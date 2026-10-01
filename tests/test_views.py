import math

import pytest

from moskophoros.views import (
    View,
    camera_basis,
    directions,
    facing,
    rotation_matrix,
)

ISO_TRUE = math.degrees(math.atan(1 / math.sqrt(2)))
EIGHT = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
EIGHT_LABELS = [
    "south",
    "south-east",
    "east",
    "north-east",
    "north",
    "north-west",
    "west",
    "south-west",
]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


# Camera basis


def test_basis_at_0_looks_horizontally():
    basis = camera_basis(0)
    assert basis.direction == (0.0, 0.0, 1.0)
    assert basis.right == (1.0, 0.0, 0.0)
    assert basis.up == (0.0, 1.0, 0.0)


def test_basis_at_90_looks_straight_down_with_up_minus_z():
    basis = camera_basis(90)
    assert basis.direction == (0.0, 1.0, 0.0)
    assert basis.right == (1.0, 0.0, 0.0)
    assert basis.up == (0.0, 0.0, -1.0)


@pytest.mark.parametrize(
    ("pitch", "sin", "cos"),
    [
        (30, 0.5, math.sqrt(3) / 2),
        # tan p = 1/√2, so sin p = 1/√3 and cos p = √2/√3.
        (ISO_TRUE, 1 / math.sqrt(3), math.sqrt(2) / math.sqrt(3)),
    ],
)
def test_basis_at_intermediate_pitches(pitch, sin, cos):
    basis = camera_basis(pitch)
    assert basis.direction == pytest.approx((0.0, sin, cos))
    assert basis.right == (1.0, 0.0, 0.0)
    assert basis.up == pytest.approx((0.0, cos, -sin))


@pytest.mark.parametrize("pitch", [0, 12.5, 30, ISO_TRUE, 60, 90])
def test_basis_is_orthonormal(pitch):
    basis = camera_basis(pitch)
    vectors = (basis.direction, basis.right, basis.up)
    for a in vectors:
        assert dot(a, a) == pytest.approx(1.0)
    for a, b in ((0, 1), (0, 2), (1, 2)):
        assert dot(vectors[a], vectors[b]) == pytest.approx(0.0, abs=1e-15)


@pytest.mark.parametrize("pitch", [-0.001, 90.001, math.nan])
def test_basis_rejects_a_pitch_out_of_range(pitch):
    with pytest.raises(ValueError, match="pitch"):
        camera_basis(pitch)


# Direction angles and labels


@pytest.mark.parametrize(
    ("view", "angles", "labels"),
    [
        (View(90.0, 8, 0.0), EIGHT, EIGHT_LABELS),  # topdown
        (View(0.0, 2, 90.0), [90.0, 270.0], ["east", "west"]),  # side
        (View(30.0, 8, 0.0), EIGHT, EIGHT_LABELS),  # iso
        (View(ISO_TRUE, 8, 0.0), EIGHT, EIGHT_LABELS),  # iso-true
        (View(30.0, 3, 10.0), [10.0, 130.0, 250.0], [None, None, None]),
        (
            View(30.0, 4, -90.0),
            [270.0, 0.0, 90.0, 180.0],
            ["west", "south", "east", "north"],
        ),
        (View(30.0, 2, -22.5), [337.5, 157.5], [None, None]),
        (View(30.0, 1, 405.0), [45.0], ["south-east"]),
        (
            View(30.0, 16, 0.0),
            [k * 22.5 for k in range(16)],
            [EIGHT_LABELS[k // 2] if k % 2 == 0 else None for k in range(16)],
        ),
    ],
)
def test_direction_angles_and_labels(view, angles, labels):
    result = directions(view)
    assert [d.index for d in result] == list(range(view.directions))
    assert [d.angle for d in result] == angles
    assert [d.label for d in result] == labels


@pytest.mark.parametrize("start", [-1e-20, -360.0, -720.0, 360.0])
def test_angles_stay_in_0_to_360(start):
    (direction,) = directions(View(30.0, 1, start))
    assert direction.angle == 0.0
    assert direction.label == "south"


@pytest.mark.parametrize("count", [0, -1, 2.0, True])
def test_direction_count_must_be_a_positive_integer(count):
    with pytest.raises(ValueError, match="direction count"):
        directions(View(30.0, count, 0.0))


# Subject rotation


@pytest.mark.parametrize(
    ("rotation", "faces"),
    [
        (0, (0.0, 0.0, 1.0)),  # toward the viewer
        (90, (1.0, 0.0, 0.0)),  # screen right
        (180, (0.0, 0.0, -1.0)),  # away
        (270, (-1.0, 0.0, 0.0)),  # screen left
        (-90, (-1.0, 0.0, 0.0)),
        (450, (1.0, 0.0, 0.0)),
    ],
)
def test_facing_at_quarter_turns(rotation, faces):
    assert facing(rotation) == faces


def test_facing_between_quarter_turns():
    half = math.sqrt(0.5)
    assert facing(45) == pytest.approx((half, 0.0, half))
    assert facing(135) == pytest.approx((half, 0.0, -half))


def test_rotation_is_counter_clockwise_seen_from_above():
    # Seen from +Y, the turn from +Z to +X is counter-clockwise (x right, z
    # down the page), the same sense as the right-hand rule about +Y.
    matrix = rotation_matrix(30)
    sin, cos = 0.5, math.sqrt(3) / 2
    expected = ((cos, 0.0, sin), (0.0, 1.0, 0.0), (-sin, 0.0, cos))
    for row, expected_row in zip(matrix, expected, strict=True):
        assert row == pytest.approx(expected_row)


def test_rotation_adds_the_model_yaw():
    result = directions(View(30.0, 4, 0.0, model_yaw=90.0))
    assert [d.angle for d in result] == [0.0, 90.0, 180.0, 270.0]
    assert [d.rotation for d in result] == [90.0, 180.0, 270.0, 0.0]
    # The yaw turns every direction a further 90°: a subject facing +Z faces
    # screen right at direction 0 and away at direction 1.
    assert [facing(d.rotation) for d in result] == [
        (1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
        (-1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    ]


def test_directions_are_deterministic():
    view = View(ISO_TRUE, 7, -13.25, model_yaw=12.5)
    assert directions(view) == directions(view)


# Large finite angles. The expected reductions use exact integer arithmetic:
# 1e20 is exactly the integer 10**20, which is 280 mod 360, and -10**20 is 80.


def test_large_start_angles_keep_their_offsets():
    result = directions(View(30.0, 8, 1e20))
    assert [d.angle for d in result] == [280, 325, 10, 55, 100, 145, 190, 235]
    assert [d.angle for d in directions(View(30.0, 4, -1e20))] == [80, 170, 260, 350]


def test_large_model_yaws_keep_their_offsets():
    result = directions(View(30.0, 4, 0.0, model_yaw=1e20))
    assert [d.rotation for d in result] == [280, 10, 100, 190]


@pytest.mark.parametrize("large", [1e20, -1e20, 1e300, -123456789.0])
def test_rotation_is_periodic_for_large_angles(large):
    small = int(large) % 360
    assert facing(large) == pytest.approx(facing(small), abs=1e-15)
    for row, small_row in zip(
        rotation_matrix(large), rotation_matrix(small), strict=True
    ):
        assert row == pytest.approx(small_row, abs=1e-15)
