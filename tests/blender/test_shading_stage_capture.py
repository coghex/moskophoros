"""Captured frames reach the shading stage (SHD-5; shading design D-34, D-37):
opaque, cutout and translucent models rendered in real Blender, loaded as the
command loads them, and shaded by internally supplied responses, with no
public control. Positions come from the fixtures' known geometry."""

import math

import numpy as np
import pytest
from material_models import QUAD_UV, Model, checker, quad_xy
from test_layer_normals_capture import (
    FRONT_ON,
    OPTIONS,
    TILTED,
    overlap,
    pixel,
    tilted_quad,
)
from test_layers import over
from test_render import render

from moskophoros import (
    cli,
    gltf,
    lighting,
    materials,
    settings,
    shading_resolve,
    stylize,
)
from moskophoros.capture import backend, blender
from moskophoros.sampling import (
    BACK_NORMAL,
    DEPTH_MAP,
    FRONT_ALPHA,
    FRONT_COLOR,
    FRONT_NORMAL,
    NORMAL_MAP,
)

pytestmark = pytest.mark.blender

KEY = (0.6, 0.0, 0.8)
LIGHTS = lighting.Lights(key=KEY, sky=(0.0, 1.0, 0.0), ground=(0.0, -1.0, 0.0))
GLOBALS = {**settings.DEFAULTS, **settings.SHADING_DEFAULTS}
# Full-strength key, no ambient form, brightness from 0 to 1: a layer's gain is
# its normal's facing term, so what each layer was given shows in its colour.
LIT = {
    "shade.mode": "brightness",
    "shade.ambient_form": False,
    "shade.key.strength": 1.0,
    "shade.brightness.floor": 0.0,
}
PALETTE = [(i * 30, 255 - i * 30, 40 + i * 20) for i in range(8)]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def srgb(byte):
    c = byte / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def scaled(colour, gain):
    out = []
    for c in colour:
        x = srgb(int(c)) * gain
        s = 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
        out.append(min(255, math.floor(255 * s + 0.5)))
    return tuple(out)


def facing(normal):
    return float(lighting.facing(np.asarray(normal, np.float64), KEY))


def captured(found, path, tmp_path):
    """The one frame of `path`, loaded as the command loads it, and the
    asset's identities."""
    result, _ = render(found, path, tmp_path, **OPTIONS)
    lookup = backend.material_lookup(result, gltf.read_glb(path))
    ((address, paths),) = result.buffers.items()
    return cli._load_frame(address, paths, {}, lookup), lookup.identities


def reduce(frame, identities, *, values=None, library=None, palette=None):
    """The frame reduced with the supplied response (none, if `values` is
    None), plain, one supersample to a pixel."""
    options = dict(
        identities=identities,
        palette=palette,
        library=library,
        shade_range=settings.DEFAULTS["shade.range"],
        pixels_per_meter=OPTIONS["ppm"],
    )
    if values is not None:
        options.update(
            shading=shading_resolve.resolve(
                {**GLOBALS, **values}, library, has_palette=palette is not None
            ),
            lights=LIGHTS,
        )
    (reduced,) = stylize.plain([frame], 1, **options)
    return reduced


def colour_at(reduced, x, y):
    return tuple(int(v) for v in reduced.pixels[pixel(x, y)])


def tilted_body(tmp_path):
    model = Model()
    body = model.material("body", (0.1, 0.2, 0.9, 1))
    model.primitive(tilted_quad(-1.0, 0.0, 1.0, 0.6), body)
    return model.write(tmp_path, "opaque")


def test_an_opaque_surface_is_lit_by_its_own_normal(found, tmp_path):
    frame, identities = captured(found, tilted_body(tmp_path), tmp_path)
    plain = reduce(frame, identities)
    lit = reduce(frame, identities, values=LIT)
    row, column = pixel(0.0, 0.3)
    np.testing.assert_allclose(
        frame.buffers[BACK_NORMAL][row, column], TILTED, atol=1e-3
    )
    gain = facing(frame.buffers[BACK_NORMAL][row, column])
    assert 0.2 < gain < 0.9
    assert tuple(lit.pixels[row, column, :3]) == scaled(
        plain.pixels[row, column, :3], gain
    )
    covered = plain.pixels[..., 3] > 0
    assert covered.any() and (lit.pixels[..., 3] == plain.pixels[..., 3]).all()
    assert (lit.pixels[~covered] == 0).all()


def test_a_cutout_is_lit_where_it_is_kept_and_transparent_elsewhere(found, tmp_path):
    model = Model()
    texture = model.texture((8, 8), checker)
    mask = model.material(
        "mask", (1, 1, 1, 1), alpha_mode="MASK", cutoff=0.5, texture=texture
    )
    model.primitive(quad_xy(-1.0, 0.0, 1.0, 0.8, 0.0), mask, texcoords=QUAD_UV)
    frame, identities = captured(found, model.write(tmp_path, "cutout"), tmp_path)
    plain = reduce(frame, identities)
    lit = reduce(frame, identities, values=LIT)
    kept = plain.pixels[..., 3] > 0
    assert kept.any() and not kept.all()
    gain = facing(FRONT_ON)
    assert gain == pytest.approx(0.8)
    expected = np.array([scaled(c, gain) for c in plain.pixels[kept][:, :3]])
    np.testing.assert_array_equal(lit.pixels[kept][:, :3], expected)
    assert (lit.pixels[..., 3] == plain.pixels[..., 3]).all()
    assert (lit.pixels[~kept] == 0).all()


def test_a_translucent_veil_and_the_body_behind_it_each_use_their_own_normal(
    found, tmp_path
):
    frame, identities = captured(found, overlap(tmp_path), tmp_path)
    plain = reduce(frame, identities)
    lit = reduce(frame, identities, values=LIT)
    row, column = pixel(-0.8, 0.3)
    front_normal = frame.buffers[FRONT_NORMAL][row, column]
    back_normal = frame.buffers[BACK_NORMAL][row, column]
    np.testing.assert_allclose(front_normal, FRONT_ON, atol=1e-3)
    np.testing.assert_allclose(back_normal, TILTED, atol=1e-3)
    front_facing, back_facing = facing(front_normal), facing(back_normal)
    assert front_facing != pytest.approx(back_facing, abs=0.1)
    q = int(frame.buffers[FRONT_ALPHA][row, column])
    front = tuple(int(v) for v in frame.buffers[FRONT_COLOR][row, column, :3])
    back = tuple(int(v) for v in frame.pixels[row, column, :3])
    expected = over(
        scaled(front, front_facing), q, scaled(back, back_facing), 65535 - q
    )
    assert tuple(lit.pixels[row, column, :3]) == expected
    # The veil alone is lit by its normal, the body alone by its own.
    alone = frame.buffers[FRONT_COLOR][pixel(0.0, 0.3)][:3]
    assert colour_at(lit, 0.0, 0.3)[:3] == scaled(alone, front_facing)
    assert colour_at(lit, 0.8, 0.3)[:3] == scaled(
        colour_at(plain, 0.8, 0.3)[:3], facing(TILTED)
    )
    # Colour only: alpha and both reduced maps are the unshaded run's.
    assert (lit.pixels[..., 3] == plain.pixels[..., 3]).all()
    for name in (NORMAL_MAP, DEPTH_MAP):
        np.testing.assert_array_equal(lit.buffers[name], plain.buffers[name])


def test_a_translucent_model_with_ramps_snaps_to_the_whole_palette(found, tmp_path):
    frame, identities = captured(found, overlap(tmp_path), tmp_path)
    lib = materials.validate_library(
        {
            "schema": materials.SCHEMA_V4,
            "ramps": {"red": [1, 2, 3], "blue": [4, 5, 6]},
            "materials": {"veil": {"uses": "red"}, "body": {"uses": "blue"}},
        },
        PALETTE,
        source="test",
        shading=True,
    )
    values = {"shade.mode": "both", "shade.snap": "palette"}
    plain = reduce(frame, identities, library=lib, palette=PALETTE)
    snapped = reduce(frame, identities, values=values, library=lib, palette=PALETTE)
    under = colour_at(snapped, -0.8, 0.3)
    assert under[:3] in PALETTE and under[3] == 255
    assert colour_at(snapped, 0.8, 0.3)[:3] in PALETTE
    assert (snapped.pixels[..., 3] == plain.pixels[..., 3]).all()
    # The model's own shading, not the unshaded ramp pick, reached the pixel.
    assert (snapped.pixels != plain.pixels).any()
