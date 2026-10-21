# Settings acceptance

This records the owner's acceptance of the settings arc, following
[the settings design](../../designs/settings_design.md) and vision V-12. The arc
is epic #83. Its slices were delivered with #82 (PR #88), #84 (PR #89), #85
(PR #90), #86 (PR #91) and #87 (PR #92), and the last one merged at
`05fd2db`.

## Verdict

**Accepted by the owner on 2026-10-13**, typed directly in the moskophoros
manager's terminal. The manager had asked for a yes or no on "Accept the
settings work and close epic #83", and the owner answered:

> "yes to 1-3"

Item 1 was the settings acceptance and the closure of #83. Items 2 and 3 were
the closures of #78, and of epics #3 and #24.

The verdict covers what the owner reviewed on 2026-10-12 and 2026-10-13,
listed under [Output](#output). It came after the owner's own comments on
those renders:
- R2 "looks better, but flat"; R1 "has too much shading in the creases".
- The look the owner wants lies between the two.
- The animations "all look very smooth".
- Later, "B4 does look good, B1 looks good as well".

Choosing a look is not part of this verdict. The shipped defaults stay as
they are (settings design D-12). The owner's own default look is set in
their user settings file, outside the repository.

## What was checked

- **R1 and R2 from settings files.** The 2026-10-09 R1 and R2 looks were
  rendered from `--config` files alone, with no code edit, at `05fd2db`. Both
  sheets and all four previews were byte-identical to the 2026-10-09 renders,
  which had used hand-edited code. This is the design's "Done when" check.
- **Frame counts.** A global `frames: 8` with `Jump: {frames: 6}` gave
  Walking 8 frames and Jump 6. The command warned that Jump keeps its own
  count.
- **A look between R1 and R2.** One settings file gave occlusion weight 0.5,
  convexity weight 0.25 and shade range 120–220. It was rendered with four
  ramps for Main (B1–B4).

## Input

- **Model:** RobotExpressive, SHA-256
  `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319`. It is
  the same model as [slice 1](slice-1.md#input).
- **Palette:** Vince128, `vince-128.gpl`, SHA-256
  `d7fc8fefc702d2492b72f3c34fe34f59b5b8af109bbde853114ed56cce2ca586`.
- **Library:** the material review's draft, converted to YAML with its
  schema line set to `moskophoros.materials/2`
  (`88de12283d496db4f0464b79163df0f26935ca6b0122426593d92f5d0d6caa59`).
  - B4 used a copy whose Main ramp is palette entries 18, 4 and 5
    (`45afb9a9d54eb627a1e435afe87096b356fb77dcff99373bd04db2adb37daf5c`).
- **Settings files**, in `~/.local/share/moskophoros-acceptance/robotexpressive/`:

  | File | SHA-256 |
  |---|---|
  | `R1.yaml` | `1578633e587c090bcbc1f21cc10ab0c8c21a55d08f7ec2f5bdbba15bffc4d7c7` |
  | `R2.yaml` | `eb6beb2fdb821232c747395d9eddba86d371977fe3f88b1bef08ba44439dbc07` |
  | `frames-check.yaml` | `9ab7a7f7211ab8e64a6fa0a4e518e9d757ac0cc47d5aad9bf663e42572b24cda` |
  | `settings-check-2/blend.yaml` | `1b05094785dfbb4f4655598327c7b3b2da118b1604b75b1f819fa5d258242778` |

- **Command**, run from that directory under the shared Blender lock, with
  `--no-user-config`:

      moskophoros --no-user-config --config <file> --clip Walking --clip Jump --once Jump \
        --cell 48x48 --view iso --directions 8 --palette <vince-128.gpl> \
        --materials <library> RobotExpressive.glb <out>/RobotExpressive.png

  The frame-count check used no library.
- **Tools:** Blender 5.2.2. moskophoros was built from `05fd2db`.

## Output

All outputs are under `~/.local/share/moskophoros-acceptance/robotexpressive/`.
None are committed.

| Sheet | SHA-256 |
|---|---|
| `settings-check/R1/RobotExpressive.png` | `d69bf4611338502135f396a343a561084eb628523041424379c73c4ecb401770` |
| `settings-check/R2/RobotExpressive.png` | `59d0a37cbf752123a22aa74cea89341bbcdb5b864142a3f7d658d123d521d67a` |
| `settings-check/frames/RobotExpressive.png` | `a1e6a787f7e6168668dfd6665826fc965a2abdc460835e9f4334caf842a3db95` |
| `settings-check-2/B1/RobotExpressive.png` | `94f89fd97f17a5fc958bb044e6632dcef655a123b90cf11e7e60b99ed4904d7c` |
| `settings-check-2/B4/RobotExpressive.png` | `8d291741d210bdc9cebf50a4e2a0b63480e1e4c2e1a91e5caad95b563cdc766f` |

The owner viewed these through two labelled review pages, which the manager
published privately on 2026-10-12 and 2026-10-13.

## Limitations

- **One correction during the review.** PR #90's instructions predate #86's
  library schema `/2`. The old library was refused with a message naming the
  one-line fix, and that fix was made on a copy.
- **The frame-count render is not a shading comparison.** It used no
  library, so its light comes from Blender's own studio light. An earlier
  version of the review page compared it with R1 and R2, and that was
  corrected.
- **Follow-ups decided during the same review:**
  - #79 was closed: the owner judged Grey and Black "fine either way".
  - The lighting sheet's direction was recorded as material styling D-27.
  - The owner adopted Vince 144 (Vince 128 plus 16 greys) as their working
    palette, in their user settings.
