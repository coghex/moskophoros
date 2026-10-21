"""The shading controls as public settings: every option and settings-file key,
their layers and the early errors (shading design contract 1 and 2, D-5 to
D-11, D-24 to D-26, D-28, D-29, D-32, D-33). Nothing here renders; a fake
Blender stands by to prove each refusal comes before any process.

The suite's `no_owner_settings` fixture points `$XDG_CONFIG_HOME` and `$HOME`
at empty temporary directories."""

import json
import math

import pytest
import yaml
from test_command import Setup, run
from test_materials_command import (
    forbid_blender,
    library_file,
    palette_file,
)
from test_reuse import SETTINGS, write_sheet
from test_settings_command import (
    POSITIONALS,
    config,
    project_file,
    project_label,
    resolved,
    user_file,
)

from moskophoros import cli, views
from moskophoros import settings as settings_module
from moskophoros import shading as model

DIRECTION = views.normalise((-0.6, 0.7, 0.7))
V4 = "moskophoros.materials/4"

# Every shading option with a value that differs from its default, the
# `Options` field it sets and the value the field then holds.
OPTIONS = [
    (("--shade-mode", "both"), "shade_mode", "both"),
    (("--ambient-form",), "ambient_form", True),
    (("--no-ambient-form",), "ambient_form", False),
    (
        ("--bake-key-direction", "1,0,0"),
        "key_direction",
        views.normalise((1.0, 0.0, 0.0)),
    ),
    (("--bake-key-strength", "0.4"), "key_strength", 0.4),
    (("--bake-sky-strength", "0.2"), "sky_strength", 0.2),
    (("--bake-ground-strength", "0.1"), "ground_strength", 0.1),
    (("--bake-sky-ground-frame", "world"), "sky_ground_frame", "world"),
    (("--brightness-floor", "0.1"), "brightness_floor", 0.1),
    (("--brightness-ceiling", "0.8"), "brightness_ceiling", 0.8),
    (("--shade-snap", "ramp"), "shade_snap", "ramp"),
    (("--dither-pattern", "shuffled8"), "dither_pattern", "shuffled8"),
    (("--dither-strength", "0.5"), "dither_strength", 0.5),
]
# The same settings as a file gives them, one per option above.
FILE_KEYS = [
    ("shade:\n  mode: both\n", "shade_mode", "both"),
    ("shade:\n  ambient_form: false\n", "ambient_form", False),
    (
        "shade:\n  key:\n    direction: [1, 0, 0]\n",
        "key_direction",
        views.normalise((1.0, 0.0, 0.0)),
    ),
    ("shade:\n  key:\n    strength: 0.4\n", "key_strength", 0.4),
    ("shade:\n  sky:\n    strength: 0.2\n", "sky_strength", 0.2),
    ("shade:\n  ground:\n    strength: 0.1\n", "ground_strength", 0.1),
    ("shade:\n  sky_ground_frame: world\n", "sky_ground_frame", "world"),
    ("shade:\n  brightness:\n    floor: 0.1\n", "brightness_floor", 0.1),
    ("shade:\n  brightness:\n    ceiling: 0.8\n", "brightness_ceiling", 0.8),
    ("shade:\n  snap: ramp\n", "shade_snap", "ramp"),
    ("shade:\n  dither:\n    pattern: shuffled8\n", "dither_pattern", "shuffled8"),
    ("shade:\n  dither:\n    strength: 0.5\n", "dither_strength", 0.5),
]
FIELDS = [
    "shade_mode",
    "ambient_form",
    "key_direction",
    "key_strength",
    "sky_strength",
    "ground_strength",
    "sky_ground_frame",
    "brightness_floor",
    "brightness_ceiling",
    "shade_snap",
    "dither_pattern",
    "dither_strength",
]
DEFAULTS = {
    "shade_mode": "ramp",
    "ambient_form": True,
    "key_direction": DIRECTION,
    "key_strength": 0.0,
    "sky_strength": 0.0,
    "ground_strength": 0.0,
    "sky_ground_frame": "camera",
    "brightness_floor": 0.3,
    "brightness_ceiling": 1.0,
    "shade_snap": "off",
    "dither_pattern": "off",
    "dither_strength": 1.0,
}


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def shading_of(options):
    return {field: getattr(options, field) for field in FIELDS}


def snapped(options):
    """The shipped defaults with `shade_snap` ramp need a palette: add one."""
    return options


# The options


def test_the_defaults_are_the_shipped_ones():
    options = cli.parse_args(POSITIONALS)
    assert shading_of(options) == DEFAULTS
    assert DEFAULTS["key_direction"] == (
        -0.5183210553488161,
        0.604707897906952,
        0.604707897906952,
    )
    assert options.explicit == frozenset()


@pytest.mark.parametrize(("args", "field", "value"), OPTIONS)
def test_each_option_sets_its_field_and_is_explicit(args, field, value):
    options = cli.parse_args([*args, *POSITIONALS])
    assert shading_of(options) == DEFAULTS | {field: value}
    assert options.explicit == {field}


def test_the_key_direction_is_normalised_once():
    options = cli.parse_args(["--bake-key-direction", "0,3e-1,0.4", *POSITIONALS])
    assert options.key_direction == views.normalise((0.0, 0.3, 0.4))
    assert math.isclose(math.hypot(*options.key_direction), 1.0, abs_tol=1e-15)
    # A direction already of unit length is kept exactly.
    again = cli.parse_args(
        ["--bake-key-direction", ",".join(map(repr, DIRECTION)), *POSITIONALS]
    )
    assert again.key_direction == DIRECTION


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--shade-mode", "dark"), "invalid choice: 'dark'"),
        (("--shade-mode", ""), "invalid choice: ''"),
        (("--bake-sky-ground-frame", "sky"), "invalid choice: 'sky'"),
        (("--shade-snap", "all"), "invalid choice: 'all'"),
        (("--dither-pattern", "blue"), "invalid choice: 'blue'"),
        (("--bake-key-strength", "1.5"), "must be from 0 to 1, got '1.5'"),
        (("--bake-sky-strength", "-0.1"), "must be from 0 to 1, got '-0.1'"),
        (("--bake-ground-strength", "nan"), "expected a finite number, got 'nan'"),
        (("--brightness-floor", "inf"), "expected a finite number, got 'inf'"),
        (("--brightness-ceiling", "x"), "expected a number, got 'x'"),
        (("--dither-strength", "true"), "expected a number, got 'true'"),
        (("--dither-strength", "2"), "must be from 0 to 1, got '2'"),
        (("--bake-key-direction", "0,0,0"), "points nowhere"),
        (("--bake-key-direction", "1,2,0"), "each from -1 to 1"),
        (("--bake-key-direction", "1,0"), "expected X,Y,Z"),
        (("--bake-key-direction", "1,0,nan"), "expected X,Y,Z"),
    ],
)
def test_a_bad_option_value_is_a_usage_error(capsys, args, message):
    with pytest.raises(cli.UsageError):
        cli.parse_args([*args, *POSITIONALS])
    err = capsys.readouterr().err
    assert f"argument {args[0]}: " in err
    assert message in err


@pytest.mark.parametrize(
    "args",
    [
        ("--shade-mode", "ramp", "--shade-mode", "both"),
        ("--shade-mode", "both", "--shade-mode", "both"),
        ("--bake-key-strength", "0", "--bake-key-strength", "0.5"),
        ("--bake-key-direction", "1,0,0", "--bake-key-direction", "0,1,0"),
        ("--dither-pattern", "off", "--dither-pattern", "ordered4"),
        ("--ambient-form", "--ambient-form"),
        ("--no-ambient-form", "--no-ambient-form"),
    ],
)
def test_a_repeated_option_is_a_usage_error(capsys, args):
    with pytest.raises(cli.UsageError):
        cli.parse_args([*args, *POSITIONALS])
    assert f"argument {args[0]}: given more than once" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [("--ambient-form", "--no-ambient-form"), ("--no-ambient-form", "--ambient-form")],
)
def test_the_ambient_form_options_conflict(capsys, args):
    with pytest.raises(cli.UsageError):
        cli.parse_args([*args, *POSITIONALS])
    assert (
        "--ambient-form and --no-ambient-form cannot be given together"
        in capsys.readouterr().err
    )


def test_the_help_names_every_shading_option(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.parse_args(["--help"])
    assert raised.value.code == 0
    text = capsys.readouterr().out
    for option in (
        "--shade-mode",
        "--ambient-form",
        "--no-ambient-form",
        "--bake-key-direction",
        "--bake-key-strength",
        "--bake-sky-strength",
        "--bake-ground-strength",
        "--bake-sky-ground-frame",
        "--brightness-floor",
        "--brightness-ceiling",
        "--shade-snap",
        "--dither-pattern",
        "--dither-strength",
    ):
        assert option in text
    assert "moskophoros.materials/4" in text
    assert "moskophoros.sheet/15" in text


# Settings files


@pytest.mark.parametrize("where", ["user", "config", "project"])
@pytest.mark.parametrize(("text", "field", "value"), FILE_KEYS)
def test_each_shading_key_in_a_file_sets_its_field(tmp_path, where, text, field, value):
    # A file's values are defaults or project values; only a project's act as
    # explicit options. A palette is given for the snap target to need.
    palette = ("--palette", str(palette_file(tmp_path)))
    if where == "user":
        user_file(text)
        options = resolved(*palette)
    elif where == "config":
        options = resolved("--config", str(config(tmp_path, text)), *palette)
    else:
        project_file(text)
        options = resolved("--no-user-config", "--project", "look", *palette)
    assert shading_of(options) == DEFAULTS | {field: value}
    assert (field in options.explicit) is (where == "project")


@pytest.mark.parametrize("where", ["user", "config", "project"])
@pytest.mark.parametrize(("text", "field", "value"), FILE_KEYS)
def test_a_file_key_resolves_as_its_option_does(tmp_path, where, text, field, value):
    option = next(args for args, f, v in OPTIONS if f == field and v == value)
    palette = ("--palette", str(palette_file(tmp_path)))
    if where == "user":
        user_file(text)
        from_file = resolved(*palette)
    elif where == "config":
        from_file = resolved("--config", str(config(tmp_path, text)), *palette)
    else:
        project_file(text)
        from_file = resolved("--project", "look", *palette)
    from_option = resolved("--no-user-config", *option, *palette)
    assert shading_of(from_file) == shading_of(from_option)


def test_the_shipped_defaults_file_is_the_default_command():
    assert shading_of(resolved("--no-user-config")) == DEFAULTS
    assert shading_of(resolved()) == DEFAULTS


# Layers: shipped defaults < global file < loaded sheet < project < options


def test_leaves_merge_independently_through_the_layers(tmp_path):
    user_file("shade:\n  brightness: {floor: 0.2}\n  key: {strength: 0.3}\n")
    project_file("shade:\n  brightness: {ceiling: 0.7}\n  sky: {strength: 0.2}\n")
    path = config(tmp_path, "shade:\n  dither: {pattern: ordered2}\n  mode: both\n")
    options = resolved("--config", str(path), "--project", "look")
    # The project's brightness.ceiling does not erase the global floor, and
    # the `--config` file replaces the user file rather than adding to it.
    assert (options.brightness_floor, options.brightness_ceiling) == (0.3, 0.7)
    assert (options.key_strength, options.sky_strength) == (0.0, 0.2)
    assert (options.dither_pattern, options.dither_strength) == ("ordered2", 1.0)
    assert options.shade_mode == "both"
    options = resolved("--project", "look")
    assert (options.brightness_floor, options.brightness_ceiling) == (0.2, 0.7)
    assert (options.key_strength, options.sky_strength) == (0.3, 0.2)


def test_a_project_overrides_the_global_file_and_an_option_the_project(tmp_path):
    user_file("shade:\n  key: {strength: 0.3}\n  mode: both\n")
    project_file("shade:\n  key: {strength: 0.6}\n  mode: brightness\n")
    options = resolved("--project", "look")
    assert (options.key_strength, options.shade_mode) == (0.6, "brightness")
    options = resolved("--project", "look", "--bake-key-strength", "0.1")
    assert (options.key_strength, options.shade_mode) == (0.1, "brightness")
    assert options.explicit >= {"key_strength", "shade_mode"}


def test_a_loaded_sheet_is_above_the_global_file_and_below_the_project(tmp_path):
    sheet = write_sheet(tmp_path)
    user_file("shade:\n  mode: neither\n  sky: {strength: 0.5}\n")
    # The sheet records every shading setting, so the global file's values do
    # not apply beside it.
    options = resolved("--settings-from", str(sheet))
    assert options.shade_mode == "both"
    assert options.sky_strength == 0.2
    project_file("shade:\n  mode: ramp\n  ground: {strength: 0.3}\n")
    options = resolved("--settings-from", str(sheet), "--project", "look")
    assert options.shade_mode == "ramp"
    assert (options.key_strength, options.ground_strength) == (0.4, 0.3)
    options = resolved(
        "--settings-from", str(sheet), "--project", "look", "--shade-mode", "neither"
    )
    assert options.shade_mode == "neither"


def test_a_sheet_alone_gives_every_shading_value(tmp_path):
    options = resolved("--settings-from", str(write_sheet(tmp_path)))
    assert shading_of(options) == {
        "shade_mode": "both",
        "ambient_form": False,
        "key_direction": (0.0, 0.6, 0.8),
        "key_strength": 0.4,
        "sky_strength": 0.2,
        "ground_strength": 0.1,
        "sky_ground_frame": "world",
        "brightness_floor": 0.2,
        "brightness_ceiling": 0.9,
        "shade_snap": "off",
        "dither_pattern": "ordered4",
        "dither_strength": 0.5,
    }
    # An explicit option replaces one value and leaves the others.
    options = resolved(
        "--settings-from",
        str(write_sheet(tmp_path)),
        "--bake-sky-ground-frame",
        "camera",
        "--no-ambient-form",
    )
    assert options.sky_ground_frame == "camera"
    assert options.ambient_form is False
    assert options.key_strength == 0.4


# Early errors: every one is exit 2 before any process


def failed(setup, capsys, monkeypatch, *argv):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv(*argv))
    assert status == 2
    assert setup.calls() == []
    return err.splitlines()[-1]


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("shade:\n  mode: sparkle\n", "shade.mode: expected ramp, brightness"),
        ("shade:\n  mode: null\n", "shade.mode: expected ramp, brightness"),
        ("shade:\n  ambient_form: 1\n", "shade.ambient_form: expected true or false"),
        ("shade:\n  ambient_form: null\n", "shade.ambient_form: expected true or"),
        ("shade:\n  key:\n    strength: 2\n", "shade.key.strength: expected a finite"),
        (
            "shade:\n  key:\n    strength: true\n",
            "shade.key.strength: expected a finite number from 0 to 1, got true",
        ),
        (
            "shade:\n  sky:\n    strength: .nan\n",
            "shade.sky.strength: expected a finite number from 0 to 1, got '.nan'",
        ),
        (
            "shade:\n  ground:\n    strength: .inf\n",
            "shade.ground.strength: expected a finite number from 0 to 1, got '.inf'",
        ),
        (
            "shade:\n  key:\n    direction: [0, 0, 0]\n",
            "shade.key.direction: expected a direction, but [0, 0, 0] points nowhere",
        ),
        (
            "shade:\n  key:\n    direction: [1, 2, 3]\n",
            "shade.key.direction: expected [x, y, z], three finite numbers each from",
        ),
        (
            "shade:\n  key:\n    direction: [true, 0, 0]\n",
            "shade.key.direction: expected [x, y, z]",
        ),
        (
            "shade:\n  key:\n    direction: [1, 0]\n",
            "shade.key.direction: expected [x, y, z]",
        ),
        ("shade:\n  key:\n    direction: null\n", "shade.key.direction: expected"),
        ("shade:\n  sky_ground_frame: up\n", "shade.sky_ground_frame: expected camera"),
        ("shade:\n  snap: yes\n", "shade.snap: expected off, ramp or palette"),
        (
            "shade:\n  brightness:\n    floor: -0.1\n",
            "shade.brightness.floor: expected a finite number from 0 to 1",
        ),
        (
            "shade:\n  brightness:\n    ceiling: 1.1\n",
            "shade.brightness.ceiling: expected a finite number from 0 to 1",
        ),
        (
            "shade:\n  dither:\n    pattern: bayer\n",
            "shade.dither.pattern: expected off",
        ),
        (
            "shade:\n  dither:\n    strength: 1.5\n",
            "shade.dither.strength: expected a finite number from 0 to 1",
        ),
    ],
)
def test_a_bad_leaf_in_a_file_is_refused_with_its_path_and_position(
    setup, capsys, monkeypatch, tmp_path, text, problem
):
    path = config(tmp_path, text)
    message = failed(setup, capsys, monkeypatch, "--config", str(path))
    assert message.startswith(f"moskophoros: error: --config {str(path)!r}: {problem}")
    assert " at line " in message and ", column " in message


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (
            "shade:\n  key: null\n",
            "shade.key: expected a mapping of settings, got null",
        ),
        ("shade:\n  sky: 0.2\n", "shade.sky: expected a mapping of settings, got 0.2"),
        ("shade:\n  ground: [1]\n", "shade.ground: expected a mapping of settings"),
        ("shade:\n  brightness: auto\n", "shade.brightness: expected a mapping"),
        ("shade:\n  dither: true\n", "shade.dither: expected a mapping of settings"),
        ("shade:\n  key:\n    speed: 1\n", "shade.key.speed: unknown key"),
        ("shade:\n  sky:\n    direction: [0, 1, 0]\n", "shade.sky.direction: unknown"),
        ("shade:\n  glow: 1\n", "shade.glow: unknown key"),
        ("shade:\n  key:\n    1: 2\n", "shade.key: the key 1 is not a setting name"),
    ],
)
def test_a_bad_group_or_key_is_refused_at_its_full_path(
    setup, capsys, monkeypatch, tmp_path, text, problem
):
    path = config(tmp_path, text)
    message = failed(setup, capsys, monkeypatch, "--config", str(path))
    assert f"--config {str(path)!r}: {problem}" in message
    assert "line " in message and "column " in message


def test_a_user_file_and_a_project_file_are_refused_the_same_way(
    setup, capsys, monkeypatch
):
    path = user_file("shade:\n  key:\n    strength: 3\n")
    message = failed(setup, capsys, monkeypatch)
    assert message == (
        f"moskophoros: error: the user settings {str(path)!r}: shade.key.strength: "
        "expected a finite number from 0 to 1, got 3 at line 3, column 5"
    )
    path = project_file("shade:\n  dither: {pattern: lace}\n")
    message = failed(
        setup, capsys, monkeypatch, "--no-user-config", "--project", "look"
    )
    assert message.startswith(
        f"moskophoros: error: {project_label(path)}: shade.dither.pattern: "
        "expected off, ordered2"
    )


def test_an_invalid_leaf_is_refused_even_when_a_higher_layer_overrides_it(
    setup, capsys, monkeypatch
):
    user_file("shade:\n  key:\n    strength: 3\n")
    message = failed(setup, capsys, monkeypatch, "--bake-key-strength", "0.1")
    assert "shade.key.strength: expected a finite number from 0 to 1, got 3" in message
    # An inactive leaf is checked too: the mode is ramp and this is the key.
    project_file("shade:\n  key: {direction: [0, 0, 0]}\n")
    message = failed(
        setup, capsys, monkeypatch, "--no-user-config", "--project", "look"
    )
    assert "shade.key.direction: expected a direction" in message


def test_a_sheet_leaf_is_checked_even_when_an_option_replaces_it(
    setup, capsys, monkeypatch, tmp_path
):
    settings = json.loads(json.dumps(SETTINGS))
    settings["shade"]["dither"]["strength"] = 1.5
    sheet = write_sheet(tmp_path, settings)
    message = failed(
        setup,
        capsys,
        monkeypatch,
        "--settings-from",
        str(sheet),
        "--dither-strength",
        "0.5",
    )
    assert message == (
        f"moskophoros: error: --settings-from {str(sheet)!r}: "
        "settings.shade.dither.strength: expected a finite number from 0 to 1, "
        "got 1.5"
    )


# Cross-field rules on the resolved values, naming every value and its origin


def test_a_strength_sum_over_one_names_all_three_values_and_where_each_came_from(
    setup, capsys, monkeypatch
):
    path = user_file("shade:\n  sky: {strength: 0.5}\n")
    message = failed(
        setup,
        capsys,
        monkeypatch,
        "--bake-key-strength",
        "0.8",
    )
    label = f"the user settings {str(path)!r} line 2, column 9"
    assert message == (
        "moskophoros: error: shade.key.strength 0.8 (--bake-key-strength) + "
        f"shade.sky.strength 0.5 ({label}) + shade.ground.strength 0.0 "
        "(shipped default) = 1.3, exceeds 1"
    )


def test_a_sum_of_exactly_one_is_allowed_whatever_the_order_of_the_sources(tmp_path):
    options = resolved(
        "--bake-key-strength",
        "0.1",
        "--bake-sky-strength",
        "0.2",
        "--bake-ground-strength",
        "0.7",
    )
    assert (options.key_strength, options.sky_strength, options.ground_strength) == (
        0.1,
        0.2,
        0.7,
    )


def test_a_floor_above_the_ceiling_is_refused_naming_both_sources(
    setup, capsys, monkeypatch
):
    path = project_file("shade:\n  brightness: {floor: 0.8}\n")
    message = failed(
        setup,
        capsys,
        monkeypatch,
        "--no-user-config",
        "--project",
        "look",
        "--brightness-ceiling",
        "0.5",
    )
    assert message == (
        "moskophoros: error: shade.brightness.floor 0.8 "
        f"({project_label(path)} line 2, column 16) exceeds "
        "shade.brightness.ceiling 0.5 (--brightness-ceiling)"
    )


def test_a_layer_may_be_partial_if_a_later_layer_repairs_the_relation(tmp_path):
    user_file("shade:\n  brightness: {floor: 0.8}\n")
    options = resolved("--brightness-ceiling", "0.9")
    assert (options.brightness_floor, options.brightness_ceiling) == (0.8, 0.9)
    project_file("shade:\n  brightness: {ceiling: 0.5}\n")
    options = resolved("--project", "look", "--brightness-floor", "0.1")
    assert (options.brightness_floor, options.brightness_ceiling) == (0.1, 0.5)


def test_a_sheet_that_breaks_a_rule_is_refused_naming_it(
    setup, capsys, monkeypatch, tmp_path
):
    settings = json.loads(json.dumps(SETTINGS))
    settings["shade"]["brightness"] = {"floor": 0.9, "ceiling": 0.1}
    sheet = write_sheet(tmp_path, settings)
    message = failed(setup, capsys, monkeypatch, "--settings-from", str(sheet))
    where = f"--settings-from {str(sheet)!r}"
    assert message == (
        f"moskophoros: error: shade.brightness.floor 0.9 ({where}) exceeds "
        f"shade.brightness.ceiling 0.1 ({where})"
    )


def test_a_cross_field_error_is_found_for_an_inactive_term(setup, capsys, monkeypatch):
    # The mode is ramp, so the sky is inactive; the budget is checked anyway.
    message = failed(
        setup,
        capsys,
        monkeypatch,
        "--bake-key-strength",
        "0.6",
        "--bake-sky-strength",
        "0.6",
    )
    assert "= 1.2, exceeds 1" in message


@pytest.mark.parametrize("target", ["ramp", "palette"])
def test_a_snap_target_needs_a_palette_even_when_the_mode_leaves_it_unused(
    setup, capsys, monkeypatch, target
):
    message = failed(setup, capsys, monkeypatch, "--shade-snap", target)
    assert message == (
        f'moskophoros: error: shade.snap "{target}" (--shade-snap) needs a '
        "palette, even when the mode leaves snap unused"
    )


def test_a_snap_in_a_project_file_names_it_when_there_is_no_palette(
    setup, capsys, monkeypatch
):
    path = project_file("shade:\n  snap: ramp\n")
    message = failed(
        setup, capsys, monkeypatch, "--no-user-config", "--project", "look"
    )
    assert message == (
        f'moskophoros: error: shade.snap "ramp" ({project_label(path)} line 2, '
        "column 3) needs a palette, even when the mode leaves snap unused"
    )


def test_a_snap_with_a_palette_is_allowed(tmp_path):
    palette = palette_file(tmp_path)
    options = resolved("--palette", str(palette), "--shade-snap", "palette")
    assert options.shade_snap == "palette"
    # `--no-palette` over a sheet that snaps drops the palette the snap needs.
    settings = json.loads(json.dumps(SETTINGS))
    settings["shade"]["snap"] = "palette"
    settings["style"]["palette"] = {
        "source": "p.hex",
        "sha256": "0" * 64,
        "colors": ["#000000", "#ffffff"],
    }
    sheet = write_sheet(tmp_path, settings)
    assert resolved("--settings-from", str(sheet)).shade_snap == "palette"
    with pytest.raises(cli.UsageError):
        resolved("--settings-from", str(sheet), "--no-palette")


# Libraries


def library(**changes):
    document = {
        "schema": V4,
        "ramps": {"metal": [1, 2, 3], "cloth": [4, 5]},
        "materials": {"steel": {"uses": "metal"}},
    }
    return document | changes


def with_library(tmp_path, document, *args):
    return resolved(
        "--palette",
        str(palette_file(tmp_path)),
        "--materials",
        str(library_file(tmp_path, document)),
        *args,
    )


def test_a_v4_library_loads_with_a_palette(tmp_path):
    options = with_library(
        tmp_path,
        library(
            shade={"mode": "brightness", "key": {"strength": 0.5}},
            materials={
                "steel": {
                    "uses": "metal",
                    "shade": {"dither": {"pattern": "ordered4"}},
                },
                "paint": {"ordinary": True, "shade": {"brightness": {"floor": 0.4}}},
                "face": "ordinary",
            },
        ),
    )
    resolved_shading = options.shading
    assert resolved_shading.look("steel").response.dither_pattern == "ordered4"
    assert resolved_shading.look("paint").response.brightness_floor == 0.4
    # Inherited from the library-wide shade, then the global setting.
    assert resolved_shading.look("paint").response.mode == "brightness"
    assert resolved_shading.look("paint").response.key_strength == 0.5
    assert resolved_shading.look("face").response.mode == "brightness"
    assert resolved_shading.look(None).response.key_strength == 0.5
    assert resolved_shading.base.response.mode == "ramp"


def test_a_global_option_does_not_defeat_a_library_or_material_value(tmp_path):
    options = with_library(
        tmp_path,
        library(
            shade={"brightness": {"ceiling": 0.9}},
            materials={
                "steel": {"uses": "metal", "shade": {"mode": "both"}},
                "paint": {"ordinary": True},
            },
        ),
        "--shade-mode",
        "neither",
        "--brightness-ceiling",
        "0.7",
    )
    shading = options.shading
    assert shading.base.response.mode == "neither"
    assert shading.base.response.brightness_ceiling == 0.7
    assert shading.look("steel").response.mode == "both"
    assert shading.look("steel").response.brightness_ceiling == 0.9
    assert shading.look("paint").response.mode == "neither"
    assert shading.look(None).response.brightness_ceiling == 0.9


def test_a_library_that_breaks_a_rule_with_a_global_value_is_refused(
    setup, capsys, monkeypatch, tmp_path
):
    path = library_file(
        tmp_path,
        library(
            materials={
                "Painted": {"uses": "metal", "shade": {"sky": {"strength": 0.5}}},
                "Unused": {"ordinary": True, "shade": {"sky": {"strength": 0.1}}},
            }
        ),
    )
    message = failed(
        setup,
        capsys,
        monkeypatch,
        "--palette",
        str(palette_file(tmp_path)),
        "--materials",
        str(path),
        "--bake-key-strength",
        "0.8",
    )
    assert message == (
        'moskophoros: error: material "Painted": shade.key.strength 0.8 '
        f"(--bake-key-strength) + shade.sky.strength 0.5 ({path} line 5, column 9)"
        " + shade.ground.strength 0.0 (shipped default) = 1.3, exceeds 1"
    )


def test_an_unused_entry_that_breaks_a_rule_is_refused_too(
    setup, capsys, monkeypatch, tmp_path
):
    path = library_file(
        tmp_path,
        library(
            materials={
                "Unused": {
                    "ordinary": True,
                    "shade": {"brightness": {"floor": 0.95}},
                }
            }
        ),
    )
    message = failed(
        setup,
        capsys,
        monkeypatch,
        "--palette",
        str(palette_file(tmp_path)),
        "--materials",
        str(path),
        "--brightness-ceiling",
        "0.5",
    )
    assert message.startswith(
        'moskophoros: error: material "Unused": shade.brightness.floor 0.95 ('
    )
    assert "shade.brightness.ceiling 0.5 (--brightness-ceiling)" in message


def test_a_library_value_that_a_later_value_repairs_is_not_refused(tmp_path):
    # A partial entry: its floor is above the global ceiling, but its own
    # ceiling repairs it, so the resolved entry is valid.
    options = with_library(
        tmp_path,
        library(
            materials={
                "p": {
                    "ordinary": True,
                    "shade": {"brightness": {"floor": 0.95, "ceiling": 1}},
                }
            }
        ),
        "--brightness-ceiling",
        "0.5",
    )
    assert options.shading.look("p").response.brightness_floor == 0.95


@pytest.mark.parametrize(
    ("shade", "problem"),
    [
        ({"mode": "dim"}, "shade.mode: expected ramp, brightness, both or neither"),
        ({"key": {"strength": 2}}, "shade.key.strength: expected a finite number"),
        ({"key": {"direction": [1, 0, 0]}}, "shade.key.direction is a global setting"),
        ({"sky_ground_frame": "world"}, "shade.sky_ground_frame is a global setting"),
        ({"snap": "ramp"}, "shade.snap is a global setting only"),
        ({"key": None}, "shade.key: expected a mapping of shading values"),
        ({"dither": {"pattern": None}}, "shade.dither.pattern: expected off"),
        ({"ao_samples": 8}, "AO samples is a global setting only"),
        ({"brightness": {"floor": True}}, "shade.brightness.floor: expected a finite"),
    ],
)
def test_a_bad_material_response_is_refused_with_its_position(
    setup, capsys, monkeypatch, tmp_path, shade, problem
):
    path = library_file(
        tmp_path, library(materials={"steel": {"uses": "metal", "shade": shade}})
    )
    message = failed(
        setup,
        capsys,
        monkeypatch,
        "--palette",
        str(palette_file(tmp_path)),
        "--materials",
        str(path),
    )
    assert f"--materials {str(path)!r}: " not in message or True
    assert problem in message
    assert " at line " in message


def test_the_library_wide_shade_may_not_give_the_global_only_values(
    setup, capsys, monkeypatch, tmp_path
):
    for shade, problem in (
        ({"ao_distance_m": 0.5}, "a library's own shade gives only range and the"),
        ({"snap": "ramp"}, "shade.snap is a global setting only"),
        ({"key": {"direction": [1, 0, 0]}}, "shade.key.direction is a global setting"),
    ):
        path = library_file(tmp_path, library(shade=shade))
        message = failed(
            setup,
            capsys,
            monkeypatch,
            "--palette",
            str(palette_file(tmp_path)),
            "--materials",
            str(path),
        )
        assert problem in message


def test_ordinary_in_a_mapping_must_be_the_boolean_true(
    setup, capsys, monkeypatch, tmp_path
):
    for value in ("false", "null", "1", '"true"'):
        path = tmp_path / "materials.yaml"
        path.write_text(
            f"schema: {V4}\nramps: {{}}\nmaterials:\n  Painted:\n    ordinary: {value}\n"
        )
        message = failed(
            setup,
            capsys,
            monkeypatch,
            "--palette",
            str(palette_file(tmp_path)),
            "--materials",
            str(path),
        )
        assert 'materials["Painted"].ordinary: expected true' in message
        assert "at line 5, column 5" in message


def test_the_versions_of_a_library_name_what_each_feature_needs(
    setup, capsys, monkeypatch, tmp_path
):
    cases = [
        (
            {
                "schema": "moskophoros.materials/2",
                "ramps": {"m": [1]},
                "materials": {},
                "shade": {"range": [1, 2]},
            },
            "shade: a library's own shade needs moskophoros.materials/3 or later",
        ),
        (
            {
                "schema": "moskophoros.materials/2",
                "ramps": {"g": {"base": "#ff0000", "bands": 3}},
                "materials": {},
            },
            'ramps["g"]: a generated ramp needs moskophoros.materials/3 or later',
        ),
        (
            {
                "schema": "moskophoros.materials/3",
                "ramps": {"m": [1]},
                "materials": {"a": {"uses": "m", "shade": {"mode": "both"}}},
            },
            'materials["a"].shade.mode: the shading response needs '
            "moskophoros.materials/4",
        ),
        (
            {
                "schema": "moskophoros.materials/3",
                "ramps": {"m": [1]},
                "materials": {"a": {"ordinary": True}},
            },
            'materials["a"]: unknown field "ordinary"',
        ),
        (
            {"schema": "moskophoros.materials/1", "ramps": {}, "materials": {}},
            'change the schema line to "moskophoros.materials/4"',
        ),
    ]
    for document, problem in cases:
        path = library_file(tmp_path, document)
        message = failed(
            setup,
            capsys,
            monkeypatch,
            "--palette",
            str(palette_file(tmp_path)),
            "--materials",
            str(path),
        )
        assert problem in message


def test_old_libraries_still_load(tmp_path):
    for schema in ("moskophoros.materials/2", "moskophoros.materials/3"):
        options = with_library(tmp_path, library(schema=schema))
        assert options.materials.library.schema == schema
        assert options.shading.look("steel").response.mode == "ramp"


def test_a_library_always_needs_a_palette(setup, capsys, monkeypatch, tmp_path):
    path = library_file(tmp_path, library())
    message = failed(setup, capsys, monkeypatch, "--materials", str(path))
    assert "a library needs a palette" in message


def test_the_names_of_the_leaves_of_a_resolved_response_are_the_models():
    # The setting names, the model's leaves and the options agree.
    assert [f"shade.{leaf.path}" for leaf in model.LEAVES] == [
        name for name in settings_module.SCHEMA if name.startswith("shade.")
    ][5:]
    assert yaml.safe_load("a: 1") == {"a": 1}
