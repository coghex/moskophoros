# Moskophoros

Moskophoros turns animated 3D models into pixel-art sprite sheets that stay
consistent in every direction. You animate a model in Blender, export it as
binary glTF (`.glb`), and Moskophoros renders every animation from every camera
direction into a single sheet, with a JSON file describing each frame.

It is a general tool for game art, not tied to any one game. Views are
configurable: top-down, side or isometric, with 1, 2, 4 or 8 directions.

## Usage

```
moskophoros [options] <infile.glb> <outfile.png>
```

For example, to render a model's `walk` loop and its one-shot `attack` in the
eight isometric directions, in 64×64 cells:

```
moskophoros --clip walk --clip attack --once attack --cell 64x64 hero.glb out/hero.png
```

A run writes, beside each other:

- `hero.png`, the sheet: one row per clip and direction, one column per frame;
- `hero.normal.png`, the normal map: the sheet's layout and alpha, each
  pixel's surface direction relative to the camera encoded in RGB, so a game
  shader can light the sprite live; `--no-normals` skips it;
- `hero.depth.png`, only with `--depth`: the depth map, each pixel's depth
  toward the viewer from the ground point in 1/16 sheet pixels, 16-bit
  greyscale, `32768` for the ground point's depth and `0` for no surface, so
  a game can light a pixel from a light at a position; a depth beyond
  ±2047.9375 sheet pixels is an overflow error (exit 4): give a smaller
  `--ppm`;
- `hero-lit.<clip>.gif`, only with `--light X,Y,Z`: each clip's preview lit
  by a point light, computed as a game reading the normal and depth maps
  would, beside the flat one; the light is in sheet pixels from the ground
  point (x right, y up, z toward the viewer), `--light-intensity` and
  `--light-ambient` set its strength, and the sheet itself stays flat;
- `hero.json`, the `moskophoros.sheet/13` description of every frame, the
  settings and style used and a fingerprint of them, naming the maps;
- `hero.<clip>.gif`, an animated preview of each clip in every direction,
  unless `--no-preview` is given.

`--cell WxH` sets the size of every frame. Unless `--ppm N` gives the scale or
`--settings-from` reuses one, the model is scaled to fit the cell, so a smaller
cell gives smaller, chunkier sprites. With neither `--cell` nor `--ppm`, and no
reused settings, the cell is 64×64. `--ppm` alone sizes the cell to fit the
model instead, and `--cell` with `--ppm` fixes both. For 48×48 frames:

```
moskophoros --clip walk --cell 48x48 hero.glb out/hero-small.png
```

Outputs are published only when the whole run succeeds, so a failed run leaves
earlier outputs as they were. `--settings-from hero.json` loads every setting
of an earlier sheet: its view, scale, cell, ground point, style, previews,
normal and depth maps, light and clip selection. Rerun with the same model and nothing else, it reproduces the
sheet byte for byte. Give `--clip` to choose other clips that line up with it:
the scale, cell and ground pixel are fixed rather than fitted again, and a
new frame that does not fit the cell is an overflow error (exit 4). Only
sheets from this version load; generate older ones again.
`--reduce mode` keeps the most common colour in each supersampled block.
The sheet has 8-bit alpha. `--edges hard`, the default, keeps outlines and
cut-out edges crisp: a pixel shows when at least half its block shows a
surface. `--edges soft` gives each pixel its block's mean alpha instead, so
edges keep the partial transparency of the reduction; the maps copy the
alpha, and the previews blend partial pixels over their grey.
`--palette colours.hex` (also `.gpl` or `.png`) adds palette mapping: plain maps
after averaging; mode maps before voting, so nearby shades pool their votes.
An earlier sheet's palette is reused from its JSON without the original file;
`--palette FILE` replaces it and `--no-palette` drops it.
`--materials library.yaml` draws each named material in the model from the
ramps of a shared YAML material library (`.yaml` or `.yml`; JSON libraries are
refused), on the palette (so it needs one): the same
`steel` on another model gets the same colours, and a material the library does
not know takes its default ramp or the ordinary look, named in a warning.
The library is recorded in the sheet's JSON and reused with `--settings-from`
without the original file; `--materials FILE` replaces it and `--no-materials`
drops it. See [docs/design.md](docs/design.md#material-libraries) for the file
format. A library is `schema: moskophoros.materials/3`; a `/2` library still
loads as before, and a `/1` library only needs that line changed.

A `/3` library may give a ramp as properties instead of indices, a base
colour (its lightest shade) and a band count, and the tool generates the
darker shades and snaps each to the palette. `--ramp-step L` (default 0.12),
`--ramp-hue-shift DEG` (default −12) and `--ramp-fade F` (default 0.3) set how
much lighter each shade drops, how far its hue turns and how much colour the
darkest loses; a generated ramp may give its own. Listing indices stays the
exact control. A library may also give the shade range its materials fall
back to:

```yaml
schema: moskophoros.materials/3
ramps:
  stone: [133, 135, 137, 138, 139]
  gold: {base: "#ca9337", bands: 4}
  chrome: {base: "#8c939c", bands: 5, hue_shift_deg: -35, chroma_fade: 0.6}
shade: {range: [190, 225]}   # the range only
materials:
  Main: {uses: gold}
  Cloth: {ramp: {base: "#7a3b2e", bands: 3}}
```

The sheet records each generated ramp's indices, so `--settings-from`
reproduces it without generating again; an explicit `--ramp-*` value
regenerates the ramps it reaches.

With a library, each material's shade comes from ambient occlusion and the
surface's own curvature. `--ao-distance M` (default 0.3), `--ao-samples N`
(1 to 128, default 64), `--occlusion-weight W` (default 0.25) and
`--convexity-weight W` (default 1.0) tune it, and `--shade-range LO,HI`
(default 84,191) sets the shade values a ramp spans. For example,
`--convexity-weight 0` drops the curvature term. The sheet records the values,
so `--settings-from` reproduces the look. A library entry may give its
material its own values, which beat the global ones (a warning says so when
you set a global it overrides); AO samples stay global:

```yaml
materials:
  Grey:
    uses: stone
    shade: {range: [120, 255], convexity_weight: 0.5}
```

`--frames N` samples every clip to N frames, retimed so each frame lasts
`1/fps` (a one-shot still ends on its last pose; `--frames 1` makes a still);
`--frames auto`, the default, samples by duration. A settings file can give a
clip its own count, which beats the global one:

```yaml
frames: 8
clips:
  Jump: {frames: 6}
  Idle: {frames: auto}   # by duration; null: take frames
```

Everything that shapes the picture can also come from YAML settings files,
all sharing one format: the view, scale, cell, ground point, supersampling,
reduction, fps, frame count, palette, library, edges, previews, normal and
depth maps, light, shading and generated-ramp values, and which Blender to
use. The global file,
`~/.config/moskophoros/config.yaml` (or
`$XDG_CONFIG_HOME/moskophoros/config.yaml`), holds your own defaults;
`--config other.yaml` uses another file as the global file instead. A
project, `--project look`, reads `projects/look.yaml` in the same folder and
applies only what it lists, as if its values were given as options;
command-line options still win. Paths in a file are relative to it, and `~`
is your home directory:

```yaml
view: iso          # topdown, side, iso or iso-true
directions: 4      # null: the view's; so are pitch and start_angle
ppm: 40            # or auto, fitted; --ppm auto also drops a configured one
cell: 48x48        # or auto
supersample: 8
reduce: mode       # or plain, the default
fps: 12
palette: ~/palettes/vince-144.gpl
materials: robot-library.yaml
edges: soft        # or hard, the default
previews: false
normals: true      # false: write no normal map
depth: false       # true: write the depth map
light:             # a preview light; null position: none
  position: [-20, 30, 40]
shade:             # set any of them; the rest keep their defaults
  ao_distance_m: 1.2
  occlusion_weight: 0.5
  convexity_weight: 0.0
  range: [120, 188]
ramp:              # generated ramps: setting C, the high-contrast one
  lightness_step: 0.09
  hue_shift_deg: -35
  chroma_fade: 0.6
```

A `view` replaces the pitch, direction count and start angle set below it.
`blender` and `any_blender` choose Blender; they are never recorded in a
sheet. The global file never changes a sheet loaded with `--settings-from`,
except for those two, while a project does. `--no-user-config` uses no global
file. See
[docs/design.md](docs/design.md#settings-files).

`moskophoros --help` lists every option.

The full contract, covering every option, the sheet and JSON formats, the
exit codes and how scale and the ground point are chosen, is in
[docs/design.md](docs/design.md). The goals and long-term direction are in
[docs/vision.md](docs/vision.md).

## Requirements

- Python 3.13 or newer, with numpy, Pillow and PyYAML
- Blender, run headless for rendering. The supported version is recorded in
  [docs/design.md](docs/design.md#supported-blender-version).

## License

MIT. See [LICENSE](LICENSE).
