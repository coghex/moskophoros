"""The back layer's normal is kept on every render (shading design D-37;
design §Capture): `back_normal` holds the camera-space normal of the back
layer's first opaque surface, present exactly where the back colour is, while
`normal` and `depth` still describe the front-most surface."""

import math

import numpy as np
import pytest
from material_models import QUAD_UV, Model, checker, quad_xy
from PIL import Image
from test_render import render

from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

PPM = 10.0
CELL = (24, 12)
GROUND_PX = (12, 9)
SLOPE = 0.5
# The tilted body's normal, in camera space: its plane z = SLOPE · x faces
# +Z leaning toward −X.
TILTED = (-SLOPE / math.hypot(SLOPE, 1), 0.0, 1 / math.hypot(SLOPE, 1))
FRONT_ON = (0.0, 0.0, 1.0)
OPTIONS = dict(ppm=PPM, cell=CELL, ground_px=GROUND_PX, supersample=1)


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def tilted_quad(x0, y0, x1, y1):
    """A rectangle in the plane z = SLOPE · x, facing +Z."""
    z0, z1 = SLOPE * x0, SLOPE * x1
    return [
        (x0, y0, z0),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y0, z0),
        (x1, y1, z1),
        (x0, y1, z0),
    ]


def overlap(directory):
    """Three columns: a translucent veil over a tilted body (left), a veil
    alone (middle) and the tilted body alone (right)."""
    model = Model()
    veil = model.material("veil", (1, 0, 0, 0.4), alpha_mode="BLEND")
    body = model.material("body", (0.1, 0.2, 0.9, 1))
    model.primitive(quad_xy(-1.1, 0.0, -0.5, 0.6, 0.9), veil)
    model.primitive(tilted_quad(-1.1, 0.0, -0.5, 0.6), body)
    model.primitive(quad_xy(-0.3, 0.0, 0.3, 0.6, 0.9), veil)
    model.primitive(tilted_quad(0.5, 0.0, 1.1, 0.6), body)
    return model.write(directory, "overlap")


def pixel(x, y):
    """The (row, column) of the pixel at world (x, y) in front view."""
    return GROUND_PX[1] - round(y * PPM), GROUND_PX[0] + round(x * PPM)


def decoded(paths, name):
    return backend.decode_normal(backend.read_wide_png(paths[name]))


def only_frame(result):
    (paths,) = result.buffers.values()
    return paths


def test_distinct_layer_normals_survive_a_translucent_overlap(found, tmp_path):
    result, _ = render(found, overlap(tmp_path), tmp_path, **OPTIONS)
    paths = only_frame(result)
    back, front_most = decoded(paths, "back_normal"), decoded(paths, "normal")
    # Over the body: the back is the body's tilted normal, the front-most the
    # veil's.
    row, column = pixel(-0.8, 0.3)
    np.testing.assert_allclose(back[row, column], TILTED, atol=1e-3)
    np.testing.assert_allclose(front_most[row, column], FRONT_ON, atol=1e-3)
    # Beside it, the veil alone: no back surface, and so no back normal.
    row, column = pixel(0.0, 0.3)
    assert (back[row, column] == 0).all()
    np.testing.assert_allclose(front_most[row, column], FRONT_ON, atol=1e-3)
    # The body alone: both are its normal.
    row, column = pixel(0.8, 0.3)
    np.testing.assert_allclose(back[row, column], TILTED, atol=1e-3)
    np.testing.assert_array_equal(back[row, column], front_most[row, column])
    # Nowhere else is there a back normal.
    row, column = pixel(0.0, -0.2)
    assert (back[row, column] == 0).all() and (front_most[row, column] == 0).all()


def test_the_back_normal_is_present_exactly_where_the_back_colour_is(found, tmp_path):
    result, _ = render(found, overlap(tmp_path), tmp_path, **OPTIONS)
    paths = only_frame(result)
    with Image.open(paths["color"]) as image:
        colour = np.asarray(image)[..., 3] == 255
    raw = backend.read_wide_png(paths["back_normal"])
    assert colour.any() and (colour != (raw[..., 3] == backend.SURFACE)).sum() == 0
    assert (raw[~colour] == 0).all()
    lengths = np.linalg.norm(
        decoded(paths, "back_normal")[colour].astype(float), axis=-1
    )
    assert np.abs(lengths - 1).max() < backend.NORMAL_TOLERANCE
    # The front-most buffers still cover either layer: the veil alone shows.
    row, column = pixel(0.0, 0.3)
    assert not colour[row, column]
    assert backend.read_wide_png(paths["normal"])[row, column, 3] == backend.SURFACE


def test_a_render_without_a_front_has_the_back_normal_as_its_normal(found, tmp_path):
    model = Model()
    body = model.material("body", (0.1, 0.2, 0.9, 1))
    model.primitive(tilted_quad(-1.0, 0.0, 1.0, 0.6), body)
    path = model.write(tmp_path, "opaque")
    result, _ = render(found, path, tmp_path, **OPTIONS)
    paths = only_frame(result)
    assert paths["back_normal"].read_bytes() == paths["normal"].read_bytes()
    row, column = pixel(0.0, 0.3)
    np.testing.assert_allclose(
        decoded(paths, "back_normal")[row, column], TILTED, atol=1e-3
    )


def test_a_cutout_has_a_back_normal_only_where_it_is_kept(found, tmp_path):
    model = Model()
    texture = model.texture((8, 8), checker)
    mask = model.material(
        "mask", (1, 1, 1, 1), alpha_mode="MASK", cutoff=0.5, texture=texture
    )
    model.primitive(quad_xy(-1.0, 0.0, 1.0, 0.8, 0.0), mask, texcoords=QUAD_UV)
    path = model.write(tmp_path, "cutout")
    result, _ = render(found, path, tmp_path, **OPTIONS)
    paths = only_frame(result)
    with Image.open(paths["color"]) as image:
        kept = np.asarray(image)[..., 3] == 255
    assert kept.any() and not kept.all()
    raw = backend.read_wide_png(paths["back_normal"])
    assert ((raw[..., 3] == backend.SURFACE) == kept).all()
    assert (raw[~kept] == 0).all()
    np.testing.assert_allclose(
        decoded(paths, "back_normal")[kept],
        np.broadcast_to(FRONT_ON, (int(kept.sum()), 3)),
        atol=1e-3,
    )


def test_repeats_and_a_frame_alone_or_in_a_sequence_give_the_same_bytes(
    found, tmp_path
):
    path = overlap(tmp_path)
    first, _ = render(found, path, tmp_path, workspace="one", **OPTIONS)
    second, _ = render(found, path, tmp_path, workspace="two", **OPTIONS)
    assert (
        only_frame(first)["back_normal"].read_bytes()
        == only_frame(second)["back_normal"].read_bytes()
    )
    # Three directions: 0°, 120° and 240°. Direction 1 alone starts at 120°.
    sequence, _ = render(
        found, path, tmp_path, workspace="three", directions=3, **OPTIONS
    )
    alone, _ = render(found, path, tmp_path, workspace="alone", start=120.0, **OPTIONS)
    frames = list(sequence.buffers.values())
    assert len(frames) == 3
    assert (
        frames[1]["back_normal"].read_bytes()
        == only_frame(alone)["back_normal"].read_bytes()
    )
    assert (
        frames[0]["back_normal"].read_bytes()
        == only_frame(first)["back_normal"].read_bytes()
    )
    assert (
        frames[1]["back_normal"].read_bytes() != frames[0]["back_normal"].read_bytes()
    )
