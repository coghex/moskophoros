# Moskophoros vision and design guardrails

**Status: proposed 2026-09-29.** Drafted from the founding design
conversation; it becomes the heading once the owner confirms it. Delete this
paragraph on confirmation.

Moskophoros turns animated 3D models into pixel-art sprite sheets that stay
consistent in every direction, and grows into a general image tool for game
art. It exists because AI image generation cannot keep one subject coherent as
it rotates: proportions, pose and placement drift between directions. Owner
direction was consolidated on 2026-09-29 from the founding design
conversation. This is context for `$guide` and fresh development sessions, not
a claim that every feature is implemented. Current work and coverage belong in
the tracker and [guide reports](guide/).

New explicit owner decisions can revise this guide. Record the decision and
its date beside the change; do not silently change intent to fit new code or
an agent recommendation. Preserve these principle IDs.

## Product and boundaries

### V-1. A generic tool that belongs to no game

Moskophoros serves the owner's games (Synarchy, and its rewrite Hetoimasia)
but never integrates with them, reads their files, or emits their private
layouts (owner decision 2026-09-29). Its vocabulary is its own:

- **subject**: the thing rendered, a model plus any attachments
- **clip**: one animation; a static sprite is a one-frame clip
- **view**: the camera setup (see V-6)
- **direction**: one camera angle within a view
- **frame**: one sampled instant of a clip from one direction
- **sheet**: the packed output image and its metadata
- **variant**: the same clip rendered with a different prop or palette

Game concepts such as units, factions or tiles are not part of the tool. Characters,
creatures, buildings, items and flora all go through the same pipeline (owner
decision 2026-09-29). A game-specific output layout, if ever wanted, is output
configuration, not a code path.

### V-2. A conventional command-line tool

The interface is `moskophoros [options] <infile.glb> <outfile.png>` (owner
decision 2026-09-29), writing the sheet plus a JSON sidecar beside it that
describes every frame's rectangle, direction angle, clip timing and anchor.
Options have sensible defaults so the bare command produces a usable sheet.
The tool is scriptable and non-interactive. The same inputs and options
produce byte-identical output.

An interactive editor with touch-ups and history is a stretch goal (V-9), not
current scope.

### V-3. Binary glTF is the canonical input

`.glb` is the input format (owner decision 2026-09-29: the owner delegated the
choice). It is an open, single-file standard that carries mesh, skeleton,
every animation and embedded textures, and is readable without Blender, so a
future renderer can consume the same files. Most AI model generators and
riggers export it directly.

Blender-only features (constraints, IK, drivers, NLA) must be baked into
keyframes at export. Accepting `.blend` directly is a deferred convenience. If
added, it converts to `.glb` first, and nothing after that step sees anything
but glTF. `.fbx` is out of scope.

## Pipeline

### V-4. Explicit stages with file boundaries

The pipeline runs in stages, each consuming and producing files plus a
manifest:

1. **capture**: render frames and auxiliary buffers from the 3D subject
2. **stylize**: turn captured buffers into pixel art (V-8)
3. **cleanup**: pixel-level fixes and temporal stability
4. **export**: pack frames into sheets and metadata

A stage depends only on its predecessor's files, never on its internals.
Per-stage caching, so a stylize change does not re-render, is planned; it
supports the owner's need to iterate on the look quickly.

### V-5. Blender is the render backend, behind one boundary

Blender is an integral part of the workflow for now (owner decision
2026-09-29). Capture runs headless Blender (`blender -b`) on the `.glb`. All
`bpy` code lives in one backend module that the rest of the tool calls through
the capture boundary; nothing else imports `bpy` or depends on a `.blend`
scene. The Blender binary comes from `--blender`, then `$MOSKOPHOROS_BLENDER`,
then `PATH`, and the tested Blender version is pinned and recorded.

Replacing Blender with a custom glTF renderer is possible later, not planned.
The boundary exists so it would mean swapping one backend, not rewriting the
tool.

### V-6. Views are parameters, not special cases

A view is a projection (orthographic for now), a camera pitch, a direction
count and a start angle (owner decision 2026-09-29). Directions are evenly
spaced around the subject: 1, 2, 4 and 8 are required, and other counts are
allowed. Named presets are shorthand only:

| Preset | Pitch | Notes |
|---|---|---|
| `topdown` | 90° | |
| `side` | 0° | 2 directions give right and left |
| `iso` | 30° | 2:1 pixel-art dimetric; tile diamonds are exactly twice as wide as tall |
| `iso-true` | 35.264° | true isometric |

A start angle of 45° gives, for example, four diagonal isometric directions.
No preset gets behaviour that its parameters do not explain.

### V-7. Consistency across directions and frames is the product

Everything that AI generation gets wrong must be structurally impossible here:

- One scale per sheet, shared by every clip and direction, so the subject
  never changes size.
- A fixed ground anchor that lands on the same pixel in every frame and
  direction.
- Lighting fixed to the camera, not the subject, so shading reads the same from
  every direction.
- Subject root motion snapped to whole pixels, so sprites do not wobble.
- Deterministic sampling of each clip at a stated frame rate.

A defect here outranks any stylistic improvement.

## Style and editing

### V-8. Stylization is deferred and pluggable

The owner will set the final look later, one pass at a time (owner decision
2026-09-29). Until then, output is deliberately plain: a camera-fixed light, a
hard-edged downsample to the cell size, and binary alpha. There is no palette,
outline or cel shading. Capture must not bake in a look. Stylize and cleanup
are replaceable passes, so palettes, outlines, shading steps and pixel cleanup
can be added without touching capture or export. Candidate techniques from the
design conversation are options, not accepted direction:

- rendering at 4–8× size and shrinking by picking each block's most common color
- palette quantization
- 1-pixel outlines where depth or surface direction changes sharply
- stepped (cel) shading

### V-9. Addressable, reproducible frames keep editing possible

Every output frame has a stable address: subject, variant, clip, direction and
frame index. Generation is deterministic (V-2). This is what later lets hand
touch-ups be stored as overrides keyed by address, reapplied after a re-render,
with history as a log of those overrides. The editor and history are a stretch
goal (owner decision 2026-09-29). Build nothing for them now, but do not choose
designs that make frames anonymous or output non-reproducible.

### V-10. General image manipulation grows from the same operations

The tool is meant to become a general image-manipulation toolkit for the
owner's game art. Image operations (resize, quantize, palette remap, outline,
trim, contact sheet) are composable library functions that the 3D pipeline
uses and that later commands can expose directly. The 3D-to-sheet path comes
first. Other commands are added for a concrete need, not in advance.

## Inputs, implementation and evidence

### V-11. Model conventions are validated, not assumed

The owner builds and rigs models with AI assistance (owner decision
2026-09-29), so input quality varies. The tool states its expectations and
checks them with clear errors naming the file, clip and problem:

- glTF's own axes and units: Y-up, meters, the subject faces +Z
- one named glTF animation per clip
- clips played in place, or root motion handled explicitly

A malformed or unexpected input is a readable failure, never a silently wrong
sheet.

### V-12. Python, and the owner's eye as the acceptance gate

Python with numpy and Pillow (owner decision 2026-09-29), matching Blender's
Python API. Keep dependencies few and pinned. Automated tests cover what can be
checked mechanically: layout arithmetic, determinism, JSON metadata, view
geometry and input validation. Whether the output is right is decided by the
owner looking at it. A slice is done when the owner reviews the sheet and
approves it, not when it integrates with a game (owner decision 2026-09-29).
Favor effectiveness first and efficiency second, without team-scale process.

## Planned first slice

These are planned mechanisms, not yet built:

- `moskophoros [options] <infile.glb> <outfile.png>` with the view options of
  V-6, `--clip`, `--fps`, `--cell` and `--blender`
- headless Blender capture of every clip × direction × frame
- the plain output of V-8
- one PNG sheet (one row per clip × direction, one column per frame) and its
  JSON sidecar
- done when the owner approves the output of a real animated model

## Unresolved choices

- The exact JSON sidecar schema, and whether to also offer a common de facto
  format such as Aseprite's JSON.
- Default frame rate and cell auto-fit rules (the padding around the subject's
  bounds across all frames).
- Root-motion policy: strip, snap, or report.
- The pinned Blender version.
- The first test model: one of the owner's, or a freely licensed rigged
  `.glb` as a stand-in.

## Continuing after a context reset

Run `$guide` after a meaningful batch of work. It compares merged code and
changed issues with these decisions from the cursor in
[`guide/CURSOR.md`](guide/CURSOR.md). Guide needs a git repository with a
default branch, so it starts once the project is under version control. Update
this document only for accepted changes in intent. When no settled next slice
exists, discuss the next unmet goal or unresolved choice before designing more
work.
