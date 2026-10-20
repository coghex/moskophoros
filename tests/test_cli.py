import json
import math
import os
from pathlib import Path

import pytest

from moskophoros import cli
from moskophoros.views import normalise, pitch_direction

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
        direction=pitch_direction(30.0),
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
        edges="hard",
        settings_from=None,
        previews=True,
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
    assert (
        options.view,
        options.direction,
        options.directions,
        options.start_angle,
    ) == (view, pitch_direction(pitch), directions, start_angle)


def test_iso_true_pitch():
    _, y, z = parse("--view", "iso-true").direction
    assert math.degrees(math.atan2(-y, -z)) == pytest.approx(35.264389682754654)


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        (["--pitch", "45"], (pitch_direction(45.0), 2, 90.0)),
        (["--directions", "4"], (pitch_direction(0.0), 4, 90.0)),
        (["--start-angle", "270"], (pitch_direction(0.0), 2, 270.0)),
        # Even a value equal to the preset's makes the view custom.
        (["--pitch", "0"], (pitch_direction(0.0), 2, 90.0)),
        (["--camera-direction", "0,0,-1"], ((0.0, 0.0, -1.0), 2, 90.0)),
        (["--camera-direction", "1,0,-1"], (normalise((1, 0, -1)), 2, 90.0)),
    ],
)
def test_an_explicit_override_makes_the_view_custom(override, expected):
    options = parse("--view", "side", *override)
    assert options.view == "custom"
    assert (options.direction, options.directions, options.start_angle) == expected


def test_the_roll_and_position_do_not_make_the_view_custom():
    options = parse("--camera-roll", "0.5", "--camera-position", "1,2,3")
    assert (options.view, options.roll, options.camera_position) == (
        "iso",
        0.5,
        (1.0, 2.0, 3.0),
    )


def test_an_override_without_view_starts_from_the_default_preset():
    options = parse("--directions", "16")
    assert (
        options.view,
        options.direction,
        options.directions,
        options.start_angle,
    ) == ("custom", pitch_direction(30.0), 16, 0.0)


@pytest.mark.parametrize(
    "options",
    [
        ["--pitch", "30", "--camera-direction", "0,-1,0"],
        ["--camera-direction", "0,-1,0", "--pitch", "30"],
        ["--view", "iso", "--camera-direction", "0,0,-1", "--pitch", "0"],
    ],
)
def test_pitch_and_a_camera_direction_cannot_be_given_together(capsys, options):
    assert usage_error(capsys, [*options, *POSITIONALS]) == (
        "--pitch and --camera-direction cannot be given together: both set the "
        "camera's direction"
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
        {"view", "start_angle", "fps", "clip", "previews"}
    )
    # Preset-derived and default values are not explicit, even when an
    # explicit value equals the default.
    assert (options.direction, options.directions) == (pitch_direction(90.0), 8)
    assert options.fps == 12.0
    assert options.supersample == 8


def test_every_option_can_be_recorded_as_explicit(tmp_path):
    options = cli.parse_args(
        [
            *["--view", "side", "--camera-direction", "0,-0.6,-0.8"],
            *["--projection", "perspective"],
            *["--camera-roll", "-0.25", "--camera-position", "0,1,2"],
            *["--directions", "4"],
            *["--start-angle", "5", "--model-yaw", "-90"],
            *["--clip", "a", "--once", "a", "--fps", "24", "--ppm", "64"],
            *["--cell", "32x48", "--ground", "1,2,3", "--ground-px", "16,40"],
            *["--root-motion", "keep", "--supersample", "4", "--reduce", "plain"],
            *["--edges", "soft"],
            *["--ao-distance", "1.2", "--ao-samples", "128"],
            *["--occlusion-weight", "0.5", "--convexity-weight", "0"],
            *["--shade-range", "120,188", "--frames", "8"],
            *["--settings-from", "old.json", "--no-preview", "--no-normals"],
            "--depth",
            *["--light", "-20,30,40", "--light-intensity", "2"],
            *["--light-ambient", "0.5"],
            *["--ramp-step", "0.09", "--ramp-hue-shift", "-35", "--ramp-fade", "0.6"],
            *["--config", "a.yaml", "--project", "look"],
            *["--work-dir", "work", "--blender", "/opt/blender", "--any-blender"],
            *POSITIONALS,
        ]
    )
    fields = {name for name in cli.Options.__dataclass_fields__}
    assert options.explicit == fields - {
        "infile",
        "outfile",
        "explicit",
        "palette_file",
        "palette",
        "no_palette",
        "materials_file",
        "materials",
        "no_materials",
        "origins",
        "clip_frames",
        # It cannot accompany --config; recorded as explicit below.
        "no_user_config",
        # The preset --view names, recorded as `view`.
        "preset",
    }
    assert options == cli.Options(
        infile=Path("in.glb"),
        outfile=Path("out.png"),
        view="custom",
        direction=(0.0, -0.6, -0.8),
        projection="perspective",
        roll=-0.25,
        camera_position=(0.0, 1.0, 2.0),
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
        edges="soft",
        settings_from=Path("old.json"),
        previews=False,
        work_dir=Path("work"),
        blender=Path("/opt/blender"),
        any_blender=True,
        explicit=options.explicit,
        config=Path("a.yaml"),
        project="look",
        ao_distance=1.2,
        ao_samples=128,
        occlusion_weight=0.5,
        convexity_weight=0.0,
        shade_range=(120, 188),
        frames=8,
        normals=False,
        depth=True,
        light=(-20.0, 30.0, 40.0),
        light_intensity=2.0,
        light_ambient=0.5,
        ramp_step=0.09,
        ramp_hue_shift=-35.0,
        ramp_fade=0.6,
        preset="side",
    )


def test_no_user_config_is_recorded_as_explicit():
    options = parse("--no-user-config")
    assert (options.explicit, options.no_user_config) == ({"no_user_config"}, True)


# Ranges


@pytest.mark.parametrize(
    ("option", "value", "field", "expected"),
    [
        ("--pitch", "0", "direction", (0.0, 0.0, -1.0)),
        ("--pitch", "90", "direction", (0.0, -1.0, 0.0)),
        ("--camera-roll", "-1", "roll", -1.0),
        ("--camera-roll", "1", "roll", 1.0),
        ("--camera-direction", "-1,1,-1", "direction", normalise((-1, 1, -1))),
        (
            "--camera-direction",
            "1e-300,1e-300,0",
            "direction",
            normalise((1e-300, 1e-300, 0.0)),
        ),
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
        ("--projection", "orthographic", "projection", "orthographic"),
        ("--projection", "perspective", "projection", "perspective"),
        ("--edges", "hard", "edges", "hard"),
        ("--edges", "soft", "edges", "soft"),
        ("--ao-distance", "1e-9", "ao_distance", 1e-9),
        ("--ao-distance", "1.2", "ao_distance", 1.2),
        ("--ao-samples", "1", "ao_samples", 1),
        ("--ao-samples", "128", "ao_samples", 128),
        ("--occlusion-weight", "0", "occlusion_weight", 0.0),
        ("--occlusion-weight", "2.5", "occlusion_weight", 2.5),
        ("--convexity-weight", "0", "convexity_weight", 0.0),
        ("--convexity-weight", "1e3", "convexity_weight", 1000.0),
        ("--shade-range", "0,1", "shade_range", (0, 1)),
        ("--shade-range", "254,255", "shade_range", (254, 255)),
        ("--shade-range", "120,188", "shade_range", (120, 188)),
        ("--frames", "1", "frames", 1),
        ("--frames", "120", "frames", 120),
        ("--frames", "08", "frames", 8),
        ("--frames", "auto", "frames", "auto"),
    ],
)
def test_range_boundaries_are_accepted(option, value, field, expected):
    assert getattr(parse(option, value), field) == expected


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--pitch", "-0.001", "must be from 0 to 90"),
        ("--pitch", "90.001", "must be from 0 to 90"),
        ("--camera-roll", "-1.001", "must be from -1 to 1"),
        ("--camera-roll", "1.5", "must be from -1 to 1"),
        ("--camera-roll", "nan", "expected a finite number"),
        ("--camera-direction", "0,0,0", "points nowhere"),
        ("--camera-direction", "0,0,-0", "points nowhere"),
        ("--camera-direction", "0,-1.5,0", "each from -1 to 1"),
        ("--camera-direction", "0,-1", "expected X,Y,Z"),
        ("--camera-direction", "0,inf,-1", "expected X,Y,Z"),
        ("--camera-direction", "0,nan,-1", "expected X,Y,Z"),
        ("--camera-position", "0,1", "expected X,Y,Z"),
        ("--camera-position", "0,1,inf", "expected X,Y,Z"),
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
        ("--projection", "Perspective", "invalid choice"),
        ("--projection", "fisheye", "invalid choice"),
        ("--edges", "fuzzy", "invalid choice"),
        ("--edges", "Hard", "invalid choice"),
        ("--edges", "", "invalid choice"),
        ("--ao-distance", "0", "must be greater than 0"),
        ("--ao-distance", "nan", "expected a finite number"),
        ("--ao-samples", "0", "must be from 1 to 128, the most Blender's ambient"),
        ("--ao-samples", "129", "must be from 1 to 128, the most Blender's ambient"),
        ("--ao-samples", "64.0", "expected an integer"),
        ("--occlusion-weight", "-0.001", "must be 0 or greater"),
        ("--convexity-weight", "-1", "must be 0 or greater"),
        ("--convexity-weight", "inf", "expected a finite number"),
        ("--shade-range", "191,84", "expected LO,HI"),
        ("--shade-range", "84,84", "expected LO,HI"),
        ("--shade-range", "-1,84", "expected LO,HI"),
        ("--shade-range", "84,256", "expected LO,HI"),
        ("--shade-range", "84", "expected LO,HI"),
        ("--shade-range", "84,120,191", "expected LO,HI"),
        ("--shade-range", "84.0,191", "expected LO,HI"),
        ("--frames", "0", "expected a whole number 1 or more, or auto"),
        ("--frames", "-1", "expected a whole number 1 or more, or auto"),
        ("--frames", "8.0", "expected a whole number 1 or more, or auto"),
        ("--frames", "+8", "expected a whole number 1 or more, or auto"),
        ("--frames", "8_0", "expected a whole number 1 or more, or auto"),
        ("--frames", "Auto", "expected a whole number 1 or more, or auto"),
        ("--frames", "", "expected a whole number 1 or more, or auto"),
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
        "--camera-roll",
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
        f"or auto, got {value!r}"
    )


@pytest.mark.parametrize(
    ("option", "field"), [("--ppm", "ppm"), ("--ground-px", "ground_px")]
)
def test_auto_is_an_explicit_automatic_value(option, field):
    """`--ppm auto` and `--ground-px auto` fit automatically, as the
    defaults do, but are given: they drop a reused or configured value
    (projects and camera design D-16)."""
    options = parse(option, "auto")
    assert getattr(options, field) is None
    assert options.explicit == {field}


@pytest.mark.parametrize("value", ["Auto", "AUTO", "auto,0", ""])
def test_ppm_takes_auto_only_as_written(capsys, value):
    assert usage_error(capsys, ["--ppm", value, *POSITIONALS]).startswith(
        "argument --ppm: expected a number"
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
        ("--edges", "hard", "soft"),
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
        (["--frame", "8", *POSITIONALS], "unrecognized option: --frame"),
        (["--dir", "4", *POSITIONALS], "unrecognized option: --dir"),
        (["--frame=8", *POSITIONALS], "unrecognized option: --frame=8"),
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
    "--projection NAME": "orthographic",
    "--camera-direction X,Y,Z": "from the view",
    "--camera-roll R": "0",
    "--camera-position X,Y,Z": "none",
    "--directions N": "from the view",
    "--start-angle DEG": "from the view",
    "--model-yaw DEG": "0",
    "--clip NAME": "every clip",
    "--once NAME": "none",
    "--fps N": "12",
    "--ppm N": "auto",
    "--cell WxH": "reused by --settings-from, else fitted to the model with --ppm, "
    "else 64x64",
    "--config FILE": "the user file",
    "--no-user-config": "off",
    "--project NAME": "none",
    "--preview": "on",
    "--frames N": "auto",
    "--ground X,Y,Z": "0,0,0",
    "--ground-px X,Y": "auto",
    "--root-motion MODE": "error",
    "--supersample N": "8",
    "--reduce NAME": "plain",
    "--edges RULE": "hard",
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
    help_texts = {}
    for (start, entry), end in zip(entries, ends, strict=True):
        help_texts[entry] = text[start:end]
        assert f"(default: {DESIGN_OPTIONS[entry]})" in text[start:end], entry
    assert (
        "unless --ppm is given or reused, the model is scaled to fit the cell"
        in help_texts["--cell WxH"]
    )


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


# The perspective camera (projects and camera design D-3, D-10, D-16)


@pytest.fixture
def setup(tmp_path):
    from test_command import Setup

    return Setup(tmp_path)


# The iso camera, from 1.5 m above and 2.5 m in front of the ground point.
PERSPECTIVE = ["--projection", "perspective", "--camera-position", "0,1.5,2.5"]


def run(capsys, argv):
    status = cli.run(argv)
    out, err = capsys.readouterr()
    assert out == ""
    return status, err


def test_the_projection_is_orthographic_by_default():
    assert parse().projection == "orthographic"
    options = parse("--projection", "perspective")
    assert (options.projection, options.view) == ("perspective", "iso")
    assert "projection" in options.explicit


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            ["--projection", "perspective"],
            "the perspective camera needs a position: give --camera-position X,Y,Z "
            "or camera.position, in meters from the ground point",
        ),
        (
            ["--projection", "perspective", "--camera-position", "0,-1.5,-2.5"],
            "the perspective camera at (0.0, -1.5, -2.5) from the ground point, "
            "looking along (0.0, -0.49999999999999994, -0.8660254037844387), has "
            "the ground point -2.915063509461097 m in front of it: the ground "
            "point must be in front of the camera",
        ),
        (
            [
                *["--projection", "perspective", "--camera-direction", "0,0,-1"],
                *["--camera-position", "1,0.5,0"],
            ],
            "the perspective camera at (1.0, 0.5, 0.0) from the ground point, "
            "looking along (0.0, 0.0, -1.0), has the ground point 0.0 m in front "
            "of it: the ground point must be in front of the camera",
        ),
    ],
    ids=["no position", "behind", "beside"],
)
def test_a_perspective_camera_needs_the_ground_point_in_front(
    setup, capsys, monkeypatch, options, message
):
    from test_materials_command import forbid_blender

    earlier = setup.listing()
    forbid_blender(monkeypatch)
    status, err = run(capsys, setup.argv(*options))
    assert status == 2
    usage, error = err.splitlines()
    assert usage == USAGE_LINE
    assert error == f"moskophoros: error: {message}"
    assert setup.listing() == earlier


def test_a_settings_file_s_perspective_camera_is_checked_too(setup, capsys, tmp_path):
    from test_materials_command import forbid_blender

    project = tmp_path / "config" / "moskophoros" / "projects" / "look.yaml"
    project.parent.mkdir(parents=True)
    project.write_text("camera:\n  projection: perspective\n")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        forbid_blender(patch)
        status, err = run(capsys, setup.argv("--project", "look"))
    assert status == 2
    assert "the perspective camera needs a position" in err
    # The position in the file, or on the command line, completes it.
    project.write_text(
        "camera:\n  projection: perspective\n  position: [0, 1.5, 2.5]\n"
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        assert run(capsys, setup.argv("--project", "look"))[0] == 0


def test_a_perspective_run_clips_from_the_measured_depths(setup, capsys, tmp_path):
    work = tmp_path / "work"
    setup.configure(depth=[1.25, 4.5])
    status, err = run(capsys, setup.argv(*PERSPECTIVE, "--work-dir", str(work)))
    assert (status, err) == (0, "")
    measure = json.loads((work / "measure" / "job.json").read_text())
    render = json.loads((work / "render" / "job.json").read_text())
    assert measure["clipping"] is None
    # Half the nearest depth, and twice the farthest plus 1 m.
    assert render["clipping"] == {
        "near_m": 0.625,
        "far_m": 10.0,
        "depth_m": [1.25, 4.5],
    }
    for job in (measure, render):
        assert job["schema"] == "moskophoros.capture-job/3"
        assert job["settings"]["camera"] == {
            "projection": "perspective",
            "direction": list(pitch_direction(30.0)),
            "roll": 0.0,
            "position": [0.0, 1.5, 2.5],
        }
    recorded = json.loads(setup.json.read_text())["settings"]["camera"]
    assert recorded == measure["settings"]["camera"]


def test_a_vertex_too_near_the_camera_is_exit_4_with_nothing_published(setup, capsys):
    from test_command import earlier_outputs

    setup.configure(near=[1, 2])
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    status, err = run(capsys, setup.argv(*PERSPECTIVE))
    assert status == 4
    assert err.splitlines() == [
        f"moskophoros: error: {setup.model}: a vertex is too near the perspective "
        "camera to project, 0.0001 m from it or nearer, or behind it; move the "
        "camera's position farther from the subject:",
        "  clip 'walk', direction 0, time 0.25 s: nearest vertex depth -0.2 m",
        "  clip 'walk', direction 0, time 0.5 s: nearest vertex depth -0.2 m",
    ]
    assert setup.listing() == earlier
    assert [call["mode"] for call in setup.calls()] == ["measure"]


@pytest.mark.parametrize(
    ("options", "changes"),
    [
        ([], {"bounds_m": None}),
        (PERSPECTIVE, {"bounds_m": None, "depth_m": [0.5, 3.0]}),
        (PERSPECTIVE, {"depth_m": "missing"}),
        (PERSPECTIVE, {"depth_m": [math.nan, 3.0]}),
        (PERSPECTIVE, {"depth_m": [2.0, math.inf]}),
        (PERSPECTIVE, {"depth_m": [3.0, 2.0]}),
        (
            PERSPECTIVE,
            {"bounds_m": {"L": 0.1, "R": 0, "U": 0, "D": 0}, "depth_m": [0, 1]},
        ),
    ],
    ids=[
        "orthographic null bounds",
        "null bounds with a far depth",
        "no depths",
        "a non-finite depth",
        "an infinite depth",
        "reversed depths",
        "bounds with a near depth",
    ],
)
def test_a_malformed_perspective_measurement_stays_exit_5(
    setup, capsys, request, options, changes
):
    from test_command import earlier_outputs

    setup.configure(frame_changes={"0": changes})
    earlier = earlier_outputs(setup, "hero.png", "hero.json")
    status, err = run(capsys, setup.argv(*options))
    assert status == 5
    # A non-finite number is no JSON number, refused as the result is read.
    where = "non-finite" if "finite" in request.node.callspec.id else "frame 0"
    assert err.startswith(f"moskophoros: error: the measure result is invalid: {where}")
    assert setup.listing() == earlier
