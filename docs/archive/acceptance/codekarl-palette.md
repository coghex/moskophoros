# Codekarl palette and project: owner acceptance

**Status: accepted by the owner, 2026-10-22.** The owner chose Codekarl's
palette and project settings with the manager, in the manager's terminal,
over four review rounds. This is an owner settings choice, not a tool change:
no code, issue or pull request is involved.

## The files

Written to the owner's settings on the owner's word ("Yes, write them"); no
existing file changed.

| File | SHA-256 |
|---|---|
| `~/.config/moskophoros/palettes/codekarl.gpl` | `219351e3e388bb5a5938972ec02d7c40af6a76cf23d627d33868ce4f2bafc4a2` |
| `~/.config/moskophoros/palettes/codekarl.hex` | `0540578adfe97526ecf457509e5ccce8c6044e712845b5b2c30770b68135846b` |
| `~/.config/moskophoros/palettes/codekarl-swatches.png` | `98796ff7367fb8c0e84f11ef9f9593d33f0c79dcb019ccd02dd870991db1290f` |
| `~/.config/moskophoros/projects/codekarl.yaml` | `8578011fd2d025e538de08dd059bd61263ea8f7decdfb0f6eb11a96148a55b70` |

- **Palette:** 127 colours, candidate L2 of round 3: twelve vivid hue ramps of
  nine steps, the first centred on a true red (`#e60003`), one brown ramp, and
  ten greys. Built in OKLCH with `ramp_palette.py` (shadows pulled toward
  blue-purple, highlights toward yellow); each part's exact command is in
  `codekarl-palette/r3/palettes/parts/`.
- **Project:** the palette; `view: side`, `directions: 1`, `start_angle: 0`;
  `edges: hard`; no normal or depth maps; previews on; the shading values the
  panel reviews used (`ao_distance_m` 1.2, occlusion 0.5, convexity 0.25,
  range 190–225); the baked light accepted in the
  [shading record](shading.md) (key 0.35, sky 0.15, ground 0, no dither, camera
  frame); and no `ramp` block, so generated ramps use the shipped formula
  (setting B).

## Decisions, in the owner's words

| Round | Question | Answer |
|---|---|---|
| 0 | Closest existing palette | "E" (warmcool-stark-128) |
| 0 | Size | "About 64 (Recommended)" |
| 0 | Saturation | "Vivid" |
| 0 | Codekarl's world | "Abstract / code" |
| 1 | Which 64-colour candidate | "i think i need a wider variety of objects in order to tell" |
| 1 | Earth colours | "Needs some" |
| 2 | Which candidate | "K3 vivid, longer ramps" |
| 2 | A true red | "i want red, in fact im thinking we expand the palette, can you run the same test on a set of palettes with 90-150 colors?" |
| 3 | Which bigger palette | "L2 127" |
| — | Generated-ramp formula | "B shipped (Recommended)" |
| — | Maps | "No maps (Recommended)" |
| — | Camera in the project file | "Yes (Recommended)" |
| — | Write the files | "Yes, write them" |

## Evidence

Under `~/.local/share/moskophoros-acceptance/codekarl-palette/`, one folder
per round, each with its candidate configuration trees, run commands and
logs. Every render used the shading review's tool (master `354a21f`; the code
is unchanged at `4af50bf`), headless, under the shared Blender lock.

| Page | SHA-256 |
|---|---|
| `r0/index.html`: the existing palettes | `1fd8b0b824861536069729ff3fa0275cfee4060bcccb1d93c59251dd98f2d2b4` |
| `r1/page/index.html`: K1–K3, robot and chest | `79693eeba41fd26ce0327be10fced8c115a30b1a1d6e970b5a787859eb270011` |
| `r2/page/index.html`: K1, K2e, K3, props and shrub | `00fcb00809c6875f9553eeb34e59584f82f7909296a41d34797779fe7cce52ba` |
| `r3/page/index.html`: L1–L3 | `14e359ab5b369c568d7cdadb6acb5c61cc3f29cb78f326ba6eade671eb2dd0b9` |

- **Props test model:** eleven props of one material each (wood, stone, steel,
  brass, skin, cloth, leaf, crystal, a monitor's casing and screen, red
  plastic, paper), built for round 2 at the owner's request for more objects:
  `palette-props-model/v2/props.glb`
  (`8499a0341e7d1cb58561bae0d731e9f423fe69942c8c441a910eaa37c95d2c99`), from
  `make_props_v2.py` (`25966a3e13a8608865c6c7e00d8a4b23d2b16ba54014c4b0127a1614c3935ae8`).
  Its library gives every material a generated ramp from its own colour, so a
  palette's gaps show as wrong colours.
- **Held equal across candidates:** the panel light; the robot's orange, the
  chest's glow and the shrub's leaves on matching hand-picked ramp steps; and,
  from round 2, the generated-ramp formula B.
- **Formula C does not suit small palettes.** Round 2's first renders used
  Synarchy's formula C, which turned the shrub's leaves brown and its pot
  magenta in the 64-colour candidates. They are kept as `r2/runs/*` without
  `-B` and were superseded before the owner saw the page.
- **Check run:** the owner's real settings, `--project codekarl`, rendered the
  props panel pixel for pixel the same as the reviewed `r3/runs/L2-props`
  render, with no maps written (`r3/verify/props.png`,
  `40a9099d114a36d3534f9c8fffc2f96b6835c8e5aca26803dffa32d983d96ca9`).
