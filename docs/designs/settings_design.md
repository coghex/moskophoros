# Settings design: YAML defaults, user settings and command-line knobs

Today every moskophoros setting is either a command-line option or a constant
in the code. The owner wants "knobs": values they can change on the fly
between generations without editing code. Those values live in YAML: shipped
defaults, overridden by the owner's own settings, overridden by a
per-generation file, overridden by the command line. The first knobs are the
shading constants behind the R1 and R2 renders. The design also has to make
room for many more settings, for per-material settings, and later for a UI
that edits the same settings (owner, 2026-10-11).

Design state: `exploring`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

The owner signed off this slice list on 2026-10-11 (D-21). The design stays
`exploring` until the owner's own review of this document is done.

- [ ] EPIC. Configure moskophoros from layered YAML settings and command-line overrides
- [#82] SET-0. Read material libraries from YAML instead of JSON
- [ ] SET-1. Load layered YAML settings for the existing options
- [ ] SET-2. Make the global shading values settings and command-line options
- [ ] SET-3. Let each material override the shading values
- [ ] SET-5. Set a clip's frame count, retiming it to the fps
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

- The settings model: names, types, units, defaults and validation (P-1, D-21).
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

Each statement cites the `D-N` that decides it. A `P-N` marks a proposal that
the owner has not signed off.

### Settings model (P-1; D-5)

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
cell: 48x48            # width x height in pixels; unset: fit the model to 64x64
fps: 12
frames: 8              # optional; unset: each clip's frames follow fps and its length
clips:                 # per-clip overrides, by clip name
  Jump:
    frames: 6
shade:
  ao_distance_m: 0.3
  ao_samples: 64
  occlusion_weight: 0.25
  convexity_weight: 1.0
  range: [84, 191]
palette: ~/palettes/vince-128.gpl
materials: robot-library.yaml   # relative to this file
```

New options: `--config FILE` (repeatable), `--no-user-config`,
`--frames N`, `--ao-distance M`, `--ao-samples N`, `--occlusion-weight W`,
`--convexity-weight W` and `--shade-range LO,HI`. `--cell`, `--fps`,
`--palette` and `--materials` already exist and keep their syntax.

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

Lowest to highest:

1. **Shipped defaults:** a YAML file inside the package (for example
   `src/moskophoros/defaults.yaml`), holding every setting.
2. **The user file:** `$XDG_CONFIG_HOME/moskophoros/config.yaml`, else
   `~/.config/moskophoros/config.yaml`. It is optional, and is skipped under
   `--no-user-config`.
3. **A loaded sheet:** `--settings-from FILE`, or a sheet loaded in a future
   UI. Every recorded setting that affects the output (D-16), including the
   clip selection and one-shot marks (D-19).
4. **`--config FILE`**, repeatable, later files winning.
5. **Command-line options.**

- Each layer is a partial tree: a key that a layer leaves out falls through
  to the layer below.
- Lists replace rather than merge. Per-clip entries merge by clip name.
- Loading is in memory, for that generation only. The tool never writes the
  user file or any `--config` file (D-15).
- Today's reuse rules carry over unchanged inside the sheet layer. An explicit
  `--view` still replaces the whole reused view, and a reused library still
  stays with its palette (design §Scale and ground point, *Reuse*).

### Files and errors (D-17, P-2)

- Settings files are read through SET-0's strict YAML reader. It allows only
  one document and no repeated keys, and its implicit typing is restricted.
- **Unknown keys are errors**, naming the file, the key path and the line.
- `version: 1` is optional at the top of a user or `--config` file. An unknown
  version is an error.
- **Exit codes:** every settings error is a usage error (exit 2) before any
  Blender invocation, including its version probe. A missing user file is not
  an error; a missing `--config` file is.
- Paths inside a file resolve relative to that file's directory, with a
  leading `~` expanded (P-2).
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
- **Validation (P-2):** distance > 0; samples a whole number from 1 to 1024;
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
- Each frame lasts exactly `1/fps`, and the sheet records the clip's retiming
  factor `d·fps/N`.
- Previews follow the recorded frame durations, as now.

### Recording and loading (D-15, D-16, P-6)

- The sheet's `settings` records every resolved setting that affects the
  output. The capture knobs move there from `generator.shade`, and per-material
  overrides and frame counts are recorded too.
- Where each value came from is never stored.
- **P-6:** each slice that adds recorded settings bumps the sheet schema, as
  `/2` and `/3` did. Older sheets still load, taking the defaults for what they
  lack.
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
  duration and retiming factor.
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
  - the material library path.
- The inventory's other settings follow later, each when it is simple and
  gives value (owner, round 2).
- How this scope splits into pull requests is D-21.

### D-15. A sheet records every setting and loads them as one in-memory layer

Decided by the owner on 2026-10-11, round 6. This resolves Q-5: "yes". It
extends D-8.

- The sheet's `settings` block records every resolved setting, including the
  shading values, per-material overrides and frame counts. The capture knobs
  move from `generator.shade` into `settings`. This is a new sheet schema
  version. Older sheets still load, taking today's defaults for what they
  lack.
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
  the command line, as now.
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

## Open questions

None. The owner's review of this document, with another agent, comes before
readiness (D-21).

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
  - path resolution;
  - errors (D-17);
  - the clip selection from a loaded sheet (D-19);
  - design §CLI, §Option validation, §Scale and ground point (*Reuse*),
    §Reproducibility and §Project layout;
  - the README.
- **Phase:** 1.
- **Depends on:** SET-0.
- **Ordering:** critical path.
- **Relevant decisions:** D-2, D-5, D-8, D-14, D-15, D-16, D-17, D-19, D-21.
- **Acceptance signals:**
  - precedence and error tests;
  - byte identity with no settings files;
  - the reproduction test;
  - tests never read the real user file.
- **Out of scope:** shading values, frames, per-material overrides, and
  schema changes to the sheet.
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
  - reuse of older sheets.
- **Phase:** 2.
- **Depends on:** SET-1.
- **Ordering:** critical path.
- **Relevant decisions:** D-3, D-6, D-9 (global values), D-12, D-15, D-16.
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
    (D-20);
  - capture and stylize changes;
  - design §Material libraries, §Material ramps and §Capture;
  - the amendment to material styling D-7 ("one global range").
- **Phase:** 3.
- **Depends on:** SET-0, SET-2.
- **Ordering:** critical path for per-material control.
- **Relevant decisions:** D-4, D-9, D-15, D-16, D-20.
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
- **Relevant decisions:** D-13, D-14, D-15, D-16, D-17.
- **Acceptance signals:**
  - pure sampling tests for loop, one-shot and `N` = 1;
  - frame duration exactly `1/fps`;
  - the retiming factor recorded;
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
