# SHD-1 against the shading pre-arc baseline

Evidence for SHD-1 (#138, epic #137, [shading design](../designs/shading_design.md)
§Verification strategy, *Compatibility*). It is a record of what was run, not a
design. The pin, tools and inputs of the shared baseline are in
[shading-pre-arc-baseline.md](shading-pre-arc-baseline.md); this record adds
SHD-1's own runs against that same pin. Generated sheets, previews, captures and
models stay outside the repository, in local evidence (below).

## What SHD-1 changed

Capture-result `/4` becomes `/5`: every render frame carries one more mandatory
buffer, `back_normal`, and the command decodes it, and the front normal derived
from the front-most normal, into two addressed arrays. The sheet schema (`/14`),
the capture-job schema (`/3`) and every default output are meant to stay as they
were. This record shows whether they did.

- **Baseline:** `shading-pre-arc`, commit `f548312a5a929fb9bd843855b83b9762123f80ab`,
  unmoved. Its `src`, `tests`, `pyproject.toml` and `requirements.lock` are
  byte-identical to the master SHD-1 branched from.
- **Candidate:** SHD-1's head `982671a3718c67cf20e1e1284bac17e8a86c5c98`
  (a later head is named in the pull request).
- **Tools:** the same virtual environment ran both sides, so every recorded tool is
  the same: Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0, PyYAML 6.0.3, Blender 5.2.2 LTS
  (`/opt/homebrew/bin/blender`), macOS 26.7.1 (arm64). Only `PYTHONPATH` differed:
  the baseline side ran the clean `git archive` copy of the pinned commit, the
  candidate side the pull request's worktree. `moskophoros.__version__` is `0.1.0`
  on both.
- **Configuration:** every command passes `--no-user-config`; no file under
  `~/.config/moskophoros` was read or written.

## Compatibility: sixteen commands, byte for byte

One generated model, `fixture.glb` (SHA-256
`edb49ec654576a0226fe345d6c4cf6cfd331912437e817f34c4388028738a595`), built with the
pinned commit's own `glb_writer.py` and `material_models.py`: a textured opaque
`Wood`, an `Iron`, a translucent `Glow` (`BLEND`) in front of the wood, a cut-out
`Leaf` (`MASK`) and an unnamed material (ordinary), with a three-key animation
`Spin` (translation and a quarter turn). Common flags: `--no-user-config --clip Spin
--view iso --directions 3 --cell 64x64 --ppm 24 --ground-px 32,52 --supersample 4
--depth --light -10,20,15`, each with `--work-dir` to keep the capture. The cases
vary what the design names: the reduction (`plain`, `mode`), the edge rule (`hard`,
`soft`) and the look: no palette (ordinary materials only), a palette alone, a palette
with a `moskophoros.materials/3` library and a palette with a `/2` library, both
mapping `Wood`, `Iron`, `Glow` and `Leaf`.

Each of the 16 cases ran with the baseline and with the candidate, one at a time
under the shared Blender lock, from its own directory with the same relative output
paths. Every case exited 0.

- **Outputs: identical.** In all 16 cases, all six output files (sheet, sheet
  JSON, normal map, depth map, flat preview, lit preview) are byte-identical,
  JSON and fingerprint included. No JSON change is allowed or present.
- **Retained captures: current buffers identical.** Each case kept 328 capture
  files on the baseline side. On the candidate side every one of those is
  byte-identical (`color`, `matid`, `shade`, `normal`, `depth` and the four front
  buffers) except four JSON files, and 36 files are added, the `back_normal`
  buffers (3 directions × 12 frames):
  - `render/result.json` and `measure/result.json` differ in `schema`
    (`/4` → `/5`), in `job_sha256`, and, for the render, in the added
    `back_normal` path of each frame;
  - `render/job.json` and `measure/job.json` differ in `output_dir` alone, which
    names each side's own run directory: the job's payload is otherwise the same,
    so the capture-job schema and payload are unchanged.

The same comparison ran on the two real models of the cost measurement (below), at
three repetitions each: the sheet, JSON, normal map, depth map and previews of all
three repetitions are byte-identical to the baseline's (5 files for the robot, 6 for
the chest), and the retained captures differ only by the same four JSON files and
the added `back_normal` files (160 for the robot, 152 for the chest).

## Cost on the robot and the chest

Both models are the owner-chosen inputs of earlier acceptances, and match their
recorded hashes: `RobotExpressive.glb`
`047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319` and the alpha
review's chest v5 `chest.glb`
`04932ad4c77d1348d6d123fa4fda8924edbfa338e7c25a8de814b7200ed3a72c`. The commands
use `--no-user-config` and the shipped defaults, so they are not the
acceptance runs that used the owner's settings:

    robot: --clip Walking --clip Jump --once Jump --cell 256x256 --view iso --directions 8
    chest: --clip Open --once Open --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges hard

| | frames | cell | supersample | capture size |
|---|---|---|---|---|
| robot | 160 | 256×256 | 8 | 2048×2048 |
| chest | 152 | 128×128 | 8 | 1024×1024 |

**Method.** Three runs of each model per side, interleaved (baseline, candidate,
baseline, … per model), each under the shared Blender lock with `--work-dir`.
**Timing scope:** `capture_s` is the wall-clock time of the two capture phases, the
measure and the render Blender process, from launch to exit, taken around
`run_phase` by `tools/run_case.py`; it includes Blender's render and the script's own
PNG encoding, and excludes stylize, cleanup and export. The whole-command time is in
the local evidence. **Work-directory bytes** are the sum of the kept capture's file
sizes. A timing hold was posted to `#moskophoros`; per the dispatch the runs began
after a few minutes without waiting for a whole-machine quiet, so other agents'
work may have run beside them, and the spread between runs is the honest bound.

| model | side | capture time, each run (s) | mean (s) | work directory (bytes) | files |
|---|---|---|---|---|---|
| robot | baseline | 926.16, 914.01, 986.23 | 942.14 | 715,334,537 | 1,444 |
| robot | candidate | 931.91, 980.88, 990.91 | 967.90 | 811,893,959 | 1,604 |
| chest | baseline | 379.75, 444.50, 425.55 | 416.60 | 223,118,233 | 1,372 |
| chest | candidate | 427.06, 491.84, 463.24 | 460.71 | 234,788,146 | 1,524 |

Measured differences (candidate minus baseline, of the means): robot **+25.76 s
(+2.7 %)** and **+96,559,422 bytes (+13.5 %)**; chest **+44.11 s (+10.6 %)** and
**+11,669,913 bytes (+5.2 %)**. The work-directory bytes were the same in all three
runs of each side. The added bytes are the `back_normal` directory (96,551,580 bytes for the robot,
whose `normal` directory is the same size, and 11,662,463 for the chest) and the
larger result JSON. The runs of one
side differ by as much as 72 s (robot) and 65 s (chest), so the robot's difference
is within the runs' own spread and the chest's overlaps it. No threshold is applied.
The code explains why the chest costs more: a model with a translucent layer encodes
a second, different normal per frame, while one without copies the file it has just
encoded; this is the reading of the code, not a separate measurement.

## Working-sheet inventory

Empty. The owner decided on 2026-10-21 that no working sheets exist yet
([D-42](../designs/shading_design.md)), so there is no invocation to prove and
nothing to regenerate; every existing sheet stays as historical evidence.
Requirement 7 of #138 is met by that record.

## Local evidence

`~/.local/share/moskophoros-acceptance/shading-pre-arc/` (SHD-1's files; SHD-2's are
under its `shd2/`):

- `manifest.json`: the pinned source, the tools, and the hashes of every input, the
  fixture generator and the harness;
- `tools/`: `make_fixtures.py`, the copied `glb_writer.py` and `material_models.py`,
  `run_matrix.py`, `run_cost.py`, `run_case.py` (timing wrapper),
  `compare_trees.py`, `summarize_cost.py` and `make_manifest.py`;
- `runs/<baseline|candidate>/<case>/`: each compatibility command
  (`command.txt`), its log, its outputs and its kept capture;
- `cost/<robot|chest>/<side>-<n>/`: each cost run's command, log, outputs, kept
  capture and `report.json`; `cost-summary.json` is the table above.

Reproduce the compatibility cases with `PINNED_PYTHON=<python> CANDIDATE_SRC=<src>
tools/run_matrix.py baseline|candidate`, and the cost series with `tools/run_cost.py 3`.
