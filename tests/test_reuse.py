"""`--settings-from`: reading an earlier sheet's settings and merging them
with explicit options (design §Scale and ground point, Reuse)."""

import copy
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest

from moskophoros import cli, export, fit, gltf, sampling, views
from moskophoros.capture.backend import Settings, Source

USAGE_LINE = "usage: moskophoros [options] <infile.glb> <outfile.png>"

# A hand-written sheet's settings, every value differing from its default.
SETTINGS = {
    "view": {
        "preset": "side",
        "projection": "orthographic",
        "pitch_deg": 0.0,
        "directions": 2,
        "start_angle_deg": 90.0,
    },
    "model_yaw_deg": -45.0,
    "fps": 24.0,
    "supersample": 4,
    "pixels_per_meter": 32.0,
    "cell": {"width": 48, "height": 40},
    "ground_m": {"x": 0.1, "y": -0.2, "z": 0.3},
    "ground_px": {"x": 24, "y": 37},
    "root_motion": "keep",
    "style": {
        "reduce": "plain",
        "palette": None,
        "materials": None,
        "shade_range": [84, 191],
    },
    "clips": [{"name": "walk", "loop": True}, {"name": "attack", "loop": False}],
}
# The same settings as an older `/2` sheet records them: a style without a
# material library or shade range.
PREVIOUS_SETTINGS = copy.deepcopy(SETTINGS)
PREVIOUS_SETTINGS["style"] = {"reduce": "plain", "palette": None}
# And as an older `/1` sheet records them: without a style.
LEGACY_SETTINGS = {name: SETTINGS[name] for name in SETTINGS if name != "style"}
REUSED = {
    "view": "side",
    "pitch": 0.0,
    "directions": 2,
    "start_angle": 90.0,
    "model_yaw": -45.0,
    "fps": 24.0,
    "supersample": 4,
    "ppm": 32.0,
    "cell": (48, 40),
    "ground": (0.1, -0.2, 0.3),
    "ground_px": (24, 37),
    "root_motion": "keep",
    "reduce": "plain",
}


def write_sheet(tmp_path, settings=None, name="old.json", **document):
    path = tmp_path / name
    contents = {"schema": "moskophoros.sheet/3"} | document
    contents["settings"] = copy.deepcopy(SETTINGS if settings is None else settings)
    path.write_text(json.dumps(contents, ensure_ascii=False), encoding="utf-8")
    return path


def parse(path, *options):
    return cli.parse_args(["--settings-from", str(path), *options, "in.glb", "out.png"])


def reuse(path, *options):
    return cli.resolve_settings(parse(path, *options))


def values(options, names=REUSED):
    return {name: getattr(options, name) for name in names}


def rejected(capsys, path, *options):
    """Reuse `path` expecting a usage error; return its problem."""
    with pytest.raises(cli.UsageError) as raised:
        reuse(path, *options)
    assert raised.value.code == 2
    out, err = capsys.readouterr()
    assert out == ""
    usage, error, *rest = err.splitlines()
    assert usage == USAGE_LINE
    assert rest == []
    assert error == f"moskophoros: error: {raised.value.message}"
    prefix = f"--settings-from {str(path)!r}: "
    assert raised.value.message.startswith(prefix)
    return raised.value.message.removeprefix(prefix)


def write_previous_sheet(tmp_path, settings=None, name="old.json"):
    """A `moskophoros.sheet/2` sheet, with `PREVIOUS_SETTINGS` by default."""
    settings = PREVIOUS_SETTINGS if settings is None else settings
    return write_sheet(tmp_path, settings, name, schema="moskophoros.sheet/2")


def write_legacy_sheet(tmp_path, settings=None, name="old.json"):
    """A `moskophoros.sheet/1` sheet, with `LEGACY_SETTINGS` by default."""
    settings = LEGACY_SETTINGS if settings is None else settings
    return write_sheet(tmp_path, settings, name, schema="moskophoros.sheet/1")


def edited(changes=(), removed=(), base=SETTINGS):
    """`base` with dotted paths set to values, or removed."""
    settings = copy.deepcopy(base)
    for dotted, value in dict(changes).items():
        *parents, last = dotted.split(".")
        target = settings
        for parent in parents:
            target = target[parent]
        target[last] = value
    for dotted in removed:
        *parents, last = dotted.split(".")
        target = settings
        for parent in parents:
            target = target[parent]
        del target[last]
    return settings


# Without reuse


def test_without_settings_from_the_parsed_options_are_kept():
    options = cli.parse_args(["--pitch", "45", "in.glb", "out.png"])
    assert cli.resolve_settings(options) is options


def test_parsing_still_reads_no_settings_file(tmp_path):
    options = parse(tmp_path / "missing.json")
    assert options.settings_from == tmp_path / "missing.json"
    assert options.ppm is None


# What is reused


def test_every_reused_value_is_carried_over(tmp_path):
    options = reuse(write_sheet(tmp_path))
    assert values(options) == REUSED
    assert options.explicit == {"settings_from"}
    assert (options.clip, options.once) == (None, ())


def test_read_settings_returns_the_reused_values(tmp_path):
    reused = cli.read_settings(write_sheet(tmp_path))
    assert reused == cli.ReusedSettings(**REUSED)


@pytest.mark.parametrize(
    ("option", "value", "changed"),
    [
        ("--model-yaw", "180", {"model_yaw": 180.0}),
        ("--fps", "6", {"fps": 6.0}),
        ("--supersample", "2", {"supersample": 2}),
        ("--ppm", "10.5", {"ppm": 10.5}),
        ("--cell", "32x30", {"cell": (32, 30)}),
        ("--ground", "1,2,-3", {"ground": (1.0, 2.0, -3.0)}),
        ("--ground-px", "3,4", {"ground_px": (3, 4)}),
        ("--root-motion", "error", {"root_motion": "error"}),
        ("--reduce", "plain", {"reduce": "plain"}),
        ("--reduce", "mode", {"reduce": "mode"}),
        ("--pitch", "10", {"pitch": 10.0, "view": "custom"}),
        ("--directions", "4", {"directions": 4, "view": "custom"}),
        ("--start-angle", "45", {"start_angle": 45.0, "view": "custom"}),
    ],
)
def test_each_explicit_option_overrides_its_reused_value(
    tmp_path, option, value, changed
):
    options = reuse(write_sheet(tmp_path), option, value)
    assert values(options) == REUSED | changed


def test_a_matching_default_given_explicitly_still_wins(tmp_path):
    options = reuse(write_sheet(tmp_path), "--fps", "12", "--supersample", "8")
    assert (options.fps, options.supersample) == (12.0, 8)


def test_explicit_settings_resolve_into_a_fixed_configuration(tmp_path):
    options = reuse(write_sheet(tmp_path), "--ppm", "5", "--cell", "16x16")
    assert (options.ppm, options.cell, options.ground_px) == (5.0, (16, 16), (24, 37))


# The view


@pytest.mark.parametrize(
    "overrides",
    [(), ("--pitch", "45"), ("--directions", "16"), ("--start-angle", "-30")],
)
def test_an_explicit_view_resolves_exactly_as_without_reuse(tmp_path, overrides):
    with_reuse = reuse(write_sheet(tmp_path), "--view", "topdown", *overrides)
    without = cli.parse_args(["--view", "topdown", *overrides, "in.glb", "out.png"])
    view = ("view", "pitch", "directions", "start_angle")
    assert values(with_reuse, view) == values(without, view)
    assert values(with_reuse, REUSED.keys() - set(view)) == {
        name: REUSED[name] for name in REUSED.keys() - set(view)
    }


def test_an_explicit_default_view_still_replaces_the_reused_view(tmp_path):
    options = reuse(write_sheet(tmp_path), "--view", "iso")
    assert values(options, ("view", "pitch", "directions", "start_angle")) == {
        "view": "iso",
        "pitch": 30.0,
        "directions": 8,
        "start_angle": 0.0,
    }


def test_an_individual_override_keeps_the_rest_of_the_reused_view(tmp_path):
    options = reuse(write_sheet(tmp_path), "--pitch", "60")
    assert values(options, ("view", "pitch", "directions", "start_angle")) == {
        "view": "custom",
        "pitch": 60.0,
        "directions": 2,
        "start_angle": 90.0,
    }


def test_a_reused_custom_view_keeps_its_recorded_values(tmp_path):
    settings = edited(
        {
            "view.preset": "custom",
            "view.pitch_deg": 52.5,
            "view.directions": 5,
            "view.start_angle_deg": 400.0,
        }
    )
    options = reuse(write_sheet(tmp_path, settings))
    assert values(options, ("view", "pitch", "directions", "start_angle")) == {
        "view": "custom",
        "pitch": 52.5,
        "directions": 5,
        "start_angle": 400.0,
    }


def test_a_reused_preset_name_keeps_its_recorded_values(tmp_path):
    # The recorded parameters are reused as written, not the preset's.
    settings = edited({"view.preset": "iso", "view.pitch_deg": 31.0})
    options = reuse(write_sheet(tmp_path, settings))
    assert (options.view, options.pitch, options.directions) == ("iso", 31.0, 2)


# Clips


def test_clips_and_once_come_from_the_command_line(tmp_path):
    options = reuse(
        write_sheet(tmp_path), "--clip", "run", "--clip", "walk", "--once", "run"
    )
    assert (options.clip, options.once) == (("run", "walk"), ("run",))


def test_reused_one_shot_markings_are_not_restored(tmp_path):
    options = reuse(write_sheet(tmp_path))
    assert (options.clip, options.once) == (None, ())


@pytest.mark.parametrize(
    "clips", [[], "nonsense", None, [{"name": 5, "loop": "x", "extra": 1}], {}]
)
def test_the_reused_clips_are_never_read(tmp_path, clips):
    options = reuse(write_sheet(tmp_path, edited({"clips": clips})))
    assert values(options) == REUSED


def test_reused_clips_may_be_absent(tmp_path):
    options = reuse(write_sheet(tmp_path, edited(removed=["clips"])))
    assert values(options) == REUSED


# What the file must be


def test_a_document_with_only_schema_and_settings_is_enough(tmp_path):
    path = tmp_path / "minimal.json"
    settings = edited(removed=["clips"])
    path.write_text(json.dumps({"schema": "moskophoros.sheet/3", "settings": settings}))
    assert values(reuse(path)) == REUSED


def test_the_rest_of_the_sheet_is_not_checked(tmp_path):
    path = write_sheet(
        tmp_path,
        generator=None,
        source="anything",
        fingerprint=5,
        image=[],
        frames={"unknown": True},
        extra="ignored",
    )
    assert values(reuse(path)) == REUSED


def test_a_whole_float_ground_pixel_is_accepted_as_its_option_accepts_it(tmp_path):
    settings = edited({"ground_px.x": 24.0, "ground_px.y": 3.7e1})
    assert reuse(write_sheet(tmp_path, settings)).ground_px == (24, 37)


def test_integer_valued_numbers_are_accepted_as_floats(tmp_path):
    settings = edited({"fps": 24, "pixels_per_meter": 32, "view.pitch_deg": 0})
    options = reuse(write_sheet(tmp_path, settings))
    assert (options.fps, options.ppm, options.pitch) == (24.0, 32.0, 0.0)
    assert all(type(v) is float for v in (options.fps, options.ppm, options.pitch))


# Rejections: the file


def test_a_missing_file_is_rejected(tmp_path, capsys):
    problem = rejected(capsys, tmp_path / "missing.json")
    assert problem == "cannot be read: No such file or directory"


def test_a_directory_is_rejected(tmp_path, capsys):
    (tmp_path / "dir.json").mkdir()
    problem = rejected(capsys, tmp_path / "dir.json")
    assert problem.startswith("cannot be read: ")


def test_a_file_that_is_not_utf_8_is_rejected(tmp_path, capsys):
    path = tmp_path / "latin1.json"
    path.write_bytes(json.dumps({"schema": "é"}, ensure_ascii=False).encode("latin-1"))
    assert rejected(capsys, path).startswith("is not UTF-8: invalid ")


@pytest.mark.parametrize(
    "text", ["", "{", '{"schema": "moskophoros.sheet/1",}', "NaN", '{"a": Infinity}']
)
def test_a_file_that_is_not_json_is_rejected(tmp_path, capsys, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    assert rejected(capsys, path).startswith("is not valid JSON: ")


def test_a_deeply_nested_file_is_rejected(tmp_path, capsys):
    path = tmp_path / "deep.json"
    path.write_text("[" * 200_000 + "]" * 200_000)
    assert rejected(capsys, path) == "is not valid JSON: it is nested too deeply"


@pytest.mark.parametrize(
    ("text", "key"),
    [
        (
            '{"schema": "moskophoros.sheet/1", "schema": "moskophoros.sheet/1"}',
            "schema",
        ),
        ('{"settings": {"fps": 12, "fps": 12}}', "fps"),
        ('{"frames": [{"x": 0, "x": 0}]}', "x"),
        ('{"settings": {"style": {"reduce": "plain", "reduce": "plain"}}}', "reduce"),
        ('{"settings": {"style": {}, "style": {}}}', "style"),
    ],
)
def test_a_repeated_key_anywhere_is_rejected(tmp_path, capsys, text, key):
    path = tmp_path / "repeat.json"
    path.write_text(text)
    assert rejected(capsys, path) == f"repeats the key {key!r}"


NOT_A_SHEET = (
    "is not a moskophoros.sheet/3 or moskophoros.sheet/2 or moskophoros.sheet/1 "
    "document"
)


@pytest.mark.parametrize(
    ("document", "problem"),
    [
        ([], f"{NOT_A_SHEET}: not a JSON object"),
        ({}, f"{NOT_A_SHEET}: schema is missing"),
        (
            {"schema": "moskophoros.sheet/4"},
            f'{NOT_A_SHEET}: schema is "moskophoros.sheet/4"',
        ),
        (
            {"schema": "moskophoros.sheet/0"},
            f'{NOT_A_SHEET}: schema is "moskophoros.sheet/0"',
        ),
        (
            {"schema": " moskophoros.sheet/2"},
            f'{NOT_A_SHEET}: schema is " moskophoros.sheet/2"',
        ),
        ({"schema": 1}, f"{NOT_A_SHEET}: schema is 1"),
        (
            {"schema": ["moskophoros.sheet/2"]},
            f'{NOT_A_SHEET}: schema is ["moskophoros.sheet/2"]',
        ),
        ({"schema": None}, f"{NOT_A_SHEET}: schema is null"),
        ({"schema": "moskophoros.sheet/2"}, "settings: missing"),
        ({"schema": "moskophoros.sheet/1"}, "settings: missing"),
        (
            {"schema": "moskophoros.sheet/2", "settings": None},
            "settings: must be set, got null",
        ),
        (
            {"schema": "moskophoros.sheet/1", "settings": []},
            "settings: expected an object, got []",
        ),
    ],
)
def test_a_file_that_is_not_a_sheet_is_rejected(tmp_path, capsys, document, problem):
    path = tmp_path / "other.json"
    path.write_text(json.dumps(document))
    assert rejected(capsys, path) == problem


# Rejections: the settings

REUSED_FIELDS = [
    "view",
    "view.preset",
    "view.projection",
    "view.pitch_deg",
    "view.directions",
    "view.start_angle_deg",
    "model_yaw_deg",
    "fps",
    "supersample",
    "pixels_per_meter",
    "cell",
    "cell.width",
    "cell.height",
    "ground_m",
    "ground_m.x",
    "ground_m.y",
    "ground_m.z",
    "ground_px",
    "ground_px.x",
    "ground_px.y",
    "root_motion",
    "style",
    "style.reduce",
    "style.palette",
]


@pytest.mark.parametrize("field", REUSED_FIELDS)
def test_a_missing_field_is_rejected(tmp_path, capsys, field):
    path = write_sheet(tmp_path, edited(removed=[field]))
    assert rejected(capsys, path) == f"settings.{field}: missing"


@pytest.mark.parametrize(
    ("field", "value", "problem"),
    [
        ("view", "iso", 'expected an object, got "iso"'),
        (
            "view.preset",
            "perspective",
            "expected 'topdown' or 'side' or 'iso' or 'iso-true' or 'custom', "
            'got "perspective"',
        ),
        (
            "view.preset",
            "ISO",
            "expected 'topdown' or 'side' or 'iso' or 'iso-true' or 'custom', "
            'got "ISO"',
        ),
        ("view.pitch_deg", 90.5, "must be from 0 to 90, got '90.5'"),
        ("view.pitch_deg", -0.1, "must be from 0 to 90, got '-0.1'"),
        ("view.pitch_deg", "30", 'expected a number, got "30"'),
        ("view.pitch_deg", True, "expected a number, got true"),
        ("view.directions", 0, "must be from 1 to 64, got '0'"),
        ("view.directions", 65, "must be from 1 to 64, got '65'"),
        ("view.directions", 8.0, "expected an integer, got '8.0'"),
        ("view.directions", False, "expected a number, got false"),
        ("view.start_angle_deg", [0], "expected a number, got [0]"),
        ("model_yaw_deg", "0", 'expected a number, got "0"'),
        ("fps", 0, "must be greater than 0, got '0'"),
        ("fps", -12.0, "must be greater than 0, got '-12.0'"),
        ("fps", {"value": 12}, 'expected a number, got {"value": 12}'),
        ("supersample", 17, "must be from 1 to 16, got '17'"),
        ("supersample", 4.5, "expected an integer, got '4.5'"),
        ("pixels_per_meter", 0.0, "must be greater than 0, got '0.0'"),
        ("pixels_per_meter", "32", 'expected a number, got "32"'),
        ("cell", [48, 40], "expected an object, got [48, 40]"),
        ("cell.width", 0, "must be from 1 to 4096, got '0'"),
        ("cell.height", 4097, "must be from 1 to 4096, got '4097'"),
        ("cell.width", 48.0, "expected an integer, got '48.0'"),
        ("ground_m", [0, 0, 0], "expected an object, got [0, 0, 0]"),
        ("ground_m.y", "0", 'expected a number, got "0"'),
        ("ground_px.x", -1, "expected a whole number 0 or greater, got '-1'"),
        ("ground_px.y", 2.5, "expected a whole number 0 or greater, got '2.5'"),
        ("ground_px.x", True, "expected a number, got true"),
        ("ground_px.y", "3", 'expected a number, got "3"'),
        ("root_motion", "ignore", "expected 'error' or 'keep', got \"ignore\""),
        ("root_motion", 1, "expected 'error' or 'keep', got 1"),
        ("style", "plain", 'expected an object, got "plain"'),
        ("style", [], "expected an object, got []"),
        ("style.reduce", "median", "expected 'plain' or 'mode', got \"median\""),
        ("style.reduce", "Plain", "expected 'plain' or 'mode', got \"Plain\""),
        ("style.reduce", "MODE", "expected 'plain' or 'mode', got \"MODE\""),
        ("style.reduce", 1, "expected 'plain' or 'mode', got 1"),
        ("style.reduce", ["plain"], "expected 'plain' or 'mode', got [\"plain\"]"),
        ("style.palette", [], "expected an object, got []"),
        ("style.palette", "", 'expected an object, got ""'),
        ("style.palette", False, "expected an object, got false"),
    ],
)
def test_an_unacceptable_value_is_rejected(tmp_path, capsys, field, value, problem):
    path = write_sheet(tmp_path, edited({field: value}))
    assert rejected(capsys, path) == f"settings.{field}: {problem}"


@pytest.mark.parametrize("projection", ["perspective", "Orthographic", None, 0])
def test_the_projection_must_be_orthographic(tmp_path, capsys, projection):
    path = write_sheet(tmp_path, edited({"view.projection": projection}))
    problem = rejected(capsys, path)
    assert problem.startswith("settings.view.projection: ")
    shown = "must be set, got null" if projection is None else "expected 'orthographic'"
    assert shown in problem


@pytest.mark.parametrize("field", ["pixels_per_meter", "cell", "ground_px"])
def test_the_fixed_values_must_be_set(tmp_path, capsys, field):
    path = write_sheet(tmp_path, edited({field: None}))
    assert rejected(capsys, path) == f"settings.{field}: must be set, got null"


@pytest.mark.parametrize(
    "field",
    ["fps", "view.pitch_deg", "root_motion", "ground_m", "style", "style.reduce"],
)
def test_other_null_fields_are_rejected(tmp_path, capsys, field):
    path = write_sheet(tmp_path, edited({field: None}))
    assert rejected(capsys, path) == f"settings.{field}: must be set, got null"


@pytest.mark.parametrize(
    "field",
    [
        "variant",
        "view.roll_deg",
        "cell.depth",
        "ground_px.z",
        "ground_m.w",
        "style.dither",
    ],
)
def test_an_unknown_field_is_rejected(tmp_path, capsys, field):
    path = write_sheet(tmp_path, edited({field: 0}))
    assert rejected(capsys, path) == f"settings.{field}: unknown field"


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("1e400", "expected a finite number, got 'inf'"),
        ("-1e400", "expected a finite number, got '-inf'"),
        ("1" + "0" * 400, "expected a finite number, got '1" + "0" * 400 + "'"),
    ],
)
def test_a_number_too_large_for_a_float_is_rejected(tmp_path, capsys, text, problem):
    path = write_sheet(tmp_path, edited({"fps": "FPS"}))
    path.write_text(path.read_text().replace('"FPS"', text))
    assert rejected(capsys, path) == f"settings.fps: {problem}"


def test_a_field_an_explicit_option_replaces_is_still_checked(tmp_path, capsys):
    path = write_sheet(tmp_path, edited({"fps": -1, "view.directions": 0}))
    problem = rejected(capsys, path, "--fps", "6", "--view", "iso")
    assert problem == (
        "settings.view.directions: must be from 1 to 64, got '0'; "
        "settings.fps: must be greater than 0, got '-1'"
    )


def test_an_invalid_reused_style_is_checked_despite_an_explicit_reduce(
    tmp_path, capsys
):
    path = write_sheet(tmp_path, edited({"style.reduce": "median", "style.palette": 1}))
    problem = rejected(capsys, path, "--reduce", "plain")
    assert problem == (
        "settings.style.reduce: expected 'plain' or 'mode', got \"median\"; "
        "settings.style.palette: expected an object, got 1"
    )


@pytest.mark.parametrize("style", [None, "plain", {}])
def test_a_style_an_explicit_reduce_replaces_is_still_checked(tmp_path, capsys, style):
    path = write_sheet(tmp_path, edited({"style": style}))
    assert rejected(capsys, path, "--reduce", "plain").startswith("settings.style")


def test_every_problem_is_reported_in_field_order(tmp_path, capsys):
    settings = edited({"extra": 1, "cell.width": 0, "ground_px": None}, ["fps"])
    problem = rejected(capsys, write_sheet(tmp_path, settings))
    assert problem == (
        "settings.fps: missing; "
        "settings.cell.width: must be from 1 to 4096, got '0'; "
        "settings.ground_px: must be set, got null; "
        "settings.extra: unknown field"
    )


def test_a_long_value_is_shown_cut_short(tmp_path, capsys):
    path = write_sheet(tmp_path, edited({"root_motion": "x" * 100}))
    problem = rejected(capsys, path)
    assert problem == "settings.root_motion: expected 'error' or 'keep', got \"" + (
        "x" * 56 + "..."
    )


# The reduction


def test_a_mode_sheet_reuses_mode(tmp_path):
    options = reuse(write_sheet(tmp_path, edited({"style.reduce": "mode"})))
    assert values(options) == REUSED | {"reduce": "mode"}
    assert cli.style_record(options) == PLAIN | {"reduce": "mode"}


@pytest.mark.parametrize(("sheet", "explicit"), [("mode", "plain"), ("plain", "mode")])
def test_an_explicit_reduce_overrides_the_reused_one(tmp_path, sheet, explicit):
    path = write_sheet(tmp_path, edited({"style.reduce": sheet}))
    options = reuse(path, "--reduce", explicit)
    assert values(options) == REUSED | {"reduce": explicit}


def test_a_legacy_sheet_with_an_explicit_mode_records_mode(tmp_path):
    options = reuse(write_legacy_sheet(tmp_path), "--reduce", "mode")
    assert cli.style_record(options) == PLAIN | {"reduce": "mode"}


# Older `/1` sheets


def test_a_legacy_sheet_reuses_as_plain(tmp_path):
    options = reuse(write_legacy_sheet(tmp_path))
    assert values(options) == REUSED
    assert cli.style_record(options) == PLAIN


def test_a_legacy_sheet_with_an_explicit_reduce_records_it(tmp_path):
    options = reuse(write_legacy_sheet(tmp_path), "--reduce", "plain")
    assert options.reduce == "plain"
    assert "reduce" in options.explicit


def test_a_legacy_sheet_carrying_a_style_is_refused(tmp_path, capsys):
    path = write_legacy_sheet(tmp_path, SETTINGS)
    assert rejected(capsys, path) == "settings.style: unknown field"


@pytest.mark.parametrize("field", ["fps", "view.directions", "ground_px"])
def test_a_legacy_sheet_is_checked_as_before(tmp_path, capsys, field):
    path = write_legacy_sheet(tmp_path, edited({field: None}, base=LEGACY_SETTINGS))
    assert rejected(capsys, path) == f"settings.{field}: must be set, got null"


def test_a_legacy_sheet_missing_a_field_names_it(tmp_path, capsys):
    path = write_legacy_sheet(tmp_path, edited(removed=["fps"], base=LEGACY_SETTINGS))
    assert rejected(capsys, path) == "settings.fps: missing"


# Fixed configuration


def _measurements(clip, right):
    address = sampling.FrameAddress("hero", "default", clip, 0, 0.0)
    bounds = fit.Bounds(left=0.25, right=right, up=1.0, down=0.0)
    return {address: fit.Measurement(bounds, height=1.0)}


def test_a_reused_configuration_resolves_as_fixed(tmp_path):
    options = reuse(write_sheet(tmp_path), "--clip", "walk")
    resolved = fit.resolve(
        _measurements("walk", 0.5), options.ppm, options.cell, options.ground_px
    )
    assert (resolved.ppm, resolved.cell, resolved.ground_px) == (
        32.0,
        (48, 40),
        (24, 37),
    )


def test_a_clip_that_no_longer_fits_overflows_and_is_never_shrunk(tmp_path):
    options = reuse(write_sheet(tmp_path), "--clip", "leap")
    # 1 m right of the ground point is 32 px at the reused scale; the ground
    # pixel leaves 24.
    with pytest.raises(fit.CellOverflow) as raised:
        fit.resolve(
            _measurements("leap", 1.0), options.ppm, options.cell, options.ground_px
        )
    assert raised.value.exit_code == 4
    ((address, overshoot),) = raised.value.frames
    assert address.clip == "leap"
    assert overshoot == {"right": 8}
    assert "32.0 pixels per meter" in str(raised.value)
    assert "48x40 cell" in str(raised.value)


# Round trip through the tool's own sheets

GENERATOR = {
    "tool": "moskophoros",
    "version": "0.1.0",
    "python": "3.13.15",
    "numpy": "2.5.3",
    "pillow": "12.3.0",
    "blender": "5.2.2",
    "renderer": "workbench",
    "studio_light": "rim.sl",
}
SOURCE = Source(Path("/models/hero.glb"), "cd" * 32, 0)
SUBJECT = gltf.Subject(
    Path("/models/hero.glb"),
    "hero",
    0,
    (
        gltf.Clip(0, "walk", 0.0, 0.5, ()),
        gltf.Clip(1, "attack", 0.25, 0.5, ()),
    ),
)
ORIGINALS = {
    "iso": Settings(
        view="iso",
        pitch=30.0,
        directions=8,
        start_angle=0.0,
        model_yaw=0.0,
        fps=12.0,
        supersample=8,
        ppm=24.5,
        cell=(3, 2),
        ground=(0.0, 0.0, 0.0),
        ground_px=(1, 1),
        root_motion="error",
    ),
    "iso-true": Settings(
        view="iso-true",
        pitch=cli.PRESETS["iso-true"].pitch,
        directions=8,
        start_angle=0.0,
        model_yaw=12.5,
        fps=7.0,
        supersample=3,
        ppm=0.1,
        cell=(2, 4),
        ground=(0.5, -1e-3, 2.0),
        ground_px=(0, 9),
        root_motion="keep",
    ),
    "custom": Settings(
        view="custom",
        pitch=47.25,
        directions=3,
        start_angle=-370.5,
        model_yaw=-90.0,
        fps=10.0,
        supersample=1,
        ppm=1000.0,
        cell=(1, 1),
        ground=(1.0, 2.0, 3.0),
        ground_px=(1, 1),
        root_motion="error",
    ),
}


PLAIN = {
    "reduce": "plain",
    "palette": None,
    "materials": None,
    "shade_range": [84, 191],
}


def _encode(settings, clip_names, once_names, style=PLAIN):
    selected = gltf.select_clips(SUBJECT, clip_names, once_names)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    width, height = settings.cell
    frames = [
        sampling.ImageFrame(frame.address, np.zeros((height, width, 4), dtype=np.uint8))
        for frame in sampling.frames("hero", selected, view, settings.fps)
    ]
    return export.encode(
        frames,
        generator=GENERATOR,
        source=SOURCE,
        subject="hero",
        settings=settings,
        style=style,
        selected_clips=selected,
        image_path=Path("hero.png"),
    )


def _rerun(path, *options):
    """Reuse the sheet at `path` with `options`, and encode again."""
    resolved = reuse(path, *options)
    return _encode(
        cli.capture_settings(resolved),
        resolved.clip or (),
        resolved.once,
        cli.style_record(resolved),
    )


@pytest.mark.parametrize("view", ORIGINALS)
@pytest.mark.parametrize(
    "selection",
    [
        (),
        ("--once", "attack"),
        ("--clip", "attack", "--clip", "walk"),
        ("--clip", "walk", "--clip", "attack", "--once", "walk", "--once", "attack"),
    ],
)
def test_reusing_a_sheet_with_the_same_clips_gives_the_same_settings(
    tmp_path, view, selection
):
    parsed = cli.parse_args([*selection, "in.glb", "out.png"])
    original = _encode(ORIGINALS[view], parsed.clip or (), parsed.once)
    path = tmp_path / "hero.json"
    path.write_bytes(original.json)

    again = _rerun(path, *selection)

    before, after = json.loads(original.json), json.loads(again.json)
    assert after["settings"] == before["settings"]
    assert after["fingerprint"] == before["fingerprint"]
    assert again.json == original.json


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (("--once", "attack"), ()),
        ((), ("--once", "walk")),
        (("--clip", "walk", "--clip", "attack"), ("--clip", "attack")),
    ],
)
def test_reusing_with_other_clip_markings_changes_settings_and_fingerprint(
    tmp_path, first, second
):
    parsed = cli.parse_args([*first, "in.glb", "out.png"])
    original = _encode(ORIGINALS["iso"], parsed.clip or (), parsed.once)
    path = tmp_path / "hero.json"
    path.write_bytes(original.json)

    again = _rerun(path, *second)

    before, after = json.loads(original.json), json.loads(again.json)
    assert after["settings"]["clips"] != before["settings"]["clips"]
    assert {k: v for k, v in after["settings"].items() if k != "clips"} == {
        k: v for k, v in before["settings"].items() if k != "clips"
    }
    assert after["fingerprint"] != before["fingerprint"]


def test_an_override_on_a_reused_sheet_changes_only_that_value(tmp_path):
    original = _encode(ORIGINALS["iso"], (), ())
    path = tmp_path / "hero.json"
    path.write_bytes(original.json)

    again = json.loads(_rerun(path, "--pitch", "45").json)

    expected = json.loads(original.json)["settings"]
    expected["view"] |= {"preset": "custom", "pitch_deg": 45.0}
    assert again["settings"] == expected


# Effects

_AUDIT = {"events": None}


def _audit(event, args):
    if _AUDIT["events"] is not None:
        _AUDIT["events"].append((event, args))


sys.addaudithook(_audit)


@contextmanager
def audited():
    events = []
    _AUDIT["events"] = events
    try:
        yield events
    finally:
        _AUDIT["events"] = None


EFFECTS = (
    "subprocess.",
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "os.fork",
    "os.remove",
    "os.rename",
    "os.mkdir",
    "os.rmdir",
    "os.truncate",
    "os.chmod",
    "os.utime",
    "shutil.",
)


@pytest.mark.parametrize("valid", [True, False])
def test_reading_the_settings_file_is_the_only_effect(tmp_path, capsys, valid):
    model = tmp_path / "in.glb"
    model.write_bytes(b"glTF")
    path = write_sheet(tmp_path, None if valid else edited({"fps": 0}))
    argv = ["--settings-from", str(path), str(model), str(tmp_path / "out.png")]
    before = sorted(
        (str(p), p.stat().st_mtime_ns) for p in [tmp_path, *tmp_path.rglob("*")]
    )
    try:
        cli.resolve_settings(cli.parse_args(argv))  # warm any lazy imports
    except cli.UsageError:
        pass
    capsys.readouterr()

    with audited() as events:
        try:
            cli.resolve_settings(cli.parse_args(argv))
        except cli.UsageError:
            assert not valid
        else:
            assert valid

    opened = [args for event, args in events if event == "open"]
    assert [Path(args[0]) for args in opened] == [path]
    assert all(args[1] in ("r", "rb") for args in opened)
    assert [event for event, _ in events if event.startswith(EFFECTS)] == []
    after = sorted(
        (str(p), p.stat().st_mtime_ns) for p in [tmp_path, *tmp_path.rglob("*")]
    )
    assert after == before
    out, _ = capsys.readouterr()
    assert out == ""


@pytest.mark.parametrize("options", [(), ("--reduce", "plain")])
def test_a_reused_sheet_round_trips_its_style(tmp_path, options):
    original = _encode(ORIGINALS["custom"], (), ())
    path = tmp_path / "hero.json"
    path.write_bytes(original.json)

    again = _rerun(path, *options)

    assert json.loads(again.json)["settings"]["style"] == PLAIN
    assert again.json == original.json


@pytest.mark.parametrize("options", [(), ("--reduce", "plain")])
def test_a_reused_legacy_sheet_gives_the_same_sheet_as_plain(tmp_path, options):
    original = _encode(ORIGINALS["iso"], (), ())
    legacy = json.loads(original.json)
    legacy["schema"] = "moskophoros.sheet/1"
    del legacy["settings"]["style"]
    path = tmp_path / "hero.json"
    path.write_text(json.dumps(legacy, indent=2, ensure_ascii=False) + "\n")

    again = _rerun(path, *options)

    assert json.loads(again.json)["schema"] == "moskophoros.sheet/3"
    assert again.json == original.json


def test_a_reused_mode_sheet_round_trips_and_differs_from_plain(tmp_path):
    mode = PLAIN | {"reduce": "mode"}
    original = _encode(ORIGINALS["iso"], (), (), mode)
    path = tmp_path / "hero.json"
    path.write_bytes(original.json)

    again = _rerun(path)
    plain = json.loads(_rerun(path, "--reduce", "plain").json)

    assert again.json == original.json
    assert json.loads(again.json)["settings"]["style"] == mode
    assert plain["settings"]["style"] == PLAIN
    assert plain["fingerprint"] != json.loads(original.json)["fingerprint"]
