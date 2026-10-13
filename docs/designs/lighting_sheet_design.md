# Lighting sheet design

Moskophoros writes a flat colour sheet: each material drawn from its ramp,
banded only by ambient occlusion and curvature (material styling D-22, D-25).
Directional light was deliberately left out, so that a game can light the
sprites live. This arc gives the game what it needs to do that: a **normal
map** aligned pixel for pixel with the colour sheet, an optional **depth
map**, and a **lit preview** that shows the owner the sprite as a game
shader would light it, without ever baking that light into the colour sheet.

It is the "later arc" that material styling D-1, D-2 and D-27 set up, and the
trigger for the depth and normal rows of design §Deferred ("Auxiliary capture
buffers"). It benefits the owner producing game art, and any game that lights
2D sprites from normal maps (V-1).

Design state: `ready for issue processing`

*Re-approved by the owner on 2026-10-13 after [Review 1](#review-1) and
[Review 2](#review-2) (D-25). It had been reset to `exploring` for those
reviews' revisions.*

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

The owner approved this slice list on 2026-10-13 (D-20) and re-approved it
after Reviews 1 and 2 (D-25), which added obligations to its slices but no
slice.

- [ ] EPIC. Light sprites live: a normal map, an optional depth map and lit previews
- [ ] LIT-1. Capture normal and depth buffers on every render
- [ ] LIT-2. Reduce normals and depth to the sheet's pixels
- [ ] LIT-3. Write the normal map, record it and reuse it
- [ ] LIT-4. Write the optional depth map
- [ ] LIT-5. Light the previews with an optional point light
- [ ] LIT-6. Review normal maps and lit previews with the owner

## Epic contract

*Signed off by the owner on 2026-10-13 (D-20).*

- **Goal:** beside every colour sheet, the owner gets a normal map (and, when
  asked, a depth map) with the same layout, cells and frames, which a game
  shader can light live; and can preview the sprites lit by a light they
  place, while the exported colour sheet stays exactly as flat as without
  the arc.
- **Done when:** the automated checks prove the maps' alignment and
  encoding; every existing look writes the same colour sheet pixels and flat
  previews as before the arc; `--settings-from` reproduces every new output
  byte for byte; and the owner reviews normal maps, depth maps and lit
  previews of the acceptance model by eye and approves them (LIT-6, V-12).
- **Users and operators:** the owner producing game art; games that read the
  maps; agents maintaining the tool.
- **Arc label:** None proposed.

## Current state and evidence

Checked on 2026-10-13 at `master` `44e5891`, by reading only, and the
tracker re-checked at readiness the same day. The capture
spike recorded under [Capture](#capture) is separate.

**Camera and space** (design §Camera and directions)

- The camera never moves; the subject turns. The camera is orthographic,
  sits in direction `(0, sin p, cos p)` from the ground point, with screen
  right +X and screen up `(0, cos p, −sin p)` in glTF coordinates. So a
  direction in the camera's frame is the same thing for every direction and
  frame of a sheet: "camera-relative" needs no per-frame bookkeeping.
- Lighting is fixed to the camera (V-7). The Workbench colour render uses a
  view-space studio light (`configure_render`,
  `capture/blender_script.py:954`).

**Capture** (design §Capture, §Capture job and result contract)

- Each frame gets a Workbench colour render, then **one Cycles render**
  that replaces every material with an emission carrying the material-ID
  code (red and blue) and the shade (green), from one camera sample per
  pixel at the pixel centre, written to an 8-bit TGA and split into
  `matid/` and `shade/` PNGs (`Auxiliary`, `render_auxiliary`,
  `blender_script.py:1083`, `:1441`). Every change is restored before the
  next colour render.
- That render's three 8-bit channels are fully used. A normal (three
  components) and a depth need more channels, more precision, or another
  render.
- The result contract already names buffers per frame, and "extra named
  buffers can be described without changing the frame structure" (design
  §result format). But the launcher accepts only **8-bit RGBA PNGs at the
  supersampled size** (`capture/backend.py:870` `_buffer`), so a float or
  16-bit buffer needs a validator change.
- The shade pass lets **no material property reach it, normal maps
  included** (design §Capture, *Surfaces*).
- Capture cost: the material spike measured about 1 s per frame for the
  auxiliary render at 128 × 112 and 4 s at 2048 × 1792 (material styling
  §Spike record); [spike 1](#spike-1) measured 0.02 s and 2 s on a faster
  machine.

**Between capture and export**

- Frames carry named buffers into stylize (`ImageFrame.buffers`, design
  §Frames into stylize). Stylize returns an ordinary reduced colour frame and
  releases every other buffer; cleanup and export see only reduced colour
  frames. A normal map needs the supersampled normals reduced to the output
  grid too, and carried to export: this is new.
- Coverage is the block's mean colour alpha, kept at 0.5 or more; output alpha
  is 0 or 255 (design §Stylize). Any aligned map must take exactly this
  coverage.

**Export** (design §Export)

- One sheet PNG, its JSON (`moskophoros.sheet/7`), and one GIF preview per
  clip (`<stem>.<clip>.gif`, 4×, on `#808080`, at most 256 colours or a
  warning). Every output is written to a temporary file and published
  all-or-nothing.
- The JSON records every setting that affects the PNG, the JSON or the
  previews, and reloads them with `--settings-from` (settings design D-16).
  Only the current schema loads; each bump stops the previous one loading
  (settings design D-24).

**The owner's consumer.** The owner's current engine reads a "face map"
as three face weights, not a normal map (material styling, "The owner's
consumer"). Under D-27 the tool emits a standard normal map and the game
converts. The owner's engine turns its camera in 4 rotations while sprites
face 8 directions (dispatch brief; material styling Q-11).

**Tracker:** no open issue or epic covers lighting, normals or depth. Open
are #63 (material styling, for MAT-8), #75 (deferred `MASK` cutouts) and #43
(held animation support).

## Desired experience

*As decided in D-9 to D-19.*

```sh
moskophoros --palette vince-144.gpl --materials robot.yaml knight.glb knight.png
```

writes, as today, the flat `knight.png`, `knight.json` and the flat
`knight.<clip>.gif` previews, and beside them `knight.normal.png`: the same
size and layout, each covered pixel holding that pixel's surface direction
in the frame's camera space, and every transparent pixel of the colour sheet
transparent in it too. A game loads both, picks the frame for the unit's
facing as it does today, and lights it with any light it likes.

Asking for depth adds a depth map in the same layout (D-10). Placing a
light, `--light X,Y,Z` (D-13), adds lit previews: the flat sprite lit with
its own normal map and depth by the documented formula a game shader would
use. The colour sheet and the flat previews never change because a light was
given.

**What a game needs.** The normal map says which way each pixel faces; that
is all a game needs for a distant light such as the sun. For a light at a
position, the game also needs where each pixel is, to know the light's
direction from it: the depth map gives that exactly. A game using only the
normal map treats every pixel as lying on the sprite's flat plane, which is
exact for a distant light and close for a near one. The lit preview uses
both maps, so it shows the exact case.

## Scope

### In scope

- Capturing per-frame surface normals, and depth, aligned with the existing
  colour, material-ID and shade buffers.
- Reducing them to the output grid with the colour sheet's coverage.
- Writing the normal map, and the optional depth map, as sheets in the
  colour sheet's layout, described in the sheet's JSON.
- The lit preview and the flag that places its light.
- Their settings, recording and reuse; the schema bump; the design
  amendments, tests and documentation each slice needs; the owner's visual
  review.

### Out of scope

- Baking any point or directional light into the colour sheet (D-1, D-4).
- Shadows that one part casts on another (D-7).
- The owner's planned interface and its interactive light (D-6).
- Any game's private layout, such as face weights (V-1, D-2).
- Changing the colour capture, the shade buffer, the ramps or any existing
  look.
- A directional-light option, light colour, distance falloff, and a lit
  sheet PNG (D-13, D-14).
- Making the ordinary look flat: it keeps its studio light (D-23).
- Normal textures (D-16), and `MASK` cutouts in any map: the maps follow
  the colour's opaque `MASK` surfaces, as the ID and shade do (material
  styling D-26).

## Design

Each part cites the decision it follows; anything without one is the
slice's engineering detail.

### Data flow

```text
capture (Blender) ── per frame ──► color   unchanged
                                   matid   unchanged
                                   shade   unchanged
                                   normal  camera-space surface direction (new)
                                   depth   camera depth                   (new)
   ▼
command: loads and validates every buffer, as today
   ▼
stylize: colour → reduced colour (unchanged)
         normal, depth → reduced maps with the colour's coverage (new)
   ▼
cleanup ──► export: sheet PNG, normal map, depth map, JSON, previews,
                    lit previews when a light is placed
```

### Direction space

The normal is stored in the frame's **camera space**: +X screen right, +Y
screen up, +Z toward the viewer (D-2). Because the camera is fixed and the
subject turns, this is one frame of reference for the whole sheet. The
encoding is the common "OpenGL" convention: `byte = round((n + 1) / 2 ·
255)` per component, so a surface facing the viewer is `(128, 128, 255)`.

**A game camera that turns.** Nothing in the sheet depends on the game's
camera. For a game camera at yaw `ψ` and the sheet's pitch `p`, the game
already picks the sprite whose direction matches the unit's facing relative
to the camera. To light it, it rotates its world light into camera space by
`ψ` and `p`, then dots it with the stored normal. Four camera rotations and
eight facings therefore need nothing extra from the tool beyond the recorded
pitch and axis convention. (The game must render at the sheet's pitch for
the lighting to be exact, as it must already for the sprite to look right.)

### Capture

How Blender produces the normal and depth is
[Q-8](#q-8-how-does-blender-produce-the-normal-and-depth), answered by
spike 1 below. The contract it had to meet:

- the **same camera sample** as the material-ID and shade, so a normal pixel
  is always the surface its ID names;
- the **shading normal** (the model's interpolated vertex normals), not the
  flat face normal;
- full precision kept at the supersampled size, since the reduction averages;
- deterministic, and the colour bytes unchanged.

**The capture** (D-11, D-12), from the spike: the existing auxiliary Cycles render
gains two shader outputs (AOVs) in every replacement material, so no second
render is needed. Blender's script reads them back with the standard library
and writes them as buffers of its own, `normal/NNNNNN.png` and
`depth/NNNNNN.png`, beside `matid` and `shade`. Their exact file encoding at
the supersampled size (for example 16-bit PNGs) is the capture slice's
detail; the launcher's validator, which accepts only 8-bit RGBA today, gains
it. Depth is stored relative to the ground point, because the camera's
distance changes per frame (below).

#### Spike 1

Recorded 2026-10-13, before any capture change; its code is not delivered.
Blender 5.2.2 LTS on macOS (Apple M3 Max, 16 cores), Cycles on the CPU,
`master` `44e5891`. The production capture script ran unchanged; the spike
extended only its `Auxiliary` class and `render_auxiliary`. Scripts, logs and
the full report are in
`~/.local/share/moskophoros-acceptance/lighting-design/spike-1/`
(`REPORT.md`).

**Technique.** In each replacement material, beside the ID and shade
emission:

- *normal:* Geometry *Normal* → Vector Transform (normal, world to camera) →
  AOV Output `normal` (a colour AOV on the view layer);
- *depth:* Camera Data *View Z Depth* → AOV Output `depth` (a value AOV).

One render writes the TGA exactly as today; the render result is then also
saved as an uncompressed 32-bit multilayer OpenEXR (`media_type` must be set
to `MULTI_LAYER_IMAGE` before the format), and every setting and AOV is
restored. Cycles' camera space is +X right, +Y up, +Z into the scene, so the
design's normal (D-2, §Direction space) is the AOV's `(x, y, −z)`. Blender
cannot load the EXR's pixels in background mode, but a reader using only the
standard library reads a 2048 × 1792 frame in 0.05 s; ZIP compression would
cost 7.7 s per frame in pure Python, so the file is uncompressed. Blender's
built-in Normal and Z passes are also filled with emission shaders, in the
same sample, but the Normal pass is in world space and background depth is
10¹⁰, so the AOVs are simpler.

**Measurements** (fixture: floor, wall at a 90° crease, smooth UV sphere of
radius 0.35 m, a plane with a known tilt; 40 px/m, cell 176 × 176, 8
directions, pitch 0°, 30° and 90°, supersample 1 and 8):

| Check | Result |
|---|---|
| Plane normals | within 0.0022° of exact; the floor reads `(0, cos p, sin p)` |
| Sphere normals | mean error about 0.05° (a flat face normal would be 1.2–1.4°); at most 0.19° where the surface faces the camera by 0.3 or more; up to 3.4° at the tessellated rim |
| Camera-relative | the tilted plane's x component changes sign between directions 0 and 45 |
| Plane depth | within 2.3 × 10⁻⁵ m |
| Alignment | 0 pixels where normal or depth coverage differs from the material-ID's, over 48 fixture and 16 RobotExpressive frames |
| Determinism | normal and depth data bit-identical on repeat and with 1 or all threads (the EXR headers carry a render time, so data is compared, not files) |
| Colour unchanged | colour, material-ID and shade PNGs byte-identical to the production command over 64 frames |
| Cost per frame | 0.022 → 0.025 s at 128 × 112; 0.108 → 0.120 s at 384 × 384 (cell 48 × 48, supersample 8); 2.04 → 2.43 s at 2048 × 1792 |
| EXR size per frame | 0.5 MB, 5.3 MB and 132 MB at those sizes |

*Ranges on RobotExpressive* (cell 48 × 48 auto-fitted to 9.06 px/m, `iso`,
supersample 8): normal x and y span −1 to 1; z spans −0.31 to 1, below 0 on
0.02 % of pixels (interpolated normals at silhouettes). The camera's
distance from the ground point **changes per frame** (it follows the
subject's reach), so raw camera depth is meaningless across frames. Depth
relative to the ground point, in D-10's sign (positive toward the viewer),
spans −1.13 to +3.32 m: −10 to +30 sheet pixels at 9.06 px/m, −45 to +133
at 40 px/m. *Sign note (Review 1, R-5):* the spike's report and its
`analyze_robot.py` measure the opposite way, positive farther from the
camera, and quote −3.32 to +1.13 m; the figures here are negated to D-10's
convention.

*Findings:* a surface seen from behind reads its normal flipped toward the
viewer, since Cycles flips the shading normal; the multilayer EXR always
carries the combined colour too.

**Outcome:** the AOV technique meets the contract above on these fixtures,
for about 10 % more auxiliary render time, which stays a small part of a
frame's capture.

### Reducing a block

For each `s×s` block whose colour pixel is covered:

- **Normal** (D-15): the sum of every surface sample's unit normal in the
  block, renormalised, whatever the material, reduction or library. Never
  palette-mapped or voted (D-8). A covered pixel whose block has no surface
  sample (a thin edge the centre samples missed) faces the viewer.
- **Depth** (D-19): the mean depth of the same samples, rounded to the
  1/16-pixel step; a covered pixel with no sample takes its covered
  neighbours' mean, else 0.
- Capture and reduction hold depth at any value; only the encoding has a
  range (D-21). A run that writes no depth map and places no light is never
  limited by it.

### Numerical reference

Added by Review 1 (R-3, R-4). It is the exact calculation, so the preview
matches what a game reading the exported maps computes, and an
implementation can be tested against fixed vectors.

**Encoding** (half up throughout; never ties-to-even):

- normal byte, per component of the unit normal `n`:
  `floor(255 · (n + 1) / 2 + ½)`;
- depth code: `32768 + floor(16 · depth + ½)`, depth in sheet pixels,
  positive toward the viewer (D-10); 0 where the colour pixel is
  transparent.

**The lit preview** (D-13, D-14), for each covered pixel of each cell, in
NumPy `float64`, elementwise:

1. *Inputs:* the reduced colour pixel after cleanup, and the pixel's
   normal and depth **as encoded** above. The preview decodes the exported
   representation, even when the map files are not written, because that is
   what a game has.
2. *Normal:* `m = 2 · byte / 255 − 1` per component, `N = m / |m|` (the
   encoded viewer-facing `(128, 128, 255)` decodes to a vector of length
   1.0000154, so it is renormalised).
3. *Depth:* `d = (code − 32768) / 16`.
4. *Position,* at the pixel's centre, in the light's frame (D-13):
   `P = (c + ½ − gx, gy − r − ½, d)`, where `c` and `r` are the pixel's
   column and row within its cell, counted from the cell's top-left, and
   `(gx, gy)` is the ground pixel corner (design §Scale and ground point).
5. *Light direction:* `V = light − P`. If `V` is exactly `(0, 0, 0)`, the
   light sits at the pixel and the diffuse term is 0 (ambient only).
   Otherwise `V` is first scaled by its largest absolute component,
   `W = V / max(|Vx|, |Vy|, |Vz|)`, and then `L = W / |W|`. *Added by
   Review 2 (S-3):* a plain `|V|` overflows for a light at `1e200` and
   underflows to 0 for one at `1e-200` from the pixel; after scaling, the
   largest component of `W` is exactly ±1, so `|W|` lies between 1 and √3
   and the direction is exact for every finite light.
6. *Factor:* `f = min(1, A + (1 − A) · I · max(0, N · L))` (D-14).
7. *Colour:* each of R, G and B is decoded with the fixed sRGB table
   (`imageops`, the palette mapping's), multiplied by `f`, encoded with
   `s = 12.92 · x` for `x ≤ 0.0031308`, else `1.055 · x^(1/2.4) − 0.055`,
   and written as `min(255, floor(255 · s + ½))`. Alpha is unchanged; a
   transparent pixel stays `(0, 0, 0, 0)`.
8. The lit frames then become GIFs exactly as the flat previews do.

No step produces a NaN or infinity: `m` is never zero for a covered pixel
(its encoded z is at least 1 byte from 127.5), `V = 0` is handled, and the
scaled normalisation in step 5 holds for every finite light. `P` is at most
a few thousand pixels from the ground point, so `light − P` cannot overflow
for any finite light. The light's three coordinates must be finite numbers
wherever they come from: the command line, a settings file or a reused
sheet (D-18).

**Reference vectors** (`A = 0.3`, `I = 1`, cell ground pixel
`(gx, gy) = (24, 46)` unless stated):

| Colour | Normal bytes | Depth code | Pixel `(c, r)` | Light | `f` | Lit colour |
|---|---|---|---|---|---|---|
| `(200, 100, 50)` | `(128, 128, 255)` | 32768 | `(24, 45)` | `(0.5, 0.5, 100)` | 0.9999892352 | `(200, 100, 50)` |
| `(200, 100, 50)` | `(128, 128, 255)` | 32768 | `(24, 45)` | `(0.5, 0.5, −100)` | 0.3 | `(116, 55, 25)` |
| `(200, 100, 50)` | `(218, 128, 218)` | 32848 | `(24, 45)` | `(100.5, 0.5, 5)` | 0.7949709697 | `(180, 90, 44)` |
| `(200, 100, 50)` | `(128, 128, 255)` | 32768 | `(24, 45)` | `(0.5, 0.5, 0)`, at the pixel | 0.3 | `(116, 55, 25)` |
| `(255, 255, 255)` | `(128, 218, 218)` | 32768 | `(30, 40)` | `(−20, 30, 40)` | 0.8912435296 | `(242, 242, 242)` |

They were computed by a throwaway script with this exact calculation; the
slices' tests recompute them.
- A transparent colour pixel is transparent in every map.

### Outputs

Beside the sheet: `<stem>.normal.png`, `<stem>.depth.png` and lit previews
`<stem>-lit.<clip>.gif` (D-17, D-22); the JSON's `maps` record names them, and the
new settings (D-18) are recorded and reused.

## Decisions

All are the owner's. D-1 to D-8 come from material styling D-27
(2026-10-13, typed in the moskophoros manager's terminal), recorded here as
this arc's starting point and not reopened. D-9 to D-23 were decided by the
owner in this design's session on 2026-10-13, D-21 to D-23 after Review 1;
D-24 and D-25 after Review 2.

### D-1. The colour sheet stays flat

Decided 2026-10-13 (material styling D-27). The colour sheet carries flat
ambient shading only, occlusion and curvature (material styling D-22,
D-25). No point or directional light is baked by default, and the tool keeps
this capability whatever else it gains.

### D-2. The lighting sheet is a standard, camera-relative normal map

Decided 2026-10-13 (material styling D-27; resolves material styling Q-11,
option A). A standard normal map, aligned pixel for pixel with the colour
sheet, holds each pixel's surface direction relative to that frame's own
camera, encoded in RGB. The game converts it to whatever its shader needs.

### D-3. An optional depth map

Decided 2026-10-13 (material styling D-27). An optional depth or height map,
aligned as the normal map is, lets a game light a pixel from a light at a
position in its world, not only from a distant light. What it stores is
[Q-2](#q-2-what-does-the-depth-map-store-and-how).

### D-4. Light is previewed, never baked

Decided 2026-10-13 (material styling D-27). An optional light is a preview.
The tool lights the flat sprite with its own normal map, making the same
calculation a game shader would, so the owner sees the sprite as the game
will light it. The exported colour sheet stays flat.

### D-5. Flat by default; an optional flag places the light

Decided 2026-10-13 (material styling D-27): "for the cli interface, just
output flat, but give the optional flag to place the light." Its form is
[Q-3](#q-3-what-is-the-light-flag-and-what-does-the-lit-preview-write).

### D-6. The owner's planned interface is not designed here

Decided 2026-10-13 (material styling D-27). In the owner's planned interface,
outside this command line, previews are lit by default, the viewer can turn
the light off or move it freely, and export writes the flat render by
default. This arc designs only the command line, but must give that
interface what it needs: the maps and the lighting formula.

### D-7. No cast shadows

Decided 2026-10-13 (material styling D-27). Shadows that one part casts on
another are out of scope. Baked ambient occlusion (the R1 behaviour) stands
in for them. Cast shadows are a possible later project.

### D-8. Alignment is the risk; normals are averaged; the owner checks by eye

Decided 2026-10-13 (material styling D-27). Keeping the maps aligned with
the colour sheet at small cell sizes is hard. Normals are averaged, never
palette-mapped. The arc plans for the owner's visual check.

### D-9. The normal map is written on every run, with an opt-out

Decided 2026-10-13 by the owner in this design's session ("all of your
recommendations are correct"; resolves Q-1, option A). Every run writes the
normal map beside the colour sheet, as previews are written today. It can be
turned off, by an option such as `--no-normals` and a setting such as
`normals: false` (names are Q-6's and Q-7's). The colour sheet is designed
to be lit live, and a sheet without its normal map is half an asset; the
capture cost, about 10 % more auxiliary render time ([Spike 1](#spike-1)),
is paid on every run.

### D-10. The depth map: camera depth in sheet pixels, 16-bit greyscale, off by default

Decided 2026-10-13 by the owner in this design's session (resolves Q-2, as
recommended).

- **Quantity:** camera depth, each pixel's distance toward the viewer from
  the plane through the ground point that faces the camera, positive toward
  the viewer like the normal's z. It is relative to the ground point because
  the camera's own distance changes per frame. With the pixel's position,
  `pixels_per_meter` and `ground_px`, a game recovers the pixel's position in
  camera space at every pitch. Height above the ground is not stored; it
  follows from depth at any pitch above 0.
- **Units:** sheet pixels, one unit being `1 / pixels_per_meter` metres, the
  same units as the pixel's x and y.
- **Encoding:** a 16-bit greyscale PNG, `value = 32768 + round(16 · depth)`,
  in 1/16-pixel steps; 0 is reserved for "no surface", so depths from
  −2047.9375 to +2047.9375 pixels are encodable.

*Corrected by Review 1 (R-1, R-3, R-5):* the first draft said this range
covers "any cell up to the 4096 limit". It does not: fitting bounds only a
subject's extent on screen, never its depth, so a valid fit can hold depths
outside it. What happens then is D-21.
`round` is half up: `value = 32768 + floor(16 · depth + ½)`. Depth is
`depth = (ground_view_z − surface_view_z) · pixels_per_meter`, where
`view_z` is the distance along the camera's viewing axis from the camera
(Cycles' *View Z Depth*) and `ground_view_z` is the ground point's, which
changes per frame ([Numerical reference](#numerical-reference)).
- **Default:** off; written only when asked (D-3).

### D-11. Normal and depth come from the existing auxiliary render

Decided 2026-10-13 by the owner in this design's session (resolves Q-8, as
recommended). The auxiliary Cycles render that gives the material ID and
shade also gives the camera-space shading normal and the camera depth,
through shader outputs (AOVs) from the same camera sample, as
[Spike 1](#spike-1) proved: exact alignment with the material ID,
deterministic, colour unchanged, about 10 % more auxiliary render time. No
second render.

### D-12. Depth is captured on every run

Decided 2026-10-13 by the owner in this design's session ("yes, depth
capture alongside the run"). Every render captures depth, whether or not the
depth map is written (D-10) or a light is placed (D-13), as the material ID
and shade are captured on every run (material styling D-13). The capture job
stays independent of which maps are written and of the preview light, and
trying a light never needs a different capture.

### D-13. One optional point light, `--light X,Y,Z`, for lit previews

Decided 2026-10-13 by the owner in this design's session (resolves Q-3,
choosing a point light over the recommended directional light; the rest as
recommended). In the owner's words: "the point light is optional for the
cli" and "i think just --light is sufficient"; "no --light flag" meant a run
without the flag, "not that it doesnt exist".

- **One option, `--light X,Y,Z`,** optional. Without it, nothing is lit:
  every preview is flat, ambient only, exactly as today, and no lit preview
  is written. There is no separate directional-light option: a point light
  placed far away acts as a distant one.
- **Position:** in the camera's frame (x screen right, y screen up, z toward
  the viewer), in sheet pixels from the ground point, the depth map's units
  (D-10). The light is therefore fixed to the camera, and every direction of
  the subject sees it from the same place (V-7).
- **Per pixel,** the light's direction is from the pixel's own position,
  recovered from its place in the cell and its captured depth (D-12), to the
  light; that is why the preview uses depth.
- **Formula,** documented so a game can match it: Lambert diffuse plus
  ambient, in linear light, `lit = colour · (ambient + (1 − ambient) ·
  max(0, N · L))`, a white light, with an ambient level as the other
  control. How intensity and distance enter it is Q-9.
- **Outputs:** lit previews beside the flat ones, `<stem>.<clip>.lit.gif`,
  the flat previews unchanged; the light recorded in the JSON so
  `--settings-from` reproduces the previews (settings design D-16). Lit
  colours leave the palette, so a GIF frame may be reduced to 256 colours,
  with today's warning. No lit sheet PNG.

*Amended by D-22 (Review 1, R-2):* the name `<stem>.<clip>.lit.gif` could be
another clip's flat preview (clips `walk` and `walk.lit`); lit previews are
named `<stem>-lit.<clip>.gif` instead.
The exact calculation is under [Numerical reference](#numerical-reference).

### D-14. Light strength: no falloff, an intensity and an ambient level

Decided 2026-10-13 by the owner in this design's session ("recommended for
all"; resolves Q-9, option A). The light does not fade with distance:
brightness depends only on the angle between the surface and the direction
to the light, so far away it acts as the sun and up close as a local light.
`--light-intensity I` (default 1, multiplying the diffuse term) and
`--light-ambient A` (default 0.3, how bright a surface facing away from the
light is) set its strength. In linear light, per channel:
`lit = colour · min(1, A + (1 − A) · I · max(0, N · L))`.

### D-15. A pixel's normal averages every surface sample in its block

Decided 2026-10-13 by the owner in this design's session (resolves Q-4,
option A, as recommended). A covered pixel's normal is the sum of every
surface sample's unit normal in its `s×s` block, renormalised, whatever
material each sample shows and whatever the reduction or library: at a
material edge it blends both surfaces. A covered pixel whose block has no
surface sample faces the viewer, `(0, 0, 1)`, encoded `(128, 128, 255)`.
The owner's check on small cells (D-8) decides whether anything finer is
needed.

*Completed by Review 1 (R-4):* a block whose normals sum to (nearly)
nothing, `|Σn| < 10⁻⁶`, is treated as a block with no sample and faces the
viewer, so no pixel's normal is undefined.

### D-16. Normal textures do not reach the normals, for now

Decided 2026-10-13 by the owner in this design's session (resolves Q-5, as
recommended). The normals are the model's geometry only, its interpolated
vertex normals; a glTF material's normal texture is ignored, as every
material property is for the ID and shade. Fine painted detail mostly
averages away within one sprite pixel, and the review model has none.
Deferred until a model needs it.

### D-17. The files and the JSON record

Decided 2026-10-13 by the owner in this design's session ("i like all of
your recommendations, these are approved"; resolves Q-6, as proposed).

- `<stem>.normal.png`, on every run (D-9): an 8-bit RGBA PNG the size of
  the sheet, in its layout. A covered pixel holds `round((n + 1) / 2 · 255)`
  per component with alpha 255; every pixel transparent in the colour sheet
  is `(0, 0, 0, 0)`, so the two alphas are identical.
- `<stem>.depth.png`, when asked (D-10): a 16-bit greyscale PNG the size of
  the sheet, 0 wherever the colour sheet is transparent.
- `<stem>.<clip>.lit.gif`, when a light is placed (D-13); *named
  `<stem>-lit.<clip>.gif` by D-22.*
- All are published all-or-nothing with the sheet. As today, a run replaces
  only the files it writes: turning a map off leaves an earlier run's file.
- The JSON gains a top-level `maps` record after `image`, each map's base
  file name or `null`:
  `{"normal": {"file": "hero.normal.png"}, "depth": null}`. The encodings
  are fixed by the design and named by the schema, not repeated per sheet.
  The new settings (D-18) sit inside `settings`, in the fingerprint, and
  reload with `--settings-from`. Any fixed parameter the normal and depth
  capture adds joins `generator.shade`'s technique record.
- Each slice that changes the record bumps the sheet schema, from
  `moskophoros.sheet/7`, as the settings arc did; each bump stops the
  previous schema loading (settings design D-24).

### D-18. Every new control is a setting

Decided 2026-10-13 by the owner in this design's session (resolves Q-7, as
proposed). Under settings design D-2's layers, each is a setting that files
may set and every sheet records whether or not it is used, as `shade` is:

| Setting | Options | Shipped default |
|---|---|---|
| `normals` | `--normals`, `--no-normals` | `true` (D-9) |
| `depth` | `--depth`, `--no-depth` | `false` (D-10) |
| `light.position` | `--light X,Y,Z`, `--no-light` | `null`: no light (D-13); otherwise three finite numbers |
| `light.intensity` | `--light-intensity I` | `1.0`, finite, 0 or greater (D-14) |
| `light.ambient` | `--light-ambient A` | `0.3`, 0 to 1 (D-14) |

```yaml
normals: true
depth: false
light:                    # set any of them; the rest fall through
  position: [-20, 30, 40] # sheet pixels from the ground point; null: no light
  intensity: 1.0
  ambient: 0.3
```

Each value is validated exactly as its option is, in a settings file and in
a reused sheet as on the command line (design §Option validation; *made
explicit by Review 2, S-3*). `light` merges key by key across layers, as
`shade` does. `--no-light`
drops a reused or configured light, as `--no-palette` does. Without
previews (`--no-preview`, `previews: false`), no lit preview is written
either, and a placed light is recorded but unused, with a warning saying
so.

### D-19. A pixel's depth averages the same samples; a gap takes its neighbours

Decided 2026-10-13 by the owner in this design's session (resolves Q-10, as
proposed). A covered pixel's depth is the mean depth of the surface samples
its normal averages (D-15), rounded to D-10's 1/16-pixel step. A covered
pixel with no surface sample takes the mean depth of its covered 8
neighbours that have samples, else 0, the ground point's plane. The lit
preview uses the same reduced depth.

*Completed by Review 1 (R-3):* the neighbours' mean is taken over their
unrounded mean depths, then rounded as D-10 rounds.

### D-20. The arc is delivered as slices LIT-1 to LIT-6

Decided 2026-10-13 by the owner in this design's session ("i approve this,
get the doc in order, marked ready"). The owner approved the
[Delivery plan](#delivery-plan)'s six slices, the [Epic
contract](#epic-contract)'s goal and done condition, and the design as ready
for issue processing. Each slice is one issue and one pull request, except
LIT-6, a documentation-only acceptance step with no pull request, as
material styling MAT-7 was: its renders stay outside the repository, and its
only repository artifact is `docs/acceptance/lighting-sheet.md`, published
with `docs-push`. LIT-4 and LIT-5 may land in either order after LIT-3.

### D-21. Depth outside the encodable range is an overflow error

Decided 2026-10-13 by the owner in this design's session ("recommended for
all three"; resolves Q-11, option A). When the depth map is written or a
light is placed (the lit preview uses the encoded depth), a covered pixel
whose depth falls outside D-10's −2047.9375 to +2047.9375 pixels is an
overflow error (exit 4), like a subject that does not fit a fixed cell. It
is raised before anything is published, and names the clip, direction and
sample time, the measured depth range in sheet pixels and the supported
range, and suggests a smaller `--ppm`. Depth is never clamped or rescaled.
Capture and reduction hold any depth, so a run that writes no depth map and
places no light is never checked. *Amended by D-24:* "a light is placed"
means lit previews are written, so previews must also be on.

### D-22. Lit previews are named `<stem>-lit.<clip>.gif`

Decided 2026-10-13 by the owner in this design's session (resolves Q-12,
option A; amends D-13 and D-17). A clip's lit preview is its flat preview's
name with `<stem>` replaced by `<stem>-lit`: the same cleaned clip name and
the same `-2`, `-3` suffix the flat rule (design §CLI) gives it, so
`hero.walk.gif` and `hero-lit.walk.gif`. Every flat name begins `<stem>.`
and every lit name `<stem>-lit.`, so within a run a lit preview can never
replace a flat one, and a game finds each lit name by the flat rule alone.

### D-23. The ordinary look keeps its studio light

Decided 2026-10-13 by the owner in this design's session (resolves Q-13,
option A). D-1's flat colour sheet is the material look: materials drawn
from a library's ramps, banded by the ambient shade. The ordinary look,
used without a library or for a material without a ramp, keeps Workbench's
camera-fixed studio light and its bytes, as material styling D-22 left it.
A lit preview over it applies directional light a second time; that is
accepted and noted, not corrected, in this arc.

### D-24. The depth range is checked only for what a run produces

Decided 2026-10-13 by the owner in this design's session (resolves Q-14,
option A; amends D-21). The depth range is checked when the depth map is
written, or when previews are on and a light is placed, since only then is
encoded depth used. With previews off, a placed light imposes nothing: it is
recorded but unused, with D-18's warning, and a depth beyond the range does
not fail the run.

### D-25. The revised design is ready for issue processing

Decided 2026-10-13 by the owner in this design's session ("yes i approve it,
anything else i will work out during the solve process"). The owner
re-approved the design after Reviews 1 and 2, with D-20's six slices and
their added obligations, as ready for issue processing, and asked for no
further Codex review. Anything else is settled while solving the slices.

## Open questions

None open. Q-14, raised by [Review 2](#review-2), is resolved by D-24. Q-11, Q-12 and Q-13, raised by [Review 1](#review-1), are resolved by D-21, D-22 and D-23. Resolved: Q-6 by D-17, Q-7 by D-18, Q-10 by D-19; Q-1 by D-9, Q-2 by D-10, Q-3 by D-13
(its remainder by D-14), Q-4 by D-15, Q-5 by D-16, Q-8 by D-11, Q-9 by
D-14.

### Q-1. Is the normal map written on every run, or only when asked?

**Resolved by D-9** (option A). Kept for the alternative.

D-2 makes the normal map *the* lighting sheet; D-3 makes only the depth map
optional. Options:

- **A. Always, with an opt-out** (like previews: `--no-normals`, a
  `normals: false` setting). Every sheet has its lighting sheet; the capture
  cost is paid on every run.
- **B. Only when asked** (`--normals`). Today's outputs are unchanged unless
  asked for.

**Recommendation: A**, since the colour sheet is now designed to be lit
live, and a sheet without its normal map is half an asset. Affects every
slice's outputs, settings and cost.

### Q-2. What does the depth map store, and how?

**Resolved by D-10** (every recommendation below). Kept for the
alternatives.

- **Quantity.** *Camera depth*: each pixel's distance toward the viewer
  from the plane through the ground point facing the camera, positive toward
  the viewer like the normal's z. It must be relative to the ground point:
  the camera's own distance changes per frame ([Spike 1](#spike-1)). With the
  pixel's position and the recorded `pixels_per_meter` and `ground_px`, a
  game recovers the pixel's full position in camera space, at every pitch.
  *Height above the ground point*: easier to read, but at pitch 0 it is just
  the screen row, so it cannot place a pixel in depth. **Recommendation:
  camera depth**; height follows from it at any pitch above 0.
- **Units.** Sheet pixels (1 unit = `1 / pixels_per_meter` m), so depth is in
  the same units as the pixel's x and y, or metres. **Recommendation: sheet
  pixels.**
- **Encoding.** A 16-bit greyscale PNG (`value = 32768 + round(16 · depth)`,
  1/16 pixel steps, ±2048 pixels, covering any cell up to the 4096 limit
  — *not so: D-10's correction and D-21 govern, Review 1 R-1 and Review 2*);
  or an 8-bit RGBA PNG with the 16-bit value split across red and green, for
  games that load only 8-bit textures. Transparent pixels need a reserved
  value or a separate alpha. **Recommendation: 16-bit greyscale, 0 reserved
  for "no surface"**. The spike measured the robot's depth at −10 to +30
  pixels at its 48 × 48 fit, and a 178-pixel span at 40 px/m, well inside
  ±2048 (sign corrected by Review 1, R-5).
- **Default:** off, written only when asked (D-3 calls it optional).

### Q-3. What is the light flag, and what does the lit preview write?

**Resolved by D-13**, except the light's intensity and falloff and the
ambient level's default, which are [Q-9](#q-9-how-strong-is-the-light-and-does-it-fall-off-with-distance).
The owner chose a point light over the recommended directional one. Kept
for the alternatives.

- **Kind of light.** A **directional** light needs only the normal map. A
  **point** light at a position needs the depth map too. **Recommendation:
  directional first; a point light only when depth is written**, perhaps in
  a later slice.
- **Form and units.** For a directional light, `--light AZ,EL` in degrees,
  camera-relative: azimuth measured on screen like the direction angles,
  elevation toward the viewer. A point light would add a position in sheet
  pixels relative to the ground point. Colour and intensity: **a white light
  of fixed strength first**, with an ambient level as the only other
  control.
- **Formula.** Documented, so a game can match it. **Recommendation:**
  Lambert diffuse plus ambient, in linear light:
  `lit = colour · (ambient + (1 − ambient) · max(0, N · L))`.
- **What it writes.** Lit previews beside the flat ones,
  `<stem>.<clip>.lit.gif`, flat previews unchanged; the light recorded in the
  JSON so `--settings-from` reproduces the previews (settings design D-16).
  Lit colours are no longer on the palette, so a GIF frame may need
  reducing to 256 colours, with today's warning. A lit sheet PNG is not
  proposed.

### Q-4. Which samples does a pixel's normal average?

**Resolved by D-15** (option A). Kept for the alternative.

- **A. Every surface sample in the block**, renormalised. Geometrically
  true; at a material edge the normal blends both surfaces.
- **B. Only the samples of the identity the colour pixel was drawn from**,
  when a material library chose one. Matches the colour exactly; differs from
  A only at material edges.

And for a covered pixel with no surface sample in its block: facing the
viewer `(0, 0, 1)`, or the mean of its covered neighbours. **Recommendation:
A, and facing the viewer**, as the simplest rule that never invents
geometry; the owner's check on small cells decides whether B is needed.

### Q-5. Do material properties perturb the normals?

**Resolved by D-16.**

glTF materials can carry a normal texture. Today no material property reaches
the ID and shade. **Recommendation: no**, the model's geometry only, for
now; textured normal detail is mostly lost when averaged into one sprite
pixel, and the review model has none. Deferred until a model needs it.

### Q-6. What files does a run write, and how does the JSON describe them?

**Resolved by D-17.**

**Proposal:**

- **Files,** beside the sheet, published all-or-nothing with it as every
  output is today:
  - `<stem>.normal.png`: an 8-bit RGBA PNG the size of the sheet, in its
    layout. A covered pixel holds `round((n + 1) / 2 · 255)` per component
    (D-2, §Direction space) with alpha 255; every pixel transparent in the
    colour sheet is `(0, 0, 0, 0)`, so the two alphas are identical.
  - `<stem>.depth.png`, when asked: a 16-bit greyscale PNG the size of the
    sheet (D-10), 0 wherever the colour sheet is transparent.
  - `<stem>.<clip>.lit.gif`, when a light is placed (D-13).
  - As today, a run replaces only the files it writes: turning a map off
    leaves an earlier run's map file where it was.
- **JSON,** schema `moskophoros.sheet/8`:
  - a top-level `maps` record after `image`:
    `{"normal": {"file": "hero.normal.png"}, "depth": null}`, each map's base
    file name or `null` when it was not written. The encodings are fixed by
    the design and named by the schema, not repeated in each sheet.
  - the new settings (Q-7) inside `settings`, so they are in the fingerprint
    and reload with `--settings-from`.
  - `generator.shade`'s technique record gains whatever fixed parameters the
    normal and depth capture has, as the shade's did.
- **Schema bumps:** each slice that changes the record bumps the schema, as
  the settings arc did; under settings design D-24, a bump stops the
  previous schema loading.

### Q-7. Which of these are settings, and what are the options?

**Resolved by D-18.**

**Proposal:** all of them are settings, under settings design D-2's layers,
so the owner's user file can, for example, turn depth on or place a default
light; every setting is recorded in the sheet whether or not it is used,
like `shade`.

| Setting | Options | Shipped default |
|---|---|---|
| `normals` | `--normals`, `--no-normals` | `true` (D-9) |
| `depth` | `--depth`, `--no-depth` | `false` (D-10) |
| `light.position` | `--light X,Y,Z`, `--no-light` | `null`: no light (D-13) |
| `light.intensity` | `--light-intensity I` | `1.0`, finite, 0 or greater (D-14) |
| `light.ambient` | `--light-ambient A` | `0.3`, 0 to 1 (D-14) |

```yaml
normals: true
depth: false
light:                    # set any of them; the rest fall through
  position: [-20, 30, 40] # sheet pixels from the ground point; null: no light
  intensity: 1.0
  ambient: 0.3
```

`light` merges key by key across layers, as `shade` does. `--no-light`
drops a reused or configured light, as `--no-palette` does. Without
previews (`--no-preview`), no lit preview is written either, and a placed
light is recorded but unused, with a warning saying so.

### Q-8. How does Blender produce the normal and depth?

In the same Cycles render as the ID and shade (shader outputs into a float
image), or a second render per frame. **Resolved by D-11**: the first,
proved by [Spike 1](#spike-1).

### Q-9. How strong is the light, and does it fall off with distance?

**Resolved by D-14** (option A, ambient 0.3). Kept for the alternatives.

D-13 places a point light; the owner asked for its strength to be
controllable: "we should scale the light intensity by the distance, so that
up close its a small point light, and at a distance its like the sun, or we
could just have an --light-intensity flag as well and set it to whatever we
want, that would be more versitile."

- **A. No falloff, plus `--light-intensity I`** (default 1, multiplying the
  diffuse term). Brightness depends only on the angle to the light. Far
  away, the light's direction is the same for every pixel, so it acts as
  the sun by itself; up close, the direction changes across the sprite, so
  near surfaces facing it light and others do not. Intensity is set by
  hand.
- **B. Inverse-square falloff, plus `--light-intensity`.** Physically
  correct, and up close it gives a bright spot fading across the sprite. But
  far away it gets dim, so a "sun" needs a very large intensity, which is
  hard to choose by hand.
- **C. Falloff over a stated radius** (`--light-radius`): full strength
  within it, fading beyond. A common game choice; one more option.

The formula with intensity becomes `lit = colour · min(1, ambient + (1 −
ambient) · I · max(0, N · L) · falloff)`, clamped per channel in linear
light.

The **ambient level**, how bright a surface facing away from the light is,
needs a default. **Recommendation: 0.3**, the owner adjusting it by eye; and
an option to set it, such as `--light-ambient`.

**Recommendation: A**, the most predictable to tune, and it does what the
owner described: near, a local light; far, the sun.

### Q-10. How does a pixel's depth reduce, and with no sample?

**Resolved by D-19.**

D-15 settles normals; depth needs the same. **Proposal:** a covered pixel's
depth is the mean depth of the same surface samples its normal averages,
rounded to the 1/16-pixel step (D-10). For a covered pixel with no surface
sample, "facing the viewer" has no depth equivalent, and 0 (the ground
point's plane) can be far from the surface around it (a surface 30
pixels in front of it). So: the mean depth of its covered 8 neighbours that have samples,
else 0. The lit preview uses the same reduced depth.

### Q-11. What happens to depth beyond the encodable range?

**Resolved by D-21** (option A). Kept for the alternatives.

Raised by Review 1 (R-1). Fitting bounds a subject's extent on screen, never
its depth, so a valid fit can hold depths beyond D-10's ±2047.9375 pixels:
the reviewer's example, a 1 m square 100 m in front of the ground point at
64 px/m in a 128 × 128 cell, has depth 6400. Real subjects at the owner's
cell sizes are tens of pixels deep (the robot: −10 to +30), so this is an
edge case, but its behaviour must be defined. Only the encoding has a
range: capture and reduction hold any depth, so a run that writes no depth
map and places no light is never affected.

- **A. Fail loudly.** When the depth map is written or a light is placed
  (the preview uses the encoded depth), any covered pixel outside the range
  is an overflow error (exit 4), before anything is published, naming the
  clip, direction and sample time, the measured depth range in sheet pixels
  and the supported one, and suggesting a smaller `--ppm`. Like today's cell
  overflow: never a silently wrong map.
- **B. Clamp** to the range, with a warning. Every run succeeds, but the
  clamped pixels are mislit.
- **C. A per-sheet scale:** the depth step is chosen per sheet so the
  measured range fits, and recorded in the JSON (`maps.depth.scale`). Always
  succeeds; a game must read the scale, and precision varies by sheet.

**Recommendation: A**, as V-7 and V-11 treat every other misfit. Affects
LIT-4 and LIT-5.

### Q-12. How are lit previews named, so they never replace a flat one?

**Resolved by D-22** (option A). Kept for the alternative.

Raised by Review 1 (R-2). A cleaned clip name may contain dots, so for clips
`walk` and `walk.lit` the flat previews are `hero.walk.gif` and
`hero.walk.lit.gif`, and D-13's lit preview of `walk` would also be
`hero.walk.lit.gif`, replacing a flat one.

- **A. `<stem>-lit.<clip>.gif`.** Every flat name starts `<stem>.`, every
  lit name `<stem>-lit.`, so within a run they can never meet. Lit names
  take the flat rule's cleaned names and `-2`, `-3` suffixes unchanged, so
  each clip's lit name is its flat name with `<stem>` replaced by
  `<stem>-lit`: `hero.walk.gif` and `hero-lit.walk.gif`. No exceptions to
  remember.
- **B. Keep `<stem>.<clip>.lit.gif` with a collision rule:** every flat name
  is reserved first (comparing ASCII case-insensitively, as today); a lit
  name that collides takes the smallest free suffix,
  `<stem>.<clip>.lit-2.gif`, in sheet order. Usually the approved name; on a
  collision, a name a game cannot guess without the rule.

**Recommendation: A.** Affects LIT-5.

### Q-13. The ordinary look is still studio-lit: does D-1 cover it?

**Resolved by D-23** (option A). Kept for the alternative.

Raised by Review 1 (its closing note). D-1 says the colour sheet stays
flat. That holds for materials drawn from a library's ramps, banded by the
ambient shade. But the **ordinary look**, used without a library or for a
material without a ramp, is still Workbench's camera-fixed studio light,
which is directional (material styling D-22 left it unchanged). A lit
preview over it applies directional light twice.

- **A. Leave it:** the ordinary look keeps today's bytes; D-1 is read as
  applying to the material look; the design notes the double lighting.
- **B. Make the ordinary look flat too,** in a later arc: it would change
  every existing ordinary sheet.

**Recommendation: A**, recorded as a scope note; B only if the owner wants
library-less sheets to be lit live as well.

### Q-14. Does a light that draws nothing still trigger the depth check?

**Resolved by D-24** (option A). Kept for the alternative.

Raised by Review 2 (S-1). D-18 says that with previews off a placed light
is "recorded but unused, with a warning". D-21 checks the depth range
whenever "a light is placed". They disagree for one run: previews off, depth
map off, a light configured (or reused from a sheet), and a depth outside
±2047.9375 pixels. D-21 as written fails it with exit 4 although nothing
would use the depth; D-18 says the light is simply unused.

- **A. Check only what is produced:** the range is checked when the depth
  map is written, or when previews are on and a light is placed. With
  previews off, a placed light imposes nothing, as D-18 says.
- **B. A placed light always imposes the limit,** even with previews off,
  stated beside D-18's "unused".

**Recommendation: A.** The check exists to keep a written file or preview
from being wrong; a run that writes neither should not fail on it. Tests in
LIT-5: a configured and a reused light with `--no-preview --no-depth`, and
depth-on and previews-on controls.

## Verification strategy

- **Pure tests:** block reduction of normals and depth (renormalising,
  coverage from the colour, both no-sample fallbacks, transparent pixels,
  independence from reduction and library), encoding round trips at the
  ends of each range, the light formula (a light far away matches a
  distant one), JSON records, settings layers and reuse.
- **Numerical reference** (Review 1): half-up rounding of normal bytes and
  depth codes, including a depth of exactly 1/32 pixel (code 32769);
  the reference vectors; a cancelling block, `(1, 0, 0)` with `(−1, 0, 0)`,
  facing the viewer; a light at a pixel's centre giving ambient only; no
  NaN anywhere, including lights very far (`1e200`) and very near
  (`1e-200`) giving the same result as a moderate light in the same
  direction (Review 2, S-3); and a reconstruction check, the lit preview
  recomputed from the **exported** colour, normal and depth PNGs (decoded as
  a game would, with a nonzero signed depth) matching the written preview's
  frames after the GIF handling. That check needs the depth map's exporter,
  so it belongs to whichever of LIT-4 and LIT-5 lands second (Review 2,
  S-2).
- **Blender tests** on generated fixtures: a plane at a known angle reads
  its exact camera-space normal at several pitches and directions; a
  sphere's normals match the analytic normal within a stated angle; a
  plane at a known position reads its depth; the normal and depth coverage
  equal the material-ID coverage pixel for pixel; repeat renders are
  identical; the colour bytes are unchanged by the new passes.
- **Old output preserved:** the colour sheet and flat previews of every
  existing look stay byte-identical; the JSON too, except the schema, the
  new records, and the fingerprint, which changes because it covers them
  (Review 1, R-6) and is checked against the new complete `generator` and
  `settings`. Same-version self-reproduction stays byte for byte.
- **Reproduction:** the self-reproduction test (settings design D-16)
  extends to the normal map, depth map and lit previews.
- **The owner's eye** (D-8, V-12): normal maps, depth maps and lit previews
  of the acceptance model at the owner's cell size and a smaller one, with
  the light in several places, judged for alignment and plausibility
  (LIT-6). No test claims a look is good.

## Review 1

Codex (mosk-solver-27) reviewed this design at `8d65f65` on 2026-10-13:
`~/.local/share/moskophoros-acceptance/lighting-design/review-codex-1.md`,
with its probes in `review/` beside it. Each finding was checked against
the code and the document, and each holds.

| Finding | Severity | Disposition |
|---|---|---|
| R-1. Depth beyond the fixed encoding: fitting never bounds depth, so D-10's "any cell" claim was false | blocking | Claim corrected in D-10; capture and reduction hold any depth; decision D-21 (overflow error, exit 4); tests in LIT-1, LIT-2, LIT-4, LIT-5 |
| R-2. `<stem>.<clip>.lit.gif` can replace another clip's flat preview | blocking | Decision D-22: lit previews are `<stem>-lit.<clip>.gif`; tests in LIT-5 |
| R-3. No complete numerical contract for the lit preview | should fix | Fixed: [Numerical reference](#numerical-reference) (decode and renormalise, pixel centres, half-up rounding, the preview uses the encoded maps), D-19's fallback rounding; reference vectors and a reconstruction check in LIT-2 and LIT-5 |
| R-4. A cancelling normal sum and a light at a pixel were undefined | should fix | Fixed: a sum under 10⁻⁶ faces the viewer (D-15 note); a light at a pixel gives ambient only; tests in LIT-2 and LIT-5 |
| R-5. The spike's depth range had the opposite sign to D-10 | should fix | Fixed: the conversion stated in D-10, the spike's figures negated with a sign note, the Q-10 example corrected; signed tests in LIT-1 and LIT-4 |
| R-6. Old JSON comparison omitted the recomputed fingerprint | minor | Fixed in [Verification strategy](#verification-strategy) and LIT-3 |

The review's closing note, that the ordinary look is still studio-lit, is
settled by D-23: it keeps its studio light, as a noted scope limit.

## Review 2

Codex (mosk-solver-27, in a fresh context) re-reviewed this design at
`c0f81fa` on 2026-10-13:
`~/.local/share/moskophoros-acceptance/lighting-design/review-codex-2.md`,
with its probes in `review-2/` beside it. It found R-1 to R-6 resolved, and
three new should-fix findings, each checked and each holding.

| Finding | Severity | Disposition |
|---|---|---|
| S-1. D-18's unused light and D-21's depth check disagree when previews and depth are off | should fix, owner | Decision D-24: the range is checked only for a depth map or lit previews actually produced; tests in LIT-5 |
| S-2. LIT-5 may land before LIT-4 but its test needed the exported depth map | should fix | Fixed: LIT-5 checks reconstruction in memory; the production check from the exported PNGs goes to whichever of LIT-4 and LIT-5 lands second, before LIT-6; the owner's either-order choice kept |
| S-3. A plain float64 norm overflows or underflows for very far or very near lights | should fix | Fixed: scaled normalisation in [Numerical reference](#numerical-reference) step 5; tests with lights at `1e200` and `1e-200`; the finite-numbers rule stated for `light.position` in settings files and reuse |
| Q-2 still repeated the old "any cell" claim | note | Annotated: D-10's correction and D-21 govern |

## Delivery plan

*Approved by the owner on 2026-10-13 (D-20).* Each slice is one issue and one
pull request, except LIT-6. Every slice amends `docs/design.md` for what it
delivers, in its own pull request, since tests read the design.

### LIT-1. Capture normal and depth buffers on every render

- **Outcome:** every render writes, per frame, a camera-space normal buffer
  and a depth buffer from the existing auxiliary Cycles render, validated by
  the launcher and decoded by the command into the frame's named buffers.
- **Scope:** the AOVs, EXR save and standard-library readback of
  [Spike 1](#spike-1) in `blender_script.py`, with every setting restored;
  `normal/` and `depth/` buffers at the supersampled size, their exact
  encoding chosen here and recorded in the design (enough precision that
  averaging is not limited by it: at least 16 bits per normal component,
  and depth relative to the ground point's camera depth); the result
  contract making them mandatory; the launcher's validation (encoding,
  unit length, coverage identical to the material ID's); decoding into
  `ImageFrame.buffers` as arrays stylize can take; design §Capture,
  §result format, §Frames into stylize and §Deferred amended.
- **Phase:** 1
- **Depends on:** `none`
- **Ordering:** `critical path`
- **Relevant decisions:** D-2, D-11, D-12, D-16
- **Acceptance signals:** Blender tests on generated fixtures: plane
  normals within a stated tolerance of exact at pitches 0°, 30° and 90° and
  two directions; a smooth sphere's interpolated normals within a stated
  mean error; a plane's depth; normal and depth coverage identical to the
  material ID's; repeat renders identical; colour, material-ID and shade
  buffers byte-identical to the base commit (local-validation report).
  From Review 1: a **signed** depth test, one surface in front of the
  ground point's plane and one behind it, reading positive and negative
  respectively, repeated at two different camera distances (R-5); and
  depths far beyond the encodable range carried without error, since
  capture is never limited by it (R-1).
- **Out of scope:** reducing or exporting the maps; any setting or option.
- **Open questions:** `None`

### LIT-2. Reduce normals and depth to the sheet's pixels

- **Outcome:** each frame's normals and depth are reduced to the output
  grid with the colour sheet's coverage, and travel with the reduced colour
  frame through cleanup to export.
- **Scope:** pure reductions in `imageops` (D-15, D-19); stylize returning
  the reduced maps beside the colour, still releasing every supersampled
  buffer before the next frame; cleanup passing them through; design
  §Frames into stylize, §Pipeline amended.
- **Phase:** 2
- **Depends on:** LIT-1
- **Ordering:** `critical path`
- **Relevant decisions:** D-8, D-15, D-19
- **Acceptance signals:** pure tests of both reductions, renormalising,
  both fallbacks and transparent pixels; reduced map alpha equal to the
  colour's under every look; outputs of every existing look unchanged.
  From Review 1: half-up encoding (R-3); the cancelling-block and
  near-zero-sum fallback (R-4); the neighbour fallback's rounding over
  unrounded means (R-3); depth beyond the encodable range reduced without
  error (R-1).
- **Out of scope:** writing any file; settings.
- **Open questions:** `None`

### LIT-3. Write the normal map, record it and reuse it

- **Outcome:** every run writes `<stem>.normal.png` beside the sheet unless
  turned off, named in the JSON's `maps` record and reproduced by
  `--settings-from`.
- **Scope:** the map's encoding and layout (D-17); the `normals` setting,
  `--normals` and `--no-normals` (D-18); `maps` and `settings.normals` in
  the JSON and fingerprint; the schema bump; all-or-nothing publishing;
  design §CLI, §Settings files, §Export and §Reuse amended.
- **Phase:** 3
- **Depends on:** LIT-2
- **Ordering:** `critical path`
- **Relevant decisions:** D-2, D-9, D-17, D-18
- **Acceptance signals:** the normal map's alpha identical to the colour
  sheet's; encoding round trips; `--no-normals` writes none and records
  `null`; self-reproduction byte-identical; the colour sheet and flat
  previews of every existing look byte-identical to before the arc, and
  their JSON identical except the schema, new records and the recomputed
  fingerprint (R-6).
- **Out of scope:** depth; light.
- **Open questions:** `None`

### LIT-4. Write the optional depth map

- **Outcome:** `--depth` (or `depth: true`) writes `<stem>.depth.png`
  beside the sheet, named in `maps`, reproduced by `--settings-from`.
- **Scope:** the 16-bit encoding (D-10, D-17); the `depth` setting,
  `--depth` and `--no-depth`; recording; the schema bump; design amended.
- **Phase:** 4
- **Depends on:** LIT-3
- **Ordering:** `not on the critical path`; before or after LIT-5, the
  later of the two taking the next schema number and the production
  reconstruction check below
- **Relevant decisions:** D-3, D-10, D-17, D-18, D-19, D-21
- **Open questions:** `None`
- **Acceptance signals:** a plane at a known position reads its depth in
  sheet pixels within the 1/16 step; 0 exactly where the colour sheet is
  transparent; the range ends encode; self-reproduction byte-identical.
  From Review 1: the signed end-to-end check, a surface in front of the
  ground point reading a code above 32768 (R-5); depth exactly at each end
  of the range and one step beyond, the latter an overflow (exit 4) naming
  the frame and nothing published (D-21), including a
  small cell whose subject is far deeper than it is wide; a run with
  `--no-depth` and no light unaffected by the range (R-1). From Review 2
  (S-2): **if LIT-5 has already landed**, the production reconstruction
  check: the lit preview recomputed from the exported colour, normal and
  depth PNGs, with a nonzero signed depth, matches the written preview's
  frames after the GIF handling.
- **Out of scope:** the light.

### LIT-5. Light the previews with an optional point light

- **Outcome:** `--light X,Y,Z` writes lit previews,
  `<stem>-lit.<clip>.gif` (D-22), beside the unchanged flat ones; without it,
  nothing changes.
- **Scope:** the light settings and options (`light.position`,
  `light.intensity`, `light.ambient`, `--light`, `--no-light`,
  `--light-intensity`, `--light-ambient`; D-18); the formula (D-14) in
  linear light, each pixel's position from its cell position and reduced
  depth (D-13, D-19); the GIF's 256-colour reduction and warning; the
  `--no-preview` warning; recording and the schema bump; the formula
  documented in the design so a game can match it.
- **Phase:** 4
- **Depends on:** LIT-3
- **Ordering:** `not on the critical path`; before or after LIT-4, the
  later of the two taking the next schema number and the production
  reconstruction check below
- **Relevant decisions:** D-4, D-5, D-13, D-14, D-18, D-19, D-21, D-22, D-23, D-24
- **Open questions:** `None`
- **Acceptance signals:** pure tests of the formula (a light behind the
  surface gives the ambient level; a distant light matches a uniform
  direction); a light placed in a settings file and reused reproduces the
  lit previews byte for byte; the colour sheet, flat previews and maps
  identical with and without a light. From Review 1: the
  [Numerical reference](#numerical-reference)'s vectors, a light at a
  pixel's centre giving ambient only, and a reconstruction check from the
  encoded maps in memory, which LIT-5 can run alone (R-3, R-4, S-2); very
  far and very near lights giving the same result as a moderate one, and a
  non-finite light coordinate refused from the command line, a settings
  file and a reused sheet (S-3); **if LIT-4 has already landed**, the
  production reconstruction check from the exported colour, normal and
  depth PNGs (S-2); the lit preview's depth-range behaviour as
  D-21 and D-24 set, including with `--no-depth` (R-1), and a configured
  and a reused light with `--no-preview --no-depth` passing beyond the range
  with D-18's warning, against depth-on and previews-on controls that fail
  (S-1); lit and flat names never
  colliding, tested with clips `walk` and `walk.lit`, case variants
  (`Walk`, `walk`) and names already carrying `-2` suffixes, alongside
  publication rollback, under D-22's naming (R-2).
- **Out of scope:** a directional option, light colour, falloff, a lit
  sheet PNG, the owner's interface.

### LIT-6. Review normal maps and lit previews with the owner

- **Outcome:** the owner's verdict on the arc's output, recorded in
  `docs/acceptance/lighting-sheet.md`.
- **Scope:** renders of RobotExpressive under the owner's look (their user
  settings) at their cell size, 48 × 48, and a smaller one; each colour
  sheet beside its normal map, depth map and an overlay showing their
  alignment; lit previews with the light in several places, near and far,
  each image labelled with what it shows and the exact command. Review 1
  asks that material boundaries and fallback pixels be shown clearly at
  native cell size, since alignment tests cannot judge them (D-8). Delivered
  as a documentation-only acceptance step with no pull request, as
  material styling MAT-7 was; renders stay outside the repository.
- **Phase:** 5
- **Depends on:** LIT-3, LIT-4, LIT-5, including the production
  reconstruction check that the later of LIT-4 and LIT-5 carries
- **Ordering:** `critical path`
- **Relevant decisions:** D-8
- **Acceptance signals:** the owner's recorded verdict.
- **Out of scope:** changing defaults or the owner's settings.
- **Open questions:** `None`

## Source notes

The owner, 2026-10-13, as recorded in material styling D-27:

> moskophoros is going to create a sprite that is flatly shaded, only R1 and
> R2, basic ambient light

> … containing information on the geometry of the object … and we will then
> be able to handle any sort of lighting in our 2D world

> for the cli interface, just output flat, but give the optional flag to
> place the light.
