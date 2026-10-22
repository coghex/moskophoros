# Projects and camera acceptance

This records the owner's review of the projects and camera arc, following #132 (CAM-5) and vision V-12. The arc is epic #127. Its code slices were delivered with:

| Slice | Issue | Pull request |
|---|---|---|
| CAM-1, add projects and a single global settings file | #128 | #133 |
| CAM-2, make the view, scale and framing settings-file settings | #129 | #134 |
| CAM-3, point the orthographic camera with a direction and roll | #130 | #135 |
| CAM-4, add the perspective projection | #131 | #136 |

The design is [`docs/archive/designs/projects_camera_design.md`](../designs/projects_camera_design.md). What the review shows was decided by the owner (design D-15):
1. Synarchy's isometric sheet through `--project synarchy`, byte-identical to today's;
2. a straight-on perspective panel of the robot, with no baked light;
3. a camera with a general direction and a roll.

## Verdict

**Accepted.** On 2026-10-20 at about 15:15 UTC, typed in the manager's terminal after viewing the decision page (see [Review images](#review-images)), the owner answered the three review questions together:

> "ok good, all three tests are correct to my eye."

The questions, as posted to the project chat on 2026-10-20 at 04:10:58 UTC:

1. Is render 1, the chest through `--project synarchy`, Synarchy's look, unchanged? It is byte-identical to the pre-migration and 5c59809 baselines.
2. Is render 2's straight-on perspective framing what the art panels need? The measured fact given with the question: the fitted scale is limited by the cell's width (the sprites span columns 1 to 119 of 128), so rows 0 to 84 of each 192-tall cell stay empty.
3. Does render 3 show the camera pointing and rolling as intended? It looks 45° down with a roll of 0.125 (22.5° clockwise), beside the plain iso reference.

The owner's answer covers all three. No change was asked for and no follow-up issue is filed. The verdict reached this agent as the manager's instruction to resume the review, which quotes the owner's words; it carries no cmux message id.

## Earlier owner decisions

These are quoted and kept apart from the verdict; none of them is the verdict.

- **The review was requested** on 2026-10-19 in the moskophoros manager's terminal. The manager reported #128 to #131 merged and asked whether to start a review agent on #132. The owner answered: "yes, start the review agent on 132" (request moskophoros-20261019-8).
- **The review commands were signed off before rendering,** on 2026-10-20 at 03:27:56 UTC, typed in the manager's terminal. The manager showed the owner the saved proposal `proposal.md` (SHA-256 `fecec322cbb7c4618cac691deb38f5295eedd4b94f521cc9bc55c9e0a0ba83dc`): the commands under [Commands](#commands), the baseline, every input's hash and the planned project file. The manager asked three things: to sign off the commands as written; to keep or reword the project file's two out-of-date comments; and whether to include the unrolled reference for render 3. The owner answered:
  > "i approve, go for it"

  Relay: cmux message `83b42732-9d48-4191-8030-d8e42ad2ccc8` from the manager. It reads the answer as the proposal as written, with its own defaults: the comments stay unedited, and the reference is included.

## The project file's move

Made on 2026-10-20 at 03:43:10 UTC, after the [baseline](#the-pre-migration-baseline) and before any review render (design D-15). It is the one change to the owner's `~/.config/moskophoros/` that #132 authorises. `projects/` did not exist before.

| File | SHA-256 | Bytes |
|---|---|---|
| `~/.config/moskophoros/synarchy.yaml`, the original, unchanged and kept as the copy | `9195adfe08c7b0866143076d76079a6523c192f8152c764db0ab02805af344f4` | 1,587 |
| `~/.config/moskophoros/projects/synarchy.yaml`, new | `e634338df4acbd1533402b1699be5cdae33563586d089df578c1796c7ed1a5ad` | 1,590 |

The new file is the original byte for byte, except its one relative path, rebased so it names the same file:

```
17c17
< palette: palettes/synarchy.gpl     # relative to this file
---
> palette: ../palettes/synarchy.gpl     # relative to this file
```

- **The comments were not edited,** as signed off. Two of them now describe the old use: "Use with: moskophoros --config ~/.config/moskophoros/synarchy.yaml", and the note that the view and scale wait for this design.
- **Before rendering,** `check_settings.py` checked the head tool's own resolution, with no Blender involved: `resolve_settings`, then `capture_settings` and `style_record`. It compared render 1's command against the pre-migration command B1:
  - every resolved setting was the same, except the fields that only say where a setting came from (`config`, `project`, `origins`, `explicit`) and the output path;
  - the palette resolved to the same file, `~/.config/moskophoros/palettes/synarchy.gpl`, SHA-256 `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c`;
  - neither command uses a library.

## Input

All under `~/.local/share/moskophoros-acceptance/`, except the owner's settings. None is committed. All are review inputs, never defaults or fixtures (V-1).

| Input | SHA-256 | Bytes |
|---|---|---|
| `alpha-model/v5/chest.glb`, the alpha review's chest ([alpha.md](alpha.md#input)) | `04932ad4c77d1348d6d123fa4fda8924edbfa338e7c25a8de814b7200ed3a72c` | 58,300 |
| `robotexpressive/RobotExpressive.glb` ([slice 1](slice-1.md#input)) | `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319` | 463,988 |
| `cutout-model/v1/shrub.glb`, the cutout review's shrub ([alpha.md](alpha.md#cutout-input)) | `7a1a29382888c8c21a0b19c9418fdbcc5417e8ac038c9d626770ca6f4f0b684f` | 143,624 |
| `~/.config/moskophoros/synarchy.yaml`, the owner's Synarchy settings | `9195adfe08c7b0866143076d76079a6523c192f8152c764db0ab02805af344f4` | 1,587 |
| `~/.config/moskophoros/config.yaml`, the global file: `version: 1` and comments only | `257304183ca22ced1386e2484e95be75996a8a067b5eba3e9cea171d25a8fd0a` | 373 |
| `~/.config/moskophoros/palettes/synarchy.gpl`, named by the Synarchy file | `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c` | 4,462 |
| `~/.config/moskophoros/libraries/robotexpressive.yaml`, the owner's robot library (render 2 only) | `33ebb76998abc2366d45a4d1c88f8cef82ccc7a9d4401907e4cde66dc27a2162` | 519 |

The Synarchy file gives:
- the palette;
- `edges: hard`, normals, depth and previews;
- the lit previews' light at `[-53.333, 106.667, 80]`;
- the shade;
- generated-ramp setting C.

It sets no view, scale or library, so the commands give the view and cell as flags.

## Commands

All runs were made from `~/.local/share/moskophoros-acceptance/projects-camera-review/`, one at a time, each under the shared Blender lock, by `run.sh` (SHA-256 `a6a406a56cc63a71a7b34f8d401f3524fc90beced1e9feef901696f2ce700921`). Each run's literal command and output are kept in `<run>.log`. Literally:

    B0:    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-5c59809/.venv/bin/moskophoros --config /Users/vincentcoghlan/.config/moskophoros/synarchy.yaml --clip Open --once Open --view iso --directions 8 --cell 128x128 ../alpha-model/v5/chest.glb baseline-5c59809/chest.png
    B1:    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-305c839/.venv/bin/moskophoros --config /Users/vincentcoghlan/.config/moskophoros/synarchy.yaml --clip Open --once Open --view iso --directions 8 --cell 128x128 ../alpha-model/v5/chest.glb baseline-head/chest.png
    R1:    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-305c839/.venv/bin/moskophoros --project synarchy --clip Open --once Open --view iso --directions 8 --cell 128x128 ../alpha-model/v5/chest.glb render-1/chest.png
    R2:    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-305c839/.venv/bin/moskophoros --project synarchy --materials /Users/vincentcoghlan/.config/moskophoros/libraries/robotexpressive.yaml --clip Walking --clip Wave --once Wave --view side --directions 4 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 ../robotexpressive/RobotExpressive.glb render-2/RobotExpressive.png
    R3:    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-305c839/.venv/bin/moskophoros --project synarchy --clip Sway --view iso --directions 8 --cell 128x128 --camera-direction -1,-1,0 --camera-roll 0.125 ../cutout-model/v1/shrub.glb render-3/shrub.png
    R3ref: /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-305c839/.venv/bin/moskophoros --project synarchy --clip Sway --view iso --directions 8 --cell 128x128 ../cutout-model/v1/shrub.glb render-3-reference/shrub.png

**What the commands show:**
- **B0 and B1** are the pre-migration baseline: today's Synarchy command, `--config` with the same flags as render 1, at the last commit before the arc and at the review head.
- **Render 1** is the same chest through the project.
- **Render 2:**
  - The `side` view looks level: direction (0, 0, −1), roll 0.
  - The preset's 2 profile directions are widened to 4 from 0°, so the panel shows the front, both profiles and the back.
  - The perspective camera is 7 m in front of the feet and 2.4 m up.
  - The colour is flat, and the light reaches only the lit previews.
- **Render 3:**
  - The direction (−1, −1, 0) is normalised to (−0.7071…, −0.7071…, 0), looking down at 45° from the +X side.
  - The roll is 0.125: 22.5°, with the picture turned clockwise.
  - By D-10 the facing is measured from the camera, so in orthographic the direction's heading does not change the picture; its steepness and the roll do.
- **R3ref** is the plain `iso` view of the same shrub, for comparison only.

## Environment

- **moskophoros:** 0.1.0.
  - **The review head:** master `305c839a6007347a7bddb3ac908e96dfb1aa6a0c`, the merge of #136 (CAM-4), with CI on master passing. It was the head of master at both signoff and rendering. The copy is in `tool-305c839/`.
  - **The baseline:** `5c59809f4730e8afeaad0e170c6c361f195313fa`, the last commit before the arc, in `tool-5c59809/`.
  - Each is a clean `git archive` copy with a virtual environment from its own `requirements.lock`.
- **Libraries:** Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0.
- **Blender:** 5.2.2 LTS, headless.
- **Colour:** `cycles-flat-emission`, 1 sample per pixel, seed 0, BOX filter of width 0.01 px, minimum and maximum transparent bounces 64, pass alpha threshold 9.313225746154785e-10.
- **Shade:** `cycles-ambient-occlusion`, 1 sample per pixel, seed 0, BOX filter of width 0.01 px.

## Resolved settings

Every run takes these from the Synarchy file:

| Setting | Value |
|---|---|
| Maps | `normals: true`, `depth: true`; previews on |
| Light | position `[-53.333, 106.667, 80.0]`, intensity 1.0, ambient 0.3 |
| Shade | `ao_distance_m` 1.2, `ao_samples` 64, `occlusion_weight` 0.5, `convexity_weight` 0.25, `range` [190, 225] |
| Generated ramps | `lightness_step` 0.09, `hue_shift_deg` −35, `chroma_fade` 0.6 |
| Style | `reduce: plain`, `edges: hard`, palette `synarchy.gpl` |
| Capture | 12 fps, frames `auto`, supersample 8, model yaw 0°, root motion `error` |

Each run's own values, as its sheet JSON records them. Every view records `preset: custom`, because an explicit `--directions` overrides the preset; the baseline at 5c59809 records the same.

| Run | Camera | View | Cell and scale | Clips | Sheet | Fingerprint |
|---|---|---|---|---|---|---|
| B0 | orthographic, pitch 30° (`/13`: `settings.view`) | 8 directions from 0° | 128×128, 104.03085341729185 px/m, ground pixel (64, 102) | `Open` once, 19 frames | 2432×1024 | `sha256:f3474c3221638df1bfa044182d9c8aa5bbadbc0b0c9c380dbeb0a32b3a22ca32` |
| B1, R1 | orthographic, direction (0, −0.49999999999999994, −0.8660254037844387), roll 0, position `null` | 8 directions from 0° | the same | the same | 2432×1024 | `sha256:72b43c488f79ffe08e5b5357c5fcab7e5389a26e98b249eeb01c86217a865bf3` |
| R2 | perspective, direction (0, 0, −1), roll 0, position (0, 2.4, 7) | 4 directions from 0°: south, east, north, west | 128×192, 18.588482237399656 px/m, ground pixel (64, 178) | `Walking` loop, 11 frames; `Wave` once, 23 frames | 2944×1536 | `sha256:e0c090e7cfd1536a6a21686eccd53150ed10dd914ae7cff8a374181bf9f758a9` |
| R3 | orthographic, direction (−0.7071067811865475, −0.7071067811865475, 0), roll 0.125, position `null` | 8 directions from 0° | 128×128, 94.27275693689624 px/m, ground pixel (64, 116) | `Sway` loop, 24 frames | 3072×1024 | `sha256:ef32e4aa1873803021be245ec86447e166543ab6f82d739dc2f08b6f9b2cd230` |
| R3ref | as B1 | 8 directions from 0° | 128×128, 104.63348333762265 px/m, ground pixel (64, 119) | `Sway` loop, 24 frames | 3072×1024 | `sha256:4602771919d8c29fcbfa882e49fcc5aca2c0909f88f4f3f051200ff475d8a220` |

Render 2 also uses the owner's robot library, `robotexpressive.yaml`. In render 2, the fitted scale is limited by the cell's width: across every cell, the sprites cover columns 1 to 119 of 128 and rows 85 to 189 of 192.

## The pre-migration baseline

Compared file by file by `compare.py` (SHA-256 `f11c6ab102a10f45979ed5fd02198db87e992607aee25008e63cc5e87b97906f`). Its output is kept as `compare-baselines.txt` and `compare-render-1.txt`.

- **B0 against B1:** all five images are byte for byte the same: the sheet, both maps and both previews. The sheet JSON differs only as D-14 and D-17 allow (`json-diff-baselines.txt`):
  - the schema, `moskophoros.sheet/13` to `/14`;
  - `settings.view` losing `projection` and `pitch_deg`;
  - the new `settings.camera`: orthographic, direction (0, −0.49999999999999994, −0.8660254037844387), roll 0, position `null`;
  - the `fingerprint`, which follows from those.

  Nothing else in the JSON changed, `generator` included.
- **B1 against render 1:** all six files are byte for byte the same, the JSON included.

## Checks before review

Run by `check.py` (SHA-256 `1a2a72fa07e38ab9df5dd1fe3c3e855d172ef4cce272820a2ea467439d921967`) on B1, R1, R2, R3 and R3ref. All 115 checks passed (`checks.txt`).

- **The JSON:** each sheet's JSON records the signed-off model, clips, camera, view, cell and the Synarchy file's settings.
  - It holds no project name. The only Synarchy string is `synarchy.gpl`, the palette's file name.
- **The normal map:** its alpha equals the colour sheet's in every pixel.
- **The depth map:** non-zero exactly where the colour's alpha is above 0.
- **The previews:** named `<stem>.<clip>.gif` and `<stem>-lit.<clip>.gif`, and no other files were written.

Two earlier failures came from the checker, not from the tool. It expected `preset: iso`, where an explicit `--directions` records `custom`, as before the arc. And its project-name test matched the key `projection`. Both were corrected in `check.py` before this run.

**Warnings** the runs printed:
- **Every run, B0 included:** the lit preview had frames with more than 256 colours, reduced to 256 without dithering. Render 2 printed this once per clip.
- **Render 2 also,** three times: materials `Grey`, `Main` and `Black` keep their own `shade.range`, [190, 225], from the robot library. The global range is the same [190, 225].

## Review images

The page `projects-camera-review/page/index.html` was given to the owner as a `file://` link. All its images sit in `page/`. The owner found it hard to read, so the manager built a simplified decision page at `projects-camera-review/decide/index.html` (SHA-256 `c26ab85ec574df72e29041b05855e5230f4395d21b29e705df4d6e56c9592126`) with a selection of the same images: its 13 image files are each byte-identical to the file of that name in `page/`. The owner's verdict came after viewing that page. They were made by `make_page.py` (SHA-256 `90fa22101798d53ca8acc3e5532d2eeda0ee5d285b9951e56c191bf87e29a7ef`), run with the head copy's Python, outside the repository.

Every image is labelled with what it shows and the exact command. They are the runs' own pixels, enlarged by whole pixels only. PNGs are written enlarged; the tool's GIFs are scaled by the browser with pixelated rendering.

- **For each of R1, R2, R3 and R3ref:**
  - the colour sheet over a checkerboard at native size, and over dark grey at 2×;
  - its alpha alone, at 2×;
  - the normal map, at native size and 2×;
  - the depth map, visualised: covered pixels are stretched from the sheet's farthest to nearest, with nearer brighter. It is shown at native size and 2×;
  - the flat and lit previews, at native size and 2×.
- **Render 1:**
  - `compare.py`'s full output and the JSON difference;
  - frame 0 of every direction, 3×, for R1, B1 and B0, one above the other.
- **Render 2:**
  - frame 0 of `Walking` in all four directions, 4×;
  - every `Walking` frame facing the camera, 3×;
  - `Wave` in profile, every second frame, 3×.
- **Render 3:** frame 0 of every direction, 4×, above the same frames of R3ref.

## Output

Nothing here is committed. Each file's size in bytes and SHA-256:

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| B0 | `chest.png` | 140,562 | `8a376e5c5392ca15ab92915f99bc3b550a3f66bf47fa2e64ca19f9bbb3edcccd` |
| B0 | `chest.json` | 32,453 | `48d3cbda0f95c21eb6b9c12fe9706491d45ab11369b6eeb804a44f464126b8ec` |
| B0 | `chest.normal.png` | 363,340 | `bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36` |
| B0 | `chest.depth.png` | 271,410 | `d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26` |
| B0 | `chest.Open.gif` | 1,278,737 | `d50e5ffce29dda92ec0ca16150a753c99f382f5f4eae31cd9a62fc1c0885936b` |
| B0 | `chest-lit.Open.gif` | 3,329,487 | `fac81c4c097f23b1e254422d23757de22feb480a3f142127884d2a690548a7ad` |
| B1, R1 | `chest.png` | 140,562 | `8a376e5c5392ca15ab92915f99bc3b550a3f66bf47fa2e64ca19f9bbb3edcccd` |
| B1, R1 | `chest.json` | 32,594 | `98b0da1b6e5cb9a67281a137007b9b6aed723d02ad004926826739000b505357` |
| B1, R1 | `chest.normal.png` | 363,340 | `bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36` |
| B1, R1 | `chest.depth.png` | 271,410 | `d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26` |
| B1, R1 | `chest.Open.gif` | 1,278,737 | `d50e5ffce29dda92ec0ca16150a753c99f382f5f4eae31cd9a62fc1c0885936b` |
| B1, R1 | `chest-lit.Open.gif` | 3,329,487 | `fac81c4c097f23b1e254422d23757de22feb480a3f142127884d2a690548a7ad` |
| R2 | `RobotExpressive.png` | 187,079 | `881676ebfa9665e8219e99d8ed810451c544dba1b71bd35f033bb3ce603a1344` |
| R2 | `RobotExpressive.json` | 31,511 | `a857d620b4918152fd116530b7aa52f9a498c13e4ca8f98cd51650bffbb598d7` |
| R2 | `RobotExpressive.normal.png` | 715,425 | `061912c645a466fe87ccbea6c38d2e646147787c03ff70f96b9705b734778828` |
| R2 | `RobotExpressive.depth.png` | 364,109 | `ce5997d5c719c33dcf4fbb2a24b7628a0a15195822824644c05023c8409b17df` |
| R2 | `RobotExpressive.Walking.gif` | 257,653 | `8e29a33f04b27093986688e81c245686811785c09c7366897a3d0fed99966023` |
| R2 | `RobotExpressive-lit.Walking.gif` | 673,613 | `cd800e79580857253a14df95d1225c819e990c173fd9031feb7b10680cb572bd` |
| R2 | `RobotExpressive.Wave.gif` | 553,547 | `64e5a8e1f2dac86bc4d086e66470280449e54ea3684572faeeba82655715f3c6` |
| R2 | `RobotExpressive-lit.Wave.gif` | 1,430,611 | `270b8acaf175ce3d2f7588f68929d3753485425b1fc560c25d23df334356ea29` |
| R3 | `shrub.png` | 649,365 | `2e19a90f2dcb1a9223b705040ff921b6db45a2fd3ee51e6a4ef4a2da39e69d6d` |
| R3 | `shrub.json` | 39,829 | `978959963314f292a9d70df8a90d72832d66f2764da7d28a96430887ecc8f200` |
| R3 | `shrub.normal.png` | 1,658,775 | `ffe4c255501df031ba9183c28d050b789db9366cb7797f7704826a3f3a94438b` |
| R3 | `shrub.depth.png` | 1,016,059 | `9012b405fb3275e23285049239374c1b7fb00db9f74989fd6125a72c23ee3039` |
| R3 | `shrub.Sway.gif` | 1,973,352 | `d09784c3f7442d25c9db5ad56e439828ff34383fba6a34b7929e72b5668f749d` |
| R3 | `shrub-lit.Sway.gif` | 3,609,641 | `ef7529259194527cdb2ef30f5882850072188c54408a36cbb0cbba46527edfc3` |
| R3ref | `shrub.png` | 646,296 | `3ef5826f009d40f4b78d72110574b92cab0d9fd7d8fb42d3492fa2d48cda9d49` |
| R3ref | `shrub.json` | 39,829 | `439cd8562509070175dbe38c04a673f69ab80ec72119431a238a8827eb96741e` |
| R3ref | `shrub.normal.png` | 1,819,151 | `4e74a38832e00470e8c8a1016d4130ac79dd97dc059ecb0bb32eb79352cd77cb` |
| R3ref | `shrub.depth.png` | 1,161,691 | `665e8abf834ddf9a6e16bbf9806e1dbb6c701fe3bf180016383a5c6b396b59eb` |
| R3ref | `shrub.Sway.gif` | 2,177,051 | `4e7fdf513c5166b5548c9bdf471cc96031746c4c1c9ea28134635db063bf0e98` |
| R3ref | `shrub-lit.Sway.gif` | 4,427,776 | `3fb55aab464727c492c6bb1393bf68cc7370c73bb1731752f11df75d174641e0` |
