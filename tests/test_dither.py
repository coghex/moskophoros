"""The deterministic threshold tiles, band dithering and two-nearest snap
(shading design contract 3 and *Fixed tile definitions*; D-17, D-27, D-29,
D-34): exact small fixtures on addressed arrays, with no Blender, file or
command. Production wiring is a later slice; these pin the kernels."""

import dataclasses
import math
import tracemalloc

import numpy as np
import pytest

from moskophoros import dither, imageops, lighting, shading

DEFAULT = shading.settings_of({}).response
LIGHTS = lighting.Lights(
    key=(0.0, 0.0, 1.0), sky=(0.0, 1.0, 0.0), ground=(0.0, -1.0, 0.0)
)
TOWARD_KEY = (0.0, 0.0, 1.0)
AWAY = (0.0, 0.0, -1.0)
# Forty distinct colours: an entry's index is its first channel over six.
PALETTE = tuple((index * 6, 255 - index * 5, (index * 37) % 256) for index in range(40))
BASE = (200, 100, 50)
RAMP4 = (0, 1, 2, 3)
FULL = 255
PATTERNS = tuple(name for name in shading.PATTERNS if name != "off")

# The approved tiles, rows top to bottom and columns left to right.
ORDERED2 = ((0, 2), (3, 1))
ORDERED4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
ORDERED8 = (
    (0, 32, 8, 40, 2, 34, 10, 42),
    (48, 16, 56, 24, 50, 18, 58, 26),
    (12, 44, 4, 36, 14, 46, 6, 38),
    (60, 28, 52, 20, 62, 30, 54, 22),
    (3, 35, 11, 43, 1, 33, 9, 41),
    (51, 19, 59, 27, 49, 17, 57, 25),
    (15, 47, 7, 39, 13, 45, 5, 37),
    (63, 31, 55, 23, 61, 29, 53, 21),
)
CLUSTERED4 = ((12, 5, 6, 13), (4, 0, 1, 7), (11, 3, 2, 8), (15, 10, 9, 14))
DIAGONAL4 = ((0, 4, 8, 12), (5, 9, 13, 1), (10, 14, 2, 6), (15, 3, 7, 11))
SHUFFLED8 = (
    (22, 15, 25, 10, 34, 61, 60, 30),
    (33, 42, 40, 21, 13, 0, 47, 12),
    (17, 4, 46, 38, 50, 6, 2, 29),
    (37, 51, 11, 9, 18, 62, 32, 20),
    (28, 19, 59, 5, 43, 49, 52, 26),
    (1, 58, 39, 44, 41, 45, 48, 8),
    (53, 23, 24, 31, 16, 57, 56, 14),
    (55, 54, 36, 63, 7, 27, 3, 35),
)
EXPECTED = {
    "ordered2": ORDERED2,
    "ordered4": ORDERED4,
    "ordered8": ORDERED8,
    "clustered4": CLUSTERED4,
    "diagonal4": DIAGONAL4,
    "shuffled8": SHUFFLED8,
}


def response(**changes):
    return dataclasses.replace(DEFAULT, **changes)


# The tiles


def test_the_tile_data_is_pinned_exactly_for_every_pattern():
    assert tuple(dither.TILES) == PATTERNS == tuple(EXPECTED)
    # Every pattern the settings name, and only those, has a tile.
    assert ("off", *dither.TILES) == shading.PATTERNS
    for name, rows in EXPECTED.items():
        assert dither.TILES[name] == rows


@pytest.mark.parametrize("name", PATTERNS)
def test_every_tile_holds_each_rank_exactly_once(name):
    ranks = sorted(rank for row in dither.TILES[name] for rank in row)
    size = len(dither.TILES[name]) * len(dither.TILES[name][0])
    assert ranks == list(range(size))


def test_the_ordered_tiles_follow_the_block_recursion():
    tile = np.zeros((1, 1), dtype=int)
    for name in ("ordered2", "ordered4", "ordered8"):
        tile = np.block([[4 * tile, 4 * tile + 2], [4 * tile + 3, 4 * tile + 1]])
        assert dither.TILES[name] == tuple(tuple(row) for row in tile.tolist())


def test_the_diagonal_tile_ranks_four_times_the_diagonal_plus_the_row():
    for y in range(4):
        for x in range(4):
            assert dither.TILES["diagonal4"][y][x] == 4 * ((x + y) % 4) + y


def test_the_tile_table_is_read_only():
    with pytest.raises(TypeError):
        dither.TILES["ordered2"] = ((0,),)


# Thresholds


@pytest.mark.parametrize("name", PATTERNS)
def test_a_threshold_is_the_rank_plus_a_half_over_the_tile_area(name):
    tile = dither.TILES[name]
    height, width = len(tile), len(tile[0])
    corners = [(0, 0), (0, width - 1), (height - 1, 0), (height - 1, width - 1)]
    for y, x in corners:
        assert dither.thresholds(name, y, x) == (tile[y][x] + 0.5) / (width * height)
    rows, columns = np.indices((height, width))
    got = dither.thresholds(name, rows, columns)
    assert got.dtype == np.float64
    assert np.array_equal(got, (np.array(tile) + 0.5) / (width * height))
    assert ((0 < got) & (got < 1)).all()


def test_ordered4_thresholds_are_pinned_exactly():
    rows, columns = np.indices((4, 4))
    got = dither.thresholds("ordered4", rows, columns)
    assert (got * 32).tolist() == [
        [1, 17, 5, 21],
        [25, 9, 29, 13],
        [7, 23, 3, 19],
        [31, 15, 27, 11],
    ]


@pytest.mark.parametrize("name", PATTERNS)
def test_the_tile_wraps_by_its_own_width_and_height(name):
    tile = dither.TILES[name]
    height, width = len(tile), len(tile[0])
    rows, columns = np.indices((height, width))
    base = dither.thresholds(name, rows, columns)
    for turns_y, turns_x in ((1, 0), (0, 1), (3, 5), (100, 77)):
        shifted = dither.thresholds(
            name, rows + turns_y * height, columns + turns_x * width
        )
        assert np.array_equal(shifted, base)


@pytest.mark.parametrize("name", PATTERNS)
def test_a_cell_that_is_not_square_or_a_tile_multiple_keeps_the_tile_anchored(name):
    tile = np.array(dither.TILES[name])
    height, width = tile.shape
    # A 5-row by 11-column cell: no multiple of the tile either way.
    rows, columns = np.indices((5, 11))
    got = dither.thresholds(name, rows, columns)
    assert got.shape == (5, 11)
    for y in range(5):
        for x in range(11):
            expected = (tile[y % height][x % width] + 0.5) / tile.size
            assert got[y, x] == expected


def test_rows_and_columns_broadcast_and_a_scalar_cell_is_one_threshold():
    got = dither.thresholds("ordered4", np.arange(4)[:, np.newaxis], np.arange(4))
    assert got.shape == (4, 4)
    assert np.ndim(dither.thresholds("ordered4", 2, 3)) == 0


def test_a_cells_threshold_ignores_its_neighbours_batching_and_order():
    rng = np.random.default_rng(11)
    rows = rng.integers(0, 40, 200)
    columns = rng.integers(0, 40, 200)
    together = dither.thresholds("shuffled8", rows, columns)
    order = rng.permutation(200)
    shuffled = dither.thresholds("shuffled8", rows[order], columns[order])
    assert np.array_equal(shuffled, together[order])
    halves = np.concatenate(
        [
            dither.thresholds("shuffled8", rows[:70], columns[:70]),
            dither.thresholds("shuffled8", rows[70:], columns[70:]),
        ]
    )
    assert np.array_equal(halves, together)
    for index in (0, 99, 199):
        one = dither.thresholds("shuffled8", rows[index], columns[index])
        assert one == together[index]


def test_a_supersample_coordinate_is_not_a_cell_coordinate():
    # The caller supplies the output cell's row and column. Passing the
    # supersampled position instead gives a different pattern.
    rows, columns = np.indices((4, 4))
    cell = dither.thresholds("ordered4", rows, columns)
    super_ = dither.thresholds("ordered4", rows * 3 + 1, columns * 3 + 1)
    assert not np.array_equal(cell, super_)


def test_bad_cells_patterns_and_strengths_are_refused():
    with pytest.raises(ValueError, match="no thresholds"):
        dither.thresholds("off", 0, 0)
    for bad in ("ordered3", "Ordered4", None, 4, ["ordered4"]):
        with pytest.raises(ValueError, match="pattern"):
            dither.thresholds(bad, 0, 0)
    with pytest.raises(ValueError, match="rows"):
        dither.thresholds("ordered4", None, 0)
    with pytest.raises(ValueError, match="columns"):
        dither.thresholds("ordered4", 0, None)
    with pytest.raises(ValueError, match="integers"):
        dither.thresholds("ordered4", 0.0, 0)
    with pytest.raises(ValueError, match="negative"):
        dither.thresholds("ordered4", 0, -1)
    for bad in (-0.01, 1.01, math.nan, math.inf, -math.inf, True, "1", None):
        with pytest.raises(ValueError, match="strength"):
            dither.is_effective("ordered4", bad)
    for good in (0, 1, 0.5, np.float32(0.5), np.int64(1)):
        assert dither.check_strength(good) == float(good)


def test_a_dither_is_effective_only_with_a_pattern_and_a_positive_strength():
    assert dither.is_effective("ordered4", 0.001)
    assert dither.is_effective("shuffled8", 1)
    assert not dither.is_effective("off", 1)
    assert not dither.is_effective("ordered4", 0)
    assert not dither.is_effective("off", 0)


# The band coordinate


def reference_band(signal, bands, threshold, strength):
    return min(
        max(math.floor(bands * signal + strength * (0.5 - threshold)), 0), bands - 1
    )


@pytest.mark.parametrize("bands", [1, 2, 4, 22, 40])
def test_the_band_is_the_clamped_floor_of_the_perturbed_coordinate(bands):
    rng = np.random.default_rng(bands)
    signal = np.concatenate([rng.random(300), [0.0, 1.0, 0.5, 1 / 3]])
    for name in PATTERNS:
        rows, columns = rng.integers(0, 64, (2, len(signal)))
        threshold = dither.thresholds(name, rows, columns)
        for strength in (0.0, 0.3, 0.5, 1.0):
            got = dither.dithered_band(signal, bands, threshold, strength)
            expected = [
                reference_band(float(e), bands, float(t), strength)
                for e, t in zip(signal, threshold, strict=True)
            ]
            assert got.dtype == np.int64
            assert got.tolist() == expected


def test_a_band_boundary_flips_with_the_threshold_by_half_the_tile():
    # Four bands, signal exactly 0.5: the coordinate is exactly 2. A cell
    # whose threshold is below a half rounds up from the boundary and keeps 2;
    # the rest fall to 1, whatever the positive strength.
    for name in PATTERNS:
        tile = np.array(dither.TILES[name])
        rows, columns = np.indices(tile.shape)
        threshold = dither.thresholds(name, rows, columns)
        for strength in (0.25, 0.5, 1.0):
            got = dither.dithered_band(0.5, 4, threshold, strength)
            assert np.array_equal(got, np.where(tile < tile.size // 2, 2, 1))


def test_the_band_clamps_at_both_limits():
    low = dither.thresholds("ordered2", *np.indices((2, 2)))
    assert dither.dithered_band(0.0, 4, low, 1.0).tolist() == [[0, 0], [0, 0]]
    assert dither.dithered_band(1.0, 4, low, 1.0).tolist() == [[3, 3], [3, 3]]
    assert dither.dithered_band(0.0, 1, 0.9, 1.0) == 0
    assert dither.dithered_band(0.99, 4, 0.01, 1.0) == 3


def test_zero_strength_is_exactly_the_floor_of_the_coordinate():
    signal = np.random.default_rng(5).random(500)
    threshold = np.random.default_rng(6).random(500)
    assert np.array_equal(
        dither.dithered_band(signal, 22, threshold, 0.0), lighting.band_of(signal, 22)
    )


# Ramp dithering of a block


def entry_of(colour):
    """The palette index of `colour`; every test ramp entry is unscaled."""
    return PALETTE.index(tuple(int(value) for value in colour))


def shade_all(
    blocks,
    rows=None,
    columns=None,
    weights=None,
    normals=None,
    *,
    ramp=RAMP4,
    shade_range=(0, 99),
    by_mode=False,
    base=BASE,
    **extra,
):
    """The colour of every block, one row of `blocks` (each a list of sample
    shades) per block. Samples face the key unless `normals` says otherwise."""
    shades = np.array(blocks)
    weights = np.full(shades.shape, FULL) if weights is None else np.array(weights)
    if normals is None:
        normals = np.tile(TOWARD_KEY, (*shades.shape, 1))
    else:
        normals = np.array(normals, dtype=np.float64)
    changes = {key: extra.pop(key) for key in list(extra) if hasattr(DEFAULT, key)}
    return lighting.shade_blocks(
        np.tile(np.array(base, dtype=np.uint8), (len(shades), 1)),
        weights,
        shades,
        normals,
        ramp=ramp,
        palette=PALETTE,
        response=response(**changes),
        shade_range=shade_range,
        lights=LIGHTS,
        by_mode=by_mode,
        rows=rows,
        columns=columns,
        **extra,
    )


def cell(name, height=None, width=None):
    """The rows and columns of every pixel of a cell the size of the tile."""
    tile = dither.TILES[name]
    rows, columns = np.indices((height or len(tile), width or len(tile[0])))
    return rows.reshape(-1), columns.reshape(-1)


def entries(colours):
    return [entry_of(colour) for colour in colours]


def test_plain_bands_at_a_boundary_follow_the_ordered2_cell():
    rows, columns = cell("ordered2")
    # Shade 50 over [0, 99] is a signal of 0.5, exactly on the 2/1 boundary.
    for strength in (0.25, 0.5, 1.0):
        got = shade_all(
            [[50]] * 4, rows, columns, pattern="ordered2", strength=strength
        )
        # Thresholds .125, .625, .875, .375 across the cell, reading order.
        assert entries(got) == [2, 1, 1, 2]
    none = shade_all([[50]] * 4, rows, columns, pattern="ordered2", strength=0.0)
    assert entries(none) == [2, 2, 2, 2]


def test_an_intermediate_signal_needs_enough_strength_to_cross_a_boundary():
    rows, columns = cell("ordered2")
    # Shade 56 is a coordinate of 2.24; only threshold .875 at full strength
    # (-0.375) crosses below 2.
    got = shade_all([[56]] * 4, rows, columns, pattern="ordered2", strength=1.0)
    assert entries(got) == [2, 2, 1, 2]
    got = shade_all([[56]] * 4, rows, columns, pattern="ordered2", strength=0.5)
    assert entries(got) == [2, 2, 2, 2]


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
@pytest.mark.parametrize("name", PATTERNS)
def test_every_pattern_clamps_at_the_first_and_last_band(name, by_mode):
    rows, columns = cell(name)
    count = len(rows)
    for strength in (0.5, 1.0):
        low = shade_all(
            [[0]] * count,
            rows,
            columns,
            by_mode=by_mode,
            pattern=name,
            strength=strength,
        )
        high = shade_all(
            [[99]] * count,
            rows,
            columns,
            by_mode=by_mode,
            pattern=name,
            strength=strength,
        )
        assert set(entries(low)) == {0}
        assert set(entries(high)) == {3}


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
@pytest.mark.parametrize("name", PATTERNS)
def test_a_boundary_signal_splits_each_tile_in_half_for_every_pattern(name, by_mode):
    rows, columns = cell(name)
    tile = np.array(dither.TILES[name])
    for strength in (0.25, 1.0):
        got = shade_all(
            [[50]] * len(rows),
            rows,
            columns,
            by_mode=by_mode,
            pattern=name,
            strength=strength,
        )
        expected = np.where(tile.reshape(-1) < tile.size // 2, 2, 1)
        assert entries(got) == expected.tolist()


def test_mode_samples_share_the_cells_one_threshold():
    rows, columns = cell("ordered2")
    # Samples at signals .3 and .7: coordinates 1.2 and 2.8. Low thresholds
    # push them to bands 1 and 3, high ones to 0 and 2, and the plain signal
    # .5 breaks the tie by the nearer band centre: entry 1 of {1, 3} (centres
    # .375, .875), entry 2 of {0, 2} (centres .125, .625). The middle
    # thresholds leave bands 1 and 2, which tie to the lower index.
    got = shade_all([[30, 70]] * 4, rows, columns, by_mode=True, pattern="ordered2")
    assert entries(got) == [1, 1, 2, 1]
    undithered = shade_all([[30, 70]], by_mode=True)
    assert entries(undithered) == [1]


def test_repeated_entries_pool_their_votes_under_dither():
    rows, columns = cell("ordered2")
    # Entry 1 holds bands 1 and 2; the samples vote for bands 0, 1 and 2 at
    # every threshold of the cell, so entry 1 pools two votes.
    got = shade_all(
        [[10, 40, 60]] * 4,
        rows,
        columns,
        ramp=(0, 1, 1, 2),
        by_mode=True,
        pattern="ordered2",
    )
    assert entries(got) == [1, 1, 1, 1]


def test_a_tie_uses_the_unperturbed_signal_and_every_band_an_entry_holds():
    rows, columns = cell("ordered2")
    # Entry 0 holds bands 0 and 2 of (0, 1, 0, 2); the signal 0.545 is 0.08
    # from band 2's centre. Whatever the thresholds do to the two votes (one
    # for entry 0, one for entry 2), the tie is judged at the plain signal.
    got = shade_all(
        [[10, 99]] * 4,
        rows,
        columns,
        ramp=(0, 1, 0, 2),
        by_mode=True,
        pattern="ordered2",
        strength=0.0,
    )
    assert entries(got) == [0, 0, 0, 0]


def test_brightness_gain_still_comes_from_the_unperturbed_signal():
    rows, columns = cell("ordered2")
    for by_mode in (False, True):
        got = shade_all(
            [[56]] * 4,
            rows,
            columns,
            by_mode=by_mode,
            mode="both",
            pattern="ordered2",
            strength=1.0,
        )
        signal = lighting.plain_signal(
            np.full((1, 1), FULL), np.array([[56]]), None, DEFAULT, (0, 99)
        )
        gain = lighting.brightness_gain(signal, DEFAULT)
        chosen = [2, 2, 1, 2]
        expected = imageops.scale_srgb(
            np.array([PALETTE[index] for index in chosen], dtype=np.uint8),
            np.repeat(gain, 4),
        )
        assert np.array_equal(got, expected)


def test_dither_does_not_change_which_shade_clamps_first_in_a_long_ramp():
    ramp = tuple(range(40))
    rows, columns = cell("ordered4")
    count = len(rows)
    for by_mode in (False, True):
        kwargs = {"ramp": ramp, "shade_range": (190, 225), "by_mode": by_mode}
        results = {
            shade: shade_all(
                [[shade]] * count, rows, columns, pattern="ordered4", **kwargs
            )
            for shade in (189, 190, 225, 226, 255)
        }
        # Raw shade clamps first: nothing outside the range moves the band.
        assert np.array_equal(results[189], results[190])
        assert np.array_equal(results[225], results[226])
        assert np.array_equal(results[225], results[255])
        # The top of the range: e = 35/36, a coordinate of 38.89, and the
        # cell reaches only the last two bands from it.
        assert set(entries(results[255])) == {38, 39}
        assert set(entries(results[190])) == {0}


def test_dither_keeps_the_narrow_three_band_range_reaching_two_bands():
    rows, columns = cell("ordered4")
    count = len(rows)
    for by_mode in (False, True):
        for shade in (101, 102, 255):
            got = shade_all(
                [[shade]] * count,
                rows,
                columns,
                ramp=(0, 1, 2),
                shade_range=(100, 101),
                by_mode=by_mode,
                pattern="ordered4",
            )
            # e = .5, a coordinate of 1.5; a shift under .5 cannot reach 2.
            assert set(entries(got)) == {1}
        low = shade_all(
            [[100]] * count,
            rows,
            columns,
            ramp=(0, 1, 2),
            shade_range=(100, 101),
            by_mode=by_mode,
            pattern="ordered4",
        )
        assert set(entries(low)) == {0}


def reference_entries(
    blocks, weights, facing, ramp, lo, hi, thresholds, strength, by_mode, response
):
    """A plain-Python model of the dithered ramp choice: each block's entry."""
    count = len(ramp)
    key = response.key_strength
    chosen = []
    for shades, weight, toward, threshold in zip(
        blocks, weights, facing, thresholds, strict=True
    ):

        def signal(shade, term):
            form = (min(max(shade, lo), hi) - lo) / (hi - lo + 1)
            if not response.ambient_form:
                form = 1.0
            light = (1.0 - key - 0.0) - 0.0 + key * term
            return form * min(1.0, max(0.0, light))

        total = sum(weight)
        mean_shade = sum(w * s for w, s in zip(weight, shades, strict=True)) / total
        mean_term = sum(w * f for w, f in zip(weight, toward, strict=True)) / total
        plain = signal(mean_shade, mean_term)
        if not by_mode:
            chosen.append(ramp[reference_band(plain, count, threshold, strength)])
            continue
        votes = {}
        for w, s, f in zip(weight, shades, toward, strict=True):
            band = reference_band(signal(s, f), count, threshold, strength)
            if w > 0:
                votes[ramp[band]] = votes.get(ramp[band], 0) + w
        top = max(votes.values())
        tied = [entry for entry, number in votes.items() if number == top]

        chosen.append(
            min(tied, key=lambda entry: (centre_gap(entry, plain, ramp), entry))
        )
    return chosen


def centre_gap(entry, plain, ramp):
    """How far the unperturbed `plain` signal is from the nearest band centre of
    any band `entry` holds in `ramp`."""
    return min(
        abs(plain - (band + 0.5) / len(ramp))
        for band in range(len(ramp))
        if ramp[band] == entry
    )


RAMPS = [
    ((0, 1, 2, 3), (0, 99)),
    ((4, 5, 5, 6, 4), (84, 191)),
    (tuple(range(22)), (0, 21)),
    (tuple(range(40)), (190, 225)),
    ((7,), (0, 255)),
    ((0, 1, 2), (100, 101)),
]


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
@pytest.mark.parametrize("name", PATTERNS)
@pytest.mark.parametrize("strength", [0.25, 0.5, 1.0])
def test_dithered_ramps_match_a_plain_python_model_on_random_blocks(
    name, strength, by_mode
):
    rng = np.random.default_rng([len(name), int(strength * 100), by_mode])
    for ramp, (lo, hi) in RAMPS:
        for changes in ({}, {"key_strength": 0.5}, {"ambient_form": False}):
            blocks, count = 40, 5
            shades = rng.integers(max(0, lo - 20), min(256, hi + 20), (blocks, count))
            weights = rng.integers(0, 4, (blocks, count)) * 85
            weights[:, 0] = np.maximum(weights[:, 0], 85)
            toward = rng.integers(0, 2, (blocks, count))
            normals = np.where(toward[..., np.newaxis] == 1, TOWARD_KEY, AWAY)
            rows = rng.integers(0, 40, blocks)
            columns = rng.integers(0, 40, blocks)
            got = shade_all(
                shades.tolist(),
                rows,
                columns,
                weights=weights.tolist(),
                normals=normals,
                ramp=ramp,
                shade_range=(lo, hi),
                by_mode=by_mode,
                pattern=name,
                strength=strength,
                **changes,
            )
            expected = reference_entries(
                shades.tolist(),
                weights.tolist(),
                toward.tolist(),
                ramp,
                lo,
                hi,
                dither.thresholds(name, rows, columns).tolist(),
                strength,
                by_mode,
                response(**changes),
            )
            assert entries(got) == expected


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
def test_off_and_zero_strength_are_exactly_the_undithered_path(by_mode):
    rng = np.random.default_rng(21)
    for ramp, (lo, hi) in RAMPS:
        shades = rng.integers(0, 256, (80, 4))
        weights = rng.integers(0, 4, (80, 4)) * 85
        weights[:, 0] = np.maximum(weights[:, 0], 85)
        rows = rng.integers(0, 30, 80)
        columns = rng.integers(0, 30, 80)
        kwargs = {
            "weights": weights.tolist(),
            "ramp": ramp,
            "shade_range": (lo, hi),
            "by_mode": by_mode,
        }
        plain = shade_all(shades.tolist(), **kwargs)
        for name, strength in (("off", 1.0), ("off", 0.0), ("ordered8", 0.0)):
            got = shade_all(
                shades.tolist(),
                rows,
                columns,
                pattern=name,
                strength=strength,
                **kwargs,
            )
            assert np.array_equal(got, plain)
        # Neither a threshold nor a cell is read where nothing is dithered.
        assert np.array_equal(
            shade_all(shades.tolist(), pattern="off", **kwargs), plain
        )
        assert np.array_equal(
            shade_all(shades.tolist(), pattern="shuffled8", strength=0, **kwargs),
            plain,
        )


def test_zero_strength_keeps_the_exact_integer_boundary_and_tie_arithmetic():
    # 22 bands over [0, 21], shade 15: the integer path gives band 15, but
    # floor(22 * (15 / 22)) is 14 in float64, so a float replacement drifts.
    ramp = tuple(range(22))
    assert math.floor(22 * (15 / 22)) == 14
    rows, columns = cell("ordered2")
    for by_mode in (False, True):
        for name, strength in (("off", 1.0), ("ordered2", 0.0), ("clustered4", 0)):
            got = shade_all(
                [[15]] * 4,
                rows,
                columns,
                ramp=ramp,
                shade_range=(0, 21),
                by_mode=by_mode,
                pattern=name,
                strength=strength,
            )
            assert entries(got) == [15] * 4
    # The legacy tie: shades 10 and 90 over four bands, signal exactly .5.
    for by_mode in (True,):
        got = shade_all(
            [[10, 90]],
            rows[:1],
            columns[:1],
            ramp=(5, 2, 4, 1),
            by_mode=by_mode,
            pattern="ordered2",
            strength=0.0,
        )
        assert entries(got) == [1]


def test_dither_applies_only_to_ramp_and_both_with_a_ramp():
    for mode in ("brightness", "neither"):
        got = shade_all([[50], [10], [90]], pattern="ordered4", strength=1.0, mode=mode)
        assert np.array_equal(got, shade_all([[50], [10], [90]], mode=mode))
    # A material with no ramp keeps its base colour (and is scaled), in every
    # mode, and so reads no cell either.
    for mode in ("ramp", "brightness", "both", "neither"):
        got = shade_all(
            [[50], [10]], ramp=None, pattern="ordered4", strength=1.0, mode=mode
        )
        assert np.array_equal(got, shade_all([[50], [10]], ramp=None, mode=mode))


def test_an_effective_dither_needs_one_cell_for_each_block():
    for rows, columns in ((None, None), ([0, 1], None), (None, [0, 1])):
        with pytest.raises(ValueError, match="output cell"):
            shade_all([[50], [50]], rows, columns, pattern="ordered2")
    with pytest.raises(ValueError, match="one cell for each"):
        shade_all([[50], [50]], [0], [0], pattern="ordered2")
    with pytest.raises(ValueError, match="one cell for each"):
        shade_all([[50], [50]], [[0, 1]], [[0, 1]], pattern="ordered2")
    with pytest.raises(ValueError, match="pattern"):
        shade_all([[50]], [0], [0], pattern="bayer")
    with pytest.raises(ValueError, match="strength"):
        shade_all([[50]], [0], [0], pattern="ordered2", strength=1.5)


def test_a_cells_result_ignores_the_order_and_batching_of_the_blocks():
    rng = np.random.default_rng(31)
    count = 120
    shades = rng.integers(0, 100, (count, 3))
    rows = rng.integers(0, 17, count)
    columns = rng.integers(0, 23, count)
    kwargs = {"pattern": "shuffled8", "strength": 1.0, "by_mode": True}
    together = shade_all(shades.tolist(), rows, columns, **kwargs)
    order = rng.permutation(count)
    shuffled = shade_all(shades[order].tolist(), rows[order], columns[order], **kwargs)
    assert np.array_equal(shuffled, together[order])
    halves = np.concatenate(
        [
            shade_all(shades[:50].tolist(), rows[:50], columns[:50], **kwargs),
            shade_all(shades[50:].tolist(), rows[50:], columns[50:], **kwargs),
        ]
    )
    assert np.array_equal(halves, together)


def test_dither_leaves_inputs_unchanged_and_repeats():
    shades = np.array([[10, 90], [50, 56]])
    weights = np.full(shades.shape, FULL)
    normals = np.tile(TOWARD_KEY, (2, 2, 1))
    base = np.tile(np.array(BASE, dtype=np.uint8), (2, 1))
    rows, columns = np.array([0, 1]), np.array([2, 3])
    copies = [array.copy() for array in (shades, weights, normals, base, rows, columns)]

    def run():
        return lighting.shade_blocks(
            base,
            weights,
            shades,
            normals,
            ramp=RAMP4,
            palette=PALETTE,
            response=response(mode="both"),
            shade_range=(0, 99),
            lights=LIGHTS,
            by_mode=True,
            pattern="clustered4",
            strength=0.75,
            rows=rows,
            columns=columns,
        )

    first = run()
    assert np.array_equal(first, run())
    for array, copy in zip(
        (shades, weights, normals, base, rows, columns), copies, strict=True
    ):
        assert np.array_equal(array, copy)
    assert first is not base


# Snap


def oklab(colour):
    return imageops._oklab(np.array([colour], dtype=np.uint8))[0]


def reference_snap(colour, target, threshold, strength):
    """A one-pixel plain-Python model of the two-nearest snap."""
    distinct = list(dict.fromkeys(tuple(int(c) for c in row) for row in target))
    desired = oklab(colour)
    labs = [oklab(entry) for entry in distinct]

    def squared(lab):
        difference = desired - lab
        return float(
            difference[0] * difference[0]
            + difference[1] * difference[1]
            + difference[2] * difference[2]
        )

    ranked = sorted(
        range(len(distinct)), key=lambda index: (squared(labs[index]), index)
    )
    if len(distinct) == 1 or strength == 0 or threshold is None:
        return distinct[ranked[0]]
    p0, p1 = labs[ranked[0]], labs[ranked[1]]
    line = p1 - p0
    along = float(
        (desired - p0)[0] * line[0]
        + (desired - p0)[1] * line[1]
        + (desired - p0)[2] * line[2]
    )
    length = float(line[0] * line[0] + line[1] * line[1] + line[2] * line[2])
    fraction = min(1.0, max(0.0, along / length))
    return distinct[ranked[1 if threshold < strength * fraction else 0]]


@pytest.fixture
def lab_is_rgb(monkeypatch):
    """Colours as their own coordinates, so distances and fractions are exact
    small integers and ratios: for ties and exact threshold equality."""
    monkeypatch.setattr(
        imageops, "_oklab", lambda rgb: np.asarray(rgb, dtype=np.float64)
    )


def snapped(colour, target, **kwargs):
    return tuple(
        int(c) for c in dither.snap(np.array([colour], np.uint8), target, **kwargs)[0]
    )


def cell_snap(colour, target, name, strength):
    """The colour of every pixel of one tile, as snap picks it."""
    rows, columns = cell(name)
    pixels = np.tile(np.array(colour, dtype=np.uint8), (len(rows), 1))
    got = dither.snap(
        pixels, target, pattern=name, strength=strength, rows=rows, columns=columns
    )
    return [tuple(int(c) for c in row) for row in got]


def test_snap_matches_a_plain_python_model_on_random_colours():
    rng = np.random.default_rng(41)
    for size in (1, 2, 3, 7, 12):
        target = rng.integers(0, 256, (size, 3)).astype(np.uint8)
        target[-1] = target[0]  # a repeated colour
        colours = rng.integers(0, 256, (60, 3)).astype(np.uint8)
        for name in PATTERNS:
            for strength in (0.0, 0.3, 1.0):
                rows = rng.integers(0, 32, 60)
                columns = rng.integers(0, 32, 60)
                got = dither.snap(
                    colours,
                    target,
                    pattern=name,
                    strength=strength,
                    rows=rows,
                    columns=columns,
                )
                threshold = dither.thresholds(name, rows, columns)
                for index in range(60):
                    expected = reference_snap(
                        colours[index], target, float(threshold[index]), strength
                    )
                    assert tuple(got[index].tolist()) == expected


def test_snap_chooses_the_second_nearest_not_the_best_partner():
    target = [[207, 21, 45], [60, 46, 205], [222, 149, 10], [24, 85, 110]]
    desired = [159, 122, 67]
    # In OKLab the nearest is target 2 and the second nearest target 0 (the
    # fraction is about .379), but target 3 makes a closer segment with it.
    labs = [oklab(entry) for entry in target]
    near = sorted(
        range(4), key=lambda i: float(((oklab(desired) - labs[i]) ** 2).sum())
    )
    assert near[:2] == [2, 0]

    def segment_distance(partner):
        line = labs[partner] - labs[2]
        f = min(1.0, max(0.0, float((oklab(desired) - labs[2]) @ line / (line @ line))))
        return float(((oklab(desired) - (labs[2] + f * line)) ** 2).sum())

    assert segment_distance(3) < segment_distance(0)
    tile = np.array(dither.TILES["ordered4"]).reshape(-1)
    got = cell_snap(desired, target, "ordered4", 1.0)
    # f = .3792: thresholds (rank + .5) / 16 below it, ranks 0 to 5, take the
    # second nearest; the rest take the nearest. Target 3 is never chosen.
    assert got == [tuple(target[0]) if rank <= 5 else tuple(target[2]) for rank in tile]
    assert tuple(target[3]) not in got


def test_snap_projects_in_oklab_not_in_rgb():
    target = [[76, 35, 80], [11, 228, 169], [149, 62, 120], [48, 197, 121]]
    desired = [7, 65, 180]
    p0, p1 = np.array(target[0], float), np.array(target[2], float)
    rgb = np.array(desired, float)
    rgb_fraction = (rgb - p0) @ (p1 - p0) / ((p1 - p0) @ (p1 - p0))
    assert rgb_fraction < 0  # behind the nearest in RGB: clamps to 0
    tile = np.array(dither.TILES["ordered4"]).reshape(-1)
    got = cell_snap(desired, target, "ordered4", 1.0)
    # The OKLab fraction is about .2665: ranks 0 to 3 take the second nearest
    # (threshold under .2665); an RGB projection would take it nowhere.
    assert got == [tuple(target[2]) if rank <= 3 else tuple(target[0]) for rank in tile]


def test_ties_for_the_nearest_and_for_the_second_go_to_the_earlier_target(lab_is_rgb):
    a, b, c, d = (0, 0, 0), (32, 0, 0), (0, 32, 0), (16, 0, 0)
    desired = (16, 16, 0)
    # d is 16 from a, b and c? Distances from (16, 16, 0): a, b, c are all 22.6
    # away: a three-way tie; (16, 0, 0) is only 16 away.
    assert snapped(desired, [a, b, c], strength=0.0) == a
    assert snapped(desired, [c, b, a]) == c
    assert snapped(desired, [b, a, c]) == b
    # With a nearer fourth colour the tie of the others is for second place;
    # the earlier of them is the second nearest in each order.
    for order, second in (([d, a, b, c], a), ([d, c, b, a], c), ([d, b, a, c], b)):
        got = cell_snap(desired, order, "ordered4", 1.0)
        assert set(got) <= {d, second}
        assert d in got


def test_equal_distance_gives_a_fraction_of_a_half_and_equality_keeps_the_nearest(
    lab_is_rgb,
):
    a, b = (0, 0, 0), (32, 0, 0)
    middle = (16, 0, 0)
    tile = np.array(dither.TILES["ordered4"]).reshape(-1)
    # f is exactly 1/2, the largest a true nearest allows. At full strength
    # a pixel takes the second colour when its threshold is under 1/2.
    assert [c == b for c in cell_snap(middle, [a, b], "ordered4", 1.0)] == [
        bool(rank < 8) for rank in tile
    ]
    # Reversed target order moves the tie, and so which colour is "nearest".
    assert cell_snap(middle, [b, a], "ordered4", 1.0) == [
        a if rank < 8 else b for rank in tile
    ]


def test_threshold_equal_to_strength_times_fraction_chooses_the_nearest(lab_is_rgb):
    a, b = (0, 0, 0), (32, 0, 0)
    tile = np.array(dither.TILES["ordered4"]).reshape(-1)
    # Thresholds are (2 rank + 1) / 32 in a 4x4 tile. d = 5 gives f = 5/32,
    # exactly rank 2's threshold: ranks 0 and 1 are below it and take b; rank
    # 2 is equal and keeps a.
    got = cell_snap((5, 0, 0), [a, b], "ordered4", 1.0)
    assert got == [b if rank < 2 else a for rank in tile]
    # The same with strength 1/2 and d = 10: f = 10/32, strength * f = 5/32.
    got = cell_snap((10, 0, 0), [a, b], "ordered4", 0.5)
    assert got == [b if rank < 2 else a for rank in tile]


def test_the_fraction_clamps_at_zero_behind_the_nearest(lab_is_rgb):
    a, b = (10, 0, 0), (20, 0, 0)
    # d = 0 projects behind a: f = -1 clamps to 0, so no threshold is under it.
    assert set(cell_snap((0, 0, 0), [a, b], "ordered4", 1.0)) == {a}


def test_the_strength_endpoints(lab_is_rgb):
    a, b = (0, 0, 0), (32, 0, 0)
    middle = (16, 0, 0)
    assert set(cell_snap(middle, [a, b], "ordered4", 0.0)) == {a}
    tile = np.array(dither.TILES["ordered4"]).reshape(-1)
    full = cell_snap(middle, [a, b], "ordered4", 1.0)
    half = cell_snap(middle, [a, b], "ordered4", 0.5)
    # f = 1/2: strength 1/2 leaves ranks whose threshold is under 1/4.
    assert full == [b if rank < 8 else a for rank in tile]
    assert half == [b if rank < 4 else a for rank in tile]


def test_off_or_zero_strength_selects_only_the_nearest_with_the_same_order_ties():
    rng = np.random.default_rng(51)
    target = rng.integers(0, 256, (9, 3)).astype(np.uint8)
    colours = rng.integers(0, 256, (400, 3)).astype(np.uint8)
    rows = rng.integers(0, 16, 400)
    columns = rng.integers(0, 16, 400)
    pixels = np.concatenate([colours, np.full((400, 1), 255, np.uint8)], axis=1)
    mapped = imageops.map_palette(pixels[np.newaxis], target.tolist())[0, :, :3]
    assert np.array_equal(dither.snap(colours, target), mapped)
    for name, strength in (("off", 1.0), ("ordered8", 0.0)):
        got = dither.snap(
            colours, target, pattern=name, strength=strength, rows=rows, columns=columns
        )
        assert np.array_equal(got, mapped)


def test_a_one_colour_target_is_constant():
    colours = np.random.default_rng(1).integers(0, 256, (50, 3)).astype(np.uint8)
    rows = np.arange(50)
    for name in PATTERNS:
        got = dither.snap(
            colours, [[9, 8, 7]], pattern=name, strength=1.0, rows=rows, columns=rows
        )
        assert (got == [9, 8, 7]).all()
    repeated = dither.snap(
        colours, [[9, 8, 7]] * 3, pattern="ordered4", rows=rows, columns=rows
    )
    assert (repeated == [9, 8, 7]).all()


def test_every_selected_colour_belongs_to_the_target_and_is_not_a_blend():
    rng = np.random.default_rng(61)
    target = rng.integers(0, 256, (6, 3)).astype(np.uint8)
    colours = rng.integers(0, 256, (500, 3)).astype(np.uint8)
    rows = rng.integers(0, 64, 500)
    columns = rng.integers(0, 64, 500)
    members = {tuple(row) for row in target.tolist()}
    for name in PATTERNS:
        got = dither.snap(
            colours, target, pattern=name, strength=1.0, rows=rows, columns=columns
        )
        assert got.dtype == np.uint8
        assert {tuple(row) for row in got.tolist()} <= members


def test_repeated_targets_deduplicate_by_first_occurrence_in_order(lab_is_rgb):
    a, b, c = (0, 0, 0), (32, 0, 0), (0, 32, 0)
    desired = (16, 16, 0)
    # a, b and c tie; the first occurrence order decides, however often a
    # colour repeats.
    assert snapped(desired, [b, a, b, c, a]) == b
    assert snapped(desired, [a, b, c, a, b]) == a
    # Repeating colours changes nothing but where each first appears.
    pattern = {"pattern": "ordered4", "strength": 1.0}
    rows, columns = cell("ordered4")
    pixels = np.tile(np.array(desired, np.uint8), (16, 1))
    plain = dither.snap(pixels, [b, a, c], rows=rows, columns=columns, **pattern)
    repeated = dither.snap(
        pixels, [b, a, b, a, c, c, b], rows=rows, columns=columns, **pattern
    )
    assert np.array_equal(plain, repeated)


def test_a_target_of_repeated_ramp_indices_has_distinct_colours_in_first_order():
    palette = [(10, 10, 10), (200, 20, 20), (20, 20, 200), (240, 240, 240)]
    target = dither.snap_target(palette, (2, 0, 2, 1, 0))
    assert target.dtype == np.uint8
    assert target.tolist() == [list(palette[i]) for i in (2, 0, 2, 1, 0)]
    colours = np.array([[15, 15, 150], [200, 30, 30]], dtype=np.uint8)
    deduplicated = dither.snap_target(palette, (2, 0, 1))
    assert np.array_equal(
        dither.snap(colours, target), dither.snap(colours, deduplicated)
    )


def test_a_missing_ramp_targets_the_whole_palette_in_palette_order():
    palette = [(10, 10, 10), (200, 20, 20), (20, 20, 200), (240, 240, 240)]
    assert dither.snap_target(palette).tolist() == [list(c) for c in palette]
    assert dither.snap_target(palette, (3, 1)).tolist() == [
        list(palette[3]),
        list(palette[1]),
    ]
    for bad in ((), (4,), (-1,), (0.5,), [[0]]):
        with pytest.raises(ValueError, match="ramp"):
            dither.snap_target(palette, bad)


def test_snap_refuses_bad_inputs():
    pixels = np.zeros((2, 3), dtype=np.uint8)
    for bad in ([], [[1, 2]], [[256, 0, 0]], [[-1, 0, 0]], [[0.5, 0, 0]], [1, 2, 3]):
        with pytest.raises(ValueError, match="target"):
            dither.snap(pixels, bad)
    for bad in (np.zeros((2, 3), dtype=np.int64), np.zeros((2, 4), dtype=np.uint8)):
        with pytest.raises(ValueError, match="rgb"):
            dither.snap(bad, [[0, 0, 0]])
    with pytest.raises(ValueError, match="output cell"):
        dither.snap(pixels, [[0, 0, 0], [9, 9, 9]], pattern="ordered4")
    with pytest.raises(ValueError, match="broadcast"):
        dither.snap(
            pixels,
            [[0, 0, 0], [9, 9, 9]],
            pattern="ordered4",
            rows=np.zeros(3, int),
            columns=np.zeros(3, int),
        )
    with pytest.raises(ValueError, match="strength"):
        dither.snap(pixels, [[0, 0, 0]], pattern="ordered4", strength=2)


def test_snap_works_on_any_leading_shape_and_leaves_its_inputs_alone():
    rng = np.random.default_rng(71)
    target = rng.integers(0, 256, (5, 3)).astype(np.uint8)
    image = rng.integers(0, 256, (6, 7, 3)).astype(np.uint8)
    rows, columns = np.indices((6, 7))
    copies = image.copy(), target.copy(), rows.copy(), columns.copy()
    got = dither.snap(
        image, target, pattern="diagonal4", strength=0.8, rows=rows, columns=columns
    )
    flat = dither.snap(
        image.reshape(-1, 3),
        target,
        pattern="diagonal4",
        strength=0.8,
        rows=rows.reshape(-1),
        columns=columns.reshape(-1),
    )
    assert got.shape == image.shape
    assert np.array_equal(got.reshape(-1, 3), flat)
    assert got is not image
    for array, copy in zip((image, target, rows, columns), copies, strict=True):
        assert np.array_equal(array, copy)
    again = dither.snap(
        image, target, pattern="diagonal4", strength=0.8, rows=rows, columns=columns
    )
    assert np.array_equal(got, again)
    assert dither.snap(np.zeros((0, 3), np.uint8), target).shape == (0, 3)


def test_a_pixels_snap_does_not_depend_on_batching_or_order(monkeypatch):
    rng = np.random.default_rng(81)
    target = rng.integers(0, 256, (11, 3)).astype(np.uint8)
    colours = rng.integers(0, 256, (333, 3)).astype(np.uint8)
    rows = rng.integers(0, 50, 333)
    columns = rng.integers(0, 50, 333)
    kwargs = {"pattern": "shuffled8", "strength": 0.9}
    together = dither.snap(colours, target, rows=rows, columns=columns, **kwargs)
    monkeypatch.setattr(dither, "_SNAP_BATCH", 7)
    small = dither.snap(colours, target, rows=rows, columns=columns, **kwargs)
    assert np.array_equal(together, small)
    order = rng.permutation(333)
    shuffled = dither.snap(
        colours[order], target, rows=rows[order], columns=columns[order], **kwargs
    )
    assert np.array_equal(shuffled, together[order])


def test_snap_work_memory_is_bounded_by_a_batch_not_pixels_times_colours():
    rng = np.random.default_rng(91)
    target = rng.integers(0, 256, (255, 3)).astype(np.uint8)
    image = rng.integers(0, 256, (400, 500, 3)).astype(np.uint8)
    rows, columns = np.indices(image.shape[:2])
    tracemalloc.start()
    try:
        dither.snap(
            image, target, pattern="ordered8", strength=1.0, rows=rows, columns=columns
        )
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    # 200 000 pixels by 255 colours of float64 would be 408 MB; the inputs,
    # coordinates and thresholds here are about 12 MB.
    assert peak < 64 * 2**20


# The call sites: where each snap runs


PAL = [(16, 16, 16), (200, 40, 40), (40, 40, 200), (240, 240, 240)]


def test_own_ramp_snap_takes_the_post_brightness_bytes_in_ramp_order():
    ramp = (1, 0, 2)
    target = dither.snap_target(PAL, ramp)
    assert target.tolist() == [list(PAL[1]), list(PAL[0]), list(PAL[2])]
    shaded = imageops.scale_srgb(np.array([PAL[1]], dtype=np.uint8), np.array([0.6]))
    assert tuple(shaded[0]) not in PAL  # off the palette after brightness
    got = dither.snap(shaded, target)
    assert tuple(got[0]) in {PAL[i] for i in ramp}
    # The same bytes snapped to the whole palette may choose a colour the
    # layer's ramp does not hold: the target, not the call, is what differs.
    whole = dither.snap(
        np.array([[60, 60, 60]], np.uint8), dither.snap_target(PAL, (1, 2))
    )
    assert tuple(whole[0]) in {PAL[1], PAL[2]}
    assert (
        tuple(
            dither.snap(np.array([[60, 60, 60]], np.uint8), dither.snap_target(PAL))[0]
        )
        == PAL[0]
    )


def test_a_post_composite_snap_differs_from_snapping_each_layer_first():
    front = np.array([[PAL[1]]], np.uint8)
    back = np.array([[PAL[2]]], np.uint8)
    weight = np.array([[1]])
    heavy = np.array([[3]])
    whole = dither.snap_target(PAL)
    composed = imageops.composite(front, weight, back, heavy)
    assert tuple(composed[0, 0]) not in PAL
    # A per-layer snap followed by composition can leave the allowed set.
    each = imageops.composite(
        dither.snap(front, whole), weight, dither.snap(back, whole), heavy
    )
    assert tuple(each[0, 0]) not in PAL
    # A final whole-palette snap of the composite returns to it.
    final = dither.snap(composed, whole)
    assert tuple(final[0, 0]) in PAL
    # The input the snap sees decides the answer: bytes before composition
    # are the layers' own, bytes after it are the mix.
    assert not np.array_equal(final, dither.snap(front, whole))
