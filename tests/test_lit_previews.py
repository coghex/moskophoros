"""Lit previews: an optional point light, computed as a game reading the
exported maps would, written beside the flat previews and never baked
(design §Export, Previews; lighting sheet design D-4, D-5, D-13, D-14, D-18,
D-21, D-22, D-23, D-24 and its Numerical reference)."""

import json
import math

import numpy as np
import pytest
from glb_writer import GlbWriter
from PIL import Image
from shading import DEFAULT_SHADE
from test_command import Setup, earlier_outputs, run
from test_materials_command import forbid_blender
from test_reuse import write_sheet

from moskophoros import cli, export, imageops, views
from moskophoros.capture.backend import Settings
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import (
    DEPTH_MAP,
    NORMAL_MAP,
    FrameAddress,
    ImageFrame,
)

UP = (128, 128, 255)
ZERO = 32768


# The formula, reimplemented here as a game would, from the Numerical
# reference: decode the exported bytes and codes, light, encode.

SRGB = np.arange(256) / 255
SRGB_LINEAR = np.where(SRGB <= 0.04045, SRGB / 12.92, ((SRGB + 0.055) / 1.055) ** 2.4)


def game_light(colour, normal_bytes, codes, ground_px, light, intensity, ambient):
    """A cell lit as a game shader reading the exported maps would."""
    height, width = codes.shape
    m = 2 * normal_bytes.astype(np.float64) / 255 - 1
    n = m / np.linalg.norm(m, axis=-1, keepdims=True).clip(min=1e-300)
    d = (codes.astype(np.float64) - 32768) / 16
    gx, gy = ground_px
    c, r = np.meshgrid(np.arange(width), np.arange(height))
    p = np.stack((c + 0.5 - gx, gy - r - 0.5, d), axis=-1)
    v = np.asarray(light, dtype=np.float64) - p
    big = np.abs(v).max(axis=-1, keepdims=True)
    w = v / np.where(big == 0, 1, big)
    size = np.linalg.norm(w, axis=-1, keepdims=True)
    lights = w / np.where(size == 0, 1, size)
    q = np.clip(np.sum(n * lights, axis=-1), 0, 1)
    q[big[..., 0] == 0] = 0
    f = np.minimum(1, ambient + (1 - ambient) * intensity * q)
    x = SRGB_LINEAR[colour[..., :3]] * f[..., None]
    s = np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)
    lit = np.zeros_like(colour)
    covered = colour[..., 3] == 255
    lit[covered, :3] = np.minimum(255, np.floor(255 * s + 0.5))[covered]
    lit[covered, 3] = 255
    return lit, f


def cell(colour=(200, 100, 50), normal=UP, code=ZERO, at=(24, 45), size=(48, 48)):
    """A cell with one covered pixel at `at` (column, row)."""
    width, height = size
    pixels = np.zeros((height, width, 4), dtype=np.uint8)
    normals = np.zeros((height, width, 3), dtype=np.uint8)
    codes = np.zeros((height, width), dtype=np.uint16)
    c, r = at
    pixels[r, c] = (*colour, 255)
    normals[r, c] = normal
    codes[r, c] = code
    return pixels, normals, codes


# The design's reference vectors (A = 0.3, I = 1, (gx, gy) = (24, 46)).

REFERENCE = [
    (
        (200, 100, 50),
        (128, 128, 255),
        32768,
        (24, 45),
        (0.5, 0.5, 100),
        0.9999892352,
        (200, 100, 50),
    ),
    (
        (200, 100, 50),
        (128, 128, 255),
        32768,
        (24, 45),
        (0.5, 0.5, -100),
        0.3,
        (116, 55, 25),
    ),
    (
        (200, 100, 50),
        (218, 128, 218),
        32848,
        (24, 45),
        (100.5, 0.5, 5),
        0.7949709697,
        (180, 90, 44),
    ),
    (
        (200, 100, 50),
        (128, 128, 255),
        32768,
        (24, 45),
        (0.5, 0.5, 0),
        0.3,
        (116, 55, 25),
    ),
    (
        (255, 255, 255),
        (128, 218, 218),
        32768,
        (30, 40),
        (-20, 30, 40),
        0.8912435296,
        (242, 242, 242),
    ),
]


@pytest.mark.parametrize(
    ("colour", "normal", "code", "at", "light", "factor", "lit"),
    REFERENCE,
    ids=["in front", "behind", "tilted and deep", "at the pixel", "white"],
)
def test_the_design_s_reference_vectors(colour, normal, code, at, light, factor, lit):
    pixels, normals, codes = cell(colour, normal, code, at)
    c, r = at
    f = imageops.light_factors(normals, codes, (24, 46), light, 1.0, 0.3)
    assert round(float(f[r, c]), 10) == factor
    result = imageops.light_pixels(pixels, normals, codes, (24, 46), light, 1.0, 0.3)
    assert tuple(int(v) for v in result[r, c]) == (*lit, 255)
    game, _ = game_light(pixels, normals, codes, (24, 46), light, 1.0, 0.3)
    np.testing.assert_array_equal(result, game)


def test_a_light_behind_the_surface_gives_the_ambient_level():
    pixels, normals, codes = cell()
    f = imageops.light_factors(normals, codes, (24, 46), (0.5, 0.5, -3), 1.0, 0.42)
    assert f[45, 24] == 0.42


def test_a_distant_light_matches_a_uniform_direction():
    # Far away along (1, 2, 3), every pixel sees the same direction.
    rng = np.random.default_rng(1)
    normals = rng.integers(0, 256, (20, 30, 3)).astype(np.uint8)
    normals[..., 2] = rng.integers(140, 256, (20, 30))
    codes = rng.integers(30000, 35000, (20, 30)).astype(np.uint16)
    direction = np.array([1.0, 2.0, 3.0]) / math.sqrt(14)
    far = imageops.light_factors(normals, codes, (15, 18), direction * 1e12, 1.0, 0.3)
    m = 2 * normals.astype(np.float64) / 255 - 1
    n = m / np.linalg.norm(m, axis=-1, keepdims=True)
    expected = np.minimum(1, 0.3 + 0.7 * np.clip(n @ direction, 0, 1))
    np.testing.assert_allclose(far, expected, atol=1e-9)


def test_a_light_at_the_pixel_s_centre_gives_ambient_only():
    pixels, normals, codes = cell(code=ZERO + 40)
    f = imageops.light_factors(normals, codes, (24, 46), (0.5, 0.5, 2.5), 1.0, 0.3)
    assert f[45, 24] == 0.3


def test_a_very_far_light_gives_a_moderate_light_s_result():
    # S-3: 1e200 from the pixel's centre, along a direction, against 5.
    pixels, normals, codes = cell(normal=(200, 160, 220), code=ZERO + 16)
    centre = np.array([0.5, 0.5, 1.0])  # pixel (24, 45) at depth 1
    direction = np.array([0.3, -0.4, 0.9])
    moderate = imageops.light_factors(
        normals, codes, (24, 46), centre + 5 * direction, 1.0, 0.3
    )
    far = imageops.light_factors(
        normals, codes, (24, 46), centre + 1e200 * direction, 1.0, 0.3
    )
    assert np.isfinite(far).all()
    assert far[45, 24] == pytest.approx(moderate[45, 24], abs=1e-12)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_a_very_near_light_gives_a_moderate_light_s_result(sign):
    # S-3: 1e-200 from the pixel's centre. A pixel centre's x and y are
    # halves, so in float64 only a light straight in front of or behind a
    # pixel at depth 0 can be that near: (0.5, 0.5, ±1e-200).
    pixels, normals, codes = cell(normal=(200, 160, 220), code=ZERO)
    near = imageops.light_factors(
        normals, codes, (24, 46), (0.5, 0.5, sign * 1e-200), 1.0, 0.3
    )
    moderate = imageops.light_factors(
        normals, codes, (24, 46), (0.5, 0.5, sign * 5.0), 1.0, 0.3
    )
    assert np.isfinite(near).all()
    assert near[45, 24] == moderate[45, 24]
    assert bool(near[45, 24] > 0.3) is (sign > 0)


def test_the_diffuse_term_is_bounded_so_no_intermediate_is_infinite():
    # The review's vector: N·L rounds to 1.0000000000000002 without the bound,
    # and an intensity at the float64 limit would overflow.
    normals = np.array([[[38, 38, 139]]], dtype=np.uint8)
    codes = np.array([[ZERO]], dtype=np.uint16)
    with np.errstate(all="raise"):
        f = imageops.light_factors(
            normals,
            codes,
            (0, 0),
            (0.5 - 179, -0.5 - 179, 23),
            1.7976931348623157e308,
            0.0,
        )
    assert f[0, 0] == 1.0


def test_no_nan_or_infinity_for_any_finite_light():
    rng = np.random.default_rng(9)
    normals = rng.integers(0, 256, (16, 16, 3)).astype(np.uint8)
    codes = rng.integers(1, 65536, (16, 16)).astype(np.uint16)
    pixels = rng.integers(0, 256, (16, 16, 4)).astype(np.uint8)
    pixels[..., 3] = np.where(rng.random((16, 16)) < 0.5, 255, 0)
    for light in [
        (0, 0, 0),
        (1e300, -1e300, 1e300),
        (-1e-300, 2e-300, 0),
        (8.5, 7.5, 0),
    ]:
        for intensity in (0.0, 1.0, 1e308):
            with np.errstate(all="raise"):
                f = imageops.light_factors(
                    normals, codes, (8, 8), light, intensity, 0.3
                )
                lit = imageops.light_pixels(
                    pixels, normals, codes, (8, 8), light, intensity, 0.3
                )
            assert np.isfinite(f).all() and ((0 <= f) & (f <= 1)).all()
            assert (lit[pixels[..., 3] == 0] == 0).all()
            np.testing.assert_array_equal(lit[..., 3], pixels[..., 3])


# In memory: lit_previews against the reconstruction from the encoded maps

SETTINGS = Settings(
    view="custom",
    direction=views.pitch_direction(30.0),
    directions=2,
    start_angle=0.0,
    model_yaw=0.0,
    fps=4.0,
    supersample=1,
    ppm=10.0,
    cell=(6, 5),
    ground=(0.0, 0.0, 0.0),
    ground_px=(3, 4),
    root_motion="error",
    shade=DEFAULT_SHADE,
)
WALK = SelectedClip(Clip(0, "walk", 0.0, 0.5, ()), one_shot=False)


def frames(seed=0, depth=(-3.0, 4.0)):
    rng = np.random.default_rng(seed)
    result = []
    for direction in (0, 1):
        for time_s in (0.0, 0.25):
            pixels = np.zeros((5, 6, 4), dtype=np.uint8)
            pixels[..., :3] = rng.integers(0, 256, 3)
            pixels[..., 3] = np.where(rng.random((5, 6)) < 0.7, 255, 0)
            normals = rng.normal(size=(5, 6, 3))
            normals[..., 2] = np.abs(normals[..., 2]) + 0.5
            normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
            depths = rng.integers(int(depth[0] * 16), int(depth[1] * 16), (5, 6)) / 16
            address = FrameAddress("hero", "default", "walk", direction, time_s)
            maps = {NORMAL_MAP: normals, DEPTH_MAP: depths}
            result.append(ImageFrame(address, pixels, buffers=maps))
    return result


def lit_preview(given, light):
    (preview,) = export.lit_previews(
        given, subject="hero", settings=SETTINGS, selected_clips=(WALK,), light=light
    )
    return preview


def test_in_memory_reconstruction_matches_the_lit_preview():
    given = frames()
    light = export.Light((7.0, 9.0, 20.0), 1.3, 0.2)
    reconstructed = []
    for frame in given:
        covered = frame.pixels[..., 3] == 255
        normal_bytes = np.zeros((5, 6, 3), dtype=np.uint8)
        normal_bytes[covered] = imageops.encode_normal(
            frame.buffers[NORMAL_MAP][covered]
        )
        codes = np.zeros((5, 6), dtype=np.uint16)
        codes[covered] = export.encode_depth(frame.buffers[DEPTH_MAP][covered])
        lit, _ = game_light(
            frame.pixels, normal_bytes, codes, (3, 4), light.position, 1.3, 0.2
        )
        reconstructed.append(ImageFrame(frame.address, lit))
    (expected,) = export.previews(
        reconstructed, subject="hero", settings=SETTINGS, selected_clips=(WALK,)
    )
    assert lit_preview(given, light).gif == expected.gif


def test_the_lit_preview_differs_from_the_flat_one_and_names_its_warning():
    given = frames()
    (flat,) = export.previews(
        given, subject="hero", settings=SETTINGS, selected_clips=(WALK,)
    )
    assert lit_preview(given, export.Light((7.0, 9.0, 20.0))).gif != flat.gif
    # Many colours: the reduction warns, naming the clip's lit preview.
    noisy = frames()
    rng = np.random.default_rng(3)
    big = Settings(**{**SETTINGS.__dict__, "cell": (40, 40), "ground_px": (20, 30)})
    for i, frame in enumerate(noisy):
        pixels = rng.integers(0, 256, (40, 40, 4), dtype=np.uint8)
        pixels[..., 3] = 255
        normals = np.zeros((40, 40, 3))
        normals[..., 2] = 1.0
        maps = {NORMAL_MAP: normals, DEPTH_MAP: np.zeros((40, 40))}
        noisy[i] = ImageFrame(frame.address, pixels, buffers=maps)
    (preview,) = export.lit_previews(
        noisy,
        subject="hero",
        settings=big,
        selected_clips=(WALK,),
        light=export.Light((0.0, 0.0, 50.0)),
    )
    assert preview.warnings == (
        "clip 'walk''s lit preview has frames with more than 256 colors, "
        "reduced to 256 without dithering",
    )


def test_a_depth_beyond_the_range_is_an_overflow_for_the_lit_preview():
    given = frames()
    given[3].buffers[DEPTH_MAP][given[3].pixels[..., 3] == 255] = 2048.0
    with pytest.raises(export.DepthOverflow) as raised:
        lit_preview(given, export.Light((1.0, 1.0, 1.0)))
    assert raised.value.exit_code == 4
    assert "clip 'walk', direction 1, time 0.25 s" in str(raised.value)


def test_lit_names_never_collide_with_flat_ones():
    clips = [
        SelectedClip(Clip(i, name, 0.0, 1.0, ()), one_shot=False)
        for i, name in enumerate(["walk", "walk.lit", "Walk", "walk-2", "a/b", "a b"])
    ]
    flat = [p.name for p in export.preview_paths("out/hero.png", clips)]
    lit = [p.name for p in export.lit_preview_paths("out/hero.png", clips)]
    assert flat == [
        "hero.walk.gif",
        "hero.walk.lit.gif",
        "hero.Walk-3.gif",
        "hero.walk-2.gif",
        "hero.a_b.gif",
        "hero.a_b-2.gif",
    ]
    assert lit == [name.replace("hero.", "hero-lit.", 1) for name in flat]
    assert not {n.lower() for n in flat} & {n.lower() for n in lit}


# The command


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def lit_names(setup):
    return sorted(name for name in setup.listing() if name.startswith("hero-lit."))


def test_a_light_writes_a_lit_preview_per_clip_beside_the_flat_ones(setup, capsys):
    setup.configure(depths=[0.4, -0.3])
    status, _, err = run(capsys, setup.argv("--light", "-20,30,40"))
    assert (status, err) == (0, "")
    assert lit_names(setup) == ["hero-lit.attack.gif", "hero-lit.walk.gif"]
    document = json.loads(setup.json.read_text())
    assert document["settings"]["light"] == {
        "position": [-20.0, 30.0, 40.0],
        "intensity": 1.0,
        "ambient": 0.3,
    }
    keys = list(document["settings"])
    assert keys[keys.index("depth") + 1] == "light"


def test_without_a_light_nothing_is_lit(setup, capsys):
    assert run(capsys, setup.argv())[0] == 0
    assert lit_names(setup) == []
    assert json.loads(setup.json.read_text())["settings"]["light"]["position"] is None


def test_a_light_changes_no_other_output(setup, capsys):
    setup.configure(depths=[0.4, -0.3], surfaces="varied")
    assert run(capsys, setup.argv("--depth"))[0] == 0
    flat = setup.listing()
    assert run(capsys, setup.argv("--depth", "--light", "5,5,30"))[0] == 0
    lit = setup.listing()
    for name in flat:
        if name != "hero.json":
            assert lit[name] == flat[name], name
    before, after = json.loads(flat["hero.json"]), json.loads(lit["hero.json"])
    differing = {k for k in before if before[k] != after[k]}
    assert differing == {"settings", "fingerprint"}
    assert {
        k for k in before["settings"] if before["settings"][k] != after["settings"][k]
    } == {"light"}


def test_previews_off_records_the_light_unused_and_warns_once(setup, capsys):
    status, _, err = run(capsys, setup.argv("--light", "1,2,3", "--no-preview"))
    assert status == 0
    assert err == (
        "moskophoros: warning: the light at (1.0, 2.0, 3.0) is recorded but "
        "unused: previews are off, so no lit preview is written\n"
    )
    assert lit_names(setup) == []
    document = json.loads(setup.json.read_text())
    assert document["settings"]["light"]["position"] == [1.0, 2.0, 3.0]


def test_an_earlier_lit_preview_stays_when_none_is_written(setup, capsys):
    earlier = earlier_outputs(setup, "hero-lit.walk.gif")
    assert run(capsys, setup.argv())[0] == 0
    assert setup.listing()["hero-lit.walk.gif"] == earlier["hero-lit.walk.gif"]


# The depth range (D-21, D-24, S-1)


def too_deep(setup):
    """Every captured pixel 200 m toward the viewer: thousands of sheet
    pixels in the 16×16 cell fitted to the 0.75 m subject."""
    setup.configure(depths=[200.0])


@pytest.mark.parametrize("depth", [(), ("--no-depth",)], ids=["default", "--no-depth"])
def test_a_light_with_previews_on_and_a_depth_beyond_the_range_overflows(
    setup, capsys, depth
):
    earlier = earlier_outputs(setup, "hero.png", "hero.json")
    too_deep(setup)
    status, _, err = run(capsys, setup.argv("--light", "0,0,50", *depth))
    assert status == 4
    assert "the subject's depth overflows the depth map" in err
    assert "give a smaller --ppm" in err
    assert setup.listing() == earlier


def test_previews_off_controls_pass_a_depth_beyond_the_range(setup, capsys, tmp_path):
    too_deep(setup)
    # A configured light, previews off, no depth map: recorded, warned, fine.
    config = tmp_path / "light.yaml"
    config.write_text("light:\n  position: [0, 0, 50]\n")
    status, _, err = run(capsys, setup.argv("--config", str(config), "--no-preview"))
    assert status == 0, err
    assert "recorded but unused" in err
    # A reused light, previews off: the same.
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    status, _, err = run(capsys, reload(setup, sheet))
    assert status == 0, err
    assert "recorded but unused" in err
    # Previews on: an overflow. The depth map on: an overflow too.
    assert run(capsys, setup.argv("--config", str(config)))[0] == 4
    assert (
        run(capsys, setup.argv("--config", str(config), "--no-preview", "--depth"))[0]
        == 4
    )


# Settings and options (D-18, S-3)


def reload(setup, sheet, *options):
    return [
        "--settings-from",
        str(sheet),
        "--no-user-config",
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(setup.png),
    ]


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--light", "1,2", "expected X,Y,Z, three finite numbers"),
        ("--light", "1,nan,3", "expected X,Y,Z, three finite numbers"),
        ("--light", "inf,0,0", "expected X,Y,Z, three finite numbers"),
        ("--light-intensity", "-1", "must be 0 or greater"),
        ("--light-intensity", "nan", "expected a finite number"),
        ("--light-ambient", "1.5", "must be from 0 to 1"),
        ("--light-ambient", "-0.1", "must be from 0 to 1"),
        ("--light-ambient", "inf", "expected a finite number"),
    ],
)
def test_bad_options_are_usage_errors_before_blender(
    setup, capsys, monkeypatch, option, value, message
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv(option, value))
    assert status == 2
    assert f"argument {option}: {message}" in err


def test_light_and_no_light_together_are_refused(setup, capsys, monkeypatch):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--light", "1,2,3", "--no-light"))
    assert status == 2
    assert "--light and --no-light cannot be given together" in err


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("light: {position: [1, 2]}", "light.position: expected [x, y, z]"),
        ("light: {position: [1, .nan, 3]}", "light.position: expected [x, y, z]"),
        ("light: {position: [1, true, 3]}", "light.position: expected [x, y, z]"),
        ("light: {position: 5}", "light.position: expected [x, y, z]"),
        ("light: {intensity: -2}", "light.intensity: expected a finite number 0 or"),
        ("light: {intensity: .inf}", "light.intensity: expected a"),
        ("light: {ambient: 2}", "light.ambient: expected a finite number from 0 to 1"),
        ("light: {ambient: true}", "light.ambient: expected a number"),
        ("light: {colour: red}", "light.colour: unknown key"),
    ],
)
def test_bad_light_values_in_a_file_name_the_file_key_and_line(
    setup, capsys, tmp_path, monkeypatch, text, message
):
    path = tmp_path / "bad.yaml"
    path.write_text("version: 1\n" + text + "\n")
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--config", str(path)))
    assert status == 2
    assert f"--config {str(path)!r}: {message}" in err
    assert "line 2" in err


def resolved(tmp_path, *args, user=None, project=None):
    environ = {"XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    if user is not None:
        path = tmp_path / "xdg" / "moskophoros" / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(user)
    if project is not None:
        path = tmp_path / "xdg" / "moskophoros" / "projects" / "look.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(project)
        args = (*args, "--project", "look")
    return cli.resolve_settings(cli.parse_args([*args, "in.glb", "out.png"]), environ)


def test_light_merges_key_by_key_and_position_replaces_whole(tmp_path):
    a = tmp_path / "a.yaml"
    a.write_text("light:\n  position: [1, 2, 3]\n  intensity: 2.0\n")
    b = "light:\n  ambient: 0.5\n  position: [4, 5, 6]\n"
    options = resolved(tmp_path, "--config", str(a), project=b)
    assert (options.light, options.light_intensity, options.light_ambient) == (
        (4.0, 5.0, 6.0),
        2.0,
        0.5,
    )
    options = resolved(tmp_path, user="light:\n  intensity: 0.25\n")
    assert (options.light, options.light_intensity, options.light_ambient) == (
        None,
        0.25,
        0.3,
    )


def test_no_light_drops_a_configured_or_reused_light(tmp_path):
    config = tmp_path / "light.yaml"
    config.write_text("light:\n  position: [1, 2, 3]\n")
    assert resolved(tmp_path, "--config", str(config), "--no-light").light is None
    assert resolved(tmp_path, "--config", str(config)).light == (1.0, 2.0, 3.0)
    off = "light:\n  position: null\n"
    assert resolved(tmp_path, "--config", str(config), project=off).light is None
    sheet = write_sheet(tmp_path)
    reused = cli.resolve_settings(
        cli.parse_args(
            ["--settings-from", str(sheet), "--no-user-config", "in.glb", "o.png"]
        )
    )
    assert reused.light == (-20.0, 30.0, 40.5)
    dropped = cli.resolve_settings(
        cli.parse_args(
            [
                "--settings-from",
                str(sheet),
                "--no-user-config",
                "--no-light",
                "in.glb",
                "o.png",
            ]
        )
    )
    assert dropped.light is None and dropped.light_intensity == 1.5


@pytest.mark.parametrize(
    ("light", "problem"),
    [
        ({"position": None, "intensity": 1.0}, "settings.light.ambient: missing"),
        (
            {"position": None, "intensity": 1.0, "ambient": 0.3, "colour": 1},
            "settings.light.colour: unknown field",
        ),
        (
            {"position": [1, 2], "intensity": 1.0, "ambient": 0.3},
            "settings.light.position",
        ),
        (
            {"position": [1, True, 3], "intensity": 1.0, "ambient": 0.3},
            "settings.light.position",
        ),
        (
            {"position": "1,2,3", "intensity": 1.0, "ambient": 0.3},
            "settings.light.position",
        ),
        (
            {"position": None, "intensity": True, "ambient": 0.3},
            "settings.light.intensity",
        ),
        (
            {"position": None, "intensity": -1, "ambient": 0.3},
            "settings.light.intensity",
        ),
        (
            {"position": None, "intensity": 1.0, "ambient": 1.5},
            "settings.light.ambient",
        ),
        (None, "settings.light: must be set"),
    ],
)
@pytest.mark.parametrize("override", [(), ("--no-light",), ("--light", "1,1,1")])
def test_a_malformed_recorded_light_is_refused_before_any_override(
    setup, capsys, tmp_path, monkeypatch, light, problem, override
):
    from test_reuse import SETTINGS

    sheet = write_sheet(tmp_path, SETTINGS | {"light": light})
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, reload(setup, sheet, *override))
    assert status == 2
    assert problem in err


# Reuse, publication and reconstruction


def test_a_sheet_with_a_light_reproduces_its_lit_previews(setup, capsys, tmp_path):
    setup.configure(depths=[0.4, -0.3], surfaces="varied")
    assert (
        run(capsys, setup.argv("--light", "-20,30,40", "--light-ambient", "0.2"))[0]
        == 0
    )
    first = setup.listing()
    assert "hero-lit.walk.gif" in first
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(first["hero.json"])
    for name in list(first):
        (setup.out / name).unlink()
    assert run(capsys, reload(setup, sheet))[0] == 0
    assert setup.listing() == first


def test_a_failed_rename_rolls_the_lit_previews_back(setup, capsys, monkeypatch):
    import os

    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero-lit.walk.gif")
    real = os.replace

    def replace(source, target):
        if str(target).endswith("hero-lit.attack.gif"):
            raise OSError(16, "Device or resource busy")
        return real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    status, _, err = run(capsys, setup.argv("--light", "1,2,3"))
    assert status == 6
    assert "hero-lit.attack.gif" in err
    assert setup.listing() == earlier


def test_clips_named_alike_publish_flat_and_lit_previews_apart(setup, capsys):
    setup.model.unlink()
    model = GlbWriter()
    hips = model.node("hips", mesh=True)
    model.scene([hips], default=True)
    for name in ("walk", "walk.lit", "Walk", "walk-2"):
        model.animation(
            name, [(hips, "translation", [0.0, 0.5], [(0, 0, 0), (0, 0.01, 0)])]
        )
    setup.model = model.write(setup.model.parent, "hero")
    argv = setup.argv("--light", "1,2,3")
    argv[argv.index("--once") : argv.index("--once") + 2] = []
    status, _, err = run(capsys, argv)
    assert status == 0, err
    names = sorted(setup.listing())
    flat = [n for n in names if n.endswith(".gif") and n.startswith("hero.")]
    lit = [n for n in names if n.startswith("hero-lit.")]
    assert len(flat) == len(lit) == 4
    assert sorted(n.replace("hero.", "hero-lit.", 1) for n in flat) == lit


def decode_png(path):
    with Image.open(path) as image:
        return np.asarray(image)


def test_production_reconstruction_from_the_exported_files(setup, capsys):
    """S-2: the lit previews recomputed from the exported colour, normal and
    depth PNGs, decoded as a game would, with nonzero signed depths, match
    the written lit previews after the GIF handling."""
    setup.configure(depths=[0.4, -0.3, 0.15], surfaces="varied")
    light = (-6.0, 9.0, 25.0)
    argv = setup.argv("--depth", "--light", "-6,9,25", "--light-intensity", "1.4")
    assert run(capsys, argv)[0] == 0
    document = json.loads(setup.json.read_text())
    colour = decode_png(setup.png)
    normal = decode_png(setup.out / document["maps"]["normal"]["file"])
    depth = decode_png(setup.out / document["maps"]["depth"]["file"])
    covered_depths = (depth[colour[..., 3] == 255].astype(np.int64) - ZERO) / 16
    assert (covered_depths > 0).any() and (covered_depths < 0).any()
    gx, gy = (
        document["settings"]["ground_px"]["x"],
        document["settings"]["ground_px"]["y"],
    )
    settings = cli.capture_settings(
        cli.resolve_settings(
            cli.parse_args(
                [
                    "--settings-from",
                    str(setup.json),
                    "--no-user-config",
                    "in.glb",
                    "o.png",
                ]
            )
        )
    )
    frames = []
    for entry in document["frames"]:
        x, y, w, h = entry["x"], entry["y"], entry["w"], entry["h"]
        lit, _ = game_light(
            colour[y : y + h, x : x + w],
            normal[y : y + h, x : x + w, :3],
            depth[y : y + h, x : x + w],
            (gx, gy),
            light,
            1.4,
            0.3,
        )
        address = FrameAddress(
            document["subject"],
            "default",
            entry["clip"],
            entry["direction"],
            entry["time_s"],
        )
        frames.append(ImageFrame(address, lit))
    selected = [
        SelectedClip(
            Clip(i, clip["name"], 0.0, clip["duration_s"], ()),
            one_shot=not clip["loop"],
        )
        for i, clip in enumerate(document["clips"])
    ]
    rebuilt = export.previews(
        frames, subject=document["subject"], settings=settings, selected_clips=selected
    )
    for preview in rebuilt:
        written = (setup.out / f"hero-lit.{preview.clip}.gif").read_bytes()
        assert written == preview.gif, preview.clip
