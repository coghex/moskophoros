# Validation

How moskophoros decides which checks a change needs, and the image they are
to run in. Test groups are declared once in a catalog, and a planner compares
two revisions and explains, for every group, whether the change selects it and
why. The decisions behind this are in the
[CI foundation design](designs/ci_foundation_design.md) (D-3 to D-7, D-10 to
D-17, D-19 to D-21).

This describes the catalog, the planner and its checks, the
[CI image](#the-ci-image) with its descriptor, and how GitHub runs the plan
behind the required `build-test` check ([On GitHub](#on-github)).

## The catalog

[`tools/validation/catalog.json`](../tools/validation/catalog.json) declares
every group once:

```json
{
  "schema_version": 1,
  "groups": [
    {
      "id": "test.package",
      "description": "pytest over the package's tests, excluding the blender marker.",
      "category": "affected",
      "commands": [
        [".venv/bin/pytest", "tests", "-m", "not blender"]
      ],
      "paths": ["src/", "tests/", "pyproject.toml", "requirements.lock"]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `id` | Stable, unique ID: dot-separated lower-case words, such as `test.package`. Requests and reports name groups by it. |
| `description` | One sentence saying what the group checks. |
| `category` | Exactly one of `floor`, `affected`, `optional`, `local-only` (below). |
| `commands` | The group's command: a non-empty list of steps, each an argument list, run in order from the repository root. The group passes when every step passes. |
| `paths` | Path patterns whose changes affect the group. Required and non-empty, except for a `floor` group, which may omit it. |

Each group's command is the exact command CI or a person runs for it. The
commands assume the virtual environment described in
[AGENTS.md](../AGENTS.md#build-and-test).

### Categories

- **`floor`:** always selected, for every change.
- **`affected`:** selected when a changed path matches its patterns, and
  whenever the planner fails wide.
- **`optional`:** selected only when a pull request requests it, never by
  path.
- **`local-only`:** never runs on GitHub. Selected, as a local obligation, when
  a changed path matches its patterns or a pull request requests it. The pull
  request must then report a passing local run.

### The groups

| Group | Category | Runs | Affected by |
|---|---|---|---|
| `check.static` | `floor` | `ruff check .`, `ruff format --check .`, the catalog validity check, `bash -n tools/docs_land.sh`, and compiling `tools/docs_land_paths.py` | every change |
| `test.workflow` | `affected` | `pytest tools`: the review-gate test, the planner's tests and the CI image tests | `tools/`, `.github/` |
| `test.package` | `affected` | `pytest tests -m "not blender"` | `src/`, `tests/`, `pyproject.toml`, `requirements.lock` |
| `test.blender` | `local-only` | `pytest -m blender`, on the owner's machine | `src/`, `tests/blender/`, `pyproject.toml`, `requirements.lock` |

Every Blender-marked test lives under `tests/blender/`, so changing an
ordinary test creates no Blender obligation. `test.blender` runs the Blender
smoke test in `tests/blender/test_smoke.py`, which starts Blender headless and
checks that it imports `bpy` in background mode. It finds Blender in the order
design §Capture gives, except `--blender`. A non-empty `$MOSKOPHOROS_BLENDER`
is used as given, with no fallback. When no Blender is found, the test fails
with the places it looked, and never skips, so only a machine with Blender can
report `test.blender` `passed`.

No `optional` group is registered yet.

### Path patterns

Patterns are matched against repository-relative paths, with `/` separators
and case-sensitively.

- A pattern ending in `/` names a directory and claims everything beneath it,
  at any depth: `src/` claims `src/a.py` and `src/x/y/z.py`, but not
  `srcs/a.py` or `lib/src/a.py`.
- Any other pattern names exactly one file: `pyproject.toml` claims only
  `pyproject.toml` at the repository root, not `pyproject.toml.bak` or
  `sub/pyproject.toml`. `src` without the slash claims only a file named
  `src`.

A pattern is invalid if it is not a non-empty string, starts with `/`, has
leading or trailing whitespace, contains `\`, `*`, `?` or `[` (there are no
wildcards), or has an empty, `.` or `..` segment. So there is no catch-all
pattern: a path is claimed only by a group that names it or its directory.

A path is **claimed** when any group's pattern matches it, whatever the
group's category. A `floor` group is selected unconditionally, but claims
nothing unless it declares patterns.

### Registering a group

1. Choose a stable ID and one category. Split a group only when it grows slow;
   groups sit at behavioral boundaries, not one per test file.
2. Add it to `catalog.json` with its description, its exact command, and the
   patterns that affect it.
3. Run the validity check and the planner's tests:

   ```sh
   python3 tools/validation/plan.py --catalog-check
   .venv/bin/pytest tools
   ```

4. Update this document's table of groups in the same pull request.

### The validity check

`plan.py --catalog-check` validates the catalog and exits 0 if it is valid, or
2 with one diagnostic per problem. It rejects malformed JSON (including a
duplicate key), a wrong `schema_version`, unknown keys, a duplicate or
malformed ID, a missing description, an unknown category, a missing command,
missing patterns on a group other than `floor`, and an invalid pattern. A
diagnostic names the group by its ID when it has one, by its position
(`groups[3]`) when it does not, and names the catalog file with the line and
column for malformed JSON.

## Selection rules

The planner compares one of two ranges:

- **Pull request range** (`--base`, `--head`): the paths changed between the
  merge base of the base and head, and the head. This is a three-dot
  comparison, the one GitHub shows.
- **Push range** (`--before`, `--after`): the paths changed between the two
  revisions.

Comparisons ignore rename detection, so a renamed file counts as both its old
and its new path, and affects the groups of both.

The planner selects:

- every `floor` group;
- every `affected` group matching a changed path;
- every `local-only` group matching a changed path, as a local obligation
  (pull request ranges only; see [Push ranges](#push-ranges));
- every group the pull request requests.

It never selects an `optional` group by path.

### Failing wide

The planner fails wide, never narrow. It selects every `floor` and `affected`
group, and states the cause in the plan, when:

- a changed path is claimed by no group;
- the comparison finds no changed paths, since nothing is ever treated as "no
  change";
- a push's `before` is all zeros, is not an ancestor of `after` (a force
  push), or is missing from history;
- any other comparison cannot be computed, such as a revision missing from a
  shallow clone.

Failing wide never adds a local-only obligation. A local-only group is
selected only by its own affected paths or by a request, so a docs-only pull
request never needs a Blender run, while any change under `src/` does.

Failing wide is a valid, conservative plan, not an error: on its own it exits
0.

### How every group is explained

The plan lists every catalog group once.

- **Selected**, with each reason that applies: `floor`; affected by the named
  paths; failing wide, with the cause; requested in the pull request.
- **Omitted**, with its reason: optional and not requested; not affected; or,
  for a local-only group in a push range, verified on the pull request.

## Pull request requests

A pull request asks for extra groups with one fenced block whose info string
is exactly `validation-request`, listing catalog IDs, one per line:

````markdown
```validation-request
test.package
```
````

A request only adds groups; it never removes the floor or an affected group.
Requesting a local-only group adds a local obligation, which never runs on
GitHub. These are errors:

- an unknown ID;
- a line naming more than one ID;
- more than one `validation-request` block;
- a block that is never closed;
- an info string that starts with `validation-request` but says anything
  else, such as `validation-request please` or `validation-request-extra`.

Only top-level blocks count. A block inside another fenced block, like the
example above, is documentation, not a request. A fence is read only when it
is indented by at most three spaces, so a block inside a block quote is not
read.

## Local-only reports

When a pull request's plan selects a local-only group, its body must report
the group's local run in one fenced block whose info string is exactly
`local-validation`. Each line is one entry:

```text
<group-id> <commit> <outcome> [<reason>]
```

- `<commit>` is the full 40-character commit the group ran at.
- `<outcome>` is `passed`, `failed` or `not-run`. Only `not-run` takes a
  reason, and it requires one.

For example:

````markdown
```local-validation
test.blender 3f1c2a9e8b7d6c5f4e3d2c1b0a9f8e7d6c5b4a39 passed
```
````

An obligation is met only when its group has exactly one entry that:

1. is well formed;
2. says `passed`: a `failed` or `not-run` entry fails the obligation, since a
   skipped test is not a passing test;
3. names a commit in the head's history;
4. is fresh: none of the group's affected paths changed between that commit
   and the head.

A failed obligation's diagnostic names the group and every condition that
failed, and a stale report lists the paths that changed. A report at an
earlier commit stays fresh through changes that do not touch the group's
paths.

The same block rules as requests apply: more than one `local-validation`
block, a block never closed, or a malformed info string is an error, and a
block nested in another fence is documentation, so a documentation example
never satisfies an obligation. Entries for groups that are not obligations,
well formed or not, are ignored and listed as ignored in the plan.

### Push ranges

A push has no pull request body, so the planner never checks local-only
obligations for a push range, and takes no `--request-file` for one. It lists
an affected local-only group as omitted, "verified on the pull request". A
direct push that bypasses a pull request, such as a docs landing, gets the
same explained omission.

## Using the planner

```sh
python3 tools/validation/plan.py --catalog-check
python3 tools/validation/plan.py --base origin/master --head HEAD
python3 tools/validation/plan.py --base origin/master --head HEAD --request-file body.md
python3 tools/validation/plan.py --before <sha> --after <sha>
```

| Option | Meaning |
|---|---|
| `--catalog-check` | Validate the catalog and exit. Takes no range. |
| `--base`, `--head` | A pull request range. |
| `--before`, `--after` | A push range. |
| `--request-file FILE` | A file holding the pull request body, read for its `validation-request` and `local-validation` blocks. Pull request ranges only. |
| `--json` | Print the plan as JSON instead of text. Both carry the same selections, reasons and obligations. |
| `--catalog FILE` | Read another catalog, such as a test fixture. Defaults to `catalog.json` beside the planner. |
| `--repo DIR` | Plan for the repository containing `DIR`. Defaults to the current directory. |

The planner uses only the Python standard library and runs on Python 3.13 or
newer. Without `--request-file`, a pull request range has no requests and no
reports, so a change that selects a local-only group shows it as a failed
obligation. Write the pull request body to a file and pass it to check the
body before opening the pull request.

The text form lists the changed paths, any fail-wide causes, the groups
selected to run on GitHub with their commands, the local obligations with
their status, the omitted groups, and the result. The JSON form carries the
same information in these fields: `comparison`, `changed_paths` (`null` when
the comparison failed), `unclaimed_paths`, `fail_wide`, `requested`, `groups`
(each with `id`, `category`, `description`, `commands`, `selected`, `local`,
`reasons`, and `obligation` for a local obligation), `ignored_reports`,
`failed_obligations` and `valid`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | A valid plan, with every obligation met, or a valid catalog. Failing wide still exits 0. |
| 1 | The plan was computed, but at least one local obligation failed. The plan says which and why. |
| 2 | An error: an invalid catalog, a malformed or ambiguous request or report block, an unknown requested ID, an unreadable file, or bad arguments. Nothing is planned. |

## The CI image

`ghcr.io/coghex/moskophoros-ci` is a prebuilt `linux/amd64` image for running
the groups. It holds:

- Python 3.13, from a base image named by digest;
- exactly the development dependencies `requirements.lock` pins, in an
  environment at `/opt/moskophoros/venv` that is first on `PATH` and has no pip
  of its own;
- `git` and `bash`.

It holds no Blender, no project source and no project build output. The image
records its own recipe fingerprint and its Python, pytest and ruff versions,
both in `/opt/moskophoros/image.json` and in labels named
`org.moskophoros.ci-image.*`.

### The recipe and its fingerprint

The recipe is [`tools/ci-image/`](../tools/ci-image/):

| File | Role |
|---|---|
| `Dockerfile` | The image: its base, packages and environment. |
| `stamp.py` | Runs during the build. Refuses an environment that is not exactly the lock's, then writes `image.json`. |
| `image.py` | The fingerprint, the descriptor check, and publication. |
| `registry.py` | How `image.py` reaches the GitHub Container Registry and Docker. |
| `descriptor.json` | The published image to use (below). |

The **recipe fingerprint** is a SHA-256 digest over exactly these inputs, read
from one commit's tree:

- every file under `tools/ci-image/` except `tools/ci-image/descriptor.json`;
- `requirements.lock`;
- `.github/workflows/ci-image.yml`.

Each input contributes its path, file mode, object type and Git object ID, so
editing, adding, removing, renaming or making an input executable changes the
fingerprint. Nothing else does: not other files, not the descriptor, and not
uncommitted or untracked changes. The same revision gives the same fingerprint
on any machine.

```sh
python3 tools/ci-image/image.py fingerprint --revision HEAD
```

The build context is staged from the same revision and holds exactly the
fingerprint's inputs, so nothing else can reach the build. `stage` refuses an
output directory that is not empty:

```sh
python3 tools/ci-image/image.py stage --revision HEAD --output /tmp/context
```

`image.py` uses only the Python standard library.

### The descriptor

[`tools/ci-image/descriptor.json`](../tools/ci-image/descriptor.json) names the
image to use. Its fields:

| Field | Meaning |
|---|---|
| `schema_version` | `1`. |
| `reference` | The image repository, `ghcr.io/coghex/moskophoros-ci`. |
| `digest` | The image's `sha256:` digest, the one to pull. |
| `recipe_fingerprint` | The recipe fingerprint the image was built from. |
| `python` | The Python version the image contains, a 3.13 release. |
| `pytest` | The pytest version it contains. |
| `ruff` | The ruff version it contains. |

The versions are read back from the published image, never supplied to the
build. The descriptor is not a fingerprint input, so committing it leaves the
fingerprint unchanged.

The **descriptor check** compares a descriptor's fingerprint with a revision's:

```sh
python3 tools/ci-image/image.py check-descriptor --revision HEAD
python3 tools/ci-image/image.py check-descriptor --revision HEAD --descriptor FILE
```

Without `--descriptor` it reads the descriptor committed at that revision. It
exits 0 on a match, 1 on a mismatch, with an error naming both fingerprints,
and 2 on any other error, such as a malformed or missing descriptor.

### Publishing once per fingerprint

[`.github/workflows/ci-image.yml`](../.github/workflows/ci-image.yml) runs on
manual dispatch, and for a pull request from this repository that changes a
fingerprint input. A pull request that changes only the descriptor does not
start it, and neither does a pull request from a fork. Every job reads one
revision: the pull request's head, or the dispatched revision.

1. **resolve** computes the fingerprint and looks up the tag
   `fp-<fingerprint>`. An existing image is used only if its labels record
   this fingerprint, a Python 3.13 release and the lock's pytest and ruff
   versions; its log then says the fingerprint's image already exists, and
   nothing is built. Only a registry answer that the tag or repository is
   unknown counts as absent. Any other failure, such as an authentication
   error, stops the workflow without publishing.
2. **publish** runs only when the tag is absent, and is the only job with
   package write permission. Runs for one fingerprint wait for each other, and
   each looks the tag up again first, so an image another run published
   meanwhile is used rather than rebuilt. Otherwise it builds the image from
   the staged context, runs it to check that it records the expected
   fingerprint and versions, that `pytest --version` and `ruff --version`
   agree, and that it has `git` and `bash` and no Blender or project package,
   then pushes it once and reads it back. A published tag is never
   overwritten: a tag that exists but does not describe this recipe stops the
   workflow, and replacing it means deleting that package version by hand.
3. **descriptor** reads the published image's descriptor back from the
   registry, checks it against the revision, and reports it in the job summary
   and as the `ci-image-descriptor` artifact.
4. **anonymous-pull** pulls the descriptor's digest with no registry
   credentials, runs it, and checks that it reports the descriptor's
   fingerprint and versions and the lock's pytest and ruff pins. It fails if
   the package is not public.

### Updating the image

1. Change the recipe: a file under `tools/ci-image/`, `requirements.lock`, or
   `.github/workflows/ci-image.yml`. Any change to these, even a comment,
   gives a new fingerprint and needs a new image.
2. Push it to a pull request from this repository. The workflow publishes the
   image for the new fingerprint, or finds the one already published.
3. Copy the descriptor from the workflow's summary into
   `tools/ci-image/descriptor.json`, and push it to the same pull request.
   The workflow runs again, since GitHub matches its paths against the pull
   request's whole change, and finds the image already published. The
   descriptor is not a fingerprint input, so the fingerprint is unchanged.
4. Check it:

   ```sh
   python3 tools/ci-image/image.py check-descriptor --revision HEAD
   ```

The package must be public. A new package can start private; only the owner
can change its visibility, in the package's settings on GitHub.

## On GitHub

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs the plan and
publishes `build-test`, one of the two checks the `master` ruleset requires.
Its logic is in [`tools/validation/ci.py`](../tools/validation/ci.py), which
`tools/validation/test_ci.py` tests. Every group reruns on every run; no result
is reused (D-12). Each record the run writes carries the run's ID and attempt,
and its artifacts are named by attempt, so `build-test` reads only what its own
run and attempt produced. Rerun all jobs, not only the failed ones: a partial
rerun's `build-test` cannot pass on results kept from an earlier attempt.

### Triggers

- A pull request is **opened**, **reopened** or **synchronized** (pushed to),
  or its body is **edited**.
- A push to `master`.

Runs for the same pull request share a concurrency group: a new run cancels
one still in progress, so an older run never finishes after a newer one. Each
push to `master` keeps its own run.

### What a run tests

Every job reads one revision, the **tested revision**:

- for a pull request, GitHub's merge commit of its head into its base branch.
  The planner compares that commit's two parents, the base and the head, in the
  [pull request range](#selection-rules), and reads the body from the GitHub
  API as it is when the run starts, never from the event;
- for a push, the pushed revision. The planner compares the push's `before`
  and `after` in the push range.

The run has three jobs:

1. **plan** checks out the tested revision with its full history, runs the
   planner, and [confirms the image](#confirming-the-image) the tested
   revision's [descriptor](#the-descriptor) names. It fails when the image is
   not confirmed, and then no group job starts.
2. **One job per group** selected to run on GitHub: every selected `floor`,
   `affected` and requested non-local-only group. Each job pulls the confirmed
   image, by the descriptor's digest, and runs the group's catalog commands
   inside it, unchanged, at the tested revision. The log names the group, the
   revision and the image. Before the commands, `.venv` is pointed at the
   image's environment and the package is installed into it, as
   [AGENTS.md](../AGENTS.md#build-and-test) does. A local-only group never runs
   on GitHub.
3. **`build-test`** is the aggregate, and the only job with that name. It
   [starts with the run](#when-build-test-appears) and waits for the others
   itself, so it concludes even when they failed or were skipped.

### Confirming the image

Before any group runs, the plan job checks the descriptor committed at the
tested revision and the image it names, in this order:

1. The descriptor is valid and records the tested revision's recipe
   fingerprint ([the descriptor check](#the-descriptor)).
2. The image exists at the descriptor's exact `reference@digest`: the plan job
   pulls it by that digest and runs it, through the same inspection as
   `image.py check-image`.
3. The image records the descriptor's recipe fingerprint, and its Python,
   pytest and ruff versions are the descriptor's. Its pytest and ruff are also
   the versions `requirements.lock` pins, and its Python is a 3.13 release.
   The lock pins no Python; the Dockerfile pins the Python base image by
   digest.

The pull is anonymous, with the workflow's read-only permissions, so the
package must be public. A pull request that changes only the descriptor is
checked the same way: one naming an image that holds what it says passes, and
one naming any other digest fails.

Only a confirmed image is passed to the group jobs, so no group runs in an
image that was not confirmed. When the image is confirmed, the plan job's log
and `build-test`'s summary say so, naming the image by digest with the
fingerprint and versions it records.

### When `build-test` appears

GitHub creates a job's check only when the job starts, and a job that needs
another starts only after it finishes. So `build-test` needs no other job: its
check appears, in progress, as soon as the run starts, before planning. From
then on it is the newest `build-test` on the tested revision, and an earlier
run's result, planned from an older body or head, no longer speaks for it. The
PR drainer and `/finalize` read the newest check, so they see this run's
pending `build-test`, never the last run's pass.

Once started, `build-test` reads its own run's jobs from the GitHub API, which
is why the workflow grants `actions: read`, and waits in two bounded steps:

1. for the plan job to finish, up to 15 minutes;
2. for every group job the plan started to finish, up to 30 minutes. A group
   job that has not appeared within 5 minutes of planning counts as missing.

It then reads the plan and group records and decides as below. A job is
finished only when all its steps are, including uploading its record. If a
wait runs out, a job never appears, two jobs share a group's name, or the run's
jobs cannot be read before the wait ends, `build-test` fails and its summary
names the jobs it was still waiting for and the last error. Its own time limit,
55 minutes, outlasts both waits, so it always reports why.

When a newer run cancels this one, `build-test` is cancelled with it: it ends
cancelled, never skipped or passed.

### Replanning on a body edit

Requests and local-only reports live in the pull request body, so editing the
body starts a new run, which cancels any run in progress and plans from the
new body. The new run's `build-test` appears at once, in progress, so the old
run's result stops counting as soon as the edit's run starts. `build-test`
reads the body again just before it concludes, and fails if it changed since
its run planned: the run the edit started decides. Adding
or removing a `validation-request` block, or adding a `local-validation`
report, needs no new commit.

### What `build-test` checks

It passes only when all of these hold, and fails otherwise:

| Check | Fails when |
|---|---|
| The plan was produced | the plan job left no record; the body could not be read from the API before planning; or the planner stopped with an error, such as a malformed request or an unknown group. |
| Local-only obligations (pull requests only) | a selected local-only group has no report, or a report that is malformed, stale, `failed` or `not-run` ([Local-only reports](#local-only-reports)). |
| Every selected group ran and passed | a group failed, timed out (15 minutes per group), was skipped, was cancelled, or recorded no result; ran at another revision, in another image, or in another run or attempt; or ran without being selected. |
| This run finished in time | the plan job or a group job did not finish, or never appeared, within [`build-test`'s waits](#when-build-test-appears), or the run's jobs could not be read. |
| The image is confirmed | the descriptor is missing or malformed; its recipe fingerprint is not the tested revision's; or the image it names cannot be pulled or inspected, or records a fingerprint or version that differs from the descriptor, or a pytest or ruff version that differs from the lock ([Confirming the image](#confirming-the-image)). No group runs, and the diagnostic names the field that differs or says why the image could not be checked. |
| The body did not change (pull requests only) | the body read just before concluding differs from the one planned from, or cannot be read. A body that cannot be read is a failure, never an empty body. |

For a push, local-only groups are not checked: the summary lists them as
"verified on the pull request", and they never fail `build-test`.

A docs-only pull request is a normal run. Its paths are claimed by no group, so
the planner fails wide: `check.static` and every `affected` group run, and no
local-only obligation is added (D-19).

### Reading the summary

`build-test`'s job summary starts with the verdict and, when it failed, one
line for each failure. Then:

- the tested revision (for a pull request, the merge commit with its base and
  head), the confirmed image by digest (`none` when it was not confirmed), the
  image check's result, and a digest of the body it planned from;
- each group run on GitHub, with its result;
- each local-only group: its obligation met or failed, or omitted with its
  reason, such as "verified on the pull request";
- the whole plan, in the planner's text form, with every selected and omitted
  group and its reason.

### Fixing a failure

| Failure | Fix |
|---|---|
| The planner stopped with an error | Correct the body's `validation-request` or `local-validation` block, as the diagnostic says. Editing the body reruns CI. |
| A local-only obligation is not met | Run the group locally at the pull request's current head, then add or update its entry in the body's `local-validation` block: `<group> <full commit> passed`. A report is stale once the group's paths change after its commit, so a push to those paths needs a fresh run and a fresh entry. |
| A group failed or timed out | Open its job's log, reproduce it locally with the command the plan shows, fix it, and push. |
| A group was skipped, cancelled or recorded no result | Read the plan job's log, or the group job's, for the cause. Rerun the workflow if a runner failed. |
| The descriptor is stale | Follow [Updating the image](#updating-the-image): commit the descriptor the `ci-image` workflow reports for this revision as `tools/ci-image/descriptor.json`. |
| The image does not match the descriptor or the lock | The descriptor names an image other than this recipe's. Commit, unedited, the descriptor the `ci-image` workflow reports for this revision, as in [Updating the image](#updating-the-image). Never edit a digest or version by hand. |
| The image could not be checked | Read the plan job's log for the registry's or Docker's error. A digest the registry does not hold means the descriptor is wrong: commit the one the `ci-image` workflow reports. If the package is not public, the owner makes it public. Otherwise rerun the workflow, since the registry was unavailable. |
| The body changed since planning | Nothing: the run the edit started replaces this one. |
| The body could not be read | Rerun the workflow; the GitHub API was unavailable. |
| A wait ran out, or the run's jobs could not be read | Open the job named in the summary to see why it stalled, then rerun all jobs. |
| A record came from another run or attempt | Rerun all jobs, not only the failed ones. |
