# Moskophoros design

**Status: accepted by the owner on 2026-09-29; ready for implementation.**

The concrete design for the first working version (**slice 1**). The
direction it serves is in [the vision](vision.md); each section names the
principles it implements. Everything here is decided. A choice not yet made is
listed under [Deferred](#deferred), never left implicit. Change this document
when a decision changes, with its date.

Decisions below were settled on 2026-09-29 unless marked otherwise.

## Vocabulary

(V-1)

| Term | Meaning |
|---|---|
| **subject** | Everything in the input file's default scene that is rendered. Named after the input file's stem. |
| **clip** | One glTF animation, identified by its name. A file with no animations has one clip, `static`. |
| **view** | The camera setup: projection, pitch, direction count and start angle. |
| **direction** | One subject rotation within a view, identified by its index and angle. |
| **frame** | One image of one clip at one sample time from one direction. |
| **cell** | The fixed-size rectangle every frame occupies. |
| **ground point** | The point in subject coordinates that always lands on the same cell pixel. |
| **sheet** | The output PNG and its JSON description. |
| **variant** | The subject with a different prop or palette. Slice 1 has one, `default`. |

## CLI

(V-2)

```
moskophoros [options] <infile.glb> <outfile.png>
```

| Option | Default | Meaning |
|---|---|---|
| `--view NAME` | `iso` | Preset: `topdown`, `side`, `iso` or `iso-true`. |
| `--pitch DEG` | from preset | Camera pitch, 0 to 90 inclusive. |
| `--directions N` | from preset | Direction count, 1 to 64. |
| `--start-angle DEG` | from preset | Angle of direction 0. |
| `--model-yaw DEG` | `0` | Corrects a model that does not face +Z (see [Input contract](#input-contract)). |
| `--clip NAME` | every clip | Repeatable. Selects clips and their order in the sheet. |
| `--once NAME` | none | Repeatable. Marks a selected clip as one-shot; all others loop. |
| `--fps N` | `12` | Target sampling rate, greater than 0. |
| `--ppm N` | auto | Pixels per meter, greater than 0. |
| `--cell WxH` | auto | Cell size in pixels, each 1 to 4096. |
| `--ground X,Y,Z` | `0,0,0` | Ground point in subject coordinates, meters. |
| `--ground-px X,Y` | auto | Cell pixel corner the ground point lands on. |
| `--root-motion MODE` | `error` | `error` or `keep`. See [Root motion](#root-motion). |
| `--supersample N` | `8` | Capture resolution multiplier, 1 to 16. |
| `--reduce NAME` | `plain` | How each supersampled block becomes one pixel: `plain`, the alpha-weighted mean, or `mode`, the most common colour. See [Stylize](#stylize). |
| `--palette FILE` | none | Map colours to an ordered `.hex`, `.gpl` or `.png` palette. See [Stylize](#stylize). |
| `--no-palette` | off | Drop a reused palette; cannot accompany `--palette`. |
| `--settings-from FILE` | none | Reuse settings from an earlier sheet's JSON. See [Scale and ground point](#scale-and-ground-point). |
| `--no-preview` | off | Skip the animated previews. |
| `--work-dir DIR` | temporary | Keep capture output in `DIR` instead of a deleted temporary directory. |
| `--blender PATH` | discovered | Blender executable. See [Capture](#capture). |
| `--any-blender` | off | Allow a Blender version other than the supported one. |

Without `--clip`, every clip is selected in the file's animation order:
ascending animation index (owner decision 2026-10-01).

`<outfile.png>` must end in `.png`. The JSON is written beside it, at the same
path with `.json` replacing `.png`. Previews are written as
`<stem>.<clip>.gif` beside it; a clip name is made filename-safe by replacing
every character outside `A–Z a–z 0–9 . _ -` with `_`. If two clip names become
the same after that, the second and later previews gain the suffix `-2`, `-3`,
and so on, in sheet order. Each clip takes the smallest suffix whose name is
not already taken, including by another clip's own name, so no two previews
share a file (owner decision 2026-10-01). Cleaned names are compared ignoring
ASCII case on every platform, so `Walk` and `walk` collide and the later one
in sheet order takes the next free suffix: `hero.Walk.gif`, `hero.walk-2.gif`.
"Another clip's own name" is its cleaned name, so `a b`, `a/b` and `a b-2`
give `a_b`, `a_b-3` and `a_b-2` (owner decisions 2026-10-02).

Existing outputs are overwritten. All outputs are written to temporary files
and renamed into place only after the whole run succeeds, so a failed run
leaves earlier outputs untouched. Publishing is all-or-nothing: if renaming
fails partway, the outputs already replaced are rolled back and the earlier
ones restored before the run fails. An output that cannot be written, on a
full disk, without permission or because a rename fails, is an output error
(exit 6) naming the output and the reason, with the earlier outputs kept
(owner decision 2026-10-03). A run replaces only the files it writes
and never deletes others, so previews from an earlier run that this run does
not write, such as a dropped clip's or under `--no-preview`, stay as they
were (owner decisions 2026-10-01). Errors go to stderr as
`moskophoros: error: <message>`.

With `--work-dir DIR`, `DIR` must be nonexistent or an existing empty
directory. An existing nonempty directory is a usage error (exit 2) naming
the directory, and its contents are untouched. The capture workspace contains
separate `measure/` and `render/` directories, each with `job.json`, eventual
`result.json` and produced buffers. An explicitly supplied workspace retains
available artifacts after success or failure; normal temporary capture
workspaces are deleted in either case. Retention does not make an incomplete
phase a valid result or supply a replay interface. Reusing a retained location
requires choosing a new or empty directory (owner decision 2026-09-30).

### Option validation

Each of these is a usage error (exit 2) unless stated otherwise (owner
decision 2026-10-01):

- A numeric option given `nan` or `inf`.
- `--ground-px` coordinates that are not whole numbers 0 or greater. Whether
  the point lies inside the cell is an [overflow](#scale-and-ground-point)
  question, not a usage one.
- The same clip named twice with `--clip`, or twice with `--once`.
- A `--once` naming a clip absent from an explicit `--clip` list. Without
  `--clip`, a `--once` naming a clip that does not exist is an
  [input error](#input-contract).
- A single-value option given more than once; the last value does not win.
- A `--reduce` value other than `plain` or `mode` (owner decision 2026-10-04).
- `--palette` together with `--no-palette`, or either option repeated.
- A bad palette file: see [Palette inputs](#palette-inputs). These errors name
  the file and, for text errors, the line, and precede every Blender invocation,
  including its version probe (owner decisions 2026-10-04).

`--start-angle` and `--model-yaw` accept any finite number of degrees; the
direction formula's `mod 360` handles wrapping. `<infile.glb>` has no suffix
requirement; its content is checked under the [input contract](#input-contract).
A usage error prints the usage synopsis to stderr, followed by the
`moskophoros: error: <message>` line.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. |
| 1 | Internal error (a bug); a traceback is printed. |
| 2 | Usage error: bad option, value or combination. |
| 3 | Input error: see [Input contract](#input-contract) and [Root motion](#root-motion). |
| 4 | Overflow: the subject does not fit a fixed cell and scale. |
| 5 | Backend error: Blender missing, wrong version, or failed. |
| 6 | Output error: an output could not be written (a full disk, no permission, a failed rename). The message names the output and the reason; the earlier outputs are kept, and no usage synopsis or traceback is printed (owner decision 2026-10-03). |
| 130 | Interrupted (Ctrl-C): `moskophoros: error: interrupted`, no traceback, nothing published (owner decision 2026-10-01). |

## Input contract

(V-3, V-11)

The input must be a binary glTF 2.0 file: magic `glTF`, container version 2,
with a JSON chunk. The tool relies on glTF's own conventions: Y is up, units
are meters, and the subject faces +Z. A model facing elsewhere is corrected
with `--model-yaw`, a rotation in degrees about the vertical axis applied
before any direction rotation, with the same sign convention as direction
angles.

The subject is the scene named by the file's `scene` property, or scene 0 when
it is absent. Every mesh in it is rendered. Cameras and lights in the file are
ignored.

Checks, each an input error (exit 3) naming the file and the problem:

- the file cannot be read, or is not binary glTF 2.0
- the file has no scenes
- the structure the tool reads is malformed (owner decision 2026-10-01): a
  `scene`, node, child, animation channel, sampler or accessor reference
  names an object that does not exist; the node hierarchy is not a forest
  (a node with two parents, or a cycle); or an animation sampler's input
  accessor lacks the one-element `min` and `max` that give the clip's range.
  Other glTF rules are left to Blender's importer.
- the file changes during capture; the [capture contract](#capture-job-and-result-contract)
  defines the digest checks (owner decision 2026-09-30)
- an animation has no name or an empty name (owner decision 2026-10-01), or
  two animations share a name (the message gives the animation's index)
- an animation uses `CUBICSPLINE` interpolation, whose tangents Blender's
  importer replaces with its own, or a `KHR_animation_pointer` channel that
  animates a mesh's morph weights (`/meshes/N/weights`), of which the
  importer keeps only one animation per mesh. Neither could be measured
  faithfully; the message names the file, the clip and the problem (owner
  decision 2026-10-02)
- a `--clip` or `--once` names a clip that does not exist
- a clip travels across the ground (see [Root motion](#root-motion))

A subject whose rendered height, measured over every sample, is under 0.01 m
or over 100 m produces a warning about possible unit errors but continues.

Slice 1 renders base color from textures and material color. Vertex colors are
not supported.

## Camera and directions

(V-6)

All geometry is in glTF coordinates: +X right, +Y up, +Z toward the viewer at
direction 0.

**The camera never moves; the subject turns.** The camera is orthographic and
centered on the ground point. Pitch `p` is the angle between the viewing
direction and the ground: 0° looks horizontally, 90° looks straight down.

- The camera sits in direction `(0, sin p, cos p)` from the ground point.
- Screen right is always +X.
- Screen up is `(0, cos p, −sin p)`. At 90° this is −Z, continuous with lower
  pitches, so top-down has no ambiguous roll.

**Direction angles are measured on screen.** For direction `i` of `N`:

```
θᵢ = (start + i · 360 / N) mod 360
```

The subject is rotated by `θᵢ + model-yaw` about the vertical axis through the
ground point. The rotation is counter-clockwise when seen from above (+Y),
which gives these facings:

| Angle | Subject faces | Label |
|---|---|---|
| 0° | the viewer (down the screen) | `south` |
| 45° | down and right | `south-east` |
| 90° | screen right | `east` |
| 135° | up and right | `north-east` |
| 180° | away (up the screen) | `north` |
| 225° | up and left | `north-west` |
| 270° | screen left | `west` |
| 315° | down and left | `south-west` |

Labels are screen-relative and are recorded only for angles that are exact
multiples of 45°; any other angle has label `null`. Directions appear in the
sheet in index order.

### Presets

| Preset | Pitch | Directions | Start angle |
|---|---|---|---|
| `topdown` | 90° | 8 | 0° |
| `side` | 0° | 2 (east, west) | 90° |
| `iso` | 30° | 8 | 0° |
| `iso-true` | arctan(1/√2) ≈ 35.264° | 8 | 0° |

Explicit `--pitch`, `--directions` and `--start-angle` override the preset's
values, and the recorded preset name is then `custom`.

The tool renders no ground. Isometric games conventionally run their grid
axes along screen diagonals: a square cell at 45° to the camera projects at
pitch 30° to a diamond exactly twice as wide as tall (before rasterization).
In such a game, movement along a grid axis uses the diagonal directions (45°,
135°, 225°, 315°). That mapping is the consumer's concern; the tool's angles
are always screen-relative.

## Clips and sampling

(V-7, V-9)

glTF stores keyframes but defines no playback, so the tool defines it.

**Isolation.** When a clip is sampled, only that animation's channels apply.
Every other node takes its static transform from the file, and every morph
target weight not animated by the clip takes its default (the mesh's
`weights`, else 0).

**Range.** A clip runs from `t0` to `t1`: the minimum and maximum of its
samplers' input accessor `min`/`max` values, which glTF requires. Its duration
is `d = t1 − t0`.

**Sample times.** With `n = max(1, floor(d · fps + 0.5))`:

| Clip | Frames | Sample times | Frame duration |
|---|---|---|---|
| looping (default) | `n` | `t0 + k·d/n`, for k = 0 … n−1 | `d/n` |
| one-shot (`--once`) | `n + 1` | `t0 + k·d/n`, for k = 0 … n | `d/n` |
| `d = 0`, or the `static` clip | 1 | `t0` (0 for `static`) | `1/fps` |

A loop leaves out its endpoint, which would duplicate its first frame. A
one-shot keeps its final pose. Samples are spaced evenly over the exact
duration, so the effective rate `n/d` can differ slightly from `--fps`; the
JSON records each clip's actual frame duration. How long to hold a one-shot's
last frame is the consumer's choice.

Each sample is evaluated at its exact time, not rounded to a timeline frame.

### Root motion

A **root** is a node that is targeted by a translation channel of the clip and
has no ancestor targeted by any channel of the clip. A root's **travel** is the
horizontal (XZ) distance between its world-space positions at `t0` and `t1`,
evaluated at direction 0.

- With `--root-motion error` (the default), any root whose travel exceeds
  0.02 m is an input error. The message names the clip, the node and the
  distance, and suggests exporting the clip in place.
- With `--root-motion keep`, the clip is rendered as-is and the subject may move
  within the cell. Overflow rules still apply.

Vertical motion (jumps, bounce) is never checked and always preserved.

## Scale and ground point

(V-7)

The ground point always lands exactly on the cell pixel-grid corner
`(gx, gy)`, counted from the cell's top-left corner, in every frame. Nothing
is snapped per frame.

**Bounds.** Over every sample of every selected clip in every direction, the
backend measures the subject's evaluated (skinned and morphed) vertices
relative to the projected ground point, in meters on the screen plane:

- `L`: the farthest extent left of the ground point
- `R`: the farthest extent right
- `U`: the farthest extent above
- `D`: the farthest extent below

Each is 0 or more. The margin is `m = 1` pixel.

**Resolution.** Scale and cell are resolved in this order:

1. **Both `--ppm` and `--cell` given (fixed).**
   - `gx = floor(W/2)`
   - `gy = H − m − ceil(D·ppm)`
2. **Only `--ppm` given.**
   - `W = 2·(ceil(max(L, R)·ppm) + m)`
   - `H = ceil(U·ppm) + ceil(D·ppm) + 2m`
   - `gx = W/2`
   - `gy = H − m − ceil(D·ppm)`
3. **Only `--cell`, or neither (then the cell is 64×64): auto-fit.**
   - `gx = floor(W/2)`
   - `ppm` is the largest value that satisfies all of:
     - `L·ppm ≤ gx − m`
     - `R·ppm ≤ W − gx − m`
     - `(U + D)·ppm ≤ H − 2m − 1`
     Constraints whose extent is 0 are skipped. The extra pixel in the vertical
     budget absorbs rounding the ground row to a whole pixel.
   - `gy = H − m − ceil(D·ppm)`

`--ground-px` overrides `(gx, gy)` in every case. If every extent is 0, auto-fit
is a usage error asking for `--ppm`.

If auto-fit cannot produce a scale greater than 0 because the cell is too
small, that is a usage error.

A cell resolved in case 2 that is wider or taller than 4096 pixels, the
`--cell` limit, is a usage error giving the computed size and suggesting a
smaller `--ppm` (owner decision 2026-10-01).

**Overflow.** Cases 2 and 3 fit by construction, unless `--ground-px` is
given. Every other configuration is checked, including case 1 and any reused
settings. A sample whose projected vertices fall outside the cell rectangle is
an overflow (exit 4). The message lists each offending clip, direction and
sample time, with the overshoot on each side in whole pixels, rounded up
(owner decision 2026-10-01). The margin is not
required when checking.

**Reuse.** `--settings-from FILE` reads the `settings` object of an earlier
sheet's JSON and reuses these values:

- view and model yaw
- fps and supersample
- ppm, cell, ground point and ground pixel
- root-motion mode
- the style's reduction and inline palette, `settings.style.reduce` and
  `settings.style.palette`

This makes scale, cell and ground pixel fixed. Options given explicitly
override the reused values; an explicit `--reduce` replaces the reused
reduction, retaining the palette. `--palette FILE` replaces the reused palette;
`--no-palette` drops it. Reuse applies the recorded ordered colours without
opening the original palette file and keeps its record unchanged. Clip selection and `--once` always come from the current command
line. A file that is unreadable, or not a `moskophoros.sheet/2` or
`moskophoros.sheet/1` document, is a usage error.

A `moskophoros.sheet/1` sheet, written before the style was recorded, has no
`settings.style` and reads as `{"reduce": "plain", "palette": null}`. Its
other fields are checked as below, and a `style` field in it is an unknown
field (owner decision 2026-10-04).

An explicit `--view` replaces the whole reused view: that preset's values
apply, then any explicit `--pitch`, `--directions` or `--start-angle` on top,
exactly as without reuse. Without `--view`, the reused view stays, and an
explicit `--pitch`, `--directions` or `--start-angle` overrides its value and
makes the preset `custom`.

The reused `settings` are checked strictly. Every reused field must be
present with a value its option would accept, `projection` must be
`orthographic`, and `pixels_per_meter`, `cell` and `ground_px` must be set.
In a `/2` sheet, `style` must be an object with exactly `reduce`, a value
`--reduce` accepts, and `palette`, either `null` or an object with exactly
`source`, `sha256` and `colors`. The source is a nonempty base filename, never
a path; the digest is exactly 64 lowercase hexadecimal digits; colours are
1 to 255 unique canonical lowercase `#rrggbb` strings in their recorded order.
The palette module applies its shared count, RGB and uniqueness checks. All
reused fields are validated before any override, including `--reduce`,
`--palette` and `--no-palette` (owner decisions 2026-10-04).
A missing or invalid field, or an unknown field inside `settings`, is a usage
error naming it. The rest of the sheet is not checked beyond its `schema`
(owner decisions 2026-10-01).

## Pipeline

(V-4, V-5)

Four stages, each depending only on the previous stage's output. Frames pass
between stages keyed by frame address. Capture writes files because it runs in
Blender's process; in slice 1 the later stages pass arrays in memory. Per-stage
caching is deferred.

#### Frames into stylize

A frame going into stylize carries its colour pixels and, beside them, any
further named buffers of the same height and width (`ImageFrame.buffers`).
The command loads every buffer the capture result names for a frame: `color`
becomes the frame's pixels, and each other buffer is carried under its own
name as an 8-bit RGBA array. Capture writes only `color` today, so frames
carry no other buffer yet. Existing reductions read only the colour.

Two buffer names are reserved for material identity and shade, with this
interface:

- Per asset, an **identity list** (`sampling.Identities`): each distinct name
  of an eligible (`OPAQUE` or `MASK`) material, in a fixed order (by its
  lowest glTF material index), then the no-identity class. Index `i` names
  the `i`th material name; the last index, `Identities.no_identity`, which
  equals the number of names, is the no-identity class. Stylize receives the
  list through its `identities` argument.
- Per frame, under `identity` (`sampling.IDENTITY`), an **identity array**:
  `int32`, shape `(height, width)`, each value an index into the identity
  list or `sampling.BACKGROUND` (−1), which is never an index. Under `shade`
  (`sampling.SHADE`), a **shade array**: `uint8`, shape `(height, width)`.
- The command decodes and validates both arrays; stylize never does.

Frames are loaded one at a time, as stylize reduces them. Stylize returns an
ordinary reduced colour frame with no buffers, and releases a frame's
supersampled colour and every other buffer once it is reduced, before the
next frame is loaded, so at most one frame's supersampled buffers are held.
Cleanup and export receive only the reduced colour frames.

### Capture

The CLI calls Blender twice, each time as a separate process:

```
<blender> -b --factory-startup -noaudio --python-exit-code 1 \
    --python <package>/capture/blender_script.py -- <job.json>
```

1. **Measure.** Imports the `.glb` and reports every root's travel and every
   sample's bounds (L, R, U, D). It renders nothing. The CLI then checks root
   motion and resolves scale, cell and ground pixel.
2. **Render.** Renders every frame at supersampled size `(W·s) × (H·s)`, with
   the ground point projected to `(gx·s, gy·s)`.

The job JSON carries all settings, sample times and the output directory.
Blender writes a manifest JSON listing each frame's address and file.
`blender_script.py` uses only `bpy` and the Python standard library, and is the
only module that imports `bpy`. It is never imported by the rest of the
package.

**What is rendered:** only the mesh objects created from the glTF scene.
Everything else, including objects the importer adds itself (such as bone
display shapes), is explicitly excluded from rendering, whether or not it
happens to be hidden.

**Clip isolation:** before sampling a clip, the backend disables every
animation layer (NLA), makes that clip the only active action on each object
it animates, and resets every pose to rest. Nothing from a previously sampled
clip may carry into the next one. This implements the rule in
[Clips and sampling](#clips-and-sampling).

**Render settings:**
- Workbench engine, with studio lighting fixed in view space (Workbench's
  default, which keeps lighting fixed to the camera). The studio light's name
  is recorded in the JSON.
- Color: texture color, falling back to material color.
- No shadows, cavity, outline or depth of field.
- Film transparent. View transform `Standard`, look `None`, exposure 0, gamma 1.

**Capture output:** one 8-bit sRGB RGBA PNG per frame, straight alpha, holding
Workbench's antialiased coverage. Every `use_stamp_*` render setting is off,
so Blender writes no date or render-time metadata and identical frames are
identical files. Slice 1 captures only this color buffer. The
manifest format lists buffers by name, so depth, normal and base-color buffers
can be added without changing it.

**Finding Blender:** `--blender`, then `$MOSKOPHOROS_BLENDER`, then `blender`
on `PATH`, then `/Applications/Blender.app/Contents/MacOS/Blender` on macOS.
The version comes from `blender --version`. A mismatch in major.minor version
is a backend error unless `--any-blender` is given; the actual version is
always recorded.

The first source that is set decides: if `--blender` or
`$MOSKOPHOROS_BLENDER` names a missing or non-executable file, that is a
backend error naming the source and path, and later sources are not tried.
Version output with no parseable version is a backend error quoting its first
line, even with `--any-blender`, which allows a different version but never
an unknown one (owner decisions 2026-10-01).

### Capture job and result contract

Owner decision 2026-09-30: the capture transport, ownership, validation and
compatibility rules below are accepted. These define the implementation
contract; they do not claim that the backend is implemented.

#### job format

Both modes consume a UTF-8 JSON document. Unknown schema versions, duplicate
keys, missing required fields and invalid numeric values are rejected.

| Field | Meaning |
|---|---|
| `schema` | Exactly `moskophoros.capture-job/1`. |
| `mode` | `measure` or `render`. |
| `source` | Absolute `path` to the original GLB, its `sha256` and the selected original glTF `scene` index. |
| `subject`, `variant` | Input stem and `default`, matching every requested frame address. |
| `settings` | The accepted sheet settings, using resolved option values. In measure mode, `pixels_per_meter`, `cell` and `ground_px` are null: fitting belongs to the caller. In render mode all three are resolved, fixed values. The sheet's `style` is left out: style is applied after capture, so the job is the same whatever the style (owner decision 2026-10-04). |
| `clips` | Selected clips in sheet order. Each carries its original `animation_index`, `name`, `t0_s`, `t1_s` and candidate `roots`. The synthetic `static` clip has a null animation index, zero endpoints and no animated roots. |
| `clips[].roots` | Each candidate root's original `node_index` and optional original `node_name`, determined using the accepted ancestry rule. Indices identify nodes; names are diagnostics, never assumed unique. |
| `frames` | The exact requested samples in sheet order: clip, direction, then sample. Each carries an `address`, sample `index` and direction `angle_deg`. The address has `subject`, `variant`, `clip`, `direction` and `time_s`. |
| `output_dir` | Absolute path to this mode's own initially empty output directory. |

The caller owns selection, sample times, direction enumeration and fitting.
Blender evaluates the supplied times and angles; it does not select clips,
resample them, auto-fit a cell or recompute the ground point. The job builder
checks that its frames agree with the selected clips and resolved settings.
All numbers must be finite; indices, dimensions, sample ranges and settings
must satisfy the accepted product constraints.

The backend maps original animation and node indices to imported state
privately. It must handle unnamed or duplicate-named nodes without conflating
them, and report an unmappable identity rather than guessing. Integration
fixtures must prove that mapping. The mapping technique is an implementation
choice inside the backend, not a new dependency on importer state elsewhere.

#### result format

Blender writes `result.json` only after the requested mode completes. The
launcher requires both a successful subprocess exit and a valid result; it
never interprets human-readable stdout as a manifest.

| Field | Meaning |
|---|---|
| `schema` | Exactly `moskophoros.capture-result/1`. |
| `mode` | Must match the submitted job. |
| `job_sha256` | Hash of the submitted job encoded as canonical JSON with sorted keys, compact separators, ASCII escapes and non-finite numbers forbidden. This binds a result to its complete request, not just its source. |
| `source_sha256` | Must match the job's source digest. |
| `backend` | Actual Blender version; render results also record the actual renderer and studio light used. The version is parsed according to the owning supported-version contract. |
| `frames` | Exactly one record per requested address, in request order. No missing, duplicate or unexpected address is accepted. |
| `frames[].bounds_m` | Measure only: finite, nonnegative `L`, `R`, `U`, `D` as defined by the product design. |
| `frames[].height_m` | Measure only: evaluated subject height along the glTF vertical axis, for the accepted unit warning. |
| `roots` | Measure only: one entry per requested clip/root pair, with `clip`, `node_index`, `node_name` and nonnegative finite `travel_m`. Include zero travel. Evaluate the clip endpoints, even when the loop's render samples omit its endpoint. |
| `frames[].buffers` | Render only: map from buffer name to relative file path. `color` is mandatory; extra named buffers can be described without changing the frame structure, although slice 1 produces only color. |

Every result frame includes its full `address`. Sample indices and angles
remain caller-owned lookup data; they do not replace the address as identity.
Measure mode writes no color buffers. Render mode writes no new fitting or
root-motion verdict: the caller has already accepted the measurement.

The color path is `color/000000.png`, with a six-digit ordinal in
request order; the ordinal can grow beyond six digits. Clip and subject names
never become capture filenames. Each file is the accepted high-resolution
color buffer. The launcher validates that referenced files exist, remain
within the phase directory, have the required dimensions and decode in the
required color mode before passing them to later stages. Paths may not be
absolute, contain parent traversal or escape through a symlink.

The caller combines actual render provenance with its generator, source and
resolved settings to compute the accepted sheet fingerprint. It attaches that
fingerprint to the loaded addressed frames before stylize and cleanup. The
transport job hash is a separate request-integrity check, not a replacement
for the sheet fingerprint and not part of its inputs.

#### ownership and failure handling

The launcher owns request files, phase directories and the Blender processes
it starts. Only the script writes phase results and buffers. Measurement and
rendering get separate initially empty directories; each contains its
launcher-written `job.json` when the script starts, with no earlier results or
buffers. Their result files cannot overwrite each other. Request and result
JSON contain no timestamps or unrecorded seeds. Result manifests use relative buffer paths so retaining the
workspace does not require rewriting frame records.

The launcher checks source bytes against the recorded digest before and after
each invocation. A changed source is an input failure naming the file, and no
final output is published. This catches ordinary edits between phases; it is
not a concurrent-file snapshot guarantee. Neither phase edits the owner's model.

Unsuccessful launch, Blender failure, missing result, a result/request mismatch,
unmappable backend identity or invalid referenced buffer is a backend failure
using the accepted error code and captured diagnostics. A malformed job caught
in the caller is an internal programming error, not bad user input. Root travel
above the threshold remains the caller's input error; fixed-setting overflow
remains its overflow error. Blender does not silently retry or fall back to
different sampling, scale or rendering settings.

On interruption the launcher stops only its own Blender process and does not
publish final outputs. Backend waits are for actual process completion, failure
or caller interruption. There is no fixed-duration render deadline or timeout
option. Tests coordinate fake subprocesses explicitly and never
sleep to guess completion.

The [CLI work-directory contract](#cli) governs retained capture ownership.
Normal temporary capture directories are deleted after success or failure. Explicitly retained
capture directories preserve available job/result/buffer evidence on failure,
without treating incomplete phases as valid results.

#### compatibility and verification

Capture jobs and results are versioned internal debugging artifacts. Retaining
them does not create a replay command, cache-reuse feature or promise that a
future release will consume old captures. The public sheet schema and
`--settings-from` contract remain the accepted compatibility boundary.
Adding auxiliary buffer names later must not require changing the address
structure or rewriting the pipeline around Blender objects.

Contract tests cover both formats and failure cases with controlled processes
and supplied files. Blender integration tests prove actual identity mapping,
sample ordering, bounds/root reporting, buffer contents and repeatability using
generated models. Whole-command tests prove that source changes, failed capture
and invalid capture results leave existing final outputs untouched.

### Supported Blender version

**Blender 5.2 LTS**, tested with **5.2.2** (pinned 2026-09-29). 5.2.2 was the
latest stable release, and 5.2 is a long-term-support series with two years
of fixes. Any 5.2.x release is accepted. On macOS it is installed with
`brew install --cask blender`; Homebrew follows the latest stable release, so
check the installed version after upgrading.

Observed on this release: `blender --version` prints `Blender 5.2.2 LTS` on
its first line, so the version parser must allow a suffix after the number.
Blender bundles its own Python (3.13.13 in 5.2.2), which is the interpreter
`blender_script.py` runs under. It must stay compatible with that Python,
independent of the tool's own Python.

Observed in the capture experiment (2026-09-29), which confirmed this
section's settings on 5.2.2:

- **The importer adds objects that are not in the file:** a bone display shape
  (`Icosphere`) in a hidden `glTF_not_exported` collection. See "What is
  rendered" above.
- **Each glTF animation becomes an action with the clip's name**, plus a muted
  NLA track per clip, and the importer leaves the last clip as the rig's active
  action. See "Clip isolation" above.
- **glTF time *t* maps to frame *t* × fps**, and sub-frame evaluation
  (`frame_set` with a `subframe`) samples exact times. Clips exported from
  Blender start at *t* = 1/fps, because Blender's frame 1 is exported at that
  time; clip ranges come from the file, so this needs no handling.
- **Rotation between keyframes differs slightly from glTF's.** Blender
  interpolates quaternion channels separately rather than by glTF's spherical
  interpolation: a 30° linear keyframe span read 5.967° where glTF gives 6°.
  Keyframe values are exact. The error is far below a pixel at sprite scale and
  is accepted.
- **Render settings behave as specified.** The studio light is `Default` with
  world-space lighting off, `TEXTURE` color falls back to the material color,
  and the `Standard` view transform reproduces a material's sRGB color exactly
  under flat light. Renders are pixel-identical across separate Blender
  processes; files are byte-identical only with stamping off.
- **Cost:** about 1 s to start Blender, about 1 s for the first render while
  shaders compile, then 10–120 ms per frame at 384×384.

This section is the single record of the supported version. The backend's
version check in `capture/blender.py` must match it. Moving to a new series is
an owner decision recorded here, after the Blender integration tests pass on
it.

### Stylize

Each supersampled frame is reduced by `s×s` blocks, by the reduction
`--reduce` names. Both reductions decide coverage the same way, for each
output pixel:

- **coverage** is the mean alpha of its block, from 0 to 1
- if coverage is below 0.5, the pixel is `(0, 0, 0, 0)`; exactly 0.5 is kept

**Plain** (`--reduce plain`, the default): a kept pixel's color is the
alpha-weighted mean of the block's RGB, rounded half up, with alpha 255.

**Most common colour** (`--reduce mode`, owner decisions 2026-10-04): a kept
pixel takes the colour with the most votes, with alpha 255.

- Each pixel of the block votes for its exact RGB with a weight equal to its
  alpha, so a pixel with alpha 0 casts no vote.
- A tie goes to the tied colour nearest the block's alpha-weighted mean RGB,
  by squared Euclidean distance in 8-bit sRGB values, compared exactly
  against the unrounded mean.
- A tie at equal distance goes to the smallest packed `0xRRGGBB` value.

Both reductions use exact integer arithmetic and are fully determined. The
transparent pixels are the same under either. Under
Workbench's smooth shading a block may hold nearly as many colours as pixels,
so the vote can fall to the tie-break; that is accepted, and the owner judges
the look (vision V-12). Future style passes replace or extend these (vision,
Long-term direction).

#### Palette inputs

`--palette FILE` selects an ordered palette. The standalone
`palette.read_palette(path)` library function returns an immutable ordered
sequence of 8-bit RGB triples and only reads the named file (owner decisions
2026-10-04, D-4, D-5 and D-10 in
[the style design](designs/style_pass_1_design.md#decisions)).

The suffix chooses the format, ignoring case:

- `.hex`: UTF-8, one six-digit `RRGGBB` per line, in either case, with an
  optional leading `#`. Blank lines and surrounding whitespace are ignored.
- `.gpl`: UTF-8, beginning with `GIMP Palette`; optional `Name:` and
  `Columns:` metadata precede colour entries. Blank lines and `#` comments
  are ignored. Entries are three whitespace-separated integers in 0 to 255,
  optionally followed by a colour name. Both text formats preserve file order.
- `.png`: distinct colours in first-appearance order, scanning rows top to
  bottom and each row left to right. Repeated pixels contribute one colour;
  indexed images contribute used pixel colours, excluding unused table entries;
  greyscale expands to RGB. Every pixel must be fully opaque, including
  transparency from a palette table or a transparent-colour key. Source
  samples must be exactly representable at 8 bits per channel: 16-bit colour
  samples are accepted only when they are multiples of 257, never rounded.

A palette has 1 to 255 colours, leaving room for the previews' `#808080`
background. Duplicate text entries are refused, naming both lines.
`palette.validate_colors(colors, source=...)` applies the RGB, count and
uniqueness checks to a plain sequence without reading anything; `source`
identifies the caller's diagnostic source, such as a settings JSON file, and
sequence errors refer to entries rather than invented text lines.

All failures raise `PaletteError`, naming the file or caller-supplied source
and the line for text errors: unreadable files, unsupported suffixes, invalid
UTF-8, missing GPL headers, malformed lines, out-of-range channels,
duplicates, empty or oversized palettes, undecodable PNGs, non-opaque pixels
and source colours requiring lossy conversion. The module neither prints nor
exits; the command reports these as usage errors (exit 2) before any Blender
invocation. `palette.read_palette_bytes(data, source=...)` parses a byte snapshot
without reading a file, so the command hashes exactly the bytes it parsed.
Quantized colour extraction remains deferred.

#### Palette mapping and composition

`imageops.map_palette(pixels, colors)` maps each nontransparent pixel to the
nearest palette entry by Euclidean distance in OKLab, with no dithering. Equal
distances choose the earlier entry. It uses a fixed 256-entry sRGB-to-linear
table and the [OKLab matrices](https://bottosson.github.io/posts/oklab/), with
NumPy float64 elementwise arithmetic in a fixed operation order. Alpha is
unchanged; alpha-zero pixels become `(0, 0, 0, 0)`; the input is untouched.
Distance work uses fixed-size pixel batches and visits palette entries in
order, never allocating a pixel-count × palette-size array.

The four fixed looks are (owner decisions 2026-10-04, D-6 and D-7):

| Reduction | Without palette | With palette |
|---|---|---|
| `plain` | Reduce by alpha-weighted mean. | Reduce, then map output pixels. |
| `mode` | Vote for exact captured colours. | Map supersampled pixels, then vote; shades mapped to the same colour pool their votes. |

Coverage and mode tie rules stay as above. Every look has the same transparent
pixels and binary output alpha; each opaque paletted output colour belongs to
the palette. Stages keep addresses, frame order and metadata. The command
processes one supersampled frame at a time. Palette data never enters capture
settings or jobs. Without a palette, both reductions produce the same bytes
as before palette mapping was added.

### Cleanup (slice 1: none)

A stage that receives addressed frames and returns them. Slice 1 passes them
through unchanged.

### Export

**Sheet.**
- One row per clip × direction: clips in selection order, and within each clip,
  directions in index order.
- One column per frame; the column count is the largest frame count of any
  clip.
- Cells are packed with no gaps; unused cells are fully transparent.
- Output is an 8-bit RGBA PNG written by Pillow with no text or time chunks.

**JSON (`moskophoros.sheet/2`).**

```json
{
  "schema": "moskophoros.sheet/2",
  "generator": {
    "tool": "moskophoros", "version": "0.1.0",
    "python": "3.x.y", "numpy": "x.y.z", "pillow": "x.y.z",
    "blender": "x.y.z", "renderer": "workbench", "studio_light": "..."
  },
  "source": { "file": "hero.glb", "sha256": "..." },
  "subject": "hero",
  "variant": "default",
  "settings": {
    "view": { "preset": "iso", "projection": "orthographic",
              "pitch_deg": 30.0, "directions": 8, "start_angle_deg": 0.0 },
    "model_yaw_deg": 0.0,
    "fps": 12.0,
    "supersample": 8,
    "pixels_per_meter": 24.5,
    "cell": { "width": 48, "height": 48 },
    "ground_m": { "x": 0.0, "y": 0.0, "z": 0.0 },
    "ground_px": { "x": 24, "y": 46 },
    "root_motion": "error",
    "style": { "reduce": "plain", "palette": null },
    "clips": [ { "name": "walk", "loop": true },
               { "name": "attack", "loop": false } ]
  },
  "fingerprint": "sha256:...",
  "image": { "file": "hero.png", "width": 576, "height": 768 },
  "directions": [ { "index": 0, "angle_deg": 0.0, "label": "south" } ],
  "clips": [
    { "name": "walk", "loop": true, "duration_s": 1.0,
      "frame_count": 12, "frame_duration_s": 0.08333333333333333 }
  ],
  "frames": [
    { "clip": "walk", "direction": 0, "index": 0, "time_s": 0.0,
      "x": 0, "y": 0, "w": 48, "h": 48 }
  ]
}
```

- `frames` lists every frame, in sheet order. A frame's address is `subject`,
  `variant`, `clip`, `direction` and `time_s` (V-9).
- `settings.style` records the look: `reduce`, the `--reduce` value, and
  `palette`, either `null` or an ordered object with `source` (the palette
  file's base filename), `sha256` (SHA-256 of its bytes), and `colors` (ordered
  canonical lowercase `#rrggbb` strings). It sits between `root_motion` and
  `clips`. Export writes and fingerprints the record the command resolved
  without interpreting it, so a new look changes neither export nor capture.
  `moskophoros.sheet/1` is the same document without `settings.style`;
  [reuse](#scale-and-ground-point) still reads it (owner decisions
  2026-10-04).
- `fingerprint` is the SHA-256 of the canonical JSON (sorted keys, no
  whitespace, UTF-8) of `generator`, `source.sha256` and `settings`. The
  hashed object mirrors the sheet's own structure:
  `{"generator": …, "settings": …, "source": {"sha256": …}}` (owner decision
  2026-10-01).
- Floats are written with Python's shortest round-trip representation.
- The file keeps the key order shown above, with 2-space indentation, UTF-8
  with non-ASCII characters kept as is, and a trailing newline (owner decision
  2026-10-01).
- `source.file` and `image.file` are base names, never paths, so the JSON is
  the same wherever the command runs (owner decision 2026-10-01).

For example, the palette record for `two.hex` containing `000000` and
`ffffff`, each followed by a newline, is:

```json
{"source": "two.hex", "sha256": "89b96770b769aab4951a86bb5b9ddea7b757fd45f822c7a4d4196759ec2f32b6", "colors": ["#000000", "#ffffff"]}
```

The palette's file bytes, colours and their order all participate in the
fingerprint; reuse needs only this inline record.

**Previews.** For each clip, an animated GIF showing all directions side by
side in index order, packed with no gap between cells (owner decision
2026-10-01):

- scaled 4× with nearest-neighbor
- in exact colors when a frame has at most 256 of them; otherwise reduced to
  256 without dithering, with a warning naming the clip (owner decision
  2026-10-01)
- on a solid `#808080` background
- each frame lasting the clip's frame duration, rounded to the nearest 10 ms
  and at least 20 ms
- looping forever; one-shot clips hold their last frame for an extra 500 ms
  before repeating

GIF stores a width in 16 bits and a delay in 16 bits of centiseconds. A
preview wider than 65,535 pixels, or any frame delay over 655,350 ms
(including a one-shot's extra 500 ms), is a usage error (exit 2) naming the
clip, the computed width or delay, and the limit. The preview is never
scaled, clamped or split to fit (owner decisions 2026-10-02).

A paletted frame uses at most 255 colours plus the grey background, so its
preview keeps exact colours without a quantization warning. Preview handling
is otherwise unchanged.

Previews exist for review in motion (V-12) and are not part of the sheet
contract.

## Reproducibility

(V-2)

Given the same input bytes, settings and generator (tool, Python, numpy,
Pillow and Blender versions, renderer), the sheet PNG and JSON are
byte-identical. To make that true:

- sample times are exact
- no timestamps are written anywhere
- sorting is fixed wherever order is not already defined
- output encoding is fixed
- palette mapping uses its fixed sRGB table and NumPy arithmetic; the recorded
  NumPy version participates in the generator and fingerprint

Output from a different Blender version or GPU may differ; the recorded
generator and fingerprint make such a difference visible.

## Project layout

(V-10, V-12)

```
pyproject.toml            console script: moskophoros = moskophoros.cli:main
requirements.lock         exact tested versions
src/moskophoros/
  cli.py                  options, presets, settings resolution, exit codes
  gltf.py                 .glb reading: scenes, clips, time ranges, validation
  views.py                camera and direction math
  sampling.py             sample times
  fit.py                  scale, cell and ground-pixel resolution, overflow
  capture/
    backend.py            the capture boundary: job in, manifest out
    blender.py            finds and runs Blender, checks its version
    blender_script.py     runs inside Blender; the only bpy code
  stylize.py              plain and most-common-colour reductions
  cleanup.py              pass-through
  export.py               sheet, JSON, previews
  imageops.py             shared image operations
  palette.py              ordered exact RGB palette reading and validation
tests/
```

- Python 3.13 or newer, matching the Python Blender 5.2 bundles (owner
  decision 2026-09-29, CI foundation design D-5). Runtime dependencies are
  numpy and Pillow; pytest and ruff are development dependencies.
- `pyproject.toml` states minimum versions; `requirements.lock` pins the
  versions that were tested.

## Testing

Automated tests (pytest), none needing Blender:

- direction angles, labels and presets
- camera basis vectors, including the top-down case
- sample times for looping, one-shot, zero-length and `static` clips
- all fit cases, `--ground-px`, and overflow detection from given bounds
- `.glb` validation errors, using small files generated by the tests
- plain and most-common-colour reductions on constructed arrays
- sheet layout, JSON content and the fingerprint's stability
- settings reuse and its overrides

Integration tests run Blender and fail with a clear diagnostic when Blender is
unavailable. Use `pytest -m "not blender"` to run only tests that do not require
Blender (owner decision 2026-09-30). They use a small generated rigged `.glb`
with a looping clip and a one-shot clip, and check:

- measured bounds against the known geometry
- that root motion is detected
- that two runs produce byte-identical output

## Slice 1 acceptance

1. The automated tests pass.
2. One of the owner's real animated characters, with a looping clip and a
   one-shot clip, renders in 8 directions at the owner's intended production
   size.
3. The owner reviews the sheet and the previews and approves them (V-12).

## Deferred

Decided later, each when its trigger arrives:

| Item | Trigger |
|---|---|
| Auxiliary capture buffers (depth, normal, base color, material ID) | The first style pass that needs them: per-material colour ramps, which need material IDs (owner decision 2026-10-04). |
| Per-material colour ramps | The owner starts a later style arc. |
| Saved style files, and a free chain of passes beyond the four looks | The owner requests them. |
| Quantized palette extraction from many-colour art, as a standalone command | The owner requests it. |
| Per-stage caching | Iteration speed becomes a problem. |
| Root-motion extraction (keeping travel as data rather than rendering it) | A consumer needs it. |
| Variants (bone-attached props, palette swaps) | The owner requests them. |
| Other sheet formats and per-frame output | A consumer needs them. |
| Perspective projection | A view needs it. |
| Vertex-color rendering | A model needs it. |
| `CUBICSPLINE` animation and mesh morph-weight animation pointers, rejected for now (owner decision 2026-10-02) | A model needs them. |

Style passes and their configuration started with style pass 1: `--reduce` and
`--palette` (see [Stylize](#stylize)), accepted by the owner on 2026-10-05. The
rows above hold what it left for later; palette swaps stay a variant (owner
decisions 2026-10-04).
