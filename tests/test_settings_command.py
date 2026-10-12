"""Settings layers in the command: the shipped defaults, the user file, a
loaded sheet, `--config` files and options (settings design D-2, D-8, D-15,
D-16, D-17, D-19, D-22, D-27, D-28 and D-32), with a controlled fake
Blender.

The suite's `no_owner_settings` fixture points `$XDG_CONFIG_HOME` and `$HOME`
at empty temporary directories, so a user file exists only where a test
writes one."""

import errno
import json
import os
import subprocess
import sys
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

from moskophoros import cli

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
    path = user_file("fps: 6\nframes: 8\n")
    assert refused(capsys) == (
        f"the user settings {str(path)!r}: frames: unknown key at line 2, column 1"
    )


def test_the_user_file_is_never_written(tmp_path):
    path = user_file("fps: 6\n")
    before = path.read_bytes(), path.stat().st_mtime_ns
    resolved()
    resolved("--fps", "9")
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


# `--config` files


def test_a_config_file_applies(tmp_path):
    path = config(tmp_path, "version: 1\nfps: 8\ncell: 32x30\n")
    options = resolved("--config", str(path))
    assert (options.fps, options.cell) == (8.0, (32, 30))
    assert {"fps", "cell"} <= options.explicit


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


def test_later_config_files_win_and_omitted_keys_fall_through(tmp_path):
    first = config(tmp_path, "fps: 8\ncell: 48x48\n", "first.yaml")
    second = config(tmp_path, "fps: 9\n", "second.yaml")
    options = resolved("--config", str(first), "--config", str(second))
    assert (options.fps, options.cell) == (9.0, (48, 48))
    options = resolved("--config", str(second), "--config", str(first))
    assert options.fps == 8.0


def test_every_config_file_is_checked_even_when_a_later_one_overrides_it(
    tmp_path, capsys
):
    bad = config(tmp_path, "fps: 0\n", "bad.yaml")
    good = config(tmp_path, "fps: 9\n", "good.yaml")
    assert refused(capsys, "--config", str(bad), "--config", str(good)) == (
        f"--config {str(bad)!r}: fps: expected a finite number greater than 0, "
        "got 0 at line 1, column 1"
    )


# Precedence, pair by pair


def test_the_user_file_is_above_the_defaults():
    user_file("fps: 6\n")
    assert resolved().fps == 6.0


def test_a_config_file_is_above_the_user_file(tmp_path):
    user_file("fps: 6\ncell: 40x40\n")
    options = resolved("--config", str(config(tmp_path, "fps: 8\n")))
    assert (options.fps, options.cell) == (8.0, (40, 40))


def test_an_option_is_above_a_config_file(tmp_path):
    path = config(tmp_path, "fps: 8\ncell: 48x48\npreviews: false\n")
    options = resolved("--config", str(path), "--fps", "10", "--preview")
    assert (options.fps, options.cell, options.previews) == (10.0, (48, 48), True)


def test_a_loaded_sheet_is_above_the_user_file(tmp_path):
    user_file("fps: 6\ncell: 32x32\npreviews: true\n")
    options = resolved("--settings-from", str(write_sheet(tmp_path)))
    assert (options.fps, options.cell, options.previews) == (24.0, (48, 40), False)


def test_a_config_file_is_above_a_loaded_sheet(tmp_path):
    path = config(tmp_path, "fps: 8\ncell: 32x30\npreviews: true\n")
    options = resolved(
        "--settings-from", str(write_sheet(tmp_path)), "--config", str(path)
    )
    assert (options.fps, options.cell, options.previews) == (8.0, (32, 30), True)
    # As --cell after --settings-from: the reused scale and ground pixel stay,
    # so both are fixed.
    assert (options.ppm, options.ground_px) == (32.0, (24, 37))


def test_an_option_is_above_a_loaded_sheet_and_a_config_file(tmp_path):
    path = config(tmp_path, "fps: 8\n")
    options = resolved(
        "--settings-from",
        str(write_sheet(tmp_path)),
        "--config",
        str(path),
        "--fps",
        "5",
    )
    assert options.fps == 5.0


# `auto` and `null` at each layer


@pytest.mark.parametrize("layer", ["user", "config", "option"])
def test_cell_auto_at_each_layer_returns_to_the_automatic_cell(tmp_path, layer):
    user_file("cell: 48x48\n" if layer != "user" else "cell: auto\n")
    args = []
    if layer == "config":
        args = ["--config", str(config(tmp_path, "cell: auto\n"))]
    elif layer == "option":
        args = ["--cell", "auto"]
    assert resolved(*args).cell is None


@pytest.mark.parametrize("how", [("--cell", "auto"), "config"])
def test_cell_auto_over_a_loaded_sheet_fits_with_the_reused_scale(tmp_path, how):
    args = (
        ["--config", str(config(tmp_path, "cell: auto\n"))]
        if how == "config"
        else list(how)
    )
    options = resolved("--settings-from", str(write_sheet(tmp_path)), *args)
    assert (options.cell, options.ppm) == (None, 32.0)


def test_the_defaults_never_turn_ppm_sizing_into_a_fixed_cell():
    options = resolved("--ppm", "20")
    assert (options.ppm, options.cell) == (20.0, None)


@pytest.mark.parametrize("layer", ["user", "config"])
def test_a_null_palette_and_library_at_a_layer_mean_none(tmp_path, layer):
    # The user file below names files that do not exist: they are never read.
    user_file("palette: missing.hex\nmaterials: missing.yaml\n")
    args = []
    if layer == "config":
        args = ["--config", str(config(tmp_path, "palette: null\nmaterials: null\n"))]
    else:
        user_file("palette: null\nmaterials: null\n")
    options = resolved(*args)
    assert (options.palette, options.materials) == (None, None)


def test_an_overridden_user_path_that_no_longer_exists_is_never_read(tmp_path):
    user_file("palette: gone.hex\nmaterials: gone.yaml\n")
    palette = palette_file(tmp_path)
    options = resolved("--palette", str(palette), "--no-materials")
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


# Palette and library from a `--config` over a loaded sheet (the reuse table)


def test_a_reused_library_stays_with_a_config_palette_of_the_same_colours(tmp_path):
    same = palette_file(tmp_path, name="same.hex")
    path = config(tmp_path, f"palette: {same}\n")
    options = resolved(
        "--settings-from", str(style_sheet(tmp_path)), "--config", str(path)
    )
    assert options.palette.source == "same.hex"
    assert options.materials.source == GOOD_RECORD["source"]


def test_a_config_palette_of_other_colours_beside_a_reused_library_is_refused(
    tmp_path, capsys
):
    other = palette_file(tmp_path, COLORS[::-1], name="other.hex")
    path = config(tmp_path, f"palette: {other}\n")
    message = refused(
        capsys, "--settings-from", str(style_sheet(tmp_path)), "--config", str(path)
    )
    assert message.startswith(
        f"--config {str(path)!r}: palette (line 1, column 1) {str(other)!r}: "
    )
    assert "its colours differ from the reused palette" in message


def test_a_config_null_palette_beside_a_reused_library_is_refused(tmp_path, capsys):
    path = config(tmp_path, "palette: null\n")
    message = refused(
        capsys, "--settings-from", str(style_sheet(tmp_path)), "--config", str(path)
    )
    assert message == (
        f"--config {str(path)!r}: palette (line 1, column 1): the reused material "
        "library needs a palette; also give --no-materials to drop it"
    )


def test_a_config_null_library_drops_the_reused_one(tmp_path):
    path = config(tmp_path, "palette: null\nmaterials: null\n")
    options = resolved(
        "--settings-from", str(style_sheet(tmp_path)), "--config", str(path)
    )
    assert (options.palette, options.materials) == (None, None)


def test_a_config_library_replaces_the_reused_one_on_the_reused_palette(tmp_path):
    path = config(tmp_path, f"materials: {library_file(tmp_path, name='mine.yaml')}\n")
    options = resolved(
        "--settings-from", str(style_sheet(tmp_path)), "--config", str(path)
    )
    assert options.materials.source == "mine.yaml"
    assert options.palette.source == PALETTE_RECORD["source"]


def test_the_user_files_palette_and_library_never_change_a_loaded_sheet(tmp_path):
    user_file("palette: gone.hex\nmaterials: gone.yaml\n")
    options = resolved("--settings-from", str(style_sheet(tmp_path)))
    assert options.palette.source == PALETTE_RECORD["source"]
    assert options.materials.source == GOOD_RECORD["source"]


def test_an_option_beats_a_config_palette_over_a_loaded_sheet(tmp_path):
    other = palette_file(tmp_path, COLORS[::-1], name="other.hex")
    path = config(tmp_path, f"palette: {other}\n")
    options = resolved(
        "--settings-from",
        str(style_sheet(tmp_path)),
        "--config",
        str(path),
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
    assert sorted(setup.listing()) == ["hero.json", "hero.png"]
    assert json.loads(setup.json.read_text())["settings"]["previews"] is False


# Every settings error before any Blender invocation


def bad_settings(kind, tmp_path):
    """The arguments of a run whose settings are bad in way `kind`."""
    if kind == "missing-config":
        return ["--config", str(tmp_path / "absent.yaml")]
    if kind == "user-unknown-key":
        user_file("frames: 8\n")
        return []
    texts = {
        "unknown-key": "clips: {}\n",
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


@pytest.mark.parametrize("where", ["config", "user"])
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
    # The user file is only a default: a loaded sheet keeps its value.
    assert getattr(resolved("--settings-from", sheet), field) == SHEET_VALUES[key]
    path = config(tmp_path, f"shade:\n  {key}: {written}\n", "look.yaml")
    # A --config value acts as the option would, over a loaded sheet too.
    assert getattr(resolved("--config", str(path)), field) == from_file
    assert (
        getattr(resolved("--settings-from", sheet, "--config", str(path)), field)
        == from_file
    )
    # An option beats every layer.
    assert getattr(resolved("--config", str(path), option, text), field) == given
    assert (
        getattr(
            resolved("--settings-from", sheet, "--config", str(path), option, text),
            field,
        )
        == given
    )


def test_one_shade_key_in_a_config_inherits_the_rest(tmp_path):
    user_file("shade:\n  ao_distance_m: 0.9\n  range: [90, 230]\n")
    path = config(tmp_path, "shade:\n  convexity_weight: 0.5\n")
    options = resolved("--config", str(path))
    assert (
        options.ao_distance,
        options.ao_samples,
        options.occlusion_weight,
        options.convexity_weight,
        options.shade_range,
    ) == (0.9, 64, 0.25, 0.5, (90, 230))
    over_sheet = resolved(
        "--settings-from", str(write_sheet(tmp_path)), "--config", str(path)
    )
    assert (
        over_sheet.ao_distance,
        over_sheet.ao_samples,
        over_sheet.convexity_weight,
        over_sheet.shade_range,
    ) == (1.2, 32, 0.5, (120, 188))


def test_the_range_replaces_whole(tmp_path):
    user_file("shade:\n  range: [90, 230]\n")
    path = config(tmp_path, "shade:\n  range: [10, 20]\n")
    assert resolved("--config", str(path)).shade_range == (10, 20)
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


@pytest.mark.parametrize("where", ["config", "user"])
def test_129_samples_from_a_file_is_exit_2_naming_file_key_line_and_limit(
    setup, capsys, monkeypatch, where
):
    text = "fps: 4\nshade:\n  ao_samples: 129\n"
    if where == "config":
        path = config(setup.tmp_path, text)
        label, args = f"--config {str(path)!r}", ["--config", str(path)]
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
        assert job["settings"]["shade"] == capture
    sheet = json.loads(setup.json.read_text())
    assert sheet["settings"]["shade"] == capture | {"range": [120, 188]}
    assert list(sheet["settings"])[-5:] == [
        "root_motion",
        "previews",
        "shade",
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
    assert before == [{"name": "walk", "loop": True}, {"name": "attack", "loop": False}]
    assert run(capsys, reload(setup, sheet))[0] == 0
    assert recorded_clips(setup) == before


def test_once_alone_replaces_the_loaded_marks(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    assert run(capsys, reload(setup, sheet, "--once", "walk"))[0] == 0
    assert recorded_clips(setup) == [
        {"name": "walk", "loop": False},
        {"name": "attack", "loop": True},
    ]


def test_once_naming_a_clip_outside_the_loaded_list_is_exit_2(
    setup, capsys, monkeypatch, tmp_path
):
    sheet = sheet_from_a_run(setup, capsys)
    # Narrow the loaded list to `walk`: `attack` exists in the model but not
    # in the list.
    document = json.loads(sheet.read_text())
    document["settings"]["clips"] = [{"name": "walk", "loop": True}]
    sheet.write_text(json.dumps(document))
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, reload(setup, sheet, "--once", "attack"))
    assert status == 2
    assert "'attack' is not among the loaded sheet's clips: 'walk'" in err


def test_clip_resets_the_loaded_selection(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    assert run(capsys, reload(setup, sheet, "--clip", "attack"))[0] == 0
    assert recorded_clips(setup) == [{"name": "attack", "loop": True}]


def test_a_recorded_clip_missing_from_the_model_is_exit_3(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    document = json.loads(sheet.read_text())
    document["settings"]["clips"].append({"name": "leap", "loop": True})
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
    assert "moskophoros.sheet/3" in err and "moskophoros.sheet/5" in err


def test_a_reloaded_sheet_without_previews_writes_none(setup, capsys):
    sheet = sheet_from_a_run(setup, capsys)
    assert json.loads(sheet.read_text())["settings"]["previews"] is False
    for gif in (setup.walk_gif, setup.attack_gif):
        assert not gif.exists()
    assert run(capsys, reload(setup, sheet))[0] == 0
    assert not setup.walk_gif.exists() and not setup.attack_gif.exists()
    assert run(capsys, reload(setup, sheet, "--preview"))[0] == 0
    assert setup.walk_gif.exists() and setup.attack_gif.exists()
