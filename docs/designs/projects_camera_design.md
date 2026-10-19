# Projects and camera design

Moskophoros serves more than one of the owner's projects, each with its own
look. Today a run's rendering settings are spread over the user file, `--config`
files and command-line-only options, and the camera is one fixed
orthographic camera with a pitch. This design makes rendering settings belong
to a project, leaves a thin file for the app's own settings, and turns the
view into a camera the owner can place and point, orthographic or
perspective, as settings and as options.

It is the first of two designs the owner asked to settle before more renders.
The shading design (baked light) follows it (request moskophoros-20261019-5).

Design state: `ready for issue processing`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [ ] EPIC. Projects and a free camera
- [ ] CAM-1. Add projects and a single global settings file
- [ ] CAM-2. Make the view, scale and framing settings-file settings
- [ ] CAM-3. Point the orthographic camera with a direction and roll
- [ ] CAM-4. Add the perspective projection
- [ ] CAM-5. Owner review of projects and the camera

## Epic contract

- **Goal:** each project's rendering look lives in its own settings file, and
  its view is a camera with a position, a direction and a projection, set in
  that file or on the command line.
- **Done when:** CAM-1 to CAM-4 are merged; commands whose resolved settings are unchanged keep their sheet, map and preview bytes (D-14, D-17); and the owner has accepted the CAM-5 review.
- **Users and operators:** the owner, rendering sprites for each project from
  that project's settings file; later, a GUI over the same settings.
- **Arc label:** `None proposed`.

## Current state and evidence

Read from master `ed8ae0a228` (`docs/design.md`, `src/moskophoros/`).

**Settings.**
- Layers, lowest first (design §Settings files):
  1. the shipped defaults (`defaults.yaml`);
  2. the user file, `~/.config/moskophoros/config.yaml`;
  3. a loaded sheet (`--settings-from`);
  4. `--config` files;
  5. options.
- **What a settings file can set:** the cell, `fps`, frames, per-clip frames, the palette, the material library, `edges`, previews, the normal and depth maps, the preview light, the shading values and the ramp formula.
- **What only an option or a loaded sheet can set:** the view (`--view`, `--pitch`, `--directions`, `--start-angle`), `--model-yaw`, `--ppm`, `--ground`, `--ground-px`, `--supersample`, `--reduce` and `--root-motion`. Settings design §Merge rules item 9 left the view out of the first scope, "designed then".
- **App-like options**, which are not rendering settings: `--blender`, `--any-blender`, `--work-dir` and `--no-user-config`.
- **The owner's files, already split by the manager on the owner's word (2026-10-19):**
  - `~/.config/moskophoros/synarchy.yaml` holds every rendering setting: palette `palettes/synarchy.gpl`, `edges`, normals, depth, previews, the preview light, the shading and the ramp formula. It notes that the view and scale cannot be set there yet.
  - `config.yaml` holds only `version: 1` and a note that app settings will come from this design.

**Camera** (design §Camera and directions, §Presets; `views.py`, `capture/blender_script.py` `place_camera`).
- **Projection:** orthographic only. The sheet records `projection: orthographic`, and a reused sheet must say so. Perspective is listed under design §Deferred: "A view needs it".
- **The camera never moves; the subject turns.**
  - The camera looks at the ground point from `(0, sin p, cos p)`, with screen right +X and no roll.
  - Pitch `p` is a float from 0 to 90 inclusive; `--pitch` already accepts any value.
  - Each direction turns the subject by `θᵢ = start + i·360/N` (plus `--model-yaw`) about the vertical axis through the ground point.
  - In the Blender script, the camera turns around the subject instead, which gives the same image because the colour is unlit.
- **Presets:** `topdown` (90°, 8 directions), `side` (0°, 2 directions, starting at 90°), `iso` (30°, 8) and `iso-true` (35.264°, 8). Explicit values override them, and the preset is then recorded as `custom`.
  - 30° is exactly the 2:1 projection: a square cell at 45° projects to a diamond twice as wide as tall.
- **A camera yaw has no visible effect in this model.** Direction angles are measured on screen and the subject turns, so turning the camera about the vertical axis would only change which direction `start-angle` names.

**Scale and framing** (design §Scale and ground point).
- **Scale and framing:** pixels per meter (`--ppm`), the cell, the ground point (subject meters) and the ground pixel together fix scale and framing.
- **Fitting:** auto-fit and `--ppm`-only sizing fit the subject's projected extents over every sample, with a 1-pixel margin. Overflow is exit 4.
- **The maps' units assume orthographic:**
  - the depth map is in sheet pixels along the viewing axis from the ground point;
  - the preview light's position is in sheet pixels from the ground point, fixed to the camera.

**Sheets.**
- **Schema:** `moskophoros.sheet/13`. Only the current schema loads (settings design D-24, the owner: "just dont support old formats"), and alpha design D-5 says existing sheets need not be preserved.
- **View record:** `settings.view` records `preset`, `projection`, `pitch_deg`, `directions` and `start_angle_deg`.

**Tracker:** no open arc overlaps. The one open issue, #43, is about animation.

## Desired experience

The owner's two projects, as the owner described them:

- **Synarchy** (and its rewrite, Hetoimasia):
  - high-angle 2:1 isometric, 8 directions;
  - flat colour with ambient ramps;
  - normal and depth maps for live lighting.
- **Codekarl:** "a 2d top down map game … procedurally generated … moskophoros is going to be used for me to generate 2d art panels to accompany text to the player".
  - Seen straight on, with baked lighting.
  - Baked lighting belongs to the shading design.

The owner picks a project and renders. Everything that decides the look comes
from that project's file. Moving or re-pointing the camera, or switching to
perspective, is a setting or an option like any other. The names Synarchy
and Codekarl live only in the owner's own files, never in code, tests or
shipped defaults (V-1).

## Scope

### In scope

- project settings files and a separate app settings file;
- the camera: position, direction, projection;
- pitch as a float setting;
- scale and framing as settings;
- recording all of these in the sheet, and reusing them.

### Out of scope

- baked light and shading modes (the shading design);
- the Codekarl palette and its settings file (after the shading design);
- the GUI (later; this design only keeps its settings plain);
- reading or touching the Codekarl repository.

## Design

This is assembled from D-1 to D-16. The details marked **(D-16)** were the
worker's proposals, which the owner signed off with the whole design.

### Files and layers (D-1, D-9, D-11)

**The files.**
- **The global file:** `$XDG_CONFIG_HOME/moskophoros/config.yaml`, else `~/.config/moskophoros/config.yaml`, as today, or the one file given with `--config FILE`.
  - It is the default project. A missing default global file is not an error; a missing `--config` file is.
  - `--no-user-config` uses none, and cannot be given with `--config`.
- **A project file:** `projects/NAME.yaml` in the configuration directory, chosen with `--project NAME`. That directory is `$XDG_CONFIG_HOME/moskophoros/` when the variable is set and not empty, else `~/.config/moskophoros/`, the same rule as the default global file. `--config FILE` and `--no-user-config` never move it.
  - A missing one is a usage error naming its path. The tool never creates the folder or any file.
  - **(D-16)** `NAME` is a plain file name: letters, digits, `.`, `_` and `-`, not starting with `.`, and without `.yaml`. Anything else is a usage error, so `--project ../x` cannot reach outside the folder.
- **One schema.** Both kinds of file take every setting (the settings table below, today's table included). They are read by today's strict reader with today's errors, and paths inside them resolve relative to the file.

**The layers, weakest first:** shipped defaults < the global file < a loaded sheet (`--settings-from`) < the project file < the flags.
- A value from the global file or the shipped defaults is a default, and a loaded sheet sits above it, exactly as the user file does today.
- A project file's values act as explicit values do over a loaded sheet, exactly as a `--config` file's do today: a project's palette follows the reuse table, for example.

**What the sheet records.**
- Every resolved rendering setting, never the project's name or the settings files' names (D-9).
- Palette and library sources stay recorded by base file name, as today.
- **(D-16)** App settings are not recorded and are never loaded from a sheet.

### New settings (D-12)

Each is validated exactly as its option is. The schema table in `settings.py` and the packaged `defaults.yaml` gain these rows, and a test keeps the two in agreement, as today.

| Setting | Option | Shipped default | Value |
|---|---|---|---|
| `view` | `--view NAME` | `iso` | a preset name; a shorthand (below) |
| `pitch` | `--pitch DEG` | `null` | 0 to 90, or `null`; a shorthand for `camera.direction` |
| `directions` | `--directions N` | `null` | 1 to 64, or `null` |
| `start_angle` | `--start-angle DEG` | `null` | degrees, or `null` |
| `model_yaw` | `--model-yaw DEG` | `0` | degrees |
| `camera.projection` | `--projection NAME` **(D-16)** | `orthographic` | `orthographic` or `perspective` |
| `camera.direction` | `--camera-direction X,Y,Z` **(D-16)** | `null` | three numbers, each −1 to +1, not all 0, or `null` |
| `camera.roll` | `--camera-roll R` **(D-16)** | `0` | −1 to +1, a fraction of a half turn |
| `camera.position` | `--camera-position X,Y,Z` **(D-16)** | `null` | meters from the ground point, or `null` |
| `ppm` | `--ppm N` | `auto` | greater than 0, or `auto` (the option accepts `auto` too) |
| `ground` | `--ground X,Y,Z` | `[0, 0, 0]` | meters, subject coordinates |
| `ground_px` | `--ground-px X,Y` | `auto` | a cell pixel corner, or `auto` (the option accepts `auto` too) |
| `supersample` | `--supersample N` | `8` | 1 to 16 |
| `reduce` | `--reduce NAME` | `plain` | `plain` or `mode` |
| `root_motion` | `--root-motion MODE` | `error` | `error` or `keep` |
| `blender` | `--blender PATH` | `null` | an executable path, or `null` to discover it as today; app setting |
| `any_blender` | `--any-blender` | `false` | `true` or `false`; app setting |

**Absent, `null` and `auto`** (review 1, C-6). In a file, a key that is left out is not set by that layer.

- **`null`** for `pitch`, `directions`, `start_angle` or `camera.direction` is an explicit value meaning "take it from the `view` in force". It clears a lower layer's override of that value.
- **`auto`** for `ppm` or `ground_px` means automatic fitting. It clears a reused or lower value, as `cell: auto` does today, and `--ppm auto` and `--ground-px auto` become option syntax (CAM-2).
- **`blender: null`** discovers Blender as today.
- **The shipped `defaults.yaml`,** literally, for these keys:

```yaml
view: iso
pitch: null
directions: null
start_angle: null
model_yaw: 0
camera:
  projection: orthographic
  direction: null
  roll: 0
  position: null
ppm: auto
ground: [0, 0, 0]
ground_px: auto
supersample: 8
reduce: plain
root_motion: error
blender: null
any_blender: false
```

`--any-blender` sets `true`, and only a file can set `false`. Every value is type-strict and finite, and every error names the file, the key and the line, as today.

**Shorthands (D-16, following settings design §Merge rules item 9).**
- **Within one layer:**
  - a `view` sets the direction, the direction count and the start angle, as `--view` does today;
  - a `pitch` sets the direction to `(0, −sin p, −cos p)`;
  - giving both a `pitch` and a `camera.direction` in the same layer, or on the command line, is a usage error (D-12).
- **Across layers, the higher layer wins** whichever form it used: a project's `camera.direction` replaces a global `pitch`, and a project's `view` replaces a global `camera.direction`, direction count and start angle.
- **Explicit values** of `pitch`, `directions`, `start_angle` or `camera.direction` over a preset make the recorded preset `custom`, as today.
- **How they resolve** (review 1, C-6; review 2, C-9). The view is one state:
  - a preset marker `P`: one of the four presets, or `custom`;
  - three values: the direction `V`, the direction count `N` and the start angle `S`;
  - and, for each value, whether it is the preset's or an override.

  `pitch` and `camera.direction` are two spellings of one logical key, the direction. The layers apply from the weakest up:
  - **The shipped defaults** set `P = iso`, with every value the preset's.
  - **A loaded sheet is a snapshot,** not shorthand input. It sets `P` to its recorded marker, which may be `custom`, and `V`, `N` and `S` to its recorded values, each counted as the preset's. So a reloaded `iso` sheet stays `iso`, and a `custom` one stays `custom`.
  - **A layer's concrete `view`** sets `P` to that preset and every value to the preset's. It applies before the rest of the same layer.
  - **A layer's non-null `pitch` or `camera.direction`** sets `V`, and a non-null `directions` or `start_angle` sets its value. Each is then an override.
    - Giving both `pitch` and `camera.direction` in one layer, with any values, `null` included, is a usage error (D-12). So the alias never depends on key order.
  - **A layer's `null`** for the direction, `directions` or `start_angle` resets that value to `P`'s and counts it as the preset's.
    - When `P` is `custom`, there is no preset to reset to. A `null` is then a usage error naming the key, unless the same layer gives a concrete `view`.
  - **After the last layer,** the recorded marker is `P` when every value is the preset's, else `custom`.
  - **Worked cases:**
    - a lower `pitch: 45` and a higher `camera.direction: null` give the preset's direction;
    - a `custom` sheet with a higher `directions: null` is an error, while `view: iso` with `directions: null` in the same layer is `iso`;
    - an `iso` sheet reloaded with nothing above it records `iso`, and its JSON and fingerprint are unchanged.

### The camera (D-3, D-7, D-8, D-10)

**Basis.** Let `f` be the normalised `camera.direction`, in subject (glTF) coordinates.
- **Unrolled axes:** `r₀ = normalise(f × Y)` and `u₀ = r₀ × f`. When `f`'s horizontal part is exactly zero, so it looks straight down or up, `r₀ = +X`.
- **Roll** turns them about `f` by `ρ = roll · π` radians, giving the screen axes `r` (right) and `u` (up). **(D-16)** A positive roll turns the camera counter-clockwise as it looks, so the picture turns clockwise:
  - `r = r₀·cos ρ + u₀·sin ρ`;
  - `u = u₀·cos ρ − r₀·sin ρ`.

  For example, at `roll = 0.5`, `r = u₀` and `u = −r₀`: a point that was at the top of the picture is now at its right.
- **Where each is used** (review 2, C-10): `r` and `u`, the rolled axes, are used everywhere the picture is made: the render transform, the orthographic framing, the perspective camera space, fitting and lens shift. Only the reference heading for `θ` uses `f` alone, and the unrolled axes appear nowhere else.
- **Today's camera follows:** for `pitch` p and roll 0, `f = (0, −sin p, −cos p)` gives `r = +X` and `u = (0, cos p, −sin p)`.

**Directions** (D-8, D-10). Each direction turns the subject by `θᵢ + model_yaw` about the vertical axis through the ground point.
- `θ` is measured from the camera's unrolled reference heading: at `θ = 0` the subject's +Z faces the camera's horizontal heading, `−(f_x, 0, f_z)`, or +Z when the camera looks straight down or up.
- **Labels come from `θ` alone** (D-18): `south` is 0°, `east` 90°, and so on, as today. Their screen-relative description holds for downward or level cameras with no roll. The light stays fixed to the camera.
- **A half-turn roll** (`roll = 1`): the picture is upside down, so `east` (90°), which faces +X, faces screen left. It keeps the name `east`.
- **A camera looking straight up,** `f = (0, 1, 0)`: `r = +X` and `u = (0, 0, 1)`, so `south` (0°), facing +Z, faces up the screen. It keeps the name `south`.
- In orthographic, the direction's heading changes nothing in the picture.

**Orthographic.**
- The image comes from `f`, the roll, the scale, the cell, the ground point and the ground pixel, as today.
- `camera.position` is ignored. **(D-16)** It is recorded as given, with no warning.

**Perspective** (spikes 1 and 2).
- **Placement:** the camera stands at the ground point plus `camera.position` and looks along `f`.
- **Camera space:** a point `p`, after the subject's turn for its direction about the ground point, has `x_c = (p − c)·r`, `y_c = (p − c)·u` and depth `z_c = (p − c)·f`, where `c` is the camera's position.
  - The ground point's own are `(x_g, y_g, d)`, with `d = −position · f`.
  - **(D-16)** `d` must be greater than 0, or it is a usage error, checked before Blender runs.
- **Projection, relative to the ground point** (review 1, C-1). A point lands at sheet position `(gx + ppm·X, gy − ppm·Y)`, where:
  - `X = d·x_c/z_c − x_g`;
  - `Y = d·y_c/z_c − y_g`.

  So the ground point projects to `(0, 0)`, and `ppm` holds for a surface at the ground point's depth (D-12).
- **Fitting** uses today's quantities: `L = max(0, −min X)`, `R = max(0, max X)`, `U = max(0, max Y)` and `D = max(0, −min Y)`, over every evaluated vertex of every sample, clip and direction. They are independent of `ppm`, so today's three fitting cases and overflow check apply unchanged.
- **Calibration** (review 1, C-4; spike 2). Blender renders the supersampled frame, `W × H` image pixels, with `s` the supersample factor.
  - **Focal length:** `ppm·d·s` image pixels. The sensor fit is horizontal, so `lens / sensor_width = ppm·d·s / W`. When that ratio times 36 is at least 1, the sensor is 36 mm and the lens is `36·ratio` mm. Otherwise the lens is 1 mm and the sensor is `1/ratio` mm. Both stay at or above Blender's 1 mm minimum, so no value is clamped.
  - **Lens shift:** `shift = (offset of the ground point's unshifted projection from its target pixel corner) / W`, horizontally and vertically, in units of the image **width** (the sensor-fit side), for portrait as well as landscape images.
  - **Spike 2 confirmed this:** with the projection above, portrait, landscape and supersampled rectangles and the widened-sensor case all rendered exactly the predicted pixels.
  - **The script reads back** the stored lens, sensor and shift, and refuses (a script error, exit 5) a stored ratio or shift more than 1e-6 relative away from the one asked for.
- **Too near to project** (review 1, C-4 and C-5).
  - A vertex with `z_c ≤ 1e-4` m, at, behind or too near the camera to clip, is an overflow (exit 4). It names the source file, the clip, the direction, the sample time and the nearest depth, and nothing is rendered or published.
  - **(D-16)** item 6's `z_c ≤ 0` is the main case; the margin keeps the near plane representable.
- **Clipping** (C-4, C-5).
  - **Near plane:** half the nearest measured vertex depth.
  - **Far plane:** twice the farthest, plus 1 m.
  - Rendered surfaces are triangles between measured vertices, so their depths lie within the measured range.
  - Both values reach the render job from the caller, which computes them from the measure results over all frames.
  - The script reads back the stored planes and refuses (exit 5) any that would not enclose the measured range.
- **The capture protocol** (C-5; review 2, C-12). Under perspective, each measure result frame gains `depth_m`, the nearest and farthest `z_c` of its vertices. The existing keys keep their names.
  - **A frame with a vertex too near to project** carries `bounds_m: null` beside its `depth_m`, and keeps its `address` and `height_m`. The launcher accepts a `null` `bounds_m` only under perspective with `depth_m[0] ≤ 1e-4`, and the caller turns it into the overflow above. For example:

    ```json
    {"address": {…}, "bounds_m": [0.41, 0.38, 1.12, 0.05], "height_m": 0.0, "depth_m": [2.71, 3.96]}
    {"address": {…}, "bounds_m": null, "height_m": 0.0, "depth_m": [-0.20, 3.10]}
    ```
  - **Any other missing, non-finite or mismatched value** stays malformed output, exit 5.
  - **Schemas:** the job schema moves to `moskophoros.capture-job/3` and the result schema to `moskophoros.capture-result/4` in CAM-4. CAM-3 moves the job to `/2` for the orthographic camera record.
- **The maps** (D-13).
  - The normal map stays in the camera's space.
  - The depth map's value is `(d − z_c)·ppm` sheet pixels, toward the viewer, at the ground point's scale, with today's encoding and range.
  - The lit preview lights each pixel from its pixel-centre screen position and its encoded depth, the 2D way, and does not reconstruct the 3D position. Design §Export's account of reconstructing a position is qualified accordingly.

### Sheets (D-14)

The schema, the `camera` record, dropping `pitch_deg`, and refusing `/13` are decided (D-14). The field layout below is decided by D-16.

- **A new sheet schema,** `moskophoros.sheet/14`.
- **`settings.view`** keeps `preset`, `directions` and `start_angle_deg`.
- **A new `settings.camera`** records:
  - `projection`;
  - `direction`, normalised;
  - `roll`;
  - `position`, three numbers or `null`.
- **The new settings** (`ppm`, `ground`, `ground_px`, `supersample`, `reduce`, `root_motion`, `model_yaw`) are recorded where they are today.
- **`pitch_deg`** is no longer recorded, since the direction holds it.
- **Reuse:** `--settings-from` loads `/14` only, and `/13` sheets stop loading (settings D-24).

## Decisions

The owner gave these in the moskophoros manager's terminal on 2026-10-19. The manager relayed them verbatim in the dispatch for request moskophoros-20261019-6 (`dispatch-projects-camera-design.md`, SHA-256 `0811d38767eb484ac5ede73e87ef246283660ecc37ffc937c1dd9cc8a0207250`, delivered by cmux message `8890a701-b169-4f42-9842-e077b28e3d91`).

### D-1. Rendering settings belong to projects; a thin app settings file

> "i think it would be wise to move the palette and shading to the project settings files then have a master settings file to handle more app related settings, does that make sense? eventually i will build a gui for this, and the global settings should be mostly that, the actual rendering settings should all be project specific. the palette too is going to be very different"

- Each project has its own settings file holding its rendering settings, palette included.
- A separate file holds app settings.
- The manager has already arranged the owner's files this way with today's tool (see *Current state*).

### D-2. The view is several settings; the camera can be moved and pointed

> "i need to cover the view, i want to do this with multiple settings, we shuold be able to move the camera around, and point it in whatever direction we want."

### D-3. The camera: position, direction and projection, as settings and options

> "i want a dynamic system to cover all the bases, so camera position, direction, and perpective. in some perspectives, that would make orthographic views ignore some of these settings, but that is fine. these should be captured in settings and as command line flags. position should be three values, direction should be three values, perspective should juse be orthographic and perspective, we can skip any others i think"

- **Position:** three values.
- **Direction:** three values; their form is Q-1.
- **Projection:** `orthographic` or `perspective`, nothing else.
- **Settings and options:** each is a settings-file setting and a command-line option.
- **Orthographic ignores what it cannot use,** which the owner accepts.

### D-4. Pitch is a float setting

> "synarchy uses a 2:1 isometric projection, and i think other projects could use different angles, so it should be a float setting."

`--pitch` already takes any value from 0 to 90 as an option. What is new is that pitch becomes a settings-file setting.

### D-5. Scale is a setting; new settings are welcome

> "yea, scale is probably something i should have, the settings arent set in stone, so dont be afraid to propose new settings."

### D-6. Two projects to serve, and the tool belongs to neither

- **Synarchy:** high-angle 2:1 isometric, 8 directions, flat with ambient ramps, normal and depth maps.
- **Codekarl:** straight-on art panels with baked lighting.
- V-1 holds: no game names in code, tests or shipped defaults. Project names live only in the owner's own files.

### D-7. The camera's direction is a vector, with a separate roll

The owner answered questions batch 1 (`questions-1.md`, SHA-256 `933331f24830df7a25ee5eb28702373f1b0e2573ff95be80028d0669a97de7d2`) and the manager's follow-ups, typed in the manager's terminal on 2026-10-19. The manager relayed them verbatim in `relay-camera-batch1.md` (SHA-256 `61119c8213288c1866d9d0d6442381b8e27523c3a2c9afd71b29eaaa6eaf4fbd`), delivered by cmux message `bbba403e-cdfe-496c-8ae3-b473c9b871e6`. D-7 to D-9 are recorded from it. This resolves Q-1's direction; the position's origin stays open as Q-8.

> "1) i mean, why is a vector hard, i was thinking a vector makes much more sense, with float values from -1 to +1 for each (x,y,z), the angle makes less sense to me, but i think what i would like to use is the one that requires the least conversion to what blender needs, so whichever option requires the least amount of processing is what i want."

After the manager pointed out that a vector cannot express roll:

> "1) oh roll, that would be a fourth option i hadnt considered, ok i have decided, here is what i want: vector and roll. roll can be -1 to +1 then we multiply by pi radians then convert to degrees for blender, does that sound right?"

- **Direction:** three floats `x, y, z`, each from −1 to +1, in subject (glTF) coordinates. It is the way the camera looks. The tool normalises it, so only its direction matters.
- **Roll:** one float from −1 to +1, a fraction of a half turn: the camera turns by `roll · π` radians about its viewing axis. The manager told the owner that Blender's Python API takes radians directly, so nothing converts to degrees; the recorded intent is `roll × π` radians. Roll −1 and +1 give the same picture.
- **The owner's tie-breaker** was the least conversion for Blender. The owner then chose the vector and roll explicitly, and the choice is what is recorded.

### D-8. Each direction turns the subject in front of the fixed camera; the light stays with the camera

This resolves Q-2 with option A. The owner first wrote:

> "2) the model turns, along with the light source if it exists."

The manager then asked whether the light stays with the camera or turns with the model. The owner answered:

> "2) i misspoke, i was right the first time, source is fixed with the camera."

- The camera is set once; each direction is the subject turned about the vertical axis through the ground point in front of it, as today.
- The light stays fixed to the camera (V-7 unchanged).
- `--directions`, `--start-angle` and the direction labels stay.
- The presets become shorthands for camera settings.

### D-9. Projects: one schema for the global file and project files, layered

This resolves Q-3. The owner:

> "3) ok yea, this was something i have been on the fence about but let me be firm and clear with it and commit to an answer. we need to introduce the concept of projects, then let --config point to global configuration and --project point to project configuration. this should be a gitignored folder that holds our two project files. i want these two files to share their definitions, a global config with no project files should use whatever defaults it has for everything, acting as a default project. if we choose a project file, it should not have to cover the complete set of config options but should overwrite the existing default options with whichever it lists, so not only could a project file define the local project, but change app settings as well, in the gui we can hide this functionality, but that is how i want it. does that make sense?"

The manager asked three follow-ups:
1. where the folder lives: A, `~/.config/moskophoros/projects/`, or B, a gitignored `projects/` in the repository;
2. whether `--config FILE` means "use this global file instead of `~/.config/moskophoros/config.yaml`", with layers from weakest: shipped defaults, the global file, the `--project` file, the command-line flags;
3. whether the sheet names the project.

The owner answered:

> "3) 1. A, 2. that is correct, 3. no, project is an internal concept to moskophoros"

- **Projects are a concept of the tool.** `--project NAME` reads `~/.config/moskophoros/projects/NAME.yaml`.
- **`--config FILE` selects the global file** in place of `~/.config/moskophoros/config.yaml`.
- **One schema.** The global file and project files share every definition. App settings are valid in a project file, and rendering settings in the global file. Neither is an error.
- **The global file is the default project:** a run without `--project` uses it, over the shipped defaults.
- **A project file is partial:** it sets only what it lists, over the global file.
- **Order, weakest first:** shipped defaults, the global file, the project file, the command-line flags. Where a loaded sheet sits is Q-9.
- **The GUI** may later hide the app settings in project files. The tool does not.
- **The sheet does not name the project.** It records the resolved settings, as it does today.
- **What this overrides** in the worker's Q-3 recommendations: rendering settings in the global file being an error, and having no default project.

### D-10. The camera's position, roll 0 and the facing of each direction

The owner approved every recommendation of questions batch 2 (`questions-2.md`, SHA-256 `e2b13564079126e1072f52a03152cda200c700437bda737dc43ab9a5e04f9792`), typed in the manager's terminal on 2026-10-19: "i approve all of those recommendations". The manager relayed this by cmux message `f12a7bd0-bd32-414b-92a2-cb44f7898daa`, with `relay-camera-batch2.md` (SHA-256 `d8ef58245aa4b72b12fd0e73f367ff4c602ebbc24b433a3fc854b3845d323ecd`). D-10 to D-12 are recorded from it. D-10 resolves Q-8.

- **The position** is in meters from the ground point. Orthographic ignores it. A perspective camera without a position is a usage error.
- **Roll 0** keeps the picture's horizontal level. When the direction points straight down or straight up, screen right is +X, which is today's `topdown` picture.
- **The facing** of each direction is measured from the camera: direction 0, `south`, always faces the camera. So in orthographic only the direction's steepness and the roll change the picture; its compass heading does not. *Refined by D-18:* the names stay tied to the model's turn under roll and upward views.

### D-11. The layers with projects

This resolves Q-9, with D-9.

- **`--config FILE`** is given at most once and replaces `config.yaml` as the global file. A command using it today, such as `--config ~/.config/moskophoros/synarchy.yaml`, keeps working, with that file as the global file.
- **`--no-user-config`** stays. It uses no global file, and cannot be given with `--config`.
- **The order**, weakest first: shipped defaults < the global file < a loaded sheet (`--settings-from`) < the project file < the command-line flags.
- **A missing project file** is a usage error naming its path. The tool never creates `projects/` or any file in it.

### D-12. Everything that shapes the picture is a setting; pitch and presets are shorthands

This resolves Q-10 and Q-5.

- **These become settings,** in the global file or a project file, as well as options:
  - the camera's projection, direction, roll and position;
  - the direction count, start angle and model yaw;
  - pixels per meter, the ground point and the ground pixel;
  - supersampling, the reduction and root motion;
  - the app settings: the Blender program, and whether another Blender version is allowed.
- **`pitch` and the presets stay as shorthands** that set the direction. `pitch` sets the vector `(0, −sin p, −cos p)`, and `iso` is pitch 30, the 2:1 projection. Giving both a pitch and a direction is a usage error.
- **Scale under perspective** is pixels per meter at the ground point's distance from the camera (spike 1). Fitting, the cell and the ground pixel work as they do today.

### D-13. The maps under perspective

The owner approved every recommendation of questions batch 3 (`questions-3.md`, SHA-256 `7047984f7ad211d5e22a9ad182250a3adc9c86878fc9e61a41f7296328f9177f`), and the manager's recommendation that the review agent moves the project file, typed in the manager's terminal on 2026-10-19: "all of your recommendations are correct". The manager relayed this by cmux message `b8560614-c876-4cf4-a7aa-10b44804c8a6`, with `relay-camera-batch3.md` (SHA-256 `f348210702880357d9019d270a0dff7fc0a3d02946ff200fa46cd09b39667f14`). The manager had also told the owner that under perspective the field of view is not set: it follows from the scale and the camera's distance. D-13 to D-15 are recorded from it. D-13 resolves Q-11 and Q-4.

- **The normal map** stays in the camera's space.
- **The depth map keeps today's encoding:** each pixel's distance along the viewing axis relative to the ground point's, in sheet pixels at the ground point's scale. A game reads it as it reads today's.
- **The lit preview lights the sprite the 2D way,** from each pixel's screen position and the depth map, as a game's shader lights the flat sprite. It does not reconstruct perspective positions.

### D-14. Today's pixels stay; the sheet's JSON moves to `/14`

This resolves Q-6.

- **Pixels:** a command that sets no camera gives byte-identical sheets, maps and previews. *Narrowed by D-17* to commands whose resolved settings are the same, with `--config`'s listed exceptions.
- **JSON:** the sheet's JSON becomes `moskophoros.sheet/14`. It gains a `camera` record (projection, direction, roll, position), and drops `pitch_deg`, which the direction holds.
- **Old sheets:** `/13` sheets stop loading with `--settings-from`.

### D-15. The owner's review (CAM-5)

This resolves Q-7. The review renders, each from the owner's own files:

1. **Synarchy's isometric sheet** through `--project synarchy`, on `alpha-model/v5/chest.glb`, shown byte-identical to today's.
2. **A straight-on perspective panel** of `RobotExpressive.glb`, with no baked light.
3. **A camera with a general direction and a roll,** on the shrub or the robot.

**The project file.** The CAM-5 review agent moves `~/.config/moskophoros/synarchy.yaml` to `~/.config/moskophoros/projects/synarchy.yaml`, keeping a copy, and records the move. The tool itself never moves files.

### D-16. The whole design is signed off, with its eight remaining details

The owner signed off the whole draft, typed in the manager's terminal on 2026-10-19: "yes that is all correct, go ahead". The manager relayed it by cmux message `74f98b31-f6c0-4f66-bb9b-ab0278a50f10`, with `relay-camera-signoff.md` (SHA-256 `2399fa85625c125fe191f4b2063e66b73c672889f35c894cad0988570a35c3a5`). It answered `signoff.md` (SHA-256 `7354caeffc75b3bc81168a859d1655ace8b19e2370b40689cb56183e80f02046`), which listed the five slices and these eight details, until then the worker's proposals:

1. **Project names** are letters, digits, `.`, `_` and `-`, not starting with `.`, given without `.yaml`. Anything else is a usage error.
2. **The options** are `--projection orthographic|perspective`, `--camera-direction X,Y,Z`, `--camera-roll R` and `--camera-position X,Y,Z`. The settings are `camera.projection`, `camera.direction`, `camera.roll` and `camera.position`.
3. **The shorthand rules** are as under *Design*, *Shorthands*.
4. **A positive roll** turns the camera counter-clockwise, so the picture turns clockwise.
5. **An orthographic camera's position** is recorded as given, unused, with no warning.
6. **Under perspective:**
   - a ground point behind the camera is a usage error (exit 2);
   - a vertex at or behind the camera is an overflow (exit 4), naming the clip, direction and sample time.
7. **The `/14` sheet's layout:**
   - `settings.view` keeps `preset`, `directions` and `start_angle_deg`;
   - `settings.camera` holds `projection`, `direction` (normalised), `roll` and `position`.
8. **App settings** are not recorded in a sheet and are never loaded from one.

The process after signoff, as the manager put it to the owner:
1. a Codex review of the design;
2. revisions until it is solid;
3. processing into an epic and child issues;
4. Codex approval of the children;
5. the manager checking with the owner before any solving.

### D-17. Byte identity covers commands whose resolved settings are the same; `--config`'s changes are listed exceptions

This resolves Q-12 (review 1, C-2) and narrows D-14. The manager put the choice to the owner on 2026-10-19:
- **A** (recommended): narrow D-14, so a command whose resolved settings are the same gives byte-identical output, and list the `--config` changes as deliberate exceptions;
- **B:** keep the old `--config` layering as well.

The manager noted that today's own files are unaffected: `config.yaml` is empty, and `synarchy.yaml` is self-contained. The owner answered "recommendation approved". The manager relayed it by cmux message `01601801-1300-45c4-b582-c75a9c1d1b77`, with `relay-camera-c2-c3.md` (SHA-256 `0b3ca5428b7258e772f72a0d3c8137aa434b660fc8985f353aab848e9f3e0515`).

- **The promise:** a command whose resolved settings are the same before and after this arc gives byte-identical sheets, maps and previews. Only the JSON changes D-14 lists.
- **The deliberate exceptions,** 1 to 4 from D-11 and 5 from D-14. CAM-1 delivers and tests 1 to 4; CAM-3, which introduces `/14`, delivers and tests 5 (review 2, C-11).
  1. **`--config` given twice** is a usage error. Before: `--config A --config B`. Now: `--config A --project B`, with B in `projects/`, or one merged file.
  2. **`--config FILE` replaces the user file** instead of layering over it, so a setting only the user file gave no longer applies. Now: keep the user file as the global file and pass the other as `--project`, or merge them.
  3. **`--config` with `--no-user-config`** is a usage error. Now: `--config FILE` alone already uses no other global file.
  4. **`--config` with `--settings-from`:** the global file sits below the loaded sheet, so the sheet's values now win where the file's used to. Now: put those values in a project file or on the command line, which sit above the sheet.
  5. **`/13` sheets no longer load** (D-14).
- **Tests:** the tests pinning the old behaviours are replaced on purpose, in CAM-1 for 1 to 4 and in CAM-3 for 5, not kept.

### D-18. Direction names stay tied to the model's turn

This resolves Q-13 (review 1, C-3), with the same message and relay as D-17. The manager put the choice:
- **A** (recommended): the names stay tied to the model's turn. `south` is always direction 0 and `east` always the same quarter turn. On normal downward, unrolled views they mean exactly what they mean today; with roll or an upward camera the picture only rotates, and the names do not change.
- **B:** recompute the names from where the model faces on screen.

The owner answered "recommendation approved".

- **Labels come from `θ` alone,** as today: `south` 0°, `south-east` 45° and so on. `θ` is measured from the camera's unrolled reference heading (D-10).
- **Today's screen-relative description** ("south faces down the screen, east faces screen right") holds for cameras that look down or level with no roll. With a roll or an upward camera the picture turns, but no label changes.

## Proposals

These were the worker's. Each was accepted, as noted.

- **P-1. One camera model for both projections.** The owner accepted its scale as D-12.
  - The camera's direction and the scale fix the image. The ground point and ground pixel fix the framing, as today.
  - **Orthographic** ignores the position.
  - **Perspective** uses the position, and with it the viewing distance. Lens shift puts the ground point on its pixel.
  - Scale stays pixels per meter, measured at the ground point's depth under perspective. Fitting and overflow then work unchanged on projected extents.
  - **Spike 1** (2026-10-19, Blender 5.2.2, headless; `~/.local/share/moskophoros-acceptance/projects-camera-design/spike-1/`, not committed) checked this:
    - **Set-up:** a perspective camera placed off-axis, 3.26 m from the ground point, with the focal length set from the scale (`f = ppm · depth` in pixels) and lens shift set to put the ground point on pixel corner (64, 110) of a 128×128 image, at 40 px/m.
    - **Result:** the rendered 1 m cube covered exactly the pixels predicted from its eight projected corners (columns [31, 85) and rows [68, 120), half-open). The ground point landed on its corner, and a 1 m edge through the ground point spanned 40.0 px.
    - So a perspective camera can keep today's framing contract, with fitting computed from projected extents.
- **P-2. Directions keep turning the subject about the ground point; the camera stays where it is set.** The owner accepted this as D-8.
  - Labels, `--directions`, `--start-angle` and V-7's camera-fixed light are unchanged.
  - The presets become shorthands for camera settings.
- **P-3. Today's commands keep their output byte for byte.** The owner accepted this as D-14.
  - The defaults reproduce today's camera.
  - A new sheet schema records the camera.

## Open questions

### Q-1. How is the camera's direction given?

**Resolved by D-7:** a vector, with a separate roll. The position's origin moved to Q-8.

### Q-2. Directions against a free camera

**Resolved by D-8:** the subject turns in front of the fixed camera, and the light stays with the camera.

### Q-3. How a project is chosen, and what the app file holds

**Resolved by D-9:**
- `--project NAME` reads `~/.config/moskophoros/projects/NAME.yaml`;
- `--config` selects the global file;
- the two kinds of file share one schema.

Which app settings exist is still open, in Q-10.

### Q-4. Perspective's parameters

**Resolved by D-12 and D-13.** The field of view follows from the scale and the ground point's distance, clipping is automatic, and the maps follow D-13.

### Q-5. Scale and framing as settings

**Resolved by D-12.**

### Q-6. Compatibility

**Resolved by D-14.**

### Q-7. Verification

**Resolved by D-15** for the owner's review. The tests are under *Verification strategy*.

### Q-8. The camera's position, its roll's zero, and what each direction is measured from

**Resolved by D-10.**

### Q-9. The layers once `--config` names the global file

**Resolved by D-11.**

### Q-10. Which app settings exist

**Resolved by D-12:** the Blender program, and whether another Blender version is allowed. `--work-dir` stays an option only, since it names one run's workspace.

### Q-11. The maps under perspective

**Resolved by D-13.**

### Q-12. Compatibility once `--config` names the global file (review 1, C-2)

**Resolved by D-17.**

### Q-13. Direction labels under roll and upward views (review 1, C-3)

**Resolved by D-18.**

## Verification strategy

- **Pure tests,** without Blender:
  - the camera basis from a direction and roll, including straight down and up, and roll −1 against +1, with a worked roll example;
  - `pitch` and the presets giving today's basis exactly;
  - each direction's facing measured from the camera;
  - the shorthand and `null`/`auto` rules within and across layers;
  - the perspective projection relative to the ground point (the ground projects to zero), with the rolled axes (`roll = 0.5` moves a point above the ground to its right), off-axis fitting and overflow, calibration and lens shift for square, portrait, landscape, supersampled and widened-sensor cases (spike 2), and the near-plane boundary;
  - project names, the project directory under XDG, the layer order, and one schema in both kinds of file.
- **Byte identity** (D-14, as narrowed by D-17).
  - Evidence comes from comparing outputs at the slice's base revision with its head, on generated fixtures, run locally and reported in the pull request. Pinned digests in tests are not used.
  - **Fixtures:** every preset, a custom pitch, a nonzero ground and model yaw, a rectangular cell, both reductions, and alpha and material-library cases.
  - **Changes that are allowed:** only those listed exactly per slice, such as the sheet JSON's schema, its `camera` record and the fingerprint. A pixel change is never accepted just because the new renderer produced it.
- **Blender tests** (`@pytest.mark.blender`, generated fixtures):
  - an orthographic camera with a general direction and a roll;
  - a perspective camera whose framing covers the predicted pixels exactly, as in spikes 1 and 2;
  - a vertex too near the camera failing with exit 4, keeping earlier outputs.
- **The owner's visual review** (CAM-5): the owner's own project files and renders, judged by eye (V-12). It gates the epic, though it is off the implementation's critical path.
- **Documentation.** `docs/design.md` is read by tests, so each slice updates the sections it changes in its own pull request. Designs and acceptance records are landed with `docs-push` and linked from the pull request.

## Delivery plan

### CAM-1. Add projects and a single global settings file

- **Outcome:** `--project NAME` layers `projects/NAME.yaml` over the global file, and `--config FILE` names the one global file.
- **Scope:**
  - `--project NAME` and its name rule;
  - the project directory under `$XDG_CONFIG_HOME`, never moved by `--config` or `--no-user-config`;
  - `--config FILE` given at most once, replacing `config.yaml`;
  - `--no-user-config` refused with `--config`;
  - the layer order with a loaded sheet;
  - one schema for both kinds of file;
  - a missing project file as a usage error.
  - **Contracts:** design §CLI and §Settings files, and the settings design's layers, updated.
- **Phase:** 1.
- **Depends on:** `none`.
- **Ordering:** `critical path`.
- **Relevant decisions:** D-1, D-9, D-11, D-16, D-17.
- **Acceptance signals:**
  - a project value overrides the global file's, and a flag overrides the project's;
  - a loaded sheet sits between the global file and the project;
  - project lookup works with XDG set and unset, with an alternate `--config` and with `--no-user-config`;
  - paths in a project file resolve relative to it, and the reuse palette and library rules hold for a project's values;
  - a second `--config`, `--config` with `--no-user-config`, a missing project file, or a bad or path-like name each fail with exit 2, naming the problem;
  - **tests replaced on purpose:** the tests pinning today's repeatable, layered `--config` (`tests/test_settings_command.py`) are replaced with tests of the new precedence and refusals, and of D-17's exceptions 1 to 4 with their new equivalents. Generating and reusing `/13` sheets keeps working in CAM-1;
  - outputs keep their bytes wherever the resolved settings are the same (D-17).
- **Out of scope:** new settings; the camera.
- **Open questions:** `None`.

### CAM-2. Make the view, scale and framing settings-file settings

- **Outcome:** everything that shapes the picture today can be set in the global or a project file.
- **Scope:**
  - `view`, `pitch`, `directions`, `start_angle`, `model_yaw`, `ppm`, `ground`, `ground_px`, `supersample`, `reduce` and `root_motion`;
  - the app settings `blender` and `any_blender`;
  - the `null` and `auto` values, including `--ppm auto` and `--ground-px auto`;
  - the shorthand rules for `view` and `pitch` across layers.
  - **Contracts:** the schema table, `defaults.yaml`, design §CLI, §Settings files, *Option validation* and *Reuse*, and the settings design, updated.
- **Phase:** 1.
- **Depends on:** CAM-1.
- **Ordering:** `critical path`.
- **Relevant decisions:** D-4, D-5, D-12, D-16.
- **Acceptance signals:**
  - each new setting in a file gives the same output as its option;
  - an empty file and the unchanged default command give today's outputs;
  - each preset resolves as today;
  - a layer's `view` replaces the pitch, direction count and start angle below it;
  - `null` and `auto` clear inherited values from files and flags, and `--ppm auto` or `--ground-px auto` drop a reused value;
  - **the view state's worked cases** (C-9):
    - a named-preset sheet reloads with its marker, JSON and fingerprint unchanged;
    - a `custom` sheet with a `null` reset is refused, and with a concrete `view` in the same layer it is accepted;
    - a lower `pitch` with a higher `null` direction gives the preset's direction;
    - `pitch` and `camera.direction` in one layer are refused whatever their values (with `camera.direction` arriving in CAM-3, CAM-2 tests the rule for `pitch` against `view` and `null`);
  - app settings survive layering but never enter the sheet's settings or its fingerprint;
  - the byte comparison holds for commands that set none of these.
- **Out of scope:** the camera's direction, roll, position and projection.
- **Open questions:** `None`.

### CAM-3. Point the orthographic camera with a direction and roll

- **Outcome:** the camera looks along any direction, with a roll, and `pitch` and the presets are shorthands for that direction.
- **Scope:**
  - `camera.direction`, `camera.roll` and `camera.position` (recorded, unused in orthographic), as settings and options;
  - the basis and roll rule, and each direction's facing and label rule (D-18), with the half-turn roll and straight-up examples as tests;
  - `pitch` with a direction refused within one layer;
  - sheet schema `/14` with `settings.camera`, an object with `projection` (a string), `direction` (an array of three numbers, normalised), `roll` (a number) and `position` (an array of three numbers, or `null`), placed after `settings.view`;
  - `--settings-from` of `/14` only;
  - the capture job's camera record, `capture-job/2`, and both its validators.
  - **Contracts:** design §Camera and directions (labels per D-18), §Presets, §Capture (job contract), §Export (sheet JSON) and §Reproducibility, updated.
- **Phase:** 2.
- **Depends on:** CAM-2.
- **Ordering:** `critical path`.
- **Relevant decisions:** D-3, D-7, D-8, D-10, D-12, D-14, D-16, D-18.
- **Acceptance signals:**
  - **the byte comparison against the base revision:** every preset and `pitch` gives today's pixels exactly;
  - **the expected JSON, job and fingerprint changes** are listed in the pull request and updated in `tests/test_export.py` and `tests/test_capture_backend.py`;
  - a direction and roll give the predicted basis;
  - looking straight down gives today's `topdown`;
  - generate-then-reload gives equal settings for a non-trivial normalised direction, a roll and an ignored orthographic position;
  - D-17's exception 5: a `/13` sheet is refused, naming both schemas, and the test that loaded `/13` is replaced on purpose;
  - generating and reloading a `/14` sheet gives equal complete output, its JSON and fingerprint included, for a named preset, a `custom` view, and `pitch` and `camera.direction` against `null` in one layer.
- **Out of scope:** perspective.
- **Open questions:** `None`.

### CAM-4. Add the perspective projection

- **Outcome:** `camera.projection: perspective` renders from the camera's position, with pixels per meter at the ground point's depth.
- **Scope:**
  - the perspective camera, its calibration, lens shift and clipping, as under *Design*;
  - fitting and overflow from ground-relative projected extents;
  - a missing position (exit 2), a ground point behind the camera (exit 2) and a vertex too near the camera (exit 4) as errors;
  - the measure result's `depth_m` and `null` `bounds_m`, `capture-job/3` and `capture-result/4`, and the launcher's validators;
  - the maps under perspective.
  - **Contracts:** design §Scale and ground point, §Capture, §Export (depth and lit previews, qualifying position reconstruction) and §Exit codes, updated.
- **Phase:** 3.
- **Depends on:** CAM-3.
- **Ordering:** `critical path`.
- **Relevant decisions:** D-3, D-10, D-12, D-13, D-16.
- **Acceptance signals:**
  - a generated cube's framing covers exactly the predicted pixels, square, rectangular, supersampled and wide-field, and with a nonzero roll and an off-axis ground point in a rectangular cell, so measure and render use the same rolled axes (C-10);
  - all three fitting cases, an off-axis ground point and animated extents fit with the 1-pixel margin;
  - depth sign, scale and range follow `(d − z_c)·ppm`, and the 2D lit preview's formula holds;
  - perspective settings reload with `--settings-from`;
  - a too-near vertex exits 4 and keeps earlier outputs, while malformed or mismatched results stay exit 5;
  - each error has its exit code and message;
  - the byte comparison holds for orthographic commands.
- **Out of scope:** other projections; baked light (the shading design).
- **Open questions:** `None`.

### CAM-5. Owner review of projects and the camera

- **Outcome:** the owner judges, by eye, renders made from their own project files with the new camera, and the verdict is recorded.
- **Scope:**
  - **Before any change,** keep a pre-migration baseline: today's Synarchy render, from `--config ~/.config/moskophoros/synarchy.yaml`, and its hashes.
  - **Move** `~/.config/moskophoros/synarchy.yaml` to `projects/synarchy.yaml` (D-15), keeping the original as a copy:
    - **rebase every relative path** so it names the same file, for example `palettes/synarchy.gpl` to `../palettes/synarchy.gpl`;
    - **record** both paths and both files' hashes;
    - **before rendering,** confirm that the resolved rendering settings and the referenced palette's and library's bytes are the same;
    - **if `projects/synarchy.yaml` already exists,** stop and ask the owner; never overwrite it.
  - The three review renders of D-15, with commands signed off by the owner before rendering.
  - The record in `docs/acceptance/`.
- **Phase:** 4.
- **Depends on:** CAM-4.
- **Ordering:** `not on the critical path`; it gates the epic's completion.
- **Relevant decisions:** D-1, D-6, D-15.
- **Acceptance signals:**
  - the project render is byte-identical to the pre-migration baseline;
  - the owner's verdict, quoted and dated.
- **Out of scope:** baked light, the Codekarl palette and its look.
- **Open questions:** `None`.

## Revision notes

### Review 1 (Codex, 2026-10-19)

`~/.local/share/moskophoros-acceptance/projects-camera-design/review-codex-1.md`, SHA-256 `0e2789e0b4152a0dcb10245dbde54e95eb7369e26fe5f71770538d558a3239d8`, reviewed `cb5b7b1e47`: 3 blocking, 5 should fix.

- **C-1, blocking: fixed.** The perspective projection is relative to the ground point, `X = d·x_c/z_c − x_g` and `Y = d·y_c/z_c − y_g`, as spike 1's script already computed. The subject's turn and the camera basis come first. Spike 1's bounds are given half-open.
- **C-2, blocking: resolved by the owner (D-17).** D-14 is narrowed to commands whose resolved settings are the same. The five `--config` and sheet exceptions are listed with their new equivalents, and CAM-1 replaces the affected tests on purpose.
- **C-3, blocking: resolved by the owner (D-18).** Labels come from `θ` alone, measured from the camera's unrolled reference heading. The screen-relative description holds for downward or level unrolled cameras. The roll matrix, a half-turn example and a straight-up example are given.
- **C-4, should fix: fixed.** The design now specifies:
  - calibration from the horizontal sensor fit, with the lens and sensor chosen together so neither falls below Blender's 1 mm minimum;
  - lens shift in units of the image width;
  - the read-back checks;
  - the near and far planes from measured depths;
  - a vertex nearer than 1e-4 m as an overflow.

  Spike 2 (`projects-camera-design/spike-2/`) confirmed calibration and shift on portrait, landscape, supersampled and widened-sensor images. Its first run, with shift in units of the larger side, failed for portrait images, which is why the width is specified.
- **C-5, should fix: fixed.** The measure result gains `depth_m` and allows `null` bounds only for a too-near frame under perspective. The caller raises exit 4, malformed output stays exit 5, and the caller computes the clipping planes for the render job. The schema bumps are assigned to CAM-3 and CAM-4.
- **C-6, should fix: fixed.** Literal shipped defaults, the meaning of an absent key, `null` and `auto`, `--ppm auto` and `--ground-px auto`, `blender: null`, and the order in which the shorthands resolve.
- **C-7, should fix: fixed.** CAM-5 rebases relative paths when it moves the project file, compares resolved settings and asset bytes before rendering, and never overwrites an existing project file.
- **C-8, should fix: fixed.** Each slice names the contracts it updates and the tests it replaces on purpose. Byte identity is shown by comparing the base revision with the head on generated fixtures. The project directory under XDG is independent of `--config`.

### Review 2 (Codex, 2026-10-19)

`~/.local/share/moskophoros-acceptance/projects-camera-design/review-codex-2.md`, SHA-256 `fa7b22a468c6597ec2e92c7a676c96823d1264415dd3717252a08ff686de45ae`, reviewed `7d149825ca`. It found C-1 to C-4 and C-7 fixed, and C-5, C-6 and C-8 partly fixed; their remaining parts are C-9 to C-12. No owner decision was needed.

- **C-9, should fix: fixed.**
  - The view is one state: a preset marker and three values, each the preset's or an override. A loaded sheet is a snapshot that keeps its marker, `custom` included.
  - `pitch` and `camera.direction` are one logical key, and giving both in one layer, with any values, is an error.
  - A `null` resets a value to the preset's, and over a `custom` view it needs a concrete `view` in the same layer.
  - The worked cases and full generate-and-reload equality are in CAM-2 and CAM-3.
- **C-10, should fix: fixed.** `r₀` and `u₀` are the unrolled axes. The rolled `r` and `u` are used for everything that makes the picture: render, framing, perspective camera space, fitting and lens shift. CAM-4 tests a rolled, off-axis perspective camera in a rectangular cell.
- **C-11, should fix: fixed.** CAM-1 delivers and tests D-17's exceptions 1 to 4 and keeps `/13` working. CAM-3 delivers exception 5 with `/14`.
- **C-12, minor: fixed.** The measure frame keeps `bounds_m`, which is `null` for a too-near frame, with its `address` and `height_m`, as the example frames show.
