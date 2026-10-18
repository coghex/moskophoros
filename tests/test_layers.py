"""Two layers per supersample, reduced and composited (alpha design D-6,
D-12, D-14, *Stylize: numerical reference* steps 1 to 4): the pinned cases
that need no ramp on the front layer, under `plain` and `mode`, `hard`
unless said, with and without a palette."""

import math

import numpy as np
import pytest

from moskophoros import imageops, materials, stylize
from moskophoros.sampling import (
    BACKGROUND,
    FRONT_ALPHA,
    FRONT_COLOR,
    FRONT_IDENTITY,
    FRONT_PRESENT,
    FRONT_SHADE,
    IDENTITY,
    SHADE,
    FrameAddress,
    Identities,
    ImageFrame,
)

RED, BLUE, GREEN = (255, 0, 0), (0, 0, 255), (0, 255, 0)
LOOKS = [pytest.param(stylize.plain, id="plain"), pytest.param(stylize.mode, id="mode")]
# A palette holding every colour the cases use, so mapping keeps them; a
# composite then snaps to its nearest entry.
PALETTE = (RED, BLUE, GREEN, (0, 0, 0), (255, 255, 255), (128, 0, 128))


def q(f):
    return math.floor(65535 * f + 0.5)


def frame(samples, size=2, identity=None, shade=None):
    """A frame of one `size`×`size` block from per-sample `(front colour or
    None, q, back colour or None)`, in raster order."""
    back = np.zeros((size, size, 4), np.uint8)
    front = np.zeros((size, size, 4), np.uint8)
    alpha = np.zeros((size, size), np.uint16)
    present = np.zeros((size, size), bool)
    for index, (front_colour, front_q, back_colour) in enumerate(samples):
        y, x = divmod(index, size)
        if back_colour is not None:
            back[y, x] = (*back_colour, 255)
        if front_colour is not None:
            front[y, x] = (*front_colour, 255)
            alpha[y, x] = front_q
            present[y, x] = True
    buffers = {
        FRONT_COLOR: front,
        FRONT_ALPHA: alpha,
        FRONT_PRESENT: present,
        FRONT_IDENTITY: np.full((size, size), BACKGROUND, np.int32),
        FRONT_SHADE: np.zeros((size, size), np.uint8),
    }
    if identity is not None:
        buffers[IDENTITY] = np.asarray(identity, np.int32).reshape(size, size)
        buffers[SHADE] = np.asarray(shade, np.uint8).reshape(size, size)
    return ImageFrame(FrameAddress("s", "default", "walk", 0, 0.0), back, {}, buffers)


def pixel(look, samples, edges="hard", **options):
    (reduced,) = look([frame(samples)], 2, edges=edges, **options)
    return tuple(int(v) for v in reduced.pixels[0, 0])


def lin(byte):
    c = byte / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def encode(linear):
    s = 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    return min(255, math.floor(255 * s + 0.5))


def over(front, front_weight, back, back_weight):
    """The composite, worked out independently in float64."""
    return tuple(
        encode(
            (front_weight * lin(f) + back_weight * lin(b))
            / (front_weight + back_weight)
        )
        for f, b in zip(front, back, strict=True)
    )


def snapped(colour, palette):
    """`colour` mapped to `palette` by `imageops.map_palette`."""
    mapped = imageops.map_palette(np.array([[[*colour, 255]]], np.uint8), palette)
    return tuple(int(v) for v in mapped[0, 0, :3])


EMPTY = (None, 0, None)


@pytest.mark.parametrize("palette", [None, PALETTE], ids=["no palette", "palette"])
@pytest.mark.parametrize("look", LOOKS)
class TestPinnedCases:
    def test_a_front_only_at_0_4_on_every_sample(self, look, palette):
        got = pixel(look, [(RED, q(0.4), None)] * 4, palette=palette)
        assert got == (*RED, 102)

    def test_a_front_only_at_0_4_on_two_samples(self, look, palette):
        samples = [(RED, q(0.4), None)] * 2 + [EMPTY] * 2
        assert pixel(look, samples, palette=palette) == (*RED, 102)
        assert pixel(look, samples, "soft", palette=palette) == (*RED, 51)

    @pytest.mark.parametrize("edges", ["hard", "soft"])
    def test_two_fronts_at_0_5_and_two_backs_weigh_by_where_each_is(
        self, look, palette, edges
    ):
        samples = [(RED, q(0.5), None)] * 2 + [(None, 0, BLUE)] * 2
        colour = over(RED, 2 * q(0.5), BLUE, 2 * 65535)
        # Not 0.625, the mean of the two layers' alphas.
        got = pixel(look, samples, edges, palette=palette)
        assert got[3] == 191
        if palette is None:
            # (1·red + 2·blue) / 3 in linear.
            assert got[:3] == colour == over(RED, 1, BLUE, 2)
        else:
            assert got[:3] == snapped(colour, palette)

    def test_a_front_at_0_5_over_a_back_on_two_samples_and_two_empty(
        self, look, palette
    ):
        samples = [(RED, q(0.5), BLUE)] * 2 + [EMPTY] * 2
        hard = pixel(look, samples, palette=palette)
        soft = pixel(look, samples, "soft", palette=palette)
        assert (hard[3], soft[3]) == (255, 128)
        assert hard[:3] == soft[:3]
        colour = over(RED, q(0.5), BLUE, 65535 - q(0.5))
        assert hard[:3] == (colour if palette is None else snapped(colour, palette))

    def test_a_faint_front_is_a_surface_whatever_its_alpha(self, look, palette):
        # f of [0.001, 0.001] front only and two back only: four surfaces,
        # alpha 0.5005, so 128, not 255.
        samples = [(RED, q(0.001), None)] * 2 + [(None, 0, BLUE)] * 2
        assert q(0.001) == 66
        assert pixel(look, samples, palette=palette)[3] == 128

    def test_a_front_of_q_0_is_a_surface_of_alpha_0(self, look, palette):
        # One back sample and one front of q 0: two surfaces of four, so the
        # pixel shows under hard, at their mean alpha, (65535 + 0) / 2.
        samples = [(RED, 0, None), (None, 0, BLUE), EMPTY, EMPTY]
        assert pixel(look, samples, palette=palette) == (*BLUE, 128)
        # Alone, it is alpha 0: no pixel.
        assert pixel(look, [(RED, 0, None)] * 4, palette=palette) == (0, 0, 0, 0)

    def test_with_a_palette_every_colour_is_one_and_alpha_is_not_snapped(
        self, look, palette
    ):
        samples = [(RED, q(0.3), BLUE), (GREEN, q(0.7), None), (None, 0, RED), EMPTY]
        for edges in ("hard", "soft"):
            got = pixel(look, samples, edges, palette=palette)
            if palette is not None:
                assert got[:3] in PALETTE
            assert got[3] not in (0, 255)


def test_the_composite_is_in_linear_colour():
    front = np.array([[RED, (10, 200, 30)]], np.uint8)
    back = np.array([[BLUE, (250, 0, 90)]], np.uint8)
    weights = np.array([[32768, 1000]]), np.array([[32767, 64535]])
    got = imageops.composite(front, weights[0], back, weights[1])
    assert got.tolist() == [
        [
            list(over(RED, 32768, BLUE, 32767)),
            list(over((10, 200, 30), 1000, (250, 0, 90), 64535)),
        ]
    ]


def test_one_weighted_layer_keeps_its_colour_unchanged():
    front = np.array([[(17, 33, 251), (0, 0, 0), (5, 5, 5)]], np.uint8)
    back = np.array([[(9, 9, 9), (120, 3, 77), (6, 6, 6)]], np.uint8)
    got = imageops.composite(front, np.array([[5, 0, 0]]), back, np.array([[0, 7, 0]]))
    assert got.tolist() == [[[17, 33, 251], [120, 3, 77], [0, 0, 0]]]


def test_with_a_palette_the_back_maps_first_and_the_composite_snaps_last():
    # Plain, palette black and white: the back (100, 100, 100) maps to
    # white first, the composite with a black front of weight 32768 over
    # transmitted weight 32767 is 188, and the final snap gives white, not
    # the black a composite of the unmapped back would snap to.
    bw = ((0, 0, 0), (255, 255, 255))
    assert over((0, 0, 0), 32768, (255, 255, 255), 32767) == (188, 188, 188)
    assert over((0, 0, 0), 32768, (100, 100, 100), 32767) == (71, 71, 71)
    samples = [((0, 0, 0), 32768, (100, 100, 100))] * 4
    assert pixel(stylize.plain, samples, palette=bw) == (255, 255, 255, 255)
    assert pixel(stylize.plain, samples) == (71, 71, 71, 255)


def test_mode_breaks_a_tie_between_front_colours_by_today_s_rule():
    # Two front colours tie at equal weight; a weaker third pulls the
    # weighted mean towards the first, which wins, as reduce_blocks_mode's
    # tie rule says.
    a, b, c = (200, 0, 0), (0, 0, 200), (200, 0, 100)
    samples = [(a, 40000, None), (b, 40000, None), (c, 20000, None), EMPTY]
    got = pixel(stylize.mode, samples)
    assert got[:3] == a
    # The same tie the other way round.
    samples = [(b, 40000, None), (a, 40000, None), ((0, 0, 100), 20000, None), EMPTY]
    assert pixel(stylize.mode, samples)[:3] == b


def test_a_ramped_back_keeps_its_ramp_under_a_front():
    palette = tuple((i * 30, i * 30, i * 30) for i in range(8))
    document = {
        "schema": materials.SCHEMA,
        "ramps": {"metal": [5]},
        "materials": {"steel": {"uses": "metal"}},
    }
    library = materials.validate_library(document, palette, source="test")
    samples = [((0, 255, 0), q(0.4), (90, 90, 90))] * 4
    one = frame(samples, identity=[0] * 4, shade=[100] * 4)
    for look in (stylize.plain, stylize.mode):
        (reduced,) = look(
            [one],
            2,
            palette=palette,
            identities=Identities(("steel",)),
            library=library,
            shade_range=(0, 255),
        )
        got = tuple(int(v) for v in reduced.pixels[0, 0])
        # The back is the ramp's entry 5, (150, 150, 150); the front is
        # mapped to the palette; the composite snaps.
        front = tuple(
            imageops.map_palette(np.array([[[0, 255, 0, 255]]], np.uint8), palette)[
                0, 0, :3
            ].tolist()
        )
        expected = over(front, q(0.4), (150, 150, 150), 65535 - q(0.4))
        snapped = tuple(
            imageops.map_palette(np.array([[[*expected, 255]]], np.uint8), palette)[
                0, 0, :3
            ].tolist()
        )
        assert got == (*snapped, 255)


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("edges", ["hard", "soft"])
def test_a_frame_with_no_front_is_reduced_as_before(look, edges):
    rng = np.random.default_rng(117)
    pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    pixels[..., 3] = rng.choice([0, 255], (8, 8))
    bare = ImageFrame(FrameAddress("s", "default", "walk", 0, 0.0), pixels)
    empty = frame([EMPTY] * 64, size=8)
    empty = ImageFrame(empty.address, pixels, {}, empty.buffers)
    (a,) = look([bare], 2, edges=edges)
    (b,) = look([empty], 2, edges=edges)
    np.testing.assert_array_equal(a.pixels, b.pixels)


@pytest.mark.parametrize("look", LOOKS)
def test_a_block_without_a_front_in_a_frame_with_one_is_reduced_as_before(look):
    rng = np.random.default_rng(42)
    pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    pixels[..., 3] = rng.choice([0, 255], (8, 8))
    samples = [EMPTY] * 64
    samples[0] = (RED, q(0.4), None)
    layered = frame(samples, size=8)
    with_front = ImageFrame(layered.address, pixels, {}, layered.buffers)
    bare = ImageFrame(layered.address, pixels)
    for edges in ("hard", "soft"):
        (a,) = look([bare], 2, edges=edges)
        (b,) = look([with_front], 2, edges=edges)
        np.testing.assert_array_equal(a.pixels[1:], b.pixels[1:])
        np.testing.assert_array_equal(a.pixels[0, 1:], b.pixels[0, 1:])


# The front layer's ramp (alpha design D-12, D-15; numerical reference step 2)

GREYS = tuple((i * 30, i * 30, i * 30) for i in range(8))


def ramped_frame(samples):
    """A 2×2 frame from per-sample `(front identity, front shade, q, back
    identity or None)`: the back steel or nothing, the front at alpha `q`."""
    back = np.zeros((2, 2, 4), np.uint8)
    front = np.zeros((2, 2, 4), np.uint8)
    alpha = np.zeros((2, 2), np.uint16)
    present = np.zeros((2, 2), bool)
    identity = np.full((2, 2), BACKGROUND, np.int32)
    shade = np.zeros((2, 2), np.uint8)
    front_identity = np.full((2, 2), BACKGROUND, np.int32)
    front_shade = np.zeros((2, 2), np.uint8)
    for index, (f_id, f_shade, front_q, back_id) in enumerate(samples):
        y, x = divmod(index, 2)
        if back_id is not None:
            back[y, x] = (90, 90, 90, 255)
            identity[y, x], shade[y, x] = back_id, 137
        if f_id is not None:
            front[y, x] = (0, 200, 40, 255)
            alpha[y, x], present[y, x] = front_q, True
            front_identity[y, x], front_shade[y, x] = f_id, f_shade
    buffers = {
        FRONT_COLOR: front,
        FRONT_ALPHA: alpha,
        FRONT_PRESENT: present,
        FRONT_IDENTITY: front_identity,
        FRONT_SHADE: front_shade,
        IDENTITY: identity,
        SHADE: shade,
    }
    return ImageFrame(FrameAddress("s", "default", "walk", 0, 0.0), back, {}, buffers)


def ramped(look, samples, entries, names=("steel", "glass", "veil")):
    document = {
        "schema": materials.SCHEMA,
        "ramps": {"metal": [5], "clear": [2], "two": [1, 3]},
        "materials": entries,
    }
    library = materials.validate_library(document, GREYS, source="test")
    (reduced,) = look(
        [ramped_frame(samples)],
        2,
        palette=GREYS,
        identities=Identities(names),
        library=library,
        shade_range=(0, 255),
    )
    return tuple(int(v) for v in reduced.pixels[0, 0])


@pytest.mark.parametrize("look", LOOKS)
def test_a_ramped_front_over_a_ramped_back_composites_both_ramps_then_snaps(look):
    entries = {"steel": {"uses": "metal"}, "glass": {"uses": "clear"}}
    got = ramped(look, [(1, 137, q(0.4), 0)] * 4, entries)
    # The front is glass's ramp colour, the back steel's, composited in
    # linear, then snapped.
    expected = snapped(over(GREYS[2], q(0.4), GREYS[5], 65535 - q(0.4)), GREYS)
    assert got == (*expected, 255)
    assert expected not in (GREYS[2], GREYS[5])


@pytest.mark.parametrize("look", LOOKS)
def test_a_front_without_a_ramp_keeps_its_ordinary_look_over_a_ramped_back(look):
    entries = {"steel": {"uses": "metal"}, "glass": "ordinary"}
    got = ramped(look, [(1, 137, q(0.4), 0)] * 4, entries)
    front = snapped((0, 200, 40), GREYS)
    expected = snapped(over(front, q(0.4), GREYS[5], 65535 - q(0.4)), GREYS)
    assert got == (*expected, 255)


@pytest.mark.parametrize("look", LOOKS)
def test_the_front_identity_tie_goes_to_the_lowest_index(look):
    # Glass (1) and veil (2) tie at equal front weight; glass, the lower
    # index, wins under both reductions (material styling D-23).
    entries = {"glass": {"uses": "clear"}, "veil": {"uses": "metal"}}
    # A front alone at q 40000 has alpha 255 · 40000 / 65535 = 155.6.
    samples = [(1, 137, 40000, None)] * 2 + [(2, 137, 40000, None)] * 2
    assert ramped(look, samples, entries) == (*GREYS[2], 156)
    samples = [(2, 137, 40000, None)] * 2 + [(1, 137, 40000, None)] * 2
    assert ramped(look, samples, entries) == (*GREYS[2], 156)


def test_mode_s_front_band_tie_goes_to_the_band_nearest_the_weighted_shade():
    # One identity, ramp [1, 3] over 0–255: shades 0 and 255 tie at equal
    # front weight, between entries 1 and 3. The weighted mean shade 127.5
    # is nearer band 0's centre, 64, than band 1's, 192: entry 1.
    entries = {"glass": {"uses": "two"}}
    # A front alone at q 30000 has alpha 255 · 30000 / 65535 = 116.7.
    samples = [(1, 0, 30000, None)] * 2 + [(1, 255, 30000, None)] * 2
    assert ramped(stylize.mode, samples, entries) == (*GREYS[1], 117)
    # Shades 10 and 255 give a mean of 132.5, nearer 192: entry 3.
    samples = [(1, 10, 30000, None)] * 2 + [(1, 255, 30000, None)] * 2
    assert ramped(stylize.mode, samples, entries) == (*GREYS[3], 117)
