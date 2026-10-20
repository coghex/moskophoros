"""Camera and direction math, following design §Camera and directions.

All geometry is in glTF coordinates: +X right, +Y up, +Z toward the viewer at
direction 0. The camera is set once and looks along its direction, with a
roll; each direction turns the subject in front of it. Angles are in
degrees. Everything here is pure.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

# Screen-relative labels, recorded only for exact multiples of 45°.
LABELS = MappingProxyType(
    {
        0: "south",
        45: "south-east",
        90: "east",
        135: "north-east",
        180: "north",
        225: "north-west",
        270: "west",
        315: "south-west",
    }
)
# A direction whose length is within this of 1 is already normalised and is
# kept exactly as given, so a recorded direction reloads unchanged (design
# §Reproducibility); any other is divided by its length.
UNIT_TOLERANCE = 1e-12


@dataclass(frozen=True)
class View:
    """A resolved view's directions: preset resolution belongs to
    `moskophoros.cli`."""

    directions: int
    start_angle: float
    model_yaw: float = 0.0


@dataclass(frozen=True)
class CameraBasis:
    """`forward` is the way the camera looks, from it toward the ground
    point; `right` and `up` are the picture's axes."""

    forward: tuple[float, float, float]
    right: tuple[float, float, float]
    up: tuple[float, float, float]


@dataclass(frozen=True)
class Direction:
    """One subject rotation within a view.

    `angle` is θᵢ in [0, 360). `rotation` is θᵢ + model yaw, also reduced to
    [0, 360): the subject's turn about the vertical axis through the ground
    point, counter-clockwise seen from above, measured from the camera's
    reference heading (`heading`).
    """

    index: int
    angle: float
    label: str | None
    rotation: float


def normalise(vector):
    """`vector`, three finite numbers not all 0, as a direction of length 1.

    One already within `UNIT_TOLERANCE` of length 1 is kept exactly, so
    normalising twice changes nothing. Any other is first divided by its
    largest component, so the length it is then divided by is from 1 to √3
    and exact enough even for a tiny vector such as `(1e-300, 1e-300, 0)` or
    a subnormal one such as `(5e-324, 5e-324, 0)`, whose own length would
    round.
    """
    x, y, z = (float(component) for component in vector)
    if not all(map(math.isfinite, (x, y, z))):
        raise ValueError(f"a direction must be finite, got {vector!r}")
    largest = max(abs(x), abs(y), abs(z))
    if largest == 0:
        raise ValueError(f"a direction cannot be all 0, got {vector!r}")
    if abs(math.hypot(x, y, z) - 1) <= UNIT_TOLERANCE:
        return x, y, z
    x, y, z = x / largest, y / largest, z / largest
    length = math.hypot(x, y, z)
    return x / length, y / length, z / length


def is_unit(vector):
    """Whether `vector` is a normalised direction: three finite numbers,
    each from −1 to +1, within `UNIT_TOLERANCE` of length 1."""
    return (
        len(vector) == 3
        and all(
            math.isfinite(component) and -1 <= component <= 1 for component in vector
        )
        and abs(math.hypot(*vector) - 1) <= UNIT_TOLERANCE
    )


def pitch_direction(pitch):
    """The direction `pitch` sets, `(0, −sin p, −cos p)`: from 0, level, to
    90, straight down (projects and camera design D-12)."""
    if not 0 <= pitch <= 90:
        raise ValueError(f"pitch must be from 0 to 90, got {pitch!r}")
    sin, cos = _sin_cos(pitch)
    return 0.0, 0.0 - sin, 0.0 - cos


def camera_basis(direction, roll=0.0):
    """The camera's axes for `direction` and `roll` (design §Camera and
    directions, Basis).

    With `f` the normalised direction, the unrolled right is
    `r₀ = normalise(f × Y)`, or +X when `f` looks straight down or up, and
    the unrolled up `u₀ = r₀ × f`. The roll turns both about `f` by
    `ρ = roll · π`: `r = r₀·cos ρ + u₀·sin ρ` and `u = u₀·cos ρ − r₀·sin ρ`,
    so a positive roll turns the picture clockwise. The products are
    written out so the axes `pitch_direction` gives are exactly today's.
    """
    if not (math.isfinite(roll) and -1 <= roll <= 1):
        raise ValueError(f"roll must be from -1 to 1, got {roll!r}")
    forward = normalise(direction)
    fx, fy, fz = forward
    level = _level(fx, fz)
    # r₀ = (f × Y) / |f × Y|, with f × Y = (−f_z, 0, f_x).
    right = (1.0, 0.0, 0.0) if level == 0 else (0.0 - fz / level, 0.0, fx / level)
    # r₀ × f, for the horizontal r₀: its Y component is |f × Y| itself.
    up = (0.0 - fy * right[2], level, fy * right[0])
    if roll != 0:
        sin, cos = _sin_cos(roll * 180)
        right, up = (
            tuple(r * cos + u * sin for r, u in zip(right, up, strict=True)),
            tuple(u * cos - r * sin for r, u in zip(right, up, strict=True)),
        )
    return CameraBasis(forward, right, up)


def heading(direction):
    """The camera's reference heading: the turn about +Y, in degrees in
    [0, 360), at which a subject facing +Z faces the camera's horizontal
    heading `−(f_x, 0, f_z)`; 0 when it looks straight down or up. Each
    direction's turn is measured from it (D-10, D-18)."""
    fx, _, fz = normalise(direction)
    if fx == 0 and fz == 0:
        return 0.0
    return _wrap(math.degrees(math.atan2(0.0 - fx, 0.0 - fz)))


def subject_basis(direction, roll=0.0):
    """The camera's axes in the subject's frame at θ = 0: the subject turned
    by `heading(direction)` takes the camera's heading with it, so this is
    the camera for the same direction turned to look along −Z.

    The picture comes from these alone. In orthographic, the direction's
    heading changes no picture and no label (design §Camera and
    directions). For a direction `pitch_direction` gives, this is
    `camera_basis` of the same direction, exactly.
    """
    fx, fy, fz = normalise(direction)
    return camera_basis((0.0, fy, 0.0 - _level(fx, fz)), roll)


def _level(x, z):
    """The length of the horizontal part `(x, 0, z)`: exactly `|z|` when `x`
    is 0, as for every direction a pitch sets."""
    return abs(z) if x == 0 else math.hypot(x, z)


# A vertex nearer the camera than this, along the way it looks, cannot be
# projected: it is at, behind or too near the camera to clip (projects and
# camera design D-16).
NEAR_LIMIT = 1e-4


@dataclass(frozen=True)
class Perspective:
    """The perspective camera in the subject's frame at θ = 0, as
    `subject_basis` gives it: `basis` its axes, `position` its position
    from the ground point, and `ground` the ground point's camera space
    `(x_g, y_g, d)`, with `d` its depth along the way the camera looks."""

    basis: CameraBasis
    position: tuple[float, float, float]
    ground: tuple[float, float, float]


def perspective(direction, roll, position):
    """The perspective camera standing at the ground point plus `position`,
    looking along `direction` with `roll` (design §Camera and directions,
    Perspective).

    Each direction's turn is measured from the camera's heading, so in the
    subject's frame at θ = 0 the camera's position is `position` turned by
    the heading's opposite, as `subject_basis` turns its axes. The ground
    point's depth `d = −position · f` is then that of the turned position
    along the turned direction, which the turn keeps; a `d` of 0 or less
    puts the ground point beside or behind the camera.
    """
    fx, _, fz = normalise(direction)
    level = _level(fx, fz)
    px, py, pz = (float(coordinate) for coordinate in position)
    if not all(map(math.isfinite, (px, py, pz))):
        raise ValueError(f"a position must be finite, got {position!r}")
    if level != 0:
        # The turn taking the heading −(f_x, 0, f_z) to +Z.
        sin, cos = fx / level, 0.0 - fz / level
        px, pz = px * cos + pz * sin, pz * cos - px * sin
    basis = subject_basis(direction, roll)
    turned = (px, py, pz)
    ground = tuple(0.0 - _dot(turned, axis) for axis in basis_axes(basis))
    return Perspective(basis, turned, ground)


def basis_axes(basis):
    """The basis's right, up and forward, the order of camera space."""
    return basis.right, basis.up, basis.forward


def project(camera, point, ground, rotation):
    """Where `point`, in subject coordinates, lands from the perspective
    `camera`, with the subject turned by `rotation` degrees about the
    vertical axis through `ground`: `(X, Y, z_c)`, in meters on the ground
    point's plane from the projected ground point, with `z_c` the point's
    depth from the camera (design §Camera and directions, Perspective).

    `X = d·x_c/z_c − x_g` and `Y = d·y_c/z_c − y_g`, so the ground point
    projects to `(0, 0)`. A `z_c` of `NEAR_LIMIT` or less cannot be
    projected, and gives None for X and Y.
    """
    x, y, z = rotate(rotation, tuple(p - g for p, g in zip(point, ground, strict=True)))
    relative = tuple(
        value - origin for value, origin in zip((x, y, z), camera.position, strict=True)
    )
    xc, yc, zc = (_dot(relative, axis) for axis in basis_axes(camera.basis))
    xg, yg, d = camera.ground
    if zc <= NEAR_LIMIT:
        return None, None, zc
    return d * xc / zc - xg, d * yc / zc - yg, zc


def rotate(rotation, vector):
    """`vector` turned by `rotation` degrees about +Y, as `rotation_matrix`
    turns it."""
    return tuple(_dot(row, vector) for row in rotation_matrix(rotation))


def perspective_bounds(camera, points, ground, rotation):
    """One frame's measurement under the perspective `camera`: `L`, `R`, `U`
    and `D` from the projected ground point, as `fit.Bounds` holds them, or
    None when a point is too near the camera to project, and the nearest and
    farthest point depths `(near, far)` (design §Camera and directions,
    Perspective). `points` must not be empty."""
    projected = [project(camera, point, ground, rotation) for point in points]
    depths = [zc for _, _, zc in projected]
    near, far = min(depths), max(depths)
    if near <= NEAR_LIMIT:
        return None, (near, far)
    xs = [x for x, _, _ in projected]
    ys = [y for _, y, _ in projected]
    return (
        (max(0.0, -min(xs)), max(0.0, *xs), max(0.0, *ys), max(0.0, -min(ys))),
        (near, far),
    )


def calibration(ppm, depth, supersample, width):
    """The perspective camera's lens and sensor width in millimeters, with a
    horizontal sensor fit, for `ppm` pixels per meter at the ground point's
    `depth` and a rendered image `width` pixels wide, supersampled by
    `supersample` (design §Capture, Perspective calibration).

    The focal length is `ppm·d·s` image pixels, so `lens / sensor =
    ppm·d·s / W`. The sensor is 36 mm and the lens 36 times that ratio when
    that is at least 1 mm; otherwise the lens is 1 mm and the sensor 1 over
    the ratio. Neither falls below Blender's 1 mm minimum.
    """
    ratio = ppm * depth * supersample / width
    if 36 * ratio >= 1:
        return 36 * ratio, 36.0
    return 1.0, 1 / ratio


def lens_shift(ppm, supersample, ground, size, ground_px):
    """The perspective camera's lens shift `(x, y)`, which puts the ground
    point's projection on its pixel corner `ground_px` of a rendered image of
    `size` `(W, H)` pixels, supersampled by `supersample`, with `ground` the
    ground point's camera space `(x_g, y_g, d)` (design §Capture,
    Perspective calibration).

    Unshifted, the ground point lands `ppm·s·x_g` image pixels right of the
    image's centre and `ppm·s·y_g` above it. Blender's shift moves the view
    in units of the image's width, the sensor-fit side, whatever its
    shape: a positive x moves it right and a positive y up.
    """
    width, height = size
    xg, yg, _ = ground
    gx, gy = (coordinate * supersample for coordinate in ground_px)
    return (
        (width / 2 + ppm * supersample * xg - gx) / width,
        (gy - height / 2 + ppm * supersample * yg) / width,
    )


def _dot(a, b):
    """Written out: `sum` compensates its rounding, and the capture script
    adds the products in this order without it."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def directions(view):
    """The view's directions in index order."""
    count = view.directions
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(f"direction count must be at least 1, got {count!r}")
    # Reduce first: added to a huge start or yaw, the offsets would round away.
    start = _wrap(view.start_angle)
    yaw = _wrap(view.model_yaw)
    result = []
    for index in range(count):
        angle = _wrap(start + index * 360 / count)
        label = LABELS[int(angle)] if angle % 45 == 0 else None
        result.append(Direction(index, angle, label, _wrap(angle + yaw)))
    return tuple(result)


def rotation_matrix(rotation):
    """The 3×3 row-major matrix turning the subject by `rotation` degrees.

    The turn is about +Y and counter-clockwise seen from above, so a subject
    facing +Z faces +X (screen right) at 90° and away from the viewer at 180°.
    """
    sin, cos = _sin_cos(rotation)
    return (
        (cos, 0.0, sin),
        (0.0, 1.0, 0.0),
        (0.0 - sin, 0.0, cos),
    )


def facing(rotation):
    """The direction a subject facing +Z faces after turning by `rotation`."""
    return tuple(row[2] for row in rotation_matrix(rotation))


_QUARTER_TURNS = {0: (0.0, 1.0), 90: (1.0, 0.0), 180: (0.0, -1.0), 270: (-1.0, 0.0)}


def _wrap(degrees):
    """`degrees` reduced to [0, 360). Python's float `%` is exact."""
    if not math.isfinite(degrees):
        raise ValueError(f"angle must be finite, got {degrees!r}")
    turned = degrees % 360
    # A tiny negative remainder rounds up to 360 itself.
    return 0.0 if turned == 360 else turned


def _sin_cos(degrees):
    """Sine and cosine, exact at quarter turns so axes stay exact."""
    turned = _wrap(degrees)
    if turned in _QUARTER_TURNS:
        return _QUARTER_TURNS[turned]
    radians = math.radians(turned)
    return math.sin(radians), math.cos(radians)
