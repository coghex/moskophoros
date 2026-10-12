"""Layered settings: the schema table, settings files and their merge
(settings design D-2, D-5, D-8, D-17, D-22 and D-30).

A settings file is a YAML mapping read by `yamlfile`, with an optional
`version: 1` and any of the settings in `SCHEMA`. Reading one gives a layer:
a partial mapping from setting names to checked values, with each path
resolved against the file's directory. `merge` lays layers over each other,
later layers winning key by key; a key a layer leaves out falls through.

The schema table is the one place a setting's type, unit, default and
validation rule are kept; the packaged `defaults.yaml` gives every setting
its shipped default and agrees with it. Everything here is pure except
`read_file` and `read_defaults`, which read the one file they name. Which
layers apply, and how they meet a loaded sheet and the command line, is the
command's business (`cli.resolve_settings`).
"""

import math
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType

from moskophoros import yamlfile

VERSION = 1
DEFAULTS_FILE = "defaults.yaml"
# The user file, under `$XDG_CONFIG_HOME` or `~/.config`.
USER_FILE = Path("moskophoros", "config.yaml")
AUTO = "auto"
MAX_CELL_SIDE = 4096


class SettingsError(Exception):
    """Bad settings input. `source` names the file, and `problem` reads after
    it."""

    def __init__(self, source, problem):
        self.source = source
        self.problem = problem
        super().__init__(f"{source}: {problem}")


class _Bad(Exception):
    """A value its setting refuses; `problem` reads after the key path."""

    def __init__(self, problem):
        self.problem = problem


@dataclass(frozen=True)
class Setting:
    """One setting: what it holds, its unit, its default as a file gives it,
    and `check`, which turns a file's value into the command's or raises
    `_Bad`. A `path` setting's string is resolved against its file."""

    kind: str
    unit: str | None
    default: object
    check: object
    path: bool = False


def _shown(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    return str(value)


def parse_cell(text):
    """`WxH` text as `(W, H)`, each side an integer from 1 to 4096 as `int`
    reads it, or None when it is not one. `--cell` reads its value the same
    way."""
    parts = text.split("x")
    if len(parts) != 2:
        return None
    try:
        width, height = (int(part) for part in parts)
    except ValueError:
        return None
    if 1 <= width <= MAX_CELL_SIDE and 1 <= height <= MAX_CELL_SIDE:
        return width, height
    return None


def _check_cell(value):
    """`auto` as None, or `WxH` as `(W, H)`."""
    if value == AUTO:
        return None
    cell = parse_cell(value) if isinstance(value, str) else None
    if cell is None:
        raise _Bad(
            f"expected WxH, two integers each from 1 to {MAX_CELL_SIDE}, or "
            f"{AUTO}, got {_shown(value)}"
        )
    return cell


def _check_fps(value):
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _Bad(f"expected a number greater than 0, got {_shown(value)}")
    try:
        number = float(value)
    except OverflowError:
        number = math.inf
    if not math.isfinite(number) or number <= 0:
        raise _Bad(f"expected a finite number greater than 0, got {_shown(value)}")
    return number


def _check_path(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _Bad(f"expected a file path or null, got {_shown(value)}")
    return value


def _check_previews(value):
    if not isinstance(value, bool):
        raise _Bad(f"expected true or false, got {_shown(value)}")
    return value


SCHEMA = MappingProxyType(
    {
        "cell": Setting(
            "the cell size in pixels, WxH with each side 1 to 4096, or auto: "
            "fitted with the pixels per meter in force, else 64x64",
            "pixels",
            AUTO,
            _check_cell,
        ),
        "fps": Setting(
            "the target sampling rate, greater than 0",
            "frames per second",
            12,
            _check_fps,
        ),
        "palette": Setting(
            "a .hex, .gpl or .png palette file, or null for none",
            None,
            None,
            _check_path,
            path=True,
        ),
        "materials": Setting(
            "a .yaml or .yml material library, or null for none; needs a palette",
            None,
            None,
            _check_path,
            path=True,
        ),
        "previews": Setting(
            "whether the animated previews are written", None, True, _check_previews
        ),
    }
)
# Each setting's default, as the command holds it.
DEFAULTS = MappingProxyType(
    {name: setting.check(setting.default) for name, setting in SCHEMA.items()}
)


def read_bytes(data, *, source, directory):
    """The layer the settings file `data` gives, read from `directory`.

    `source` names the file in errors. Paths resolve against `directory`,
    with a leading `~` expanded. Raises `SettingsError` naming the key path
    and line of the first problem.
    """
    try:
        document, marks = yamlfile.load_located(data)
    except yamlfile.YamlError as error:
        raise SettingsError(source, error.problem) from None
    if not isinstance(document, dict):
        raise SettingsError(
            source, f"expected a mapping of settings, got {_shown(document)}"
        )

    def refuse(path, problem):
        line, column = yamlfile.locate(marks, path)
        key = ".".join(str(step) for step in path)
        raise SettingsError(source, f"{key}: {problem} at line {line}, column {column}")

    for key in document:
        if not isinstance(key, str):
            line, column = yamlfile.locate(marks, (key,))
            raise SettingsError(
                source,
                f"the key {_shown(key)} is not a setting name at line {line}, "
                f"column {column}",
            )
    if "version" in document:
        version = document["version"]
        if type(version) is not int or version != VERSION:
            refuse(("version",), f"expected {VERSION}, got {_shown(version)}")
    layer = {}
    for key, value in document.items():
        if key == "version":
            continue
        setting = SCHEMA.get(key)
        if setting is None:
            refuse((key,), "unknown key")
        try:
            checked = setting.check(value)
        except _Bad as error:
            refuse((key,), error.problem)
        if setting.path and checked is not None:
            checked = Path(directory, os.path.expanduser(checked))
        layer[key] = checked
    return layer


def read_file(path, *, source, required):
    """The layer the settings file at `path` gives, or None when it is
    missing and not `required`. Reading it is the only effect."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        if not required:
            return None
        raise SettingsError(source, "does not exist") from None
    except OSError as error:
        raise SettingsError(
            source, f"cannot be read: {error.strerror or error}"
        ) from None
    return read_bytes(data, source=source, directory=path.parent)


def read_defaults():
    """The shipped defaults layer, from the packaged `defaults.yaml`."""
    data = resources.files("moskophoros").joinpath(DEFAULTS_FILE).read_bytes()
    return read_bytes(data, source="the shipped defaults", directory=".")


def user_file(environ):
    """The user file's path under the environment `environ`:
    `$XDG_CONFIG_HOME/moskophoros/config.yaml` when that is set and not
    empty, else `~/.config/moskophoros/config.yaml`."""
    base = environ.get("XDG_CONFIG_HOME")
    if not base:
        home = environ.get("HOME") or os.path.expanduser("~")
        base = os.path.join(home, ".config")
    return Path(base, USER_FILE)


def merge(*layers):
    """Lay `layers` over each other, lowest first: each key takes the value
    of the last layer that has it."""
    merged = {}
    for layer in layers:
        merged.update(layer)
    return merged
