# CI foundation design

Give moskophoros categorized, explainable CI before any product code lands, so
every slice 1 pull request starts with the owner's usual CI features: test
groups declared once, mandatory and affected groups selected automatically,
optional groups run only on request, and a prebuilt, digest-pinned CI image.
It serves the owner, who finalizes pull requests, and the agents that open
them, who need to know which checks a change requires and why.

Design state: `ready for issue processing`

Owner: `coghex/moskophoros`; publication target: `master`. Created 2026-09-29
in the owner's `docs-wip` worktree.

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [ ] EPIC. Establish categorized, explainable CI with a prebuilt image
- [ ] CIF-1. Set up the pytest and ruff harness and run it in CI
- [ ] CIF-2. Declare test groups in a catalog and explain which ones a change needs
- [ ] CIF-3. Build and publish the CI image once per recipe, addressed by digest
- [ ] CIF-4. Run the planned groups on GitHub behind an honest `build-test`

The owner approved every decision and marked this design ready for issue
processing on 2026-09-29.

## Epic contract

- **Goal:** every pull request's required checks are the mandatory floor, plus
  the non-optional groups its changes affect, plus the groups it explicitly
  requests. The plan explains each group's selection or omission, and CI runs
  inside a prebuilt image.
- **Done when:** a pull request's plan is visible and correct for code,
  docs-only and request cases; `build-test` reflects exactly the planned
  groups; the image is published and addressed by digest; and the conventions
  are documented for the slice 1 epic to register its groups.
- **Users and operators:** the owner, reviewing and finalizing pull requests;
  solve and review agents, which read the plan to choose and report checks.
- **Arc label:** `ci` (proposed; no such label exists yet).

## Current state and evidence

- **CI today:** `.github/workflows/ci.yml` has one job, `build-test`, which
  checks the docs-landing helper's syntax and runs `tools/test_review_gate.py`.
  `.github/workflows/review-gate.yml` publishes `review-approved`. A `master`
  ruleset requires both, with up-to-date branches and an admin bypass that
  `tools/docs_land.sh` relies on.
- **No product code or package yet.** `AGENTS.md` §Build and test states the
  planned commands (`pip install -e '.[dev]'`, `pytest`, `pytest -m "not
  blender"`), to be created by the first implementation pull request.
- **Toolchains:** Blender 5.2.2 bundles Python 3.13.13, which the capture
  backend runs under (design §Supported Blender version). The owner's machine
  runs Python 3.14. GitHub's `ubuntu-latest` runners provide Python 3.12.
- **The model:** Hetoimasia's `docs/ci_validation_design.md` and
  `docs/validation.md` describe a catalog (`tools/validation/catalog.json`), a
  planner (`tools/validation/plan.py`), a `validation-request` block in pull
  request bodies, parallel workers with an aggregate `build-test`, and an image
  (`ghcr.io/coghex/hetoimasia-ci`) published once per recipe fingerprint and
  addressed by digest. Its planner derives dependencies from Cabal's package
  graph, so it cannot be reused as is for a Python project.
- **Tracker:** `coghex/moskophoros` has no issues, so no existing epic overlaps.

## Desired experience

- An agent or the owner runs one local command to see which groups a change
  requires and why, before pushing.
- A pull request needing extra coverage names catalog groups in its body; it
  never supplies shell commands.
- A docs-only pull request still produces a normal `build-test` result.
- An unrequested optional group is an explained omission, never a missing or
  failing check.
- Blender groups never run on GitHub. The plan says so and names the local
  command, and the pull request reports whether they ran locally (D-3).
- CI setup time is spent pulling a pinned image, not installing toolchains.

## Scope

### In scope

- The Python test harness: a minimal `pyproject.toml`, pytest and ruff
  configuration, and a lock file (D-8).
- The catalog, and the conventions for registering a group.
- The planner and its selection policy.
- Pull-request requests for extra groups.
- The CI image: recipe, pinning, publication and use.
- The GitHub workflow that runs the plan and the `build-test` aggregate.
- Documentation of all of the above, and `AGENTS.md` updates.

### Out of scope

- The product package's contents, command and tests, which belong to the
  slice 1 epic. This epic creates only the empty package (D-18).
- Hetoimasia's heavier machinery (D-12): evidence
  receipts and reuse, runner classes, display or GPU workers, review-replay
  provenance, and periodic-testing skill integration.
- Running Blender on GitHub (D-3).
- Changes to the review gate or the PR drainer.

## Design

Everything here is decided. The catalog (D-10), requests (D-11) and exclusions
(D-12) are described in their decisions. The subsections below began as
proposals P-2, P-4, P-6, P-7 and P-8, were revised on 2026-09-29 after an
external review, and were approved by the owner as D-13 to D-17.

### P-2. A planner that explains itself, with a defined comparison (D-13)

A small standard-library Python tool that prints which groups are required and
why: floor, affected by named paths, requested, or omitted as optional or
local-only. It also has a machine-readable form for CI. Unknown group IDs,
malformed requests and an invalid catalog are errors with a diagnostic.

What it compares:

- **Pull request:** the changed paths are those between the merge base of the
  base branch and the head, and the head (a three-dot comparison, the one
  GitHub shows). The revision CI tests is GitHub's merge commit for the pull
  request.
- **Push:** the changed paths are those between the push's `before` and
  `after` revisions.
- **Renames count as both paths.** Comparisons ignore rename detection, so a
  renamed file affects the groups of its old path and its new path.
- **Fail wide, never narrow.** A `before` revision that is all zeros, not an
  ancestor of `after` (a force push), or missing from history, and any
  comparison that cannot be computed, select every non-optional group, with
  that reason in the plan. So do paths no group claims. Nothing is ever
  treated as "no change".

### P-4. A prebuilt image, published once per recipe (D-14)

A pinned base image (by digest) with Python 3.13 (D-5), the locked development
dependencies and the test tools, including ruff (D-6). It contains no Blender
and no project source. Published to `ghcr.io/coghex/moskophoros-ci`, and CI
runs it by digest. This follows Hetoimasia's recipe and descriptor model.

- **The fingerprint** is a hash of exactly these inputs, read from one
  commit's tree: every file under `tools/ci-image/` (the Dockerfile, which
  names the base image by digest, and any provisioning or build scripts), the
  lock file of development dependencies, and the image workflow file. The
  descriptor below is the one file excluded, so recording a digest never
  changes the fingerprint. Only files the fingerprint covers reach the build.
- **The descriptor** (`tools/ci-image/descriptor.json`) records the image
  reference, its digest, the fingerprint it was built from, and the Python and
  ruff versions it contains. CI runs exactly the descriptor's digest.
- **Updating the image:** a pull request that changes any fingerprint input
  runs the image workflow, which builds and publishes the candidate image under
  its fingerprint and reports its digest. The author commits the resulting
  descriptor to the same pull request with an ordinary push. Validation checks
  that the descriptor's fingerprint matches the candidate's; while it does not,
  `build-test` fails with a diagnostic naming the stale descriptor. An image is
  published once per fingerprint and never overwritten.

### P-6. The initial groups (D-15)

Following D-9, the first catalog:

| Group | Category | Runs | Affected by |
|---|---|---|---|
| `check.static` | mandatory floor | ruff lint and format check; the catalog's validity check; syntax checks of the vendored helpers (`bash -n tools/docs_land.sh`, Python compilation of `tools/docs_land_paths.py`) | every candidate |
| `test.workflow` | affected | pytest over `tools/`: the review-gate test and the planner's own tests | `tools/`, `.github/` |
| `test.package` | affected | pytest over the package's tests, excluding the `blender` marker | `src/`, `tests/`, `pyproject.toml`, the lock file |
| `test.blender` | local-only | pytest over the `blender` marker, on the owner's machine | `src/`, the Blender tests, `pyproject.toml`, the lock file |

`test.blender` covers the whole package because capture, sampling, fitting,
stylizing and output encoding all live in it, and `AGENTS.md` requires the
Blender tests whenever any of those change. As a result, nearly every package
pull request carries a local Blender obligation.

Vendored Kanban files are excluded from ruff, so they stay byte-identical to
their upstream revision; `check.static` still checks their syntax, as CI does
today. Slice 1 adds its package and Blender tests under these groups rather
than inventing new ones.

### P-7. A pull request body change replans (D-16)

Requests (D-11) and local-only reports (D-7) are read from the pull request
body, which GitHub's default pull-request events ignore when edited. So:

- CI also runs when a pull request body is edited.
- Runs for the same pull request share a concurrency group that cancels a
  run in progress, so an older run cannot finish after a newer one.
- The aggregate reads the body again before concluding, and fails if the body
  changed since it planned.

### P-8. Local-only reports must be fresh, and pushes do not check them (D-17)

This refines D-7.

- **Freshness:** each report entry names the commit the tests ran at. It is
  accepted only if that commit is in the pull request's history and none of the
  group's affected paths changed between it and the head. Otherwise
  `build-test` fails and names the group and the paths that changed.
- **Pushes:** a push has no pull request body, so local-only obligations are
  not checked on push. The push plan lists them as omitted, "verified on the
  pull request". A direct push that bypasses a pull request, such as a docs
  landing, gets the same explained omission.

## Decisions

### D-1. pytest, used the way the owner uses Hspec

Owner decision 2026-09-29. Tests are written with pytest as the one primary
framework, organized by behavior with descriptive names, and small scripts are
used only where pytest cannot reach. Rejected: Hspec tests driving the command
line, which would add a Haskell toolchain to a Python repository and could not
test internal functions; rewriting the tool in Haskell, which would reverse
vision V-12.

### D-2. Test models come from a pure-Python `.glb` writer

Owner decision 2026-09-29. Tests generate the rigged, animated `.glb` files they
need with a small pure-Python writer, so no binary fixtures are committed and
the fixtures are deterministic. The writer itself belongs to the slice 1 epic;
this epic only relies on tests needing no committed models. Rejected: models
built in Blender and committed.

### D-3. Blender tests are local-only

Owner decision 2026-09-29. Groups that need Blender never run on GitHub, whose
runners lack Blender and a reliable OpenGL context. A pull request that affects
them reports whether they were run locally. Rejected: installing Blender in
CI.

### D-4. Categorized CI and a prebuilt image, before slice 1

Owner decision 2026-09-29. Moskophoros adopts the owner's CI features from
their other projects: groups selected by category, optional groups run only on
explicit request, and a prebuilt cache image. This is its own epic, delivered
before the slice 1 product epic. Rejected: putting CI slices inside the slice 1
epic, or building slice 1 first on the current simple CI.

### D-5. Python 3.13

Owner decision 2026-09-29. CI and the image run Python 3.13, and the package
requires 3.13 or later. 3.13 is the Python Blender 5.2 bundles, so the tool and
its capture backend run and are tested on the same version; the owner's local
3.14 still satisfies the requirement. Rejected: 3.12 (the runners' default),
3.14 (the owner's local version), and a tested range of versions, which would
multiply CI runs and images.

### D-6. ruff lint and format checks, in the mandatory floor

Owner decision 2026-09-29. ruff checks linting and formatting on every
candidate. No type checker for now; one can be added later if type errors
appear. Rejected: adding mypy or pyright now, and running no static checks.

### D-7. A required, structured report for local-only groups

Owner decision 2026-09-29. When a pull request affects a local-only group, its
body must carry a structured block stating, for each such group, whether it was
run, and its result or the reason it was not. The planner checks the block
against the local-only groups the plan selects, and `build-test` fails while
the report is missing or incomplete. Rejected: the same block as advisory only,
and free text nothing checks.

### D-8. This epic sets up the Python test harness

Owner decision 2026-09-29. This epic adds the minimal `pyproject.toml`, the
pytest and ruff configuration and the `blender` marker, so the catalog
registers real groups and CI checks them from the start. Slice 1's skeleton
then adds the package's contents and its command; the empty package itself
comes from this epic (reworded by D-18, 2026-09-29). Rejected: leaving the
harness to slice 1's skeleton.

### D-9. Start with a few coarse groups

Owner decision 2026-09-29. The catalog starts with about four groups: static
checks (floor), workflow tests, package tests, and Blender tests (local-only).
Nearly any code change runs the whole fast suite; a group is split once it
grows slow. Rejected: fine-grained groups per module, which would cost catalog
upkeep while the code is still taking shape.

### D-10. One catalog of test groups

Owner approval 2026-09-29 (proposal P-1). Groups are declared once, each with a
stable ID, the command that runs it, the paths that affect it, and a
classification: mandatory floor, affected (non-optional), optional, or
local-only. Groups sit at behavioral boundaries, not one per test file. Local
commands, CI and agents all read the same catalog. Paths are matched by
explicit patterns, not a dependency graph.

### D-11. Requests in the pull request body

Owner approval 2026-09-29 (proposal P-3). A fenced `validation-request` block
lists catalog IDs, one per line, as in Hetoimasia. A request only adds
coverage; it can never remove the floor or an affected group. Requesting a
local-only group adds a local obligation (D-7); it never runs on GitHub.

### D-12. Leave out what a small Python project does not need

Owner approval 2026-09-29 (proposal P-5). Evidence receipts and reuse, runner
classes, sharding, display and GPU workers, and review-replay provenance are
left out. They earn their cost in Hetoimasia's slow Haskell and Vulkan builds;
moskophoros's tests are expected to run in seconds, so rerunning is cheaper
than proving reuse. Revisit if CI time grows. P-8's freshness rule is not
evidence reuse: it only checks that a report still describes the code.

### D-13. The planner's comparison rules

Owner approval 2026-09-29 of proposal P-2 as revised after review (concern 8):
three-dot comparison for pull requests, tested on GitHub's merge commit;
`before..after` for pushes; renames count as both paths; and anything that
cannot be compared, or is unclaimed, selects every non-optional group. See
[P-2](#p-2-a-planner-that-explains-itself-with-a-defined-comparison-d-13).

### D-14. The image's fingerprint and descriptor lifecycle

Owner approval 2026-09-29 of proposal P-4 as revised after review (concerns 3
and 4): the fingerprint covers exactly `tools/ci-image/`, the lock file and the
image workflow, excluding the descriptor; the author commits the descriptor in
the recipe-changing pull request; and a stale descriptor fails `build-test`.
See [P-4](#p-4-a-prebuilt-image-published-once-per-recipe-d-14).

### D-15. The initial groups

Owner approval 2026-09-29 of proposal P-6 as revised after review (concerns 1
and 7): `check.static` keeps the vendored helpers' syntax checks, and
`test.blender` is affected by the whole package, so nearly every package pull
request carries a local Blender obligation. See
[P-6](#p-6-the-initial-groups-d-15).

### D-16. Editing a pull request body replans

Owner approval 2026-09-29 of proposal P-7 (concern 2): CI runs on body edits,
superseded runs are cancelled, and the aggregate fails if the body changed
since it planned. See
[P-7](#p-7-a-pull-request-body-change-replans-d-16).

### D-17. Fresh local-only reports; pushes do not check them

Owner approval 2026-09-29 of proposal P-8 (concerns 5 and 6), refining D-7: a
report names the commit its tests ran at and goes stale when the group's paths
change after it; push plans list local-only obligations as omitted, "verified
on the pull request". See
[P-8](#p-8-local-only-reports-must-be-fresh-and-pushes-do-not-check-them-d-17).

### D-18. The harness creates an empty package; slice 1 fills it

Owner decision 2026-09-29, resolving Q-6 with option A (concern 9). CIF-1
creates an importable `moskophoros` package holding only its version, with one
smoke test, and no command. `AGENTS.md` lists only commands that work after
each slice; slice 1 adds the package's contents, the command and
`moskophoros --help`. This rewords D-8's consequence. Rejected: option B, a
harness with no package and two initial groups, which would have changed D-9.

## Open questions

### Q-1. Which Python version do CI and the package target?

Resolved by D-5.

### Q-2. Which static checks join the tests?

Resolved by D-6.

### Q-3. How does a pull request report local-only groups?

Resolved by D-7.

### Q-4. Who owns the pytest harness setup?

Resolved by D-8.

### Q-5. How finely are groups split at first?

Resolved by D-9.

### Q-6. Where is the line between the test harness and the product package?

Resolved by D-18 (option A).

## Verification strategy

- **Planner:** pytest cases over fixture catalogs and fixture Git histories,
  covering every selection reason, request parsing, errors and unclaimed paths.
- **Workflow:** a test that the workflow runs exactly the planned groups, and
  that `build-test` fails on any unexpected skip, failure or missing group.
- **Image:** the published image's recorded fingerprint matches the recipe,
  and CI refuses an image whose digest does not match the pin.
- **Live check:** a docs-only pull request, a code pull request and a request
  pull request each show the expected plan and checks.

## Delivery plan

Approved by the owner 2026-09-29.

### CIF-1. Set up the pytest and ruff harness and run it in CI

- **Outcome:** the harness commands in `AGENTS.md` §Build and test work, and
  CI runs ruff and pytest on Python 3.13, over an empty `moskophoros` package
  (D-18).
- **Scope:**
  - a minimal `pyproject.toml` requiring Python 3.13 or later, with pytest and
    ruff as development dependencies, and a lock file of exact versions
  - pytest configuration with the `blender` marker, and ruff configuration
    that excludes the vendored Kanban files
  - an importable `moskophoros` package holding only its version, with one
    smoke test, and no command (D-18)
  - the existing `tools/` tests running under pytest
  - `ci.yml`'s `build-test` running ruff, pytest (excluding `blender`) and the
    vendored helpers' syntax checks on 3.13, until CIF-4 replaces it
  - `AGENTS.md` §Build and test listing only commands that work after this
    slice
- **Phase:** 1
- **Depends on:** none
- **Ordering:** critical path, can land first
- **Relevant decisions:** D-1, D-5, D-6, D-8, D-18
- **Acceptance signals:** a clean clone passes every command `AGENTS.md` lists
  on 3.13; `build-test` runs ruff, pytest and the helper syntax checks; the
  vendored files are byte-identical to before.
- **Out of scope:** the catalog, the planner, the image; the `moskophoros`
  command, which is slice 1's.
- **Open questions:** None

### CIF-2. Declare test groups in a catalog and explain which ones a change needs

- **Outcome:** the catalog and planner exist and run locally, with P-6's groups
  registered.
- **Scope:** the catalog format (D-10), the planner and its comparison rules
  (P-2), requests (D-11), the local-only report check with freshness (D-7,
  P-8), the initial groups (P-6), and documentation of how to register and
  request a group. `AGENTS.md`'s Blender rule points to the catalog.
- **Phase:** 1
- **Depends on:** CIF-1
- **Ordering:** critical path
- **Relevant decisions:** D-1, D-3, D-6, D-7, D-9, D-10, D-11, D-13, D-15, D-17
- **Acceptance signals:** the planner's explanations match hand-built fixture
  histories for every selection reason, including a rename out of a group's
  paths, a force push and missing history; an invalid catalog, an unknown
  requested group, a missing or incomplete local-only report and a stale
  report are each errors with a diagnostic.
- **Out of scope:** running anything on GitHub; the image.
- **Open questions:** None

### CIF-3. Build and publish the CI image once per recipe, addressed by digest

- **Outcome:** `ghcr.io/coghex/moskophoros-ci` exists, pinned by digest, built
  only when its recipe fingerprint changes.
- **Scope:** the recipe (Python 3.13 and CIF-1's locked development
  dependencies), the fingerprint over its defined inputs, the descriptor, and
  the publishing workflow, following P-4's update lifecycle.
- **Phase:** 1
- **Depends on:** CIF-1 (for the lock file)
- **Ordering:** independent of CIF-2
- **Relevant decisions:** D-4, D-5, D-6, D-14
- **Acceptance signals:** rebuilding an unchanged recipe publishes nothing
  new; changing any fingerprint input, including the lock file alone,
  publishes a new digest; committing the descriptor leaves the fingerprint
  unchanged; the image reports its pinned versions, including Python 3.13 and
  ruff.
- **Out of scope:** Blender.
- **Open questions:** None

### CIF-4. Run the planned groups on GitHub behind an honest `build-test`

- **Outcome:** the planner decides what runs on every pull request and push,
  groups run in the image, and `build-test` is the required aggregate.
- **Scope:** replacing CIF-1's interim `ci.yml`; reading requests and
  local-only reports from the pull request body, with P-7's replanning on body
  edits; P-8's push behavior; the check that the descriptor matches the
  candidate (P-4); the aggregate; and `AGENTS.md` updates.
- **Phase:** 2
- **Depends on:** CIF-2, CIF-3
- **Ordering:** critical path
- **Relevant decisions:** D-3, D-4, D-5, D-6, D-7, D-13, D-14, D-16, D-17
- **Acceptance signals:** the live check in the verification strategy,
  including: a pull request that affects a local-only group fails
  `build-test` until a fresh report is added; editing the body to request a
  group reruns CI and selects it; a stale descriptor fails `build-test`.
- **Out of scope:** evidence reuse (D-12).
- **Open questions:** None
