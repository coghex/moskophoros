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

## Desired experience and settled scope

The owner chooses project settings to generate either:

1. Eight-direction, high-angle isometric sprites, no outline, with internal
   ambient colour variation and geometry maps for live lighting.
2. Straight-on panels with lighting baked into material ramps, without an
   additional brightness multiplication for that project.

The tool also supports brightness shading, the combination, and neither
shading operation. All four modes belong in settings (D-5). These are generic
controls, not game-specific code or shipped presets.
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
in settings. The setting name, shipped value, per-material overrides, base
colour, missing-ramp behaviour and numerical formula are not yet decided.
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
The answer does not explicitly select a regeneration procedure, JSON-only
conversion, old-schema loading support or the exact default-image guarantee.
Those details remain open in Q-3. No sheet is changed during this design turn.

The manager separately suggested reading this as no migration code plus
regeneration at the schema bump, and explicitly marked that interpretation
non-binding. It is the recommendation in the follow-up, not an owner decision.

## Proposals and open questions

Unresolved recommendations below are proposals, not approved decisions.
Batch 1's accepted answers are D-5 to D-7. No dependent formula or slice
ordering is adopted while its blocking questions remain open.

Batch 1 was posted on 2026-10-20 at 16:52:53 UTC in `#moskophoros`,
message `w8y5pdsiqbn56f33gpftcxhsmi`, request
`moskophoros-20261020-1`, against this draft at `07a7180c79`.
It explicitly asks for independent answers to Q-1, Q-2 and Q-3.

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

- **A, recommended follow-up to D-7:** retain today's default look, with new
  directional terms off and existing settings unchanged; preserve every image
  byte: colour sheet,
  maps, regular previews and lit previews, including the ordinary look.
  New recorded settings change the JSON and fingerprint. Bump the sheet
  schema and retain the existing current-schema-only loading policy;
  regenerate the owner's existing working sheets once when implementation
  lands, while a new sheet reloads byte-identically. Inventory those sheets
  and their reproducible inputs before that work; keep historical acceptance
  artifacts as evidence. This proposes no automatic edit of the owner's
  project files during design.
- **B:** the same image guarantee, but convert existing sheet JSON once
  instead of regenerating; this needs its own conversion and verification
  contract and is not assumed safe by merely changing the schema string.
- **C:** allow the default images to change; this would need a separate
  explicit look decision and visual acceptance.

The precise schema version and library changes follow the settled design,
not an assumed number here. Old-schema loading was an alternative in batch 1
but was not explicitly selected. D-7 authorises the sheet update; this
follow-up clarifies its method and the still-unconfirmed image guarantee.

### Q-4. Which light terms, in which frame, and how are they combined?

Settle a camera-fixed key, sky and ground terms; a point versus distant key;
whether sky/ground track world up or screen up under camera roll; whether the
live-lit project wants any sky term. Preserve D-4's camera-fixed key.
Define term weights, ambient combination, clamp order, and whether intensity
can brighten beyond the base. Present labelled probes before a look choice.

**Batch 2 asks availability only:** A, recommended, independently switchable
key, sky and ground terms alongside the existing ambient form; B, key only
in this arc and sky/ground later; or C, another explicitly named subset.
This selects the controls to design, not strengths, coordinates or a look for
either project. Those remain for subsequent questions and labelled probes.

### Q-5. Which controls may materials override?

Settle project-level controls and material-level response, including whether
mode varies by material. Today's material entries override ambient values
and ranges, and their own values beat global options. Define ordinary
materials, textured materials, library defaults, inheritance, warnings,
validation and inline reuse before choosing schemas or syntax.

**Batch 2 asks ownership:** A, recommended, the project supplies a default
mode and shared light arrangement, and each material may override its mode
and shading-response strengths; B, all new controls apply to the whole
subject, with no material overrides. A permits an unshaded glow beside a
shaded body without giving each material a different light position.
It follows today's library ownership of material-specific appearance.
The exact response fields depend on Q-4 and will be enumerated before signoff.

### Q-6. What dithering belongs in this arc?

The owner requested “dithering/naturalness”; the previous arc excluded it.
Settle whether it enters now, which colour transitions it affects, its
pattern and strength, and its behaviour through motion, rotation, alpha
edges and mixed materials. Labelled comparisons are needed. Determinism
alone does not establish visual stability.

### Q-7. Do outlines belong in this arc?

The live-lit use explicitly has none. Settle whether the baked use wants
outlines now or leaves them for a later arc; do not infer that from “works
of art”. Similarly distinguish dithering from later authored wood texture.

### Q-8. Where does the new operation sit in the pipeline?

After the behaviour is settled, define the addressed buffers and the
stylize operation. Existing high-resolution normals and shade may suffice
for some choices, but that has not been established for all modes,
perspective, material boundaries or the combined translucent front layer.
Respect V-4/V-8/V-10; keep pure colour operations outside Blender and do not
silently widen the deferred retained-capture recolouring command.

### Q-9. What evidence completes the arc?

Settle a distinct owner visual-review slice covering both uses, the four
modes, relevant camera settings and motion. Choose review inputs and
configuration at that point, without treating the not-yet-authored Codekarl
palette as an available dependency. Mechanical verification must cover
reproduction, compatibility, alpha/map alignment, settings and errors.

### Q-10. What other boundaries and delivery order should be explicit?

Confirm whether cast shadows, coloured lights, multiple key lights,
specular highlights and retained-capture recolouring remain outside this
arc. They are not implied by “baked light”. Once these boundaries and the
previous questions are resolved, propose one-PR delivery slices and their
dependencies for owner signoff.

### Q-11. What colour is shaded when ramp selection is off or unavailable?

D-5 settles routing, not the base colour. Define the base for brightness and
neither: the model's unlit colour/texture, a library-authored base, or a
specified ramp entry. Also define ramp/both on an ordinary or unmapped
material; whether missing ramps are errors or use an explicit fallback;
whether brightness may leave the palette; and how palette mapping,
translucent composition and dithering interact. These choices must not
silently discard textures or invent a ramp. Present labelled examples for
colour choices before adopting a contract.

## Verification strategy

Existing requirements are determinism, explicit validation, addressed stage
outputs, both edge rules, aligned maps and owner visual judgment. Proposed
new mechanical checks and a distinct visual review are Q-3 and Q-9. The
current [validation contract](../validation.md) will govern implementation;
this document-only exploration runs no repository tests.

## Delivery plan

No slices yet: Q-1 and Q-2 are resolved; Q-3 to Q-11 remain open. The processing ledger contains only
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
  answers and their limits. No readiness signoff has been received.
