"""Mapping blocks onto material ramps, following design §Stylize (Material
ramps): pure tests on synthetic colour, identity and shade arrays."""

import weakref
from fractions import Fraction

import numpy as np
import pytest

from moskophoros import imageops, materials, stylize
from moskophoros.sampling import (
    BACKGROUND,
    IDENTITY,
    SHADE,
    FrameAddress,
    Identities,
    ImageFrame,
)

# Eight distinct entries; an entry's index is easy to read off its grey.
COLORS = tuple((index * 30, index * 30, index * 30) for index in range(8))
PLAIN = pytest.param(stylize.plain, False, id="plain")
MODE = pytest.param(stylize.mode, True, id="mode")
BOTH = [PLAIN, MODE]
NAMES = ("steel", "cloth", "skin")
IDENTITIES = Identities(NAMES)
NONE = IDENTITIES.no_identity


def library(ramps=None, default=None, entries=None):
    """A validated library; `entries` are material entries as JSON gives them."""
    document = {
        "schema": materials.SCHEMA,
        "ramps": {"metal": [1, 2, 3], "cloth": [4, 5]} if ramps is None else ramps,
        "materials": {} if entries is None else entries,
    }
    if default is not None:
        document["default"] = default
    return materials.validate_library(document, COLORS, source="test")


def address(i=0):
    return FrameAddress("s", "default", "walk", i, float(i))


def frame(alpha, identity, shade, i=0, metadata=None):
    """A frame of one block (2×2 pixels per block) from per-pixel lists."""
    size = int(np.sqrt(len(alpha)))
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[..., :3] = (200, 40, 90)
    pixels[..., 3] = np.reshape(alpha, (size, size))
    return ImageFrame(
        address(i),
        pixels,
        {} if metadata is None else metadata,
        {
            IDENTITY: np.reshape(identity, (size, size)).astype(np.int32),
            SHADE: np.reshape(shade, (size, size)).astype(np.uint8),
        },
    )


def run(look, one, factor=None, **options):
    """The reduced pixels of one frame; a lone block is a single pixel."""
    factor = factor or one.pixels.shape[0]
    options.setdefault("palette", COLORS)
    options.setdefault("identities", IDENTITIES)
    options.setdefault("shade_range", (0, 255))
    (result,) = look([one], factor, **options)
    return result.pixels


def uniform(shade, index=0):
    """A fully covered block whose pixels all have one identity and shade."""
    return frame([255] * 4, [index] * 4, [shade] * 4)


def mapped(look, shade, lib, shade_range=(0, 255), index=0):
    """The palette index a uniform block takes."""
    return entry(run(look, uniform(shade, index), library=lib, shade_range=shade_range))


def entry(pixels):
    """The palette index of a mapped single pixel, checking alpha 255."""
    assert pixels.shape == (1, 1, 4) and pixels[0, 0, 3] == 255
    return COLORS.index(tuple(int(c) for c in pixels[0, 0, :3]))


def ordinary(look, one, factor=None):
    factor = factor or one.pixels.shape[0]
    bare = ImageFrame(one.address, one.pixels, one.metadata)
    return look([bare], factor, palette=COLORS)[0].pixels


# Resolution


def test_a_name_resolves_to_its_own_entry_first():
    lib = library(
        default="cloth",
        entries={"steel": {"ramp": [7, 0]}, "skin": {"uses": "metal"}},
    )
    assert stylize.resolve(lib, "steel") == (7, 0)
    assert stylize.resolve(lib, "skin") == (1, 2, 3)


def test_an_ordinary_entry_resolves_to_the_ordinary_look_even_with_a_default():
    lib = library(default="cloth", entries={"steel": "ordinary"})
    assert stylize.resolve(lib, "steel") is None


def test_an_unmapped_name_takes_the_default_else_the_ordinary_look():
    assert stylize.resolve(library(default="cloth"), "steel") == (4, 5)
    assert stylize.resolve(library(), "steel") is None


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_each_resolution_reaches_the_block(look, by_mode):
    lib = library(
        default="cloth",
        entries={
            "steel": {"ramp": [7]},
            "cloth": {"uses": "metal"},
            "skin": "ordinary",
        },
    )
    assert mapped(look, 0, lib, index=0) == 7
    assert mapped(look, 0, lib, index=1) == 1
    skin = uniform(0, 2)
    np.testing.assert_array_equal(run(look, skin, library=lib), ordinary(look, skin))
    # A name with no entry and no default takes the ordinary look.
    bare = library(entries={"steel": {"ramp": [7]}})
    np.testing.assert_array_equal(
        run(look, uniform(0, 1), library=bare), ordinary(look, uniform(0, 1))
    )
    assert mapped(look, 0, library(default="metal"), index=1) == 1


# Bands


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_each_band_edge_of_an_even_split(look, by_mode):
    lib = library(ramps={"r": [1, 2, 3, 4]}, default="r")
    lo, hi = 40, 199  # four bands of 40, starting at 40, 80, 120 and 160
    edges = [(0, 0), (39, 0), (40, 0), (79, 0), (80, 1), (119, 1)]
    edges += [(120, 2), (159, 2), (160, 3), (199, 3), (200, 3), (255, 3)]
    for shade, band in edges:
        assert mapped(look, shade, lib, (lo, hi)) == band + 1, shade


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_an_uneven_split_follows_the_formula_for_every_shade(look, by_mode):
    lib = library(ramps={"r": [1, 2, 3]}, default="r")
    lo, hi = 40, 199  # 160 values over three bands
    for shade in range(256):
        band = (min(max(shade, lo), hi) - lo) * 3 // (hi - lo + 1)
        assert mapped(look, shade, lib, (lo, hi)) == band + 1, shade


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_the_full_range_and_the_narrowest_range(look, by_mode):
    lib = library(ramps={"r": [1, 2]}, default="r")
    full = [mapped(look, v, lib) for v in (0, 127, 128, 255)]
    assert full == [1, 1, 2, 2]
    narrow = [mapped(look, v, lib, (100, 101)) for v in (0, 99, 100, 101, 102, 255)]
    assert narrow == [1, 1, 1, 2, 2, 2]


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_ramp_longer_than_the_range_leaves_bands_unreachable(look, by_mode):
    # lo=100, hi=101, N=3: the top shade takes band (1·3)//2 = 1, never band 2.
    lib = library(ramps={"r": [1, 2, 3]}, default="r")
    got = [mapped(look, v, lib, (100, 101)) for v in (0, 100, 101, 255)]
    assert got == [1, 1, 2, 2]


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_one_entry_ramp_is_flat(look, by_mode):
    lib = library(ramps={"flat": [6]}, default="flat")
    assert {mapped(look, v, lib, (10, 200)) for v in (0, 100, 255)} == {6}


def test_plain_clamps_the_mean_not_its_samples():
    # Shades 0 and 255 at equal weight over (100, 120), three bands of seven:
    # the mean 127.5 clamps to 120, band 2. Clamping the samples first would
    # average 100 and 120 to 110, band 1.
    lib = library(ramps={"r": [1, 2, 3]}, default="r")
    one = frame([255] * 4, [0] * 4, [0, 255, 0, 255])
    assert entry(run(stylize.plain, one, library=lib, shade_range=(100, 120))) == 3


def test_plain_does_not_round_the_mean_before_the_band():
    # Shades 127 and 128 average 127.5. Over (0, 255) it is band 0 of two,
    # though its rounding, 128, is band 1; over (0, 254) it is exactly the
    # edge of band 1.
    lib = library(ramps={"r": [1, 2]}, default="r")
    one = frame([255] * 4, [0] * 4, [127, 128, 127, 128])
    assert entry(run(stylize.plain, one, library=lib)) == 1
    assert entry(run(stylize.plain, one, library=lib, shade_range=(0, 254))) == 2


def test_plain_and_mode_can_differ_on_one_block():
    lib = library(ramps={"r": [1, 2]}, default="r")
    one = frame([255] * 4, [0] * 4, [120, 120, 120, 255])  # mean 153.75
    assert entry(run(stylize.plain, one, library=lib)) == 2
    assert entry(run(stylize.mode, one, library=lib)) == 1


def test_mode_pools_the_votes_of_a_repeated_entry():
    # Bands of 85: entry 5 fills bands 0 and 2, entry 6 band 1. Entry 6 has
    # four votes, entry 5 three and two, which pool to five.
    lib = library(ramps={"r": [5, 6, 5]}, default="r")
    one = frame([255] * 9, [0] * 9, [0, 0, 0, 100, 100, 100, 100, 250, 250])
    assert entry(run(stylize.mode, one, library=lib, shade_range=(0, 254))) == 5


def test_one_entry_at_both_ends_of_a_ramp():
    lib = library(ramps={"r": [2, 4, 2]}, default="r")
    # Over (0, 255) the bands start at 0, 86 and 171.
    for v, want in [(0, 2), (85, 2), (86, 4), (170, 4), (171, 2), (255, 2)]:
        assert mapped(stylize.plain, v, lib) == want, v
        assert mapped(stylize.mode, v, lib) == want, v


@pytest.mark.parametrize(
    ("ramp", "winner"), [([1, 2, 1, 3], 1), ([3, 2, 3, 1], 3)], ids=["low", "high"]
)
def test_mode_ties_go_to_the_nearest_band_centre_over_every_occurrence(ramp, winner):
    # (0, 119) has four bands of 30, centred 15, 45, 75 and 105.
    lib = library(ramps={"r": ramp}, default="r")
    # The entry in bands 0 and 2 ties the entry in band 3 (shades 29 and 119)
    # at mean 74. Counting only its voted band 0, it is 59 away and the other
    # only 31; but it also fills the unvoted band 2, centred 75, one away.
    one = frame([255] * 4, [0] * 4, [29, 119, 29, 119])
    assert entry(run(stylize.mode, one, library=lib, shade_range=(0, 119))) == winner


def test_mode_ties_at_equal_distance_go_to_the_smaller_palette_index():
    # Shades 1 and 119 at equal weight: the mean 60 is midway between the
    # centres 15 and 105 of bands 0 and 3.
    one = frame([255] * 4, [0] * 4, [1, 119, 1, 119])
    for ramp in ([5, 6, 6, 4], [4, 6, 6, 5]):
        lib = library(ramps={"r": ramp}, default="r")
        assert entry(run(stylize.mode, one, library=lib, shade_range=(0, 119))) == 4


# Identity


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_materials_sharing_a_name_pool_their_votes(look, by_mode):
    names = Identities(("steel", "cloth", "steel"))
    lib = library(entries={"steel": {"ramp": [1]}, "cloth": {"ramp": [2]}})
    # Steel's 200 + 200 beats cloth's 255; unpooled, cloth would win.
    one = frame([200, 200, 255, 255], [0, 2, 1, BACKGROUND], [0] * 4)
    assert entry(run(look, one, library=lib, identities=names)) == 1


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_equal_votes_go_to_the_lowest_material_index_and_no_identity_last(
    look, by_mode
):
    lib = library(entries={n: {"ramp": [i + 1]} for i, n in enumerate(NAMES)})

    def both(a, b):
        return frame([255] * 4, [a, a, b, b], [0] * 4)

    assert entry(run(look, both(1, 0), library=lib)) == 1
    assert entry(run(look, both(2, 1), library=lib)) == 2
    assert entry(run(look, both(2, 0), library=lib)) == 1
    # No-identity is last: in a tie it loses to any named material.
    assert entry(run(look, both(NONE, 2), library=lib)) == 3


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_tie_does_not_depend_on_pixel_order(look, by_mode):
    lib = library(entries={n: {"ramp": [i + 1]} for i, n in enumerate(NAMES)})
    got = {
        entry(run(look, frame([255] * 4, list(order), [0] * 4), library=lib))
        for order in [(2, 1, 1, 2), (1, 2, 2, 1), (2, 2, 1, 1), (1, 1, 2, 2)]
    }
    assert got == {2}


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_votes_are_weighted_by_colour_alpha(look, by_mode):
    lib = library(entries={"steel": {"ramp": [1]}, "cloth": {"ramp": [2]}})
    # One pixel of alpha 255 outvotes two of alpha 120.
    one = frame([120, 120, 255, 255], [0, 0, 1, BACKGROUND], [0] * 4)
    assert entry(run(look, one, library=lib)) == 2


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_covered_block_with_no_vote_takes_the_ordinary_look(look, by_mode):
    lib = library(default="metal")
    # Covered by alpha (exactly 0.5), but the only pixels with an identity are
    # transparent, and the opaque ones are background.
    one = frame([255, 255, 0, 0], [BACKGROUND, BACKGROUND, 0, 0], [9] * 4)
    np.testing.assert_array_equal(run(look, one, library=lib), ordinary(look, one))
    assert run(look, one, library=lib)[0, 0, 3] == 255


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_edge_pixels_with_background_identity_count_towards_coverage(look, by_mode):
    lib = library(default="metal")
    # Two background pixels and one steel pixel cover 0.75, and steel wins.
    one = frame([255, 255, 255, 0], [BACKGROUND, BACKGROUND, 0, 0], [100] * 4)
    assert entry(run(look, one, library=lib)) in (1, 2, 3)
    # Two background pixels alone: exactly 0.5 coverage, kept, and no vote.
    half = frame([255, 255, 0, 0], [BACKGROUND, BACKGROUND, 0, 0], [100] * 4)
    assert run(look, half, library=lib)[0, 0, 3] == 255


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_block_below_half_coverage_stays_transparent(look, by_mode):
    lib = library(default="metal")
    one = frame([255, 0, 0, 0], [0] * 4, [100] * 4)
    assert tuple(run(look, one, library=lib)[0, 0]) == (0, 0, 0, 0)
    two = frame([255, 255, 0, 0], [0] * 4, [100] * 4)
    assert run(look, two, library=lib)[0, 0, 3] == 255


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_no_identity_block_keeps_the_whole_blocks_ordinary_look(look, by_mode):
    lib = library(default="metal", entries={"steel": {"ramp": [1]}})
    # No-identity wins by weight; the steel and background pixels, with
    # extreme shades, still count in the ordinary look.
    one = frame([255] * 4, [NONE, NONE, 0, BACKGROUND], [10, 20, 255, 0])
    np.testing.assert_array_equal(run(look, one, library=lib), ordinary(look, one))


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_blend_surfaces_take_the_ordinary_look_even_sharing_a_mapped_name(
    look, by_mode
):
    # A BLEND material named "steel" decodes to no-identity, while an opaque
    # "steel" is index 0. The library and its default both map "steel".
    lib = library(default="metal", entries={"steel": {"ramp": [7]}})
    blend = frame([255] * 4, [NONE] * 4, [50] * 4)
    np.testing.assert_array_equal(run(look, blend, library=lib), ordinary(look, blend))
    mixed = frame([255] * 4, [NONE, NONE, NONE, 0], [50] * 4)
    np.testing.assert_array_equal(run(look, mixed, library=lib), ordinary(look, mixed))
    opaque = frame([255] * 4, [0] * 4, [50] * 4)
    assert entry(run(look, opaque, library=lib)) == 7


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_only_the_winners_pixels_give_the_band(look, by_mode):
    lib = library(ramps={"r": [1, 2]}, entries={"steel": {"uses": "r"}})
    # Steel's pixels are dark; the losing cloth, no-identity and background
    # pixels are bright and must not move the band.
    one = frame(
        [255] * 9,
        [0, 0, 0, 0, 1, BACKGROUND, NONE, BACKGROUND, 1],
        [0, 10, 20, 5, 255, 255, 255, 255, 255],
    )
    assert entry(run(look, one, library=lib)) == 1


def test_plain_weights_the_winners_shades_by_colour_alpha():
    lib = library(ramps={"r": [1, 2]}, default="r")
    # Steel is the first two pixels; background fills the rest of the block.
    # Dark at alpha 255 and bright at 90: mean 255·90/345 = 66.5, band 0.
    one = frame([255, 90, 255, 255], [0, 0, BACKGROUND, BACKGROUND], [0, 255, 255, 255])
    assert entry(run(stylize.plain, one, library=lib)) == 1
    # Dark at alpha 90 and bright at 255: mean 255·255/345 = 188.5, band 1.
    two = frame([90, 255, 255, 255], [0, 0, BACKGROUND, BACKGROUND], [0, 255, 255, 255])
    assert entry(run(stylize.plain, two, library=lib)) == 2


def test_mode_and_plain_ignore_a_transparent_pixels_shade():
    lib = library(ramps={"r": [1, 2]}, default="r")
    one = frame([255, 255, 255, 0], [0] * 4, [0, 0, 0, 255])
    assert entry(run(stylize.mode, one, library=lib)) == 1
    assert entry(run(stylize.plain, one, library=lib)) == 1


# Whole frames


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_block_takes_the_ramp_while_others_keep_the_ordinary_look(look, by_mode):
    lib = library(entries={"steel": {"ramp": [7]}})
    rng = np.random.default_rng(3)
    pixels = rng.integers(0, 256, (6, 6, 4), dtype=np.uint8)
    pixels[..., 3] = 255
    identity = np.full((6, 6), NONE, dtype=np.int32)
    identity[:2, :2] = 0  # block (0, 0) is steel
    one = ImageFrame(
        address(), pixels, {}, {IDENTITY: identity, SHADE: np.zeros((6, 6), np.uint8)}
    )
    result = run(look, one, factor=2, library=lib)
    expected = ordinary(look, one, factor=2)
    expected[0, 0] = (*COLORS[7], 255)
    np.testing.assert_array_equal(result, expected)


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_without_a_library_the_reductions_are_unchanged(look, by_mode):
    rng = np.random.default_rng(4)
    pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    carrying = ImageFrame(
        address(),
        pixels,
        {},
        {
            IDENTITY: rng.integers(-1, 4, (8, 8), dtype=np.int32),
            SHADE: rng.integers(0, 256, (8, 8), dtype=np.uint8),
        },
    )
    bare = ImageFrame(address(), pixels)
    for palette in (None, COLORS):
        got = look([carrying], 2, palette=palette, identities=IDENTITIES)
        want = look([bare], 2, palette=palette)
        np.testing.assert_array_equal(got[0].pixels, want[0].pixels)


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_the_result_is_independent_of_library_key_order_and_repeatable(look, by_mode):
    entries = {
        "steel": {"uses": "metal"},
        "cloth": {"ramp": [6, 5]},
        "skin": "ordinary",
    }
    forward = library(
        ramps={"metal": [1, 2, 3], "cloth": [4, 5]}, default="cloth", entries=entries
    )
    backward = library(
        ramps={"cloth": [4, 5], "metal": [1, 2, 3]},
        default="cloth",
        entries=dict(reversed(entries.items())),
    )
    rng = np.random.default_rng(8)
    pixels = rng.integers(0, 256, (12, 12, 4), dtype=np.uint8)
    pixels[..., 3] = rng.choice([0, 128, 255], (12, 12))
    named = {
        IDENTITY: rng.integers(-1, NONE + 1, (12, 12), dtype=np.int32),
        SHADE: rng.integers(0, 256, (12, 12), dtype=np.uint8),
    }
    one = ImageFrame(address(), pixels, {}, named)
    first = run(look, one, factor=3, library=forward, shade_range=(20, 230))
    np.testing.assert_array_equal(
        first, run(look, one, factor=3, library=backward, shade_range=(20, 230))
    )
    np.testing.assert_array_equal(
        first, run(look, one, factor=3, library=forward, shade_range=(20, 230))
    )


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_lazy_frames_keep_addresses_order_and_metadata_and_release_every_buffer(
    look, by_mode
):
    lib = library(default="metal")
    held, inputs = [], []

    def capture():
        for i in (2, 0, 1):
            assert all(ref() is None for ref in held), "a previous frame is held"
            rng = np.random.default_rng(i)
            pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
            named = {
                IDENTITY: rng.integers(-1, NONE + 1, (8, 8), dtype=np.int32),
                SHADE: rng.integers(0, 256, (8, 8), dtype=np.uint8),
            }
            inputs.append((pixels.copy(), {k: v.copy() for k, v in named.items()}))
            held.extend(weakref.ref(a) for a in [pixels, *named.values()])
            yield ImageFrame(address(i), pixels, {"i": i}, named)
            del pixels, named

    result = look(
        capture(),
        2,
        palette=COLORS,
        identities=IDENTITIES,
        library=lib,
        shade_range=(0, 255),
    )
    assert [r.address for r in result] == [address(2), address(0), address(1)]
    assert [r.metadata for r in result] == [{"i": 2}, {"i": 0}, {"i": 1}]
    assert all(r.buffers == {} for r in result)
    assert all(ref() is None for ref in held)
    # Each frame reduces as it does alone, and some block took a ramp entry.
    for output, (pixels, named) in zip(result, inputs, strict=True):
        alone = ImageFrame(address(), pixels, {}, named)
        np.testing.assert_array_equal(
            output.pixels, run(look, alone, factor=2, library=lib)
        )
        ordinary_pixels = ordinary(look, alone, 2)
        assert (output.pixels != ordinary_pixels).any()
        np.testing.assert_array_equal(output.pixels[..., 3], ordinary_pixels[..., 3])


def test_inputs_are_left_unchanged():
    lib = library(default="metal")
    rng = np.random.default_rng(1)
    pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    named = {
        IDENTITY: rng.integers(-1, NONE + 1, (8, 8), dtype=np.int32),
        SHADE: rng.integers(0, 256, (8, 8), dtype=np.uint8),
    }
    copies = [pixels.copy(), *(a.copy() for a in named.values())]
    for look in (stylize.plain, stylize.mode):
        run(look, ImageFrame(address(), pixels, {}, named), factor=2, library=lib)
    for before, after in zip(copies, [pixels, *named.values()], strict=True):
        np.testing.assert_array_equal(before, after)


# Errors


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_a_library_needs_its_inputs(look, by_mode):
    lib = library(default="metal")
    one = frame([255] * 4, [0] * 4, [0] * 4)
    for options in (
        {"palette": None},
        {"identities": None},
        {"shade_range": None},
    ):
        with pytest.raises(ValueError, match="material library needs"):
            run(look, one, library=lib, **options)
    for missing in (IDENTITY, SHADE):
        buffers = {k: v for k, v in one.buffers.items() if k != missing}
        stripped = ImageFrame(one.address, one.pixels, {}, buffers)
        with pytest.raises(ValueError, match=f"needs the {missing} buffer"):
            run(look, stripped, library=lib)


@pytest.mark.parametrize("shade_range", [(5, 5), (6, 5), (-1, 5), (0, 256)])
def test_the_shade_range_must_satisfy_lo_below_hi_within_a_byte(shade_range):
    one = frame([255] * 4, [0] * 4, [0] * 4)
    with pytest.raises(ValueError, match="shade range"):
        run(
            stylize.plain,
            one,
            library=library(default="metal"),
            shade_range=shade_range,
        )


def test_identity_buffers_must_match_the_frame_and_the_list():
    lib = library(default="metal")
    one = frame([255] * 4, [0] * 4, [0] * 4)
    for bad in (
        np.full((2, 2), NONE + 1, dtype=np.int32),
        np.full((2, 2), -2, dtype=np.int32),
        np.zeros((3, 2), dtype=np.int32),
    ):
        broken = ImageFrame(one.address, one.pixels, {}, {**one.buffers, IDENTITY: bad})
        with pytest.raises(ValueError, match="identity must"):
            run(stylize.plain, broken, library=lib)


# Against an independent reference


def nearest(mean, ramp, entry_index, lo, span):
    """The distance from `mean` to the nearest centre of any band holding the
    entry, in exact fractions."""
    n = len(ramp)
    return min(
        abs(mean - (lo + (k + Fraction(1, 2)) * Fraction(span, n)))
        for k in range(n)
        if ramp[k] == entry_index
    )


def reference(pixels, identity, shade, factor, names, lib, lo, hi, by_mode):
    """Block by block with `Fraction`s: the design's rules, read directly."""
    span = hi - lo + 1
    first = {}
    for index, name in enumerate(names):
        first.setdefault(name, index)

    def pooled(index):
        return first[names[index]] if index < len(names) else index

    def ramp_of(index):
        if index >= len(names):
            return None
        name = names[index]
        if name in lib.materials:
            value = lib.materials[name]
            if value.ramp is not None:
                return value.ramp
            return lib.ramps[value.uses] if value.uses is not None else None
        return lib.ramps[lib.default] if lib.default is not None else None

    height, width = pixels.shape[0] // factor, pixels.shape[1] // factor
    out = {}
    for r in range(height):
        for c in range(width):
            cells = [
                (
                    int(pixels[r * factor + y, c * factor + x, 3]),
                    int(identity[r * factor + y, c * factor + x]),
                    int(shade[r * factor + y, c * factor + x]),
                )
                for y in range(factor)
                for x in range(factor)
            ]
            if 2 * sum(a for a, _, _ in cells) < 255 * factor * factor:
                continue
            votes = {}
            for a, i, _ in cells:
                if a > 0 and i >= 0:
                    votes[pooled(i)] = votes.get(pooled(i), 0) + a
            if not votes:
                continue
            winner = min(votes, key=lambda k: (-votes[k], k))
            ramp = ramp_of(winner)
            if ramp is None:
                continue
            own = [
                (a, v) for a, i, v in cells if a > 0 and i >= 0 and pooled(i) == winner
            ]
            total = sum(a for a, _ in own)
            mean = Fraction(sum(a * v for a, v in own), total)
            n = len(ramp)
            if not by_mode:
                clamped = min(max(mean, lo), hi)
                out[r, c] = ramp[int((clamped - lo) * n // span)]
                continue
            tally = {}
            for a, v in own:
                e = ramp[(min(max(v, lo), hi) - lo) * n // span]
                tally[e] = tally.get(e, 0) + a
            top = max(tally.values())

            out[r, c] = min(
                (e for e in tally if tally[e] == top),
                key=lambda e: (nearest(mean, ramp, e, lo, span), e),
            )
    return out


@pytest.mark.parametrize(("look", "by_mode"), BOTH)
def test_random_blocks_match_an_independent_reference(look, by_mode):
    rng = np.random.default_rng(2026)
    for trial in range(250):
        factor = int(rng.integers(1, 4))
        rows, columns = (int(v) for v in rng.integers(1, 4, 2))
        names = tuple(
            rng.choice(["a", "b", "c", "d"], int(rng.integers(0, 5))).tolist()
        )
        identities = Identities(names)
        ramps = {
            f"r{k}": rng.integers(0, len(COLORS), int(rng.integers(1, 9))).tolist()
            for k in range(3)
        }
        entries = {}
        for name in "abcd":
            kind = int(rng.integers(0, 4))
            if kind == 1:
                entries[name] = {"uses": f"r{int(rng.integers(0, 3))}"}
            elif kind == 2:
                entries[name] = {"ramp": ramps["r0"][::-1]}
            elif kind == 3:
                entries[name] = "ordinary"
        default = f"r{int(rng.integers(0, 3))}" if rng.integers(0, 2) else None
        lib = library(ramps=ramps, default=default, entries=entries)
        lo = int(rng.integers(0, 250))
        hi = min(255, lo + 1 + int(rng.choice([0, 1, 3, 20, 255])))
        height, width = rows * factor, columns * factor
        pixels = rng.integers(0, 256, (height, width, 4), dtype=np.uint8)
        pixels[..., 3] = rng.choice([0, 0, 40, 128, 255], (height, width))
        identity = rng.integers(-1, len(names) + 1, (height, width)).astype(np.int32)
        shade = rng.choice(
            [
                0,
                lo,
                min(lo + 1, 255),
                (lo + hi) // 2,
                hi,
                255,
                int(rng.integers(0, 256)),
            ],
            (height, width),
        ).astype(np.uint8)
        one = ImageFrame(address(), pixels, {}, {IDENTITY: identity, SHADE: shade})
        result = look(
            [one],
            factor,
            palette=COLORS,
            identities=identities,
            library=lib,
            shade_range=(lo, hi),
        )[0].pixels
        want = ordinary(look, one, factor)
        for (r, c), index in reference(
            pixels, identity, shade, factor, names, lib, lo, hi, by_mode
        ).items():
            want[r, c] = (*COLORS[index], 255)
        np.testing.assert_array_equal(result, want, err_msg=f"trial {trial}")


def test_random_ties_match_the_reference_under_mode():
    """Few colours and equal alpha make `mode` ties common."""
    rng = np.random.default_rng(7)
    tied = 0
    for trial in range(600):
        size = int(rng.integers(2, 4))
        ramp = rng.integers(1, 4, int(rng.integers(2, 7))).tolist()
        lib = library(ramps={"r": ramp}, default="r")
        lo = int(rng.integers(0, 100))
        hi = lo + 1 + int(rng.integers(0, 150))
        pixels = np.zeros((size, size, 4), dtype=np.uint8)
        pixels[..., 3] = 255
        identity = np.zeros((size, size), dtype=np.int32)
        shade = rng.integers(lo, hi + 1, (size, size), dtype=np.uint8)
        one = ImageFrame(address(), pixels, {}, {IDENTITY: identity, SHADE: shade})
        got = stylize.mode(
            [one],
            size,
            palette=COLORS,
            identities=IDENTITIES,
            library=lib,
            shade_range=(lo, hi),
        )[0].pixels
        want = reference(pixels, identity, shade, size, NAMES, lib, lo, hi, True)
        assert got[0, 0, :3].tolist() == list(COLORS[want[0, 0]]), trial
        bands = (shade.astype(int) - lo) * len(ramp) // (hi - lo + 1)
        votes = np.bincount([ramp[b] for b in bands.ravel()], minlength=4)
        tied += (votes == votes.max()).sum() > 1
    assert tied > 60


def test_map_ramps_marks_exactly_the_mapped_blocks():
    identity = np.array([[0, 0, 1, 1], [0, 0, 1, 1]], dtype=np.int32)
    pixels = np.full((2, 4, 4), 255, dtype=np.uint8)
    shade = np.zeros((2, 4), dtype=np.uint8)
    result, mapped = imageops.map_ramps(
        pixels, identity, shade, 2, [(3,), None, None], COLORS, 0, 255, by_mode=False
    )
    assert mapped.tolist() == [[True, False]]
    assert tuple(result[0, 0]) == (*COLORS[3], 255)
    assert tuple(result[0, 1]) == (0, 0, 0, 0)
