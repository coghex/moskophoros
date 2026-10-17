"""The sheet PNG, its normal and depth maps, its `moskophoros.sheet/13` JSON
and the animated previews, flat and lit, following design §Export.

`encode` lays the reduced frames out on the sheet and its maps, describes
them and returns the files' bytes; `normal_path` and `depth_path` name the
maps; `write` writes the sheet and JSON where the caller says. `previews`
returns each clip's GIF, `preview_paths` names them and `write_previews`
writes them; `lit_previews` and `lit_preview_paths` do the same for the
previews lit by a `Light`. Everything except the writers is pure, and the same inputs give
byte-identical output (design §Reproducibility).
"""

import hashlib
import io
import json
import math
import platform
import re
import struct
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType

import numpy as np
import PIL
from PIL import Image

import moskophoros
from moskophoros import imageops, sampling, views
from moskophoros.capture.backend import settings_document

SCHEMA = "moskophoros.sheet/13"
# The global formula of generated ramps, in its recorded order, at the
# shipped defaults (material styling design D-30, D-33).
DEFAULT_RAMP = MappingProxyType(
    {"lightness_step": 0.12, "hue_shift_deg": -12.0, "chroma_fade": 0.3}
)
OVERFLOW_ERROR = 4
# The depth map's code for "no surface", for a depth of 0 (the ground point's
# plane), and the depths it can hold, in sheet pixels (lighting sheet design
# D-10, D-21).
NO_SURFACE = 0
DEPTH_ZERO = 32768
DEPTH_LIMIT = 2047.9375
USAGE_ERROR = 2
PREVIEW_SCALE = 4
PREVIEW_BACKGROUND = (128, 128, 128)
# GIF stores widths in 16 bits and delays in 16 bits of centiseconds.
MAX_PREVIEW_WIDTH = 65_535
MAX_PREVIEW_DELAY_MS = 655_350
MIN_PREVIEW_DELAY_MS = 20
ONE_SHOT_HOLD_MS = 500
_SHA256 = re.compile(r"[0-9a-f]{64}")
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


class DepthOverflow(Exception):
    """Covered pixels whose depth the depth map cannot hold: exit
    classification 4, as a subject overflowing a fixed cell is (lighting
    sheet design D-21).

    `frames` holds each overflowing frame's address with the lowest and
    highest depth of its covered pixels, in sheet pixels, in request order.
    """

    exit_code = OVERFLOW_ERROR

    def __init__(self, message, frames):
        super().__init__(message)
        self.frames = frames


class UsageError(Exception):
    """Settings whose previews GIF cannot represent: exit classification 2."""

    exit_code = USAGE_ERROR


@dataclass(frozen=True)
class Light:
    """The preview light (lighting sheet design D-13, D-14): `position`, its
    `(x, y, z)` in sheet pixels from the ground point in the camera's frame,
    or None for no light; `intensity`, `I`; and `ambient`, `A`."""

    position: tuple[float, float, float] | None = None
    intensity: float = 1.0
    ambient: float = 0.3

    def record(self):
        """The sheet's `settings.light`."""
        return {
            "position": (
                None
                if self.position is None
                else [float(value) for value in self.position]
            ),
            "intensity": float(self.intensity),
            "ambient": float(self.ambient),
        }


NO_LIGHT = Light()


@dataclass(frozen=True)
class Sheet:
    """The encoded sheet: `png` and `json` bytes, ready to write, and the
    normal and depth maps' `normal` and `depth` PNG bytes, each None when it
    is not written."""

    png: bytes
    json: bytes
    normal: bytes | None = None
    depth: bytes | None = None


@dataclass(frozen=True)
class Preview:
    """One clip's encoded preview, with any warning for the command to print."""

    clip: str
    gif: bytes
    warnings: tuple[str, ...]


def generator(backend):
    """The sheet's `generator`: this tool and its libraries, and the Blender
    version, the renderer, the colour's technique and the shade's technique
    with their fixed parameters, that a render result's `backend` reports.
    The shade's capture values are settings, recorded in `settings.shade`."""
    missing = [
        key for key in ("blender", "renderer", "color", "shade") if key not in backend
    ]
    if missing:
        raise ValueError(f"the render provenance lacks {', '.join(missing)}")
    return {
        "tool": "moskophoros",
        "version": moskophoros.__version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pillow": PIL.__version__,
        "blender": backend["blender"],
        "renderer": backend["renderer"],
        "color": dict(backend["color"]),
        "shade": dict(backend["shade"]),
    }


def fingerprint(generator, settings, source_sha256):
    """`sha256:<hex>` over the canonical JSON of the object mirroring the sheet,
    `{"generator": …, "settings": …, "source": {"sha256": …}}`.

    Canonical means recursively sorted keys, no whitespace, non-ASCII kept as
    is, no NaN or infinity, UTF-8 and no trailing newline. `settings` is the
    sheet's `settings` object.
    """
    if not isinstance(source_sha256, str) or not _SHA256.fullmatch(source_sha256):
        raise ValueError(f"the source digest is not 64 hex digits: {source_sha256!r}")
    mirrored = {
        "generator": generator,
        "settings": settings,
        "source": {"sha256": source_sha256},
    }
    canonical = json.dumps(
        mirrored,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def sheet_settings(
    settings,
    selected_clips,
    style,
    *,
    shade_range,
    previews=True,
    normals=True,
    depth=False,
    light=NO_LIGHT,
    ramp=DEFAULT_RAMP,
):
    """The sheet's `settings` object: the capture job's settings, fitted, then
    `previews`, whether the animated previews are written, `normals` and
    `depth`, whether the normal and depth maps are written, `light`, the
    preview light's record whether or not one is placed, `shade`, the
    capture's shade values with the shade range `[lo, hi]` stylize used,
    `ramp`, the global formula of generated ramps (`lightness_step`,
    `hue_shift_deg`, `chroma_fade`) whether or not a library is used, and
    `style` recorded as given, just before `clips`.

    `style` is the record the command resolved, written and fingerprinted as
    it is: export does not know which reductions or palettes exist.
    """
    document = settings_document(settings, selected_clips)
    clips = document.pop("clips")
    # The sheet records the global values; each material's own values are
    # in its library entry, recorded inline in the style.
    capture = document.pop("shade")
    shade = {
        key: capture[key]
        for key in (
            "ao_distance_m",
            "ao_samples",
            "occlusion_weight",
            "convexity_weight",
        )
    } | {"range": [int(bound) for bound in shade_range]}
    return document | {
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
        "clips": clips,
    }


def encode(
    frames,
    *,
    generator,
    source,
    subject,
    settings,
    style,
    selected_clips,
    image_path,
    shade_range,
    previews=True,
    normals=True,
    depth=False,
    light=NO_LIGHT,
    ramp=DEFAULT_RAMP,
):
    """Lay out and describe the sheet, returning its PNG, JSON and, with
    `normals` and `depth`, its normal and depth maps' bytes.

    `frames` are the reduced `sampling.ImageFrame`s, exactly one for each
    frame the selected clips and resolved `settings` request, each the cell
    size, in any order; with `normals` or `depth`, each carries its normal or
    depth map (`sampling.NORMAL_MAP`, `sampling.DEPTH_MAP`). `generator` comes from `generator()`, `source`
    is the capture `Source`, `style` is the style record `sheet_settings`
    takes, `selected_clips` are `gltf.SelectedClip`s in selection order,
    `image_path` is where the PNG will be written; only its base name is
    recorded, as is the source's and the normal map's; `shade_range` is the
    shade range stylize used, recorded in `settings.shade`; `previews`
    records whether the animated previews are written; `normals` and
    `depth` whether the normal and depth maps are; and `light` is the preview
    light, recorded in `settings.light`.

    The normal map is laid out as the sheet is: each pixel the colour covers
    (alpha above 0) holds its normal encoded by `imageops.encode_normal`,
    unblended, with the colour's alpha, and every other pixel is
    `(0, 0, 0, 0)` (lighting sheet design D-17; alpha design D-11). The depth
    map, a 16-bit greyscale PNG laid out the same way, holds
    `32768 + floor(16 · depth + ½)` for each covered pixel's depth in sheet
    pixels, and 0, "no surface", everywhere else (D-10).

    Raises `DepthOverflow` when the depth map is written and a covered
    pixel's depth lies outside `±DEPTH_LIMIT` sheet pixels (D-21), and
    `ValueError` for frames that are missing, extra, duplicated or the wrong
    size, or lack a map that is to be written, or for unfitted settings:
    these are internal errors.
    """
    if settings.ppm is None or settings.cell is None or settings.ground_px is None:
        raise ValueError("the settings are not fitted: scale, cell and ground pixel")
    selected_clips = tuple(selected_clips)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    directions = views.directions(view)
    requested = sampling.frames(
        subject, selected_clips, view, settings.fps, settings.frames
    )
    width, height = settings.cell
    frames = tuple(frames)
    pixels = _pixels_by_address(frames, requested, (height, width, 4))
    normal_maps = (
        _maps_by_address(frames, sampling.NORMAL_MAP, (height, width, 3))
        if normals
        else None
    )
    depth_maps = (
        _maps_by_address(frames, sampling.DEPTH_MAP, (height, width)) if depth else None
    )
    if depth:
        _check_depths(requested, pixels, depth_maps, settings.ppm)

    row_of_clip = {selected.clip.name: c for c, selected in enumerate(selected_clips)}
    samplings = [
        sampling.sample(selected, settings.fps, settings.frames)
        for selected in selected_clips
    ]
    columns = max(s.frame_count for s in samplings)
    rows = len(selected_clips) * len(directions)
    image = np.zeros((rows * height, columns * width, 4), dtype=np.uint8)
    normal_image = np.zeros_like(image) if normals else None
    depth_image = np.zeros(image.shape[:2], dtype=np.uint16) if depth else None
    frame_documents = []
    for frame in requested:
        address = frame.address
        row = row_of_clip[address.clip] * len(directions) + address.direction
        x, y = frame.index * width, row * height
        image[y : y + height, x : x + width] = pixels[address]
        if normals:
            alpha = pixels[address][..., 3]
            covered = alpha > 0
            cell = np.zeros((height, width, 4), dtype=np.uint8)
            cell[covered, :3] = imageops.encode_normal(normal_maps[address][covered])
            cell[covered, 3] = alpha[covered]
            normal_image[y : y + height, x : x + width] = cell
        if depth:
            covered = pixels[address][..., 3] > 0
            codes = np.full((height, width), NO_SURFACE, dtype=np.uint16)
            codes[covered] = encode_depth(depth_maps[address][covered])
            depth_image[y : y + height, x : x + width] = codes
        frame_documents.append(
            {
                "clip": address.clip,
                "direction": address.direction,
                "index": frame.index,
                "time_s": float(address.time_s),
                "x": x,
                "y": y,
                "w": width,
                "h": height,
            }
        )

    settings_doc = sheet_settings(
        settings,
        selected_clips,
        style,
        shade_range=shade_range,
        previews=previews,
        normals=normals,
        depth=depth,
        light=light,
        ramp=ramp,
    )
    description = {
        "schema": SCHEMA,
        "generator": generator,
        "source": {"file": Path(source.path).name, "sha256": source.sha256},
        "subject": subject,
        "variant": sampling.VARIANT,
        "settings": settings_doc,
        "fingerprint": fingerprint(generator, settings_doc, source.sha256),
        "image": {
            "file": Path(image_path).name,
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
        },
        "maps": {
            "normal": {"file": normal_path(image_path).name} if normals else None,
            "depth": {"file": depth_path(image_path).name} if depth else None,
        },
        "directions": [
            {"index": d.index, "angle_deg": float(d.angle), "label": d.label}
            for d in directions
        ],
        "clips": [
            {
                "name": selected.clip.name,
                "loop": not selected.one_shot,
                "duration_s": float(selected.clip.t1 - selected.clip.t0),
                "frame_count": s.frame_count,
                "frame_duration_s": float(s.frame_duration),
                "time_scale": float(s.time_scale),
            }
            for selected, s in zip(selected_clips, samplings, strict=True)
        ],
        "frames": frame_documents,
    }
    return Sheet(
        _png(image),
        _json(description),
        None if normal_image is None else _png(normal_image),
        None if depth_image is None else _png(depth_image),
    )


def normal_path(png_path):
    """The normal map's path, `<stem>.normal.png` beside the sheet PNG."""
    png_path = Path(png_path)
    return png_path.with_name(png_path.name.removesuffix(".png") + ".normal.png")


def depth_path(png_path):
    """The depth map's path, `<stem>.depth.png` beside the sheet PNG."""
    png_path = Path(png_path)
    return png_path.with_name(png_path.name.removesuffix(".png") + ".depth.png")


def encode_depth(depths):
    """Encode depths in sheet pixels as the depth map's codes,
    `32768 + floor(16 · depth + ½)`, half up (lighting sheet design
    §Numerical reference): 1 to 65535 for −2047.9375 to +2047.9375.

    Returns a new `uint16` array of the input's shape. Raises `ValueError`
    for a depth that is not finite or encodes outside 1 to 65535.
    """
    depths = np.asarray(depths, dtype=np.float64)
    if not np.isfinite(depths).all():
        raise ValueError("depths must be finite")
    codes = DEPTH_ZERO + np.floor(16 * depths + 0.5)
    if ((codes < 1) | (codes > 0xFFFF)).any():
        raise ValueError(f"depths must lie within ±{DEPTH_LIMIT} sheet pixels")
    return codes.astype(np.uint16)


def _check_depths(requested, pixels, depth_maps, ppm):
    """Raise `DepthOverflow` for frames with a covered pixel whose depth the
    depth map cannot hold (lighting sheet design D-21), in request order."""
    overflowing = []
    for frame in requested:
        covered = pixels[frame.address][..., 3] > 0
        depths = depth_maps[frame.address][covered]
        if depths.size and (np.abs(depths) > DEPTH_LIMIT).any():
            overflowing.append(
                (frame.address, (float(depths.min()), float(depths.max())))
            )
    if not overflowing:
        return
    lines = [
        f"the subject's depth overflows the depth map at {ppm!r} pixels per "
        f"meter: it holds -{DEPTH_LIMIT} to +{DEPTH_LIMIT} sheet pixels, and "
        "depth is never clamped or rescaled; give a smaller --ppm:"
    ]
    for address, (low, high) in overflowing:
        lines.append(
            f"  clip {address.clip!r}, direction {address.direction}, "
            f"time {address.time_s!r} s: {low!r} to {high!r} px"
        )
    raise DepthOverflow("\n".join(lines), tuple(overflowing))


def write(sheet, png_path, json_path):
    """Write an encoded sheet to the paths the caller chose."""
    Path(png_path).write_bytes(sheet.png)
    Path(json_path).write_bytes(sheet.json)


def _pixels_by_address(frames, requested, shape):
    """Map each requested address to its frame's pixels, or raise."""
    wanted = {frame.address for frame in requested}
    pixels = {}
    for frame in frames:
        address = frame.address
        if address in pixels:
            raise ValueError(f"two frames have the address {address}")
        if address not in wanted:
            raise ValueError(f"a frame has the unrequested address {address}")
        array = frame.pixels
        if (
            not isinstance(array, np.ndarray)
            or array.dtype != np.uint8
            or array.shape != shape
        ):
            described = (
                f"{array.dtype} {array.shape}"
                if isinstance(array, np.ndarray)
                else type(array).__name__
            )
            raise ValueError(
                f"the frame at {address} is {described}, not uint8 {shape}"
            )
        pixels[address] = array
    missing = [frame.address for frame in requested if frame.address not in pixels]
    if missing:
        raise ValueError(
            f"{len(missing)} requested frame(s) are missing, the first {missing[0]}"
        )
    return pixels


def _maps_by_address(frames, name, shape):
    """Map each frame's address to its map under `name`, or raise."""
    maps = {}
    for frame in frames:
        array = frame.buffers.get(name)
        if not isinstance(array, np.ndarray) or array.shape != shape:
            kind = "normal" if name == sampling.NORMAL_MAP else "depth"
            raise ValueError(f"the frame at {frame.address} has no {shape} {kind} map")
        maps[frame.address] = array
    return maps


def _png(image):
    """An 8-bit RGBA PNG with no text or time chunks."""
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()


def _json(description):
    text = json.dumps(description, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def previews(frames, *, subject, settings, selected_clips, lit=False):
    """Each selected clip's animated GIF preview, in sheet order.

    `frames` are the plain frames `encode` takes. GIF frame `k` shows sample
    `k` of every direction side by side in index order, enlarged
    `PREVIEW_SCALE` times, each pixel blended over a solid
    `PREVIEW_BACKGROUND` by `blend_over_background`, so a transparent pixel
    is the background and an opaque one keeps its colour. A frame keeps its
    exact colors when it has at most 256 of them, partly transparent pixels'
    blends included; otherwise it is reduced to 256 without dithering and
    the preview warns, even when the sheet is paletted (alpha design D-13). Each frame lasts the clip's frame duration in whole
    centiseconds, rounded half up and at least 20 ms; a one-shot clip holds
    its last frame 500 ms longer. The GIF loops forever. With `lit`, the
    frames are lit ones (`lit_previews`) and the warning says so.

    Raises `UsageError` when a preview would be wider than
    `MAX_PREVIEW_WIDTH` or a frame delay longer than `MAX_PREVIEW_DELAY_MS`,
    and `ValueError` for wrong frames, as `encode` does.
    """
    if settings.cell is None:
        raise ValueError("the settings are not fitted: no cell size")
    selected_clips = tuple(selected_clips)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    count = len(views.directions(view))
    width, height = settings.cell
    preview_width = count * width * PREVIEW_SCALE
    plans = []
    for selected in selected_clips:
        name = selected.clip.name
        if preview_width > MAX_PREVIEW_WIDTH:
            raise UsageError(
                f"the preview of clip {name!r} would be {preview_width} pixels "
                f"wide, over GIF's limit of {MAX_PREVIEW_WIDTH} pixels"
            )
        timing = sampling.sample(selected, settings.fps, settings.frames)
        delays = preview_delays_ms(
            timing.frame_duration, timing.frame_count, selected.one_shot
        )
        longest = max(delays)
        if longest > MAX_PREVIEW_DELAY_MS:
            raise UsageError(
                f"a frame of clip {name!r}'s preview would last {longest} ms, "
                f"over GIF's limit of {MAX_PREVIEW_DELAY_MS} ms"
            )
        plans.append((name, timing.times, delays))

    requested = sampling.frames(
        subject, selected_clips, view, settings.fps, settings.frames
    )
    pixels = _pixels_by_address(frames, requested, (height, width, 4))

    result = []
    for name, times, delays in plans:
        images = []
        reduced = False
        for time_s in times:
            row = np.concatenate(
                [
                    pixels[
                        sampling.FrameAddress(
                            subject, sampling.VARIANT, name, d, time_s
                        )
                    ]
                    for d in range(count)
                ],
                axis=1,
            )
            transparent = row[..., 3] == 0
            rgb = blend_over_background(row)
            indices, palette, frame_reduced = _palette_frame(rgb, transparent)
            reduced |= frame_reduced
            indices = indices.repeat(PREVIEW_SCALE, axis=0).repeat(
                PREVIEW_SCALE, axis=1
            )
            images.append((indices, palette))
        warnings = ()
        if reduced:
            kind = "lit preview" if lit else "preview"
            warnings = (
                f"clip {name!r}'s {kind} has frames with more than 256 colors, "
                "reduced to 256 without dithering",
            )
        result.append(Preview(name, _gif(images, delays), warnings))
    return tuple(result)


def blend_over_background(pixels):
    """RGBA `pixels` blended over the solid `PREVIEW_BACKGROUND`, in 8-bit
    sRGB straight alpha, as an image viewer shows a PNG (alpha design D-13):
    each channel is `floor((c · α + g · (255 − α)) / 255 + ½)`, with `c` the
    pixel's channel, `α` its alpha and `g` the background's channel, in exact
    integers. It is exact at `α` 0 and 255: a transparent pixel is the
    background and an opaque one keeps its colour. Returns a new `uint8`
    array of the RGB channels."""
    pixels = np.asarray(pixels)
    alpha = pixels[..., 3:4].astype(np.int64)
    rgb = pixels[..., :3].astype(np.int64)
    grey = np.asarray(PREVIEW_BACKGROUND, dtype=np.int64)
    # floor(x / 255 + ½) is floor((2x + 255) / 510).
    return ((2 * (rgb * alpha + grey * (255 - alpha)) + 255) // 510).astype(np.uint8)


def lit_previews(frames, *, subject, settings, selected_clips, light):
    """Each selected clip's preview lit by `light`, a `Light` with a
    position, in sheet order, as `previews` makes the flat ones (lighting
    sheet design D-4, D-13, D-14, D-22).

    Each covered pixel, alpha above 0, is lit from the frame's normal and
    depth **as encoded**, `imageops.encode_normal` and `encode_depth`,
    whether or not the map files are written, by `imageops.light_pixels` at
    the cell's ground pixel, keeping its alpha; the lit frames are then
    blended and become GIFs exactly as the flat previews do, a 256-colour
    reduction warning naming the clip's lit preview (alpha design D-13). Raises `DepthOverflow` when a covered pixel's depth lies outside
    `±DEPTH_LIMIT` (D-21, D-24), `UsageError` as `previews` does, and
    `ValueError` for wrong frames or a light with no position.
    """
    if light.position is None:
        raise ValueError("lit previews need a light with a position")
    if settings.cell is None or settings.ground_px is None:
        raise ValueError("the settings are not fitted: no cell or ground pixel")
    selected_clips = tuple(selected_clips)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    requested = sampling.frames(
        subject, selected_clips, view, settings.fps, settings.frames
    )
    width, height = settings.cell
    frames = tuple(frames)
    pixels = _pixels_by_address(frames, requested, (height, width, 4))
    normals = _maps_by_address(frames, sampling.NORMAL_MAP, (height, width, 3))
    depths = _maps_by_address(frames, sampling.DEPTH_MAP, (height, width))
    _check_depths(requested, pixels, depths, settings.ppm)
    lit = []
    for frame in frames:
        address = frame.address
        covered = pixels[address][..., 3] > 0
        normal_bytes = np.zeros((height, width, 3), dtype=np.uint8)
        normal_bytes[covered] = imageops.encode_normal(normals[address][covered])
        codes = np.zeros((height, width), dtype=np.uint16)
        codes[covered] = encode_depth(depths[address][covered])
        lit.append(
            sampling.ImageFrame(
                address,
                imageops.light_pixels(
                    pixels[address],
                    normal_bytes,
                    codes,
                    settings.ground_px,
                    light.position,
                    light.intensity,
                    light.ambient,
                ),
                frame.metadata,
            )
        )
    return previews(
        lit,
        subject=subject,
        settings=settings,
        selected_clips=selected_clips,
        lit=True,
    )


def lit_preview_paths(png_path, selected_clips):
    """Each selected clip's lit preview path: its flat preview's name with
    `<stem>` replaced by `<stem>-lit` (lighting sheet design D-22), so
    `hero.walk.gif` gives `hero-lit.walk.gif`, with the same cleaned name and
    suffix. Every flat name begins `<stem>.` and every lit one `<stem>-lit.`,
    so the two never collide."""
    png_path = Path(png_path)
    stem = png_path.stem
    return tuple(
        path.with_name(f"{stem}-lit{path.name[len(stem) :]}")
        for path in preview_paths(png_path, selected_clips)
    )


def preview_delays_ms(frame_duration_s, frame_count, one_shot):
    """Each GIF frame's delay in milliseconds, a multiple of 10.

    The frame duration is rounded to the nearest 10 ms, halves up, and is at
    least 20 ms; a one-shot clip's last frame lasts 500 ms longer. A duration
    too long for a float, such as `1/fps` at a tiny fps, gives `math.inf`.
    """
    if math.isinf(frame_duration_s):
        delay = math.inf
    else:
        centiseconds = math.floor(Fraction(frame_duration_s) * 100 + Fraction(1, 2))
        delay = max(MIN_PREVIEW_DELAY_MS, 10 * centiseconds)
    delays = [delay] * frame_count
    if one_shot:
        delays[-1] += ONE_SHOT_HOLD_MS
    return delays


def preview_paths(png_path, selected_clips):
    """Each selected clip's preview path, `<stem>.<name>.gif` beside the PNG.

    A clip name is made filename-safe by replacing every character outside
    `A–Z a–z 0–9 . _ -` with `_`. Names are compared ignoring ASCII case. In
    sheet order, a clip takes its cleaned name unless an earlier preview has
    it; otherwise it takes the smallest `-2`, `-3`, … suffix matching neither
    another clip's cleaned name nor a name already assigned.
    """
    png_path = Path(png_path)
    cleaned = [_UNSAFE.sub("_", selected.clip.name) for selected in selected_clips]
    assigned = set()
    paths = []
    for i, clean in enumerate(cleaned):
        name = clean
        if name.lower() in assigned:
            others = {other.lower() for j, other in enumerate(cleaned) if j != i}
            suffix = 2
            while f"{clean}-{suffix}".lower() in others | assigned:
                suffix += 1
            name = f"{clean}-{suffix}"
        assigned.add(name.lower())
        paths.append(png_path.with_name(f"{png_path.stem}.{name}.gif"))
    return tuple(paths)


def write_previews(previews, paths):
    """Write each preview to the path the caller chose for it."""
    previews, paths = tuple(previews), tuple(paths)
    if len(previews) != len(paths):
        raise ValueError(f"{len(previews)} previews but {len(paths)} paths")
    for preview, path in zip(previews, paths, strict=True):
        Path(path).write_bytes(preview.gif)


def _palette_frame(rgb, transparent):
    """Index an RGB frame: `(indices, palette bytes, reduced)`.

    At most 256 distinct colors are kept exactly. Otherwise the colors are
    reduced to 255 by median cut without dithering, and the last entry is
    the exact background, which every wholly transparent pixel keeps.
    """
    packed = (
        rgb[..., 0].astype(np.uint32) << 16
        | rgb[..., 1].astype(np.uint32) << 8
        | rgb[..., 2].astype(np.uint32)
    )
    colors, inverse = np.unique(packed, return_inverse=True)
    if len(colors) <= 256:
        palette = np.stack([colors >> 16, colors >> 8 & 255, colors & 255], axis=1)
        indices = inverse.reshape(packed.shape).astype(np.uint8)
        return indices, palette.astype(np.uint8).tobytes(), False
    quantized = Image.fromarray(rgb).quantize(
        colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    indices = np.array(quantized, dtype=np.uint8)
    palette = bytes(quantized.getpalette())
    background = len(palette) // 3
    indices[transparent] = background
    return indices, palette + bytes(PREVIEW_BACKGROUND), True


def _gif(images, delays_ms):
    """An animated GIF of indexed full frames, each with its own color table
    and delay, looping forever. Every frame is kept, even one identical to the
    one before it."""
    height, width = images[0][0].shape
    parts = [
        b"GIF89a",
        struct.pack("<HHBBB", width, height, 0, 0, 0),
        # NETSCAPE2.0 application extension: loop forever.
        b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00",
    ]
    for (indices, palette), delay in zip(images, delays_ms, strict=True):
        table, data = _lzw_frame(indices, palette)
        size_bits = (len(table) // 3).bit_length() - 2
        # Graphic control extension: disposal 1 (leave in place), no
        # transparency, the delay in centiseconds.
        parts.append(struct.pack("<BBBBHBB", 0x21, 0xF9, 4, 1 << 2, delay // 10, 0, 0))
        parts.append(
            struct.pack("<BHHHHB", 0x2C, 0, 0, width, height, 0x80 | size_bits)
        )
        parts.append(table)
        parts.append(data)
    parts.append(b"\x3b")
    return b"".join(parts)


def _lzw_frame(indices, palette):
    """Encode one indexed frame with Pillow and return its color table, padded
    to a power of two, and its LZW data: the minimum code size byte and the
    data sub-blocks with their terminator."""
    image = Image.frombytes(
        "P", (indices.shape[1], indices.shape[0]), indices.tobytes()
    )
    image.putpalette(palette)
    buffer = io.BytesIO()
    image.save(buffer, format="GIF", interlace=False)
    data = buffer.getvalue()
    flags = data[10]
    offset = 13
    table = b""
    if flags & 0x80:
        size = 3 << ((flags & 7) + 1)
        table = data[offset : offset + size]
        offset += size
    while data[offset] == 0x21:  # skip extensions
        offset += 2
        while data[offset]:
            offset += data[offset] + 1
        offset += 1
    if data[offset] != 0x2C:
        raise RuntimeError("Pillow wrote no image descriptor")
    left, top, frame_width, frame_height, image_flags = struct.unpack_from(
        "<HHHHB", data, offset + 1
    )
    if (left, top, frame_width, frame_height) != (0, 0, *indices.shape[::-1]):
        raise RuntimeError("Pillow wrote a partial frame")
    if image_flags & 0x40:
        raise RuntimeError("Pillow wrote an interlaced frame")
    offset += 10
    if image_flags & 0x80:
        size = 3 << ((image_flags & 7) + 1)
        table = data[offset : offset + size]
        offset += size
    if not table:
        raise RuntimeError("Pillow wrote no color table")
    start = offset
    offset += 1  # minimum code size
    while data[offset]:
        offset += data[offset] + 1
    return table, data[start : offset + 1]
