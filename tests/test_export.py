import hashlib
import io
import platform
import random
import struct
from dataclasses import replace
from pathlib import Path

import numpy as np
import PIL
import pytest
from PIL import Image

import moskophoros
from moskophoros import export, stylize
from moskophoros.capture.backend import Settings, Source
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import FrameAddress, ImageFrame

SHA = "ab" * 32
GENERATOR = {
    "tool": "moskophoros",
    "version": "0.1.0",
    "python": "3.13.15",
    "numpy": "2.5.3",
    "pillow": "12.3.0",
    "blender": "5.2.2",
    "renderer": "workbench",
    "studio_light": "rim.sl",
}

# The described sheet: the `side` view (east, then west), three clips at 3 fps.
SIDE = Settings(
    view="side",
    pitch=0.0,
    directions=2,
    start_angle=90.0,
    model_yaw=0.0,
    fps=3.0,
    supersample=4,
    ppm=24.5,
    cell=(2, 3),
    ground=(0.0, 0.0, 0.0),
    ground_px=(1, 2),
    root_motion="error",
)
RUN = SelectedClip(Clip(0, "läuft", 0.0, 1.0, ()), one_shot=False)
STRIKE = SelectedClip(Clip(1, "攻撃", 0.5, 1.5, ()), one_shot=True)
POSE = SelectedClip(Clip(2, "pose", 0.25, 0.25, ()), one_shot=False)
SOURCE = Source(Path("/work/models/héros.glb"), SHA, 0)

# Sample times worked out by hand from design §Clips and sampling:
# läuft: d = 1, n = floor(1 · 3 + 0.5) = 3 frames at k/3, each 1/3 long.
# 攻撃: d = 1, n = 3, one-shot, so 4 frames at 0.5 + k/3, endpoint included.
# pose: d = 0, so 1 frame at t0 = 0.25 lasting 1/fps.
TIMES = {
    "läuft": [0.0, 0.3333333333333333, 0.6666666666666666],
    "攻撃": [0.5, 0.8333333333333333, 1.1666666666666665, 1.5],
    "pose": [0.25],
}

CANONICAL = (
    '{"generator":{"blender":"5.2.2","numpy":"2.5.3","pillow":"12.3.0",'
    '"python":"3.13.15","renderer":"workbench","studio_light":"rim.sl",'
    '"tool":"moskophoros","version":"0.1.0"},'
    '"settings":{"cell":{"height":3,"width":2},'
    '"clips":[{"loop":true,"name":"läuft"},{"loop":false,"name":"攻撃"},'
    '{"loop":true,"name":"pose"}],'
    '"fps":3.0,"ground_m":{"x":0.0,"y":0.0,"z":0.0},"ground_px":{"x":1,"y":2},'
    '"model_yaw_deg":0.0,"pixels_per_meter":24.5,"root_motion":"error",'
    '"supersample":4,"view":{"directions":2,"pitch_deg":0.0,"preset":"side",'
    '"projection":"orthographic","start_angle_deg":90.0}},'
    '"source":{"sha256":"' + SHA + '"}}'
)
FINGERPRINT = "sha256:" + hashlib.sha256(CANONICAL.encode("utf-8")).hexdigest()


def _frame(clip, direction, time_s, shape, value=0):
    address = FrameAddress("héros", "default", clip, direction, time_s)
    return ImageFrame(address, np.full(shape, value, dtype=np.uint8))


def _side_frames():
    return [
        _frame(clip, direction, time_s, (3, 2, 4))
        for clip, times in TIMES.items()
        for direction in (0, 1)
        for time_s in times
    ]


def _encode_side(frames=None, **changes):
    arguments = {
        "generator": GENERATOR,
        "source": SOURCE,
        "subject": "héros",
        "settings": SIDE,
        "selected_clips": (RUN, STRIKE, POSE),
        "image_path": Path("/tmp/out/héros.png"),
    } | changes
    return export.encode(_side_frames() if frames is None else frames, **arguments)


def _frame_line(clip, direction, index, time_s, x, y):
    return (
        "    {\n"
        f'      "clip": "{clip}",\n'
        f'      "direction": {direction},\n'
        f'      "index": {index},\n'
        f'      "time_s": {time_s},\n'
        f'      "x": {x},\n'
        f'      "y": {y},\n'
        '      "w": 2,\n'
        '      "h": 3\n'
        "    }"
    )


EXPECTED_FRAMES = ",\n".join(
    [
        _frame_line("läuft", 0, 0, "0.0", 0, 0),
        _frame_line("läuft", 0, 1, "0.3333333333333333", 2, 0),
        _frame_line("läuft", 0, 2, "0.6666666666666666", 4, 0),
        _frame_line("läuft", 1, 0, "0.0", 0, 3),
        _frame_line("läuft", 1, 1, "0.3333333333333333", 2, 3),
        _frame_line("läuft", 1, 2, "0.6666666666666666", 4, 3),
        _frame_line("攻撃", 0, 0, "0.5", 0, 6),
        _frame_line("攻撃", 0, 1, "0.8333333333333333", 2, 6),
        _frame_line("攻撃", 0, 2, "1.1666666666666665", 4, 6),
        _frame_line("攻撃", 0, 3, "1.5", 6, 6),
        _frame_line("攻撃", 1, 0, "0.5", 0, 9),
        _frame_line("攻撃", 1, 1, "0.8333333333333333", 2, 9),
        _frame_line("攻撃", 1, 2, "1.1666666666666665", 4, 9),
        _frame_line("攻撃", 1, 3, "1.5", 6, 9),
        _frame_line("pose", 0, 0, "0.25", 0, 12),
        _frame_line("pose", 1, 0, "0.25", 0, 15),
    ]
)

EXPECTED_JSON = (
    """{
  "schema": "moskophoros.sheet/1",
  "generator": {
    "tool": "moskophoros",
    "version": "0.1.0",
    "python": "3.13.15",
    "numpy": "2.5.3",
    "pillow": "12.3.0",
    "blender": "5.2.2",
    "renderer": "workbench",
    "studio_light": "rim.sl"
  },
  "source": {
    "file": "héros.glb",
    "sha256": "@SHA@"
  },
  "subject": "héros",
  "variant": "default",
  "settings": {
    "view": {
      "preset": "side",
      "projection": "orthographic",
      "pitch_deg": 0.0,
      "directions": 2,
      "start_angle_deg": 90.0
    },
    "model_yaw_deg": 0.0,
    "fps": 3.0,
    "supersample": 4,
    "pixels_per_meter": 24.5,
    "cell": {
      "width": 2,
      "height": 3
    },
    "ground_m": {
      "x": 0.0,
      "y": 0.0,
      "z": 0.0
    },
    "ground_px": {
      "x": 1,
      "y": 2
    },
    "root_motion": "error",
    "clips": [
      {
        "name": "läuft",
        "loop": true
      },
      {
        "name": "攻撃",
        "loop": false
      },
      {
        "name": "pose",
        "loop": true
      }
    ]
  },
  "fingerprint": "@FINGERPRINT@",
  "image": {
    "file": "héros.png",
    "width": 8,
    "height": 18
  },
  "directions": [
    {
      "index": 0,
      "angle_deg": 90.0,
      "label": "east"
    },
    {
      "index": 1,
      "angle_deg": 270.0,
      "label": "west"
    }
  ],
  "clips": [
    {
      "name": "läuft",
      "loop": true,
      "duration_s": 1.0,
      "frame_count": 3,
      "frame_duration_s": 0.3333333333333333
    },
    {
      "name": "攻撃",
      "loop": false,
      "duration_s": 1.0,
      "frame_count": 4,
      "frame_duration_s": 0.3333333333333333
    },
    {
      "name": "pose",
      "loop": true,
      "duration_s": 0.0,
      "frame_count": 1,
      "frame_duration_s": 0.3333333333333333
    }
  ],
  "frames": [
@FRAMES@
  ]
}
""".replace("@SHA@", SHA)
    .replace("@FINGERPRINT@", FINGERPRINT)
    .replace("@FRAMES@", EXPECTED_FRAMES)
    .encode("utf-8")
)


def test_the_description_matches_the_expected_document_byte_for_byte():
    assert _encode_side().json == EXPECTED_JSON


def test_the_fingerprint_hashes_the_canonical_mirrored_object():
    settings = {
        "view": {
            "preset": "side",
            "projection": "orthographic",
            "pitch_deg": 0.0,
            "directions": 2,
            "start_angle_deg": 90.0,
        },
        "model_yaw_deg": 0.0,
        "fps": 3.0,
        "supersample": 4,
        "pixels_per_meter": 24.5,
        "cell": {"width": 2, "height": 3},
        "ground_m": {"x": 0.0, "y": 0.0, "z": 0.0},
        "ground_px": {"x": 1, "y": 2},
        "root_motion": "error",
        "clips": [
            {"name": "läuft", "loop": True},
            {"name": "攻撃", "loop": False},
            {"name": "pose", "loop": True},
        ],
    }
    assert export.fingerprint(GENERATOR, settings, SHA) == FINGERPRINT


def test_the_fingerprint_ignores_file_names_and_paths():
    moved = Source(Path("/elsewhere/other-name.glb"), SHA, 3)
    sheet = _encode_side(source=moved, image_path=Path("/x/y/renamed.png"))
    assert f'"fingerprint": "{FINGERPRINT}"'.encode() in sheet.json


@pytest.mark.parametrize(
    "changes",
    [
        {"generator": GENERATOR | {"blender": "5.2.3"}},
        {"generator": GENERATOR | {"studio_light": "basic.sl"}},
        {"generator": GENERATOR | {"pillow": "12.3.1"}},
        {"settings": replace(SIDE, supersample=8)},
        {"settings": replace(SIDE, ppm=24.25)},
        {"settings": replace(SIDE, root_motion="keep")},
        {"source": Source(SOURCE.path, "cd" * 32, 0)},
        {"selected_clips": (RUN, STRIKE, replace(POSE, one_shot=True))},
    ],
    ids=[
        "blender",
        "studio light",
        "pillow",
        "supersample",
        "scale",
        "root motion",
        "source digest",
        "loop",
    ],
)
def test_the_fingerprint_changes_with_any_hashed_input(changes):
    sheet = _encode_side(**changes)
    assert f'"fingerprint": "{FINGERPRINT}"'.encode() not in sheet.json
    assert b'"fingerprint": "sha256:' in sheet.json


def test_the_fingerprint_rejects_a_malformed_digest():
    with pytest.raises(ValueError, match="64 hex"):
        export.fingerprint(GENERATOR, {}, "ABC")


# Layout


def _chunks(png):
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    offset, chunks = 8, []
    while offset < len(png):
        (length,) = struct.unpack(">I", png[offset : offset + 4])
        kind = png[offset + 4 : offset + 8]
        chunks.append((kind, png[offset + 8 : offset + 8 + length]))
        offset += 12 + length
    return chunks


GRID = Settings(
    view="custom",
    pitch=30.0,
    directions=4,
    start_angle=0.0,
    model_yaw=0.0,
    fps=2.0,
    supersample=8,
    ppm=10.0,
    cell=(3, 2),
    ground=(0.0, 0.0, 0.0),
    ground_px=(1, 1),
    root_motion="keep",
)
# At 2 fps, a one-second loop has 2 frames (at 0 and 0.5) and a one-second
# one-shot 3 (at 0, 0.5 and 1).
SHORT = SelectedClip(Clip(0, "short", 0.0, 1.0, ()), one_shot=False)
LONG = SelectedClip(Clip(1, "long", 0.0, 1.0, ()), one_shot=True)
GRID_TIMES = {"short": [0.0, 0.5], "long": [0.0, 0.5, 1.0]}


def _grid_frames():
    frames = []
    for c, (clip, times) in enumerate(GRID_TIMES.items()):
        for d in range(4):
            for k, time_s in enumerate(times):
                pixels = np.empty((2, 3, 4), dtype=np.uint8)
                pixels[:] = (c + 1, d + 1, k + 1, 255)
                address = FrameAddress("grid", "default", clip, d, time_s)
                frames.append(ImageFrame(address, pixels))
    return frames


def _encode_grid(frames):
    return export.encode(
        frames,
        generator=GENERATOR,
        source=Source(Path("/m/grid.glb"), SHA, 0),
        subject="grid",
        settings=GRID,
        selected_clips=(SHORT, LONG),
        image_path="grid.png",
    )


def test_cells_are_placed_by_clip_direction_and_index_with_transparent_gaps():
    frames = _grid_frames()
    random.Random(4).shuffle(frames)
    sheet = _encode_grid(frames)
    image = np.array(Image.open(io.BytesIO(sheet.png)))
    # 3 columns (the longest clip) of 3 pixels; 2 clips × 4 directions rows
    # of 2 pixels.
    assert image.shape == (16, 9, 4)
    expected = np.zeros((16, 9, 4), dtype=np.uint8)
    for c, times in enumerate(GRID_TIMES.values()):
        for d in range(4):
            for k in range(len(times)):
                x, y = 3 * k, 2 * (4 * c + d)
                expected[y : y + 2, x : x + 3] = (c + 1, d + 1, k + 1, 255)
    assert np.array_equal(image, expected)
    # The short clip's third column is unused in each of its four rows.
    assert not image[0:8, 6:9].any()


def test_frames_are_described_in_sheet_order_whatever_the_input_order():
    ordered = _encode_grid(_grid_frames())
    frames = _grid_frames()
    frames.reverse()
    assert _encode_grid(frames) == ordered


def test_the_png_is_8_bit_rgba_without_text_or_time_chunks():
    chunks = _chunks(_encode_side().png)
    kinds = [kind for kind, _ in chunks]
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND"
    assert set(kinds) <= {b"IHDR", b"IDAT", b"IEND"}
    width, height, depth, color_type = struct.unpack(">IIBB", chunks[0][1][:10])
    assert (width, height, depth, color_type) == (8, 18, 8, 6)


def test_two_exports_of_the_same_inputs_are_byte_identical():
    first, second = _encode_side(), _encode_side()
    assert first.png == second.png
    assert first.json == second.json


def test_the_static_clip_is_one_frame_at_zero():
    static = SelectedClip(Clip(None, "static", 0.0, 0.0, ()), one_shot=False)
    settings = replace(SIDE, fps=12.0, directions=1, view="custom")
    frame = ImageFrame(
        FrameAddress("box", "default", "static", 0, 0.0),
        np.zeros((3, 2, 4), dtype=np.uint8),
    )
    sheet = export.encode(
        [frame],
        generator=GENERATOR,
        source=Source(Path("/m/box.glb"), SHA, 0),
        subject="box",
        settings=settings,
        selected_clips=(static,),
        image_path="box.png",
    )
    text = sheet.json.decode()
    assert (
        '  "clips": [\n'
        "    {\n"
        '      "name": "static",\n'
        '      "loop": true,\n'
        '      "duration_s": 0.0,\n'
        '      "frame_count": 1,\n'
        '      "frame_duration_s": 0.08333333333333333\n'
        "    }\n"
        "  ],\n"
    ) in text
    assert '"time_s": 0.0,' in text
    assert '"width": 2,\n    "height": 3\n' in text


# Rejected frames


def _without(frames, clip, direction, time_s):
    return [
        f
        for f in frames
        if (f.address.clip, f.address.direction, f.address.time_s)
        != (clip, direction, time_s)
    ]


@pytest.mark.parametrize(
    ("frames", "match"),
    [
        (_without(_side_frames(), "攻撃", 1, 1.5), "missing"),
        ([], "missing"),
        (_side_frames() + [_frame("läuft", 0, 0.5, (3, 2, 4))], "unrequested"),
        (_side_frames() + [_frame("läuft", 2, 0.0, (3, 2, 4))], "unrequested"),
        (_side_frames() + [_frame("other", 0, 0.0, (3, 2, 4))], "unrequested"),
        (_side_frames() + [_frame("pose", 0, 0.25, (3, 2, 4))], "two frames"),
        (
            _without(_side_frames(), "pose", 0, 0.25)
            + [_frame("pose", 0, 0.25, (2, 3, 4))],
            "not uint8",
        ),
        (
            _without(_side_frames(), "pose", 0, 0.25)
            + [_frame("pose", 0, 0.25, (6, 4, 4))],
            "not uint8",
        ),
        (
            _without(_side_frames(), "pose", 0, 0.25)
            + [_frame("pose", 0, 0.25, (3, 2, 3))],
            "not uint8",
        ),
    ],
    ids=[
        "one missing",
        "none",
        "an extra time",
        "an extra direction",
        "an extra clip",
        "a duplicate",
        "transposed",
        "supersampled",
        "three channels",
    ],
)
def test_wrong_frames_are_rejected(frames, match):
    with pytest.raises(ValueError, match=match):
        _encode_side(frames)


def test_a_frame_of_another_dtype_is_rejected():
    frames = _without(_side_frames(), "pose", 1, 0.25)
    address = FrameAddress("héros", "default", "pose", 1, 0.25)
    frames.append(ImageFrame(address, np.zeros((3, 2, 4), dtype=np.float32)))
    with pytest.raises(ValueError, match="float32"):
        _encode_side(frames)


def test_unfitted_settings_are_rejected():
    with pytest.raises(ValueError, match="not fitted"):
        _encode_side(settings=replace(SIDE, cell=None))


# Generator and writing


def test_the_generator_records_this_tool_and_the_render_provenance():
    backend = {"blender": "5.2.2", "renderer": "workbench", "studio_light": "rim.sl"}
    assert export.generator(backend) == {
        "tool": "moskophoros",
        "version": moskophoros.__version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pillow": PIL.__version__,
        "blender": "5.2.2",
        "renderer": "workbench",
        "studio_light": "rim.sl",
    }
    assert list(export.generator(backend)) == list(GENERATOR)


def test_the_generator_needs_render_provenance():
    with pytest.raises(ValueError, match="renderer, studio_light"):
        export.generator({"blender": "5.2.2"})


def test_write_puts_the_bytes_at_the_given_paths(tmp_path):
    sheet = _encode_side()
    png, json_path = tmp_path / "a" / "sheet.png", tmp_path / "b.json"
    png.parent.mkdir()
    export.write(sheet, png, json_path)
    assert png.read_bytes() == sheet.png
    assert json_path.read_bytes() == sheet.json
    assert sorted(p.name for p in tmp_path.rglob("*")) == ["a", "b.json", "sheet.png"]


def test_stylized_frames_export_directly():
    supersampled = [
        ImageFrame(frame.address, np.full((6, 4, 4), 200, dtype=np.uint8), {"k": 1})
        for frame in _side_frames()
    ]
    plain = stylize.plain(supersampled, 2)
    image = np.array(Image.open(io.BytesIO(_encode_side(plain).png)))
    assert (image == (200, 200, 200, 255)).all(axis=2)[:, :2].all()
