"""Pure lighting and four-mode colour operations (shading design contract 3,
D-5, D-14, D-15, D-23 to D-26, D-36, D-40).

The shading signal of a block is `e = a · L`: the ambient form `a` of its
winning material's shade, times the light factor `L` of its normals' facing
terms. A mode routes that one signal to a ramp band, to a linear brightness
gain, to both or to neither, over a ramp entry or the ordinary colour.

Everything here is pure arrays in and arrays out. It reads no file, imports
no Blender and is wired to no command yet: the settings arrive as the
`shading.Response` and `shading_resolve.Look` that SHD-2 resolves. The
signal is evaluated in `float64`, in the order the design states; the exact
integer path that today's ramps use stays in `imageops`, and runs whenever
the response asks for nothing the integer arithmetic does not already do.
"""

from dataclasses import dataclass

import numpy as np

from moskophoros import imageops, views
from moskophoros.palette import validate_colors
from moskophoros.shading import FRAMES

# The camera's up, in its own frame: +X right, +Y up, +Z toward the viewer.
CAMERA_UP = (0.0, 1.0, 0.0)


@dataclass(frozen=True)
class Lights:
    """The unit vectors toward the key, the sky and the ground, in camera
    coordinates."""

    key: tuple[float, float, float]
    sky: tuple[float, float, float]
    ground: tuple[float, float, float]


def light_vectors(key_direction, frame, camera_direction=None, roll=0.0):
    """The `Lights` for the resolved `key_direction`, the sky and ground
    `frame` (`shading.FRAMES`), and the view's `camera_direction` and `roll`.

    The key is camera-fixed under either frame, normalised as `views` does
    (a direction already of unit length is kept exactly). In the camera frame
    the sky is the picture's up and follows the roll for free. In the world
    frame it is the subject's +Y, projected onto the camera's axes by
    `views.subject_basis`, the one basis both projections use:
    `w = (right_y, up_y, −forward_y)`. Turning the subject about +Y leaves
    it unchanged, so it takes no subject rotation. The ground is the sky's
    opposite. `camera_direction` is needed only for the world frame.
    """
    if frame not in FRAMES:
        raise ValueError(f"the sky and ground frame must be one of {FRAMES}: {frame!r}")
    key = views.normalise(key_direction)
    if frame == "camera":
        sky = CAMERA_UP
    else:
        if camera_direction is None:
            raise ValueError("the world frame needs the camera's direction")
        basis = views.subject_basis(camera_direction, roll)
        sky = (basis.right[1], basis.up[1], 0.0 - basis.forward[1])
    ground = tuple(0.0 - component for component in sky)
    return Lights(key, sky, ground)


def facing(normals, vector):
    """The facing term `min(1, max(0, n · vector))` of each normal `n`, in
    `float64`, after scaling it to unit length (a zero normal faces nothing).
    The dot product of two unit vectors can round above 1, so the term is
    bounded on both sides, as D-26 defines it and `imageops.light_factors`
    does. `normals` has the three components on its last axis; the result
    has its other axes. Nothing is changed in place."""
    normals = np.asarray(normals, dtype=np.float64)
    length = np.sqrt(np.sum(normals * normals, axis=-1, keepdims=True))
    units = normals / np.where(length == 0, 1.0, length)
    dot = np.sum(units * np.asarray(vector, dtype=np.float64), axis=-1)
    return np.minimum(1.0, np.maximum(0.0, dot))


def facing_terms(normals, weight, lights, response):
    """The key, sky and ground facing terms `(k, s, g)` of each sample, in a
    new array of the normals' shape; the last axis holds the three terms.

    A term whose strength is 0 is left 0: it cannot change `L`, and its
    normals need not be there. `normals` may then be None when all three are
    0. Otherwise every sample with some `weight` needs a finite normal that is
    not zero, or this raises `ValueError`; a sample without weight is not
    looked at."""
    strengths = (
        response.key_strength,
        response.sky_strength,
        response.ground_strength,
    )
    vectors = (lights.key, lights.sky, lights.ground)
    if not any(strengths):
        return None if normals is None else np.zeros(np.shape(normals))
    if normals is None:
        raise ValueError("a directional strength needs the layer's normals")
    normals = np.asarray(normals, dtype=np.float64)
    contributing = np.asarray(weight) > 0
    seen = normals[contributing]
    if not np.isfinite(seen).all() or (np.sum(seen * seen, axis=-1) == 0).any():
        raise ValueError("a sample with weight needs a finite normal that is not 0")
    normals = np.where(contributing[..., np.newaxis], normals, 0.0)
    terms = np.zeros(normals.shape)
    for index, (strength, vector) in enumerate(zip(strengths, vectors, strict=True)):
        if strength:
            terms[..., index] = facing(normals, vector)
    return terms


def light_factor(response, key=0.0, sky=0.0, ground=0.0):
    """`L = (1 − K − S − G) + K·key + S·sky + G·ground` for the response's
    strengths `K, S, G`, evaluated in that order in `float64` from facing
    terms `key`, `sky` and `ground` in `[0, 1]`, then bounded to `[0, 1]`
    against rounding (the strengths' sum is at most 1, and SHD-2 rejects any
    other). Defaults, with all strengths 0, give 1."""
    uniform = 1.0 - response.key_strength - response.sky_strength
    uniform = uniform - response.ground_strength
    light = (
        uniform
        + response.key_strength * np.asarray(key, dtype=np.float64)
        + response.sky_strength * np.asarray(sky, dtype=np.float64)
        + response.ground_strength * np.asarray(ground, dtype=np.float64)
    )
    return np.minimum(1.0, np.maximum(0.0, light))


def form_term(shade, shade_range, response):
    """The ambient form `a = (clamp(shade, lo, hi) − lo) / (hi − lo + 1)` of
    `shade` (any array, which need not be whole numbers) over the range
    `[lo, hi]`, clamping first (D-36); 1 where the response turns the form off.
    Returns a new `float64` array of the shade's shape."""
    shade = np.asarray(shade, dtype=np.float64)
    if not response.ambient_form:
        return np.ones(shade.shape)
    lo, hi = shade_range
    return (np.minimum(np.maximum(shade, lo), hi) - lo) / (hi - lo + 1)


def band_of(signal, bands):
    """The band `clamp(floor(N · e), 0, N − 1)` of a signal `e`, for `N`
    bands, as an `int64` array."""
    return np.clip(np.floor(bands * np.asarray(signal)), 0, bands - 1).astype(np.int64)


def plain_signal(weight, shade, terms, response, shade_range):
    """The plain-reduction signal `e` of each block: the winning material's
    raw shade and each facing term averaged separately with the samples'
    `weight`, then `a` from the clamped mean shade and `L` from the mean terms.
    A product of means, not a mean of products, and of terms, not of normals.

    `weight` and `shade` are `(B, S)` arrays, the weight 0 where a sample is
    not the winner's, with some weight in every block; `terms` is
    `facing_terms`' array or None for terms of 0. Returns `(B,)` `float64`."""
    weight = np.asarray(weight, dtype=np.int64)
    total = weight.sum(axis=1)
    if (total <= 0).any():
        raise ValueError("every block needs some weight")

    def mean(values):
        return (weight * values).sum(axis=1) / total

    mean_terms = (
        [0.0, 0.0, 0.0] if terms is None else [mean(terms[..., i]) for i in range(3)]
    )
    form = form_term(mean(np.asarray(shade, dtype=np.int64)), shade_range, response)
    return form * light_factor(response, *mean_terms)


def brightness_gain(signal, response):
    """The gain `floor + (ceiling − floor) · e` of a signal `e` in `[0, 1]`,
    kept within `[floor, ceiling]` against rounding. It is not normalised to
    reach the ceiling: with the form on, the greatest gain is
    `floor + (ceiling − floor) · (hi − lo) / (hi − lo + 1)` (D-40)."""
    floor, ceiling = response.brightness_floor, response.brightness_ceiling
    gain = floor + (ceiling - floor) * np.asarray(signal, dtype=np.float64)
    return np.minimum(ceiling, np.maximum(floor, gain))


def shade_blocks(
    base,
    weight,
    shade,
    normals,
    *,
    ramp,
    palette,
    response,
    shade_range,
    lights,
    by_mode,
):
    """The shaded colour of each block of one winning identity, by the
    response's mode (contract 3's table).

    `base` is the `(B, 3)` `uint8` ordinary colour of each block, reduced as
    the caller does (plain reduces, then maps; mode maps, then votes): it is
    the colour of a material with no `ramp`, and the ramp's last entry takes
    its place as the base where there is one (D-14). `weight`, `shade` and
    `normals` are `(B, S, …)` arrays of each block's `S` samples, with a
    weight of 0 where a sample is not the winner's or shows nothing (an
    `int` array, some weight in every block); `normals` may be None while
    the response's strengths are all 0. `ramp` is a sequence of palette
    indices or None, `palette` the colours they index, `shade_range` the
    material's `(lo, hi)`, and `by_mode` selects the weighted vote of ramp
    entries over the band of the mean.

    | mode       | with a ramp                 | without one          |
    |------------|-----------------------------|----------------------|
    | ramp       | the band's entry            | the base             |
    | brightness | the last entry, scaled      | the base, scaled     |
    | both       | the band's entry, scaled    | the base, scaled     |
    | neither    | the last entry              | the base             |

    A block always scales by the plain signal, after its colour is chosen.
    Returns a new `uint8` array of shape `(B, 3)`; no input is changed.
    """
    base = np.asarray(base)
    weight = np.asarray(weight)
    shade = np.asarray(shade)
    if base.ndim != 2 or base.shape[1] != 3 or base.dtype != np.uint8:
        raise ValueError("base must be a (B, 3) uint8 array")
    if not np.issubdtype(weight.dtype, np.integer) or weight.shape != shade.shape:
        raise ValueError("weight and shade must be integer arrays of one shape")
    if weight.ndim != 2 or len(weight) != len(base):
        raise ValueError("weight and shade must hold the samples of each block")
    if (weight < 0).any():
        raise ValueError("a weight cannot be negative")
    lo, hi = imageops._shade_range(*shade_range)
    palette_array = None
    if ramp is not None:
        palette_array = np.asarray(validate_colors(palette, source="palette"), np.uint8)
        ramp = np.asarray(ramp, dtype=np.int64)
        if (
            ramp.ndim != 1
            or len(ramp) == 0
            or not ((0 <= ramp) & (ramp < len(palette_array))).all()
        ):
            raise ValueError(
                f"a ramp must be non-empty indices into the {len(palette_array)}-colour "
                f"palette, not {tuple(ramp)}"
            )
    terms = facing_terms(normals, weight, lights, response)
    signal = plain_signal(weight, shade, terms, response, (lo, hi))

    if ramp is None:
        colour = base.copy()
    elif response.mode in ("ramp", "both"):
        entries = _entries(
            weight.astype(np.int64),
            shade.astype(np.int64),
            terms,
            signal,
            ramp,
            len(palette_array),
            response,
            (lo, hi),
            by_mode,
        )
        colour = palette_array[entries]
    else:
        colour = np.tile(palette_array[ramp[-1]], (len(base), 1))
    if response.mode in ("brightness", "both"):
        colour = imageops.scale_srgb(colour, brightness_gain(signal, response))
    return colour


def _entries(weight, shade, terms, signal, ramp, size, response, shade_range, by_mode):
    """The palette index of each block's ramp entry."""
    lo, hi = shade_range
    if response.ambient_form and not (
        response.key_strength or response.sky_strength or response.ground_strength
    ):
        # Nothing the integer arithmetic does not already do: keep it exactly.
        return imageops._ramp_entries(weight, shade, ramp, lo, hi, size, by_mode)
    if not by_mode:
        return ramp[band_of(signal, len(ramp))]
    return _voted(weight, shade, terms, signal, ramp, response, shade_range)


# The most block-by-entry (and block-by-sample) cells a vote holds at once.
_VOTE_BATCH = 1 << 18


def _voted(weight, shade, terms, signal, ramp, response, shade_range):
    """The palette index of each block's most voted ramp entry, every sample
    voting with its weight for the entry of its own band. Entries a ramp
    repeats pool their votes. A tie goes to the entry with a band centre
    `(k + ½) / N` nearest the block's plain `signal`, counting every band the
    entry has, then to the lower palette index.

    The blocks go in batches, so the working arrays, each of a block's
    entries or bands or samples, stay a fixed size however large the image."""
    entries, unit = np.unique(ramp, return_inverse=True)
    width = max(len(entries), len(ramp), weight.shape[1])
    step = max(1, _VOTE_BATCH // width)
    chosen = np.empty(len(weight), dtype=np.int64)
    for start in range(0, len(weight), step):
        part = slice(start, start + step)
        chosen[part] = _voted_batch(
            weight[part],
            shade[part],
            None if terms is None else terms[part],
            signal[part],
            ramp,
            entries,
            unit,
            response,
            shade_range,
        )
    return chosen


def _voted_batch(
    weight, shade, terms, signal, ramp, entries, unit, response, shade_range
):
    bands, kinds = len(ramp), len(entries)
    terms = np.zeros((*shade.shape, 3)) if terms is None else terms
    sample = form_term(shade, shade_range, response) * light_factor(
        response, terms[..., 0], terms[..., 1], terms[..., 2]
    )
    band = band_of(sample, bands)
    voting = weight > 0
    block = np.broadcast_to(np.arange(len(weight))[:, np.newaxis], weight.shape)
    votes = np.bincount(
        (block * kinds + unit[band])[voting],
        weights=weight[voting],
        minlength=len(weight) * kinds,
    ).reshape(len(weight), kinds)
    gaps = np.abs(signal[:, np.newaxis] - (np.arange(bands) + 0.5) / bands)
    distance = np.stack([gaps[:, unit == k].min(axis=1) for k in range(kinds)], axis=1)
    distance = np.where(votes == votes.max(axis=1, keepdims=True), distance, np.inf)
    # `entries` ascends, so the first of equal distances is the lower index.
    nearest = np.argmax(distance == distance.min(axis=1, keepdims=True), axis=1)
    return entries[nearest]


def shade_layer(
    base,
    identity,
    shade,
    normals,
    weights,
    factor,
    *,
    ramps,
    palette,
    looks,
    lights,
    by_mode,
    pool=None,
):
    """A layer's reduced `base` colour with each block shaded by its winning
    material's look (`shade_blocks`), the winner chosen as `imageops.map_ramps`
    chooses it.

    `base` is the `H×W×4` `uint8` reduced ordinary colour. `identity` (an
    integer array, −1 for none), `shade` (`uint8`), `normals` (`H·s×W·s×3`,
    or None while no look uses a direction) and `weights` (the layer's visible
    weights, integers) are `H·s×W·s` supersampled arrays; only samples that
    belong to the winner and have a weight contribute. `ramps` holds, for each
    identity index, a tuple of palette indices or None, and `looks` its
    `shading_resolve.Look`. `pool` is as for `map_ramps`.

    A block that has no winner, whether no weight, no vote or an alpha of 0 in
    `base`, keeps its ordinary look in every mode. Alpha is `base`'s and the
    inputs are not changed. Returns a new `H×W×4` array.
    """
    if not isinstance(base, np.ndarray) or base.dtype != np.uint8 or base.ndim != 3:
        raise TypeError("base must be a uint8 array of shape (height, width, 4)")
    if base.shape[2] != 4:
        raise ValueError(f"base must have shape (height, width, 4), not {base.shape}")
    rows, columns = base.shape[:2]
    if not isinstance(identity, np.ndarray):
        raise TypeError("identity must be a NumPy array")
    factor = imageops._check_factor(identity.shape, factor)
    shape = (rows * factor, columns * factor)
    for name, array in (("identity", identity), ("shade", shade), ("weights", weights)):
        if not isinstance(array, np.ndarray):
            raise TypeError(f"{name} must be a NumPy array")
        if array.shape != shape:
            raise ValueError(f"{name} must have shape {shape}, not {array.shape}")
    if not np.issubdtype(identity.dtype, np.integer):
        raise TypeError(f"identity must be an integer array, not {identity.dtype}")
    if not np.issubdtype(weights.dtype, np.integer):
        raise TypeError(f"weights must be an integer array, not {weights.dtype}")
    if shade.dtype != np.uint8:
        raise TypeError(f"shade must be uint8, not {shade.dtype}")
    if normals is not None:
        normals = np.asarray(normals)
        if normals.shape != (*shape, 3):
            raise ValueError(
                f"normals must have shape {(*shape, 3)}, not {normals.shape}"
            )
    identities = len(ramps)
    if len(looks) != identities:
        raise ValueError("looks must hold one look for each identity")
    if identity.min() < -1 or identity.max() >= identities:
        raise ValueError(f"identity must hold -1 or an index below {identities}")
    if pool is not None:
        pool = np.asarray(pool, dtype=np.int64)
        if pool.shape != (identities,) or pool.min() < 0 or pool.max() >= identities:
            raise ValueError("pool must hold one identity index for each identity")
        identity = np.where(identity < 0, -1, pool[np.maximum(identity, 0)])

    ident = imageops._by_block(identity, factor)
    alpha = imageops._by_block(weights, factor)
    shades = imageops._by_block(shade, factor)
    if normals is not None:
        sampled = (
            normals.reshape(rows, factor, columns, factor, 3)
            .transpose(0, 2, 1, 3, 4)
            .reshape(rows * columns, factor * factor, 3)
        )
    colour = base[..., :3].reshape(-1, 3)
    covered = (base[..., 3] > 0).reshape(-1)
    winner = imageops._winners(alpha, ident, identities, covered)
    result = base.copy()
    flat = result.reshape(-1, 4)
    for index, (ramp, look) in enumerate(zip(ramps, looks, strict=True)):
        chosen = np.flatnonzero(winner == index)
        if len(chosen) == 0:
            continue
        own = (ident[chosen] == index) & (alpha[chosen] > 0)
        flat[chosen, :3] = shade_blocks(
            colour[chosen],
            alpha[chosen] * own,
            shades[chosen],
            None if normals is None else sampled[chosen],
            ramp=ramp,
            palette=palette,
            response=look.response,
            shade_range=look.shade_range,
            lights=lights,
            by_mode=by_mode,
        )
    return result
