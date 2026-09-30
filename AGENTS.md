# Working in moskophoros

Moskophoros is a Python command-line tool that renders animated `.glb` models
into pixel-art sprite sheets through headless Blender. This file is the single
authority on **how to work** here, for every agent. `CLAUDE.md` imports it; do
not keep rules anywhere else.

What to build and why lives elsewhere, in this order of authority:

1. [docs/vision.md](docs/vision.md): the owner's direction and principles
   (V-1 … V-12). `$guide` / `/guide` reviews work against it.
2. [docs/design.md](docs/design.md): the concrete contracts: CLI, geometry,
   sampling, formats, errors.
3. [MEMORY.md](MEMORY.md): where the project stands now, and what is next.

If code, the design and the vision disagree, stop and ask the owner. Never
change the vision or the design to fit code, or quietly pick one side.

## Required reading

Read the owning document before working in an area, including when a change
reaches into it from elsewhere.

| Area | Read first |
|---|---|
| Anything user-visible: CLI, outputs, errors | design §CLI, §Export |
| Camera, directions, scale, ground point | design §Camera and directions, §Scale and ground point |
| Clip timing, root motion | design §Clips and sampling |
| Blender backend | design §Capture, §Supported Blender version |
| Stylize, cleanup, image operations | vision V-4, V-8, V-10; design §Pipeline |
| Scope or direction questions | vision |
| Test groups, CI checks, pull request validation | [docs/validation.md](docs/validation.md) |

## Owner authority

- The owner decides direction, style and acceptance. Agents recommend. Record
  a new owner decision with its date in the document that owns the topic.
- Visual quality is judged by the owner, not by tests (vision V-12).
- Authorization carries across turns within a conversation. It does not carry
  to a different kind of action; ask before anything outward-facing that was
  not requested.

## Architecture rules

These restate the design's hard boundaries so they are not missed:

- **Only `src/moskophoros/capture/blender_script.py` imports `bpy`.** It runs
  inside Blender's own Python (3.13 in Blender 5.2), using only `bpy` and the
  standard library. Nothing else imports it.
- **Stages talk through addressed frames.** Capture, stylize, cleanup and
  export depend on each other's outputs, never on each other's internals.
- **Keep pure logic apart from effects.** Geometry, sampling, fitting and
  layout are pure functions tested without Blender or the filesystem.
- **Output is deterministic.** No timestamps, no unordered iteration into
  output, and no randomness without a recorded seed.
- **The tool belongs to no game.** No game names, paths or layouts in code,
  tests or defaults (vision V-1).
- **Fail loudly on bad input.** Use the design's exit codes and name the file,
  clip and problem. Never silently produce a wrong sheet.

Add a dependency only for a concrete use, and pin it in `requirements.lock`.

## Build and test

These commands need Python 3.13 or newer. CI runs the same ones on 3.13, and a
change that alters them updates this section in the same pull request.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock   # the exact tested tool versions
.venv/bin/pip install --no-deps -e .
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest                    # everything; Blender tests skip if absent
.venv/bin/pytest -m "not blender"   # fast: no Blender needed; what CI runs
.venv/bin/python tools/validation/plan.py --base origin/master --head HEAD
                                    # which test groups this change needs, and why
```

`pyproject.toml` states minimum versions and `requirements.lock` pins the tested
ones. After changing the development dependencies, regenerate the lock for
Python 3.13 and commit it with the change:

```sh
.venv/bin/uv pip compile pyproject.toml --extra dev --python-version 3.13 --universal -o requirements.lock
```

- Mark every test that needs Blender with `@pytest.mark.blender`, and keep it
  under `tests/blender/`. An unregistered marker is an error.
- Run the tests covering what you changed: the groups the planner selects.
  Run the Blender tests whenever it selects `test.blender`, the local-only
  group in [the catalog](tools/validation/catalog.json).
- A pull request that selects `test.blender` must carry a `local-validation`
  block reporting a passing run at a current commit
  ([docs/validation.md](docs/validation.md#local-only-reports)).
- A skipped test is not a passing test. Report skips and the reason.
- Tests write only to temporary directories, and generate their own `.glb`
  fixtures.
- Never use sleeps for timing. Coordinate processes explicitly.

## Blender

- The supported version is recorded only in design §Supported Blender version
  (currently 5.2 LTS). Do not copy the number elsewhere.
- Always run Blender headless: `-b --factory-startup -noaudio`. Never open its
  interface, and never read or change the owner's Blender preferences,
  add-ons or startup file.
- Do not upgrade, downgrade or reinstall Blender without the owner's approval.

## Delivery

- **Tracker:** GitHub `coghex/moskophoros`, default branch `master`. The
  primary checkout is `~/work/moskophoros`. The Kanban plugin lives in
  `~/work/kanban`; that repository is never this project's tracker.
- **Keep the primary checkout clean.** It only fast-forwards to `master`.
  Implement in an isolated worktree on a branch, and deliver by pull request.
- **One issue, one pull request, one worktree.** Code, tests, the
  documentation the change requires and any evidence go together. Use
  `Closes #N` when the pull request completes the issue.
- **Mark every pull request's origin.** Its body must end with exactly one
  origin marker as its final line: `<!-- pr-origin:claude -->` or
  `<!-- pr-origin:codex -->`, naming the agent that wrote it. Put any
  attribution line above it. Review is routed to the other agent; a pull
  request without a valid marker counts as unknown origin and is reviewed by
  both. The `kanban:solve` workflow adds the marker; add it yourself when
  opening a pull request any other way.
- **Standalone documentation** (no code change) is written in the `docs-wip`
  worktree, found by branch rather than by path:

  ```sh
  git worktree list --porcelain | awk '/^worktree /{p=substr($0,10)} /^branch refs\/heads\/docs-wip$/{print p}'
  ```

  It lands on `master` only when the owner asks, through `tools/docs_land.sh`
  (the `kanban:push-docs` skill). Dry-run first and stop on any warning or
  refusal. Never use this lane for documentation a code change needs.
- **Merging.** The PR drainer merges a pull request once it carries
  `reviewed:approve` and its `build-test` and `review-approved` checks pass. A
  push that changes the pull request's own files removes the approval, so it
  needs a fresh review. Never merge or approve your own work, never merge on
  your own initiative, and never add review labels by hand. A label alone is
  not proof of a fresh approval.
- Never reset, clean or rebase another agent's worktree. Stop only processes
  you started.

## Evidence and honesty

- Report what happened: failing output, skipped steps, untested platforms.
  "Tests pass" says nothing about how a sprite looks.
- A pull request that changes rendered output gives the exact command that
  reproduces it, so the owner can view the sheet and its previews.
- Implementation docs describe current behavior. Plans are labeled as plans,
  and nothing is described as done before it is.

## Files

- Never commit generated sheets, previews, capture work directories or
  virtual environments.
- Do not commit large binaries (models, renders) without the owner's approval.
- Owner-supplied `.glb` models are inputs, not missing art. A generated sprite
  is this tool's product, never a placeholder that needs an artist.

## Keeping these documents healthy

- **This file:** rules for how to work only. Keep it short. Put a subsystem's
  rules in its owning document and link to it; when moving a rule, confirm its
  new home states it.
- **No history in instructions:** no issue or pull request numbers, dates of
  past incidents, or "previously" notes. The git log and the tracker hold
  history.
- **Define every abbreviation** where it is first used, or do not use it.
- **MEMORY.md** follows its own rules, stated at its top.
