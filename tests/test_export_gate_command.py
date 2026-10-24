"""No settings file can switch on an export setting that is not available yet
(export design P-13, EXP-2): the command refuses it with exit 2 before
Blender, naming the file, the key and where, whatever the value."""

import os
from pathlib import Path

import pytest
from test_command import Setup, run
from test_materials_command import forbid_blender
from test_settings_command import project_file, project_label

# Each file text sets one inactive key, at the given line and column: the
# internal defaults, values the key accepts, values it refuses, and entries
# for clips the model lacks.
INACTIVE = [
    ("stored_directions: all\n", "stored_directions", "1, column 1"),
    ("stored_directions: [0, 4]\n", "stored_directions", "1, column 1"),
    ("stored_directions: []\n", "stored_directions", "1, column 1"),
    ("direction_names: {}\n", "direction_names", "1, column 1"),
    ("direction_names: {1: right}\n", "direction_names", "1, column 1"),
    ("mirrors: {}\n", "mirrors", "1, column 1"),
    ("mirrors: {7: 1}\n", "mirrors", "1, column 1"),
    ("export: {}\n", "export", "1, column 1"),
    ("export: null\n", "export", "1, column 1"),
    ("export: 3\n", "export", "1, column 1"),
    ("export: [sheet]\n", "export", "1, column 1"),
    ("export:\n  formats: [sheet]\n", "export", "1, column 1"),
    ("export:\n  formats: [frames]\n", "export", "1, column 1"),
    ("export:\n  atlas_padding: 0\n", "export", "1, column 1"),
    ("export:\n  frame_path: x.png\n", "export", "1, column 1"),
    ("clips:\n  walk: {fps: null}\n", "clips.walk.fps", "2, column 10"),
    ("clips:\n  walk: {fps: 12}\n", "clips.walk.fps", "2, column 10"),
    ("clips:\n  walk: {fps: 6}\n", "clips.walk.fps", "2, column 10"),
    (
        "clips:\n  walk: {stored_directions: null}\n",
        "clips.walk.stored_directions",
        "2, column 10",
    ),
    (
        "clips:\n  walk: {stored_directions: all}\n",
        "clips.walk.stored_directions",
        "2, column 10",
    ),
    ("clips:\n  walk: {mirrors: {}}\n", "clips.walk.mirrors", "2, column 10"),
    ("clips:\n  walk: {output_name: null}\n", "clips.walk.output_name", "2, column 10"),
    (
        "clips:\n  walk: {output_name: stride}\n",
        "clips.walk.output_name",
        "2, column 10",
    ),
    # An entry for a clip that is not selected, or that the model lacks.
    ("clips:\n  leap: {fps: 6}\n", "clips.leap.fps", "2, column 10"),
    ("clips:\n  attack: {mirrors: {}}\n", "clips.attack.mirrors", "2, column 12"),
    # A usable leaf before an inactive one does not make it pass.
    ("clips:\n  walk:\n    frames: 4\n    fps: 6\n", "clips.walk.fps", "4, column 5"),
]


CLIPS = ("--clip", "walk", "--clip", "attack")


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def config(setup, text):
    path = setup.tmp_path / "export.yaml"
    path.write_text(text)
    return path


def user_file(text):
    path = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros", "config.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def assert_refused(setup, capsys, label, key, where):
    status, out, err = run(capsys, setup.argv(*CLIPS))
    assert status == 2, err
    assert out == ""
    assert f"{label}: {key}: not available yet at line {where}" in err
    assert setup.calls() == []
    assert setup.listing() == {}


@pytest.mark.parametrize(("text", "key", "where"), INACTIVE)
def test_a_config_file_cannot_set_an_inactive_key(
    setup, capsys, monkeypatch, text, key, where
):
    path = config(setup, text)
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv(*CLIPS, "--config", str(path)))
    assert status == 2, err
    assert f"--config {str(path)!r}: {key}: not available yet at line {where}" in err
    assert setup.calls() == []
    assert setup.listing() == {}


@pytest.mark.parametrize(("text", "key", "where"), INACTIVE)
def test_the_user_file_cannot_set_an_inactive_key(
    setup, capsys, monkeypatch, text, key, where
):
    path = user_file(text)
    forbid_blender(monkeypatch)
    assert_refused(setup, capsys, f"the user settings {str(path)!r}", key, where)


@pytest.mark.parametrize(("text", "key", "where"), INACTIVE)
def test_a_project_file_cannot_set_an_inactive_key(
    setup, capsys, monkeypatch, text, key, where
):
    path = project_file(text)
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv(*CLIPS, "--project", "look"))
    assert status == 2, err
    assert f"{project_label(path)}: {key}: not available yet at line {where}" in err
    assert setup.calls() == []
    assert setup.listing() == {}


def test_a_still_unknown_key_keeps_its_own_refusal(setup, capsys, monkeypatch):
    forbid_blender(monkeypatch)
    for text, problem in [
        ("formats: [sheet]\n", "formats: unknown key"),
        ("clips:\n  walk: {speed: 2}\n", "clips.walk.speed: unknown key"),
    ]:
        path = config(setup, text)
        status, _, err = run(capsys, setup.argv("--config", str(path)))
        assert status == 2
        assert f"--config {str(path)!r}: {problem} at line " in err
    assert setup.calls() == []


def test_an_empty_clip_entry_and_a_count_stay_accepted(setup, capsys):
    path = config(setup, "clips:\n  walk: {}\n  attack: {frames: 2}\n")
    status, _, err = run(capsys, setup.argv("--config", str(path), "--no-preview"))
    assert status == 0, err
    assert setup.png.exists()


def test_no_option_for_the_inactive_settings_exists(setup, capsys, monkeypatch):
    forbid_blender(monkeypatch)
    for flag in ("--formats", "--output-dir"):
        status, _, err = run(capsys, setup.argv(flag, "sheet"))
        assert status == 2
        assert f"moskophoros: error: unrecognized option: {flag}\n" in err
    assert setup.calls() == []
