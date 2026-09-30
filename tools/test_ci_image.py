"""Test the CI image's fingerprint, descriptor check, staging and publish-once rule.

Each history is built in a temporary repository, and ``image.py`` runs as a
separate process exactly as the workflow runs it. Publication runs against a
fake registry transport that records every request it receives.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / "tools" / "ci-image" / "image.py"
REFERENCE = "ghcr.io/example/project-ci"
DIGEST = "sha256:" + "d" * 64

LOCK = """\
# A fixture lock.
colorama==0.4.6 ; sys_platform == 'win32'
    # via pytest
pytest==9.1.1
ruff==0.16.9
"""


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

    def write(self, relative: str, text: str) -> None:
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message: str = "change") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")


def run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    process = subprocess.run(
        [sys.executable, str(IMAGE), *args, "--repo", str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    if check:
        assert process.returncode == 0, process.stderr
    return process


def fingerprint(repo: Repo, revision: str = "HEAD") -> str:
    return run(repo.path, "fingerprint", "--revision", revision).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    repository = Repo(tmp_path / "repo")
    repository.write("tools/ci-image/Dockerfile", "FROM scratch\n")
    repository.write("tools/ci-image/stamp.py", "print('stamp')\n")
    repository.write("requirements.lock", LOCK)
    repository.write(".github/workflows/ci-image.yml", "name: ci-image\n")
    repository.write(".github/workflows/ci.yml", "name: CI\n")
    repository.write("README.md", "readme\n")
    repository.write("src/app.py", "print('app')\n")
    repository.commit("initial")
    return repository


def descriptor_for(value: str, **overrides) -> dict:
    document = {
        "schema_version": 1,
        "reference": REFERENCE,
        "digest": DIGEST,
        "recipe_fingerprint": value,
        "python": "3.13.9",
        "pytest": "9.1.1",
        "ruff": "0.16.9",
    }
    document.update(overrides)
    return document


# --------------------------------------------------------------------------
# The fingerprint


def test_fingerprint_is_a_sha256_hex_digest(repo):
    value = fingerprint(repo)
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda r: r.write("requirements.lock", LOCK.replace("9.1.1", "9.1.2")),
            id="lock-alone",
        ),
        pytest.param(
            lambda r: r.write("tools/ci-image/Dockerfile", "FROM scratch\nRUN true\n"),
            id="edit-dockerfile",
        ),
        pytest.param(
            lambda r: r.write("tools/ci-image/stamp.py", "print('other')\n"),
            id="edit-script",
        ),
        pytest.param(
            lambda r: r.write("tools/ci-image/extra.sh", "true\n"), id="add-recipe-file"
        ),
        pytest.param(
            lambda r: r.git("rm", "-q", "tools/ci-image/stamp.py"),
            id="delete-recipe-file",
        ),
        pytest.param(
            lambda r: r.git(
                "mv", "tools/ci-image/stamp.py", "tools/ci-image/stamp2.py"
            ),
            id="rename",
        ),
        pytest.param(
            lambda r: (r.path / "tools/ci-image/stamp.py").chmod(0o755),
            id="make-executable",
        ),
        pytest.param(
            lambda r: r.write(".github/workflows/ci-image.yml", "name: other\n"),
            id="edit-workflow",
        ),
    ],
)
def test_changing_a_recipe_input_changes_the_fingerprint(repo, change):
    before = fingerprint(repo)
    change(repo)
    repo.commit()
    assert fingerprint(repo) != before


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda r: r.write("tools/ci-image/descriptor.json", "{}\n"),
            id="add-descriptor",
        ),
        pytest.param(lambda r: r.write("README.md", "other\n"), id="readme"),
        pytest.param(lambda r: r.write("src/app.py", "print('other')\n"), id="source"),
        pytest.param(
            lambda r: r.write(".github/workflows/ci.yml", "name: other\n"),
            id="other-workflow",
        ),
        pytest.param(
            lambda r: r.write("tools/ci-imagex/Dockerfile", "FROM scratch\n"),
            id="lookalike-directory",
        ),
        pytest.param(
            lambda r: r.write("requirements.lock.bak", LOCK), id="lookalike-file"
        ),
    ],
)
def test_changing_anything_else_leaves_the_fingerprint(repo, change):
    before = fingerprint(repo)
    change(repo)
    repo.commit()
    assert fingerprint(repo) == before


def test_changing_the_descriptor_leaves_the_fingerprint(repo):
    repo.write("tools/ci-image/descriptor.json", "{}\n")
    repo.commit()
    before = fingerprint(repo)
    repo.write("tools/ci-image/descriptor.json", json.dumps(descriptor_for("a" * 64)))
    repo.commit()
    assert fingerprint(repo) == before


def test_uncommitted_and_untracked_changes_do_not_affect_the_fingerprint(repo):
    before = fingerprint(repo)
    repo.write("tools/ci-image/Dockerfile", "FROM scratch\nRUN edited\n")
    repo.write("tools/ci-image/untracked.sh", "true\n")
    repo.write("requirements.lock", "ruff==0.0.1\n")
    repo.git("add", "tools/ci-image/Dockerfile")
    assert fingerprint(repo) == before


def test_a_named_revision_is_fingerprinted_whatever_is_checked_out(repo):
    first = repo.git("rev-parse", "HEAD")
    before = fingerprint(repo)
    repo.write("tools/ci-image/Dockerfile", "FROM scratch\nRUN later\n")
    repo.commit()
    after = fingerprint(repo)
    assert fingerprint(repo, first) == before
    repo.git("checkout", "-q", first)
    assert fingerprint(repo, "master") == after


def test_the_same_revision_gives_the_same_fingerprint_in_another_clone(repo, tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(repo.path), str(clone)], check=True)
    assert run(clone, "fingerprint").stdout.strip() == fingerprint(repo)


def test_an_unknown_revision_is_an_error(repo):
    process = run(
        repo.path, "fingerprint", "--revision", "no-such-revision", check=False
    )
    assert process.returncode == 2
    assert "no-such-revision" in process.stderr


# --------------------------------------------------------------------------
# The descriptor check


def test_the_descriptor_check_passes_on_a_match(repo):
    value = fingerprint(repo)
    repo.write("tools/ci-image/descriptor.json", json.dumps(descriptor_for(value)))
    repo.commit()
    process = run(repo.path, "check-descriptor", "--revision", "HEAD")
    assert value in process.stdout


def test_the_descriptor_check_fails_on_a_mismatch_naming_both(repo):
    value = fingerprint(repo)
    repo.write("tools/ci-image/descriptor.json", json.dumps(descriptor_for(value)))
    repo.commit()
    repo.write("requirements.lock", LOCK.replace("0.16.9", "0.16.10"))
    repo.commit()
    current = fingerprint(repo)
    process = run(repo.path, "check-descriptor", check=False)
    assert process.returncode == 1
    assert value in process.stderr and current in process.stderr
    assert "tools/ci-image/descriptor.json" in process.stderr


def test_the_descriptor_check_reads_a_named_file(repo, tmp_path):
    file = tmp_path / "descriptor.json"
    file.write_text(json.dumps(descriptor_for("b" * 64)))
    process = run(repo.path, "check-descriptor", "--descriptor", str(file), check=False)
    assert process.returncode == 1
    assert "b" * 64 in process.stderr and fingerprint(repo) in process.stderr
    file.write_text(json.dumps(descriptor_for(fingerprint(repo))))
    run(repo.path, "check-descriptor", "--descriptor", str(file))


@pytest.mark.parametrize(
    "overrides",
    [
        {"digest": "sha256:short"},
        {"python": "3.12.1"},
        {"schema_version": 2},
        {"extra": "field"},
        {"ruff": 16},
    ],
)
def test_a_malformed_descriptor_is_an_error(repo, tmp_path, overrides):
    file = tmp_path / "descriptor.json"
    file.write_text(json.dumps(descriptor_for(fingerprint(repo), **overrides)))
    process = run(repo.path, "check-descriptor", "--descriptor", str(file), check=False)
    assert process.returncode == 2
    assert "not a valid descriptor" in process.stderr


def test_a_missing_descriptor_is_an_error(repo):
    process = run(repo.path, "check-descriptor", check=False)
    assert process.returncode == 2


# --------------------------------------------------------------------------
# Staging


def test_staging_extracts_exactly_the_recipe_inputs(repo, tmp_path):
    repo.write("tools/ci-image/descriptor.json", "{}\n")
    repo.commit()
    repo.write("tools/ci-image/untracked.sh", "true\n")
    output = tmp_path / "context"
    run(repo.path, "stage", "--output", str(output))
    staged = sorted(
        str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()
    )
    assert staged == [
        ".github/workflows/ci-image.yml",
        "requirements.lock",
        "tools/ci-image/Dockerfile",
        "tools/ci-image/stamp.py",
    ]


def test_staging_refuses_a_directory_that_is_not_empty(repo, tmp_path):
    output = tmp_path / "context"
    output.mkdir()
    (output / "stray").write_text("x")
    process = run(repo.path, "stage", "--output", str(output), check=False)
    assert process.returncode == 2
    assert "not an empty directory" in process.stderr


# --------------------------------------------------------------------------
# Publishing once, against a fake registry transport

FAKE = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, sys
    from pathlib import Path

    state_path = Path(__file__).with_name("state.json")
    state = json.loads(state_path.read_text())
    command, *arguments = sys.argv[1:]
    state["calls"].append([command, *arguments])

    def save():
        state_path.write_text(json.dumps(state))

    def labelled(values):
        return {"org.moskophoros.ci-image." + k.replace("_", "-"): v for k, v in values.items()}

    if command == "lookup":
        if state["lookup_error"]:
            save()
            print("error: the registry answered 401", file=sys.stderr)
            sys.exit(2)
        tag = arguments[0]
        if state["appear_on_lookup"]:
            state["tags"][tag] = state["appear_on_lookup"]
            state["appear_on_lookup"] = None
        save()
        if tag not in state["tags"]:
            sys.exit(3)
        record = state["tags"][tag]
        print(json.dumps({"digest": record["digest"], "labels": labelled(record["values"])}))
    elif command == "build":
        context, local, fingerprint = arguments
        values = {"recipe_fingerprint": fingerprint, **state["built"]}
        state["images"][local] = values
        save()
        print(json.dumps(values))
    elif command == "inspect":
        reference = arguments[0]
        values = state["images"].get(reference) or next(
            r["values"] for t, r in state["tags"].items() if reference == t.rsplit(":", 1)[0] + "@" + r["digest"]
        )
        save()
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
            "labels": labelled(values),
        }))
    elif command == "push":
        local, reference = arguments
        state["tags"][reference] = {"digest": state["push_digest"], "values": state["images"][local]}
        save()
    else:
        sys.exit(2)
    """
)


class Registry:
    def __init__(self, directory: Path):
        directory.mkdir()
        self.executable = directory / "registry.py"
        self.executable.write_text(FAKE)
        self.executable.chmod(0o755)
        self.state_path = directory / "state.json"
        self.save(
            {
                "calls": [],
                "tags": {},
                "images": {},
                "lookup_error": False,
                "appear_on_lookup": None,
                "built": {"python": "3.13.9", "pytest": "9.1.1", "ruff": "0.16.9"},
                "push_digest": DIGEST,
            }
        )

    def state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def save(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state))

    def update(self, **values) -> None:
        state = self.state()
        state.update(values)
        self.save(state)

    def commands(self) -> list[str]:
        return [call[0] for call in self.state()["calls"]]


@pytest.fixture
def registry(tmp_path: Path) -> Registry:
    return Registry(tmp_path / "registry")


def published(value: str, digest: str = DIGEST, **overrides) -> dict:
    values = {
        "recipe_fingerprint": value,
        "python": "3.13.9",
        "pytest": "9.1.1",
        "ruff": "0.16.9",
    }
    values.update(overrides)
    return {f"{REFERENCE}:fp-{value}": {"digest": digest, "values": values}}


def publish(repo: Repo, registry: Registry, tmp_path: Path, check: bool = True):
    return run(
        repo.path,
        "publish",
        "--image",
        REFERENCE,
        "--registry",
        str(registry.executable),
        "--context",
        str(tmp_path / "context"),
        check=check,
    )


def resolve(repo: Repo, registry: Registry, *extra: str, check: bool = True):
    return run(
        repo.path,
        "resolve",
        "--image",
        REFERENCE,
        "--registry",
        str(registry.executable),
        *extra,
        check=check,
    )


def test_a_miss_builds_checks_and_pushes_once(repo, registry, tmp_path):
    process = publish(repo, registry, tmp_path)
    result = json.loads(process.stdout)
    assert result["status"] == "published" and result["published"] is True
    assert result["digest"] == DIGEST
    assert registry.commands() == ["lookup", "build", "inspect", "push", "lookup"]
    push = registry.state()["calls"][3]
    assert push[2] == f"{REFERENCE}:fp-{fingerprint(repo)}"


def test_an_existing_image_is_returned_and_never_rebuilt_or_overwritten(
    repo, registry, tmp_path
):
    value = fingerprint(repo)
    existing = "sha256:" + "e" * 64
    registry.update(tags=published(value, existing))
    process = publish(repo, registry, tmp_path)
    result = json.loads(process.stdout)
    assert result["status"] == "hit" and result["published"] is False
    assert result["digest"] == existing
    assert registry.commands() == ["lookup"]
    assert "already exists" in process.stderr
    assert not (tmp_path / "context").exists()


def test_an_image_another_run_published_meanwhile_is_returned(repo, registry, tmp_path):
    # `resolve` saw a miss; by the time `publish` holds the concurrency group,
    # another run has published the same fingerprint.
    value = fingerprint(repo)
    assert json.loads(resolve(repo, registry).stdout)["status"] == "miss"
    concurrent = "sha256:" + "c" * 64
    registry.update(
        appear_on_lookup=published(value, concurrent)[f"{REFERENCE}:fp-{value}"]
    )
    result = json.loads(publish(repo, registry, tmp_path).stdout)
    assert result["published"] is False and result["digest"] == concurrent
    assert "build" not in registry.commands() and "push" not in registry.commands()


def test_a_lookup_error_is_not_a_miss(repo, registry, tmp_path):
    registry.update(lookup_error=True)
    process = publish(repo, registry, tmp_path, check=False)
    assert process.returncode == 2
    assert "never taken for an absent image" in process.stderr
    assert registry.commands() == ["lookup"]
    assert resolve(repo, registry, check=False).returncode == 2


def test_an_existing_tag_that_is_not_this_recipe_is_refused_not_overwritten(
    repo, registry, tmp_path
):
    value = fingerprint(repo)
    registry.update(tags=published(value, ruff="0.1.0"))
    process = publish(repo, registry, tmp_path, check=False)
    assert process.returncode == 2
    assert "never overwritten" in process.stderr
    assert registry.commands() == ["lookup"]


def test_a_candidate_that_is_not_the_recipe_is_not_pushed(repo, registry, tmp_path):
    registry.update(built={"python": "3.12.1", "pytest": "9.1.1", "ruff": "0.16.9"})
    process = publish(repo, registry, tmp_path, check=False)
    assert process.returncode == 2
    assert "nothing is published" in process.stderr
    assert "push" not in registry.commands()


def test_resolve_writes_the_descriptor_from_the_published_image(
    repo, registry, tmp_path
):
    value = fingerprint(repo)
    registry.update(tags=published(value))
    output = tmp_path / "descriptor.json"
    process = resolve(
        repo, registry, "--require-hit", "--descriptor-output", str(output)
    )
    assert "already exists" in process.stderr
    assert json.loads(output.read_text()) == descriptor_for(value)
    run(repo.path, "check-descriptor", "--descriptor", str(output))


def test_resolve_requiring_a_hit_fails_on_a_miss(repo, registry):
    process = resolve(repo, registry, "--require-hit", check=False)
    assert process.returncode == 2
    assert "absent" in process.stderr


def test_check_image_compares_the_image_with_its_descriptor(repo, registry, tmp_path):
    value = fingerprint(repo)
    registry.update(tags=published(value))
    file = tmp_path / "descriptor.json"
    file.write_text(json.dumps(descriptor_for(value)))
    arguments = [
        "check-image",
        "--descriptor",
        str(file),
        "--registry",
        str(registry.executable),
    ]
    run(repo.path, *arguments)
    file.write_text(json.dumps(descriptor_for(value, python="3.13.1")))
    process = run(repo.path, *arguments, check=False)
    assert process.returncode == 2
    assert "3.13.1" in process.stderr


def test_the_repository_recipe_stages_and_fingerprints(tmp_path):
    output = tmp_path / "context"
    run(ROOT, "stage", "--output", str(output))
    assert (output / "tools/ci-image/Dockerfile").is_file()
    assert (output / "requirements.lock").is_file()
    assert not (output / "tools/ci-image/descriptor.json").exists()
