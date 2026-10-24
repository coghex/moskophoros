# Game-ready export formats design

Design configurable frame folders, per-clip atlases, stored direction subsets
with runtime mirroring, and clip sampling for a general-purpose renderer.
The approved acolyte is the external acceptance model; no consumer names,
paths or private formats belong in production code, defaults or tests.

Design state: `exploring`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [ ] EPIC. Export configurable game-ready frames and clip atlases

No child slices are defined yet. The owner has established the consumer
boundary, timing scope and compatibility contract. Direction and output
details, acceptance scope and delivery boundaries remain open.

## Epic contract

- **Goal:** render a model using project settings into reusable images and
  metadata, with explicit clip timing, directions, scale and ground anchor.
- **Done when:** pending owner decisions. Proposed completion is the agreed
  generic export contract implemented, mechanically verified, and reviewed
  visually by the owner using the approved acolyte beside current sprites.
- **Users and operators:** artists and developers rendering subjects for games.
- **Arc label:** None proposed.

## Authority and source material

Request `moskophoros-20261024-1`, dispatched by the manager on 2026-10-24 in
`~/.local/state/project-manager/moskophoros/dispatch-export-format-design.md`.
The verified `mosk-manager` chat record
`wuihstigu7bmbb8e4e56cpb53w` confirms the owner selected this design session.
The brief quotes the owner's choice as **"Design the export format
(Recommended)"**, after approving the acolyte. This authorizes exploration,
not the options proposed below. Every subsequent approved choice will record
the owner's exact words, date and relay message ID or "in the designer's pane".

The endpoint is an owner-signed design ready for `process-design-doc`.
This session writes no implementation or repository tests and files no issues.
Only this design document changes in the repository. Local probes and review
pages live under `~/.local/share/moskophoros-acceptance/export-format-design/`.
Consumer repositories and existing acceptance evidence remain read-only.

## Verified current state and evidence

Inspected on 2026-10-24 at moskophoros
`9d182393e8d020099186a99771841f0730bc1645` and Synarchy
`047832b6b5be3f810b7bafed47aea64073ee2f3f`.
The open moskophoros tracker contains only #43, mesh-weight animation and
CUBICSPLINE support; no overlapping export epic was open at this check.

### Existing moskophoros contracts

- [Vision](../vision.md) V-1 forbids consumer integration and private layouts;
  V-2 requires reproducibility; V-4 keeps addressed-frame stage boundaries;
  V-7 requires stable scale and anchor; V-9 identifies samples by time;
  V-12 reserves visual acceptance to the owner.
- [Design](../design.md), CLI and Export: the positional output is a PNG;
  one combined sheet has a row per clip and direction, columns per frame,
  transparent unused cells, and no gaps. Normal and optional depth maps use
  the same layout. JSON is `moskophoros.sheet/15`; previews are separate.
  Outputs are staged, published together and rolled back on publication
  failure. Only files written by the run are replaced; stale files remain.
- `src/moskophoros/export.py` (`encode`, `sheet_settings`, `SCHEMA`) implements
  this combined sheet. `sampling.py` (`count`, `sample`, `frames`) supplies
  addressed frames; `settings.py`'s `CLIP_SCHEMA` currently accepts `frames`.
- Per-clip frame counts **already exist** as `clips.NAME.frames`. Counts can
  be an integer, `auto`, or `null` to inherit the global count. `fps` is
  global. With an explicit N, each frame lasts `1/fps`; the clip is retimed.
  A loop samples `t0 + k*d/N`, excluding the duplicate endpoint. A one-shot
  with N >= 2 includes both endpoints. Static and zero-duration clips stay
  one frame. See design, Clips and sampling, and historical settings D-13,
  D-24, D-31 and D-33 in
  [settings design](../archive/designs/settings_design.md).
- Fixed `ppm`, `cell` and `ground_px` already exist. The anchor is an integer
  pixel-grid corner from cell top-left. A fixed configuration that overflows
  fails rather than shrinking. No new fitting mechanism is established here.
- Directions currently form an evenly spaced ring, with index i at
  `(start + i*360/N) mod 360`. At zero camera roll: 0 is south, 45 south-east,
  90 east, 135 north-east, 180 north, 225 north-west, 270 west, 315 south-west.
  Compass labels are present only at exact multiples of 45 degrees. Labels
  do not change with roll. Export uses index order, not compass-name sorting.
- Settings layers are defaults, global file, reused sheet, project, flags.
  Project names and settings-file paths are not recorded in output. Reuse
  accepts only the current sheet schema; a schema bump retires the previous
  one. See design, Settings files, and historical
  [projects/camera design](../archive/designs/projects_camera_design.md).

### Consumer evidence, not a tool specification

Read-only source root: `~/work/synarchy/`. Asset root:
`assets/textures/units/acolyte/`.

- `animations/<clip>/<direction>/frame_NNN.png`: 54 clips, 2,250 PNG frames,
  all **48x48**. Walk has six frames per stored direction; idle has four.
- 46 clips store north, north-east, east, south-east and south. Eight clips
  also store the three western directions. All eight are the `_RH_dagger`
  attack, combat-idle and hit-react clips, including their injured variants.
- `atlas/index.json` is a **consumer-specific** schema, version 2, with unit
  identity, asset paths, source and atlas digests, playback and direction
  records. Every frame occupies a 50x50 physical slot: a 48x48 logical cell
  with a one-pixel extrusion border (edge texels copied, including corners).
  A read-only Python/Pillow/NumPy probe compared every one of the 2,250 slots
  against its source frame plus edge padding: zero mismatches.
- Columns are frames in ascending `frame_NNN` order. Full row order is south,
  south-west, west, north-west, north, north-east, east, south-east, filtering
  out absent directions. The five-row order is consequently south, north,
  north-east, east, south-east. It is not folder alphabetical order and it
  differs from moskophoros's current angle order.
- Examples: walk is 300x250, idle 200x250, `attack_heavy_unarmed` 450x250,
  and `attack_quick_RH_dagger` 250x400. `portrait.png` is 32x32.
- `data/units/acolyte.yaml` declares walk at 8 FPS, looping and mirrored;
  idle at 6 FPS, looping and mirrored; quick right-hand dagger attack at
  12 FPS, non-looping and not mirrored. Handedness follows the explicit
  per-animation `flip` field, not a runtime `_RH_` name heuristic.
- `src/Unit/Atlas/Load.hs`, `Index.hs` and
  `src/Engine/Scripting/Lua/API/Units/Yaml.hs` load compiled atlases only.
  They validate the private index against declarations, source pixels,
  extrusion borders and digests. Dropping in a generic atlas alone is not
  enough. `tools/pack_atlas.py` owns that consumer compilation boundary.
- `src/Unit/Render.hs:131` gates runtime mirroring on `aFlip`; a missing
  western view reads its eastern counterpart and flips horizontally.
- `src/Unit/Render.hs:257` derives quad dimensions from logical frame size.
  Its placement centers horizontally and sets the ground at image height
  minus `base_width/2`. With `base_width: 8` and 48x48 cells, this implies a
  **(24,44)** logical pixel-corner anchor. This is an inference from the
  renderer and declaration, not metadata embedded in the old art and not
  an owner-approved setting for the new model.

### Approved model and reproducible evidence

The handoff `~/.local/share/moskophoros-acceptance/acolyte-model/CHANGES-2026-10-24.md`
identifies approved refine6: `physics-v2/acolyte.glb`, its editable `.blend`,
`library-v4.yaml`, and `page-refine6/index.html`. GLB SHA-256:
`ae74abd5fd982f8ed85b71dcd3c1f32b43e53a604c1649f4ca4c1f6439e91c02`.
It has in-place walk (one second) and idle (two seconds), a Rigify rig and
baked skirt-bone motion. The duplicate cycle endpoint exists and matches;
sprite sampling excludes it. The bake does not require the physics add-on
at render time.

Approved `render-physics2/*-game/acolyte.json` records 24 px/m, global 12 FPS,
ground pixel (11,40), and fitted cells: walk 22x45 with 12 samples, idle
22x43 with 24 samples. These are not existing 48x48 deliverables. The walk
command uses four directions at 0,90,180,270 degrees. New acceptance must
cover the agreed stored directions, cell and anchor explicitly.

The brief's required diff check, `git diff --stat 354a21f origin/master --
src pyproject.toml requirements.lock`, was empty. Its pinned acceptance
tool can therefore support later probes. No new Blender render has run in
this design session. Any such run must use the shared lock and headless
factory-startup flags, and copy inputs rather than overwrite evidence.

## Desired experience and scope

The owner's selected direction is a generic project-configured export that
can reach per-clip/per-direction frame folders, subsets with mirroring and
clip-specific sampling. The request also asks to design per-clip atlases.
The output choices and consumer handoff are approved in D-1 below.

Established constraints: no game-specific branches or fixtures; no consumer
file writes or configuration edits in this design session; no model
refinement; no production code or tracker creation. Portrait generation,
extra clip naming features and automatic stale-output removal have not been
accepted into or excluded from implementation scope.

## Design directions approved in round 1

### P-1. Generic exports, consumer-owned compilation

Adopted by D-1. Retained proposal ID for the round-1 record.

Make frame folders and per-clip atlases independently selectable, with both
available in one run and an optional combined sheet. Record generic metadata
even when the combined sheet is disabled. Configure names, paths, row order
and atlas padding through project settings. For the test consumer, export
frames and let its existing compiler produce its private index and runtime
atlases. Do not teach moskophoros the consumer's schema or digest rules.
This makes generic atlases useful to other consumers without claiming they
replace this game's compilation step. Exact settings and CLI remain open.

### P-2. Add per-clip FPS without changing frame-count meaning

Adopted by D-2. Retained proposal ID for the round-1 record.

Keep existing frame-count retiming and add a per-clip FPS override. A
one-second walk with six frames at 6 FPS lasts one second; six at 8 FPS lasts
0.75 seconds, matching the current game's cadence. A two-second idle with
four frames at 2 FPS preserves two seconds, while four at 6 FPS matches the
old game's two-thirds-second cadence. These numbers explain behavior; none
is selected for the approved model. Preview cadence requires owner review.

### P-3. Preserve default images, explicitly version metadata

Adopted by D-3. Retained proposal ID for the round-1 record.

Keep today's combined-sheet default, sampling, image layout, map and preview
bytes when no new option is used. Permit JSON and fingerprint changes for
the new recorded settings and schema. Continue the owner's current-schema-
only reuse policy instead of adding compatibility modes. A promise of
byte-identical JSON conflicts with an unconditional schema bump; that part
of the brief needs a precise choice. Exact schema identity remains open.

## Decisions

### D-1. Selectable generic exports; consumer-owned private compilation

Owner signoff on 2026-10-24, via verified `mosk-manager` relay
`c3csfyvkcf4anp6jc2nup8s382`, explicitly answering round-1 question message
`eb4vudqbjg5ryipmrc9dvqki2w`. The owner chose:

> "A: folders, atlases or both"

The relay confirms this is option A as described on `round-01/index.html`.
P-1 is adopted: independently selectable frame folders and per-clip atlases,
both in one run, optional combined sheet, generic metadata and configurable
paths, order and padding. The game retains its compiler and private index.
The frame-folders-only first arc is rejected in favor of the requested
complete format scope. This affects export, metadata, settings and acceptance;
it does not yet settle the CLI or template grammar.

### D-2. Per-clip FPS with existing frame-count retiming

Owner signoff on 2026-10-24 through the same verified relay and question:

> "A: per-clip fps"

P-2 is adopted. Add per-clip FPS and preserve the current explicit-count
meaning; do not add a separate source-duration-preserving sampling mode.
Actual acceptance-model cadence is still open. This affects sampling,
settings, metadata/reuse and preview timing. Global-FPS-only was rejected
because clips need independent playback rates.

### D-3. Default image compatibility, versioned JSON

Owner signoff on 2026-10-24 through the same verified relay and question:

> "A: images unchanged"

P-3 is adopted: preserve default sheet/map/preview bytes when no new feature
is selected, allow the schema, JSON and fingerprint to change, and retain
current-schema-only reuse. No legacy JSON compatibility path is added.
This affects every new setting's recording, reuse and regression checks;
the exact schema identity remains open.

## Round-2 proposals awaiting owner signoff

These are configuration and behavior choices, not approval of a mirrored
acolyte's appearance. The actual five-view look and cadence remain Q-6.

### P-4. Ordered subsets of the existing direction ring

Keep the current direction count and start angle as the definition of the
view's ring. Add an ordered list of stored direction indices, globally and
overridable by exact clip name. Default: all directions in current order.
An override replaces the list as a whole; no wildcard or regular-expression
clip matching and no special handling for hand or weapon names.

For eight directions starting at zero, `[0,4,3,2,1]` stores south, north,
north-east, east and south-east in that order, matching the consumer's five
atlas rows. An asymmetric clip can explicitly select `[0,7,6,5,4,3,2,1]`.
These are project-authored examples, never tool defaults. Direction 4 stays
direction 4 in frame addresses even if it becomes the second exported row.

Use the existing compass label for output names when present, otherwise a
numeric name; allow a project to give explicit output-name aliases by index.
An alias changes the path name, never the angle, index or physical meaning
of the existing compass label in metadata. Reject duplicate stored indices
and colliding output names. Measure and render only stored directions, using
one common resolved scale, cell and anchor for all selected clips. Fixed
scale/cell/anchor settings remain the way to keep independent runs aligned.

Alternative: add clip-name patterns as well as exact overrides. This is not
recommended for the first arc because matching precedence and accidental
asymmetric mirroring would become extra user-visible rules. Per-clip exact
entries already fit the settings model and are easy to inspect.

### P-5. Explicit runtime mirror references, no generated mirror files

For each clip, record optional mappings from an omitted direction index to
a stored source index plus a horizontal-flip operation. A global mapping may
be replaced per clip; an empty mapping disables it for asymmetric clips.
At eight directions, example mappings are 7 from 1, 6 from 2 and 5 from 3.
Each source must be stored and each target omitted; no chains, cycles or
automatic inference of symmetry. A view may simply be absent with no mirror
mapping. The exporter does not render or write duplicate images for aliases.

The generic manifest distinguishes real samples from derived views, records
the source sample identity, and describes how to mirror the image, anchor
and maps. A horizontal flip moves a pixel-corner anchor from `(gx,gy)` to
`(W-gx,gy)`; camera-space normals require the X component negated, while
depth values move with their pixels. Thus a consumer cannot correctly mirror
normal maps merely by reversing their texel order. The exact encoding and
metadata fields belong to the later technical contract checkpoint.

This is an author declaration of an acceptable 2D substitute, not proof that
a 3D model, animation, camera or baked light is symmetric. Owner visual
review must compare the chosen substitutes. Synarchy's compiler and YAML
remain its authority for its own runtime mirroring; moskophoros writes no
game declarations and does not claim the game reads this generic manifest.

Alternative: omit mirror relationships entirely and export only the subset;
leave every missing-view relationship to the consumer. That is simpler, but
the generic result then cannot describe a complete intended view set. Files
containing synthesized mirrored pixels are not proposed for this arc.

### P-6. A directory output mode with relative templates

Keep `moskophoros [options] model.glb output.png` working as today. Add an
explicit directory-output form, illustrated as
`moskophoros --project look --output-dir OUT model.glb`, mutually exclusive
with the positional output PNG. The directory mode selects frame folders,
per-clip atlases, a combined sheet or any combination through settings, and
always writes generic metadata. It does not imply a private consumer layout.

The invocation supplies the destination root. Project settings supply relative
templates for the files under it, with clip, direction, frame index and map
kind available as appropriate. For example, a project could request
`animations/{clip}/{direction}/frame_{frame:03}.png` and `atlas/{clip}.png`.
Indices start at zero; width three means minimum width, not a 999-frame cap.
No absolute paths, parent traversal or collisions are allowed in templates.
Resolved output is confined to the chosen root. Root location is not part of
the fingerprint, so moving an otherwise identical export does not change it.

This checkpoint chooses the directory-root interface and configurable relative
paths. The exact settings keys, supported tokens and format grammar, default
paths, manifest filename/schema, existing-directory policy, map suffixes and
transactional publication contract will be enumerated for signoff next.

Alternative: keep requiring a positional `output.png` even when no combined
sheet is wanted, using its parent and stem to name metadata and all export
folders. This preserves one invocation shape but asks the user to name a
PNG the tool may deliberately not write.

## Open questions

### Q-1. Output choices and consumer boundary

Resolved by D-1.

### Q-2. Clip timing

Resolved by D-2. Actual acolyte counts and cadence remain under Q-6.

### Q-3. Default compatibility

Resolved by D-3.

### Q-4. Direction subsets, names and mirroring

Round 2: A (recommended), adopt P-4's ordered index subsets, exact per-clip
overrides, explicit naming aliases and stored-view-only measurement/rendering;
or B, add clip-name patterns too? Mirror representation has its own explicit
checkpoint Q-8 below. Actual five-view acceptance still needs Q-6's labelled
visual evidence. Exact settings syntax remains part of Q-9.

### Q-5. Output paths, maps, naming and publication

Round 2: A (recommended), adopt P-6's new directory-output mode and relative
templates while retaining the old PNG invocation; or B, retain a mandatory
output PNG argument even for exports with no combined sheet? This settles
the interface direction; Q-9 retains the detailed output contract.

### Q-6. Acceptance cell, anchor and optional outputs

Unasked. Visually compare a fixed cell and explicit anchor at the accepted
scale; decide portrait scope, actual clip counts/cadence and normal/depth
use. Keep the approved model as input. A dedicated owner visual-review slice
is required by the brief but its scope depends on these answers.

### Q-7. Delivery and readiness

Unasked. Set one-PR slice boundaries and dependency order only after the
blocking behavioral decisions. Obtain separate readiness signoff. Recheck
tracker overlap at readiness. A document publication is not design approval.

### Q-8. What does runtime mirroring mean in the export?

Round 2: A (recommended), adopt P-5's explicit mirror references in generic
metadata, with per-clip replacement/disable and no generated duplicate PNGs;
or B, store only the subset and leave mirror relationships entirely outside
the export? This is not visual signoff on any model's symmetry.

### Q-9. Detailed settings, metadata and output contract

Unasked; depends on Q-4, Q-5 and Q-8. Set settings keys and layer merge/reset
semantics, per-clip FPS override validation and interaction with global flags,
clip output-name mapping, templates and file validation, atlas padding,
map alignment/naming, preview policy, manifest schema and settings reuse,
and all-or-nothing publication including stale-file behavior. These choices
must be explicit before affected slices become ready for issue processing.

## Verification strategy

Proposed families, to refine with the accepted contract: pure sample and
direction mapping; settings precedence and reuse; frame/atlas pixel equality,
padding and map alignment; stable frame addresses; deterministic metadata and
paths; invalid templates and collisions; overflow and publication rollback;
unchanged default image bytes; generated-fixture Blender integration; and a
separate owner visual review of the approved model beside current sprites.
Real consumer assets stay local acceptance evidence, never repository tests.
Implementation follows [validation](../validation.md) and its planner-selected
groups, including current-commit local Blender evidence when selected.

## Delivery plan

Zero child slices yet. Decomposition waits on the unresolved questions. The processing
ledger will mirror the eventual dependency-ordered plan exactly.

## Conversation cursor

Round 1 resolved Q-1, Q-2 and Q-3 as D-1, D-2 and D-3. Local text decision page:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-01/index.html`.
This is a new round folder, not an alteration of the approved model review.
No visual preference was requested in that round. Later visual questions need
labelled comparison images grouped by decision. The verified manager relay
`c3csfyvkcf4anp6jc2nup8s382` carries the owner's signoff dated 2026-10-24.
Next: direction selection, mirror representation and output configuration.

Round 2 asks Q-4, Q-8 and Q-5, in that order. New round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-02/index.html`.
No visual approval is requested here. P-4, P-5 and P-6 remain proposals until
the owner answers. After these answers, settle Q-9 and Q-6 before the final
dependency-ordered slices and readiness signoff; the three-question limit
does not silently resolve the remaining choices.
