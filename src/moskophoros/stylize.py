"""Stylize: the look of each frame, following design §Stylize.

A stage between capture and cleanup. It depends only on the frames it is
given, never on capture internals, and touches no file or process.

Frames arrive one at a time and may carry named buffers beside their colour;
`identities`, a `sampling.Identities`, is the asset's identity list that a
frame's identity buffer indexes. Without a material `library` the reductions
read only the colour. With one, each block also takes its winning material's
ramp entry. Each returns ordinary reduced colour frames carrying no buffers,
and lets go of a frame, with all its buffers, before asking for the next.
"""

import numpy as np

from moskophoros import imageops
from moskophoros.sampling import IDENTITY, SHADE, ImageFrame


def plain(
    frames, factor, palette=None, identities=None, library=None, shade_range=None
):
    """Reduce every supersampled frame by `factor`×`factor` blocks.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata. With a palette, map the reduced
    pixels after averaging. With a material `library`, blocks whose winning
    material has a ramp take its entry instead (see `materials`).
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
        result.append(ImageFrame(frame.address, pixels, frame.metadata))
        # Release the capture before asking its iterator for the next array.
        del frame
    return tuple(result)


def mode(frames, factor, palette=None, identities=None, library=None, shade_range=None):
    """Reduce every supersampled frame by `factor`×`factor` blocks, keeping
    each block's most common colour.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata. With a palette, map the supersampled
    pixels before voting, so shades mapped to one entry pool their votes. With
    a material `library`, blocks whose winning material has a ramp take its
    most voted entry instead (see `materials`).
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
        result.append(ImageFrame(frame.address, pixels, frame.metadata))
        del frame
    return tuple(result)


def resolve(library, name):
    """The ramp a material called `name` takes: a tuple of palette indices, or
    `None` for the ordinary look.

    A name resolves in order: its own entry (a ramp, a named ramp it uses, or
    `"ordinary"`), then the library's default ramp, then the ordinary look.
    """
    entry = library.materials.get(name)
    if entry is not None:
        if entry.ramp is not None:
            return entry.ramp
        if entry.uses is not None:
            return library.ramps[entry.uses]
        return None
    if library.default is not None:
        return library.ramps[library.default]
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
        )
        ordinary[mapped] = ramped[mapped]
        return ordinary

    return step
