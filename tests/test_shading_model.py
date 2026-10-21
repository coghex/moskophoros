"""The shading leaves, their checks and the response models, without a file
or the command (shading design contracts 1 and 2; D-25, D-26, D-29, D-32)."""

import itertools
import math
from dataclasses import fields
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from moskophoros import settings, views
from moskophoros import shading as model

EXPECTED_DIRECTION = (-0.5183210553488161, 0.604707897906952, 0.604707897906952)


def refusal(check, value):
    with pytest.raises(model.Bad) as raised:
        check(value)
    return raised.value


def test_the_leaves_are_in_the_settings_tables_order():
    assert [leaf.path for leaf in model.LEAVES] == [
        "mode",
        "ambient_form",
        "key.direction",
        "key.strength",
        "sky.strength",
        "ground.strength",
        "sky_ground_frame",
        "brightness.floor",
        "brightness.ceiling",
        "snap",
        "dither.pattern",
        "dither.strength",
    ]
    assert model.SUBGROUPS == ("key", "sky", "ground", "brightness", "dither")


def test_only_the_response_leaves_may_be_overridden():
    # Direction, the sky and ground frame and the snap target are global only.
    assert {leaf.path for leaf in model.LEAVES if not leaf.response} == {
        "key.direction",
        "sky_ground_frame",
        "snap",
    }
    assert list(model.FIELDS) == [leaf.path for leaf in model.LEAVES if leaf.response]
    assert list(model.FIELDS.values()) == [
        field.name for field in fields(model.Response)
    ]


def test_every_default_is_the_contracts():
    assert dict(model.DEFAULTS) == {
        "mode": "ramp",
        "ambient_form": True,
        "key.direction": EXPECTED_DIRECTION,
        "key.strength": 0.0,
        "sky.strength": 0.0,
        "ground.strength": 0.0,
        "sky_ground_frame": "camera",
        "brightness.floor": 0.3,
        "brightness.ceiling": 1.0,
        "snap": "off",
        "dither.pattern": "off",
        "dither.strength": 1.0,
    }
    # Every default is already a checked value: checking it changes nothing.
    for leaf in model.LEAVES:
        assert leaf.check(model.DEFAULTS[leaf.path]) == model.DEFAULTS[leaf.path]


def test_settings_of_nothing_is_the_defaults():
    given = model.settings_of({})
    assert given == model.Settings(
        model.Response("ramp", True, 0.0, 0.0, 0.0, 0.3, 1.0, "off", 1.0),
        EXPECTED_DIRECTION,
        "camera",
        "off",
    )
    assert model.settings_of({"shade.mode": "both", "shade.snap": "ramp"}) == (
        model.Settings(
            model.Response("both", True, 0.0, 0.0, 0.0, 0.3, 1.0, "off", 1.0),
            EXPECTED_DIRECTION,
            "camera",
            "ramp",
        )
    )


def test_the_shading_settings_are_in_the_public_schema_after_the_range():
    names = list(settings.SCHEMA)
    start = names.index("shade.range") + 1
    assert names[start : start + len(model.DEFAULTS)] == [
        f"shade.{path}" for path in model.DEFAULTS
    ]
    assert {
        f"shade.{path}": settings.DEFAULTS[f"shade.{path}"] for path in model.DEFAULTS
    } == {f"shade.{path}": value for path, value in model.DEFAULTS.items()}


# The key direction (contract 1)


def test_the_default_direction_is_normalised_once_by_views():
    assert model.check_direction(model.KEY_DIRECTION) == EXPECTED_DIRECTION
    assert views.normalise(model.KEY_DIRECTION) == EXPECTED_DIRECTION
    assert math.isclose(math.hypot(*EXPECTED_DIRECTION), 1.0, rel_tol=0, abs_tol=1e-15)


@pytest.mark.parametrize(
    "vector", [(1, 0, 0), [0, -1, 0], (0, 0, 1), (-1, -1, -1), (1e-300, 0, 0)]
)
def test_direction_endpoints_are_accepted_and_normalised(vector):
    direction = model.check_direction(vector)
    assert direction == views.normalise(vector)
    assert math.isclose(math.hypot(*direction), 1.0, abs_tol=1e-15)


def test_a_direction_already_of_unit_length_is_kept_exactly():
    assert model.check_direction(EXPECTED_DIRECTION) == EXPECTED_DIRECTION
    assert model.check_direction(list(EXPECTED_DIRECTION)) == EXPECTED_DIRECTION


@pytest.mark.parametrize(
    "value",
    [
        None,
        "x",
        [],
        [0, 1],
        [0, 1, 0, 0],
        [1.5, 0, 0],
        [0, -1.0000001, 0],
        [math.nan, 0, 0],
        [math.inf, 0, 0],
        [True, 0, 0],
        ["1", 0, 0],
        [None, 0, 0],
        [1e999, 0, 0],
    ],
)
def test_a_bad_direction_is_refused(value):
    assert refusal(model.check_direction, value).wanted.startswith("expected [x, y, z]")


def test_a_zero_direction_points_nowhere():
    error = refusal(model.check_direction, [0, 0, 0])
    assert error.problem(repr) == "expected a direction, but [0, 0, 0] points nowhere"


def test_a_recorded_unit_direction_is_kept_exactly_and_never_renormalised():
    # Off by less than the tolerance: kept as recorded, not corrected.
    almost = (EXPECTED_DIRECTION[0] + 5e-13, *EXPECTED_DIRECTION[1:])
    assert model.check_recorded_direction(almost) == almost
    assert (
        model.check_recorded_direction(list(EXPECTED_DIRECTION)) == EXPECTED_DIRECTION
    )
    assert model.check_recorded_direction((0, 0, 1)) == (0.0, 0.0, 1.0)


@pytest.mark.parametrize(
    "value",
    [
        model.KEY_DIRECTION,
        (0.5, 0.5, 0.5),
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (EXPECTED_DIRECTION[0] + 2e-12, *EXPECTED_DIRECTION[1:]),
        None,
        [True, 0, 0],
    ],
)
def test_a_recorded_direction_that_is_not_unit_is_invalid(value):
    refusal(model.check_recorded_direction, value)


# The numeric, enumerated and boolean leaves


@pytest.mark.parametrize(
    "path",
    [
        "key.strength",
        "sky.strength",
        "ground.strength",
        "brightness.floor",
        "brightness.ceiling",
        "dither.strength",
    ],
)
def test_a_unit_leaf_takes_zero_to_one_and_only_a_finite_number(path):
    check = model.BY_PATH[path].check
    assert check(0) == 0.0 and isinstance(check(0), float)
    assert check(1) == 1.0 and isinstance(check(1), float)
    assert check(0.25) == 0.25
    for value in (
        -0.0000001,
        1.0000001,
        2,
        True,
        False,
        "0.5",
        None,
        [0.5],
        math.nan,
        math.inf,
        -math.inf,
        10**400,
    ):
        assert refusal(check, value).wanted == "expected a finite number from 0 to 1"


@pytest.mark.parametrize(
    ("path", "choices"),
    [
        ("mode", model.MODES),
        ("sky_ground_frame", model.FRAMES),
        ("snap", model.SNAPS),
        ("dither.pattern", model.PATTERNS),
    ],
)
def test_an_enumerated_leaf_takes_exactly_its_names(path, choices):
    check = model.BY_PATH[path].check
    for choice in choices:
        assert check(choice) == choice
    for value in ("", "Ramp", " ramp", "ordered3", None, True, 1, ["ramp"]):
        assert refusal(check, value).wanted.startswith("expected ")


def test_the_enumerations_are_the_contracts():
    assert model.MODES == ("ramp", "brightness", "both", "neither")
    assert model.FRAMES == ("camera", "world")
    assert model.SNAPS == ("off", "ramp", "palette")
    assert model.PATTERNS == (
        "off",
        "ordered2",
        "ordered4",
        "ordered8",
        "clustered4",
        "diagonal4",
        "shuffled8",
    )


def test_ambient_form_is_a_boolean_and_nothing_else():
    check = model.BY_PATH["ambient_form"].check
    assert check(True) is True and check(False) is False
    for value in (0, 1, "true", "false", None, [], 0.0):
        assert refusal(check, value).wanted == "expected true or false"


def test_a_refusal_words_the_value_the_readers_way():
    error = refusal(model.BY_PATH["mode"].check, "Ramp")
    assert (
        error.problem(repr) == "expected ramp, brightness, both or neither, got 'Ramp'"
    )
    assert error.problem(model.quote) == (
        'expected ramp, brightness, both or neither, got "Ramp"'
    )


# The unit budget and the brightness order (D-25, D-26)


def sourced(value, origin="o"):
    return model.Sourced(value, origin)


@pytest.mark.parametrize("order", list(itertools.permutations((0.1, 0.2, 0.7))))
def test_strengths_adding_to_exactly_one_pass_in_any_order(order):
    assert model.strength_total(*order) == 1
    assert model.budget_problem(*map(sourced, order)) is None


def test_strengths_are_added_as_decimals_not_as_floats():
    # An exact comparison of the stored floats would refuse these, whose
    # decimal values add to exactly 1.
    for exact in ((0.0, 0.1, 0.9), (0.0, 0.07, 0.93), (0.19, 0.0, 0.81)):
        assert sum(Fraction(strength) for strength in exact) > 1
        for order in itertools.permutations(exact):
            assert model.budget_problem(*map(sourced, order)) is None
    assert model.strength_total(0.1, 0.2, 0.7) == 1
    assert model.strength_total(0.3, 0.3, 0.4) == 1
    assert model.strength_total(0.3, 0.3, 0.4000001) > 1
    assert model.strength_total(0.5, 0.5, 0.0) == 1
    assert model.strength_total(1.0, 0.0, 0.0) == 1


@pytest.mark.parametrize(
    "strengths", [(1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.5, 0.25, 0.25), (0.0, 1.0, 0.0)]
)
def test_the_budget_holds_at_its_boundary(strengths):
    assert model.budget_problem(*map(sourced, strengths)) is None


def test_the_budget_refuses_an_excess_and_names_every_contribution():
    problem = model.budget_problem(
        model.Sourced(0.8, "--bake-key-strength"),
        model.Sourced(0.5, "library.yaml line 7, column 5"),
        model.Sourced(0.0, "shipped default"),
    )
    assert problem == (
        "shade.key.strength 0.8 (--bake-key-strength) + shade.sky.strength 0.5 "
        "(library.yaml line 7, column 5) + shade.ground.strength 0.0 "
        "(shipped default) = 1.3, exceeds 1"
    )
    assert (
        model.budget_problem(*map(sourced, (0.2, 0.4, 0.4000000000000001))) is not None
    )


def test_brightness_may_be_flat_and_may_not_be_inverted():
    assert model.brightness_problem(sourced(0.5), sourced(0.5)) is None
    assert model.brightness_problem(sourced(0.0), sourced(1.0)) is None
    assert model.brightness_problem(
        model.Sourced(0.8, "config.yaml line 12"),
        model.Sourced(0.5, "--brightness-ceiling"),
    ) == (
        "shade.brightness.floor 0.8 (config.yaml line 12) exceeds "
        "shade.brightness.ceiling 0.5 (--brightness-ceiling)"
    )


def test_the_shading_error_keeps_its_problems_in_order():
    error = model.ShadingError(["first", "second"])
    assert error.problems == ("first", "second")
    assert str(error) == "first\nsecond"


@pytest.mark.parametrize("order", list(itertools.permutations((1.0, 3e-28, 3e-28))))
def test_the_sum_is_exact_whatever_the_magnitudes_and_the_order(order):
    # A default 28-digit context rounds 1 + 3e-28 + 3e-28 by the order added.
    assert model.strength_total(*order) == Decimal("1.0000000000000000000000000006")
    assert model.budget_problem(*map(sourced, order)) is not None


def test_the_sum_does_not_depend_on_the_ambient_decimal_context():
    with localcontext() as context:
        context.prec = 5
        assert model.strength_total(1.0, 3e-28, 3e-28) > 1
        assert model.strength_total(0.1, 0.2, 0.7) == 1
    assert model.strength_total(5e-324, 1.0, 0.0) > 1
