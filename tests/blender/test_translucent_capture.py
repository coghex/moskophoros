"""`BLEND` materials are seen through (alpha design ALPHA-4; D-1, D-3, D-6,
D-11, D-12; design §Capture): each supersample has a back layer, the first
opaque surface, and a front layer, every translucent surface in front of it
combined, carried by the front buffers; the normal and depth describe the
front-most surface; a stack too deep to render behind a visible front fails
loudly; and the command composites the front over the back."""

import json
import math
import struct

import numpy as np
import pytest
from material_models import QUAD_UV, Model, quad_xy
from PIL import Image
from test_render import render

from moskophoros import cli, imageops
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

# A row of 0.4 m quads in front view, one column per stack, 0.5 m apart, at
# 20 pixels per meter; layers from 0.5 m, 0.01 m apart, over a body at 0.
PPM = 20.0
CELL = (170, 20)
GROUND_PX = (85, 15)


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def f32(value):
    return float(np.float32(value))


def linear(byte):
    c = byte / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb(value):
    value = min(max(value, 0.0), 1.0)
    s = 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055
    return math.floor(255 * s + 0.5)


class Stacks:
    """A model of columns, each a stack of quads, front to back, over a body
    or nothing; it records each translucent layer's alpha and linear colour
    as Cycles receives them."""

    def __init__(self):
        self.model = Model()
        self.hole = self.model.material("hole", (1, 1, 1, 0), alpha_mode="MASK")
        self.columns = []
        self.layers = {}

    def blend(self, name, rgb, alpha, received=None, **options):
        material = self.model.material(
            name, (*rgb, alpha), alpha_mode="BLEND", **options
        )
        self.layers[material] = received or (f32(alpha), [f32(v) for v in rgb])
        return material

    def opaque(self, name, rgb):
        material = self.model.material(name, (*rgb, 1.0))
        self.layers[material] = (1.0, [f32(v) for v in rgb])
        return material

    def column(self, name, layers, back=None, **primitive):
        x0 = -4.0 + 0.5 * len(self.columns) + 0.05
        depths = []
        for k, material in enumerate(layers):
            z = 0.5 + 0.01 * (len(layers) - 1 - k)
            self.model.primitive(
                quad_xy(x0, 0.0, x0 + 0.4, 0.4, z), material, **primitive
            )
            depths.append(z)
        if back is not None:
            self.model.primitive(quad_xy(x0, 0.0, x0 + 0.4, 0.4, 0.0), back)
        self.columns.append((name, x0, layers, depths, back))

    def expected(self, layers, depths, back):
        """The analytic front layer (alpha, straight colour, front-most
        code and depth), front over back."""
        through, premultiplied, code, depth = 1.0, np.zeros(3), 0, None
        for material, z in zip(layers, depths, strict=True):
            if material == self.hole:
                continue
            alpha, colour = self.layers[material]
            if alpha <= 2**-25:
                continue
            if code == 0:
                code, depth = material + 1, z
            premultiplied += through * alpha * np.array(colour)
            through *= 1 - alpha
        front = 1 - through
        return front, premultiplied, code, depth, through


def stacks(directory):
    s = Stacks()
    blue = s.opaque("blue", (0.1, 0.2, 0.9))
    hole = s.hole
    a = s.blend("a veil", (1, 0, 0), 0.4)
    s.column("(a)", [a] + [hole] * 10, blue)
    b_red, b_green = (
        s.blend("b red", (1, 0, 0), 0.5),
        s.blend("b green", (0, 1, 0), 0.25),
    )
    s.column("(b)", [hole, b_red, hole, hole, hole, b_green] + [hole] * 5, blue)
    c_red, c_green = (
        s.blend("c red", (1, 0, 0), 0.5),
        s.blend("c green", (0, 1, 0), 0.5),
    )
    s.column("(c) two panes of 0.5", [c_red, c_green])
    alternating = []
    for k in range(15):
        rgb = ((k * 0.37) % 1.0, (k * 0.61 + 0.2) % 1.0, (k * 0.13 + 0.5) % 1.0)
        alternating += [s.blend(f"d{k}", rgb, 0.3), hole]
    s.column("(d) 30 layers", alternating, blue)
    s.column("0.4 over the body", [s.blend("veil", (1, 0.5, 0), 0.4)], blue)
    s.column("0.4 over nothing", [s.blend("veil alone", (1, 0.5, 0), 0.4)])
    s.column("tiny alpha", [s.blend("tiny", (0.2, 0.6, 1.0), 5e-7)])
    s.column("the hole floor", [s.blend("floor", (0.2, 0.6, 1.0), 1e-9)])
    # The importer stores COLOR_0 as 8-bit: 0.5 arrives as 128/255.
    vertex = s.blend(
        "vertex", (1, 1, 1), 1.0, received=(128 / 255, [51 / 255, 204 / 255, 102 / 255])
    )
    s.column("vertex alpha", [vertex], blue, colors=[(0.2, 0.8, 0.4, 0.5)] * 6)
    texture = s.model.texture((2, 2), lambda x, y: (255, 128, 0, 200))
    textured = s.blend(
        "texture x factor",
        (1, 1, 1),
        0.5,
        received=(0.5 * 200 / 255, [1.0, linear(128), 0.0]),
        texture=texture,
    )
    s.column("texture x factor", [textured], blue, texcoords=QUAD_UV)
    s.column("unlit", [s.blend("unlit", (0, 1, 0), 0.4, unlit=True)], blue)
    return s, s.model.write(directory, "stacks")


def centre(x0):
    return int(GROUND_PX[1] - 0.2 * PPM), int(round(GROUND_PX[0] + (x0 + 0.2) * PPM))


def buffers(result):
    paths = list(result.buffers.values())[0]
    loaded = {}
    for name, path in paths.items():
        if name in ("normal", "depth", "front_alpha"):
            loaded[name] = backend.read_wide_png(path).astype(np.int64)
        else:
            with Image.open(path) as image:
                loaded[name] = np.asarray(image).astype(np.int64)
    return loaded


def test_stacks_match_front_over_back(found, tmp_path):
    s, path = stacks(tmp_path)
    result, _ = render(
        found, path, tmp_path, ppm=PPM, cell=CELL, ground_px=GROUND_PX, supersample=1
    )
    image = buffers(result)
    for name, x0, layers, depths, back in s.columns:
        y, x = centre(x0)
        front, premultiplied, code, depth, through = s.expected(layers, depths, back)
        at = {
            buffer: tuple(int(v) for v in pixels[y, x])
            for buffer, pixels in image.items()
        }
        if code:
            q = math.floor(65535 * front + 0.5)
            assert at["front_alpha"] == (q, 0, 0, 65535), name
            assert at["front_matid"] == (code >> 8, code & 255, 0, 255), name
            if q > 0:
                colour = tuple(srgb(v / front) for v in premultiplied)
                assert at["front_color"] == (*colour, 255), name
            else:
                # A surface of alpha 0: present, but of no weight.
                assert at["front_color"][3] == 255, name
        else:
            for buffer in backend.FRONT_BUFFERS:
                assert not any(at[buffer]), (name, buffer)
        if back is not None:
            _, colour = s.layers[back]
            assert at["color"] == (*(srgb(v) for v in colour), 255), name
            assert at["matid"] == ((back + 1) >> 8, (back + 1) & 255, 0, 255), name
        else:
            assert at["color"] == (0, 0, 0, 0), name
        # The maps describe the front-most surface that is not a hole.
        surface = depth if code else (0.0 if back is not None else None)
        if surface is None:
            assert at["depth"] == (0, 0, 0, 0), name
        else:
            bits = struct.pack(">HH", at["depth"][0], at["depth"][1])
            assert abs(struct.unpack(">f", bits)[0] - surface) < 1e-6, name
        # The front over the back, from the 8-bit buffers, is the analytic
        # composite to within one 8-bit level.
        if code and back is not None:
            q = at["front_alpha"][0]
            mine = [
                (q * linear(f) + (65535 - q) * linear(b)) / 65535
                for f, b in zip(at["front_color"][:3], at["color"][:3], strict=True)
            ]
            exact = premultiplied + through * np.array(s.layers[back][1])
            assert (
                max(abs(srgb(m) - srgb(e)) for m, e in zip(mine, exact, strict=True))
                <= 1
            ), name
    assert image["front_alpha"][centre(s.columns[2][1])][0] == 49151  # 0.75


# The limit behind a visible translucent front (alpha design spike 3).


def deep(directory, holes, over_body):
    model = Model()
    front = model.material("front", (1, 0, 0, 0.4), alpha_mode="BLEND")
    hole = model.material("hole", (1, 1, 1, 0), alpha_mode="MASK")
    body = model.material("body", (0.1, 0.2, 0.9, 1))
    # The stack lies beyond the occlusion distance from the body.
    model.primitive(quad_xy(-0.5, -0.5, 0.5, 0.5, 1.2), front)
    for layer in range(holes):
        model.primitive(quad_xy(-0.5, -0.5, 0.5, 0.5, 0.5 + 0.01 * layer), hole)
    if over_body:
        model.primitive(quad_xy(-0.5, -0.5, 0.5, 0.5, 0.0), body)
    return model.write(directory, f"deep-{holes}")


SMALL = dict(ppm=10.0, cell=(16, 16), ground_px=(8, 8), supersample=1)


@pytest.mark.parametrize(
    "over_body", [True, False], ids=["over a body", "over nothing"]
)
def test_a_front_and_63_holes_render(found, tmp_path, over_body):
    result, _ = render(found, deep(tmp_path, 63, over_body), tmp_path, **SMALL)
    image = buffers(result)
    assert image["front_alpha"][8, 8].tolist() == [26214, 0, 0, 65535]
    assert (image["color"][8, 8, 3] == 255) == over_body


@pytest.mark.parametrize(
    ("holes", "over_body"),
    [(64, True), (64, False), (65, True)],
    ids=["64 over a body", "64 over nothing", "65 over a body"],
)
def test_a_front_and_64_or_more_holes_fail_and_publish_nothing(
    found, tmp_path, capsys, holes, over_body
):
    path = deep(tmp_path, holes, over_body)
    out = tmp_path / "out"
    out.mkdir()
    earlier = {"deep.png": b"earlier sheet", "deep.json": b"earlier json"}
    for name, data in earlier.items():
        (out / name).write_bytes(data)
    status = cli.run(
        [
            "--no-user-config",
            "--blender",
            str(found.path),
            *["--cell", "16x16", "--supersample", "1", "--directions", "1"],
            "--no-preview",
            str(path),
            str(out / "deep.png"),
        ]
    )
    err = capsys.readouterr().err
    assert status == 5, err
    assert f"{path.resolve()}: clip 'static', direction 0, frame 0 (t = 0.0 s)" in err
    assert "crossed more than 64 surfaces that still let light through" in err
    assert "(the limit is 64)" in err
    assert {p.name: p.read_bytes() for p in out.iterdir()} == earlier


# The whole command


def command(found, path, out, *options):
    out.mkdir(exist_ok=True)
    status = cli.run(
        [
            "--no-user-config",
            "--blender",
            str(found.path),
            *["--pitch", "0", "--directions", "1", "--start-angle", "0"],
            *options,
            "--no-preview",
            str(path),
            str(out / "sheet.png"),
        ]
    )
    return status


def test_presence_survives_transport(found, tmp_path, capsys):
    # Sheet pixel 1 of a 4×4 cell at supersample 2: its left samples see a
    # front of alpha 0.001 over nothing, its right ones the body. Four
    # surfaces, alpha 0.5005: 128, not 255, and not the body's alone.
    model = Model()
    faint = model.material("faint", (1, 0, 0, 0.001), alpha_mode="BLEND")
    body = model.material("body", (0.1, 0.2, 0.9, 1))
    model.primitive(quad_xy(-0.1, -0.15, -0.05, 0.15, 0.2), faint)
    model.primitive(quad_xy(-0.05, -0.15, 0.0, 0.15, 0.0), body)
    path = model.write(tmp_path, "faint")
    options = [
        "--ppm",
        "10",
        "--cell",
        "4x4",
        "--ground-px",
        "2,2",
        "--supersample",
        "2",
    ]
    assert command(found, path, tmp_path / "out", *options) == 0, (
        capsys.readouterr().err
    )
    with Image.open(tmp_path / "out" / "sheet.png") as image:
        sheet = np.asarray(image)
    assert sheet[1:3, 1, 3].tolist() == [128, 128]


def test_a_ramped_body_keeps_its_ramp_under_a_quad_and_the_maps_show_the_quad(
    found, tmp_path, capsys
):
    model = Model()
    veil = model.material("veil", (0.1, 0.9, 0.2, 0.4), alpha_mode="BLEND")
    steel = model.material("steel", (0.5, 0.5, 0.5, 1))
    model.primitive(quad_xy(-0.6, 0.2, 0.6, 1.4, 0.5), veil)
    model.primitive(quad_xy(-1.0, 0.0, 1.0, 1.6, 0.0), steel)
    path = model.write(tmp_path, "ramped")
    colours = [(i * 30, 255 - i * 30, 40) for i in range(8)]
    (tmp_path / "p.hex").write_text(
        "".join(f"{r:02x}{g:02x}{b:02x}\n" for r, g, b in colours)
    )
    (tmp_path / "lib.yaml").write_text(
        "schema: moskophoros.materials/3\nramps:\n  metal: [5]\n"
        "materials:\n  steel: {uses: metal}\n"
    )
    out = tmp_path / "out"
    options = [
        *["--ppm", "10", "--cell", "24x20", "--ground-px", "12,18"],
        *["--supersample", "1", "--depth"],
        *["--palette", str(tmp_path / "p.hex")],
        *["--materials", str(tmp_path / "lib.yaml")],
    ]
    assert command(found, path, out, *options) == 0, capsys.readouterr().err
    with Image.open(out / "sheet.png") as image:
        sheet = np.asarray(image)
    q = math.floor(65535 * f32(0.4) + 0.5)
    front = imageops.map_palette(
        np.array([[[srgb(f32(0.1)), srgb(f32(0.9)), srgb(f32(0.2)), 255]]], np.uint8),
        colours,
    )[0, 0, :3]
    ramp = colours[5]
    mixed = [
        srgb((q * linear(int(f)) + (65535 - q) * linear(b)) / 65535)
        for f, b in zip(front, ramp, strict=True)
    ]
    snapped = imageops.map_palette(np.array([[[*mixed, 255]]], np.uint8), colours)
    # Under the quad: the body's ramp colour, the quad over it, snapped.
    assert sheet[10, 12].tolist() == [*snapped[0, 0, :3].tolist(), 255]
    # Beside it: the body's ramp colour alone.
    assert sheet[17, 2].tolist() == [*ramp, 255]
    # The depth map shows the quad, 0.5 m toward the viewer, over the body.
    with Image.open(out / "sheet.depth.png") as image:
        depth = np.asarray(image).astype(np.int64)
    assert depth[10, 12] == 32768 + 16 * 5
    assert depth[17, 2] == 32768


# A broken front buffer (design §Capture job and result contract)

WRAPPER = """\
import runpy, sys
scope = runpy.run_path({script!r})["main"].__globals__
original = scope["render_frames"]


def render_frames(job, document, statics):
    found = original(job, document, statics)
    import os
    path = os.path.join(job["output_dir"], "front_alpha", "000000.png")
    if {fault!r} == "missing":
        os.remove(path)
    else:
        with open(path, "r+b") as handle:
            handle.truncate(40)
    return found


scope["render_frames"] = render_frames
scope["main"](sys.argv)
"""


@pytest.mark.parametrize(
    ("fault", "message"),
    [("missing", "does not exist"), ("corrupt", "front_alpha buffer")],
)
def test_a_missing_or_corrupt_front_buffer_fails_and_publishes_nothing(
    found, tmp_path, monkeypatch, capsys, fault, message
):
    wrapper = tmp_path / "broken.py"
    wrapper.write_text(WRAPPER.format(script=str(blender.SCRIPT), fault=fault))
    monkeypatch.setattr(blender, "SCRIPT", wrapper)
    model = Model()
    model.primitive(
        quad_xy(-0.4, 0.0, 0.4, 0.8, 0.0),
        model.material("v", (1, 0, 0, 0.4), alpha_mode="BLEND"),
    )
    path = model.write(tmp_path, "veil")
    out = tmp_path / "out"
    out.mkdir()
    earlier = {"sheet.png": b"earlier sheet", "sheet.json": b"earlier json"}
    for name, data in earlier.items():
        (out / name).write_bytes(data)
    status = command(found, path, out, "--cell", "8x8", "--supersample", "1")
    err = capsys.readouterr().err
    assert status == 5, err
    assert message in err
    assert {p.name: p.read_bytes() for p in out.iterdir()} == earlier


def test_repeat_renders_are_byte_identical_in_every_buffer(found, tmp_path):
    s, path = stacks(tmp_path)
    options = dict(ppm=PPM, cell=CELL, ground_px=GROUND_PX, supersample=2)
    first, _ = render(found, path, tmp_path, workspace="one", **options)
    second, _ = render(found, path, tmp_path, workspace="two", **options)
    (a,) = first.buffers.values()
    (b,) = second.buffers.values()
    assert set(a) >= set(backend.FRONT_BUFFERS)
    for name in a:
        assert a[name].read_bytes() == b[name].read_bytes(), name
    assert (
        json.loads((tmp_path / "one" / "render" / "result.json").read_text())["schema"]
        == "moskophoros.capture-result/4"
    )
