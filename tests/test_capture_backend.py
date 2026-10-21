import copy
import hashlib
import json
import os
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from capture_buffers import (
    FRONT_BUFFERS,
    png16,
    write_depth,
    write_front,
    write_normal,
)
from PIL import Image
from shading import DEFAULT_SHADE

from moskophoros import fit, sampling, views
from moskophoros.capture.backend import (
    BackendError,
    MalformedJob,
    MaterialShade,
    RootTravel,
    Settings,
    Shade,
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
    direction=views.pitch_direction(30.0),
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
    shade=DEFAULT_SHADE,
)
RENDER_SETTINGS = replace(MEASURE_SETTINGS, ppm=10.0, cell=(4, 3), ground_px=(2, 2))
VIEW = views.View(2, 10.0, 0.0)


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
            "directions": 2,
            "start_angle_deg": 10.0,
        },
        "camera": {
            "projection": "orthographic",
            "direction": [0.0, -0.49999999999999994, -0.8660254037844387],
            "roll": 0.0,
            "position": None,
        },
        "model_yaw_deg": 0.0,
        "fps": 4.0,
        "frames": "auto",
        "supersample": 2,
        "pixels_per_meter": ppm,
        "cell": cell,
        "ground_m": {"x": 0.0, "y": 0.0, "z": 0.0},
        "ground_px": ground_px,
        "root_motion": "error",
        "shade": {
            "ao_distance_m": 0.3,
            "ao_samples": 64,
            "occlusion_weight": 0.25,
            "convexity_weight": 1.0,
            "materials": [],
        },
        "clips": [
            {"name": "walk", "loop": True, "frames": None},
            {"name": "attack", "loop": False, "frames": None},
        ],
    }


def expected_job(mode, settings, output_dir, clipping=None):
    return {
        "schema": "moskophoros.capture-job/3",
        "mode": mode,
        "source": {"path": "/models/hero.glb", "sha256": SHA, "scene": 0},
        "subject": "hero",
        "variant": "default",
        "settings": settings,
        "clips": EXPECTED_CLIPS,
        "frames": EXPECTED_FRAMES,
        "clipping": clipping,
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
        (
            {"settings": replace(MEASURE_SETTINGS, direction=(0.0, 0.0, 0.0))},
            "direction",
        ),
        (
            {"settings": replace(MEASURE_SETTINGS, direction=(0.0, -0.5, -0.5))},
            "direction",
        ),
        ({"settings": replace(MEASURE_SETTINGS, direction=(0.0, 1.0))}, "direction"),
        ({"settings": replace(MEASURE_SETTINGS, roll=1.5)}, "roll"),
        ({"settings": replace(MEASURE_SETTINGS, roll=float("nan"))}, "roll"),
        ({"settings": replace(MEASURE_SETTINGS, position=(0.0, 1.0))}, "position"),
        (
            {"settings": replace(MEASURE_SETTINGS, position=(0.0, 1.0, float("inf")))},
            "position",
        ),
        ({"settings": replace(MEASURE_SETTINGS, fps=float("nan"))}, "fps"),
        ({"settings": replace(MEASURE_SETTINGS, supersample=17)}, "supersample"),
        ({"settings": replace(MEASURE_SETTINGS, view="front")}, "view"),
        ({"settings": replace(MEASURE_SETTINGS, root_motion="drop")}, "root_motion"),
        ({"settings": replace(MEASURE_SETTINGS, cell=(4097, 3))}, "cell"),
        (
            {"settings": replace(MEASURE_SETTINGS, shade=Shade(0.3, 129, 0.25, 1.0))},
            "shade.ao_samples 129",
        ),
        (
            {"settings": replace(MEASURE_SETTINGS, shade=Shade(0.3, 0, 0.25, 1.0))},
            "shade.ao_samples 0",
        ),
        (
            {"settings": replace(MEASURE_SETTINGS, shade=Shade(0.3, True, 0.25, 1.0))},
            "shade.ao_samples True",
        ),
        (
            {"settings": replace(MEASURE_SETTINGS, shade=Shade(0.0, 64, 0.25, 1.0))},
            "shade.ao_distance_m 0.0",
        ),
        (
            {
                "settings": replace(
                    MEASURE_SETTINGS, shade=Shade(float("inf"), 64, 0.25, 1.0)
                )
            },
            "shade.ao_distance_m inf",
        ),
        (
            {"settings": replace(MEASURE_SETTINGS, shade=Shade(0.3, 64, -0.1, 1.0))},
            "shade.occlusion_weight -0.1",
        ),
        (
            {"settings": replace(MEASURE_SETTINGS, shade=Shade(0.3, 64, 0.25, "1"))},
            "shade.convexity_weight '1'",
        ),
        ({"settings": replace(MEASURE_SETTINGS, shade=None)}, "shade None"),
        (
            {
                "settings": replace(
                    MEASURE_SETTINGS,
                    shade=replace(
                        MEASURE_SETTINGS.shade,
                        materials=(MaterialShade(0, 0.0, 0.5, 0.5),),
                    ),
                )
            },
            r"shade.materials\[0\].ao_distance_m 0.0",
        ),
        (
            {
                "settings": replace(
                    MEASURE_SETTINGS,
                    shade=replace(
                        MEASURE_SETTINGS.shade,
                        materials=(MaterialShade(0, 1.0, -0.5, 0.5),),
                    ),
                )
            },
            r"shade.materials\[0\].occlusion_weight -0.5",
        ),
        (
            {
                "settings": replace(
                    MEASURE_SETTINGS,
                    shade=replace(
                        MEASURE_SETTINGS.shade,
                        materials=(
                            MaterialShade(2, 1.0, 0.5, 0.5),
                            MaterialShade(1, 1.0, 0.5, 0.5),
                        ),
                    ),
                )
            },
            "are not distinct, ascending",
        ),
        (
            {
                "settings": replace(
                    MEASURE_SETTINGS,
                    shade=replace(MEASURE_SETTINGS.shade, materials=[1]),
                )
            },
            "shade.materials",
        ),
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
        "schema": "moskophoros.capture-result/5",
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
    "the wrong schema": (_set(["schema"], "moskophoros.capture-result/1"), "schema"),
    "the other mode": (_set(["mode"], "render"), "mode"),
    "another job's hash": (_set(["job_sha256"], "0" * 64), "job_sha256"),
    "another source": (_set(["source_sha256"], "0" * 64), "source_sha256"),
    "a missing field": (_delete(["roots"]), "missing roots"),
    "an unknown field": (_set(["extra"], 1), "unknown extra"),
    "no backend version": (_delete(["backend", "blender"]), "missing blender"),
    "a bad backend version": (_set(["backend", "blender"], "5.2.2 LTS"), "version"),
    "render fields in a measure backend": (
        _set(["backend", "renderer"], "cycles"),
        "unknown renderer",
    ),
    "a colour record in a measure backend": (
        _set(["backend", "color"], {"technique": "cycles-flat-emission"}),
        "unknown color",
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


# Perspective measure results (projects and camera design D-16, C-5, C-12)

PERSPECTIVE_SETTINGS = replace(
    MEASURE_SETTINGS, projection="perspective", position=(0.0, 1.5, 2.5)
)


def perspective_job(output_dir="/work/measure"):
    return build_job(
        "measure", SOURCE, "hero", PERSPECTIVE_SETTINGS, CLIPS, frames(), output_dir
    )


def perspective_document(job):
    """Every frame with its depths, the farthest equal to the nearest in
    frame 4; frame 1 has a vertex behind the camera, so no bounds."""
    document = measure_document(job)
    for k, frame in enumerate(document["frames"]):
        frame["depth_m"] = [2.0, 2.0] if k == 4 else [2.0, 3.0 + 0.1 * k]
    document["frames"][1] |= {"bounds_m": None, "depth_m": [-0.2, 3.1]}
    return document


def test_a_valid_perspective_measure_result(tmp_path):
    job = perspective_job(str(tmp_path))
    result = validate_result(job, tmp_path, encode(perspective_document(job)))
    addresses = [sampling.FrameAddress(**frame["address"]) for frame in EXPECTED_FRAMES]
    assert list(result.depths) == addresses
    assert result.depths[addresses[1]] == (-0.2, 3.1)
    assert result.depths[addresses[4]] == (2.0, 2.0)
    assert result.measurements[addresses[1]] == fit.Measurement(None, 1.75)
    assert result.measurements[addresses[2]] == fit.Measurement(
        fit.Bounds(0.5, 0.5, 1.5, 0.0), 1.75
    )


def test_an_orthographic_measure_result_has_no_depths(tmp_path):
    job = measure_job(str(tmp_path))
    assert validate_result(job, tmp_path, encode(measure_document(job))).depths is None


@pytest.mark.parametrize(
    ("depth", "near"),
    [
        ([-0.2, 3.1], True),
        ([0.0, 3.1], True),
        ([5e-5, 3.1], True),
        ([1e-4, 3.1], True),
        ([1.0000000000000002e-4, 3.1], False),
        ([0.5, 3.1], False),
    ],
)
def test_bounds_are_null_exactly_when_a_vertex_is_too_near(tmp_path, depth, near):
    job = perspective_job(str(tmp_path))
    for bounds in (None, {"L": 0.5, "R": 0.25, "U": 1.5, "D": 0.0}):
        document = perspective_document(job)
        document["frames"][1] |= {"bounds_m": bounds, "depth_m": depth}
        if (bounds is None) == near:
            validate_result(job, tmp_path, encode(document))
            continue
        with pytest.raises(BackendError, match="frame 1 ") as raised:
            validate_result(job, tmp_path, encode(document))
        assert raised.value.exit_code == 5


PERSPECTIVE_REJECTIONS = {
    "no depths": (_delete(["frames", 2, "depth_m"]), "frame 2 is missing depth_m"),
    "null depths": (_set(["frames", 2, "depth_m"], None), "frame 2 depth_m"),
    "one depth": (_set(["frames", 2, "depth_m"], [2.0]), "frame 2 depth_m"),
    "three depths": (_set(["frames", 2, "depth_m"], [2.0, 2.5, 3.0]), "depth_m"),
    "reversed depths": (_set(["frames", 2, "depth_m"], [3.0, 2.0]), "nearest first"),
    "a boolean depth": (_set(["frames", 2, "depth_m"], [True, 3.0]), "depth_m"),
    "a string depth": (_set(["frames", 2, "depth_m"], ["2", 3.0]), "depth_m"),
    "an object of depths": (
        _set(["frames", 2, "depth_m"], {"near": 2.0, "far": 3.0}),
        "frame 2 depth_m",
    ),
    "a non-finite depth": (
        _set(["frames", 2, "depth_m"], [float("nan"), 3.0]),
        "non-finite",
    ),
    "an infinite depth": (
        _set(["frames", 2, "depth_m"], [2.0, float("inf")]),
        "non-finite",
    ),
    "null bounds with a far depth": (
        _set(["frames", 2, "bounds_m"], None),
        "frame 2 bounds_m is null",
    ),
    "bounds with a near depth": (
        _set(["frames", 1, "bounds_m"], {"L": 0.5, "R": 0.0, "U": 1.5, "D": 0.0}),
        "frame 1 has bounds_m",
    ),
    "a missing height beside null bounds": (
        _delete(["frames", 1, "height_m"]),
        "frame 1 is missing height_m",
    ),
}


@pytest.mark.parametrize("name", list(PERSPECTIVE_REJECTIONS))
def test_a_perspective_measure_result_is_rejected(tmp_path, name):
    change, message = PERSPECTIVE_REJECTIONS[name]
    job = perspective_job(str(tmp_path))
    document = perspective_document(job)
    change(document)
    with pytest.raises(BackendError, match=message) as raised:
        validate_result(job, tmp_path, encode(document))
    assert raised.value.exit_code == 5


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_set(["frames", 2, "bounds_m"], None), "frame 2 bounds_m is null"),
        (_set(["frames", 2, "depth_m"], [-0.2, 3.1]), "unknown depth_m"),
    ],
    ids=["null bounds", "depths"],
)
def test_an_orthographic_frame_has_bounds_and_no_depths(tmp_path, change, message):
    job = measure_job(str(tmp_path))
    document = measure_document(job)
    change(document)
    with pytest.raises(BackendError, match=message) as raised:
        validate_result(job, tmp_path, encode(document))
    assert raised.value.exit_code == 5


# Perspective jobs and their clipping


def test_the_clipping_planes_enclose_every_frame_s_depths():
    from moskophoros.capture.backend import Clipping, clipping

    depths = [(2.5, 3.0), (1.25, 2.0), (2.0, 2.0), (3.0, 4.5)]
    assert clipping(depths) == Clipping(0.625, 10.0, (1.25, 4.5))
    assert clipping([(2.0, 2.0)]) == Clipping(1.0, 5.0, (2.0, 2.0))
    with pytest.raises(ValueError, match="cannot be clipped"):
        clipping([(2.0, 3.0), (1e-4, 3.0)])


def test_a_perspective_render_job_carries_its_clipping():
    from moskophoros.capture.backend import Clipping

    settings = replace(PERSPECTIVE_SETTINGS, ppm=10.0, cell=(4, 3), ground_px=(2, 2))
    job = build_job(
        "render",
        SOURCE,
        "hero",
        settings,
        CLIPS,
        frames(),
        "/work/render",
        Clipping(0.625, 10.0, (1.25, 4.5)),
    )
    assert job["schema"] == "moskophoros.capture-job/3"
    assert job["clipping"] == {"near_m": 0.625, "far_m": 10.0, "depth_m": [1.25, 4.5]}
    assert job["settings"]["camera"] == {
        "projection": "perspective",
        "direction": list(views.pitch_direction(30.0)),
        "roll": 0.0,
        "position": [0.0, 1.5, 2.5],
    }
    assert perspective_job()["clipping"] is None


def test_clipping_belongs_to_a_perspective_render_job_alone():
    from moskophoros.capture.backend import Clipping

    planes = Clipping(0.625, 10.0, (1.25, 4.5))
    perspective = replace(PERSPECTIVE_SETTINGS, ppm=10.0, cell=(4, 3), ground_px=(2, 2))
    cases = [
        ("render", perspective, None, "needs clipping"),
        ("render", RENDER_SETTINGS, planes, "only a perspective render"),
        ("measure", PERSPECTIVE_SETTINGS, planes, "only a perspective render"),
        ("render", perspective, Clipping(1.25, 10.0, (1.25, 4.5)), "do not enclose"),
        ("render", perspective, Clipping(0.5, 4.5, (1.25, 4.5)), "do not enclose"),
    ]
    for mode, settings, clip, message in cases:
        with pytest.raises(MalformedJob, match=message):
            build_job(mode, SOURCE, "hero", settings, CLIPS, frames(), "/w", clip)


@pytest.mark.parametrize(
    ("position", "message"),
    [
        (None, "the perspective camera has no position"),
        ((0.0, -1.5, -2.5), "the ground point is not in front of the camera"),
        ((1.0, 0.0, 0.0), "the ground point is not in front of the camera"),
    ],
)
def test_a_perspective_job_needs_the_ground_point_in_front(position, message):
    settings = replace(PERSPECTIVE_SETTINGS, position=position)
    with pytest.raises(MalformedJob, match=message):
        build_job("measure", SOURCE, "hero", settings, CLIPS, frames(), "/w")


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


def raw_png(path, width, height, bit_depth, color_type, channels, extra=(), fill=0x7F):
    """A PNG written by hand, for formats Pillow does not write, every byte
    of it `fill`. `extra` chunks, as (kind, data), go after the pixel data."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    sample = bit_depth // 8
    row = b"\x00" + bytes([fill]) * (width * channels * sample)
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


SHADE = {
    "technique": "cycles-ambient-occlusion",
    "samples_per_pixel": 1,
    "seed": 0,
    "pixel_filter": "BOX",
    "filter_width_px": 0.01,
}
# Material 0's code, with red its high byte and green its low byte.
MATID = (0, 1, 0, 255)
SHADED = (137, 137, 137, 255)
# A surface's flat colour: a capture's colour is opaque or empty.
OPAQUE = (200, 100, 50, 255)
BUFFER_NAMES = ("color", "matid", "shade", "back_normal", "normal", "depth")
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


def render_document(job, phase_dir):
    """A valid render result, writing its 8×6 buffers: a 4×3 cell at 2×.
    Every pixel shows material 0 in an opaque flat colour, shaded 137,
    facing the viewer at depth 0.5 m."""
    records = []
    for ordinal, frame in enumerate(job["frames"]):
        paths = {name: f"{name}/{ordinal:06d}.png" for name in BUFFER_NAMES}
        Image.new("RGBA", (8, 6), OPAQUE).save(
            phase_dir / _parent(phase_dir, paths["color"])
        )
        Image.new("RGBA", (8, 6), MATID).save(
            phase_dir / _parent(phase_dir, paths["matid"])
        )
        Image.new("RGBA", (8, 6), SHADED).save(
            phase_dir / _parent(phase_dir, paths["shade"])
        )
        covered = np.ones((6, 8), dtype=bool)
        write_normal(phase_dir / paths["back_normal"], covered)
        write_normal(phase_dir / paths["normal"], covered)
        write_depth(phase_dir / paths["depth"], covered, 0.5)
        paths |= write_front(phase_dir, ordinal, (8, 6))
        records.append({"address": dict(frame["address"]), "buffers": paths})
    return {
        "schema": "moskophoros.capture-result/5",
        "mode": "render",
        "job_sha256": independent_sha256(job),
        "source_sha256": SHA,
        "backend": {
            "blender": "5.2.2",
            "renderer": "cycles",
            "color": dict(COLOR),
            "shade": dict(SHADE),
        },
        "frames": records,
        "materials": [{"id": 1, "material": 0}, {"id": 65535, "material": None}],
    }


def _paint(path, pixel, value):
    with Image.open(path) as opened:
        image = opened.copy()
    image.putpixel(pixel, value)
    image.save(path)


def _clear(phase_dir, ordinal, pixel):
    """Make `pixel` of frame `ordinal` no surface in every buffer."""
    for name in ("color", "matid", "shade"):
        _paint(phase_dir / f"{name}/{ordinal:06d}.png", pixel, (0, 0, 0, 0))
    for name, write in (
        ("back_normal", write_normal),
        ("normal", write_normal),
        ("depth", write_depth),
    ):
        covered = np.ones((6, 8), dtype=bool)
        covered[pixel[1], pixel[0]] = False
        args = (covered, 0.5) if name == "depth" else (covered,)
        write(phase_dir / f"{name}/{ordinal:06d}.png", *args)


# The front layer at one pixel.
FRONT_PIXEL = np.zeros((6, 8), dtype=bool)
FRONT_PIXEL[2, 3] = True


def write_front_alpha(phase_dir, ordinal, present, sample=(0, 0, 0, 0)):
    """Frame `ordinal`'s front alpha buffer, `sample` wherever `present`."""
    samples = np.zeros((6, 8, 4), dtype=np.uint16)
    if present is not None:
        samples[present] = sample
    png16(phase_dir / f"front_alpha/{ordinal:06d}.png", samples)


def _parent(phase_dir, relative):
    (phase_dir / relative).parent.mkdir(parents=True, exist_ok=True)
    return relative


def test_a_valid_render_result(tmp_path):
    job = render_job(str(tmp_path))
    result = validate_result(job, tmp_path, encode(render_document(job, tmp_path)))
    assert result.backend == {
        "blender": "5.2.2",
        "renderer": "cycles",
        "color": COLOR,
        "shade": SHADE,
    }
    assert result.measurements is None and result.roots is None
    root = tmp_path.resolve()
    assert list(result.buffers.values()) == [
        {
            name: root / f"{name}/{ordinal:06d}.png"
            for name in (*BUFFER_NAMES, *FRONT_BUFFERS)
        }
        for ordinal in range(6)
    ]
    assert result.materials == {1: 0, 65535: None}


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
    # Into the compressed pixels, past the IEND chunk and IDAT's checksum.
    path.write_bytes(data[: len(data) - 30])


RENDER_REJECTIONS = {
    "no renderer": (lambda d, p: d["backend"].pop("renderer"), "missing renderer"),
    "no colour record": (lambda d, p: d["backend"].pop("color"), "missing color"),
    "a studio light": (
        lambda d, p: d["backend"].update(studio_light="Default"),
        "unknown studio_light",
    ),
    "a colour record without a field": (
        lambda d, p: d["backend"]["color"].pop("pass_alpha_threshold"),
        "backend.color is missing pass_alpha_threshold",
    ),
    "a colour record with another field": (
        lambda d, p: d["backend"]["color"].update(studio_light="Default"),
        "backend.color has unknown studio_light",
    ),
    "a colour technique that is no name": (
        lambda d, p: d["backend"]["color"].update(technique=""),
        "backend.color.technique is invalid",
    ),
    "a fractional sample count": (
        lambda d, p: d["backend"]["color"].update(samples_per_pixel=1.5),
        "backend.color.samples_per_pixel is invalid",
    ),
    "a boolean seed": (
        lambda d, p: d["backend"]["color"].update(seed=False),
        "backend.color.seed is invalid",
    ),
    "a negative bounce limit": (
        lambda d, p: d["backend"]["color"].update(min_transparent_bounces=-1),
        "backend.color.min_transparent_bounces is invalid",
    ),
    "a string bounce limit": (
        lambda d, p: d["backend"]["color"].update(transparent_max_bounces="64"),
        "backend.color.transparent_max_bounces is invalid",
    ),
    "a zero alpha threshold": (
        lambda d, p: d["backend"]["color"].update(pass_alpha_threshold=0),
        "backend.color.pass_alpha_threshold is invalid",
    ),
    "a filter width that is no number": (
        lambda d, p: d["backend"]["color"].update(filter_width_px=None),
        "backend.color.filter_width_px is invalid",
    ),
    "a partly covered colour pixel": (
        lambda d, p: _paint(p / "color/000001.png", (3, 2), (200, 100, 50, 128)),
        r"colour pixel \(3, 2\) is \(200, 100, 50, 128\), whose alpha is neither",
    ),
    "a colour background pixel with a colour": (
        lambda d, p: (
            _clear(p, 1, (3, 2)),
            _paint(p / "color/000001.png", (3, 2), (1, 0, 0, 0)),
        ),
        r"colour pixel \(3, 2\) is \(1, 0, 0, 0\), no surface, but not",
    ),
    "an empty colour pixel on a surface": (
        lambda d, p: _paint(p / "color/000002.png", (0, 5), (0, 0, 0, 0)),
        r"colour pixel \(0, 5\) is \(0, 0, 0, 0\), no surface, but the "
        r"material-ID pixel there is \(0, 1, 0, 255\)",
    ),
    "a colour surface over no material ID": (
        lambda d, p: (
            _clear(p, 3, (7, 0)),
            _paint(p / "color/000003.png", (7, 0), OPAQUE),
        ),
        r"colour pixel \(7, 0\) is \(200, 100, 50, 255\), a surface, but the "
        r"material-ID pixel there is \(0, 0, 0, 0\)",
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
        lambda d, p: d["frames"][0]["buffers"].update(extra="extra/000000.png"),
        "extra buffer 'extra/000000.png' does not exist",
    ),
    # The front layer (alpha design, Capture transport and provenance).
    "no front alpha buffer": (
        lambda d, p: d["frames"][0]["buffers"].pop("front_alpha"),
        "frame 0 has no front_alpha buffer",
    ),
    "an 8-bit front alpha": (
        lambda d, p: Image.new("RGBA", (8, 6)).save(p / "front_alpha/000000.png"),
        r"front_alpha buffer 'front_alpha/000000.png' is not 16-bit RGBA",
    ),
    "a front alpha where no front colour is": (
        lambda d, p: (
            write_front(p, 1, (8, 6), FRONT_PIXEL, (10, 20, 30), 26214),
            png16(p / "front_alpha/000001.png", np.zeros((6, 8, 4), np.uint16)),
        ),
        r"front_alpha pixel \(3, 2\) is \(0, 0, 0, 0\), no surface, but the "
        r"front material-ID pixel there is \(0, 1, 0, 255\)",
    ),
    "a front colour over no front material ID": (
        lambda d, p: (
            write_front(p, 2, (8, 6), FRONT_PIXEL, (10, 20, 30), 26214),
            _paint(p / "front_matid/000002.png", (3, 2), (0, 0, 0, 0)),
            _paint(p / "front_shade/000002.png", (3, 2), (0, 0, 0, 0)),
            write_front_alpha(p, 2, None),
        ),
        r"front colour pixel \(3, 2\) is \(10, 20, 30, 255\), a surface, but the "
        r"front material-ID pixel there is \(0, 0, 0, 0\)",
    ),
    "a front material-ID code not in the table": (
        lambda d, p: write_front(p, 0, (8, 6), FRONT_PIXEL, (1, 2, 3), 9, code=7),
        "frame 0: front material-ID code 7 is not in the table",
    ),
    "a front alpha with green": (
        lambda d, p: (
            write_front(p, 0, (8, 6), FRONT_PIXEL, (1, 2, 3), 9),
            write_front_alpha(p, 0, FRONT_PIXEL, (9, 1, 0, 65535)),
        ),
        r"front_alpha pixel \(3, 2\) is \(9, 1, 0, 65535\), not an encoded value",
    ),
    "a front-only pixel the normal leaves empty": (
        lambda d, p: (
            _clear(p, 3, (3, 2)),
            write_front(p, 3, (8, 6), FRONT_PIXEL, (1, 2, 3), 9),
        ),
        r"frame 3: normal pixel \(3, 2\) is \(0, 0, 0, 0\), no surface, but a "
        r"layer shows one there \(material-ID pixels \(0, 0, 0, 0\) and front "
        r"\(0, 1, 0, 255\)\)",
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


def test_a_front_layer_over_and_beside_the_back_is_accepted(tmp_path):
    # Frame 4 shows a front layer at one pixel over the back, and frame 5 a
    # front alone where its back is cleared.
    phase_dir = tmp_path / "render"
    job = render_job(str(phase_dir))
    document = render_document(job, phase_dir)
    write_front(phase_dir, 4, (8, 6), FRONT_PIXEL, (10, 20, 30), 26214)
    _clear(phase_dir, 5, (3, 2))
    covered = np.ones((6, 8), dtype=bool)
    write_normal(phase_dir / "normal/000005.png", covered)
    write_depth(phase_dir / "depth/000005.png", covered, 0.5)
    write_front(phase_dir, 5, (8, 6), FRONT_PIXEL, (10, 20, 30), 0)
    result = validate_result(job, phase_dir, encode(document))
    assert len(result.buffers) == 6


def test_a_hand_written_8_bit_rgba_png_is_accepted(tmp_path):
    # The same writer as the 16-bit rejection, at 8 bits.
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    raw_png(tmp_path / "color/000005.png", 8, 6, 8, 6, 4, fill=0xFF)
    validate_result(job, tmp_path, encode(document))


def test_a_symlink_inside_the_phase_directory_is_accepted(tmp_path):
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    _inside_link(document, tmp_path)
    validate_result(job, tmp_path, encode(document))


def test_a_valid_extra_buffer_is_accepted(tmp_path):
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    png(tmp_path / "extra/000000.png")
    document["frames"][0]["buffers"]["extra"] = "extra/000000.png"
    result = validate_result(job, tmp_path, encode(document))
    first = next(iter(result.buffers.values()))
    assert set(first) == {*BUFFER_NAMES, *FRONT_BUFFERS, "extra"}


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


# The shade's capture values (settings design D-3, D-9, D-42)


def test_the_job_carries_the_capture_values_and_not_the_range():
    shade = Shade(1.2, 128, 0.5, 0.0)
    job = build_job(
        "render",
        SOURCE,
        "hero",
        replace(RENDER_SETTINGS, shade=shade),
        CLIPS,
        frames(),
        "/work/render",
    )
    assert job["settings"]["shade"] == {
        "ao_distance_m": 1.2,
        "ao_samples": 128,
        "occlusion_weight": 0.5,
        "convexity_weight": 0.0,
        "materials": [],
    }
    assert list(job["settings"])[-2:] == ["shade", "clips"]


@pytest.mark.parametrize(
    "changed",
    [
        {"ao_distance_m": 1.2},
        {"ao_samples": 128},
        {"occlusion_weight": 0.5},
        {"convexity_weight": 0.0},
    ],
)
def test_each_capture_value_changes_the_job_s_digest(changed):
    def digest(shade):
        job = build_job(
            "render",
            SOURCE,
            "hero",
            replace(RENDER_SETTINGS, shade=shade),
            CLIPS,
            frames(),
            "/work/render",
        )
        return job_sha256(job)

    assert digest(replace(DEFAULT_SHADE, **changed)) != digest(DEFAULT_SHADE)


# Frame counts in the job (settings design D-13, D-31)


@pytest.mark.parametrize("value", [0, -1, True, 2.0, "8", "Auto", None])
def test_an_invalid_global_frame_count_is_a_malformed_job(value):
    with pytest.raises(MalformedJob, match="frames"):
        build_job(
            "measure",
            SOURCE,
            "hero",
            replace(MEASURE_SETTINGS, frames=value),
            CLIPS,
            frames(),
            "/work/measure",
        )


@pytest.mark.parametrize("value", [0, -2, True, 1.5, "6", "AUTO"])
def test_an_invalid_clip_frame_count_is_a_malformed_job(value):
    clips = (replace(CLIPS[0], frames=value), CLIPS[1])
    with pytest.raises(MalformedJob, match="frame count"):
        build_job(
            "measure",
            SOURCE,
            "hero",
            MEASURE_SETTINGS,
            clips,
            frames(),
            "/work/measure",
        )


def test_frames_inconsistent_with_the_counts_are_a_malformed_job():
    counted = (replace(CLIPS[0], frames=3), CLIPS[1])
    # Frames sampled automatically do not match a clip counted to 3.
    with pytest.raises(MalformedJob, match="frames are not the ones"):
        build_job(
            "measure",
            SOURCE,
            "hero",
            MEASURE_SETTINGS,
            counted,
            frames(),
            "/work/measure",
        )
    with pytest.raises(MalformedJob, match="frames are not the ones"):
        build_job(
            "measure",
            SOURCE,
            "hero",
            replace(MEASURE_SETTINGS, frames=5),
            CLIPS,
            frames(),
            "/work/measure",
        )


def test_the_job_carries_the_counts_and_a_changed_count_changes_its_digest():
    def job(global_, own):
        clips = (replace(CLIPS[0], frames=own), CLIPS[1])
        settings = replace(MEASURE_SETTINGS, frames=global_)
        requested = sampling.frames("hero", clips, VIEW, 4.0, global_)
        return build_job("measure", SOURCE, "hero", settings, clips, requested, "/w")

    base = job(3, None)
    assert base["settings"]["frames"] == 3
    assert [clip["frames"] for clip in base["settings"]["clips"]] == [None, None]
    assert job(3, 2)["settings"]["clips"][0]["frames"] == 2
    assert job(3, "auto")["settings"]["clips"][0]["frames"] == "auto"
    digests = {
        job_sha256(job(global_, own))
        for global_, own in ((3, None), (4, None), (3, 2), (3, "auto"))
    }
    assert len(digests) == 4
