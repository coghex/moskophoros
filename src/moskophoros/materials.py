"""Material libraries: named ramps of palette indices, read and validated.

A library is a YAML file the tool only reads (material design D-8, settings
design D-7), parsed by the strict reader in `yamlfile`. Its ramps
index the shared palette (D-6, D-7); it holds named generic ramps, an optional
default naming one of them, and material entries (D-15, D-17). An entry with
a ramp may override the global shading values for its material (settings
design D-9, D-20). `warnings` names what a library leaves to its fallbacks
for a given model (D-3, D-9, D-17, D-18).

A `moskophoros.materials/3` library may also give a ramp as properties, a
base colour and a band count with optional formula values, which `generate`
turns into palette indices (D-28, D-33, D-34), and a top-level `shade` giving
the shade range its materials fall back to (D-35, D-36). A `/2` library still
loads and reads exactly as before.
"""

import json
import math
import re
from dataclasses import dataclass, fields, replace
from numbers import Integral
from pathlib import Path
from types import MappingProxyType

from moskophoros import ramps as generation
from moskophoros import yamlfile

SCHEMA = "moskophoros.materials/3"
# The schema before generated ramps and a library shade, which still loads
# and reads exactly as before (D-34).
LEGACY_SCHEMA = "moskophoros.materials/2"
# The schema before per-material shading, which no longer loads (settings
# design D-29): the only edit it needs is its schema line.
PREVIOUS_SCHEMA = "moskophoros.materials/1"
# A generated ramp's formula values, with the global settings' limits
# (D-33), in their recorded order.
FORMULA = ("lightness_step", "hue_shift_deg", "chroma_fade")
FORMULA_LIMITS = MappingProxyType(
    {
        "lightness_step": (0.0, 1.0),
        "hue_shift_deg": (-180.0, 180.0),
        "chroma_fade": (0.0, 1.0),
    }
)
_BASE = re.compile(r"#[0-9A-Fa-f]{6}")
ORDINARY = "ordinary"
MAX_RAMP = 256
# A library file's name ends in one of these, in any case (settings D-11).
SUFFIXES = (".yaml", ".yml")
# The glTF alpha modes, whose materials have an identity and can take a ramp,
# translucent `BLEND` ones included (alpha design D-15); a material of any
# other alpha mode takes the ordinary look.
RAMP_ALPHA_MODES = ("OPAQUE", "MASK", "BLEND")
_FIELDS = ("schema", "ramps", "default", "shade", "materials")
_REQUIRED = ("schema", "ramps", "materials")


class LibraryError(Exception):
    """Bad material library input; the caller decides how to report it."""

    def __init__(self, source, problem):
        self.source = source
        self.problem = problem
        super().__init__(f"{source}: {problem}")


@dataclass(frozen=True)
class Shade:
    """A material's own shading values, each None where the global value in
    force applies (settings design D-9, D-20, D-23). AO samples is global
    only."""

    ao_distance_m: float | None = None
    occlusion_weight: float | None = None
    convexity_weight: float | None = None
    range: tuple[int, int] | None = None

    def given(self):
        """The values the library gives, as `(name, value)` pairs in the fixed
        order `ao_distance_m`, `occlusion_weight`, `convexity_weight`,
        `range`."""
        return tuple(
            (field.name, getattr(self, field.name))
            for field in fields(self)
            if getattr(self, field.name) is not None
        )


# The capture values among a material's shading values; `range` acts in
# stylize.
CAPTURE_VALUES = ("ao_distance_m", "occlusion_weight", "convexity_weight")


@dataclass(frozen=True)
class Generated:
    """A ramp given as properties (D-34): its `base` colour, canonical
    lowercase `#rrggbb`, its band count `bands`, its own formula values, each
    None where the global value in force applies, and its `indices`, the
    generated palette indices, None until `generate` makes them."""

    base: str
    bands: int
    lightness_step: float | None = None
    hue_shift_deg: float | None = None
    chroma_fade: float | None = None
    indices: tuple[int, ...] | None = None

    def given(self):
        """Its own formula values, as `(name, value)` pairs in `FORMULA`'s
        order."""
        return tuple(
            (name, getattr(self, name))
            for name in FORMULA
            if getattr(self, name) is not None
        )

    def formula(self, globals_):
        """The formula values it is generated with: its own, else the global
        value in `globals_` (D-33)."""
        return tuple(
            globals_[name] if getattr(self, name) is None else getattr(self, name)
            for name in FORMULA
        )


def indices(ramp):
    """A ramp's palette indices: a hand-listed ramp's own, or a generated
    one's result."""
    if isinstance(ramp, Generated):
        if ramp.indices is None:
            raise ValueError("the generated ramp has not been generated")
        return ramp.indices
    return ramp


@dataclass(frozen=True)
class Entry:
    """One material entry: its own `ramp`, the named ramp it `uses`, or
    neither, which is the `"ordinary"` look. `shade` holds its own shading
    values, or is None when it gives none; the ordinary look takes none."""

    ramp: tuple[int, ...] | Generated | None = None
    uses: str | None = None
    shade: Shade | None = None


@dataclass(frozen=True)
class Library:
    """A validated library. Both mappings are read-only and ordered by name,
    so the result never depends on the file's key order. A ramp is a tuple of
    palette indices or a `Generated` one. `shade` is the library's own
    shading values, a range only (D-36), or None."""

    ramps: MappingProxyType
    default: str | None
    materials: MappingProxyType
    shade: Shade | None = None


def check_path(path):
    """Refuse a library path whose name does not end in `.yaml` or `.yml`,
    before anything is read (settings D-11)."""
    if Path(path).suffix.lower() not in SUFFIXES:
        raise LibraryError(
            path,
            "material libraries are YAML; the file name must end in .yaml or .yml",
        )


def read_library(path, colors):
    """Read and validate the library at `path` against the palette `colors`.

    Raises `LibraryError` for bad input. Reading this file is the only effect.
    """
    path = Path(path)
    check_path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise LibraryError(path, f"cannot be read: {error.strerror or error}") from None
    return read_library_bytes(data, colors, source=path)


def read_library_bytes(data, colors, *, source):
    """Parse a library snapshot, so its contents and digest describe the same
    bytes. The bytes are one strict YAML document (`yamlfile.load`). `source`
    only labels diagnostics; a caller reading a file checks its name first
    (`check_path`).
    """
    try:
        document = yamlfile.load(data)
    except yamlfile.YamlError as error:
        raise LibraryError(source, error.problem) from None
    return validate_library(document, colors, source=source)


def validate_library(document, colors, *, source, recorded=False):
    """Validate an already-parsed library against the palette `colors`.

    Applies every structural, value and reference check. `source` only labels
    diagnostics; nothing is read and `document` is not changed. A `/2`
    library may not give generated ramps or a top-level `shade`. With
    `recorded`, the document is a sheet's inline record: each generated ramp
    must carry its `indices`, `bands` palette indices, which are kept as
    recorded; otherwise no generated ramp may carry them.
    """
    if not isinstance(document, dict):
        raise LibraryError(source, "expected a mapping")
    _check_keys(document, source)
    unknown = sorted(key for key in document if key not in _FIELDS)
    if unknown:
        raise LibraryError(source, f"unknown field {_name(unknown[0])}")
    for field in _REQUIRED:
        if field not in document:
            raise LibraryError(source, f"{field}: missing")
    if document["schema"] == PREVIOUS_SCHEMA:
        raise LibraryError(
            source,
            f"schema: {_name(PREVIOUS_SCHEMA)} libraries no longer load; change "
            f"the schema line to {_name(SCHEMA)}, the only edit the library needs",
        )
    if document["schema"] not in (SCHEMA, LEGACY_SCHEMA) or not isinstance(
        document["schema"], str
    ):
        raise LibraryError(
            source,
            f"schema: expected {_name(SCHEMA)} or {_name(LEGACY_SCHEMA)}, got "
            f"{_shown(document['schema'])}",
        )
    reading = _Reading(len(colors), source, document["schema"] == SCHEMA, recorded)
    ramps = {
        name: _ramp(value, f"ramps[{_name(name)}]", reading)
        for name, value in _named(document["ramps"], "ramps", source)
    }
    default = None
    if "default" in document:
        default = _reference(document["default"], "default", ramps, source)
    shade = None
    if "shade" in document:
        if not reading.current:
            raise LibraryError(
                source,
                f"shade: a library's own shade needs schema {_name(SCHEMA)}; "
                f"this library is {_name(LEGACY_SCHEMA)}",
            )
        shade = _library_shade(document["shade"], "shade", source)
    materials = {}
    for name, value in _named(document["materials"], "materials", source):
        materials[name] = _entry(value, f"materials[{_name(name)}]", ramps, reading)
    return Library(MappingProxyType(ramps), default, MappingProxyType(materials), shade)


def generate(library, colors, globals_, recorded=None):
    """`library` with every generated ramp's indices made into the palette
    `colors` (D-33), the formula values each ramp does not give taken from
    `globals_`, a mapping of `FORMULA` names to the global values in force.

    `recorded` is, for a reused library, the global values its recorded
    indices were generated with: a ramp whose effective formula values are
    the same under both keeps its recorded indices without regenerating, and
    any other is generated again from its recorded properties.
    """

    def made(ramp):
        if not isinstance(ramp, Generated):
            return ramp
        formula = ramp.formula(globals_)
        if (
            ramp.indices is not None
            and recorded is not None
            and ramp.formula(recorded) == formula
        ):
            return ramp
        base = tuple(int(ramp.base[i : i + 2], 16) for i in (1, 3, 5))
        return replace(
            ramp,
            indices=generation.generate(base, ramp.bands, *formula, colors),
        )

    ramps = {name: made(ramp) for name, ramp in library.ramps.items()}
    materials = {
        name: entry if entry.ramp is None else replace(entry, ramp=made(entry.ramp))
        for name, entry in library.materials.items()
    }
    return replace(
        library,
        ramps=MappingProxyType(ramps),
        materials=MappingProxyType(materials),
    )


def warnings(records, library):
    """The warnings for a model under `library`, as messages in a fixed order.

    `records` are the model's `gltf.PrimitiveMaterial`s. Each distinct named
    material the library has no entry for is named once, saying whether it
    took the default ramp or the ordinary look (D-9, D-17), a translucent
    `BLEND` material as any other (alpha design D-15); a material whose only
    alpha modes glTF does not define takes the ordinary look whatever the
    default, its warning naming the alpha mode of its lowest material index
    (the manager's note under D-15).
    One further warning counts the parts with no name (unnamed or missing
    materials, D-18), and each library entry used only by materials whose
    alpha mode glTF does not define is named. Entries and ramps the model
    never uses are silent (D-15).
    """
    parts = {}
    unnamed = 0
    for record in records:
        if record.material_index is None or record.name is None:
            unnamed += 1
            continue
        entry = parts.setdefault(
            record.name, {"index": record.material_index, "ramp": False, "other": None}
        )
        entry["index"] = min(entry["index"], record.material_index)
        if record.alpha_mode in RAMP_ALPHA_MODES:
            entry["ramp"] = True
        elif entry["other"] is None or record.material_index < entry["other"][0]:
            entry["other"] = (record.material_index, record.alpha_mode)
    messages = []
    fallback = (
        "the default ramp " + _name(library.default)
        if library.default is not None
        else "the ordinary look"
    )
    for name, used in sorted(
        parts.items(), key=lambda item: (item[1]["index"], item[0])
    ):
        if name in library.materials:
            continue
        head = f"material {_name(name)} has no entry in the material library"
        if not used["ramp"]:
            messages.append(
                f"{head}; its alpha mode {_shown(used['other'][1])} is not one glTF "
                "defines, so it takes the ordinary look"
            )
        else:
            messages.append(f"{head} and takes {fallback}")
    if unnamed:
        messages.append(
            f"{unnamed} {'part has' if unnamed == 1 else 'parts have'} no material "
            "name (an unnamed or missing material) and "
            f"{'takes' if unnamed == 1 else 'take'} the ordinary look"
        )
    for name in sorted(library.materials):
        used = parts.get(name)
        if used is not None and not used["ramp"]:
            messages.append(
                f"the library entry {_name(name)} names only materials whose alpha "
                "mode glTF does not define, which take the ordinary look"
            )
    return messages


def _ramped(records, library):
    """Each glTF material of the model that takes its library entry's ramp,
    with its entry, in material order: a named material of a glTF alpha mode,
    translucent ones included, whose entry gives a ramp or uses one."""
    taken = {}
    for record in records:
        if record.material_index is None or record.name is None:
            continue
        if record.alpha_mode not in RAMP_ALPHA_MODES:
            continue
        entry = library.materials.get(record.name)
        if entry is None or (entry.ramp is None and entry.uses is None):
            continue
        taken.setdefault(record.material_index, (record.name, entry))
    return [(index, *taken[index]) for index in sorted(taken)]


def capture_overrides(records, library, globals_):
    """The capture values of each glTF material that overrides any of them,
    as `(material index, ao_distance_m, occlusion_weight, convexity_weight)`
    in material order (settings design D-9, D-23, D-36).

    `records` are the model's `gltf.PrimitiveMaterial`s, and `globals_` maps
    each capture value's name to the global value in force. A material's own
    value wins; one it does not give is the global. Materials sharing a name
    share their entry, translucent ones as any other (alpha design D-15); one
    taking the default ramp or the ordinary look, and one with no entry, take
    the global values.
    """
    overrides = []
    for index, _, entry in _ramped(records, library):
        shade = entry.shade
        if shade is None or all(
            getattr(shade, name) is None for name in CAPTURE_VALUES
        ):
            continue
        overrides.append(
            (
                index,
                *(
                    globals_[name]
                    if getattr(shade, name) is None
                    else getattr(shade, name)
                    for name in CAPTURE_VALUES
                ),
            )
        )
    return overrides


def override_warnings(records, library, explicit):
    """The warnings for globals given explicitly that a material keeps its own
    value over (settings design D-23), in a fixed order: by material, then
    in the order `ao_distance_m`, `occlusion_weight`, `convexity_weight`,
    `range`.

    `explicit` maps the name of each shading value a `--config` file or an
    option set to that global value. Each material of the model taking its
    entry's ramp is named once per value it overrides; a value the shipped
    defaults, the user file or a loaded sheet gave warns nothing.
    """
    messages = []
    named = set()
    for _, name, entry in _ramped(records, library):
        if name in named or entry.shade is None:
            continue
        named.add(name)
        for setting, value in entry.shade.given():
            if setting not in explicit:
                continue
            shown = list(value) if setting == "range" else value
            messages.append(
                f"material {_name(name)} keeps its own shade.{setting}, "
                f"{_shown(shown)}, from the material library; the global "
                f"{_shown(list(explicit[setting]) if setting == 'range' else explicit[setting])} "
                "applies to materials without their own"
            )
    return messages


def _in_use(records, library):
    """The ramps the model's materials take, as `(label, ramp, own range)`
    in material order, each ramp once: a material's own ramp, a named ramp
    an entry uses, and the default ramp a named material of a glTF alpha
    mode without an entry takes. `own range` is whether every material taking it
    gives its own shade range."""
    used = {}
    for index, name, entry in _ramped(records, library):
        if entry.ramp is not None:
            key, label, ramp = (
                ("own", name),
                f"material {_name(name)}'s own ramp",
                entry.ramp,
            )
        else:
            key, label, ramp = (
                ("named", entry.uses),
                f"ramp {_name(entry.uses)}",
                library.ramps[entry.uses],
            )
        own = entry.shade is not None and entry.shade.range is not None
        if key in used:
            used[key][3] = used[key][3] and own
        else:
            used[key] = [index, label, ramp, own]
    if library.default is not None:
        takers = sorted(
            record.material_index
            for record in records
            if record.material_index is not None
            and record.name is not None
            and record.alpha_mode in RAMP_ALPHA_MODES
            and record.name not in library.materials
        )
        if takers:
            key = ("named", library.default)
            if key in used:
                used[key][3] = False
            else:
                used[key] = [
                    takers[0],
                    f"ramp {_name(library.default)}",
                    library.ramps[library.default],
                    False,
                ]
    return [tuple(item[1:]) for item in sorted(used.values(), key=lambda item: item[0])]


def ramp_warnings(records, library, explicit):
    """The warnings for global formula values given explicitly that a
    generated ramp in use keeps its own value over (D-33; settings design
    D-23): by ramp in the order the model first uses them, then in
    `FORMULA`'s order. `explicit` maps each formula value a `--config` file
    or an option set to that global value; the shipped defaults, the user
    file and a loaded sheet set none."""
    messages = []
    for label, ramp, _ in _in_use(records, library):
        if not isinstance(ramp, Generated):
            continue
        for setting, value in ramp.given():
            if setting in explicit:
                messages.append(
                    f"{label} keeps its own {setting}, {_shown(value)}, from the "
                    f"material library; the global {_shown(explicit[setting])} "
                    "applies to generated ramps without their own"
                )
    return messages


def library_shade_warnings(records, library, explicit):
    """The warning for a global shade range given explicitly that the
    library's own range beats (D-35, D-36; settings design D-23): one,
    naming the library's value, when a material in use takes it."""
    if (
        "range" not in explicit
        or library.shade is None
        or library.shade.range is None
        or all(own for _, _, own in _in_use(records, library))
    ):
        return []
    return [
        f"the material library gives shade.range {_shown(list(library.shade.range))} "
        "to its materials without their own; the global "
        f"{_shown(list(explicit['range']))} does not reach them"
    ]


def _named(mapping, location, source):
    """Yield a name-keyed mapping's items in name order, checking each name."""
    if not isinstance(mapping, dict):
        raise LibraryError(source, f"{location}: expected a mapping")
    _check_keys(mapping, source, location)
    for name in sorted(mapping):
        if name == "":
            raise LibraryError(source, f"{location}: the empty name is not allowed")
        yield name, mapping[name]


def _check_keys(mapping, source, location=None):
    # An unquoted YAML key such as `1` or `true` is not a string, and an
    # already-parsed library might hold any key.
    for key in mapping:
        if not isinstance(key, str):
            where = f"{location}: " if location else ""
            raise LibraryError(source, f"{where}key {_shown(key)} is not a string")


@dataclass(frozen=True)
class _Reading:
    """What validating one library needs: the palette size, the source for
    diagnostics, whether it is the current schema, and whether it is a
    sheet's inline record."""

    size: int
    source: object
    current: bool
    recorded: bool


def _ramp(value, location, reading):
    """A ramp: a list of palette indices, or (in a `/3` library) a mapping of
    properties for a generated one."""
    if isinstance(value, dict):
        return _generated(value, location, reading)
    return _listed(value, location, reading.size, reading.source)


def _generated(value, location, reading):
    source = reading.source
    if not reading.current:
        raise LibraryError(
            source,
            f"{location}: a generated ramp needs schema {_name(SCHEMA)}; this "
            f"library is {_name(LEGACY_SCHEMA)}",
        )
    _check_keys(value, source, location)
    known = ("base", "bands", *FORMULA, *(("indices",) if reading.recorded else ()))
    unknown = sorted(key for key in value if key not in known)
    if unknown:
        raise LibraryError(source, f"{location}: unknown field {_name(unknown[0])}")
    for required in ("base", "bands", *(("indices",) if reading.recorded else ())):
        if required not in value:
            raise LibraryError(source, f"{location}.{required}: missing")
    base = value["base"]
    if not isinstance(base, str) or not _BASE.fullmatch(base):
        raise LibraryError(
            source, f"{location}.base: expected an sRGB #rrggbb, got {_shown(base)}"
        )
    bands = value["bands"]
    if isinstance(bands, bool) or not isinstance(bands, Integral):
        raise LibraryError(
            source,
            f"{location}.bands: expected a whole number from 1 to {MAX_RAMP}, got "
            f"{_shown(bands)}",
        )
    if not 1 <= bands <= MAX_RAMP:
        raise LibraryError(
            source,
            f"{location}.bands: expected a whole number from 1 to {MAX_RAMP}, got "
            f"{int(bands)}",
        )
    own = {}
    for name in FORMULA:
        if name not in value:
            continue
        low, high = FORMULA_LIMITS[name]
        number = _finite(value[name])
        if number is None or not low <= number <= high:
            raise LibraryError(
                source,
                f"{location}.{name}: expected a finite number from {_number(low)} to "
                f"{_number(high)}, got {_shown(value[name])}",
            )
        own[name] = number
    recorded = None
    if reading.recorded:
        recorded = _listed(
            value["indices"], f"{location}.indices", reading.size, source
        )
        if len(recorded) != bands:
            raise LibraryError(
                source,
                f"{location}.indices: has {len(recorded)} entries; expected "
                f"{int(bands)}, its bands",
            )
    return Generated(base.lower(), int(bands), indices=recorded, **own)


def _number(value):
    return str(int(value)) if value == int(value) else str(value)


def _listed(value, location, size, source):
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


def _entry(value, location, ramps, reading):
    source = reading.source
    if isinstance(value, str) and value == ORDINARY:
        return Entry()
    if not isinstance(value, dict):
        raise LibraryError(
            source,
            f'{location}: expected {{"ramp": [...]}}, {{"uses": NAME}} or '
            f'"{ORDINARY}", got {_shown(value)}',
        )
    _check_keys(value, source, location)
    unknown = sorted(key for key in value if key not in ("ramp", "uses", "shade"))
    if unknown:
        raise LibraryError(source, f"{location}: unknown field {_name(unknown[0])}")
    if ("ramp" in value) == ("uses" in value):
        raise LibraryError(
            source, f'{location}: expected exactly one of "ramp" and "uses"'
        )
    shade = (
        _shade(value["shade"], f"{location}.shade", source)
        if "shade" in value
        else None
    )
    if "ramp" in value:
        ramp = _ramp(value["ramp"], f"{location}.ramp", reading)
        return Entry(ramp=ramp, shade=shade)
    uses = _reference(value["uses"], f"{location}.uses", ramps, source)
    return Entry(uses=uses, shade=shade)


def _shade(value, location, source):
    """A material's own shading values, checked with the global values'
    limits (settings design D-30), or None when it gives none."""
    if not isinstance(value, dict):
        raise LibraryError(
            source,
            f"{location}: expected a mapping of shading values, got {_shown(value)}",
        )
    _check_keys(value, source, location)
    if "ao_samples" in value:
        raise LibraryError(
            source,
            f"{location}.ao_samples: AO samples is a global setting only; set it "
            "with --ao-samples or shade.ao_samples in a settings file",
        )
    known = [field.name for field in fields(Shade)]
    unknown = sorted(key for key in value if key not in known)
    if unknown:
        raise LibraryError(source, f"{location}: unknown field {_name(unknown[0])}")
    given = {}
    for name in known:
        if name not in value:
            continue
        here = f"{location}.{name}"
        item = value[name]
        if name == "range":
            given[name] = _shade_range(item, here, source)
            continue
        number = _finite(item)
        if number is None or (number <= 0 if name == "ao_distance_m" else number < 0):
            wanted = "greater than 0" if name == "ao_distance_m" else "0 or greater"
            raise LibraryError(
                source, f"{here}: expected a finite number {wanted}, got {_shown(item)}"
            )
        given[name] = number
    return Shade(**given) if given else None


def _library_shade(value, location, source):
    """A library's own shading values: the shade range only (D-36)."""
    if not isinstance(value, dict):
        raise LibraryError(
            source,
            f"{location}: expected a mapping of shading values, got {_shown(value)}",
        )
    _check_keys(value, source, location)
    for name in (*CAPTURE_VALUES, "ao_samples"):
        if name in value:
            raise LibraryError(
                source,
                f"{location}.{name}: a library's own shade gives only range; give "
                f"{name} in a material's own shade, or as a global setting",
            )
    shade = _shade(value, location, source)
    return shade


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _shade_range(value, location, source):
    if (
        isinstance(value, list | tuple)
        and len(value) == 2
        and all(
            isinstance(bound, int) and not isinstance(bound, bool) for bound in value
        )
        and 0 <= value[0] < value[1] <= 255
    ):
        return int(value[0]), int(value[1])
    raise LibraryError(
        source,
        f"{location}: expected [lo, hi], two integers with 0 <= lo < hi <= 255, "
        f"got {_shown(value)}",
    )


def _name(name):
    """Show a name exactly, quotes and whitespace included."""
    return json.dumps(name, ensure_ascii=False)


def _shown(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return repr(value)
