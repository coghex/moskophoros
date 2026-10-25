# EXP-6a image byte-identity evidence (issue #159)

Local evidence for the positional switch to `moskophoros.export/1`, recorded on
2026-10-24 as export design D-3 and the owner's evidence-placement
clarification require. It records byte identity of the images, not owner
visual acceptance. Models, renders and logs stay outside the repository.

## Identity

- Base: `4a221025190c41e8df9c618ab6d64978b491f497` (master, before the switch). Head: `528505cbe2d5d2527e6d6600b3a86cf2954ac063` (the pull
  request's last change to `src/`; later commits change only documentation and
  tests).
- Model: generated once from `tests/blender/test_whole_command.py::rigged_model`
  with `GlbWriter`, then used unchanged for both sides. SHA-256
  `0e84337243b491acc81389ce62916c9673803e23344933d1aa59b9250b44a81c`.
- Generator at both sides: moskophoros 0.1.0, Python 3.14.8, NumPy 2.5.3,
  Pillow 12.3.0, Blender 5.2.2 LTS at `/opt/homebrew/bin/blender`, renderer
  `cycles`; each side in its own virtual environment from the same
  `requirements.lock`, the base from a clean `git archive` of the base commit.
- Configuration: `--no-user-config` on every run, so no live owner file
  affects either side. Separate output roots per side and per invocation.
- Blender ran under `lockf ~/.local/state/project-manager/moskophoros/blender.lock`.

## Model generation

Run once, from the head worktree with its virtual environment, before either
side rendered:

```python
import sys
from pathlib import Path

sys.path[:0] = ["tests", "tests/blender"]
from test_whole_command import rigged_model

rigged_model(Path("evidence-159/model"))   # writes hero.glb
```

## Commands as run

Base (`out-base/default` and `out-base/maps`):

```sh
/private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/base-src/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/model/hero.glb /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/out-base/default/hero.png
/private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/base-src/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack --depth --light 30,40,50 /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/model/hero.glb /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/out-base/maps/hero.png
```

Head (`out-head/default` and `out-head/maps`):

```sh
/Users/vincentcoghlan/worktrees/coghex/moskophoros/issue-159-legacy-export-manifest/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/model/hero.glb /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/out-head/default/hero.png
/Users/vincentcoghlan/worktrees/coghex/moskophoros/issue-159-legacy-export-manifest/.venv/bin/moskophoros --no-user-config --blender /opt/homebrew/bin/blender --supersample 2 --cell 16x16 --fps 4 --clip walk --clip attack --once attack --depth --light 30,40,50 /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/model/hero.glb /private/tmp/claude-501/-Users-vincentcoghlan-work-moskophoros/85db917c-03ec-4725-a88f-a99c04e20ce0/scratchpad/evidence-159/out-head/maps/hero.png
```

The model is `evidence-159/model/hero.glb`; the fixed render overrides follow
the existing generated-model baseline (`FAST` and `SHEET` in
`tests/blender/test_whole_command.py`), `slide` is excluded, and the export
settings are at their defaults.

## Per-file SHA-256, base and head

Every colour, normal and depth PNG and every flat and lit GIF is identical.
The JSON differs at this switch only, as expected (`moskophoros.sheet/15`
to `moskophoros.export/1`, and its fingerprint).

| File | Base SHA-256 | Head SHA-256 | Result |
|---|---|---|---|
| `default/hero.attack.gif` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | identical |
| `default/hero.json` | `fb8d3be1aee8774e755dd3bb7ba15c97a252ac68a1e647b69201c36d7feddd28` | `9d5e9166b611db2954498bacfe19636232cb008e44c1c7a992a65a7681977f3a` | differs (expected) |
| `default/hero.normal.png` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | identical |
| `default/hero.png` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | identical |
| `default/hero.walk.gif` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | identical |
| `maps/hero-lit.attack.gif` | `f50a43fd32e90bc2008c3c1e557e9160693c90ca2ff558acb522c10cc4abc444` | `f50a43fd32e90bc2008c3c1e557e9160693c90ca2ff558acb522c10cc4abc444` | identical |
| `maps/hero-lit.walk.gif` | `cededac3b1ada093f5a3e7e6a2b35d56768cbc0a9d2bba064f682e32fb6165cc` | `cededac3b1ada093f5a3e7e6a2b35d56768cbc0a9d2bba064f682e32fb6165cc` | identical |
| `maps/hero.attack.gif` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | `0cd3097453fda0647d33f3132e6b28f9f77b547e5f0b573e2b8e500c10fad0a4` | identical |
| `maps/hero.depth.png` | `c4900e1bc398343b8d11c69c41ea22d7b0765696c1b19d734cb562cff9c611c8` | `c4900e1bc398343b8d11c69c41ea22d7b0765696c1b19d734cb562cff9c611c8` | identical |
| `maps/hero.json` | `abf84d796030170c7128b404097bd995c6c6c839baac5ad7620cf7025682c390` | `41e58365feff6d7829c78cba25a4947279c65ebfc951c068f642744a126c24be` | differs (expected) |
| `maps/hero.normal.png` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | `c8003dcf37d96afa09a4318d22562c206977432296d33aa6171672661a1cb248` | identical |
| `maps/hero.png` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | `cd05d020230684ff26c3000d9a7d6c3c3ce92fdb7b3a27bdf133c58ae033f3a6` | identical |
| `maps/hero.walk.gif` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | `3ffdf0d3ef85299fafe29a68cc2671fbed75da5d42dccc406ab77d7b59358c1c` | identical |

