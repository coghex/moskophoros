# Moskophoros

Moskophoros turns animated 3D models into pixel-art sprite sheets that stay
consistent in every direction. You animate a model in Blender, export it as
binary glTF (`.glb`), and Moskophoros renders every animation from every camera
direction into a single sheet, with a JSON file describing each frame.

It is a general tool for game art, not tied to any one game. Views are
configurable: top-down, side or isometric, with 1, 2, 4 or 8 directions.

## Status

Early implementation. These parts exist as library code:

- command-line option parsing and validation, `moskophoros.cli`;
- the GLB reader, `moskophoros.gltf`, which reads a `.glb` file's subject
  scene, clips, time ranges and root nodes, and selects clips by name;
- camera and direction math, `moskophoros.views`, and sample times and frame
  addresses, `moskophoros.sampling`, which enumerate every requested frame in
  sheet order;
- scale and placement, `moskophoros.fit`, which resolves one scale, cell and
  ground pixel from measured bounds and reports frames that overflow the cell;
- the capture interface, `moskophoros.capture`, which builds capture jobs,
  validates their results, finds Blender, checks its version and runs one
  capture phase;
- measurement and rendering inside Blender,
  `moskophoros/capture/blender_script.py`, which reports each frame's bounds
  and height and each root's travel, and renders each frame as a
  supersampled PNG with the accepted Workbench settings;
- image operations, `moskophoros.imageops`, which load a captured PNG and
  reduce a supersampled image by blocks, and the stylize and cleanup stages,
  `moskophoros.stylize` and `moskophoros.cleanup`, which reduce captured
  frames and pass them through;
- export, `moskophoros.export`, which lays plain frames out on the sheet PNG
  and writes its JSON description and fingerprint.

The `moskophoros` command is not available yet: these parts are not yet
joined into a command that writes a sheet. The goals and long-term direction
are in [docs/vision.md](docs/vision.md); the concrete design of the first
version is in [docs/design.md](docs/design.md).

## Planned usage

```
moskophoros [options] <infile.glb> <outfile.png>
```

This writes `outfile.png` and `outfile.json` beside it.

## Requirements

- Python 3 with numpy and Pillow
- Blender, run headless for rendering. The supported version is recorded in
  [docs/design.md](docs/design.md#supported-blender-version).

## License

MIT. See [LICENSE](LICENSE).
