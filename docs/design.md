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
| `--settings-from FILE` | none | Reuse settings from an earlier sheet's JSON. See [Scale and ground point](#scale-and-ground-point). |
| `--no-preview` | off | Skip the animated previews. |
| `--work-dir DIR` | temporary | Keep capture output in `DIR` instead of a deleted temporary directory. |
| `--blender PATH` | discovered | Blender executable. See [Capture](#capture). |
| `--any-blender` | off | Allow a Blender version other than the supported one. |

`<outfile.png>` must end in `.png`. The JSON is written beside it, at the same
path with `.json` replacing `.png`. Previews are written as
`<stem>.<clip>.gif` beside it; a clip name is made filename-safe by replacing
every character outside `A–Z a–z 0–9 . _ -` with `_`. If two clip names become
the same after that, the second and later previews gain the suffix `-2`, `-3`,
and so on, in sheet order.

Existing outputs are overwritten. All outputs are written to temporary files
and renamed into place only after the whole run succeeds, so a failed run
leaves earlier outputs untouched. Errors go to stderr as
`moskophoros: error: <message>`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. |
| 1 | Internal error (a bug); a traceback is printed. |
| 2 | Usage error: bad option, value or combination. |
| 3 | Input error: see [Input contract](#input-contract) and [Root motion](#root-motion). |
| 4 | Overflow: the subject does not fit a fixed cell and scale. |
| 5 | Backend error: Blender missing, wrong version, or failed. |

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
- an animation has no name, or two animations share a name (the message gives
  the animation's index)
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

**Overflow.** Cases 2 and 3 fit by construction, unless `--ground-px` is
given. Every other configuration is checked, including case 1 and any reused
settings. A sample whose projected vertices fall outside the cell rectangle is
an overflow (exit 4). The message lists each offending clip, direction and
sample time, with the overshoot in pixels on each side. The margin is not
required when checking.

**Reuse.** `--settings-from FILE` reads the `settings` object of an earlier
sheet's JSON and reuses these values:

- view and model yaw
- fps and supersample
- ppm, cell, ground point and ground pixel
- root-motion mode

This makes scale, cell and ground pixel fixed. Options given explicitly
override the reused values. Clip selection and `--once` always come from the
current command line. A file that is unreadable, or not a `moskophoros.sheet/1`
document, is a usage error.

## Pipeline

(V-4, V-5)

Four stages, each depending only on the previous stage's output. Frames pass
between stages keyed by frame address. Capture writes files because it runs in
Blender's process; in slice 1 the later stages pass arrays in memory. Per-stage
caching is deferred.

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

**Render settings:**
- Workbench engine, with studio lighting fixed in view space (Workbench's
  default, which keeps lighting fixed to the camera). The studio light's name
  is recorded in the JSON.
- Color: texture color, falling back to material color.
- No shadows, cavity, outline or depth of field.
- Film transparent. View transform `Standard`, look `None`, exposure 0, gamma 1.

**Capture output:** one 8-bit sRGB RGBA PNG per frame, straight alpha, holding
Workbench's antialiased coverage. Slice 1 captures only this color buffer. The
manifest format lists buffers by name, so depth, normal and base-color buffers
can be added without changing it.

**Finding Blender:** `--blender`, then `$MOSKOPHOROS_BLENDER`, then `blender`
on `PATH`, then `/Applications/Blender.app/Contents/MacOS/Blender` on macOS.
The version comes from `blender --version`. A mismatch in major.minor version
is a backend error unless `--any-blender` is given; the actual version is
always recorded.

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

This section is the single record of the supported version. The backend's
version check in `capture/blender.py` must match it. Moving to a new series is
an owner decision recorded here, after the Blender integration tests pass on
it.

### Stylize (slice 1: plain)

Each supersampled frame is reduced by `s×s` blocks. For each output pixel:

- **coverage** is the mean alpha of its block, from 0 to 1
- if coverage is below 0.5, the pixel is `(0, 0, 0, 0)`
- otherwise, its color is the alpha-weighted mean of the block's RGB, rounded
  half up, with alpha 255

This is the only look-related step in slice 1. Future style passes replace or
extend it (vision, Long-term direction).

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

**JSON (`moskophoros.sheet/1`).**

```json
{
  "schema": "moskophoros.sheet/1",
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
- `fingerprint` is the SHA-256 of the canonical JSON (sorted keys, no
  whitespace, UTF-8) of `generator`, `source.sha256` and `settings`.
- Floats are written with Python's shortest round-trip representation.

**Previews.** For each clip, an animated GIF showing all directions side by
side in index order:

- scaled 4× with nearest-neighbor
- on a solid `#808080` background
- each frame lasting the clip's frame duration, rounded to the nearest 10 ms
  and at least 20 ms
- looping forever; one-shot clips hold their last frame for an extra 500 ms
  before repeating

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
  stylize.py              plain reduction
  cleanup.py              pass-through
  export.py               sheet, JSON, previews
  imageops.py             shared image operations
tests/
```

- Python 3.12 or newer. Runtime dependencies are numpy and Pillow; pytest is a
  development dependency.
- `pyproject.toml` states minimum versions; `requirements.lock` pins the
  versions that were tested.

## Testing

Automated tests (pytest), none needing Blender:

- direction angles, labels and presets
- camera basis vectors, including the top-down case
- sample times for looping, one-shot, zero-length and `static` clips
- all fit cases, `--ground-px`, and overflow detection from given bounds
- `.glb` validation errors, using small files generated by the tests
- plain reduction on constructed arrays
- sheet layout, JSON content and the fingerprint's stability
- settings reuse and its overrides

Integration tests run Blender and are skipped with a stated reason when Blender
is not found. They use a small generated rigged `.glb` with a looping clip and
a one-shot clip, and check:

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
| Auxiliary capture buffers (depth, normal, base color, material ID) | The first style pass that needs them. |
| Style passes and their configuration | The owner starts style work. |
| Per-stage caching | Iteration speed becomes a problem. |
| Root-motion extraction (keeping travel as data rather than rendering it) | A consumer needs it. |
| Variants (bone-attached props, palette swaps) | The owner requests them. |
| Other sheet formats and per-frame output | A consumer needs them. |
| Perspective projection | A view needs it. |
| Vertex-color rendering | A model needs it. |
