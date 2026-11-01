"""Read an animation sampler's key times from a glTF document, and judge how
closely a cubic spline's keys are spaced.

Implements design §Input contract (the `CUBICSPLINE` key spacing). Pure: the
caller supplies the bytes of each buffer through `fetch(index)`, so nothing
here touches a file.
"""

import math
import struct

# Blender's scene frame rate in the capture, and the spacing, in frames, that
# Blender keeps between two keys (design §Input contract). Blender treats keys
# no further apart than this as one key. The capture script asserts that the
# scene runs at this rate.
BLENDER_FRAME_RATE = 24.0
MIN_KEY_SPACING_FRAMES = 0.01

_FLOAT = 5126
_INDEX_FORMATS = {5121: "B", 5123: "H", 5125: "I"}
_MAX_KEYS = 10_000_000


def float32(value):
    """`value` rounded to 32-bit floating point, as Blender stores a key time."""
    try:
        return struct.unpack("<f", struct.pack("<f", value))[0]
    except OverflowError:
        return math.inf


def spacing_problem(times):
    """Describe the first pair of adjacent keys of a cubic spline that the
    capture cannot evaluate exactly, or return None.

    `times` are the keys' times in seconds. A pair is refused when the times
    do not increase, or when, as Blender stores them (frames at its scene rate
    rounded to 32-bit floats), they are no further apart than the least
    spacing. Returns `(index, text)`: the first key's index and what is wrong.
    """
    frames = [float32(time * BLENDER_FRAME_RATE) for time in times]
    least = float32(MIN_KEY_SPACING_FRAMES)
    for index in range(len(times) - 1):
        first, second = times[index], times[index + 1]
        if not second > first:
            return index, f"keys {index} and {index + 1} do not increase in time"
        gap = frames[index + 1] - frames[index]
        if gap <= least:
            return index, (
                f"keys {index} and {index + 1}, at {first!r} s and {second!r} s, "
                f"are {gap:.6g} Blender frame(s) apart as Blender stores them, "
                f"no more than the {MIN_KEY_SPACING_FRAMES} frame "
                f"({MIN_KEY_SPACING_FRAMES / BLENDER_FRAME_RATE * 1000:.4f} ms) "
                "below which it cannot tell two keys apart"
            )
    return None


def _rows(document, fetch, view_index, offset, row, count, stride=None):
    view = document["bufferViews"][view_index]
    data = fetch(view["buffer"])
    start = view.get("byteOffset", 0) + offset
    stride = stride or row.size
    return [row.unpack_from(data, start + i * stride) for i in range(count)]


def sampler_times(document, fetch, index):
    """The times in seconds held by accessor `index`, or None when it is not a
    readable accessor of finite 32-bit floats (the capture reports that)."""
    try:
        accessor = document["accessors"][index]
        count = accessor["count"]
        if (
            accessor["type"] != "SCALAR"
            or accessor["componentType"] != _FLOAT
            or isinstance(count, bool)
            or not isinstance(count, int)
            or not 0 <= count <= _MAX_KEYS
        ):
            return None
        row = struct.Struct("<f")
        if "bufferView" in accessor:
            view = document["bufferViews"][accessor["bufferView"]]
            rows = _rows(
                document,
                fetch,
                accessor["bufferView"],
                accessor.get("byteOffset", 0),
                row,
                count,
                view.get("byteStride"),
            )
        else:
            rows = [(0.0,)] * count
        sparse = accessor.get("sparse")
        if sparse is not None:
            changed = sparse["count"]
            if (
                isinstance(changed, bool)
                or not isinstance(changed, int)
                or not 0 <= changed <= count
            ):
                return None
            indices, values = sparse["indices"], sparse["values"]
            positions = [
                position
                for (position,) in _rows(
                    document,
                    fetch,
                    indices["bufferView"],
                    indices.get("byteOffset", 0),
                    struct.Struct(f"<{_INDEX_FORMATS[indices['componentType']]}"),
                    changed,
                )
            ]
            replacements = _rows(
                document,
                fetch,
                values["bufferView"],
                values.get("byteOffset", 0),
                row,
                changed,
            )
            if any(not 0 <= position < count for position in positions):
                return None
            rows = list(rows)
            for position, replacement in zip(positions, replacements, strict=True):
                rows[position] = replacement
    except (
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        OSError,
        struct.error,
    ):
        return None
    times = [float(value) for (value,) in rows]
    return times if all(map(math.isfinite, times)) else None
