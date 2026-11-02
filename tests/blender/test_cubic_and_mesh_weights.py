"""Cubic spline animation and mesh morph-weight pointers, measured through the
launcher on generated models, in real Blender.

Every expected value is worked out here from glTF's own rules (the cubic
spline formula and the instantiation rules for morph weights), independently
of the script.
"""

import math
import struct

import pytest
from glb_writer import GlbWriter
from test_measure import TIMES, assert_close, boxes, by_clip, measure
from test_render import TOLERANCE_PX, centroid, cube, images, render

from moskophoros.capture import backend, blender
from moskophoros.gltf import InputError

pytestmark = pytest.mark.blender

TRIANGLE = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
ZERO = (0.0, 0.0, 0.0)
# Morph target 0 raises the triangle's top vertex by its weight; target 1
# moves its right vertex right by its weight.
RISE = [ZERO, ZERO, (0.0, 1.0, 0.0)]
WIDEN = [ZERO, (1.0, 0.0, 0.0), ZERO]
ONCE_TIMES = [*TIMES, 1.0]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def cubic_at(times, keys, t):
    """glTF's cubic spline at time `t`. `keys` holds an (in-tangent, value,
    out-tangent) triple of tuples for each time."""
    segment = min(max(i for i, key in enumerate(times) if key <= t), len(times) - 2)
    t0, t1 = times[segment], times[segment + 1]
    step = t1 - t0
    s = (t - t0) / step
    _, p0, out = keys[segment]
    into, p1, _ = keys[segment + 1]
    return tuple(
        (2 * s**3 - 3 * s**2 + 1) * v0
        + (s**3 - 2 * s**2 + s) * step * m0
        + (-2 * s**3 + 3 * s**2) * v1
        + (s**3 - s**2) * step * m1
        for v0, m0, v1, m1 in zip(p0, out, p1, into, strict=True)
    )


def flat(keys):
    """The rows `GlbWriter.animation` takes for CUBICSPLINE."""
    return [row for key in keys for row in key]


def mirrored(model, mesh, **kwargs):
    """A node of `mesh` turned upside down: its morph rises downward, so the
    subject's D tells it from an upright node, whose morph raises U."""
    return model.node("down", mesh=mesh, scale=(1.0, -1.0, 1.0), **kwargs)


# Mesh-weight pointers


def test_a_mesh_weight_pointer_animates_every_node_using_the_mesh(found, tmp_path):
    # The pointer is the clip's only channel. The upright node raises U and
    # the mirrored one D, so neither can hide behind the other.
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    up = model.node("up", mesh=mesh)
    down = mirrored(model, mesh)
    model.scene([up, down], default=True)
    clip = model.animation("swell", [])
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    result, _ = measure(found, model.write(tmp_path, "swell"), tmp_path)
    assert_close(
        boxes(result)["swell"],
        [(0.0, 1.0, 1.0 + 0.5 * t, 1.0 + 0.5 * t) for t in TIMES],
    )


def two_clips_on_a_mesh(tmp_path):
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    up = model.node("up", mesh=mesh)
    down = mirrored(model, mesh)
    model.scene([up, down], default=True)
    first = model.animation("first", [])
    model.pointer_channel(first, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    second = model.animation("second", [])
    model.pointer_channel(second, "/meshes/0/weights", [0, 1], [(0.5,), (0.0,)])
    return model.write(tmp_path, "two")


@pytest.mark.parametrize(
    "order",
    [("first",), ("second",), ("first", "second"), ("second", "first")],
    ids=["first alone", "second alone", "file order", "reversed"],
)
def test_clips_on_one_mesh_each_measure_their_own_weights(found, tmp_path, order):
    expected = {
        "first": [1.0 + 0.5 * t for t in TIMES],
        "second": [1.5 - 0.5 * t for t in TIMES],
    }
    result, _ = measure(
        found, two_clips_on_a_mesh(tmp_path), tmp_path, clip_names=order
    )
    measured = boxes(result)
    assert list(measured) == list(order)
    for clip in order:
        assert_close(measured[clip], [(0.0, 1.0, u, u) for u in expected[clip]])


def node_wins_model(tmp_path, *, direct, first, mesh_end=0.5, node_weights=None):
    """An upright node whose own weights come from `direct` (`channel`, a
    `/nodes/0/weights` `pointer`, or its `node_weights` default alone), and a
    mirrored node that takes the mesh's pointer, which runs from 0 to
    `mesh_end`. `first` puts the node's channel before the pointer."""
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    held = model.node("held", mesh=mesh, weights=node_weights)
    free = mirrored(model, mesh)
    model.scene([held, free], default=True)
    clip = model.animation("swell", [])
    own = {
        "channel": lambda: add_weights_channel(model, clip, held),
        "pointer": lambda: model.pointer_channel(
            clip, f"/nodes/{held}/weights", [0, 1], [(0.0,), (0.25,)]
        ),
        "default": lambda: None,
    }[direct]
    if first:
        own()
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (mesh_end,)])
    if not first:
        own()
    return model.write(tmp_path, "wins")


def add_weights_channel(model, clip, node):
    """An ordinary `weights` channel from 0 to 0.25 on `node`."""
    samplers = model.document["animations"][clip]["samplers"]
    samplers.append(
        {
            "input": model._accessor("SCALAR", [(0.0,), (1.0,)], True),
            "output": model._accessor("SCALAR", [(0.0,), (0.25,)], False),
            "interpolation": "LINEAR",
        }
    )
    model.document["animations"][clip]["channels"].append(
        {"sampler": len(samplers) - 1, "target": {"node": node, "path": "weights"}}
    )


@pytest.mark.parametrize("first", [True, False], ids=["node first", "mesh first"])
@pytest.mark.parametrize("direct", ["channel", "pointer"])
def test_a_node_animated_in_the_clip_ignores_the_mesh_pointer(
    found, tmp_path, direct, first
):
    # The node's weight runs 0 to 0.25, the mesh's 0 to 0.5: at t = 1 the
    # node is at 1.25, not 1.5. The mirrored node, which the clip does not
    # animate itself, follows the mesh.
    path = node_wins_model(tmp_path, direct=direct, first=first)
    result, _ = measure(found, path, tmp_path, clip_names=["swell"], once=["swell"])
    assert_close(
        boxes(result)["swell"],
        [(0.0, 1.0, 1.0 + 0.25 * t, 1.0 + 0.5 * t) for t in ONCE_TIMES],
    )
    assert boxes(result)["swell"][-1][2] == pytest.approx(1.25, abs=1e-5)


def test_a_node_default_weight_ignores_the_mesh_pointer(found, tmp_path):
    # The node's own default of 0.75 stays: U = 1.75 throughout.
    path = node_wins_model(tmp_path, direct="default", first=True, node_weights=[0.75])
    result, _ = measure(found, path, tmp_path)
    assert_close(
        boxes(result)["swell"],
        [(0.0, 1.0, 1.75, 1.0 + 0.5 * t) for t in TIMES],
    )


@pytest.mark.parametrize(
    ("direct", "node_weights", "expected"),
    [("channel", None, 0.25), ("default", [0.75], 0.0)],
    ids=["animated node", "default node"],
)
def test_an_overridden_mesh_curve_beyond_the_limit_is_never_used(
    found, tmp_path, direct, node_weights, expected
):
    # Only the node is subject: its mesh curve runs to 12, past Blender's
    # limit, but its effective weights are 0 to 0.25, or 0.75.
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    held = model.node("held", mesh=mesh, weights=node_weights)
    model.scene([held], default=True)
    clip = model.animation("swell", [])
    if direct == "channel":
        add_weights_channel(model, clip, held)
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (12.0,)])
    path = model.write(tmp_path, "heavy")
    result, _ = measure(found, path, tmp_path, clip_names=["swell"], once=["swell"])
    base = 1.75 if node_weights else 1.0
    assert_close(
        boxes(result)["swell"],
        [(0.0, 1.0, base + expected * t, 0.0) for t in ONCE_TIMES],
    )


def test_a_mesh_curve_beyond_the_limit_fails_where_it_is_used(found, tmp_path):
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    model.scene([model.node("face", mesh=mesh)], default=True)
    clip = model.animation("swell", [])
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (12.0,)])
    with pytest.raises(
        backend.BackendError, match="to 12.0 at 1.0 s, beyond Blender's ±10"
    ):
        measure(
            found,
            model.write(tmp_path, "far"),
            tmp_path,
            clip_names=["swell"],
            once=["swell"],
        )


def test_a_mesh_pointer_that_no_node_uses_still_gives_the_clip_its_range(
    found, tmp_path
):
    # Every node using the mesh has its own weights, so the clip animates
    # nothing but still lasts a second: four samples, all of the static pose.
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    model.scene([model.node("face", mesh=mesh, weights=[0.5])], default=True)
    clip = model.animation("swell", [])
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    result, _ = measure(found, model.write(tmp_path, "idle"), tmp_path)
    rows = by_clip(result)["swell"]
    assert [time for _, time, _, _ in rows] == TIMES
    assert_close(boxes(result)["swell"], [(0.0, 1.0, 1.5, 0.0)] * 4)


# Cameras and lights


def light_and_shape(model, kind):
    """A triangle node, and a camera or light, whose pointer channel returns
    for a clip of two seconds."""
    shape = model.node("shape", mesh=True)
    other = model.node(kind)
    if kind == "camera":
        model.document["cameras"] = [
            {"type": "perspective", "perspective": {"yfov": 0.8, "znear": 0.1}}
        ]
        model.document["nodes"][other]["camera"] = 0
        pointer = "/cameras/0/perspective/yfov"
    else:
        model.document["extensions"] = {
            "KHR_lights_punctual": {"lights": [{"type": "point", "intensity": 10.0}]}
        }
        model.document.setdefault("extensionsUsed", []).append("KHR_lights_punctual")
        model.document["nodes"][other]["extensions"] = {
            "KHR_lights_punctual": {"light": 0}
        }
        pointer = "/extensions/KHR_lights_punctual/lights/0/intensity"
    model.scene([shape, other], default=True)
    return shape, pointer


@pytest.mark.parametrize("kind", ["camera", "light"])
def test_a_camera_or_light_property_changes_neither_geometry_nor_samples(
    found, tmp_path, kind
):
    # The triangle moves 1 m in the first second; the property runs to 2 s,
    # so the clip lasts 2 s and its 8 samples run 0 to 1.75 s.
    model = GlbWriter()
    shape, pointer = light_and_shape(model, kind)
    clip = model.animation(
        "pan", [(shape, "translation", [0, 1], [(0, 0, 0), (1.0, 0, 0)])]
    )
    model.pointer_channel(clip, pointer, [0, 2], [(0.8,), (1.0,)])
    result, job = measure(found, model.write(tmp_path, kind), tmp_path)
    assert (job["clips"][0]["t0_s"], job["clips"][0]["t1_s"]) == (0.0, 2.0)
    times = [k / 4 for k in range(8)]
    assert [time for _, time, _, _ in by_clip(result)["pan"]] == times
    assert_close(
        boxes(result)["pan"], [(0.0, 1.0 + min(t, 1.0), 1.0, 0.0) for t in times]
    )


# Cubic spline interpolation


def test_a_cubic_morph_weight_follows_its_tangents(found, tmp_path):
    # Keys of 0 at t = 0 and t = 1, an out-tangent of +4 and an in-tangent of
    # −4: the weight is 4·(t − t²), 1 at t = 0.5 (Blender's own automatic
    # handles would keep it at 0).
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    keys = [((0.0,), (0.0,), (4.0,)), ((-4.0,), (0.0,), (0.0,))]
    model.animation(
        "rise", [(face, "weights", [0, 1], flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "rise"),
        tmp_path,
        clip_names=["rise"],
        once=["rise"],
    )
    rows = by_clip(result)["rise"]
    weights = [4 * (t - t * t) for t in ONCE_TIMES]
    assert weights[2] == 1.0
    assert_close([box[2] for _, _, box, _ in rows], [1.0 + w for w in weights])
    assert_close([height for _, _, _, height in rows], [1.0 + w for w in weights])
    assert rows[2][2][2] == pytest.approx(2.0, abs=1e-5)
    assert rows[2][3] == pytest.approx(2.0, abs=1e-5)


def test_a_cubic_translation_follows_its_tangents_and_travels_nowhere(found, tmp_path):
    # The same curve on x: R = 1 + 4·(t − t²), 2 at the midpoint. Root travel
    # is the distance between the endpoints, 0.
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    keys = [
        ((0.0,) * 3, ZERO, (4.0, 0.0, 0.0)),
        ((-4.0, 0.0, 0.0), ZERO, (0.0,) * 3),
    ]
    model.animation(
        "sway",
        [(shape, "translation", [0, 1], flat(keys))],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "sway"),
        tmp_path,
        clip_names=["sway"],
        once=["sway"],
    )
    rows = boxes(result)["sway"]
    assert_close(rows, [(0.0, 1.0 + 4 * (t - t * t), 1.0, 0.0) for t in ONCE_TIMES])
    assert rows[2][1] == pytest.approx(2.0, abs=1e-5)
    assert [(root.clip, root.node_index) for root in result.roots] == [("sway", shape)]
    assert result.roots[0].travel_m == pytest.approx(0.0, abs=1e-5)


def test_a_cubic_scale_over_several_keys_of_unequal_length(found, tmp_path):
    # Three keys at 0.5, 2.5 and 3 s: segments of 2 s and 0.5 s, with
    # tangents in x and y. The clip lasts 2.5 s and has 10 samples.
    times = [0.5, 2.5, 3.0]
    keys = [
        ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (0.8, -0.4, 0.0)),
        ((1.2, 0.3, 0.0), (2.0, 1.5, 1.0), (-0.5, 0.6, 0.0)),
        ((-1.0, -0.9, 0.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0)),
    ]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "grow", [(shape, "scale", times, flat(keys))], interpolation="CUBICSPLINE"
    )
    result, job = measure(found, model.write(tmp_path, "grow"), tmp_path)
    sampled = [0.5 + 0.25 * k for k in range(10)]
    assert [time for _, time, _, _ in by_clip(result)["grow"]] == sampled
    expected = []
    for t in sampled:
        sx, sy, _ = cubic_at(times, keys, t)
        assert min(sx, sy) > 0.5
        expected.append((0.0, sx, sy, 0.0))
    assert_close(boxes(result)["grow"], expected)


def rotated(q, point):
    x, y, z, w = q
    px, py, pz = point
    cx, cy, cz = (y * pz - z * py, z * px - x * pz, x * py - y * px)
    dx, dy, dz = (y * cz - z * cy, z * cx - x * cz, x * cy - y * cx)
    return (px + 2 * (w * cx + dx), py + 2 * (w * cy + dy), pz + 2 * (w * cz + dz))


def rotation_bounds(times, keys, t):
    """The triangle's L, R, U, D with glTF's normalized cubic rotation at `t`."""
    q = cubic_at(times, keys, t)
    length = math.hypot(*q)
    points = [rotated([c / length for c in q], p) for p in TRIANGLE]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (max(0, -min(xs)), max(0, *xs), max(0, *ys), max(0, -min(ys)))


TURN = (0.0, 0.0, math.sin(math.pi / 6), math.cos(math.pi / 6))


@pytest.mark.parametrize(
    "keys",
    [
        [
            ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.2, -0.1, 0.5, 0.0)),
            ((0.1, 0.2, -0.3, -0.2), TURN, (0.0, 0.0, 0.0, 0.0)),
        ],
        # The control points on the first key's side of the turn are an
        # obtuse angle from its value, where the importer would flip them.
        [
            ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 3.0, -4.0)),
            ((0.0, 0.0, 3.0, -4.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)),
        ],
        # The first control point is orthogonal to its neighbour to within
        # rounding, which the importer's 32-bit arithmetic may decide either
        # way (a review finding).
        [
            ((0.0, 0.0, 0.0, 0.0), (0.5, 0.5, 0.5, 0.5), (4.0, -2.0, -3.0, -5.0)),
            ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)),
        ],
        # The curve passes within 3e-5 of the zero quaternion (a review
        # finding), and its keys' tangents are 1e-3 and 1e-4 from square on.
        [
            ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.001, 0.0, 0.0, -6.0)),
            ((-0.001, 0.0, 0.0, 6.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)),
        ],
        [
            ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0001, 0.0, 0.0, -6.0)),
            ((-0.0001, 0.0, 0.0, 6.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)),
        ],
        # Keys nearly opposite, so the curve turns the long way round.
        [
            ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0, 0.0), (0.0, 0.2, 0.0, -1.0), (0.0, 0.0, 0.0, 0.0)),
        ],
    ],
    ids=[
        "moderate tangents",
        "tangents the importer would flip",
        "a control point square on to its neighbour",
        "a curve near the zero quaternion",
        "a curve nearer the zero quaternion",
        "nearly opposite keys",
    ],
)
def test_a_cubic_rotation_matches_the_normalized_cubic_quaternion(
    found, tmp_path, keys
):
    # A key interval of 1.5 s, nonzero tangents in several components. The
    # tolerance is 0.1° at the triangle's unit lever arm, far from what the
    # restored tangents give.
    times = [0.0, 1.5]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "turn", [(shape, "rotation", times, flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(
        found, model.write(tmp_path, "turn"), tmp_path, fps=4.0, clip_names=["turn"]
    )
    sampled = [1.5 * k / 6 for k in range(6)]
    assert [time for _, time, _, _ in by_clip(result)["turn"]] == pytest.approx(sampled)
    measured = boxes(result)["turn"]
    for got, t in zip(measured, sampled, strict=True):
        want = rotation_bounds(times, keys, t)
        assert got == pytest.approx(want, abs=math.sin(math.radians(0.1)))
        assert got == pytest.approx(want, abs=1e-4)


def test_a_cubic_key_interval_of_a_millisecond(found, tmp_path):
    # The first interval is 0.024 of a frame at Blender's 24 fps, closer than
    # keys can be before Blender merges them (a review finding); the second
    # runs to the end of the clip.
    times = [0.0, 0.001, 1.0]
    keys = [
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (300.0, 0.0, 0.0)),
        ((100.0, 0.0, 0.0), (0.5, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((-2.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    ]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "snap", [(shape, "translation", times, flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "snap"),
        tmp_path,
        clip_names=["snap"],
        once=["snap"],
    )
    expected = [(0.0, 1.0 + cubic_at(times, keys, t)[0], 1.0, 0.0) for t in ONCE_TIMES]
    assert expected[1][1] != pytest.approx(1.0, abs=0.01)
    assert_close(boxes(result)["snap"], expected)


def test_cubic_keys_closer_than_blender_merges_them(found, tmp_path):
    # The first interval is 0.0024 of a frame at Blender's 24 fps, a quarter
    # of the 0.01 frame under which Blender treats keys as one (a review
    # finding). The key between holds 0.5 for an instant; the tangents are 0,
    # so the curve then returns to 0, and the clip ends where it began.
    times = [0.0, 0.0001, 1.0]
    keys = [
        ((0.0,) * 3, (0.0,) * 3, (0.0,) * 3),
        ((0.0,) * 3, (0.5, 0.0, 0.0), (0.0,) * 3),
        ((0.0,) * 3, (0.0,) * 3, (0.0,) * 3),
    ]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "blip", [(shape, "translation", times, flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "blip"),
        tmp_path,
        clip_names=["blip"],
        once=["blip"],
    )
    expected = [(0.0, 1.0 + cubic_at(times, keys, t)[0], 1.0, 0.0) for t in ONCE_TIMES]
    assert expected[0][1] == 1.0 and expected[1][1] < 1.5
    assert_close(boxes(result)["blip"], expected)
    assert result.roots[0].travel_m == pytest.approx(0.0, abs=1e-5)


# Blender's evaluator returns a key's value for a time within about 1e-4 frame
# of that key. The tool computes cubic channels itself, so a sample a
# microsecond after a key with a steep tangent is still exact (a review
# finding). The key and the next are 32-bit exact; the sample, 0.5 s, is
# 9.5e-7 s after the first and 0.00049 s before the second.
STEEP_TIMES = [0.0, 0.4999990463256836, 0.50048828125, 1.0]


def test_a_cubic_translation_is_exact_just_after_a_key_with_a_steep_tangent(
    found, tmp_path
):
    keys = [
        ((0.0,) * 3, (0.0,) * 3, (0.0,) * 3),
        ((0.0,) * 3, (0.0,) * 3, (1024.0, 0.0, 0.0)),
        ((0.0,) * 3, (0.5, 0.0, 0.0), (0.0,) * 3),
        ((0.0,) * 3, (0.0,) * 3, (0.0,) * 3),
    ]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "steep",
        [(shape, "translation", STEEP_TIMES, flat(keys))],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "steep"),
        tmp_path,
        clip_names=["steep"],
        once=["steep"],
    )
    expected = [
        (0.0, 1.0 + cubic_at(STEEP_TIMES, keys, t)[0], 1.0, 0.0) for t in ONCE_TIMES
    ]
    # Blender's own reading of t = 0.5 would be the key's value, R = 1.
    assert expected[2][1] == pytest.approx(1.00097845, abs=1e-7)
    assert_close(boxes(result)["steep"], expected)


def test_a_cubic_weight_is_exact_just_after_a_key_with_a_steep_tangent(found, tmp_path):
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    keys = [
        ((0.0,), (0.0,), (0.0,)),
        ((0.0,), (0.0,), (1024.0,)),
        ((0.0,), (0.5,), (0.0,)),
        ((0.0,), (0.0,), (0.0,)),
    ]
    model.animation(
        "steep",
        [(face, "weights", STEEP_TIMES, flat(keys))],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "steep"),
        tmp_path,
        clip_names=["steep"],
        once=["steep"],
    )
    rows = by_clip(result)["steep"]
    weights = [cubic_at(STEEP_TIMES, keys, t)[0] for t in ONCE_TIMES]
    assert weights[2] == pytest.approx(0.00097845, abs=1e-7)
    assert_close([box[2] for _, _, box, _ in rows], [1.0 + w for w in weights])


def test_a_cubic_rotation_is_exact_just_after_a_key_with_a_steep_tangent(
    found, tmp_path
):
    # The out-tangent turns the key about z by 2·2048·9.5e-7 ≈ 0.23° by 0.5 s.
    keys = [
        ((0.0,) * 4, (0.0, 0.0, 0.0, 1.0), (0.0,) * 4),
        ((0.0,) * 4, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 2048.0, 0.0)),
        ((0.0,) * 4, (0.0, 0.0, 0.3, 0.95), (0.0,) * 4),
        ((0.0,) * 4, (0.0, 0.0, 0.0, 1.0), (0.0,) * 4),
    ]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "steep",
        [(shape, "rotation", STEEP_TIMES, flat(keys))],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "steep"),
        tmp_path,
        clip_names=["steep"],
        once=["steep"],
    )
    measured = boxes(result)["steep"]
    for got, t in zip(measured, ONCE_TIMES, strict=True):
        assert got == pytest.approx(rotation_bounds(STEEP_TIMES, keys, t), abs=1e-4)
    # At 0.5 s the key's own value (no turn) would be off by far more.
    key_only = rotation_bounds(STEEP_TIMES, keys, STEEP_TIMES[1])
    assert abs(measured[2][0] - key_only[0]) > 1e-3


def test_a_cubic_rotation_is_normalized_in_double_precision(found, tmp_path):
    # Both keys are the identity. At 0.5 s the middle of the curve is a
    # quaternion that is nearly pure x, 2.5e-22 with w cancelled to zero,
    # whose square underflows in Blender's 32 bits: a half turn about x, so
    # the triangle's top vertex lands at its bottom (a review finding).
    times = [0.0, 1.0]
    identity = (0.0, 0.0, 0.0, 1.0)
    zero = (0.0,) * 4
    tangent = 1e-21
    out, into = (tangent, 0.0, 0.0, -4.0), (-tangent, 0.0, 0.0, 4.0)
    keys = [(zero, identity, out), (into, identity, zero)]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "flip", [(shape, "rotation", times, flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "flip"),
        tmp_path,
        clip_names=["flip"],
        once=["flip"],
    )
    measured = boxes(result)["flip"]
    for got, t in zip(measured, ONCE_TIMES, strict=True):
        assert got == pytest.approx(rotation_bounds(times, keys, t), abs=1e-4)
    # The middle sample is the half turn: L, R, U, D = 0, 1, 0, 1.
    assert measured[2] == pytest.approx((0.0, 1.0, 0.0, 1.0), abs=1e-4)


@pytest.mark.parametrize("interpolation", ["LINEAR", "CUBICSPLINE"])
@pytest.mark.parametrize("rest", [(50.0, 100.0, 150.0), (256.0, 0.0, 256.0)])
@pytest.mark.parametrize("other_clip", [False, True], ids=["alone", "with a far clip"])
def test_a_joint_translated_far_from_its_bind_pose_is_measured_accurately(
    found, tmp_path, interpolation, rest, other_clip
):
    # The joint rests at `rest`, turned about z by (0, 0, 0.6, 0.8), which is
    # 73.74° with cosine 0.28 and sine 0.96; its inverse bind matrix is the
    # exact inverse of that world matrix, so the triangle weighted to it stays
    # at its own coordinates, L, R, U, D = 0, 1, 1, 0. The importer works in 32
    # bits around values in the hundreds, and the cubic channel's map has to
    # survive that, whatever an unselected clip holds the joint at: here the
    # opposite place. The second rest has key values and a bind offset at the
    # supported limit of 256 m.
    c, s = 0.28, 0.96
    x, y, z = rest
    bind = (-(c * x + s * y), -(-s * x + c * y), -z)
    model = GlbWriter()
    joint = model.node("joint", translation=rest, rotation=(0.0, 0.0, 0.6, 0.8))
    skin = model.skin([joint], [(c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0, *bind, 1)])
    skinned = model.node(
        "skinned",
        mesh=model.mesh(
            TRIANGLE,
            joints=[(0, 0, 0, 0)] * 3,
            skin_weights=[(1, 0, 0, 0)] * 3,
        ),
        skin=skin,
    )
    model.scene([joint, skinned], default=True)

    def hold(name, here):
        if interpolation == "LINEAR":
            values = [here, here]
        else:
            values = [ZERO, here, ZERO, ZERO, here, ZERO]
        model.animation(
            name,
            [(joint, "translation", [0.0, 1.0], values)],
            interpolation=interpolation,
        )

    hold("hold", rest)
    if other_clip:
        hold("far", tuple(-v for v in rest))
    result, _ = measure(
        found,
        model.write(tmp_path, "hold"),
        tmp_path,
        clip_names=["hold"],
        once=["hold"],
    )
    # The requirement is 1e-4 m.
    for box in boxes(result)["hold"]:
        assert box == pytest.approx((0.0, 1.0, 1.0, 0.0), abs=1e-4)


@pytest.mark.parametrize("interpolation", ["LINEAR", "CUBICSPLINE"])
def test_a_clip_spanning_distant_translations_is_accurate_in_every_segment(
    found, tmp_path, interpolation
):
    # The joint of the previous test, at (128, −100, 128), holds there for a
    # second, goes to twice that, at the supported limit of 256 m, and comes
    # back. Where the joint is at its rest pose (t <= 1 and t = 3) the
    # triangle is at its own coordinates, L, R, U, D = 0, 1, 1, 0.
    rest = (128.0, -100.0, 128.0)
    c, s = 0.28, 0.96
    x, y, z = rest
    bind = (-(c * x + s * y), -(-s * x + c * y), -z)
    model = GlbWriter()
    joint = model.node("joint", translation=rest, rotation=(0.0, 0.0, 0.6, 0.8))
    skin = model.skin([joint], [(c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0, *bind, 1)])
    skinned = model.node(
        "skinned",
        mesh=model.mesh(
            TRIANGLE, joints=[(0, 0, 0, 0)] * 3, skin_weights=[(1, 0, 0, 0)] * 3
        ),
        skin=skin,
    )
    model.scene([joint, skinned], default=True)
    far = tuple(2 * v for v in rest)
    keys = [rest, rest, far, rest]
    if interpolation == "CUBICSPLINE":
        keys = [row for key in keys for row in (ZERO, key, ZERO)]
    model.animation(
        "hold",
        [(joint, "translation", [0.0, 1.0, 2.0, 3.0], keys)],
        interpolation=interpolation,
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "hold"),
        tmp_path,
        clip_names=["hold"],
        once=["hold"],
    )
    rows = {time: box for _, time, box, _ in by_clip(result)["hold"]}
    assert 1.0 in rows and 3.0 in rows
    for time, box in rows.items():
        if time <= 1.0 or time == 3.0:
            assert box == pytest.approx((0.0, 1.0, 1.0, 0.0), abs=1e-4), time


def test_a_translation_that_turns_outside_its_keys_is_accurate_there(found, tmp_path):
    # The joint of the previous tests rests at (100, 64, 120). Both keys are
    # twice that, with an out-tangent of −4 times it and an in-tangent of 4
    # times it over a second: the curve dips to the rest halfway, where the
    # triangle is at its own coordinates, L, R, U, D = 0, 1, 1, 0. The map has
    # to be accurate there, away from both keys.
    rest = (100.0, 64.0, 120.0)
    c, s = 0.28, 0.96
    x, y, z = rest
    bind = (-(c * x + s * y), -(-s * x + c * y), -z)
    model = GlbWriter()
    joint = model.node("joint", translation=rest, rotation=(0.0, 0.0, 0.6, 0.8))
    skin = model.skin([joint], [(c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0, *bind, 1)])
    skinned = model.node(
        "skinned",
        mesh=model.mesh(
            TRIANGLE, joints=[(0, 0, 0, 0)] * 3, skin_weights=[(1, 0, 0, 0)] * 3
        ),
        skin=skin,
    )
    model.scene([joint, skinned], default=True)
    far = tuple(2 * v for v in rest)
    keys = [
        (ZERO, far, tuple(-4 * v for v in rest)),
        (tuple(4 * v for v in rest), far, ZERO),
    ]
    model.animation(
        "dip",
        [(joint, "translation", [0.0, 1.0], flat(keys))],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(
        found,
        model.write(tmp_path, "dip"),
        tmp_path,
        clip_names=["dip"],
        once=["dip"],
    )
    rows = {time: box for _, time, box, _ in by_clip(result)["dip"]}
    assert rows[0.5] == pytest.approx((0.0, 1.0, 1.0, 0.0), abs=1e-4)


@pytest.mark.parametrize("where", ["in no scene", "in another scene"])
def test_a_cubic_channel_on_a_node_outside_the_selected_scene(found, tmp_path, where):
    # The clip moves the subject with a cubic curve; the same clip also moves
    # a node nothing selected draws, and rotates one, with cubic curves.
    keys = [
        ((0.0,) * 3, ZERO, (4.0, 0.0, 0.0)),
        ((-4.0, 0.0, 0.0), ZERO, (0.0,) * 3),
    ]
    spin = [
        ((0.0,) * 4, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.5, 0.0)),
        ((0.0,) * 4, (0.0, 0.0, 0.5, 0.866), (0.0,) * 4),
    ]
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    stray = model.node("stray", mesh=True)
    model.scene([shape], default=True)
    if where == "in another scene":
        model.scene([stray])
    model.animation(
        "sway",
        [
            (shape, "translation", [0, 1], flat(keys)),
            (stray, "translation", [0, 1], flat(keys)),
            (stray, "rotation", [0, 1], flat(spin)),
        ],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(
        found, model.write(tmp_path, "stray"), tmp_path, clip_names=["sway"]
    )
    assert_close(
        boxes(result)["sway"],
        [(0.0, 1.0 + 4 * (t - t * t), 1.0, 0.0) for t in TIMES],
    )


def test_cubic_morph_weights_of_several_targets(found, tmp_path):
    # Two targets, one lifting U and one widening R, with different values
    # and tangents; keys at 0, 0.5 and 2 s.
    times = [0.0, 0.5, 2.0]
    keys = [
        ((0.0, 0.0), (0.0, 1.0), (2.0, -1.0)),
        ((1.0, 0.5), (0.8, 0.25), (-0.4, 1.2)),
        ((0.3, -0.6), (0.0, 0.5), (0.0, 0.0)),
    ]
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE, WIDEN], weights=[0.0, 0.0])
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    model.animation(
        "grow", [(face, "weights", times, flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(found, model.write(tmp_path, "targets"), tmp_path)
    sampled = [0.25 * k for k in range(8)]
    expected = []
    for t in sampled:
        up, wide = cubic_at(times, keys, t)
        assert min(up, wide) > -0.9
        expected.append((0.0, 1.0 + wide, 1.0 + up, 0.0))
    assert_close(boxes(result)["grow"], expected)


def joint_model():
    """Joint J1, at (0, 0.5, 0) under J0, moves a skinned body's vertex at
    (0.5, 0.5, 0); the body's other vertices are on J0."""
    model = GlbWriter()
    j1 = model.node("J1", translation=(0.0, 0.5, 0.0))
    j0 = model.node("J0", children=[j1])
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
    model.scene([j0, model.node("body", mesh=mesh, skin=skin)], default=True)
    return model, j1


def test_a_cubic_translation_of_a_joint(found, tmp_path):
    # The skinned vertex on joint J1 sets R = 0.5 + J1's x, and J1 follows
    # the cubic curve 4·(t − t²).
    model, j1 = joint_model()
    keys = [
        ((0.0,) * 3, (0.0, 0.5, 0.0), (4.0, 0.0, 0.0)),
        ((-4.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0,) * 3),
    ]
    model.animation(
        "bend", [(j1, "translation", [0, 1], flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(found, model.write(tmp_path, "joint"), tmp_path)
    assert_close(
        boxes(result)["bend"],
        [(0.0, 0.5 + 4 * (t - t * t), 0.5, 0.0) for t in TIMES],
    )


def test_a_cubic_rotation_of_a_joint(found, tmp_path):
    # J1 turns by a cubic quaternion, with tangents the importer would flip,
    # and carries the vertex 0.5 m to its right around it.
    model, j1 = joint_model()
    keys = [
        ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 3.0, -4.0)),
        ((0.0, 0.0, 3.0, -4.0), TURN, (0.0, 0.0, 0.0, 0.0)),
    ]
    model.animation(
        "bend", [(j1, "rotation", [0, 1], flat(keys))], interpolation="CUBICSPLINE"
    )
    result, _ = measure(found, model.write(tmp_path, "twist"), tmp_path)
    expected = []
    for t in TIMES:
        q = cubic_at([0.0, 1.0], keys, t)
        length = math.hypot(*q)
        x, y, _ = rotated([c / length for c in q], (0.5, 0.0, 0.0))
        xs, ys = [0.0, 0.25, x], [0.0, 0.0, 0.5 + y]
        expected.append((max(0, -min(xs)), max(0, *xs), max(0, *ys), max(0, -min(ys))))
    assert_close(boxes(result)["bend"], expected)


def share_sampler(model, clip, sampler, node, path):
    """Another channel of `clip` on `node`, reading an existing sampler."""
    model.document["animations"][clip]["channels"].append(
        {"sampler": sampler, "target": {"node": node, "path": path}}
    )


def test_channels_sharing_a_cubic_sampler_all_follow_its_tangents(found, tmp_path):
    # The upright node raises U and the mirrored one D, both from one sampler.
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    up = model.node("up", mesh=mesh)
    down = mirrored(model, mesh)
    model.scene([up, down], default=True)
    keys = [((0.0,), (0.0,), (4.0,)), ((-4.0,), (0.0,), (0.0,))]
    clip = model.animation(
        "rise", [(up, "weights", [0, 1], flat(keys))], interpolation="CUBICSPLINE"
    )
    share_sampler(model, clip, 0, down, "weights")
    result, _ = measure(found, model.write(tmp_path, "shared"), tmp_path)
    assert_close(
        boxes(result)["rise"],
        [(0.0, 1.0, 1.0 + 4 * (t - t * t), 1.0 + 4 * (t - t * t)) for t in TIMES],
    )


def test_a_cubic_mesh_weight_pointer_reaches_every_node_using_the_mesh(found, tmp_path):
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    up = model.node("up", mesh=mesh)
    down = mirrored(model, mesh)
    model.scene([up, down], default=True)
    clip = model.animation("rise", [])
    model.pointer_channel(
        clip,
        "/meshes/0/weights",
        [0, 1],
        [(0.0,), (0.0,), (4.0,), (-4.0,), (0.0,), (0.0,)],
        interpolation="CUBICSPLINE",
    )
    result, _ = measure(found, model.write(tmp_path, "cubic-pointer"), tmp_path)
    assert_close(
        boxes(result)["rise"],
        [(0.0, 1.0, 1.0 + 4 * (t - t * t), 1.0 + 4 * (t - t * t)) for t in TIMES],
    )
    assert boxes(result)["rise"][2][3] == pytest.approx(2.0, abs=1e-5)


def test_a_cubic_translation_with_sparse_tangents(found, tmp_path):
    # The output holds zeros but for the two tangents, +4 on x and −4 on x,
    # supplied as sparse replacements of rows 2 and 3.
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "sway",
        [(shape, "translation", [0, 1], [ZERO] * 6)],
        interpolation="CUBICSPLINE",
    )
    indices = model._view(struct.pack("<2H", 2, 3))
    values = model._view(struct.pack("<6f", 4, 0, 0, -4, 0, 0))
    output = model.document["animations"][0]["samplers"][0]["output"]
    model.document["accessors"][output]["sparse"] = {
        "count": 2,
        "indices": {"bufferView": indices, "componentType": 5123},
        "values": {"bufferView": values},
    }
    result, _ = measure(
        found,
        model.write(tmp_path, "sparse"),
        tmp_path,
        clip_names=["sway"],
        once=["sway"],
    )
    assert_close(
        boxes(result)["sway"],
        [(0.0, 1.0 + 4 * (t - t * t), 1.0, 0.0) for t in ONCE_TIMES],
    )


# The weight range


def curve(peak):
    """A weight curve 0 at t = 0 and t = 1 with tangents ±4·peak: it reaches
    `peak` at t = 0.5, and its Bézier handles reach 4/3 of that."""
    return [((0.0,), (0.0,), (4 * peak,)), ((-4 * peak,), (0.0,), (0.0,))]


def curve_model(tmp_path, peak):
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    model.animation(
        "rise",
        [(face, "weights", [0, 1], flat(curve(peak)))],
        interpolation="CUBICSPLINE",
    )
    return model.write(tmp_path, "curve")


def test_handles_beyond_the_limit_do_not_fail_while_every_sample_is_within(
    found, tmp_path
):
    # The peak is 8, within ±10; the handles are at 10.67.
    result, _ = measure(found, curve_model(tmp_path, 8.0), tmp_path)
    assert_close(
        [box[2] for box in boxes(result)["rise"]],
        [1.0 + 32 * (t - t * t) for t in TIMES],
    )


def test_a_sampled_cubic_weight_beyond_the_limit_fails(found, tmp_path):
    # The peak is 11.25, reached at the sample at 0.5 s.
    with pytest.raises(
        backend.BackendError, match="to 11.25 at 0.5 s, beyond Blender's ±10"
    ):
        measure(found, curve_model(tmp_path, 11.25), tmp_path)


# The supported range (design §Supported Blender version): a cubic spline
# channel inside it is measured to 1e-4 m, one just beyond it is an input error


def rest_joint_model(rest):
    """A joint at `rest`, turned about z by (0, 0, 0.6, 0.8), with a triangle
    weighted to it and an inverse bind matrix that keeps the triangle at its own
    coordinates."""
    c, s = 0.28, 0.96
    x, y, z = rest
    bind = (-(c * x + s * y), -(-s * x + c * y), -z)
    model = GlbWriter()
    joint = model.node("joint", translation=rest, rotation=(0.0, 0.0, 0.6, 0.8))
    skin = model.skin([joint], [(c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0, *bind, 1)])
    skinned = model.node(
        "skinned",
        mesh=model.mesh(
            TRIANGLE, joints=[(0, 0, 0, 0)] * 3, skin_weights=[(1, 0, 0, 0)] * 3
        ),
        skin=skin,
    )
    model.scene([joint, skinned], default=True)
    return model, joint


def refused(found, tmp_path, model, message):
    with pytest.raises(InputError, match=message) as raised:
        measure(found, model.write(tmp_path, "range"), tmp_path)
    assert raised.value.exit_code == 3
    return raised.value


def shape_model(path, keys, name="walk"):
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        name, [(shape, path, [0.0, 1.0], keys)], interpolation="CUBICSPLINE"
    )
    return model


@pytest.mark.parametrize(
    ("path", "keys", "problem"),
    [
        (
            "translation",
            [ZERO, ZERO, ZERO, ZERO, (257.0, 0.0, 0.0), ZERO],
            "has a key value of 257 m, beyond ±256 m",
        ),
        (
            "translation",
            [ZERO, ZERO, (0.0, 1028.0, 0.0), (0.0, -1028.0, 0.0), ZERO, ZERO],
            "reaches 257 m between its keys 0 and 1, beyond ±256 m",
        ),
        (
            "translation",
            [ZERO, ZERO, (10001.0, 0.0, 0.0), ZERO, ZERO, ZERO],
            "has a tangent of 10001, beyond ±10000",
        ),
        (
            "scale",
            [ZERO, (1.0, 1.0, 1.0), ZERO, ZERO, (10001.0, 1.0, 1.0), ZERO],
            "has a key value of 10001, beyond ±10000",
        ),
        (
            "rotation",
            [(0.0,) * 4, (0.0, 0.0, 0.0, 1.0), (0.0,) * 4]
            + [(0.0,) * 4, (0.0, 0.0, 0.0006, 0.0007), (0.0,) * 4],
            "has a key quaternion of length 0.000921954, below 0.001",
        ),
    ],
    ids=[
        "a translation key",
        "a translation between its keys",
        "a translation tangent",
        "a scale key",
        "a rotation key",
    ],
)
def test_a_cubic_channel_just_beyond_the_range_is_an_input_error(
    found, tmp_path, path, keys, problem
):
    error = refused(found, tmp_path, shape_model(path, keys), problem)
    assert error.problem == (
        f"animation 0 ('walk'), node 0 ('shape')'s {path} {problem}"
    )


def test_a_weight_tangent_just_beyond_the_range_is_an_input_error(found, tmp_path):
    model = GlbWriter()
    mesh = model.mesh(TRIANGLE, targets=[RISE], weights=[0.0])
    face = model.node("face", mesh=mesh)
    model.scene([face], default=True)
    keys = [((0.0,), (0.0,), (10001.0,)), ((0.0,), (0.0,), (0.0,))]
    model.animation(
        "rise", [(face, "weights", [0, 1], flat(keys))], interpolation="CUBICSPLINE"
    )
    refused(found, tmp_path, model, "has a tangent of 10001, beyond ±10000")


def test_a_bind_offset_just_beyond_the_range_is_an_input_error(found, tmp_path):
    # The joint rests 300 m from the origin; its cubic keys are all within
    # the range.
    model, joint = rest_joint_model((300.0, 0.0, 0.0))
    keys = [ZERO, ZERO, ZERO, ZERO, (1.0, 0.0, 0.0), ZERO]
    model.animation(
        "hold",
        [(joint, "translation", [0.0, 1.0], keys)],
        interpolation="CUBICSPLINE",
    )
    error = refused(
        found,
        tmp_path,
        model,
        r"animation 0 \('hold'\), node 0 \('joint'\)'s translation "
        r"has a bind offset of -?\d+(\.\d+)? m, beyond ±256 m",
    )
    assert "beyond ±256 m" in error.problem


def test_a_rotation_key_at_the_limit_of_a_thousandth_is_measured_exactly(
    found, tmp_path
):
    # Both keys are the quarter turn's quaternion at a length of 0.001, which
    # is normalized in double precision before it reaches Blender.
    length = 0.001 * 1.000001
    zero = (0.0,) * 4
    key = (0.0, 0.0, 0.6 * length, 0.8 * length)
    assert math.hypot(*key) >= 0.001
    keys = [(zero, key, zero), (zero, key, zero)]
    model = shape_model("rotation", flat(keys), "turn")
    result, _ = measure(
        found,
        model.write(tmp_path, "turn"),
        tmp_path,
        clip_names=["turn"],
        once=["turn"],
    )
    for got, t in zip(boxes(result)["turn"], ONCE_TIMES, strict=True):
        assert got == pytest.approx(rotation_bounds([0.0, 1.0], keys, t), abs=1e-4)
    assert boxes(result)["turn"][0] != pytest.approx((0.0, 1.0, 1.0, 0.0), abs=1e-2)


def test_a_cubic_scale_at_the_limit_is_measured(found, tmp_path):
    zero = (0.0, 0.0, 0.0)
    wide = (10000.0, 1.0, 1.0)
    model = shape_model("scale", [zero, wide, zero, zero, wide, zero], "grow")
    result, _ = measure(
        found,
        model.write(tmp_path, "grow"),
        tmp_path,
        clip_names=["grow"],
        once=["grow"],
    )
    for box in boxes(result)["grow"]:
        assert box == pytest.approx((0.0, 10000.0, 1.0, 0.0), rel=1e-6)


def test_a_cubic_translation_at_the_limit_travels_exactly(found, tmp_path):
    # Both keys are 0, with an out-tangent of 1024 and an in-tangent of −1024
    # over a second: x is 1024·(t − t²), peaking at exactly 256 m at 0.5 s,
    # where the triangle's R is 257.
    keys = [ZERO, ZERO, (1024.0, 0.0, 0.0), (-1024.0, 0.0, 0.0), ZERO, ZERO]
    model = shape_model("translation", keys, "reach")
    result, _ = measure(
        found,
        model.write(tmp_path, "reach"),
        tmp_path,
        clip_names=["reach"],
        once=["reach"],
    )
    rows = boxes(result)["reach"]
    expected = [(0.0, 1.0 + 1024 * t * (1 - t), 1.0, 0.0) for t in ONCE_TIMES]
    assert expected[2][1] == 257.0
    for got, want in zip(rows, expected, strict=True):
        assert got == pytest.approx(want, abs=1e-4)


# Rendering


def test_a_render_places_a_cubic_translation_at_its_tangent_correct_pose(
    found, tmp_path
):
    # The cube's keys are both at the origin, with tangents ±1.6: x is
    # 1.6·(t − t²), 0.4 m at t = 0.5, where Blender's automatic handles would
    # keep it at 0. At 20 px per meter in the supersampled image the cube is
    # 8 px right of the ground pixel (20, 20).
    model = GlbWriter()
    mover = model.node(
        "mover", mesh=model.mesh(cube((0.0, 0.0, 0.0), 0.08), material=model.material())
    )
    model.scene([mover], default=True)
    keys = [
        ((0.0,) * 3, ZERO, (1.6, 0.0, 0.0)),
        ((-1.6, 0.0, 0.0), ZERO, (0.0,) * 3),
    ]
    model.animation(
        "swing",
        [(mover, "translation", [0, 1], flat(keys))],
        interpolation="CUBICSPLINE",
    )
    result, _ = render(found, model.write(tmp_path, "swing"), tmp_path)
    rendered = list(images(result).items())
    assert [address.time_s for address, _ in rendered] == TIMES
    for (_, image), t in zip(rendered, TIMES, strict=True):
        x = 20 + 1.6 * (t - t * t) * 20
        assert centroid(image, lambda r, g, b: True) == pytest.approx(
            (x, 20), abs=TOLERANCE_PX
        )
    assert centroid(rendered[2][1], lambda r, g, b: True)[0] == pytest.approx(
        28, abs=TOLERANCE_PX
    )


def test_a_render_is_exact_just_after_a_key_with_a_steep_tangent(found, tmp_path):
    # An out-tangent of 1e4 per second, the supported limit, moves the cube
    # 0.0095 m in the 9.5e-7 s between the key and the sample at 0.5 s. At 100
    # pixels per meter in the supersampled image that is 1.9 px; Blender's own
    # reading of that time is the key's value, at the ground pixel.
    model = GlbWriter()
    mover = model.node(
        "mover", mesh=model.mesh(cube((0.0, 0.0, 0.0), 0.08), material=model.material())
    )
    model.scene([mover], default=True)
    keys = [
        ((0.0,) * 3, ZERO, ZERO),
        ((0.0,) * 3, ZERO, (1e4, 0.0, 0.0)),
        (ZERO, (0.3, 0.0, 0.0), ZERO),
        (ZERO, ZERO, ZERO),
    ]
    model.animation(
        "steep",
        [(mover, "translation", STEEP_TIMES, flat(keys))],
        interpolation="CUBICSPLINE",
    )
    result, _ = render(
        found,
        model.write(tmp_path, "steep"),
        tmp_path,
        ppm=100.0,
        cell=(80, 80),
        ground_px=(40, 40),
    )
    rendered = list(images(result).items())
    assert [address.time_s for address, _ in rendered] == TIMES
    for (_, image), t in zip(rendered, TIMES, strict=True):
        x = 80 + cubic_at(STEEP_TIMES, keys, t)[0] * 200
        assert centroid(image, lambda r, g, b: True) == pytest.approx(
            (x, 80), abs=TOLERANCE_PX
        )
    assert cubic_at(STEEP_TIMES, keys, 0.5)[0] == pytest.approx(0.0095, abs=5e-4)
