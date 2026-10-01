"""Command-line options: parsing, validation, view presets and help.

`parse_args` turns an argument list into validated `Options`, following
design §CLI, §Option validation and §Presets. On success it has no effects:
it reads no files, starts no process and prints nothing. Checks that need the
input file, the filesystem or Blender belong to the stages that use them.
"""

import argparse
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

PROG = "moskophoros"
USAGE = f"{PROG} [options] <infile.glb> <outfile.png>"
USAGE_ERROR = 2


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
    settings_from: Path | None
    no_preview: bool
    work_dir: Path | None
    blender: Path | None
    any_blender: bool
    explicit: frozenset[str]


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
        settings_from=args.settings_from,
        no_preview=args.no_preview,
        work_dir=args.work_dir,
        blender=args.blender,
        any_blender=args.any_blender,
        explicit=explicit,
    )


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise UsageError(message)


def _record(action, namespace, *, repeatable=False):
    if not repeatable and action.dest in namespace.explicit_:
        raise argparse.ArgumentError(action, "given more than once")
    namespace.explicit_.add(action.dest)


class _Single(argparse.Action):
    """An option that takes one value and may be given at most once."""

    def __call__(self, parser, namespace, values, option_string=None):
        _record(self, namespace)
        setattr(namespace, self.dest, values)


class _Flag(argparse.Action):
    """A flag that may be given at most once."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=False, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        _record(self, namespace)
        setattr(namespace, self.dest, True)


class _Names(argparse.Action):
    """A repeatable option collecting distinct names in the order given."""

    def __call__(self, parser, namespace, values, option_string=None):
        names = getattr(namespace, self.dest) or []
        if values in names:
            raise argparse.ArgumentError(self, f"{values!r} named more than once")
        _record(self, namespace, repeatable=True)
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


def _cell(text):
    parts = text.split("x")
    try:
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(text)
        width, height = (_from_to(_integer, 1, 4096)(part) for part in parts)
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


def _ground_px(text):
    parts = text.split(",")
    try:
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(text)
        x, y = (_number(part) for part in parts)
        if not all(value.is_integer() and value >= 0 for value in (x, y)):
            raise argparse.ArgumentTypeError(text)
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError(
            f"expected X,Y, two whole numbers 0 or greater, got {text!r}"
        ) from None
    return int(x), int(y)


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
        _from_to(_number, 0, 90),
        None,
        "camera pitch, 0 to 90 (default: from the view)",
    )
    single(
        "--directions",
        "N",
        _from_to(_integer, 1, 64),
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
        _from_to(_integer, 1, 16),
        8,
        "capture resolution multiplier, 1 to 16 (default: 8)",
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
    flags = {"-h", "--help", "--no-preview", "--any-blender"}
    return parser, frozenset(value_options), frozenset(flags)


def _prepare(parser, argv, value_options, flags):
    """Reject unknown options, and join `--option -value` into `--option=-value`.

    argparse takes a value such as `-1,0,0` or `-1e-3` for an option, so a
    negative ground point or angle would need `=`. It also reports an unknown
    option's value as a misplaced positional argument, naming the wrong
    argument. A value starting with `--` is left for argparse to reject, and a
    positional argument starting with `-` follows a bare `--`.
    """
    prepared = []
    index = 0
    while index < len(argv):
        token = argv[index]
        index += 1
        if token == "--":
            prepared.extend(argv[index - 1 :])
            break
        name = token.partition("=")[0]
        if (
            token in value_options
            and index < len(argv)
            and not argv[index].startswith("--")
        ):
            value = argv[index]
            index += 1
            if value.startswith("-") and value not in ("-", "-h"):
                prepared.append(f"{token}={value}")
            else:
                prepared.extend((token, value))
            continue
        if token.startswith("-") and token != "-" and name not in value_options | flags:
            parser.error(f"unrecognized option: {name}")
        prepared.append(token)
    return prepared
