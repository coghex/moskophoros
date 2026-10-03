# Slice 1 acceptance

This records the owner's acceptance of slice 1, following design §Slice 1 acceptance and vision V-12. It was delivered with #36 and pull request #49.

## Verdict

**Accepted by the owner on 2026-10-03 at 19:25 UTC**, after viewing the sheet and both previews listed below:

> "that is a set of sprite sheets of walking and jumping so that is right i think. i expected the frames to be stiched together vertically, but this is fine, i approve"

The owner's assistant, laz, relayed the verdict in the project chat (`#moskophoros`, message `kemi6bpchrh27yc6g5m4sbw7ds`).

The sheet's current horizontal layout is accepted as designed: one row per clip and direction, frames left to right. The verdict asks for no change of orientation and adds no new requirement.

The verdict is bound to this exact output: pull request #49 at head `4cc01a08cf0c3016a9ea277a258b681dd1e98184`, and the four files whose hashes are listed under [Output](#output).

## Input

The model is the official three.js example model *RobotExpressive*, which the owner chose on 2026-10-03.

- **Source:** https://raw.githubusercontent.com/mrdoob/three.js/f2fff78cb77c540106dc4abb8a01c2260cf370c4/examples/models/gltf/RobotExpressive/RobotExpressive.glb
- **Upstream commit:** `f2fff78cb77c540106dc4abb8a01c2260cf370c4`. The file itself was last changed upstream in `b924f0cad405`.
- **SHA-256:** `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319`, 463,988 bytes.
- **Licence:** CC0 1.0. The model is by Tomás Laulhé ([Quaternius](https://www.patreon.com/quaternius)), with modifications by [Don McCurdy](https://donmccurdy.com/): three facial-expression morph targets, conversion with FBX2GLTF, and duplicate materials removed. The attribution is taken from the upstream README.
- **Clips:** `Walking` loops, 0.958 s long. `Jump` plays once, 0.708 s long.

The model is not committed, in line with AGENTS.md §Files.

## Command

Run from the directory holding the model, with pull request #49's command at the head above:

    moskophoros --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8 RobotExpressive.glb out-temperance/RobotExpressive.png

## Environment

- moskophoros 0.1.0, at head `4cc01a08cf0c3016a9ea277a258b681dd1e98184`
- Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0
- Blender 5.2.2 LTS, with the Workbench renderer and studio light `Default`

## Resolved settings

These are taken from the sheet's JSON.

- **View:** pitch 30°, 8 directions, start angle 0°, orthographic. The preset is recorded as `custom` because `--directions` was given explicitly, as design §Presets specifies. The values are the `iso` preset's own.
- **Capture:** model yaw 0°, 12 fps, supersample 8.
- **Scale and placement:** 39.45430057639541 pixels per meter, auto-fitted to a 256×256 cell. The ground point (0, 0, 0) m lands on cell pixel (128, 222).
- **Root motion:** `error`. Both clips pass the 0.02 m check.
- **Frames:** `Walking` has 11 frames of 87.1 ms, looping. `Jump` has 9 frames of 88.5 ms, one-shot, and its last sample is exactly its end time.
- **Fingerprint:** `sha256:c97f3e7c7c5bcf474f93a82969bced46b12bfc07c53bbc55c81ed6d3a3c370cb`

## Output

The outputs were kept on the owner's Mac, in `~/.local/share/moskophoros-acceptance/robotexpressive/out-temperance/`. Generated sheets and previews are never committed.

| File | Size | SHA-256 |
|---|---|---|
| `RobotExpressive.png` | 2816×4096 RGBA | `17cbce33eefffa7a10b4b6e01d51f3c3aa78e07d1793089b7b8d0562ec38d63a` |
| `RobotExpressive.json` | | `6bcc11880f827236a23066b87b7f221628816955c525ac0cfb760a340742b3c5` |
| `RobotExpressive.Walking.gif` | 8192×1024, 11 frames | `95f4c43fe6b1d414b7063b3a23ab09c2b449dfba015d05dccf23fc8a155995fd` |
| `RobotExpressive.Jump.gif` | 8192×1024, 9 frames | `9d82e36866c5e6baa48ceeed0c8ddb964a0a5be82ce4f0bdb2b154cb75be7382` |

## Owner decisions made during acceptance

Each decision was relayed by laz in the project chat.

- **2026-10-03 14:16 UTC: the input.** Use RobotExpressive at 256×256 cells, in the iso view, in 8 directions, with `Walking` looping and `Death` as the one-shot clip (message `asp4v8yssqvjmzp6wuqudyz9ks`).
- **2026-10-03 14:51 UTC: `Jump` instead of `Death`** (message `we4tmtkcykqh7n4xf9dtdbyqns`).
  - `Death` moves the robot's root 1.01 m across the ground. Under the default `--root-motion error`, that is an input error (design §Root motion), so the owner chose a clip that passes rather than rendering the fall with `--root-motion keep`.
  - The same decision approved a fix: a one-shot clip's last sample is now exactly its end time. Before the fix, floating-point rounding could put it just past the end, failing clips such as `Punch` with a backend error.
- **2026-10-03 19:07 UTC: the bone-parenting fix** (message `39qcaf8t7bmbb5gpe8kxsy4ymn`).
  - The first render was missing the robot's legs. Blender's glTF importer, with its default `BLENDER` bone heuristic, misplaces meshes parented to bones whenever the armature is scaled: by about 0.6 m on this model, whose armature is scaled ×100.
  - The capture now imports with `bone_heuristic="TEMPERANCE"`, which places them as glTF specifies.
  - The accepted render is the first one made with this fix.

## Output errors

**2026-10-03, decided by the owner** (message `jhqfuhytzpwecxvgi57s2jpe7e`): an output that cannot be written, whether on a full disk, without permission or because a rename fails while publishing, exits with code 6 and prints no usage synopsis or traceback. The message names the output and the reason, and says the earlier outputs are kept. Rollback is unchanged: earlier outputs are restored byte for byte, newly placed outputs are removed, and staged files are deleted. design.md §Exit codes records this.

The change touches only error reporting, so the accepted pixels are unaffected.
