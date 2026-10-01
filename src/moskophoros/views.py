"""Camera and direction math, following design §Camera and directions.

All geometry is in glTF coordinates: +X right, +Y up, +Z toward the viewer at
direction 0. The camera never moves; the subject turns. Angles are in
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


@dataclass(frozen=True)
class View:
    """A resolved view: preset resolution belongs to `moskophoros.cli`."""

    pitch: float
    directions: int
    start_angle: float
    model_yaw: float = 0.0


@dataclass(frozen=True)
class CameraBasis:
    """`direction` points from the ground point toward the camera."""

    direction: tuple[float, float, float]
    right: tuple[float, float, float]
    up: tuple[float, float, float]


@dataclass(frozen=True)
class Direction:
    """One subject rotation within a view.

    `angle` is θᵢ in [0, 360). `rotation` is θᵢ + model yaw, also reduced to
    [0, 360): the subject's turn about the vertical axis through the ground
    point, counter-clockwise seen from above.
    """

    index: int
    angle: float
    label: str | None
    rotation: float


def camera_basis(pitch):
    """The camera basis for `pitch`, from 0 (horizontal) to 90 (top-down)."""
    if not 0 <= pitch <= 90:
        raise ValueError(f"pitch must be from 0 to 90, got {pitch!r}")
    sin, cos = _sin_cos(pitch)
    return CameraBasis(
        direction=(0.0, sin, cos),
        right=(1.0, 0.0, 0.0),
        up=(0.0, cos, 0.0 - sin),
    )


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
