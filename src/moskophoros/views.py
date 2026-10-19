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
