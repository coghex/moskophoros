# Material styling acceptance

This records the owner's **qualified** acceptance of the material styling proof of concept (the first release of the arc: hand-listed ramps judged by the owner), following #70 and vision V-12. The material styling epic is #63; its code slices were delivered with #64, #65, #66, #67, #68 and #69.

## Verdict

**Qualified acceptance of the proof of concept, by the owner, on 2026-10-08 at 23:00 UTC.** On the delivered plain and most-common-colour renders and the diagnostic finding, the owner said:

> "as for the shading itself, it needs tweaking, but the concept is proven, i would commit"

The owner's assistant, laz, relayed it in the project chat (`#moskophoros`, message `zdf3gpf9a5ucdmnrdz6acgdxbw`, decision `user-mosk70-qualified-POC-acceptance-commit-20261008`, 2026-10-08 23:00:33 UTC), on the exact #70 plain and mode artifacts at master `b1627f21fe34c6e0c91fc2942a8dd0a03bb04289` and the diagnostic finding `6wnp2jbtkznpxf3bjmjrmkzd9a`. The relay asks that it be recorded as a **qualified acceptance of the proof of concept, with the warm palette and art-direction limits and the Grey and Black clipping and saturation limits explicit, and not as approval of the shading as polished**. It also says that further shading tweaks are recorded follow-up only, and that it is not unqualified visual acceptance, epic #63 closure or authority for MAT-8 (generated ramps).

The verdict is the owner's alone (V-12). This record, written by the worker that rendered the outputs, quotes it and does not extend it: it ranks no look above another, says nothing about the default look (which stays `plain`), and approves no particular ramp.

What was offered: the two sheets and four previews listed under [Output](#output), at their paths on the owner's Mac, with the router asked to deliver them in chat. The record does not say which of these files the owner personally viewed.

The verdict is bound to this exact output: master `b1627f21fe34c6e0c91fc2942a8dd0a03bb04289`, the library `library-draft.json` (SHA-256 `e95e26035b5cfbb9bd5ed6371f55bd09566aa1d56322a7e49e9e4151316b4721`), and the eight files whose hashes are listed under [Output](#output).

## Earlier owner decisions

These are quoted and kept apart from the verdict; none of them is the verdict.

- **Library and commands signed off, before rendering (the sign-off is not the verdict).** laz, `#moskophoros`, message `9j8nznw9r4dec9384qes5ftn4e` (decision `user-mosk-materials-implement-20261008`, 2026-10-08 21:10:51 UTC):

  > "The user APPROVES #70 Phase A library AND exactly the two saved PLAIN and MODE render commands, and requests their new sheets/previews here in chat. Approval binds phase-a-proposal.md SHA256 4dbddc5130721948720cb61bccbed6390f5f8a7fe685b6a90e45772b9bdeb022, commit b1627f21fe34c6e0c91fc2942a8dd0a03bb04289, library-draft.json SHA256 e95e26035b5cfbb9bd5ed6371f55bd09566aa1d56322a7e49e9e4151316b4721, RobotExpressive.glb 047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319, Vince128 d7fc8fefc702d2492b72f3c34fe34f59b5b8af109bbde853114ed56cce2ca586. … This approval authorizes rendering, NOT visual acceptance: owner verdict remains pending until they see output; do not mark #70 accepted/complete or publish a verdict now."

  The record keeps the saved proposal `phase-a-proposal.md` (SHA-256 `4dbddc5130721948720cb61bccbed6390f5f8a7fe685b6a90e45772b9bdeb022`), which holds the library draft, its colour table and the two commands.

- **Qualified feedback on the renders, 2026-10-08 21:59:44 UTC** (laz, `#moskophoros`, message `8iytcjavjdsk7qmfryjgac4zmn`, request `user-mosk70-qualified-feedback-diagnosis-20261008`), quoted:

  > "Parent relays this qualified owner feedback on the exact #70 plain/mode artifacts at b1627f21fe34c6e0c91fc2942a8dd0a03bb04289: materials are readable/distinct, animations look good and no weird artifacts were seen; a good first proof of concept. Concerns: orange/yellow looks infrared, shading may be reversed, Grey looks like one flat colour with no shading. This is NOT unqualified visual acceptance or authority to close #70/epic."

  It asked for a read-only diagnosis, which is summarized under [Diagnoses](#diagnoses). It is not the verdict.

- **One diagnostic render approved, 2026-10-08 22:08:42 UTC** (laz, `#moskophoros`, message `sy3nfmpsvugxctc4ijc2mzmmk2`, decision `user-mosk70-one-plain-diagnostic-render-20261008`): "EXACTLY ONE additional PLAIN diagnostic render … retaining intermediate material-ID/shade buffers via existing --work-dir option … retention flag and new output/work directories ONLY. … NO MODE rerender, palette/library/shade-range/AO/code changes, variants, extra experiments or visual acceptance." It was accepted by the project manager before execution (22:09:21 UTC). See [Diagnostic run](#diagnostic-run).

## Input

**Model.** RobotExpressive, the same file slice 1 and style pass 1 were accepted with; its source, licence (CC0 1.0) and attribution are in [slice-1.md](slice-1.md#input).

- **SHA-256:** `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319`, 463,988 bytes.
- **Clips:** `Walking` loops, `Jump` plays once.
- **Materials:** `Grey`, `Main` and `Black`, flat and opaque, so the review does not exercise textures or cutouts.

**Palette.** Vince128, `vince-128.gpl`, chosen by the owner on 2026-10-04 (D-16); provenance in [style-pass-1.md](style-pass-1.md#input).

- **SHA-256:** `d7fc8fefc702d2492b72f3c34fe34f59b5b8af109bbde853114ed56cce2ca586`, 128 unique opaque colours, in the file's order.

**Library.** `library-draft.json`, the review library drafted for `Grey`, `Main` and `Black` on Vince128 and signed off by the owner before rendering (above). It is a review input like the model and palette: never a default or a fixture (V-1).

- **SHA-256:** `e95e26035b5cfbb9bd5ed6371f55bd09566aa1d56322a7e49e9e4151316b4721`, 287 bytes. Contents, verbatim:

```json
{
  "schema": "moskophoros.materials/1",
  "ramps": {
    "shadow": [95, 94, 93],
    "stone": [15, 14, 12, 10, 9],
    "warm": [1, 3, 4, 5, 6]
  },
  "default": "stone",
  "materials": {
    "Black": {"uses": "shadow"},
    "Grey": {"uses": "stone"},
    "Main": {"uses": "warm"}
  }
}
```

Ramps are palette indices into Vince128 (0-based, in the `.gpl` order), darkest first; the default is not used by this model (all three materials have entries):

| Material | Ramp | Band | Palette index | Colour |
|---|---|---|---|---|
| Main | warm | 0 | 1 | `#3b2233` |
| Main | warm | 1 | 3 | `#9e3535` |
| Main | warm | 2 | 4 | `#b65f33` |
| Main | warm | 3 | 5 | `#b99346` |
| Main | warm | 4 | 6 | `#bdbd6a` |
| Grey | stone | 0 | 15 | `#332a30` |
| Grey | stone | 1 | 14 | `#553f46` |
| Grey | stone | 2 | 12 | `#8c6d5d` |
| Grey | stone | 3 | 10 | `#a2a285` |
| Grey | stone | 4 | 9 | `#c3cbb4` |
| Black | shadow | 0 | 95 | `#212829` |
| Black | shadow | 1 | 94 | `#364047` |
| Black | shadow | 2 | 93 | `#5c647d` |

The OKLab lightness of each ramp's entries rises monotonically (warm 0.291 to 0.780, stone 0.297 to 0.830, shadow 0.270 to 0.506).

The model, palette and library are input choices (D-16, D-17): choosing them was made before rendering and is not a verdict. Only the model's source, licence and attribution are in the repository, in [slice-1.md](slice-1.md#input). **None of the three is committed** (AGENTS.md §Files); they stay in `~/.local/share/moskophoros-acceptance/robotexpressive/` and `~/Documents/Codex/2026-10-04/task-3/inputs/`.

## Commands

Run on 2026-10-08, one after another under the shared moskophoros Blender lock, with master at the commit above. Each command below is copied literally from its run's `.command` file (made from the saved `phase-a-proposal.md` lines, SHA-256 `4dbddc5130721948720cb61bccbed6390f5f8a7fe685b6a90e45772b9bdeb022`), with the working directory the `.run` file records:

    cd /Users/vincentcoghlan/.local/share/moskophoros-acceptance/robotexpressive

    # plain
    /usr/bin/lockf -k ~/.local/state/project-manager/moskophoros/blender.lock /usr/bin/time -l /Users/vincentcoghlan/worktrees/coghex/moskophoros/accept-70-b1627f2/.venv/bin/moskophoros --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8 --palette /Users/vincentcoghlan/Documents/Codex/2026-10-04/task-3/inputs/vince-128.gpl --materials /Users/vincentcoghlan/.local/share/moskophoros-acceptance/robotexpressive/material-review/library-draft.json RobotExpressive.glb material-review-b1627f2/plain/RobotExpressive.png > material-review-b1627f2/logs/plain.log 2>&1

    # mode
    /usr/bin/lockf -k ~/.local/state/project-manager/moskophoros/blender.lock /usr/bin/time -l /Users/vincentcoghlan/worktrees/coghex/moskophoros/accept-70-b1627f2/.venv/bin/moskophoros --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8 --reduce mode --palette /Users/vincentcoghlan/Documents/Codex/2026-10-04/task-3/inputs/vince-128.gpl --materials /Users/vincentcoghlan/.local/share/moskophoros-acceptance/robotexpressive/material-review/library-draft.json RobotExpressive.glb material-review-b1627f2/mode/RobotExpressive.png > material-review-b1627f2/logs/mode.log 2>&1

The executable is the console script of a clean, detached worktree at that commit (`~/worktrees/coghex/moskophoros/accept-70-b1627f2`), with no changes: `git status --short` was empty after the renders. The palette and library were passed by absolute path; the sheets record only their base names, as design §Export requires. Each command ran under `/usr/bin/lockf -k ~/.local/state/project-manager/moskophoros/blender.lock /usr/bin/time -l`, with stdout and stderr in the run's log.

| Look | Start (UTC) | End (UTC) | Exit | Wall time | Warnings |
|---|---|---|---|---|---|
| Plain with library | 2026-10-08T21:11:58Z | 2026-10-08T21:18:29Z | 0 | 391 s (`time -l` 390.11 s) | none |
| Most common colour with library | 2026-10-08T21:18:34Z | 2026-10-08T21:39:23Z | 0 | 1249 s (`time -l` 1248.87 s) | none |

Neither run printed anything but the `time -l` report: no warning of any kind, so no fallback for `Grey`, `Main` or `Black`. The most-common-colour run took about 21 minutes, against about 6.5 minutes for the plain run; the proposal had estimated about 1 and 15 minutes, from style pass 1, which had no material pass. This run adds the per-frame material-ID and shade capture (MAT-3) and, for the most-common-colour look, the mapping of the supersampled pixels. This is recorded as observed; the verdict asks for no change.

## Environment

- moskophoros 0.1.0, at master `b1627f21fe34c6e0c91fc2942a8dd0a03bb04289`
- Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0
- Blender 5.2.2 LTS, with the workbench renderer and studio light `Default`
- Shade technique `cycles-ambient-occlusion`: samples_per_pixel 1, seed 0, pixel_filter BOX, filter_width_px 0.01, ao_distance_m 0.3, ao_samples 64, occlusion_weight 0.25, convexity_weight 1.0
- Shade range `[84, 191]`: the default (`backend.DEFAULT_SHADE_RANGE`); no option sets it, and it is recorded in each sheet's JSON.

Every sheet's JSON records this same generator.

## Resolved settings

These are taken from the sheets' JSON (`moskophoros.sheet/3`), and are the same for both looks except `settings.style` and the fingerprint.

- **View:** pitch 30°, 8 directions, start angle 0°, orthographic. The preset is recorded as `custom` because `--directions` was given explicitly (design §Presets, D-13); the values are the `iso` preset's own.
- **Capture:** model yaw 0°, 12 fps, supersample 8.
- **Scale and placement:** 39.45430057639541 pixels per meter, auto-fitted to a 256×256 cell. The ground point (0, 0, 0) m lands on cell pixel (128, 222).
- **Root motion:** `error`.
- **Frames:** `Walking` has 11 frames of 87.1 ms, looping. `Jump` has 9 frames of 88.5 ms, one-shot.

**The style record.** Each sheet's `settings.style` was read from its JSON and checked against the signed-off inputs. It has `reduce`, `palette`, `materials` and `shade_range`, in that order:

| Look | `settings.style` | Fingerprint |
|---|---|---|
| Plain with library | `reduce` `plain`; `palette` `source` `vince-128.gpl`, `sha256` `d7fc8fef…a586` in full, and Vince128's 128 colours in file order; `materials` `source` `library-draft.json`, `sha256` `e95e2603…4721` in full, with `ramps`, `default` (`stone`) and `materials` equal to the library file; `shade_range` `[84, 191]` | `sha256:94d5feffc45eb68f844afe42d81b7d9aff7efd3ec65b3b420b3893f93d721f12` |
| Most common colour with library | the same, with `reduce` `mode` | `sha256:ee8696d0b5eaf7db60b14a861b555d6ca8a8dc15fab4a0f6fa8c23e7ade2d67e` |

Every sheet is 2816×4096 RGBA with alpha only 0 or 255, 2,058,353 opaque pixels in both looks, and the same pixels as style pass 1's sheets (the opaque mask is identical). **Every opaque pixel of both sheets is exactly one of the three ramps' colours**: none uses another palette entry, so none took the ordinary look or a fallback.

Pixels per ramp entry, darkest first (sheet pixels):

| Material | Look | Total | Per entry | Share |
|---|---|---|---|---|
| Main | Plain with library | 1,368,650 | 2 / 20,564 / 640,442 / 292,351 / 415,291 | 0.00% / 1.50% / 46.79% / 21.36% / 30.34% |
| Main | Most common colour with library | 1,368,650 | 2 / 20,614 / 657,616 / 274,595 / 415,823 | 0.00% / 1.51% / 48.05% / 20.06% / 30.38% |
| Grey | Plain with library | 489,366 | 0 / 0 / 0 / 1,615 / 487,751 | 0.00% / 0.00% / 0.00% / 0.33% / 99.67% |
| Grey | Most common colour with library | 489,366 | 0 / 0 / 0 / 1,180 / 488,186 | 0.00% / 0.00% / 0.00% / 0.24% / 99.76% |
| Black | Plain with library | 200,337 | 0 / 0 / 200,337 | 0.00% / 0.00% / 100.00% |
| Black | Most common colour with library | 200,337 | 0 / 0 / 200,337 | 0.00% / 0.00% / 100.00% |

## Output

The outputs are kept on the owner's Mac, in `~/.local/share/moskophoros-acceptance/robotexpressive/material-review-b1627f2/`, one directory per look, with the evidence manifest `MANIFEST.md` and the run logs. Generated sheets and previews are never committed. No upload workflow was installed, so the project manager reported them as durable local artifacts for the router to upload.

| Look | File | Size | Bytes | SHA-256 |
|---|---|---|---|---|
| Plain with library | `plain/RobotExpressive.png` | 2816×4096 RGBA | 576,657 | `331b464ecfa57ee17a346f7d141b514a16173c38706f72795c637720b77fc5b4` |
| Plain with library | `plain/RobotExpressive.json` |  | 34,371 | `7a6774650687a064b1ce9b723f68ebce4079ce8103048823b4512cfe8709386f` |
| Plain with library | `plain/RobotExpressive.Walking.gif` | 8192×1024, 11 frames | 1,182,982 | `4b19990e04d0384dc7a9196761fcdd2ca807d83ea76d1d02ee584d0064a323e2` |
| Plain with library | `plain/RobotExpressive.Jump.gif` | 8192×1024, 9 frames | 969,507 | `4819aa348a5e2293d51e6021bacf7ee5a0fafebf0e6d262d2d0e4ae20d5b2c98` |
| Most common colour with library | `mode/RobotExpressive.png` | 2816×4096 RGBA | 579,031 | `e532a722c26986920f5987179f3bc6c6eac79fab4b54c499da64c19d04ed65d3` |
| Most common colour with library | `mode/RobotExpressive.json` |  | 34,370 | `0fd704ba7b3db422a3067734bd577535645597bad1f3e46dbe2defdb19cef69e` |
| Most common colour with library | `mode/RobotExpressive.Walking.gif` | 8192×1024, 11 frames | 1,182,784 | `3396f669076d4fb5d8f525dc3a94f09f89958dd804ee100e7220231e1df1a2df` |
| Most common colour with library | `mode/RobotExpressive.Jump.gif` | 8192×1024, 9 frames | 969,816 | `15e67cb518257fc33e1a17b359e0673d030808301ea6528f769976b069dfcb95` |

Run logs, run records and the literal command lines (bytes, SHA-256):

| File | Bytes | SHA-256 |
|---|---|---|
| `material-review-b1627f2/logs/plain.log` | 777 | `a66d9b70163e266a0946a84a943f7aaf3201bc0fadbc4472a51b3642894beb01` |
| `material-review-b1627f2/logs/plain.run` | 167 | `0fc9c0e765bdfa8be91b42f5f1b83c8079e7742962481eb5a3e6e81ffdccee96` |
| `material-review-b1627f2/logs/plain.command` | 586 | `6a339fec84b73af612525756c289f78909879d43dacdf7a2a51f1b53446a4c6b` |
| `material-review-b1627f2/logs/mode.log` | 777 | `5de07e381b4c63c17b848dac6003c874a01b456718bf70532c6214947855a779` |
| `material-review-b1627f2/logs/mode.run` | 167 | `dd4b7e309652e9fbfa05bd73acb9fd51b64fc1f04a2b6c7624570fb69b2c0219` |
| `material-review-b1627f2/logs/mode.command` | 598 | `020df88dbdf45230e8ef81c7c03b536d6f02f71709e7f2573928e4e610b87afa` |
| `material-review-b1627f2-diag/logs/plain.log` | 777 | `916a2283d1c3753b52c03f66393819ccb71ca3cb31595662e0a7f8da798df14f` |
| `material-review-b1627f2-diag/logs/plain.run` | 178 | `8798366e5eb867ef3b9473c8cbaf49bae7b17b0aad44912e9e802b0d12e0b26c` |
| `material-review-b1627f2-diag/logs/plain.command` | 710 | `0c4f318c9509a80589116025121eea2c84bf9a3caacf5f26e0068424f7585646` |

## Diagnostic run

After the qualified feedback, the owner approved exactly one more plain render, with the capture's work directory kept, to read the raw shade values (above). It was the saved plain command plus only `--work-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/robotexpressive/material-review-b1627f2-diag/work` and the output directory `material-review-b1627f2-diag/plain/`; no mode run, and no change to the palette, library, shade range, ambient-occlusion parameters or code. The literal command line as saved in its `.command` file ends with the first run's stale log redirect (see [Disclosures](#disclosures)); the effective command is the plain command above with `--work-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/robotexpressive/material-review-b1627f2-diag/work` before `RobotExpressive.glb` and `material-review-b1627f2-diag/plain/RobotExpressive.png` as the output.

- **Start / end (UTC):** 2026-10-08T22:09:41Z / 2026-10-08T22:15:27Z. **Exit:** 0. **Wall time:** 346 s (`time -l` 346.24 s). **Warnings:** none.
- **Its sheet, JSON and both previews are byte-identical to the first plain run's**, so keeping the work directory changed nothing and the render is repeatable:

| File (in `material-review-b1627f2-diag/plain/`) | Bytes | SHA-256 | vs first plain run |
|---|---|---|---|
| `plain/RobotExpressive.png` | 576,657 | `331b464ecfa57ee17a346f7d141b514a16173c38706f72795c637720b77fc5b4` | identical |
| `plain/RobotExpressive.json` | 34,371 | `7a6774650687a064b1ce9b723f68ebce4079ce8103048823b4512cfe8709386f` | identical |
| `plain/RobotExpressive.Walking.gif` | 1,182,982 | `4b19990e04d0384dc7a9196761fcdd2ca807d83ea76d1d02ee584d0064a323e2` | identical |
| `plain/RobotExpressive.Jump.gif` | 969,507 | `4819aa348a5e2293d51e6021bacf7ee5a0fafebf0e6d262d2d0e4ae20d5b2c98` | identical |

- **Retained buffers:** `work/` holds 484 files, 392,978,651 bytes: the measure phase, `render/job.json`, `render/result.json` and, for each of the 160 frames, `render/color`, `render/matid` and `render/shade` PNGs. Each file's size and SHA-256 are listed one per line in `work-manifest.txt` (SHA-256 `e5dbb14caa804764de215bb0c6911e6b0654288b44c159b3e6809d7ae2b6098c`). The buffers are outside the repository and not committed. The ID and shade buffers agree on every pixel (0 mismatches).

## Limitations

These are the limits of what was reviewed, kept explicit as the verdict asks. They are findings, not decisions.

**Warm ramp, art direction** (diagnosis 1). 98.5% of `Main`'s pixels land on the warm ramp's three lightest entries, `b65f33` orange (46.8%), `b99346` gold (21.4%) and `bdbd6a` yellow-olive (30.3%); the dark purple `3b2233` appears on 2 pixels and the red `9e3535` on 1.5%. Those three entries rise from lightness 0.58 to 0.78 at chroma 0.106 to 0.127 and hue 46°, 83° and 109°. The same pixels in style pass 1's studio-lit look were mostly the darker, less saturated olive-brown `6a5822`. It is the ramp's chosen entries and where `Main`'s shades fall, not a mapping fault. The owner reported the orange and yellow as looking infrared.

**Shading direction** (diagnosis 1). Not inverted: the library is darkest first, the mapper sends the lowest shade to the first entry, and the shade is `clamp(0.25·AO_out + 1.0·(1 − AO_in))` (creases dark, flat open surfaces 137, convex and thin parts light); the Blender test that pins crease < flat < convex passed at this commit. Thin and convex parts (arms, legs, rims, feet) are lightest and the large head and torso shells are the middle band, with no directional light (D-22), which can read as lit from below. The owner raised that the shading may be reversed.

**`Grey` and `Black` are clipped above 191 and saturated at 255** (diagnosis 2). From the retained shade buffers (160 frames, supersampled pixels):

| Material | Pixels | Median | 1st percentile | Above 191 (clamped to 191) | Exactly 255 |
|---|---|---|---|---|---|
| Main | 87,737,750 | 150 | 123 | 22.09% | 6.41% |
| Grey | 31,171,736 | 231 | 170 | 80.45% | 23.57% |
| Black | 12,824,333 | 233 | 165 | 81.64% | 45.25% |

Nothing is below 84. `Grey`'s shades spread widely, from 170 to 255 with 118 distinct values, and the fixed range's top, 191, cuts them off, so a top band that begins at 170.4 takes 98.99% of its pixels (99.67% of the sheet's): one colour. `Black` is wholly in its top entry, `5c647d` slate blue, where style pass 1's look was near black. The capture is not bunched near one value: this is lost range, not a constant capture. The ceiling 255 is the formula's clamp at 1.0, reached by many thin parts, so a higher top of range alone would still leave a saturated top.

**Other limits.** One model, one palette and one hand-listed library, judged by the owner at the sizes viewed. The shade range is the default (84..191) and no option sets it. The shade signal is ambient occlusion and convexity only; directional shading belongs to the later lighting arc. The plain and most-common-colour reductions give nearly the same band shares: for every ramp entry they differ by at most about 1.3 percentage points.

## Diagnoses

Two read-only diagnoses followed the feedback. Their full write-ups are local files, outside the repository, and are hashed in the table below.

- **Diagnosis 1** (`material-review-b1627f2/diagnosis-1.md`, from the existing outputs, the merged code, the library and style pass 1's aligned sheet): infrared orange, a ramp and art-direction matter and not a mapping fault; shading, not inverted; flat `Grey`, band occupancy with the raw shades unknown, as the buffers had been deleted.
- **Diagnosis 2** (`material-review-b1627f2-diag/diagnosis-2.md`, from the diagnostic run's retained buffers): lost range, the numbers above, with the same shades computed under other global ranges (not applied).

| File | Bytes | SHA-256 |
|---|---|---|
| `material-review/phase-a-proposal.md` | 4,446 | `4dbddc5130721948720cb61bccbed6390f5f8a7fe685b6a90e45772b9bdeb022` |
| `material-review-b1627f2/MANIFEST.md` | 6,112 | `7c9dc437a5ac702e9e1cef36af1578b2580a384fc8ca90442df856a3815818ba` |
| `material-review-b1627f2/owner-feedback-1.md` | 1,673 | `fba21f752012365d6ea467622ba798ab8abcd8d583ab1f206b03a5e113186b65` |
| `material-review-b1627f2/diagnosis-1.md` | 12,032 | `0f84ccafa0ff36470b617feec144393143077914255edee2c610f6b5cea25260` |
| `material-review-b1627f2/diagnosis-1-analysis.txt` | 6,509 | `510aaa2c9dda9fd3956a57d07cc85734c7ba758dcce91b259e6b4815d5713be6` |
| `material-review-b1627f2-diag/diagnosis-2.md` | 11,154 | `ee949d18ea8701af13fb89f64bd8c947902012c0438cbfc87012bb179e5e5fbe` |
| `material-review-b1627f2-diag/diagnosis-2-analysis.txt` | 4,159 | `d6d01b8d916ed9510895c85feed74428eb36c9c397995b73d22d283d1f55dfbf` |
| `material-review-b1627f2-diag/work-manifest.txt` | 51,764 | `e5dbb14caa804764de215bb0c6911e6b0654288b44c159b3e6809d7ae2b6098c` |
| `material-review-b1627f2-diag/shade-histograms.npz` | 9,194 | `36db4bc394dfa6b0210524a51d3184c4b5264487743a91222e0ce3fad1c4f42e` |
| `material-review-b1627f2-diag/shade-histograms.png` | 24,376 | `8c25a921e4bb2d6b83f83bd0666bed72e4f0e33859dfa02916c7cb95370ae3d6` |
| `material-review-b1627f2-diag/shade-preview.png` | 116,014 | `22574e5720b827d21330e4cbca7ec611280ebb4db7999af963c91872fe2f53c9` |

## Follow-up notes

**Recorded notes only.** The owner's relay says further shading tweaks are recorded follow-up only: none of these is an issue, an implementation, a test, a render or a decision, and none is MAT-8. They are options, with no ranking, as diagnoses 1 and 2 set them out.

1. **Warm ramp alternatives** (a library change; needs a new sign-off and render): keep it; a shorter hue swing from existing Vince128 entries, for example `[3, 4, 5]` (red, orange, gold, hues 24° to 83°) or `[2, 3, 4, 5]`; or a darker, lower-chroma top, for example `[18, 4, 5]`. Generated ramps are MAT-8.
2. **Raise the default shade range's top to 255** (`backend.DEFAULT_SHADE_RANGE` from `(84, 191)` to `(84, 255)`, with the design's spike table and the test assertions that pin `(84, 191)`): `Grey` would spread over three colours (15.8 / 25.2 / 59.0 per cent over its bands) and `Black` over two, but `Main`'s flat-surface mass would move from the orange band to the red one (`Main` 0.5 / 54.7 / 20.9 / 12.6 / 11.3 per cent), because the range is global. Sheets already written keep their recorded range.
3. **A `--shade-range` option**, which MAT-6 left out of the first arc.
4. **A shade technique that saturates less**, for example a lower convexity weight: MAT-3's design and code.
5. **A per-material range**: a new design decision, since the design has one global range (D-7).
6. **Directional shading** is the later lighting-sheet arc (D-1, D-4).

## Disclosures

- **Log truncation and repair.** The saved plain command line ends with `> material-review-b1627f2/logs/plain.log 2>&1`. The diagnostic runner kept that text and appended its own redirect, so the shell opened the first run's `plain.log` for writing and truncated it to 0 bytes; the diagnostic run's own report went to its own log as intended. The first run's log held only the `time -l` report, which had been printed in full earlier in the session. It was rebuilt from that, and accepted only because the 777-byte result has the exact SHA-256 `a66d9b70163e266a0946a84a943f7aaf3201bc0fadbc4472a51b3642894beb01` recorded in `MANIFEST.md` and in the post that reported the renders. It is restored byte for byte, with a later modification time. Nothing else was touched; the first run's sheets, JSON and previews are unchanged, as their hashes in the diagnostic comparison show.
- **A premature start post.** Before the first plain render, a status post announced it as starting while the runner had aborted on a line-count check and nothing had run; a correction followed, and the render's actual start is the one in the `.run` file.
- No code was changed, no model, palette or library was modified, and nothing generated is committed. The only repository change is this file.

## Completion

This record holds the owner's verdict (qualified acceptance of the proof of concept, 2026-10-08 23:00 UTC). It is not unqualified visual acceptance and not approval of the shading as polished; the shading tweaks are recorded above as follow-up notes, with no issue filed. It is not the closure of epic #63 and not authority for MAT-8. Whether this verdict meets #70's completion criterion ("the published record holds the owner's verdict") and whether the epic stays open is for the owner to say; #70 and #63 were open when this was written.
