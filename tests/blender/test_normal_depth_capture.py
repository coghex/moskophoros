"""The normal and depth buffers on generated models, in real Blender (design
§Capture; lighting sheet design D-2, D-10, D-11, D-12, D-16 and D-21).

Expected values are worked out here from the fixtures' known geometry and
the camera of design §Camera and directions, independently of the script:
for direction angle a and pitch p, the camera's right, up and toward-viewer
axes are (1, 0, 0), (0, cos p, −sin p) and (0, sin p, cos p) turned by −a
about +Y. A camera-space normal is the world normal's components along them,
and a depth is a point's distance toward the viewer from the ground point,
(P − G) · toward.
"""

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pytest
from glb_writer import GlbWriter
from material_models import Model, edges, form, sphere
from PIL import Image
from test_render import cube, marker_model, render

from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

# The largest angle between a flat plane's captured normal and its exact
# normal, and the largest error of a plane's captured depth.
PLANE_TOLERANCE_DEG = 0.01
DEPTH_TOLERANCE_M = 5e-5
TRANSLATED_TOLERANCE_M = 2e-6
# A smooth sphere's interpolated normals against the exact sphere's, over the
# pixels facing the viewer by 0.3 or more: their mean and largest error. A
# flat face normal of this tessellation is about 1.3° off on average.
SPHERE_MEAN_DEG = 0.1
SPHERE_MAX_DEG = 0.3
GREY = (0.6, 0.6, 0.6, 1.0)


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def axes(pitch, angle):
    """The camera's right, up and toward-viewer axes in glTF coordinates."""
    p, a = math.radians(pitch), math.radians(-angle)
    sin_a, cos_a = math.sin(a), math.cos(a)

    def turn(v):
        return np.array(
            (v[0] * cos_a + v[2] * sin_a, v[1], -v[0] * sin_a + v[2] * cos_a)
        )

    return (
        turn((1.0, 0.0, 0.0)),
        turn((0.0, math.cos(p), -math.sin(p))),
        turn((0.0, math.sin(p), math.cos(p))),
    )


def frame(result, ordinal=0):
    """Frame `ordinal`'s material-ID codes (0 off a surface), normal and
    depth, as the command decodes them."""
    paths = list(result.buffers.values())[ordinal]
    with Image.open(paths["matid"]) as image:
        ids = np.asarray(image).astype(np.int64)
    codes = np.where(ids[..., 3] == 255, ids[..., 0] << 8 | ids[..., 1], 0)
    normal, depth = backend.decode_normal_depth(paths)
    return codes, normal.astype(np.float64), depth.astype(np.float64)


def angle_deg(a, b):
    """The angles between the vectors of `a` and `b`, in degrees."""
    cross = np.linalg.norm(np.cross(a, b), axis=-1)
    dot = np.sum(a * b, axis=-1)
    return np.degrees(np.arctan2(cross, dot))


def plane(center, normal, half):
    """Two triangles of a square plane through `center`, facing `normal`."""
    n = np.asarray(normal, dtype=np.float64)
    n /= np.linalg.norm(n)
    helper = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = np.cross(helper, n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    c = np.asarray(center, dtype=np.float64)
    corners = [
        tuple(c + half * (su * u + sv * v))
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    return [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]


def surfaces_model(tmp_path, stem, surfaces, extra=()):
    """A node per `(positions)` in `surfaces`, material k + 1 for the k-th,
    and `extra` nodes of an unrelated material."""
    model = GlbWriter()
    nodes = [
        model.node(f"s{k}", mesh=model.mesh(positions, material=model.material(GREY)))
        for k, positions in enumerate(surfaces)
    ]
    for k, positions in enumerate(extra):
        mesh = model.mesh(positions, material=model.material(GREY))
        nodes.append(model.node(f"x{k}", mesh=mesh))
    model.scene(nodes, default=True)
    return model.write(tmp_path, stem)


def pixel_offsets(shape, ground_px, ppm, supersample):
    """Each pixel centre's offset from the ground point along the camera's
    right and up axes, in meters."""
    height, width = shape
    columns = (np.arange(width) + 0.5) / supersample - ground_px[0]
    rows = ground_px[1] - (np.arange(height) + 0.5) / supersample
    across, up = np.meshgrid(columns / ppm, rows / ppm)
    return across, up


# Normals


TILTED = {
    1: ((-0.6, 0.3, 0.0), (0.3, 0.6, 0.74)),
    2: ((0.6, 0.3, 0.0), (-0.4, 0.5, 0.77)),
}


@pytest.mark.parametrize("pitch", [0.0, 30.0, 90.0])
def test_a_plane_reads_its_exact_camera_space_normal(found, tmp_path, pitch):
    path = surfaces_model(
        tmp_path, "planes", [plane(c, n, 0.25) for c, n in TILTED.values()]
    )
    result, job = render(
        found,
        path,
        tmp_path,
        pitch=pitch,
        directions=8,
        ppm=40.0,
        cell=(80, 48),
        ground_px=(40, 30),
        supersample=2,
    )
    for ordinal in (0, 1):
        angle = job["frames"][ordinal]["angle_deg"]
        right, up, toward = axes(pitch, angle)
        codes, normal, _ = frame(result, ordinal)
        for code, (_, world) in TILTED.items():
            n = np.asarray(world) / np.linalg.norm(world)
            assert n @ toward > 0.2, "the fixture must face the camera"
            expected = np.array((n @ right, n @ up, n @ toward))
            hit = codes == code
            assert hit.sum() > 100, (pitch, angle, code)
            errors = angle_deg(normal[hit], expected)
            assert errors.max() <= PLANE_TOLERANCE_DEG, (pitch, angle, code)
        # The two planes' x components have opposite signs head-on.
        if ordinal == 0:
            assert normal[codes == 1][:, 0].mean() > 0 > normal[codes == 2][:, 0].mean()


def sphere_errors(found, tmp_path, smooth):
    """The angles between a sphere's captured normals and the exact sphere's,
    over the pixels facing the viewer by 0.3 or more, in two directions."""
    center, radius = np.array((0.0, 0.4, 0.0)), 0.3
    model = Model()
    positions, normals = sphere(tuple(center), radius, rings=48, segments=96)
    model.primitive(
        positions, model.material("ball"), normals=normals if smooth else None
    )
    stem = "smooth" if smooth else "faceted"
    path = model.write(tmp_path, stem)
    pitch, ppm, ground_px, supersample = 30.0, 100.0, (40, 68), 2
    result, job = render(
        found,
        path,
        tmp_path,
        pitch=pitch,
        directions=2,
        ppm=ppm,
        cell=(80, 72),
        ground_px=ground_px,
        supersample=supersample,
        workspace=stem,
    )
    errors = []
    for ordinal in (0, 1):
        right, up, _ = axes(pitch, job["frames"][ordinal]["angle_deg"])
        codes, normal, _ = frame(result, ordinal)
        across, above = pixel_offsets(codes.shape, ground_px, ppm, supersample)
        dx = across - center @ right
        dy = above - center @ up
        inside = np.clip(radius**2 - dx**2 - dy**2, 0.0, None)
        expected = np.stack((dx, dy, np.sqrt(inside)), axis=-1) / radius
        facing = (codes != 0) & (expected[..., 2] >= 0.3)
        assert facing.sum() > 2000
        errors.append(angle_deg(normal[facing], expected[facing]))
    return np.concatenate(errors)


def test_a_smooth_sphere_reads_its_interpolated_normals(found, tmp_path):
    errors = sphere_errors(found, tmp_path, smooth=True)
    assert errors.mean() <= SPHERE_MEAN_DEG, errors.mean()
    assert errors.max() <= SPHERE_MAX_DEG, errors.max()
    # The measurement tells interpolated normals from flat face normals: the
    # same sphere without vertex normals is shaded flat, and far off.
    faceted = sphere_errors(found, tmp_path, smooth=False)
    assert faceted.mean() >= 5 * SPHERE_MEAN_DEG, faceted.mean()


def test_normals_ignore_every_material_property(found, tmp_path):
    # The form fixture plain and with textures, metallic and roughness (D-16).
    from material_models import appearance

    options = dict(pitch=30.0, ppm=40.0, cell=(128, 112), ground_px=(64, 80))
    plain, _ = render(
        found, form(tmp_path), tmp_path, supersample=1, workspace="a", **options
    )
    varied, _ = render(
        found, appearance(tmp_path), tmp_path, supersample=1, workspace="b", **options
    )
    (a,) = plain.buffers.values()
    (b,) = varied.buffers.values()
    for name in ("normal", "depth"):
        assert a[name].read_bytes() == b[name].read_bytes(), name


# Depth


def facing_quads(z_values, half=0.25):
    """A square facing +Z at each z, side by side across x."""
    count = len(z_values)
    quads = []
    for k, z in enumerate(z_values):
        x = (k - (count - 1) / 2) * 0.7
        quads.append(plane((x, 0.3, z), (0.0, 0.0, 1.0), half))
    return quads


def expected_depth(z, pitch, angle, shape, ground_px, ppm, supersample):
    """Each pixel's depth where its view ray meets the plane at `z` (the
    ground point at the origin)."""
    right, up, toward = axes(pitch, angle)
    across, above = pixel_offsets(shape, ground_px, ppm, supersample)
    return (z - across * right[2] - above * up[2]) / toward[2]


@pytest.mark.parametrize("pitch", [0.0, 30.0])
def test_surfaces_in_front_of_and_behind_the_ground_point_read_signed_depths(
    found, tmp_path, pitch
):
    # Repeated with a far cube, out of frame, that moves the camera 60 m
    # farther from the ground point: depth is relative to it, so unchanged.
    z_values = {1: 0.3, 2: -0.5}
    options = dict(
        pitch=pitch, ppm=40.0, cell=(72, 48), ground_px=(36, 36), supersample=2
    )
    depths = []
    for stem, extra in (("near", ()), ("far", [cube((60.0, 0.0, 0.0), 0.1)])):
        path = surfaces_model(
            tmp_path, stem, facing_quads(list(z_values.values())), extra
        )
        result, _ = render(found, path, tmp_path, workspace=stem, **options)
        codes, _, depth = frame(result)
        for code, z in z_values.items():
            hit = codes == code
            assert hit.sum() > 100
            expected = expected_depth(z, pitch, 0.0, codes.shape, (36, 36), 40.0, 2)
            assert np.abs(depth[hit] - expected[hit]).max() <= DEPTH_TOLERANCE_M
        # In front of the ground point's plane is positive, behind it negative.
        assert (depth[codes == 1] > 0).all() and (depth[codes == 2] < 0).all()
        depths.append(depth)
    np.testing.assert_allclose(depths[0], depths[1], atol=DEPTH_TOLERANCE_M)


def test_a_plane_at_a_known_position_reads_its_depth(found, tmp_path):
    # A floor 0.2 m above the ground point, seen from above: depth 0.2 m.
    floor = plane((0.0, 0.2, 0.0), (0.0, 1.0, 0.0), 0.4)
    path = surfaces_model(tmp_path, "floor", [floor])
    result, _ = render(
        found, path, tmp_path, pitch=90.0, ppm=40.0, cell=(40, 40), ground_px=(20, 20)
    )
    codes, normal, depth = frame(result)
    hit = codes == 1
    assert hit.sum() > 1000
    assert np.abs(depth[hit] - 0.2).max() <= DEPTH_TOLERANCE_M
    assert (
        angle_deg(normal[hit], np.array((0.0, 0.0, 1.0))).max() <= PLANE_TOLERANCE_DEG
    )


def test_depths_far_beyond_the_depth_map_s_range_are_carried(found, tmp_path):
    # 120 m at 40 px/m is 4800 sheet pixels toward or away from the viewer,
    # beyond the depth map's ±2047.9375; capture is never limited by it (D-21).
    z_values = {1: 120.0, 2: -120.0}
    path = surfaces_model(tmp_path, "deep", facing_quads(list(z_values.values()), 0.2))
    result, _ = render(
        found, path, tmp_path, ppm=40.0, cell=(48, 32), ground_px=(24, 28)
    )
    codes, _, depth = frame(result)
    for code, z in z_values.items():
        hit = codes == code
        assert hit.sum() > 50
        assert np.abs(depth[hit] - z).max() <= 1e-3
        assert np.abs(depth[hit] * 40.0).min() > 2047.9375


# Coverage, repeats and sequences


@pytest.mark.parametrize("supersample", [1, 4])
@pytest.mark.parametrize("fixture", ["edges", "form"])
def test_normal_and_depth_coverage_is_the_material_id_s(
    found, tmp_path, fixture, supersample
):
    path = {"edges": edges, "form": form}[fixture](tmp_path)
    result, _ = render(
        found,
        path,
        tmp_path,
        pitch=30.0,
        directions=2,
        ppm=40.0,
        cell=(96, 128),
        ground_px=(48, 100),
        supersample=supersample,
    )
    for paths in result.buffers.values():
        with Image.open(paths["matid"]) as image:
            covered = np.asarray(image)[..., 3] == 255
        assert covered.any() and not covered.all()
        for name in ("normal", "depth"):
            samples = backend.read_wide_png(paths[name])
            assert ((samples[..., 3] == backend.SURFACE) == covered).all(), name
            assert not samples[~covered].any(), name


def test_repeat_renders_give_identical_normal_and_depth_files(found, tmp_path):
    path = form(tmp_path)
    options = dict(pitch=30.0, ppm=40.0, cell=(128, 112), ground_px=(64, 80))
    first, _ = render(
        found, path, tmp_path, supersample=2, workspace="first", **options
    )
    second, _ = render(
        found, path, tmp_path, supersample=2, workspace="second", **options
    )
    for a, b in zip(first.buffers.values(), second.buffers.values(), strict=True):
        for name in ("normal", "depth"):
            assert a[name].read_bytes() == b[name].read_bytes(), name


def test_a_frame_s_normal_and_depth_are_the_same_alone_and_within_a_sequence(
    found, tmp_path
):
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
    for name in ("normal", "depth"):
        assert within[name].read_bytes() == single[name].read_bytes(), name


@pytest.mark.parametrize(
    ("cell", "supersample"),
    [((1, 6), 1), ((3, 6), 1), ((6, 1), 1), ((6, 3), 1), ((1, 1), 2), ((3, 1), 1)],
    ids=["1 wide", "3 wide", "1 tall", "3 tall", "1x1 at 2x", "3x1"],
)
def test_small_and_uneven_frames_are_the_corner_of_an_uncropped_render(
    found, tmp_path, cell, supersample
):
    # Blender renders at least 4 pixels each way; a smaller frame is the
    # top-left corner of the same render, cropped. Its ID, normal and depth
    # must be exactly that corner's.
    path = marker_model(tmp_path, "marker")
    options = dict(pitch=30.0, ground_px=(1, 1), supersample=supersample, ppm=10.0)
    small, _ = render(found, path, tmp_path, cell=cell, workspace="small", **options)
    # The same padded frame, at least 4 pixels each way, uncropped: the same
    # camera, so the same samples.
    least = -(-4 // supersample)
    reference_cell = (max(cell[0], least), max(cell[1], least))
    whole, _ = render(
        found, path, tmp_path, cell=reference_cell, workspace="whole", **options
    )
    width, height = cell[0] * supersample, cell[1] * supersample
    (a,) = small.buffers.values()
    (b,) = whole.buffers.values()
    with Image.open(a["matid"]) as image, Image.open(b["matid"]) as reference:
        ids = np.asarray(image)
        assert ids.shape[:2] == (height, width)
        np.testing.assert_array_equal(ids, np.asarray(reference)[:height, :width])
    assert (ids[..., 3] == 255).any()
    for name in ("normal", "depth"):
        samples = backend.read_wide_png(a[name])
        corner = backend.read_wide_png(b[name])[:height, :width]
        np.testing.assert_array_equal(samples, corner, err_msg=name)


# Restoration (requirement 2)

RESTORE_PROBE = """
import importlib.util, json, os, sys, tempfile
import bpy

path = sys.argv[sys.argv.index("--") + 1]
spec = importlib.util.spec_from_file_location("probe_script", path)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)
scene = bpy.context.scene
cube = bpy.data.objects["Cube"]
cube.data.materials.clear()
script.configure_render(scene, {
    "supersample": 1, "cell": {"width": 8, "height": 6},
})


def state():
    image = scene.render.image_settings
    return {
        "aovs": [(aov.name, aov.type) for aov in bpy.context.view_layer.aovs],
        "image": [
            getattr(image, name)
            for name in ("media_type", "file_format", "color_mode", "color_depth",
                         "exr_codec")
        ],
        "render": [scene.render.engine, scene.render.filepath],
        "cycles": [scene.cycles.samples, scene.cycles.seed],
        "materials": sorted(m.name for m in bpy.data.materials),
        "groups": sorted(g.name for g in bpy.data.node_groups),
        "slots": len(cube.data.materials),
    }


scratch = tempfile.mkdtemp()
tga, exr = os.path.join(scratch, "a.tga"), os.path.join(scratch, "a.exr")
scene.render.filepath = tga
before = state()
shade = {"ao_distance_m": 0.3, "ao_samples": 4, "occlusion_weight": 0.25,
         "convexity_weight": 1.0, "materials": []}
surfaces = script.Surfaces(scene, [cube], {}, shade, {})
surfaces.apply()
during = state()
try:
    bpy.ops.render.render(write_still=True)
    script.save_exr(scene, exr)
finally:
    surfaces.restore()
layer = bpy.context.view_layer.name
names = (
    [f"{layer}.Combined.A", f"{layer}.matid.X", f"{layer}.shade.X"]
    + [f"{layer}.normal.{axis}" for axis in "RGB"]
    + [f"{layer}.depth.X"]
)
channels = script.read_exr(exr, 8, 6, names)
print("PROBE " + json.dumps({
    "before": before, "during": during, "after": state(),
    "lengths": sorted({len(values) for values in channels.values()}),
}))
"""


def test_the_capture_shaders_are_restored_and_save_exr_keeps_the_settings(
    found, tmp_path
):
    probe = tmp_path / "probe.py"
    probe.write_text(RESTORE_PROBE)
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
    # While it runs: the five AOVs, the stand-in and the count switch; after
    # it, nothing, and saving the OpenEXR leaves the render's own image
    # settings as they were.
    assert probed["during"]["aovs"] == [
        ["matid", "VALUE"],
        ["shade", "VALUE"],
        ["normal", "COLOR"],
        ["depth", "VALUE"],
        ["hit", "VALUE"],
    ]
    assert "moskophoros.no-material" in probed["during"]["materials"]
    assert probed["during"]["groups"] == ["moskophoros.count"]
    assert probed["before"]["render"][0] == "CYCLES"
    assert probed["after"] == probed["before"]
    assert probed["before"]["aovs"] == []
    assert probed["before"]["image"][:2] == ["IMAGE", "TARGA_RAW"]
    assert probed["lengths"] == [48]


@pytest.mark.parametrize("pitch", [0.0, 30.0])
@pytest.mark.parametrize(
    "ground",
    [(0.0, 0.0, 0.0), (0.0, 0.0, 10000.0), (-3.3, 1.7, 2.9), (250.25, -40.5, -1300.75)],
    ids=["origin", "far along z", "off origin", "far off origin"],
)
def test_depth_is_relative_to_a_translated_ground_point(found, tmp_path, ground, pitch):
    # A square facing +Z 0.5 m in front of the ground point's plane, wherever
    # the ground point is. The depth is measured from the camera Blender
    # stores, in single precision; measured from the camera as placed in
    # double precision, it was 4·10⁻⁵ m off 10 km from the origin, head-on.
    # Viewed obliquely, Cycles' single-precision ray arithmetic limits any
    # depth to about the float32 spacing of the surface's coordinates.
    gx, gy, gz = ground
    square = plane((gx, gy + 0.3, gz + 0.5), (0.0, 0.0, 1.0), 0.25)
    path = surfaces_model(tmp_path, "translated", [square])
    result, _ = render(
        found,
        path,
        tmp_path,
        pitch=pitch,
        ground=ground,
        ppm=40.0,
        cell=(40, 40),
        ground_px=(20, 36),
        supersample=2,
    )
    codes, _, depth = frame(result)
    hit = codes == 1
    assert hit.sum() > 1000
    expected = expected_depth(0.5, pitch, 0.0, codes.shape, (20, 36), 40.0, 2)
    if pitch == 0:
        tolerance = TRANSLATED_TOLERANCE_M
    else:
        spacing = float(np.spacing(np.float32(max(map(abs, ground)) + 2.0)))
        tolerance = 1e-5 + 2 * spacing
    assert np.abs(depth[hit] - expected[hit]).max() <= tolerance


# Reduced to the sheet's pixels (LIT-2)


@pytest.mark.parametrize("supersample", [1, 3])
def test_the_command_reduces_captured_normals_and_depth_to_the_sheet(
    found, tmp_path, capsys, monkeypatch, supersample
):
    # Squares facing the viewer 0.3 m in front of the ground point and 0.5 m
    # behind it, head-on at 40 px/m: 12 and −20 sheet pixels, whatever the
    # supersample factor.
    from moskophoros import cli, export
    from moskophoros.sampling import DEPTH_MAP, NORMAL_MAP

    path = surfaces_model(tmp_path, "squares", facing_quads([0.3, -0.5]))
    seen = {}
    real = export.encode

    def recording(frames, **kwargs):
        seen["frames"] = tuple(frames)
        return real(frames, **kwargs)

    monkeypatch.setattr(export, "encode", recording)
    status = cli.run(
        [
            "--no-user-config",
            "--pitch",
            "0",
            "--directions",
            "1",
            "--ppm",
            "40",
            "--cell",
            "72x40",
            "--supersample",
            str(supersample),
            "--no-preview",
            "--blender",
            str(found.path),
            str(path),
            str(tmp_path / "squares.png"),
        ]
    )
    _, err = capsys.readouterr()
    assert status == 0, err
    (frame,) = seen["frames"]
    covered = frame.pixels[..., 3] == 255
    normals, depths = frame.buffers[NORMAL_MAP], frame.buffers[DEPTH_MAP]
    assert covered.sum() > 100
    assert set(np.unique(depths[covered])) == {-20.0, 12.0}
    assert angle_deg(normals[covered], np.array((0.0, 0.0, 1.0))).max() <= 0.01
    assert (normals[~covered] == 0).all() and (depths[~covered] == 0).all()


# The depth map (LIT-4)


def test_the_depth_map_reads_a_plane_s_depth_in_sheet_pixels(found, tmp_path, capsys):
    # Squares facing the viewer 0.3 m in front of the ground point and 0.5 m
    # behind it, head-on at 40 px/m: 12 and −20 sheet pixels, codes 32960
    # and 32448, in front above 32768 and behind below it (R-5).
    import io

    from PIL import Image

    from moskophoros import cli

    path = surfaces_model(tmp_path, "squares", facing_quads([0.3, -0.5]))
    out = tmp_path / "squares.png"
    status = cli.run(
        [
            "--no-user-config",
            "--pitch",
            "0",
            "--directions",
            "1",
            "--ppm",
            "40",
            "--cell",
            "72x40",
            "--supersample",
            "2",
            "--no-preview",
            "--depth",
            "--blender",
            str(found.path),
            str(path),
            str(out),
        ]
    )
    _, err = capsys.readouterr()
    assert status == 0, err
    with Image.open(out) as image:
        alpha = np.asarray(image)[..., 3]
    codes = np.asarray(
        Image.open(io.BytesIO((tmp_path / "squares.depth.png").read_bytes()))
    )
    assert codes.dtype == np.uint16 and codes.shape == alpha.shape
    covered = alpha == 255
    assert covered.sum() > 100
    assert set(np.unique(codes[covered])) == {32768 + 12 * 16, 32768 - 20 * 16}
    assert (codes[~covered] == 0).all()
    assert codes[covered].max() > 32768 > codes[covered].min()
