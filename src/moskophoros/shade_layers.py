"""The response step of stylize: each layer shaded by its winning material's
response, then snapped, dithered and composited (shading design contract 3;
D-14, D-18 to D-21, D-23, D-27 to D-30, D-34, D-36, D-37).

`stylize` reduces each layer to its ordinary colour first and hands it here
with the layer's own weights, identity, shade and normal arrays. This step
chooses each output pixel's winning identity as `imageops.map_ramps` does,
shades the pixel by that identity's `shading_resolve.Look` through
`lighting.shade_blocks`, and decides the three things that depend on the
other layer of the same pixel:

- **Band dithering** of a ramp or both layer is suppressed where a snap makes
  the final colour choice instead: under `ramp` snap on a brightness or both
  layer itself, under `palette` snap on both layers of a pixel where either
  uses brightness or both.
- **Own-ramp snap** (`ramp`): a brightness or both layer's rounded bytes snap
  to its own ramp, or to the whole palette when it has none, before the
  layers are composited.
- **Whole-palette snap** (`palette`): when some contributing layer uses
  brightness or both, the composite's rounded bytes snap once to the whole
  palette, dithered by the controls of the layer with the greater visible
  weight, the front on a tie.

Everything else keeps the existing composition: the layers composite once in
linear colour, and a pixel of two layers none of which uses brightness or both
still maps to the palette. Alpha, coverage and geometry are never touched; the
step returns colour only. It reads only arrays and values it is given, keeps
no reference to them and changes none in place.
"""

from dataclasses import dataclass
from functools import cached_property

import numpy as np

from moskophoros import dither, imageops, lighting

# The modes that scale a colour by the plain signal, and the ones that select
# a ramp band by it.
BRIGHT = ("brightness", "both")
BANDED = ("ramp", "both")


@dataclass(frozen=True)
class Table:
    """What a stylize call resolved for its identities, shared by every frame:
    `pooled` maps an identity index to the lowest index of its name (the last
    index is the no-identity class), `ramps` and `looks` give each index its
    palette-index ramp or None and its `shading_resolve.Look` (None for an
    index pooled into a lower one), `palette` the `(P, 3)` `uint8` colours or
    None, `lights` the `lighting.Lights` and `snap` the global snap target."""

    pooled: np.ndarray
    ramps: tuple
    looks: tuple
    palette: object
    lights: object
    snap: str

    @cached_property
    def bright(self):
        """Whether each identity index's response uses brightness or both."""
        return np.array(
            [look is not None and look.response.mode in BRIGHT for look in self.looks]
        )


@dataclass(frozen=True)
class Layer:
    """One layer of a frame to shade: `rgb`, its ordinary `uint8` colour of
    shape `(H, W, 3)`; `weights`, the integer weight of each supersample
    (`(H·s, W·s)`); the names of the frame's identity, shade and normal
    buffers for the layer; and, optionally, `covered`, an `(H, W)` boolean
    array of the blocks that may be shaded (all that have weight, if None)."""

    rgb: np.ndarray
    weights: np.ndarray
    identity: str
    shade: str
    normals: str
    covered: object = None


@dataclass(frozen=True)
class _Group:
    """The blocks of one layer that one identity won: their ordinary colour,
    the winner's weights, shades and normals, their output cells, and the
    ramp and `Look` the winner resolved to."""

    base: np.ndarray
    weight: np.ndarray
    shades: np.ndarray
    normals: object
    rows: np.ndarray
    columns: np.ndarray
    ramp: object
    look: object

    def shade(self, colour, part, pattern, table, by_mode):
        """Set `colour` for the blocks `part` marks to their shaded colour,
        band dithered by `pattern` (`off` for none)."""
        if not part.any():
            return
        response = self.look.response
        normals = None if self.normals is None else self.normals[part]
        colour[part] = lighting.shade_blocks(
            self.base[part],
            self.weight[part],
            self.shades[part],
            normals,
            ramp=self.ramp,
            palette=table.palette,
            response=response,
            shade_range=self.look.shade_range,
            lights=table.lights,
            by_mode=by_mode,
            pattern=pattern,
            strength=response.dither_strength,
            rows=self.rows[part],
            columns=self.columns[part],
        )


class _Work:
    """One layer of one frame under shading: its blocks' samples and winners,
    and its colour as shading changes it."""

    def __init__(self, table, frame, layer, factor):
        for name in (layer.identity, layer.shade):
            if name not in frame.buffers:
                raise ValueError(
                    f"{frame.address}: a shading response needs the {name} buffer"
                )
        self.table = table
        self.frame = frame
        self.layer = layer
        self.rows, self.columns = layer.rgb.shape[:2]
        identity = np.asarray(frame.buffers[layer.identity])
        identities = len(table.ramps)
        if identity.min() < -1 or identity.max() >= identities:
            raise ValueError(
                f"{frame.address}: the {layer.identity} buffer must hold -1 or "
                f"an index below {identities}"
            )
        identity = np.where(identity < 0, -1, table.pooled[np.maximum(identity, 0)])
        self.alpha = imageops._by_block(layer.weights, factor)
        self.ident = imageops._by_block(identity, factor)
        self.shades = imageops._by_block(frame.buffers[layer.shade], factor)
        self.total = self.alpha.sum(axis=1)
        covered = self.total > 0
        if layer.covered is not None:
            covered &= np.asarray(layer.covered).reshape(-1)
        self.winner = imageops._winners(self.alpha, self.ident, identities, covered)
        self.bright = (self.winner >= 0) & table.bright[np.maximum(self.winner, 0)]
        self.rgb = layer.rgb.reshape(-1, 3).copy()
        self.factor = factor
        self._normals = None

    def sampled_normals(self):
        """The layer's normals as one row of `s²` samples per block."""
        if self._normals is None:
            normals = self.frame.buffers.get(self.layer.normals)
            if normals is None:
                raise ValueError(
                    f"{self.frame.address}: a shading response with a directional "
                    f"strength needs the {self.layer.normals} buffer"
                )
            normals = np.asarray(normals)
            shape = (self.rows * self.factor, self.columns * self.factor, 3)
            if normals.shape != shape:
                raise ValueError(
                    f"{self.frame.address}: the {self.layer.normals} buffer must "
                    f"have shape {shape}, not {normals.shape}"
                )
            size = self.factor
            self._normals = (
                normals.reshape(self.rows, size, self.columns, size, 3)
                .transpose(0, 2, 1, 3, 4)
                .reshape(self.rows * self.columns, size * size, 3)
            )
        return self._normals

    def shade(self, suppress, cells, *, by_mode):
        """Shade every block that has a winner whose response changes its
        colour. `suppress` marks the blocks whose band dithering a snap
        replaces, and `cells` holds the output cell row and column of every
        block. With ramp snap on, a brightness or both block then snaps to its
        own ramp."""
        table = self.table
        for index in np.unique(self.winner[self.winner >= 0]):
            look, ramp = table.looks[index], table.ramps[index]
            response = look.response
            if ramp is None and response.mode in ("ramp", "neither"):
                continue  # the ordinary colour, as it is
            chosen = np.flatnonzero(self.winner == index)
            own = (self.ident[chosen] == index) & (self.alpha[chosen] > 0)
            weight = self.alpha[chosen] * own
            shades = self.shades[chosen]
            directional = (
                response.key_strength
                or response.sky_strength
                or response.ground_strength
            )
            normals = self.sampled_normals()[chosen] if directional else None
            rows, columns = cells[0][chosen], cells[1][chosen]
            group = _Group(
                self.rgb[chosen],
                weight,
                shades,
                normals,
                rows,
                columns,
                ramp,
                look,
            )
            colour = np.empty_like(group.base)
            quiet = suppress[chosen]
            try:
                if ramp is not None and response.mode in BANDED:
                    group.shade(colour, ~quiet, response.dither_pattern, table, by_mode)
                    group.shade(colour, quiet, "off", table, by_mode)
                else:
                    everyone = np.ones(len(chosen), bool)
                    group.shade(colour, everyone, "off", table, by_mode)
            except ValueError as error:
                raise ValueError(f"{self.frame.address}: {error}") from None
            if table.snap == "ramp" and response.mode in BRIGHT:
                colour = dither.snap(
                    colour,
                    dither.snap_target(table.palette, ramp),
                    pattern=response.dither_pattern,
                    strength=response.dither_strength,
                    rows=rows,
                    columns=columns,
                )
            self.rgb[chosen] = colour

    def colour(self):
        return self.rgb.reshape(self.rows, self.columns, 3)


def shade_frame(table, frame, factor, back, front=None, *, palette, by_mode):
    """The colour of a frame's output pixels, shaded and composited:
    `uint8` RGB of shape `(H, W, 3)`, black where no layer has weight.

    `back` and `front` are `Layer`s, `front` None for a frame without a front
    layer; `palette` is the palette `stylize` was given, or None, for the
    composite mapping that remains when no layer uses brightness or both.
    Raises `ValueError`, naming the frame, for a buffer the response needs
    and the frame lacks."""
    works = [_Work(table, frame, back, factor)]
    if front is not None:
        works.append(_Work(table, frame, front, factor))
    rows, columns = works[0].rows, works[0].columns
    count = rows * columns
    cells = np.divmod(np.arange(count), columns)
    bright = np.zeros(count, bool)
    for work in works:
        bright |= work.bright
    nobody = np.zeros(count, bool)
    for work in works:
        suppress = {"off": nobody, "ramp": work.bright, "palette": bright}[table.snap]
        work.shade(suppress, cells, by_mode=by_mode)
    back_work = works[0]
    zero = np.zeros((rows, columns))
    front_work = works[1] if front is not None else None
    back_weight = back_work.total.reshape(rows, columns)
    front_weight = (
        zero if front_work is None else front_work.total.reshape(rows, columns)
    )
    front_colour = (
        np.zeros((rows, columns, 3), np.uint8)
        if front_work is None
        else front_work.colour()
    )
    result = imageops.composite(
        front_colour, front_weight, back_work.colour(), back_weight
    )
    flat = result.reshape(-1, 3)
    both = ((front_weight > 0) & (back_weight > 0)).reshape(-1)
    if palette is not None:
        # The existing rule: a composite of two layers maps to the palette
        # unless a brightness or both layer keeps it where it is (D-18).
        mapped = both & ~bright
        if mapped.any():
            opaque = np.full((1, int(mapped.sum()), 1), 255, np.uint8)
            rgba = np.concatenate([flat[mapped][np.newaxis], opaque], axis=2)
            flat[mapped] = imageops.map_palette(rgba, palette)[0, :, :3]
    if table.snap == "palette" and bright.any():
        _snap_composite(table, flat, bright, works, cells)
    return result


def _snap_composite(table, flat, bright, works, cells):
    """Snap the composite of the pixels where some contributing layer uses
    brightness or both to the whole palette, each pixel dithered by the
    controls of the layer with the greater visible weight, the front on a tie
    (D-30); `neither` or a layer without a winner snaps without dithering."""
    owner = works[0].winner
    if len(works) == 2:
        front, back = works[1], works[0]
        owner = np.where(front.total >= back.total, front.winner, back.winner)
    for index in np.unique(owner[bright]):
        chosen = np.flatnonzero(bright & (owner == index))
        pattern, strength = "off", 1.0
        if index >= 0:
            response = table.looks[index].response
            if response.mode != "neither":
                pattern, strength = response.dither_pattern, response.dither_strength
        flat[chosen] = dither.snap(
            flat[chosen],
            table.palette,
            pattern=pattern,
            strength=strength,
            rows=cells[0][chosen],
            columns=cells[1][chosen],
        )
