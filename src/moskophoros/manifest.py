"""The generic export manifest, `moskophoros.export/1` (export design P-8,
P-8a): its writer and its strict reader.

`build` describes an export from the resolved plans and the encoded
artifacts, `encode` serializes it, and `settings_record` is the manifest's
`settings` object, built independently of `capture.backend.settings_document`
so no export setting reaches a capture job. `decode` reads a manifest back
from its bytes, checking every member and every record the others imply,
and `read` reads a file first. The reader returns a `Manifest` holding the
settings as the layer they reload into (`Manifest.source`), the legacy
`cli.ReusedSettings` of the values that existed before this schema, and the
validated document.

The command does not call any of this yet: it still writes and loads
`moskophoros.sheet/15`, and `cli.read_settings` refuses this schema. Only
`read` touches the file system, and only to read the manifest itself: no
artifact, palette or library file is opened. Everything else is pure.
"""

import argparse
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from moskophoros import cli, export, exportsettings, outputs, sampling, views
from moskophoros import settings as layered
from moskophoros.capture import backend
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.usage import UsageError

SCHEMA = "moskophoros.export/1"
SHEET_PREFIX = "moskophoros.sheet/"
FLIP_X = "flip-x"
MAX_PROBLEMS = 10

# The members of each object, in serialized order (design P-8a).
DOCUMENT = (
    "schema",
    "generator",
    "source",
    "subject",
    "variant",
    "settings",
    "fingerprint",
    "artifacts",
    "directions",
    "clips",
    "frames",
)
GENERATOR = (
    "tool",
    "version",
    "python",
    "numpy",
    "pillow",
    "blender",
    "renderer",
    "color",
    "shade",
)
SOURCE = ("file", "sha256")
SETTINGS = (
    "view",
    "camera",
    "model_yaw_deg",
    "fps",
    "frames",
    "supersample",
    "pixels_per_meter",
    "cell",
    "ground_m",
    "ground_px",
    "root_motion",
    "previews",
    "normals",
    "depth",
    "light",
    "shade",
    "ramp",
    "style",
    "stored_directions",
    "direction_names",
    "mirrors",
    "export",
    "clips",
)
EXPORT = ("formats", "frame_path", "atlas_path", "sheet_path", "atlas_padding")
SETTINGS_CLIP = (
    "name",
    "loop",
    "frames",
    "fps",
    "stored_directions",
    "mirrors",
    "output_name",
)
ARTIFACT = ("kind", "channel", "path", "width", "height")
DIRECTION = ("index", "angle_deg", "label", "output_name")
CLIP = (
    "name",
    "loop",
    "duration_s",
    "frame_count",
    "frame_duration_s",
    "time_scale",
    "output_name",
    "fps",
    "stored_directions",
    "mirrors",
)
MIRROR = ("target", "source", "transform", "ground_px")
FRAME = ("clip", "direction", "index", "time_s", "locations")
LOCATION = ("artifact", "x", "y", "w", "h")

SHEET, ATLAS, FRAME_KIND, PREVIEW = (
    outputs.SHEET,
    outputs.ATLAS,
    outputs.FRAME,
    outputs.PREVIEW,
)
COLOR, NORMAL, DEPTH, FLAT, LIT = (
    outputs.COLOR,
    outputs.NORMAL,
    outputs.DEPTH,
    outputs.FLAT,
    outputs.LIT,
)
PNG_KINDS = (SHEET, ATLAS, FRAME_KIND)
CHANNELS = {
    SHEET: (COLOR, NORMAL, DEPTH),
    ATLAS: (COLOR, NORMAL, DEPTH),
    FRAME_KIND: (COLOR, NORMAL, DEPTH),
    PREVIEW: (FLAT, LIT),
}
_SHA256 = re.compile(r"[0-9a-f]{64}")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")


# Writing


def settings_record(
    settings,
    resolved,
    request,
    style,
    *,
    shade_range,
    previews=True,
    normals=True,
    depth=False,
    light=export.NO_LIGHT,
    ramp=export.DEFAULT_RAMP,
    shading=None,
):
    """The manifest's `settings` object (design P-8a), in serialized order.

    `settings` are the fitted capture settings, `resolved` the
    `exportsettings.ExportSettings` and `request` the `plan.RequestPlan` of
    the same run, whose selected clips are recorded in selection order with
    each override as supplied. `style` is the look record
    (`cli.style_record`), recorded as given; `shade_range`, `previews`,
    `normals`, `depth`, `light`, `ramp` and `shading` are as
    `export.sheet_settings` takes them. Nothing here builds or reads the
    capture job's settings document.
    """
    if settings.ppm is None or settings.cell is None or settings.ground_px is None:
        raise ValueError("the settings are not fitted: scale, cell and ground pixel")
    if float(settings.fps) != resolved.fps or settings.frames != resolved.frames:
        raise ValueError("the resolved export settings and the capture settings differ")
    capture = settings.shade
    shade = {
        "ao_distance_m": float(capture.ao_distance_m),
        "ao_samples": capture.ao_samples,
        "occlusion_weight": float(capture.occlusion_weight),
        "convexity_weight": float(capture.convexity_weight),
        "range": [int(bound) for bound in shade_range],
    } | export.shading_record(shading)
    return {
        "view": {
            "preset": settings.view,
            "directions": settings.directions,
            "start_angle_deg": float(settings.start_angle),
        },
        "camera": {
            "projection": settings.projection,
            "direction": [float(component) for component in settings.direction],
            "roll": float(settings.roll),
            "position": (
                None
                if settings.position is None
                else [float(coordinate) for coordinate in settings.position]
            ),
        },
        "model_yaw_deg": float(settings.model_yaw),
        "fps": float(settings.fps),
        "frames": settings.frames,
        "supersample": settings.supersample,
        "pixels_per_meter": float(settings.ppm),
        "cell": {"width": settings.cell[0], "height": settings.cell[1]},
        "ground_m": dict(zip("xyz", map(float, settings.ground), strict=True)),
        "ground_px": {"x": settings.ground_px[0], "y": settings.ground_px[1]},
        "root_motion": settings.root_motion,
        "previews": previews,
        "normals": normals,
        "depth": depth,
        "light": light.record(),
        "shade": shade,
        "ramp": {
            name: float(ramp[name])
            for name in ("lightness_step", "hue_shift_deg", "chroma_fade")
        },
        "style": style,
        "stored_directions": _stored_array(resolved.stored_directions),
        "direction_names": [
            {"index": index, "name": name}
            for index, name in sorted(resolved.direction_names.items())
        ],
        "mirrors": _mirror_array(resolved.mirrors),
        "export": {
            "formats": list(resolved.formats),
            "frame_path": resolved.frame_path,
            "atlas_path": resolved.atlas_path,
            "sheet_path": resolved.sheet_path,
            "atlas_padding": resolved.atlas_padding,
        },
        "clips": [
            _supplied_clip(clip.selected, resolved.clips.get(clip.selected.clip.name))
            for clip in request.clips
        ],
    }


def _stored_array(stored):
    if stored is None:
        return None
    return stored if isinstance(stored, str) else list(stored)


def _mirror_array(mirrors):
    if mirrors is None:
        return None
    return [
        {"target": target, "source": source}
        for target, source in sorted(mirrors.items())
    ]


def _supplied_clip(selected, own):
    """A selected clip as the settings record it: the values as supplied, a
    null for each that inherits."""
    own = exportsettings.ClipSettings() if own is None else own
    return {
        "name": selected.clip.name,
        "loop": not selected.one_shot,
        "frames": selected.frames,
        "fps": None if own.fps is None else float(own.fps),
        "stored_directions": _stored_array(own.stored_directions),
        "mirrors": _mirror_array(own.mirrors),
        "output_name": own.output_name,
    }


def build(
    *,
    generator,
    source,
    subject,
    settings,
    style,
    resolved,
    request,
    names,
    encoded,
    shade_range,
    previews=True,
    normals=True,
    depth=False,
    light=export.NO_LIGHT,
    ramp=export.DEFAULT_RAMP,
    shading=None,
):
    """The manifest document of an export, as a dict in serialized order.

    `generator` comes from `export.generator`, `source` is the capture
    `Source`, `subject` the subject's name, `settings`, `style`,
    `resolved`, `request`, `shade_range`, `previews`, `normals`, `depth`,
    `light`, `ramp` and `shading` as `settings_record` takes them, `names`
    the `outputs.Names` of the same request and `encoded` the
    `exportimages.Encoded` of its frames. Nothing is read or written.
    """
    record = settings_record(
        settings,
        resolved,
        request,
        style,
        shade_range=shade_range,
        previews=previews,
        normals=normals,
        depth=depth,
        light=light,
        ramp=ramp,
        shading=shading,
    )
    view = views.View(settings.directions, settings.start_angle, settings.model_yaw)
    width, height = settings.cell
    ground_x, ground_y = settings.ground_px
    return {
        "schema": SCHEMA,
        "generator": generator,
        "source": {"file": Path(source.path).name, "sha256": source.sha256},
        "subject": subject,
        "variant": sampling.VARIANT,
        "settings": record,
        "fingerprint": export.fingerprint(generator, record, source.sha256),
        "artifacts": [_artifact_record(artifact) for artifact in encoded.artifacts],
        "directions": [
            {
                "index": direction.index,
                "angle_deg": float(direction.angle),
                "label": direction.label,
                "output_name": names.directions[direction.index],
            }
            for direction in views.directions(view)
        ],
        "clips": [
            {
                "name": clip.selected.clip.name,
                "loop": not clip.selected.one_shot,
                "duration_s": float(clip.selected.clip.t1 - clip.selected.clip.t0),
                "frame_count": clip.sampling.frame_count,
                "frame_duration_s": float(clip.sampling.frame_duration),
                "time_scale": float(clip.sampling.time_scale),
                "output_name": names.clips[clip.selected.clip.name],
                "fps": float(clip.fps),
                "stored_directions": [d.index for d in clip.directions],
                "mirrors": [
                    {
                        "target": pair.target,
                        "source": pair.source,
                        "transform": FLIP_X,
                        "ground_px": {"x": width - ground_x, "y": ground_y},
                    }
                    for pair in clip.mirrors
                ],
            }
            for clip in request.clips
        ],
        "frames": [
            {
                "clip": sample.clip,
                "direction": sample.direction,
                "index": sample.index,
                "time_s": float(sample.time_s),
                "locations": [
                    {
                        "artifact": place.artifact,
                        "x": place.x,
                        "y": place.y,
                        "w": place.w,
                        "h": place.h,
                    }
                    for place in sample.locations
                ],
            }
            for sample in encoded.samples
        ],
    }


def _artifact_record(artifact):
    record = {
        "kind": artifact.kind,
        "channel": artifact.channel,
        "path": artifact.path,
        "width": artifact.width,
        "height": artifact.height,
    }
    if artifact.kind != SHEET:
        record["clip"] = artifact.clip
    if artifact.kind == FRAME_KIND:
        record["direction"] = artifact.direction
        record["index"] = artifact.index
    if artifact.kind != PREVIEW:
        record["padding"] = artifact.padding
        record["cell"] = {"width": artifact.cell[0], "height": artifact.cell[1]}
    return record


def serialize(document):
    """`document` as the manifest's bytes: two-space indentation, UTF-8 with
    non-ASCII kept, and one trailing newline."""
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def encode(**options):
    """The manifest bytes of an export: `build`'s keyword arguments.

    The bytes are read back by `decode` before they are returned, so a
    manifest the reader would refuse is an internal `ValueError`, never a
    file.
    """
    data = serialize(build(**options))
    try:
        decode(data, "the manifest")
    except UsageError as error:
        raise ValueError(f"the manifest written is invalid: {error}") from None
    return data


# Reading


@dataclass(frozen=True)
class Manifest:
    """A manifest read and checked. `label` names it in errors; `reused` is
    the `cli.ReusedSettings` of the settings that existed before the export
    arc; `layer` is every export setting, with the global `fps` and
    `frames`, in the form `exportsettings.resolve` takes; `document` is the
    checked document."""

    label: str
    reused: cli.ReusedSettings
    layer: Mapping
    document: Mapping

    def source(self):
        """The `exportsettings.Source` of a reused layer."""
        return exportsettings.Source(exportsettings.REUSED, self.label, self.layer)


def read(path):
    """The `Manifest` in the file at `path`. Reading that file is the only
    effect; raises `usage.UsageError` naming it and the problem."""
    path = Path(path)
    label = f"manifest {str(path)!r}"
    try:
        data = path.read_bytes()
    except OSError as error:
        raise UsageError(
            f"{label}: cannot be read: {error.strerror or error}"
        ) from None
    return decode(data, label)


def decode(data, label="the manifest"):
    """The `Manifest` the bytes `data` make, or a `usage.UsageError` naming
    `label` and the field and problem.

    Everything is checked: the JSON, then every member and its type, the
    settings as a settings file's values are, the inline style, and last
    the records that the recorded settings imply (design P-8, part 4, and
    the review's derived-record rules): the fingerprint, the directions,
    the clips, the artifacts and the frames with their locations. No file is
    opened, nothing is written and no process is started.
    """
    document = _parse(data, label)
    problems = _Problems(label)
    if not _members(problems, document, DOCUMENT, ""):
        problems.raise_all()
    checked = _structure(problems, document)
    problems.raise_all()
    _derive(label, document, checked)
    return Manifest(
        label, cli.reused_from(checked), _layer(checked), MappingProxyType(document)
    )


class _Problems:
    """The problems found so far, each already naming its field."""

    def __init__(self, label):
        self.label = label
        self.items = []

    def add(self, where, text):
        self.items.append(f"{where}: {text}" if where else text)

    def raise_all(self):
        if not self.items:
            return
        shown = self.items[:MAX_PROBLEMS]
        if len(self.items) > MAX_PROBLEMS:
            shown.append(f"and {len(self.items) - MAX_PROBLEMS} more")
        raise UsageError(f"{self.label}: " + "; ".join(shown))


def _fail(label, where, text):
    raise UsageError(f"{label}: {where}: {text}")


def _parse(data, label):
    try:
        document = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=cli._unique_keys,
            parse_constant=cli._no_constant,
        )
    except UnicodeDecodeError as error:
        raise UsageError(
            f"{label}: is not UTF-8: {error.reason} at byte {error.start}"
        ) from None
    except cli._DuplicateKey as error:
        raise UsageError(f"{label}: {error}") from None
    except ValueError as error:
        raise UsageError(f"{label}: is not valid JSON: {error}") from None
    except RecursionError:
        raise UsageError(
            f"{label}: is not valid JSON: it is nested too deeply"
        ) from None
    not_a_manifest = f"is not a {SCHEMA} document"
    if not isinstance(document, dict):
        raise UsageError(f"{label}: {not_a_manifest}: not a JSON object")
    if "schema" not in document:
        raise UsageError(f"{label}: {not_a_manifest}: schema is missing")
    schema = document["schema"]
    if schema == SCHEMA:
        return document
    if isinstance(schema, str) and schema.startswith(SHEET_PREFIX):
        raise UsageError(
            f"{label}: is a {schema} sheet, which no longer loads; only {SCHEMA} "
            "manifests do, so generate it again from the model or project"
        )
    raise UsageError(f"{label}: {not_a_manifest}: schema is {cli._shown(schema)}")


# Types


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    """A finite JSON number, never a boolean."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _members(problems, value, names, where):
    """Whether `value` is an object with exactly the members `names`; each
    absent or unknown one is a problem."""
    if not isinstance(value, dict):
        problems.add(where, f"expected an object, got {cli._shown(value)}")
        return False
    prefix = f"{where}." if where else ""
    ok = True
    for name in names:
        if name not in value:
            problems.add(f"{prefix}{name}", "missing")
            ok = False
    for name in value:
        if name not in names:
            problems.add(f"{prefix}{name}", "unknown member")
            ok = False
    return ok


def _field(problems, value, where, test, wanted):
    ok = test(value)
    if not ok:
        problems.add(where, f"expected {wanted}, got {cli._shown(value)}")
    return ok


def _text(problems, value, where):
    return _field(
        problems,
        value,
        where,
        lambda v: isinstance(v, str) and bool(v),
        "a nonempty string",
    )


def _whole(problems, value, where, low=0):
    return _field(
        problems,
        value,
        where,
        lambda v: _is_int(v) and v >= low,
        "a whole number" if low == 0 else f"a whole number {low} or more",
    )


def _number(problems, value, where, low=None, strict=False):
    def test(v):
        if not _is_number(v):
            return False
        if low is None:
            return True
        return v > low if strict else v >= low

    wanted = "a finite number"
    if low is not None:
        wanted += f" {'greater than' if strict else 'at least'} {low}"
    return _field(problems, value, where, test, wanted)


# The settings' shape


def _recorded(key, *, clip=False):
    """A settings member checked as the setting `key` is checked."""

    def check(value):
        try:
            return layered.check_recorded(key, value, clip=clip)
        except ValueError as error:
            raise argparse.ArgumentTypeError(str(error)) from None

    return check


def _entries(value, keys, what):
    """The mapping an array of `{keys[0], keys[1]}` entries encodes: the
    first member whole and strictly increasing, which makes duplicates and a
    wrong order each their own problem."""
    if not isinstance(value, list):
        raise argparse.ArgumentTypeError(
            f"expected an array of {what}, got {cli._shown(value)}"
        )
    pairs = {}
    last = None
    for position, entry in enumerate(value):
        if not isinstance(entry, dict) or set(entry) != set(keys):
            raise argparse.ArgumentTypeError(
                f"[{position}]: expected exactly {', '.join(keys)}, "
                f"got {cli._shown(entry)}"
            )
        key = entry[keys[0]]
        if not _is_int(key):
            raise argparse.ArgumentTypeError(
                f"[{position}].{keys[0]}: expected a whole number, got {cli._shown(key)}"
            )
        if key in pairs:
            raise argparse.ArgumentTypeError(
                f"[{position}].{keys[0]}: {key} is listed twice"
            )
        if last is not None and key < last:
            raise argparse.ArgumentTypeError(
                f"[{position}].{keys[0]}: {key} follows {last}; the entries must "
                f"be sorted by {keys[0]}"
            )
        pairs[key] = entry[keys[1]]
        last = key
    return pairs


def _names(value):
    return _recorded("direction_names")(_entries(value, ("index", "name"), "names"))


def _mirrors(value):
    return _recorded("mirrors")(_entries(value, ("target", "source"), "mirrors"))


def _formats(value):
    formats = _recorded("export.formats")(value)
    if list(formats) != value:
        raise argparse.ArgumentTypeError(
            "expected the formats in the order sheet, frames, atlases, got "
            f"{cli._shown(value)}"
        )
    return formats


def _clip_entries(value):
    """The recorded clips of the settings, converted, each exactly the
    members of `SETTINGS_CLIP`."""
    if not isinstance(value, list) or not value:
        raise argparse.ArgumentTypeError(
            f"expected a nonempty list of clips, got {cli._shown(value)}"
        )
    names = set()
    clips = []
    for position, entry in enumerate(value):
        if not isinstance(entry, dict) or set(entry) != set(SETTINGS_CLIP):
            raise argparse.ArgumentTypeError(
                f"[{position}]: expected exactly {', '.join(SETTINGS_CLIP)}, "
                f"got {cli._shown(entry)}"
            )

        def leaf(name, convert, position=position, entry=entry):
            try:
                return convert(entry[name])
            except (ValueError, argparse.ArgumentTypeError) as error:
                raise argparse.ArgumentTypeError(
                    f"[{position}].{name}: {error}"
                ) from None

        name = entry["name"]
        if not isinstance(name, str) or not name:
            raise argparse.ArgumentTypeError(
                f"[{position}].name: expected a nonempty clip name, got {cli._shown(name)}"
            )
        if name in names:
            raise argparse.ArgumentTypeError(
                f"[{position}].name: the clip {cli._shown(name)} is recorded twice"
            )
        names.add(name)
        if not isinstance(entry["loop"], bool):
            raise argparse.ArgumentTypeError(
                f"[{position}].loop: expected true or false, got "
                f"{cli._shown(entry['loop'])}"
            )
        mirrors = entry["mirrors"]
        clips.append(
            {
                "name": name,
                "loop": entry["loop"],
                "frames": leaf("frames", _clip_leaf("frames")),
                "fps": leaf("fps", _clip_leaf("fps")),
                "stored_directions": leaf(
                    "stored_directions", _clip_leaf("stored_directions")
                ),
                "mirrors": None
                if mirrors is None
                else leaf(
                    "mirrors",
                    lambda v: _clip_leaf("mirrors")(
                        _entries(v, ("target", "source"), "mirrors")
                    ),
                ),
                "output_name": leaf("output_name", _clip_leaf("output_name")),
            }
        )
    return clips


def _clip_leaf(key):
    def check(value):
        return layered.check_recorded(key, value, clip=True)

    return check


_SHAPE = {
    **{name: shape for name, shape in cli._SETTINGS.items() if name != "clips"},
    "stored_directions": _recorded("stored_directions"),
    "direction_names": _names,
    "mirrors": _mirrors,
    "export": {
        "formats": _formats,
        "frame_path": _recorded("export.frame_path"),
        "atlas_path": _recorded("export.atlas_path"),
        "sheet_path": _recorded("export.sheet_path"),
        "atlas_padding": _recorded("export.atlas_padding"),
    },
    "clips": _clip_entries,
}


def _layer(checked):
    """The checked settings as the layer `exportsettings.resolve` reads."""
    layer = layered.Layer(
        {
            "fps": checked["fps"],
            "frames": checked["frames"],
            "stored_directions": checked["stored_directions"],
            "direction_names": checked["direction_names"],
            "mirrors": checked["mirrors"],
            "export.formats": checked["export"]["formats"],
            "export.frame_path": checked["export"]["frame_path"],
            "export.atlas_path": checked["export"]["atlas_path"],
            "export.sheet_path": checked["export"]["sheet_path"],
            "export.atlas_padding": checked["export"]["atlas_padding"],
        }
    )
    layer["clips"] = {
        entry["name"]: {
            leaf: entry[leaf]
            for leaf in ("frames", "fps", "stored_directions", "mirrors", "output_name")
        }
        for entry in checked["clips"]
    }
    return layer


# The document's structure


def _structure(problems, document):
    """Check every member and type of `document`, returning the checked
    settings; the problems are added to `problems`."""
    _generator(problems, document["generator"])
    _source(problems, document["source"])
    _text(problems, document["subject"], "subject")
    if document["variant"] != sampling.VARIANT:
        problems.add(
            "variant",
            f"expected {sampling.VARIANT!r}, got {cli._shown(document['variant'])}",
        )
    _field(
        problems,
        document["fingerprint"],
        "fingerprint",
        lambda v: isinstance(v, str) and _FINGERPRINT.fullmatch(v) is not None,
        "sha256: and 64 lowercase hexadecimal digits",
    )
    raw = document["settings"]
    settings_problems = []
    checked = cli._check_shape(_SHAPE, raw, "settings", settings_problems)
    if not settings_problems:
        checked["style"] = cli._style(checked["style"], settings_problems)
    problems.items.extend(settings_problems)
    _artifacts(problems, document["artifacts"])
    _directions(problems, document["directions"])
    _clips(problems, document["clips"])
    _frames(problems, document["frames"])
    return checked


def _generator(problems, generator):
    if not _members(problems, generator, GENERATOR, "generator"):
        return
    for name in GENERATOR[:7]:
        _text(problems, generator[name], f"generator.{name}")
    for name, fields in (
        ("color", backend.COLOR_FIELDS),
        ("shade", backend.SHADE_FIELDS),
    ):
        where = f"generator.{name}"
        record = generator[name]
        if not _members(problems, record, tuple(fields), where):
            continue
        for key, kind in fields.items():
            value = record[key]
            if kind == "name":
                _text(problems, value, f"{where}.{key}")
            elif kind == "count":
                _whole(problems, value, f"{where}.{key}", 1)
            elif kind == "index":
                _whole(problems, value, f"{where}.{key}")
            elif kind == "positive":
                _number(problems, value, f"{where}.{key}", 0, strict=True)
            else:
                _number(problems, value, f"{where}.{key}")


def _source(problems, source):
    if not _members(problems, source, SOURCE, "source"):
        return
    _field(
        problems,
        source["file"],
        "source.file",
        lambda v: isinstance(v, str) and bool(v) and "/" not in v and "\\" not in v,
        "a nonempty base filename",
    )
    _field(
        problems,
        source["sha256"],
        "source.sha256",
        lambda v: isinstance(v, str) and _SHA256.fullmatch(v) is not None,
        "64 lowercase hexadecimal digits",
    )


def _artifact_members(kind):
    members = list(ARTIFACT)
    if kind != SHEET:
        members.append("clip")
    if kind == FRAME_KIND:
        members += ["direction", "index"]
    if kind != PREVIEW:
        members += ["padding", "cell"]
    return tuple(members)


def _artifacts(problems, artifacts):
    if not isinstance(artifacts, list):
        problems.add("artifacts", f"expected an array, got {cli._shown(artifacts)}")
        return
    for position, artifact in enumerate(artifacts):
        where = f"artifacts[{position}]"
        if not isinstance(artifact, dict):
            problems.add(where, f"expected an object, got {cli._shown(artifact)}")
            continue
        kind = artifact.get("kind")
        if not isinstance(kind, str) or kind not in CHANNELS:
            problems.add(
                f"{where}.kind",
                f"expected sheet, atlas, frame or preview, got {cli._shown(kind)}",
            )
            continue
        if not _members(problems, artifact, _artifact_members(kind), where):
            continue
        channels = CHANNELS[kind]
        _field(
            problems,
            artifact["channel"],
            f"{where}.channel",
            lambda v, channels=channels: isinstance(v, str) and v in channels,
            f"one of {', '.join(channels)}",
        )
        _field(
            problems,
            artifact["path"],
            f"{where}.path",
            lambda v: isinstance(v, str) and _path_problem(v) is None,
            "a nonempty relative path of / separated components, none empty, . or ..",
        )
        _whole(problems, artifact["width"], f"{where}.width", 1)
        _whole(problems, artifact["height"], f"{where}.height", 1)
        if kind != SHEET:
            _text(problems, artifact["clip"], f"{where}.clip")
        if kind == FRAME_KIND:
            _whole(problems, artifact["direction"], f"{where}.direction")
            _whole(problems, artifact["index"], f"{where}.index")
        if kind != PREVIEW:
            _whole(problems, artifact["padding"], f"{where}.padding")
            cell = artifact["cell"]
            if _members(problems, cell, ("width", "height"), f"{where}.cell"):
                _whole(problems, cell["width"], f"{where}.cell.width", 1)
                _whole(problems, cell["height"], f"{where}.cell.height", 1)
    seen = {}
    for position, artifact in enumerate(artifacts):
        path = artifact.get("path") if isinstance(artifact, dict) else None
        if isinstance(path, str):
            if path in seen:
                problems.add(
                    f"artifacts[{position}].path",
                    f"{path!r} is also the path of artifacts[{seen[path]}]",
                )
            seen.setdefault(path, position)


def _path_problem(path):
    """Why `path` is not a relative `/` path, or None. Only this: a
    manifest records whichever form wrote it, so the directory-mode name
    rules (devices, backslashes, case) are not applied."""
    if path.startswith("/"):
        return "it starts with /"
    for component in path.split("/"):
        if component in ("", ".", ".."):
            return f"it has the component {component!r}"
    return None


def _directions(problems, directions):
    if not isinstance(directions, list) or not directions:
        problems.add(
            "directions", f"expected a nonempty array, got {cli._shown(directions)}"
        )
        return
    for position, entry in enumerate(directions):
        where = f"directions[{position}]"
        if not _members(problems, entry, DIRECTION, where):
            continue
        _whole(problems, entry["index"], f"{where}.index")
        _number(problems, entry["angle_deg"], f"{where}.angle_deg")
        if entry["label"] is not None:
            _text(problems, entry["label"], f"{where}.label")
        if not isinstance(entry["output_name"], str):
            problems.add(
                f"{where}.output_name",
                f"expected a string, got {cli._shown(entry['output_name'])}",
            )


def _mirror_record(problems, entry, where):
    if not _members(problems, entry, MIRROR, where):
        return
    _whole(problems, entry["target"], f"{where}.target")
    _whole(problems, entry["source"], f"{where}.source")
    if entry["transform"] != FLIP_X:
        problems.add(
            f"{where}.transform",
            f"expected {FLIP_X!r}, got {cli._shown(entry['transform'])}",
        )
    ground = entry["ground_px"]
    if _members(problems, ground, ("x", "y"), f"{where}.ground_px"):
        _whole(problems, ground["x"], f"{where}.ground_px.x")
        _whole(problems, ground["y"], f"{where}.ground_px.y")


def _clips(problems, clips):
    if not isinstance(clips, list) or not clips:
        problems.add("clips", f"expected a nonempty array, got {cli._shown(clips)}")
        return
    for position, entry in enumerate(clips):
        where = f"clips[{position}]"
        if not _members(problems, entry, CLIP, where):
            continue
        _text(problems, entry["name"], f"{where}.name")
        if not isinstance(entry["loop"], bool):
            problems.add(
                f"{where}.loop",
                f"expected true or false, got {cli._shown(entry['loop'])}",
            )
        _number(problems, entry["duration_s"], f"{where}.duration_s", 0)
        _whole(problems, entry["frame_count"], f"{where}.frame_count", 1)
        _number(problems, entry["frame_duration_s"], f"{where}.frame_duration_s")
        _number(problems, entry["time_scale"], f"{where}.time_scale")
        if not isinstance(entry["output_name"], str):
            problems.add(
                f"{where}.output_name",
                f"expected a string, got {cli._shown(entry['output_name'])}",
            )
        _number(problems, entry["fps"], f"{where}.fps", 0, strict=True)
        stored = entry["stored_directions"]
        if not isinstance(stored, list) or not stored:
            problems.add(
                f"{where}.stored_directions",
                f"expected a nonempty array, got {cli._shown(stored)}",
            )
        else:
            for index, direction in enumerate(stored):
                _whole(problems, direction, f"{where}.stored_directions[{index}]")
        mirrors = entry["mirrors"]
        if not isinstance(mirrors, list):
            problems.add(
                f"{where}.mirrors", f"expected an array, got {cli._shown(mirrors)}"
            )
        else:
            for index, mirror in enumerate(mirrors):
                _mirror_record(problems, mirror, f"{where}.mirrors[{index}]")


def _frames(problems, frames):
    if not isinstance(frames, list):
        problems.add("frames", f"expected an array, got {cli._shown(frames)}")
        return
    for position, entry in enumerate(frames):
        where = f"frames[{position}]"
        if not _members(problems, entry, FRAME, where):
            continue
        _text(problems, entry["clip"], f"{where}.clip")
        _whole(problems, entry["direction"], f"{where}.direction")
        _whole(problems, entry["index"], f"{where}.index")
        _number(problems, entry["time_s"], f"{where}.time_s")
        locations = entry["locations"]
        if not isinstance(locations, list):
            problems.add(
                f"{where}.locations", f"expected an array, got {cli._shown(locations)}"
            )
            continue
        for index, place in enumerate(locations):
            here = f"{where}.locations[{index}]"
            if not _members(problems, place, LOCATION, here):
                continue
            _whole(problems, place["artifact"], f"{here}.artifact")
            _whole(problems, place["x"], f"{here}.x")
            _whole(problems, place["y"], f"{here}.y")
            _whole(problems, place["w"], f"{here}.w", 1)
            _whole(problems, place["h"], f"{here}.h", 1)


# The records the settings imply


def _same(actual, expected):
    """The path inside `actual` of the first difference from `expected`, as
    `(path, expected, actual)`, or None. Numbers compare by value, but never
    a boolean with a number."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return "", expected, actual
        for key, want in expected.items():
            if key not in actual:
                return f".{key}", want, None
            found = _same(actual[key], want)
            if found is not None:
                path, wanted, got = found
                return f".{key}{path}", wanted, got
        return None
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return "", expected, actual
        for position, want in enumerate(expected):
            if position >= len(actual):
                return f"[{position}]", want, None
            found = _same(actual[position], want)
            if found is not None:
                path, wanted, got = found
                return f"[{position}]{path}", wanted, got
        if len(actual) > len(expected):
            return f"[{len(expected)}]", None, actual[len(expected)]
        return None
    if isinstance(expected, bool) or isinstance(actual, bool):
        return None if actual is expected else ("", expected, actual)
    return None if actual == expected else ("", expected, actual)


def _expect(label, where, actual, expected, why):
    found = _same(actual, expected)
    if found is not None:
        path, want, got = found
        _fail(label, f"{where}{path}", f"expected {want!r}, got {got!r}; {why}")


def _derive(label, document, checked):
    """Refuse a document whose own records disagree with what its recorded
    settings imply."""
    raw = document["settings"]
    expected = export.fingerprint(
        document["generator"], raw, document["source"]["sha256"]
    )
    if document["fingerprint"] != expected:
        _fail(
            label,
            "fingerprint",
            f"is {document['fingerprint']}, but the generator, the source digest "
            f"and the settings hash to {expected}",
        )
    entries = checked["clips"]
    records = document["clips"]
    if len(records) != len(entries):
        _fail(
            label,
            "clips",
            f"has {len(records)} clips, but settings.clips selects {len(entries)}",
        )
    for position, (entry, record) in enumerate(zip(entries, records, strict=True)):
        for member, want in (("name", entry["name"]), ("loop", entry["loop"])):
            if record[member] != want:
                _fail(
                    label,
                    f"clips[{position}].{member}",
                    f"expected {want!r}, got {record[member]!r}; settings.clips"
                    f"[{position}] says so",
                )
    view = views.View(
        checked["view"]["directions"],
        checked["view"]["start_angle_deg"],
        checked["model_yaw_deg"],
    )
    try:
        ring = views.directions(view)
    except ValueError as error:
        _fail(label, "settings.view", str(error))
    selected = tuple(
        SelectedClip(
            Clip(position, entry["name"], 0.0, float(record["duration_s"]), ()),
            not entry["loop"],
            entry["frames"],
        )
        for position, (entry, record) in enumerate(zip(entries, records, strict=True))
    )
    resolved = exportsettings.resolve(
        [exportsettings.Source(exportsettings.REUSED, label, _layer(checked))]
    )
    _check_budget(label, document, resolved, selected)
    try:
        request = exportsettings.request(
            resolved, document["subject"], selected, view
        ).plan
    except UsageError as error:
        _fail(label, "settings", str(error))
    names = outputs.resolve_names(
        selected,
        view,
        subject=document["subject"],
        clip_aliases={name: own.output_name for name, own in resolved.clips.items()},
        direction_aliases=dict(resolved.direction_names),
        directory=False,
    )
    _expect(
        label,
        "directions",
        document["directions"],
        [
            {
                "index": direction.index,
                "angle_deg": float(direction.angle),
                "label": direction.label,
                "output_name": names.directions[direction.index],
            }
            for direction in ring
        ],
        "the recorded view and names imply the whole ring",
    )
    width, height = checked["cell"]["width"], checked["cell"]["height"]
    ground = checked["ground_px"]
    _expect(
        label,
        "clips",
        document["clips"],
        [
            {
                "name": clip.selected.clip.name,
                "loop": not clip.selected.one_shot,
                "duration_s": float(clip.selected.clip.t1),
                "frame_count": clip.sampling.frame_count,
                "frame_duration_s": float(clip.sampling.frame_duration),
                "time_scale": float(clip.sampling.time_scale),
                "output_name": names.clips[clip.selected.clip.name],
                "fps": float(clip.fps),
                "stored_directions": [d.index for d in clip.directions],
                "mirrors": [
                    {
                        "target": pair.target,
                        "source": pair.source,
                        "transform": FLIP_X,
                        "ground_px": {"x": width - ground["x"], "y": ground["y"]},
                    }
                    for pair in clip.mirrors
                ],
            }
            for clip in request.clips
        ],
        "the recorded settings resolve to this",
    )
    padding = checked["export"]["atlas_padding"]
    expected = _expected_artifacts(checked, request, (width, height), padding)
    _check_artifacts(label, document["artifacts"], expected)
    _check_frames(label, document, request, expected, (width, height), padding)


def _check_budget(label, document, resolved, selected):
    """Refuse a clip whose settings would sample far more frames than the
    document records, before any plan is built from it."""
    limit = len(document["frames"])
    for position, chosen in enumerate(selected):
        own = resolved.clips.get(chosen.clip.name)
        fps = resolved.fps if own is None or own.fps is None else own.fps
        count = resolved.frames if chosen.frames is None else chosen.frames
        duration = chosen.clip.t1 - chosen.clip.t0
        if count == sampling.AUTO:
            wanted = duration * fps
            too_many = wanted > limit + 1
        else:
            wanted = count
            too_many = count > limit
        if too_many:
            _fail(
                label,
                f"clips[{position}].frame_count",
                f"the settings sample about {wanted:g} frames, but the document "
                f"records only {limit}",
            )


def _expected_artifacts(checked, request, cell, padding):
    """The artifacts the recorded settings imply, in order, each without its
    path."""
    width, height = cell
    channels = [COLOR] + [NORMAL] * checked["normals"] + [DEPTH] * checked["depth"]
    formats = checked["export"]["formats"]
    previews = checked["previews"]
    lit = previews and checked["light"]["position"] is not None
    expected = []

    def png(kind, channel, w, h, **identity):
        record = {"kind": kind, "channel": channel, "width": w, "height": h}
        record.update(identity)
        record["padding"] = padding if kind == ATLAS else 0
        record["cell"] = {"width": width, "height": height}
        expected.append(record)

    if "sheet" in formats:
        columns = max(clip.sampling.frame_count for clip in request.clips)
        rows = sum(len(clip.directions) for clip in request.clips)
        for channel in channels:
            png(SHEET, channel, columns * width, rows * height)
    if "atlases" in formats:
        slot_w, slot_h = width + 2 * padding, height + 2 * padding
        for clip in request.clips:
            for channel in channels:
                png(
                    ATLAS,
                    channel,
                    clip.sampling.frame_count * slot_w,
                    len(clip.directions) * slot_h,
                    clip=clip.selected.clip.name,
                )
    if "frames" in formats:
        for clip in request.clips:
            for frame in clip.frames:
                for channel in channels:
                    png(
                        FRAME_KIND,
                        channel,
                        width,
                        height,
                        clip=clip.selected.clip.name,
                        direction=frame.address.direction,
                        index=frame.index,
                    )
    for clip in request.clips:
        for channel in [FLAT] * previews + [LIT] * lit:
            expected.append(
                {
                    "kind": PREVIEW,
                    "channel": channel,
                    "width": len(clip.directions) * width * export.PREVIEW_SCALE,
                    "height": height * export.PREVIEW_SCALE,
                    "clip": clip.selected.clip.name,
                }
            )
    return expected


def _check_artifacts(label, artifacts, expected):
    if len(artifacts) != len(expected):
        _fail(
            label,
            "artifacts",
            f"has {len(artifacts)} entries, but the recorded formats, maps, "
            f"previews and clips imply {len(expected)}",
        )
    for position, (actual, want) in enumerate(zip(artifacts, expected, strict=True)):
        _expect(
            label,
            f"artifacts[{position}]",
            actual,
            want,
            "the recorded settings imply this artifact in this order",
        )


def _check_frames(label, document, request, artifacts, cell, padding):
    """Check the frame records and their locations against the plan and the
    layouts of the artifacts."""
    width, height = cell
    samples = [
        (clip.selected.clip.name, frame.address.direction, frame.index)
        for clip in request.clips
        for frame in clip.frames
    ]
    frames = document["frames"]
    if len(frames) != len(samples):
        _fail(
            label,
            "frames",
            f"has {len(frames)} records, but the clips and stored directions "
            f"imply {len(samples)}",
        )
    times = {}
    for position, (record, sample) in enumerate(zip(frames, samples, strict=True)):
        got = (record["clip"], record["direction"], record["index"])
        if got != sample:
            _fail(
                label,
                f"frames[{position}]",
                f"is clip {got[0]!r}, direction {got[1]}, sample {got[2]}, but "
                f"the clips and stored directions put clip {sample[0]!r}, "
                f"direction {sample[1]}, sample {sample[2]} here",
            )
        known = times.setdefault((record["clip"], record["index"]), record["time_s"])
        if known != record["time_s"]:
            _fail(
                label,
                f"frames[{position}].time_s",
                f"is {record['time_s']!r}, but sample {record['index']} of clip "
                f"{record['clip']!r} is at {known!r} in another direction",
            )
    wanted = _expected_locations(request, artifacts, (width, height), padding)
    recorded = document["artifacts"]
    for position, (record, sample) in enumerate(zip(frames, samples, strict=True)):
        where = f"frames[{position}].locations"
        last = -1
        for index, place in enumerate(record["locations"]):
            here = f"{where}[{index}]"
            number = place["artifact"]
            if number >= len(recorded):
                _fail(
                    label,
                    f"{here}.artifact",
                    f"{number} is not one of the {len(recorded)} artifacts",
                )
            artifact = recorded[number]
            if artifact["kind"] not in PNG_KINDS:
                _fail(
                    label,
                    f"{here}.artifact",
                    f"artifacts[{number}] is a preview, which holds no sample",
                )
            _check_identity(label, here, artifact, number, sample)
            if (place["w"], place["h"]) != (width, height):
                _fail(
                    label,
                    f"{here}",
                    f"is {place['w']}x{place['h']}, but the cell is {width}x{height}",
                )
            if (
                place["x"] + place["w"] > artifact["width"]
                or place["y"] + place["h"] > artifact["height"]
            ):
                _fail(
                    label,
                    here,
                    f"lies outside artifacts[{number}], which is "
                    f"{artifact['width']}x{artifact['height']}",
                )
            if artifact["kind"] == ATLAS and padding:
                slot_w, slot_h = width + 2 * padding, height + 2 * padding
                inside_x = padding <= place["x"] % slot_w <= slot_w - padding - width
                inside_y = padding <= place["y"] % slot_h <= slot_h - padding - height
                if not (inside_x and inside_y):
                    _fail(
                        label,
                        here,
                        f"points into the padding of atlas artifacts[{number}]",
                    )
            if number == last:
                _fail(label, f"{here}.artifact", f"artifacts[{number}] is listed twice")
            if number < last:
                _fail(
                    label,
                    f"{here}.artifact",
                    f"{number} follows {last}; locations are sorted by artifact",
                )
            last = number
        found = [
            (place["artifact"], place["x"], place["y"]) for place in record["locations"]
        ]
        want = wanted[sample]
        if [item[0] for item in found] != [item[0] for item in want]:
            have = {item[0] for item in found}
            missing = [item[0] for item in want if item[0] not in have]
            extra = [item[0] for item in found if item[0] not in {w[0] for w in want}]
            _fail(
                label,
                where,
                "does not hold exactly one location in each png artifact of the "
                f"sample; missing {missing}, unexpected {extra}",
            )
        for index, (got, need) in enumerate(zip(found, want, strict=True)):
            if got != need:
                _fail(
                    label,
                    f"{where}[{index}]",
                    f"is at ({got[1]}, {got[2]}) in artifacts[{got[0]}], but the "
                    f"layout puts the sample at ({need[1]}, {need[2]})",
                )


def _check_identity(label, here, artifact, number, sample):
    clip, direction, index = sample
    if artifact["kind"] != SHEET and artifact["clip"] != clip:
        _fail(
            label,
            f"{here}.artifact",
            f"artifacts[{number}] belongs to clip {artifact['clip']!r}, not {clip!r}",
        )
    if artifact["kind"] == FRAME_KIND and (
        artifact["direction"],
        artifact["index"],
    ) != (
        direction,
        index,
    ):
        _fail(
            label,
            f"{here}.artifact",
            f"artifacts[{number}] is direction {artifact['direction']}, sample "
            f"{artifact['index']}, not direction {direction}, sample {index}",
        )


def _expected_locations(request, artifacts, cell, padding):
    """Where each sample is, `{(clip, direction, index): [(artifact, x, y)]}`,
    each list in artifact order, as the layouts of `exportimages` place it."""
    width, height = cell
    slot_w, slot_h = width + 2 * padding, height + 2 * padding
    rows = {}
    first = 0
    for clip in request.clips:
        for row, direction in enumerate(clip.directions):
            rows[clip.selected.clip.name, direction.index] = (first + row, row)
        first += len(clip.directions)
    places = {}
    by_clip = {}
    for clip in request.clips:
        name = clip.selected.clip.name
        by_clip[name] = []
        for frame in clip.frames:
            key = (name, frame.address.direction, frame.index)
            places[key] = []
            by_clip[name].append(key)
    for number, artifact in enumerate(artifacts):
        kind = artifact["kind"]
        if kind == FRAME_KIND:
            key = (artifact["clip"], artifact["direction"], artifact["index"])
            places[key].append((number, 0, 0))
        elif kind == ATLAS:
            for clip, direction, index in by_clip[artifact["clip"]]:
                row = rows[clip, direction][1]
                places[clip, direction, index].append(
                    (number, index * slot_w + padding, row * slot_h + padding)
                )
        elif kind == SHEET:
            for key, found in places.items():
                clip, direction, index = key
                found.append((number, index * width, rows[clip, direction][0] * height))
    return places
