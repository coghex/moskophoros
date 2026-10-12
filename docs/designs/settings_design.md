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

The slices below are a **proposal** awaiting the owner's signoff (Q-9).

- [ ] EPIC. Configure moskophoros from layered YAML settings and command-line overrides
- [#82] SET-0. Read material libraries from YAML instead of JSON
- [ ] SET-1. Load layered YAML settings for the existing options
- [ ] SET-2. Make the shading constants settings and command-line options
- [ ] SET-3. Add per-material settings
- [ ] SET-4. Recolour shading without a re-render

## Epic contract

- **Goal:** every setting the owner tunes per generation has one name, one
  shipped default and one validation rule. It can be set in the user file, in
  a `--config` file or on the command line, in that order of precedence. Every
  sheet records the values it was made with.
- **Done when:** (proposal) the shading knobs and the settings the owner lists
  under Q-1 can each be set at every layer. The R1 and R2 looks can be
  reproduced from a `--config` file alone, with no code edit. Per-material
  settings work. A sheet reused with `--settings-from` reproduces itself
  whatever the user file says. The owner accepts it (V-12).
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
  `moskophoros --config flat.yaml hero.glb hero.png`, then
  `--convexity-weight 0.3` on top to try a variation.
- **Personal defaults.** `~/.config/moskophoros/config.yaml` holds the owner's
  usual choices, so everyday commands stay short.
- **Shipped defaults are visible.** One defaults file inside the package holds
  every setting's default. It doubles as the reference for what can be set.
- **Per-material control.** Per-material settings live in the same settings
  model (D-4).
- **Reproducible.** A sheet says exactly what made it, and
  `--settings-from` makes it again.
- **A UI later** edits the same settings (D-5).

## Scope

### In scope

- A settings model: names, types, units, defaults and validation.
- The four layers (D-2), their precedence, and how `--settings-from` fits in.
- Shipped defaults as a YAML file in the package.
- Shading knobs as settings and options (D-3).
- Per-material settings (D-4).
- Recording the resolved settings in the sheet.
- The design.md amendments these require, delivered with the implementation
  pull requests.
- Optionally, recolouring shade without a re-render (SET-4, by the owner's
  choice).

### Out of scope

- The UI itself (D-5). Only "do not rule it out" applies.
- Choosing new default values for the look. Today's values stay the defaults
  unless the owner decides otherwise (Q-7).
- Directional light. D-22 and D-25 stand: the knobs tune occlusion and
  curvature only.
- Resolving #78 or #79.
- Free chains of style passes. Saved settings files are requested; a pass
  chain is still deferred (style pass 1 D-7).

## Design

Everything in this section is a **Proposal** unless it cites a `D-N`.

### Settings model (P-1)

- One plain, nested data structure of named values: mappings, lists, strings,
  numbers and booleans, which YAML and JSON can both represent. Each leaf has
  a declared type, unit, default and validation rule, kept in one schema
  table in the code. That table is what a UI would read to build its controls
  (D-5).
- Names are `snake_case`, with the unit in the name where there is one,
  matching the sheet JSON (`ao_distance_m`, `pitch_deg`).
- Sections follow the pipeline stages, for example `view`, `sampling`,
  `scale`, `capture.shade`, `style` and `materials`. The final layout comes
  from Q-1 and the inventory.
- Every command-line option that is a setting maps to exactly one key. Options
  that act on one run only, such as `--work-dir`, `--no-preview` and the input
  and output paths, are proposed to stay command-line only. That is part of
  Q-1.

### Layers and precedence (D-2)

Lowest to highest:

1. **Shipped defaults:** `src/moskophoros/defaults.yaml` (proposed name), read
   as package data. It holds every setting.
2. **The user file:** `~/.config/moskophoros/config.yaml`, optional.
3. **`--config FILE`:** optional and single (Q-6 asks whether it may be
   repeated).
4. **Command-line options.**

Each layer is a partial tree: a key a layer does not mention falls through to
the layer below. Lists replace rather than merge. Proposal for per-material
mappings: merge by material name (Q-3).

Where `--settings-from` sits is open (Q-4). The proposal is shipped defaults
< user file < `--config` < reused sheet < command line. A reused sheet then
reproduces itself whatever the user file says, and explicit options still
override it, as they do today.

### Files and errors (P-2)

- **Safe loading only:** `yaml.safe_load` through a loader that rejects
  duplicate keys, which PyYAML otherwise silently accepts.
- **Strict types**, to blunt YAML 1.1 surprises: a boolean key accepts only
  `true` and `false`, a number key accepts no quoted strings, and `nan` and
  `inf` are refused, as on the command line.
- **Unknown keys are errors**, naming the file, the key path and, where PyYAML
  gives one, the line. This matches the strict `--settings-from` check.
- **Exit codes:** every settings error is a usage error (exit 2) before any
  Blender invocation, including its version probe, as palette and library
  errors already are. A missing user file is not an error; a missing
  `--config` file is.
- **Paths inside a file** (for example a palette or library) resolve relative
  to that file's directory.
- **Schema version:** a top-level `version: 1` key, optional in user and
  `--config` files and present in the shipped defaults. An unknown version is
  a usage error.
- **Tests stay hermetic:** an environment variable or option
  (`--no-user-config`, proposed) keeps tests and scripted runs from reading
  the owner's user file. AGENTS.md already bars tests from reading the owner's
  Blender setup, and this keeps the same rule.

### Recording and reproducibility (P-3; V-2, V-9)

- The sheet records the fully resolved values, never the layers. A sheet made
  with a user file reproduces on a machine without it.
- The shading values already have homes. Capture constants are in
  `generator.shade`, and the range is in `settings.style.shade_range`. Q-5
  asks whether capture knobs move from `generator` to `settings`, since they
  become choices rather than properties of the technique.
- Where each value came from (default, user, `--config`, sheet or command line)
  is not part of the result. It is proposed to go to stderr, or into a separate
  record outside the fingerprint (Q-5), so the same resolved settings still
  give the same bytes.

### Shading knobs (D-3)

| Setting (proposed key) | Option (proposed) | Default (today) | R1 | R2 | Stage |
|---|---|---|---|---|---|
| `capture.shade.ao_distance_m` | `--ao-distance M` | 0.3 | 1.2 | 1.2 | capture |
| `capture.shade.ao_samples` | `--ao-samples N` | 64 | 64 | 64 | capture |
| `capture.shade.occlusion_weight` | `--occlusion-weight W` | 0.25 | 0.5 | 0.5 | capture (stylize with SET-4) |
| `capture.shade.convexity_weight` | `--convexity-weight W` | 1.0 | 0.0 | 0.5 | capture (stylize with SET-4) |
| `style.shade_range` | `--shade-range LO,HI` | [84, 191] | [120, 188] | [120, 255] | stylize |

- The shade formula keeps its meaning: linear
  `clamp(occlusion_weight · AO_out + convexity_weight · (1 − AO_in), 0, 1)`.
  It covers occlusion and curvature only, with no light, direction or material
  property (D-25).
- **AO samples** is proposed as a knob. It trades render time for noise, and
  the sheet already records it.
- **Proposed validation:** distance > 0; samples a whole number from 1 to
  1024; weights finite and ≥ 0; range integers with `0 ≤ lo < hi ≤ 255`, as
  reuse already checks.
- R1 and R2 become two example `--config` files. Whether they ship with the
  package is part of Q-7.
- D-10's range rationale and the fixture's distinct-band guarantee are
  proposed to stay bound to the shipped defaults only. A user who changes the
  knobs owns the resulting bands. Q-7 asks the owner to confirm.

### Per-material settings (D-4)

Open (Q-2, Q-3). Candidate per-material settings, from the evidence:

- the **shade range**, which #79 needs for Grey and Black. This would amend
  material styling D-7, "one global range".
- the **weights**: possible in capture, which already replaces each material's
  shader, or in stylize with SET-4.
- the **ramp**, which today lives in the JSON library.

### Recolouring without a re-render (SET-4, optional)

- Capture would keep occlusion (`AO_out`) and convexity (`1 − AO_in`) as
  separate values per pixel instead of one combined shade. The weights would
  then move from capture to stylize.
- A weight or range change recolours retained buffers without Blender. That
  fits V-4: capture decides nothing about the look.
- The R1/R2 decomposition shows the arithmetic works (feedback-1 §7.1;
  manifest, *Validity*).
- **Costs:**
  - The render's channels are already full (ID in red and blue, shade in
    green), so this needs another output or channel.
  - Combining 8-bit O and C in stylize rounds differently from today's
    single shade, so default output bytes would change.
  - "Recolour a retained capture" is a new kind of run. Today's design gives
    `--work-dir` no replay interface.
- Whether, and when, is the owner's call (Q-8).

## Decisions

All five were made by the owner on 2026-10-11, in the moskophoros manager's
terminal, and relayed in request moskophoros-20261011-1.

### D-1. Settings files are YAML, read with PyYAML

"im just used to yaml, and pyyaml is a pretty good library, so use yaml". The
project pin goes into `pyproject.toml` and `requirements.lock` with the first
implementation pull request (AGENTS.md, Architecture rules). Affects SET-1.

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
a knob (proposed: yes). R1 and R2 are the reference presets:

- R1: AO 1.2 m, occlusion 0.5, convexity 0.0, range 120..188, "more internal
  shading from ambient light";
- R2: AO 1.2 m, occlusion 0.5, convexity 0.5, range 120..255, "more flat".

The knobs do not change D-25's meaning: occlusion and curvature only, with no
light or direction. Affects SET-2.

### D-4. Per-material settings belong in the settings

"per material will definitely be in the settings". What they are and how they
relate to the JSON library is Q-2 and Q-3. Affects SET-3.

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
- Whether each value is global, per material or both is Q-12.

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
- Still open (Q-13): whether the sheet's own description becomes YAML too,
  and how existing `.json` libraries are treated.

Affects SET-0 and SET-3.

### D-8. Precedence: defaults < user file < loaded sheet < `--config` < options

Decided by the owner on 2026-10-11, round 3. This resolves Q-4 and adopts
P-4: "yea, that is fine".

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

## Open questions

### Q-1. Which settings exist, and which stay command-line only?

The owner has "many settings i can think of". The inventory above lists
today's options and tunable constants. Which become settings, which stay
command-line only, and what else does the owner want? This decides the schema
and the slice boundaries. Resolved by the owner's list.

**Owner input, 2026-10-11 (round 2), not yet signed off:**

- The inventory's labels "look good": a setting that is simple to include and
  gives value should be included.
- The first slice is limited to scale, fps, frame count, and "most
  importantly … the two shading dials that i want to control shading, ambient
  (known in my work currently as R1) and soft (R2)".
- "I would allow more if you think it wise."

**Agent view:**

- Keep the first slice small. The loader and the layers are the real work.
  Each extra key costs little code, but it is a schema commitment.
- Worth adding: the cell size, if "scale" means only pixels per meter, and the
  palette and library paths, which every acceptance command so far repeats.
- Still open:
  - what the dials are (Q-10);
  - what frame count means (Q-11);
  - whether scale covers the cell.

**Owner clarification, 2026-10-11 (round 3):**

- "Scale" meant **image size**, the cell (`--cell WxH`). The owner generates
  48×48 today but needs arbitrary sizes.
- The dials are the raw values (D-6).
- The first-slice candidates are now:
  - the cell;
  - fps;
  - frame count (Q-11);
  - the raw shading values.
- The agent's suggestion to add the palette and library paths is unanswered.

### Q-2. What are the per-material settings?

Candidates are the shade range (#79; this would amend material styling D-7),
the occlusion and convexity weights, and the ramp. Anything else? Resolved by
the owner.

**Owner input, 2026-10-11 (round 2), not yet signed off:**

- "All of the shading stuff needs per material values as well, im not sure
  what all i want."
- For a first slice: a per-material shade range (min and max), with the
  materials defined in YAML.

A per-material range amends material styling D-7 ("one global range"), so it
needs its own explicit signoff. Per-material weights and AO distance come
later, and stay deliberately open until the owner decides what they want.
Weights and distance act in capture, where each material's shader is already
replaced, or in stylize with SET-4.

### Q-3. How do per-material settings relate to the JSON material library?

- **(a) Merge:** YAML settings gain a `materials:` section keyed by material
  name, and the library keeps the ramps. Two files speak about one material.
- **(b) Replace:** the library moves into the YAML settings. A
  `moskophoros.materials/1` JSON file stays readable or gets converted.
- **(c) Reference:** the settings name a library file, and per-material
  settings go into the library, under a new library schema version.

Each affects reuse, the sheet record (D-19) and validation against the
palette. Resolved by the owner.

**Owner input, 2026-10-11 (round 2), not yet signed off:**

- "I didnt realize i was already using json, ideally i would want everything
  in yaml if possible."
- The YAML library may be gated on an earlier issue that moves the library to
  YAML first.
- Still open:
  - whether the library becomes part of the settings model, or a separate
    YAML file;
  - whether existing JSON libraries stay readable.
- The sheet's description stays JSON: vision V-2 fixes "a JSON description
  beside it". The agent's reading, to confirm, is that "everything" means the
  files the owner writes.

### Q-4. Where does `--settings-from` sit among the layers?

**Resolved by D-8.**

The proposal is above `--config`, below the command line, so a reused sheet
ignores the user file and `--config`. Alternatives: below the user file, or
not combinable with `--config` at all. Resolved by the owner.

**Owner input, 2026-10-11 (round 2), not yet signed off.** A later UI will
"load up a sprite, see its current sheet and all of the settings used in its
generation get loaded in to the parameters automatically". Loading a sheet
takes preference over all settings. From the command line, "even without
explicit options", the config file settings should still override the sheet,
"i suppose, but you tell me".

**Agent view.** The sheet's JSON `settings` is already that metadata. It must
grow to hold every setting, including the shading knobs (Q-5). Letting the
implicit user file override a reused sheet has two costs:

- A reused sheet would silently take today's preferences, so it would no
  longer reproduce itself (V-2).
- A user file that sets the scale would refit sprites that were meant to keep
  their size across exports (V-7, stable scale).

**Proposal P-4.** The same order applies in the UI and on the command line:
shipped defaults < user file < loaded sheet < `--config` files < command-line
options. Under P-4:

- Your everyday user file never changes a reused sheet.
- A `--config` file you name on that command line counts as explicit, so it
  does.

### Q-5. What does the sheet record?

- Do the capture knobs move from `generator.shade` into `settings`, since
  they become choices?
- Is provenance (which layer set each value) recorded, and if so, outside the
  fingerprint? Recording it inside would make identical settings from
  different files give different bytes (V-2).

This affects the sheet schema version (`/4`) and reuse of `/3` sheets.
Resolved by the owner.

The owner's round-2 answer to Q-4 bears on this question: loading a sheet must
restore every setting. Reuse today reads only `settings`, never `generator`
(`cli.py:356–432`), so the shading knobs would not be restored from
`generator.shade`. Moving them into `settings` follows from that need. That
move is part of Q-5's signoff.

### Q-6. Schema details

May `--config` be repeated, with later files winning? Should a generic
`--set key.path=value` option reach settings without a dedicated flag? Should
the user file's location follow `$XDG_CONFIG_HOME`, or be fixed? And confirm
the error, unknown-key and versioning proposals in P-2. Resolved by the owner.

### Q-7. Defaults, presets and the bound guarantees

- Do today's values stay the shipped defaults, or does R1 or R2 become the
  default?
- Do R1 and R2 ship as example files?
- Do D-10's range rationale and the fixture's distinct-band guarantee stay
  bound to the defaults only?

Resolved by the owner.

### Q-12. Global, per material, or both?

The owner: "i guess these would be per material, maybe we dont need a global,
you tell me."

**Agent recommendation:**

- Each of the four values has a global default, and any material may override
  any of them.
- AO samples is global only, if it is a setting at all.

Reasons:

- Without a global value, every material entry repeats all four values, and
  a model with an unlisted material has none.
- A global value is what the defaults file and `--config` naturally hold.
- It mirrors the library's existing default ramp.

Weights and AO distance act in capture, per material shader. The range acts in
stylize. **Resolved by D-9.**

### Q-13. What else does "everything yaml" cover?

- Does the sheet's description (`hero.json`) become YAML? Vision V-2 fixes a
  JSON description, the sheet is read by programs, and `--settings-from`
  reads it. The agent recommends it stays JSON.
- Are existing `.json` libraries refused with a hint to convert them, or still
  read?

**Resolved by D-10 and D-11.**

### Q-10. What are the "ambient" and "soft" shading dials?

**Resolved by D-6:** raw values now, named presets later.

The owner calls them "the two shading dials … ambient (known in my work
currently as R1) and soft (R2)". R1 and R2 are each a full set of four values,
and they differ in convexity weight (0 against 0.5) and in the top of the range
(188 against 255). Three readings:

- **(a) Two named presets:** for example `--shading ambient` or
  `--shading soft`, carrying the R1 and R2 values. The raw knobs (D-3) are
  still settable underneath, as `--pitch` is under `--view`.
- **(b) Two continuous dials:** `ambient` and `soft`, each a number. A formula,
  still to be designed, turns them into the raw knobs.
- **(c) Raw knobs only:** shipped example files `ambient.yaml` and `soft.yaml`.

Resolved by the owner.

### Q-11. What is "frame count"?

No frame-count option exists today: a clip gets
`max(1, floor(duration · fps + 0.5))` samples, plus one for a one-shot
(design §Clips and sampling). Readings:

- a fixed number of frames per clip, used instead of fps;
- a cap on frames per clip, on top of fps;
- either of those set per clip.

Resolved by the owner.

**Owner input, 2026-10-11 (round 5):** "when i think about an animation, its
frame count, and fps, with the total duration being determined by those two
characteristics, but this doesnt really work with blender does it? if it does
then thats what i want, if not, then just fps is fine, the important thing is
that we can generate animations of arbitrary fps and length."

**Verified facts** (design §Clips and sampling):

- A clip's authored length `d` comes from the model: its glTF keyframe
  range, `t1 − t0`.
- The tool chooses its own sample times, and Blender evaluates each at its
  exact time, not on a timeline frame. So the tool is not bound to the
  timeline grid or the authored frame rate.
- Today the output always plays at the authored speed. `n` frames are spaced
  `d/n` apart, and each lasts `d/n`, so `fps` only picks `n`.

**Agent analysis.** The owner's model works. With a frame count `N` and an
fps `F`:

- sample `N` poses evenly over the authored motion, at `t0 + k·d/N`;
- give each frame `1/F`.

The clip then plays for `N/F` seconds. When that differs from `d`, the motion
is retimed: played faster or slower than authored, by the factor `d·F/N`. A
loop still closes seamlessly, because the samples cover the whole cycle.
Nothing in Blender has to change, and the model need not be re-exported to
change the length.

**Proposal P-5:**

- `fps` stays a global setting.
- A per-clip `frames` setting is optional.
- Without `frames`, today's behaviour holds exactly, so existing sheets
  reproduce.
- With `frames`, the clip is sampled as above, and the sheet records its
  frame duration (`1/F`) and its retiming factor.

Still open:

- whether `frames` is per clip, global, or both;
- whether a one-shot's `N` includes its final pose (today it adds one).

Amends design §Clips and sampling.

### Q-8. Recolouring without a re-render: a slice, a deferral, or dropped?

See SET-4 above. Resolved by the owner.

### Q-9. Delivery order and slice boundaries

Is the proposed SET-1 to SET-4 order right? In particular, may SET-2 land
before SET-3, and is SET-4 in this arc? Resolved by the owner, after Q-1 to
Q-8.

## Verification strategy

Proposal:

- **Pure tests**, needing no Blender or filesystem, for layer merging,
  precedence, validation, unknown keys, duplicate keys, YAML type traps and
  error messages.
- **Command tests** with temporary user and `--config` files: precedence,
  exit 2 before any Blender invocation, and hermetic runs that never read the
  owner's real user file.
- **Byte identity:** with no user file, no `--config` and no new options,
  every sheet, JSON and preview is byte-identical to today's, apart from
  whatever Q-5 changes in the JSON.
- **Blender tests** for the shading knobs: non-default weights and distance
  reach the shade buffer and the sheet record. The fixture's distinct-band
  check stays bound to the defaults (Q-7).
- **Owner acceptance:** reproduce R1 and R2 from `--config` files and compare
  them byte for byte with the manifest's recorded sheets
  (`R1/RobotExpressive.png` d69bf461…, `R2/RobotExpressive.png` 59d0a37c…).
  The owner then judges a fresh variation by eye (V-12).

## Delivery plan

**Proposal**, pending Q-1 to Q-9. Every slice amends design.md in its own pull
request, because tests read design.md.

### SET-0. Read material libraries from YAML instead of JSON

- **Outcome:** `--materials FILE` reads a YAML library with the same fields
  and validation as today, through a strict YAML reader the settings loader
  will reuse. The owner asked for its issue to be drafted first (D-7).
- **Scope:** the strict reader; the PyYAML pin; the library reader; tests;
  the design §CLI and §Material libraries amendments; the README.
- **Phase:** 0.
- **Depends on:** none.
- **Ordering:** can land first.
- **Relevant decisions:** D-1, D-7.
- **Acceptance signals:** the same library content in YAML gives the same
  `Library`, and byte-identical sheet PNGs and previews. YAML 1.1 traps,
  duplicate keys and multiple documents are refused with named errors before
  Blender starts.
- **Out of scope:**
  - per-material shading fields (SET-3);
  - the settings loader (SET-1);
  - the sheet's format;
  - palette formats.
- **Relevant decisions (added):** D-10, D-11. The owner approved the issue
  draft on 2026-10-11.
- **Open questions:** None.

### SET-1. Load layered YAML settings for the existing options

- **Outcome:** shipped defaults, the user file and `--config` are loaded,
  validated and merged under the command line. Every existing option chosen
  under Q-1 is a setting, and the sheet records the resolved values.
- **Scope:** the settings schema and loader; the PyYAML pin; hermetic test
  support; design §CLI, §Option validation and §Reproducibility amendments.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-2, D-5.
- **Acceptance signals:** precedence and error tests; byte identity with no
  settings files.
- **Out of scope:** new knobs; per-material settings.
- **Open questions:** Q-1, Q-4, Q-5, Q-6.

### SET-2. Make the shading constants settings and command-line options

- **Outcome:** AO distance, AO samples, occlusion and convexity weights and
  the shade range are settings and options. R1 and R2 can be reproduced from
  `--config` files.
- **Scope:** the capture job carries the knobs; `blender_script.py` reads them
  instead of `SHADE`; the range default comes from the settings; design
  §Capture and §Export amendments; the overridden "no command option sets the
  shade range" rule.
- **Phase:** 2.
- **Depends on:** SET-1.
- **Ordering:** critical path.
- **Relevant decisions:** D-3, D-5.
- **Acceptance signals:** Blender tests for non-default knobs; R1/R2
  reproduction.
- **Out of scope:** per-material values; recolouring without a re-render.
- **Open questions:** Q-5, Q-7.

### SET-3. Add per-material settings

- **Outcome:** per-material settings as decided under Q-2 and Q-3.
- **Scope:** to be settled.
- **Phase:** 3.
- **Depends on:** SET-1; SET-2 if per-material shading values are chosen.
- **Ordering:** not on the critical path for the shading knobs.
- **Relevant decisions:** D-4.
- **Acceptance signals:** to be settled.
- **Out of scope:** generated ramps (MAT-8).
- **Open questions:** Q-2, Q-3.

### SET-4. Recolour shading without a re-render

- **Outcome:** capture keeps occlusion and convexity separately, so weight and
  range changes need no Blender run.
- **Scope:** to be settled; possibly a spike first.
- **Phase:** 4.
- **Depends on:** SET-2.
- **Ordering:** not on the critical path.
- **Relevant decisions:** D-3.
- **Acceptance signals:** to be settled.
- **Out of scope:** to be settled.
- **Open questions:** Q-8, deliberately open.
