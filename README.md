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
- `hero.json`, the `moskophoros.sheet/3` description of every frame, the
  settings and style used and a fingerprint of them;
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
of an earlier sheet: its view, scale, cell, ground point, style, previews and
clip selection. Rerun with the same model and nothing else, it reproduces the
sheet byte for byte. Give `--clip` to choose other clips that line up with it:
the scale, cell and ground pixel are fixed rather than fitted again, and a
new frame that does not fit the cell is an overflow error (exit 4). Only
sheets from this version load; generate older ones again.
`--reduce mode` keeps the most common colour in each supersampled block.
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
format.

With a library, each material's shade comes from ambient occlusion and the
surface's own curvature. `--ao-distance M` (default 0.3), `--ao-samples N`
(1 to 128, default 64), `--occlusion-weight W` (default 0.25) and
`--convexity-weight W` (default 1.0) tune it, and `--shade-range LO,HI`
(default 84,191) sets the shade values a ramp spans. For example,
`--convexity-weight 0` drops the curvature term. The sheet records the values,
so `--settings-from` reproduces the look.

The cell, fps, palette, library, previews and shading values can also come
from YAML settings files. `~/.config/moskophoros/config.yaml` (or
`$XDG_CONFIG_HOME/moskophoros/config.yaml`) holds your own defaults, and
`--config look.yaml`, repeatable, applies a file as if its values were given
as options; command-line options still win. Paths in a file are relative to
it, and `~` is your home directory:

```yaml
cell: 48x48        # or auto
fps: 12
palette: ~/palettes/vince-128.gpl
materials: robot-library.yaml
previews: false
shade:             # set any of them; the rest keep their defaults
  ao_distance_m: 1.2
  occlusion_weight: 0.5
  convexity_weight: 0.0
  range: [120, 188]
```

Your own file never changes a sheet loaded with `--settings-from`, while a
`--config` file does. `--no-user-config` skips your file. See
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
