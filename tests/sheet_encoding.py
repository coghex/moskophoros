"""The sheet, its maps, its previews and its manifest from reduced frames, for
the tests that look at what a positional run writes without Blender.

It takes what the command takes after capture and runs the stages the command
runs: the export settings and request plan, the positional output plan,
`exportimages.encode` and `manifest.encode`. `encode` returns the sheet and
maps as the files the command writes them, `previews` and `lit_previews` the
flat and lit previews of the same run.
"""

from pathlib import Path
from types import SimpleNamespace

from moskophoros import (
    export,
    exportimages,
    exportsettings,
    manifest,
    outputs,
    views,
)


def _plan(settings, subject, selected_clips):
    view = views.View(settings.directions, settings.start_angle, settings.model_yaw)
    selected = tuple(selected_clips)
    own = {
        "fps": settings.fps,
        "frames": settings.frames,
        "clips": {chosen.clip.name: {"frames": chosen.frames} for chosen in selected},
    }
    resolved = exportsettings.resolve(
        [
            exportsettings.Source(exportsettings.DEFAULTS, "the defaults", {}),
            exportsettings.Source(exportsettings.OPTION, "the test", own),
        ]
    )
    chosen = exportsettings.request(resolved, subject, selected, view)
    names = outputs.resolve_names(
        chosen.selected, view, subject=subject, directory=False
    )
    return resolved, chosen.plan, names


def _images(
    frames,
    resolved,
    request,
    names,
    settings,
    image_path,
    normals,
    depth,
    previews,
    light,
):
    lit = previews and light.position is not None
    layout = outputs.plan_outputs(
        request,
        names,
        resolved,
        destination=outputs.Positional(Path(image_path).name),
        normals=normals,
        depth=depth,
        previews=previews,
        lit=lit,
    )
    return exportimages.encode(
        frames,
        request=request,
        output_plan=layout,
        settings=settings,
        formats=resolved.formats,
        atlas_padding=resolved.atlas_padding,
        normals=normals,
        depth=depth,
        previews=previews,
        light=light,
    )


def settings_record(
    settings, subject, selected_clips, style, *, shade_range, **options
):
    """The manifest's `settings` object of a run: `options` are the keyword
    arguments `manifest.settings_record` takes after the shade range."""
    resolved, request, _ = _plan(settings, subject, selected_clips)
    return manifest.settings_record(
        settings, resolved, request, style, shade_range=shade_range, **options
    )


def _preview(artifact):
    return SimpleNamespace(
        clip=artifact.clip, gif=artifact.data, warnings=artifact.warnings
    )


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
    light=export.NO_LIGHT,
    ramp=export.DEFAULT_RAMP,
    shading=None,
):
    """The run's files: `png`, `normal` and `depth` the sheet and its maps
    (None when not written), `json` the manifest, `flat` and `lit` the
    previews' GIFs in clip order, and `encoded` and `document` the
    `exportimages.Encoded` and the manifest as a dict.

    `frames`, `settings`, `style` and the rest are as the command has them
    after capture, cleanup and fitting."""
    resolved, request, names = _plan(settings, subject, selected_clips)
    encoded = _images(
        frames,
        resolved,
        request,
        names,
        settings,
        image_path,
        normals,
        depth,
        previews,
        light,
    )
    data = manifest.encode(
        generator=generator,
        source=source,
        subject=subject,
        settings=settings,
        style=style,
        resolved=resolved,
        request=request,
        names=names,
        encoded=encoded,
        shade_range=shade_range,
        previews=previews,
        normals=normals,
        depth=depth,
        light=light,
        ramp=ramp,
        shading=shading,
    )

    def image(kind, channel):
        found = [a for a in encoded.artifacts if (a.kind, a.channel) == (kind, channel)]
        return found[0].data if found else None

    return SimpleNamespace(
        png=image(outputs.SHEET, outputs.COLOR),
        normal=image(outputs.SHEET, outputs.NORMAL),
        depth=image(outputs.SHEET, outputs.DEPTH),
        json=data,
        flat=tuple(
            a.data
            for a in encoded.artifacts
            if (a.kind, a.channel) == (outputs.PREVIEW, outputs.FLAT)
        ),
        lit=tuple(
            a.data
            for a in encoded.artifacts
            if (a.kind, a.channel) == (outputs.PREVIEW, outputs.LIT)
        ),
        encoded=encoded,
        document=manifest.decode(data).document,
    )


def previews(frames, *, subject, settings, selected_clips):
    """Each selected clip's flat preview, with its `clip`, `gif` and
    `warnings`, from `frames` that need hold no maps."""
    resolved, request, names = _plan(settings, subject, selected_clips)
    encoded = _images(
        frames,
        resolved,
        request,
        names,
        settings,
        "hero.png",
        False,
        False,
        True,
        export.NO_LIGHT,
    )
    return tuple(_preview(a) for a in encoded.artifacts if a.channel == outputs.FLAT)


def lit_previews(frames, *, subject, settings, selected_clips, light):
    """Each selected clip's preview lit by `light`, from `frames` that carry
    a normal and a depth map."""
    if light.position is None:
        raise ValueError("lit previews need a light with a position")
    resolved, request, names = _plan(settings, subject, selected_clips)
    encoded = _images(
        frames,
        resolved,
        request,
        names,
        settings,
        "hero.png",
        False,
        False,
        True,
        light,
    )
    return tuple(_preview(a) for a in encoded.artifacts if a.channel == outputs.LIT)


# Reading a manifest document


def find(document, kind, channel, clip=None):
    """The position and record of the first artifact of `kind` and `channel`
    (and `clip`, when given) in a manifest `document`, or `(None, None)`."""
    for position, artifact in enumerate(document["artifacts"]):
        if (artifact["kind"], artifact["channel"]) == (kind, channel) and (
            clip is None or artifact.get("clip") == clip
        ):
            return position, artifact
    return None, None


def path_of(document, kind, channel, clip=None):
    """The path of the artifact `find` finds, or None."""
    return (
        find(document, kind, channel, clip)[1]
        and find(document, kind, channel, clip)[1]["path"]
    )


def cell(document, entry, channel="color"):
    """The location of the frame record `entry` in the sheet's `channel`
    image: its `x`, `y`, `w` and `h`."""
    position, _ = find(document, outputs.SHEET, channel)
    (place,) = [p for p in entry["locations"] if p["artifact"] == position]
    return place
