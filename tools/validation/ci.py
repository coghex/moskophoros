#!/usr/bin/env python3
"""Run the validation plan on GitHub, and decide `build-test`.

One subcommand for each job of .github/workflows/ci.yml:

- ``plan`` reads the pull request body from the API, plans the tested revision
  with plan.py, checks the CI image descriptor, and records all of it;
- ``run-group`` runs one catalog group's commands exactly as the catalog states
  them, and records the outcome;
- ``await-plan`` and ``await-groups`` run in `build-test`, which starts with
  the run: they poll the run's own jobs until the plan job, then every group
  job it selected, has finished, within a bounded wait;
- ``conclude`` reads the pull request body again, collects every record, and
  decides `build-test`, writing the job summary.

The rules are documented in docs/validation.md, On GitHub. Standard library
only; runs on Python 3.13.
"""

import argparse
import hashlib
import importlib.util
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CATALOG_PATH = "tools/validation/catalog.json"
STATE_FILE = "plan-state.json"
BODY_FILE = "body.md"
STATE_SCHEMA = 1
JOB_RESULTS = ("success", "failure", "cancelled", "skipped")
DEFAULT_TIMEOUT = 15 * 60
PLAN_JOB = "plan"
AGGREGATE_JOB = "build-test"
# The waits `build-test` allows, in seconds. The plan job has 10 minutes and
# each group job 20 in ci.yml, so these cover queueing as well, and together
# stay well inside build-test's own timeout-minutes.
PLAN_WAIT = 15 * 60
GROUPS_WAIT = 30 * 60
DISCOVERY_WAIT = 5 * 60
POLL_INTERVAL = 15
API_TIMEOUT = 30


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = load("plan", HERE / "plan.py")
image_tool = load("image", ROOT / "tools" / "ci-image" / "image.py")


class CIError(Exception):
    """A problem this tool reports as a diagnostic instead of a result."""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise CIError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_body(repository: str, number: int) -> str:
    """Return a pull request's current body from the GitHub API, never a substitute."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/pulls/{number}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise CIError(f"gh api failed: {detail}")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CIError(f"gh api returned malformed JSON: {error}") from None
    if not isinstance(document, dict) or "body" not in document:
        raise CIError("gh api returned no body field")
    body = document["body"]
    if body is None:
        return ""
    if not isinstance(body, str):
        raise CIError(f"gh api returned a body that is not text: {body!r}")
    return body


# --------------------------------------------------------------------------
# plan


def pull_request_range(repo: Path, revision: str) -> tuple[str, str]:
    """The base and head GitHub merged into the tested merge commit, in order."""
    parents = git(repo, "rev-list", "--parents", "-n", "1", revision).split()[1:]
    if len(parents) != 2:
        raise CIError(
            f"the tested revision {revision} is not a merge commit of a base and a "
            "head, so it is not GitHub's merge commit for the pull request"
        )
    return parents[0], parents[1]


def run_planner(
    repo: Path, arguments: list[str], catalog: Path
) -> tuple[int, dict | None, str]:
    process = subprocess.run(
        [
            sys.executable,
            str(HERE / "plan.py"),
            "--json",
            "--repo",
            str(repo),
            "--catalog",
            str(catalog),
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode in (planner.EXIT_VALID, planner.EXIT_OBLIGATION_FAILED):
        try:
            return process.returncode, json.loads(process.stdout), process.stderr
        except json.JSONDecodeError as error:
            return process.returncode, None, f"the plan is not JSON: {error}"
    return process.returncode, None, process.stderr.strip()


def check_image(repo: Path, revision: str) -> tuple[dict, str | None, str | None]:
    """Check the descriptor at `revision`, and return the image it names."""
    root = str(repo)
    try:
        document, _ = image_tool.read_descriptor(root, revision, None)
    except image_tool.ImageError as error:
        return {"status": "error", "message": str(error)}, None, str(error)
    image = f"{document['reference']}@{document['digest']}"
    try:
        value = image_tool.check_descriptor(root, revision, None)
    except image_tool.Mismatch as error:
        return {"status": "stale", "message": str(error)}, image, None
    except image_tool.ImageError as error:
        return {"status": "error", "message": str(error)}, image, None
    return (
        {
            "status": "current",
            "message": f"the descriptor records the tested revision's recipe fingerprint {value}",
        },
        image,
        None,
    )


def make_plan(
    repo: Path,
    event: str,
    revision: str,
    output: Path,
    *,
    repository: str | None = None,
    number: int | None = None,
    before: str | None = None,
    run: dict | None = None,
) -> dict:
    """Plan the tested revision and record everything `conclude` needs."""
    output.mkdir(parents=True, exist_ok=True)
    revision = git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}")
    catalog = repo / CATALOG_PATH
    state = {
        "schema": STATE_SCHEMA,
        "event": event,
        "revision": revision,
        "run": run,
        "pull_request": number,
        "range": None,
        "body": None,
        "errors": [],
        "planner_exit": None,
        "plan": None,
        "descriptor": None,
        "image": None,
        "github_groups": [],
    }
    arguments = None
    if event == "pull_request":
        try:
            body = fetch_body(repository, number)
        except CIError as error:
            state["errors"].append(
                f"could not read pull request #{number}'s body before planning: {error}"
            )
        else:
            (output / BODY_FILE).write_text(body, encoding="utf-8")
            state["body"] = {"sha256": sha256(body), "length": len(body)}
        try:
            base, head = pull_request_range(repo, revision)
        except CIError as error:
            state["errors"].append(str(error))
        else:
            state["range"] = {"base": base, "head": head}
            arguments = ["--base", base, "--head", head]
            if state["body"] is not None:
                arguments += ["--request-file", str(output / BODY_FILE)]
            else:
                arguments = None
    else:
        state["range"] = {"before": before, "after": revision}
        arguments = ["--before", before, "--after", revision]

    if arguments is not None:
        code, plan, detail = run_planner(repo, arguments, catalog)
        state["planner_exit"] = code
        state["plan"] = plan
        if plan is None:
            state["errors"].append(f"the planner failed (exit {code}): {detail}")
        else:
            state["github_groups"] = [
                group["id"]
                for group in plan["groups"]
                if group["selected"] and not group["local"]
            ]

    descriptor, image, problem = check_image(repo, revision)
    state["descriptor"] = descriptor
    state["image"] = image
    if problem:
        state["image_error"] = problem
    (output / STATE_FILE).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return state


# --------------------------------------------------------------------------
# run-group


def run_group(
    repo: Path,
    group_id: str,
    revision: str,
    image: str,
    output: Path,
    timeout: float = DEFAULT_TIMEOUT,
    run: dict | None = None,
) -> dict:
    """Run one group's catalog commands in order, and record what happened."""
    record = {
        "group": group_id,
        "revision": revision,
        "run": run,
        "image": image,
        "outcome": "failed",
        "commands": [],
        "detail": None,
    }

    def finish(outcome: str, detail: str | None = None) -> dict:
        record["outcome"] = outcome
        record["detail"] = detail
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return record

    try:
        groups = planner.load_catalog(repo / CATALOG_PATH)
        checkout = git(repo, "rev-parse", "HEAD")
    except (planner.PlanError, CIError) as error:
        return finish("failed", str(error))
    if checkout != revision:
        return finish(
            "failed", f"the checkout is {checkout}, not the tested revision {revision}"
        )
    group = next((entry for entry in groups if entry["id"] == group_id), None)
    if group is None:
        return finish("failed", f"the catalog has no group {group_id!r}")
    if group["category"] == "local-only":
        return finish("failed", f"{group_id} is local-only and never runs on GitHub")

    deadline = time.monotonic() + timeout
    for command in group["commands"]:
        print(f"$ {shlex.join(command)}", flush=True)
        entry = {"command": command, "exit": None}
        record["commands"].append(entry)
        try:
            process = subprocess.run(
                command,
                cwd=repo,
                stdin=subprocess.DEVNULL,
                timeout=max(deadline - time.monotonic(), 0),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return finish(
                "timed-out",
                f"{shlex.join(command)} was still running after the group's "
                f"{timeout:g}-second limit",
            )
        except OSError as error:
            return finish("failed", f"{shlex.join(command)} could not start: {error}")
        entry["exit"] = process.returncode
        if process.returncode != 0:
            return finish(
                "failed", f"{shlex.join(command)} exited {process.returncode}"
            )
    return finish("passed")


# --------------------------------------------------------------------------
# await-plan and await-groups


def describe_run(run: dict | None) -> str:
    if not isinstance(run, dict):
        return "an unidentified run"
    return f"run {run.get('id')} attempt {run.get('attempt')}"


def fetch_jobs(repository: str, run: dict, timeout: float) -> list[dict]:
    """Every job of this run's attempt, as GitHub reports it now."""
    endpoint = (
        f"repos/{repository}/actions/runs/{run['id']}/attempts/{run['attempt']}"
        "/jobs?per_page=100"
    )
    try:
        result = subprocess.run(
            ["gh", "api", "--paginate", endpoint, "--jq", ".jobs[]"],
            capture_output=True,
            text=True,
            timeout=max(timeout, 1),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise CIError(f"gh api did not answer within {timeout:g} seconds") from None
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise CIError(f"gh api failed: {detail}")
    jobs = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError as error:
            raise CIError(f"gh api returned a malformed job: {error}") from None
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            raise CIError(f"gh api returned a job without a name: {line[:200]}")
        jobs.append(job)
    return jobs


def job_result(conclusions: list[str | None]) -> str:
    """Combine finished jobs' conclusions the way `needs.<job>.result` does."""
    if not conclusions or all(value == "skipped" for value in conclusions):
        return "skipped"
    if all(value == "success" for value in conclusions):
        return "success"
    if any(value == "cancelled" for value in conclusions):
        return "cancelled"
    return "failure"


def await_jobs(
    names: list[str],
    read_jobs,
    *,
    budget: float,
    discovery: float = DISCOVERY_WAIT,
    interval: float = POLL_INTERVAL,
    clock=time.monotonic,
    sleep=time.sleep,
) -> dict[str, str | None]:
    """Wait until every job in `names` has finished; return each conclusion.

    `read_jobs(timeout)` returns the run's jobs or raises CIError. A job that
    has not appeared within `discovery` seconds, or has not finished within
    `budget`, raises CIError naming it; so does a name two jobs share. A read
    that fails is retried until the budget runs out, and no call is given more
    time than remains.
    """
    start = clock()
    deadline = start + budget
    last_error = None
    missing, pending = list(names), []
    while True:
        remaining = deadline - clock()
        try:
            jobs = read_jobs(min(API_TIMEOUT, max(remaining, 0)))
        except CIError as error:
            last_error = str(error)
        else:
            last_error = None
            found = {}
            for job in jobs:
                found.setdefault(job["name"], []).append(job)
            shared = [name for name in names if len(found.get(name, [])) > 1]
            if shared:
                raise CIError(
                    "more than one job of this run is named "
                    + ", ".join(shared)
                    + ", so which one decides is unclear"
                )
            missing = [name for name in names if name not in found]
            pending = [
                name
                for name in names
                if name in found and found[name][0].get("status") != "completed"
            ]
            if not missing and not pending:
                return {name: found[name][0].get("conclusion") for name in names}
            if missing and clock() - start >= discovery:
                raise CIError(
                    "no job of this run is named "
                    + ", ".join(missing)
                    + f" after {discovery:g} seconds"
                )
        remaining = deadline - clock()
        if remaining <= 0:
            waiting = [name for name in names if name in missing or name in pending]
            problem = f"gave up after {budget:g} seconds waiting for " + (
                ", ".join(waiting) if waiting else "the run's jobs"
            )
            if last_error:
                problem += f"; the last read of the run's jobs failed: {last_error}"
            raise CIError(problem)
        sleep(min(interval, remaining))


def expected_groups(state: dict | None, plan_job: str) -> list[str]:
    """The group jobs ci.yml starts: its `groups` job's condition, restated."""
    if plan_job != "success" or state is None or not state.get("image"):
        return []
    return list(state.get("github_groups") or [])


def read_state(plan_dir: Path | None) -> tuple[dict | None, list[str]]:
    """The plan record under `plan_dir`, and a problem if it cannot be used."""
    state_path = plan_dir / STATE_FILE if plan_dir else None
    if state_path is None or not state_path.is_file():
        return None, []
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, [f"the plan record cannot be read: {error}"]
    if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
        return None, ["the plan record is not a record this tool wrote"]
    return state, []


def await_plan(read_jobs, budget: float = PLAN_WAIT, **options) -> str:
    """Wait for this run's plan job; return its result."""
    conclusions = await_jobs([PLAN_JOB], read_jobs, budget=budget, **options)
    return job_result([conclusions[PLAN_JOB]])


def await_groups(
    state: dict | None,
    plan_job: str,
    read_jobs,
    budget: float = GROUPS_WAIT,
    **options,
) -> str:
    """Wait for every group job the plan started; return their combined result."""
    names = expected_groups(state, plan_job)
    if not names:
        return "skipped"
    reserved = {PLAN_JOB, AGGREGATE_JOB} & set(names)
    if reserved:
        raise CIError(
            "the plan selected a group named like one of this run's own jobs: "
            + ", ".join(sorted(reserved))
        )
    conclusions = await_jobs(names, read_jobs, budget=budget, **options)
    return job_result(list(conclusions.values()))


# --------------------------------------------------------------------------
# conclude


def read_records(directory: Path | None) -> tuple[list[dict], list[str]]:
    """Every group record under `directory`, and a problem for each unreadable one."""
    records, problems = [], []
    if directory is None or not directory.is_dir():
        return records, problems
    for path in sorted(directory.rglob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            problems.append(f"the group record {path.name} cannot be read: {error}")
            continue
        if not isinstance(record, dict) or not isinstance(record.get("group"), str):
            problems.append(f"the group record {path.name} is malformed")
            continue
        records.append(record)
    return records, problems


def decide(
    state: dict | None,
    records: list[dict],
    plan_job: str,
    groups_job: str,
    final_body: str | None = None,
    final_body_error: str | None = None,
    record_problems: list[str] | None = None,
    run: dict | None = None,
) -> dict:
    """Decide `build-test`: every failure, and each selected group's status.

    `final_body` is the pull request body read just before concluding, or
    None with `final_body_error` saying why it could not be read. `run`, when
    given, is this run's ID and attempt, and every record must carry it.
    Anything absent, skipped or unreadable is a failure, never a pass.
    """
    failures = list(record_problems or [])
    statuses = {}
    if state is None:
        failures.insert(
            0,
            f"the plan was not produced: the plan job concluded {plan_job} "
            "and left no record",
        )
        return {"passed": False, "failures": failures, "statuses": statuses}

    failures.extend(state["errors"])
    if run is not None and state.get("run") != run:
        failures.append(
            f"the plan was recorded by {describe_run(state.get('run'))}, not by "
            f"this one, {describe_run(run)}"
        )
    if plan_job != "success" and not state["errors"]:
        failures.append(f"the plan job concluded {plan_job}")
    plan = state["plan"]
    if state["event"] == "pull_request" and plan is not None:
        for entry in plan["groups"]:
            obligation = entry.get("obligation")
            if obligation and not obligation["met"]:
                failures.append(
                    f"the local-only group {entry['id']} has no fresh passing report: "
                    + "; ".join(obligation["problems"])
                )

    descriptor = state["descriptor"]
    if descriptor["status"] == "stale":
        failures.append(f"the CI image descriptor is stale: {descriptor['message']}")
    elif descriptor["status"] != "current":
        failures.append(
            f"the CI image descriptor cannot be checked: {descriptor['message']}"
        )

    selected = state["github_groups"]
    by_group = {}
    for record in records:
        by_group.setdefault(record["group"], []).append(record)
    for group_id in sorted(set(by_group) - set(selected)):
        failures.append(
            f"{group_id} ran, but the plan did not select it to run on GitHub"
        )
    group_failed = False
    for group_id in selected:
        found = by_group.get(group_id, [])
        if not found:
            status = groups_job if groups_job in ("skipped", "cancelled") else "missing"
            statuses[group_id] = status
            failures.append(
                f"{group_id} {status}: no result was recorded "
                f"(the group jobs concluded {groups_job})"
            )
            group_failed = True
            continue
        if len(found) > 1:
            statuses[group_id] = "failed"
            failures.append(f"{group_id} recorded {len(found)} results; expected one")
            group_failed = True
            continue
        record = found[0]
        statuses[group_id] = record.get("outcome")
        if record.get("outcome") != "passed":
            detail = record.get("detail") or "no detail recorded"
            failures.append(f"{group_id} {record.get('outcome')}: {detail}")
            group_failed = True
        if record.get("revision") != state["revision"]:
            failures.append(
                f"{group_id} ran at {record.get('revision')}, not the tested "
                f"revision {state['revision']}"
            )
            group_failed = True
        if run is not None and record.get("run") != run:
            failures.append(
                f"{group_id} was recorded by {describe_run(record.get('run'))}, "
                f"not by this one, {describe_run(run)}"
            )
            group_failed = True
        if record.get("image") != state["image"]:
            failures.append(
                f"{group_id} ran in {record.get('image')}, not the descriptor's "
                f"image {state['image']}"
            )
            group_failed = True
    if selected and groups_job != "success" and not group_failed:
        failures.append(f"the group jobs concluded {groups_job}")

    if state["event"] == "pull_request" and state["body"] is not None:
        if final_body is None:
            failures.append(
                "could not read the pull request body again before concluding, so "
                "whether it changed since planning is unconfirmed: "
                + (final_body_error or "no reason given")
            )
        elif sha256(final_body) != state["body"]["sha256"]:
            failures.append(
                "the pull request body changed since this run planned from it; "
                "the run that edit started decides"
            )
    return {"passed": not failures, "failures": failures, "statuses": statuses}


def summary(state: dict | None, verdict: dict) -> str:
    """The job summary: the verdict, each failure, and the whole plan."""
    lines = [f"## build-test: {'passed' if verdict['passed'] else 'failed'}", ""]
    if verdict["failures"]:
        lines += ["### Failures", ""]
        lines += [f"- {failure}" for failure in verdict["failures"]]
        lines.append("")
    if state is None:
        return "\n".join(lines)
    revision = state["revision"]
    span = state["range"] or {}
    if state["event"] == "pull_request":
        tested = f"`{revision}`, GitHub's merge commit for pull request #{state['pull_request']}"
        if span:
            tested += f" (base `{span['base']}`, head `{span['head']}`)"
    else:
        tested = f"`{revision}`, the pushed revision"
    lines += [
        "| | |",
        "|---|---|",
        f"| Tested revision | {tested} |",
        f"| Image | `{state['image'] or 'none'}` |",
        f"| Descriptor | {state['descriptor']['status']}: {state['descriptor']['message']} |",
    ]
    if state["event"] == "pull_request":
        body = state["body"]
        lines.append(
            "| Pull request body | "
            + (
                f"read from the API, sha256 `{body['sha256'][:12]}`"
                if body
                else "not read"
            )
            + " |"
        )
    lines.append("")
    if state["github_groups"]:
        lines += ["### Groups run on GitHub", "", "| Group | Result |", "|---|---|"]
        lines += [
            f"| `{group_id}` | {verdict['statuses'].get(group_id, 'missing')} |"
            for group_id in state["github_groups"]
        ]
        lines.append("")
    plan = state["plan"]
    if plan is not None:
        local = [entry for entry in plan["groups"] if entry["local"]]
        if local:
            lines += ["### Local-only groups", ""]
            for entry in local:
                if "obligation" in entry:
                    obligation = entry["obligation"]
                    text = (
                        f"obligation met: passed at `{obligation['commit']}`"
                        if obligation["met"]
                        else "obligation FAILED: " + "; ".join(obligation["problems"])
                    )
                else:
                    text = "; ".join(planner.describe(r) for r in entry["reasons"])
                lines.append(f"- `{entry['id']}`: {text}")
            lines.append("")
        lines += ["### Plan", "", "```text", planner.render(plan), "```", ""]
    return "\n".join(lines)


def conclude(
    plan_dir: Path | None,
    results_dir: Path | None,
    plan_job: str,
    groups_job: str,
    repository: str | None,
    run: dict | None = None,
) -> tuple[dict | None, dict]:
    state, problems = read_state(plan_dir)
    records, record_problems = read_records(results_dir)
    final_body = final_body_error = None
    if state is not None and state["event"] == "pull_request":
        try:
            final_body = fetch_body(repository, state["pull_request"])
        except CIError as error:
            final_body_error = str(error)
    verdict = decide(
        state,
        records,
        plan_job,
        groups_job,
        final_body,
        final_body_error,
        problems + record_problems,
        run,
    )
    return state, verdict


# --------------------------------------------------------------------------
# Command line


def write_output(path: Path | None, values: dict[str, str]) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        for name, value in values.items():
            handle.write(f"{name}={value}\n")


def add_run_arguments(parser: argparse.ArgumentParser, required: bool) -> None:
    parser.add_argument(
        "--run-id", type=int, required=required, help="this workflow run's ID"
    )
    parser.add_argument(
        "--run-attempt", type=int, required=required, help="its attempt number"
    )


def run_of(arguments: argparse.Namespace) -> dict | None:
    if arguments.run_id is None and arguments.run_attempt is None:
        return None
    if arguments.run_id is None or arguments.run_attempt is None:
        raise CIError("--run-id and --run-attempt go together")
    return {"id": arguments.run_id, "attempt": arguments.run_attempt}


def fail_waiting(summary_path: Path | None, problem: str) -> int:
    """Report a wait that could not finish as `build-test`'s failure."""
    text = f"## build-test: failed\n\n### Failures\n\n- {problem}\n"
    print(text)
    if summary_path is not None:
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write(text)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ci.py",
        description="Run the validation plan on GitHub (docs/validation.md).",
    )
    parser.add_argument(
        "--repo", type=Path, default=Path("."), help="the checkout (default .)"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    planning = commands.add_parser("plan", help="plan the tested revision")
    planning.add_argument("--event", choices=("pull_request", "push"), required=True)
    planning.add_argument("--revision", required=True, help="the tested revision")
    planning.add_argument("--repository", help="owner/name, for a pull request")
    planning.add_argument("--pull-request", type=int, help="its number")
    planning.add_argument("--before", help="a push's before revision")
    planning.add_argument("--output", type=Path, required=True)
    planning.add_argument("--github-output", type=Path)
    add_run_arguments(planning, required=False)

    running = commands.add_parser("run-group", help="run one group's commands")
    running.add_argument("--group", required=True)
    running.add_argument("--revision", required=True)
    running.add_argument("--image", required=True)
    running.add_argument("--output", type=Path, required=True)
    running.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    add_run_arguments(running, required=False)

    for name, budget, what in (
        ("await-plan", PLAN_WAIT, "wait for this run's plan job"),
        ("await-groups", GROUPS_WAIT, "wait for the group jobs the plan started"),
    ):
        waiting = commands.add_parser(name, help=what)
        waiting.add_argument("--repository", required=True, help="owner/name")
        add_run_arguments(waiting, required=True)
        waiting.add_argument("--budget", type=float, default=budget)
        waiting.add_argument("--github-output", type=Path)
        waiting.add_argument("--summary", type=Path)
        if name == "await-groups":
            waiting.add_argument("--plan-dir", type=Path)
            waiting.add_argument("--plan-job", choices=JOB_RESULTS, required=True)

    concluding = commands.add_parser("conclude", help="decide build-test")
    concluding.add_argument("--plan-dir", type=Path)
    concluding.add_argument("--results-dir", type=Path)
    concluding.add_argument("--plan-job", choices=JOB_RESULTS, required=True)
    concluding.add_argument("--groups-job", choices=JOB_RESULTS, required=True)
    concluding.add_argument("--repository", help="owner/name, for a pull request")
    concluding.add_argument("--summary", type=Path)
    add_run_arguments(concluding, required=False)

    arguments = parser.parse_args(argv)
    repo = arguments.repo.resolve()
    try:
        if arguments.command == "plan":
            if arguments.event == "pull_request" and not (
                arguments.repository and arguments.pull_request
            ):
                raise CIError("a pull request needs --repository and --pull-request")
            if arguments.event == "push" and not arguments.before:
                raise CIError("a push needs --before")
            state = make_plan(
                repo,
                arguments.event,
                arguments.revision,
                arguments.output,
                repository=arguments.repository,
                number=arguments.pull_request,
                before=arguments.before,
                run=run_of(arguments),
            )
            write_output(
                arguments.github_output,
                {
                    "groups": json.dumps(state["github_groups"]),
                    "image": state["image"] or "",
                },
            )
            if state["plan"] is not None:
                print(planner.render(state["plan"]))
            for problem in [*state["errors"], state.get("image_error")]:
                if problem:
                    print(f"ci.py: {problem}", file=sys.stderr)
            return 1 if state["errors"] else 0
        if arguments.command == "run-group":
            record = run_group(
                repo,
                arguments.group,
                arguments.revision,
                arguments.image,
                arguments.output,
                arguments.timeout,
                run_of(arguments),
            )
            print(f"{record['group']}: {record['outcome']}")
            if record["detail"]:
                print(record["detail"], file=sys.stderr)
            return 0 if record["outcome"] == "passed" else 1
        if arguments.command in ("await-plan", "await-groups"):
            run = run_of(arguments)

            def read_jobs(timeout: float) -> list[dict]:
                return fetch_jobs(arguments.repository, run, timeout)

            try:
                if arguments.command == "await-plan":
                    name = "plan_job"
                    result = await_plan(read_jobs, arguments.budget)
                else:
                    name = "groups_job"
                    state, _ = read_state(arguments.plan_dir)
                    result = await_groups(
                        state, arguments.plan_job, read_jobs, arguments.budget
                    )
            except CIError as error:
                return fail_waiting(arguments.summary, str(error))
            print(f"{name}: {result}")
            write_output(arguments.github_output, {name: result})
            return 0
        state, verdict = conclude(
            arguments.plan_dir,
            arguments.results_dir,
            arguments.plan_job,
            arguments.groups_job,
            arguments.repository,
            run_of(arguments),
        )
        text = summary(state, verdict)
        print(text)
        if arguments.summary is not None:
            with arguments.summary.open("a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        return 0 if verdict["passed"] else 1
    except CIError as error:
        print(f"ci.py: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
