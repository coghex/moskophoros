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
command's business (`cli.resolve_settings`). The global file and a project
file share this one schema (projects and camera design D-9).
"""

import math
import os
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType

from moskophoros import views, yamlfile
from moskophoros.capture.backend import MAX_AO_SAMPLES, PROJECTIONS
from moskophoros.imageops import EDGES

VERSION = 1
DEFAULTS_FILE = "defaults.yaml"
# The configuration directory under `$XDG_CONFIG_HOME` or `~/.config`, the
# user file in it, the default global file, and its folder of project files.
CONFIG_DIR = "moskophoros"
USER_FILE = "config.yaml"
PROJECTS_DIR = "projects"
# A project name: letters, digits, `.`, `_` and `-`, not starting with `.`,
# given without `.yaml` (projects and camera design D-16).
PROJECT_NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", re.ASCII)
PROJECT_SUFFIX = ".yaml"
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


def _check_light_position(value):
    """A light's position: `null`, no light, or three finite numbers
    `[x, y, z]`, never booleans."""
    if value is None:
        return None
    if isinstance(value, list) and len(value) == 3:
        try:
            return tuple(_finite(coordinate, "") for coordinate in value)
        except _Bad:
            pass
    shown = (
        "[" + ", ".join(map(_shown, value)) + "]"
        if isinstance(value, list)
        else _shown(value)
    )
    raise _Bad(f"expected [x, y, z], three finite numbers, or null, got {shown}")


def _check_direction(value):
    """The camera's direction: `null`, the view's, or `[x, y, z]`, three
    finite numbers each from −1 to +1, not all 0, normalised (projects and
    camera design D-7)."""
    if value is None:
        return None
    if isinstance(value, list) and len(value) == 3:
        try:
            vector = tuple(_finite(component, "") for component in value)
        except _Bad:
            vector = None
        if vector is not None and all(-1 <= component <= 1 for component in vector):
            if any(vector):
                return views.normalise(vector)
            raise _Bad("expected a direction, but [0, 0, 0] points nowhere")
    raise _Bad(
        "expected [x, y, z], three finite numbers each from -1 to 1, not all 0, "
        f"or null, got {_shown_list(value)}"
    )


def _check_ambient(value):
    number = _finite(value, "from 0 to 1")
    if not 0 <= number <= 1:
        raise _Bad(f"expected a finite number from 0 to 1, got {_shown(value)}")
    return number


def _within(low, high):
    def check(value):
        number = _finite(value, f"from {low} to {high}")
        if not low <= number <= high:
            raise _Bad(
                f"expected a finite number from {low} to {high}, got {_shown(value)}"
            )
        return number

    return check


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


def _check_frames(value):
    """A frame count as a file gives it: `auto` or a whole number of 1 or
    more, an integer, never `8.0`, `"8"` or a boolean (settings design
    D-34)."""
    if value == AUTO or (type(value) is int and value >= 1):
        return value
    raise _Bad(f"expected a whole number 1 or more, or {AUTO}, got {_shown(value)}")


def _check_clip_frames(value):
    """A clip's own frame count: a count, `auto`, or null to take the global
    count (settings design D-31)."""
    if value is None:
        return None
    try:
        return _check_frames(value)
    except _Bad:
        raise _Bad(
            f"expected a whole number 1 or more, {AUTO} or null, got {_shown(value)}"
        ) from None


def _check_edges(value):
    """One of `EDGES`, the shipped default first (alpha design D-4, D-9)."""
    if isinstance(value, str) and value in EDGES:
        return value
    raise _Bad(f"expected {' or '.join(EDGES)}, got {_shown(value)}")


def _check_previews(value):
    if not isinstance(value, bool):
        raise _Bad(f"expected true or false, got {_shown(value)}")
    return value


def _one_of(*choices):
    """A string among `choices`, as the option of the same name accepts."""

    def check(value):
        if isinstance(value, str) and value in choices:
            return value
        listed = ", ".join(choices[:-1]) + f" or {choices[-1]}"
        raise _Bad(f"expected {listed}, got {_shown(value)}")

    return check


def _nullable(check, wanted):
    """`check`, or `null`: the value from the view in force (projects and
    camera design D-16). `wanted` describes what `check` accepts."""

    def nullable(value):
        if value is None:
            return None
        try:
            return check(value)
        except _Bad:
            raise _Bad(f"expected {wanted}, or null, got {_shown(value)}") from None

    return nullable


def _whole_from(low, high):
    def check(value):
        if type(value) is not int or not low <= value <= high:
            raise _Bad(
                f"expected a whole number from {low} to {high}, got {_shown(value)}"
            )
        return value

    return check


def _check_degrees(value):
    return _finite(value, "of degrees")


def _check_ppm(value):
    """`auto` as None, the automatic scale, or a finite number greater than
    0."""
    if value == AUTO:
        return None
    try:
        return _check_fps(value)
    except _Bad:
        raise _Bad(
            f"expected a finite number greater than 0, or {AUTO}, got {_shown(value)}"
        ) from None


def _shown_list(value):
    if isinstance(value, list):
        return "[" + ", ".join(map(_shown, value)) + "]"
    return _shown(value)


def _check_ground(value):
    """The ground point: `[x, y, z]`, three finite numbers, never booleans."""
    if isinstance(value, list) and len(value) == 3:
        try:
            return tuple(_finite(coordinate, "") for coordinate in value)
        except _Bad:
            pass
    raise _Bad(f"expected [x, y, z], three finite numbers, got {_shown_list(value)}")


def _check_ground_px(value):
    """`auto` as None, or `[x, y]`, two whole numbers 0 or greater: integers,
    or integral finite floats such as `3.0`, made integers; never booleans
    or strings. Whether it lies in the cell is an overflow question."""
    if value == AUTO:
        return None
    if isinstance(value, list) and len(value) == 2:
        coordinates = []
        for coordinate in value:
            if type(coordinate) is int and coordinate >= 0:
                coordinates.append(coordinate)
            elif (
                type(coordinate) is float
                and math.isfinite(coordinate)
                and coordinate.is_integer()
                and coordinate >= 0
            ):
                coordinates.append(int(coordinate))
            else:
                break
        else:
            return tuple(coordinates)
    raise _Bad(
        f"expected [x, y], two whole numbers 0 or greater, or {AUTO}, got "
        f"{_shown_list(value)}"
    )


# The view's presets, as `--view` names them, and the values `--reduce` and
# `--root-motion` accept, the default first.
VIEWS = ("topdown", "side", "iso", "iso-true")
REDUCTIONS = ("plain", "mode")
ROOT_MOTION_MODES = ("error", "keep")
# The view's settings (projects and camera design D-16): a preset, and the
# values a preset gives, which `null` takes from the preset in force. `pitch`
# and `camera.direction` are two spellings of the direction (`DIRECTION`),
# and one layer may give only one of them (D-12).
VIEW_SETTINGS = ("view", "pitch", "camera.direction", "directions", "start_angle")
DIRECTION = ("pitch", "camera.direction")
# The app settings: never recorded in a sheet, never loaded from one, and
# no part of its fingerprint (projects and camera design D-16).
APP_SETTINGS = ("blender", "any_blender")

SCHEMA = MappingProxyType(
    {
        "view": Setting(
            f"the view preset: {', '.join(VIEWS)}; it sets the pitch, the "
            "direction count and the start angle",
            None,
            "iso",
            _one_of(*VIEWS),
        ),
        "pitch": Setting(
            "the camera pitch, 0 to 90, or null: the view's",
            "degrees",
            None,
            _nullable(_within(0, 90), "a finite number from 0 to 90"),
        ),
        "camera.projection": Setting(
            "the camera's projection: orthographic or perspective, which looks "
            "from camera.position",
            None,
            PROJECTIONS[0],
            _one_of(*PROJECTIONS),
        ),
        "camera.direction": Setting(
            "the way the camera looks, [x, y, z] in subject coordinates, each "
            "-1 to 1, not all 0, normalised, or null: the view's",
            None,
            None,
            _check_direction,
        ),
        "camera.roll": Setting(
            "the camera's turn about the way it looks, -1 to 1, a fraction of a "
            "half turn; positive turns the picture clockwise",
            "half turns",
            0,
            _within(-1, 1),
        ),
        "camera.position": Setting(
            "the camera's position from the ground point, [x, y, z], or null; "
            "the perspective camera needs it, and the orthographic camera "
            "leaves it unused",
            "meters",
            None,
            _check_light_position,
        ),
        "directions": Setting(
            "the direction count, 1 to 64, or null: the view's",
            "directions",
            None,
            _nullable(_whole_from(1, 64), "a whole number from 1 to 64"),
        ),
        "start_angle": Setting(
            "the angle of direction 0, or null: the view's",
            "degrees",
            None,
            _nullable(_check_degrees, "a finite number of degrees"),
        ),
        "model_yaw": Setting(
            "corrects a model that does not face +Z",
            "degrees",
            0,
            _check_degrees,
        ),
        "ppm": Setting(
            "pixels per meter, greater than 0, or auto: fitted",
            "pixels per meter",
            AUTO,
            _check_ppm,
        ),
        "ground": Setting(
            "the ground point in subject coordinates, [x, y, z]",
            "meters",
            [0, 0, 0],
            _check_ground,
        ),
        "ground_px": Setting(
            "the cell pixel corner the ground point lands on, [x, y], two whole "
            "numbers 0 or greater, or auto: fitted",
            "pixels",
            AUTO,
            _check_ground_px,
        ),
        "supersample": Setting(
            "the capture resolution multiplier, 1 to 16",
            None,
            8,
            _whole_from(1, 16),
        ),
        "reduce": Setting(
            "how each supersampled block becomes one pixel: plain or mode",
            None,
            REDUCTIONS[0],
            _one_of(*REDUCTIONS),
        ),
        "root_motion": Setting(
            "error or keep",
            None,
            ROOT_MOTION_MODES[0],
            _one_of(*ROOT_MOTION_MODES),
        ),
        "blender": Setting(
            "the Blender executable, or null: discovered; an app setting",
            None,
            None,
            _check_path,
            path=True,
        ),
        "any_blender": Setting(
            "whether a Blender version other than the supported one is allowed; "
            "an app setting",
            None,
            False,
            _check_previews,
        ),
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
        "frames": Setting(
            "how many frames each clip is sampled to, retimed so each lasts "
            "1/fps, a whole number 1 or more, or auto: sampled by duration",
            "frames",
            AUTO,
            _check_frames,
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
        "edges": Setting(
            "how a pixel's alpha comes from its supersampled block: hard, a "
            "pixel shows when at least half its block shows a surface, at "
            "their mean alpha; soft, its alpha is the block's mean alpha",
            None,
            EDGES[0],
            _check_edges,
        ),
        "previews": Setting(
            "whether the animated previews are written", None, True, _check_previews
        ),
        "normals": Setting(
            "whether the normal map is written", None, True, _check_previews
        ),
        "depth": Setting(
            "whether the depth map is written", None, False, _check_previews
        ),
        "light.position": Setting(
            "the preview light's position in the camera's frame, from the "
            "ground point: [x, y, z] with x screen right, y screen up and z "
            "toward the viewer, or null for no light",
            "sheet pixels",
            None,
            _check_light_position,
        ),
        "light.intensity": Setting(
            "how strongly the light lights a surface facing it, 0 or greater",
            None,
            1.0,
            _check_weight,
        ),
        "light.ambient": Setting(
            "how bright a surface facing away from the light is, 0 to 1",
            None,
            0.3,
            _check_ambient,
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
        "ramp.lightness_step": Setting(
            "how much OKLab lightness each shade of a generated ramp drops, 0 to 1",
            None,
            0.12,
            _within(0, 1),
        ),
        "ramp.hue_shift_deg": Setting(
            "how far each shade of a generated ramp turns the hue, -180 to 180",
            "degrees",
            -12.0,
            _within(-180, 180),
        ),
        "ramp.chroma_fade": Setting(
            "how much chroma a generated ramp loses by its darkest shade, 0 to 1",
            None,
            0.3,
            _within(0, 1),
        ),
    }
)
# A clip's own settings, in a file's `clips` mapping keyed by clip name;
# each beats the global setting of the same name (settings design D-17,
# D-26). Clips the model lacks, or that are not selected, are unused.
CLIP_SCHEMA = MappingProxyType(
    {
        "frames": Setting(
            "the clip's own frame count, a whole number 1 or more, auto, or "
            "null to take the global count",
            "frames",
            None,
            _check_clip_frames,
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


def read_bytes(data, *, source, directory, shipped=False):
    """The layer the settings file `data` gives, read from `directory`.

    `source` names the file in errors. Paths resolve against `directory`,
    with a leading `~` expanded. Raises `SettingsError` naming the key path
    and line of the first problem. A file giving both spellings of the
    direction, `pitch` and `camera.direction`, with any values, is refused,
    except the `shipped` defaults, which set the view's initial state.
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
    clips = {}
    for key, value in document.items():
        if key == "version":
            continue
        if key == "clips":
            clips = _read_clips(value, refuse, marks, source)
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
    if not shipped and all(name in layer for name in DIRECTION):
        later = max(DIRECTION, key=lambda name: layer.where[name])
        refuse(
            tuple(later.split(".")),
            "pitch and camera.direction both set the camera's direction; give "
            "only one of them",
        )
    if clips:
        layer["clips"] = clips
    return layer


def _read_clips(value, refuse, marks, source):
    """A file's `clips` mapping: each named clip's own settings, as
    `{clip name: frames}` for the clips that give a frame count, null
    included. Every entry is checked, whether or not the model has it."""
    if not isinstance(value, dict):
        refuse(("clips",), f"expected a mapping of clips by name, got {_shown(value)}")
    clips = {}
    for name, entry in value.items():
        if not isinstance(name, str) or not name:
            line, column = yamlfile.locate(marks, ("clips", name))
            raise SettingsError(
                source,
                f"clips: the key {_shown(name)} is not a clip name at line {line}, "
                f"column {column}",
            )
        if not isinstance(entry, dict):
            refuse(
                ("clips", name),
                f"expected a mapping of the clip's settings, got {_shown(entry)}",
            )
        for member, member_value in entry.items():
            if member not in CLIP_SCHEMA:
                refuse(("clips", name, member), "unknown key")
            try:
                clips[name] = CLIP_SCHEMA[member].check(member_value)
            except _Bad as error:
                refuse(("clips", name, member), error.problem)
    return clips


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
    return read_bytes(data, source="the shipped defaults", directory=".", shipped=True)


def config_dir(environ):
    """The configuration directory under the environment `environ`:
    `$XDG_CONFIG_HOME/moskophoros` when that is set and not empty, else
    `~/.config/moskophoros`."""
    base = environ.get("XDG_CONFIG_HOME")
    if not base:
        home = environ.get("HOME") or os.path.expanduser("~")
        base = os.path.join(home, ".config")
    return Path(base, CONFIG_DIR)


def user_file(environ):
    """The user file's path under the environment `environ`,
    `config.yaml` in the configuration directory: the global file unless
    `--config` names another."""
    return config_dir(environ) / USER_FILE


def is_project_name(name):
    """Whether `name` is a project name: letters, digits, `.`, `_` and `-`,
    not starting with `.`, and not ending in `.yaml`, so it names a file in
    the projects folder and nothing outside it."""
    if name.endswith(PROJECT_SUFFIX):
        return False
    return PROJECT_NAME.fullmatch(name) is not None


def project_file(environ, name):
    """The path of project `name`'s file under the environment `environ`,
    `projects/NAME.yaml` in the configuration directory, which neither
    `--config` nor `--no-user-config` moves. `name` must be a project name."""
    if not is_project_name(name):
        raise ValueError(f"not a project name: {name!r}")
    return config_dir(environ) / PROJECTS_DIR / f"{name}{PROJECT_SUFFIX}"


def merge(*layers):
    """Lay `layers` over each other, lowest first: each key takes the value
    of the last layer that has it."""
    merged = Layer()
    for layer in layers:
        clips = {**merged.get("clips", {}), **layer.get("clips", {})}
        merged.update(layer)
        if clips:
            # Per-clip entries merge by clip name (settings design D-22).
            merged["clips"] = clips
        merged.where.update(getattr(layer, "where", {}))
    return merged
