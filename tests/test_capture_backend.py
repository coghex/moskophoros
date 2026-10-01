import copy
import hashlib
import json
import os
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from moskophoros import fit, sampling, views
from moskophoros.capture.backend import (
    BackendError,
    MalformedJob,
    RootTravel,
    Settings,
    Source,
    build_job,
    canonical_json,
    job_sha256,
    validate_result,
)
from moskophoros.gltf import Clip, Root, SelectedClip

SHA = "ab" * 32
SOURCE = Source(Path("/models/hero.glb"), SHA, 0)
WALK = Clip(0, "walk", 0.25, 0.5, (Root(3, "hips"),))
ATTACK = Clip(1, "attack", 1.0, 1.25, (Root(3, "hips"), Root(7, None)))
CLIPS = (SelectedClip(WALK, one_shot=False), SelectedClip(ATTACK, one_shot=True))
MEASURE_SETTINGS = Settings(
    view="custom",
    pitch=30.0,
    directions=2,
    start_angle=10.0,
    model_yaw=0.0,
    fps=4.0,
    supersample=2,
    ppm=None,
    cell=None,
    ground=(0.0, 0.0, 0.0),
    ground_px=None,
    root_motion="error",
)
RENDER_SETTINGS = replace(MEASURE_SETTINGS, ppm=10.0, cell=(4, 3), ground_px=(2, 2))
VIEW = views.View(30.0, 2, 10.0, 0.0)


def frames(clips=CLIPS):
    return sampling.frames("hero", clips, VIEW, 4.0)


def measure_job(output_dir="/work/measure"):
    return build_job(
        "measure", SOURCE, "hero", MEASURE_SETTINGS, CLIPS, frames(), output_dir
    )


def render_job(output_dir="/work/render"):
    return build_job(
        "render", SOURCE, "hero", RENDER_SETTINGS, CLIPS, frames(), output_dir
    )


def address(clip, direction, time_s):
    return {
        "subject": "hero",
        "variant": "default",
        "clip": clip,
        "direction": direction,
        "time_s": time_s,
    }


# walk: d = 0.25 s at 4 fps, n = 1, looping: 0.25. attack: one-shot: 1.0, 1.25.
# Directions: 10° and 190°.
EXPECTED_FRAMES = [
    {"address": address("walk", 0, 0.25), "index": 0, "angle_deg": 10.0},
    {"address": address("walk", 1, 0.25), "index": 0, "angle_deg": 190.0},
    {"address": address("attack", 0, 1.0), "index": 0, "angle_deg": 10.0},
    {"address": address("attack", 0, 1.25), "index": 1, "angle_deg": 10.0},
    {"address": address("attack", 1, 1.0), "index": 0, "angle_deg": 190.0},
    {"address": address("attack", 1, 1.25), "index": 1, "angle_deg": 190.0},
]
EXPECTED_CLIPS = [
    {
        "animation_index": 0,
        "name": "walk",
        "t0_s": 0.25,
        "t1_s": 0.5,
        "roots": [{"node_index": 3, "node_name": "hips"}],
    },
    {
        "animation_index": 1,
        "name": "attack",
        "t0_s": 1.0,
        "t1_s": 1.25,
        "roots": [
            {"node_index": 3, "node_name": "hips"},
            {"node_index": 7, "node_name": None},
        ],
    },
]


def expected_settings(ppm, cell, ground_px):
    return {
        "view": {
            "preset": "custom",
            "projection": "orthographic",
            "pitch_deg": 30.0,
            "directions": 2,
            "start_angle_deg": 10.0,
        },
        "model_yaw_deg": 0.0,
        "fps": 4.0,
        "supersample": 2,
        "pixels_per_meter": ppm,
        "cell": cell,
        "ground_m": {"x": 0.0, "y": 0.0, "z": 0.0},
        "ground_px": ground_px,
        "root_motion": "error",
        "clips": [{"name": "walk", "loop": True}, {"name": "attack", "loop": False}],
    }


def expected_job(mode, settings, output_dir):
    return {
        "schema": "moskophoros.capture-job/1",
        "mode": mode,
        "source": {"path": "/models/hero.glb", "sha256": SHA, "scene": 0},
        "subject": "hero",
        "variant": "default",
        "settings": settings,
        "clips": EXPECTED_CLIPS,
        "frames": EXPECTED_FRAMES,
        "output_dir": output_dir,
    }


def independent_sha256(document):
    text = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()


# Jobs


def test_a_measure_job():
    expected = expected_job(
        "measure", expected_settings(None, None, None), "/work/measure"
    )
    job = measure_job()
    assert job == expected
    assert job_sha256(job) == independent_sha256(expected)


def test_a_render_job():
    expected = expected_job(
        "render",
        expected_settings(10.0, {"width": 4, "height": 3}, {"x": 2, "y": 2}),
        "/work/render",
    )
    job = render_job()
    assert job == expected
    assert job_sha256(job) == independent_sha256(expected)


def test_a_measure_job_leaves_fixed_values_null():
    job = build_job(
        "measure", SOURCE, "hero", RENDER_SETTINGS, CLIPS, frames(), "/work/measure"
    )
    settings = job["settings"]
    assert (settings["pixels_per_meter"], settings["cell"], settings["ground_px"]) == (
        None,
        None,
        None,
    )


def test_the_static_clip_has_a_null_index_and_no_roots():
    static = (SelectedClip(Clip(None, "static", 0.0, 0.0, ()), one_shot=False),)
    job = build_job(
        "measure",
        SOURCE,
        "hero",
        MEASURE_SETTINGS,
        static,
        frames(static),
        "/work/measure",
    )
    assert job["clips"] == [
        {
            "animation_index": None,
            "name": "static",
            "t0_s": 0.0,
            "t1_s": 0.0,
            "roots": [],
        }
    ]
    assert [frame["address"]["time_s"] for frame in job["frames"]] == [0.0, 0.0]


def test_canonical_json():
    document = {"b": [1, 2.5, None, True], "a": {"é": "ü", "c": -0.0}}
    assert canonical_json(document) == (
        b'{"a":{"c":-0.0,"\\u00e9":"\\u00fc"},"b":[1,2.5,null,true]}'
    )
    with pytest.raises(ValueError):
        canonical_json({"a": float("nan")})


def bad_frames():
    good = frames()
    return {
        "a frame missing": good[:-1],
        "frames reordered": (good[1], good[0], *good[2:]),
        "a wrong angle": (replace(good[0], angle=11.0), *good[1:]),
        "a wrong index": (replace(good[0], index=1), *good[1:]),
    }


@pytest.mark.parametrize("name", list(bad_frames()))
def test_frames_must_be_the_ones_the_clips_and_settings_give(name):
    with pytest.raises(MalformedJob, match="frames") as raised:
        build_job(
            "measure",
            SOURCE,
            "hero",
            MEASURE_SETTINGS,
            CLIPS,
            bad_frames()[name],
            "/work/measure",
        )
    assert raised.value.exit_code == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"mode": "preview"}, "mode"),
        ({"subject": "villain"}, "stem"),
        ({"output_dir": "work/measure"}, "absolute"),
        ({"source": Source(Path("hero.glb"), SHA, 0)}, "absolute"),
        ({"source": Source(Path("/models/hero.glb"), "AB" * 32, 0)}, "sha256"),
        ({"source": Source(Path("/models/hero.glb"), SHA, -1)}, "scene"),
        ({"settings": replace(MEASURE_SETTINGS, pitch=91.0)}, "pitch"),
        ({"settings": replace(MEASURE_SETTINGS, fps=float("nan"))}, "fps"),
        ({"settings": replace(MEASURE_SETTINGS, supersample=17)}, "supersample"),
        ({"settings": replace(MEASURE_SETTINGS, view="front")}, "view"),
        ({"settings": replace(MEASURE_SETTINGS, root_motion="drop")}, "root_motion"),
        ({"settings": replace(MEASURE_SETTINGS, cell=(4097, 3))}, "cell"),
        ({"mode": "render"}, "ppm is not resolved"),
        ({"clips": ()}, "no clips"),
        ({"clips": (CLIPS[0], CLIPS[0])}, "twice"),
        (
            {
                "clips": (
                    SelectedClip(
                        Clip(None, "static", 0.0, 0.0, (Root(1, None),)), False
                    ),
                )
            },
            "static",
        ),
        (
            {"clips": (SelectedClip(Clip(0, "walk", float("nan"), 0.5, ()), False),)},
            "range",
        ),
        (
            {
                "clips": (
                    SelectedClip(
                        Clip(0, "walk", 0.25, 0.5, (Root(3, None), Root(3, "x"))), False
                    ),
                )
            },
            "root node indices",
        ),
    ],
)
def test_a_malformed_job_is_an_internal_error(change, message):
    arguments = {
        "mode": "measure",
        "source": SOURCE,
        "subject": "hero",
        "settings": MEASURE_SETTINGS,
        "clips": CLIPS,
        "output_dir": "/work/measure",
    }
    arguments.update(change)
    with pytest.raises(MalformedJob, match=message) as raised:
        build_job(
            arguments["mode"],
            arguments["source"],
            arguments["subject"],
            arguments["settings"],
            arguments["clips"],
            frames(),
            arguments["output_dir"],
        )
    assert raised.value.exit_code == 1


# Measure results


def measure_document(job):
    return {
        "schema": "moskophoros.capture-result/1",
        "mode": "measure",
        "job_sha256": independent_sha256(job),
        "source_sha256": SHA,
        "backend": {"blender": "5.2.2"},
        "frames": [
            {
                "address": dict(frame["address"]),
                "bounds_m": {"L": 0.5, "R": 0.25 * k, "U": 1.5, "D": 0.0},
                "height_m": 1.75,
            }
            for k, frame in enumerate(job["frames"])
        ],
        "roots": [
            {"clip": "walk", "node_index": 3, "node_name": "hips", "travel_m": 0.0},
            {"clip": "attack", "node_index": 3, "node_name": "hips", "travel_m": 0.01},
            {"clip": "attack", "node_index": 7, "node_name": None, "travel_m": 0.0},
        ],
    }


def encode(document):
    return json.dumps(document).encode("utf-8")


def test_a_valid_measure_result(tmp_path):
    job = measure_job(str(tmp_path))
    result = validate_result(job, tmp_path, encode(measure_document(job)))
    assert result.mode == "measure"
    assert result.backend == {"blender": "5.2.2"}
    assert result.buffers is None
    assert list(result.measurements) == [
        sampling.FrameAddress(**frame["address"]) for frame in EXPECTED_FRAMES
    ]
    assert list(result.measurements.values())[2] == fit.Measurement(
        fit.Bounds(0.5, 0.5, 1.5, 0.0), 1.75
    )
    assert result.roots == (
        RootTravel("walk", 3, "hips", 0.0),
        RootTravel("attack", 3, "hips", 0.01),
        RootTravel("attack", 7, None, 0.0),
    )


def _set(path, value):
    def change(document):
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _delete(path):
    def change(document):
        target = document
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


def _swap_frames(document):
    frames = document["frames"]
    frames[0], frames[1] = frames[1], frames[0]


def _swap_roots(document):
    roots = document["roots"]
    roots[1], roots[2] = roots[2], roots[1]


MEASURE_REJECTIONS = {
    "the wrong schema": (_set(["schema"], "moskophoros.capture-result/2"), "schema"),
    "the other mode": (_set(["mode"], "render"), "mode"),
    "another job's hash": (_set(["job_sha256"], "0" * 64), "job_sha256"),
    "another source": (_set(["source_sha256"], "0" * 64), "source_sha256"),
    "a missing field": (_delete(["roots"]), "missing roots"),
    "an unknown field": (_set(["extra"], 1), "unknown extra"),
    "no backend version": (_delete(["backend", "blender"]), "missing blender"),
    "a bad backend version": (_set(["backend", "blender"], "5.2.2 LTS"), "version"),
    "render fields in a measure backend": (
        _set(["backend", "renderer"], "workbench"),
        "unknown renderer",
    ),
    "a missing frame": (lambda d: d["frames"].pop(), "5 records for 6"),
    "an extra frame": (
        lambda d: d["frames"].append(copy.deepcopy(d["frames"][0])),
        "7 records for 6",
    ),
    "frames out of order": (_swap_frames, "frame 0 has address"),
    "a different address": (_set(["frames", 0, "address", "time_s"], 0.5), "address"),
    "a boolean direction": (
        _set(["frames", 1, "address", "direction"], True),
        "frame 1 has address",
    ),
    "a negative bound": (_set(["frames", 2, "bounds_m", "U"], -0.1), "bounds_m.U"),
    "a missing bound": (_delete(["frames", 2, "bounds_m", "D"]), "missing D"),
    "a missing height": (_delete(["frames", 3, "height_m"]), "missing height_m"),
    "a string height": (_set(["frames", 3, "height_m"], "1.75"), "height_m"),
    "buffers in a measure frame": (
        _set(["frames", 0, "buffers"], {"color": "color/000000.png"}),
        "unknown buffers",
    ),
    "a missing root": (lambda d: d["roots"].pop(), "2 entries for 3"),
    "roots out of order": (_swap_roots, "root 1 is"),
    "a root with another name": (_set(["roots", 2, "node_name"], "arm"), "root 2 is"),
    "a negative travel": (_set(["roots", 1, "travel_m"], -0.01), "travel_m"),
}


@pytest.mark.parametrize("name", list(MEASURE_REJECTIONS))
def test_a_measure_result_is_rejected(tmp_path, name):
    change, message = MEASURE_REJECTIONS[name]
    job = measure_job(str(tmp_path))
    document = measure_document(job)
    change(document)
    with pytest.raises(BackendError, match=message) as raised:
        validate_result(job, tmp_path, encode(document))
    assert raised.value.exit_code == 5


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (b"{", "not JSON"),
        (b'{"schema": 1, "schema": 2}', "duplicate key 'schema'"),
        (b'{"height_m": NaN}', "non-finite number NaN"),
        (b'{"height_m": -Infinity}', "non-finite number -Infinity"),
        (b'{"height_m": 1e999}', "non-finite number 1e999"),
        (b'{"name": "\xff"}', "not JSON"),
        (b"[]", "not an object"),
    ],
)
def test_a_result_must_be_strict_json(tmp_path, text, message):
    with pytest.raises(BackendError, match=message):
        validate_result(measure_job(str(tmp_path)), tmp_path, text)


# Render results


def png(path, size=(8, 6), mode="RGBA", format="PNG"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, (200, 100, 50, 128)[: len(mode)]).save(path, format=format)
    return path


def raw_png(path, width, height, bit_depth, color_type, channels, extra=()):
    """A PNG written by hand, for formats Pillow does not write. `extra`
    chunks, as (kind, data), go after the pixel data."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    sample = bit_depth // 8
    row = b"\x00" + b"\x7f" * (width * channels * sample)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0),
        )
        + chunk(b"IDAT", zlib.compress(row * height))
        + b"".join(chunk(kind, data) for kind, data in extra)
        + chunk(b"IEND", b"")
    )


def render_document(job, phase_dir):
    """A valid render result, writing its 8×6 buffers: a 4×3 cell at 2×."""
    records = []
    for ordinal, frame in enumerate(job["frames"]):
        path = f"color/{ordinal:06d}.png"
        png(phase_dir / path)
        records.append({"address": dict(frame["address"]), "buffers": {"color": path}})
    return {
        "schema": "moskophoros.capture-result/1",
        "mode": "render",
        "job_sha256": independent_sha256(job),
        "source_sha256": SHA,
        "backend": {
            "blender": "5.2.2",
            "renderer": "workbench",
            "studio_light": "Default",
        },
        "frames": records,
    }


def test_a_valid_render_result(tmp_path):
    job = render_job(str(tmp_path))
    result = validate_result(job, tmp_path, encode(render_document(job, tmp_path)))
    assert result.backend == {
        "blender": "5.2.2",
        "renderer": "workbench",
        "studio_light": "Default",
    }
    assert result.measurements is None and result.roots is None
    root = tmp_path.resolve()
    assert list(result.buffers.values()) == [
        {"color": root / f"color/{ordinal:06d}.png"} for ordinal in range(6)
    ]


def _outside_link(document, phase_dir):
    outside = png(phase_dir.parent / "outside.png")
    target = phase_dir / "color/000000.png"
    target.unlink()
    target.symlink_to(outside)


def _inside_link(document, phase_dir):
    # A symlink that stays inside the phase directory is fine.
    target = phase_dir / "color/000000.png"
    target.rename(phase_dir / "color/real.png")
    target.symlink_to(phase_dir / "color/real.png")


def _truncate(document, phase_dir):
    path = phase_dir / "color/000003.png"
    data = path.read_bytes()
    path.write_bytes(data[: len(data) - 20])


RENDER_REJECTIONS = {
    "no renderer": (lambda d, p: d["backend"].pop("renderer"), "missing renderer"),
    "no studio light": (
        lambda d, p: d["backend"].pop("studio_light"),
        "missing studio_light",
    ),
    "no color buffer": (
        lambda d, p: d["frames"][0]["buffers"].pop("color"),
        "no color",
    ),
    "bounds in a render frame": (
        lambda d, p: d["frames"][0].update(bounds_m={}),
        "unknown bounds_m",
    ),
    "roots in a render result": (lambda d, p: d.update(roots=[]), "unknown roots"),
    "an absolute path": (
        lambda d, p: d["frames"][0]["buffers"].update(
            color=str(p / "color/000000.png")
        ),
        "is absolute",
    ),
    "a parent reference": (
        lambda d, p: d["frames"][0]["buffers"].update(
            color="color/../color/000000.png"
        ),
        "parent reference",
    ),
    "a symlink escape": (_outside_link, "escapes the phase directory"),
    "a missing file": (
        lambda d, p: (p / "color/000002.png").unlink(),
        "does not exist",
    ),
    "a misnamed color buffer": (
        lambda d, p: d["frames"][1]["buffers"].update(color="color/000000.png"),
        "not 'color/000001.png'",
    ),
    "the wrong size": (
        lambda d, p: png(p / "color/000004.png", size=(8, 7)),
        "is 8x7, not 8x6",
    ),
    "a JPEG": (
        lambda d, p: png(p / "color/000001.png", mode="RGB", format="JPEG"),
        "is not a PNG",
    ),
    "an RGB PNG": (lambda d, p: png(p / "color/000001.png", mode="RGB"), "8-bit RGBA"),
    "a palette PNG": (lambda d, p: png(p / "color/000001.png", mode="P"), "8-bit RGBA"),
    "a 16-bit RGBA PNG": (
        lambda d, p: raw_png(p / "color/000005.png", 8, 6, 16, 6, 4),
        "bit depth 16",
    ),
    "truncated pixel data": (_truncate, "does not decode"),
    # Pillow raises SyntaxError for an unknown iCCP compression method.
    "a malformed iCCP chunk": (
        lambda d, p: raw_png(
            p / "color/000002.png", 8, 6, 8, 6, 4, [(b"iCCP", b"name\x00\x01x")]
        ),
        "does not decode",
    ),
    # ... and IndexError for an empty iCCP chunk.
    "an empty iCCP chunk": (
        lambda d, p: raw_png(p / "color/000003.png", 8, 6, 8, 6, 4, [(b"iCCP", b"")]),
        "does not decode",
    ),
    "an invalid extra buffer": (
        lambda d, p: d["frames"][0]["buffers"].update(depth="depth/000000.png"),
        "depth buffer 'depth/000000.png' does not exist",
    ),
}


@pytest.mark.parametrize("name", list(RENDER_REJECTIONS))
def test_a_render_result_is_rejected(tmp_path, name):
    change, message = RENDER_REJECTIONS[name]
    phase_dir = tmp_path / "render"
    job = render_job(str(phase_dir))
    document = render_document(job, phase_dir)
    change(document, phase_dir)
    with pytest.raises(BackendError, match=message) as raised:
        validate_result(job, phase_dir, encode(document))
    assert raised.value.exit_code == 5


def test_a_hand_written_8_bit_rgba_png_is_accepted(tmp_path):
    # The same writer as the 16-bit rejection, at 8 bits.
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    raw_png(tmp_path / "color/000005.png", 8, 6, 8, 6, 4)
    validate_result(job, tmp_path, encode(document))


def test_a_symlink_inside_the_phase_directory_is_accepted(tmp_path):
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    _inside_link(document, tmp_path)
    validate_result(job, tmp_path, encode(document))


def test_a_valid_extra_buffer_is_accepted(tmp_path):
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    png(tmp_path / "depth/000000.png")
    document["frames"][0]["buffers"]["depth"] = "depth/000000.png"
    result = validate_result(job, tmp_path, encode(document))
    first = next(iter(result.buffers.values()))
    assert set(first) == {"color", "depth"}


def test_pillow_s_size_guard_does_not_refuse_an_expected_size(tmp_path, monkeypatch):
    # With a limit of 1 pixel, Pillow would refuse every 8×6 buffer; the
    # header has already checked the exact size, and the limit is restored.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)
    job = render_job(str(tmp_path))
    validate_result(job, tmp_path, encode(render_document(job, tmp_path)))
    assert Image.MAX_IMAGE_PIXELS == 1


# Unusual values and files are classified, never raised raw.


def test_huge_integers_are_finite_numbers(tmp_path):
    job = measure_job(str(tmp_path))
    document = measure_document(job)
    document["frames"][0]["bounds_m"]["L"] = 10**400
    document["frames"][0]["height_m"] = 10**400
    result = validate_result(job, tmp_path, encode(document))
    first = next(iter(result.measurements.values()))
    assert (first.bounds.left, first.height) == (10**400, 10**400)


def test_deeply_nested_json_is_rejected(tmp_path):
    # Some Python versions' parsers exceed the recursion limit here, others
    # parse it; either way it is a backend error, never a raw exception.
    text = b"[" * 100_000 + b"]" * 100_000
    with pytest.raises(BackendError) as raised:
        validate_result(measure_job(str(tmp_path)), tmp_path, text)
    assert raised.value.exit_code == 5


def _directory_buffer(document, phase_dir):
    path = phase_dir / "color/000001.png"
    path.unlink()
    path.mkdir()


def _fifo_buffer(document, phase_dir):
    path = phase_dir / "color/000001.png"
    path.unlink()
    os.mkfifo(path)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda d, p: d["frames"][1]["buffers"].update(color="color/0\u00001.png"),
            "contains a NUL character",
        ),
        (_directory_buffer, "is not a regular file"),
        (_fifo_buffer, "is not a regular file"),
    ],
    ids=["a NUL in the path", "a directory", "a FIFO"],
)
def test_unusual_buffer_files_are_rejected(tmp_path, change, message):
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    change(document, tmp_path)
    with pytest.raises(BackendError, match=message) as raised:
        validate_result(job, tmp_path, encode(document))
    assert raised.value.exit_code == 5


def test_an_unreadable_buffer_is_rejected(tmp_path, monkeypatch):
    # Permissions cannot make a file unreadable to root, so the read fails
    # by substitution instead.
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    unreadable = (tmp_path / "color/000002.png").resolve()
    real_open = Path.open

    def guarded_open(self, *args, **kwargs):
        if self == unreadable:
            raise PermissionError(13, "Permission denied", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    with pytest.raises(BackendError, match="cannot be read: .*Permission denied"):
        validate_result(job, tmp_path, encode(document))
