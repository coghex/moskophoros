# Moskophoros memory

Where the project stands, for an agent or the owner arriving cold. Read it
after [AGENTS.md](AGENTS.md), then check `git log` and the tracker for
anything newer than the date below.

**Last reconciled: 2026-10-13.**

**Rules for this file:**
- **Current state only.** When something changes, replace the old line; don't
  append. History lives in git and the tracker.
- **Link, don't copy.** Direction belongs to the vision, contracts to the
  design, and working rules to AGENTS.md. This file points to them.
- **Keep it under about 100 lines.** A section that grows is a sign its content
  belongs in an owning document.
- **Update it** as a standalone documentation change when a milestone lands, a
  decision changes, or the next step changes, and bump the date. Implementation
  pull requests leave it alone, so parallel work does not conflict on it.

## Where things stand

- **Review heading:** [docs/vision.md](docs/vision.md); `/guide` resumes from
  [docs/guide/CURSOR.md](docs/guide/CURSOR.md). The last guide review stopped
  at `bb3c9b4` (2026-10-06); later work is unreviewed.
- **The command works.** It renders an animated `.glb` through headless
  Blender into a sheet, a JSON description and animated previews, and the
  owner judges the looks by eye (vision V-12). Its contract is
  [docs/design.md](docs/design.md) §CLI.
- **Accepted by the owner** (records in [docs/acceptance/](docs/acceptance/)):
  - slice 1, the plain pipeline: 2026-10-03;
  - style pass 1, palettes and reduction: 2026-10-05;
  - material styling, a qualified acceptance of the proof of concept:
    2026-10-08. Its limits are the warm ramp (#78) and Grey and Black
    clipping (#79).
- **Settings arc** ([design](docs/designs/settings_design.md), epic #83):
  all five slices are merged (SET-0 to SET-3 and SET-5). They add layered YAML
  settings (user file, reused sheet, `--config`, options), the shading values
  as settings and options, per-material shading, and clip frame counts.
  Libraries are YAML (`moskophoros.materials/2`). On 2026-10-12 the
  2026-10-09 R1 and R2 looks reproduced byte for byte from `--config` files
  alone. **Waiting on the owner's visual verdict** before #83 closes.
- **Open epics:**
  - #3 (CI) and #24 (slice 1): all children closed; the owner decides
    closure.
  - #63 (material styling): open for MAT-8 and its follow-ups.
  - #83 (settings): see above.

## Environment

- **Repository:** `coghex/moskophoros` on GitHub (public), default branch
  `master`, MIT license.
- **Checkouts:**
  - primary checkout: `~/work/moskophoros`;
  - pull request worktrees: under `~/worktrees/coghex/moskophoros/` (the
    Kanban default).
- **Blender:** 5.2.2 LTS, installed through Homebrew at
  `/Applications/Blender.app`, with `blender` on `PATH`. The supported version
  is recorded in design §Supported Blender version.
- **Python:** the system Python is 3.14. Blender bundles its own 3.13.
- **Docs landing:** `docs-push`, as AGENTS.md §Delivery says.
  `tools/docs_land.sh` is vendored from Kanban; its provenance is in
  [tools/README.md](tools/README.md).
- **Acceptance renders** of the owner's test model live outside git, under
  `~/.local/share/moskophoros-acceptance/` on the owner's Mac.

## Kanban pull-request flow

- **Labels:** the eight workflow labels exist (review states, `epic`,
  `needs-decision`, `wip`, `blocked`, `hotfix`).
- **Required checks:** `build-test` (CI) and `review-approved` (the review
  gate), enforced on `master` by a ruleset that requires up-to-date branches.
- **CI:** `build-test` runs the test groups the planner selects, inside the
  prebuilt image ([docs/validation.md](docs/validation.md)). The Blender group
  is local-only and reported in the pull request body.
- **PR drainer:** installed as `com.coghex.drain-prs.coghex.moskophoros` and
  **stopped** by the owner. Approved pull requests are merged one at a time
  with the drainer's single-pull-request mode, on the owner's request.
- **Docs and open pull requests:** a docs push puts open pull requests behind
  `master`. Updating one drops its approval, so it needs a fresh review.
- **Merged branches:** GitHub does not delete them automatically here; delete
  them after merging.

## Next steps

1. **Owner:** judge the settings renders of 2026-10-12. On acceptance, record
   it in `docs/acceptance/` and close #83.
2. **#79 and #78:** both are reviewed `changes` and `blocked`, waiting on the
   owner's choices. Per-material shade ranges and library edits can now try
   those choices without code. Revise each body to the chosen option, then
   re-review.
3. **Deferred, each waiting on a stated trigger:**
   - recolouring without a re-render (settings D-18);
   - MAT-8, generated ramps (material styling Q-24);
   - #75, glTF MASK cutouts;
   - #43, mesh-weight animation and CUBICSPLINE tangents: approved, but held
     until a model needs it.
4. **Lighting sheet:** the next arc. The owner settled its direction on
   2026-10-13 in material styling D-27: a flat colour sheet, a normal map, an
   optional depth map, and a lit preview that is never baked. Its own design
   comes next, when the owner asks.
5. **Guide:** review the work after `bb3c9b4`.

## Owner preferences

- Likes to discuss and decide before building: start slow, present options
  with a recommendation, then act.
- Judges style by eye from clearly labelled renders. Agents propose looks and
  never change a default look without the owner's decision.
- Wants accepted documents marked with their status, and published once
  ready.
- Makes and rigs models with AI tools, so expect imperfect inputs (vision
  V-11).
- Serves Synarchy and its rewrite Hetoimasia, but the tool must never
  integrate with either.

## Open questions

Owner choices only: the settings verdict, #78 and #79 above, and whether to
close #3 and #24. Deferred design decisions and their triggers are listed in
design §Deferred.
