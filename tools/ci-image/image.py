#!/usr/bin/env python3
"""The CI image: its recipe fingerprint, build context, descriptor and publication.

Every command works from one named revision's committed tree, so the working
tree, the checked-out revision and untracked files never affect it.

- ``fingerprint`` prints the recipe fingerprint of a revision: a digest over
  exactly the recipe inputs, with the descriptor excluded.
- ``check-descriptor`` checks that a descriptor records a revision's
  fingerprint.
- ``stage`` writes exactly the recipe inputs, with their committed bytes and
  modes, into an empty build context.
- ``resolve`` looks up the image for a revision's fingerprint. A validated
  existing image is a *hit*; a tag the registry confirms is absent is a
  *miss*; a lookup that fails is neither, and nothing is published.
- ``publish`` looks the tag up again and, only on a confirmed miss, builds,
  checks and pushes the image once. A published tag is never overwritten.
- ``check-image`` runs a described image and checks that it reports the
  descriptor's fingerprint and versions.

The registry and Docker are reached through a transport executable
(``--registry``), which ``registry.py`` implements:

- ``lookup REFERENCE:TAG`` prints ``{"digest": ..., "labels": {...}}``, or
  exits 3 when the registry confirms the tag is absent;
- ``build CONTEXT LOCAL FINGERPRINT`` builds and labels the image;
- ``inspect IMAGE`` runs the image and prints what it reports;
- ``push LOCAL REFERENCE:TAG`` pushes it.

Any other exit status is an error. Standard library only. See
``docs/validation.md``.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True

DESCRIPTOR_PATH = "tools/ci-image/descriptor.json"
LOCK_PATH = "requirements.lock"
# A trailing "/" names a directory and everything beneath it; anything else
# names exactly one file.
RECIPE_INPUTS = ("tools/ci-image/", LOCK_PATH, ".github/workflows/ci-image.yml")
FINGERPRINT_SCHEMA_VERSION = 1
DESCRIPTOR_SCHEMA_VERSION = 1
# The tree modes of regular files, and the permissions each is staged with.
FILE_MODES = {"100644": 0o644, "100755": 0o755}

PYTHON_SERIES = "3.13"
VERSIONED = ("python", "pytest", "ruff")
# The image's own record of itself, and the labels a lookup reads without
# pulling it. Both carry the fingerprint and the versions.
EMBEDDED_PATH = "/opt/moskophoros/image.json"
ENVIRONMENT_PYTHON = "/opt/moskophoros/venv/bin/python3"
LABEL_PREFIX = "org.moskophoros.ci-image."
RECORDED = ("recipe_fingerprint", *VERSIONED)

ABSENT = 3
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REFERENCE = re.compile(r"^[a-z0-9.-]+(?::[0-9]+)?/[a-z0-9._/-]+$")
VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)\s*(?:;\s*(.+))?$")

DESCRIPTOR_FIELDS = {
    "schema_version": int,
    "reference": str,
    "digest": str,
    "recipe_fingerprint": str,
    "python": str,
    "pytest": str,
    "ruff": str,
}

UPDATE_INSTRUCTION = (
    "run the ci-image workflow (.github/workflows/ci-image.yml) for this revision and commit "
    f"the descriptor it reports as {DESCRIPTOR_PATH}"
)


class ImageError(Exception):
    """A diagnostic reported instead of a result."""


class Mismatch(ImageError):
    """A descriptor that does not record the revision's fingerprint."""


def label(name: str) -> str:
    return LABEL_PREFIX + name.replace("_", "-")


# --------------------------------------------------------------------------
# Revisions and fingerprints


def git(root: str, *arguments: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", root, *arguments], capture_output=True, check=False
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise ImageError(f"git {' '.join(arguments)} failed: {detail or 'no output'}")
    return process.stdout


def commit(root: str, revision: str) -> str:
    return (
        git(root, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}")
        .decode()
        .strip()
    )


def is_recipe_input(path: str) -> bool:
    if path == DESCRIPTOR_PATH:
        return False
    return any(
        path.startswith(entry) if entry.endswith("/") else path == entry
        for entry in RECIPE_INPUTS
    )


def recipe_entries(root: str, revision: str) -> list[tuple[str, str, str, str]]:
    """Each recipe input of one commit's tree: path, mode, type and object ID."""
    entries = []
    for record in git(
        root, "ls-tree", "-r", "-z", "--full-tree", commit(root, revision)
    ).split(b"\0"):
        if not record:
            continue
        metadata, separator, path = record.decode("utf-8").partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise ImageError(
                f"cannot read the tree of {revision}: unexpected entry {record!r}"
            )
        if is_recipe_input(path):
            entries.append((path, *fields))
    return sorted(entries)


def fingerprint(root: str, revision: str) -> str:
    """The recipe fingerprint of one revision.

    Each input contributes its path, mode, type and content ID, so an edited,
    added, removed, renamed or newly executable input moves it, and two commits
    with identical inputs share it whatever else differs.
    """
    payload = {
        "fingerprint_schema_version": FINGERPRINT_SCHEMA_VERSION,
        "entries": [list(entry) for entry in recipe_entries(root, revision)],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def locked_versions(root: str, revision: str) -> dict[str, str]:
    """The pytest and ruff versions a revision's lock file pins."""
    text = git(root, "show", f"{commit(root, revision)}:{LOCK_PATH}").decode("utf-8")
    pins = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = PIN.match(stripped)
        if not match:
            raise ImageError(
                f"{LOCK_PATH} at {revision} has a line that is not NAME==VERSION: {stripped!r}"
            )
        pins[re.sub(r"[-_.]+", "-", match[1]).lower()] = match[2]
    missing = [name for name in ("pytest", "ruff") if name not in pins]
    if missing:
        raise ImageError(f"{LOCK_PATH} at {revision} pins no {' or '.join(missing)}")
    return {"pytest": pins["pytest"], "ruff": pins["ruff"]}


def stage(root: str, revision: str, output: str) -> list[str]:
    """Write exactly one revision's recipe inputs into an empty directory.

    Each input is written from its blob with the tree's bytes and executable
    bit. Nothing converts it on the way: no ``.gitattributes`` or local Git
    configuration applies, unlike ``git archive`` or a checkout. An input that
    is not a regular file, such as a symlink or a submodule, is refused.
    """
    entries = recipe_entries(root, revision)
    paths = [entry[0] for entry in entries]
    if not any(path == "tools/ci-image/Dockerfile" for path in paths):
        raise ImageError(f"{revision} has no tools/ci-image/Dockerfile to build")
    for path, mode, kind, _ in entries:
        if kind != "blob" or mode not in FILE_MODES:
            raise ImageError(
                f"{path} at {revision} is a {kind} with mode {mode}, not a regular "
                "file; only regular files can be staged exactly"
            )
        if any(part in ("", ".", "..", ".git") for part in path.split("/")):
            raise ImageError(f"{path} at {revision} is not a path that can be staged")
    if os.path.exists(output) and (not os.path.isdir(output) or os.listdir(output)):
        raise ImageError(
            f"{output} is not an empty directory; only recipe inputs may reach the build"
        )
    os.makedirs(output, exist_ok=True)
    for path, mode, _, object_id in entries:
        target = os.path.join(output, *path.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "xb") as handle:
            handle.write(git(root, "cat-file", "blob", object_id))
        os.chmod(target, FILE_MODES[mode])
    return paths


# --------------------------------------------------------------------------
# Descriptors


def validate_descriptor(document: object, source: str) -> dict:
    if not isinstance(document, dict):
        raise ImageError(f"{source} is not a JSON object")
    problems = []
    for name in sorted(set(document) - set(DESCRIPTOR_FIELDS)):
        problems.append(f"unknown field {name!r}")
    for name, kind in DESCRIPTOR_FIELDS.items():
        if name not in document:
            problems.append(f"missing field {name!r}")
        elif type(document[name]) is not kind:
            problems.append(f"{name!r} is not a {kind.__name__}")
    if not problems:
        checks = (
            (document["schema_version"] == DESCRIPTOR_SCHEMA_VERSION, "schema_version"),
            (REFERENCE.match(document["reference"]), "reference"),
            (DIGEST.match(document["digest"]), "digest"),
            (HEX64.match(document["recipe_fingerprint"]), "recipe_fingerprint"),
            (
                VERSION.match(document["python"]) and python_series(document["python"]),
                "python",
            ),
            (VERSION.match(document["pytest"]), "pytest"),
            (VERSION.match(document["ruff"]), "ruff"),
        )
        problems += [f"{name!r} is {document[name]!r}" for ok, name in checks if not ok]
    if problems:
        raise ImageError(f"{source} is not a valid descriptor: " + "; ".join(problems))
    return document


def python_series(version: str) -> bool:
    return version.split(".")[:2] == PYTHON_SERIES.split(".")


def descriptor(reference: str, digest: str, recorded: dict[str, str]) -> dict:
    document = {
        "schema_version": DESCRIPTOR_SCHEMA_VERSION,
        "reference": reference,
        "digest": digest,
        **{name: recorded[name] for name in RECORDED},
    }
    return validate_descriptor(document, "the returned descriptor")


def read_descriptor(root: str, revision: str, path: str | None) -> tuple[dict, str]:
    if path is None:
        source = f"{DESCRIPTOR_PATH} at {revision}"
        text = git(root, "show", f"{commit(root, revision)}:{DESCRIPTOR_PATH}").decode(
            "utf-8"
        )
    else:
        source = path
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            raise ImageError(f"cannot read {path}: {error}") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ImageError(f"{source} is not JSON: {error}") from error
    return validate_descriptor(document, source), source


def check_descriptor(root: str, revision: str, path: str | None) -> str:
    document, source = read_descriptor(root, revision, path)
    expected = fingerprint(root, revision)
    if document["recipe_fingerprint"] != expected:
        raise Mismatch(
            f"{source} records recipe fingerprint {document['recipe_fingerprint']}, but {revision} "
            f"has recipe fingerprint {expected}; {UPDATE_INSTRUCTION}"
        )
    return expected


# --------------------------------------------------------------------------
# The registry


def tag_for(image: str, recipe_fingerprint: str) -> str:
    return f"{image}:fp-{recipe_fingerprint}"


def call(registry: str, *arguments: str) -> str:
    """Make one transport request; its diagnostics and build log pass through to standard error."""
    try:
        process = subprocess.run(
            [registry, *arguments], stdout=subprocess.PIPE, check=False
        )
    except OSError as error:
        raise ImageError(
            f"cannot run the registry transport {registry}: {error}"
        ) from error
    if process.returncode == ABSENT and arguments[0] == "lookup":
        return ""
    if process.returncode != 0:
        raise ImageError(
            f"registry {arguments[0]} {arguments[1]} failed (exit {process.returncode}), as reported above; "
            "an error is never taken for an absent image"
        )
    return process.stdout.decode("utf-8", errors="replace")


def answer(output: str, description: str) -> dict:
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise ImageError(f"{description} did not answer with JSON: {error}") from error
    if not isinstance(document, dict):
        raise ImageError(f"{description} did not answer with a JSON object")
    return document


def lookup(registry: str, reference: str) -> dict | None:
    """The published image at a tag, or None when the registry confirms it is absent."""
    output = call(registry, "lookup", reference)
    return answer(output, f"the lookup of {reference}") if output else None


def expected_problems(
    values: dict, recipe_fingerprint: str, pins: dict[str, str], what: str
) -> list[str]:
    problems = []
    if values.get("recipe_fingerprint") != recipe_fingerprint:
        problems.append(
            f"{what} recipe fingerprint is {values.get('recipe_fingerprint')!r}, not {recipe_fingerprint}"
        )
    python = values.get("python")
    if (
        not isinstance(python, str)
        or not VERSION.match(python)
        or not python_series(python)
    ):
        problems.append(f"{what} Python is {python!r}, not a {PYTHON_SERIES} release")
    for name in ("pytest", "ruff"):
        if values.get(name) != pins[name]:
            problems.append(
                f"{what} {name} is {values.get(name)!r}, but the lock pins {pins[name]}"
            )
    return problems


def published(
    record: dict, reference: str, recipe_fingerprint: str, pins: dict[str, str]
) -> dict:
    """An existing image's digest and recorded values, refused unless they describe this recipe."""
    labels = record.get("labels")
    labels = labels if isinstance(labels, dict) else {}
    values = {name: labels.get(label(name)) for name in RECORDED}
    problems = expected_problems(values, recipe_fingerprint, pins, "its")
    digest = record.get("digest")
    if not isinstance(digest, str) or not DIGEST.match(digest):
        problems.append(f"its digest {digest!r} is not a sha256 digest")
    if problems:
        raise ImageError(
            f"{reference} exists but is not this recipe's image: "
            + "; ".join(problems)
            + "; a published tag "
            "is never overwritten, so delete that package version deliberately if it must be replaced"
        )
    return {"digest": digest, **values}


def exists_message(reference: str, digest: str) -> str:
    return f"the image for this recipe fingerprint already exists: {reference} is {digest}; nothing is published"


def resolve(root: str, revision: str, image: str, registry: str) -> dict:
    recipe_fingerprint = fingerprint(root, revision)
    pins = locked_versions(root, revision)
    reference = tag_for(image, recipe_fingerprint)
    record = lookup(registry, reference)
    if record is None:
        return {
            "status": "miss",
            "reference": reference,
            "recipe_fingerprint": recipe_fingerprint,
        }
    return {
        "status": "hit",
        "reference": reference,
        **published(record, reference, recipe_fingerprint, pins),
    }


def contents_problems(
    report: dict, recipe_fingerprint: str, pins: dict[str, str]
) -> tuple[dict, list[str]]:
    """What a running image reports, checked against the recipe it should hold."""
    embedded = report.get("embedded")
    embedded = embedded if isinstance(embedded, dict) else {}
    problems = expected_problems(embedded, recipe_fingerprint, pins, "the embedded")
    if report.get("python") != embedded.get("python"):
        problems.append(
            f"it runs Python {report.get('python')!r} but records {embedded.get('python')!r}"
        )
    for name in ("pytest", "ruff"):
        if report.get(name) != f"{name} {embedded.get(name)}":
            problems.append(
                f"`{name} --version` says {report.get(name)!r} but it records {embedded.get(name)!r}"
            )
    if report.get("python_path") != ENVIRONMENT_PYTHON:
        problems.append(
            f"python3 is {report.get('python_path')!r}, not {ENVIRONMENT_PYTHON}"
        )
    for tool in ("git", "bash"):
        if not report.get(tool):
            problems.append(f"it has no {tool}")
    if report.get("blender"):
        problems.append(f"it contains Blender at {report['blender']}")
    if report.get("moskophoros"):
        problems.append("it can import the moskophoros package")
    labels = report.get("labels")
    labels = labels if isinstance(labels, dict) else {}
    for name in RECORDED:
        if labels.get(label(name)) != embedded.get(name):
            problems.append(
                f"label {label(name)} is {labels.get(label(name))!r}, but it records {embedded.get(name)!r}"
            )
    return {name: embedded.get(name) for name in RECORDED}, problems


def publish(root: str, revision: str, image: str, registry: str, context: str) -> dict:
    recipe_fingerprint = fingerprint(root, revision)
    pins = locked_versions(root, revision)
    reference = tag_for(image, recipe_fingerprint)
    # The recheck. Publication is serialized per fingerprint, so an image
    # another run published while this one waited is found here, and nothing
    # is built or pushed.
    record = lookup(registry, reference)
    if record is not None:
        return {
            "status": "hit",
            "published": False,
            "reference": reference,
            **published(record, reference, recipe_fingerprint, pins),
        }

    stage(root, revision, context)
    local = f"moskophoros-ci-candidate:{recipe_fingerprint[:16]}"
    call(registry, "build", context, local, recipe_fingerprint)
    candidate, problems = contents_problems(
        answer(call(registry, "inspect", local), "the candidate inspection"),
        recipe_fingerprint,
        pins,
    )
    if problems:
        raise ImageError(
            "the candidate image is not the recipe's, so nothing is published: "
            + "; ".join(problems)
        )

    call(registry, "push", local, reference)
    record = lookup(registry, reference)
    if record is None:
        raise ImageError(f"{reference} is absent immediately after it was pushed")
    result = published(record, reference, recipe_fingerprint, pins)
    if any(result[name] != candidate[name] for name in RECORDED):
        raise ImageError(
            f"{reference} does not describe the checked candidate after publication"
        )
    return {"status": "published", "published": True, "reference": reference, **result}


def check_image(root: str, revision: str, path: str, registry: str) -> dict:
    """Run a described image and check it reports what the descriptor and the lock say."""
    document, source = read_descriptor(root, revision, path)
    pins = locked_versions(root, revision)
    reference = f"{document['reference']}@{document['digest']}"
    reported, problems = contents_problems(
        answer(call(registry, "inspect", reference), f"the inspection of {reference}"),
        document["recipe_fingerprint"],
        pins,
    )
    for name in RECORDED:
        if reported[name] != document[name]:
            problems.append(
                f"it records {name} {reported[name]!r}, but {source} says {document[name]!r}"
            )
    if problems:
        raise ImageError(f"{reference} does not match {source}: " + "; ".join(problems))
    return {"reference": reference, **reported}


# --------------------------------------------------------------------------
# The command line


def write_outputs(path: str | None, result: dict) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key in ("status", "published", "recipe_fingerprint", "digest"):
            if key in result:
                value = result[key]
                handle.write(
                    f"{key.replace('_', '-')}={str(value).lower() if isinstance(value, bool) else value}\n"
                )


def write_json(path: str, document: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="image.py", description="The CI image recipe and its publication."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def revision_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--revision", default="HEAD", help="the revision to read (default HEAD)"
        )
        sub.add_argument(
            "--repo", default=".", help="a directory in the repository (default .)"
        )

    def registry_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--image", required=True, help="the registry repository, without a tag"
        )
        sub.add_argument(
            "--registry", required=True, help="the registry transport executable"
        )
        sub.add_argument("--github-output", default=None)

    revision_options(
        commands.add_parser("fingerprint", help="print a revision's recipe fingerprint")
    )
    checked = commands.add_parser(
        "check-descriptor", help="check a descriptor records a revision's fingerprint"
    )
    revision_options(checked)
    checked.add_argument(
        "--descriptor",
        default=None,
        help=f"a descriptor file (default: {DESCRIPTOR_PATH} at the revision)",
    )
    staged = commands.add_parser("stage", help="extract a revision's recipe inputs")
    revision_options(staged)
    staged.add_argument("--output", required=True)
    resolved = commands.add_parser(
        "resolve", help="look up the image for a revision's fingerprint"
    )
    revision_options(resolved)
    registry_options(resolved)
    resolved.add_argument(
        "--require-hit", action="store_true", help="treat a miss as an error"
    )
    resolved.add_argument(
        "--descriptor-output", default=None, help="on a hit, write the descriptor here"
    )
    publishing = commands.add_parser(
        "publish", help="publish the image for a revision's fingerprint once"
    )
    revision_options(publishing)
    registry_options(publishing)
    publishing.add_argument(
        "--context",
        required=True,
        help="an empty directory to stage the build context in",
    )
    inspected = commands.add_parser(
        "check-image", help="check a described image against its descriptor"
    )
    revision_options(inspected)
    inspected.add_argument("--descriptor", required=True)
    inspected.add_argument("--registry", required=True)

    arguments = parser.parse_args(argv)
    root = os.path.abspath(arguments.repo)
    if arguments.command == "fingerprint":
        print(fingerprint(root, arguments.revision))
    elif arguments.command == "check-descriptor":
        value = check_descriptor(root, arguments.revision, arguments.descriptor)
        print(
            f"the descriptor records {arguments.revision}'s recipe fingerprint {value}"
        )
    elif arguments.command == "stage":
        for path in stage(root, arguments.revision, arguments.output):
            print(path)
    elif arguments.command == "resolve":
        result = resolve(root, arguments.revision, arguments.image, arguments.registry)
        if result["status"] == "hit":
            print(
                exists_message(result["reference"], result["digest"]), file=sys.stderr
            )
            if arguments.descriptor_output:
                write_json(
                    arguments.descriptor_output,
                    descriptor(arguments.image, result["digest"], result),
                )
        elif arguments.require_hit:
            raise ImageError(
                f"{result['reference']} is absent, but it was required to exist"
            )
        else:
            print(
                f"{result['reference']} is absent; it is published only by the publish job",
                file=sys.stderr,
            )
        write_outputs(arguments.github_output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
    elif arguments.command == "publish":
        result = publish(
            root,
            arguments.revision,
            arguments.image,
            arguments.registry,
            arguments.context,
        )
        if not result["published"]:
            print(
                exists_message(result["reference"], result["digest"]), file=sys.stderr
            )
        write_outputs(arguments.github_output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
    elif arguments.command == "check-image":
        print(
            json.dumps(
                check_image(
                    root, arguments.revision, arguments.descriptor, arguments.registry
                ),
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Mismatch as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)
    except ImageError as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(2)
