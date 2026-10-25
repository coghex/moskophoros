"""The shading settings in `settings.read_bytes`: the two-level reader, nested
leaf merging and where each value came from (shading design contract 1, D-32,
D-39), and their place in the public schema and the shipped defaults."""

import math
from pathlib import Path

import pytest

from moskophoros import settings
from moskophoros import shading as model
from moskophoros.settings import SettingsError, merge, read_bytes

ROOT = Path(__file__).resolve().parents[1]


def read(text, source="s.yaml"):
    return read_bytes(text.encode(), source=source, directory="/settings")


def public(text):
    return read_bytes(text.encode(), source="s.yaml", directory="/settings")


def refused(text, reader=read):
    with pytest.raises(SettingsError) as raised:
        reader(text)
    assert raised.value.source == "s.yaml"
    return raised.value.problem


# Reading leaves


def test_every_shading_leaf_reads_from_its_nested_place():
    layer = read(
        """\
shade:
  mode: both
  ambient_form: false
  key: {direction: [1, 0, 0], strength: 0.25}
  sky: {strength: 0.5}
  ground: {strength: 0.125}
  sky_ground_frame: world
  brightness: {floor: 0.2, ceiling: 0.9}
  snap: palette
  dither: {pattern: ordered4, strength: 0.5}
"""
    )
    assert dict(layer) == {
        "shade.mode": "both",
        "shade.ambient_form": False,
        "shade.key.direction": (1.0, 0.0, 0.0),
        "shade.key.strength": 0.25,
        "shade.sky.strength": 0.5,
        "shade.ground.strength": 0.125,
        "shade.sky_ground_frame": "world",
        "shade.brightness.floor": 0.2,
        "shade.brightness.ceiling": 0.9,
        "shade.snap": "palette",
        "shade.dither.pattern": "ordered4",
        "shade.dither.strength": 0.5,
    }
    assert list(layer) == list(dict(layer))


def test_a_direction_is_normalised_once_and_a_unit_one_is_kept():
    assert read("shade: {key: {direction: [-0.6, 0.7, 0.7]}}")[
        "shade.key.direction"
    ] == (-0.5183210553488161, 0.604707897906952, 0.604707897906952)
    unit = read(
        "shade: {key: {direction: [-0.5183210553488161, 0.604707897906952, 0.604707897906952]}}"
    )
    assert unit["shade.key.direction"] == model.DEFAULTS["key.direction"]


def test_the_existing_shade_settings_read_beside_the_new_ones():
    layer = read("shade:\n  range: [10, 20]\n  mode: neither\n  ao_samples: 8\n")
    assert dict(layer) == {
        "shade.range": (10, 20),
        "shade.mode": "neither",
        "shade.ao_samples": 8,
    }


def test_leaves_merge_independently_across_layers():
    first = read("shade: {brightness: {ceiling: 0.7}, key: {strength: 0.5}}")
    second = read("shade: {brightness: {floor: 0.1}, sky: {strength: 0.25}}")
    merged = merge(first, second)
    # Setting a floor does not erase the ceiling an earlier layer set.
    assert dict(merged) == {
        "shade.brightness.ceiling": 0.7,
        "shade.key.strength": 0.5,
        "shade.brightness.floor": 0.1,
        "shade.sky.strength": 0.25,
    }
    third = read("shade: {brightness: {ceiling: 0.6}}")
    assert merge(first, second, third)["shade.brightness.ceiling"] == 0.6
    assert merge(first, second, third)["shade.brightness.floor"] == 0.1


def test_omitted_leaves_and_empty_groups_supply_nothing():
    assert dict(read("shade: {}")) == {}
    assert (
        dict(read("shade: {key: {}, sky: {}, ground: {}, brightness: {}, dither: {}}"))
        == {}
    )
    assert dict(read("shade:\n  key: {}\n  mode: both\n")) == {"shade.mode": "both"}


def test_each_leaf_keeps_its_line_and_column():
    layer = read(
        """\
shade:
  mode: both
  brightness:
    floor: 0.2
  dither: {pattern: ordered2, strength: 1}
"""
    )
    assert layer.where == {
        "shade.mode": (2, 3),
        "shade.brightness.floor": (4, 5),
        "shade.dither.pattern": (5, 12),
        "shade.dither.strength": (5, 31),
    }


def test_origins_name_the_layer_line_and_column_of_each_setting():
    first = read("shade:\n  brightness: {ceiling: 0.7}\n")
    second = read("shade:\n  brightness:\n    floor: 0.1\n  ao_samples: 4\n")
    assert settings.origins([("config.yaml", first), ("--project 'look'", second)]) == {
        "shade.brightness.ceiling": "config.yaml line 2, column 16",
        "shade.brightness.floor": "--project 'look' line 3, column 5",
        "shade.ao_samples": "--project 'look' line 4, column 3",
    }
    plain = settings.Layer({"shade.mode": "both"})
    assert settings.origins([("the command line", plain)]) == {
        "shade.mode": "the command line"
    }


# Refusals, at the full dotted path with the key's position


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (
            "shade:\n  key: null\n",
            "shade.key: expected a mapping of settings, got null at line 2, column 3",
        ),
        (
            "shade:\n  mode: ramp\n  dither: 0.5\n",
            "shade.dither: expected a mapping of settings, got 0.5 at line 3, column 3",
        ),
        (
            "shade: {brightness: [0.3, 1]}",
            "shade.brightness: expected a mapping of settings, got a list at line 1, column 9",
        ),
        (
            "shade:\n  sky: ''\n",
            "shade.sky: expected a mapping of settings, got '' at line 2, column 3",
        ),
        (
            "shade:\n  ground: true\n",
            "shade.ground: expected a mapping of settings, got true at line 2, column 3",
        ),
        (
            "shade:\n  key: {colour: red}\n",
            "shade.key.colour: unknown key at line 2, column 9",
        ),
        (
            "shade:\n  key: {strengths: 1}\n",
            "shade.key.strengths: unknown key at line 2, column 9",
        ),
        (
            "shade:\n  sky: {direction: [1, 0, 0]}\n",
            "shade.sky.direction: unknown key at line 2, column 9",
        ),
        ("shade:\n  glow: 1\n", "shade.glow: unknown key at line 2, column 3"),
        (
            "shade:\n  mode: {x: 1}\n",
            "shade.mode: expected ramp, brightness, both or neither, got a mapping at line 2, column 3",
        ),
        (
            "shade:\n  key:\n    1: 2\n",
            "shade.key: the key 1 is not a setting name at line 3, column 5",
        ),
        (
            "shade:\n  true: {}\n",
            "shade: the key true is not a setting name at line 2, column 3",
        ),
    ],
)
def test_a_bad_group_or_key_is_refused_at_its_full_path(text, problem):
    assert refused(text) == problem


@pytest.mark.parametrize(
    "line",
    [
        "mode: null",
        "ambient_form: null",
        "key: {direction: null}",
        "key: {strength: null}",
        "sky: {strength: null}",
        "ground: {strength: null}",
        "sky_ground_frame: null",
        "brightness: {floor: null}",
        "brightness: {ceiling: null}",
        "snap: null",
        "dither: {pattern: null}",
        "dither: {strength: null}",
    ],
)
def test_no_new_leaf_takes_null(line):
    assert " got null at line 2, column " in refused(f"shade:\n  {line}\n")


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        (
            "key: {strength: true}",
            "shade.key.strength: expected a number from 0 to 1, got true",
        ),
        (
            "sky: {strength: false}",
            "shade.sky.strength: expected a number from 0 to 1, got false",
        ),
        (
            "brightness: {floor: '0.5'}",
            "shade.brightness.floor: expected a number from 0 to 1, got '0.5'",
        ),
        (
            "brightness: {ceiling: 1.5}",
            "shade.brightness.ceiling: expected a finite number from 0 to 1, got 1.5",
        ),
        (
            "ground: {strength: -0.1}",
            "shade.ground.strength: expected a finite number from 0 to 1, got -0.1",
        ),
        (
            "dither: {strength: 1e999}",
            "shade.dither.strength: expected a finite number from 0 to 1, got inf",
        ),
        (
            "dither: {strength: 2}",
            "shade.dither.strength: expected a finite number from 0 to 1, got 2",
        ),
        (
            "dither: {pattern: ordered3}",
            "shade.dither.pattern: expected off, ordered2, ordered4, ordered8, clustered4, diagonal4 or shuffled8, got 'ordered3'",
        ),
        ("snap: yes", "shade.snap: expected off, ramp or palette, got 'yes'"),
        (
            "sky_ground_frame: Camera",
            "shade.sky_ground_frame: expected camera or world, got 'Camera'",
        ),
        ("ambient_form: 1", "shade.ambient_form: expected true or false, got 1"),
        (
            "ambient_form: 'true'",
            "shade.ambient_form: expected true or false, got 'true'",
        ),
        (
            "key: {direction: [0, 0, 0]}",
            "shade.key.direction: expected a direction, but [0, 0, 0] points nowhere",
        ),
        (
            "key: {direction: [2, 0, 0]}",
            "shade.key.direction: expected [x, y, z], three finite numbers each from -1 to 1, not all 0, got [2, 0, 0]",
        ),
        (
            "key: {direction: [true, 0, 0]}",
            "shade.key.direction: expected [x, y, z], three finite numbers each from -1 to 1, not all 0, got [true, 0, 0]",
        ),
        (
            "key: {direction: [1, 0]}",
            "shade.key.direction: expected [x, y, z], three finite numbers each from -1 to 1, not all 0, got [1, 0]",
        ),
    ],
)
def test_a_bad_value_is_refused_with_its_key_path_and_position(line, problem):
    text = f"shade:\n  {line}\n"
    message = refused(text)
    assert message.startswith(
        problem.replace("expected a number", "expected a finite number")
    )
    assert message.endswith(" at line 2, column " + message.rsplit("column ", 1)[1])


def test_a_leaf_is_checked_even_when_it_is_inactive_or_overridden():
    # Nothing here has an effect: the mode is neither and no term is on.
    text = "shade:\n  mode: neither\n  dither: {strength: 3}\n"
    assert refused(text).startswith("shade.dither.strength: ")
    text = "shade:\n  snap: palette\n  brightness: {floor: -1}\n"
    assert refused(text).startswith("shade.brightness.floor: ")


def test_a_group_that_is_not_a_mapping_is_reported_before_a_bad_value():
    text = "shade:\n  brightness: {floor: 9}\n  key: null\n"
    assert refused(text) == (
        "shade.key: expected a mapping of settings, got null at line 3, column 3"
    )


def test_a_cross_field_relation_is_not_a_reader_error():
    # The sum and the order are checked on resolved values, never on a layer
    # that a later layer may correct.
    layer = read(
        "shade:\n  key: {strength: 0.9}\n  sky: {strength: 0.9}\n"
        "  brightness: {floor: 0.9, ceiling: 0.1}\n"
    )
    assert layer["shade.key.strength"] == 0.9
    assert layer["shade.brightness.ceiling"] == 0.1


def test_the_duplicate_camera_direction_rule_is_unchanged():
    problem = refused(
        "pitch: 30\ncamera: {direction: [0, -1, -1]}\nshade: {mode: both}\n"
    )
    assert problem.startswith("camera.direction: pitch and camera.direction both set")


def test_an_infinite_or_nan_number_is_never_a_leaf():
    for value in ("1e999", "-1e999", ".nan", ".inf"):
        assert refused(f"shade:\n  sky: {{strength: {value}}}\n").startswith(
            "shade.sky.strength: expected "
        )
    assert not math.isfinite(float("1e999"))


# The public settings carry them

# Every shading leaf is a public setting, in the settings table's order after
# the range, with its shipped default (contract 1).
NEW_SETTINGS = [f"shade.{path}" for path in model.DEFAULTS]


def test_the_public_schema_holds_every_shading_leaf_after_the_range():
    assert settings.GROUPS == {"camera", "shade", "light", "ramp", "export"}
    shade = [name for name in settings.SCHEMA if name.startswith("shade.")]
    assert shade == [
        "shade.ao_distance_m",
        "shade.ao_samples",
        "shade.occlusion_weight",
        "shade.convexity_weight",
        "shade.range",
        *NEW_SETTINGS,
    ]
    # The new sub-groups are no top-level groups.
    assert not {"key", "sky", "ground", "brightness", "dither"} & settings.GROUPS
    shipped = settings.read_defaults()
    assert list(shipped) == list(settings.SCHEMA)
    for name in NEW_SETTINGS:
        assert shipped[name] == settings.DEFAULTS[name]
        assert shipped.where[name][0] > 0


def test_the_shipped_defaults_leave_the_default_look_alone():
    defaults = settings.DEFAULTS
    assert defaults["shade.mode"] == "ramp"
    assert defaults["shade.ambient_form"] is True
    assert defaults["shade.snap"] == "off"
    assert defaults["shade.dither.pattern"] == "off"
    for name in ("key", "sky", "ground"):
        assert defaults[f"shade.{name}.strength"] == 0.0


def test_public_settings_files_read_the_nested_keys():
    layer = public("shade:\n  key:\n    strength: 0.5\n")
    assert dict(layer) == {"shade.key.strength": 0.5}
    assert dict(public("shade: {sky: {strength: 0}}")) == {"shade.sky.strength": 0.0}
    assert refused("shade:\n  brightness: null\n", public) == (
        "shade.brightness: expected a mapping of settings, got null at line 2, column 3"
    )


def test_public_settings_files_read_the_flat_new_keys():
    layer = public("shade:\n  mode: both\n  sky_ground_frame: world\n  snap: ramp\n")
    assert dict(layer) == {
        "shade.mode": "both",
        "shade.sky_ground_frame": "world",
        "shade.snap": "ramp",
    }
    for key in ("mode", "ambient_form", "snap", "sky_ground_frame"):
        assert refused(f"shade:\n  {key}: wrong\n", public).startswith(f"shade.{key}: ")
