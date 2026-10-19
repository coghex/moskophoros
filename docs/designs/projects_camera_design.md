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

Design state: `exploring`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

Slices are not drafted yet; they follow the open questions.

- [ ] EPIC. Projects and a free camera

## Epic contract

- **Goal:** each project's rendering look lives in its own settings file, and
  its view is a camera with a position, a direction and a projection, set in
  that file or on the command line.
- **Done when:** to be settled with the delivery plan.
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

Not drafted yet; it waits on the open questions.

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

## Proposals

These are the worker's, not decisions.

- **P-1. One camera model for both projections.**
  - The camera's direction and the scale fix the image. The ground point and ground pixel fix the framing, as today.
  - **Orthographic** ignores the position.
  - **Perspective** uses the position, and with it the viewing distance. Lens shift puts the ground point on its pixel.
  - Scale stays pixels per meter, measured at the ground point's depth under perspective. Fitting and overflow then work unchanged on projected extents.
- **P-2. Directions keep turning the subject about the ground point; the camera stays where it is set.**
  - Labels, `--directions`, `--start-angle` and V-7's camera-fixed light are unchanged.
  - The presets become shorthands for camera settings.
- **P-3. Today's commands keep their output byte for byte.**
  - The defaults reproduce today's camera.
  - A new sheet schema records the camera.

## Open questions

### Q-1. How is the camera's direction given, and its position measured?

**Options for the direction's three values:**
- **A. Angles:** yaw, pitch and roll, in degrees. Pitch is today's pitch.
- **B. A point the camera looks at.**
- **C. A vector it looks along.**

**Options for the position's origin:**
- the ground point;
- the subject's origin.

Because the subject turns, a camera yaw does the same as the start angle (see *Current state*). The answer decides the option and setting names, the presets and the sheet record.

### Q-2. Directions against a free camera

- **Does each direction still turn the subject** (P-2), or does the camera orbit around it?
- **What becomes of `--directions`, `--start-angle` and the presets?**

For unlit colour the two images are the same, but they differ once light is baked or placed in the world.

### Q-3. How a project is chosen, and what the app file holds

**Options for choosing a project:**
- `--config FILE`, as today;
- a new `--project NAME` that finds the project's file.

**Also to settle:**
- where project files live;
- which app settings exist (Blender path, version check, work directory, a default project?);
- whether a rendering setting in the app file stays allowed.

### Q-4. Perspective's parameters

- **Field of view:** is it a setting, or derived from the scale and the cell (P-1)?
- **Clipping.**
- **Map units:** what the depth map's and the preview light's sheet-pixel units mean under perspective.

### Q-5. Scale and framing as settings

- **Which become file settings:** `ppm`, the ground point, the ground pixel, supersample, model yaw, root motion and the reduction?
- **What scale means under perspective.**

### Q-6. Compatibility

- **Byte-identical output** for existing commands (P-3).
- **The sheet schema bump,** which stops `/13` sheets loading under settings D-24.
- **`--settings-from` with a camera.**

### Q-7. Verification

- **Probes and tests:** free and perspective cameras, and fitting under perspective.
- **The owner's visual review** as its own slice.
