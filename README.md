# Moskophoros

Moskophoros turns animated 3D models into pixel-art sprite sheets that stay
consistent in every direction. You animate a model in Blender, export it as
binary glTF (`.glb`), and Moskophoros renders every animation from every camera
direction into a single sheet, with a JSON file describing each frame.

It is a general tool for game art, not tied to any one game. Views are
configurable: top-down, side or isometric, with 1, 2, 4 or 8 directions.

## Status

Early implementation. Two parts exist as library code:

- command-line option parsing and validation, `moskophoros.cli`;
- the GLB reader, `moskophoros.gltf`, which reads a `.glb` file's subject
  scene, clips, time ranges and root nodes, and selects clips by name.

The `moskophoros` command is not available yet, and nothing renders. The goals
and long-term direction are in [docs/vision.md](docs/vision.md); the concrete
design of the first version is in [docs/design.md](docs/design.md).

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
