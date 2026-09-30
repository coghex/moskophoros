#!/usr/bin/env python3
"""Run the validation plan on GitHub, and decide `build-test`.

One subcommand for each job of .github/workflows/ci.yml:

- ``plan`` reads the pull request body from the API, plans the tested revision
  with plan.py, checks the CI image descriptor, and records all of it;
- ``run-group`` runs one catalog group's commands exactly as the catalog states
  them, and records the outcome;
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
) -> dict:
    """Plan the tested revision and record everything `conclude` needs."""
    output.mkdir(parents=True, exist_ok=True)
    revision = git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}")
    catalog = repo / CATALOG_PATH
    state = {
        "schema": STATE_SCHEMA,
        "event": event,
        "revision": revision,
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
) -> dict:
    """Run one group's catalog commands in order, and record what happened."""
    record = {
        "group": group_id,
        "revision": revision,
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
) -> dict:
    """Decide `build-test`: every failure, and each selected group's status.

    `final_body` is the pull request body read just before concluding, or
    None with `final_body_error` saying why it could not be read. Anything
    absent, skipped or unreadable is a failure, never a pass.
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
) -> tuple[dict | None, dict]:
    state = None
    problems = []
    state_path = plan_dir / STATE_FILE if plan_dir else None
    if state_path is not None and state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            problems.append(f"the plan record cannot be read: {error}")
        else:
            if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
                problems.append("the plan record is not a record this tool wrote")
                state = None
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

    running = commands.add_parser("run-group", help="run one group's commands")
    running.add_argument("--group", required=True)
    running.add_argument("--revision", required=True)
    running.add_argument("--image", required=True)
    running.add_argument("--output", type=Path, required=True)
    running.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    concluding = commands.add_parser("conclude", help="decide build-test")
    concluding.add_argument("--plan-dir", type=Path)
    concluding.add_argument("--results-dir", type=Path)
    concluding.add_argument("--plan-job", choices=JOB_RESULTS, required=True)
    concluding.add_argument("--groups-job", choices=JOB_RESULTS, required=True)
    concluding.add_argument("--repository", help="owner/name, for a pull request")
    concluding.add_argument("--summary", type=Path)

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
            )
            print(f"{record['group']}: {record['outcome']}")
            if record["detail"]:
                print(record["detail"], file=sys.stderr)
            return 0 if record["outcome"] == "passed" else 1
        state, verdict = conclude(
            arguments.plan_dir,
            arguments.results_dir,
            arguments.plan_job,
            arguments.groups_job,
            arguments.repository,
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
