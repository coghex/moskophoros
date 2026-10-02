"""The sheet PNG and its `moskophoros.sheet/1` JSON, following design §Export.

`encode` lays the plain frames out on the sheet, describes them and returns
both files' bytes; `write` writes them where the caller says. Everything
except `write` is pure, and the same inputs give byte-identical output
(design §Reproducibility).
"""

import hashlib
import io
import json
import platform
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

import moskophoros
from moskophoros import sampling, views
from moskophoros.capture.backend import settings_document

SCHEMA = "moskophoros.sheet/1"
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Sheet:
    """The encoded sheet: `png` and `json` bytes, ready to write."""

    png: bytes
    json: bytes


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


def encode(frames, *, generator, source, subject, settings, selected_clips, image_path):
    """Lay out and describe the sheet, returning its PNG and JSON bytes.

    `frames` are the plain `sampling.ImageFrame`s, exactly one for each frame
    the selected clips and resolved `settings` request, each the cell size,
    in any order. `generator` comes from `generator()`, `source` is the
    capture `Source`, `selected_clips` are `gltf.SelectedClip`s in selection
    order, and `image_path` is where the PNG will be written; only its base
    name is recorded, as is the source's.

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

    settings_doc = settings_document(settings, selected_clips)
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
