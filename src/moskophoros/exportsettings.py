"""The export settings resolved across layers, checked against the view, and
handed to the request planner (export design P-7, part 1; D-2, D-4, D-5).

`resolve` lays the layers, lowest first, as the command orders them (shipped
defaults, global file, reused settings, project file, explicit options) and
returns every value with where it came from. Global `stored_directions`,
`direction_names`, `mirrors` and `export.formats` replace whole; the other
`export` leaves merge one by one; clip entries merge by clip name and leaf,
so a clip's own `fps` leaves its lower-layer `frames` alone and an explicit
`null` clears a lower value. `request` then checks the resolved indices
against the actual view, naming the clip and the settings that contribute to
a clash, and builds the `plan.RequestPlan` with the typed per-clip overrides.

The command resolves through it with the layers it has: the internal defaults
and its own `fps` and frame counts. The other settings it reads are inactive
for every settings file (`settings`) and for a loaded manifest
(`cli.read_settings`), so they stay at their defaults. Everything here is
pure.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from moskophoros import plan, settings, views
from moskophoros.usage import UsageError

# Where a layer comes from, lowest first; the kinds the warnings tell apart.
DEFAULTS, GLOBAL, REUSED, PROJECT, OPTION = (
    "defaults",
    "global",
    "reused",
    "project",
    "option",
)
KINDS = (DEFAULTS, GLOBAL, REUSED, PROJECT, OPTION)
SHIPPED = "the shipped default"

# The global settings resolved here, with the sampling pair the planner
# needs beside them.
GLOBAL_KEYS = (
    "fps",
    "frames",
    "stored_directions",
    "direction_names",
    "mirrors",
    "export.formats",
    "export.frame_path",
    "export.atlas_path",
    "export.sheet_path",
    "export.atlas_padding",
)
CLIP_LEAVES = ("frames", "fps", "stored_directions", "mirrors", "output_name")


@dataclass(frozen=True)
class Source:
    """One layer: its `kind` (one of `KINDS`), its `label` for errors, and
    its `layer`, a `settings.Layer` or any mapping of the same names."""

    kind: str
    label: str
    layer: Mapping


@dataclass(frozen=True)
class ClipSettings:
    """A clip's own resolved leaves; None inherits the global value (or, for
    `output_name`, the cleaned source name). `origins` says where each leaf
    that some layer gives, a null included, came from."""

    frames: object = None
    fps: float | None = None
    stored_directions: object = None
    mirrors: Mapping[int, int] | None = None
    output_name: str | None = None
    origins: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class ExportSettings:
    """The resolved values. `origins` maps each global setting to where it
    came from, `fps_kind` is the kind of the layer that gave the global
    `fps`, and `clips` maps source clip names to their leaves, for every
    clip a layer names, selected or not."""

    fps: float
    frames: object
    stored_directions: object
    direction_names: Mapping[int, str]
    mirrors: Mapping[int, int]
    formats: tuple[str, ...]
    frame_path: str
    atlas_path: str
    sheet_path: str
    atlas_padding: int
    clips: Mapping[str, ClipSettings]
    origins: Mapping[str, str]
    fps_kind: str


def _where(source, key):
    where = getattr(source.layer, "where", {}).get(key)
    if where is None:
        return source.label
    return f"{source.label} line {where[0]}, column {where[1]}"


def resolve(sources):
    """The `ExportSettings` that the `sources` (`Source`s, lowest first) give;
    a setting no layer gives takes its internal default."""
    sources = tuple(sources)
    for source in sources:
        if source.kind not in KINDS:
            raise ValueError(f"not a layer kind: {source.kind!r}")
    values, origins, kinds = {}, {}, {}
    for key in GLOBAL_KEYS:
        for source in reversed(sources):
            if key in source.layer:
                values[key] = source.layer[key]
                origins[key] = _where(source, key)
                kinds[key] = source.kind
                break
        else:
            values[key] = settings.ALL_DEFAULTS[key]
            origins[key] = SHIPPED
            kinds[key] = DEFAULTS
    merged = settings.merge_clips(*(s.layer.get("clips", {}) for s in sources))
    clips = {}
    for name, leaves in merged.items():
        clip_origins = {}
        for leaf in leaves:
            for source in reversed(sources):
                if leaf in source.layer.get("clips", {}).get(name, {}):
                    clip_origins[leaf] = _where(source, ("clips", name, leaf))
                    break
        clips[name] = ClipSettings(
            **{leaf: leaves.get(leaf) for leaf in CLIP_LEAVES},
            origins=MappingProxyType(clip_origins),
        )
    return ExportSettings(
        fps=values["fps"],
        frames=values["frames"],
        stored_directions=values["stored_directions"],
        direction_names=values["direction_names"],
        mirrors=values["mirrors"],
        formats=values["export.formats"],
        frame_path=values["export.frame_path"],
        atlas_path=values["export.atlas_path"],
        sheet_path=values["export.sheet_path"],
        atlas_padding=values["export.atlas_padding"],
        clips=MappingProxyType(clips),
        origins=MappingProxyType(origins),
        fps_kind=kinds["fps"],
    )


@dataclass(frozen=True)
class Request:
    """The selected clips with their resolved frame counts, and the plan of
    their frames."""

    selected: tuple
    plan: plan.RequestPlan


def request(resolved, subject, selected_clips, view):
    """Check `resolved` against `view` and plan `selected_clips` of `subject`.

    Each global and each selected clip's direction and mirror index must be
    one of the view's directions, every direction-name key too, and in each
    selected clip's effective values every mirror source must be stored and
    every target omitted. A clash raises `UsageError` naming the clip and
    each setting that contributes to it, with where it came from. Entries for
    clips that are not selected are unused. The planner then gets the typed
    per-clip overrides and keeps its own timing, precedence and addresses.
    """
    count = len(views.directions(view))

    def out_of_view(indices, label, origin):
        for index in indices:
            if index >= count:
                raise UsageError(
                    f"{label} ({origin}): the direction {index} is not one of the "
                    f"view's {count} directions"
                )

    out_of_view(
        resolved.direction_names, "direction_names", resolved.origins["direction_names"]
    )
    out_of_view(
        _stored_indices(resolved.stored_directions, count),
        "stored_directions",
        resolved.origins["stored_directions"],
    )
    out_of_view(
        _mirror_indices(resolved.mirrors), "mirrors", resolved.origins["mirrors"]
    )
    selected = []
    overrides = {}
    for item in selected_clips:
        name = item.clip.name
        own = resolved.clips.get(name, ClipSettings())
        selected.append(replace(item, frames=own.frames))
        where = f"clip {name!r}"
        if own.stored_directions is None:
            stored_label = "stored_directions"
            stored_origin = resolved.origins["stored_directions"]
            stored = resolved.stored_directions
        else:
            stored_label = f"clips.{name}.stored_directions"
            stored_origin = own.origins["stored_directions"]
            stored = own.stored_directions
            out_of_view(
                _stored_indices(stored, count), f"{where} {stored_label}", stored_origin
            )
        if own.mirrors is None:
            mirror_label = "mirrors"
            mirror_origin = resolved.origins["mirrors"]
            mirrors = resolved.mirrors
        else:
            mirror_label = f"clips.{name}.mirrors"
            mirror_origin = own.origins["mirrors"]
            mirrors = own.mirrors
            out_of_view(
                _mirror_indices(mirrors), f"{where} {mirror_label}", mirror_origin
            )
        kept = set(_stored_indices(stored, count))
        for target, source in sorted(mirrors.items()):
            contributors = (
                f"{stored_label} ({stored_origin}) and {mirror_label} ({mirror_origin})"
            )
            if source not in kept:
                raise UsageError(
                    f"{where}: mirror {target} <- {source} takes its picture from "
                    f"direction {source}, which is not stored; see {contributors}"
                )
            if target in kept:
                raise UsageError(
                    f"{where}: mirror {target} <- {source} replaces direction "
                    f"{target}, which is stored, not omitted; see {contributors}"
                )
        if (
            own.fps is not None
            or own.stored_directions is not None
            or own.mirrors is not None
        ):
            overrides[name] = plan.ClipOverride(
                own.fps, own.stored_directions, own.mirrors
            )
    try:
        result = plan.plan(
            subject,
            selected,
            view,
            resolved.fps,
            resolved.frames,
            resolved.stored_directions,
            resolved.mirrors,
            overrides,
        )
    except ValueError as error:
        raise UsageError(str(error)) from None
    return Request(tuple(selected), result)


def _stored_indices(stored, count):
    return range(count) if stored == plan.ALL else stored


def _mirror_indices(mirrors):
    return [index for pair in mirrors.items() for index in pair]
