# Style pass 1 acceptance

This records the owner's acceptance of the style pass 1 looks, following #55 and vision V-12. Style pass 1 is the epic #50; its slices were delivered with #51, #52, #53 and #54.

## Verdict

**Accepted by the owner on 2026-10-05 at 21:19 UTC.** The owner accepted the four-look output offered for review, writing:

> "pause all the work until we get git back, including your 15 and 1 hour chron jobs, the janitor, the managers, i approve those moskophoros images, those look good. everything else will have to wait"

The owner's assistant, laz, relayed the verdict in the project chat (`#moskophoros`, message `htiy3c8sgugdvzuep85wqqpaen`, 2026-10-05 21:22 UTC). The rest of that message paused other work while GitHub was unavailable; the verdict on the images is the part recorded here.

What was offered: the four sheets and eight previews listed under [Output](#output), at their paths on the owner's Mac, with byte-identical copies under other names delivered to the owner's library; and a compact set, a native-size comparison of the four looks with native-size `Walking` previews. The record does not say which of these files the owner personally viewed.

The quoted verdict approves the images. It says nothing about the default look, which stays `plain` (style pass 1 design D-1), and ranks no look above another.

Choosing Vince128 as the palette was an input choice (D-16), made before rendering. It is not itself a verdict; the owner's verdict above is the only one, and it is the owner's alone (V-12).

The verdict is bound to this exact output: master `a98cb0b3e035d6ce1e4e579bc636b48a5892f983`, and the sixteen files whose hashes are listed under [Output](#output).

## Input

**Model.** RobotExpressive, the same file slice 1 was accepted with; its source, licence (CC0 1.0) and attribution are in [slice-1.md](slice-1.md#input).

- **SHA-256:** `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319`, 463,988 bytes.
- **Clips:** `Walking` loops, `Jump` plays once.

**Palette.** Vince128, `vince-128.gpl`, chosen by the owner on 2026-10-04 (D-16).

- **SHA-256:** `d7fc8fefc702d2492b72f3c34fe34f59b5b8af109bbde853114ed56cce2ca586`, 3,901 bytes. 128 unique opaque colours; the `.gpl` order matches the package's `vince-128.hex`.
- **Package:** `vince-128-palette.zip`, SHA-256 `36cbc94b3f7a5949b884d5adaa57ba8ff4994e0c0b57c4ae4420f0a1a6a21ac8`, kept with the palette in `~/Documents/Codex/2026-10-04/task-3/inputs/`.
- **Provenance,** as the package README states it: an original 128-colour palette created for Vince on 4 October 2026. The ramp construction method is credited to Raymond Schlitter / SLYNYRD, *Pixelblog 1: Color Palettes*. No licence is stated, and none is inferred.

Neither the model nor the palette is committed, in line with AGENTS.md §Files.

## Commands

Run on 2026-10-05, one after another under the shared moskophoros Blender lock, with master at the commit above. Each command below is copied literally from its run's log, with the working directory the log records:

    cd /Users/vincentcoghlan/.local/share/moskophoros-acceptance/robotexpressive

    # plain
    /Users/vincentcoghlan/worktrees/coghex/moskophoros/accept-55-a98cb0b/.venv/bin/moskophoros --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8  RobotExpressive.glb style-pass-1-a98cb0b/plain/RobotExpressive.png

    # mode
    /Users/vincentcoghlan/worktrees/coghex/moskophoros/accept-55-a98cb0b/.venv/bin/moskophoros --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8 --reduce mode RobotExpressive.glb style-pass-1-a98cb0b/mode/RobotExpressive.png

    # plain-vince128
    /Users/vincentcoghlan/worktrees/coghex/moskophoros/accept-55-a98cb0b/.venv/bin/moskophoros --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8 --palette /Users/vincentcoghlan/Documents/Codex/2026-10-04/task-3/inputs/vince-128.gpl RobotExpressive.glb style-pass-1-a98cb0b/plain-vince128/RobotExpressive.png

    # mode-vince128
    /Users/vincentcoghlan/worktrees/coghex/moskophoros/accept-55-a98cb0b/.venv/bin/moskophoros --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8 --reduce mode --palette /Users/vincentcoghlan/Documents/Codex/2026-10-04/task-3/inputs/vince-128.gpl RobotExpressive.glb style-pass-1-a98cb0b/mode-vince128/RobotExpressive.png

The flags are slice 1's acceptance command's, plus each look's options. The executable is the console script of a clean, detached worktree at that commit, with no changes. The palette was passed by its absolute path; the sheets record only its base name, as design §Export requires. Each command ran wrapped in `/usr/bin/lockf -k ~/.local/state/project-manager/moskophoros/blender.lock /usr/bin/time -l`. The logs are kept beside the outputs, in `logs/plain.log`, `logs/mode.log`, `logs/plain-vince128.log` and `logs/mode-vince128.log`.

| Look | Exit | Wall time | Warnings |
|---|---|---|---|
| Plain | 0 | 47.51 s | 2: preview colour reduction |
| Most common colour | 0 | 54.60 s | 2: preview colour reduction |
| Plain with Vince128 | 0 | 58.47 s | none |
| Most common colour with Vince128 | 0 | 925.66 s | none |

The plain and most-common-colour runs each printed:

    moskophoros: warning: clip 'Walking''s preview has frames with more than 256 colors, reduced to 256 without dithering
    moskophoros: warning: clip 'Jump''s preview has frames with more than 256 colors, reduced to 256 without dithering

These are the preview colour reduction design §Export specifies and D-14 keeps. Those looks' preview frames have more than 256 colours, so their GIFs are reduced to 256 without dithering. The sheets keep exact colours, and the paletted looks' previews keep exact colours too. Slice 1's accepted run printed the same two warnings.

The most-common-colour run with Vince128 took about 15 minutes, against about a minute for each of the others. Blender finished early; the time was spent mapping colours, because that look maps the supersampled pixels to the palette before the vote (D-7), about 64 times as many as the plain look with Vince128 maps. This is recorded as observed; the verdict asks for no change.

## Environment

- moskophoros 0.1.0, at master `a98cb0b3e035d6ce1e4e579bc636b48a5892f983`
- Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0
- Blender 5.2.2 LTS, with the Workbench renderer and studio light `Default`

Every sheet's JSON records this same generator, and it is the same as slice 1's accepted run.

## Resolved settings

These are taken from the sheets' JSON, and are the same for all four looks except `settings.style`.

- **View:** pitch 30°, 8 directions, start angle 0°, orthographic. The preset is recorded as `custom` because `--directions` was given explicitly (design §Presets, D-13). The values are the `iso` preset's own.
- **Capture:** model yaw 0°, 12 fps, supersample 8.
- **Scale and placement:** 39.45430057639541 pixels per meter, auto-fitted to a 256×256 cell. The ground point (0, 0, 0) m lands on cell pixel (128, 222).
- **Root motion:** `error`.
- **Frames:** `Walking` has 11 frames of 87.1 ms, looping. `Jump` has 9 frames of 88.5 ms, one-shot.

**The style record.** Each sheet's `settings.style` was read from its JSON and checked against the expected record:

| Look | `settings.style` | Fingerprint |
|---|---|---|
| Plain | `reduce` `plain`, `palette` `null` | `sha256:dbd195a86737e032610cdf3bfefa2fde4f9d1c4f38c2ad035e73ef88ae8cc79d` |
| Most common colour | `reduce` `mode`, `palette` `null` | `sha256:b461ffacb0005003272c4b8f1ca92092463241744585385398eb0872780a4551` |
| Plain with Vince128 | `reduce` `plain`, `palette` `source` `vince-128.gpl`, `sha256` `d7fc8fef…ca586` in full, and Vince128's 128 colours in file order | `sha256:e73067b97a8ade4a9a366637ad6fb7d03b1c4f7a153e65b4fa5c401d65afba37` |
| Most common colour with Vince128 | `reduce` `mode`, `palette` `source` `vince-128.gpl`, `sha256` `d7fc8fef…ca586` in full, and Vince128's 128 colours in file order | `sha256:6e9498bd18472624b1346d7d059d49c5c89e8bd108f9236683ab98783916e3dd` |

Every sheet is 2816×4096 RGBA, with alpha only 0 or 255, and all four make the same pixels transparent. The two paletted sheets use only Vince128 colours: 32 entries with the plain look, 29 with the most-common-colour look.

## Output

The outputs are kept on the owner's Mac, in `~/.local/share/moskophoros-acceptance/robotexpressive/style-pass-1-a98cb0b/`, one directory per look, with the evidence manifest `MANIFEST.md` and the run logs. Generated sheets and previews are never committed.

| Look | File | Size | Bytes | SHA-256 |
|---|---|---|---|---|
| Plain | `plain/RobotExpressive.png` | 2816×4096 RGBA | 2,672,577 | `17cbce33eefffa7a10b4b6e01d51f3c3aa78e07d1793089b7b8d0562ec38d63a` |
| Plain | `plain/RobotExpressive.json` |  | 30,452 | `c0189fbd3c35e9cdfeaf21d7618a5c8dc2bb8ad24d7aed302517e565d8fd290a` |
| Plain | `plain/RobotExpressive.Walking.gif` | 8192×1024, 11 frames | 4,413,020 | `95f4c43fe6b1d414b7063b3a23ab09c2b449dfba015d05dccf23fc8a155995fd` |
| Plain | `plain/RobotExpressive.Jump.gif` | 8192×1024, 9 frames | 3,660,842 | `9d82e36866c5e6baa48ceeed0c8ddb964a0a5be82ce4f0bdb2b154cb75be7382` |
| Most common colour | `mode/RobotExpressive.png` | 2816×4096 RGBA | 1,720,198 | `b1357975c21ed03c4754355eba5fdd75d374c009242ad014c98b6288a681f536` |
| Most common colour | `mode/RobotExpressive.json` |  | 30,451 | `629cbc07449d6e5dd9841bb9ca1d43bf49858444f81f5113c3248227b9b8cb3a` |
| Most common colour | `mode/RobotExpressive.Walking.gif` | 8192×1024, 11 frames | 3,186,832 | `16f8285a946a1e09c49be8e83c5f1e37bcc0bb024bf19b08efce04638cabfdda` |
| Most common colour | `mode/RobotExpressive.Jump.gif` | 8192×1024, 9 frames | 2,633,065 | `49c6ba0033ac3498d9bd957af7773482fea2a269988b9a6fcb583fe428b6e96d` |
| Plain with Vince128 | `plain-vince128/RobotExpressive.png` | 2816×4096 RGBA | 1,160,979 | `b07337ac3949bf1f0c008cc1089cdd4e0e764aea1ed2f352470f0a00f5613e77` |
| Plain with Vince128 | `plain-vince128/RobotExpressive.json` |  | 33,295 | `07a9cc7276135e28ef1b202e51e423ee38819d6b688192944487482b5d6a4fc1` |
| Plain with Vince128 | `plain-vince128/RobotExpressive.Walking.gif` | 8192×1024, 11 frames | 1,981,696 | `328212be2d97b26f337301e2150316533a44d3f74acda2d3025fab82ad90994c` |
| Plain with Vince128 | `plain-vince128/RobotExpressive.Jump.gif` | 8192×1024, 9 frames | 1,617,716 | `67e60300b2705422556585c88474e6ac1f7c469e4cda5d3fc04980f2638a4943` |
| Most common colour with Vince128 | `mode-vince128/RobotExpressive.png` | 2816×4096 RGBA | 832,093 | `6aed9564901ae341261805d5656dda5d7647cbddf88e25a6270de5c1aa12fea1` |
| Most common colour with Vince128 | `mode-vince128/RobotExpressive.json` |  | 33,294 | `5ef6a60f37fbb9970629581b0ceebc46ed1ed9631ca271ac415915e9ad6ed001` |
| Most common colour with Vince128 | `mode-vince128/RobotExpressive.Walking.gif` | 8192×1024, 11 frames | 1,574,292 | `82a3312768cbbdbcb3e53a57d5795772e75d859ea254d9cdde7f242c54856ee6` |
| Most common colour with Vince128 | `mode-vince128/RobotExpressive.Jump.gif` | 8192×1024, 9 frames | 1,293,784 | `26d77db3fa1e29841d735901504005c7ed728594730f0323929ebb01a270ee00` |

## Plain compared with slice 1

The plain sheet is **byte-identical** to slice 1's accepted sheet: both PNGs have SHA-256 `17cbce33eefffa7a10b4b6e01d51f3c3aa78e07d1793089b7b8d0562ec38d63a`. Both plain previews are byte-identical to slice 1's as well.

The plain JSON differs from slice 1's only where style pass 1 changed the record: `schema` is `moskophoros.sheet/2` instead of `/1`, `settings.style` is added as `{"reduce": "plain", "palette": null}`, and so the fingerprint is `sha256:dbd195a8…c79d` instead of `sha256:c97f3e7c…70cb`. Every other field, including the generator, is equal.

## Deviations

- The first attempt at the plain render stopped inside the render wrapper script, before Blender started. The script passed the plain look's empty option list in a way macOS's bash 3.2 rejects. Nothing was rendered or written to `plain/`. The script was fixed and the failed attempt's log was removed; the four successful runs' logs are kept, as listed under [Commands](#commands).
- No code was changed for the review, and no input was modified.
