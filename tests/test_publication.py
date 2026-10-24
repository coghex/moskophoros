"""The output publisher (export design P-9): the directory form's filesystem
checks, nested publication with the metadata file last, and the rollback of
both forms. It works on temporary trees, synthetic plans and arbitrary bytes;
no image or Blender is involved. Faults are injected at explicit calls, and
an interruption is a real Ctrl-C delivered at an exact point, never a sleep."""

import errno
import json
import os
import signal
import stat
from pathlib import Path

import pytest

from moskophoros import outputs, publication
from moskophoros.publication import Interrupted, OutputError
from moskophoros.usage import UsageError

PATHS = (
    "sheet.png",
    "frames/walk/south/0.png",
    "frames/walk/south/1.png",
    "atlas/walk.png",
    "previews/walk.gif",
)
MANIFEST = "manifest.json"
EXIT_USAGE, EXIT_OUTPUT = 2, 6


def plan_of(paths=PATHS, manifest=MANIFEST):
    return outputs.OutputPlan(
        tuple(outputs.Output(outputs.FRAME, outputs.COLOR, p) for p in paths),
        outputs.Output(outputs.MANIFEST, None, manifest),
    )


def body(path, tag="new"):
    return f"{tag}: {path}".encode()


def manifest_bytes(subject="hero", tag="new"):
    return json.dumps({"subject": subject, "tag": tag}).encode()


def check(root, *, paths=PATHS, subject="hero", **kwargs):
    return publication.check_directory(root, plan_of(paths), subject=subject, **kwargs)


def publish(target, *, paths=PATHS, tag="new", manifest=None):
    manifest = manifest_bytes(tag=tag) if manifest is None else manifest
    publication.publish_directory(
        target, [(path, body(path, tag)) for path in paths], manifest
    )


def export(root, paths=PATHS, **kwargs):
    publish(check(root, paths=paths, **kwargs), paths=paths)


def tree(top):
    """Everything under `top`, without following links: a directory is
    `None`, a link its target, a file its bytes."""
    found = {}
    top = Path(top)
    if not os.path.lexists(top):
        return found
    for directory, names, files in os.walk(top):
        for name in [*names, *files]:
            path = Path(directory) / name
            relative = str(path.relative_to(top))
            if path.is_symlink():
                found[relative] = ("link", os.readlink(path))
            elif path.is_dir():
                found[relative] = None
            elif not stat.S_ISREG(path.lstat().st_mode):
                found[relative] = ("special", stat.S_IFMT(path.lstat().st_mode))
            else:
                found[relative] = path.read_bytes()
    return found


def earlier_tree(root, paths=PATHS, *, manifest=True):
    """An output directory from an earlier run, and an unrelated note."""
    for path in paths:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body(path, "earlier"))
    if manifest:
        (root / MANIFEST).write_bytes(manifest_bytes(tag="earlier"))
    (root / "notes.txt").write_text("not an output")
    return tree(root)


@pytest.fixture
def parent(tmp_path):
    (tmp_path / "parent").mkdir()
    return tmp_path / "parent"


@pytest.fixture
def root(parent):
    return parent / "out"


# Faults and interruptions at explicit calls


class Calls:
    """Count the calls of `os.<name>` (all of them, or those `where` accepts)
    and, at the `at`-th, raise `error` before the call or deliver a Ctrl-C
    after it."""

    def __init__(
        self, monkeypatch, name, *, at=None, error=None, after=None, where=None
    ):
        self.calls = []
        self.at, self.error, self.after = at, error, after
        real = getattr(os, name)

        def wrapper(*args, **kwargs):
            counted = where is None or where(*args)
            number = len(self.calls)
            if counted:
                self.calls.append(args)
                if self.error is not None and number == self.at:
                    raise self.error
            result = real(*args, **kwargs)
            if counted and self.after is not None and number == self.after:
                signal.raise_signal(signal.SIGINT)
            return result

        monkeypatch.setattr(os, name, wrapper)


def total_calls(tmp_path, name, build, run):
    """How many `os.<name>` calls a clean `run` of the tree `build` makes,
    not counting the building."""
    with pytest.MonkeyPatch.context() as patch:
        home = tmp_path / f"count-{name}"
        home.mkdir()
        root = build(home)
        counter = Calls(patch, name)
        run(root)
        return len(counter.calls)


def new_root_scene(base):
    (base / "parent").mkdir()
    return base / "parent" / "out"


def existing_scene(base):
    root = new_root_scene(base)
    root.mkdir()
    earlier_tree(root)
    return root


def run_export(root):
    export(root)


# Creating and replacing


def test_a_new_root_under_an_existing_parent_gets_nested_outputs(root):
    target = check(root)
    assert not root.exists()  # the check creates nothing
    publish(target)
    assert tree(root) == {
        **{
            part: None
            for part in (
                "frames",
                "frames/walk",
                "frames/walk/south",
                "atlas",
                "previews",
            )
        },
        **{path: body(path) for path in PATHS},
        MANIFEST: manifest_bytes(),
    }


def test_an_existing_root_is_used_and_its_other_files_stay(root):
    root.mkdir()
    (root / "notes.txt").write_text("keep me")
    export(root)
    assert (root / "notes.txt").read_text() == "keep me"
    assert (root / "frames/walk/south/1.png").read_bytes() == body(
        "frames/walk/south/1.png"
    )


def test_missing_ancestors_above_the_root_are_not_created(parent):
    root = parent / "a" / "b" / "out"
    with pytest.raises(UsageError, match="its parent"):
        check(root)
    assert tree(parent) == {}


@pytest.mark.parametrize("kind", ["file", "link-to-file", "dangling-link"])
def test_a_root_that_is_not_a_directory_is_a_usage_error(parent, root, kind):
    external = parent.parent / "external"
    if kind == "file":
        root.write_bytes(b"a file")
    elif kind == "link-to-file":
        external.write_bytes(b"a file")
        root.symlink_to(external)
    else:
        root.symlink_to(parent.parent / "nowhere")
    before = tree(parent)
    with pytest.raises(UsageError, match=r"the output directory .*(not a directory)"):
        check(root)
    assert tree(parent) == before
    assert not (parent.parent / "nowhere").exists()


def test_a_root_whose_parent_is_a_file_is_a_usage_error(parent):
    (parent / "file").write_bytes(b"x")
    with pytest.raises(UsageError, match="its parent"):
        check(parent / "file" / "out")


def test_a_root_that_is_a_link_to_a_directory_is_resolved_once(parent, root):
    real = parent / "real"
    real.mkdir()
    root.symlink_to(real)
    target = check(root)
    assert target.root == real.resolve()
    publish(target)
    assert (real / "sheet.png").read_bytes() == body("sheet.png")
    assert root.is_symlink()


def test_links_above_the_resolved_root_are_allowed(tmp_path):
    real = tmp_path / "real"
    (real / "deep").mkdir(parents=True)
    (tmp_path / "alias").symlink_to(real)
    export(tmp_path / "alias" / "deep" / "out")
    assert (real / "deep" / "out" / MANIFEST).is_file()


def test_the_planned_paths_must_be_the_published_ones(root):
    target = check(root)
    with pytest.raises(ValueError, match="planned paths"):
        publication.publish_directory(
            target, [(path, b"x") for path in PATHS[:-1]], b"{}"
        )
    assert not root.exists()


# Preflight refusals come before any capture or mutation


def capture_after_check(root, **kwargs):
    """The command's order: check, capture, publish."""
    captured = []
    target = check(root, **kwargs)
    captured.append("captured")
    return captured, target


@pytest.mark.parametrize(
    ("setup_tree", "reason"),
    [
        (lambda r: (r / "atlas" / "walk.png").mkdir(parents=True), "is a directory"),
        (lambda r: (r / "sheet.png").mkdir(), "is a directory"),
        (lambda r: os.mkfifo(r / "sheet.png"), "is not a regular file"),
        (lambda r: (r / "frames").write_bytes(b"x"), "is not a directory"),
        (
            lambda r: (
                (r / "frames" / "walk").mkdir(parents=True),
                (r / "frames" / "walk" / "south").write_bytes(b"x"),
            ),
            "is not a directory",
        ),
        (lambda r: (r / MANIFEST).mkdir(), "is a directory"),
        (lambda r: os.mkfifo(r / MANIFEST), "is not a regular file"),
    ],
)
def test_bad_existing_targets_and_components_are_refused_before_capture(
    root, setup_tree, reason
):
    root.mkdir()
    setup_tree(root)
    before = tree(root)
    with pytest.raises(UsageError, match=reason) as raised:
        capture_after_check(root)
    assert raised.value.exit_code == EXIT_USAGE
    assert tree(root) == before


@pytest.mark.parametrize(
    "setup_link",
    [
        lambda r, outside: (r / "sheet.png").symlink_to(outside / "file"),
        lambda r, outside: (r / "sheet.png").symlink_to(outside / "missing"),
        lambda r, outside: (r / "frames").symlink_to(outside),
        lambda r, outside: (r / "previews").symlink_to(outside),
        lambda r, outside: (r / MANIFEST).symlink_to(outside / "file"),
        lambda r, outside: (r / MANIFEST).symlink_to(outside / "missing"),
        lambda r, outside: (r / "atlas").symlink_to(r),
    ],
    ids=[
        "image",
        "dangling-image",
        "directory",
        "previews",
        "metadata",
        "dangling-metadata",
        "link-inside-root",
    ],
)
def test_a_link_at_or_below_the_root_is_refused_before_capture(root, setup_link):
    outside = root.parent / "outside"
    outside.mkdir()
    (outside / "file").write_bytes(b"outside")
    root.mkdir()
    setup_link(root, outside)
    before, outside_before = tree(root), tree(outside)
    with pytest.raises(UsageError, match="is a symbolic link") as raised:
        capture_after_check(root)
    assert raised.value.exit_code == EXIT_USAGE
    assert (tree(root), tree(outside)) == (before, outside_before)


# The recheck at publication


def swap_for_link(root, name, outside):
    target = root / name
    if target.is_dir() and not target.is_symlink():
        target.rmdir()
    elif os.path.lexists(target):
        target.unlink()
    target.symlink_to(outside)


@pytest.mark.parametrize("name", ["frames", "previews", "sheet.png", MANIFEST])
def test_a_component_that_becomes_a_link_is_refused_at_publication(root, name):
    outside = root.parent / "outside"
    outside.mkdir()
    (outside / "file").write_bytes(b"outside")
    root.mkdir()
    for directory in ("frames", "previews"):
        (root / directory).mkdir()
    target = check(root)
    swap_for_link(root, name, outside / "file" if "." in name else outside)
    before, outside_before = tree(root), tree(outside)
    with pytest.raises(OutputError, match="changed after it was checked") as raised:
        publish(target)
    assert raised.value.exit_code == EXIT_OUTPUT
    assert (tree(root), tree(outside)) == (before, outside_before)


def test_a_component_that_becomes_a_file_is_refused_at_publication(root):
    root.mkdir()
    target = check(root)
    (root / "atlas").write_bytes(b"in the way")
    before = tree(root)
    with pytest.raises(OutputError, match="not a directory"):
        publish(target)
    assert tree(root) == before


def test_a_root_that_becomes_a_link_is_refused_at_publication(parent, root):
    root.mkdir()
    target = check(root)
    root.rmdir()
    elsewhere = parent / "elsewhere"
    elsewhere.mkdir()
    root.symlink_to(elsewhere)
    with pytest.raises(OutputError, match="no longer resolves"):
        publish(target)
    assert tree(elsewhere) == {}


def test_a_link_that_appears_after_staging_is_refused_and_nothing_is_followed(
    root, monkeypatch
):
    outside = root.parent / "outside"
    outside.mkdir()
    root.mkdir()
    (root / "atlas").mkdir()
    target = check(root)
    real_open = open
    opened = []

    def staging_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        opened.append(Path(path).name)
        if len(opened) == len(PATHS) + 1:  # the manifest, the last staged
            (root / "atlas").rename(root / "atlas-moved")
            (root / "atlas").symlink_to(outside)
        return handle

    monkeypatch.setattr(publication, "open", staging_open, raising=False)
    with pytest.raises(OutputError, match="changed after it was checked"):
        publish(target)
    assert tree(outside) == {}


# Ownership: one subject per directory root


def test_no_manifest_means_no_subject_to_compare(root):
    root.mkdir()
    export(root)


def test_a_manifest_of_the_same_subject_is_replaced_whatever_the_model(root):
    root.mkdir()
    (root / MANIFEST).write_text(
        json.dumps({"schema": "moskophoros.sheet/9", "subject": "hero", "model": "00"})
    )
    export(root)
    assert json.loads((root / MANIFEST).read_text())["tag"] == "new"


def test_a_manifest_of_another_subject_is_a_usage_error_before_capture(root):
    root.mkdir()
    (root / MANIFEST).write_text(json.dumps({"subject": "villain"}))
    before = tree(root)
    with pytest.raises(UsageError, match="belongs to the subject 'villain'") as raised:
        capture_after_check(root)
    assert raised.value.exit_code == EXIT_USAGE
    assert str(root / MANIFEST) in str(raised.value)
    assert tree(root) == before


def test_the_subject_is_the_raw_stem_not_the_cleaned_name(root):
    root.mkdir()
    (root / MANIFEST).write_text(json.dumps({"subject": "a b"}))
    check(root, subject="a b")
    with pytest.raises(UsageError):
        check(root, subject="a_b")


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"{not json", "not valid JSON"),
        (b"\xff\xfe", "not valid JSON"),
        (b"", "not valid JSON"),
        (b"[1, 2]", "has no subject"),
        (b'{"schema": "x"}', "has no subject"),
        (b'{"subject": 7}', "not a string"),
        (b'{"subject": null}', "not a string"),
    ],
)
def test_an_unusable_manifest_is_a_usage_error_naming_the_file(root, content, reason):
    root.mkdir()
    (root / MANIFEST).write_bytes(content)
    with pytest.raises(UsageError, match=reason) as raised:
        check(root)
    assert raised.value.exit_code == EXIT_USAGE
    assert str(root / MANIFEST) in str(raised.value)


@pytest.mark.parametrize("failure", ["open", "read"])
def test_a_manifest_read_failure_is_an_output_error_not_a_usage_error(
    root, monkeypatch, failure
):
    root.mkdir()
    (root / MANIFEST).write_text(json.dumps({"subject": "hero"}))
    denied = OSError(errno.EACCES, "Permission denied")
    if failure == "open":
        Calls(
            monkeypatch,
            "open",
            at=0,
            error=denied,
            where=lambda path, *rest: Path(path) == root / MANIFEST,
        )
    else:
        monkeypatch.setattr(
            os, "fdopen", lambda *args, **kwargs: (_ for _ in ()).throw(denied)
        )
    with pytest.raises(OutputError, match="cannot read") as raised:
        check(root)
    assert raised.value.exit_code == EXIT_OUTPUT


def test_an_unreadable_manifest_file_is_an_output_error(root):
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    root.mkdir()
    manifest = root / MANIFEST
    manifest.write_text(json.dumps({"subject": "hero"}))
    manifest.chmod(0)
    try:
        with pytest.raises(OutputError, match="Permission denied"):
            check(root)
    finally:
        manifest.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_the_manifest_is_never_opened_when_it_is_not_a_regular_file(root, monkeypatch):
    root.mkdir()
    os.mkfifo(root / MANIFEST)
    opened = Calls(monkeypatch, "open")
    with pytest.raises(UsageError, match="is not a regular file"):
        check(root)
    assert opened.calls == []


def test_a_race_to_a_fifo_manifest_is_not_blocked_on_or_followed(root):
    # The check proper refuses a FIFO; the reader itself must never block on
    # one or take it for a document.
    root.mkdir()
    os.mkfifo(root / MANIFEST)
    with pytest.raises(UsageError, match="is not a regular file"):
        publication._read_regular(root / MANIFEST)


def test_the_reader_does_not_follow_a_link(root):
    root.mkdir()
    outside = root.parent / "outside.json"
    outside.write_text(json.dumps({"subject": "hero"}))
    (root / MANIFEST).symlink_to(outside)
    with pytest.raises(OutputError):
        publication._read_regular(root / MANIFEST)


# Overlap with inputs


@pytest.mark.parametrize("kind", ["model", "config", "palette", "library"])
def test_an_output_that_is_an_input_is_refused_before_capture(root, parent, kind):
    root.mkdir()
    inputs = {}
    for name in ("model", "config", "palette", "library"):
        path = parent / f"{name}.bin"
        path.write_bytes(name.encode())
        inputs[name] = path
    # The input sits at a planned output path, inside the root.
    (root / "atlas").mkdir()
    shared = root / "atlas" / "walk.png"
    shared.write_bytes(b"input")
    os.replace(shared, inputs[kind])
    os.link(inputs[kind], shared)
    before = tree(root)
    with pytest.raises(UsageError, match="is also an input") as raised:
        capture_after_check(root, inputs=list(inputs.values()))
    assert raised.value.exit_code == EXIT_USAGE
    assert tree(root) == before


def test_an_input_that_merely_lives_in_the_root_is_not_an_overlap(root):
    root.mkdir()
    model = root / "model.glb"
    model.write_bytes(b"glb")
    export(root, inputs=[model])
    assert model.read_bytes() == b"glb"


def test_the_reuse_document_may_be_replaced_in_place(root):
    root.mkdir()
    (root / MANIFEST).write_bytes(manifest_bytes(tag="earlier"))
    manifest = root / MANIFEST
    with open(manifest, "rb") as handle:  # read completely, then closed
        handle.read()
    export(root, inputs=[manifest], reuse=manifest)
    assert json.loads(manifest.read_text())["tag"] == "new"


def test_the_reuse_document_is_restored_when_publication_fails(root, monkeypatch):
    root.mkdir()
    earlier = earlier_tree(root)
    manifest = root / MANIFEST
    target = check(root, inputs=[manifest], reuse=manifest)
    # Fail the manifest's own rename into place, the last step.
    real = os.replace

    def replace(source, dest):
        if Path(dest) == manifest and ".manifest.json.moskophoros-new" in str(source):
            raise OSError(errno.EBUSY, "Device or resource busy")
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(OutputError, match="earlier outputs are kept"):
        publish(target)
    assert tree(root) == earlier


def test_only_the_reuse_document_is_exempt(root, parent):
    root.mkdir()
    (root / MANIFEST).write_bytes(manifest_bytes())
    other = parent / "other.json"
    os.link(root / "manifest.json", other)
    with pytest.raises(UsageError, match="is also an input"):
        check(root, inputs=[other], reuse=root / "nowhere.json")


# Replace only what is written


def test_a_rerun_replaces_only_the_planned_outputs(root):
    root.mkdir()
    earlier = earlier_tree(root, (*PATHS, "frames/walk/south/2.png", "gone/clip.png"))
    export(root)  # fewer frames, and a dropped clip
    after = tree(root)
    for stale in ("frames/walk/south/2.png", "gone/clip.png", "notes.txt"):
        assert after[stale] == earlier[stale]
    for path in PATHS:
        assert after[path] == body(path)
    assert json.loads(after[MANIFEST])["tag"] == "new"


def test_changed_paths_leave_the_old_files_alone(root):
    root.mkdir()
    earlier = earlier_tree(root)
    renamed = ("sheet.png", "frames/run/south/0.png", "atlas/run.png")
    export(root, paths=renamed)
    after = tree(root)
    for path in PATHS[1:]:
        assert after[path] == earlier[path]
    assert after["frames/run/south/0.png"] == body("frames/run/south/0.png")


def test_the_manifest_is_replaced_last(root, monkeypatch):
    root.mkdir()
    earlier_tree(root)
    placed = []
    real = os.replace

    def replace(source, dest):
        if ".moskophoros-new-" in Path(source).name:
            placed.append(str(Path(dest).relative_to(root)))
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    export(root)
    assert placed == [*PATHS, MANIFEST]


def test_every_file_is_staged_before_any_target_is_replaced(root, monkeypatch):
    root.mkdir()
    earlier_tree(root)
    events = []
    real_open, real_replace = open, os.replace

    def staging_open(path, mode="r", *args, **kwargs):
        events.append("stage")
        return real_open(path, mode, *args, **kwargs)

    def replace(source, dest):
        events.append("replace")
        return real_replace(source, dest)

    monkeypatch.setattr(publication, "open", staging_open, raising=False)
    monkeypatch.setattr(os, "replace", replace)
    export(root)
    staged = len(PATHS) + 1
    assert events[:staged] == ["stage"] * staged
    assert "stage" not in events[staged:]


def test_staging_files_sit_beside_their_targets_and_none_remain(root, monkeypatch):
    seen = []
    real_open = open

    def staging_open(path, mode="r", *args, **kwargs):
        seen.append(Path(path))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(publication, "open", staging_open, raising=False)
    export(root)
    assert sorted(path.parent.relative_to(root).as_posix() for path in seen) == sorted(
        [str(Path(p).parent) for p in PATHS] + ["."]
    )
    assert not [name for name in tree(root) if "moskophoros-" in name]


def test_a_failure_in_the_end_does_not_delete_backups_that_cannot_be_deleted(
    root, monkeypatch, capsys
):
    root.mkdir()
    earlier_tree(root)
    real = os.remove

    def remove(path):
        if "-earlier-" in Path(path).name and Path(path).name.startswith(".sheet"):
            raise OSError(errno.EACCES, "Permission denied")
        return real(path)

    monkeypatch.setattr(os, "remove", remove)
    export(root)
    err = capsys.readouterr().err
    assert "moskophoros: warning: the earlier" in err
    assert "could not be deleted from" in err
    assert (root / "sheet.png").read_bytes() == body("sheet.png")


# Failures: everything is restored


def failing_scenes():
    return [
        pytest.param(new_root_scene, id="new-root"),
        pytest.param(existing_scene, id="existing-root"),
    ]


def attempt(build, tmp_path, name):
    """A fresh scene and its tree before a run on it."""
    home = tmp_path / name
    home.mkdir()
    root = build(home)
    return root, tree(root.parent)


@pytest.mark.parametrize("build", failing_scenes())
def test_a_rename_failure_at_every_step_restores_every_prior_byte(
    tmp_path, monkeypatch, build
):
    total = total_calls(tmp_path, "replace", build, run_export)
    assert total > len(PATHS)
    for step in range(total):
        root, before = attempt(build, tmp_path, f"fail-{step}")
        calls = Calls(
            monkeypatch,
            "replace",
            at=step,
            error=OSError(errno.EBUSY, "Device or resource busy"),
        )
        with pytest.raises(OutputError, match="cannot write") as raised:
            export(root)
        monkeypatch.undo()
        assert raised.value.exit_code == EXIT_OUTPUT
        assert "Device or resource busy" in str(raised.value)
        assert str(raised.value).endswith("earlier outputs are kept")
        assert len(calls.calls) > step
        assert tree(root.parent) == before, step


@pytest.mark.parametrize("build", failing_scenes())
def test_a_failure_replacing_the_manifest_leaves_no_new_valid_manifest(
    tmp_path, monkeypatch, build
):
    root, before = attempt(build, tmp_path, "metadata")
    real = os.replace

    def replace(source, dest):
        if Path(dest) == root / MANIFEST and "-new-" in Path(source).name:
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(OutputError, match="No space left on device"):
        export(root)
    monkeypatch.undo()
    assert tree(root.parent) == before


class FullDisk:
    """A file handle whose write stops halfway with ENOSPC."""

    def __init__(self, handle):
        self.handle = handle

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.handle.close()

    def write(self, data):
        self.handle.write(data[: len(data) // 2])
        raise OSError(errno.ENOSPC, "No space left on device", self.handle.name)


def fail_staging(monkeypatch, step, kind, code, reason):
    """Make staging the `step`-th file fail: `denied` cannot create it, `full`
    creates it and stops writing halfway."""
    real_open = open
    opened = []

    def staging_open(path, mode="r", *args, **kwargs):
        if "x" not in mode:
            return real_open(path, mode, *args, **kwargs)
        opened.append(path)
        if len(opened) - 1 != step:
            return real_open(path, mode, *args, **kwargs)
        if kind == "denied":
            raise PermissionError(code, reason, str(path))
        return FullDisk(real_open(path, mode, *args, **kwargs))

    monkeypatch.setattr(publication, "open", staging_open, raising=False)


def interrupt_staging(monkeypatch, step):
    """Deliver Ctrl-C right after the `step`-th file is created."""
    real_open = open
    opened = []

    def staging_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if "x" in mode:
            opened.append(path)
            if len(opened) - 1 == step:
                signal.raise_signal(signal.SIGINT)
        return handle

    monkeypatch.setattr(publication, "open", staging_open, raising=False)


def interrupt_after_mkdir(monkeypatch, step):
    """Raise the interrupt itself from the `step`-th directory creation, after
    the directory exists: the bookkeeping must not depend on deferral."""
    real = os.mkdir
    count = []

    def mkdir(path, *args):
        real(path, *args)
        count.append(path)
        if len(count) - 1 == step:
            raise KeyboardInterrupt

    monkeypatch.setattr(os, "mkdir", mkdir)


@pytest.mark.parametrize("build", failing_scenes())
@pytest.mark.parametrize(
    "failure",
    [
        ("full", errno.ENOSPC, "No space left on device"),
        ("denied", errno.EACCES, "Permission denied"),
    ],
)
def test_a_staging_failure_at_every_file_restores_every_prior_byte(
    tmp_path, monkeypatch, build, failure
):
    kind, code, reason = failure
    for step in range(len(PATHS) + 1):
        root, before = attempt(build, tmp_path, f"stage-{kind}-{step}")
        fail_staging(monkeypatch, step, kind, code, reason)
        with pytest.raises(OutputError, match="cannot write") as raised:
            export(root)
        monkeypatch.undo()
        assert reason in str(raised.value)
        assert tree(root.parent) == before, step


def test_every_output_is_staged_before_a_staging_failure_can_change_a_target(
    root, monkeypatch
):
    root.mkdir()
    earlier = earlier_tree(root)

    def staging_open(path, mode="r", *args, **kwargs):
        if Path(path).name.startswith(".manifest.json."):
            raise PermissionError(errno.EACCES, "Permission denied", str(path))
        return open(path, mode, *args, **kwargs)

    monkeypatch.setattr(publication, "open", staging_open, raising=False)
    with pytest.raises(OutputError, match="Permission denied"):
        export(root)
    assert tree(root) == earlier


@pytest.mark.parametrize("build", [new_root_scene])
def test_a_directory_creation_failure_at_every_directory_cleans_what_it_made(
    tmp_path, monkeypatch, build
):
    total = total_calls(tmp_path, "mkdir", build, run_export)
    assert total == 6  # the root, frames, walk, south, atlas, previews
    for step in range(total):
        root, before = attempt(build, tmp_path, f"mkdir-{step}")
        Calls(
            monkeypatch,
            "mkdir",
            at=step,
            error=OSError(errno.EACCES, "Permission denied"),
        )
        with pytest.raises(OutputError, match="cannot create the directory") as raised:
            export(root)
        monkeypatch.undo()
        assert raised.value.exit_code == EXIT_OUTPUT
        assert "Permission denied" in str(raised.value)
        assert tree(root.parent) == before, step


def test_a_directory_that_fills_during_publication_is_not_removed(root, monkeypatch):
    # Another writer puts a file into a directory this run created: it is no
    # longer empty, so the cleanup leaves it and the file alone.
    real = os.replace
    count = []

    def replace(source, dest):
        count.append(dest)
        if len(count) == 2:
            (root / "previews" / "other.txt").write_text("not ours")
            raise OSError(errno.EBUSY, "Device or resource busy")
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(OutputError, match="earlier outputs are kept"):
        export(root)
    assert tree(root) == {
        "previews": None,
        "previews/other.txt": b"not ours",
    }


def test_a_preexisting_directory_is_never_removed(root, monkeypatch):
    (root / "frames" / "walk").mkdir(parents=True)
    before = tree(root)
    Calls(
        monkeypatch,
        "replace",
        at=0,
        error=OSError(errno.EBUSY, "Device or resource busy"),
    )
    with pytest.raises(OutputError):
        export(root)
    assert tree(root) == before


def test_a_failed_run_leaves_a_preexisting_empty_root(root, monkeypatch):
    root.mkdir()
    Calls(
        monkeypatch,
        "replace",
        at=0,
        error=OSError(errno.EBUSY, "Device or resource busy"),
    )
    with pytest.raises(OutputError):
        export(root)
    assert tree(root) == {}


# Interruptions


@pytest.mark.parametrize("build", failing_scenes())
def test_ctrl_c_right_after_any_rename_restores_everything(
    tmp_path, monkeypatch, build
):
    total = total_calls(tmp_path, "replace", build, run_export)
    for step in range(total):
        root, before = attempt(build, tmp_path, f"after-{step}")
        calls = Calls(monkeypatch, "replace", after=step)
        with pytest.raises(KeyboardInterrupt) as raised:
            export(root)
        monkeypatch.undo()
        assert not isinstance(raised.value, Interrupted)
        assert len(calls.calls) > step
        assert tree(root.parent) == before, step


@pytest.mark.parametrize("build", failing_scenes())
def test_a_raised_interrupt_in_any_rename_restores_everything(
    tmp_path, monkeypatch, build
):
    total = total_calls(tmp_path, "replace", build, run_export)
    for step in range(total):
        root, before = attempt(build, tmp_path, f"raised-{step}")
        Calls(monkeypatch, "replace", at=step, error=KeyboardInterrupt())
        with pytest.raises(KeyboardInterrupt):
            export(root)
        monkeypatch.undo()
        assert tree(root.parent) == before, step


def test_ctrl_c_right_after_any_directory_creation_loses_no_directory(
    tmp_path, monkeypatch
):
    for step in range(6):
        root, before = attempt(new_root_scene, tmp_path, f"mkdir-int-{step}")
        calls = Calls(monkeypatch, "mkdir", after=step)
        with pytest.raises(KeyboardInterrupt):
            export(root)
        monkeypatch.undo()
        assert len(calls.calls) > step
        assert tree(root.parent) == before, step


def test_a_raised_interrupt_right_after_a_real_mkdir_is_still_cleaned_up(
    tmp_path, monkeypatch
):
    for step in range(6):
        root, before = attempt(new_root_scene, tmp_path, f"mkdir-raised-{step}")
        interrupt_after_mkdir(monkeypatch, step)
        with pytest.raises(KeyboardInterrupt):
            export(root)
        monkeypatch.undo()
        assert tree(root.parent) == before, step


@pytest.mark.parametrize("build", failing_scenes())
def test_ctrl_c_while_staging_restores_everything(tmp_path, monkeypatch, build):
    for step in range(len(PATHS) + 1):
        root, before = attempt(build, tmp_path, f"staging-{step}")
        interrupt_staging(monkeypatch, step)
        with pytest.raises(KeyboardInterrupt):
            export(root)
        monkeypatch.undo()
        assert tree(root.parent) == before, step


def test_ctrl_c_before_publication_leaves_previous_outputs_untouched(root):
    root.mkdir()
    earlier = earlier_tree(root)
    target = check(root)
    # The command's own phases are interruptible: nothing was published.
    with pytest.raises(KeyboardInterrupt):
        signal.raise_signal(signal.SIGINT)
    assert tree(root) == earlier
    publish(target)  # and the handler was restored for the next publication


def test_ctrl_c_after_every_output_is_in_place_lets_the_run_finish(root, monkeypatch):
    root.mkdir()
    earlier = earlier_tree(root)
    Calls(
        monkeypatch,
        "remove",
        after=0,
        where=lambda path: "-earlier-" in Path(path).name,
    )
    export(root)
    after = tree(root)
    assert after["notes.txt"] == earlier["notes.txt"]
    for path in PATHS:
        assert after[path] == body(path)
    assert not [name for name in after if "-earlier-" in name]


# Rollback failures


def fail_when(monkeypatch, name, matches, error):
    real = getattr(os, name)

    def wrapper(*args, **kwargs):
        if matches(*args):
            raise error
        return real(*args, **kwargs)

    monkeypatch.setattr(os, name, wrapper)


def is_backup(path):
    return "-earlier-" in Path(path).name


def fail_manifest_rename(monkeypatch, root, error):
    """The last step: the manifest's rename into place."""
    real = os.replace

    def replace(source, dest):
        if Path(dest) == root / MANIFEST and "-new-" in Path(source).name:
            raise error
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)


def test_a_restoration_failure_names_the_target_and_its_backup(root, monkeypatch):
    root.mkdir()
    earlier = earlier_tree(root)
    sheet = root / "sheet.png"
    fail_manifest_rename(
        monkeypatch, root, OSError(errno.EBUSY, "Device or resource busy")
    )
    fail_when(
        monkeypatch,
        "replace",
        lambda source, dest: is_backup(source) and Path(dest) == sheet,
        OSError(errno.EACCES, "Permission denied"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert raised.value.exit_code == EXIT_OUTPUT
    assert "Device or resource busy" in message
    assert "rolling back failed" in message
    assert "earlier outputs are kept" not in message
    (backup,) = [name for name in tree(root) if name.startswith(".sheet.png.")]
    assert f"the earlier {str(sheet)!r} could not be restored" in message
    assert f"kept at {str(root / backup)!r}" in message
    # The new file was removed and the earlier one is kept at the backup, whose
    # bytes are intact; every other target was restored.
    assert not sheet.exists()
    assert (root / backup).read_bytes() == earlier["sheet.png"]
    after = tree(root)
    del after[backup]
    for path in (*PATHS[1:], MANIFEST, "notes.txt"):
        assert after[path] == earlier[path], path


def test_a_removal_failure_of_a_new_file_is_reported_and_the_rest_continues(
    root, monkeypatch
):
    root.mkdir()
    earlier = earlier_tree(root, PATHS[:-1])  # the preview is new
    preview = root / "previews" / "walk.gif"
    fail_manifest_rename(
        monkeypatch, root, OSError(errno.EBUSY, "Device or resource busy")
    )
    fail_when(
        monkeypatch,
        "remove",
        lambda path: Path(path) == preview,
        OSError(errno.EACCES, "Permission denied"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert (
        f"the new {str(preview)!r} could not be removed: Permission denied" in message
    )
    assert "earlier outputs are kept" not in message
    assert preview.read_bytes() == body("previews/walk.gif")
    # The directory holding it is not empty, so it stays.
    assert (root / "previews").is_dir()
    for path in (*PATHS[:-1], MANIFEST):
        assert (root / path).read_bytes() == earlier[path], path


def test_a_failed_removal_of_a_new_manifest_is_reported(root, monkeypatch):
    root.mkdir()
    manifest = root / MANIFEST
    real = os.replace

    def replace(source, dest):
        # Fail the last file: the manifest is placed, then the run is
        # interrupted before completion.
        if Path(dest) == manifest and "-new-" in Path(source).name:
            real(source, dest)
            raise KeyboardInterrupt
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    fail_when(
        monkeypatch,
        "remove",
        lambda path: Path(path) == manifest,
        OSError(errno.EPERM, "Operation not permitted"),
    )
    with pytest.raises(Interrupted) as raised:
        export(root)
    monkeypatch.undo()
    assert isinstance(raised.value, KeyboardInterrupt)
    assert str(raised.value).startswith("interrupted; rolling back failed: ")
    assert f"the new {str(manifest)!r} could not be removed" in str(raised.value)


def test_a_directory_removal_failure_is_reported_without_a_false_clean_claim(
    root, monkeypatch
):
    Calls(
        monkeypatch,
        "replace",
        at=1,
        error=OSError(errno.EBUSY, "Device or resource busy"),
    )
    fail_when(
        monkeypatch,
        "rmdir",
        lambda path: Path(path) == root / "atlas",
        OSError(errno.EACCES, "Permission denied"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert "earlier outputs are kept, but the new directory" in message
    assert str(root / "atlas") in message
    assert (root / "atlas").is_dir()
    assert not (root / "sheet.png").exists()


def test_rollback_continues_past_a_failed_step(root, monkeypatch):
    root.mkdir()
    earlier = earlier_tree(root)
    fail_manifest_rename(
        monkeypatch, root, OSError(errno.EBUSY, "Device or resource busy")
    )
    fail_when(
        monkeypatch,
        "replace",
        lambda source, dest: is_backup(source) and Path(dest).name == "1.png",
        OSError(errno.EACCES, "Permission denied"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert message.count("could not be restored") == 1
    for path in ("sheet.png", "frames/walk/south/0.png", "atlas/walk.png", MANIFEST):
        assert (root / path).read_bytes() == earlier[path], path


def test_an_interruption_with_a_failed_rollback_keeps_its_class_and_reports(
    root, monkeypatch
):
    root.mkdir()
    earlier_tree(root)
    sheet = root / "sheet.png"
    Calls(monkeypatch, "replace", at=7, error=KeyboardInterrupt())
    fail_when(
        monkeypatch,
        "replace",
        lambda source, dest: is_backup(source) and Path(dest) == sheet,
        OSError(errno.EACCES, "Permission denied"),
    )
    with pytest.raises(Interrupted) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert message.startswith("interrupted; rolling back failed: ")
    assert f"the earlier {str(sheet)!r} could not be restored and is kept at" in message


def test_rollback_does_not_cross_a_link_that_appeared(root, monkeypatch):
    # A directory this run made is replaced by a link to elsewhere before the
    # failure: the cleanup must not delete through it.
    outside = root.parent / "outside"
    outside.mkdir()
    (outside / "keep.png").write_bytes(b"outside")
    (outside / "walk.png").write_bytes(b"outside too")  # where a rollback would reach
    root.mkdir()
    real = os.replace
    count = []

    def replace(source, dest):
        count.append(dest)
        if len(count) == 5:
            (root / "atlas" / "walk.png").unlink()
            (root / "atlas").rmdir()
            (root / "atlas").symlink_to(outside)
            raise OSError(errno.EBUSY, "Device or resource busy")
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(OutputError):
        export(root)
    monkeypatch.undo()
    assert tree(outside) == {"keep.png": b"outside", "walk.png": b"outside too"}
    assert (root / "atlas").is_symlink()


# Lookups that fail are not answers


def fail_lstat(monkeypatch, matches, error):
    """Make `os.lstat` of a path `matches` accepts raise `error`."""
    real = os.lstat

    def lstat(path, *args, **kwargs):
        if matches(Path(path)):
            raise error
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)


def test_a_failed_backup_lookup_in_rollback_does_not_hide_a_restoration(
    root, monkeypatch
):
    root.mkdir()
    earlier = earlier_tree(root)
    failing = []  # set once the manifest's rename has failed: the rollback
    real = os.replace

    def replace(source, dest):
        if Path(dest) == root / MANIFEST and "-new-" in Path(source).name:
            failing.append(True)
            raise OSError(errno.EBUSY, "Device or resource busy")
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    fail_lstat(
        monkeypatch,
        lambda path: bool(failing) and is_backup(path),
        OSError(errno.EIO, "Input/output error"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    assert "Device or resource busy" in str(raised.value)
    # The lookups failed, but the restorations did not need them.
    assert str(raised.value).endswith("earlier outputs are kept")
    assert tree(root) == earlier


def test_a_backup_that_cannot_be_confirmed_missing_is_reported_not_assumed(
    root, monkeypatch
):
    root.mkdir()
    earlier_tree(root)
    sheet = root / "sheet.png"
    failing = []  # set once the manifest's rename has failed: the rollback
    real = os.replace

    def replace(source, dest):
        if Path(dest) == root / MANIFEST and "-new-" in Path(source).name:
            failing.append(True)
            raise OSError(errno.EBUSY, "Device or resource busy")
        if is_backup(source) and Path(dest) == sheet:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")
        return real(source, dest)

    monkeypatch.setattr(os, "replace", replace)
    fail_lstat(
        monkeypatch,
        lambda path: (
            bool(failing) and is_backup(path) and path.name.startswith(".sheet.png.")
        ),
        OSError(errno.EIO, "Input/output error"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert f"the earlier {str(sheet)!r} could not be restored" in message
    assert "kept at" in message
    assert "earlier outputs are kept" not in message


def test_a_failed_lookup_of_an_existing_target_never_overwrites_it(root, monkeypatch):
    root.mkdir()
    earlier = earlier_tree(root)
    sheet = root / "sheet.png"
    target = check(root)
    looked = []
    real = os.lstat

    def lstat(path, *args, **kwargs):
        if Path(path) == sheet:
            looked.append(path)
            # The two rechecks come first; then the publisher asks whether
            # the target exists, to move it aside.
            if len(looked) == 3:
                raise OSError(errno.EIO, "Input/output error")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)
    with pytest.raises(OutputError, match="Input/output error"):
        publish(target)
    monkeypatch.undo()
    assert len(looked) == 3
    assert tree(root) == earlier


# A failing write is part of the rollback record


def test_a_partial_staged_file_is_removed_by_the_guarded_rollback(root, monkeypatch):
    # The write fails halfway; the cleanup fails too, and says so.
    root.mkdir()
    earlier = earlier_tree(root)
    fail_staging(monkeypatch, 2, "full", errno.ENOSPC, "No space left on device")
    fail_when(
        monkeypatch,
        "remove",
        lambda path: ".1.png.moskophoros-new-" in Path(path).name,
        OSError(errno.EACCES, "Permission denied"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert "No space left on device" in message
    assert "the temporary file" in message
    assert "could not be removed: Permission denied" in message
    leftover = [name for name in tree(root) if "moskophoros-new-" in name]
    assert len(leftover) == 1
    assert leftover[0].startswith("frames/walk/south/.1.png.")
    for path in (*PATHS, MANIFEST, "notes.txt"):
        assert (root / path).read_bytes() == earlier[path], path


def test_a_failed_write_does_not_clean_up_through_a_link_that_appeared(
    root, monkeypatch
):
    import re

    outside = root.parent / "outside"
    planted = outside / "walk" / "south"
    planted.mkdir(parents=True)
    # Where the failed write's temporary file would be, through the link.
    decoy = planted / f".1.png.moskophoros-new-{os.getpid()}-0"
    decoy.write_bytes(b"not ours")
    real_open = open

    def staging_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if re.search(r"/south/\.1\.png\.", str(path)):
            (root / "frames").rename(root / "frames-aside")
            (root / "frames").symlink_to(outside)
            return FullDisk(handle)
        return handle

    monkeypatch.setattr(publication, "open", staging_open, raising=False)
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    assert decoy.read_bytes() == b"not ours"
    assert "its directory is now a link" in str(raised.value)
    assert "earlier outputs are kept" in str(raised.value)


def test_deleting_backups_after_completion_does_not_follow_a_link_that_appeared(
    root, monkeypatch, capsys
):
    outside = root.parent / "outside"
    outside.mkdir()
    # The backup of atlas/walk.png is named like this; the decoy is the same
    # name outside the root, where a followed link would delete it.
    decoy = outside / f".walk.png.moskophoros-earlier-{os.getpid()}-0"
    decoy.write_bytes(b"not ours")
    root.mkdir()
    earlier_tree(root)
    real = os.replace

    def replace(source, dest):
        real(source, dest)
        if Path(dest) == root / MANIFEST and "-new-" in Path(source).name:
            # The last rename: the publication is complete, its cleanup begins.
            (root / "atlas").rename(root / "atlas-aside")
            (root / "atlas").symlink_to(outside)

    monkeypatch.setattr(os, "replace", replace)
    export(root)
    monkeypatch.undo()
    assert decoy.read_bytes() == b"not ours"
    warning = capsys.readouterr().err
    assert "warning: the earlier" in warning
    assert "its directory is now a link" in warning
    # The real backup is kept, where it was moved.
    assert (root / "atlas-aside" / decoy.name).read_bytes() == body(
        "atlas/walk.png", "earlier"
    )


def test_a_confinement_lookup_that_fails_skips_the_destructive_step(root, monkeypatch):
    import re

    outside = root.parent / "outside"
    planted = outside / "walk" / "south"
    planted.mkdir(parents=True)
    decoy = planted / f".1.png.moskophoros-new-{os.getpid()}-0"
    decoy.write_bytes(b"not ours")
    armed = []
    real_open = open

    def staging_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if re.search(r"/south/\.1\.png\.", str(path)):
            (root / "frames").rename(root / "frames-aside")
            (root / "frames").symlink_to(outside)
            armed.append(True)
            return FullDisk(handle)
        return handle

    monkeypatch.setattr(publication, "open", staging_open, raising=False)
    fail_lstat(
        monkeypatch,
        lambda path: bool(armed) and path == root / "frames",
        OSError(errno.EIO, "Input/output error"),
    )
    with pytest.raises(OutputError) as raised:
        export(root)
    monkeypatch.undo()
    message = str(raised.value)
    assert decoy.read_bytes() == b"not ours"
    assert "its directory could not be checked: Input/output error" in message
    assert "the temporary file" in message


# The positional form's publisher


def test_publish_writes_beside_the_targets_and_replaces(tmp_path):
    (tmp_path / "a.png").write_bytes(b"earlier")
    publication.publish([(tmp_path / "a.png", b"one"), (tmp_path / "b.json", b"two")])
    assert tree(tmp_path) == {"a.png": b"one", "b.json": b"two"}


def test_publish_moves_a_linked_target_aside_and_replaces_it_with_a_file(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.png").write_bytes(b"referent")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").symlink_to(outside / "real.png")
    publication.publish([(out / "a.png", b"new")])
    assert not (out / "a.png").is_symlink()
    assert (out / "a.png").read_bytes() == b"new"
    assert (outside / "real.png").read_bytes() == b"referent"


def test_publish_restores_a_linked_target_as_the_link_itself(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.png").write_bytes(b"referent")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").symlink_to(outside / "real.png")
    (out / "b.png").write_bytes(b"earlier")
    before = tree(tmp_path)
    Calls(
        monkeypatch,
        "replace",
        at=3,
        error=OSError(errno.EBUSY, "Device or resource busy"),
    )
    with pytest.raises(OutputError, match="earlier outputs are kept"):
        publication.publish([(out / "a.png", b"new"), (out / "b.png", b"new")])
    monkeypatch.undo()
    assert tree(tmp_path) == before
    assert (out / "a.png").is_symlink()
    assert os.readlink(out / "a.png") == str(outside / "real.png")


def test_publish_makes_no_directories(tmp_path):
    with pytest.raises(OutputError, match="cannot write"):
        publication.publish([(tmp_path / "missing" / "a.png", b"x")])
    assert tree(tmp_path) == {}


def test_the_error_classes_carry_the_documented_exit_codes():
    assert OutputError.exit_code == 6
    assert UsageError.exit_code == 2
    assert issubclass(Interrupted, KeyboardInterrupt)
