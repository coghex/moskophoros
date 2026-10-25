import hashlib
import io
import json
import platform
import random
import struct
from dataclasses import replace
from pathlib import Path

import numpy as np
import PIL
import pytest
import sheet_encoding
from manifest_fixture import GENERATOR
from PIL import Image
from shading import DEFAULT_SHADE

import moskophoros
from moskophoros import export, stylize, views
from moskophoros.capture.backend import Settings, Shade, Source, settings_document
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import NORMAL_MAP, FrameAddress, ImageFrame

SHA = "ab" * 32
# The described sheet: the `side` view (east, then west), three clips at 3 fps.
SIDE = Settings(
    view="side",
    direction=views.pitch_direction(0.0),
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
    shade=DEFAULT_SHADE,
)
RUN = SelectedClip(Clip(0, "läuft", 0.0, 1.0, ()), one_shot=False)
STRIKE = SelectedClip(Clip(1, "攻撃", 0.5, 1.5, ()), one_shot=True)
POSE = SelectedClip(Clip(2, "pose", 0.25, 0.25, ()), one_shot=False)
SOURCE = Source(Path("/work/models/héros.glb"), SHA, 0)
PLAIN = {
    "reduce": "plain",
    "edges": "hard",
    "palette": None,
    "materials": None,
}
RANGE = (84, 191)
# The default `settings.shade` of a sheet, in the order it is recorded
# (shading design contract 1), the key direction as `views.normalise` gives it.
SHADE_RECORD = {
    "ao_distance_m": 0.3,
    "ao_samples": 64,
    "occlusion_weight": 0.25,
    "convexity_weight": 1.0,
    "range": [84, 191],
    "mode": "ramp",
    "ambient_form": True,
    "key": {
        "direction": [-0.5183210553488161, 0.604707897906952, 0.604707897906952],
        "strength": 0.0,
    },
    "sky": {"strength": 0.0},
    "ground": {"strength": 0.0},
    "sky_ground_frame": "camera",
    "brightness": {"floor": 0.3, "ceiling": 1.0},
    "snap": "off",
    "dither": {"pattern": "off", "strength": 1.0},
}

# Sample times worked out by hand from design §Clips and sampling:
# läuft: d = 1, n = floor(1 · 3 + 0.5) = 3 frames at k/3, each 1/3 long.
# 攻撃: d = 1, n = 3, one-shot, so 4 frames at 0.5 + k/3, endpoint included.
# pose: d = 0, so 1 frame at t0 = 0.25 lasting 1/fps.
TIMES = {
    "läuft": [0.0, 0.3333333333333333, 0.6666666666666666],
    "攻撃": [0.5, 0.8333333333333333, 1.1666666666666665, 1.5],
    "pose": [0.25],
}

# The `settings` object the side sheet records (design P-8a), in order: the
# export arc's members are at their inactive defaults.
SETTINGS_RECORD = {
    "view": {"preset": "side", "directions": 2, "start_angle_deg": 90.0},
    "camera": {
        "projection": "orthographic",
        "direction": [0.0, 0.0, -1.0],
        "roll": 0.0,
        "position": None,
    },
    "model_yaw_deg": 0.0,
    "fps": 3.0,
    "frames": "auto",
    "supersample": 4,
    "pixels_per_meter": 24.5,
    "cell": {"width": 2, "height": 3},
    "ground_m": {"x": 0.0, "y": 0.0, "z": 0.0},
    "ground_px": {"x": 1, "y": 2},
    "root_motion": "error",
    "previews": True,
    "normals": True,
    "depth": False,
    "light": {"position": None, "intensity": 1.0, "ambient": 0.3},
    "shade": SHADE_RECORD,
    "ramp": {"lightness_step": 0.12, "hue_shift_deg": -12.0, "chroma_fade": 0.3},
    "style": PLAIN,
    "stored_directions": "all",
    "direction_names": [],
    "mirrors": [],
    "export": {
        "formats": ["sheet"],
        "frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
        "atlas_path": "atlases/{clip}{map}.png",
        "sheet_path": "sheet{map}.png",
        "atlas_padding": 0,
    },
    "clips": [
        {
            "name": name,
            "loop": loop,
            "frames": None,
            "fps": None,
            "stored_directions": None,
            "mirrors": None,
            "output_name": None,
        }
        for name, loop in (("läuft", True), ("攻撃", False), ("pose", True))
    ],
}
# The fingerprint is the hash of the canonical form of the generator, the
# settings and the source digest: sorted keys, no whitespace, non-ASCII kept.
CANONICAL = json.dumps(
    {
        "generator": GENERATOR,
        "settings": SETTINGS_RECORD,
        "source": {"sha256": SHA},
    },
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
FINGERPRINT = "sha256:" + hashlib.sha256(CANONICAL.encode("utf-8")).hexdigest()


def _facing(height, width):
    """A reduced normal map facing the viewer everywhere."""
    normals = np.zeros((height, width, 3))
    normals[..., 2] = 1.0
    return {NORMAL_MAP: normals}


def _frame(clip, direction, time_s, shape, value=0):
    address = FrameAddress("héros", "default", clip, direction, time_s)
    pixels = np.full(shape, value, dtype=np.uint8)
    return ImageFrame(address, pixels, buffers=_facing(*shape[:2]))


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
        "style": PLAIN,
        "shade_range": RANGE,
        "selected_clips": (RUN, STRIKE, POSE),
        "image_path": Path("/tmp/out/héros.png"),
    } | changes
    return sheet_encoding.encode(
        _side_frames() if frames is None else frames, **arguments
    )


def _frame_entry(clip, direction, index, time_s, x, y):
    """A sample's record: its cell in the sheet's colour map (artifact 0) and
    in its normal map (artifact 1)."""
    return {
        "clip": clip,
        "direction": direction,
        "index": index,
        "time_s": time_s,
        "locations": [
            {"artifact": artifact, "x": x, "y": y, "w": 2, "h": 3}
            for artifact in (0, 1)
        ],
    }


def _clip_record(name, loop, duration, count, frame_duration, output_name):
    return {
        "name": name,
        "loop": loop,
        "duration_s": duration,
        "frame_count": count,
        "frame_duration_s": frame_duration,
        "time_scale": 1.0,
        "output_name": output_name,
        "fps": 3.0,
        "stored_directions": [0, 1],
        "mirrors": [],
    }


def _preview_record(path, clip):
    return {
        "kind": "preview",
        "channel": "flat",
        "path": path,
        "width": 16,
        "height": 12,
        "clip": clip,
    }


def _sheet_record(channel, path):
    return {
        "kind": "sheet",
        "channel": channel,
        "path": path,
        "width": 8,
        "height": 18,
        "padding": 0,
        "cell": {"width": 2, "height": 3},
    }


# The side sheet is 4 columns (the longest clip, 攻撃) of 2 pixels and 6 rows
# (three clips of two directions) of 3 pixels; its previews show both
# directions side by side at 4 times the size.
EXPECTED = {
    "schema": "moskophoros.export/1",
    "generator": GENERATOR,
    "source": {"file": "héros.glb", "sha256": SHA},
    "subject": "héros",
    "variant": "default",
    "settings": SETTINGS_RECORD,
    "fingerprint": FINGERPRINT,
    "artifacts": [
        _sheet_record("color", "héros.png"),
        _sheet_record("normal", "héros.normal.png"),
        _preview_record("héros.l_uft.gif", "läuft"),
        _preview_record("héros.__.gif", "攻撃"),
        _preview_record("héros.pose.gif", "pose"),
    ],
    "directions": [
        {"index": 0, "angle_deg": 90.0, "label": "east", "output_name": "east"},
        {"index": 1, "angle_deg": 270.0, "label": "west", "output_name": "west"},
    ],
    "clips": [
        _clip_record("läuft", True, 1.0, 3, 0.3333333333333333, "l_uft"),
        _clip_record("攻撃", False, 1.0, 4, 0.3333333333333333, "__"),
        _clip_record("pose", True, 0.0, 1, 0.3333333333333333, "pose"),
    ],
    "frames": [
        _frame_entry("läuft", 0, 0, 0.0, 0, 0),
        _frame_entry("läuft", 0, 1, 0.3333333333333333, 2, 0),
        _frame_entry("läuft", 0, 2, 0.6666666666666666, 4, 0),
        _frame_entry("läuft", 1, 0, 0.0, 0, 3),
        _frame_entry("läuft", 1, 1, 0.3333333333333333, 2, 3),
        _frame_entry("läuft", 1, 2, 0.6666666666666666, 4, 3),
        _frame_entry("攻撃", 0, 0, 0.5, 0, 6),
        _frame_entry("攻撃", 0, 1, 0.8333333333333333, 2, 6),
        _frame_entry("攻撃", 0, 2, 1.1666666666666665, 4, 6),
        _frame_entry("攻撃", 0, 3, 1.5, 6, 6),
        _frame_entry("攻撃", 1, 0, 0.5, 0, 9),
        _frame_entry("攻撃", 1, 1, 0.8333333333333333, 2, 9),
        _frame_entry("攻撃", 1, 2, 1.1666666666666665, 4, 9),
        _frame_entry("攻撃", 1, 3, 1.5, 6, 9),
        _frame_entry("pose", 0, 0, 0.25, 0, 12),
        _frame_entry("pose", 1, 0, 0.25, 0, 15),
    ],
}
EXPECTED_JSON = (json.dumps(EXPECTED, indent=2, ensure_ascii=False) + "\n").encode()


def test_the_description_matches_the_expected_document_byte_for_byte():
    assert _encode_side().json == EXPECTED_JSON


def test_the_description_lists_the_sheet_maps_and_previews_as_artifacts():
    document = _encode_side().document
    assert list(document) == [
        "schema",
        "generator",
        "source",
        "subject",
        "variant",
        "settings",
        "fingerprint",
        "artifacts",
        "directions",
        "clips",
        "frames",
    ]
    assert "image" not in document and "maps" not in document
    # Without the maps and the previews only the colour sheet remains: an
    # output that is off has no entry, not a null.
    bare = _encode_side(normals=False, previews=False).document
    assert [a["path"] for a in bare["artifacts"]] == ["héros.png"]
    assert all(len(f["locations"]) == 1 for f in bare["frames"])


def test_the_fingerprint_hashes_the_canonical_mirrored_object():
    assert export.fingerprint(GENERATOR, SETTINGS_RECORD, SHA) == FINGERPRINT


def test_the_fingerprint_ignores_file_names_and_paths():
    moved = Source(Path("/elsewhere/other-name.glb"), SHA, 3)
    sheet = _encode_side(source=moved, image_path=Path("/x/y/renamed.png"))
    assert f'"fingerprint": "{FINGERPRINT}"'.encode() in sheet.json


@pytest.mark.parametrize(
    "changes",
    [
        {"generator": GENERATOR | {"blender": "5.2.3"}},
        {
            "generator": GENERATOR
            | {"color": GENERATOR["color"] | {"technique": "another"}}
        },
        {"generator": GENERATOR | {"pillow": "12.3.1"}},
        {"settings": replace(SIDE, supersample=8)},
        {"settings": replace(SIDE, ppm=24.25)},
        {"settings": replace(SIDE, root_motion="keep")},
        {"source": Source(SOURCE.path, "cd" * 32, 0)},
        {"selected_clips": (RUN, STRIKE, replace(POSE, one_shot=True))},
        {"style": PLAIN | {"reduce": "mode"}},
    ],
    ids=[
        "blender",
        "colour technique",
        "pillow",
        "supersample",
        "scale",
        "root motion",
        "source digest",
        "loop",
        "style",
    ],
)
def test_the_fingerprint_changes_with_any_hashed_input(changes):
    sheet = _encode_side(**changes)
    assert f'"fingerprint": "{FINGERPRINT}"'.encode() not in sheet.json
    assert b'"fingerprint": "sha256:' in sheet.json


def _record(style=PLAIN, selected=(RUN, STRIKE, POSE), **options):
    return sheet_encoding.settings_record(
        SIDE, "héros", selected, style, shade_range=RANGE, **options
    )


def test_the_fingerprint_covers_the_style_record():
    settings = _record()
    restyled = _record({"reduce": "plain", "palette": []})
    assert export.fingerprint(GENERATOR, settings, SHA) == FINGERPRINT
    assert export.fingerprint(GENERATOR, restyled, SHA) != FINGERPRINT
    unstyled = {key: value for key, value in settings.items() if key != "style"}
    assert export.fingerprint(GENERATOR, unstyled, SHA) != FINGERPRINT
    # The edges rule is inside the fingerprint (alpha design D-9).
    soft = _record(PLAIN | {"edges": "soft"})
    assert soft["style"] == {
        "reduce": "plain",
        "edges": "soft",
        "palette": None,
        "materials": None,
    }
    assert export.fingerprint(GENERATOR, soft, SHA) != FINGERPRINT


@pytest.mark.parametrize("normals", [True, False])
@pytest.mark.parametrize("previews", [True, False])
def test_previews_normals_shade_and_the_style_record_sit_before_the_export_members(
    previews, normals
):
    settings = _record(selected=(RUN,), previews=previews, normals=normals)
    assert list(settings)[-13:] == [
        "root_motion",
        "previews",
        "normals",
        "depth",
        "light",
        "shade",
        "ramp",
        "style",
        "stored_directions",
        "direction_names",
        "mirrors",
        "export",
        "clips",
    ]
    assert settings["style"] == PLAIN
    assert settings["previews"] is previews
    assert settings["normals"] is normals
    assert settings["shade"] == SHADE_RECORD
    assert list(settings["shade"]) == [
        "ao_distance_m",
        "ao_samples",
        "occlusion_weight",
        "convexity_weight",
        "range",
        "mode",
        "ambient_form",
        "key",
        "sky",
        "ground",
        "sky_ground_frame",
        "brightness",
        "snap",
        "dither",
    ]
    assert list(settings["shade"]["key"]) == ["direction", "strength"]
    assert list(settings["shade"]["brightness"]) == ["floor", "ceiling"]
    assert list(settings["shade"]["dither"]) == ["pattern", "strength"]
    # The capture job's values are the manifest's, though the manifest builds
    # its settings on its own and the job holds none of the export members.
    job = settings_document(SIDE, (RUN,))
    capture = {key: value for key, value in job["shade"].items() if key != "materials"}
    rest = {
        k: v for k, v in settings.items() if k in job and k not in ("shade", "clips")
    }
    assert rest == {k: v for k, v in job.items() if k not in ("shade", "clips")}
    assert {k: SHADE_RECORD[k] for k in capture} == capture
    assert [(c["name"], c["loop"], c["frames"]) for c in settings["clips"]] == [
        (c["name"], c["loop"], c["frames"]) for c in job["clips"]
    ]


def test_the_sheet_records_the_shade_values_used_and_fingerprints_them():
    shade = Shade(1.2, 128, 0.5, 0.0)
    sheet = json.loads(
        _encode_side(settings=replace(SIDE, shade=shade), shade_range=(120, 255)).json
    )
    assert sheet["settings"]["shade"] == SHADE_RECORD | {
        "ao_distance_m": 1.2,
        "ao_samples": 128,
        "occlusion_weight": 0.5,
        "convexity_weight": 0.0,
        "range": [120, 255],
    }
    assert "shade_range" not in sheet["settings"]["style"]
    assert sheet["fingerprint"] != json.loads(_encode_side().json)["fingerprint"]
    ranged = json.loads(_encode_side(shade_range=(84, 190)).json)
    assert ranged["fingerprint"] != json.loads(_encode_side().json)["fingerprint"]


def test_the_previews_flag_is_recorded_and_fingerprinted():
    on = json.loads(_encode_side(previews=True).json)
    off = json.loads(_encode_side(previews=False).json)
    assert (on["settings"]["previews"], off["settings"]["previews"]) == (True, False)
    assert on["fingerprint"] != off["fingerprint"]
    assert {k: v for k, v in on["settings"].items() if k != "previews"} == {
        k: v for k, v in off["settings"].items() if k != "previews"
    }


def test_export_records_the_style_record_as_given():
    # The manifest checks the look it records as a settings file's would be,
    # so a different valid look is written and fingerprinted as it is.
    style = {"reduce": "mode", "edges": "soft", "palette": None, "materials": None}
    sheet = _encode_side(style=style)
    description = json.loads(sheet.json)
    assert description["settings"]["style"] == style
    assert description["fingerprint"] == export.fingerprint(
        GENERATOR, _record(style), SHA
    )
    assert description["fingerprint"] != FINGERPRINT
    assert sheet.png == _encode_side().png


def test_a_look_the_manifest_reader_refuses_is_never_written():
    with pytest.raises(ValueError, match="manifest written is invalid"):
        _encode_side(style={})


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
    direction=views.pitch_direction(30.0),
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
    shade=DEFAULT_SHADE,
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
                frames.append(ImageFrame(address, pixels, buffers=_facing(2, 3)))
    return frames


def _encode_grid(frames):
    return sheet_encoding.encode(
        frames,
        generator=GENERATOR,
        source=Source(Path("/m/grid.glb"), SHA, 0),
        subject="grid",
        settings=GRID,
        style=PLAIN,
        shade_range=RANGE,
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
        buffers=_facing(3, 2),
    )
    sheet = sheet_encoding.encode(
        [frame],
        generator=GENERATOR,
        source=Source(Path("/m/box.glb"), SHA, 0),
        subject="box",
        settings=settings,
        style=PLAIN,
        shade_range=RANGE,
        selected_clips=(static,),
        image_path="box.png",
    )
    document = sheet.document
    assert document["clips"] == [
        {
            "name": "static",
            "loop": True,
            "duration_s": 0.0,
            "frame_count": 1,
            "frame_duration_s": 0.08333333333333333,
            "time_scale": 1.0,
            "output_name": "static",
            "fps": 12.0,
            "stored_directions": [0],
            "mirrors": [],
        }
    ]
    assert [f["time_s"] for f in document["frames"]] == [0.0]
    # One cell of 2 by 3 pixels: the sheet, its normal map and the preview.
    assert [
        (a["kind"], a["channel"], a["width"], a["height"])
        for a in document["artifacts"]
    ] == [
        ("sheet", "color", 2, 3),
        ("sheet", "normal", 2, 3),
        ("preview", "flat", 8, 12),
    ]


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


SHADE = {"technique": "cycles-ambient-occlusion", "seed": 0}


def test_the_generator_records_this_tool_and_the_render_provenance():
    backend = {
        "blender": "5.2.2",
        "renderer": "cycles",
        "color": {"technique": "cycles-flat-emission"},
        "shade": SHADE,
    }
    assert export.generator(backend) == {
        "tool": "moskophoros",
        "version": moskophoros.__version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pillow": PIL.__version__,
        "blender": "5.2.2",
        "renderer": "cycles",
        "color": {"technique": "cycles-flat-emission"},
        "shade": SHADE,
    }
    assert list(export.generator(backend)) == list(GENERATOR)


def test_the_generator_needs_render_provenance():
    with pytest.raises(ValueError, match="renderer, color, shade"):
        export.generator({"blender": "5.2.2"})


@pytest.mark.parametrize(
    "change",
    [
        {"technique": "another"},
        {"samples_per_pixel": 2},
        {"seed": 1},
        {"pixel_filter": "GAUSSIAN"},
        {"filter_width_px": 1.5},
    ],
)
def test_a_different_shade_technique_or_parameter_changes_the_fingerprint(change):
    shade = {
        "technique": "cycles-ambient-occlusion",
        "samples_per_pixel": 1,
        "seed": 0,
        "pixel_filter": "BOX",
        "filter_width_px": 0.01,
    }
    backend = {"blender": "5.2.2", "renderer": "cycles", "color": COLOR}
    settings = {"supersample": 2}

    def fingerprint(shade):
        generator = export.generator({**backend, "shade": shade})
        return export.fingerprint(generator, settings, "ab" * 32)

    assert fingerprint(shade) != fingerprint(shade | change)
    assert fingerprint(shade) == fingerprint(dict(shade))


COLOR = {
    "technique": "cycles-flat-emission",
    "samples_per_pixel": 1,
    "seed": 0,
    "pixel_filter": "BOX",
    "filter_width_px": 0.01,
    "min_transparent_bounces": 64,
    "transparent_max_bounces": 64,
    "pass_alpha_threshold": 2.0**-30,
}


@pytest.mark.parametrize(
    "change",
    [
        {"technique": "another"},
        {"samples_per_pixel": 2},
        {"seed": 1},
        {"pixel_filter": "GAUSSIAN"},
        {"filter_width_px": 1.5},
        {"min_transparent_bounces": 0},
        {"transparent_max_bounces": 8},
        {"pass_alpha_threshold": 0.5},
    ],
)
def test_the_colour_record_is_copied_and_fingerprinted(change):
    backend = {"blender": "5.2.2", "renderer": "cycles", "shade": SHADE}

    def fingerprint(color):
        generator = export.generator({**backend, "color": color})
        assert generator["color"] == color and generator["color"] is not color
        return export.fingerprint(generator, {"supersample": 2}, "ab" * 32)

    assert fingerprint(COLOR) != fingerprint(COLOR | change)
    assert fingerprint(COLOR) == fingerprint(dict(COLOR))


def test_stylized_frames_export_directly():
    supersampled = [
        ImageFrame(frame.address, np.full((6, 4, 4), 200, dtype=np.uint8), {"k": 1})
        for frame in _side_frames()
    ]
    plain = stylize.plain(supersampled, 2)
    image = np.array(Image.open(io.BytesIO(_encode_side(plain, normals=False).png)))
    # Every supersample is a surface of alpha 200, so the pixel keeps it.
    assert (image == (200, 200, 200, 200)).all(axis=2)[:, :2].all()
