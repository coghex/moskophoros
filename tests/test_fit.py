import pytest

from moskophoros.fit import (
    Bounds,
    CellOverflow,
    Fit,
    Measurement,
    UsageError,
    resolve,
)
from moskophoros.sampling import FrameAddress


def address(clip="walk", direction=0, time_s=0.0):
    return FrameAddress("hero", "default", clip, direction, time_s)


def one_frame(left, right, up, down, height=1.0):
    return {address(): Measurement(Bounds(left, right, up, down), height)}


# Case 1: both --ppm and --cell (fixed)


def test_fixed_scale_and_cell():
    # gx = floor(48/2) = 24; gy = 40 - 1 - ceil(0.25 · 10 = 2.5) = 36.
    result = resolve(one_frame(1.0, 0.5, 2.0, 0.25), ppm=10, cell=(48, 40))
    assert result == Fit(10, (48, 40), (24, 36), ())


def test_fixed_odd_cell_rounds_the_ground_column_down():
    # gx = floor(47/2) = 23.
    assert resolve(one_frame(1.0, 0.5, 2.0, 0.25), ppm=10, cell=(47, 40)).ground_px == (
        23,
        36,
    )


# Case 2: only --ppm


def test_ppm_only_computes_the_cell():
    # max(L, R)·ppm = 12.3, so W = 2·(13 + 1) = 28.
    # H = ceil(20) + ceil(2.5) + 2 = 20 + 3 + 2 = 25.
    # gx = 28/2 = 14; gy = 25 - 1 - 3 = 21.
    result = resolve(one_frame(1.23, 0.5, 2.0, 0.25), ppm=10)
    assert result == Fit(10, (28, 25), (14, 21), ())


def test_ppm_only_uses_the_wider_side():
    # Here R is the wider side: ceil(0.71 · 10 = 7.1) = 8, so W = 2·(8 + 1) = 18.
    assert resolve(one_frame(0.2, 0.71, 1.0, 0.0), ppm=10).cell == (18, 12)


# Case 3: auto-fit


def test_auto_fit_in_the_default_cell():
    # 64×64, gx = 32. Limits: L: (32 - 1)/1 = 31; R: (64 - 32 - 1)/2 = 15.5;
    # vertical: (64 - 2 - 1)/(1.5 + 0.5) = 30.5. ppm = 15.5.
    # gy = 64 - 1 - ceil(0.5 · 15.5 = 7.75) = 55.
    result = resolve(one_frame(1.0, 2.0, 1.5, 0.5))
    assert result == Fit(15.5, (64, 64), (32, 55), ())


def test_auto_fit_in_a_given_cell():
    # 40×30, gx = 20. Limits: L: 19/0.5 = 38; R: 19/1 = 19; vertical: 27/0.9 = 30.
    # ppm = 19; gy = 30 - 1 - ceil(0.4 · 19 = 7.6) = 21.
    result = resolve(one_frame(0.5, 1.0, 0.5, 0.4), cell=(40, 30))
    assert result.ppm == 19
    assert (result.cell, result.ground_px) == ((40, 30), (20, 21))


def test_auto_fit_skips_a_constraint_whose_extent_is_0():
    # A cell 3 wide has gx = 1 and gx - m = 0, so a left or right extent
    # would allow no scale at all. Both are 0 here, so only the vertical
    # limit applies: (64 - 3)/(1 + 1) = 30.5. gy = 64 - 1 - ceil(30.5) = 32.
    result = resolve(one_frame(0.0, 0.0, 1.0, 1.0), cell=(3, 64))
    assert result == Fit(30.5, (3, 64), (1, 32), ())


def test_auto_fit_skips_a_zero_vertical_extent():
    # U + D = 0: only the horizontal limits apply. L: 31/2 = 15.5; R: 31/1 = 31.
    result = resolve(one_frame(2.0, 1.0, 0.0, 0.0), cell=(64, 4))
    assert result == Fit(15.5, (64, 4), (32, 3), ())


def test_bounds_aggregate_over_every_frame():
    # Each maximum comes from a different frame; together they are the
    # bounds of test_auto_fit_in_the_default_cell.
    measurements = {
        address(direction=0): Measurement(Bounds(1.0, 0.1, 0.2, 0.1), 0.5),
        address(direction=1): Measurement(Bounds(0.3, 2.0, 0.2, 0.1), 0.5),
        address(direction=2): Measurement(Bounds(0.3, 0.1, 1.5, 0.1), 0.5),
        address(direction=3): Measurement(Bounds(0.3, 0.1, 0.2, 0.5), 0.5),
    }
    assert resolve(measurements) == Fit(15.5, (64, 64), (32, 55), ())
    # The same aggregate gives one shared configuration in case 2 too:
    # W = 2·(ceil(20) + 1) = 42; H = ceil(15) + ceil(5) + 2 = 22; gy = 22 - 1 - 5.
    assert resolve(measurements, ppm=10) == Fit(10, (42, 22), (21, 16), ())


# --ground-px


def test_ground_px_replaces_the_fixed_ground_point():
    result = resolve(
        one_frame(1.0, 0.5, 2.0, 0.25), ppm=10, cell=(48, 40), ground_px=(24, 30)
    )
    assert result == Fit(10, (48, 40), (24, 30), ())


def test_ground_px_replaces_the_computed_ground_point():
    # Case 2 cell 28×25 as above; extents 12.3, 5, 20 and 2.5 fit (14, 22).
    result = resolve(one_frame(1.23, 0.5, 2.0, 0.25), ppm=10, ground_px=(14, 22))
    assert result == Fit(10, (28, 25), (14, 22), ())


def test_ground_px_applies_after_auto_fit():
    # ppm is still 15.5, computed with gx = 32. At (30, 55) the extents 15.5,
    # 31, 23.25 and 7.75 fit within 30, 34, 55 and 9.
    result = resolve(one_frame(1.0, 2.0, 1.5, 0.5), ground_px=(30, 55))
    assert result == Fit(15.5, (64, 64), (30, 55), ())


@pytest.mark.parametrize(
    ("options", "side", "pixels"),
    [
        # Case 1: bottom 2.5 > 40 - 38 = 2 by 0.5.
        ({"ppm": 10, "cell": (48, 40), "ground_px": (24, 38)}, "bottom", 1),
        # Case 2: left 12.3 > 12 by 0.3.
        ({"ppm": 10, "ground_px": (12, 21)}, "left", 1),
    ],
)
def test_ground_px_can_cause_overflow(options, side, pixels):
    with pytest.raises(CellOverflow) as raised:
        resolve(one_frame(1.23, 0.5, 2.0, 0.25), **options)
    assert raised.value.frames == ((address(), {side: pixels}),)


def test_ground_px_after_auto_fit_can_cause_overflow():
    # ppm 15.5: the right extent 31 passes 64 - 40 = 24 by 7.
    with pytest.raises(CellOverflow) as raised:
        resolve(one_frame(1.0, 2.0, 1.5, 0.5), ground_px=(40, 50))
    assert raised.value.frames == ((address(), {"right": 7}),)


# Usage errors


def test_auto_fit_needs_a_nonzero_extent():
    with pytest.raises(UsageError, match="give --ppm") as raised:
        resolve(one_frame(0.0, 0.0, 0.0, 0.0))
    assert raised.value.exit_code == 2


def test_ppm_with_zero_extents_is_not_a_usage_error():
    # W = 2·(0 + 1) = 2; H = 0 + 0 + 2 = 2.
    assert resolve(one_frame(0.0, 0.0, 0.0, 0.0), ppm=10) == Fit(10, (2, 2), (1, 1), ())


@pytest.mark.parametrize(
    ("bounds", "cell"),
    [
        ((1.0, 0.0, 0.0, 0.0), (2, 64)),  # left: gx - m = 1 - 1 = 0
        ((1.0, 0.0, 0.0, 0.0), (1, 64)),  # left: gx - m = 0 - 1 = -1
        ((0.0, 1.0, 0.0, 0.0), (2, 64)),  # right: W - gx - m = 2 - 1 - 1 = 0
        ((0.0, 0.0, 1.0, 0.0), (64, 3)),  # vertical: H - 2m - 1 = 0
    ],
)
def test_auto_fit_rejects_a_cell_too_small(bounds, cell):
    with pytest.raises(UsageError, match="too small") as raised:
        resolve(one_frame(*bounds), cell=cell)
    assert raised.value.exit_code == 2
    assert f"the {cell[0]}x{cell[1]} cell" in str(raised.value)
    assert "larger --cell" in str(raised.value)


@pytest.mark.parametrize(
    ("bounds", "cell"),
    [
        # W = 2·(ceil(2047) + 1) = 4096, with H = 2.
        ((2047.0, 0.0, 0.0, 0.0), (4096, 2)),
        # H = ceil(4094) + 0 + 2 = 4096, with W = 2.
        ((0.0, 0.0, 4094.0, 0.0), (2, 4096)),
        ((0.0, 0.0, 4093.0, 1.0), (2, 4096)),
    ],
)
def test_a_computed_cell_of_4096_is_accepted(bounds, cell):
    assert resolve(one_frame(*bounds), ppm=1).cell == cell


@pytest.mark.parametrize(
    ("bounds", "size"),
    [
        # Width is always even: 2·(ceil(2048) + 1) = 4098.
        ((2048.0, 0.0, 0.0, 0.0), "4098x2"),
        # Height reaches 4097 exactly: ceil(4095) + 0 + 2.
        ((0.0, 0.0, 4095.0, 0.0), "2x4097"),
    ],
)
def test_a_computed_cell_over_4096_is_rejected(bounds, size):
    with pytest.raises(UsageError) as raised:
        resolve(one_frame(*bounds), ppm=1)
    assert raised.value.exit_code == 2
    message = str(raised.value)
    assert f"a {size} cell" in message
    assert "smaller --ppm" in message


# Overflow


FIXED = {"ppm": 10, "cell": (40, 40), "ground_px": (20, 30)}


@pytest.mark.parametrize(
    ("bounds", "side", "pixels"),
    [
        # left: 2.02 · 10 = 20.2 passes gx = 20 by 0.2, reported as 1 px.
        ((2.02, 0.0, 0.0, 0.0), "left", 1),
        # right: 25 passes 40 - 20 = 20 by 5.
        ((0.0, 2.5, 0.0, 0.0), "right", 5),
        # top: 31.5 passes gy = 30 by 1.5, reported as 2 px.
        ((0.0, 0.0, 3.15, 0.0), "top", 2),
        # bottom: 10.1 passes 40 - 30 = 10 by 0.1, reported as 1 px.
        ((0.0, 0.0, 0.0, 1.01), "bottom", 1),
    ],
)
def test_overflow_on_each_side(bounds, side, pixels):
    with pytest.raises(CellOverflow) as raised:
        resolve(one_frame(*bounds), **FIXED)
    assert raised.value.exit_code == 4
    assert raised.value.frames == ((address(), {side: pixels}),)
    assert f"{side} {pixels} px" in str(raised.value)


def test_overflowing_frames_are_listed_in_request_order():
    measurements = {
        address("walk", 0, 0.0): Measurement(Bounds(2.5, 2.5, 0.0, 0.0), 1.0),
        address("walk", 1, 0.0): Measurement(Bounds(1.0, 1.0, 1.0, 0.5), 1.0),
        address("walk", 1, 0.25): Measurement(Bounds(0.0, 0.0, 3.15, 1.01), 1.0),
        address("attack", 0, 1.5): Measurement(Bounds(0.0, 2.0625, 0.0, 0.0), 1.0),
    }
    with pytest.raises(CellOverflow) as raised:
        resolve(measurements, **FIXED)
    assert raised.value.frames == (
        (address("walk", 0, 0.0), {"left": 5, "right": 5}),
        (address("walk", 1, 0.25), {"top": 2, "bottom": 1}),
        (address("attack", 0, 1.5), {"right": 1}),
    )
    assert str(raised.value).splitlines()[1:] == [
        "  clip 'walk', direction 0, time 0.0 s: left 5 px, right 5 px",
        "  clip 'walk', direction 1, time 0.25 s: top 2 px, bottom 1 px",
        "  clip 'attack', direction 0, time 1.5 s: right 1 px",
    ]
    assert str(raised.value).startswith(
        "the subject overflows the 40x40 cell at 10 pixels per meter with "
        "ground pixel (20, 30)"
    )


def test_bounds_exactly_on_the_edges_fit():
    # 20, 20, 30 and 10 pixels reach exactly to each edge: the margin is not
    # required when checking, and nothing is changed.
    result = resolve(one_frame(2.0, 2.0, 3.0, 1.0), **FIXED)
    assert result == Fit(10, (40, 40), (20, 30), ())


def test_bounds_inside_the_margin_fit():
    # 19.5 px reaches into the one-pixel margin on every side without
    # crossing an edge.
    result = resolve(one_frame(1.95, 1.95, 2.95, 0.95), **FIXED)
    assert result == Fit(10, (40, 40), (20, 30), ())


def test_a_fixed_configuration_is_never_shrunk():
    # The same bounds auto-fit without overflow, but fixed values that are
    # too small fail rather than change.
    bounds = one_frame(1.0, 2.0, 1.5, 0.5)
    assert resolve(bounds, cell=(64, 64)).ppm == 15.5
    with pytest.raises(CellOverflow) as raised:
        resolve(bounds, ppm=20, cell=(64, 64))
    # gx = 32, gy = 64 - 1 - ceil(10) = 53. Right: 40 > 32 by 8.
    assert raised.value.frames == ((address(), {"right": 8}),)


@pytest.mark.parametrize("options", [{"ppm": 10}, {}, {"cell": (40, 30)}])
def test_cases_2_and_3_without_ground_px_never_overflow(options):
    # Bounds that overflow the fixed configuration above fit when the cell or
    # scale is computed.
    measurements = {
        address("walk", 0, 0.0): Measurement(Bounds(2.5, 2.5, 0.0, 0.0), 1.0),
        address("walk", 1, 0.25): Measurement(Bounds(0.0, 0.0, 3.15, 1.01), 1.0),
        address("attack", 0, 1.5): Measurement(Bounds(0.0, 2.0625, 0.0, 0.0), 1.0),
    }
    with pytest.raises(CellOverflow):
        resolve(measurements, **FIXED)
    resolve(measurements, **options)


# Unit warning


@pytest.mark.parametrize("height", [0.01, 1.0, 100.0])
def test_no_unit_warning_from_0_01_to_100_m(height):
    assert resolve(one_frame(1.0, 1.0, 1.0, 0.0, height)).warnings == ()


@pytest.mark.parametrize("height", [0.0099, 100.01])
def test_a_unit_warning_outside_0_01_to_100_m(height):
    result = resolve(one_frame(1.0, 1.0, 1.0, 0.0, height))
    (warning,) = result.warnings
    assert f"{height!r} m tall" in warning
    assert result.ppm == 31  # resolution still succeeds


def test_the_unit_warning_uses_the_tallest_height_not_the_bounds():
    # The projected extents are tiny, but the tallest frame is 150 m: the
    # warning reads height_m, and the shortest frame does not hide it.
    measurements = {
        address(direction=0): Measurement(Bounds(0.001, 0.001, 0.001, 0.0), 2.0),
        address(direction=1): Measurement(Bounds(0.001, 0.001, 0.001, 0.0), 150.0),
    }
    (warning,) = resolve(measurements).warnings
    assert "150.0 m tall" in warning
    # And the reverse: large extents, but every height in range.
    measurements = {
        address(direction=0): Measurement(Bounds(500.0, 500.0, 500.0, 0.0), 0.5),
    }
    assert resolve(measurements).warnings == ()


# Huge but finite values. Pixel arithmetic is exact, so these neither raise
# Python's own OverflowError nor round.


def test_a_huge_ppm_gives_the_cell_size_usage_error():
    # W = 2·(ceil(2 · 1e308) + 1), computed exactly.
    with pytest.raises(UsageError, match="smaller --ppm") as raised:
        resolve(one_frame(2.0, 1.0, 1.0, 0.0), ppm=1e308)
    assert raised.value.exit_code == 2
    width = 2 * (2 * int(1e308) + 1)
    assert f"a {width}x" in str(raised.value)


def test_a_huge_fixed_ppm_reports_overflow():
    # gx = 32; gy = 64 - 1 - 0 = 63. Left 2e308 - 32, right 1e308 - 32 and
    # top 1e308 - 63, all exact integers.
    with pytest.raises(CellOverflow) as raised:
        resolve(one_frame(2.0, 1.0, 1.0, 0.0), ppm=1e308, cell=(64, 64))
    big = int(1e308)
    assert raised.value.exit_code == 4
    assert raised.value.frames == (
        (address(), {"left": 2 * big - 32, "right": big - 32, "top": big - 63}),
    )


def test_a_huge_ground_px_reports_overflow_exactly():
    # ppm 15.5 (as in test_auto_fit_in_the_default_cell). The right edge is at
    # 64 - gx, so the right overshoot is 31 - 64 + gx, exactly.
    gx = 9007199254741093
    with pytest.raises(CellOverflow) as raised:
        resolve(one_frame(1.0, 2.0, 1.5, 0.5), ground_px=(gx, 55))
    assert raised.value.frames == ((address(), {"right": 31 - 64 + gx}),)
    gx = 10**309
    with pytest.raises(CellOverflow) as raised:
        resolve(one_frame(1.0, 2.0, 1.5, 0.5), ground_px=(gx, 55))
    assert raised.value.frames == ((address(), {"right": 31 - 64 + gx}),)


def test_extents_too_small_for_a_finite_auto_fit_scale():
    # 31 / 1e-320 is past the largest float.
    with pytest.raises(UsageError, match="give --ppm") as raised:
        resolve(one_frame(1e-320, 0.0, 0.0, 0.0))
    assert raised.value.exit_code == 2


def test_auto_fit_with_huge_extents():
    # U + D = 2e308 is past the largest float, but the limit is exact:
    # (64 - 2 - 1)/2e308 = 3.05e-307. gy = 64 - 1 - ceil(1e308 · 3.05e-307 = 30.5)
    # = 32.
    result = resolve(one_frame(0.0, 0.0, 1e308, 1e308))
    assert result.ppm == pytest.approx(3.05e-307)
    assert (result.cell, result.ground_px) == ((64, 64), (32, 32))
