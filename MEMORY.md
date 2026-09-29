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

1. Turn slice 1 into tracker issues (design-epic or issue workflow).
2. **Owner:** provide a real animated character `.glb` with one looping clip
   and one one-shot clip, for slice 1 acceptance. Tests use generated fixtures
   until then.

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
