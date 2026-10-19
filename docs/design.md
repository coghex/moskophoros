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
| **view** | The camera setup: the camera's projection, direction, roll and position, the direction count and the start angle. |
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
| `--view NAME` | `iso` | Preset: `topdown`, `side`, `iso` or `iso-true`. A [settings file](#settings-files) may set it. |
| `--pitch DEG` | from preset | Camera pitch, 0 to 90 inclusive: a shorthand for the camera direction `(0, −sin p, −cos p)`. Cannot accompany `--camera-direction`. A [settings file](#settings-files) may set it. |
| `--camera-direction X,Y,Z` | from preset | The way the camera looks, in subject coordinates: three finite numbers, each −1 to +1, not all 0, which the tool normalises. Cannot accompany `--pitch`. See [Camera and directions](#camera-and-directions). A [settings file](#settings-files) may set it. |
| `--camera-roll R` | `0` | The camera's turn about the way it looks, a finite number from −1 to +1, a fraction of a half turn (`R · π` radians); positive turns the picture clockwise. A [settings file](#settings-files) may set it. |
| `--camera-position X,Y,Z` | none | The camera's position, three finite numbers, meters from the ground point. The orthographic camera records it unused, with no warning (projects and camera design D-16). A [settings file](#settings-files) may set it. |
| `--directions N` | from preset | Direction count, 1 to 64. A [settings file](#settings-files) may set it. |
| `--start-angle DEG` | from preset | Angle of direction 0. A [settings file](#settings-files) may set it. |
| `--model-yaw DEG` | `0` | Corrects a model that does not face +Z (see [Input contract](#input-contract)). A [settings file](#settings-files) may set it. |
| `--clip NAME` | every clip | Repeatable. Selects clips and their order in the sheet. |
| `--once NAME` | none | Repeatable. Marks a selected clip as one-shot; all others loop. |
| `--fps N` | `12` | Target sampling rate, greater than 0. A [settings file](#settings-files) may set it. |
| `--ppm N` | auto | Pixels per meter, greater than 0, or `auto`, fitted. `auto` drops a reused or configured value, as `--cell auto` drops a cell (projects and camera design D-16). See [Scale and ground point](#scale-and-ground-point). A [settings file](#settings-files) may set it. |
| `--cell WxH` | reused by `--settings-from`, else fitted to the model with `--ppm`, else 64×64 | Cell size in pixels, each 1 to 4096, or `auto`, the automatic cell: fitted with the pixels per meter in force, given or reused, else 64×64. `auto` drops a reused or configured cell (owner decision 2026-10-11, settings design D-32). Without a given or reused `--ppm`, the model is scaled to fit the cell. See [Scale and ground point](#scale-and-ground-point). A [settings file](#settings-files) may set it. |
| `--ground X,Y,Z` | `0,0,0` | Ground point in subject coordinates, meters. A [settings file](#settings-files) may set it. |
| `--ground-px X,Y` | auto | Cell pixel corner the ground point lands on, or `auto`, fitted. `auto` drops a reused or configured value (projects and camera design D-16). A [settings file](#settings-files) may set it. |
| `--root-motion MODE` | `error` | `error` or `keep`. See [Root motion](#root-motion). A [settings file](#settings-files) may set it. |
| `--supersample N` | `8` | Capture resolution multiplier, 1 to 16. A [settings file](#settings-files) may set it. |
| `--reduce NAME` | `plain` | How each supersampled block becomes one pixel: `plain`, the alpha-weighted mean, or `mode`, the most common colour. See [Stylize](#stylize). A [settings file](#settings-files) may set it. |
| `--edges RULE` | `hard` | How a pixel's alpha comes from its supersampled block: `hard`, a pixel shows when at least half its block shows a surface, at their mean alpha, so outlines stay crisp; or `soft`, its alpha is the block's mean alpha, so outlines and cut-out edges keep the partial alpha reducing the block gives (alpha design D-4, D-9). See [Stylize](#stylize). A [settings file](#settings-files) may set it. |
| `--palette FILE` | none | Map colours to an ordered `.hex`, `.gpl` or `.png` palette. See [Stylize](#stylize). A [settings file](#settings-files) may set it. |
| `--no-palette` | off | Use no palette, dropping a reused or configured one; cannot accompany `--palette`. |
| `--materials FILE` | none | Draw each named material from the ramps of a YAML material library, a `.yaml` or `.yml` file, on the palette in force. Needs a palette. See [Material libraries](#material-libraries). A [settings file](#settings-files) may set it. |
| `--no-materials` | off | Use no material library, dropping a reused or configured one; cannot accompany `--materials`. |
| `--ao-distance M` | `0.3` | How far the shade's ambient occlusion looks for other surfaces, in meters, greater than 0. See [Capture](#capture), *Shade*. A [settings file](#settings-files) may set it. |
| `--ao-samples N` | `64` | Ambient occlusion samples per pixel, a whole number from 1 to 128, the most Blender's Ambient Occlusion node takes (settings design D-42). A [settings file](#settings-files) may set it. |
| `--occlusion-weight W` | `0.25` | How much occlusion by other surfaces lightens the shade, finite and 0 or greater. A [settings file](#settings-files) may set it. |
| `--convexity-weight W` | `1.0` | How much a surface's own convexity lightens the shade, finite and 0 or greater. A [settings file](#settings-files) may set it. |
| `--shade-range LO,HI` | `84,191` | The 8-bit shade values a material's ramp spans, two integers with `0 ≤ LO < HI ≤ 255`. See [Material ramps](#material-ramps). A [settings file](#settings-files) may set it. |
| `--ramp-step L` | `0.12` | How much OKLab lightness each shade of a library's [generated ramps](#generated-ramps) drops, finite, 0 to 1. A ramp's own value beats it. |
| `--ramp-hue-shift DEG` | `-12` | How far each shade of a generated ramp turns the hue, in degrees, finite, −180 to 180. |
| `--ramp-fade F` | `0.3` | How much chroma a generated ramp loses by its darkest shade, finite, 0 to 1. |
| `--frames N` | `auto` | How many frames each clip is sampled to, a whole number 1 or more, retimed so every frame lasts `1/fps`; `auto` samples by duration. A clip's own count, set in a [settings file](#settings-files), beats it. See [Clips and sampling](#clips-and-sampling). |
| `--settings-from FILE` | none | Load every recorded setting of an earlier `moskophoros.sheet/14` sheet's JSON. See [Scale and ground point](#scale-and-ground-point). |
| `--config FILE` | the user file | Use FILE as the global settings file, in place of the user file. Given at most once. Its values are defaults, below a loaded sheet. See [Settings files](#settings-files). |
| `--no-user-config` | off | Use no global settings file: skip the user file. Cannot accompany `--config`. |
| `--project NAME` | none | Read the project file `projects/NAME.yaml` in the configuration directory. Given at most once. Its values act as the options would, over the global file and a loaded sheet. See [Settings files](#settings-files). |
| `--preview` | on | Write the animated previews, also over a sheet or settings file without them; cannot accompany `--no-preview`. |
| `--no-preview` | off | Skip the animated previews. A [settings file](#settings-files) may set `previews: false` instead. |
| `--normals` | on | Write the normal map, `<stem>.normal.png`, also over a sheet or settings file without it; cannot accompany `--no-normals`. See [Export](#export). |
| `--no-normals` | off | Skip the normal map; an earlier one is left as it was. A [settings file](#settings-files) may set `normals: false` instead. |
| `--depth` | off | Write the depth map, `<stem>.depth.png`, also over a sheet or settings file without it; cannot accompany `--no-depth`. A depth it cannot hold is an [overflow](#scale-and-ground-point). See [Export](#export). |
| `--no-depth` | off | Skip the depth map, also over a sheet or settings file that writes it; an earlier one is left as it was. |
| `--light X,Y,Z` | none | Place a point light and write a lit preview per clip, `<stem>-lit.<clip>.gif`, beside the flat ones: `X` screen right, `Y` screen up, `Z` toward the viewer, in sheet pixels from the ground point, three finite numbers. See [Export](#export), *Lit previews*. |
| `--no-light` | off | Place no light, dropping a reused or configured one, as `--no-palette` does; cannot accompany `--light`. |
| `--light-intensity I` | `1.0` | How strongly the light lights a surface facing it, finite and 0 or greater. |
| `--light-ambient A` | `0.3` | How bright a surface facing away from the light is, finite and from 0 to 1. |
| `--work-dir DIR` | temporary | Keep capture output in `DIR` instead of a deleted temporary directory. |
| `--blender PATH` | discovered | Blender executable. See [Capture](#capture). A [settings file](#settings-files) may set it as the app setting `blender`, which no sheet records or loads. |
| `--any-blender` | off | Allow a Blender version other than the supported one. A [settings file](#settings-files) may set it as the app setting `any_blender`, which no sheet records or loads; only a file can set it back to `false`. |

Without `--clip`, every clip is selected in the file's animation order:
ascending animation index (owner decision 2026-10-01).

`<outfile.png>` must end in `.png`. The JSON is written beside it, at the same
path with `.json` replacing `.png`, the normal map, unless turned off, at
the same path with `.normal.png` replacing `.png`, and the depth map, when
asked, with `.depth.png` (lighting sheet design D-9, D-10, D-17). Previews are written as
`<stem>.<clip>.gif` beside it, and with a light each clip's lit preview as
`<stem>-lit.<clip>.gif`, the flat name with `<stem>` replaced by
`<stem>-lit` (lighting sheet design D-22); a clip name is made filename-safe by replacing
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
were, and so does an earlier normal map under `--no-normals`, depth map
without `--depth` and lit previews without a light (owner decisions
2026-10-01; lighting sheet design D-17). Errors go to stderr as
`moskophoros: error: <message>`.

With `--work-dir DIR`, `DIR` must be nonexistent or an existing empty
directory. An existing nonempty directory is a usage error (exit 2) naming
the directory, and its contents are untouched. The capture workspace contains
separate `measure/` and `render/` directories, each with `job.json`, eventual
`result.json` and produced buffers. While a phase runs, its directory also
holds `import/`, the script's private copy of the model that Blender imports,
which the phase removes when it finishes or fails. During rendering,
`render/` also holds
`scratch/`, the capture's scratch directory (its TGA and its main and
count renders' OpenEXRs),
which a successful phase removes. After a failure, a retained workspace may
still hold `scratch/`; after an interruption, it may still hold `scratch/`
and either phase's `import/`. An explicitly supplied workspace
retains available artifacts after success or failure; normal temporary
capture workspaces are deleted in either case, the scratch and the copy with
them. Retention does not make an incomplete
phase a valid result or supply a replay interface. Reusing a retained location
requires choosing a new or empty directory (owner decision 2026-09-30).

### Settings files

Everything that shapes the picture is also a setting, which YAML settings
files may set: the view, the model yaw, the scale, the cell, the ground point
and ground pixel, supersampling, the reduction, root motion, `fps`, the
palette, the material library, the edges rule, whether previews and the
normal and depth maps are written, and the preview light. So are the two app
settings, the Blender executable and whether another Blender version is
allowed (owner decisions 2026-10-11, settings design D-2, D-5, D-8, D-14,
D-17, D-22, D-28, D-30 and D-32; lighting sheet design D-18; alpha design
D-9; projects and camera design D-4, D-5, D-12 and D-16). Each is validated exactly as its option is. One schema table
in `settings.py` gives each setting's type, unit, default and validation
rule, and the packaged `defaults.yaml` gives every setting its shipped
default; a test keeps the two in agreement.

| Setting | Option | Shipped default | Value |
|---|---|---|---|
| `view` | `--view NAME` | `iso` | `topdown`, `side`, `iso` or `iso-true`: a shorthand that sets the next three (see *The view*) |
| `pitch` | `--pitch DEG` | `null` | a finite number from 0 to 90, or `null`: the view's; a shorthand for `camera.direction` |
| `camera.direction` | `--camera-direction X,Y,Z` | `null` | `[x, y, z]`, three finite numbers each from −1 to 1, not all 0, normalised, or `null`: the view's |
| `camera.roll` | `--camera-roll R` | `0` | a finite number from −1 to 1, a fraction of a half turn |
| `camera.position` | `--camera-position X,Y,Z` | `null` | `[x, y, z]`, three finite numbers, meters from the ground point, or `null`; unused by the orthographic camera |
| `directions` | `--directions N` | `null` | a whole number from 1 to 64, or `null`: the view's |
| `start_angle` | `--start-angle DEG` | `null` | a finite number of degrees, or `null`: the view's |
| `model_yaw` | `--model-yaw DEG` | `0` | a finite number of degrees |
| `ppm` | `--ppm N` | `auto` | a finite number greater than 0, or `auto` |
| `cell` | `--cell WxH` | `auto` | `WxH`, each side 1 to 4096, or `auto` |
| `ground` | `--ground X,Y,Z` | `[0, 0, 0]` | `[x, y, z]`, three finite numbers, meters in subject coordinates |
| `ground_px` | `--ground-px X,Y` | `auto` | `[x, y]`, two whole numbers 0 or greater, or `auto` |
| `supersample` | `--supersample N` | `8` | a whole number from 1 to 16 |
| `reduce` | `--reduce NAME` | `plain` | `plain` or `mode` |
| `root_motion` | `--root-motion MODE` | `error` | `error` or `keep` |
| `fps` | `--fps N` | `12` | a finite number greater than 0 |
| `frames` | `--frames N` | `auto` | a whole number 1 or more, or `auto` |
| `clips.NAME.frames` | none: files only | none | a whole number 1 or more, `auto`, or `null` to take `frames` |
| `palette` | `--palette FILE`, `--no-palette` | `null` | a palette file path, or `null` for none |
| `materials` | `--materials FILE`, `--no-materials` | `null` | a material library path, or `null` for none |
| `edges` | `--edges RULE` | `hard` | `hard` or `soft` |
| `previews` | `--preview`, `--no-preview` | `true` | `true` or `false` |
| `normals` | `--normals`, `--no-normals` | `true` | `true` or `false` |
| `depth` | `--depth`, `--no-depth` | `false` | `true` or `false` |
| `light.position` | `--light X,Y,Z`, `--no-light` | `null`: no light | `[x, y, z]`, three finite numbers in sheet pixels, or `null` |
| `light.intensity` | `--light-intensity I` | `1.0` | a finite number 0 or greater |
| `light.ambient` | `--light-ambient A` | `0.3` | a finite number from 0 to 1 |
| `shade.ao_distance_m` | `--ao-distance M` | `0.3` | a finite number greater than 0, meters |
| `shade.ao_samples` | `--ao-samples N` | `64` | a whole number from 1 to 128 |
| `shade.occlusion_weight` | `--occlusion-weight W` | `0.25` | a finite number 0 or greater |
| `shade.convexity_weight` | `--convexity-weight W` | `1.0` | a finite number 0 or greater |
| `shade.range` | `--shade-range LO,HI` | `[84, 191]` | `[lo, hi]`, two integers with `0 ≤ lo < hi ≤ 255` |
| `ramp.lightness_step` | `--ramp-step L` | `0.12` | a finite number from 0 to 1 |
| `ramp.hue_shift_deg` | `--ramp-hue-shift DEG` | `-12` | a finite number from −180 to 180, degrees |
| `ramp.chroma_fade` | `--ramp-fade F` | `0.3` | a finite number from 0 to 1 |
| `blender` | `--blender PATH` | `null` | an executable's path, or `null` to discover Blender as today; an app setting |
| `any_blender` | `--any-blender` | `false` | `true` or `false`; an app setting |

Values are type-strict: a number is a YAML number, never a string such as
`"30"` or a boolean, and is finite. `directions`, `supersample` and
`frames` are YAML integers, never `8.0`. `ground_px` coordinates are whole
numbers: an integral float such as `3.0` is taken as `3`, as `--ground-px`
takes it. Whether the ground pixel lies inside the cell stays an
[overflow](#scale-and-ground-point) question.

The `camera` settings are a nested mapping in a file too, merged key by key
the same way (projects and camera design D-7, D-16). The `camera.projection`
setting comes with the perspective projection; until then a file giving it is
refused as an unknown key, and the camera is orthographic.

The `shade` settings are a nested mapping in a file, and each is a setting of
its own: they merge key by key across the layers, so a file may set one and
inherit the rest, while `shade.range`, a list, replaces whole (owner
decisions 2026-10-11 and 2026-10-12, settings design D-3, D-9, D-12, D-22,
D-30 and D-42). They are global values; each material may override them in
its library entry.

`clips` is a mapping keyed by clip name, each entry a mapping of that clip's
own settings, so far only `frames` (owner decisions 2026-10-11, settings
design D-17, D-22, D-31 and D-34). Per-clip values are set in files only.
Entries merge by clip name across the layers, the loaded sheet's included,
and a higher layer's `null` clears a lower one's count. An entry naming a
clip the model does not have, or one not selected, is unused, though it is
still checked. An unknown key in an entry, or a bad count, is an error
naming the file, the key path (`clips.Jump.frames`) and the line.

**Layers.** Lowest first, each a partial set of settings; a setting a layer
leaves out falls through to the layer below (projects and camera design D-9,
D-11):

1. the shipped defaults, `defaults.yaml` inside the package;
2. the global file, the default project:
   - the user file, `config.yaml` in the configuration directory. It is
     optional: a missing user file is not an error;
   - or the one file `--config FILE` names, in its place. It must exist;
   - or none, with `--no-user-config`, as tests and scripts use;
3. a loaded sheet, `--settings-from FILE` (see
   [Scale and ground point](#scale-and-ground-point), *Reuse*);
4. the project file, `--project NAME`: `projects/NAME.yaml` in the
   configuration directory. It must exist;
5. the command-line options.

The configuration directory is `$XDG_CONFIG_HOME/moskophoros/` when that
variable is set and not empty, else `~/.config/moskophoros/`. Neither
`--config` nor `--no-user-config` moves it, so a project is found in the same
place whichever global file is used.

A project name is letters, digits, `.`, `_` and `-`, not starting with `.`,
and given without `.yaml`, so it names a file in `projects/` and nothing
outside it (projects and camera design D-16). Any other name, such as one
holding `/` or ending in `.yaml`, is a usage error naming it.

Loading is in memory, for that generation only. The tool never writes the
global file or a project file, and never creates `projects/` or a file in
it. The sheet records the resolved settings, never the project's name or a
settings file's name; where each value came from is never recorded, so
identical resolved settings give identical bytes.

**Merge rules.**

- `auto` is a value. `cell: auto` is the automatic cell: fitted with the
  pixels per meter in force, from `--ppm` or a loaded sheet, else 64×64 with
  auto-fit. So the shipped defaults never turn `--ppm`-only sizing into a
  fixed cell. Any layer may set `auto`, and `--cell` accepts it.
- `null` means none for `palette` and `materials`, as `--no-palette` and
  `--no-materials` do.
- A project value acts exactly as its explicit option would, including
  against a loaded sheet: `cell` behaves like `--cell` after
  `--settings-from`, and a palette or library follows the reuse table under
  *Reuse*. A command-line option still beats it.
- A value from the global file or the shipped defaults is only a default,
  whether the global file is the user file or a `--config` file. A loaded
  sheet records every one of these settings and sits above both, so they
  apply only without one.
- Per-clip frame counts merge by clip name: the global file's, then the
  loaded sheet's, then the project's.
- The library is one setting, a path, and replaces whole. It is validated
  against the palette in force, wherever each came from.
- `auto` for `ppm` or `ground_px` is the automatic value: it clears a
  reused or lower value and fits, as `cell: auto` does for the cell, and
  `--ppm auto` and `--ground-px auto` accept it too.
- `null` for `pitch`, `camera.direction`, `directions` or `start_angle`
  takes that value from the view's preset in force (*The view*). `blender: null` discovers Blender as
  without `--blender`.
- The app settings, `blender` and `any_blender`, layer like any setting,
  but no sheet records them, they never reach its fingerprint, and
  `--settings-from` never loads them. So the global file's app settings
  apply over a loaded sheet too, and a project's or an option's beat them.
  `--any-blender` sets `true`; only a file can set `false`.
- The other options, `--clip`, `--once`, `--settings-from`, `--work-dir`,
  `--config`, `--no-user-config` and `--project`, are not settings.

**The view.** The view is one state: a preset marker, `topdown`, `side`,
`iso`, `iso-true` or `custom`, and three values, the camera's direction, the
direction count and the start angle, each either the preset's or an override
(projects and camera design D-12, D-16). `pitch` and `camera.direction` are
two spellings of one value, the direction: a `pitch` p sets the direction
`(0, −sin p, −cos p)`. A file giving both, with any values, `null` included,
in either order, is a usage error (exit 2) naming the file, the later key and
its line, and so is `--pitch` with `--camera-direction`; nothing is written.
The shipped defaults list both as `null`: they set the starting state and are
not such a layer. The camera's roll and position are ordinary settings, not
part of the view state. The layers apply from the weakest up:

1. The shipped defaults set `iso`, with every value the preset's.
2. A loaded sheet is a snapshot: it sets its recorded marker, `custom`
   included, and its recorded values, each counted as the preset's. So the
   global file's view, below it, never applies over it.
3. In each other layer, a `view` applies first, whatever its place in the
   file: it sets the preset and every value to the preset's, replacing any
   lower layer's values. Then a non-null `pitch` or `camera.direction`,
   `directions` or `start_angle` is an override, and a `null` resets that
   value to the preset's. While the marker is `custom`, from a loaded sheet, a `null` has
   no preset to reset to: it is a usage error naming the file, the key and its
   line, unless the same layer gives a `view`. The command line is the last
   layer, `--view` applying before `--pitch` or `--camera-direction`,
   `--directions` and `--start-angle`.
4. After the last layer, the recorded marker is the preset's name when every
   value is the preset's, else `custom`.

So `view: topdown` with `pitch: null` in one layer gives `topdown`;
`view: iso` with `pitch: 45` gives `custom` with pitch 45's direction; a
lower `pitch: 45` under a higher `camera.direction: null` gives the preset's
direction, as does a lower `camera.direction` under a higher `pitch: null`;
and an `iso` sheet reloaded with nothing above it records `iso`, with its
JSON and fingerprint unchanged.

**Files.** The global file and a project file share one schema: either may
set any setting in the table above, and a project file sets only what it
lists. Each is read through the strict YAML reader
(see [Material libraries](#material-libraries)) and is a mapping of
settings; an empty mapping, `{}` or `version: 1` alone, sets nothing, while
an empty file, or one of comments only, is an error. Errors name the global
file by its path, as `the user settings '…'` or `--config '…'`, and a project
file by its name and path, as `--project 'look' ('…/projects/look.yaml')`. `version: 1` is optional at its top. A key the table above does
not list, such as a misspelt `fame` or a `shade.ao_radius`, an unknown
version, a value of the wrong type or out of range, or any YAML error is a usage error
(exit 2) naming the file, the key and the line. A path inside a settings file
resolves relative to that file's directory, with a leading `~` expanded,
whether a palette, a library or the `blender` executable;
paths on the command line resolve as before. Every path a settings file
supplies must be one the file system can name: one holding a NUL character
or a lone surrogate (from a `\uD800` escape) is refused while the file is
read. The raw value is checked before `~` is expanded and again after it is
resolved, and anything the expansion or resolution raises is the same
error; a `~user` prefix naming no user is left as written. Every participating file is read and checked first, but only the
palette and library that survive the merge are read, and only the Blender
executable that survives is checked, so an overridden path need not exist. Any failure to read a palette or library a settings file
names, whether missing, a directory, without permission, a name too long or
a loop of links, is a usage error naming the settings file, the key and its
line, such as
`--config 'look.yaml': palette (line 3, column 1) '/art/p.gpl': cannot be read: …`.
A `blender` setting that names no executable file is a backend error
(exit 5), as `--blender` is, naming the settings file, the key and its line:
`--project 'look' ('…/projects/look.yaml'): blender (line 2, column 1) names '/opt/b', which is not an executable file; no other Blender is tried`.
A failed version probe or a refused Blender version stays a backend error
too.

```yaml
version: 1
view: iso               # topdown, side, iso or iso-true
pitch: null             # 0 to 90; null: the view's; or camera.direction
camera:
  direction: null       # [x, y, z], each -1 to 1, not all 0; null: the view's
  roll: 0               # -1 to 1, a fraction of a half turn
  position: null        # [x, y, z] meters from the ground point; unused
directions: 8           # 1 to 64; null: the view's
start_angle: null       # degrees; null: the view's
model_yaw: 0
ppm: 40                 # or auto
cell: 48x48             # or auto
ground: [0, 0, 0]       # meters
ground_px: auto         # or [x, y], a cell pixel corner
supersample: 8
reduce: mode            # or plain
root_motion: error      # or keep
fps: 12
palette: ~/palettes/vince-144.gpl
materials: robot-library.yaml   # relative to this file
edges: hard             # soft: a pixel takes its block's mean alpha
previews: true          # false: write no animated previews
normals: true           # false: write no normal map
depth: false            # true: write the depth map
light:                  # a preview light; set any of them, the rest fall through
  position: [-20, 30, 40]  # sheet pixels from the ground point; null: no light
  intensity: 1.0
  ambient: 0.3
frames: 8               # or auto
clips:
  Jump: {frames: 6}     # its own count; auto: by duration; null: take frames
shade:                  # set any of them; the rest fall through
  ao_distance_m: 1.2
  occlusion_weight: 0.5
  convexity_weight: 0.0
  range: [120, 188]
ramp:                   # generated ramps' formula (setting B is shipped)
  lightness_step: 0.09
  hue_shift_deg: -35
  chroma_fade: 0.6
blender: /Applications/Blender.app/Contents/MacOS/Blender  # null: discovered
any_blender: false
```

### Option validation

Each of these is a usage error (exit 2) unless stated otherwise (owner
decision 2026-10-01):

- A numeric option given `nan` or `inf`.
- `--ppm` that is not a finite number greater than 0, nor `auto`.
- `--ground-px` coordinates that are not whole numbers 0 or greater, nor
  `auto`. Whether
  the point lies inside the cell is an [overflow](#scale-and-ground-point)
  question, not a usage one.
- The same clip named twice with `--clip`, or twice with `--once`.
- A `--once` naming a clip absent from an explicit `--clip` list. Without
  `--clip`, a `--once` naming a clip that does not exist is an
  [input error](#input-contract).
- A single-value option given more than once; the last value does not win.
- A `--reduce` value other than `plain` or `mode` (owner decision 2026-10-04).
- An `--edges` value other than `hard` or `soft`; in a settings file, an
  `edges` that is not one of those two strings, named with the file, the key
  and its line; in a reused sheet, a `settings.style.edges` that is missing
  or not one of them (alpha design D-9).
- `--pitch` together with `--camera-direction`; `--camera-direction` not
  three finite numbers `X,Y,Z` each from −1 to 1, or all 0;
  `--camera-roll` not a finite number from −1 to 1; `--camera-position` not
  three finite numbers `X,Y,Z` (projects and camera design D-7, D-12, D-16).
- `--palette` together with `--no-palette`, or either option repeated.
- `--materials` together with `--no-materials`, or either option repeated.
- `--preview` together with `--no-preview`, or either option repeated.
- `--normals` together with `--no-normals`, or either option repeated; in a
  file or a reused sheet, a `normals` that is not `true` or `false`.
- `--depth` together with `--no-depth`, or either option repeated; in a file
  or a reused sheet, a `depth` that is not `true` or `false`.
- `--light` together with `--no-light`, or either option repeated; `--light`
  not three finite numbers `X,Y,Z`; `--light-intensity` not a finite number
  0 or greater; `--light-ambient` not a finite number from 0 to 1. In a
  settings file or a reused sheet the same values are refused, `light.position`
  being `null` or a list of three finite numbers, never booleans (lighting
  sheet design D-18, Review 2's S-3).
- `--frames` not a decimal whole number 1 or more, nor `auto`; in a file, a
  count that is not a YAML integer 1 or more (never `8.0`, `"8"` or a
  boolean), nor `auto`, nor (for a clip) `null`. There is no upper bound;
  the sheet and GIF limits still apply (settings design D-34).
- `--ao-distance` not finite and greater than 0; `--ao-samples` not a whole
  number from 1 to 128, the limit stated (settings design D-42); a
  `--occlusion-weight` or `--convexity-weight` not finite and 0 or greater; a
  `--shade-range` not two integers with `0 ≤ LO < HI ≤ 255`. The same limits
  apply to the `shade` settings in a [settings file](#settings-files).
- `--ramp-step` or `--ramp-fade` not a finite number from 0 to 1, or
  `--ramp-hue-shift` not one from −180 to 180; the same limits apply to the
  `ramp` settings in a settings file and a reused sheet (material styling
  design D-33).
- A bad [settings file](#settings-files), or a missing or unreadable
  `--config` file or project file. These errors name the file, the key and
  the line; a missing project file's error names its path, and nothing is
  created. The view, scale and framing settings and the app settings are
  refused as their options are: a `view` that is not a preset name; a
  `pitch` not from 0 to 90, a `camera.direction` not three finite numbers
  each from −1 to 1, or all 0, `directions` not a whole number from 1 to 64,
  or `start_angle` not a finite number, other than `null`; a `pitch` and a
  `camera.direction` in one file, whatever their values; a `camera.roll` not
  a finite number from −1 to 1; a `camera.position` not three finite numbers
  nor `null`; a `model_yaw` not
  a finite number; a `ppm` not finite and greater than 0, nor `auto`; a
  `ground` not three finite numbers; a `ground_px` not two whole numbers 0
  or greater, nor `auto`; a `supersample` not a whole number from 1 to 16; a
  `reduce` or `root_motion` not one of its values; a `blender` not a path or
  `null`; an `any_blender` not `true` or `false`. Booleans and numeric
  strings are never numbers.
- Over a loaded sheet whose view is `custom`, a project file's `null` for
  `pitch`, `camera.direction`, `directions` or `start_angle` without a
  `view` in the same file,
  named with the file, the key and its line (projects and camera design
  D-16).
- `--config` given more than once, or together with `--no-user-config`;
  `--project` given more than once, or with a name that is not a project
  name (see [Settings files](#settings-files), *Layers*).
- Over a loaded sheet without `--clip`, a `--once` naming a clip outside the
  loaded clip list (owner decision 2026-10-11, settings design D-27).
- A `--materials` file whose name does not end in `.yaml` or `.yml`, in any
  case, `.json` included. The error says libraries are YAML, and comes before
  the file is read (owner decision 2026-10-11, settings design D-11).
- A bad palette file: see [Palette inputs](#palette-inputs). These errors name
  the file and, for text errors, the line, and precede every Blender invocation,
  including its version probe (owner decisions 2026-10-04).
- A bad material library, or a library without a palette, or a reused library
  beside an explicit option that would change its palette: see
  [Material libraries](#material-libraries). These errors name the file and the
  material or entry, and precede every Blender invocation, including its
  version probe (owner decisions 2026-10-07, D-8 and D-24).

Every settings error, including a bad palette or library a settings file
names, comes before any Blender invocation, including its version probe
(owner decision 2026-10-11, settings design D-17). Errors that depend on the
model's measurements, such as fitting and overflow, keep their own place and
exit codes.

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
| 4 | Overflow: the subject does not fit a fixed cell and scale, or, with the depth map written, its depth does not fit the map's range. |
| 5 | Backend error: Blender missing, wrong version, or failed, including a frame with a stack of see-through surfaces deeper than the capture renders (see [Capture](#capture)). |
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

Material identities are read from the glTF JSON on every run, whether or not
a material library is used (D-3, D-18, owner decisions 2026-10-07). Names
compare exactly, including case; equal names are one identity. An absent or
empty material name, or a primitive without a material, has no identity and
is not an error. Alpha mode is reported as given, defaulting to `OPAQUE`
when absent; unlisted values are left to Blender's importer. A primitive
without a material also reports `OPAQUE`.

`gltf.read_material_identities` is a pure reader of decoded JSON;
`read_glb` exposes its records as `Subject.primitive_materials`. Records
include the original node, mesh, primitive and material indices, name
(`None` for no identity) and alpha mode. They include scene roots and all
their descendants, ordered by ascending node index, then primitive index.
A shared mesh has separate records for each reached node instance; duplicate
names retain separate primitive records and material indices, including 0.
Primitives belonging only to other scenes or unreachable meshes are excluded
from the result, while input validation applies to the entire document.

Checks, each an input error (exit 3) naming the file and the problem:

- the file cannot be read, or is not binary glTF 2.0
- the file has no scenes
- the structure the tool reads is malformed (owner decision 2026-10-01): a
  `scene`, node, child, animation channel, sampler or accessor reference
  names an object that does not exist; the node hierarchy is not a forest
  (a node with two parents, or a cycle); or an animation sampler's input
  accessor lacks the one-element `min` and `max` that give the clip's range.
  Other glTF rules are left to Blender's importer.
- a material's present `name` is not a string, or a primitive's present
  `material` or a node's present `mesh` is not an integer index into the
  corresponding array (booleans are not indices); present `materials`,
  `meshes` or a mesh's `primitives` is not an array; or a material, mesh or
  primitive entry is not an object. These checks apply even to unused
  entries and other scenes. Optional absent arrays are valid when nothing
  references them (material styling D-18; structural contract above).
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

**The camera is set once; each direction turns the subject in front of it**
(projects and camera design D-3, D-7, D-8, D-10). The camera is orthographic
and centered on the ground point. It looks along its direction, with a roll,
and the light stays fixed to it.

**Basis.** Let `f` be the normalised `camera.direction`, the way the camera
looks, in subject coordinates.

- The unrolled axes: `r₀ = normalise(f × Y)` and `u₀ = r₀ × f`. When `f`'s
  horizontal part is exactly zero, so it looks straight down or up, `r₀ = +X`.
- The roll turns them about `f` by `ρ = roll · π` radians, giving screen
  right `r` and screen up `u`:
  - `r = r₀·cos ρ + u₀·sin ρ`;
  - `u = u₀·cos ρ − r₀·sin ρ`.

  A positive roll turns the camera counter-clockwise as it looks, so the
  picture turns clockwise: at `roll = 0.5`, `r = u₀` and `u = −r₀`, and a
  point at the top of the picture is now at its right. Roll −1 and +1 give the
  same picture.
- The rolled `r` and `u` are used for everything that makes the picture: the
  render transform, the measured bounds and the orthographic framing. Only
  the reference heading for each direction's turn uses `f` alone.
- `camera.position` is unused by the orthographic camera. It is recorded as
  given, with no warning (D-16).

**Pitch is a shorthand.** Pitch `p`, the angle between the viewing direction
and the ground (0° looks horizontally, 90° straight down), sets the direction
`(0, −sin p, −cos p)` (D-12). With roll 0 it gives the pitch-only camera
exactly: screen right +X and screen up `(0, cos p, −sin p)`, with the camera
in direction `(0, sin p, cos p)` from the ground point. At 90° up is −Z,
continuous with lower pitches, so top-down has no ambiguous roll.

**Normalising.** The tool divides a direction by its length, computed
without squaring its components, so a tiny one such as `(1e-300, 1e-300, 0)`
is normalised too. A direction whose length is already within `1e-12` of 1 is
kept exactly as given, so normalising twice changes nothing, a pitch's
direction is kept bit for bit, and a recorded direction reloads unchanged.

**Exactness.** The products are written so a direction a pitch or preset
sets gives exactly the pitch camera's basis, bounds, camera transform and
pixels. Measuring keeps one detail of the pitch camera's floating point: it
evaluated the vertical part of a straight-down camera's up as `cos 90°`,
about `6e-17`, not 0. So a camera looking straight down without a roll
measures with that up, which can move a fitted cell by one pixel; any roll,
and every other direction, measures with the exact axes.

**Direction angles are measured from the camera.** For direction `i` of `N`:

```
θᵢ = (start + i · 360 / N) mod 360
```

The subject is rotated by `θᵢ + model-yaw` about the vertical axis through the
ground point, measured from the camera's unrolled reference heading: at
`θ = 0` the subject's +Z faces the camera's horizontal heading, `−(f_x, 0,
f_z)`, or +Z when the camera looks straight down or up (D-10). So the
direction's compass heading changes no orthographic picture and no label;
only its steepness and the roll do. The rotation is counter-clockwise when
seen from above (+Y), which gives these facings for a camera looking down or
level with no roll:

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

Labels come from `θ` alone (D-18) and are recorded only for angles that are
exact multiples of 45°; any other angle has label `null`. Their
screen-relative description holds for cameras that look down or level with
no roll. With a roll or an upward camera the picture turns, but no label
changes: at `roll = 1` the picture is upside down, so `east` (90°), facing
+X, faces screen left and keeps its name; looking straight up,
`f = (0, 1, 0)`, `r = +X` and `u = (0, 0, 1)`, so `south` (0°), facing +Z,
faces up the screen and keeps its name. Directions appear in the sheet in
index order.

### Presets

| Preset | Pitch | Direction | Directions | Start angle |
|---|---|---|---|---|
| `topdown` | 90° | `(0, −1, 0)` | 8 | 0° |
| `side` | 0° | `(0, 0, −1)` | 2 (east, west) | 90° |
| `iso` | 30° | `(0, −sin 30°, −cos 30°)` | 8 | 0° |
| `iso-true` | arctan(1/√2) ≈ 35.264° | its pitch's | 8 | 0° |

A preset is a shorthand: it sets its pitch's direction, the direction count
and the start angle (D-12). Explicit `--pitch` or `--camera-direction`,
`--directions` and `--start-angle`, or the settings `pitch` or
`camera.direction`, `directions` and `start_angle`, override the preset's
values, and the recorded preset name is then `custom`. The roll and the
position are no part of a preset and never make the view `custom`. How a settings file's `view` and these
values layer is under [Settings files](#settings-files), *The view*.

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

**Frame counts.** A clip's frame count is its own value, a count or `auto`,
when it has one; else the global `frames` (`--frames`, or a
[settings file](#settings-files)), whatever layer each came from (owner
decisions 2026-10-11, settings design D-13, D-26, D-31). `auto` samples by
duration.

**Sample times.** With `n = max(1, floor(d · fps + 0.5))`, for a clip whose
count is `auto`:

| Clip | Frames | Sample times | Frame duration | `time_scale` |
|---|---|---|---|---|
| looping (default) | `n` | `t0 + k·d/n`, for k = 0 … n−1 | `d/n` | 1 |
| one-shot (`--once`) | `n + 1` | `t0 + k·d/n`, for k = 0 … n | `d/n` | 1 |
| `d = 0`, or the `static` clip | 1 | `t0` (0 for `static`) | `1/fps` | 1 |

With a count `N`, the clip is retimed so every frame lasts exactly `1/fps`
(settings design D-13, D-33, D-38):

| Clip | Frames | Sample times | Frame duration | `time_scale` |
|---|---|---|---|---|
| looping, `N ≥ 2` | `N` | `t0 + k·d/N`, for k = 0 … N−1 | `1/fps` | `d·fps/N` |
| one-shot, `N ≥ 2` | `N` | `t0 + k·d/(N−1)`, for k = 0 … N−1 | `1/fps` | `d·fps/(N−1)` |
| `N = 1`, loop or one-shot: a still | 1 | `t0` | `1/fps` | 1 |
| `d = 0`, or the `static` clip | 1 | `t0` (0 for `static`) | `1/fps` | 1 |

A loop leaves out its endpoint, which would duplicate its first frame. A
one-shot keeps its final pose: its last sample is `t1` itself. Sampled by
duration, samples are spaced evenly over the exact duration, so the
effective rate `n/d` can differ slightly from `--fps`; the JSON records each
clip's actual frame duration and its `time_scale`, the retiming factor. How
long to hold a one-shot's last frame is the consumer's choice. A clip of zero
duration and `static`, the synthetic clip with no animation index, always
have one frame, whatever their count (D-25); an authored animation named
`static` is an ordinary clip.

**Warnings** (settings design D-25, D-26, D-41), neither an error nor a
change to the output:

- When `--frames` or a project file sets the global count, as a count or
  `auto`, one warning names every selected clip whose own value, a count or
  `auto`, beats it, even an equal one. Zero-duration and `static` clips are
  left out. A global from the shipped defaults, the global file or a loaded
  sheet warns nothing.
- A selected zero-duration or `static` clip whose own count is above 1 is
  named as keeping one frame.
- A `clips` entry for a clip not selected warns nothing.

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

Fitting bounds only a subject's extent on screen, never its depth, so a valid
fit can hold depths the depth map cannot encode (lighting sheet design R-1).
When the depth map is written, or previews are on and a light is placed
(the lit previews use the encoded depth), a covered pixel, any whose alpha
is above 0 (alpha design D-11), whose reduced depth
lies outside −2047.9375 to +2047.9375 sheet pixels is also an overflow
(exit 4), raised before anything is published (D-21, D-24). The two share
one check and one message. The message gives the
scale and the supported range and suggests a smaller `--ppm`, then lists
each offending clip, direction and sample time with the lowest and highest
depth of its covered pixels in sheet pixels. Depth is never clamped or
rescaled. A run that writes no depth map and no lit preview is not checked:
with previews off, a placed light imposes nothing.

**Reuse.** `--settings-from FILE` loads the `settings` object of an earlier
sheet's JSON as one in-memory layer of [settings](#settings-files), applying
every recorded setting that affects the output (owner decisions 2026-10-11,
settings design D-15, D-16, D-19 and D-28):

- view and model yaw
- the camera, `settings.camera`: its direction, roll and position
- fps and supersample
- ppm, cell, ground point and ground pixel
- root-motion mode
- whether previews are written, `settings.previews`, and whether the normal
  and depth maps are, `settings.normals` and `settings.depth`
- the preview light, `settings.light`
- the shading values, `settings.shade`: the ambient occlusion distance and
  samples, the occlusion and convexity weights, and the shade range
- the style: its reduction, edges rule and inline palette,
  `settings.style.reduce`, `settings.style.edges` and
  `settings.style.palette`, and its inline material library,
  `settings.style.materials`
- the clip selection and its one-shot marks, `settings.clips`

This makes scale, cell and ground pixel fixed. Options given explicitly, and
project values, override the reused values; the global file, whether the user
file or a `--config` file, and the shipped defaults never do (projects and
camera design D-11). A project's `ppm`, `ground`, `ground_px`, `model_yaw`,
`camera.roll`, `camera.position`, `supersample`, `reduce` and `root_motion`
replace the reused values as their options do; `ppm: auto` or `--ppm auto`, and `ground_px: auto` or
`--ground-px auto`, drop the reused scale or ground pixel and fit them again
in the cell in force. The app settings, `blender` and `any_blender`, are
never recorded or loaded, so the global file's apply over a loaded sheet. An explicit `--reduce` replaces the reused reduction,
retaining the palette, and an explicit `--edges`, or a project file's
`edges`, replaces the reused edges rule (alpha design D-9). `--palette FILE` replaces the reused palette;
`--no-palette` drops it. Reuse applies the recorded ordered colours without
opening the original palette file and keeps its record unchanged. `--preview`
writes previews over a sheet made without them, and `--no-preview` skips them
over one made with them; `--normals` and `--no-normals`, and `--depth` and
`--no-depth`, do the same for the normal and depth maps, and `--no-light`
drops a reused light. Reuse reads only the sheet's `schema` and `settings`: the normal
map is made again from the model, never read from an earlier file, and a
document holding only those two keys is enough.

The clip selection (owner decisions 2026-10-11, settings design D-19 and
D-27):

- The loaded sheet supplies the clip list, in sheet order, and its one-shot
  marks.
- An explicit `--clip` replaces the whole list, and `--once` then comes from
  the command line, as without a loaded sheet.
- Without `--clip`, an explicit `--once` replaces the loaded marks: the clips
  it names are exactly the one-shots. Each name must be in the loaded clip
  list; a name that is not is a usage error.
- Without `--clip` or `--once`, the loaded list and marks stay.
- Each recorded clip's own frame count, a count, `auto` or `null`, loads
  with the global `settings.frames`. Per-clip counts merge by clip name, so
  an explicit `--clip` replaces the selection and its marks but not the
  counts: a re-selected clip keeps its loaded count. A `--frames` reaches
  every clip whose value is `null` (settings design D-31, D-39).
- The final selection is checked against the model: a retained loaded clip
  the model no longer has is an input error (exit 3) naming the clip. A clip
  that `--clip` replaced need not exist.

Each recorded generated ramp keeps its recorded `indices` without being
generated again. Only when an explicit value, from a project file or an
option, changes a reused ramp's effective formula values is that ramp
generated again from its recorded properties; the global file sits below the
loaded sheet, so it never changes a loaded sheet's ramps (material styling
design D-33). The
global formula reloads from `settings.ramp`.

Only the current sheet schema, `moskophoros.sheet/14`, loads (owner decision
2026-10-11, settings design D-24; projects and camera design D-14, D-17). A
sheet of any other schema, `/1` to `/13` included, is a usage error naming
its schema and the supported one. Nothing
defaults a missing `settings.style.edges`. A file
that is unreadable, or not a sheet document, is a usage error.

The reused library follows the palette's pattern (owner decisions 2026-10-07,
D-19 and D-24). It is applied without opening the original library file and
keeps its record unchanged. `--materials FILE` replaces it, and
`--no-materials` drops it. A reused library is kept only with the palette it
was written for:

| Library | Palette | Result |
|---|---|---|
| reused | reused | allowed |
| reused | explicit, with the same ordered colours | allowed; the palette's record names the new file |
| reused | explicit, with other colours (reordered, added, removed or changed) | usage error: a new palette would silently recolour every ramp. Give `--materials FILE` too, or `--no-materials` |
| reused | `--no-palette` | usage error: a library needs a palette. Give `--no-materials` too |
| explicit | reused or explicit | allowed, validated against the palette in force |
| `--no-materials` | any | the reused library is dropped, and the ordinary looks apply |

"Different" compares the palettes' ordered colour lists, never file names or
hashes, which stay provenance. A deliberate palette swap that keeps a library
is a variant, deferred with palette swaps. The recorded library is validated
against the recorded palette before any override, and an invalid one is an
error even when an override drops or replaces it; a library that is dropped or
replaced is never checked against another palette. The final library and
palette are validated before any Blender invocation.

The reused view is a snapshot in the view's layers (see
[Settings files](#settings-files), *The view*). An explicit `--view`, or a
project's `view`, replaces the whole reused view: that preset's values
apply, then any `--pitch` or `--camera-direction`, `--directions` or
`--start-angle`, or the project's `pitch` or `camera.direction`,
`directions` or `start_angle`, on top, exactly as without reuse. Without
one, the reused view stays, its recorded direction among its values, and an
explicit or project direction, `directions` or `start_angle` overrides its
value and makes the preset `custom`. A project's `null` resets that value to the reused preset's,
and over a reused `custom` view is a usage error unless the project gives a
`view`.

The reused `settings` are checked strictly. Every reused field must be
present with a value its option would accept, and `pixels_per_meter`, `cell`
and `ground_px` must be set. `view` must be an object with exactly `preset`,
`directions` and `start_angle_deg`. `camera` must be an object with exactly
`projection`, which must be `orthographic`; `direction`, a list of three
numbers, never booleans, each from −1 to 1, normalised: its length within
`1e-12` of 1, and it is kept exactly as recorded; `roll`, a number from −1 to
1; and `position`, `null` or a list of three finite numbers.
`cell` is the fitted `{width, height}` record, never `auto`. `previews`,
`normals` and `depth` must be `true` or `false`. `light` must be an object
with exactly `position`, `null` or a list of three numbers, never booleans,
`intensity` and `ambient`, each a value its option would accept. `clips` must be a nonempty list of distinct clips, each
an object with exactly `name`, a nonempty string, `loop`, `true` or
`false`, and `frames`, the clip's own frame count as given: an integer of 1
or more (never a boolean), `"auto"`, or `null` to take the global
`settings.frames`; it is checked even when `--clip` replaces it. `shade` must be an
object with exactly `ao_distance_m`, `ao_samples`, `occlusion_weight`,
`convexity_weight` and `range`, each a value its option would accept:
numbers, never booleans, and `ao_samples` an integer from 1 to 128.
`style` must be an object with exactly `reduce`, a value
`--reduce` accepts, `edges`, a value `--edges` accepts, `palette`, either
`null` or an object with exactly
`source`, `sha256` and `colors`, `materials`, either `null` or an object with
exactly `source`, `sha256`, `ramps`, `default` and `materials`, and the
library's own `shade` after `default` when it gave one. The source is a nonempty base filename, never a path; the
digest is exactly 64 lowercase hexadecimal digits; colours are 1 to 255 unique
canonical lowercase `#rrggbb` strings in their recorded order. The palette
module applies its shared count, RGB and uniqueness checks. A library record's
`ramps`, `default` (a ramp name, or `null` for none) and `materials` are
validated by the library module exactly as a library file is, against the
recorded palette, and a record beside a `null` palette is an error. A
recorded generated ramp must also carry `indices`, exactly `bands` valid
palette indices, checked without generating; the recorded library is
validated even when `--materials FILE` replaces it or `--no-materials` drops
it. `ramp` must hold exactly `lightness_step`, `hue_shift_deg` and
`chroma_fade`, each a value its option would accept.
`shade.range` is an array of exactly two JSON integers, never booleans or
floating-point numbers, with `0 ≤ lo < hi ≤ 255`; it is validated even when
`materials` is `null`. All reused fields are validated before any
override, including `--reduce`, `--edges`, `--palette`, `--no-palette`, `--materials`,
`--no-materials`, `--clip`, `--once`, `--preview`, `--no-preview`,
`--normals`, `--no-normals`, `--depth`, `--no-depth`, `--light`,
`--no-light`, `--light-intensity`, `--light-ambient` and the shading
options, and project values (owner decisions 2026-10-04,
2026-10-07, 2026-10-11, 2026-10-12).
A missing or invalid field, or an unknown field inside `settings`, is a usage
error naming it. The rest of the sheet is not checked beyond its `schema`
(owner decisions 2026-10-01).

## Pipeline

(V-4, V-5)

Four stages, each depending only on the previous stage's output. Frames pass
between stages keyed by frame address. Capture writes files because it runs in
Blender's process; in slice 1 the later stages pass arrays in memory. Per-stage
caching is deferred. From stylize on, each reduced colour frame carries its
reduced normal and depth maps (see [Normal and depth maps](#normal-and-depth-maps)),
which cleanup passes through and export receives; export writes the normal
map and, when asked, the depth map from them.

#### Frames into stylize

A frame going into stylize carries its colour pixels and, beside them,
further named buffers of the same height and width (`ImageFrame.buffers`).
The command loads every buffer the capture result names for a frame: `color`
becomes the frame's pixels; `matid` and `shade` are decoded into the
identity and shade arrays below, `normal` and `depth` into the normal and
depth arrays, and the front buffers into the front arrays; and any other
buffer is carried under its own name as an
8-bit RGBA array. The colour reduction reads only the colour, unless it is
given a material library, which also reads the identity and shade arrays
(see [Material ramps](#material-ramps)). Independently of that choice, both
reductions reduce a frame's normal and depth arrays when it carries both, as
[Normal and depth maps](#normal-and-depth-maps) specifies; a frame must carry
both or neither, and one carrying only one of them is a `ValueError` naming
the frame.

Four buffer names are reserved, for material identity, shade, normal and
depth, with this interface:

- Per asset, an **identity list** (`sampling.Identities`): each distinct name
  of an eligible (`OPAQUE`, `MASK` or `BLEND`) material, in a fixed order (by
  its lowest glTF material index), then the no-identity class. A translucent
  `BLEND` material has an identity like any other, and a name used by opaque
  and translucent materials is one identity (alpha design D-15). Index `i` names
  the `i`th material name; the last index, `Identities.no_identity`, which
  equals the number of names, is the no-identity class. Stylize receives the
  list through its `identities` argument.
- Per frame, under `identity` (`sampling.IDENTITY`), an **identity array**:
  `int32`, shape `(height, width)`, each value an index into the identity
  list or `sampling.BACKGROUND` (−1), which is never an index. Under `shade`
  (`sampling.SHADE`), a **shade array**: `uint8`, shape `(height, width)`.
- Per frame, the **front layer** (alpha design D-6, D-12): under
  `front_color` (`sampling.FRONT_COLOR`), its straight colour as an 8-bit
  RGBA array, alpha 255 where it is present; under `front_alpha`
  (`sampling.FRONT_ALPHA`), its alpha `q` as `uint16`, shape
  `(height, width)`, 0 where it is absent; under `front_present`
  (`sampling.FRONT_PRESENT`), its presence as `bool`, from the front
  colour's alpha and never from `q`; and under `front_identity` and
  `front_shade` (`sampling.FRONT_IDENTITY`, `sampling.FRONT_SHADE`), the
  front-most translucent surface's identity (`int32`) and shade (`uint8`),
  decoded as the back's are. The frame's pixels are the back layer.
- Per frame, under `normal` (`sampling.NORMAL`), a **normal array**:
  `float32`, shape `(height, width, 3)`, the unit normal of the surface each
  pixel sampled, in the frame's camera space (+X screen right, +Y screen up,
  +Z toward the viewer), and `(0, 0, 0)` where no surface was hit. Under
  `depth` (`sampling.DEPTH`), a **depth array**: `float32`, shape
  `(height, width)`, that surface's depth in meters toward the viewer from
  the ground point's camera depth, any finite value, and NaN where no
  surface was hit. Both describe the front-most surface that is not a hole,
  the front layer's where it is present (alpha design D-11). Both decode the [capture's](#capture) buffers exactly:
  the depth is the buffer's 32-bit float, and each normal component
  `2 · v / 65535 − 1` of its 16-bit value `v`.
- The command decodes and validates both arrays; stylize never does. It
  joins the render result's material table
  ([result format](#result-format)) with the glTF material identities
  ([Input contract](#input-contract)): the identity list holds each distinct
  name of an `OPAQUE`, `MASK` or `BLEND` material that a primitive of the
  selected scene uses, by lowest material index. A pixel of background
  (alpha 0) decodes to `BACKGROUND`; a pixel showing a material of an alpha
  mode glTF does not define, an unnamed material or a primitive without one
  decodes to the no-identity class. The front identity and shade arrays
  decode the same way, and stylize uses them to ramp the front layer
  ([Two layers](#two-layers)). The shade array is the shade buffer's red channel.
  A table entry naming a material the model does not have is a backend
  error (exit 5), like any invalid capture result. The normal and depth
  arrays are the command's to decode too.

Frames are loaded one at a time, as stylize reduces them. Stylize returns a
reduced colour frame carrying only its reduced normal and depth maps, and
releases a frame's supersampled colour and every other buffer once it is
reduced, before the next frame is loaded, so at most one frame's
supersampled buffers are held; the maps are new arrays, never views of them.
Cleanup and export receive the reduced colour frames and their maps.

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
   the ground point projected to `(gx·s, gy·s)`: the back layer's colour,
   material-ID and shade buffers, the front layer's colour, alpha,
   material-ID and shade buffers, and the front-most surface's normal and
   depth, from flat, unlit Cycles renders of one shared camera sample per
   pixel (below).

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

**Render settings** (alpha design ALPHA-1, ALPHA-4, *The pipeline with
alpha*, D-8). The renders of a frame give every buffer from **one shared
camera sample per pixel**, so each buffer describes exactly the surfaces of
its layer at that sample. Workbench is not used.

- Cycles on the CPU, 1 sample per pixel, adaptive sampling off, seed 0 (not
  animated), pixel filter Box of width 0.01 px (the sample sits at the pixel
  centre), sample clamping off, denoising off.
- Every light bounce 0; `min_transparent_bounces` and
  `transparent_max_bounces` both 64; the view layer's
  `pass_alpha_threshold` 2^-30.
- Film transparent, dither 0, view transform `Standard`, look `None`,
  exposure 0, gamma 1, display sRGB.
- These parameters are recorded in the result's and the sheet's `color`
  record (below).

**Capture output:** nine PNGs per frame, whether or not a material library
is used, a light is placed or a map is written (material styling D-13;
lighting sheet design D-12; alpha design, *Capture transport and
provenance*): the back layer's colour, material-ID buffer and shade buffer,
each 8-bit RGBA; the normal and depth buffers, each 16-bit RGBA; and the
front layer's colour, material-ID and shade buffers, 8-bit RGBA, and its
alpha buffer, 16-bit RGBA (below). Each is written from pixels by the script's own PNG writer, with no
chunk but IHDR, IDAT and IEND, so no date or render-time text reaches a
buffer and identical frames are identical files; every `use_stamp_*` render
setting is off besides. The manifest format lists buffers by name, so further
buffers can be added without changing it.

- *Two layers* (alpha design D-6, D-12): at each sample, the **back layer**
  is the first opaque surface, and the **front layer** every translucent
  surface in front of it, combined by front-over-back compositing in linear
  colour into one straight colour and one alpha, with the front-most
  translucent surface's identity and shade. A cut-out hole is no surface at
  all. Either layer may be absent.
- *Coverage:* the one sample at each pixel centre decides whether each layer
  is present there: each layer's buffers cover exactly the same pixels, and
  are `(0, 0, 0, 0)` wherever it is absent. Each colour's alpha is
  therefore 255 or 0, never fractional: this replaces Workbench's
  antialiased coverage (alpha design D-5). Presence always comes from
  Blender's float data, the gated hits, and never from a quantized colour or
  alpha, so a front layer of tiny alpha is still present.
- *Colour:* each surface's **flat, unlit** material colour (alpha design
  D-8): no studio light, shading or shadow. It is straight 8-bit sRGB through
  Blender's `Standard` transform with dither 0, as the render's TGA holds it,
  where the render's float alpha shows a surface.

**Surfaces** (alpha design spikes 1 to 4, A-8). Every rendered surface's
shader is replaced, for the whole render phase, by one graph holding its
three renders' shaders, switched by a shared node group of two values,
`count` and `front` (alpha design spike 3's `group` switch), which Cycles
folds into each material. Each writes the surface's material-ID code,
shade, normal, depth and a hit flag, and the front layer's code, shade and
hit, to eight AOVs, each gated to the render it belongs to; the
replacements are removed and the original shaders restored when the phase
ends.

- *The back render* (both values 0): an opaque surface is
  `Mix(alpha, Transparent, Emission(colour))`, `alpha` 1 or a `MASK`
  material's chain; a `BLEND` surface is a pure `Transparent`, a hole. It
  gives the back colour, material ID, shade and hit.
- *The front render* (`front` 1), run only when the model renders a `BLEND`
  material: a `BLEND` surface is `Mix(alpha, Transparent, Emission(colour))`
  with its alpha chain, and an opaque surface `Mix(alpha, Transparent,
  Holdout)`, which stops the path and holds out its share. Its float alpha
  is then exactly the front layer's `f = 1 − Π(1 − αₖ)` over a body or the
  background alike, and its TGA, through the `Standard` transform as the
  back colour's, the front layer's straight colour, since Blender writes
  8-bit images un-premultiplied (alpha design spike 4). Its gated AOVs are
  the front-most translucent surface's `front_matid`, `front_shade` and
  `front_hit`; an opaque surface writes no front AOV but stops the pass.
  It runs with both transparent bounce limits one above 64: Cycles shades
  the surface a path ends at after its last transparent bounce without
  closures, so a holdout there would hold nothing out, and the count render
  (below) refuses any path that crosses more than 64 surfaces that let light
  through, so the path always reaches its opaque surface. A model without a
  `BLEND` material renders no front render, and its front buffers are
  empty.

- *Colour extraction,* from the shader the glTF importer built:
  - a Principled BSDF: the colour feeding its `Base Color` (a constant, or
    the importer's chain: a texture, its factor, vertex colours);
  - the `KHR_materials_unlit` core, `Mix(Light Path "Is Camera Ray",
    Transparent, Emission)`, alone or wrapped in a `Mix` with an alpha
    chain: the colour feeding the Emission's `Color`;
  - any other shape is a backend error (exit 5) naming the glTF material by
    index and by its name when it has one, and nothing is published.
- *Alpha* (alpha design ALPHA-2, D-1, D-3): a `MASK` material's alpha is
  the importer's own chain, `1 − (texture alpha × factor < alphaCutoff)`,
  with the cutoff 0.5 when the glTF gives none, so a texel is kept when its
  alpha is at least the cutoff. It is the extraction rule's: a Principled
  BSDF's `Alpha`, or the factor of the `Mix` wrapping the unlit core. A
  cut-out texel is a **hole**: no surface in any buffer, showing the surface
  behind it in all of them, or nothing. A `BLEND` material's alpha (alpha
  design ALPHA-4, D-1, D-3) is the importer's chain, taken by the same
  rule: the factor, the texture alpha, their product, or the vertex
  colour's alpha, which the importer stores in 8 bits. It is translucent,
  and a `BLEND` surface Cycles leaves no surface (α ≤ 2^-25, below) is a
  hole. The tool adds no transparency rule of its own. An `OPAQUE`
  material is captured opaque whatever its alpha.
- *The surface gate* (alpha design spike 2): every AOV is multiplied by a
  gate computed, in Math nodes, in the order Cycles computes the mix's
  transparency: `sat = clamp(α)`, `t = 1 − sat`, `v = 1 − t`,
  `g = 1 − (v < T)`, with `T` the view layer's `pass_alpha_threshold`.
  Cycles stops its passes exactly where `v > 0`, which is where `g = 1`, so
  the surface it selects writes each AOV exactly once and a hole writes
  none. The hit AOV is `g` itself, and the front hit likewise in the front
  render; a hit other than exactly 0 or 1, back hits not exactly on the
  back colour's surfaces, or a front render whose float alpha is above 0
  anywhere but on its hits, is a backend error (exit 5). By Cycles' own
  arithmetic, a surface is a hole exactly when `α ≤ 2^-25`, and a surface
  of `α` above about `1 − 10⁻⁵` is opaque to it (alpha design spike 2).
- *Gated occlusion distance:* the shade's occlusion distance is multiplied
  by the same gate, so a hole runs no occlusion and stacked cut-outs do not
  re-run it on every layer crossed. Occlusion otherwise keeps its
  approximation, in which every surface occludes as if solid (alpha design
  D-7); the shade's values are unchanged by the gate.
- *Without a material:* a primitive without one takes a stand-in, glTF's
  default material: white, opaque, code 65535.
- No material property but the colour (texture, metallic, roughness, normal
  map, emission) reaches any buffer.

**Material-ID and shade buffers** (material styling design D-10, D-11,
D-22, D-25, D-26; alpha design, *Capture transport and provenance*). Both
come from float AOVs, `matid` and `shade`, of the same render.

- *Shade* (D-22, D-25), occlusion and curvature only: linear
  `clamp(occlusion_weight · AO_out + convexity_weight · (1 − AO_in), 0, 1)`,
  where `AO_out` and `AO_in` are Cycles ambient occlusion looking outside and
  inside the surface, out to `ao_distance_m` with `ao_samples` samples. The
  four values are [settings](#settings-files) and options, `--ao-distance`,
  `--ao-samples`, `--occlusion-weight` and `--convexity-weight`, that reach
  Blender in the capture job's `settings.shade` and every material's
  replacement shader (owner decisions 2026-10-11 and 2026-10-12, settings
  design D-3, D-9, D-12 and D-42). Their shipped defaults are today's values:
  distance 0.3 m, 64 samples, occlusion weight 0.25 and convexity weight 1.0.
  At the defaults, creases and nooks are darker and convex curves lighter; a
  flat open surface is 0.25, encoded 137. A convexity weight of 0 removes the
  curvature term. AO samples stop at 128, the most Blender 5.2's Ambient
  Occlusion node takes: it silently clamps more, so the command refuses it
  first. A material whose library entry gives its own `ao_distance_m`,
  `occlusion_weight` or `convexity_weight` has its replacement shader use
  them, and the global values for the others; AO samples are global only
  (settings design D-9, D-36). An importer's copy of a glTF material takes
  that material's values, and a surface without a material and one taking
  the ordinary look take the global values; so does a material taking the
  default ramp. A translucent `BLEND` material's entry works exactly as an
  opaque one's: its own values reach its front shade (alpha design D-15). A library's own `shade` gives a range
  only, which acts in stylize, so it never reaches capture, and the capture
  job is the same whatever the default ramp, the ranges and the generated
  ramps (material styling design D-36). No light,
  direction or material property enters the shade. The buffer has `R = G = B` =
  the byte the `Standard` transform gives the linear shade,
  `floor(255 · sRGB(v) + ½)` with `v` clamped to [0, 1] (0.25 gives 137),
  alpha 255 where a surface was sampled and `(0, 0, 0, 0)` elsewhere.
  Occlusion keeps its approximation: every surface occludes as if solid
  (alpha design D-7).
- *Material-ID codes:* a glTF material of index `i` has code `i + 1`; a
  primitive without a material has the largest code, 65535; background is
  0. The AOV holds the code as a float, exact for every code; a value that
  is not exactly one of the model's codes, a surface holding the background
  code or a background pixel holding a code is a backend error (exit 5).
  The buffer holds a code's high byte in red and its low byte in green,
  blue 0 and alpha 255, and background as `(0, 0, 0, 0)`. A model with more
  than 65534 materials cannot be encoded: an input error (exit 3) before any
  Blender invocation, including the version probe.
- *Default shade range:* `[84, 191]`, the shipped default of the
  `shade.range` setting and `--shade-range` (settings design D-12): ramps take
  bands over the range in force (material styling design, Mapping a block).
  It was chosen from the spike's measurements so that a flat open surface, a
  crease and an isolated convex curve take different bands; that rationale
  and the distinct-band guarantee hold at the default shading values only.

**Normal and depth buffers** (lighting sheet design D-2, D-10, D-11, D-12,
D-16 and D-21, and its Spike 1, which holds the measurements). The same
render gives both, from the same camera sample as the colour, material ID
and shade, through two more AOVs that every replacement shader, the
stand-in's included, writes beside its emission: Geometry *Normal* through a
Vector Transform (normal, world to camera) to a colour AOV `normal`, and
Camera Data *View Z Depth* to a value AOV `depth`. Each render writes them
for its own surfaces, so they are taken from the front render where the
front layer is present, and from the back render elsewhere: the front-most
surface that is not a hole (alpha design D-11). The eight view-layer AOVs
are added for the render phase and removed after it.

After each frame's back and front renders, each one's colour is written as
an 8-bit TGA through the `Standard` transform, and its result also saved,
every pass and AOV, as an uncompressed multilayer OpenEXR of 32-bit floats
(the image settings' media type set to multilayer before the format, and
every image setting restored), which the script reads with the standard
library and removes. The float alpha of the back render's `Combined` pass
decides the back layer's coverage, exactly 0 or 1 at every pixel; its TGA's
alpha, the gated hits and every back AOV must hold a surface exactly where
it does, or the frame is a backend error (exit 5). The front render's float
alpha is the front layer's `f`, stored as `q = floor(65535 · f + ½)`.

**The count render** (alpha design spike 3, Review 2 B-1). After each
frame's back and front renders, the shared switch turns every surface to a
count shader: a shading point that still has a transparent closure, by
Cycles' own test (its transparent weight, averaged over the channels, at
least 10⁻⁵), becomes `Add(Transparent white, Emission white 1)`, and any
other point an `Emission` of strength 0. A `BLEND` surface always counts,
whatever its alpha, since the back render crosses it as a hole: so the
count covers what both renders cross, a visible translucent front
included. The switch also zeroes every AOV
and the occlusion distance, so the count render runs no occlusion and
writes no AOV. It uses the same camera, sampling and both transparent
bounce limits, 64, and is read back from its own OpenEXR, since background
mode keeps no render in memory. Its red channel counts, per pixel, the
surfaces the camera path crossed that still let light through, capped at
65. A frame where any pixel counts 65 or more is a backend error (exit 5):
the message names the input, the clip, the direction, the frame and its
time, the pixel, and the limit 64, and nothing is published. It means a
camera path crossed more than 64 surfaces that still let light through, so
Cycles stopped it before its end; it covers stacks ending at an opaque
surface and at the background alike, whatever their alphas. It is
conservative: it can refuse a frame whose lost light is below 8-bit
precision, and never accepts a damaged one. The switch back restores the
back render exactly, and no render carries a marker, so the count changes
no buffer.

**Front buffers** (alpha design, *Capture transport and provenance*), at
`front_color/`, `front_alpha/`, `front_matid/` and `front_shade/` with the
colour's ordinal:

- `front_color`: the front layer's straight colour, encoded as `color`,
  alpha 255 where the front layer is present;
- `front_alpha`: a 16-bit RGBA PNG in the form of `normal`: red is
  `q = floor(65535 · f + ½)`, green and blue 0, alpha 65535 where the front
  layer is present. A present front layer may have `q` 0, a surface of
  alpha 0, and a deep combined stack may round to 65535;
- `front_matid` and `front_shade`: as `matid` and `shade`, for the
  front-most translucent surface, which ramp the front layer in stylize.

Every file goes to the script's
scratch directory, `scratch/` inside the render phase directory: the script
creates it before the first frame and removes it after the last, and
otherwise the workspace's lifetime governs it ([ownership and failure
handling](#ownership-and-failure-handling)), so a failed or interrupted
Blender never leaves it outside the workspace.

- *Normal:* the unit **shading** normal, the model's interpolated vertex
  normals rather than the flat face normal, in the frame's camera space: +X
  screen right, +Y screen up, +Z toward the viewer. Cycles' camera looks
  along −Z, so this is the AOV's `(x, y, −z)`. No material property reaches
  it, normal textures included (D-16). A surface seen from behind reads its
  normal flipped toward the viewer, as Cycles shades it, and interpolated
  normals at a silhouette can point slightly away from the viewer (z below
  0).
- *Depth:* the surface's depth toward the viewer from the ground point,
  `ground_view_z − view_z` in meters, where `view_z` is the distance along
  the camera's viewing axis (*View Z Depth*) and `ground_view_z` the ground
  point's, taken per frame, since the camera's distance changes per frame
  (it stands clear of the subject's reach). Positive is nearer the viewer
  than the ground point, like the normal's z (D-10). `ground_view_z` comes
  from the camera transform Blender stores, in single precision, the camera
  Cycles measures from. Cycles works in single precision, so a depth is as
  precise as the float32 spacing of the surface's coordinates: about
  10⁻⁶ m near the origin, about 1 mm 10 km from it. Any depth is held: the
  depth map's range (D-21) limits only that map, and capture is never
  limited by it.
- *Coverage:* each buffer marks a pixel as a surface where its AOV holds a
  value: a unit normal is never `(0, 0, 0)`, and a view depth is never 0,
  since the camera's near plane is in front of every surface. That is
  exactly where either layer is present.
- *Encoding:* each buffer is a 16-bit RGBA PNG at the supersampled size,
  `normal/000000.png` and `depth/000000.png` with the colour's ordinal, every
  row unfiltered and no chunk but IHDR, IDAT and IEND. Alpha is 65535 on a
  surface, and every sample is 0 off one. The normal stores each component
  `n` as `floor((n + 1) / 2 · 65535 + ½)` in red, green and blue: at most
  1.5 · 10⁻⁵ from the AOV's value. The depth stores the 32-bit float nearest
  `ground_view_z − view_z`: its big-endian bits are red (the high half) and
  green (the low half), with blue 0. A covered depth of exactly 0 is
  therefore `(0, 0, 0, 65535)`, distinct from no surface.

Blender writes every buffer's PNG itself from the renders' pixels, with nothing but those pixels in them, since Cycles adds
render-time text to the files it saves, the OpenEXR's included; identical
frames are identical files.

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
| `schema` | Exactly `moskophoros.capture-job/2`. |
| `mode` | `measure` or `render`. |
| `source` | Absolute `path` to the original GLB, its `sha256` and the selected original glTF `scene` index. |
| `subject`, `variant` | Input stem and `default`, matching every requested frame address. |
| `settings` | The accepted sheet settings, using resolved option values, with the global frame count `frames` and each clip entry's own `frames` as given, which the script checks (a count, `auto`, or for a clip `null`); the job's `frames` list already holds the times they sample, so Blender never resamples, and `time_scale` is not in the job. In measure mode, `pixels_per_meter`, `cell` and `ground_px` are null: fitting belongs to the caller. In render mode all three are resolved, fixed values. `view` holds exactly `preset`, `directions` and `start_angle_deg`, and `camera`, after it, exactly `projection` (`orthographic`), `direction` (three finite numbers each from −1 to 1, normalised to within `1e-12` of length 1), `roll` (a finite number from −1 to 1) and `position` (three finite numbers, or null), as the sheet records them (projects and camera design D-14, D-16); both the launcher and the script check them strictly, and the script projects and frames with the rolled screen axes (see [Camera and directions](#camera-and-directions)). `shade` carries the shade's capture values, exactly `ao_distance_m` (finite, greater than 0), `ao_samples` (an integer, 1 to 128), `occlusion_weight` and `convexity_weight` (finite, 0 or greater), and `materials`: for each glTF material whose library entry gives its own `ao_distance_m`, `occlusion_weight` or `convexity_weight`, in ascending material order, exactly `material` (its glTF index) and its three resolved capture values, each its own or the global. Both the launcher and the script check them. Of the style, the job carries only those per-material values (owner decision 2026-10-11, settings design D-36, amending the rule below): the sheet's ramps, generated or listed, palette, reduction, default ramp, `previews` and shade ranges, the library's own `shade` included, are left out, as they act after capture, so the job and its `job_sha256` are the same whatever they are (owner decisions 2026-10-04, 2026-10-12). |
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
| `schema` | Exactly `moskophoros.capture-result/3`, for measure and render results alike (`/2` had no front buffers, alpha design ALPHA-4; `/1` recorded Workbench's renderer and studio light, ALPHA-1). |
| `mode` | Must match the submitted job. |
| `job_sha256` | Hash of the submitted job encoded as canonical JSON with sorted keys, compact separators, ASCII escapes and non-finite numbers forbidden. This binds a result to its complete request, not just its source. |
| `source_sha256` | Must match the job's source digest. |
| `backend` | Actual Blender version, and nothing else in a measure result. Render results also record, in this order, `renderer`, the renderer's name (`"cycles"`); `color`, exactly the colour's technique and its fixed parameters (`technique`, `samples_per_pixel`, `seed`, `pixel_filter`, `filter_width_px`, `min_transparent_bounces`, `transparent_max_bounces`, `pass_alpha_threshold`: a nonempty name, a whole number 1 or more, whole numbers 0 or more for the seed and the two bounce limits, a name, and numbers greater than 0 for the width and the threshold); and `shade`, exactly the shade technique and its fixed parameters (`technique`, `samples_per_pixel`, `seed`, `pixel_filter`, `filter_width_px`), whose capture values are the job's. There is no studio light. The version is parsed according to the owning supported-version contract. |
| `frames` | Exactly one record per requested address, in request order. No missing, duplicate or unexpected address is accepted. |
| `frames[].bounds_m` | Measure only: finite, nonnegative `L`, `R`, `U`, `D` as defined by the product design. |
| `frames[].height_m` | Measure only: evaluated subject height along the glTF vertical axis, for the accepted unit warning. |
| `roots` | Measure only: one entry per requested clip/root pair, with `clip`, `node_index`, `node_name` and nonnegative finite `travel_m`. Include zero travel. Evaluate the clip endpoints, even when the loop's render samples omit its endpoint. |
| `frames[].buffers` | Render only: map from buffer name to relative file path. `color`, `matid`, `shade`, `normal`, `depth`, `front_color`, `front_alpha`, `front_matid` and `front_shade` are mandatory; extra named buffers can be described without changing the frame structure. |
| `materials` | Render only: the asset's material table, one entry per material-ID code used, each `{"id": code, "material": index}` mapping a code to a glTF material index, or to `null` for "no material". Background (0) is never in it. |

Every result frame includes its full `address`. Sample indices and angles
remain caller-owned lookup data; they do not replace the address as identity.
Measure mode writes no color buffers. Render mode writes no new fitting or
root-motion verdict: the caller has already accepted the measurement.

The color path is `color/000000.png`, with a six-digit ordinal in
request order; the ordinal can grow beyond six digits. Every other buffer's
path is `<name>/000000.png` alike, such as `matid/000000.png` and
`front_alpha/000000.png`. Clip and subject names
never become capture filenames. Each file is the accepted high-resolution
color buffer. The launcher validates that referenced files exist, remain
within the phase directory, have the required dimensions and decode in the
required color mode before passing them to later stages. Paths may not be
absolute, contain parent traversal or escape through a symlink.

The launcher also rejects, as a backend error (exit 5):

- a render phase the script ended with an error, Blender's failure: among
  them a frame whose stack of see-through surfaces is deeper than the
  capture renders, the [count render](#capture)'s refusal naming the input,
  clip, direction, frame and limit;
- a colour pixel whose alpha is other than 0 or 255, an empty colour pixel
  other than `(0, 0, 0, 0)`, or a colour pixel whose coverage differs from
  the material ID's, in either direction;
- a material-ID pixel that is not exactly an encoded value (alpha other than
  0 or 255, background other than `(0, 0, 0, 0)`, blue other than 0, or
  code 0 at alpha 255), or a code missing from the table;
- a table entry that maps the background code, repeats a code, or is not a
  material of the model (checked by the command against the glTF);
- a shade pixel whose red, green and blue differ, or whose alpha is other
  than 0 or 255;
- a pixel where the two disagree: a background ID must have shade
  `(0, 0, 0, 0)`, and every other ID shade alpha 255;
- each of these for the front layer too, between `front_color`,
  `front_matid` and `front_shade`, each named "front";
- a front alpha buffer that is missing, at another path or not a 16-bit
  RGBA PNG in the capture's encoding; a front alpha pixel that is not an
  encoded value (alpha other than 0 or 65535, green or blue other than 0,
  or no surface other than `(0, 0, 0, 0)`); or one present where the front
  material ID is not, or absent where it is;
- a normal, depth or other front buffer that is missing or at another
  path, or a normal or depth file that is not a 16-bit RGBA PNG of the supersampled size in the
  [capture's encoding](#capture) (non-interlaced, every row unfiltered, no
  chunk but IHDR, IDAT and IEND);
- a normal or depth pixel that is not exactly an encoded value: alpha other
  than 0 or 65535, or no surface other than `(0, 0, 0, 0)`;
- a normal or depth pixel whose coverage differs from the layers', in
  either direction: a surface where neither layer is present, or none where
  either is;
- a surface's normal that is not a finite vector of unit length within
  `10⁻³` (the encoding moves it by at most 2.7 · 10⁻⁵; a normal pointing
  away from the viewer is accepted, since silhouettes produce them);
- a surface's depth that is not a finite 32-bit float, or whose blue is not
  0.

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
without treating incomplete phases as valid results. The script keeps the
capture's intermediate TGA and OpenEXRs inside the render phase
directory, and imports its private copy of the model from `import/` inside
each phase directory, so the launcher's deletion or retention of the
workspace covers them even when it has killed Blender, where no cleanup
inside Blender can run. The script removes the copy, `import/` and all, when
it finishes or fails.

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
- **Render settings behaved as specified** for the Workbench colour render
  this experiment measured, which one flat Cycles render has since replaced
  (alpha design ALPHA-1; its spikes 1 to 3 record that render's settings,
  exactness and cost on 5.2.2). The `Standard` view transform reproduces a
  material's sRGB colour exactly. Renders are pixel-identical across separate
  Blender processes; Blender's own image files carry render-time text, so
  every buffer is written from pixels.
- **Cost:** about 1 s to start Blender and about 1 s for the first render
  while shaders compile.

This section is the single record of the supported version. The backend's
version check in `capture/blender.py` must match it. Moving to a new series is
an owner decision recorded here, after the Blender integration tests pass on
it.

### Stylize

Each supersampled frame is reduced by `s×s` blocks, by the reduction
`--reduce` names. **Coverage and alpha are decided once per output pixel**,
by the edges rule `--edges` names, before and apart from any colour rule
(alpha design, *Stylize: numerical reference*, step 1; D-2, D-4, D-9). The
reductions, the palette and the material ramps then only choose the colour;
none applies a coverage cut of its own, and the pixel keeps this alpha
whatever its colour, a palette never snapping it.

- A supersample is a **surface sample** where either layer is present
  ([Two layers](#two-layers), below): the back colour's alpha is above 0,
  or the front layer is present, a front of alpha 0 included. Its composite
  alpha `aᵢ` is in units of 1/65535: on a frame without a front layer, its
  8-bit alpha times 257, so an opaque surface is 65535.
- For a block of `n = s²` samples with `m` surface samples and
  `S = Σ aᵢ`, in exact integers:
  - **`hard`** (the default): the pixel exists when `2m ≥ n`, at least half
    its block showing a surface, with `D = 65535 · m`: its alpha is the mean
    alpha of the surfaces it shows, so outlines and cut-out edges stay as
    crisp as an opaque model's, and an opaque model's kept pixels are 255;
  - **`soft`**: the pixel exists when `S > 0`, with `D = 65535 · n`: its
    alpha is its block's mean alpha, so outlines and cut-out edges keep the
    partial transparency reducing the block gives.
- The alpha byte is `α = (510 · S + D) // (2 · D)`, that is
  `floor(255 · S / D + ½)`, half up. A pixel that does not exist, or whose
  `α` is 0, is `(0, 0, 0, 0)`. The numerator reaches 8,573,026,560 at
  supersample 16, beyond 32 bits, so the arithmetic is 64-bit.
- For example, at supersample 2, one surface sample of four is transparent
  under `hard` and 64 under `soft`, and two are 255 and 128.

It is `imageops.block_alpha`, which every reduction and the material ramps
call.

**Plain** (`--reduce plain`, the default): a kept pixel's color is the
alpha-weighted mean of the block's RGB, rounded half up.

**Most common colour** (`--reduce mode`, owner decisions 2026-10-04): a kept
pixel takes the colour with the most votes.

- Each pixel of the block votes for its exact RGB with a weight equal to its
  alpha, so a pixel with alpha 0 casts no vote.
- A tie goes to the tied colour nearest the block's alpha-weighted mean RGB,
  by squared Euclidean distance in 8-bit sRGB values, compared exactly
  against the unrounded mean.
- A tie at equal distance goes to the smallest packed `0xRRGGBB` value.

Both reductions use exact integer arithmetic and are fully determined. The
alpha, and so the transparent pixels, are the same under either. A textured surface, or a
ramp's bands, can give a block nearly as many colours as pixels, so the vote
can fall to the tie-break; that is accepted, and the owner judges the look
(vision V-12). Future style passes replace or extend these (vision,
Long-term direction).

#### Two layers

A frame whose front layer is present somewhere ([Frames into
stylize](#frames-into-stylize)) is reduced by the numerical reference's
steps 1 to 4 (alpha design, *Stylize: numerical reference*; D-6, D-12,
D-14; `stylize.layered`). A frame without one is reduced exactly as above,
and so is a block with no front sample in a frame with one.

1. **Weights,** per supersample, in units of 1/65535
   (`imageops.layer_weights`): the front's `uᵢ = qᵢ` where it is present,
   and the back's transmitted weight `tᵢ = bᵢ · (65535 − uᵢ)`, where `bᵢ`
   is 1 on a back surface (exactly `floor(257 · alpha · (65535 − uᵢ) /
   65535)` for the back colour's 8-bit alpha). The composite alpha is
   `aᵢ = uᵢ + tᵢ`, and coverage and the alpha byte are decided from it as
   above (`imageops.composite_alpha`). A front layer whose `q` is 0 is a
   surface with alpha 0: presence never comes from the quantized alpha.
2. **Each layer's colour,** with its own weights in place of colour alpha
   (`imageops.reduce_weighted`): `W_f = Σ uᵢ`, `W_b = Σ tᵢ`. A layer of
   weight 0 is absent from the pixel; a sample where a layer is absent casts
   no vote and adds nothing to its sums.
   - `plain` takes the weighted mean of the layer's 8-bit sRGB values,
     rounded half up; with a palette, that mean then maps to it, before
     compositing (D-14).
   - `mode` takes the weighted vote, with the tie rules above against the
     weighted mean; with a palette, the layer's samples map first.
   - Each layer takes its winning material's ramp where it has one, by the
     rules of [Material ramps](#material-ramps) with its own weights in
     place of colour alpha (`imageops.map_ramps` with `weights`): the back
     layer from the back's identity and shade arrays and `tᵢ`, the front
     layer from the front identity and shade arrays, its front-most
     material's, and `uᵢ` (alpha design D-12, D-15). So a combined front is
     ramped by its front-most material, and a rear pane's ramp is never
     applied; a front whose winner takes no ramp keeps the ordinary look, in
     which every pane's own colour survives.
3. **Composite** in linear colour, `float64`, through the fixed 256-entry
   sRGB-to-linear table palette mapping uses (`imageops.composite`):
   `C = (W_f · lin(F̄) + W_b · lin(B̄)) / (W_f + W_b)`, encoded to 8-bit sRGB
   with the standard transfer function, rounded half up. A pixel with one
   weighted layer keeps that layer's colour unchanged, with no round trip.
   The weights carry each layer's share where it is, so a block whose front
   and back cover different samples weighs each by where it is: two front
   samples at 0.5 and two back samples give alpha 191 and `(1 · F + 2 · B) /
   3` in linear, not 0.625.
4. **Palette** (D-14): with a palette, a composited colour maps to the
   nearest palette colour by `imageops.map_palette` (OKLab, the earlier
   entry on a tie); a one-layer pixel already holds one. Alpha is step 1's,
   never snapped. For example, with a black-and-white palette, a black front
   of weight 32768 over a back of `(100, 100, 100)` with transmitted weight
   32767 maps the back to white first, composites to 188 and snaps to white,
   not black.

#### Normal and depth maps

Every frame's normals and depths are reduced to its reduced colour's pixels,
with exactly the colour's coverage, so the maps line up with the sheet pixel
for pixel (lighting sheet design D-8, D-15, D-19, D-21, D-27 and its
Numerical reference). They read the frame's normal and depth arrays
([Frames into stylize](#frames-into-stylize)): a **surface sample** is a
supersampled pixel where capture hit a surface. The colour and the samples
come from the same one camera sample per supersampled pixel
([Capture](#capture)), so a kept colour pixel has surface samples in its
block and a transparent one can have some; the rules below also define a
kept pixel with none.

- *Coverage:* a map pixel exists exactly where the reduced colour's alpha is
  above 0, a partly transparent pixel included, under either edges rule and
  either reduction, with or without a palette or a library (alpha design
  D-11). A transparent colour pixel has no surface in the maps, whatever its
  block holds. The map surface of a sample is the front layer's where it is
  present, otherwise the back's, the front-most surface the capture's
  normal and depth describe, and normal and depth reduce over those samples
  as below, unchanged; the normal's direction is never blended, and the lit
  preview lights the front-most surface's direction.
- *Normal:* a covered pixel's normal is the sum of the unit normals of every
  surface sample in its `s×s` block, renormalised to unit length, whatever
  material each sample shows, and whatever the reduction, palette or library.
  It is never palette-mapped or voted. It faces the viewer, `(0, 0, 1)`, when
  the block has no surface sample, or when the samples' normals cancel,
  `|Σn| < 10⁻⁶`.
- *Depth:* a covered pixel's depth is the mean depth of the same samples, a
  cancelling block's included, in **sheet pixels**: the captured meters times
  the sheet's `pixels_per_meter`, never scaled by the supersample factor.
  A covered pixel whose block has no sample takes the mean of the
  **unrounded** depths of its covered 8 neighbours within the frame that have
  samples; with none, 0, the ground point's plane. Either is then rounded
  half up to the 1/16-pixel step, `floor(16 · d + ½) / 16`, never
  ties-to-even. Any depth is held, without clamping or rescaling: only the
  depth map's later encoding has a range (D-21).
- *Carried:* the reduced frame (`sampling.ImageFrame`) carries the maps as
  its only buffers. Under `normal_map` (`sampling.NORMAL_MAP`), a `float64`
  array of shape `(H, W, 3)`: each covered pixel's unit normal in the
  frame's camera space (+X screen right, +Y screen up, +Z toward the
  viewer), and `(0, 0, 0)` elsewhere. Under `depth_map`
  (`sampling.DEPTH_MAP`), a `float64` array of shape `(H, W)`: each covered
  pixel's depth in sheet pixels toward the viewer from the ground point, a
  multiple of 1/16, and 0 elsewhere. Neither holds a NaN or infinity. A
  frame given to stylize without normal and depth is reduced to one carrying
  no buffers.
- *Encoding:* a normal's bytes are `floor(255 · (n + 1) / 2 + ½)` per
  component, half up, so a normal facing the viewer is `(128, 128, 255)`
  (`imageops.encode_normal`).

Both are pure functions in `imageops`, `reduce_normal_depth` and
`encode_normal`, and the maps change no colour, sheet, JSON or preview.

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

#### Material libraries

A material library defines each material's look once, as a ramp of indices
into the shared palette, for reuse across subjects (owner decisions
2026-10-07, D-6, D-7, D-8, D-15 and D-17 in
[the material design](designs/material_styling_design.md#decisions)). The
standalone `materials.read_library(path, colors)` library function reads only
the named file and validates it against the palette `colors`.
`materials.read_library_bytes(data, colors, source=...)` parses a byte
snapshot, so a caller can hash exactly the bytes it parsed, and
`materials.validate_library(document, colors, source=...)` validates an
already-parsed library without reading anything or changing its input. All
three return the same result for the same library. `--materials FILE` gives the
command a library, and `stylize` maps frames onto its ramps
([Material ramps](#material-ramps)).

A library is a UTF-8 YAML file whose name ends in `.yaml` or `.yml`, in any
case (owner decisions 2026-10-11, settings design D-7 and D-11; this replaces
the JSON format of material design D-8). `read_library` and the command refuse
any other name, `.json` included, before reading the file, saying that
libraries are YAML. `read_library_bytes` and `validate_library` never inspect
`source`, which only labels diagnostics, so a sheet whose recorded library
`source` ends in `.json` still reuses. Comments are allowed:

```yaml
# Ramps run darkest first, as indices into the palette.
schema: moskophoros.materials/3
ramps:
  metal: [12, 13, 14, 15, 47]
  cloth: [80, 81, 82]
  gold: {base: "#ca9337", bands: 4}        # generated from properties
  chrome: {base: "#8c939c", bands: 5, hue_shift_deg: -35, chroma_fade: 0.6}
default: cloth          # a named material with no entry takes this ramp
shade: {range: [190, 225]}   # the range its materials fall back to
materials:
  steel: {uses: metal}
  cloth.red:
    ramp: [80, 81, 82]
    shade: {range: [120, 255], convexity_weight: 0.5}   # its own values
  leather: {ramp: {base: "#6b4226", bands: 3}}
  face: ordinary
```

- `schema` is `moskophoros.materials/3`, the current schema, or
  `moskophoros.materials/2`, which still loads and reads exactly as before:
  every `/2` library is valid `/3` (owner decision 2026-10-14, material
  styling design D-34). Only a `/3` library may give a generated ramp or a
  top-level `shade`; a `/2` library using either is an error naming the ramp
  or key. A `moskophoros.materials/1` library, from before per-material
  shading, is refused, saying to change its `schema` line to
  `moskophoros.materials/3`, the only edit it needs (owner decision
  2026-10-11, settings design D-29). `schema`, `ramps` and `materials` are
  required; `ramps` and `materials` are mappings and may be empty. No other
  field is allowed at any level.
- `ramps` holds named generic ramps. A ramp is a non-empty list of at most
  256 integers, never booleans or numbers such as `3.0`, each an index
  from `0` to one less than the palette's length. A one-entry ramp is a flat
  material; indices may repeat. "Darkest first", band 0 being the least
  light, is the authoring convention and is not checked.
- Wherever a ramp is a list, a `/3` library may give it as a mapping of
  properties instead, a **generated ramp** ([Generated
  ramps](#generated-ramps)): `base`, an sRGB `#rrggbb` (any case, recorded
  lowercase), and `bands`, a whole number from 1 to 256, are required;
  `lightness_step` (0 to 1), `hue_shift_deg` (−180 to 180) and `chroma_fade`
  (0 to 1), finite, are optional, each beating the global `ramp` setting of
  that name. No other key is allowed. A library may mix listed and generated
  ramps, and `uses` and `default` may name either. Listing a ramp's indices
  stays the exact control (material styling design D-12).
- `default`, optional, names one ramp in `ramps`; `null` is not allowed.
- A `/3` library may give a top-level `shade`, its own shade **range** only:
  `{range: [lo, hi]}`, checked as a material's `range`. A library `shade`
  giving `ao_distance_m`, `occlusion_weight`, `convexity_weight` or
  `ao_samples` is an error naming the key: capture values come only from a
  material's own `shade` or the globals (owner decision 2026-10-14, material
  styling design D-35, D-36).
- Each `materials` entry is exactly one of `{"ramp": [...]}`, its own ramp;
  `{"uses": NAME}`, a ramp in `ramps`; or the string `"ordinary"`.
- An entry with `ramp` or `uses` may carry a `shade` mapping, its material's
  own shading values (owner decisions 2026-10-11, settings design D-4, D-9,
  D-20 and D-23): any of `ao_distance_m` (finite, greater than 0),
  `occlusion_weight` and `convexity_weight` (finite, 0 or greater) and `range`
  (`[lo, hi]`, two integers with `0 ≤ lo < hi ≤ 255`), checked with the
  global values' limits. `ao_samples` there is an error saying AO samples is
  global only; any other key is an unknown field. The `"ordinary"` form, named
  ramps and the default carry none. A material's own value beats the global
  one from any layer; a value it does not give is the global in force. A
  material with no entry, or taking the default ramp or the ordinary look,
  takes the global values; a translucent (`BLEND`) material's entry works as
  any other's, its own values reaching its front shade and its own range
  its front layer's bands (alpha design D-15). Materials sharing a name
  share their entry and its values. The values live only in the library, so
  they never merge across settings layers (D-22). A material's **shade
  range** is the first given of: its entry's own `range`, the library's
  `shade.range`, the settings layers' `shade.range`, the shipped default. A
  material with no entry that takes the default ramp also takes the library's
  range; the ordinary look uses none (D-35, D-36).
- Names are non-empty strings, kept and compared exactly, case and
  whitespace included. A reference to an undefined ramp is an error. Entries
  and ramps no model uses are valid and not reported. An unquoted name the
  typing below reads as something else, such as `1`, `true` or `null`, is
  refused as a key that is not a string; quoted, it is a name.

The file is read by the strict YAML reader `yamlfile.load(data)`, which the
settings loader reuses (settings design D-1). It is PyYAML's safe loader with
these rules:

- The bytes are decoded strictly as UTF-8 first, so a UTF-16 file is refused
  even with a byte order mark. A UTF-8 byte order mark is allowed.
- A file holds exactly one document. An empty file, or one holding only
  comments, is refused, and so is a second document.
- A key repeated at any level is refused, naming the key and its line.
- Every explicit tag is refused, such as `!!int`, `!!float`, `!!str`,
  `!!binary`, `!!set`, `!!pairs`, a local `!name` or the bare `!`.
- Anchors and aliases are allowed and resolve to ordinary values. An alias
  inside its own anchored node, such as `&a [*a]`, is refused.
- A sequence or mapping used as a key is refused.
- Implicit typing is restricted, so a plain value means only what it looks
  like:

  | Plain value | Means | Stays a string |
  |---|---|---|
  | `true`, `false` | a boolean | `True`, `TRUE`, `yes`, `no`, `on`, `off` |
  | `null`, `~` | null | `Null`, `NULL`, and an empty value, which is `""` |
  | `-?(0\|[1-9][0-9]*)` | an integer | `+1`, `1_000`, `0o17`, `017`, `0x0F`, `1:20` |
  | JSON's numbers with a fraction, an exponent or both: `1.5`, `-2.5E-3`, `1e3` | a float | `.5`, `5.`, `+1.5`, `.inf`, `-.inf`, `.nan`, `.NaN` |

  Every other plain value is a string: timestamps such as `2026-10-11`, `<<`,
  which never merges, and `=`. A quoted value is always a string. So `017` as
  a ramp index is refused as `ramps["metal"][0]: "017" is not an integer`,
  and a material named `on` or `no` keeps its name.
- Every failure is a `yamlfile.YamlError` naming its line and column, which
  count from 1, never another exception. That includes input Python itself
  refuses while PyYAML reads it: an escape beyond U+10FFFF such as
  `"\U00110000"`, a number longer than Python's integer digit limit, and
  nesting too deep to read, each placed where reading stopped. Only a UTF-8
  error gives a byte offset instead.

The result is an immutable `materials.Library`: `ramps` maps each name to a
tuple of indices, `default` is a ramp name or `None`, and `materials` maps
each name to a `materials.Entry` holding its own `ramp` or the name it
`uses`, and `shade`, a `materials.Shade` of the values it gives or `None`;
an entry with neither ramp nor `uses` is `"ordinary"`.
`materials.capture_overrides` gives each glTF material's own capture values,
and `materials.override_warnings` the warnings below. Both mappings are read-only
and ordered by name, so the result does not depend on the file's key order,
and checks run in name order, so neither does the first error reported.

Every failure raises `materials.LibraryError`, naming the file or
caller-supplied source and the problem: a name that does not end in `.yaml`
or `.yml`, unreadable files, invalid UTF-8, malformed YAML, nesting too deep
to read, an empty file, more than one document, repeated keys, a tag, a
recursive alias, a sequence or mapping key, an integer with too many digits
for Python to convert, an escape beyond U+10FFFF, a wrong or missing field, an
unknown field, a key that is not a string, a value of the wrong type, an
empty or oversized ramp, a non-integer or out-of-palette index, an entry of
none or several forms, an empty name, a reference to an undefined ramp, a
`moskophoros.materials/1` schema, or a `shade` that is not a mapping, holds
`ao_samples` or an unknown key, or a value outside its limits.
YAML errors give the line and column, such as `is not valid YAML at line 3,
column 1: …` or `repeats the key "metal" at line 4, column 3`; only these
parse failures say YAML. Errors after parsing name the field, ramp or
material and the position in a ramp, such as `materials["steel"].ramp[2]`, in
wording that does not depend on the format, since they also check a reused
sheet's inline record. The module neither prints nor exits.

#### Generated ramps

A generated ramp turns a base colour and a band count into palette indices
when the library is read (owner decisions 2026-10-14, material styling
design D-28 to D-34 and its numerical reference; `ramps.generate`). Band
`i` of `N` (0 the darkest) is `k = N − 1 − i` shades below the base, so the
last band is the base colour itself. With `step`, `hue` and `fade` the
ramp's own `lightness_step`, `hue_shift_deg` and `chroma_fade`, else the
global `ramp` settings ([Settings files](#settings-files)):

1. **Base to OKLab:** the base's 8-bit sRGB is decoded with the palette
   mapping's table and converted with palette mapping's OKLab conversion
   (`imageops._oklab`: its matrices, `cbrt`, the same operation order).
   `C0 = hypot(a0, b0)`, and `h0 = atan2(b0, a0)` in degrees.
2. **Each band:** `L = max(0, L0 − step·k)`; `h = h0 + hue·k`, except
   `h = h0` when `C0 < 0.02` (a near-grey keeps its hue);
   `C = C0·(1 − fade·k/(N − 1))`, and `C = C0` when `N = 1`;
   `a = C·cos(h·π/180)` and `b = C·sin(h·π/180)` in float64, with no hue
   wrapping.
3. **The gamut predicate** converts `(L, a, b)` to linear sRGB with the
   inverse of Björn Ottosson's 2021 matrices:
   `l = (L + 0.3963377774a + 0.2158037573b)³`,
   `m = (L − 0.1055613458a − 0.0638541728b)³`,
   `s = (L − 0.0894841775a − 1.2914855480b)³`,
   `R = 4.0767416621l − 3.3077115913m + 0.2309699292s`,
   `G = −1.2684380046l + 2.6097574011m − 0.3413193965s`,
   `B = −0.0041960863l − 0.7034186147m + 1.7076147010s`. The colour is in
   gamut when every channel is in `[−10⁻⁶, 1 + 10⁻⁶]`; the tolerance belongs
   to this predicate only.
4. **The search:** a shade out of gamut keeps its lightness and hue and loses
   chroma: with `lo = 0` and `hi = C`, 40 times `mid = (lo + hi)/2`, setting
   `lo = mid` if `mid` passes, else `hi = mid`; the result is `lo`.
5. **Snapping** compares the shade's own `(L, a, b)`, never converted back to
   RGB, clamped or rounded, with each palette entry's OKLab as palette
   mapping computes it, by the sum of squared differences. A later entry wins
   only when strictly nearer, so equal distances keep the lower index.
   Repeats are kept, so the band count never changes.

Pinned cases: base `#000040`, `N = 2`, step 1, hue −12°, fade 0.3, on the
two-entry palette `[#000003, #010000]`, gives `[0, 0]` (a clamped RGB round
trip would give `[1, 0]`). On the Vince 144 palette, the shipped setting B
(0.12, −12°, 0.3) gives gold `#ca9337`, `N = 4`, `[18, 19, 4, 5]` and the
near-grey steel `#8c939c`, `N = 4`, `[111, 133, 135, 137]`; setting C (0.09,
−35°, 0.6) gives `[110, 13, 4, 5]` and `[132, 134, 136, 137]`.

A generated ramp is then used exactly as a listed ramp of its indices: a
sheet from it is byte-identical to one from the listed ramp. A ramp's own
formula value beats the global from any layer; a global given explicitly, by
an option or a project file, that a generated ramp in use keeps its own
value over is named in a warning, naming the ramp and the value it kept
(settings design D-23); a value from the shipped defaults, the global file or
a loaded sheet warns nothing.

#### Material ramps

`stylize.plain` and `stylize.mode` take three further arguments, none used
unless `library` is given: `library`, a validated `materials.Library`;
`identities`, the asset's `sampling.Identities`; and `shade_range`, the pair
`(lo, hi)` of 8-bit shade values with `0 ≤ lo < hi ≤ 255`, the global range;
a material whose entry gives its own `range`, or else whose library gives
one (material styling design D-35, D-36), is banded over that instead,
throughout: clamping, band boundaries and `mode`'s band centres (owner
decisions 2026-10-11, settings design D-9; this amends material design D-7's
one global range) (owner decisions
2026-10-07, D-6, D-7, D-9, D-11, D-15, D-17, D-18, D-20, D-22, D-23 and D-25
in [the material design](designs/material_styling_design.md#decisions)). The
range is a parameter: stylize never chooses or normalises it. A library needs
a palette, and each frame must carry the `identity` and `shade` buffers
([Frames into stylize](#frames-into-stylize)), or stylize raises
`ValueError` naming the frame. Without a library both reductions colour each
block exactly as above, from the colour alone. Frames
are handled one at a time; a frame's colour, identity, shade, normal and
depth arrays are released once it is reduced. The result is a reduced colour
frame whose only buffers are its reduced `normal_map` and `depth_map` when
the frame carried both normal and depth, and none when it carried neither
([Normal and depth maps](#normal-and-depth-maps)).

**Resolution.** `stylize.resolve(library, name)` gives the ramp a material
name takes: its own entry (its `ramp`, or the ramp it `uses`; `"ordinary"`
gives none), then the library's default ramp, then none, which is the
ordinary look. The no-identity class (unnamed and missing materials, and
those of an alpha mode glTF does not define) always takes the ordinary look.
A translucent `BLEND` material resolves as any other (alpha design D-15).

**Mapping a block.** For each `s×s` block, every weight is the colour
buffer's alpha, as in the reductions above. A frame with a front layer maps
each layer apart, with that layer's own weights, identity and shade in place
of the colour alpha and the frame's arrays ([Two layers](#two-layers)): the
front layer votes on the front identities with `uᵢ` and takes its band from
the winner's front shade, by the same integer rules and tie order (material
styling D-23):

1. **Coverage and alpha** are decided exactly as above, by the edges rule,
   from the colour buffer's alpha. Transparent blocks stay `(0, 0, 0, 0)`; a
   pixel with colour alpha but background identity counts towards coverage
   and casts no vote.
2. **Identity.** Each pixel with an identity votes for it with its colour
   alpha. Materials sharing a name pool their votes as one identity (D-18); the
   no-identity class is one candidate; background pixels cast no vote. The most
   votes wins; a tie goes to the identity with the smallest lowest glTF
   material index, the no-identity class last (D-23). No vote at all means the
   ordinary look.
3. **Band.** If the winner resolves to a ramp of `N` entries, only the winner's
   pixels give the band; shades of losing identities and of background never
   do. `[lo, hi]` is the winner's own range if its entry gives one, else the
   global range. Let `L = hi − lo + 1`. The range is split into `N` equal bands, and a
   shade `v`, clamped into `[lo, hi]`, takes band `(v − lo)·N // L`. Let
   `A` be the sum of the winner's colour alphas and `W` the sum of alpha times
   the original shade.
   - **Plain:** the mean `W/A` is clamped, not its samples and not rounded
     first: with `Wc = min(max(W, lo·A), hi·A)`, the band is
     `(Wc − lo·A)·N // (L·A)`, and the output is `palette[ramp[band]]`.
   - **Mode:** each winner pixel with alpha above zero votes for the palette
     entry `ramp[band]` of its clamped shade, with its alpha as the weight, so
     repeated ramp entries pool their votes. A tie goes to the entry nearest
     the unrounded mean `W/A`, taken over **every** occurrence of that entry
     in the ramp, voted for or not: band `k` is centred at
     `lo + (k + ½)·L/N`, and occurrence `k` is at distance
     `|2·N·W − (2·N·lo + (2k + 1)·L)·A|` (scaled by `2·N·A`), minimised over
     the entry's occurrences. A tie at equal distance goes to the smaller
     palette index.
   - The output alpha is the block's, from step 1.
4. **Otherwise** (no-identity, `"ordinary"`, unmapped without a default, or no
   vote) the block takes the existing look for the chosen reduction and
   palette over the whole block, including losing identities and background
   pixels (D-9).

`hi` is band `N − 1` only when `N ≤ L`: in general it takes band
`((L − 1)·N) // L`. Over `lo = 100`, `hi = 101` a three-entry ramp uses its
first two entries; longer ramps are valid, and their later bands are
unreachable.

Coverage, votes, shade sums, bands and `mode` ties use exact integer
arithmetic, so they are deterministic and do not depend on the library's key
order. The ordinary look keeps its own arithmetic, including the NumPy
`float64` OKLab palette mapping above, and is unchanged. Dithering and eased
bands are out of scope (D-7).

#### Using a library from the command

`--materials FILE`, or a [settings file](#settings-files)'s `materials`,
reads the library file once; the same bytes are parsed
(`materials.read_library_bytes`) and hashed (SHA-256), and the library is
validated against the palette in force, whether it came from `--palette`, a
settings file or reused settings. `--no-materials` drops a reused library. The library is
used with the reduction, the palette and the shade range in force: each frame
is mapped as under [Material ramps](#material-ramps), from the decoded
material-ID and shade buffers. The shade range in force is the `shade.range`
setting: `--shade-range`, a settings file, a reused sheet's recorded range
(kept even when an explicit library replaces the reused one), or the shipped
default `[84, 191]`.

Each of these is a usage error (exit 2) before any Blender invocation,
including its version probe, naming the file and, where there is one, the
material or entry: every library error, a library without a palette (given
neither by `--palette` nor by reused settings), and the combinations of
[reuse](#scale-and-ground-point) that would change a reused library's palette.
A library is checked against the palette in force only if it stays.

When a library is in use, whether given or reused, the command prints these
warnings on stderr, each once (owner decisions 2026-10-07, D-3, D-9, D-17 and
D-18), before capture starts:

- each named model material with no library entry, naming it and whether it
  took the default ramp or the ordinary look, a translucent `BLEND` material
  as any other (alpha design D-15); a name used only by materials whose alpha
  mode glTF does not define takes the ordinary look whatever the default, and
  its warning names that alpha mode (the manager's note under D-15)
- one warning counting the parts with no material name, from the glTF
  primitives of the selected scene: an unnamed material, or a primitive without
  one
- each library entry whose name is used only by materials whose alpha mode
  glTF does not define
- for each global shading value an option or a project file set, each
  material of the model taking its entry's ramp that keeps its own value
  instead, naming the material, the value and the global one, once per
  material and value, by material then in the order `ao_distance_m`,
  `occlusion_weight`, `convexity_weight`, `range` (owner decision 2026-10-11,
  settings design D-23). A global from the shipped defaults, the global file or
  a loaded sheet warns nothing, nor does an entry the model never uses; a
  translucent material's warns as any other's
- an explicit global `shade.range` that the library's own range beats for a
  material in use, once, naming the library's value (material styling design
  D-35)
- an explicit global `ramp` value that a generated ramp in use keeps its own
  value over, naming the ramp and the value it kept (D-33)

Library entries and named ramps the model never uses are silent (D-15).
Names are shown as JSON strings, so quotes and whitespace are visible. The
warnings are not errors, and no output changes with them.

Without a library, the sheet PNG and previews of every look are byte-identical
to those the reductions gave before libraries existed; only the sheet's JSON
changes, by its schema and the `style` fields below, and with them its
fingerprint.

### Cleanup (slice 1: none)

A stage that receives addressed frames and returns them. Slice 1 passes them
through unchanged, their normal and depth maps included.

### Export

**Sheet.**
- One row per clip × direction: clips in selection order, and within each clip,
  directions in index order.
- One column per frame; the column count is the largest frame count of any
  clip.
- Cells are packed with no gaps; unused cells are fully transparent.
- Output is an 8-bit RGBA PNG written by Pillow with no text or time chunks.

**Normal map** (lighting sheet design D-2, D-9, D-17), `<stem>.normal.png`
beside the sheet unless `normals` is false: an 8-bit RGBA PNG written by
Pillow with no text or time chunks, exactly the sheet's size and in its
layout, the same cells, frames and positions. Each pixel the colour sheet
covers (alpha above 0) holds that pixel's reduced normal ([Normal and depth
maps](#normal-and-depth-maps)), in the frame's camera space (+X screen
right, +Y screen up, +Z toward the viewer), encoded per component as
`floor(255 · (n + 1) / 2 + ½)`, its direction never blended, with the
colour's alpha `α` (alpha design D-11): an opaque pixel facing the viewer is
`(128, 128, 255, 255)`. Every pixel transparent in the colour sheet is
`(0, 0, 0, 0)`, so the two alphas are identical, partial alpha included. It is published
all-or-nothing with the sheet, JSON and previews, rolled back with them, and
named in an output error (exit 6) when it cannot be written. A game decodes
a normal as `2 · byte / 255 − 1` per component and renormalises it.

**Depth map** (lighting sheet design D-3, D-10, D-17, D-21), `<stem>.depth.png`
beside the sheet when `depth` is true (off by default): a 16-bit greyscale
PNG written by Pillow with no text or time chunks, exactly the sheet's size
and in its layout. Each pixel the colour sheet covers (alpha above 0, a
partly transparent one included) holds `32768 + floor(16 · depth + ½)`, where `depth` is the pixel's reduced depth
([Normal and depth maps](#normal-and-depth-maps)) in sheet pixels, toward
the viewer from the plane through the ground point that faces the camera:
a surface in front of that plane reads above 32768 and one behind it below.
Depths from −2047.9375 to +2047.9375 encode, as codes 1 to 65535; one beyond
is an [overflow](#scale-and-ground-point). Every other pixel, transparent in
the colour sheet or in an unused cell, is 0, which means "no surface". A
game recovers `depth = (code − 32768) / 16` and, with the pixel's position,
`pixels_per_meter` and `ground_px`, its position in camera space. It is
published with the other outputs, rolled back with them, and named in an
output error (exit 6) when it cannot be written.

**JSON (`moskophoros.sheet/14`).**

```json
{
  "schema": "moskophoros.sheet/14",
  "generator": {
    "tool": "moskophoros", "version": "0.1.0",
    "python": "3.x.y", "numpy": "x.y.z", "pillow": "x.y.z",
    "blender": "x.y.z", "renderer": "cycles",
    "color": { "technique": "cycles-flat-emission", "samples_per_pixel": 1,
               "seed": 0, "pixel_filter": "BOX", "filter_width_px": 0.01,
               "min_transparent_bounces": 64, "transparent_max_bounces": 64,
               "pass_alpha_threshold": 9.313225746154785e-10 },
    "shade": { "technique": "cycles-ambient-occlusion", "samples_per_pixel": 1,
               "seed": 0, "pixel_filter": "BOX", "filter_width_px": 0.01 }
  },
  "source": { "file": "hero.glb", "sha256": "..." },
  "subject": "hero",
  "variant": "default",
  "settings": {
    "view": { "preset": "iso", "directions": 8, "start_angle_deg": 0.0 },
    "camera": { "projection": "orthographic",
                "direction": [0.0, -0.49999999999999994, -0.8660254037844387],
                "roll": 0.0, "position": null },
    "model_yaw_deg": 0.0,
    "fps": 12.0,
    "frames": "auto",
    "supersample": 8,
    "pixels_per_meter": 24.5,
    "cell": { "width": 48, "height": 48 },
    "ground_m": { "x": 0.0, "y": 0.0, "z": 0.0 },
    "ground_px": { "x": 24, "y": 46 },
    "root_motion": "error",
    "previews": true,
    "normals": true,
    "depth": false,
    "light": { "position": null, "intensity": 1.0, "ambient": 0.3 },
    "shade": { "ao_distance_m": 0.3, "ao_samples": 64,
               "occlusion_weight": 0.25, "convexity_weight": 1.0,
               "range": [84, 191] },
    "ramp": { "lightness_step": 0.12, "hue_shift_deg": -12.0,
              "chroma_fade": 0.3 },
    "style": { "reduce": "plain", "edges": "hard", "palette": null,
               "materials": null },
    "clips": [ { "name": "walk", "loop": true, "frames": null },
               { "name": "attack", "loop": false, "frames": null } ]
  },
  "fingerprint": "sha256:...",
  "image": { "file": "hero.png", "width": 576, "height": 768 },
  "maps": { "normal": { "file": "hero.normal.png" }, "depth": null },
  "directions": [ { "index": 0, "angle_deg": 0.0, "label": "south" } ],
  "clips": [
    { "name": "walk", "loop": true, "duration_s": 1.0,
      "frame_count": 12, "frame_duration_s": 0.08333333333333333,
      "time_scale": 1.0 }
  ],
  "frames": [
    { "clip": "walk", "direction": 0, "index": 0, "time_s": 0.0,
      "x": 0, "y": 0, "w": 48, "h": 48 }
  ]
}
```

- `frames` lists every frame, in sheet order. A frame's address is `subject`,
  `variant`, `clip`, `direction` and `time_s` (V-9).
- `settings.style` records the look, in this order: `reduce`, the `--reduce`
  value; `edges`, the edges rule in force, `hard` or `soft`, required and
  inside the fingerprint (alpha design D-9); `palette`, either `null` or an ordered object with `source` (the
  palette file's base filename), `sha256` (SHA-256 of its bytes), and `colors`
  (ordered canonical lowercase `#rrggbb` strings); `materials`, either `null`
  or an object with `source` (the library file's base filename), `sha256`
  (SHA-256 of its bytes), `ramps` (each named ramp in name order: a listed
  ramp as its list of palette indices, a generated ramp as a mapping of its
  properties as given, `base` in canonical lowercase, `bands`, its own
  `lightness_step`, `hue_shift_deg` and `chroma_fade` in that order, then
  `indices`, the generated result), `default` (a ramp name, or `null`), the
  library's own `shade` when it gives one (holding only `range`; a library
  without one has no `shade`), and `materials` (each
  entry in name order: `{"ramp": [...]}` or a generated ramp's mapping,
  `{"uses": NAME}` or `"ordinary"`,
  and an entry giving its own shading values has a `shade` after its `ramp`
  or `uses`, holding only the values the library gives, in the fixed order
  `ao_distance_m`, `occlusion_weight`, `convexity_weight`, `range`, whatever
  the file's order (settings design D-37); an entry without them has no
  `shade`).
  It sits between `ramp` and `clips`. Export writes and fingerprints the record the
  command resolved without interpreting it, so a new look changes neither
  export nor capture (owner decisions 2026-10-04, 2026-10-07).
- `settings.view` records the view: `preset`, the preset's name or `custom`,
  `directions` and `start_angle_deg`. `settings.camera`, directly after it,
  records the camera: `projection`, `"orthographic"`; `direction`, the
  normalised direction, three numbers; `roll`, a number; and `position`,
  three numbers or `null`, recorded unused by the orthographic camera. The
  pitch is not recorded: the direction holds it. Both are inside the
  fingerprint (projects and camera design D-14, D-16).
- `settings.frames` records the global frame count as given, `auto` or a
  count, directly after `settings.fps`; each `settings.clips` entry runs
  `name`, `loop` and `frames`, the clip's own value as given: a count,
  `auto` or `null`. Counts are recorded as given, never resolved; each
  top-level `clips` entry's `frame_count` is the resolved number, and its
  `time_scale`, directly after `frame_duration_s`, the retiming factor
  (owner decisions 2026-10-11, settings design D-24, D-31, D-40). Inside the
  fingerprint.
- `settings.previews` records whether the run wrote the animated previews, a
  boolean between `root_motion` and `normals`, inside the fingerprint (owner
  decision 2026-10-11, settings design D-28).
- `settings.normals` records whether the run wrote the normal map, a boolean
  between `previews` and `depth`, inside the fingerprint (lighting sheet
  design D-17, D-18).
- `settings.depth` records whether the run wrote the depth map, a boolean
  between `normals` and `light`, inside the fingerprint (lighting sheet
  design D-17, D-18).
- `settings.light` records the preview light, in this order: `position`
  (`[x, y, z]` or `null`), `intensity` and `ambient`, whether or not a light
  is placed or used, between `depth` and `shade`, inside the fingerprint
  (lighting sheet design D-13, D-18).
- `settings.ramp` records the global formula of generated ramps, in the order
  `lightness_step`, `hue_shift_deg`, `chroma_fade`, between `shade` and
  `style`, inside the fingerprint, whether or not a library is used (material
  styling design D-33).
- `maps`, directly after `image`, names each map's base file name, or `null`
  for a map not written: `normal` is `{"file": "<stem>.normal.png"}`, or
  `null` with `normals` false, and `depth` is `{"file": "<stem>.depth.png"}`
  with `depth` true, else `null`. The encodings are fixed by this design and named by the
  schema, not repeated per sheet. `maps` is outside the fingerprint, as
  `image` is; `settings.normals` covers it.
- `settings.shade` records the shading values used, in this order:
  `ao_distance_m`, `ao_samples`, `occlusion_weight`, `convexity_weight` and
  `range` (`[lo, hi]`), recorded whether or not a library is used, between
  `light` and `style`, inside the fingerprint (owner decisions 2026-10-11
  and 2026-10-12, settings design D-24 and D-35). `generator.shade` keeps only
  the fixed technique: `technique`, `samples_per_pixel`, `seed`,
  `pixel_filter` and `filter_width_px`. `moskophoros.sheet/5` is the same
  document without per-material shading in the inline library record, and
  `moskophoros.sheet/4` recorded the
  capture values in `generator.shade` and the range as
  `settings.style.shade_range`; `moskophoros.sheet/6` had no frame counts or
  `time_scale`; `moskophoros.sheet/7` had no normal map, `maps` or
  `settings.normals`; `moskophoros.sheet/8` had no depth map or
  `settings.depth`; `moskophoros.sheet/9` had no `settings.light`;
  `moskophoros.sheet/10` had no `settings.ramp`, generated ramp records or
  library `shade`; `moskophoros.sheet/11` had Workbench's lit colour,
  recorded `generator.renderer` `"workbench"` and `generator.studio_light`,
  and had no `generator.color`; `moskophoros.sheet/12` had no
  `settings.style.edges`, and its pixels' alpha was only 0 or 255;
  `moskophoros.sheet/13` recorded the view's `projection` and `pitch_deg`
  in `settings.view` and had no `settings.camera`;
  [reuse](#scale-and-ground-point) loads only `/14` (settings design D-24;
  projects and camera design D-14, D-17). The normal and depth capture adds no fixed
  parameter to `generator.shade` (lighting sheet design D-26).
- `generator` records this tool, its Python and libraries, and what the
  render result's `backend` reports: the Blender version, `renderer`
  (`"cycles"`), `color`, the colour's technique and fixed parameters, and
  `shade`, the shade's, each copied as the result gives it and inside the
  fingerprint (alpha design ALPHA-1). There is no studio light.
- `fingerprint` is the SHA-256 of the canonical JSON (sorted keys, no
  whitespace, UTF-8) of `generator`, `source.sha256` and `settings`. The
  hashed object mirrors the sheet's own structure:
  `{"generator": …, "settings": …, "source": {"sha256": …}}` (owner decision
  2026-10-01).
- Floats are written with Python's shortest round-trip representation.
- The file keeps the key order shown above, with 2-space indentation, UTF-8
  with non-ASCII characters kept as is, and a trailing newline (owner decision
  2026-10-01).
- `source.file`, `image.file` and the `maps` files are base names, never
  paths, so the JSON is the same wherever the command runs (owner decision
  2026-10-01).

For example, the palette record for `two.hex` containing `000000` and
`ffffff`, each followed by a newline, is:

```json
{"source": "two.hex", "sha256": "89b96770b769aab4951a86bb5b9ddea7b757fd45f822c7a4d4196759ec2f32b6", "colors": ["#000000", "#ffffff"]}
```

The palette's file bytes, colours and their order all participate in the
fingerprint; reuse needs only this inline record. The library record is
likewise inline, so reuse never opens the library file: for `ramps`
`{"metal": [12, 13, 14]}`, `default` `null` and a `steel` entry using `metal`,
it is

```json
{"source": "materials.yaml", "sha256": "…", "ramps": {"metal": [12, 13, 14]}, "default": null, "materials": {"steel": {"uses": "metal"}}}
```

and a library file's bytes, its ramps, default and entries, and the shade
range all participate in the fingerprint.

**Previews.** For each clip, an animated GIF showing all directions side by
side in index order, packed with no gap between cells (owner decision
2026-10-01):

- scaled 4× with nearest-neighbor
- each pixel blended over a solid `#808080` background in 8-bit sRGB
  straight alpha, as an image viewer shows a PNG (alpha design D-13): each
  channel is `floor((c · α + 128 · (255 − α)) / 255 + ½)`, with `c` the
  pixel's 8-bit channel and `α` its alpha, in exact integers. It is exact at
  `α` 0 and 255, so a transparent pixel is the grey, an opaque one keeps its
  colour, and a preview of opaque frames is the same bytes as before
  blending. For example, `(255, 0, 64)` at `α = 191` previews as
  `(223, 32, 80)`, and `200` at `α = 100` as `156`.
  (`export.blend_over_background`)
- in exact colors when a frame, blends included, has at most 256 of them;
  otherwise reduced to 256 without dithering, with a warning naming the clip
  (owner decision 2026-10-01)
- each frame lasting the clip's frame duration, rounded to the nearest 10 ms
  and at least 20 ms
- looping forever; one-shot clips hold their last frame for an extra 500 ms
  before repeating

GIF stores a width in 16 bits and a delay in 16 bits of centiseconds. A
preview wider than 65,535 pixels, or any frame delay over 655,350 ms
(including a one-shot's extra 500 ms), is a usage error (exit 2) naming the
clip, the computed width or delay, and the limit. The preview is never
scaled, clamped or split to fit (owner decisions 2026-10-02).

A paletted frame without partly transparent pixels uses at most 255 colours
plus the grey background, so its preview keeps exact colours without a
quantization warning. Partly transparent pixels add their blends, so a
paletted frame with them may exceed 256 colours, and then takes the
reduction and its warning like any other frame (alpha design D-13); while
it has at most 256 it keeps them exactly. Preview handling is otherwise
unchanged.

**Lit previews** (lighting sheet design D-4, D-5, D-13, D-14, D-22, D-23,
D-24). With a light placed (`light.position` set) and previews on, each
clip's lit preview, `<stem>-lit.<clip>.gif`, is written beside its flat one
and handled exactly as it is: the same layout, scale, background, timing and
limits, and the same 256-colour reduction, whose warning names the clip's
lit preview. Each covered pixel, alpha above 0, is lit with the normal map
first, keeping its alpha, then blended over the grey exactly as a flat
preview's is (alpha design D-11, D-13). Without a light every preview is flat and no lit preview is
written. With previews off a placed light is recorded but unused, with one
warning saying so. Light is previewed, never baked: the colour sheet, flat
previews and maps are the same with and without a light. The ordinary look
shows each material's flat, unlit colour, so a lit preview over it applies
the light once (alpha design D-8, which replaces lighting sheet design
D-23).

The light sits in the camera's frame, fixed to the camera, so every
direction of the subject sees it from the same place: `x` screen right, `y`
screen up and `z` toward the viewer, in sheet pixels from the ground point,
the depth map's units. It does not fade with distance, so placed far away it
acts as a distant light. For each pixel the colour covers, in each cell, in
NumPy `float64`, elementwise (lighting sheet design §Numerical reference),
which is what a game reading the exported maps computes:

1. *Inputs:* the reduced colour pixel after cleanup, and the pixel's normal
   and depth **as encoded**: the normal map's bytes and the depth map's
   code, even when neither file is written.
2. *Normal:* `m = 2 · byte / 255 − 1` per component, `N = m / |m|`.
3. *Depth:* `d = (code − 32768) / 16`.
4. *Position,* at the pixel's centre: `P = (c + ½ − gx, gy − r − ½, d)`,
   where `c` and `r` are the pixel's column and row within its cell from the
   cell's top-left and `(gx, gy)` is the ground pixel corner.
5. *Light direction:* `V = light − P`. If `V` is exactly `(0, 0, 0)`, the
   light sits at the pixel and the diffuse term is 0. Otherwise
   `W = V / max(|Vx|, |Vy|, |Vz|)` and `L = W / |W|`, so a light at `1e200`
   or `1e-200` from the pixel still gives an exact direction.
6. *Factor:* `q = min(1, max(0, N · L))` and
   `f = min(1, A + (1 − A) · I · q)`, with `I` the intensity and `A` the
   ambient level. `q` is bounded above as well as below because rounding
   can make `N · L` exceed 1, which with an intensity near the float64 limit
   would overflow (a correction from #100's issue review to the lighting
   design's Numerical reference).
7. *Colour:* each of R, G and B is decoded with the fixed sRGB table (the
   palette mapping's), multiplied by `f`, and encoded with `s = 12.92 · x`
   for `x ≤ 0.0031308`, else `1.055 · x^(1/2.4) − 0.055`, and written as
   `min(255, floor(255 · s + ½))`. Alpha is unchanged; a transparent pixel
   stays `(0, 0, 0, 0)`.

No step produces a NaN or infinity for any finite light. The lit preview
uses encoded depth, so a covered depth beyond the depth map's range is an
[overflow](#scale-and-ground-point) whenever lit previews are written.

Previews exist for review in motion (V-12) and are not part of the sheet
contract.

## Reproducibility

(V-2)

Given the same input bytes, settings and generator (tool, Python, numpy,
Pillow and Blender versions, renderer, colour and shade techniques), the sheet PNG, its
normal and depth maps and JSON are byte-identical. To make that true:

- sample times are exact
- no timestamps are written anywhere
- sorting is fixed wherever order is not already defined
- output encoding is fixed
- palette mapping uses its fixed sRGB table and NumPy arithmetic; the recorded
  NumPy version participates in the generator and fingerprint

Output from a different Blender version or GPU may differ; the recorded
generator and fingerprint make such a difference visible.

A sheet reproduces itself (owner decision 2026-10-11, settings design D-16):
rerunning with `--settings-from` that sheet, the same model, the same output
file name and no other options gives a byte-identical PNG, JSON and
previews, flat and lit, and the same normal and depth maps, with the same
generator. A sheet made with `--no-preview` reloads writing no previews, one made with
`--no-normals` writing no normal map and recording `null` for it, and one
made without `--depth` writing no depth map. A recorded camera direction is
kept exactly as recorded, never normalised again, so a sheet with any
direction and roll reproduces itself too (projects and camera design D-14).
The whole-command Blender tests check this.

## Project layout

(V-10, V-12)

```
pyproject.toml            console script: moskophoros = moskophoros.cli:main
requirements.lock         exact tested versions
src/moskophoros/
  cli.py                  options, presets, settings resolution, exit codes
  settings.py             the settings schema table, settings files, layers
  defaults.yaml           the shipped settings defaults, installed with the package
  gltf.py                 .glb reading: scenes, clips, time ranges, validation
  views.py                camera and direction math
  sampling.py             sample times
  fit.py                  scale, cell and ground-pixel resolution, overflow
  capture/
    backend.py            the capture boundary: job in, manifest out
    blender.py            finds and runs Blender, checks its version
    blender_script.py     runs inside Blender; the only bpy code
  stylize.py              plain and most-common-colour reductions, material ramps
  cleanup.py              pass-through
  export.py               sheet, JSON, previews
  imageops.py             shared image operations
  palette.py              ordered exact RGB palette reading and validation
  materials.py            material library reading, validation and warnings
  yamlfile.py             the strict YAML reader for files the owner writes
tests/
```

- Python 3.13 or newer, matching the Python Blender 5.2 bundles (owner
  decision 2026-09-29, CI foundation design D-5). Runtime dependencies are
  numpy, Pillow and PyYAML; pytest and ruff are development dependencies.
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
- settings files: the schema table and `defaults.yaml` agreeing, each layer's
  precedence, `auto` and `null`, paths and every refused file

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
| Auxiliary capture buffers (base color, material ID) | The first style pass that needs them: per-material colour ramps, which need material IDs (owner decision 2026-10-04). |
| Per-material colour ramps | The owner starts a later style arc. |
| A free chain of passes beyond the four looks | The owner requests it. Settings files are delivered (owner decision 2026-10-11, settings design D-2). |
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
