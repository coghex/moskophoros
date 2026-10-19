import math

import pytest

from moskophoros import views
from moskophoros.cli import PRESETS
from moskophoros.views import (
    UNIT_TOLERANCE,
    View,
    camera_basis,
    directions,
    facing,
    heading,
    is_unit,
    normalise,
    pitch_direction,
    rotation_matrix,
    subject_basis,
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


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


# Camera basis (design §Camera and directions, Basis)


def bits(vector):
    """`vector`'s components as their exact bits, signed zeros included."""
    return tuple(float(component).hex() for component in vector)


def legacy_basis(pitch):
    """The pitch-only camera as `camera_basis(pitch)` built it before the
    camera had a direction: toward the camera, right and up."""
    sin, cos = views._sin_cos(pitch)
    return (0.0, sin, cos), (1.0, 0.0, 0.0), (0.0, cos, 0.0 - sin)


def project(point, basis):
    """`point`'s screen position: its right and up components."""
    return dot(point, basis.right), dot(point, basis.up)


PITCHES = [0, 1e-9, 12.5, 30, ISO_TRUE, 45, 47.25, 60, 89.999, 90]


@pytest.mark.parametrize(
    "pitch", [*PITCHES, *(preset.pitch for preset in PRESETS.values())]
)
def test_a_pitch_gives_today_s_basis_bit_for_bit(pitch):
    toward, right, up = legacy_basis(pitch)
    direction = pitch_direction(pitch)
    assert bits(direction) == bits(tuple(0.0 - value for value in toward))
    for basis in (camera_basis(direction), subject_basis(direction)):
        assert bits(basis.forward) == bits(direction)
        assert bits(basis.right) == bits(right)
        assert bits(basis.up) == bits(up)


def test_a_pitch_is_the_direction_0_minus_sin_minus_cos():
    assert pitch_direction(0) == (0.0, 0.0, -1.0)
    assert pitch_direction(90) == (0.0, -1.0, 0.0)
    assert pitch_direction(30) == pytest.approx((0.0, -0.5, -math.sqrt(3) / 2))
    # Normalising it changes nothing: it is already within the tolerance.
    for pitch in PITCHES:
        assert bits(normalise(pitch_direction(pitch))) == bits(pitch_direction(pitch))


@pytest.mark.parametrize("pitch", [-0.001, 90.001, math.nan])
def test_a_pitch_out_of_range_is_refused(pitch):
    with pytest.raises(ValueError, match="pitch"):
        pitch_direction(pitch)


def test_straight_down_is_today_s_topdown():
    basis = camera_basis((0.0, -1.0, 0.0))
    assert (basis.right, basis.up) == ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0))
    assert camera_basis((0, -0.25, 0)) == basis


def test_straight_up_has_right_x_and_up_z():
    basis = camera_basis((0.0, 1.0, 0.0))
    assert (basis.right, basis.up) == ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))


@pytest.mark.parametrize(
    ("direction", "roll"),
    [
        ((0.3, -0.7, -0.2), 0.0),
        ((0.3, -0.7, -0.2), 0.37),
        ((-1.0, 0.25, 1.0), -0.5),
        ((1e-300, 1e-300, 0.0), 0.9),
        ((0.0, 1.0, 0.0), 0.25),
        ((0.1, 0.1, 0.1), -1.0),
    ],
)
def test_a_direction_and_roll_give_the_predicted_axes(direction, roll):
    basis = camera_basis(direction, roll)
    f = normalise(direction)
    horizontal = math.hypot(f[0], f[2])
    if horizontal == 0:
        r0 = (1.0, 0.0, 0.0)
    else:
        # normalise(f × Y), with f × Y = (−f_z, 0, f_x).
        r0 = (-f[2] / horizontal, 0.0, f[0] / horizontal)
    u0 = cross(r0, f)
    rho = roll * math.pi
    r = tuple(
        a * math.cos(rho) + b * math.sin(rho) for a, b in zip(r0, u0, strict=True)
    )
    u = tuple(
        b * math.cos(rho) - a * math.sin(rho) for a, b in zip(r0, u0, strict=True)
    )
    assert basis.forward == f
    assert basis.right == pytest.approx(r, abs=1e-15)
    assert basis.up == pytest.approx(u, abs=1e-15)
    vectors = (basis.forward, basis.right, basis.up)
    for a in vectors:
        assert dot(a, a) == pytest.approx(1.0)
    for a, b in ((0, 1), (0, 2), (1, 2)):
        assert dot(vectors[a], vectors[b]) == pytest.approx(0.0, abs=1e-15)
    # Right-handed: right × up is toward the camera, −f.
    assert cross(basis.right, basis.up) == pytest.approx(
        tuple(-value for value in f), abs=1e-15
    )


def test_a_half_roll_turns_the_top_of_the_picture_to_its_right():
    direction = pitch_direction(30)
    top = camera_basis(direction).up  # the point at the top of the picture
    rolled = camera_basis(direction, 0.5)
    assert project(top, rolled) == pytest.approx((1.0, 0.0), abs=1e-15)
    # r = u₀ and u = −r₀ exactly at a quarter turn.
    assert rolled.right == camera_basis(direction).up
    assert rolled.up == (-1.0, -0.0, -0.0)


def test_roll_minus_1_and_plus_1_give_the_same_basis():
    for direction in [(0.3, -0.7, -0.2), pitch_direction(30), (0.0, 1.0, 0.0)]:
        assert camera_basis(direction, -1.0) == camera_basis(direction, 1.0)


@pytest.mark.parametrize("roll", [-1.001, 1.5, math.nan, math.inf])
def test_a_roll_out_of_range_is_refused(roll):
    with pytest.raises(ValueError, match="roll"):
        camera_basis((0, 0, -1), roll)


# Labels under roll and an upward camera (D-18)


def test_labels_keep_their_names_under_a_half_roll_and_looking_up():
    names = [d.label for d in directions(View(8, 0.0))]
    assert names == EIGHT_LABELS
    east = facing(90)  # +X, screen right for a level, unrolled camera
    assert project(east, camera_basis(pitch_direction(30))) == pytest.approx((1.0, 0.0))
    # A half-turn roll turns the picture upside down: east faces screen left.
    assert project(east, camera_basis(pitch_direction(30), 1.0)) == (-1.0, 0.0)
    # Looking straight up, south (+Z) faces up the screen.
    assert project(facing(0), camera_basis((0.0, 1.0, 0.0))) == (0.0, 1.0)
    # Neither changes a name: they come from θ alone.
    assert [d.label for d in directions(View(8, 0.0))] == names


# The heading (D-10, D-18)


@pytest.mark.parametrize(
    ("direction", "heading_deg"),
    [
        ((0.0, -0.5, -1.0), 0.0),
        ((-1.0, 0.0, 0.0), 90.0),
        ((0.0, -0.5, 1.0), 180.0),
        ((1.0, -1.0, 0.0), 270.0),
        ((0.0, -1.0, 0.0), 0.0),
        ((0.0, 1.0, 0.0), 0.0),
    ],
)
def test_the_heading_turns_south_to_face_the_camera(direction, heading_deg):
    assert heading(direction) == pytest.approx(heading_deg)
    f = normalise(direction)
    if f[0] or f[2]:
        horizontal = math.hypot(f[0], f[2])
        assert facing(heading(direction)) == pytest.approx(
            (-f[0] / horizontal, 0.0, -f[2] / horizontal)
        )


def turned(point, rotation):
    return tuple(dot(row, point) for row in rotation_matrix(rotation))


@pytest.mark.parametrize("roll", [0.0, 0.3, -1.0])
@pytest.mark.parametrize("pitch", [0.0, 30.0, 72.5])
@pytest.mark.parametrize("compass", [0.0, 37.0, 90.0, 200.0, 315.5])
def test_a_direction_s_heading_changes_no_picture_and_no_label(roll, pitch, compass):
    # The same steepness looking along another compass heading.
    _, y, z = pitch_direction(pitch)
    a = math.radians(compass)
    direction = (z * math.sin(a), y, z * math.cos(a))
    world = camera_basis(direction, roll)
    reference = subject_basis(direction, roll)
    assert reference == pytest.approx(camera_basis(pitch_direction(pitch), roll))
    points = [(0.3, 1.2, -0.4), (-1.0, 0.0, 0.5), (0.0, 2.0, 0.0)]
    for d in directions(View(8, 0.0, model_yaw=12.5)):
        for point in points:
            # The subject turns by θ + yaw from the camera's heading.
            in_world = project(turned(point, heading(direction) + d.rotation), world)
            in_reference = project(turned(point, d.rotation), reference)
            assert in_world == pytest.approx(in_reference, abs=1e-12)
    assert [d.label for d in directions(View(8, 0.0))] == EIGHT_LABELS


# Normalising a direction


def test_a_direction_is_normalised_to_length_1():
    assert normalise((0, 0, -2)) == (0.0, 0.0, -1.0)
    assert normalise((3, 0, 4)) == (0.6, 0.0, 0.8)


@pytest.mark.parametrize(
    ("vector", "expected"),
    [
        ((1e-300, 1e-300, 0), (math.sqrt(0.5), math.sqrt(0.5), 0.0)),
        # Subnormal components: their own length rounds, so dividing by it
        # would leave the result off length 1.
        ((1e-320, 1e-320, 0), (math.sqrt(0.5), math.sqrt(0.5), 0.0)),
        ((5e-324, 5e-324, 0), (math.sqrt(0.5), math.sqrt(0.5), 0.0)),
        (
            (5e-324, -5e-324, 5e-324),
            (1 / math.sqrt(3), -1 / math.sqrt(3), 1 / math.sqrt(3)),
        ),
        ((1e-310, 0, -3e-310), (1 / math.sqrt(10), 0.0, -3 / math.sqrt(10))),
        ((5e-324, 0, 0), (1.0, 0.0, 0.0)),
    ],
)
def test_a_tiny_direction_is_normalised_without_underflow(vector, expected):
    unit = normalise(vector)
    assert unit == pytest.approx(expected, abs=1e-15)
    assert is_unit(unit)
    assert normalise(unit) == unit


@pytest.mark.parametrize(
    "vector", [(0.1, 0.1, 0.1), (0.3, -0.7, -0.2), (1, 1, 1), (-1, 0.25, 1)]
)
def test_normalising_twice_changes_nothing(vector):
    once = normalise(vector)
    assert bits(normalise(once)) == bits(once)
    assert abs(math.hypot(*once) - 1) <= UNIT_TOLERANCE
    assert is_unit(once)


@pytest.mark.parametrize(
    "vector", [(0, 0, 0), (0.0, -0.0, 0.0), (math.nan, 0, 1), (0, math.inf, 0)]
)
def test_a_direction_must_be_finite_and_not_all_0(vector):
    with pytest.raises(ValueError, match="direction"):
        normalise(vector)


def test_a_normalised_direction_is_within_the_tolerance():
    assert is_unit((0.0, 0.0, -1.0))
    assert is_unit((0.0, 0.6, 0.8 + 1e-13))
    assert not is_unit((0.0, 0.6, 0.8 + 1e-11))
    assert not is_unit((0.0, -1.5, 0.0))
    assert not is_unit((0.0, -1.0))


# Direction angles and labels


@pytest.mark.parametrize(
    ("view", "angles", "labels"),
    [
        (View(8, 0.0), EIGHT, EIGHT_LABELS),  # topdown
        (View(2, 90.0), [90.0, 270.0], ["east", "west"]),  # side
        (View(8, 0.0), EIGHT, EIGHT_LABELS),  # iso
        (View(8, 0.0), EIGHT, EIGHT_LABELS),  # iso-true
        (View(3, 10.0), [10.0, 130.0, 250.0], [None, None, None]),
        (
            View(4, -90.0),
            [270.0, 0.0, 90.0, 180.0],
            ["west", "south", "east", "north"],
        ),
        (View(2, -22.5), [337.5, 157.5], [None, None]),
        (View(1, 405.0), [45.0], ["south-east"]),
        (
            View(16, 0.0),
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
    (direction,) = directions(View(1, start))
    assert direction.angle == 0.0
    assert direction.label == "south"


@pytest.mark.parametrize("count", [0, -1, 2.0, True])
def test_direction_count_must_be_a_positive_integer(count):
    with pytest.raises(ValueError, match="direction count"):
        directions(View(count, 0.0))


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
    result = directions(View(4, 0.0, model_yaw=90.0))
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
    view = View(7, -13.25, model_yaw=12.5)
    assert directions(view) == directions(view)


# Large finite angles. The expected reductions use exact integer arithmetic:
# 1e20 is exactly the integer 10**20, which is 280 mod 360, and -10**20 is 80.


def test_large_start_angles_keep_their_offsets():
    result = directions(View(8, 1e20))
    assert [d.angle for d in result] == [280, 325, 10, 55, 100, 145, 190, 235]
    assert [d.angle for d in directions(View(4, -1e20))] == [80, 170, 260, 350]


def test_large_model_yaws_keep_their_offsets():
    result = directions(View(4, 0.0, model_yaw=1e20))
    assert [d.rotation for d in result] == [280, 10, 100, 190]


@pytest.mark.parametrize("large", [1e20, -1e20, 1e300, -123456789.0])
def test_rotation_is_periodic_for_large_angles(large):
    small = int(large) % 360
    assert facing(large) == pytest.approx(facing(small), abs=1e-15)
    for row, small_row in zip(
        rotation_matrix(large), rotation_matrix(small), strict=True
    ):
        assert row == pytest.approx(small_row, abs=1e-15)
