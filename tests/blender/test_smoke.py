"""The Blender smoke test: Blender runs headless on this machine.

`bpy` is imported only inside the Blender process, never by pytest, so this
module collects and deselects without Blender.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

MACOS_APP = Path("/Applications/Blender.app/Contents/MacOS/Blender")
TIMEOUT_SECONDS = 120
SENTINEL = "moskophoros-smoke: bpy imported in background mode"
EXPRESSION = f"""\
import bpy
if not bpy.app.background:
    raise RuntimeError("Blender is not running in background mode")
print({SENTINEL!r})
"""


class BlenderNotFound(Exception):
    pass


def _is_executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def find_blender(environ=os.environ, platform=sys.platform, macos_app=MACOS_APP):
    """Find Blender in design §Capture's order, without `--blender`.

    A non-empty `$MOSKOPHOROS_BLENDER` is used as given: if it is not an
    executable file, discovery fails rather than falling back. The result is
    absolute, so it still names Blender after the test changes directory.
    """
    override = environ.get("MOSKOPHOROS_BLENDER", "")
    if override:
        if _is_executable(override):
            return os.path.abspath(override)
        raise BlenderNotFound(
            f"$MOSKOPHOROS_BLENDER is {override!r}, which is not an executable "
            "file. It is used without falling back to PATH or the macOS "
            "application."
        )
    search_path = environ.get("PATH", os.defpath)
    found = shutil.which("blender", path=search_path)
    if found:
        return os.path.abspath(found)
    looked = [
        "$MOSKOPHOROS_BLENDER (unset or empty)",
        f"`blender` on PATH ({search_path})",
    ]
    if platform == "darwin":
        if _is_executable(macos_app):
            return os.path.abspath(macos_app)
        looked.append(str(macos_app))
    else:
        looked.append(f"{macos_app} (not checked: not macOS)")
    raise BlenderNotFound(
        "Blender was not found. Looked in: " + "; ".join(looked) + "."
    )


def _text(output):
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output or ""


def _diagnostics(stdout, stderr):
    return f"stdout:\n{_text(stdout)}\nstderr:\n{_text(stderr)}"


def _smoke_failure(cwd):
    """Run the expression in headless Blender; return why it failed, or None."""
    try:
        blender = find_blender()
    except BlenderNotFound as error:
        return str(error)
    command = [
        blender,
        "-b",
        "--factory-startup",
        "-noaudio",
        "--python-exit-code",
        "1",
        "--python-expr",
        EXPRESSION,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except OSError as error:
        return f"Could not start Blender at {blender}: {error}"
    except subprocess.TimeoutExpired as error:
        return (
            f"Blender at {blender} did not finish within {TIMEOUT_SECONDS} s.\n"
            + _diagnostics(error.stdout, error.stderr)
        )
    if result.returncode != 0:
        return f"Blender at {blender} exited with status {result.returncode}.\n" + (
            _diagnostics(result.stdout, result.stderr)
        )
    if SENTINEL not in result.stdout.splitlines():
        return (
            f"Blender at {blender} did not report importing bpy in background "
            "mode.\n" + _diagnostics(result.stdout, result.stderr)
        )
    return None


@pytest.mark.blender
def test_blender_runs_headless(tmp_path):
    failure = _smoke_failure(tmp_path)
    if failure:
        pytest.fail(failure, pytrace=False)


def _executable(path):
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_an_invalid_override_fails_without_falling_back(tmp_path):
    _executable(tmp_path / "blender")
    app = _executable(tmp_path / "Blender")
    environ = {"MOSKOPHOROS_BLENDER": "/nonexistent", "PATH": str(tmp_path)}
    with pytest.raises(BlenderNotFound, match="'/nonexistent'"):
        find_blender(environ, "darwin", app)


def test_discovery_order_is_override_then_path_then_macos_app(tmp_path):
    override = _executable(tmp_path / "override")
    on_path = _executable(tmp_path / "blender")
    app = _executable(tmp_path / "Blender")
    path = str(tmp_path)
    assert find_blender(
        {"MOSKOPHOROS_BLENDER": str(override), "PATH": path}, "darwin", app
    ) == str(override)
    assert find_blender(
        {"MOSKOPHOROS_BLENDER": "", "PATH": path}, "darwin", app
    ) == str(on_path)
    assert find_blender({"PATH": str(tmp_path / "empty")}, "darwin", app) == str(app)


def test_finding_nothing_names_every_place_looked(tmp_path):
    empty = str(tmp_path)
    app = tmp_path / "Blender"
    with pytest.raises(BlenderNotFound) as raised:
        find_blender({"PATH": empty}, "darwin", app)
    message = str(raised.value)
    assert "$MOSKOPHOROS_BLENDER" in message
    assert f"PATH ({empty})" in message
    assert str(app) in message


def test_the_macos_app_is_not_used_elsewhere(tmp_path):
    app = _executable(tmp_path / "Blender")
    with pytest.raises(BlenderNotFound, match="not checked: not macOS"):
        find_blender({"PATH": str(tmp_path / "empty")}, "linux", app)


def test_a_relative_blender_is_made_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    blender = _executable(tmp_path / "blender")
    app = tmp_path / "Blender"
    assert find_blender({"MOSKOPHOROS_BLENDER": "./blender"}, "darwin", app) == str(
        blender
    )
    assert find_blender({"PATH": "."}, "darwin", app) == str(blender)
