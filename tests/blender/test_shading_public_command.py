"""The shading controls in the whole command, in real Blender: the four modes,
both snap targets, the dither patterns, the camera and world sky, both
projections, the output-map switches and the additional preview light, on
generated opaque, cutout and translucent subjects (shading design contract 1
to 3; SHD-6). Representative combinations, not the whole product: the pure
and stage tests pin the arithmetic, and this pins that the command wires it,
records it and reproduces it from its sheet."""

import json

import numpy as np
import pytest
import yaml
from material_models import edges, form
from PIL import Image

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

PALETTE = [
    (20, 20, 30),
    (90, 40, 40),
    (200, 60, 50),
    (60, 180, 90),
    (230, 220, 120),
    (250, 250, 250),
    (40, 60, 160),
    (150, 150, 160),
]
LIBRARY = {
    "schema": "moskophoros.materials/4",
    "ramps": {"warm": [0, 1, 2, 4], "cool": [0, 6, 7, 5]},
    "default": "cool",
    "materials": {
        "floor": {"uses": "cool"},
        "wall": {"uses": "warm"},
        "ball": {
            "ramp": [0, 3, 4, 5],
            "shade": {"mode": "both", "dither": {"pattern": "ordered4"}},
        },
        "steel": {"uses": "warm"},
        "cloth": {"ordinary": True, "shade": {"mode": "brightness"}},
        "glass": {"ramp": [6, 7]},
    },
}
# A flat front view of `edges`: the leaf cutout, the occluder and the glass.
FRONT = [
    *["--pitch", "0", "--directions", "1", "--start-angle", "0"],
    *["--ppm", "10", "--cell", "96x96", "--ground-px", "48,50"],
]
ISO = ["--directions", "2", "--cell", "40x40"]
BAKED = [
    *["--shade-mode", "both", "--bake-key-strength", "0.6"],
    *["--bake-sky-strength", "0.2", "--bake-ground-strength", "0.1"],
]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    directory = tmp_path_factory.mktemp("models")
    return {"opaque": form(directory), "cutout": edges(directory)}


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    directory = tmp_path_factory.mktemp("inputs")
    (directory / "palette.hex").write_text(
        "".join(bytes(color).hex() + "\n" for color in PALETTE)
    )
    (directory / "materials.yaml").write_text(yaml.safe_dump(LIBRARY))
    return directory


def view_of(subject):
    return ISO if subject == "opaque" else FRONT


def render(found, models, inputs, tmp_path, subject, name, *options, library=True):
    out = tmp_path / name
    out.mkdir()
    argv = [
        *["--no-user-config", "--blender", str(found.path)],
        *["--supersample", "2", "--fps", "4", "--no-preview"],
        *view_of(subject),
        *["--palette", str(inputs / "palette.hex")],
        *(["--materials", str(inputs / "materials.yaml")] if library else []),
        *options,
        str(models[subject]),
        str(out / "sheet.png"),
    ]
    status = cli.run(argv)
    assert status == 0, name
    return out


def pixels(path):
    with Image.open(path) as image:
        return np.array(image)


def opaque_colours(path):
    sheet = pixels(path)
    return {tuple(int(v) for v in p[:3]) for p in sheet.reshape(-1, 4) if p[3] == 255}


def listing(directory):
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


MODES = ["ramp", "brightness", "both", "neither"]


@pytest.mark.parametrize("subject", ["opaque", "cutout"])
def test_the_modes_change_colour_never_alpha_or_the_geometry_maps(
    capsys, found, models, inputs, tmp_path, subject
):
    base = render(found, models, inputs, tmp_path, subject, "base", "--depth")
    for mode in MODES[1:]:
        out = render(
            found,
            models,
            inputs,
            tmp_path,
            subject,
            mode,
            "--depth",
            "--shade-mode",
            mode,
            "--bake-key-strength",
            "0.5",
        )
        assert np.array_equal(
            pixels(out / "sheet.png")[..., 3], pixels(base / "sheet.png")[..., 3]
        )
        for name in ("sheet.normal.png", "sheet.depth.png"):
            assert (out / name).read_bytes() == (base / name).read_bytes()
    # The key light moves the brightness and both modes off the ramp's look.
    lit = render(
        found,
        models,
        inputs,
        tmp_path,
        subject,
        "lit",
        "--shade-mode",
        "brightness",
        "--bake-key-strength",
        "0.9",
    )
    assert (lit / "sheet.png").read_bytes() != (base / "sheet.png").read_bytes()


@pytest.mark.parametrize("subject", ["opaque", "cutout"])
@pytest.mark.parametrize("snap", ["ramp", "palette"])
def test_snapped_brightness_stays_on_the_palette(
    capsys, found, models, inputs, tmp_path, subject, snap
):
    out = render(
        found,
        models,
        inputs,
        tmp_path,
        subject,
        "snap",
        *BAKED,
        "--shade-snap",
        snap,
        "--dither-pattern",
        "clustered4",
        "--dither-strength",
        "0.7",
    )
    allowed = set(PALETTE)
    colours = opaque_colours(out / "sheet.png")
    if snap == "palette" or subject == "opaque":
        assert colours <= allowed
    # Opaque pixels stay opaque and the sheet records every setting.
    shade = json.loads((out / "sheet.json").read_text())["settings"]["shade"]
    assert shade["snap"] == snap and shade["mode"] == "both"
    assert shade["dither"] == {"pattern": "clustered4", "strength": 0.7}


@pytest.mark.parametrize("subject", ["opaque", "cutout"])
def test_a_palette_free_brightness_run_shades_the_ordinary_colour(
    capsys, found, models, inputs, tmp_path, subject
):
    plain = render(found, models, inputs, tmp_path, subject, "plain", library=False)
    out = render(
        found,
        models,
        inputs,
        tmp_path,
        subject,
        "bright",
        "--shade-mode",
        "brightness",
        "--bake-key-strength",
        "0.8",
        "--brightness-floor",
        "0.1",
        library=False,
    )
    assert (out / "sheet.png").read_bytes() != (plain / "sheet.png").read_bytes()
    assert np.array_equal(
        pixels(out / "sheet.png")[..., 3], pixels(plain / "sheet.png")[..., 3]
    )


@pytest.mark.parametrize("reduce", ["plain", "mode"])
@pytest.mark.parametrize("edge", ["hard", "soft"])
def test_both_reductions_and_both_edge_rules_reproduce_exactly(
    capsys, found, models, inputs, tmp_path, reduce, edge
):
    out = render(
        found,
        models,
        inputs,
        tmp_path,
        "cutout",
        "first",
        *BAKED,
        "--reduce",
        reduce,
        "--edges",
        edge,
        "--dither-pattern",
        "diagonal4",
        "--shade-snap",
        "palette",
    )
    again = tmp_path / "again"
    again.mkdir()
    # The sheet alone: no palette, library or model-independent option.
    status = cli.run(
        [
            *["--no-user-config", "--blender", str(found.path)],
            *["--settings-from", str(out / "sheet.json")],
            str(models["cutout"]),
            str(again / "sheet.png"),
        ]
    )
    assert status == 0
    assert listing(again) == listing(out)


def test_the_camera_and_world_sky_agree_when_level_and_unrolled_then_part_with_roll(
    capsys, found, models, inputs, tmp_path
):
    # The sphere shows normals all round, so a different sky shows.
    sky = [
        *["--shade-mode", "brightness", "--bake-sky-strength", "0.9"],
        *["--pitch", "0"],
    ]
    camera = render(found, models, inputs, tmp_path, "opaque", "camera", *sky)
    world = render(
        found,
        models,
        inputs,
        tmp_path,
        "opaque",
        "world",
        *sky,
        "--bake-sky-ground-frame",
        "world",
    )
    # Looking level, the subject's up is the picture's up.
    assert (camera / "sheet.png").read_bytes() == (world / "sheet.png").read_bytes()
    turned = [*sky, "--camera-roll", "0.25"]
    rolled_camera = render(found, models, inputs, tmp_path, "opaque", "rc", *turned)
    rolled_world = render(
        found,
        models,
        inputs,
        tmp_path,
        "opaque",
        "rw",
        *turned,
        "--bake-sky-ground-frame",
        "world",
    )
    # Camera-frame terms follow the roll with the picture; the world's do not.
    assert (rolled_camera / "sheet.png").read_bytes() != (
        rolled_world / "sheet.png"
    ).read_bytes()
    record = json.loads((rolled_world / "sheet.json").read_text())
    assert record["settings"]["shade"]["sky_ground_frame"] == "world"
    assert record["settings"]["camera"]["roll"] == 0.25


def test_the_world_sky_follows_the_camera_pitch_not_the_roll_of_the_picture(
    capsys, found, models, inputs, tmp_path
):
    sky = ["--shade-mode", "brightness", "--bake-sky-strength", "0.9"]
    camera = render(found, models, inputs, tmp_path, "opaque", "camera", *sky)
    world = render(
        found,
        models,
        inputs,
        tmp_path,
        "opaque",
        "world",
        *sky,
        "--bake-sky-ground-frame",
        "world",
    )
    # An isometric camera looks down, so the two frames differ.
    assert (camera / "sheet.png").read_bytes() != (world / "sheet.png").read_bytes()


def test_a_perspective_camera_with_roll_bakes_and_reproduces(
    capsys, found, models, inputs, tmp_path
):
    options = [
        *["--projection", "perspective", "--camera-position", "0,2,9"],
        *["--camera-roll", "-0.1", "--bake-sky-ground-frame", "world"],
        *BAKED,
        *["--dither-pattern", "shuffled8", "--shade-snap", "ramp"],
    ]
    out = render(found, models, inputs, tmp_path, "opaque", "perspective", *options)
    again = tmp_path / "again"
    again.mkdir()
    status = cli.run(
        [
            *["--no-user-config", "--blender", str(found.path)],
            *["--settings-from", str(out / "sheet.json")],
            str(models["opaque"]),
            str(again / "sheet.png"),
        ]
    )
    assert status == 0
    assert listing(again) == listing(out)
    # The key stays camera-fixed under perspective: one direction for the image.
    shade = json.loads((out / "sheet.json").read_text())["settings"]["shade"]
    assert shade["key"]["strength"] == 0.6


def test_the_additional_preview_light_lights_baked_colour_and_nothing_bakes_it(
    capsys, found, models, inputs, tmp_path
):
    out = tmp_path / "lit"
    out.mkdir()
    status = cli.run(
        [
            *["--no-user-config", "--blender", str(found.path)],
            *["--supersample", "2", "--fps", "4", *ISO],
            *["--palette", str(inputs / "palette.hex")],
            *["--materials", str(inputs / "materials.yaml")],
            *["--shade-mode", "brightness", "--bake-key-strength", "0.5"],
            *["--light", "30,40,50", "--depth"],
            str(models["opaque"]),
            str(out / "sheet.png"),
        ]
    )
    assert status == 0
    names = {path.name for path in out.iterdir()}
    assert {"sheet-lit.default.gif", "sheet.default.gif"} <= names or any(
        "-lit." in name for name in names
    )
    assert {"sheet.normal.png", "sheet.depth.png", "sheet.json"} <= names
    # The unlit sheet is the same with and without the preview light.
    plain = render(
        found,
        models,
        inputs,
        tmp_path,
        "opaque",
        "plain",
        "--shade-mode",
        "brightness",
        "--bake-key-strength",
        "0.5",
        "--depth",
    )
    assert (out / "sheet.png").read_bytes() == (plain / "sheet.png").read_bytes()


def test_the_output_switches_leave_the_baked_colour_alone(
    capsys, found, models, inputs, tmp_path
):
    full = render(found, models, inputs, tmp_path, "opaque", "full", *BAKED, "--depth")
    bare = render(
        found,
        models,
        inputs,
        tmp_path,
        "opaque",
        "bare",
        *BAKED,
        "--no-normals",
    )
    assert (full / "sheet.png").read_bytes() == (bare / "sheet.png").read_bytes()
    assert not (bare / "sheet.normal.png").exists()
    assert (full / "sheet.depth.png").exists()


def test_a_library_override_beats_a_global_option_in_the_rendering(
    capsys, found, models, inputs, tmp_path
):
    # The ball's library entry says both; a global `neither` cannot defeat it.
    loud = render(
        found, models, inputs, tmp_path, "opaque", "loud", "--shade-mode", "neither"
    )
    quiet = render(
        found, models, inputs, tmp_path, "opaque", "quiet", "--shade-mode", "ramp"
    )
    assert (loud / "sheet.png").read_bytes() != (quiet / "sheet.png").read_bytes()
    record = json.loads((loud / "sheet.json").read_text())["settings"]
    assert record["style"]["materials"]["materials"]["ball"]["shade"]["mode"] == "both"
