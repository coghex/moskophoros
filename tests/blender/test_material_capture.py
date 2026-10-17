"""The material-ID and shade buffers on generated models, in real Blender
(design §Capture; material styling design §Spike record (D-10), D-25, D-26).

Positions are worked out from the fixtures' known geometry: in front view
(pitch 0, one direction, the ground point at the origin and on `GROUND_PX`),
a point (x, y) lands at pixel (gx + x·ppm, gy − y·ppm), times the supersample.
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from glb_writer import GlbWriter
from material_models import EDGES, appearance, edges, form, quad_xy, vertex_colours
from PIL import Image
from shading import DEFAULT_RANGE, DEFAULT_SHADE
from test_render import render

from moskophoros import gltf
from moskophoros.capture import backend, blender
from moskophoros.capture.backend import MaterialShade, Shade
from moskophoros.sampling import BACKGROUND

pytestmark = pytest.mark.blender

PPM = 40.0
CELL = (96, 128)
GROUND_PX = (48, 100)
# Texel centres of the `edges` MASK quad's checker (x −1–0, y 1.1–2.1): the
# texel (4, 4) is transparent, so cut out; (2, 4) is opaque, so kept.
CUT_TEXEL = (-0.4375, 1.5375)
KEPT_TEXEL = (-0.6875, 1.5375)


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
        KEPT_TEXEL: code["mask"],
        CUT_TEXEL: code["behind"],
        (0.55, 1.6): code["occluder"],
        (0.2, 1.2): code["occluded"],
        (-0.5, -0.5): code["glass"],
        (0.5, -0.5): backend.NO_MATERIAL_ID,
    }
    for point, value in expected.items():
        assert image[at(*point, supersample)] == value, point
    used = set(np.unique(image).tolist())
    # Every code is a table entry or background; the unused material never
    # shows, and the surface behind the MASK material shows through its holes.
    assert used <= set(result.materials) | {0}
    assert code["unused"] not in used and code["behind"] in used
    # Two materials meet along x = 0 with no pixel of anything else between.
    row = at(0.0, 0.5, supersample)[0]
    left, right = at(-0.45, 0.5, supersample)[1], at(0.45, 0.5, supersample)[1]
    assert set(image[row, left:right].tolist()) == {code["left"], code["right"]}
    # The strip is 0.4 px wide at supersample 1: no pixel centre falls on it,
    # so the ID misses it, as accepted; at 16 it is several pixels wide.
    strip = (image == code["strip"]).sum()
    assert strip == 0 if supersample == 1 else strip > 0


def test_a_mask_material_cuts_out_in_colour_id_and_shade(found, tmp_path):
    # Alpha design D-1, D-3: where the MASK texture is transparent, the colour,
    # ID and shade show the surface behind it; elsewhere the MASK material.
    path = edges(tmp_path)
    result, _ = front(found, path, tmp_path, 4)
    buffers = list(result.buffers.values())[0]
    color, shade = pixels(buffers["color"]), pixels(buffers["shade"])
    image = codes(result)
    top, left = at(-0.95, 2.05, 4)
    bottom, right = at(-0.05, 1.15, 4)
    region = (slice(top, bottom), slice(left, right))
    assert set(np.unique(image[region]).tolist()) == {
        EDGES["mask"] + 1,
        EDGES["behind"] + 1,
    }
    assert (color[region][..., 3] == 255).all()
    assert (shade[region][..., 3] == 255).all()
    # The cut texels show the blue surface behind, the kept ones the yellow.
    hole, kept = at(*CUT_TEXEL, 4), at(*KEPT_TEXEL, 4)
    assert image[hole] == EDGES["behind"] + 1 and image[kept] == EDGES["mask"] + 1
    assert color[hole][2] > 150 > color[hole][0]
    assert color[kept][0] > 150 > color[kept][2]


def test_an_importer_copy_of_a_material_keeps_its_glTF_material(found, tmp_path):
    # Blender copies material 0 (as moskophoros.material.0.data.001) for the
    # quad with vertex colours; both quads must still show material 0's code.
    result, _ = front(found, vertex_colours(tmp_path), tmp_path, 1)
    image = codes(result)
    assert image[at(-0.5, 0.5, 1)] == 1
    assert image[at(0.5, 0.5, 1)] == 1
    assert set(np.unique(image).tolist()) == {0, 1}


def test_an_importer_copy_takes_its_glTF_materials_own_values(found, tmp_path):
    """Settings design D-36: material 0's own occlusion weight reaches the
    importer's copy of it too, so both quads shade alike."""
    path = vertex_colours(tmp_path)
    own = Shade(0.3, 64, 0.25, 1.0, (MaterialShade(0, 0.3, 0.5, 1.0),))
    for shade, expected in ((DEFAULT_SHADE, 0.25), (own, 0.5)):
        result, _ = render(
            found,
            path,
            tmp_path,
            ppm=PPM,
            cell=CELL,
            ground_px=GROUND_PX,
            supersample=1,
            workspace=f"work-{expected}",
            shade=shade,
        )
        values = pixels(list(result.buffers.values())[0]["shade"])[..., 0]
        left, right = values[at(-0.5, 0.5, 1)], values[at(0.5, 0.5, 1)]
        assert left == right
        assert abs(int(left) - srgb_byte(expected)) <= 0.5, (expected, left)


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
        KEPT_TEXEL: 3,  # leaf (MASK)
        CUT_TEXEL: 4,  # bark, through the leaf's hole
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


def form_shades(found, path, tmp_path, supersample, shade=DEFAULT_SHADE, name="work"):
    """The mean shade byte of `form`'s crease, flat and convex regions."""
    result, _ = render(
        found,
        path,
        tmp_path,
        pitch=30.0,
        ppm=40.0,
        cell=(128, 112),
        ground_px=(64, 80),
        supersample=supersample,
        workspace=name,
        shade=shade,
    )
    return region_means(result, supersample)


def region_means(result, supersample):
    # The spike's recorded settings and regions (material styling design
    # §Spike record (D-10)): floor 1, wall 2 and sphere 3 are material codes.
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
    return {name: float(shade[mask].mean()) for name, mask in regions.items()}


@pytest.mark.parametrize("supersample", [1, 4])
def test_flat_crease_and_convex_take_different_bands(found, tmp_path, supersample):
    # At the defaults only (settings design D-12).
    means = form_shades(found, form(tmp_path), tmp_path, supersample)
    assert means["flat"] == 137.0
    assert means["crease"] < means["flat"] < means["convex"]
    lo, hi = DEFAULT_RANGE
    assert (lo, hi) == (84, 191)
    for n in (3, 4, 5):
        bands = [
            band(round(means[name]), lo, hi, n) for name in ("crease", "flat", "convex")
        ]
        assert bands[0] < bands[1] < bands[2], (n, means, bands)


# The capture values (settings design D-3, D-9, D-42): the shade is
# clamp(occlusion_weight · AO_out + convexity_weight · (1 − AO_in), 0, 1),
# written as the sRGB byte of that linear value.


def srgb_byte(linear):
    encoded = (
        12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    )
    return 255 * encoded


def test_the_weights_change_the_shade_as_the_formula_says(found, tmp_path):
    path = form(tmp_path)
    default = form_shades(found, path, tmp_path, 1, name="default")
    # The flat surface is open (AO_out 1) and not convex (AO_in 1): its shade
    # is the occlusion weight. Without the convexity term, the isolated
    # convex sphere is no brighter than the flat surface.
    weighted = form_shades(
        found, path, tmp_path, 1, Shade(0.3, 64, 0.5, 0.0), name="weighted"
    )
    assert default["flat"] == 137.0 == round(srgb_byte(0.25))
    assert abs(weighted["flat"] - srgb_byte(0.5)) <= 0.5
    assert default["convex"] > default["flat"] + 5
    assert abs(weighted["convex"] - weighted["flat"]) <= 0.5
    # Occlusion still darkens the crease.
    assert weighted["crease"] < weighted["flat"]


def test_a_longer_ao_distance_reaches_farther_geometry(found, tmp_path):
    # The "flat" region lies 0.3 m or more from the crease: open at the
    # default 0.3 m, occluded by the wall within 1.2 m.
    path = form(tmp_path)
    near = form_shades(found, path, tmp_path, 1, name="near")
    far = form_shades(found, path, tmp_path, 1, Shade(1.2, 64, 0.25, 1.0), name="far")
    assert near["flat"] == 137.0
    assert far["flat"] < near["flat"] - 2
    assert far["crease"] <= near["crease"]


PROBE = """
import importlib.util, json, sys
import bpy

path, shade, code = sys.argv[sys.argv.index("--") + 1 :]
spec = importlib.util.spec_from_file_location("probe_script", path)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)
material = bpy.data.materials.new("probe")
material.use_nodes = True
surfaces = script.Surfaces(bpy.context.scene, [], {}, json.loads(shade), {})
surfaces.make_switch()
surfaces._inject(material, int(code), None, None)
nodes = material.node_tree.nodes
labelled = {node.label: node for node in nodes if node.label.startswith("moskophoros.")}
distance = labelled["moskophoros.ao_distance_m"]
print("PROBE " + json.dumps({
    # Each AO node's samples, and the distance its gated input carries.
    "ao": sorted(
        (
            node.inside,
            node.samples,
            round(distance.inputs[1].default_value, 6)
            if node.inputs["Distance"].links[0].from_node == distance
            else None,
        )
        for node in nodes
        if node.bl_idname == "ShaderNodeAmbientOcclusion"
    ),
    # Each shade math node's constant input: the weight, or the 1 in 1 - AO_in.
    "math": sorted(
        (
            node.operation,
            round(node.inputs[0 if node.operation == "SUBTRACT" else 1].default_value, 6),
        )
        for label, node in labelled.items()
        if label != "moskophoros.ao_distance_m"
    ),
}))
"""


@pytest.mark.parametrize("samples", [1, 64, 128])
def test_the_job_s_samples_distance_and_weights_reach_both_ao_nodes(
    found, tmp_path, samples
):
    """Settings design D-42: up to 128 samples reach both AO nodes as given;
    Blender would silently clamp more, which the command refuses first."""
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE)
    shade = {
        "ao_distance_m": 0.75,
        "ao_samples": samples,
        "occlusion_weight": 0.4,
        "convexity_weight": 0.6,
        "materials": [],
    }
    completed = subprocess.run(
        [
            str(found.path),
            "-b",
            "--factory-startup",
            "-noaudio",
            "--python",
            str(probe),
            "--",
            str(Path(blender.__file__).with_name("blender_script.py")),
            json.dumps(shade),
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [
        line for line in completed.stdout.splitlines() if line.startswith("PROBE ")
    ]
    assert completed.returncode == 0 and lines, completed.stdout + completed.stderr
    probed = json.loads(lines[0].removeprefix("PROBE "))
    assert probed["ao"] == [[False, samples, 0.75], [True, samples, 0.75]]
    assert probed["math"] == [
        ["MULTIPLY", 0.4],
        ["MULTIPLY_ADD", 0.6],
        ["SUBTRACT", 1.0],
    ]


def probe(found, tmp_path, shade, code):
    path = tmp_path / f"probe-{code}.py"
    path.write_text(PROBE)
    completed = subprocess.run(
        [
            str(found.path),
            "-b",
            "--factory-startup",
            "-noaudio",
            "--python",
            str(path),
            "--",
            str(Path(blender.__file__).with_name("blender_script.py")),
            json.dumps(shade),
            str(code),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [
        line for line in completed.stdout.splitlines() if line.startswith("PROBE ")
    ]
    assert completed.returncode == 0 and lines, completed.stdout + completed.stderr
    return json.loads(lines[0].removeprefix("PROBE "))


def test_a_materials_own_values_reach_its_shader_and_only_its(found, tmp_path):
    """Settings design D-9 and D-36: glTF material 1 (code 2) overrides the
    distance and weights; samples stay global, and other materials and the
    no-material stand-in take the global values."""
    shade = {
        "ao_distance_m": 0.3,
        "ao_samples": 128,
        "occlusion_weight": 0.25,
        "convexity_weight": 1.0,
        "materials": [
            {
                "material": 1,
                "ao_distance_m": 1.25,
                "occlusion_weight": 0.5,
                "convexity_weight": 0.0,
            }
        ],
    }
    own = probe(found, tmp_path, shade, 2)
    assert own["ao"] == [[False, 128, 1.25], [True, 128, 1.25]]
    assert own["math"] == [["MULTIPLY", 0.5], ["MULTIPLY_ADD", 0.0], ["SUBTRACT", 1.0]]
    for code in (1, backend.NO_MATERIAL_ID):
        other = probe(found, tmp_path, shade, code)
        assert other["ao"] == [[False, 128, 0.3], [True, 128, 0.3]]
        assert other["math"] == [
            ["MULTIPLY", 0.25],
            ["MULTIPLY_ADD", 1.0],
            ["SUBTRACT", 1.0],
        ]


def test_two_materials_in_one_frame_each_take_their_own_values(found, tmp_path):
    """The floor (glTF material 0) overrides its occlusion weight; the wall
    keeps the global one. Both flat open surfaces have AO_out 1 and no
    convexity, so each shade is its own occlusion weight."""
    path = form(tmp_path)
    result, _ = render(
        found,
        path,
        tmp_path,
        pitch=30.0,
        ppm=40.0,
        cell=(128, 112),
        ground_px=(64, 80),
        supersample=1,
        shade=Shade(0.3, 64, 0.25, 1.0, (MaterialShade(0, 0.3, 0.5, 1.0),)),
    )
    image = codes(result)
    shade = pixels(list(result.buffers.values())[0]["shade"])[..., 0]
    floor, wall, ball = image == 1, image == 2, image == 3
    meeting = (floor & (_distance_to(wall, 2) <= 1)) | (
        wall & (_distance_to(floor, 2) <= 1)
    )
    to_crease = _distance_to(meeting, 40)
    clear = (_distance_to(ball, 40) >= 8) & (_distance_to(image == 0, 40) >= 3)
    open_floor = floor & (to_crease >= 12) & clear
    open_wall = wall & (to_crease >= 12) & clear
    assert open_floor.any() and open_wall.any()
    assert abs(float(shade[open_floor].mean()) - srgb_byte(0.5)) <= 0.5
    assert float(shade[open_wall].mean()) == 137.0


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
