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
