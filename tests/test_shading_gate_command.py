"""No public path can reach the shading foundations: a `/4` library, the nested
shading settings and the response in a stored library still fail exactly as
they did, before any Blender invocation (shading design D-39, SHD-2)."""

import ast
import json
from pathlib import Path

import pytest
from test_command import Setup, run
from test_materials_command import (
    GOOD_RECORD,
    forbid_blender,
    library_file,
    library_with,
    materialed,
    named_hero,
    palette_file,
    style_sheet,
)
from test_settings_command import config, project_file, refused, user_file

from moskophoros import cli

SRC = Path(__file__).resolve().parents[1] / "src" / "moskophoros"
V4 = "moskophoros.materials/4"


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


# A `/4` library through `--materials`


@pytest.mark.parametrize(
    "library",
    [
        library_with(schema=V4),
        library_with(
            schema=V4,
            materials={"steel": {"ordinary": True, "shade": {"mode": "both"}}},
        ),
        library_with(schema=V4, shade={"key": {"strength": 0.5}}),
    ],
    ids=["plain", "ordinary mapping", "library-wide response"],
)
def test_a_v4_library_is_refused_with_the_pre_arc_error_before_blender(
    setup, capsys, monkeypatch, library
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, materialed(setup, library=library))
    assert status == 2
    assert (
        'materials.yaml: schema: expected "moskophoros.materials/3" or '
        '"moskophoros.materials/2", got "moskophoros.materials/4"' in err
    )
    assert setup.calls() == []


@pytest.mark.parametrize(
    ("library", "problem"),
    [
        (
            library_with(materials={"steel": {"ordinary": True}}),
            'materials["steel"]: unknown field "ordinary"',
        ),
        (
            library_with(
                materials={"steel": {"uses": "metal", "shade": {"mode": "both"}}}
            ),
            'materials["steel"].shade: unknown field "mode"',
        ),
        (
            library_with(
                materials={
                    "steel": {"uses": "metal", "shade": {"brightness": {"floor": 0}}}
                }
            ),
            'materials["steel"].shade: unknown field "brightness"',
        ),
        (library_with(shade={"mode": "both"}), 'shade: unknown field "mode"'),
    ],
    ids=["ordinary mapping", "entry mode", "entry nested", "library mode"],
)
def test_the_new_fields_in_a_v3_library_are_unknown_fields_as_before(
    setup, capsys, monkeypatch, library, problem
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, materialed(setup, library=library))
    assert status == 2
    assert f"materials.yaml: {problem}" in err
    assert setup.calls() == []


def test_the_v1_error_still_names_v3(setup, capsys, monkeypatch):
    forbid_blender(monkeypatch)
    status, _, err = run(
        capsys,
        materialed(setup, library=library_with(schema="moskophoros.materials/1")),
    )
    assert status == 2
    assert 'change the schema line to "moskophoros.materials/3"' in err


# A `/4`-only library stored in a current sheet


def stored(tmp_path, capsys, record):
    sheet = style_sheet(tmp_path, materials=record)
    with pytest.raises(cli.UsageError):
        cli.read_settings(sheet)
    err = capsys.readouterr().err
    assert f"--settings-from {str(sheet)!r}: " in err
    return err


def record_with(**changes):
    record = json.loads(json.dumps(GOOD_RECORD))
    for key, value in changes.items():
        record["materials"]["steel"][key] = value
    return record


def test_a_stored_ordinary_mapping_entry_is_an_unknown_field(tmp_path, capsys):
    record = json.loads(json.dumps(GOOD_RECORD))
    record["materials"]["face"] = {"ordinary": True}
    assert (
        'settings.style.materials: materials["face"]: unknown field "ordinary"'
        in stored(tmp_path, capsys, record)
    )


def test_a_stored_entry_response_field_is_an_unknown_field(tmp_path, capsys):
    record = record_with(shade={"mode": "both"})
    assert (
        'settings.style.materials: materials["steel"].shade: unknown field "mode"'
        in stored(tmp_path, capsys, record)
    )
    record = record_with(shade={"key": {"strength": 0.5}})
    assert (
        'settings.style.materials: materials["steel"].shade: unknown field "key"'
        in stored(tmp_path, capsys, record)
    )


def test_a_stored_library_wide_response_field_is_an_unknown_field(tmp_path, capsys):
    record = json.loads(json.dumps(GOOD_RECORD))
    record["shade"] = {"mode": "both"}
    assert 'settings.style.materials: shade: unknown field "mode"' in stored(
        tmp_path, capsys, record
    )


def test_the_stored_library_validates_as_v3_so_no_schema_field_turns_the_gate_on(
    tmp_path, capsys
):
    record = json.loads(json.dumps(GOOD_RECORD))
    record["schema"] = V4
    assert "settings.style.materials.schema: unknown field" in stored(
        tmp_path, capsys, record
    )


def test_a_stored_response_is_refused_whatever_options_replace_the_library(
    tmp_path, capsys
):
    sheet = style_sheet(tmp_path, materials=record_with(shade={"mode": "both"}))
    for options in ((), ("--no-materials",)):
        with pytest.raises(cli.UsageError):
            cli.resolve_settings(
                cli.parse_args(
                    [
                        "--settings-from",
                        str(sheet),
                        "--no-user-config",
                        *options,
                        "m.glb",
                        "o.png",
                    ]
                )
            )
        assert 'shade: unknown field "mode"' in capsys.readouterr().err


# Nested shading keys in a settings file


NESTED = "shade:\n  key:\n    strength: 0.5\n"


def test_nested_shading_keys_in_every_settings_file_keep_the_old_error(
    tmp_path, capsys
):
    path = config(tmp_path, NESTED)
    assert refused(capsys, "--config", str(path)) == (
        f"--config {str(path)!r}: shade.key: unknown key at line 2, column 3"
    )
    path = user_file(NESTED)
    assert refused(capsys) == (
        f"the user settings {str(path)!r}: shade.key: unknown key at line 2, column 3"
    )
    path = project_file("shade:\n  brightness: {floor: 0.2}\n")
    message = refused(capsys, "--no-user-config", "--project", "look")
    assert message.endswith("shade.brightness: unknown key at line 2, column 3")


def test_flat_shading_keys_in_a_settings_file_are_unknown_as_before(tmp_path, capsys):
    path = config(tmp_path, "shade:\n  mode: both\n")
    assert refused(capsys, "--config", str(path)) == (
        f"--config {str(path)!r}: shade.mode: unknown key at line 2, column 3"
    )


def test_a_command_with_nested_shading_keys_exits_2_before_blender(
    setup, capsys, monkeypatch, tmp_path
):
    forbid_blender(monkeypatch)
    path = config(tmp_path, NESTED)
    status, _, err = run(capsys, setup.argv("--config", str(path)))
    assert status == 2
    assert "shade.key: unknown key at line 2, column 3" in err
    assert "shade.key.strength" not in err
    assert setup.calls() == []


def test_no_shading_option_exists_yet(capsys):
    for option in ("--shade-mode", "--bake-key-strength", "--brightness-floor"):
        with pytest.raises(cli.UsageError):
            cli.parse_args([option, "0.5", "m.glb", "o.png"])
        assert f"unrecognized option: {option}" in capsys.readouterr().err


# The gate cannot be reached from the public command


def test_only_the_internal_modules_name_the_gate():
    internal = {
        "lighting.py",
        "shading.py",
        "shading_resolve.py",
        "settings.py",
        "materials.py",
        # The stage takes the resolved shading as an argument; the command
        # passes none until SHD-6, and neither module ever passes `True`.
        "stylize.py",
        "shade_layers.py",
    }
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "shading":
                # The two readers pass their own parameter through, never True.
                assert path.name in internal, path
                assert not (
                    isinstance(node.value, ast.Constant) and node.value.value is True
                ), path
            names = {
                getattr(node, "id", None),
                getattr(node, "attr", None),
            } & {"SHADING_SCHEMA", "SHADING_DEFAULTS", "SCHEMA_V4", "shading_resolve"}
            if names:
                assert path.name in internal, (path, names)
            if isinstance(node, ast.ImportFrom | ast.Import):
                imported = {alias.name for alias in node.names} | {
                    getattr(node, "module", None) or ""
                }
                if imported & {"shading", "shading_resolve", "moskophoros.shading"}:
                    assert path.name in internal, path


def test_the_public_loaders_do_not_pass_the_gate():
    # Reading a file or the packaged defaults, and a library file or sheet
    # record, never turn it on.
    import inspect

    from moskophoros import materials, settings

    for function in (
        settings.read_file,
        settings.read_defaults,
        materials.read_library,
    ):
        assert "shading" not in inspect.getsource(function)
    assert inspect.signature(settings.read_bytes).parameters["shading"].default is False
    assert (
        inspect.signature(materials.validate_library).parameters["shading"].default
        is False
    )
    assert (
        inspect.signature(materials.read_library_bytes).parameters["shading"].default
        is False
    )


def test_the_default_command_still_writes_a_current_sheet(setup, capsys, tmp_path):
    # With the foundations in place nothing new reaches the sheet.
    named_hero(setup, [{"name": "steel"}])
    argv = setup.argv(
        "--no-preview",
        "--palette",
        str(palette_file(tmp_path)),
        "--materials",
        str(library_file(tmp_path, library_with())),
    )
    status, _, err = run(capsys, argv)
    assert status == 0, err
    sheet = json.loads(setup.json.read_text())
    assert sheet["schema"] == "moskophoros.sheet/14"
    assert list(sheet["settings"]["shade"]) == [
        "ao_distance_m",
        "ao_samples",
        "occlusion_weight",
        "convexity_weight",
        "range",
    ]


def test_the_command_passes_no_resolved_shading_to_stylize():
    # SHD-5 gives stylize the arguments; SHD-6 wires them. Until then the
    # command's reductions carry neither, so its output cannot change.
    tree = ast.parse((SRC / "cli.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword):
            assert node.arg not in {"shading", "lights"}, node.lineno
        if isinstance(node, ast.Attribute | ast.Name):
            assert getattr(node, "attr", getattr(node, "id", None)) != "shade_layers"
