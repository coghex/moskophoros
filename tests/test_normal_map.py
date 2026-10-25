"""The normal map: written on every run unless turned off, recorded in the
sheet's JSON and reproduced by `--settings-from` (design §Export, §CLI,
§Settings files; lighting sheet design D-2, D-9, D-17, D-18, D-26)."""

import io
import json
import math

import numpy as np
import pytest
import sheet_encoding
from PIL import Image
from test_command import BACKEND, Setup, earlier_outputs, run
from test_export import GENERATOR, PLAIN, POSE, RANGE, RUN, SIDE, SOURCE, STRIKE
from test_export import TIMES as SIDE_TIMES
from test_materials_command import forbid_blender, materialed, named_hero

from moskophoros import export, imageops, publication
from moskophoros.sampling import NORMAL_MAP, FrameAddress, ImageFrame

UP = (128, 128, 255, 255)


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def decoded(png):
    with Image.open(io.BytesIO(png)) as image:
        assert (image.mode, image.format) == ("RGBA", "PNG")
        return np.asarray(image)


# The map, from export.encode


def side_frames(seed=0):
    """The export tests' side sheet frames (2×3 cells), each with partial
    coverage and its own random unit normals."""
    rng = np.random.default_rng(seed)
    frames = []
    for clip, times in SIDE_TIMES.items():
        for direction in (0, 1):
            for time_s in times:
                pixels = rng.integers(0, 256, (3, 2, 4), dtype=np.uint8)
                pixels[..., 3] = np.where(rng.random((3, 2)) < 0.6, 255, 0)
                normals = rng.normal(size=(3, 2, 3))
                normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
                normals[pixels[..., 3] == 0] = 0.0
                address = FrameAddress("héros", "default", clip, direction, time_s)
                frames.append(
                    ImageFrame(address, pixels, buffers={NORMAL_MAP: normals})
                )
    return frames


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
    } | changes
    return sheet_encoding.encode(frames, **arguments)


def test_the_map_has_the_sheet_s_size_layout_and_alpha():
    frames = side_frames()
    sheet = encode(frames)
    colour, normal = decoded(sheet.png), decoded(sheet.normal)
    assert normal.shape == colour.shape
    np.testing.assert_array_equal(normal[..., 3], colour[..., 3])
    assert (normal[colour[..., 3] == 0] == 0).all()
    # Each frame's normals sit at its own cell, encoded.
    document = json.loads(sheet.json)
    by_address = {
        (f.address.clip, f.address.direction, f.address.time_s): f for f in frames
    }
    for entry in document["frames"]:
        frame = by_address[(entry["clip"], entry["direction"], entry["time_s"])]
        place = sheet_encoding.cell(document, entry, "normal")
        x, y = place["x"], place["y"]
        cell = normal[y : y + place["h"], x : x + place["w"]]
        covered = frame.pixels[..., 3] == 255
        np.testing.assert_array_equal(
            cell[covered, :3],
            imageops.encode_normal(frame.buffers[NORMAL_MAP][covered]),
        )


def test_the_encoded_bytes_decode_back_within_the_encoding_s_step():
    frames = side_frames(3)
    normal = decoded(encode(frames).normal)
    colour = decoded(encode(frames).png)
    document = json.loads(encode(frames).json)
    worst = 0.0
    for entry, frame in zip(document["frames"], frames, strict=True):
        assert (entry["clip"], entry["direction"], entry["time_s"]) == (
            frame.address.clip,
            frame.address.direction,
            frame.address.time_s,
        )
        place = sheet_encoding.cell(document, entry, "normal")
        x, y = place["x"], place["y"]
        cell = normal[y : y + place["h"], x : x + place["w"]]
        covered = colour[y : y + place["h"], x : x + place["w"], 3]
        back = 2 * cell[..., :3].astype(np.float64) / 255 - 1
        error = np.abs(back - frame.buffers[NORMAL_MAP])[covered == 255]
        worst = max(worst, float(error.max(initial=0.0)))
    # Half a step of 2/255 either way.
    assert 0 < worst <= 1 / 255 + 1e-12


def test_a_pixel_facing_the_viewer_is_128_128_255():
    frames = side_frames()
    for frame in frames:
        frame.pixels[..., 3] = 255
        frame.buffers[NORMAL_MAP][...] = (0.0, 0.0, 1.0)
    normal = decoded(encode(frames).normal)
    covered = normal[..., 3] == 255
    assert covered.sum() == len(frames) * 6
    assert (normal[covered] == UP).all() and (normal[~covered] == 0).all()


def test_the_map_png_has_no_text_or_time_chunks():
    data = encode(side_frames()).normal
    chunks, at = [], 8
    while at < len(data):
        length = int.from_bytes(data[at : at + 4])
        chunks.append(data[at + 4 : at + 8])
        at += 12 + length
    assert set(chunks) <= {b"IHDR", b"IDAT", b"IEND"}


def test_without_normals_no_map_is_encoded_and_none_is_needed():
    frames = [ImageFrame(f.address, f.pixels) for f in side_frames()]
    sheet = encode(frames, normals=False)
    document = json.loads(sheet.json)
    assert sheet.normal is None
    assert sheet_encoding.path_of(document, "sheet", "normal") is None
    assert [a["channel"] for a in document["artifacts"] if a["kind"] == "sheet"] == [
        "color"
    ]
    assert document["settings"]["normals"] is False
    with pytest.raises(ValueError, match="normal map"):
        encode(frames)


def test_the_map_is_an_artifact_and_the_flag_is_fingerprinted():
    on = json.loads(encode(side_frames()).json)
    off = json.loads(encode(side_frames(), normals=False).json)
    keys = list(on)
    assert keys[keys.index("fingerprint") + 1] == "artifacts"
    assert sheet_encoding.path_of(on, "sheet", "normal") == "héros.normal.png"
    assert sheet_encoding.path_of(on, "sheet", "depth") is None
    assert on["fingerprint"] != off["fingerprint"]
    for document in (on, off):
        assert document["fingerprint"] == export.fingerprint(
            document["generator"], document["settings"], document["source"]["sha256"]
        )


def test_the_map_s_path_is_beside_the_sheet():
    assert export.normal_path("out/hero.png").as_posix() == "out/hero.normal.png"
    assert export.normal_path("a.b.png").name == "a.b.normal.png"


# The command


def listing(setup):
    return sorted(setup.listing())


def map_of(setup):
    return decoded((setup.out / "hero.normal.png").read_bytes())


def test_a_run_writes_the_map_beside_the_sheet(setup, capsys):
    setup.configure(surfaces="varied")
    assert run(capsys, setup.argv())[0] == 0
    colour, normal = decoded(setup.png.read_bytes()), map_of(setup)
    assert normal.shape == colour.shape
    np.testing.assert_array_equal(normal[..., 3], colour[..., 3])
    document = json.loads(setup.json.read_text())
    assert sheet_encoding.path_of(document, "sheet", "normal") == "hero.normal.png"
    assert document["settings"]["normals"] is True
    # D-26: the capture reports no fixed parameter for normal and depth.
    assert document["generator"]["shade"] == BACKEND["shade"]


@pytest.mark.parametrize(
    "how", ["option", "config", "user"], ids=["--no-normals", "--config", "user file"]
)
def test_turned_off_writes_none_records_null_and_keeps_an_earlier_map(
    setup, capsys, tmp_path, monkeypatch, how
):
    earlier = earlier_outputs(setup, "hero.normal.png")
    if how == "option":
        args = ["--no-normals"]
    else:
        path = tmp_path / "off.yaml"
        path.write_text("normals: false\n")
        if how == "config":
            args = ["--config", str(path)]
        else:
            home = tmp_path / "xdg"
            (home / "moskophoros").mkdir(parents=True)
            path.rename(home / "moskophoros" / "config.yaml")
            monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
            args = []
    assert run(capsys, setup.argv(*args))[0] == 0
    after = setup.listing()
    assert after["hero.normal.png"] == earlier["hero.normal.png"]
    document = json.loads(setup.json.read_text())
    assert sheet_encoding.path_of(document, "sheet", "normal") is None
    assert document["settings"]["normals"] is False


def test_normals_and_no_normals_together_are_refused(setup, capsys, monkeypatch):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--normals", "--no-normals"))
    assert status == 2
    assert "--normals and --no-normals cannot be given together" in err


@pytest.mark.parametrize("text", ["normals: yes", "normals: 1", "normals: null"])
def test_a_bad_normals_value_in_a_file_names_the_file_key_and_line(
    setup, capsys, tmp_path, monkeypatch, text
):
    path = tmp_path / "bad.yaml"
    path.write_text("version: 1\n" + text + "\n")
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--config", str(path)))
    assert status == 2
    assert f"--config {str(path)!r}: normals: expected true or false" in err
    assert "at line 2" in err


def reload(setup, sheet, *options, outfile=None):
    return [
        "--settings-from",
        str(sheet),
        "--no-user-config",
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(setup.png if outfile is None else outfile),
    ]


def recorded(setup, capsys, *options):
    setup.configure(surfaces="varied")
    assert run(capsys, setup.argv(*options))[0] == 0
    sheet = setup.tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    return sheet


def test_normals_over_a_reused_or_configured_false_writes_the_map(
    setup, capsys, tmp_path
):
    sheet = recorded(setup, capsys, "--no-normals")
    assert json.loads(sheet.read_text())["settings"]["normals"] is False
    assert "hero.normal.png" not in setup.listing()
    assert run(capsys, reload(setup, sheet, "--normals"))[0] == 0
    assert json.loads(setup.json.read_text())["settings"]["normals"] is True
    assert "hero.normal.png" in setup.listing()
    (setup.out / "hero.normal.png").unlink()
    off = tmp_path / "off.yaml"
    off.write_text("normals: false\n")
    assert run(capsys, setup.argv("--config", str(off), "--normals"))[0] == 0
    assert "hero.normal.png" in setup.listing()


@pytest.mark.parametrize("options", [(), ("--no-normals",)], ids=["on", "off"])
def test_reloading_a_sheet_reproduces_the_map_byte_for_byte(setup, capsys, options):
    sheet = recorded(setup, capsys, *options)
    first = setup.listing()
    for name in list(first):
        (setup.out / name).unlink()
    assert run(capsys, reload(setup, sheet))[0] == 0
    assert setup.listing() == first
    assert ("hero.normal.png" in first) is (not options)


def test_a_document_of_only_schema_and_settings_no_longer_loads(setup, capsys):
    """Reuse validates the whole manifest: settings alone, which the earlier
    schema accepted, are refused before Blender and nothing is written."""
    sheet = recorded(setup, capsys)
    first = setup.listing()
    document = json.loads(sheet.read_text())
    minimal = setup.tmp_path / "minimal.json"
    minimal.write_text(
        json.dumps({"schema": document["schema"], "settings": document["settings"]})
    )
    for name in list(first):
        (setup.out / name).unlink()
    status, _, err = run(capsys, reload(setup, minimal))
    assert status == 2
    assert "generator: missing" in err and "fingerprint: missing" in err
    assert setup.listing() == {}


def test_reuse_with_another_output_name_names_its_own_map(setup, capsys):
    sheet = recorded(setup, capsys)
    other = setup.out / "other.png"
    assert run(capsys, reload(setup, sheet, outfile=other))[0] == 0
    document = json.loads((setup.out / "other.json").read_text())
    assert sheet_encoding.path_of(document, "sheet", "normal") == "other.normal.png"
    assert (setup.out / "other.normal.png").read_bytes() == (
        setup.out / "hero.normal.png"
    ).read_bytes()


def test_the_map_is_named_in_an_output_error(setup, capsys, monkeypatch):
    earlier = earlier_outputs(setup, "hero.png", "hero.json")
    real_open = open

    def staged_open(path, mode="r", *args, **kwargs):
        if "x" in mode and str(path).split("/")[-1].startswith(
            ".hero.normal.png.moskophoros-new-"
        ):
            raise PermissionError(13, "Permission denied", str(path))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(publication, "open", staged_open, raising=False)
    status, _, err = run(capsys, setup.argv())
    assert status == 6
    assert f"cannot write {str(setup.out / 'hero.normal.png')!r}" in err
    assert setup.listing() == earlier


@pytest.mark.parametrize("reduce", ["plain", "mode"])
def test_the_map_is_the_same_under_a_library(setup, capsys, reduce):
    # The normals do not depend on the look: the library changes colours only.
    named_hero(setup, [{"name": "steel"}, {"name": "cloth"}])
    setup.configure(
        materials=[{"id": 1, "material": 0}, {"id": 2, "material": 1}]
        + [{"id": 65535, "material": None}],
        code=1,
        pixels="solid",
        surfaces="varied",
    )
    assert run(capsys, materialed(setup, "--reduce", reduce))[0] == 0
    with_library = map_of(setup)
    assert run(capsys, setup.argv("--reduce", reduce))[0] == 0
    np.testing.assert_array_equal(map_of(setup), with_library)


def test_the_unit_round_trip_is_within_half_a_step_for_every_byte():
    # Every byte decodes to within half a step of what encodes to it.
    values = np.linspace(-1.0, 1.0, 20001)
    encoded = imageops.encode_normal(np.stack([values] * 3, axis=-1))[:, 0]
    back = 2 * encoded.astype(np.float64) / 255 - 1
    assert np.abs(back - values).max() <= 1 / 255 + 1e-12
    assert math.isclose(2 * 128 / 255 - 1, 1 / 255)
