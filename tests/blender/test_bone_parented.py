"""Meshes parented to a bone, under a scaled armature, in real Blender.

The rig: an armature node scaled by S holds the joints `hips` and its child
`thigh`, which a small skinned triangle makes bones. A box mesh is the child
of `thigh`, so the importer parents its object to the bone. Its clip `kick`
turns the thigh 90° about +Z and animates the box's own translation,
rotation and scale. Every node offset is divided by S, so the world-space
geometry is the same at every scale.

Expected positions come from glTF's own TRS maths, worked out here. Samples
fall on keyframes, where Blender's per-channel quaternion interpolation is
exact. With Blender's default bone heuristic the box was misplaced by
bone length × (S − 1); scale 1 is the control.
"""

import hashlib
import math

import pytest
from glb_writer import GlbWriter
from PIL import Image

from moskophoros import gltf, sampling, views
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

TOLERANCE_M = 1e-4
TOLERANCE_PX = 0.35
RED = (1.0, 0.0, 0.0, 1.0)
GREEN = (0.0, 1.0, 0.0, 1.0)
HALF = math.sqrt(0.5)
# The box's half extents, unequal so that its own rotation shows.
BOX = (0.05, 0.02, 0.03)
# The skinned triangle, in world coordinates: it sits at the hips.
TRIANGLE = [(-0.02, 1.0, 0.0), (0.0, 1.0, 0.0), (-0.01, 1.02, 0.0)]
# Each node's translation, rotation and scale at t = 0 and t = 1, in world
# units; the rig divides translations by S.
HIPS = ((0.0, 1.0, 0.0), (0, 0, 0, 1), (1, 1, 1))
THIGH = {
    0.0: ((0.0, -0.5, 0.0), (0, 0, 0, 1), (1, 1, 1)),
    1.0: ((0.0, -0.5, 0.0), (0, 0, HALF, HALF), (1, 1, 1)),
}
BOX_NODE = {
    0.0: ((0.3, 0.0, 0.0), (0, 0, 0, 1), (1, 1, 1)),
    1.0: ((0.3, 0.1, 0.0), (0, 0, HALF, HALF), (2, 1.5, 1)),
}


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def box_triangles(half):
    hx, hy, hz = half
    corners = [(x, y, z) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4)]
    faces.append((1, 5, 7, 3))
    return [corners[i] for a, b, c, d in faces for i in (a, b, c, a, c, d)]


def rig(tmp_path, scale):
    s = scale
    model = GlbWriter()

    def node_trs(trs):
        translation, rotation, size = trs
        return {
            "translation": tuple(v / s for v in translation),
            "rotation": rotation,
            "scale": size,
        }

    box = model.node(
        "box",
        mesh=model.mesh(
            box_triangles(tuple(v / s for v in BOX)), material=model.material(RED)
        ),
        **node_trs(BOX_NODE[0.0]),
    )
    thigh = model.node("thigh", children=[box], **node_trs(THIGH[0.0]))
    hips = model.node("hips", children=[thigh], **node_trs(HIPS))
    # Each inverse bind matrix undoes its joint's world matrix, so the
    # triangle's vertices are its world positions.
    skin = model.skin(
        [hips, thigh],
        [
            (1 / s, 0, 0, 0, 0, 1 / s, 0, 0, 0, 0, 1 / s, 0, 0, -1 / s, 0, 1),
            (1 / s, 0, 0, 0, 0, 1 / s, 0, 0, 0, 0, 1 / s, 0, 0, -0.5 / s, 0, 1),
        ],
    )
    skinned = model.node(
        "skinned",
        mesh=model.mesh(
            TRIANGLE,
            joints=[(0, 0, 0, 0)] * 3,
            skin_weights=[(1, 0, 0, 0)] * 3,
            material=model.material(GREEN),
        ),
        skin=skin,
    )
    armature = model.node("armature", scale=(s, s, s), children=[hips, skinned])
    model.scene([armature], default=True)

    def keys(trs, index):
        return [
            tuple(v / s for v in trs[t][0]) if index == 0 else trs[t][index]
            for t in (0.0, 1.0)
        ]

    model.animation(
        "kick",
        [
            (thigh, "rotation", [0.0, 1.0], keys(THIGH, 1)),
            (box, "translation", [0.0, 1.0], keys(BOX_NODE, 0)),
            (box, "rotation", [0.0, 1.0], keys(BOX_NODE, 1)),
            (box, "scale", [0.0, 1.0], keys(BOX_NODE, 2)),
        ],
    )
    return model.write(tmp_path, f"rig{scale}")


def rotate(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    # v + 2·q×(q×v + w·v), for a unit quaternion
    cx, cy, cz = (
        y * vz - z * vy + w * vx,
        z * vx - x * vz + w * vy,
        x * vy - y * vx + w * vz,
    )
    return (
        vx + 2 * (y * cz - z * cy),
        vy + 2 * (z * cx - x * cz),
        vz + 2 * (x * cy - y * cx),
    )


def apply(trs, point):
    translation, rotation, size = trs
    scaled = tuple(p * k for p, k in zip(point, size, strict=True))
    turned = rotate(rotation, scaled)
    return tuple(a + b for a, b in zip(turned, translation, strict=True))


def box_world(point, t):
    """A point in the box's local, world-unit frame, carried through the box,
    thigh and hips transforms at time `t`."""
    return apply(HIPS, apply(THIGH[t], apply(BOX_NODE[t], point)))


def expected_bounds(t):
    hx, hy, hz = BOX
    corners = [
        box_world((x, y, z), t) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)
    ]
    points = corners + TRIANGLE
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    # Direction 0 at pitch 0, ground at the origin: right is +X, up is +Y.
    return (max(0, -min(xs)), max(0, *xs), max(0, *ys), max(0, -min(ys)))


def run(found, path, tmp_path, mode, **fitted):
    subject = gltf.read_glb(path)
    clips = gltf.select_clips(subject, ["kick"], ["kick"])
    settings = backend.Settings(
        "custom",
        0.0,
        1,
        0.0,
        0.0,
        1.0,
        2 if mode == "render" else 1,
        fitted.get("ppm"),
        fitted.get("cell"),
        (0.0, 0.0, 0.0),
        fitted.get("ground_px"),
        "error",
    )
    frames = sampling.frames(
        subject.name, clips, views.View(0.0, 1, 0.0, 0.0), settings.fps
    )
    root = tmp_path / mode
    root.mkdir()
    source = backend.Source(
        path.resolve(),
        hashlib.sha256(path.read_bytes()).hexdigest(),
        subject.scene_index,
    )
    job = backend.build_job(
        mode, source, subject.name, settings, clips, frames, str(root / mode)
    )
    return blender.run_phase(found, root, job)


SCALES = [1, 2, 100]


@pytest.mark.parametrize("scale", SCALES)
def test_measured_bounds_match_gltf(found, tmp_path, scale):
    result = run(found, rig(tmp_path, scale), tmp_path, "measure")
    # One-shot at 1 fps: samples at t = 0 (the static pose) and t = 1.
    measured = {
        address.time_s: measurement.bounds
        for address, measurement in result.measurements.items()
    }
    assert sorted(measured) == [0.0, 1.0]
    for t, bounds in measured.items():
        got = (bounds.left, bounds.right, bounds.up, bounds.down)
        assert got == pytest.approx(expected_bounds(t), abs=TOLERANCE_M), t


PPM = 100.0
CELL = (120, 120)
GROUND_PX = (40, 110)
SUPERSAMPLE = 2


def red_centroid(path):
    with Image.open(path) as image:
        pixels = image.convert("RGBA").load()
        total = sx = sy = 0.0
        for y in range(image.height):
            for x in range(image.width):
                r, g, b, a = pixels[x, y]
                if a and r > g and r > b:
                    total += a
                    sx += a * (x + 0.5)
                    sy += a * (y + 0.5)
    assert total, "no red pixels"
    return sx / total, sy / total


@pytest.mark.parametrize("scale", SCALES)
def test_rendered_box_lands_where_gltf_puts_it(found, tmp_path, scale):
    result = run(
        found,
        rig(tmp_path, scale),
        tmp_path,
        "render",
        ppm=PPM,
        cell=CELL,
        ground_px=GROUND_PX,
    )
    rendered = {
        address.time_s: buffers["color"] for address, buffers in result.buffers.items()
    }
    assert sorted(rendered) == [0.0, 1.0]
    for t, path in rendered.items():
        cx, cy, _ = box_world((0.0, 0.0, 0.0), t)
        expected = (
            (GROUND_PX[0] + cx * PPM) * SUPERSAMPLE,
            (GROUND_PX[1] - cy * PPM) * SUPERSAMPLE,
        )
        assert red_centroid(path) == pytest.approx(expected, abs=TOLERANCE_PX), t
