#!/usr/bin/env python3
"""Record what the CI image contains, inside the image, while it is built.

Runs once, from the Dockerfile, under the image's own environment. It refuses
an environment that holds anything other than the locked distributions at
their pinned versions, then writes ``image.json``: the recipe fingerprint the
image was built from and the Python, pytest and ruff versions it contains.

Usage: ``stamp.py FINGERPRINT LOCK OUTPUT``. Standard library only.
"""

import importlib.metadata
import json
import platform
import re
import sys

HEX64 = re.compile(r"^[0-9a-f]{64}$")
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)\s*(?:;\s*(.+))?$")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked(path: str) -> dict[str, tuple[str, bool]]:
    """Each locked distribution's version, and whether an environment marker limits it."""
    pins = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            match = PIN.match(text)
            if not match:
                sys.exit(
                    f"stamp: {path} has a line that is not NAME==VERSION: {text!r}"
                )
            pins[normalized(match[1])] = (match[2], match[3] is not None)
    return pins


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.exit("usage: stamp.py FINGERPRINT LOCK OUTPUT")
    fingerprint, lock, output = argv
    if not HEX64.match(fingerprint):
        sys.exit(f"stamp: {fingerprint!r} is not a recipe fingerprint")
    pins = locked(lock)
    installed = {
        normalized(distribution.metadata["Name"]): distribution.version
        for distribution in importlib.metadata.distributions()
    }
    problems = []
    for name, version in sorted(installed.items()):
        if name not in pins:
            problems.append(f"{name} {version} is installed but not locked")
        elif pins[name][0] != version:
            problems.append(f"{name} is {version}, but the lock pins {pins[name][0]}")
    for name, (version, conditional) in sorted(pins.items()):
        if name not in installed and not conditional:
            problems.append(f"{name}=={version} is locked but not installed")
    if problems:
        sys.exit("stamp: the environment is not the lock's: " + "; ".join(problems))

    document = {
        "recipe_fingerprint": fingerprint,
        "python": platform.python_version(),
        "pytest": installed["pytest"],
        "ruff": installed["ruff"],
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(document, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
