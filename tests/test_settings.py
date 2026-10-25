"""Settings files and their layers, without the command (settings design D-2,
D-5, D-8, D-17, D-22 and D-30)."""

import sys
import tomllib
from importlib import resources
from pathlib import Path

import pytest

from moskophoros import settings
from moskophoros.settings import SettingsError, merge, read_bytes, read_file

ROOT = Path(__file__).resolve().parents[1]


def layer(text, directory="/settings"):
    return read_bytes(text.encode("utf-8"), source="s.yaml", directory=directory)


def refused(data):
    with pytest.raises(SettingsError) as raised:
        read_bytes(
            data if isinstance(data, bytes) else data.encode("utf-8"),
            source="s.yaml",
            directory="/settings",
        )
    assert raised.value.source == "s.yaml"
    assert str(raised.value) == f"s.yaml: {raised.value.problem}"
    return raised.value.problem


# The schema table and the shipped defaults


def test_the_schema_holds_every_setting_in_order():
    assert list(settings.SCHEMA) == [
        "view",
        "pitch",
        "camera.projection",
        "camera.direction",
        "camera.roll",
        "camera.position",
        "directions",
        "start_angle",
        "model_yaw",
        "ppm",
        "ground",
        "ground_px",
        "supersample",
        "reduce",
        "root_motion",
        "blender",
        "any_blender",
        "cell",
        "fps",
        "frames",
        "palette",
        "materials",
        "edges",
        "previews",
        "normals",
        "depth",
        "light.position",
        "light.intensity",
        "light.ambient",
        "shade.ao_distance_m",
        "shade.ao_samples",
        "shade.occlusion_weight",
        "shade.convexity_weight",
        "shade.range",
        "shade.mode",
        "shade.ambient_form",
        "shade.key.direction",
        "shade.key.strength",
        "shade.sky.strength",
        "shade.ground.strength",
        "shade.sky_ground_frame",
        "shade.brightness.floor",
        "shade.brightness.ceiling",
        "shade.snap",
        "shade.dither.pattern",
        "shade.dither.strength",
        "ramp.lightness_step",
        "ramp.hue_shift_deg",
        "ramp.chroma_fade",
        "stored_directions",
        "direction_names",
        "mirrors",
        "export.formats",
        "export.frame_path",
        "export.atlas_path",
        "export.sheet_path",
        "export.atlas_padding",
    ]
    assert settings.GROUPS == {"camera", "shade", "light", "ramp", "export"}
    for name, setting in settings.SCHEMA.items():
        assert setting.kind, name
        assert callable(setting.check), name


def test_the_design_s_example_settings_file_loads():
    # A user may copy it into a global or project file as it stands.
    text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    start = text.index("```yaml\nversion: 1\nview: iso")
    example = text[start + len("```yaml\n") : text.index("```\n", start + 1)]
    layer = read_bytes(example.encode(), source="example", directory=ROOT)
    assert layer["camera.direction"] is None
    assert "pitch" not in layer


def test_the_defaults_file_and_the_schema_table_agree():
    shipped = settings.read_defaults()
    assert list(shipped) == list(settings.SCHEMA)
    assert shipped == dict(settings.DEFAULTS)
    assert shipped == {
        # The view, scale and framing settings and the app settings
        # (projects and camera design D-12, D-16): today's option defaults.
        "view": "iso",
        "pitch": None,
        # The camera (projects and camera design D-3, D-7, D-16):
        # orthographic, the view's direction, no roll, and no position.
        "camera.projection": "orthographic",
        "camera.direction": None,
        "camera.roll": 0.0,
        "camera.position": None,
        "directions": None,
        "start_angle": None,
        "model_yaw": 0.0,
        "ppm": None,
        "ground": (0.0, 0.0, 0.0),
        "ground_px": None,
        "supersample": 8,
        "reduce": "plain",
        "root_motion": "error",
        "blender": None,
        "any_blender": False,
        "cell": None,
        "fps": 12.0,
        "frames": "auto",
        "palette": None,
        "materials": None,
        # Hard edges by default (alpha design D-4, D-9).
        "edges": "hard",
        "previews": True,
        "normals": True,
        "depth": False,
        "light.position": None,
        "light.intensity": 1.0,
        "light.ambient": 0.3,
        # Today's shading values stay the defaults (settings design D-12).
        "shade.ao_distance_m": 0.3,
        "shade.ao_samples": 64,
        "shade.occlusion_weight": 0.25,
        "shade.convexity_weight": 1.0,
        "shade.range": (84, 191),
        # The shading controls (shading design contract 1): off by default,
        # so the default command keeps today's images.
        "shade.mode": "ramp",
        "shade.ambient_form": True,
        "shade.key.direction": (
            -0.5183210553488161,
            0.604707897906952,
            0.604707897906952,
        ),
        "shade.key.strength": 0.0,
        "shade.sky.strength": 0.0,
        "shade.ground.strength": 0.0,
        "shade.sky_ground_frame": "camera",
        "shade.brightness.floor": 0.3,
        "shade.brightness.ceiling": 1.0,
        "shade.snap": "off",
        "shade.dither.pattern": "off",
        "shade.dither.strength": 1.0,
        "ramp.lightness_step": 0.12,
        "ramp.hue_shift_deg": -12.0,
        "ramp.chroma_fade": 0.3,
        # The export settings (export design P-7).
        "stored_directions": "all",
        "direction_names": {},
        "mirrors": {},
        "export.formats": ("sheet",),
        "export.frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
        "export.atlas_path": "atlases/{clip}{map}.png",
        "export.sheet_path": "sheet{map}.png",
        "export.atlas_padding": 0,
    }


def test_the_defaults_file_gives_every_default_as_the_table_writes_it():
    text = resources.files("moskophoros").joinpath("defaults.yaml").read_text("utf-8")
    from moskophoros import yamlfile

    document = yamlfile.load(text.encode("utf-8"))
    expected = {"version": 1}
    for name, setting in settings.SCHEMA.items():
        *groups, member = name.split(".")
        target = expected
        for group in groups:
            target = target.setdefault(group, {})
        target[member] = setting.default
    assert document == expected


def test_the_defaults_file_is_installed_with_the_package():
    # The file is read through the package's resources, so an installed
    # distribution must carry it: setuptools installs only what
    # package-data declares beside the modules.
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert declared["tool"]["setuptools"]["package-data"]["moskophoros"] == [
        settings.DEFAULTS_FILE
    ]
    packaged = {
        path.name
        for path in (ROOT / "src" / "moskophoros").rglob("*")
        if path.is_file() and path.suffix not in (".py", ".pyc")
    }
    assert packaged == {settings.DEFAULTS_FILE}


# Reading a settings file


def test_an_empty_mapping_and_a_full_file():
    assert layer("{}\n") == {}
    assert layer(
        "version: 1\ncell: 48x40\nfps: 24\npalette: p.gpl\n"
        "materials: lib.yaml\npreviews: false\n"
    ) == {
        "cell": (48, 40),
        "fps": 24.0,
        "palette": Path("/settings/p.gpl"),
        "materials": Path("/settings/lib.yaml"),
        "previews": False,
    }


def test_comments_and_the_order_of_keys_do_not_matter():
    assert layer("# mine\nfps: 6  # slow\ncell: auto\n") == layer(
        "cell: auto\nfps: 6\n"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("cell: auto", None),
        ("cell: 1x1", (1, 1)),
        ("cell: 4096x4096", (4096, 4096)),
        ("cell: '64x32'", (64, 32)),
        ("fps: 0.5", 0.5),
        ("fps: 1e2", 100.0),
        ("previews: true", True),
        ("edges: hard", "hard"),
        ("edges: soft", "soft"),
        ("edges: 'soft'", "soft"),
        ("palette: null", None),
        ("palette: ~", None),
        ("materials: null", None),
    ],
)
def test_each_settings_values(text, expected):
    key = text.split(":")[0]
    assert layer(text + "\n") == {key: expected}


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("cell: 64", "cell: expected WxH, two integers each from 1 to 4096, or auto"),
        ("cell: 0x5", "cell: expected WxH, two integers each from 1 to 4096, or auto"),
        (
            "cell: 4097x1",
            "cell: expected WxH, two integers each from 1 to 4096, or auto",
        ),
        ("cell: Auto", "cell: expected WxH, two integers each from 1 to 4096, or auto"),
        ("cell: null", "cell: expected WxH, two integers each from 1 to 4096, or auto"),
        (
            "cell: [48, 48]",
            "cell: expected WxH, two integers each from 1 to 4096, or auto",
        ),
        ("fps: 0", "fps: expected a finite number greater than 0, got 0"),
        ("fps: -12", "fps: expected a finite number greater than 0, got -12"),
        ("fps: 1e400", "fps: expected a finite number greater than 0, got inf"),
        ("fps: '12'", "fps: expected a number greater than 0, got '12'"),
        ("fps: .inf", "fps: expected a number greater than 0, got '.inf'"),
        ("fps: true", "fps: expected a number greater than 0, got true"),
        ("fps: null", "fps: expected a number greater than 0, got null"),
        ("palette: ''", "palette: expected a file path or null, got ''"),
        ("palette: 5", "palette: expected a file path or null, got 5"),
        (
            'palette: "bad\\0/p.hex"',
            "palette: expected a file path without a NUL character, got 'bad\\x00/p.hex'",
        ),
        (
            'materials: "lib.yaml\\0"',
            "materials: expected a file path without a NUL character",
        ),
        ("materials: [a.yaml]", "materials: expected a file path or null, got a list"),
        ("previews: yes", "previews: expected true or false, got 'yes'"),
        ("previews: 1", "previews: expected true or false, got 1"),
        ("previews: null", "previews: expected true or false, got null"),
        ("normals: yes", "normals: expected true or false, got 'yes'"),
        ("normals: 1", "normals: expected true or false, got 1"),
        ("normals: null", "normals: expected true or false, got null"),
        ("edges: fuzzy", "edges: expected hard or soft, got 'fuzzy'"),
        ("edges: Hard", "edges: expected hard or soft, got 'Hard'"),
        ("edges: null", "edges: expected hard or soft, got null"),
        ("edges: true", "edges: expected hard or soft, got true"),
        ("edges: [hard]", "edges: expected hard or soft, got a list"),
    ],
)
def test_a_wrong_type_or_out_of_range_value_names_key_and_line(text, problem):
    message = refused("version: 1\n" + text + "\n")
    assert message.startswith(problem)
    assert message.endswith(" at line 2, column 1")


def test_an_overlong_integer_fps_is_refused_with_its_line():
    assert refused("fps: " + "9" * 400 + "\n") == (
        "fps: expected a finite number greater than 0, got "
        + "9" * 400
        + " at line 1, column 1"
    )


@pytest.mark.parametrize("key", ["View", "fame", "Frames", "Cell", "fps ", "Shade"])
def test_an_unknown_key_is_refused_naming_it_and_its_line(key):
    text = f"version: 1\nfps: 12\n'{key}': {{a: 1}}\n"
    assert refused(text) == f"{key}: unknown key at line 3, column 1"


@pytest.mark.parametrize("key", ["work_dir", "settings_from", "clip", "once"])
def test_an_option_that_is_not_a_setting_is_an_unknown_key(key):
    text = f"fps: 12\n{key}: x\n"
    assert refused(text) == f"{key}: unknown key at line 2, column 1"


# The view, scale and framing, and the app settings (projects and camera
# design D-4, D-5, D-12, D-16)


@pytest.mark.parametrize(
    ("text", "key", "expected"),
    [
        ("view: topdown", "view", "topdown"),
        ("view: iso-true", "view", "iso-true"),
        ("pitch: 0", "pitch", 0.0),
        ("pitch: 90", "pitch", 90.0),
        ("pitch: 35.5", "pitch", 35.5),
        ("pitch: null", "pitch", None),
        ("directions: 1", "directions", 1),
        ("directions: 64", "directions", 64),
        ("directions: null", "directions", None),
        ("start_angle: -720.5", "start_angle", -720.5),
        ("start_angle: 1e5", "start_angle", 1e5),
        ("start_angle: null", "start_angle", None),
        ("model_yaw: -90", "model_yaw", -90.0),
        ("ppm: 0.001", "ppm", 0.001),
        ("ppm: 64", "ppm", 64.0),
        ("ppm: auto", "ppm", None),
        ("ground: [-1.5, 0, 2e-1]", "ground", (-1.5, 0.0, 0.2)),
        ("ground_px: [0, 0]", "ground_px", (0, 0)),
        ("ground_px: [16, 40]", "ground_px", (16, 40)),
        # An integral float is the whole number, as `--ground-px 3.0,7` is.
        ("ground_px: [3.0, 7]", "ground_px", (3, 7)),
        # Whether it lies in the cell is an overflow question.
        ("ground_px: [100000, 100000]", "ground_px", (100000, 100000)),
        ("ground_px: auto", "ground_px", None),
        ("supersample: 1", "supersample", 1),
        ("supersample: 16", "supersample", 16),
        ("reduce: mode", "reduce", "mode"),
        ("root_motion: keep", "root_motion", "keep"),
        ("blender: null", "blender", None),
        ("any_blender: true", "any_blender", True),
        ("any_blender: false", "any_blender", False),
    ],
)
def test_each_view_scale_and_app_setting_takes_its_options_values(text, key, expected):
    assert layer(f"{text}\n") == {key: expected}


def test_the_blender_setting_resolves_against_the_files_directory():
    assert layer("blender: bin/blender\n", "/settings") == {
        "blender": Path("/settings/bin/blender")
    }


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("view: front", "expected topdown, side, iso or iso-true, got 'front'"),
        ("view: custom", "expected topdown, side, iso or iso-true, got 'custom'"),
        ("view: null", "expected topdown, side, iso or iso-true, got null"),
        ("pitch: 90.001", "expected a finite number from 0 to 90, or null, got 90.001"),
        ("pitch: -1", "expected a finite number from 0 to 90, or null, got -1"),
        ("pitch: '30'", "expected a finite number from 0 to 90, or null, got '30'"),
        ("pitch: true", "expected a finite number from 0 to 90, or null, got true"),
        ("pitch: 1e400", "expected a finite number from 0 to 90, or null, got inf"),
        ("directions: 0", "expected a whole number from 1 to 64, or null, got 0"),
        ("directions: 65", "expected a whole number from 1 to 64, or null, got 65"),
        ("directions: 8.0", "expected a whole number from 1 to 64, or null, got 8.0"),
        ("start_angle: 1e400", "expected a finite number of degrees, or null, got inf"),
        (
            "start_angle: north",
            "expected a finite number of degrees, or null, got 'north'",
        ),
        ("model_yaw: null", "expected a number of degrees, got null"),
        ("model_yaw: -1e400", "expected a finite number of degrees, got -inf"),
        ("ppm: 0", "expected a finite number greater than 0, or auto, got 0"),
        ("ppm: null", "expected a finite number greater than 0, or auto, got null"),
        ("ppm: Auto", "expected a finite number greater than 0, or auto, got 'Auto'"),
        ("ppm: false", "expected a finite number greater than 0, or auto, got false"),
        ("ground: [1, 2]", "expected [x, y, z], three finite numbers, got [1, 2]"),
        (
            "ground: [0, 1e400, 0]",
            "expected [x, y, z], three finite numbers, got [0, inf, 0]",
        ),
        (
            "ground: [0, true, 0]",
            "expected [x, y, z], three finite numbers, got [0, true, 0]",
        ),
        (
            "ground: ['0', 0, 0]",
            "expected [x, y, z], three finite numbers, got ['0', 0, 0]",
        ),
        ("ground: null", "expected [x, y, z], three finite numbers, got null"),
        (
            "ground_px: [1.5, 0]",
            "expected [x, y], two whole numbers 0 or greater, or auto, got [1.5, 0]",
        ),
        (
            "ground_px: [-1, 0]",
            "expected [x, y], two whole numbers 0 or greater, or auto, got [-1, 0]",
        ),
        (
            "ground_px: [0, true]",
            "expected [x, y], two whole numbers 0 or greater, or auto, got [0, true]",
        ),
        (
            "ground_px: ['3', 7]",
            "expected [x, y], two whole numbers 0 or greater, or auto, got ['3', 7]",
        ),
        (
            "ground_px: [1e400, 0]",
            "expected [x, y], two whole numbers 0 or greater, or auto, got [inf, 0]",
        ),
        (
            "ground_px: [1, 2, 3]",
            "expected [x, y], two whole numbers 0 or greater, or auto, got [1, 2, 3]",
        ),
        (
            "ground_px: null",
            "expected [x, y], two whole numbers 0 or greater, or auto, got null",
        ),
        ("supersample: 0", "expected a whole number from 1 to 16, got 0"),
        ("supersample: 17", "expected a whole number from 1 to 16, got 17"),
        ("supersample: 4.0", "expected a whole number from 1 to 16, got 4.0"),
        ("reduce: median", "expected plain or mode, got 'median'"),
        ("reduce: Mode", "expected plain or mode, got 'Mode'"),
        ("root_motion: ignore", "expected error or keep, got 'ignore'"),
        ("blender: ''", "expected a file path or null, got ''"),
        ("blender: 3", "expected a file path or null, got 3"),
        ("any_blender: yes", "expected true or false, got 'yes'"),
        ("any_blender: null", "expected true or false, got null"),
    ],
)
def test_a_bad_view_scale_or_app_setting_is_refused_naming_key_and_line(text, problem):
    key = text.split(":")[0]
    assert refused(f"fps: 12\n{text}\n") == f"{key}: {problem} at line 2, column 1"


def test_the_settings_presets_are_the_commands():
    from moskophoros import cli

    assert tuple(cli.PRESETS) == settings.VIEWS
    assert cli.REDUCTIONS == settings.REDUCTIONS
    assert cli.ROOT_MOTION_MODES == settings.ROOT_MOTION_MODES


# The shade group (settings design D-3, D-9, D-12, D-22, D-30, D-42)


def test_a_shade_group_gives_one_setting_per_key():
    assert layer(
        "shade:\n  ao_distance_m: 1.2\n  ao_samples: 128\n  occlusion_weight: 0.5\n"
        "  convexity_weight: 0\n  range: [120, 188]\n"
    ) == {
        "shade.ao_distance_m": 1.2,
        "shade.ao_samples": 128,
        "shade.occlusion_weight": 0.5,
        "shade.convexity_weight": 0.0,
        "shade.range": (120, 188),
    }
    assert layer("shade: {occlusion_weight: 0.5}\n") == {"shade.occlusion_weight": 0.5}
    assert layer("shade: {}\n") == {}


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("ao_distance_m", "1e-9", 1e-9),
        ("ao_distance_m", "100", 100.0),
        ("ao_samples", "1", 1),
        ("ao_samples", "128", 128),
        ("occlusion_weight", "0", 0.0),
        ("occlusion_weight", "7.5", 7.5),
        ("convexity_weight", "0.0", 0.0),
        ("range", "[0, 1]", (0, 1)),
        ("range", "[254, 255]", (254, 255)),
        ("range", "[0, 255]", (0, 255)),
    ],
)
def test_each_shade_value_inside_its_bounds(key, value, expected):
    assert layer(f"shade:\n  {key}: {value}\n") == {f"shade.{key}": expected}


@pytest.mark.parametrize(
    ("key", "value", "problem"),
    [
        ("ao_distance_m", "0", "expected a finite number greater than 0, got 0"),
        ("ao_distance_m", "-0.3", "expected a finite number greater than 0, got -0.3"),
        ("ao_distance_m", "1e400", "expected a finite number greater than 0, got inf"),
        ("ao_distance_m", ".inf", "expected a number greater than 0, got '.inf'"),
        ("ao_distance_m", "true", "expected a number greater than 0, got true"),
        (
            "ao_samples",
            "129",
            "expected a whole number from 1 to 128, the most Blender's ambient "
            "occlusion takes, got 129",
        ),
        (
            "ao_samples",
            "0",
            "expected a whole number from 1 to 128, the most Blender's ambient "
            "occlusion takes, got 0",
        ),
        ("ao_samples", "1024", "expected a whole number from 1 to 128"),
        ("ao_samples", "64.0", "expected a whole number from 1 to 128"),
        ("ao_samples", "true", "expected a whole number from 1 to 128"),
        (
            "occlusion_weight",
            "-0.01",
            "expected a finite number 0 or greater, got -0.01",
        ),
        ("convexity_weight", "-1", "expected a finite number 0 or greater, got -1"),
        ("convexity_weight", "'1'", "expected a number 0 or greater, got '1'"),
        ("range", "[191, 84]", "expected [lo, hi], two integers with 0 <= lo < hi"),
        ("range", "[84, 84]", "expected [lo, hi], two integers with 0 <= lo < hi"),
        ("range", "[-1, 84]", "expected [lo, hi], two integers with 0 <= lo < hi"),
        ("range", "[84, 256]", "expected [lo, hi], two integers with 0 <= lo < hi"),
        ("range", "[84.0, 191]", "got [84.0, 191]"),
        ("range", "[true, 191]", "got [true, 191]"),
        ("range", "[84]", "got [84]"),
        ("range", "[84, 120, 191]", "got [84, 120, 191]"),
        ("range", "84,191", "got '84,191'"),
    ],
)
def test_a_shade_value_out_of_bounds_names_its_key_path_and_line(key, value, problem):
    message = refused(f"version: 1\nfps: 12\nshade:\n  {key}: {value}\n")
    assert message.startswith(f"shade.{key}: ")
    assert problem in message
    assert message.endswith(" at line 4, column 3")


def test_an_unknown_shade_key_names_its_key_path_and_line():
    assert refused("shade:\n  ao_samples: 8\n  ao_quality: high\n") == (
        "shade.ao_quality: unknown key at line 3, column 3"
    )


@pytest.mark.parametrize(("value", "shown"), [("0.3", "0.3"), ("[0.3]", "a list")])
def test_shade_must_be_a_mapping(value, shown):
    assert refused(f"fps: 1\nshade: {value}\n") == (
        f"shade: expected a mapping of settings, got {shown} at line 2, column 1"
    )


def test_a_shade_key_that_is_not_a_name_is_refused():
    assert refused("shade:\n  1: 2\n") == (
        "shade: the key 1 is not a setting name at line 2, column 3"
    )


def test_shade_values_merge_key_by_key_and_the_range_replaces_whole():
    defaults = dict(settings.DEFAULTS)
    user = layer("shade: {ao_distance_m: 1.2, range: [120, 255]}\n")
    config = layer("shade: {convexity_weight: 0.5, range: [100, 200]}\n")
    merged = merge(defaults, user, config)
    assert {
        key: value
        for key, value in merged.items()
        if key
        in (
            "shade.ao_distance_m",
            "shade.ao_samples",
            "shade.occlusion_weight",
            "shade.convexity_weight",
            "shade.range",
        )
    } == {
        "shade.ao_distance_m": 1.2,
        "shade.ao_samples": 64,
        "shade.occlusion_weight": 0.25,
        "shade.convexity_weight": 0.5,
        "shade.range": (100, 200),
    }


@pytest.mark.parametrize("version", ["2", "0", "true", "'1'", "1.0", "null"])
def test_an_unknown_version_is_refused(version):
    problem = refused(f"fps: 12\nversion: {version}\n")
    assert problem.startswith("version: expected 1, got ")
    assert problem.endswith(" at line 2, column 1")


def test_version_one_may_be_given_or_left_out():
    assert layer("version: 1\nfps: 6\n") == layer("fps: 6\n") == {"fps": 6.0}


@pytest.mark.parametrize(
    ("text", "shown"), [("- fps", "a list"), ("12", "12"), ("fps", "'fps'")]
)
def test_a_file_that_is_not_a_mapping_is_refused(text, shown):
    assert refused(text + "\n") == f"expected a mapping of settings, got {shown}"


@pytest.mark.parametrize(
    ("key", "shown"), [("1", "1"), ("null", "null"), ("true", "true")]
)
def test_a_key_that_is_not_a_name_is_refused(key, shown):
    assert refused(f"fps: 12\n{key}: x\n") == (
        f"the key {shown} is not a setting name at line 2, column 1"
    )


# Every failure the strict YAML reader refuses is a located settings error.

DIGITS = "9" * (sys.get_int_max_str_digits() + 1)


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ("fps: 1\nfps: 2\n", 'repeats the key "fps" at line 2, column 1'),
        ("fps: !!float 12\n", "uses the tag !!float at line 1, column 6"),
        (
            "cell: &c [*c]\n",
            "the alias *c is inside its own anchor at line 1, column 11",
        ),
        ("fps: 1\n---\nfps: 2\n", "holds more than one YAML document; the second"),
        ("", "is empty: it holds no YAML document"),
        ("# nothing\n", "is empty: it holds no YAML document"),
        ("fps:\n\t12\n", "is not valid YAML at line 2, column 1"),
        ("fps: [1, 2\n", "is not valid YAML at line 2, column 1"),
        (f"fps: {DIGITS}\n", "has an integer of "),
        ('palette: "\\U00110000"\n', "is not valid YAML at line 1, column 13"),
        ("[" * 100_000, "is not valid YAML at line 1, column "),
        (b"fps: \xff\n", "is not UTF-8: invalid start byte at byte 5"),
        (b"\xff\xfe" + "fps: 1\n".encode("utf-16-le"), "is not UTF-8"),
    ],
    ids=[
        "repeated-key",
        "tag",
        "recursive-alias",
        "two-documents",
        "empty",
        "only-comments",
        "tab",
        "unclosed",
        "long-integer",
        "escape-past-unicode",
        "deep-nesting",
        "invalid-utf8",
        "utf-16",
    ],
)
def test_every_yaml_failure_is_a_settings_error_with_its_location(data, problem):
    assert refused(data).startswith(problem)


# Paths


def test_a_relative_path_resolves_against_the_files_directory():
    assert layer("palette: ../p.gpl\n", directory="/a/b")["palette"] == Path(
        "/a/b/../p.gpl"
    )
    assert layer("materials: lib.yaml\n", directory="conf")["materials"] == Path(
        "conf/lib.yaml"
    )


def test_an_absolute_path_is_kept():
    assert layer("palette: /x/p.gpl\n", directory="/a")["palette"] == Path("/x/p.gpl")


@pytest.mark.parametrize(
    ("given", "problem"),
    [
        ('"~bad\\0/p.hex"', "expected a file path without a NUL character"),
        ('"~bad\\uD800/p.hex"', "expected a file path the file system can name"),
    ],
)
def test_a_path_is_checked_before_and_after_it_is_expanded(given, problem):
    message = refused(f"version: 1\npalette: {given}\n")
    assert message.startswith(f"palette: {problem}")
    assert message.endswith(" at line 2, column 1")


def test_an_unknown_user_is_left_unexpanded():
    assert layer("palette: ~no-such-user-84/p.hex\n", directory="/a")["palette"] == (
        Path("/a/~no-such-user-84/p.hex")
    )


def test_a_leading_tilde_is_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert layer("palette: ~/p.gpl\n", directory="/a")["palette"] == tmp_path / "p.gpl"
    # Only a leading tilde.
    assert layer("palette: a/~/p.gpl\n", directory="/a")["palette"] == Path(
        "/a/a/~/p.gpl"
    )


# Files


def test_a_missing_optional_file_gives_no_layer(tmp_path):
    assert read_file(tmp_path / "none.yaml", source="u", required=False) is None


def test_a_missing_required_file_is_an_error(tmp_path):
    with pytest.raises(SettingsError) as raised:
        read_file(tmp_path / "none.yaml", source="--config 'none.yaml'", required=True)
    assert str(raised.value) == "--config 'none.yaml': does not exist"


@pytest.mark.parametrize("required", [True, False])
def test_a_directory_is_unreadable_either_way(tmp_path, required):
    (tmp_path / "dir.yaml").mkdir()
    with pytest.raises(SettingsError) as raised:
        read_file(tmp_path / "dir.yaml", source="d", required=required)
    assert raised.value.problem.startswith("cannot be read: ")


def test_a_files_paths_resolve_against_its_own_directory(tmp_path):
    (tmp_path / "conf").mkdir()
    path = tmp_path / "conf" / "s.yaml"
    path.write_text("palette: p.hex\n")
    assert read_file(path, source="s", required=True) == {
        "palette": tmp_path / "conf" / "p.hex"
    }


# The user file


def test_the_user_file_is_under_xdg_config_home_when_it_is_set():
    environ = {"XDG_CONFIG_HOME": "/x/conf", "HOME": "/home/me"}
    assert settings.user_file(environ) == Path("/x/conf/moskophoros/config.yaml")


@pytest.mark.parametrize(
    "environ", [{"HOME": "/home/me"}, {"XDG_CONFIG_HOME": "", "HOME": "/home/me"}]
)
def test_the_user_file_is_under_home_otherwise(environ):
    assert settings.user_file(environ) == Path(
        "/home/me/.config/moskophoros/config.yaml"
    )


# Project files (projects and camera design D-9, D-16)


def test_a_project_file_is_under_xdg_config_home_when_it_is_set():
    environ = {"XDG_CONFIG_HOME": "/x/conf", "HOME": "/home/me"}
    assert settings.project_file(environ, "look") == Path(
        "/x/conf/moskophoros/projects/look.yaml"
    )


@pytest.mark.parametrize(
    "environ", [{"HOME": "/home/me"}, {"XDG_CONFIG_HOME": "", "HOME": "/home/me"}]
)
def test_a_project_file_is_under_home_otherwise(environ):
    assert settings.project_file(environ, "look..v2") == Path(
        "/home/me/.config/moskophoros/projects/look..v2.yaml"
    )


@pytest.mark.parametrize(
    "name", ["look", "look..v2", "v1.2", "_draft", "-wide", "A-9", "look.yml"]
)
def test_project_names(name):
    assert settings.is_project_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        ".hidden",
        "a/b",
        "../look",
        "/look",
        "a\\b",
        "look.yaml",
        "a b",
        "lö",
        "look\n",
        "look\0",
    ],
)
def test_not_project_names(name):
    assert not settings.is_project_name(name)
    with pytest.raises(ValueError):
        settings.project_file({"HOME": "/home/me"}, name)


# Merging


def test_a_later_layer_wins_key_by_key_and_an_omitted_key_falls_through():
    defaults = dict(settings.DEFAULTS)
    user = {"fps": 6.0, "cell": (48, 48)}
    first = {"fps": 24.0, "palette": Path("/p.gpl")}
    second = {"fps": 30.0}
    assert merge(defaults, user, first, second) == dict(settings.DEFAULTS) | {
        "cell": (48, 48),
        "fps": 30.0,
        "palette": Path("/p.gpl"),
    }


@pytest.mark.parametrize(
    ("value", "expected"), [("auto", None), ("null", None)], ids=["auto", "null"]
)
def test_auto_and_null_are_values_that_override_a_lower_layer(value, expected):
    key = "cell" if value == "auto" else "palette"
    lower = {"cell": (48, 48), "palette": Path("/p.gpl")}
    assert merge(lower, layer(f"{key}: {value}\n"))[key] == expected


def test_merging_nothing_gives_nothing_and_changes_no_layer():
    first = {"fps": 6.0}
    assert merge() == {}
    assert merge(first, {"fps": 7.0}) == {"fps": 7.0}
    assert first == {"fps": 6.0}


# Frame counts (settings design D-13, D-17, D-22, D-31, D-34)


def test_a_global_count_and_each_clips_own_value():
    assert layer(
        "frames: 8\nclips:\n  Jump: {frames: 6}\n  Idle: {frames: auto}\n"
        "  Walk: {frames: null}\n  Pose: {}\n"
    ) == {
        "frames": 8,
        "clips": {
            "Jump": {"frames": 6},
            "Idle": {"frames": "auto"},
            "Walk": {"frames": None},
        },
    }
    assert layer("frames: auto\n") == {"frames": "auto"}
    assert layer("frames: 100000\n") == {"frames": 100000}


@pytest.mark.parametrize(
    ("value", "shown"),
    [("0", "0"), ("-1", "-1"), ("8.0", "8.0"), ("'8'", "'8'"), ("true", "true")]
    + [("null", "null"), ("Auto", "'Auto'"), ("[8]", "a list")],
)
def test_a_bad_global_count_names_its_key_and_line(value, shown):
    assert refused(f"fps: 12\nframes: {value}\n") == (
        f"frames: expected a whole number 1 or more, or auto, got {shown} "
        "at line 2, column 1"
    )


@pytest.mark.parametrize(
    ("value", "shown"),
    [("0", "0"), ("-3", "-3"), ("6.0", "6.0"), ("'6'", "'6'"), ("false", "false")],
)
def test_a_bad_clip_count_names_its_key_path_and_line(value, shown):
    assert refused(
        f"clips:\n  Walk: {{frames: 2}}\n  Jump:\n    frames: {value}\n"
    ) == (
        f"clips.Jump.frames: expected a whole number 1 or more, auto or null, got "
        f"{shown} at line 4, column 5"
    )


def test_an_unknown_clip_key_names_its_key_path_and_line():
    assert refused("clips:\n  Jump:\n    frames: 6\n    speed: 24\n") == (
        "clips.Jump.speed: unknown key at line 4, column 5"
    )


def test_a_clip_leaf_is_checked_and_names_its_key_path_and_line():
    layer = read_bytes(
        b"clips:\n  Jump:\n    frames: 6\n    fps: 24\n",
        source="s.yaml",
        directory="/settings",
    )
    assert layer["clips"] == {"Jump": {"frames": 6, "fps": 24.0}}
    assert layer.where[("clips", "Jump", "fps")] == (4, 5)
    assert refused("clips:\n  Jump:\n    frames: 6\n    fps: 0\n").startswith(
        "clips.Jump.fps: "
    )


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("clips: [Jump]\n", "clips: expected a mapping of clips by name, got a list"),
        (
            "clips:\n  Jump: 6\n",
            "clips.Jump: expected a mapping of the clip's settings, got 6 at line 2, "
            "column 3",
        ),
        ("clips:\n  1: {frames: 6}\n", "clips: the key 1 is not a clip name"),
        ("clips:\n  '': {frames: 6}\n", "clips: the key '' is not a clip name"),
    ],
)
def test_a_malformed_clips_mapping_is_refused(text, problem):
    assert refused(text).startswith(problem)


def test_per_clip_values_merge_by_name_and_null_clears_a_lower_count():
    user = layer("clips:\n  Jump: {frames: 6}\n  Walk: {frames: 4}\n")
    config = layer("clips:\n  Jump: {frames: null}\n  Idle: {frames: auto}\n")
    assert merge(user, config)["clips"] == {
        "Jump": {"frames": None},
        "Walk": {"frames": 4},
        "Idle": {"frames": "auto"},
    }
    assert merge(user, layer("fps: 6\n"))["clips"] == {
        "Jump": {"frames": 6},
        "Walk": {"frames": 4},
    }
