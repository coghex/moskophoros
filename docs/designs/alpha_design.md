# Alpha design

Moskophoros's sprite sheets have alpha, but only as coverage: a pixel is
either a surface (alpha 255) or background (alpha 0). Transparency in the
model itself is lost. A glTF `MASK` material's cut-out texels render as
opaque texture colour (#75), and a translucent `BLEND` surface is drawn as if
it were solid. This arc makes the sheet carry the model's transparency, so
foliage, fences, hair cards, glass or ghosts come out as the model intends.
The colour sheet, its normal and depth maps and the lit preview all stay
aligned.

The owner asked for it on 2026-10-15: "outlines are something i want for
sure, but actually outside my use case at the moment, much more critical is
transparency. help me implement alpha". It lifts #75's deferral for design.
It benefits the owner producing game art, and any project using the tool
(V-1).

Design state: `ready for issue processing`

Reset to `exploring` on 2026-10-17 for Codex review 1 (5 blocking, 3 should
fix), then marked ready again the same day under the owner's delegation
(request moskophoros-20261017-1): every finding is fixed and no owner
decision changed; see *Review 1*. Reset again the same day for Codex
rereview 2 (1 blocking, 3 should fix, 1 minor), and marked ready again under
the same delegation once every finding was fixed with no owner decision
changed; see *Review 2*.

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

Slices as delegated to the designer by the owner (D-16).

- [x] EPIC. Carry the model's transparency into the sprite sheet — [#113]
- [x] ALPHA-1. Capture colour and buffers in one flat Cycles render — [#114]
- [x] ALPHA-2. Cut out `MASK` materials — [#115]
- [x] ALPHA-3. Carry 8-bit alpha, the `edges` setting and preview blending — [#116]
- [x] ALPHA-4. Capture and composite translucent layers — [#117]
- [x] ALPHA-5. Give translucent materials identities and ramps — [#118]
- [x] ALPHA-6. Blend translucent pixels in the previews — [no-issue]: merged into ALPHA-3 (Review 1, A-4)
- [x] ALPHA-7. Owner review of alpha sheets — [#119]

## Epic contract

- **Goal:** a model whose glTF materials are transparent renders a sheet
  whose pixels carry that transparency as the design settles it. Its normal
  and depth maps, material identity and shade agree with the colour pixel for
  pixel, and the owner judges the look (V-12).
- **Done when:**
  - `MASK` cutouts and `BLEND` translucency reach the sheet as 8-bit alpha
    (D-1 to D-3), with hard edges by default and soft ones on request (D-4,
    D-9).
  - Translucent layers composite over ramped surfaces (D-6, D-12).
  - Every map agrees with the colour pixel for pixel, its alpha included
    (D-11), and the previews show translucency (D-13).
  - Automated checks on generated fixtures prove alignment and determinism.
    Output of opaque models changes by design (D-5, D-8), and tests pinning
    exact output are updated deliberately.
  - The owner reviews sheets and previews of a model of their own and
    approves them, in a slice of its own (ALPHA-7).
- **Users and operators:** the owner producing game art; agents maintaining
  the tool.
- **Arc label:** None proposed.

## Current state and evidence

**Fixed by earlier owner decisions (not reopened here):**

- The flat ambient colour sheet, the normal map, the optional depth map and
  the lit preview are accepted (lighting sheet design; owner LIT-6 review,
  2026-10-14). Alpha must keep them aligned: whatever is transparent in the
  colour sheet is transparent in every map.
- Material styling is accepted, generated ramps included (MAT-8, D-28 to
  D-36). Only its D-26 is revisited here.
- V-4: capture keeps full information and decides nothing about the look.
  Any hardening of transparency happens after capture, so a style change
  never needs a re-render.
- Output is deterministic; the tool belongs to no game (V-1); the owner
  judges the look (V-12).

**Verified current behaviour (master `bd52aba`):**

- **Input:** the glTF reader reports each primitive's alpha mode as given,
  defaulting to `OPAQUE` (design §Input contract).
- **Colour capture:** Workbench, "texture color, falling back to material
  color", film transparent, straight alpha (design §Capture, *Render
  settings*). Its alpha is antialiased coverage only.
  - Workbench ignores the alpha the glTF importer builds for a `MASK`
    material, so cut-out texels render opaque. In the material styling
    spike's *edges* fixture, the holes are `(54, 54, 54, 255)`.
  - Setting `blend_method` (`CLIP`, `BLEND`) or `surface_render_method`
    (`BLENDED`) changes nothing (material styling Q-26; #75).
- **Auxiliary capture:** one Cycles render, 1 sample per pixel, transparent
  bounces 8. It gives the material ID, shade, normal and depth from one
  shared camera sample per pixel. Every material's shader is replaced by an
  emission, so no material property, alpha included, reaches it.
  - **D-26** (owner, 2026-10-08): `MASK` materials are captured opaque, with
    no cutouts, so the ID and shade match the colour.
  - The spike noted that its Cycles method can honour the importer's alpha
    (#75).
- **Identity:** a pixel showing a `BLEND` material, or any alpha mode other
  than `OPAQUE` and `MASK`, decodes to no identity and takes the ordinary
  look (design §Pipeline; material styling D-23).
- **Stylize:** a pixel's coverage is the mean alpha of its supersampled
  block, and a pixel below 0.5 is `(0, 0, 0, 0)`. Every kept pixel has alpha
  255, under `plain` (the alpha-weighted mean) and `mode` (an alpha-weighted
  vote) alike (design §Stylize).
- **Maps:** a normal or depth map pixel exists exactly where the reduced
  colour's alpha is 255 (design §Stylize, *Normal and depth maps*).
- **Palettes** have no alpha; a palette maps only the RGB of a kept pixel.
- **Previews** are GIFs, whose transparency is one bit.
- **The owner's models at hand** use no transparency: RobotExpressive, the
  ramp review's `suzannes.glb` and `lightfix.glb` are all `OPAQUE`, with no
  `baseColorFactor` alpha below 1.
- **Tracker:** #75 (open, `enhancement`, `blocked`) records `MASK` cutouts
  as deferred work. No other open epic overlaps this arc.

## Design

### Capture spike 1 (Q-4)

Run on 2026-10-15 with Blender 5.2.2, on generated fixtures. The report,
scripts, fixtures, renders and every command are in
`~/.local/share/moskophoros-acceptance/alpha-design/spike-1/` (`REPORT.md`).
`renders/contact_sheet.png` shows the main results side by side.

- **What the glTF importer builds:**
  - `MASK` alpha is node math, `1 − (texture alpha × factor < cutoff)`:
    exactly 0 or 1, with no hashing or dithering.
  - `BLEND` alpha is the factor, the texture alpha, their product, or the
    vertex colour's alpha.
  - `MASK` and `OPAQUE` materials differ only in that node chain.
- **Workbench cannot do this.**
  - It shows a `BLEND` material's factor alpha, but never the glTF cutoff and
    never partial texture alpha.
  - Its blending is not the linear "over" composite.
  - Today it also shows the hidden colour of alpha-0 texels: red holes come
    out as (177, 55, 55, 255).
- **One Cycles render does it exactly and deterministically.** It uses the
  auxiliary render's settings (1 sample per pixel, Box 0.01 px, seed 0, film
  transparent), with each material's surface replaced by
  `Mix(Transparent, Emission(the importer's colour chain))`, its factor taken
  from the importer's alpha chain.
  - Alpha equals glTF's at every probe: holes 0, the cutoff at 127 cut and
    128 kept, translucency 0.4, and the gradient texel for texel.
  - A 0.4 veil over the body is exactly `0.4·veil + 0.6·body` in linear.
  - Pixels are bit-identical across runs and processes.
  - Cycles writes render-time text into its own PNG and EXR files, so the
    colour is written from pixels, as the auxiliary buffers already are.
- **The other buffers need a gate.**
  - Cycles adds shader output passes (AOVs) over every surface a ray
    crosses, holes included. It stops at the first surface whose alpha
    reaches `pass_alpha_threshold`.
  - Multiplying every AOV by a gate `alpha ≥ T`, with the threshold at the
    same T, makes the material ID, shade, normal and depth all describe one
    surface. T near 0 gives the front-most surface that is not a hole; T 0.5
    the first with alpha at least 0.5; T 1 the first opaque one. All three
    were exact.
  - Today's ID and shade, carried in the emission colour, would be blended
    by partial alpha, so they move to AOVs, as floats.
- **The surface flag:**
  - "This supersample shows a surface" is exactly "alpha > 0", read from the
    float result.
  - More stacked transparent layers than `transparent_max_bounces` give
    false opaque black pixels. Capture sets a generous limit (64 cost
    nothing measurable) and fails loudly when alpha > 0 but no gated surface
    was written. *Superseded by spike 2:* that check misses a stack
    exhausted behind a visible front layer, and the minimum must be pinned
    too (Review 1, A-1, A-3).
- **Cost:** one render replaces today's two, at about the same time per
  frame on an ordinary model (1024²: 0.54–0.63 s, against 0.56–0.63 s).
  - Ambient occlusion runs again on every layer crossed, so 10 stacked
    cut-out layers cost 7× more.
  - Gating the occlusion distance by the same gate removes that extra cost,
    with identical output.
- **Two findings need owner decisions:**
  - **Studio light:** the Cycles colour is the flat, unlit material colour,
    not Workbench's studio-lit colour. This conflicts with lighting design
    D-23 (Q-11).
  - **Occlusion:** cut-out holes and translucent surfaces occlude like solid
    ones in the shade's ambient occlusion (Q-12).

### Capture spike 2 (Review 1: A-1, A-2, A-3, A-8)

Run on 2026-10-17 with Blender 5.2.2, on generated fixtures, to prove the
remedies Codex review 1 asked for. The report, scripts, fixtures, results
and every command are in
`~/.local/share/moskophoros-acceptance/alpha-design/spike-2/` (`REPORT.md`,
`commands.log`). The Cycles behaviour it relies on was read from Blender's
bundled kernel source, then confirmed by experiment.

- **Exact composites (A-1).** Pinning `min_transparent_bounces` and
  `transparent_max_bounces` both to 64 gives exact front-over-back
  composites through mixed stacks: a 0.4 veil over 10 holes over blue; a
  hole, a 0.5 pane, 3 holes, a 0.25 pane, 5 holes, blue; two 0.5 panes over
  the background (alpha 0.75); 30 alternating translucent and hole layers.
  The largest error is 4.1e-8. With the minimum left at 0 (the control),
  Russian roulette makes blue 0.999 instead of 0.6. Separate processes are
  bit-identical. Cost is unchanged: 0.55 s at 1024² on the ordinary model,
  against 0.54–0.63 s in spike 1.
- **An exact surface gate (A-2).** The gate is computed in Math nodes in the
  order Cycles computes the Mix shader's transparency:
  - `sat = clamp(α)`, `t = 1 − sat`, `v = 1 − t`, and
    `g = 1 − (v < T)`, with `pass_alpha_threshold = T = 2^-30`;
  - every AOV and the occlusion distance are multiplied by `g`.
  - Cycles stops its passes exactly where `v > 0`, which is exactly where
    `g = 1`, so one surface contributes exactly once.
  - Over 9 fixtures of 4096 pixels: factor alpha from 0 to 1, texture ×
    factor, `LINEAR`-filtered sweeps, vertex alpha, `MASK` cutoffs. There
    were 0 anomalies. The review's counterexample (a 5e-7 front) now gives
    the front's ID, hit 1, its depth and a unit normal.
- **Detecting an exhausted stack (A-3).** *Superseded by spike 3 (Review 2,
  B-1):* the in-render marker below is attenuated by the layers in front of
  it and can accept a damaged frame; capture uses spike 3's count render
  instead. Spike 2's finding, as recorded: with both limits at `L`, the
  colour is wrong exactly when a camera path crosses `L + 1` or more
  surfaces that still have a transparent closure. (Spike 3 corrects this:
  wrong colour implies truncation, not the reverse.) This was proven both
  ending at an opaque surface and at the background, at `L = 64` (90 of 90
  cases) and `L = 8` (42 of 42).
  - **In the one render:** every shading point at transparent depth ≥ `L`
    that still has a transparent closure (Cycles' own test, transparent
    weight ≥ 1e-5) adds a white emission of strength −1e30. A truncated
    path then has a colour channel far below 0. **The frame fails when any
    Combined RGB channel is below −1.** The marker changed no correct
    render (42 bit-identical EXRs) and costs nothing measurable. It needs
    Cycles' sample clamping off, as the factory default has it.
  - A separate count render is also exact (`error iff count ≥ L + 1`, about
    5 % of the main render's time), but is not needed.

### Capture spike 3 (Review 2: B-1, B-4)

Run on 2026-10-17 with Blender 5.2.2, on generated fixtures and the review's
own. The report, scripts, fixtures, results and every command are in
`~/.local/share/moskophoros-acceptance/alpha-design/spike-3/` (`REPORT.md`,
`commands.log`).

- **The count render.** After the main render, every material switches to a
  count shader: a shading point that still has a transparent closure
  (Cycles' own test, as in spike 2) becomes `Add(Transparent white,
  Emission white 1)`, any other `Emission` of strength 0. No occlusion, no
  AOVs (their outputs disconnected, or Cycles evaluates the occlusion
  anyway: 1.18 s instead of 0.024 s). Same camera, sampling and bounce
  limits, both 64. Its red channel counts exactly the transparent-closure
  surfaces each path crosses, capped at 65, independent of colour
  throughput.
- **The rule:** a frame is truncated, and refused, when any pixel of the
  count render has red ≥ 65.
  - It agreed with structural truncation in 137 of 137 cases: the review's
    white alpha-0.67 stacks of 64 and 65; white stacks at alpha 0.05 to
    0.95; spike 2's 90 mixed stacks; a visible translucent front over 63,
    64 and 65 holes; holes and unlit stacks; all ending at an opaque surface
    and at the background. No valid stack of 64 was refused. The
    near-opaque counterexample counts 0.
  - It refuses some truncated frames whose colour is still right to 1e-6:
    13 of 137, where the throughput Cycles dropped was between 6.3e-7 and
    5e-84. It never accepts a wrong frame. Exit 5 therefore means "a camera
    path crossed more than 64 surfaces that still let light through", not
    "the colour is wrong".
  - Switching back restores the main render bit for bit, and keeping the
    count nodes in each material changes the main render neither in time
    nor in bytes. The fastest switch is one shared node-group value
    (0.8 ms per round trip).
  - Reading a render from memory returns nothing in background mode, so the
    count is read back from its EXR.
- **Cost of the complete proposed capture** (main render, count render,
  switching, reading and checking, writing every buffer), against today's
  production capture (Workbench colour plus the auxiliary render), per
  frame, median of frames 2–5, median of three interleaved rounds:
  1.19–1.22× on the ordinary model at 1024², 1.10–1.21× on stacked
  cutouts at 384². The count adds about 0.10 s per frame at 1024², half of
  it saving the count's EXR. The machine was shared and loaded (load
  average 14–16); the spike's own buffer writer is slower than
  production's.
- **Not tested:** limits other than 64 and 8, real assets deeper than 64
  layers, GPU, animation, a count-only view layer.
- **Unlit and material-less inputs (A-8).** The importer builds two
  material shapes, and one extraction rule covers both:
  - a Principled BSDF: colour from `Base Color`, alpha from `Alpha`;
  - the `KHR_materials_unlit` core, `Mix(Light Path "Is Camera Ray",
    Transparent, Emission)`, alone (alpha 1) or wrapped in
    `Mix(alpha chain, Transparent, core)`: colour from the Emission's
    colour, alpha from the wrapper's factor.
  - Any other shape is refused, naming the material.
  - Unlit opaque, `MASK` and `BLEND` render exactly (≤ 1.2e-7).
  - A primitive without a material keeps code 65535, and its stand-in
    becomes glTF's default material, white, opaque. It renders exactly.
    Today Workbench shows it lit grey.
- **Precision limits** of Blender's own representation, not cutoffs this
  design chooses:
  - A surface is a hole to Cycles when `α ≤ 2^-25` (about 3e-8): `1 − α`
    rounds to 1 in 32-bit floats. The composite gives it no coverage and
    the gate does not select it, so they agree. This is the alpha "as
    Blender imports it" (D-3).
  - A layer with `α` above about `1 − 1e-5` is opaque to Cycles: it drops a
    transparent closure weaker than 1e-5. The error is below 1e-5, invisible
    at 8 bits and 16 bits alike.
  - Blender's glTF importer stores vertex colours (`COLOR_0`) as 8-bit, so
    vertex alpha comes in steps of 1/255.
  - A pixel of alpha 0 can carry a tiny premultiplied colour (`α · colour`
    for a hole-floor surface). Capture treats alpha 0 as empty and writes
    `(0, 0, 0, 0)`.
- **Not tested:** skinned or animated models, the owner's models,
  perspective cameras, GPU devices, texture transforms, other
  `KHR_materials_*` extensions, importer material copies.

### The pipeline with alpha (proposal, assembled from D-1 to D-16)

This puts the decisions together. Where it goes beyond them it is a proposal,
and the arithmetic is pinned below and by each slice's tests, as the
lighting and MAT-8 arcs did.

**Capture.** One Cycles render per frame replaces Workbench's colour and the
auxiliary render.

- **Settings:** 1 sample per pixel, Box filter 0.01 px, seed 0, film
  transparent, every light bounce 0, `min_transparent_bounces` and
  `transparent_max_bounces` both 64, `pass_alpha_threshold` 2^-30, sample
  clamping off. These are recorded in the provenance (transport table).
- **Surfaces:** each material's surface becomes `Mix(Transparent,
  Emission(colour))`, with its colour and alpha taken from the importer's
  chains (D-3) by the extraction rule of spike 2 (Principled or unlit;
  any other shape is a backend error, exit 5, naming the material). It is
  flat and unlit (D-8), with `MASK` cut at `alphaCutoff` and `BLEND`
  partial. A primitive without a material takes the white, opaque stand-in,
  code 65535.
- **Surface selection:** spike 2's gate. A non-hole is a surface Cycles
  renders with any opacity. A selected surface writes each gated AOV exactly
  once; a hit value other than 0 or 1 is a backend error (exit 5).
- **Two layers** per supersample:
  - **the back layer,** the first opaque surface: its colour, identity,
    shade, normal and depth, or nothing;
  - **the front layer,** the translucent layers in front of it combined
    (D-12): its colour and alpha, and the front-most translucent surface's
    identity and shade, or nothing.
  - The maps take the front-most surface's normal and depth (D-11). A
    cut-out hole is no surface at all.
  - How the front layer's own colour and alpha are separated from the back
    layer is the one capture step not yet proven. Gated AOVs for the
    front-most and the first opaque surface are exact (spike 2). ALPHA-4
    settles the separation by a feasibility spike first; a further render
    is acceptable. The spike must meet the **correctness gate** (the front
    and back buffers of the transport table, matching the numerical
    reference's pinned cases and spike 2's mixed stacks) and the **cost
    gate** below. If either fails, implementation stops after the spike
    and reports to the owner, who decides; a failed gate never authorises
    an approximation or dropping a required pass.
  - **Cost gate (Review 2, B-4).** The complete capture per frame (every
    render, the count render, shader switches, reading and checking,
    writing every buffer; Blender start-up, import and one-off node
    building excluded) must be at most 2× the baseline.
    - **Baseline:** the production capture at `0a69fba` (Workbench colour
      plus the auxiliary render), as spike 3's `q6_timing3.py today`
      reproduces it.
    - **Fixture and settings:** spike 1's `fixtures/alpha.glb` (sha256
      `c0b25307e9f790824cbda35891282e83dec5a6c4183788dde51454c3963213a1`)
      at a 1024² supersampled render, 5 frames of one pose, the capture
      settings of this design.
    - **Aggregation:** the median of frames 2–5, then the median of three
      rounds that interleave the baseline and the candidate in the same
      session on the same machine, with the load average reported.
    - Spike 3 measured the capture without front separation at 1.19–1.22×,
      which leaves the separation about 0.8× of the baseline.
- **Material ID and shade** move to float AOVs, gated. Every alpha mode has
  an identity, so a `BLEND` material can take a ramp (D-15).
- **Occlusion** stays as today (D-7), with its distance gated, which keeps
  stacked cutouts cheap.
- **An exhausted stack fails loudly** by spike 3's count render, after the
  main render of each frame: a frame where any pixel's count is 65 or more
  is a backend error (exit 5) naming the input, clip, direction, frame and
  the limit 64, and nothing is published. It means a camera path crossed
  more than 64 surfaces that still let light through. It covers stacks
  behind a visible front layer and stacks ending at the background alike,
  whatever their alphas, and is conservative: it can refuse a frame whose
  lost light is below 8-bit precision, never accept a damaged one. The
  main render carries no marker.
- **Written from pixels** by the production PNG writer, as the auxiliary
  buffers are, so no render-time text reaches the output.

**Stylize** decides coverage once per output pixel, reduces each layer
with its own weights, composites the front over the back in linear colour,
then snaps to the palette (D-4, D-6, D-9, D-12, D-14). The numerical
reference below pins it.

**Previews** blend over their grey (D-13), in the same slice that first
produces partial alpha (ALPHA-3).

**Settings and formats.**

- The `edges` setting and `--edges` (D-9): a top-level setting in settings
  files, recorded in the sheet as `settings.style.edges` beside `reduce`,
  inside the fingerprint, required in the new schema, with the settings
  layers' strict validation (an unknown value is a usage error, exit 2).
- Only the current sheet schema loads (settings design D-24): sheets of the
  previous schema are refused by `--settings-from`, as every bump does.
  Nothing defaults a missing `edges`.
- The capture job does not change with `edges`, nor with the style values
  settings design D-36 leaves out of it; it still carries each material's
  own capture overrides, as D-36 says. The job's hash is the same under
  `hard` and `soft`.
- Which slice bumps which schema is in the transport table below.

#### Capture transport and provenance (Review 1, A-7)

What addressed frames receive. Presence always comes from Blender's float
data (the gated hits), written as each buffer's alpha. It is never
recovered from a quantized colour or alpha, so a surface of tiny alpha still
counts as a surface in stylize.

| Buffer | Slice | File | Content | Absent |
|---|---|---|---|---|
| `color` | ALPHA-1 | 8-bit RGBA PNG | the back layer's flat colour, straight sRGB through Blender's `Standard` transform, dither 0, written from pixels by the production writer | `(0, 0, 0, 0)` |
| `matid` | ALPHA-1 | 8-bit RGBA PNG, as today | the back layer's material code from a float AOV: R high byte, G low byte, B 0, alpha 255 | `(0, 0, 0, 0)` |
| `shade` | ALPHA-1 | 8-bit RGBA PNG, as today | the back layer's linear shade from a float AOV, encoded to the byte the `Standard` transform gives (0.25 → 137), `R = G = B` | `(0, 0, 0, 0)` |
| `normal`, `depth` | ALPHA-1; front-most from ALPHA-4 | 16-bit RGBA PNG, as today | the front-most surface's (D-11); the back's until ALPHA-4 adds a front | `(0, 0, 0, 0)` |
| `front_color` | ALPHA-4 | 8-bit RGBA PNG | the combined front layer's straight colour (D-12), encoded as `color` | `(0, 0, 0, 0)` |
| `front_alpha` | ALPHA-4 | 16-bit RGBA PNG, the form of `normal` | R = `q = floor(65535 · f + ½)` of the front layer's alpha `f`, G = B = 0, alpha 65535 | `(0, 0, 0, 0)` |
| `front_matid`, `front_shade` | ALPHA-4 (used from ALPHA-5) | as `matid`, `shade` | the front-most translucent surface's code and shade | `(0, 0, 0, 0)` |

- **Codes** keep today's mapping: material index `i` is code `i + 1`, a
  primitive without a material 65535, background 0, at most 65534
  materials. A float AOV that is not exactly an integer code in range is a
  backend error (exit 5); every code is exact in a 32-bit float.
- **Decoded arrays** (the command decodes, stylize never does): per layer an
  `int32` identity array and a `uint8` shade array as today; `front_alpha`
  as `uint16`; presence as `bool` arrays from each buffer's alpha.
- **Validation** (exit 5, as today's buffer checks): a layer's colour, ID
  and shade present on exactly the same pixels; `front_alpha` present
  exactly where `front_color` is; `normal` and `depth` present exactly where
  a back or front layer is; missing, misplaced or wrongly formatted files,
  as today. A front alpha may round to 65535 (a deep combined stack); the
  back then gets weight 0.
- **Provenance.** ALPHA-1 removes Workbench, so `backend.studio_light` and
  `generator.studio_light` go, `renderer` becomes `"cycles"`, and a `color`
  record beside `shade` names the technique and its fixed parameters
  (`technique`, `samples_per_pixel`, `seed`, `pixel_filter`,
  `filter_width_px`, both transparent bounce limits and
  `pass_alpha_threshold`).
- **Material-less parts** change from Workbench's lit grey to the stand-in's
  flat white (spike 2), glTF's default material. That is part of D-5's
  accepted change.
- **Schemas.** ALPHA-1 bumps the capture result to `/2` and the sheet to its
  next number. ALPHA-3 bumps the sheet again for `edges`. ALPHA-4 bumps the
  capture result to `/3` for the front buffers. Under settings design D-24,
  each sheet bump stops the previous schema loading.

#### Stylize: numerical reference (Review 1, A-6)

This replaces "each layer is reduced by today's rules". Today's reducers
and ramp mapper each apply the 0.5 coverage cut themselves; here coverage is
decided once, for the composite, and only their colour, vote and band rules
are reused, with the layer weights below in place of colour alpha.

**Per supersample `i`** of an output pixel's `s×s` block (`n = s²`), as
decoded from the capture buffers (transport table above):

- `b_i` is 1 where a back (first opaque) surface exists, else 0; its colour
  `B_i` is 8-bit sRGB.
- `p_i` is 1 where a front (combined translucent) layer exists, else 0; its
  alpha is the 16-bit integer `q_i` (`f_i = q_i / 65535`, 0 when `p_i` is
  0), its straight colour `F_i` 8-bit sRGB.
- The sample is a **surface** when `b_i` or `p_i` is 1. A front layer whose
  `q_i` is 0 is still a surface, with alpha 0: presence never comes from
  the quantized alpha.
- Integer weights in units of `1/65535`: the front's `u_i = q_i`, the back's
  transmitted weight `t_i = b_i · (65535 − q_i)`, and the composite alpha
  `a_i = u_i + t_i`. The per-sample composite is exactly D-6's
  front-over-back.

**1. Coverage and alpha,** once per pixel, in exact integers. Let `m` be the
number of surface samples and `S = Σ a_i`.

- `hard`: the pixel exists when `2m ≥ n`; `D = 65535 · m`.
- `soft`: the pixel exists when `S > 0`; `D = 65535 · n`.
- The alpha byte is `α = (510 · S + D) // (2 · D)`, that is
  `floor(255 · S / D + ½)`. A pixel that does not exist, or whose `α` is 0,
  is `(0, 0, 0, 0)`.
- An opaque model has `a_i = 65535` on every surface sample, so under
  `hard` every kept pixel is 255, as today.

**2. Each layer's colour,** with weights `u_i` (front) or `t_i` (back) in
place of colour alpha. `W_f = Σ u_i`, `W_b = Σ t_i`. A layer with weight 0
is absent from the pixel. Samples where a layer is absent cast no vote and
add nothing to its sums.

- Ordinary look, `plain`: the weighted mean of the layer's 8-bit sRGB
  values, rounded half up. With a palette, that mean then maps to the
  palette, as `plain` does today (reduce, then map), before compositing
  (D-14).
- Ordinary look, `mode`: the weighted vote, with today's tie rules against
  the weighted mean.
- With a palette, `mode` maps the layer's samples before voting, as today.
- Ramp: the identity vote with the layer's weights, then the band from the
  winner's weighted shade, with today's integer rules (design §Stylize,
  *Mapping a block*), giving a palette colour.

**3. Composite** in linear colour, `float64`, through the fixed
256-entry sRGB-to-linear table palette mapping already uses:

- `C = (W_f · lin(F̄) + W_b · lin(B̄)) / (W_f + W_b)`, encoded to 8-bit
  sRGB with the standard sRGB transfer function, rounded half up.
- When only one layer has weight, the colour is that layer's colour
  unchanged: no conversion round trip.
- The weights carry each layer's share of the per-sample composite, so a
  block where the front and back cover different samples weights each by
  where it is, not by its mean alpha alone.

**4. Palette** (D-14): with a palette, the composite's 8-bit RGB maps to the
nearest palette colour by `imageops.map_palette` (OKLab, earlier entry on a
tie). A one-layer pixel already holds a palette colour and maps to itself
(a palette has no duplicates). Alpha is `α` from step 1, never snapped.

**5. Maps** (D-11): a sample's map surface is the front layer's where
`p_i` is 1, otherwise the back's. Normal and depth reduce over those
samples by the lighting design's numerical reference, unchanged. A map
pixel exists exactly where `α > 0`; the normal map's alpha is `α`, and the
depth map is non-zero there.

**Pinned cases** (each slice's tests pin these exactly, `hard` unless
said; colours given are what the composite must use):

| Block (2×2 unless said) | Expected |
|---|---|
| empty | `(0, 0, 0, 0)`, no map pixel |
| opaque, every sample | today's colour, alpha 255 |
| front only, `f = 0.4`, every sample | alpha 102, the front's colour |
| front only, `f = 0.4`, two samples | `hard` 102, `soft` 51 |
| two samples front only `f = 0.5`, two back only | alpha 191 (0.75), colour `(1 · red + 2 · blue) / 3` in linear, under either rule; not 0.625 |
| front `f = 0.5` over back on the same two samples, two empty | `hard` 255, `soft` 128; colour the composite of the two |
| `f` of `[0.001, 0.001]` front only, two back only | four surfaces, alpha 128 (0.5005); not 255 |
| one surface sample of four | `hard` transparent; `soft` its alpha ÷ 4 |
| ramped front over ramped back (ALPHA-5) | each layer its own ramp colour, composited, then snapped |
| `plain`, palette black and white; front `(0, 0, 0)` with weight 32768, back `(100, 100, 100)` with transmitted weight 32767 | the back maps to white first; the composite is 188; the final snap gives white `(255, 255, 255)`, not black |
| `mode`, two front colours tied | today's tie rule against the weighted mean |

## Decisions

### D-1. Both cutouts and translucency are in scope

Decided 2026-10-15 by the owner in this design's pane (Q-1): "yes both i
guess. we should be able to render sprites with alpha where the cutoff is, i
dont want to see any background in my final sprites, and also if we have a
transparent material, such as a translucent cloth, we should be able to
render the effects that blender puts on it properly, as in see through it,
perhaps with a nonbinary alpha value in the output sprite."

- **Cutouts (`MASK`):** a cut-out texel is transparent in the sprite. No
  background colour shows through it, and the surface behind it shows if
  there is one.
- **Translucency (`BLEND`):** a translucent surface, such as cloth, is seen
  through as Blender renders it, with partial alpha in the sprite.
- **Test model:** the owner offered to build a test model first; see
  [Test inputs](#test-inputs).

### D-2. One 8-bit alpha channel; a cutout is alpha 0

Decided 2026-10-15 by the owner (Q-2, option C): "full 8 bit alpha, cutouts
should just be an alpha of 0, right? i dont really see why you are seperating
the two into two different contexts, they are all just cases of 0-1 alpha
space."

- The sheet's alpha is full 8-bit, 0 to 255, not quantised to levels.
- Cutouts and translucency are not separate outputs. Both are values in one
  0 to 1 alpha: a cut-out texel is 0, an opaque surface 1, and a translucent
  surface in between.
- `MASK` and `BLEND` differ only in how Blender computes a surface's alpha.

How partial alpha meets the outline rule is [Q-9](#q-9-outlines-hard-pixel-edges-or-soft).

### D-3. Alpha comes from the material, as Blender imports it

Decided 2026-10-15 by the owner (Q-3): "yes, it comes from blender, and the
material definitions."

- A surface's alpha is what Blender's glTF importer builds from the material:
  the base colour texture's alpha times `baseColorFactor`'s alpha, with the
  material's `alphaMode` and `alphaCutoff` (0.5 by default).
- The tool adds no transparency rule of its own.

### D-4. Hard edges by default; soft edges as an option

Decided 2026-10-15 by the owner (Q-9): "ideally, this would be an option,
defaulting to hard edges, but allowing the user to select soft edges if they
want to render the transparency that naturally arises from whatever scaling
algorithm we use."

- **Hard (the default):** Q-9's option A.
  - A pixel exists when at least half its block shows a surface, as today.
  - Its alpha is the mean alpha of the surfaces it shows. Outlines and cutout
    edges stay crisp, and only translucent materials give partial alpha.
- **Soft (chosen by the user):** Q-9's option B. A pixel's alpha is its
  block's mean alpha, so outlines and cutout edges keep the partial
  transparency that reducing the supersampled block produces.
- It is a setting with an option; its name and form are
  [Q-7](#q-7-settings).

### D-5. Existing sheets need not be preserved

Decided 2026-10-15 by the owner (Q-6): "i dont need the old renders anymore,
i dont want any opaque renders, they are just artifacts of development, so
feel free to overwrite them".

- "Byte-identical" meant that, after this arc, rendering an opaque model
  with the same command gives exactly the same files as before. That is
  usually a regression check: a test proves nothing changed.
- The owner does not need that. The arc may change the output of every
  model, opaque ones included, for example by using one capture path for all
  models. Each changed output is then judged in the owner's review (V-12),
  not compared to the old one.
- Existing tests that pin today's exact output are updated deliberately by
  the slice that changes it, and each such change is named in its pull
  request.
- Alignment stays a hard rule: the colour, material ID, shade and every map
  agree pixel for pixel.

### D-6. Two layers, with blending required

Decided by the owner (Q-10, option B). Relayed on 2026-10-17 by the owner's assistant laz to the moskophoros manager, which recorded it (owner message Sentinel_89d25b4bec048191ad74761c24fd93fc, delivery key owner-alpha-q10-q12-20261017-Sentinel_89d25, cmux message 3f7199ab-16e1-4cc4-8af6-73bdf50451c5). The owner asked that the decisions be passed to the manager as an attributed message.

- **Two layers, not one.** Translucency is composited, never dropped: the
  owner requires blending, and it is not an optional setting.
- **What it covers:** both the colour and the resulting alpha, for
  - a translucent surface over an opaque one;
  - two translucent layers, one in front of the other, such as two panes of
    glass.

  The two-layer description in Q-10 B (a translucent front layer over the
  ramped opaque surface) must be extended to cover the second case.
- **Combining alphas.** The owner asked whether combining the layers' alphas
  is correct. The assistant's technical clarification, not a further owner
  decision, is ordinary front-over-back compositing in linear colour:
  - `a_out = a_front + a_back·(1 − a_front)`;
  - premultiplied colour `c_out = c_front + c_back·(1 − a_front)`, each `c`
    already multiplied by its alpha; straight colour is `c_out / a_out` when
    `a_out` is not 0.
  - Two panes of alpha 0.5 give 0.75, and anything over an opaque surface
    gives alpha 1.
- **Not requested:** physically accurate refraction.
- **Still open:** which surface the normal and depth maps describe under
  translucency (Q-5), and how a stack of more than one translucent layer is
  represented and styled. When two translucent layers each have a material
  ramp, Q-10 B's "combined into one front layer" would have to say whose
  identity and ramp the combined layer takes, or ramp each layer before
  combining. Neither is decided here.

### D-7. Occlusion: start from today's approximation, judge a baseline

Decided by the owner (Q-12). Relayed on 2026-10-17 by the owner's assistant laz to the moskophoros manager, which recorded it (owner message Sentinel_89d25b4bec048191ad74761c24fd93fc, delivery key owner-alpha-q10-q12-20261017-Sentinel_89d25, cmux message 3f7199ab-16e1-4cc4-8af6-73bdf50451c5). The owner asked that the decisions be passed to the manager as an attributed message.

The owner: "we start with the approximation, then examine the output, no need
to investigate until we have a baseline anyways."

- **The assistant's interpretation, already given to the owner** (recorded as
  the assistant's reading, not a separately quoted owner choice):
  - keep the current approximation at first, in which every surface occludes
    as if solid in the shade's ambient occlusion (material styling D-25);
  - then judge the baseline output.
  - This does not mean taking translucent materials out of the occlusion.
- No further investigation of occlusion through holes or translucency (the
  further spike Q-12 mentions) until a baseline exists. Spike 1's gated
  occlusion distance is a cost measure with identical output, and does not
  conflict with this.

### D-8. The colour is flat and unlit; this replaces lighting D-23

Decided 2026-10-17 by the owner in this design's session (Q-11, option A),
approving the recommendation put to them in these words: yes to flat, which
replaces lighting design D-23 for materials without a ramp and fits "no light
baked" (material styling D-27); an unramped model that looks too flat is
given a generated ramp. The owner: "all of your recommendations here are
correct, i approve".

- Capture records each surface's flat, unlit material colour. In spike 1 the
  body is (231, 137, 89), not the studio-lit (162, 105, 80).
- **Materials with a ramp** are unchanged: their colour comes from the ramp,
  and the shade moves along it (material styling).
- **The ordinary look** (no library, or a material without a ramp) shows the
  material's flat colour with no shading. Light comes from the normal map and
  the lit preview. Workbench's camera-fixed studio light is no longer used,
  so lighting design D-23 is replaced, and a lit preview no longer applies
  light a second time over a lit colour.
- Not implied: quantising translucent composites to the palette. That is
  part of the palette question still to settle.

### D-9. Edges are a setting, `edges: hard | soft`

Decided 2026-10-17 by the owner in this design's session (Q-7), approving
the recommendation: "all of your recommendations here are correct, i
approve".

- Setting `edges`, values `hard` (the default) and `soft`, with the option
  `--edges hard|soft`, under the settings layers (settings design).
- It is recorded in the sheet's settings, so `--settings-from` reproduces it.
- `hard` and `soft` are the two rules of D-4.
- It acts after capture (V-4), so the capture job is the same whichever is
  chosen.
- The sheet schema bump that carries it is settled with the slices.

### D-10. The alpha epic supersedes #75

Decided 2026-10-17 by the owner in this design's session (Q-8), approving
the recommendation: "all of your recommendations here are correct, i
approve".

- The new alpha epic replaces #75. #75 is closed with a link to the epic
  when the epic is filed.
- Its framing, rendering cutouts through Workbench, no longer matches the
  capture this design uses (spike 1).
- `process-design-doc` and the manager act on it; this design changes no
  tracker state.

### D-11. The maps describe the front-most surface

Decided 2026-10-17 by the owner in this design's session (Q-5, option A),
approving the recommendation: "all 3 recommendations are sound, once again, i
approve".

- Where a translucent layer covers a pixel, the normal and depth maps
  describe the nearest surface that is not a hole: the cloth, where cloth
  covers the body or the background.
- The normal map's alpha copies the colour's alpha, and the depth map is
  non-zero exactly where the colour's alpha is above 0. A pixel transparent
  in the colour is transparent in every map, and the lighting design's
  "the two alphas are identical" holds with partial alpha.
- The normal's direction is stored unblended.
- The lit preview lights the front-most surface's direction.

### D-12. Translucent layers combine into one front layer, first

Decided 2026-10-17 by the owner in this design's session (Q-13, option C),
approving the recommendation: "all 3 recommendations are sound, once again, i
approve".

- All translucent layers in front of the first opaque surface combine into
  one front layer. Its colour and alpha are their front-over-back composite
  (D-6). Its identity and shade are those of the front-most translucent
  surface.
- Stylize ramps that layer by the front-most material, then lays it over the
  ramped opaque surface.
- When the front-most translucent material has no ramp, every pane's own
  colour survives in the composite. When it has a ramp, a rear pane's ramp is
  not applied.
- Keeping each translucent layer separately (Q-13 B) is done only if a real
  model needs it, judged on the baseline, as D-7 does for occlusion.

### D-13. Previews blend translucent pixels over their grey

Decided 2026-10-17 by the owner in this design's session (Q-14), approving
the recommendation: "all 3 recommendations are sound, once again, i approve".

- Each preview pixel is blended over the solid `#808080` background with its
  alpha, in 8-bit sRGB straight alpha, as an image viewer shows a PNG.
- The lit preview lights the colour with the normal map (D-11) first, then
  blends the same way.
- Blended pixels add colours. A frame over 256 colours takes the existing
  reduction to 256 with its warning, even with a palette: the rule that a
  paletted frame keeps exact colours holds only for frames without
  translucent pixels.
- Rejected: blending in linear colour, which is closer to the render but
  further from how viewers and engines show the sheet.
- **Rounding of the blend** (recorded by the moskophoros manager on
  2026-10-17, answering the issue processor's question; it applies D-13 with
  this design's half-up convention and decides nothing new): each 8-bit
  channel is `floor((c·α + 128·(255 − α)) / 255 + ½)`, with `c` and `α` the
  pixel's 8-bit sRGB channel and alpha and 128 the grey. It is exact at
  `α` 0 and 255, so opaque previews are unchanged, and it is pinned with a
  test vector in ALPHA-3. Rejected: whatever an imaging library's own
  integer approximation gives, which can differ by one level.

### D-14. With a palette, the composite's RGB snaps; alpha stays smooth

Decided 2026-10-17 by the owner in this design's session (Q-15, option A):
"for Q-15 i think you are right, snap the result to the nearst equivalent
anywhere in the palette, not just the two color ramps of the blending
materials, rgb snaps, alpha remains smooth".

- When the sheet has a palette, each layer is ramped or mapped as today,
  the front is composited over the back, and the result's RGB is mapped to
  the nearest colour **anywhere in the palette**, not only in the two
  materials' ramps. The nearest colour is the existing palette mapping's
  (`imageops.map_palette`: Euclidean distance in OKLab, the earlier entry
  on a tie).
- Alpha is not snapped: it keeps its 8-bit value (D-2).
- A pixel without a front layer is already a palette colour, so mapping it
  again leaves it unchanged. Every colour of a paletted sheet is a palette
  colour.
- Without a palette nothing is snapped.

### D-15. Material styling D-26 is superseded; `BLEND` materials have an identity

Decided 2026-10-17 by the owner in this design's session (Q-16). The owner
delegated the wording: "Q-16 you can replace the wording however you think
most alligns to my most recent statements". The recorded wording, aligned
with D-1, D-6 and D-12 ("a translucent material can have a ramp too"):

- Material styling D-26 is superseded by this design (D-1 to D-3, D-6,
  D-11, D-12, D-14). `MASK` cutouts and `BLEND` translucency are captured
  with the model's alpha, and the material ID, shade, normal and depth
  describe the surfaces of the colour's layers as this design sets out.
- `BLEND` materials leave the no-identity class. They have an identity like
  any other material, pool by name with opaque materials of the same name,
  and take a ramp through their entry or the library's default. The warning
  for a library mapping a name used only by `BLEND` materials goes.
- Until the alpha slices land, D-26 and the no-identity rule describe current
  behaviour. The note is recorded in `material_styling_design.md`.
- **A `BLEND` entry's own shade** (recorded by the moskophoros manager on
  2026-10-17, answering the issue processor's question; it reads "like any
  other material" and decides nothing new): a `BLEND` material whose entry
  gives its own shade values is treated exactly as an opaque ramped
  material. Its own capture values (`ao_distance` and the weights) reach the
  capture job as per-material overrides (settings design D-36), its own range
  applies in stylize, and the override warnings apply to it. `docs/design.md`
  §Material libraries' rule that a `BLEND` material takes the global values
  belonged to D-26's no-identity class and goes with it, in ALPHA-5. A
  `BLEND` material taking the library's default ramp takes the global values
  and the library's range, as any material does.

### D-16. The slicing is the designer's

Decided 2026-10-17 by the owner in this design's session (Q-17): "Q-17 is a
process question, i dont care, you can slice this up however you feel is
best. if everything is clear, and you think its ready, mark it ready when
you are done". The Delivery plan's ALPHA-1 to ALPHA-7 are the designer's
slicing under that delegation, and the owner's same words authorised marking
the design ready.

## Open questions

### Q-1. Scope: what does "alpha" cover?

**Resolved by D-1.**

glTF has two kinds of transparency:

- **`MASK`, cutouts.** Each texel is either drawn or discarded, at the
  material's `alphaCutoff` (0.5 by default). Used for foliage, fences, hair
  cards and chain mail.
- **`BLEND`, translucency.** A surface is partly see-through: glass, water,
  smoke, ghosts, energy effects.

Alpha can come from the base colour texture's alpha, from
`baseColorFactor`'s alpha, or both (glTF multiplies them, and vertex colour
alpha too).

What matters is which effects the owner needs now, and whether a model
needs it today.

### Q-2. Output alpha: binary, or levels of translucency?

**Resolved by D-2** (full 8-bit). Kept for the alternatives: binary, or a few levels.

A sheet pixel can be binary, fully there or not, which is the pixel-art
convention, or it can carry levels of partial alpha. With levels:

- how many there are;
- how they relate to the palette (which has no alpha), the coverage rule
  and `plain` and `mode`;
- what a translucent pixel shows: the colour blended over what is behind it
  in the model, or the front surface's colour with a partial alpha.

### Q-3. Where does a surface's alpha come from?

**Resolved by D-3.**

Follow glTF: `baseColorFactor` alpha × texture alpha × vertex colour alpha,
with `alphaCutoff` for `MASK`. Or a subset.

### Q-4. Capture technique and cost

**Settled by capture spike 1** (see Design), a technical finding rather than
an owner decision. The separation of the front layer is left to ALPHA-4's
spike, with the stop-and-ask rule in *The pipeline with alpha*.

How Blender produces cutouts and, if in scope, translucency,
deterministically: Cycles for the colour, a separate alpha pass, or another
method, with its cost per frame. To settle by a spike once scope is known.

### Q-5. The other buffers through a cutout or a translucent surface

**Resolved by D-11** (front-most surface). The previews are D-13; the GIF
previews sit on solid grey, so their one-bit transparency is never used.

The material ID, shade, normal and depth: do they show the front surface,
the first opaque surface, or none? And how do the lit preview and the GIF
previews (one-bit transparency) show it?

Narrowed by D-6. Each layer, the opaque surface behind and the translucent
front layer, carries its own material identity and shade, because stylize
ramps each. The previews are Q-14. What stays open is which surface the
**normal and depth maps** describe where a translucent layer covers a pixel,
and what alpha the maps carry there:

- **A. The front-most surface (proposal).** The maps describe the nearest
  surface that is not a hole: the cloth where cloth covers the body.
  - One rule covers cloth over the body and cloth over the background, which
    has nothing opaque behind it.
  - Depth is the depth of what is in front, which is what a game needs to
    sort the sprite against others.
  - A game lighting the pixel lights the cloth's direction. For thin cloth
    that is close to the body's.
- **B. The opaque surface behind, falling back to the translucent one** where
  nothing opaque is behind. The body seen through glass is lit as the body,
  but the rule has a fallback, and depth sorts by what is behind the glass.
- **C. Both,** as a second normal and depth map for the front layer. Most
  information, but more files and more for a game to load.

In every option the normal map's alpha copies the colour's alpha, and the
depth map is non-zero exactly where the colour's alpha is above 0. The
lighting design's rule that "the two alphas are identical" and "whatever is
transparent in the colour sheet is transparent in every map" then hold
unchanged with partial alpha. The normal's direction is stored unblended.

### Q-6. Compatibility

**Resolved by D-5:** no byte-identical guarantee; the rest is folded into the capture technique (Q-4) and the review.

- Sheets of models without `MASK` or `BLEND` materials stay byte-identical
  (to confirm).
- Sheets of existing `MASK` models change. The owner decides that change and
  its acceptance. D-26 and design §Capture are revised to match.

### Q-7. Settings

**Resolved by D-9** (`edges: hard | soft`). Other settings, such as a cutoff
override, were not asked for.

Whether anything is a setting or an option, such as an alpha cutoff
override, the number of levels or an opt-out, under the settings layers and
the schema-bump rule.

### Q-8. What happens to #75?

**Resolved by D-10** (superseded).

The new epic either supersedes #75 or absorbs it as a child. This design
recommends one; `process-design-doc` and the manager act on it.

### Q-9. Outlines: hard pixel edges, or soft?

**Resolved by D-4** (both, hard by default).

Raised by D-2. Two kinds of partial alpha meet in a pixel's block:

- **Edge coverage:** at a sprite's outline, or at a cutout's edge, part of
  the block shows a surface and part shows nothing.
- **Material alpha:** a translucent surface covers the whole block but is
  partly see-through.

Today edges are hard: a block at least half covered is a full pixel (alpha
255), and anything less is empty. This is the pixel-art convention, and every
existing sheet relies on it.

- **A. Hard edges, translucency kept (proposal).**
  - Each supersample records whether it shows a surface. A cut-out hole
    shows the surface behind, or nothing.
  - Each supersample also records the alpha it shows: 1 for an opaque
    surface, partial through a translucent one.
  - A pixel exists when at least half its block shows a surface, as today.
    Its alpha is the mean alpha of those surface samples, in 8 bits.
  - Outlines and cutout edges stay crisp. Only translucent materials give
    partial alpha. An opaque model's pixels stay at 255, so its sheets can
    stay byte-identical.
- **B. Soft edges everywhere.**
  - A pixel's alpha is its block's mean alpha.
  - Outlines and cutout edges become antialiased, partly transparent
    pixels.
  - Every existing sheet changes, opaque ones included, and the sprite
    gains the soft fringe that pixel art usually avoids.

### Q-10. Translucency over a material with a ramp

**Resolved by D-6** (two layers, blending required). Normal and depth under translucency (Q-5), and stacks of translucent layers, stay open.

Raised by spike 1. A material ramp *replaces* a pixel's colour with palette
colours chosen by the shade (material styling). A single composited colour
cannot be both ramped and seen through. Consider translucent cloth over a
ramped body:

- **A. One layer (simplest).**
  - Each pixel is described by one surface (the gate's T).
  - With the front-most surface, the cloth has no identity (`BLEND` takes
    the ordinary look today), so the body seen through it loses its ramp and
    shows its raw colour.
  - With the first opaque surface, the body's ramp replaces the composite,
    and the cloth disappears.
- **B. Two layers (proposal).**
  - Capture also records the front translucent layer: its colour, alpha and
    identity.
  - Stylize ramps the opaque surface behind it as usual, then lays the
    translucent layer over it with its alpha. A translucent material can
    have a ramp too.
  - The look is decided after capture (V-4), and cloth over a ramped body
    looks right.
  - It costs more design and one more slice.
  - Several translucent layers stacked in front would be combined into one
    front layer.

It also decides which surface the normal and depth maps describe under
translucency.

### Q-11. The colour's lighting: flat, or studio-lit?

**Resolved by D-8** (A, flat colour, confirmed 2026-10-17). The owner's
earlier leaning, kept for its wording: relayed on 2026-10-17 by the owner's assistant laz to the moskophoros manager, which recorded it (owner message Sentinel_89d25b4bec048191ad74761c24fd93fc, delivery key owner-alpha-q10-q12-20261017-Sentinel_89d25, cmux message 3f7199ab-16e1-4cc4-8af6-73bdf50451c5). The owner asked that the decisions be passed to the manager as an attributed message. The owner leans
"flat base colour" and said: "sprite colors should be straight from the color
palette, there shouldnt be any shading on them, the shading just shifts up and
down the color ramp in the render". The owner also said the question was not
really clear.

To confirm with the owner, without reopening settled scope:

- **The capture versus the ramp.** Q-11 is about the colour that capture
  records, the ordinary look's base colour. Option A makes it flat and unlit.
  Moving along a ramp's palette entries by the shade is material styling,
  and it is unchanged by any option here. The owner's description matches A
  for materials with a ramp.
- **Materials without a ramp.** The ordinary look (no library, or a material
  without a ramp) has no ramp to shift along. Under A it shows the material's
  flat colour with no shading at all. Lighting design D-23 (owner,
  2026-10-13) kept Workbench's studio light for exactly this look, so
  choosing A replaces D-23. The owner should confirm both.
- **Not implied:** quantising blended colours to the palette. The owner's
  "straight from the color palette" is not recorded as a new requirement for
  translucent composites (D-6).

Raised by spike 1. Lighting design D-23 (owner, 2026-10-13) keeps the
ordinary look's Workbench studio light. Workbench cannot render alpha, and
the Cycles colour is the material's flat, unlit colour. For the body that is
(231, 137, 89), against (162, 105, 80) studio-lit.

Options:
- **A. Flat colour:** the ordinary look becomes the material's own colour
  with no light, which fits D-27's "no light baked". Light comes from the
  normal map and the lit preview. An object without a ramp looks flat.
- **B. Imitate the studio light:** emit the colour times a fixed function of
  the camera-space normal. This is close to today, but a baked directional
  light again, and untested.
- **C. Ambient-shaded colour:** the colour times a factor from the shade
  (occlusion and curvature). This needs a mapping to be designed.

Ramped materials are unaffected, since their colour comes from the ramp.

### Q-12. Do cutouts and translucent surfaces occlude the shade?

**Resolved by D-7** (today's approximation first, then judge a baseline).

Raised by spike 1. The shade's ambient occlusion (material styling D-25)
treats every surface as solid.

- A body behind a leaf's holes is darkened as if the holes were solid: shade
  0.18, against 0.34–0.38 without the leaf.
- A translucent quad darkens what it covers.
- Making `MASK` and `BLEND` surfaces not occlude at all is possible, but
  then a leaf's solid texels cast no occlusion either.
- Honouring the holes exactly needs a further spike.

### Q-13. A stack of translucent layers, each with a ramp

**Resolved by D-12** (option C: one combined front layer first).

Raised by D-6. Two panes of glass, or cloth over a veil, put two translucent
layers in front of one opaque surface. When both have a material ramp,
something has to say whose ramp colours the front.

- **A. One combined front layer (proposal).**
  - Capture combines all translucent layers in front of the opaque surface
    into one front layer: its colour and alpha are their front-over-back
    composite (D-6), and its identity and shade are the front-most
    translucent surface's.
  - Stylize ramps that layer by the front-most material, then lays it over
    the ramped opaque surface.
  - When the front-most translucent material has no ramp, both panes' own
    colours survive in the composite. When it has a ramp, the rear pane's
    ramp is not applied: its own colour is replaced by the front ramp's
    colours.
  - It fits the spike's capture: one more gated layer, about today's cost.
- **B. Every translucent layer kept separately** up to a fixed count, such as
  4, each with its own colour, alpha, identity and shade. Stylize ramps each
  and composites them back to front.
  - Exact for any stack.
  - Untested. Separating layers probably needs a further render per layer
    (depth peeling), and a stack deeper than the count needs its own rule.
- **C. A first, B later if a model needs it.** Judge the baseline as D-7
  does for occlusion.

### Q-14. Partial alpha in the previews

**Resolved by D-13** (blend over the grey in 8-bit sRGB).

The flat GIF previews draw each frame on a solid `#808080` background
(design §Export), so a GIF's one-bit transparency is never used. A
translucent pixel needs only a blend rule.

- **Proposal:** blend each pixel over the grey with its alpha, in 8-bit sRGB
  straight alpha, as an image viewer shows a PNG. The lit preview lights the
  colour with the normal map (Q-5) first, then blends the same way.
- Consequences:
  - Blended pixels add colours. A frame with more than 256 colours takes the
    existing reduction to 256, with its warning.
  - The rule that a paletted frame keeps exact colours (at most 255 plus the
    grey) no longer holds for a frame with translucent pixels. Such a frame
    can then warn.
- **Alternative:** blend in linear colour, matching the capture composite
  (D-6). It is closer to the render, but differs from how viewers and most
  engines show the sheet.

### Q-15. The palette and translucent pixels

**Resolved by D-14** (option A, snapped anywhere in the palette).

A palette has no alpha. With a palette today, every kept pixel's colour is a
palette colour. Translucency adds two kinds of colour that are not:

- a translucent layer over an opaque one, which composites to alpha 1;
- a translucent layer over the background, which keeps a partial alpha.

Options:

- **A. Snap after compositing (proposal).**
  - Each layer is ramped or mapped to the palette, composited, then the
    result is mapped to its nearest palette colour, as `plain` maps a pixel
    today. Alpha is unchanged.
  - Every pixel's colour in a paletted sheet stays a palette colour, as the
    owner put it, "straight from the color palette". Translucency shows only
    in alpha, and in which palette colour a see-through mix lands on.
  - Cloth at 0.4 over a body becomes the palette colour nearest the mix.
- **B. Do not snap the composite.**
  - Each layer is a palette colour, but their blend is not.
  - Smoother see-through, but a paletted sheet then holds colours outside
    its palette.

Without a palette nothing is snapped, under either option.

### Q-16. The revision of material styling D-26

**Resolved by D-15.**

D-26 (owner, 2026-10-08) captured `MASK` opaque, with no cutouts, and the
material styling design keeps `BLEND` materials in the no-identity class,
always taking the ordinary look. D-1, D-6 and D-12 supersede both. The
revision recorded in `material_styling_design.md` would say:

- **D-26 is superseded by the alpha design** (D-1 to D-3, D-6, D-11, D-12).
  `MASK` cutouts and `BLEND` translucency are captured with the model's
  alpha. The ID, shade, normal and depth describe the surfaces of the
  colour's layers, as the alpha design sets out.
- **`BLEND` materials have an identity** like any other: they leave the
  no-identity class, and can take a ramp through their entry or the
  library's default. The warning for a library that maps a name used only by
  `BLEND` materials goes.
- Until the alpha slices land, D-26 and the no-identity rule describe
  current behaviour.

### Q-17. The delivery slices

**Resolved by D-16** (delegated to the designer).

The proposed slices are in the Delivery plan below: seven, in dependency
order, with the owner's visual review last, as LIT-6 was. To settle: whether
the split and order are right, and whether anything is missing.

## Test inputs

The repository's tests generate their own `.glb` fixtures (AGENTS.md), so
the automated checks never wait on a hand-made model. The capture spike
(Q-4) also uses generated fixtures.

An owner-made model is the right input for the owner's visual review (V-12),
and it is needed only by that last slice. It can be built in parallel with
this design. **Proposal for what it holds**, as one model or a few small
ones:

- **A cutout:** a `MASK` material with a texture whose alpha has holes, such
  as leaves, a fence or hair cards, with an `alphaCutoff` set. The holes
  should show both another surface of the model behind them and empty
  background.
- **Translucent cloth:** a `BLEND` material with partial alpha (a texture's
  alpha, or only `baseColorFactor`'s alpha), over an opaque part of the model
  and also against empty background.
- **A translucent material with an alpha gradient,** to show the range of
  levels.
- **An opaque part** beside them, with named materials, so that material
  ramps and the maps can be checked next to the transparency.
- **Ideally a short animation,** so cutouts and translucency are seen moving
  across frames.
- **Export:** a binary glTF (`.glb`), with each material's alpha mode set in
  Blender, so the glTF records `MASK` or `BLEND`.

## Verification strategy

- **Generated fixtures** (the repository's tests build their own `.glb`, as
  `tests/material_models.py` does): a cutout plane over a body and over the
  background, with texels on both sides of the cutoff (127 cut, 128 kept); a
  translucent quad over a body and over the background; an alpha gradient;
  two translucent panes; a stack deeper than the bounce limit; an opaque
  named material beside them.
- **Alignment:** the material ID, shade, normal and depth describe the
  surfaces D-11 and the layers name. The normal map's alpha equals the
  colour's, and the depth map is non-zero exactly where the colour's alpha
  is above 0, under `plain` and `mode`, with and without a palette or a
  library, and under both `edges` values.
- **Exact values:** composite alpha and colour against the front-over-back
  formula (D-6); hard and soft coverage against D-4; palette snapping
  against D-14.
- **Determinism:** repeated runs, in separate processes, give identical
  bytes.
- **Mixed stacks** (spike 2): exact composites through holes and panes
  under the pinned bounce limits; tiny-alpha and hole-floor surfaces; the
  surface gate's hit exactly 0 or 1.
- **Failure:** a stack one deeper than the limit fails with exit 5, behind a
  visible front layer and ending at the background alike, naming the input,
  clip, direction, frame and limit, and publishing nothing; an unsupported
  material graph and a missing or corrupt buffer fail the same way.
- **Cost:** per-frame time on an ordinary model and on stacked cutouts,
  compared with today's two renders, reported in the slice's pull request.
- **Compatibility:** no byte-identical guarantee (D-5). Each pull request
  that changes output names the tests whose pinned output it updates, and
  gives the command that reproduces the new sheets. Only the current sheet
  schema loads (settings design D-24); a new sheet reproduces itself byte
  for byte through `--settings-from`.
- **Look:** the owner's visual review, ALPHA-7 (V-12), on the owner's model
  (Test inputs). Tests prove alignment, not how a sprite looks.

## Delivery plan

The designer's slicing (D-16). ALPHA-1 to ALPHA-5 are code slices: each
lands in its own pull request and updates the parts of `docs/design.md` it
changes there, since tests read that document. ALPHA-7 is a
documentation-only acceptance step with no pull request, as material
styling MAT-7 and lighting LIT-6 were.

### ALPHA-1. Capture colour and buffers in one flat Cycles render

- **Outcome:** one Cycles render per frame gives the colour, material ID,
  shade, normal and depth; Workbench is gone from capture.
- **Scope:**
  - the capture settings of *The pipeline with alpha*, both bounce limits
    pinned at 64 (A-1);
  - the extraction rule for Principled and unlit graphs, refusing other
    shapes, and the white material-less stand-in (A-8);
  - the flat, unlit colour (D-8);
  - ID and shade as float AOVs, encoded as the transport table says;
  - the colour written from pixels;
  - provenance: `renderer` `"cycles"`, `studio_light` removed, the `color`
    record; the capture result `/2` and the next sheet schema (A-7);
  - design §Capture, *Capture job and result contract* and the sheet JSON.
  - Every material is still captured opaque, as D-26 has it.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** critical path, can land first.
- **Relevant decisions:** D-5, D-7, D-8.
- **Acceptance signals:**
  - buffers aligned on the existing fixtures;
  - identical bytes across runs in separate processes;
  - material codes 255, 256 and 65535 (material-less) round trip; shade
    0.25 encodes to 137;
  - unlit opaque fixtures and a material-less primitive render their flat
    colour, the latter white;
  - an unsupported material graph fails with exit 5 naming it;
  - per-frame cost against today's two renders, reported;
  - tests pinning Workbench output updated and named.
- **Out of scope:** any alpha from materials.
- **Open questions:** None.

*ALPHA-1's implementation notes* (recorded by ALPHA-1, #114, 2026-10-17;
`docs/design.md` §Capture, *Capture job and result contract* and §Export
hold the contract). They record choices the decisions left to the slice:

- **One shader replacement per phase.** With no second render to alternate
  with, the capture shaders, the four AOVs (`matid`, `shade`, `normal`,
  `depth`) and the material-less stand-in are applied once before the first
  frame and restored when the phase ends (`blender_script.Surfaces`). The
  render settings are set once (`configure_render`).
- **Colour from the TGA.** Each frame's colour is the render's 8-bit TGA,
  written by Blender through the `Standard` transform with dither 0, so the
  encoding is Blender's; the script masks it to the coverage and writes the
  PNG itself. The shade's byte is computed by the script as
  `floor(255 · sRGB(v) + ½)` (0.25 gives 137, as before).
- **Coverage.** The OpenEXR's `Combined` alpha decides it. In this slice it
  must be exactly 0 or 1 everywhere, and the TGA's alpha, the material-ID
  AOV and the normal and depth AOVs must agree with it pixel for pixel, or
  the frame fails (exit 5). ALPHA-2 relaxes the first rule for cut-outs.
- **The extraction rule** reads the active Material Output's `Surface`: a
  Principled BSDF gives the socket feeding `Base Color`; the unlit core,
  alone or wrapped, the socket feeding its Emission's `Color`. A constant is
  copied, a chain linked. Only materials a subject surface renders are read,
  so an unused material of any shape is never refused. A refusal names
  `glTF material <index>` and its original name.
- **The `color` record** is named `cycles-flat-emission`, and lists its
  fields in the order the issue gives them; it sits before `shade` in
  `backend` and `generator`. `pass_alpha_threshold` is recorded as the exact
  float `9.313225746154785e-10`.
- **The scratch directory** is renamed from `auxiliary/` to `scratch/`, and
  its files to `capture.tga` and `capture.exr`, since there is no auxiliary
  render any more; its lifetime is unchanged.
- **The launcher's colour check** is new: a colour alpha of 0 or 255 only,
  an empty colour pixel `(0, 0, 0, 0)`, and the colour's coverage equal to
  the material ID's in both directions, checked after the other buffers so
  their own diagnostics keep their precedence.

### ALPHA-2. Cut out `MASK` materials

- **Outcome:** a `MASK` material's cut-out texels are holes in the colour and
  in every buffer, showing the surface behind or nothing, and a stack too
  deep to render fails loudly.
- **Scope:**
  - the importer's alpha chain for `MASK` (D-3), with its cutoff, Principled
    and unlit;
  - spike 2's surface gate (A-2) and the gated occlusion distance;
  - the count render, its switch and its exit 5 (A-3, B-1).
  - Output alpha stays binary, by today's coverage rule. `BLEND` is still
    captured opaque.
- **Phase:** 2.
- **Depends on:** ALPHA-1.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-7, D-10.
- **Acceptance signals:**
  - the cutoff fixture keeps 128 and cuts 127; a `LINEAR`-filtered cutoff
    stays binary; an unlit `MASK` cuts the same;
  - holes over a body show the body's ID, shade, normal and depth; holes
    over the background are transparent in every map;
  - every gated hit is exactly 0 or 1;
  - 64 holes over a body or over the background render correctly; 65 fail
    with exit 5 naming the input, clip, direction, frame and limit, and
    publish nothing (the translucent-front cases belong to ALPHA-4, where
    `BLEND` becomes see-through);
  - no valid stack is refused;
  - stacked-cutout cost reported.
- **Out of scope:** partial alpha, `BLEND`.
- **Open questions:** None.

*ALPHA-2's implementation notes* (recorded by ALPHA-2, #115, 2026-10-17;
`docs/design.md` §Capture, *Capture job and result contract* and §Exit codes
hold the contract). They record choices the decisions left to the slice:

- **Which alpha reaches the mix.** The extraction rule returns each
  material's alpha socket (a Principled BSDF's `Alpha`, an unlit wrapper's
  factor, or none for the bare unlit core), and only a material whose glTF
  `alphaMode` is `MASK` uses it; every other material's mix takes a constant
  1, so `BLEND` stays opaque until ALPHA-4.
- **One graph, one switch.** Each material holds the main surface, the
  count surface and spike 3's `group` switch: a shared node group,
  `moskophoros.count`, whose one value feeds `Mix(S, main, count)` and
  multiplies the gate, so a single product `gate · (1 − S)` gates every AOV,
  the hit AOV and the occlusion distance. At `S = 0` every factor is exactly
  1 or the gate, so an opaque model's buffers are the same bytes as
  ALPHA-1's.
- **The hit AOV** is the gated value itself. With binary alpha, coverage is
  still read from the `Combined` alpha, which must be exactly 0 or 1, and
  the hits must equal it pixel for pixel; ALPHA-3 moves presence to the hits
  when alpha becomes partial.
- **The count render** is rendered without writing a still and saved to
  `scratch/count.exr`; its message names the input path, the clip, the
  direction, the frame's ordinal and time, the first pixel at the limit and
  the limit itself.
- **Occlusion noise.** Each transparent bounce advances Cycles' random
  sequence, so one-sample occlusion noise at convex edges can differ when
  holes are stacked in front of a surface; an open flat surface's shade is
  unaffected. This is part of the occlusion approximation (D-7), not of the
  gate.

### ALPHA-3. Carry 8-bit alpha, the `edges` setting and preview blending

- **Outcome:** sheets carry 8-bit alpha under the `hard` and `soft` rules,
  the maps copy it, and the flat and lit previews show it over their grey.
- **Scope:**
  - steps 1 and 5 of the numerical reference, for `plain` and `mode`, with
    and without a palette or a library (A-6);
  - the `edges` setting and `--edges` (D-9), recorded in
    `settings.style.edges`; the next sheet schema, with the previous one
    refused (A-5);
  - the maps' alpha (D-11);
  - preview blending in 8-bit sRGB over `#808080`, flat and lit, with the
    colour-count warning (D-13), merged here from ALPHA-6 because previews
    are on by default (A-4).
- **Phase:** 2.
- **Depends on:** ALPHA-2.
- **Ordering:** critical path.
- **Relevant decisions:** D-2, D-4, D-9, D-11, D-13.
- **Acceptance signals:**
  - the pinned cases of the numerical reference that need no front layer;
  - `hard` keeps today's outlines; `soft` gives the block mean;
  - map alpha equals colour alpha under both;
  - a whole command with `--edges soft` and default previews succeeds, and
    so does one with a light; a partial pixel previews as the blend over
    the grey; opaque previews are byte-identical to before the slice;
  - `--settings-from` reproduces a new sheet byte for byte; a sheet of the
    previous schema is refused with exit 2; the capture job's hash is the
    same under `hard` and `soft`.
- **Out of scope:** translucency.
- **Open questions:** None.

*ALPHA-3's implementation notes* (recorded by ALPHA-3, #116, 2026-10-17;
`docs/design.md` §CLI, §Settings files, §Option validation, §Stylize,
§Export and §Scale and ground point, *Reuse*, hold the contract). They record
choices the decisions left to the slice:

- **One function decides coverage.** `imageops.block_alpha` is step 1 of the
  numerical reference, and `reduce_blocks`, `reduce_blocks_mode` and
  `map_ramps` each call it on the colour's alpha in place of their own 0.5
  cut. Their colour, vote and band rules are unchanged and still weight
  each sample by its colour alpha, which for a binary capture is the
  reference's equal surface weight.
- **An 8-bit alpha as a composite alpha.** A sample is a surface where its
  alpha is above 0, and its `aᵢ` is `257 · alpha`, so 255 is 65535. Captures
  are binary until ALPHA-4, so this is exactly the reference's `aᵢ`; it also
  gives the image functions, which take any RGBA, D-4's "mean alpha of the
  surfaces" under `hard` for partly transparent input.
- **Where `edges` lives.** `EDGES` is defined once in `imageops`, and the
  settings table, the option and the reused-sheet check take it from there.
  It sits after `materials` in the table and `defaults.yaml`, and after
  `reduce` in `settings.style`. The image and stylize functions default to
  `hard`; the command always passes the value in force, and the sheet
  record has no default.
- **Blending is export's.** `export.blend_over_background` gives D-13's
  rounding in exact integers, `floor((2x + 255) / 510)` for
  `x = c·α + 128·(255 − α)`. The 256-colour reduction still gives its
  reserved grey entry to wholly transparent pixels; a partly transparent
  pixel's blend is quantized with the other colours. Opaque previews, flat
  and lit, are pinned by digests computed at master `4ee6a76`.
- **Maps.** The normal map's alpha is the colour's alpha, and every check
  and use that took alpha 255 as covered takes alpha above 0: the maps'
  reduction, the map writers, depth overflow and lighting, which keeps the
  pixel's alpha.

### ALPHA-4. Capture and composite translucent layers

- **Outcome:** a `BLEND` surface is see-through: its front layer is captured
  apart from the opaque surface behind, and composited over it in stylize.
- **Scope:**
  - **first, a feasibility spike** separating the front layer from the
    back, with the stop rule of *The pipeline with alpha*;
  - `BLEND` alpha (D-3), Principled and unlit;
  - the front buffers and the capture result `/3` (transport table);
  - the maps from the front-most surface (D-11);
  - steps 2 to 4 of the numerical reference: layer weights, the linear
    composite and snapping the composite's RGB to the palette (D-14).
  - The front layer keeps the ordinary look.
- **Phase:** 3.
- **Depends on:** ALPHA-3.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-6, D-11, D-12, D-14.
- **Acceptance signals:**
  - spike 2's mixed stacks (a)–(d) match front-over-back;
  - a 0.4 quad over a body matches the formula; over the background its
    alpha is 0.4; two panes of 0.5 give 0.75;
  - every pinned case of the numerical reference that needs no ramp on the
    front layer (the front-ramp cases are ALPHA-5's);
  - the front's own transparent closure counts toward the limit: a visible
    translucent front followed by 63 holes (64 surfaces) renders correctly,
    and the same front followed by 64 holes (65 surfaces) fails with exit
    5, both ending at an opaque surface and at the background (spike 3 rows
    `vf_63_*`, `vf_64_*`); a front followed by 65 holes fails too (Review 1
    A-3, Review 2 B-1, Review 3 C-1);
  - tiny alpha (5e-7) is a surface; alpha at the hole floor (1e-9) is not;
    vertex alpha and texture × factor alpha render;
  - presence survives transport: the `[0.001, 0.001, 1, 1]` block gives
    alpha 128;
  - a ramped body keeps its ramp under the quad; the maps show the quad;
  - with a palette every colour is a palette colour and alpha is
    unsnapped;
  - a missing or corrupt front buffer fails with exit 5;
  - the cost gate of *The pipeline with alpha*, measured and reported.
- **Out of scope:** ramps on translucent materials.
- **Open questions:** None. If the feasibility spike fails the correctness
  or the cost gate, implementation stops and reports to the owner.

*ALPHA-4's implementation notes* (recorded by ALPHA-4, #117, 2026-10-17;
`docs/design.md` §Capture, *Capture job and result contract*, *Frames into
stylize* and §Stylize, *Two layers*, hold the contract). They record the
feasibility spike and the choices the decisions left to the slice:

- **The spike** is `alpha-design/spike-4/` (`REPORT.md`), beside spikes 1
  to 3. Both gates passed.
  - Correctness: stacks (a)–(d) and every per-sample state of the pinned
    cases give the front `q`, front and back colours and codes exactly. The
    composite from the 8-bit buffers is within one level of front-over-back.
  - Cost: 1.73× the baseline. The median of frames 2–5 then of three
    interleaved rounds was 2.029 s against spike 3's unchanged `today`
    1.174 s, per round 1.79×, 1.32× and 1.73×. It ran without
    whole-machine quiet at the owner's direction ("i do have empty cores,
    so you should take the test and just trust the timing"), with the
    1-minute load rising from 3.86 to 20.33.
- **The separation is a further render.**
  - The back render shows every `BLEND` surface as a hole.
  - The front render holds out every opaque surface. Its float alpha is
    then the front layer's alpha, and its 8-bit TGA, which Blender writes
    un-premultiplied, the front's straight colour, "encoded as `color`".
  - One shared node group of two values switches the three renders.
  - A model without a `BLEND` material renders no front render, so an
    opaque model's buffers are master's, byte for byte.
- **The front render runs with both bounce limits at 65.** Cycles shades a
  path's last surface after its 64th transparent bounce without closures,
  so a holdout there holds nothing out. The spike's boundary fixtures missed
  this; the production test of a front, 63 holes and a body found it. The
  count render bounds every accepted path, so this changes no other frame.
  The recorded `color` limits stay the back and count renders' 64.
- **The count render counts every `BLEND` surface,** whatever its alpha,
  since the back render crosses it as a hole. A `BLEND` layer Cycles treats
  as opaque (α > 1 − 10⁻⁵) in front of 64 more surfaces is refused, which
  the conservative rule allows.
- **Presence is the gated front hit.** The script requires the front
  render's float alpha to be above 0 exactly there. Below about 10⁻⁵,
  Cycles' coverage `1 − fl(1 − α)` differs from the emitted α, so a tiny
  front's straight colour can be off by a few levels. Such a layer's `q` is
  0, a surface of no weight.
- **Back weights from an 8-bit alpha:**
  `tᵢ = floor(257 · alpha · (65535 − uᵢ) / 65535)`. It is exact for a
  capture's 0 or 255 and for a sample without a front, so image functions
  given any RGBA keep ALPHA-3's rule.
- **Blocks without a front sample reduce as before.** The layered path
  applies only to frames with a front layer, and a block without a front
  sample reduces exactly as ALPHA-3 did.
- **Front identities decode to the no-identity class** until ALPHA-5.

### ALPHA-5. Give translucent materials identities and ramps

- **Outcome:** a `BLEND` material can take a ramp, by its entry or the
  library's default, and its front layer is ramped before compositing.
- **Scope:** `BLEND` leaves the no-identity class (D-15); the front layer's
  identity vote and band with its own weights (numerical reference, step
  2); the library warnings; design §Pipeline.
- **Phase:** 3.
- **Depends on:** ALPHA-4.
- **Ordering:** critical path.
- **Relevant decisions:** D-6, D-12, D-14, D-15.
- **Acceptance signals:** the numerical reference's front-ramp cases; a
  ramped translucent quad over a ramped body shows both ramps, composited
  then snapped; a name shared by opaque and `BLEND` materials pools as one;
  the `mode` tie case on the front layer.
- **Out of scope:** keeping translucent layers separately (D-12).
- **Open questions:** None.

### ALPHA-6. Blend translucent pixels in the previews

Merged into ALPHA-3 (Review 1, A-4): previews are on by default and refuse
partial alpha today, so the slice that first produces partial alpha must
blend it. Kept as an identifier only, marked `[no-issue]`.

### ALPHA-7. Owner review of alpha sheets

- **Outcome:** the owner reviews sheets, maps and previews of their own
  model and approves the look, or names what to change (V-12). The verdict
  is recorded in `docs/acceptance/alpha.md`.
- **Delivery:** documentation-only, with no pull request, as MAT-7 and LIT-6
  were. `docs/acceptance/alpha.md` lands on `master` with `docs-push`, and
  the issue is closed by a comment linking it at its commit. Renders stay
  outside the repository, under `~/.local/share/moskophoros-acceptance/`,
  each labelled with what it shows and the exact command. The owner's model
  is an owner-supplied input (Test inputs): renders wait for it and for the
  owner's signoff of the commands.
- **Scope:** renders of the owner's model (Test inputs) under both `edges`
  values, with and without a library, with the commands to reproduce them;
  the occlusion baseline D-7 asks for; whether D-12's combined layer is
  enough.
- **Phase:** 4.
- **Depends on:** ALPHA-1 to ALPHA-5.
- **Ordering:** critical path, last.
- **Relevant decisions:** D-7, D-12.
- **Acceptance signals:** the owner's recorded verdict.
- **Out of scope:** code changes, which become their own issues.
- **Open questions:** None.

## Review 1

Codex review 1 by mosk-reviewer-53, against `553fe50`:
`~/.local/share/moskophoros-acceptance/alpha-design/review-codex-1.md`
(sha256 `44d3d899dec7ec0f17b9545623b645a9de7cc3512013b0d573b6dbd17408ef37`),
with its probes in `review-1/` beside it. Revision request
moskophoros-20261017-1. Five blocking findings and three should-fix; every
one was verified against the probes and the code, and all are fixed. No
owner decision changed.

| Id | Severity | Disposition |
|---|---|---|
| A-1 | blocking | **Fixed.** Both transparent bounce limits are pinned at 64; spike 2 proves exact composites through mixed stacks and unchanged cost. Settings in *The pipeline with alpha*; tests in ALPHA-1 and ALPHA-4. |
| A-2 | blocking | **Fixed** without an owner decision. Spike 2's gate repeats Cycles' own transparency arithmetic, so it selects exactly the surface where Cycles stops (0 anomalies over 9 fixtures; the review's 5e-7 case now correct). No epsilon is chosen: the only surfaces treated as holes are those with `α ≤ 2^-25`, which Cycles itself renders with no coverage, so this is the alpha "as Blender imports it" (D-3). Recorded under *Precision limits*; tests in ALPHA-2 and ALPHA-4. |
| A-3 | blocking | **Fixed,** then corrected by Review 2 (B-1): spike 2's in-render marker proved unreliable, and spike 3's count render replaces it. Exit 5 with the diagnostic and nothing published. Tests in ALPHA-2 (holes) and ALPHA-4 (translucent fronts). |
| A-4 | blocking | **Fixed.** Preview blending (D-13) moves into ALPHA-3, which first produces partial alpha; ALPHA-6 is merged and marked `[no-issue]`. Whole-command acceptance with default previews and with a light. |
| A-5 | blocking | **Fixed** by honouring settings D-24: the older-sheet promise is removed, `edges` is required in the new schema, and the previous schema is refused. |
| A-6 | should fix | **Fixed.** *Stylize: numerical reference*: one coverage decision, per-layer weights carried per sample, the linear composite, rounding, palette snapping and pinned cases, including the review's 0.75 case and a front-only 0.4 block. |
| A-7 | should fix | **Fixed.** *Capture transport and provenance*: buffers, encodings, presence, validation, the shade byte (0.25 → 137), codes, provenance without `studio_light`, and which slice bumps which schema. |
| A-8 | should fix | **Fixed.** Spike 2's extraction rule covers Principled and `KHR_materials_unlit` graphs and refuses other shapes; the material-less stand-in is white, opaque, code 65535; unlit, vertex-alpha and `LINEAR` cutoff cases assigned to ALPHA-1, ALPHA-2 and ALPHA-4. |

Remaining risk, stated plainly: separating the front layer from the back
(ALPHA-4) is not yet proven. ALPHA-4 starts with a feasibility spike, and
stops and reports to the owner if it fails its correctness or cost gate
(Review 2 makes both gates measurable).

## Review 2

Codex rereview 2 by mosk-reviewer-53, against `0a69fba`:
`~/.local/share/moskophoros-acceptance/alpha-design/review-codex-2.md`
(sha256 `875e7fa494243f6310852c39b67e2c6003d2280728533f482e2ae6318965f62e`),
with its probes in `review-2/` beside it. It found A-1, A-2, A-4, A-5, A-7
and A-8 resolved, A-3 and A-6 partly resolved (through B-1 and B-2), and
confirmed that A-2's `α ≤ 2^-25` floor is Cycles' own arithmetic, needing no
owner decision. Every new finding was verified against the probes; all are
fixed, and no owner decision changed.

| Id | Severity | Disposition |
|---|---|---|
| B-1 | blocking | **Fixed.** Reproduced by spike 3: the marker accepts 65 white layers at alpha 0.67 with the colour darkened to 0.847. Spike 3's count render replaces it, independent of colour throughput: 137 of 137 cases agree with truncation, the 64/65 pair included, with no valid stack refused and no damaged frame accepted. Exit 5 is now defined as truncation, which is stricter than "the colour is wrong" (13 harmless truncations are refused), so the fail-loudly contract is kept, not weakened. Cost counted in the capture budget (1.19–1.22× today). Tests in ALPHA-2 and ALPHA-4. |
| B-2 | should fix | **Fixed.** `plain` maps each layer's mean to the palette before compositing, as D-14 says; the review's black-and-white case is pinned (white, not black). |
| B-3 | should fix | **Fixed.** ALPHA-2 keeps the pure-hole 64/65 cases; the visible translucent-front exhaustion cases move to ALPHA-4; the front-ramp pinned cases move to ALPHA-5. |
| B-4 | should fix | **Fixed.** The cost gate names its baseline (production capture at `0a69fba`), the frozen fixture and hash, the timing boundary over the complete capture, and the aggregation. A failed correctness or cost gate stops implementation after the spike pending the owner. |
| B-5 | minor | **Fixed.** The job is invariant under `edges` and the style values D-36 leaves out; its per-material capture overrides stay. |

## Review 3

Codex rereview 3 by mosk-reviewer-53, against `f2dec32`:
`~/.local/share/moskophoros-acceptance/alpha-design/review-codex-3.md`
(sha256 `8024d599bf4d858a6a125182c4f6318d0056ee87d22bf8008779205c3d4562a0`).
No blocking finding. It found B-1, B-2, B-4, B-5, A-3 and A-6 resolved and
B-3 partly resolved (through C-1), and confirmed that refusing harmless
truncations needs no owner decision. Both findings are fixed; no owner
decision changed, and the design stays ready.

| Id | Severity | Disposition |
|---|---|---|
| C-1 | should fix | **Fixed.** ALPHA-4's boundary counts the front's own closure: front + 63 holes renders, front + 64 holes fails with exit 5, at both endings (spike 3 rows `vf_63_*`, `vf_64_*`); front + 65 kept as an extra refusal. ALPHA-2's pure-hole 64/65 boundary is unchanged. |
| C-2 | minor | **Fixed.** Review 2's report hash corrected. |
