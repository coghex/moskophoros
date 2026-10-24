"""The images of an export: frame files, per-clip atlases, the combined sheet,
their normal and depth maps and the stored-view previews (export design P-7,
part 4 and 5; P-8, part 3 and P-8a).

`encode` lays the post-cleanup addressed frames of a `plan.RequestPlan` out in
every planned representation and returns the files' bytes with the artifact
descriptors and sample locations a manifest needs. The artifacts follow the
`outputs.OutputPlan` the caller made for the same request, which names their
paths; nothing here chooses a path, creates a file or serializes metadata.

The legacy `export.encode`, `export.previews` and `export.lit_previews` stay
the public path until the schema switch. This module shares their image
operations, so with every direction stored, one global rate and no mirrors
its sheet, maps and previews are byte-identical to theirs. Everything here is
pure.
"""

from dataclasses import dataclass

import numpy as np

from moskophoros import export, imageops, outputs, sampling

SHEET, ATLAS, FRAME, PREVIEW = (
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
FORMATS = ("sheet", "frames", "atlases")
MAX_PADDING = 64


@dataclass(frozen=True)
class Artifact:
    """One encoded file: its `kind`, `channel`, planned `path`, pixel `width`
    and `height`, and its `data`.

    `clip` is the source clip of an atlas, a frame or a preview; `direction`
    (original index) and `index` (sample) belong to a frame; `padding` and
    `cell`, the logical `(width, height)`, to a PNG. A field the kind does not
    have is None. `warnings` are a preview's, for the command to print.
    """

    kind: str
    channel: str
    path: str
    width: int
    height: int
    data: bytes
    clip: str | None = None
    direction: int | None = None
    index: int | None = None
    padding: int | None = None
    cell: tuple[int, int] | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Location:
    """Where a sample's cell is in the PNG artifact `artifact` (its position in
    `Encoded.artifacts`): the logical rectangle `x, y, w, h`, atlas padding
    excluded."""

    artifact: int
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Sample:
    """One real sample: its original `direction` and `index` in `clip`, its
    exact `time_s`, and `locations`, one per enabled PNG representation,
    sorted by artifact."""

    clip: str
    direction: int
    index: int
    time_s: float
    locations: tuple[Location, ...]


@dataclass(frozen=True)
class Encoded:
    """The `artifacts` in the plan's order and the `samples` in clip, stored
    direction, sample order."""

    artifacts: tuple[Artifact, ...]
    samples: tuple[Sample, ...]


def encode(
    frames,
    *,
    request,
    output_plan,
    settings,
    formats,
    atlas_padding=0,
    normals=True,
    depth=False,
    previews=True,
    light=export.NO_LIGHT,
):
    """Encode `frames` as `output_plan` plans, returning an `Encoded`.

    `frames` are the reduced `sampling.ImageFrame`s, in any order: exactly one
    for each frame that `request`, a `plan.RequestPlan`, lists, each the
    fitted cell size. With `normals` or `depth`, or a light placed for lit previews,
    each carries its maps (`sampling.NORMAL_MAP`, `sampling.DEPTH_MAP`).
    `settings` are the fitted capture settings (`ppm`, `cell`, `ground_px`),
    `formats` a nonempty subset of `sheet`, `frames` and `atlases`,
    `atlas_padding` an integer from 0 to 64, and `previews`, `normals`,
    `depth` and `light` as `export.encode` takes them. `output_plan` must be
    the `outputs.plan_outputs` plan for the same request and options.

    Raises `export.DepthOverflow` when depth is written or a lit preview is
    made and a covered pixel's depth lies outside `±export.DEPTH_LIMIT`
    (samples listed in plan order), `export.UsageError` for a preview a
    GIF cannot hold, and `ValueError` for frames or maps that are missing, extra,
    duplicated or the wrong size or type, for unfitted settings and for a plan
    that is not the one these options make: internal errors.
    """
    if settings.ppm is None or settings.cell is None or settings.ground_px is None:
        raise ValueError("the settings are not fitted: scale, cell and ground pixel")
    formats = tuple(formats)
    if not formats or set(formats) - set(FORMATS) or len(set(formats)) != len(formats):
        raise ValueError(f"not a nonempty set of formats: {formats!r}")
    if (
        isinstance(atlas_padding, bool)
        or not isinstance(atlas_padding, int)
        or not 0 <= atlas_padding <= MAX_PADDING
    ):
        raise ValueError(f"atlas padding is not 0 to {MAX_PADDING}: {atlas_padding!r}")
    lit = previews and light.position is not None
    planned = tuple(output_plan.artifacts)
    _check_plan(planned, request, formats, normals, depth, previews, lit)

    width, height = settings.cell
    requested = request.frames
    frames = tuple(frames)
    pixels = export.pixels_by_address(frames, requested, (height, width, 4))
    need_normals = normals or lit
    need_depths = depth or lit
    normal_maps = (
        export.maps_by_address(frames, sampling.NORMAL_MAP, (height, width, 3))
        if need_normals
        else None
    )
    depth_maps = (
        export.maps_by_address(frames, sampling.DEPTH_MAP, (height, width))
        if need_depths
        else None
    )
    if need_depths:
        export.check_depths(requested, pixels, depth_maps, settings.ppm)

    delays = (
        _preview_delays(request, width)
        if any(a.kind == PREVIEW for a in planned)
        else {}
    )

    normal_bytes = {}
    depth_codes = {}
    cells = {COLOR: pixels, NORMAL: {}, DEPTH: {}}
    for frame in requested:
        address = frame.address
        covered = pixels[address][..., 3] > 0
        if need_normals:
            encoded = np.zeros((height, width, 3), dtype=np.uint8)
            encoded[covered] = imageops.encode_normal(normal_maps[address][covered])
            normal_bytes[address] = encoded
        if need_depths:
            codes = np.full((height, width), export.NO_SURFACE, dtype=np.uint16)
            codes[covered] = export.encode_depth(depth_maps[address][covered])
            depth_codes[address] = codes
        if normals:
            cell = np.zeros((height, width, 4), dtype=np.uint8)
            cell[covered, :3] = normal_bytes[address][covered]
            cell[covered, 3] = pixels[address][covered, 3]
            cells[NORMAL][address] = cell
        if depth:
            cells[DEPTH][address] = depth_codes[address]
    shown = {FLAT: pixels}
    if lit:
        shown[LIT] = {
            frame.address: imageops.light_pixels(
                pixels[frame.address],
                normal_bytes[frame.address],
                depth_codes[frame.address],
                settings.ground_px,
                light.position,
                light.intensity,
                light.ambient,
            )
            for frame in requested
        }

    clips = {clip.selected.clip.name: clip for clip in request.clips}
    slots = {(f.address.clip, f.address.direction, f.index): f for f in requested}
    locations = {frame.address: [] for frame in requested}
    artifacts = []
    for position, output in enumerate(planned):
        if output.kind == PREVIEW:
            artifacts.append(
                _preview(
                    output,
                    clips[output.clip],
                    (width, height),
                    shown[output.channel],
                    delays[output.clip],
                )
            )
            continue
        layer = cells[output.channel]
        padding = atlas_padding if output.kind == ATLAS else 0
        if output.kind == SHEET:
            image, placed = _sheet(request.clips, layer, (width, height))
        elif output.kind == ATLAS:
            image, placed = _atlas(clips[output.clip], layer, (width, height), padding)
        else:
            address = slots[output.clip, output.direction, output.index].address
            image, placed = layer[address], {address: (0, 0)}
        for address, (x, y) in placed.items():
            locations[address].append(Location(position, x, y, width, height))
        artifacts.append(
            Artifact(
                output.kind,
                output.channel,
                output.path,
                int(image.shape[1]),
                int(image.shape[0]),
                export.encode_png(image),
                clip=output.clip,
                direction=output.direction,
                index=output.index,
                padding=padding,
                cell=(width, height),
            )
        )

    samples = tuple(
        Sample(
            frame.address.clip,
            frame.address.direction,
            frame.index,
            frame.address.time_s,
            tuple(locations[frame.address]),
        )
        for frame in requested
    )
    return Encoded(tuple(artifacts), samples)


def _check_plan(planned, request, formats, normals, depth, previews, lit):
    """Raise `ValueError` unless `planned` is exactly the artifacts these
    options and `request` make, in the export's fixed order."""
    channels = [COLOR] + [NORMAL] * normals + [DEPTH] * depth
    expected = []
    if "sheet" in formats:
        expected += [(SHEET, channel, None, None, None) for channel in channels]
    if "atlases" in formats:
        for clip in request.clips:
            name = clip.selected.clip.name
            expected += [(ATLAS, channel, name, None, None) for channel in channels]
    if "frames" in formats:
        for clip in request.clips:
            name = clip.selected.clip.name
            for frame in clip.frames:
                expected += [
                    (FRAME, channel, name, frame.address.direction, frame.index)
                    for channel in channels
                ]
    for clip in request.clips:
        name = clip.selected.clip.name
        expected += [(PREVIEW, FLAT, name, None, None)] * previews
        expected += [(PREVIEW, LIT, name, None, None)] * lit
    actual = [(o.kind, o.channel, o.clip, o.direction, o.index) for o in planned]
    if actual == expected:
        return
    for position, (want, got) in enumerate(zip(expected, actual, strict=False)):
        if want != got:
            raise ValueError(
                f"the output plan's artifact {position} is {got}, but the options "
                f"and request plan {want}"
            )
    raise ValueError(
        f"the output plan has {len(actual)} artifacts, but the options and "
        f"request plan {len(expected)}"
    )


def _layout(cells, shape):
    """An empty image `shape` of the cells' dtype and rank."""
    sample = next(iter(cells.values()))
    return np.zeros(shape + sample.shape[2:], dtype=sample.dtype)


def _sheet(clips, layer, cell):
    """The combined sheet of `layer`, unpadded, and where each sample is."""
    width, height = cell
    columns = max(clip.sampling.frame_count for clip in clips)
    rows = sum(len(clip.directions) for clip in clips)
    image = _layout(layer, (rows * height, columns * width))
    placed = {}
    first = 0
    for clip in clips:
        order = {d.index: r for r, d in enumerate(clip.directions)}
        for frame in clip.frames:
            row = first + order[frame.address.direction]
            x, y = frame.index * width, row * height
            image[y : y + height, x : x + width] = layer[frame.address]
            placed[frame.address] = (x, y)
        first += len(clip.directions)
    return image, placed


def _atlas(clip, layer, cell, padding):
    """A clip's atlas of `layer`: a row per stored direction, a column per
    sample, each cell's border repeating its nearest edge texel."""
    width, height = cell
    slot_w, slot_h = width + 2 * padding, height + 2 * padding
    image = _layout(
        layer, (len(clip.directions) * slot_h, clip.sampling.frame_count * slot_w)
    )
    rows = {d.index: r for r, d in enumerate(clip.directions)}
    placed = {}
    for frame in clip.frames:
        cell_pixels = layer[frame.address]
        if padding:
            cell_pixels = np.pad(
                cell_pixels,
                ((padding, padding), (padding, padding))
                + ((0, 0),) * (cell_pixels.ndim - 2),
                mode="edge",
            )
        x = frame.index * slot_w
        y = rows[frame.address.direction] * slot_h
        image[y : y + slot_h, x : x + slot_w] = cell_pixels
        placed[frame.address] = (x + padding, y + padding)
    return image, placed


def _preview_delays(request, width):
    """Each clip's GIF frame delays, or `export.UsageError` naming a clip whose
    preview GIF cannot hold: too wide, or a frame too long."""
    result = {}
    for clip in request.clips:
        name = clip.selected.clip.name
        preview_width = len(clip.directions) * width * export.PREVIEW_SCALE
        if preview_width > export.MAX_PREVIEW_WIDTH:
            raise export.UsageError(
                f"the preview of clip {name!r} would be {preview_width} pixels "
                f"wide, over GIF's limit of {export.MAX_PREVIEW_WIDTH} pixels"
            )
        timing = clip.sampling
        delays = export.preview_delays_ms(
            timing.frame_duration, timing.frame_count, clip.selected.one_shot
        )
        longest = max(delays)
        if longest > export.MAX_PREVIEW_DELAY_MS:
            raise export.UsageError(
                f"a frame of clip {name!r}'s preview would last {longest} ms, "
                f"over GIF's limit of {export.MAX_PREVIEW_DELAY_MS} ms"
            )
        result[name] = delays
    return result


def _preview(output, clip, cell, shown, delays):
    """One clip's flat or lit preview from `shown`, the cells by address:
    sample `k` shows the stored directions side by side in their configured
    order."""
    width, height = cell
    slots = {(f.address.direction, f.index): f.address for f in clip.frames}
    rows = (
        np.concatenate([shown[slots[d.index, k]] for d in clip.directions], axis=1)
        for k in range(clip.sampling.frame_count)
    )
    gif, reduced = export.preview_gif(rows, delays)
    return Artifact(
        PREVIEW,
        output.channel,
        output.path,
        len(clip.directions) * width * export.PREVIEW_SCALE,
        height * export.PREVIEW_SCALE,
        gif,
        clip=output.clip,
        warnings=export.reduction_warnings(output.clip, reduced, output.channel == LIT),
    )
