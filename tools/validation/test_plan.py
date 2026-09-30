"""Test the validation planner against fixture catalogs and real Git histories.

Each history is built in a temporary repository, and the planner runs as a
separate process exactly as CI and people run it.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
PLANNER = ROOT / "tools" / "validation" / "plan.py"

_spec = importlib.util.spec_from_file_location("plan", PLANNER)
plan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan)


def group(identifier, category, paths=None, **extra):
    entry = {
        "id": identifier,
        "description": f"the {identifier} group",
        "category": category,
        "commands": [["true"]],
    }
    if paths is not None:
        entry["paths"] = paths
    entry.update(extra)
    return entry


FIXTURE = {
    "schema_version": 1,
    "groups": [
        group("check.static", "floor"),
        group("test.app", "affected", ["src/", "tests/", "pyproject.toml"]),
        group("test.tools", "affected", ["tools/"]),
        group("test.extra", "optional", ["src/"]),
        group("test.local", "local-only", ["src/", "tests/local/"]),
    ],
}


class Repo:
    def __init__(self, path: Path):
        self.path = path
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

    def commit_raw(self, name: bytes, content: bytes) -> str:
        """Commit one file named by raw bytes, through Git plumbing alone.

        Some filesystems refuse a name that is not UTF-8, so the file never
        reaches the working tree.
        """
        blob = (
            subprocess.run(
                ["git", "-C", str(self.path), "hash-object", "-w", "--stdin"],
                input=content,
                check=True,
                capture_output=True,
            )
            .stdout.decode()
            .strip()
        )
        subprocess.run(
            ["git", "-C", str(self.path), "update-index", "--add", "--cacheinfo"]
            + [b"100644," + blob.encode() + b"," + name],
            check=True,
            capture_output=True,
        )
        self.git("commit", "-q", "-m", "raw name")
        return self.git("rev-parse", "HEAD")

    def commit(self, files: dict, message: str = "change") -> str:
        for name, content in files.items():
            target = self.path / name
            if content is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "repo").mkdir()
    repository = Repo(tmp_path / "repo")
    repository.commit(
        {
            "README.md": "readme\n",
            "src/app.py": "app\n",
            "tests/test_app.py": "test\n",
            "tools/tool.py": "tool\n",
        },
        "base",
    )
    repository.git("checkout", "-q", "-b", "pr")
    return repository


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(FIXTURE), encoding="utf-8")
    return path


def run_planner(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(PLANNER), *map(str, args)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def pr_plan(repo, catalog, body=None, head="HEAD", json_form=True):
    args = [
        "--repo",
        repo.path,
        "--catalog",
        catalog,
        "--base",
        "master",
        "--head",
        head,
    ]
    if body is not None:
        request = repo.path.parent / "body.md"
        request.write_text(body, encoding="utf-8")
        args += ["--request-file", request]
    if json_form:
        args.append("--json")
    return run_planner(*args)


def push_plan(repo, catalog, before, after):
    return run_planner(
        "--repo",
        repo.path,
        "--catalog",
        catalog,
        "--before",
        before,
        "--after",
        after,
        "--json",
    )


def loaded(result, code=0):
    assert result.returncode == code, result.stdout + result.stderr
    return json.loads(result.stdout)


def entry(result_plan, identifier):
    return next(item for item in result_plan["groups"] if item["id"] == identifier)


def codes(result_plan, identifier):
    return [reason["code"] for reason in entry(result_plan, identifier)["reasons"]]


def report(commit, identifier="test.local", outcome="passed", reason=""):
    return f"```local-validation\n{identifier} {commit} {outcome} {reason}\n```\n"


# --------------------------------------------------------------------------
# The catalog


def test_committed_catalog_is_valid():
    result = run_planner("--catalog-check")
    assert result.returncode == 0, result.stderr
    assert "is valid: 4 groups" in result.stdout


def test_committed_catalog_registers_the_initial_groups():
    groups, problems = plan.read_catalog(plan.CATALOG)
    assert problems == []
    assert {g["id"]: g["category"] for g in groups} == {
        "check.static": "floor",
        "test.workflow": "affected",
        "test.package": "affected",
        "test.blender": "local-only",
    }


def invalid(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    result = run_planner("--catalog-check", "--catalog", path)
    assert result.returncode == 2
    return result.stderr


def with_groups(*groups):
    return json.dumps({"schema_version": 1, "groups": list(groups)})


def test_duplicate_id_is_rejected_naming_the_group(tmp_path):
    stderr = invalid(
        tmp_path, with_groups(group("a.b", "floor"), group("a.b", "floor"))
    )
    assert "group 'a.b': duplicate id" in stderr


@pytest.mark.parametrize("identifier", ["build-test", "review-approved"])
def test_a_required_check_name_is_reserved(tmp_path, identifier):
    stderr = invalid(tmp_path, with_groups(group(identifier, "floor")))
    assert (
        f"group {identifier!r}: the id is reserved: {identifier!r} is the name "
        "of a required check"
    ) in stderr
    path = tmp_path / "bad.json"
    with pytest.raises(plan.PlanError, match="is the name of a required check"):
        plan.load_catalog(path)


def test_unknown_category_is_rejected_naming_the_group(tmp_path):
    stderr = invalid(tmp_path, with_groups(group("a.b", "sometimes", ["src/"])))
    assert "group 'a.b': unknown category 'sometimes'" in stderr


@pytest.mark.parametrize("commands", [None, [], [[]], [[""]], "pytest"])
def test_missing_command_is_rejected_naming_the_group(tmp_path, commands):
    broken = group("a.b", "floor")
    if commands is None:
        del broken["commands"]
    else:
        broken["commands"] = commands
    stderr = invalid(tmp_path, with_groups(broken))
    assert "group 'a.b': missing command" in stderr


@pytest.mark.parametrize("category", ["affected", "optional", "local-only"])
def test_missing_patterns_are_rejected_except_for_a_floor_group(tmp_path, category):
    stderr = invalid(tmp_path, with_groups(group("a.b", category)))
    assert "group 'a.b': missing patterns" in stderr
    stderr = invalid(tmp_path, with_groups(group("a.b", category, [])))
    assert "group 'a.b': missing patterns" in stderr


def test_a_floor_group_needs_no_patterns(tmp_path):
    path = tmp_path / "ok.json"
    path.write_text(with_groups(group("a.b", "floor")), encoding="utf-8")
    assert run_planner("--catalog-check", "--catalog", path).returncode == 0


@pytest.mark.parametrize(
    "pattern",
    [
        "",
        "/src/",
        "src/*.py",
        "src/?",
        "src/[ab]",
        "src\\app.py",
        "../src/",
        "src//a",
        "./src/",
        "/",
        " src/",
        3,
    ],
)
def test_invalid_pattern_is_rejected_naming_the_group(tmp_path, pattern):
    stderr = invalid(tmp_path, with_groups(group("a.b", "affected", [pattern])))
    assert "group 'a.b': invalid pattern" in stderr


def test_malformed_json_names_the_file_and_location(tmp_path):
    stderr = invalid(tmp_path, '{"schema_version": 1,\n "groups": [}\n')
    assert "bad.json: malformed JSON at line 2 column" in stderr


def test_duplicate_json_key_is_malformed(tmp_path):
    stderr = invalid(
        tmp_path, '{"schema_version": 1, "schema_version": 1, "groups": []}'
    )
    assert "malformed JSON: duplicate key" in stderr


def test_a_group_without_an_id_is_named_by_position(tmp_path):
    nameless = group("a.b", "floor")
    del nameless["id"]
    stderr = invalid(tmp_path, with_groups(group("x.y", "floor"), nameless))
    assert "groups[1]: missing id" in stderr


def test_structural_errors_name_the_catalog(tmp_path):
    assert "bad.json: the top level must be an object" in invalid(tmp_path, "[]")
    assert "'groups' must be a non-empty list" in invalid(
        tmp_path, '{"schema_version": 1}'
    )


def test_planning_refuses_an_invalid_catalog(repo, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(with_groups(group("a.b", "sometimes")), encoding="utf-8")
    result = pr_plan(repo, path)
    assert result.returncode == 2
    assert "unknown category" in result.stderr


# --------------------------------------------------------------------------
# Path patterns


def test_a_directory_pattern_claims_everything_beneath_it():
    assert plan.matches("src/a.py", "src/")
    assert plan.matches("src/deep/nested/a.py", "src/")
    assert not plan.matches("srcs/a.py", "src/")
    assert not plan.matches("lib/src/a.py", "src/")


def test_a_file_pattern_claims_exactly_that_path():
    assert plan.matches("pyproject.toml", "pyproject.toml")
    assert not plan.matches("pyproject.toml.bak", "pyproject.toml")
    assert not plan.matches("src/a.py", "src")
    assert not plan.matches("sub/pyproject.toml", "pyproject.toml")


# --------------------------------------------------------------------------
# Selection and omission


def test_floor_always_runs_and_unaffected_groups_are_omitted(repo, catalog):
    repo.commit({"tools/tool.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog))
    assert codes(result, "check.static") == ["floor"]
    assert entry(result, "test.tools")["reasons"] == [
        {"code": "affected", "paths": ["tools/tool.py"]}
    ]
    assert codes(result, "test.app") == ["not-affected"]
    assert codes(result, "test.extra") == ["optional-unrequested"]
    assert codes(result, "test.local") == ["not-affected"]
    assert not entry(result, "test.local")["selected"]
    assert result["fail_wide"] == []
    assert result["valid"]


def test_an_optional_group_is_never_selected_by_path(repo, catalog):
    head = repo.commit({"src/app.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog, report(head)))
    assert not entry(result, "test.extra")["selected"]
    assert codes(result, "test.extra") == ["optional-unrequested"]


def test_a_request_selects_an_optional_and_an_unaffected_group(repo, catalog):
    repo.commit({"tools/tool.py": "changed\n"})
    body = "Please run:\n\n```validation-request\ntest.extra\ntest.app\n```\n"
    result = loaded(pr_plan(repo, catalog, body))
    assert result["requested"] == ["test.extra", "test.app"]
    assert codes(result, "test.extra") == ["requested"]
    assert codes(result, "test.app") == ["requested"]
    assert entry(result, "test.extra")["selected"]


def test_a_request_only_adds_to_the_floor(repo, catalog):
    repo.commit({"tools/tool.py": "changed\n"})
    body = "```validation-request\ncheck.static\n```\n"
    result = loaded(pr_plan(repo, catalog, body))
    assert codes(result, "check.static") == ["floor", "requested"]
    assert codes(result, "test.tools") == ["affected"]


def test_a_rename_out_of_a_group_selects_it_by_the_old_path(repo, catalog):
    repo.git("mv", "src/app.py", "tools/app.py")
    head = repo.commit({})
    result = loaded(pr_plan(repo, catalog, report(head)))
    assert result["changed_paths"] == ["src/app.py", "tools/app.py"]
    assert entry(result, "test.app")["reasons"] == [
        {"code": "affected", "paths": ["src/app.py"]}
    ]
    assert entry(result, "test.tools")["reasons"] == [
        {"code": "affected", "paths": ["tools/app.py"]}
    ]
    assert codes(result, "test.local") == ["affected"]


def test_an_unclaimed_path_fails_wide_without_a_local_obligation(repo, catalog):
    repo.commit({"README.md": "changed\n", "tools/tool.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog))
    assert result["unclaimed_paths"] == ["README.md"]
    assert result["fail_wide"] == ["changed paths no group claims: README.md"]
    assert codes(result, "test.app") == ["fail-wide"]
    assert codes(result, "test.tools") == ["affected", "fail-wide"]
    assert codes(result, "check.static") == ["floor"]
    assert codes(result, "test.extra") == ["optional-unrequested"]
    assert codes(result, "test.local") == ["not-affected"]
    assert result["valid"]


def test_a_docs_only_change_selects_no_local_only_group(repo, catalog):
    repo.commit({"docs/guide.md": "guide\n"})
    result = loaded(pr_plan(repo, catalog))
    assert [g["id"] for g in result["groups"] if g["selected"]] == [
        "check.static",
        "test.app",
        "test.tools",
    ]
    assert not entry(result, "test.local")["selected"]


def test_an_empty_comparison_fails_wide(repo, catalog):
    result = loaded(pr_plan(repo, catalog))
    assert result["changed_paths"] == []
    assert result["fail_wide"] == ["the comparison found no changed paths"]
    assert codes(result, "test.app") == ["fail-wide"]


def test_a_pull_request_compares_from_the_merge_base(repo, catalog):
    branch_point = repo.git("rev-parse", "HEAD")
    head = repo.commit({"src/app.py": "changed\n"})
    repo.git("checkout", "-q", "master")
    repo.commit({"tools/tool.py": "base moved on\n", "README.md": "base\n"})
    repo.git("checkout", "-q", "pr")
    result = loaded(pr_plan(repo, catalog, report(head)))
    assert result["comparison"]["merge_base"] == branch_point
    assert result["changed_paths"] == ["src/app.py"]
    assert result["fail_wide"] == []
    assert codes(result, "test.tools") == ["not-affected"]
    assert codes(result, "test.app") == ["affected"]


def test_a_missing_pull_request_base_fails_wide(repo, catalog):
    result = loaded(
        run_planner(
            "--repo",
            repo.path,
            "--catalog",
            catalog,
            "--base",
            "nope",
            "--head",
            "HEAD",
            "--json",
        )
    )
    assert result["changed_paths"] is None
    assert "missing from history" in result["fail_wide"][0]
    assert codes(result, "test.app") == ["fail-wide"]
    assert codes(result, "test.local") == ["not-affected"]
    assert (
        "failing wide adds no local-only group"
        in entry(result, "test.local")["reasons"][0]["note"]
    )


# --------------------------------------------------------------------------
# Push ranges


def test_push_range_compares_before_and_after(repo, catalog):
    before = repo.commit({"tools/tool.py": "one\n"})
    after = repo.commit({"tests/test_app.py": "two\n"})
    result = loaded(push_plan(repo, catalog, before, after))
    assert result["changed_paths"] == ["tests/test_app.py"]
    assert codes(result, "test.app") == ["affected"]
    assert codes(result, "test.tools") == ["not-affected"]


def test_push_range_lists_local_obligations_as_verified_on_the_pull_request(
    repo, catalog
):
    before = repo.git("rev-parse", "HEAD")
    after = repo.commit({"src/app.py": "changed\n"})
    result = loaded(push_plan(repo, catalog, before, after))
    local = entry(result, "test.local")
    assert not local["selected"]
    assert local["reasons"] == [
        {"code": "verified-on-pull-request", "paths": ["src/app.py"]}
    ]
    assert "obligation" not in local
    assert result["valid"]


def test_an_all_zero_before_fails_wide(repo, catalog):
    after = repo.commit({"src/app.py": "changed\n"})
    result = loaded(push_plan(repo, catalog, "0" * 40, after))
    assert result["fail_wide"] == ["the push's before revision is all zeros"]
    assert codes(result, "test.app") == ["fail-wide"]
    assert codes(result, "test.tools") == ["fail-wide"]
    assert codes(result, "test.local") == ["not-affected"]


def test_a_force_push_fails_wide(repo, catalog):
    before = repo.commit({"tools/tool.py": "old\n"})
    repo.git("reset", "-q", "--hard", "HEAD~1")
    after = repo.commit({"tools/tool.py": "new\n"})
    result = loaded(push_plan(repo, catalog, before, after))
    assert result["fail_wide"] == ["before is not an ancestor of after (a force push)"]
    assert codes(result, "test.app") == ["fail-wide"]


def test_missing_history_fails_wide(repo, catalog):
    after = repo.commit({"tools/tool.py": "new\n"})
    result = loaded(push_plan(repo, catalog, "1" * 40, after))
    assert "missing from history" in result["fail_wide"][0]
    assert codes(result, "test.app") == ["fail-wide"]


def test_a_push_takes_no_pull_request_body(repo, catalog, tmp_path):
    body = tmp_path / "body.md"
    body.write_text("", encoding="utf-8")
    result = run_planner(
        "--repo",
        repo.path,
        "--catalog",
        catalog,
        "--before",
        "HEAD",
        "--after",
        "HEAD",
        "--request-file",
        body,
    )
    assert result.returncode == 2
    assert "a push has no pull request body" in result.stderr


# --------------------------------------------------------------------------
# Requests


def request_error(repo, catalog, body):
    repo.commit({"tools/tool.py": "changed\n"})
    result = pr_plan(repo, catalog, body)
    assert result.returncode == 2, result.stdout
    return result.stderr


def test_an_unknown_requested_id_is_an_error(repo, catalog):
    stderr = request_error(repo, catalog, "```validation-request\ntest.nope\n```\n")
    assert "unknown group 'test.nope'" in stderr


def test_two_request_blocks_are_an_error(repo, catalog):
    body = "```validation-request\ntest.app\n```\n\n```validation-request\ntest.extra\n```\n"
    assert "2 validation-request blocks" in request_error(repo, catalog, body)


def test_an_unterminated_request_block_is_an_error(repo, catalog):
    assert "never closed" in request_error(
        repo, catalog, "```validation-request\ntest.app\n"
    )


@pytest.mark.parametrize(
    "info",
    ["validation-request please", "validation-request-extra", "validation-requests"],
)
def test_a_malformed_request_info_string_is_an_error(repo, catalog, info):
    stderr = request_error(repo, catalog, f"```{info}\ntest.extra\n```\n")
    assert "malformed validation-request block" in stderr


def test_a_malformed_request_line_is_an_error(repo, catalog):
    stderr = request_error(
        repo, catalog, "```validation-request\ntest.app test.extra\n```\n"
    )
    assert "one catalog ID per line" in stderr


@pytest.mark.parametrize("outer", ["````markdown", "~~~"])
def test_a_request_block_inside_another_fence_is_documentation(repo, catalog, outer):
    repo.commit({"tools/tool.py": "changed\n"})
    closer = outer.rstrip("markdown")
    body = f"How to ask:\n\n{outer}\n```validation-request\ntest.nope\n```\n{closer}\n"
    result = loaded(pr_plan(repo, catalog, body))
    assert result["requested"] == []


# --------------------------------------------------------------------------
# Local-only reports


def obligation(result_plan):
    return entry(result_plan, "test.local")["obligation"]


def test_a_missing_report_fails_the_obligation(repo, catalog):
    repo.commit({"src/app.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog), code=1)
    assert result["failed_obligations"] == ["test.local"]
    assert obligation(result)["problems"] == ["no local-validation entry reports it"]


@pytest.mark.parametrize(
    "line",
    [
        "test.local abc123 passed",
        "test.local {head}",
        "test.local {head} succeeded",
        "test.local {head} not-run",
        "test.local {head} passed and more",
    ],
)
def test_a_malformed_report_fails_the_obligation(repo, catalog, line):
    head = repo.commit({"src/app.py": "changed\n"})
    body = f"```local-validation\n{line.format(head=head)}\n```\n"
    result = loaded(pr_plan(repo, catalog, body), code=1)
    assert obligation(result)["problems"][0].startswith("malformed entry")


def test_a_failed_report_fails_the_obligation(repo, catalog):
    head = repo.commit({"src/app.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog, report(head, outcome="failed")), code=1)
    assert obligation(result)["problems"] == ["the report says it failed"]


def test_a_not_run_report_fails_the_obligation(repo, catalog):
    head = repo.commit({"src/app.py": "changed\n"})
    body = report(head, outcome="not-run", reason="Blender is not installed")
    result = loaded(pr_plan(repo, catalog, body), code=1)
    assert obligation(result)["problems"] == [
        "the report says it was not run: Blender is not installed"
    ]


def test_a_report_outside_the_heads_history_fails_the_obligation(repo, catalog):
    elsewhere = repo.commit({"src/app.py": "elsewhere\n"})
    repo.git("reset", "-q", "--hard", "HEAD~1")
    repo.commit({"src/app.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog, report(elsewhere)), code=1)
    assert obligation(result)["problems"] == [
        f"the reported commit {elsewhere} is not in the head's history"
    ]


def test_a_report_at_an_unknown_commit_fails_the_obligation(repo, catalog):
    repo.commit({"src/app.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog, report("2" * 40)), code=1)
    assert obligation(result)["problems"] == [
        f"the reported commit {'2' * 40} is missing from history"
    ]


def test_a_stale_report_fails_naming_the_changed_paths(repo, catalog):
    reported = repo.commit({"src/app.py": "changed\n"})
    repo.commit({"src/app.py": "changed again\n", "src/new.py": "new\n"})
    result = loaded(pr_plan(repo, catalog, report(reported)), code=1)
    assert obligation(result)["stale_paths"] == ["src/app.py", "src/new.py"]
    assert "stale" in obligation(result)["problems"][0]
    assert "src/app.py, src/new.py" in obligation(result)["problems"][0]


def test_a_passing_report_at_the_head_meets_the_obligation(repo, catalog):
    head = repo.commit({"src/app.py": "changed\n"})
    result = loaded(pr_plan(repo, catalog, report(head)))
    assert obligation(result)["met"]
    assert result["failed_obligations"] == []


def test_a_passing_ancestor_report_survives_unrelated_changes(repo, catalog):
    reported = repo.commit({"src/app.py": "changed\n"})
    repo.commit({"tools/tool.py": "unrelated\n", "tests/test_app.py": "unrelated\n"})
    result = loaded(pr_plan(repo, catalog, report(reported)))
    assert obligation(result)["met"]


def test_a_requested_local_only_group_needs_evidence(repo, catalog):
    head = repo.commit({"tools/tool.py": "changed\n"})
    body = "```validation-request\ntest.local\n```\n"
    result = loaded(pr_plan(repo, catalog, body), code=1)
    assert codes(result, "test.local") == ["requested"]
    assert obligation(result)["problems"] == ["no local-validation entry reports it"]
    result = loaded(pr_plan(repo, catalog, body + report(head)))
    assert obligation(result)["met"]


def test_duplicate_reports_for_an_obligation_fail_it(repo, catalog):
    head = repo.commit({"src/app.py": "changed\n"})
    body = f"```local-validation\ntest.local {head} passed\ntest.local {head} failed\n```\n"
    result = loaded(pr_plan(repo, catalog, body), code=1)
    assert obligation(result)["problems"] == ["2 local-validation entries report it"]


@pytest.mark.parametrize(
    "info", ["local-validation please", "local-validation-extra", "local-validations"]
)
def test_a_malformed_report_info_string_is_an_error(repo, catalog, info):
    head = repo.commit({"src/app.py": "changed\n"})
    result = pr_plan(repo, catalog, f"```{info}\ntest.local {head} passed\n```\n")
    assert result.returncode == 2
    assert "malformed local-validation block" in result.stderr


def test_two_report_blocks_are_an_error(repo, catalog):
    head = repo.commit({"src/app.py": "changed\n"})
    result = pr_plan(repo, catalog, report(head) + "\n" + report(head))
    assert result.returncode == 2
    assert "2 local-validation blocks" in result.stderr


def test_a_report_for_a_group_that_is_not_an_obligation_is_ignored(repo, catalog):
    repo.commit({"tools/tool.py": "changed\n"})
    body = "```local-validation\ntest.local not-even-a-commit\n```\n"
    result = loaded(pr_plan(repo, catalog, body))
    assert result["ignored_reports"] == ["test.local not-even-a-commit"]
    assert result["valid"]


def test_a_report_inside_another_fence_is_documentation(repo, catalog):
    head = repo.commit({"src/app.py": "changed\n"})
    body = f"````markdown\n{report(head)}````\n"
    result = loaded(pr_plan(repo, catalog, body), code=1)
    assert obligation(result)["problems"] == ["no local-validation entry reports it"]


# --------------------------------------------------------------------------
# Output forms


def text_sections(text):
    """Map each group line in the text plan to its section and reason text."""
    found, section = {}, None
    for line in text.splitlines():
        if line.endswith(":") and not line.startswith(" "):
            section = line if line.startswith(("Selected", "Omitted")) else None
        elif section and line.startswith("  ") and not line.startswith("   "):
            identifier, _, reasons = line.strip().partition("  ")
            found[identifier] = (section, reasons.strip())
    return found


def test_json_and_text_carry_the_same_selections_and_reasons(repo, catalog):
    reported = repo.commit({"src/app.py": "changed\n"})
    repo.commit({"README.md": "changed\n", "src/app.py": "changed again\n"})
    body = "```validation-request\ntest.extra\n```\n" + report(reported)
    as_json = loaded(pr_plan(repo, catalog, body), code=1)
    as_text = pr_plan(repo, catalog, body, json_form=False)
    assert as_text.returncode == 1
    wide = "failing wide: changed paths no group claims: README.md"
    assert text_sections(as_text.stdout) == {
        "check.static": ("Selected, runs on GitHub:", "floor: always runs"),
        "test.app": ("Selected, runs on GitHub:", f"affected by src/app.py; {wide}"),
        "test.tools": ("Selected, runs on GitHub:", wide),
        "test.extra": ("Selected, runs on GitHub:", "requested in the pull request"),
        "test.local": ("Selected, local obligations:", "affected by src/app.py"),
    }
    for item in as_json["groups"]:
        expected = "Omitted:"
        if item["selected"]:
            expected = (
                "Selected, local obligations:"
                if item["local"]
                else "Selected, runs on GitHub:"
            )
        assert text_sections(as_text.stdout)[item["id"]][0] == expected
    assert "Changed paths (2):\n  README.md\n  src/app.py\n" in as_text.stdout
    for cause in as_json["fail_wide"]:
        assert cause in as_text.stdout
    for problem in obligation(as_json)["problems"]:
        assert f"FAILED: {problem}" in as_text.stdout
    assert (
        f"FAILED: the report is stale: its paths changed since {reported}: src/app.py\n"
    ) in as_text.stdout
    assert "Result: failed obligations: test.local" in as_text.stdout


def test_text_names_the_paths_a_push_verifies_on_the_pull_request(repo, catalog):
    before = repo.git("rev-parse", "HEAD")
    after = repo.commit({"src/app.py": "changed\n", "tests/local/a.py": "a\n"})
    result = run_planner(
        "--repo", repo.path, "--catalog", catalog, "--before", before, "--after", after
    )
    assert result.returncode == 0, result.stderr
    assert text_sections(result.stdout)["test.local"] == (
        "Omitted:",
        "verified on the pull request (affected by src/app.py, tests/local/a.py)",
    )
    assert text_sections(result.stdout)["test.app"] == (
        "Selected, runs on GitHub:",
        "affected by src/app.py, tests/local/a.py",
    )


# --------------------------------------------------------------------------
# Paths that are not UTF-8


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("src/app.py", "src/app.py"),
        ("src/café.py", "src/café.py"),
        ("src/caf\udce9.py", '"src/caf\\xe9.py"'),
        ("src/caf\\xe9.py", '"src/caf\\\\xe9.py"'),
        ('src/"a".py', '"src/\\"a\\".py"'),
        ("src/a, b.py", '"src/a, b.py"'),
        ("src/a.py; requested", '"src/a.py; requested"'),
        ("src/a\nb.py", '"src/a\\nb.py"'),
    ],
)
def test_a_path_is_shown_plainly_or_quoted_and_escaped(path, text):
    assert plan.shown(path) == text


def test_text_quotes_a_path_holding_a_reason_or_list_separator(repo, catalog):
    body = "```validation-request\ntest.tools\n```\n"
    repo.commit({"tools/a.py; requested in the pull request": "a\n"})
    delimited = pr_plan(repo, catalog, body, json_form=False)
    assert delimited.returncode == 0, delimited.stdout + delimited.stderr
    assert text_sections(delimited.stdout)["test.tools"] == (
        "Selected, runs on GitHub:",
        'affected by "tools/a.py; requested in the pull request"; '
        "requested in the pull request",
    )
    repo.commit({"tools/b, tools/c.py": "b\n"})
    listed = pr_plan(repo, catalog, json_form=False)
    assert text_sections(listed.stdout)["test.tools"][1] == (
        'affected by "tools/a.py; requested in the pull request", "tools/b, tools/c.py"'
    )


def strict_text_plan(repo, catalog, *args):
    """Run the text form with strict UTF-8 output, and decode it strictly."""
    result = subprocess.run(
        [sys.executable, str(PLANNER), "--repo", str(repo.path)]
        + ["--catalog", str(catalog), *map(str, args)],
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8:strict"},
    )
    return result.returncode, result.stdout.decode(), result.stderr.decode()


def test_text_shows_a_path_that_is_not_utf8_escaped(repo, catalog, tmp_path):
    repo.commit_raw(b"src/caf\xe9.py", b"app\n")
    head = repo.commit_raw(b"caf\xe9.md", b"notes\n")
    body = tmp_path / "body.md"
    body.write_text(report(head), encoding="utf-8")
    code, stdout, stderr = strict_text_plan(
        repo, catalog, "--base", "master", "--head", "HEAD", "--request-file", body
    )
    assert code == 0, stdout + stderr
    assert "Traceback" not in stderr
    assert 'Changed paths (2):\n  "caf\\xe9.md"\n  "src/caf\\xe9.py"\n' in stdout
    assert '  - changed paths no group claims: "caf\\xe9.md"\n' in stdout
    assert text_sections(stdout)["test.local"] == (
        "Selected, local obligations:",
        'affected by "src/caf\\xe9.py"',
    )
    assert f"met: passed at {head}" in stdout
    as_json = loaded(pr_plan(repo, catalog, report(head)))
    assert as_json["changed_paths"] == ["caf\udce9.md", "src/caf\udce9.py"]
    assert as_json["unclaimed_paths"] == ["caf\udce9.md"]


def test_text_names_a_stale_path_that_is_not_utf8(repo, catalog, tmp_path):
    reported = repo.commit({"src/app.py": "changed\n"})
    repo.commit_raw(b"src/caf\xe9.py", b"app\n")
    body = tmp_path / "body.md"
    body.write_text(report(reported), encoding="utf-8")
    code, stdout, stderr = strict_text_plan(
        repo, catalog, "--base", "master", "--head", "HEAD", "--request-file", body
    )
    assert code == 1, stdout + stderr
    assert "Traceback" not in stderr
    assert (
        f"FAILED: the report is stale: its paths changed since {reported}: "
        '"src/caf\\xe9.py"\n'
    ) in stdout


def test_text_shows_a_push_path_that_is_not_utf8(repo, catalog):
    before = repo.git("rev-parse", "HEAD")
    after = repo.commit_raw(b"src/caf\xe9.py", b"app\n")
    code, stdout, stderr = strict_text_plan(
        repo, catalog, "--before", before, "--after", after
    )
    assert code == 0, stdout + stderr
    assert text_sections(stdout)["test.local"] == (
        "Omitted:",
        'verified on the pull request (affected by "src/caf\\xe9.py")',
    )
