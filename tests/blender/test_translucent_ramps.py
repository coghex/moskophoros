"""Translucent materials take ramps (alpha design ALPHA-5; D-12, D-14,
D-15): a `BLEND` material has an identity, its front layer is ramped by its
front-most material before compositing over the ramped body, a rear pane's
ramp is not applied, and a `BLEND` entry's own capture values reach its
shade. In real Blender, through the whole command."""

import math

import numpy as np
import pytest
import yaml
from material_models import Model, quad_xy
from PIL import Image

from moskophoros import cli, imageops
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

PALETTE = [(i * 30, 255 - i * 30, 40 + i * 20) for i in range(8)]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def linear(byte):
    c = byte / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb(value):
    s = 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055
    return math.floor(255 * s + 0.5)


def snapped(colour):
    pixel = np.array([[[*colour, 255]]], np.uint8)
    return tuple(int(v) for v in imageops.map_palette(pixel, PALETTE)[0, 0, :3])


def over(front, q, back):
    return tuple(
        srgb((q * linear(f) + (65535 - q) * linear(b)) / 65535)
        for f, b in zip(front, back, strict=True)
    )


def command(found, tmp_path, path, library, name, *options):
    out = tmp_path / name
    out.mkdir()
    (tmp_path / "p.hex").write_text(
        "".join(f"{r:02x}{g:02x}{b:02x}\n" for r, g, b in PALETTE)
    )
    library_path = tmp_path / f"{name}.yaml"
    library_path.write_text(yaml.safe_dump(library))
    status = cli.run(
        [
            "--no-user-config",
            "--blender",
            str(found.path),
            *["--pitch", "0", "--directions", "1", "--start-angle", "0"],
            *["--ppm", "10", "--cell", "24x20", "--ground-px", "12,18"],
            *["--supersample", "1", "--no-preview", "--depth"],
            *["--palette", str(tmp_path / "p.hex"), "--materials", str(library_path)],
            *options,
            str(path),
            str(out / "sheet.png"),
        ]
    )
    assert status == 0
    return out


def loaded(path):
    with Image.open(path) as image:
        return np.asarray(image).astype(np.int64)


def library(entries):
    return {
        "schema": "moskophoros.materials/3",
        "ramps": {"metal": [5], "clear": [2], "pink": [3], "amber": [4]},
        "materials": entries,
    }


def test_a_ramped_quad_over_a_ramped_body_composites_both_ramps_then_snaps(
    found, tmp_path
):
    model = Model()
    veil = model.material("veil", (0.1, 0.9, 0.2, 0.4), alpha_mode="BLEND")
    steel = model.material("steel", (0.5, 0.5, 0.5, 1))
    model.primitive(quad_xy(-0.6, 0.2, 0.6, 1.4, 0.5), veil)
    model.primitive(quad_xy(-1.0, 0.0, 1.0, 1.6, 0.0), steel)
    path = model.write(tmp_path, "ramped")
    entries = {"steel": {"uses": "metal"}, "veil": {"uses": "clear"}}
    out = command(found, tmp_path, path, library(entries), "both")
    sheet = loaded(out / "sheet.png")
    q = math.floor(65535 * float(np.float32(0.4)) + 0.5)
    under = snapped(over(PALETTE[2], q, PALETTE[5]))
    # Under the quad: the veil's ramp over the body's, composited, snapped.
    assert sheet[10, 12].tolist() == [*under, 255]
    assert under not in (PALETTE[2], PALETTE[5])
    # Beside it, the body's ramp alone.
    assert sheet[17, 2].tolist() == [*PALETTE[5], 255]
    # The maps show the quad, 0.5 m toward the viewer, over the body.
    depth = loaded(out / "sheet.depth.png")
    assert depth[10, 12] == 32768 + 16 * 5
    assert depth[17, 2] == 32768


def two_panes(directory):
    """A near pane over a rear pane, each 0.5, over a body."""
    model = Model()
    near = model.material("near", (0.9, 0.1, 0.1, 0.5), alpha_mode="BLEND")
    rear = model.material("rear", (0.1, 0.1, 0.9, 0.5), alpha_mode="BLEND")
    steel = model.material("steel", (0.5, 0.5, 0.5, 1))
    model.primitive(quad_xy(-0.6, 0.2, 0.6, 1.4, 0.6), near)
    model.primitive(quad_xy(-0.6, 0.2, 0.6, 1.4, 0.5), rear)
    model.primitive(quad_xy(-1.0, 0.0, 1.0, 1.6, 0.0), steel)
    return model.write(directory, "panes")


@pytest.mark.parametrize(
    "near", ["ordinary", {"uses": "clear"}], ids=["ordinary", "ramped"]
)
def test_a_rear_pane_s_ramp_never_recolours_the_combined_front(found, tmp_path, near):
    path = two_panes(tmp_path)
    sheets = []
    for rear in ("pink", "amber"):
        entries = {"steel": {"uses": "metal"}, "near": near, "rear": {"uses": rear}}
        out = command(found, tmp_path, path, library(entries), f"rear-{rear}")
        sheets.append((out / "sheet.png").read_bytes())
    assert sheets[0] == sheets[1]
    if near != "ordinary":
        # The combined front, alpha 0.75, is the near pane's ramp colour.
        sheet = loaded(tmp_path / "rear-pink" / "sheet.png")
        expected = snapped(over(PALETTE[2], 49151, PALETTE[5]))
        assert sheet[10, 12].tolist() == [*expected, 255]


def test_a_blend_entry_s_own_capture_values_reach_its_front_shade(found, tmp_path):
    # Two translucent quads over nothing, beyond each other's occlusion: one
    # whose entry sets both weights to 0, so its shade is 0, and one taking
    # the global values, so its open flat face is 0.25, encoded 137.
    model = Model()
    dark = model.material("dark", (0.2, 0.8, 0.2, 0.5), alpha_mode="BLEND")
    plain = model.material("plain", (0.2, 0.8, 0.2, 0.5), alpha_mode="BLEND")
    model.primitive(quad_xy(-1.1, 0.2, -0.3, 1.4, 0.0), dark)
    model.primitive(quad_xy(0.3, 0.2, 1.1, 1.4, 0.0), plain)
    path = model.write(tmp_path, "shades")
    entries = {
        "dark": {
            "uses": "clear",
            "shade": {"occlusion_weight": 0.0, "convexity_weight": 0.0},
        },
        "plain": {"uses": "clear"},
    }
    out = command(
        found,
        tmp_path,
        path,
        library(entries),
        "shades",
        "--work-dir",
        str(tmp_path / "work"),
    )
    shade = loaded(tmp_path / "work" / "render" / "front_shade" / "000000.png")
    assert shade[10, 4].tolist() == [0, 0, 0, 255]
    assert shade[10, 19].tolist() == [137, 137, 137, 255]
    assert (out / "sheet.png").exists()
