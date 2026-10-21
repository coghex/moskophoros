# Settings design: YAML defaults, user settings and command-line knobs

Today every moskophoros setting is either a command-line option or a constant
in the code. The owner wants "knobs": values they can change on the fly
between generations without editing code. Those values live in YAML: shipped
defaults, overridden by the owner's own settings, overridden by a
per-generation file, overridden by the command line. The first knobs are the
shading constants behind the R1 and R2 renders. The design also has to make
room for many more settings, for per-material settings, and later for a UI
that edits the same settings (owner, 2026-10-11).

Design state: `ready for issue processing`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

The owner signed off this slice list on 2026-10-11 (D-21). After three
reviews the owner declared the design ready the same day: "i think its
probably ready, go ahead and mark it so if you agree". The agent agreed:

- no question is open;
- every slice is one pull request, in dependency order;
- no tracker epic duplicates this one (the open epics are #3, #24 and #63);
- SET-0 is already filed as #82.

- [x] EPIC. Configure moskophoros from layered YAML settings and command-line overrides — [#83]
- [#82] SET-0. Read material libraries from YAML instead of JSON
- [x] SET-1. Load layered YAML settings for the existing options — [#84]
- [x] SET-2. Make the global shading values settings and command-line options — [#85]
- [x] SET-3. Let each material override the shading values — [#86]
- [x] SET-5. Set a clip's frame count, retiming it to the fps — [#87]
- [deferred] SET-4. Recolour shading without a re-render. Waits until iteration speed becomes a problem and the owner asks for it (D-18).

## Epic contract

- **Goal:** every setting the owner tunes per generation has one name, one
  shipped default and one validation rule. It can be set in the user file, in
  `--config` files and, for global values, on the command line, in the order
  D-8 fixes. Every sheet records every setting that affects its output, and
  loading the sheet regenerates that output exactly.
- **Done when:**
  - every D-14 setting works at every layer;
  - the R1 and R2 looks can be reproduced from a `--config` file alone, with
    no code edit;
  - per-material shading overrides and clip frame counts work;
  - reusing a sheet with the same model gives byte-identical output, checked
    by a test (D-16);
  - with no settings files and no new options, sheet PNGs and previews are
    byte-identical to today's (D-12);
  - the owner accepts the result (V-12).
- **Users and operators:** the owner, generating sprites from the command line.
  Later, a UI that edits the same settings model (D-5).
- **Arc label:** `None proposed`.

## Current state and evidence

Verified at `master` @ 87bec34, 2026-10-11.

- **No settings file of any kind.** Nothing reads YAML or a configuration
  file. The only environment variable is `$MOSKOPHOROS_BLENDER`
  (design §Capture, *Finding Blender*). PyYAML is not a project dependency;
  6.0.3 is installed in the system Python 3.14.
- **Settings are options or constants.** Design §CLI lists 24 options. The
  inventory below lists them, and the constants a user could plausibly tune.
- **The shading constants are hard-coded in two places.**
  - `src/moskophoros/capture/blender_script.py:976–979` holds `SHADE`:
    `ao_distance_m` 0.3, `ao_samples` 64, `occlusion_weight` 0.25 and
    `convexity_weight` 1.0. They feed the Cycles AO nodes at `:1112–1127`.
  - `src/moskophoros/capture/backend.py:45` holds
    `DEFAULT_SHADE_RANGE = (84, 191)`. `backend.py:53–56` validates the
    `shade` record that Blender reports back.
  - `src/moskophoros/cli.py:164, 257, 428–430` uses the range for new runs and
    for `/2` sheets that predate it.
- **The design fixes them.**
  - Design §Capture, the *Shade* bullet (`docs/design.md:581–589`), fixes
    `clamp(0.25 · AO_out + 1.0 · (1 − AO_in), 0, 1)`, 0.3 m and 64 samples.
  - The *Default shade range* bullet (`:595–598`) fixes `[84, 191]` and
    promises that a flat open surface, a crease and an isolated convex curve
    take different bands.
  - §Export, *Using a library from the command* (`:1036–1038`), says: "No
    command option sets the shade range; a new run uses
    `capture.backend.DEFAULT_SHADE_RANGE`, and a reused sheet keeps its
    recorded range".
  - Material styling D-10 (`material_styling_design.md:504–507`) chose the
    range from the spike's crease, flat and sphere values (about 102, 137 and
    176), which hold only at today's weights and distance.
    `tests/blender/test_material_capture.py:203–242` checks flat = 137 and
    distinct bands for N = 3, 4 and 5 at `(84, 191)`.
- **The sheet already records the shading values.** `generator.shade` records
  `ao_distance_m`, `ao_samples`, `occlusion_weight` and `convexity_weight`
  with the other technique fields. `settings.style.shade_range` records the
  range, and both enter the fingerprint (design §Export).
- **Saved style files were deferred until the owner asked.** Style pass 1 D-9,
  "Options now, saved style files later" (`style_pass_1_design.md:436`), and
  design §Deferred ("Saved style files … | The owner requests them.") defer
  them. Material styling lists them as out of scope for that arc
  (`material_styling_design.md:1415`). The owner's request of 2026-10-11 is
  that trigger.
- **The material library is JSON** (`moskophoros.materials/1`, `--materials
  FILE`). It maps each glTF material name to a ramp of palette indices, a
  named shared ramp or `"ordinary"`, with an optional default ramp. The sheet
  records it inline (design §Material libraries, D-19).
- **`--settings-from FILE`** reuses an earlier sheet's `settings`: view, model
  yaw, fps, supersample, scale, cell, ground point and pixel, root-motion mode,
  and the style (reduction, inline palette, inline library and shade range).
  Explicit options override the reused values. The reused record is checked
  strictly, and unknown fields are usage errors (design §Scale and ground
  point, *Reuse*).
- **The shading evidence.** Owner feedback-1 §4–§7 and the native 48×48
  captures R1 and R2 (`~/.local/share/moskophoros-acceptance/robotexpressive/`,
  read-only):
  - R1: AO 1.2 m, occlusion 0.5, convexity 0.0, range 120..188.
  - R2: AO 1.2 m, occlusion 0.5, convexity 0.5, range 120..255.
  - Both were made by editing `blender_script.py` and `backend.py` in a
    throwaway worktree. That is exactly the workflow the knobs replace.
  - The R1/R2 identical-rays check held on 100% of covered pixels, so
    `O = 2·s_R1` and `C = 2·(s_R2 − s_R1)`. Any weights and range at 1.2 m
    can be computed offline from those two captures (feedback-1 §7.1).
- **Related open issues:** #79 (Grey and Black clip above 191) and #78 (the
  warm ramp for Main). Both are deferred refinement records. Shading knobs
  and per-material settings would let the owner try their options without a
  code change. This design does not resolve either issue.

### Inventory

Surveyed at 87bec34. The **Proposed** column is an agent proposal for Q-1:

- **setting:** settable at every layer;
- **CLI:** command line only, because it belongs to one run or one input;
- **internal:** stays a constant.

**Command-line options** (`src/moskophoros/cli.py:1097–1281`):

| Option | Default | Range | Proposed |
|---|---|---|---|
| `--view NAME` | `iso` | `topdown`, `side`, `iso`, `iso-true` | setting |
| `--pitch DEG` | from preset | 0–90 | setting |
| `--directions N` | from preset | 1–64 | setting |
| `--start-angle DEG` | from preset | finite | setting |
| `--model-yaw DEG` | 0 | finite | CLI (per model) |
| `--clip NAME` (repeatable) | every clip | distinct names | CLI (per model) |
| `--once NAME` (repeatable) | none | among `--clip` | CLI (per model) |
| `--fps N` | 12 | > 0 | setting |
| `--ppm N` | auto | > 0 | setting |
| `--cell WxH` | reused, else fitted with `--ppm`, else 64×64 | 1–4096 each | setting |
| `--ground X,Y,Z` | 0,0,0 m | finite | CLI (per model) |
| `--ground-px X,Y` | auto | whole ≥ 0 | setting |
| `--root-motion MODE` | `error` | `error`, `keep` | setting |
| `--supersample N` | 8 | 1–16 | setting |
| `--reduce NAME` | `plain` | `plain`, `mode` | setting |
| `--palette FILE` / `--no-palette` | none | `.hex`, `.gpl`, `.png` | setting (a path) |
| `--materials FILE` / `--no-materials` | none | JSON library | setting (a path); see Q-3 |
| `--settings-from FILE` | none | sheet `/1`–`/3` | CLI; see Q-4 |
| `--no-preview` | off | — | setting |
| `--work-dir DIR` | temporary | new or empty | CLI |
| `--blender PATH` | discovered | executable | setting |
| `--any-blender` | off | — | setting |

**Constants a user could plausibly tune:**

| Constant | Value | Where | Proposed |
|---|---|---|---|
| `SHADE` AO distance, samples and weights | 0.3 m, 64, 0.25, 1.0 | `capture/blender_script.py:976–979` | setting (D-3) |
| `DEFAULT_SHADE_RANGE` | (84, 191) | `capture/backend.py:45` | setting (D-3) |
| View presets `PRESETS` | topdown 90°/8/0°, side 0°/2/90°, iso 30°/8/0°, iso-true 35.264°/8/0° | `cli.py:76–87` | open: user-defined presets? |
| `fit.DEFAULT_CELL` | 64×64 | `fit.py:18` | setting (as `--cell`'s default) |
| `fit.MARGIN` | 1 px | `fit.py:17` | open |
| `MAX_ROOT_TRAVEL_M` | 0.02 m allowed under `error` | `cli.py:66` | open |
| Coverage threshold | 0.5 | `imageops.py:416–418` | open |
| `PREVIEW_SCALE` | 4× | `export.py:32` | setting |
| `PREVIEW_BACKGROUND` | `#808080` | `export.py:33` | open (the 255-colour palette limit depends on it) |
| `ONE_SHOT_HOLD_MS` | 500 ms | `export.py:38` | setting |
| `MIN_PREVIEW_DELAY_MS` | 20 ms | `export.py:37` | internal (a GIF viewer limit) |
| Model-height warning bounds | 0.01–100 m | `fit.py:22–23` | internal |
| Workbench colour render (studio light, texture colour, no shadows or cavity, `Standard`) | fixed | `blender_script.py:896–943` | internal (V-7: lighting fixed to the camera) |
| Cycles fixed parameters (1 spp, seed 0, Box 0.01 px, bounces) | fixed | `blender_script.py:970–1000` | internal (the shared-sample contract) |
| Camera `CLEARANCE`, `MIN_RESOLUTION`, glTF import options | 1 m, 4 px, fixed | `blender_script.py:946–949, 522–524` | internal |

Limits such as the 4096 cell side, the 16× supersample, the 255-colour
palette, the 256-entry ramp, the 65534 materials, the GIF limits and the
exit codes are contracts, not knobs. The validation ranges are repeated in
`cli.py`, `capture/backend.py:320–332` and `blender_script.py:202–229`; a
settings schema could become their single home, apart from the Blender
script, which cannot import the package.

Environment: `$MOSKOPHOROS_BLENDER` and `PATH` locate Blender
(`capture/blender.py:31, 58, 68`).

## Desired experience

From the owner's words (2026-10-11):

- **Quick to change.** Try a look by editing a small YAML file, or a single
  option, and rerunning. For example:
  `moskophoros --config grey-soft.yaml hero.glb hero.png`, then
  `--convexity-weight 0.3` on top to try a variation.
- **Personal defaults.** `~/.config/moskophoros/config.yaml` holds the owner's
  usual cell, fps, palette, library and shading, so everyday commands shrink
  to the model and the output.
- **Shipped defaults are visible.** One defaults file inside the package holds
  every setting's default. It doubles as the reference for what can be set.
- **Per-material control.** Any material can override the shading values (D-9).
- **Arbitrary size, rate and length.** Any cell size, any fps, and a frame
  count per clip (D-13, D-14).
- **Reproducible.** A sheet records everything that affects its output.
  Loading it, from `--settings-from` now or a UI later, regenerates that output
  exactly, without touching the owner's YAML files (D-15, D-16).
- **A UI later** edits the same settings (D-5).

## Scope

### In scope

- The settings model: names, types, units, defaults and validation (D-21, D-30).
- The layers and their precedence, including a loaded sheet (D-2, D-8, D-17).
- Shipped defaults as a YAML file in the package.
- The D-14 settings: cell, fps, frames, the shading values with per-material
  overrides, AO samples, and the palette and library paths.
- The library moving to YAML (SET-0, #82).
- Recording every output-affecting setting in the sheet, and loading it back
  (D-15, D-16).
- The design.md amendments each slice requires, in that slice's pull request.

### Out of scope

- The UI itself (D-5). Only "do not rule it out" applies.
- Named shading presets such as "ambient" and "soft" (D-6, deferred).
- Recolouring without a re-render (D-18, deferred).
- New default values for the look (D-12).
- The inventory's other settings, which follow later, each when it is simple
  and gives value (D-14).
- A generic `--set key=value` option (D-17).
- The sheet's own format: it stays JSON (D-10).
- Directional light. D-22 and D-25 stand: the knobs tune occlusion and
  curvature only.
- Resolving #78 or #79, though the knobs let the owner try their options.
- Free chains of style passes. Settings files are requested; a pass chain is
  still deferred (style pass 1 D-7).

## Design

Each statement cites the `D-N` that decides it.

### Settings model (D-5, D-30)

- One plain, nested data structure of named values: mappings, lists, strings,
  numbers and booleans. Each leaf has a declared type, unit, default and
  validation rule, kept in one schema table in the code. That table is what a
  UI would read to build its controls (D-5).
- Names are `snake_case`, with the unit in the name where there is one,
  matching the sheet JSON (`ao_distance_m`).
- Every global setting in the first scope has its own command-line option.
  Per-clip and per-material values are set in files only (D-17).
- Settings that do not affect the output stay out of the sheet, and loading a
  sheet never changes them (D-16). Examples are local and UI preferences,
  `--work-dir` and the Blender path.

### File shape (D-21)

A user or `--config` file. Any key may be left out, and an omitted key falls
through to the layer below:

```yaml
version: 1
cell: 48x48            # width x height in pixels; auto: today's automatic sizing
fps: 12
frames: 8              # auto: each clip's frames follow fps and its length
clips:                 # per-clip overrides, by clip name
  Jump:
    frames: 6          # a count; auto: duration-based; null: take the global
shade:
  ao_distance_m: 0.3
  ao_samples: 64
  occlusion_weight: 0.25
  convexity_weight: 1.0
  range: [84, 191]
palette: ~/palettes/vince-144.gpl
materials: robot-library.yaml   # relative to this file
previews: true         # false: write no animated previews
```

New options: `--config FILE` (repeatable), `--no-user-config`, `--preview`
(D-28), `--frames N|auto`, `--ao-distance M`, `--ao-samples N`, `--occlusion-weight W`,
`--convexity-weight W` and `--shade-range LO,HI`. `--cell`, `--fps`,
`--palette`, `--materials` and `--no-preview` already exist and keep their
syntax, and `--cell` also accepts `auto` (D-32).

A `clips` entry naming a clip the model does not have is silently unused.
That follows the precedent of unused library entries (material styling D-15),
so one user file can serve many models. Per-material overrides live in the
library (D-20):

```yaml
schema: moskophoros.materials/2
ramps:
  stone: [15, 14, 12, 10, 9]
materials:
  Grey:
    uses: stone
    shade: {range: [120, 255], convexity_weight: 0.5}
```

### Layers and precedence (D-2, D-8, D-17)

**Superseded in part by the projects and camera design** (D-9, D-11, D-16 and
D-17, owner decisions 2026-10-19), which its CAM-1 slice (#128) implements:
`--config` names the one global file instead of a repeatable explicit layer,
and the explicit settings-file layer is the project file. The layers below
are those decisions; [the projects and camera design](projects_camera_design.md)
(*Files and layers*) records them.

Lowest to highest:

1. **Shipped defaults:** a YAML file inside the package (for example
   `src/moskophoros/defaults.yaml`), holding every setting.
2. **The global file,** the default project: the user file,
   `$XDG_CONFIG_HOME/moskophoros/config.yaml`, else
   `~/.config/moskophoros/config.yaml`, which is optional; or the one file
   `--config FILE` names in its place, which must exist; or none under
   `--no-user-config`, which cannot accompany `--config`.
3. **A loaded sheet:** `--settings-from FILE`, or a sheet loaded in a future
   UI. Every recorded setting that affects the output (D-16), including the
   clip selection and one-shot marks (D-19).
4. **The project file,** `--project NAME`: `projects/NAME.yaml` in the same
   configuration directory, which neither `--config` nor `--no-user-config`
   moves. It must exist. `NAME` is letters, digits, `.`, `_` and `-`, not
   starting with `.`, given without `.yaml`.
5. **Command-line options.**

- Each layer is a partial tree: a key that a layer leaves out falls through
  to the layer below. The global file and a project file share one schema.
- Lists replace rather than merge. Per-clip entries merge by clip name:
  global, then sheet, then project.
- Loading is in memory, for that generation only. The tool never writes the
  global file or a project file, and never creates `projects/` (D-15). The
  sheet never names the project or a settings file.
- Today's reuse rules carry over unchanged inside the sheet layer. An explicit
  `--view`, or a project's `view`, replaces the whole reused view, and a
  reused library still stays with its palette (design §Scale and ground
  point, *Reuse*). The loaded sheet is a snapshot in the view's layers (Merge
  rules item 9).
- The app settings, `blender` and `any_blender`, are no part of a sheet, so
  the global file's apply over a loaded sheet too (projects and camera design
  D-16).

### Merge rules (D-22)

The owner's review asked these to be explicit. The owner signed them off
(D-22).

1. **Automatic is a value.** The defaults file gives every setting a value.
   Where today's default is computed, the value is `auto`: `cell: auto` and
   `frames: auto`.
   - Any layer may set `auto` to return to the automatic behaviour.
   - `cell: auto` is today's rule: fitted with the pixels per meter when one
     is in force (from a loaded sheet or `--ppm`), else 64×64 with auto-fit.
   - So the defaults file never turns `--ppm`-only sizing into a fixed cell.
   - `ppm: auto` and `ground_px: auto` are the automatic scale and ground
     pixel, and `--ppm auto` and `--ground-px auto` take them too: each
     clears a reused or lower value and fits again (projects and camera
     design D-16, CAM-2).
2. **`null` means none**, for the palette and the library, as `--no-palette`
   and `--no-materials` do.
3. **A `--config` value acts exactly as the same explicit option would**,
   including today's reuse rules against a loaded sheet. *Superseded by the
   projects and camera design D-11:* a project file's values now act this
   way, and a `--config` file is the global file, a default below the sheet,
   as the user file is (see *Layers and precedence* above).
   - `cell` in a `--config` over a loaded sheet behaves like `--cell` after
     `--settings-from`.
   - A palette or library from a `--config` follows the material styling D-24
     table.
   - A value from the user file or the shipped defaults is only a default. The
     sheet sits above both, so they never change a loaded sheet's values.
4. **Mappings merge key by key.** Each `shade` value is separate, and `clips`
   entries merge by clip name. A clip entry's `frames: null` clears an
   inherited override (D-31).
5. **Lists replace whole,** such as `range: [lo, hi]`.
6. **Files replace whole.** The library is one setting, a path. Per-material
   overrides live inside it (D-20), so they never merge across layers.
   Nothing needs clearing, and a user file cannot inject overrides into a
   loaded sheet: the sheet records its library inline and sits above the
   user file.
7. **A library is validated against the palette in force,** wherever each
   came from, before any Blender invocation.
8. **One-shot marks over a loaded sheet (D-27).** An explicit `--once`
   replaces the loaded marks; each name must be in the loaded clip list.
9. **Compound settings.** The view was not in the first scope. *Delivered by
   the projects and camera design* (D-4, D-12 and D-16, owner decisions
   2026-10-19; CAM-2, #129): `view`, `pitch`, `directions` and `start_angle`
   are settings, with the model yaw, the scale, the ground point and pixel,
   supersampling, the reduction and root motion.
   - **The view is one state:** a preset marker, and the pitch, direction
     count and start angle, each the preset's or an override.
   - **The shipped defaults** set `iso`, with every value the preset's
     (`pitch`, `directions` and `start_angle` default to `null`).
   - **A loaded sheet is a snapshot,** not shorthand input: its recorded
     marker, `custom` included, and its values, each counted as the
     preset's. So the global file's view never applies over it.
   - **A layer's `view`** applies first within that layer, whatever its
     place in the file, and sets every value to its preset's, so it replaces
     a lower layer's pitch, direction count and start angle, as `--view`
     does.
   - **A layer's non-null `pitch`, `directions` or `start_angle`** is an
     override. **A layer's `null`** resets that value to the preset's; over a
     loaded `custom` view, which has no preset, it is a usage error naming
     the file, the key and its line, unless the same layer gives a `view`.
   - **After the last layer,** the recorded marker is the preset's name when
     every value is the preset's, else `custom`. An `iso` sheet reloaded with
     nothing above it records `iso`, with its JSON and fingerprint unchanged.
   - The command line is the last layer: `--view`, then `--pitch` or
     `--camera-direction`, `--directions` and `--start-angle`.
   - *Extended by CAM-3* (#130, projects and camera design D-7, D-12, D-14
     and D-16): the view state's first value is the camera's direction, and
     `pitch` and `camera.direction` are its two spellings, a `pitch` p
     setting `(0, −sin p, −cos p)`. One file, or the command line, giving
     both, with any values, `null` included, is a usage error; the shipped
     defaults list both as `null` and are exempt, as they set the starting
     state. `camera.roll` and `camera.position` are ordinary settings in the
     nested `camera` mapping, merged key by key. The sheet becomes
     `moskophoros.sheet/14`, recording `settings.camera` (projection,
     normalised direction, roll, position) after `settings.view`, which no
     longer records `projection` or `pitch_deg`; `--settings-from` loads
     `/14` only.
   - *Extended by CAM-4* (#131, projects and camera design D-3, D-10 and
     D-16): `camera.projection`, `orthographic` (the shipped default) or
     `perspective`, is an ordinary setting in the same `camera` mapping,
     with the option `--projection NAME`, recorded in
     `settings.camera.projection` and reloaded by `--settings-from`. It is
     no view value: it changes no preset marker. Once the layers are
     merged, a perspective camera without `camera.position`, or with the
     ground point not in front of it, is a usage error before Blender runs,
     whichever layers set the projection, the direction and the position.

### Files and errors (D-17, D-30)

- Settings files are read through SET-0's strict YAML reader. It allows only
  one document and no repeated keys, and its implicit typing is restricted.
- **Unknown keys are errors**, naming the file, the key path and the line.
- `version: 1` is optional at the top of a user or `--config` file. An unknown
  version is an error.
- **Exit codes:** every settings error is a usage error (exit 2) before any
  Blender invocation, including its version probe. A missing user file is not
  an error; a missing `--config` file is. A `blender` setting naming no
  executable, a failed version probe or a refused Blender version stays a
  backend error (exit 5), as with `--blender`, and the error names the
  settings file, the key and its line. Only the Blender that survives the
  layers is checked.
- Paths inside a file resolve relative to that file's directory, with a
  leading `~` expanded (D-30).
- Tests and scripts use `--no-user-config`, so they never read the owner's
  file.

### Shading values (D-3, D-6, D-9, D-12)

| Setting | Option | Default | R1 | R2 | Acts in | Per material |
|---|---|---|---|---|---|---|
| `shade.ao_distance_m` | `--ao-distance M` | 0.3 | 1.2 | 1.2 | capture | yes |
| `shade.ao_samples` | `--ao-samples N` | 64 | 64 | 64 | capture | no |
| `shade.occlusion_weight` | `--occlusion-weight W` | 0.25 | 0.5 | 0.5 | capture | yes |
| `shade.convexity_weight` | `--convexity-weight W` | 1.0 | 0.0 | 0.5 | capture | yes |
| `shade.range` | `--shade-range LO,HI` | [84, 191] | [120, 188] | [120, 255] | stylize | yes |

- The shade formula keeps its meaning: linear
  `clamp(occlusion_weight · AO_out + convexity_weight · (1 − AO_in), 0, 1)`.
  It covers occlusion and curvature only, with no light, direction or material
  property (D-25).
- Weights and distance reach Blender through the capture job, so
  `blender_script.py` no longer holds them as constants. Per-material values
  go into each material's replacement shader, which capture already builds.
  The range is a stylize parameter, as now.
- **Validation (D-30, D-42):** distance > 0; samples a whole number from 1 to 128;
  weights finite and ≥ 0; the range two integers with `0 ≤ lo < hi ≤ 255`, as
  reuse already checks.
- Material styling D-10's range rationale and the fixture's distinct-band
  guarantee stay bound to the defaults only (D-12).

### Frames (D-13)

- Without `frames`, sampling is exactly today's.
- With `frames` = `N`:
  - a loop samples `t0 + k·d/N`, for k = 0 … N − 1;
  - a one-shot samples `t0 + k·d/(N − 1)`, for k = 0 … N − 1;
  - `N` = 1 samples `t0`.
- Each frame lasts exactly `1/fps`, and the sheet records the clip's
  `time_scale` (D-33): `d·fps/N` for a loop of `N ≥ 2`, `d·fps/(N − 1)` for
  a one-shot of `N ≥ 2`, and `1` for automatic sampling and for every
  one-frame clip. One frame is a still (D-38).
- **A clip's value (D-31):** a count, `auto` (duration-based) or `null`
  (take the global value). `--frames auto` and `--cell auto` reset from the
  command line (D-32).
- **Validation (D-34):** a whole number of 1 or more, or `auto`, with no
  upper bound.
- **Zero-duration clips (D-25).** A clip with `d = 0`, or the synthetic
  `static` clip, always has one frame at `t0`, lasting `1/fps`. A global count
  does not apply to it. A per-clip count above 1 naming it gives a warning.
- **Precedence (D-26).** A clip's own count beats the global count from any
  layer. An explicit global gives a warning naming the clips that kept their
  own value (D-41). The sheet records counts as given (a number, `auto` or
  `null`), never the resolved totals.
- **Over a loaded sheet (D-39),** an explicit `--clip` replaces the selection
  and one-shot marks only. Per-clip counts still merge by clip name.
- Previews follow the recorded frame durations, as now.

### Recording and loading (D-15, D-16, D-28, D-30)

- The sheet's `settings` records every resolved setting that affects the
  output. The capture knobs move there from `generator.shade`, and per-material
  overrides and frame counts are recorded too.
- Where each value came from is never stored.
- **Schema bumps (D-30):** each slice that adds recorded settings bumps the sheet schema, as
  `/2` and `/3` did. Under D-24, the previous schema then stops loading.
- **The recorded schema (D-24):**
  - SET-1's sheet schema adds `settings.previews` (a boolean) after
    `root_motion` (D-28).
  - SET-2's sheet schema adds `settings.shade`: `ao_distance_m`,
    `ao_samples`, `occlusion_weight`, `convexity_weight` and `range`, after
    `previews` (D-35). With both, `settings` runs `root_motion`, `previews`,
    `shade`, `style`, `clips`.
  - `settings.style` drops `shade_range`, and `generator.shade` keeps only
    the technique fields: `technique`, `samples_per_pixel`, `seed`,
    `pixel_filter` and `filter_width_px`.
  - SET-3 adds an optional `shade` to entries in the inline library record,
    as the library gives it (D-37).
  - SET-5 adds `settings.frames` (`auto` or a count) directly after `fps`,
    a `frames` after `loop` on each `settings.clips` entry (a count, `auto`
    or `null`; D-31), and a `time_scale` (the retiming factor) after
    `frame_duration_s` on each top-level `clips` entry (D-40).
- **Only the current sheet schema loads (D-24).** A sheet of any other schema
  is a usage error (exit 2) naming its schema and the one supported.
- **The reproduction test (D-16):** generate a sheet, then rerun with
  `--settings-from` that sheet, the same model and no other options. The PNG,
  JSON and previews must be byte-identical. Each slice extends the test to its
  own settings.

### Deferred: recolouring without a re-render (D-18)

The record is kept for when the trigger arrives:

- Capture would keep occlusion (`AO_out`) and convexity (`1 − AO_in`) as
  separate values per pixel, so the weights would move from capture to
  stylize. A weight or range change would then recolour retained buffers
  without Blender, which fits V-4.
- The R1/R2 decomposition shows the arithmetic works (feedback-1 §7.1;
  manifest, *Validity*).
- **Costs:**
  - The render's channels are already full, so this needs another output.
  - 8-bit O and C combined in stylize round differently from today's single
    shade.
  - "Recolour a retained capture" is a new kind of run.
- At the owner's sizes a re-render is cheap: R1 and R2 at 48×48 took 22.6 s and
  19.9 s (manifest).

## Decisions

D-1 to D-5 were made by the owner on 2026-10-11, in the moskophoros manager's
terminal, and relayed in request moskophoros-20261011-1. D-6 onward were made
by the owner in this design conversation on the same day, round by round
(*Source notes*).

### D-1. Settings files are YAML, read with PyYAML

"im just used to yaml, and pyyaml is a pretty good library, so use yaml". The
project pin goes into `pyproject.toml` and `requirements.lock` with the first
implementation pull request, SET-0 (#82) (AGENTS.md, Architecture rules).
Affects SET-0 and SET-1.

### D-2. Four layers, each overriding the one below

From lowest to highest: shipped defaults in a YAML file inside the package,
which holds every default and is not edited by the user; the user file
`~/.config/moskophoros/config.yaml`; an explicit per-generation
`--config FILE`; then individual command-line options. "the command line
version overriding the user settings, which override the global defaults."
Affects SET-1.

### D-3. The shading constants become settings and command-line options

AO distance, occlusion weight, convexity weight and shade range become
settings and options. The AO sample count is included if the design judges it
a knob. D-9 makes it a global-only setting. R1 and R2 are the reference presets:

- R1: AO 1.2 m, occlusion 0.5, convexity 0.0, range 120..188, "more internal
  shading from ambient light";
- R2: AO 1.2 m, occlusion 0.5, convexity 0.5, range 120..255, "more flat".

The knobs do not change D-25's meaning: occlusion and curvature only, with no
light or direction. Affects SET-2.

### D-4. Per-material settings belong in the settings

"per material will definitely be in the settings". What they are is D-9. Where
they live is D-20. Affects SET-3.

### D-5. A UI comes later and must not be ruled out

"eventually actual interface in a ui, but for now, just command line
overrides and yaml global/user defaults". The settings model stays a plain
data structure that a UI could edit. The UI is not designed here. Affects
every slice.

### D-6. Raw shading values, no named presets yet

Decided by the owner on 2026-10-11, round 3. This resolves Q-10, with none of
its readings taken in full. "I want those 4 values as settings, forget ambient
and soft, i will save those for later, eventually we can have presets like
that, but for now i want to control raw values."

- The settings are the raw AO distance, occlusion weight, convexity weight
  and shade range.
- Named shading presets, and the names "ambient" and "soft", are deferred.
- R1 and R2 stay reference values for verification only.
- Whether each value is global, per material or both: D-9.

Affects SET-2 and SET-3.

### D-7. Every file the owner writes is YAML; the material library moves first

Decided by the owner on 2026-10-11, round 3. This partly resolves Q-3.

- "Everything yaml, the agent choosing json was a mistake, i like that yaml
  has comments, and is more readable to me … so everything gets yamled, i
  will do that first."
- The JSON material library is replaced by a YAML library file. This lands
  first, as its own issue (SET-0), which also brings the PyYAML pin and a
  strict YAML reader that the settings loader reuses.
- This supersedes the format part of material styling D-8 ("The library is a
  JSON file"). The tool still only reads the library.
- The sheet stays JSON (D-10), and `.json` libraries are refused (D-11).

Affects SET-0 and SET-3.

### D-8. Precedence: defaults < user file < loaded sheet < `--config` < options

Decided by the owner on 2026-10-11, round 3. This resolves Q-4 and adopts
the agent's proposal: "yea, that is fine".

- The order, lowest to highest: shipped defaults, the user file, a loaded
  sheet (`--settings-from`, or loading a sheet in a future UI), `--config`
  files, then command-line options.
- The same order applies in the UI and on the command line.
- Consequences:
  - The everyday user file never changes a reused sheet, so the sheet
    reproduces itself (V-2) and keeps its size (V-7).
  - A `--config` named on the same command line is explicit, so it does
    override the sheet.
  - The sheet must record every setting, so it can be loaded back (Q-5).

Affects SET-1.

### D-9. Global shading values, each overridable per material

Decided by the owner on 2026-10-11, round 4. This resolves Q-12, as
recommended: "both is fine".

- AO distance, occlusion weight, convexity weight and shade range each have a
  global value.
- Any material may override any of them. A material that sets none uses the
  global values.
- The AO sample count is a global-only setting.
- The per-material range amends material styling D-7 ("one global range").
- Weights and distance act in capture, through each material's replacement
  shader. The range acts in stylize.

Affects SET-2 and SET-3.

### D-10. The sheet's description stays JSON

Decided by the owner on 2026-10-11, round 4. This resolves part of Q-13: "the
sheet description can stay json". YAML covers the files the owner writes:
the library, the user file and `--config` files. The tool's output, and what
`--settings-from` reads, stays JSON (vision V-2). Affects SET-0 and SET-1.

### D-11. `.json` material libraries are refused

Decided by the owner on 2026-10-11, round 4. This resolves the rest of Q-13:
"refuse them". A library file must end in `.yaml` or `.yml`. Any other suffix
is a usage error (exit 2) before Blender starts, saying that libraries are
YAML. No conversion command is provided. Affects SET-0.

The owner approved the SET-0 issue draft on 2026-10-11 (round 4). On the
owner's word in round 5 ("file it now, i am the authority"), it was filed as
#82 ahead of the epic. The owner manages its approval.

### D-12. Today's shading values stay the shipped defaults

Decided by the owner on 2026-10-11, round 5. This resolves the first and third
parts of Q-7, as recommended: "yes, that is fine".

- The shipped defaults are AO distance 0.3 m, 64 AO samples, occlusion
  weight 0.25, convexity weight 1.0 and shade range [84, 191].
- A command that sets no new value keeps giving byte-identical output.
- Material styling D-10's range rationale and the fixture's distinct-band
  guarantee (design §Capture; `tests/blender/test_material_capture.py:203–242`)
  stay bound to these defaults only. Values the owner sets, R1 and R2
  included, are judged by eye (V-12).

Affects SET-2.

### D-13. Frame count is a setting that retimes the clip

Decided by the owner on 2026-10-11, round 6. This resolves Q-11 and adopts
the agent's proposal: "yes, it should act as any other setting, following the override path
we laid out earlier".

- `fps` is a setting.
- `frames` is an optional setting, with a global value and per-clip
  overrides keyed by clip name. Both follow the D-8 layers like any other
  setting.
- Without `frames`, sampling is exactly today's, so existing sheets
  reproduce.
- With `frames` = `N` and `fps` = `F`, the tool samples `N` poses evenly over
  the authored motion. Each frame lasts `1/F`, so the clip plays for `N/F`
  seconds, retimed by the factor `d·F/N`. The sheet records each clip's frame
  duration and retiming factor. *Corrected by D-33:* a one-shot's factor is
  `d·F/(N − 1)`.
- For a one-shot, `N` counts every cell, the final pose included, so the
  samples fall at `t0 + k·d/(N − 1)`, for k = 0 … N − 1. An `N` of 1 shows
  `t0`.

This amends design §Clips and sampling. Affects SET-5.

### D-14. The first settings scope

Decided by the owner on 2026-10-11, round 6. This resolves Q-1's scope: "yes".

- The first settings are:
  - the cell (image size, any size);
  - `fps`;
  - `frames` (D-13);
  - the four shading values, global with per-material overrides (D-9), plus
    the global AO sample count;
  - the palette path;
  - the material library path;
  - whether previews are written (added by D-28).
- The inventory's other settings follow later, each when it is simple and
  gives value (owner, round 2).
- How this scope splits into pull requests is D-21.

### D-15. A sheet records every setting and loads them as one in-memory layer

Decided by the owner on 2026-10-11, round 6. This resolves Q-5: "yes". It
extends D-8.

- The sheet's `settings` block records every resolved setting, including the
  shading values, per-material overrides and frame counts. The capture knobs
  move from `generator.shade` into `settings`. This is a new sheet schema
  version. *Amended by D-24:* older sheets no longer load.
- Where each value came from is not stored in the sheet, so identical
  settings give identical bytes. It may be printed on request.
- The owner: "all these would override the client settings at once … this is
  not saved to disk, just loaded into the program, we dont overwrite the
  user's yaml settings, just the values for the generation." Loading a sheet
  supplies one layer, in memory, for that generation only. The tool never
  writes the user file or any `--config` file.
- Which recorded settings a loaded sheet applies is D-16.

Affects SET-1 and SET-2.

### D-16. Loading a sheet applies everything that affects the output

Decided by the owner on 2026-10-11, round 7. This resolves Q-14 with reading
(a), widened: "everything that effects the output, reusing a sprite's settings
with the same model should generate identical output, we should have a test
for that. if there are client settings that done effect output, we dont change
those, these might be related to the ui for instance, local settings for
users, but the generation needs to be identical. so (a)".

- Every recorded setting that affects the sheet PNG, its JSON or the previews
  loads, model yaw and the ground point included.
- Settings that do not affect the output are not recorded, and loading a
  sheet never changes them. Examples are local and UI preferences.
- A test regenerates a sheet from itself with the same model and no other
  options, and requires byte-identical output. Each slice extends it.
- Clip selection and one-shot marks also affect the output, but today's design
  always takes them from the command line. Loading them is confirmed
  separately: D-19 confirms it.

Affects SET-1, SET-2, SET-3 and SET-5.

### D-17. Settings file and option details

Decided by the owner on 2026-10-11, round 7. This resolves Q-6 and the
remaining P-2 proposals, as recommended: "that's all fine".

- `--config FILE` may be repeated, and later files win.
- The user file is `$XDG_CONFIG_HOME/moskophoros/config.yaml` when that
  variable is set, else `~/.config/moskophoros/config.yaml`.
- `--no-user-config` skips the user file, for tests and scripts.
- Every global setting in the first scope has its own option. Per-clip and
  per-material values are set in files only.
- There is no generic `--set key=value` option for now.
- A settings file may carry `version: 1`. Unknown keys and unknown versions
  are usage errors (exit 2) before any Blender invocation.

Affects SET-1, SET-2 and SET-5.

### D-18. Recolouring without a re-render is deferred

Decided by the owner on 2026-10-11, round 7. This resolves Q-8, as
recommended: "defer".

- SET-4 leaves this arc's active plan. Its trigger is iteration speed
  becoming a problem, and the owner asking for it.
- The analysis stays under Design, *Deferred*, and goes into design §Deferred
  when this arc amends design.md.

### D-19. A loaded sheet supplies the clip selection

Decided by the owner on 2026-10-11, round 8. This resolves Q-15, as proposed:
"proposal approved".

- A loaded sheet supplies the clip list and one-shot marks from
  `settings.clips`.
- An explicit `--clip` replaces the whole list, and `--once` then comes from
  the command line, as now. *Amended by D-39:* per-clip frame counts are not
  part of that list; they merge by clip name.
- A recorded clip that the model no longer has is an input error (exit 3), as
  an unknown `--once` is today.
- This replaces design §Scale and ground point (*Reuse*): "Clip selection and
  `--once` always come from the current command line."

Affects SET-1.

### D-20. Per-material shading overrides live in the library

Decided by the owner on 2026-10-11, round 8. This resolves Q-16 with option
(a): "(a) sounds better when you put it that way, lets go (a)".

- A material entry in the YAML library may carry an optional `shade` mapping.
  It may override any of `ao_distance_m`, `occlusion_weight`,
  `convexity_weight` and `range`, but not `ao_samples`.
- The entry still has exactly one of `ramp` or `uses`. The `"ordinary"` form
  carries no `shade`, since the ordinary look does not use the shade.
- A material without an override, or taking the default ramp, uses the global
  values.
- This is a new library schema, `moskophoros.materials/2`. The library stays
  the one place that defines a material's look, shared across models
  (material styling D-3).
- The sheet already records the library inline, so the overrides reload with
  it. To vary one material for one generation, the owner edits or copies the
  library.

**Amended by material styling D-35 (owner, 2026-10-14):** a
`moskophoros.materials/3` library may also give a top-level `shade`. It
gives `range` only (material styling D-36), which comes between a material's
own range and the global one, and materials taking the default ramp use it
too. Capture values, and this design's D-36, are unchanged.

**Amended by [shading design](shading_design.md) D-33 (owner, 2026-10-21; implemented by #143, 2026-10-21):** a `moskophoros.materials/4` ordinary entry may be a mapping, `{ordinary: true, shade: {...}}`, carrying the response overrides of that design's contract 2 and the existing per-material capture overrides (`ao_distance_m`, `occlusion_weight`, `convexity_weight`) and `range`. The string `"ordinary"` still carries none, and `/2` and `/3` libraries are unchanged. `ao_samples` stays global only.

Affects SET-3.

### D-21. The slice plan, file shape, formats and options

Decided by the owner on 2026-10-11, round 8. This resolves Q-9: "the slice
plane and file shape and formats and options all look right to me, write it
in the doc".

- **The slices,** in order: SET-0 (#82), SET-1, SET-2, SET-3 and SET-5. SET-4
  is deferred (D-18).
- **The file shape** is under Design, *File shape*.
- **The new options** are `--config FILE` (repeatable), `--no-user-config`,
  `--frames N`, `--ao-distance M`, `--ao-samples N`, `--occlusion-weight W`,
  `--convexity-weight W` and `--shade-range LO,HI`.
- **Readiness:** the owner will review this document with another agent
  before marking it ready, so its state stays `exploring` until then.

Affects every slice.

### D-22. The merge rules

Decided by the owner on 2026-10-11, round 10. This resolves the first part of
Q-18 and adopts P-8 as proposed: "that is fine". The rules are under Design,
*Merge rules*:

- `auto` is a value;
- `null` means none;
- a `--config` value acts as the explicit option;
- mappings merge by key, while lists and files replace whole;
- the library is validated against the palette in force;
- the view keeps today's rules until it becomes a setting.

Affects SET-1, SET-2, SET-3 and SET-5.

### D-23. A material's own value beats any global value

Decided by the owner on 2026-10-11, round 10. This resolves Q-17 with option
(a).

- A per-material override in the library wins over the global value, whatever
  layer the global came from. An option such as `--convexity-weight 0`
  changes only the materials without their own value.
- When a global value is set explicitly, by a `--config` file or an option,
  and a material in use overrides it, a warning names that material and the
  value it kept. The warning is not an error, and the output does not change
  with it.

Affects SET-3.

### D-24. Only the current sheet schema loads; the recorded fields as proposed

Decided by the owner on 2026-10-11, round 10. This resolves the rest of Q-18:
"it doesnt matter, we are developing still though, none of my current sheets
matter, just dont support old formats."

- `--settings-from`, and later a UI, loads only the current sheet schema. Any
  other schema is a usage error naming it and the supported one.
- Reading `/1` and `/2` sheets is removed in SET-1. After that, each schema
  bump stops the previous one loading.
- This replaces D-15's "older sheets still load" and the older-sheet rules in
  design §Scale and ground point (*Reuse*).
- The owner left the field layout to the design ("it doesnt matter"), so the
  proposed layout is adopted. It is under Design, *Recording and loading*.

Affects SET-1, SET-2, SET-3 and SET-5.

### D-25. A zero-duration clip keeps one frame

Decided by the owner on 2026-10-11, round 12. This resolves Q-20 as proposed:
"all recommended".

- A clip with `d = 0`, or the synthetic `static` clip, always has exactly one
  frame, at `t0`, lasting `1/fps`, so no two frames share an address (V-9).
- A global count does not apply to such a clip. A per-clip count above 1
  naming it gives a warning naming the clip.
- SET-5's acceptance covers a global count over a `static` model, a per-clip
  count on a zero-duration clip, and a count of 1.

Affects SET-5.

### D-26. A clip's own count beats the global count

Decided by the owner on 2026-10-11, round 12. This resolves Q-21 as proposed,
mirroring D-23.

- A clip's own `frames` wins over the global count from any layer.
- When the global is set explicitly, by a `--config` file or `--frames`, a
  warning names each clip that kept its own count.
- `frames: auto` on a clip's entry clears its count. *Amended by D-31:* a
  clip's `auto` means duration-based sampling, and `null` clears an override.
- The sheet records counts as given: the global count or `auto`, and each
  clip's own count or `auto`.

Affects SET-5.

### D-27. An explicit `--once` replaces a loaded sheet's one-shot marks

Decided by the owner on 2026-10-11, round 12. This resolves Q-22 as proposed.

- Over a loaded sheet without `--clip`, the clips named by `--once` are
  exactly the one-shots.
- Each name must be in the loaded clip list. A name that is not there is a
  usage error.
- Without `--once`, the loaded marks stay. `--clip` resets the selection as
  in D-19.
- SET-1 tests each case.

Affects SET-1.

### D-28. Previews on or off is a recorded setting

Decided by the owner on 2026-10-11, round 12. This resolves Q-23 with option
(a).

- `previews: true | false` joins the first scope (amending D-14). It is
  recorded in `settings` and enters the fingerprint like any setting.
- `--no-preview` sets it false, and a new `--preview` sets it true over a
  loaded sheet (amending D-21's options).
- A reused sheet made without previews therefore writes none, and the
  reproduction test covers the sheet PNG, its JSON and the previews.
- SET-1 records it, so SET-1 takes a sheet-schema bump (D-30). This amends
  SET-1's "no schema changes".

Affects SET-1.

### D-29. A `moskophoros.materials/1` library stops loading in SET-3

Decided by the owner on 2026-10-11, round 12. This resolves Q-19 as proposed.

After SET-3 only `moskophoros.materials/2` loads. A `/1` library is a usage
error saying to change its `schema` line, which is the only edit it needs.
**Amended by material styling D-34 (owner, 2026-10-14):** MAT-8 adds
`moskophoros.materials/3`, and `/2` keeps loading beside it.

Affects SET-3.

### D-30. The settings structure, validation limits, paths and schema bumps

Decided by the owner on 2026-10-11, round 12. This resolves Q-24 and adopts
the remaining proposals:

- **One structure (P-1):** one plain settings structure, with one schema table
  in the code that a UI can read.
- **Limits and paths (P-2):**
  - AO distance > 0;
  - AO samples a whole number from 1 to 128 (D-42 amends the original 1 to 1024);
  - weights finite and ≥ 0;
  - the range two integers with `0 ≤ lo < hi ≤ 255`;
  - paths resolve relative to their file, with a leading `~` expanded.
- **Schema bumps (P-6):** each slice that adds recorded settings bumps the
  sheet schema, and under D-24 the previous schema stops loading.

Affects every slice.

### D-31. A clip's frame count is a number, `auto` or `null`

Decided by the owner on 2026-10-11, round 14. This resolves Q-25 as proposed
("all four approved") and amends D-26's "`frames: auto` clears its count".

- **A number** is the clip's own count, and it beats the global count.
- **`auto`** is duration-based sampling for that clip, and it also beats the
  global count.
- **`null`, or leaving the key out,** is no override: the clip takes the
  global value. In a higher layer, `null` clears a lower layer's override.
- **The record:** the sheet records the global value as a count or `auto`,
  and each clip's own value as a count, `auto` or `null`. A reload reproduces
  exactly, and `--frames` over a loaded sheet reaches every clip whose value
  is `null`.

Affects SET-5.

### D-32. `--cell auto` and `--frames auto`

Decided by the owner on 2026-10-11, round 14. This resolves Q-26 as proposed.

- Both options accept `auto`, so the command line can clear an inherited
  fixed value.
- `--no-palette` and `--no-materials` reset those two, as now.
- Per-clip and per-material values have no options (D-17).

Affects SET-1 (`--cell auto`) and SET-5 (`--frames auto`).

### D-33. `time_scale` is the sample spacing over the frame duration

Decided by the owner on 2026-10-11, round 14. This resolves Q-27 as proposed
and corrects D-13's factor for one-shots.

| Clip | `time_scale` |
|---|---|
| explicit count `N`, loop | `d·fps/N` |
| explicit count `N ≥ 2`, one-shot | `d·fps/(N − 1)` |
| automatic sampling | exactly `1` |
| one frame (zero duration, `static`, or a one-shot with `N` = 1) | `1` |

*Amended by D-38:* the one-frame row covers any clip with `N` = 1, looping
or one-shot, and the loop row applies from `N` = 2.

Tests cover each case. Affects SET-5.

### D-34. Frame-count validation

Decided by the owner on 2026-10-11, round 14. This resolves Q-28 as proposed.

- A frame count is a whole number of 1 or more, or `auto`, and a clip's
  count may also be `null` (D-31).
- In YAML it must be an integer: never `8.0`, `"8"` or a boolean. On the
  command line it must be a decimal integer or `auto`.
- There is no separate upper bound, as `--fps` has none. The existing sheet
  and GIF limits still apply and fail loudly.
- An invalid count is a usage error (exit 2) before any Blender invocation.

Affects SET-5.

### D-35. `settings.shade` follows `settings.previews`

Decided by the owner on 2026-10-11, during issue processing, option (a):
"a". Both D-24's `shade` and D-28's `previews` were placed "after
`root_motion`".

- `settings` runs `root_motion`, `previews`, `shade`, `style`, `clips`.
- SET-1 (#84) adds `previews` directly after `root_motion`, unchanged. SET-2
  adds `shade` directly after `previews`.

Affects SET-2.

### D-36. The capture job carries each material's capture values

Decided by the owner on 2026-10-11, during issue processing, option (a):
"i approve your recommendations for both".

- design.md §Capture job and result contract says the job leaves out the
  sheet's `style`, "so the job is the same whatever the style" (owner
  decision 2026-10-04). D-9 puts each material's weights and distance in its
  capture shader, and D-20 puts those overrides in the library, which is part
  of the style. So the rule is amended.
- The job carries each material's AO distance, occlusion weight and
  convexity weight, keyed by glTF material, and nothing else from the style.
  It stays the same whatever the ramps, the palette, the reduction, the shade
  range and the default ramp.
- SET-3 amends that design.md row. The alternative, moving the weights from
  capture to stylize, is the deferred recolouring (D-18).

Affects SET-3.

### D-37. The inline library record keeps each material's overrides as given

Decided by the owner on 2026-10-11, during issue processing, option (a), with
D-36.

- A material entry's `shade` follows its `ramp` or `uses` in the sheet's
  inline library record.
- It holds only the keys the library gives, in a fixed order whatever the
  file's key order: `ao_distance_m`, `occlusion_weight`, `convexity_weight`,
  `range`. An entry without overrides has no `shade`.
- Reloading restores exactly what the library said, as the record already
  does for ramps.

Affects SET-3.

### D-38. One frame is a still

Decided by the owner on 2026-10-11, during issue processing: "frames: 1
means a static image", then "choose your recommended for both". The
*Frames* section's "one-frame clips" and D-33's one-frame row disagreed on
a looping clip with a count of 1.

- Any clip with one frame is a still image. Its frame is at `t0`, lasts
  `1/fps`, and the sheet records `time_scale: 1`.
- That covers a count of 1, looping or one-shot, a zero-duration clip and
  `static`.
- D-33's one-frame row becomes "zero duration, `static`, or any clip with
  `N` = 1". The loop row `d·fps/N` applies from `N` = 2.

Affects SET-5.

### D-39. An explicit `--clip` replaces only the clip selection

Decided by the owner on 2026-10-11, during issue processing, option (a).
D-19's "`--clip` replaces the whole list" and the merge rule "`clips`
entries merge by clip name" disagreed on a loaded sheet's per-clip counts.

- Over a loaded sheet, an explicit `--clip` replaces the clip list and the
  one-shot marks (D-19), but not the per-clip frame counts.
- Per-clip counts merge by clip name across layers, the loaded sheet's
  included. So a re-selected clip keeps its loaded count, and `--frames`
  reaches only the clips whose value is `null` (D-31).

Affects SET-5.

### D-40. Where the frame fields sit in the sheet

Decided by the owner on 2026-10-11, during issue processing, option (a).
The design named SET-5's fields but not their positions.

- `settings.frames` comes directly after `settings.fps`.
- Each `settings.clips` entry runs `name`, `loop`, `frames`.
- Each top-level `clips` entry gains `time_scale` directly after
  `frame_duration_s`.

Affects SET-5.

### D-41. Which clips the frame-count warning names

Decided by the owner on 2026-10-11, during issue processing: "choose your
recommended for both". This makes D-25's and D-26's warnings exact.

- When the global count is set explicitly, by `--frames` or a `--config`
  file, as a count or as `auto`, the warning names every selected clip whose
  own value (a count or `auto`) beats it. It fires even when the two values
  are equal, as SET-3's material warning does (D-23).
- Zero-duration and `static` clips are left out of that warning. They give
  only D-25's warning, and only when their own count is above 1.
- A `clips` entry naming a clip that is not selected gives no warning of
  either kind.

Affects SET-5.

### D-42. AO samples run from 1 to 128

Decided by the owner on 2026-10-12, during SET-2 implementation, option (a).
D-30 allowed 1 to 1024 samples. Blender 5.2.2 LTS, the supported version,
hard-limits the Ambient Occlusion node's `samples` to 1..128 and silently
clamps any higher value to 128 (checked under the Blender lock: 129 → 128,
1024 → 128).

- AO samples are a whole number from 1 to 128, in every layer and for every
  material. The default stays 64.
- A value outside 1..128 is a usage error (exit 2) before any Blender
  invocation. It names the option, or the file, key path and line, and states
  the limit.
- If a later supported Blender raises the node's limit, raising this limit is
  a new decision.

Affects SET-2 and SET-3.

## Open questions

None.

## Resolved questions

Each kept with its identifier. The owner's words are under *Source notes*.

- **Q-1.** Which settings exist? The inventory's labels were accepted.
  **Resolved by D-14**, the first scope. "Scale" meant image size, the cell.
- **Q-2.** What are the per-material settings? The four shading values except
  AO samples. **Resolved by D-9.** Ramps stay in the library.
- **Q-3.** How do per-material settings relate to the library? The library
  becomes YAML (**D-7**), JSON libraries are refused (**D-11**), and the sheet
  stays JSON (**D-10**). The overrides live in the library
  (**D-20**).
- **Q-4.** Where does a loaded sheet sit among the layers? **Resolved by D-8.**
- **Q-5.** What does the sheet record? **Resolved by D-15**; what loading
  applies is **D-16**.
- **Q-6.** Schema details. **Resolved by D-17.**
- **Q-7.** Defaults, presets and the bound guarantees. **Resolved by D-12**
  (today's values stay the defaults, and the guarantees stay bound to them)
  and **D-6** (no presets or example files; R1 and R2 are references).
- **Q-8.** Recolouring without a re-render. **Resolved by D-18:** deferred.
- **Q-10.** The "ambient" and "soft" dials. **Resolved by D-6:** raw values.
- **Q-11.** What "frame count" means. **Resolved by D-13:** retiming.
- **Q-12.** Global or per material. **Resolved by D-9:** both.
- **Q-13.** What "everything YAML" covers. **Resolved by D-10 and D-11.**
- **Q-14.** What a loaded sheet applies. **Resolved by D-16.**
- **Q-15.** Whether a loaded sheet supplies the clip selection. **Resolved by
  D-19:** yes.
- **Q-16.** Where per-material overrides live. **Resolved by D-20:** in the
  library.
- **Q-9.** The slice plan and file shape. **Resolved by D-21.**
- **Q-17.** A global value against a material's override. **Resolved by
  D-23:** the material wins.
- **Q-18.** The merge rules and the recorded schema. **Resolved by D-22 and
  D-24.**
- **Q-19.** The `/1` library after SET-3. **Resolved by D-29.**
- **Q-20.** Frame counts on zero-duration clips. **Resolved by D-25.**
- **Q-21.** A clip's count against the global count. **Resolved by D-26.**
- **Q-22.** `--once` over a loaded sheet. **Resolved by D-27.**
- **Q-23.** Previews and the reproduction promise. **Resolved by D-28.**
- **Q-24.** The remaining proposals. **Resolved by D-30.**
- **Q-25.** A clip's `auto` against `null`. **Resolved by D-31.**
- **Q-26.** Resetting from the command line. **Resolved by D-32.**
- **Q-27.** `time_scale` when nothing is retimed. **Resolved by D-33.**
- **Q-28.** Frame-count validation. **Resolved by D-34.**

### The owner's third review, 2026-10-11

The review read 81a6083 and found it nearly ready. It raised three contract
gaps (Q-25 to Q-27) and a validation rule (Q-28), all resolved in round 14
by D-31 to D-34.

### The owner's second review, 2026-10-11

The review read 948b91f. It found the scope, the material inheritance, the
schema retirement and the delivery plan sound, with targeted gaps:

1. **Frame counts on zero-duration clips:** Q-20.
2. **A per-clip count against a global count:** Q-21.
3. **`--once` without `--clip` over a loaded sheet:** Q-22.
4. **`--no-preview` and the reproduction promise:** Q-23.
5. **Q-19** was still open.

All five were resolved by the owner in round 12 (D-25 to D-29).

### The owner's review, 2026-10-11

The owner had another agent review the document. Its line numbers match
1460e55, the round-6 version. Disposition against the current text:

1. **Precedence contradicted D-8:** fixed in 9b5d1e9. Every section now uses
   D-8's order, and per-material values follow D-9 and D-20.
2. **Merge rules for absent, automatic and reset values and compound
   options:** a real gap. **Resolved by D-22.**
3. **Per-material storage and inheritance:** storage is settled by D-20, with
   a YAML example under Design, *File shape*. Injection from the user file is
   impossible (D-22, rule 6). Global against override is **D-23**.
4. **Frame count had no semantics or slice:** settled by D-13, delivered by
   SET-5.
5. **The reproduction promise exceeded reuse:** the clip selection is D-19. The
   recorded schema is **D-24**, and older sheets are not supported.
6. **SET-1's dependencies contradicted D-7:** fixed in 9b5d1e9. SET-1 depends
   on SET-0, and the pin is only in SET-0.

## Verification strategy

- **Pure tests**, needing no Blender or filesystem, for:
  - layer merging and precedence, each pair of layers;
  - validation, unknown keys and versions;
  - YAML traps and duplicate keys (SET-0's reader);
  - path resolution;
  - retimed sample times;
  - per-material banding.
- **Command tests** with temporary user and `--config` files:
  - precedence end to end;
  - exit 2 before any Blender invocation;
  - `--no-user-config`;
  - no test ever reads the owner's real user file.
- **Byte identity with no settings:** with no user file, no `--config` and no
  new options, every sheet PNG and preview is byte-identical to today's. The
  JSON changes only by the slice's schema bump.
- **The reproduction test (D-16):** a sheet regenerated from itself with the
  same model is byte-identical, PNG, JSON and previews. It runs in the
  whole-command Blender tests and grows with each slice.
- **Blender tests** for the shading values: non-default global and
  per-material weights and distance reach the shade buffer and the record.
  The fixture's distinct-band check stays at the defaults (D-12).
- **Owner acceptance (V-12):** reproduce R1 and R2 from `--config` files with
  the YAML conversion of `library-draft.json`. Their sheet PNGs and previews
  should match the 2026-10-09 manifest hashes (`R1/RobotExpressive.png`
  d69bf461…, `R2/RobotExpressive.png` 59d0a37c…). If a merged change since has
  altered rendering, the pull request names it. The owner then judges new
  variations by eye.

## Delivery plan

Signed off by the owner on 2026-10-11 (D-21). Every slice amends design.md in
its own pull request, because tests read design.md.

### SET-0. Read material libraries from YAML instead of JSON

- **Outcome:** `--materials FILE` reads a YAML library with the same fields and
  validation as today, through a strict YAML reader that the settings loader
  reuses.
- **Scope:**
  - the strict reader;
  - the PyYAML pin;
  - the library reader;
  - tests;
  - the design §CLI and §Material libraries amendments;
  - the README.
- **Phase:** 0.
- **Depends on:** none.
- **Ordering:** can land first.
- **Relevant decisions:** D-1, D-7, D-10, D-11.
- **Acceptance signals:**
  - the same library content in YAML gives the same `Library`, with
    byte-identical sheet PNGs and previews;
  - YAML 1.1 traps, repeated keys and multiple documents are refused with
    named errors before Blender starts.
- **Out of scope:**
  - per-material shading fields (SET-3);
  - the settings loader (SET-1);
  - the sheet's format;
  - palette formats.
- **Open questions:** None. The owner approved the issue draft on 2026-10-11,
  and it is filed as #82.

### SET-1. Load layered YAML settings for the existing options

- **Outcome:** the shipped defaults file, the user file, repeatable `--config`
  files and a loaded sheet merge under the command line in D-8's order. Cell,
  fps, palette and library work at every layer. A loaded sheet applies every
  setting that affects the output, and the reproduction test is in place.
- **Scope:**
  - the settings schema table and the pure merge and validation functions;
  - the packaged defaults file;
  - user-file discovery and `--no-user-config`;
  - `--cell auto` (D-32);
  - path resolution;
  - errors (D-17);
  - the clip selection from a loaded sheet (D-19), and `--once` over it
    (D-27);
  - `previews` as a recorded setting, with `--preview`, under the next sheet
    schema (D-28);
  - design §CLI, §Option validation, §Scale and ground point (*Reuse*),
    §Reproducibility and §Project layout;
  - the README.
- **Phase:** 1.
- **Depends on:** SET-0.
- **Ordering:** critical path.
- **Relevant decisions:** D-2, D-5, D-8, D-14, D-15, D-16, D-17, D-19, D-21.
  Also D-22, D-24 (only the current schema loads), D-27, D-28, D-30 and D-32.
- **Acceptance signals:**
  - precedence and error tests;
  - byte identity with no settings files;
  - the reproduction test, including a sheet made with `--no-preview`;
  - the `--once` cases over a loaded sheet;
  - tests never read the real user file.
- **Out of scope:** shading values, frames and per-material overrides.
- **Open questions:** None.

### SET-2. Make the global shading values settings and command-line options

- **Outcome:** AO distance, AO samples, the occlusion and convexity weights
  and the shade range are settings and options. They reach Blender through
  the capture job and are recorded in `settings`, under the next sheet
  schema. A loaded sheet restores them, and R1 and R2 can be reproduced from
  `--config` files.
- **Scope:**
  - the capture job and `blender_script.py` read the values instead of
    `SHADE`;
  - `backend.DEFAULT_SHADE_RANGE` gives way to the setting;
  - design §Capture (*Shade* and *Default shade range*), §Export (the
    overridden "No command option sets the shade range") and §CLI;
  - the new schema, with the previous one no longer loading (D-24).
- **Phase:** 2.
- **Depends on:** SET-1.
- **Ordering:** critical path.
- **Relevant decisions:** D-3, D-6, D-9 (global values), D-12, D-15, D-16,
  D-22, D-24, D-35.
- **Acceptance signals:**
  - a Blender test that non-default values reach the shade buffer and the
    record;
  - default output byte-identical;
  - the fixture's distinct-band test unchanged;
  - the reproduction test extended;
  - R1 and R2 reproduction for the owner.
- **Out of scope:** per-material values; recolouring without a re-render.
- **Open questions:** None.

### SET-3. Let each material override the shading values

- **Outcome:** any material may override AO distance, the weights and the
  range. Capture applies the material's weights and distance in its
  replacement shader, and stylize bands each material over its own range.
  The overrides are recorded and reloaded.
- **Scope:**
  - the `shade` mapping on library entries, under `moskophoros.materials/2`
    (D-20), with `/1` no longer loading (D-29);
  - capture and stylize changes, and the D-23 warning;
  - design §Material libraries, §Material ramps and §Capture;
  - the amendment to material styling D-7 ("one global range").
- **Phase:** 3.
- **Depends on:** SET-0, SET-2.
- **Ordering:** critical path for per-material control.
- **Relevant decisions:** D-4, D-9, D-15, D-16, D-20, D-22, D-23, D-24, D-29,
  D-36, D-37.
- **Acceptance signals:**
  - a Blender test with two materials of different weights and distance in
    one frame;
  - pure tests of per-material banding;
  - the reproduction test extended;
  - output without overrides byte-identical.
- **Out of scope:** generated ramps (MAT-8); AO samples per material.
- **Open questions:** None.

### SET-5. Set a clip's frame count, retiming it to the fps

- **Outcome:** `frames`, global and per clip, samples each clip as D-13
  defines, records each clip's frame duration and retiming factor, and
  reloads them. Without `frames`, sampling is unchanged.
- **Scope:**
  - `sampling.py`;
  - the `--frames N` option and the per-clip file entries;
  - the sheet's clip records, under the next sheet schema;
  - design §Clips and sampling, §Export and §CLI.
- **Phase:** 3.
- **Depends on:** SET-1.
- **Ordering:** independent of SET-2 and SET-3. Each sheet-schema bump takes
  the next version, whichever slice lands first.
- **Relevant decisions:** D-13, D-14, D-15, D-16, D-17, D-22, D-24, D-25,
  D-26, D-31, D-32, D-33, D-34, D-38, D-39, D-40, D-41.
- **Acceptance signals:**
  - pure sampling tests for loop, one-shot and `N` = 1;
  - zero-duration and `static` clips keep one frame, with the warning for a
    per-clip count (D-25);
  - a clip's own count beats `--frames`, with the warning (D-26);
  - frame duration exactly `1/fps`;
  - `time_scale` for each D-33 case;
  - a clip's count, `auto` and `null`, each reloaded exactly (D-31);
  - `--frames auto`;
  - the D-34 validation errors;
  - output without `frames` byte-identical;
  - the reproduction test extended.
- **Out of scope:** root-motion extraction; per-clip fps.
- **Open questions:** None.

### SET-4. Recolour shading without a re-render

- **Status:** deferred (D-18), not part of this arc's active plan.
- **Precondition:** iteration speed becomes a problem, and the owner asks for
  it.
- **Depends on:** SET-2.
- **Relevant decisions:** D-18.

## Source notes

The owner's words, 2026-10-11, in this design conversation:

- **Round 2:** "your settings look good, if its simple to include and
  provides value, we should include it, but for the first design slice we can
  limit it to the scale, fps, frame count, and i think most importantly are
  the two shading dials that i want to control shading, ambient (known in my
  work currently as R1) and soft (R2). … i would allow more if you think it
  wise. 2) yes, all of the shading stuff needs per material values as well,
  im not sure what all i want, but for a first slice, the shade range, min and
  max, with materials defined in yaml, i didnt realize i was already using
  json, ideally i would want everything in yaml if possible, we can gate this
  work on an issue to address that first if you think that's ok. 3) … when i
  implement a ui, i want to load up a sprite, see its current sheet and all
  of the settings used in its generation get loaded in to the parameters
  automatically …"
- **Round 3:** "i generate 48x48 each time now, but i need to support
  arbitrary sizes, so yes, scale is incorrect terminology, i meant image
  size. … i want those 4 values as settings, forget ambient and soft … i guess
  these would be per material, maybe we dont need a global, you tell me. 2)
  yea a new library file, everything yaml … i will do that first, you can
  draft the issue for me now. 3) yea, that is fine"
- **Round 4:** "1) both is fine, 2) ok, the sheet description can stay json.
  3) refuse them. i approve your draft issue as well"
- **Round 5:** "1) yea, file it now, i am the authority, i will manage getting
  it approved … 2) when i think about an animation, its frame count, and fps,
  with the total duration being determined by those two characteristics …
  the important thing is that we can generate animations of arbitrary fps and
  length … 3) yes, that is fine"
- **Round 6:** "1) yes, it should act as any other setting, following the
  override path we laid out earlier. 2) yes, 3) yes, i think that the sheet
  should store a settings block with the settings that effect more than just
  the sprite in question, as well as per material settings, then all these
  would override the client settings at once. … this is not saved to disk,
  just loaded into the program, we dont overwrite the user's yaml settings,
  just the values for the generation."
- **Round 7:** "1) everything that effects the output, reusing a sprite's
  settings with the same model should generate identical output, we should
  have a test for that. if there are client settings that done effect output,
  we dont change those … so (a) 2) that's all fine, 3) defer"
- **Round 8:** "1) proposal approved, 2) (a) sounds better when you put it
  that way, lets go (a) 3) the slice plane and file shape and formats and
  options all look right to me, write it in the doc, i will will review the
  doc with another agent first before getting back to you, so dont mark it
  ready yet"
- **Round 9, the owner's review:** an outside agent's six findings,
  dispositioned under *Resolved questions*.
- **Round 10:** "1) that is fine, 2) (a) 3) it doesnt matter, we are
  developing still though, none of my current sheets matter, just dont
  support old formats."
- **Round 11, the owner's second review:** four targeted gaps and Q-19,
  dispositioned under *Resolved questions*.
- **Round 12:** "all recommended"
- **Round 13, the owner's third review:** three contract gaps and a
  validation rule.
- **Round 14:** "all four approved"
- **Round 15:** "i think its probably ready, go ahead and mark it so if you
  agree."
