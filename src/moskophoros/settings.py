"""Layered settings: the schema table, settings files and their merge
(settings design D-2, D-5, D-8, D-17, D-22 and D-30).

A settings file is a YAML mapping read by `yamlfile`, with an optional
`version: 1` and any of the settings in `SCHEMA`. A group such as `shade` is
a nested mapping whose settings are named by their dotted key paths, such as
`shade.ao_distance_m`, so a file may set one and inherit the rest; a list
such as `shade.range` is one value and replaces whole. Reading one gives a layer:
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
from moskophoros.capture.backend import MAX_AO_SAMPLES

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


class Layer(dict):
    """A layer's settings, with `where` mapping each name to the `(line,
    column)` it is written at, for errors about the file it names."""

    def __init__(self, values=(), where=None):
        super().__init__(values)
        self.where = dict(where or {})


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


def _finite(value, wanted):
    """`value` as a finite float, or `_Bad` saying it should be `wanted`."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _Bad(f"expected a number {wanted}, got {_shown(value)}")
    try:
        number = float(value)
    except OverflowError:
        number = math.inf
    if not math.isfinite(number):
        raise _Bad(f"expected a finite number {wanted}, got {_shown(value)}")
    return number


def _check_fps(value):
    number = _finite(value, "greater than 0")
    if number <= 0:
        raise _Bad(f"expected a finite number greater than 0, got {_shown(value)}")
    return number


def _check_distance(value):
    number = _finite(value, "greater than 0")
    if number <= 0:
        raise _Bad(f"expected a finite number greater than 0, got {_shown(value)}")
    return number


def _check_samples(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_AO_SAMPLES
    ):
        raise _Bad(
            f"expected a whole number from 1 to {MAX_AO_SAMPLES}, the most "
            f"Blender's ambient occlusion takes, got {_shown(value)}"
        )
    return value


def _check_weight(value):
    number = _finite(value, "0 or greater")
    if number < 0:
        raise _Bad(f"expected a finite number 0 or greater, got {_shown(value)}")
    return number


def _check_range(value):
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(type(bound) is int for bound in value)
        and 0 <= value[0] < value[1] <= 255
    ):
        return tuple(value)
    shown = (
        "[" + ", ".join(map(_shown, value)) + "]"
        if isinstance(value, list)
        else _shown(value)
    )
    raise _Bad(f"expected [lo, hi], two integers with 0 <= lo < hi <= 255, got {shown}")


def _check_path(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _Bad(f"expected a file path or null, got {_shown(value)}")
    return value


def resolve_path(given, directory):
    """The path the settings value `given` names, resolved against
    `directory` with a leading `~` expanded, or `_Bad` naming `given`.

    The whole pipeline runs inside one boundary: the raw string is checked
    first, then expanded, joined and checked again, so whatever any step
    raises, `ValueError`, `UnicodeError`, `OSError` or `RuntimeError` (such
    as an unnamable `~user`), is a settings error and never escapes. Every
    path a settings file supplies passes here.
    """
    try:
        _nameable(given)
        path = Path(directory, os.path.expanduser(given))
        _nameable(os.fspath(path))
        return path
    except (ValueError, UnicodeError, OSError, RuntimeError) as error:
        reason = getattr(error, "reason", None) or str(error)
        raise _Bad(
            f"expected a file path the file system can name, got {_shown(given)}: "
            f"{reason}"
        ) from None


def _nameable(text):
    """Refuse a path no file system can name: one holding a NUL character,
    or one `os.fsencode` refuses, such as one holding a lone surrogate."""
    if "\0" in text:
        # Python refuses to open such a path.
        raise _Bad(f"expected a file path without a NUL character, got {_shown(text)}")
    os.fsencode(text)


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
        "shade.ao_distance_m": Setting(
            "how far ambient occlusion looks for other surfaces, greater than 0",
            "meters",
            0.3,
            _check_distance,
        ),
        "shade.ao_samples": Setting(
            f"ambient occlusion samples per pixel, 1 to {MAX_AO_SAMPLES}",
            "samples",
            64,
            _check_samples,
        ),
        "shade.occlusion_weight": Setting(
            "how much occlusion by other surfaces lightens the shade, 0 or greater",
            None,
            0.25,
            _check_weight,
        ),
        "shade.convexity_weight": Setting(
            "how much a surface's own convexity lightens the shade, 0 or greater",
            None,
            1.0,
            _check_weight,
        ),
        "shade.range": Setting(
            "the 8-bit shade values a material's ramp spans, [lo, hi] with "
            "0 <= lo < hi <= 255",
            None,
            [84, 191],
            _check_range,
        ),
    }
)
# The groups of settings a file writes as a nested mapping, such as `shade`;
# each of its keys is a setting of its own, merged key by key.
GROUPS = frozenset(name.split(".")[0] for name in SCHEMA if "." in name)
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
    entries = []
    for key, value in document.items():
        if key == "version":
            continue
        if key not in GROUPS:
            entries.append(((key,), value))
            continue
        if not isinstance(value, dict):
            refuse((key,), f"expected a mapping of settings, got {_shown(value)}")
        for member, member_value in value.items():
            if not isinstance(member, str):
                line, column = yamlfile.locate(marks, (key, member))
                raise SettingsError(
                    source,
                    f"{key}: the key {_shown(member)} is not a setting name at "
                    f"line {line}, column {column}",
                )
            entries.append(((key, member), member_value))
    layer = Layer()
    for path, value in entries:
        key = ".".join(path)
        setting = SCHEMA.get(key)
        if setting is None:
            refuse(path, "unknown key")
        try:
            checked = setting.check(value)
        except _Bad as error:
            refuse(path, error.problem)
        if setting.path and checked is not None:
            try:
                checked = resolve_path(checked, directory)
            except _Bad as error:
                refuse(path, error.problem)
        layer[key] = checked
        layer.where[key] = yamlfile.locate(marks, path)
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
    except (OSError, ValueError) as error:
        raise SettingsError(
            source, f"cannot be read: {getattr(error, 'strerror', None) or error}"
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
    merged = Layer()
    for layer in layers:
        merged.update(layer)
        merged.where.update(getattr(layer, "where", {}))
    return merged
