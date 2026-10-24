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
- [ ] EXP-1. Plan per-clip sampling and stored directions
- [ ] EXP-2. Resolve export settings, names and output paths
- [ ] EXP-3. Encode frame files and clip atlases from addressed frames
- [ ] EXP-4. Record and reload the generic export manifest
- [ ] EXP-5. Publish nested output files with rollback
- [ ] EXP-6. Connect directory exports to the command pipeline
- [ ] EXP-7. Review the implemented acolyte export with the owner

Seven proposed slices, awaiting Q-7 signoff. Generic behavior, contracts,
base-acolyte directions, timing and portrait scope are decided. Q-14 and
Q-15 affect only the final owner-review slice; the plan does not assume
their answers or add model rework to implementation.

## Epic contract

- **Goal:** render a model using project settings into reusable images and
  metadata, with explicit clip timing, directions, scale and ground anchor.
- **Done when:** all approved output combinations work from project settings;
  defaults preserve image bytes; the current manifest reproduces the export;
  path, overflow and publication failures satisfy the contract; planned
  automated checks pass with current local Blender evidence; and the owner
  approves the implemented base-acolyte export beside old sprites in EXP-7.
  Acceptance input/placement follow the answers to Q-14/Q-15.
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
tool can therefore support the design probes. The check was repeated before
round 4 and remained empty. The round-4 render below used the shared lock and
headless factory-startup flags, with copied model/library inputs and fresh
output paths rather than overwriting evidence.

### Round-4 local probes, not implementation acceptance

These probes use the then-approved `physics-v2` model. After viewing them,
the owner requested model/look revisions in a separate workstream. Preserve
the probes as historical export evidence; they are not approval of the
model/look for the final export review. See D-10 through D-12 and Q-14.

All paths below are relative to
`~/.local/share/moskophoros-acceptance/export-format-design/round-04/`.

- `render_probe.py` copies the approved model and library into `inputs/` and
  invokes the pinned tool under `/usr/bin/lockf -k` with the shared lock.
  `render/command.txt` preserves the exact command; `render/inputs.json`
  records input hashes, and `render/run.log` records the result. It rendered
  both clips at 24 px/m, 48x48, ground (24,44), eight directions, and 12 FPS.
  Exit 0, no overflow. Only the three already-known skin-ramp override
  warnings appeared. No repository tests were run for this documentation task.
- `render/acolyte.json` is today's `moskophoros.sheet/15`, with 12 walk frames
  and 24 idle frames in every direction. Model SHA-256 matches the approved
  handoff above. This is not the proposed new export schema or implementation.
- `build_comparisons.py` cuts cells using JSON rectangles. It compares actual
  SW/W/NW samples with horizontally mirrored SE/E/NE at the same sample times.
  For lit comparisons it reverses depth pixels and negates the encoded normal
  X component before lighting, retaining alpha and the centered anchor.
  The comparison page places actual views above derived views in a single
  synchronized animation; it also shows flat colour separately.
- The walk is not pixel-symmetric: across 36 compared western-view samples,
  5,604 RGBA pixels differ, including 3,403 alpha pixels. Idle's 72 comparisons
  differ at 1,924 RGBA pixels, including 866 alpha pixels. These are counts
  of differences, not visual-quality verdicts or an error in mirroring.
- Timing variants use every second walk frame (six samples) or every sixth
  idle frame (four samples). The source times cover the authored loop without
  the duplicate endpoint. GIF generation uses the current tool's colour and
  timing routines, with no palette reductions. Its 10-ms delay rounding means
  intended versus displayed loop durations differ; the page states both.
- `build_mockup.py` builds option-A frame folders and per-clip atlases for
  colour/normal/depth under `q6/option-A-layout/`. Five stored directions,
  six walk or four idle frames, and one-pixel extrusion give 300x250 and
  200x250 atlases. All 150 emitted frame/map files were compared with their
  padded atlas slots: exact decoded pixel equality including borders. The
  local `mockup-plan.json` is explicitly marked as a design mockup; no fake
  production manifest or consumer index is emitted.
- `comparison-evidence.json` records timings, comparisons and output hashes.
  `index.html` links each question to its own image directory, `q6/`, `q12/`
  or `q13/`. No browser was opened; the owner receives the exact file link.

## Desired experience and scope

The owner's selected direction is a generic project-configured export that
can reach per-clip/per-direction frame folders, subsets with mirroring and
clip-specific sampling. The request also asks to design per-clip atlases.
The output choices and consumer handoff are approved in D-1 below.

Established constraints: no game-specific branches or fixtures; no consumer
file writes or configuration edits in this design session; no model
refinement; no production code or tracker creation. Clip output-name mapping
is included (D-7); automatic stale-output removal is excluded (D-9).
Portrait-specific generation is excluded (D-12). Model/look rework belongs
to a separate request and is not an export delivery slice.

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

### D-4. Ordered direction lists and exact per-clip overrides

Owner signoff on 2026-10-24, via verified `mosk-manager` relay
`kxtwp9nj4gdsdhmdnk28wjaezn`, answering round-2 message
`g84eyq3qefmj2y6dfxpj9ntt9a`. The owner chose:

> "A: lists + per-clip"

The relay explicitly adopts P-4 on `round-02/index.html`: ordered original
indices, exact per-clip replacement, output aliases, stored-view-only
measurement and rendering, and a common scale/cell/anchor. Pattern-based
clip matching is excluded from this arc. Frame indices are not direction
identities; reordering an exported row never renumbers its direction.

### D-5. Runtime mirror records without duplicate PNGs

Owner signoff on 2026-10-24 through the same verified relay and question:

> "A: mirror records"

P-5 is adopted: explicit omitted-target-to-stored-source relationships,
replaceable or disabled per clip, recorded in generic metadata with anchor
and map transforms. No automatically inferred symmetry, mirror chains or
generated mirrored PNGs. Visual acceptability remains for owner review.

### D-6. Directory output and relative templates

Owner signoff on 2026-10-24 through the same verified relay and question:

> "A: --output-dir OUT"

P-6 is adopted: mutually exclusive directory and legacy positional-PNG
output forms; project-controlled relative templates; no destination escape
or collisions; destination location excluded from the fingerprint. The
alternative requiring a phantom PNG name is rejected. The detailed contract
checkpoint below settles names, settings, metadata and publication.

## Design directions approved in round 2

These are configuration and behavior choices, not approval of a mirrored
acolyte's appearance. The actual five-view look and cadence remain Q-6.

### P-4. Ordered subsets of the existing direction ring

Adopted by D-4. Retained proposal ID for the round-2 record.

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

Adopted by D-5. Retained proposal ID for the round-2 record.

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

Adopted by D-6. Retained proposal ID for the round-2 record.

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

### D-7. Settings, paths and image layout contract

Owner signoff on 2026-10-24, via verified `mosk-manager` relay
`zrbvdx42r5mqc9vwavgcrkvbfn`, answering contract-checkpoint message
`wxpznwr7zxj78abmr7na4kx766` after the complete contracts were summarized
with the round-03 link. The owner chose:

> "A: approve P-7"

P-7's five enumerated parts are adopted: settings/merging/timing, names,
formats/templates, image/map layout, and stored-view previews. This approves
the exact configuration contract, not the illustrative acolyte values.

### D-8. One generic export metadata schema

Owner signoff on 2026-10-24 through the same verified relay and question:

> "A: approve P-8"

P-8 is adopted in full: `moskophoros.export/1` in both command forms, ordered
artifacts and sample locations, mirror semantics, deterministic recording
and complete settings replay. Distinct current sheet and bundle schemas are
rejected. Earlier sheet schemas stop loading as D-3 already authorized.

### D-9. Replace written files and retain old files

Owner signoff on 2026-10-24 through the same verified relay and question:

> "A: overwrite, keep old"

P-9 is adopted in full, including preflight, path confinement, staging,
manifest-last publication and rollback limitations. The relay explicitly
records that the owner was told a shorter rerun leaves old frames that a
folder-scanning game would pick up. No managed pruning or empty-root-only
restriction is added. Fresh acceptance roots avoid stale-file ambiguity.

## Contracts approved in round 3

P-7, P-8 and P-9 were approved as D-7, D-8 and D-9. Their identifiers remain
for the approval record. They do not approve the acceptance model's appearance. All new
settings below follow the existing defaults/global/reuse/project/flags order.

### P-7. Settings, paths and image layout

Adopted by D-7.

**1. Settings shape and defaults.** The new top-level values are
`stored_directions: all`, `direction_names: {}`, `mirrors: {}` and `export`.
The first is `all` or a nonempty ordered list of distinct integer indices.
`direction_names` maps integer indices to filename aliases. `mirrors` maps
integer target indices to integer stored-source indices. Each of those three
settings replaces whole across layers; an empty name/mirror mapping clears
it, and `all` resets direction selection. Global `null` is invalid.

Each `clips.NAME` entry may contain `frames` (unchanged), `fps`,
`stored_directions`, `mirrors`, and `output_name`. The new fields default to
`null`: inherit the global value, or use the source clip's cleaned name for
`output_name`. A per-clip `all` overrides a restricted global direction list;
an empty per-clip mirror map disables inherited mirrors. Omitted leaves
inherit across layers; explicit `null` clears the lower per-clip override.
Entries merge by clip name **and leaf**, so changing FPS preserves that
clip's lower-layer frame count. Alias maps use integer YAML keys, not string
digits. New settings are files-only except `--formats` below.

`fps` is finite and greater than zero, just like the global value. A clip's
own FPS beats global FPS even when the latter comes from `--fps`; it controls
both automatic sampling and the duration of explicitly counted frames.
Existing loop, one-shot and zero-duration formulas use that resolved FPS.
An explicit project/global-FPS flag shadowed by selected clips' own FPS
gets one warning listing those clips, following the frame-count precedent;
defaults, global-file values and reused values do not warn. Unlike count
overrides, FPS overrides matter to the duration of a still too.

Unused clip entries remain syntax/type checked without warnings, as today.
Integer direction keys/values must be in 0..63 at read time. After merging,
every selected clip's resolved indices must exist in the actual view;
mirror sources must be stored and targets omitted. Direction-name keys
must exist in the actual view. Nothing is silently dropped when `--view`
or `--directions` changes. Settings errors identify file, key and location;
merged incompatibilities identify the clip and contributing settings.

**2. Names and identity.** Source clip names and original direction indices
remain the frame identity. A clip's output name, used by every directory-mode
path and preview, is its explicit alias or its source name with characters
outside `A-Z a-z 0-9 . _ -` replaced by `_`. A direction's output name is its
explicit alias, existing compass label, or `direction-NNN` with a three-digit
index. Explicit aliases must already use that character set. Any resulting
empty name, `.` or `..`, trailing dot, or case-insensitive Windows device
name (`CON`, `PRN`, `AUX`, `NUL`, `COM1`..`COM9`, `LPT1`..`LPT9`, including
such names before an extension) is refused. Colliding clip output names or
direction output names are errors, compared ignoring ASCII case, with the
conflicting originals named. No automatic numeric suffixes in directory
mode. The old PNG mode keeps today's preview naming/disambiguation and does
not apply directory-mode aliases to filenames.

**3. Formats and templates.** These defaults ship in `defaults.yaml`:

```yaml
stored_directions: all
direction_names: {}
mirrors: {}
export:
  formats: [sheet]
  frame_path: frames/{clip}/{direction}/frame_{frame:03}{map}.png
  atlas_path: atlases/{clip}{map}.png
  sheet_path: sheet{map}.png
  atlas_padding: 0
clips: {}
```

`export.formats` is a nonempty subset of `sheet`, `frames`, `atlases`, with
no duplicates, replacing whole. `--formats sheet,frames,atlases` sets it as
an ordinary last-layer option; equivalent input orders resolve to canonical
order `sheet,frames,atlases`. Other `export` leaves merge independently.
Templates are files-only settings. `atlas_padding` is an integer 0..64;
it affects per-clip atlases only, not the combined sheet or frame PNGs.

Template tokens are `{subject}`, `{variant}`, `{clip}`, `{direction}`,
`{frame}`, and `{map}`. Subject and variant use the same cleaned-name rules;
subject is still the input filename stem, variant is currently `default`.
`{frame}` is a zero-based decimal index; `{frame:0N}` sets a minimum width
N of 1..12, so `{frame:03}` means three digits. `{map}` is empty for colour,
`.normal` for normals, `.depth` for depth. Frame templates allow all tokens;
atlas templates exclude direction and frame; sheet templates exclude clip,
direction and frame. Missing address tokens are allowed only if the fully
expanded plan has no collisions. There are no other formatting operations,
attribute/index access, expressions, globbing, environment expansion or
home expansion; unknown tokens or unmatched braces are errors.

Directory mode always writes `manifest.json`. Enabled previews use
`previews/{clip}.gif` and `previews/{clip}.lit.gif`, not configurable in this
arc. These names and every enabled map participate in collision checking.
A template omitting `{map}` therefore fails if enabled colour/map files
would collide. Paths must end in lowercase `.png`, use `/` separators and
contain nonempty components other than `.` or `..`. Absolute paths, drive
prefixes, backslashes, control characters and Windows-reserved filename
characters/device components or trailing dots/spaces are refused. Compare
all expanded paths ignoring ASCII case, including file/directory prefix
conflicts. Errors are usage exit 2 before capture, naming the template,
conflicting addresses and paths. Filesystem refusals are output exit 6.

Directory mode may write any chosen format combination. The positional PNG
mode requires `formats: [sheet]`; otherwise it fails asking for
`--output-dir`. This avoids ignoring a project's requested formats. Its PNG,
JSON, maps and preview names remain today's; directory path templates are
recorded but inactive. The two destination forms are mandatory alternatives,
not settings; neither an absolute output root nor the legacy output basename
enters the fingerprint. Neither invocation writes project settings.

**4. Image layout and maps.** Every format consumes the same addressed
post-cleanup frames, without recapture, trimming, rescaling or per-frame
recentering. A frame file is exactly the common W by H cell. A per-clip
atlas has one row per stored direction in its configured order, one column
per sampled frame, and no empty trailing columns. With padding p, its size
is `N*(W+2p)` by `D*(H+2p)`; the logical rectangle in slot (column,row)
starts at `(column*(W+2p)+p, row*(H+2p)+p)` and is W by H. Every border,
including corners, repeats the nearest edge texel, preserving all channel
values exactly. Padding zero is tightly packed.

The combined sheet remains unpadded, clips in selected order, each clip's
stored directions in configured order, columns equal to the largest frame
count, unused cells transparent. Its row offset is the sum of preceding
clips' stored-direction counts, never the original direction index.
Normals and depth accompany every enabled format according to existing
`normals`/`depth` settings, with identical logical rectangles and padding.
Encodings remain unchanged; depth is 16-bit and normal alpha matches colour.
The padding copies encoded texels, never averages or renormalizes them.
Normal/depth files are neither independently packed nor trimmed.

**5. Previews.** Preserve today's flat/lit GIF appearance, scaling, palette,
delay rounding and limits. Preview real stored directions only, in their
configured order, with each clip's resolved timing. Runtime mirror aliases
are represented in metadata, not added as GIF panels in this arc. Visual
acceptance will use a local comparison page to show those derived views.
`--no-preview`, `--no-normals`, `--depth` and the existing light controls keep
their meanings. A default legacy invocation keeps image bytes identical.

**Example, not approved acolyte acceptance settings:**

```yaml
directions: 8
stored_directions: [0, 4, 3, 2, 1]
mirrors: {7: 1, 6: 2, 5: 3}
export:
  formats: [frames, atlases]
  frame_path: animations/{clip}/{direction}/frame_{frame:03}{map}.png
  atlas_path: atlas/{clip}{map}.png
  atlas_padding: 1
clips:
  walk: {frames: 6, fps: 6}
  attack:
    stored_directions: [0, 7, 6, 5, 4, 3, 2, 1]
    mirrors: {}
    output_name: strike
```

This uses general clip names and settings, not a special game preset. Portrait
generation and actual acceptance values remain Q-6; neither is implied here.

### P-8. One generic metadata schema and replay contract

Adopted by D-8.

**1. Schema and location.** Both command forms write
`moskophoros.export/1`: `manifest.json` under the directory root, or today's
`<output-stem>.json` beside the positional PNG. Replace the old combined-
sheet-specific JSON shape rather than carrying two current schemas.
`--settings-from` accepts either location only at this current schema;
`moskophoros.sheet/15` is refused with a diagnostic naming both schemas and
saying to rerender from the model/project. No migration tool or legacy reader.

**2. Logical content.** Keep the existing generator, source, subject, variant,
settings and fingerprint meanings. Settings gain the new fields and each
selected clip's override values as supplied, including `null` inheritance.
Per-clip fields are recorded together, with existing name/loop/count fields;
FPS, stored directions, mirrors and output aliases are never lost on reuse.
The command's destination mode is not a rendering setting: replay still
chooses a destination explicitly. As today, the manifest stores resolved
fitting values and inline palette/library content, not machine-local paths.

Top-level directions describe the full ring's original index, angle, label
and output name. Clip records retain source name, loop, source duration,
resolved count, frame duration and time scale; add output name, resolved
FPS and stored-direction order. Real frames carry clip, original direction,
index, exact source time, and a list of locations. Subject and variant come
from the manifest; those plus clip/direction/time remain the identity.

An ordered `artifacts` array identifies each output by its zero-based array
index, kind (`sheet`, `atlas`, `frame`, `preview`), channel (`color`, `normal`,
`depth`, `flat`, `lit` as appropriate), root-relative path and pixel dimensions.
An artifact includes its clip for atlas/frame/preview and direction/frame
index for individual frame files. PNG artifacts record their padding and
logical cell dimensions. Each real frame's `locations` entries contain an
artifact index and logical `x,y,w,h`, for every exported colour/normal/depth
representation of that sample. GIFs are artifacts but not frame locations.
The JSON does not index itself. There is no `image`/`maps` singleton whose
meaning changes depending on the number of selected output formats.

Clip mirror records carry target and stored-source direction indices,
`transform: flip-x`, and derived ground pixel `(W-gx,gy)`. The source clip,
sample index/time and every artifact location are inherited from that clip's
real source samples; aliases have no fake captured-frame entries or duplicate
locations. Schema semantics specify image reversal within the logical cell,
normal-vector X negation after decoding and normalization, unchanged normal
alpha, and reversal of depth pixels without changing their values. Consumers
flipping encoded normals directly use `R'=255-R` only for covered pixels;
transparent texels stay zero. For padded atlases, flip the logical rectangle,
not the entire atlas or physical slot. The manifest's normal/depth encodings
remain those of the current design, not consumer shader conventions.

**3. Determinism.** Artifact ordering is fixed: sheet colour/normal/depth;
then per-clip atlases in clip order, each colour/normal/depth; then individual
frames in clip, stored-direction, sample order, each colour/normal/depth;
then previews in clip order, flat then lit. Omitted files have no entries.
Mirror records sort by target index, aliases by index. The JSON has fixed
key order, two-space indentation, UTF-8 and a trailing newline, as today.
Relative paths always use `/`; output root and project name are absent.
The fingerprint remains the canonical hash of generator, source digest and
recorded settings, including new settings. Output artifact paths/dimensions
are outside it, as the old `image` was; path templates are inside settings.

**4. Replay.** The manifest alone plus the same model/generator restores every
render/export setting, clip selection and one-shot marks, inline materials,
counts, rates, subsets, aliases, mirroring and formats. No project or palette
file is needed. The same destination mode and legacy basename where relevant
produce byte-identical files and metadata at any root. A different explicit
destination mode is allowed subject to its format constraints, and may change
artifact filenames/metadata without changing the fingerprint. Existing
settings-layer precedence and explicit `--clip`/`--once` behavior stay intact.
No normalizing recorded camera/light directions again. Unknown schema,
missing/invalid required settings and inconsistent references fail loudly.

The logical shape and schema behavior above are proposed contracts; the
implementation documentation will pin the complete JSON example and key
order before the implementation's final review, without changing these
meanings. During sliced delivery, any intermediate schema bump must have a
separate name and reject its predecessor; it cannot silently change `/1`.

### P-9. Publication, reruns and failures

Adopted by D-9.

**1. Existing files.** Permit a new or existing output directory. A run
replaces exactly the paths it writes and never deletes other files. Dropped
clips, reduced frame counts, disabled maps and changed templates may leave
old files; the new manifest lists only the current run's files and is the
authority for what belongs to it. Consumers scanning directories must use a
fresh output root or clean their own stale files. No hidden managed cleanup,
ownership database, pruning option or recursive directory replacement in this
arc. This extends the current publication policy without a destructive default.

**2. Preflight and staging.** Resolve and validate every planned output path
before Blender capture, including metadata/previews, duplicate names and
file/directory prefix conflicts. The chosen output root is resolved once;
its ancestors may be ordinary filesystem links, but no existing symlink at
or below that resolved root may be traversed as an output component or
overwritten as an output file. Recheck components before publication. Refuse
non-regular existing file targets and input/output overlap, including the
model and read configuration/palette/library files. Do not follow a link
outside the root. Concurrent writers to the same root are unsupported; do
not promise isolation against filesystem changes by other processes.

After successful rendering/encoding, create needed directories, stage every
file on the destination filesystem, and replace files under the existing
rollback mechanism. Publish the manifest last; roll it back with the others
if a handled failure interrupts publication. Readers must wait for successful
command completion; a many-file replacement is not an atomic snapshot for
concurrent readers. No successful partial export is reported.

**3. Failures and cleanup.** On a handled write/rename failure or interruption,
restore previous files and remove newly published files. Remove only newly
created empty directories and this run's temporary files; never remove an
existing directory or other content. Report output exit 6 naming the failed
path. If rollback itself fails, report each unrestored target and preserved
backup path honestly; do not claim earlier outputs were fully restored.
No power-loss or uncatchable-process-kill recovery guarantee is added.
Bad configuration and planned path collisions are usage exit 2, invalid model
input exit 3, geometry/depth overflow exit 4 and backend failures exit 5,
as in today's contract. A failure publishes no valid new manifest.

The alternative is an explicitly managed export that removes files from the
previous manifest on rerun. It is not recommended here because it expands
ownership, deletion and recovery semantics. It can be designed separately if
the owner prefers it; an empty-directory-only mode is another stricter option.

### D-10. Five views plus mirrors for the base unequipped acolyte

Owner answer on 2026-10-24, via verified `mosk-manager` relay
`cu65sdzfp57fn7hhp3jf637m86`, answering round-4 question message
`px6jz5p75byqcjjyj6w89nqkd2`:

> "as for this question you are asking me, the acolyte is 5 views + mirrors for the base unequipped version."

Record the five-view/mirror choice for the **base unequipped version** only.
It is not blanket approval for equipped/asymmetric clips, and not approval
of the model's look. The response does not explicitly choose the other
numbers bundled into P-10 (cell, scale and anchor); Q-15 asks whether those
remain the acceptance target or should be set during the later visual review.

### D-11. Old-game clip rates and counts

Owner answer on 2026-10-24 through the same verified relay and question:

> "B: game's old rates"

The owner additionally wrote:

> "the fps needs to drop to the 8 that the original art uses"

This selects the explicitly described option B: walk **six frames at 8 FPS**
(0.75 seconds) and idle **four frames at 6 FPS** (two-thirds of a second).
The extra remark emphasizes the walk rate; the chosen option already states
the two per-clip rates. P-11's recommendation to preserve source duration and
the full 12-FPS sample-count alternative are rejected for this acceptance
profile. Generic sampling/retiming semantics are unchanged.

### D-12. Portraits excluded; model rework is a separate request

Owner answer on 2026-10-24 through the same verified relay and question:

> "A: not in this arc"

Adopt P-12: no portrait-specific workflow in this arc; generic static exports
remain supported. In the same relay the owner identified model/look changes:
skin reading grey under lighting, a desire for brighter cartoon colours and
a possible blue ramp, and a more casual walk/posture. The owner said:

> "the mask is nice, dont change that."

These are context for the separate model work, not export implementation
requirements or permission for this designer to edit the model. The manager
explicitly directed that rework remain outside this design and asked for an
owner decision on the final acceptance model. Q-14 records that decision
point. Do not label the round-4 appearance approved or silently pin the
export's final acceptance to the old look.

## Round-4 acceptance choices and retained alternatives

### P-10. Fixed cells and five stored acolyte directions

Five views plus mirrors are adopted only for the base unequipped version
(D-10). The placement values remain proposed pending Q-15, and the final
model/look input is Q-14. The rest of this section describes the reviewed
prototype, not an unqualified acceptance record.

Use the approved model and look at 24 px/m in fixed 48x48 cells, ground
pixel (24,44), with colour, normals and depth. Store `[0,4,3,2,1]` and map
7 from 1, 6 from 2, 5 from 3 for both unarmed clips. Use frame folders plus
per-clip atlases with one-pixel padding; include a combined-sheet run and
metadata-only replay checks in technical acceptance. Flat and lit previews
stay enabled with the accepted project's current light.

This reaches the consumer's logical cell/row layout through generic settings;
50x50 is the physical atlas slot, not the cell. Local acceptance keeps the
existing approved palette/library and project snapshot, not a shipped preset.
The model remains larger than the old art at its approved scale. The old
sprite's drawn feet do not coincide exactly with the renderer's inferred
(24,44) anchor; the page marks the anchor rather than moving the old pixels.

The alternative is the same cell/anchor/scale/maps/padding with all eight
real directions `[0,7,6,5,4,3,2,1]` and no mirrors. This retains the model's
original pose in each direction; five views save three rows but change some
poses/robe details. The owner judges that tradeoff from synchronized images.
Future asymmetric clips require their own explicit full-direction settings;
approval here would cover only these unarmed walk and idle clips.

### P-11. Reduced counts at the authored duration

Rejected for acceptance in favor of option B, D-11. Retained to explain the
round-4 alternatives; the final profile is six walk frames at 8 FPS and four
idle frames at 6 FPS.

For the acceptance model, use six walk frames at 6 FPS (one-second loop)
and four idle frames at 2 FPS (two-second loop). This exercises independent
clip rates and the consumer's smaller frame counts without speeding up the
approved authored motion. Its coarser sampling is a visible tradeoff.

Alternatives on the page: the same counts at the current game's 8/6 FPS,
making walk 0.75 seconds and idle two-thirds of a second; or retain the
approved full sampling, walk 12 and idle 24 frames, both at 12 FPS. The
owner may mix choices by clip. Displayed GIF cycles are respectively
walk 1.02/0.78/0.96 seconds and idle 2.00/0.68/1.92 seconds because today's
preview rounds every frame to 10 ms. Metadata uses the intended durations.

### P-12. Portrait generation remains outside this arc

Adopted by D-12.

Do not add portrait-specific cameras, crops, output kinds or automatic pose
selection. The existing 32x32 portrait is read-only context on the page.
Generic static one-frame exports remain supported; a portrait may be designed
as a separate rendering workflow later. The alternative is to include that
workflow now, which requires its own framing/pose/size decisions before
delivery boundaries can be finalized.

The final implemented export still requires a dedicated owner review, even
if the owner accepts these prototype values. Prototype approval chooses the
acceptance target; it does not close the future implementation's visual gate.

## Open questions

### Q-1. Output choices and consumer boundary

Resolved by D-1.

### Q-2. Clip timing

Resolved by D-2. Actual acolyte counts and cadence are now D-11.

### Q-3. Default compatibility

Resolved by D-3.

### Q-4. Direction subsets, names and mirroring

Resolved by D-4. The base unequipped acolyte's five-view choice is D-10;
the implemented result still needs visual review. Settings syntax is D-7.

### Q-5. Output paths, maps, naming and publication

Resolved by D-6. Q-9 retains the detailed output contract.

### Q-6. Acceptance cell, anchor and optional outputs

Direction scope resolved by D-10. The owner answered five views plus mirrors
for the base unequipped version, not an unqualified approval of P-10's
placement bundle. Remaining placement values are explicitly carried to Q-15.
Model-version ownership is Q-14. Labelled probe evidence remains round-04/q6.

### Q-7. Delivery and readiness

Round 5: approve P-13's seven-slice plan and explicitly mark the design ready
after Q-14/Q-15 are recorded (recommended), or approve the plan but leave the
design exploring for further changes? Alternatively specify plan amendments.
The tracker was rechecked: only unrelated #43 is open, and no PRs are open.
No export epic duplicates the proposed umbrella at this check.

### Q-8. What does runtime mirroring mean in the export?

Resolved by D-5. This is not visual signoff on any model's symmetry.

### Q-9. Detailed settings, metadata and output contract

Resolved by D-7.

### Q-10. Metadata and reuse

Resolved by D-8.

### Q-11. Output replacement and stale files

Resolved by D-9.

### Q-12. Acolyte frame counts and rates

Resolved by D-11: option B, walk six at 8 FPS, idle four at 6 FPS.

### Q-13. Portrait workflow scope

Resolved by D-12: portrait-specific generation is outside this arc.

### Q-14. Which acolyte version owns final visual acceptance?

Required clarification from the manager after the owner requested separate
model rework: use the latest acolyte explicitly approved by the owner at
review time (recommended), recording and freezing its model/library/palette
hashes for that review; or pin the historical `physics-v2` and `library-v4`
as this export arc's acceptance fixture? Technical tests use generated models
either way. Model refinement is never a dependency of implementation work;
it may gate only the final owner review if the owner chooses the newer model.

### Q-15. Acceptance placement after model rework

Required clarification because D-10 answers direction scope only: retain the
prototype's 48x48 cell, 24 px/m, anchor (24,44), normal/depth outputs and
one-pixel atlas padding as the initial acceptance target (recommended), with
an overflow or desired change sent to the owner; or choose those acceptance
values during the final model review? Either is compatible with the generic
export contract. No auto-shrinking, changed anchor or claimed visual approval
is inferred from the five-view answer.

## Verification strategy

Checks belong to each slice and use generated fixtures and temporary
directories. Real consumer assets remain local acceptance evidence, never
repository tests. Test observable behavior: exact sample times and identity;
layer merging and reset semantics; invalid names/templates/mirror sources;
decoded cell/map/padding equality; deterministic metadata and complete replay;
and injected staging/replacement/rollback failures that preserve prior files.

Generated-GLB integration covers unequal clip rates/counts/subsets, a full-view
asymmetric exception, format combinations, maps/previews and fresh-root replay.
Retained jobs prove that only stored samples are requested. Compare the new
default encoder with the existing one on the same addressed arrays before
activation; preserve reproducible default-image baseline hashes for a locally
generated model across the command switch using the same generator. New
metadata is expected to differ. Appearance needs the separate owner gate.

Every code slice follows [validation](../validation.md) and the planner at its
actual diff. The current catalog selects `test.blender` for any `src/` change,
even preparatory pure-code changes; those PRs need current passing local
evidence as well as required CI checks. No new dependency is proposed.
Evidence/design notes land with `docs-push`; implementation contracts tests
read, notably `docs/design.md`, travel with code under the documentation-as-code
rule. No generated art or binary model enters the repository.

## Delivery plan

### P-13. Seven slices with one public activation and a final owner gate

Proposed until Q-7 is approved. EXP-1 through EXP-6 are each one issue,
worktree and reviewable code PR. EXP-7 is a human acceptance issue with
evidence published by `docs-push`, not a manufactured code PR. Model rework
is outside every slice.

EXP-1 through EXP-5 provide tested internal capabilities. The existing command
continues its current sheet behavior/schema until EXP-6 connects the complete
feature. It must not accept new settings and silently ignore them. Prepare
schema extensions/helpers without enabling incomplete public behavior. EXP-6
activates the full settings contract and makes one public switch to
`moskophoros.export/1`; no intermediate public export schema or long-lived
feature flag is needed. This sequencing is part of the plan being approved.

Dependency order: EXP-1 → EXP-2 → EXP-3 → EXP-4 → EXP-6 → EXP-7.
EXP-5 depends on EXP-2 and also feeds EXP-6. After EXP-2 it may proceed
separately from encoding/metadata if the manager judges the scopes compatible.
The ledger gives one valid order, not a request to launch parallel agents.

### EXP-1. Plan per-clip sampling and stored directions

- **Outcome:** one pure request planner resolves per-clip sample times,
  durations and stored-view order without changing original frame addresses.
- **Scope:** effective FPS/count rules; loop/one-shot/still cases; ordered
  subsets; logical mirror references; shared frame plans for capture/export/
  previews. Existing callers keep default behavior until integration.
- **Phase:** internal planning foundation.
- **Depends on:** `none`.
- **Ordering:** critical path.
- **Relevant decisions:** D-2, D-4, D-5, D-7.
- **Acceptance signals:** expected exact times/rates for unequal clips;
  reordered subsets keep original direction IDs; no captured alias samples;
  static and zero-length clips keep their defined behavior.
- **Out of scope:** parsing, filenames, public activation and Blender changes.
- **Open questions:** None.

### EXP-2. Resolve export settings, names and output paths

- **Outcome:** layered settings yield a validated deterministic request and
  complete relative output-path plan before rendering.
- **Scope:** schema extensions, per-clip leaf merge/reset, formats normalization,
  alias/name validation, template grammar, all enabled map/preview/manifest
  paths, collision/prefix checks, warnings and provenance. Prepare extensions
  without making the old command accept values it cannot execute. Keep one
  schema-table authority rather than duplicate existing setting definitions.
- **Phase:** internal configuration and preflight.
- **Depends on:** EXP-1.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-2, D-4, D-5, D-6, D-7, D-9.
- **Acceptance signals:** layer/reset cases resolve exactly; errors retain
  file/key locations; path conflicts fail before capture; a changed view
  cannot silently discard invalid direction/mirror references.
- **Out of scope:** encoding, filesystem mutation and command activation.
- **Open questions:** None.

### EXP-3. Encode frame files and clip atlases from addressed frames

- **Outcome:** one set of post-cleanup addressed frames produces any approved
  combination of individual PNGs, clip atlases and combined sheet, with maps.
- **Scope:** logical rectangles, variable clip-row counts, exact padding,
  encodings, ordered artifact descriptors and sample locations; stored-view
  previews at each clip's timing. Reuse shared image operations. Keep encoding
  separate from publication and preserve the old path for comparison until EXP-6.
- **Phase:** internal image export.
- **Depends on:** EXP-1, EXP-2.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-4, D-5, D-7.
- **Acceptance signals:** decoded frame/map pixels and every padded edge/corner
  match; zero padding and unequal counts work; combined-sheet empty cells are
  transparent; default PNG/GIF bytes match the existing encoder on identical
  inputs; missing/extra/duplicate addressed frames are rejected.
- **Out of scope:** metadata schema, publication and model changes.
- **Open questions:** None.

### EXP-4. Record and reload the generic export manifest

- **Outcome:** `moskophoros.export/1` records all sample locations and mirror
  references and restores every required setting.
- **Scope:** deterministic JSON/key order/fingerprint; artifact references;
  full-ring and per-clip records; actual versus derived identity; inline
  palette/library; strict validation and reload to the settings layer. Pin
  the full JSON example/field contract before final review. Keep this internal
  until EXP-6 so no partially implemented schema becomes public.
- **Phase:** internal metadata and replay.
- **Depends on:** EXP-1, EXP-2, EXP-3.
- **Ordering:** critical path.
- **Relevant decisions:** D-3, D-5, D-7, D-8.
- **Acceptance signals:** encode/reload preserves overrides and inheritance;
  references match artifacts; mirror/anchor semantics hold; original config
  files are unnecessary; malformed references and old schemas are refused.
- **Out of scope:** CLI switch, consumer indexes and runtime shaders.
- **Open questions:** None.

### EXP-5. Publish nested output files with rollback

- **Outcome:** planned exports create directories and replace their files
  with manifest-last publication and honest rollback.
- **Scope:** filesystem preflight/confinement, input/output overlap checks,
  staging, replace-only-written policy, rollback, owned-empty-directory cleanup
  and backup diagnostics. The publisher stays independent of image internals;
  preserve existing default publication behavior.
- **Phase:** filesystem effects.
- **Depends on:** EXP-2.
- **Ordering:** independent of EXP-3/EXP-4 after EXP-2; required by EXP-6.
- **Relevant decisions:** D-6, D-7, D-9.
- **Acceptance signals:** injected failures restore prior bytes; only owned
  empty new directories are cleaned; stale/unrelated files survive; links
  cannot escape the root; incomplete publication has no valid new manifest;
  rollback failures identify preserved backups without claiming full restoration.
- **Out of scope:** pruning, crash recovery and concurrent-writer isolation.
- **Open questions:** None.

### EXP-6. Connect directory exports to the command pipeline

- **Outcome:** both command forms support all approved settings, output
  combinations and metadata replay end to end.
- **Scope:** activate settings; add `--output-dir`/`--formats` and their
  constraints; connect request planning, measure/render, common fitting,
  stylize/cleanup, encoding, metadata and publication. Update the capture
  builder's expected-frame check to use the shared resolved plan rather than
  reconstructing a global-FPS/full-ring plan. Blender still evaluates exact
  supplied times/angles and renders no aliases. Document the full CLI/contract.
- **Phase:** public activation and integration.
- **Depends on:** EXP-1, EXP-2, EXP-3, EXP-4, EXP-5.
- **Ordering:** critical path.
- **Relevant decisions:** D-1 through D-9.
- **Acceptance signals:** generated-model command runs cover format combinations,
  per-clip rates/counts/subsets, full-view exceptions, maps/previews and fresh-root
  replay. Defaults match pre-activation image baselines with the same generator.
  No accepted option is ignored. The command switches to `/1`, refuses `/15`,
  and its help and tested contracts match the delivered behavior.
- **Out of scope:** consumer integration, model changes and final visual approval.
- **Open questions:** None. The current capture wire already accepts arbitrary
  in-ring addressed samples and exact times: no renderer resampling or new
  wire field is needed. The caller validates the resolved plan; capture keeps
  its existing wire fields and carries no output paths/aliases/mirror policy.

### EXP-7. Review the implemented acolyte export with the owner

- **Outcome:** explicit owner acceptance with reproducible evidence identifying
  the exact input, settings, generator and implementation revision.
- **Scope:** apply Q-14's model policy and Q-15's placement policy; base
  unequipped acolyte has five views plus mirrors, walk six at 8 FPS, idle
  four at 6 FPS. Produce frame folders and clip atlases/maps, a combined-sheet
  comparison, and replay from metadata alone. Compare captured/mirrored views
  and old sprites on a labelled page. Check timing, counts, pixels and replay
  separately from visual judgement. Always use a fresh local output root.
- **Phase:** owner acceptance and documentation closeout.
- **Depends on:** EXP-6; additionally the owner-selected model/placement gate.
- **Ordering:** critical path to epic completion; does not block EXP-1–EXP-6.
- **Relevant decisions:** D-1 through D-12, plus eventual Q-14/Q-15 decisions.
- **Acceptance signals:** current technical checks pass; exact commands and
  hashes are recorded; the owner explicitly approves the implemented export
  with dated provenance. Stop for the owner if the chosen model is unapproved,
  overflows, lacks expected clips or needs appearance work. Never silently
  substitute an input, refit scale or close the epic on tests alone.
- **Out of scope:** model/look refinement, portraits, equipped/asymmetric asset
  creation, game writes and private compilation. Generated fixtures cover
  full-direction exceptions mechanically.
- **Open questions:** Q-14 and Q-15 affect only review inputs/targets or an
  explicit owner gate. This is documentation-only acceptance: evidence lands
  with `docs-push`, with no code PR needed.

## Conversation cursor

Round 1 resolved Q-1, Q-2 and Q-3 as D-1, D-2 and D-3. Local text decision page:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-01/index.html`.
This is a new round folder, not an alteration of the approved model review.
No visual preference was requested in that round. Later visual questions need
labelled comparison images grouped by decision. The verified manager relay
`c3csfyvkcf4anp6jc2nup8s382` carries the owner's signoff dated 2026-10-24.
Direction selection, mirror representation and output configuration were
subsequently approved in round 2.

Round 2 resolved Q-4, Q-8 and Q-5 as D-4, D-5 and D-6. Its round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-02/index.html`.
No visual approval was requested there. Verified relay
`kxtwp9nj4gdsdhmdnk28wjaezn` records the owner's answers dated 2026-10-24.
Next settle Q-9 and Q-6 before the final
dependency-ordered slices and readiness signoff; the three-question limit
does not silently resolve the remaining choices.

Round 3 resolved Q-9, Q-10 and Q-11 as D-7, D-8 and D-9. Its round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-03/index.html`.
Verified relay `zrbvdx42r5mqc9vwavgcrkvbfn` records the owner's signoff dated
2026-10-24. Q-6 now covers acceptance values/visual probes and portrait
scope, then Q-7 covers slices and readiness. No implementation is authorized
by this design session.

Round 4 answered Q-6's direction scope, Q-12 and Q-13 as D-10, D-11 and D-12.
Its round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-04/index.html`.
The fresh locked render and local crop/layout probes succeeded as recorded
above. Verified relay `cu65sdzfp57fn7hhp3jf637m86` records the owner's answers
dated 2026-10-24. The owner requested separate model/look rework; Q-14 and
Q-15 explicitly carry the remaining model/placement questions. Next propose
delivery slices with those choices isolated to the final owner-review gate.

Round 5 asks Q-14 (review model), Q-15 (initial placement policy) and Q-7
(seven slices and readiness). New round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-05/index.html`.
The placement section reproduces the earlier labelled image as historical
context, explicitly not a new model/look approval. State remains `exploring`
until the owner answers these questions and grants readiness.
