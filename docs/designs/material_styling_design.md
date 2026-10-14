# Material styling design

Sprites rendered by moskophoros today are recognisably 3D renders: smooth
studio shading reduced to pixels and, optionally, snapped to a palette. They
do not match hand-made art, and the same material does not come out the same
colours on two subjects. This arc makes stylize **material-aware**: every
surface knows which named material it is, and each material draws its pixels
from its own short run of shades (a *ramp*) on one shared palette. A steel
blade then has the same colours whichever subject holds it, and the whole
project stays on one cohesive colour ladder.

It is the next step the vision names under "Long-term direction: the style
pipeline" (*palettes … with per-material color ramps*), and the trigger that
design §Deferred and style pass 1 D-8 set for the first auxiliary capture
buffer. It benefits the owner producing game art, and any later project that
uses the tool (V-1).

Design state: `exploring`

*Reset 2026-10-14 for MAT-8 review 1* ([below](#mat-8-review-1)). Codex
review 1 found that D-35 conflicts with settings design D-36, which needs an
owner decision (Q-30, since resolved by D-36), and asked for three contract fixes. MAT-1 to MAT-7 are
unaffected. The design returns to ready on the owner's signoff of the
revision.

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [x] EPIC. Draw each named material from its own ramp on a shared palette — [#63]
- [x] MAT-1. Carry several named capture buffers per frame through the pipeline — [#64]
- [x] MAT-2. Read material identities from the glTF — [#65]
- [x] MAT-3. Capture material-ID and shade buffers — [#66]
- [x] MAT-4. Read and validate a material library — [#67]
- [x] MAT-5. Map frames onto material ramps — [#68]
- [x] MAT-6. Choose, record and reuse a material library from the command — [#69]
- [x] MAT-7. Render materials for the owner's visual review — [#70]
- [ ] MAT-8. Generate ramps from material properties

The owner approved this slice list on 2026-10-07 (D-14); it replaces the
earlier M1–M5 shape.

## Epic contract

- **Goal:** the owner renders a sheet in which each named material of the
  model is drawn from its own ramp on the chosen palette, by giving a material
  library on the command line, without editing the model's colours. The same
  material name, library and palette give the same colours on every subject.
  The library is recorded in the sheet's JSON and fingerprint, so the look is
  reproducible and reusable.
- **Done when:** the automated checks pass; without a material library, every
  existing look (plain, mode, each with or without a palette) produces the
  same sheet pixels as before the arc, shown by a recorded before-and-after
  comparison ([Verification strategy](#verification-strategy)); the owner
  reviews sheets and previews of the acceptance inputs (D-16) and approves
  them (V-12); and ramps can be generated from material properties (MAT-8,
  D-12). Visual quality has no acceptance criterion other than the owner's
  judgement.
- **First release and completion:** MAT-1 to MAT-7 are the first release,
  hand-listed ramps judged by the owner. MAT-8 follows it and completes the
  epic.
- **Users and operators:** the owner producing game art; agents maintaining
  the tool.
- **Arc label:** None proposed.

## Current state and evidence

Checked on 2026-10-07 at `master` `cccf528`, by reading only. No test, build,
render or Blender process ran for this design.

**Capture**

- Capture renders with Workbench, studio lighting fixed in view space,
  `TEXTURE` colour falling back to material colour, no shadows, cavity or
  outline, transparent film (`capture/blender_script.py:887`
  `configure_render`; design §Capture).
- It sets no antialiasing, specular-highlight, metallic, roughness or alpha
  option, so Workbench's defaults apply: the colour buffer is antialiased,
  and whether studio shading varies with a material's metallic or roughness
  is unverified (`configure_render` sets none of `scene.display.render_aa`,
  `shading.show_specular_highlight` or any material display setting).
- It writes exactly one buffer per frame, `color/NNNNNN.png`
  (`blender_script.py:1042` `render_frames`, `:1085`).
- The result contract already allows extra named buffers: `frames[].buffers`
  maps names to files, `color` is mandatory, and every named buffer is
  validated (design §Capture job and result contract;
  `capture/backend.py:484`). But each one must be an **8-bit RGBA PNG at the
  supersampled size** (`backend.py:558` `_buffer`), so a new buffer must be
  encoded that way or the validator must change.
- **The capture job is independent of style.** The job's `settings` leaves out
  the sheet's `style`, "so the job is the same whatever the style" (design
  §job format; style pass 1 D-11). V-4 adds that capture "keeps full
  information and decides nothing about the look … so a style experiment never
  needs a re-render". A buffer captured *only when* a material library is given
  would break both.

**Between capture and stylize**

- A frame carries **one image**: `ImageFrame(address, pixels, metadata)`
  (`sampling.py:53`), and the command loads only `buffers["color"]`
  (`cli.py:517`). Stylize functions take a stream of those frames
  (`stylize.py`). A pass that needs a material-ID or shade buffer beside the
  colour cannot receive it today: this is a **foundational change** (MAT-1).
- Frames are loaded and reduced one at a time, so only one supersampled frame
  is held at once (`cli.py:514`). A material pass works per frame and keeps
  that property.

**Stylize today** (design §Stylize; style pass 1 D-1 to D-7)

- Four looks: `--reduce plain|mode`, each optionally mapped to `--palette FILE`
  by nearest colour in OKLab without dithering. Coverage (below 0.5 mean alpha
  is transparent) is shared by both reductions; output alpha is 0 or 255.
- `settings.style` records the reduction and the palette's exact colours,
  source name and SHA-256, under schema `moskophoros.sheet/2`, outside the
  capture job; it is covered by the fingerprint and reused by
  `--settings-from` (style pass 1 D-10, D-11).
- Palette errors are usage errors (exit 2) before Blender starts.

**Materials in the input**

- Nothing in the tool reads glTF materials. `gltf.py` reads no `materials` or
  primitive `material` references, and design §Input contract makes no claim
  about material names. glTF material names are optional and need not be
  unique, so identity by name (D-3) needs new input rules (D-18).
- Blender's importer creates its own material objects; mapping them back to
  glTF materials happens inside the backend, like the existing node and
  animation mapping (design §job format).
- The review model (D-16), `RobotExpressive.glb` in the owner's local
  acceptance store (`~/.local/share/moskophoros-acceptance/robotexpressive/`,
  SHA-256 `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319`),
  has three materials, `Grey`, `Main` and `Black`, all referenced by
  primitives, flat colours with no textures, alpha mode `OPAQUE`, metallic 0.1
  and roughness 0.9. It exercises named materials, but not textures, cutouts,
  duplicate or missing names; generated fixtures cover those.

**The owner's consumer: what an "RGB facemap" is**

The owner's current game lights world sprites with a *face map*, and units
today have none ("Units have no directional face map of their own",
`~/work/synarchy/src/Unit/Render.hs:195`). Its fragment shader
(`~/work/synarchy/src/Engine/Graphics/Vulkan/ShaderCode.hs:168`) reads a face
map's RGB as **weights over three faces**: "R=right, G=top, B=left"
(`:267`), normalised by their sum (`:263`), and brightness is the weighted
mix of a right, top and left brightness derived from the sun angle (`:298`).
So a face map is not a normal map: it is the surface direction **projected
onto three fixed screen-relative directions**. This is recorded only as the
owner's consumer context. Under V-1 the tool emits no game's private layout;
how a generic output serves this consumer is
[Q-11](#q-11-what-does-the-lighting-sheet-encode).

**Tracker:** no open pull request; no open epic overlaps materials (#3 and #24
are stale epics whose children are closed; #43 is owner-deferred and
unrelated). Re-checked at readiness.

## Research grounding

- **Dead Cells** (Motion Twin; T. Vasseur, ["Art Design Deep Dive: Using a 3D
  pipeline for 2D animation in Dead Cells"](https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-),
  Game Developer, 2018): low-detail 3D models rendered small without
  antialiasing, each frame exported as a colour PNG **and a normal map**, lit
  in-game by a toon shader. Reusing equipment across monsters came from
  reusing 3D parts, not from a colour system.
- **Blasphemous** (The Game Kitchen): hand-authored, flat, no outlines, bold
  colours from one cohesive set of ramps. *Our observation of the games, not
  a published method:* materials differ by how they band, metal in few
  high-contrast steps with warm highlights, cloth and skin in softer,
  lower-contrast steps, stone rougher.
- **Pixel-art ramp practice** (for example the method Vince128's README
  credits, SLYNYRD, ["Pixelblog 1: Color Palettes"](https://www.slynyrd.com/blog/2018/1/10/pixelblog-1-color-palettes)):
  a good ramp **shifts hue** as it darkens and lightens (shadows toward cool
  or purple, highlights toward warm or yellow) and changes saturation, rather
  than only scaling brightness.
- **Hypotheses, untested:** that the averaged palette looks seem "off" partly
  because their ramps only scale brightness, and partly because render
  luminance mixes each material's own colour into its shading (Q-9); and that
  the 3D-render look comes from mapping smooth render gradients onto long
  ramps, so few, wide, authored bands avoid it. MAT-7's review is the first
  evidence for or against them.

## Desired experience

The owner names materials in their 3D tool (`steel`, `cloth.red`, `skin`),
exports a `.glb`, and keeps one shared material library for the project. A
render then looks like:

```sh
moskophoros --palette project.gpl --materials project-materials.json \
    --reduce mode knight.glb knight.png
```

*(Illustrative; the option name is MAT-6's.)* Each named material in the
library is drawn from its ramp: few bold bands, colours from the palette. The
same `steel` on another subject gets identical colours. A material the
library does not know takes the library's default ramp if it has one,
otherwise the ordinary look, and is named in a warning either way, so nothing
changes colour silently (D-9, D-17). Library errors fail before Blender
starts, naming the file, the material and the problem. `--settings-from` reuses
the whole look, library included, on the next asset without needing the files
again.

Later, a second sheet of the same frames lets the game light the sprites live
(day/night, point lights), while the colour sheet keeps the materials'
identity (D-1, D-2; [later arc](#later-arc-the-lighting-sheet)).

## Scope

### In scope

- Reading glTF material identities, with the input rules that requires
  (MAT-2, D-18).
- Capturing, for every frame, a material-ID buffer and the shade source the
  ramps need (MAT-3, D-11, D-13).
- Carrying several named buffers per frame from capture into stylize (MAT-1).
- A material library file and its validation (MAT-4, D-8).
- Generating ramps from material properties, after the first review (MAT-8,
  D-12).
- Mapping each frame onto material ramps, composed with the existing
  reductions and palette (MAT-5, D-6, D-7, D-20).
- The command option, its errors and warnings, and recording and reusing the
  library (MAT-6, D-19).
- The design amendments, tests and documentation each slice needs, and the
  owner's visual review (MAT-7).

### Out of scope

- The **lighting sheet** for live engine lighting (normals or face weights):
  a later arc (D-1, D-4), recorded [below](#later-arc-the-lighting-sheet).
- Dithering of any kind, including per-material dither patterns.
- Eased or non-linear band spacing, and the reserved baked-versus-live range
  (D-2) beyond the band count.
- Material-driven surface noise or roughness effects.
- Outlines, cleanup passes, frame-to-frame stability, AI restyling.
- Translucent or alpha-blended materials: coverage stays as today
  (D-20).
- Palette swaps and other variants (design §Deferred).
- Saved style files and a free chain of passes (style pass 1 D-9).

## Design

**Proposal throughout this section**, except where a decision is cited.

### Data flow

```text
.glb ──► gltf (pure): material identities (MAT-2)
   │
   ▼
capture (Blender) ── per frame ──► color   antialiased, unchanged
                                   matid   material ID per pixel   (MAT-3)
                                   shade   occlusion and curvature (MAT-3, D-11, D-22, D-25)
   │   result: buffers per frame, plus one ID → glTF material table
   ▼
launcher validates the result; the command joins the ID table with the
glTF identities (MAT-1, MAT-2)
   │
   ▼
frame: color, identity per pixel, shade per pixel; asset: identity list
   │
   ▼
stylize: reduce (plain | mode) + material ramps (MAT-5) ──► reduced colour
   │        (the supersampled buffers are released here)
   ▼
cleanup ──► export    (unchanged: they see reduced colour frames only)
```

Stylize resolves IDs without reading the model or the capture's files: the
command hands it decoded arrays and the identity list
([Frames into stylize](#frames-into-stylize)).

### Identity (D-3, D-18)

A material's identity is its glTF material **name**, read from the file's
JSON in pure Python, never from Blender's renamed copies. Names compare
exactly, case included (D-18). Two glTF materials with the same name are
**one identity** on purpose: that is what makes "steel" match across parts and
subjects, and their pixels pool together wherever identities are counted
([Mapping a block](#mapping-a-block-d-7-d-9-d-20)).

A primitive with no material, or a material whose name is absent or the empty
string, belongs to one shared **no-identity** class: it gets the ordinary
look, and when a library is given one warning counts such parts (D-18).

Input errors (exit 3, naming the file and the problem, design §Input
contract), checked whether or not a library is given: a material `name` that
is not a string; a primitive `material` that is not an integer index into
`materials`.

### Capture (D-10, D-11, D-13)

Every render writes, beside `color`, a **material-ID buffer** and a
**light-only shade buffer**, on every render whether or not a library is used
(D-13). The capture job stays style-independent (V-4; style pass 1 D-11).

**Sampling and ownership.** The colour buffer stays antialiased, exactly as
today. The ID and shade buffers are rendered **unfiltered, from one shared
sample per pixel**, so each shade pixel holds the light of exactly the
surface its ID names, and no shade pixel blends two surfaces. This is an
approximation of the antialiased colour, and its limits are deliberate:

- An edge pixel can have colour alpha above zero where the ID sees
  background. It counts toward coverage as today, but casts no material vote.
- A pixel straddling two materials belongs wholly to the one its sample hit.
- A feature thinner than a pixel can appear in the colour but be missed by
  the ID. A covered block in which no pixel has an identity gets the ordinary
  look.
- At `--supersample 1` a block is one pixel, so its material is that pixel's
  ID, or the ordinary look when the ID is background.

**Cutouts and translucency.** Materials with glTF alpha mode `MASK` are
captured opaque, with no cutouts, in the colour and therefore in the ID and
shade passes too (D-26): every pixel's identity is the surface the colour
shows, and no surface behind a `MASK` texel is identified. `MASK` materials are eligible
for ramps like `OPAQUE` ones. `BLEND` (translucent) materials are out of
scope: coverage stays as today, and they keep the ordinary look. That is
decided from the glTF, not inferred from pixels: MAT-2 reports each
material's alpha mode, and when the command builds the identity list it
assigns every `BLEND` material to the **no-identity** class, whatever its
name. A name shared by an opaque and a `BLEND` material therefore pools only
its opaque materials; the `BLEND` surfaces vote as no-identity, and a block
they win keeps the ordinary look even when the library or its default would
map the name. A library that maps a name used only by `BLEND` materials
gets a warning naming it.

**Shade numerical contract.** The shade pass replaces every surface with one
uniform white, **specular highlights off and every material display setting
(metallic, roughness) standardised**, shaded by **occlusion and surface
curvature only** (D-22, D-25): creases, nooks and concave curves darker, open
and convex surfaces lighter, with no directional, sky or ground light. What it
records varies with neither any material property nor any light direction. The
colour buffer keeps the studio light unchanged, for the ordinary look. It is
written as an 8-bit RGBA PNG with `R = G = B`, alpha 255 where a surface was
sampled and 0 elsewhere; the shade value is that byte over 255, encoded as the
colour buffer is (sRGB, the `Standard` view transform). Bands are taken over one
**fixed shade range**, the same for every frame, subject and material, never
normalised per frame or per subject. (*Amended by settings design D-9 and D-20,
2026-10-11:* a material's library entry may give its own range, the same for
every frame and subject; the others take the global range.) MAT-5's mapper takes the range as a
parameter and never chooses it; MAT-3 chooses the default for new renders
from the spike's measurements; MAT-6 records and reuses it
([Recording and reuse](#recording-and-reuse-d-19)).

**ID encoding and table.** The ID buffer is an 8-bit RGBA PNG (the existing
validator's form). One reserved value means **background**; it is never in
the table. Every other value used is in one table per asset, mapping it to a
glTF material index or to "no material" (a primitive without one); the exact
channels are the spike's. A model with more materials than the encoding holds
is an input error (exit 3) before Blender. The launcher rejects, as a backend
error:

- an ID pixel that is not exactly an encoded value, or a non-background ID
  missing from the table;
- a table entry that is not a material of the model, or that maps the
  background value;
- a shade pixel whose R, G and B differ, or whose alpha is other than 0 or
  255;
- a pixel where the two disagree: a background ID must have shade `(0, 0, 0,
  0)`, and every other ID must have shade alpha 255. So a surface can never
  take a band from a missing shade sample.

**The spike (D-10)** chooses how Blender produces both buffers. Candidates,
all **unverified**: Workbench re-renders with each material's display colour
set to its encoded ID, flat lighting and antialiasing off (ID); with every
surface uniform white, specular off, display settings standardised, and
occlusion and curvature only (shade). For the shade, Workbench's cavity has
methods `WORLD` (larger-scale occlusion), `SCREEN` (curvature) and `BOTH`
([Blender API](https://docs.blender.org/api/5.2/bpy.types.View3DShading.html));
the other candidate is a render engine's ambient-occlusion pass, which shows
occlusion but not isolated convex curves. A sampled method must be shown
deterministic.

Its acceptance cases, recorded with its outcome before MAT-3:

- exact, deterministic IDs and shade on repeat;
- two materials meeting along an edge; a feature thinner than a pixel; a
  `MASK` cutout with a second material behind it; one material occluding
  another;
- `--supersample` at 1 and at its largest supported value;
- a shade buffer identical for two materials that differ in colour, texture,
  metallic and roughness;
- the full D-25 signal: a flat open surface, a crease and an isolated convex
  curve on one fixture take **different bands** after the 8-bit encoding and
  the fixed range, not only different raw values;
- for a screen-space method, how the shade of the same surface changes with
  supersampling, scale (`pixels_per_meter`) and view direction, stating
  whether the result is view-dependent enhancement or an estimate of surface
  form. The owner judges whether that approximation is acceptable.

The spike records the method, its fixed parameters (cavity type, ridge and
valley factors, distances, sample counts) and any seed. **Failure route:** the
antialiased-colour approximation above is already accepted. If the technique
cannot meet the shared-sample ID and shade contract, or D-25's signal, the
spike stops and brings the gap to the owner; MAT-3 does not proceed on a
relaxed contract without a new decision.

#### Spike record (D-10)

Recorded 2026-10-08 by MAT-3's solver ([#66]), before any capture change. The
spike's code is not delivered. Blender 5.2.2 LTS on macOS (Apple silicon);
Cycles on the CPU.

**Fixtures** (generated glTF, one node each):

- *edges*: two materials meeting along a vertical edge; a strip of a third
  0.01 m wide (0.4 px at 40 px/m); a `MASK` material (an 8×8 nearest-filtered
  texture of cells with alpha 0 or 255, cutoff 0.5) 0.2 m in front of a
  fourth; a cube of a fifth in front of a sixth; two materials both named
  `steel`; an unnamed material; a primitive without a material.
- *form*: a floor (y = 0, 3 × 2.5 m), a wall meeting it at a 90° crease
  (z = −1, 1.5 m high) and an isolated smooth UV sphere (radius 0.35 m,
  24 × 48 segments, centre (0.7, 0.75, 0.4)), all one grey.
- *appearance*: the *form* geometry with materials that differ in base
  colour, base-colour texture, metallic (0, 0.5, 1) and roughness (0 to 0.3).
- *many*: 256 quads, each its own material.

**Render settings:** render jobs as the command builds them, one direction,
pitch 30° (also 0° and 60°), 40 px/m (also 20 and 80), cell 128 × 112
(scaled with px/m), supersample 1 (also 4 and 16); eight directions for the
sequence checks.

**Measurement regions** (from the ID buffer, in output pixels): *flat* is
floor or wall at least 12 px from the crease, 8 px from the sphere and 3 px
from the background; *crease* is floor or wall within max(1, s/2)
supersampled pixels of the floor–wall boundary, with the same exclusions;
*sphere* is the sphere's pixels, split into centre, middle and rim by
distance to its edge.

**Candidates.**

- *Workbench cavity* (flat lighting, one uniform grey of 0.214 linear, 128
  in sRGB, since on white a ridge cannot get lighter than a flat surface;
  specular off; antialiasing off; ridge and valley factors 2.0 for
  curvature, 2.5 for cavity). Both methods are screen-space, deterministic
  and identical across *appearance*. **Not chosen.**
  - `SCREEN` (curvature): flat exactly 127; the crease a one-pixel line at
    0; the sphere 156 at supersample 1, 136 at 4 and 130 at 16, and 177, 156
    and 143 at 20, 40 and 80 px/m; a dark ring along the sphere's silhouette
    whose mean varies from 8 to 147 with the direction. It measures the
    image, not the form: view-dependent enhancement.
  - `WORLD` (screen-space ambient occlusion, 0.2 m, 16 samples): stable with
    supersample and view (sphere about 147; crease 94, 83 and 72 at 20, 40
    and 80 px/m), but noisy: a flat surface's pixels vary by ±4 to 7 and
    straddle two bands.
- *Cycles, world-space* (**chosen**, below).

**Chosen method.** After each frame's unchanged colour render, one Cycles
render in which every material's surface is temporarily replaced by an
emission whose colour carries the frame's ID and shade, so both come from
**one shared camera sample per pixel**; then every setting and material is
restored exactly before the next colour render.

- Cycles fixed parameters: CPU; 1 sample per pixel; adaptive sampling off;
  seed 0, not animated; pixel filter Box, width 0.01 px (the sample sits at
  the pixel centre); every light bounce 0; transparent bounces 8; denoising
  off; film transparent; view transform `Standard`, look `None`, exposure 0,
  gamma 1, sRGB display; dither 0.
- **Shade** (linear, clamped to [0, 1]):
  `0.25 · AO_out + 1.0 · (1 − AO_in)`, where `AO_out` and `AO_in` are
  Cycles Ambient Occlusion nodes with distance 0.3 m and 64 samples, looking
  outside and inside the surface respectively (not local-only). `AO_out`
  darkens creases and nooks; `1 − AO_in`, how much surface lies within
  0.3 m behind the point, lightens convex curves. A flat open surface is
  exactly 0.25 linear, 137 encoded. No light, no material property and no
  direction enters it. Encoded as the colour is (sRGB, `Standard`), with
  `R = G = B`, alpha 255 where a surface was sampled and 0 elsewhere.
- **ID:** a 16-bit value in two bytes; 0 with alpha 0 is background; the
  spike assigned 1, 2, … in material order. The 256 materials of *many*
  give exactly their 256 values and no other. That exercises every value of
  the low byte but only 0 and 1 of the high byte; MAT-3's Blender tests
  cover a carry between the bytes and the largest code.

**Measurements** (shade bytes of the chosen method on *form*: mean ± standard
deviation, 5th to 95th percentile, and the band of the mean for N = 3, 4 and
5 over the range chosen below):

| Setting | Flat | Crease | Sphere (centre) | Bands N = 3 / 4 / 5 (crease, flat, sphere) |
|---|---|---|---|---|
| s = 1, 40 px/m, 30° | 137 ± 0 | 106.8 ± 5.0 (101–115) | 175.7 ± 4.5 (168–185) | 0,1,2 / 0,1,3 / 1,2,4 |
| s = 4 | 137 ± 0 | 102.1 ± 2.9 (98–106) | 175.5 ± 5.2 (168–185) | 0,1,2 / 0,1,3 / 0,2,4 |
| s = 16 | 137 ± 0 | 101.3 ± 2.8 (96–106) | 176.0 ± 4.8 (168–182) | 0,1,2 / 0,1,3 / 0,2,4 |
| 20 px/m | 137 ± 0 | 112.9 ± 8.0 (103–126) | 174.5 ± 2.6 (171–177) | 0,1,2 / **1,1**,3 / 1,2,4 |
| 80 px/m | 137 ± 0 | 103.1 ± 3.2 (98–109) | 174.5 ± 4.5 (165–179) | 0,1,2 / 0,1,3 / 0,2,4 |
| pitch 60° | 137 ± 0 | 106.8 ± 6.2 (98–116) | 175.8 ± 4.2 (171–185) | 0,1,2 / 0,1,3 / 1,2,4 |
| pitch 0° | 134.5 ± 6.2 (wall) | not visible | 176.2 ± 2.5 (171–179) | –, 1, 2 / –, 1, 3 / –, 2, 4 |

The crease's value depends on how much of its 0.3 m darkening a pixel
covers, so at 20 px/m (5 cm pixels) its mean shares N = 4's band with flat;
the sphere's rim and middle match its centre within 1.

**Other cases.**

- *Determinism:* ID and shade pixels identical on repeat and with 1, 3 and
  the default number of threads. Cycles' own PNG files carry render-time
  text metadata, so the delivery writes the ID and shade PNGs itself from
  the pixels.
- *Appearance:* ID and shade pixels identical for *form* and *appearance*.
- *Edges, supersample 1 and 16:* each pixel's ID is the material an
  unfiltered flat Workbench render shows there, except on the primitive
  without a material: Cycles renders an empty material slot mostly
  transparent, with a few stray values, so the pass needs a stand-in
  material for it. The 0.01 m strip is missed at supersample 1 and present
  at 16, as accepted. The importer renames duplicate and unnamed materials
  (`steel.001`, `Material_6`), so the delivery names materials by glTF index
  in its private copy.
- *Colour independence:* with every setting restored exactly, all colour
  frames of two eight-direction sequences are byte-identical with and
  without the auxiliary renders before them.
- *Time:* about 1 s per frame at 128 × 112 and 4 s at 2048 × 1792
  (supersample 16).

**Default shade range: `[84, 191]`.** For N = 3 its band edges fall at the
midpoints between the measured crease (about 102), flat (137) and sphere
(about 176) values; the same range keeps the three apart for N = 3 and 5 at
every setting above, and for N = 4 at all but 20 px/m.

**Outcome:** the chosen method is world-space, not screen-space, and meets
the shared-sample ID and shade contract and D-25's signal on these
fixtures. **One finding blocked MAT-3:** the colour capture does not cut out
`MASK` materials ([Q-26](#q-26-how-do-mask-cutouts-relate-between-the-colour-and-the-id-and-shade-buffers));
resolved by D-26: the ID and shade match the colour, with no cutouts.

**Provenance.** The result's `backend` reports the shade technique and the
parameters above, and the sheet's `generator` gains them beside `renderer`
and `studio_light` (`export.generator`), so they are in the fingerprint and
survive the capture's temporary directory. A recorded shade range reproduces
band thresholds only; a different shade technique or Blender can change the
signal under them, as a different renderer can change colour today (design
§Reproducibility). The generator makes that difference visible.

### Frames into stylize

MAT-1 defines the one interface MAT-3 produces and MAT-5 consumes, so they can
be built in parallel against it:

- Per asset, an **identity list**: each distinct name of an eligible
  (`OPAQUE` or `MASK`) material, in a fixed order (by its lowest glTF material
  index), then the no-identity class. The command builds it from MAT-2's names
  and alpha modes and the capture's ID table, so `BLEND`, unnamed and missing
  materials all decode to no-identity.
- Per frame, beside the colour pixels: an **identity array** of the same
  size, holding an index into the identity list or *background*; and a
  **shade array** of 8-bit shade values. Both are decoded and validated by the
  command, never by stylize.

Frames are loaded one at a time, as today. Stylize returns an ordinary reduced
colour frame; the supersampled colour, identity and shade arrays are released
once it is reduced, so at most one frame's supersampled buffers are held.
Cleanup and export receive exactly what they receive today.

### Library (D-6, D-7, D-8, D-12, D-15, D-17)

A JSON file the tool only reads. A ramp is a list of palette indices, darkest
first (D-6, D-7). The library holds **named generic ramps** (metal, cloth,
skin…) that every model can reuse, and **material entries** that each give
their own ramp, point at a named ramp, or say `"ordinary"` (D-15). An optional
**default** names the ramp for materials with no entry (D-17). Illustrative
shape only:

```json
{
  "schema": "moskophoros.materials/1",
  "ramps": {
    "metal": [12, 13, 14, 15, 47],
    "cloth": [80, 81, 82]
  },
  "default": "cloth",
  "materials": {
    "steel":     {"uses": "metal"},
    "cloth.red": {"ramp": [80, 81, 82]},
    "face":      "ordinary"
  }
}
```

A named material resolves in order: its own entry, then the default, then the
ordinary look. Every material that takes the default or the ordinary look
without an entry is named in a warning.

Validation, each a usage error (exit 2) before Blender naming the
file and the entry (D-8):

- UTF-8 JSON with no repeated key; `schema` exactly `moskophoros.materials/1`;
  no unknown field at any level.
- A ramp is a non-empty list of at most 256 JSON integers (not booleans, not
  `3.0`), each a valid index into the palette. One entry is allowed (a flat
  material, the most flatness D-7 offers); repeated indices are allowed.
- "Darkest first" is the authoring convention for band order, band 0 being
  the least light; it is not validated, since a hue-shifted ramp need not be
  monotone in any one measure.
- A material entry is exactly one of `{"ramp": …}`, `{"uses": NAME}` or
  `"ordinary"`; `uses` and `default` name a ramp in `ramps`.
- Names are non-empty strings; the empty name is not a material (D-18).

MAT-8 lets a ramp be given as **properties** that generate it instead (D-12,
D-21, D-28 to D-34), and lets a library give a default `shade` (D-35). The
library schema becomes `moskophoros.materials/3`, and `/2` still loads
(D-34).

### Mapping a block (D-7, D-9, D-20)

For each `s×s` block, every weight below is the colour buffer's alpha, as in
the existing reductions:

1. **Coverage** is decided exactly as today, from the colour buffer's alpha.
   Transparent blocks stay `(0, 0, 0, 0)`.
2. **Identity:** each pixel with an identity votes for it with its colour alpha.
   Materials sharing a name **pool their votes** as one identity (D-18); the
   no-identity class is one candidate; background pixels cast no vote. The most
   votes wins; ties go to the identity with the smallest lowest glTF material
   index, no-identity last (D-23). No vote at all means the ordinary look.
3. **Band:** if the winning identity resolves to a ramp of N entries, its
   pixels' shade values, and only theirs, give the band. The fixed shade range
   `[lo, hi]` (8-bit shade values, `0 ≤ lo < hi ≤ 255`) is split into N equal
   bands (D-7): a shade `v` is clamped into the range and takes band
   `(v − lo)·N // (hi − lo + 1)`, so `lo` is band 0 and, when `N ≤ hi − lo + 1`,
   `hi` is band N−1 (with `L = hi − lo + 1`, `hi` takes band `((L − 1)·N) // L`;
   a longer ramp is valid and has unreachable bands, never shortened or
   rejected). Under `plain`, take the alpha-weighted mean shade `W/A`, clamped
   after averaging, not rounded: with `Wc = min(max(W, lo·A), hi·A)` its band is
   `(Wc − lo·A)·N // ((hi − lo + 1)·A)`; output `palette[ramp[band]]`. Under
   `mode`, map each of the winner's pixels to `ramp[band]` and vote by palette
   entry, weighted by colour alpha (D-23). A tie goes to the entry with a band
   centre nearest the unrounded mean shade `W/A` of the original shades, over
   **every** occurrence of that entry in the ramp, then to the smaller palette
   index. Band `k`'s centre is `lo + (k + ½)·(hi − lo + 1)/N`, compared exactly
   by scaling both sides by `2·N·A`: occurrence `k` is at distance
   `|2·N·W − (2·N·lo + (2k + 1)·L)·A|`. Votes use each pixel's clamped shade.
   Alpha is 255.
4. Otherwise (no-identity, including `BLEND`; `"ordinary"`; unmapped without
   a default), the block takes the existing look for the chosen reduction and
   palette (D-9).

Coverage, identity votes, shade sums, bands and `mode` tie comparisons are
exact integer arithmetic, deterministic, and independent of the library's key
order. The ordinary look keeps its existing arithmetic, including the NumPy
`float64` OKLab palette mapping, and is unchanged.

### Recording and reuse (D-19)

`settings.style` gains the library inline (its named ramps, default and
material entries) with its source base name and SHA-256 (D-19), and the fixed
shade range. It is covered by the fingerprint and reused by
`--settings-from`. Recording it bumps the sheet schema version; a sheet
written without a library reuses as having none.

The shade range is two integers `lo < hi` in 0–255, recorded whether or not a
library is used and outside the library, since it belongs to the shade
signal, not the ramps. A new render uses the current default (MAT-3); a reused
sheet keeps its recorded range, even when an explicit library replaces the
reused one. No command option sets it in this arc. A sheet without a recorded
range reuses with the default.

As with the palette today, the library file is read once, and the same bytes
are parsed and hashed. The final library and palette combination, whether
from files or reused settings, is validated before **any** Blender
invocation, including the version probe. A reused library is validated as an
explicit one is, even when an explicit option replaces it (the existing reuse
contract). Explicit options combine with reused ones as D-24 sets out;
`--no-materials` drops a reused library.

*Clarified on MAT-6's review:* under schema `moskophoros.sheet/3`,
`settings.style` is `reduce`, `palette`, `materials` and `shade_range`, in that
order. `materials` is `null`, or the library inline: its `source` base name and
`sha256`, then its `ramps`, `default` (`null` for none) and `materials`, the
named ones in name order. `shade_range` is exactly two JSON integers (not
booleans or floats) with `0 ≤ lo < hi ≤ 255`, validated whenever a `/3` sheet
is reused, even when the library is `null`, dropped or replaced; only `/1` and
`/2` sheets obtain the default. The original reused library is validated
against its original inline palette before any override, and the final library
against the final palette: an invalid recorded library is an error even when
it is dropped or replaced, a discarded library is never checked against a
replacement palette, and a valid one may be dropped with `--no-materials`
beside `--no-palette`. The sheet PNG and previews of the four existing looks
stay byte-identical without a library; their JSON changes only by the schema,
these `style` fields and the fingerprint.

### Failure behaviour

- Unreadable or malformed library, an index outside the palette, a library
  without a palette: usage errors (exit 2) before Blender starts, naming the
  file and material (D-6, D-8).
- A model material absent from the library, or a library entry the model never
  uses: not an error. (*Clarified on MAT-6's review:* the warnings apply
  whenever a library is active, including a reused one. Each distinct name warns
  once with its actual outcome, so a `BLEND` material keeps the ordinary look
  even beside a default ramp. The count of parts with no identity comes from the
  selected scene's primitive records, not the decoded no-identity class, which
  also holds named `BLEND` materials.) The first is a warning naming the material and whether
  it took the default ramp or the ordinary look (D-9, D-17); the second, like
  an unused named ramp, is silent (D-15).
- An entry or default naming a ramp the library does not define: a usage
  error (exit 2) before Blender, naming the file and the entry (D-17).
- A malformed glTF material name or primitive material reference, or more
  materials than the ID encoding holds: input errors (exit 3) before Blender
  ([Identity](#identity-d-3-d-18), [Capture](#capture-d-10-d-11-d-13)).
- A material-ID buffer that disagrees with its table or is not exact, or a
  shade buffer outside its contract: a backend error (exit 5), like any
  invalid capture result.

## Decisions

### D-1. Two aligned outputs: a material-aware colour sheet, and later a lighting sheet

Decided 2026-10-07. moskophoros grows to emit, per asset, a material-aware
colour sheet and an aligned **lighting sheet** that lets the owner's engine
light the sprites live. The tool produces both; it never performs the live
lighting (V-1). They are separate arcs (D-4).

*Clarified 2026-10-07 on review:* the first draft called the second output an
"RGB facemap" and assumed it was a normal map. The owner's engine reads a face
map as weights over three faces ([evidence](#current-state-and-evidence)), so
what the lighting sheet encodes is open (Q-11). The decision itself, two
outputs, is unchanged.

### D-2. The colour sheet bakes identity and ambient tone; directional light is live

Decided 2026-10-07. The colour sheet bakes each material's identity and a
modest ambient/mid shading; strong directional shaping is left to live
lighting from the lighting sheet. A per-material control of how much is baked
is wanted; beyond the band count its form is deferred, with generated ramps
(D-12, D-21) its likely home.

*Made concrete by D-22:* bands come from ambient light only, so the colour
sheet bakes no directional shading at all; all of it is left to the lighting
sheet.

### D-3. Identity from glTF material names; look from a shared library; loud fallback

Decided 2026-10-07. A material's identity is the glTF material name, so it
travels with the model. Its look is defined once in an external, shared
library file, reused across subjects and projects. A material the library
does not define falls back with a warning naming it (V-11; detail in D-9).

### D-4. The first arc is material ramps on the colour sheet

Decided 2026-10-07. This arc delivers material ramps on the colour sheet and
the capture buffers they need. The lighting sheet is a later arc. It attacks
the owner's first problem: sprites that do not match the rest of the game's
art.

### D-5. The ramp band comes from render luminance

Decided 2026-10-07 (resolved Q-1, option A). Each block's band comes from the
luminance of the existing colour render, quantised hard into a few bands,
adding only the material-ID buffer. Normals arrive with the lighting sheet.

**Superseded by D-11** on 2026-10-07, after Q-9 showed that render luminance
mixes the material's own colour and texture into the band.

### D-6. Ramps index the shared palette, so a library needs a palette

Decided 2026-10-07 (resolved Q-5). A ramp is an ordered list of indices into
the active palette, darkest first, so every material stays on the one shared
palette. A library used without a palette (from `--palette` or reused
settings) is a usage error (exit 2) before Blender starts.

### D-7. The minimal ramp model: N palette indices, linear bands

Decided 2026-10-07 (resolved Q-2 for this arc). A material is an ordered ramp
of N palette indices; **N is the material's flatness control**. The shade is
quantised linearly into N bands. Dithering, eased spacing and the baked/live
range are deferred. Generated ramps add to this model later (D-12); they do
not replace it. **Amended by settings design D-9 and D-20 (owner,
2026-10-11):** the bands are taken over the global shade range unless a
material's library entry gives its own `shade.range`, which that material is
banded over instead; there is no longer one range for every material.
**Amended by D-35 (owner, 2026-10-14):** a library's own `shade.range` comes
between the material's and the global range.

### D-8. The library is a JSON file the tool only reads

Decided 2026-10-07 (resolved Q-3). The library is a JSON file mapping
material names to ramps, with room for later properties. Like
`palette.read_palette`, its reader reads only the named file and raises a
typed error naming the file and the entry; the command reports errors as
usage errors (exit 2) before Blender.

### D-9. A material without a ramp gets the ordinary look

Decided 2026-10-07 (resolved Q-7, option b). A block whose material has no
library entry, or that has no material, is drawn in the existing look for the
chosen reduction and palette. A named material missing from the library
produces a warning naming it. No default ramp is invented. **Amended by
D-17:** a library may name its own default ramp.

### D-10. A throwaway spike settles how Blender produces the new buffers

Decided 2026-10-07 (resolved Q-8's process). How Blender produces the
material-ID buffer and the shade buffer (D-11) is settled by a
small throwaway spike when MAT-3 starts, with its outcome recorded here first.
This document authorizes no Blender work.

### D-11. The band comes from a light-only shade buffer

Decided 2026-10-07 (resolves Q-9, option B; supersedes D-5). Capture writes a
**shade buffer** for every frame: the same frame with every surface one
uniform white under the same camera-fixed studio light, so it holds light
only, never the material's colour or texture. The band of a block is
quantised from it, so band N means the same light on every material. Normals
still arrive with the lighting sheet. How Blender renders it is part of D-10's
spike. **Amended by D-22:** the shade buffer's light is non-directional
ambient light, not the studio light.

### D-12. Hand-listed ramps first; ramps generated from properties next

Decided 2026-10-07 (resolves Q-10, option C). The first release of this arc
uses only hand-listed palette-index ramps (D-7), so the owner can judge the
banding sooner. Generating a ramp from material properties (base colour, band
count, hue shift toward shadow and toward light, saturation, contrast), then
snapping each shade to the palette, follows as MAT-8. A hand-listed `ramp`
overrides generated shades. **Specified by D-28 to D-35 (owner, 2026-10-14).**

### D-13. The new buffers are captured on every render

Decided 2026-10-07 (resolves Q-12). Every render writes the material-ID and
shade buffers, whether or not a library is used. The capture job stays
independent of style (V-4; style pass 1 D-11), and trying a library never
needs a different capture. The accepted cost is the extra Workbench renders
per frame on every sheet.

*Clarified on review:* the command still captures on every run; this arc adds
no way to replay a retained capture. D-13 keeps that possible later without
a job change; it does not make a library experiment skip Blender today.

### D-14. The arc is delivered as slices MAT-1 to MAT-8

Decided 2026-10-07. The owner approved the [Delivery plan](#delivery-plan)'s
eight slices, replacing the earlier M1–M5 shape. The two added foundations are
multi-buffer frames (MAT-1) and reading glTF material identities (MAT-2);
generated ramps (MAT-8) follow the owner's review. Each slice is one pull
request, except MAT-7.

*Exception, decided 2026-10-08 (owner, relayed by laz, #moskophoros
`xw77kpgu6p5468n94ddnec8u9s`):* MAT-7 is a documentation-only owner
acceptance step with no pull request. Its review library and its renders are
review inputs and outputs kept outside the repository (D-16, `AGENTS.md`
§Files). Its only repository artifact is `docs/acceptance/material-styling.md`,
published with `docs-push`. The issue is complete when that record holds the
owner's verdict. The exception changes how MAT-7 is delivered and nothing
else: the owner's library sign-off and visual verdict are still required.

### D-15. Textured materials keep the ordinary look; unused entries are silent

Decided 2026-10-07 (resolves Q-15, as proposed). A ramp replaces a block's
colour, so a textured material would lose its painted detail. Such materials
stay out of the library and keep the ordinary look (D-9). A library entry may
mark a name `"ordinary"`, which draws it in the ordinary look without D-9's
warning. Library entries the model never uses are normal for a shared library
and are not reported.

*Clarified on review:* there is no automatic texture detection. When a
library has a default (D-17), a named textured material left out of it takes
the default ramp, so keeping its detail needs an explicit `"ordinary"` entry.

### D-16. The first review uses the stock robot, Vince128 and owner-approved ramps

Decided 2026-10-07 (resolves Q-18). The MAT-7 review renders the stock robot
model already used for style pass 1 (RobotExpressive) with the Vince128
palette. Owner-made models come later, in a separate discussion. Every ramp in
the review library is drafted for, and signed off by, the owner before MAT-7
renders it, together with the named generic ramps and default (D-17). The
model and the palette are review inputs only, never defaults or test fixtures
(V-1).

*Clarified on review:* the robot's material names are now checked: `Grey`,
`Main` and `Black`, flat and opaque, at the hash recorded in [Current state
and evidence](#current-state-and-evidence). The review library is drafted for
those three. The review therefore does not exercise textures or cutouts.

### D-17. A library holds named generic ramps and an optional default

Decided 2026-10-07 (resolves Q-20, option B with optional A; amends D-9). A
library defines named generic ramps (such as metal, cloth, skin) once, and a
material entry may point at one instead of listing its own, so the owner signs
off on a small set reused across models. Matching is by explicit entry only;
name patterns are not in this arc. A library may name one of its ramps as the
**default** for named materials with no entry. The tool never invents a
default: without one, D-9's ordinary look applies. Either way the material is
named in a warning. Unnamed parts and `"ordinary"` entries (D-15) always get
the ordinary look. A reference to an undefined ramp is a usage error (exit 2)
before Blender.

### D-18. Material names match exactly; unnamed parts warn

Decided 2026-10-07 (resolves Q-14). Identity is the glTF material name read
from the file's JSON, compared exactly, case included: `Steel` and `steel` are
different. Equal names are one identity. An unnamed material, or a primitive
without one, has no identity and gets the ordinary look; this is not an input
error, but when a library is given one warning counts such parts.

### D-19. The library is recorded inline in the sheet

Decided 2026-10-07 (resolves Q-6). `settings.style` records the whole library
inline (named ramps, default, material entries; with MAT-8, each generated
ramp beside its properties, D-21), its source base name and SHA-256, as the
palette is recorded today. It is covered by the fingerprint and reused by
`--settings-from` without the file. The sheet schema version is bumped, and
older sheets read as having no library, following style pass 1 D-11 exactly.

### D-20. Block mapping and coverage

Decided 2026-10-07 (resolves Q-16 and Q-17, as proposed). Coverage and binary
alpha stay exactly as today, from the colour buffer. A covered block's
material is the alpha-weighted vote of its material IDs; ties go to library
order, then glTF material index. The band comes from the winning material's
pixels in the shade buffer only: `plain` averages then quantises, `mode`
quantises then votes. Exact band boundaries are engineering detail pinned in
MAT-5. Translucent materials are out of scope.

*Clarified on review:* "material IDs" vote as identities, so glTF materials
sharing a name pool their votes (D-18), and the shade is taken from all of the
winning identity's pixels. The tie order and what `mode` votes on are reopened
as [Q-22](#q-22-how-are-ties-broken-and-what-does-mode-vote-on) and settled by
D-23, because "library order" is not well defined for a library of named ramps
and a default, and repeated ramp entries make band votes and colour votes
differ.

### D-21. Generated ramps are built in OKLCh and recorded with their result

Decided 2026-10-07 (resolves Q-19, as proposed). For MAT-8, an entry gives a
base colour, a band count, and hue shifts toward shadow and toward light in
degrees. The ideal ramp is built in OKLCh, the polar form of the OKLab space
already used for palette mapping, then each shade snaps to the nearest palette
entry. Two shades that snap to the same entry keep the repeat, so the band
count never silently changes. The sheet records both the properties and the
resulting index ramp (D-19), so a later change to the generator cannot change
an old sheet's look. Saturation and contrast controls are MAT-8's detail.
**Amended by D-28 and D-33 (owner, 2026-10-14):** the base is the lightest
shade, so there is no hue shift toward light; contrast is `lightness_step`
and saturation is `chroma_fade`.

*Clarified on review:* OKLCh fixes the space, not the formula. The rest is
[Q-24](#q-24-what-is-the-ramp-generation-formula), specified when MAT-8
starts.

### D-22. Bands come from ambient light only

Decided 2026-10-07 (resolves Q-21, option C; amends D-11 and makes D-2
concrete). The shade buffer records non-directional ambient light on uniform
white surfaces, not the directional studio light, so the colour sheet bakes
no directional shading: the lit and far sides of a sleeve take the same band
unless ambient light differs between them. Directional shaping is left
entirely to the later lighting sheet, so it is never applied twice. The owner
accepts flatter sprites until the lighting arc lands. What ambient light
includes is D-25; how Blender produces it is D-10's spike. The colour buffer
and the ordinary look are unchanged.

### D-23. Ties follow the model's material order; `mode` votes by palette entry

Decided 2026-10-07 (resolves Q-22, as recommended; amends D-20's tie order).
Identity ties go to the identity whose lowest glTF material index is
smallest, with the no-identity class last; this depends only on the model, so
the library's key order never matters and recording needs no order. Under
`mode`, each of the winning identity's pixels is mapped to its ramp entry and
the pixels vote by **palette entry**, weighted by colour alpha, as the
existing paletted `mode` does, so repeated ramp entries pool. A tie goes to
the entry whose band is nearest the winner's alpha-weighted mean shade, then
to the smaller palette index.

*Clarified on review:* an entry repeated in a ramp has several bands. Its
distance is from the mean shade to the nearest centre among all its
occurrences, whether or not they received votes, in exact arithmetic
([Mapping a block](#mapping-a-block-d-7-d-9-d-20)).

### D-24. Reused libraries and explicit options

Decided 2026-10-07 (resolves Q-23, as recommended). With `--settings-from`:
a reused library and reused palette are allowed; a reused library with an
explicit different palette is a usage error unless the library is also given
explicitly or dropped, since a new palette would silently recolour every
ramp; a reused library with `--no-palette` is a usage error (D-6); an
explicit library is validated against whichever palette is in force. A new
`--no-materials` drops a reused library, and giving it with an explicit
library is a usage error, as `--palette` with `--no-palette` is. A deliberate
palette swap that keeps a library is a variant, deferred with palette swaps
(design §Deferred). All of this is checked before any Blender invocation.

*Clarified on review:* "different" compares the palettes' ordered colour
lists. The same colours in the same order from another file name or format
are the same palette; reordered, added or changed colours are different. File
names and hashes stay provenance only.

### D-25. Ambient means occlusion and curvature only

Decided 2026-10-07 (resolves Q-25, option A, widened by the owner to
curvature). The shade buffer records only creases, nooks and crannies
(occlusion) and curves (surface curvature). No sky, ground or other
direction-dependent light: the owner's engine shades the face maps generated
alongside the sprites, so brightness from the sky, the ground and the sun is
live. The sprite carries what live lighting cannot: each material's
**hue-shifted ramp**, chosen by local form. Broad flat open surfaces take one
band; the owner accepts that. How Blender produces occlusion and curvature
deterministically is D-10's spike.

### D-26. `MASK` materials are captured opaque, with no cutouts

Decided 2026-10-08 (resolves Q-26, option A; owner, relayed by laz,
#moskophoros `nubgv9twjfegt38t7dm5iredee`): "alpha will not be supported until
i get further along in the project." The ID and shade buffers match the colour
as it is captured today: a `MASK` material is drawn over its whole surface,
its transparent texels opaque, with no cutouts, so every pixel's identity and
shade are those of the surface the colour shows and the three buffers stay
aligned. No surface behind a `MASK` texel is identified. Honouring `MASK`
cutouts in the colour (Q-26's option C) is a separate, deferred follow-up that
needs its own explicit owner request; until then nothing here changes the
colour output or implies alpha support.

### D-27. The lighting sheet is a normal map with an optional depth map; light is previewed, not baked

Decided 2026-10-13 by the owner in the manager terminal, after reviewing the
settings arc's R1 and R2 renders (resolves Q-11, option A, and adds a depth
map). The owner's direction, in their words: "moskophoros is going to create a
sprite that is flatly shaded, only R1 and R2, basic ambient light", output
alongside a map "containing information on the geometry of the object" that
goes to the game's shader, "and we will then be able to handle any sort of
lighting in our 2D world". Their summary of what follows: "for the cli
interface, just output flat, but give the optional flag to place the light."

- **Colour sheet:** flat ambient shading only (occlusion and curvature, D-22,
  D-25). This confirms D-2: no point or directional light is baked by default.
  The tool must keep this capability whatever else it gains.
- **Lighting sheet:** a standard normal map, aligned pixel for pixel with the
  colour sheet. It holds each pixel's surface direction relative to that
  frame's own camera, encoded in RGB. The game converts it to whatever its
  shader needs, including face weights (V-1).
- **Depth map:** an optional, equally aligned depth or height map, so a game
  can light a pixel from a light at a position in its world, not only from a
  distant light.
- **Lit preview:** an optional light is a preview, not a bake. The tool
  lights the flat sprite with its own normal map, the same calculation a
  game shader makes, so the owner sees the sprite as the game will light it.
  The exported colour sheet stays flat.
- **Command line:** the default output stays flat. An optional flag places
  the light for the lit preview.
- **The owner's planned interface** (outside this tool's command line):
  previews are lit by default, the viewer can turn the light off or move it
  freely around the object, and export writes the flat render by default,
  with no light.
- **Out of scope for now:** shadows that one part casts on another. Baked
  ambient occlusion (the R1 behaviour) stands in for them. The owner expects
  cast shadows as a possible later project.
- **Risk:** keeping the normal and depth maps aligned with the colour sheet at
  small cell sizes is hard. Normals must be averaged, not palette-mapped.
  Expect to need the owner's visual check.

Open for the lighting-sheet design: the light flag's form and units; the
depth encoding; how units facing 8 directions combine with the engine's 4
camera rotations; whether materials perturb normals; and how the sheet's JSON
describes the new maps.

### D-28. A generated ramp's base colour is its lightest shade

Decided 2026-10-14 by the owner in the manager terminal, after reviewing
sample ramps (part of Q-24). The owner chose "Lightest shade": a generated
ramp's last band, band N−1, is the base colour itself, and every other band
is darker. A generated ramp has no shift toward light, so D-21's "hue shift
toward light" is dropped.

Evidence (outside the repository): the manager's prototype
`~/.local/share/moskophoros-acceptance/ramp-gen/gen.py`, and ten sample
materials under three settings in `ramp-gen/samples.json`.

Affects MAT-8.

### D-29. The base colour is written in the library

Decided 2026-10-14 by the owner in the manager terminal (part of Q-24). The
owner chose "Written in the library": each generated ramp states its base
colour in the library, so a material looks the same on every model (D-3). The
model's own glTF colour is not used.

Affects MAT-8.

### D-30. Setting B is the default formula, and the formula's values are settings

Decided 2026-10-14 by the owner in the manager terminal (part of Q-24). In
the owner's words: "B should be the default, but im definitely using C for my
actual synarchy project, i like the high contrast from the large hue shift,
but just a little would be more versitile for a variety of uses, and i will
be using to make other things."

- **B, the shipped default:** each shade darker lowers OKLab lightness by
  0.12 and turns the hue by −12°. Chroma fades linearly to 70% of the base
  colour's at the darkest shade (a fade of 0.3).
- **C, the owner's setting for their own project:** a step of 0.09, −35° per
  shade and a fade of 0.6.
- **Consequence:** the formula's three values are settings (the user file,
  `--config` files and options; settings design D-2), as well as values a
  library may give, so the owner's user settings can choose C while the
  shipped default stays B.

Affects MAT-8.

### D-31. Per-material formula overrides are wanted

Decided 2026-10-14 by the owner in the manager terminal (part of Q-24). In
the owner's words: "i know we need the capability but im not sure we need to
implement now, having metals and other reflective surfaces have a larger
shift would be an obvious improvement, but im not sure any other examples."

The capability is wanted. Whether MAT-8 implements it, or only leaves room
for it in the library format, is
[Q-28](#q-28-how-does-a-library-give-a-generated-ramp).

Affects MAT-8.

### D-32. The shade range 190–225 is carried by the material files

Decided 2026-10-14 by the owner in the manager terminal, after the range
review. In the owner's words: "ok yes 190-225 looks best, maximizing detail
while maintining abstraction, these ranges should be in the material files
for color ramps, we can set them to this value or let them fallback to it as
a default, whichever sounds best to you."

- The owner judged 190–225 by eye (V-12). At the owner's earlier 120–220,
  about 96% of the robot's body took the base shade; at 190–225 the body is
  about 63% darkest, 17% middle and 20% base (renders in
  `~/.local/share/moskophoros-acceptance/ramp-gen/check/`, `ramp-gen/narrow/`
  and `robotexpressive/ramp-gen-check/`).
- A material library carries its range. The owner left the form open; the
  manager proposed a library-level default, which is
  [Q-29](#q-29-does-a-library-give-a-default-shade).
- The shipped default range stays [84, 191] (settings design D-12).

Affects MAT-8.

### D-33. The exact formula, and its values as settings

Decided 2026-10-14 by the owner in this design's pane (resolves Q-27, as
proposed): "yes, all of your recommendations are sound to me, i approve".

**The formula.** It is the manager's reviewed prototype, made exact. It snaps
from the unrounded colour, which picks the same indices on all 30 reviewed
sample ramps. Given:

- a base colour (sRGB `#rrggbb`), and its OKLCh lightness, chroma and hue
  `L0, C0, h0`, with `h0 = atan2(b0, a0)` in degrees, using the OKLab
  conversion that palette mapping already uses;
- a band count N;
- the values `step` (`lightness_step`), `hue` (`hue_shift_deg`) and `fade`
  (`chroma_fade`).

Band `i` (0 the darkest) is `k = N − 1 − i` shades below the base, so band
N − 1 is the base (D-28). For each band:

- `L = max(0, L0 − step·k)`;
- `h = h0 + hue·k`, except that `h = h0` when `C0 < 0.02`: a near-grey keeps
  its hue;
- `C = C0·(1 − fade·k/(N − 1))`, and `C = C0` when N = 1;
- **Gamut:** if `(L, C, h)` lies outside the sRGB gamut, `C` is reduced by 40
  halvings of the interval `[0, C]`, keeping the largest value tested in
  gamut. A colour is outside the gamut when a linear channel is below −10⁻⁶
  or above 1 + 10⁻⁶. Lightness and hue never change.
- **Snapping:** the shade snaps to the palette entry nearest it in OKLab, by
  Euclidean distance. Equal distances go to the lower index, as in palette
  mapping. Repeats are kept, so the band count never changes (D-21).

*Clarified on MAT-8 review 1 (M-2): the numerical reference.* This completes
the arithmetic above without changing it. It still reproduces all 30 reviewed
sample ramps.

1. **Base to OKLab:** decode the base's 8-bit sRGB to linear with the
   palette-mapping table, then apply palette mapping's OKLab conversion
   (`imageops._oklab`: its matrices, `cbrt`, the same operation order).
   - `C0 = hypot(a0, b0)`, and `h0 = atan2(b0, a0)` in degrees.
2. **A shade's coordinates:**
   - `a = C·cos(h·π/180)`, `b = C·sin(h·π/180)`, in float64.
   - Hue needs no wrapping.
3. **The gamut predicate** converts `(L, a, b)` to linear sRGB with the
   inverse of Björn Ottosson's 2021 matrices:
   - `l = (L + 0.3963377774a + 0.2158037573b)³`
   - `m = (L − 0.1055613458a − 0.0638541728b)³`
   - `s = (L − 0.0894841775a − 1.2914855480b)³`
   - `R = 4.0767416621l − 3.3077115913m + 0.2309699292s`
   - `G = −1.2684380046l + 2.6097574011m − 0.3413193965s`
   - `B = −0.0041960863l − 0.7034186147m + 1.7076147010s`

   The colour is in gamut when every channel is in `[−10⁻⁶, 1 + 10⁻⁶]`. The
   tolerance belongs to this predicate only.
4. **The search:** if `C` passes, keep it. Otherwise set `lo = 0` and
   `hi = C`, then 40 times set `mid = (lo + hi)/2`, setting `lo = mid` if
   `mid` passes, else `hi = mid`. The result is `lo`. `C = 0` always passes.
5. **Snapping** compares the shade's own coordinates `(L, a, b)`, after the
   search, with each palette entry's OKLab as palette mapping computes it.
   - The shade is not converted back to RGB, clamped or rounded.
   - The comparison uses the sum of squared differences. A later entry wins
     only when strictly nearer, so equal distances keep the lower index.

**Pinned cases:**
- **The review's counterexample.** Base `#000040`, N = 2, step 1, hue −12°,
  fade 0.3, with the two-entry palette `[#000003, #010000]`, gives
  `[0, 0]`. A clamped RGB round trip would give `[1, 0]`.
- **Setting B on Vince 144:**
  - gold `#ca9337`, N = 4: `[18, 19, 4, 5]`;
  - near-grey steel `#8c939c`, N = 4: `[111, 133, 135, 137]` (C0 ≈ 0.016, so
    the hue is not shifted).
- **Setting C on Vince 144:**
  - gold: `[110, 13, 4, 5]`;
  - steel: `[132, 134, 136, 137]`.

**The settings.** A new global `ramp` mapping (settings design D-2 layers),
with one option per value:

| Setting | Option | Default (B, D-30) | Limits |
|---|---|---|---|
| `ramp.lightness_step` | `--ramp-step L` | 0.12 | finite, 0 to 1 |
| `ramp.hue_shift_deg` | `--ramp-hue-shift DEG` | −12 | finite, −180 to 180 |
| `ramp.chroma_fade` | `--ramp-fade F` | 0.3 | finite, 0 to 1 |

- A generated ramp's own value (D-34) beats the global value from any layer.
  An explicit global (from `--config` or an option) that loses to a ramp in
  use gives a warning naming that ramp and the value it kept, as settings
  design D-23 does for shade values.
- **The sheet record:**
  - The sheet records the global values as `settings.ramp`, in the order
    `lightness_step`, `hue_shift_deg`, `chroma_fade`, between `shade` and
    `style`, inside the fingerprint, whether or not a library is used.
  - This bumps the sheet schema, and under settings design D-24 and D-30 the
    previous schema stops loading.
- Each generated ramp is recorded in the inline library with its properties
  as given and its resulting indices (D-21, D-34).
- **A loaded sheet** reuses each recorded result without regenerating it.
  - When an explicit value (from `--config` or an option) changes a reused
    ramp's effective inputs, that ramp is regenerated from its recorded
    properties.
  - The user file sits below the loaded sheet (settings design D-8), so it
    never changes a loaded sheet's ramps.
  - The reused-library palette rules (D-24) are unchanged.

Affects MAT-8.

### D-34. A ramp may be given as properties, with its own formula values

Decided 2026-10-14 by the owner in this design's pane (resolves Q-28, as
recommended).

- Wherever a library gives a ramp as a list of palette indices, it may give a
  mapping of properties instead. That covers a named ramp under `ramps` and a
  material's own `ramp`.
  - `base` (sRGB `#rrggbb`) and `bands` (a whole number from 1 to 256) are
    required.
  - `lightness_step`, `hue_shift_deg` and `chroma_fade` are optional, with
    the global settings' limits. An omitted value takes the global value
    (D-33).
  - No other key is allowed.
- **Per-ramp overrides ship in MAT-8.** This is D-31's capability: for
  example, a metal ramp with a larger hue shift. Adding them later would cost
  another library schema bump.
- A hand-listed ramp and a generated ramp are alternatives for the same
  place, and a library may mix them. D-12's "a hand-listed `ramp` overrides
  generated shades" means that listing a ramp's indices remains the exact
  control.
- **The library schema becomes `moskophoros.materials/3`.**
  - A `moskophoros.materials/2` library still loads, since every `/2` library
    is valid `/3`, and is read exactly as before.
  - `/1` stays refused (settings design D-29).
  - Only a `/3` library may give generated ramps or a library `shade` (D-35).
- **The sheet record:** a generated ramp is a mapping of the properties as
  given, in the order `base` (canonical lowercase), `bands`,
  `lightness_step`, `hue_shift_deg` and `chroma_fade`, then `indices`, the
  generated result. A hand-listed ramp stays a list.
- **Validation:**
  - A malformed mapping, a value out of its limits or a `/2` library using a
    `/3` feature is a usage error (exit 2) before Blender, naming the file
    and the ramp.
  - A reloaded record's `indices` must be N valid palette indices.

Example:

```yaml
schema: moskophoros.materials/3
ramps:
  stone: [133, 135, 137, 138, 139]
  gold: {base: "#ca9337", bands: 4}
  chrome: {base: "#8c939c", bands: 5, hue_shift_deg: -35, chroma_fade: 0.6}
materials:
  Main: {uses: gold}
  Cloth: {ramp: {base: "#7a3b2e", bands: 3}}
```

Affects MAT-8.

### D-35. A library may give a default shade

Decided 2026-10-14 by the owner in this design's pane (resolves Q-29, the
manager's form, as recommended). This is the form of D-32. **Amended by D-36
(owner, 2026-10-14):** the library `shade` gives `range` only, so the
capture-value parts below no longer apply.

- A `/3` library may give a top-level `shade` mapping, with the keys a
  material's `shade` may give: `ao_distance_m`, `occlusion_weight`,
  `convexity_weight` and `range` (settings design D-20). The validation is
  the same.
- **Resolution order:** each value is taken from the first of these that
  sets it:
  1. the material's own `shade`;
  2. the library's `shade`;
  3. the settings layers;
  4. the shipped default.
- Materials without an entry that take the library's default ramp also use
  the library's `shade`. The ordinary look uses no shade, as now.
- **Consequence:** where a library sets a value, `--shade-range`, the other
  shade options and the user file's values no longer reach that library's
  materials.
  - An explicit global that loses to the library's value gives one warning,
    naming the library's value.
  - This follows settings design D-23.
- **The sheet record:** the library's `shade` sits in the inline library
  record after `default`, holding only the keys given, in settings design
  D-37's fixed order. A library without one has no `shade`.
- The library's capture values reach Blender per material, in the capture
  job (settings design D-36).
- The shipped default range is unchanged (D-32). The owner's library can then
  state `shade: {range: [190, 225]}` once instead of on every material.

Affects MAT-8.

### D-36. A library's default shade gives the range only

Decided 2026-10-14 by the owner in this design's pane (resolves Q-30, option
A, as recommended): "A". It amends D-35.

- A library's top-level `shade` may give only `range`. The range is a
  stylize value. A library `shade` giving `ao_distance_m`,
  `occlusion_weight` or `convexity_weight` is a usage error (exit 2) before
  Blender, naming the file and the key.
- **The range resolves in D-35's order:** the material's own, then the
  library's, then the settings layers, then the shipped default. The
  library's range also applies to materials with no entry that take the
  default ramp.
- **Capture values are unchanged from today.** They come from a material
  entry's own `shade`, else the global values. Materials taking the default
  ramp, the ordinary look, unnamed and `BLEND` surfaces take the globals.
- **Settings design D-36, design.md §Capture and the capture job contract
  stand unchanged.**
  - The job never carries the library's `shade`.
  - The job is the same whatever the default ramp and the ranges.
- **Consequence:** where a library sets a range, `--shade-range` and the user
  file's range no longer reach that library's materials. The warning of D-35
  applies. The other shade options keep reaching every material without its
  own value.
- **Later:** library-wide capture values remain possible as Q-30's option B,
  at the cost of a library schema bump.

Affects MAT-8.

## Open questions

None open. Q-24 is resolved by D-28 to D-36 (2026-10-14), with Q-27, Q-28,
Q-29 and Q-30 by D-33, D-34, D-35 and D-36. Q-11 is resolved by D-27. Q-21, Q-22 and Q-23, raised by an
outside review on 2026-10-07, are resolved by D-22, D-23 and D-24; Q-25,
raised by D-22, by D-25; Q-26, raised by the D-10 spike, by D-26.

Resolved: Q-1, Q-2, Q-3, Q-5, Q-6, Q-7, Q-9, Q-10, Q-12, Q-14, Q-15, Q-16,
Q-17, Q-18, Q-19 and Q-20 by D-5 (since superseded by D-11), D-7, D-8, D-6,
D-19, D-9, D-11, D-12, D-13, D-18, D-15, D-20, D-20, D-16, D-21 and D-17;
Q-8's process by D-10. Q-4 is folded into Q-11. Q-13 is unused. Resolved
entries keep their alternatives as history; their decisions are
authoritative.

### Q-6. Exactly how is the library recorded?

**Resolved by D-19**: inline in `settings.style` with base name and SHA-256,
covered by the fingerprint, reused by `--settings-from`, schema bumped as in
style pass 1 D-11. Override rules are D-24.

### Q-9. Should the band come from a shade buffer instead of render luminance?

**Resolved by D-11** (option B). Kept for the rejected alternatives.

*Reopened D-5 with new evidence.* Workbench's `TEXTURE` colour is the
material's colour times the studio light. Its luminance therefore mixes three
things: light, the material's own brightness and any texture detail. A dark
material only reaches the low bands; a light one only the high bands; a
texture's painted details become band changes. That is probably why ramps
have looked "off".

- **A. Keep D-5:** render luminance, normalised per material by its own
  observed range. No new buffer, but ranges vary per frame and clip, so a
  material's bands can shift between frames, and textures still leak in.
- **B. A light-only shade buffer:** a second capture of the same frame with
  every surface one uniform white under the same camera-fixed studio light.
  It holds the light only, the same for every material, so band N means the
  same light everywhere. One more Workbench render per frame; no normals.
- **C. Normals now:** capture normals and compute the light in stylize. The
  most control, but it pulls the lighting-sheet arc forward and needs a
  lighting model now.

**Recommendation: B.** It fixes the root cause at little cost, stays inside
the current Workbench setup, and leaves normals to the lighting arc. Affects
MAT-3 and MAT-5.

### Q-10. Can material properties generate a ramp?

**Resolved by D-12** (option C). The property set and snapping rules are
[Q-19](#q-19-how-are-ramps-generated-from-properties).

The owner's first idea was that "each material should have properties" that
"automatically get converted to the scaled color map". D-7 settled only
hand-listed palette indices.

- **A. Hand-listed only** (D-7 as is). Exact control; every ramp hand-made.
- **B. Generated, then snapped:** an entry gives properties: a base colour,
  band count, hue shift toward shadow and toward light, saturation change and
  contrast. The tool builds the ideal ramp from them in OKLab, then snaps each
  shade to the nearest palette entry (D-6 holds). A listed `ramp` still
  overrides.
- **C. B later:** ship A in this arc and add B as the next slice.

**Recommendation: C.** A ships the look sooner and lets the owner judge
banding first. B is the better long-term authoring model and the natural home
for the "flatness" and baked/live controls. Snapping can produce repeated
colours, which B must handle. Affects MAT-4 and MAT-5.

### Q-11. What does the lighting sheet encode?

**Resolved by D-27** on 2026-10-13: option A, a standard normal map, plus
an optional depth map.

For the later arc; recorded now so this arc does not rule anything out. The
owner's engine reads three face weights (R right, G top, B left); Dead Cells
and most engines read a normal map.

- **A. A standard normal map** (camera-space direction encoded in RGB); the
  game converts.
- **B. A generic projection:** weights of the surface direction onto N
  screen-relative directions given as settings, with "right, top, left"
  as one possible configuration and no game name in the tool (V-1).
- **C. Both.**

Needs the facemap channel convention confirmed for Hetoimasia, and how units
facing 8 directions combine with the engine's 4 camera rotations. Affects the
later arc only.

### Q-12. Are the new buffers captured on every render?

**Resolved by D-13** (always).

The proposal captures them always, keeping the capture job style-independent
(V-4; style pass 1 D-11). Cost: one or two extra Workbench renders per frame
for every sheet, used or not. The alternative is a capture setting naming the
buffers, which changes the job and makes a library experiment fail with
"re-render with X" when the buffer is missing. **Recommendation: always.**
Affects MAT-3.

### Q-14. What input rules does material identity need?

**Resolved by D-18**: names from the glTF JSON, compared exactly; equal
names are one identity; unnamed or missing materials have no identity and,
with a library, one warning counts them. Malformed names and references are
proposed input errors in [Identity](#identity-d-3-d-18).

### Q-15. What happens to texture detail and to unused library entries?

**Resolved by D-15**: textured materials stay out of the library or are
marked `"ordinary"`, keeping their painted detail; unused entries are
silent.

### Q-16. Exactly how is each block mapped?

**Resolved by D-20**, clarified on review: identity vote pooled by name,
shade from the winner's pixels, `plain` averages then quantises. Tie order and
`mode`'s vote were reopened as Q-22 and settled by D-23.

### Q-17. How do transparency and coverage work?

**Resolved by D-20**: coverage and binary alpha as today; translucent
(`BLEND`) materials out of scope. `MASK` materials are captured opaque, with
no cutouts (D-26; [Capture](#capture-d-10-d-11-d-13)).

### Q-18. What are the acceptance inputs?

**Resolved by D-16**: the stock robot (three named materials, checked),
Vince128, and ramps the owner signs off.

### Q-19. How are ramps generated from properties?

**Resolved by D-21**: base colour, band count and hue shifts in degrees,
built in OKLCh, snapped to the palette keeping repeats, recorded with both
properties and result. The formula itself is Q-24.

### Q-20. What are "default fallbacks"?

**Resolved by D-17** (B, with A as an optional default). The owner wants
per-material ramps "and then some default fallbacks". This
may revise D-9, under which a material without an entry gets the ordinary look
and no default ramp is invented. Candidates:

- **A. A library-wide default ramp:** every named material without an entry
  uses it, with D-9's warning kept. Unnamed parts and `"ordinary"` entries
  (D-15) still get the ordinary look.
- **B. Named fallback ramps by kind:** the library defines generic ramps such
  as `metal`, `cloth` or `skin`, and an entry or a name pattern points a
  material at one, so a new model works before it has its own entries.
- **C. Keep D-9:** the ordinary look is the fallback, and "default fallbacks"
  means a starter library of generic ramps to copy from.

Affects MAT-4, MAT-5 and MAT-7.

### Q-21. How much directional shading does the colour sheet bake?

**Resolved by D-22** (option C). Kept for the rejected alternatives.

D-2 says the colour sheet bakes a *modest* ambient shading and leaves strong
directional shaping to live lighting. But the band follows the studio light
(D-11), which is directional: the lit side of a sleeve takes the top band and
the far side the bottom. The band count sets how many steps there are, not
how far apart they are; only the ramp's colours set that. If the later
lighting sheet then lights the sprite live, directional shading is applied
twice.

- **A. Accept it for the first release:** bands follow the studio light;
  how strong that looks is authored in each ramp (close colours for modest
  shading, far apart for bold). The baked-versus-live split is revisited
  with the lighting arc, which may ask for flatter ramps or a separate
  ambient pass.
- **B. Bound it now:** add a library-level shade window or contrast control
  that compresses the shade range before banding, so baked shading is
  modest by construction.
- **C. Ambient-only bands now:** derive the band from a non-directional
  light (for example uniform ambient or occlusion), leaving all directional
  shaping to the lighting sheet. Flatter sprites until the lighting arc
  lands, and a different spike.

**Recommendation: A.** Contrast in the ramp is the pixel-art way to author
it, the owner signs off every ramp anyway, and B or C can be added once the
lighting arc defines what "live" needs. Affects MAT-5, MAT-7.

### Q-22. How are ties broken, and what does `mode` vote on?

**Resolved by D-23** (as recommended).

D-20 sends identity ties to "library order, then glTF index". But a library
is a set of named ramps, a default and keyed entries, so its order depends on
JSON key order, and defaulted, unnamed and `"ordinary"` materials have no
place in it. And for `mode`, a ramp may repeat an entry (D-21 keeps repeats,
and a hand-listed ramp may too): with `[red, red, blue]` and band votes of
30%, 30% and 40%, voting by band picks blue, voting by output colour picks
red. The existing paletted `mode` maps to the palette and then votes, so it
pools by output colour (`imageops.reduce_blocks_mode`).

**Recommendation:**

- **Identity ties** go to the identity whose lowest glTF material index is
  smallest, with the no-identity class last. This depends only on the model,
  never on the library, so recording needs no order.
- **`mode`** quantises each of the winner's pixels to its band, maps it to
  its palette entry, and votes by **output palette entry**, weighted by
  colour alpha, as the existing paletted `mode` does. A tie goes to the
  entry whose band is nearest the winner's mean shade, then to the smaller
  palette index.

Affects MAT-5.

### Q-23. How do explicit options combine with a reused library?

**Resolved by D-24** (as recommended).

Today an explicit `--palette` replaces a reused palette and `--no-palette`
drops it. A reused library adds combinations:

| Library | Palette | Recommendation |
|---|---|---|
| reused | reused | allowed |
| reused | explicit, different | **usage error**: the library's indices were chosen for the recorded palette, and a new palette silently changes every colour. Give the library explicitly too, or drop it. |
| reused | `--no-palette` | usage error (D-6: a library needs a palette) |
| explicit | reused or explicit | allowed, validated against that palette |
| `--no-materials` | any | the reused library is dropped; the ordinary looks apply |

An explicit library and `--no-materials` together are a usage error, as
`--palette` with `--no-palette` is. A deliberate palette swap that keeps a
library is a variant, deferred with palette swaps (design §Deferred).
Affects MAT-6.

### Q-24. What is the ramp-generation formula?

**Resolved by D-28 to D-35** (2026-10-14). Kept for its list of what the
formula had to settle.

For MAT-8, beyond D-21: the lightness endpoints and where the base colour
sits in the ramp; how hue shifts interpolate across bands; how achromatic
(grey) base colours take a hue shift; the units and limits of saturation and
contrast; and how a shade equally near two palette entries snaps.
**Specified when MAT-8 starts**, with a short owner review of sample ramps;
MAT-8 is not ready until then. Affects MAT-8.

*Progress, 2026-10-14:* the owner reviewed sample ramps and decided D-28 to
D-32. What remains is split into Q-27 (the exact formula and its settings),
Q-28 (the library format) and Q-29 (the library's default shade).

### Q-27. What exactly is the formula, and how is it set?

**Resolved by D-33** (as proposed).

**Proposal: the formula as reviewed, made exact.** It is the manager's
prototype, with one change: shades snap from the unrounded colour, not from an
8-bit copy. Snapping from the unrounded colour gives the same palette indices
on all 30 reviewed sample ramps (ten materials, settings A, B and C, Vince
144).

Given a base colour (sRGB `#rrggbb`), its OKLCh lightness, chroma and hue
`L0, C0, h0` (with `h0 = atan2(b0, a0)`, the same OKLab conversion as palette
mapping), a band count N, and the values `step`, `hue` and `fade`, band
`i` (0 darkest) is `k = N − 1 − i` shades below the base:

- `L = max(0, L0 − step·k)`;
- `h = h0 + hue·k`, or `h0` when `C0 < 0.02` (a near-grey keeps its hue);
- `C = C0·(1 − fade·k/(N − 1))`, or `C0` when N = 1;
- if `(L, C, h)` is outside the sRGB gamut (a linear channel below −10⁻⁶ or
  above 1 + 10⁻⁶), `C` is reduced by 40 halvings between 0 and `C`, keeping
  the largest value found in gamut; lightness and hue never change;
- the shade snaps to the palette entry nearest in OKLab, Euclidean distance,
  equal distances to the lower index (as palette mapping does), and repeats
  are kept (D-21).

**Proposal: the settings.** A new `ramp` mapping, global values with options:

| Setting | Option | Default (B) | Limits |
|---|---|---|---|
| `ramp.lightness_step` | `--ramp-step L` | 0.12 | finite, 0 to 1 |
| `ramp.hue_shift_deg` | `--ramp-hue-shift DEG` | −12 | finite, −180 to 180 |
| `ramp.chroma_fade` | `--ramp-fade F` | 0.3 | finite, 0 to 1 |

- A generated ramp's own value beats the global one from any layer, with a
  warning when an explicit global loses, as for shade values (settings
  design D-23).
- The sheet records the global values (a sheet schema bump, settings design
  D-30) and, for each generated ramp, its properties as given and its
  resulting indices (D-21).
- A loaded sheet reuses the recorded indices without regenerating them. An
  explicit value or `--config` that changes a ramp's inputs regenerates it
  from its recorded properties.

Affects MAT-8.

### Q-28. How does a library give a generated ramp?

**Resolved by D-34** (as recommended).

**Proposal:** anywhere a library gives a ramp as a list of indices, a named
ramp under `ramps` or a material's own `ramp`, it may give a mapping instead:

```yaml
ramps:
  stone: [133, 135, 137, 138, 139]
  gold: {base: "#ca9337", bands: 4}
  chrome: {base: "#8c939c", bands: 5, hue_shift_deg: -35, chroma_fade: 0.6}
materials:
  Main: {uses: gold}
  Cloth: {ramp: {base: "#7a3b2e", bands: 3}}
```

- `base` and `bands` are required; `bands` is 1 to 256, as a listed ramp's
  length is.
- **Recommendation:** ship the per-ramp overrides of D-31 in MAT-8.
  - They are three optional keys with the global settings' validation.
  - Adding them later needs another library schema bump, and under settings
    design D-29 a bump stops every older library loading until its `schema`
    line is edited.
- The library schema becomes `moskophoros.materials/3`. **Recommendation:**
  a `/2` library still loads. Every `/2` library is valid `/3`, so the owner's
  existing libraries need no edit. The alternative is D-29's precedent, where
  the older schema stops loading.

Affects MAT-8.

### Q-29. Does a library give a default shade?

**Resolved by D-35** (as recommended).

**Proposal (the manager's form):** a top-level `shade` mapping in the
library, with the same keys a material's `shade` may give (`ao_distance_m`,
`occlusion_weight`, `convexity_weight`, `range`; settings design D-20).

```yaml
schema: moskophoros.materials/3
shade: {range: [190, 225]}
```

- Each value resolves in order: the material's own `shade`, the library's
  `shade`, the settings layers, the shipped default.
- Materials with no entry that take the library's default ramp use the
  library's `shade` too. The ordinary look uses no shade, as now.
- **Consequence:** where a library sets a value, `--shade-range` and the user
  file's range no longer reach that library's materials. An explicit global
  that loses gives one warning naming the library's value, as settings
  design D-23 warns for a material's own value.
- The sheet records the library's `shade` inline with the library. Its
  capture values reach Blender per material, as settings design D-36 sets
  out.

The alternative is that each material sets its own range, as the owner's
library does today. This works now but repeats the range in every entry.

Affects MAT-8.

### Q-30. Which materials take a library's capture values?

**Resolved by D-36** (option A, as recommended).

Raised by MAT-8 review 1 (M-1, blocking).

**The conflict:** D-35 makes three promises that cannot all hold:
- A library `shade` may give capture values (`ao_distance_m`,
  `occlusion_weight`, `convexity_weight`), not only `range`.
- A material with no entry that takes the default ramp uses the library
  `shade`.
- Settings design D-36, design.md §Capture and the capture job contract
  promise that the capture job is the same whatever the default ramp. A
  material with no entry takes the global capture values, as the code does
  today (`materials.capture_overrides`).

For example, take a library with `shade: {convexity_weight: 0}` and no
`default`. A model material `Unknown` with no entry is captured with the
global weight. Add `default: r`, and D-35 gives it weight 0. Adding a default
ramp has changed the capture.

**Options:**
- **A. The library default gives the range only** (the manager's
  suggestion).
  - The library `shade` may give only `range`, a stylize value.
  - Capture values stay per material, in material entries, as today.
  - D-36 and the capture contract are untouched.
  - The default-ramped materials take the library range.
  - This covers what D-32 asked for: "these ranges should be in the material
    files".
  - Library-wide capture values would need a later library schema bump.
- **B. The review's narrow amendment.**
  - The library `shade` gives all four values.
  - Every material taking a ramp, through its entry or the default, takes the
    library's capture values.
  - Ordinary, unnamed and `BLEND` surfaces keep the global values.
  - D-36 is amended: the job may change when adding or removing a default
    changes which materials inherit library capture values. It stays
    independent of ramp indices and properties, the palette, the reduction
    and the range.
  - A library without capture values in its `shade` keeps today's behaviour.

**Recommendation: A.**
- It is the smaller contract, and it meets the need that prompted D-32.
- The owner's capture values (AO distance 1.2, weights 0.5 and 0.25) already
  live in the user settings, and nothing so far asks for them per library.
- B stays possible later, at the cost of a library schema bump.

Affects MAT-8.

### Q-25. What does "ambient light" include?

**Resolved by D-25** (A, widened to curvature). Kept for the alternatives.

D-22 takes bands from non-directional ambient light. Uniform ambient light
alone is the same everywhere, so every material would be one band. Something
must vary:

- **A. Occlusion only:** open surfaces are brightest, creases, armpits and
  the inside of a cloak darker. Fully independent of direction; the most
  "pure" ambient.
- **B. Sky and ground (hemisphere):** surfaces facing up lit like the sky,
  facing down like the ground, in between blended. Fixed to the world's up,
  not to any sun or the camera, so it is the same from all eight directions.
- **C. Both:** hemisphere light darkened by occlusion. The common games
  ambient term.

**Recommendation: C.** A alone leaves broad flat surfaces in one band, which
is very flat; B alone ignores creases. C gives a soft top-to-bottom
gradient plus contact shading, neither of which a live directional light
supplies, so nothing is applied twice. Its technique and determinism are
D-10's spike. Affects MAT-3, MAT-5 and MAT-7.

### Q-26. How do `MASK` cutouts relate between the colour and the ID and shade buffers?

**Resolved by D-26** (option A, 2026-10-08). Found by the D-10 spike (2026-10-08). §Capture and
MAT-3 require the ID and shade passes to keep `MASK` cutouts "so surfaces
behind a hole are identified as in the colour", assuming the colour discards
them. It does not: Workbench ignores the alpha the glTF importer builds for a
`MASK` material, so a transparent texel renders as the texture's colour,
opaque (the *edges* fixture's holes are `(54, 54, 54, 255)`), and the
material behind never shows. Setting the legacy `blend_method` to `CLIP` or
`BLEND`, or `surface_render_method` to `BLENDED`, changes nothing.

- **A. Match the colour as captured:** the ID and shade show the `MASK`
  material over its whole surface, as the colour does. Every pixel's
  identity is the surface the colour shows; no surface behind a hole is
  identified. Contradicts the literal "cutouts are kept".
- **B. Cut out the ID and shade only:** surfaces behind a hole are
  identified, while the colour there shows the `MASK` material's
  transparent texels, so those pixels vote for one material and show
  another's colour.
- **C. Make the colour honour cutouts first:** a separate change that alters
  existing sheets of `MASK` models (no longer byte-identical) and needs its
  own technique, since Workbench settings alone do not do it; the ID and
  shade then keep the same cutouts.

**Recommendation: A for MAT-3, and C as its own issue.** A keeps every
pixel's identity the surface the colour shows, which is what a block's vote
needs; B makes those pixels disagree. The colour ignoring cutouts is a
defect of its own, for foliage, hair cards and fences; when C lands, the ID
and shade passes keep the same cutouts, which the Cycles method can do from
the importer's alpha. Affects MAT-3, and through it MAT-5 and MAT-7.

## MAT-8 review 1

Codex (mosk-solver-27) reviewed MAT-8's design at `7b227fc`. Report:
`~/.local/share/moskophoros-acceptance/ramp-gen/review-codex-mat8-1.md`, with
probes in `review-1/` beside it. It had 1 blocking finding and 3 should fix.
Each was verified against the code and design.md before its disposition.

| Id | Finding | Disposition |
|---|---|---|
| M-1 | D-35's library capture values for default-ramped materials contradict settings design D-36 and the capture contract | Confirmed (`materials.capture_overrides` gives such materials the global values). Resolved by D-36 (Q-30, option A): the library `shade` gives the range only, so D-36 of the settings design and the capture contract stand. |
| M-2 | Snapping after the gamut search is ambiguous (direct OKLab vs the prototype's RGB clamp) | Fixed. D-33 gains a numerical reference: snap directly from the post-search OKLab; the tolerance is the predicate's only; the counterexample is pinned. Reproduced: `[0, 0]`, and all 30 sample ramps still match. |
| M-3 | Acceptance omits existing hand-listed libraries | Fixed. MAT-8 adds before-and-after preservation for `/2` and listed `/3` libraries under `plain` and `mode`, and a generated-equals-listed check. |
| M-4 | MAT-8's documentation scope misses design.md *Reuse*, *Capture* and the capture job contract | Fixed. They are assigned to MAT-8 with the reuse validation rules carried forward. The sheet schema is `/11`. |

## Verification strategy

- **Pure tests, no Blender:** glTF material-name reading, its rules and its
  input errors; library parsing and every validation rule; block mapping
  (identity pooling across duplicate names, ties, band boundaries, `plain`
  versus `mode`, repeated ramp entries including one entry at both ends of a
  ramp, the exact band formula at the range's ends and outside it, fallback,
  coverage, no-vote blocks); `BLEND` materials decoding to no-identity,
  including one sharing a name with an opaque material that the library or
  its default maps; joint ID and shade validation; independence from library
  key order; determinism.
- **The spike's cases** ([Capture](#capture-d-10-d-11-d-13)) become Blender
  tests in MAT-3: material edges, thin features, a `MASK` material in front of a
  second (captured opaque with no cutout, matching the colour, D-26),
  occlusion, and the smallest and largest supersample.
- **Blender tests** (`@pytest.mark.blender`, generated `.glb` fixtures): the
  ID buffer is exact and its table maps to the right glTF materials,
  including duplicate and missing names; repeat renders are byte-identical;
  the shade buffer is identical for materials differing in colour, texture,
  metallic and roughness.
- **The cross-subject promise:** two generated subjects with the same pose
  and lighting, sharing a material name but with different source colours and
  split across differently indexed glTF materials, give the same colours for
  that material from one library.
- **Old output preserved:** before MAT-3 changes capture, its author records
  the colour buffers of the generated fixtures at the base commit, with the
  same Blender; after the change they must be byte-identical, and a frame's
  colour must not depend on whether auxiliary passes ran before it (rendering
  the same frame alone and within a sequence). The comparison goes in the
  local-validation report. Whole-command tests then show the sheet pixels of
  all four looks unchanged without a library.
- **Whole-command tests:** a library without a palette and every library
  error exit 2 before any Blender invocation; unmapped materials warn by name;
  the fingerprint changes with the library; `--settings-from` reproduces the
  look without the files; D-24's combinations.
- **The owner's eye** on the acceptance render (V-12). No test claims a look
  is good.

## Delivery plan

*Approved by the owner on 2026-10-07 (D-14); revised for the outside review
the same day without changing the slices.*

### MAT-1. Carry several named capture buffers per frame through the pipeline

- **Outcome:** a frame can carry named buffers (`color` and others) from
  capture into stylize, loaded one frame at a time and released after
  reduction; existing passes read `color` and produce identical sheets. It
  defines the [Frames into stylize](#frames-into-stylize) interface that
  MAT-3 produces and MAT-5 consumes.
- **Scope:** the frame type, the command's loading of buffers, design
  §Pipeline amendment.
- **Phase:** 1 (foundation).
- **Depends on:** none.
- **Ordering:** can land first.
- **Relevant decisions:** D-4.
- **Acceptance signals:** existing tests pass unchanged; a test frame with an
  extra buffer reaches stylize intact.
- **Out of scope:** new buffers from capture.
- **Open questions:** None.

### MAT-2. Read material identities from the glTF

- **Outcome:** a pure function returns, for the selected scene, each
  primitive's material index, name and alpha mode, applying D-18's rules.
- **Scope:** `gltf.py`, design §Input contract amendment.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** independent.
- **Relevant decisions:** D-3, D-18.
- **Acceptance signals:** pure tests with named, unnamed, empty-named,
  duplicate-named and missing materials, and each input error.
- **Out of scope:** Blender.
- **Open questions:** None.

### MAT-3. Capture material-ID and shade buffers

- **Outcome:** every render writes an exact material-ID buffer and a shade
  buffer (D-11) beside an unchanged `color`, with an ID-to-glTF-material table
  in the result, validated by the launcher and decoded into the [Frames into
  stylize](#frames-into-stylize) interface.
- **Scope:** D-10 spike first; `blender_script.py`, result validation, design
  §Capture and §Capture job and result contract amendments.
- **Phase:** 2.
- **Depends on:** MAT-1, MAT-2.
- **Ordering:** critical path.
- **Relevant decisions:** D-4, D-10, D-11, D-13, D-22, D-25.
- **Acceptance signals:** the spike's recorded outcome, with the owner's
  decision if it took the failure route; the default shade range chosen from
  its measurements; shade provenance in the generator; Blender tests above;
  the before-and-after colour comparison; local-validation report.
- **Out of scope:** normals; any stylize change.
- **Open questions:** None.

### MAT-4. Read and validate a material library

- **Outcome:** `materials.read_library` parses and validates the JSON library
  against a palette, with typed errors naming file and material.
- **Scope:** new pure module, design §Stylize amendment.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** independent.
- **Relevant decisions:** D-6, D-7, D-8, D-15, D-17.
- **Acceptance signals:** pure tests for every validation error.
- **Out of scope:** generated ramps (MAT-8).
- **Open questions:** None.

### MAT-5. Map frames onto material ramps

- **Outcome:** a pure stylize step maps each block per [Mapping a
  block](#mapping-a-block-d-7-d-9-d-20), composed with both reductions and the
  palette, one frame at a time.
- **Scope:** `stylize.py`, `imageops.py`, design §Stylize amendment.
- **Phase:** 2.
- **Depends on:** MAT-1, MAT-2, MAT-4.
- **Ordering:** critical path; builds against MAT-1's interface in parallel
  with MAT-3. The mapper takes the shade range as a parameter, so it does not
  wait for the spike's measurements.
- **Relevant decisions:** D-6, D-7, D-9, D-11, D-15, D-17, D-18, D-20, D-22,
  D-23, D-25.
- **Acceptance signals:** pure tests on synthetic colour, identity and shade
  arrays.
- **Out of scope:** dithering, eased bands.
- **Open questions:** None.

### MAT-6. Choose, record and reuse a material library from the command

- **Outcome:** the command option, its errors and warnings, the recorded
  library and shade range in `settings.style` and fingerprint, reuse by
  `--settings-from` with D-24's rules.
- **Scope:** `cli.py`, `export.py`, design §CLI and §Export amendments.
- **Phase:** 3.
- **Depends on:** MAT-3, MAT-5.
- **Ordering:** critical path.
- **Relevant decisions:** D-3, D-6, D-8, D-9, D-17, D-19, D-24.
- **Acceptance signals:** whole-command tests above.
- **Out of scope:** saved style files; replaying a retained capture.
- **Open questions:** None.

### MAT-7. Render materials for the owner's visual review

- **Outcome:** the owner reviews sheets and previews of the acceptance inputs
  and approves or rejects the look.
- **Scope:** the exact reproducing commands and inputs by name and hash.
- **Phase:** 4.
- **Depends on:** MAT-6.
- **Ordering:** critical path.
- **Relevant decisions:** D-4, D-16, D-17, D-22, D-25.
- **Acceptance signals:** the owner signs off on the review library's ramps
  before rendering, then records a verdict on the sheets.
- **Delivery:** documentation only, with no pull request (the D-14
  exception): the acceptance record is published with `docs-push`.
- **Out of scope:** tuning beyond what the verdict asks; owner-made models.
- **Open questions:** None.

### MAT-8. Generate ramps from material properties

> **Ready** on 2026-10-14: the owner reviewed sample ramps and decided D-28 to D-35, which specify Q-24. It was deferred on 2026-10-07 until then. **Reopened** the same day by MAT-8 review 1: not ready until Q-30 is decided and the owner signs off the revision. Q-30 is resolved by D-36.

- **Outcome:** a library can give a ramp as properties instead of a list of
  palette indices. The tool generates the ramp by D-33's formula and snaps it
  to the palette. It records the properties and the result, and reuses the
  recorded result without regenerating it. The formula's values are settings
  with options, defaulting to setting B. A library can also give a default
  `shade` for its materials.
- **Scope:**
  - **The library reader:** the `moskophoros.materials/3` schema, with `/2`
    still loading (D-34). Generated ramp mappings, wherever a ramp may be
    given, with optional per-ramp formula values (D-34). The library-level
    `shade`, which gives `range` only, and its validation (D-35, D-36).
  - **Generation:** a pure function from base colour, band count and formula
    values to palette indices (D-28, D-33).
  - **Settings:** the `ramp` settings, `ramp.lightness_step`,
    `ramp.hue_shift_deg` and `ramp.chroma_fade`, in the shipped defaults
    (setting B). Their options `--ramp-step`, `--ramp-hue-shift` and
    `--ramp-fade`, and their validation (D-30, D-33).
  - **Resolution order:** a ramp's own formula values beat the globals. Shade
    ranges resolve from the material, then the library's `shade`, then the
    settings, then the shipped default (D-33, D-35, D-36). The warnings for
    explicit globals that lose (D-33, D-35).
  - **The capture job is unchanged:** capture values still come only from a
    material entry's own `shade` or the globals, and the job never carries
    the library `shade` (D-36; settings design D-36).
  - **Recording and reuse:** `settings.ramp`, the generated-ramp records and
    the library `shade` record (D-33, D-34, D-35), with the sheet schema
    bump. Reuse without regeneration. Regeneration when an explicit value
    changes a reused ramp's inputs (D-33).
  - **Documents:** the design.md amendments go in the same pull request,
    since tests read design.md (MAT-8 review 1, M-4). They cover:
    - §CLI and §Settings files;
    - §Stylize;
    - §Export, with the sheet schema `moskophoros.sheet/11`, the next free
      one;
    - §Scale and ground point, *Reuse*:
      - only `/11` loads;
      - the reused fields gain `settings.ramp`;
      - the inline library keys gain the library `shade` and generated-ramp
        records;
      - the original recorded library is still validated before any
        override, including when it is dropped or replaced, and generated
        records are validated structurally (`indices` are N valid palette
        indices) without regenerating;
      - the recorded `indices` change only when an explicit value changes
        that ramp's effective inputs (D-33);
    - §Capture and §Capture job and result contract: state that a
      library's `shade` (a range) never reaches capture, so the job stays
      the same whatever the default ramp and the ranges (D-36).
- **Phase:** 5.
- **Depends on:** MAT-7 (#70, done).
- **Ordering:** after the first release; required for epic completion.
- **Relevant decisions:** D-6, D-7, D-12, D-19, D-21, D-24, D-28 to D-36;
  settings design D-20, D-23, D-24, D-29, D-30, D-36, D-37.
- **Acceptance signals:**
  - **Pure tests for generation:**
    - lightness, hue and chroma per band;
    - the near-grey rule;
    - N = 1;
    - the lightness floor at 0;
    - gamut clipping;
    - snapping ties going to the lower index;
    - repeats kept.
    - the numerical reference of D-33 (M-2), including its counterexample on
      a generic two-entry palette.
  - **Reference vectors:** with the Vince 144 palette, setting B and setting C
    reproduce the indices recorded for the ten materials in
    `~/.local/share/moskophoros-acceptance/ramp-gen/samples.json`. The
    palette's colours and these indices are copied into the tests as literal
    data, with no file outside the repository read.
  - **Reader tests:**
    - `/2` libraries load unchanged;
    - `/3` features are refused in a `/2` library;
    - mapping and limit errors are usage errors (exit 2) before Blender;
    - `/1` is still refused.
  - **Resolution tests:**
    - the formula values and shade values resolve in D-33's and D-35's
      orders;
    - each warning fires;
    - the capture job and its `job_sha256` are unchanged by a library
      `shade` and by adding or removing a default ramp (D-36);
    - a library `shade` giving a capture value is refused.
  - **The reproduction test** (settings design D-16) covers a generated
    library: rerunning from a sheet reproduces it byte for byte without
    regenerating, and an explicit `--ramp-hue-shift` regenerates it.
  - **Without a library,** every existing look's PNG and previews are
    unchanged; the JSON changes only by the schema, `settings.ramp` and the
    fingerprint.
  - **Existing hand-listed libraries are preserved** (MAT-8 review 1, M-3):
    - **The fixture:** an unchanged `/2` library with only listed ramps,
      covering:
      - a material's own ramp, a named ramp and the default ramp;
      - an ordinary and a `BLEND` fallback;
      - repeated indices;
      - a per-material `shade`.
    - **Before and after the change,** under both `plain` and `mode`:
      - the capture values and the capture job are the same;
      - the PNG and previews are byte-identical;
      - so are the normal and depth maps, when enabled;
      - the JSON differs only by the schema, `settings.ramp` and the
        fingerprint.
    - Changing the global `ramp` settings changes neither its resolved ramps
      nor its images.
    - The same holds for a `/3` library with listed ramps and no top-level
      `shade`. A library that adds a top-level `shade` is outside this
      obligation, since it is meant to change the look.
  - **Generated equals listed:** a generated ramp renders exactly as a
    listed ramp of its resulting indices, under `plain` and `mode`, including
    repeated indices that `mode` pools.
  - **The owner's review** (V-12): the owner reviews sheets from generated
    ramps against hand-listed ones. The pull request gives the exact
    commands, under both setting B and setting C.
- **Out of scope:**
  - dithering;
  - eased (non-linear) bands;
  - taking the base colour from the glTF (D-29);
  - palette swaps that keep a library (D-24);
  - changing the shipped shade range (D-32).
- **Open questions:** None.

## Later arc: the lighting sheet

Not part of this epic; recorded so this arc rules nothing out. A second sheet,
aligned frame for frame with the colour sheet, lets the owner's engine light
sprites live (D-1, D-2). D-27 settles what it holds: a normal map, an
optional depth map, and a lit preview whose light is never baked into the
exported colour sheet. Open: the direction space (camera-relative,
consistent with V-7), how Blender produces normals and depth, whether
materials perturb them (rough surfaces adding noise), the preview light's
flag, and how the sheet's JSON describes the maps. Becomes its own design
when the owner takes it up.

## Source notes

The owner, 2026-10-07, on what materials are for:

> materials means that a steel object in the hands of one sprite will have the
> exact same color profile as a steel object in the hands of a different type
> of unit.

> each material should have properties, these properties should automatically
> get converted to the scaled color map … perhaps certain materials like cloth
> can have some dithering … or color ramps that are not linear

> mostly flat outline (i.e. no outline), bold color choices that fit in a
> ladder … things i want to avoid: … those old ps1-era 3d games … to have some
> sort of control to handle the 'flatness' of the sprite, would be ideal.

On ambient shading (resolving Q-25):

> my game engine is going to shade facemaps that we generate alongside, sky
> and ground will fit in to that, the only shading we want is to indicate
> creases, nooks and crannies, and curves, my engine can capture the
> brightness, but only in the sprite can we capture the proper hue shift from
> the color ramps.

On the lighting sheet:

> moskophoros … can not only create me my unit sprites in all 8 directions,
> but actually provide me physically correct rgb facemaps for every single
> frame … i can load a facemap sprite sheet alongside the regular one and shade
> the game live.
