#!/usr/bin/env python3
"""Explain which validation groups a change requires.

Reads the catalog of test groups next to this file, compares two revisions,
and explains every group as selected or omitted, with its reason. It also
checks a pull request's validation requests and its local-only reports. The
rules are documented in docs/validation.md.

Standard library only; runs on Python 3.13.
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

CATALOG = Path(__file__).resolve().with_name("catalog.json")
SCHEMA_VERSION = 1
CATEGORIES = ("floor", "affected", "optional", "local-only")
TOP_KEYS = {"schema_version", "groups"}
GROUP_KEYS = {"id", "description", "category", "commands", "paths"}
ID_PATTERN = re.compile(r"[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
FENCE_PATTERN = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
REQUEST_BLOCK = "validation-request"
REPORT_BLOCK = "local-validation"
OUTCOMES = ("passed", "failed", "not-run")

EXIT_VALID = 0
EXIT_OBLIGATION_FAILED = 1
EXIT_ERROR = 2


class PlanError(Exception):
    """An input the planner refuses; it exits with EXIT_ERROR and the message."""


class DuplicateKey(Exception):
    pass


# --------------------------------------------------------------------------
# The catalog


def pattern_problem(pattern: object) -> str | None:
    """Return why `pattern` is not a valid path pattern, or None if it is."""
    if not isinstance(pattern, str) or not pattern:
        return f"{pattern!r} is not a non-empty string"
    if pattern != pattern.strip():
        return f"{pattern!r} has leading or trailing whitespace"
    if pattern.startswith("/"):
        return f"{pattern!r} starts with '/'; patterns are repository-relative"
    if any(character in pattern for character in "\\*?["):
        return f"{pattern!r} uses '\\', '*', '?' or '[', which patterns do not support"
    segments = pattern.removesuffix("/").split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return f"{pattern!r} has an empty, '.' or '..' segment"
    return None


def matches(path: str, pattern: str) -> bool:
    """A pattern ending in '/' claims everything beneath it; any other names one file."""
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    document = {}
    for key, value in pairs:
        if key in document:
            raise DuplicateKey(key)
        document[key] = value
    return document


def read_catalog(path: Path) -> tuple[list[dict], list[str]]:
    """Return the catalog's groups and every problem found in it."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [], [f"catalog {path}: cannot be read: {error}"]
    try:
        document = json.loads(text, object_pairs_hook=unique_keys)
    except json.JSONDecodeError as error:
        return [], [
            f"catalog {path}: malformed JSON at line {error.lineno} "
            f"column {error.colno}: {error.msg}"
        ]
    except DuplicateKey as error:
        return [], [f"catalog {path}: malformed JSON: duplicate key {error}"]
    problems = catalog_problems(document, str(path))
    groups = document.get("groups") if isinstance(document, dict) else None
    return (groups if isinstance(groups, list) else []), problems


def catalog_problems(document: object, source: str) -> list[str]:
    """List every problem in a parsed catalog, naming the group where it can."""
    if not isinstance(document, dict):
        return [f"catalog {source}: the top level must be an object"]
    problems = [
        f"catalog {source}: unknown top-level key {key!r}"
        for key in sorted(document.keys() - TOP_KEYS)
    ]
    if document.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"catalog {source}: schema_version must be {SCHEMA_VERSION}")
    groups = document.get("groups")
    if not isinstance(groups, list) or not groups:
        problems.append(f"catalog {source}: 'groups' must be a non-empty list")
        return problems
    seen = set()
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            problems.append(f"catalog {source}: groups[{index}] must be an object")
            continue
        identifier = group.get("id")
        if isinstance(identifier, str) and identifier:
            where = f"catalog {source}: group {identifier!r}"
            if not ID_PATTERN.fullmatch(identifier):
                problems.append(
                    f"{where}: the id must be dot-separated lower-case words, "
                    "such as 'test.package'"
                )
            if identifier in seen:
                problems.append(f"{where}: duplicate id")
            seen.add(identifier)
        else:
            where = f"catalog {source}: groups[{index}]"
            problems.append(f"{where}: missing id")
        problems.extend(
            f"{where}: unknown key {key!r}" for key in sorted(group.keys() - GROUP_KEYS)
        )
        description = group.get("description")
        if not isinstance(description, str) or not description.strip():
            problems.append(f"{where}: missing description")
        category = group.get("category")
        if not isinstance(category, str) or category not in CATEGORIES:
            problems.append(
                f"{where}: unknown category {category!r}; "
                f"use one of {', '.join(CATEGORIES)}"
            )
        commands = group.get("commands")
        if not (
            isinstance(commands, list)
            and commands
            and all(
                isinstance(command, list)
                and command
                and all(isinstance(word, str) and word for word in command)
                for command in commands
            )
        ):
            problems.append(
                f"{where}: missing command: 'commands' must be a non-empty list "
                "of commands, each a non-empty list of arguments"
            )
        paths = group.get("paths", [])
        if not isinstance(paths, list):
            problems.append(f"{where}: 'paths' must be a list of patterns")
            continue
        if not paths and category != "floor":
            problems.append(
                f"{where}: missing patterns: only a floor group may omit 'paths'"
            )
        for pattern in paths:
            problem = pattern_problem(pattern)
            if problem:
                problems.append(f"{where}: invalid pattern {problem}")
    return problems


def load_catalog(path: Path) -> list[dict]:
    groups, problems = read_catalog(path)
    if problems:
        raise PlanError("the catalog is invalid:\n" + "\n".join(problems))
    return groups


# --------------------------------------------------------------------------
# Pull request bodies


def top_level_fences(text: str) -> list[dict]:
    """Return every top-level fenced block: its info string, lines and closure.

    A fence inside another fenced block is only that block's content, so an
    example in documentation is never read as a block of its own.
    """
    blocks = []
    current = None
    for line in text.splitlines():
        match = FENCE_PATTERN.fullmatch(line.rstrip())
        if current is None:
            if match is None:
                continue
            marker, info = match.groups()
            if marker[0] == "`" and "`" in info:
                continue
            current = {
                "marker": marker,
                "info": info.strip(),
                "lines": [],
                "closed": False,
            }
            blocks.append(current)
            continue
        marker = current["marker"]
        if (
            match is not None
            and match.group(1)[0] == marker[0]
            and len(match.group(1)) >= len(marker)
            and not match.group(2).strip()
        ):
            current["closed"] = True
            current = None
        else:
            current["lines"].append(line)
    return blocks


def named_block(text: str, name: str, source: str) -> list[str] | None:
    """Return the lines of the one top-level block named `name`, or None."""
    found = []
    for block in top_level_fences(text):
        if not block["info"].startswith(name):
            continue
        if block["info"] != name:
            raise PlanError(
                f"{source}: malformed {name} block: its info string must be "
                f"exactly {name!r}, not {block['info']!r}"
            )
        if not block["closed"]:
            raise PlanError(f"{source}: the {name} block is never closed")
        found.append(block)
    if len(found) > 1:
        raise PlanError(f"{source}: {len(found)} {name} blocks; use exactly one")
    return found[0]["lines"] if found else None


def parse_request(text: str, source: str, known: set[str]) -> list[str]:
    """Return the catalog IDs the body's validation-request block names."""
    lines = named_block(text, REQUEST_BLOCK, source)
    requested = []
    for line in lines or []:
        entry = line.strip()
        if not entry:
            continue
        if len(entry.split()) > 1:
            raise PlanError(
                f"{source}: malformed {REQUEST_BLOCK} line {entry!r}; "
                "list one catalog ID per line"
            )
        if entry not in known:
            raise PlanError(f"{source}: {REQUEST_BLOCK} names unknown group {entry!r}")
        if entry not in requested:
            requested.append(entry)
    return requested


def parse_reports(text: str, source: str) -> list[dict]:
    """Return the body's local-validation entries, each with any problem found."""
    lines = named_block(text, REPORT_BLOCK, source)
    entries = []
    for line in lines or []:
        words = line.split(maxsplit=3)
        if not words:
            continue
        entry = {"line": line.strip(), "group": words[0], "problem": None}
        entries.append(entry)
        if len(words) < 3:
            entry["problem"] = "expected '<group> <commit> <outcome>'"
            continue
        commit, outcome = words[1].lower(), words[2]
        reason = words[3] if len(words) == 4 else None
        if not COMMIT_PATTERN.fullmatch(commit):
            entry["problem"] = f"{words[1]!r} is not a full 40-character commit"
        elif outcome not in OUTCOMES:
            entry["problem"] = (
                f"unknown outcome {outcome!r}; use one of {', '.join(OUTCOMES)}"
            )
        elif outcome == "not-run" and reason is None:
            entry["problem"] = "a not-run outcome needs a reason"
        elif outcome != "not-run" and reason is not None:
            entry["problem"] = f"only a not-run outcome takes a reason, not {outcome!r}"
        else:
            entry.update(commit=commit, outcome=outcome, reason=reason)
    return entries


# --------------------------------------------------------------------------
# Git


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )


def resolve(repo: Path, revision: str) -> str | None:
    """Return the full commit a revision names, or None if history lacks it."""
    result = git(repo, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}")
    return result.stdout.decode().strip() if result.returncode == 0 else None


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool | None:
    """True or False, or None when git cannot tell."""
    result = git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    return {0: True, 1: False}.get(result.returncode)


def changed_between(repo: Path, old: str, new: str) -> list[str] | None:
    """Paths that differ between two commits; a rename counts as both paths."""
    result = git(repo, "diff", "--no-renames", "--name-only", "-z", old, new, "--")
    if result.returncode != 0:
        return None
    names = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    return sorted({name for name in names if name})


def pull_request_range(
    repo: Path, base: str, head: str
) -> tuple[dict, list[str] | None, list[str]]:
    """Compare the merge base of `base` and `head` with `head` (three-dot)."""
    head_commit = resolve(repo, head)
    comparison = {
        "kind": "pull_request",
        "base": base,
        "head": head,
        "head_commit": head_commit,
    }
    base_commit = resolve(repo, base)
    if base_commit is None:
        return comparison, None, [f"the base revision {base!r} is missing from history"]
    if head_commit is None:
        return comparison, None, [f"the head revision {head!r} is missing from history"]
    result = git(repo, "merge-base", base_commit, head_commit)
    if result.returncode != 0:
        return (
            comparison,
            None,
            ["the base and head have no merge base to compare from"],
        )
    merge_base = result.stdout.decode().split()[0]
    comparison["merge_base"] = merge_base
    paths = changed_between(repo, merge_base, head_commit)
    if paths is None:
        return comparison, None, ["git could not compare the merge base with the head"]
    return comparison, paths, []


def push_range(
    repo: Path, before: str, after: str
) -> tuple[dict, list[str] | None, list[str]]:
    """Compare a push's `before` and `after` revisions (two-dot)."""
    after_commit = resolve(repo, after)
    comparison = {
        "kind": "push",
        "before": before,
        "after": after,
        "after_commit": after_commit,
    }
    if before and set(before) == {"0"}:
        return comparison, None, ["the push's before revision is all zeros"]
    before_commit = resolve(repo, before)
    if before_commit is None:
        return (
            comparison,
            None,
            [f"the before revision {before!r} is missing from history"],
        )
    if after_commit is None:
        return (
            comparison,
            None,
            [f"the after revision {after!r} is missing from history"],
        )
    ancestry = is_ancestor(repo, before_commit, after_commit)
    if ancestry is None:
        return (
            comparison,
            None,
            ["git could not tell whether before is an ancestor of after"],
        )
    if not ancestry:
        return comparison, None, ["before is not an ancestor of after (a force push)"]
    paths = changed_between(repo, before_commit, after_commit)
    if paths is None:
        return comparison, None, ["git could not compare before with after"]
    return comparison, paths, []


# --------------------------------------------------------------------------
# The plan


def affected_paths(group: dict, paths: list[str]) -> list[str]:
    return [
        path for path in paths if any(matches(path, p) for p in group.get("paths", []))
    ]


def check_obligation(
    repo: Path, group: dict, head: str | None, entries: list[dict]
) -> dict:
    """Decide whether the body's report satisfies one local-only obligation."""
    reports = [entry for entry in entries if entry["group"] == group["id"]]
    if not reports:
        return {"met": False, "problems": [f"no {REPORT_BLOCK} entry reports it"]}
    if len(reports) > 1:
        return {
            "met": False,
            "problems": [f"{len(reports)} {REPORT_BLOCK} entries report it"],
        }
    report = reports[0]
    if report["problem"]:
        return {
            "met": False,
            "problems": [f"malformed entry {report['line']!r}: {report['problem']}"],
        }
    commit, problems, stale = report["commit"], [], []
    if report["outcome"] == "failed":
        problems.append("the report says it failed")
    elif report["outcome"] == "not-run":
        problems.append(f"the report says it was not run: {report['reason']}")
    if head is None:
        problems.append(
            "the head is missing from history, so the report cannot be checked"
        )
    elif resolve(repo, commit) is None:
        problems.append(f"the reported commit {commit} is missing from history")
    else:
        ancestry = is_ancestor(repo, commit, head)
        if ancestry is None:
            problems.append(
                f"git could not tell whether {commit} is in the head's history"
            )
        elif not ancestry:
            problems.append(
                f"the reported commit {commit} is not in the head's history"
            )
        else:
            since = changed_between(repo, commit, head)
            if since is None:
                problems.append(f"git could not compare {commit} with the head")
            else:
                stale = affected_paths(group, since)
                if stale:
                    problems.append(
                        f"the report is stale: its paths changed since {commit}: "
                        + ", ".join(stale)
                    )
    result = {
        "met": not problems,
        "problems": problems,
        "commit": commit,
        "outcome": report["outcome"],
    }
    if stale:
        result["stale_paths"] = stale
    return result


def build_plan(
    repo: Path,
    groups: list[dict],
    comparison: dict,
    paths: list[str] | None,
    causes: list[str],
    requested: list[str],
    reports: list[dict] | None,
) -> dict:
    """Explain every catalog group as selected or omitted, with its reasons."""
    pull_request = comparison["kind"] == "pull_request"
    causes = list(causes)
    unclaimed = []
    if paths is not None:
        if not paths:
            causes.append("the comparison found no changed paths")
        claimed = {path for group in groups for path in affected_paths(group, paths)}
        unclaimed = [path for path in paths if path not in claimed]
        if unclaimed:
            causes.append("changed paths no group claims: " + ", ".join(unclaimed))
    explained = []
    for group in groups:
        category = group["category"]
        hits = affected_paths(group, paths or [])
        reasons = []
        if category == "floor":
            reasons.append({"code": "floor"})
        if category in ("affected", "local-only") and hits:
            reasons.append({"code": "affected", "paths": hits})
        if category == "affected" and causes:
            reasons.append({"code": "fail-wide", "causes": causes})
        if group["id"] in requested:
            reasons.append({"code": "requested"})
        local = category == "local-only"
        entry = {
            "id": group["id"],
            "category": category,
            "description": group["description"],
            "commands": group["commands"],
            "selected": bool(reasons),
            "local": local,
            "reasons": reasons,
        }
        if local and reasons and not pull_request:
            entry["selected"] = False
            entry["reasons"] = [{"code": "verified-on-pull-request", "paths": hits}]
        elif not reasons:
            if category == "optional":
                entry["reasons"] = [{"code": "optional-unrequested"}]
            else:
                omission = {"code": "not-affected"}
                if paths is None:
                    omission["note"] = (
                        "the comparison failed, and failing wide adds no local-only group"
                    )
                entry["reasons"] = [omission]
        if local and entry["selected"]:
            entry["obligation"] = check_obligation(
                repo, group, comparison.get("head_commit"), reports or []
            )
        explained.append(entry)
    obliged = {entry["id"] for entry in explained if "obligation" in entry}
    ignored = [entry for entry in reports or [] if entry["group"] not in obliged]
    failed = [
        entry["id"]
        for entry in explained
        if not entry.get("obligation", {"met": True})["met"]
    ]
    return {
        "comparison": comparison,
        "changed_paths": paths,
        "unclaimed_paths": unclaimed,
        "fail_wide": causes,
        "requested": requested,
        "groups": explained,
        "ignored_reports": [entry["line"] for entry in ignored],
        "failed_obligations": failed,
        "valid": not failed,
    }


def describe(reason: dict) -> str:
    code = reason["code"]
    if code == "floor":
        return "floor: always runs"
    if code == "affected":
        return "affected by " + ", ".join(reason["paths"])
    if code == "fail-wide":
        return "failing wide: " + "; ".join(reason["causes"])
    if code == "requested":
        return "requested in the pull request"
    if code == "optional-unrequested":
        return "optional and not requested"
    if code == "not-affected":
        return "not affected" + (f" ({reason['note']})" if "note" in reason else "")
    if code == "verified-on-pull-request":
        return (
            "verified on the pull request (affected by "
            + ", ".join(reason["paths"])
            + ")"
        )
    raise ValueError(code)


def render(plan: dict) -> str:
    comparison = plan["comparison"]
    if comparison["kind"] == "pull_request":
        lines = [
            f"Validation plan for a pull request: {comparison['base']}...{comparison['head']}",
            f"  merge base {comparison.get('merge_base') or 'unknown'}, "
            f"head {comparison['head_commit'] or 'unknown'}",
        ]
    else:
        lines = [
            f"Validation plan for a push: {comparison['before']}..{comparison['after']}",
            f"  after {comparison['after_commit'] or 'unknown'}",
        ]
    paths = plan["changed_paths"]
    if paths is None:
        lines.append("Changed paths: unknown")
    else:
        lines.append(f"Changed paths ({len(paths)}):")
        lines.extend(f"  {path}" for path in paths)
    if plan["fail_wide"]:
        lines.append("Failing wide: every floor and affected group runs, because")
        lines.extend(f"  - {cause}" for cause in plan["fail_wide"])
    width = max(len(entry["id"]) for entry in plan["groups"])
    sections = (
        ("Selected, runs on GitHub:", lambda e: e["selected"] and not e["local"]),
        ("Selected, local obligations:", lambda e: e["selected"] and e["local"]),
        ("Omitted:", lambda e: not e["selected"]),
    )
    for title, belongs in sections:
        members = [entry for entry in plan["groups"] if belongs(entry)]
        if not members:
            continue
        lines.extend(["", title])
        for entry in members:
            text = "; ".join(describe(reason) for reason in entry["reasons"])
            lines.append(f"  {entry['id']:<{width}}  {text}")
            if not entry["selected"]:
                continue
            lines.extend(
                f"  {'':<{width}}  $ {shlex.join(command)}"
                for command in entry["commands"]
            )
            obligation = entry.get("obligation")
            if obligation and obligation["met"]:
                lines.append(f"  {'':<{width}}  met: passed at {obligation['commit']}")
            elif obligation:
                lines.extend(
                    f"  {'':<{width}}  FAILED: {problem}"
                    for problem in obligation["problems"]
                )
    if plan["ignored_reports"]:
        lines.extend(["", f"Ignored {REPORT_BLOCK} entries (no obligation):"])
        lines.extend(f"  {line}" for line in plan["ignored_reports"])
    lines.append("")
    if plan["valid"]:
        lines.append("Result: valid; every obligation is met.")
    else:
        lines.append(
            "Result: failed obligations: " + ", ".join(plan["failed_obligations"])
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Command line


def repository_root(path: Path) -> Path:
    result = git(path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise PlanError(f"{path} is not inside a Git repository")
    return Path(result.stdout.decode().strip())


def run(arguments: argparse.Namespace) -> int:
    catalog = arguments.catalog or CATALOG
    ranges = {
        "pull request": (arguments.base, arguments.head),
        "push": (arguments.before, arguments.after),
    }
    given = [name for name, ends in ranges.items() if any(ends)]
    if arguments.catalog_check:
        if given or arguments.request_file:
            raise PlanError("--catalog-check takes no range and no --request-file")
        groups, problems = read_catalog(catalog)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return EXIT_ERROR
        print(f"catalog {catalog} is valid: {len(groups)} groups")
        return EXIT_VALID
    if len(given) != 1 or not all(ranges[given[0]]):
        raise PlanError("give --base and --head, or --before and --after")
    for revision in ranges[given[0]]:
        if revision.startswith("-"):
            raise PlanError(f"revision {revision!r} must not start with '-'")
    if given[0] == "push" and arguments.request_file:
        raise PlanError(
            "a push has no pull request body; --request-file needs --base and --head"
        )

    groups = load_catalog(catalog)
    requested, reports = [], None
    if arguments.request_file:
        source = str(arguments.request_file)
        try:
            body = arguments.request_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise PlanError(f"{source}: cannot be read: {error}") from None
        requested = parse_request(body, source, {group["id"] for group in groups})
        reports = parse_reports(body, source)

    repo = repository_root(arguments.repo)
    if given[0] == "pull request":
        comparison, paths, causes = pull_request_range(
            repo, arguments.base, arguments.head
        )
    else:
        comparison, paths, causes = push_range(repo, arguments.before, arguments.after)
    plan = build_plan(repo, groups, comparison, paths, causes, requested, reports)
    if arguments.json:
        print(json.dumps(plan, indent=2))
    else:
        print(render(plan))
    return EXIT_VALID if plan["valid"] else EXIT_OBLIGATION_FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="plan.py",
        description="Explain which validation groups a change requires (docs/validation.md).",
    )
    parser.add_argument(
        "--catalog-check", action="store_true", help="validate the catalog and exit"
    )
    parser.add_argument("--base", help="pull request range: the base revision")
    parser.add_argument("--head", help="pull request range: the head revision")
    parser.add_argument("--before", help="push range: the revision before the push")
    parser.add_argument("--after", help="push range: the revision after the push")
    parser.add_argument(
        "--request-file",
        type=Path,
        help="a file holding the pull request body, for its requests and local-only reports",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help=f"catalog to read (default: {CATALOG.name} beside this file)",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="repository to plan for (default: .)",
    )
    parser.add_argument("--json", action="store_true", help="print the plan as JSON")
    try:
        return run(parser.parse_args(argv))
    except PlanError as error:
        print(f"plan.py: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
