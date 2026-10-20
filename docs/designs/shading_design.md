# Shading design

Moskophoros must serve both sprites lit by their consumer from exported face
maps and art panels whose lighting is baked into their colours. This design
settles that capability with the owner before implementation.

Design state: `exploring`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [ ] EPIC. Support configurable baked shading alongside live-lit sprites

No delivery slices are settled yet. The remaining behaviour and scope must be
answered before decomposition. This document is not ready for issue processing.

## Epic contract

- **Goal:** express the owner's two uses through generic project settings,
  with four settings-controlled modes: ramp, brightness, both and neither.
- **Done when:** the owner has accepted the implemented behaviours on both
  uses, including sheets and motion, and the agreed mechanical contracts
  pass verification. The precise review and delivery boundaries remain open.
- **Users and operators:** artists generating sprites or panels and consumers
  using their colour, normal and optional depth maps.
- **Arc label:** none proposed.

This is a plan. It does not describe a shipped baked-light option.

## Current state and evidence

Verified against `master` at `6c5f47a1293cc8a99b25d5e6e360bfd3536ab320`
on 2026-10-20:

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
- Tracker overlap check on 2026-10-20: no open shading epic. The only open
  issue was #43, mesh-weight animation pointers and CUBICSPLINE tangents.
  Check again at readiness.

### Existing contracts this design must explicitly amend

| Contract | Current rule | Relationship to the requested capability |
|---|---|---|
| [Material styling D-22](material_styling_design.md#d-22-bands-come-from-ambient-light-only) | Bands come from ambient light only | Optional directional ramp shading needs an amendment |
| [Material styling D-25](material_styling_design.md#d-25-ambient-means-occlusion-and-curvature-only) | No sky, ground or other direction-dependent light | Additional terms need explicit scope and settings |
| [Lighting D-4](lighting_sheet_design.md#d-4-light-is-previewed-never-baked), [design §Previews](../design.md#export) | Light is previewed, never baked | Replace the universal restriction with the owner-approved output contract |
| Material styling D-27; lighting D-1 | Preserve the flat ambient capability | Compatible; exact default byte compatibility is Q-3 |
| [Alpha D-8](alpha_design.md#d-8-the-colour-is-flat-and-unlit-this-replaces-lighting-d-23) | Ordinary materials are flat and unlit | Preserve as the default; settle optional baking without a ramp |
| Material styling scope and ramp mapping | Dithering excluded | Dithering needs its own scope and visual decision |

These are known design changes requested by the owner, not defects to repair
silently. This draft changes no current contract document. Changes to
`docs/design.md` accompany implementation because tests read it.

### What the owner has actually judged

- [Material styling](../acceptance/material-styling.md): qualified proof of
  concept on 2026-10-08; generated ramps separately accepted on 2026-10-14.
  Neither is blanket approval of every future shading look.
- [Settings](../acceptance/settings.md): accepted 2026-10-13. The owner wanted
  a look between the two shade trials; that did not change shipped defaults.
- [Lighting](../acceptance/lighting-sheet.md): accepted 2026-10-14, including
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

The present assignment writes this design only: no production code, repository
tests, issues or labels. Local evidence probes are allowed by the dispatch.
The Codekarl repository is not an input and must not be read. Its palette
and project file come after this design.

## Decisions

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

## Proposals and open questions

Unresolved recommendations below are proposals, not approved decisions.
Batch 1's accepted answers are D-5 to D-7; batch 2's are D-8 to D-10;
batch 3's are D-11 to D-13; batch 4's are D-14 to D-16;
batch 5's are D-17 to D-19; batch 6's are D-20 to D-22.
No dependent formula or slice
ordering is adopted while its blocking questions remain open.

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
normal retention A. The snap target and composition rules remain open.

Batch 6 was posted on 2026-10-20 at 20:19:21 UTC in `#moskophoros`,
message `4swxhvrx6gwizmkgdv42qjviqi`, under the same request, against
draft `7bd4f74b00` and Probe 3's page hash above. It asks Q-11's snap target,
Q-11's ordinary/missing-ramp behaviour, and Q-10's exclusions. D-20 to D-22
record both snap targets, whole-palette fallback and the exclusions. The
extent of "either way" for ordinary shading still needs clarification.

Batch 7 was posted on 2026-10-20 at 20:48:30 UTC in `#moskophoros`,
message `44ggxjrpc5r923cgqn8t7vq5en`, under the same request, against
draft `3048600136` and Probe 4's page hash above. It asks Q-11's ordinary
shading clarification, Q-4's sky/ground frame and any narrow V-7 exception,
and Q-4's brightness range. These remain proposals pending the owner's
answers.

### Q-1. Does a mode route all shading or only the added light?

Resolved by D-5: option A, with neither as the fourth mode. The rejected
option B kept today's ambient ramp colour in every mode and routed only the
added light. Base-colour and missing-ramp details continue as Q-11; the
formula remains in Q-4. The answer does not approve a particular look.

### Q-2. How should baked light and preview light relate?

Resolved by D-6: option A. Alternatives not selected were one shared light
with a preview/bake destination, and separate controls that forbid an
additional lit preview while baking. The accepted separation preserves
existing `--light` meaning and deliberate hybrid lighting.

### Q-3. What remains identical, and what happens to reused sheets?

Resolved by D-8: option A, preserve default images and regenerate working
sheets once, keeping historical acceptance artifacts. Alternatives not
selected were a one-time JSON conversion, or changing the default look.
Old-schema loading was also offered in batch 1 and is not being added.

### Q-4. Which light terms, in which frame, and how are they combined?

Availability resolved by D-9 and the distant key by D-11. Still settle
whether sky/ground track world up or screen up under camera roll; whether the
live-lit project wants any sky term. Preserve D-4's camera-fixed key.
Define term weights, ambient combination, clamp order, and whether intensity
can brighten beyond the base. Present labelled probes before a look choice.

Batch 3 selected the distant key. Alternatives not selected were a point
bake key, and a key selectable between direction and position.

Combination family resolved by D-15: multiply the normalised ambient-form
signal by the lighting factor. The weighted-average alternative was not
selected. Probe 1 illustrated the product with
`e = a * clamp(.20 + .50*k + .20*s + .10*g, 0, 1)` and B with
`e = (a + k + .4*s + .2*g) / 2.6`. `a` is the range-normalised shade;
`k`, `s` and `g` are nonnegative key, sky and ground facing terms. These
weights have different meanings and are not equal-energy comparisons.
Weights and bounds will be specified separately, with a zero-new-terms path
preserving D-8 exactly. Selecting a family does not select these weights or
the live-lit project's sky setting.

**Batch 7, sky-frame proposal, not decided:** A (recommended) makes sky
camera screen-up and ground screen-down, following camera roll. This
preserves V-7's camera-fixed lighting rule. B makes these terms follow
subject/world up and its opposite; this needs the owner's explicit narrow
exception to V-7 for sky/ground. C offers both frames with camera as default
and the same explicit exception when world is selected. The key remains
camera-fixed under D-4 in all options. Probe 4 illustrates the difference;
no vision amendment is made before the owner decides.

**Batch 7, brightness-range proposal, not decided:** expose a floor and
ceiling for the linear RGB gain. A (recommended) keeps both in `[0,1]`,
with floor no greater than ceiling, so brightness only darkens or restores
the base. B permits a ceiling up to 4, still at least the floor, with the
floor in `[0,1]`; output channels clip at white. Ramp selection remains
limited to its entries; these gain controls affect brightness/both only.
Probe 4 illustrates ceilings 1 and 2. Defaults, exact formula and material
inheritance remain for the later complete settings contract.

### Q-5. Which controls may materials override?

Ownership resolved by D-10: project defaults and material mode/response
overrides, with a shared light arrangement. Today's material entries override ambient values
and ranges, and their own values beat global options. Define ordinary
materials, textured materials, library defaults, inheritance, warnings,
validation and inline reuse before choosing schemas or syntax.

The exact response fields depend on Q-4 and will be enumerated before
signoff; inheritance and the remaining schema details stay open.

### Q-6. What dithering belongs in this arc?

The owner requested “dithering/naturalness”; D-12 includes it in this arc,
off by default. Still settle which colour transitions it affects, its
pattern and strength, and its behaviour through motion, rotation, alpha
edges and mixed materials. Labelled comparisons are needed. Determinism
alone does not establish visual stability.

Deferring dithering to a later arc was not selected. Pattern and colour
rules follow through labelled probes.

Batch 4 offered 4×4, 2×2 or further investigation. D-16 instead asks for
an owner choice of patterns, potentially beyond those two. No fixed pattern
or exact catalogue was selected.
Both candidates choose adjacent ramp entries at output resolution and are
fixed to cell pixel coordinates. They leave alpha and geometry unchanged.
Packing does not shift the pattern, but moving surfaces pass through it.
The robot GIFs compare no dithering, both patterns at strength 0.5, and
4×4 at strength 1.0. The illustrated coordinate is `N*e`, perturbed by
`strength*(.5-threshold)` before flooring/clamping to the ramp. Exact
arithmetic and ranges remain to specify. The half-strength recommendation
is an example, not a shipped default; D-12 keeps dithering off by default.

Catalogue, controls and anchoring resolved by D-17, selecting batch 5's A.
Custom threshold files (B) and a different/subset catalogue (C) were not
selected. Exact strength limits, arithmetic and interaction with the new
optional brightness snap remain open.

### Q-7. Do outlines belong in this arc?

Resolved by D-13: defer outlines to a separate style arc. Including optional
outlines now was not selected. This does not decide later authored wood
texture, which is distinct from both outlines and dithering.

### Q-8. Where does the new operation sit in the pipeline?

After the behaviour is settled, define the addressed buffers and the
stylize operation. Existing high-resolution normals and shade may suffice
for some choices, but that has not been established for all modes,
perspective, material boundaries or the combined translucent front layer.
Respect V-4/V-8/V-10; keep pure colour operations outside Blender and do not
silently widen the deferred retained-capture recolouring command.

**Verified limitation:** design §Frames into stylize and
`capture.backend.decode_normal_depth` supply the front-most normal, the
front layer's where present, rather than a normal for each colour layer.
The existing shade has separate front/back values. Correctly applying
directional shading to both layers cannot simply reuse that single normal
for both: decide the required new capture data before finalising Q-8.
Probe 1 avoids translucent fronts and therefore does not resolve this.

Further code reading: `capture.blender_script.render_frame` already reads
the back render's normal and, when present, the front render's normal; it
then replaces the covered back values with the front values before writing
the one normal buffer. Retaining the two values is a data-output extension,
not inherently another ray-traced render. Its format, validation and default
image compatibility still need verification.

Per-layer normal retention and operation placement resolved by D-19,
selecting batch 5's A. Remaining pipeline details include sampling,
addressed buffer contracts and compatibility verification. The chest must
exercise the new path before visual acceptance.

### Q-9. What evidence completes the arc?

Settle a distinct owner visual-review slice covering both uses, the four
modes, relevant camera settings and motion. Choose review inputs and
configuration at that point, without treating the not-yet-authored Codekarl
palette as an available dependency. Mechanical verification must cover
reproduction, compatibility, alpha/map alignment, settings and errors.

### Q-10. What other boundaries and delivery order should be explicit?

Exclusions resolved by D-22: no cast shadows, coloured lights, multiple key
lights, specular highlights or retained-capture recolouring command in this
arc. Batch 6's alternative of adding named capabilities was not selected.
Once the remaining behaviour questions are resolved, propose one-PR
delivery slices and their dependencies for owner signoff. Ordering remains
open; outlines are separately deferred by D-13.

### Q-11. What colour is shaded when ramp selection is off or unavailable?

D-14 settles the base: last/lightest ramp entry for mapped materials, model
colour/texture for ordinary materials. Still define ramp/both on an ordinary or unmapped
material; whether missing ramps are errors or use an explicit fallback;
mixed-material snap precedence; and how palette mapping,
translucent composition and dithering interact. These choices must not
silently discard textures or invent a ramp. Present labelled examples for
colour choices before adopting a contract.

Batch 4 selected the library-base rule (D-14). The alternative of always
taking the model's captured base when ramp selection is off was not selected.
Probe 1 uses an explicit
teal assignment to make the rules distinguishable: the existing gold ramp's
last colour and the palette-mapped model colour happened to look alike.
This choice does not approve teal as a look, generated-ramp base handling
beyond the resolved entry, or any missing-ramp/palette-composition policy.

Default palette policy resolved by D-18, selecting batch 5's A with an
additional required snap option. Probe 2 displays the opaque/cutout
difference for snapping to the whole palette; its images do not validate
translucent composition or selecting only a material's ramp. Missing-ramp
policy and the exact optional snap contract remain open.

Snap targets resolved by D-20, choosing batch 6's C. Single-target choices
A/B were not selected. Missing-ramp snap fallback is recorded in D-21, but
the reach of "either way" into ordinary shading remains open. The batch 6
proposal preserved ordinary colour/texture without a resolved ramp, with
brightness alone in both mode; it must not silently become a decision.
Treating the entire palette as a shading ramp would be a different policy
and needs its own definition, especially for texture and colour ordering.

**Batch 7 clarification, not decided:** A (recommended) reads "the whole
palette, either way" as snap fallback only: without a resolved ramp, ramp
mode keeps ordinary colour/texture, both adds brightness to it, and either
enabled snap target uses the whole palette. B also requests new shading
through the whole palette for materials without ramps; that requires a
separate ordering/texture policy and an opt-in compatibility rule before
adoption. The question asks the extent of the answer, not whether the
already accepted whole-palette snap fallback is allowed.

## Verification strategy

Existing requirements are determinism, explicit validation, addressed stage
outputs, both edge rules, aligned maps and owner visual judgment. Proposed
new mechanical checks and a distinct visual review follow D-8 and Q-9. The
current [validation contract](../validation.md) will govern implementation;
this document-only exploration runs no repository tests.

## Delivery plan

No slices yet: Q-1 to Q-3 and Q-7 are resolved; Q-4 to Q-6 are partly
resolved; their remaining details and Q-8 to Q-11 remain open.
The processing ledger contains only
the proposed umbrella, matching that state. Final readiness requires the
owner's explicit signoff on behaviour, scope and dependency-ordered slices.
Codex review and tracker processing follow on the manager's instruction.

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
  No readiness signoff has been received.
