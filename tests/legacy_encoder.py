"""A frozen copy of the sheet encoder that `exportimages.encode` replaced, for
comparison only (export design D-3).

These are the image-making parts of `export.encode`, `export.previews` and
`export.lit_previews` as they were at commit 4a22102519, the last one before
the positional command switched to `moskophoros.export/1`: the sheet and its
normal and depth maps laid out row by row, and the flat and lit preview GIFs.
The metadata part, the sheet JSON, is not copied: nothing here can write a
sheet description. The copy takes the shared helpers (`export.encode_png`,
`export.preview_gif` and the rest) from `export`, so a byte that differs is a
difference in layout or arithmetic, and a comparison of bytes holds on every
platform whatever its zlib: both sides compress with the same library.

Nothing is to be changed here to follow the encoder it is compared with; the
point of the copy is that it does not move.
"""

from types import SimpleNamespace

import numpy as np

from moskophoros import export, imageops, sampling, views


def sheet(frames, *, subject, settings, selected_clips, normals=True, depth=False):
    """The sheet's `png` and its `normal` and `depth` maps' bytes (None when
    not written), from the reduced `frames` of `selected_clips`."""
    selected_clips = tuple(selected_clips)
    view = views.View(settings.directions, settings.start_angle, settings.model_yaw)
    directions = views.directions(view)
    requested = sampling.frames(
        subject, selected_clips, view, settings.fps, settings.frames
    )
    width, height = settings.cell
    frames = tuple(frames)
    pixels = export.pixels_by_address(frames, requested, (height, width, 4))
    normal_maps = (
        export.maps_by_address(frames, sampling.NORMAL_MAP, (height, width, 3))
        if normals
        else None
    )
    depth_maps = (
        export.maps_by_address(frames, sampling.DEPTH_MAP, (height, width))
        if depth
        else None
    )
    if depth:
        export.check_depths(requested, pixels, depth_maps, settings.ppm)

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
            codes = np.full((height, width), export.NO_SURFACE, dtype=np.uint16)
            codes[covered] = export.encode_depth(depth_maps[address][covered])
            depth_image[y : y + height, x : x + width] = codes
    return SimpleNamespace(
        png=export.encode_png(image),
        normal=None if normal_image is None else export.encode_png(normal_image),
        depth=None if depth_image is None else export.encode_png(depth_image),
    )


def previews(frames, *, subject, settings, selected_clips, lit=False):
    """Each selected clip's animated GIF preview, in sheet order, as
    `SimpleNamespace(clip, gif, warnings)`. With `lit` the frames are lit ones
    and the warning says so."""
    width, height = settings.cell
    selected_clips = tuple(selected_clips)
    view = views.View(settings.directions, settings.start_angle, settings.model_yaw)
    count = len(views.directions(view))
    preview_width = count * width * export.PREVIEW_SCALE
    plans = []
    for selected in selected_clips:
        name = selected.clip.name
        if preview_width > export.MAX_PREVIEW_WIDTH:
            raise export.UsageError(
                f"the preview of clip {name!r} would be {preview_width} pixels "
                f"wide, over GIF's limit of {export.MAX_PREVIEW_WIDTH} pixels"
            )
        timing = sampling.sample(selected, settings.fps, settings.frames)
        delays = export.preview_delays_ms(
            timing.frame_duration, timing.frame_count, selected.one_shot
        )
        longest = max(delays)
        if longest > export.MAX_PREVIEW_DELAY_MS:
            raise export.UsageError(
                f"a frame of clip {name!r}'s preview would last {longest} ms, "
                f"over GIF's limit of {export.MAX_PREVIEW_DELAY_MS} ms"
            )
        plans.append((name, timing.times, delays))

    requested = sampling.frames(
        subject, selected_clips, view, settings.fps, settings.frames
    )
    pixels = export.pixels_by_address(frames, requested, (height, width, 4))
    result = []
    for name, times, delays in plans:
        rows = (
            np.concatenate(
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
            for time_s in times
        )
        gif, reduced = export.preview_gif(rows, delays)
        result.append(
            SimpleNamespace(
                clip=name,
                gif=gif,
                warnings=export.reduction_warnings(name, reduced, lit),
            )
        )
    return tuple(result)


def lit_previews(frames, *, subject, settings, selected_clips, light):
    """Each selected clip's preview lit by `light`, in sheet order."""
    selected_clips = tuple(selected_clips)
    view = views.View(settings.directions, settings.start_angle, settings.model_yaw)
    requested = sampling.frames(
        subject, selected_clips, view, settings.fps, settings.frames
    )
    width, height = settings.cell
    frames = tuple(frames)
    pixels = export.pixels_by_address(frames, requested, (height, width, 4))
    normals = export.maps_by_address(frames, sampling.NORMAL_MAP, (height, width, 3))
    depths = export.maps_by_address(frames, sampling.DEPTH_MAP, (height, width))
    export.check_depths(requested, pixels, depths, settings.ppm)
    lit = []
    for frame in frames:
        address = frame.address
        covered = pixels[address][..., 3] > 0
        normal_bytes = np.zeros((height, width, 3), dtype=np.uint8)
        normal_bytes[covered] = imageops.encode_normal(normals[address][covered])
        codes = np.zeros((height, width), dtype=np.uint16)
        codes[covered] = export.encode_depth(depths[address][covered])
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
        lit, subject=subject, settings=settings, selected_clips=selected_clips, lit=True
    )
