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
- `hero.json`, the `moskophoros.sheet/2` description of every frame, the
  settings and style used and a fingerprint of them;
- `hero.<clip>.gif`, an animated preview of each clip in every direction,
  unless `--no-preview` is given.

Outputs are published only when the whole run succeeds, so a failed run leaves
earlier outputs as they were. `--settings-from hero.json` reuses an earlier
sheet's view, scale, cell, ground point and style, so new clips line up with
it. `--reduce mode` keeps the most common colour in each supersampled block.
`--palette colours.hex` (also `.gpl` or `.png`) adds palette mapping: plain maps
after averaging; mode maps before voting, so nearby shades pool their votes.
An earlier sheet's palette is reused from its JSON without the original file;
`--palette FILE` replaces it and `--no-palette` drops it.

`moskophoros --help` lists every option.

The full contract, covering every option, the sheet and JSON formats, the
exit codes and how scale and the ground point are chosen, is in
[docs/design.md](docs/design.md). The goals and long-term direction are in
[docs/vision.md](docs/vision.md).

## Requirements

- Python 3.13 or newer, with numpy and Pillow
- Blender, run headless for rendering. The supported version is recorded in
  [docs/design.md](docs/design.md#supported-blender-version).

## License

MIT. See [LICENSE](LICENSE).
