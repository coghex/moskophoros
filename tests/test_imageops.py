import struct
import zlib

import numpy as np
import pytest
from PIL import Image

from moskophoros.imageops import MAX_PIXELS, load_png, reduce_blocks


def _image(rows):
    """An image from rows of `(r, g, b, a)` tuples."""
    return np.array(rows, dtype=np.uint8)


def _block(pixels):
    """A 2×2 image from four pixels, row by row."""
    return _image([pixels[:2], pixels[2:]])


def _reduce_one(pixels):
    (row,) = reduce_blocks(_block(pixels), 2)
    (pixel,) = row
    return tuple(int(value) for value in pixel)


# Coverage threshold. A 2×2 block holds 4 · 255 = 1020 alpha; half is 510.

GREY = (100, 150, 200)


@pytest.mark.parametrize(
    ("alphas", "expected"),
    [
        ((255, 254, 0, 0), (0, 0, 0, 0)),  # 509: just below half
        ((255, 255, 0, 0), (*GREY, 255)),  # 510: exactly half is kept
        ((255, 255, 1, 0), (*GREY, 255)),  # 511: just above
        ((170, 170, 170, 0), (*GREY, 255)),  # 510 spread over three pixels
        ((170, 170, 169, 0), (0, 0, 0, 0)),  # 509 spread over three pixels
    ],
)
def test_coverage_threshold(alphas, expected):
    assert _reduce_one([(*GREY, a) for a in alphas]) == expected


@pytest.mark.parametrize(
    ("alpha", "kept"), [(0, False), (127, False), (128, True), (255, True)]
)
def test_factor_one_thresholds_each_pixel_alone(alpha, kept):
    # Coverage alpha / 255 reaches 0.5 at 127.5, so 128 is the first kept.
    (row,) = reduce_blocks(_image([[(7, 8, 9, alpha)]]), 1)
    assert tuple(int(v) for v in row[0]) == ((7, 8, 9, 255) if kept else (0, 0, 0, 0))


def test_factor_one_keeps_exact_colors():
    pixels = _image(
        [[(1, 2, 3, 255), (254, 0, 77, 200)], [(9, 9, 9, 128), (5, 6, 7, 10)]]
    )
    assert reduce_blocks(pixels, 1).tolist() == [
        [[1, 2, 3, 255], [254, 0, 77, 255]],
        [[9, 9, 9, 255], [0, 0, 0, 0]],
    ]


def test_a_nearly_transparent_bright_pixel_barely_shifts_the_mean():
    # Σa = 3·255 + 1 = 766 and Σa·c = 3·255·10 + 1·250 = 7900 per channel,
    # so the mean is 7900 / 766 ≈ 10.31, which rounds to 10. An unweighted
    # mean would be (3·10 + 250) / 4 = 70.
    dark = (10, 10, 10, 255)
    assert _reduce_one([dark, dark, dark, (250, 250, 250, 1)]) == (10, 10, 10, 255)


def test_alpha_weighting_follows_the_weights():
    # Σa = 255 + 85 + 170 = 510. Red: 255·200 / 510 = 100. Green:
    # 85·200 / 510 ≈ 33.33 → 33. Blue: 170·90 / 510 = 30.
    pixels = [(200, 0, 0, 255), (0, 200, 0, 85), (0, 0, 90, 170), (9, 9, 9, 0)]
    assert _reduce_one(pixels) == (100, 33, 30, 255)


def test_rounding_exactly_at_a_half_goes_up():
    # Opaque block: red (0 + 1 + 0 + 0) / 4 = 0.25 → 0, green
    # (0 + 1 + 1 + 0) / 4 = 0.5 → 1, blue (2 + 3 + 2 + 3) / 4 = 2.5 → 3
    # (banker's rounding would give 2).
    pixels = [(0, 0, 2, 255), (1, 1, 3, 255), (0, 1, 2, 255), (0, 0, 3, 255)]
    assert _reduce_one(pixels) == (0, 1, 3, 255)


def test_weighted_rounding_at_a_half_goes_up():
    # Σa = 170 + 85 + 255 = 510, exactly half coverage. Red:
    # (170·0 + 85·0 + 255·3) / 510 = 1.5 → 2. Green: (170·3 + 85·0 + 255·0)
    # / 510 = 1. Blue: (170·0 + 85·9 + 255·0) / 510 = 1.5 → 2.
    pixels = [(0, 3, 0, 170), (0, 0, 9, 85), (3, 0, 0, 255), (99, 99, 99, 0)]
    assert _reduce_one(pixels) == (2, 1, 2, 255)


def test_rounding_just_below_a_half_goes_down():
    # Σa = 3·255 + 254 = 1019. Red: (255·(2 + 3 + 2) + 254·2) / 1019
    # = 2293 / 1019 ≈ 2.2502 → 2. Green: 254·2 / 1019 ≈ 0.4985 → 0.
    pixels = [(2, 0, 0, 255), (3, 0, 0, 255), (2, 0, 0, 255), (2, 2, 0, 254)]
    assert _reduce_one(pixels) == (2, 0, 0, 255)


def test_a_fully_transparent_block_is_transparent_black():
    pixels = [(255, 255, 255, 0), (12, 200, 7, 0), (1, 2, 3, 0), (99, 0, 99, 0)]
    assert _reduce_one(pixels) == (0, 0, 0, 0)


def test_several_blocks_reduce_in_place():
    # A 4×6 image (2 rows of 3 blocks at s = 2), each block a distinct solid
    # opaque color except one half-covered and one empty block.
    colors = [
        [(10, 20, 30), (40, 50, 60), (70, 80, 90)],
        [(1, 2, 3), (4, 5, 6), (7, 8, 9)],
    ]
    pixels = np.zeros((4, 6, 4), dtype=np.uint8)
    for by, row in enumerate(colors):
        for bx, color in enumerate(row):
            pixels[2 * by : 2 * by + 2, 2 * bx : 2 * bx + 2] = (*color, 255)
    pixels[0:2, 2:4, 3] = (255, 0)  # left column of block (0, 1) only: half
    pixels[2:4, 4:6, 3] = 0  # block (1, 2) empty
    assert reduce_blocks(pixels, 2).tolist() == [
        [[10, 20, 30, 255], [40, 50, 60, 255], [70, 80, 90, 255]],
        [[1, 2, 3, 255], [4, 5, 6, 255], [0, 0, 0, 0]],
    ]


def test_factor_three_averages_nine_pixels():
    # Red 0..8 over an opaque 3×3 block: mean 4. Green alternates 0 and 255
    # (five 255s): 1275 / 9 = 141.67 → 142.
    pixels = np.zeros((3, 3, 4), dtype=np.uint8)
    pixels[..., 0] = np.arange(9).reshape(3, 3)
    pixels[..., 1] = np.array([[255, 0, 255], [0, 255, 0], [255, 0, 255]])
    pixels[..., 3] = 255
    assert reduce_blocks(pixels, 3).tolist() == [[[4, 142, 0, 255]]]


def test_factor_sixteen_with_high_values_does_not_overflow():
    pixels = np.full((32, 16, 4), 255, dtype=np.uint8)
    pixels[16:, :, :3] = (254, 1, 128)
    assert reduce_blocks(pixels, 16).tolist() == [
        [[255, 255, 255, 255]],
        [[254, 1, 128, 255]],
    ]


def test_the_result_is_uint8_rgba():
    result = reduce_blocks(np.zeros((4, 6, 4), dtype=np.uint8), 2)
    assert result.dtype == np.uint8
    assert result.shape == (2, 3, 4)


def test_a_numpy_integer_factor_is_accepted():
    assert reduce_blocks(np.zeros((2, 2, 4), dtype=np.uint8), np.int64(2)).shape == (
        1,
        1,
        4,
    )


def test_the_input_is_not_changed():
    pixels = np.arange(4 * 4 * 4, dtype=np.uint8).reshape(4, 4, 4)
    before = pixels.copy()
    reduce_blocks(pixels, 2)
    assert np.array_equal(pixels, before)


@pytest.mark.parametrize(
    ("shape", "factor"), [((5, 4, 4), 2), ((4, 6, 4), 4), ((3, 3, 4), 2)]
)
def test_dimensions_not_a_multiple_of_the_factor_are_rejected(shape, factor):
    with pytest.raises(ValueError, match="does not divide"):
        reduce_blocks(np.zeros(shape, dtype=np.uint8), factor)


@pytest.mark.parametrize(
    ("pixels", "factor", "error"),
    [
        ([[[0, 0, 0, 0]]], 1, TypeError),
        (np.zeros((2, 2, 4), dtype=np.float64), 1, TypeError),
        (np.zeros((2, 2, 4), dtype=np.uint16), 1, TypeError),
        (np.zeros((2, 2), dtype=np.uint8), 1, ValueError),
        (np.zeros((2, 2, 3), dtype=np.uint8), 1, ValueError),
        (np.zeros((1, 2, 2, 4), dtype=np.uint8), 1, ValueError),
        (np.zeros((0, 2, 4), dtype=np.uint8), 1, ValueError),
        (np.zeros((2, 2, 4), dtype=np.uint8), 0, ValueError),
        (np.zeros((2, 2, 4), dtype=np.uint8), -2, ValueError),
        (np.zeros((2, 2, 4), dtype=np.uint8), 2.0, TypeError),
        (np.zeros((2, 2, 4), dtype=np.uint8), True, TypeError),
        (np.zeros((2, 2, 4), dtype=np.uint8), "2", TypeError),
    ],
    ids=[
        "a list",
        "float64",
        "uint16",
        "two dimensions",
        "three channels",
        "four dimensions",
        "empty",
        "factor 0",
        "factor -2",
        "factor 2.0",
        "factor True",
        "factor '2'",
    ],
)
def test_malformed_arguments_are_rejected(pixels, factor, error):
    with pytest.raises(error):
        reduce_blocks(pixels, factor)


# Loading


def _png(width, height, rows, *, bit_depth=8, color_type=6):
    """Encode a PNG by hand, so the test controls every header field."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    raw = b"".join(b"\0" + bytes(row) for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_a_png_round_trips_through_the_loader(tmp_path):
    pixels = _image(
        [
            [(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 0)],
            [(1, 2, 3, 4), (250, 251, 252, 253), (17, 34, 51, 68)],
        ]
    )
    path = tmp_path / "frame.png"
    Image.fromarray(pixels, "RGBA").save(path)
    loaded = load_png(path)
    assert loaded.dtype == np.uint8
    assert loaded.shape == (2, 3, 4)
    assert np.array_equal(loaded, pixels)


def test_rows_load_top_to_bottom(tmp_path):
    rows = [[10, 20, 30, 40], [50, 60, 70, 80]]  # one pixel per row
    path = tmp_path / "rows.png"
    path.write_bytes(_png(1, 2, rows))
    assert load_png(path).tolist() == [[[10, 20, 30, 40]], [[50, 60, 70, 80]]]


@pytest.mark.parametrize(
    ("data", "match"),
    [
        (b"not a png at all, just text", "is not a PNG"),
        (_png(1, 1, [[1, 2, 3]], color_type=2), "color type 2"),
        (_png(1, 1, [[0, 1, 0, 2, 0, 3, 0, 4]], bit_depth=16), "bit depth 16"),
        (_png(1, 1, [[1, 2]], color_type=4), "color type 4"),
    ],
    ids=["text", "RGB", "16-bit RGBA", "grey with alpha"],
)
def test_the_loader_rejects_other_files(tmp_path, data, match):
    path = tmp_path / "frame.png"
    path.write_bytes(data)
    with pytest.raises(ValueError, match=match):
        load_png(path)


def test_a_missing_file_raises_os_error(tmp_path):
    with pytest.raises(OSError):
        load_png(tmp_path / "missing.png")


def test_the_loader_accepts_images_above_pillows_default_guard(tmp_path, monkeypatch):
    path = tmp_path / "frame.png"
    Image.fromarray(np.full((16, 16, 4), 9, dtype=np.uint8), "RGBA").save(path)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(Image.DecompressionBombError):
        Image.open(path)
    assert load_png(path).shape == (16, 16, 4)
    assert Image.MAX_IMAGE_PIXELS == 10


def test_the_guard_is_restored_when_loading_fails(tmp_path, monkeypatch):
    data = _png(16, 16, [[9] * 64] * 16)
    path = tmp_path / "truncated.png"
    path.write_bytes(data[: len(data) - 30])
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(Exception):  # noqa: B017 (Pillow's own decode error)
        load_png(path)
    assert Image.MAX_IMAGE_PIXELS == 10


def test_the_largest_capture_is_within_the_guard():
    # A 4096-pixel cell side at the largest supersample, 16.
    assert MAX_PIXELS == (4096 * 16) * (4096 * 16)
