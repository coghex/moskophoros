"""Deterministic threshold tiles, band dithering and two-nearest snap (shading
design contract 3 and *Fixed tile definitions*; D-17, D-27, D-29, D-34).

Two quantisers share one threshold source. Band dithering moves a ramp's band
coordinate before it is floored; snap picks between the two palette colours
nearest a colour. Both read a threshold from a fixed tile, anchored to the
output cell's own pixel column and row, so a cell's pattern never depends on
its frame, direction, the sheet's packing or the order of the calls.

Everything here is pure arrays in and arrays out, with no randomness, file or
dependency beyond NumPy. Nothing is wired to a command yet: which layers are
dithered, which snap target applies and which layer controls a composite are
chosen by the caller and arrive as explicit arguments.
"""

from types import MappingProxyType

import numpy as np

from moskophoros import imageops
from moskophoros.palette import validate_colors
from moskophoros.shading import PATTERNS


def _ordered(side):
    """The ordered (Bayer) tile of `side` ∈ {2, 4, 8}: from `M = [0]`, repeatedly
    `[[4M, 4M + 2], [4M + 3, 4M + 1]]`."""
    tile = np.zeros((1, 1), dtype=np.int64)
    while len(tile) < side:
        tile = np.block([[4 * tile, 4 * tile + 2], [4 * tile + 3, 4 * tile + 1]])
    return tile


_CLUSTERED4 = (
    (12, 5, 6, 13),
    (4, 0, 1, 7),
    (11, 3, 2, 8),
    (15, 10, 9, 14),
)
_SHUFFLED8 = (
    (22, 15, 25, 10, 34, 61, 60, 30),
    (33, 42, 40, 21, 13, 0, 47, 12),
    (17, 4, 46, 38, 50, 6, 2, 29),
    (37, 51, 11, 9, 18, 62, 32, 20),
    (28, 19, 59, 5, 43, 49, 52, 26),
    (1, 58, 39, 44, 41, 45, 48, 8),
    (53, 23, 24, 31, 16, 57, 56, 14),
    (55, 54, 36, 63, 7, 27, 3, 35),
)


def _rows(tile):
    return tuple(tuple(int(rank) for rank in row) for row in tile)


# Each pattern's rank tile, rows top to bottom and columns left to right, as
# nested tuples; `off` has none. Each tile holds every rank once.
TILES = MappingProxyType(
    {
        "ordered2": _rows(_ordered(2)),
        "ordered4": _rows(_ordered(4)),
        "ordered8": _rows(_ordered(8)),
        "clustered4": _CLUSTERED4,
        "diagonal4": tuple(
            tuple(4 * ((x + y) % 4) + y for x in range(4)) for y in range(4)
        ),
        "shuffled8": _SHUFFLED8,
    }
)
_ARRAYS = {name: np.array(rows, dtype=np.int64) for name, rows in TILES.items()}
for _array in _ARRAYS.values():
    _array.setflags(write=False)


def check_pattern(pattern):
    """`pattern`, or `ValueError` unless it is one of `shading.PATTERNS`."""
    if not isinstance(pattern, str) or pattern not in PATTERNS:
        raise ValueError(f"the dither pattern must be one of {PATTERNS}: {pattern!r}")
    return pattern


def check_strength(strength):
    """`strength` as a `float`, or `ValueError` unless it is a finite number
    from 0 to 1 (never a boolean)."""
    wanted = f"the dither strength must be a finite number from 0 to 1: {strength!r}"
    if isinstance(strength, bool) or not isinstance(
        strength, int | float | np.integer | np.floating
    ):
        raise ValueError(wanted)
    try:
        number = float(strength)
    except OverflowError:
        raise ValueError(wanted) from None
    if not 0 <= number <= 1:  # False for NaN
        raise ValueError(wanted)
    return number


def is_effective(pattern, strength):
    """Whether a dither does anything: a pattern other than `off` with a
    strength above 0. Otherwise the undithered path runs, with no artificial
    threshold. Checks both arguments."""
    check_pattern(pattern)
    return pattern != "off" and check_strength(strength) > 0


def _cells(rows, columns):
    """`rows` and `columns`, the output cell's pixel row and column, as
    broadcast non-negative `int64` arrays."""
    arrays = []
    for name, given in (("rows", rows), ("columns", columns)):
        if given is None:
            raise ValueError(f"a dither pattern needs the output cell's {name}")
        values = np.asarray(given)
        if not np.issubdtype(values.dtype, np.integer):
            raise ValueError(f"{name} must be integers, not {values.dtype}")
        if (values < 0).any():
            raise ValueError(f"{name} cannot be negative")
        arrays.append(values.astype(np.int64))
    return np.broadcast_arrays(*arrays)


def thresholds(pattern, rows, columns):
    """The threshold `(rank + ½) / (W · H)` of each output cell pixel, in
    `float64`, for the tile of `pattern` (width `W`, height `H`) at column
    `x mod W` and row `y mod H`. `rows` and `columns` are the pixels' `y` and
    `x` in the output cell, top left the origin; they broadcast to the shape
    returned. They are never supersample or sheet coordinates, and no frame,
    direction or packing offset is added. `off` has no tile and is refused."""
    if check_pattern(pattern) == "off":
        raise ValueError("the off pattern has no thresholds")
    rows, columns = _cells(rows, columns)
    tile = _ARRAYS[pattern]
    height, width = tile.shape
    rank = tile[rows % height, columns % width]
    return (rank + 0.5) / (width * height)


def dithered_band(signal, bands, threshold, strength):
    """The band `clamp(floor(N · e + strength · (½ − threshold)), 0, N − 1)` of
    a signal `e` for `N` bands, as an `int64` array. `signal` and `threshold`
    broadcast. The perturbation is added to the band coordinate before the
    floor; the signal itself is not changed."""
    shifted = bands * np.asarray(signal, dtype=np.float64) + strength * (
        0.5 - np.asarray(threshold, dtype=np.float64)
    )
    return np.clip(np.floor(shifted), 0, bands - 1).astype(np.int64)


def snap_target(palette, ramp=None):
    """The `(T, 3)` `uint8` colours a snap may choose from: the layer's own
    `ramp` (palette indices) in ramp order, or, where there is no ramp, the
    whole `palette` in palette order. Which one applies is the caller's
    choice; a missing ramp changes the target, never where snap runs. A ramp
    may repeat a colour; `snap` deduplicates."""
    colours = np.asarray(validate_colors(palette, source="palette"), dtype=np.uint8)
    if ramp is None:
        return colours
    ramp = np.asarray(ramp)
    if (
        ramp.ndim != 1
        or len(ramp) == 0
        or not np.issubdtype(ramp.dtype, np.integer)
        or not ((0 <= ramp) & (ramp < len(colours))).all()
    ):
        raise ValueError(
            f"a ramp must be non-empty indices into the {len(colours)}-colour "
            f"palette, not {tuple(ramp.tolist())}"
        )
    return colours[ramp]


def _distinct(target):
    """The distinct RGB byte triples of `target`, in the order each first
    occurs, as a `(T, 3)` `uint8` array."""
    colours = np.asarray(target)
    if (
        colours.ndim != 2
        or colours.shape[1] != 3
        or len(colours) == 0
        or not np.issubdtype(colours.dtype, np.integer)
        or ((colours < 0) | (colours > 255)).any()
    ):
        raise ValueError(
            "the snap target must be a non-empty list of RGB triples of "
            "integers from 0 to 255"
        )
    colours = colours.astype(np.uint8)
    _, first = np.unique(colours, axis=0, return_index=True)
    return colours[np.sort(first)]


# The most colours a snap measures against the target at once.
_SNAP_BATCH = 65536


def snap(rgb, target, *, pattern="off", strength=1.0, rows=None, columns=None):
    """Each colour of `rgb` snapped to one colour of `target`, a new `uint8`
    array of `rgb`'s shape. Only the bytes of `target` are returned, never a
    blend.

    `rgb` is `(..., 3)` `uint8`, the colour already rounded to 8-bit sRGB; the
    caller supplies it after brightness (own-ramp snap) or after composition
    (whole-palette snap). `target` is a `(T, 3)` list of RGB triples, such as
    `snap_target`'s, deduplicated here by first occurrence.

    In OKLab (`imageops._oklab`) take the nearest colour `p0` and the second
    nearest `p1` of the distinct target colours, ties going to the earlier in
    target order for both. With `d` the desired colour, the fraction is
    `f = clamp(dot(d − p0, p1 − p0) / dot(p1 − p0, p1 − p0), 0, 1)`, and the
    pixel takes `p1` if and only if `threshold < strength · f`; equality keeps
    `p0`. This is the projection onto the segment of the two nearest, not the
    best partner of `p0` anywhere in the target, and not an RGB projection.
    With `pattern` `off` or `strength` 0, or a one-colour target, the pixel
    takes `p0` with no threshold. The thresholds are `thresholds(pattern,
    rows, columns)` for the pixels' output cell `rows` and `columns`, which
    must broadcast to `rgb`'s leading shape.

    Work is done in fixed batches of pixels against one target colour at a
    time, never pixels × colours at once. Nothing is changed in place."""
    rgb = np.asarray(rgb)
    if rgb.dtype != np.uint8 or rgb.ndim < 1 or rgb.shape[-1] != 3:
        raise ValueError("rgb must be a uint8 array with three channels last")
    colours = _distinct(target)
    shape = rgb.shape[:-1]
    result = np.empty(rgb.shape, dtype=np.uint8)
    flat_in, flat_out = rgb.reshape(-1, 3), result.reshape(-1, 3)

    effective = is_effective(pattern, strength)
    mixed = effective and len(colours) > 1
    if mixed:
        strength = check_strength(strength)
        threshold = thresholds(pattern, rows, columns)
        try:
            threshold = np.broadcast_to(threshold, shape).reshape(-1)
        except ValueError:
            raise ValueError(
                f"rows and columns must broadcast to {shape}, not {threshold.shape}"
            ) from None
    labs = imageops._oklab(colours)
    for start in range(0, len(flat_in), _SNAP_BATCH):
        part = slice(start, start + _SNAP_BATCH)
        lab = imageops._oklab(flat_in[part])
        nearest, second = _two_nearest(lab, labs)
        chosen = nearest
        if mixed:
            p0, p1 = labs[nearest], labs[second]
            line = p1 - p0
            length = np.sum(line * line, axis=1)
            along = np.sum((lab - p0) * line, axis=1)
            fraction = np.clip(along / np.where(length == 0, 1.0, length), 0.0, 1.0)
            chosen = np.where(threshold[part] < strength * fraction, second, nearest)
        flat_out[part] = colours[chosen]
    return result


def _two_nearest(lab, labs):
    """The index of each colour's nearest and second-nearest target colour by
    squared OKLab distance, strict comparison in target order so that ties go
    to the earlier. A one-colour target repeats its only colour."""
    count = len(lab)
    best = np.full(count, np.inf)
    runner = np.full(count, np.inf)
    first = np.zeros(count, dtype=np.int64)
    second = np.zeros(count, dtype=np.int64)
    for index, colour in enumerate(labs):
        difference = lab - colour
        distance = np.sum(difference * difference, axis=1)
        closer = distance < best
        next_closer = ~closer & (distance < runner)
        runner = np.where(closer, best, np.where(next_closer, distance, runner))
        second = np.where(closer, first, np.where(next_closer, index, second))
        best = np.where(closer, distance, best)
        first = np.where(closer, index, first)
    return first, second
