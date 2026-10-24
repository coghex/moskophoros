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

## Open questions

### Q-1. Output choices and consumer boundary

Resolved by D-1.

### Q-2. Clip timing

Resolved by D-2. Actual acolyte counts and cadence remain under Q-6.

### Q-3. Default compatibility

Resolved by D-3.

### Q-4. Direction subsets, names and mirroring

Resolved by D-4. Actual five-view acceptance still needs Q-6's labelled
visual evidence. Exact settings syntax remains part of Q-9.

### Q-5. Output paths, maps, naming and publication

Resolved by D-6. Q-9 retains the detailed output contract.

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

Resolved by D-5. This is not visual signoff on any model's symmetry.

### Q-9. Detailed settings, metadata and output contract

Resolved by D-7.

### Q-10. Metadata and reuse

Resolved by D-8.

### Q-11. Output replacement and stale files

Resolved by D-9.

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
