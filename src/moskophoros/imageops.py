"""Shared image operations: composable functions, usable outside the pipeline.

Images are NumPy `uint8` arrays of shape `(height, width, 4)`: RGBA with
straight (not premultiplied) alpha, channel values as encoded (sRGB for a
captured frame), and rows top to bottom as a PNG stores them.
"""

from pathlib import Path

import numpy as np
from PIL import Image

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_RGBA = 6

# The largest capture the design allows: a 4096-pixel cell side, supersampled
# 16 times. Pillow's default guard against unexpectedly large images would
# refuse many valid captures.
MAX_PIXELS = (4096 * 16) ** 2


def load_png(path):
    """Load an 8-bit RGBA PNG, such as a captured color buffer, as an array.

    Raises `ValueError` for a file that is not an 8-bit RGBA PNG, and lets
    `OSError` from reading it propagate.
    """
    path = Path(path)
    with path.open("rb") as handle:
        header = handle.read(26)
    if len(header) < 26 or header[:8] != _PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG")
    if header[24] != 8 or header[25] != _PNG_RGBA:
        raise ValueError(
            f"{path} is not 8-bit RGBA (bit depth {header[24]}, "
            f"color type {header[25]})"
        )
    limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(path, formats=["PNG"]) as image:
            image.load()
            if image.mode != "RGBA":
                raise ValueError(f"{path} decodes as {image.mode}, not RGBA")
            pixels = np.array(image, dtype=np.uint8)
    finally:
        Image.MAX_IMAGE_PIXELS = limit
    return pixels


def reduce_blocks(pixels, factor):
    """Reduce an `(H·s)×(W·s)` RGBA image by `s×s` blocks to `H×W`.

    For each block, coverage is its mean alpha over 255. Below 0.5 the output
    pixel is `(0, 0, 0, 0)`; otherwise its RGB is the alpha-weighted mean
    `Σ(aᵢ·cᵢ) / Σaᵢ` of the block's RGB, rounded half up, and its alpha is
    255. The arithmetic is exact integer arithmetic. The input is not changed.

    Raises `TypeError` for a non-array, a non-`uint8` array or a factor that is
    not an integer, and `ValueError` for a malformed shape, a factor below 1,
    or dimensions that are not multiples of the factor.
    """
    if not isinstance(pixels, np.ndarray):
        raise TypeError(f"pixels must be a NumPy array, not {type(pixels).__name__}")
    if pixels.dtype != np.uint8:
        raise TypeError(f"pixels must be uint8, not {pixels.dtype}")
    if pixels.ndim != 3 or pixels.shape[2] != 4:
        raise ValueError(
            f"pixels must have shape (height, width, 4), not {pixels.shape}"
        )
    if isinstance(factor, bool) or not isinstance(factor, int | np.integer):
        raise TypeError(f"factor must be an integer, not {factor!r}")
    factor = int(factor)
    if factor < 1:
        raise ValueError(f"factor must be at least 1, not {factor}")
    height, width = pixels.shape[:2]
    if height == 0 or width == 0:
        raise ValueError(f"pixels must not be empty, but have shape {pixels.shape}")
    if height % factor or width % factor:
        raise ValueError(
            f"a {width}x{height} image does not divide into {factor}x{factor} blocks"
        )
    blocks = pixels.astype(np.int64).reshape(
        height // factor, factor, width // factor, factor, 4
    )
    alpha = blocks[..., 3]
    alpha_sum = alpha.sum(axis=(1, 3))
    weighted = (blocks[..., :3] * alpha[..., np.newaxis]).sum(axis=(1, 3))
    # Coverage alpha_sum / (255·s²) is below 0.5 exactly when this holds.
    transparent = 2 * alpha_sum < 255 * factor * factor
    # round(w / a) half up is floor((2w + a) / 2a); a is positive wherever the
    # pixel is kept, and the placeholder 1 elsewhere is discarded below.
    divisor = np.where(transparent, 1, alpha_sum)[..., np.newaxis]
    rgb = (2 * weighted + divisor) // (2 * divisor)
    result = np.zeros((height // factor, width // factor, 4), dtype=np.uint8)
    opaque = ~transparent
    result[opaque, :3] = rgb[opaque]
    result[opaque, 3] = 255
    return result
