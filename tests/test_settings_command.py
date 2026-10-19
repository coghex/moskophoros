"""Settings layers in the command: the shipped defaults, the global file
(the user file, or the one `--config` names), a loaded sheet, the project
file (`--project`) and options (settings design D-2, D-8, D-15, D-16, D-17,
D-19, D-22, D-27, D-28 and D-32; projects and camera design D-9, D-11, D-16
and D-17), with a controlled fake Blender.

The suite's `no_owner_settings` fixture points `$XDG_CONFIG_HOME` and `$HOME`
at empty temporary directories, so a user file exists only where a test
writes one."""

import errno
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_command import Setup, run
from test_materials_command import (
    COLORS,
    GOOD_RECORD,
    PALETTE_RECORD,
    forbid_blender,
    library_file,
    palette_file,
    style_sheet,
)
from test_reuse import write_sheet

from moskophoros import cli, views
from moskophoros import settings as settings_module

POSITIONALS = ["in.glb", "out.png"]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def user_file(text):
    path = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros", "config.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def config(directory, text, name="settings.yaml"):
    path = Path(directory) / name
    path.write_text(text)
    return path


def project_file(text, name="look"):
    """Write project `name`'s file in the suite's configuration directory."""
    path = Path(
        os.environ["XDG_CONFIG_HOME"], "moskophoros", "projects", f"{name}.yaml"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def project_label(path, name="look"):
    return f"--project {name!r} ({str(path)!r})"


def resolved(*args):
    return cli.resolve_settings(cli.parse_args([*args, *POSITIONALS]))


def refused(capsys, *args):
    with pytest.raises(cli.UsageError) as raised:
        resolved(*args)
    err = capsys.readouterr().err
    assert err.splitlines()[0].startswith("usage:")
    assert err.splitlines()[-1] == f"moskophoros: error: {raised.value.message}"
    return raised.value.message


# The user file


def test_a_user_file_found_through_xdg_config_home_applies():
    user_file("fps: 6\ncell: 48x40\npreviews: false\n")
    options = resolved()
    assert (options.fps, options.cell, options.previews) == (6.0, (48, 40), False)


def test_without_xdg_config_home_the_user_file_is_under_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / ".config" / "moskophoros" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("fps: 7\n")
    assert resolved().fps == 7.0


def test_no_user_config_skips_the_user_file():
    user_file("fps: 6\nunknown: 1\n")
    assert resolved("--no-user-config").fps == 12.0


def test_a_missing_user_file_is_not_an_error():
    options = resolved()
    assert (options.fps, options.cell, options.previews) == (12.0, None, True)
    assert (options.palette, options.materials) == (None, None)


def test_a_bad_user_file_is_a_usage_error_naming_it(capsys):
    path = user_file("fps: 6\nfame: 8\n")
    assert refused(capsys) == (
        f"the user settings {str(path)!r}: fame: unknown key at line 2, column 1"
    )


def test_the_user_file_is_never_written(tmp_path):
    path = user_file("fps: 6\n")
    before = path.read_bytes(), path.stat().st_mtime_ns
    resolved()
    resolved("--fps", "9")
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


# The global file named by `--config`


def test_a_config_file_applies_as_the_global_file(tmp_path):
    path = config(tmp_path, "version: 1\nfps: 8\ncell: 32x30\n")
    options = resolved("--config", str(path))
    assert (options.fps, options.cell) == (8.0, (32, 30))
    # The global file gives defaults, as the user file does: not explicit
    # values (projects and camera design D-11).
    assert not {"fps", "cell"} & options.explicit


def test_a_missing_config_file_is_a_usage_error(tmp_path, capsys):
    path = tmp_path / "absent.yaml"
    assert refused(capsys, "--config", str(path)) == (
        f"--config {str(path)!r}: does not exist"
    )


def test_an_unreadable_config_file_is_a_usage_error(tmp_path, capsys):
    (tmp_path / "dir.yaml").mkdir()
    assert refused(capsys, "--config", str(tmp_path / "dir.yaml")).startswith(
        f"--config {str(tmp_path / 'dir.yaml')!r}: cannot be read: "
    )


def test_a_second_config_is_a_usage_error(tmp_path, capsys):
    # D-17's exception 1: two files are now the global file and a project.
    first = config(tmp_path, "fps: 8\n", "first.yaml")
    second = config(tmp_path, "fps: 9\n", "second.yaml")
    assert refused(capsys, "--config", str(first), "--config", str(second)) == (
        f"argument --config: given more than once: {str(first)!r}, {str(second)!r}"
    )


def test_config_replaces_the_user_file(tmp_path):
    # D-17's exception 2: a setting only the user file gave no longer applies.
    user_file("fps: 6\ncell: 40x40\n")
    options = resolved("--config", str(config(tmp_path, "fps: 8\n")))
    assert (options.fps, options.cell) == (8.0, None)


def test_config_with_no_user_config_is_a_usage_error(tmp_path, capsys):
    # D-17's exception 3: `--config FILE` alone already uses no other file.
    path = config(tmp_path, "fps: 8\n")
    assert refused(capsys, "--config", str(path), "--no-user-config") == (
        "--config and --no-user-config cannot be given together"
    )


def test_an_alternate_config_bypasses_a_malformed_user_file(tmp_path):
    user_file("fps: 0\nunknown: 1\n")
    assert resolved("--config", str(config(tmp_path, "fps: 8\n"))).fps == 8.0


def test_the_global_file_is_checked_even_when_the_project_overrides_it(
    tmp_path, capsys
):
    bad = config(tmp_path, "fps: 0\n", "bad.yaml")
    project_file("fps: 9\n")
    assert refused(capsys, "--config", str(bad), "--project", "look") == (
        f"--config {str(bad)!r}: fps: expected a finite number greater than 0, "
        "got 0 at line 1, column 1"
    )


def test_the_project_file_is_checked_even_when_an_option_overrides_it(capsys):
    path = project_file("fps: 0\n")
    assert refused(capsys, "--project", "look", "--fps", "9") == (
        f"{project_label(path)}: fps: expected a finite number greater than 0, "
        "got 0 at line 1, column 1"
    )


# Project files (projects and camera design D-9, D-11 and D-16)


def test_a_project_file_found_through_xdg_config_home_applies():
    project_file("fps: 8\ncell: 32x30\n")
    options = resolved("--project", "look")
    assert (options.fps, options.cell) == (8.0, (32, 30))
    # A project's values act as explicit options.
    assert {"fps", "cell"} <= options.explicit


def test_without_xdg_config_home_projects_are_under_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / ".config" / "moskophoros" / "projects" / "look.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("fps: 7\n")
    assert resolved("--project", "look").fps == 7.0


def test_an_empty_xdg_config_home_means_home_for_projects(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / ".config" / "moskophoros" / "projects" / "look.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("fps: 7\n")
    assert resolved("--project", "look").fps == 7.0


@pytest.mark.parametrize("how", ["config", "no-user-config"])
def test_neither_config_nor_no_user_config_moves_the_projects(tmp_path, how):
    project_file("fps: 8\n")
    # A project folder beside the --config file is never looked in.
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "look.yaml").write_text("fps: 3\n")
    if how == "config":
        args = ["--config", str(config(tmp_path, "cell: 32x30\n"))]
    else:
        user_file("cell: 32x30\n")
        args = ["--no-user-config"]
    options = resolved(*args, "--project", "look")
    assert options.fps == 8.0
    assert options.cell == ((32, 30) if how == "config" else None)


def test_a_missing_project_file_is_a_usage_error_and_creates_nothing(capsys):
    home = Path(os.environ["XDG_CONFIG_HOME"])
    before = sorted(home.rglob("*"))
    path = home / "moskophoros" / "projects" / "absent.yaml"
    assert refused(capsys, "--project", "absent") == (
        f"{project_label(path, 'absent')}: does not exist"
    )
    assert sorted(home.rglob("*")) == before
    user_file("fps: 6\n")
    assert refused(capsys, "--project", "absent").endswith(": does not exist")
    assert not (home / "moskophoros" / "projects").exists()


def test_a_project_that_is_a_directory_is_a_usage_error(capsys):
    path = project_file("fps: 8\n").parent / "folder.yaml"
    path.mkdir()
    assert refused(capsys, "--project", "folder").startswith(
        f"{project_label(path, 'folder')}: cannot be read: "
    )


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", ".hidden", "a/b", "../look", "/look", "look.yaml", "a b", "lö"],
)
def test_a_name_that_is_not_a_project_name_is_a_usage_error_naming_it(capsys, name):
    project_file("fps: 8\n")
    message = refused(capsys, f"--project={name}")
    assert message == (
        f"argument --project: {name!r} is not a project name: use letters, "
        "digits, '.', '_' and '-', not starting with '.', and leave out '.yaml'"
    )


@pytest.mark.parametrize("name", ["look..v2", "v1.2", "_draft", "-wide", "A-9"])
def test_a_name_with_inner_dots_or_a_leading_dash_is_a_project_name(name):
    project_file("fps: 8\n", name)
    assert resolved(f"--project={name}").fps == 8.0


def test_a_second_project_is_a_usage_error(capsys):
    project_file("fps: 8\n")
    project_file("fps: 9\n", "other")
    assert refused(capsys, "--project", "look", "--project", "other") == (
        "argument --project: given more than once: 'look', 'other'"
    )


@pytest.mark.parametrize("text", ["{}\n", "version: 1\n"])
def test_an_empty_project_mapping_changes_nothing(text):
    user_file("fps: 6\ncell: 40x40\n")
    project_file(text)
    assert resolved("--project", "look") == replace(
        resolved(), project="look", explicit=frozenset({"project"})
    )


@pytest.mark.parametrize("text", ["", "# nothing\n"])
def test_a_project_file_holding_no_document_is_a_usage_error(capsys, text):
    path = project_file(text)
    assert refused(capsys, "--project", "look") == (
        f"{project_label(path)}: is empty: it holds no YAML document"
    )


def test_a_project_sets_only_what_it_lists(tmp_path):
    user_file("fps: 6\npreviews: false\n")
    project_file("cell: 32x30\n")
    options = resolved("--project", "look")
    assert (options.fps, options.previews, options.cell) == (6.0, False, (32, 30))


def test_a_project_and_the_global_file_share_one_schema(tmp_path, capsys):
    text = "fps: 6\nfame: 8\n"
    path = project_file(text)
    assert refused(capsys, "--project", "look") == (
        f"{project_label(path)}: fame: unknown key at line 2, column 1"
    )
    path = config(tmp_path, text)
    assert refused(capsys, "--config", str(path)) == (
        f"--config {str(path)!r}: fame: unknown key at line 2, column 1"
    )


# Precedence, pair by pair


def test_the_user_file_is_above_the_defaults():
    user_file("fps: 6\n")
    assert resolved().fps == 6.0


@pytest.mark.parametrize("global_", ["user", "config"])
def test_a_project_file_is_above_the_global_file(tmp_path, global_):
    text = "fps: 6\ncell: 40x40\n"
    if global_ == "user":
        user_file(text)
        args = []
    else:
        args = ["--config", str(config(tmp_path, text))]
    project_file("fps: 8\n")
    options = resolved(*args, "--project", "look")
    assert (options.fps, options.cell) == (8.0, (40, 40))


def test_an_option_is_above_a_project_file():
    project_file("fps: 8\ncell: 48x48\npreviews: false\n")
    options = resolved("--project", "look", "--fps", "10", "--preview")
    assert (options.fps, options.cell, options.previews) == (10.0, (48, 48), True)


def test_a_loaded_sheet_is_above_the_user_file(tmp_path):
    user_file("fps: 6\ncell: 32x32\npreviews: true\n")
    options = resolved("--settings-from", str(write_sheet(tmp_path)))
    assert (options.fps, options.cell, options.previews) == (24.0, (48, 40), False)


def test_a_loaded_sheet_is_above_a_config_global_file(tmp_path):
    # D-17's exception 4: the sheet's values now win where the file's used to.
    path = config(tmp_path, "fps: 8\ncell: 32x30\npreviews: true\n")
    options = resolved(
        "--settings-from", str(write_sheet(tmp_path)), "--config", str(path)
    )
    assert (options.fps, options.cell, options.previews) == (24.0, (48, 40), False)


def test_a_project_file_is_above_a_loaded_sheet(tmp_path):
    user_file("fps: 6\n")
    project_file("fps: 8\ncell: 32x30\npreviews: true\n")
    options = resolved(
        "--settings-from", str(write_sheet(tmp_path)), "--project", "look"
    )
    assert (options.fps, options.cell, options.previews) == (8.0, (32, 30), True)
    # As --cell after --settings-from: the reused scale and ground pixel stay,
    # so both are fixed.
    assert (options.ppm, options.ground_px) == (32.0, (24, 37))


def test_an_option_is_above_a_loaded_sheet_and_a_project_file(tmp_path):
    project_file("fps: 8\n")
    options = resolved(
        "--settings-from",
        str(write_sheet(tmp_path)),
        "--project",
        "look",
        "--fps",
        "5",
    )
    assert options.fps == 5.0


# `auto` and `null` at each layer


@pytest.mark.parametrize("layer", ["user", "project", "option"])
def test_cell_auto_at_each_layer_returns_to_the_automatic_cell(tmp_path, layer):
    user_file("cell: 48x48\n" if layer != "user" else "cell: auto\n")
    args = []
    if layer == "project":
        project_file("cell: auto\n")
        args = ["--project", "look"]
    elif layer == "option":
        args = ["--cell", "auto"]
    assert resolved(*args).cell is None


@pytest.mark.parametrize("how", [("--cell", "auto"), "project"])
def test_cell_auto_over_a_loaded_sheet_fits_with_the_reused_scale(tmp_path, how):
    if how == "project":
        project_file("cell: auto\n")
        args = ["--project", "look"]
    else:
        args = list(how)
    options = resolved("--settings-from", str(write_sheet(tmp_path)), *args)
    assert (options.cell, options.ppm) == (None, 32.0)


def test_the_defaults_never_turn_ppm_sizing_into_a_fixed_cell():
    options = resolved("--ppm", "20")
    assert (options.ppm, options.cell) == (20.0, None)


@pytest.mark.parametrize("layer", ["user", "config", "project"])
def test_a_null_palette_and_library_at_a_layer_mean_none(tmp_path, layer):
    # The user file below names files that do not exist: they are never read.
    user_file("palette: missing.hex\nmaterials: missing.yaml\n")
    args = []
    nulls = "palette: null\nmaterials: null\n"
    if layer == "config":
        args = ["--config", str(config(tmp_path, nulls))]
    elif layer == "project":
        project_file(nulls)
        args = ["--project", "look"]
    else:
        user_file(nulls)
    options = resolved(*args)
    assert (options.palette, options.materials) == (None, None)


def test_an_overridden_user_path_that_no_longer_exists_is_never_read(tmp_path):
    user_file("palette: gone.hex\nmaterials: gone.yaml\n")
    palette = palette_file(tmp_path)
    options = resolved("--palette", str(palette), "--no-materials")
    assert options.palette.source == "palette.hex"
    assert options.materials is None


def test_a_global_path_a_project_overrides_is_never_read(tmp_path):
    path = config(tmp_path, "palette: gone.hex\nmaterials: gone.yaml\n")
    project_file(f"palette: {palette_file(tmp_path)}\nmaterials: null\n")
    options = resolved("--config", str(path), "--project", "look")
    assert options.palette.source == "palette.hex"
    assert options.materials is None


# Paths in settings files


def test_paths_resolve_against_the_settings_files_directory(tmp_path, monkeypatch):
    (tmp_path / "conf" / "lib").mkdir(parents=True)
    palette_file(tmp_path / "conf")
    library_file(tmp_path / "conf" / "lib")
    path = config(
        tmp_path / "conf", "palette: palette.hex\nmaterials: lib/materials.yaml\n"
    )
    monkeypatch.chdir(tmp_path)
    options = resolved("--config", str(path))
    assert (options.palette.source, options.materials.source) == (
        "palette.hex",
        "materials.yaml",
    )


def test_paths_in_a_project_file_resolve_against_its_directory(tmp_path, monkeypatch):
    path = project_file("palette: palette.hex\nmaterials: lib/materials.yaml\n")
    (path.parent / "lib").mkdir()
    palette_file(path.parent)
    library_file(path.parent / "lib")
    monkeypatch.chdir(tmp_path)
    options = resolved("--project", "look")
    assert (options.palette.source, options.materials.source) == (
        "palette.hex",
        "materials.yaml",
    )


def test_a_leading_tilde_expands_to_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    palette_file(tmp_path)
    user_file("palette: ~/palette.hex\n")
    assert resolved().palette.colors == COLORS


def test_a_file_path_error_names_the_settings_file(tmp_path, capsys):
    path = config(tmp_path, "palette: missing.hex\n")
    assert refused(capsys, "--config", str(path)) == (
        f"--config {str(path)!r}: palette (line 1, column 1) "
        f"{str(tmp_path / 'missing.hex')!r}: cannot be read: No such file or directory"
    )


def test_a_library_from_a_file_is_validated_against_the_palette_in_force(
    tmp_path, capsys
):
    library = library_file(tmp_path)
    small = palette_file(tmp_path, COLORS[:2], name="small.hex")
    user_file(f"palette: {small}\nmaterials: {library}\n")
    message = refused(capsys)
    assert message.startswith("the user settings ")
    assert ": materials " in message
    assert "is not an index into the 2-colour palette" in message


def test_a_library_from_a_file_needs_a_palette(tmp_path, capsys):
    path = config(tmp_path, f"materials: {library_file(tmp_path)}\n")
    assert refused(capsys, "--config", str(path)).startswith(
        f"--config {str(path)!r}: materials "
    )


# Palette and library from a project over a loaded sheet (the reuse table)


def test_a_reused_library_stays_with_a_project_palette_of_the_same_colours(
    tmp_path,
):
    same = palette_file(tmp_path, name="same.hex")
    project_file(f"palette: {same}\n")
    options = resolved(
        "--settings-from", str(style_sheet(tmp_path)), "--project", "look"
    )
    assert options.palette.source == "same.hex"
    assert options.materials.source == GOOD_RECORD["source"]


def test_a_project_palette_of_other_colours_beside_a_reused_library_is_refused(
    tmp_path, capsys
):
    other = palette_file(tmp_path, COLORS[::-1], name="other.hex")
    path = project_file(f"palette: {other}\n")
    message = refused(
        capsys, "--settings-from", str(style_sheet(tmp_path)), "--project", "look"
    )
    assert message.startswith(
        f"{project_label(path)}: palette (line 1, column 1) {str(other)!r}: "
    )
    assert "its colours differ from the reused palette" in message


def test_a_project_null_palette_beside_a_reused_library_is_refused(tmp_path, capsys):
    path = project_file("palette: null\n")
    message = refused(
        capsys, "--settings-from", str(style_sheet(tmp_path)), "--project", "look"
    )
    assert message == (
        f"{project_label(path)}: palette (line 1, column 1): the reused material "
        "library needs a palette; also give --no-materials to drop it"
    )


def test_a_project_null_library_drops_the_reused_one(tmp_path):
    project_file("palette: null\nmaterials: null\n")
    options = resolved(
        "--settings-from", str(style_sheet(tmp_path)), "--project", "look"
    )
    assert (options.palette, options.materials) == (None, None)


def test_a_project_library_replaces_the_reused_one_on_the_reused_palette(tmp_path):
    project_file(f"materials: {library_file(tmp_path, name='mine.yaml')}\n")
    options = resolved(
        "--settings-from", str(style_sheet(tmp_path)), "--project", "look"
    )
    assert options.materials.source == "mine.yaml"
    assert options.palette.source == PALETTE_RECORD["source"]


@pytest.mark.parametrize("global_", ["user", "config"])
def test_the_global_files_palette_and_library_never_change_a_loaded_sheet(
    tmp_path, global_
):
    text = "palette: gone.hex\nmaterials: gone.yaml\n"
    args = []
    if global_ == "user":
        user_file(text)
    else:
        args = ["--config", str(config(tmp_path, text))]
    options = resolved("--settings-from", str(style_sheet(tmp_path)), *args)
    assert options.palette.source == PALETTE_RECORD["source"]
    assert options.materials.source == GOOD_RECORD["source"]


def test_an_option_beats_a_project_palette_over_a_loaded_sheet(tmp_path):
    other = palette_file(tmp_path, COLORS[::-1], name="other.hex")
    project_file(f"palette: {other}\n")
    options = resolved(
        "--settings-from",
        str(style_sheet(tmp_path)),
        "--project",
        "look",
        "--no-palette",
        "--no-materials",
    )
    assert (options.palette, options.materials) == (None, None)


# Previews


def test_preview_and_no_preview_together_are_a_usage_error(capsys):
    with pytest.raises(cli.UsageError) as raised:
        cli.parse_args(["--preview", "--no-preview", *POSITIONALS])
    assert raised.value.message == "--preview and --no-preview cannot be given together"


def test_previews_false_in_a_settings_file_writes_no_previews(setup, capsys, tmp_path):
    path = config(tmp_path, "previews: false\n")
    status, _, err = run(capsys, setup.argv("--config", str(path)))
    assert status == 0, err
    assert sorted(setup.listing()) == ["hero.json", "hero.normal.png", "hero.png"]
    assert json.loads(setup.json.read_text())["settings"]["previews"] is False


# The sheet and its bytes (projects and camera design D-9, D-17)


def test_a_global_file_and_a_project_give_the_bytes_of_one_merged_file(
    setup, capsys, tmp_path
):
    palette = palette_file(tmp_path)
    merged = (
        f"fps: 6\nedges: soft\ndepth: true\npalette: {palette}\n"
        "light:\n  position: [-20, 30, 40]\n  intensity: 2\n"
    )
    path = config(tmp_path, merged, "zz-merged-q7.yaml")
    status, _, err = run(capsys, setup.argv("--config", str(path)))
    assert status == 0, err
    expected = setup.listing()
    assert {"hero.depth.png", "hero-lit.walk.gif"} <= set(expected)
    shutil.rmtree(setup.out)
    setup.out.mkdir()
    path = config(
        tmp_path,
        f"fps: 9\nedges: soft\npalette: {palette}\nlight:\n  intensity: 2\n",
        "zz-global-q7.yaml",
    )
    project_file("fps: 6\ndepth: true\nlight:\n  position: [-20, 30, 40]\n", "zz-q7")
    status, _, err = run(
        capsys, setup.argv("--config", str(path), "--project", "zz-q7")
    )
    assert status == 0, err
    assert setup.listing() == expected
    # The sheet names neither the project nor a settings file.
    text = setup.json.read_text()
    assert "q7" not in text and "projects" not in text


# Every settings error before any Blender invocation


def bad_settings(kind, tmp_path):
    """The arguments of a run whose settings are bad in way `kind`."""
    if kind == "missing-config":
        return ["--config", str(tmp_path / "absent.yaml")]
    if kind == "user-unknown-key":
        user_file("fame: 8\n")
        return []
    if kind == "missing-project":
        return ["--project", "absent"]
    if kind == "bad-project-name":
        return ["--project", "../look"]
    if kind == "project-unknown-key":
        project_file("fame: 8\n")
        return ["--project", "look"]
    if kind == "project-missing-palette":
        project_file("palette: absent.hex\n")
        return ["--project", "look"]
    if kind == "second-config":
        good = config(tmp_path, "fps: 8\n", "good.yaml")
        return ["--config", str(good), "--config", str(good)]
    if kind == "config-and-no-user-config":
        return ["--config", str(config(tmp_path, "fps: 8\n")), "--no-user-config"]
    texts = {
        "unknown-key": "fame: 8\n",
        "unknown-version": "version: 2\n",
        "wrong-type": "fps: fast\n",
        "out-of-range": "cell: 0x0\n",
        "repeated-key": "fps: 1\nfps: 2\n",
        "tag": "fps: !!int 0x0F\n",
        "long-integer": "fps: " + "9" * 5000 + "\n",
        "escape": 'palette: "\\U00110000"\n',
        "deep": "[" * 100_000,
        "not-utf8": "fps: \udcff\n",
        "missing-palette": "palette: absent.hex\n",
        "too-many-samples": "shade:\n  ao_samples: 129\n",
        "zero-distance": "shade:\n  ao_distance_m: 0\n",
        "negative-weight": "shade:\n  convexity_weight: -1\n",
        "inverted-range": "shade:\n  range: [191, 84]\n",
        "unknown-shade-key": "shade:\n  ao_quality: 3\n",
        "shade-not-a-mapping": "shade: 0.3\n",
        "nul-palette": 'palette: "bad\\0/p.hex"\n',
        "nul-materials": f'palette: {palette_file(tmp_path)}\nmaterials: "lib\\0/m.yaml"\n',
        "library-without-palette": "materials: lib.yaml\n",
    }
    path = tmp_path / "bad.yaml"
    text = texts[kind]
    path.write_bytes(text.encode("utf-8", "surrogateescape"))
    return ["--config", str(path)]


@pytest.mark.parametrize(
    "kind",
    [
        "missing-config",
        "user-unknown-key",
        "missing-project",
        "bad-project-name",
        "project-unknown-key",
        "project-missing-palette",
        "second-config",
        "config-and-no-user-config",
        "unknown-key",
        "unknown-version",
        "wrong-type",
        "out-of-range",
        "repeated-key",
        "tag",
        "long-integer",
        "escape",
        "deep",
        "not-utf8",
        "missing-palette",
        "too-many-samples",
        "zero-distance",
        "negative-weight",
        "inverted-range",
        "unknown-shade-key",
        "shade-not-a-mapping",
        "nul-palette",
        "nul-materials",
        "library-without-palette",
    ],
)
def test_every_settings_error_is_exit_2_before_any_blender_invocation(
    setup, capsys, monkeypatch, kind
):
    args = bad_settings(kind, setup.tmp_path)
    forbid_blender(monkeypatch)
    status, out, err = run(capsys, setup.argv(*args))
    assert status == 2, err
    assert out == ""
    assert err.splitlines()[0].startswith("usage:")
    assert setup.calls() == []
    assert not setup.png.exists()


def test_a_nul_in_a_settings_path_names_the_file_key_and_line(tmp_path, capsys):
    path = config(tmp_path, f'palette: {palette_file(tmp_path)}\nmaterials: "a\\0b"\n')
    assert refused(capsys, "--config", str(path)) == (
        f"--config {str(path)!r}: materials: expected a file path without a NUL "
        "character, got 'a\\x00b' at line 2, column 1"
    )


# Every path a settings file names: one validator, and every failure to read
# what it names, a located usage error before Blender.


def unusable(kind, directory, suffix):
    """A path, as a settings file in `directory` writes it, that cannot be
    read in way `kind`, and the problem the command reports for it."""
    name = "p" + suffix
    if kind == "missing":
        return name, "cannot be read: No such file or directory"
    if kind == "directory":
        (directory / name).mkdir()
        return name, "cannot be read: Is a directory"
    if kind == "no-permission":
        # The test makes reading this file fail with EACCES: file modes
        # cannot, for a user such as root that they do not bind.
        (directory / name).write_text("000000\n")
        return name, "cannot be read: Permission denied"
    if kind == "name-too-long":
        return "x" * 300 + suffix, "cannot be read: File name too long"
    if kind == "link-loop":
        (directory / name).symlink_to(directory / name)
        return name, "cannot be read: Too many levels of symbolic links"
    if kind == "nul":
        given = f'"bad\\0/{name}"'
        return given, "expected a file path without a NUL character"
    if kind == "surrogate":
        return (
            f'"bad\\uD800/{name}"',
            f"expected a file path the file system can name, got 'bad\\ud800/{name}': "
            "surrogates not allowed",
        )
    # A `~` prefix: the raw string is checked before it is expanded.
    if kind == "tilde-nul":
        return f'"~bad\\0/{name}"', "expected a file path without a NUL character"
    if kind == "tilde-surrogate":
        return (
            f'"~bad\\uD800/{name}"',
            f"expected a file path the file system can name, got '~bad\\ud800/{name}': "
            "surrogates not allowed",
        )
    if kind == "tilde-no-such-user":
        # Left unexpanded, so it names a file under the settings file's
        # directory, which does not exist.
        return f"~no-such-user-84/{name}", "cannot be read: No such file or directory"
    raise AssertionError(kind)


@pytest.mark.parametrize("where", ["config", "user", "project"])
@pytest.mark.parametrize("key", ["palette", "materials"])
@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "directory",
        "no-permission",
        "name-too-long",
        "link-loop",
        "nul",
        "surrogate",
        "tilde-nul",
        "tilde-surrogate",
        "tilde-no-such-user",
    ],
)
def test_every_unusable_settings_path_is_exit_2_naming_file_key_and_line(
    setup, capsys, monkeypatch, kind, key, where
):
    if where == "config":
        directory = setup.tmp_path / "conf"
        directory.mkdir()
    elif where == "project":
        directory = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros", "projects")
        directory.mkdir(parents=True)
    else:
        directory = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros")
        directory.mkdir(parents=True)
    written, problem = unusable(
        kind, directory, ".hex" if key == "palette" else ".yaml"
    )
    text = f"palette: {palette_file(setup.tmp_path)}\n" if key == "materials" else ""
    text += f"{key}: {written}\n"
    line = text.count("\n")
    if where == "config":
        path = config(directory, text)
        label, args = f"--config {str(path)!r}", ["--config", str(path)]
    elif where == "project":
        path = project_file(text)
        label, args = project_label(path), ["--project", "look"]
    else:
        path = user_file(text)
        label, args = f"the user settings {str(path)!r}", []
    if kind == "no-permission":
        locked = directory / written
        real = Path.read_bytes

        def read_bytes(self):
            if self == locked:
                raise PermissionError(
                    errno.EACCES, os.strerror(errno.EACCES), str(self)
                )
            return real(self)

        monkeypatch.setattr(Path, "read_bytes", read_bytes)
    forbid_blender(monkeypatch)
    status, out, err = run(capsys, setup.argv(*args))
    assert (status, out) == (2, "")
    message = err.splitlines()[-1]
    assert message.startswith(f"moskophoros: error: {label}: {key}")
    assert f"line {line}, column 1" in message
    assert problem in message
    assert setup.calls() == []
    assert not setup.png.exists()


# The shading values (settings design D-3, D-9, D-12, D-22, D-30, D-42)

SHADE_FIELDS = {
    "ao_distance_m": ("ao_distance", "--ao-distance", "1.5", 1.5),
    "ao_samples": ("ao_samples", "--ao-samples", "16", 16),
    "occlusion_weight": ("occlusion_weight", "--occlusion-weight", "0.75", 0.75),
    "convexity_weight": ("convexity_weight", "--convexity-weight", "0.25", 0.25),
    "range": ("shade_range", "--shade-range", "100,200", (100, 200)),
}
FILE_VALUES = {
    "ao_distance_m": ("0.9", 0.9),
    "ao_samples": ("8", 8),
    "occlusion_weight": ("0.6", 0.6),
    "convexity_weight": ("0.4", 0.4),
    "range": ("[90, 230]", (90, 230)),
}
# The shared sheet's recorded values (test_reuse.SETTINGS).
SHEET_VALUES = {
    "ao_distance_m": 1.2,
    "ao_samples": 32,
    "occlusion_weight": 0.5,
    "convexity_weight": 0.0,
    "range": (120, 188),
}


@pytest.mark.parametrize("key", SHADE_FIELDS)
def test_each_shading_value_follows_the_layers(tmp_path, key):
    field, option, text, given = SHADE_FIELDS[key]
    written, from_file = FILE_VALUES[key]
    default = getattr(resolved("--no-user-config"), field)
    user_file(f"shade:\n  {key}: {written}\n")
    assert getattr(resolved(), field) == from_file != default
    sheet = str(write_sheet(tmp_path))
    # The global file is only a default: a loaded sheet keeps its value.
    assert getattr(resolved("--settings-from", sheet), field) == SHEET_VALUES[key]
    path = config(tmp_path, f"shade:\n  {key}: {written}\n", "look.yaml")
    assert getattr(resolved("--config", str(path)), field) == from_file
    assert (
        getattr(resolved("--settings-from", sheet, "--config", str(path)), field)
        == SHEET_VALUES[key]
    )
    # A project value acts as the option would, over a loaded sheet too.
    project_file(f"shade:\n  {key}: {written}\n")
    assert getattr(resolved("--no-user-config", "--project", "look"), field) == (
        from_file
    )
    assert (
        getattr(resolved("--settings-from", sheet, "--project", "look"), field)
        == from_file
    )
    # An option beats every layer.
    assert getattr(resolved("--project", "look", option, text), field) == given
    assert (
        getattr(
            resolved("--settings-from", sheet, "--project", "look", option, text),
            field,
        )
        == given
    )


def test_one_shade_key_in_a_project_inherits_the_rest(tmp_path):
    user_file("shade:\n  ao_distance_m: 0.9\n  range: [90, 230]\n")
    project_file("shade:\n  convexity_weight: 0.5\n")
    options = resolved("--project", "look")
    assert (
        options.ao_distance,
        options.ao_samples,
        options.occlusion_weight,
        options.convexity_weight,
        options.shade_range,
    ) == (0.9, 64, 0.25, 0.5, (90, 230))
    over_sheet = resolved(
        "--settings-from", str(write_sheet(tmp_path)), "--project", "look"
    )
    assert (
        over_sheet.ao_distance,
        over_sheet.ao_samples,
        over_sheet.convexity_weight,
        over_sheet.shade_range,
    ) == (1.2, 32, 0.5, (120, 188))


def test_the_range_replaces_whole(tmp_path):
    user_file("shade:\n  range: [90, 230]\n")
    project_file("shade:\n  range: [10, 20]\n")
    assert resolved("--project", "look").shade_range == (10, 20)
    assert resolved("--shade-range", "30,40").shade_range == (30, 40)


@pytest.mark.parametrize(
    "args",
    [
        ("--ao-samples", "129"),
        ("--ao-samples", "1024"),
        ("--ao-distance", "0"),
        ("--occlusion-weight", "-0.5"),
        ("--shade-range", "191,84"),
    ],
)
def test_a_bad_shading_option_is_exit_2_before_any_blender_invocation(
    setup, capsys, monkeypatch, args
):
    forbid_blender(monkeypatch)
    status, out, err = run(capsys, setup.argv(*args))
    assert (status, out) == (2, "")
    assert f"argument {args[0]}: " in err
    assert setup.calls() == []


@pytest.mark.parametrize("where", ["config", "user", "project"])
def test_129_samples_from_a_file_is_exit_2_naming_file_key_line_and_limit(
    setup, capsys, monkeypatch, where
):
    text = "fps: 4\nshade:\n  ao_samples: 129\n"
    if where == "config":
        path = config(setup.tmp_path, text)
        label, args = f"--config {str(path)!r}", ["--config", str(path)]
    elif where == "project":
        path = project_file(text)
        label, args = project_label(path), ["--project", "look"]
    else:
        path = user_file(text)
        label, args = f"the user settings {str(path)!r}", []
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv(*args))
    assert status == 2
    assert err.splitlines()[-1] == (
        f"moskophoros: error: {label}: shade.ao_samples: expected a whole number "
        "from 1 to 128, the most Blender's ambient occlusion takes, got 129 at "
        "line 3, column 3"
    )
    assert setup.calls() == []


def test_the_jobs_carry_the_capture_values_and_the_sheet_records_all_five(
    setup, capsys, tmp_path
):
    work = setup.tmp_path / "work"
    path = config(
        tmp_path,
        "shade:\n  ao_distance_m: 1.2\n  ao_samples: 128\n  occlusion_weight: 0.5\n"
        "  convexity_weight: 0\n  range: [120, 188]\n",
    )
    status, _, err = run(
        capsys, setup.argv("--config", str(path), "--work-dir", str(work))
    )
    assert status == 0, err
    capture = {
        "ao_distance_m": 1.2,
        "ao_samples": 128,
        "occlusion_weight": 0.5,
        "convexity_weight": 0.0,
    }
    for mode in ("measure", "render"):
        job = json.loads((work / mode / "job.json").read_text())
        assert job["settings"]["shade"] == capture | {"materials": []}
    sheet = json.loads(setup.json.read_text())
    assert sheet["settings"]["shade"] == capture | {"range": [120, 188]}
    assert list(sheet["settings"])[-9:] == [
        "root_motion",
        "previews",
        "normals",
        "depth",
        "light",
        "shade",
        "ramp",
        "style",
        "clips",
    ]
    assert "shade_range" not in sheet["settings"]["style"]
    assert list(sheet["generator"]["shade"]) == [
        "technique",
        "samples_per_pixel",
        "seed",
        "pixel_filter",
        "filter_width_px",
    ]


def test_changing_only_the_range_leaves_the_capture_jobs_unchanged(setup, capsys):
    jobs = []
    for shade_range in ("84,191", "120,255"):
        work = setup.tmp_path / f"work-{shade_range}"
        argv = setup.argv("--shade-range", shade_range, "--work-dir", str(work))
        assert run(capsys, argv)[0] == 0
        jobs.append(
            {
                mode: (work / mode / "job.json").read_text().replace(str(work), "W")
                for mode in ("measure", "render")
            }
        )
    assert jobs[0] == jobs[1]


# Isolation from the owner's own user file


@pytest.fixture(scope="module")
def module_options():
    """Resolved once per module, as shared whole-command fixtures run."""
    return cli.resolve_settings(cli.parse_args(POSITIONALS))


def test_a_module_scoped_fixture_sees_no_user_settings(module_options):
    assert (module_options.fps, module_options.cell) == (12.0, None)
    assert module_options.previews is True


def test_a_populated_ambient_user_file_never_reaches_the_suite(tmp_path):
    """The suite isolates the user file before fixtures of any scope run: a
    run started with a user file in both places it is looked for still sees
    the shipped defaults in a module-scoped fixture."""
    for base in (tmp_path / "xdg", tmp_path / "home" / ".config"):
        (base / "moskophoros").mkdir(parents=True)
        (base / "moskophoros" / "config.yaml").write_text("fps: 6\ncell: 8x8\n")
    env = os.environ | {
        "XDG_CONFIG_HOME": str(tmp_path / "xdg"),
        "HOME": str(tmp_path / "home"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    test = f"{__file__}::test_a_module_scoped_fixture_sees_no_user_settings"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


# The clip selection over a loaded sheet (D-19, D-27)


def sheet_from_a_run(setup, capsys):
    """Run once (walk loops, attack is one-shot) and keep the sheet JSON."""
    assert run(capsys, setup.argv("--no-preview"))[0] == 0
    sheet = setup.tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    return sheet


def reload(setup, sheet, *options):
    return [
        "--settings-from",
        str(sheet),
        "--no-user-config",
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(setup.png),
    ]


def recorded_clips(setup):
    return json.loads(setup.json.read_text())["settings"]["clips"]


def test_neither_clip_nor_once_keeps_the_loaded_selection(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    before = recorded_clips(setup)
    assert before == [
        {"name": "walk", "loop": True, "frames": None},
        {"name": "attack", "loop": False, "frames": None},
    ]
    assert run(capsys, reload(setup, sheet))[0] == 0
    assert recorded_clips(setup) == before


def test_once_alone_replaces_the_loaded_marks(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    assert run(capsys, reload(setup, sheet, "--once", "walk"))[0] == 0
    assert recorded_clips(setup) == [
        {"name": "walk", "loop": False, "frames": None},
        {"name": "attack", "loop": True, "frames": None},
    ]


def test_once_naming_a_clip_outside_the_loaded_list_is_exit_2(
    setup, capsys, monkeypatch, tmp_path
):
    sheet = sheet_from_a_run(setup, capsys)
    # Narrow the loaded list to `walk`: `attack` exists in the model but not
    # in the list.
    document = json.loads(sheet.read_text())
    document["settings"]["clips"] = [{"name": "walk", "loop": True, "frames": None}]
    sheet.write_text(json.dumps(document))
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, reload(setup, sheet, "--once", "attack"))
    assert status == 2
    assert "'attack' is not among the loaded sheet's clips: 'walk'" in err


def test_clip_resets_the_loaded_selection(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    assert run(capsys, reload(setup, sheet, "--clip", "attack"))[0] == 0
    assert recorded_clips(setup) == [{"name": "attack", "loop": True, "frames": None}]


def test_a_recorded_clip_missing_from_the_model_is_exit_3(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    document = json.loads(sheet.read_text())
    document["settings"]["clips"].append({"name": "leap", "loop": True, "frames": None})
    sheet.write_text(json.dumps(document))
    status, _, err = run(capsys, reload(setup, sheet))
    assert status == 3
    assert "no clip is named 'leap'" in err
    # Replacing the selection drops the missing clip.
    assert run(capsys, reload(setup, sheet, "--clip", "walk"))[0] == 0


def test_an_older_sheet_is_exit_2_naming_its_schema_and_the_supported_one(
    setup, capsys, monkeypatch, tmp_path
):
    sheet = write_sheet(tmp_path, schema="moskophoros.sheet/3")
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, reload(setup, sheet))
    assert status == 2
    assert "moskophoros.sheet/3" in err and "moskophoros.sheet/14" in err


def test_a_reloaded_sheet_without_previews_writes_none(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    assert json.loads(sheet.read_text())["settings"]["previews"] is False
    for gif in (setup.walk_gif, setup.attack_gif):
        assert not gif.exists()
    assert run(capsys, reload(setup, sheet))[0] == 0
    assert not setup.walk_gif.exists() and not setup.attack_gif.exists()
    assert run(capsys, reload(setup, sheet, "--preview"))[0] == 0
    assert setup.walk_gif.exists() and setup.attack_gif.exists()


# The view, scale and framing, and the app settings (projects and camera
# design D-4, D-5, D-12, D-16)

VIEW = ("view", "direction", "directions", "start_angle")
P = views.pitch_direction
# Each new setting in a file, and the options that give the same values.
EQUIVALENTS = [
    ("view: side\n", ["--view", "side"]),
    ("view: topdown\npitch: 45\n", ["--view", "topdown", "--pitch", "45"]),
    ("pitch: 12.5\n", ["--pitch", "12.5"]),
    ("camera:\n  direction: [0, -1, -1]\n", ["--camera-direction", "0,-1,-1"]),
    (
        "view: side\ncamera:\n  direction: [0.5, -0.25, -1]\n",
        ["--view", "side", "--camera-direction", "0.5,-0.25,-1"],
    ),
    ("camera:\n  roll: -0.75\n", ["--camera-roll", "-0.75"]),
    ("camera:\n  position: [0, 2, 3.5]\n", ["--camera-position", "0,2,3.5"]),
    ("directions: 4\n", ["--directions", "4"]),
    ("start_angle: -45\n", ["--start-angle", "-45"]),
    ("model_yaw: -90\n", ["--model-yaw", "-90"]),
    ("ppm: 40\n", ["--ppm", "40"]),
    ("ppm: auto\n", ["--ppm", "auto"]),
    ("ground: [1, -2, 0.5]\n", ["--ground", "1,-2,0.5"]),
    ("ground_px: [8, 15]\n", ["--ground-px", "8,15"]),
    ("ground_px: [8.0, 15]\n", ["--ground-px", "8.0,15"]),
    ("ground_px: auto\n", ["--ground-px", "auto"]),
    ("supersample: 4\n", ["--supersample", "4"]),
    ("reduce: mode\n", ["--reduce", "mode"]),
    ("root_motion: keep\n", ["--root-motion", "keep"]),
    ("blender: /opt/blender/blender\n", ["--blender", "/opt/blender/blender"]),
    ("any_blender: true\n", ["--any-blender"]),
]
# What a file and options may differ in once resolved: where values came
# from, never what they are.
PROVENANCE = {"explicit", "origins", "preset", "config", "project", "no_user_config"}


def comparable(options):
    return {
        name: getattr(options, name)
        for name in cli.Options.__dataclass_fields__
        if name not in PROVENANCE
    }


@pytest.mark.parametrize("where", ["user", "config", "project"])
@pytest.mark.parametrize(("text", "option"), EQUIVALENTS)
def test_each_new_setting_in_a_file_resolves_as_its_option(
    tmp_path, where, text, option
):
    if where == "user":
        user_file(text)
        from_file = resolved()
    elif where == "config":
        from_file = resolved("--config", str(config(tmp_path, text)))
    else:
        project_file(text)
        from_file = resolved("--project", "look")
    from_option = resolved("--no-user-config", *option)
    assert comparable(from_file) == comparable(from_option)


@pytest.mark.parametrize("text", ["{}\n", "version: 1\n"])
def test_an_empty_file_and_the_default_command_resolve_as_today(text):
    default = resolved()
    user_file(text)
    project_file(text)
    assert comparable(resolved("--project", "look")) == comparable(default)
    today = cli.parse_args(POSITIONALS)
    assert comparable(default) == comparable(today)
    assert (
        default.view,
        default.direction,
        default.directions,
        default.start_angle,
    ) == ("iso", P(30.0), 8, 0.0)
    assert (default.roll, default.camera_position) == (0.0, None)


@pytest.mark.parametrize("preset", list(cli.PRESETS))
@pytest.mark.parametrize("where", ["user", "project"])
def test_each_preset_from_a_file_resolves_as_today(preset, where):
    (user_file if where == "user" else project_file)(f"view: {preset}\n")
    options = resolved(*(["--project", "look"] if where == "project" else []))
    today = cli.parse_args(["--view", preset, *POSITIONALS])
    assert [getattr(options, name) for name in VIEW] == [
        getattr(today, name) for name in VIEW
    ]
    assert options.view == preset


def test_a_layers_view_replaces_a_lower_layers_values():
    user_file("pitch: 45\ndirections: 4\nstart_angle: 10\n")
    project_file("view: side\n")
    options = resolved("--project", "look")
    assert [getattr(options, name) for name in VIEW] == ["side", P(0.0), 2, 90.0]
    project_file("pitch: 45\ndirections: 4\nstart_angle: 10\n")
    options = resolved("--project", "look", "--view", "topdown")
    assert [getattr(options, name) for name in VIEW] == ["topdown", P(90.0), 8, 0.0]


def test_a_layers_view_applies_before_its_own_values():
    user_file("view: topdown\npitch: null\n")
    options = resolved()
    assert [getattr(options, name) for name in VIEW] == ["topdown", P(90.0), 8, 0.0]
    # Key order in the file does not matter.
    user_file("pitch: 45\nview: iso\n")
    options = resolved()
    assert [getattr(options, name) for name in VIEW] == ["custom", P(45.0), 8, 0.0]


def test_a_lower_override_and_a_higher_null_give_the_presets_value():
    user_file("pitch: 45\ndirections: 4\n")
    project_file("pitch: null\n")
    options = resolved("--project", "look")
    # The higher null clears the pitch only; the direction count stays.
    assert [getattr(options, name) for name in VIEW] == ["custom", P(30.0), 4, 0.0]
    project_file("pitch: null\ndirections: null\n")
    options = resolved("--project", "look")
    assert [getattr(options, name) for name in VIEW] == ["iso", P(30.0), 8, 0.0]


def test_a_null_takes_the_value_of_the_preset_in_force():
    user_file("view: side\npitch: 45\n")
    project_file("pitch: null\n")
    options = resolved("--project", "look")
    assert [getattr(options, name) for name in VIEW] == ["side", P(0.0), 2, 90.0]


def test_an_option_override_over_a_files_view_makes_it_custom():
    project_file("view: topdown\n")
    options = resolved("--project", "look", "--directions", "4")
    assert [getattr(options, name) for name in VIEW] == ["custom", P(90.0), 4, 0.0]


def custom_sheet(tmp_path):
    from test_reuse import SETTINGS

    settings = json.loads(json.dumps(SETTINGS))
    settings["view"] = {
        "preset": "custom",
        "directions": 4,
        "start_angle_deg": 45.0,
    }
    settings["camera"]["direction"] = list(P(20.0))
    return write_sheet(tmp_path, settings)


def test_a_custom_sheet_with_a_higher_null_is_exit_2_naming_the_key(tmp_path, capsys):
    sheet = custom_sheet(tmp_path)
    path = project_file("fps: 8\ndirections: null\n")
    assert refused(capsys, "--settings-from", str(sheet), "--project", "look") == (
        f"{project_label(path)}: directions (line 2, column 1): null takes the "
        "view's preset value, but the loaded sheet's view is custom, with no "
        "preset; give a view in the same file"
    )


def test_a_custom_sheet_with_a_view_and_a_null_in_one_layer_gives_the_preset(
    tmp_path,
):
    sheet = custom_sheet(tmp_path)
    project_file("view: iso\ndirections: null\n")
    options = resolved("--settings-from", str(sheet), "--project", "look")
    assert [getattr(options, name) for name in VIEW] == ["iso", P(30.0), 8, 0.0]


def test_a_custom_sheet_keeps_its_marker_and_values_with_nothing_above(tmp_path):
    sheet = custom_sheet(tmp_path)
    # The global file sits below the loaded sheet, so its view never applies.
    user_file("view: topdown\npitch: null\n")
    options = resolved("--settings-from", str(sheet))
    assert [getattr(options, name) for name in VIEW] == ["custom", P(20.0), 4, 45.0]


def test_a_project_value_over_a_sheet_is_an_override(tmp_path):
    sheet = write_sheet(tmp_path)  # a side sheet
    project_file("directions: 4\n")
    options = resolved("--settings-from", str(sheet), "--project", "look")
    assert [getattr(options, name) for name in VIEW] == ["custom", P(0.0), 4, 90.0]
    project_file("directions: null\n")
    options = resolved("--settings-from", str(sheet), "--project", "look")
    assert [getattr(options, name) for name in VIEW] == ["side", P(0.0), 2, 90.0]


def test_an_iso_sheet_reloads_as_iso_with_its_json_and_fingerprint(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    before = sheet.read_bytes()
    assert json.loads(before)["settings"]["view"]["preset"] == "iso"
    # A global view sits below the loaded sheet and changes nothing.
    argv = reload(setup, sheet)
    argv.remove("--no-user-config")
    user_file("view: side\npitch: 45\nsupersample: 4\nppm: 3\n")
    assert run(capsys, argv)[0] == 0
    assert setup.json.read_bytes() == before


# The camera (projects and camera design D-3, D-7, D-12, D-14, D-16)


def generated_and_reloaded(setup, capsys, *options):
    """Run with `options`, then reload its sheet with nothing else; return
    both runs' complete output, every file's bytes by name."""
    status, _, err = run(capsys, setup.argv(*options))
    assert status == 0, err
    first = setup.listing()
    sheet = setup.tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    for path in setup.out.iterdir():
        path.unlink()
    status, _, err = run(capsys, reload(setup, sheet))
    assert status == 0, err
    return first, setup.listing()


def camera_record(setup):
    settings = json.loads(setup.json.read_text())["settings"]
    return settings["view"], settings["camera"]


@pytest.mark.parametrize(
    ("files", "options", "preset", "direction"),
    [
        # A named preset, and a custom view.
        ({}, ["--view", "topdown"], "topdown", P(90.0)),
        ({}, ["--pitch", "47.25", "--directions", "3"], "custom", P(47.25)),
        # A non-trivial normalised direction, a roll and an ignored position.
        (
            {},
            ["--camera-direction", "0.3,-0.7,-0.2"],
            "custom",
            views.normalise((0.3, -0.7, -0.2)),
        ),
        ({}, ["--camera-roll", "0.37"], "iso", P(30.0)),
        ({}, ["--camera-position", "0.5,-2,7"], "iso", P(30.0)),
        (
            {"project": "camera:\n  direction: [-1, 0.25, 1]\n  roll: -0.5\n"},
            [],
            "custom",
            views.normalise((-1, 0.25, 1)),
        ),
        # The cross-layer resets: a lower pitch with a higher null direction
        # under a named preset, and a higher null pitch over a lower
        # direction.
        (
            {
                "user": "view: side\npitch: 45\n",
                "project": "camera:\n  direction: null\n",
            },
            [],
            "side",
            P(0.0),
        ),
        (
            {"user": "camera:\n  direction: [1, -1, -1]\n", "project": "pitch: null\n"},
            [],
            "iso",
            P(30.0),
        ),
    ],
)
def test_a_14_sheet_reloads_to_equal_complete_output(
    setup, capsys, files, options, preset, direction
):
    if "user" in files:
        user_file(files["user"])
    if "project" in files:
        project_file(files["project"])
        options = [*options, "--project", "look"]
    first, again = generated_and_reloaded(setup, capsys, *options)
    assert again == first
    view, camera = camera_record(setup)
    assert view["preset"] == preset
    assert camera["projection"] == "orthographic"
    assert tuple(camera["direction"]) == direction
    assert "pitch_deg" not in view and "projection" not in view


def test_the_camera_record_holds_the_roll_and_the_unused_position(setup, capsys):
    argv = setup.argv("--camera-roll", "-0.25", "--camera-position", "0,1.5,-3")
    status, _, err = run(capsys, argv)
    # Orthographic records the position unused, with no warning (D-16).
    assert (status, err) == (0, "")
    assert camera_record(setup)[1] == {
        "projection": "orthographic",
        "direction": list(P(30.0)),
        "roll": -0.25,
        "position": [0.0, 1.5, -3.0],
    }


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        # Naive squared-length normalisation would underflow to 0.
        (["--camera-direction", "1e-300,1e-300,0"], (1e-300, 1e-300, 0.0)),
        # Repeated normalisation could move a component by one step.
        (["--camera-direction", "0.1,0.1,0.1"], (0.1, 0.1, 0.1)),
    ],
)
def test_a_numerically_sensitive_direction_reloads_unchanged(
    setup, capsys, given, expected
):
    status, _, err = run(capsys, setup.argv(*given))
    assert status == 0, err
    record = setup.json.read_bytes()
    direction = camera_record(setup)[1]["direction"]
    assert tuple(direction) == views.normalise(expected)
    assert all(component == pytest.approx(direction[0]) for component in direction[:2])
    for round in range(2):
        sheet = setup.tmp_path / f"round-{round}.json"
        sheet.write_bytes(setup.json.read_bytes())
        assert run(capsys, reload(setup, sheet))[0] == 0
        assert setup.json.read_bytes() == record


def pair_text(first, pitch, direction):
    pitch_line = f"pitch: {pitch}\n"
    direction_lines = f"camera:\n  direction: {direction}\n"
    if first == "pitch":
        return "fps: 4\n" + pitch_line + direction_lines, ("camera.direction", 4, 3)
    return "fps: 4\n" + direction_lines + pitch_line, ("pitch", 4, 1)


@pytest.mark.parametrize("where", ["user", "config", "project"])
@pytest.mark.parametrize("first", ["pitch", "camera.direction"])
@pytest.mark.parametrize(
    ("pitch", "direction"),
    [("45", "[0, -1, 0]"), ("45", "null"), ("null", "[0, -1, 0]"), ("null", "null")],
)
def test_pitch_and_a_direction_in_one_file_are_exit_2_and_write_nothing(
    setup, capsys, monkeypatch, where, first, pitch, direction
):
    text, (key, line, column) = pair_text(first, pitch, direction)
    if where == "user":
        path = user_file(text)
        label, argv = f"the user settings {str(path)!r}", []
    elif where == "config":
        path = config(setup.tmp_path, text)
        label, argv = f"--config {str(path)!r}", ["--config", str(path)]
    else:
        path = project_file(text)
        label, argv = project_label(path), ["--project", "look"]
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv(*argv))
    assert status == 2
    assert err.splitlines()[-1] == (
        f"moskophoros: error: {label}: {key}: pitch and camera.direction both set "
        f"the camera's direction; give only one of them at line {line}, column "
        f"{column}"
    )
    assert setup.listing() == {}


@pytest.mark.parametrize(
    "options",
    [
        ["--pitch", "45", "--camera-direction", "0,-1,0"],
        ["--camera-direction", "0,-1,0", "--pitch", "45"],
    ],
)
def test_pitch_and_a_direction_on_the_command_line_write_nothing(
    setup, capsys, monkeypatch, options
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv(*options))
    assert status == 2
    assert "--pitch and --camera-direction cannot be given together" in err
    assert setup.listing() == {}


def test_the_shipped_defaults_give_both_spellings_of_the_direction():
    # They set the view's starting state and are not an ordinary layer.
    shipped = settings_module.read_defaults()
    assert (shipped["pitch"], shipped["camera.direction"]) == (None, None)


@pytest.mark.parametrize(
    ("text", "key", "problem"),
    [
        (
            "camera:\n  direction: [0, 0, 0]\n",
            "camera.direction",
            "expected a direction, but [0, 0, 0] points nowhere",
        ),
        (
            "camera:\n  direction: [0, -1.5, 0]\n",
            "camera.direction",
            "expected [x, y, z], three finite numbers each from -1 to 1, not all 0, "
            "or null, got [0, -1.5, 0]",
        ),
        (
            "camera:\n  direction: [0, 1e400, -1]\n",
            "camera.direction",
            "expected [x, y, z], three finite numbers each from -1 to 1, not all 0, "
            "or null, got [0, inf, -1]",
        ),
        (
            "camera:\n  roll: 1.5\n",
            "camera.roll",
            "expected a finite number from -1 to 1, got 1.5",
        ),
        (
            "camera:\n  roll: 1e400\n",
            "camera.roll",
            "expected a finite number from -1 to 1, got inf",
        ),
        (
            "camera:\n  position: [0, 1, -1e400]\n",
            "camera.position",
            "expected [x, y, z], three finite numbers, or null, got [0, 1, -inf]",
        ),
        (
            "camera:\n  projection: orthographic\n",
            "camera.projection",
            "unknown key",
        ),
    ],
)
def test_a_bad_camera_setting_is_exit_2_naming_file_key_and_line(
    setup, capsys, monkeypatch, text, key, problem
):
    path = project_file("fps: 4\n" + text)
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--project", "look"))
    assert status == 2
    assert err.splitlines()[-1] == (
        f"moskophoros: error: {project_label(path)}: {key}: {problem} at line 3, "
        "column 3"
    )
    assert setup.listing() == {}


@pytest.mark.parametrize(
    ("given", "field"),
    [
        (("--ppm", "auto"), "ppm"),
        ("ppm: auto\n", "ppm"),
        (("--ground-px", "auto"), "ground_px"),
        ("ground_px: auto\n", "ground_px"),
    ],
)
def test_auto_drops_a_reused_value(tmp_path, given, field):
    sheet = write_sheet(tmp_path)
    assert getattr(resolved("--settings-from", str(sheet)), field) is not None
    if isinstance(given, str):
        project_file(given)
        given = ("--project", "look")
    options = resolved("--settings-from", str(sheet), *given)
    assert getattr(options, field) is None
    # Everything else stays reused, the cell included.
    assert options.cell == (48, 40)


@pytest.mark.parametrize(
    ("lower", "higher", "field"),
    [
        ("ppm: 40\n", "ppm: auto\n", "ppm"),
        ("ppm: 40\n", ("--ppm", "auto"), "ppm"),
        ("ground_px: [3, 4]\n", "ground_px: auto\n", "ground_px"),
        ("ground_px: [3, 4]\n", ("--ground-px", "auto"), "ground_px"),
    ],
)
def test_auto_drops_a_lower_layers_value(lower, higher, field):
    user_file(lower)
    assert getattr(resolved(), field) is not None
    if isinstance(higher, str):
        project_file(higher)
        higher = ("--project", "look")
    assert getattr(resolved(*higher), field) is None


def recorded(setup):
    return json.loads(setup.json.read_text())["settings"]


def test_ppm_auto_over_a_reused_scale_fits_automatically(setup, capsys):
    assert run(capsys, setup.argv("--no-preview"))[0] == 0
    fitted = recorded(setup)
    assert run(capsys, setup.argv("--no-preview", "--ppm", "5"))[0] == 0
    sheet = setup.tmp_path / "fixed.json"
    sheet.write_bytes(setup.json.read_bytes())
    assert recorded(setup)["pixels_per_meter"] == 5.0
    assert run(capsys, reload(setup, sheet, "--ppm", "auto"))[0] == 0
    again = recorded(setup)
    assert again["pixels_per_meter"] == fitted["pixels_per_meter"] != 5.0
    assert (again["cell"], again["ground_px"]) == (fitted["cell"], fitted["ground_px"])


def test_file_auto_values_over_lower_ones_fit_as_the_default_run(setup, capsys):
    assert run(capsys, setup.argv("--no-preview"))[0] == 0
    fitted = setup.json.read_bytes()
    user_file("ppm: 5\nground_px: [3, 3]\n")
    project_file("ppm: auto\nground_px: auto\n")
    argv = setup.argv("--no-preview", "--project", "look")
    assert run(capsys, argv)[0] == 0
    assert setup.json.read_bytes() == fitted


# The app settings: they layer, but no sheet records or loads them


def file_argv(setup, *options):
    """The run's arguments without `--blender`, so a file supplies it."""
    argv = setup.argv(*options)
    index = argv.index("--blender")
    del argv[index : index + 2]
    return argv


def old_blender(setup):
    """A Blender reporting an unsupported version, which renders as the fake
    does."""
    path = setup.tmp_path / "old" / "blender"
    path.parent.mkdir()
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Blender 4.5.0"; exit 0; fi\n'
        f'exec "{setup.fake}" "$@"\n'
    )
    path.chmod(0o755)
    return path


def test_blender_and_any_blender_from_a_file_take_effect_and_are_never_recorded(
    setup, capsys
):
    assert run(capsys, setup.argv())[0] == 0
    with_option = setup.listing()
    old = old_blender(setup)
    # The path is relative to the project file.
    path = project_file(f"blender: {os.path.relpath(old, setup.tmp_path)}\n")
    target = path.parent / os.path.relpath(old, setup.tmp_path)
    target.parent.mkdir(parents=True)
    shutil.copy(old, target)
    status, _, err = run(capsys, file_argv(setup, "--project", "look"))
    assert status == 5
    assert "4.5.0" in err and "--any-blender" in err
    project_file(
        f"blender: {os.path.relpath(old, setup.tmp_path)}\nany_blender: true\n"
    )
    calls = len(setup.calls())
    assert run(capsys, file_argv(setup, "--project", "look"))[0] == 0
    assert len(setup.calls()) == calls + 2
    # Same sheet, maps and previews, so the same JSON and fingerprint.
    assert setup.listing() == with_option
    text = setup.json.read_text()
    assert "any_blender" not in text and str(target) not in text


def test_global_app_settings_survive_loading_a_sheet(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    before = sheet.read_bytes()
    old = old_blender(setup)
    user_file(f"blender: {old}\nany_blender: true\n")
    argv = file_argv(setup)
    options = cli.resolve_settings(
        cli.parse_args(["--settings-from", str(sheet), *argv])
    )
    assert (options.blender, options.any_blender) == (old, True)
    assert run(capsys, ["--settings-from", str(sheet), *argv])[0] == 0
    assert setup.json.read_bytes() == before


def test_a_project_resets_the_global_app_settings(tmp_path):
    user_file("blender: /opt/blender\nany_blender: true\n")
    project_file("blender: null\nany_blender: false\n")
    sheet = write_sheet(tmp_path)
    for options in (
        resolved("--project", "look"),
        resolved("--project", "look", "--settings-from", str(sheet)),
    ):
        assert (options.blender, options.any_blender) == (None, False)


def test_options_beat_file_app_settings(tmp_path):
    project_file("blender: /opt/blender\nany_blender: false\n")
    options = resolved("--project", "look", "--blender", "b", "--any-blender")
    assert (options.blender, options.any_blender) == (Path("b"), True)


def test_a_file_blender_path_expands_a_leading_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    project_file("blender: ~/bin/blender\n")
    assert resolved("--project", "look").blender == tmp_path / "bin" / "blender"


def test_a_null_blender_discovers_it_as_today(setup, capsys, monkeypatch):
    user_file(f"blender: {setup.fake}\n")
    project_file("blender: null\n")
    monkeypatch.setenv("MOSKOPHOROS_BLENDER", str(setup.tmp_path / "absent"))
    status, _, err = run(capsys, file_argv(setup, "--project", "look"))
    assert status == 5
    assert "$MOSKOPHOROS_BLENDER names" in err


def test_an_unusable_file_blender_is_exit_5_naming_the_file(setup, capsys):
    absent = setup.tmp_path / "absent"
    path = project_file(f"fps: 4\nblender: {absent}\n")
    status, _, err = run(capsys, file_argv(setup, "--project", "look"))
    assert status == 5
    assert err == (
        f"moskophoros: error: {project_label(path)}: blender (line 2, column 1) "
        f"names {str(absent)!r}, which is not an executable file; no other "
        "Blender is tried\n"
    )


def test_an_overridden_file_blender_is_never_checked(setup, capsys):
    project_file(f"blender: {setup.tmp_path / 'absent'}\n")
    assert run(capsys, setup.argv("--project", "look"))[0] == 0


@pytest.mark.parametrize("where", ["user", "project"])
@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("view: front", "expected topdown, side, iso or iso-true, got 'front'"),
        ("pitch: 91", "expected a finite number from 0 to 90, or null, got 91"),
        ("ppm: 0", "expected a finite number greater than 0, or auto, got 0"),
        (
            "ground_px: [1.5, 0]",
            "expected [x, y], two whole numbers 0 or greater, or auto, got [1.5, 0]",
        ),
        ("supersample: 17", "expected a whole number from 1 to 16, got 17"),
        ("blender: 3", "expected a file path or null, got 3"),
        ("any_blender: 1", "expected true or false, got 1"),
    ],
)
def test_a_bad_new_setting_is_exit_2_naming_file_key_and_line(
    setup, capsys, monkeypatch, where, text, problem
):
    if where == "user":
        path = user_file(f"fps: 4\n{text}\n")
        label, argv = f"the user settings {str(path)!r}", []
    else:
        path = project_file(f"fps: 4\n{text}\n")
        label, argv = project_label(path), ["--project", "look"]
    forbid_blender(monkeypatch)
    argv = setup.argv(*argv)
    status, _, err = run(capsys, argv)
    assert status == 2
    key = text.split(":")[0]
    assert err.splitlines()[-1] == (
        f"moskophoros: error: {label}: {key}: {problem} at line 2, column 1"
    )
