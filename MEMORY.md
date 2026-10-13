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
    2026-10-08;
  - settings: 2026-10-13.
- **Settings arc** ([design](docs/designs/settings_design.md)): accepted
  by the owner on 2026-10-13 ([record](docs/acceptance/settings.md)); epic
  #83 closed. Layered YAML settings (user file, reused sheet, `--config`,
  options), the shading values, per-material shading and clip frame counts.
  Libraries are YAML (`moskophoros.materials/2`).
- **Open epics:** #63 (material styling), open for MAT-8 and #75. #3, #24
  and #83 are closed, and so are #78 and #79, settled by settings.

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
- **The owner's user settings** (`~/.config/moskophoros/config.yaml`) set
  their working palette, Vince 144 (Vince 128 plus a 16-step grey ramp,
  chosen 2026-10-13), for every run without `--palette`. Pass
  `--no-user-config` for any render that must match shipped defaults.

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

1. **Owner's look:** the Vince 144 renders of 2026-10-13 are with the
   owner. Their chosen shading goes in their user settings file, not the
   shipped defaults.
2. **Lighting sheet:** the next arc. The owner settled its direction on
   2026-10-13 in material styling D-27: a flat colour sheet, a normal map, an
   optional depth map, and a lit preview that is never baked. Its own design
   comes next, when the owner asks.
3. **Guide:** review the work after `bb3c9b4`.
4. **Deferred, each waiting on a stated trigger:**
   - recolouring without a re-render (settings D-18);
   - MAT-8, generated ramps (material styling Q-24);
   - #75, glTF MASK cutouts;
   - #43, mesh-weight animation and CUBICSPLINE tangents: approved, but held
     until a model needs it.

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

Owner choices only: their default look (above). Deferred design decisions
and their triggers are listed in design §Deferred.
