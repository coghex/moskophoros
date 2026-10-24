"""The `moskophoros` command: options, settings reuse, the run and its exit
codes.

`parse_args` turns an argument list into validated `Options`, following
design §CLI, §Option validation and §Presets. On success it has no effects:
it reads no files, starts no process and prints nothing. Checks that need the
input file, the filesystem or Blender belong to the stages that use them.

`resolve_settings` lays the settings layers under the parsed options,
following design §CLI, Settings files, and §Scale and ground point, Reuse:
the shipped defaults, the global file, a loaded sheet (`--settings-from`) and
a project file (`--project`). `read_settings` reads and checks the loaded sheet's
`settings`, and `apply_settings` merges them with the options. It also reads
the selected palette and material library snapshots; these reads precede any
Blender invocation.

`capture_settings` gives the settings capture and export share, the
shade's capture values among them, and `style_record` the style the sheet
records beside them, following design §Export: the reduction, the palette and
the material library. The style and the shade range never reach the capture
job.

`main` runs the whole command, following design §CLI and §Pipeline: read and
measure the model, check root motion, fit, render, stylize, clean up and
export, then publish every output all or nothing. `run` does the same and
returns the exit status of design §Exit codes.
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import sys
import tempfile
import threading
import traceback
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from dataclasses import field as dataclass_field
from decimal import Decimal, InvalidOperation
from itertools import count
from pathlib import Path
from types import MappingProxyType

from moskophoros import (
    cleanup,
    export,
    fit,
    gltf,
    imageops,
    lighting,
    materials,
    palette,
    sampling,
    shading_resolve,
    stylize,
    views,
)
from moskophoros import settings as layered
from moskophoros import shading as shading_model
from moskophoros.capture import backend, blender

PROG = "moskophoros"
USAGE = f"{PROG} [options] <infile.glb> <outfile.png>"
INTERNAL_ERROR = 1
USAGE_ERROR = 2
OUTPUT_ERROR = 6
INTERRUPTED = 130
# Root travel above this is an input error under `--root-motion error`.
MAX_ROOT_TRAVEL_M = 0.02


@dataclass(frozen=True)
class Preset:
    pitch: float
    directions: int
    start_angle: float

    @property
    def direction(self):
        """The camera direction the preset's pitch sets (projects and camera
        design D-12)."""
        return views.pitch_direction(self.pitch)


PRESETS = MappingProxyType(
    {
        "topdown": Preset(pitch=90.0, directions=8, start_angle=0.0),
        "side": Preset(pitch=0.0, directions=2, start_angle=90.0),
        "iso": Preset(pitch=30.0, directions=8, start_angle=0.0),
        "iso-true": Preset(
            pitch=math.degrees(math.atan(1 / math.sqrt(2))),
            directions=8,
            start_angle=0.0,
        ),
    }
)
DEFAULT_VIEW = "iso"
# The resolved view name once --pitch, --camera-direction, --directions or
# --start-angle is given.
CUSTOM_VIEW = "custom"
ROOT_MOTION_MODES = layered.ROOT_MOTION_MODES
# The values --reduce accepts; the first is the default.
REDUCTIONS = layered.REDUCTIONS
# The values --projection accepts; the first is the default.
PROJECTIONS = layered.PROJECTIONS
# The only sheet schema `--settings-from` loads (settings design D-24).
SHEET_SCHEMA = "moskophoros.sheet/15"
_MAX_DIGITS = 4300
# The view's values a preset gives, which an override replaces. `--pitch` and
# `--camera-direction` both set the direction.
_VIEW_VALUES = ("direction", "directions", "start_angle")
_REPEATABLE = frozenset({"--clip", "--once"})
# The shading settings (shading design contract 1), each as its path under
# `shade`, the `Options` field that holds its global value, which is also its
# option's name in `explicit`, and the option that sets it, as errors and
# warnings name it. A material may override all but the key direction, the
# sky and ground frame and the snap target (`shading_model.FIELDS`).
_SHADING = (
    ("mode", "shade_mode", "--shade-mode"),
    ("ambient_form", "ambient_form", "--ambient-form"),
    ("key.direction", "key_direction", "--bake-key-direction"),
    ("key.strength", "key_strength", "--bake-key-strength"),
    ("sky.strength", "sky_strength", "--bake-sky-strength"),
    ("ground.strength", "ground_strength", "--bake-ground-strength"),
    ("sky_ground_frame", "sky_ground_frame", "--bake-sky-ground-frame"),
    ("brightness.floor", "brightness_floor", "--brightness-floor"),
    ("brightness.ceiling", "brightness_ceiling", "--brightness-ceiling"),
    ("snap", "shade_snap", "--shade-snap"),
    ("dither.pattern", "dither_pattern", "--dither-pattern"),
    ("dither.strength", "dither_strength", "--dither-strength"),
)
# The shading values a material may override that existed before the
# response, the same way: path under `shade`, `Options` field and option.
_SHADE_VALUES = (
    ("ao_distance_m", "ao_distance", "--ao-distance"),
    ("occlusion_weight", "occlusion_weight", "--occlusion-weight"),
    ("convexity_weight", "convexity_weight", "--convexity-weight"),
    ("range", "shade_range", "--shade-range"),
)
# The `Options` field of each file setting whose name differs, which is also
# its option's name in `explicit`.
_SETTING_FIELDS = MappingProxyType(
    {
        "shade.ao_distance_m": "ao_distance",
        "shade.ao_samples": "ao_samples",
        "shade.occlusion_weight": "occlusion_weight",
        "shade.convexity_weight": "convexity_weight",
        "shade.range": "shade_range",
        "light.position": "light",
        "light.intensity": "light_intensity",
        "light.ambient": "light_ambient",
        "ramp.lightness_step": "ramp_step",
        "ramp.hue_shift_deg": "ramp_hue_shift",
        "ramp.chroma_fade": "ramp_fade",
        "camera.projection": "projection",
        "camera.roll": "roll",
        "camera.position": "camera_position",
        **{f"shade.{path}": field for path, field, _ in _SHADING},
    }
)
# The file settings that are paths, with the `Options` fields a path and a
# null set; the others set the field of their own name. Each one's names in
# `explicit` are its own and, for a path, the null's flag.
_PATH_FIELDS = MappingProxyType(
    {
        "palette": ("palette_file", "no_palette"),
        "materials": ("materials_file", "no_materials"),
    }
)
_HELP = frozenset({"-h", "--help"})


@dataclass(frozen=True)
class PaletteRecord:
    """A palette snapshot; reuse never needs its original file."""

    source: str
    sha256: str
    colors: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class MaterialsRecord:
    """A material library snapshot; reuse never needs its original file.
    `formula`, for a reused one, maps each global formula value to the one
    its recorded generated ramps were made with (material styling design
    D-33); None for a library read from its file."""

    source: str
    sha256: str
    library: materials.Library
    formula: MappingProxyType | None = None


@dataclass(frozen=True)
class Options:
    """Validated options.

    `explicit` holds the field names of the options given on the command
    line, as distinct from defaults and preset-derived values; once
    `resolve_settings` has run, it also holds the fields a project file set,
    which act as explicit options; `--pitch` is named `pitch` there. `view`
    is the resolved preset name, or `custom` when an explicit direction,
    direction count or start angle overrides the preset; `preset` is the
    preset `--view` names, or the default. `direction` is the camera's
    normalised direction, which `--pitch` or the preset may set,
    `projection` its projection, `roll` its roll and `camera_position` its
    position, or None. `clip` is None when every clip is selected; `ppm`,
    `cell` and `ground_px` are None when automatic. `origins` names the settings file
    that set a palette, a library or the Blender executable, for its errors.
    """

    infile: Path
    outfile: Path
    view: str
    direction: tuple[float, float, float]
    directions: int
    start_angle: float
    model_yaw: float
    clip: tuple[str, ...] | None
    once: tuple[str, ...]
    fps: float
    ppm: float | None
    cell: tuple[int, int] | None
    ground: tuple[float, float, float]
    ground_px: tuple[int, int] | None
    root_motion: str
    supersample: int
    reduce: str
    settings_from: Path | None
    previews: bool
    work_dir: Path | None
    blender: Path | None
    any_blender: bool
    explicit: frozenset[str]
    palette_file: Path | None = None
    no_palette: bool = False
    palette: PaletteRecord | None = None
    materials_file: Path | None = None
    no_materials: bool = False
    materials: MaterialsRecord | None = None
    shade_range: tuple[int, int] = layered.DEFAULTS["shade.range"]
    ao_distance: float = layered.DEFAULTS["shade.ao_distance_m"]
    ao_samples: int = layered.DEFAULTS["shade.ao_samples"]
    occlusion_weight: float = layered.DEFAULTS["shade.occlusion_weight"]
    convexity_weight: float = layered.DEFAULTS["shade.convexity_weight"]
    # The global shading settings (shading design contract 1), each the
    # shipped default until a layer or an option sets it. `key_direction` is
    # the normalised direction toward the key light in the camera's frame.
    shade_mode: str = layered.DEFAULTS["shade.mode"]
    ambient_form: bool = layered.DEFAULTS["shade.ambient_form"]
    key_direction: tuple[float, float, float] = layered.DEFAULTS["shade.key.direction"]
    key_strength: float = layered.DEFAULTS["shade.key.strength"]
    sky_strength: float = layered.DEFAULTS["shade.sky.strength"]
    ground_strength: float = layered.DEFAULTS["shade.ground.strength"]
    sky_ground_frame: str = layered.DEFAULTS["shade.sky_ground_frame"]
    brightness_floor: float = layered.DEFAULTS["shade.brightness.floor"]
    brightness_ceiling: float = layered.DEFAULTS["shade.brightness.ceiling"]
    shade_snap: str = layered.DEFAULTS["shade.snap"]
    dither_pattern: str = layered.DEFAULTS["shade.dither.pattern"]
    dither_strength: float = layered.DEFAULTS["shade.dither.strength"]
    # The resolved shading, a `shading_resolve.Resolved`, and where each of
    # its settings came from (`resolve_settings`); None before then. They are
    # derived from the settings above, so they take no part in comparing
    # options.
    shading: object = dataclass_field(default=None, compare=False)
    shading_origins: MappingProxyType = dataclass_field(
        default=MappingProxyType({}), compare=False
    )
    # The global file `--config` names, in place of the user file; whether
    # `--no-user-config` uses none; and the `--project` name.
    config: Path | None = None
    no_user_config: bool = False
    project: str | None = None
    origins: MappingProxyType = MappingProxyType({})
    # The global frame count as given, "auto" or a count, and each clip's own
    # by name: a count, "auto", or None to take the global (settings design
    # D-13, D-31).
    frames: int | str = layered.DEFAULTS["frames"]
    clip_frames: MappingProxyType = MappingProxyType({})
    # How a pixel's alpha comes from its block, hard or soft (alpha design
    # D-4, D-9).
    edges: str = layered.DEFAULTS["edges"]
    # Whether the normal map is written (lighting sheet design D-9, D-18).
    normals: bool = layered.DEFAULTS["normals"]
    # Whether the depth map is written (lighting sheet design D-3, D-18).
    depth: bool = layered.DEFAULTS["depth"]
    # The preview light (lighting sheet design D-13, D-14, D-18): its
    # position in sheet pixels from the ground point in the camera's frame,
    # or None for no light, its intensity and its ambient level.
    light: tuple[float, float, float] | None = layered.DEFAULTS["light.position"]
    light_intensity: float = layered.DEFAULTS["light.intensity"]
    light_ambient: float = layered.DEFAULTS["light.ambient"]
    # The global formula of generated ramps (material styling design D-30,
    # D-33): the lightness step, hue shift in degrees and chroma fade.
    ramp_step: float = layered.DEFAULTS["ramp.lightness_step"]
    ramp_hue_shift: float = layered.DEFAULTS["ramp.hue_shift_deg"]
    ramp_fade: float = layered.DEFAULTS["ramp.chroma_fade"]
    preset: str = DEFAULT_VIEW
    projection: str = layered.DEFAULTS["camera.projection"]
    roll: float = layered.DEFAULTS["camera.roll"]
    camera_position: tuple[float, float, float] | None = layered.DEFAULTS[
        "camera.position"
    ]


class UsageError(SystemExit):
    """A usage error, already reported on stderr; its exit status is 2."""

    def __init__(self, message):
        super().__init__(USAGE_ERROR)
        self.message = message


def parse_args(argv: Sequence[str]) -> Options:
    """Parse and validate `argv`, the arguments after the program name.

    Raises `UsageError` after printing the usage synopsis and
    `moskophoros: error: <message>` to stderr. `--help` prints help to stdout
    and raises `SystemExit(0)`.
    """
    parser, value_options, flags = _build_parser()
    namespace = argparse.Namespace(explicit_=set())
    args = parser.parse_args(_prepare(parser, argv, value_options, flags), namespace)
    if args.palette is not None and args.no_palette:
        parser.error("--palette and --no-palette cannot be given together")
    if args.materials is not None and args.no_materials:
        parser.error("--materials and --no-materials cannot be given together")
    if args.preview and args.no_preview:
        parser.error("--preview and --no-preview cannot be given together")
    if args.normals and args.no_normals:
        parser.error("--normals and --no-normals cannot be given together")
    if args.depth and args.no_depth:
        parser.error("--depth and --no-depth cannot be given together")
    if args.light is not None and args.no_light:
        parser.error("--light and --no-light cannot be given together")
    if args.ambient_form and args.no_ambient_form:
        parser.error("--ambient-form and --no-ambient-form cannot be given together")
    if args.config is not None and args.no_user_config:
        parser.error("--config and --no-user-config cannot be given together")
    if args.pitch is not None and args.direction is not None:
        parser.error(
            "--pitch and --camera-direction cannot be given together: both set "
            "the camera's direction"
        )

    once = tuple(args.once or ())
    clip = None if args.clip is None else tuple(args.clip)
    if clip is not None:
        for name in once:
            if name not in clip:
                parser.error(f"argument --once: {name!r} is not among the --clip names")

    explicit = set(args.explicit_)
    if explicit & {"preview", "no_preview"}:
        explicit = (explicit - {"preview", "no_preview"}) | {"previews"}
    if "no_normals" in explicit:
        explicit = (explicit - {"no_normals"}) | {"normals"}
    if "no_depth" in explicit:
        explicit = (explicit - {"no_depth"}) | {"depth"}
    if "no_light" in explicit:
        explicit = (explicit - {"no_light"}) | {"light"}
    if "no_ambient_form" in explicit:
        explicit = (explicit - {"no_ambient_form"}) | {"ambient_form"}
    explicit = frozenset(explicit)
    preset = PRESETS[args.view]
    overrides = {"pitch", "direction", "directions", "start_angle"} & explicit
    if "direction" in explicit:
        direction = args.direction
    elif "pitch" in explicit:
        direction = views.pitch_direction(args.pitch)
    else:
        direction = preset.direction
    return Options(
        infile=args.infile,
        outfile=args.outfile,
        view=CUSTOM_VIEW if overrides else args.view,
        direction=direction,
        projection=args.projection,
        roll=args.roll,
        camera_position=args.camera_position,
        directions=args.directions if "directions" in explicit else preset.directions,
        start_angle=(
            args.start_angle if "start_angle" in explicit else preset.start_angle
        ),
        model_yaw=args.model_yaw,
        clip=clip,
        once=once,
        fps=args.fps,
        ppm=args.ppm,
        cell=args.cell,
        ground=args.ground,
        ground_px=args.ground_px,
        root_motion=args.root_motion,
        supersample=args.supersample,
        reduce=args.reduce,
        edges=args.edges,
        settings_from=args.settings_from,
        previews=(
            not args.no_preview
            if "previews" in explicit
            else layered.DEFAULTS["previews"]
        ),
        work_dir=args.work_dir,
        blender=args.blender,
        any_blender=args.any_blender,
        explicit=explicit,
        palette_file=args.palette,
        no_palette=args.no_palette,
        materials_file=args.materials,
        no_materials=args.no_materials,
        ao_distance=args.ao_distance,
        ao_samples=args.ao_samples,
        occlusion_weight=args.occlusion_weight,
        convexity_weight=args.convexity_weight,
        shade_range=args.shade_range,
        shade_mode=args.shade_mode,
        ambient_form=(
            not args.no_ambient_form
            if "ambient_form" in explicit
            else layered.DEFAULTS["shade.ambient_form"]
        ),
        key_direction=args.key_direction,
        key_strength=args.key_strength,
        sky_strength=args.sky_strength,
        ground_strength=args.ground_strength,
        sky_ground_frame=args.sky_ground_frame,
        brightness_floor=args.brightness_floor,
        brightness_ceiling=args.brightness_ceiling,
        shade_snap=args.shade_snap,
        dither_pattern=args.dither_pattern,
        dither_strength=args.dither_strength,
        config=args.config,
        no_user_config=args.no_user_config,
        project=args.project,
        frames=args.frames,
        normals=(
            not args.no_normals
            if "normals" in explicit
            else layered.DEFAULTS["normals"]
        ),
        depth=(not args.no_depth if "depth" in explicit else layered.DEFAULTS["depth"]),
        light=args.light,
        light_intensity=args.light_intensity,
        light_ambient=args.light_ambient,
        ramp_step=args.ramp_step,
        ramp_hue_shift=args.ramp_hue_shift,
        ramp_fade=args.ramp_fade,
        preset=args.view,
    )


@dataclass(frozen=True)
class ReusedSettings:
    """The values `--settings-from` reuses, named as in `Options`.

    `view` is a preset name or `custom`, with the view's recorded direction,
    direction count and start angle; `projection`, `roll` and
    `camera_position` are the camera's recorded projection, roll and
    position. Scale, cell and ground pixel are always set: reuse makes them
    fixed. `clip` is the recorded clip selection, in sheet order, and `once`
    the one-shot clips among it.
    """

    view: str
    direction: tuple[float, float, float]
    directions: int
    start_angle: float
    projection: str
    roll: float
    camera_position: tuple[float, float, float] | None
    model_yaw: float
    fps: float
    supersample: int
    ppm: float
    cell: tuple[int, int]
    ground: tuple[float, float, float]
    ground_px: tuple[int, int]
    root_motion: str
    previews: bool
    normals: bool
    depth: bool
    light: tuple[float, float, float] | None
    light_intensity: float
    light_ambient: float
    ramp_step: float
    ramp_hue_shift: float
    ramp_fade: float
    clip: tuple[str, ...]
    once: tuple[str, ...]
    frames: int | str
    clip_frames: MappingProxyType
    reduce: str
    edges: str
    shade_range: tuple[int, int]
    ao_distance: float
    ao_samples: int
    occlusion_weight: float
    convexity_weight: float
    shade_mode: str
    ambient_form: bool
    key_direction: tuple[float, float, float]
    key_strength: float
    sky_strength: float
    ground_strength: float
    sky_ground_frame: str
    brightness_floor: float
    brightness_ceiling: float
    shade_snap: str
    dither_pattern: str
    dither_strength: float
    palette: PaletteRecord | None = None
    materials: MaterialsRecord | None = None


def resolve_settings(options: Options, environ=None) -> Options:
    """Lay the settings layers under `options`, then resolve the palette and
    material library bytes and check the combination, all before Blender.

    The layers, lowest first, are the shipped defaults, the global file (the
    user file, or the one `--config` names; none with `--no-user-config`), a
    loaded sheet (`--settings-from`), the project file (`--project`), then
    the command line (design §CLI, Settings files; projects and camera design
    D-11). Every file is read and checked before any value is used. A project
    value acts as its explicit option would, including against a loaded
    sheet. The global file and the defaults are only defaults: a loaded sheet
    records every setting they hold, so they apply only without one, except
    the app settings, which no sheet records. The view resolves layer by
    layer (`_resolve_view`). `environ` locates the user file and the project
    files; it is `os.environ` by default. Only the palette and library that
    survive the merge are read.
    """
    environ = os.environ if environ is None else environ
    defaults, global_, projects = _read_layers(options, environ)
    command_line_view = _command_line_view(options)
    given = options.explicit
    options = _apply_layer(
        options, layered.merge(*(values for _, values in projects)), projects
    )
    reused = reused_colors = None
    clip_layers = [] if global_ is None else [global_[1].get("clips", {})]
    if options.settings_from is not None:
        reused = read_settings(options.settings_from)
        options = apply_settings(options, reused)
        if reused.palette is not None:
            reused_colors = reused.palette.colors
        clip_layers.append(
            {name: {"frames": count} for name, count in reused.clip_frames.items()}
        )
        options = _apply_defaults(options, defaults, global_, layered.APP_SETTINGS)
    else:
        options = _apply_defaults(options, defaults, global_)
    view_layers = [("the shipped defaults", defaults)]
    if global_ is not None:
        view_layers.append(global_)
    if reused is not None:
        view_layers = [("--settings-from", reused)]
    options = _resolve_view(options, [*view_layers, *projects, command_line_view])
    _check_camera(options)
    # Each clip's own frame count merges by clip name, the loaded sheet's
    # included, a higher layer's null clearing a lower one's count; per-clip
    # values come from files and the sheet only (settings design D-17, D-39).
    clip_layers += [values.get("clips", {}) for _, values in projects]
    merged = {
        name: leaves["frames"]
        for name, leaves in layered.merge_clips(*clip_layers).items()
        if "frames" in leaves
    }
    options = replace(options, clip_frames=MappingProxyType(merged))
    options = _resolve_palette(options)
    options = _resolve_materials(options, reused_colors)
    return _resolve_shading(options, given, global_, projects)


def _resolve_shading(options, given, global_, projects):
    """Resolve the shading response of the merged `options` with its library
    and check the combination, before Blender (shading design contract 2).

    `given` is what the command line set, as `Options.explicit` held it
    before any file did; `global_` and `projects` are the global file's and
    the project files' `(label, layer)`. Every cross-field rule is checked on
    the resolved values, each failure naming every value it involves and where
    it came from: an option, a settings file and line, a loaded sheet, a
    library, or the shipped default.
    """
    projected = layered.origins(projects)
    globally = {} if global_ is None else layered.origins([global_])
    origins = {}
    for path, field, option in (*_SHADE_VALUES, *_SHADING):
        name = f"shade.{path}"
        if field in given:
            # The ambient form is one setting with two options.
            negated = field == "ambient_form" and not options.ambient_form
            origins[name] = "--no-ambient-form" if negated else option
        elif name in projected:
            origins[name] = projected[name]
        elif options.settings_from is not None:
            origins[name] = f"--settings-from {str(options.settings_from)!r}"
        elif name in globally:
            origins[name] = globally[name]
    library = None if options.materials is None else options.materials.library
    try:
        resolved = shading_resolve.resolve(
            _shading_values(options),
            library,
            has_palette=options.palette is not None,
            origins=origins,
        )
    except shading_model.ShadingError as error:
        _build_parser()[0].error("; ".join(error.problems))
    return replace(options, shading=resolved, shading_origins=MappingProxyType(origins))


def _shading_values(options):
    """The checked values of the global shade settings in `options`, named as
    the settings are, which `shading_resolve.resolve` takes."""
    return {
        f"shade.{path}": getattr(options, field)
        for path, field, _ in (*_SHADE_VALUES, *_SHADING)
    }


def _check_camera(options):
    """Refuse a perspective camera without a position, or with the ground
    point not in front of it, `d = −position · f` 0 or less (projects and
    camera design D-10, D-16), before Blender runs."""
    if options.projection != backend.PERSPECTIVE:
        return
    parser = _build_parser()[0]
    if options.camera_position is None:
        parser.error(
            "the perspective camera needs a position: give --camera-position "
            "X,Y,Z or camera.position, in meters from the ground point"
        )
    depth = views.perspective(
        options.direction, options.roll, options.camera_position
    ).ground[2]
    if not depth > 0:
        parser.error(
            f"the perspective camera at {_coordinates(options.camera_position)} "
            f"from the ground point, looking along {_coordinates(options.direction)}, "
            f"has the ground point {depth!r} m in front of it: the ground point "
            "must be in front of the camera"
        )


def _read_layers(options, environ):
    """The shipped defaults, the global file's label and layer (or None),
    and the project file's label and layer in a list, empty without
    `--project`. A missing `--config` file or project file is an error; a
    missing user file is not. Nothing is created."""
    parser = _build_parser()[0]
    try:
        defaults = layered.read_defaults()
        global_ = None
        if options.config is not None:
            label = f"--config {str(options.config)!r}"
            global_ = (
                label,
                layered.read_file(options.config, source=label, required=True),
            )
        elif not options.no_user_config:
            path = layered.user_file(environ)
            label = f"the user settings {str(path)!r}"
            values = layered.read_file(path, source=label, required=False)
            global_ = None if values is None else (label, values)
        projects = []
        if options.project is not None:
            path = layered.project_file(environ, options.project)
            label = f"--project {options.project!r} ({str(path)!r})"
            projects.append(
                (label, layered.read_file(path, source=label, required=True))
            )
    except layered.SettingsError as error:
        parser.error(str(error))
    return defaults, global_, projects


def _apply_layer(options, values, sources, mark=True):
    """Set the `Options` fields of each setting in `values` that the command
    line did not, as its option would. With `mark`, the settings join
    `explicit`; a null palette or library then drops a reused one, as
    `--no-palette` and `--no-materials` do. `sources` are the layers'
    `(label, values)`, lowest first, to name the file that set a path."""
    explicit = set(options.explicit)
    changes = {}
    origins = dict(options.origins)
    for name, value in values.items():
        if name == "clips" or name in layered.VIEW_SETTINGS:
            continue
        if name not in _PATH_FIELDS:
            field = _SETTING_FIELDS.get(name, name)
            if field not in explicit:
                changes[field] = value
                if mark:
                    explicit.add(field)
                if layered.SCHEMA[name].path and value is not None:
                    origins[name] = _where(sources, name)
            continue
        path_field, none_field = _PATH_FIELDS[name]
        if explicit & {name, none_field}:
            continue
        if value is not None or mark:
            origins[name] = _where(sources, name)
        changes[path_field] = value
        changes[none_field] = mark and value is None
        if mark:
            explicit.add(name if value is not None else none_field)
    if not changes:
        return options
    return replace(
        options,
        explicit=frozenset(explicit),
        origins=MappingProxyType(origins),
        **changes,
    )


def _where(sources, name):
    """The settings file, key and line of the highest of `sources` that sets
    `name`, as errors name it."""
    label, layer = next(
        (label, layer) for label, layer in reversed(sources) if name in layer
    )
    line, column = layer.where[name]
    return f"{label}: {name} (line {line}, column {column})"


def _apply_defaults(options, defaults, global_, names=None):
    """The global file's settings, then the shipped defaults, for what
    neither the command line nor a project file set: all of them without a
    loaded sheet, or only `names`, the app settings, with one."""
    sources = [("the shipped defaults", defaults)]
    if global_ is not None:
        sources.append(global_)
    merged = layered.merge(*(values for _, values in sources))
    if names is not None:
        merged = layered.Layer({name: merged[name] for name in names if name in merged})
    return _apply_layer(options, merged, sources, mark=False)


def _command_line_view(options):
    """The command line's view settings as a layer: `--view`, then the
    direction `--pitch` or `--camera-direction` sets, `--directions` and
    `--start-angle`, each only when given."""
    explicit = options.explicit
    values = {"view": options.preset} if "view" in explicit else {}
    if explicit & {"pitch", "direction"}:
        values["camera.direction"] = options.direction
    values |= {
        name: getattr(options, name)
        for name in ("directions", "start_angle")
        if name in explicit
    }
    return ("the command line", layered.Layer(values))


def _resolve_view(options, layers):
    """Resolve the view through `layers`, `(label, values)` from the weakest
    (projects and camera design D-16, *How they resolve*).

    The view is a preset marker and three values, the direction, the
    direction count and the start angle, each the preset's or an override.
    A layer sets the direction with `pitch`, the direction it gives, or
    `camera.direction`, never both (`settings.read_bytes`). A loaded
    sheet, given as its `ReusedSettings`, is a snapshot: its recorded marker,
    `custom` included, and its values, each counted as the preset's. Within a
    layer, a `view` applies first and sets every value to its preset's; then
    a non-null value is an override, and a `null` resets that value to the
    preset's. A `null` while the marker is `custom` has no preset to reset to,
    a usage error naming the file and key, unless the same layer gives a
    `view`. The resolved marker is the preset's name when no value is an
    override, else `custom`.
    """
    preset, values, overrides = None, {}, set()
    for label, layer in layers:
        if isinstance(layer, ReusedSettings):
            preset = layer.view
            values = {name: getattr(layer, name) for name in _VIEW_VALUES}
            overrides.clear()
            continue
        if "view" in layer:
            preset = layer["view"]
            values = {name: getattr(PRESETS[preset], name) for name in _VIEW_VALUES}
            overrides.clear()
        given = {}
        for name, key in _VIEW_KEYS:
            if key in layer:
                value = layer[key]
                if key == "pitch" and value is not None:
                    value = views.pitch_direction(value)
                given[name] = value
        for name, value in given.items():
            if value is not None:
                values[name] = value
                overrides.add(name)
                continue
            if preset == CUSTOM_VIEW:
                key = next(key for key in _view_keys(name) if key in layer)
                line, column = layer.where[key]
                _build_parser()[0].error(
                    f"{label}: {key} (line {line}, column {column}): null takes "
                    "the view's preset value, but the loaded sheet's view is "
                    "custom, with no preset; give a view in the same file"
                )
            values[name] = getattr(PRESETS[preset], name)
            overrides.discard(name)
    return replace(options, view=CUSTOM_VIEW if overrides else preset, **values)


# Each view value with the layer keys that set it, as `(value, key)`: the
# direction from `pitch`, as the direction it gives, or `camera.direction`.
_VIEW_KEYS = (
    ("direction", "pitch"),
    ("direction", "camera.direction"),
    ("directions", "directions"),
    ("start_angle", "start_angle"),
)


def _view_keys(name):
    return [key for value, key in _VIEW_KEYS if value == name]


_UNREADABLE = (OSError, ValueError, RuntimeError)


def _unreadable(error):
    """Why a palette or library file cannot be read: any `OSError`, such as
    a missing file, a directory, no permission, a name too long or a loop of
    links, or a path the file system cannot name (`ValueError`, including
    `UnicodeError`, or `RuntimeError`)."""
    return f"cannot be read: {getattr(error, 'strerror', None) or error}"


def _origin(options, name, option):
    """How errors name the source of a palette or library setting: `option`
    when the command line gave it, else the settings file, key and line."""
    return options.origins.get(name, option)


def _resolve_palette(options: Options) -> Options:
    if options.palette_file is not None:
        path = options.palette_file
        name = _origin(options, "palette", "--palette")
        try:
            source = _palette_source(path.name)
        except argparse.ArgumentTypeError as error:
            _build_parser()[0].error(f"{name} {str(path)!r}: {error}")
        try:
            data = path.read_bytes()
        except _UNREADABLE as error:
            _build_parser()[0].error(f"{name} {str(path)!r}: {_unreadable(error)}")
        try:
            colors = palette.read_palette_bytes(data, source=path)
        except palette.PaletteError as error:
            _build_parser()[0].error(f"{name} {error}")
        options = replace(
            options,
            palette=PaletteRecord(source, hashlib.sha256(data).hexdigest(), colors),
        )
    elif options.no_palette:
        options = replace(options, palette=None)
    return options


def _resolve_materials(options: Options, reused_colors) -> Options:
    """Settle the material library: an explicit file is read once and
    validated against the palette in force, `--no-materials` drops a reused
    library, and a reused library is kept only with the palette colours it
    was recorded for (design §CLI, D-24).

    `reused_colors` are the ordered colours of the reused palette, if any,
    before an explicit option replaced it. A dropped or replaced library is
    never checked against the palette in force.
    """
    parser = _build_parser()[0]
    colors = None if options.palette is None else options.palette.colors
    if options.materials_file is not None:
        path = options.materials_file
        name = _origin(options, "materials", "--materials")
        try:
            materials.check_path(path)
        except materials.LibraryError as error:
            parser.error(f"{name} {error}")
        if colors is None:
            parser.error(
                f"{name} {str(path)!r}: a library needs a palette; give "
                "--palette FILE or reuse a sheet with one"
            )
        try:
            source = _palette_source(path.name)
        except argparse.ArgumentTypeError as error:
            parser.error(f"{name} {str(path)!r}: {error}")
        try:
            data = path.read_bytes()
        except _UNREADABLE as error:
            parser.error(f"{name} {str(path)!r}: {_unreadable(error)}")
        try:
            library = materials.read_library_bytes(data, colors, source=path)
        except materials.LibraryError as error:
            parser.error(f"{name} {error}")
        library = materials.generate(library, colors, _formula(options))
        return replace(
            options,
            materials=MaterialsRecord(
                source, hashlib.sha256(data).hexdigest(), library
            ),
        )
    if options.no_materials:
        return replace(options, materials=None)
    if options.materials is None:
        return options
    if colors is None:
        parser.error(
            f"{_origin(options, 'palette', '--no-palette')}: the reused material "
            "library needs a palette; also give --no-materials to drop it"
        )
    if colors != reused_colors:
        parser.error(
            f"{_origin(options, 'palette', '--palette')} "
            f"{str(options.palette_file)!r}: its colours differ from "
            "the reused palette the reused material library was written for; "
            "also give --materials FILE, or --no-materials to drop the library"
        )
    # A reused generated ramp keeps its recorded indices unless an explicit
    # value changes its effective formula (material styling design D-33).
    record = options.materials
    library = materials.generate(
        record.library, colors, _formula(options), recorded=record.formula
    )
    return replace(options, materials=replace(record, library=library))


def _formula(options):
    """The global formula values of generated ramps in force, by name."""
    return {
        "lightness_step": options.ramp_step,
        "hue_shift_deg": options.ramp_hue_shift,
        "chroma_fade": options.ramp_fade,
    }


def read_settings(path) -> ReusedSettings:
    """Read and check the reusable `settings` of the sheet description at
    `path`. Reading that file is the only effect.

    Raises `UsageError`, reported as `parse_args` reports one, naming the
    file and the problem: the file cannot be read, is not UTF-8 JSON, repeats
    a key, is not a `SHEET_SCHEMA` document with a `settings` object
    (another sheet schema is named), or its `settings` has a missing, unknown
    or unacceptable field. Every field is checked as its option checks it,
    including fields an explicit option will replace: the style, with a
    recorded material library checked against the recorded palette, the
    previews and normals flags, and the clip selection, a nonempty list of distinct clips
    each with exactly a name, a loop flag and its own frame count as given:
    a count of 1 or more (never a boolean), `"auto"`, or null to take the
    global count. Nothing beyond `schema` and `settings` is read.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        _settings_error(path, f"cannot be read: {error.strerror or error}")
    try:
        document = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_keys,
            parse_constant=_no_constant,
        )
    except UnicodeDecodeError as error:
        _settings_error(path, f"is not UTF-8: {error.reason} at byte {error.start}")
    except _DuplicateKey as error:
        _settings_error(path, str(error))
    except ValueError as error:
        _settings_error(path, f"is not valid JSON: {error}")
    except RecursionError:
        _settings_error(path, "is not valid JSON: it is nested too deeply")
    not_a_sheet = f"is not a {SHEET_SCHEMA} document"
    if not isinstance(document, dict):
        _settings_error(path, f"{not_a_sheet}: not a JSON object")
    if "schema" not in document:
        _settings_error(path, f"{not_a_sheet}: schema is missing")
    schema = document["schema"]
    if isinstance(schema, str) and schema.startswith(_SHEET_PREFIX):
        if schema != SHEET_SCHEMA:
            _settings_error(
                path,
                f"is a {schema} sheet; only {SHEET_SCHEMA} sheets load, so "
                "generate it again",
            )
    else:
        _settings_error(path, f"{not_a_sheet}: schema is {_shown(schema)}")
    if "settings" not in document:
        _settings_error(path, "settings: missing")
    problems = []
    checked = _check_shape(_SETTINGS, document["settings"], "settings", problems)
    if not problems:
        checked["style"] = _style(checked["style"], problems)
    if problems:
        _settings_error(path, "; ".join(problems))
    view, camera, cell, ground, ground_px, shade, style = (
        checked[name]
        for name in (
            "view",
            "camera",
            "cell",
            "ground_m",
            "ground_px",
            "shade",
            "style",
        )
    )
    return ReusedSettings(
        view=view["preset"],
        direction=camera["direction"],
        directions=view["directions"],
        start_angle=view["start_angle_deg"],
        projection=camera["projection"],
        roll=camera["roll"],
        camera_position=camera["position"],
        model_yaw=checked["model_yaw_deg"],
        fps=checked["fps"],
        supersample=checked["supersample"],
        ppm=checked["pixels_per_meter"],
        cell=(cell["width"], cell["height"]),
        ground=(ground["x"], ground["y"], ground["z"]),
        ground_px=(ground_px["x"], ground_px["y"]),
        root_motion=checked["root_motion"],
        previews=checked["previews"],
        normals=checked["normals"],
        depth=checked["depth"],
        light=checked["light"]["position"],
        light_intensity=checked["light"]["intensity"],
        light_ambient=checked["light"]["ambient"],
        ramp_step=checked["ramp"]["lightness_step"],
        ramp_hue_shift=checked["ramp"]["hue_shift_deg"],
        ramp_fade=checked["ramp"]["chroma_fade"],
        frames=checked["frames"],
        clip_frames=MappingProxyType(
            {entry["name"]: entry["frames"] for entry in checked["clips"]}
        ),
        clip=tuple(entry["name"] for entry in checked["clips"]),
        once=tuple(entry["name"] for entry in checked["clips"] if not entry["loop"]),
        reduce=style["reduce"],
        edges=style["edges"],
        shade_range=shade["range"],
        ao_distance=shade["ao_distance_m"],
        ao_samples=shade["ao_samples"],
        occlusion_weight=shade["occlusion_weight"],
        convexity_weight=shade["convexity_weight"],
        shade_mode=shade["mode"],
        ambient_form=shade["ambient_form"],
        key_direction=shade["key"]["direction"],
        key_strength=shade["key"]["strength"],
        sky_strength=shade["sky"]["strength"],
        ground_strength=shade["ground"]["strength"],
        sky_ground_frame=shade["sky_ground_frame"],
        brightness_floor=shade["brightness"]["floor"],
        brightness_ceiling=shade["brightness"]["ceiling"],
        shade_snap=shade["snap"],
        dither_pattern=shade["dither"]["pattern"],
        dither_strength=shade["dither"]["strength"],
        palette=style["palette"],
        materials=(
            None
            if style["materials"] is None
            else replace(
                style["materials"],
                formula=MappingProxyType(
                    {name: checked["ramp"][name] for name in materials.FORMULA}
                ),
            )
        ),
    )


def apply_settings(options: Options, reused: ReusedSettings) -> Options:
    """Merge `reused` into `options`; an explicit option wins over its
    reused value.

    The view is left as it is: `_resolve_view` lays the reused view under
    the project's and the command line's. An explicit `--clip` replaces the
    reused clip selection and its one-shot marks, and `--once` then comes
    from the command line. Without
    `--clip`, the reused clips stay, and an explicit `--once` replaces their
    marks: it must name only reused clips, else this is a usage error.
    `explicit` stays as given.
    """
    explicit = options.explicit
    names = [
        field.name
        for field in fields(ReusedSettings)
        if field.name not in ("clip", "once", "clip_frames", "view", *_VIEW_VALUES)
    ]
    values = {name: getattr(reused, name) for name in names if name not in explicit}
    if "clip" not in explicit:
        values["clip"] = reused.clip
        if "once" not in explicit:
            values["once"] = reused.once
        for name in options.once:
            if name not in reused.clip:
                _build_parser()[0].error(
                    f"argument --once: {name!r} is not among the loaded sheet's "
                    f"clips: {', '.join(map(repr, reused.clip))}"
                )
    return replace(options, **values)


def capture_settings(options: Options) -> backend.Settings:
    """The resolved settings capture and export share, from merged `options`.

    They hold no style: `style_record` gives that, and it stays out of the
    capture job.
    """
    return backend.Settings(
        view=options.view,
        projection=options.projection,
        direction=options.direction,
        roll=options.roll,
        position=options.camera_position,
        directions=options.directions,
        start_angle=options.start_angle,
        model_yaw=options.model_yaw,
        fps=options.fps,
        supersample=options.supersample,
        ppm=options.ppm,
        cell=options.cell,
        ground=options.ground,
        ground_px=options.ground_px,
        root_motion=options.root_motion,
        frames=options.frames,
        shade=backend.Shade(
            ao_distance_m=options.ao_distance,
            ao_samples=options.ao_samples,
            occlusion_weight=options.occlusion_weight,
            convexity_weight=options.convexity_weight,
        ),
    )


def style_record(options: Options) -> dict:
    """The sheet's ordered look record, independent of capture settings:
    `reduce`, `edges`, `palette` and `materials` (the library snapshot, or
    `None`), in that order. The shade range is a setting, recorded in
    `settings.shade`."""
    record = options.palette
    return {
        "reduce": options.reduce,
        "edges": options.edges,
        "palette": None
        if record is None
        else {
            "source": record.source,
            "sha256": record.sha256,
            "colors": ["#" + bytes(color).hex() for color in record.colors],
        },
        "materials": None
        if options.materials is None
        else _materials_document(options.materials),
    }


def _materials_document(record: MaterialsRecord) -> dict:
    """The library snapshot as the sheet records it: its source base name and
    digest, then its ramps, default and entries in name order. An entry with
    its own shading values has a `shade` after its `ramp`, `uses` or
    `ordinary`, holding only the values the library gives, in a fixed order:
    the capture values and range, then the response leaves in the settings
    table's order, `key`, `sky`, `ground`, `brightness` and `dither` as nested
    mappings of the leaves given (settings design D-37; shading design
    contract 1). An ordinary entry given as the string stays the string, and
    one given as a mapping stays a mapping, `{"ordinary": true}` with its
    `shade` when it has one, so reuse writes the same bytes."""
    library = record.library
    entries = {}
    for name, entry in library.materials.items():
        if entry.ramp is not None:
            entries[name] = {"ramp": _ramp_document(entry.ramp)}
        elif entry.uses is not None:
            entries[name] = {"uses": entry.uses}
        elif entry.ordinary_mapping:
            entries[name] = {"ordinary": True}
        else:
            entries[name] = materials.ORDINARY
            continue
        if entry.shade is not None:
            entries[name]["shade"] = entry.shade.document()
    document = {
        "source": record.source,
        "sha256": record.sha256,
        "ramps": {name: _ramp_document(ramp) for name, ramp in library.ramps.items()},
        "default": library.default,
    }
    # The library's own shade, only when it gives one (D-35).
    if library.shade is not None:
        document["shade"] = library.shade.document()
    document["materials"] = entries
    return document


def _ramp_document(ramp):
    """A ramp as the sheet records it: a hand-listed one as its list, a
    generated one as its properties as given, `base`, `bands`, its own
    formula values in a fixed order, then `indices`, its result (material
    styling design D-34)."""
    if not isinstance(ramp, materials.Generated):
        return list(ramp)
    return (
        {"base": ramp.base, "bands": ramp.bands}
        | dict(ramp.given())
        | {"indices": list(materials.indices(ramp))}
    )


def main(argv: Sequence[str] | None = None):
    """The `moskophoros` console script: run the command and exit with its
    status."""
    sys.exit(run(sys.argv[1:] if argv is None else argv))


def run(argv: Sequence[str]) -> int:
    """Run the command on `argv` and return its exit status.

    Errors are reported on stderr as `moskophoros: error: <message>`, and a
    usage error after the usage synopsis. An internal error prints its
    traceback first. An output that cannot be written returns 6, with the
    earlier outputs kept. An interruption publishes nothing, is reported as
    `interrupted` and returns 130.
    """
    try:
        try:
            options = resolve_settings(parse_args(argv))
        except SystemExit as exit:
            # Usage errors are already reported; --help exits 0.
            return exit.code
        _command(options)
        return 0
    except KeyboardInterrupt:
        _report("error", "interrupted")
        return INTERRUPTED
    except (fit.UsageError, export.UsageError, _CommandUsageError) as error:
        _build_parser()[0].print_usage(sys.stderr)
        _report("error", str(error))
        return USAGE_ERROR
    except (
        gltf.InputError,
        fit.CellOverflow,
        fit.NearOverflow,
        export.DepthOverflow,
        backend.BackendError,
        _OutputError,
    ) as error:
        _report("error", str(error))
        return error.exit_code
    except Exception:
        traceback.print_exc()
        _report("error", "internal error; this is a bug")
        return INTERNAL_ERROR


class _CommandUsageError(Exception):
    """A usage error found while running: an output or work directory that
    cannot be used. Exit classification 2."""


class _OutputError(Exception):
    """An output that could not be written, such as on a full disk or without
    permission; the earlier outputs are kept. Exit classification 6."""

    exit_code = OUTPUT_ERROR


def _report(kind, message):
    sys.stderr.write(f"{PROG}: {kind}: {message}\n")


def _command(options):
    """Run the stages for parsed and merged `options`, then publish."""
    outfile = options.outfile
    json_path = outfile.with_name(outfile.name.removesuffix(".png") + ".json")
    source, subject = _read_source(options.infile)
    if subject.material_count > backend.MAX_MATERIALS:
        raise gltf.InputError(
            options.infile,
            f"has {subject.material_count} materials; the material-ID buffer "
            f"holds at most {backend.MAX_MATERIALS}",
        )
    selected = tuple(
        replace(selected, frames=options.clip_frames.get(selected.clip.name))
        for selected in gltf.select_clips(subject, options.clip or (), options.once)
    )
    for warning in _frame_warnings(options, selected):
        _report("warning", warning)
    preview_paths = export.preview_paths(outfile, selected) if options.previews else ()
    normal_paths = [export.normal_path(outfile)] if options.normals else []
    depth_paths = [export.depth_path(outfile)] if options.depth else []
    light = export.Light(options.light, options.light_intensity, options.light_ambient)
    lit = options.previews and light.position is not None
    lit_paths = export.lit_preview_paths(outfile, selected) if lit else ()
    if light.position is not None and not options.previews:
        _report(
            "warning",
            f"the light at {_coordinates(light.position)} is recorded but unused: "
            "previews are off, so no lit preview is written",
        )
    _check_targets(
        [outfile, json_path, *normal_paths, *depth_paths, *preview_paths, *lit_paths]
    )
    view = views.View(options.directions, options.start_angle, options.model_yaw)
    requested = sampling.frames(
        subject.name, selected, view, options.fps, options.frames
    )
    settings = capture_settings(options)
    sheet_style = style_record(options)
    resolved = _resolved_shading(options)
    if options.materials is not None:
        library = options.materials.library
        for warning in materials.warnings(subject.primitive_materials, library):
            _report("warning", warning)
        for warning in materials.shadow_warnings(
            subject.primitive_materials,
            library,
            _explicit_shading(options),
            _explicit_formula(options),
            _warning_origins(options),
        ):
            _report("warning", warning)
        settings = replace(
            settings,
            shade=replace(
                settings.shade,
                materials=tuple(
                    backend.MaterialShade(*values)
                    for values in materials.capture_overrides(
                        subject.primitive_materials,
                        library,
                        {
                            "ao_distance_m": options.ao_distance,
                            "occlusion_weight": options.occlusion_weight,
                            "convexity_weight": options.convexity_weight,
                        },
                    )
                ),
            ),
        )
    found = blender.locate(
        options.blender,
        options.any_blender,
        source=_origin(options, "blender", "--blender"),
    )

    with _workspace(options.work_dir) as workspace:
        measured = blender.run_phase(
            found,
            workspace,
            backend.build_job(
                "measure",
                source,
                subject.name,
                settings,
                selected,
                requested,
                str(workspace / "measure"),
            ),
        )
        if settings.root_motion == "error":
            check_root_motion(options.infile, measured.roots)
        clip = None
        if measured.depths is not None:
            fit.check_near(
                options.infile,
                measured.measurements,
                measured.depths,
                views.NEAR_LIMIT,
            )
            clip = backend.clipping(measured.depths.values())
        fitted = fit.resolve(
            measured.measurements, options.ppm, options.cell, options.ground_px
        )
        for warning in fitted.warnings:
            _report("warning", warning)
        settings = replace(
            settings, ppm=fitted.ppm, cell=fitted.cell, ground_px=fitted.ground_px
        )
        rendered = blender.run_phase(
            found,
            workspace,
            backend.build_job(
                "render",
                source,
                subject.name,
                settings,
                selected,
                requested,
                str(workspace / "render"),
                clip,
            ),
        )
        lookup = backend.material_lookup(rendered, subject)
        generator = export.generator(rendered.backend)
        metadata = {
            "fingerprint": export.fingerprint(
                generator,
                export.sheet_settings(
                    settings,
                    selected,
                    sheet_style,
                    shade_range=options.shade_range,
                    previews=options.previews,
                    normals=options.normals,
                    depth=options.depth,
                    light=light,
                    ramp=_formula(options),
                    shading=resolved.settings,
                ),
                source.sha256,
            )
        }
        # Loaded one at a time as stylize reduces them, so only one
        # supersampled frame is held at once.
        captured = (
            _load_frame(address, paths, metadata, lookup)
            for address, paths in rendered.buffers.items()
        )
        reduce = {"plain": stylize.plain, "mode": stylize.mode}[options.reduce]
        colors = options.palette.colors if options.palette is not None else None
        identities = lookup.identities
        # Depth is reduced to sheet pixels at the sheet's scale. The shading
        # is passed whether or not a library or palette is: the stage skips
        # the response step where it would change nothing.
        scale = {
            "identities": identities,
            "pixels_per_meter": settings.ppm,
            "edges": options.edges,
            "shade_range": options.shade_range,
            "shading": resolved,
            "lights": lighting.light_vectors(
                resolved.settings.key_direction,
                resolved.settings.sky_ground_frame,
                options.direction,
                options.roll,
            ),
        }
        if colors is None:
            reduced = reduce(captured, settings.supersample, **scale)
        elif options.materials is None:
            reduced = reduce(captured, settings.supersample, palette=colors, **scale)
        else:
            reduced = reduce(
                captured,
                settings.supersample,
                palette=colors,
                library=options.materials.library,
                **scale,
            )
        frames = cleanup.passthrough(reduced)

    sheet = export.encode(
        frames,
        generator=generator,
        source=source,
        subject=subject.name,
        settings=settings,
        style=sheet_style,
        shade_range=options.shade_range,
        previews=options.previews,
        normals=options.normals,
        depth=options.depth,
        light=light,
        ramp=_formula(options),
        shading=resolved.settings,
        selected_clips=selected,
        image_path=outfile,
    )
    outputs = [(outfile, sheet.png), (json_path, sheet.json)]
    outputs += [(path, sheet.normal) for path in normal_paths]
    outputs += [(path, sheet.depth) for path in depth_paths]
    if options.previews:
        previews = export.previews(
            frames, subject=subject.name, settings=settings, selected_clips=selected
        )
        for preview in previews:
            for warning in preview.warnings:
                _report("warning", warning)
        outputs += zip(
            preview_paths, (preview.gif for preview in previews), strict=True
        )
    if lit:
        # The depth range is checked here too: the lit previews use the
        # encoded depth (lighting sheet design D-21, D-24).
        lit_previews = export.lit_previews(
            frames,
            subject=subject.name,
            settings=settings,
            selected_clips=selected,
            light=light,
        )
        for preview in lit_previews:
            for warning in preview.warnings:
                _report("warning", warning)
        outputs += zip(
            lit_paths, (preview.gif for preview in lit_previews), strict=True
        )
    publish(outputs)


def _coordinates(point):
    """`(x, y, z)` with each coordinate in its shortest form."""
    return "(" + ", ".join(repr(float(value)) for value in point) + ")"


def _frame_warnings(options, selected):
    """The frame-count warnings for the selected clips (settings design D-25,
    D-26, D-41), neither an error nor a change to the output.

    When `--frames` or a project file set the global count, one warning
    names every selected clip whose own value, a count or `auto`, beats it,
    even an equal one; a clip of zero duration and `static` are left out.
    Each of those whose own count is above 1 is named as keeping one frame.
    """
    messages = []
    still = [
        item
        for item in selected
        if item.clip.animation_index is None or item.clip.t1 == item.clip.t0
    ]
    if "frames" in options.explicit:
        own = [
            f"{json.dumps(item.clip.name, ensure_ascii=False)} ({item.frames})"
            for item in selected
            if item.frames is not None and item not in still
        ]
        if own:
            messages.append(
                f"the global frame count {options.frames} does not reach the clips "
                f"with their own: {', '.join(own)}"
            )
    for item in still:
        if isinstance(item.frames, int) and item.frames > 1:
            messages.append(
                f"clip {json.dumps(item.clip.name, ensure_ascii=False)} has no "
                f"duration and keeps one frame; its own frame count {item.frames} "
                "does not apply"
            )
    return messages


def _explicit_formula(options):
    """The global formula values an option or a project file set, by name:
    the ones a generated ramp's own value warns about (material styling
    design D-33)."""
    fields = {
        "lightness_step": "ramp_step",
        "hue_shift_deg": "ramp_hue_shift",
        "chroma_fade": "ramp_fade",
    }
    return {
        name: getattr(options, field)
        for name, field in fields.items()
        if field in options.explicit
    }


def _explicit_shading(options):
    """The global shading values an option or a project file set, by name,
    such as `range` and `key.strength`: the ones a material's or a library's
    own value warns about (settings design D-23; shading design D-41). The
    shipped defaults, the global file (the user file or the one `--config`
    replaces it with) and a loaded sheet set none. The key direction, the sky
    and ground frame and the snap target are global only, so nothing
    overrides them."""
    overridable = {path for path, _, _ in _SHADE_VALUES} | set(shading_model.FIELDS)
    return {
        path: getattr(options, field)
        for path, field, _ in (*_SHADE_VALUES, *_SHADING)
        if path in overridable and field in options.explicit
    }


def _warning_origins(options):
    """Where each global shading value came from, by name as
    `_explicit_shading` names it, for the warnings that show it."""
    return {
        name.removeprefix("shade."): origin
        for name, origin in options.shading_origins.items()
    }


def _resolved_shading(options):
    """The resolved shading of `options`: the one `resolve_settings` made, or,
    for options built without it, resolved here."""
    if options.shading is not None:
        return options.shading
    return _resolve_shading(options, options.explicit, None, []).shading


def _load_frame(address, paths, metadata, lookup):
    """The captured frame at `address` with every named buffer in `paths`:
    `color` as its pixels, `matid` and `shade` decoded through `lookup` into
    its identity and shade arrays, `normal` and `depth` into its normal and
    depth arrays, `back_normal` into its back-normal array, the front buffers
    into its front arrays and the front-normal array derived from the normal
    and the front's presence, and each other buffer under its own name."""
    pixels = imageops.load_png(paths["color"])
    identity, shade = backend.decode_frame(paths, lookup)
    normal, depth = backend.decode_normal_depth(paths)
    back_normal = backend.decode_back_normal(paths)
    front = backend.decode_front(paths, lookup)
    front_normal = backend.derive_front_normal(paths, normal, front[2])
    buffers = {
        name: imageops.load_png(path)
        for name, path in paths.items()
        if name not in ("color", *backend.AUXILIARY_BUFFERS)
    }
    buffers[sampling.IDENTITY] = identity
    buffers[sampling.SHADE] = shade
    buffers[sampling.NORMAL] = normal
    buffers[sampling.DEPTH] = depth
    buffers[sampling.BACK_NORMAL] = back_normal
    buffers[sampling.FRONT_NORMAL] = front_normal
    for name, array in zip(
        (
            sampling.FRONT_COLOR,
            sampling.FRONT_ALPHA,
            sampling.FRONT_PRESENT,
            sampling.FRONT_IDENTITY,
            sampling.FRONT_SHADE,
        ),
        front,
        strict=True,
    ):
        buffers[name] = array
    return sampling.ImageFrame(address, pixels, metadata, buffers)


def _read_source(path):
    """The capture `Source` and the `gltf.Subject` of the model at `path`.

    The digest is taken before the model is read, so a change while it is
    read is caught by capture's own digest checks.
    """
    try:
        data = path.read_bytes()
    except OSError as error:
        raise gltf.InputError(
            path, f"cannot be read: {error.strerror or error}"
        ) from None
    subject = gltf.read_glb(path)
    source = backend.Source(
        Path(os.path.abspath(path)),
        hashlib.sha256(data).hexdigest(),
        subject.scene_index,
    )
    return source, subject


def check_root_motion(path, roots):
    """Raise `gltf.InputError` for the model at `path` if any root in `roots`
    travels more than `MAX_ROOT_TRAVEL_M` across the ground."""
    travelling = [root for root in roots if root.travel_m > MAX_ROOT_TRAVEL_M]
    if not travelling:
        return
    described = []
    for root in travelling:
        node = f"node {root.node_index}"
        if root.node_name is not None:
            node += f" ({root.node_name!r})"
        described.append(
            f"clip {root.clip!r} moves its root {node} {root.travel_m!r} m "
            "across the ground"
        )
    raise gltf.InputError(
        path,
        "; ".join(described)
        + f", more than {MAX_ROOT_TRAVEL_M} m; export the clip in place, "
        "or give --root-motion keep",
    )


def _check_targets(targets):
    """Refuse output paths that cannot be published, before capture starts."""
    for target in targets:
        if not target.parent.is_dir():
            raise _CommandUsageError(
                f"the output directory {str(target.parent)!r} does not exist"
            )
        if target.is_dir() and not target.is_symlink():
            raise _CommandUsageError(f"the output {str(target)!r} is a directory")


@contextmanager
def _workspace(work_dir):
    """The capture workspace: `work_dir`, new or empty and kept afterwards,
    or a temporary directory deleted afterwards, whatever happens."""
    if work_dir is None:
        path = Path(tempfile.mkdtemp(prefix=f"{PROG}-"))
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)
        return
    path = Path(os.path.abspath(work_dir))
    shown = str(work_dir)
    if os.path.lexists(path):
        if not path.is_dir():
            raise _CommandUsageError(f"--work-dir {shown!r} is not a directory")
        try:
            empty = next(path.iterdir(), None) is None
        except OSError as error:
            raise _CommandUsageError(
                f"--work-dir {shown!r} cannot be read: {error.strerror or error}"
            ) from None
        if not empty:
            raise _CommandUsageError(
                f"--work-dir {shown!r} is not empty; give a new or empty directory"
            )
    else:
        try:
            path.mkdir(parents=True)
        except OSError as error:
            raise _CommandUsageError(
                f"--work-dir {shown!r} cannot be created: {error.strerror or error}"
            ) from None
    yield path


def publish(outputs):
    """Write each `(path, bytes)` in `outputs`, all or nothing.

    Every output is first written to a temporary file beside its target.
    Then, target by target, an existing file is moved aside and the new one
    renamed into place. If anything fails or is interrupted before every
    output is in place, each output placed is removed, each earlier file is
    moved back, and the error propagates. Once every output is in place the
    publication is complete: the earlier files are deleted, and an
    interruption then no longer stops the run. Nothing else in the output
    directories is touched.

    While publishing, an interruption is deferred to the next step, so no
    rename is ever left out of the record the rollback reads, and the
    rollback itself runs to the end. A failure to write is an `_OutputError`
    naming the output.
    """
    outputs = [(Path(target), data) for target, data in outputs]
    interrupted = []
    staged, moved, placed = [], [], []
    target = None
    with _deferred_interrupts(interrupted):
        try:
            try:
                for target, data in outputs:
                    _stop_if(interrupted)
                    staged.append((target, _stage(target, data)))
                for target, temporary in staged:
                    _stop_if(interrupted)
                    if os.path.lexists(target):
                        backup = _unused_name(target, "earlier")
                        # Recorded first: the rollback checks which renames
                        # happened.
                        moved.append((target, backup))
                        os.replace(target, backup)
                    placed.append((target, temporary))
                    os.replace(temporary, target)
                _stop_if(interrupted)
            except BaseException:
                _roll_back(placed, moved)
                raise
            finally:
                for _, temporary in staged:
                    _remove_quietly(temporary)
        except OSError as error:
            raise _OutputError(
                f"cannot write {str(target)!r}: {error.strerror or error}; "
                "earlier outputs are kept"
            ) from None
        for target, backup in moved:
            try:
                os.remove(backup)
            except OSError as error:
                _report(
                    "warning",
                    f"the earlier {str(target)!r} could not be deleted from "
                    f"{str(backup)!r}: {error.strerror or error}",
                )


@contextmanager
def _deferred_interrupts(received):
    """Record Ctrl-C in `received` instead of raising it, in the main thread,
    where Python delivers signals."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.signal(
        signal.SIGINT, lambda signum, frame: received.append(signum)
    )
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _stop_if(interrupted):
    if interrupted:
        raise KeyboardInterrupt


def _stage(target, data):
    """Write `data` to a new temporary file beside `target`; return its path.

    It is created like any new file, so the umask sets its permissions.
    """
    path = _unused_name(target, "new")
    handle = open(path, "xb")
    try:
        with handle:
            handle.write(data)
    except BaseException:
        # Only the file this call created, after a write such as on a full
        # disk fails partway.
        _remove_quietly(path)
        raise
    return path


def _unused_name(target, purpose):
    """A name beside `target`, hidden and unused, for a `purpose` file."""
    for n in count():
        path = target.with_name(f".{target.name}.{PROG}-{purpose}-{os.getpid()}-{n}")
        if not os.path.lexists(path):
            return path


def _roll_back(placed, moved):
    """Undo a partial publication: remove each output whose rename into place
    happened, then move each earlier file that was moved aside back. A step
    that fails is reported, and the rest still run."""
    for target, temporary in reversed(placed):
        if os.path.lexists(temporary):
            continue  # its rename never happened
        try:
            os.remove(target)
        except OSError as error:
            _report(
                "error",
                f"rolling back, {str(target)!r} could not be removed: "
                f"{error.strerror or error}",
            )
    for target, backup in reversed(moved):
        if not os.path.lexists(backup):
            continue  # its rename never happened
        try:
            os.replace(backup, target)
        except OSError as error:
            _report(
                "error",
                f"rolling back, the earlier {str(target)!r} could not be restored "
                f"and is kept at {str(backup)!r}: {error.strerror or error}",
            )


def _remove_quietly(path):
    try:
        os.remove(path)
    except OSError:
        pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise UsageError(message)


class _Single(argparse.Action):
    """An option that takes one value; `_prepare` rejects a repeat."""

    def __call__(self, parser, namespace, values, option_string=None):
        namespace.explicit_.add(self.dest)
        setattr(namespace, self.dest, values)


class _Flag(argparse.Action):
    """A flag; `_prepare` rejects a repeat."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=False, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        namespace.explicit_.add(self.dest)
        setattr(namespace, self.dest, True)


class _Names(argparse.Action):
    """A repeatable option collecting distinct names in the order given."""

    def __call__(self, parser, namespace, values, option_string=None):
        names = getattr(namespace, self.dest) or []
        if values in names:
            raise argparse.ArgumentError(self, f"{values!r} named more than once")
        namespace.explicit_.add(self.dest)
        setattr(namespace, self.dest, [*names, values])


def _number(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, got {text!r}") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"expected a finite number, got {text!r}")
    return value


def _integer(text):
    try:
        return int(text)
    except ValueError:
        pass
    _number(text)
    raise argparse.ArgumentTypeError(f"expected an integer, got {text!r}")


def _from_to(convert, low, high):
    def check(text):
        value = convert(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(
                f"must be from {low} to {high}, got {text!r}"
            )
        return value

    return check


def _positive(text):
    value = _number(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0, got {text!r}")
    return value


def _weight(text):
    value = _number(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or greater, got {text!r}")
    return value


def _ao_samples(text):
    value = _integer(text)
    if not 1 <= value <= backend.MAX_AO_SAMPLES:
        raise argparse.ArgumentTypeError(
            f"must be from 1 to {backend.MAX_AO_SAMPLES}, the most Blender's "
            f"ambient occlusion takes, got {text!r}"
        )
    return value


def _shade_range_option(text):
    """`LO,HI` as `(LO, HI)`: two integers with `0 <= LO < HI <= 255`."""
    parts = text.split(",")
    try:
        lo, hi = (int(part) for part in parts)
    except ValueError:
        lo = hi = None
    if lo is None or not 0 <= lo < hi <= 255:
        raise argparse.ArgumentTypeError(
            f"expected LO,HI, two integers with 0 <= LO < HI <= 255, got {text!r}"
        )
    return lo, hi


_pitch = _from_to(_number, 0, 90)
_roll = _from_to(_number, -1, 1)
_directions = _from_to(_integer, 1, 64)
_supersample = _from_to(_integer, 1, 16)
_cell_side = _from_to(_integer, 1, 4096)


def _cell(text):
    """`WxH` as `(W, H)`, or `auto` as None, the automatic cell."""
    if text == layered.AUTO:
        return None
    cell = layered.parse_cell(text)
    if cell is None:
        raise argparse.ArgumentTypeError(
            f"expected WxH, two integers each from 1 to 4096, or auto, got {text!r}"
        )
    return cell


_ambient = _from_to(_number, 0, 1)
_unit = _from_to(_number, 0, 1)
_half_turn = _from_to(_number, -180, 180)


def _light(text):
    parts = text.split(",")
    try:
        if len(parts) != 3:
            raise argparse.ArgumentTypeError(text)
        x, y, z = (_number(part) for part in parts)
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError(
            f"expected X,Y,Z, three finite numbers, got {text!r}"
        ) from None
    return x, y, z


def _camera_direction(text):
    """`X,Y,Z`, three finite numbers each from -1 to 1, not all 0, as the
    normalised direction."""
    parts = text.split(",")
    try:
        if len(parts) != 3:
            raise argparse.ArgumentTypeError(text)
        vector = tuple(_number(part) for part in parts)
    except argparse.ArgumentTypeError:
        vector = None
    if vector is None or not all(-1 <= component <= 1 for component in vector):
        raise argparse.ArgumentTypeError(
            "expected X,Y,Z, three finite numbers each from -1 to 1, not all 0, "
            f"got {text!r}"
        )
    if not any(vector):
        raise argparse.ArgumentTypeError(
            f"expected a direction, but {text!r} points nowhere"
        )
    return views.normalise(vector)


def _ground(text):
    parts = text.split(",")
    try:
        if len(parts) != 3:
            raise argparse.ArgumentTypeError(text)
        x, y, z = (_number(part) for part in parts)
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError(
            f"expected X,Y,Z, three finite numbers, got {text!r}"
        ) from None
    return x, y, z


def _whole(text):
    """A whole number 0 or greater, read exactly: `3.0` is 3, `0.5` is not."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    # Bounded like int() on decimal text, so a huge exponent cannot build a
    # huge integer.
    if not value.is_finite() or value < 0 or value.adjusted() >= _MAX_DIGITS:
        return None
    if value != value.to_integral_value():
        return None
    return int(value)


def _ppm(text):
    """Pixels per meter, or `auto` as None, the automatic scale."""
    return None if text == layered.AUTO else _positive(text)


def _ground_px(text):
    """`X,Y` as `(X, Y)`, or `auto` as None, the automatic ground pixel."""
    if text == layered.AUTO:
        return None
    parts = text.split(",")
    coordinates = [_whole(part) for part in parts]
    if len(parts) != 2 or None in coordinates:
        raise argparse.ArgumentTypeError(
            f"expected X,Y, two whole numbers 0 or greater, or auto, got {text!r}"
        )
    x, y = coordinates
    return x, y


def _path(text):
    if not text:
        raise argparse.ArgumentTypeError("expected a path, got ''")
    return Path(text)


def _project_name(text):
    if not layered.is_project_name(text):
        raise argparse.ArgumentTypeError(
            f"{text!r} is not a project name: use letters, digits, '.', '_' and "
            "'-', not starting with '.', and leave out '.yaml'"
        )
    return text


def _outfile(text):
    if not text.endswith(".png"):
        raise argparse.ArgumentTypeError(f"must end in .png, got {text!r}")
    return Path(text)


def _build_parser():
    parser = _Parser(
        prog=PROG,
        usage=USAGE,
        description="Render an animated .glb model into a pixel-art sprite sheet.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "infile", metavar="<infile.glb>", type=_path, help="input model"
    )
    parser.add_argument(
        "outfile",
        metavar="<outfile.png>",
        type=_outfile,
        help="output sheet; its JSON is written beside it",
    )

    value_options = set()

    def single(name, metavar, type, default, help, **kwargs):
        value_options.add(name)
        parser.add_argument(
            name,
            metavar=metavar,
            type=type,
            default=default,
            action=_Single,
            help=help,
            **kwargs,
        )

    views = ", ".join(PRESETS)
    single(
        "--view",
        "NAME",
        str,
        DEFAULT_VIEW,
        f"view preset: {views} (default: {DEFAULT_VIEW})",
        choices=tuple(PRESETS),
    )
    single(
        "--pitch",
        "DEG",
        _pitch,
        None,
        "camera pitch, 0 to 90: a shorthand for the camera direction "
        "(0, -sin DEG, -cos DEG) (default: from the view)",
    )
    single(
        "--projection",
        "NAME",
        str,
        layered.DEFAULTS["camera.projection"],
        f"the camera's projection: {', '.join(PROJECTIONS)}; perspective looks "
        "from --camera-position (default: "
        f"{layered.DEFAULTS['camera.projection']})",
        choices=PROJECTIONS,
    )
    single(
        "--camera-direction",
        "X,Y,Z",
        _camera_direction,
        None,
        "the way the camera looks, in subject coordinates, each -1 to 1, not "
        "all 0, normalised; cannot accompany --pitch (default: from the view)",
        dest="direction",
    )
    single(
        "--camera-roll",
        "R",
        _roll,
        layered.DEFAULTS["camera.roll"],
        "the camera's turn about the way it looks, -1 to 1, a fraction of a "
        "half turn; positive turns the picture clockwise (default: 0)",
        dest="roll",
    )
    single(
        "--camera-position",
        "X,Y,Z",
        _ground,
        layered.DEFAULTS["camera.position"],
        "the camera's position in meters from the ground point; the "
        "perspective camera needs it, and the orthographic camera records it "
        "unused (default: none)",
        dest="camera_position",
    )
    single(
        "--directions",
        "N",
        _directions,
        None,
        "direction count, 1 to 64 (default: from the view)",
    )
    single(
        "--start-angle",
        "DEG",
        _number,
        None,
        "angle of direction 0 (default: from the view)",
    )
    single(
        "--model-yaw",
        "DEG",
        _number,
        0.0,
        "corrects a model that does not face +Z (default: 0)",
    )
    for name, help in (
        ("--clip", "select a clip; repeatable, in sheet order (default: every clip)"),
        ("--once", "mark a selected clip as one-shot; repeatable (default: none)"),
    ):
        value_options.add(name)
        parser.add_argument(name, metavar="NAME", action=_Names, help=help)
    single(
        "--fps",
        "N",
        _positive,
        layered.DEFAULTS["fps"],
        "target sampling rate, greater than 0 (default: 12)",
    )
    single(
        "--frames",
        "N",
        _frames_option,
        layered.DEFAULTS["frames"],
        "how many frames each clip is sampled to, retimed so each lasts 1/fps, "
        "1 or more, or auto: sampled by duration; a settings file's clips "
        "mapping may give a clip its own (default: auto)",
    )
    single(
        "--ppm",
        "N",
        _ppm,
        None,
        "pixels per meter, greater than 0, or auto: fitted; auto drops a reused "
        "or configured value (default: auto)",
    )
    single(
        "--cell",
        "WxH",
        _cell,
        layered.DEFAULTS["cell"],
        "cell size in pixels, each 1 to 4096, or auto; unless --ppm is given or "
        "reused, the model is scaled to fit the cell, so a smaller cell gives "
        "smaller, chunkier sprites; --cell with --ppm fixes both; auto drops a "
        "reused or configured cell (default: reused by --settings-from, else "
        "fitted to the model with --ppm, else 64x64)",
    )
    single(
        "--ground",
        "X,Y,Z",
        _ground,
        (0.0, 0.0, 0.0),
        "ground point in subject coordinates, meters (default: 0,0,0)",
    )
    single(
        "--ground-px",
        "X,Y",
        _ground_px,
        None,
        "cell pixel corner the ground point lands on, or auto: fitted; auto "
        "drops a reused or configured value (default: auto)",
    )
    single(
        "--root-motion",
        "MODE",
        str,
        "error",
        "error or keep (default: error)",
        choices=ROOT_MOTION_MODES,
    )
    single(
        "--supersample",
        "N",
        _supersample,
        8,
        "capture resolution multiplier, 1 to 16 (default: 8)",
    )
    single(
        "--reduce",
        "NAME",
        str,
        REDUCTIONS[0],
        f"pixel reduction: {', '.join(REDUCTIONS)} (default: {REDUCTIONS[0]})",
        choices=REDUCTIONS,
    )
    defaults = layered.DEFAULTS
    single(
        "--edges",
        "RULE",
        str,
        defaults["edges"],
        "how a pixel's alpha comes from its supersampled block: hard, a pixel "
        "shows when half its block shows a surface, keeping outlines crisp; "
        "soft, its alpha is the block's mean alpha, so outlines and cut-out "
        f"edges keep partial alpha (default: {defaults['edges']})",
        choices=layered.EDGES,
    )
    single(
        "--ao-distance",
        "M",
        _positive,
        defaults["shade.ao_distance_m"],
        "how far ambient occlusion looks for other surfaces, in meters, greater "
        "than 0 (default: 0.3)",
    )
    single(
        "--ao-samples",
        "N",
        _ao_samples,
        defaults["shade.ao_samples"],
        f"ambient occlusion samples per pixel, 1 to {backend.MAX_AO_SAMPLES} "
        "(default: 64)",
    )
    single(
        "--occlusion-weight",
        "W",
        _weight,
        defaults["shade.occlusion_weight"],
        "how much occlusion by other surfaces lightens the shade, 0 or greater "
        "(default: 0.25)",
    )
    single(
        "--convexity-weight",
        "W",
        _weight,
        defaults["shade.convexity_weight"],
        "how much a surface's own convexity lightens the shade, 0 or greater "
        "(default: 1.0)",
    )
    single(
        "--shade-range",
        "LO,HI",
        _shade_range_option,
        defaults["shade.range"],
        "the 8-bit shade values a material's ramp spans, 0 <= LO < HI <= 255 "
        "(default: 84,191)",
    )
    single(
        "--shade-mode",
        "NAME",
        str,
        defaults["shade.mode"],
        "what the shading signal changes: ramp selects ramp entries, "
        "brightness scales the unshaded base colour, both selects then "
        "scales, neither does neither; a material may override it "
        f"(default: {defaults['shade.mode']})",
        choices=shading_model.MODES,
        dest="shade_mode",
    )
    parser.add_argument(
        "--ambient-form",
        action=_Flag,
        help="use the ambient form term of the shade, also over a sheet or "
        "settings file without it (default: on)",
    )
    parser.add_argument(
        "--no-ambient-form",
        action=_Flag,
        help="leave the ambient form out, so a directional term shades alone "
        "(default: off)",
    )
    single(
        "--bake-key-direction",
        "X,Y,Z",
        _camera_direction,
        defaults["shade.key.direction"],
        "toward the key light in the camera's frame, x screen right, y up and "
        "z toward the viewer, each -1 to 1, not all 0, normalised "
        "(default: -0.6,0.7,0.7)",
        dest="key_direction",
    )
    for name, dest, key, what in (
        ("--bake-key-strength", "key_strength", "key", "the key light's share"),
        ("--bake-sky-strength", "sky_strength", "sky", "the sky light's share"),
        (
            "--bake-ground-strength",
            "ground_strength",
            "ground",
            "the ground light's share",
        ),
    ):
        single(
            name,
            "S",
            _unit,
            defaults[f"shade.{key}.strength"],
            f"{what}, 0 to 1; the key, sky and ground shares add to at most 1; "
            "a material may override it (default: 0)",
            dest=dest,
        )
    single(
        "--bake-sky-ground-frame",
        "NAME",
        str,
        defaults["shade.sky_ground_frame"],
        "the frame the sky and ground lights follow: camera, the picture's "
        "up, or world, the subject's up (default: camera)",
        choices=shading_model.FRAMES,
        dest="sky_ground_frame",
    )
    single(
        "--brightness-floor",
        "G",
        _unit,
        defaults["shade.brightness.floor"],
        "the least brightness gain, 0 to 1, at most the ceiling; a material "
        "may override it (default: 0.3)",
        dest="brightness_floor",
    )
    single(
        "--brightness-ceiling",
        "G",
        _unit,
        defaults["shade.brightness.ceiling"],
        "the greatest brightness gain, 0 to 1, at least the floor; a material "
        "may override it (default: 1)",
        dest="brightness_ceiling",
    )
    single(
        "--shade-snap",
        "TARGET",
        str,
        defaults["shade.snap"],
        "snap the brightness and both modes' colours to the material's ramp "
        "(ramp) or the whole palette (palette); needs a palette "
        "(default: off)",
        choices=shading_model.SNAPS,
        dest="shade_snap",
    )
    single(
        "--dither-pattern",
        "NAME",
        str,
        defaults["shade.dither.pattern"],
        f"dither with a fixed pattern: {', '.join(shading_model.PATTERNS)}; a "
        "material may override it (default: off)",
        choices=shading_model.PATTERNS,
        dest="dither_pattern",
    )
    single(
        "--dither-strength",
        "S",
        _unit,
        defaults["shade.dither.strength"],
        "how far the pattern moves a pixel toward its second choice, 0 to 1; a "
        "material may override it (default: 1)",
        dest="dither_strength",
    )
    single(
        "--ramp-step",
        "L",
        _unit,
        defaults["ramp.lightness_step"],
        "how much OKLab lightness each shade of a library's generated ramps "
        "drops, 0 to 1 (default: 0.12)",
    )
    single(
        "--ramp-hue-shift",
        "DEG",
        _half_turn,
        defaults["ramp.hue_shift_deg"],
        "how far each shade of a generated ramp turns the hue, degrees, -180 "
        "to 180 (default: -12)",
    )
    single(
        "--ramp-fade",
        "F",
        _unit,
        defaults["ramp.chroma_fade"],
        "how much chroma a generated ramp loses by its darkest shade, 0 to 1 "
        "(default: 0.3)",
    )
    single(
        "--palette",
        "FILE",
        _path,
        None,
        "map colours to a HEX, GPL or PNG palette (default: none)",
    )
    parser.add_argument(
        "--no-palette",
        action=_Flag,
        help="use no palette, dropping a reused or configured one (default: off)",
    )
    single(
        "--materials",
        "FILE",
        _path,
        None,
        "draw materials from the ramps of a YAML moskophoros.materials/4 "
        "library (moskophoros.materials/3 and /2 still load): ramps listed as "
        "palette indices or generated from a base colour, and entries that "
        "may give their own shading values; needs a palette (default: none)",
    )
    parser.add_argument(
        "--no-materials",
        action=_Flag,
        help="use no material library, dropping a reused or configured one "
        "(default: off)",
    )
    single(
        "--settings-from",
        "FILE",
        _path,
        None,
        "load every setting of an earlier sheet's JSON, a "
        f"{SHEET_SCHEMA} sheet (default: none)",
    )
    single(
        "--config",
        "FILE",
        _path,
        None,
        "use FILE as the global settings file, in place of the user file, "
        "$XDG_CONFIG_HOME/moskophoros/config.yaml, else "
        "~/.config/moskophoros/config.yaml. A settings file may set the view, "
        "pitch or camera.direction, camera.projection, camera.roll, "
        "camera.position, directions, "
        "start_angle, model_yaw, ppm, cell, ground, "
        "ground_px, supersample, reduce, root_motion, fps, frames, clips, "
        "palette, materials, edges, previews, normals, depth, light, shade, "
        "ramp, and the app settings blender and any_blender. The global file "
        "and the shipped defaults give the defaults, below any loaded sheet "
        "(default: the user file)",
    )
    parser.add_argument(
        "--no-user-config",
        action=_Flag,
        help="use no global settings file: skip the user file; cannot accompany "
        "--config (default: off)",
    )
    single(
        "--project",
        "NAME",
        _project_name,
        None,
        "read the project settings file projects/NAME.yaml in the "
        "configuration directory, $XDG_CONFIG_HOME/moskophoros, else "
        "~/.config/moskophoros; NAME is letters, digits, '.', '_' and '-', "
        "not starting with '.', without '.yaml'. Its values act as the "
        "options would, over the global file and any loaded sheet "
        "(default: none)",
    )
    parser.add_argument(
        "--preview",
        action=_Flag,
        help="write the animated previews, also over a sheet or settings file "
        "without them (default: on)",
    )
    parser.add_argument(
        "--no-preview",
        action=_Flag,
        help="skip the animated previews (default: off)",
    )
    parser.add_argument(
        "--normals",
        action=_Flag,
        help="write the normal map, <stem>.normal.png, also over a sheet or "
        "settings file without it (default: on)",
    )
    parser.add_argument(
        "--no-normals",
        action=_Flag,
        help="skip the normal map; an earlier one is left as it is (default: off)",
    )
    parser.add_argument(
        "--depth",
        action=_Flag,
        help="write the depth map, <stem>.depth.png: each pixel's depth toward "
        "the viewer from the ground point, 16-bit; a depth beyond 2047.9375 "
        "sheet pixels either way is an overflow (default: off)",
    )
    parser.add_argument(
        "--no-depth",
        action=_Flag,
        help="skip the depth map, also over a sheet or settings file that "
        "writes it; an earlier one is left as it is (default: off)",
    )
    single(
        "--light",
        "X,Y,Z",
        _light,
        defaults["light.position"],
        "place a point light and write lit previews, <stem>-lit.<clip>.gif, "
        "beside the flat ones: X screen right, Y screen up and Z toward the "
        "viewer, in sheet pixels from the ground point (default: none)",
    )
    parser.add_argument(
        "--no-light",
        action=_Flag,
        help="place no light, dropping a reused or configured one (default: off)",
    )
    single(
        "--light-intensity",
        "I",
        _weight,
        defaults["light.intensity"],
        "how strongly the light lights a surface facing it, 0 or greater "
        "(default: 1.0)",
    )
    single(
        "--light-ambient",
        "A",
        _ambient,
        defaults["light.ambient"],
        "how bright a surface facing away from the light is, 0 to 1 (default: 0.3)",
    )
    single(
        "--work-dir",
        "DIR",
        _path,
        None,
        "keep capture output in DIR, which must be new or empty "
        "(default: a deleted temporary directory)",
    )
    single(
        "--blender",
        "PATH",
        _path,
        None,
        "Blender executable; never recorded in a sheet (default: discovered)",
    )
    parser.add_argument(
        "--any-blender",
        action=_Flag,
        help="allow a Blender version other than the supported one (default: off)",
    )
    flags = {
        *_HELP,
        "--preview",
        "--no-preview",
        "--normals",
        "--no-normals",
        "--depth",
        "--no-depth",
        "--no-light",
        "--no-user-config",
        "--any-blender",
        "--no-palette",
        "--no-materials",
        "--ambient-form",
        "--no-ambient-form",
    }
    return parser, frozenset(value_options), frozenset(flags)


def _prepare(parser, argv, value_options, flags):
    """Check options against their raw text, and join `--option -value`.

    Unknown and repeated options are rejected here, where the text given is
    still at hand: argparse reports an unknown option's value as a misplaced
    positional argument, and passes options on already converted. Only
    `--clip` and `--once` repeat.

    argparse takes a value such as `-1,0,0` or `-1e-3` for an option, so a
    negative ground point or angle would need `=`; it is joined as
    `--option=-value`. A value starting with `--` is left for argparse to
    reject, and a positional argument starting with `-` follows a bare `--`.
    """
    prepared = []
    given = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        index += 1
        if token == "--":
            prepared.extend(argv[index - 1 :])
            break
        if not token.startswith("-") or token == "-":
            prepared.append(token)
            continue
        name, equals, value = token.partition("=")
        if name not in value_options | flags:
            parser.error(f"unrecognized option: {token}")
        if (
            not equals
            and name in value_options
            and index < len(argv)
            and not argv[index].startswith("--")
        ):
            value = argv[index]
            index += 1
            equals = "="
            if value.startswith("-") and value not in ("-", "-h"):
                prepared.append(f"{name}={value}")
            else:
                prepared.extend((name, value))
        else:
            prepared.append(token)
        if name not in _REPEATABLE | _HELP:
            values = given.setdefault(name, [])
            values.append(value if equals else None)
            if len(values) > 1:
                shown = ", ".join(repr(text) for text in values if text is not None)
                parser.error(
                    f"argument {name}: given more than once"
                    + (f": {shown}" if shown else "")
                )
    return prepared


# Reading reused settings


class _DuplicateKey(ValueError):
    pass


def _unique_keys(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateKey(f"repeats the key {key!r}")
        document[key] = value
    return document


def _no_constant(name):
    raise ValueError(f"{name} is not a JSON value")


def _settings_error(path, problem):
    _build_parser()[0].error(f"--settings-from {str(path)!r}: {problem}")


def _shown(value):
    """`value` as JSON, cut short when long."""
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 60 else text[:57] + "..."


def _reused(convert):
    """Check a reused JSON number with its option's converter: the number's
    shortest text must be a value the option would accept."""

    def check(value):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise argparse.ArgumentTypeError(f"expected a number, got {_shown(value)}")
        return convert(repr(value))

    return check


def _whole_number(text):
    value = _whole(text)
    if value is None:
        raise argparse.ArgumentTypeError(
            f"expected a whole number 0 or greater, got {text!r}"
        )
    return value


def _one_of(*choices):
    def check(value):
        if not isinstance(value, str) or value not in choices:
            expected = " or ".join(map(repr, choices))
            raise argparse.ArgumentTypeError(
                f"expected {expected}, got {_shown(value)}"
            )
        return value

    return check


# The sheet's `settings` object, member by member. A member that may be null
# or a palette record is `_PALETTE`, and one that may be null or a material
# library record `_MATERIALS`.
_PALETTE = object()
_MATERIALS = object()
_SHEET_PREFIX = "moskophoros.sheet/"


class _Nullable:
    """A member that may be null, or else is checked as `shape`."""

    def __init__(self, shape):
        self.shape = shape


def _palette_source(value):
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or any(c in value for c in "/\\\0:")
    ):
        raise argparse.ArgumentTypeError("expected a nonempty base filename")
    return value


def _palette_digest(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("expected 64 lowercase hexadecimal digits")
    return value


def _palette_colors(value):
    if not isinstance(value, list):
        raise argparse.ArgumentTypeError(
            "expected an array of canonical #rrggbb colours"
        )
    colors = []
    for index, color in enumerate(value, 1):
        if not isinstance(color, str) or not re.fullmatch("#[0-9a-f]{6}", color):
            raise argparse.ArgumentTypeError(
                f"entry {index}: expected a lowercase #rrggbb colour"
            )
        colors.append(tuple(bytes.fromhex(color[1:])))
    try:
        return palette.validate_colors(colors, source="palette")
    except palette.PaletteError as error:
        raise argparse.ArgumentTypeError(error.problem) from None


_PALETTE_FIELDS = {
    "source": _palette_source,
    "sha256": _palette_digest,
    "colors": _palette_colors,
}


def _anything(value):
    return value


def _ramp_name(value):
    if not isinstance(value, str) or not value:
        raise argparse.ArgumentTypeError(
            f"expected a nonempty ramp name or null, got {_shown(value)}"
        )
    return value


def _shade_range(value):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(isinstance(bound, bool) or not isinstance(bound, int) for bound in value)
    ):
        raise argparse.ArgumentTypeError(
            f"expected two integers [lo, hi], got {_shown(value)}"
        )
    lo, hi = value
    if not 0 <= lo < hi <= 255:
        raise argparse.ArgumentTypeError(
            f"expected 0 <= lo < hi <= 255, got {_shown(value)}"
        )
    return lo, hi


def _light_position(value):
    """A recorded light position: a list of three numbers, never booleans,
    each finite; `null`, no light, is allowed by its shape."""
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(isinstance(v, bool) or not isinstance(v, int | float) for v in value)
    ):
        raise argparse.ArgumentTypeError(
            f"expected [x, y, z], three numbers, or null, got {_shown(value)}"
        )
    return tuple(_number(repr(coordinate)) for coordinate in value)


def _previews(value):
    if not isinstance(value, bool):
        raise argparse.ArgumentTypeError(f"expected true or false, got {_shown(value)}")
    return value


def _frame_count(value):
    """A recorded frame count: `"auto"` or a whole number of 1 or more, never a
    boolean or a float (settings design D-34)."""
    if value == layered.AUTO or (type(value) is int and value >= 1):
        return value
    raise argparse.ArgumentTypeError(
        f"expected a whole number 1 or more, or {layered.AUTO!r}, got {_shown(value)}"
    )


def _frames_option(text):
    """`--frames`: a decimal integer of 1 or more, or `auto`."""
    if text == layered.AUTO:
        return text
    if not re.fullmatch("[0-9]+", text) or int(text) < 1:
        raise argparse.ArgumentTypeError(
            f"expected a whole number 1 or more, or auto, got {text!r}"
        )
    return int(text)


def _clips(value):
    """The recorded clip selection: a nonempty list of distinct clips, each
    exactly `{"name": NAME, "loop": BOOLEAN, "frames": FRAMES}`, in sheet
    order, `FRAMES` its own count as given: a count, `"auto"` or null."""
    if not isinstance(value, list) or not value:
        raise argparse.ArgumentTypeError(
            f"expected a nonempty list of clips, got {_shown(value)}"
        )
    names = set()
    for index, entry in enumerate(value):
        if not isinstance(entry, dict) or set(entry) != {"name", "loop", "frames"}:
            raise argparse.ArgumentTypeError(
                f'[{index}]: expected exactly {{"name": NAME, "loop": BOOLEAN, '
                f'"frames": FRAMES}}, got {_shown(entry)}'
            )
        name, loop = entry["name"], entry["loop"]
        if not isinstance(name, str) or not name:
            raise argparse.ArgumentTypeError(
                f"[{index}].name: expected a nonempty clip name, got {_shown(name)}"
            )
        if not isinstance(loop, bool):
            raise argparse.ArgumentTypeError(
                f"[{index}].loop: expected true or false, got {_shown(loop)}"
            )
        frames = entry["frames"]
        if frames is not None and not (
            frames == layered.AUTO or (type(frames) is int and frames >= 1)
        ):
            raise argparse.ArgumentTypeError(
                f"[{index}].frames: expected a whole number 1 or more, "
                f"{layered.AUTO!r} or null, got {_shown(frames)}"
            )
        if name in names:
            raise argparse.ArgumentTypeError(
                f"[{index}].name: the clip {_shown(name)} is recorded twice"
            )
        names.add(name)
    return value


# A material library record, whose ramps, default and entries the library
# module checks once the palette is known (`_style`).
_MATERIALS_FIELDS = {
    "source": _palette_source,
    "sha256": _palette_digest,
    "ramps": _anything,
    "default": _Nullable(_ramp_name),
    "materials": _anything,
}


def _recorded_direction(value):
    """A recorded camera direction: a list of three numbers, never booleans,
    each from -1 to 1, normalised to within `views.UNIT_TOLERANCE`. It is
    kept exactly as recorded."""
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(isinstance(v, bool) or not isinstance(v, int | float) for v in value)
    ):
        raise argparse.ArgumentTypeError(
            f"expected [x, y, z], three numbers, got {_shown(value)}"
        )
    vector = tuple(_number(repr(component)) for component in value)
    if not views.is_unit(vector):
        raise argparse.ArgumentTypeError(
            "expected a normalised direction, each component from -1 to 1 and "
            f"its length within {views.UNIT_TOLERANCE} of 1, got {_shown(value)}"
        )
    return vector


def _recorded_leaf(path):
    """A recorded shading leaf, checked as a settings file checks it (shading
    design contract 1): its own type and bounds, whether or not another layer
    replaces it. The cross-field rules wait for the resolved values."""

    def check(value):
        try:
            return shading_model.BY_PATH[path].check(value)
        except shading_model.Bad as error:
            raise argparse.ArgumentTypeError(error.problem(_shown)) from None

    return check


def _recorded_direction_leaf(value):
    """A recorded key direction: three numbers, each from -1 to 1, of unit
    length within `views.UNIT_TOLERANCE`, kept exactly as recorded and never
    normalised again."""
    try:
        return shading_model.check_recorded_direction(value)
    except shading_model.Bad:
        raise argparse.ArgumentTypeError(
            "expected a recorded unit direction [x, y, z], each component from "
            f"-1 to 1 and its length within {views.UNIT_TOLERANCE} of 1, got "
            f"{_shown(value)}"
        ) from None


_SETTINGS = {
    "view": {
        "preset": _one_of(*PRESETS, CUSTOM_VIEW),
        "directions": _reused(_directions),
        "start_angle_deg": _reused(_number),
    },
    "camera": {
        "projection": _one_of(*PROJECTIONS),
        "direction": _recorded_direction,
        "roll": _reused(_roll),
        "position": _Nullable(_light_position),
    },
    "model_yaw_deg": _reused(_number),
    "fps": _reused(_positive),
    "frames": _frame_count,
    "supersample": _reused(_supersample),
    "pixels_per_meter": _reused(_positive),
    "cell": {"width": _reused(_cell_side), "height": _reused(_cell_side)},
    "ground_m": {axis: _reused(_number) for axis in "xyz"},
    "ground_px": {axis: _reused(_whole_number) for axis in "xy"},
    "root_motion": _one_of(*ROOT_MOTION_MODES),
    "previews": _previews,
    "normals": _previews,
    "depth": _previews,
    "light": {
        "position": _Nullable(_light_position),
        "intensity": _reused(_weight),
        "ambient": _reused(_ambient),
    },
    "shade": {
        "ao_distance_m": _reused(_positive),
        "ao_samples": _reused(_ao_samples),
        "occlusion_weight": _reused(_weight),
        "convexity_weight": _reused(_weight),
        "range": _shade_range,
        "mode": _recorded_leaf("mode"),
        "ambient_form": _recorded_leaf("ambient_form"),
        "key": {
            "direction": _recorded_direction_leaf,
            "strength": _recorded_leaf("key.strength"),
        },
        "sky": {"strength": _recorded_leaf("sky.strength")},
        "ground": {"strength": _recorded_leaf("ground.strength")},
        "sky_ground_frame": _recorded_leaf("sky_ground_frame"),
        "brightness": {
            "floor": _recorded_leaf("brightness.floor"),
            "ceiling": _recorded_leaf("brightness.ceiling"),
        },
        "snap": _recorded_leaf("snap"),
        "dither": {
            "pattern": _recorded_leaf("dither.pattern"),
            "strength": _recorded_leaf("dither.strength"),
        },
    },
    "ramp": {
        "lightness_step": _reused(_unit),
        "hue_shift_deg": _reused(_half_turn),
        "chroma_fade": _reused(_unit),
    },
    "style": {
        "reduce": _one_of(*REDUCTIONS),
        "edges": _one_of(*layered.EDGES),
        "palette": _PALETTE,
        "materials": _MATERIALS,
    },
    "clips": _clips,
}


def _check_shape(shape, value, name, problems):
    """Check `value` against `shape`, adding each problem under its field
    path to `problems`, and return the converted values."""
    if shape is _PALETTE:
        if value is None:
            return None
        before = len(problems)
        checked = _check_shape(_PALETTE_FIELDS, value, name, problems)
        return PaletteRecord(**checked) if len(problems) == before else None
    if shape is _MATERIALS:
        if value is None:
            return None
        # A library's own shade is recorded only when it gives one (material
        # styling design D-35); the library module checks it with the rest.
        if isinstance(value, dict) and "shade" in value:
            rest = {key: item for key, item in value.items() if key != "shade"}
            checked = _check_shape(_MATERIALS_FIELDS, rest, name, problems)
            return checked | {"shade": value["shade"]}
        return _check_shape(_MATERIALS_FIELDS, value, name, problems)
    if isinstance(shape, _Nullable):
        if value is None:
            return None
        return _check_shape(shape.shape, value, name, problems)
    if value is None:
        problems.append(f"{name}: must be set, got null")
        return None
    if callable(shape):
        try:
            return shape(value)
        except argparse.ArgumentTypeError as error:
            problems.append(f"{name}: {error}")
            return None
    if not isinstance(value, dict):
        problems.append(f"{name}: expected an object, got {_shown(value)}")
        return None
    checked = {}
    for member, member_shape in shape.items():
        if member not in value:
            problems.append(f"{name}.{member}: missing")
            continue
        checked[member] = _check_shape(
            member_shape, value[member], f"{name}.{member}", problems
        )
    problems.extend(
        f"{name}.{member}: unknown field" for member in value if member not in shape
    )
    return checked


def _style(style, problems):
    """`style` with its recorded material library, if any, validated against
    the recorded palette and made a `MaterialsRecord`.

    A library needs a palette (design §CLI, D-6), so a record beside a null
    palette is a problem under `settings.style.materials`.
    """
    record = style.get("materials")
    if record is None:
        return style
    where = "settings.style.materials"
    if style["palette"] is None:
        problems.append(f"{where}: a library needs a palette, but the palette is null")
        return style
    document = {
        "schema": materials.recorded_schema(record),
        "ramps": record["ramps"],
        "materials": record["materials"],
    }
    if record["default"] is not None:
        document["default"] = record["default"]
    if "shade" in record:
        document["shade"] = record["shade"]
    try:
        library = materials.validate_library(
            document, style["palette"].colors, source=where, recorded=True
        )
    except materials.LibraryError as error:
        problems.append(f"{where}: {error.problem}")
        return style
    return style | {
        "materials": MaterialsRecord(record["source"], record["sha256"], library)
    }
