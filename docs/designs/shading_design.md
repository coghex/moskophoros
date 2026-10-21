# Shading design

Moskophoros must serve both sprites lit by their consumer from exported face
maps and art panels whose lighting is baked into their colours. This design
settles that capability with the owner before implementation.

Design state: `ready for issue processing`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [x] EPIC. Support configurable baked shading alongside live-lit sprites — [#137]
- [x] SHD-1. Preserve addressed normals for both capture layers — [#138]
- [x] SHD-2. Model and resolve shading settings and library responses — [#139]
- [x] SHD-3. Implement pure lighting and four-mode colour operations — [#140]
- [x] SHD-4. Implement deterministic ramp and snap dithering — [#141]
- [x] SHD-5. Integrate shading into the addressed-frame pipeline — [#142]
- [x] SHD-6. Expose shading controls and reproducible sheet settings — [#143]
- [x] SHD-7. Obtain owner visual acceptance for both uses — [#144]
- [x] SHD-8. Regenerate the inventoried working sheets — [#145]

The owner approved the eight delivery slices, their dependencies and design
readiness in D-35. D-36 to D-39 resolve review round 1's four owner questions
and approve the revised contracts and slice boundaries. Round 2 returned
READY; D-40 and the precision fixes below address its three minor findings.
The manager has directed issue processing, with separate signoff for each draft.

## Epic contract

- **Goal:** express the owner's two uses through generic project settings,
  with four settings-controlled modes: ramp, brightness, both and neither.
- **Done when:** the owner has accepted the implemented behaviours on both
  uses, including sheets and motion, and the agreed mechanical contracts
  pass verification; settings reproduce without source palette/library files;
  unchanged settings preserve baseline image bytes; and inventoried working
  sheets have been regenerated after acceptance, preserving historical evidence.
- **Users and operators:** artists generating sprites or panels and consumers
  using their colour, normal and optional depth maps.
- **Arc label:** none proposed.

This is a plan. It does not describe a shipped baked-light option.

## Current state and evidence

Verified against `master` at `6c5f47a1293cc8a99b25d5e6e360bfd3536ab320`
on 2026-10-20 (America/Los_Angeles):

- Capture supplies flat, unlit material colour, material identity, shade,
  normal and depth, with the alpha design's back and combined front layers.
  The shade combines ambient occlusion and curvature, with no directional
  light. The implementation is `capture/blender_script.py`, its material
  shader construction; the current contract is
  [design §Capture](../design.md#capture).
- Material ramps use that shade to choose palette entries. Their ranges may
  be set per material, at library level, or globally, in that order.
  Materials without a ramp use ordinary colour. `stylize.py` resolves the
  library and applies the reduction and ramp mapping.
- `--light X,Y,Z` currently affects only additional lit previews. It is a
  point in the camera's frame, in sheet pixels from the ground point, with
  no distance falloff. `export.lit_previews` uses the encoded normal and depth
  maps to apply `imageops.light_pixels` to the already reduced colour.
  It scales linear RGB by a factor from zero to one, so it does not brighten
  a colour beyond the input. Under perspective it still lights the 2D sprite,
  not reconstructed perspective geometry.
- Maps describe geometry and share colour coverage; normal maps are on by
  default and depth maps optional. Whether a map file is written is separate
  from using the underlying data for lit previews.
- Project files, free camera direction and roll, and perspective are built
  and accepted. Settings layer as shipped defaults < global file < loaded
  sheet < project file < options. Project names are absent from the sheet.
  See [projects and camera](projects_camera_design.md), especially D-8,
  D-11, D-13 and D-17, and its
  [acceptance record](../acceptance/projects-camera.md).
- The current sheet schema is `moskophoros.sheet/14`; only the current schema
  loads through `--settings-from`. Libraries are `moskophoros.materials/3`,
  with `/2` also supported. Recorded resolved settings and inline palette and
  library data support reproduction without reopening those input files.
- The owner's `projects/synarchy.yaml` supplies the accepted ambient shade,
  ramp formula, palette, hard edges, maps and a preview light. Its current
  contents were read, not changed. The other project's palette and settings
  follow this design; neither is being authored here.
- Tracker overlap recheck on 2026-10-21 UTC: no open shading epic or pull request.
  The only open issue is [#43](https://github.com/coghex/moskophoros/issues/43),
  mesh-weight animation pointers and CUBICSPLINE tangents. It is not a shading
  prerequisite; the manager should sequence overlapping capture-file edits.

### Existing contracts this design must explicitly amend

| Contract | Existing rule to amend or preserve | Approved replacement and owning slice |
|---|---|---|
| [Material styling](material_styling_design.md) D-22, D-25 | Ambient-only bands; no sky/ground or directional light | D-9/D-15/D-24/D-26 permit optional directional terms; SHD-6 |
| Material styling D-27; [lighting](lighting_sheet_design.md) D-4; design §Export | Light is previewed, not baked | D-5/D-6 permit baked modes while preserving the separate preview interface; SHD-6 |
| Lighting D-1; material styling D-27's default ambient capability | Preserve existing ambient output | D-7/D-8 retain exact default image bytes; SHD-1 through SHD-6 verification, SHD-6 narrative amendment |
| [Alpha D-8](alpha_design.md#d-8-the-colour-is-flat-and-unlit-this-replaces-lighting-d-23) | Ordinary materials are flat and unlit | D-14/D-23 permit optional brightness with the ordinary base, including without a library; SHD-5 integration and SHD-6 public contract |
| Material styling D-7, scope and ramp mapping; design §Palette mapping and composition, §Material ramps | Dithering excluded | D-12/D-17/D-27/D-29 approve the six patterns and quantisation rules; SHD-6 |
| [Settings](settings_design.md) D-20; design §Material libraries | The ordinary form carries no shade | D-33 adds `/4` ordinary mapping entries with overrides; SHD-6 |
| [Projects and camera](projects_camera_design.md) D-8; [vision V-7](../vision.md#v-7-consistency-is-the-product) | Light stays camera-fixed, V-7 unchanged | D-24 permits world-up sky/ground only; key stays camera-fixed, direction consistency remains; SHD-6 |
| Design §Capture job and result contract, §Frames into stylize | Mandatory transport buffers and decoded arrays omit separate layer normals | D-19/D-34/D-37 retain layer normals with one extra transported buffer; SHD-1 |
| Design §CLI, §Settings files, §Option validation, §Stylize, §Export, §Reproducibility | Existing options, palette/ramp rules and sheet record | D-32 to D-34 add controls, nested responses, validation, modes, snap and deterministic reuse; SHD-6 public activation |

These are known design changes requested by the owner, not defects to repair
silently. This draft changes no current contract document. Changes to
`docs/design.md` accompany implementation because tests read it.
The per-slice documentation and pinned-test assignments are listed below.
D-19 preserves existing capture information that was being discarded; it
adds no style choice to capture. This implements V-4's full-information
boundary and leaves later style experiments in stylize, consistent with V-8.

### What the owner has actually judged

- [Material styling](../archive/acceptance/material-styling.md): qualified proof of
  concept on 2026-10-08; generated ramps separately accepted on 2026-10-14.
  Neither is blanket approval of every future shading look.
- [Settings](../archive/acceptance/settings.md): accepted 2026-10-13. The owner wanted
  a look between the two shade trials; that did not change shipped defaults.
- [Lighting](../archive/acceptance/lighting-sheet.md): accepted 2026-10-14, including
  a dark rear light. This judged preview lighting.
- [Alpha](../acceptance/alpha.md): both hard and soft edges accepted;
  the combined translucent front layer and present occlusion approximation
  accepted. Wood shading and texture were left for later.
- [Cutouts](../acceptance/alpha.md#cutouts): accepted separately. The leaf
  range adjustment was a library choice, not a pipeline defect. The later
  request for a rounder trunk and a darker line beneath the pot rim initiated
  this design; it is preserved in the handoff quoted below.

### Probe 1: colour routing, term combination and dithering

Prepared on 2026-10-20 for batch 4. **Experimental evidence, not shipped
behaviour or an owner-approved look.** No production code or tests changed.

- Review page:
  `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-design/probe-1/page/index.html`.
  Its SHA-256 is
  `658528cf4b9707e8d7ba658a0cd9241c101717ecdf656895fb554a6c32c4029f`.
- The folder holds `capture.sh`, `settings.yaml`, `compare.py`, input
  palette/library snapshots, raw captures and a complete hash manifest.
  `manifest.json` SHA-256:
  `09e3634d6a0f7663ba4fb6f9fae8a6ba3aea57aec9f2aea547c50b9522b630b3`.
  `compare.py` SHA-256:
  `5419eecaf16078e2a8bb2d3eb7ad570ab0af61ce31218ce42e4ab1ed3c7befc1`.
- Capture uses repository code unchanged from `6c5f47a1293cc8a99b25d5e6e360bfd3536ab320`,
  through the existing acceptance environment (NumPy 2.5.3, Pillow 12.3.0).
  Both commands ran under the shared Blender lock with a local settings
  file replacing the user configuration. The backend ran headless.
- Fresh robot capture: Walking, 12 samples × 4 directions, 96×128 cells at
  supersample 4. Fresh shrub capture: one Sway sample and direction, same
  cell and supersampling. Both commands exited 0 without warnings. The first
  preflight attempt failed on absent output directories, before rendering;
  its log is retained and the command script creates the directories now.
- Inputs are the existing acceptance robot and shrub, and snapshots of the
  owner's palette and their review libraries. No input/configuration changed.
  For Q-11 only, the robot's Main material is deliberately assigned a teal
  ramp `[50,52,53]` in the prototype to distinguish library-base and model-base
  colour. Other panels use its original library. Bark and soil use a
  probe-only range `[110,190]` to expose form; these are not proposed project
  settings or a continuation of the parked shrub-library tuning task.
- The probe selects a winning material per output pixel, averages its
  captured shade and normal-facing terms, then applies the candidate colour
  rule. Key direction points toward `(-.6,.7,.7)` in camera coordinates,
  normalised. Sky/ground use subject up transformed through the unrolled
  30-degree camera; that coordinate choice is an experiment, not a decision.
- Verified locally: 48 robot frames and one shrub frame; no translucent
  fronts; unchanged alpha across variants; ramp/dither colours stay in the
  palette; motion GIFs have 12 frames; local page references exist. Sampled
  motion frames and the colour comparisons were visually inspected. GIFs use
  one palette per animation, no GIF dithering, and 100 ms/sample for review;
  the exact prototype colours are in the PNGs.
- Limits: no translucent-layer demonstration, no texture fallback exercise,
  no perspective or roll comparison, and no proof of animation quality from
  the mechanical checks. The owner judges the motion. Production sampling,
  formulas, settings and error contracts remain open until selected below.

### Probe 2: selectable patterns and brightness palette policy

Local comparison prepared on 2026-10-20, reusing Probe 1's unchanged captures
and function definitions without rerunning Blender or changing production code:

- Page: `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-design/probe-2/page/index.html`.
  SHA-256: `6d8dd0afbdedb4a1894cae81da2f789878bcd322aac3bd86de1d4b05feed4e17`.
- Prototype: `~/.local/share/moskophoros-acceptance/shading-design/probe-2/patterns.py`.
  SHA-256: `fcf44a52eee91d9290d4f24e6f80b15d419b2f995dfd44525a409cf93385039c`.
- Manifest: `~/.local/share/moskophoros-acceptance/shading-design/probe-2/manifest.json`.
  SHA-256: `a8ade30cfe8f048d975ae6c0d8ad1793cd695dbd1896603096dc82fbff7b7003`.

Six fixed threshold tiles are compared: ordered 2×2, 4×4 and 8×8, clustered
4×4, diagonal 4×4, and shuffled 8×8. The last is one recorded permutation,
not blue noise or fresh randomness. Every tile contains each threshold rank
once; exact matrices are in the manifest. The page offers strengths 0.5 and
1.0, a no-dither reference, twelve robot Walking samples and a static shrub,
all at direction 0. Cell-pixel anchoring and all earlier numerical settings
are unchanged. Each robot pattern animation was checked to have twelve
frames. The earlier prototype, page and manifest were checked unchanged.

The brightness pair compares calculated colours against a final palette
snap. That snap changes 4,966 visible robot pixels and 4,141 visible shrub
pixels in the first sample. PNGs carry the prototype colours; GIF palette
limitations remain as in Probe 1. Static links and generated image files
were checked, and representative PNGs inspected; no browser was opened.
These opaque/cutout probes do not validate translucent composition,
perspective or camera roll. No repository tests were run. The page asks
three contract questions below; none is a decision until the owner answers.

### Probe 3: material-ramp versus whole-palette snap

Prepared on 2026-10-20 to clarify D-18's requested setting, using Probe 1's
unchanged raw captures and brightness formula. No Blender invocation,
production edit or owner-configuration change:

- Page: `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-design/probe-3/page/index.html`.
  SHA-256: `a817e019a90ca277f556a7e7c0c6afa243e5ab2d111e44fb8a4814971e919515`.
- Prototype: `~/.local/share/moskophoros-acceptance/shading-design/probe-3/snap.py`.
  SHA-256: `1c273a915c5e11285f878abb7db752270e5ee50897a12bcb857722332ddf33db`.
- Manifest: `~/.local/share/moskophoros-acceptance/shading-design/probe-3/manifest.json`.
  SHA-256: `ef3b390093e746f6496470bd89f30e0be1b468478c9e4eae4438433b7c0db109`.

Each subject has three labelled PNGs: no snap, nearest colour in the winning
material's own ramp, and nearest colour in the whole palette. Both snaps
use the current OKLab distance and earlier-entry tie rule without dithering.
The two snap targets differ at 4,044 visible robot pixels and 2,563 visible
shrub pixels. Alpha equality and material-ramp membership were checked;
representative PNGs were inspected. Probe 1's page/manifest and Probe 2's
page hashes remain unchanged. These static opaque/cutout examples clarify
the target using existing short ramps; they do not decide a project look,
test longer authored ramps, or verify translucent behaviour. No repository
tests were run.

### Probe 4: sky frame and brightness range

Prepared on 2026-10-20 from Probe 1's immutable captures, without a new
Blender run, production edit or owner-configuration change:

- Page: `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-design/probe-4/page/index.html`.
  SHA-256: `94782a1439904b32498d0b908370ef376f8eaadb4f87f56d5c31dd9ebec03ef4`.
- Prototype: `~/.local/share/moskophoros-acceptance/shading-design/probe-4/lighting.py`.
  SHA-256: `7d1ea7bad7813896cbee222bf2f5549d8f50090a07a1adfaf73c631c37773aca`.
- Manifest: `~/.local/share/moskophoros-acceptance/shading-design/probe-4/manifest.json`.
  SHA-256: `43061a871662d2af175dd96a0c11c6ff1a18cf1f5feb3f356dce871e504857c7`.

The sky comparison isolates `e = a * (.20 + .80 * sky)` and uses the
existing ramps, with key/ground off. It contrasts camera screen-up with
subject/world up, unrolled and at a mathematically transformed 90-degree
clockwise roll. The latter rotates cell pixels exactly and changes the
camera-up facing vector from original `(0,1,0)` to `(-1,0,0)`, consistent
with `views.camera_basis`; it is not a new capture or an end-to-end roll
test. World-up colours were verified to rotate exactly with the subject,
and both frame choices retain identical alpha.

The brightness pair keeps Probe 1's original ambient/light signal and
changes only the brightness ceiling: gain `.30 + .70*e` versus
`.30 + 1.70*e`, with output channels clipped to white. The first frame
changes at 4,573 visible robot pixels and 3,790 visible shrub pixels.
Dithering and snap are off. Representative PNGs were inspected. These
opaque/cutout illustrations are not project defaults, acceptance of a
look, or verification of perspective/translucency. No repository tests ran.

### Probe 5: snap-dithering algorithm

Prepared on 2026-10-20 from Probe 1's unchanged captures, using twelve
Walking samples at direction 0 and one shrub sample. No new Blender run,
production edit, owner-configuration change or repository test:

- Page: `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-design/probe-5/page/index.html`.
  SHA-256: `623ec674cb169014a53334fab336d3e6e917e8d7e48cf7b7a584514f18ba0db4`.
- Prototype: `~/.local/share/moskophoros-acceptance/shading-design/probe-5/snap_dither.py`.
  SHA-256: `30a42a0661895b020c7b6a0387ab90518d65b7538adb7a49edc7c0fe57a3db77`.
- Manifest: `~/.local/share/moskophoros-acceptance/shading-design/probe-5/manifest.json`.
  SHA-256: `36f215a6f300000293bd5263b1989a895a09aa5ff877cc4124516b84e1bfd9ff`.

For brightness and both, and for each snap target, compare undithered
nearest colour with two candidate algorithms. A uses the two nearest
allowed colours in OKLab. B anchors the nearest colour and searches all
partners for the segment with the least squared approximation error.
Both project the desired colour onto the chosen segment, clamped to that
segment, to obtain the second-colour fraction `t`. The ordered 4×4 tile
chooses the second colour when its threshold is less than `strength*t`.
Strengths 0.5 and 1 are displayed. Intermediate ramp selection is undithered.
Stable ties follow target order; identical colours are deduplicated keeping
the first occurrence, and a one-colour target remains constant.

Assertions check target membership, unchanged alpha, strength zero matching
the existing nearest-colour mapping, and twelve frames in the representative
robot GIFs. All 26 page links and all strength-switch image variants exist.
Representative PNGs were inspected. Prior probe page hashes are unchanged.
The comparisons use the earlier experimental light and short ramps, not new
project defaults. GIFs retain their earlier shared-palette limitations;
PNGs show exact opaque subject colours. These samples have no translucent
fronts and do not verify the proposed composite ownership rule below.

## Desired experience and settled scope

The owner chooses project settings to generate either:

1. Eight-direction, high-angle isometric sprites, no outline, with internal
   ambient colour variation and geometry maps for live lighting.
2. Straight-on panels with lighting baked into material ramps, without an
   additional brightness multiplication for that project.

The tool also supports brightness shading, the combination, and neither
shading operation. All four modes belong in settings (D-5). These are generic
controls, not game-specific code or shipped presets. Key, sky and ground
terms are independently switchable (D-9); a project supplies defaults and
materials can override their mode and shading response (D-10).
The already accepted camera capability is reused, not redesigned.

The original design assignment wrote this document only, with local evidence
probes allowed by its dispatch. The round 2 processing handoff now authorises
tracker drafts and, after individual signoff, issue creation and ledger
updates. Production code and repository tests remain outside this assignment.
The Codekarl repository is not an input and must not be read. Its palette
and project file come after this design.

## Decisions

Decisions are chronological. The resolved Q entries and implementation
contracts incorporate later answers to details left open by earlier entries.

### D-1. Serve both live-lit sprites and baked panels

Owner, 2026-10-19 16:31 UTC, typed in the earlier review worker's pane;
quoted in the handoff and relayed in the dispatch identified in *Source
notes*:

> "i should be able to set it one way to give me 8 direction, high angle isometric, flat no-outline with the internal ambient shading, sprites like the ones we have been generating, with corresponding 3d facemaps to fit into my shaders for live real-time lighting. it also needs to be set up to generate art for my other game, its 2d characters and objects stright on view with the lighting baked in to give a sense of works of art."

This settles the two uses. It does not settle which light terms to bake or
their numerical combination.

### D-2. Ramp shading without brightness changes, and a combined option

Owner, 2026-10-19 16:41 UTC, same arrival and provenance as D-1:

> "yes, and there are multiple ways i want to do it. for the second game, there should be no brightness changes, all shading is color ramp, but the ability to shade objects with both, is something i would like to include for other purposes."

The dispatch initially named three ways. D-5 settles their routing and adds
the fourth, neither. The earlier worker's reading was not itself a decision.

### D-3. Rendering settings and palettes belong to projects

Owner, 2026-10-19; time not recorded in the supplied dispatch. Its quoted
words are also recorded in projects and camera D-1:

> "the actual rendering settings should all be project specific. the palette too is going to be very different"

The projects and camera design already settles the layering and the generic
tool boundary. Its implementation and acceptance settle the handoff's
questions about introducing settings files and configuring the view.

### D-4. The light stays fixed to the camera

Owner, 2026-10-19; time not recorded in the cited relay. Projects and camera
D-8 records the explicit correction:

> "2) i misspoke, i was right the first time, source is fixed with the camera."

Provenance: `relay-camera-batch1.md`, SHA-256
`61119c8213288c1866d9d0d6442381b8e27523c3a2c9afd71b29eaaa6eaf4fbd`,
cmux relay `bbba403e-cdfe-496c-8ae3-b473c9b871e6`.
This is settled and is not being reopened.

### D-5. Four modes route the complete chosen shading signal

Owner, about 2026-10-20 19:37 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`ae3ad3ce-e442-4abd-92fb-f51fb3f858de`, answering batch 1 message
`w8y5pdsiqbn56f33gpftcxhsmi`:

> "1) A, but i want to make sure you know that we need to support all 4 modes, ramp, brightness, both, and neither, its all needs to be in the settings."

This resolves Q-1's routing, with the owner's addition:

| Mode | Operation on the complete chosen shading signal |
|---|---|
| Ramp | Choose ramp entries without multiplying their RGB |
| Brightness | Scale an unshaded base colour, without shade-driven ramp selection |
| Both | Choose a ramp entry, then scale its RGB |
| Neither | Apply neither shade-driven ramp selection nor brightness scaling |

Ambient form and optional light are included in the selected routing; this
is not a switch for the added light alone. All four modes must be expressible
in settings. D-10 subsequently approves per-material overrides. The setting
name, exact shipped value, base colour, missing-ramp behaviour and numerical
formula are not yet decided; D-8 constrains the defaults to preserve today's
images.
In particular, neither is not a name for today's ambient ramp look: that
look already uses ramp shading. Palette mapping and model texture handling
must be specified separately from these shading operations (Q-11).

### D-6. Bake controls and preview light are separate

Same date, time, arrival and relay as D-5. The owner's answer to Q-2 was:

> "2) A"

- Bake controls are separate from today's `--light`.
- The regular preview shows the exported colour result, subject to the
  existing preview scaling, background blending and GIF colour limits.
- `--light` explicitly adds a live-light simulation over that result, even
  when it already contains baked shading. This deliberate combination is
  allowed; baking does not silently request it.
- Normal and depth maps remain geometry, unaffected by the lighting controls.

This resolves Q-2. Existing map output switches remain independent.

### D-7. Update the existing sheets with the settings update

Same date, time, arrival and relay as D-5. The owner's answer to Q-3 was:

> "3) i shouldnt have very many sheets, you can update them all with the settings update for now"

The owner authorises updating the existing sheets with the settings update.
This answer alone did not select a regeneration procedure, JSON-only
conversion, old-schema loading support or the exact default-image guarantee.
D-8 settles those details after an explicit follow-up. No sheet is changed
during design.

The manager separately suggested reading this as no migration code plus
regeneration at the schema bump, and explicitly marked that interpretation
non-binding. It became an owner decision only through D-8's explicit approval.

### D-8. Preserve default images and regenerate working sheets once

Owner, about 2026-10-20 19:42 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`d44ba361-bf3c-4e8e-91a2-e59e2aeccd33`, answering batch 2 message
`67tefmibchfh673kt62jphjyq6`. The full answer was:

> "3) A, 4) A, 5) A"

The first answer approves Q-3's follow-up recommendation and resolves Q-3:

- New directional terms are off by default. Existing resolved settings keep
  today's look and byte-identical colour sheets, maps, regular previews and
  lit previews, including ordinary materials.
- New recorded settings change the JSON and fingerprint and require a sheet
  schema bump. Only the current schema loads; no older-schema loader or
  one-off JSON conversion is added.
- Regenerate all the owner's existing working sheets once when the new
  settings/schema land. First inventory them and their reproducible inputs;
  preserve historical acceptance artifacts as evidence. Assign this work in
  the delivery plan, rather than assuming it has happened.
- A new sheet must reproduce byte-identically through `--settings-from`.
- There is no automatic project-file edit during design.

The exact schema number and library changes follow the complete design.
Preserving today's look does not equate its ambient ramp shading with neither.

### D-9. Key, sky and ground are independently available

Same date, time, arrival and relay as D-8. The owner's “4) A” approves
Q-4's availability recommendation:

- Support key light, sky and ground terms, each independently switchable,
  alongside existing occlusion and curvature.
- A project need not enable every term.
- This selects available controls, not their weights, coordinate frames,
  formulas or final appearance, nor whether the live-lit project uses sky.

Q-4 remains open for those details. Key-only was not selected as the arc's
scope. The key stays fixed to the camera under D-4.

### D-10. Project defaults with material response overrides

Same date, time, arrival and relay as D-8. The owner's “5) A” approves
Q-5's ownership recommendation:

- The project supplies a default mode and shared light arrangement.
- Each material may override its mode and shading-response strengths in its
  library entry. Thus a glow can stay unshaded beside a shaded body.
- The light arrangement is shared; this does not introduce separate light
  positions for each material.
- Enumerate the exact response fields after settling the terms. Inheritance,
  validation, ordinary-material entries and inline reuse remain to specify.

This resolves Q-5's ownership choice, not its full schema. Uniform-only
controls were not selected.

### D-11. One distant key, controlled by a camera-relative direction

Owner, about 2026-10-20 19:46 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`35757489-cc29-456a-a840-3a702ec80cb3`, answering batch 3 message
`5eijvs26h8vy3b9iqnyztgwh4i` (Q-4 key control, Q-6 timing, Q-7 outlines):

> "A for all is fine"

The Q-4 recommendation is approved: one distant bake key set by a direction
vector in camera coordinates. Its incoming direction is uniform across the
subject; there is no bake-key distance to tune. The preview point light
remains separate and available (D-6). A point bake key and selectable
point/distant bake types are outside this arc. The vector convention and
intensity remain to specify; this does not choose the final look.

### D-12. Include optional dithering, off by default

Same answer and provenance as D-11. The Q-6 timing recommendation is
approved: dithering belongs in this arc and is optional, off by default to
preserve D-8. Its pattern, affected transitions and stability through motion
must be chosen from labelled comparisons before design readiness. No pattern
or algorithm is approved by this decision.

### D-13. Defer outlines to a separate style arc

Same answer and provenance as D-11. The Q-7 recommendation is approved:
outlines are outside this delivery and wait for a separate style arc. This
arc covers shading and dithering. The live-lit use remains outline-free;
no outline algorithm or appearance is selected for the baked use here.

### D-14. Ramp-mapped materials keep their library base colour

Owner, about 2026-10-20 20:02 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`ba055c23-a81e-43c6-b64e-8e3ab9b60301`, answering batch 4 message
`2rnvusxti2arq8azwejcumt8z2`. The owner's complete answer was:

> "1) A, 2) A, 3) i want to choose the pattern, and perhaps even more than just those 2"

The first answer approves Q-11's base rule:

- In brightness and neither, a ramp-mapped material takes the ramp's
  last/lightest palette entry as its unshaded base.
- An ordinary material keeps its captured unlit model colour/texture.
- Turning off ramp shading does not discard a library's material colour.

This selects a behaviour, not the example's teal colour. Missing-ramp
handling and palette/composition policy remain in Q-11.

**Visual provenance for D-14 to D-16:** the manager reports that the owner
judged a simplified page at
`~/.local/share/moskophoros-acceptance/shading-design/decide-batch4/index.html`,
SHA-256 `bfd29db2aefe3bff99a651ce465d56a7d010d01d346e509b0856376b3b2929aa`.
All 21 referenced images were verified byte-identical to Probe 1's originals.
The page restates the same A/B choices and describes the images as rough
tests, with strengths to be tuned later.

### D-15. Multiply ambient form by the lighting factor

Same answer and provenance as D-14. The owner's “2) A” approves the
multiplicative family from Q-4: ambient form is multiplied by the light
factor, so directional light does not erase a deep crease. The weighted
average alternative was not selected. The probe's particular weights,
brightness endpoints and project look are not defaults; their controls and
precise arithmetic still need a contract.

### D-16. The owner wants a choice of dither patterns

Same answer and provenance as D-14. The owner's third answer is:

> "3) i want to choose the pattern, and perhaps even more than just those 2"

Do not freeze the design to the proposed 4×4 pattern. Keep a choice of
patterns, with additional possibilities to present. The exact catalogue,
how it is selected in settings, custom-pattern support and anchoring are
still to settle through Q-6 and labelled renders.

The manager suggested a user-selectable pattern setting and explicitly
marked that reading non-binding. Batch 5 makes that proposed interface and
its offered patterns explicit rather than treating one pattern as accepted.

### D-17. Six selectable dither patterns, strength and material overrides

Owner, about 2026-10-20 20:16 UTC, typed directly in the manager's terminal
after viewing Probe 2; relayed by mosk-manager in cmux message
`20dc14aa-e207-4c00-8fcb-33c26f9ca4ec`, answering batch 5 message
`jjbdta8qj7fjkd5xp6gqfvzc2s`. The complete answer was:

> "1) A, 2) A is default but i want a color ramp snap option in the settings, i feel like it could look good with a much larger color ramp than these examples 3) A"

The first answer approves all six named Probe 2 patterns: ordered 2×2,
4×4 and 8×8, clustered 4×4, diagonal 4×4 and fixed shuffled 8×8. Offer
off, configurable strength and material overrides. Keep the displayed
cell-pixel anchoring; moving surfaces pass through the fixed pattern.
Dithering remains off by default. Further named patterns can be added
later; custom threshold-tile files are outside this arc. This settles
D-16's catalogue question, not a project's chosen pattern or strength.

### D-18. Off-palette brightness by default, with an optional snap setting

Same answer and provenance as D-17. The second answer approves A as the
default: brightness and both may produce off-palette colours; ramp-only
and neither keep the existing palette rules. Mixed translucent composites
remain off-palette when a contributing layer uses brightness/both, with
the existing palette snap otherwise. Alpha and geometry maps stay unchanged.

The owner additionally requires a "color ramp snap option in the settings"
and suggests that a much larger ramp could look good. Record that capability
as required, without interpreting it as a selected look, a specific ramp
size, or approval of the whole-palette snap displayed in Probe 2. Q-11 must
clarify the snap's target (material ramp versus whole palette), placement,
mixed-layer behaviour and handling of materials without ramps. The earlier
B-only alternative is not the default; optional snapping is now in scope.

### D-19. Retain each layer's normal and shade before composition

Same answer and provenance as D-17. The third answer approves retaining
the already-computed back and front normals, shading each colour layer
separately, then using existing composition. Preserve the accepted combined
front approximation represented by its front-most material/direction,
alpha and exported geometry maps. Deferring this extension and rejecting
directional baking on translucent input was not selected. This extends
captured data and validation, without inherently requiring another render.
Buffer formats, sampling and verification remain to specify in Q-8. The
chest must exercise the result; opaque/cutout probes are not that evidence.

### D-20. Offer both snap targets, with off as the default

Owner, about 2026-10-20 20:44 UTC, typed directly in the manager's terminal
after viewing Probe 3; relayed by mosk-manager in cmux message
`f31db19c-e69e-4355-b089-675413f7601b`, answering batch 6 message
`4swxhvrx6gwizmkgdv42qjviqi`. The complete answer was:

> "1) C, i like both 2) the whole palette, either way, 3) A"

The first answer selects C: offer off, material-ramp snap and whole-palette
snap. Off remains the default. Material-ramp snap selects from the layer's
own ramp after brightness and before composition; translucent blending can
leave those ramps. Whole-palette snap applies after composition and may
select any palette entry. This settles the targets and their basic
placement, not mixed material override precedence or dithering with snap.
The owner viewed examples with existing short ramps; no project ramp size
or colour scheme is being selected here.

### D-21. Use the whole palette when snapping without a material ramp

Same answer and provenance as D-20. The second answer is:

> "2) the whole palette, either way"

Use the whole palette as the snap target when a material has no resolved
ramp, whether material-ramp or whole-palette snap was requested. The
material-specific missing-ramp error proposed as batch 6's A is not the
requested behaviour. Do not infer that the whole palette is itself an
ordered shading ramp: the answer may reach beyond snap fallback into
ordinary shading, and Q-11 asks that distinction explicitly before adopting
the earlier ordinary-mode proposal. Existing library defaults can supply a
resolved ramp. Validation when no palette exists also remains to state.

The manager suggested reading the answer as B, and explicitly marked that
interpretation non-binding. The original words and the unresolved extent
of "either way" are preserved here rather than treating that suggestion as
an additional owner decision.

### D-22. Keep the arc to the agreed shading, dithering and snap controls

Same answer and provenance as D-20. The third answer selects A: cast
shadows, coloured lights, multiple key lights, specular highlights and a
command to recolour retained captures are outside this arc. Outlines remain
deferred under D-13. Existing ambient occlusion remains in scope; excluding
new cast shadows does not remove it. Delivery order still needs signoff once
the remaining behaviour and verification contracts are settled.

### D-23. Whole-palette fallback applies to snap, not an invented shading ramp

Owner, about 2026-10-20 20:50 UTC, typed directly in the manager's terminal
after viewing Probe 4; relayed by mosk-manager in cmux message
`066ddb06-09d7-4668-b1eb-1ea044eb7fa2`, answering batch 7 message
`44ggxjrpc5r923cgqn8t7vq5en`. The complete answer was:

> "1) A, 2) C, 3) A"

The first answer resolves the extent of D-21: whole-palette fallback applies
only to snap. Without a resolved material ramp, ramp mode retains ordinary
colour/texture, both applies brightness to that ordinary colour, and either
enabled snap target uses the whole palette. Do not treat the palette as an
ordered shading ramp. This preserves the ordinary path rather than
manufacturing ramps or discarding texture. Missing-palette validation
remains to state in the settings contract.

### D-24. Selectable camera/world sky frame, defaulting to camera

Same answer and provenance as D-23. The second answer selects C: sky/ground
frame is selectable between camera screen-up/down and subject/world up/down,
with camera as the default. Camera-frame terms follow camera roll; world
terms do not. The key stays camera-fixed under D-4 in either case.

The choice explicitly approves a narrow exception to V-7's camera-fixed
lighting principle when sky/ground use world frame. That exception must be
recorded in the owning vision/implementation contracts during delivery;
this design-only assignment does not change those documents. Neither a
camera-only nor a world-only interface was selected. This does not select
sky/ground strengths or enable either term for a particular project.

### D-25. Brightness gain stays between zero and the base colour

Same answer and provenance as D-23. The third answer selects A: configurable
brightness floor and ceiling both lie in `[0,1]`, with floor no greater
than ceiling. Scale linear RGB; brightness can darken or restore the base
but cannot brighten beyond it. These gain controls affect brightness/both;
ramp selection still selects its existing entries. A ceiling above 1, shown
with 2 and proposed up to 4, was not selected. Exact interpolation, shipped
endpoint values and inheritance remain for the complete settings contract.

### D-26. Directional strengths share a unit budget; ambient form can be bypassed

Owner, about 2026-10-20 21:55 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`18e15fc0-f95f-4d00-a1fd-99a49ef236b6`, answering batch 8 message
`t34mq5fvgajcxfzw9yngjqqm2a`. The complete answer was:

> "1) A, 2) B, 3) A"

The first answer selects A: nonnegative key/sky/ground strengths `K/S/G`
each at most 1, with total at most 1. Zero disables that term; the remaining
budget supplies uniform light. For nonnegative facing terms `k/s/g` in
`[0,1]`, `L=(1-K-S-G)+K*k+S*s+G*g`. Defaults are all zero, giving `L=1`.
Reject an excessive total rather than silently normalising it. A separate
uniform-floor control with independently saturating weights was not selected.

Keep `e=a*L`. An ambient-form on/off control defaults on; off substitutes
`a=1`, allowing directional shading without ambient form. Brightness gain
is `floor+(ceiling-floor)*e`, with D-25's bounds. Sampling, precision and
the exact legacy-compatible ramp path still need specification. The formula
does not authorise changing default image bytes under D-8.

### D-27. Dither snap quantisation, without dithering the intermediate ramp too

Same answer and provenance as D-26. The second answer selects B: include
dithering of optional snap quantisation. With snap enabled, dither the final
colour choice instead of both intermediate ramp selection and its later
snap. Without snap, shade-driven ramp selection remains the dither target.
Continuous brightness without snap and neither mode receive no artificial
noise. Ramp-only dithering with always-undithered snapping was not selected.

This is a capability decision. The promised labelled snap-algorithm
comparison and material-override rule for composited pixels are still needed
before selecting that algorithm or declaring a look accepted.

### D-28. Snap target is shared by the export/project

Same answer and provenance as D-26. The third answer selects A: one snap
target setting inherited through the normal export/project settings layers,
with no per-material target override. Already approved material mode,
response and dither overrides remain available. The alternative of a
material's whole-palette request forcing the final composite to snap was
not selected. File syntax and missing-palette validation remain to specify.

### D-29. Two-nearest-colour snap dithering and a unit strength range

Owner, about 2026-10-21 00:48 UTC, typed directly in the manager's terminal
after viewing Probe 5; relayed by mosk-manager in cmux message
`8587a525-f617-4a48-81da-289fe90cd6f7`, answering batch 9 message
`ms3nau3wnydkdw35azsub3hr62`. The complete answer was:

> "A on all three"

The first approval selects Probe 5's two-nearest-colour algorithm. Use
OKLab distance to choose the two nearest distinct allowed colours, project
the desired colour onto their segment and clamp the second-colour fraction
to `[0,1]`. Choose that second colour where the selected tile's threshold
is less than `strength*fraction`; otherwise choose the nearest. Stable
ties follow target order. Deduplicate identical colours by first occurrence;
a one-colour target remains constant. The best-partner-segment search was
not selected.

Dither strength is finite `[0,1]`, default 1 when a pattern is chosen;
the pattern stays off by default. Strength zero uses the undithered path.
This selects the algorithm and strength contract, not a project's chosen
look. Shade-driven ramp sampling still needs its complete specification.

### D-30. The visibly dominant layer controls composite dithering

Same answer and provenance as D-29. For whole-palette snap at a pixel with
both layers, choose the layer with the greater visible contribution using
the existing front and transmitted-back weights summed over the output
pixel; tie to front. Use that layer's winning material, pattern, strength
and mode's no-dither rule, including neither. One-layer pixels use their
own material controls. Always-front and project-only mixed-pixel rules were
not selected.

Own-ramp snap remains per layer. A missing-ramp fallback changes its allowed
colour set to the whole palette, not its placement. This ownership contract
must still be verified on translucent evidence; opaque/cutout probes do
not establish its visual quality.

### D-31. Separate owner visual review, then regenerate working sheets

Same answer and provenance as D-29. Reserve a separate owner visual-review
slice after mechanical validation. Use the robot for motion, shrub for
cutouts and chest for translucency. Cover the live-lit eight-direction
isometric use and straight-on baked panels, including perspective/roll,
four modes and representative dithering/snap combinations. Include a longer
generic ramp example to exercise D-18 without depending on the second
game's not-yet-authored palette.

Actual live-lit sky strength and other project look values are deliberately
open until that review, which must stop for the owner's visual acceptance.
Preserve current project settings until review; neither passing tests nor
these design probes select project tuning. After acceptance, inventory and
regenerate working sheets under D-8 while preserving historical evidence.
Detailed delivery boundaries and ordering still need signoff after the
remaining data/settings contracts are settled.

### D-32. Settings names, defaults, validation and persistence

Owner, about 2026-10-21 00:57 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`c7d58503-9365-4b09-88be-2c82dbc04920`, answering batch 10 message
`znwjdat3za8bvp872zif42y8ra`. The complete answer was:

> "A, A, A"

The approval names the reviewed contracts file
`~/.local/share/moskophoros-acceptance/shading-design/batch-10-contracts.md`,
SHA-256 `e8aa954b2bd86bdcec0ae81d8699fb0cc81f292753d33eec34450485f7b180c2`.
The manager summarised it beforehand, specifically calling out snap applying
only to brightness/both and library values taking precedence over CLI values.

The first A approves contract 1 in full, reproduced under *Implementation
contracts*: exact settings/CLI names, defaults, direction convention, strict
validation, palette requirements and recorded reuse. Earlier provisional
defaults are superseded by this table. Current-schema-only sheet loading
and unchanged default image bytes remain required.

### D-33. Library version 4 and response inheritance

Same answer and provenance as D-32. The second A approves contract 2 in
full: `/4` library shape, continued `/2` and `/3` reading, ordinary entries
with response overrides, material > library > global response precedence,
cross-field validation and warnings. Retain the existing palette prerequisite
for libraries. This amends the older rule that ordinary entries cannot
carry shading values, without changing what old libraries render by default.

### D-34. Sampling, snap applicability and addressed layer normals

Same answer and provenance as D-32. The third A approves contract 3 in
full: optional snap operates only on brightness/both, the specified
mean/vote and dither arithmetic, exact integer compatibility path, layer
composition rules, addressed normal buffers and validation. Ramp-only
retains ramp dithering; neither stays unshaded and undithered. Shading never
changes alpha or exported geometry maps. D-31's later visual acceptance
remains mandatory; this contract approval is not acceptance of unimplemented
output or readiness signoff on the delivery plan. D-35 subsequently supplies
the delivery-plan and readiness signoff.

### D-35. Delivery plan and design readiness

Owner, about 2026-10-21 01:49 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`793d365b-4cca-4173-aab7-47d98d33ee46`, answering batch 11 message
`wnjw5kij527hz293d6w7amz2ke`. The exact answer was:

> "sounds good to me, i approve this plan"

The approval names the reviewed delivery plan
`~/.local/share/moskophoros-acceptance/shading-design/batch-11-delivery.md`,
SHA-256 `58f448621c2bb523fdd98acf2f05ff4e67d28fefd880280641a12881d764f990`.
The manager summarised the eight slices beforehand and explained the next
steps: design review, then `process-design-doc` for the epic and children,
then child approvals, with no solving without the owner's word.

The owner approves SHD-1 through SHD-8, their stated dependencies and
readiness for issue processing. The manager directs recording the signoff,
marking the design ready, publishing it and reporting completion. This
completes the design assignment. Design review comes next; later processing
requires the manager's instruction, with the epic and then one child per
invocation receiving separate approvals. Actual project look values remain
deliberately deferred to owner visual acceptance in SHD-7, followed by
SHD-8's regeneration. No implementation or tracker mutation is authorised
by this design signoff.

### D-36. Clamp raw shade before continuous normalisation

Owner, about 2026-10-21 02:07 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`97680a2f-1e3c-483a-994f-ff214e08ff1b`. The exact answer to the four
review-round-1 recommendations was:

> "i approve all 4 reccomendations, A for all"

The manager presented S-14 first: clamp the mean to `[lo,hi]` before
normalising in the continuous path, matching today's integer path so long
ramps have no top-band jump. The first A approves that correction to D-34.
Use `a=(clamp(mean_shade,lo,hi)-lo)/(hi-lo+1)` for plain reduction;
mode reduction uses the same range mapping for each sample. Ambient bypass
still sets `a=1`, and the exact legacy integer path stays intact. SHD-3 owns
the correction and long-ramp boundary evidence; SHD-4/SHD-5 use that signal.

### D-37. Transport one extra normal buffer and measure its cost

Same answer and provenance as D-36. The manager's second recommendation,
S-16, transports only `back_normal` and derives the front from the existing
`normal` plus front presence. The second A approves this change to D-34's
two-extra-buffer transport, while preserving both addressed layer normals
at the stylize boundary. SHD-1 reports measured capture-time and
work-directory cost on the robot and chest; no extra ray-traced render is
needed. Exported `normal` and `depth` remain unchanged.

### D-38. Accept exact owner-file diffs, then authorise their application

Same answer and provenance as D-36. The manager's third recommendation,
S-7, requires SHD-7's acceptance record to give the exact diff for each
owner file. The owner's verdict authorises the SHD-8 agent to apply exactly
that diff; SHD-8 records before and after hashes. The third A approves this
procedure. It does not choose project values now or authorise edits beyond
the later accepted diffs. A changed source file or a required additional
edit returns to the owner instead of expanding the accepted diff.

### D-39. Move internal parsing and warnings into SHD-2

Same answer and provenance as D-36. The manager's fourth recommendation,
S-10, moves the two-level reader, gated `/4` parser and warning builders
into SHD-2, leaving SHD-6 wiring, schema activation, reuse and evidence.
The fourth A approves these revised boundaries and publishing the narrative
amendments with `docs-push` as a named step after SHD-6 merges. Test-read
`docs/design.md` remains in the corresponding code PR. The eight slice IDs,
titles and dependencies stay unchanged. This is the explicit exception to
the usual pre-final-review timing for these narrative amendments.

Together D-36 to D-39 settle all four review holds. The manager directs
restoring the document to ready, landing revision 1 and reporting status.
Independent re-review is still required by the approved process; readiness
does not authorise tracker creation or implementation.

### D-40. Keep the shared signal and document its brightness cap

Owner, about 2026-10-21 02:20 UTC, typed directly in the manager's terminal;
relayed by mosk-manager in cmux message
`7539e167-f7ee-4d84-acf4-9029abe13103`. The exact answer to S-20 was:

> "A"

The manager presented A as keeping D-36 unchanged, stating that brightness
gain tops out below the ceiling while ambient form is on, and adding a
narrow-range SHD-3 fixture. B would normalise gain separately. The owner
selected A: no separate gain normalisation. With ambient form on,
`a <= (hi-lo)/(hi-lo+1)` and `L <= 1`, so maximum gain is
`floor+(ceiling-floor)*(hi-lo)/(hi-lo+1)`. This is below the ceiling when
floor < ceiling, with a gap of `(ceiling-floor)/(hi-lo+1)`; equal endpoints
remain constant. Ambient bypass can reach the ceiling at `L=1`. This
clarifies D-25's restoration wording; it does not raise the allowed ceiling.
SHD-3 verifies a narrow-range brightness case as well as long-ramp bands.

### D-41. Only options and project files trigger shadow warnings

Owner, 2026-10-20 (2026-10-21 UTC), typed directly in the manager's
terminal; relayed by mosk-manager for request `moskophoros-20261020-1` in
`~/.local/state/project-manager/moskophoros/dispatch-shading-amend-41.md`,
SHA-256 `f0dd42748fe2e8e526091464fb3ec059de609d835e55d3a8d609c71afc6e0316`.
The manager asked:

> Should values in your global config file trigger "ignored value" warnings?
> A (recommended): keep today's rule. Only options and the project file warn, for the new shading settings and the existing ones alike. The issue and the design's wording get corrected, with a dated note.
> B: make the global file warn too.

The owner's answer, verbatim:

> "A"

Only an explicit command-line option or a project-file value triggers a
shadow warning when a library/material value takes precedence. The global
file, its `--config` replacement, shipped defaults and a reused sheet are
not warning events. This applies to new response fields and existing fields
alike, preserving existing behaviour. It corrects contract 2's inclusion
of `--config`, introduced during round-1 S-18 and identified by the #143
issue review; it does not change value precedence or validation.

### D-42. No working sheets exist yet

Owner, 2026-10-21, typed directly in the manager's terminal; relayed by
mosk-manager for request `moskophoros-20261020-1` in
`~/.local/state/project-manager/moskophoros/dispatch-shading-d42.md`,
SHA-256 `f1953b0f26069b9e5d2cfd47c0b87dd4518c21ad9e4e8d8cfdfbdf16bdf823c4`.
The manager asked:

> Which of your existing sprite sheets count as "working" sheets? (The manager searched the machine: almost every moskophoros sheet is a review or test render under ~/.local/share/moskophoros-acceptance/; 8 early robot sheets in ~/Documents/Codex/ from 1-9 October use sheet formats /1-/3; none are in ~/work/synarchy.)
> A (recommended): you have no working sheets yet. The inventory is recorded as empty, every existing sheet is kept as evidence, and #145 has nothing to regenerate and closes with that note.
> B: count the latest accepted review sheets (alpha v5, cutout library) as working.
> C: you name specific sheets or folders.

The owner's answer, verbatim:

> "A"

This resolves D-8's requirement to regenerate all existing working sheets
for this arc: there are none. Record SHD-1's working-sheet inventory as
empty and preserve every existing sheet as historical evidence. SHD-8
(#145) records that nothing needs regenerating and closes with that note;
this decision does not claim the tracker action has already happened.

## Question history and resolution

Behaviour contracts were approved through D-34 and the delivery plan through
D-35. D-36 to D-39 resolve review round 1's Q-12 to Q-15 and amend the
affected contracts and slice boundaries; the original signoffs remain
recorded. Actual project look values are
deliberately deferred to the owner-review slice under D-31.
Batch 1's accepted answers are D-5 to D-7; batch 2's are D-8 to D-10;
batch 3's are D-11 to D-13; batch 4's are D-14 to D-16;
batch 5's are D-17 to D-19; batch 6's are D-20 to D-22;
batch 7's are D-23 to D-25; batch 8's are D-26 to D-28;
batch 9's are D-29 to D-31; batch 10's are D-32 to D-34; batch 11's is D-35.
The Q entries after the dated batch history give the current resolution.
Q-1 to Q-15 are resolved. Project look tuning remains deliberately deferred
to SHD-7's owner acceptance.

Batch 1 was posted on 2026-10-20 at 16:52:53 UTC in `#moskophoros`,
message `w8y5pdsiqbn56f33gpftcxhsmi`, request
`moskophoros-20261020-1`, against this draft at `07a7180c79`.
It explicitly asks for independent answers to Q-1, Q-2 and Q-3.

Batch 2 was posted on 2026-10-20 at 19:40:03 UTC in `#moskophoros`,
message `67tefmibchfh673kt62jphjyq6`, under the same request, against
draft `cc0496073d`. It asked Q-3's update/default follow-up, Q-4's term
availability and Q-5's setting ownership. The owner approved all three A
recommendations through D-8 to D-10; no look or numerical formula was
proposed for approval in this batch.

Batch 3 was posted on 2026-10-20 at 19:44:15 UTC in `#moskophoros`,
message `5eijvs26h8vy3b9iqnyztgwh4i`, under the same request, against
draft `2a5e2eb2e7`. It asked Q-4's key control type, Q-6's dithering timing
and Q-7's outline scope. D-11 to D-13 record approval of all three A
recommendations; the batch approved no rendered look.

Batch 4 was posted on 2026-10-20 at 19:55:23 UTC in `#moskophoros`,
message `2rnvusxti2arq8azwejcumt8z2`, under the same request, against
draft `74c8293a75` and Probe 1's page hash above. Its three questions are
Q-11's base colour rule, Q-4's combination family and Q-6's ordered
pattern/anchoring. D-14 to D-16 record the answers: base rule A, combination
family A, and an owner choice of patterns rather than one fixed pattern.
The probe's illustrative weights, brightness endpoints and project look are
not proposed defaults.

Batch 5 was posted on 2026-10-20 at 20:11:17 UTC in `#moskophoros`,
message `jjbdta8qj7fjkd5xp6gqfvzc2s`, under the same request, against
draft `80402faf04` and Probe 2's page hash above. It asks Q-6's pattern
catalogue/anchoring, Q-11's brightness palette policy, and Q-8's per-layer
normal retention. D-17 to D-19 record the answers: pattern catalogue A,
off-palette default A with an additional required snap setting, and per-layer
normal retention A. Snap target and composition details were subsequently
settled through D-20/D-23/D-30/D-34.

Batch 6 was posted on 2026-10-20 at 20:19:21 UTC in `#moskophoros`,
message `4swxhvrx6gwizmkgdv42qjviqi`, under the same request, against
draft `7bd4f74b00` and Probe 3's page hash above. It asks Q-11's snap target,
Q-11's ordinary/missing-ramp behaviour, and Q-10's exclusions. D-20 to D-22
record both snap targets, whole-palette fallback and the exclusions. The
extent of "either way" for ordinary shading was subsequently clarified by D-23.

Batch 7 was posted on 2026-10-20 at 20:48:30 UTC in `#moskophoros`,
message `44ggxjrpc5r923cgqn8t7vq5en`, under the same request, against
draft `3048600136` and Probe 4's page hash above. It asks Q-11's ordinary
shading clarification, Q-4's sky/ground frame and any narrow V-7 exception,
and Q-4's brightness range. D-23 to D-25 record A/C/A: snap fallback only,
selectable sky frame with the explicit narrow exception, and bounded gain.

Batch 8 was posted on 2026-10-20 at 20:53:39 UTC in `#moskophoros`,
message `t34mq5fvgajcxfzw9yngjqqm2a`, under the same request, against
draft `5d95e390fe`. It asks Q-4's strength formula and ambient bypass,
Q-6's dithering scope, and Q-5's snap ownership/composition precedence.
D-26 to D-28 record A/B/A: unit-budget lighting, snap dithering and a shared
snap target. D-29/D-30 subsequently settled the snap algorithm and composite
dither ownership.

Batch 9 was posted on 2026-10-20 at 22:00:16 UTC in `#moskophoros`,
message `ms3nau3wnydkdw35azsub3hr62`, under the same request, against
draft `42e2e75f1b` and Probe 5's page hash above. It asks Q-6's snap
algorithm/strength, Q-6/Q-11's composite ownership and fallback placement,
and Q-9's visual-review boundary. D-29 to D-31 record all three A approvals.

Batch 10 was posted on 2026-10-21 at 00:56:10 UTC in `#moskophoros`,
message `znwjdat3za8bvp872zif42y8ra`, under the same request, against
draft `ae411e59d3`. It requests separate signoff on the three enumerated
implementation contracts embedded below. The review copy is
`~/.local/share/moskophoros-acceptance/shading-design/batch-10-contracts.md`,
SHA-256 `e8aa954b2bd86bdcec0ae81d8699fb0cc81f292753d33eec34450485f7b180c2`.
D-32 to D-34 record all three A approvals against that exact file hash.

Batch 11 was posted on 2026-10-21 at 01:04:54 UTC in `#moskophoros`,
message `wnjw5kij527hz293d6w7amz2ke`, under the same request, against
draft `45873add79`. It asks one final question: approve SHD-1 through SHD-8
and their dependencies and declare the design ready, or name required
changes. The exact review copy is
`~/.local/share/moskophoros-acceptance/shading-design/batch-11-delivery.md`,
SHA-256 `58f448621c2bb523fdd98acf2f05ff4e67d28fefd880280641a12881d764f990`.
D-35 records the owner's approval of this plan and readiness against that
exact file hash.

### Q-1. Does a mode route all shading or only the added light?

Resolved by D-5 and D-34: the four modes route the complete chosen signal,
including ambient form and optional directional terms. Neither does neither
operation. The narrower added-light-only interpretation was rejected.

### Q-2. How should baked light and preview light relate?

Resolved by D-6: separate controls. Ordinary previews display final colour;
the existing additional lit preview remains available even over baked
colour. Maps describe geometry, not illumination.

### Q-3. What remains identical, and what happens to reused sheets?

Resolved by D-8, D-31 and D-32: preserve default image bytes, use only the
current sheet schema, then inventory/regenerate working sheets after the
owner's visual acceptance. Preserve historical acceptance evidence.

### Q-4. Which light terms, in which frame, and how are they combined?

Resolved by D-9/D-11/D-15/D-24/D-25/D-26/D-32/D-34: one camera-fixed
distant key, selectable camera/world sky-ground frame, a unit strength
budget, multiplicative form/light, bounded linear RGB gain and the exact
settings/sampling contract below. Point bake lights, weighted-average form
combination and brightness above the base were rejected. Actual project
strengths are deliberately open only in the D-31 review slice.

### Q-5. Which controls may materials override?

Resolved by D-10/D-17/D-28/D-32/D-33. The settings table enumerates
response/dither overrides and global-only arrangement/snap controls; library
version 4 defines ordinary entries, inheritance, errors and warnings.
Per-material snap-target overrides were rejected.

### Q-6. What dithering belongs in this arc?

Resolved by D-12/D-17/D-27/D-29/D-30/D-34: six selectable fixed tiles,
off by default, strength 0..1, cell-pixel anchoring, shade-driven ramp
dithering and two-nearest-colour snap dithering at the specified operation.
The dominant visible layer controls composite dithering, ties to front.
Custom tile files and best-partner-segment snap dithering were rejected.
The contracts and tile definitions below specify reproducible arithmetic;
rendered implementation quality remains for D-31.

### Q-7. Do outlines belong in this arc?

Resolved by D-13: defer them to a separate style arc.

### Q-8. Where does the new operation sit in the pipeline?

Resolved by D-19/D-34: retain addressed layer normals, shade each layer
outside Blender, then compose and apply the selected final operation. Keep
the accepted combined-front approximation, alpha and exported geometry
unchanged. The contract below includes mean/vote behaviour, strict buffer
validation, frame-at-a-time memory and an exact legacy path.

### Q-9. What evidence completes the arc?

Behavioural review boundary resolved by D-31: robot/shrub/chest, both uses,
motion, perspective/roll, the modes, representative dithering/snapping and
a longer generic ramp. Tests cannot approve looks. The approved delivery
plan assigns that owner review and subsequent regeneration distinct slices;
their boundaries and order are approved by D-35.

### Q-10. What other boundaries and delivery order should be explicit?

Exclusions resolved by D-22. Cast shadows, coloured lights, multiple keys,
specular and retained-capture recolouring are outside this arc.
Delivery-slice boundaries and dependency order below are approved by D-35;
no tracker artifact is authorised by approving this design.

### Q-11. What colour is shaded when ramp selection is off or unavailable?

Resolved by D-14/D-18/D-20/D-21/D-23/D-28/D-30/D-32/D-34: mapped base
is the last ramp colour; ordinary colour/texture is preserved. Optional
brightness/both snap has off/ramp/palette targets. Missing-ramp fallback
changes the allowed colour set, not placement. The contracts specify mixed
layers, mode applicability and errors without treating a palette as an
ordered shading ramp.

### Q-12. Who applies accepted changes to owner configuration files? (S-7)

Resolved by D-38: SHD-7 records exact candidate diffs for each owner file;
the owner's verdict authorises the SHD-8 agent to apply exactly those diffs
and record before/after hashes. No owner configuration changes in this
design revision, and no project look is accepted yet.

### Q-13. Which internal work moves from SHD-6 into SHD-2? (S-10)

Resolved by D-39: SHD-2 owns the two-level reader, gated `/4` parser and
warning builders, tested directly. SHD-6 owns wiring, schema activation,
reuse and evidence. Narrative amendments publish via docs-push as a named
post-merge step for SHD-6; test-read contracts remain in the code PR.

### Q-14. Where does the continuous ambient signal clamp? (S-14)

Resolved by D-36: clamp raw shade to `[lo,hi]` before normalising on the
continuous path. With `lo=190, hi=225, N=40`, raw mean 226 selects band 38
at `L=1` without dithering, matching the integer path in exact arithmetic.
The previous expression would select 39; that jump was not retained.

### Q-15. How many layer normals does capture transport? (S-16)

Resolved by D-37: carry only `back_normal`, deriving front normals from
existing `normal` wherever `front_present` is true. Both addressed layer
normals still reach stylize. The reviewer measured about
0.26 seconds per 768×1024 normal-buffer write and about 9.4 MB per decoded
float32 buffer plus 18.9 MB per float64 working copy; these are local probe
measurements, not production budgets. SHD-1 must report actual capture-time
and work-directory deltas on robot and chest. The two-extra-buffer
alternative was superseded by D-37.

## Review round 1 revision record

Review by mosk-reviewer-67 (Claude) against `f548312`, received 2026-10-21
UTC: 0 blocking, 10 should-fix, 9 minor. Review file
`~/.local/share/moskophoros-acceptance/shading-design/review-claude-1.md`,
SHA-256 `3ed6942b7ac24a14c699522168b3fbc027e8a626b2d6f4da601a9241336be45b`.
The manager's revision brief is
`~/.local/state/project-manager/moskophoros/dispatch-shading-revise-1.md`,
SHA-256 `0a8038b6f507e57cb07868dee2bf396c24ffa262f2cd2f80b5f1af22fcc30dee`,
relayed in cmux message `d1643ba1-ab87-4005-b09e-a9f4ee5d2fb6`.
It authorises the following non-owner clarifications and additive evidence
obligations. Those clarifications are review dispositions, not new owner D
decisions. The four owner-reserved findings were subsequently approved in
D-36 to D-39 through relay `97680a2f-1e3c-483a-994f-ff214e08ff1b`.
All 19 findings were addressed and independently confirmed resolved by round 2.

| Finding | Disposition in this revision |
|---|---|
| S-1 | Fixed: response without a library, global range, optional palette and default bypass; SHD-5 inputs named |
| S-2 | Fixed: second-level groups, leaf merging, null/type/path errors and SHD-2 internal reader/parser duty |
| S-3 | Fixed: leaf validation per source, cross-field validation after resolution, all contributing origins in errors |
| S-4 | Fixed: exact ordered sheet shape/types, all inactive values recorded, unit-vector reuse and inline library |
| S-5 | Fixed: named pre-arc baseline and pin before whichever foundation slice merges first |
| S-6 | Fixed: proven explicit invocations and snapshots; old sheet metadata is evidence, never a new-schema reuse input |
| S-7 | Fixed by D-38: exact per-file diffs, owner verdict authorising SHD-8 application, before/after hashes |
| S-8 | Fixed: mode-reduction motion, soft edges and dithered perspective/roll required in SHD-7 |
| S-9 | Fixed: complete amendment table and per-code-slice public-doc/pinned-test assignments |
| S-10 | Fixed by D-39: internal reader/parser/warning builders in SHD-2; SHD-6 wiring, activation, reuse and evidence; narrative amendments after merge |
| S-11 | Fixed: OKLab projection, RGB-byte input/deduplication and both nearest-colour tie rules |
| S-12 | Fixed: tile denominator is width times height; output-cell coordinates named |
| S-13 | Fixed: effective band dithering defined and ties use unperturbed signal |
| S-14 | Fixed by D-36: continuous raw shade clamped before normalisation, long-ramp boundary checks |
| S-15 | Fixed: older material features require `/3 or later`; `/1` guidance names `/4` |
| S-16 | Fixed by D-37: one extra transported normal buffer, derived front normals, measured robot/chest cost in SHD-1 |
| S-17 | Fixed: explicit world-up vector, stylize argument and narrow V-7 exception |
| S-18 | Fixed: explicit-source warning convention includes ordinary overrides; false ordinary flag rejected |
| S-19 | Fixed: resolved references, reviewer identity, timezone and V-4/V-8 explanation |

## Review round 2 and processing handoff

Claude's round 2 review of `6359cb19a5` returned **READY for issue
processing**, with S-1 to S-19 resolved, no blockers or should-fix findings,
and three minor findings. Review file
`~/.local/share/moskophoros-acceptance/shading-design/review-claude-2.md`,
SHA-256 `632470e3db709d59e22b0baa53b79388d6966c0dfbf5e9960792a139b566480a`.

- **S-20:** resolved by D-40. Keep D-36, state the brightness cap and add
  SHD-3's narrow-range brightness fixture; do not normalise gain separately.
- **S-21:** fixed by making the whole-palette dither-suppression sentence
  explicitly conditional on effective snap (a contributing brightness/both layer).
- **S-22:** fixed by specifying SHD-2's internal gate and public-path
  rejection tests for new settings and `/4` file/inline library records.

The manager relayed D-40 and the processing direction in cmux message
`7539e167-f7ee-4d84-acf4-9029abe13103`. The process brief is
`~/.local/state/project-manager/moskophoros/dispatch-process-shading.md`,
SHA-256 `cf9838d671c0eaa4f8ae350957df5ffc26336ffe59d2a1fbee747c584b2fdafd`.
Publish these final clarifications, retain readiness, then process the epic
and one dependency-ready child per invocation. Each complete draft requires
the manager's or owner's explicit signoff before creation. Child readiness
review and solving are outside this processing assignment.

## Implementation contracts

The base contracts were approved in full by D-32 through D-34 from batch
10's immutable review copy. This text incorporates the non-owner precision
fixes authorised by the revision brief above and the owner's amendments
D-36 to D-40 and round 2's precision fixes; the immutable original approved
copy is unchanged.
These are implementation requirements, not claims of shipped
behaviour. No project look is selected here; D-31 reserves that for rendered
acceptance.

### 1. Settings, defaults and validation (Q-4/Q-5/Q-11)

Keep the existing settings precedence and extend nested leaf merging to the
new second-level sub-groups. All new global
fields have command-line overrides, following the existing settings design.
Per-material values remain in the library. Approved additions:

| YAML field | Default | Command option | Material override |
|---|---|---|---|
| `shade.mode` | `ramp` | `--shade-mode` | yes |
| `shade.ambient_form` | `true` | `--ambient-form` / `--no-ambient-form` | yes |
| `shade.key.direction` | `[-0.6, 0.7, 0.7]`, normalised | `--bake-key-direction X,Y,Z` | no |
| `shade.key.strength` | `0` | `--bake-key-strength` | yes |
| `shade.sky.strength` | `0` | `--bake-sky-strength` | yes |
| `shade.ground.strength` | `0` | `--bake-ground-strength` | yes |
| `shade.sky_ground_frame` | `camera` | `--bake-sky-ground-frame` | no |
| `shade.brightness.floor` | `0.3` | `--brightness-floor` | yes |
| `shade.brightness.ceiling` | `1` | `--brightness-ceiling` | yes |
| `shade.snap` | `off` | `--shade-snap` | no |
| `shade.dither.pattern` | `off` | `--dither-pattern` | yes |
| `shade.dither.strength` | `1` | `--dither-strength` | yes |

Modes are `ramp`, `brightness`, `both`, `neither`; frames `camera`, `world`;
snap targets `off`, `ramp`, `palette`. Pattern names are `off`, `ordered2`,
`ordered4`, `ordered8`, `clustered4`, `diagonal4`, `shuffled8`, using the
exact tiles reviewed in Probe 2. The brightness default 0.3/1 matches the
probes; it has no effect in the default ramp mode. Existing ambient values,
ramp generation, reduction and preview-light defaults are unchanged.

Key direction points **toward** the light in camera coordinates: +X right,
+Y up, +Z toward the viewer. Components must be finite, each in `[-1,1]`,
and not all zero; normalise once and record the resolved unit vector.
Strengths follow D-26, brightness endpoints D-25, dither strength D-29.
World up is the subject's fixed +Y transformed into camera coordinates:
`b = views.subject_basis(camera_direction, roll)` and
`w = (b.right[1], b.up[1], -b.forward[1])`. The command computes this vector
and passes it explicitly to stylize; stylize reads no capture internals.
Camera up is `(0,1,0)`. Ground uses the opposite vector.
Perspective does not change a distant light's direction across the image.
Both projections use this same basis. Rotation about subject +Y leaves world
up unchanged across sheet directions. D-24's V-7 exception is narrowly that
world sky/ground stay tied to world up and camera pitch instead of rotating
with camera roll; the key remains camera-fixed.

Reject unknown names, non-finite values, booleans masquerading as numbers,
null for any new field, invalid sums/ranges and conflicting/repeated CLI
options. Omission inherits; explicit values override individual nested
leaves. Validate even inactive values, without warnings merely because a
term is off. A non-off snap target requires a palette, even if the chosen
mode would leave snap unused. Settings/library errors are exit 2 before
any Blender invocation, naming file/key/line or CLI option and the material
where relevant. Existing library palette requirements remain unchanged.

Inside `shade`, `key`, `sky`, `ground`, `brightness` and `dither` are mappings,
not leaf settings. Settings files and library `shade` mappings merge their
allowed leaves independently; a later `brightness.floor` never erases an
earlier `brightness.ceiling`. Omitted leaves inherit. Empty mappings supply
no leaves. Reject null or any non-mapping sub-group, unknown leaves and
non-string keys at the full dotted path with the YAML key's line/column:
for example `config.yaml: shade.key: expected a mapping of settings, got
null at line 12, column 3`. Library paths additionally name the material
when applicable. Library groups still admit only the leaves allowed by
contract 2; nesting does not allow a per-material direction or snap target.
SHD-2 extends both readers behind the internal-only gate.

Validate types and each leaf's own bounds in every input layer, even when
overridden. Validate the new cross-field rules (`K+S+G <= 1` and brightness
floor <= ceiling) on resolved values only: first the merged global response,
then the library-wide inherited response used by the no-identity class and
every resolved material entry, including unused entries. Do not reject a partial layer solely because its
cross-field relationship will be corrected by a later layer. Retain the
existing per-file duplicate camera-spelling rule unchanged. Report all
contributing values and their origins, including inherited defaults, rather
than attributing a cross-source violation to one arbitrary file. Examples:

```text
shade.brightness.floor 0.8 (config.yaml line 12) exceeds shade.brightness.ceiling 0.5 (--brightness-ceiling)
material 'Painted': shade.key.strength 0.8 (--bake-key-strength) + shade.sky.strength 0.5 (library.yaml line 7) + shade.ground.strength 0.0 (shipped default) = 1.3, exceeds 1
```

These are exit-2 errors before Blender. CLI origins use the option spelling;
file origins include the file, key and line/column; entry errors identify
the material. The examples abbreviate columns for readability.

Record all new resolved global values, and library overrides as supplied,
in the sheet and fingerprint. Reuse must reproduce them without reopening
the original palette/library. Activate `moskophoros.sheet/15` in SHD-6 (the
next version after the reviewed `/14`; reconcile an intervening schema bump
explicitly before implementation). Keep D-8's current-schema-only loading
and one-time regeneration.
The existing `--light` preview interface stays separate.

The exact `settings.shade` shape and insertion order are shown below with
shipped defaults. Preserve the five existing fields first, then add the
new fields in settings-table order. `ao_samples` and `range` entries remain
integers; other numeric values, including direction components, are floats;
`ambient_form` is a boolean and enums are strings. Nested members have the
order shown. Record every value even when inactive:

```json
{
  "ao_distance_m": 0.3,
  "ao_samples": 64,
  "occlusion_weight": 0.25,
  "convexity_weight": 1.0,
  "range": [84, 191],
  "mode": "ramp",
  "ambient_form": true,
  "key": {
    "direction": [-0.5183210553488161, 0.604707897906952, 0.604707897906952],
    "strength": 0.0
  },
  "sky": {"strength": 0.0},
  "ground": {"strength": 0.0},
  "sky_ground_frame": "camera",
  "brightness": {"floor": 0.3, "ceiling": 1.0},
  "snap": "off",
  "dither": {"pattern": "off", "strength": 1.0}
}
```

Reuse validates a recorded unit key direction against `views.UNIT_TOLERANCE`
and keeps its components exactly as recorded, never normalising them again;
a non-unit recorded vector is invalid. Ordinary file/CLI vectors normalise
once using `views.normalise`; the example records that helper's result.
Retain existing JSON encoding and sorted-key canonical fingerprinting.
The existing inline `settings.style` library record keeps overrides as
supplied, including `/4` `ordinary: true` mappings and their nested `shade`,
alongside existing recorded generated-ramp indices. Do not flatten or replace
entry overrides with inherited values. Palette/library reuse reads that
inline record without reopening source files.

### 2. Library shape and inheritance (Q-5)

Introduce `moskophoros.materials/4`. Continue reading `/2` and `/3` under
their existing rules; they cannot contain new fields. Old libraries need no
edit for unchanged output. New fields or ordinary entries with response
overrides require `/4`. Keep rejecting `/1`; its migration guidance names
`moskophoros.materials/4`. Messages for library-wide shade and generated
ramps say `needs moskophoros.materials/3 or later`, rather than incorrectly
requiring `/4` for those older features. New response fields require `/4`.

Extend each material's existing `shade` mapping with the response fields
marked yes in contract 1. At library top level, `shade` may contain the
existing `range` plus those new response fields. It still cannot supply
library-wide AO capture values. Direction, sky/ground frame, snap target
and AO sample count remain global only. Existing per-material AO capture
overrides remain available, including on the new ordinary-entry form.

Each new response leaf inherits **material entry > library-wide shade >
resolved global setting**. A global CLI override cannot defeat a material
or library value. Resolve and validate every entry's combined strengths and
brightness endpoints, including unused entries; partial overrides do not
escape the cross-field checks. **D-41 amendment, 2026-10-20:** only an
explicit command-line option or a project-file value counts as an explicit
global value for shadow warnings when library/material values take
precedence. Apply the existing warning convention to new response fields
and existing fields alike, including ordinary entries with response or
ambient-occlusion overrides. The global file, its `--config` replacement,
shipped defaults, a reused sheet and ordinary inheritance are not warning
events. Existing warning behaviour is unchanged.

Keep existing ramp/uses forms and the string `ordinary`. Add a mapping form
with exactly one of `ramp`, `uses`, or `ordinary: true`, plus optional
`shade`. `ordinary` in a mapping must be the boolean `true`; `false`, null,
strings or numbers are errors, not another form of inheritance. For example:

```yaml
schema: moskophoros.materials/4
ramps: {}
shade:
  mode: brightness
materials:
  Painted:
    ordinary: true
    shade:
      brightness: {floor: 0.4, ceiling: 1}
  Glow:
    ordinary: true
    shade:
      mode: neither
```

This example still requires a palette under the retained library rule.
`ordinary` means no assigned ramp, not forced `neither`; it preserves the
model's ordinary colour/texture base and inherits response controls. An
unlisted material keeps the existing default-ramp resolution. Materials
without identities use global/library-wide response defaults and retain
their ordinary base. Missing ramp references still error; D-23's snap
fallback applies only when there is legitimately no resolved ramp.

The response step runs with or without a library. Without one, every
identity (including no-identity) is ordinary, with the resolved global
response and global `shade.range`; no palette is required unless snap is
non-off. A supplied palette retains ordinary palette mapping. Ramp mode
has no invented ramp, both falls back to brightness, and neither keeps the
ordinary base, as D-23 requires. Skip the response step for the all-default
no-library case to preserve exact existing bytes. SHD-5 passes resolved
responses, the sky/ground vector and `shade_range` into stylize explicitly,
with the range supplied whether or not a library is present.

### 3. Pixel operations and addressed capture data (Q-6/Q-8/Q-11)

**Snap applicability (D-34):** optional snap operates on
brightness/both. Ramp-only keeps shade-driven ramp dithering; neither stays
unshaded and undithered. Existing palette mapping of ordinary colours and
non-brightness translucent composites remains unchanged. This preserves
the original role of snap as a post-brightness operation.

Retain the existing per-layer alpha weights, material winner/ties, ordinary
colour reduction and geometric-map reduction. Use the winning material's
response and resolved ramp. Mapped brightness/neither base is the last ramp
entry; ordinary base is the existing reduced ordinary colour/texture,
including its usual palette mapping when a palette is present.

For plain reduction, average the winning material's raw shade and each
nonnegative normal-facing term separately, using that layer's existing
visible sample weights. With range `[lo,hi]`, use
`a=(clamp(mean_shade,lo,hi)-lo)/(hi-lo+1)` when ambient form is on, otherwise
`a=1`. Compute `L` from the averaged facing terms, then `e=a*L`. This is the
order illustrated in the probes, not averaging normals before the facing
dot product. Ramp index is `clamp(floor(N*e),0,N-1)`; RGB brightness gain is
`floor+(ceiling-floor)*e` in linear colour, followed by sRGB encoding and
half-up byte rounding.

As D-40 confirms, ambient form on caps `e` below 1. At `L=1`, maximum
gain is `floor+(ceiling-floor)*(hi-lo)/(hi-lo+1)`, below the ceiling unless
the endpoints are equal. For `[100,101]` with floor 0.3 and ceiling 1.0,
the cap is 0.65, even when raw shade exceeds 101. Ambient form off gives
gain 1.0 in that example at `L=1`. No separate brightness normalisation is
applied; this range-dependent cap is intentional.

For mode reduction, clamp each winning-material sample's raw shade to
`[lo,hi]` before the same normalisation, evaluate its range signal and light
product, select its band and use the existing weighted palette
entry vote. Repeated entries pool their votes. Resolve ties by nearest
band centre to the unperturbed plain-reduction signal above, then lower
palette index; dithering never perturbs the tie-breaking reference.
Brightness uses that same plain-reduction signal after the voted ramp/base
colour has been selected. Thus the existing mean-versus-vote distinction
remains, without introducing a separate brightness voting scheme.

For shade-driven ramp dithering, perturb the band coordinate by
`strength*(0.5-threshold)` before flooring; in mode reduction use the same
output-cell threshold for every sample's band vote. Threshold is
`(tile_rank+0.5)/(width*height)` at `(x mod width,y mod height)`, where `x,y`
are the output cell's pixel column and row, with top-left origin,
with no frame/direction/sheet-packing offset. Both layers share the cell
origin. Snap dithering uses D-29 instead. These are distinct quantisers
with one pattern/strength control.

Effective band dithering requires a pattern other than `off`, strength
greater than zero, mode `ramp` or `both`, a resolved ramp, and no effective
snap suppressing that layer's intermediate dithering. Otherwise use the
undithered band path. Effective whole-palette snap (some contributing layer
uses brightness/both) suppresses intermediate dithering on both contributing
layers, including a ramp-only layer. D-29 snap receives
the 8-bit sRGB bytes after brightness half-up rounding (own-ramp snap) or
composition (whole-palette snap). Distinct target colours mean distinct RGB
byte triples. Deduplicate by first target occurrence, select nearest and
second-nearest by OKLab distance with target-order ties for both, and project
the desired colour onto their segment **in OKLab** before clamping the
second-colour fraction. A one-colour target is constant.

**Exact compatibility:** with ambient form on, all directional strengths
zero and no effective dithering, retain today's exact integer ramp
selection and tie arithmetic. Do not replace it with a floating-point
approximation. The normal default output, including ordinary materials,
alpha, maps and previews, must remain byte-identical under D-8. The new
continuous formula above governs changed shading settings; it does not
silently revise the historical integer-bin boundary cases.

For effective ramp snap, skip intermediate dithering on each
brightness/both layer, apply brightness, then D-29 snap to its ramp (or the
whole palette if absent). Composite once, retaining its off-palette result
when a contributing layer uses brightness/both, as D-18 requires. For
effective palette snap, if any contributing layer uses brightness/both,
skip intermediate dithering on both layers, composite their colours, then
snap once to the whole palette. D-30 selects the final dither controller;
if its mode is neither, snap without dithering. With snap off, retain
brightness/both colours without a final palette snap. When neither layer
uses brightness/both, retain today's composite palette rule. No operation
changes alpha or geometry buffers.

Capture transports one extra buffer, `back_normal`, alongside the existing
front-most `normal` and `depth` (D-37). Reuse the existing 16-bit RGBA normal
encoding, camera coordinates and unit-length tolerance. `back_normal` is
zero where the back colour is absent and present exactly where it is
present. At the existing command/backend boundary, decode `back_normal`
as a float32 addressed array and derive the addressed `front_normal` from
the decoded existing `normal` wherever `front_present` is true, zero
elsewhere. Derive presence from the front colour, not front alpha `q`;
zero-opacity but present fronts still have their accepted front-most normal.
There is no separately transported `front_normal` PNG. Validate the source
normal/presence relationship before deriving it. The derived array describes
the accepted combined front layer's front-most surface.

Bump capture-result schema and strictly validate required names, dimensions,
encoding, presence and normals before stylize; malformed output is backend
error 5 with frame/buffer context. A capture-job schema change is only needed
if its payload changes. Exported normal/depth still use their existing
buffers unchanged. Normalise a float64 working copy of the addressed layer
normals for shading only; never mutate the decoded exported-map source.
Keep pure colour maths outside Blender. Retain one supersampled frame at
a time and release its auxiliary buffers after reduction. No retained-
capture replay command, new dependency or extra ray-traced render is
introduced by this contract. Mechanical checks cover the new buffers,
plain/mode and material ties, every snap/mode combination, both edge rules,
zero-strength equality, deterministic reuse, and default byte comparisons.
D-31's later owner review still decides whether the implemented result
looks right.

### Fixed tile definitions

These reproduce D-17's reviewed Probe 2 tiles; they are data, not new pattern
choices. Rows are top to bottom and columns left to right. Ordered tiles
start with `M=[0]` and repeatedly form the block matrix
`[[4*M,4*M+2],[4*M+3,4*M+1]]` to side length 2, 4 or 8.

Clustered 4×4:

```text
12  5  6 13
 4  0  1  7
11  3  2  8
15 10  9 14
```

Diagonal 4×4 has rank `4*((x+y) mod 4)+y`, with `x,y` from 0 to 3.
Shuffled 8×8 is fixed, with no runtime random seed or permutation:

```text
22 15 25 10 34 61 60 30
33 42 40 21 13  0 47 12
17  4 46 38 50  6  2 29
37 51 11  9 18 62 32 20
28 19 59  5 43 49 52 26
 1 58 39 44 41 45 48  8
53 23 24 31 16 57 56 14
55 54 36 63  7 27  3 35
```

## Verification strategy

Each implementation slice includes tests for the behaviour it introduces;
verification is not postponed to the final visual review. Follow the
[validation contract](../validation.md) and planner at each actual PR head.
With the present catalog, source changes select static checks, package
tests and local Blender tests. Report the required current-head local
validation; skipped tests do not pass. Generated fixtures and outputs stay
in temporary/local evidence directories, not git.

- **Compatibility:** the named pre-arc source baseline is
  `shading-pre-arc`, commit `f548312a5a929fb9bd843855b83b9762123f80ab`
  (a manifest name, not a mutable Git tag). Before the first implementation
  change, pin that source, its actual tool/dependency versions, command set
  and hashed input/config/library/palette snapshots in local evidence. The
  manager records the manifest in the eventual epic. Whichever of SHD-1 or
  SHD-2 merges first must prove this precondition; later slices reuse it,
  never move it to their own starting head. Compare
  default sheet/map PNG and ordinary/lit preview bytes against it. Exercise
  mapped and ordinary materials, old library versions, both reductions and
  both edge rules. Record expected schema/settings/fingerprint differences
  separately; JSON changes do not justify changed image bytes.
- **Pure operations:** small exact fixtures cover light direction/frame,
  unit-budget boundaries and ambient bypass; mode/band ties and repeated
  palette entries; gain endpoints and rounding; all tiles and strengths;
  nearest-pair ties, duplicate/single-colour targets and snap fallback.
- **Layers and capture:** generated opaque, cutout and translucent fixtures
  verify normal presence/encoding, malformed-buffer rejection, separate
  layer lighting, front approximation, dominant-contribution ties,
  unchanged alpha/maps, and release of supersampled data frame by frame.
- **Settings/reuse:** exercise precedence, ordinary-entry inheritance,
  invalid inactive fields, cross-field errors, early failure before Blender,
  warning provenance and every recorded field. Reproduce with original
  palette/library files unavailable, using the new current sheet schema.
- **End-to-end behaviour:** cover the four modes with effective/ineffective
  snap, both snap targets, all patterns, camera/world sky, orthographic and
  perspective/roll, normals/depth output switches and additional lit preview.
  Use representative combinations rather than treating every Cartesian
  combination as a separate visual review.
- **Visual acceptance:** SHD-7 follows D-31; tests establish contracts, not
  whether motion, ramps or dithering look right. Record the owner's exact
  acceptance or requested revisions against immutable evidence and settings.
  Require mode reduction with lighting and ramp dithering in motion, at
  least one soft-edge case, and a dithered perspective/roll animation; the
  earlier plain-reduction probes did not establish these visual outcomes.

**Working-sheet invocation inventory:** SHD-1 records each working sheet's
explicit command, source hash, tool versions, complete effective config and
palette/library snapshots, and output hashes; classify historical artifacts
separately. Where only `/14` JSON survives, derive the explicit invocation
by hand as local evidence. This is not a tool conversion or an old-schema
loader. Prove the invocation at `shading-pre-arc` by reproducing the original
sheet and associated image/preview bytes and `/14` metadata byte for byte,
including recorded path spellings. Record discrepancies rather than quietly
updating the reference. Missing inputs, differing historical tools or any
unproven invocation stop that item for owner disposition. SHD-8 uses only
proven invocations plus SHD-7's accepted changes under the new tool; it never
passes an old `/14` sheet to the new current-only `--settings-from` loader.

**D-42 note, 2026-10-21:** the owner confirmed there are no working sheets
yet. SHD-1 records an empty working-sheet inventory; every existing sheet
is historical evidence to preserve. There are no working invocations to
prove or outputs to regenerate for this arc. The shared pre-arc baseline
and compatibility checks remain required.

This design-only assignment ran local numerical probes and document checks,
not repository tests. No implementation, CI or rendered-product acceptance
is claimed.

## Delivery plan

**Approved by the owner in D-35 and amended by D-36 to D-39.** All review
holds are resolved. Additive evidence obligations are authorised by the
revision brief. The processing ledger mirrors this
order. SHD-1 and SHD-2 can be developed independently; the remaining slices
follow the stated dependencies. Public controls activate only in SHD-6,
after their entire behaviour exists: earlier foundations must not accept
new user settings and silently ignore them.

SHD-1 through SHD-6 are one-PR-sized code deliveries with their own tests.
SHD-7/SHD-8 are acceptance/operational documentation slices: publish their
records with `docs-push`, with no empty code PR. Fixes discovered there use
the normal code-review path before acceptance resumes. Test-read Markdown,
including `docs/design.md`, travels with the relevant code under repository
rules; narrative design amendments and acceptance records use `docs-push`.
No tracker items are created by this design workflow. The owner selected
Claude for design review; round 1 is recorded above. Re-review and issue
processing await the manager's instruction after these revisions.

### SHD-1. Preserve addressed normals for both capture layers

**D-42 note, 2026-10-21:** the working-sheet inventory below is empty by
the owner's decision. Record that disposition and preserve all existing
sheets as historical evidence; no working-sheet invocation proof is needed.
The capture and shared-baseline requirements remain unchanged.

- **Outcome:** validated back/front normal buffers reach addressed frames,
  while exported geometry and default colours remain unchanged.
- **Scope:** capture/result schema and encoder changes, backend decoding and
  validation, frame buffer names, fixtures and the owning capture contract.
  Transport only `back_normal`; derive addressed front normals from existing
  `normal` and front presence at decode, without modifying map data.
  Apply the shared `shading-pre-arc` baseline precondition before either
  foundation slice merges. Build the proven invocation inventory specified
  under Verification, distinguishing working outputs from historical
  acceptance artifacts; it must support regeneration without loading old
  sheet JSON in the new tool.
- **Phase:** 1, capture foundation.
- **Depends on:** none.
- **Ordering:** critical path; can land first.
- **Relevant decisions:** D-8, D-19, D-31, D-34, D-37.
- **Acceptance signals:** distinct layer normals survive a translucent
  fixture; missing/malformed buffers fail with frame context; existing map
  and default image bytes match the recorded baseline; required checks pass.
  Report measured capture-time and work-directory byte deltas versus the
  pinned baseline on robot and chest, with commands, frame/cell dimensions,
  supersampling and tool versions. Include derived-normal presence checks,
  including zero-opacity but present fronts; no extra normal render or
  transported front-normal file is introduced.
- **Out of scope:** shading controls, colour maths, owner-config edits or
  regeneration of working sheets.
- **Documentation and pinned tests:** update `docs/design.md` §Capture job
  and result contract (result format/mandatory buffers, ownership/failures,
  compatibility) and §Frames into stylize. Update capture-result `/4` pins
  and fixtures in `tests/test_capture_backend.py`, `tests/test_command.py`
  and `tests/test_capture_blender.py`. Add layer-buffer checks without
  changing sheet JSON; capture job schema stays unchanged if its payload does.
- **Open questions:** none; Q-15 resolved by D-37.

### SHD-2. Model and resolve shading settings and library responses

- **Outcome:** reusable pure response models, validators and library
  decoding/resolution implement the signed settings/inheritance contract.
- **Scope:** new field types/defaults, normalised direction and strength
  validation, `/4` response/ordinary-entry handling, preserved `/2`/`/3`
  readers, nested inheritance, explicit-value provenance and warning data.
  Extend settings and library readers for the second-level sub-groups,
  leaf origins and resolved cross-field errors behind the internal gate.
  Own the gated `/4` parser and complete warning-message builders, with
  direct tests for source attribution, ordinary-entry overrides and older
  schema guidance; SHD-6 only wires these into public paths.
  Apply the shared baseline precondition if this slice merges first.
  Keep these foundations internal until SHD-6 wires the public loaders and
  CLI; do not accept unsupported user-facing fields in this intermediate step.
  The gate is an explicit internal parameter or schema injection used by
  direct tests, unreachable from public command options, settings files or
  sheet records until SHD-6 activation.
- **Phase:** 1, configuration foundation.
- **Depends on:** none.
- **Ordering:** critical path; independent of SHD-1 and can land first.
- **Relevant decisions:** D-10, D-17, D-24 to D-26, D-28, D-29, D-32, D-33, D-39.
- **Acceptance signals:** direct model/parser tests cover old library
  equivalence, ordinary entries, precedence, shadow warnings and cross-field
  validation, including inactive and unused entries; public behaviour stays
  at its pre-activation contract.
  Public-path tests assert the unchanged pre-arc rejection messages for a
  `/4` library passed through `--materials`, a `/4` library embedded in a
  current sheet's inline record, and new nested settings keys such as
  `shade.key.strength`. No public option or file can enable the internal gate.
- **Out of scope:** public flags, sheet schema activation, rendering or
  owner-config edits.
- **Documentation and pinned tests:** none public; add direct internal
  parser/model tests while preserving the active settings key list,
  defaults, `/3` public loader and sheet schema. No public `docs/design.md`
  amendment yet. S-2's new reader tests exercise gated code only.
- **Open questions:** none; Q-13 resolved by D-39.

### SHD-3. Implement pure lighting and four-mode colour operations

- **Outcome:** tested pure kernels compute the selected light/form signal
  and four colour modes for already addressed sample data.
- **Scope:** direction/frame transformations, per-sample facing terms,
  plain/mode sampling, band/tie rules, ordinary/mapped bases, bounded linear
  brightness and the exact integer compatibility path. Use the SHD-2
  response model; expose no CLI or persistence change yet.
- **Phase:** 2, colour mathematics.
- **Depends on:** SHD-2.
- **Ordering:** critical path.
- **Relevant decisions:** D-5, D-14, D-15, D-23 to D-26, D-32, D-34, D-36, D-40.
- **Acceptance signals:** exact fixtures distinguish averaging normals from
  averaging facing terms, mean from vote, ambient bypass, camera/world
  roll, ordinary fallback and repeated ramp entries; zero-new-term kernels
  preserve legacy results; gain rounding/bounds are verified.
  Pin long-ramp boundary cases including `[190,225]` with 40 bands and
  `[100,101]` with 3 bands, checking raw shades below, at and above each
  range endpoint under plain and mode reduction. The continuous mapping
  clamps raw shade first; retain exact legacy arithmetic on its own path.
  Add the narrow-range brightness fixture `[100,101]`, floor 0.3,
  ceiling 1.0 and `L=1`: at or above the high endpoint, gain is 0.65 with
  ambient form on and 1.0 with it off, for plain and mode reduction.
  Verify the resulting linear-RGB scaling and half-up encoded bytes.
- **Out of scope:** dither/snap quantisation, capture changes, stage wiring
  and public settings.
- **Documentation and pinned tests:** no public `docs/design.md` or schema
  pins change while kernels are internal. Add pure-operation tests for the
  contracts above; retain existing integer-kernel expectations unchanged.
- **Open questions:** none; Q-14 resolved by D-36.

### SHD-4. Implement deterministic ramp and snap dithering

- **Outcome:** pure quantisation kernels implement the six fixed tiles,
  shade-driven band dithering and the approved two-nearest snap algorithm.
- **Scope:** exact tile data, cell-coordinate thresholds, strength handling,
  nearest-colour fallback, target order and duplicate/single-colour cases,
  per-layer versus composite quantisation inputs. Keep kernel inputs explicit
  so stage integration decides when and whose controls to apply.
- **Phase:** 2, colour quantisation.
- **Depends on:** SHD-3.
- **Ordering:** critical path.
- **Relevant decisions:** D-12, D-17, D-20, D-23, D-27, D-29, D-34, D-36.
- **Acceptance signals:** all tiles contain each rank exactly once; zero
  strength equals the undithered path; targets contain every selected colour;
  ties, duplicates and one-colour targets follow the signed rules; packing
  and frame order do not alter the pattern.
- **Out of scope:** public options, configuration files or visual acceptance.
- **Documentation and pinned tests:** no public `docs/design.md` or schema
  pins change while quantisers are internal. Add exact pure-kernel tile,
  rounding, tie and coordinate tests; public scope changes belong to SHD-6.
- **Open questions:** none; band arithmetic incorporates D-36.

### SHD-5. Integrate shading into the addressed-frame pipeline

- **Outcome:** stylize applies the complete per-layer and final-composite
  contract using internal resolved responses, preserving stage boundaries.
- **Scope:** addressed normal consumption, existing material winners and
  weights, four-mode base/shading operations, effective snap applicability,
  dominant-layer dither control, no double dithering and unchanged geometric
  reduction. Exercise new responses directly in stage tests; normal command
  defaults remain unchanged until SHD-6 enables the public interface.
  Run the response path without a library as contract 2 specifies; pass
  resolved responses, sky/ground vector and `shade_range` explicitly, with
  the range supplied even without a library. Test palette-free brightness,
  no-ramp both/ramp/neither, and the default no-library bypass.
- **Phase:** 3, pipeline integration.
- **Depends on:** SHD-1, SHD-2, SHD-3, SHD-4.
- **Ordering:** critical path.
- **Relevant decisions:** D-6, D-14, D-18 to D-21, D-23, D-27 to D-30, D-34, D-36, D-37.
- **Acceptance signals:** mixed front/back mode combinations, own-ramp
  fallback placement, whole-palette composite ownership and ties agree with
  exact fixtures; alpha/maps are invariant; default bytes match; one-frame
  memory discipline and both reductions/edge rules are covered.
- **Out of scope:** CLI/schema activation, owner project tuning and review.
- **Documentation and pinned tests:** update `docs/design.md` §Frames into
  stylize and §Stylize (Two layers) for the internal response arguments,
  addressed data and reduction boundary, explicitly noting that public
  activation remains SHD-6. No public schema pins change; extend stage tests
  for the new arguments and no-library/ordinary combinations.
- **Open questions:** none; Q-14/Q-15 resolved by D-36/D-37.

### SHD-6. Expose shading controls and reproducible sheet settings

- **Outcome:** users can select every approved control through YAML/CLI,
  load `/4` libraries and reproduce outputs from current-schema sheets.
- **Scope:** wire the completed models/kernels into public settings, defaults,
  CLI, project precedence, library loading, warnings, early errors, sheet
  records/reuse and fingerprints. Reuse SHD-2's two-level reader, gated `/4`
  parser and warning builders; do not reimplement them here. Activate the
  sheet schema bump once.
  Complete end-to-end/default-byte evidence and the owning CLI/pipeline/
  export contracts. Narrative publication is the named post-merge step below.
- **Phase:** 4, public activation and reproducibility.
- **Depends on:** SHD-5.
- **Ordering:** critical path.
- **Relevant decisions:** D-5 to D-11, D-14, D-18, D-22 to D-30, D-32 to D-34, D-39.
- **Acceptance signals:** every option round-trips; invalid input fails
  before Blender; old `/2`/`/3` libraries retain their output; the signed
  precedence/warnings hold; reuse works without original palette/library
  files; generated opaque/cutout/translucent cases cover modes, frames,
  projections, output-map switches and additional lit previews. Record
  passing planned checks and default byte comparisons at the delivered head.
- **Out of scope:** editing owner project values, second-game palette work,
  visual acceptance or bulk sheet replacement.
- **Documentation and pinned tests:** update `docs/design.md` §CLI,
  §Settings files (including the test-read YAML example), §Option validation,
  §Frames into stylize, §Stylize (Palette mapping and composition, Material
  libraries, Material ramps, Using a library from the command), §Export
  (including previews) and §Reproducibility. Remove the universal
  no-dithering/no-baked-light claims while retaining their default behaviour.
  Update sheet `/14` pins in `tests/test_command.py`, `test_export.py`,
  `test_frames_command.py`, `test_materials_command.py`, `test_reuse.py` and
  `test_settings_command.py` (all under `tests/`). Update materials schema
  and error expectations in `test_generated_ramps.py`,
  `test_material_shading_command.py`, `test_materials.py` and `test_reuse.py`;
  retain valid `/3` fixtures as compatibility coverage, adding `/4` cases
  rather than blindly replacing every `/3` literal. In `test_settings.py`,
  update the ordered `SCHEMA` keys, defaults-file agreement and example
  loading tests; keep the top-level `GROUPS` set unchanged and test the new
  sub-group recognition separately.
- **Post-merge narrative publication (D-39):** after SHD-6 merges, publish
  the narrative amendments with `docs-push` as a named completion step,
  before handing off to SHD-7. Cover the amendment table's material styling,
  lighting, alpha, settings D-20 and projects/camera D-8 changes and D-24's
  dated V-7 exception. Record the documentation commit in the slice's
  completion report. These narrative edits are outside the code PR's review
  acceptance; test-read `docs/design.md` stays in that PR.
- **Open questions:** none; Q-13 resolved by D-39.

### SHD-7. Obtain owner visual acceptance for both uses

- **Outcome:** an acceptance record links reproducible, immutable evidence
  to the owner's explicit verdict and selected project look values.
- **Scope:** D-31's robot/shrub/chest matrix, both use cases, motion,
  perspective/roll, modes and representative dither/snap combinations,
  including a longer generic ramp. Require `reduce: mode` with light and
  ramp dithering in motion, at least one soft-edge case and a dithered
  perspective/roll animation. Use candidate config copies in local
  evidence; preserve live project settings until the owner accepts the
  exact proposed values. Record commands, hashes, tool revision, limitations
  and the exact owner response in `docs/acceptance/shading.md` via docs-push.
  Give the exact diff for every owner project/library file and its current
  hash. The owner's verdict authorises SHD-8 to apply exactly those accepted
  diffs (D-38); record that verdict against the immutable diff evidence.
- **Phase:** 5, owner visual review; documentation/acceptance delivery.
- **Depends on:** SHD-6.
- **Ordering:** critical path.
- **Relevant decisions:** D-1 to D-4, D-8, D-17 to D-20, D-24 to D-31, D-34, D-38.
- **Acceptance signals:** the owner approves both uses against named evidence;
  requested code corrections are delivered and verified before refreshing
  that evidence. Tests or agent judgments cannot substitute for the verdict.
- **Out of scope:** automatic project-look selection, the second game's
  palette/project file, unrelated art changes and bulk regeneration.
- **Open questions:** deliberately open actual project strengths, palette/
  ramp choices and look tuning under D-31. Stop for the owner at this slice;
  a withheld visual acceptance blocks SHD-8, not a guessed default.
  The application procedure is settled by D-38; exact diffs still require
  that later owner verdict.

### SHD-8. Regenerate the inventoried working sheets

**D-42 note, 2026-10-21:** the owner confirmed there are no working sheets
yet. The inventory is empty, every existing sheet remains historical
evidence, and SHD-8 (#145) records that nothing needs regenerating and
closes with that note. The regeneration requirements below have no working
outputs to act on for this arc; do not regenerate historical evidence.

- **Outcome:** reproducible working sheets use the accepted current settings
  and current schema; historical acceptance evidence remains intact.
- **Scope:** reconcile SHD-1's inventory. Under the authority of SHD-7's
  owner verdict, the SHD-8 agent applies exactly the accepted per-file diffs
  and records before/after hashes. Confirm each file still matches its
  reviewed before-hash; a changed file or additional edit stops for the
  owner. Regenerate each
  working output from its baseline-proven explicit invocation and snapshots
  with those accepted changes, and verify current-schema reuse. Do not use
  old `/14` sheets as settings inputs to the new tool. Extend the acceptance
  record with inventory/disposition, commands, output hashes and any unresolved
  input. Keep assets, sheets, previews and local config out of the repository.
- **Phase:** 6, operational refresh and documentation.
- **Depends on:** SHD-7.
- **Ordering:** critical path to the epic's completion.
- **Relevant decisions:** D-3, D-8, D-31, D-32, D-38.
- **Acceptance signals:** every inventoried working sheet is regenerated and
  reproducible, or explicitly dispositioned by the owner; historical artifact
  hashes remain unchanged. Missing inputs or uncertain working/archive
  classification stop that item for the owner rather than trigger guesses.
- **Out of scope:** an old-schema loader/converter, regenerating historical
  evidence, unsolicited config changes and second-game setup.
- **Open questions:** any concrete inventory gap, changed owner file or
  unproven baseline invocation requires owner
  disposition, recorded before declaring done.

## Source notes

- Request: `moskophoros-20261020-1`. The owner invoked this workflow through
  the manager and supplied the dispatch path and hash in the designer's
  pane on 2026-10-20.
- Dispatch:
  `~/.local/state/project-manager/moskophoros/dispatch-shading-design.md`,
  SHA-256
  `f170119f3ca2db77c13eec3812b10b019b3ea4875e255f293f516cf39fdbafe7`.
  It relays the owner's instruction in the manager's terminal:
  “ok onto the shading design” (2026-10-20; time not supplied).
- Earlier handoff:
  `~/.local/share/moskophoros-acceptance/cutout-review/handoff-shading-design.md`,
  written by mosk-solver-23 on 2026-10-19. Its owner quotes are source
  material; its interpretations and ten questions are not decisions.
- Owner, 2026-10-19 16:31 UTC, in that earlier worker's pane:
  the handoff quotes “looks like a rectangle, not a column” about the trunk.
  For the pot, it quotes
  “should be the darkest part and have a little shade into the pot color”
  about the line under the rim, and “the rim should be the brightest part”.
- In that same 16:31 UTC answer the owner explained the live-lit use:
  “objects need ambient shading baked in so that the objects have some color
  shift and dithering/naturalness.” This is a requirement to settle dithering,
  not approval of a particular pattern.
- The dispatch describes the second project in the owner's words:
  “a 2d top down map game … procedurally generated … moskophoros is going to
  be used for me to generate 2d art panels to accompany text to the player”.
  Its timestamp is not supplied; the ellipses are in the dispatch.
- Owner after the alpha review, quoted in the dispatch and
  `docs/acceptance/alpha.md`: “the wood could honestly have more shading, and
  perhaps some more texture to it, but we can do that later”. The acceptance
  record dates the answer to about 2026-10-19 03:05 UTC and identifies the
  manager's relay as `a51e81e0-8190-47be-ab85-99ff495d2e59`.
- Questions go to `#moskophoros` as `question` posts with
  `--re moskophoros-20261020-1`. The manager relays the owner's answers;
  direct answers in this designer's pane also count. Each accepted answer
  will retain its date/time, exact words and relay ID or pane provenance.
  Batch 1 was answered through cmux relay
  `ae3ad3ce-e442-4abd-92fb-f51fb3f858de`; D-5 to D-7 preserve the exact
  answers and their limits. Batch 2 was answered through cmux relay
  `d44ba361-bf3c-4e8e-91a2-e59e2aeccd33`; D-8 to D-10 preserve its exact
  answer and the approved recommendations. Batch 3 was answered through cmux
  relay `35757489-cc29-456a-a840-3a702ec80cb3`; D-11 to D-13 preserve it.
  Batch 4 was answered through cmux relay
  `ba055c23-a81e-43c6-b64e-8e3ab9b60301`; D-14 to D-16 preserve it.
  Batch 5 was answered through cmux relay
  `20dc14aa-e207-4c00-8fcb-33c26f9ca4ec`; D-17 to D-19 preserve it.
  Batch 6 was answered through cmux relay
  `f31db19c-e69e-4355-b089-675413f7601b`; D-20 to D-22 preserve it.
  Batch 7 was answered through cmux relay
  `066ddb06-09d7-4668-b1eb-1ea044eb7fa2`; D-23 to D-25 preserve it.
  Batch 8 was answered through cmux relay
  `18e15fc0-f95f-4d00-a1fd-99a49ef236b6`; D-26 to D-28 preserve it.
  Batch 9 was answered through cmux relay
  `8587a525-f617-4a48-81da-289fe90cd6f7`; D-29 to D-31 preserve it.
  Batch 10 was answered through cmux relay
  `c7d58503-9365-4b09-88be-2c82dbc04920`; D-32 to D-34 preserve it.
  Batch 11's delivery-plan and readiness signoff was relayed through cmux
  message `793d365b-4cca-4173-aab7-47d98d33ee46`; D-35 preserves it.
