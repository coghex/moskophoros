"""Complete generated exports for the manifest tests: a fitted request, its
frames made in memory, the encoded artifacts and the manifest bytes, with
every stage the real run uses and none that needs Blender."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
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
from moskophoros import settings as layered
from moskophoros.capture.backend import Settings, Source
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import DEPTH_MAP, NORMAL_MAP, ImageFrame

SHA = "ab" * 32
W, H = 3, 2
RING8 = views.View(8, 0.0)
GENERATOR = {
    "tool": "moskophoros",
    "version": "0.1.0",
    "python": "3.13.15",
    "numpy": "2.5.3",
    "pillow": "12.3.0",
    "blender": "5.2.2",
    "renderer": "cycles",
    "color": {
        "technique": "cycles-flat-emission",
        "samples_per_pixel": 1,
        "seed": 0,
        "pixel_filter": "BOX",
        "filter_width_px": 0.01,
        "min_transparent_bounces": 64,
        "transparent_max_bounces": 64,
        "pass_alpha_threshold": 9.313225746154785e-10,
    },
    "shade": {
        "technique": "cycles-ambient-occlusion",
        "samples_per_pixel": 1,
        "seed": 0,
        "pixel_filter": "BOX",
        "filter_width_px": 0.01,
    },
}
PLAIN = {"reduce": "plain", "edges": "hard", "palette": None, "materials": None}
SOURCE = Source(Path("/work/models/hero.glb"), SHA, 0)
LIGHT = export.Light(position=(5.0, 7.0, 20.0), intensity=0.9, ambient=0.2)
RANGE = (84, 191)


def clip(index, name, t1=1.0, one_shot=False, count=None, t0=0.0):
    return SelectedClip(Clip(index, name, t0, t1, ()), one_shot, count)


WALK = clip(0, "walk", count=2)
IDLE = clip(1, "idle", count=1)


def read(text):
    return layered.read_bytes(text.encode(), source="f.yaml", directory="/s")


def sources(text):
    """The layers a settings text makes, as a reused layer."""
    return [exportsettings.Source(exportsettings.REUSED, "the settings", read(text))]


def settings_for(resolved, view=RING8, cell=(W, H), ground_px=(1, 2), **changes):
    return (
        Settings(
            view="custom",
            direction=views.pitch_direction(0.0),
            directions=view.directions,
            start_angle=view.start_angle,
            model_yaw=view.model_yaw,
            fps=resolved.fps,
            supersample=4,
            ppm=4.0,
            cell=cell,
            ground=(0.0, 0.0, 0.0),
            ground_px=ground_px,
            root_motion="error",
            frames=resolved.frames,
            shade=DEFAULT_SHADE,
        )
        if not changes
        else replace(settings_for(resolved, view, cell, ground_px), **changes)
    )


def frames_for(request, seed=1, shape=(H, W)):
    """Distinct random cells: alpha 0, 1, 77 and 255 mixed, unit normals and
    depths in sixteenths."""
    rng = np.random.default_rng(seed)
    frames = []
    for frame in request.frames:
        pixels = rng.integers(0, 256, shape + (4,), dtype=np.uint8)
        pixels[..., 3] = rng.choice([0, 0, 1, 77, 255], size=shape)
        normals = rng.normal(size=shape + (3,))
        normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
        depths = np.round(rng.uniform(-100, 100, shape) * 16) / 16
        depths[pixels[..., 3] == 0] = 5000.0
        frames.append(
            ImageFrame(
                frame.address, pixels, buffers={NORMAL_MAP: normals, DEPTH_MAP: depths}
            )
        )
    return frames


def export_for(
    text="{}\n",
    *,
    clips=(WALK, IDLE),
    view=RING8,
    destination=None,
    normals=True,
    depth=False,
    previews=True,
    light=export.NO_LIGHT,
    style=PLAIN,
    cell=(W, H),
    ground_px=(1, 2),
    subject="hero",
    source=SOURCE,
    generator=GENERATOR,
    seed=1,
    shade_range=RANGE,
    encode=True,
):
    """Everything an export is made of, from the settings `text`."""
    resolved = exportsettings.resolve(sources(text))
    chosen = exportsettings.request(resolved, subject, clips, view)
    settings = settings_for(resolved, view, cell, ground_px)
    lit = previews and light.position is not None
    destination = destination or (
        outputs.Directory()
        if "sheet" != resolved.formats[0] or len(resolved.formats) > 1
        else outputs.Positional("hero.png")
    )
    directory = isinstance(destination, outputs.Directory)
    names = outputs.resolve_names(
        chosen.selected,
        view,
        subject=subject,
        clip_aliases={n: c.output_name for n, c in resolved.clips.items()},
        direction_aliases=dict(resolved.direction_names),
        directory=directory,
    )
    output_plan = outputs.plan_outputs(
        chosen.plan,
        names,
        resolved,
        destination=destination,
        normals=normals,
        depth=depth,
        previews=previews,
        lit=lit,
    )
    frames = frames_for(chosen.plan, seed, (cell[1], cell[0]))
    encoded = exportimages.encode(
        frames,
        request=chosen.plan,
        output_plan=output_plan,
        settings=settings,
        formats=resolved.formats,
        atlas_padding=resolved.atlas_padding,
        normals=normals,
        depth=depth,
        previews=previews,
        light=light,
    )
    options = dict(
        generator=generator,
        source=source,
        subject=subject,
        settings=settings,
        style=style,
        resolved=resolved,
        request=chosen.plan,
        names=names,
        encoded=encoded,
        shade_range=shade_range,
        previews=previews,
        normals=normals,
        depth=depth,
        light=light,
    )
    result = SimpleNamespace(
        options=options,
        resolved=resolved,
        request=chosen.plan,
        names=names,
        encoded=encoded,
        frames=frames,
        settings=settings,
        output_plan=output_plan,
    )
    if encode:
        result.data = manifest.encode(**options)
        result.document = json.loads(result.data)
    return result


def decode(data, label="the manifest"):
    return manifest.decode(data, label)


def style_of(loaded):
    """The style record a loaded manifest makes, as the command writes it."""
    reused = loaded.reused
    return cli.style_document(
        reused.reduce, reused.edges, reused.palette, reused.materials
    )


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def seal(document):
    """Give `document` the fingerprint its generator, settings and source
    digest hash to, computed here and not by the writer."""
    import hashlib

    document["fingerprint"] = (
        "sha256:"
        + hashlib.sha256(
            canonical(
                {
                    "generator": document["generator"],
                    "settings": document["settings"],
                    "source": {"sha256": document["source"]["sha256"]},
                }
            )
        ).hexdigest()
    )
    return document


def dump(document):
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
