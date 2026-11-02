"""The capture script's pure encoders, loaded without Blender: the shade
byte the `Standard` transform gives, and the material-ID AOV's codes and
coverage (alpha design, Capture transport and provenance). A refusal here
is the script's error, which fails the command with exit 5."""

import base64
import importlib.util
import math
import struct
import sys
import types
from array import array
from dataclasses import replace

import pytest
from glb_writer import GlbWriter

from moskophoros.capture import blender


@pytest.fixture(scope="module")
def script():
    """blender_script.py, with a stand-in for `bpy`, which only Blender has."""
    saved = sys.modules.get("bpy")
    sys.modules["bpy"] = types.ModuleType("bpy")
    try:
        spec = importlib.util.spec_from_file_location("capture_script", blender.SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if saved is None:
            del sys.modules["bpy"]
        else:
            sys.modules["bpy"] = saved
    return module


def srgb(value):
    if value <= 0.0031308:
        return 12.92 * value
    return 1.055 * value ** (1 / 2.4) - 0.055


def test_a_quarter_shade_is_137(script):
    assert script.shade_byte(0.25) == 137


@pytest.mark.parametrize(
    ("value", "byte"),
    [(0.0, 0), (1.0, 255), (-0.5, 0), (2.0, 255), (0.5, 188), (0.001, 3)],
)
def test_the_shade_byte_is_the_standard_transform_s(script, value, byte):
    assert script.shade_byte(value) == byte


def test_every_shade_byte_rounds_the_srgb_value_half_up(script):
    for step in range(1001):
        value = step / 1000
        assert script.shade_byte(value) == math.floor(255 * srgb(value) + 0.5)


CODES = {1, 2, 255, 256, 65535}


@pytest.mark.parametrize("value", [1.0, 256.0, 65535.0, 0.0])
def test_an_exact_code_is_read(script, value):
    assert script.material_code(value, CODES | {0}) == int(value)


@pytest.mark.parametrize(
    "value",
    [1.5, 0.9999999, 3.0, 65536.0, -1.0, math.nan, math.inf],
    ids=["half", "almost one", "unknown", "too large", "negative", "nan", "inf"],
)
def test_a_value_that_is_no_exact_code_is_refused(script, value):
    with pytest.raises(script.ScriptError, match="material-ID AOV holds"):
        script.material_code(value, CODES | {0})


def frame(ids, shades, alpha, width=2):
    covered = [
        bytes(255 if a else 0 for a in alpha[y : y + width])
        for y in range(0, len(alpha), width)
    ]
    return array("f", ids), array("f", shades), covered


def test_the_material_id_and_shade_rows(script):
    ids, shades, covered = frame(
        [0.0, 255.0, 256.0, 65535.0], [0.0, 0.25, 1.0, 0.5], [0, 1, 1, 1]
    )
    id_rows, shade_rows = script.id_and_shade_rows(
        ids, shades, covered, 2, CODES, "frame 0"
    )
    assert [bytes(row) for row in id_rows] == [
        bytes([0, 0, 0, 0, 0, 255, 0, 255]),
        bytes([1, 0, 0, 255, 255, 255, 0, 255]),
    ]
    assert [bytes(row) for row in shade_rows] == [
        bytes([0, 0, 0, 0, 137, 137, 137, 255]),
        bytes([255, 255, 255, 255, 188, 188, 188, 255]),
    ]


@pytest.mark.parametrize(
    ("ids", "alpha", "message"),
    [
        (
            [0.0, 1.0],
            [1, 1],
            r"material ID at pixel \(0, 0\) is 0, but the colour there shows a surface",
        ),
        (
            [1.0, 2.0],
            [1, 0],
            r"material ID at pixel \(1, 0\) is 2, but the colour there shows no surface",
        ),
        ([1.0, 2.5], [1, 1], "material-ID AOV holds 2.5"),
        ([1.0, 7.0], [1, 1], "material-ID AOV holds 7.0"),
    ],
)
def test_a_material_id_that_disagrees_or_is_no_code_is_refused(
    script, ids, alpha, message
):
    ids, shades, covered = frame(ids, [0.0, 0.0], alpha)
    with pytest.raises(script.ScriptError, match=message):
        script.id_and_shade_rows(ids, shades, covered, 2, CODES, "frame 0")


def test_coverage_accepts_only_whole_surfaces(script):
    assert script.coverage(array("f", [0.0, 1.0, 1.0, 0.0]), 2, "frame 0") == [
        bytes([0, 255]),
        bytes([255, 0]),
    ]
    with pytest.raises(script.ScriptError, match=r"alpha at pixel \(1, 1\) is 0.5"):
        script.coverage(array("f", [0.0, 1.0, 1.0, 0.5]), 2, "frame 0")


def test_the_colour_rows_mask_empty_pixels_and_follow_the_alpha(script):
    rows = [bytearray([9, 9, 9, 0, 200, 100, 50, 255])]
    assert script.colour_rows(rows, [bytes([0, 255])], "frame 0") == [
        bytearray([0, 0, 0, 0, 200, 100, 50, 255])
    ]
    with pytest.raises(
        script.ScriptError, match=r"colour at pixel \(1, 0\) has 8-bit alpha 255"
    ):
        script.colour_rows(
            [bytearray([9, 9, 9, 0, 1, 2, 3, 255])], [bytes([0, 0])], "frame 0"
        )


def test_a_frame_of_more_than_256_codes(script):
    # More distinct codes than a byte can index takes the slower path.
    codes = set(range(1, 301))
    ids = array("f", [float(code) for code in range(1, 301)] + [0.0] * 4)
    shades = array("f", [0.25] * 300 + [0.0] * 4)
    covered = [bytes([255] * 300 + [0] * 4)]
    (identity,), (level,) = script.id_and_shade_rows(
        ids, shades, covered, 304, codes, "f"
    )
    assert [(identity[4 * i], identity[4 * i + 1]) for i in (0, 255, 299)] == [
        (0, 1),
        (1, 0),
        (1, 44),
    ]
    assert identity[4 * 300 :] == bytes(16)
    assert level[0:4] == bytes([137, 137, 137, 255]) and level[4 * 300 :] == bytes(16)


# The surface gate and the count render (alpha design ALPHA-2)


def test_whole_hits_on_the_colour_s_surfaces_pass(script):
    script.check_hits(
        array("f", [0.0, 1.0, 1.0, 0.0]), [bytes([0, 255]), bytes([255, 0])], 2, "f"
    )


@pytest.mark.parametrize("value", [0.5, 2.0, 1e-30, -1.0, math.nan])
def test_a_hit_other_than_0_or_1_is_refused(script, value):
    hits = array("f", [0.0, 1.0, value, 1.0])
    with pytest.raises(
        script.ScriptError, match=r"surface gate's hit at pixel \(0, 1\) is"
    ):
        script.check_hits(hits, [bytes([0, 255]), bytes([255, 255])], 2, "frame 3")


def test_a_refusal_names_the_first_pixel_s_own_value(script):
    values = array("f", [1.0, 0.25, 0.0, 0.75])
    with pytest.raises(script.ScriptError) as hit:
        script.check_hits(values, [bytes([255, 255]), bytes([0, 255])], 2, "frame 3")
    assert str(hit.value) == (
        "frame 3: the surface gate's hit at pixel (1, 0) is 0.25, not exactly 0 or 1"
    )
    with pytest.raises(script.ScriptError) as alpha:
        script.coverage(values, 2, "frame 3")
    assert str(alpha.value) == (
        "frame 3: the render's alpha at pixel (1, 0) is 0.25, not a whole opaque "
        "surface or none"
    )


def test_hits_off_the_colour_s_surfaces_are_refused(script):
    with pytest.raises(
        script.ScriptError,
        match=r"frame 3: the surface gate at pixel \(1, 0\) shows no surface, but "
        r"the colour there shows a surface",
    ):
        script.check_hits(array("f", [1.0, 0.0]), [bytes([255, 255])], 2, "frame 3")


PLACE = "/models/fence.glb: clip 'walk', direction 3, frame 17 (t = 0.25 s)"


def test_a_count_of_64_passes(script):
    script.check_count(array("f", [0.0, 64.0, 12.0, 64.0]), 2, PLACE)


@pytest.mark.parametrize("deepest", [65.0, 100.0])
def test_a_count_of_65_or_more_names_the_frame_and_the_limit(script, deepest):
    with pytest.raises(script.ScriptError) as raised:
        script.check_count(array("f", [0.0, 3.0, deepest, 64.0]), 2, PLACE)
    assert str(raised.value) == (
        f"{PLACE}: a camera path at pixel (0, 1) crossed more than 64 surfaces "
        "that still let light through, which the capture cannot render (the "
        "limit is 64)"
    )
    assert script.LAYER_LIMIT == 64


def test_a_nan_alpha_is_refused(script):
    with pytest.raises(script.ScriptError, match=r"alpha at pixel \(1, 0\) is nan"):
        script.coverage(array("f", [0.0, math.nan]), 2, "frame 0")


# The camera (projects and camera design D-7, D-8, D-10, D-14)


def legacy_bounds(points, ground, rotation_deg, pitch_deg):
    """The pitch-only camera's measured bounds, as the script computed them
    before the camera had a direction."""
    a = math.radians(rotation_deg)
    p = math.radians(pitch_deg)
    cos_a, sin_a, cos_p, sin_p = math.cos(a), math.sin(a), math.cos(p), math.sin(p)
    gx, gy, gz = ground
    xs = []
    ys = []
    for x, y, z in points:
        dx, dy, dz = x - gx, y - gy, z - gz
        turned_x = dx * cos_a + dz * sin_a
        turned_z = -dx * sin_a + dz * cos_a
        xs.append(turned_x)
        ys.append(cos_p * dy - sin_p * turned_z)
    return {
        "L": max(0.0, -min(xs)),
        "R": max(0.0, *xs),
        "U": max(0.0, *ys),
        "D": max(0.0, -min(ys)),
    }


def camera(direction, roll=0.0):
    return {"direction": list(direction), "roll": roll}


def bits(values):
    return [float(value).hex() for value in values]


PITCHES = [0.0, 1e-9, 12.5, 30.0, 35.264389682754654, 45.0, 47.25, 60.0, 89.999, 90.0]
ROTATIONS = [0.0, 12.5, 45.0, 90.0, 135.0, 180.0, 270.0, 359.0]


@pytest.mark.parametrize("pitch", PITCHES)
def test_a_pitch_direction_measures_today_s_bounds_bit_for_bit(script, pitch):
    import random

    from moskophoros import views

    generator = random.Random(int(pitch * 1000))
    points = [tuple(generator.uniform(-2.0, 2.0) for _ in range(3)) for _ in range(64)]
    points += [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)]
    axes = script.measure_axes(camera(views.pitch_direction(pitch)))
    for ground in [(0.0, 0.0, 0.0), (0.25, -0.5, 1.5)]:
        for rotation in ROTATIONS:
            assert bits(script.bounds(points, ground, rotation, axes).values()) == bits(
                legacy_bounds(points, ground, rotation, pitch).values()
            ), (ground, rotation)


def test_straight_down_keeps_the_pitch_camera_s_rounding(script):
    # cos 90° is about 6e-17 in floating point, not 0, and the pitch-only
    # camera measured with it; at 1 pixel per meter that small part makes
    # the fitted cell 4 pixels tall rather than 3.
    from moskophoros import fit, sampling

    points = [(-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (0.0, -1.0, 0.0)]
    axes = script.measure_axes(camera((0.0, -1.0, 0.0)))
    box = script.bounds(points, (0.0, 0.0, 0.0), 0.0, axes)
    assert box == legacy_bounds(points, (0.0, 0.0, 0.0), 0.0, 90.0)
    assert box["D"] == 6.123233995736766e-17
    address = sampling.FrameAddress("cube", "default", "static", 0, 0.0)
    bounds = fit.Bounds(box["L"], box["R"], box["U"], box["D"])
    resolved = fit.resolve({address: fit.Measurement(bounds, 0.0)}, ppm=1.0)
    assert resolved.cell[1] == 4
    # A roll, or any other direction, measures with the exact axes.
    rolled = script.measure_axes(camera((0.0, -1.0, 0.0), 1.0))
    assert rolled[1][1] == 0.0


@pytest.mark.parametrize(
    ("direction", "roll"),
    [
        ((0.0, -0.5, -0.8660254037844386), 0.0),
        ((0.0, -1.0, 0.0), 0.0),
        ((0.0, 1.0, 0.0), 0.25),
        ((0.3, -0.7, -0.2), 0.37),
        ((-1.0, 0.25, 1.0), -0.5),
        ((0.1, 0.1, 0.1), 1.0),
        ((0.6, 0.0, 0.8), -1.0),
    ],
)
def test_the_script_s_axes_are_moskophoros_views(script, direction, roll):
    from moskophoros import views

    unit = views.normalise(direction)
    toward, right, up = script.subject_axes(camera(unit, roll))
    basis = views.subject_basis(unit, roll)
    assert bits(right) == bits(basis.right)
    assert bits(up) == bits(basis.up)
    assert toward == pytest.approx(tuple(-value for value in basis.forward))


@pytest.mark.parametrize("pitch", PITCHES)
def test_a_pitch_direction_places_today_s_camera_axes_bit_for_bit(script, pitch):
    from moskophoros import views

    sin_p, cos_p = script._sin_cos(pitch)
    legacy = ((0.0, sin_p, cos_p), (1.0, 0.0, 0.0), (0.0, cos_p, 0.0 - sin_p))
    axes = script.subject_axes(camera(views.pitch_direction(pitch)))
    for axis, expected in zip(axes, legacy, strict=True):
        assert bits(axis) == bits(expected)


def valid_job():
    from test_capture_backend import CLIPS, MEASURE_SETTINGS, SOURCE, VIEW

    from moskophoros import plan
    from moskophoros.capture import backend

    frames = plan.plan("hero", CLIPS, VIEW, MEASURE_SETTINGS.fps)
    return backend.build_job(
        "measure", SOURCE, "hero", MEASURE_SETTINGS, CLIPS, frames, "/work/measure"
    )


def test_the_script_accepts_the_launcher_s_camera_record(script):
    job = valid_job()
    assert job["schema"] == script.JOB_SCHEMA == "moskophoros.capture-job/3"
    script.check_job(job)
    job["settings"]["camera"] |= {"roll": -1, "position": [0, 1.5, -3.0]}
    script.check_job(job)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"projection": "fisheye"}, "the projection"),
        ({"projection": "perspective"}, "the perspective camera has no position"),
        (
            {"projection": "perspective", "position": [0, -1, -1]},
            "the ground point is not in front of the perspective camera",
        ),
        ({"direction": [0.0, 0.0, 0.0]}, "settings.camera.direction"),
        ({"direction": [0.0, -0.5, -0.5]}, "settings.camera.direction"),
        ({"direction": [0.0, -1.0]}, "settings.camera.direction"),
        ({"direction": [0.0, True, 0.0]}, "settings.camera.direction"),
        ({"direction": None}, "settings.camera.direction"),
        ({"roll": 1.5}, "settings.camera.roll"),
        ({"roll": "0"}, "settings.camera.roll"),
        ({"position": [0, 1]}, "settings.camera.position"),
        ({"position": [0, 1, "2"]}, "settings.camera.position"),
        ({"fov": 50}, "settings.camera is missing"),
    ],
)
def test_the_script_refuses_a_malformed_camera_record(script, change, message):
    job = valid_job()
    job["settings"]["camera"] |= change
    with pytest.raises(script.ScriptError, match=message):
        script.check_job(job)


@pytest.mark.parametrize(
    ("view", "message"),
    [
        ({"pitch_deg": 30.0}, "settings.view is missing"),
        ({"projection": "orthographic"}, "settings.view is missing"),
    ],
)
def test_the_script_refuses_the_old_view_record(script, view, message):
    job = valid_job()
    job["settings"]["view"] |= view
    with pytest.raises(script.ScriptError, match=message):
        script.check_job(job)


# The perspective camera (projects and camera design D-3, D-10, D-12, D-16)

PERSPECTIVE_CAMERAS = [
    ((0.3, -0.6, -0.7), 0.3, (-1.5, 2.25, 2.0)),
    ((0.0, -0.5, -0.8660254037844386), 0.0, (0.0, 2.0, 3.4641016151377544)),
    ((0.0, -1.0, 0.0), -0.75, (0.25, 4.0, 0.5)),
    ((-1.0, 0.25, 0.5), 1.0, (3.0, -0.5, -1.0)),
    ((0.0, 0.0, -1.0), 0.5, (1.0, 0.5, 4.0)),
]


def perspective_camera(direction, roll, position):
    from moskophoros import views

    return {
        "projection": "perspective",
        "direction": list(views.normalise(direction)),
        "roll": roll,
        "position": list(position),
    }


@pytest.mark.parametrize("given", PERSPECTIVE_CAMERAS)
def test_the_script_s_perspective_frame_is_moskophoros_views(script, given):
    from moskophoros import views

    camera = perspective_camera(*given)
    axes, position, ground = script.perspective_frame(camera)
    expected = views.perspective(camera["direction"], camera["roll"], given[2])
    for axis, wanted in zip(axes, views.basis_axes(expected.basis), strict=True):
        assert bits(axis) == bits(wanted)
    assert bits(position) == bits(expected.position)
    assert bits(ground) == bits(expected.ground)


@pytest.mark.parametrize("rotation", ROTATIONS)
@pytest.mark.parametrize("given", PERSPECTIVE_CAMERAS)
def test_the_script_s_perspective_bounds_are_moskophoros_views(script, given, rotation):
    import random

    from moskophoros import views

    generator = random.Random(int(rotation * 10))
    points = [tuple(generator.uniform(-0.5, 0.5) for _ in range(3)) for _ in range(32)]
    ground = (0.1, 0.2, -0.05)
    camera = perspective_camera(*given)
    box, depth = script.perspective_bounds(
        points, ground, rotation, script.perspective_frame(camera)
    )
    wanted, wanted_depth = views.perspective_bounds(
        views.perspective(camera["direction"], camera["roll"], given[2]),
        points,
        ground,
        rotation,
    )
    assert bits(depth) == bits(wanted_depth)
    assert bits(box.values()) == bits(wanted)


def test_the_script_measures_a_frame_too_near_to_project(script):
    camera = perspective_camera((0.0, 0.0, -1.0), 0.0, (0.0, 0.0, 2.0))
    frame = script.perspective_frame(camera)
    points = [(0.0, 0.0, 0.0), (0.0, 0.0, 2.5), (0.0, 0.0, -1.0)]
    assert script.perspective_bounds(points, (0.0, 0.0, 0.0), 0.0, frame) == (
        None,
        [-0.5, 3.0],
    )
    # At the limit itself, as moskophoros.views.NEAR_LIMIT says.
    near = [(0.0, 0.0, 2.0 - script.NEAR_LIMIT), (0.0, 0.0, 0.0)]
    box, depth = script.perspective_bounds(near, (0.0, 0.0, 0.0), 0.0, frame)
    assert (box is None) == (depth[0] <= script.NEAR_LIMIT)
    # With no vertex, the ground point's own depth.
    assert script.perspective_bounds([], (0.0, 0.0, 0.0), 0.0, frame) == (
        {"L": 0.0, "R": 0.0, "U": 0.0, "D": 0.0},
        [2.0, 2.0],
    )


@pytest.mark.parametrize(
    "arguments",
    [
        (40.0, 3.26, 1, 128),
        (40.0, 3.26, 4, 512),
        (1.0, 1.0, 1, 64),
        (0.5, 0.25, 2, 1000),
        (24.0, 1.7, 8, 192),
    ],
)
def test_the_script_s_calibration_is_moskophoros_views(script, arguments):
    from moskophoros import views

    assert bits(script.calibration(*arguments)) == bits(views.calibration(*arguments))


@pytest.mark.parametrize(
    ("ground", "size", "ground_px"),
    [
        ((0.5, -0.25, 3.0), (40, 80), (5, 30)),
        ((-0.5, 0.25, 3.0), (80, 40), (30, 5)),
        ((0.31, 0.77, 2.5), (48, 64), (11, 29)),
    ],
)
def test_the_script_s_lens_shift_is_moskophoros_views(script, ground, size, ground_px):
    from moskophoros import views

    assert bits(script.lens_shift(10.0, 2, ground, size, ground_px)) == bits(
        views.lens_shift(10.0, 2, ground, size, ground_px)
    )


def perspective_job(mode="measure", clipping=None):
    from test_capture_backend import CLIPS, MEASURE_SETTINGS, SOURCE, VIEW

    from moskophoros import plan
    from moskophoros.capture import backend

    settings = replace(
        MEASURE_SETTINGS, projection="perspective", position=(0.0, 1.5, 2.5)
    )
    if mode == "render":
        settings = replace(settings, ppm=10.0, cell=(4, 3), ground_px=(2, 2))
    frames = plan.plan("hero", CLIPS, VIEW, settings.fps)
    return backend.build_job(
        mode, SOURCE, "hero", settings, CLIPS, frames, f"/work/{mode}", clipping
    )


def test_the_script_accepts_the_launcher_s_perspective_jobs(script):
    from moskophoros.capture import backend

    script.check_job(perspective_job())
    job = perspective_job("render", backend.Clipping(0.5, 7.0, (1.0, 3.0)))
    assert job["clipping"] == {"near_m": 0.5, "far_m": 7.0, "depth_m": [1.0, 3.0]}
    script.check_job(job)


@pytest.mark.parametrize(
    ("clipping", "message"),
    [
        (None, "clipping is not an object"),
        ({"near_m": 0.5, "far_m": 7.0}, "clipping is missing"),
        ({"near_m": 1.0, "far_m": 7.0, "depth_m": [1.0, 3.0]}, "do not enclose"),
        ({"near_m": 0.5, "far_m": 3.0, "depth_m": [1.0, 3.0]}, "do not enclose"),
        ({"near_m": 0.0, "far_m": 7.0, "depth_m": [1.0, 3.0]}, "do not enclose"),
        ({"near_m": 0.5, "far_m": 7.0, "depth_m": [3.0, 1.0]}, "do not enclose"),
        ({"near_m": 0.5, "far_m": 7.0, "depth_m": [1.0]}, "not two numbers"),
        ({"near_m": 0.5, "far_m": 7.0, "depth_m": [True, 3.0]}, "not two numbers"),
        ({"near_m": "0.5", "far_m": 7.0, "depth_m": [1.0, 3.0]}, "do not enclose"),
    ],
)
def test_the_script_refuses_a_perspective_render_s_bad_clipping(
    script, clipping, message
):
    from moskophoros.capture import backend

    job = perspective_job("render", backend.Clipping(0.5, 7.0, (1.0, 3.0)))
    job["clipping"] = clipping
    with pytest.raises(script.ScriptError, match=message):
        script.check_job(job)


def test_the_script_refuses_clipping_for_any_other_job(script):
    clipping = {"near_m": 0.5, "far_m": 7.0, "depth_m": [1.0, 3.0]}
    for job in (valid_job(), perspective_job()):
        job["clipping"] = clipping
        with pytest.raises(script.ScriptError, match="only a perspective render"):
            script.check_job(job)


# Cubic spline animation and mesh weight pointers, which the script rewrites
# in its private copy before Blender imports it


def load(script, model, tmp_path, name="subject"):
    """The decoded document, binary rest and source path of a written model."""
    path = model.write(tmp_path, name)
    document, rest = script.split_glb(path.read_bytes(), str(path))
    return document, rest, str(path)


def bezier(points, s):
    """De Casteljau's algorithm for a cubic Bézier curve."""
    while len(points) > 1:
        points = [(1 - s) * a + s * b for a, b in zip(points, points[1:], strict=False)]
    return points[0]


def hermite(p0, out, p1, into, step, s):
    """glTF's cubic spline segment, for a key interval of `step` seconds."""
    return (
        (2 * s**3 - 3 * s**2 + 1) * p0
        + (s**3 - 2 * s**2 + s) * step * out
        + (-2 * s**3 + 3 * s**2) * p1
        + (s**3 - s**2) * step * into
    )


def test_cubic_output_is_split_into_keys(script):
    # Two keys of two components: (in, value, out) each.
    values, ins, outs, block = script.cubic_keys(
        [0.0, 2.0], [*(0, 0), *(1, 2), *(3, -3), *(0, 6), *(2, 4), *(5, 5)]
    )
    assert block == 2
    assert values == [(1, 2), (2, 4)]
    assert ins == [(0, 0), (0, 6)]
    assert outs == [(3, -3), (5, 5)]


KEYS = {
    # Keys at 0, 2 and 3 s of two components, as (in, value, out) triples:
    # (0, 1, 3) and (−6, 4, 0), then (1, 2, 5) for the second component.
    "times": [0.0, 2.0, 3.0],
    "values": [(1.0, 2.0), (4.0, -1.0), (0.5, 0.5)],
    "ins": [(0.0, 0.0), (-6.0, 2.0), (7.0, -4.0)],
    "outs": [(3.0, 1.0), (0.0, -3.0), (0.0, 0.0)],
}


def test_a_cubic_spline_is_evaluated_by_glTFs_formula(script):
    for time_s in (0.0, 0.25, 1.0, 1.999, 2.0, 2.0001, 2.5, 2.999999, 3.0):
        k = 0 if time_s < 2.0 else 1
        step = KEYS["times"][k + 1] - KEYS["times"][k]
        s = (time_s - KEYS["times"][k]) / step
        want = tuple(
            hermite(
                KEYS["values"][k][c],
                KEYS["outs"][k][c],
                KEYS["values"][k + 1][c],
                KEYS["ins"][k + 1][c],
                step,
                s,
            )
            for c in range(2)
        )
        assert script.cubic_value(KEYS, time_s) == pytest.approx(want, abs=1e-12)


def test_a_cubic_spline_has_the_bezier_curve_of_its_thirds(script):
    # Keys at 0 and 2 s: the segment's controls sit at p0 + Δt·m0/3 and
    # p1 − Δt·a1/3, and the curve is Bézier in the fraction of the interval.
    first = KEYS["values"][0][0] + 2 * KEYS["outs"][0][0] / 3
    last = KEYS["values"][1][0] - 2 * KEYS["ins"][1][0] / 3
    for s in (0.0, 0.1, 0.5, 0.9, 1.0):
        got = script.cubic_value(KEYS, 2 * s)[0]
        assert got == pytest.approx(
            bezier([KEYS["values"][0][0], first, last, KEYS["values"][1][0]], s)
        )


def test_a_cubic_spline_holds_its_end_values_and_a_single_key(script):
    assert script.cubic_value(KEYS, -5.0) == (1.0, 2.0)
    assert script.cubic_value(KEYS, 3.0) == (0.5, 0.5)
    assert script.cubic_value(KEYS, 99.0) == (0.5, 0.5)
    single = {"times": [1.0], "values": [(7.0,)], "ins": [(0.0,)], "outs": [(0.0,)]}
    assert [script.cubic_value(single, t) for t in (0.0, 1.0, 2.0)] == [(7.0,)] * 3


def test_a_cubic_spline_is_exact_a_microsecond_from_a_steep_key(script):
    # The reviewer's curve: a key at a 32-bit time 9.5e-7 s before 0.5 s, with
    # an out-tangent of 1024 per second. Blender's evaluator reads the key's
    # value there; the exact value is 0.00098.
    keys = {
        "times": [0.0, 0.4999990463256836, 0.50048828125, 1.0],
        "values": [(0.0,), (0.0,), (0.5,), (0.0,)],
        "ins": [(0.0,)] * 4,
        "outs": [(0.0,), (1024.0,), (0.0,), (0.0,)],
    }
    (got,) = script.cubic_value(keys, 0.5)
    step = 0.50048828125 - 0.4999990463256836
    s = (0.5 - 0.4999990463256836) / step
    assert got == pytest.approx(hermite(0.0, 1024.0, 0.5, 0.0, step, s), abs=1e-12)
    assert got == pytest.approx(0.00097845, abs=1e-8)


@pytest.mark.parametrize(
    ("times", "values", "message"),
    [
        ([0.0, 1.0], [0.0] * 5, "an in-tangent, a value and an out-tangent"),
        ([0.0, 1.0], [0.0] * 7, "an in-tangent, a value and an out-tangent"),
        ([], [], "an in-tangent, a value and an out-tangent"),
        ([0.0, 0.0], [0.0] * 6, "do not increase"),
        ([1.0, 0.0], [0.0] * 6, "do not increase"),
    ],
)
def test_malformed_cubic_data_is_refused(script, times, values, message):
    with pytest.raises(ValueError, match=message):
        script.cubic_keys(times, values)


def affine(matrix, offset, point):
    return tuple(
        sum(m * p for m, p in zip(row, point, strict=True)) + o
        for row, o in zip(matrix, offset, strict=True)
    )


@pytest.mark.parametrize("path", ["translation", "scale", "rotation"])
def test_an_affine_conversion_is_measured_from_the_calibration_keys(script, path):
    points = script._CALIBRATION[path]
    d = len(points[0])
    # A permutation with a sign, a scaling and an offset, as the importer applies.
    matrix = [[0.0] * d for _ in range(d)]
    for i in range(d):
        matrix[i][(i + 1) % d] = -1.0 if i == 0 else 2.0
    offset = [0.25 * (i + 1) for i in range(d)]
    images = [affine(matrix, offset, point) for point in points]
    solved = script.solve_affine(points, images)
    assert solved is not None
    assert [v for row in solved[0] for v in row] == pytest.approx(
        [v for row in matrix for v in row], abs=1e-9
    )
    assert solved[1] == pytest.approx(offset, abs=1e-9)


def test_a_conversion_that_is_not_affine_is_not_measured(script):
    points = script._CALIBRATION["translation"]
    images = [tuple(x * x for x in point) for point in points]
    assert script.solve_affine(points, images) is None


def test_accessors_are_read_with_strides_offsets_and_normalization(script, tmp_path):
    model = GlbWriter()
    model._accessor("VEC3", [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)], False)
    document, rest, source = load(script, model, tmp_path)
    fetch = script.buffer_reader(document, script.binary_chunk(rest), source)
    assert script.read_accessor(document, fetch, 0, source) == [
        (1.0, 2.0, 3.0),
        (4.0, 5.0, 6.0),
    ]
    # The same data, every other float of a strided view, from an offset.
    document["bufferViews"][0]["byteStride"] = 24
    document["accessors"][0].update(count=1, byteOffset=4)
    assert script.read_accessor(document, fetch, 0, source) == [(2.0, 3.0, 4.0)]
    # Bytes read as normalized unsigned and signed integers.
    payload = base64.b64encode(bytes([0, 255, 128, 128])).decode("ascii")
    document["buffers"][0]["uri"] = f"data:;base64,{payload}"
    document["bufferViews"][0] = {"buffer": 0, "byteLength": 4}
    document["accessors"][0] = {
        "bufferView": 0,
        "componentType": 5121,
        "normalized": True,
        "count": 1,
        "type": "VEC4",
    }
    fetch = script.buffer_reader(document, None, source)
    assert script.read_accessor(document, fetch, 0, source) == [
        (0.0, 1.0, 128 / 255, 128 / 255)
    ]
    # As signed bytes, 255 is −1 and 128 is −128, which clamps to −1.
    document["accessors"][0]["componentType"] = 5120
    assert script.read_accessor(document, fetch, 0, source) == [
        (0.0, -1 / 127, -1.0, -1.0)
    ]
    # No buffer view means zeros.
    document["accessors"][0] = {"componentType": 5126, "count": 2, "type": "VEC2"}
    assert script.read_accessor(document, fetch, 0, source) == [(0.0, 0.0)] * 2


@pytest.mark.parametrize(
    "change",
    [
        {"sparse": {}},
        {"sparse": {"count": 1, "indices": {"bufferView": 0, "componentType": 5121}}},
        {"count": 1000},
        {"bufferView": 7},
        {"type": "MAT4"},
        {"componentType": 1},
    ],
    ids=[
        "sparse without parts",
        "sparse without values",
        "past the end",
        "no such view",
        "a matrix",
        "no such type",
    ],
)
def test_unreadable_accessors_are_refused_by_name(script, tmp_path, change):
    model = GlbWriter()
    model._accessor("VEC3", [(1.0, 2.0, 3.0)], False)
    document, rest, source = load(script, model, tmp_path)
    document["accessors"][0].update(change)
    fetch = script.buffer_reader(document, script.binary_chunk(rest), source)
    with pytest.raises(script.ScriptError, match="accessor 0"):
        script.read_accessor(document, fetch, 0, source)


def sparse_model(positions):
    """Four VEC3 rows of zeros but for sparse replacements at `positions`,
    which are (1, 2, 3) and (4, 5, 6)."""
    model = GlbWriter()
    indices = model._view(struct.pack(f"<{len(positions)}H", *positions))
    values = model._view(struct.pack("<6f", 1, 2, 3, 4, 5, 6))
    model.document["accessors"] = [
        {
            "componentType": 5126,
            "count": 4,
            "type": "VEC3",
            "sparse": {
                "count": 2,
                "indices": {"bufferView": indices, "componentType": 5123},
                "values": {"bufferView": values},
            },
        }
    ]
    return model


def test_a_sparse_accessor_has_its_replacements_applied(script, tmp_path):
    document, rest, source = load(script, sparse_model([1, 3]), tmp_path)
    fetch = script.buffer_reader(document, script.binary_chunk(rest), source)
    assert script.read_accessor(document, fetch, 0, source) == [
        (0.0, 0.0, 0.0),
        (1.0, 2.0, 3.0),
        (0.0, 0.0, 0.0),
        (4.0, 5.0, 6.0),
    ]


def test_a_sparse_accessor_replaces_rows_of_its_buffer_view(script, tmp_path):
    model = sparse_model([0, 2])
    model.document["accessors"][0]["bufferView"] = model._view(
        struct.pack("<12f", *range(12))
    )
    document, rest, source = load(script, model, tmp_path)
    fetch = script.buffer_reader(document, script.binary_chunk(rest), source)
    assert script.read_accessor(document, fetch, 0, source) == [
        (1.0, 2.0, 3.0),
        (3.0, 4.0, 5.0),
        (4.0, 5.0, 6.0),
        (9.0, 10.0, 11.0),
    ]


def test_a_sparse_index_beyond_the_accessor_is_refused(script, tmp_path):
    document, rest, source = load(script, sparse_model([1, 4]), tmp_path)
    fetch = script.buffer_reader(document, script.binary_chunk(rest), source)
    with pytest.raises(script.ScriptError, match="accessor 0"):
        script.read_accessor(document, fetch, 0, source)


def test_a_buffer_in_a_file_beside_the_source_is_read(script, tmp_path):
    (tmp_path / "data.bin").write_bytes(b"abcd")
    document = {"buffers": [{"uri": "data.bin", "byteLength": 4}]}
    fetch = script.buffer_reader(document, None, str(tmp_path / "model.glb"))
    assert fetch(0) == b"abcd"
    document["buffers"].append({"uri": "missing.bin", "byteLength": 4})
    fetch = script.buffer_reader(document, None, str(tmp_path / "model.glb"))
    with pytest.raises(script.ScriptError, match="cannot read buffer 1"):
        fetch(1)


def shared_mesh_model():
    """Nodes 0 and 1 share mesh 0; node 2 has its own weights; node 3 is in
    another scene. Animation 0 holds a mesh pointer and a translation."""
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0)] * 3],
        weights=[0.0],
    )
    a = model.node("a", mesh=mesh)
    b = model.node("b", mesh=mesh)
    c = model.node("c", mesh=mesh, weights=[0.5])
    d = model.node("d", mesh=mesh)
    model.scene([a, b, c], default=True)
    model.scene([d])
    clip = model.animation("swell", [(a, "translation", [0, 1], [(0, 0, 0)] * 2)])
    model.pointer_channel(clip, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    return model, (a, b, c, d)


def channel_targets(animation):
    return [
        (channel["target"].get("node"), channel["target"]["path"], channel["sampler"])
        for channel in animation["channels"]
    ]


def test_a_mesh_pointer_goes_to_the_nodes_of_the_scene_using_the_mesh(script):
    model, (a, b, c, d) = shared_mesh_model()
    emptied = script.distribute_mesh_weights(model.document, 0)
    assert emptied == []
    # The translation stays; nodes a and b follow the pointer's sampler 1;
    # node c has weights of its own and node d is not in the scene.
    assert channel_targets(model.document["animations"][0]) == [
        (a, "translation", 0),
        (a, "weights", 1),
        (b, "weights", 1),
    ]


def test_a_node_animated_by_the_clip_keeps_its_own_weights(script):
    model, (a, b, c, d) = shared_mesh_model()
    clip = model.document["animations"][0]
    clip["channels"].insert(0, {"sampler": 0, "target": {"node": b, "path": "weights"}})
    script.distribute_mesh_weights(model.document, 0)
    assert channel_targets(clip) == [
        (b, "weights", 0),
        (a, "translation", 0),
        (a, "weights", 1),
    ]


def test_a_node_weight_pointer_also_keeps_its_own_weights(script):
    model, (a, b, c, d) = shared_mesh_model()
    model.pointer_channel(0, f"/nodes/{a}/weights", [0, 1], [(0.0,), (0.25,)])
    script.distribute_mesh_weights(model.document, 0)
    assert channel_targets(model.document["animations"][0])[1:] == [
        (b, "weights", 1),
        (None, "pointer", 2),
    ]


def test_the_selected_scene_decides_which_nodes_follow_a_mesh_pointer(script):
    model, (a, b, c, d) = shared_mesh_model()
    script.distribute_mesh_weights(model.document, 1)
    assert channel_targets(model.document["animations"][0]) == [
        (a, "translation", 0),
        (d, "weights", 1),
    ]


def test_an_animation_left_without_a_channel_is_reported(script):
    model, (a, b, c, d) = shared_mesh_model()
    quiet = model.animation("quiet", [])
    model.pointer_channel(quiet, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    model.document["nodes"][a]["weights"] = [0.0]
    model.document["nodes"][b]["weights"] = [0.0]
    emptied = script.distribute_mesh_weights(model.document, 0)
    assert emptied == [model.document["animations"][1]]
    assert model.document["animations"][1]["channels"] == []


def test_a_document_without_animations_or_scene_nodes_is_left_alone(script):
    model = GlbWriter()
    model.scene([model.node("box", mesh=True)], default=True)
    assert script.distribute_mesh_weights(model.document, 0) == []
    assert "animations" not in model.document


def test_the_private_copy_reduces_cubic_samplers_to_their_keys(script, tmp_path):
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    keys = [
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (3.0, 0.0, 0.0)),
        ((-3.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    ]
    model.animation(
        "sway",
        [(shape, "translation", [0.0, 3.0], [row for key in keys for row in key])],
        interpolation="CUBICSPLINE",
    )
    document, rest, source = load(script, model, tmp_path)
    glb, cubics = script.private_copy(document, rest, source, 0)
    assert cubics == {
        0: {
            (shape, "translation"): {
                "times": [0.0, 3.0],
                "values": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
                "ins": [(0.0, 0.0, 0.0), (-3.0, 0.0, 0.0)],
                "outs": [(3.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
                "rotation": False,
            }
        }
    }
    copy, binary = script.split_glb(glb, source)
    fetch = script.buffer_reader(copy, script.binary_chunk(binary), source)
    # The placeholder animation comes first; the clip's sampler is LINEAR and
    # holds the values alone.
    sampler = copy["animations"][1]["samplers"][0]
    assert sampler["interpolation"] == "LINEAR"
    assert script.read_accessor(copy, fetch, sampler["input"], source) == [
        (0.0,),
        (3.0,),
    ]
    assert script.read_accessor(copy, fetch, sampler["output"], source) == [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    ]
    # The last animation measures the importer's conversion of the node's
    # translation with the calibration keys.
    calibration = copy["animations"][-1]
    assert calibration["name"] == script.CALIBRATION_NAME
    assert [c["target"] for c in calibration["channels"]] == [
        {"node": shape, "path": "translation"}
    ]
    sampler = calibration["samplers"][calibration["channels"][0]["sampler"]]
    assert script.read_accessor(copy, fetch, sampler["output"], source) == [
        tuple(map(float, point)) for point in script._CALIBRATION["translation"]
    ]
    # The original document is untouched.
    assert document["animations"][0]["samplers"][0]["interpolation"] == "CUBICSPLINE"


def test_files_without_cubic_translation_rotation_or_scale_get_no_calibration(
    script, tmp_path
):
    model = GlbWriter()
    face = model.node(
        "face",
        mesh=model.mesh(
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            targets=[[(0.0, 0.0, 0.0)] * 3],
            weights=[0.0],
        ),
    )
    model.scene([face], default=True)
    keys = [((0.0,), (0.0,), (4.0,)), ((-4.0,), (0.0,), (0.0,))]
    model.animation(
        "rise",
        [(face, "weights", [0, 1], [row for key in keys for row in key])],
        interpolation="CUBICSPLINE",
    )
    document, rest, source = load(script, model, tmp_path)
    glb, cubics = script.private_copy(document, rest, source, 0)
    copy, _ = script.split_glb(glb, source)
    assert [a["name"] for a in copy["animations"]] == [
        script.PLACEHOLDER,
        "moskophoros.animation.0",
    ]
    assert list(cubics[0]) == [(face, "weights")]


def test_every_channel_sharing_a_cubic_sampler_is_recorded(script, tmp_path):
    model, (a, b, c, d) = shared_mesh_model()
    clip = model.animation("rise", [])
    model.pointer_channel(
        clip,
        "/meshes/0/weights",
        [0, 1],
        [(0.0,), (0.0,), (4.0,), (-4.0,), (0.0,), (0.0,)],
        interpolation="CUBICSPLINE",
    )
    document, rest, source = load(script, model, tmp_path)
    _, cubics = script.private_copy(document, rest, source, 0)
    # Nodes a and b both follow the pointer's one sampler.
    assert sorted(cubics[1]) == [(a, "weights"), (b, "weights")]
    assert cubics[1][(a, "weights")] is cubics[1][(b, "weights")]


def test_other_cubic_samplers_are_left_as_they_are(script, tmp_path):
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.document["cameras"] = [
        {"type": "perspective", "perspective": {"yfov": 0.8, "znear": 0.1}}
    ]
    clip = model.animation("pan", [(shape, "translation", [0, 1], [(0, 0, 0)] * 2)])
    model.pointer_channel(
        clip,
        "/cameras/0/perspective/yfov",
        [0, 1],
        [(0.0,), (0.8,), (0.0,), (0.0,), (1.0,), (0.0,)],
        interpolation="CUBICSPLINE",
    )
    document, rest, source = load(script, model, tmp_path)
    _, cubics = script.private_copy(document, rest, source, 0)
    assert cubics == {}


def test_a_cubic_rotation_is_calibrated_with_quaternions_that_turn_gently(
    script, tmp_path
):
    points = script._CALIBRATION["rotation"]
    for before, after in zip(points, points[1:], strict=False):
        assert sum(a * b for a, b in zip(before, after, strict=True)) > 0.5


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: s.update(input=99), "accessor 99"),
        (lambda s: s.pop("output"), "no readable input and output"),
        (lambda s: s.update(output=99), "accessor 99"),
    ],
    ids=["no such input", "no output", "no such output"],
)
def test_a_broken_sampler_fails_the_script(script, tmp_path, change, message):
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    flat = (0.0, 0.0, 0.0)
    model.animation(
        "sway",
        [(shape, "translation", [0, 1], [flat] * 6)],
        interpolation="CUBICSPLINE",
    )
    change(model.document["animations"][0]["samplers"][0])
    document, rest, source = load(script, model, tmp_path)
    with pytest.raises(script.ScriptError, match=message):
        script.private_copy(document, rest, source, 0)


@pytest.mark.parametrize(
    ("kind", "rows", "message"),
    [
        ("VEC3", 5, "an in-tangent, a value and an out-tangent"),
        ("VEC4", 6, "does not hold translation values"),
    ],
)
def test_cubic_data_of_the_wrong_shape_fails_the_script(
    script, tmp_path, kind, rows, message
):
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    model.animation(
        "bad",
        [(shape, "translation", [0, 1], [(0.0,) * 3] * 6)],
        interpolation="CUBICSPLINE",
    )
    sampler = model.document["animations"][0]["samplers"][0]
    width = {"VEC3": 3, "VEC4": 4}[kind]
    sampler["output"] = model._accessor(kind, [(0.0,) * width] * rows, False)
    document, rest, source = load(script, model, tmp_path)
    with pytest.raises(script.ScriptError, match=message):
        script.private_copy(document, rest, source, 0)


def test_an_animation_the_pointer_emptied_animates_the_placeholder(script, tmp_path):
    model, (a, b, c, d) = shared_mesh_model()
    quiet = model.animation("quiet", [])
    model.pointer_channel(quiet, "/meshes/0/weights", [0, 1], [(0.0,), (0.5,)])
    model.document["nodes"][a]["weights"] = [0.0]
    model.document["nodes"][b]["weights"] = [0.0]
    document, rest, source = load(script, model, tmp_path)
    glb, _ = script.private_copy(document, rest, source, 0)
    copy, _ = script.split_glb(glb, source)
    placeholder = len(copy["nodes"]) - 1
    assert copy["nodes"][placeholder]["name"] == script.PLACEHOLDER
    emptied = next(a for a in copy["animations"] if a["name"].endswith(".1"))
    assert emptied["channels"] == [
        {
            "sampler": len(emptied["samplers"]) - 1,
            "target": {"node": placeholder, "path": "translation"},
        }
    ]


ROTATION_KEYS = {
    "times": [0.0, 1.0],
    "values": [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)],
    "ins": [(0.0,) * 4, (-1e-21, 0.0, 0.0, 4.0)],
    "outs": [(1e-21, 0.0, 0.0, -4.0), (0.0,) * 4],
    "rotation": True,
}


@pytest.mark.parametrize(
    ("tangent", "want"),
    [
        # w cancels at the middle and x is 2.5e-22, whose square underflows
        # in 32 bits; the quaternion is (1, 0, 0, 0).
        (1e-21, (1.0, 0.0, 0.0, 0.0)),
        # x is 2.5e19, whose square overflows in 32 bits; w is 1.
        (1e20, (1.0, 0.0, 0.0, 4e-20)),
    ],
)
def test_a_cubic_rotation_is_normalized_in_double_precision(script, tangent, want):
    keys = dict(ROTATION_KEYS)
    if tangent == 1e20:
        keys["ins"] = [(0.0,) * 4, (-1e20, 0.0, 0.0, 0.0)]
        keys["outs"] = [(1e20, 0.0, 0.0, 0.0), (0.0,) * 4]
    got = script.cubic_value(keys, 0.5)
    assert math.hypot(*got) == pytest.approx(1.0, abs=1e-15)
    assert got == pytest.approx(want, abs=1e-12)


def test_only_a_rotation_is_normalized_and_not_the_zero_quaternion(script):
    unit = {
        "times": [0.0],
        "values": [(3.0, 0.0, 0.0, 4.0)],
        "ins": [(0.0,) * 4],
        "outs": [(0.0,) * 4],
    }
    assert script.cubic_value(unit, 0.0) == (3.0, 0.0, 0.0, 4.0)
    assert script.cubic_value({**unit, "rotation": True}, 0.0) == (0.6, 0.0, 0.0, 0.8)
    zero = {**unit, "values": [(0.0,) * 4], "rotation": True}
    assert script.cubic_value(zero, 0.0) == (0.0,) * 4
