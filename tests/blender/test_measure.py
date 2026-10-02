"""Measure jobs run through the launcher on generated models, in real Blender.

Every expected value is worked out here from the fixture's known geometry,
independently of the script.
"""

import hashlib
import json
import math
import subprocess

import pytest
from glb_writer import GlbWriter

from moskophoros import gltf, sampling, views
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

HALF = math.sqrt(0.5)
TOLERANCE = 1e-5


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def measure(
    found,
    path,
    tmp_path,
    *,
    clip_names=(),
    once=(),
    pitch=0.0,
    directions=1,
    start=0.0,
    yaw=0.0,
    fps=4.0,
    ground=(0.0, 0.0, 0.0),
    workspace="work",
):
    """Measure `path` and return (result, job)."""
    subject = gltf.read_glb(path)
    clips = gltf.select_clips(subject, clip_names, once)
    settings = backend.Settings(
        "custom",
        pitch,
        directions,
        start,
        yaw,
        fps,
        1,
        None,
        None,
        ground,
        None,
        "error",
    )
    view = views.View(pitch, directions, start, yaw)
    frames = sampling.frames(subject.name, clips, view, fps)
    root = tmp_path / workspace
    root.mkdir()
    source = backend.Source(
        path.resolve(),
        hashlib.sha256(path.read_bytes()).hexdigest(),
        subject.scene_index,
    )
    job = backend.build_job(
        "measure", source, subject.name, settings, clips, frames, str(root / "measure")
    )
    return blender.run_phase(found, root, job), job


def by_clip(result):
    """{clip: [(direction, time, bounds as L, R, U, D, height)]} in order."""
    grouped = {}
    for address, measurement in result.measurements.items():
        b = measurement.bounds
        grouped.setdefault(address.clip, []).append(
            (
                address.direction,
                address.time_s,
                (b.left, b.right, b.up, b.down),
                measurement.height,
            )
        )
    return grouped


def assert_close(actual, expected):
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected, strict=True):
        assert got == pytest.approx(want, abs=TOLERANCE), (got, want)


# Projection, directions and the selected scene


POINTS = [
    (1.0, 0.0, 0.0),
    (0.0, 2.0, 0.0),
    (0.0, 0.0, -3.0),
    (-0.5, -0.25, 0.75),
    (0.2, 0.1, 0.4),
    (0.3, 0.5, -0.6),
]
# The node turns 90° about +Y and moves to (2, 0, 1): (x, y, z) -> (z, y, -x).
NODE_TRANSLATION = (2.0, 0.0, 1.0)


def world(point):
    x, y, z = point
    return (z + NODE_TRANSLATION[0], y + NODE_TRANSLATION[1], -x + NODE_TRANSLATION[2])


def expected_bounds(points, ground, rotation_deg, pitch_deg):
    """Turn about the vertical axis through `ground`, counter-clockwise seen
    from above, then project onto the screen: right is +X, up is
    (0, cos p, −sin p)."""
    a = math.radians(rotation_deg)
    p = math.radians(pitch_deg)
    xs, ys = [], []
    for x, y, z in points:
        dx, dy, dz = x - ground[0], y - ground[1], z - ground[2]
        tx = dx * math.cos(a) + dz * math.sin(a)
        tz = -dx * math.sin(a) + dz * math.cos(a)
        xs.append(tx)
        ys.append(dy * math.cos(p) - tz * math.sin(p))
    return (max(0, -min(xs)), max(0, *xs), max(0, *ys), max(0, -min(ys)))


def projection_model(tmp_path):
    model = GlbWriter()
    shape = model.mesh(POINTS)
    far = model.mesh(
        [(100.0, 100.0, 100.0), (101.0, 100.0, 100.0), (100.0, 101.0, 100.0)]
    )
    model.scene([model.node("elsewhere", mesh=far)])
    subject = model.node(
        "subject",
        mesh=shape,
        translation=NODE_TRANSLATION,
        rotation=(0.0, HALF, 0.0, HALF),
    )
    model.scene([subject], default=True)
    return model.write(tmp_path, "shape")


def test_a_hand_checked_projection(found, tmp_path):
    # Pitch 0, direction 0: the world points' x and y are the screen's.
    # World points: (2, 0, 0), (2, 2, 1), (-1, 0, 1), (2.75, -0.25, 1.5),
    # (2.4, 0.1, 0.8), (1.4, 0.5, 0.7). L = max(0, 1) = 1, R = 2.75, U = 2,
    # D = 0.25; height = 2 - (-0.25) = 2.25.
    result, _ = measure(found, projection_model(tmp_path), tmp_path)
    ((direction, time_s, box, height),) = by_clip(result)["static"]
    assert (direction, time_s) == (0, 0.0)
    assert box == pytest.approx((1.0, 2.75, 2.0, 0.25), abs=TOLERANCE)
    assert height == pytest.approx(2.25, abs=TOLERANCE)


def test_bounds_at_several_directions_with_yaw_pitch_and_ground(found, tmp_path):
    ground = (0.5, 0.25, -0.5)
    result, job = measure(
        found,
        projection_model(tmp_path),
        tmp_path,
        pitch=30.0,
        directions=3,
        start=10.0,
        yaw=25.0,
        ground=ground,
    )
    points = [world(point) for point in POINTS]
    expected = [
        (d, 0.0, expected_bounds(points, ground, angle + 25.0, 30.0), 2.25)
        for d, angle in enumerate([10.0, 130.0, 250.0])
    ]
    actual = by_clip(result)["static"]
    assert [(d, t) for d, t, _, _ in actual] == [(d, t) for d, t, _, _ in expected]
    for (_, _, box, height), (_, _, want, want_height) in zip(
        actual, expected, strict=True
    ):
        assert box == pytest.approx(want, abs=TOLERANCE)
        assert height == pytest.approx(want_height, abs=TOLERANCE)


# Evaluated geometry and clip isolation


def isolation_model(tmp_path):
    """Three clips that each move a different extent, from nonzero statics.

    - `mover`, static at x = −3, sets L = 3; `slide` moves it to x = −3 − t.
    - `body` is skinned; its vertex on joint J1 sets R = 0.5; `bend` moves J1
      by 2t in x, so R = 0.5 + 2t.
    - `face`'s top vertex sets U = 1 + w for its morph weight w, whose
      default is 0.5; `smile` animates w from 0 to 1, so U = 1 + t.
    """
    model = GlbWriter()
    j1 = model.node("J", translation=(0.0, 0.5, 0.0))
    j0 = model.node("J", children=[j1])
    skin = model.skin(
        [j0, j1],
        [
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -0.5, 0, 1),
        ],
    )
    body_mesh = model.mesh(
        [(0.0, 0.0, 0.0), (0.25, 0.0, 0.0), (0.5, 0.5, 0.0)],
        joints=[(0, 0, 0, 0), (0, 0, 0, 0), (1, 0, 0, 0)],
        skin_weights=[(1, 0, 0, 0)] * 3,
    )
    body = model.node("body", mesh=body_mesh, skin=skin)
    face_mesh = model.mesh(
        [(-0.5, 0.0, 0.0), (0.0, 0.0, 0.0), (-0.25, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.5],
    )
    face = model.node("face", mesh=face_mesh)
    mover = model.node("mover", mesh=True, translation=(-3.0, 0.0, 0.0))
    model.scene([j0, body, face, mover], default=True)
    model.animation(
        "slide", [(mover, "translation", [0, 1], [(-3.0, 0, 0), (-4.0, 0, 0)])]
    )
    model.animation(
        "bend", [(j1, "translation", [0, 1], [(0.0, 0.5, 0), (2.0, 0.5, 0)])]
    )
    model.animation("smile", [(face, "weights", [0, 1], [(0.0,), (1.0,)])])
    return model.write(tmp_path, "isolation")


TIMES = [0.0, 0.25, 0.5, 0.75]
EXPECTED_ISOLATION = {
    "slide": [(3.0 + t, 0.5, 1.5, 0.0) for t in TIMES],
    "bend": [(3.0, 0.5 + 2 * t, 1.5, 0.0) for t in TIMES],
    "smile": [(3.0, 0.5, 1.0 + t, 0.0) for t in TIMES],
}


def boxes(result):
    return {
        clip: [box for _, _, box, _ in rows] for clip, rows in by_clip(result).items()
    }


@pytest.mark.parametrize(
    "order",
    [("slide", "bend", "smile"), ("smile", "bend", "slide"), ("smile", "slide")],
    ids=["file order", "reversed", "a reordered subset"],
)
def test_each_clip_starts_from_the_static_state(found, tmp_path, order):
    result, job = measure(found, isolation_model(tmp_path), tmp_path, clip_names=order)
    assert [clip["name"] for clip in job["clips"]] == list(order)
    measured = boxes(result)
    assert list(measured) == list(order)
    for clip in order:
        assert_close(measured[clip], EXPECTED_ISOLATION[clip])


def test_skinned_geometry_between_keyframes_at_fractional_frames(found, tmp_path):
    # `bend` from t0 = 0.1 to t1 = 1.1: J1 moves 2·(t − 0.1) in x. At 4 fps
    # the samples are 0.1, 0.35, 0.6 and 0.85: Blender frames 2.4, 8.4, 14.4
    # and 20.4, all between keyframes.
    model = GlbWriter()
    j1 = model.node(translation=(0.0, 0.5, 0.0))
    j0 = model.node(children=[j1])
    skin = model.skin(
        [j0, j1],
        [
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -0.5, 0, 1),
        ],
    )
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (0.25, 0.0, 0.0), (0.5, 0.5, 0.0)],
        joints=[(0, 0, 0, 0), (0, 0, 0, 0), (1, 0, 0, 0)],
        skin_weights=[(1, 0, 0, 0)] * 3,
    )
    model.scene([j0, model.node(mesh=mesh, skin=skin)], default=True)
    model.animation(
        "bend", [(j1, "translation", [0.1, 1.1], [(0.0, 0.5, 0), (2.0, 0.5, 0)])]
    )
    result, _ = measure(found, model.write(tmp_path, "skinned"), tmp_path)
    rows = by_clip(result)["bend"]
    times = [0.1 + k * 1.0 / 4 for k in range(4)]
    assert [t for _, t, _, _ in rows] == pytest.approx(times)
    # Bone display shapes would sit at the origin, making L above 0. The
    # script asks the importer for none, and measures only objects holding
    # the file's meshes.
    assert_close(
        [box for _, _, box, _ in rows],
        [(0.0, 0.5 + 2 * (t - 0.1), 0.5, 0.0) for t in times],
    )


def test_a_one_shot_clip_ends_at_its_final_pose(found, tmp_path):
    result, _ = measure(
        found, isolation_model(tmp_path), tmp_path, clip_names=["slide"], once=["slide"]
    )
    assert_close(
        boxes(result)["slide"], [(3.0 + t, 0.5, 1.5, 0.0) for t in [*TIMES, 1.0]]
    )


# Roots


def roots_model(tmp_path):
    """Roots beneath a static, scaled and turned parent, with unnamed and
    duplicate-named nodes.

    Node 0, `dup`, is static. Node 1, unnamed, walks (0, 0, 0) -> (3, 0, 4)
    beneath `base`, scaled 2: 10 m in the world. Node 2 is its animated
    child, so not a root. Node 4, also `dup`, only rises: 0 m.
    """
    model = GlbWriter()
    decoy = model.node("dup", mesh=True, translation=(0.0, 0.0, -2.0))
    walker = model.node(None, mesh=True)
    hand = model.node("hand", mesh=True, translation=(0.0, 1.0, 0.0))
    model.document["nodes"][walker]["children"] = [hand]
    base = model.node(
        "base",
        translation=(1.0, 0.0, 1.0),
        rotation=(0.0, HALF, 0.0, HALF),
        scale=(2.0, 2.0, 2.0),
        children=[walker],
    )
    jumper = model.node("dup", mesh=True, translation=(0.0, 0.0, 2.0))
    model.scene([decoy, base, jumper], default=True)
    model.animation(
        "walk",
        [
            (walker, "translation", [0, 1], [(0.0, 0, 0), (3.0, 0, 4.0)]),
            (hand, "translation", [0, 1], [(0.0, 1, 0), (5.0, 1, 0)]),
            (
                jumper,
                "translation",
                [0, 0.5, 1],
                [(0, 0, 2.0), (0, 3, 2.0), (0, 5, 2.0)],
            ),
        ],
    )
    return model.write(tmp_path, "roots"), (decoy, walker, hand, base, jumper)


def test_root_travel(found, tmp_path):
    path, (decoy, walker, hand, base, jumper) = roots_model(tmp_path)
    # A loop at 3 fps samples 0, 1/3 and 2/3: never t1 = 1, which travel uses.
    result, job = measure(found, path, tmp_path, fps=3.0)
    assert [t for _, t, _, _ in by_clip(result)["walk"]] == pytest.approx(
        [0.0, 1 / 3, 2 / 3]
    )
    assert [
        (root["node_index"], root["node_name"]) for root in job["clips"][0]["roots"]
    ] == [
        (walker, None),
        (jumper, "dup"),
    ]
    assert [(r.clip, r.node_index, r.node_name) for r in result.roots] == [
        ("walk", walker, None),
        ("walk", jumper, "dup"),
    ]
    assert [r.travel_m for r in result.roots] == pytest.approx(
        [10.0, 0.0], abs=TOLERANCE
    )


def test_joint_roots_with_duplicate_names(found, tmp_path):
    # Joints 0 and 1 share a name. The root joint 0 walks 3 m; joint 1, its
    # child, moves too, so it is not a root.
    model = GlbWriter()
    j1 = model.node("joint", translation=(0.0, 0.5, 0.0))
    j0 = model.node("joint", children=[j1])
    skin = model.skin(
        [j0, j1],
        [
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -0.5, 0, 1),
        ],
    )
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (0.25, 0.0, 0.0), (0.5, 0.5, 0.0)],
        joints=[(0, 0, 0, 0), (0, 0, 0, 0), (1, 0, 0, 0)],
        skin_weights=[(1, 0, 0, 0)] * 3,
    )
    model.scene([j0, model.node(mesh=mesh, skin=skin)], default=True)
    model.animation(
        "stride",
        [
            (j0, "translation", [0, 1], [(0.0, 0, 0), (0.0, 0, -3.0)]),
            (j1, "translation", [0, 1], [(0.0, 0.5, 0), (1.0, 0.5, 0)]),
        ],
    )
    result, _ = measure(found, model.write(tmp_path, "joints"), tmp_path)
    ((root),) = result.roots
    assert (root.node_index, root.node_name) == (j0, "joint")
    assert root.travel_m == pytest.approx(3.0, abs=TOLERANCE)


# Static and zero-length clips, and repeatability


def test_a_static_and_a_zero_length_clip(found, tmp_path):
    model = GlbWriter()
    still = model.node("still", mesh=True, translation=(0.0, 0.0, 0.0))
    model.scene([still], default=True)
    static_path = model.write(tmp_path, "still")
    result, _ = measure(found, static_path, tmp_path)
    # The triangle (0, 0, 0), (1, 0, 0), (0, 1, 0): R = 1, U = 1.
    assert by_clip(result) == {
        "static": [(0, 0.0, pytest.approx((0.0, 1.0, 1.0, 0.0)), pytest.approx(1.0))]
    }

    model.animation("pose", [(still, "translation", [0.5], [(2.0, 0.0, 0.0)])])
    posed = model.write(tmp_path, "posed")
    result, _ = measure(found, posed, tmp_path, workspace="posed")
    ((_, time_s, box, _),) = by_clip(result)["pose"]
    assert time_s == 0.5
    assert box == pytest.approx((0.0, 3.0, 1.0, 0.0), abs=TOLERANCE)


def test_measuring_twice_gives_identical_results(found, tmp_path):
    path = isolation_model(tmp_path)
    first, job = measure(found, path, tmp_path, directions=2, workspace="first")
    second, _ = measure(found, path, tmp_path, directions=2, workspace="second")
    assert first == second
    # The two jobs differ only in their output directories, so their results
    # differ only in job_sha256.
    documents = [
        json.loads((tmp_path / name / "measure" / "result.json").read_text())
        for name in ("first", "second")
    ]
    assert documents[0].pop("job_sha256") != documents[1].pop("job_sha256")
    assert documents[0] == documents[1]
    # A measure phase writes its result and no buffers.
    listing = sorted(p.name for p in (tmp_path / "first" / "measure").iterdir())
    assert listing == ["job.json", "result.json"]


# Failures inside the script


def run_raw(found, tmp_path, text):
    """Run the script on a hand-written job; return (status, stderr)."""
    phase = tmp_path / "raw"
    phase.mkdir()
    job_path = phase / "job.json"
    job_path.write_text(text)
    completed = subprocess.run(
        blender.command(found, job_path),
        cwd=phase,
        capture_output=True,
        text=True,
        check=False,
    )
    assert not (phase / "result.json").exists()
    return completed.returncode, completed.stderr


def valid_job_text(found, tmp_path):
    path = isolation_model(tmp_path)
    subject = gltf.read_glb(path)
    clips = gltf.select_clips(subject, (), ())
    settings = backend.Settings(
        "custom", 0.0, 1, 0.0, 0.0, 4.0, 1, None, None, (0, 0, 0), None, "error"
    )
    frames = sampling.frames(subject.name, clips, views.View(0.0, 1, 0.0), 4.0)
    job = backend.build_job(
        "measure",
        backend.Source(
            path.resolve(), hashlib.sha256(path.read_bytes()).hexdigest(), 0
        ),
        subject.name,
        settings,
        clips,
        frames,
        str(tmp_path / "raw"),
    )
    return job


def _repeat_first_frame(text):
    job = json.loads(text)
    job["frames"].append(job["frames"][0])
    return json.dumps(job)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda text: text.replace('{"', '{"schema": "x", "', 1), "duplicate key"),
        (
            lambda text: text.replace(
                "moskophoros.capture-job/1", "moskophoros.capture-job/2"
            ),
            "schema",
        ),
        (lambda text: text.replace('"measure"', '"render"', 1), "not supported"),
        (lambda text: text.replace('"fps": 4.0', '"fps": NaN'), "non-finite"),
        (lambda text: text.replace('"fps": 4.0', '"fps": 1e999'), "non-finite"),
        (lambda text: text.replace('"variant": "default",', ""), "missing"),
        (
            lambda text: text.replace('"time_s": 0.25', '"time_s": 99', 1),
            "outside clip",
        ),
        (_repeat_first_frame, "repeats"),
    ],
    ids=[
        "duplicate key",
        "schema",
        "render mode",
        "NaN",
        "overflow",
        "missing field",
        "a time outside its clip",
        "a repeated address",
    ],
)
def test_a_malformed_job_fails_before_importing(found, tmp_path, change, message):
    job = valid_job_text(found, tmp_path)
    # Point the source at a file that does not exist: reaching the import
    # would fail differently.
    job["source"]["path"] = str(tmp_path / "missing.glb")
    text = change(json.dumps(job, separators=(", ", ": ")))
    status, stderr = run_raw(found, tmp_path, text)
    assert status != 0
    error = [
        line for line in stderr.splitlines() if line.startswith("moskophoros: error:")
    ]
    assert error and message in error[0], stderr
    assert "missing.glb" not in error[0]


def _static_with_range(job):
    job["clips"][0]["animation_index"] = None


def _repeated_root(job):
    job["clips"][0]["roots"].append(dict(job["clips"][0]["roots"][0]))


def _wrong_angle(job):
    job["frames"][0]["angle_deg"] = 1.0


def _wrong_index(job):
    job["frames"][1]["index"] = 5


def _boolean_index(job):
    job["frames"][1]["index"] = True


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_static_with_range, "must be the static clip"),
        (_repeated_root, "repeats root node"),
        (_wrong_angle, "angle is 1.0, not 0.0"),
        (_wrong_index, "are not indexed"),
        (_boolean_index, "a frame's index"),
    ],
    ids=[
        "static clip with a range",
        "repeated root",
        "wrong angle",
        "wrong index",
        "boolean index",
    ],
)
def test_an_inconsistent_job_fails_before_importing(found, tmp_path, change, message):
    job = valid_job_text(found, tmp_path)
    job["source"]["path"] = str(tmp_path / "missing.glb")
    change(job)
    status, stderr = run_raw(found, tmp_path, json.dumps(job))
    assert status != 0
    error = [
        line for line in stderr.splitlines() if line.startswith("moskophoros: error:")
    ]
    assert error and message in error[0], stderr


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda job: job["clips"][0].update(animation_index=7), "animation 7"),
        (
            lambda job: job["clips"][0]["roots"].append(
                {"node_index": 99, "node_name": None}
            ),
            "node 99",
        ),
    ],
    ids=["animation", "node"],
)
def test_an_unmappable_identity_fails_by_name(found, tmp_path, change, message):
    job = valid_job_text(found, tmp_path)
    change(job)
    status, stderr = run_raw(found, tmp_path, json.dumps(job))
    assert status != 0
    assert f"moskophoros: error: {message}" in stderr, stderr


# Bones whose file defaults differ from their bind pose, and meshes Blender
# moves into objects of their own


IDENTITY = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)


@pytest.mark.parametrize(
    ("joint", "expected"),
    [
        # World = joint · v, with an identity inverse bind matrix.
        ({"translation": (2.0, 0.0, 0.0)}, (0.0, 3.0, 1.0, 0.0)),
        ({"scale": (2.0, 2.0, 2.0)}, (0.0, 2.0, 2.0, 0.0)),
    ],
    ids=["translated", "scaled"],
)
def test_a_joint_s_default_transform_is_its_static_pose(
    found, tmp_path, joint, expected
):
    model = GlbWriter()
    j = model.node("joint", **joint)
    skin = model.skin([j], [IDENTITY])
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        joints=[(0, 0, 0, 0)] * 3,
        skin_weights=[(1, 0, 0, 0)] * 3,
    )
    other = model.node("other", translation=(0.0, -9.0, 0.0))
    model.scene([j, model.node("body", mesh=mesh, skin=skin), other], default=True)
    # A clip that moves only a node with no geometry: the joint keeps its
    # default transform in every clip.
    model.animation("idle", [(other, "translation", [0, 1], [(0, -9, 0), (1, -9, 0)])])
    result, _ = measure(found, model.write(tmp_path, "bind"), tmp_path)
    assert_close(boxes(result)["idle"], [expected] * 4)


def test_a_skinned_mesh_with_animated_morph_weights(found, tmp_path):
    # Blender moves this mesh into an object of its own. The joint doubles
    # and moves it by (2, 0, 0); the morph raises the top vertex by w, so
    # U = 2·(1 + w) with w = t, and R = 2·1 + 2 = 4.
    model = GlbWriter()
    j = model.node("joint", translation=(2.0, 0.0, 0.0), scale=(2.0, 2.0, 2.0))
    skin = model.skin([j], [IDENTITY])
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.5],
        joints=[(0, 0, 0, 0)] * 3,
        skin_weights=[(1, 0, 0, 0)] * 3,
    )
    body = model.node("body", mesh=mesh, skin=skin)
    still = model.node("still", mesh=True, translation=(-1.0, 0.0, 0.0))
    model.scene([j, body, still], default=True)
    model.animation("smile", [(body, "weights", [0, 1], [(0.0,), (1.0,)])])
    model.animation("rest", [(still, "translation", [0, 1], [(-1, 0, 0), (-1, 0, 0)])])
    result, _ = measure(found, model.write(tmp_path, "split"), tmp_path)
    measured = boxes(result)
    assert_close(measured["smile"], [(1.0, 4.0, 2.0 + 2.0 * t, 0.0) for t in TIMES])
    # In another clip the weight is back at its default 0.5: U = 3.
    assert_close(measured["rest"], [(1.0, 4.0, 3.0, 0.0)] * 4)


def test_a_huge_model_yaw_measures_like_its_reduced_angle(found, tmp_path):
    # 1e20 is exactly the integer 10**20, which is 280 mod 360.
    path = projection_model(tmp_path)
    huge, _ = measure(found, path, tmp_path, directions=4, yaw=1e20, workspace="huge")
    small, _ = measure(
        found, path, tmp_path, directions=4, yaw=280.0, workspace="small"
    )
    huge_rows, small_rows = by_clip(huge)["static"], by_clip(small)["static"]
    assert len({box for _, _, box, _ in huge_rows}) == 4
    for (_, _, box, _), (_, _, want, _) in zip(huge_rows, small_rows, strict=True):
        assert box == pytest.approx(want, abs=TOLERANCE)


def test_nodes_sharing_a_mesh_with_different_morph_weights(found, tmp_path):
    # Blender gives each instance its own mesh data. The top vertex rises by
    # each node's weight: 1.25 at x = 0 and 1.75 at x = 3, so U = 1.75 and
    # R = 3 + 1 = 4.
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.0],
    )
    first = model.node("first", mesh=mesh, weights=[0.25])
    second = model.node(
        "second", mesh=mesh, translation=(3.0, 0.0, 0.0), weights=[0.75]
    )
    model.scene([first, second], default=True)
    path = model.write(tmp_path, "shared")
    result, _ = measure(found, path, tmp_path)
    assert_close(boxes(result)["static"], [(0.0, 4.0, 1.75, 0.0)])

    model.animation("swap", [(second, "weights", [0, 1], [(0.75,), (0.0,)])])
    result, _ = measure(
        found, model.write(tmp_path, "swapped"), tmp_path, workspace="swap"
    )
    # U = max(1.25, 1 + 0.75·(1 − t)).
    assert_close(
        boxes(result)["swap"],
        [(0.0, 4.0, max(1.25, 1.75 - 0.75 * t), 0.0) for t in TIMES],
    )


def test_a_root_in_another_scene_is_evaluated(found, tmp_path):
    # The selected scene holds a still triangle; the clip moves a node of
    # the other scene 5 m, which is a root but not part of the subject.
    model = GlbWriter()
    mover = model.node("mover", mesh=True, translation=(50.0, 0.0, 0.0))
    model.scene([mover])
    model.scene([model.node("still", mesh=True)], default=True)
    model.animation(
        "move", [(mover, "translation", [0, 1], [(50.0, 0, 0), (55.0, 0, 0)])]
    )
    result, job = measure(found, model.write(tmp_path, "scenes"), tmp_path)
    assert [root["node_index"] for root in job["clips"][0]["roots"]] == [mover]
    ((root),) = result.roots
    assert root.travel_m == pytest.approx(5.0, abs=TOLERANCE)
    assert_close(boxes(result)["move"], [(0.0, 1.0, 1.0, 0.0)] * 4)


def test_file_names_cannot_take_a_node_s_identity(found, tmp_path):
    # The skin's own name is the name the script gives node 2, and Blender
    # names armatures after skins. Node 2 still walks 5 m.
    model = GlbWriter()
    joint = model.node("joint")
    skin = model.skin([joint], [IDENTITY])
    model.document["skins"][skin]["name"] = "moskophoros.node.2"
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        joints=[(0, 0, 0, 0)] * 3,
        skin_weights=[(1, 0, 0, 0)] * 3,
    )
    body = model.node("body", mesh=mesh, skin=skin)
    walker = model.node("moskophoros.mesh.0.data", mesh=True)
    model.document["scenes"] = []
    model.scene([joint, body, walker], default=True)
    model.document["scenes"][0]["name"] = "moskophoros.node.1"
    model.animation("walk", [(walker, "translation", [0, 1], [(0, 0, 0), (5.0, 0, 0)])])
    assert walker == 2
    result, _ = measure(found, model.write(tmp_path, "names"), tmp_path)
    ((root),) = result.roots
    assert (root.node_index, root.travel_m) == (2, pytest.approx(5.0, abs=TOLERANCE))
    # At the last sample, t = 0.75, the walker's triangle reaches x = 3.75 + 1.
    assert boxes(result)["walk"][-1] == pytest.approx(
        (0.0, 4.75, 1.0, 0.0), abs=TOLERANCE
    )


def test_a_time_beyond_blender_s_frame_range_fails(found, tmp_path):
    # 50000 s is frame 1.2 million at 24 fps, past Blender's ±1048574.
    model = GlbWriter()
    still = model.node("still", mesh=True)
    model.scene([still], default=True)
    model.animation(
        "long", [(still, "translation", [0, 50000], [(0, 0, 0), (1, 0, 0)])]
    )
    with pytest.raises(backend.BackendError, match="beyond Blender's frame range"):
        measure(found, model.write(tmp_path, "long"), tmp_path, fps=0.0001)


def morph_model(tmp_path, stem, weights):
    """A unit triangle whose top vertex rises by its morph weight."""
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.0],
    )
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    model.animation("move", [(face, "weights", [0, 1], [(0.0,), (weights,)])])
    return model.write(tmp_path, stem)


@pytest.mark.parametrize("end", [2.0, -2.0, 10.0, -10.0])
def test_animated_morph_weights_beyond_0_to_1(found, tmp_path, end):
    # The top vertex is at y = 1 + w, with w = end·t; one-shot reaches t = 1.
    path = morph_model(tmp_path, "morph", end)
    result, _ = measure(found, path, tmp_path, clip_names=["move"], once=["move"])
    expected = []
    for t in [*TIMES, 1.0]:
        top = 1.0 + end * t
        expected.append(
            ((0.0, 1.0, max(0.0, top), max(0.0, -top)), max(top, 0.0) - min(top, 0.0))
        )
    rows = by_clip(result)["move"]
    assert_close([box for _, _, box, _ in rows], [box for box, _ in expected])
    assert [height for _, _, _, height in rows] == pytest.approx(
        [height for _, height in expected], abs=TOLERANCE
    )


def test_a_sampled_morph_weight_beyond_blender_s_limit_fails(found, tmp_path):
    # One-shot samples reach t = 1, where the weight is 12.
    path = morph_model(tmp_path, "far", 12.0)
    with pytest.raises(
        backend.BackendError, match="to 12.0 at 1.0 s, beyond Blender's ±10"
    ):
        measure(found, path, tmp_path, clip_names=["move"], once=["move"])


def test_a_weight_beyond_the_limit_between_samples_is_never_used(found, tmp_path):
    # Looping samples stop at t = 0.75, where the weight is 9: the 12 at
    # t = 1 is never evaluated.
    result, _ = measure(found, morph_model(tmp_path, "near", 12.0), tmp_path)
    assert_close(
        boxes(result)["move"], [(0.0, 1.0, 1.0 + 12.0 * t, 0.0) for t in TIMES]
    )


def test_a_default_morph_weight_beyond_the_limit_fails(found, tmp_path):
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
    )
    model.scene([model.node("face", mesh=mesh, weights=[12.0])], default=True)
    with pytest.raises(backend.BackendError, match="default weight is 12.0"):
        measure(found, model.write(tmp_path, "heavy"), tmp_path)


def test_weights_the_measurement_never_uses_do_not_matter(found, tmp_path):
    # An unselected clip drives the subject's weight to 12, and a node of
    # another scene has a default weight of 12; neither is measured.
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.0],
    )
    elsewhere = model.node("elsewhere", mesh=mesh, weights=[12.0])
    model.scene([elsewhere])
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    model.animation("good", [(face, "translation", [0, 1], [(0, 0, 0), (1, 0, 0)])])
    model.animation("unused", [(face, "weights", [0, 1], [(0.0,), (12.0,)])])
    result, _ = measure(
        found, model.write(tmp_path, "unused"), tmp_path, clip_names=["good"]
    )
    assert_close(boxes(result)["good"], [(0.0, 1.0 + t, 1.0, 0.0) for t in TIMES])


def test_a_cubic_curve_is_checked_where_evaluated_not_by_its_handles(found, tmp_path):
    # Weights 0, 8.5, 8.5 at 0, 1 and 2 s with zero tangents. Blender's
    # imported handles pass 10, but the weights it evaluates stay within.
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.0],
    )
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    flat = (0.0,)
    model.animation(
        "rise",
        [
            (
                face,
                "weights",
                [0, 1, 2],
                [flat, (0.0,), flat, flat, (8.5,), flat, flat, (8.5,), flat],
            )
        ],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "cubic"),
        tmp_path,
        clip_names=["rise"],
        once=["rise"],
    )
    rows = boxes(result)["rise"]
    # Every sample measured, its top within 1 + 10, ending at 1 + 8.5.
    assert len(rows) == 9
    assert all(box[2] <= 11.0 for box in rows)
    assert rows[-1] == pytest.approx((0.0, 1.0, 9.5, 0.0), abs=TOLERANCE)


def test_gpu_instancing_counts_every_instance(found, tmp_path):
    # One triangle node drawn at x = 0 and x = 5: R = 6.
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.instances(shape, [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0)])
    model.scene([shape], default=True)
    result, _ = measure(found, model.write(tmp_path, "instanced"), tmp_path)
    assert_close(boxes(result)["static"], [(0.0, 6.0, 1.0, 0.0)])


def test_a_pointer_animation_of_a_mesh_s_weights(found, tmp_path):
    # KHR_animation_pointer animates mesh 0's weight 0 -> 0.5 for both nodes
    # using it; one also moves. U = 1 + 0.5·t on both, so the measured U is
    # 1 + 0.5·t; R = 1 + 3 = 4 from the second node.
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.0],
    )
    first = model.node("first", mesh=mesh)
    second = model.node("second", mesh=mesh, translation=(3.0, 0.0, 0.0))
    model.scene([first, second], default=True)
    clip = model.animation(
        "swell", [(first, "translation", [0, 1], [(0, 0, 0), (0, 0, 0)])]
    )
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    result, _ = measure(
        found,
        model.write(tmp_path, "pointer"),
        tmp_path,
        clip_names=["swell"],
        once=["swell"],
    )
    assert_close(
        boxes(result)["swell"], [(0.0, 4.0, 1.0 + 0.5 * t, 0.0) for t in [*TIMES, 1.0]]
    )


def test_a_clip_that_also_animates_a_camera(found, tmp_path):
    # Cameras are ignored: a clip that moves the triangle and widens a
    # camera's field of view measures the triangle alone.
    model = GlbWriter()
    model.document["cameras"] = [
        {"type": "perspective", "perspective": {"yfov": 0.8, "znear": 0.1}}
    ]
    shape = model.node("shape", mesh=True)
    camera = model.node("camera", translation=(0.0, 0.0, 5.0))
    model.document["nodes"][camera]["camera"] = 0
    model.scene([shape, camera], default=True)
    clip = model.animation(
        "pan", [(shape, "translation", [0, 1], [(0, 0, 0), (1.0, 0, 0)])]
    )
    model.pointer_channel(clip, "/cameras/0/perspective/yfov", [0, 1], [(0.8,), (1.0,)])
    result, _ = measure(found, model.write(tmp_path, "camera"), tmp_path)
    assert_close(boxes(result)["pan"], [(0.0, 1.0 + t, 1.0, 0.0) for t in TIMES])


@pytest.mark.parametrize(
    "selected", [("first",), ("first", "second")], ids=["earlier alone", "both"]
)
def test_pointer_weight_clips_sharing_a_mesh(found, tmp_path, selected):
    # Two clips animate mesh 0's weight through KHR_animation_pointer:
    # `first` to 0.5, `second` to 0.25, so U = 1 + 0.5·t and 1 + 0.25·t.
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.0],
    )
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    for name, end in (("first", 0.5), ("second", 0.25)):
        clip = model.animation(name, [(face, "translation", [0, 1], [(0, 0, 0)] * 2)])
        model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (end,)])
    result, _ = measure(
        found, model.write(tmp_path, "clips"), tmp_path, clip_names=list(selected)
    )
    measured = boxes(result)
    assert_close(measured["first"], [(0.0, 1.0, 1.0 + 0.5 * t, 0.0) for t in TIMES])
    if "second" in selected:
        assert_close(
            measured["second"], [(0.0, 1.0, 1.0 + 0.25 * t, 0.0) for t in TIMES]
        )


def pointer_and_node_model(tmp_path, stem, *, pointer_first, node_default=None):
    """A clip animating mesh 0's weight to 0.5 by pointer and, unless the
    node has a default, the node's own weight to 0.25."""
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        weights=[0.0],
    )
    face = model.node("face", mesh=mesh, weights=node_default)
    model.scene([face], default=True)
    if node_default is None:
        clip = model.animation("clip", [(face, "weights", [0, 1], [(0.0,), (0.25,)])])
    else:
        clip = model.animation("clip", [(face, "translation", [0, 1], [(0, 0, 0)] * 2)])
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    if pointer_first:
        model.document["animations"][clip]["channels"].reverse()
    return model, model.write(tmp_path, stem)


@pytest.mark.parametrize(
    "pointer_first", [False, True], ids=["node first", "pointer first"]
)
def test_a_node_s_own_weight_animation_overrides_its_mesh_s(
    found, tmp_path, pointer_first
):
    # The node's weight wins: U = 1 + 0.25·t, in either channel order.
    _, path = pointer_and_node_model(tmp_path, "order", pointer_first=pointer_first)
    result, _ = measure(found, path, tmp_path, clip_names=["clip"], once=["clip"])
    assert_close(
        boxes(result)["clip"], [(0.0, 1.0, 1.0 + 0.25 * t, 0.0) for t in [*TIMES, 1.0]]
    )


def test_a_node_s_default_weights_override_its_mesh_s_animation(found, tmp_path):
    # The node's default 0.75 wins over the mesh's animated weight: U = 1.75.
    _, path = pointer_and_node_model(
        tmp_path, "default", pointer_first=False, node_default=[0.75]
    )
    result, _ = measure(found, path, tmp_path)
    assert_close(boxes(result)["clip"], [(0.0, 1.0, 1.75, 0.0)] * 4)


def test_a_clip_whose_only_channel_is_overridden_moves_nothing(found, tmp_path):
    # With the translation channel removed, the clip only animates the
    # mesh's weight, which the node's default overrides: U = 1.75 throughout.
    model, _ = pointer_and_node_model(
        tmp_path, "unused", pointer_first=True, node_default=[0.75]
    )
    animation = model.document["animations"][0]
    animation["channels"] = [
        channel
        for channel in animation["channels"]
        if channel["target"].get("path") == "pointer"
    ]
    result, _ = measure(found, model.write(tmp_path, "inert"), tmp_path)
    assert_close(boxes(result)["clip"], [(0.0, 1.0, 1.75, 0.0)] * 4)
