"""Stylize: the look of each frame, following design §Stylize.

A stage between capture and cleanup. It depends only on the frames it is
given, never on capture internals, and touches no file or process.

Frames arrive one at a time and may carry named buffers beside their colour;
`identities`, a `sampling.Identities`, is the asset's identity list that a
frame's identity buffer indexes. Without a material `library` the colour
reduction reads only the colour; with one, it also reads the identity and
shade buffers, and each block takes its winning material's ramp entry. Each
reduction returns reduced colour frames, and lets go of a frame, with all its
buffers, before asking for the next.

Independently of the colour reduction, a frame carrying both normal and
depth buffers (`NORMAL`, `DEPTH`) has them reduced to its reduced colour's
pixels, with exactly the colour's coverage, whatever the reduction, palette
or library (design §Normal and depth maps; lighting sheet design D-8, D-15,
D-19, D-27; `imageops.reduce_normal_depth`). The reduced frame carries them
as its only buffers, under `NORMAL_MAP` and `DEPTH_MAP`. A frame carrying
neither is reduced to one carrying no buffers, and one carrying only one of
them is a `ValueError` naming the frame.
"""

import numpy as np

from moskophoros import imageops, materials
from moskophoros.sampling import (
    DEPTH,
    DEPTH_MAP,
    IDENTITY,
    NORMAL,
    NORMAL_MAP,
    SHADE,
    ImageFrame,
)


def plain(
    frames,
    factor,
    palette=None,
    identities=None,
    library=None,
    shade_range=None,
    pixels_per_meter=None,
):
    """Reduce every supersampled frame by `factor`×`factor` blocks.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata and its reduced normal and depth
    maps (see `maps`). With a palette, map the reduced pixels after
    averaging. With a material `library`, blocks whose winning material has a
    ramp take its entry instead (see `materials`).
    """
    materials = _materials(
        factor, palette, identities, library, shade_range, by_mode=False
    )
    result = []
    for frame in frames:
        pixels = imageops.reduce_blocks(frame.pixels, factor)
        if palette is not None:
            pixels = imageops.map_palette(pixels, palette)
        if materials is not None:
            pixels = materials(frame, pixels)
        named = maps(frame, pixels, factor, pixels_per_meter)
        result.append(ImageFrame(frame.address, pixels, frame.metadata, named))
        # Release the capture before asking its iterator for the next array.
        del frame
    return tuple(result)


def mode(
    frames,
    factor,
    palette=None,
    identities=None,
    library=None,
    shade_range=None,
    pixels_per_meter=None,
):
    """Reduce every supersampled frame by `factor`×`factor` blocks, keeping
    each block's most common colour.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata and its reduced normal and depth
    maps (see `maps`). With a palette, map the supersampled pixels before
    voting, so shades mapped to one entry pool their votes. With a material
    `library`, blocks whose winning material has a ramp take its most voted
    entry instead (see `materials`).
    """
    materials = _materials(
        factor, palette, identities, library, shade_range, by_mode=True
    )
    result = []
    for frame in frames:
        pixels = frame.pixels
        if palette is not None:
            pixels = imageops.map_palette(pixels, palette)
        pixels = imageops.reduce_blocks_mode(pixels, factor)
        if materials is not None:
            pixels = materials(frame, pixels)
        named = maps(frame, pixels, factor, pixels_per_meter)
        result.append(ImageFrame(frame.address, pixels, frame.metadata, named))
        del frame
    return tuple(result)


def maps(frame, pixels, factor, pixels_per_meter):
    """The reduced maps of `frame`, whose reduced colour is `pixels`:
    `{NORMAL_MAP: normals, DEPTH_MAP: depths}` from its `NORMAL` and `DEPTH`
    buffers, at the colour's coverage (alpha 255), with depth converted to
    sheet pixels by the sheet's `pixels_per_meter`; `{}` for a frame
    carrying neither. The arrays are new, so the frame's are free once it is
    released."""
    given = [name for name in (NORMAL, DEPTH) if name in frame.buffers]
    if not given:
        return {}
    if len(given) != 2:
        raise ValueError(f"{frame.address}: a frame needs both normal and depth")
    if pixels_per_meter is None:
        raise ValueError("reducing depth needs the sheet's pixels_per_meter")
    normals, depths = imageops.reduce_normal_depth(
        frame.buffers[NORMAL],
        frame.buffers[DEPTH],
        pixels[..., 3] == 255,
        factor,
        pixels_per_meter,
    )
    return {NORMAL_MAP: normals, DEPTH_MAP: depths}


def resolve(library, name):
    """The ramp a material called `name` takes: a tuple of palette indices, or
    `None` for the ordinary look.

    A name resolves in order: its own entry (a ramp, a named ramp it uses, or
    `"ordinary"`), then the library's default ramp, then the ordinary look. A
    generated ramp resolves to its generated indices (material styling design
    D-33), exactly as a hand-listed ramp of those indices would.
    """
    entry = library.materials.get(name)
    if entry is not None:
        if entry.ramp is not None:
            return materials.indices(entry.ramp)
        if entry.uses is not None:
            return materials.indices(library.ramps[entry.uses])
        return None
    if library.default is not None:
        return materials.indices(library.ramps[library.default])
    return None


def _own_range(library, name):
    """The shade range of a material called `name` before the global one: its
    entry's own, else the library's (material styling design D-35, D-36),
    which a material taking the default ramp also takes; None for the
    global."""
    entry = library.materials.get(name)
    if entry is not None and entry.shade is not None and entry.shade.range is not None:
        return entry.shade.range
    if library.shade is not None:
        return library.shade.range
    return None


def _materials(factor, palette, identities, library, shade_range, *, by_mode):
    """The per-frame material step for `library`, or `None` without one.

    The step takes a frame and its reduced ordinary look and returns the look
    with each block that took a ramp entry replaced; it keeps no reference to
    the frame, so the frame's buffers are free once it returns.
    """
    if library is None:
        return None
    if palette is None:
        raise ValueError("a material library needs a palette: its ramps index it")
    if identities is None:
        raise ValueError("a material library needs the asset's identity list")
    if shade_range is None:
        raise ValueError("a material library needs a shade range")
    lo, hi = shade_range
    names = identities.names
    # Materials sharing a name are one identity, the one of lowest index.
    pooled = np.array([names.index(name) for name in names] + [len(names)])
    ramps = tuple(
        resolve(library, name) if pooled[index] == index else None
        for index, name in enumerate(names)
    ) + (None,)
    # Each material's own shade range, where its entry gives one (settings
    # design D-9); the others take the global range.
    ranges = tuple(
        _own_range(library, name) if pooled[index] == index else None
        for index, name in enumerate(names)
    ) + (None,)

    def step(frame, ordinary):
        for name in (IDENTITY, SHADE):
            if name not in frame.buffers:
                raise ValueError(
                    f"{frame.address}: a material library needs the {name} buffer"
                )
        ramped, mapped = imageops.map_ramps(
            frame.pixels,
            frame.buffers[IDENTITY],
            frame.buffers[SHADE],
            factor,
            ramps,
            palette,
            lo,
            hi,
            by_mode=by_mode,
            pool=pooled,
            ranges=ranges,
        )
        ordinary[mapped] = ramped[mapped]
        return ordinary

    return step
