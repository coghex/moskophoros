# Shading visual acceptance

This records the owner's visual review of the shading arc (epic #137), slice SHD-7 (#144), under vision V-12. The arc's code slices are #138 to #143; the design is [`docs/designs/shading_design.md`](../designs/shading_design.md).

**Status: pending.** The review evidence is prepared and the owner has not yet given a verdict. Nothing below is an owner judgement, and no owner file has been changed. The owner's first answers (see [Round 2](#round-2-the-shrub) and [Round 3](#round-3-the-shrubs-leaf-ramp) and [Round 4](#round-4-the-six-live-lit-looks-on-the-shrub-with-l1-leaves)) asked for the live-lit shrub to be revised and rounds 2 to 4 followed, so no look or use is accepted yet. This record is completed when the owner's verdict and the exact-diff handoff are recorded.

## Verdict

No verdict has been given. The owner was shown the decision page (see [Decision page](#decision-page)); their answers, with date, origin and relay id, are recorded here when they arrive, bound to the evidence and diffs below.

## Earlier owner decisions

Kept apart from the verdict. Design approvals D-1 to D-42 settle the contracts and the two uses; **none of them is a product verdict**, and the design deliberately left the project look values (sky strength, dithering, ramp choices, tuning) for this review (D-31). D-38 settles how an accepted look reaches the owner's files: the verdict authorises the SHD-8 agent (#145) to apply exactly the accepted diffs, and a changed source file or an extra edit returns to the owner. D-42: the owner has no working sheets, so #145 has nothing to regenerate.

## Input

All are review inputs, never defaults or fixtures (V-1). Copies are under `$REVIEW/inputs/`, where `REVIEW=~/.local/share/moskophoros-acceptance/shading-review/v1`. Hashes were taken at the start, at the end, and match #144's.

| Input | SHA-256 | Bytes |
|---|---|---|
| `robotexpressive/RobotExpressive.glb`, motion | `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319` | 463,988 |
| `cutout-model/v1/shrub.glb`, cutouts | `7a1a29382888c8c21a0b19c9418fdbcc5417e8ac038c9d626770ca6f4f0b684f` | 143,624 |
| `alpha-model/v5/chest.glb`, translucency | `04932ad4c77d1348d6d123fa4fda8924edbfa338e7c25a8de814b7200ed3a72c` | 58,300 |
| chest library (the alpha review's `review-library.yaml`, `moskophoros.materials/3`) | `251d2f81537873d4ad88ef8dcf30638c611562719465aa2edf576fb7cbf63d24` | 531 |
| shrub library (the cutout review's `review-library.yaml`, `/3`) | `3a3173b5cd35e7e3a6bb7e247ee83c45f87e1a74da9c1ea5370b0b877dc13da5` | 628 |
| longer-ramp library for the robot (`/3`, review-only, written for this review) | `2de74a2b671b5f6796ce45b56988f4b343ea5d3fbc1dc05d43340c0e64ce7234` | 771 |
| chest library with Glow set to `neither` (`/4`, review-only, written for this review) | `6ccfa6acb4e7d275cf646a799d985ea1d79a578625d6cf888d85816798722c36` | 658 |

The owner's files, copied once to `$REVIEW/inputs/owner-snapshot/` and rehashed at the end of the review (see [Owner files](#owner-files-and-the-handoff)). The copy omits the symlink `palettes/vince-144.gpl` (to `synarchy.gpl`) and keeps nothing else out.

## Environment

- **Review tool:** master `354a21fe316595bee6f13c2455849162f6bb421f` (#143 merged as `c577422`, its narrative amendments `354a21f`), a clean `git archive` copy at `$REVIEW/tool/`, moskophoros 0.1.0, with a virtual environment from its `requirements.lock` (SHA-256 `86f3d9a7b64c1882b5825bc3b8157dcc3d37d4d6eb04731659391520e1a3de43`).
- **Baseline:** `shading-pre-arc`, source `f548312a5a929fb9bd843855b83b9762123f80ab`, unchanged ([`shading-pre-arc-baseline.md`](shading-pre-arc-baseline.md)). Used here only for the default-look byte comparison below.
- **Libraries:** Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0, PyYAML 6.0.3, on macOS 26.7.1 (arm64). **Blender:** 5.2.2 LTS (build 2026-09-15), `/opt/homebrew/bin/blender`, headless (`-b --factory-startup -noaudio`, run by the tool), one run at a time under `~/.local/state/project-manager/moskophoros/blender.lock`.
- **Colour:** `cycles-flat-emission`, 1 sample per pixel, seed 0, BOX filter 0.01 px, 64 transparent bounces; **shade:** `cycles-ambient-occlusion`, 1 sample, seed 0; supersample 8, as every sheet's `generator` records.
- **Configuration:** each run sets `XDG_CONFIG_HOME` to a candidate tree under `$REVIEW/candidates/<id>/`, so `--project` and the global file resolve inside the evidence copy; `~/.config/moskophoros` was not read by any run and was never written.
- **The mechanical evidence behind the tool** is #143's, in [`shading-pre-arc-baseline.md`](shading-pre-arc-baseline.md) (planned checks passed at its head, 171 non-JSON files byte-identical to the baseline). This review ran no repository test suite.

## Candidate settings and the proposed project-file changes

Every run uses a candidate configuration tree: a copy of the owner's files, with `projects/synarchy.yaml` changed only where a candidate says so (live-lit, use A) or a new review-only `projects/baked-panel.yaml` (baked panels, use B). The relative palette path `../palettes/synarchy.gpl` is unchanged, so each tree's palette is a byte-identical copy of the owner's and every sheet records the palette as `synarchy.gpl`, SHA-256 `073695cb…938c`. A sheet records its model, palette and library by file name and SHA-256, never by path, so the copied paths change nothing a sheet records; the only absolute paths are those in the commands below.

| Candidate | `projects/synarchy.yaml` SHA-256 | Diff SHA-256 |
|---|---|---|
| `live-0` | `e634338df4acbd1533402b1699be5cdae33563586d089df578c1796c7ed1a5ad` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `live-sky20` | `655fbe4721baa2ee6b6038d5efb918bfb1b52628c47df288d36bab1f7c2a9de6` | `e208fba1224a204e06dbdb897adf397ebc53fe51534e12b7fe6b1f92ce48474d` |
| `live-sky40` | `8684e47aff7c215c1b55f5a06ef215476f0d1c64b5426c911106df9f6c85e2bf` | `26a95a4c89c2a989210af19f2f1e2a78efd223db632b36425b030a351fc722df` |
| `live-skyw30` | `349b3ba41998cadd6bdd85f198c29e1629d84c16e12cb3ffa63fe60df1e4b476` | `981b2b9a080eecc89543eaef35f86de978b62b759ca6ef624e0a61ba404e9337` |
| `live-dith4` | `ae0f9eb050900b8a53ae00f76a97dbb937d95fcdc1b052f4586ce3901df96b6a` | `fb0db3f17d05f1d0f407d33fa3d0ce5f405f395be86815d6a1e9378f312074ba` |
| `live-sky20-dith4` | `5a4a2929f5fabd1915f45749bb08864240feabd450d8798d8ad12e3782ea4e3b` | `88f41ab4553414f23aa04dbb9fa5490d7739ad8bd46d78445d1d355f4e5b9775` |

The exact diffs, each applied to the owner's current file (SHA-256 `e634338df4acbd1533402b1699be5cdae33563586d089df578c1796c7ed1a5ad`), and verified by `helpers/verify_diffs.sh`: every patched copy equals its candidate file byte for byte.

### `live-0`

```diff
(no change: the owner's current file)
```

### `live-sky20`

```diff
--- a/projects/synarchy.yaml
+++ b/projects/synarchy.yaml
@@ -35,6 +35,7 @@
   occlusion_weight: 0.5
   convexity_weight: 0.25
   range: [190, 225]
+  sky: {strength: 0.2}
 
 # Generated-ramp formula: setting C, chosen 2026-10-14 for Synarchy's
 # high-contrast look. The everyday default is setting B (shipped).
```

### `live-sky40`

```diff
--- a/projects/synarchy.yaml
+++ b/projects/synarchy.yaml
@@ -35,6 +35,7 @@
   occlusion_weight: 0.5
   convexity_weight: 0.25
   range: [190, 225]
+  sky: {strength: 0.4}
 
 # Generated-ramp formula: setting C, chosen 2026-10-14 for Synarchy's
 # high-contrast look. The everyday default is setting B (shipped).
```

### `live-skyw30`

```diff
--- a/projects/synarchy.yaml
+++ b/projects/synarchy.yaml
@@ -35,6 +35,8 @@
   occlusion_weight: 0.5
   convexity_weight: 0.25
   range: [190, 225]
+  sky: {strength: 0.3}
+  sky_ground_frame: world
 
 # Generated-ramp formula: setting C, chosen 2026-10-14 for Synarchy's
 # high-contrast look. The everyday default is setting B (shipped).
```

### `live-dith4`

```diff
--- a/projects/synarchy.yaml
+++ b/projects/synarchy.yaml
@@ -35,6 +35,7 @@
   occlusion_weight: 0.5
   convexity_weight: 0.25
   range: [190, 225]
+  dither: {pattern: ordered4, strength: 1}
 
 # Generated-ramp formula: setting C, chosen 2026-10-14 for Synarchy's
 # high-contrast look. The everyday default is setting B (shipped).
```

### `live-sky20-dith4`

```diff
--- a/projects/synarchy.yaml
+++ b/projects/synarchy.yaml
@@ -35,6 +35,8 @@
   occlusion_weight: 0.5
   convexity_weight: 0.25
   range: [190, 225]
+  sky: {strength: 0.2}
+  dither: {pattern: ordered4, strength: 1}
 
 # Generated-ramp formula: setting C, chosen 2026-10-14 for Synarchy's
 # high-contrast look. The everyday default is setting B (shipped).
```

The baked-panel candidate `panel-base` has no owner counterpart (no such project exists); its file is `$REVIEW/candidates/panel-base/moskophoros/projects/baked-panel.yaml`, SHA-256 `e8fa88dc37c4bd8d5ca8bfc0502dc62e8dd2b3583f026460326d96a2cf295b37`. The bake settings of each panel run are command-line options, shown in the commands.

## Commands

Run from `$REVIEW` one at a time by `helpers/run_case.py <case>` (SHA-256 `5adec96a7ad67ce5d5f669974fbccf4ee8436740aa0f3524bf05e845ec4fefe1`), each as `XDG_CONFIG_HOME=$REVIEW/candidates/<candidate> /usr/bin/lockf -k <blender.lock> <command>`. Each run's literal command is `runs/<case>/command.txt` and its output `run.log`. Literally, with `$LOCK=~/.local/state/project-manager/moskophoros/blender.lock`, `$TOOL=$REVIEW/tool/.venv/bin/moskophoros` and `$M=$REVIEW/inputs/models`:

```sh
# PB-robot-ramp-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.35 --bake-sky-strength 0.15 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-soft/robot.png
# PB-robot-ramp-strong
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-strong/robot.png
# PB-robot-ramp-strong-lit
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --light -53.333,106.667,80 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-strong-lit/robot.png
# PB-robot-ramp-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern ordered4 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-ordered4/robot.png
# PB-robot-ramp-clustered4-s06
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern clustered4 --dither-strength 0.6 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-clustered4-s06/robot.png
# PB-robot-ramp-shuffled8
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern shuffled8 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-shuffled8/robot.png
# PB-robot-ramp-mode-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern ordered4 --reduce mode --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-mode-ordered4/robot.png
# PB-robot-brightness
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode brightness --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-brightness/robot.png
# PB-robot-brightness-snap-palette-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode brightness --shade-snap palette --dither-pattern ordered4 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-brightness-snap-palette-ordered4/robot.png
# PB-robot-both
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode both --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-both/robot.png
# PB-robot-both-snap-ramp-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode both --shade-snap ramp --dither-pattern ordered4 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-both-snap-ramp-ordered4/robot.png
# PB-robot-neither
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode neither --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-neither/robot.png
# PB-robot-roll-world-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --camera-roll 0.0625 --bake-key-strength 0.5 --bake-sky-strength 0.3 --dither-pattern ordered4 --bake-sky-ground-frame world --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-roll-world-ordered4/robot.png
# PB-robot-roll-camera-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --camera-roll 0.0625 --bake-key-strength 0.5 --bake-sky-strength 0.3 --dither-pattern ordered4 --bake-sky-ground-frame camera --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-roll-camera-ordered4/robot.png
# PB-robot-long-ramp
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/long-ramps-robot.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --ramp-step 0.05 --ramp-hue-shift -20 --ramp-fade 0.3 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-long-ramp/robot.png
# PB-robot-long-ramp-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/long-ramps-robot.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --ramp-step 0.05 --ramp-hue-shift -20 --ramp-fade 0.3 --dither-pattern ordered4 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-long-ramp-ordered4/robot.png
# PB-robot-long-brightness-snap-ramp-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/long-ramps-robot.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --ramp-step 0.05 --ramp-hue-shift -20 --ramp-fade 0.3 --shade-mode brightness --shade-snap ramp --dither-pattern ordered4 --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-long-brightness-snap-ramp-ordered4/robot.png
# PB-robot-ramp-ordered4-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern ordered4 --edges soft --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-ramp-ordered4-soft/robot.png
# PB-shrub-ramp-strong
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --view side --directions 1 --start-angle 0 --cell 96x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/PB-shrub-ramp-strong/shrub.png
# PB-shrub-ramp-mode-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --view side --directions 1 --start-angle 0 --cell 96x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern ordered4 --reduce mode --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/PB-shrub-ramp-mode-ordered4/shrub.png
# PB-shrub-ramp-ordered4-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --view side --directions 1 --start-angle 0 --cell 96x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern ordered4 --edges soft --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/PB-shrub-ramp-ordered4-soft/shrub.png
# PB-shrub-brightness-snap-palette-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --view side --directions 1 --start-angle 0 --cell 96x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode brightness --shade-snap palette --dither-pattern ordered4 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/PB-shrub-brightness-snap-palette-ordered4/shrub.png
# PB-shrub-both
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --view side --directions 1 --start-angle 0 --cell 96x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode both --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/PB-shrub-both/shrub.png
# PB-shrub-neither
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --view side --directions 1 --start-angle 0 --cell 96x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode neither --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/PB-shrub-neither/shrub.png
# PB-chest-ramp-strong-hard
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/chest-review-library.yaml --clip Open --once Open --view side --directions 1 --start-angle 0 --cell 128x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/PB-chest-ramp-strong-hard/chest.png
# PB-chest-ramp-ordered4-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/chest-review-library.yaml --clip Open --once Open --view side --directions 1 --start-angle 0 --cell 128x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern ordered4 --edges soft --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/PB-chest-ramp-ordered4-soft/chest.png
# PB-chest-brightness-snap-ramp-ordered4-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/chest-review-library.yaml --clip Open --once Open --view side --directions 1 --start-angle 0 --cell 128x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode brightness --shade-snap ramp --dither-pattern ordered4 --edges soft --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/PB-chest-brightness-snap-ramp-ordered4-soft/chest.png
# PB-chest-both-snap-palette-ordered4-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/chest-review-library.yaml --clip Open --once Open --view side --directions 1 --start-angle 0 --cell 128x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode both --shade-snap palette --dither-pattern ordered4 --edges soft --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/PB-chest-both-snap-palette-ordered4-soft/chest.png
# PB-chest-glow-neither-ramp-ordered4-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/chest-glow-override-library.yaml --clip Open --once Open --view side --directions 1 --start-angle 0 --cell 128x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --dither-pattern ordered4 --edges soft --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/PB-chest-glow-neither-ramp-ordered4-soft/chest.png
# PB-chest-neither-soft
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/chest-review-library.yaml --clip Open --once Open --view side --directions 1 --start-angle 0 --cell 128x128 --bake-key-strength 0.6 --bake-sky-strength 0.2 --bake-ground-strength 0.1 --shade-mode neither --edges soft --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/PB-chest-neither-soft/chest.png
# A-live-0-shrub
XDG_CONFIG_HOME=$REVIEW/candidates/live-0 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-0/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/A-live-0-shrub/shrub.png
# A-live-0-robot
XDG_CONFIG_HOME=$REVIEW/candidates/live-0 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-0/moskophoros/libraries/robotexpressive.yaml --clip Walking --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/A-live-0-robot/robot.png
# A-live-sky20-shrub
XDG_CONFIG_HOME=$REVIEW/candidates/live-sky20 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-sky20/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/A-live-sky20-shrub/shrub.png
# A-live-sky20-robot
XDG_CONFIG_HOME=$REVIEW/candidates/live-sky20 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-sky20/moskophoros/libraries/robotexpressive.yaml --clip Walking --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/A-live-sky20-robot/robot.png
# A-live-sky40-shrub
XDG_CONFIG_HOME=$REVIEW/candidates/live-sky40 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-sky40/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/A-live-sky40-shrub/shrub.png
# A-live-sky40-robot
XDG_CONFIG_HOME=$REVIEW/candidates/live-sky40 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-sky40/moskophoros/libraries/robotexpressive.yaml --clip Walking --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/A-live-sky40-robot/robot.png
# A-live-skyw30-shrub
XDG_CONFIG_HOME=$REVIEW/candidates/live-skyw30 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-skyw30/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/A-live-skyw30-shrub/shrub.png
# A-live-skyw30-robot
XDG_CONFIG_HOME=$REVIEW/candidates/live-skyw30 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-skyw30/moskophoros/libraries/robotexpressive.yaml --clip Walking --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/A-live-skyw30-robot/robot.png
# A-live-dith4-shrub
XDG_CONFIG_HOME=$REVIEW/candidates/live-dith4 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-dith4/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/A-live-dith4-shrub/shrub.png
# A-live-dith4-robot
XDG_CONFIG_HOME=$REVIEW/candidates/live-dith4 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-dith4/moskophoros/libraries/robotexpressive.yaml --clip Walking --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/A-live-dith4-robot/robot.png
# A-live-sky20-dith4-shrub
XDG_CONFIG_HOME=$REVIEW/candidates/live-sky20-dith4 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-sky20-dith4/moskophoros/libraries/shrub-review-library.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $M/shrub.glb $REVIEW/runs/A-live-sky20-dith4-shrub/shrub.png
# A-live-sky20-dith4-robot
XDG_CONFIG_HOME=$REVIEW/candidates/live-sky20-dith4 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-sky20-dith4/moskophoros/libraries/robotexpressive.yaml --clip Walking --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/A-live-sky20-dith4-robot/robot.png
# A-live-0-chest
XDG_CONFIG_HOME=$REVIEW/candidates/live-0 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-0/moskophoros/libraries/chest-review-library.yaml --clip Open --once Open --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/A-live-0-chest/chest.png
# A-live-sky20-dith4-chest
XDG_CONFIG_HOME=$REVIEW/candidates/live-sky20-dith4 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW/candidates/live-sky20-dith4/moskophoros/libraries/chest-review-library.yaml --clip Open --once Open --blender /opt/homebrew/bin/blender $M/chest.glb $REVIEW/runs/A-live-sky20-dith4-chest/chest.png
# PB-robot-roll25-camera-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --camera-roll 0.25 --bake-key-strength 0.5 --bake-sky-strength 0.3 --dither-pattern ordered4 --bake-sky-ground-frame camera --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-roll25-camera-ordered4/robot.png
# PB-robot-roll25-world-ordered4
XDG_CONFIG_HOME=$REVIEW/candidates/panel-base /usr/bin/lockf -k $LOCK $TOOL --project baked-panel --materials $REVIEW/candidates/panel-base/moskophoros/libraries/robotexpressive.yaml --clip Walking --view side --directions 1 --start-angle 0 --cell 128x192 --projection perspective --camera-position 0,2.4,7 --camera-roll 0.25 --bake-key-strength 0.5 --bake-sky-strength 0.3 --dither-pattern ordered4 --bake-sky-ground-frame world --blender /opt/homebrew/bin/blender $M/RobotExpressive.glb $REVIEW/runs/PB-robot-roll25-world-ordered4/robot.png
```

Every run exited 0. The default look was also run with the pinned pre-arc tool (`helpers/pre-arc-moskophoros`, the manifest's `baseline-src/src` at `f548312…`, verified identical to that commit's `src`), the same three commands with `--pre-arc`: `python3 helpers/run_case.py --pre-arc A-live-0-shrub A-live-0-robot A-live-0-chest`.

## Review matrix

**Use A, live-lit:** the owner's Synarchy project (iso, 8 directions, 128×128, hard edges, palette, normal and depth maps, preview light), six candidates, robot (Walking, 11 frames), shrub (Sway, `--frames 8`) and, for two candidates, the chest (Open). Mode is `ramp` in all six, so the sprite's colour is flat ambient ramp shading; the maps are geometry. **Use B, baked panels:** straight-on (`--view side --directions 1`), robot through a perspective camera (`--camera-position 0,2.4,7`), shrub and chest orthographic. Columns are the settings each run's sheet records: mode · key/sky/ground strengths and the sky frame · dithering · snap · reduce · edges · camera.

| Run | Mode | Key/sky/ground | Dither | Snap | Reduce | Edges | Camera |
|---|---|---|---|---|---|---|---|
| `PB-robot-ramp-soft` | ramp | 0.35/0.15/0 camera | off | off | plain | hard | perspective, roll 0 |
| `PB-robot-ramp-strong` | ramp | 0.6/0.2/0.1 camera | off | off | plain | hard | perspective, roll 0 |
| `PB-robot-ramp-strong-lit` | ramp | 0.6/0.2/0.1 camera | off | off | plain | hard | perspective, roll 0 |
| `PB-robot-ramp-ordered4` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | plain | hard | perspective, roll 0 |
| `PB-robot-ramp-clustered4-s06` | ramp | 0.6/0.2/0.1 camera | clustered4 x0.6 | off | plain | hard | perspective, roll 0 |
| `PB-robot-ramp-shuffled8` | ramp | 0.6/0.2/0.1 camera | shuffled8 x1 | off | plain | hard | perspective, roll 0 |
| `PB-robot-ramp-mode-ordered4` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | mode | hard | perspective, roll 0 |
| `PB-robot-brightness` | brightness | 0.6/0.2/0.1 camera | off | off | plain | hard | perspective, roll 0 |
| `PB-robot-brightness-snap-palette-ordered4` | brightness | 0.6/0.2/0.1 camera | ordered4 x1 | palette | plain | hard | perspective, roll 0 |
| `PB-robot-both` | both | 0.6/0.2/0.1 camera | off | off | plain | hard | perspective, roll 0 |
| `PB-robot-both-snap-ramp-ordered4` | both | 0.6/0.2/0.1 camera | ordered4 x1 | ramp | plain | hard | perspective, roll 0 |
| `PB-robot-neither` | neither | 0.6/0.2/0.1 camera | off | off | plain | hard | perspective, roll 0 |
| `PB-robot-roll-world-ordered4` | ramp | 0.5/0.3/0 world | ordered4 x1 | off | plain | hard | perspective, roll 0.0625 |
| `PB-robot-roll-camera-ordered4` | ramp | 0.5/0.3/0 camera | ordered4 x1 | off | plain | hard | perspective, roll 0.0625 |
| `PB-robot-long-ramp` | ramp | 0.6/0.2/0.1 camera | off | off | plain | hard | perspective, roll 0 |
| `PB-robot-long-ramp-ordered4` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | plain | hard | perspective, roll 0 |
| `PB-robot-long-brightness-snap-ramp-ordered4` | brightness | 0.6/0.2/0.1 camera | ordered4 x1 | ramp | plain | hard | perspective, roll 0 |
| `PB-robot-ramp-ordered4-soft` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | plain | soft | perspective, roll 0 |
| `PB-shrub-ramp-strong` | ramp | 0.6/0.2/0.1 camera | off | off | plain | hard | orthographic, roll 0 |
| `PB-shrub-ramp-mode-ordered4` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | mode | hard | orthographic, roll 0 |
| `PB-shrub-ramp-ordered4-soft` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | plain | soft | orthographic, roll 0 |
| `PB-shrub-brightness-snap-palette-ordered4` | brightness | 0.6/0.2/0.1 camera | ordered4 x1 | palette | plain | hard | orthographic, roll 0 |
| `PB-shrub-both` | both | 0.6/0.2/0.1 camera | off | off | plain | hard | orthographic, roll 0 |
| `PB-shrub-neither` | neither | 0.6/0.2/0.1 camera | off | off | plain | hard | orthographic, roll 0 |
| `PB-chest-ramp-strong-hard` | ramp | 0.6/0.2/0.1 camera | off | off | plain | hard | orthographic, roll 0 |
| `PB-chest-ramp-ordered4-soft` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | plain | soft | orthographic, roll 0 |
| `PB-chest-brightness-snap-ramp-ordered4-soft` | brightness | 0.6/0.2/0.1 camera | ordered4 x1 | ramp | plain | soft | orthographic, roll 0 |
| `PB-chest-both-snap-palette-ordered4-soft` | both | 0.6/0.2/0.1 camera | ordered4 x1 | palette | plain | soft | orthographic, roll 0 |
| `PB-chest-glow-neither-ramp-ordered4-soft` | ramp | 0.6/0.2/0.1 camera | ordered4 x1 | off | plain | soft | orthographic, roll 0 |
| `PB-chest-neither-soft` | neither | 0.6/0.2/0.1 camera | off | off | plain | soft | orthographic, roll 0 |
| `A-live-0-shrub` | ramp | 0/0/0 - | off | off | plain | hard | orthographic, roll 0 |
| `A-live-0-robot` | ramp | 0/0/0 - | off | off | plain | hard | orthographic, roll 0 |
| `A-live-sky20-shrub` | ramp | 0/0.2/0 camera | off | off | plain | hard | orthographic, roll 0 |
| `A-live-sky20-robot` | ramp | 0/0.2/0 camera | off | off | plain | hard | orthographic, roll 0 |
| `A-live-sky40-shrub` | ramp | 0/0.4/0 camera | off | off | plain | hard | orthographic, roll 0 |
| `A-live-sky40-robot` | ramp | 0/0.4/0 camera | off | off | plain | hard | orthographic, roll 0 |
| `A-live-skyw30-shrub` | ramp | 0/0.3/0 world | off | off | plain | hard | orthographic, roll 0 |
| `A-live-skyw30-robot` | ramp | 0/0.3/0 world | off | off | plain | hard | orthographic, roll 0 |
| `A-live-dith4-shrub` | ramp | 0/0/0 - | ordered4 x1 | off | plain | hard | orthographic, roll 0 |
| `A-live-dith4-robot` | ramp | 0/0/0 - | ordered4 x1 | off | plain | hard | orthographic, roll 0 |
| `A-live-sky20-dith4-shrub` | ramp | 0/0.2/0 camera | ordered4 x1 | off | plain | hard | orthographic, roll 0 |
| `A-live-sky20-dith4-robot` | ramp | 0/0.2/0 camera | ordered4 x1 | off | plain | hard | orthographic, roll 0 |
| `A-live-0-chest` | ramp | 0/0/0 - | off | off | plain | hard | orthographic, roll 0 |
| `A-live-sky20-dith4-chest` | ramp | 0/0.2/0 camera | ordered4 x1 | off | plain | hard | orthographic, roll 0 |
| `PB-robot-roll25-camera-ordered4` | ramp | 0.5/0.3/0 camera | ordered4 x1 | off | plain | hard | perspective, roll 0.25 |
| `PB-robot-roll25-world-ordered4` | ramp | 0.5/0.3/0 world | ordered4 x1 | off | plain | hard | perspective, roll 0.25 |

### Coverage

| Obligation | Use | Runs |
|---|---|---|
| Robot motion | live-lit | `A-live-*-robot` (six candidates, Walking) |
| Robot motion | baked | `PB-robot-*` (Walking, 11 frames) |
| Shrub cutouts | live-lit | `A-live-*-shrub` |
| Shrub cutouts | baked | `PB-shrub-*`, hard and soft |
| Chest translucency | live-lit | `A-live-0-chest`, `A-live-sky20-dith4-chest` |
| Chest translucency | baked | `PB-chest-*`, separate layer shading, mixed-layer snap, Glow override |
| Mode `ramp` | both | `A-*`, `PB-robot-ramp-*`, `PB-shrub-ramp-*`, `PB-chest-ramp-*` |
| Mode `brightness` | baked | `PB-robot-brightness`, `PB-robot-brightness-snap-palette-ordered4`, `PB-shrub-brightness-snap-palette-ordered4`, `PB-chest-brightness-snap-ramp-ordered4-soft`, `PB-robot-long-brightness-snap-ramp-ordered4` |
| Mode `both` | baked | `PB-robot-both`, `PB-robot-both-snap-ramp-ordered4`, `PB-shrub-both`, `PB-chest-both-snap-palette-ordered4-soft` |
| Mode `neither` | baked | `PB-robot-neither`, `PB-shrub-neither`, `PB-chest-neither-soft`; per material: `PB-chest-glow-neither-ramp-ordered4-soft` |
| Dither patterns | both | ordered4 (`A-live-dith4-*`, `PB-*-ordered4*`), clustered4 at 0.6 (`PB-robot-ramp-clustered4-s06`), shuffled8 (`PB-robot-ramp-shuffled8`) |
| Snap targets | baked | ramp: `PB-robot-both-snap-ramp-ordered4`, `PB-robot-long-brightness-snap-ramp-ordered4`, `PB-chest-brightness-snap-ramp-ordered4-soft`; palette: `PB-robot-brightness-snap-palette-ordered4`, `PB-shrub-brightness-snap-palette-ordered4`, `PB-chest-both-snap-palette-ordered4-soft` |
| Camera and world sky | both | world: `A-live-skyw30-*`, `PB-robot-roll-world-ordered4`, `PB-robot-roll25-world-ordered4`; camera: all others with sky, `PB-robot-roll-camera-ordered4`, `PB-robot-roll25-camera-ordered4` |
| Perspective and roll | baked | every `PB-robot-*` is perspective; roll 0.0625 and 0.25: `PB-robot-roll-*`, `PB-robot-roll25-*` |
| Longer generic ramp | baked | `PB-robot-long-ramp`, `PB-robot-long-ramp-ordered4`, `PB-robot-long-brightness-snap-ramp-ordered4` (16-entry grey, 12- and 8-band generated ramps) |
| **Mandatory:** `reduce: mode` with light and ramp dithering, in motion | baked | `PB-robot-ramp-mode-ordered4` (Walking), `PB-shrub-ramp-mode-ordered4` (Sway) |
| **Mandatory:** a soft-edge case | baked | `PB-robot-ramp-ordered4-soft`, `PB-shrub-ramp-ordered4-soft`, every `PB-chest-*-soft` |
| **Mandatory:** a dithered perspective and roll animation | baked | `PB-robot-roll-camera-ordered4`, `PB-robot-roll-world-ordered4`, `PB-robot-roll25-camera-ordered4`, `PB-robot-roll25-world-ordered4` |
| Regular colour previews and the additional point-lit previews | both | every run writes `<stem>.<clip>.gif`; the live-lit runs and `PB-robot-ramp-strong-lit` also write `<stem>-lit.<clip>.gif` from `light` / `--light` |
| Unaltered exported sheets and maps | both | `runs/<case>/<stem>.png`, `.normal.png`, `.depth.png` (live-lit) and the GIFs are the tool's output; the decision page's images are enlargements of them |

## Mechanical checks (measured, not visual)

`helpers/check.py` (SHA-256 `f5a455e1b771e18b5eac2b0a0a2f14969e09f0d929c5168fcdd73d82f15fb807`) reads every run's files; its full output is `$REVIEW/checks.txt` (SHA-256 `dc6b0bb8bd4a0fb8688409b76b6da3b399effbb206550c76ce803b8d37810f6e`). It found, for all runs: exit 0; sheet schema `moskophoros.sheet/15`; every recorded shading setting equal to its command-line value; a preview GIF with the clip's frame count; and, between runs that share a camera, cell, clip and edge rule, **equal alpha and byte-identical normal maps**, so shading changed neither coverage nor geometry. Palette membership of every visible pixel: all `ramp`, `neither` and every snapped run stay inside the palette, except where translucent layers mix under `brightness` with ramp snap (`PB-chest-brightness-snap-ramp-ordered4-soft`, as D-18 expects); unsnapped `brightness` and `both` leave the palette (as D-18 expects).

**The default look against the pinned pre-arc tool** (`helpers/compare_prearc.py`, output `compare-prearc.txt`, SHA-256 `cb986168587a43bd26e4e31222fe58fd8cf34eed56870e85fb551317f00d2e8f`): candidate `live-0` is the owner's project file verbatim.

```text
A-live-0-shrub/shrub-lit.Sway.gif: byte-identical  8004654971786e620c50ef7a7f25334ffeeac323dff9c6efeb60ac3a3991dab1
A-live-0-shrub/shrub.Sway.gif: byte-identical  9d03ab5211feee01352d8182d8b303b9a1a8be7e208fe6bce63b14464f62f452
A-live-0-shrub/shrub.depth.png: byte-identical  a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9
A-live-0-shrub/shrub.json: JSON differs in ['fingerprint', 'schema', 'settings']; settings.shade gains ['mode', 'ambient_form', 'key', 'sky', 'ground', 'sky_ground_frame', 'brightness', 'snap', 'dither']; old shade members changed []; other settings changed []; pre-arc schema moskophoros.sheet/14 -> moskophoros.sheet/15  as expected
A-live-0-shrub/shrub.normal.png: byte-identical  d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5
A-live-0-shrub/shrub.png: byte-identical  6306607f332d49ebd03a6d9c1e6534794fde81899f83df6764e58f4bcd19d537
A-live-0-robot/robot-lit.Walking.gif: byte-identical  089d8b46814818097e0cd2b9e6a07901a758789d928263b92aa3f0388412a06d
A-live-0-robot/robot.Walking.gif: byte-identical  e607e8d9a842b8a4296326f8f7503e41f771094cb10d58cc7e3208d736d4313e
A-live-0-robot/robot.depth.png: byte-identical  76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2
A-live-0-robot/robot.json: JSON differs in ['fingerprint', 'schema', 'settings']; settings.shade gains ['mode', 'ambient_form', 'key', 'sky', 'ground', 'sky_ground_frame', 'brightness', 'snap', 'dither']; old shade members changed []; other settings changed []; pre-arc schema moskophoros.sheet/14 -> moskophoros.sheet/15  as expected
A-live-0-robot/robot.normal.png: byte-identical  8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0
A-live-0-robot/robot.png: byte-identical  d89a5bb27742674e5051bbb8bf81df4834484b2d41f67b8d9c36f4496e5424a8
A-live-0-chest/chest-lit.Open.gif: byte-identical  9cf8f373572303039da43a58b92037bba1ead3cd4b1d793fe5ecdc19fad9554b
A-live-0-chest/chest.Open.gif: byte-identical  a22dc4214e70842c6bd5142c31656512043261778653a953a59719532a73c8d0
A-live-0-chest/chest.depth.png: byte-identical  d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26
A-live-0-chest/chest.json: JSON differs in ['fingerprint', 'schema', 'settings']; settings.shade gains ['mode', 'ambient_form', 'key', 'sky', 'ground', 'sky_ground_frame', 'brightness', 'snap', 'dither']; old shade members changed []; other settings changed []; pre-arc schema moskophoros.sheet/14 -> moskophoros.sheet/15  as expected
A-live-0-chest/chest.normal.png: byte-identical  bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36
A-live-0-chest/chest.png: byte-identical  ed9490c5062b542b915e625cb2498c1160a94cbc1e92de409228c2f5f78a70b4

ALL IMAGE AND PREVIEW BYTES IDENTICAL; JSON DIFFERENCES AS EXPECTED
```

**The proposed diffs** apply to the owner's current file and give the candidate files byte for byte (`helpers/verify_diffs.sh`, output `verify-diffs.txt`, SHA-256 `9076831300b2a0411de069578041513f7737780626c473235debd422ac585057`).

## Owner files and the handoff

The review changed no owner file. The hashes at the start (from `inputs/owner-snapshot/`) and at the end of the review:

| File | At the start | At the end |
|---|---|---|
| `~/.config/moskophoros/config.yaml` | `257304183ca22ced1386e2484e95be75996a8a067b5eba3e9cea171d25a8fd0a` | `257304183ca22ced1386e2484e95be75996a8a067b5eba3e9cea171d25a8fd0a` |
| `~/.config/moskophoros/projects/synarchy.yaml` | `e634338df4acbd1533402b1699be5cdae33563586d089df578c1796c7ed1a5ad` | `e634338df4acbd1533402b1699be5cdae33563586d089df578c1796c7ed1a5ad` |
| `~/.config/moskophoros/synarchy.yaml` | `9195adfe08c7b0866143076d76079a6523c192f8152c764db0ab02805af344f4` | `9195adfe08c7b0866143076d76079a6523c192f8152c764db0ab02805af344f4` |
| `~/.config/moskophoros/libraries/robotexpressive.yaml` | `33ebb76998abc2366d45a4d1c88f8cef82ccc7a9d4401907e4cde66dc27a2162` | `33ebb76998abc2366d45a4d1c88f8cef82ccc7a9d4401907e4cde66dc27a2162` |
| `~/.config/moskophoros/palettes/synarchy.gpl` | `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c` | `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c` |

**Proposed changes, by file** (pending the owner's verdict; nothing applies until then, and #145 applies only the accepted diff):

- `~/.config/moskophoros/projects/synarchy.yaml`: one of the candidate diffs above, chosen by the owner's answer to decision 1. The current hash is the one above; the candidate hashes are in the table.
- `~/.config/moskophoros/config.yaml`: **no change** (version and comments only).
- `~/.config/moskophoros/synarchy.yaml`: **no change** (the older duplicate that the Projects arc kept; not used by `--project`).
- `~/.config/moskophoros/libraries/robotexpressive.yaml`: **no change** (a `/2` library; it keeps its ranges and ramps, and needs no `/4` response field for any candidate).
- `~/.config/moskophoros/palettes/*`: **no change.**
- Baked panels: **no owner file exists and none is proposed.** The owner's choices for this use are recorded as values only; the second game's palette and project file are not authored here.

## Limitations

- The decision's look values are the owner's; the candidates' numbers (sky 0.2/0.3/0.4, key 0.35/0.5/0.6, ground 0.1, patterns and strengths) were chosen as representative points, not as recommendations.
- Brightness and both modes with no snap leave the palette; the preview GIFs (256 colours) approximate those runs, which the PNG sheets carry exactly. The live-lit robot's point-lit preview exceeds 256 colours and the tool says so in `run.log` (reduced without dithering).
- The chest's glow is shaded as a separate layer and combined as the accepted combined front layer; that approximation (D-19) is the tool's, not new.
- A baked panel uses the owner's Synarchy palette because the second game's palette does not exist; the panel candidate is review-only.
- Every library material range [190, 225] is also set in the candidate project files, so the tool prints a shadow warning for the robot library (D-41: a project-file value is shadowed by the library's own); the warnings are in each `run.log` and change nothing.
- No code was changed and no repository test suite was run for this record; #143's evidence stands as the mechanical basis.

## Decision page

The owner was shown `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-review/v1/page/index.html` (SHA-256 `68055804812dc6cbc4a52d63cfacb9377fc9baac4bba191eca0ba6f62ff141d6`), with its images in `$REVIEW/page/img/` and the full index at `$REVIEW/index.html` (SHA-256 `c71354e4cb555c7569337d107ff43e85e89d412a7cbaa6f66b5e7885b1a12d64`), built by `helpers/make_page.py` and `helpers/make_index.py`. The composites are the runs' own pixels enlarged by whole pixels, labelled with the recorded settings.

## Round 2: the shrub

Round 1's evidence (`$REVIEW`, the sections above) is unchanged. This round adds new, separately labelled evidence under `$REVIEW2=~/.local/share/moskophoros-acceptance/shading-review/v2`, after the owner's first answers on section 1 (requirement 6). It is not a verdict: section 1's look, and sections 11 and 12, are still open.

### The owner's answers

Relayed by the moskophoros manager for request `moskophoros-20261020-1` in `~/.local/state/project-manager/moskophoros/relay-144-shrub-1.md` (SHA-256 `45e5ab7f57e8b29746f2040ac05a5075d89559b44567606e92ccb52fb1cf23b6`). The owner typed them directly in the manager's terminal on 2026-10-21 (no time given in the relay):

> "i would liek you to walk me through the approval of all the sprites, these live-lit sprites in 1 all look bad, the branches dont look right, they are disconnected, the leaves are too sparse. many of the other texstures in this doc look good, just help me by asking very specific questions and figure out why these dont look good"

The manager's four questions and the owner's answers, verbatim:

1. Q: The shrub is a test model generated by script for the cutout review. How should we treat it? A: "i approve improving the model, but it looked right before, are these scaled down further than what it was before?" (The manager answered the owner: no, same scale as the cutout review; the difference is the missing trial F.)
2. Q: When you say the leaves are too sparse, what do you see? (Too few/gaps; too dark/one mass; both) A: "Both"
3. Q: For the disconnected branches, what would you expect to see from the high isometric angle? A: "i want to see it at all, but its perhaps because the dark leaves are obscuring things, so fix the leaves first, then we will discuss the trunk"
4. Q: Section 1 also shows the robot and the chest in the live-lit use. Do those look right? A: "not only do the robot and chest look good, but they look great, the best they ever have"

### What round 1 got wrong

Round 1's shrub runs (`A-live-*-shrub`, `PB-shrub-*`) used the cutout review's plain `shrub-review-library.yaml`, which leaves out the owner's chosen leaf entry, trial F (`Leaves: {uses: leaves, shade: {range: [110, 190]}}`, chosen 2026-10-19, [alpha.md](alpha.md#leaf-colour)). Measured on the whole sheet, 85.5% of the leaf pixels of `A-live-0-shrub` are the darkest green, as the alpha record found for the plain library (86%). The owner saw disconnected branches and, in their words, suspects the dark leaves are obscuring them. The baked-panel shrub runs (`PB-shrub-*`) have the same omission and have not been re-rendered.

### Evidence

- **Trial F:** `lib-F.yaml`, SHA-256 `f67099def641676eb9a39924f2f89455ba93b03d88b9df6a8996c4eff528b74c`, the file of `cutout-review/trials/lib-F.yaml` (hash recorded in alpha.md), copied unchanged into each candidate tree.
- **Shrub model v1:** `cutout-model/v1/shrub.glb`, SHA-256 `7a1a29382888c8c21a0b19c9418fdbcc5417e8ac038c9d626770ca6f4f0b684f`, unchanged.
- **Shrub model v2:** `cutout-model/v2/shrub.glb`, SHA-256 `0f8d8c2e95869d47998706733ae969a44a841b36ed794ef38a557d87c30d7285`, built by `make_shrub_v2.py` (SHA-256 `2890e4270fe9be8c7036171fe95c26a2286ea546dfeefe7f1150b8e5c420c115`; `make_shrub_v1.py` `8982eb3df892e40ca5fefc0753b9a4e4adc8021ea4459483336e1caa7aa4928a`) with Blender 5.2.2, headless, under the shared Blender lock, seed 20261019. Changes from v1 (the owner approved improving the model): the sprig texture has 11 leaves instead of 6, each broader (width 0.16 instead of 0.12); 110 outer and 34 inner leaf cards are requested instead of 48 and 14, which gives 122 cards in the file instead of 52. A card is 26% opaque (alpha >= 0.4) instead of 13%. The pot, soil, trunk and branches code, the card size, the sphere they sit on, the animation and the materials are v1's. Measured by comparing the two files: the vertex data of `Pot` (soil and terracotta) and of `Branches` (bark), and their node translations, are byte-identical. Not committed.
- **Candidates:** the six live-lit trees of round 1, copied (their project files are byte-identical to round 1's, so the diffs and hashes in [Candidate settings](#candidate-settings-and-the-proposed-project-file-changes) apply unchanged) with `libraries/lib-F.yaml` added.
- **Commands:** run by `helpers/run_case.py` (the round-1 runner, with `$REVIEW2` as its base), one at a time under the Blender lock, each as `XDG_CONFIG_HOME=$REVIEW2/candidates/<candidate> /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW2/candidates/<candidate>/moskophoros/libraries/lib-F.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $REVIEW2/inputs/models/<model> $REVIEW2/runs/<case>/shrub.png`, with `<candidate>` one of `live-0`, `live-sky20`, `live-sky40`, `live-skyw30`, `live-dith4`, `live-sky20-dith4` and `<model>` `shrub-v1.glb` (case suffix `-m1`) or `shrub-v2.glb` (`-m2`). The tool is round 1's (master `354a21f`). Every run exited 0.
- **Checks:** `helpers/check.py` over the 12 runs: all pass, with equal alpha and byte-identical normal and depth maps within each model's six runs. Output `$REVIEW2/checks.txt` (SHA-256 `ced1db4e5ea0de84104abdf6307454e85302558f4dc5031a71650bf98fad2ab5`).
- **Decision page:** `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-review/v2/page/index.html` (SHA-256 `2eef8063249b4a11cd28b94c8eebbbf986fb267e8a3567ac72c27e1bd898298a`), index `$REVIEW2/index.html` (SHA-256 `bc5bdbde46a2c91d172c3f325f6254677de1151ceb0da19d8d0cb3ef6526f652`), measurements `$REVIEW2/stats.json` (SHA-256 `dff0cc3386e15bb887c02794dfac7bcd0fc8073a8e9b7bbad7b4427b7cf1f109`).

Measured over each whole sheet (8 directions × 8 frames), leaf pixels by green, darkest first (`#3d431c #41631f #358824 #43ad55`), and visible pixels:

| Run | Model, leaf entry | Visible px | Leaf px | Leaf bands, % |
|---|---|---|---|---|
| round 1 `A-live-0-shrub` | v1, plain library (round 1) | 289,854 | 173,244 | 85.5 / 5.1 / 5.7 / 3.8 |
| round 1 `A-live-sky20-shrub` | v1, plain library (round 1) | 289,854 | 173,244 | 86.3 / 6.2 / 6 / 1.5 |
| round 1 `A-live-sky40-shrub` | v1, plain library (round 1) | 289,854 | 173,244 | 87.8 / 7.5 / 3.9 / 0.7 |
| round 1 `A-live-skyw30-shrub` | v1, plain library (round 1) | 289,854 | 173,244 | 86.5 / 6.3 / 5.3 / 1.9 |
| round 1 `A-live-dith4-shrub` | v1, plain library (round 1) | 289,854 | 173,244 | 85.5 / 5.1 / 5.7 / 3.8 |
| round 1 `A-live-sky20-dith4-shrub` | v1, plain library (round 1) | 289,854 | 173,244 | 86.4 / 6.1 / 5.8 / 1.7 |
| `S2-live-0-m1` | v1, trial F | 289,854 | 173,244 | 8.1 / 50.3 / 13 / 28.6 |
| `S2-live-0-m2` | v2, trial F | 398,950 | 305,455 | 0.5 / 68.5 / 14.7 / 16.2 |
| `S2-live-sky20-m1` | v1, trial F | 289,854 | 173,244 | 15.5 / 48.5 / 13 / 23 |
| `S2-live-sky20-m2` | v2, trial F | 398,950 | 305,455 | 2 / 73.4 / 12.5 / 12.2 |
| `S2-live-sky40-m1` | v1, trial F | 289,854 | 173,244 | 37.2 / 33.1 / 21.7 / 8 |
| `S2-live-sky40-m2` | v2, trial F | 398,950 | 305,455 | 34.1 / 47.1 / 12 / 6.8 |
| `S2-live-skyw30-m1` | v1, trial F | 289,854 | 173,244 | 17.5 / 47.1 / 17.3 / 18.1 |
| `S2-live-skyw30-m2` | v2, trial F | 398,950 | 305,455 | 6.9 / 68.5 / 13 / 11.6 |
| `S2-live-dith4-m1` | v1, trial F | 289,854 | 173,244 | 14.5 / 42.8 / 14 / 28.6 |
| `S2-live-dith4-m2` | v2, trial F | 398,950 | 305,455 | 7.7 / 59.6 / 16.2 / 16.4 |
| `S2-live-sky20-dith4-m1` | v1, trial F | 289,854 | 173,244 | 23.3 / 40.1 / 16.2 / 20.4 |
| `S2-live-sky20-dith4-m2` | v2, trial F | 398,950 | 305,455 | 18.6 / 55.7 / 13.9 / 11.7 |

The owner answered decisions 1 and 2 of this round (leaf colour: "B: better, not right"; model: "D: keep v1"), quoted verbatim under [Round 3](#round-3-the-shrubs-leaf-ramp); decision 3 (the look) is not answered and waits for the leaf colour.


Output files of the round's runs:

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `S2-live-0-m1` | `shrub-lit.Sway.gif` | 1,386,007 | `9b6829abab790a74943625e77fd3110c865c01a7feaf007daacb046d56688a35` |
| `S2-live-0-m1` | `shrub.Sway.gif` | 615,648 | `83c256e3aeee866dc69f2267a64ef9917110dfae69b7ed901035eae296216c8d` |
| `S2-live-0-m1` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `S2-live-0-m1` | `shrub.json` | 19,248 | `a3d64b36477683634424b098af19e12c1148ca7b2b49b08080fe31972a26dfa5` |
| `S2-live-0-m1` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `S2-live-0-m1` | `shrub.png` | 169,883 | `466155377d0c59c2b5281600849f93a47a364f92b86fb7709c80231048c55737` |
| `S2-live-0-m2` | `shrub-lit.Sway.gif` | 1,464,724 | `3223f7f8de31cb6f5d1ef9f1b7c9c7c186fd28e0b6f6a5b93a6728a044dfbcc2` |
| `S2-live-0-m2` | `shrub.Sway.gif` | 436,296 | `c9056cd3ded24cc374c1ff5d386d0f2dbd4067964d03fbeb449c8f0b022c8081` |
| `S2-live-0-m2` | `shrub.depth.png` | 416,036 | `b88f80213df7217ac763e9f359f9975112bd3a427aa5e0c76debe9c8945118b1` |
| `S2-live-0-m2` | `shrub.json` | 19,248 | `2d9c19d16c30ef0cb8c07d0ea82fa64d0c502e67375482ff26baf227fc848ca3` |
| `S2-live-0-m2` | `shrub.normal.png` | 676,945 | `4df7c89b2d23d21a6bb0a9053cdec6dd6619bad52b5c251728c98b349873b1b1` |
| `S2-live-0-m2` | `shrub.png` | 122,266 | `9e186327692ed783fa801dc3324a3c05dfae310353a1da1b5f44dc853b059b4a` |
| `S2-live-sky20-m1` | `shrub-lit.Sway.gif` | 1,410,956 | `3a807439e3586ef476e0b7b5e541afef2dbfce1e70c73f629aa5a9b6a711737f` |
| `S2-live-sky20-m1` | `shrub.Sway.gif` | 649,152 | `5771f9540798883d7c1dc11da0e2a75fb835d2126031df6bdf6479fc98730160` |
| `S2-live-sky20-m1` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `S2-live-sky20-m1` | `shrub.json` | 19,248 | `cd378a2a02afee5d48184739655c4a5b2fc847bfef25c8b9b4a18909ac956c54` |
| `S2-live-sky20-m1` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `S2-live-sky20-m1` | `shrub.png` | 181,065 | `52bf8503504595e5876f031d7bed9a1e595ba38b7414952d100e43a6afb34281` |
| `S2-live-sky20-m2` | `shrub-lit.Sway.gif` | 1,457,173 | `53e9a93c93a25b28b6a302ebbb00908b6cd3cdb34a2ad65b6862af7b7a815c0f` |
| `S2-live-sky20-m2` | `shrub.Sway.gif` | 440,112 | `6ddbfc92f55dc22d8f29b83ae899142dd3547ff18218f3ef602e733cc5e9d2b6` |
| `S2-live-sky20-m2` | `shrub.depth.png` | 416,036 | `b88f80213df7217ac763e9f359f9975112bd3a427aa5e0c76debe9c8945118b1` |
| `S2-live-sky20-m2` | `shrub.json` | 19,248 | `2d464f7e316ab2c913641239133344eff5b4b92ff278679df567240a26c3ff6a` |
| `S2-live-sky20-m2` | `shrub.normal.png` | 676,945 | `4df7c89b2d23d21a6bb0a9053cdec6dd6619bad52b5c251728c98b349873b1b1` |
| `S2-live-sky20-m2` | `shrub.png` | 123,894 | `edab691fcb4912bfe7bffbcff50e0fbcf4d5bf2f8873c129ab2020fb4b2b41d1` |
| `S2-live-sky40-m1` | `shrub-lit.Sway.gif` | 1,382,738 | `4c87cfa77366df254cc41f34ff24806ae03056bff184c506676b7533210bd165` |
| `S2-live-sky40-m1` | `shrub.Sway.gif` | 615,214 | `5a0d963b8c2d22c1c8bc33e01195cabd8c630efc9520e84d83855a102fb31e4a` |
| `S2-live-sky40-m1` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `S2-live-sky40-m1` | `shrub.json` | 19,248 | `13939c597ebb53c415f25b3bd164012dca45bc87752a43ceb7e159fb74cf9175` |
| `S2-live-sky40-m1` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `S2-live-sky40-m1` | `shrub.png` | 168,779 | `038c6ca255a36a2193a976f5fd7fbd871c879545f9f7292fbb9a270bc3db7394` |
| `S2-live-sky40-m2` | `shrub-lit.Sway.gif` | 1,456,937 | `cdb5511189b116c9cc6fafdab956819a5a09e618f5f9c3861adf7d2a4c861d15` |
| `S2-live-sky40-m2` | `shrub.Sway.gif` | 482,359 | `ee9d88d1dc11a0f5c00660280bb1994b01831dcf5c79bf3f289151702f7f6ca4` |
| `S2-live-sky40-m2` | `shrub.depth.png` | 416,036 | `b88f80213df7217ac763e9f359f9975112bd3a427aa5e0c76debe9c8945118b1` |
| `S2-live-sky40-m2` | `shrub.json` | 19,248 | `d81a5409f35efd5fbc9571d788973983326694506451abd618ea589a5ef78d73` |
| `S2-live-sky40-m2` | `shrub.normal.png` | 676,945 | `4df7c89b2d23d21a6bb0a9053cdec6dd6619bad52b5c251728c98b349873b1b1` |
| `S2-live-sky40-m2` | `shrub.png` | 132,611 | `f71ecfceb7d72b7f3037f09bcec49544690da78f3e3d373bdd76022f0b5b2318` |
| `S2-live-skyw30-m1` | `shrub-lit.Sway.gif` | 1,437,159 | `1dda0866d3bb02da01d900607a488ca7a7a16cdb9a3a13e18a664b7c288d3d74` |
| `S2-live-skyw30-m1` | `shrub.Sway.gif` | 669,779 | `d780cb839a64a558fa6eaa201d83f6aaa6c230257c6190cc48182190b300ef8f` |
| `S2-live-skyw30-m1` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `S2-live-skyw30-m1` | `shrub.json` | 19,247 | `d2c7ab8b9b095ae7953bb1f189ab75c07ec315f2a569076aa506c7422c655e35` |
| `S2-live-skyw30-m1` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `S2-live-skyw30-m1` | `shrub.png` | 183,669 | `57d2cba4cba8e6868ab2ff30f6da4747975b6009552c16f19a4d033ef3764ce3` |
| `S2-live-skyw30-m2` | `shrub-lit.Sway.gif` | 1,502,825 | `a7749af49d98684e6ae377d5bebaa7f3daa27586f7a2f3ae03d666612c29bbe4` |
| `S2-live-skyw30-m2` | `shrub.Sway.gif` | 492,165 | `e46a2e13329fe02a83e438c022ddde7b789a18e11a7498231ec6b71d5109f6c9` |
| `S2-live-skyw30-m2` | `shrub.depth.png` | 416,036 | `b88f80213df7217ac763e9f359f9975112bd3a427aa5e0c76debe9c8945118b1` |
| `S2-live-skyw30-m2` | `shrub.json` | 19,247 | `4da6fa599a24765c54c68f43f3f2b03f0bc4da36873ab0b4491f7cf7c1f4cecd` |
| `S2-live-skyw30-m2` | `shrub.normal.png` | 676,945 | `4df7c89b2d23d21a6bb0a9053cdec6dd6619bad52b5c251728c98b349873b1b1` |
| `S2-live-skyw30-m2` | `shrub.png` | 135,411 | `8bc38d0210f3dc322ed562853a8542b32fb3d401a775fab7585648571fbd79f5` |
| `S2-live-dith4-m1` | `shrub-lit.Sway.gif` | 1,438,761 | `6784ba9b264b0e9300dda02a4f6a9bce3d8c5e76707faa52a13345a54146dbb7` |
| `S2-live-dith4-m1` | `shrub.Sway.gif` | 668,458 | `33a9794ca9b05afb809003eb55de9c1d741155e1d84ffc9ecac5bc769d02aee7` |
| `S2-live-dith4-m1` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `S2-live-dith4-m1` | `shrub.json` | 19,253 | `bb5fe1fd8059894ae88ea81860ff284a3768b45cf52ff75e8197a03315458e3d` |
| `S2-live-dith4-m1` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `S2-live-dith4-m1` | `shrub.png` | 192,461 | `bcfba7eb48395e296762848beb2b293c798861cd9320f8ca16505b19078edeaf` |
| `S2-live-dith4-m2` | `shrub-lit.Sway.gif` | 1,608,053 | `9a08f1f4be3a320d4217e620a135b451590bca0008ca075b2e70a4575756dcf2` |
| `S2-live-dith4-m2` | `shrub.Sway.gif` | 573,291 | `8c9f59f4926618468b76104c01e851d0afe3b533570e7f4c5f9902b27c62b7f3` |
| `S2-live-dith4-m2` | `shrub.depth.png` | 416,036 | `b88f80213df7217ac763e9f359f9975112bd3a427aa5e0c76debe9c8945118b1` |
| `S2-live-dith4-m2` | `shrub.json` | 19,253 | `c761b44c72498dce12eaa668d35d911ca9988c16989c890c9531f5cde9122835` |
| `S2-live-dith4-m2` | `shrub.normal.png` | 676,945 | `4df7c89b2d23d21a6bb0a9053cdec6dd6619bad52b5c251728c98b349873b1b1` |
| `S2-live-dith4-m2` | `shrub.png` | 158,573 | `6dba386176879bc1bb014a93a1ae6715a4ce97e3d34d22792302b34ae01d51bd` |
| `S2-live-sky20-dith4-m1` | `shrub-lit.Sway.gif` | 1,506,418 | `b97c635cee94225a187535bd185fe6a11bb3e07cafe289c6b9ea56aba35899ce` |
| `S2-live-sky20-dith4-m1` | `shrub.Sway.gif` | 711,590 | `04d5871fd7023defc697524153b9e5b053799aa43dd0b8737bb96f34154690df` |
| `S2-live-sky20-dith4-m1` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `S2-live-sky20-dith4-m1` | `shrub.json` | 19,253 | `7553a97b1aae9bfca0702f71ba1bf3e8da42fea098ec7b61f2c17f805fe41953` |
| `S2-live-sky20-dith4-m1` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `S2-live-sky20-dith4-m1` | `shrub.png` | 202,692 | `07fd3e46b721f2d158a58b26a4a02c593323c3ddecb5ffdcb3858ed42d479976` |
| `S2-live-sky20-dith4-m2` | `shrub-lit.Sway.gif` | 1,677,839 | `e2ece35d7c196e172007a5d4f9852cbd23963769184648716c316b76fcab064c` |
| `S2-live-sky20-dith4-m2` | `shrub.Sway.gif` | 604,657 | `547ba65de9c881a3f3dd2d529e969f396ba5e17799bb2150f98c1e75eb404563` |
| `S2-live-sky20-dith4-m2` | `shrub.depth.png` | 416,036 | `b88f80213df7217ac763e9f359f9975112bd3a427aa5e0c76debe9c8945118b1` |
| `S2-live-sky20-dith4-m2` | `shrub.json` | 19,253 | `5ead5986459d63cfe4fddaf22cf53c79f9a29cc32203a78fb57990d4dc32f68b` |
| `S2-live-sky20-dith4-m2` | `shrub.normal.png` | 676,945 | `4df7c89b2d23d21a6bb0a9053cdec6dd6619bad52b5c251728c98b349873b1b1` |
| `S2-live-sky20-dith4-m2` | `shrub.png` | 165,652 | `dec72c6ca1a70e45bdee3199ed4a8807d9c401a588eb717553add9f617aa0c27` |
## Round 3: the shrub's leaf ramp

Rounds 1 and 2 are unchanged. This round adds new evidence under `$REVIEW3=~/.local/share/moskophoros-acceptance/shading-review/v3`. It is not a verdict.

### The owner's answers on round 2

Relayed by the moskophoros manager for request `moskophoros-20261020-1` in `~/.local/state/project-manager/moskophoros/relay-144-shrub-2.md` (SHA-256 `eafad3ac450bd9b1b8440e29fb39387a0beff9af5e3386f5f7b8a18dc84dc91b`). The owner answered in the manager's terminal on 2026-10-22 (UTC), through the manager's multiple-choice questions on the round-2 page. Verbatim selections:

1. "Section 1 of the shrub page: does the leaf colour fix (trial F) help?" -> "B: better, not right"
2. "Section 2: which shrub model? v1 (52 cards, branches visible through gaps) or v2 (122 cards, a full ball that hides most of the trunk from above)?" -> "D: keep v1"
3. Follow-up, after the manager showed a zoomed v1 + trial F canopy: "With trial F, what is still not right about the greens? (Pick all that apply)" -> "Two greens clash, Jump too big, Still too dark, Highlights too bright" (as shown to the owner: two greens clash = "the dull olive mass and the bright emerald leaves look like different colours; I want one green family"; jump too big = "dark to bright happens in one step; I want more in-between shades so leaves blend"; still too dark = "too much of the canopy is the dull olive; overall it should be lighter"; highlights too bright = "the bright emerald leaves pop out too much, like neon or noise").

Section 3 of the round-2 page (which look) is not answered: it waits for the leaf colour. The owner keeps the v1 model; the trunk and branches stay as they are until the leaves are settled.

### Evidence

- **Model:** `shrub.glb` v1, SHA-256 `7a1a29382888c8c21a0b19c9418fdbcc5417e8ac038c9d626770ca6f4f0b684f`, unchanged. **Look:** candidate A, the owner's current project settings (no sky, no dither), the round-1 tree, byte-identical `projects/synarchy.yaml`.
- **Candidates L0 to L5**, one render each, each a copy of trial F's library with only the `Leaves` entry's ramp and its own range changed; no owner file changes (the shrub library is a review file):

| Candidate | Library file SHA-256 | `Leaves` ramp | Range |
|---|---|---|---|
| L0 | `f67099def641676eb9a39924f2f89455ba93b03d88b9df6a8996c4eff528b74c` (`libraries/leaf-L0.yaml`) | indices [34, 35, 36, 37] = #3d431c #41631f #358824 #43ad55 | [110, 190] |
| L1 | `5d43fa30b3f99cac4b1ca211078c2369515423e7d2402abd2a419ecbe8c3228e` (`libraries/leaf-L1.yaml`) | indices [46, 45, 44, 43, 42] = #343728 #414d35 #4a6844 #658b6b #8dad9d | [84, 226] |
| L2 | `10c492932010ae7dd9805939306a1069788473252104465edeece0bec5872076` (`libraries/leaf-L2.yaml`) | indices [29, 28, 27, 26] = #534c39 #5d603f #768560 #95ad8d | [40, 240] |
| L3 | `9803c22ef1497d674be62ebf0789bdc4c786e223b7ba8f358e7fa5290a8d7069` (`libraries/leaf-L3.yaml`) | indices [19, 20, 21, 22] = #6a5822 #757d22 #7ba540 #87ca70 | [40, 240] |
| L4 | `3f8de37716e19294d2716e625eedf9ab3b9aaa574737b664d449a5cc5a628dfb` (`libraries/leaf-L4.yaml`) | indices [34, 35, 44, 43] = #3d431c #41631f #4a6844 #658b6b | [40, 240] |
| L5 | `38342646b6103c030b0fe0a9a2b6ec2ae74b277cd4456a5f26b1212afdf34785` (`libraries/leaf-L5.yaml`) | generated `{base: "#43ad55", bands: 6, lightness_step: 0.05, hue_shift_deg: -6.0, chroma_fade: 0.3}`, resolved to indices [35, 35, 36, 36, 37, 37] = #41631f #41631f #358824 #358824 #43ad55 #43ad55 | [94, 218] |

L0 is `lib-F.yaml` (SHA-256 `f67099de…b74c`, the owner's trial F) copied unchanged. The generated ramp of L5 is the library's own form (a `/3` library); the tool snapped its six bands onto three palette greens, each used twice.

- **How the ranges were picked** (a proposal, not a choice; the relay asked that the canopy be lighter than trial F, with most leaf pixels on the middle bands, few on the darkest and the lightest reserved for leaves facing up): a calibration capture (`calibration/cal.png`, SHA-256 `ddc2c129a81e79adc1c8b14879554f5699508e9f535c7d55573147191eec4861`) gave the leaves a 64-entry ramp (palette entries 64 to 127) over shade 0 to 255, so each leaf pixel's colour names a 4-wide bin of its raw shade, 22,088 leaf pixels, all eight directions at frame 0 (`calibration/histogram.json`, SHA-256 `be1ffc9fa5f724e789256b9c4744a19376b0bb9123acb776379f97a88f7a6d07`). `helpers/calibrate.py` searched, for 4, 5 and 6 equal bands, the range whose bands best match shares of about 8% (darkest), 15% (lightest) and an equal split between: 4 bands [40, 240]; 5 bands [84, 226]; 6 bands [94, 218] (`calibration/ranges.json`, SHA-256 `f9d2e6ab9f68e796a3a71185f768a8846610a908bf5c069a892e7011ce6d0c4f`). The same histogram reproduces trial F's measured shares closely (9.9, 48.6, 12.3, 29.3 against 8.1, 50.3, 13.0, 28.6).
- **Commands:** `$REVIEW3/helpers/run_case.py R3-L0 … R3-L5`, each `XDG_CONFIG_HOME=$REVIEW3/candidates/live-0 /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW3/candidates/live-0/moskophoros/libraries/leaf-<L>.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $REVIEW3/inputs/models/shrub.glb $REVIEW3/runs/R3-<L>/shrub.png`; master `354a21f`, headless Blender 5.2.2, under the lock; every run exited 0. The calibration capture used `--frames 1` and `cal-lib.yaml` instead of the library, output `calibration/cal.png`.
- **Checks:** `helpers/check.py`, all pass; alpha and the normal and depth maps are identical across the six runs (output `checks.txt`, SHA-256 `8fc5c1aacc4acc619ece76a697d016109bd759b99b2c4a4b21a795031ae08cb2`). L0's sheet, maps and both preview GIFs are byte-identical to round 2's `S2-live-0-m1`; only the sheet JSON differs (model, subject and library file names, and so the fingerprint).
- **Decision page:** `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-review/v3/page/index.html` (SHA-256 `c792026b266231a87dcdf3272815077105d960314cbf218077627a67ec45fd16`), index `$REVIEW3/index.html` (SHA-256 `b57644003ac1fe3ebe0b50ebb05d2278633b5618c026bc1cdcee2a47b9fbe87d`), measurements `stats.json` (SHA-256 `b7e604fc2bebb0d4372cedd60473e24583c12113006459587beb1fdb2ff172d5`).

Measured over each whole sheet (8 directions × 8 frames), the share of leaf pixels on each distinct green, darkest first:

| Candidate | Greens, darkest first | Share, % |
|---|---|---|
| L0 | #3d431c #41631f #358824 #43ad55 | 8.1 / 50.3 / 13 / 28.6 |
| L1 | #343728 #414d35 #4a6844 #658b6b #8dad9d | 3.6 / 41.9 / 25.4 / 14.2 / 14.9 |
| L2 | #534c39 #5d603f #768560 #95ad8d | 1.3 / 42.6 / 37.4 / 18.7 |
| L3 | #6a5822 #757d22 #7ba540 #87ca70 | 1.3 / 42.6 / 37.4 / 18.7 |
| L4 | #3d431c #41631f #4a6844 #658b6b | 1.3 / 42.6 / 37.4 / 18.7 |
| L5 | #41631f #358824 #43ad55 | 21 / 53.6 / 25.4 |

### The owner's leaf-ramp choice

Relayed by the moskophoros manager for request `moskophoros-20261020-1` in `~/.local/state/project-manager/moskophoros/relay-144-shrub-3.md` (SHA-256 `225e90677ffc4d2efb072588fd04fb9c64e186a96d53b98d276c982fecfb5f5a`). The owner, in the manager's terminal on 2026-10-22, after viewing the round-3 page (asked "Which leaf ramp for the shrub?"), verbatim:

> "L0 looks good, i assumed you overwrote the file since you didnt give me alink, so i actually never saw this, it looks ok, but i would say that L1 has better color, L4 looks good, L5 is probably the most realistic looking, but i could see myself using any of these. i would say we pick L1"

**Choice: L1, muted green:** the shrub's `Leaves` ramp `[46, 45, 44, 43, 42]` (#343728 #414d35 #4a6844 #658b6b #8dad9d) with its own shade range `[84, 226]`, as rendered in round 3. It is bound to library `leaf-L1.yaml` (SHA-256 `5d43fa30b3f99cac4b1ca211078c2369515423e7d2402abd2a419ecbe8c3228e`) and to the run `R3-L1`: `shrub.json` `04f377351da173c2965968bbfbf909dfdb03554b6ae2a26470ebfeac28ddad2e`, `shrub.png` `0a066fb49d8d197d671022c139856d52026dcdb2f73a2e5fa6bc72a1a9ce8174`. It lives in the shrub's review library only; **no owner file changes** for it. It is a choice of the leaf ramp, not a verdict on either use.


Output files of the round's runs:

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `R3-L0` | `shrub-lit.Sway.gif` | 1,386,007 | `9b6829abab790a74943625e77fd3110c865c01a7feaf007daacb046d56688a35` |
| `R3-L0` | `shrub.Sway.gif` | 615,648 | `83c256e3aeee866dc69f2267a64ef9917110dfae69b7ed901035eae296216c8d` |
| `R3-L0` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R3-L0` | `shrub.json` | 19,244 | `a6c7dd21a3efd2c120a41de18ad65e9e554c8995051bb773fe570b9ea15af00d` |
| `R3-L0` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R3-L0` | `shrub.png` | 169,883 | `466155377d0c59c2b5281600849f93a47a364f92b86fb7709c80231048c55737` |
| `R3-L1` | `shrub-lit.Sway.gif` | 1,398,600 | `0eef7e719483776c247788efde027a875c0ea6c0b2bb95f40588d1023d23d4a0` |
| `R3-L1` | `shrub.Sway.gif` | 660,626 | `28f53725341a7448c6c5916a4ad75b2eefe59314e8722d533c9df767f5600da7` |
| `R3-L1` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R3-L1` | `shrub.json` | 19,259 | `04f377351da173c2965968bbfbf909dfdb03554b6ae2a26470ebfeac28ddad2e` |
| `R3-L1` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R3-L1` | `shrub.png` | 181,760 | `0a066fb49d8d197d671022c139856d52026dcdb2f73a2e5fa6bc72a1a9ce8174` |
| `R3-L2` | `shrub-lit.Sway.gif` | 1,384,201 | `441accd9a5bdc7982dd98cb4f6574d6825b0ea4ef207f5dc50f49b5382faedc5` |
| `R3-L2` | `shrub.Sway.gif` | 600,158 | `04478d1e29e77d2eece58094e75df1ffc99d2c7fb0bb33a7aecf2628d1b10108` |
| `R3-L2` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R3-L2` | `shrub.json` | 19,243 | `b49426169c6518d36af832abf7be3d5f694ab12d4347270a90f2fc6b6882ad72` |
| `R3-L2` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R3-L2` | `shrub.png` | 161,330 | `d7fc84b3a643e53c5a09ecc5fb7ba6f8f5e77532db0dc857a8fd0601785161f8` |
| `R3-L3` | `shrub-lit.Sway.gif` | 1,389,711 | `2707983e1d02a18622a8e7aceba5e43205f1c5e1aaa1b8da137e2e3b52f1c33a` |
| `R3-L3` | `shrub.Sway.gif` | 600,158 | `4ae237e701235c8b253587e2315bed2df449eda762b0455ba4aa0cd04f4bd3d9` |
| `R3-L3` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R3-L3` | `shrub.json` | 19,243 | `37b245b3b3360c2e4774d695fe2c8a3882a606ffed28997bc337a3aae1f348e6` |
| `R3-L3` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R3-L3` | `shrub.png` | 162,307 | `c964635b16e940b928b36fa08c2ef2871bd5bd1b8c6fd4eff67ae4844640be11` |
| `R3-L4` | `shrub-lit.Sway.gif` | 1,389,227 | `fac5b92a0a19bb6e7cfb04e187ad49d8dbf066fd42d62f970f701238143c0a39` |
| `R3-L4` | `shrub.Sway.gif` | 600,158 | `a19ccc5db1de8771522fcb6b3758ab1dcdf05bf6d76a86d9cf3066fedcd0d750` |
| `R3-L4` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R3-L4` | `shrub.json` | 19,243 | `1b42ab193ea6efa6007ebe38917f8876f46b7ae9726bb5ab148e9534d1681ffa` |
| `R3-L4` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R3-L4` | `shrub.png` | 162,830 | `38a7d65f3433a617ed1f5b6dca27879d57695483d5c4f51e962ecd4083c9b216` |
| `R3-L5` | `shrub-lit.Sway.gif` | 1,386,299 | `a86a03729f1ac2a5685bc01751a18e4f2549130789d0790cc60466305414c75f` |
| `R3-L5` | `shrub.Sway.gif` | 590,812 | `3e42518dc51485329ed065b03376788e666d76537a214ede9a4e86e304e16d11` |
| `R3-L5` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R3-L5` | `shrub.json` | 19,484 | `6a472527a93eb782ed765b34c126186b899bfddb26dc0e8bd604af79db51171b` |
| `R3-L5` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R3-L5` | `shrub.png` | 160,845 | `19af5aa8b7b46f8d40e9b8c219849922bd3136d7715788b55414aec776ac2a3e` |
## Round 4: the six live-lit looks on the shrub with L1 leaves

Rounds 1 to 3 are unchanged. This round adds new evidence under `$REVIEW4=~/.local/share/moskophoros-acceptance/shading-review/v4`, after the owner chose leaf ramp L1 ([Round 3](#round-3-the-shrubs-leaf-ramp)). It is not a verdict.

- **Runs:** the six section-1 candidates (`live-0`, `live-sky20`, `live-sky40`, `live-skyw30`, `live-dith4`, `live-sky20-dith4`; their project files and diffs are round 1's, byte-identical) on the v1 shrub (SHA-256 `7a1a29382888c8c21a0b19c9418fdbcc5417e8ac038c9d626770ca6f4f0b684f`) with `leaf-L1.yaml` (SHA-256 `5d43fa30b3f99cac4b1ca211078c2369515423e7d2402abd2a419ecbe8c3228e`, the round-3 file).
- **Commands:** `$REVIEW4/helpers/run_case.py R4-<candidate>`, each `XDG_CONFIG_HOME=$REVIEW4/candidates/<candidate> /usr/bin/lockf -k $LOCK $TOOL --project synarchy --view iso --directions 8 --cell 128x128 --materials $REVIEW4/candidates/<candidate>/moskophoros/libraries/leaf-L1.yaml --clip Sway --frames 8 --blender /opt/homebrew/bin/blender $REVIEW4/inputs/models/shrub.glb $REVIEW4/runs/R4-<candidate>/shrub.png`; master `354a21f`, headless Blender 5.2.2, under the lock. Every run exited 0.
- **Checks:** `helpers/check.py`, output `checks.txt` (SHA-256 `faf2d33471e6b91a14b4921b72c1d496e007469664510092ccbb476bad4fdfdf`): alpha and the normal and depth maps identical across the six runs. `R4-live-0` is the same configuration as round 3's `R3-L1`; its sheet, maps and GIFs are byte-identical to it.
- **Decision page:** `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/shading-review/v4/page/index.html` (SHA-256 `3cce4d64686ddecc1014810da9de2e088562569bc899e2916c4ef6fe49be91aa`), shrub rows (L1) beside round 1's unchanged robot and chest images, with each look's exact diff; index `$REVIEW4/index.html` (SHA-256 `bd158efae0cb9c2172ba89f004addc8cf8b08ea268bcba21ca76f5c566a554d5`), measurements `stats.json` (SHA-256 `e25021e498c3753cfc17c3b5d8095103eef45adc2f7799dacc62d783617c2b14`).

Measured over each whole sheet (8 directions × 8 frames), the share of the shrub's leaf pixels on each L1 green, darkest first (#343728 #414d35 #4a6844 #658b6b #8dad9d):

| Run | Share, % |
|---|---|
| `R4-live-0` | 3.6 / 41.9 / 25.4 / 14.2 / 14.9 |
| `R4-live-sky20` | 4.6 / 54.6 / 19.6 / 16.6 / 4.5 |
| `R4-live-sky40` | 8.1 / 61 / 21 / 7.9 / 2.1 |
| `R4-live-skyw30` | 5.2 / 54.7 / 20.1 / 14 / 6 |
| `R4-live-dith4` | 3.8 / 34.2 / 32.7 / 14.6 / 14.7 |
| `R4-live-sky20-dith4` | 6 / 49 / 23.7 / 15.9 / 5.3 |

The owner's answer (which live-lit look) goes here when it arrives.

Output files of the round's runs:

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `R4-live-0` | `shrub-lit.Sway.gif` | 1,398,600 | `0eef7e719483776c247788efde027a875c0ea6c0b2bb95f40588d1023d23d4a0` |
| `R4-live-0` | `shrub.Sway.gif` | 660,626 | `28f53725341a7448c6c5916a4ad75b2eefe59314e8722d533c9df767f5600da7` |
| `R4-live-0` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R4-live-0` | `shrub.json` | 19,259 | `04f377351da173c2965968bbfbf909dfdb03554b6ae2a26470ebfeac28ddad2e` |
| `R4-live-0` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R4-live-0` | `shrub.png` | 181,760 | `0a066fb49d8d197d671022c139856d52026dcdb2f73a2e5fa6bc72a1a9ce8174` |
| `R4-live-sky20` | `shrub-lit.Sway.gif` | 1,388,142 | `2cb39b2af89007a9d5d57b05cde720e713634c5596f4e189317bba64848d6253` |
| `R4-live-sky20` | `shrub.Sway.gif` | 635,688 | `3d3b79d3c51a32b42a5440a1572bcc3d5736ef7c55aa5e3c966488c14f62552c` |
| `R4-live-sky20` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R4-live-sky20` | `shrub.json` | 19,259 | `5d3a089b97545023b817f8bd7af32a9a6baff79b948d55b0e7c8f4c3aa0e7d62` |
| `R4-live-sky20` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R4-live-sky20` | `shrub.png` | 173,096 | `f67cdeae0adaa756b6276e3e7fd035610a2ce5c49658de78fae166b12ec6d30d` |
| `R4-live-sky40` | `shrub-lit.Sway.gif` | 1,362,905 | `37cda238476dd52e0218d12fa8d669bf01e85b9261a0e0564754f0a6a6f31abc` |
| `R4-live-sky40` | `shrub.Sway.gif` | 590,716 | `3c03e626204557001f4cb974f21d165a4d6a28af36386bfea70a6345c0889bcc` |
| `R4-live-sky40` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R4-live-sky40` | `shrub.json` | 19,259 | `f9e6c1dc282b12dcb204e5db72bd90036d8570faef540a4b6b176f07a22113f3` |
| `R4-live-sky40` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R4-live-sky40` | `shrub.png` | 159,620 | `498b18104750dab7f1431fae5ec880b82ae2b3dca0c88fa156550616bce853f2` |
| `R4-live-skyw30` | `shrub-lit.Sway.gif` | 1,424,776 | `f176f42e9e2eeb99800c32ec9c4ba37c269ef80c0dce44715e810dac251b3cdd` |
| `R4-live-skyw30` | `shrub.Sway.gif` | 666,963 | `71a58222c63468998620519b6c5d417c4d729e569ec5c307f0478bac4b9e9d50` |
| `R4-live-skyw30` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R4-live-skyw30` | `shrub.json` | 19,258 | `04076016e1a88bd73eb7eb6fbffe532b8d75c65a131ff75c1a939642e2530bef` |
| `R4-live-skyw30` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R4-live-skyw30` | `shrub.png` | 179,945 | `bcb0329b14418aeb61d858f508efb8cc53ceda6a2af377d0c61a421caaec85ef` |
| `R4-live-dith4` | `shrub-lit.Sway.gif` | 1,467,431 | `296b4665a82cc24dd07fc772a0cb03119cc3012f529104f89b3160266b8c7530` |
| `R4-live-dith4` | `shrub.Sway.gif` | 705,939 | `135e6b082304dd7ed3a3966461ab579d0228bd2c280b6aaba3250c4268d775a2` |
| `R4-live-dith4` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R4-live-dith4` | `shrub.json` | 19,264 | `ecfca51de4fa76651c65e8d6ea771d0fbf9406011ef70da1311dfa774f281739` |
| `R4-live-dith4` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R4-live-dith4` | `shrub.png` | 201,658 | `f66e752d5919425070079feca1974c8aed39a2421a3bdfd749bbf92dd44da62b` |
| `R4-live-sky20-dith4` | `shrub-lit.Sway.gif` | 1,477,936 | `5cb0f80966129a473beb6de0944a1b84af3e44abab90cc8c75062c9dec4f732b` |
| `R4-live-sky20-dith4` | `shrub.Sway.gif` | 708,853 | `b809bf2f8fe16ef3e4f5ae09af2e2bb944496a7c2839c011b3fcd48f147ed9bc` |
| `R4-live-sky20-dith4` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `R4-live-sky20-dith4` | `shrub.json` | 19,264 | `022a4c19a374908ece41d1826cb949644fec73e0e13d53373812d9d425f62503` |
| `R4-live-sky20-dith4` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `R4-live-sky20-dith4` | `shrub.png` | 197,995 | `dd94786e40bfbb4b23e979174f861071c8a331f622fd996850abb2096ea0c554` |

## Output

Nothing here is committed. Size in bytes and SHA-256 of each unaltered output file of each run:

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `PB-robot-ramp-soft` | `robot.Walking.gif` | 148,515 | `2aab9995bf1ef3d2e0221e3c2ff72ed134aed6d147d6f00c8289f85565d59839` |
| `PB-robot-ramp-soft` | `robot.json` | 9,509 | `55c98b4cfaa242e319b1033aef3caaf53de367355e606fddedac113218c0d038` |
| `PB-robot-ramp-soft` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-ramp-soft` | `robot.png` | 35,430 | `e04787094e106a66df714f06a488a081b5a0d6a0e48efc459951608a8100a624` |
| `PB-robot-ramp-strong` | `robot.Walking.gif` | 136,140 | `8cd38d3642d948dd1bdf9acf98ac1e74c56f602cac5643897b7a6a7450eda8c6` |
| `PB-robot-ramp-strong` | `robot.json` | 9,507 | `783dec1239ead61188e66dcd3cd9a6571536bd5860b68a3940046465cc005abd` |
| `PB-robot-ramp-strong` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-ramp-strong` | `robot.png` | 30,474 | `b40002e2c1a939dc140683d84e25b2ae68545c184cab0a542840e6b6442e0375` |
| `PB-robot-ramp-strong-lit` | `robot-lit.Walking.gif` | 449,926 | `48d47c3ae53c6d13fb08beaef6e721b3b3567a3b11540ff1a3a0466236411279` |
| `PB-robot-ramp-strong-lit` | `robot.Walking.gif` | 136,140 | `8cd38d3642d948dd1bdf9acf98ac1e74c56f602cac5643897b7a6a7450eda8c6` |
| `PB-robot-ramp-strong-lit` | `robot.json` | 9,559 | `cc8afa3b8f028b34c4b31f6285779cea460227dde5c4635c89610e5d292393ff` |
| `PB-robot-ramp-strong-lit` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-ramp-strong-lit` | `robot.png` | 30,474 | `b40002e2c1a939dc140683d84e25b2ae68545c184cab0a542840e6b6442e0375` |
| `PB-robot-ramp-ordered4` | `robot.Walking.gif` | 171,804 | `d92c7b8a6670dbd8f024aab996b8eb1053c511832387e2e62a90c1c2db916b34` |
| `PB-robot-ramp-ordered4` | `robot.json` | 9,512 | `6d8b83038affc7b5e0164f32955313c7ea97e47ecf1a73b6ccad22ece20c6395` |
| `PB-robot-ramp-ordered4` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-ramp-ordered4` | `robot.png` | 38,911 | `ce608f869367ddaadcf9c0ce1387ab78aaa19cc9f3f2849459bd31b356c02051` |
| `PB-robot-ramp-clustered4-s06` | `robot.Walking.gif` | 151,286 | `2782c90edb80f17abe1c52695fe6e49e8039a3fff07f4d44727330f032df7415` |
| `PB-robot-ramp-clustered4-s06` | `robot.json` | 9,514 | `33cfcec684e91e5d000fc9480b98b309782e1f91c86bd1267a2fb5abab40ffac` |
| `PB-robot-ramp-clustered4-s06` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-ramp-clustered4-s06` | `robot.png` | 35,837 | `2895bcc738b2ef458c32b458998242cdcc4a50035a31e86ad3dd0b5fe1b2a520` |
| `PB-robot-ramp-shuffled8` | `robot.Walking.gif` | 176,990 | `3d97246a1ca44ea5d6f9950e54e79ff7cb1ea99e90fe6424b8d24163f54cf0eb` |
| `PB-robot-ramp-shuffled8` | `robot.json` | 9,513 | `d33855611199f6d452ddf10fabedfd3f2d325c495c6021f25855727afa5a09cd` |
| `PB-robot-ramp-shuffled8` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-ramp-shuffled8` | `robot.png` | 43,054 | `db72674c04ea2f7e0b8d8a92caef1265a117a0f83b248f76faaf0d9d044e039b` |
| `PB-robot-ramp-mode-ordered4` | `robot.Walking.gif` | 172,943 | `47881f131d3f4eb296adfb05436c63065bf1de39fac13f804d0989f0aa451196` |
| `PB-robot-ramp-mode-ordered4` | `robot.json` | 9,511 | `2f7dc9e4ecc10295f67424606f40776a45d2ed1d841d5087d3ec32e041094e32` |
| `PB-robot-ramp-mode-ordered4` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-ramp-mode-ordered4` | `robot.png` | 39,210 | `9f6b9ee0bc12b82b25f208d9c013c8a2b4d6f788d87006d9a73edf18386d685c` |
| `PB-robot-brightness` | `robot.Walking.gif` | 547,123 | `f6b611ce1e9ff68665b330b967f83dbf409fd61bbf5aa63e86efff477ab24159` |
| `PB-robot-brightness` | `robot.json` | 9,513 | `e00198538e86954aa4052d17cf18bae0bebac8c1f85254fc34b729c8fc416fcb` |
| `PB-robot-brightness` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-brightness` | `robot.png` | 132,296 | `6171d54477f56cee7bb2596159df76aa89f440f4873f41cd1a1972eb76fd6f29` |
| `PB-robot-brightness-snap-palette-ordered4` | `robot.Walking.gif` | 224,056 | `641507bbc7e67dfee2137a0f313f0fe1f4878b1026beba6b437d8acd518716fb` |
| `PB-robot-brightness-snap-palette-ordered4` | `robot.json` | 9,522 | `8bc5fce50d648f10eabebd9a037429a081e614010db4041ada112b9f0306b232` |
| `PB-robot-brightness-snap-palette-ordered4` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-brightness-snap-palette-ordered4` | `robot.png` | 55,701 | `4c41354b38e0ce88077767cea211564ae0a512602bae1603ccd850a1f825803d` |
| `PB-robot-both` | `robot.Walking.gif` | 483,204 | `f14e7ccec3ae205124fb6ab7ccda33f8bcb605c8c412ba901d5e734279d97ef1` |
| `PB-robot-both` | `robot.json` | 9,507 | `edf28e4a942188fc7436e6e9a7f8dcb81bbc05c2aaf745c665a06806685a1aee` |
| `PB-robot-both` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-both` | `robot.png` | 123,455 | `7e61f6a7de4668d07f8f70a8dada7af698183060cde5185f5c883d7a81032ddf` |
| `PB-robot-both-snap-ramp-ordered4` | `robot.Walking.gif` | 145,035 | `4a15de218c3e8286b75dba3ca07a520ff2ed9bdeea5bb7abda8d39a20b428f40` |
| `PB-robot-both-snap-ramp-ordered4` | `robot.json` | 9,513 | `627d9ee22fec3c0cc9571479107cc0cd2236c99bc19527645200e9ee1f8b14b1` |
| `PB-robot-both-snap-ramp-ordered4` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-both-snap-ramp-ordered4` | `robot.png` | 32,933 | `43aed6e1d200e3f3e9609ccf840fda22c1fc3e908e18644141e53b4e3cda1228` |
| `PB-robot-neither` | `robot.Walking.gif` | 82,673 | `62431b625b224cb6839c0354ecfb7ba34607cd4500319d011c69dbed5f0d3309` |
| `PB-robot-neither` | `robot.json` | 9,510 | `cd76bd24e957fd4c0c5b28ad811518c663b4a6e4559649f07fe8b2172ca22810` |
| `PB-robot-neither` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-neither` | `robot.png` | 17,063 | `27532fed8bdfa1b1d3925107cd7c90b8e45cd08daa0d7a798e7d5743337efe60` |
| `PB-robot-roll-world-ordered4` | `robot.Walking.gif` | 149,837 | `18405282a73970f0802e369583fcf319e4ed61819528242ca7590504a8ed8031` |
| `PB-robot-roll-world-ordered4` | `robot.json` | 9,514 | `68f6ba97f1821f1d94bc1c36e2411d3cb1b700d480358c41f2dc6b579c24b530` |
| `PB-robot-roll-world-ordered4` | `robot.normal.png` | 149,714 | `e31be35d8e966d9065ffb47d209cc0bb42e5f740cb405bdef035ac4a8e57506e` |
| `PB-robot-roll-world-ordered4` | `robot.png` | 35,116 | `5434f17866eb35ae20d71c89d30a85ddbef95bca542922d0fa98595fe22600a3` |
| `PB-robot-roll-camera-ordered4` | `robot.Walking.gif` | 150,132 | `b178a169320f37eba5512e46cc7cfb00c202a574f937c844b7a807c752b6fd15` |
| `PB-robot-roll-camera-ordered4` | `robot.json` | 9,515 | `42d72d92da670ebda436c90988918ad51c1084267cbc8ca67634643c09bcbfac` |
| `PB-robot-roll-camera-ordered4` | `robot.normal.png` | 149,714 | `e31be35d8e966d9065ffb47d209cc0bb42e5f740cb405bdef035ac4a8e57506e` |
| `PB-robot-roll-camera-ordered4` | `robot.png` | 34,969 | `b34eabf2675e43de15f9b3f43b25790b46c10937f9f216b5eaac1d8ef9d2dd4c` |
| `PB-robot-long-ramp` | `robot.Walking.gif` | 210,448 | `39c47f11b09a77df5db122b0eac57ff8765d8a035fe1f72f919b7fe09a3783d8` |
| `PB-robot-long-ramp` | `robot.json` | 9,895 | `5927c7d61301fd0362a2d7809ccee2a36ea2e80a53ad19e39d36e0b9a7cefdec` |
| `PB-robot-long-ramp` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-long-ramp` | `robot.png` | 54,860 | `400cea2c7a26807e07fae2b2e182ea0947a18da0ae7b828574cd6b61b861f071` |
| `PB-robot-long-ramp-ordered4` | `robot.Walking.gif` | 248,201 | `f363d1ecd9e1eeb0479f1c297bd6824c5ee864fc91e7d4093b36ff8da33ca160` |
| `PB-robot-long-ramp-ordered4` | `robot.json` | 9,900 | `767647286468e5524341499ba80b3e90cf5accd7d69136d9d0283cc6ecdab697` |
| `PB-robot-long-ramp-ordered4` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-long-ramp-ordered4` | `robot.png` | 61,958 | `0b89d63d6843b76cf246607d31e35d79e9f3c02cfb7aad4b2069a323097ab508` |
| `PB-robot-long-brightness-snap-ramp-ordered4` | `robot.Walking.gif` | 230,362 | `eadeda0582f9335cff4e0ecfff161deac608dd7a4956722b9963686d188ec261` |
| `PB-robot-long-brightness-snap-ramp-ordered4` | `robot.json` | 9,907 | `0264e4be2c4240436995b74f26d79f12677ac6f312a7ade632cfe6f3d0de6c2d` |
| `PB-robot-long-brightness-snap-ramp-ordered4` | `robot.normal.png` | 166,132 | `41c08f20f0c38c2cc004180a3580674d249dc00f2063ee47a78bcf76f921b485` |
| `PB-robot-long-brightness-snap-ramp-ordered4` | `robot.png` | 54,852 | `b2f077b8153d607b8e08eff33a252d8447ef48af629984ca7da09c2297323d1a` |
| `PB-robot-ramp-ordered4-soft` | `robot.Walking.gif` | 282,045 | `81e8234f1a98eb2ce1d88943bbb8a6e894844d6d48957fed473e53ee842771e7` |
| `PB-robot-ramp-ordered4-soft` | `robot.json` | 9,512 | `0f075d862649f5aff1397e2f0cad1833024ab9bfb83593a7f75ae92c6cc3b35a` |
| `PB-robot-ramp-ordered4-soft` | `robot.normal.png` | 196,509 | `e76fc9cfb4b734baa2de4f9cf7ca83d6e9ce837f76bda367477d4da3ceac280f` |
| `PB-robot-ramp-ordered4-soft` | `robot.png` | 76,953 | `bb9a3a1e258a07a1d98323116aa15de0e3acf90a8c4df37de019233ff18d7ea5` |
| `PB-shrub-ramp-strong` | `shrub.Sway.gif` | 51,450 | `282c8fdaa2a4c9206ce28bfddb97f958653956596d157ef3507e31941864365b` |
| `PB-shrub-ramp-strong` | `shrub.json` | 8,680 | `74984b6679bddbdce6cd4ec7785ee7e0d4c0d692bbaea9641ca6491e484a428e` |
| `PB-shrub-ramp-strong` | `shrub.normal.png` | 65,536 | `367cbdc3a57be0d7956b2cb3530157864b297bddf5cb8c5d11a6890ef2c900b8` |
| `PB-shrub-ramp-strong` | `shrub.png` | 11,998 | `130a2336c19d9038662003d10c95c1882ebb4a312985cbe96ac738908cd5fe04` |
| `PB-shrub-ramp-mode-ordered4` | `shrub.Sway.gif` | 57,529 | `8c862ad0b1a80265684b1820dcccb83105532cd8eb9cf67beecc446f269609f4` |
| `PB-shrub-ramp-mode-ordered4` | `shrub.json` | 8,684 | `34c4c76fbf4e5763581c5a538903282426a1df233426cbfd6ff6af72cab287f9` |
| `PB-shrub-ramp-mode-ordered4` | `shrub.normal.png` | 65,536 | `367cbdc3a57be0d7956b2cb3530157864b297bddf5cb8c5d11a6890ef2c900b8` |
| `PB-shrub-ramp-mode-ordered4` | `shrub.png` | 13,335 | `eec42f3f9d1a8ecffaaec3dedd973b403a2fd57fe3fac0515ef0d2971f3b1585` |
| `PB-shrub-ramp-ordered4-soft` | `shrub.Sway.gif` | 174,598 | `4a11b1afc2f599c73befe44713125d7af0a0b7d1d36d2536660d2f93f06bc842` |
| `PB-shrub-ramp-ordered4-soft` | `shrub.json` | 8,685 | `f242383582a4fe3b0a3c51830e81d356407dbb3408137ec8e681fc8d01fb1f39` |
| `PB-shrub-ramp-ordered4-soft` | `shrub.normal.png` | 97,502 | `d6e9d7bf7bbed90d6184e966de35868d17ddf46eda1ccc1b6db564fd29262601` |
| `PB-shrub-ramp-ordered4-soft` | `shrub.png` | 45,996 | `c43c24ca4d4baf374f05155319ac73a1d21c76f965195c5640f1810c70aea0ca` |
| `PB-shrub-brightness-snap-palette-ordered4` | `shrub.Sway.gif` | 71,210 | `510bb21e55ec3d628fdfff46651d9bdace6d22c209a325a1e794fe844c8ee596` |
| `PB-shrub-brightness-snap-palette-ordered4` | `shrub.json` | 8,695 | `8e95e6425ef56c68fb6c0983e4bc8f1c58f78def56eb318455a6c154680aee32` |
| `PB-shrub-brightness-snap-palette-ordered4` | `shrub.normal.png` | 65,536 | `367cbdc3a57be0d7956b2cb3530157864b297bddf5cb8c5d11a6890ef2c900b8` |
| `PB-shrub-brightness-snap-palette-ordered4` | `shrub.png` | 16,428 | `dc37a678180336d2880666d2bdb498f492c02620903249196b500dc6dda138ae` |
| `PB-shrub-both` | `shrub.Sway.gif` | 105,031 | `882feb97ddbb2dc61c8f116d5f52034275ef753337bebd8984f733a6c20c4a04` |
| `PB-shrub-both` | `shrub.json` | 8,680 | `679993f22ed1ae4c95da9d5241200314c4cea66369ecf0b6208479f8cf2b11f0` |
| `PB-shrub-both` | `shrub.normal.png` | 65,536 | `367cbdc3a57be0d7956b2cb3530157864b297bddf5cb8c5d11a6890ef2c900b8` |
| `PB-shrub-both` | `shrub.png` | 22,812 | `5bb6d52713aead7c265e6529becfccf0827bcce16882123cf835a1b00f2c3764` |
| `PB-shrub-neither` | `shrub.Sway.gif` | 46,569 | `15447e83da78447a041899d69083fb728be23e5f8c10eac6f348f97c50d450c5` |
| `PB-shrub-neither` | `shrub.json` | 8,683 | `67c5173756d4376a6ff9f309c9b2a45376d35bd6de8b077680e5d798e83542a4` |
| `PB-shrub-neither` | `shrub.normal.png` | 65,536 | `367cbdc3a57be0d7956b2cb3530157864b297bddf5cb8c5d11a6890ef2c900b8` |
| `PB-shrub-neither` | `shrub.png` | 10,302 | `a04199a9ccc76a9101e69532f46f7c6c7bd4cb90ba5d96a366c0d4992fd891f5` |
| `PB-chest-ramp-strong-hard` | `chest.Open.gif` | 176,740 | `fd82064af9ba52c9f627508aba14ed1c51e51666d9192e94aa86bebe0a932559` |
| `PB-chest-ramp-strong-hard` | `chest.json` | 10,805 | `cf17e5fb854ff730269086328fb856ade3d9795c640ac94f4f819d5638aec3c0` |
| `PB-chest-ramp-strong-hard` | `chest.normal.png` | 10,533 | `fadf630b59ed46fb2b17720c04385f3c537ea7e2222b817587ba1ea32f957cfa` |
| `PB-chest-ramp-strong-hard` | `chest.png` | 13,293 | `3b33e6ee670685e5c1ebee231ead6e4e2fd9ce5fa9c3507e95305508faaedf74` |
| `PB-chest-ramp-ordered4-soft` | `chest.Open.gif` | 306,782 | `fe6af7c5da26ed6ae75dde286c5abd902b4114c9602c99117dc4a25be19455fa` |
| `PB-chest-ramp-ordered4-soft` | `chest.json` | 10,810 | `63b552fc469800622989ab38aae0b8466c428866d69d7e764c889da30cd85194` |
| `PB-chest-ramp-ordered4-soft` | `chest.normal.png` | 11,223 | `303844447946d72c7a9390a8a80f5216725ab31f9e9b84f76cf60f38eb3b6e01` |
| `PB-chest-ramp-ordered4-soft` | `chest.png` | 28,691 | `06ce3fd3cc65712185b39a482da8fe01ef40eddbb3f4d50c549af0383673f4d2` |
| `PB-chest-brightness-snap-ramp-ordered4-soft` | `chest.Open.gif` | 555,372 | `e34e4c51b5d94981f5f1589a759456820d4723a1d4bacff3a5656bc9e39f4295` |
| `PB-chest-brightness-snap-ramp-ordered4-soft` | `chest.json` | 10,817 | `b9927f9852667a881b62e22f72d1e0802bc09d608ee166e60727311cb6889678` |
| `PB-chest-brightness-snap-ramp-ordered4-soft` | `chest.normal.png` | 11,223 | `303844447946d72c7a9390a8a80f5216725ab31f9e9b84f76cf60f38eb3b6e01` |
| `PB-chest-brightness-snap-ramp-ordered4-soft` | `chest.png` | 54,507 | `b48f68fdf5baa960d68d2012432ffcc6db5fe0d8d8960fb7cd5a9a1f9a9a3c16` |
| `PB-chest-both-snap-palette-ordered4-soft` | `chest.Open.gif` | 323,294 | `0a013545aa79c46fbff1cb98657389b6b6bcbbfaf540a8ea6c30cd9207ea90a5` |
| `PB-chest-both-snap-palette-ordered4-soft` | `chest.json` | 10,814 | `4ba7eaeefd4875dab8335ec1af4e4066d6b08f823ecdecab3a76964bcca2d675` |
| `PB-chest-both-snap-palette-ordered4-soft` | `chest.normal.png` | 11,223 | `303844447946d72c7a9390a8a80f5216725ab31f9e9b84f76cf60f38eb3b6e01` |
| `PB-chest-both-snap-palette-ordered4-soft` | `chest.png` | 32,693 | `9115ec585dcbbfdfa9bd2a675541ca05376bba98a36361f30ed7a2f8b025905b` |
| `PB-chest-glow-neither-ramp-ordered4-soft` | `chest.Open.gif` | 330,134 | `e91e48ad886c0fab3d1e947f664bf32304977b3f1d63053037b0f4e3cb11c3f3` |
| `PB-chest-glow-neither-ramp-ordered4-soft` | `chest.json` | 10,887 | `4c20b92f145216a63764cdcd99ef6492bc1f269b354a8dd1e0a81a38809871de` |
| `PB-chest-glow-neither-ramp-ordered4-soft` | `chest.normal.png` | 11,223 | `303844447946d72c7a9390a8a80f5216725ab31f9e9b84f76cf60f38eb3b6e01` |
| `PB-chest-glow-neither-ramp-ordered4-soft` | `chest.png` | 32,252 | `64b3a92087edfa5af0239b7af4de8c1726997b8348f7dc031aba429e84520cba` |
| `PB-chest-neither-soft` | `chest.Open.gif` | 134,069 | `8a4f572f3246effe914a0d19525b88290aeba977c0bf5b2beb1c9fb86389feac` |
| `PB-chest-neither-soft` | `chest.json` | 10,808 | `75baba3a8611e04362abe40ce36451cb8b5e693224a4c547d55bb22dd8a82922` |
| `PB-chest-neither-soft` | `chest.normal.png` | 11,223 | `303844447946d72c7a9390a8a80f5216725ab31f9e9b84f76cf60f38eb3b6e01` |
| `PB-chest-neither-soft` | `chest.png` | 9,460 | `4b0c44a43e6a1083f72d734d6a32d1dbe4063d2f1bd4b00ced42de3dcd0657f8` |
| `A-live-0-shrub` | `shrub-lit.Sway.gif` | 1,323,536 | `8004654971786e620c50ef7a7f25334ffeeac323dff9c6efeb60ac3a3991dab1` |
| `A-live-0-shrub` | `shrub.Sway.gif` | 506,640 | `9d03ab5211feee01352d8182d8b303b9a1a8be7e208fe6bce63b14464f62f452` |
| `A-live-0-shrub` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `A-live-0-shrub` | `shrub.json` | 19,137 | `fcad439ce112c7f731ba10ffe195033bc4687042f4c033f3bdb977b341e5afae` |
| `A-live-0-shrub` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `A-live-0-shrub` | `shrub.png` | 138,770 | `6306607f332d49ebd03a6d9c1e6534794fde81899f83df6764e58f4bcd19d537` |
| `A-live-0-robot` | `robot-lit.Walking.gif` | 1,898,026 | `089d8b46814818097e0cd2b9e6a07901a758789d928263b92aa3f0388412a06d` |
| `A-live-0-robot` | `robot.Walking.gif` | 680,048 | `e607e8d9a842b8a4296326f8f7503e41f771094cb10d58cc7e3208d736d4313e` |
| `A-live-0-robot` | `robot.depth.png` | 432,205 | `76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2` |
| `A-live-0-robot` | `robot.json` | 23,712 | `fbab65bb7ede5ddabcd5745190addb8658a60335bb26329a5ead38e72e3f3315` |
| `A-live-0-robot` | `robot.normal.png` | 818,004 | `8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0` |
| `A-live-0-robot` | `robot.png` | 190,383 | `d89a5bb27742674e5051bbb8bf81df4834484b2d41f67b8d9c36f4496e5424a8` |
| `A-live-sky20-shrub` | `shrub-lit.Sway.gif` | 1,331,590 | `3b04fa1ec52998812d38bef8fb50174ac93bb1658eb0dda6d91c38bc565f0f62` |
| `A-live-sky20-shrub` | `shrub.Sway.gif` | 512,605 | `bfc646eed13a9cd5809e62ee27305119d09383eab601e3af46e1fd0863cb8dc3` |
| `A-live-sky20-shrub` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `A-live-sky20-shrub` | `shrub.json` | 19,137 | `6f5feff6125618561b5251218fdbb12d3ae4004dbc6831cb2d56753383d09da0` |
| `A-live-sky20-shrub` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `A-live-sky20-shrub` | `shrub.png` | 138,783 | `aba537316734b36cb6f108af6862a5bad982897117ebdbfb585c1edbabfd363c` |
| `A-live-sky20-robot` | `robot-lit.Walking.gif` | 1,837,386 | `c0b2c3bd765c577df2c79b9be185280db55b76ca285e29d148539a281aa0cd0e` |
| `A-live-sky20-robot` | `robot.Walking.gif` | 608,689 | `1e3a8af357ee863d62a6ef25d90a9a3aaf2186f4b69bb46ab90e22ce39dd9d90` |
| `A-live-sky20-robot` | `robot.depth.png` | 432,205 | `76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2` |
| `A-live-sky20-robot` | `robot.json` | 23,712 | `a1d92e8903a9bf0a527cd2975d350db0a1c8ee52ab25f29026d2823db299fee4` |
| `A-live-sky20-robot` | `robot.normal.png` | 818,004 | `8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0` |
| `A-live-sky20-robot` | `robot.png` | 168,058 | `a8db5e320ccebbd59b2ba2a008cf2ca2026d119728d8483b73de1d20c2e5200a` |
| `A-live-sky40-shrub` | `shrub-lit.Sway.gif` | 1,307,250 | `9cffea316cc074b926d05b02a819bf45992d876df3e732548199160ee57fffff` |
| `A-live-sky40-shrub` | `shrub.Sway.gif` | 481,251 | `9b45830de5be123d515ca4dd574065e4f1528bfe4d3d8af3bcd42c0c7068c13a` |
| `A-live-sky40-shrub` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `A-live-sky40-shrub` | `shrub.json` | 19,137 | `aa888d5078dd46a64ec77a2625d4a64ce461c5466508cf5af42b6135395686a4` |
| `A-live-sky40-shrub` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `A-live-sky40-shrub` | `shrub.png` | 128,225 | `97261c74ff820ea18ea6a45afcc2b748f370f496cf65d7336837f230bcc156b6` |
| `A-live-sky40-robot` | `robot-lit.Walking.gif` | 1,807,674 | `fe798b623c862b7a670b15eb6e1320373269388bb1cdd864c40ec32c1711e08f` |
| `A-live-sky40-robot` | `robot.Walking.gif` | 553,667 | `9a8dafd41625e354b58a58d03a6f00473efbad4cf42b82d15fade1773a826a58` |
| `A-live-sky40-robot` | `robot.depth.png` | 432,205 | `76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2` |
| `A-live-sky40-robot` | `robot.json` | 23,712 | `010029590fd189460eed32c95bcae56231d9bb3cff5ccf12f6abab10e30dcb1c` |
| `A-live-sky40-robot` | `robot.normal.png` | 818,004 | `8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0` |
| `A-live-sky40-robot` | `robot.png` | 149,539 | `526f5178a22344e348e546afeb3053286fed30180869e9bc0f202087c6d0ec12` |
| `A-live-skyw30-shrub` | `shrub-lit.Sway.gif` | 1,359,797 | `95b34d4f9883eba4d58433a9d6dad3ad4e3d793fb5a1c6fe7ee6648122662c84` |
| `A-live-skyw30-shrub` | `shrub.Sway.gif` | 536,919 | `04b870762f2c2ea0d80529c8415496151c4d0e09ef5b673b02fbe64b6ecb5444` |
| `A-live-skyw30-shrub` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `A-live-skyw30-shrub` | `shrub.json` | 19,136 | `24a16d0ea837cedc2d5593f7d0fde8bcd0ac647d955f2df4d7da5bd12023d7c3` |
| `A-live-skyw30-shrub` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `A-live-skyw30-shrub` | `shrub.png` | 143,700 | `f8a890dc9cf002f00569c508acf13e7b9b2a2b719b4bc8a4d1b34a1848780ff5` |
| `A-live-skyw30-robot` | `robot-lit.Walking.gif` | 1,842,251 | `5438f83f9290521c3bc7d8a86623dac40b26cd69cb8025eda6a9e3014bda9fe0` |
| `A-live-skyw30-robot` | `robot.Walking.gif` | 615,920 | `ce753b7829aff084a153dcda46f48634e24c795cfa327a97e6f83336f883647f` |
| `A-live-skyw30-robot` | `robot.depth.png` | 432,205 | `76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2` |
| `A-live-skyw30-robot` | `robot.json` | 23,711 | `2423341d8b91840c127cd5a963710b058eb08b8b88e79faa1b4fa6f77dcc2169` |
| `A-live-skyw30-robot` | `robot.normal.png` | 818,004 | `8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0` |
| `A-live-skyw30-robot` | `robot.png` | 168,943 | `67c6b376e4b78c04df785528a1256de30f5a3f5c61aa6f5b10a3c68b91a0729a` |
| `A-live-dith4-shrub` | `shrub-lit.Sway.gif` | 1,339,528 | `c6877742acc346d4f81878327b5d0202158d539aeadf6e44d63cc6f2ed41bae3` |
| `A-live-dith4-shrub` | `shrub.Sway.gif` | 519,562 | `d8e65890a9235736f4dc88e104a100d13ca371b341848c1578c15ceab9a3026b` |
| `A-live-dith4-shrub` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `A-live-dith4-shrub` | `shrub.json` | 19,142 | `28a2eaa094078fa6df0933a888d1b871708793ce709cb55ec3db0b5d4439a147` |
| `A-live-dith4-shrub` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `A-live-dith4-shrub` | `shrub.png` | 143,302 | `76a7d7d9eefc34e7e3691ccd85045d676886ac04f7f08a5076cb5c336856f646` |
| `A-live-dith4-robot` | `robot-lit.Walking.gif` | 2,117,180 | `21769fee86ded437288594ae2cba0642856e3ab54392fb7474d086cdd6e4eb95` |
| `A-live-dith4-robot` | `robot.Walking.gif` | 799,250 | `8e4d494939696455e80c089edda56a967708db2fbf32abb8af59d937e0fb11ac` |
| `A-live-dith4-robot` | `robot.depth.png` | 432,205 | `76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2` |
| `A-live-dith4-robot` | `robot.json` | 23,717 | `aeeaba4b7ea38614025b3223d6e2bdafd82aedbeea0fa448308b35ad4693e144` |
| `A-live-dith4-robot` | `robot.normal.png` | 818,004 | `8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0` |
| `A-live-dith4-robot` | `robot.png` | 211,820 | `5b59a9c4f74cbf345314aec3ba02f78e984d17fd02f155903ad497af71e0ddca` |
| `A-live-sky20-dith4-shrub` | `shrub-lit.Sway.gif` | 1,375,285 | `87232941d0d3e265072cd6055314b1259480d3bed89dc12857420026eb41affb` |
| `A-live-sky20-dith4-shrub` | `shrub.Sway.gif` | 539,302 | `65808595a59366244eed660409a8c6c8541097097b4113373b82c3518adba55a` |
| `A-live-sky20-dith4-shrub` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `A-live-sky20-dith4-shrub` | `shrub.json` | 19,142 | `12b459e9150afb0de1304adc5a16ee67ff76f205ae2a7801697fcd2dcd54d913` |
| `A-live-sky20-dith4-shrub` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `A-live-sky20-dith4-shrub` | `shrub.png` | 144,261 | `27be9ee0eb5651ec304d565a08277f3460ada7fe0cc3a8f8f1952dffb08179fc` |
| `A-live-sky20-dith4-robot` | `robot-lit.Walking.gif` | 2,126,207 | `ef4fbf8db72f7e5674101f0d9de3aa31c2e1240b979753a227757787b06ffc96` |
| `A-live-sky20-dith4-robot` | `robot.Walking.gif` | 794,398 | `ed2a5680db427b97f712b977a346de2aed63e87e282b26b9e1831c068363b127` |
| `A-live-sky20-dith4-robot` | `robot.depth.png` | 432,205 | `76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2` |
| `A-live-sky20-dith4-robot` | `robot.json` | 23,717 | `fceac441b23b0202ca1ebd34e1b6f1697cf669d21a58414418276438555a42a7` |
| `A-live-sky20-dith4-robot` | `robot.normal.png` | 818,004 | `8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0` |
| `A-live-sky20-dith4-robot` | `robot.png` | 205,605 | `7a25a3fe4c167cebccd6bd3fe856609d1869bba4e9ed1ac3edfa7d73c659d199` |
| `A-live-0-chest` | `chest-lit.Open.gif` | 3,416,392 | `9cf8f373572303039da43a58b92037bba1ead3cd4b1d793fe5ecdc19fad9554b` |
| `A-live-0-chest` | `chest.Open.gif` | 1,723,627 | `a22dc4214e70842c6bd5142c31656512043261778653a953a59719532a73c8d0` |
| `A-live-0-chest` | `chest.depth.png` | 271,410 | `d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26` |
| `A-live-0-chest` | `chest.json` | 34,250 | `a58e8358790535b905979b9eccf088e17029d1a0e6e80d044e65a2d31aad1d2b` |
| `A-live-0-chest` | `chest.normal.png` | 363,340 | `bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36` |
| `A-live-0-chest` | `chest.png` | 167,967 | `ed9490c5062b542b915e625cb2498c1160a94cbc1e92de409228c2f5f78a70b4` |
| `A-live-sky20-dith4-chest` | `chest-lit.Open.gif` | 4,337,599 | `9d1999ca95276baa48452f8289b10dded1cedf4c83421086fb33dbb4f5517763` |
| `A-live-sky20-dith4-chest` | `chest.Open.gif` | 2,315,536 | `deeb088f685f2351ae0afe94e1711f838650162d35b1886a70fa0a70dc01547d` |
| `A-live-sky20-dith4-chest` | `chest.depth.png` | 271,410 | `d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26` |
| `A-live-sky20-dith4-chest` | `chest.json` | 34,255 | `1d94ddf3cb48ac5bdc75461c812330de0c10e5939b2fd83912c24c379deba8d2` |
| `A-live-sky20-dith4-chest` | `chest.normal.png` | 363,340 | `bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36` |
| `A-live-sky20-dith4-chest` | `chest.png` | 219,506 | `6ee7c5e693a72ce72ec05ddea9459d36a9047781c8310d19d1cd34b688573cae` |
| `PB-robot-roll25-camera-ordered4` | `robot.Walking.gif` | 75,953 | `314c3f08f4a09b41a6ac6800896e183f8872d29d1cf26d961698c991b115fb76` |
| `PB-robot-roll25-camera-ordered4` | `robot.json` | 9,513 | `81571a1ec72ceedd9998ec44c4d25dc4d2b4284610b3b71ba90dce3d6c4f6190` |
| `PB-robot-roll25-camera-ordered4` | `robot.normal.png` | 72,452 | `c56c96be6db463f970090fd146b376d6d4e6c85029128df11fb4fb2a41d105b1` |
| `PB-robot-roll25-camera-ordered4` | `robot.png` | 17,503 | `abe5a29f3141855afe25f4772035eb072a67751482c28bbba367d6c08247805a` |
| `PB-robot-roll25-world-ordered4` | `robot.Walking.gif` | 75,058 | `7dfbb4f63b2f9028d06f4ed85dbf5d8f13771f09f17f6bcd5c07234aaf6908e6` |
| `PB-robot-roll25-world-ordered4` | `robot.json` | 9,512 | `2b103340221195d4f493cf8eca5c01d1f8baacdd2270aa44dbd534bf838b564e` |
| `PB-robot-roll25-world-ordered4` | `robot.normal.png` | 72,452 | `c56c96be6db463f970090fd146b376d6d4e6c85029128df11fb4fb2a41d105b1` |
| `PB-robot-roll25-world-ordered4` | `robot.png` | 17,085 | `9a46ee6732ff355ede295aacbf692afab4907b252e9f16c9ea97a2726650382b` |

The pre-arc tool's runs of the default look (`runs-prearc/`):

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `A-live-0-shrub` | `shrub-lit.Sway.gif` | 1,323,536 | `8004654971786e620c50ef7a7f25334ffeeac323dff9c6efeb60ac3a3991dab1` |
| `A-live-0-shrub` | `shrub.Sway.gif` | 506,640 | `9d03ab5211feee01352d8182d8b303b9a1a8be7e208fe6bce63b14464f62f452` |
| `A-live-0-shrub` | `shrub.depth.png` | 407,004 | `a1b10e37972614d34653e9de36380899f875858e8ce7734d71f7b43417031ad9` |
| `A-live-0-shrub` | `shrub.json` | 18,608 | `7be5ca2eae15d3dcf31a9bfa3ecec4dbe37d4324f3fd634fcc518dc66213b686` |
| `A-live-0-shrub` | `shrub.normal.png` | 615,227 | `d01e136f8435ebd1af6a4a08fbb0c9bca12fe92fd6db189523bd837bbe98e2d5` |
| `A-live-0-shrub` | `shrub.png` | 138,770 | `6306607f332d49ebd03a6d9c1e6534794fde81899f83df6764e58f4bcd19d537` |
| `A-live-0-robot` | `robot-lit.Walking.gif` | 1,898,026 | `089d8b46814818097e0cd2b9e6a07901a758789d928263b92aa3f0388412a06d` |
| `A-live-0-robot` | `robot.Walking.gif` | 680,048 | `e607e8d9a842b8a4296326f8f7503e41f771094cb10d58cc7e3208d736d4313e` |
| `A-live-0-robot` | `robot.depth.png` | 432,205 | `76dc33fddf9f1baf3c0c0c885c16ef819c371f149184bf556a02b5306d1bb2f2` |
| `A-live-0-robot` | `robot.json` | 23,183 | `de6edc442a2fee488ccc867ced10680f28776805092b3624b1d4eae15128e253` |
| `A-live-0-robot` | `robot.normal.png` | 818,004 | `8e2e9c005854ea045e9cd9e73a43a33ded709423f7f6754b4e33146dd1ed55b0` |
| `A-live-0-robot` | `robot.png` | 190,383 | `d89a5bb27742674e5051bbb8bf81df4834484b2d41f67b8d9c36f4496e5424a8` |
| `A-live-0-chest` | `chest-lit.Open.gif` | 3,416,392 | `9cf8f373572303039da43a58b92037bba1ead3cd4b1d793fe5ecdc19fad9554b` |
| `A-live-0-chest` | `chest.Open.gif` | 1,723,627 | `a22dc4214e70842c6bd5142c31656512043261778653a953a59719532a73c8d0` |
| `A-live-0-chest` | `chest.depth.png` | 271,410 | `d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26` |
| `A-live-0-chest` | `chest.json` | 33,721 | `b0f9de829c3320cedd8523ffd45e3e729ff5c49efb70c87e93d972972a016777` |
| `A-live-0-chest` | `chest.normal.png` | 363,340 | `bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36` |
| `A-live-0-chest` | `chest.png` | 167,967 | `ed9490c5062b542b915e625cb2498c1160a94cbc1e92de409228c2f5f78a70b4` |
