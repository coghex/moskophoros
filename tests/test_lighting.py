"""The pure lighting and four-mode colour operations (shading design
contract 3; D-5, D-14, D-15, D-23 to D-26, D-36, D-40): exact small fixtures
on addressed sample arrays, with no Blender, file or command."""

import dataclasses
import math
import tracemalloc
import warnings

import numpy as np
import pytest

from moskophoros import imageops, lighting, shading, views
from moskophoros.shading_resolve import Look

DEFAULT = shading.settings_of({}).response
# Axis-aligned vectors keep every facing term exactly 0 or 1.
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


def response(**changes):
    return dataclasses.replace(DEFAULT, **changes)


# The key light at full strength on a normal that faces it: the continuous
# path with the light factor exactly 1 (ambient form on).
CONTINUOUS = {"key_strength": 1.0}


def shade(
    shades,
    weights=None,
    normals=None,
    *,
    ramp=RAMP4,
    shade_range=(0, 99),
    by_mode=False,
    base=BASE,
    lights=LIGHTS,
    **changes,
):
    """The colour of one block whose samples have `shades`, as a tuple.
    Samples face the key unless `normals` says otherwise."""
    shades = np.array([shades])
    weights = np.full(shades.shape, FULL) if weights is None else np.array([weights])
    if normals is None:
        normals = np.tile(TOWARD_KEY, (1, shades.shape[1], 1))
    else:
        normals = np.array([normals], dtype=np.float64)
    result = lighting.shade_blocks(
        np.array([base], dtype=np.uint8),
        weights,
        shades,
        normals,
        ramp=ramp,
        palette=PALETTE,
        response=response(**changes),
        shade_range=shade_range,
        lights=lights,
        by_mode=by_mode,
    )
    return tuple(int(value) for value in result[0])


def decode(byte):
    channel = byte / 255
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def encode(linear):
    s = 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    return min(255, math.floor(255 * s + 0.5))


def scaled(colour, gain):
    """`colour` scaled in linear light by `gain`, from the sRGB definition."""
    return tuple(encode(decode(byte) * gain) for byte in colour)


# The sky and ground frame


def test_the_key_is_normalised_once_and_follows_the_camera_in_either_frame():
    for frame in ("camera", "world"):
        lights = lighting.light_vectors([-0.6, 0.7, 0.7], frame, (0, -1, -1), 0.25)
        assert lights.key == views.normalise([-0.6, 0.7, 0.7])
        assert math.isclose(math.hypot(*lights.key), 1.0, abs_tol=1e-15)
    unit = (0.0, 0.0, 1.0)
    assert lighting.light_vectors(unit, "camera").key == unit


@pytest.mark.parametrize("roll", [0.0, 0.25, 0.5, 1.0])
@pytest.mark.parametrize("direction", [(0, 0, -1), (0, -1, -1), (0, -1, 0)])
def test_the_camera_frame_sky_is_screen_up_whatever_the_view_or_roll(direction, roll):
    lights = lighting.light_vectors([0, 0, 1], "camera", direction, roll)
    assert lights.sky == (0.0, 1.0, 0.0)
    assert lights.ground == (0.0, -1.0, 0.0)
    assert lighting.light_vectors([0, 0, 1], "camera").sky == lights.sky


@pytest.mark.parametrize(
    ("direction", "roll", "sky"),
    [
        ((0, 0, -1), 0.0, (0.0, 1.0, 0.0)),  # level: up is screen up
        ((0, -1, 0), 0.0, (0.0, 0.0, 1.0)),  # straight down: toward the viewer
        ((0, 1, 0), 0.0, (0.0, 0.0, -1.0)),  # straight up: away from the viewer
        ((0, -1, -1), 0.0, (0.0, math.sqrt(0.5), math.sqrt(0.5))),  # 45 degrees
        ((0, -1, -1), 0.5, (math.sqrt(0.5), 0.0, math.sqrt(0.5))),  # rolled 90
        ((0, 0, -1), 0.5, (1.0, 0.0, 0.0)),
        ((0, 0, -1), 1.0, (0.0, -1.0, 0.0)),  # rolled upside down
    ],
)
def test_the_world_frame_sky_is_the_subjects_up_in_camera_coordinates(
    direction, roll, sky
):
    lights = lighting.light_vectors([0, 0, 1], "world", direction, roll)
    assert lights.sky == pytest.approx(sky, abs=1e-15)
    assert lights.ground == pytest.approx(tuple(-c for c in sky), abs=1e-15)
    assert math.isclose(math.hypot(*lights.sky), 1.0, abs_tol=1e-15)


def test_the_world_frame_is_the_basis_projection_of_subject_up():
    for direction, roll in [((0, -1, -1), 0.0), ((0, -1, -2), 0.3), ((0, 0, -1), -0.2)]:
        basis = views.subject_basis(direction, roll)
        sky = lighting.light_vectors([0, 0, 1], "world", direction, roll).sky
        assert sky == (basis.right[1], basis.up[1], 0.0 - basis.forward[1])


def test_the_world_frame_ignores_the_heading_and_so_every_subject_rotation():
    # A subject rotated about +Y leaves its Y components alone, and the basis
    # is measured from the heading: directions of one pitch share it.
    level = math.sqrt(0.5)
    skies = {
        lighting.light_vectors([0, 0, 1], "world", (x, -level, z), 0.1).sky
        for x, z in [(0, -level), (level, 0), (-level, 0), (0.5, -0.5 * math.sqrt(1.0))]
        if math.isclose(math.hypot(x, z), level)
    }
    assert len(skies) == 1


def test_orthographic_and_perspective_share_one_basis_so_a_distant_light_is_constant():
    for position in [(0, 0, 5), (3, 2, -4), (-1, 9, 0.5)]:
        camera = views.perspective((0, -1, -1), 0.25, position)
        sky = lighting.light_vectors([0, 0, 1], "world", (0, -1, -1), 0.25).sky
        assert sky == (
            camera.basis.right[1],
            camera.basis.up[1],
            0.0 - camera.basis.forward[1],
        )
    # Whatever the pixel, the facing term depends on its normal alone.
    normals = np.tile((0.0, 0.6, 0.8), (4, 5, 1))
    terms = lighting.facing(
        normals, lighting.light_vectors([0, 0, 1], "world", (0, -1, -1)).sky
    )
    assert np.ptp(terms) == 0


def test_a_bad_frame_or_a_world_frame_without_a_camera_is_refused():
    with pytest.raises(ValueError, match="frame"):
        lighting.light_vectors([0, 0, 1], "ground")
    with pytest.raises(ValueError, match="camera's direction"):
        lighting.light_vectors([0, 0, 1], "world")


# Facing terms


def test_a_facing_term_is_bounded_between_0_and_1():
    v = (-0.82269028759918, -0.1819861337355423, -0.5385737997878917)
    # The unit vector's dot product with itself rounds above 1.
    assert np.sum(np.array(v) * np.array(v)) > 1.0
    assert lighting.facing(np.array(v), v) == 1.0
    assert lighting.facing((0.0, 0.0, 1.0), (0.0, 0.0, -1.0)) == 0.0


def test_opposite_normals_split_the_sky_and_the_ground():
    up, down = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
    assert lighting.facing(up, LIGHTS.sky) == 1.0
    assert lighting.facing(up, LIGHTS.ground) == 0.0
    assert lighting.facing(down, LIGHTS.sky) == 0.0
    assert lighting.facing(down, LIGHTS.ground) == 1.0
    assert lighting.facing((1.0, 0.0, 0.0), LIGHTS.sky) == 0.0


def test_facing_scales_the_normal_to_unit_length_and_leaves_inputs_alone():
    normals = np.array([[0.0, 3.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.6, 0.8]])
    kept = normals.copy()
    terms = lighting.facing(normals, LIGHTS.sky)
    assert list(terms) == [1.0, 0.0, 0.6]
    assert np.array_equal(normals, kept)


def test_a_mean_normal_is_not_a_mean_of_facing_terms():
    # Opposite normals cancel when averaged, but half of the samples face the key.
    normals = [(0.0, 0.0, 1.0), (0.0, 0.0, -1.0)]
    mean_normal = np.mean(normals, axis=0)
    assert lighting.facing(mean_normal, LIGHTS.key) == 0.0
    assert lighting.facing(normals, LIGHTS.key).mean() == 0.5
    signal = lighting.plain_signal(
        [[FULL, FULL]],
        [[99, 99]],
        lighting.facing_terms(
            np.array([normals]),
            np.array([[FULL, FULL]]),
            LIGHTS,
            response(key_strength=1.0),
        ),
        response(key_strength=1.0, ambient_form=False),
        (0, 99),
    )
    assert signal[0] == 0.5


def test_a_zero_normal_or_a_missing_one_is_refused_only_where_it_matters():
    terms = response(key_strength=1.0)
    with pytest.raises(ValueError, match="normal that is not 0"):
        lighting.facing_terms(np.zeros((1, 1, 3)), np.array([[FULL]]), LIGHTS, terms)
    with pytest.raises(ValueError, match="normals"):
        lighting.facing_terms(None, np.array([[FULL]]), LIGHTS, terms)
    # Without weight a sample is never looked at, and without a strength
    # no normals are needed.
    odd = np.array([[[np.nan, np.inf, 0.0], [0.0, 0.0, 1.0]]])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        got = lighting.facing_terms(odd, np.array([[0, FULL]]), LIGHTS, terms)
    assert got[0, 1, 0] == 1.0 and not got[0, 0].any()
    assert lighting.facing_terms(None, np.array([[FULL]]), LIGHTS, DEFAULT) is None


# The light factor and the ambient form


def test_the_defaults_give_a_light_factor_of_one_and_a_signal_of_the_form_alone():
    assert lighting.light_factor(DEFAULT, 0.3, 0.2, 0.9) == 1.0
    signal = lighting.plain_signal([[FULL]], [[50]], None, DEFAULT, (0, 99))
    assert signal[0] == 0.5


@pytest.mark.parametrize(
    ("strengths", "terms", "expected"),
    [
        ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), 1.0),
        ((0.5, 0.0, 0.0), (0.0, 1.0, 1.0), 0.5),  # the key alone, unlit
        ((0.5, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0),
        ((0.0, 0.25, 0.0), (1.0, 0.0, 1.0), 0.75),  # sky alone, unlit
        ((0.0, 0.0, 0.25), (1.0, 1.0, 0.0), 0.75),  # ground alone, unlit
        ((0.5, 0.25, 0.25), (0.0, 0.0, 0.0), 0.0),  # total 1: no uniform light
        ((0.5, 0.25, 0.25), (1.0, 0.0, 0.0), 0.5),
        ((0.5, 0.25, 0.25), (0.5, 1.0, 0.0), 0.5),
        ((1.0, 0.0, 0.0), (0.25, 0.0, 0.0), 0.25),
    ],
)
def test_the_light_factor_spends_a_unit_budget(strengths, terms, expected):
    k, s, g = strengths
    light = lighting.light_factor(
        response(key_strength=k, sky_strength=s, ground_strength=g), *terms
    )
    assert light == expected


def test_the_light_factor_stays_within_0_and_1_against_rounding():
    # 1 − 0.1 − 0.2 − 0.7 is not exactly 0 in float64.
    spent = response(key_strength=0.1, sky_strength=0.2, ground_strength=0.7)
    assert lighting.light_factor(spent, 1.0, 1.0, 1.0) == 1.0
    assert lighting.light_factor(spent, 0.0, 0.0, 0.0) == 0.0


def test_the_form_clamps_the_shade_before_it_normalises():
    form = lighting.form_term([89, 90, 91, 140, 190, 191, 255], (90, 190), DEFAULT)
    assert form.tolist() == [
        0.0,
        0.0,
        1 / 101,
        50 / 101,
        100 / 101,
        100 / 101,
        100 / 101,
    ]


def test_ambient_bypass_sets_the_form_to_one():
    off = response(ambient_form=False)
    assert lighting.form_term([0, 50, 255], (0, 99), off).tolist() == [1.0, 1.0, 1.0]
    assert lighting.plain_signal([[FULL]], [[0]], None, off, (0, 99))[0] == 1.0


def test_the_signal_is_a_product_of_means_not_a_mean_of_products():
    # One sample is dark but faces the key, the other is bright but does not.
    key_only = response(key_strength=1.0)
    normals = np.array([[TOWARD_KEY, AWAY]])
    weight = np.array([[FULL, FULL]])
    terms = lighting.facing_terms(normals, weight, LIGHTS, key_only)
    # a(mean shade 49.5) = 0.495 and L(mean facing 0.5) = 0.5; the mean of
    # the per-sample products would be (0 · 1 + 0.99 · 0) / 2 = 0.
    signal = lighting.plain_signal(weight, [[0, 99]], terms, key_only, (0, 99))
    assert signal[0] == pytest.approx(0.2475, abs=1e-15)


def test_the_weights_of_the_layer_average_the_shade_and_each_term_separately():
    key_only = response(key_strength=1.0)
    weight = np.array([[3, 1]])
    terms = lighting.facing_terms(
        np.array([[TOWARD_KEY, AWAY]]), weight, LIGHTS, key_only
    )
    signal = lighting.plain_signal(weight, [[100, 0]], terms, key_only, (0, 99))
    # mean shade 75 → a = 0.75; mean key = 0.75
    assert signal[0] == pytest.approx(0.5625, abs=1e-15)


def test_a_block_with_no_weight_has_no_signal():
    with pytest.raises(ValueError, match="some weight"):
        lighting.plain_signal([[0, 0]], [[1, 2]], None, DEFAULT, (0, 99))


# Bands


@pytest.mark.parametrize(
    ("signal", "band"),
    [
        (-0.5, 0),
        (0.0, 0),
        (0.2499, 0),
        (0.25, 1),
        (0.5, 2),
        (0.9999, 3),
        (1.0, 3),
        (7.0, 3),
    ],
)
def test_the_band_is_the_clamped_floor_of_n_times_the_signal(signal, band):
    assert lighting.band_of(signal, 4) == band


def long_ramp():
    return tuple(range(40))


def bands(shades, *, by_mode, shade_range, ramp, **changes):
    """The entry each single-sample block takes, from its shade."""
    return [
        shade([s], ramp=ramp, shade_range=shade_range, by_mode=by_mode, **changes)
        for s in shades
    ]


# [190,225] over forty bands: below, at and above each endpoint.
LONG = [189, 190, 191, 207, 224, 225, 226, 255]
LONG_BANDS = [0, 0, 1, 18, 37, 38, 38, 38]


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
@pytest.mark.parametrize("changes", [{}, CONTINUOUS], ids=["legacy", "continuous"])
def test_forty_bands_over_190_to_225_clamp_with_no_jump_above_the_top(by_mode, changes):
    got = bands(
        LONG, by_mode=by_mode, shade_range=(190, 225), ramp=long_ramp(), **changes
    )
    assert got == [PALETTE[b] for b in LONG_BANDS]
    assert PALETTE[39] not in got


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
@pytest.mark.parametrize("changes", [{}, CONTINUOUS], ids=["legacy", "continuous"])
def test_three_bands_over_100_to_101_reach_only_the_first_two(by_mode, changes):
    got = bands(
        [99, 100, 101, 102, 255],
        by_mode=by_mode,
        shade_range=(100, 101),
        ramp=(0, 1, 2),
        **changes,
    )
    assert got == [PALETTE[b] for b in (0, 0, 1, 1, 1)]


def test_the_mean_is_clamped_in_the_plain_signal_and_each_sample_in_the_mode_vote():
    # Shades 100 and 255 over [190, 225]: the mean 177.5 clamps to the low end
    # (band 0); clamping each sample first would average to band 19.
    for changes in ({}, CONTINUOUS):
        plain = shade([100, 255], ramp=long_ramp(), shade_range=(190, 225), **changes)
        assert plain == PALETTE[0]
    form = lighting.form_term([100, 255], (190, 225), DEFAULT)
    assert lighting.band_of(form.mean(), 40) == 19
    # In mode each sample clamps and votes: bands 0 and 38 tie one vote each, and
    # the plain signal 0 breaks the tie toward the nearer centre, band 0.
    for changes in ({}, CONTINUOUS):
        voted = shade(
            [100, 255],
            ramp=long_ramp(),
            shade_range=(190, 225),
            by_mode=True,
            **changes,
        )
        assert voted == PALETTE[0]
    voted = shade(
        [120, 255, 255], ramp=long_ramp(), shade_range=(190, 225), by_mode=True
    )
    assert voted == PALETTE[38]


def test_the_exact_integer_path_is_kept_where_the_float_formula_would_differ():
    # 22 bands over [0, 21], shade 15: 15 · 22 // 22 = 15 exactly, but
    # floor(22 · (15 / 22)) is 14 in float64.
    ramp = tuple(range(22))
    assert math.floor(22 * (15 / 22)) == 14
    legacy = shade([15], ramp=ramp, shade_range=(0, 21))
    assert legacy == PALETTE[15]
    continuous = shade([15], ramp=ramp, shade_range=(0, 21), **CONTINUOUS)
    assert continuous == PALETTE[14]


def test_the_integer_path_runs_only_with_the_form_on_and_no_directional_strength():
    ramp = tuple(range(22))
    for changes in (
        {"ambient_form": False},
        {"key_strength": 0.1},
        {"sky_strength": 0.1},
        {"ground_strength": 0.1},
    ):
        got = shade([15], normals=[AWAY], ramp=ramp, shade_range=(0, 21), **changes)
        assert got in PALETTE
    assert shade([15], ramp=ramp, shade_range=(0, 21)) == PALETTE[15]


def test_legacy_kernels_match_map_ramps_on_random_blocks():
    rng = np.random.default_rng(7)
    factor, rows, columns = 3, 5, 6
    shape = (rows * factor, columns * factor)
    ramps = [(0, 1, 2, 3), (4, 5, 5, 6, 4), None, (7,), tuple(range(22))]
    lo_hi = [(0, 99), (84, 191), (0, 255), (190, 225), (0, 21)]
    pixels = rng.integers(0, 256, (*shape, 4), dtype=np.uint8)
    pixels[..., 3] = rng.integers(0, 4, shape) * 85
    identity = rng.integers(-1, len(ramps), shape)
    shades = rng.integers(0, 256, shape).astype(np.uint8)
    for by_mode in (False, True):
        expected, mapped = imageops.map_ramps(
            pixels,
            identity,
            shades,
            factor,
            ramps,
            PALETTE,
            84,
            191,
            by_mode=by_mode,
            ranges=lo_hi,
        )
        # The caller's ordinary colour, with the alpha the edge rule decides.
        base = np.zeros((rows, columns, 4), dtype=np.uint8)
        base[..., :3] = BASE
        base[..., 3] = imageops.block_alpha(pixels[..., 3], factor, "hard")
        looks = [Look(DEFAULT, bounds, 0.3, 0.25, 1.0) for bounds in lo_hi]
        got = lighting.shade_layer(
            base,
            identity,
            shades,
            None,
            pixels[..., 3].astype(np.int64),
            factor,
            ramps=ramps,
            palette=PALETTE,
            looks=looks,
            lights=LIGHTS,
            by_mode=by_mode,
        )
        assert mapped.any()
        assert np.array_equal(got[mapped], expected[mapped])
        # Everything else is the caller's ordinary look, alpha included.
        assert np.array_equal(got[~mapped], base[~mapped])


# The four modes


def gain_of(e, floor=0.3, ceiling=1.0):
    return floor + (ceiling - floor) * e


@pytest.mark.parametrize("changes", [{}, CONTINUOUS], ids=["legacy", "continuous"])
def test_the_four_modes_with_a_ramp_and_with_none(changes):
    # Shade 50 over [0, 99]: e = 0.5, band 2, gain 0.65.
    with_ramp = {
        "ramp": PALETTE[2],
        "brightness": scaled(PALETTE[3], 0.65),
        "both": scaled(PALETTE[2], 0.65),
        "neither": PALETTE[3],
    }
    without = {
        "ramp": BASE,
        "brightness": scaled(BASE, 0.65),
        "both": scaled(BASE, 0.65),
        "neither": BASE,
    }
    for mode in with_ramp:
        assert shade([50], mode=mode, **changes) == with_ramp[mode], mode
        assert shade([50], mode=mode, ramp=None, **changes) == without[mode], mode


def test_a_ramped_material_ignores_its_ordinary_colour_in_every_mode():
    for mode in ("ramp", "brightness", "both", "neither"):
        assert shade([50], mode=mode, base=(1, 2, 3)) == shade([50], mode=mode)


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
def test_brightness_and_neither_never_select_a_band(by_mode):
    low = shade([0], mode="neither", by_mode=by_mode)
    high = shade([99], mode="neither", by_mode=by_mode)
    assert low == high == PALETTE[3]
    assert shade([0], mode="brightness", by_mode=by_mode) == scaled(PALETTE[3], 0.3)


def test_the_mean_and_the_vote_differ_on_a_skewed_block():
    shades = [10, 90, 90, 90]
    for changes in ({}, CONTINUOUS):
        # mean 70 → band 2; three of four samples vote for band 3
        assert shade(shades, **changes) == PALETTE[2]
        assert shade(shades, by_mode=True, **changes) == PALETTE[3]


def test_a_mode_vote_uses_each_samples_own_light_factor():
    # Shade 99 everywhere; only the first sample faces the key, at strength 1,
    # so its signal is 0.99 (band 3) and the other's is 0 (band 0).
    normals = [TOWARD_KEY, AWAY]
    kwargs = {"normals": normals, "key_strength": 1.0}
    # Equal weights tie bands 0 and 3: the plain signal 0.495 is nearer band 0.
    assert shade([99, 99], by_mode=True, **kwargs) == PALETTE[0]
    # Three to one for the lit sample: it wins the vote, while the plain mean
    # (a · mean facing = 0.99 · 0.75, band 2) picks another entry.
    weights = [3 * FULL // 4, FULL // 4]
    assert shade([99, 99], weights, by_mode=True, **kwargs) == PALETTE[3]
    assert shade([99, 99], weights, **kwargs) == PALETTE[2]


def test_repeated_ramp_entries_pool_their_votes():
    # Entry 1 holds bands 1 and 2; one sample each in bands 0, 1 and 2.
    for changes in ({}, CONTINUOUS):
        got = shade([10, 35, 60], ramp=(0, 1, 1, 2), by_mode=True, **changes)
        assert got == PALETTE[1]


def test_a_tie_goes_to_the_entry_nearest_a_band_centre_then_the_lower_index():
    for changes in ({}, CONTINUOUS):
        # Bands 0 and 3 tie; the plain signal 0.545 is nearer centre 0.875.
        assert shade([10, 99], by_mode=True, **changes) == PALETTE[3]
        # Signal 0.5 is equally far from both centres: the lower palette
        # index wins, and band 3 holds palette entry 1 here.
        got = shade([10, 90], ramp=(5, 2, 4, 1), by_mode=True, **changes)
        assert got == PALETTE[1]
        got = shade([10, 90], ramp=(1, 2, 4, 5), by_mode=True, **changes)
        assert got == PALETTE[1]


def test_a_tie_counts_every_band_a_repeated_entry_holds_voted_for_or_not():
    # Entry 0 holds bands 0 and 2, entry 2 band 3. One vote each. The plain
    # signal 0.545 is 0.08 from band 2's centre 0.625, so entry 0 wins; only
    # counting its voted band 0 would put it 0.42 away and give entry 2 the tie.
    for changes in ({}, CONTINUOUS):
        got = shade([10, 99], ramp=(0, 1, 0, 2), by_mode=True, **changes)
        assert got == PALETTE[0]


def test_brightness_uses_the_plain_signal_after_the_voted_colour_is_chosen():
    shades = [10, 90, 90, 90]
    # Plain e = 0.7; the voted colour is entry 3.
    plain_gain = gain_of(0.7)
    got = shade(shades, mode="both", by_mode=True)
    assert got == scaled(PALETTE[3], plain_gain)
    # Not the voted band's own centre, nor the voters' signal.
    assert got != scaled(PALETTE[3], gain_of(0.875))
    assert got != scaled(PALETTE[3], gain_of(0.9))
    assert shade(shades, mode="brightness", by_mode=True) == got


def test_a_directional_light_changes_the_band_and_the_gain_together():
    # The sky alone at strength 0.5, on a normal facing away from it: L = 0.5.
    lit = {"sky_strength": 0.5}
    got = shade([99], normals=[(1.0, 0.0, 0.0)], mode="both", **lit)
    # a = 0.99, e = 0.495: band 1; gain 0.3 + 0.7 · 0.495
    assert got == scaled(PALETTE[1], 0.3 + 0.7 * 0.99 * 0.5)
    sky = shade([99], normals=[(0.0, 1.0, 0.0)], mode="both", **lit)
    assert sky == scaled(PALETTE[3], 0.3 + 0.7 * 0.99)


def test_ambient_bypass_lets_the_light_alone_pick_the_band():
    # No form: e = L whatever the shade.
    off = {"ambient_form": False, "key_strength": 0.5}
    assert shade([0], **off) == PALETTE[3]
    assert shade([0], normals=[AWAY], **off) == PALETTE[2]
    assert shade([99], normals=[AWAY], mode="both", **off) == scaled(
        PALETTE[2], gain_of(0.5)
    )


def test_a_block_with_no_ramp_vote_still_scales_by_the_signal():
    got = shade([50, 50], ramp=None, mode="both", by_mode=True)
    assert got == scaled(BASE, 0.65)


# Brightness


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
@pytest.mark.parametrize("shade_value", [101, 102, 200, 255])
def test_a_narrow_range_caps_the_gain_below_the_ceiling_unless_the_form_is_off(
    by_mode, shade_value
):
    # [100, 101], floor 0.3, ceiling 1: a = 1/2 at or above the high end.
    samples = [shade_value, shade_value]
    got = shade(
        samples, ramp=None, mode="brightness", shade_range=(100, 101), by_mode=by_mode
    )
    assert got == scaled(BASE, 0.65)
    bypass = shade(
        samples,
        ramp=None,
        mode="brightness",
        shade_range=(100, 101),
        by_mode=by_mode,
        ambient_form=False,
    )
    assert bypass == BASE
    signal = lighting.plain_signal([[FULL] * 2], [samples], None, DEFAULT, (100, 101))
    gain = lighting.brightness_gain(signal, DEFAULT)[0]
    assert gain == pytest.approx(0.65, abs=1e-15)


def test_the_gain_is_not_normalised_to_reach_the_ceiling():
    both = response(brightness_floor=0.2, brightness_ceiling=0.8)
    top = lighting.plain_signal([[FULL]], [[255]], None, both, (0, 99))
    assert lighting.brightness_gain(top, both)[0] == pytest.approx(0.2 + 0.6 * 0.99)


def test_equal_zero_and_unit_endpoints_give_a_constant_gain():
    for floor, ceiling in [(0.5, 0.5), (0.0, 0.0), (1.0, 1.0)]:
        end = {"brightness_floor": floor, "brightness_ceiling": ceiling}
        gains = {
            lighting.brightness_gain(np.array([e]), response(**end))[0]
            for e in (0.0, 0.3, 0.99)
        }
        assert gains == {floor}
    assert shade(
        [50], ramp=None, mode="brightness", brightness_floor=0.0, brightness_ceiling=0.0
    ) == (0, 0, 0)
    assert (
        shade(
            [50],
            ramp=None,
            mode="brightness",
            brightness_floor=1.0,
            brightness_ceiling=1.0,
        )
        == BASE
    )
    assert shade(
        [50], ramp=None, mode="brightness", brightness_floor=0.5, brightness_ceiling=0.5
    ) == scaled(BASE, 0.5)


def test_scaling_by_one_returns_every_byte_and_by_zero_returns_black():
    every = np.arange(256, dtype=np.uint8)
    rgb = np.stack([every, every[::-1], np.roll(every, 17)], axis=-1)
    assert np.array_equal(imageops.scale_srgb(rgb, np.ones(256)), rgb)
    assert not imageops.scale_srgb(rgb, np.zeros(256)).any()


def test_scaling_follows_the_srgb_definition_and_never_brightens():
    rng = np.random.default_rng(3)
    rgb = rng.integers(0, 256, (400, 3), dtype=np.uint8)
    gain = rng.random(400)
    got = imageops.scale_srgb(rgb, gain)
    expected = [scaled(tuple(map(int, c)), g) for c, g in zip(rgb, gain, strict=True)]
    assert got.tolist() == [list(e) for e in expected]
    assert (got <= rgb).all()
    assert got.dtype == np.uint8


@pytest.mark.parametrize("target", [1, 7, 100, 127, 128, 200, 254])
def test_bytes_round_half_up_at_the_encoding_boundary(target):
    # The linear value whose encoded 255 · s is exactly target + ½.
    s = (target + 0.5) / 255
    boundary = s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    white = np.array([[255, 255, 255]], dtype=np.uint8)
    below = imageops.scale_srgb(white, np.array([boundary * (1 - 1e-9)]))
    above = imageops.scale_srgb(white, np.array([boundary * (1 + 1e-9)]))
    assert below[0, 0] == target
    assert above[0, 0] == target + 1


def test_the_gain_is_kept_within_the_endpoints_against_rounding():
    for floor, ceiling in [(0.3, 1.0), (0.1, 0.7), (0.0, 1.0), (0.3, 0.9)]:
        r = response(brightness_floor=floor, brightness_ceiling=ceiling)
        gains = lighting.brightness_gain(np.array([0.0, 1 / 3, 0.5, 1.0]), r)
        assert ((gains >= floor) & (gains <= ceiling)).all()


# Layers: winners, exclusions and unchanged inputs


def layer_fixture():
    """One row of two 2×2 blocks. Block 0 votes for material 0 (weight 3 and
    3 against 1 and 1), whose losing neighbours are a bright, odd material 1;
    block 1 has no identity at all."""
    identity = np.array([[0, 0, -1, -1], [1, 1, -1, -1]])
    shades = np.array([[40, 60, 255, 255], [255, 255, 255, 255]], dtype=np.uint8)
    weights = np.array([[3, 3, 5, 5], [1, 1, 5, 5]])
    normals = np.zeros((2, 4, 3))
    normals[:, :2] = TOWARD_KEY
    normals[1, :2] = AWAY
    normals[:, 2:] = (0.0, 1.0, 0.0)
    return identity, shades, weights, normals


def layer(
    base, identity, shades, normals, weights, *, modes=("both", "ramp"), **kwargs
):
    looks = [
        Look(response(mode=mode, key_strength=1.0), (0, 99), 0.3, 0.25, 1.0)
        for mode in modes
    ]
    return lighting.shade_layer(
        base,
        identity,
        shades,
        normals,
        weights,
        2,
        ramps=[RAMP4, (10, 11)],
        palette=PALETTE,
        looks=looks,
        lights=LIGHTS,
        by_mode=kwargs.pop("by_mode", False),
        **kwargs,
    )


def test_only_the_winning_materials_visible_samples_shade_a_block():
    identity, shades, weights, normals = layer_fixture()
    base = np.full((1, 2, 4), 255, dtype=np.uint8)
    base[..., :3] = BASE
    got = layer(base, identity, shades, normals, weights)
    # Material 0 wins block 0 with shades 40 and 60 (mean 50) facing the key;
    # material 1's shade 255 facing away from it never counts.
    assert tuple(got[0, 0, :3]) == scaled(PALETTE[2], 0.65)
    alone = shade([40, 60, 0, 0], weights=[3, 3, 0, 0], mode="both", **CONTINUOUS)
    assert tuple(got[0, 0, :3]) == alone
    # A block without an identity keeps its ordinary look, in every mode.
    assert tuple(got[0, 1]) == (*BASE, 255)


def test_zero_weight_samples_and_zero_weight_blocks_add_nothing():
    identity, shades, _, normals = layer_fixture()
    base = np.full((1, 2, 4), 255, dtype=np.uint8)
    base[..., :3] = BASE
    # Block 0 keeps one sample of material 0; the rest, and all of block 1,
    # have no weight, and one weightless sample has no usable normal.
    weights = np.array([[0, 3, 0, 0], [0, 0, 0, 0]])
    normals[0, 0] = (np.nan, 0.0, 0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        got = layer(base, identity, shades, normals, weights)
    only = shade([60], weights=[3], mode="both", **CONTINUOUS)
    assert tuple(got[0, 0, :3]) == only
    assert tuple(got[0, 1]) == (*BASE, 255)


def test_a_weighted_block_with_no_identity_vote_keeps_its_ordinary_look_in_every_mode():
    identity = np.full((2, 2), -1)
    shades = np.full((2, 2), 90, dtype=np.uint8)
    weights = np.full((2, 2), 200)
    base = np.array([[[11, 22, 33, 255]]], dtype=np.uint8)
    for mode in ("ramp", "brightness", "both", "neither"):
        for by_mode in (False, True):
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                got = lighting.shade_layer(
                    base,
                    identity,
                    shades,
                    np.tile(TOWARD_KEY, (2, 2, 1)),
                    weights,
                    2,
                    ramps=[RAMP4],
                    palette=PALETTE,
                    looks=[Look(response(mode=mode), (0, 99), 0.3, 0.25, 1.0)],
                    lights=LIGHTS,
                    by_mode=by_mode,
                )
            assert got.tolist() == base.tolist()


def test_a_block_whose_base_alpha_is_zero_stays_unshaded():
    identity, shades, weights, normals = layer_fixture()
    base = np.zeros((1, 2, 4), dtype=np.uint8)
    got = layer(base, identity, shades, normals, weights)
    assert not got.any()


def test_ordinary_materials_scale_the_reduced_base_and_keep_its_alpha():
    identity = np.zeros((2, 2), dtype=np.int64)
    shades = np.full((2, 2), 50, dtype=np.uint8)
    base = np.array([[[*BASE, 180]]], dtype=np.uint8)
    got = lighting.shade_layer(
        base,
        identity,
        shades,
        None,
        np.full((2, 2), 90),
        2,
        ramps=[None],
        palette=None,
        looks=[Look(response(mode="brightness"), (0, 99), 0.3, 0.25, 1.0)],
        lights=LIGHTS,
        by_mode=False,
    )
    assert tuple(got[0, 0]) == (*scaled(BASE, 0.65), 180)


def test_pooled_identities_are_one_material():
    identity = np.array([[0, 1], [0, 1]])
    shades = np.full((2, 2), 50, dtype=np.uint8)
    base = np.full((1, 1, 4), 255, dtype=np.uint8)
    base[..., :3] = BASE
    look = Look(response(mode="ramp"), (0, 99), 0.3, 0.25, 1.0)
    got = lighting.shade_layer(
        base,
        identity,
        shades,
        None,
        np.full((2, 2), 9),
        2,
        ramps=[RAMP4, RAMP4],
        palette=PALETTE,
        looks=[look, look],
        lights=LIGHTS,
        by_mode=False,
        pool=[0, 0],
    )
    assert tuple(got[0, 0, :3]) == PALETTE[2]


def test_the_inputs_are_never_changed_and_calls_are_deterministic():
    identity, shades, weights, normals = layer_fixture()
    base = np.full((1, 2, 4), 255, dtype=np.uint8)
    base[..., :3] = BASE
    normals = normals.astype(np.float32)
    kept = [a.copy() for a in (identity, shades, weights, normals, base)]
    first = layer(base, identity, shades, normals, weights, by_mode=True)
    second = layer(base, identity, shades, normals, weights, by_mode=True)
    assert np.array_equal(first, second)
    for original, array in zip(
        kept, (identity, shades, weights, normals, base), strict=True
    ):
        assert np.array_equal(original, array)
    assert first is not base


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"shades": np.zeros((2, 4), dtype=np.int64)}, TypeError),
        ({"identity": np.full((2, 4), 9)}, ValueError),
        ({"weights": np.zeros((3, 4), dtype=np.int64)}, ValueError),
        ({"weights": np.zeros((2, 4))}, TypeError),
        ({"normals": np.zeros((2, 4, 2))}, ValueError),
    ],
)
def test_malformed_layers_are_refused(change, error):
    identity, shades, weights, normals = layer_fixture()
    arguments = {
        "identity": identity,
        "shades": shades,
        "weights": weights,
        "normals": normals,
    } | change
    base = np.full((1, 2, 4), 255, dtype=np.uint8)
    with pytest.raises(error):
        layer(base, **arguments)


def test_blocks_refuse_a_ramp_outside_the_palette_and_a_bad_range():
    with pytest.raises(ValueError, match="ramp"):
        shade([50], ramp=(0, 99))
    with pytest.raises(ValueError, match="ramp"):
        shade([50], ramp=())
    with pytest.raises(ValueError, match="shade range"):
        shade([50], shade_range=(5, 5))


def test_the_mode_vote_memory_is_bounded_by_batches_not_by_blocks_times_entries():
    size = 128
    rng = np.random.default_rng(5)
    palette = tuple((i, 255 - i, (i * 7) % 256) for i in range(255))
    shades = rng.integers(0, 256, (size, size)).astype(np.uint8)
    inputs = (
        np.full((size, size, 4), 255, dtype=np.uint8),
        np.zeros((size, size), dtype=np.int64),
        shades,
        None,
        np.full((size, size), FULL),
        1,
    )
    look = Look(response(ambient_form=False), (0, 254), 0.3, 0.25, 1.0)

    def peak(entries):
        tracemalloc.start()
        try:
            lighting.shade_layer(
                *inputs,
                ramps=[tuple(range(entries))],
                palette=palette,
                looks=[look],
                lights=LIGHTS,
                by_mode=True,
            )
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    # One dense block-by-entry array alone would be 33 MB here (16384 blocks,
    # 255 entries, 8 bytes); the vote works in batches of a fixed size.
    assert peak(255) < 16 * 2**20
