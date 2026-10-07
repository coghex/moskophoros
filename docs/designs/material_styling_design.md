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

Design state: `ready for issue processing`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [x] EPIC. Draw each named material from its own ramp on a shared palette — [#63]
- [x] MAT-1. Carry several named capture buffers per frame through the pipeline — [#64]
- [x] MAT-2. Read material identities from the glTF — [#65]
- [ ] MAT-3. Capture material-ID and shade buffers
- [ ] MAT-4. Read and validate a material library
- [ ] MAT-5. Map frames onto material ramps
- [ ] MAT-6. Choose, record and reuse a material library from the command
- [ ] MAT-7. Render materials for the owner's visual review
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

**Cutouts and translucency.** Materials with glTF alpha mode `MASK` discard
pixels; the ID and shade passes must keep the same cutouts, so surfaces
behind a hole are identified as in the colour. `MASK` materials are eligible
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
normalised per frame or per subject. MAT-5's mapper takes the range as a
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

MAT-8 later lets an entry give **properties** that generate its ramp instead
(D-12, D-21).

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
   `(v − lo)·N // (hi − lo + 1)`, so `lo` is band 0 and `hi` band N−1. Under
   `plain`, take the alpha-weighted mean shade `W/A`, clamped, and its band
   `(W − lo·A)·N // ((hi − lo + 1)·A)`; output `palette[ramp[band]]`. Under
   `mode`, map each of the winner's pixels to `ramp[band]` and vote by palette
   entry, weighted by colour alpha (D-23). A tie goes to the entry with a band
   centre nearest the mean shade, over **every** occurrence of that entry in
   the ramp, then to the smaller palette index. Band `k`'s centre is
   `lo + (k + ½)·(hi − lo + 1)/N`, compared exactly by scaling both sides by
   `2·N·A`. Alpha is 255.
4. Otherwise (no-identity, including `BLEND`; `"ordinary"`; unmapped without
   a default), the block takes the existing look for the chosen reduction and
   palette (D-9).

All arithmetic is exact integer arithmetic, deterministic, and independent of
the library's key order.

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

### Failure behaviour

- Unreadable or malformed library, an index outside the palette, a library
  without a palette: usage errors (exit 2) before Blender starts, naming the
  file and material (D-6, D-8).
- A model material absent from the library, or a library entry the model never
  uses: not an error. The first is a warning naming the material and whether
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
not replace it.

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
overrides generated shades.

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
request.

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

## Open questions

Open: Q-24, deferred to MAT-8's start; and Q-11, which belongs to the later
lighting-sheet arc and blocks no slice here. Q-21, Q-22 and Q-23, raised by an
outside review on 2026-10-07, are resolved by D-22, D-23 and D-24; Q-25,
raised by D-22, by D-25.

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
(`BLEND`) materials out of scope. `MASK` cutouts are a capture requirement
([Capture](#capture-d-10-d-11-d-13)).

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

For MAT-8, beyond D-21: the lightness endpoints and where the base colour
sits in the ramp; how hue shifts interpolate across bands; how achromatic
(grey) base colours take a hue shift; the units and limits of saturation and
contrast; and how a shade equally near two palette entries snaps.
**Specified when MAT-8 starts**, with a short owner review of sample ramps;
MAT-8 is not ready until then. Affects MAT-8.

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
  tests in MAT-3: material edges, thin features, a `MASK` cutout over a
  second material, occlusion, and the smallest and largest supersample.
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
- **Out of scope:** tuning beyond what the verdict asks; owner-made models.
- **Open questions:** None.

### MAT-8. Generate ramps from material properties

- **Outcome:** a library entry can give properties instead of a hand-listed
  ramp; the tool builds the ramp and snaps it to the palette, records both,
  and reuses the recorded ramp without regenerating it.
- **Scope:** the library reader, generation, the recorded settings and their
  reuse in `cli.py`, design §Stylize and §Export amendments.
- **Phase:** 5.
- **Depends on:** MAT-7.
- **Ordering:** after the first release; required for epic completion. Needs
  Q-24 specified before it is ready.
- **Relevant decisions:** D-6, D-7, D-12, D-19, D-21.
- **Acceptance signals:** pure tests for generation, snapping and recording;
  the owner reviews generated ramps against hand-listed ones.
- **Out of scope:** dithering; eased (non-linear) bands.
- **Open questions:** Q-24.

## Later arc: the lighting sheet

Not part of this epic; recorded so this arc rules nothing out. A second sheet,
aligned frame for frame with the colour sheet, lets the owner's engine light
sprites live (D-1, D-2). Open: its encoding (Q-11), the direction space
(camera-relative, consistent with V-7), how Blender produces normals, whether
materials perturb it (rough surfaces adding noise), and how the sheet's JSON
describes it. Becomes its own design when the owner takes it up.

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
