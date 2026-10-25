"""The capture script's pure encoders, loaded without Blender: the shade
byte the `Standard` transform gives, and the material-ID AOV's codes and
coverage (alpha design, Capture transport and provenance). A refusal here
is the script's error, which fails the command with exit 5."""

import importlib.util
import math
import sys
import types
from array import array
from dataclasses import replace

import pytest

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
