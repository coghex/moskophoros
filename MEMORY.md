# Moskophoros memory

Where the project stands, for an agent or the owner arriving cold. Read it
after [AGENTS.md](AGENTS.md), then check `git log` and the tracker for
anything newer than the date below.

**Last reconciled: 2026-10-20.**

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
  [docs/guide/CURSOR.md](docs/guide/CURSOR.md), which holds coverage and follow-ups.
- **The command works.** It renders an animated `.glb` through headless
  Blender into a sheet, a JSON description and animated previews, and the
  owner judges the looks by eye (vision V-12). Its contract is
  [docs/design.md](docs/design.md) §CLI.
- **Accepted by the owner** (records in [docs/acceptance/](docs/acceptance/)):
  - slice 1, the plain pipeline: 2026-10-03;
  - style pass 1, palettes and reduction: 2026-10-05;
  - material styling, a qualified acceptance of the proof of concept:
    2026-10-08;
  - settings: 2026-10-13;
  - lighting sheet: 2026-10-14;
  - alpha: 2026-10-19, cutouts judged separately on a shrub the same day;
  - projects and camera: 2026-10-20.
- **Settings arc** ([design](docs/designs/settings_design.md)): accepted
  by the owner on 2026-10-13 ([record](docs/archive/acceptance/settings.md)); epic
  #83 closed. Layered YAML settings (user file, reused sheet, `--config`,
  options), the shading values, per-material shading and clip frame counts.
  Libraries are YAML (`moskophoros.materials/3`, with `/2` still supported).
- **Lighting sheet** ([record](docs/archive/acceptance/lighting-sheet.md)): every run
  writes `<stem>.normal.png`; `--depth` adds a depth map and `--light X,Y,Z`
  lit previews. Known cost: normal and depth encoding roughly doubles a test
  render's time.
- **Alpha arc** ([design](docs/designs/alpha_design.md)): accepted by the
  owner on 2026-10-19 ([record](docs/acceptance/alpha.md)); epic #113 closed.
  Sheets carry the model's transparency: `MASK` cutouts, `BLEND` translucency
  in 8-bit alpha, `--edges hard|soft` (both required), and maps aligned with
  the colour. Cutouts were judged on a separate shrub model and accepted
  ([Cutouts](docs/acceptance/alpha.md#cutouts)).
- **Projects and camera arc** ([design](docs/designs/projects_camera_design.md)):
  accepted by the owner on 2026-10-20 ([record](docs/acceptance/projects-camera.md));
  epic #127 closed. `--project NAME` reads `~/.config/moskophoros/projects/NAME.yaml`
  over the global file. The camera takes a direction vector, a roll, a position, and
  an orthographic or perspective projection, as flags or settings. Commands that
  set no camera give byte-identical images. Contract: design §Camera and directions.
- **Open epics:** none. Material styling, settings, lighting sheets, alpha
  and projects and camera are complete; #63, #83, #95, #113 and #127 are
  closed on the owner’s word.

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
- **The owner's settings are per project** (owner, 2026-10-19). Every
  rendering setting lives in the project's own file, chosen with `--project`.
  - `~/.config/moskophoros/projects/synarchy.yaml`: live-lit isometric sprites.
    The pre-migration copy `~/.config/moskophoros/synarchy.yaml` is kept. It
    holds the palette `../palettes/synarchy.gpl` (formerly Vince 144:
    Vince 128 plus a 16-step grey ramp, unchanged), the shading (render N3,
    range 190–225), ramp setting C, `edges: hard`, normal and depth maps on,
    and a preview light.
  - `config.yaml`, the user file, is kept for app settings and holds none
    yet, so a run without `--config` uses the shipped defaults.
  - `codekarl.yaml` comes later: the baked, straight-on art panels, with
    their own palette.
  - The robot's library is
    `~/.config/moskophoros/libraries/robotexpressive.yaml`.

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

1. **Shading design (next, when the owner is ready):** baked light for straight-on art panels.
   The three shading ways are ramp only, brightness only, and both, with
   dithering. It amends lighting D-4, `design.md` §Previews ("never baked"),
   and material styling D-22 and D-25. Then the Codekarl palette and
   `codekarl.yaml` follow.
2. **Later, on the owner's word:** more shading and texture for wood (raised
   in the alpha review; a look question, not yet an issue).
3. **Deferred, each waiting on a stated trigger:**
   - recolouring without a re-render (settings D-18);
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

None blocking. Deferred design decisions and their triggers are listed in
design §Deferred.
