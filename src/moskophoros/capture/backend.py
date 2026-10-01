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
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from moskophoros import fit, sampling, views
from moskophoros.cli import PRESETS, ROOT_MOTION_MODES

INTERNAL_ERROR = 1
BACKEND_ERROR = 5
JOB_SCHEMA = "moskophoros.capture-job/1"
RESULT_SCHEMA = "moskophoros.capture-result/1"
MODES = ("measure", "render")
CUSTOM_VIEW = "custom"
MAX_CELL = 4096
MAX_SUPERSAMPLE = 16

_SHA256 = re.compile(r"[0-9a-f]{64}")
_VERSION = re.compile(r"\d+\.\d+(?:\.\d+)?")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_RGBA = 6


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
class Settings:
    """Resolved settings, as the sheet's `settings` object records them.

    `view` is a preset name or `custom`. `ppm`, `cell` and `ground_px` are
    None until fitting resolves them.
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


@dataclass(frozen=True)
class RootTravel:
    clip: str
    node_index: int
    node_name: str | None
    travel_m: float


@dataclass(frozen=True)
class CaptureResult:
    """A validated result.

    `backend` holds `blender`, and for a render also `renderer` and
    `studio_light`. A measure result has `measurements`, keyed by frame
    address in request order, and `roots`; a render result has `buffers`,
    mapping each address to its absolute buffer paths by name.
    """

    mode: str
    backend: dict[str, str]
    measurements: dict[sampling.FrameAddress, fit.Measurement] | None
    roots: tuple[RootTravel, ...] | None
    buffers: dict[sampling.FrameAddress, dict[str, Path]] | None


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
        expected = sampling.frames(subject, selected_clips, view, settings.fps)
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
        "supersample": settings.supersample,
        "pixels_per_meter": None if ppm is None else float(ppm),
        "cell": None if cell is None else {"width": cell[0], "height": cell[1]},
        "ground_m": dict(zip("xyz", map(float, settings.ground), strict=True)),
        "ground_px": (
            None if ground_px is None else {"x": ground_px[0], "y": ground_px[1]}
        ),
        "root_motion": settings.root_motion,
        "clips": [
            {"name": selected.clip.name, "loop": not selected.one_shot}
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
    if mode == "measure":
        keys.append("roots")
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

    settings = job["settings"]
    scale = settings["supersample"]
    size = (settings["cell"]["width"] * scale, settings["cell"]["height"] * scale)
    buffers = {}
    for ordinal, (record, address) in enumerate(zip(records, addresses, strict=True)):
        where = f"frame {ordinal}"
        named = record["buffers"]
        if not isinstance(named, dict) or "color" not in named:
            raise _Invalid(f"{where} has no color buffer")
        buffers[address] = {
            name: _buffer(phase_dir, path, size, f"{where} {name} buffer")
            for name, path in named.items()
        }
        if named["color"] != f"color/{ordinal:06d}.png":
            raise _Invalid(
                f"{where} color buffer is {named['color']!r}, not "
                f"'color/{ordinal:06d}.png'"
            )
    return CaptureResult(mode, backend, None, None, buffers)


def _backend(value, mode):
    keys = ["blender"] if mode == "measure" else ["blender", "renderer", "studio_light"]
    _object(value, keys, "backend")
    if not isinstance(value["blender"], str) or not _VERSION.fullmatch(
        value["blender"]
    ):
        raise _Invalid(f"backend.blender is not a version: {value['blender']!r}")
    for key in keys[1:]:
        if not isinstance(value[key], str) or not value[key]:
            raise _Invalid(f"backend.{key} is not a name: {value[key]!r}")
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


def _buffer(phase_dir, path, size, where):
    """The absolute path of a valid buffer: a contained 8-bit RGBA PNG."""
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
    if header[24] != 8 or header[25] != _PNG_RGBA:
        raise _Invalid(
            f"{where} {path!r} is not 8-bit RGBA (bit depth {header[24]}, "
            f"color type {header[25]})"
        )
    actual = (int.from_bytes(header[16:20]), int.from_bytes(header[20:24]))
    if actual != size:
        raise _Invalid(
            f"{where} {path!r} is {actual[0]}x{actual[1]}, not {size[0]}x{size[1]}"
        )
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
