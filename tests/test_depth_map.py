"""The optional depth map: written when asked, recorded in the sheet's JSON,
checked against its range and reproduced by `--settings-from` (design
§Export, §CLI, §Settings files, §Scale and ground point; lighting sheet design
D-3, D-10, D-17, D-18, D-19, D-21, D-24)."""

import io
import json
import struct

import numpy as np
import pytest
from PIL import Image
from test_command import Setup, earlier_outputs, run
from test_export import GENERATOR, PLAIN, POSE, RANGE, RUN, SIDE, SOURCE, STRIKE
from test_export import TIMES as SIDE_TIMES
from test_materials_command import forbid_blender

from moskophoros import cli, export, imageops
from moskophoros.sampling import DEPTH_MAP, NORMAL_MAP, FrameAddress, ImageFrame

LIMIT = 2047.9375


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def chunks(png):
    found, at = [], 8
    while at < len(png):
        length = int.from_bytes(png[at : at + 4])
        found.append((png[at + 4 : at + 8], png[at + 8 : at + 8 + length]))
        at += 12 + length
    return found


def decoded(png):
    with Image.open(io.BytesIO(png)) as image:
        return np.asarray(image)


# The map, from export.encode


def side_frames(depth_of, seed=0):
    """The export tests' side sheet frames (2×3 cells), each with partial
    coverage; `depth_of(address, rng)` gives a cell's depths."""
    rng = np.random.default_rng(seed)
    frames = []
    for clip, times in SIDE_TIMES.items():
        for direction in (0, 1):
            for time_s in times:
                address = FrameAddress("héros", "default", clip, direction, time_s)
                pixels = rng.integers(0, 256, (3, 2, 4), dtype=np.uint8)
                pixels[..., 3] = np.where(rng.random((3, 2)) < 0.6, 255, 0)
                pixels[0, 0, 3] = 255
                normals = np.zeros((3, 2, 3))
                normals[..., 2] = 1.0
                depths = np.asarray(depth_of(address, rng), dtype=np.float64)
                depths = np.where(pixels[..., 3] == 255, depths, 0.0)
                maps = {NORMAL_MAP: normals, DEPTH_MAP: depths}
                frames.append(ImageFrame(address, pixels, buffers=maps))
    return frames


def grid_depths(address, rng):
    """Depths on the 1/16 grid, in front of and behind the ground point."""
    return rng.integers(-2000 * 16, 2000 * 16, (3, 2)) / 16


def encode(frames, **changes):
    arguments = {
        "generator": GENERATOR,
        "source": SOURCE,
        "subject": "héros",
        "settings": SIDE,
        "style": PLAIN,
        "shade_range": RANGE,
        "selected_clips": (RUN, STRIKE, POSE),
        "image_path": "héros.png",
        "depth": True,
    } | changes
    return export.encode(frames, **arguments)


def test_the_map_is_16_bit_greyscale_with_no_text_or_time_chunks():
    sheet = encode(side_frames(grid_depths))
    found = chunks(sheet.depth)
    assert [kind for kind, _ in found if kind != b"IDAT"] == [b"IHDR", b"IEND"]
    width, height, bits, colour = struct.unpack(">IIBB", found[0][1][:10])
    assert (bits, colour) == (16, 0)
    assert (width, height) == decoded(sheet.png).shape[1::-1]


def test_covered_pixels_hold_their_code_in_their_cell_and_all_else_is_0():
    frames = side_frames(grid_depths)
    sheet = encode(frames)
    codes, colour = decoded(sheet.depth), decoded(sheet.png)
    assert codes.dtype == np.uint16 and codes.shape == colour.shape[:2]
    assert (codes[colour[..., 3] == 0] == 0).all()
    by_address = {
        (f.address.clip, f.address.direction, f.address.time_s): f for f in frames
    }
    for entry in json.loads(sheet.json)["frames"]:
        frame = by_address[(entry["clip"], entry["direction"], entry["time_s"])]
        cell = codes[entry["y"] : entry["y"] + 3, entry["x"] : entry["x"] + 2]
        covered = frame.pixels[..., 3] == 255
        expected = 32768 + 16 * frame.buffers[DEPTH_MAP][covered]
        np.testing.assert_array_equal(cell[covered], expected)
        assert (cell[~covered] == 0).all()
    # Unused cells (läuft has 3 frames, 攻撃 4) are 0 too.
    assert (codes[0:3, 6:8] == 0).all()


@pytest.mark.parametrize(
    ("depth", "code"),
    [
        (0.0, 32768),
        (0.0625, 32769),  # in front of the ground point: above 32768
        (-0.0625, 32767),  # behind it: below
        (12.5, 32968),
        (LIMIT, 65535),
        (-LIMIT, 1),
    ],
)
def test_the_encoding(depth, code):
    frames = side_frames(lambda address, rng: np.full((3, 2), depth))
    codes, colour = decoded(encode(frames).depth), decoded(encode(frames).png)
    assert (codes[colour[..., 3] == 255] == code).all()
    assert tuple(export.encode_depth([depth])) == (code,)


def test_a_32nd_of_a_pixel_is_reduced_to_a_16th_and_encodes_as_32769():
    # The review's vector: a raw depth of 1/32 px goes through #97's
    # reduction, which rounds half up to 1/16, then through the encoding.
    covered = np.ones((1, 1), dtype=bool)
    normal = np.zeros((2, 2, 3), dtype=np.float32)
    normal[..., 2] = 1.0
    depth = np.full((2, 2), 1 / 32, dtype=np.float32)
    _, reduced = imageops.reduce_normal_depth(normal, depth, covered, 2, 1.0)
    assert reduced[0, 0] == 1 / 16
    assert tuple(export.encode_depth(reduced.ravel())) == (32769,)


@pytest.mark.parametrize("bad", [2048.0, -2048.0, float("nan"), float("inf")])
def test_encode_depth_refuses_what_it_cannot_hold(bad):
    with pytest.raises(ValueError):
        export.encode_depth([bad])


@pytest.mark.parametrize("beyond", [LIMIT + 0.0625, -LIMIT - 0.0625])
def test_a_depth_one_step_beyond_either_end_is_an_overflow(beyond):
    def depth_of(address, rng):
        values = np.full((3, 2), 7.0)
        if (address.clip, address.direction) == ("攻撃", 1):
            values[0, 0] = beyond
        return values

    with pytest.raises(export.DepthOverflow) as raised:
        encode(side_frames(depth_of))
    error = raised.value
    assert error.exit_code == 4
    lines = str(error).splitlines()
    assert lines[0] == (
        "the subject's depth overflows the depth map at 24.5 pixels per meter: "
        "it holds -2047.9375 to +2047.9375 sheet pixels, and depth is never "
        "clamped or rescaled; give a smaller --ppm:"
    )
    low, high = sorted((7.0, beyond))
    assert lines[1:] == [
        f"  clip '攻撃', direction 1, time {t!r} s: {low!r} to {high!r} px"
        for t in SIDE_TIMES["攻撃"]
    ]
    assert [address.time_s for address, _ in error.frames] == SIDE_TIMES["攻撃"]


def test_a_transparent_pixel_s_depth_is_never_checked():
    def depth_of(address, rng):
        return np.full((3, 2), 1e9)

    frames = side_frames(depth_of)
    for frame in frames:
        frame.pixels[..., 3] = 0
    assert decoded(encode(frames).depth).max() == 0


def test_without_depth_nothing_is_checked_or_encoded():
    frames = side_frames(lambda address, rng: np.full((3, 2), 1e9))
    sheet = encode(frames, depth=False)
    document = json.loads(sheet.json)
    assert sheet.depth is None
    assert document["maps"]["depth"] is None
    assert document["settings"]["depth"] is False


def test_the_record_and_the_fingerprint():
    frames = side_frames(grid_depths)
    on, off = (
        json.loads(encode(frames).json),
        json.loads(encode(frames, depth=False).json),
    )
    assert on["maps"] == {
        "normal": {"file": "héros.normal.png"},
        "depth": {"file": "héros.depth.png"},
    }
    keys = list(on["settings"])
    assert keys[keys.index("normals") + 1] == "depth"
    assert on["settings"]["depth"] is True
    assert on["fingerprint"] != off["fingerprint"]
    assert {
        k: v for k, v in on.items() if k not in ("maps", "settings", "fingerprint")
    } == {k: v for k, v in off.items() if k not in ("maps", "settings", "fingerprint")}
    assert export.depth_path("out/hero.png").as_posix() == "out/hero.depth.png"


# The command


def deep(setup, meters):
    """Every captured pixel at `meters` toward the viewer."""
    setup.configure(depths=[meters])


def test_depth_writes_the_map_beside_the_sheet(setup, capsys):
    deep(setup, 0.25)
    assert run(capsys, setup.argv("--depth"))[0] == 0
    assert "hero.depth.png" in setup.listing()
    document = json.loads(setup.json.read_text())
    assert document["maps"]["depth"] == {"file": "hero.depth.png"}
    assert document["settings"]["depth"] is True
    codes = decoded((setup.out / "hero.depth.png").read_bytes())
    colour = decoded(setup.png.read_bytes())
    ppm = document["settings"]["pixels_per_meter"]
    expected = 32768 + int(np.floor(16 * float(np.float32(0.25)) * ppm + 0.5))
    assert (codes[colour[..., 3] == 255] == expected).all()
    assert (codes[colour[..., 3] == 0] == 0).all()


def test_depth_without_normals_or_previews(setup, capsys):
    # Independent settings: the review's addition.
    assert run(capsys, setup.argv("--depth", "--no-normals", "--no-preview"))[0] == 0
    assert sorted(setup.listing()) == ["hero.depth.png", "hero.json", "hero.png"]
    document = json.loads(setup.json.read_text())
    assert document["maps"] == {"normal": None, "depth": {"file": "hero.depth.png"}}


def test_off_by_default_writes_none_and_keeps_an_earlier_map(setup, capsys):
    earlier = earlier_outputs(setup, "hero.depth.png")
    assert run(capsys, setup.argv())[0] == 0
    assert setup.listing()["hero.depth.png"] == earlier["hero.depth.png"]
    document = json.loads(setup.json.read_text())
    assert document["maps"]["depth"] is None
    assert document["settings"]["depth"] is False


def test_a_subject_far_deeper_than_its_cell_overflows_with_nothing_published(
    setup, capsys
):
    # A 16×16 cell fitted to a subject 0.75 m tall, 200 m deep: thousands of
    # sheet pixels toward the viewer.
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.depth.png")
    deep(setup, 200.0)
    status, out, err = run(capsys, setup.argv("--depth"))
    assert (status, out) == (4, "")
    lines = err.splitlines()
    assert lines[0].startswith("moskophoros: error: the subject's depth overflows")
    assert "-2047.9375 to +2047.9375 sheet pixels" in lines[0]
    assert lines[0].endswith("give a smaller --ppm:")
    assert lines[1].startswith("  clip 'walk', direction 0, time 0.0 s: ")
    assert len(lines) == 1 + (4 + 3) * 8
    assert setup.listing() == earlier


def test_without_the_map_that_subject_is_not_checked(setup, capsys):
    deep(setup, 200.0)
    assert run(capsys, setup.argv())[0] == 0
    assert run(capsys, setup.argv("--no-depth"))[0] == 0
    assert "hero.depth.png" not in setup.listing()


def test_depth_and_no_depth_together_are_refused(setup, capsys, monkeypatch):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--depth", "--no-depth"))
    assert status == 2
    assert "--depth and --no-depth cannot be given together" in err


@pytest.mark.parametrize("text", ["depth: yes", "depth: 1", "depth: null"])
def test_a_bad_depth_value_in_a_file_names_the_file_key_and_line(
    setup, capsys, tmp_path, monkeypatch, text
):
    path = tmp_path / "bad.yaml"
    path.write_text("version: 1\n" + text + "\n")
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--config", str(path)))
    assert status == 2
    assert f"--config {str(path)!r}: depth: expected true or false" in err
    assert "at line 2" in err


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


def test_no_depth_drops_a_reused_or_configured_true(setup, capsys, tmp_path):
    deep(setup, 0.5)
    assert run(capsys, setup.argv("--depth"))[0] == 0
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    (setup.out / "hero.depth.png").unlink()
    assert run(capsys, reload(setup, sheet, "--no-depth"))[0] == 0
    assert "hero.depth.png" not in setup.listing()
    assert json.loads(setup.json.read_text())["settings"]["depth"] is False
    on = tmp_path / "on.yaml"
    on.write_text("depth: true\n")
    assert run(capsys, setup.argv("--config", str(on), "--no-depth"))[0] == 0
    assert "hero.depth.png" not in setup.listing()
    assert run(capsys, setup.argv("--config", str(on)))[0] == 0
    assert "hero.depth.png" in setup.listing()


def test_a_sheet_with_depth_reproduces_it_byte_for_byte(setup, capsys, tmp_path):
    setup.configure(depths=[0.5, -0.25, 0.0])
    assert run(capsys, setup.argv("--depth"))[0] == 0
    first = setup.listing()
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(first["hero.json"])
    for name in list(first):
        (setup.out / name).unlink()
    assert run(capsys, reload(setup, sheet))[0] == 0
    assert setup.listing() == first


def test_the_map_is_named_in_an_output_error(setup, capsys, monkeypatch):
    earlier = earlier_outputs(setup, "hero.png", "hero.json")
    real_open = open

    def staged_open(path, mode="r", *args, **kwargs):
        if "x" in mode and str(path).split("/")[-1].startswith(
            ".hero.depth.png.moskophoros-new-"
        ):
            raise PermissionError(13, "Permission denied", str(path))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(cli, "open", staged_open, raising=False)
    status, _, err = run(capsys, setup.argv("--depth"))
    assert status == 6
    assert f"cannot write {str(setup.out / 'hero.depth.png')!r}" in err
    assert setup.listing() == earlier


def test_a_failed_rename_rolls_the_depth_map_back_with_the_rest(
    setup, capsys, monkeypatch
):
    import os

    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.depth.png")
    real = os.replace
    calls = []

    def replace(source, target):
        calls.append(target)
        # Fail on the last publication rename, after the depth map is placed.
        if str(target).endswith("hero.walk.gif"):
            raise OSError(16, "Device or resource busy")
        return real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    status, _, err = run(capsys, setup.argv("--depth"))
    assert status == 6
    assert any(str(target).endswith("hero.depth.png") for target in calls)
    assert setup.listing() == earlier
