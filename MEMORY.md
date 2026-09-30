# Moskophoros memory

Where the project stands, for an agent or the owner arriving cold. Read it
after [AGENTS.md](AGENTS.md), then check `git log` and the tracker for
anything newer than the date below.

**Last reconciled: 2026-09-29.**

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

- **Phase:** design accepted, no code yet. The vision and the slice 1 design
  were accepted by the owner on 2026-09-29.
- **Next milestone:** slice 1, the plain 3D-to-sheet pipeline. Its acceptance
  is in design §Slice 1 acceptance.
- **Implementation:** no package yet. CI exists but only checks the
  repository tooling (see below).

## Environment

- **Repository:** `coghex/moskophoros` on GitHub (public), default branch
  `master`, MIT license.
- **Checkouts:**
  - primary checkout: `~/work/moskophoros`
  - docs worktree: `~/work/moskophoros/.worktrees/docs` on `docs-wip`
  - pull request worktrees: under `~/worktrees/coghex/moskophoros/` (the Kanban
    default)
- **Blender:** 5.2.2 LTS, installed through Homebrew at
  `/Applications/Blender.app`, with `blender` on `PATH`. The supported version
  is recorded in design §Supported Blender version.
- **Python:** the system Python is 3.14. Blender bundles its own 3.13.
- **Docs landing:** `tools/docs_land.sh`, vendored from Kanban. Provenance is in
  [tools/README.md](tools/README.md).

## Kanban pull-request flow

Set up on 2026-09-29; `kanban --doctor` reports every action ready.

- **Labels:** the eight workflow labels exist (review states, `epic`,
  `needs-decision`, `wip`, `blocked`, `hotfix`).
- **Required checks:** `build-test` (CI) and `review-approved` (the review
  gate), enforced on `master` by a ruleset. Repository admins bypass it, which
  is what lets `tools/docs_land.sh` push documentation directly.
- **CI:** `build-test` checks the docs-landing helper and runs
  `tools/test_review_gate.py`. The first implementation pull request adds the
  package's tests to it.
- **Review gate:** Kanban's own gate, with two local fixes to its
  stale-approval step that upstream Kanban still lacks. Provenance is in the
  workflow's header.
- **PR drainer:** installed as `com.coghex.drain-prs.coghex.moskophoros` and
  currently **stopped** by the owner; control it with `kanban:drain-prs`.
- **Not installed:** the optional issue approval service (Hetoimasia has one).
- **Merged branches:** GitHub does not delete them automatically here; delete
  them after merging.

## Next steps

The path from the accepted design to code, agreed 2026-09-29:

1. **Blender capture experiment:** done 2026-09-29. Design §Capture holds on
   Blender 5.2; its findings are recorded under §Supported Blender version.
2. **Two design epics, in order**, written with `/design-epic` into
   `docs/designs/`:
   1. **CI foundation:** fully processed 2026-09-29 into epic #3 and issues
      #4 (pytest/ruff harness), #5 (catalog and planner), #6 (CI image) and
      #7 (GitHub wiring). [Design](docs/designs/ci_foundation_design.md).
   2. **Slice 1:** not yet written. Draft slices: skeleton and CLI validation;
      `.glb` reading (a pure-Python writer builds test models); camera and
      sampling; scale and fit; Blender measure; render, stylize and export;
      previews and reuse; owner acceptance.
3. **`/solve` the CI issues in order:** #4 first; then #5 and #6, which can run
   in parallel; then #7. The owner finalizes by hand while the drainer is
   stopped. After that, write the slice 1 design with `/design-epic`.
4. **Owner:** a real character `.glb` (one looping, one one-shot clip) for the
   final slice; tests use generated fixtures until then.

**Don't land docs while pull requests are open.** Branches must be up to date,
and `/finalize` cannot carry approval across a branch update, so each open PR
would need `/fix` and a fresh review. Alternatively, configure moskophoros
`coordination_paths` in the Kanban config.

## Owner preferences

- Likes to discuss and decide before building: start slow, present options
  with a recommendation, then act.
- Style (palettes, outlines, shading) is deferred on purpose. Don't push it
  into early milestones; the owner will take it up.
- Wants accepted documents marked with their status, and published once
  ready.
- Makes and rigs models with AI tools, so expect imperfect inputs (vision
  V-11).
- Serves Synarchy and its rewrite Hetoimasia, but the tool must never
  integrate with either.

## Open questions

None blocking. Deferred decisions and their triggers are listed in
design §Deferred.
