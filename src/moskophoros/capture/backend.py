"""Capture jobs and results, following design §Capture job and result contract.

A job is built from resolved values and checked before it is written: a
malformed job is a programming error (`MalformedJob`, exit classification 1).
A result is accepted only when every rule of the contract holds; anything
else is a backend error (`BackendError`, exit classification 5). Everything
here is pure except reading the result's buffers.
"""

import hashlib
import json
import math
import os
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from moskophoros import fit, imageops, sampling, views

INTERNAL_ERROR = 1
BACKEND_ERROR = 5
JOB_SCHEMA = "moskophoros.capture-job/1"
RESULT_SCHEMA = "moskophoros.capture-result/3"
MODES = ("measure", "render")
CUSTOM_VIEW = "custom"
MAX_CELL = 4096
MAX_SUPERSAMPLE = 16

_SHA256 = re.compile(r"[0-9a-f]{64}")
_VERSION = re.compile(r"\d+\.\d+(?:\.\d+)?")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_RGBA = 6

# The material-ID buffer: red holds a code's high byte, green its low byte,
# blue 0, alpha 255; background is (0, 0, 0, 0). A glTF material of index i
# has code i + 1, and a primitive without a material NO_MATERIAL_ID.
ID_BACKGROUND = 0
NO_MATERIAL_ID = 0xFFFF
MAX_MATERIALS = NO_MATERIAL_ID - 1
# The fields of a render result's `backend.shade`, the fixed shade
# technique, and their checks. The capture values are the job's.
SHADE_FIELDS = {
    "technique": "name",
    "samples_per_pixel": "count",
    "seed": "index",
    "pixel_filter": "name",
    "filter_width_px": "positive",
}
# The colour's technique and its fixed parameters, which a render result's
# `backend.color` reports (alpha design, Capture transport and provenance).
COLOR_FIELDS = {
    "technique": "name",
    "samples_per_pixel": "count",
    "seed": "index",
    "pixel_filter": "name",
    "filter_width_px": "positive",
    "min_transparent_bounces": "index",
    "transparent_max_bounces": "index",
    "pass_alpha_threshold": "positive",
}
# The most samples Blender's Ambient Occlusion node takes; it silently clamps
# more (settings design D-42).
MAX_AO_SAMPLES = 128
# Every render frame's buffers beside its colour, each at
# <name>/NNNNNN.png with the colour's ordinal: the back layer's material ID
# and shade, the front-most surface's normal and depth, and the front
# layer's colour, alpha, material ID and shade (alpha design D-6, D-11,
# D-12, Capture transport and provenance).
FRONT_BUFFERS = ("front_color", "front_alpha", "front_matid", "front_shade")
AUXILIARY_BUFFERS = ("matid", "shade", "normal", "depth", *FRONT_BUFFERS)
# The normal and depth buffers (lighting sheet design D-2, D-10, D-11): 16-bit
# RGBA PNGs, every row unfiltered, with no chunk but IHDR, IDAT and IEND.
# Alpha is SURFACE where the render hit a surface, and every sample is 0
# where it hit none. A normal's components n are stored as
# floor((n + 1) / 2 · 65535 + ½) in red, green and blue, in camera space (+X
# screen right, +Y screen up, +Z toward the viewer). A depth, in meters
# toward the viewer from the ground point's camera depth, is a 32-bit float
# whose big-endian bits are red (the high half) and green (the low half),
# with blue 0.
# The front alpha buffer has the same form: red is the front layer's alpha
# `f` as `q = floor(65535 · f + ½)`, green and blue 0, alpha SURFACE where the
# front layer is present.
WIDE_BUFFERS = ("normal", "depth", "front_alpha")
SURFACE = 0xFFFF
# How far a surface's normal may be from unit length: the 16-bit encoding
# moves it by at most 2.7·10⁻⁵.
NORMAL_TOLERANCE = 1e-3


class MalformedJob(Exception):
    """A job the caller built wrongly: an internal error, exit classification 1."""

    exit_code = INTERNAL_ERROR


class BackendError(Exception):
    """A capture failure: exit classification 5, with any captured output."""

    exit_code = BACKEND_ERROR

    def __init__(self, message, stdout="", stderr=""):
        self.message = message
        self.stdout = stdout
        self.stderr = stderr
        details = [message]
        for name, text in (("stdout", stdout), ("stderr", stderr)):
            if text:
                details.append(f"Blender {name}:\n{text.rstrip()}")
        super().__init__("\n".join(details))


@dataclass(frozen=True)
class Source:
    """The original GLB: an absolute path, its SHA-256 and the scene index."""

    path: Path
    sha256: str
    scene: int


@dataclass(frozen=True)
class MaterialShade:
    """One glTF material's own capture values (settings design D-9, D-36):
    its AO distance and weights, each its library override or the global
    value. AO samples is global only."""

    material: int
    ao_distance_m: float
    occlusion_weight: float
    convexity_weight: float


@dataclass(frozen=True)
class Shade:
    """The capture values of the shade (design §Capture, Shade): the ambient
    occlusion distance and samples, and the weights of occlusion by other
    surfaces and of a surface's own convexity. `materials` holds the values
    of each glTF material that overrides any of them, in material order; every
    other surface takes the global values. The shade range acts after
    capture, so it is not here."""

    ao_distance_m: float
    ao_samples: int
    occlusion_weight: float
    convexity_weight: float
    materials: tuple[MaterialShade, ...] = ()


@dataclass(frozen=True)
class Settings:
    """Resolved settings, as the sheet's `settings` object records them.

    `view` is a preset name or `custom`. `ppm`, `cell` and `ground_px` are
    None until fitting resolves them. `shade` holds the capture values of
    the shade.
    """

    view: str
    pitch: float
    directions: int
    start_angle: float
    model_yaw: float
    fps: float
    supersample: int
    ppm: float | None
    cell: tuple[int, int] | None
    ground: tuple[float, float, float]
    ground_px: tuple[int, int] | None
    root_motion: str
    shade: Shade
    # The global frame count as given: "auto" or a count (settings design
    # D-13, D-31); each selected clip carries its own.
    frames: int | str = sampling.AUTO


@dataclass(frozen=True)
class RootTravel:
    clip: str
    node_index: int
    node_name: str | None
    travel_m: float


@dataclass(frozen=True)
class CaptureResult:
    """A validated result.

    `backend` holds `blender`, and for a render also `renderer`, `color` and
    `shade`. A measure result has `measurements`, keyed by
    frame address in request order, and `roots`; a render result has
    `buffers`, mapping each address to its absolute buffer paths by name, and
    `materials`, mapping each material-ID code to its glTF material index, or
    to None for "no material".
    """

    mode: str
    backend: dict[str, object]
    measurements: dict[sampling.FrameAddress, fit.Measurement] | None
    roots: tuple[RootTravel, ...] | None
    buffers: dict[sampling.FrameAddress, dict[str, Path]] | None
    materials: dict[int, int | None] | None = None


@dataclass(frozen=True)
class MaterialLookup:
    """A render's material-ID codes joined with the asset's identities.

    `identities` is the asset's identity list; `codes` an `int32` array of
    65536 entries giving each code's index into it, `sampling.BACKGROUND` for
    the background code, and `UNKNOWN_CODE` for codes not in the table.
    """

    identities: sampling.Identities
    codes: object


UNKNOWN_CODE = -2


def canonical_json(document):
    """`document` as canonical JSON bytes: sorted keys, compact, ASCII only."""
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def job_sha256(job):
    return hashlib.sha256(canonical_json(job)).hexdigest()


def build_job(mode, source, subject, settings, selected_clips, frames, output_dir):
    """Build a `mode` job, raising `MalformedJob` if the inputs disagree.

    `selected_clips` are `gltf.SelectedClip`s in sheet order, and `frames`
    the `sampling.Frame`s requested, which must be exactly those the clips
    and settings give. In a measure job, `pixels_per_meter`, `cell` and
    `ground_px` are null; a render job needs all three resolved.
    """
    if mode not in MODES:
        raise MalformedJob(f"mode must be one of {MODES}, got {mode!r}")
    _check_source(source)
    if not isinstance(subject, str) or subject != Path(source.path).stem:
        raise MalformedJob(
            f"subject {subject!r} is not the source's stem {Path(source.path).stem!r}"
        )
    _check_settings(settings, mode)
    selected_clips = tuple(selected_clips)
    _check_clips(selected_clips)
    frames = tuple(frames)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    try:
        expected = sampling.frames(
            subject, selected_clips, view, settings.fps, settings.frames
        )
    except ValueError as error:
        raise MalformedJob(str(error)) from None
    if frames != expected:
        raise MalformedJob(
            "the frames are not the ones the selected clips and settings give"
        )
    if not Path(output_dir).is_absolute():
        raise MalformedJob(f"output_dir must be absolute, got {str(output_dir)!r}")

    job = {
        "schema": JOB_SCHEMA,
        "mode": mode,
        "source": {
            "path": str(source.path),
            "sha256": source.sha256,
            "scene": source.scene,
        },
        "subject": subject,
        "variant": sampling.VARIANT,
        "settings": settings_document(settings, selected_clips, mode == "render"),
        "clips": [_clip_document(selected.clip) for selected in selected_clips],
        "frames": [_frame_document(frame) for frame in frames],
        "output_dir": str(output_dir),
    }
    try:
        canonical_json(job)
    except ValueError as error:
        raise MalformedJob(f"the job is not valid JSON: {error}") from None
    return job


def settings_document(settings, selected_clips, fitted=True):
    """The sheet's `settings` object. Without `fitted`, the scale, cell and
    ground pixel are null, as in a measure job."""
    cell = settings.cell if fitted else None
    ground_px = settings.ground_px if fitted else None
    ppm = settings.ppm if fitted else None
    return {
        "view": {
            "preset": settings.view,
            "projection": "orthographic",
            "pitch_deg": float(settings.pitch),
            "directions": settings.directions,
            "start_angle_deg": float(settings.start_angle),
        },
        "model_yaw_deg": float(settings.model_yaw),
        "fps": float(settings.fps),
        "frames": settings.frames,
        "supersample": settings.supersample,
        "pixels_per_meter": None if ppm is None else float(ppm),
        "cell": None if cell is None else {"width": cell[0], "height": cell[1]},
        "ground_m": dict(zip("xyz", map(float, settings.ground), strict=True)),
        "ground_px": (
            None if ground_px is None else {"x": ground_px[0], "y": ground_px[1]}
        ),
        "root_motion": settings.root_motion,
        "shade": {
            "ao_distance_m": float(settings.shade.ao_distance_m),
            "ao_samples": settings.shade.ao_samples,
            "occlusion_weight": float(settings.shade.occlusion_weight),
            "convexity_weight": float(settings.shade.convexity_weight),
            "materials": [
                {
                    "material": own.material,
                    "ao_distance_m": float(own.ao_distance_m),
                    "occlusion_weight": float(own.occlusion_weight),
                    "convexity_weight": float(own.convexity_weight),
                }
                for own in settings.shade.materials
            ],
        },
        "clips": [
            {
                "name": selected.clip.name,
                "loop": not selected.one_shot,
                "frames": selected.frames,
            }
            for selected in selected_clips
        ],
    }


def address_document(address):
    return {
        "subject": address.subject,
        "variant": address.variant,
        "clip": address.clip,
        "direction": address.direction,
        "time_s": float(address.time_s),
    }


def _clip_document(clip):
    return {
        "animation_index": clip.animation_index,
        "name": clip.name,
        "t0_s": float(clip.t0),
        "t1_s": float(clip.t1),
        "roots": [
            {"node_index": root.node_index, "node_name": root.node_name}
            for root in clip.roots
        ],
    }


def _frame_document(frame):
    return {
        "address": address_document(frame.address),
        "index": frame.index,
        "angle_deg": float(frame.angle),
    }


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    """A finite number. Integers of any size are finite; testing one as a
    float could overflow."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _check_source(source):
    if not Path(source.path).is_absolute():
        raise MalformedJob(f"the source path must be absolute, got {source.path!r}")
    if not isinstance(source.sha256, str) or not _SHA256.fullmatch(source.sha256):
        raise MalformedJob(f"the source sha256 is not a digest: {source.sha256!r}")
    if not _is_int(source.scene) or source.scene < 0:
        raise MalformedJob(f"the scene index is invalid: {source.scene!r}")


def _check_settings(settings, mode):
    # Imported here because the command in `cli` imports this module.
    from moskophoros.cli import PRESETS, ROOT_MOTION_MODES

    problems = []
    if settings.view not in (*PRESETS, CUSTOM_VIEW):
        problems.append(f"view {settings.view!r}")
    if not (_is_number(settings.pitch) and 0 <= settings.pitch <= 90):
        problems.append(f"pitch {settings.pitch!r}")
    if not (_is_int(settings.directions) and 1 <= settings.directions <= 64):
        problems.append(f"directions {settings.directions!r}")
    for name in ("start_angle", "model_yaw"):
        if not _is_number(getattr(settings, name)):
            problems.append(f"{name} {getattr(settings, name)!r}")
    if not (_is_number(settings.fps) and settings.fps > 0):
        problems.append(f"fps {settings.fps!r}")
    if not (
        _is_int(settings.supersample) and 1 <= settings.supersample <= MAX_SUPERSAMPLE
    ):
        problems.append(f"supersample {settings.supersample!r}")
    if not (
        isinstance(settings.ground, tuple)
        and len(settings.ground) == 3
        and all(map(_is_number, settings.ground))
    ):
        problems.append(f"ground {settings.ground!r}")
    if settings.root_motion not in ROOT_MOTION_MODES:
        problems.append(f"root_motion {settings.root_motion!r}")
    problems += _shade_problems(settings.shade)
    if not _is_frame_count(settings.frames):
        problems.append(f"frames {settings.frames!r}")
    fitted = {
        "ppm": settings.ppm is None or (_is_number(settings.ppm) and settings.ppm > 0),
        "cell": settings.cell is None or _is_pair(settings.cell, 1, MAX_CELL),
        "ground_px": settings.ground_px is None or _is_pair(settings.ground_px, 0),
    }
    problems += [
        f"{name} {getattr(settings, name)!r}" for name, ok in fitted.items() if not ok
    ]
    if mode == "render":
        problems += [
            f"{name} is not resolved"
            for name in fitted
            if getattr(settings, name) is None
        ]
    if problems:
        raise MalformedJob("invalid settings: " + "; ".join(problems))


def _is_pair(value, low, high=None):
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and all(
            _is_int(item) and item >= low and (high is None or item <= high)
            for item in value
        )
    )


def _check_clips(selected_clips):
    if not selected_clips:
        raise MalformedJob("no clips are selected")
    names = [selected.clip.name for selected in selected_clips]
    if len(set(names)) != len(names):
        raise MalformedJob(f"a clip is selected twice: {names!r}")
    for selected in selected_clips:
        clip = selected.clip
        where = f"clip {clip.name!r}"
        if not isinstance(clip.name, str) or not clip.name:
            raise MalformedJob(f"{where} has no name")
        if not (_is_number(clip.t0) and _is_number(clip.t1) and clip.t0 <= clip.t1):
            raise MalformedJob(f"{where} has an invalid range {clip.t0!r}..{clip.t1!r}")
        if clip.animation_index is None:
            if clip.t0 != 0 or clip.t1 != 0 or clip.roots:
                raise MalformedJob(
                    f"{where} has no animation index, but is not the static clip"
                )
        elif not _is_int(clip.animation_index) or clip.animation_index < 0:
            raise MalformedJob(f"{where} has animation index {clip.animation_index!r}")
        indices = [root.node_index for root in clip.roots]
        if len(set(indices)) != len(indices) or not all(
            _is_int(index) and index >= 0 for index in indices
        ):
            raise MalformedJob(f"{where} has invalid root node indices {indices!r}")
        for root in clip.roots:
            if root.node_name is not None and not isinstance(root.node_name, str):
                raise MalformedJob(f"{where} has root name {root.node_name!r}")
        if selected.frames is not None and not _is_frame_count(selected.frames):
            raise MalformedJob(f"{where} has frame count {selected.frames!r}")


def _is_frame_count(value):
    """A frame count as given: `"auto"` or a whole number of 1 or more."""
    return value == sampling.AUTO or (_is_int(value) and value >= 1)


# Results


class _Invalid(Exception):
    pass


def validate_result(job, phase_dir, text):
    """Validate `text`, a `result.json` read from `phase_dir`, against `job`.

    Returns a `CaptureResult`, or raises `BackendError` naming the first
    rule broken.
    """
    mode = job["mode"]
    try:
        document = _strict_json(text)
        return _result(job, Path(phase_dir), document)
    except _Invalid as error:
        raise BackendError(f"the {mode} result is invalid: {error}") from None


def _strict_json(data):
    def pairs(items):
        document = {}
        for key, value in items:
            if key in document:
                raise _Invalid(f"duplicate key {key!r}")
            document[key] = value
        return document

    def constant(name):
        raise _Invalid(f"non-finite number {name}")

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise _Invalid(f"non-finite number {text}")
        return value

    try:
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        return json.loads(
            text, object_pairs_hook=pairs, parse_constant=constant, parse_float=number
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise _Invalid(f"not JSON: {error}") from None


def _object(value, keys, where):
    if not isinstance(value, dict):
        raise _Invalid(f"{where} is not an object")
    missing = [key for key in keys if key not in value]
    unknown = [key for key in value if key not in keys]
    if missing:
        raise _Invalid(f"{where} is missing {', '.join(missing)}")
    if unknown:
        raise _Invalid(f"{where} has unknown {', '.join(unknown)}")
    return value


def _nonnegative(value, where):
    if not _is_number(value) or value < 0:
        raise _Invalid(f"{where} is not a finite number 0 or more: {value!r}")
    return value


def _result(job, phase_dir, document):
    mode = job["mode"]
    keys = ["schema", "mode", "job_sha256", "source_sha256", "backend", "frames"]
    keys.append("roots" if mode == "measure" else "materials")
    _object(document, keys, "the result")
    if document["schema"] != RESULT_SCHEMA:
        raise _Invalid(f"schema is {document['schema']!r}, not {RESULT_SCHEMA!r}")
    if document["mode"] != mode:
        raise _Invalid(f"mode is {document['mode']!r}, but the job's is {mode!r}")
    if document["job_sha256"] != job_sha256(job):
        raise _Invalid("job_sha256 does not match the submitted job")
    if document["source_sha256"] != job["source"]["sha256"]:
        raise _Invalid("source_sha256 does not match the job's source")
    backend = _backend(document["backend"], mode)

    requested = job["frames"]
    records = document["frames"]
    if not isinstance(records, list):
        raise _Invalid("frames is not a list")
    if len(records) != len(requested):
        raise _Invalid(
            f"frames has {len(records)} records for {len(requested)} requested"
        )
    addresses = []
    for ordinal, (record, frame) in enumerate(zip(records, requested, strict=True)):
        where = f"frame {ordinal}"
        fields = ["address", "bounds_m", "height_m"] if mode == "measure" else None
        _object(record, fields or ["address", "buffers"], where)
        if not _same_address(record["address"], frame["address"]):
            raise _Invalid(
                f"{where} has address {record['address']!r}, but the request's is "
                f"{frame['address']!r}"
            )
        addresses.append(_address(frame["address"]))

    if mode == "measure":
        measurements = {}
        for ordinal, (record, address) in enumerate(
            zip(records, addresses, strict=True)
        ):
            where = f"frame {ordinal}"
            bounds = _object(
                record["bounds_m"], ["L", "R", "U", "D"], f"{where} bounds_m"
            )
            for side in "LRUD":
                _nonnegative(bounds[side], f"{where} bounds_m.{side}")
            measurements[address] = fit.Measurement(
                fit.Bounds(bounds["L"], bounds["R"], bounds["U"], bounds["D"]),
                _nonnegative(record["height_m"], f"{where} height_m"),
            )
        roots = _roots(document["roots"], job)
        return CaptureResult(mode, backend, measurements, roots, None)

    materials = _materials(document["materials"])
    settings = job["settings"]
    scale = settings["supersample"]
    size = (settings["cell"]["width"] * scale, settings["cell"]["height"] * scale)
    buffers = {}
    for ordinal, (record, address) in enumerate(zip(records, addresses, strict=True)):
        where = f"frame {ordinal}"
        named = record["buffers"]
        for name in ("color", *AUXILIARY_BUFFERS):
            if not isinstance(named, dict) or name not in named:
                raise _Invalid(f"{where} has no {name} buffer")
        buffers[address] = {
            name: _buffer(
                phase_dir,
                path,
                size,
                f"{where} {name} buffer",
                bits=16 if name in WIDE_BUFFERS else 8,
            )
            for name, path in named.items()
        }
        for name in ("color", *AUXILIARY_BUFFERS):
            if named[name] != f"{name}/{ordinal:06d}.png":
                raise _Invalid(
                    f"{where} {name} buffer is {named[name]!r}, not "
                    f"'{name}/{ordinal:06d}.png'"
                )
        _auxiliary(buffers[address], materials, where)
    return CaptureResult(mode, backend, None, None, buffers, materials)


def _materials(entries):
    """The material table: {code: glTF material index or None}."""
    if not isinstance(entries, list):
        raise _Invalid("materials is not a list")
    table = {}
    for ordinal, entry in enumerate(entries):
        where = f"materials entry {ordinal}"
        _object(entry, ["id", "material"], where)
        code, material = entry["id"], entry["material"]
        if not _is_int(code) or not ID_BACKGROUND <= code <= NO_MATERIAL_ID:
            raise _Invalid(f"{where} id is not a material-ID code: {code!r}")
        if code == ID_BACKGROUND:
            raise _Invalid(f"{where} maps the background code {ID_BACKGROUND}")
        if code in table:
            raise _Invalid(f"{where} repeats code {code}")
        if material is not None and not (_is_int(material) and material >= 0):
            raise _Invalid(f"{where} material is not a material index: {material!r}")
        table[code] = material
    return table


def _auxiliary(paths, materials, where):
    """Check a frame's buffers against each other and against the material
    table (design §Capture job and result contract): each layer's colour,
    material ID and shade on exactly the same pixels, the front alpha exactly
    where the front colour is, and the normal and depth exactly where either
    layer is."""
    ids = _layer(paths, "", materials, where)
    front_ids = _layer(paths, "front_", materials, where)
    _front_alpha(paths["front_alpha"], front_ids, where)
    covered = (ids[..., 3] == 255) | (front_ids[..., 3] == 255)
    for name in ("normal", "depth"):
        _surfaces(name, paths[name], covered, ids, front_ids, where)
    for prefix, layer_ids in (("", ids), ("front_", front_ids)):
        _colour(paths, prefix, layer_ids, where)


def _layer(paths, prefix, materials, where):
    """Check one layer's material-ID and shade buffers, the back's (`prefix`
    "") or the front's ("front_"); return its material-ID pixels."""
    label = prefix.replace("_", " ")
    ids = _pixels(paths[f"{prefix}matid"])
    shade = _pixels(paths[f"{prefix}shade"])
    problems = (
        (
            ~np.isin(ids[..., 3], (0, 255))
            | ((ids[..., 3] == 0) & ids[..., :3].any(axis=-1))
            | ((ids[..., 3] == 255) & (ids[..., 2] != 0))
            | ((ids[..., 3] == 255) & ~ids[..., :2].any(axis=-1)),
            label + "material-ID pixel {} is {}, not an encoded value",
            ids,
        ),
        (
            (shade[..., 0] != shade[..., 1]) | (shade[..., 1] != shade[..., 2]),
            label + "shade pixel {} is {}, whose red, green and blue differ",
            shade,
        ),
        (
            ~np.isin(shade[..., 3], (0, 255)),
            label + "shade pixel {} is {}, whose alpha is neither 0 nor 255",
            shade,
        ),
        (
            ((ids[..., 3] == 0) & shade.any(axis=-1))
            | ((ids[..., 3] == 255) & (shade[..., 3] != 255)),
            label + "shade pixel {} is {}, but the material-ID pixel there is {}",
            shade,
        ),
    )
    _refuse_first(problems, ids, where)
    codes = ids[..., 0].astype(np.int32) << 8 | ids[..., 1]
    used = np.unique(codes[ids[..., 3] == 255])
    unknown = [int(code) for code in used if int(code) not in materials]
    if unknown:
        raise _Invalid(
            f"{where}: {label}material-ID code {unknown[0]} is not in the table"
        )
    return ids


def _colour(paths, prefix, ids, where):
    """Check one layer's colour buffer: it covers exactly the surfaces the
    layer's material ID holds."""
    label = prefix.replace("_", " ")
    colour_name = label + "colour"
    color = _pixels(paths[f"{prefix}color"])
    problems = (
        (
            ~np.isin(color[..., 3], (0, 255)),
            colour_name + " pixel {} is {}, whose alpha is neither 0 nor 255",
            color,
        ),
        (
            (color[..., 3] == 0) & color.any(axis=-1),
            colour_name + " pixel {} is {}, no surface, but not (0, 0, 0, 0)",
            color,
        ),
        (
            (color[..., 3] == 255) & (ids[..., 3] != 255),
            colour_name
            + f" pixel {{}} is {{}}, a surface, but the {label}material-ID pixel there is {{}}",
            color,
        ),
        (
            (color[..., 3] == 0) & (ids[..., 3] != 0),
            colour_name
            + f" pixel {{}} is {{}}, no surface, but the {label}material-ID pixel there is {{}}",
            color,
        ),
    )
    _refuse_first(problems, ids, where)


def _front_alpha(path, front_ids, where):
    """Check a frame's front alpha buffer: its encoding, and its coverage
    against the front layer's material ID."""
    try:
        samples = read_wide_png(path)
    except ValueError as error:
        raise _Invalid(f"{where} front_alpha buffer {error}") from None
    alpha = samples[..., 3]
    surface = alpha == SURFACE
    present = front_ids[..., 3] == 255
    problems = (
        (
            ~np.isin(alpha, (0, SURFACE))
            | (~surface & samples.any(axis=-1))
            | (surface & samples[..., 1:3].any(axis=-1)),
            "is {}, not an encoded value",
        ),
        (
            surface & ~present,
            "is {}, a surface, but the front material-ID pixel there is {}",
        ),
        (
            ~surface & present,
            "is {}, no surface, but the front material-ID pixel there is {}",
        ),
    )
    for wrong, message in problems:
        if wrong.any():
            y, x = (int(i) for i in np.argwhere(wrong)[0])
            raise _Invalid(
                f"{where}: front_alpha pixel {(x, y)} "
                + message.format(
                    tuple(int(v) for v in samples[y, x]),
                    tuple(int(v) for v in front_ids[y, x]),
                )
            )


def _refuse_first(problems, ids, where):
    """Refuse the first of `problems`, `(wrong, message, image)` triples, that
    any pixel shows, naming the pixel, its value and the material ID's."""
    for wrong, message, image in problems:
        if wrong.any():
            y, x = (int(i) for i in np.argwhere(wrong)[0])
            values = tuple(int(v) for v in image[y, x])
            raise _Invalid(
                f"{where}: "
                + message.format((x, y), values, tuple(int(v) for v in ids[y, x]))
            )


def _surfaces(name, path, covered, ids, front_ids, where):
    """Check a frame's normal or depth buffer: its encoding, its coverage
    against the layers', and its values. It describes the front-most surface
    that is not a hole, so it holds a surface exactly where either layer
    does (alpha design D-11)."""
    try:
        samples = read_wide_png(path)
    except ValueError as error:
        raise _Invalid(f"{where} {name} buffer {error}") from None
    alpha = samples[..., 3]
    surface = alpha == SURFACE
    if name == "normal":
        values = decode_normal(samples)
        bad = surface & ~unit_normals(values)
        problem = "not a unit normal"
    else:
        values = decode_depth(samples)
        bad = surface & ((samples[..., 2] != 0) | ~np.isfinite(values))
        problem = "not a finite depth"
    problems = (
        (
            ~np.isin(alpha, (0, SURFACE)) | (~surface & samples.any(axis=-1)),
            "is {}, not an encoded value",
        ),
        (
            surface & ~covered,
            "is {}, a surface, but neither layer shows one there (material-ID "
            "pixels {} and front {})",
        ),
        (
            ~surface & covered,
            "is {}, no surface, but a layer shows one there (material-ID "
            "pixels {} and front {})",
        ),
        (bad, "is {}, " + problem),
    )
    for wrong, message in problems:
        if wrong.any():
            y, x = (int(i) for i in np.argwhere(wrong)[0])
            raise _Invalid(
                f"{where}: {name} pixel {(x, y)} "
                + message.format(
                    tuple(int(v) for v in samples[y, x]),
                    tuple(int(v) for v in ids[y, x]),
                    tuple(int(v) for v in front_ids[y, x]),
                )
            )


def read_wide_png(path):
    """The samples of a normal or depth buffer as a `uint16` array of shape
    `(height, width, 4)`: a 16-bit RGBA PNG, non-interlaced, with every row
    unfiltered and no chunk but IHDR, IDAT and IEND, as the capture writes
    it. Raises `ValueError` for any other file, and lets `OSError` from
    reading it propagate."""
    data = Path(path).read_bytes()
    if data[:8] != _PNG_SIGNATURE:
        raise ValueError("is not a PNG")
    at, chunks = 8, []
    while at < len(data):
        if at + 12 > len(data):
            raise ValueError("is truncated")
        (length,) = struct.unpack_from(">I", data, at)
        kind = data[at + 4 : at + 8]
        body = data[at + 8 : at + 8 + length]
        if len(body) != length or at + 12 + length > len(data):
            raise ValueError("is truncated")
        (crc,) = struct.unpack_from(">I", data, at + 8 + length)
        if zlib.crc32(kind + body) != crc:
            raise ValueError(f"has a corrupt {kind!r} chunk")
        chunks.append((kind, body))
        at += 12 + length
    kinds = [kind for kind, _ in chunks]
    if (
        len(kinds) < 3
        or kinds[0] != b"IHDR"
        or kinds[-1] != b"IEND"
        or set(kinds[1:-1]) != {b"IDAT"}
    ):
        raise ValueError(f"has the chunks {kinds}, not IHDR, IDAT and IEND only")
    header = chunks[0][1]
    if len(header) != 13:
        raise ValueError("has a malformed IHDR")
    width, height, bits, color, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", header
    )
    if (bits, color, compression, filtering, interlace) != (16, _PNG_RGBA, 0, 0, 0):
        raise ValueError(
            f"is not a non-interlaced 16-bit RGBA PNG (bit depth {bits}, "
            f"color type {color}, interlace {interlace})"
        )
    try:
        raw = zlib.decompress(b"".join(body for _, body in chunks[1:-1]))
    except zlib.error as error:
        raise ValueError(f"does not decompress: {error}") from None
    stride = 1 + width * 8
    if len(raw) != height * stride:
        raise ValueError(f"holds {len(raw)} bytes, not {height * stride}")
    rows = np.frombuffer(raw, dtype=np.uint8).reshape(height, stride)
    if rows[:, 0].any():
        row = int(np.argmax(rows[:, 0] != 0))
        raise ValueError(f"filters row {row}; every row must be unfiltered")
    return rows[:, 1:].view(">u2").reshape(height, width, 4).astype(np.uint16)


def decode_normal(samples):
    """A normal buffer's samples as a `float32` array of shape `(height,
    width, 3)`: each surface pixel's camera-space normal, and (0, 0, 0)
    where there is no surface."""
    normal = samples[..., :3].astype(np.float64) * (2 / 0xFFFF) - 1
    normal[samples[..., 3] != SURFACE] = 0.0
    return normal.astype(np.float32)


def decode_depth(samples):
    """A depth buffer's samples as a `float32` array of shape `(height,
    width)`: each surface pixel's depth in meters, positive toward the viewer
    from the ground point, and NaN where there is no surface."""
    bits = samples[..., 0].astype(np.uint32) << 16 | samples[..., 1]
    depth = bits.view(np.float32).copy()
    depth[samples[..., 3] != SURFACE] = np.nan
    return depth


def unit_normals(normals):
    """Where `normals`, an array of shape `(..., 3)`, holds finite vectors of
    unit length within `NORMAL_TOLERANCE`."""
    length = np.linalg.norm(np.asarray(normals, dtype=np.float64), axis=-1)
    with np.errstate(invalid="ignore"):
        return np.isfinite(length) & (np.abs(length - 1) <= NORMAL_TOLERANCE)


def _pixels(path):
    """The pixels of a buffer `_buffer` has accepted, whose size it checked,
    so Pillow's guard against large images is not needed."""
    limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(path, formats=["PNG"]) as image:
            return np.asarray(image, dtype=np.uint8)
    finally:
        Image.MAX_IMAGE_PIXELS = limit


def identities(primitive_materials):
    """The asset's identity list from its `gltf.PrimitiveMaterial` records,
    and {glTF material index: identity index} for every material they use.

    The list holds each distinct name of an `OPAQUE` or `MASK` material, in
    order of its lowest material index; a `BLEND` material (or any other
    alpha mode), an unnamed one and a missing one are the no-identity class.
    """
    eligible = sorted(
        {
            (record.material_index, record.name)
            for record in primitive_materials
            if record.material_index is not None
            and record.name is not None
            and record.alpha_mode in ("OPAQUE", "MASK")
        }
    )
    names = []
    for _, name in eligible:
        if name not in names:
            names.append(name)
    listed = sampling.Identities(tuple(names))
    indices = {
        record.material_index: listed.no_identity
        for record in primitive_materials
        if record.material_index is not None
    }
    for material_index, name in eligible:
        indices[material_index] = names.index(name)
    return listed, indices


def material_lookup(result, subject):
    """Join a render `result`'s material table with `subject`'s materials.

    Raises `BackendError` if the table names a material the model does not
    have.
    """
    listed, indices = identities(subject.primitive_materials)
    codes = np.full(NO_MATERIAL_ID + 1, UNKNOWN_CODE, dtype=np.int32)
    codes[ID_BACKGROUND] = sampling.BACKGROUND
    for code, material in sorted(result.materials.items()):
        if material is not None and material >= subject.material_count:
            raise BackendError(
                f"the render result is invalid: material-ID code {code} maps "
                f"material {material}, but the model has {subject.material_count}"
            )
        # A material no primitive of the subject uses never shows.
        codes[code] = indices.get(material, listed.no_identity)
    return MaterialLookup(listed, codes)


def decode_frame(paths, lookup):
    """A frame's identity and shade arrays (design §Frames into stylize) from
    its validated `matid` and `shade` buffers in `paths`."""
    ids = imageops.load_png(paths["matid"])
    identity = lookup.codes[ids[..., 0].astype(np.int32) << 8 | ids[..., 1]]
    identity[ids[..., 3] == 0] = sampling.BACKGROUND
    del ids
    if (identity == UNKNOWN_CODE).any():
        raise BackendError(
            f"the render result is invalid: {paths['matid']} holds a code that "
            "is not in the material table"
        )
    shade = imageops.load_png(paths["shade"])[..., 0].copy()
    return identity, shade


def decode_front(paths, lookup):
    """A frame's front arrays (design §Frames into stylize) from its
    validated front buffers in `paths`: the front colour's pixels, the front
    alpha `q` as `uint16` (0 where the layer is absent), the layer's presence
    as `bool`, and its identity (`int32`, through `lookup`) and shade
    (`uint8`) arrays."""
    pixels = imageops.load_png(paths["front_color"])
    present = pixels[..., 3] == 255
    try:
        samples = read_wide_png(paths["front_alpha"])
    except ValueError as error:
        raise BackendError(
            f"the render result is invalid: {paths['front_alpha']} {error}"
        ) from None
    alpha = samples[..., 0].copy()
    del samples
    identity, shade = decode_frame(
        {"matid": paths["front_matid"], "shade": paths["front_shade"]}, lookup
    )
    return pixels, alpha, present, identity, shade


def decode_normal_depth(paths):
    """A frame's normal and depth arrays (design §Frames into stylize) from
    its validated `normal` and `depth` buffers in `paths`."""
    decoded = []
    for name, decode in (("normal", decode_normal), ("depth", decode_depth)):
        try:
            decoded.append(decode(read_wide_png(paths[name])))
        except ValueError as error:
            raise BackendError(
                f"the render result is invalid: {paths[name]} {error}"
            ) from None
    return tuple(decoded)


def _backend(value, mode):
    keys = ["blender"]
    if mode == "render":
        keys += ["renderer", "color", "shade"]
    _object(value, keys, "backend")
    if not isinstance(value["blender"], str) or not _VERSION.fullmatch(
        value["blender"]
    ):
        raise _Invalid(f"backend.blender is not a version: {value['blender']!r}")
    if mode == "render" and (
        not isinstance(value["renderer"], str) or not value["renderer"]
    ):
        raise _Invalid(f"backend.renderer is not a name: {value['renderer']!r}")
    result = dict(value)
    if mode == "render":
        result["color"] = _technique(value["color"], COLOR_FIELDS, "backend.color")
        result["shade"] = _technique(value["shade"], SHADE_FIELDS, "backend.shade")
    return result


def _shade_problems(shade):
    """What is wrong with the capture values `shade`: the distance finite and
    greater than 0, the samples 1 to `MAX_AO_SAMPLES`, the weights finite and
    0 or greater."""
    if not isinstance(shade, Shade):
        return [f"shade {shade!r}"]
    problems = []
    if not (_is_number(shade.ao_distance_m) and shade.ao_distance_m > 0):
        problems.append(f"shade.ao_distance_m {shade.ao_distance_m!r}")
    if not (_is_int(shade.ao_samples) and 1 <= shade.ao_samples <= MAX_AO_SAMPLES):
        problems.append(f"shade.ao_samples {shade.ao_samples!r}")
    for name in ("occlusion_weight", "convexity_weight"):
        value = getattr(shade, name)
        if not (_is_number(value) and value >= 0):
            problems.append(f"shade.{name} {value!r}")
    if not isinstance(shade.materials, tuple) or not all(
        isinstance(own, MaterialShade) for own in shade.materials
    ):
        return [*problems, f"shade.materials {shade.materials!r}"]
    indices = [own.material for own in shade.materials]
    if not all(_is_int(index) and 0 <= index < MAX_MATERIALS for index in indices) or (
        indices != sorted(set(indices))
    ):
        problems.append(
            f"shade.materials indices {indices!r} are not distinct, ascending "
            "glTF material indices"
        )
    for own in shade.materials:
        where = f"shade.materials[{own.material!r}]"
        if not (_is_number(own.ao_distance_m) and own.ao_distance_m > 0):
            problems.append(f"{where}.ao_distance_m {own.ao_distance_m!r}")
        for name in ("occlusion_weight", "convexity_weight"):
            value = getattr(own, name)
            if not (_is_number(value) and value >= 0):
                problems.append(f"{where}.{name} {value!r}")
    return problems


def _technique(value, fields, where):
    """A fixed technique record of `fields`, each of its kind."""
    _object(value, list(fields), where)
    checks = {
        "name": lambda v: isinstance(v, str) and bool(v),
        "count": lambda v: _is_int(v) and v >= 1,
        "index": lambda v: _is_int(v) and v >= 0,
        "positive": lambda v: _is_number(v) and v > 0,
        "number": _is_number,
    }
    for key, kind in fields.items():
        if not checks[kind](value[key]):
            raise _Invalid(f"{where}.{key} is invalid: {value[key]!r}")
    return dict(value)


def _same_address(value, requested):
    if not isinstance(value, dict) or set(value) != set(requested):
        return False
    if not _is_int(value["direction"]) or not _is_number(value["time_s"]):
        return False
    return all(value[key] == requested[key] for key in requested)


def _address(document):
    return sampling.FrameAddress(
        document["subject"],
        document["variant"],
        document["clip"],
        document["direction"],
        document["time_s"],
    )


def _roots(entries, job):
    requested = [
        (clip["name"], root["node_index"], root["node_name"])
        for clip in job["clips"]
        for root in clip["roots"]
    ]
    if not isinstance(entries, list):
        raise _Invalid("roots is not a list")
    if len(entries) != len(requested):
        raise _Invalid(
            f"roots has {len(entries)} entries for {len(requested)} requested "
            "clip/root pairs"
        )
    roots = []
    for ordinal, (entry, (clip, index, name)) in enumerate(
        zip(entries, requested, strict=True)
    ):
        where = f"root {ordinal}"
        _object(entry, ["clip", "node_index", "node_name", "travel_m"], where)
        given = (entry["clip"], entry["node_index"], entry["node_name"])
        if not _is_int(entry["node_index"]) or given != (clip, index, name):
            raise _Invalid(
                f"{where} is {given!r}, but the request's is {(clip, index, name)!r}"
            )
        travel = _nonnegative(entry["travel_m"], f"{where} travel_m")
        roots.append(RootTravel(clip, index, name, travel))
    return tuple(roots)


def _buffer(phase_dir, path, size, where, bits=8):
    """The absolute path of a valid buffer: a contained RGBA PNG of `bits` per
    sample. An 8-bit buffer is decoded here; a 16-bit one, a normal or depth
    buffer, by `_surfaces`."""
    if not isinstance(path, str) or not path:
        raise _Invalid(f"{where} path is not a path: {path!r}")
    relative = Path(path)
    if relative.is_absolute() or os.path.isabs(path):
        raise _Invalid(f"{where} path {path!r} is absolute")
    if ".." in relative.parts:
        raise _Invalid(f"{where} path {path!r} has a parent reference")
    if "\0" in path:
        raise _Invalid(f"{where} path {path!r} contains a NUL character")
    try:
        root = phase_dir.resolve()
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root):
            raise _Invalid(f"{where} path {path!r} escapes the phase directory")
        if not resolved.exists():
            raise _Invalid(f"{where} {path!r} does not exist")
        if not resolved.is_file():
            raise _Invalid(f"{where} {path!r} is not a regular file")
        with resolved.open("rb") as handle:
            header = handle.read(26)
    except (OSError, ValueError, RuntimeError) as error:
        raise _Invalid(f"{where} {path!r} cannot be read: {error}") from None
    if len(header) < 26 or header[:8] != _PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise _Invalid(f"{where} {path!r} is not a PNG")
    if header[24] != bits or header[25] != _PNG_RGBA:
        raise _Invalid(
            f"{where} {path!r} is not {bits}-bit RGBA (bit depth {header[24]}, "
            f"color type {header[25]})"
        )
    actual = (int.from_bytes(header[16:20]), int.from_bytes(header[20:24]))
    if actual != size:
        raise _Invalid(
            f"{where} {path!r} is {actual[0]}x{actual[1]}, not {size[0]}x{size[1]}"
        )
    if bits == 16:
        return resolved
    # The header already gave the exact expected size, so Pillow's guard
    # against unexpectedly large images would only refuse a large legitimate
    # cell, such as 2048 pixels supersampled 8 times.
    limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(resolved, formats=["PNG"]) as image:
            image.load()
            if image.mode != "RGBA" or image.size != size:
                raise _Invalid(f"{where} {path!r} decodes as {image.mode} {image.size}")
    except _Invalid:
        raise
    except Exception as error:
        # The bytes come from Blender, not from this tool: whatever Pillow's
        # decoder raises on them, such as SyntaxError or IndexError for a
        # malformed chunk, means the buffer is invalid.
        raise _Invalid(f"{where} {path!r} does not decode: {error!r}") from None
    finally:
        Image.MAX_IMAGE_PIXELS = limit
    return resolved
