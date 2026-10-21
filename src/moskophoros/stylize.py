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

Given the resolved shading (`shading`, a `shading_resolve.Resolved`, and its
`lights`; design §Stylize, Two layers), each layer is also shaded by its winning
material's response, snapped, dithered and composited by `shade_layers`
(shading design contract 3), with or without a library. The command passes
them on every run; where they would change nothing, and without them, the
reductions are exactly as above.

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

from moskophoros import imageops, lighting, materials, shade_layers, shading_resolve
from moskophoros.sampling import (
    BACK_NORMAL,
    DEPTH,
    DEPTH_MAP,
    FRONT_ALPHA,
    FRONT_COLOR,
    FRONT_IDENTITY,
    FRONT_NORMAL,
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
    *,
    shading=None,
    lights=None,
):
    """Reduce every supersampled frame by `factor`×`factor` blocks, each
    output pixel's alpha decided by `edges` (`imageops.reduce_blocks`).

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata and its reduced normal and depth
    maps (see `maps`). With a palette, map the reduced pixels after
    averaging; alpha is never snapped. With a material `library`, blocks
    whose winning material has a ramp take its entry instead (see
    `materials`).

    `shading`, a `shading_resolve.Resolved`, and `lights`, the
    `lighting.Lights` of the frame's sky, ground and key, are the resolved
    shading response (see `shaded`); without them the reduction is exactly the
    one above.
    """
    materials = _materials(
        factor,
        palette,
        identities,
        library,
        shade_range,
        by_mode=False,
        edges=edges,
        shading=shading,
        lights=lights,
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
    *,
    shading=None,
    lights=None,
):
    """Reduce every supersampled frame by `factor`×`factor` blocks, keeping
    each block's most common colour, each output pixel's alpha decided by
    `edges` (`imageops.reduce_blocks_mode`).

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata and its reduced normal and depth
    maps (see `maps`). With a palette, map the supersampled pixels before
    voting, so shades mapped to one entry pool their votes. With a material
    `library`, blocks whose winning material has a ramp take its most voted
    entry instead (see `materials`). `shading` and `lights` are as for
    `plain`.
    """
    materials = _materials(
        factor,
        palette,
        identities,
        library,
        shade_range,
        by_mode=True,
        edges=edges,
        shading=shading,
        lights=lights,
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
    if isinstance(materials, _Shaded):
        # Each layer is shaded by its winning material's response and the
        # layers composited by the response step (`shade_layers`).
        colour = materials.layered(frame, back_rgb, t, front_rgb, u)
    else:
        if materials is not None:
            # Each layer takes the ramp of its winning material, the front
            # layer by its front-most material's identity and shade, so a
            # rear pane's ramp is not applied (D-12, D-15).
            opaque = np.full(back_rgb.shape[:2], 255, np.uint8)
            back_rgb = materials(frame, np.dstack([back_rgb, opaque]), weights=t)[
                ..., :3
            ]
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


def _materials(
    factor,
    palette,
    identities,
    library,
    shade_range,
    *,
    by_mode,
    edges,
    shading=None,
    lights=None,
):
    """The per-frame material step for `library`, or `None` without one.

    The step takes a frame and its reduced ordinary look and returns the look
    with each block that took a ramp entry replaced; with `weights`, a
    layer's own (`layered`), they replace colour alpha in the votes and
    bands, and with `front` the front layer's identity and shade arrays are
    voted and banded instead of the frame's. It keeps no reference to the frame, so the frame's buffers are
    free once it returns.

    Given the resolved `shading` and its `lights`, the step is `shaded`
    instead, and may exist without a library.
    """
    if (shading is None) != (lights is None):
        raise ValueError("a resolved shading and its lights are given together")
    if shading is not None:
        return shaded(
            factor,
            palette,
            identities,
            library,
            shade_range,
            shading,
            lights,
            by_mode=by_mode,
        )
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


def shaded(
    factor, palette, identities, library, shade_range, shading, lights, *, by_mode
):
    """The response step for the resolved `shading` (a
    `shading_resolve.Resolved`) and its `lights` (a `lighting.Lights`), or
    `None` where it would change nothing.

    The caller resolves everything and passes it: each identity's response
    and shade range (`shading.look`), the global snap target
    (`shading.settings.snap`), the key, sky and ground vectors in camera
    coordinates (`lights`, from `lighting.light_vectors`) and `shade_range`,
    the global range, which must be the one `shading` resolved. Stylize never
    resolves a frame name or reads a setting, a file or a Blender object.

    With a `library` each identity takes its ramp (`resolve`); without one
    every identity is ordinary under the global response, and a palette is
    needed only by a snap target other than `off`. Without a library, and with
    no response that scales brightness (mode `brightness` or `both`), nothing
    changes the ordinary colour, so there is no step and the frame is reduced
    exactly as it was before shading existed.
    """
    if not isinstance(shading, shading_resolve.Resolved):
        raise TypeError("shading must be a shading_resolve.Resolved")
    if not isinstance(lights, lighting.Lights):
        raise TypeError("lights must be a lighting.Lights")
    snap = shading.settings.snap
    if library is not None and palette is None:
        raise ValueError("a material library needs a palette: its ramps index it")
    if snap != "off" and palette is None:
        raise ValueError(f"the snap target {snap!r} needs a palette")
    if shade_range is None:
        raise ValueError("a shading response needs a shade range")
    if tuple(shade_range) != shading.base.shade_range:
        raise ValueError(
            f"the shade range {tuple(shade_range)} is not the resolved global "
            f"range {shading.base.shade_range}"
        )
    everyone = (shading.base, shading.fallback, *shading.materials.values())
    if library is None and not any(
        look.response.mode in shade_layers.BRIGHT for look in everyone
    ):
        return None
    if identities is None:
        raise ValueError("a shading response needs the asset's identity list")
    names = identities.names
    # Materials sharing a name are one identity, the one of lowest index.
    pooled = np.array([names.index(name) for name in names] + [len(names)])
    own = [pooled[index] == index for index in range(len(names))]
    ramps = tuple(
        None if library is None or not own[index] else resolve(library, name)
        for index, name in enumerate(names)
    ) + (None,)
    looks = tuple(
        shading.look(name) if own[index] else None for index, name in enumerate(names)
    ) + (shading.look(None),)
    colours = None if palette is None else np.asarray(palette, dtype=np.uint8)
    table = shade_layers.Table(pooled, ramps, looks, colours, lights, snap)
    return _Shaded(table, factor, palette, by_mode)


class _Shaded:
    """The response step as `stylize` calls it: a frame's layers shaded and
    composited by `shade_layers`. It keeps no reference to a frame."""

    def __init__(self, table, factor, palette, by_mode):
        self.table = table
        self.factor = factor
        self.palette = palette
        self.by_mode = by_mode

    def __call__(self, frame, ordinary):
        """The reduced `ordinary` RGBA look of a frame with no front layer,
        shaded: the frame's identity, shade and back normal arrays with its
        colour alpha as the weights, one contributing layer."""
        layer = shade_layers.Layer(
            ordinary[..., :3],
            frame.pixels[..., 3],
            IDENTITY,
            SHADE,
            BACK_NORMAL,
            covered=ordinary[..., 3] > 0,
        )
        colour = shade_layers.shade_frame(
            self.table,
            frame,
            self.factor,
            layer,
            palette=self.palette,
            by_mode=self.by_mode,
        )
        result = ordinary.copy()
        result[..., :3] = colour
        return result

    def layered(self, frame, back_rgb, back_weights, front_rgb, front_weights):
        """The composite colour of a frame with a front layer: each layer's
        ordinary reduced `uint8` RGB and its own weights."""
        back = shade_layers.Layer(back_rgb, back_weights, IDENTITY, SHADE, BACK_NORMAL)
        front = shade_layers.Layer(
            front_rgb, front_weights, FRONT_IDENTITY, FRONT_SHADE, FRONT_NORMAL
        )
        return shade_layers.shade_frame(
            self.table,
            frame,
            self.factor,
            back,
            front,
            palette=self.palette,
            by_mode=self.by_mode,
        )
