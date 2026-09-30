"""Test how CI runs the plan on GitHub and decides `build-test`.

Each case builds a history in a temporary repository, with GitHub's merge
commit for a pull request made the way GitHub makes it, and runs ci.py's
``plan``, ``run-group`` and ``conclude`` as separate processes, exactly as the
workflow's jobs do. A stub ``gh`` serves the pull request body and the run's
jobs, and a fake registry transport answers the plan's image inspection. The waiting tests drive `build-test`'s waits with a controlled clock and
scripted job lists, never real time. The last tests check the workflow file
wires those jobs together as documented.
"""

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
CI = ROOT / "tools" / "validation" / "ci.py"
IMAGE_TOOL = ROOT / "tools" / "ci-image" / "image.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
IMAGE_REFERENCE = "ghcr.io/example/project-ci"
IMAGE_DIGEST = "sha256:" + "e" * 64
IMAGE = f"{IMAGE_REFERENCE}@{IMAGE_DIGEST}"

_spec = importlib.util.spec_from_file_location("ci", CI)
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)

# Answers `gh api repos/<owner>/<name>/pulls/<n>` with the body in
# $FAKE_BODY, or fails when $FAKE_BODY does not exist; and answers the jobs of
# run 11 attempt 2 with the JSON lines in $FAKE_JOBS, as `--jq .jobs[]` prints.
FAKE_GH = """\
#!/usr/bin/env python3
import json, os, sys
JOBS = "repos/owner/name/actions/runs/11/attempts/2/jobs?per_page=100"
if sys.argv[1:] == ["api", "--paginate", JOBS, "--jq", ".jobs[]"]:
    try:
        print(open(os.environ["FAKE_JOBS"], encoding="utf-8").read(), end="")
    except OSError as error:
        sys.exit(f"HTTP 502: {error}")
    sys.exit(0)
if sys.argv[1:3] != ["api", "repos/owner/name/pulls/7"]:
    sys.exit(f"unexpected gh call: {sys.argv[1:]}")
try:
    body = open(os.environ["FAKE_BODY"], encoding="utf-8").read()
except OSError as error:
    sys.exit(f"HTTP 502: {error}")
print(json.dumps({"number": 7, "body": body}))
"""


# The registry transport image.py inspects an image through. It logs each
# request to $FAKE_INSPECTED and answers `inspect REFERENCE@DIGEST` as
# registry.py does, from the recorded values $FAKE_IMAGES holds for it; an
# image it does not hold cannot be pulled, and one recorded as "garbage"
# answers with something that is not JSON.
FAKE_REGISTRY = """\
#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_INSPECTED"], "a", encoding="utf-8") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
command, *arguments = sys.argv[1:]
images = json.load(open(os.environ["FAKE_IMAGES"], encoding="utf-8"))
if command != "inspect" or arguments[0] not in images:
    sys.exit(f"error: manifest unknown: {' '.join(sys.argv[1:])}")
values = images[arguments[0]]
if values == "garbage":
    print("Error response from daemon")
    sys.exit(0)
print(json.dumps({
    "embedded": values,
    "python": values["python"],
    "python_path": "/opt/moskophoros/venv/bin/python3",
    "pytest": "pytest " + values["pytest"],
    "ruff": "ruff " + values["ruff"],
    "git": "git version 2.47.3",
    "bash": "5.2.37(1)-release",
    "blender": None,
    "moskophoros": False,
    "labels": {
        "org.moskophoros.ci-image." + key.replace("_", "-"): value
        for key, value in values.items()
    },
}))
"""


def logging_command(group_id: str) -> list[str]:
    return ["sh", "-c", f'echo {group_id} >> "$CI_TEST_LOG"']


def group(identifier, category, paths=None, commands=None):
    entry = {
        "id": identifier,
        "description": f"the {identifier} group",
        "category": category,
        "commands": commands or [logging_command(identifier)],
    }
    if paths is not None:
        entry["paths"] = paths
    return entry


def catalog(**commands) -> dict:
    return {
        "schema_version": 1,
        "groups": [
            group("check.static", "floor", commands=commands.get("check.static")),
            group("test.app", "affected", ["src/", "tests/"], commands.get("test.app")),
            group("test.tools", "affected", ["tools/", ".github/"]),
            group("test.extra", "optional", ["src/"]),
            group("test.local", "local-only", ["src/", "tests/local/"]),
        ],
    }


class Repo:
    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True)
        self.git("init", "-q", "-b", "master")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def write(self, files: dict) -> None:
        for name, content in files.items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def commit(self, files: dict, message: str = "change") -> str:
        self.write(files)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def fingerprint(self) -> str:
        return subprocess.run(
            [sys.executable, str(IMAGE_TOOL), "fingerprint", "--repo", str(self.path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def merge_commit(self, branch: str) -> str:
        """Check out GitHub's merge commit of `branch` into master: base, then head."""
        self.git("checkout", "-q", "--detach", "master")
        self.git("merge", "-q", "--no-ff", "-m", "merge", branch)
        return self.git("rev-parse", "HEAD")


def descriptor(fingerprint: str, **overrides) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "reference": IMAGE_REFERENCE,
            "digest": IMAGE_DIGEST,
            "recipe_fingerprint": fingerprint,
            "python": "3.13.9",
            "pytest": "9.1.1",
            "ruff": "0.16.9",
            **overrides,
        }
    )


def recorded(document: dict) -> dict:
    """The values an image records, as the descriptor `document` states them."""
    return {
        name: document[name]
        for name in ("recipe_fingerprint", "python", "pytest", "ruff")
    }


@pytest.fixture
def repo(tmp_path):
    repository = Repo(tmp_path / "repo")
    repository.commit(
        {
            "tools/validation/catalog.json": json.dumps(catalog()),
            "tools/ci-image/Dockerfile": "FROM scratch\n",
            "requirements.lock": "pytest==9.1.1\nruff==0.16.9\n",
            "src/app.py": "app\n",
            "docs/guide.md": "guide\n",
        },
        "recipe",
    )
    repository.commit(
        {"tools/ci-image/descriptor.json": descriptor(repository.fingerprint())},
        "base",
    )
    return repository


class Run:
    """One CI run: its plan, group results and verdict, with the files it used."""

    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.plan_dir = tmp_path / "plan"
        self.results_dir = tmp_path / "results"
        self.log = tmp_path / "commands.log"
        self.body = tmp_path / "body.md"
        self.jobs = tmp_path / "jobs.jsonl"
        self.images_file = tmp_path / "images.json"
        self.inspected_log = tmp_path / "inspected.log"
        bindir = tmp_path / "bin"
        bindir.mkdir()
        for name, text in (("gh", FAKE_GH), ("registry", FAKE_REGISTRY)):
            executable = bindir / name
            executable.write_text(text, encoding="utf-8")
            executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
        self.registry = bindir / "registry"
        self.env = dict(
            os.environ,
            PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
            FAKE_BODY=str(self.body),
            FAKE_JOBS=str(self.jobs),
            FAKE_IMAGES=str(self.images_file),
            FAKE_INSPECTED=str(self.inspected_log),
            CI_TEST_LOG=str(self.log),
        )
        self.run_arguments: list[str] = []
        # The images the registry holds, by reference@digest. None holds
        # exactly the image the tested revision's descriptor describes.
        self.images: dict | None = None

    def ci(self, repo: Repo | None, *args: str) -> subprocess.CompletedProcess:
        where = ["--repo", str(repo.path)] if repo else []
        return subprocess.run(
            [sys.executable, str(CI), *where, *args],
            capture_output=True,
            text=True,
            check=False,
            env=self.env,
        )

    def published(self, repo: Repo, revision: str) -> dict:
        if self.images is not None:
            return self.images
        try:
            document = json.loads(
                repo.git("show", f"{revision}:tools/ci-image/descriptor.json")
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return {}
        return {f"{document['reference']}@{document['digest']}": recorded(document)}

    def inspected(self) -> list[str]:
        if not self.inspected_log.exists():
            return []
        return self.inspected_log.read_text().splitlines()

    def plan(self, repo: Repo, revision: str, before: str | None = None):
        self.images_file.write_text(json.dumps(self.published(repo, revision)))
        if before is None:
            event = ["--event", "pull_request", "--repository", "owner/name"]
            event += ["--pull-request", "7"]
        else:
            event = ["--event", "push", "--before", before]
        self.github_output = self.tmp / "github-output"
        self.planned = self.ci(
            repo,
            "plan",
            *event,
            "--revision",
            revision,
            "--output",
            str(self.plan_dir),
            "--github-output",
            str(self.github_output),
            "--registry",
            str(self.registry),
            *self.run_arguments,
        )
        outputs = dict(
            line.split("=", 1)
            for line in self.github_output.read_text().splitlines()
            if "=" in line
        )
        self.groups = json.loads(outputs.get("groups", "[]"))
        self.image = outputs.get("image", "")
        self.plan_job = "success" if self.planned.returncode == 0 else "failure"
        return self.planned

    def run_groups(self, repo: Repo, revision: str, **options) -> str:
        """Run every planned group as the matrix does; return the job result."""
        passed = True
        for group_id in self.groups:
            process = self.ci(
                repo,
                "run-group",
                "--group",
                group_id,
                "--revision",
                revision,
                "--image",
                self.image,
                "--output",
                str(self.results_dir / f"group-{group_id}" / f"{group_id}.json"),
                *[f"--{key}={value}" for key, value in options.items()],
                *self.run_arguments,
            )
            passed = passed and process.returncode == 0
        return "success" if passed else "failure"

    def conclude(self, groups_job: str, plan_job: str | None = None):
        self.summary = self.tmp / "summary.md"
        process = self.ci(
            None,
            "conclude",
            "--plan-dir",
            str(self.plan_dir),
            "--results-dir",
            str(self.results_dir),
            "--plan-job",
            plan_job or self.plan_job,
            "--groups-job",
            groups_job,
            "--repository",
            "owner/name",
            "--summary",
            str(self.summary),
            *self.run_arguments,
        )
        self.text = self.summary.read_text() if self.summary.exists() else ""
        return process

    def ran(self) -> list[str]:
        return self.log.read_text().split() if self.log.exists() else []

    def whole(self, repo: Repo, revision: str, before: str | None = None, **options):
        """Plan, run the groups when ci.yml's `groups` job would start, and conclude."""
        self.plan(repo, revision, before)
        starts = self.plan_job == "success" and self.image and self.groups
        groups_job = self.run_groups(repo, revision, **options) if starts else "skipped"
        return self.conclude(groups_job)


@pytest.fixture
def run(tmp_path):
    return Run(tmp_path)


def pull_request(repo: Repo, files: dict, *, branch: str = "pr") -> tuple[str, str]:
    """Commit `files` on a branch; return its head and GitHub's merge commit."""
    repo.git("checkout", "-q", "-b", branch, "master")
    head = repo.commit(files)
    return head, repo.merge_commit(branch)


def report(head: str, outcome: str = "passed", reason: str = "") -> str:
    line = f"test.local {head} {outcome} {reason}".rstrip()
    return f"Body.\n\n```local-validation\n{line}\n```\n"


# --------------------------------------------------------------------------
# Passing runs


def test_a_docs_only_pull_request_runs_the_floor_and_passes(repo, run):
    _, merge = pull_request(repo, {"docs/guide.md": "better guide\n"})
    run.body.write_text("Docs only.\n")
    process = run.whole(repo, merge)
    assert process.returncode == 0, process.stdout + process.stderr
    assert "check.static" in run.ran()
    assert "test.local" not in run.ran()
    assert "## build-test: passed" in run.text
    assert "test.local" in run.text and "not affected" in run.text


def test_a_code_change_runs_its_groups_and_needs_a_fresh_passing_report(repo, run):
    head, merge = pull_request(repo, {"src/app.py": "new app\n"})
    run.body.write_text(report(head))
    process = run.whole(repo, merge)
    assert process.returncode == 0, process.stdout + process.stderr
    assert sorted(run.ran()) == ["check.static", "test.app"]
    assert f"obligation met: passed at `{head}`" in run.text
    assert f"`{merge}`, GitHub's merge commit for pull request #7" in run.text


def test_a_request_selects_and_runs_the_requested_group(repo, run):
    _, merge = pull_request(repo, {"tools/x.py": "x\n"})
    run.body.write_text("```validation-request\ntest.extra\n```\n")
    process = run.whole(repo, merge)
    assert process.returncode == 0, process.stdout + process.stderr
    assert sorted(run.ran()) == ["check.static", "test.extra", "test.tools"]
    assert "requested in the pull request" in run.text


def test_a_push_lists_local_only_groups_as_verified_on_the_pull_request(repo, run):
    before = repo.git("rev-parse", "HEAD")
    after = repo.commit({"src/app.py": "pushed app\n"})
    process = run.whole(repo, after, before=before)
    assert process.returncode == 0, process.stdout + process.stderr
    assert sorted(run.ran()) == ["check.static", "test.app"]
    assert "`test.local`: verified on the pull request" in run.text
    assert "`" + after + "`, the pushed revision" in run.text


# --------------------------------------------------------------------------
# Each way build-test fails


def test_a_planner_error_fails(repo, run):
    _, merge = pull_request(repo, {"src/app.py": "new app\n"})
    run.body.write_text("```validation-request\ntest.unknown\n```\n")
    process = run.whole(repo, merge)
    assert run.planned.returncode == 1
    assert run.ran() == []
    assert process.returncode == 1
    assert "the planner failed (exit 2)" in run.text
    assert "unknown group 'test.unknown'" in run.text


def test_a_missing_plan_fails(run):
    process = run.conclude("skipped", plan_job="failure")
    assert process.returncode == 1
    assert "the plan was not produced: the plan job concluded failure" in run.text


@pytest.mark.parametrize(
    ("body", "diagnostic"),
    [
        (lambda head, stale: "No report.\n", "no local-validation entry reports it"),
        (lambda head, stale: report(stale), "the report is stale"),
        (lambda head, stale: report(head, "failed"), "the report says it failed"),
        (
            lambda head, stale: report(head, "not-run", "no Blender here"),
            "the report says it was not run: no Blender here",
        ),
    ],
    ids=["missing", "stale", "failed", "not-run"],
)
def test_an_unmet_local_only_obligation_fails(repo, run, body, diagnostic):
    repo.git("checkout", "-q", "-b", "pr", "master")
    stale = repo.commit({"src/app.py": "first\n"})
    head = repo.commit({"src/app.py": "second\n"})
    merge = repo.merge_commit("pr")
    run.body.write_text(body(head, stale))
    process = run.whole(repo, merge)
    assert process.returncode == 1
    assert "the local-only group test.local has no fresh passing report" in run.text
    assert diagnostic in run.text
    assert "test.local" not in run.ran()


def test_a_failed_group_fails(repo, run):
    repo.commit(
        {
            "tools/validation/catalog.json": json.dumps(
                catalog(**{"test.app": [["sh", "-c", "exit 3"]]})
            )
        }
    )
    _, merge = pull_request(repo, {"src/app.py": "new app\n"})
    run.body.write_text(report(repo.git("rev-parse", "pr")))
    process = run.whole(repo, merge)
    assert process.returncode == 1
    assert "test.app failed: sh -c 'exit 3' exited 3" in run.text


def test_a_timed_out_group_fails(repo, run):
    hang = [sys.executable, "-c", "import threading; threading.Event().wait()"]
    repo.commit(
        {"tools/validation/catalog.json": json.dumps(catalog(**{"test.app": [hang]}))}
    )
    _, merge = pull_request(repo, {"src/app.py": "new app\n"})
    run.body.write_text(report(repo.git("rev-parse", "pr")))
    process = run.whole(repo, merge, timeout=0.5)
    assert process.returncode == 1
    assert "test.app timed-out" in run.text
    assert "after the group's 0.5-second limit" in run.text


@pytest.mark.parametrize("result", ["skipped", "cancelled"])
def test_skipped_or_cancelled_group_jobs_fail(repo, run, result):
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    run.body.write_text("Docs.\n")
    run.plan(repo, merge)
    process = run.conclude(result)
    assert process.returncode == 1
    assert f"check.static {result}: no result was recorded" in run.text


def test_a_selected_group_with_no_result_is_missing_and_fails(repo, run):
    _, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(repo.git("rev-parse", "pr")))
    run.plan(repo, merge)
    run.groups = ["check.static"]
    process = run.conclude(run.run_groups(repo, merge))
    assert process.returncode == 1
    assert "test.app missing: no result was recorded" in run.text


def test_a_stale_descriptor_fails_the_plan_and_runs_no_group(repo, run):
    repo.commit({"requirements.lock": "pytest==9.1.2\nruff==0.16.9\n"})
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    run.body.write_text("Docs.\n")
    process = run.whole(repo, merge)
    assert run.planned.returncode == 1
    assert run.image == ""
    assert run.ran() == [] and run.inspected() == []
    assert process.returncode == 1
    assert "the CI image descriptor is stale, so no group ran" in run.text
    assert "commit the descriptor it reports" in run.text
    assert "the plan job concluded" not in run.text


# --------------------------------------------------------------------------
# The image the descriptor names is confirmed before any group runs in it

ZERO_DIGEST = "sha256:" + "0" * 64


def change(repo: Repo, run: Run, event: str, files: dict) -> tuple[str, str | None]:
    """Commit `files` as a pull request or a push; return the tested revision and before."""
    if event == "push":
        before = repo.git("rev-parse", "HEAD")
        return repo.commit(files), before
    run.body.write_text("Body.\n")
    return pull_request(repo, files)[1], None


def image_values(fingerprint: str, **overrides) -> dict:
    return {
        "recipe_fingerprint": fingerprint,
        "python": "3.13.9",
        "pytest": "9.1.1",
        "ruff": "0.16.9",
        **overrides,
    }


@pytest.mark.parametrize("event", ["pull_request", "push"])
def test_the_plan_confirms_the_image_and_groups_run_in_that_image(repo, run, event):
    revision, before = change(repo, run, event, {"docs/guide.md": "better\n"})
    process = run.whole(repo, revision, before)
    assert process.returncode == 0, run.text
    assert run.inspected() == [f"inspect {IMAGE}"]
    assert run.image == IMAGE
    assert "check.static" in run.ran()
    record = json.loads(
        (run.results_dir / "group-check.static" / "check.static.json").read_text()
    )
    assert record["image"] == IMAGE
    confirmation = (
        f"confirmed {IMAGE}: it records the tested revision's recipe fingerprint "
        f"{repo.fingerprint()} and python 3.13.9, pytest 9.1.1, ruff 0.16.9"
    )
    assert confirmation in run.planned.stdout
    assert confirmation in run.text


@pytest.mark.parametrize("event", ["pull_request", "push"])
@pytest.mark.parametrize(
    ("descriptor_overrides", "image", "diagnostic"),
    [
        pytest.param(
            {"digest": ZERO_DIGEST},
            {},
            f"registry inspect {IMAGE_REFERENCE}@{ZERO_DIGEST} failed",
            id="wrong-digest",
        ),
        pytest.param(
            {"python": "3.13.1"},
            {},
            "it records python '3.13.9', but tools/ci-image/descriptor.json at ",
            id="descriptor-python",
        ),
        pytest.param(
            {"pytest": "9.1.0"},
            {},
            "it records pytest '9.1.1', but tools/ci-image/descriptor.json at ",
            id="descriptor-pytest",
        ),
        pytest.param(
            {"ruff": "0.1.0"},
            {},
            "it records ruff '0.16.9', but tools/ci-image/descriptor.json at ",
            id="descriptor-ruff",
        ),
        pytest.param(
            {"pytest": "9.2.0", "ruff": "0.17.0"},
            {"pytest": "9.2.0", "ruff": "0.17.0"},
            "the embedded pytest is '9.2.0', but the lock pins 9.1.1; "
            "the embedded ruff is '0.17.0', but the lock pins 0.16.9",
            id="lock-pins",
        ),
        pytest.param(
            {},
            {"recipe_fingerprint": "f" * 64},
            f"the embedded recipe fingerprint is '{'f' * 64}', not ",
            id="image-fingerprint",
        ),
        pytest.param(
            {},
            "garbage",
            f"the inspection of {IMAGE} did not answer with JSON",
            id="uninspectable",
        ),
    ],
)
def test_an_image_that_is_not_confirmed_fails_the_plan_and_runs_no_group(
    repo, run, event, descriptor_overrides, image, diagnostic
):
    fingerprint = repo.fingerprint()
    run.images = {
        IMAGE: image if image == "garbage" else image_values(fingerprint, **image)
    }
    named = f"{IMAGE_REFERENCE}@{descriptor_overrides.get('digest', IMAGE_DIGEST)}"
    files = {"docs/guide.md": "better\n"}
    if descriptor_overrides:
        files["tools/ci-image/descriptor.json"] = descriptor(
            fingerprint, **descriptor_overrides
        )
    revision, before = change(repo, run, event, files)
    process = run.whole(repo, revision, before)
    assert run.inspected() == [f"inspect {named}"]
    assert run.planned.returncode == 1
    assert diagnostic in run.planned.stderr
    assert run.image == "" and run.ran() == []
    assert process.returncode == 1
    assert "## build-test: failed" in run.text
    assert (
        "the image the CI image descriptor names is not confirmed, so no group ran in it"
        in run.text
    )
    assert diagnostic in run.text
    assert "the plan job concluded" not in run.text


def test_the_guide_reviews_probe_fails_the_plan_naming_the_digest(repo, run):
    """A descriptor naming the all-zero digest and ruff 0.1.0, fingerprint intact."""
    run.images = {IMAGE: image_values(repo.fingerprint())}
    _, merge = pull_request(
        repo,
        {
            "tools/ci-image/descriptor.json": descriptor(
                repo.fingerprint(), digest=ZERO_DIGEST, ruff="0.1.0"
            )
        },
    )
    run.body.write_text("Body.\n")
    process = run.whole(repo, merge)
    assert run.planned.returncode == 1
    assert ZERO_DIGEST in run.planned.stderr
    assert process.returncode == 1 and ZERO_DIGEST in run.text
    assert run.ran() == []


def test_a_descriptor_only_change_is_checked_like_any_other(repo, run):
    other = "sha256:" + "a" * 64
    fingerprint = repo.fingerprint()
    run.images = {
        IMAGE: image_values(fingerprint),
        f"{IMAGE_REFERENCE}@{other}": image_values(fingerprint),
    }
    head, merge = pull_request(
        repo, {"tools/ci-image/descriptor.json": descriptor(fingerprint, digest=other)}
    )
    run.body.write_text("Body.\n")
    assert run.whole(repo, merge).returncode == 0, run.text
    assert run.image == f"{IMAGE_REFERENCE}@{other}"

    unknown = "sha256:" + "b" * 64
    (run.tmp / "unknown").mkdir()
    rerun = Run(run.tmp / "unknown")
    rerun.images = run.images
    repo.git("checkout", "-q", "pr")
    repo.commit(
        {"tools/ci-image/descriptor.json": descriptor(fingerprint, digest=unknown)}
    )
    merge = repo.merge_commit("pr")
    rerun.body.write_text("Body.\n")
    process = rerun.whole(repo, merge)
    assert process.returncode == 1 and rerun.ran() == []
    assert f"registry inspect {IMAGE_REFERENCE}@{unknown} failed" in rerun.text


def test_a_body_changed_since_planning_fails(repo, run):
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    run.body.write_text("Docs.\n")
    run.plan(repo, merge)
    groups_job = run.run_groups(repo, merge)
    run.body.write_text("Docs, edited.\n")
    process = run.conclude(groups_job)
    assert process.returncode == 1
    assert "the pull request body changed since this run planned from it" in run.text


def test_a_body_that_cannot_be_read_before_planning_fails(repo, run):
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    process = run.whole(repo, merge)
    assert run.planned.returncode == 1
    assert run.ran() == []
    assert process.returncode == 1
    assert "could not read pull request #7's body before planning" in run.text
    assert "HTTP 502" in run.text


def test_a_body_that_cannot_be_read_again_fails(repo, run):
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    run.body.write_text("Docs.\n")
    run.plan(repo, merge)
    groups_job = run.run_groups(repo, merge)
    run.body.unlink()
    process = run.conclude(groups_job)
    assert process.returncode == 1
    assert "could not read the pull request body again before concluding" in run.text
    assert "HTTP 502" in run.text


# --------------------------------------------------------------------------
# The jobs run exactly the plan, in one revision and one image


def test_groups_run_their_catalog_commands_at_the_tested_revision_in_its_image(
    repo, run
):
    commands = [["sh", "-c", 'echo first >> "$CI_TEST_LOG"'], logging_command("second")]
    repo.commit(
        {
            "tools/validation/catalog.json": json.dumps(
                catalog(**{"check.static": commands})
            )
        }
    )
    head, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(head))
    assert run.whole(repo, merge).returncode == 0
    assert run.ran() == ["first", "second", "test.app"]
    assert run.image == IMAGE
    for group_id in ("check.static", "test.app"):
        path = run.results_dir / f"group-{group_id}" / f"{group_id}.json"
        record = json.loads(path.read_text())
        assert record["revision"] == merge
        assert record["image"] == IMAGE
        assert record["outcome"] == "passed"
    assert [c["command"] for c in record["commands"]] == [logging_command("test.app")]


def test_a_local_only_group_is_never_planned_to_run_or_run(repo, run):
    head, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(head))
    run.plan(repo, merge)
    assert "test.local" not in run.groups
    run.groups = ["test.local"]
    assert run.run_groups(repo, merge) == "failure"
    assert run.ran() == []
    record = json.loads(
        (run.results_dir / "group-test.local" / "test.local.json").read_text()
    )
    assert record["detail"] == "test.local is local-only and never runs on GitHub"


def test_a_group_run_at_another_revision_or_image_fails(repo, run):
    head, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(head))
    run.plan(repo, merge)
    groups_job = run.run_groups(repo, merge)
    for group_id, field, value in (
        ("check.static", "revision", head),
        ("test.app", "image", f"{IMAGE_REFERENCE}@sha256:{'0' * 64}"),
    ):
        path = run.results_dir / f"group-{group_id}" / f"{group_id}.json"
        record = json.loads(path.read_text())
        record[field] = value
        path.write_text(json.dumps(record))
    process = run.conclude(groups_job)
    assert process.returncode == 1
    assert f"check.static ran at {head}, not the tested revision {merge}" in run.text
    assert "test.app ran in " in run.text and "not the descriptor's image" in run.text


def test_a_group_the_plan_did_not_select_fails(repo, run):
    head, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(head))
    run.plan(repo, merge)
    run.groups.append("test.tools")
    process = run.conclude(run.run_groups(repo, merge))
    assert process.returncode == 1
    assert "test.tools ran, but the plan did not select it" in run.text


def test_a_checkout_that_is_not_the_tested_revision_fails_the_group(repo, run):
    head, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(head))
    run.plan(repo, merge)
    repo.git("checkout", "-q", "--detach", head)
    process = run.conclude(run.run_groups(repo, merge))
    assert process.returncode == 1
    assert f"the checkout is {head}, not the tested revision {merge}" in run.text


@pytest.mark.parametrize("job", ["plan", "groups"])
@pytest.mark.parametrize("result", ["failure", "skipped", "cancelled"])
def test_an_upstream_job_that_did_not_succeed_cannot_pass(repo, run, job, result):
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    run.body.write_text("Docs.\n")
    run.plan(repo, merge)
    groups_job = run.run_groups(repo, merge)
    if job == "plan":
        process = run.conclude(groups_job, plan_job=result)
        assert f"the plan job concluded {result}" in run.text
    else:
        process = run.conclude(result)
        assert f"the group jobs concluded {result}" in run.text
    assert process.returncode == 1


def test_decide_never_passes_without_a_plan():
    verdict = ci.decide(None, [], "success", "success")
    assert not verdict["passed"]


RUN = ["--run-id", "11", "--run-attempt", "2"]


def test_records_are_bound_to_their_run_and_attempt(repo, run):
    head, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(head))
    run.run_arguments = RUN
    assert run.whole(repo, merge).returncode == 0, run.text
    state = json.loads((run.plan_dir / "plan-state.json").read_text())
    assert state["run"] == {"id": 11, "attempt": 2}
    record = json.loads(
        (run.results_dir / "group-test.app" / "test.app.json").read_text()
    )
    assert record["run"] == {"id": 11, "attempt": 2}

    run.run_arguments = ["--run-id", "11", "--run-attempt", "3"]
    process = run.conclude("success")
    assert process.returncode == 1
    assert (
        "the plan was recorded by run 11 attempt 2, not by this one, "
        "run 11 attempt 3" in run.text
    )
    assert "test.app was recorded by run 11 attempt 2" in run.text


def test_a_record_without_a_run_does_not_speak_for_one(repo, run):
    head, merge = pull_request(repo, {"src/app.py": "new\n"})
    run.body.write_text(report(head))
    run.plan(repo, merge)
    groups_job = run.run_groups(repo, merge)
    run.run_arguments = RUN
    process = run.conclude(groups_job)
    assert process.returncode == 1
    assert "the plan was recorded by an unidentified run" in run.text
    assert "check.static was recorded by an unidentified run" in run.text


# --------------------------------------------------------------------------
# build-test's waits, with a controlled clock and scripted job lists


class Clock:
    """Time that moves only when the code under test sleeps."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds > 0
        self.slept.append(seconds)
        self.now += seconds


def job(name, status="completed", conclusion="success"):
    return {"name": name, "status": status, "conclusion": conclusion}


class Jobs:
    """Answers each read with the next scripted job list, or its error."""

    def __init__(self, clock: Clock, *answers):
        self.clock = clock
        self.answers = list(answers)
        self.timeouts = []

    def __call__(self, timeout: float) -> list[dict]:
        self.timeouts.append((self.clock.now, timeout))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


def waits(clock: Clock, **overrides) -> dict:
    return {"clock": clock, "sleep": clock.sleep, "interval": 10, **overrides}


PLANNED = {
    "revision": "r",
    "image": IMAGE,
    "github_groups": ["check.static", "test.app"],
}


def test_the_plan_wait_returns_once_the_plan_job_finishes():
    clock = Clock()
    jobs = Jobs(
        clock,
        [job("build-test", "in_progress", None)],
        [job("plan", "queued", None), job("build-test", "in_progress", None)],
        [job("plan", "in_progress", None)],
        [job("plan")],
    )
    assert ci.await_plan(jobs, 600, **waits(clock)) == "success"
    assert clock.now == 30


@pytest.mark.parametrize(
    ("conclusion", "result"),
    [("failure", "failure"), ("cancelled", "cancelled"), ("timed_out", "failure")],
)
def test_a_plan_job_that_did_not_succeed_is_reported_as_such(conclusion, result):
    clock = Clock()
    jobs = Jobs(clock, [job("plan", conclusion=conclusion)])
    assert ci.await_plan(jobs, 600, **waits(clock)) == result


def test_failed_planning_waits_for_no_group_and_cannot_pass():
    clock = Clock()
    jobs = Jobs(clock, AssertionError("no job list is read"))
    assert ci.await_groups(PLANNED, "failure", jobs, 600, **waits(clock)) == "skipped"
    assert ci.await_groups(None, "success", jobs, 600, **waits(clock)) == "skipped"
    no_image = {**PLANNED, "image": None}
    assert ci.await_groups(no_image, "success", jobs, 600, **waits(clock)) == "skipped"
    assert jobs.timeouts == []
    verdict = ci.decide(
        {
            **PLANNED,
            "event": "push",
            "errors": [],
            "plan": None,
            "descriptor": {"status": "current", "message": ""},
        },
        [],
        "failure",
        "skipped",
    )
    assert not verdict["passed"]
    assert "the plan job concluded failure" in verdict["failures"]
    assert "check.static skipped: no result was recorded" in verdict["failures"][1]


def test_group_jobs_that_appear_late_are_awaited_until_they_finish():
    clock = Clock()
    jobs = Jobs(
        clock,
        [job("plan")],
        [job("plan")],
        [job("plan"), job("group/check.static", "queued", None)],
        [
            job("plan"),
            job("group/check.static"),
            job("group/test.app", "in_progress", None),
        ],
        [job("plan"), job("group/check.static"), job("group/test.app")],
    )
    assert ci.await_groups(PLANNED, "success", jobs, 600, **waits(clock)) == "success"
    assert clock.now == 40


def test_a_selected_group_job_that_never_appears_fails_the_wait():
    clock = Clock()
    jobs = Jobs(clock, [job("plan"), job("group/check.static")])
    with pytest.raises(ci.CIError, match="no job of this run is named group/test.app"):
        ci.await_groups(PLANNED, "success", jobs, 600, **waits(clock, discovery=60))
    assert clock.now == 60


@pytest.mark.parametrize(
    ("conclusions", "result"),
    [
        (["success", "cancelled"], "cancelled"),
        (["success", "failure"], "failure"),
        (["skipped", "success"], "failure"),
        (["skipped", "skipped"], "skipped"),
        (["success", None], "failure"),
    ],
)
def test_group_jobs_combine_like_a_needs_result(conclusions, result):
    clock = Clock()
    jobs = Jobs(
        clock,
        [
            job("group/check.static", conclusion=conclusions[0]),
            job("group/test.app", conclusion=conclusions[1]),
        ],
    )
    assert ci.await_groups(PLANNED, "success", jobs, 600, **waits(clock)) == result


def test_a_group_that_never_finishes_fails_within_the_budget():
    clock = Clock()
    jobs = Jobs(
        clock, [job("group/check.static"), job("group/test.app", "in_progress", None)]
    )
    with pytest.raises(ci.CIError) as caught:
        ci.await_groups(PLANNED, "success", jobs, 95, **waits(clock))
    assert str(caught.value) == "gave up after 95 seconds waiting for group/test.app"
    assert clock.now == 95
    assert all(at + timeout <= 95 for at, timeout in jobs.timeouts)


def test_a_status_read_that_keeps_failing_fails_within_the_budget():
    clock = Clock()
    jobs = Jobs(clock, ci.CIError("gh api failed: HTTP 502"))
    with pytest.raises(ci.CIError) as caught:
        ci.await_plan(jobs, 45, **waits(clock))
    assert str(caught.value) == (
        "gave up after 45 seconds waiting for plan; the last read of the run's "
        "jobs failed: gh api failed: HTTP 502"
    )
    assert clock.now == 45
    assert all(at + timeout <= 45 for at, timeout in jobs.timeouts)


def test_a_status_read_that_fails_once_is_retried():
    clock = Clock()
    jobs = Jobs(clock, ci.CIError("gh api failed: HTTP 502"), [job("plan")])
    assert ci.await_plan(jobs, 600, **waits(clock)) == "success"
    assert clock.now == 10


def test_two_jobs_sharing_a_selected_name_fail_the_wait():
    clock = Clock()
    jobs = Jobs(
        clock,
        [job("group/check.static"), job("group/check.static"), job("group/test.app")],
    )
    with pytest.raises(ci.CIError, match="more than one job .* group/check.static"):
        ci.await_groups(PLANNED, "success", jobs, 600, **waits(clock))


@pytest.mark.parametrize("group", ["plan", "build-test", "review-approved"])
def test_a_group_named_like_another_check_waits_only_for_its_own_job(group):
    clock = Clock()
    jobs = Jobs(
        clock,
        [job("plan"), job("build-test", "in_progress", None), job("review-approved")],
        [
            job("plan"),
            job("review-approved"),
            job(f"group/{group}", conclusion="failure"),
        ],
    )
    state = {**PLANNED, "github_groups": [group]}
    assert ci.await_groups(state, "success", jobs, 600, **waits(clock)) == "failure"
    assert clock.now == 10


def lines(*jobs) -> str:
    return "".join(json.dumps(entry) + "\n" for entry in jobs)


def test_await_plan_reads_this_runs_attempt_and_reports_the_result(run):
    run.jobs.write_text(lines(job("plan", conclusion="failure"), job("build-test")))
    output = run.tmp / "output"
    process = run.ci(
        None,
        "await-plan",
        "--repository",
        "owner/name",
        *RUN,
        "--github-output",
        str(output),
    )
    assert process.returncode == 0, process.stderr
    assert output.read_text() == "plan_job=failure\n"


def test_await_groups_that_run_out_of_time_fail_build_test_with_a_diagnostic(repo, run):
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    run.body.write_text("Docs.\n")
    run.plan(repo, merge)
    run.jobs.write_text(
        lines(job("plan"), job("group/check.static", "in_progress", None))
    )
    summary = run.tmp / "summary.md"
    process = run.ci(
        None,
        "await-groups",
        "--repository",
        "owner/name",
        *RUN,
        "--plan-dir",
        str(run.plan_dir),
        "--plan-job",
        "success",
        "--budget",
        "0",
        "--summary",
        str(summary),
    )
    assert process.returncode == 1
    assert summary.read_text() == (
        "## build-test: failed\n\n### Failures\n\n"
        "- gave up after 0 seconds waiting for group/check.static, group/test.app, "
        "group/test.tools\n"
    )


def test_await_plan_fails_when_the_jobs_cannot_be_read(run):
    process = run.ci(
        None, "await-plan", "--repository", "owner/name", *RUN, "--budget", "0"
    )
    assert process.returncode == 1
    assert "the last read of the run's jobs failed: gh api failed: HTTP 502" in (
        process.stdout
    )


# --------------------------------------------------------------------------
# The workflow file


def workflow_jobs() -> dict[str, str]:
    """Each job's YAML text, keyed by its ID."""
    text = WORKFLOW.read_text(encoding="utf-8")
    jobs = text.split("\njobs:\n", 1)[1]
    return {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"^  ([\w-]+):\n((?:    .*\n|\s*\n|  #.*\n)*)", jobs, re.M
        )
    }


def test_the_workflow_triggers_on_body_edits_and_cancels_superseded_runs():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "types: [opened, synchronize, reopened, edited]" in text
    assert "branches: [master]" in text
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text
    assert "format('ci-pr-{0}', github.event.pull_request.number)" in text


def test_the_workflow_holds_no_write_permission():
    text = WORKFLOW.read_text(encoding="utf-8")
    grants = re.findall(r"^\s+([\w-]+):\s*(read|write|none)\s*$", text, re.M)
    assert sorted(grants) == [
        ("actions", "read"),
        ("contents", "read"),
        ("packages", "read"),
        ("pull-requests", "read"),
    ]
    assert "write-all" not in text and "read-all" not in text
    # The plan inspects the image as an anonymous, read-only pull.
    assert "docker login" not in text and "REGISTRY_TOKEN" not in text


def test_build_test_is_the_one_aggregate_and_starts_with_the_run():
    jobs = workflow_jobs()
    assert set(jobs) == {"plan", "groups", "build-test"}
    assert all("name: build-test" not in body for body in jobs.values())
    aggregate = jobs["build-test"]
    # No `needs` and no `if`: GitHub creates its check when the run starts,
    # and cancelling the run cancels it rather than skipping it.
    assert "needs:" not in aggregate
    assert "\n    if:" not in aggregate
    steps = [
        "ci.py await-plan",
        "name: plan-${{ github.run_attempt }}",
        "ci.py await-groups",
        "pattern: group-${{ github.run_attempt }}-*",
        "ci.py conclude",
    ]
    positions = [aggregate.index(step) for step in steps]
    assert positions == sorted(positions)
    assert "PLAN_JOB: ${{ steps.plan.outputs.plan_job }}" in aggregate
    assert "GROUPS_JOB: ${{ steps.groups.outputs.groups_job }}" in aggregate
    assert '--plan-job "$PLAN_JOB" --groups-job "$GROUPS_JOB"' in aggregate
    assert aggregate.count('--run-id "$RUN_ID" --run-attempt "$RUN_ATTEMPT"') == 3
    assert "RUN_ATTEMPT: ${{ github.run_attempt }}" in aggregate


def test_no_group_check_can_take_a_required_checks_name():
    groups = workflow_jobs()["groups"]
    names = re.findall(r"^    name: (.*)$", groups, re.M)
    # A fixed prefix, then the group's ID: every value starts with the prefix.
    assert names == [ci.GROUP_JOB_PREFIX + "${{ matrix.group }}"]
    assert ci.group_job("review-approved") == "group/review-approved"
    for name in (*ci.planner.RESERVED_IDS, ci.PLAN_JOB, ci.AGGREGATE_JOB):
        assert not name.startswith(ci.GROUP_JOB_PREFIX)


def test_build_test_outlasts_its_waits_so_it_can_report_them():
    jobs = workflow_jobs()
    minutes = int(re.search(r"timeout-minutes: (\d+)", jobs["build-test"])[1])
    waits = ci.PLAN_WAIT + ci.GROUPS_WAIT + 2 * ci.API_TIMEOUT
    assert minutes * 60 >= waits + 5 * 60
    plan = int(re.search(r"timeout-minutes: (\d+)", jobs["plan"])[1])
    group = int(re.search(r"timeout-minutes: (\d+)", jobs["groups"])[1])
    assert ci.PLAN_WAIT > plan * 60 and ci.GROUPS_WAIT > group * 60


def test_plan_and_group_records_carry_the_run_and_attempt():
    jobs = workflow_jobs()
    assert "name: plan-${{ github.run_attempt }}" in jobs["plan"]
    assert '--run-id "$RUN_ID" --run-attempt "$RUN_ATTEMPT"' in jobs["plan"]
    groups = jobs["groups"]
    assert "name: group-${{ github.run_attempt }}-${{ matrix.group }}" in groups
    assert '--run-id "$RUN_ID" --run-attempt "$RUN_ATTEMPT"' in groups
    assert "--env RUN_ID --env RUN_ATTEMPT" in groups


def test_every_group_runs_in_the_planned_image_at_the_tested_revision():
    jobs = workflow_jobs()
    groups = jobs["groups"]
    assert "group: ${{ fromJSON(needs.plan.outputs.groups) }}" in groups
    assert "fail-fast: false" in groups
    assert "IMAGE: ${{ needs.plan.outputs.image }}" in groups
    assert 'docker run --rm --volume "$GITHUB_WORKSPACE:/work"' in groups
    assert '--env GROUP --env IMAGE --env REVISION "$IMAGE"' in groups
    assert "tools/validation/ci.py run-group" in groups
    for body in jobs.values():
        assert "ref: ${{ github.sha }}" in body
    assert "REVISION: ${{ github.sha }}" in jobs["plan"]
    assert "REVISION: ${{ github.sha }}" in groups
