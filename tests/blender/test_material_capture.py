"""The material-ID and shade buffers on generated models, in real Blender
(design §Capture; material styling design §Spike record (D-10), D-25, D-26).

Positions are worked out from the fixtures' known geometry: in front view
(pitch 0, one direction, the ground point at the origin and on `GROUND_PX`),
a point (x, y) lands at pixel (gx + x·ppm, gy − y·ppm), times the supersample.
"""

import numpy as np
import pytest
from glb_writer import GlbWriter
from material_models import EDGES, appearance, edges, form, quad_xy
from PIL import Image
from test_render import render

from moskophoros import gltf
from moskophoros.capture import backend, blender
from moskophoros.sampling import BACKGROUND

pytestmark = pytest.mark.blender

PPM = 40.0
CELL = (96, 128)
GROUND_PX = (48, 100)


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def pixels(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA")).astype(np.int64)


def codes(result, ordinal=0):
    """Frame `ordinal`'s material-ID codes, 0 for background."""
    ids = pixels(list(result.buffers.values())[ordinal]["matid"])
    return np.where(ids[..., 3] == 255, ids[..., 0] << 8 | ids[..., 1], 0)


def at(x, y, supersample):
    """The supersampled pixel (row, column) a front-view point lands in."""
    column = int((GROUND_PX[0] + x * PPM) * supersample)
    row = int((GROUND_PX[1] - y * PPM) * supersample)
    return row, column


def front(found, path, tmp_path, supersample, workspace="work"):
    return render(
        found,
        path,
        tmp_path,
        ppm=PPM,
        cell=CELL,
        ground_px=GROUND_PX,
        supersample=supersample,
        workspace=workspace,
    )


# The spike's cases: material edges, a thin feature, a MASK material in front
# of a second, occlusion, at supersample 1 and 16.


@pytest.mark.parametrize("supersample", [1, 16])
def test_the_material_id_buffer_is_exact_and_its_table_maps_the_gltf_materials(
    found, tmp_path, supersample
):
    path = edges(tmp_path)
    result, _ = front(found, path, tmp_path, supersample)
    assert result.materials == {i + 1: i for i in range(9)} | {65535: None}
    image = codes(result)
    code = {name: index + 1 for name, index in EDGES.items()}
    expected = {
        (-0.7, 0.5): code["left"],
        (0.5, 0.5): code["right"],
        (-0.5, 1.6): code["mask"],
        (0.55, 1.6): code["occluder"],
        (0.2, 1.2): code["occluded"],
        (-0.5, -0.5): code["glass"],
        (0.5, -0.5): backend.NO_MATERIAL_ID,
    }
    for point, value in expected.items():
        assert image[at(*point, supersample)] == value, point
    used = set(np.unique(image).tolist())
    # Every code is a table entry or background; the unused material and the
    # surface wholly behind the MASK material never show.
    assert used <= set(result.materials) | {0}
    assert code["unused"] not in used and code["behind"] not in used
    # Two materials meet along x = 0 with no pixel of anything else between.
    row = at(0.0, 0.5, supersample)[0]
    left, right = at(-0.45, 0.5, supersample)[1], at(0.45, 0.5, supersample)[1]
    assert set(image[row, left:right].tolist()) == {code["left"], code["right"]}
    # The strip is 0.4 px wide at supersample 1: no pixel centre falls on it,
    # so the ID misses it, as accepted; at 16 it is several pixels wide.
    strip = (image == code["strip"]).sum()
    assert strip == 0 if supersample == 1 else strip > 0


def test_a_mask_material_is_opaque_in_colour_id_and_shade(found, tmp_path):
    # D-26: no cutouts. Where the MASK texture is transparent, the colour shows
    # the MASK material opaque, and so do the ID and the shade.
    path = edges(tmp_path)
    result, _ = front(found, path, tmp_path, 4)
    buffers = list(result.buffers.values())[0]
    color, shade = pixels(buffers["color"]), pixels(buffers["shade"])
    image = codes(result)
    top, left = at(-0.95, 2.05, 4)
    bottom, right = at(-0.05, 1.15, 4)
    region = (slice(top, bottom), slice(left, right))
    assert (image[region] == EDGES["mask"] + 1).all()
    assert (color[region][..., 3] == 255).all()
    assert (shade[region][..., 3] == 255).all()
    # The texture's transparent cells are there: dark texels in the colour.
    assert (color[region][..., 0] < 100).any() and (color[region][..., 0] > 150).any()


def test_identities_decode_duplicate_unnamed_missing_and_blend_materials(
    found, tmp_path
):
    path = edges(tmp_path)
    result, _ = front(found, path, tmp_path, 1)
    subject = gltf.read_glb(path)
    lookup = backend.material_lookup(result, subject)
    assert lookup.identities.names == ("steel", "cloth", "wire", "leaf", "bark")
    identity, shade = backend.decode_frame(list(result.buffers.values())[0], lookup)
    none = lookup.identities.no_identity
    expected = {
        (-0.7, 0.5): 0,  # steel
        (0.55, 1.6): 0,  # the second material named steel pools into it
        (0.5, 0.5): 1,  # cloth
        (-0.5, 1.6): 3,  # leaf (MASK)
        (0.2, 1.2): none,  # unnamed
        (-0.5, -0.5): none,  # BLEND
        (0.5, -0.5): none,  # no material
    }
    for point, value in expected.items():
        assert identity[at(*point, 1)] == value, point
    assert identity[0, 0] == BACKGROUND and shade[0, 0] == 0


def test_repeat_renders_are_byte_identical(found, tmp_path):
    path = edges(tmp_path)
    first, _ = front(found, path, tmp_path, 2, "first")
    second, _ = front(found, path, tmp_path, 2, "second")
    for a, b in zip(first.buffers.values(), second.buffers.values(), strict=True):
        for name in ("color", "matid", "shade"):
            assert a[name].read_bytes() == b[name].read_bytes(), name


def test_the_shade_ignores_colour_texture_metallic_and_roughness(found, tmp_path):
    plain = form(tmp_path)
    varied = appearance(tmp_path)
    options = dict(pitch=30.0, ppm=40.0, cell=(128, 112), ground_px=(64, 80))
    first, _ = render(found, plain, tmp_path, supersample=1, workspace="a", **options)
    second, _ = render(found, varied, tmp_path, supersample=1, workspace="b", **options)
    (a,), (b,) = first.buffers.values(), second.buffers.values()
    assert a["shade"].read_bytes() == b["shade"].read_bytes()
    assert a["matid"].read_bytes() == b["matid"].read_bytes()
    assert a["color"].read_bytes() != b["color"].read_bytes()


# D-25: a flat open surface, a crease and an isolated convex curve take
# different bands after the 8-bit encoding and the fixed range.


def _distance_to(mask, limit):
    """Each pixel's Chebyshev distance to `mask`, capped at `limit`."""
    distance = np.full(mask.shape, limit)
    reached = mask.copy()
    for step in range(limit):
        distance[reached & (distance == limit)] = step
        grown = reached.copy()
        grown[1:] |= reached[:-1]
        grown[:-1] |= reached[1:]
        grown[:, 1:] |= reached[:, :-1]
        grown[:, :-1] |= reached[:, 1:]
        reached = grown
    return distance


def band(value, lo, hi, n):
    value = min(max(value, lo), hi)
    return (value - lo) * n // (hi - lo + 1)


@pytest.mark.parametrize("supersample", [1, 4])
def test_flat_crease_and_convex_take_different_bands(found, tmp_path, supersample):
    # The spike's recorded settings and regions (material styling design
    # §Spike record (D-10)): floor 1, wall 2 and sphere 3 are material codes.
    path = form(tmp_path)
    result, _ = render(
        found,
        path,
        tmp_path,
        pitch=30.0,
        ppm=40.0,
        cell=(128, 112),
        ground_px=(64, 80),
        supersample=supersample,
    )
    image = codes(result)
    shade = pixels(list(result.buffers.values())[0]["shade"])[..., 0]
    s = supersample
    floor, wall, ball = image == 1, image == 2, image == 3
    meeting = (floor & (_distance_to(wall, 2) <= 1)) | (
        wall & (_distance_to(floor, 2) <= 1)
    )
    limit = 40 * s
    to_crease, to_ball = _distance_to(meeting, limit), _distance_to(ball, limit)
    to_background = _distance_to(image == 0, limit)
    clear = (to_ball >= 8 * s) & (to_background >= 3 * s)
    regions = {
        "crease": (floor | wall) & (to_crease <= max(1, s // 2)) & clear,
        "flat": (floor | wall) & (to_crease >= 12 * s) & clear,
        "convex": ball,
    }
    means = {name: float(shade[mask].mean()) for name, mask in regions.items()}
    assert means["flat"] == 137.0
    assert means["crease"] < means["flat"] < means["convex"]
    lo, hi = backend.DEFAULT_SHADE_RANGE
    assert (lo, hi) == (84, 191)
    for n in (3, 4, 5):
        bands = [
            band(round(means[name]), lo, hi, n) for name in ("crease", "flat", "convex")
        ]
        assert bands[0] < bands[1] < bands[2], (n, means, bands)


# Colour: unchanged by the auxiliary render before it.


def test_a_frame_s_buffers_are_the_same_alone_and_within_a_sequence(found, tmp_path):
    path = form(tmp_path)
    options = dict(pitch=30.0, ppm=40.0, cell=(128, 112), ground_px=(64, 80))
    sequence, _ = render(
        found, path, tmp_path, directions=8, supersample=2, workspace="seq", **options
    )
    alone, _ = render(
        found, path, tmp_path, start=225.0, supersample=2, workspace="one", **options
    )
    within = list(sequence.buffers.values())[5]
    (single,) = alone.buffers.values()
    for name in ("color", "matid", "shade"):
        assert within[name].read_bytes() == single[name].read_bytes(), name


# The ID encoding across both bytes.


def test_the_encoding_is_exact_across_both_bytes(found, tmp_path):
    """300 materials take codes 1–300, so the low byte takes every value and
    the high byte carries from 0 to 1 between codes 255 and 256; a primitive
    without a material takes the largest code, 65535 (high and low byte 255)."""
    model = GlbWriter()
    meshes = model.document.setdefault("meshes", [])
    meshes.append({"primitives": []})
    count, side, size = 300, 18, 0.1
    model.document["materials"] = [
        {"pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1]}}
        for _ in range(count)
    ]
    for i in range(count):
        x, y = (i % side) * size, (i // side) * size
        quad = quad_xy(x, y, x + size, y + size, 0.0)
        meshes[0]["primitives"].append(
            {
                "attributes": {"POSITION": model._accessor("VEC3", quad, True)},
                "material": i,
            }
        )
    bare = quad_xy(0.0, -0.3, side * size, -0.1, 0.0)
    meshes[0]["primitives"].append(
        {"attributes": {"POSITION": model._accessor("VEC3", bare, True)}}
    )
    node = model.node("grid", mesh=0)
    model.scene([node], default=True)
    path = model.write(tmp_path, "grid")
    result, _ = render(
        found,
        path,
        tmp_path,
        ppm=100.0,
        cell=(200, 220),
        ground_px=(10, 200),
        supersample=1,
    )
    used = set(np.unique(codes(result)).tolist()) - {0}
    assert used == set(range(1, count + 1)) | {65535}
    assert {255, 256, 65535} <= used
    assert {code & 0xFF for code in used} == set(range(256))
    assert {code >> 8 for code in used} == {0, 1, 255}
