"""Output names and the relative output-path plan (export design P-7, parts
2 and 3).

`resolve_names` gives each selected clip and each direction of the view its
output name. `plan_outputs` lists every file a run writes, as relative paths
in the order the export fixes, and refuses the plan when two of its paths
could meet. A request is the `plan.RequestPlan` that `exportsettings` builds.

This is internal preparation: nothing here reads or writes a file, and the
command does not call it yet. A path is a string of `/`-separated components,
relative to an output directory, or in the positional form a bare file name
beside the PNG. Actual roots, existing files and symbolic links are the
publisher's business. Everything here is pure.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from moskophoros import export, sampling, templates, views
from moskophoros.usage import UsageError

# The kinds and channels of an output, as the manifest names them.
SHEET, ATLAS, FRAME, PREVIEW, MANIFEST = (
    "sheet",
    "atlas",
    "frame",
    "preview",
    "manifest",
)
COLOR, NORMAL, DEPTH, FLAT, LIT = "color", "normal", "depth", "flat", "lit"
MANIFEST_PATH = "manifest.json"
# What `{map}` expands to for each image channel.
MAP_SUFFIXES = ((COLOR, ""), (NORMAL, ".normal"), (DEPTH, ".depth"))

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_ALIAS = re.compile(r"[A-Za-z0-9._-]*", re.ASCII)
_DEVICE = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", re.ASCII | re.I)
_DRIVE = re.compile(r"[A-Za-z]:")
_RESERVED = re.compile(r'[<>:"|?*\\\x00-\x1f\x7f]')
_FOLD = {code: code + 32 for code in range(ord("A"), ord("Z") + 1)}


def clean(name):
    """`name` with every character outside `A-Z a-z 0-9 . _ -` replaced by
    `_`: how a source name, a subject or a variant is written in a path."""
    return _UNSAFE.sub("_", name)


def fold(text):
    """`text` with ASCII capitals made small and every other character kept:
    how names and paths are compared (export design P-7, part 2)."""
    return text.translate(_FOLD)


@dataclass(frozen=True)
class Names:
    """The output names of a request: `clips` maps each selected source clip
    name, `directions` each direction index of the view's full ring, and
    `subject` and `variant` are the path tokens of the same names."""

    clips: object
    directions: object
    subject: str
    variant: str


def resolve_names(
    selected_clips,
    view,
    *,
    subject,
    variant=sampling.VARIANT,
    clip_aliases=None,
    direction_aliases=None,
    directory=True,
):
    """The output names of `selected_clips` and of every direction of `view`.

    A clip's name is its alias in `clip_aliases` (source name to alias), else
    its source name cleaned; a direction's is its alias in `direction_aliases`
    (index to alias), else its compass label, else `direction-NNN`. For the
    `directory` form every name must be usable in a path: an alias uses only
    `A-Z a-z 0-9 . _ -`, and no name is empty, `.`, `..`, ending in `.`, or a
    Windows device name such as `CON` or `aux.txt`; clip names, and direction
    names, differ ignoring ASCII case, else `UsageError` names the originals.
    Without `directory`, for the positional form whose filenames keep
    their legacy forms, the names are informational and nothing is refused.
    Subject and variant are cleaned and checked only where a path uses them.
    """
    clip_aliases = clip_aliases or {}
    direction_aliases = direction_aliases or {}
    clips = {}
    for selected in selected_clips:
        source = selected.clip.name
        alias = clip_aliases.get(source)
        clips[source] = clean(source) if alias is None else alias
    ring = views.directions(view)
    directions = {}
    for direction in ring:
        alias = direction_aliases.get(direction.index)
        if alias is not None:
            directions[direction.index] = alias
        elif direction.label is not None:
            directions[direction.index] = direction.label
        else:
            directions[direction.index] = f"direction-{direction.index:03d}"
    if directory:
        for source, name in clips.items():
            aliased = clip_aliases.get(source) is not None
            _check_name(name, f"clip {source!r}", aliased)
        _check_distinct(clips, "clips", repr)
        for index, name in directions.items():
            aliased = direction_aliases.get(index) is not None
            _check_name(name, f"direction {index}", aliased)
        label = {d.index: d.label for d in ring}
        _check_distinct(
            directions,
            "directions",
            lambda index: f"{index} ({label[index]})" if label[index] else f"{index}",
        )
    return Names(
        MappingProxyType(clips),
        MappingProxyType(directions),
        clean(subject),
        clean(variant),
    )


def _check_name(name, owner, aliased):
    where = f"{owner}'s output name {name!r}"
    if aliased and not _ALIAS.fullmatch(name):
        raise UsageError(
            f"{where} uses a character outside A-Z a-z 0-9 . _ -; an alias "
            "must already use only those"
        )
    if name == "":
        raise UsageError(f"{owner}'s output name is empty")
    if name in (".", ".."):
        raise UsageError(f"{where} is not a usable name")
    if name.endswith("."):
        raise UsageError(f"{where} ends with a dot")
    if _DEVICE.fullmatch(name):
        raise UsageError(f"{where} is a Windows device name")


def _check_distinct(names, what, shown):
    seen = {}
    for original, name in names.items():
        key = fold(name)
        if key in seen:
            other = seen[key]
            raise UsageError(
                f"{what} {shown(other)} and {shown(original)} both have the output "
                f"name {names[other]!r}"
                + (
                    ""
                    if names[other] == name
                    else f" and {name!r}, equal ignoring case"
                )
                + "; give one an alias"
            )
        seen[key] = original


@dataclass(frozen=True)
class Output:
    """One planned file. `path` is relative to the output directory (or a bare
    name in the positional form); `clip` is a source clip name, `direction` an
    original direction index and `index` a sample index, as far as the kind
    has them."""

    kind: str
    channel: str | None
    path: str
    clip: str | None = None
    direction: int | None = None
    index: int | None = None


@dataclass(frozen=True)
class OutputPlan:
    """Every file a run writes. `artifacts` are the images in the export's
    fixed order: the sheet's colour, normal and depth; then each clip's atlas;
    then each clip's frames over its stored directions and samples; then each
    clip's previews, flat and then lit. A file not written has no entry.
    `manifest` is the metadata file, published last by the publisher."""

    artifacts: tuple[Output, ...]
    manifest: Output


@dataclass(frozen=True)
class Directory:
    """The destination is an output directory."""


@dataclass(frozen=True)
class Positional:
    """The destination is a PNG file, given by its name, such as
    `hero.png`; its other files keep the legacy names beside it."""

    png: str


def plan_outputs(
    request,
    names,
    settings,
    *,
    destination,
    normals=True,
    depth=False,
    previews=True,
    lit=False,
):
    """The `OutputPlan` for `request` (a `plan.RequestPlan`) named by `names`,
    written to `destination` (`Directory` or `Positional`).

    `settings` holds `formats` and the three path templates. The maps follow
    `normals` and `depth`; the flat previews follow `previews`, and the lit
    ones `lit`, which the command sets only with previews and a light. Every
    template is checked for syntax whatever the formats and destination. The
    positional form needs the formats `("sheet",)` and keeps its legacy
    names, with none of the directory-mode refusals. The directory form
    expands the templates for the real stored frames only, and refuses a path
    that is unusable or that two outputs share ignoring ASCII case, or one is
    a directory of another. Raises `UsageError` before anything is written.
    """
    parsed = {
        kind: _parse(kind, getattr(settings, kind))
        for kind in (templates.FRAME_PATH, templates.ATLAS_PATH, templates.SHEET_PATH)
    }
    formats = tuple(settings.formats)
    channels = [COLOR]
    channels += [NORMAL] if normals else []
    channels += [DEPTH] if depth else []
    if isinstance(destination, Positional):
        return _positional(request, destination, formats, channels, previews, lit)
    if not isinstance(destination, Directory):
        raise ValueError(f"not a destination: {destination!r}")
    return _directory(
        request, names, parsed, formats, channels, previews, lit, settings
    )


def _parse(kind, text):
    try:
        return templates.parse(text, kind)
    except templates.TemplateError as error:
        raise UsageError(f"export.{kind} {text!r}: the template {error}") from None


def _positional(request, destination, formats, channels, previews, lit):
    if formats != ("sheet",):
        raise UsageError(
            f"the formats {', '.join(formats)} need an output directory: give "
            "--output-dir instead of an output PNG, or use the formats sheet"
        )
    png = Path(destination.png)
    selected = tuple(clip.selected for clip in request.clips)
    paths = {
        COLOR: png,
        NORMAL: export.normal_path(png),
        DEPTH: export.depth_path(png),
    }
    artifacts = [Output(SHEET, channel, paths[channel].name) for channel in channels]
    flat = export.preview_paths(png, selected)
    lit_paths = export.lit_preview_paths(png, selected)
    for clip, flat_path, lit_path in zip(selected, flat, lit_paths, strict=True):
        name = clip.clip.name
        if previews:
            artifacts.append(Output(PREVIEW, FLAT, flat_path.name, clip=name))
        if lit:
            artifacts.append(Output(PREVIEW, LIT, lit_path.name, clip=name))
    manifest = png.name.removesuffix(".png") + ".json"
    return OutputPlan(tuple(artifacts), Output(MANIFEST, None, manifest))


def _directory(request, names, parsed, formats, channels, previews, lit, settings):
    base = {templates.SUBJECT: names.subject, templates.VARIANT: names.variant}
    suffix = dict(MAP_SUFFIXES)
    entries = []

    def add(output, kind, address):
        template = parsed[kind]
        entries.append((output, f"export.{kind} {template.text!r}", address))

    if "sheet" in formats:
        for channel in channels:
            path = templates.expand(
                parsed[templates.SHEET_PATH], base | {templates.MAP: suffix[channel]}
            )
            add(
                Output(SHEET, channel, path),
                templates.SHEET_PATH,
                f"the sheet, {channel}",
            )
    if "atlases" in formats:
        for clip in request.clips:
            source = clip.selected.clip.name
            for channel in channels:
                values = base | {
                    templates.CLIP: names.clips[source],
                    templates.MAP: suffix[channel],
                }
                path = templates.expand(parsed[templates.ATLAS_PATH], values)
                add(
                    Output(ATLAS, channel, path, clip=source),
                    templates.ATLAS_PATH,
                    f"the atlas of clip {source!r}, {channel}",
                )
    if "frames" in formats:
        for clip in request.clips:
            source = clip.selected.clip.name
            for frame in clip.frames:
                direction = frame.address.direction
                for channel in channels:
                    values = base | {
                        templates.CLIP: names.clips[source],
                        templates.DIRECTION: names.directions[direction],
                        templates.FRAME: frame.index,
                        templates.MAP: suffix[channel],
                    }
                    path = templates.expand(parsed[templates.FRAME_PATH], values)
                    add(
                        Output(
                            FRAME,
                            channel,
                            path,
                            clip=source,
                            direction=direction,
                            index=frame.index,
                        ),
                        templates.FRAME_PATH,
                        f"clip {source!r}, direction {direction}, sample "
                        f"{frame.index}, {channel}",
                    )
    for output, origin, address in entries:
        problem = path_problem(output.path)
        if problem:
            raise UsageError(f"{origin} gives {output.path!r} for {address}: {problem}")
    artifacts = [output for output, _, _ in entries]
    fixed = []
    for clip in request.clips:
        source = clip.selected.clip.name
        name = names.clips[source]
        if previews:
            fixed.append(
                (Output(PREVIEW, FLAT, f"previews/{name}.gif", clip=source), FLAT)
            )
        if lit:
            fixed.append(
                (Output(PREVIEW, LIT, f"previews/{name}.lit.gif", clip=source), LIT)
            )
    manifest = Output(MANIFEST, None, MANIFEST_PATH)
    owners = list(entries)
    owners.append((manifest, "the manifest", MANIFEST_PATH))
    for output, channel in fixed:
        owners.append(
            (output, "a preview", f"the {channel} preview of clip {output.clip!r}")
        )
    _check_exclusive(owners)
    return OutputPlan(tuple(artifacts) + tuple(out for out, _ in fixed), manifest)


def path_problem(path):
    """Why `path`, an expanded image path, cannot be used, or None: it must
    end in lowercase `.png`, use `/` and only `/`, be relative with nonempty
    components that are not `.` or `..`, hold no control or Windows-reserved
    character, and have no component ending in a dot or a space or naming a
    Windows device."""
    if _RESERVED.search(path) and not _DRIVE.match(path):
        return "it has a backslash, a control character or a Windows-reserved character"
    if path.startswith("/") or _DRIVE.match(path):
        return "it is not a relative path"
    if not path.endswith(".png"):
        return "it does not end in .png"
    for component in path.split("/"):
        if component == "":
            return "it has an empty component"
        if component in (".", ".."):
            return f"it has the component {component!r}"
        if component.endswith((".", " ")):
            return f"the component {component!r} ends with a dot or a space"
        if _DEVICE.fullmatch(component):
            return f"the component {component!r} is a Windows device name"
    return None


def _check_exclusive(owners):
    """Refuse two outputs at one path, or a path that is a directory of
    another, comparing ignoring ASCII case. `owners` are `(Output, what wrote
    it, its address)`."""
    seen = {}
    for output, origin, address in owners:
        key = fold(output.path)
        if key in seen:
            other = seen[key]
            raise UsageError(
                f"{other[1]} for {other[2]} and {origin} for {address} would both "
                f"write {output.path!r}"
                + (
                    ""
                    if other[0].path == output.path
                    else f" ({other[0].path!r}, equal ignoring case)"
                )
            )
        seen[key] = (output, origin, address)
    for key, (output, origin, address) in seen.items():
        parts = key.split("/")
        for count in range(1, len(parts)):
            prefix = "/".join(parts[:count])
            if prefix in seen:
                other = seen[prefix]
                raise UsageError(
                    f"{other[1]} for {other[2]} writes the file {other[0].path!r}, "
                    f"which {origin} for {address} needs as a directory in "
                    f"{output.path!r}"
                )
