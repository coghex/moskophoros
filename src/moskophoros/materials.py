"""Material libraries: named ramps of palette indices, read and validated.

A library is a JSON file the tool only reads (material design D-8). Its ramps
index the shared palette (D-6, D-7); it holds named generic ramps, an optional
default naming one of them, and material entries (D-15, D-17).
"""

import json
from dataclasses import dataclass
from numbers import Integral
from pathlib import Path
from types import MappingProxyType

SCHEMA = "moskophoros.materials/1"
ORDINARY = "ordinary"
MAX_RAMP = 256
_FIELDS = ("schema", "ramps", "default", "materials")
_REQUIRED = ("schema", "ramps", "materials")


class LibraryError(Exception):
    """Bad material library input; the caller decides how to report it."""

    def __init__(self, source, problem):
        self.source = source
        self.problem = problem
        super().__init__(f"{source}: {problem}")


@dataclass(frozen=True)
class Entry:
    """One material entry: its own `ramp`, the named ramp it `uses`, or
    neither, which is the `"ordinary"` look."""

    ramp: tuple[int, ...] | None = None
    uses: str | None = None


@dataclass(frozen=True)
class Library:
    """A validated library. Both mappings are read-only and ordered by name,
    so the result never depends on the file's key order."""

    ramps: MappingProxyType
    default: str | None
    materials: MappingProxyType


def read_library(path, colors):
    """Read and validate the library at `path` against the palette `colors`.

    Raises `LibraryError` for bad input. Reading this file is the only effect.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise LibraryError(path, f"cannot be read: {error.strerror or error}") from None
    return read_library_bytes(data, colors, source=path)


def read_library_bytes(data, colors, *, source):
    """Parse a library snapshot, so its contents and digest describe the same
    bytes. The JSON must be UTF-8, repeat no key and use no non-JSON constant.
    """
    try:
        document = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_keys,
            parse_constant=_no_constant,
        )
    except UnicodeDecodeError as error:
        raise LibraryError(
            source, f"is not UTF-8: {error.reason} at byte {error.start}"
        ) from None
    except _DuplicateKey as error:
        raise LibraryError(source, str(error)) from None
    except ValueError as error:
        raise LibraryError(source, f"is not valid JSON: {error}") from None
    except RecursionError:
        raise LibraryError(
            source, "is not valid JSON: it is nested too deeply"
        ) from None
    return validate_library(document, colors, source=source)


def validate_library(document, colors, *, source):
    """Validate an already-parsed library against the palette `colors`.

    Applies every structural, value and reference check. `source` only labels
    diagnostics; nothing is read and `document` is not changed.
    """
    if not isinstance(document, dict):
        raise LibraryError(source, "expected a JSON object")
    _check_keys(document, source)
    unknown = sorted(key for key in document if key not in _FIELDS)
    if unknown:
        raise LibraryError(source, f"unknown field {_name(unknown[0])}")
    for field in _REQUIRED:
        if field not in document:
            raise LibraryError(source, f"{field}: missing")
    if not isinstance(document["schema"], str) or document["schema"] != SCHEMA:
        raise LibraryError(
            source,
            f"schema: expected {_name(SCHEMA)}, got {_shown(document['schema'])}",
        )
    size = len(colors)
    ramps = {
        name: _ramp(value, f"ramps[{_name(name)}]", size, source)
        for name, value in _named(document["ramps"], "ramps", source)
    }
    default = None
    if "default" in document:
        default = _reference(document["default"], "default", ramps, source)
    materials = {}
    for name, value in _named(document["materials"], "materials", source):
        materials[name] = _entry(
            value, f"materials[{_name(name)}]", ramps, size, source
        )
    return Library(MappingProxyType(ramps), default, MappingProxyType(materials))


def _named(mapping, location, source):
    """Yield a name-keyed object's items in name order, checking each name."""
    if not isinstance(mapping, dict):
        raise LibraryError(source, f"{location}: expected an object")
    _check_keys(mapping, source, location)
    for name in sorted(mapping):
        if name == "":
            raise LibraryError(source, f"{location}: the empty name is not allowed")
        yield name, mapping[name]


def _check_keys(mapping, source, location=None):
    # JSON keys are always strings; an already-parsed library might not be.
    for key in mapping:
        if not isinstance(key, str):
            where = f"{location}: " if location else ""
            raise LibraryError(source, f"{where}key {key!r} is not a string")


def _ramp(value, location, size, source):
    if not isinstance(value, (list, tuple)):
        raise LibraryError(source, f"{location}: expected a list of palette indices")
    if not 1 <= len(value) <= MAX_RAMP:
        raise LibraryError(
            source,
            f"{location}: has {len(value)} entries; expected 1 to {MAX_RAMP}",
        )
    for position, index in enumerate(value):
        here = f"{location}[{position}]"
        if isinstance(index, bool) or not isinstance(index, Integral):
            raise LibraryError(source, f"{here}: {_shown(index)} is not an integer")
        if not 0 <= index < size:
            raise LibraryError(
                source,
                f"{here}: {int(index)} is not an index into the {size}-colour "
                f"palette (0 to {size - 1})",
            )
    return tuple(int(index) for index in value)


def _reference(value, location, ramps, source):
    if not isinstance(value, str):
        raise LibraryError(
            source, f"{location}: expected a ramp name, got {_shown(value)}"
        )
    if value == "":
        raise LibraryError(source, f"{location}: the empty name is not allowed")
    if value not in ramps:
        raise LibraryError(source, f"{location}: no ramp is named {_name(value)}")
    return value


def _entry(value, location, ramps, size, source):
    if isinstance(value, str) and value == ORDINARY:
        return Entry()
    if not isinstance(value, dict):
        raise LibraryError(
            source,
            f'{location}: expected {{"ramp": [...]}}, {{"uses": NAME}} or '
            f'"{ORDINARY}", got {_shown(value)}',
        )
    _check_keys(value, source, location)
    unknown = sorted(key for key in value if key not in ("ramp", "uses"))
    if unknown:
        raise LibraryError(source, f"{location}: unknown field {_name(unknown[0])}")
    if len(value) != 1:
        raise LibraryError(
            source, f'{location}: expected exactly one of "ramp" and "uses"'
        )
    if "ramp" in value:
        return Entry(ramp=_ramp(value["ramp"], f"{location}.ramp", size, source))
    return Entry(uses=_reference(value["uses"], f"{location}.uses", ramps, source))


def _name(name):
    """Show a name exactly, quotes and whitespace included."""
    return json.dumps(name, ensure_ascii=False)


def _shown(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return repr(value)


class _DuplicateKey(ValueError):
    pass


def _unique_keys(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateKey(f"repeats the key {_name(key)}")
        document[key] = value
    return document


def _no_constant(name):
    raise ValueError(f"{name} is not a JSON value")
