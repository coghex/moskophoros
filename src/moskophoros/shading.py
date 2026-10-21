"""The shading settings and per-material response: their leaves, checks and
models (shading design contracts 1 and 2; D-10, D-24 to D-26, D-29, D-32,
D-33, D-39).

Nothing here is public yet. The leaves are not in `settings.SCHEMA`, the
shipped defaults or the command line, and a library may not give them until
SHD-6 turns the gate on; the readers in `settings` and `materials` take them
only through an explicit internal parameter, which direct tests use.

A leaf is named by its path under `shade`, such as `key.strength`. The
leaves a material or a library may override (`Leaf.response`) make up a
`Response`. The rest, the key direction, the sky and ground frame and the snap
target, are global only and make up the rest of `Settings`. Everything here
is pure.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, localcontext
from types import MappingProxyType

from moskophoros import views

MODES = ("ramp", "brightness", "both", "neither")
FRAMES = ("camera", "world")
SNAPS = ("off", "ramp", "palette")
PATTERNS = (
    "off",
    "ordered2",
    "ordered4",
    "ordered8",
    "clustered4",
    "diagonal4",
    "shuffled8",
)
# What a file gives for the key direction by default; it is normalised.
KEY_DIRECTION = [-0.6, 0.7, 0.7]
# The origin a value has when no layer set it.
DEFAULT_ORIGIN = "shipped default"


def quote(text):
    """`text` as JSON shows it, quotes and whitespace included, as library
    messages name things."""
    return json.dumps(text, ensure_ascii=False)


class Bad(Exception):
    """A value a leaf refuses. `wanted` says what the leaf expects and
    `value` is what it got; a reader words `wanted, got <value>` with its own
    way of showing values. `got` is False when `wanted` says everything."""

    def __init__(self, wanted, value, got=True):
        self.wanted = wanted
        self.value = value
        self.got = got
        super().__init__(wanted)

    def problem(self, shown):
        """The message, with the value shown as `shown` shows it."""
        return f"{self.wanted}, got {shown(self.value)}" if self.got else self.wanted


class ShadingError(Exception):
    """Resolved settings or a resolved library that cannot be used. `problems`
    are the messages in their fixed order: the palette rules, the global
    response, the library-wide response, then the materials by name. Each
    names every contributing value and where it came from."""

    def __init__(self, problems):
        self.problems = tuple(problems)
        super().__init__("\n".join(self.problems))


def _number(low, high):
    """A finite number from `low` to `high` as a float; never a boolean."""

    def check(value):
        wanted = f"expected a finite number from {low} to {high}"
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise Bad(wanted, value)
        try:
            number = float(value)
        except OverflowError:
            raise Bad(wanted, value) from None
        if not low <= number <= high:  # False for NaN, and for an infinity
            raise Bad(wanted, value)
        return number

    return check


def _one_of(*choices):
    def check(value):
        if isinstance(value, str) and value in choices:
            return value
        listed = ", ".join(choices[:-1]) + f" or {choices[-1]}"
        raise Bad(f"expected {listed}", value)

    return check


def _boolean(value):
    if not isinstance(value, bool):
        raise Bad("expected true or false", value)
    return value


def _components(value):
    """`value` as three finite numbers, or None."""
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    if any(
        isinstance(item, bool) or not isinstance(item, int | float) for item in value
    ):
        return None
    try:
        vector = tuple(float(item) for item in value)
    except OverflowError:
        return None
    return vector if all(-1 <= item <= 1 for item in vector) else None


def check_direction(value):
    """A key direction as a file or an option gives it: `[x, y, z]`, three
    finite numbers each from -1 to 1, not all 0, normalised once with
    `views.normalise`."""
    vector = _components(value)
    if vector is None:
        raise Bad(
            "expected [x, y, z], three finite numbers each from -1 to 1, not all 0",
            value,
        )
    if not any(vector):
        raise Bad(
            "expected a direction, but [0, 0, 0] points nowhere", value, got=False
        )
    return views.normalise(vector)


def check_recorded_direction(value):
    """A key direction a sheet recorded: three numbers within
    `views.UNIT_TOLERANCE` of unit length, kept exactly as recorded and never
    normalised again."""
    vector = _components(value)
    if vector is None or not views.is_unit(vector):
        raise Bad("expected a recorded unit direction, [x, y, z]", value)
    return vector


@dataclass(frozen=True)
class Leaf:
    """One shading leaf: its `path` under `shade`, its `default` as a file
    gives it, `check`, which turns a value into the leaf's or raises `Bad`,
    whether a material or the library may override it (`response`), and what
    it holds."""

    path: str
    default: object
    check: object
    response: bool
    what: str


# The leaves in the settings table's order (contract 1).
LEAVES = (
    Leaf(
        "mode",
        "ramp",
        _one_of(*MODES),
        True,
        "what the shading signal changes: ramp, brightness, both or neither",
    ),
    Leaf(
        "ambient_form",
        True,
        _boolean,
        True,
        "whether the ambient form term applies",
    ),
    Leaf(
        "key.direction",
        KEY_DIRECTION,
        check_direction,
        False,
        "toward the key light in the camera's frame, normalised",
    ),
    Leaf("key.strength", 0, _number(0, 1), True, "the key light's share, 0 to 1"),
    Leaf("sky.strength", 0, _number(0, 1), True, "the sky light's share, 0 to 1"),
    Leaf("ground.strength", 0, _number(0, 1), True, "the ground light's share, 0 to 1"),
    Leaf(
        "sky_ground_frame",
        "camera",
        _one_of(*FRAMES),
        False,
        "the frame the sky and ground lights follow: camera or world",
    ),
    Leaf(
        "brightness.floor",
        0.3,
        _number(0, 1),
        True,
        "the least brightness gain, 0 to 1, at most the ceiling",
    ),
    Leaf(
        "brightness.ceiling",
        1,
        _number(0, 1),
        True,
        "the greatest brightness gain, 0 to 1, at least the floor",
    ),
    Leaf(
        "snap", "off", _one_of(*SNAPS), False, "the snap target: off, ramp or palette"
    ),
    Leaf("dither.pattern", "off", _one_of(*PATTERNS), True, "the dither pattern"),
    Leaf("dither.strength", 1, _number(0, 1), True, "the dither strength, 0 to 1"),
)
BY_PATH = MappingProxyType({leaf.path: leaf for leaf in LEAVES})
# The nested groups of `shade` the new leaves sit in.
SUBGROUPS = tuple(
    dict.fromkeys(leaf.path.split(".")[0] for leaf in LEAVES if "." in leaf.path)
)
# Each shading leaf's default as the command holds it, by path under `shade`.
DEFAULTS = MappingProxyType({leaf.path: leaf.check(leaf.default) for leaf in LEAVES})


@dataclass(frozen=True)
class Response:
    """The shading response a material, the library or the global settings
    give: every leaf an entry may override, resolved."""

    mode: str
    ambient_form: bool
    key_strength: float
    sky_strength: float
    ground_strength: float
    brightness_floor: float
    brightness_ceiling: float
    dither_pattern: str
    dither_strength: float


# The `Response` field of each response leaf, by path.
FIELDS = MappingProxyType(
    {leaf.path: leaf.path.replace(".", "_") for leaf in LEAVES if leaf.response}
)
RESPONSE_PATHS = tuple(FIELDS)


@dataclass(frozen=True)
class Settings:
    """The resolved global shading settings."""

    response: Response
    key_direction: tuple[float, float, float]
    sky_ground_frame: str
    snap: str


def settings_of(values):
    """The `Settings` of `values`, which maps `shade.<path>` names to checked
    values; a leaf it leaves out has its default."""

    def value(path):
        return values.get(f"shade.{path}", DEFAULTS[path])

    return Settings(
        Response(**{field: value(path) for path, field in FIELDS.items()}),
        value("key.direction"),
        value("sky_ground_frame"),
        value("snap"),
    )


@dataclass(frozen=True)
class Sourced:
    """A value with the origin it is shown with in an error."""

    value: object
    origin: str


def _label(path, item):
    return f"shade.{path} {item.value!r} ({item.origin})"


def strength_total(*strengths):
    """The sum of `strengths` as a `Decimal`, exact on the decimal values the
    floats print as, so the result never depends on the order or on the
    ambient `Decimal` context, and 0.1, 0.2 and 0.7 add to exactly 1."""
    with localcontext() as context:
        # Wide enough for the sum of any three floats to be exact, however
        # far apart their magnitudes are.
        context.prec = 1200
        return sum((Decimal(repr(strength)) for strength in strengths), Decimal(0))


def budget_problem(key, sky, ground):
    """Why `key`, `sky` and `ground`, the `Sourced` strengths, add to more
    than 1, or None (D-26)."""
    total = strength_total(key.value, sky.value, ground.value)
    if total <= 1:
        return None
    return (
        f"{_label('key.strength', key)} + {_label('sky.strength', sky)} + "
        f"{_label('ground.strength', ground)} = {total}, exceeds 1"
    )


def brightness_problem(floor, ceiling):
    """Why the `Sourced` brightness `floor` exceeds `ceiling`, or None
    (D-25)."""
    if floor.value <= ceiling.value:
        return None
    return (
        f"{_label('brightness.floor', floor)} exceeds "
        f"{_label('brightness.ceiling', ceiling)}"
    )
