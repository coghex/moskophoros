"""Render jobs run through the launcher on generated models, in real Blender.

Expected pixel positions are worked out here from the fixtures' known
geometry, independently of the script. Workbench antialiases with a small
fixed sample pattern, which moves a shape's coverage centroid by up to about
a quarter of a supersampled pixel, so positions are compared within
`TOLERANCE_PX`.
"""

import hashlib
import io
import math
import struct

import pytest
from glb_writer import GlbWriter
from PIL import Image

from moskophoros import gltf, sampling, views
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

TOLERANCE_PX = 0.35
RED = (1.0, 0.0, 0.0, 1.0)
GREEN = (0.0, 1.0, 0.0, 1.0)
IDENTITY = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def cube(center, half):
    """Triangles of an axis-aligned cube."""
    x, y, z = center
    corners = [
        (x + dx * half, y + dy * half, z + dz * half)
        for dx in (-1, 1)
        for dy in (-1, 1)
        for dz in (-1, 1)
    ]
    faces = [
        (0, 1, 3, 2),
        (4, 6, 7, 5),
        (0, 4, 5, 1),
        (2, 3, 7, 6),
        (0, 2, 6, 4),
        (1, 5, 7, 3),
    ]
    triangles = []
    for a, b, c, d in faces:
        triangles += [
            corners[a],
            corners[b],
            corners[c],
            corners[a],
            corners[c],
            corners[d],
        ]
    return triangles


def quad(x0, y0, x1, y1):
    """Two triangles of a rectangle in the z = 0 plane, facing +Z."""
    return [
        (x0, y0, 0.0),
        (x1, y0, 0.0),
        (x1, y1, 0.0),
        (x0, y0, 0.0),
        (x1, y1, 0.0),
        (x0, y1, 0.0),
    ]


def render(
    found,
    path,
    tmp_path,
    *,
    pitch=0.0,
    directions=1,
    start=0.0,
    yaw=0.0,
    fps=4.0,
    ground=(0.0, 0.0, 0.0),
    ppm=10.0,
    cell=(20, 20),
    ground_px=(10, 10),
    supersample=2,
    clip_names=(),
    workspace="work",
):
    """Render `path` with a fixed configuration; return (result, job)."""
    subject = gltf.read_glb(path)
    clips = gltf.select_clips(subject, clip_names, ())
    settings = backend.Settings(
        "custom",
        pitch,
        directions,
        start,
        yaw,
        fps,
        supersample,
        ppm,
        cell,
        ground,
        ground_px,
        "error",
    )
    frames = sampling.frames(
        subject.name, clips, views.View(pitch, directions, start, yaw), fps
    )
    root = tmp_path / workspace
    root.mkdir()
    source = backend.Source(
        path.resolve(),
        hashlib.sha256(path.read_bytes()).hexdigest(),
        subject.scene_index,
    )
    job = backend.build_job(
        "render", source, subject.name, settings, clips, frames, str(root / "render")
    )
    return blender.run_phase(found, root, job), job


def images(result):
    """{address: RGBA image}, in request order."""
    loaded = {}
    for address, buffers in result.buffers.items():
        with Image.open(buffers["color"]) as image:
            loaded[address] = image.convert("RGBA")
    return loaded


def centroid(image, keep):
    """The alpha-weighted centre of the pixels whose color `keep` accepts, in
    pixel-corner coordinates from the top left."""
    pixels = image.load()
    total = sx = sy = 0.0
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a and keep(r, g, b):
                total += a
                sx += a * (x + 0.5)
                sy += a * (y + 0.5)
    assert total, "no pixels of that color"
    return sx / total, sy / total


def reddish(r, g, b):
    return r > g and r > b


def greenish(r, g, b):
    return g > r and g > b


def projected(point, ground, rotation_deg, pitch_deg, ppm, supersample, ground_px):
    """Where `point` lands in the supersampled image: turned by `rotation_deg`
    about the vertical through `ground`, counter-clockwise seen from above,
    then projected with screen right +X and screen up (0, cos p, −sin p)."""
    a = math.radians(rotation_deg)
    p = math.radians(pitch_deg)
    dx, dy, dz = (point[i] - ground[i] for i in range(3))
    turned_x = dx * math.cos(a) + dz * math.sin(a)
    turned_z = -dx * math.sin(a) + dz * math.cos(a)
    up = dy * math.cos(p) - turned_z * math.sin(p)
    scale = ppm * supersample
    return (
        ground_px[0] * supersample + turned_x * scale,
        ground_px[1] * supersample - up * scale,
    )


# Geometry


GROUND = (0.3, 0.2, -0.1)
FEATURE = (GROUND[0] + 0.4, GROUND[1] + 0.25, GROUND[2] - 0.3)


def placement_model(tmp_path):
    """A red cube centred on the ground point and a green one off it."""
    model = GlbWriter()
    red = model.material(RED)
    green = model.material(GREEN)
    marker = model.node("marker", mesh=model.mesh(cube(GROUND, 0.08), material=red))
    feature = model.node(
        "feature", mesh=model.mesh(cube(FEATURE, 0.08), material=green)
    )
    model.scene([marker, feature], default=True)
    return model.write(tmp_path, "placement")


@pytest.mark.parametrize("pitch", [0.0, 30.0, 90.0], ids=["side-on", "30", "top-down"])
def test_the_ground_point_and_an_off_ground_feature_land_where_projected(
    found, tmp_path, pitch
):
    # A rectangular cell, an off-centre ground pixel, a nonzero ground point,
    # yaw and supersampling, at three directions.
    cell, ground_px, supersample, ppm, yaw = (24, 20), (9, 11), 2, 10.0, 25.0
    result, job = render(
        found,
        placement_model(tmp_path),
        tmp_path,
        pitch=pitch,
        directions=3,
        start=10.0,
        yaw=yaw,
        ground=GROUND,
        ppm=ppm,
        cell=cell,
        ground_px=ground_px,
        supersample=supersample,
    )
    rendered = images(result)
    assert len(rendered) == 3
    for (address, image), angle in zip(
        rendered.items(), [10.0, 130.0, 250.0], strict=True
    ):
        assert image.size == (cell[0] * supersample, cell[1] * supersample)
        marker = centroid(image, reddish)
        assert marker == pytest.approx(
            (ground_px[0] * supersample, ground_px[1] * supersample), abs=TOLERANCE_PX
        ), address
        expected = projected(
            FEATURE, GROUND, angle + yaw, pitch, ppm, supersample, ground_px
        )
        assert centroid(image, greenish) == pytest.approx(expected, abs=TOLERANCE_PX), (
            address
        )


def test_no_bone_display_shape_is_rendered(found, tmp_path):
    # A skinned cube away from the ground point; the importer's bone display
    # shape would sit at the armature's origin, the ground point.
    model = GlbWriter()
    joint = model.node("joint")
    skin = model.skin([joint], [IDENTITY])
    corners = cube((0.6, 0.0, 0.0), 0.1)
    mesh = model.mesh(
        corners,
        joints=[(0, 0, 0, 0)] * len(corners),
        skin_weights=[(1, 0, 0, 0)] * len(corners),
        material=model.material(RED),
    )
    model.scene([joint, model.node("body", mesh=mesh, skin=skin)], default=True)
    result, _ = render(found, model.write(tmp_path, "skinned"), tmp_path)
    (image,) = images(result).values()
    pixels = image.load()
    around_ground = [pixels[x, y][3] for x in range(14, 26) for y in range(14, 26)]
    assert max(around_ground) == 0
    # The cube itself is there, 0.6 m to the right: x ≈ 20 + 12.
    assert centroid(image, reddish) == pytest.approx((32.0, 20.0), abs=TOLERANCE_PX)


# Color and alpha


def blue_png():
    data = io.BytesIO()
    Image.new("RGB", (2, 2), (0, 0, 255)).save(data, format="PNG")
    return data.getvalue()


def test_material_and_texture_colors_on_a_transparent_background(found, tmp_path):
    # Facing the camera: an untextured red quad on the left, and on the right
    # a quad whose white material carries a blue texture.
    model = GlbWriter()
    plain = model.mesh(quad(-0.8, -0.3, -0.2, 0.3), material=model.material(RED))
    textured = model.mesh(
        quad(0.2, -0.3, 0.8, 0.3),
        material=model.material(texture=model.texture(blue_png())),
        texcoords=[
            (0.0, 1.0),
            (1.0, 1.0),
            (1.0, 0.0),
            (0.0, 1.0),
            (1.0, 0.0),
            (0.0, 0.0),
        ],
    )
    model.scene(
        [model.node("plain", mesh=plain), model.node("textured", mesh=textured)]
    )
    model.document["scene"] = 0
    result, _ = render(
        found,
        model.write(tmp_path, "colors"),
        tmp_path,
        cell=(20, 10),
        ground_px=(10, 5),
    )
    (image,) = images(result).values()
    assert image.size == (40, 20)
    pixels = image.load()
    # The quads cover x 4..16 and 24..36, y 4..16; the corners are empty.
    for corner in [(0, 0), (39, 0), (0, 19), (39, 19), (20, 10)]:
        assert pixels[corner][3] == 0, corner
    r, g, b, a = pixels[10, 10]
    assert a == 255 and r > 3 * max(g, b, 1), pixels[10, 10]
    r, g, b, a = pixels[30, 10]
    assert a == 255 and b > 3 * max(r, g, 1), pixels[30, 10]


def test_edge_pixels_keep_straight_alpha(found, tmp_path):
    # A red quad facing the camera, whose left and right edges fall halfway
    # across pixel columns: partly covered pixels keep the face's color, with
    # alpha giving the coverage, rather than color scaled by alpha.
    model = GlbWriter()
    mesh = model.mesh(quad(-0.425, -0.3, 0.425, 0.3), material=model.material(RED))
    model.scene([model.node("plate", mesh=mesh)], default=True)
    result, _ = render(found, model.write(tmp_path, "plate"), tmp_path)
    (image,) = images(result).values()
    pixels = image.load()
    face = pixels[20, 20]
    assert face[3] == 255
    partial = [
        pixels[x, y]
        for x in range(image.width)
        for y in range(image.height)
        if 30 < pixels[x, y][3] < 225
    ]
    assert len(partial) >= 10
    # Straight alpha keeps each channel near the face's, within the slight
    # darkening of Workbench's edge filtering. Premultiplied alpha would
    # scale red by the coverage, below 225/255 ≈ 0.88 of the face's.
    for r, g, b, a in partial:
        assert r >= 0.9 * face[0], (r, g, b, a)
        assert abs(g - face[1]) <= 3 and abs(b - face[2]) <= 3, (r, g, b, a)


# Clips, repeatability and the result


def clip_model(tmp_path):
    """Two clips from t0 = 0.1 s, each moving one cube up 0.5 m:

    - `slide` moves the red cube, an object, from y = 0;
    - `bend` moves the green cube, skinned to a joint, from y = 0.
    """
    model = GlbWriter()
    red = model.node(
        "red",
        mesh=model.mesh(cube((0.0, 0.0, 0.0), 0.08), material=model.material(RED)),
        translation=(-0.5, 0.0, 0.0),
    )
    joint = model.node("joint", translation=(0.5, 0.0, 0.0))
    skin = model.skin([joint], [(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -0.5, 0, 0, 1)])
    corners = cube((0.5, 0.0, 0.0), 0.08)
    green = model.mesh(
        corners,
        joints=[(0, 0, 0, 0)] * len(corners),
        skin_weights=[(1, 0, 0, 0)] * len(corners),
        material=model.material(GREEN),
    )
    model.scene([red, joint, model.node("green", mesh=green, skin=skin)], default=True)
    model.animation(
        "slide", [(red, "translation", [0.1, 1.1], [(-0.5, 0.0, 0), (-0.5, 0.5, 0)])]
    )
    model.animation(
        "bend", [(joint, "translation", [0.1, 1.1], [(0.5, 0.0, 0), (0.5, 0.5, 0)])]
    )
    return model.write(tmp_path, "clips")


def test_clips_render_the_same_in_either_order_at_their_evaluated_poses(
    found, tmp_path
):
    path = clip_model(tmp_path)
    first, _ = render(
        found, path, tmp_path, clip_names=["slide", "bend"], workspace="a"
    )
    second, _ = render(
        found, path, tmp_path, clip_names=["bend", "slide"], workspace="b"
    )
    one, other = images(first), images(second)
    assert set(one) == set(other)
    for address in one:
        assert one[address].tobytes() == other[address].tobytes(), address
    # Samples at 0.1, 0.35, 0.6 and 0.85 s are Blender frames 2.4 to 20.4,
    # between keyframes. The moving cube rises 0.5·(t − 0.1) m, 10 px per
    # 0.5 m at 20 px per meter; the other stays at its static place.
    for address, image in one.items():
        rise = 0.5 * (address.time_s - 0.1) * 20
        red_y = 20 - rise if address.clip == "slide" else 20
        green_y = 20 - rise if address.clip == "bend" else 20
        assert centroid(image, reddish) == pytest.approx((10, red_y), abs=TOLERANCE_PX)
        assert centroid(image, greenish) == pytest.approx(
            (30, green_y), abs=TOLERANCE_PX
        )


def png_chunks(path):
    data = path.read_bytes()
    kinds = []
    offset = 8
    while offset < len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        kinds.append(data[offset + 4 : offset + 8].decode("ascii"))
        offset += 12 + length
    return kinds


def test_the_same_job_renders_byte_identical_files_without_stamps(found, tmp_path):
    path = clip_model(tmp_path)
    first, _ = render(found, path, tmp_path, workspace="first")
    second, _ = render(found, path, tmp_path, workspace="second")
    one = [buffers["color"] for buffers in first.buffers.values()]
    other = [buffers["color"] for buffers in second.buffers.values()]
    assert [p.name for p in one] == [f"{i:06d}.png" for i in range(8)]
    for a, b in zip(one, other, strict=True):
        assert a.read_bytes() == b.read_bytes()
        assert not {"tEXt", "zTXt", "iTXt", "tIME"} & set(png_chunks(a))


def test_the_result_records_the_renderer_and_studio_light(found, tmp_path):
    result, job = render(found, placement_model(tmp_path), tmp_path)
    assert result.backend == {
        "blender": found.version,
        "renderer": "workbench",
        "studio_light": "Default",
    }
    phase = tmp_path / "work" / "render"
    listing = sorted(p.relative_to(phase).as_posix() for p in phase.rglob("*"))
    assert listing == ["color", "color/000000.png", "job.json", "result.json"]
