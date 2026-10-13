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

Design state: `exploring`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

*Not yet proposed.* The slices are drafted once the open questions below are
settled; a candidate shape is under [Delivery plan](#delivery-plan).

## Epic contract

*Proposal, not yet signed off.*

- **Goal:** beside every colour sheet, the owner gets a normal map (and, when
  asked, a depth map) with the same layout, cells and frames, which a game
  shader can light live; and can preview the sprites lit by a light they
  place, while the exported colour sheet stays exactly as flat as without
  the arc.
- **Done when:** the automated checks prove the maps' alignment and
  encoding; every existing look writes the same colour sheet pixels as
  before the arc; and the owner reviews normal maps and lit previews of the
  acceptance model by eye and approves them (V-12).
- **Users and operators:** the owner producing game art; games that read the
  maps; agents maintaining the tool.
- **Arc label:** None proposed.

## Current state and evidence

Checked on 2026-10-13 at `master` `44e5891`, by reading only. The capture
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

*Proposal, pending the open questions.*

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

## Design

**Proposal throughout this section**, except where a decision is cited.

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

**Proposed capture**, from the spike: the existing auxiliary Cycles render
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
subject's reach), so raw camera depth is meaningless across frames; depth
relative to the ground point spans 4.45 m, −30 to +10 sheet pixels at
9.06 px/m, or a 178-pixel span at 40 px/m.

*Findings:* a surface seen from behind reads its normal flipped toward the
viewer, since Cycles flips the shading normal; the multilayer EXR always
carries the combined colour too.

**Outcome:** the AOV technique meets the contract above on these fixtures,
for about 10 % more auxiliary render time, which stays a small part of a
frame's capture.

### Reducing a block

For each `s×s` block whose colour pixel is covered:

- **Normal:** the sum of the block's sampled unit normals, renormalised
  ([Q-4](#q-4-which-samples-does-a-pixels-normal-average)). Never
  palette-mapped or voted (D-8).
- A transparent colour pixel is transparent in every map.
- A covered colour pixel whose block has no normal sample (a thin edge the
  centre samples missed) needs a fallback (Q-4).

### Outputs

Candidate names, beside the sheet: `<stem>.normal.png`, `<stem>.depth.png`,
and lit previews `<stem>.<clip>.lit.gif`. The JSON gains a description of
each map and the light, under a schema bump to `moskophoros.sheet/8`
([Q-6](#q-6-what-files-does-a-run-write-and-how-does-the-json-describe-them)).

## Decisions

These are the owner's, from material styling D-27 (2026-10-13, typed in the
moskophoros manager's terminal), recorded here as this arc's starting
point. They are not reopened.

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
  −2047.9375 to +2047.9375 pixels are encodable, covering any cell up to the
  4096 limit.
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

## Open questions

Open: Q-4, Q-5, Q-6, Q-7 and Q-9. Resolved: Q-1 by D-9, Q-2 by D-10,
Q-3 by D-13 (its remainder is Q-9), Q-8 by D-11.

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
  1/16 pixel steps, ±2048 pixels, covering any cell up to the 4096 limit);
  or an 8-bit RGBA PNG with the 16-bit value split across red and green, for
  games that load only 8-bit textures. Transparent pixels need a reserved
  value or a separate alpha. **Recommendation: 16-bit greyscale, 0 reserved
  for "no surface"**. The spike measured the robot's depth at −30 to +10
  pixels at its 48 × 48 fit, and a 178-pixel span at 40 px/m, well inside
  ±2048.
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

glTF materials can carry a normal texture. Today no material property reaches
the ID and shade. **Recommendation: no**, the model's geometry only, for
now; textured normal detail is mostly lost when averaged into one sprite
pixel, and the review model has none. Deferred until a model needs it.

### Q-6. What files does a run write, and how does the JSON describe them?

Candidate names under [Outputs](#outputs). The JSON would gain a `maps`
record (each map's file and encoding: axes and byte formula for normals;
quantity, unit, zero and scale for depth), settings for which maps are
written and the preview light, a schema bump to `moskophoros.sheet/8`
(settings design D-24: `/7` sheets then stop loading), and reuse of all of
it through `--settings-from`. Depends on Q-1 to Q-3.

### Q-7. Which of these are settings?

Under settings design D-2's layers: whether each map is written, and the
preview light, as settings that files may set and sheets record; or command
options only. **Recommendation: settings**, like `previews`, so the owner's
user file can turn depth on or place a default light. Depends on Q-1 to Q-3.

### Q-8. How does Blender produce the normal and depth?

In the same Cycles render as the ID and shade (shader outputs into a float
image), or a second render per frame. **Resolved by D-11**: the first,
proved by [Spike 1](#spike-1).

### Q-9. How strong is the light, and does it fall off with distance?

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

## Verification strategy

*Proposal.*

- **Pure tests:** block reduction of normals and depth (renormalising,
  coverage from the colour, the no-sample fallback, transparent pixels),
  encoding round trips, the light formula, JSON records and reuse.
- **Blender tests** on generated fixtures: a plane at a known angle reads
  its exact camera-space normal at several pitches and directions; a
  sphere's normals match the analytic normal within a stated angle; a
  plane at a known position reads its depth; the normal and depth coverage
  equal the material-ID coverage pixel for pixel; repeat renders are
  identical; the colour bytes are unchanged by the new passes.
- **Old output preserved:** the colour sheet, JSON (except schema and the
  new records) and flat previews of every existing look stay byte-identical.
- **The owner's eye** (D-8, V-12): normal maps and lit previews of the
  acceptance model at the owner's cell size, with the light in several
  places, judged for alignment and plausibility.

## Delivery plan

*A candidate shape only, for discussion; not proposed for signoff until the
open questions are settled.*

1. Capture the normal and depth buffers (after the spike).
2. Reduce them to the output grid with the colour's coverage.
3. Write the normal map, record it in the JSON, bump the schema, reuse it.
4. Write the optional depth map.
5. Lit previews and the light flag.
6. The owner's visual review (documentation only, like material styling
   MAT-7).

## Source notes

The owner, 2026-10-13, as recorded in material styling D-27:

> moskophoros is going to create a sprite that is flatly shaded, only R1 and
> R2, basic ambient light

> … containing information on the geometry of the object … and we will then
> be able to handle any sort of lighting in our 2D world

> for the cli interface, just output flat, but give the optional flag to
> place the light.
