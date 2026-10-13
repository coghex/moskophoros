"""`--settings-from`: reading an earlier sheet's settings and merging them
with explicit options (design §Scale and ground point, Reuse)."""

import copy
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from shading import DEFAULT_RANGE, DEFAULT_SHADE

from moskophoros import cli, export, fit, gltf, sampling, views
from moskophoros.capture.backend import Settings, Shade, Source

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
    "frames": 6,
    "supersample": 4,
    "pixels_per_meter": 32.0,
    "cell": {"width": 48, "height": 40},
    "ground_m": {"x": 0.1, "y": -0.2, "z": 0.3},
    "ground_px": {"x": 24, "y": 37},
    "root_motion": "keep",
    "previews": False,
    "normals": False,
    "depth": True,
    "light": {"position": [-20.0, 30.0, 40.5], "intensity": 1.5, "ambient": 0.25},
    "shade": {
        "ao_distance_m": 1.2,
        "ao_samples": 32,
        "occlusion_weight": 0.5,
        "convexity_weight": 0.0,
        "range": [120, 188],
    },
    "style": {
        "reduce": "plain",
        "palette": None,
        "materials": None,
    },
    "clips": [
        {"name": "walk", "loop": True, "frames": 8},
        {"name": "attack", "loop": False, "frames": None},
    ],
}
REUSED = {
    "view": "side",
    "pitch": 0.0,
    "directions": 2,
    "start_angle": 90.0,
    "model_yaw": -45.0,
    "fps": 24.0,
    "frames": 6,
    "supersample": 4,
    "ppm": 32.0,
    "cell": (48, 40),
    "ground": (0.1, -0.2, 0.3),
    "ground_px": (24, 37),
    "root_motion": "keep",
    "previews": False,
    "normals": False,
    "depth": True,
    "light": (-20.0, 30.0, 40.5),
    "light_intensity": 1.5,
    "light_ambient": 0.25,
    "clip": ("walk", "attack"),
    "once": ("attack",),
    "clip_frames": {"walk": 8, "attack": None},
    "reduce": "plain",
    "shade_range": (120, 188),
    "ao_distance": 1.2,
    "ao_samples": 32,
    "occlusion_weight": 0.5,
    "convexity_weight": 0.0,
}


def write_sheet(tmp_path, settings=None, name="old.json", **document):
    path = tmp_path / name
    contents = {"schema": "moskophoros.sheet/10"} | document
    contents["settings"] = copy.deepcopy(SETTINGS if settings is None else settings)
    path.write_text(json.dumps(contents, ensure_ascii=False), encoding="utf-8")
    return path


def parse(path, *options):
    return cli.parse_args(
        [
            "--settings-from",
            str(path),
            "--no-user-config",
            *options,
            "in.glb",
            "out.png",
        ]
    )


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


def test_without_settings_from_or_settings_files_the_parsed_options_are_kept():
    options = cli.parse_args(["--pitch", "45", "in.glb", "out.png"])
    assert cli.resolve_settings(options) == options


def test_parsing_still_reads_no_settings_file(tmp_path):
    options = parse(tmp_path / "missing.json")
    assert options.settings_from == tmp_path / "missing.json"
    assert options.ppm is None


# What is reused


def test_every_reused_value_is_carried_over(tmp_path):
    options = reuse(write_sheet(tmp_path))
    assert values(options) == REUSED
    assert options.explicit == {"settings_from", "no_user_config"}


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
        ("--preview", None, {"previews": True}),
        ("--cell", "auto", {"cell": None}),
        ("--ao-distance", "0.3", {"ao_distance": 0.3}),
        ("--ao-samples", "128", {"ao_samples": 128}),
        ("--occlusion-weight", "0.25", {"occlusion_weight": 0.25}),
        ("--convexity-weight", "1", {"convexity_weight": 1.0}),
        ("--shade-range", "84,191", {"shade_range": (84, 191)}),
    ],
)
def test_each_explicit_option_overrides_its_reused_value(
    tmp_path, option, value, changed
):
    options = reuse(write_sheet(tmp_path), option, *([] if value is None else [value]))
    assert values(options) == REUSED | changed


def test_no_preview_keeps_a_sheet_made_without_previews_without_them(tmp_path):
    with_previews = write_sheet(tmp_path, edited({"previews": True}), name="p.json")
    assert reuse(with_previews).previews is True
    assert reuse(with_previews, "--no-preview").previews is False
    assert reuse(write_sheet(tmp_path)).previews is False


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


# Clips (settings design D-19 and D-27)


def test_the_loaded_clips_and_one_shot_marks_stay_without_clip_or_once(tmp_path):
    options = reuse(write_sheet(tmp_path))
    assert (options.clip, options.once) == (("walk", "attack"), ("attack",))


def test_an_explicit_clip_replaces_the_selection_and_its_marks(tmp_path):
    options = reuse(
        write_sheet(tmp_path), "--clip", "run", "--clip", "walk", "--once", "run"
    )
    assert (options.clip, options.once) == (("run", "walk"), ("run",))
    options = reuse(write_sheet(tmp_path), "--clip", "attack")
    assert (options.clip, options.once) == (("attack",), ())


@pytest.mark.parametrize(
    ("once", "marked"),
    [(["walk"], ("walk",)), (["walk", "attack"], ("walk", "attack"))],
)
def test_once_alone_replaces_the_loaded_marks(tmp_path, once, marked):
    options = []
    for name in once:
        options += ["--once", name]
    reused = reuse(write_sheet(tmp_path), *options)
    assert (reused.clip, reused.once) == (("walk", "attack"), marked)


def test_once_naming_a_clip_outside_the_loaded_list_is_a_usage_error(tmp_path, capsys):
    with pytest.raises(cli.UsageError) as raised:
        reuse(write_sheet(tmp_path), "--once", "run")
    assert raised.value.message == (
        "argument --once: 'run' is not among the loaded sheet's clips: 'walk', 'attack'"
    )
    assert capsys.readouterr().err.splitlines()[0] == USAGE_LINE


@pytest.mark.parametrize(
    ("clips", "problem"),
    [
        ([], "expected a nonempty list of clips, got []"),
        ("nonsense", 'expected a nonempty list of clips, got "nonsense"'),
        ({}, "expected a nonempty list of clips, got {}"),
        (
            [{"name": "walk", "loop": True}],
            '[0]: expected exactly {"name": NAME, "loop": BOOLEAN, "frames": FRAMES}, '
            'got {"name": "walk", "loop": true}',
        ),
        (
            [{"name": "walk", "loop": True, "frames": None, "extra": 1}],
            '[0]: expected exactly {"name": NAME, "loop": BOOLEAN, "frames": FRAMES}, '
            'got {"name": "walk", "loop": true, "frames": null, "extra": 1}',
        ),
        (
            ["walk"],
            '[0]: expected exactly {"name": NAME, "loop": BOOLEAN, "frames": FRAMES}, '
            'got "walk"',
        ),
        (
            [{"name": 5, "loop": True, "frames": None}],
            "[0].name: expected a nonempty clip name, got 5",
        ),
        (
            [{"name": "", "loop": True, "frames": None}],
            '[0].name: expected a nonempty clip name, got ""',
        ),
        (
            [{"name": "a", "loop": 1, "frames": None}],
            "[0].loop: expected true or false, got 1",
        ),
        (
            [{"name": "a", "loop": True, "frames": 0}],
            "[0].frames: expected a whole number 1 or more, 'auto' or null, got 0",
        ),
        (
            [{"name": "a", "loop": True, "frames": 8.0}],
            "[0].frames: expected a whole number 1 or more, 'auto' or null, got 8.0",
        ),
        (
            [{"name": "a", "loop": True, "frames": True}],
            "[0].frames: expected a whole number 1 or more, 'auto' or null, got true",
        ),
        (
            [{"name": "a", "loop": True, "frames": "8"}],
            "[0].frames: expected a whole number 1 or more, 'auto' or null, got \"8\"",
        ),
        (
            [
                {"name": "a", "loop": True, "frames": None},
                {"name": "a", "loop": False, "frames": None},
            ],
            '[1].name: the clip "a" is recorded twice',
        ),
    ],
)
def test_a_malformed_clip_selection_is_rejected(tmp_path, capsys, clips, problem):
    path = write_sheet(tmp_path, edited({"clips": clips}))
    assert rejected(capsys, path) == f"settings.clips: {problem}"


@pytest.mark.parametrize("options", [(), ("--clip", "walk"), ("--once", "walk")])
def test_a_malformed_clip_selection_is_rejected_even_when_clip_replaces_it(
    tmp_path, capsys, options
):
    path = write_sheet(tmp_path, edited({"clips": None}))
    assert rejected(capsys, path, *options) == "settings.clips: must be set, got null"
    path = write_sheet(tmp_path, edited(removed=["clips"]))
    assert rejected(capsys, path, *options) == "settings.clips: missing"


@pytest.mark.parametrize("value", [None, "true", 1, 0])
def test_previews_must_be_a_boolean(tmp_path, capsys, value):
    path = write_sheet(tmp_path, edited({"previews": value}))
    problem = rejected(capsys, path, "--preview")
    if value is None:
        assert problem == "settings.previews: must be set, got null"
    else:
        assert problem.startswith("settings.previews: expected true or false, got ")


# What the file must be


def test_a_document_with_only_schema_and_settings_is_enough(tmp_path):
    path = tmp_path / "minimal.json"
    path.write_text(
        json.dumps({"schema": "moskophoros.sheet/10", "settings": SETTINGS})
    )
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
            '{"schema": "moskophoros.sheet/10", "schema": "moskophoros.sheet/10"}',
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


NOT_A_SHEET = "is not a moskophoros.sheet/10 document"


def older(schema):
    return f"is a {schema} sheet; only moskophoros.sheet/10 sheets load, so generate it again"


@pytest.mark.parametrize(
    ("document", "problem"),
    [
        ([], f"{NOT_A_SHEET}: not a JSON object"),
        ({}, f"{NOT_A_SHEET}: schema is missing"),
        ({"schema": "moskophoros.sheet/3"}, older("moskophoros.sheet/3")),
        ({"schema": "moskophoros.sheet/2"}, older("moskophoros.sheet/2")),
        ({"schema": "moskophoros.sheet/1"}, older("moskophoros.sheet/1")),
        ({"schema": "moskophoros.sheet/6"}, older("moskophoros.sheet/6")),
        ({"schema": "moskophoros.sheet/5"}, older("moskophoros.sheet/5")),
        ({"schema": "moskophoros.sheet/4"}, older("moskophoros.sheet/4")),
        ({"schema": "moskophoros.sheet/11"}, older("moskophoros.sheet/11")),
        ({"schema": "moskophoros.sheet/9"}, older("moskophoros.sheet/9")),
        ({"schema": "moskophoros.sheet/8"}, older("moskophoros.sheet/8")),
        ({"schema": "moskophoros.sheet/7"}, older("moskophoros.sheet/7")),
        (
            {"schema": " moskophoros.sheet/4"},
            f'{NOT_A_SHEET}: schema is " moskophoros.sheet/4"',
        ),
        ({"schema": 1}, f"{NOT_A_SHEET}: schema is 1"),
        (
            {"schema": ["moskophoros.sheet/10"]},
            f'{NOT_A_SHEET}: schema is ["moskophoros.sheet/10"]',
        ),
        ({"schema": None}, f"{NOT_A_SHEET}: schema is null"),
        ({"schema": "moskophoros.sheet/10"}, "settings: missing"),
        (
            {"schema": "moskophoros.sheet/10", "settings": None},
            "settings: must be set, got null",
        ),
        (
            {"schema": "moskophoros.sheet/10", "settings": []},
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
    "previews",
    "normals",
    "depth",
    "light",
    "light.position",
    "light.intensity",
    "light.ambient",
    "shade",
    "shade.ao_distance_m",
    "shade.ao_samples",
    "shade.occlusion_weight",
    "shade.convexity_weight",
    "shade.range",
    "style",
    "style.reduce",
    "style.palette",
    "style.materials",
    "clips",
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
        ("shade", [], "expected an object, got []"),
        ("shade.ao_distance_m", 0, "must be greater than 0, got '0'"),
        ("shade.ao_distance_m", -1.0, "must be greater than 0, got '-1.0'"),
        ("shade.ao_distance_m", "0.3", 'expected a number, got "0.3"'),
        (
            "shade.ao_samples",
            129,
            "must be from 1 to 128, the most Blender's ambient occlusion takes, "
            "got '129'",
        ),
        (
            "shade.ao_samples",
            0,
            "must be from 1 to 128, the most Blender's ambient occlusion takes, "
            "got '0'",
        ),
        ("shade.ao_samples", 64.0, "expected an integer, got '64.0'"),
        ("shade.ao_samples", True, "expected a number, got true"),
        ("shade.occlusion_weight", -0.25, "must be 0 or greater, got '-0.25'"),
        ("shade.convexity_weight", -1, "must be 0 or greater, got '-1'"),
        ("shade.convexity_weight", False, "expected a number, got false"),
        ("shade.range", [191, 84], "expected 0 <= lo < hi <= 255, got [191, 84]"),
        ("shade.range", [84, 256], "expected 0 <= lo < hi <= 255, got [84, 256]"),
        ("shade.range", [84.0, 191], "expected two integers [lo, hi], got [84.0, 191]"),
        ("shade.range", "84,191", 'expected two integers [lo, hi], got "84,191"'),
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
        "shade.ao_quality",
        "style.dither",
        "style.shade_range",
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


@pytest.mark.parametrize(
    "schema",
    [
        "moskophoros.sheet/9",
        "moskophoros.sheet/8",
        "moskophoros.sheet/7",
        "moskophoros.sheet/6",
        "moskophoros.sheet/5",
        "moskophoros.sheet/4",
        "moskophoros.sheet/3",
        "moskophoros.sheet/2",
        "moskophoros.sheet/1",
    ],
)
@pytest.mark.parametrize("options", [(), ("--reduce", "plain"), ("--clip", "walk")])
def test_an_older_sheet_is_a_usage_error_whatever_overrides_it(
    tmp_path, capsys, schema, options
):
    path = write_sheet(tmp_path, schema=schema)
    assert rejected(capsys, path, *options) == older(schema)


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
        shade=DEFAULT_SHADE,
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
        shade=Shade(1.2, 128, 0.5, 0.0),
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
        shade=DEFAULT_SHADE,
    ),
}


PLAIN = {
    "reduce": "plain",
    "palette": None,
    "materials": None,
}


def _encode(
    settings,
    clip_names,
    once_names,
    style=PLAIN,
    previews=True,
    shade_range=DEFAULT_RANGE,
    normals=True,
    depth=False,
    light=export.NO_LIGHT,
):
    """The encoded sheet, with `lit`, its lit previews' GIFs when a light is
    placed and previews are on."""
    selected = gltf.select_clips(SUBJECT, clip_names, once_names)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    width, height = settings.cell

    def frame(address):
        # The left half covered, facing the viewer at a depth for its
        # direction, in front of and behind the ground point.
        pixels = np.zeros((height, width, 4), dtype=np.uint8)
        pixels[:, : width // 2] = (90, 60, 30, 255)
        normals = np.zeros((height, width, 3))
        normals[:, : width // 2, 2] = 1.0
        depths = np.zeros((height, width))
        depths[:, : width // 2] = address.direction * 1.5 - 3.25
        maps = {sampling.NORMAL_MAP: normals, sampling.DEPTH_MAP: depths}
        return sampling.ImageFrame(address, pixels, buffers=maps)

    frames = [
        frame(requested.address)
        for requested in sampling.frames("hero", selected, view, settings.fps)
    ]
    sheet = export.encode(
        frames,
        generator=GENERATOR,
        source=SOURCE,
        subject="hero",
        settings=settings,
        style=style,
        previews=previews,
        normals=normals,
        depth=depth,
        light=light,
        shade_range=shade_range,
        selected_clips=selected,
        image_path=Path("hero.png"),
    )
    lit = ()
    if previews and light.position is not None:
        lit = tuple(
            preview.gif
            for preview in export.lit_previews(
                frames,
                subject="hero",
                settings=settings,
                selected_clips=selected,
                light=light,
            )
        )
    return SimpleNamespace(**vars(sheet), lit=lit)


def _rerun(path, *options):
    """Reuse the sheet at `path` with `options`, and encode again."""
    resolved = reuse(path, *options)
    return _encode(
        cli.capture_settings(resolved),
        resolved.clip or (),
        resolved.once,
        cli.style_record(resolved),
        resolved.previews,
        resolved.shade_range,
        resolved.normals,
        resolved.depth,
        export.Light(resolved.light, resolved.light_intensity, resolved.light_ambient),
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
    "light", [export.NO_LIGHT, export.Light((-20.0, 30.0, 40.0), 1.5, 0.2)]
)
@pytest.mark.parametrize("depth", [False, True])
@pytest.mark.parametrize("normals", [True, False])
@pytest.mark.parametrize("previews", [True, False])
@pytest.mark.parametrize(
    "selection",
    [
        (),
        ("--once", "attack"),
        ("--clip", "attack", "--clip", "walk"),
        ("--clip", "walk", "--once", "walk"),
    ],
)
def test_loading_a_sheet_with_no_options_reproduces_it(
    tmp_path, selection, previews, normals, depth, light
):
    """Settings design D-16: the loaded sheet supplies every setting, the
    clip selection, its one-shot marks and the previews, normals and depth
    flags included; each map is reproduced byte for byte, or not written."""
    parsed = cli.parse_args([*selection, "in.glb", "out.png"])
    original = _encode(
        ORIGINALS["iso-true"],
        parsed.clip or (),
        parsed.once,
        previews=previews,
        shade_range=(120, 255),
        normals=normals,
        depth=depth,
        light=light,
    )
    path = tmp_path / "hero.json"
    path.write_bytes(original.json)

    again = _rerun(path)
    assert again.json == original.json
    assert again.normal == original.normal
    assert (again.normal is None) is (not normals)
    assert again.depth == original.depth
    assert (again.depth is None) is (not depth)
    assert again.lit == original.lit
    assert bool(original.lit) is (previews and light.position is not None)
    document = json.loads(original.json)
    assert document["settings"]["previews"] is previews
    assert document["settings"]["normals"] is normals
    assert document["settings"]["depth"] is depth
    assert document["maps"] == {
        "normal": {"file": "hero.normal.png"} if normals else None,
        "depth": {"file": "hero.depth.png"} if depth else None,
    }


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (("--once", "attack"), ("--once", "walk")),
        ((), ("--once", "walk")),
        (("--clip", "walk", "--clip", "attack"), ("--clip", "attack")),
        (("--once", "attack"), ("--clip", "walk", "--clip", "attack")),
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
    argv = [
        "--settings-from",
        str(path),
        "--no-user-config",
        str(model),
        str(tmp_path / "out.png"),
    ]
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
    defaults = Path(cli.layered.__file__).with_name("defaults.yaml")
    assert [Path(args[0]) for args in opened] == [defaults, path]
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
