"""One flat, unlit Cycles render gives every buffer (alpha design ALPHA-1,
D-5, D-8; design §Capture): each surface's flat material colour, through
the importer's colour chain, with the material ID, shade, normal and depth
on exactly the same pixels; material codes round trip; an opaque material
covers its whole face, a `MASK` material cuts out and a `BLEND` material is
the front layer (alpha design D-1, D-6, D-12); and a material graph the
capture cannot read fails the command, naming the material."""

import math

import numpy as np
import pytest
from material_models import (
    Model,
    appearance,
    checker,
    edges,
    form,
    quad_xy,
    vertex_colours,
)
from PIL import Image
from test_render import render

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

# A row of 0.4 m quads, one per slot, 0.5 m apart, in a front view of
# 4 m × 1 m at 20 pixels per meter.
PPM = 20.0
CELL = (80, 20)
GROUND_PX = (40, 10)
QUAD_UV = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0), (1.0, 0.0), (0.0, 0.0)]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def srgb_byte(linear):
    """The `Standard` transform's 8-bit sRGB encoding of a linear value."""
    value = (
        12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    )
    return math.floor(255 * value + 0.5)


def linear(byte):
    value = byte / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def slot(index):
    """Quad `index` of the row."""
    x0 = -2.0 + 0.5 * index + 0.05
    return quad_xy(x0, -0.2, x0 + 0.4, 0.2, 0.0)


def slot_pixels(image, index, supersample=1):
    """The pixels well inside quad `index`."""
    x0 = (GROUND_PX[0] + (-2.0 + 0.5 * index + 0.1) * PPM) * supersample
    x1 = (GROUND_PX[0] + (-2.0 + 0.5 * index + 0.4) * PPM) * supersample
    y0 = (GROUND_PX[1] - 0.15 * PPM) * supersample
    y1 = (GROUND_PX[1] + 0.15 * PPM) * supersample
    return image[int(y0) : int(y1), int(x0) : int(x1)].reshape(-1, image.shape[-1])


def row(found, path, tmp_path, workspace="work"):
    return render(
        found,
        path,
        tmp_path,
        ppm=PPM,
        cell=CELL,
        ground_px=GROUND_PX,
        supersample=1,
        workspace=workspace,
    )


def loaded(result, name, ordinal=0):
    path = list(result.buffers.values())[ordinal][name]
    if name in ("normal", "depth", "front_alpha"):
        return backend.read_wide_png(path).astype(np.int64)
    with Image.open(path) as image:
        return np.asarray(image).astype(np.int64)


TEXEL = (200, 100, 50, 255)
FACTOR = (0.5, 1.0, 0.25, 1.0)
RED = (0.8, 0.1, 0.1, 1.0)
TEAL = (0.05, 0.6, 0.45, 1.0)


def looks(directory):
    """The row: a Principled constant colour, a Principled texture times a
    non-white factor, the same two unlit, an unlit `BLEND` material of alpha
    0.5 and an unlit `MASK` checker (both wrapped in an alpha chain by the
    importer), a Principled `BLEND` material of alpha 0.5, and a primitive
    without a material."""
    model = Model()
    texture = model.texture((4, 4), lambda x, y: TEXEL)
    materials = [
        model.material("constant", RED),
        model.material("textured", FACTOR, texture=texture),
        model.material("unlit", TEAL, unlit=True),
        model.material("unlit textured", FACTOR, texture=texture, unlit=True),
        model.material(
            "unlit veil", (0.3, 0.2, 0.9, 0.5), alpha_mode="BLEND", unlit=True
        ),
        model.material(
            "unlit leaf",
            (1.0, 1.0, 1.0, 1.0),
            alpha_mode="MASK",
            cutoff=0.5,
            texture=model.texture((8, 8), checker),
            unlit=True,
        ),
        model.material("glass", (0.9, 0.9, 0.2, 0.5), alpha_mode="BLEND"),
    ]
    for index, material in enumerate(materials):
        model.primitive(slot(index), material, texcoords=QUAD_UV)
    model.primitive(slot(len(materials)))
    return model.write(directory, "looks")


def expected(factor, texel=(255, 255, 255, 255)):
    return tuple(
        srgb_byte(linear(byte) * value)
        for byte, value in zip(texel[:3], factor[:3], strict=True)
    ) + (255,)


def test_each_material_renders_its_flat_colour(found, tmp_path):
    result, _ = row(found, looks(tmp_path), tmp_path)
    # The BLEND materials, 4 and 6, are the front layer: their flat colour
    # is the front colour, with nothing behind them.
    colour = np.where(
        loaded(result, "front_color")[..., 3:] == 255,
        loaded(result, "front_color"),
        loaded(result, "color"),
    )
    ids = loaded(result, "matid")
    wanted = {
        0: expected(RED),
        1: expected(FACTOR, TEXEL),
        2: expected(TEAL),
        3: expected(FACTOR, TEXEL),
        4: expected((0.3, 0.2, 0.9)),
        6: expected((0.9, 0.9, 0.2)),
        7: (255, 255, 255, 255),
    }
    for index, value in wanted.items():
        found_colours = {tuple(p) for p in slot_pixels(colour, index)}
        # One flat colour over the whole face: no light, no shading.
        assert len(found_colours) == 1, (index, found_colours)
        (only,) = found_colours
        assert all(abs(a - b) <= 1 for a, b in zip(only, value, strict=True)), (
            index,
            only,
            value,
        )
    # Constant colours, through nothing but the `Standard` transform, are
    # exactly the encoded factor; the material-less part is glTF's white.
    for index in (0, 2, 7):
        assert tuple(slot_pixels(colour, index)[0]) == wanted[index]
    # The unlit MASK checker cuts out (alpha design D-1): its kept texels are
    # its flat yellow, its cut ones nothing, in the colour and the ID alike.
    leaf = slot_pixels(colour, 5)
    assert {tuple(p) for p in leaf} == {
        expected((1, 1, 1), (255, 220, 0, 255)),
        (0, 0, 0, 0),
    }
    leaf_ids = slot_pixels(ids, 5)
    assert ((leaf_ids[:, 3] == 255) == (leaf[:, 3] == 255)).all()
    assert {(int(r) << 8 | int(g)) for r, g, b, a in leaf_ids if a} == {6}
    # Each BLEND material shows only in the front layer, at alpha 0.5.
    back, alpha = loaded(result, "color"), loaded(result, "front_alpha")
    for index in (4, 6):
        assert (slot_pixels(back, index) == 0).all(), index
        assert {tuple(p) for p in slot_pixels(alpha, index)} == {
            (32768, 0, 0, 65535)
        }, index


def test_every_opaque_material_covers_its_face_and_every_buffer_covers_it(
    found, tmp_path
):
    result, _ = row(found, looks(tmp_path), tmp_path)
    colour = loaded(result, "color")
    for index in (0, 1, 2, 3, 7):
        assert (slot_pixels(colour, index)[:, 3] == 255).all(), index
    aligned(result)


def aligned(result):
    """Every frame's layers aligned: each layer's colour, material ID and
    shade (and the front's alpha) present on exactly its colour's pixels,
    each colour wholly present or wholly empty, and the normal and depth
    present exactly where either layer is."""
    for ordinal in range(len(result.buffers)):
        either = None
        for prefix in ("", "front_"):
            colour = loaded(result, f"{prefix}color", ordinal)
            present = colour[..., 3] == 255
            assert ((colour[..., 3] == 0) | present).all(), prefix
            assert (colour[~present] == 0).all(), prefix
            names = ["matid", "shade"] + (["alpha"] if prefix else [])
            for name in names:
                other = loaded(result, prefix + name, ordinal)
                full = 65535 if name == "alpha" else 255
                assert ((other[..., 3] == full) == present).all(), prefix + name
                assert (other[~present] == 0).all(), prefix + name
            either = present if either is None else either | present
        for name in ("normal", "depth"):
            other = loaded(result, name, ordinal)
            assert ((other[..., 3] == 65535) == either).all(), name
            assert (other[~either] == 0).all(), name


@pytest.mark.parametrize("fixture", [edges, form, appearance, vertex_colours])
def test_every_buffer_is_aligned_with_the_colour(found, tmp_path, fixture):
    path = fixture(tmp_path)
    result, _ = render(
        found,
        path,
        tmp_path,
        pitch=30.0,
        directions=4,
        ppm=40.0,
        cell=(96, 96),
        ground_px=(48, 72),
        supersample=2,
    )
    aligned(result)
    assert loaded(result, "color")[..., 3].any()


def test_material_codes_255_256_and_65535_round_trip(found, tmp_path):
    model = Model()
    materials = [
        model.material(f"m{index}", (index / 255, 0.5, 0.5, 1.0))
        for index in range(256)
    ]
    model.primitive(slot(0), materials[254])
    model.primitive(slot(1), materials[255])
    model.primitive(slot(2))
    model.primitive(slot(3), materials[0])
    result, _ = row(found, model.write(tmp_path, "codes"), tmp_path)
    ids = loaded(result, "matid")
    for index, code in ((0, 255), (1, 256), (2, 65535), (3, 1)):
        pixels = slot_pixels(ids, index)
        assert {(int(r), int(g), int(b), int(a)) for r, g, b, a in pixels} == {
            (code >> 8, code & 0xFF, 0, 255)
        }, index
    assert result.materials[255] == 254
    assert result.materials[256] == 255
    assert result.materials[65535] is None
    aligned(result)


# A material graph the capture cannot read (alpha design spike 3, A-8).

WRAPPER = """\
import runpy, sys
scope = runpy.run_path({script!r})["main"].__globals__
original = scope["import_glb"]


def import_glb(data, directory):
    original(data, directory)
    import bpy
    material = bpy.data.materials["moskophoros.material.0.data"]
    tree = material.node_tree
    output = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    diffuse = tree.nodes.new("ShaderNodeBsdfDiffuse")
    tree.links.new(diffuse.outputs[0], output.inputs["Surface"])


scope["import_glb"] = import_glb
scope["main"](sys.argv)
"""


def test_an_unsupported_material_graph_fails_naming_the_material(
    found, tmp_path, monkeypatch, capsys
):
    wrapper = tmp_path / "unsupported.py"
    wrapper.write_text(WRAPPER.format(script=str(blender.SCRIPT)))
    monkeypatch.setattr(blender, "SCRIPT", wrapper)
    model = Model()
    model.primitive(slot(0), model.material("odd", RED))
    path = model.write(tmp_path, "odd")
    out = tmp_path / "out"
    out.mkdir()
    earlier = {"odd.png": b"earlier sheet", "odd.json": b"earlier json"}
    for name, data in earlier.items():
        (out / name).write_bytes(data)
    status = cli.run(
        [
            "--no-user-config",
            "--blender",
            str(found.path),
            "--cell",
            "8x8",
            "--supersample",
            "1",
            "--directions",
            "1",
            "--no-preview",
            str(path),
            str(out / "odd.png"),
        ]
    )
    err = capsys.readouterr().err
    assert status == 5, err
    assert "glTF material 0 ('odd')'s surface is ShaderNodeBsdfDiffuse" in err
    assert {p.name: p.read_bytes() for p in out.iterdir()} == earlier
