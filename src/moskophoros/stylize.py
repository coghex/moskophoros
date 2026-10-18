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

Each output pixel's coverage and alpha are decided once, from its block,
under the `edges` rule (`imageops.block_alpha`; alpha design D-4, D-9): the
reductions and the material step reuse their colour, vote and band rules and
keep that alpha, whatever the palette or library.

A frame whose front layer is present somewhere (`FRONT_PRESENT`; alpha
design D-6, D-12, D-14) is reduced by the numerical reference's steps 1 to
4 (`layered`): each supersample's front weight and the back's transmitted
weight decide the alpha, each layer is reduced with its own weights, the
front is composited over the back in linear colour, and with a palette the
composite's colour snaps to it. A frame without one is reduced exactly as
above.

Independently of the colour reduction, a frame carrying both normal and
depth buffers (`NORMAL`, `DEPTH`) has them reduced to its reduced colour's
pixels, with exactly the colour's coverage, alpha above 0, whatever the
reduction, palette or library (design §Normal and depth maps; lighting sheet design D-8, D-15,
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
    FRONT_ALPHA,
    FRONT_COLOR,
    FRONT_IDENTITY,
    FRONT_PRESENT,
    FRONT_SHADE,
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
    edges=imageops.EDGES[0],
):
    """Reduce every supersampled frame by `factor`×`factor` blocks, each
    output pixel's alpha decided by `edges` (`imageops.reduce_blocks`).

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata and its reduced normal and depth
    maps (see `maps`). With a palette, map the reduced pixels after
    averaging; alpha is never snapped. With a material `library`, blocks
    whose winning material has a ramp take its entry instead (see
    `materials`).
    """
    materials = _materials(
        factor, palette, identities, library, shade_range, by_mode=False, edges=edges
    )
    result = []
    for frame in frames:
        if _has_front(frame):
            pixels = layered(frame, factor, palette, materials, edges, by_mode=False)
        else:
            pixels = imageops.reduce_blocks(frame.pixels, factor, edges)
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
    edges=imageops.EDGES[0],
):
    """Reduce every supersampled frame by `factor`×`factor` blocks, keeping
    each block's most common colour, each output pixel's alpha decided by
    `edges` (`imageops.reduce_blocks_mode`).

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata and its reduced normal and depth
    maps (see `maps`). With a palette, map the supersampled pixels before
    voting, so shades mapped to one entry pool their votes. With a material
    `library`, blocks whose winning material has a ramp take its most voted
    entry instead (see `materials`).
    """
    materials = _materials(
        factor, palette, identities, library, shade_range, by_mode=True, edges=edges
    )
    result = []
    for frame in frames:
        if _has_front(frame):
            pixels = layered(frame, factor, palette, materials, edges, by_mode=True)
        else:
            pixels = frame.pixels
            if palette is not None:
                pixels = imageops.map_palette(pixels, palette)
            pixels = imageops.reduce_blocks_mode(pixels, factor, edges)
            if materials is not None:
                pixels = materials(frame, pixels)
        named = maps(frame, pixels, factor, pixels_per_meter)
        result.append(ImageFrame(frame.address, pixels, frame.metadata, named))
        del frame
    return tuple(result)


def _has_front(frame):
    present = frame.buffers.get(FRONT_PRESENT)
    return present is not None and bool(present.any())


def layered(frame, factor, palette, materials, edges, *, by_mode):
    """The reduced colour of a frame with a front layer, by the numerical
    reference's steps 1 to 4 (alpha design, *Stylize: numerical reference*).

    1. Each supersample's front weight `uᵢ` and back transmitted weight `tᵢ`
       (`imageops.layer_weights`) give its composite alpha `aᵢ = uᵢ + tᵢ`; a
       sample is a surface where either layer is present. The block's alpha
       byte is decided from them under `edges` (`imageops.composite_alpha`).
    2. Each layer is reduced with its own weights in place of colour alpha
       (`imageops.reduce_weighted`): `plain` takes the weighted mean, which a
       palette then maps; `mode` the weighted vote, a palette mapping the
       samples first. Each layer takes its winning material's ramp where it
       has one (`materials`, with the layer's own weights, identities and
       shades); the front layer's identity and shade are its front-most
       material's.
    3. The front is composited over the back in linear colour with the
       layers' total weights (`imageops.composite`); a pixel with one
       weighted layer keeps that layer's colour.
    4. With a palette, a composited colour maps to the nearest palette
       colour; a one-layer pixel already holds one. Alpha is step 1's, never
       snapped.

    A pixel whose alpha is 0 is `(0, 0, 0, 0)`."""
    back = frame.pixels
    front = frame.buffers[FRONT_COLOR]
    u, t = imageops.layer_weights(
        back[..., 3], frame.buffers[FRONT_ALPHA], frame.buffers[FRONT_PRESENT]
    )
    surfaces = (back[..., 3] > 0) | frame.buffers[FRONT_PRESENT]
    alpha = imageops.composite_alpha(u + t, surfaces, factor, edges)
    if by_mode and palette is not None:
        back = imageops.map_palette(back, palette)
        front = imageops.map_palette(front, palette)
    back_rgb, back_weight = imageops.reduce_weighted(
        back[..., :3], t, factor, by_mode=by_mode
    )
    front_rgb, front_weight = imageops.reduce_weighted(
        front[..., :3], u, factor, by_mode=by_mode
    )
    if not by_mode and palette is not None:
        back_rgb = _mapped(back_rgb, palette)
        front_rgb = _mapped(front_rgb, palette)
    if materials is not None:
        # Each layer takes the ramp of its winning material, the front layer
        # by its front-most material's identity and shade, so a rear pane's
        # ramp is not applied (D-12, D-15).
        opaque = np.full(back_rgb.shape[:2], 255, np.uint8)
        back_rgb = materials(frame, np.dstack([back_rgb, opaque]), weights=t)[..., :3]
        front_rgb = materials(
            frame, np.dstack([front_rgb, opaque]), weights=u, front=True
        )[..., :3]
    colour = imageops.composite(front_rgb, front_weight, back_rgb, back_weight)
    if palette is not None:
        both = (front_weight > 0) & (back_weight > 0)
        colour[both] = _mapped(colour[both][np.newaxis], palette)[0]
    pixels = np.zeros((*alpha.shape, 4), dtype=np.uint8)
    kept = alpha > 0
    pixels[kept, :3] = colour[kept]
    pixels[kept, 3] = alpha[kept]
    return pixels


def _mapped(rgb, palette):
    """`uint8` RGB of shape `(H, W, 3)` mapped to the palette."""
    opaque = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
    return imageops.map_palette(opaque, palette)[..., :3]


def maps(frame, pixels, factor, pixels_per_meter):
    """The reduced maps of `frame`, whose reduced colour is `pixels`:
    `{NORMAL_MAP: normals, DEPTH_MAP: depths}` from its `NORMAL` and `DEPTH`
    buffers, at the colour's coverage (alpha above 0, alpha design D-11),
    with depth converted to sheet pixels by the sheet's `pixels_per_meter`;
    `{}` for a frame carrying neither. The arrays are new, so the frame's are
    free once it is released."""
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
        pixels[..., 3] > 0,
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


def _materials(factor, palette, identities, library, shade_range, *, by_mode, edges):
    """The per-frame material step for `library`, or `None` without one.

    The step takes a frame and its reduced ordinary look and returns the look
    with each block that took a ramp entry replaced; with `weights`, a
    layer's own (`layered`), they replace colour alpha in the votes and
    bands, and with `front` the front layer's identity and shade arrays are
    voted and banded instead of the frame's. It keeps no reference to the frame, so the frame's buffers are
    free once it returns.
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

    def step(frame, ordinary, weights=None, front=False):
        names = (FRONT_IDENTITY, FRONT_SHADE) if front else (IDENTITY, SHADE)
        for name in names:
            if name not in frame.buffers:
                raise ValueError(
                    f"{frame.address}: a material library needs the {name} buffer"
                )
        ramped, mapped = imageops.map_ramps(
            frame.buffers[FRONT_COLOR] if front else frame.pixels,
            frame.buffers[names[0]],
            frame.buffers[names[1]],
            factor,
            ramps,
            palette,
            lo,
            hi,
            by_mode=by_mode,
            pool=pooled,
            ranges=ranges,
            edges=edges,
            weights=weights,
        )
        ordinary[mapped] = ramped[mapped]
        return ordinary

    return step
