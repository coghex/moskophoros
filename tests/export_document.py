"""A complete `moskophoros.export/1` document around hand-written settings,
for the tests that exercise `--settings-from` with settings of their own.

`document` takes a `settings` object in the shape a sheet's settings had
before the export arc (no export members, clips with only a name, a loop flag
and a frame count), adds the new members at their inactive defaults, and
makes every other member from the real writer: the artifacts, directions,
clips and frames the settings imply, and the fingerprint their generator,
source digest and settings hash to. Settings that cannot be written, such as
a deliberately invalid field, get a structurally valid placeholder instead, so
the problem a test looks for is the settings' own and never a structural one
caused by an incomplete fixture.
"""

import copy
import functools
import json

import numpy as np
from manifest_fixture import GENERATOR, SHA, SOURCE
from shading import DEFAULT_SHADE

from moskophoros import (
    cli,
    export,
    exportimages,
    exportsettings,
    manifest,
    outputs,
    views,
)
from moskophoros.capture.backend import Settings
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import DEPTH_MAP, NORMAL_MAP, ImageFrame

# The members the export arc added to the settings, at their inactive defaults.
EXPORT_DEFAULTS = {
    "stored_directions": "all",
    "direction_names": [],
    "mirrors": [],
    "export": {
        "formats": ["sheet"],
        "frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
        "atlas_path": "atlases/{clip}{map}.png",
        "sheet_path": "sheet{map}.png",
        "atlas_padding": 0,
    },
}
CLIP_DEFAULTS = {
    "fps": None,
    "stored_directions": None,
    "mirrors": None,
    "output_name": None,
}
PLACEHOLDER = {
    "artifacts": [],
    "directions": [
        {"index": 0, "angle_deg": 0.0, "label": None, "output_name": "direction-000"}
    ],
    "clips": [
        {
            "name": "placeholder",
            "loop": True,
            "duration_s": 0.0,
            "frame_count": 1,
            "frame_duration_s": 1.0,
            "time_scale": 1.0,
            "output_name": "placeholder",
            "fps": 1.0,
            "stored_directions": [0],
            "mirrors": [],
        }
    ],
    "frames": [],
}


def completed(settings):
    """`settings` with the members of the export arc added at their inactive
    defaults where it lacks them. A shape that is not a settings object is
    left as it is."""
    settings = copy.deepcopy(settings)
    if not isinstance(settings, dict):
        return settings
    for name, value in EXPORT_DEFAULTS.items():
        settings.setdefault(name, copy.deepcopy(value))
    clips = settings.get("clips")
    if isinstance(clips, list):
        for entry in clips:
            if isinstance(entry, dict):
                for name, value in CLIP_DEFAULTS.items():
                    entry.setdefault(name, value)
    return settings


def _frames(request, shape):
    zeros = np.zeros(shape)
    return [
        ImageFrame(
            frame.address,
            np.zeros(shape + (4,), dtype=np.uint8),
            buffers={NORMAL_MAP: np.zeros(shape + (3,)), DEPTH_MAP: zeros},
        )
        for frame in request.frames
    ]


def _derived(settings, subject, durations):
    """The artifacts, directions, clips and frames of `settings` (already
    completed), made by the writer."""
    view = settings["view"]
    cell = settings["cell"]
    ground = settings["ground_px"]
    light = settings["light"]
    capture = Settings(
        view="custom",
        direction=tuple(settings["camera"]["direction"]),
        directions=view["directions"],
        start_angle=view["start_angle_deg"],
        model_yaw=settings["model_yaw_deg"],
        fps=settings["fps"],
        supersample=settings["supersample"],
        ppm=settings["pixels_per_meter"],
        cell=(cell["width"], cell["height"]),
        ground=tuple(settings["ground_m"][axis] for axis in "xyz"),
        ground_px=(ground["x"], ground["y"]),
        root_motion=settings["root_motion"],
        frames=settings["frames"],
        shade=DEFAULT_SHADE,
    )
    ring = views.View(capture.directions, capture.start_angle, capture.model_yaw)
    selected = tuple(
        SelectedClip(
            Clip(position, entry["name"], 0.0, durations.get(entry["name"], 1.0), ()),
            not entry["loop"],
            entry["frames"],
        )
        for position, entry in enumerate(settings["clips"])
    )
    own = {
        "fps": settings["fps"],
        "frames": settings["frames"],
        "clips": {chosen.clip.name: {"frames": chosen.frames} for chosen in selected},
    }
    resolved = exportsettings.resolve(
        [
            exportsettings.Source(exportsettings.DEFAULTS, "the defaults", {}),
            exportsettings.Source(exportsettings.OPTION, "the test", own),
        ]
    )
    chosen = exportsettings.request(resolved, subject, selected, ring)
    names = outputs.resolve_names(
        chosen.selected, ring, subject=subject, directory=False
    )
    shown = light["position"]
    lamp = export.Light(
        None if shown is None else tuple(shown), light["intensity"], light["ambient"]
    )
    previews, normals, depth = (
        settings[key] for key in ("previews", "normals", "depth")
    )
    lit = previews and lamp.position is not None
    layout = outputs.plan_outputs(
        chosen.plan,
        names,
        resolved,
        destination=outputs.Positional("old.png"),
        normals=normals,
        depth=depth,
        previews=previews,
        lit=lit,
    )
    encoded = exportimages.encode(
        _frames(chosen.plan, (capture.cell[1], capture.cell[0])),
        request=chosen.plan,
        output_plan=layout,
        settings=capture,
        formats=resolved.formats,
        previews=previews,
        normals=normals,
        depth=depth,
        light=lamp,
    )
    built = manifest.build(
        generator=GENERATOR,
        source=SOURCE,
        subject=subject,
        settings=capture,
        style=settings["style"],
        resolved=resolved,
        request=chosen.plan,
        names=names,
        encoded=encoded,
        shade_range=settings["shade"]["range"],
        previews=previews,
        normals=normals,
        depth=depth,
        light=lamp,
    )
    return {name: built[name] for name in PLACEHOLDER}


@functools.cache
def _cached(text, subject, durations):
    return _derived(json.loads(text), subject, dict(durations))


def document(settings, *, subject="hero", durations=None):
    """The complete document around `settings`: a dict in serialized order.

    `durations` maps clip names to their source length in seconds, one second
    for any not named."""
    settings = completed(settings)
    try:
        if _problems(settings):
            raise ValueError("settings the reader refuses")
        derived = copy.deepcopy(
            _cached(
                json.dumps(settings, sort_keys=True),
                subject,
                tuple(sorted((durations or {}).items())),
            )
        )
    except Exception:
        derived = copy.deepcopy(PLACEHOLDER)
    return {
        "schema": manifest.SCHEMA,
        "generator": GENERATOR,
        "source": {"file": "hero.glb", "sha256": SHA},
        "subject": subject,
        "variant": "default",
        "settings": settings,
        "fingerprint": _fingerprint(settings),
        **derived,
    }


def refit(contents, settings):
    """The manifest `contents` with its settings replaced by `settings` (in
    the sheet-era shape or the complete one), the records they imply made
    again, and its generator, source and subject kept. A clip the contents do
    not record is one second long."""
    durations = {clip["name"]: clip["duration_s"] for clip in contents["clips"]}
    made = document(settings, subject=contents["subject"], durations=durations)
    made["generator"] = contents["generator"]
    made["source"] = contents["source"]
    made["fingerprint"] = _fingerprint(
        made["settings"], contents["generator"], contents["source"]["sha256"]
    )
    return made


def _problems(settings):
    """The problems the reader finds in `settings` themselves."""
    problems = []
    checked = cli._check_shape(manifest._SHAPE, settings, "settings", problems)
    if not problems:
        cli._style(checked["style"], problems)
    return problems


def _fingerprint(settings, generator=GENERATOR, sha=SHA):
    try:
        return export.fingerprint(generator, settings, sha)
    except (TypeError, ValueError):
        return "sha256:" + "0" * 64
