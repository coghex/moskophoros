"""The perspective camera on generated models, in real Blender (projects and
camera design D-3, D-10, D-12, D-13, D-16; design §Camera and directions,
Perspective; §Capture, Perspective calibration and clipping).

Expected pixels are worked out here from the fixtures' known geometry,
projected in the world frame, independently of the script: the camera
stands at the ground point plus its position with `moskophoros.views`'
camera axes, the subject turns by the camera's heading plus its direction's
turn about the vertical through the ground point, and a point lands at
`(gx + ppm·X, gy − ppm·Y)` with `X = d·x_c/z_c − x_g` and
`Y = d·y_c/z_c − y_g`. A convex solid covers the pixels whose centres lie
inside the convex hull of its projected corners, since one camera sample at
each pixel centre decides coverage.
"""

import hashlib
import json

import numpy as np
import pytest
from glb_writer import GlbWriter
from PIL import Image
from shading import DEFAULT_SHADE
from test_render import cube

from moskophoros import cli, gltf, imageops, plan, views
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

RED = (1.0, 0.0, 0.0, 1.0)
GREEN = (0.0, 1.0, 0.0, 1.0)
GREY = (0.6, 0.6, 0.6, 1.0)
# A pixel centre this near a predicted edge, in supersampled pixels, could
# fall either side of it in single precision.
EDGE_PX = 1e-3


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def off_axis(direction, depth, across, up, roll=0.0):
    """A camera position `depth` meters back along `direction` from the
    ground point, moved `across` and `up` along its own rolled right and up,
    so the ground point lies off its axis."""
    basis = views.camera_basis(direction, roll)
    return tuple(
        float(-depth * f + across * r + up * u)
        for f, r, u in zip(basis.forward, basis.right, basis.up, strict=True)
    )


def world_camera(settings, rotation):
    """The camera in the world frame, with the subject turned by `rotation`
    from the camera's heading: a function from subject points to
    `(X, Y, z_c)`, and the camera's position, axes and ground depth."""
    basis = views.camera_basis(settings.direction, settings.roll)
    r, u, f = (np.array(axis) for axis in (basis.right, basis.up, basis.forward))
    position = np.array(settings.position)
    ground = np.array(settings.ground)
    turn = np.array(views.rotation_matrix(views.heading(settings.direction) + rotation))
    xg, yg, d = (-position @ axis for axis in (r, u, f))

    def project(points):
        q = (np.asarray(points, dtype=np.float64) - ground) @ turn.T - position
        xc, yc, zc = q @ r, q @ u, q @ f
        return d * xc / zc - xg, d * yc / zc - yg, zc

    return project, (position, r, u, f, d, turn)


def image_points(settings, rotation, points):
    """Where `points` land in the supersampled image, `(u, v)` from its top
    left corner, and their depths."""
    project, _ = world_camera(settings, rotation)
    x, y, zc = project(points)
    s, ppm = settings.supersample, settings.ppm
    gx, gy = settings.ground_px
    return np.stack((s * (gx + ppm * x), s * (gy - ppm * y)), axis=-1), zc


def hull(points):
    """The convex hull of 2D `points`, counter-clockwise (y down)."""
    points = sorted(map(tuple, points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


def coverage(polygon, size):
    """Pixels whose centres are inside the convex `polygon`, and those whose
    centres are within `EDGE_PX` of an edge."""
    width, height = size
    cx, cy = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)
    inside = np.ones((height, width), dtype=bool)
    loose = np.ones((height, width), dtype=bool)
    near = np.zeros((height, width), dtype=bool)
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0), strict=True):
        edge = b - a
        distance = (edge[0] * (cy - a[1]) - edge[1] * (cx - a[0])) / np.hypot(*edge)
        inside &= distance > 0
        loose &= distance > -EDGE_PX
        near |= np.abs(distance) < EDGE_PX
    return inside, near & loose


def corners(center, half):
    x, y, z = center
    return [
        (x + dx * half, y + dy * half, z + dz * half)
        for dx in (-1, 1)
        for dy in (-1, 1)
        for dz in (-1, 1)
    ]


def as_stored(points):
    """The points as glTF stores them, in single precision."""
    return np.asarray(points, dtype=np.float32).astype(np.float64)


def settings_for(
    direction,
    roll,
    position,
    *,
    ppm=40.0,
    cell=(32, 32),
    ground=(0.0, 0.0, 0.0),
    ground_px=(16, 16),
    supersample=1,
    directions=1,
    start=0.0,
    yaw=0.0,
):
    return backend.Settings(
        "custom",
        views.normalise(direction),
        directions,
        start,
        yaw,
        4.0,
        supersample,
        ppm,
        cell,
        ground,
        ground_px,
        "error",
        DEFAULT_SHADE,
        roll=roll,
        position=position,
        projection="perspective",
    )


def capture(found, path, tmp_path, settings, workspace="work"):
    """Measure, clip from the measured depths, and render `path` with the
    fixed `settings`, through the launcher; return (measured, rendered,
    render job)."""
    subject = gltf.read_glb(path)
    clips = gltf.select_clips(subject, (), ())
    frames = plan.plan(
        subject.name,
        clips,
        views.View(settings.directions, settings.start_angle, settings.model_yaw),
        settings.fps,
    )
    root = tmp_path / workspace
    root.mkdir()
    source = backend.Source(
        path.resolve(),
        hashlib.sha256(path.read_bytes()).hexdigest(),
        subject.scene_index,
    )
    unfitted = backend.Settings(
        **{**settings.__dict__, "ppm": None, "cell": None, "ground_px": None}
    )
    measure = backend.build_job(
        "measure", source, subject.name, unfitted, clips, frames, str(root / "measure")
    )
    measured = blender.run_phase(found, root, measure)
    clip = backend.clipping(measured.depths.values())
    job = backend.build_job(
        "render",
        source,
        subject.name,
        settings,
        clips,
        frames,
        str(root / "render"),
        clip,
    )
    return measured, blender.run_phase(found, root, job), job


def alpha(paths):
    with Image.open(paths["color"]) as image:
        return np.asarray(image.convert("RGBA"))[..., 3]


def cubes_model(tmp_path, solids, stem="cubes"):
    """A cube node per `(center, half, colour)` in `solids`."""
    model = GlbWriter()
    nodes = []
    for k, (center, half, colour) in enumerate(solids):
        mesh = model.mesh(cube(center, half), material=model.material(colour))
        nodes.append(model.node(f"cube{k}", mesh=mesh))
    model.scene(nodes, default=True)
    return model.write(tmp_path, stem)


def check_framing(rendered, settings, solids, angles):
    """Every rendered frame covers exactly the pixels predicted for
    `solids`, `(center, half, colour)`, at each of `angles`."""
    s = settings.supersample
    size = (settings.cell[0] * s, settings.cell[1] * s)
    for (address, paths), angle in zip(rendered.buffers.items(), angles, strict=True):
        covered = alpha(paths) > 0
        assert covered.shape == (size[1], size[0])
        predicted = np.zeros_like(covered)
        uncertain = np.zeros_like(covered)
        for center, half, _ in solids:
            points, depths = image_points(
                settings,
                (angle + settings.model_yaw) % 360,
                as_stored(corners(center, half)),
            )
            assert (depths > 0).all()
            inside, near = coverage(hull(points), size)
            predicted |= inside
            uncertain |= near
        # A pixel centre on an edge may fall either side; there are few.
        assert uncertain.sum() <= 2, address
        assert predicted.any(), address
        wrong = np.argwhere((covered != predicted) & ~uncertain)
        assert wrong.size == 0, (address, [tuple(p[::-1]) for p in wrong[:10]])


# Framing (spikes 1 and 2): each shape of image, and supersampling


CUBE = [((0.0, 0.25, 0.0), 0.25, RED)]
ISO = views.pitch_direction(30.0)


@pytest.mark.parametrize(
    ("cell", "supersample", "ppm", "ground_px", "depth"),
    [
        ((32, 32), 1, 40.0, (14, 24), 2.5),
        ((24, 40), 1, 40.0, (11, 30), 2.5),
        ((40, 24), 1, 30.0, (22, 19), 2.5),
        ((20, 16), 4, 22.0, (9, 12), 2.5),
        # A field of view so wide that the lens would fall under 1 mm:
        # ppm·d·s / W is 1·1.25·8 / 384, under 1/36, so the sensor widens.
        ((48, 32), 8, 1.0, (21, 23), 1.25),
    ],
    ids=["square", "portrait", "landscape", "supersampled", "widened sensor"],
)
def test_a_cube_covers_exactly_the_predicted_pixels(
    found, tmp_path, cell, supersample, ppm, ground_px, depth
):
    position = off_axis(ISO, depth, 0.35, -0.2)
    settings = settings_for(
        ISO,
        0.0,
        position,
        ppm=ppm,
        cell=cell,
        ground_px=ground_px,
        supersample=supersample,
    )
    lens, sensor = views.calibration(ppm, depth, supersample, cell[0] * supersample)
    assert (sensor > 36) == (ppm == 1.0)
    path = cubes_model(tmp_path, [(c, h, colour) for c, h, colour in CUBE])
    _, rendered, job = capture(found, path, tmp_path, settings)
    assert job["settings"]["camera"]["projection"] == "perspective"
    check_framing(rendered, settings, CUBE, [0.0])


GENERAL = views.normalise((0.45, -0.6, -0.65))
GROUND = (0.3, 0.2, -0.1)
FEATURE = (GROUND[0] + 0.4, GROUND[1] + 0.25, GROUND[2] - 0.3)


def test_a_rolled_off_axis_camera_frames_a_rectangular_cell(found, tmp_path):
    # A general direction with a roll that is no quarter turn, the ground
    # point off the camera's axis and off the cell's centre, three
    # directions and a model yaw.
    roll = 0.37
    settings = settings_for(
        GENERAL,
        roll,
        off_axis(GENERAL, 2.75, -0.4, 0.3, roll),
        ppm=24.0,
        cell=(36, 28),
        ground=GROUND,
        ground_px=(13, 17),
        supersample=2,
        directions=3,
        start=10.0,
        yaw=25.0,
    )
    perspective = views.perspective(settings.direction, roll, settings.position)
    assert abs(perspective.ground[0]) > 0.1 and abs(perspective.ground[1]) > 0.1
    solids = [(GROUND, 0.08, RED), (FEATURE, 0.12, GREEN)]
    path = cubes_model(tmp_path, solids)
    measured, rendered, _ = capture(found, path, tmp_path, settings)
    check_framing(rendered, settings, solids, [10.0, 130.0, 250.0])
    # The ground point lands on its pixel corner: the red cube about it is
    # centred there.
    for paths in rendered.buffers.values():
        with Image.open(paths["color"]) as image:
            rgba = np.asarray(image.convert("RGBA")).astype(np.int64)
        red = (rgba[..., 3] > 0) & (rgba[..., 0] > rgba[..., 1])
        rows, columns = np.nonzero(red)
        assert (columns.mean() + 0.5, rows.mean() + 0.5) == pytest.approx(
            (13 * 2, 17 * 2), abs=0.6
        )
    # Measure and render use the same rolled axes: the measured bounds are
    # those projected here, over every vertex.
    for (address, measurement), angle in zip(
        measured.measurements.items(), [10.0, 130.0, 250.0], strict=True
    ):
        project, _ = world_camera(settings, (angle + 25.0) % 360)
        points = np.concatenate(
            [as_stored(corners(center, half)) for center, half, _ in solids]
        )
        x, y, zc = project(points)
        expected = (
            max(0.0, -x.min()),
            max(0.0, x.max()),
            max(0.0, y.max()),
            max(0.0, -y.min()),
        )
        bounds = measurement.bounds
        assert (bounds.left, bounds.right, bounds.up, bounds.down) == pytest.approx(
            expected, rel=1e-9, abs=1e-12
        ), address
        assert measured.depths[address] == pytest.approx((zc.min(), zc.max()), rel=1e-9)


# Clipping across frames


def test_the_clipping_planes_enclose_every_measured_frame(found, tmp_path):
    # A cube far off the vertical axis comes nearer and goes farther as
    # the subject turns.
    model = GlbWriter()
    away = model.node(
        "away",
        mesh=model.mesh(cube((0.6, 0.2, 0.0), 0.2), material=model.material(RED)),
    )
    model.scene([away], default=True)
    path = model.write(tmp_path, "turning")
    settings = settings_for(
        ISO, 0.0, off_axis(ISO, 3.0, 0.0, 0.0), ppm=20.0, cell=(40, 40), directions=4
    )
    measured, rendered, job = capture(found, path, tmp_path, settings)
    depths = list(measured.depths.values())
    assert len(depths) == 4 and len({near for near, _ in depths}) >= 3
    nearest = min(near for near, _ in depths)
    farthest = max(far for _, far in depths)
    assert job["clipping"] == {
        "near_m": nearest / 2,
        "far_m": 2 * farthest + 1,
        "depth_m": [nearest, farthest],
    }
    assert len(rendered.buffers) == 4

    # A point-like triangle: its nearest and farthest depths are one.
    dot = (0.0, 0.5, 0.0)
    model = GlbWriter()
    point = model.node(
        "point", mesh=model.mesh([dot, dot, dot], material=model.material(GREEN))
    )
    model.scene([point], default=True)
    path = model.write(tmp_path, "point")
    settings = settings_for(ISO, 0.0, off_axis(ISO, 3.0, 0.0, 0.0), directions=1)
    measured, _, job = capture(found, path, tmp_path, settings, workspace="point")
    ((near, far),) = measured.depths.values()
    assert near == far
    assert job["clipping"]["depth_m"] == [near, far]


# The normal and depth buffers (D-13)


def test_a_plane_reads_its_camera_space_normal_and_axial_depth(found, tmp_path):
    """A tilted plane under a rolled, off-axis camera: each pixel's normal is
    the plane's in camera space, and its depth is d − z_c along the viewing
    axis, not the distance along the ray; reduced, it is that times the
    pixels per meter, with no supersample factor."""
    normal = np.array((0.3, 0.5, 0.81))
    normal /= np.linalg.norm(normal)
    center = np.array((0.05, 0.1, -0.05))
    helper = np.cross((1.0, 0.0, 0.0), normal)
    helper /= np.linalg.norm(helper)
    other = np.cross(normal, helper)
    half = 0.9
    quad = [
        tuple(center + half * (a * helper + b * other))
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, -1), (1, 1), (-1, 1))
    ]
    model = GlbWriter()
    node = model.node("plane", mesh=model.mesh(quad, material=model.material(GREY)))
    model.scene([node], default=True)
    path = model.write(tmp_path, "plane")
    roll, rotation = 0.37, 40.0
    settings = settings_for(
        GENERAL,
        roll,
        off_axis(GENERAL, 2.0, 0.3, -0.25, roll),
        ppm=30.0,
        cell=(40, 32),
        ground_px=(17, 15),
        supersample=2,
        start=rotation,
    )
    _, rendered, _ = capture(found, path, tmp_path, settings)
    (paths,) = rendered.buffers.values()
    normals, depths = backend.decode_normal_depth(paths)
    covered = ~np.isnan(depths)
    assert covered.mean() > 0.3

    _, (position, r, u, f, d, turn) = world_camera(settings, rotation)
    ground = np.array(settings.ground)
    n = turn @ normal
    point = ground + turn @ (center - ground)
    s, ppm = settings.supersample, settings.ppm
    gx, gy = settings.ground_px
    height, width = depths.shape
    columns, rows = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)
    # The ray through each pixel centre, from the camera at ground + position.
    a = ((columns / s - gx) / ppm - position @ r) / d
    b = ((gy - rows / s) / ppm - position @ u) / d
    ray = a[..., None] * r + b[..., None] * u + f
    camera = ground + position
    zc = ((point - camera) @ n) / (ray @ n)
    expected = d - zc
    assert np.abs(depths[covered] - expected[covered]).max() < 2e-5
    # The distance along the ray differs, by much more than the tolerance.
    along_ray = d - zc * np.linalg.norm(ray, axis=-1)
    assert np.abs(along_ray - expected)[covered].max() > 0.01
    camera_space = np.array((n @ r, n @ u, -(n @ f)))
    assert np.abs(normals[covered] - camera_space).max() < 1e-3

    # Reduced to sheet pixels at the ground point's scale.
    with Image.open(paths["color"]) as image:
        reduced_alpha = np.asarray(image.convert("RGBA"))[..., 3]
    whole = reduced_alpha.reshape(height // s, s, width // s, s).min(axis=(1, 3)) > 0
    _, sheet = imageops.reduce_normal_depth(normals, depths, whole, s, settings.ppm)
    blocks = expected.reshape(height // s, s, width // s, s).mean(axis=(1, 3))
    assert np.abs(sheet[whole] - blocks[whole] * ppm).max() <= 1 / 32 + 1e-3


# Readback: Blender's stored camera is refused unless it is the one asked for


def single_frame_job(tmp_path, settings, clip):
    path = cubes_model(tmp_path, CUBE)
    subject = gltf.read_glb(path)
    clips = gltf.select_clips(subject, (), ())
    frames = plan.plan(subject.name, clips, views.View(1, 0.0, 0.0), 4.0)
    root = tmp_path / "work"
    root.mkdir()
    source = backend.Source(
        path.resolve(),
        hashlib.sha256(path.read_bytes()).hexdigest(),
        subject.scene_index,
    )
    job = backend.build_job(
        "render",
        source,
        subject.name,
        settings,
        clips,
        frames,
        str(root / "render"),
        clip,
    )
    return root, job


@pytest.mark.parametrize(
    ("change", "clip", "message"),
    [
        # A scale too large for Blender's single-precision lens.
        ({"ppm": 1e300}, (1.0, 7.0, (2.0, 3.0)), "lens as"),
        # A ground pixel too far for its single-precision shift.
        ({"ground_px": (10**42, 16)}, (1.0, 7.0, (2.0, 3.0)), "horizontal shift"),
        # A near plane under Blender's least, which it raises past the
        # nearest depth.
        ({}, (5e-8, 7.0, (1e-7, 3.0)), "clipping planes"),
    ],
    ids=["lens", "shift", "near plane"],
)
def test_a_stored_camera_other_than_asked_is_refused(
    found, tmp_path, change, clip, message
):
    settings = settings_for(ISO, 0.0, off_axis(ISO, 2.5, 0.0, 0.0))
    settings = backend.Settings(**{**settings.__dict__, **change})
    root, job = single_frame_job(tmp_path, settings, backend.Clipping(*clip))
    with pytest.raises(backend.BackendError, match=message) as raised:
        blender.run_phase(found, root, job)
    assert raised.value.exit_code == 5


# The whole command


def run(capsys, argv):
    status = cli.run(argv)
    out, err = capsys.readouterr()
    return status, out, err


def bobbing_model(tmp_path):
    """A cube that rises and grows over `bob`, off the vertical axis."""
    model = GlbWriter()
    node = model.node(
        "box",
        mesh=model.mesh(cube((0.15, 0.25, 0.05), 0.25), material=model.material(RED)),
    )
    model.scene([node], default=True)
    model.animation(
        "bob",
        [
            (node, "translation", [0.0, 0.5, 1.0], [(0, 0, 0), (0, 0.3, 0), (0, 0, 0)]),
            (
                node,
                "scale",
                [0.0, 0.5, 1.0],
                [(1, 1, 1), (1.3, 0.8, 1.3), (1, 1, 1)],
            ),
        ],
    )
    return model.write(tmp_path, "bob")


PERSPECTIVE = [
    *["--projection", "perspective", "--camera-direction", "0.45,-0.6,-0.65"],
    *["--camera-roll", "0.2", "--camera-position", "-1.6,2.2,2.4"],
]


def test_a_fitted_perspective_sheet_keeps_the_margin(found, tmp_path, capsys):
    path = bobbing_model(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    status, _, err = run(
        capsys,
        [
            *PERSPECTIVE,
            *["--no-user-config", "--directions", "4", "--fps", "6"],
            *["--supersample", "2", "--cell", "40x48", "--ground", "0,0.1,0"],
            *["--blender", str(found.path), str(path), str(out / "bob.png")],
        ],
    )
    assert (status, err) == (0, "")
    sheet = json.loads((out / "bob.json").read_text())
    assert sheet["settings"]["camera"] == {
        "projection": "perspective",
        "direction": list(views.normalise((0.45, -0.6, -0.65))),
        "roll": 0.2,
        "position": [-1.6, 2.2, 2.4],
    }
    width, height = 40, 48
    with Image.open(out / "bob.png") as image:
        covered = np.asarray(image.convert("RGBA"))[..., 3] > 0
    rows, columns = covered.shape[0] // height, covered.shape[1] // width
    assert rows * columns >= 4 * 6
    nearest = []
    for row in range(rows):
        for column in range(columns):
            cell = covered[
                row * height : (row + 1) * height, column * width : (column + 1) * width
            ]
            if not cell.any():
                continue
            # The 1-pixel margin is empty on every side.
            assert not (cell[0].any() or cell[-1].any()), (row, column)
            assert not (cell[:, 0].any() or cell[:, -1].any()), (row, column)
            ys, xs = np.nonzero(cell)
            nearest.append(
                min(
                    xs.min() - 1,
                    width - 2 - xs.max(),
                    ys.min() - 1,
                    height - 2 - ys.max(),
                )
            )
    # Fitted, not shrunk: some frame reaches the margin.
    assert min(nearest) == 0


def test_a_vertex_too_near_the_camera_exits_4_with_nothing_published(
    found, tmp_path, capsys
):
    # A long box through the camera's position: one end is behind it.
    model = GlbWriter()
    node = model.node(
        "pole",
        mesh=model.mesh(
            [
                p
                for p in cube((0.0, 0.5, 1.0), 0.1)
                for p in [(p[0], p[1], 1.0 + (p[2] - 1.0) * 25)]
            ],
            material=model.material(RED),
        ),
    )
    model.scene([node], default=True)
    path = model.write(tmp_path, "pole")
    out = tmp_path / "out"
    out.mkdir()
    earlier = {"pole.png": b"earlier sheet", "pole.json": b"earlier json"}
    for name, data in earlier.items():
        (out / name).write_bytes(data)
    status, _, err = run(
        capsys,
        [
            *["--projection", "perspective", "--camera-direction", "0,0,-1"],
            *["--camera-position", "0,0.5,2", "--directions", "1", "--no-user-config"],
            *["--blender", str(found.path), str(path), str(out / "pole.png")],
        ],
    )
    assert status == 4
    lines = err.splitlines()
    assert lines[0] == (
        f"moskophoros: error: {path}: a vertex is too near the perspective camera "
        "to project, 0.0001 m from it or nearer, or behind it; move the camera's "
        "position farther from the subject:"
    )
    assert lines[1].startswith(
        "  clip 'static', direction 0, time 0.0 s: nearest vertex depth -"
    )
    assert {p.name: p.read_bytes() for p in out.iterdir()} == earlier
