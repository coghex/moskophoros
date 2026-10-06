"""All inputs are generated here; no owner palette files are used."""

import struct
import zlib

import pytest
from PIL import Image
from test_capture_backend import raw_png

from moskophoros.palette import PaletteError, read_palette, validate_colors

COLORS = ((1, 2, 3), (170, 187, 204), (255, 0, 128))


def text_file(tmp_path, suffix, text):
    path = tmp_path / f"colors{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


def png_file(tmp_path, mode, pixels, *, size=None, suffix=".png", **save_options):
    path = tmp_path / f"art{suffix}"
    image = Image.new(mode, size or (len(pixels), 1))
    image.putdata(pixels)
    image.save(path, format="PNG", **save_options)
    return path


@pytest.mark.parametrize("suffix", [".hex", ".HeX"])
def test_hex_forms_and_order(tmp_path, suffix):
    path = text_file(tmp_path, suffix, "\n  010203 \n#AaBbCc\n\tFf0080\t\n\n")
    assert read_palette(path) == COLORS


@pytest.mark.parametrize("suffix", [".gpl", ".GpL"])
def test_gpl_metadata_comments_names_order(tmp_path, suffix):
    path = text_file(
        tmp_path,
        suffix,
        "GIMP Palette\nName: Test é\nColumns: 3\n# comment\n\n"
        "1 2 3 First colour\n170\t187\t204\n255 0 128 pink\n",
    )
    assert read_palette(path) == COLORS


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
@pytest.mark.parametrize("suffix", [".png", ".PnG"])
def test_png_first_appearance_order(tmp_path, mode, suffix):
    colors = [COLORS[i] for i in (2, 0, 2, 1, 0, 1)]
    pixels = [(*c, 255) for c in colors] if mode == "RGBA" else colors
    path = png_file(tmp_path, mode, pixels, size=(3, 2), suffix=suffix)
    assert read_palette(path) == (COLORS[2], COLORS[0], COLORS[1])


def test_indexed_pixels_not_table_order_or_unused_entries(tmp_path):
    path = tmp_path / "indexed.png"
    image = Image.new("P", (4, 1))
    image.putpalette([channel for c in COLORS for channel in c])
    image.putdata([2, 0, 2, 0])
    image.save(path)
    assert read_palette(path) == (COLORS[2], COLORS[0])
    # An unused transparent table entry is not a transparent pixel.
    image.save(path, transparency=1)
    assert read_palette(path) == (COLORS[2], COLORS[0])
    image.save(path, transparency=2)
    assert_problem(path, "not opaque")


@pytest.mark.parametrize(
    ("mode", "pixels", "expected"),
    [
        ("L", [128, 0, 128, 255], ((128, 128, 128), (0, 0, 0), (255, 255, 255))),
        ("1", [255, 0, 255], ((255, 255, 255), (0, 0, 0))),
        ("LA", [(17, 255), (12, 255)], ((17, 17, 17), (12, 12, 12))),
    ],
)
def test_greyscale_expansion(tmp_path, mode, pixels, expected):
    assert read_palette(png_file(tmp_path, mode, pixels)) == expected


@pytest.mark.parametrize(
    ("mode", "pixels", "options"),
    [
        ("RGBA", [(1, 2, 3, 255), (4, 5, 6, 254)], {}),
        ("LA", [(5, 254)], {}),
        ("L", [5], {"transparency": 5}),
        ("RGB", [(1, 2, 3)], {"transparency": (1, 2, 3)}),
    ],
)
def test_nonopaque_pixels(tmp_path, mode, pixels, options):
    assert_problem(png_file(tmp_path, mode, pixels, **options), "not opaque")


def test_package_of_128_colors_reads_identically(tmp_path):
    colors = tuple((i, 255 - i, (i * 37) % 256) for i in range(128))
    hex_path = text_file(
        tmp_path, ".hex", "\n".join("".join(f"{v:02x}" for v in c) for c in colors)
    )
    gpl_path = text_file(
        tmp_path,
        ".gpl",
        "GIMP Palette\n" + "\n".join(" ".join(str(v) for v in c) for c in colors),
    )
    square = png_file(tmp_path, "RGB", colors, size=(16, 8))
    strip = png_file(tmp_path, "RGB", colors, size=(128, 1), suffix=".PNG")
    for path in (hex_path, gpl_path, square, strip):
        assert read_palette(path) == colors


@pytest.mark.parametrize("count", [1, 255])
@pytest.mark.parametrize("suffix", [".hex", ".gpl", ".png"])
def test_limits_accepted(tmp_path, count, suffix):
    colors = tuple((i, 0, 0) for i in range(count))
    if suffix == ".png":
        path = png_file(tmp_path, "RGB", colors)
    else:
        text = (
            "\n".join("".join(f"{v:02x}" for v in c) for c in colors)
            if suffix == ".hex"
            else "GIMP Palette\n"
            + "\n".join(" ".join(str(v) for v in c) for c in colors)
        )
        path = text_file(tmp_path, suffix, text)
    assert read_palette(path) == colors


def assert_problem(path, *parts):
    with pytest.raises(PaletteError) as caught:
        read_palette(path)
    assert str(path) in str(caught.value)
    for part in parts:
        assert part in str(caught.value)


@pytest.mark.parametrize(
    ("suffix", "text", "parts"),
    [
        (".hex", "12345\n", ("line 1", "malformed")),
        (".hex", "\n#123456 trailing\n", ("line 2", "malformed")),
        (".hex", "# comment\n", ("line 1", "malformed")),
        (".gpl", "1 2 3\n", ("line 1", "header")),
        (".gpl", "GIMP Palette\n1 2\n", ("line 2", "malformed")),
        (".gpl", "GIMP Palette\n1 2 blue\n", ("line 2", "malformed")),
        (".gpl", "GIMP Palette\n1.5 2 3\n", ("line 2", "malformed")),
        (".gpl", "GIMP Palette\n1 2 256\n", ("line 2", "0..255")),
        (".gpl", "GIMP Palette\n-1 2 3\n", ("line 2", "0..255")),
        (".gpl", "GIMP Palette\nColumns: oops\n", ("line 2", "malformed")),
        (".hex", "\n010203\n#010203\n", ("line 2", "line 3", "duplicate")),
        (
            ".gpl",
            "GIMP Palette\n1 2 3 A\n# comment\n1 2 3 B\n",
            ("line 2", "line 4", "duplicate"),
        ),
        (".hex", "\n\t\n", ("no colours",)),
        (".gpl", "GIMP Palette\n# comment\n", ("no colours",)),
    ],
)
def test_text_errors(tmp_path, suffix, text, parts):
    assert_problem(text_file(tmp_path, suffix, text), *parts)


@pytest.mark.parametrize("suffix", [".hex", ".gpl"])
def test_utf8_required(tmp_path, suffix):
    path = tmp_path / f"bad{suffix}"
    path.write_bytes(b"GIMP Palette\n\xff")
    assert_problem(path, "line 2", "not UTF-8")


@pytest.mark.parametrize("suffix", [".hex", ".gpl", ".png"])
def test_unreadable(tmp_path, suffix):
    assert_problem(tmp_path / f"missing{suffix}", "cannot be read")
    path = tmp_path / f"directory{suffix}"
    path.mkdir()
    assert_problem(path, "cannot be read")


def test_suffix(tmp_path):
    assert_problem(tmp_path / "colors.jpg", ".hex", ".gpl", ".png")


@pytest.mark.parametrize("suffix", [".hex", ".gpl", ".png"])
def test_256_colors_refused(tmp_path, suffix):
    colors = [(i, 0, 0) for i in range(256)]
    if suffix == ".png":
        path = png_file(tmp_path, "RGB", colors)
    else:
        text = (
            "\n".join("".join(f"{v:02x}" for v in c) for c in colors)
            if suffix == ".hex"
            else "GIMP Palette\n"
            + "\n".join(" ".join(str(v) for v in c) for c in colors)
        )
        path = text_file(tmp_path, suffix, text)
    assert_problem(path, "more than 255")


@pytest.mark.parametrize("damage", ["garbage", "truncated", "wrong_format", "bad_crc"])
def test_undecodable_png(tmp_path, damage):
    path = png_file(tmp_path, "RGB", COLORS)
    data = path.read_bytes()
    if damage == "garbage":
        path.write_bytes(b"not png")
    elif damage == "truncated":
        path.write_bytes(data[: len(data) // 2])
    elif damage == "bad_crc":
        path.write_bytes(data[:29] + bytes([data[29] ^ 1]) + data[30:])
    else:
        Image.new("RGB", (1, 1)).save(path, format="JPEG")
    assert_problem(path, "not a decodable PNG")


def test_empty_iccp_chunk_is_an_undecodable_png(tmp_path):
    # A correct-CRC, empty iCCP chunk makes Pillow's decoder raise IndexError.
    path = tmp_path / "icc.png"
    raw_png(path, 8, 6, 8, 6, 4, [(b"iCCP", b"")])
    assert_problem(path, "not a decodable PNG")


def test_sequence_checks_are_pure_and_name_source(tmp_path):
    source = tmp_path / "nonexistent-settings.json"
    colors = [[1, 2, 3], [4, 5, 6]]
    assert validate_colors(colors, source=source) == ((1, 2, 3), (4, 5, 6))
    assert colors == [[1, 2, 3], [4, 5, 6]]
    assert not source.exists()
    assert validate_colors([(i, 0, 0) for i in range(255)], source=source)[-1] == (
        254,
        0,
        0,
    )
    for entries, part in [
        ([], "no colours"),
        ([(i, 0, 0) for i in range(256)], "more than 255"),
        ([(1, 2, 3)] * 2, "duplicate"),
    ]:
        with pytest.raises(PaletteError) as caught:
            validate_colors(entries, source=source)
        message = str(caught.value)
        assert str(source) in message and part in message and "line" not in message
        if part == "duplicate":
            assert "entry 1" in message and "entry 2" in message


@pytest.mark.parametrize(
    "color", [None, (1, 2), (1, 2, 256), (-1, 2, 3), (1.0, 2, 3), (True, 2, 3), "abc"]
)
def test_sequence_requires_rgb_integers(color):
    with pytest.raises(PaletteError, match="settings.json.*entry 1"):
        validate_colors([color], source="settings.json")


def chunk(tag, payload):
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload))
    )


ADAM7 = [
    (0, 0, 8, 8),
    (4, 0, 8, 8),
    (0, 4, 4, 8),
    (2, 0, 4, 4),
    (0, 2, 2, 4),
    (1, 0, 2, 2),
    (0, 1, 1, 2),
]


def png16(
    tmp_path, kind, pixels, *, width=1, interlace=0, filter_type=0, transparency=None
):
    """Generate source 16-bit samples, including data Pillow cannot write."""
    height = len(pixels) // width
    stride = len(pixels[0]) * 2
    raw = bytearray()
    for x0, y0, dx, dy in ADAM7 if interlace else [(0, 0, 1, 1)]:
        xs = range(x0, width, dx)
        if not xs:
            continue
        previous = bytes(len(xs) * stride)
        for y in range(y0, height, dy):
            row = b"".join(
                struct.pack(
                    ">" + "H" * len(pixels[y * width + x]), *pixels[y * width + x]
                )
                for x in xs
            )
            filtered = bytearray()
            for i, value in enumerate(row):
                a = row[i - stride] if i >= stride else 0
                b = previous[i]
                c = previous[i - stride] if i >= stride else 0
                # Independent encoder formulation of PNG's Paeth predictor.
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                paeth = a if pa <= pb and pa <= pc else b if pb <= pc else c
                prediction = [0, a, b, (a + b) // 2, paeth][filter_type]
                filtered.append((value - prediction) % 256)
            raw.extend(bytes([filter_type]) + filtered)
            previous = row
    data = b"\x89PNG\r\n\x1a\n" + chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 16, kind, 0, 0, interlace)
    )
    if transparency is not None:
        data += chunk(
            b"tRNS", struct.pack(">" + "H" * len(transparency), *transparency)
        )
    data += chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    path = tmp_path / "source16.png"
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("kind", [0, 2, 4, 6])
@pytest.mark.parametrize("filter_type", range(5))
@pytest.mark.parametrize("interlace", [0, 1])
def test_16bit_exact_samples_all_modes_filters_interlace(
    tmp_path, kind, filter_type, interlace
):
    colors = [(i, (i * 37) % 256, 255 - i) for i in range(81)]
    pixels = [
        (c[0] * 257,) if kind in (0, 4) else tuple(v * 257 for v in c) for c in colors
    ]
    if kind in (4, 6):
        pixels = [(*p, 65535) for p in pixels]
    path = png16(
        tmp_path, kind, pixels, width=9, filter_type=filter_type, interlace=interlace
    )
    expected = tuple((c[0],) * 3 if kind in (0, 4) else c for c in colors)
    assert read_palette(path) == expected


@pytest.mark.parametrize("kind", [0, 2, 4, 6])
def test_16bit_lossy_source_refused(tmp_path, kind):
    pixel = (258,) if kind in (0, 4) else (257, 258, 65535)
    if kind in (4, 6):
        pixel = (*pixel, 65535)
    assert_problem(png16(tmp_path, kind, [pixel]), "exactly at 8 bits")


@pytest.mark.parametrize("kind", [4, 6])
def test_16bit_alpha_cannot_round_to_opaque(tmp_path, kind):
    pixel = (257, 65534) if kind == 4 else (257, 514, 771, 65534)
    assert_problem(png16(tmp_path, kind, [pixel]), "not opaque")


@pytest.mark.parametrize("kind", [0, 2])
def test_16bit_transparent_sample(tmp_path, kind):
    pixel = (257,) if kind == 0 else (257, 514, 771)
    assert_problem(png16(tmp_path, kind, [pixel], transparency=pixel), "not opaque")


def test_tiny_interlaced_png16(tmp_path):
    assert read_palette(png16(tmp_path, 2, [(257, 514, 771)], interlace=1)) == (
        (1, 2, 3),
    )


def test_huge_gpl_integer_is_palette_error(tmp_path):
    path = text_file(tmp_path, ".gpl", "GIMP Palette\n" + "9" * 5000 + " 2 3\n")
    assert_problem(path, "line 2", "0..255")


def test_gpl_leading_zeros(tmp_path):
    path = text_file(tmp_path, ".gpl", "GIMP Palette\n+" + "0" * 5000 + "1 -000 003\n")
    assert read_palette(path) == ((1, 0, 3),)
