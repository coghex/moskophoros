"""The `moskophoros` command: options, settings reuse, the run and its exit
codes.

`parse_args` turns an argument list into validated `Options`, following
design §CLI, §Option validation and §Presets. On success it has no effects:
it reads no files, starts no process and prints nothing. Checks that need the
input file, the filesystem or Blender belong to the stages that use them.

`resolve_settings` applies `--settings-from`, following design §Scale and
ground point, Reuse: `read_settings` reads and checks the earlier sheet's
`settings`, and `apply_settings` merges them with the parsed options. It also
reads a selected palette snapshot; these reads precede any Blender invocation.

`capture_settings` gives the settings capture and export share, and
`style_record` the style the sheet records beside them, following design
§Export: the reduction and the palette. The style never reaches the capture
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
    palette,
    sampling,
    stylize,
    views,
)
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
# The resolved view name once --pitch, --directions or --start-angle is given.
CUSTOM_VIEW = "custom"
ROOT_MOTION_MODES = ("error", "keep")
# The values --reduce accepts; the first is the default.
REDUCTIONS = ("plain", "mode")
SHEET_SCHEMA = "moskophoros.sheet/2"
# An older sheet, still reused; it reads as the plain reduction with no palette.
LEGACY_SHEET_SCHEMA = "moskophoros.sheet/1"
_MAX_DIGITS = 4300
_VIEW_FIELDS = ("view", "pitch", "directions", "start_angle")
_REPEATABLE = frozenset({"--clip", "--once"})
_HELP = frozenset({"-h", "--help"})


@dataclass(frozen=True)
class PaletteRecord:
    """A palette snapshot; reuse never needs its original file."""

    source: str
    sha256: str
    colors: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class Options:
    """Validated options.

    `explicit` holds the field names of the options given on the command
    line, as distinct from defaults and preset-derived values. `view` is the
    resolved preset name, or `custom` when an explicit pitch, direction count
    or start angle overrides the preset. `clip` is None when every clip is
    selected; `ppm`, `cell` and `ground_px` are None when automatic.
    """

    infile: Path
    outfile: Path
    view: str
    pitch: float
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
    no_preview: bool
    work_dir: Path | None
    blender: Path | None
    any_blender: bool
    explicit: frozenset[str]
    palette_file: Path | None = None
    no_palette: bool = False
    palette: PaletteRecord | None = None


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

    once = tuple(args.once or ())
    clip = None if args.clip is None else tuple(args.clip)
    if clip is not None:
        for name in once:
            if name not in clip:
                parser.error(f"argument --once: {name!r} is not among the --clip names")

    explicit = frozenset(args.explicit_)
    preset = PRESETS[args.view]
    overrides = {"pitch", "directions", "start_angle"} & explicit
    return Options(
        infile=args.infile,
        outfile=args.outfile,
        view=CUSTOM_VIEW if overrides else args.view,
        pitch=args.pitch if "pitch" in explicit else preset.pitch,
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
        settings_from=args.settings_from,
        no_preview=args.no_preview,
        work_dir=args.work_dir,
        blender=args.blender,
        any_blender=args.any_blender,
        explicit=explicit,
        palette_file=args.palette,
        no_palette=args.no_palette,
    )


@dataclass(frozen=True)
class ReusedSettings:
    """The values `--settings-from` reuses, named as in `Options`.

    `view` is a preset name or `custom`, with the view's recorded pitch,
    direction count and start angle. Scale, cell and ground pixel are always
    set: reuse makes them fixed.
    """

    view: str
    pitch: float
    directions: int
    start_angle: float
    model_yaw: float
    fps: float
    supersample: int
    ppm: float
    cell: tuple[int, int]
    ground: tuple[float, float, float]
    ground_px: tuple[int, int]
    root_motion: str
    reduce: str
    palette: PaletteRecord | None = None


def resolve_settings(options: Options) -> Options:
    """Validate reuse before overrides, then resolve palette bytes before Blender."""
    if options.settings_from is not None:
        options = apply_settings(options, read_settings(options.settings_from))
    if options.palette_file is not None:
        path = options.palette_file
        try:
            source = _palette_source(path.name)
        except argparse.ArgumentTypeError as error:
            _build_parser()[0].error(f"--palette {str(path)!r}: {error}")
        try:
            data = path.read_bytes()
        except OSError as error:
            _build_parser()[0].error(
                f"--palette {str(path)!r}: cannot be read: {error.strerror or error}"
            )
        try:
            colors = palette.read_palette_bytes(data, source=path)
        except palette.PaletteError as error:
            _build_parser()[0].error(f"--palette {error}")
        options = replace(
            options,
            palette=PaletteRecord(source, hashlib.sha256(data).hexdigest(), colors),
        )
    elif options.no_palette:
        options = replace(options, palette=None)
    return options


def read_settings(path) -> ReusedSettings:
    """Read and check the reusable `settings` of the sheet description at
    `path`. Reading that file is the only effect.

    Raises `UsageError`, reported as `parse_args` reports one, naming the
    file and the problem: the file cannot be read, is not UTF-8 JSON, repeats
    a key, is not a `moskophoros.sheet/2` or `moskophoros.sheet/1` document
    with a `settings` object, or its `settings` has a missing, unknown or
    unacceptable field. Every field is checked as its option checks it,
    including fields an explicit option will replace. A `/2` sheet's
    `settings.style` is checked the same way; a `/1` sheet has none and reads
    as the plain reduction. Nothing beyond `schema` and `settings` is read,
    and `settings.clips` is ignored.
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
    not_a_sheet = f"is not a {' or '.join(_SHAPES)} document"
    if not isinstance(document, dict):
        _settings_error(path, f"{not_a_sheet}: not a JSON object")
    if "schema" not in document:
        _settings_error(path, f"{not_a_sheet}: schema is missing")
    schema = document["schema"]
    if not isinstance(schema, str) or schema not in _SHAPES:
        _settings_error(path, f"{not_a_sheet}: schema is {_shown(schema)}")
    if "settings" not in document:
        _settings_error(path, "settings: missing")
    problems = []
    shape = _SHAPES[schema]
    checked = _check_shape(shape, document["settings"], "settings", problems)
    if problems:
        _settings_error(path, "; ".join(problems))
    view, cell, ground, ground_px = (
        checked[name] for name in ("view", "cell", "ground_m", "ground_px")
    )
    return ReusedSettings(
        view=view["preset"],
        pitch=view["pitch_deg"],
        directions=view["directions"],
        start_angle=view["start_angle_deg"],
        model_yaw=checked["model_yaw_deg"],
        fps=checked["fps"],
        supersample=checked["supersample"],
        ppm=checked["pixels_per_meter"],
        cell=(cell["width"], cell["height"]),
        ground=(ground["x"], ground["y"], ground["z"]),
        ground_px=(ground_px["x"], ground_px["y"]),
        root_motion=checked["root_motion"],
        reduce=checked["style"]["reduce"] if "style" in shape else REDUCTIONS[0],
        palette=checked["style"]["palette"] if "style" in shape else None,
    )


def apply_settings(options: Options, reused: ReusedSettings) -> Options:
    """Merge `reused` into `options`; an explicit option wins over its
    reused value.

    An explicit `--view` resolves the view exactly as without reuse.
    Otherwise the reused view stays, and an explicit `--pitch`,
    `--directions` or `--start-angle` replaces its value and makes the preset
    `custom`. Clip selection, `--once` and `explicit` stay as parsed.
    """
    explicit = options.explicit
    names = [field.name for field in fields(ReusedSettings)]
    if "view" in explicit:
        names = [name for name in names if name not in _VIEW_FIELDS]
    values = {name: getattr(reused, name) for name in names if name not in explicit}
    if "view" not in explicit and explicit & set(_VIEW_FIELDS):
        values["view"] = CUSTOM_VIEW
    return replace(options, **values)


def capture_settings(options: Options) -> backend.Settings:
    """The resolved settings capture and export share, from merged `options`.

    They hold no style: `style_record` gives that, and it stays out of the
    capture job.
    """
    return backend.Settings(
        view=options.view,
        pitch=options.pitch,
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
    )


def style_record(options: Options) -> dict:
    """The sheet's ordered look record, independent of capture settings."""
    record = options.palette
    return {
        "reduce": options.reduce,
        "palette": None
        if record is None
        else {
            "source": record.source,
            "sha256": record.sha256,
            "colors": ["#" + bytes(color).hex() for color in record.colors],
        },
    }


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
    selected = gltf.select_clips(subject, options.clip or (), options.once)
    preview_paths = (
        () if options.no_preview else export.preview_paths(outfile, selected)
    )
    _check_targets([outfile, json_path, *preview_paths])
    view = views.View(
        options.pitch, options.directions, options.start_angle, options.model_yaw
    )
    requested = sampling.frames(subject.name, selected, view, options.fps)
    settings = capture_settings(options)
    sheet_style = style_record(options)
    found = blender.locate(options.blender, options.any_blender)

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
            ),
        )
        generator = export.generator(rendered.backend)
        metadata = {
            "fingerprint": export.fingerprint(
                generator,
                export.sheet_settings(settings, selected, sheet_style),
                source.sha256,
            )
        }
        # Loaded one at a time as stylize reduces them, so only one
        # supersampled frame is held at once.
        captured = (
            _load_frame(address, paths, metadata)
            for address, paths in rendered.buffers.items()
        )
        reduce = {"plain": stylize.plain, "mode": stylize.mode}[options.reduce]
        colors = options.palette.colors if options.palette is not None else None
        reduced = (
            reduce(captured, settings.supersample)
            if colors is None
            else reduce(captured, settings.supersample, palette=colors)
        )
        frames = cleanup.passthrough(reduced)

    sheet = export.encode(
        frames,
        generator=generator,
        source=source,
        subject=subject.name,
        settings=settings,
        style=sheet_style,
        selected_clips=selected,
        image_path=outfile,
    )
    outputs = [(outfile, sheet.png), (json_path, sheet.json)]
    if not options.no_preview:
        previews = export.previews(
            frames, subject=subject.name, settings=settings, selected_clips=selected
        )
        for preview in previews:
            for warning in preview.warnings:
                _report("warning", warning)
        outputs += zip(
            preview_paths, (preview.gif for preview in previews), strict=True
        )
    publish(outputs)


def _load_frame(address, paths, metadata):
    """The captured frame at `address` with every named buffer in `paths`:
    `color` as its pixels, and each other buffer under its own name."""
    buffers = {name: imageops.load_png(path) for name, path in paths.items()}
    return sampling.ImageFrame(address, buffers.pop("color"), metadata, buffers)


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


_pitch = _from_to(_number, 0, 90)
_directions = _from_to(_integer, 1, 64)
_supersample = _from_to(_integer, 1, 16)
_cell_side = _from_to(_integer, 1, 4096)


def _cell(text):
    parts = text.split("x")
    try:
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(text)
        width, height = (_cell_side(part) for part in parts)
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError(
            f"expected WxH, two integers each from 1 to 4096, got {text!r}"
        ) from None
    return width, height


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


def _ground_px(text):
    parts = text.split(",")
    coordinates = [_whole(part) for part in parts]
    if len(parts) != 2 or None in coordinates:
        raise argparse.ArgumentTypeError(
            f"expected X,Y, two whole numbers 0 or greater, got {text!r}"
        )
    x, y = coordinates
    return x, y


def _path(text):
    if not text:
        raise argparse.ArgumentTypeError("expected a path, got ''")
    return Path(text)


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
        "camera pitch, 0 to 90 (default: from the view)",
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
        12.0,
        "target sampling rate, greater than 0 (default: 12)",
    )
    single(
        "--ppm",
        "N",
        _positive,
        None,
        "pixels per meter, greater than 0 (default: auto)",
    )
    single(
        "--cell",
        "WxH",
        _cell,
        None,
        "cell size in pixels, each 1 to 4096 (default: auto)",
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
        "cell pixel corner the ground point lands on (default: auto)",
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
    single("--palette", "FILE", _path, None, "map colours to a HEX, GPL or PNG palette")
    parser.add_argument(
        "--no-palette", action=_Flag, help="drop a reused palette (default: off)"
    )
    single(
        "--settings-from",
        "FILE",
        _path,
        None,
        "reuse settings from an earlier sheet's JSON (default: none)",
    )
    parser.add_argument(
        "--no-preview",
        action=_Flag,
        help="skip the animated previews (default: off)",
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
        "Blender executable (default: discovered)",
    )
    parser.add_argument(
        "--any-blender",
        action=_Flag,
        help="allow a Blender version other than the supported one (default: off)",
    )
    flags = {*_HELP, "--no-preview", "--any-blender", "--no-palette"}
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


# The sheet's `settings` object, member by member. `clips` is recognized but
# never read: clip selection comes from the current command line. A member
# that may be null or a palette record is `_PALETTE`.
_IGNORED = None
_PALETTE = object()


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
_LEGACY_SETTINGS = {
    "view": {
        "preset": _one_of(*PRESETS, CUSTOM_VIEW),
        "projection": _one_of("orthographic"),
        "pitch_deg": _reused(_pitch),
        "directions": _reused(_directions),
        "start_angle_deg": _reused(_number),
    },
    "model_yaw_deg": _reused(_number),
    "fps": _reused(_positive),
    "supersample": _reused(_supersample),
    "pixels_per_meter": _reused(_positive),
    "cell": {"width": _reused(_cell_side), "height": _reused(_cell_side)},
    "ground_m": {axis: _reused(_number) for axis in "xyz"},
    "ground_px": {axis: _reused(_whole_number) for axis in "xy"},
    "root_motion": _one_of(*ROOT_MOTION_MODES),
    "clips": _IGNORED,
}
_SETTINGS = {
    name: _LEGACY_SETTINGS[name] for name in _LEGACY_SETTINGS if name != "clips"
}
_SETTINGS |= {
    "style": {"reduce": _one_of(*REDUCTIONS), "palette": _PALETTE},
    "clips": _IGNORED,
}
# Each reusable schema's `settings`, newest first.
_SHAPES = {SHEET_SCHEMA: _SETTINGS, LEGACY_SHEET_SCHEMA: _LEGACY_SETTINGS}


def _check_shape(shape, value, name, problems):
    """Check `value` against `shape`, adding each problem under its field
    path to `problems`, and return the converted values."""
    if shape is _PALETTE:
        if value is None:
            return None
        before = len(problems)
        checked = _check_shape(_PALETTE_FIELDS, value, name, problems)
        return PaletteRecord(**checked) if len(problems) == before else None
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
        if member_shape is _IGNORED:
            continue
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
