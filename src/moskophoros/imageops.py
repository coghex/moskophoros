"""Shared image operations: composable functions, usable outside the pipeline.

Images are NumPy `uint8` arrays of shape `(height, width, 4)`: RGBA with
straight (not premultiplied) alpha, channel values as encoded (sRGB for a
captured frame), and rows top to bottom as a PNG stores them.
"""

from pathlib import Path

import numpy as np
from PIL import Image

from moskophoros.palette import validate_colors

# A fixed lookup for every encoded 8-bit sRGB value. No per-pixel gamma powers.
_SRGB = np.arange(256, dtype=np.float64) / 255
_SRGB_LINEAR = np.where(
    _SRGB <= 0.04045, _SRGB / 12.92, ((_SRGB + 0.055) / 1.055) ** 2.4
)
_SRGB_LINEAR.setflags(write=False)
_PALETTE_BATCH = 65536
# How a pixel takes its alpha from its block (alpha design D-4, D-9); the
# first is the default.
EDGES = ("hard", "soft")
# A sample's composite alpha is in units of 1/65535: an 8-bit alpha `a` is
# `257 · a`, so 255 is the whole 65535.
_UNIT = 65535


def _oklab(rgb):
    """Linear sRGB to OKLab, using the 2021 matrices from Björn Ottosson.

    https://bottosson.github.io/posts/oklab/ . Explicit elementwise arithmetic
    keeps the operation order independent of the number of pixels in a batch.
    """
    r, g, b = np.moveaxis(_SRGB_LINEAR[rgb], -1, 0)
    l_root = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.stack(
        (
            0.2104542553 * l_root + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l_root - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l_root + 0.7827717662 * m - 0.8086757660 * s,
        ),
        axis=-1,
    )


def map_palette(pixels, colors):
    """Map RGBA to an ordered palette by Euclidean OKLab distance, undithered.

    Equal distances keep the earlier entry. Alpha is unchanged; zero-alpha
    pixels become transparent black. The input is untouched. Work memory is
    bounded by a fixed pixel batch plus the palette, never pixels × colours.
    """
    if not isinstance(pixels, np.ndarray) or pixels.dtype != np.uint8:
        raise TypeError("pixels must be a uint8 array")
    if pixels.ndim != 3 or pixels.shape[2] != 4:
        raise ValueError("pixels must have shape (height, width, 4)")
    palette = np.asarray(validate_colors(colors, source="palette"), dtype=np.uint8)
    labs = _oklab(palette)
    result = np.array(pixels, copy=True, order="C")
    flat = result.reshape(-1, 4)
    for start in range(0, len(flat), _PALETTE_BATCH):
        batch = flat[start : start + _PALETTE_BATCH]
        lab = _oklab(batch[:, :3])
        best = np.full(len(batch), np.inf)
        chosen = np.zeros(len(batch), dtype=np.uint8)
        for index, color in enumerate(labs):
            difference = lab - color
            distance = np.sum(difference * difference, axis=1)
            closer = distance < best
            best[closer] = distance[closer]
            chosen[closer] = index
        batch[:, :3] = palette[chosen]
        batch[batch[:, 3] == 0] = 0
    return result


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


def block_alpha(alpha, factor, edges):
    """Each `s×s` block's alpha byte: the one coverage decision for its output
    pixel (alpha design, *Stylize: numerical reference*, step 1; D-2, D-4).

    `alpha` is an `(H·s)×(W·s)` array of 8-bit alphas. A sample is a surface
    where its alpha is above 0, and its composite alpha `aᵢ` is its alpha in
    units of 1/65535, `257 · alpha`. With `n = s²`, `m` surface samples and
    `S = Σ aᵢ`, in exact integers:

    - `hard`: the pixel exists when `2m ≥ n`, with `D = 65535 · m`, so its
      alpha is the mean alpha of the surfaces it shows;
    - `soft`: the pixel exists when `S > 0`, with `D = 65535 · n`, so its
      alpha is its block's mean alpha.

    Its alpha is `(510 · S + D) // (2 · D)`, that is `floor(255 · S / D + ½)`,
    and 0 where it does not exist. Returns a new `H×W` `uint8` array.

    Raises `ValueError` for an `edges` other than `EDGES`, and the errors
    `reduce_blocks` raises for a malformed plane or factor.
    """
    if not isinstance(alpha, np.ndarray):
        raise TypeError(f"alpha must be a NumPy array, not {type(alpha).__name__}")
    if alpha.dtype != np.uint8:
        raise TypeError(f"alpha must be uint8, not {alpha.dtype}")
    if alpha.ndim != 2:
        raise ValueError(f"alpha must have shape (height, width), not {alpha.shape}")
    factor = _check_factor(alpha.shape, factor)
    height, width = alpha.shape
    return _alpha_bytes(_by_block(alpha, factor), edges).reshape(
        height // factor, width // factor
    )


def _alpha_bytes(alpha, edges):
    """`block_alpha` for alphas given as one row of `s²` values per block."""
    return _coverage(257 * alpha, alpha > 0, edges)


def _coverage(composite, surfaces, edges):
    """Each block's alpha byte from its samples' composite alphas `aᵢ`, in
    units of 1/65535, and where they are `surfaces`, both given as one row
    of `s²` values per block (numerical reference step 1)."""
    _check_edges(edges)
    n = composite.shape[1]
    surfaces = surfaces.sum(axis=1)
    total = composite.sum(axis=1)
    if edges == "hard":
        exists = 2 * surfaces >= n
        denominator = _UNIT * surfaces
    else:
        exists = total > 0
        denominator = np.full_like(total, _UNIT * n)
    # The placeholder 1 where the pixel does not exist is discarded below.
    denominator = np.where(exists, denominator, 1)
    result = (510 * total + denominator) // (2 * denominator)
    return np.where(exists, result, 0).astype(np.uint8)


def _check_edges(edges):
    if edges not in EDGES:
        raise ValueError(f"edges must be one of {', '.join(EDGES)}, not {edges!r}")


def reduce_blocks(pixels, factor, edges=EDGES[0]):
    """Reduce an `(H·s)×(W·s)` RGBA image by `s×s` blocks to `H×W`.

    Each output pixel's alpha is its block's `block_alpha` under `edges`; a
    pixel of alpha 0 is `(0, 0, 0, 0)`. Otherwise its RGB is the
    alpha-weighted mean `Σ(aᵢ·cᵢ) / Σaᵢ` of the block's RGB, rounded half
    up. The arithmetic is exact integer arithmetic. The input is not changed.

    Raises `TypeError` for a non-array, a non-`uint8` array or a factor that is
    not an integer, and `ValueError` for a malformed shape, a factor below 1,
    dimensions that are not multiples of the factor, or an unknown `edges`.
    """
    blocks = _blocks(pixels, factor)
    rows, factor, columns, _, _ = blocks.shape
    alpha = blocks[..., 3]
    alpha_sum = alpha.sum(axis=(1, 3))
    weighted = (blocks[..., :3] * alpha[..., np.newaxis]).sum(axis=(1, 3))
    alphas = block_alpha(pixels[..., 3], factor, edges)
    kept = alphas > 0
    # round(w / a) half up is floor((2w + a) / 2a); a is positive wherever the
    # pixel is kept, and the placeholder 1 elsewhere is discarded below.
    divisor = np.where(kept, alpha_sum, 1)[..., np.newaxis]
    rgb = (2 * weighted + divisor) // (2 * divisor)
    result = np.zeros((rows, columns, 4), dtype=np.uint8)
    result[kept, :3] = rgb[kept]
    result[kept, 3] = alphas[kept]
    return result


def reduce_blocks_mode(pixels, factor, edges=EDGES[0]):
    """Reduce an `(H·s)×(W·s)` RGBA image by `s×s` blocks to `H×W`, keeping
    each block's most common colour.

    Each output pixel's alpha is `reduce_blocks`'s, and a pixel of alpha 0 is
    `(0, 0, 0, 0)`. Otherwise each pixel votes for its exact RGB with its
    alpha as the weight, so a transparent pixel casts no vote, and the colour
    with the most votes wins. A tie goes to the tied colour
    nearest the block's alpha-weighted mean RGB by squared distance, compared
    exactly against the mean as a fraction, then to the smallest packed
    `0xRRGGBB`. The arithmetic is exact integer arithmetic. The input is not
    changed.

    Raises the errors `reduce_blocks` raises, for the same problems.
    """
    _check_edges(edges)
    blocks = _blocks(pixels, factor)
    rows, factor, columns, _, _ = blocks.shape
    count = rows * columns
    # One row of s² pixels for each block, the blocks in raster order.
    flat = blocks.transpose(0, 2, 1, 3, 4).reshape(count, factor * factor, 4)
    rgb, alpha = flat[..., :3], flat[..., 3]
    result = np.zeros((count, 4), dtype=np.uint8)
    result[:, :3] = _vote(rgb, alpha)
    alphas = _alpha_bytes(alpha, edges)
    result[:, 3] = alphas
    result[alphas == 0] = 0
    return result.reshape(rows, columns, 4)


def _vote(rgb, weight):
    """Each block's most voted colour, as `uint8` RGB of shape `(blocks, 3)`,
    from `rgb` and `weight`, one row of `s²` samples per block: each sample
    votes for its exact RGB with its weight, so a weight of 0 casts no vote.
    A tie goes to the tied colour nearest the block's weighted mean RGB by
    squared distance, compared exactly against the mean as a fraction, then
    to the smallest packed `0xRRGGBB`. A block of no vote is black."""
    count = len(rgb)
    alpha = weight
    alpha_sum = alpha.sum(axis=1)
    weighted = (rgb * alpha[..., np.newaxis]).sum(axis=1)
    result = np.zeros((count, 3), dtype=np.uint8)
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
        # The squared distance to the mean W / A, scaled by A² to stay exact,
        # is Σ (c·A − W)² = A·(A·Σc² − 2·Σc·W) + ΣW². Within a block A > 0
        # and ΣW² are the same for every candidate, so A·Σc² − 2·Σc·W ranks
        # them alike. It stays within int64 for any factor whose block fits
        # in memory, where the squared form overflows above about 200.
        total = alpha_sum[owner]
        distance = total * (channels**2).sum(axis=1) - 2 * (
            channels * weighted[owner]
        ).sum(axis=1)
        # By block, then most votes, nearest the mean, smallest packed value.
        ranked = np.lexsort((colour, distance, -votes, owner))
        first = ranked[np.flatnonzero(np.diff(owner[ranked], prepend=-1))]
        result[owner[first]] = channels[first]
    return result


# The two layers of a supersample (alpha design D-6, D-12, Stylize: numerical
# reference): a back layer, the first opaque surface, and a front layer, the
# translucent surfaces in front of it combined. Weights are in units of
# 1/65535.
OPAQUE = 65535


def layer_weights(back_alpha, front_alpha, front_present):
    """Each supersample's front weight `uᵢ = qᵢ` where the front layer is
    present (0 elsewhere) and the back's transmitted weight
    `tᵢ = bᵢ · (65535 − uᵢ)`, as `int64` arrays of the inputs' shape.

    `back_alpha` is the back colour's 8-bit alpha, so `bᵢ` is
    `257 · alpha / 65535`: 1 on a captured surface, whose alpha is 255, and
    the 8-bit alpha's share otherwise, as `block_alpha` takes it; `tᵢ` is
    `floor(257 · alpha · (65535 − uᵢ) / 65535)`, exact for both.
    `front_alpha` is the front layer's `q`, `front_present` where it is."""
    u = np.where(front_present, front_alpha, 0).astype(np.int64)
    t = (257 * np.asarray(back_alpha, dtype=np.int64) * (OPAQUE - u)) // OPAQUE
    return u, t


def composite_alpha(composite, surfaces, factor, edges):
    """Each `s×s` block's alpha byte from its samples' composite alphas
    `aᵢ = uᵢ + tᵢ` (`layer_weights`) and where a layer is present,
    `surfaces`, both `(H·s)×(W·s)`: `block_alpha`'s rules with `aᵢ` in
    place of `257 · alpha`. A front layer whose `q` is 0 is a surface of
    alpha 0. Returns a new `H×W` `uint8` array."""
    composite = np.asarray(composite, dtype=np.int64)
    factor = _check_factor(composite.shape, factor)
    height, width = composite.shape
    return _coverage(
        _by_block(composite, factor), _by_block(surfaces, factor) > 0, edges
    ).reshape(height // factor, width // factor)


def reduce_weighted(rgb, weight, factor, *, by_mode):
    """One layer reduced by `s×s` blocks with its own weights (numerical
    reference step 2): `(colour, total)`, the block's `uint8` RGB, shape
    `(H, W, 3)`, and its total weight `W`, `int64` of shape `(H, W)`.

    `rgb` is an `(H·s)×(W·s)×3` array of 8-bit sRGB, and `weight` the
    samples' integer weights; a sample of weight 0 adds nothing and casts no
    vote. Plain (`by_mode` false) takes the weighted mean `Σ(wᵢ·cᵢ) / Σwᵢ`,
    rounded half up; mode the weighted vote with `reduce_blocks_mode`'s tie
    rules against the weighted mean. A block of total weight 0 is black."""
    rgb = np.asarray(rgb)
    weight = np.asarray(weight, dtype=np.int64)
    factor = _check_factor(weight.shape, factor)
    height, width = weight.shape
    rows, columns = height // factor, width // factor
    w = _by_block(weight, factor)
    flat = np.stack([_by_block(rgb[..., c], factor) for c in range(3)], axis=-1)
    total = w.sum(axis=1)
    if by_mode:
        colour = _vote(flat, w)
    else:
        weighted = (flat * w[..., np.newaxis]).sum(axis=1)
        divisor = np.where(total > 0, total, 1)[..., np.newaxis]
        colour = np.where(
            total[..., np.newaxis] > 0, (2 * weighted + divisor) // (2 * divisor), 0
        ).astype(np.uint8)
    return colour.reshape(rows, columns, 3), total.reshape(rows, columns)


def composite(front, front_weight, back, back_weight):
    """Each pixel's front layer over its back (numerical reference step 3):
    `C = (W_f · lin(F) + W_b · lin(B)) / (W_f + W_b)` in linear colour,
    `float64`, through the fixed 256-entry sRGB table, encoded to 8-bit sRGB
    with the standard transfer function, rounded half up. A pixel with one
    weighted layer keeps that layer's colour unchanged, and one with none is
    black. `front` and `back` are `uint8` RGB arrays of shape `(H, W, 3)`,
    and the weights `(H, W)`."""
    front, back = np.asarray(front), np.asarray(back)
    front_weight = np.asarray(front_weight, dtype=np.int64)
    back_weight = np.asarray(back_weight, dtype=np.int64)
    result = np.where(
        (front_weight > 0)[..., np.newaxis],
        front,
        np.where((back_weight > 0)[..., np.newaxis], back, 0),
    ).astype(np.uint8)
    both = (front_weight > 0) & (back_weight > 0)
    if both.any():
        wf = front_weight[both].astype(np.float64)[:, np.newaxis]
        wb = back_weight[both].astype(np.float64)[:, np.newaxis]
        linear = (wf * _SRGB_LINEAR[front[both]] + wb * _SRGB_LINEAR[back[both]]) / (
            wf + wb
        )
        encoded = np.where(
            linear <= 0.0031308,
            12.92 * linear,
            1.055 * np.power(linear, 1 / 2.4) - 0.055,
        )
        result[both] = np.minimum(255, np.floor(255 * encoded + 0.5)).astype(np.uint8)
    return result


# A block's normals cancel when their sum is shorter than this (lighting
# sheet design D-15, D-27).
CANCELLING = 1e-6
# The 8 neighbours of a pixel, in a fixed order so their sum is deterministic.
_NEIGHBOURS = tuple(
    (dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)
)


def reduce_normal_depth(normal, depth, covered, factor, pixels_per_meter):
    """Reduce a frame's captured normals and depths by `s×s` blocks to its
    reduced colour's pixels (lighting sheet design D-8, D-15, D-19, D-27).

    `normal` is a `(H·s, W·s, 3)` array of camera-space unit normals and
    `depth` an `(H·s, W·s)` array of depths in meters toward the viewer from
    the ground point, NaN where no surface was sampled, as the command
    decodes them (`sampling.NORMAL`, `sampling.DEPTH`). `covered` is the
    reduced colour's coverage, an `(H, W)` boolean array: its alpha above 0.

    Returns `(normals, depths)`, new `float64` arrays of shapes `(H, W, 3)`
    and `(H, W)`. For a covered pixel:

    - its normal is the sum of the unit normals of every surface sample in
      its block, renormalised; it faces the viewer, `(0, 0, 1)`, when the
      block has no sample or the sum is shorter than `CANCELLING`;
    - its depth, in sheet pixels (meters times `pixels_per_meter`), is the
      mean of the same samples' depths, a cancelling block's included; with
      no sample, the mean of the unrounded means of its covered 8
      neighbours (within the frame) that have samples, else 0. Either is
      rounded half up to the 1/16-pixel step, `floor(16·d + ½) / 16`.

    An uncovered pixel has normal `(0, 0, 0)` and depth 0, whatever samples
    its block holds. Any finite depth is held, without clamping. The inputs
    are not changed, and nothing returned refers to them.

    Raises `TypeError` or `ValueError` for malformed arguments.
    """
    normal = np.asarray(normal)
    depth = np.asarray(depth)
    covered = np.asarray(covered)
    if covered.dtype != np.bool_ or covered.ndim != 2:
        raise ValueError("covered must be a 2-D boolean array")
    if isinstance(factor, bool) or not isinstance(factor, (int, np.integer)):
        raise TypeError("factor must be an integer")
    if factor < 1:
        raise ValueError("factor must be at least 1")
    height, width = covered.shape
    size = (height * factor, width * factor)
    if normal.shape != (*size, 3) or depth.shape != size:
        raise ValueError(
            f"normal {normal.shape} and depth {depth.shape} do not reduce by "
            f"{factor} to {covered.shape}"
        )
    if not (np.isfinite(pixels_per_meter) and pixels_per_meter > 0):
        raise ValueError(
            f"pixels_per_meter must be finite and positive: {pixels_per_meter!r}"
        )
    blocks = (height, factor, width, factor)
    samples = depth.astype(np.float64).reshape(blocks)
    surface = ~np.isnan(samples)
    count = surface.sum(axis=(1, 3))
    vectors = np.where(
        surface[..., np.newaxis], normal.astype(np.float64).reshape(*blocks, 3), 0.0
    )
    summed = vectors.sum(axis=(1, 3))
    length = np.sqrt(np.sum(summed * summed, axis=-1))
    sampled = covered & (count > 0)
    turned = sampled & (length >= CANCELLING)
    normals = np.zeros((height, width, 3))
    normals[turned] = summed[turned] / length[turned][:, np.newaxis]
    normals[covered & ~turned] = (0.0, 0.0, 1.0)
    in_pixels = np.where(surface, samples, 0.0) * float(pixels_per_meter)
    means = in_pixels.sum(axis=(1, 3)) / np.maximum(count, 1)
    # A covered pixel without samples takes its sampled neighbours' mean.
    padded = np.pad(np.where(sampled, means, 0.0), 1)
    present = np.pad(sampled, 1)
    total = np.zeros((height, width))
    neighbours = np.zeros((height, width), dtype=np.int64)
    for dy, dx in _NEIGHBOURS:
        window = (slice(1 + dy, 1 + dy + height), slice(1 + dx, 1 + dx + width))
        total += padded[window]
        neighbours += present[window]
    fallback = np.where(neighbours > 0, total / np.maximum(neighbours, 1), 0.0)
    unrounded = np.where(sampled, means, fallback)
    depths = np.where(covered, np.floor(16 * unrounded + 0.5) / 16, 0.0)
    return normals, depths


def encode_normal(normals):
    """Encode unit normals as bytes, `floor(255 · (n + 1) / 2 + ½)` per
    component, half up (lighting sheet design §Numerical reference): a
    normal facing the viewer, `(0, 0, 1)`, is `(128, 128, 255)`.

    Returns a new `uint8` array of the input's shape, whose last axis holds
    the three components. Raises `ValueError` for a non-finite component or
    one outside −1 to 1 by more than rounding.
    """
    normals = np.asarray(normals, dtype=np.float64)
    if normals.ndim < 1 or normals.shape[-1] != 3:
        raise ValueError("normals must have 3 components on their last axis")
    if not np.isfinite(normals).all() or (np.abs(normals) > 1 + 1e-9).any():
        raise ValueError("normals must be finite components from -1 to 1")
    encoded = np.floor(255 * (normals + 1) / 2 + 0.5)
    return np.clip(encoded, 0, 255).astype(np.uint8)


def light_factors(normal_bytes, depth_codes, ground_px, position, intensity, ambient):
    """Each pixel's light factor `f` for a point light, from the encoded maps
    (lighting sheet design D-13, D-14 and its Numerical reference).

    `normal_bytes` is an `(H, W, 3)` array of encoded normals, `depth_codes`
    an `(H, W)` array of depth codes (`32768 + 16 · depth`), `ground_px` the
    cell's ground pixel corner `(gx, gy)`, `position` the light's `(x, y, z)`
    in sheet pixels from the ground point in camera space (x screen right,
    y screen up, z toward the viewer), `intensity` `I` and `ambient` `A`.
    In `float64`, elementwise, for the pixel in column `c` and row `r`:

    - `m = 2 · byte / 255 − 1`, `N = m / |m|`; `d = (code − 32768) / 16`;
    - `P = (c + ½ − gx, gy − r − ½, d)`, `V = light − P`;
    - `V = 0` gives no diffuse term; otherwise `W = V / max |V_i|`,
      `L = W / |W|`, so every finite light gives a finite direction;
    - `q = min(1, max(0, N · L))`, bounded so rounding never lifts it over
      1 (issue review's correction);
    - `f = min(1, A + (1 − A) · I · q)`.

    Returns a new `float64` array of shape `(H, W)`. Pixels are taken as
    given: the caller passes only covered pixels' meaning.
    """
    normal_bytes = np.asarray(normal_bytes)
    depth_codes = np.asarray(depth_codes)
    height, width = depth_codes.shape
    m = 2 * normal_bytes.astype(np.float64) / 255 - 1
    length = np.sqrt(np.sum(m * m, axis=-1, keepdims=True))
    normals = m / np.where(length == 0, 1.0, length)
    depths = (depth_codes.astype(np.float64) - 32768) / 16
    gx, gy = (float(value) for value in ground_px)
    columns, rows = np.meshgrid(np.arange(width), np.arange(height))
    points = np.stack((columns + 0.5 - gx, gy - rows - 0.5, depths), axis=-1)
    v = np.asarray(position, dtype=np.float64) - points
    largest = np.max(np.abs(v), axis=-1, keepdims=True)
    at_light = largest[..., 0] == 0
    w = v / np.where(largest == 0, 1.0, largest)
    # |W| lies between 1 and √3, except at the light, where W is 0.
    size = np.sqrt(np.sum(w * w, axis=-1, keepdims=True))
    lights = w / np.where(size == 0, 1.0, size)
    diffuse = np.minimum(1.0, np.maximum(0.0, np.sum(normals * lights, axis=-1)))
    diffuse[at_light] = 0.0
    return np.minimum(1.0, ambient + (1 - ambient) * float(intensity) * diffuse)


def light_pixels(
    pixels, normal_bytes, depth_codes, ground_px, position, intensity, ambient
):
    """A cell lit by a point light: each covered pixel's (alpha above 0) R, G
    and B decoded with the fixed sRGB table, multiplied by its
    `light_factors`, and encoded again as `min(255, floor(255 · s + ½))` with
    `s = 12.92 · x` for `x ≤ 0.0031308`, else `1.055 · x^(1/2.4) − 0.055`.
    Alpha is unchanged, partial alpha included (alpha design D-11, D-13), and
    every other pixel is `(0, 0, 0, 0)`. Returns a new `uint8` RGBA array;
    the inputs are not changed."""
    pixels = np.asarray(pixels)
    covered = pixels[..., 3] > 0
    factors = light_factors(
        normal_bytes, depth_codes, ground_px, position, intensity, ambient
    )
    linear = _SRGB_LINEAR[pixels[..., :3]] * factors[..., np.newaxis]
    encoded = np.where(
        linear <= 0.0031308,
        12.92 * linear,
        1.055 * np.power(linear, 1 / 2.4) - 0.055,
    )
    rgb = np.minimum(255, np.floor(255 * encoded + 0.5)).astype(np.uint8)
    lit = np.zeros(pixels.shape, dtype=np.uint8)
    lit[covered, :3] = rgb[covered]
    lit[covered, 3] = pixels[covered, 3]
    return lit


def map_ramps(
    pixels,
    identity,
    shade,
    factor,
    ramps,
    colors,
    lo,
    hi,
    *,
    by_mode,
    pool=None,
    ranges=None,
    edges=EDGES[0],
    weights=None,
):
    """Give each block of a supersampled frame its winning material's ramp
    entry, following design §Stylize (Material ramps).

    `pixels` is an `(H·s)×(W·s)` RGBA image, `identity` an integer array and
    `shade` a `uint8` array of the same height and width. `ramps` holds, for
    each identity index, a tuple of indices into the palette `colors`, or
    `None` where that identity takes the ordinary look. `[lo, hi]` is the
    shade range, `0 ≤ lo < hi ≤ 255`. Equal identity indices are one identity;
    `pool`, if given, maps each index to the one it is pooled into (materials
    sharing a name are one identity), and a tie between identities goes to the
    smaller pooled index. `ranges`, if given, holds for each identity index
    its own shade range `(lo, hi)`, or None where `[lo, hi]` applies: a
    material is banded over its own range throughout, clamping, band
    boundaries and `by_mode`'s band centres included.

    Returns `(result, mapped)`: `mapped`, an `H×W` boolean array, marks the
    blocks that took a ramp entry, and `result`, `H×W×4`, holds that entry's
    colour there, with the block's `block_alpha` under `edges`, and
    `(0, 0, 0, 0)` elsewhere. Only a block whose alpha is above 0 takes an
    entry. Every other block, including a block of no vote and one whose
    winner has no ramp, is left to the caller's ordinary look, whose alpha
    is the same.

    Coverage, identity votes, shade sums, bands and `by_mode` tie comparisons
    are exact integer arithmetic. Nothing is changed in place.

    With `weights`, an integer array of the image's height and width, each
    pixel votes and weighs its shade with its weight instead of its colour
    alpha: a layer's own weights (numerical reference step 2). Every block
    of some weight may then take an entry, with alpha 255, whatever
    `edges`: its coverage is the caller's.

    Raises `TypeError` and `ValueError` for malformed arguments, an unknown
    `edges` included, as `reduce_blocks` does.
    """
    factor = _check_image(pixels, factor)
    _check_edges(edges)
    palette = np.asarray(validate_colors(colors, source="palette"), dtype=np.uint8)
    height, width = pixels.shape[:2]
    for name, array in (("identity", identity), ("shade", shade)):
        if not isinstance(array, np.ndarray):
            raise TypeError(f"{name} must be a NumPy array")
        if array.shape != (height, width):
            raise ValueError(
                f"{name} must have shape {(height, width)}, not {array.shape}"
            )
    if not np.issubdtype(identity.dtype, np.integer):
        raise TypeError(f"identity must be an integer array, not {identity.dtype}")
    if shade.dtype != np.uint8:
        raise TypeError(f"shade must be uint8, not {shade.dtype}")
    lo, hi = _shade_range(lo, hi)
    identities = len(ramps)
    if ranges is None:
        ranges = (None,) * identities
    ranges = tuple(ranges)
    if len(ranges) != identities:
        raise ValueError("ranges must hold one shade range or None per identity")
    ranges = tuple(
        (lo, hi) if bounds is None else _shade_range(*bounds) for bounds in ranges
    )
    for ramp in ramps:
        if ramp is None:
            continue
        if len(ramp) == 0 or not all(0 <= index < len(palette) for index in ramp):
            raise ValueError(
                f"a ramp must be non-empty indices into the {len(palette)}-colour "
                f"palette, not {tuple(ramp)}"
            )
    if identity.min() < -1 or identity.max() >= identities:
        raise ValueError(f"identity must hold -1 or an index below {identities}")
    if pool is not None:
        pool = np.asarray(pool, dtype=np.int64)
        if pool.shape != (identities,) or pool.min() < 0 or pool.max() >= identities:
            raise ValueError("pool must hold one identity index for each identity")
        identity = np.where(identity < 0, -1, pool[np.maximum(identity, 0)])

    rows, columns = height // factor, width // factor
    count = rows * columns
    if weights is None:
        alpha = _by_block(pixels[..., 3], factor)
    else:
        weights = np.asarray(weights)
        if weights.shape != (height, width):
            raise ValueError(
                f"weights must have shape {(height, width)}, not {weights.shape}"
            )
        alpha = _by_block(weights, factor)
    ident = _by_block(identity, factor)
    shades = _by_block(shade, factor)
    result = np.zeros((count, 4), dtype=np.uint8)
    mapped = np.zeros(count, dtype=bool)

    # Identity: each pixel with an identity votes with its colour alpha.
    voting = (alpha > 0) & (ident >= 0)
    if weights is None:
        alphas = _alpha_bytes(alpha, edges)
    else:
        alphas = np.where(alpha.sum(axis=1) > 0, 255, 0).astype(np.uint8)
    covered = alphas > 0
    if voting.any():
        block = np.broadcast_to(np.arange(count)[:, np.newaxis], ident.shape)
        keys = block[voting] * identities + ident[voting]
        order = np.argsort(keys, kind="stable")
        keys, weights = keys[order], alpha[voting][order]
        starts = np.flatnonzero(np.diff(keys, prepend=-1))
        votes = np.add.reduceat(weights, starts)
        keys = keys[starts]
        owner, candidate = keys // identities, keys % identities
        # By block, then most votes, then the smallest identity index.
        ranked = np.lexsort((candidate, -votes, owner))
        first = ranked[np.flatnonzero(np.diff(owner[ranked], prepend=-1))]
        winner = np.full(count, -1, dtype=np.int64)
        winner[owner[first]] = candidate[first]
        winner[~covered] = -1
        for index, ramp in enumerate(ramps):
            if ramp is None:
                continue
            chosen = np.flatnonzero(winner == index)
            if len(chosen) == 0:
                continue
            own = (ident[chosen] == index) & (alpha[chosen] > 0)
            entries = _ramp_entries(
                alpha[chosen] * own,
                shades[chosen],
                np.asarray(ramp, dtype=np.int64),
                *ranges[index],
                len(palette),
                by_mode,
            )
            result[chosen, :3] = palette[entries]
            result[chosen, 3] = alphas[chosen]
            mapped[chosen] = True
    return result.reshape(rows, columns, 4), mapped.reshape(rows, columns)


def _shade_range(lo, hi):
    for bound in (lo, hi):
        if isinstance(bound, bool) or not isinstance(bound, int | np.integer):
            raise TypeError(f"the shade range must be integers, not {bound!r}")
    lo, hi = int(lo), int(hi)
    if not 0 <= lo < hi <= 255:
        raise ValueError(
            f"the shade range must satisfy 0 <= lo < hi <= 255: {lo}, {hi}"
        )
    return lo, hi


# The most tied (block, entry) candidates compared against a ramp at once.
_TIE_BATCH = 4096


def _ramp_entries(weight, shade, ramp, lo, hi, size, by_mode):
    """The palette index of each block of one winning identity.

    `weight` and `shade` hold, for each block, the colour alpha and shade of
    each of its pixels, the weight 0 where a pixel is not the winner's.
    Every block has some weight. `ramp` holds N palette indices.
    """
    bands, span = len(ramp), hi - lo + 1
    total = weight.sum(axis=1)
    mean = (weight * shade).sum(axis=1)
    if not by_mode:
        # Clamp the mean, not its samples: the band is exact in W and A.
        clamped = np.minimum(np.maximum(mean, lo * total), hi * total)
        return ramp[((clamped - lo * total) * bands) // (span * total)]

    band = ((np.clip(shade, lo, hi) - lo) * bands) // span
    voting = weight > 0
    block = np.broadcast_to(np.arange(len(weight))[:, np.newaxis], weight.shape)
    keys = block[voting] * size + ramp[band[voting]]
    order = np.argsort(keys, kind="stable")
    keys, weights = keys[order], weight[voting][order]
    starts = np.flatnonzero(np.diff(keys, prepend=-1))
    votes = np.add.reduceat(weights, starts)
    keys = keys[starts]
    owner, entry = keys // size, keys % size

    # The leading entries of each block: more than one is a tie.
    firsts = np.flatnonzero(np.diff(owner, prepend=-1))
    run = np.diff(np.append(firsts, len(owner)))
    leading = votes == np.repeat(np.maximum.reduceat(votes, firsts), run)
    shared = np.repeat(np.add.reduceat(leading.astype(np.int64), firsts), run) > 1
    distance = np.zeros(len(owner), dtype=np.int64)
    tied = np.flatnonzero(leading & shared)
    centres = 2 * bands * lo + (2 * np.arange(bands) + 1) * span
    for start in range(0, len(tied), _TIE_BATCH):
        part = tied[start : start + _TIE_BATCH]
        # |2·N·W − centre·A| is the distance from the unrounded mean W / A to
        # a band centre, scaled by 2·N·A. An entry repeated in the ramp has
        # several bands, and every one counts, voted for or not.
        gaps = np.abs(
            2 * bands * mean[owner[part], np.newaxis]
            - centres * total[owner[part], np.newaxis]
        )
        gaps[ramp != entry[part, np.newaxis]] = np.iinfo(np.int64).max
        distance[part] = gaps.min(axis=1)
    # By block, then most votes, nearest a band, smallest palette index.
    ranked = np.lexsort((entry, distance, -votes, owner))
    return entry[ranked[np.flatnonzero(np.diff(owner[ranked], prepend=-1))]]


def _check_image(pixels, factor):
    """Check a block reduction's arguments; return `factor` as an `int`."""
    if not isinstance(pixels, np.ndarray):
        raise TypeError(f"pixels must be a NumPy array, not {type(pixels).__name__}")
    if pixels.dtype != np.uint8:
        raise TypeError(f"pixels must be uint8, not {pixels.dtype}")
    if pixels.ndim != 3 or pixels.shape[2] != 4:
        raise ValueError(
            f"pixels must have shape (height, width, 4), not {pixels.shape}"
        )
    return _check_factor(pixels.shape, factor)


def _check_factor(shape, factor):
    """Check that an image of `shape` divides into `factor`×`factor` blocks;
    return `factor` as an `int`."""
    if isinstance(factor, bool) or not isinstance(factor, int | np.integer):
        raise TypeError(f"factor must be an integer, not {factor!r}")
    factor = int(factor)
    if factor < 1:
        raise ValueError(f"factor must be at least 1, not {factor}")
    height, width = shape[:2]
    if height == 0 or width == 0:
        raise ValueError(f"pixels must not be empty, but have shape {shape}")
    if height % factor or width % factor:
        raise ValueError(
            f"a {width}x{height} image does not divide into {factor}x{factor} blocks"
        )
    return factor


def _blocks(pixels, factor):
    """Check `reduce_blocks`'s arguments; return the image as `int64` blocks
    of shape `(H, s, W, s, 4)`."""
    factor = _check_image(pixels, factor)
    height, width = pixels.shape[:2]
    return pixels.astype(np.int64).reshape(
        height // factor, factor, width // factor, factor, 4
    )


def _by_block(plane, factor):
    """An `(H·s)×(W·s)` plane as one row of `s²` `int64` values for each
    block, the blocks in raster order."""
    height, width = plane.shape
    return (
        plane.astype(np.int64)
        .reshape(height // factor, factor, width // factor, factor)
        .transpose(0, 2, 1, 3)
        .reshape(-1, factor * factor)
    )
