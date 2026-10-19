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

## Proposals

These are the worker's, not decisions.

- **P-1. One camera model for both projections.**
  - The camera's direction and the scale fix the image. The ground point and ground pixel fix the framing, as today.
  - **Orthographic** ignores the position.
  - **Perspective** uses the position, and with it the viewing distance. Lens shift puts the ground point on its pixel.
  - Scale stays pixels per meter, measured at the ground point's depth under perspective. Fitting and overflow then work unchanged on projected extents.
  - **Spike 1** (2026-10-19, Blender 5.2.2, headless; `~/.local/share/moskophoros-acceptance/projects-camera-design/spike-1/`, not committed) checked this:
    - **Set-up:** a perspective camera placed off-axis, 3.26 m from the ground point, with the focal length set from the scale (`f = ppm · depth` in pixels) and lens shift set to put the ground point on pixel corner (64, 110) of a 128×128 image, at 40 px/m.
    - **Result:** the rendered 1 m cube covered exactly the pixels predicted from its eight projected corners (columns 31–85, rows 68–120). The ground point landed on its corner, and a 1 m edge through the ground point spanned 40.0 px.
    - So a perspective camera can keep today's framing contract, with fitting computed from projected extents.
- **P-2. Directions keep turning the subject about the ground point; the camera stays where it is set.** The owner accepted this as D-8.
  - Labels, `--directions`, `--start-angle` and V-7's camera-fixed light are unchanged.
  - The presets become shorthands for camera settings.
- **P-3. Today's commands keep their output byte for byte.**
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

### Q-8. The camera's position, its roll's zero, and what each direction is measured from

**Raised by D-7 and D-8:**
- **The position:** what its origin is, and whether perspective needs one given.
- **Roll 0:** which way is up when the direction points straight up or down, where "up" is ambiguous.
- **The facing:** whether each direction's facing is measured from the camera's heading. If it is, the labels keep their meaning, and in orthographic the vector's heading changes nothing but which side direction 0 shows.

### Q-9. The layers once `--config` names the global file

**Raised by D-9.** Today `--config` is repeatable and sits above a loaded sheet.

- what happens to today's repeatable, layered `--config`, and to commands that use it;
- where `--settings-from` sits among the global file, the project and the flags;
- what `--no-user-config` becomes;
- what happens when a project file is missing, and whether the `projects/` folder must exist.

### Q-10. Which app settings exist

**Raised by D-9.** Today's candidates: `--blender`, `--any-blender`, `--work-dir`. With one schema, any of these may sit in the global file or a project file.
