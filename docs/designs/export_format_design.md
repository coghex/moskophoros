# Game-ready export formats design

Design configurable frame folders, per-clip atlases, stored direction subsets
with runtime mirroring, and clip sampling for a general-purpose renderer.
The approved acolyte is the external acceptance model; no consumer names,
paths or private formats belong in production code, defaults or tests.

Design state: `ready for issue processing`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [x] EPIC. Export configurable game-ready frames and clip atlases — [#153]
- [x] EXP-1. Plan per-clip sampling and stored directions — [#154]
- [x] EXP-2. Resolve export settings, names and output paths — [#155]
- [x] EXP-3. Encode frame files and clip atlases from addressed frames — [#156]
- [x] EXP-4. Record and reload the generic export manifest — [#157]
- [x] EXP-5. Publish nested output files with rollback — [#158]
- [ ] EXP-6a. Switch legacy output to the complete export manifest
- [ ] EXP-6b. Activate configurable directory exports
- [ ] EXP-7. Review the implemented acolyte export with the owner

Eight slices approved by the owner on 2026-10-24 (D-18 amends D-15).
All design questions are resolved. D-13 and D-14 set the model and placement policies for the
final owner-review slice; model rework remains outside implementation.
Design review is complete. Epic #153 and EXP-1 through EXP-5 (#154–#158) are filed;
three child entries remain unprocessed and require separate draft signoff before creation.

## Epic contract

- **Goal:** render a model using project settings into reusable images and
  metadata, with explicit clip timing, directions, scale and ground anchor.
- **Done when:** all approved output combinations work from project settings;
  defaults preserve image bytes; the current manifest reproduces the export;
  path, overflow and publication failures satisfy the contract; planned
  automated checks pass with current local Blender evidence; and the owner
  approves the implemented base-acolyte export beside old sprites in EXP-7.
  Acceptance input and placement follow D-13 and D-14.
- **Users and operators:** artists and developers rendering subjects for games.
- **Arc label:** None proposed.

## Authority and source material

Request `moskophoros-20261024-1`, dispatched by the manager on 2026-10-24 in
`~/.local/state/project-manager/moskophoros/dispatch-export-format-design.md`.
The verified `mosk-manager` chat record
`wuihstigu7bmbb8e4e56cpb53w` confirms the owner selected this design session.
The brief quotes the owner's choice as **"Design the export format
(Recommended)"**, after approving the acolyte. This authorizes exploration,
not by itself the options below. Every subsequent approved choice records
the owner's exact words, date and relay message ID or "in the designer's pane".

The endpoint is an owner-signed design ready for `process-design-doc`.
This session writes no implementation or repository tests and files no issues.
The review-1 revision also adds the authorized dated note under vision V-2
(D-19); all other repository work remains design-only. Local probes and review
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
model/look for the final export review. See D-10 through D-14.

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
colour frames in its strict frame tree and keep normal/depth files outside
that tree; its existing compiler owns the private index and runtime atlases.
Do not teach moskophoros the consumer's schema or digest rules.
This makes generic atlases useful to other consumers without claiming they
replace this game's compilation step. D-6 and D-7 subsequently settle the
exact settings and CLI.

### P-2. Add per-clip FPS without changing frame-count meaning

Adopted by D-2. Retained proposal ID for the round-1 record.

Keep existing frame-count retiming and add a per-clip FPS override. A
one-second walk with six frames at 6 FPS lasts one second; six at 8 FPS lasts
0.75 seconds, matching the current game's cadence. A two-second idle with
four frames at 2 FPS preserves two seconds, while four at 6 FPS matches the
old game's two-thirds-second cadence. These numbers explain behavior; none
was selected in round 1. D-11 subsequently selects the old-game cadence;
the implemented previews still require owner review.

### P-3. Preserve default images, explicitly version metadata

Adopted by D-3. Retained proposal ID for the round-1 record.

Keep today's combined-sheet default, sampling, image layout, map and preview
bytes when no new option is used. Permit JSON and fingerprint changes for
the new recorded settings and schema. Continue the owner's current-schema-
only reuse policy instead of adding compatibility modes. A promise of
byte-identical JSON conflicts with an unconditional schema bump; that part
of the brief needed a precise choice. D-8 subsequently fixes the schema
identity as `moskophoros.export/1`.

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
Acceptance-model cadence is subsequently settled by D-11. This affects sampling,
settings, metadata/reuse and preview timing. Global-FPS-only was rejected
because clips need independent playback rates.

### D-3. Default image compatibility, versioned JSON

Owner signoff on 2026-10-24 through the same verified relay and question:

> "A: images unchanged"

P-3 is adopted: preserve default sheet/map/preview bytes when no new feature
is selected, allow the schema, JSON and fingerprint to change, and retain
current-schema-only reuse. No legacy JSON compatibility path is added.
This affects every new setting's recording, reuse and regression checks;
the exact schema identity is subsequently settled by D-8.

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
An explicit `--fps` or a project file's `fps` shadowed by selected clips'
own FPS gets one warning listing those clips, even when the per-clip value
equals the global value, following the frame-count precedent. Defaults,
global-file values and reused values do not warn. Unlike count overrides,
FPS overrides matter to the duration of a still too, so stills are included.

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

The name refusals in this subsection and expanded-template path checks below
apply only in directory mode. The positional form checks recorded templates'
syntax only and preserves existing output/preview naming, including names
such as `aux` and case-colliding clips. Identity fields retain original names.
In the positional form, `output_name` fields record the resolved directory-mode
names without directory-mode validation; they are informational and may
collide. Artifact `path` values give the actual filenames, including legacy
preview suffixes. Unapplied directory aliases cannot make a default legacy
run fail.

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
```

Do not add `clips: {}` to `defaults.yaml`: clips keep their existing separate
default/`CLIP_SCHEMA` handling. These new `SCHEMA` rows ship in defaults only
when activated in EXP-6b. EXP-2's inactive-row gate is specified in P-13.

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
home expansion; unknown tokens or unmatched braces are errors. One root holds
one subject's export (D-16); `{subject}` names files inside that root, not a
way to batch different models into a shared root.

The grammar is:

```text
template   = (literal | "{" token "}" | "{frame:0" width "}")+
token      = "subject" | "variant" | "clip" | "direction" | "frame" | "map"
width      = "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "11" | "12"
literal    = one character from [A-Za-z0-9._/-]
```

There are no brace escapes: `{{` and `}}` fail. `{frame:3}`, `{frame:00}`,
`{clip:03}`, `{ clip }`, leading-zero widths and non-ASCII literals fail.
The per-format token restrictions above still apply. Syntax is checked even
for inactive templates. Every path rule below applies to each expanded path,
not to a token's spelling in the template: for example `out/{map}/frame.png`
fails for colour's empty component. A nonempty component starting with a dot
(for example `.subject`) is allowed unless it is exactly `.` or `..` or
violates another rule; hidden names are not a separate prohibition.

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
conflicting addresses and paths. The P-9 table distinguishes preflight usage
refusals (2), output I/O failures (6) and interruption (130).

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
  frame_path: animations{map}/{clip}/{direction}/frame_{frame:03}.png
  atlas_path: atlas/{clip}{map}.png
  atlas_padding: 1
clips:
  walk: {frames: 6, fps: 6}
  attack:
    stored_directions: [0, 7, 6, 5, 4, 3, 2, 1]
    mirrors: {}
    output_name: strike
```

This uses general clip names and settings, not a special game preset. Colour
frames go under `animations/`; maps go under `animations.normal/` and
`animations.depth/`. Portrait scope and actual acceptance values are D-10
through D-14; neither is selected by this example.

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

In the positional form the root is the PNG's containing directory: artifact
paths are base names, preserving existing relocation behavior. Directory-mode
paths are relative to `--output-dir`.

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

Consumers must use the derived mirror anchor: if `W != 2*gx`, it differs
from the stored-view anchor by `W-2*gx` pixels. This includes auto-fit odd
widths. Placement by a single shared anchor would shift those mirrored views;
the 48-wide, gx=24 acceptance target is unaffected.

A horizontal flip represents geometric reflection only if roll is 0 or ±1
(the existing roll unit, half-turns), `theta_target + theta_source` is
congruent to zero modulo 360 degrees, and a perspective camera has
no sideways position offset from its vertical heading plane through the
ground point. Orthographic position is unused. These are necessary camera
conditions, not a claim that the subject or its lighting is symmetric.
Here `theta = (start + i*360/N) mod 360`; `model_yaw` corrects the model to
face +Z before the direction turn and does not enter the angle condition.
Using `model_yaw` for anything other than facing correction is outside this
condition's assumptions. This corrects the review-1 formula; D-17's warning
policy is unchanged.
Per D-17, warn once per clip/target-source pair when any condition fails,
listing the pair and failed conditions, then export anyway. The transform
still specifies the requested pixel operation, not guaranteed equivalence
to a separately captured target. Validate geometry with pure checks in EXP-2
and emit warnings in EXP-6b; document these semantics in `docs/design.md`.

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
artifact filenames/metadata without changing the fingerprint only when the
recorded settings stay identical. In particular, switching a frames/atlases
manifest to positional output requires `--formats sheet`, changing settings
and the fingerprint. Existing
settings-layer precedence and explicit `--clip`/`--once` behavior stay intact.
No normalizing recorded camera/light directions again. Unknown schema,
missing/invalid required settings and inconsistent references fail loudly.

The complete member/order contract is pinned in P-8a below, before EXP-4 is
filed. EXP-4 implements it internally and EXP-6a copies the contract into
`docs/design.md` with the public switch. P-13 delivers one public schema
change at EXP-6a, with no public intermediate schema or silent change to `/1`
when EXP-6b activates settings.

### P-8a. Pinned JSON members, order and example

This is the complete `/1` member contract for EXP-4 issue review, pinned in
the review-1 revision. It supplements P-8's meanings without adding another
schema. Required keys are never omitted unless this table explicitly says
so. Unknown, duplicate, missing and wrong-type members fail strict reuse;
integer indices exclude booleans. Preserve existing finite-number checks,
inline palette/library validation and current-only reuse errors.

| Object | Members in serialized order |
|---|---|
| Document | `schema`, `generator`, `source`, `subject`, `variant`, `settings`, `fingerprint`, `artifacts`, `directions`, `clips`, `frames` |
| `generator`, `source` | Exact existing member order, types and values from `docs/design.md` §Export at `5788a7c4f6`; no added capture fields |
| `settings` | `view`, `camera`, `model_yaw_deg`, `fps`, `frames`, `supersample`, `pixels_per_meter`, `cell`, `ground_m`, `ground_px`, `root_motion`, `previews`, `normals`, `depth`, `light`, `shade`, `ramp`, `style`, `stored_directions`, `direction_names`, `mirrors`, `export`, `clips` |
| Existing nested settings | Existing types/order and inline palette/library variants from the same §Export contract; resolved fit values and normalized vectors preserved exactly |
| `settings.export` | `formats`, `frame_path`, `atlas_path`, `sheet_path`, `atlas_padding` |
| `settings.clips[]` | `name`, `loop`, `frames`, `fps`, `stored_directions`, `mirrors`, `output_name` |
| Name-map entry | `index` (integer), `name` (string) |
| Settings mirror-map entry | `target` (integer), `source` (integer) |
| Artifact common prefix | `kind`, `channel`, `path`, `width`, `height` |
| Artifact suffix, after prefix | `clip` for atlas/frame/preview; then `direction`, `index` for frame only; then `padding`, `cell` for PNG kinds only |
| Artifact `cell` | `width`, `height` (positive integer logical dimensions) |
| `directions[]` | `index`, `angle_deg`, `label`, `output_name` |
| Top-level `clips[]` | `name`, `loop`, `duration_s`, `frame_count`, `frame_duration_s`, `time_scale`, `output_name`, `fps`, `stored_directions`, `mirrors` |
| Top-level clip mirror entry | `target`, `source`, `transform`, `ground_px` |
| Mirror `ground_px` | `x`, `y` (integer pixel-edge coordinates) |
| `frames[]` | `clip`, `direction`, `index`, `time_s`, `locations` |
| Location | `artifact` (zero-based integer array index), `x`, `y`, `w`, `h` (integers; positive sizes) |

`settings.stored_directions` is the JSON string `"all"` or an ordered integer
array. `settings.direction_names` and `settings.mirrors` are arrays of the
entries above, sorted by index/target; empty mappings encode as `[]`, never
string-keyed JSON objects. Reuse converts them to integer-keyed internal
maps; the YAML rule rejecting string-digit keys is unchanged. Duplicate
indices/targets are errors, not last-wins mappings. Per-clip
`stored_directions` is `null`, `"all"` or an ordered integer array; per-clip
`mirrors` is `null` or the same target/source array. `null` retains inheritance,
whereas `[]` explicitly disables inherited mirrors. Per-clip `fps` is `null`
or a positive finite float; `output_name` is `null` or its supplied alias;
`frames` retains count/`"auto"`/`null`. Settings clips list selected source
clips in selection order, as today; effective values belong in the top-level
clip records, not in place of supplied overrides.

Top-level clip `duration_s` is source duration; `fps`, `frame_count`,
`frame_duration_s` and `time_scale` are resolved by the existing sampling
formulas. Its `stored_directions` is always an ordered nonempty index array,
and `mirrors` is always a target-sorted array (possibly empty). Direction
records cover the entire ring in original index order, with existing nullable
compass `label` and the P-7 output name. In positional output, both direction
and clip `output_name` values are informational directory-mode names, resolved
without directory-mode name validation; actual filenames are artifact paths.
Frames follow selected clip, stored
direction, sample order. Locations sort by artifact index. Every enabled PNG
representation occurs exactly once for each real sample; no preview or
mirror is a location. Reference checks validate channels, dimensions,
logical bounds excluding padding, clip/direction/index identity and absence
of missing/extra samples. Artifact dimensions are positive integers; padding
is zero for frame/sheet and the configured value for atlas. `channel` is
`color`/`normal`/`depth` for PNGs and `flat`/`lit` for previews. No irrelevant
suffix keys or null placeholders are emitted on artifacts.

The manifest settings builder is independent of
`capture.backend.settings_document`. The latter remains the existing strict
capture-relevant subset, including its old per-clip name/loop/frames keys.
Do not append export settings to a Blender job. EXP-4 tests byte identity of
job settings while varying the new manifest-only fields with the existing
capture fields and fitted values held fixed. Actual addressed frame lists
and fit may change when a selected plan changes; that is not a settings-wire
schema change. The job's `fps` remains the resolved global value, while exact
sample times in the job frames govern clips with their own FPS.

Complete structural example: one stored static view, one requested mirror,
colour frame output only. Hash/version placeholders stand for the existing
computed values; they are not literal valid digest/version test fixtures.
Formatting here is compact for reading; the writer uses two-space indentation
and the key order above. Other optional library/palette shapes retain their
complete existing §Export definitions; no ellipsis substitutes for members.

```json
{
  "schema": "moskophoros.export/1",
  "generator": {
    "tool": "moskophoros", "version": "0.1.0",
    "python": "3.x.y", "numpy": "x.y.z", "pillow": "x.y.z",
    "blender": "x.y.z", "renderer": "cycles",
    "color": {"technique": "cycles-flat-emission", "samples_per_pixel": 1,
      "seed": 0, "pixel_filter": "BOX", "filter_width_px": 0.01,
      "min_transparent_bounces": 64, "transparent_max_bounces": 64,
      "pass_alpha_threshold": 9.313225746154785e-10},
    "shade": {"technique": "cycles-ambient-occlusion", "samples_per_pixel": 1,
      "seed": 0, "pixel_filter": "BOX", "filter_width_px": 0.01}
  },
  "source": {"file": "hero.glb", "sha256": "<computed source digest>"},
  "subject": "hero",
  "variant": "default",
  "settings": {
    "view": {"preset": "custom", "directions": 4, "start_angle_deg": 0.0},
    "camera": {"projection": "orthographic", "direction": [0.0, -0.6, -0.8],
      "roll": 0.0, "position": null},
    "model_yaw_deg": 0.0,
    "fps": 12.0,
    "frames": "auto",
    "supersample": 8,
    "pixels_per_meter": 4.0,
    "cell": {"width": 4, "height": 4},
    "ground_m": {"x": 0.0, "y": 0.0, "z": 0.0},
    "ground_px": {"x": 2, "y": 3},
    "root_motion": "error",
    "previews": false,
    "normals": false,
    "depth": false,
    "light": {"position": null, "intensity": 1.0, "ambient": 0.3},
    "shade": {"ao_distance_m": 0.3, "ao_samples": 64,
      "occlusion_weight": 0.25, "convexity_weight": 1.0, "range": [84, 191],
      "mode": "ramp", "ambient_form": true,
      "key": {"direction": [-0.5183210553488161, 0.604707897906952, 0.604707897906952], "strength": 0.0},
      "sky": {"strength": 0.0}, "ground": {"strength": 0.0},
      "sky_ground_frame": "camera", "brightness": {"floor": 0.3, "ceiling": 1.0},
      "snap": "off", "dither": {"pattern": "off", "strength": 1.0}},
    "ramp": {"lightness_step": 0.12, "hue_shift_deg": -12.0, "chroma_fade": 0.3},
    "style": {"reduce": "plain", "edges": "hard", "palette": null, "materials": null},
    "stored_directions": "all",
    "direction_names": [{"index": 1, "name": "right"}],
    "mirrors": [],
    "export": {"formats": ["frames"],
      "frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
      "atlas_path": "atlases/{clip}{map}.png", "sheet_path": "sheet{map}.png",
      "atlas_padding": 0},
    "clips": [{"name": "static", "loop": true, "frames": null, "fps": null,
      "stored_directions": [1], "mirrors": [{"target": 3, "source": 1}],
      "output_name": null}]
  },
  "fingerprint": "sha256:<computed fingerprint>",
  "artifacts": [{"kind": "frame", "channel": "color",
    "path": "frames/static/right/frame_000.png", "width": 4, "height": 4,
    "clip": "static", "direction": 1, "index": 0, "padding": 0,
    "cell": {"width": 4, "height": 4}}],
  "directions": [
    {"index": 0, "angle_deg": 0.0, "label": "south", "output_name": "south"},
    {"index": 1, "angle_deg": 90.0, "label": "east", "output_name": "right"},
    {"index": 2, "angle_deg": 180.0, "label": "north", "output_name": "north"},
    {"index": 3, "angle_deg": 270.0, "label": "west", "output_name": "west"}
  ],
  "clips": [{"name": "static", "loop": true, "duration_s": 0.0,
    "frame_count": 1, "frame_duration_s": 0.08333333333333333, "time_scale": 1.0,
    "output_name": "static", "fps": 12.0, "stored_directions": [1],
    "mirrors": [{"target": 3, "source": 1, "transform": "flip-x",
      "ground_px": {"x": 2, "y": 3}}]}],
  "frames": [{"clip": "static", "direction": 1, "index": 0, "time_s": 0.0,
    "locations": [{"artifact": 0, "x": 0, "y": 0, "w": 4, "h": 4}]}]
}
```

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

In `--output-dir` mode only, one root holds one subject's export (D-16).
Before capture, read an
existing `manifest.json` and refuse exit 2 if its `subject` differs from the
new run's subject. A same-subject rerun remains allowed, including a changed
model hash. Subject is the input stem, not a content identity. A malformed or
unreadable manifest, or one lacking a string subject, cannot establish this
precondition: refuse before capture with the file and reason. Do not interpret
this check as permission to reuse an old schema; replay remains current-only.
`{subject}` is for naming inside one subject's root. This guard does not add
pruning or multi-subject ownership tracking. It does not inspect or guard a
positional `<stem>.json`: replacing a legacy sheet made from another subject
remains allowed.

**2. Preflight and staging.** In `--output-dir` mode, resolve and validate
every planned output path before Blender capture, including metadata/previews, duplicate names and
file/directory prefix conflicts. The chosen output root is resolved once;
its ancestors may be ordinary filesystem links, but no existing symlink at
or below that resolved root may be traversed as an output component or
overwritten as an output file. Recheck components before publication. Refuse
non-regular existing file targets and input/output overlap, including the
model and read configuration/palette/library files. The one explicit exception
is the `--settings-from` document: read it completely and close it before
capture, then allow it to be replaced in both forms, including
`--settings-from OUT/manifest.json --output-dir OUT` and positional replay
onto its own JSON. It receives the same staging/rollback protection as every
other target. In directory mode, do not follow a link outside the root.
Concurrent writers to the same root are unsupported; do
not promise isolation against filesystem changes by other processes.

In directory mode, a new root may be created when its immediate parent already exists as a
directory; do not create missing ancestors above the root. Nested directories
inside the root are created as needed.

The positional form retains exactly the existing `_check_targets` filesystem
preflight: refuse when a target's parent is not a directory, or the target
is a real directory (`is_dir()` and not `is_symlink()`), with exit 2. Keep
`publish()`'s behavior of moving a symlinked target aside and replacing it
with a regular file. Do not add directory mode's subject, symlink,
non-regular-target or input/output-overlap refusals to this form, including
when an input palette PNG is also an output target. In-place
`--settings-from` replay and rollback reporting remain shared behavior.

After successful rendering/encoding, create needed directories, stage every
file on the destination filesystem, and replace files under the existing
rollback mechanism. Publish the manifest last; roll it back with the others
if a handled failure interrupts publication. Readers must wait for successful
command completion; a many-file replacement is not an atomic snapshot for
concurrent readers. No successful partial export is reported.

**3. Failures and cleanup.** On a handled write/rename failure or interruption,
restore previous files and remove newly published files. Remove only newly
created empty directories and this run's temporary files; never remove an
existing directory or other content. Report output exit 6 for I/O failure,
or 130 for a handled interruption, naming the affected path. If rollback
itself fails, report each unrestored target and preserved
backup path honestly; do not claim earlier outputs were fully restored.
No power-loss or uncatchable-process-kill recovery guarantee is added.
Bad configuration and planned path collisions are usage exit 2, invalid model
input exit 3, geometry/depth overflow exit 4 and backend failures exit 5,
as in today's contract. A failure publishes no valid new manifest.

| Condition | Forms | Detection | Exit |
|---|---|---|---|
| Bad settings, inactive key or template syntax | Both, under their active-setting rules | Before capture | 2 |
| Directory-mode name, expanded-path collision or prefix error | `--output-dir` only | Before capture | 2 |
| Existing manifest has a different subject or invalid ownership record | `--output-dir` only | Before capture | 2 |
| Root is a file/non-directory; its immediate parent is missing/non-directory | `--output-dir` only | Before capture | 2 |
| Target is a directory or other non-regular file; symlink at/below root; input/output overlap except the loaded reuse document | `--output-dir` only | Before capture | 2 |
| Target parent is not a directory, or target is a real directory and not a symlink | Positional only, unchanged `_check_targets` | Before capture | 2 |
| Invalid model/input | Both | Input validation | 3 |
| Geometry or encoded-depth overflow | Both | Fitting/encoding | 4 |
| Backend failure | Both | Measure/render | 5 |
| Output filesystem I/O, stage/write/rename/rollback failure; directory creation or existing-manifest read I/O where applicable | Both; root creation/manifest ownership read only in directory mode | At the attempted operation | 6 |
| Output components become invalid after successful directory preflight | `--output-dir` only | Publication recheck | 6 |
| Handled interruption | Both | Any stage; roll back if publication started | 130 |

Manifest parse/subject errors are usage errors (2); an actual read I/O error
is output error (6). A rollback failure preserves the original failure class
(6 or 130) and reports backups; it never claims a complete restoration.
Only the rows marked shared apply to both forms; the new directory refusals
do not change legacy positional preflight or symlink replacement behavior.

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
numbers bundled into P-10 (cell, scale and anchor); D-14 subsequently adopts
those as the initial acceptance target in answer to Q-15.

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
owner decision on the final acceptance model. D-13 resolves Q-14.
Do not label the round-4 appearance approved or silently pin the
export's final acceptance to the old look.

### D-13. Latest owner-approved acolyte at review time

Owner signoff on 2026-10-24, via verified `mosk-manager` relay
`9aqym2znqa32juy547huw6mvg2`, answering final-checkpoint question message
`g6qgzq7kjekwv86fu3kfbdajww` with the round-05 links. For Q-14 the owner chose:

> "A: latest approved"

Use the latest acolyte explicitly approved by the owner at review time.
Record and freeze its model, library, palette and settings hashes for that
review. Do not pin the historical `physics-v2`/`library-v4` as the final
acceptance input or assume that a newer unapproved model qualifies.
Model rework remains a separate request. Model approval gates only EXP-7;
EXP-1 through EXP-6b use generated fixtures and can proceed independently.

### D-14. Start acceptance from the reviewed placement values

Owner signoff on 2026-10-24 through the same verified relay and question.
For Q-15 the owner chose:

> "A: start from these"

Use a 48x48 cell, 24 px/m, ground anchor (24,44), normal and depth outputs,
and one-pixel atlas padding as the initial acceptance target. If the revised
model overflows or a placement change is desired, stop and ask the owner;
never automatically shrink it or move its anchor. This settles the remaining
Q-6 placement values and Q-15, without approving colours, posture or any
other aspect of the model's appearance.

### D-15. Seven-slice plan approved and ready for issue processing

Owner signoff on 2026-10-24 through the same verified relay and question.
For Q-7 the owner chose:

> "A: approve, ready"

Originally adopted P-13 and seven ordered EXP-1 through EXP-7 slices. D-18
subsequently amends this plan to eight slices on the owner's instruction.
All design questions are resolved and the document is ready for issue processing.
The manager explicitly instructed this session to record and land the design,
post done with the path, commit and slice list, then stop without filing
issues. The manager arranges design review and `process-design-doc` next.

### D-16. Refuse a different subject in an existing output root

Owner decision, 2026-10-24; source: **manager relay of the owner's answers
to review 1**, verified `mosk-manager` message `4vxnn6as53vva49b8kdfjs26ai`
and `dispatch-export-design-revise-1.md` (SHA-256 prefix `66723cda71ed`).
For X-3 the owner chose:

> "Refuse (Recommended)"

A directory root holds one model's export. Before capture, refuse an existing
`manifest.json` whose `subject` differs, with usage exit 2. Same-subject
reruns remain allowed. `{subject}` names files within one model's root;
it does not authorize multi-model batching into a shared root. This amends
D-9's unconditional overwrite rule with the explicit P-9 preflight guard.

### D-17. Warn on mirror camera-condition violations, then export

Owner decision, 2026-10-24, through the same **manager relay of the owner's
answers to review 1**. For X-9 the owner chose:

> "Warn (Recommended)"

Export anyway, warning once with the clip and target/source pair when the
P-8 roll, angle-pair or sideways-perspective-offset conditions fail. Multiple
failed conditions for one pair share that warning. This does not infer model
symmetry or alter D-5's explicit transform records. EXP-2 checks conditions;
EXP-6b activates the warning and documents it in the current contract.

### D-18. Split the public transition into EXP-6a and EXP-6b

Owner decision, 2026-10-24, through the same **manager relay of the owner's
answers to review 1**. For X-10 the owner chose:

> "Split into 6a/6b (Rec.)"

Amend D-15's seven-slice plan to eight. EXP-6a switches legacy output to the
complete `moskophoros.export/1`, with new user settings still refused.
EXP-6b activates settings and `--output-dir`/`--formats`; EXP-7 depends on
6b. The public schema changes once, in 6a; 6b does not change its shape.
No option may be accepted and ignored. Each half owns the pinned test and
`docs/design.md` inventory below. The manager authorizes retaining readiness
once every review finding is addressed, followed by the same reviewer's
re-review; this is not a claim that the reviewer has approved the revision.

### D-19. Record the optional-sheet command form in vision V-2

Owner decision, 2026-10-24, through the same **manager relay of the owner's
answers to review 1**. For X-16 the owner chose:

> "Add dated note (Rec.)"

Add only a dated owner note under V-2 citing D-6: the `--output-dir` form may
write no combined sheet. Preserve all other vision text. The note describes
approved direction, not already delivered behavior, and lands by `docs-push`.

## Round-4 acceptance choices and retained alternatives

### P-10. Fixed cells and five stored acolyte directions

Five views plus mirrors are adopted only for the base unequipped version
(D-10). D-14 adopts the placement values as the initial acceptance target;
D-13 selects the final model. The rest of this section describes the reviewed
prototype, not an unqualified acceptance record.

Use the approved model and look at 24 px/m in fixed 48x48 cells, ground
pixel (24,44), with colour, normals and depth. Store `[0,4,3,2,1]` and map
7 from 1, 6 from 2, 5 from 3 for both unarmed clips. Use frame folders plus
per-clip atlases with one-pixel padding; include a combined-sheet run and
metadata-only replay checks in technical acceptance. Flat and lit previews
stay enabled with the accepted project's current light.

This reaches the consumer's logical cell/row layout through generic settings;
50x50 is the physical atlas slot, not the cell. Its compiler accepts only
`frame_NNN.png` inside direction folders: maps must live outside that colour
tree. The round-04 mixed-map mock-up is historical format evidence, not a
valid consumer handoff. EXP-7 uses
`animations{map}/{clip}/{direction}/frame_{frame:03}.png`; generic defaults
remain unchanged. Consumer validation rejects stray/stale frame PNGs loudly,
although other directory scanners may consume them. Keep fresh roots.
Local acceptance freezes the latest approved palette/library and settings
under D-13, not a shipped preset.
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

## Resolved questions

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

Resolved by D-10 and D-14. The owner answered five views plus mirrors
for the base unequipped version, not an unqualified approval of P-10's
placement bundle. D-14 subsequently resolves the remaining placement values
through Q-15. D-13 resolves model-version ownership through Q-14. Labelled
probe evidence remains round-04/q6.

### Q-7. Delivery and readiness

Resolved by D-15, amended by D-18: P-13's eight-slice plan is approved and the design is ready
for issue processing. The tracker was rechecked on 2026-10-24: only unrelated
#43 is open, and no PRs are open. No export epic duplicates the umbrella at
this check. This session files no issues.

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

Resolved by D-13: use the latest acolyte explicitly approved by the owner at
review time, freezing its model/library/palette/settings hashes for that
review. The historical pinned-model alternative was not selected. Technical
tests use generated models; only EXP-7 depends on model approval.

### Q-15. Acceptance placement after model rework

Resolved by D-14: start from the prototype's 48x48 cell, 24 px/m, anchor
(24,44), normal/depth outputs and one-pixel atlas padding. Ask the owner about
overflow or desired changes. Deferring the initial values until final review
was not selected; automatic shrinking or anchor changes are not authorized.

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

**D-3 byte-identity evidence belongs to EXP-6a and EXP-6b.** Each implementer,
before its switch, generates the rigged model from
`tests/blender/test_whole_command.py::rigged_model` once, records its SHA-256,
and runs the base and head in isolated output roots with that identical model,
generator and settings. Use `--clip walk --clip attack --once attack` as in
the existing whole-command baseline, excluding the fixture's deliberately
travelling `slide` clip; isolate configuration so live owner files cannot
affect either run. Cover the positional default-output invocation and
an otherwise identical opt-in depth/lit-preview invocation so colour, normals, depth,
flat GIFs and lit GIFs are all compared; flags used only for the comparison
must be identical at base/head. Record exact commands, base/head commits,
model and generator identity (including the model hash), and each emitted
image's base/head SHA-256 directly beside the PR's single `local-validation`
fence in the PR body. Keep that fence exactly in `docs/validation.md`'s
format: `test.blender <full current-head SHA> passed`. Include the same
commands, identities and image-hash table in linked `docs-push` evidence.
JSON/fingerprint differences are expected only across 6a's schema
switch. 6b must also keep the already-final `/1` default metadata unchanged.
Keep models/renders/logs locally under the acceptance folder, separate from
consumer evidence; publish the textual evidence with `docs-push` and link it
from the PR. Do not commit generated binaries or substitute a CI-only claim
for this local check. A mismatch blocks acceptance until explained and fixed
within D-3; no new look is implicitly approved by tests.

**Owner-approved evidence-placement clarification, 2026-10-24.** In response
to question message `87d8wvc6b394xpzh44qtx9p3q2`, the owner chose
"Beside the block (Rec.)", relayed by the manager in this session on
2026-10-24. This applies to both EXP-6a and EXP-6b: the structured fence
contains only the required test result; exact commands, model/generator
identity and the base/head image SHA-256 table go directly beside it in the
PR body and in linked `docs-push` evidence. Coverage is unchanged.

**Scale evidence (review 1, not a benchmark guarantee).** The reviewer's
`review-1/scale_probe.py`/`.log` reported 1,764 stored frames, 5,455 files and
a 3.3 MB, 175,147-line indented manifest; at 2,250 frames roughly 4.2 MB.
Existing `publish()` took 1.08 seconds fresh and 2.23 seconds replacing
existing files, with zero leftover hidden files. This pure temporary-folder
probe did not run Blender and does not measure the future publisher. It
supports ordinary staged publication in EXP-5, not an extra indexing/storage
subsystem. Capture still runs once per stored sample across output formats.

Every code slice follows [validation](../validation.md) and the planner at its
actual diff. The current catalog selects `test.blender` for any `src/` change,
even preparatory pure-code changes; those PRs need current passing local
evidence as well as required CI checks. No new dependency is proposed.
Evidence/design notes land with `docs-push`; implementation contracts tests
read, notably `docs/design.md`, travel with code under the documentation-as-code
rule. No generated art or binary model enters the repository.

## Delivery plan

### P-13. Eight slices with one public schema and a final owner gate

Approved by D-15 and amended by D-18. EXP-1 through EXP-6b are each one issue,
worktree and reviewable code PR. EXP-7 is a human acceptance issue with
evidence published by `docs-push`, not a manufactured code PR. Model rework
is outside every slice.

EXP-1 through EXP-5 provide tested internal capabilities. The existing command
continues its current sheet behavior/schema until EXP-6a switches the legacy
path to the complete `moskophoros.export/1`. EXP-6b activates new settings and
directory output with that same schema. No intermediate public schema or
long-lived feature flag is needed. No accepted setting may be ignored.

EXP-2 adds new rows to the single `SCHEMA`/`CLIP_SCHEMA` authority with an
internal inactive marker, including the new `export` group. Any user layer
setting an inactive key fails exit 2 before capture, naming source file,
key and line with "not available yet". New per-clip leaves have the same
gate. Helpers may construct typed values for internal tests without exposing
them to the command. Shipped `defaults.yaml`, `DEFAULTS` and their agreement
test filter to active rows; do not duplicate a second schema. Group/key-order
tests distinguish all definitions from publicly active settings. `--formats`
and `--output-dir` do not exist until EXP-6b.

EXP-6a can record/reload the complete new default fields through an internal
manifest decoder, but the user-file gate remains closed. Reuse accepts those
new fields only at their inactive defaults (`all`, empty maps, default export
templates/formats/padding and null per-clip overrides), and refuses non-default
new settings as unavailable before capture. This permits 6a to replay its own
output without accepting an ignored option. EXP-6b removes the temporary
markers/reuse restriction, ships the new defaults and activates both flags.

Dependency order: EXP-1 → EXP-2 → EXP-3 → EXP-4 → EXP-6a → EXP-6b → EXP-7.
EXP-5 depends on EXP-2 and also feeds EXP-6b. After EXP-2 it may proceed
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
  Implement P-13's inactive-row gate in `SCHEMA`/`CLIP_SCHEMA`, active-default
  agreement, group/key-order tests and file/line errors. Include pure mirror
  condition checks and once-per-pair diagnostic construction (D-17).
- **Phase:** internal configuration and preflight.
- **Depends on:** EXP-1.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-2, D-4, D-5, D-6, D-7, D-9, D-17, D-18.
- **Acceptance signals:** layer/reset cases resolve exactly; errors retain
  file/key locations; path conflicts fail before capture; a changed view
  cannot silently discard invalid direction/mirror references; user files
  cannot activate new rows; old defaults still load and agree with active
  rows in `tests/test_settings.py`; each violating mirror pair warns once.
  With eight directions, start 0, roll 0 and no sideways perspective offset,
  a correct `{7: 1}` pair must not warn for a nonzero facing-correction
  `model_yaw` (for example 90 or 30 degrees). Wrong angle pairs must warn
  regardless of that correction.
- **Out of scope:** encoding, filesystem mutation and command activation.
- **Open questions:** None.

### EXP-3. Encode frame files and clip atlases from addressed frames

- **Outcome:** one set of post-cleanup addressed frames produces any approved
  combination of individual PNGs, clip atlases and combined sheet, with maps.
- **Scope:** logical rectangles, variable clip-row counts, exact padding,
  encodings, ordered artifact descriptors and sample locations; stored-view
  previews at each clip's timing. Reuse shared image operations. Keep encoding
  separate from publication and preserve the old path for comparison until EXP-6a.
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
  palette/library; strict validation and reload to the settings layer. Use
  the full P-8a member/order contract, already pinned before this issue is
  filed, including array encodings for integer-keyed maps. Build manifest
  settings independently of `backend.settings_document`; assert job-settings
  byte identity under changes to manifest-only fields. Keep this internal
  until EXP-6a so no partially implemented schema becomes public.
- **Phase:** internal metadata and replay.
- **Depends on:** EXP-1, EXP-2, EXP-3.
- **Ordering:** critical path.
- **Relevant decisions:** D-3, D-5, D-7, D-8.
- **Acceptance signals:** encode/reload preserves overrides and inheritance;
  references match artifacts; mirror/anchor semantics hold; original config
  files are unnecessary; malformed references and old schemas are refused;
  new settings do not leak into strict capture-job keys. Review compares
  every serialized member and order against P-8a, not a later PR invention.
- **Out of scope:** CLI switch, consumer indexes and runtime shaders.
- **Open questions:** None.

### EXP-5. Publish nested output files with rollback

- **Outcome:** planned exports create directories and replace their files
  with manifest-last publication and honest rollback.
- **Scope:** filesystem preflight/confinement, input/output overlap checks,
  staging, replace-only-written policy, rollback, owned-empty-directory cleanup
  and backup diagnostics. Scope the new confinement/overlap/non-regular and
  D-16 subject refusals to directory mode per P-9's Forms column; positional
  `_check_targets` and replacement of symlinked targets remain unchanged.
  Include the explicit in-place-reuse exception. The publisher stays independent of image internals;
  preserve existing default publication behavior.
- **Phase:** filesystem effects.
- **Depends on:** EXP-2.
- **Ordering:** independent of EXP-3/EXP-4 after EXP-2; required by EXP-6b.
- **Relevant decisions:** D-6, D-7, D-9, D-16.
- **Acceptance signals:** injected failures restore prior bytes; only owned
  empty new directories are cleaned; stale/unrelated files survive; links
  cannot escape the root; incomplete publication has no valid new manifest;
  rollback failures identify preserved backups without claiming full restoration.
- **Out of scope:** pruning, crash recovery and concurrent-writer isolation.
- **Open questions:** None.

### EXP-6a. Switch legacy output to the complete export manifest

- **Outcome:** the positional command emits and replays the final `/1`
  manifest while preserving its existing image bytes and refusing new options.
- **Scope:** wire EXP-3/EXP-4 into the legacy path; switch `/15` to `/1` once,
  refusing older schemas; enforce P-13's inactive-default-only reuse rule.
  Move the full P-8a JSON contract into `docs/design.md`. Keep current sample
  planning and publication behavior; no directory mode yet. Update the
  schema/artifact test inventory below and record local byte-identity evidence.
- **Phase:** public schema transition, legacy path only.
- **Depends on:** EXP-1, EXP-2, EXP-3, EXP-4.
- **Ordering:** critical path; EXP-5 is not required for this legacy switch.
- **Relevant decisions:** D-3, D-8, D-18.
- **Acceptance signals:** legacy default images match base/head SHA-256
  evidence under Verification; `/1` reloads itself and `/15` fails clearly;
  all serialized fields have final meanings/order; non-default inactive reuse
  values and every new user-file key/flag are refused, never ignored.
- **Out of scope:** activation of direction/FPS/output settings, new CLI flags,
  nested publication, consumer assets and visual approval.
- **Open questions:** None. The test/document inventory below is part of scope.

### EXP-6b. Activate configurable directory exports

- **Outcome:** both command forms support all approved settings, output
  combinations and metadata replay end to end.
- **Scope:** activate settings; add `--output-dir`/`--formats` and their
  constraints; connect request planning, measure/render, common fitting,
  stylize/cleanup, encoding, metadata and publication. Update the capture
  builder's expected-frame check to use the shared resolved plan rather than
  reconstructing a global-FPS/full-ring plan. Blender still evaluates exact
  supplied times/angles and renders no aliases. Remove inactive markers and
  reuse restrictions, ship new defaults, activate D-17 warnings and P-9
  publication rules. Keep the `/1` schema unchanged. Document the full
  CLI/contract with the inventory below.
- **Phase:** public activation and integration.
- **Depends on:** EXP-1, EXP-2, EXP-3, EXP-4, EXP-5, EXP-6a.
- **Ordering:** critical path.
- **Relevant decisions:** D-1 through D-9, D-16 through D-19.
- **Acceptance signals:** generated-model command runs cover format combinations,
  per-clip rates/counts/subsets, full-view exceptions, maps/previews and fresh-root
  replay. Defaults match pre-activation image baselines with the same generator.
  No accepted option is ignored. The command retains 6a's complete `/1`
  shape and default metadata, and its help and tested contracts match the
  delivered behavior. In-place replay, same-subject reruns, wrong-subject
  refusal and mirror warning behavior have whole-command coverage.
- **Out of scope:** consumer integration, model changes and final visual approval.
- **Open questions:** None. The current capture wire already accepts arbitrary
  in-ring addressed samples and exact times: no renderer resampling or new
  wire field is needed. The caller validates the resolved plan; capture keeps
  its existing wire fields and carries no output paths/aliases/mirror policy.

**EXP-6a/6b pinned-test and documentation inventory.** Paths/sections refer
to the reviewed base `5788a7c4f6`; update names if moved, preserve obligations.

| Slice | Tests owned by the transition |
|---|---|
| EXP-6a | Convert all 20 `/15` pins in `tests/test_reuse.py` (10), `test_command.py`, `test_materials_command.py`, `test_shading_command.py` (2 each), `test_export.py`, `test_frames_command.py`, `test_settings_command.py`, `test_shading_settings_command.py` (1 each). Preserve old-schema refusal tests with updated expected current schema. |
| EXP-6a | Convert singleton `image`/`maps` assertions and exact JSON/order expectations to artifacts/locations in `tests/test_export.py`, `test_reuse.py`, `test_command.py`, `test_normal_map.py`, `test_depth_map.py`, `test_lit_previews.py`, `tests/blender/test_whole_command.py`. Preserve pixel, filename, map encoding and preview assertions. Add capture-settings isolation and default `/1` replay checks. |
| EXP-6b | Activate key/group/default expectations and design-example loading in `tests/test_settings.py` (review lines 88, 94–106); remove inactive-key/default-only-reuse tests in favor of full layered-settings and replay coverage. Extend settings/frames/command and Blender whole-command tests for all new behavior, including exact requested samples, mirror warnings and filesystem/refusal cases. |
| Both | Run planner-selected checks and current local Blender checks; include the Verification section's base/head image-hash evidence at each current PR head. |

The review's broad text search also found `tests/blender/test_normal_depth_capture.py`
using `probed["before"]["image"]` for a Blender image-state tuple, not the
export JSON. Do not mechanically rewrite that unrelated assertion. The
actual export-shape/schema inventory spans 12 files; the review's 13-file
count includes that incidental match.

| Slice | `docs/design.md` sections owned by the transition |
|---|---|
| EXP-6a | Vocabulary: generic manifest/artifact terms while the public command still writes a sheet. CLI `--settings-from` row and positional output paragraph: final schema/artifact names, unchanged filenames. Reuse: current `/1` only, complete field validation, temporary inactive-default restriction. Export JSON: full P-8/P-8a member/order contract. Reproducibility: `/1` default replay and fingerprint boundaries. Mark directory-only/new-setting behavior planned until 6b; do not claim it is active. |
| EXP-6b | Vocabulary and CLI synopsis/output paragraph: both forms, optional sheet, formats and one-subject roots. Settings table, example and per-clip merging: active fields/defaults/gates removed. Exit codes: P-9 table including 130 and in-place replay. Clips and sampling: per-clip FPS and warning rules. Bounds: only stored directions, common fit. Reuse: full settings with no temporary restriction. |
| EXP-6b | Capture job contract: capture-relevant subset, unchanged exact keys, frames in resolved-plan order, global `fps` does not time per-clip clips. Export layout: configured direction order, artifacts, templates, padding and mirror geometry/anchors. Previews: stored-direction order and per-clip cadence. Reproducibility: both forms, output roots and changed-format fingerprint caveat. Remove delivered per-frame/other-output items from Deferred, retaining genuinely deferred formats. |

`docs/design.md` is read by tests and travels with each code change. The
approved V-2 note lands now by `docs-push`, separate from those code contracts.

### EXP-7. Review the implemented acolyte export with the owner

- **Outcome:** explicit owner acceptance with reproducible evidence identifying
  the exact input, settings, generator and implementation revision.
- **Scope:** apply D-13's model policy and D-14's placement policy; base
  unequipped acolyte has five views plus mirrors, walk six at 8 FPS, idle
  four at 6 FPS. Produce frame folders and clip atlases/maps, a combined-sheet
  comparison, and replay from metadata alone. Compare captured/mirrored views
  and old sprites on a labelled page. Check timing, counts, pixels and replay
  separately from visual judgement. Always use a fresh local output root.
  Load export settings from a frozen, hashed `--config FILE` under the local
  acceptance folder, capturing the approved palette/library and required
  project values there; do not depend on a changing live project layer.
  Nothing under `~/.config/moskophoros/` changes without the owner. Route
  normal/depth frames outside the colour frame tree using
  `animations{map}/{clip}/{direction}/frame_{frame:03}.png`; hand off only
  `animations/` to the consumer's existing frame compiler, without running
  that compiler or writing its repository in this slice. Show the actual
  frozen preview-light values to the owner: the historical project comment
  says "scaled for 128x128 cells" while this target is 48x48. Do not silently
  retune the light; desired changes follow the owner gate.
- **Phase:** owner acceptance and documentation closeout.
- **Depends on:** EXP-6b; additionally the owner-selected model/placement gate.
- **Ordering:** critical path to epic completion; does not block EXP-1–EXP-6b.
- **Relevant decisions:** D-1 through D-19.
- **Acceptance signals:** current technical checks pass; exact commands and
  hashes are recorded; the owner explicitly approves the implemented export
  with dated provenance. Stop for the owner if the chosen model is unapproved,
  overflows, lacks expected clips or needs appearance work. Never silently
  substitute an input, refit scale or close the epic on tests alone.
- **Out of scope:** model/look refinement, portraits, equipped/asymmetric asset
  creation, game writes and private compilation. Generated fixtures cover
  full-direction exceptions mechanically.
- **Open questions:** None. D-13 and D-14 are explicit acceptance gates for
  review inputs and targets. This is documentation-only acceptance: evidence lands
  with `docs-push`, with no code PR needed.

## Review 1 disposition

Review: local `review-claude-1.md`, SHA-256
`472fb39140a29b1433b495e429ffdfd5fab020ada76ebe522b21f48dae1e2308`,
against design commit `5788a7c4f6`; verdict: 0 blocking, 12 should fix,
5 minor. Revision authority: manager dispatch SHA-256
`66723cda71ed34bd928c437a65bebb2f43e153e7b4336b56e355cf670dbbd61f`,
verified relay `4vxnn6as53vva49b8kdfjs26ai`, dated 2026-10-24.
The reviewer owns the next verdict; the dispositions below report this
designer's edits, not review approval. No findings are declined.

| Finding | Resolution in this revision |
|---|---|
| X-1 | P-13/EXP-2 specify inactive schema rows, source/key/line exit-2 refusals, active defaults/group tests and EXP-6b-only flags. EXP-6a reuse accepts only the inactive default values it emits. |
| X-2 | P-8a/EXP-4 build manifest settings independently and require byte-identical capture settings when new manifest fields vary. EXP-6b rewrites Capture job wording for the subset, resolved-plan order and global FPS. |
| X-3 | D-16 records owner “Refuse”; P-7/P-9 restrict roots to one subject, with a pre-capture exit-2 guard and within-root meaning for `{subject}`. |
| X-4 | P-9 enumerates refusal/operation timing and exits 2–6/130, new-root parent behavior and rollback-failure reporting. Re-review 2 found the form scope partial; X-19 below explicitly limits new refusals to directory mode. |
| X-5 | P-9 explicitly permits replacing the fully read/closed `--settings-from` document in both forms, with normal rollback protection. |
| X-6 | P-7 limits name and expanded-template refusals to directory mode; positional output retains legacy names and checks template syntax only. |
| X-7 | P-8a pins the full ordered member contract and complete structural example now, before EXP-4 filing; integer-keyed JSON maps are sorted arrays with explicit null/empty/all semantics. |
| X-8 | P-7 gives exact grammar, no brace escapes/non-ASCII literals, strict frame widths, per-expansion path checks and explicit dot-component behavior. |
| X-9 | D-17 records owner “Warn”; P-8 gives mirror camera conditions and once-per-pair warnings, with EXP-2 checks and EXP-6b activation/documentation. Re-review 2 corrected its review-1 angle formula; X-18 below applies that correction. |
| X-10 | D-18 amends D-15 to eight slices, splitting EXP-6a schema transition from EXP-6b activation. Both have named pinned-test and design-section inventories; incidental Blender image-state match is identified, not changed. |
| X-11 | Verification assigns each 6a/6b implementer the same-generated-model base/head comparison, exact commands, per-image SHA-256 values and current local-validation evidence; binaries stay local. |
| X-12 | P-1/P-7/P-10/EXP-7 route maps outside `animations/` using `animations{map}/…`; only colour frames enter the consumer handoff. Historical mixed-map probe is not called consumer-ready; stale-frame validator behavior is clarified. |
| X-13 | EXP-7 requires a frozen hashed local `--config`, no live config edits, and explicit display of the historical 128x128-light comment versus the 48x48 target. |
| X-14 | P-8 explains the derived anchor shift `W-2*gx`, including odd widths, and requires consumers to use the per-mirror anchor. No extra warning policy is added. |
| X-15 | Verification records the reviewer's measured 5,455-file/3.3-MB scale and 1.08/2.23-second publication probe, clearly as existing-code evidence rather than a performance promise. |
| X-16 | D-19 records owner “Add dated note”; only the dated V-2 note is added in `docs/vision.md`, citing D-6 and distinguishing planned behavior. |
| X-17 | P-8 qualifies cross-mode fingerprint identity and defines positional root/base names; P-7 omits `clips` from shipped defaults and states exact FPS warning provenance/equal-value/still behavior. Current `/15` evidence remains correct. |

## Review 2 disposition

Re-review 2 inspected `56e503e90c` and reported 15 review-1 findings resolved,
X-4/X-9 partial, plus X-18 blocking, X-19 should fix and X-20 minor. Report:
local `review-claude-2.md`, SHA-256
`6e3f46d4d39363bf1c9890fd6c1d3f44e2f6d0b66680505db8b9d07fbed244b8`.
Revision authority: manager's `dispatch-export-design-revise-2.md`, SHA-256
`175295f64618ea92f7f0356d6fcadd6034da5939f15b3172bcec254f4ed26467`,
2026-10-24. These corrections change no owner decision or slice boundary.

| Finding | Resolution |
|---|---|
| X-18 (completes X-9) | P-8 uses `theta_target + theta_source ≡ 0 (mod 360)` with direction angles defined independently of the facing correction. The reviewer's `review-2/mirror_condition_probe.py`/`.log` confirms correct 45°/315° pairs for yaw 0/90/30 and rejects the old formula's wrong pairs. EXP-2 requires nonzero-yaw coverage; D-17 remains unchanged. |
| X-19 (completes X-4) | P-9's Forms column and prose scope subject, symlink, overlap, non-regular and new-root checks to `--output-dir`. Positional output keeps exactly `_check_targets`' two filesystem refusals and `publish()`'s symlink replacement; shared failures, in-place reuse and rollback remain shared. EXP-5 repeats the boundary. |
| X-20 | P-7/P-8a distinguish original identity from informational directory-mode `output_name` values in positional output, with no directory-name validation. Artifact paths are the actual filenames. |

The reviewer said fixing X-18/X-19 makes the design ready and needs only a
quick check. This revision addresses all three; the manager arranges that
check. No reviewer approval of this new commit is claimed here.

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
The detailed contracts and acceptance choices were addressed in subsequent
rounds before the final dependency-ordered slices and readiness signoff.

Round 3 resolved Q-9, Q-10 and Q-11 as D-7, D-8 and D-9. Its round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-03/index.html`.
Verified relay `zrbvdx42r5mqc9vwavgcrkvbfn` records the owner's signoff dated
2026-10-24. Acceptance values, visual probes, portrait scope and readiness
were subsequently addressed in rounds 4 and 5. No implementation is authorized
by this design session.

Round 4 answered Q-6's direction scope, Q-12 and Q-13 as D-10, D-11 and D-12.
Its round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-04/index.html`.
The fresh locked render and local crop/layout probes succeeded as recorded
above. Verified relay `cu65sdzfp57fn7hhp3jf637m86` records the owner's answers
dated 2026-10-24. The owner requested separate model/look rework; round 5
resolved the remaining model/placement questions and approved delivery slices
with those choices isolated to the final owner-review gate.

Round 5 resolved Q-14 (review model), Q-15 (initial placement policy) and Q-7
(seven slices and readiness) as D-13, D-14 and D-15. Its round folder:
`file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-format-design/round-05/index.html`.
The placement section reproduces the earlier labelled image as historical
context, explicitly not a new model/look approval. Verified manager relay
`9aqym2znqa32juy547huw6mvg2` records all three owner answers dated 2026-10-24,
responding to question message `g6qgzq7kjekwv86fu3kfbdajww`. The design was
marked `ready for issue processing` at that checkpoint, with all seven
original slices unprocessed.

Review 1 subsequently found twelve should-fix and five minor items, with no
blocking finding. The owner answered the four decision items through the
manager on 2026-10-24 (D-16 through D-19). This revision addresses X-1 through
X-17 as mapped above and retains readiness under the revision brief's express
condition that every finding be addressed. The V-2 note landed with that
revision. Re-review 2 then requested X-18 through X-20; they are addressed
above without changing D-1 through D-19. All eight slices remain unprocessed.
Publish this design revision, report done with one line per new finding,
and stop for the manager to arrange the quick reviewer check. No review
approval or issue creation is claimed. After review, `process-design-doc`
processes the epic first and exactly one child per invocation, with separate
approval for every tracker artifact. This session files no issues.

## Issue-processing cursor

2026-10-24: processing authorized by the manager under
`dispatch-process-export.md` (SHA-256 prefix `d9fbd55ee7ee`). The manager
signed off `drafts/epic-v1.md` (SHA-256
`26e73801395826368207d672a3a1f2b57804de6469ea4fd59dcb177ec87a3c7e`).
Epic [#153](https://github.com/coghex/moskophoros/issues/153) was created
with that exact body and the existing `epic` label. No review labels were
added. Next entry: EXP-1; eight child drafts/signoffs remain. The earlier
no-issue-creation instructions above describe the completed design phase.

2026-10-24: the manager signed off `drafts/exp-1-v1.md` (SHA-256
`b6c2c6c26e6a1848e52ff336aa09227ffb58fdf80828e5955106c2a303c1124f`).
EXP-1 [#154](https://github.com/coghex/moskophoros/issues/154) was created
with that exact body and the existing `enhancement` label, and linked on its
still-unchecked epic #153 checklist line. No review labels were added.
Next entry: EXP-2; seven children remain to be drafted and signed off.

2026-10-24: the manager signed off `drafts/exp-2-v1.md` (SHA-256
`eea0c5567bf66f3214b2e39ea8f0f899e0f12fa6d4f1245e122fa763f0c20558`).
EXP-2 [#155](https://github.com/coghex/moskophoros/issues/155) was created
with that exact body and the existing `enhancement` label, and linked on its
still-unchecked epic #153 checklist line. No review labels were added.
Next entry: EXP-3; six children remain to be drafted and signed off.

2026-10-24: the manager signed off `drafts/exp-3-v1.md` (SHA-256
`4cc6e80963a8ff4ad38664020669f51234e67d879fe17302e6b2ecfe43c45888`).
EXP-3 [#156](https://github.com/coghex/moskophoros/issues/156) was created
with that exact body and the existing `enhancement` label, and linked on its
still-unchecked epic #153 checklist line. No review labels were added.
Next entry: EXP-4; five children remain to be drafted and signed off.

2026-10-24: the manager signed off `drafts/exp-4-v1.md` (SHA-256
`089dfd6a0b0b7719dfc00566a63bfb9d2aeef0e16e7ba84cf32ea5aea85bf621`).
EXP-4 [#157](https://github.com/coghex/moskophoros/issues/157) was created
with that exact body and the existing `enhancement` label, and linked on its
still-unchecked epic #153 checklist line. No review labels were added.
Next entry: EXP-5; four children remain to be drafted and signed off.

2026-10-24: the manager signed off `drafts/exp-5-v1.md` (SHA-256
`61639043ba58528d03db3d7bd76057bdf74540357a73659669d3bfa1e242bd7d`).
EXP-5 [#158](https://github.com/coghex/moskophoros/issues/158) was created
with that exact body and the existing `enhancement` label, and linked on its
still-unchecked epic #153 checklist line. No review labels were added.
Next entry: EXP-6a; three children remain to be drafted and signed off.
