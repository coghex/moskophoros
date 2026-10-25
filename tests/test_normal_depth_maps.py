"""Normals and depth reduced to the sheet's pixels, and carried to export
(design §Stylize, Normal and depth maps; lighting sheet design D-8, D-15,
D-19, D-21, D-27 and §Numerical reference). Pure tests, then the command
with a fake Blender."""

import math
import weakref
from fractions import Fraction

import numpy as np
import pytest
from test_command import Setup, run
from test_material_ramps import library

from moskophoros import cleanup, exportimages, imageops, stylize
from moskophoros.imageops import encode_normal, reduce_normal_depth
from moskophoros.sampling import (
    DEPTH,
    DEPTH_MAP,
    IDENTITY,
    NORMAL,
    NORMAL_MAP,
    SHADE,
    FrameAddress,
    Identities,
    ImageFrame,
)

UP = (0.0, 0.0, 1.0)
NO = math.nan


def unit(*v):
    v = np.asarray(v, dtype=np.float64)
    return tuple(v / np.linalg.norm(v))


def block_frame(blocks, factor=2):
    """Normal and depth arrays from a grid of blocks: each block a list of
    `factor²` samples, `(normal, depth_m)` or None for no surface."""
    rows, columns = len(blocks), len(blocks[0])
    normal = np.zeros((rows * factor, columns * factor, 3), dtype=np.float32)
    depth = np.full((rows * factor, columns * factor), np.nan, dtype=np.float32)
    for r, row in enumerate(blocks):
        for c, samples in enumerate(row):
            for k, sample in enumerate(samples):
                if sample is None:
                    continue
                y, x = r * factor + k // factor, c * factor + k % factor
                normal[y, x], depth[y, x] = sample
    return normal, depth


def reduce(blocks, covered=None, factor=2, ppm=1.0, dtype=np.float32):
    normal, depth = block_frame(blocks, factor)
    if covered is None:
        covered = np.ones((len(blocks), len(blocks[0])), dtype=bool)
    return reduce_normal_depth(
        normal.astype(dtype), depth.astype(dtype), np.asarray(covered), factor, ppm
    )


EMPTY = [None] * 4


# Normals (D-15, D-8)


def test_a_block_s_normals_are_summed_and_renormalised():
    a, b = unit(1, 0, 1), unit(0, 1, 1)
    normals, _ = reduce([[[(a, 0.0), (a, 0.0), (b, 0.0), None]]], dtype=np.float64)
    expected = 2 * np.array(a) + np.array(b)
    np.testing.assert_allclose(normals[0, 0], expected / np.linalg.norm(expected))
    assert np.linalg.norm(normals[0, 0]) == pytest.approx(1.0, abs=1e-15)


def test_a_block_with_no_surface_sample_faces_the_viewer():
    normals, depths = reduce([[EMPTY]])
    assert tuple(normals[0, 0]) == UP
    assert depths[0, 0] == 0.0


def test_cancelling_normals_face_the_viewer_and_keep_their_own_depth():
    # (1, 0, 0) with (−1, 0, 0) cancels exactly (R-4, D-27).
    blocks = [
        [
            [((1, 0, 0), 0.25), ((-1, 0, 0), 0.75), None, None],
            EMPTY,
        ]
    ]
    normals, depths = reduce(blocks)
    assert tuple(normals[0, 0]) == UP
    assert depths[0, 0] == 0.5
    # It counts as a neighbour with samples: the empty block takes its depth.
    assert tuple(normals[0, 1]) == UP and depths[0, 1] == 0.5


@pytest.mark.parametrize(
    ("angle", "cancels"), [(0.9e-6, True), (1.1e-6, False)], ids=["under", "over"]
)
def test_a_sum_just_under_the_threshold_cancels(angle, cancels):
    # |(1, 0, 0) + (−cos a, sin a, 0)| is very nearly a.
    other = (-math.cos(angle), math.sin(angle), 0.0)
    normals, depths = reduce(
        [[[((1.0, 0.0, 0.0), 1.0), (other, 2.0), None, None]]], dtype=np.float64
    )
    assert depths[0, 0] == 1.5
    if cancels:
        assert tuple(normals[0, 0]) == UP
    else:
        assert normals[0, 0, 2] == 0.0 and normals[0, 0, 1] > 0.99


def test_the_normal_does_not_depend_on_which_material_a_sample_shows():
    # Pure in the samples alone; see the stylize tests for every look.
    a, b = unit(1, 1, 1), unit(-1, 0, 2)
    normals, _ = reduce([[[(a, 0.0), (b, 0.0), (a, 0.0), (b, 0.0)]]])
    expected = np.array(a) + np.array(b)
    np.testing.assert_allclose(
        normals[0, 0], expected / np.linalg.norm(expected), atol=1e-7
    )


# Depth (D-19, D-27, D-21)


@pytest.mark.parametrize(
    ("depth", "rounded"),
    [
        (1 / 32, 1 / 16),  # an exact half step rounds up: code 32769
        (-1 / 32, 0.0),  # so does a negative one, toward +∞
        (-3 / 32, -1 / 16),
        (3 / 32, 2 / 16),
        (0.0, 0.0),
        (0.03, 0.0),
        (0.04, 1 / 16),
        (-2047.9375, -2047.9375),
    ],
)
def test_a_block_s_depth_is_its_samples_mean_rounded_half_up(depth, rounded):
    _, depths = reduce([[[(UP, depth), (UP, depth), None, None]]], dtype=np.float64)
    assert depths[0, 0] == rounded


def test_depth_is_the_mean_in_sheet_pixels():
    # 0.1 m and 0.2 m at 30 px/m: 4.5 sheet pixels, never scaled by the
    # supersample factor.
    for factor in (1, 2, 3):
        samples = [(UP, 0.1), (UP, 0.2)] + [None] * (factor * factor - 2)
        if factor == 1:
            samples = [(UP, 0.15)]
        normal, depth = block_frame([[samples]], factor)
        _, depths = reduce_normal_depth(
            normal.astype(np.float64),
            depth.astype(np.float64),
            np.ones((1, 1), bool),
            factor,
            30.0,
        )
        assert depths[0, 0] == 4.5, factor


def test_an_empty_block_takes_its_neighbours_unrounded_mean():
    # Neighbours 0.04 and 0.0 px: rounded first, they would be 1/16 and 0,
    # whose mean 1/32 rounds to 1/16; unrounded, their mean 0.02 rounds to 0
    # (R-3).
    blocks = [[[(UP, 0.04)] * 4, EMPTY, [(UP, 0.0)] * 4]]
    _, depths = reduce(blocks, dtype=np.float64)
    assert list(depths[0]) == [1 / 16, 0.0, 0.0]
    blocks = [[[(UP, 0.04)] * 4, EMPTY, [(UP, 0.05)] * 4]]
    _, depths = reduce(blocks, dtype=np.float64)
    assert depths[0, 1] == 1 / 16


def test_the_fallback_uses_only_covered_sampled_neighbours_in_the_frame():
    # A 3×3 grid: the centre has no sample. Of its 8 neighbours, the corner
    # (0, 0) is transparent in the colour and so ignored; the other sampled
    # ones are at 1, 2 and 3 px; the rest are empty.
    one, two, three = ([(UP, d)] * 4 for d in (1.0, 2.0, 3.0))
    blocks = [
        [[(UP, 100.0)] * 4, one, EMPTY],
        [two, EMPTY, EMPTY],
        [EMPTY, three, EMPTY],
    ]
    covered = np.ones((3, 3), dtype=bool)
    covered[0, 0] = False
    _, depths = reduce(blocks, covered)
    assert depths[1, 1] == 2.0
    # At the frame's corner (2, 2), of its 3 neighbours only (2, 1) has
    # samples.
    assert depths[2, 2] == 3.0
    # (0, 2) sees (0, 1) and empty or out-of-frame neighbours.
    assert depths[0, 2] == 1.0
    # The transparent corner has no surface, whatever its samples.
    assert depths[0, 0] == 0.0


def test_with_no_sampled_neighbour_the_depth_is_0():
    blocks = [[EMPTY, EMPTY], [EMPTY, [(UP, 9.0)] * 4]]
    covered = np.array([[True, True], [True, False]])
    _, depths = reduce(blocks, covered)
    assert list(depths.ravel()) == [0.0, 0.0, 0.0, 0.0]


@pytest.mark.parametrize("meters", [1e4, -1e4, 3.0e7, -3.0e38])
def test_any_depth_is_reduced_without_clamping(meters):
    # Far beyond ±2047.9375 sheet pixels at 40 px/m (D-21).
    blocks = [[[(UP, meters)] * 4, EMPTY]]
    _, depths = reduce(blocks, ppm=40.0)
    value = float(np.float32(meters)) * 40.0
    assert depths[0, 0] == math.floor(16 * value + 0.5) / 16
    assert depths[0, 1] == depths[0, 0]
    assert np.isfinite(depths).all()


# Coverage and the uncovered pixels


def test_a_transparent_pixel_has_no_surface_whatever_its_samples():
    blocks = [[[(unit(1, 0, 1), 3.0)] * 4, [(UP, 5.0)] * 4]]
    normals, depths = reduce(blocks, np.array([[False, True]]))
    assert tuple(normals[0, 0]) == (0.0, 0.0, 0.0) and depths[0, 0] == 0.0
    assert tuple(normals[0, 1]) == UP and depths[0, 1] == 5.0


def test_outputs_are_finite_new_arrays_and_the_inputs_are_unchanged():
    rng = np.random.default_rng(5)
    normal = rng.normal(size=(12, 18, 3)).astype(np.float32)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    depth = rng.uniform(-1e6, 1e6, (12, 18)).astype(np.float32)
    hole = rng.random((12, 18)) < 0.4
    normal[hole], depth[hole] = 0.0, np.nan
    covered = rng.random((4, 6)) < 0.7
    before = normal.copy(), depth.copy()
    normals, depths = reduce_normal_depth(normal, depth, covered, 3, 7.017563343627643)
    assert np.isfinite(normals).all() and np.isfinite(depths).all()
    np.testing.assert_array_equal(normal, before[0])
    np.testing.assert_array_equal(depth, before[1])
    for result in (normals, depths):
        assert not np.shares_memory(result, normal)
        assert not np.shares_memory(result, depth)
    lengths = np.linalg.norm(normals, axis=-1)
    np.testing.assert_allclose(lengths[covered], 1.0, atol=1e-12)
    assert (lengths[~covered] == 0).all() and (depths[~covered] == 0).all()
    assert (depths * 16 == np.floor(depths * 16)).all()


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        (
            (np.zeros((4, 4, 3)), np.zeros((4, 4)), np.ones((2, 2), int), 2, 1.0),
            ValueError,
        ),
        (
            (np.zeros((4, 4, 3)), np.zeros((4, 4)), np.ones((2, 2), bool), 2.0, 1.0),
            TypeError,
        ),
        (
            (np.zeros((4, 4, 3)), np.zeros((4, 4)), np.ones((2, 2), bool), 0, 1.0),
            ValueError,
        ),
        (
            (np.zeros((4, 4, 3)), np.zeros((4, 5)), np.ones((2, 2), bool), 2, 1.0),
            ValueError,
        ),
        (
            (np.zeros((4, 4, 3)), np.zeros((4, 4)), np.ones((2, 2), bool), 2, 0.0),
            ValueError,
        ),
        (
            (np.zeros((4, 4, 3)), np.zeros((4, 4)), np.ones((2, 2), bool), 2, math.inf),
            ValueError,
        ),
    ],
)
def test_malformed_arguments_are_refused(arguments, error):
    with pytest.raises(error):
        reduce_normal_depth(*arguments)


# The normal's byte encoding (§Numerical reference, R-3)


def test_the_normal_encoding_at_the_ends_and_facing_the_viewer():
    assert tuple(encode_normal(UP)) == (128, 128, 255)
    assert tuple(encode_normal((-1.0, 1.0, 0.0))) == (0, 255, 128)
    encoded = encode_normal(np.zeros((2, 3, 3)))
    assert encoded.dtype == np.uint8 and encoded.shape == (2, 3, 3)


def _exact_half(k):
    """A float n whose 255 · (n + 1) / 2 evaluates to exactly k + ½, or None."""
    n = (2 * k + 1) / 255 - 1
    for _ in range(64):
        value = 255 * (n + 1) / 2
        if value == k + 0.5:
            return n
        n = np.nextafter(n, np.inf if value < k + 0.5 else -np.inf)
    return None


def test_exact_halves_round_up_never_to_even():
    checked = 0
    for k in range(0, 255, 2):  # an even k: ties-to-even would keep k
        n = _exact_half(k)
        if n is None:
            continue
        assert encode_normal((n, 0.0, 0.0))[0] == k + 1, k
        checked += 1
    assert checked > 50


def test_the_encoding_matches_exact_arithmetic():
    rng = np.random.default_rng(11)
    values = np.concatenate([rng.uniform(-1, 1, 2000), [-1.0, 0.0, 1.0]])
    for n in values:
        exact = math.floor(
            Fraction(255) * (Fraction(float(n)) + 1) / 2 + Fraction(1, 2)
        )
        computed = int(encode_normal((n, n, n))[0])
        # The two agree except within floating rounding of a half.
        if computed != exact:
            assert abs(255 * (n + 1) / 2 - (exact - 0.5)) < 1e-9


@pytest.mark.parametrize("bad", [(math.nan, 0, 1), (0, math.inf, 0), (1.5, 0, 0)])
def test_the_encoding_refuses_non_finite_or_out_of_range_components(bad):
    with pytest.raises(ValueError):
        encode_normal(bad)


# Stylize: every look gives the same maps, at the colour's coverage


COLORS = tuple((index * 30, index * 30, index * 30) for index in range(8))
IDENTITIES = Identities(("steel", "cloth", "skin"))


def captured(i, factor=2, size=(6, 8)):
    """A supersampled frame of `size` reduced pixels with partial colour
    coverage, two materials and normal and depth samples with holes."""
    rng = np.random.default_rng(40 + i)
    height, width = size[0] * factor, size[1] * factor
    pixels = rng.integers(0, 256, (height, width, 4), dtype=np.uint8)
    pixels[..., 3] = np.where(rng.random((height, width)) < 0.6, 255, 0)
    normal = rng.normal(size=(height, width, 3)).astype(np.float32)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    depth = rng.uniform(-3.0, 3.0, (height, width)).astype(np.float32)
    hole = rng.random((height, width)) < 0.3
    normal[hole], depth[hole] = 0.0, np.nan
    named = {
        IDENTITY: rng.integers(-1, 3, (height, width), dtype=np.int32),
        SHADE: rng.integers(0, 256, (height, width), dtype=np.uint8),
        NORMAL: normal,
        DEPTH: depth,
    }
    return ImageFrame(
        FrameAddress("s", "default", "walk", i, i / 4), pixels, {"i": i}, named
    )


LOOKS = {
    "plain": (stylize.plain, {}),
    "plain-palette": (stylize.plain, {"palette": COLORS}),
    "mode": (stylize.mode, {}),
    "mode-palette": (stylize.mode, {"palette": COLORS}),
    "plain-library": (
        stylize.plain,
        {"palette": COLORS, "library": None, "shade_range": (84, 191)},
    ),
    "mode-library": (
        stylize.mode,
        {"palette": COLORS, "library": None, "shade_range": (84, 191)},
    ),
}


def styled(look, frames, factor=2):
    reduce, options = LOOKS[look]
    options = dict(options)
    if "library" in options:
        options["library"] = library(entries={"steel": {"uses": "metal"}})
    return reduce(
        frames, factor, identities=IDENTITIES, pixels_per_meter=12.5, **options
    )


@pytest.mark.parametrize("look", list(LOOKS))
def test_the_maps_have_the_colour_s_coverage_under_every_look(look):
    for frame in styled(look, [captured(i) for i in range(3)]):
        covered = frame.pixels[..., 3] == 255
        assert covered.any() and not covered.all()
        normals, depths = frame.buffers[NORMAL_MAP], frame.buffers[DEPTH_MAP]
        assert normals.shape == (*covered.shape, 3) and depths.shape == covered.shape
        lengths = np.linalg.norm(normals, axis=-1)
        np.testing.assert_allclose(lengths[covered], 1.0, atol=1e-12)
        assert (lengths[~covered] == 0).all() and (depths[~covered] == 0).all()


def test_every_look_gives_the_same_maps_where_the_coverage_agrees():
    # Coverage is decided the same way under every look, so the maps are
    # identical: the reduction, palette and library change only colours.
    results = {look: styled(look, [captured(i) for i in range(3)]) for look in LOOKS}
    reference = results["plain"]
    for look, frames in results.items():
        for a, b in zip(reference, frames, strict=True):
            np.testing.assert_array_equal(a.pixels[..., 3], b.pixels[..., 3])
            for name in (NORMAL_MAP, DEPTH_MAP):
                np.testing.assert_array_equal(a.buffers[name], b.buffers[name], look)


def test_a_block_spanning_two_materials_blends_both_normals_under_a_library():
    a, b = unit(1, 0, 1), unit(-1, 0, 1)
    pixels = np.full((2, 2, 4), 255, dtype=np.uint8)
    frame = ImageFrame(
        FrameAddress("s", "default", "walk", 0, 0.0),
        pixels,
        {},
        {
            IDENTITY: np.array([[0, 0], [1, 1]], dtype=np.int32),
            SHADE: np.full((2, 2), 137, dtype=np.uint8),
            NORMAL: np.array([[a, a], [b, b]], dtype=np.float32),
            DEPTH: np.array([[0.1, 0.1], [0.3, 0.3]], dtype=np.float32),
        },
    )
    (reduced,) = styled("mode-library", [frame])
    np.testing.assert_allclose(reduced.buffers[NORMAL_MAP][0, 0], UP, atol=1e-7)
    assert reduced.buffers[DEPTH_MAP][0, 0] == math.floor(16 * 0.2 * 12.5 + 0.5) / 16


def test_a_frame_needs_both_normal_and_depth_and_a_scale():
    frame = captured(0)
    del frame.buffers[DEPTH]
    with pytest.raises(ValueError, match="both normal and depth"):
        stylize.plain([frame], 2, pixels_per_meter=1.0)
    with pytest.raises(ValueError, match="pixels_per_meter"):
        stylize.plain([captured(0)], 2)


@pytest.mark.parametrize("factor", [1, 2, 3])
@pytest.mark.parametrize("look", ["plain", "mode-library"])
def test_stylize_releases_every_supersampled_array_before_the_next_frame(look, factor):
    held = []

    def capture():
        for i in range(3):
            assert all(ref() is None for ref in held), "a previous frame is held"
            frame = captured(i, factor)
            held.extend(weakref.ref(a) for a in [frame.pixels, *frame.buffers.values()])
            yield frame
            del frame

    result = styled(look, capture(), factor)
    assert all(ref() is None for ref in held)
    for i, frame in enumerate(result):
        assert frame.address.direction == i and frame.metadata == {"i": i}
        assert set(frame.buffers) == {NORMAL_MAP, DEPTH_MAP}
        for array in frame.buffers.values():
            assert array.base is None or array.base.size == array.size


def test_cleanup_passes_the_maps_through():
    frames = styled("plain", [captured(i) for i in range(2)])
    passed = cleanup.passthrough(frames)
    for a, b in zip(frames, passed, strict=True):
        assert a is b


# The command: decoded depth through stylize and cleanup to export


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def exported(setup, capsys, monkeypatch, *options, supersample="1"):
    """The frames and settings exportimages.encode receives."""
    seen = {}
    real = exportimages.encode

    def recording(frames, **kwargs):
        seen["frames"], seen["settings"] = tuple(frames), kwargs["settings"]
        return real(frames, **kwargs)

    monkeypatch.setattr(exportimages, "encode", recording)
    argv = setup.argv(*options)
    at = argv.index("--supersample")
    argv[at + 1] = supersample
    status, _, err = run(capsys, argv)
    assert status == 0, err
    return seen["frames"], seen["settings"]


@pytest.mark.parametrize("supersample", ["1", "2", "3"])
def test_captured_depth_reaches_export_in_sheet_pixels(
    setup, capsys, monkeypatch, supersample
):
    depths_m = [0.5, -0.25, 0.0, 0.1234567]
    setup.configure(depths=depths_m)
    frames, settings = exported(
        setup, capsys, monkeypatch, "--no-preview", supersample=supersample
    )
    ppm = settings.ppm
    assert ppm != int(ppm), "a fitted, non-whole scale"
    assert len(frames) == (4 + 3) * 8
    for i, frame in enumerate(frames):
        covered = frame.pixels[..., 3] == 255
        assert covered.any() and not covered.all()
        meters = float(np.float32(depths_m[i % len(depths_m)]))
        expected = math.floor(16 * meters * ppm + 0.5) / 16
        depths = frame.buffers[DEPTH_MAP]
        assert (depths[covered] == expected).all(), (i, depths[covered][0], expected)
        assert (depths[~covered] == 0).all()
        normals = frame.buffers[NORMAL_MAP]
        # Within the 16-bit capture's step: 0 is stored as 32768 of 65535.
        np.testing.assert_allclose(
            normals[covered], np.broadcast_to(UP, normals[covered].shape), atol=3e-5
        )
        assert (normals[~covered] == 0).all()
    signs = {np.sign(frame.buffers[DEPTH_MAP].sum()) for frame in frames}
    assert signs == {-1.0, 0.0, 1.0}


def test_the_maps_reach_export_with_their_frames_addresses_and_metadata(
    setup, capsys, monkeypatch
):
    loaded = []
    real_plain = stylize.plain

    def recording(frames, factor, **kwargs):
        def watched():
            for frame in frames:
                loaded.append((frame.address, dict(frame.metadata)))
                yield frame
                del frame

        return real_plain(watched(), factor, **kwargs)

    monkeypatch.setattr(stylize, "plain", recording)
    frames, _ = exported(setup, capsys, monkeypatch, "--no-preview")
    assert [(f.address, dict(f.metadata)) for f in frames] == loaded
    assert all(set(f.buffers) == {NORMAL_MAP, DEPTH_MAP} for f in frames)


def test_the_maps_change_no_output(setup, capsys):
    # The sheet, JSON and previews are the same whatever the depths reduce to.
    setup.configure(depths=[0.0])
    assert run(capsys, setup.argv())[0] == 0
    flat = setup.listing()
    setup.configure(depths=[3.5, -800.0])
    assert run(capsys, setup.argv())[0] == 0
    assert setup.listing() == flat


def test_imageops_offers_the_reduction_and_the_encoding():
    assert imageops.reduce_normal_depth is reduce_normal_depth
    assert imageops.encode_normal is encode_normal
