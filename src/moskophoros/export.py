"""The sheet PNG, its `moskophoros.sheet/2` JSON and the animated previews,
following design §Export.

`encode` lays the plain frames out on the sheet, describes them and returns
both files' bytes; `write` writes them where the caller says. `previews`
returns each clip's GIF, `preview_paths` names them and `write_previews`
writes them. Everything except the writers is pure, and the same inputs give
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

import numpy as np
import PIL
from PIL import Image

import moskophoros
from moskophoros import sampling, views
from moskophoros.capture.backend import settings_document

SCHEMA = "moskophoros.sheet/2"
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


class UsageError(Exception):
    """Settings whose previews GIF cannot represent: exit classification 2."""

    exit_code = USAGE_ERROR


@dataclass(frozen=True)
class Sheet:
    """The encoded sheet: `png` and `json` bytes, ready to write."""

    png: bytes
    json: bytes


@dataclass(frozen=True)
class Preview:
    """One clip's encoded preview, with any warning for the command to print."""

    clip: str
    gif: bytes
    warnings: tuple[str, ...]


def generator(backend):
    """The sheet's `generator`: this tool and its libraries, and the Blender
    version, renderer and studio light a render result's `backend` reports."""
    missing = [
        key for key in ("blender", "renderer", "studio_light") if key not in backend
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
        "studio_light": backend["studio_light"],
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


def sheet_settings(settings, selected_clips, style):
    """The sheet's `settings` object: the capture job's settings, fitted, with
    `style` recorded as given just before `clips`.

    `style` is the record the command resolved, written and fingerprinted as
    it is: export does not know which reductions or palettes exist.
    """
    document = settings_document(settings, selected_clips)
    clips = document.pop("clips")
    return document | {"style": style, "clips": clips}


def encode(
    frames, *, generator, source, subject, settings, style, selected_clips, image_path
):
    """Lay out and describe the sheet, returning its PNG and JSON bytes.

    `frames` are the plain `sampling.ImageFrame`s, exactly one for each
    frame the selected clips and resolved `settings` request, each the cell
    size, in any order. `generator` comes from `generator()`, `source` is the
    capture `Source`, `style` is the style record `sheet_settings` takes,
    `selected_clips` are `gltf.SelectedClip`s in selection order, and
    `image_path` is where the PNG will be written; only its base name is
    recorded, as is the source's.

    Raises `ValueError` for frames that are missing, extra, duplicated or
    the wrong size, or for unfitted settings: these are internal errors.
    """
    if settings.ppm is None or settings.cell is None or settings.ground_px is None:
        raise ValueError("the settings are not fitted: scale, cell and ground pixel")
    selected_clips = tuple(selected_clips)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    directions = views.directions(view)
    requested = sampling.frames(subject, selected_clips, view, settings.fps)
    width, height = settings.cell
    pixels = _pixels_by_address(frames, requested, (height, width, 4))

    row_of_clip = {selected.clip.name: c for c, selected in enumerate(selected_clips)}
    samplings = [sampling.sample(selected, settings.fps) for selected in selected_clips]
    columns = max(s.frame_count for s in samplings)
    rows = len(selected_clips) * len(directions)
    image = np.zeros((rows * height, columns * width, 4), dtype=np.uint8)
    frame_documents = []
    for frame in requested:
        address = frame.address
        row = row_of_clip[address.clip] * len(directions) + address.direction
        x, y = frame.index * width, row * height
        image[y : y + height, x : x + width] = pixels[address]
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

    settings_doc = sheet_settings(settings, selected_clips, style)
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
            }
            for selected, s in zip(selected_clips, samplings, strict=True)
        ],
        "frames": frame_documents,
    }
    return Sheet(_png(image), _json(description))


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


def _png(image):
    """An 8-bit RGBA PNG with no text or time chunks."""
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()


def _json(description):
    text = json.dumps(description, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def previews(frames, *, subject, settings, selected_clips):
    """Each selected clip's animated GIF preview, in sheet order.

    `frames` are the plain frames `encode` takes, with alpha 0 or 255. GIF
    frame `k` shows sample `k` of every direction side by side in index
    order, enlarged `PREVIEW_SCALE` times, with transparent pixels on a solid
    `PREVIEW_BACKGROUND`. A frame keeps its exact colors when it has at most
    256 of them; otherwise it is reduced to 256 without dithering and the
    preview warns. Each frame lasts the clip's frame duration in whole
    centiseconds, rounded half up and at least 20 ms; a one-shot clip holds
    its last frame 500 ms longer. The GIF loops forever.

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
        timing = sampling.sample(selected, settings.fps)
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

    requested = sampling.frames(subject, selected_clips, view, settings.fps)
    pixels = _pixels_by_address(frames, requested, (height, width, 4))
    for address, array in pixels.items():
        if not np.isin(array[..., 3], (0, 255)).all():
            raise ValueError(f"the frame at {address} has alpha other than 0 or 255")

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
            rgb = row[..., :3].copy()
            rgb[transparent] = PREVIEW_BACKGROUND
            indices, palette, frame_reduced = _palette_frame(rgb, transparent)
            reduced |= frame_reduced
            indices = indices.repeat(PREVIEW_SCALE, axis=0).repeat(
                PREVIEW_SCALE, axis=1
            )
            images.append((indices, palette))
        warnings = ()
        if reduced:
            warnings = (
                f"clip {name!r}'s preview has frames with more than 256 colors, "
                "reduced to 256 without dithering",
            )
        result.append(Preview(name, _gif(images, delays), warnings))
    return tuple(result)


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
    the exact background, which every transparent pixel keeps.
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
