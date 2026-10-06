"""Ordered, exact RGB palettes, independent of the rendering pipeline."""

import io
import re
import struct
import zlib
from numbers import Integral
from pathlib import Path

from PIL import Image


class PaletteError(Exception):
    """Bad palette input; the caller decides how to report it."""

    def __init__(self, source, problem):
        self.source = source
        self.problem = problem
        super().__init__(f"{source}: {problem}")


def validate_colors(colors, *, source):
    """Return immutable RGB triples, checking values, uniqueness and 1–255 size.

    `source` labels diagnostics (for example a settings JSON path). This pure
    function reads nothing and refers to entries, never invented file lines.
    """
    return _validate(
        ((color, f"entry {i}") for i, color in enumerate(colors, 1)), source
    )


def _validate(entries, source):
    colors = []
    seen = {}
    for entry, location in entries:
        try:
            color = tuple(entry)
        except TypeError:
            raise PaletteError(source, f"{location}: expected an RGB triple") from None
        if len(color) != 3 or any(
            isinstance(c, bool) or not isinstance(c, Integral) or not 0 <= c <= 255
            for c in color
        ):
            raise PaletteError(source, f"{location}: expected three integers in 0..255")
        color = tuple(int(c) for c in color)
        if color in seen:
            raise PaletteError(
                source,
                f"{location}: duplicate colour {color}, first listed at {seen[color]}",
            )
        seen[color] = location
        colors.append(color)
        if len(colors) > 255:
            raise PaletteError(source, f"{location}: more than 255 colours")
    if not colors:
        raise PaletteError(source, "no colours; expected 1 to 255")
    return tuple(colors)


def read_palette(path):
    """Read `.hex`, `.gpl` or `.png`, raising `PaletteError` for bad input.

    Suffix matching ignores case. Text colours keep file order; PNG colours
    keep first appearance in row order. Reading this file is the only effect.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".hex", ".gpl", ".png"}:
        raise PaletteError(path, "accepted suffixes are .hex, .gpl and .png")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise PaletteError(path, f"cannot be read: {error.strerror or error}") from None
    return read_palette_bytes(data, source=path)


def read_palette_bytes(data, *, source):
    """Parse a palette snapshot, so its colours and digest describe the same bytes."""
    path = Path(source)
    suffix = path.suffix.lower()
    if suffix not in {".hex", ".gpl", ".png"}:
        raise PaletteError(path, "accepted suffixes are .hex, .gpl and .png")
    if suffix == ".png":
        return _png(data, path)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        line = data[: error.start].count(b"\n") + 1
        raise PaletteError(path, f"line {line}: not UTF-8") from None
    return _validate(_text_colors(text, suffix, path), path)


def _text_colors(text, suffix, path):
    lines = text.splitlines()
    if suffix == ".gpl" and (not lines or lines[0] != "GIMP Palette"):
        raise PaletteError(path, "line 1: missing GIMP Palette header")
    started = False
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or (suffix == ".gpl" and (number == 1 or line.startswith("#"))):
            continue
        if suffix == ".hex":
            if not re.fullmatch(r"#?[0-9a-fA-F]{6}", line):
                raise PaletteError(path, f"line {number}: malformed HEX colour")
            value = line.removeprefix("#")
            color = tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
        else:
            if not started and line.startswith("Name:"):
                continue
            if not started and re.fullmatch(r"Columns:\s*[0-9]+", line):
                continue
            tokens = line.split(maxsplit=3)
            if len(tokens) < 3 or any(
                not re.fullmatch(r"[+-]?[0-9]+", token) for token in tokens[:3]
            ):
                raise PaletteError(path, f"line {number}: malformed GPL colour")
            values = [token.lstrip("+-").lstrip("0") or "0" for token in tokens[:3]]
            if any(len(value) > 3 for value in values):
                raise PaletteError(path, f"line {number}: RGB values must be in 0..255")
            color = tuple(
                -int(value) if token.startswith("-") else int(value)
                for token, value in zip(tokens[:3], values, strict=True)
            )
            if any(not 0 <= c <= 255 for c in color):
                raise PaletteError(path, f"line {number}: RGB values must be in 0..255")
        started = True
        yield color, f"line {number}"


def _png(data, path):
    try:
        # Verify checks chunk integrity; load also checks compressed pixel data.
        with Image.open(io.BytesIO(data), formats=["PNG"]) as image:
            image.verify()
        with Image.open(io.BytesIO(data), formats=["PNG"]) as image:
            image.load()
            if data[24] == 16:
                pixels = _png16(data)
            else:
                pixels = image.convert("RGBA").get_flattened_data()
            colors = dict.fromkeys(_opaque_rgb(pixels, path))
    except PaletteError:
        raise
    except (
        IndexError,
        OSError,
        ValueError,
        SyntaxError,
        struct.error,
        zlib.error,
        Image.DecompressionBombError,
    ) as error:
        raise PaletteError(path, f"not a decodable PNG: {error}") from None
    return validate_colors(colors, source=path)


def _opaque_rgb(pixels, path):
    for index, (r, g, b, a) in enumerate(pixels, 1):
        if a != 255:
            raise PaletteError(path, f"pixel {index}: not opaque")
        yield r, g, b


def _png16(data):
    """Decode source samples before Pillow can discard their low bytes.

    PNG filtering is bytewise; each Adam7 pass has independent previous rows.
    See https://www.w3.org/TR/png-3/ sections 8, 9 and 12.4.
    """
    width, height, _, kind, _, _, interlace = struct.unpack(">IIBBBBB", data[16:29])
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[kind]
    compressed = bytearray()
    transparent = None
    offset = 8
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        tag = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + size]
        if tag == b"IDAT":
            compressed.extend(payload)
        elif tag == b"tRNS":
            transparent = struct.unpack(">" + "H" * (len(payload) // 2), payload)
        offset += size + 12
    raw = zlib.decompress(compressed)
    passes = (
        [(0, 0, 1, 1)]
        if interlace == 0
        else [
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        ]
    )
    pixels = [None] * (width * height)
    offset = 0
    stride = channels * 2
    for x0, y0, dx, dy in passes:
        xs = range(x0, width, dx)
        if not xs:
            continue
        length = len(xs) * stride
        previous = bytearray(length)
        for y in range(y0, height, dy):
            filter_type = raw[offset]
            row = bytearray(raw[offset + 1 : offset + 1 + length])
            offset += length + 1
            if len(row) != length or filter_type > 4:
                raise ValueError("invalid 16-bit PNG scanline")
            for i in range(length):
                left = row[i - stride] if i >= stride else 0
                up = previous[i]
                corner = previous[i - stride] if i >= stride else 0
                predictors = (0, left, up, (left + up) // 2, _paeth(left, up, corner))
                row[i] = (row[i] + predictors[filter_type]) & 255
            samples = struct.unpack(">" + "H" * (len(row) // 2), row)
            for j, x in enumerate(xs):
                sample = samples[j * channels : (j + 1) * channels]
                color = sample[:1] if kind in (0, 4) else sample[:3]
                alpha = sample[-1] if kind in (4, 6) else 65535
                if color == transparent:
                    alpha = 0
                if alpha != 65535:
                    # Preserve non-opacity even when converting would round to 255.
                    pixels[y * width + x] = (0, 0, 0, 0)
                else:
                    if any(c % 257 for c in color):
                        raise ValueError(
                            "source colours cannot be represented exactly at 8 bits per channel"
                        )
                    rgb = tuple(c // 257 for c in color)
                    pixels[y * width + x] = (*(rgb * 3 if len(rgb) == 1 else rgb), 255)
            previous = row
    if offset != len(raw):
        raise ValueError("invalid 16-bit PNG pixel data length")
    return pixels


def _paeth(left, up, corner):
    prediction = left + up - corner
    distances = (abs(prediction - left), abs(prediction - up), abs(prediction - corner))
    return (left, up, corner)[distances.index(min(distances))]
