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
    blocks = _blocks(pixels, factor)
    rows, factor, columns, _, _ = blocks.shape
    alpha = blocks[..., 3]
    alpha_sum = alpha.sum(axis=(1, 3))
    weighted = (blocks[..., :3] * alpha[..., np.newaxis]).sum(axis=(1, 3))
    # Coverage alpha_sum / (255·s²) is below 0.5 exactly when this holds.
    transparent = _transparent(alpha_sum, factor)
    # round(w / a) half up is floor((2w + a) / 2a); a is positive wherever the
    # pixel is kept, and the placeholder 1 elsewhere is discarded below.
    divisor = np.where(transparent, 1, alpha_sum)[..., np.newaxis]
    rgb = (2 * weighted + divisor) // (2 * divisor)
    result = np.zeros((rows, columns, 4), dtype=np.uint8)
    opaque = ~transparent
    result[opaque, :3] = rgb[opaque]
    result[opaque, 3] = 255
    return result


def reduce_blocks_mode(pixels, factor):
    """Reduce an `(H·s)×(W·s)` RGBA image by `s×s` blocks to `H×W`, keeping
    each block's most common colour.

    Coverage is `reduce_blocks`'s: below 0.5 the output pixel is
    `(0, 0, 0, 0)`. Otherwise each pixel votes for its exact RGB with its
    alpha as the weight, so a transparent pixel casts no vote, and the colour
    with the most votes wins, with alpha 255. A tie goes to the tied colour
    nearest the block's alpha-weighted mean RGB by squared distance, compared
    exactly against the mean as a fraction, then to the smallest packed
    `0xRRGGBB`. The arithmetic is exact integer arithmetic. The input is not
    changed.

    Raises the errors `reduce_blocks` raises, for the same problems.
    """
    blocks = _blocks(pixels, factor)
    rows, factor, columns, _, _ = blocks.shape
    count = rows * columns
    # One row of s² pixels for each block, the blocks in raster order.
    flat = blocks.transpose(0, 2, 1, 3, 4).reshape(count, factor * factor, 4)
    rgb, alpha = flat[..., :3], flat[..., 3]
    alpha_sum = alpha.sum(axis=1)
    weighted = (rgb * alpha[..., np.newaxis]).sum(axis=1)
    result = np.zeros((count, 4), dtype=np.uint8)

    voting = alpha > 0
    if voting.any():
        # Each vote is keyed by its block and packed colour; equal keys are
        # one candidate, whose votes are the summed alphas.
        packed = rgb[..., 0] << 16 | rgb[..., 1] << 8 | rgb[..., 2]
        block = np.broadcast_to(np.arange(count)[:, np.newaxis], packed.shape)
        keys = block[voting] << 24 | packed[voting]
        order = np.argsort(keys, kind="stable")
        keys, weights = keys[order], alpha[voting][order]
        starts = np.flatnonzero(np.diff(keys, prepend=-1))
        votes = np.add.reduceat(weights, starts)
        keys = keys[starts]
        owner, colour = keys >> 24, keys & 0xFFFFFF
        channels = np.stack([colour >> 16, colour >> 8 & 255, colour & 255], axis=1)
        # The squared distance to the mean W / A, scaled by A² to stay exact:
        # Σ (c·A − W)².
        total = alpha_sum[owner][:, np.newaxis]
        distance = ((channels * total - weighted[owner]) ** 2).sum(axis=1)
        # By block, then most votes, nearest the mean, smallest packed value.
        ranked = np.lexsort((colour, distance, -votes, owner))
        first = ranked[np.flatnonzero(np.diff(owner[ranked], prepend=-1))]
        result[owner[first], :3] = channels[first]
        result[owner[first], 3] = 255

    result[_transparent(alpha_sum, factor)] = 0
    return result.reshape(rows, columns, 4)


def _blocks(pixels, factor):
    """Check `reduce_blocks`'s arguments; return the image as `int64` blocks
    of shape `(H, s, W, s, 4)`."""
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
    return pixels.astype(np.int64).reshape(
        height // factor, factor, width // factor, factor, 4
    )


def _transparent(alpha_sum, factor):
    """Where a block's coverage, its alpha sum over `255·s²`, is below 0.5."""
    return 2 * alpha_sum < 255 * factor * factor
