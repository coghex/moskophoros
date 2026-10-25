# EXP-6b image byte-identity evidence (issue #160)

Local evidence for the activation of the configurable export, recorded on
2026-10-24 as export design D-3 and the owner's evidence-placement
clarification require. It records byte identity of the default command's
images and metadata, not owner visual acceptance (EXP-7). Models, renders and
logs stay outside the repository.

## Identity

- Base: `41c89c7e924b18c330f670f4b26b8e7a5e33954d` (master, including the
  EXP-6a switch to `moskophoros.export/1`). Head: `6e04ab32572066becf3b52d559094afabd1b167b`, the pull
  request's last change to `src/`; later commits change only tests and
  documentation.
- Model: generated once from `tests/blender/test_whole_command.py::rigged_model`
  with `GlbWriter`, then used unchanged for both sides. SHA-256
  `0e84337243b491acc81389ce62916c9673803e23344933d1aa59b9250b44a81c`, the same
  model the EXP-6a record names.
- Generator at both sides: moskophoros 0.1.0, Python 3.14.8, NumPy 2.5.3,
  Pillow 12.3.0, Blender 5.2.2 LTS at `/opt/homebrew/bin/blender`, renderer
  `cycles`; each side in its own virtual environment from the same
  `requirements.lock`, the base from a clean `git archive` of the base commit.
- Configuration: `--no-user-config` on every run and an empty temporary
  `$XDG_CONFIG_HOME` and `$HOME`, so no live owner file affects either side.
  Separate output roots per side and per invocation.
- Blender ran under `lockf ~/.local/state/project-manager/moskophoros/blender.lock`.

## Model generation

Run once, from the head worktree with its virtual environment, before either
side rendered:

```python
import sys
from pathlib import Path

sys.path[:0] = ["tests", "tests/blender"]
from test_whole_command import rigged_model

rigged_model(Path("export-6b/model"))   # writes hero.glb
```

## Commands as run

Base (`out-base/default` and `out-base/maps`):

```sh
/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/base-src/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/model/hero.glb /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/out-base/default/hero.png
/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/base-src/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack --depth --light 30,40,50 /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/model/hero.glb /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/out-base/maps/hero.png
```

Head (`out-head/default` and `out-head/maps`):

```sh
/Users/vincentcoghlan/worktrees/coghex/moskophoros/issue-160-activate-directory-exports/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/model/hero.glb /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/out-head/default/hero.png
/Users/vincentcoghlan/worktrees/coghex/moskophoros/issue-160-activate-directory-exports/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack --depth --light 30,40,50 /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/model/hero.glb /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-6b/out-head/maps/hero.png
```

The fixed render overrides follow the existing generated-model baseline
(`FAST` and `SHEET` in `tests/blender/test_whole_command.py`), `slide` is
excluded, the legacy output basename `hero` is the same on both sides, and the
export settings are at their defaults.

## Per-file SHA-256, base and head

Every colour, normal and depth PNG and every flat and lit GIF is identical, and
so is each run's `hero.json`: the default `moskophoros.export/1` manifest bytes
and fingerprint (`sha256:75f9eea6…e95cf` for the plain run, `sha256:09cfb356…3e050`
with depth and the light) did not change at this activation, as the contract
requires (the schema changed once, at EXP-6a). The image and manifest hashes also equal the
EXP-6a record's head hashes.

| File | Base SHA-256 | Head SHA-256 | Result |
|---|---|---|---|
| `default/hero.attack.gif` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | identical |
| `default/hero.json` | `9d5e9166b611db2954498bacfe19636232cb008e44c1c7a992a65a7681977f3a` | `9d5e9166b611db2954498bacfe19636232cb008e44c1c7a992a65a7681977f3a` | identical |
| `default/hero.normal.png` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | identical |
| `default/hero.png` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | identical |
| `default/hero.walk.gif` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | identical |
| `maps/hero-lit.attack.gif` | `f50a43fd32e90bc2008c3c1e557e9160693c90ca2ff558acb522c10cc4abc444` | `f50a43fd32e90bc2008c3c1e557e9160693c90ca2ff558acb522c10cc4abc444` | identical |
| `maps/hero-lit.walk.gif` | `cededac3b1ada093f5a3e7e6a2b35d56768cbc0a9d2bba064f682e32fb6165cc` | `cededac3b1ada093f5a3e7e6a2b35d56768cbc0a9d2bba064f682e32fb6165cc` | identical |
| `maps/hero.attack.gif` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | identical |
| `maps/hero.depth.png` | `c4900e1bc398343b8d11c69c41ea22d7b0765696c1b19d734cb562cff9c611c8` | `c4900e1bc398343b8d11c69c41ea22d7b0765696c1b19d734cb562cff9c611c8` | identical |
| `maps/hero.json` | `41e58365feff6d7829c78cba25a4947279c65ebfc951c068f642744a126c24be` | `41e58365feff6d7829c78cba25a4947279c65ebfc951c068f642744a126c24be` | identical |
| `maps/hero.normal.png` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | identical |
| `maps/hero.png` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | identical |
| `maps/hero.walk.gif` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | identical |

## Viewing the new output

The new directory output is not part of the comparison above; it has no
earlier form. To look at it (frame folders, padded atlases, the maps outside the
colour tree and stored-view previews), on the same generated model:

```sh
.venv/bin/moskophoros --config look.yaml --blender /opt/homebrew/bin/blender --supersample 2 --cell 32x32 --clip walk --clip attack --once attack export-6b/model/hero.glb --output-dir export-6b/owner-view/out
```

with `look.yaml`:

```yaml
stored_directions: [0, 4, 3, 2, 1]
mirrors: {7: 1, 6: 2, 5: 3}
normals: true
depth: true
light:
  position: [30, 40, 50]
export:
  formats: [frames, atlases]
  atlas_padding: 1
  frame_path: animations{map}/{clip}/{direction}/frame_{frame:03}.png
clips:
  walk: {frames: 6, fps: 8}
  attack: {frames: 4, fps: 6}
```

It writes 161 files under the output directory: colour frames under
`animations/`, normals under `animations.normal/` and depth under
`animations.depth/` (five stored views each, mirrors added no file), padded
`atlases/<clip>.png` with their maps, flat and lit previews as
`previews/<clip>.gif` and `previews/<clip>.lit.gif`, and `manifest.json`. This
is a technical check of the format, not visual acceptance.
