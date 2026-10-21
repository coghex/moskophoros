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
loads and reads exactly as before. A `/4` library, the current one, may also
give the shading response in the `shade` of an entry and of the library, and
an ordinary entry as a mapping that carries a `shade` of its own (shading
design contract 2, D-33); `/2` and `/3` libraries cannot.
"""

import json
import math
import re
from dataclasses import dataclass, field, fields, replace
from numbers import Integral
from pathlib import Path
from types import MappingProxyType

from moskophoros import ramps as generation
from moskophoros import shading, yamlfile

# The schema with generated ramps and a library shade, which still loads and
# reads exactly as before.
SCHEMA = "moskophoros.materials/3"
# The current schema, with the shading response and ordinary entries as
# mappings (shading design contract 2).
SCHEMA_V4 = "moskophoros.materials/4"
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
    only.

    The fields after `range` are the shading response (shading design
    contract 2), given only by a `/4` library: the leaves of
    `shading.Response`, named as it names them. A library-wide shade gives
    `range` and those only.
    """

    ao_distance_m: float | None = None
    occlusion_weight: float | None = None
    convexity_weight: float | None = None
    range: tuple[int, int] | None = None
    mode: str | None = None
    ambient_form: bool | None = None
    key_strength: float | None = None
    sky_strength: float | None = None
    ground_strength: float | None = None
    brightness_floor: float | None = None
    brightness_ceiling: float | None = None
    dither_pattern: str | None = None
    dither_strength: float | None = None

    def given(self):
        """The values the library gives, as `(name, value)` pairs in the fixed
        order `ao_distance_m`, `occlusion_weight`, `convexity_weight`,
        `range`, then the response in the settings table's order."""
        return tuple(
            (item.name, getattr(self, item.name))
            for item in fields(self)
            if getattr(self, item.name) is not None
        )

    def document(self):
        """The values the library gives, as the mapping they were supplied
        in: the first four flat, the response leaves as `shade` names them,
        `key`, `sky`, `ground`, `brightness` and `dither` nested. The values
        are as supplied, never merged with an inherited one."""
        document = {}
        for name, value in self.given():
            if name in RESPONSE_NAMES:
                continue
            document[name] = list(value) if name == "range" else value
        for path, name in shading.FIELDS.items():
            value = getattr(self, name)
            if value is None:
                continue
            group, _, leaf = path.rpartition(".")
            target = document.setdefault(group, {}) if group else document
            target[leaf] = value
        return document


# The capture values among a material's shading values; `range` acts in
# stylize.
CAPTURE_VALUES = ("ao_distance_m", "occlusion_weight", "convexity_weight")
# The shading response's names among them (`shading.Response`'s fields).
RESPONSE_NAMES = tuple(shading.FIELDS.values())


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
    values, or is None when it gives none; the string `"ordinary"` takes
    none, and a `/4` ordinary mapping (`{ordinary: true, shade: ...}`) may
    carry them. `ordinary_mapping` says the entry was given as that mapping
    rather than as the string, which a sheet records as it was given."""

    ramp: tuple[int, ...] | Generated | None = None
    uses: str | None = None
    shade: Shade | None = None
    ordinary_mapping: bool = False


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
    # Where the library came from, for diagnostics, its schema, and the
    # `(line, column)` of each shading value it gave, by path from the
    # document's root, such as `("materials", "Painted", "shade", "key",
    # "strength")`. Only a library read from file bytes has positions. None
    # of the three takes part in comparing libraries.
    source: object = field(default=None, compare=False, repr=False)
    schema: str | None = field(default=None, compare=False, repr=False)
    where: MappingProxyType = field(
        default=MappingProxyType({}), compare=False, repr=False
    )

    def origin(self, path):
        """Where the value at `path` was given, as an error shows it: the
        source and its line and column when the library has them, else the
        source and the key path, such as `materials["Painted"].shade.mode`."""
        path = tuple(path)
        label = "the material library" if self.source is None else str(self.source)
        position = self.where.get(path)
        if position is not None:
            return f"{label} line {position[0]}, column {position[1]}"
        return f"{label}: {_key_path(path)}"


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
    bytes. The bytes are one strict YAML document (`yamlfile.load_located`).
    `source` only labels diagnostics; a caller reading a file checks its name
    first (`check_path`).

    The document is read with its positions, so an error about a shading
    value names its line and column, and the library keeps them for the
    errors the resolved values cause (`Library.origin`).
    """
    try:
        document, marks = yamlfile.load_located(data)
    except yamlfile.YamlError as error:
        raise LibraryError(source, error.problem) from None
    return validate_library(document, colors, source=source, marks=marks)


def validate_library(document, colors, *, source, recorded=False, marks=None):
    """Validate an already-parsed library against the palette `colors`.

    Applies every structural, value and reference check. `source` only labels
    diagnostics; nothing is read and `document` is not changed. A `/2`
    library may not give generated ramps or a top-level `shade`, and a `/2`
    or `/3` library may not give the shading response or an ordinary entry as
    a mapping, which need `/4` (shading design contract 2). With `recorded`,
    the document is a sheet's inline record: each generated ramp must carry
    its `indices`, `bands` palette indices, which are kept as recorded;
    otherwise no generated ramp may carry them.

    `marks` are the document's positions (`yamlfile.load_located`), which
    only a library read from file bytes has.
    """
    if not isinstance(document, dict):
        raise LibraryError(source, "expected a mapping")
    _check_keys(document, source)
    unknown = sorted(key for key in document if key not in _FIELDS)
    if unknown:
        raise LibraryError(source, f"unknown field {_name(unknown[0])}")
    for required in _REQUIRED:
        if required not in document:
            raise LibraryError(source, f"{required}: missing")
    if document["schema"] == PREVIOUS_SCHEMA:
        raise LibraryError(
            source,
            f"schema: {_name(PREVIOUS_SCHEMA)} libraries no longer load; change "
            f"the schema line to {_name(SCHEMA_V4)}, the only edit the library "
            "needs",
        )
    accepted = (SCHEMA_V4, SCHEMA, LEGACY_SCHEMA)
    if not isinstance(document["schema"], str) or document["schema"] not in accepted:
        listed = f"{_name(SCHEMA_V4)}, {_name(SCHEMA)} or {_name(LEGACY_SCHEMA)}"
        raise LibraryError(
            source,
            f"schema: expected {listed}, got {_shown(document['schema'])}",
        )
    reading = _Reading(len(colors), source, document["schema"], recorded, marks=marks)
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
                f"shade: a library's own shade needs {SCHEMA} or later; this "
                f"library is {_name(LEGACY_SCHEMA)}",
            )
        shade = _library_shade(document["shade"], "shade", reading, ("shade",))
    materials = {}
    for name, value in _named(document["materials"], "materials", source):
        materials[name] = _entry(
            value, f"materials[{_name(name)}]", ramps, reading, ("materials", name)
        )
    return Library(
        MappingProxyType(ramps),
        default,
        MappingProxyType(materials),
        shade,
        source=source,
        schema=document["schema"],
        where=MappingProxyType(reading.where),
    )


def recorded_schema(record):
    """The schema a sheet's inline library `record`, a mapping with its
    `materials` and optional `shade`, is read under: `/4` when it uses
    anything only `/4` has, an ordinary entry given as a mapping or a shading
    response in a `shade`, else `/3`, which a library of any older schema is
    recorded as. A sheet does not record the schema line, so this reads it
    off the record, and a reused library behaves as the library it was."""
    response = {*_RESPONSE_TOP, *_GLOBAL_ONLY}
    shades = [record.get("shade")]
    entries = record.get("materials")
    # A record that is not well formed is `validate_library`'s to refuse.
    for entry in entries.values() if isinstance(entries, dict) else ():
        if isinstance(entry, dict):
            if ORDINARY in entry:
                return SCHEMA_V4
            shades.append(entry.get("shade"))
    for shade in shades:
        if isinstance(shade, dict) and response & set(shade):
            return SCHEMA_V4
    return SCHEMA


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


def _taken(records, library):
    """`_ramped`'s materials, and with them each glTF material of the model
    whose entry is an ordinary mapping with shading values of its own, in
    material order (shading design contract 2, D-33)."""
    taken = {}
    for record in records:
        if record.material_index is None or record.name is None:
            continue
        if record.alpha_mode not in RAMP_ALPHA_MODES:
            continue
        entry = library.materials.get(record.name)
        if entry is None or (
            entry.ramp is None and entry.uses is None and entry.shade is None
        ):
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
    the global values. An ordinary mapping entry (in a `/4` library)
    overrides them like any other.
    """
    overrides = []
    for index, _, entry in _taken(records, library):
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

    `explicit` maps the name of each shading value an option or a project file
    set to that global value. Each material of the model taking its entry's
    ramp is named once per value it overrides; a value the shipped defaults,
    the global file (the user file or the one `--config` replaces it with) or
    a loaded sheet gave warns nothing (shading design D-41).
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
    `FORMULA`'s order. `explicit` maps each formula value an option or a
    project file set to that global value; the shipped defaults, the global
    file (the user file or the one `--config` replaces it with) and a loaded
    sheet set none (shading design D-41)."""
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
    if "range" not in explicit or library.shade is None or library.shade.range is None:
        return []
    if library.schema == SCHEMA_V4:
        # Every class of part takes the library's range where it has none of
        # its own: ordinary entries, materials without an entry and parts
        # without an identity too.
        reached = _takes_library(records, library, "range")
    else:
        reached = not all(own for _, _, own in _in_use(records, library))
    if not reached:
        return []
    return [
        f"the material library gives shade.range {_shown(list(library.shade.range))} "
        "to its materials without their own; the global "
        f"{_shown(list(explicit['range']))} does not reach them"
    ]


# The `explicit` name of each response field of `Shade`: its leaf path, such
# as `key.strength`. The other names are those of `Shade`'s first four fields.
_LEAF_OF = MappingProxyType({name: path for path, name in shading.FIELDS.items()})


def shadow_warnings(records, library, explicit, formula, origins=None):
    """Every warning for a global given explicitly that a library or material
    value takes precedence over, in a fixed order: the materials' own values,
    by material and then in `Shade`'s order; the library's own shade, the range
    first and then the response in `shading.FIELDS`' order; then the
    generated ramps' (settings design D-23, D-33; shading design contract 2,
    D-41).

    `explicit` maps the name of each shading value an option or a project file
    set to that global value (`ao_distance_m`, `range`, and a response leaf as
    its path under `shade`, such as `key.strength`); `formula` maps each
    formula value the same way, as `ramp_warnings` takes it. Which layers are
    explicit is the caller's decision: this adds no rule of its own. `origins`
    maps those same names to where the global value came from, such as
    `--bake-key-strength`, which a message about a response leaf or an
    ordinary entry shows.

    Defaults, ordinary inheritance and a term merely being off warn nothing.
    For a `/2` or `/3` library these are exactly the messages of
    `override_warnings`, `library_shade_warnings` and `ramp_warnings`, in that
    order; an ordinary mapping entry is named like a ramped one.
    """
    origins = origins or {}
    return [
        *_entry_warnings(records, library, explicit, origins),
        *library_shade_warnings(records, library, explicit),
        *_library_response_warnings(records, library, explicit, origins),
        *ramp_warnings(records, library, formula),
    ]


def _entry_warnings(records, library, explicit, origins):
    messages = []
    named = set()
    for _, name, entry in _taken(records, library):
        if name in named or entry.shade is None:
            continue
        named.add(name)
        ordinary = entry.ramp is None and entry.uses is None
        for setting, value in entry.shade.given():
            key = _LEAF_OF.get(setting, setting)
            if key not in explicit:
                continue
            if not ordinary and setting not in RESPONSE_NAMES:
                # The existing wording, unchanged, for the existing values.
                shown = list(value) if setting == "range" else value
                messages.append(
                    f"material {_name(name)} keeps its own shade.{setting}, "
                    f"{_shown(shown)}, from the material library; the global "
                    f"{_shown(list(explicit[setting]) if setting == 'range' else explicit[setting])} "
                    "applies to materials without their own"
                )
                continue
            own = library.origin(("materials", name, "shade", *key.split(".")))
            messages.append(
                f"material {_name(name)} keeps its own shade.{key}, "
                f"{_shown(value)} ({own}), from the material library; the "
                f"global {_shown(explicit[key])}{_origin(origins, key)} "
                "applies to materials without their own"
            )
    return messages


def _library_response_warnings(records, library, explicit, origins):
    """The warnings for a global response leaf given explicitly that the
    library's own shade beats for a part of the model: one per leaf,
    when some part takes the library's value."""
    if library.shade is None:
        return []
    messages = []
    for path, name in shading.FIELDS.items():
        value = getattr(library.shade, name)
        if value is None or path not in explicit:
            continue
        if not _takes_library(records, library, name):
            continue
        own = library.origin(("shade", *path.split(".")))
        messages.append(
            f"the material library gives shade.{path} {_shown(value)} ({own}) "
            "to its materials without their own; the global "
            f"{_shown(explicit[path])}{_origin(origins, path)} does not reach "
            "them"
        )
    return messages


def _takes_library(records, library, name):
    """Whether some part of the model takes the library's own value of the
    response field `name`: a part with no material name, a material with no
    entry that applies, or one whose entry does not give it."""
    taken = {material: entry for _, material, entry in _taken(records, library)}
    for record in records:
        if record.material_index is None or record.name is None:
            return True
        # A part of an alpha mode glTF does not define takes the ordinary
        # look whatever other parts of its name do.
        entry = (
            taken.get(record.name) if record.alpha_mode in RAMP_ALPHA_MODES else None
        )
        if entry is None or entry.shade is None or getattr(entry.shade, name) is None:
            return True
    return False


def _origin(origins, name):
    return f" ({origins[name]})" if name in origins else ""


def _named(mapping, location, source):
    """Yield a name-keyed mapping's items in name order, checking each name."""
    if not isinstance(mapping, dict):
        raise LibraryError(source, f"{location}: expected a mapping")
    _check_keys(mapping, source, location)
    for name in sorted(mapping):
        if name == "":
            raise LibraryError(source, f"{location}: the empty name is not allowed")
        yield name, mapping[name]


def _check_keys(mapping, source, location=None, reading=None, path=()):
    # An unquoted YAML key such as `1` or `true` is not a string, and an
    # already-parsed library might hold any key. With `reading`, the message
    # gives the key's position.
    for key in mapping:
        if not isinstance(key, str):
            where = f"{location}: " if location else ""
            at = "" if reading is None else reading.at((*path, key))
            raise LibraryError(source, f"{where}key {_shown(key)} is not a string{at}")


@dataclass(frozen=True)
class _Reading:
    """What validating one library needs: the palette size, the source for
    diagnostics, its schema, whether it is a sheet's inline record, and, for a
    library read from file bytes, the document's positions and the positions
    of the shading values read, by path."""

    size: int
    source: object
    schema: str
    recorded: bool
    marks: object = None
    where: dict = field(default_factory=dict)

    @property
    def current(self):
        """Whether the schema is `/3` or later: generated ramps and a
        library shade."""
        return self.schema in (SCHEMA, SCHEMA_V4)

    @property
    def response(self):
        """Whether the schema is `/4`, which may give the shading response
        and ordinary entries as mappings."""
        return self.schema == SCHEMA_V4

    def at(self, path):
        """` at line L, column C` for the key at `path`, empty without the
        document's positions."""
        if self.marks is None:
            return ""
        line, column = yamlfile.locate(self.marks, path)
        return f" at line {line}, column {column}"

    def note(self, path):
        """Keep the position of the value at `path`, if there are any."""
        if self.marks is not None:
            self.where[tuple(path)] = yamlfile.locate(self.marks, path)


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
            f"{location}: a generated ramp needs {SCHEMA} or later; this "
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


def _entry(value, location, ramps, reading, path):
    source = reading.source
    if isinstance(value, str) and value == ORDINARY:
        return Entry()
    if not isinstance(value, dict):
        raise LibraryError(
            source,
            f'{location}: expected {{"ramp": [...]}}, {{"uses": NAME}} or '
            f'"{ORDINARY}", got {_shown(value)}{reading.at(path)}',
        )
    _check_keys(value, source, location, reading, path)
    mapping = ("ramp", "uses", "shade", *(("ordinary",) if reading.response else ()))
    unknown = sorted(key for key in value if key not in mapping)
    if unknown:
        raise LibraryError(
            source,
            f"{location}: unknown field {_name(unknown[0])}"
            f"{reading.at((*path, unknown[0]))}",
        )
    forms = [form for form in ("ramp", "uses", "ordinary") if form in value]
    if len(forms) != 1:
        raise LibraryError(
            source,
            (
                f'{location}: expected exactly one of "ramp", "uses" and "ordinary"'
                if reading.response
                else f'{location}: expected exactly one of "ramp" and "uses"'
            )
            + reading.at(path),
        )
    if forms == ["ordinary"] and value["ordinary"] is not True:
        raise LibraryError(
            source,
            f"{location}.ordinary: expected true, which is the ordinary look, got "
            f"{_shown(value['ordinary'])}"
            f"{reading.at((*path, 'ordinary'))}",
        )
    shade = (
        _shade(value["shade"], f"{location}.shade", reading, (*path, "shade"))
        if "shade" in value
        else None
    )
    if "ramp" in value:
        ramp = _ramp(value["ramp"], f"{location}.ramp", reading)
        return Entry(ramp=ramp, shade=shade)
    if "ordinary" in value:
        return Entry(shade=shade, ordinary_mapping=True)
    uses = _reference(value["uses"], f"{location}.uses", ramps, source)
    return Entry(uses=uses, shade=shade)


# The shading leaves a library may not override (contract 2), by top-level
# key of a `shade` mapping, and the groups of those it may.
_GLOBAL_ONLY = ("sky_ground_frame", "snap")
_RESPONSE_GROUPS = tuple(
    dict.fromkeys(path.split(".")[0] for path in shading.FIELDS if "." in path)
)
_RESPONSE_TOP = tuple(dict.fromkeys(path.split(".")[0] for path in shading.FIELDS))


def _shade(value, location, reading, path, library=False):
    """A material's own shading values, checked with the global values'
    limits (settings design D-30), or None when it gives none. With
    `library`, the library's own, which give the range and the response
    only (D-36), never the capture values.

    A `/4` library may also give the response leaves (contract 2), nested as
    a settings file nests them; each leaf is
    checked on its own, whatever the value would resolve to, and its
    position is kept. Cross-field rules wait for the resolved values
    (`shading_resolve`)."""
    source = reading.source
    if not isinstance(value, dict):
        raise LibraryError(
            source,
            f"{location}: expected a mapping of shading values, got {_shown(value)}"
            f"{reading.at(path)}",
        )
    _check_keys(value, source, location, reading, path)
    if library:
        for name in (*CAPTURE_VALUES, "ao_samples"):
            if name in value:
                raise LibraryError(
                    source,
                    f"{location}.{name}: a library's own shade gives only "
                    f"{'range and the shading response' if reading.response else 'range'}"
                    f"; give {name} in a material's own shade, or as a global setting"
                    f"{reading.at((*path, name))}",
                )
    elif "ao_samples" in value:
        raise LibraryError(
            source,
            f"{location}.ao_samples: AO samples is a global setting only; set it "
            "with --ao-samples or shade.ao_samples in a settings file"
            f"{reading.at((*path, 'ao_samples'))}",
        )
    known = [*CAPTURE_VALUES, "range"]
    _check_response_keys(value, location, reading, path)
    known += [name for name in _RESPONSE_TOP if name in value]
    unknown = sorted(key for key in value if key not in known)
    if unknown:
        raise LibraryError(
            source,
            f"{location}: unknown field {_name(unknown[0])}"
            f"{reading.at((*path, unknown[0]))}",
        )
    given = {}
    for name in (*CAPTURE_VALUES, "range"):
        if name not in value:
            continue
        here = f"{location}.{name}"
        item = value[name]
        if name == "range":
            given[name] = _shade_range(item, here, source, reading.at((*path, name)))
        else:
            number = _finite(item)
            if number is None or (
                number <= 0 if name == "ao_distance_m" else number < 0
            ):
                wanted = "greater than 0" if name == "ao_distance_m" else "0 or greater"
                raise LibraryError(
                    source,
                    f"{here}: expected a finite number {wanted}, got {_shown(item)}"
                    f"{reading.at((*path, name))}",
                )
            given[name] = number
        reading.note((*path, name))
    given |= _response(value, location, reading, path)
    return Shade(**given) if given else None


def _library_shade(value, location, reading, path):
    """A library's own shading values: the shade range (D-36), and in a `/4`
    library the shading response."""
    return _shade(value, location, reading, path, library=True)


def _check_response_keys(value, location, reading, path):
    """Refuse a response key the library's schema or place does not allow:
    one a `/2` or `/3` library may not give, and the global-only leaves."""
    source = reading.source
    for name in sorted(value):
        here = f"{location}.{name}"
        if name in _RESPONSE_TOP and not reading.response:
            raise LibraryError(
                source,
                f"{here}: the shading response needs {SCHEMA_V4}; this library "
                f"is {_name(reading.schema)}{reading.at((*path, name))}",
            )
        if name in _GLOBAL_ONLY and reading.response:
            raise LibraryError(
                source,
                f"{here}: shade.{name} is a global setting only; set it with its "
                f"option or in a settings file{reading.at((*path, name))}",
            )


def _response(value, location, reading, path):
    """The response leaves `value` gives, as `Shade` fields, each checked and
    its position kept."""
    source = reading.source
    given = {}
    for name in _RESPONSE_TOP:
        if name not in value:
            continue
        item = value[name]
        if name in _RESPONSE_GROUPS:
            if not isinstance(item, dict):
                raise LibraryError(
                    source,
                    f"{location}.{name}: expected a mapping of shading values, got "
                    f"{_shown(item)}{reading.at((*path, name))}",
                )
            _check_keys(item, source, f"{location}.{name}", reading, (*path, name))
            for leaf in sorted(item):
                leaf_path = f"{name}.{leaf}"
                if leaf_path == "key.direction":
                    raise LibraryError(
                        source,
                        f"{location}.{leaf_path}: shade.key.direction is a global "
                        "setting only; set it with its option or in a settings "
                        f"file{reading.at((*path, name, leaf))}",
                    )
                if leaf_path not in shading.FIELDS:
                    raise LibraryError(
                        source,
                        f"{location}.{name}: unknown field {_name(leaf)}"
                        f"{reading.at((*path, name, leaf))}",
                    )
            for leaf in sorted(item):
                given[shading.FIELDS[f"{name}.{leaf}"]] = _leaf(
                    item[leaf],
                    f"{name}.{leaf}",
                    f"{location}.{name}.{leaf}",
                    reading,
                    (*path, name, leaf),
                )
            continue
        given[shading.FIELDS[name]] = _leaf(
            item, name, f"{location}.{name}", reading, (*path, name)
        )
    return given


def _leaf(item, leaf_path, location, reading, path):
    """One response leaf's checked value, and its position kept."""
    try:
        checked = shading.BY_PATH[leaf_path].check(item)
    except shading.Bad as error:
        raise LibraryError(
            reading.source,
            f"{location}: {error.problem(_shown)}{reading.at(path)}",
        ) from None
    reading.note(path)
    return checked


def _key_path(path):
    """A path from a library's root as a key path: `materials["Painted"]
    .shade.mode`."""
    if len(path) >= 2 and path[0] in ("ramps", "materials"):
        return f"{path[0]}[{_name(path[1])}]" + "".join(f".{step}" for step in path[2:])
    return ".".join(path)


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _shade_range(value, location, source, at=""):
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
        f"got {_shown(value)}{at}",
    )


def _name(name):
    """Show a name exactly, quotes and whitespace included."""
    return json.dumps(name, ensure_ascii=False)


def _shown(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return repr(value)
