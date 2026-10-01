"""Scale, cell and ground-pixel resolution, following design §Scale and
ground point.

`resolve` turns per-frame measurements into one configuration for the whole
sheet, then checks every frame against it. A fixed configuration is never
adjusted to fit: an overflow is reported, never shrunk away. Everything here
is pure.
"""

import math
import sys
from dataclasses import dataclass
from fractions import Fraction

USAGE_ERROR = 2
OVERFLOW_ERROR = 4
MARGIN = 1
DEFAULT_CELL = (64, 64)
MAX_CELL = 4096
# A subject's height outside this range suggests a unit error (design
# §Input contract).
MIN_HEIGHT = 0.01
MAX_HEIGHT = 100.0
SIDES = ("left", "right", "top", "bottom")


@dataclass(frozen=True)
class Bounds:
    """Extents in meters from the projected ground point, each 0 or more."""

    left: float
    right: float
    up: float
    down: float


@dataclass(frozen=True)
class Measurement:
    """One frame's measured bounds and its height along the vertical axis."""

    bounds: Bounds
    height: float


@dataclass(frozen=True)
class Fit:
    ppm: float
    cell: tuple[int, int]
    ground_px: tuple[int, int]
    warnings: tuple[str, ...]


class UsageError(Exception):
    """A configuration that cannot be resolved: exit classification 2."""

    exit_code = USAGE_ERROR


class CellOverflow(Exception):
    """Frames that fall outside the cell: exit classification 4.

    `frames` holds each overflowing frame's address with its overshoot in
    whole pixels, rounded up, for each side it crosses, in request order.
    """

    exit_code = OVERFLOW_ERROR

    def __init__(self, message, frames):
        super().__init__(message)
        self.frames = frames


def resolve(measurements, ppm=None, cell=None, ground_px=None):
    """Resolve the sheet's configuration from `measurements`.

    `measurements` maps each frame address to its `Measurement`, in request
    order. `ppm`, `cell` (W, H) and `ground_px` (x, y) are the resolved
    options, each None when absent. Raises `UsageError` or `CellOverflow`.
    """
    if not measurements:
        raise ValueError("no frames were measured")
    bounds = [measurement.bounds for measurement in measurements.values()]
    left = max(b.left for b in bounds)
    right = max(b.right for b in bounds)
    up = max(b.up for b in bounds)
    down = max(b.down for b in bounds)
    m = MARGIN

    if ppm is not None and cell is not None:
        width, height = cell
        gx = width // 2
    elif ppm is not None:
        width = 2 * (math.ceil(_pixels(max(left, right), ppm)) + m)
        height = math.ceil(_pixels(up, ppm)) + math.ceil(_pixels(down, ppm)) + 2 * m
        if width > MAX_CELL or height > MAX_CELL:
            raise UsageError(
                f"--ppm {ppm!r} needs a {_int(width)}x{_int(height)} cell, larger than the "
                f"{MAX_CELL}-pixel limit; give a smaller --ppm"
            )
        gx = width // 2
    else:
        width, height = cell if cell is not None else DEFAULT_CELL
        gx = width // 2
        ppm = _auto_ppm(left, right, up, down, width, height, gx)
    gy = height - m - math.ceil(_pixels(down, ppm))
    if ground_px is not None:
        gx, gy = ground_px

    _check_overflow(measurements, ppm, width, height, gx, gy)
    return Fit(ppm, (width, height), (gx, gy), _unit_warnings(measurements))


def _pixels(extent, ppm):
    """`extent · ppm` exactly, so huge but finite values neither overflow nor
    round, and compare exactly with integer pixel coordinates."""
    return Fraction(extent) * Fraction(ppm)


def _auto_ppm(left, right, up, down, width, height, gx):
    """The largest scale fitting the cell with its margin (case 3).

    The limits are exact fractions, so huge extents neither overflow their
    sum nor round; the scale is rounded to a float once, at the end.
    """
    m = MARGIN
    limits = []
    if left > 0:
        limits.append(Fraction(gx - m) / Fraction(left))
    if right > 0:
        limits.append(Fraction(width - gx - m) / Fraction(right))
    if up + down > 0:
        # The extra pixel absorbs rounding the ground row to a whole pixel.
        limits.append(Fraction(height - 2 * m - 1) / (Fraction(up) + Fraction(down)))
    if not limits:
        raise UsageError(
            "every measured extent is 0, so auto-fit has nothing to scale; give --ppm"
        )
    ppm = min(limits)
    if ppm <= 0:
        raise UsageError(
            f"the {width}x{height} cell is too small to auto-fit the subject "
            f"with a {m}-pixel margin; give a larger --cell, or --ppm"
        )
    if ppm > sys.float_info.max:
        raise UsageError(
            "the measured extents are too small for auto-fit to choose a "
            "finite scale; give --ppm"
        )
    return float(ppm)


def _check_overflow(measurements, ppm, width, height, gx, gy):
    """Raise `CellOverflow` for frames whose extents pass a cell edge.

    The margin is not required: an extent exactly on an edge fits.
    """
    overflowing = []
    for address, measurement in measurements.items():
        b = measurement.bounds
        reach = {
            "left": _pixels(b.left, ppm) - gx,
            "right": _pixels(b.right, ppm) - (width - gx),
            "top": _pixels(b.up, ppm) - gy,
            "bottom": _pixels(b.down, ppm) - (height - gy),
        }
        overshoot = {side: math.ceil(reach[side]) for side in SIDES if reach[side] > 0}
        if overshoot:
            overflowing.append((address, overshoot))
    if not overflowing:
        return
    lines = [
        f"the subject overflows the {width}x{height} cell at {ppm!r} pixels per "
        f"meter with ground pixel ({_int(gx)}, {_int(gy)}); a fixed scale, cell "
        "and ground pixel are never shrunk to fit:"
    ]
    for address, overshoot in overflowing:
        sides = ", ".join(
            f"{side} {_int(pixels)} px" for side, pixels in overshoot.items()
        )
        lines.append(
            f"  clip {address.clip!r}, direction {address.direction}, "
            f"time {address.time_s!r} s: {sides}"
        )
    raise CellOverflow("\n".join(lines), tuple(overflowing))


def _int(value):
    """`value` in decimal, or in scientific notation from 10**30 on.

    Pixel coordinates from `--ground-px` can be any whole number, and Python
    refuses to write an integer of more than 4300 digits in decimal. The
    mantissa is truncated, not rounded.
    """
    if abs(value) < 10**30:
        return str(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    exponent = (value.bit_length() - 1) * 30103 // 100000  # about log10
    while 10 ** (exponent + 1) <= value:
        exponent += 1
    while 10**exponent > value:
        exponent -= 1
    digits = str(value // 10 ** (exponent - 5))
    return f"{sign}{digits[0]}.{digits[1:]}e+{exponent}"


def _unit_warnings(measurements):
    tallest = max(measurement.height for measurement in measurements.values())
    if MIN_HEIGHT <= tallest <= MAX_HEIGHT:
        return ()
    return (
        f"the subject is {tallest!r} m tall, outside {MIN_HEIGHT} m to "
        f"{MAX_HEIGHT:g} m; check that the model is in meters",
    )
