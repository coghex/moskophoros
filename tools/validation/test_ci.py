"""Test how CI runs the plan on GitHub and decides `build-test`.

Each case builds a history in a temporary repository, with GitHub's merge
commit for a pull request made the way GitHub makes it, and runs ci.py's
``plan``, ``run-group`` and ``conclude`` as separate processes, exactly as the
workflow's jobs do. A stub ``gh`` serves the pull request body. The last tests
check the workflow file wires those jobs together as documented.
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
# $FAKE_BODY, or fails when $FAKE_BODY does not exist.
FAKE_GH = """\
#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:3] != ["api", "repos/owner/name/pulls/7"]:
    sys.exit(f"unexpected gh call: {sys.argv[1:]}")
try:
    body = open(os.environ["FAKE_BODY"], encoding="utf-8").read()
except OSError as error:
    sys.exit(f"HTTP 502: {error}")
print(json.dumps({"number": 7, "body": body}))
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


def descriptor(fingerprint: str) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "reference": IMAGE_REFERENCE,
            "digest": IMAGE_DIGEST,
            "recipe_fingerprint": fingerprint,
            "python": "3.13.9",
            "pytest": "9.1.1",
            "ruff": "0.16.9",
        }
    )


@pytest.fixture
def repo(tmp_path):
    repository = Repo(tmp_path / "repo")
    repository.commit(
        {
            "tools/validation/catalog.json": json.dumps(catalog()),
            "tools/ci-image/Dockerfile": "FROM scratch\n",
            "requirements.lock": "pytest==9.1.1\n",
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
        bindir = tmp_path / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.env = dict(
            os.environ,
            PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
            FAKE_BODY=str(self.body),
            CI_TEST_LOG=str(self.log),
        )

    def ci(self, repo: Repo | None, *args: str) -> subprocess.CompletedProcess:
        where = ["--repo", str(repo.path)] if repo else []
        return subprocess.run(
            [sys.executable, str(CI), *where, *args],
            capture_output=True,
            text=True,
            check=False,
            env=self.env,
        )

    def plan(self, repo: Repo, revision: str, before: str | None = None):
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
        )
        self.text = self.summary.read_text() if self.summary.exists() else ""
        return process

    def ran(self) -> list[str]:
        return self.log.read_text().split() if self.log.exists() else []

    def whole(self, repo: Repo, revision: str, before: str | None = None, **options):
        self.plan(repo, revision, before)
        groups_job = (
            self.run_groups(repo, revision, **options) if self.groups else "skipped"
        )
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


def test_a_stale_descriptor_fails(repo, run):
    repo.commit({"requirements.lock": "pytest==9.1.2\n"})
    _, merge = pull_request(repo, {"docs/guide.md": "better\n"})
    run.body.write_text("Docs.\n")
    process = run.whole(repo, merge)
    assert process.returncode == 1
    assert "the CI image descriptor is stale" in run.text
    assert "commit the descriptor it reports" in run.text


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
        ("contents", "read"),
        ("packages", "read"),
        ("pull-requests", "read"),
    ]
    assert "write-all" not in text and "read-all" not in text


def test_build_test_is_the_one_aggregate_and_runs_after_failures():
    jobs = workflow_jobs()
    assert set(jobs) == {"plan", "groups", "build-test"}
    assert all("name: build-test" not in body for body in jobs.values())
    aggregate = jobs["build-test"]
    assert "    needs: [plan, groups]\n" in aggregate
    assert "    if: ${{ !cancelled() }}\n" in aggregate
    assert '--plan-job "$PLAN_JOB" --groups-job "$GROUPS_JOB"' in aggregate
    assert "PLAN_JOB: ${{ needs.plan.result }}" in aggregate
    assert "GROUPS_JOB: ${{ needs.groups.result }}" in aggregate


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
