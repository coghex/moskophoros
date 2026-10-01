# Slice 1 delivery design

Turn the accepted Moskophoros product design into the first working plain
3D-to-sheet pipeline, delivered through small, reviewable pull requests (PRs).
The input is animated binary glTF (`.glb`, called GLB below).
The product contracts remain in [the design](../design.md); this document owns
the delivery boundaries, dependencies and evidence needed to complete them.

Design state: `ready for issue processing`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]` reviewed and deliberately not tracked separately · `[deferred]` blocked on a concrete precondition

## Processing status

- [x] EPIC. Deliver the first plain animated GLB-to-sheet pipeline — [#24]
- [x] S1-1. Parse and validate the command-line options — [#25]
- [x] S1-2. Read GLB scenes and clips with generated fixtures — [#26]
- [x] S1-3. Define frame addresses, camera directions and sample times — [#27]
- [x] S1-4. Resolve scale and placement and detect overflow — [#28]
- [x] S1-5. Define the capture interface and launch Blender safely — [#29]
- [x] S1-6. Measure animated geometry and root travel in Blender — [#30]
- [x] S1-7. Render addressed frames with the accepted capture settings — [#31]
- [x] S1-8. Implement plain image reduction and pass-through cleanup — [#32]
- [x] S1-9. Assemble sheets and deterministic JSON descriptions — [#33]
- [x] S1-10. Generate animated direction previews — [#34]
- [ ] S1-11. Reuse sheet settings with explicit overrides
- [ ] S1-12. Connect the complete command and obtain owner acceptance

The owner approved these delivery boundaries and their dependencies on
2026-09-30 (D-4), and approved final command activation and owner acceptance
in S1-12 (D-5). These are not filed issue specifications. The umbrella epic
was filed as [#24](https://github.com/coghex/moskophoros/issues/24) on
2026-10-01; child issues are linked in the ledger above as they are filed.

## Epic contract

- **Goal:** `moskophoros [options] <infile.glb> <outfile.png>` produces the
  accepted sheet, JavaScript Object Notation (JSON) description and animated
  previews, with consistent scale and placement across clips and directions.
- **Done when:** the accepted automated checks pass; an owner's real animated
  character with a looping and a one-shot clip renders in eight directions at
  the owner's intended production size; the owner reviews and approves the
  sheet and previews. See [design §Slice 1 acceptance](../design.md#slice-1-acceptance).
- **Users and operators:** the owner producing game art, and agents maintaining
  the generic command-line tool. No game integration is part of completion.
- **Arc label:** None proposed.

## Current state and evidence

Checked on 2026-09-30 at repository revision
`4a9baa3a6ceec030d8ad7c24f5814ff07db6ac46`:

- `src/moskophoros/__init__.py` exposes the package version. There is no
  product command-line interface (CLI), GLB reader, camera or sampling logic,
  capture backend, image pipeline or exporter yet. `pyproject.toml` has no
  console-script entry and no runtime dependencies.
- The pytest and ruff harness, locked development dependencies, validation
  planner and prebuilt continuous integration (CI) image are implemented. The
  catalog already provides `check.static`, `test.workflow`, `test.package` and local-only
  `test.blender`; this arc can add tests beneath those existing groups.
- `tests/blender/test_smoke.py` proves that Blender starts headless and imports
  `bpy` in background mode. It fails on missing or invalid executables and
  never skips. It does not qualify the supported version or capture behavior.
- The [CI foundation design](ci_foundation_design.md) D-20 and D-21 require
  Blender tests under `tests/blender/` and a fresh passing local run for any
  selected obligation. [Validation](../validation.md) documents the implemented
  planner and reports. Use the published current validation contract when the
  docs-worktree copy has not yet incorporated later implementation changes.
- The latest [guide review](../guide/2026-09-30T135925Z-4a9baa3.md) examined
  the foundation repairs and recorded no new actionable finding: 241 local
  tests, including the Blender smoke test, passed at that revision.
- The accepted design records a completed Blender capture experiment and its
  observations in [§Supported Blender version](../design.md#supported-blender-version).
  That experiment supports feasibility; it is not implementation acceptance.
- The open tracker inventory contains only the CI foundation epic
  [#3](https://github.com/coghex/moskophoros/issues/3). No open pull request or
  overlapping slice 1 epic was found. Recheck overlap before readiness.
  Rechecked 2026-10-01: this arc's own epic #24 is now open, and every child
  issue of #3 is closed.

The owner resolved the missing-Blender testing disagreement (D-3), capture
contract (D-6) and retained-work-directory behavior (D-7) on 2026-09-30.
Their owning definitions are recorded in the product design. Those amendments
and this delivery document landed on `master` in commit `2651912`.

## Desired experience

The owner supplies an animated binary glTF (`.glb`) model and an output PNG
path. The command validates the input and options, evaluates the selected
clips at exact sample times, measures all frames before choosing a common
scale, captures them, reduces them to plain pixels and exports the results.

The default output includes a JSON description and per-clip animated previews.
The owner can fix or reuse settings to preserve scale and the ground pixel
across exports. Invalid input, forbidden root travel, fixed-setting overflow
and backend failure produce the accepted error codes and useful diagnostics.
Failed runs leave earlier outputs untouched.

These are accepted product behaviors, not newly proposed contracts. Their
exact values, formulas and formats stay in the owning design sections.

## Scope

### In scope

- The accepted CLI, defaults, options, validation and errors.
- GLB scene and clip reading, with fixtures generated by tests.
- Pure camera, direction, sample-time, fitting and overflow logic.
- The separate Blender measure and render processes and their capture boundary.
- Addressed frames through capture, plain stylize, pass-through cleanup and export.
- PNG sheets, deterministic metadata and fingerprints, animated previews and
  settings reuse.
- Mechanical integration evidence and owner visual acceptance.
- The tests, dependency pins and documentation each implementation change needs,
  delivered together in its own PR.

### Out of scope

All [design §Deferred](../design.md#deferred) items remain deferred, including
auxiliary buffers, style configuration, caching, variants, extra formats,
perspective and vertex-color rendering. No editor, custom renderer, standalone
image-command suite or game integration is added by this arc.

## Design

### Existing contracts

The accepted design owns the CLI and exit codes, input expectations, geometry,
clip isolation and sampling, root motion, scale and ground-point resolution,
capture settings, plain reduction, output layout and metadata, previews,
settings reuse and reproducibility. This delivery document links to those
contracts rather than maintaining a second definition.

Stages communicate through frame addresses and outputs. Only
`capture/blender_script.py` imports `bpy`, inside Blender's process. Pure
geometry, sampling, fitting and layout remain independent of process and
filesystem effects. Image operations remain reusable library functions.

### P-1. Refine the agreed overview into one-PR delivery boundaries — accepted by D-4

The owner endorsed this overview on 2026-09-30:

1. CLI and input validation.
2. Camera and sampling, including frame identities.
3. Scale and placement.
4. Blender measurement and root-motion detection.
5. Rendering and export through the plain image pipeline.
6. Previews and settings reuse.
7. Owner acceptance with a real animated character.

This is a high-level sequence, not seven approved issue specifications.
The approved twelve slices below separate the reader from option parsing,
the process boundary from Blender implementation, image operations from
export, and previews from settings reuse. This keeps each change independently
testable and leaves a small final integration PR to exercise the whole tool.

### P-2. Activate the console command only when it can complete a run — accepted by D-5

S1-1 supplies option parsing, validation and help-generation logic, tested as
library code. S1-12 adds the `moskophoros` console-script entry when all stages,
previews and settings reuse are available. Interim documentation describes
implemented components as components, rather than advertising a working
render command. The owner accepted this sequencing in D-5.

An earlier installable command is a reasonable alternative, but its behavior
for valid render requests while stages are absent would need an explicit
temporary contract. The accepted product design defines no such contract.

### P-3. Establish the shared capture contract before implementing both modes — accepted by D-6

S1-3 defines frame addresses and sampling independently of Blender. S1-5
implements the outside-Blender launcher and validates the accepted job and
result formats; S1-6 and S1-7 implement the two backend modes against them.
The caller owns clip selection, sample times, directions, fitting and final
fingerprinting. The backend evaluates the request and returns addressed
measurement data or named image buffers with actual provenance.

The single authoritative field definition and failure/lifecycle contract now
lives in [design §Capture job and result contract](../design.md#capture-job-and-result-contract).
Capture archives are internal debugging artifacts; their retention does not
create replay or cache compatibility. Blender waits for completion, failure
or caller interruption without a fixed render deadline. These choices are
accepted by D-6, not implementation suggestions to reopen during processing.

### P-5. Require an empty explicitly retained work directory — accepted by D-7

The owner accepted a new or empty explicitly supplied workspace, refusal of
nonempty directories without touching their contents, separate measure/render
directories and retention after success or failure. The owning definition is
[design §CLI](../design.md#cli). D-7 rejects allocating fresh subdirectories
inside an existing nonempty parent, so there is no extra naming/discovery
contract to implement.

### P-4. Finish with one implementation PR that carries owner acceptance — accepted by D-5

S1-12 connects already-tested components, makes the command available,
demonstrates generated-fixture reproducibility and includes the owner's
real-character review before final review and merge. Its tracked Markdown
evidence records the exact command, input hash, tools, settings, output
locations and owner's verdict. Models, sheets, previews and capture directories
stay outside Git as [AGENTS.md](../../AGENTS.md#files) requires.

The owner supplies the character, identifies the production size and judges
the output. If those inputs are unavailable, S1-12 remains incomplete; agents
cannot substitute a mechanical pass for acceptance. Repairs uncovered by that
review stay in the final implementation PR with its evidence and documentation.

### Dependency order

The processing order below is dependency-valid, but it is not an instruction
to run everything serially. Independent logic can be developed without
waiting for Blender work. Shared-file overlap still needs coordination.

| Slice | Required predecessors | Observable result |
|---|---|---|
| S1-1 | none | Validated explicit options and generated help |
| S1-2 | none | Parsed scenes/clips and reusable generated models |
| S1-3 | S1-2 | Addressed samples and camera/direction math |
| S1-4 | S1-3 | One fitted configuration and precise overflow reports |
| S1-5 | S1-1, S1-2, S1-3, S1-4 | Capture contract and outside-Blender launcher |
| S1-6 | S1-5 | Measured bounds and root travel from real Blender |
| S1-7 | S1-6 | High-resolution addressed PNGs |
| S1-8 | S1-3 | Plain addressed pixel frames |
| S1-9 | S1-4, S1-5, S1-8 | Sheet and deterministic description from supplied frames |
| S1-10 | S1-9 | Per-clip motion previews |
| S1-11 | S1-1, S1-4, S1-9 | Reused settings and tested explicit overrides |
| S1-12 | S1-7, S1-10, S1-11 | Complete command, integration evidence and owner verdict |

### Delivery constraints inherited from the repository

One issue, one isolated worktree and one PR per delivery slice. Required
documentation and evidence belong in that implementation PR. This planning
document and the explicitly approved product-design correction are standalone
documentation in `docs-wip`; neither is published by this workflow.

Add each runtime dependency only in its first consuming slice, with supported
minimums and a regenerated Python-compatible lock. The S1-5 buffer
validator needs Pillow; S1-7 uses it to inspect rendered integration-test images;
S1-8 needs NumPy for reduction and Pillow for image handling. Whichever consuming
slice lands first introduces its dependencies. Coordinate their shared lock/image changes. Each affected PR
follows the existing image-publication and descriptor lifecycle because the lock
is a recipe input. No new framework or dependency is proposed.

Tests generate their own fixtures in temporary directories. Tests requiring
Blender live under `tests/blender/` with the registered marker. Package-code
and dependency changes normally select `test.blender`, even for pure logic:
run the selected local group and supply the fresh passing report. Keep tests
in the existing groups; do not create a group for each slice.

## Decisions

### D-1. Implement the accepted slice 1 product contracts

Inherited owner decision from the accepted vision and product design,
2026-09-29. The first product milestone is the plain animated GLB-to-sheet
pipeline. Preserve its existing scope and observable acceptance; do not
invent style requirements or treat passing tests as visual approval.

### D-2. Use the proposed high-level delivery sequence as the starting point

Owner signoff in this conversation, 2026-09-30: “ok sounds good,” followed by
a request to make the design document. P-1 preserves the enumerated overview.
The detailed delivery choices are recorded in D-4 and D-5. D-6 and D-7
settle the shared capture contract and retained-work-directory behavior.

### D-3. Missing Blender fails selected integration tests

Owner decision 2026-09-30, explicitly approving the proposed testing policy
and correction to [design §Testing](../design.md#testing). Selected Blender
tests fail with a clear diagnostic if Blender is unavailable. Developers
intentionally running only fast tests use `pytest -m "not blender"`.
A skip cannot satisfy a local-only obligation. Q-1 is resolved by this
decision; the owning testing paragraph was updated in the docs worktree.

### D-4. Deliver the arc through the twelve listed slices

Owner decision 2026-09-30: explicit approval of the twelve-slice breakdown
and its listed dependencies in this conversation. S1-1 through S1-12 and the
matching processing ledger are the accepted delivery boundaries. Component
tests establish useful intermediate results; only the completed product meets
the arc-level acceptance. Q-2's breakdown choice is resolved by this decision.

### D-5. Activate the command and complete owner acceptance in S1-12

Owner decision 2026-09-30: explicit approval of command activation in the
final integration PR, with real-character evidence and owner visual approval
before review and merge. Earlier slices expose tested library components;
S1-12 adds the console entry and working-command documentation. Required
evidence stays in that implementation PR. Rejected: an installed command in
S1-1 with a temporary incomplete-render contract. Q-2's activation choice is
resolved by this decision.

### D-6. Use the accepted capture job and result contract

Owner decision 2026-09-30: explicit approval of P-3's proposed formats and
rules. Versioned JSON jobs/results bind the submitted request, source and
exact frame set; original indices identify imported clips and nodes; the
launcher validates results and buffers before handing frames onward. Actual
render provenance feeds the sheet fingerprint separately from the transport
job hash. Source edits fail capture, and failures leave final outputs intact.
Capture archives are internal debugging artifacts, with no replay/cache
compatibility promise. Waits end on completion, failure or caller interruption,
with no fixed render deadline. The contract now lives in
[the product design](../design.md#capture-job-and-result-contract), so its
fields and meanings have one authority. Q-3 is resolved by this decision.

### D-7. Retain captures only in a new or empty explicit workspace

Owner decision 2026-09-30: explicit approval of P-5. `--work-dir` rejects an
existing nonempty directory with a usage error and leaves its contents
untouched. A new or empty workspace gets separate measure/render directories
and retains available capture artifacts after success or failure. Normal
temporary capture directories are deleted. The rule is recorded in
[design §CLI](../design.md#cli). Rejected: allocating fresh subdirectories
under a nonempty parent. Q-4 is resolved by this decision.

### D-8. S1-12 rejects a nonempty `--work-dir`; S1-1 only parses the path

Owner decision 2026-10-01, answering which slice enforces D-7's usage error.
S1-1 parses `--work-dir DIR` as a path and never inspects the filesystem.
S1-12 checks that `DIR` is absent or empty at the point where it creates the
capture workspace, as part of the workspace lifecycle it already owns. That
keeps the parser free of filesystem reads and puts the check and the creation
together, with no window for the directory to change between them. Rejected:
checking in the S1-1 parser, which reports earlier but reads the disk during
option validation and still leaves S1-12 to handle a directory that changes
before use. The product rule in [design §CLI](../design.md#cli) is unchanged.

### D-9. Settle the option-validation rules design §CLI left unstated

Owner decision 2026-10-01: explicit approval of all eight P-6 rules listed
under Q-5, recorded in the product contract rather than only in an issue. They
now live in [design §Option validation](../design.md#option-validation), which
is their single authority. Rejected: filing S1-1 with an open-question section
for its solver to stop and ask, and letting a repeated single-value option
keep its last value. Q-5 is resolved by this decision.

### D-10. Without `--clip`, clips follow the file's animation order

Owner decision 2026-10-01: every clip is selected in ascending animation
index. This matches how the capture job identifies clips; a re-export that
reorders animations reorders the sheet. Recorded in
[design §CLI](../design.md#cli). Rejected: sorting by name, which is stable
across re-exports but may not follow the author's intended order. Q-6 is
resolved by this decision.

### D-11. The reader rejects malformed structure it relies on as an input error

Owner decision 2026-10-01: references the tool follows (`scene`, node,
child, channel, sampler, accessor), a non-forest node hierarchy, and a
sampler input accessor without one-element `min`/`max` are input errors
(exit 3) naming the file and problem (V-11). Other glTF rules are left to
Blender's importer. Recorded in
[design §Input contract](../design.md#input-contract). Rejected: checking only
the originally listed items and letting other malformations surface as
backend errors or reader crashes. Q-7 is resolved by this decision.

### D-12. An empty animation name counts as no name

Owner decision 2026-10-01: `"name": ""` is an input error giving the
animation's index, like a missing name. An empty name cannot be selected with
`--clip` or form a preview filename. Recorded in
[design §Input contract](../design.md#input-contract). Rejected: accepting
`""` as a clip name. Q-8 is resolved by this decision.

### D-13. S1-1 owns view-preset resolution; S1-3 takes a resolved view

Owner decision 2026-10-01, settling an overlap found while drafting S1-3:
S1-3's scope listed "presets, overrides", which S1-1 (#25) already
implements. S1-1 keeps preset resolution and the `custom` rule, matching
[design §Project layout](../design.md#project-layout) (presets in `cli.py`,
camera and direction math in `views.py`). S1-3 takes an already-resolved
pitch, direction count, start angle and model yaw as plain values, so it still
depends only on S1-2. Rejected: moving presets into S1-3, which would have
required editing the filed S1-1 issue.

### D-14. A computed cell over 4096 pixels is a usage error

Owner decision 2026-10-01, raised while drafting S1-4: with only `--ppm`,
the cell is computed and had no upper bound. A computed width or height over
4096, the `--cell` limit, is now a usage error giving the size and suggesting
a smaller `--ppm`. Recorded in
[design §Scale and ground point](../design.md#scale-and-ground-point).
Rejected: no limit, which lets a mistaken scale produce a runaway sheet.

### D-15. Overflow reports overshoot in whole pixels, rounded up

Owner decision 2026-10-01, raised while drafting S1-4: each side's overshoot
is reported in whole pixels rounded up, so any overshoot shows as at least
1 px. Recorded in
[design §Scale and ground point](../design.md#scale-and-ground-point).
Rejected: fractional pixels, which are exact but noisier and depend on float
formatting.

### D-16. The first configured Blender source decides

Owner decision 2026-10-01, raised while drafting S1-5: if `--blender` or
`$MOSKOPHOROS_BLENDER` is set but names a missing or non-executable file,
discovery fails with a backend error naming the source and path, and later
sources are not tried. Recorded in [design §Capture](../design.md#capture).
Rejected: falling through to the next source, which could silently run a
different Blender than the one requested.

### D-17. An unparseable Blender version is always a backend error

Owner decision 2026-10-01, raised while drafting S1-5: `--any-blender`
allows a different version, never an unknown one, so the sheet can always
record `generator.blender`. The error quotes the output's first line.
Recorded in [design §Capture](../design.md#capture). Rejected: accepting the
raw first line as the version under `--any-blender`.

### D-18. The fingerprint hashes an object that mirrors the sheet

Owner decision 2026-10-01, raised while drafting S1-9: the hashed object is
`{"generator": …, "settings": …, "source": {"sha256": …}}`, so a fingerprint
can be recomputed from a sheet by keeping those parts. Recorded in
[design §Export](../design.md#export). Rejected: a flat `source_sha256` key.

### D-19. The sheet JSON keeps the example's key order, indented

Owner decision 2026-10-01, raised while drafting S1-9: keys in design
§Export's example order, 2-space indentation, UTF-8 with non-ASCII kept,
shortest round-trip floats and a trailing newline. Recorded in
[design §Export](../design.md#export). Rejected: canonical compact JSON, which
is hard to read and diff.

### D-20. Sheet JSON records base names, not paths

Owner decision 2026-10-01, raised while drafting S1-9: `source.file` and
`image.file` are base names, so the JSON is identical wherever the command
runs. Recorded in [design §Export](../design.md#export). Rejected: the path as
typed, which varies by directory and machine.

### D-21. Previews keep exact colors when they can, and never dither

Owner decision 2026-10-01, raised while drafting S1-10: a GIF frame holds at
most 256 colors. A frame within that limit keeps its exact colors; one over
it is reduced to 256 without dithering, with a warning naming the clip.
Recorded in [design §Export](../design.md#export). Rejected: Pillow's default
dithered reduction, which adds noise the sheet does not have, and failing the
run, which would block most real characters.

### D-22. Preview directions are packed with no gap

Owner decision 2026-10-01, raised while drafting S1-10: directions sit side
by side like sheet cells, so a preview shows the real cell boundaries.
Recorded in [design §Export](../design.md#export). Rejected: a one-pixel gap.

### D-23. Preview filenames take the next free suffix

Owner decision 2026-10-01, raised while drafting S1-10: in sheet order, each
clip takes its sanitized name if free, else the smallest unused `-2`, `-3`, …
suffix, counting other clips' own names, so no preview overwrites another.
Recorded in [design §CLI](../design.md#cli). Rejected: refusing the run.

### D-24. An explicit `--view` replaces the whole reused view

Owner decision 2026-10-01, raised while drafting S1-11: with
`--settings-from`, an explicit `--view` resolves exactly as without reuse,
and the reused view is ignored. Without it, the reused view stays and
individual overrides make the preset `custom`. Recorded in
[design §Scale and ground point](../design.md#scale-and-ground-point).
Rejected: refusing `--view` with `--settings-from`.

### D-25. Reused settings are validated strictly

Owner decision 2026-10-01, raised while drafting S1-11: every reused field
must be present and acceptable to its option, `projection` must be
`orthographic`, and the fixed values must be set. Unknown fields inside
`settings` are a usage error. Recorded in
[design §Scale and ground point](../design.md#scale-and-ground-point).
Rejected: ignoring unknown fields, which could silently drop settings.

## Open questions

### Q-1. Should missing Blender fail selected integration tests?

Resolved by D-3. Rejected: keeping missing-Blender skips and amending the
working/report contracts to accommodate them. The selected group must prove
its tests ran; a passing environment smoke test cannot stand for skipped
capture integration tests.

### Q-2. Accept the proposed delivery boundaries and final command activation?

Resolved by D-4 and D-5. The twelve listed boundaries and final command
activation are accepted. The alternative early-command contract was rejected.

### Q-3. What exact capture job and result contracts will the slices share?

Resolved by D-6. The accepted contract is now in
[design §Capture job and result contract](../design.md#capture-job-and-result-contract).
No capture-schema or lifecycle decision remains open for these slices.

### Q-4. May an explicitly retained work directory already contain files?

Resolved by D-7. The owner selected a new or empty workspace and rejected
fresh per-run subdirectories inside a nonempty parent. See the owning
[CLI contract](../design.md#cli). No workspace-policy decision remains open.

### Q-5. Which option-validation rules does design §CLI leave unstated?

Resolved by D-9; all eight rules below were approved as written.

Raised 2026-10-01 while drafting S1-1. Design §CLI gives each option's type,
default and range, but not these rules, several of which choose between a
usage error (exit 2) and an input error (exit 3) or between rejecting and
accepting a command line. The owner chose to settle them in design §CLI as a
dated owner decision before S1-1 is filed, rather than leaving the solver to
stop and ask. The rules proposed for signoff (P-6):

1. Numeric options reject `nan` and `inf` as usage errors.
2. `--start-angle` and `--model-yaw` accept any finite value; the parser keeps
   the given value, and the existing `mod 360` in the direction formula
   (S1-3) handles wrapping.
3. `--ground-px X,Y` takes whole numbers 0 or greater; whether the point lies
   inside the cell is left to overflow checking (S1-4).
4. Naming the same clip twice with `--clip`, or twice with `--once`, is a
   usage error.
5. A `--once` naming a clip absent from an explicit `--clip` list is a usage
   error. Without `--clip`, an unknown name stays an input error found by the
   reader (S1-2).
6. Giving a single-value option more than once is a usage error, not
   "last one wins".
7. A usage error prints the usage synopsis, then
   `moskophoros: error: <message>`.
8. `<infile.glb>` has no suffix requirement; its content is checked by the
   reader (S1-2).

Affects S1-1 and the product contract it implements.

### Q-6. Without `--clip`, in what order are clips selected?

Resolved by D-10. Raised 2026-10-01 while drafting S1-2: design §CLI said
"every clip" without an order, which fixes the sheet's rows, JSON and
fingerprint.

### Q-7. How strictly does the reader validate glTF structure?

Resolved by D-11. Raised 2026-10-01 while drafting S1-2: the input contract
listed specific checks but not dangling references or missing accessor
bounds the reader depends on.

### Q-8. Is an empty animation name a name?

Resolved by D-12. Raised 2026-10-01 while drafting S1-2.

## Readiness

Reopened 2026-10-01: D-8 moved the `--work-dir` emptiness check between
slices, and D-9 added option-validation rules to the product contract. All
five design questions were resolved and the owner signed off readiness again
on 2026-10-01.

Reopened again 2026-10-01: D-10, D-11 and D-12 amended the product contract
for S1-2. All eight design questions are resolved, and the owner signed off
readiness again on 2026-10-01. The ledger, slice
order and dependencies are unchanged, and the only open epics are #3 and this
arc's own #24.

Previously: all four design questions were resolved and the owner had approved
the seven recorded decisions. The twelve-slice processing ledger matches the delivery plan,
dependencies are ordered, and the owning product contracts have been amended.
The tracker was rechecked on 2026-09-30: no overlapping open product epic or
PR was found. Model availability, production size and the final visual verdict
are explicit execution gates for S1-12, not unanswered design questions.

The owner explicitly declared the design ready for issue processing on
2026-09-30. No prior product implementation requires migration; the accepted
sheet schema and settings-reuse contract define compatibility, and capture
retention remains an internal debugging facility.

Readiness does not publish documents or authorize tracker creation.
`process-design-doc` processes the epic first, then exactly one child per
invocation, with separate approval for every tracker artifact.

## Verification strategy

The accepted design calls for generated fixtures and tests of camera math,
directions, clip timing, fitting, overflow, GLB errors, image reduction,
layout, metadata, settings reuse and deterministic output. Blender integration
tests must establish known evaluated bounds, root-motion detection and output
reproducibility. D-3 requires failures when Blender is missing.

Use the existing validation groups and the planner's selected obligations.
No test result establishes visual quality. Final owner review uses the actual
production size, the sheet and the motion previews. Exact issue acceptance
commands and evidence locations are refined during issue processing.

Use known simple geometry to distinguish correct bounds from a plausible
image; include transforms, skinning, morphs and successive clip isolation in
generated fixtures. Test root-motion error/keep behavior and preservation of
vertical motion. Check fixed settings that overflow instead of silently shrinking.

For exports, test independently expected sheet coordinates, canonical
fingerprints, transparent unused cells and deterministic bytes. Verify the
accepted reduction's alpha threshold and rounding with small arrays. Previews
need direction order, durations, endpoint hold and filename-collision tests.

The complete command must demonstrate two byte-identical PNG/JSON runs under
the same recorded tools, clear failures in each accepted exit-code class,
settings reuse with overrides, and preservation of existing outputs after a
failed run. Test publication failure as well as failures before export: writing
several temporary files alone does not establish the whole-run guarantee.

## Delivery plan

The delivery boundaries below are accepted by D-4 and D-5. Their product
behavior comes from D-1, with the accepted testing, capture and workspace
amendments in D-3, D-6 and D-7, and D-8 places the `--work-dir` check in
S1-12. D-9 settles the option-validation rules S1-1 implements. All design
questions are resolved. The listed
phase numbers describe dependency layers, not milestones with separate
product acceptance.

### S1-1. Parse and validate the command-line options

- **Outcome:** a tested parser for the accepted CLI,
  including help and explicit-option tracking for later reuse.
- **Scope:** option types, ranges and combinations; paths and output suffix;
  preset-versus-explicit inputs; usage-error formatting. File/clip validation
  belongs to S1-2 and orchestration to S1-12. `--work-dir` is parsed as a path
  only; the parser never inspects the filesystem (D-8). The rules in design
  §Option validation (D-9) that a parser can check without the input file.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** critical path; can land first.
- **Relevant decisions:** D-1, D-2, D-3, D-4, D-5, D-8, D-9.
- **Acceptance signals:** valid options parse without effects; invalid usage
  gives the accepted diagnostic and exit classification; each D-9 rule has a
  tested outcome; help covers all options.
- **Out of scope:** installed console entry and rendering; the nonempty
  `--work-dir` check (S1-12, D-8); clip existence (S1-2).
- **Open questions:** None.

### S1-2. Read GLB scenes and clips with generated fixtures

- **Outcome:** the outside-Blender reader supplies scene, clip and root-analysis
  information required by the accepted input and timing contracts.
- **Scope:** container/JSON reading, default scene, subject naming, animation
  names/ranges, clip selection and one-shot validation. Supply a reusable
  pure-Python test writer for simple static and animated fixtures; extend it
  with skinning/morph/root-motion cases when their consumers arrive.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** critical path; independent of S1-1.
- **Relevant decisions:** D-1, D-3, D-10, D-11, D-12.
- **Acceptance signals:** generated valid inputs yield independently expected
  scene/clip data, with default selection in animation-index order (D-10);
  malformed inputs, including D-11's structural errors, and invalid or empty
  names (D-12) fail with file/clip context.
- **Out of scope:** implementing a renderer or duplicating Blender's importer.
- **Open questions:** None.

### S1-3. Define frame addresses, camera directions and sample times

- **Outcome:** pure functions and records enumerate the exact addressed samples
  and view geometry that all later stages share.
- **Scope:** subject/variant/clip/direction/time identity; sample index for
  layout only; camera basis, yaw, angles and labels from an already-resolved
  view (D-13); looping, one-shot, static and zero-duration timing.
- **Phase:** 2.
- **Depends on:** S1-2.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-4, D-6, D-13.
- **Acceptance signals:** independently calculated vectors and times cover
  top-down and custom views, both endpoint policies and nonzero clip starts.
- **Out of scope:** Blender state, fitting, settings fingerprints, and preset
  resolution (S1-1, D-13).
- **Open questions:** None.

### S1-4. Resolve scale and placement and detect overflow

- **Outcome:** pure fitting resolves one configuration from aggregate bounds
  and reports every fixed-configuration overflow by frame address.
- **Scope:** all accepted scale/cell cases, margin, rounding, explicit ground
  pixel, degenerate bounds, size warnings and per-side overshoot diagnostics.
- **Phase:** 3.
- **Depends on:** S1-3.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-14, D-15.
- **Acceptance signals:** numeric fixtures prove each formula and that fixed
  or reused settings fail on overflow instead of shrinking.
- **Out of scope:** evaluating geometry or recomputing ground from a frame.
- **Open questions:** None.

### S1-5. Define the capture interface and launch Blender safely

- **Outcome:** an agreed, tested serialized boundary and an outside-Blender
  launcher for measure/render requests.
- **Scope:** common job/result validation; executable discovery and version
  check against the owning supported-version contract; required headless flags;
  invocation, captured diagnostics and backend-error mapping. Test with controlled
  fake processes; keep `bpy` inside the future script.
- **Phase:** 4.
- **Depends on:** S1-1, S1-2, S1-3, S1-4.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-4, D-6, D-7, D-8, D-16, D-17.
- **Acceptance signals:** precedence, version suffixes and override, launch
  failure, script failure and malformed output have independently tested outcomes.
  Under P-3, buffer validation also proves path containment, image mode and
  dimensions; pin Pillow when introducing that concrete use.
- **Out of scope:** real measurement, rendering and extra capture buffers.
- **Open questions:** None.

### S1-6. Measure animated geometry and root travel in Blender

- **Outcome:** the real measure mode returns bounds and root travel for all
  requested samples without rendering.
- **Scope:** import the selected subject; map clip/node identities; reset and
  isolate actions, animation layers, poses and morph defaults; evaluate skinned
  and morphed geometry in the accepted coordinates; report bounds and root travel.
- **Phase:** 5.
- **Depends on:** S1-5.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-4, D-6, D-7.
- **Acceptance signals:** generated geometry proves bounds, root ancestry and
  travel, vertical-motion preservation and absence of carry-over between clips.
- **Out of scope:** color images, fitting inside Blender and style.
- **Open questions:** None.

### S1-7. Render addressed frames with the accepted capture settings

- **Outcome:** render mode writes high-resolution color buffers and their
  addressed manifest for a resolved fixed configuration.
- **Scope:** selected mesh exclusion rules, fixed camera/ground projection,
  camera-relative lighting, texture/material color, transparent antialiasing,
  stamping disabled and named-buffer manifest. Reuse measurement's isolation.
  Pin Pillow if image-inspection tests first need it here, with the matching CI
  image and descriptor in this PR.
- **Phase:** 6.
- **Depends on:** S1-6.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-3, D-4, D-6, D-7.
- **Acceptance signals:** generated models cover dimensions, ground projection,
  import-added object exclusion, clip order independence and repeatable PNG bytes.
- **Out of scope:** pixel reduction, style and auxiliary buffers.
- **Open questions:** None.

### S1-8. Implement plain image reduction and pass-through cleanup

- **Outcome:** addressed capture arrays become addressed plain pixel frames.
- **Scope:** reusable image operations, accepted block coverage/color reduction
  and rounding, fully transparent pixel normalization, pass-through cleanup;
  add and pin NumPy and any still-missing Pillow dependency for this concrete use.
- **Phase:** 3; can proceed while capture is developed.
- **Depends on:** S1-3.
- **Ordering:** independent of the Blender implementation.
- **Relevant decisions:** D-1, D-3.
- **Acceptance signals:** small constructed arrays prove thresholds, alpha
  weighting, rounding and unchanged addresses; dependency/image checks pass.
- **Out of scope:** palettes, outlines, cel shading and new image commands.
- **Open questions:** None.

### S1-9. Assemble sheets and deterministic JSON descriptions

- **Outcome:** supplied addressed frames yield the accepted sheet layout and
  `moskophoros.sheet/1` description, ready for staged publication.
- **Scope:** clip/direction order, columns, transparent unused cells, frame
  rectangles, generator/source/settings metadata and canonical fingerprint;
  fixed PNG/JSON encoding and export helpers.
- **Phase:** 5; independent of real rendering after its interface is settled.
- **Depends on:** S1-4, S1-5, S1-8.
- **Ordering:** critical path; can proceed alongside S1-6 and S1-7.
- **Relevant decisions:** D-1, D-3, D-18, D-19, D-20.
- **Acceptance signals:** supplied frames and provenance yield independently
  expected coordinates, metadata, fingerprints and byte-identical repeated exports.
- **Out of scope:** previews, backend execution and whole-command publication.
- **Open questions:** None.

### S1-10. Generate animated direction previews

- **Outcome:** export helpers produce the accepted per-clip animated GIFs.
- **Scope:** all directions side by side, nearest-neighbor enlargement, gray
  background, rounded/minimum durations, loop behavior, one-shot endpoint hold
  and filename sanitization/collision handling.
- **Phase:** 6.
- **Depends on:** S1-9.
- **Ordering:** critical path to owner review; independent of S1-11.
- **Relevant decisions:** D-1, D-3, D-21, D-22, D-23.
- **Acceptance signals:** decode generated previews to verify geometry, clip
  timing, endpoint hold, background and unique filenames; `--no-preview`
  integration follows in S1-12.
- **Out of scope:** editor, alternate preview layouts and visual acceptance.
- **Open questions:** None.

### S1-11. Reuse sheet settings with explicit overrides

- **Outcome:** settings from an accepted sheet description combine with new
  explicit options while keeping scale, cell and ground pixel fixed.
- **Scope:** settings-file/schema validation, the accepted reusable values,
  override precedence and current-run clip/one-shot selection; use existing fit
  checks rather than a second overflow mechanism.
- **Phase:** 6.
- **Depends on:** S1-1, S1-4, S1-9.
- **Ordering:** critical path; independent of S1-10.
- **Relevant decisions:** D-1, D-3, D-9, D-24, D-25.
- **Acceptance signals:** independently expected reused values and overrides;
  malformed files are usage errors; a new clip that no longer fits fails rather
  than silently changing scale.
- **Out of scope:** caches, overrides for pixel touch-ups and new schema versions.
- **Open questions:** None.

### S1-12. Connect the complete command and obtain owner acceptance

- **Outcome:** an installed command completes the accepted product flow and
  carries the mechanical and owner evidence that closes the milestone.
- **Scope:** wire validated options, input, samples, two capture calls, root
  checks, fit, plain pipeline, sheets, previews and reuse; temporary/retained
  work-directory lifecycle, including rejecting an existing nonempty
  `--work-dir` as a usage error when the workspace is created (D-7, D-8);
  stage all outputs and preserve earlier outputs on failure; install the
  console entry and document the working command.
- **Phase:** 7.
- **Depends on:** S1-7, S1-10, S1-11.
- **Ordering:** final critical-path slice.
- **Relevant decisions:** D-1, D-3, D-4, D-5, D-7, D-8.
- **Acceptance signals:** generated-model command tests cover the complete
  output set, failure codes and publication failures, and a nonempty
  `--work-dir` that exits 2 with its contents untouched; repeated runs give identical
  PNG/JSON bytes. The owner approves a real character's eight-direction sheet
  and previews at the intended production size before final PR review and merge.
- **Out of scope:** deferred style and game integration; accepting mechanical
  tests in place of the owner's verdict; landing required evidence afterward.
- **Open questions:** None. Owner model, production size and visual verdict
  remain execution prerequisites; agents do not choose them or substitute tests.
