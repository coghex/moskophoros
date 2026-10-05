import math
import os
from pathlib import Path

import pytest

from moskophoros import cli

POSITIONALS = ["in.glb", "out.png"]
USAGE_LINE = "usage: moskophoros [options] <infile.glb> <outfile.png>"


def parse(*options):
    return cli.parse_args([*options, *POSITIONALS])


def usage_error(capsys, argv):
    """Parse `argv` expecting a usage error; return its error message."""
    with pytest.raises(cli.UsageError) as raised:
        cli.parse_args(argv)
    assert raised.value.code == 2
    out, err = capsys.readouterr()
    assert out == ""
    usage, error, *rest = err.splitlines()
    assert usage == USAGE_LINE
    assert rest == []
    assert error == f"moskophoros: error: {raised.value.message}"
    return raised.value.message


# Defaults and presets


def test_defaults():
    options = cli.parse_args(POSITIONALS)
    assert options == cli.Options(
        infile=Path("in.glb"),
        outfile=Path("out.png"),
        view="iso",
        pitch=30.0,
        directions=8,
        start_angle=0.0,
        model_yaw=0.0,
        clip=None,
        once=(),
        fps=12.0,
        ppm=None,
        cell=None,
        ground=(0.0, 0.0, 0.0),
        ground_px=None,
        root_motion="error",
        supersample=8,
        reduce="plain",
        settings_from=None,
        no_preview=False,
        work_dir=None,
        blender=None,
        any_blender=False,
        explicit=frozenset(),
    )


@pytest.mark.parametrize(
    ("view", "pitch", "directions", "start_angle"),
    [
        ("topdown", 90.0, 8, 0.0),
        ("side", 0.0, 2, 90.0),
        ("iso", 30.0, 8, 0.0),
        ("iso-true", math.degrees(math.atan(1 / math.sqrt(2))), 8, 0.0),
    ],
)
def test_presets_resolve(view, pitch, directions, start_angle):
    options = parse("--view", view)
    assert (options.view, options.pitch, options.directions, options.start_angle) == (
        view,
        pitch,
        directions,
        start_angle,
    )


def test_iso_true_pitch():
    assert parse("--view", "iso-true").pitch == pytest.approx(35.264389682754654)


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        (["--pitch", "45"], (45.0, 2, 90.0)),
        (["--directions", "4"], (0.0, 4, 90.0)),
        (["--start-angle", "270"], (0.0, 2, 270.0)),
        # Even a value equal to the preset's makes the view custom.
        (["--pitch", "0"], (0.0, 2, 90.0)),
    ],
)
def test_an_explicit_override_makes_the_view_custom(override, expected):
    options = parse("--view", "side", *override)
    assert options.view == "custom"
    assert (options.pitch, options.directions, options.start_angle) == expected


def test_an_override_without_view_starts_from_the_default_preset():
    options = parse("--directions", "16")
    assert (options.view, options.pitch, options.directions, options.start_angle) == (
        "custom",
        30.0,
        16,
        0.0,
    )


def test_model_yaw_does_not_make_the_view_custom():
    assert parse("--model-yaw", "90").view == "iso"


# Explicit options


def test_explicit_options_are_recorded_apart_from_defaults_and_presets():
    options = parse(
        "--view",
        "topdown",
        "--start-angle",
        "45",
        "--fps",
        "12",
        "--clip",
        "walk",
        "--clip",
        "idle",
        "--no-preview",
    )
    assert options.explicit == frozenset(
        {"view", "start_angle", "fps", "clip", "no_preview"}
    )
    # Preset-derived and default values are not explicit, even when an
    # explicit value equals the default.
    assert (options.pitch, options.directions) == (90.0, 8)
    assert options.fps == 12.0
    assert options.supersample == 8


def test_every_option_can_be_recorded_as_explicit(tmp_path):
    options = cli.parse_args(
        [
            *["--view", "side", "--pitch", "10", "--directions", "4"],
            *["--start-angle", "5", "--model-yaw", "-90"],
            *["--clip", "a", "--once", "a", "--fps", "24", "--ppm", "64"],
            *["--cell", "32x48", "--ground", "1,2,3", "--ground-px", "16,40"],
            *["--root-motion", "keep", "--supersample", "4", "--reduce", "plain"],
            *["--settings-from", "old.json", "--no-preview"],
            *["--work-dir", "work", "--blender", "/opt/blender", "--any-blender"],
            *POSITIONALS,
        ]
    )
    fields = {name for name in cli.Options.__dataclass_fields__}
    assert options.explicit == fields - {"infile", "outfile", "explicit"}
    assert options == cli.Options(
        infile=Path("in.glb"),
        outfile=Path("out.png"),
        view="custom",
        pitch=10.0,
        directions=4,
        start_angle=5.0,
        model_yaw=-90.0,
        clip=("a",),
        once=("a",),
        fps=24.0,
        ppm=64.0,
        cell=(32, 48),
        ground=(1.0, 2.0, 3.0),
        ground_px=(16, 40),
        root_motion="keep",
        supersample=4,
        reduce="plain",
        settings_from=Path("old.json"),
        no_preview=True,
        work_dir=Path("work"),
        blender=Path("/opt/blender"),
        any_blender=True,
        explicit=options.explicit,
    )


# Ranges


@pytest.mark.parametrize(
    ("option", "value", "field", "expected"),
    [
        ("--pitch", "0", "pitch", 0.0),
        ("--pitch", "90", "pitch", 90.0),
        ("--directions", "1", "directions", 1),
        ("--directions", "64", "directions", 64),
        ("--fps", "0.001", "fps", 0.001),
        ("--ppm", "0.001", "ppm", 0.001),
        ("--cell", "1x1", "cell", (1, 1)),
        ("--cell", "4096x4096", "cell", (4096, 4096)),
        ("--ground-px", "0,0", "ground_px", (0, 0)),
        ("--ground-px", "3.0,7", "ground_px", (3, 7)),
        ("--ground-px", "9007199254740993,1e3", "ground_px", (9007199254740993, 1000)),
        ("--supersample", "1", "supersample", 1),
        ("--supersample", "16", "supersample", 16),
        ("--start-angle", "-720.5", "start_angle", -720.5),
        ("--start-angle", "1e5", "start_angle", 1e5),
        ("--model-yaw", "-1e-3", "model_yaw", -0.001),
        ("--model-yaw", "450", "model_yaw", 450.0),
        ("--ground", "-1.5,0,2e-1", "ground", (-1.5, 0.0, 0.2)),
        ("--root-motion", "keep", "root_motion", "keep"),
        ("--reduce", "plain", "reduce", "plain"),
        ("--reduce", "mode", "reduce", "mode"),
    ],
)
def test_range_boundaries_are_accepted(option, value, field, expected):
    assert getattr(parse(option, value), field) == expected


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--pitch", "-0.001", "must be from 0 to 90"),
        ("--pitch", "90.001", "must be from 0 to 90"),
        ("--directions", "0", "must be from 1 to 64"),
        ("--directions", "65", "must be from 1 to 64"),
        ("--directions", "8.5", "expected an integer"),
        ("--fps", "0", "must be greater than 0"),
        ("--fps", "-1", "must be greater than 0"),
        ("--ppm", "0", "must be greater than 0"),
        ("--cell", "0x32", "expected WxH"),
        ("--cell", "32x4097", "expected WxH"),
        ("--cell", "32", "expected WxH"),
        ("--cell", "32x32x32", "expected WxH"),
        ("--cell", "32X32", "expected WxH"),
        ("--supersample", "0", "must be from 1 to 16"),
        ("--supersample", "17", "must be from 1 to 16"),
        ("--ground", "1,2", "expected X,Y,Z"),
        ("--ground", "1,2,x", "expected X,Y,Z"),
        ("--start-angle", "north", "expected a number"),
        ("--view", "front", "invalid choice"),
        ("--root-motion", "ignore", "invalid choice"),
        ("--reduce", "median", "invalid choice"),
        ("--reduce", "Mode", "invalid choice"),
        ("--reduce", "Plain", "invalid choice"),
        ("--reduce", "", "invalid choice"),
    ],
)
def test_the_nearest_invalid_value_is_rejected(capsys, option, value, message):
    error = usage_error(capsys, [option, value, *POSITIONALS])
    assert error.startswith(f"argument {option}: ")
    assert message in error
    assert repr(value) in error


@pytest.mark.parametrize("value", ["out.PNG", "out.png.json", "out", "out.png/"])
def test_the_output_must_end_in_png_exactly_as_written(capsys, value):
    error = usage_error(capsys, ["in.glb", value])
    assert error == f"argument <outfile.png>: must end in .png, got {value!r}"


def test_the_input_has_no_suffix_requirement():
    assert cli.parse_args(["model.GLTF-binary", "out.png"]).infile == Path(
        "model.GLTF-binary"
    )


@pytest.mark.parametrize("argv", [["", "out.png"], ["--work-dir", "", *POSITIONALS]])
def test_an_empty_path_is_rejected(capsys, argv):
    assert "expected a path, got ''" in usage_error(capsys, argv)


def test_options_and_positionals_may_interleave():
    options = cli.parse_args(["in.glb", "--view", "side", "out.png", "--fps", "8"])
    assert (options.infile, options.outfile, options.view, options.fps) == (
        Path("in.glb"),
        Path("out.png"),
        "side",
        8.0,
    )


def test_values_starting_with_a_dash():
    options = cli.parse_args(
        ["--ground", "-1,-2,-3", "--clip", "-walk", "--", "-in.glb", "out.png"]
    )
    assert options.ground == (-1.0, -2.0, -3.0)
    assert options.clip == ("-walk",)
    assert options.infile == Path("-in.glb")
    assert cli.parse_args(["--start-angle=-45", *POSITIONALS]).start_angle == -45.0


# Option validation rules (design §Option validation)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "NaN", "Infinity"])
@pytest.mark.parametrize(
    "option",
    [
        "--pitch",
        "--directions",
        "--start-angle",
        "--model-yaw",
        "--fps",
        "--ppm",
        "--supersample",
    ],
)
def test_numbers_must_be_finite(capsys, option, value):
    error = usage_error(capsys, [option, value, *POSITIONALS])
    assert error == f"argument {option}: expected a finite number, got {value!r}"


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--cell", "nanx32"),
        ("--cell", "32xinf"),
        ("--ground", "0,nan,0"),
        ("--ground", "inf,0,0"),
        ("--ground-px", "inf,0"),
        ("--ground-px", "0,nan"),
    ],
)
def test_composite_numbers_must_be_finite(capsys, option, value):
    assert usage_error(capsys, [option, value, *POSITIONALS]).startswith(
        f"argument {option}: "
    )


@pytest.mark.parametrize(
    "value",
    [
        "-1,0",
        "0,-1",
        "1.5,0",
        "0,0.5",
        "0.99999999999999999,0",
        "0,1.00000000000000001",
        "1e999999999,0",
        "x,0",
        "1",
        "1,2,3",
    ],
)
def test_ground_px_takes_two_whole_numbers_0_or_greater(capsys, value):
    error = usage_error(capsys, ["--ground-px", value, *POSITIONALS])
    assert error == (
        "argument --ground-px: expected X,Y, two whole numbers 0 or greater, "
        f"got {value!r}"
    )


def test_ground_px_outside_the_cell_is_not_a_usage_error():
    assert parse("--cell", "16x16", "--ground-px", "100,100").ground_px == (100, 100)


@pytest.mark.parametrize("option", ["--clip", "--once"])
def test_a_clip_named_twice_is_rejected(capsys, option):
    argv = ["--clip", "walk", "--clip", "run"] if option == "--once" else []
    argv += [option, "walk", option, "walk", *POSITIONALS]
    error = usage_error(capsys, argv)
    assert error == f"argument {option}: 'walk' named more than once"


def test_clips_keep_the_order_given():
    options = parse("--clip", "run", "--clip", "idle", "--clip", "walk")
    assert options.clip == ("run", "idle", "walk")


def test_once_must_name_an_explicitly_selected_clip(capsys):
    error = usage_error(
        capsys, ["--once", "jump", "--clip", "walk", "--clip", "run", *POSITIONALS]
    )
    assert error == "argument --once: 'jump' is not among the --clip names"


def test_once_without_clip_is_left_to_the_input_check():
    options = parse("--once", "jump", "--once", "fall")
    assert (options.clip, options.once) == (None, ("jump", "fall"))


def test_once_may_precede_its_clip():
    options = parse("--once", "jump", "--clip", "walk", "--clip", "jump")
    assert (options.clip, options.once) == (("walk", "jump"), ("jump",))


@pytest.mark.parametrize(
    ("option", "first", "second"),
    [
        ("--view", "iso", "side"),
        ("--pitch", "30", "30"),
        ("--directions", "8", "4"),
        ("--start-angle", "0", "90"),
        ("--model-yaw", "0", "90"),
        ("--fps", "12", "24"),
        ("--ppm", "32", "64"),
        ("--cell", "8x8", "16x16"),
        ("--ground", "0,0,0", "1,1,1"),
        ("--ground-px", "0,0", "1,1"),
        ("--root-motion", "error", "keep"),
        ("--supersample", "8", "4"),
        ("--reduce", "plain", "plain"),
        ("--reduce", "plain", "mode"),
        ("--settings-from", "a.json", "b.json"),
        ("--work-dir", "a", "b"),
        ("--blender", "a", "b"),
        ("--no-preview", None, None),
        ("--any-blender", None, None),
    ],
)
def test_a_single_value_option_given_twice_is_rejected(capsys, option, first, second):
    once = [option] if first is None else [option, first]
    again = [option] if second is None else [option, second]
    error = usage_error(capsys, [*once, *again, *POSITIONALS])
    if first is None:
        assert error == f"argument {option}: given more than once"
    else:
        assert error == (
            f"argument {option}: given more than once: {first!r}, {second!r}"
        )


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["--pitch=10", "--pitch", "20"],
            "argument --pitch: given more than once: '10', '20'",
        ),
        (
            ["--ground", "-1,0,0", "--ground=1,0,0"],
            "argument --ground: given more than once: '-1,0,0', '1,0,0'",
        ),
        # A repeat is reported even when an earlier value is invalid.
        (
            ["--pitch", "91", "--pitch", "20"],
            "argument --pitch: given more than once: '91', '20'",
        ),
    ],
)
def test_a_repeat_names_the_values_given(capsys, argv, message):
    assert usage_error(capsys, [*argv, *POSITIONALS]) == message


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--frames", "8", *POSITIONALS], "unrecognized option: --frames"),
        (["--dir", "4", *POSITIONALS], "unrecognized option: --dir"),
        (["--frames=8", *POSITIONALS], "unrecognized option: --frames=8"),
        (["-v", *POSITIONALS], "unrecognized option: -v"),
        (["-in.glb", "out.png"], "unrecognized option: -in.glb"),
        ([*POSITIONALS, "--pitch"], "argument --pitch: expected one argument"),
        (
            ["--clip", "--view", "side", *POSITIONALS],
            "argument --clip: expected one argument",
        ),
        ([*POSITIONALS, "extra.png"], "unrecognized arguments: extra.png"),
        (["in.glb"], "the following arguments are required: <outfile.png>"),
        (
            [],
            "the following arguments are required: <infile.glb>, <outfile.png>",
        ),
    ],
)
def test_unknown_options_and_wrong_positional_counts_are_rejected(
    capsys, argv, message
):
    assert message in usage_error(capsys, argv)


# Help


DESIGN_OPTIONS = {
    "--view NAME": "iso",
    "--pitch DEG": "from the view",
    "--directions N": "from the view",
    "--start-angle DEG": "from the view",
    "--model-yaw DEG": "0",
    "--clip NAME": "every clip",
    "--once NAME": "none",
    "--fps N": "12",
    "--ppm N": "auto",
    "--cell WxH": "auto",
    "--ground X,Y,Z": "0,0,0",
    "--ground-px X,Y": "auto",
    "--root-motion MODE": "error",
    "--supersample N": "8",
    "--reduce NAME": "plain",
    "--settings-from FILE": "none",
    "--no-preview": "off",
    "--work-dir DIR": "a deleted temporary directory",
    "--blender PATH": "discovered",
    "--any-blender": "off",
}


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_names_every_option_with_its_default(capsys, flag):
    with pytest.raises(SystemExit) as raised:
        cli.parse_args([flag])
    assert raised.value.code == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert out.startswith(USAGE_LINE)
    text = " ".join(out.split())
    entries = sorted((text.index(f" {entry} "), entry) for entry in DESIGN_OPTIONS)
    ends = [start for start, _ in entries[1:]] + [len(text)]
    for (start, entry), end in zip(entries, ends, strict=True):
        assert f"(default: {DESIGN_OPTIONS[entry]})" in text[start:end], entry


# No effects


def snapshot(root):
    return sorted(
        (str(path.relative_to(root)), path.stat().st_mtime_ns, path.is_dir())
        for path in [root, *root.rglob("*")]
    )


def test_a_valid_parse_leaves_the_filesystem_untouched(tmp_path, capsys):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "left-over.txt").write_text("kept\n")
    before = snapshot(tmp_path)
    infile = tmp_path / "missing.glb"
    settings = tmp_path / "missing.json"
    outfile = tmp_path / "out" / "sheet.png"

    options = cli.parse_args(
        [
            *["--settings-from", str(settings), "--work-dir", str(work_dir)],
            *["--blender", str(tmp_path / "no-blender")],
            str(infile),
            str(outfile),
        ]
    )

    assert (options.infile, options.settings_from, options.work_dir) == (
        infile,
        settings,
        work_dir,
    )
    assert snapshot(tmp_path) == before
    assert not os.path.lexists(infile)
    assert capsys.readouterr() == ("", "")
