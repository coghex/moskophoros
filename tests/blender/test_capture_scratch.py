"""The capture render's TGA and OpenEXR, and each phase's private copy of
the model, share the command workspace's lifetime (design §CLI, §Capture): a
temporary workspace takes them with it after success, failure or
interruption, and a retained `--work-dir` keeps them inside it. Faults are
injected around the real script's `save_exr` and `import_glb` through a
wrapper script, with real headless Blender."""

import os
import signal
import tempfile
import threading
from pathlib import Path

import pytest
from material_models import edges

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

# What the scratch holds when the fault strikes, just after the back
# render's OpenEXR is saved; the front render's TGA and OpenEXR and the count
# render's OpenEXR come after it.
INTERMEDIATES = {"capture.tga", "capture.exr"}

# Runs the real script with its own temporary files under `child_temp`. Each
# phase's import confirms its copy of the model exists and records the
# directory it was imported from in `imports`. `fault` is "none", "raise"
# (fail) or "block" (report the pid on `ready`, then wait forever), and
# strikes at `at`: "save_exr", just after the render's first OpenEXR is saved,
# or "measure" or "render", just after that phase's import.
WRAPPER = """\
import json, os, runpy, sys, tempfile
tempfile.tempdir = {child_temp!r}
scope = runpy.run_path({script!r})["main"].__globals__
original_save_exr = scope["save_exr"]
original_import_glb = scope["import_glb"]
with open(sys.argv[-1], encoding="utf-8") as handle:
    mode = json.load(handle)["mode"]


def fault(at, message):
    if at != {at!r}:
        return
    if {fault!r} == "raise":
        raise OSError("injected failure after " + message)
    if {fault!r} == "block":
        with open({ready!r}, "w") as fifo:
            fifo.write(str(os.getpid()))
        with open({never!r}) as fifo:
            fifo.read()


def save_exr(scene, path):
    original_save_exr(scene, path)
    fault("save_exr", "the OpenEXR was saved")


def import_glb(data, directory):
    original_import_glb(data, directory)
    with open(os.path.join(directory, "subject.glb"), "rb") as handle:
        if handle.read() != data:
            raise OSError("the import's copy of the model is not the model")
    with open({imports!r}, "a", encoding="utf-8") as handle:
        handle.write(mode + " " + os.path.abspath(directory) + "\\n")
    fault(mode, "the " + mode + " phase's import")


scope["save_exr"] = save_exr
scope["import_glb"] = import_glb
scope["main"](sys.argv)
"""


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


class Run:
    """One command run with a faulty script, its temporary directories under
    the test's control, and earlier final outputs to keep."""

    def __init__(self, tmp_path, monkeypatch, found, fault, at="save_exr"):
        self.found = found
        self.parent_temp = tmp_path / "parent-temp"
        self.child_temp = tmp_path / "child-temp"
        self.out = tmp_path / "out"
        for directory in (self.parent_temp, self.child_temp, self.out):
            directory.mkdir()
        self.ready, never = tmp_path / "ready", tmp_path / "never"
        self.imports = tmp_path / "imports"
        if fault == "block":
            os.mkfifo(self.ready)
            os.mkfifo(never)
        wrapper = tmp_path / "fault.py"
        wrapper.write_text(
            WRAPPER.format(
                child_temp=str(self.child_temp),
                script=str(blender.SCRIPT),
                fault=fault,
                at=at,
                imports=str(self.imports),
                ready=str(self.ready),
                never=str(never),
            )
        )
        monkeypatch.setattr(blender, "SCRIPT", wrapper)
        monkeypatch.setattr(tempfile, "tempdir", str(self.parent_temp))
        self.model = edges(tmp_path)
        self.earlier = {"sheet.png": b"earlier sheet", "sheet.json": b"earlier json"}
        for name, data in self.earlier.items():
            (self.out / name).write_bytes(data)

    def argv(self, *options):
        return [
            "--no-user-config",
            "--blender",
            str(self.found.path),
            "--directions",
            "1",
            "--cell",
            "8x8",
            "--supersample",
            "1",
            "--no-preview",
            "--ao-samples",
            "1",
            *options,
            str(self.model),
            str(self.out / "sheet.png"),
        ]

    def outputs(self):
        return {path.name: path.read_bytes() for path in self.out.iterdir()}

    def strays(self):
        """Everything left under the script's own temporary directory,
        outside the command's workspace: an import's copy of the model or its
        directory as much as the render's intermediates."""
        return sorted(
            str(path.relative_to(self.child_temp))
            for path in self.child_temp.rglob("*")
        )

    def imported(self):
        """Each phase that imported the model, with the directory it imported
        its copy from, in order."""
        if not self.imports.exists():
            return []
        lines = self.imports.read_text(encoding="utf-8").splitlines()
        return [
            (mode, Path(directory))
            for mode, directory in (line.split(" ", 1) for line in lines)
        ]


def interrupted(run, capsys, argv):
    """Run `argv`, interrupting the command once the script has saved its
    first OpenEXR; return the status, stderr and the Blender process's pid."""
    main = threading.main_thread().ident
    launched = []

    def interrupt_when_ready():
        with open(run.ready) as fifo:
            launched.append(int(fifo.read()))
        signal.pthread_kill(main, signal.SIGINT)

    helper = threading.Thread(target=interrupt_when_ready)
    helper.start()
    status = cli.run(argv)
    helper.join()
    _, err = capsys.readouterr()
    (pid,) = launched
    return status, err, pid


def test_a_successful_run_leaves_no_intermediates_or_copies(
    tmp_path, monkeypatch, capsys, found
):
    run = Run(tmp_path, monkeypatch, found, "none")
    work = tmp_path / "work"
    status = cli.run(run.argv("--work-dir", str(work)))
    assert status == 0, capsys.readouterr().err
    assert [mode for mode, _ in run.imported()] == ["measure", "render"]
    assert not any(directory.exists() for _, directory in run.imported())
    assert sorted(p.name for p in (work / "measure").iterdir()) == [
        "job.json",
        "result.json",
    ]
    assert sorted(p.name for p in (work / "render").iterdir()) == [
        "color",
        "depth",
        "front_alpha",
        "front_color",
        "front_matid",
        "front_shade",
        "job.json",
        "matid",
        "normal",
        "result.json",
        "shade",
    ]
    assert run.strays() == []
    assert list(run.parent_temp.iterdir()) == []


def test_a_failure_after_the_intermediates_exist_removes_them(
    tmp_path, monkeypatch, capsys, found
):
    run = Run(tmp_path, monkeypatch, found, "raise")
    status = cli.run(run.argv())
    err = capsys.readouterr().err
    assert status == 5, err
    assert "injected failure after the OpenEXR was saved" in err
    # The temporary workspace, intermediates and all, is gone, and none was
    # left outside it.
    assert list(run.parent_temp.iterdir()) == []
    assert run.strays() == []
    assert run.outputs() == run.earlier


def test_a_failure_with_a_work_dir_keeps_the_intermediates_inside_it(
    tmp_path, monkeypatch, capsys, found
):
    run = Run(tmp_path, monkeypatch, found, "raise")
    work = tmp_path / "work"
    status = cli.run(run.argv("--work-dir", str(work)))
    assert status == 5, capsys.readouterr().err
    scratch = work / "render" / "scratch"
    assert {path.name for path in scratch.iterdir()} == INTERMEDIATES
    assert run.strays() == []
    assert list(run.parent_temp.iterdir()) == []
    assert run.outputs() == run.earlier


def test_an_interruption_after_the_intermediates_exist_removes_them(
    tmp_path, monkeypatch, capsys, found
):
    run = Run(tmp_path, monkeypatch, found, "block")
    status, err, pid = interrupted(run, capsys, run.argv())
    assert (status, err) == (130, "moskophoros: error: interrupted\n")
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # stopped and reaped
    assert list(run.parent_temp.iterdir()) == []
    assert run.strays() == []
    assert run.outputs() == run.earlier


def test_an_interruption_with_a_work_dir_keeps_the_intermediates_inside_it(
    tmp_path, monkeypatch, capsys, found
):
    run = Run(tmp_path, monkeypatch, found, "block")
    work = tmp_path / "work"
    status, err, pid = interrupted(run, capsys, run.argv("--work-dir", str(work)))
    assert (status, err) == (130, "moskophoros: error: interrupted\n")
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    scratch = work / "render" / "scratch"
    assert {path.name for path in scratch.iterdir()} == INTERMEDIATES
    assert run.strays() == []
    assert list(run.parent_temp.iterdir()) == []
    assert run.outputs() == run.earlier


# Each phase's private copy of the model (design §Capture job and result
# contract, ownership and failure handling), struck just after the phase has
# imported it.

PHASES = ("measure", "render")


@pytest.mark.parametrize("phase", PHASES)
def test_a_failure_after_the_import_removes_the_copy(
    tmp_path, monkeypatch, capsys, found, phase
):
    run = Run(tmp_path, monkeypatch, found, "raise", at=phase)
    status = cli.run(run.argv())
    err = capsys.readouterr().err
    assert status == 5, err
    assert f"injected failure after the {phase} phase's import" in err
    assert [mode for mode, _ in run.imported()][-1] == phase
    assert not any(directory.exists() for _, directory in run.imported())
    assert run.strays() == []
    assert list(run.parent_temp.iterdir()) == []
    assert run.outputs() == run.earlier


@pytest.mark.parametrize("phase", PHASES)
def test_a_failure_with_a_work_dir_after_the_import_removes_the_copy(
    tmp_path, monkeypatch, capsys, found, phase
):
    # The retained workspace keeps the phase's evidence, but the script still
    # removes its copy, directory and all, when it fails.
    run = Run(tmp_path, monkeypatch, found, "raise", at=phase)
    work = tmp_path / "work"
    status = cli.run(run.argv("--work-dir", str(work)))
    assert status == 5, capsys.readouterr().err
    assert [mode for mode, _ in run.imported()][-1] == phase
    assert not any(directory.exists() for _, directory in run.imported())
    assert sorted(p.name for p in (work / phase).iterdir()) == ["job.json"]
    assert run.strays() == []
    assert list(run.parent_temp.iterdir()) == []
    assert run.outputs() == run.earlier


@pytest.mark.parametrize("phase", PHASES)
def test_an_interruption_after_the_import_leaves_no_copy(
    tmp_path, monkeypatch, capsys, found, phase
):
    run = Run(tmp_path, monkeypatch, found, "block", at=phase)
    status, err, pid = interrupted(run, capsys, run.argv())
    assert (status, err) == (130, "moskophoros: error: interrupted\n")
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # stopped and reaped
    assert [mode for mode, _ in run.imported()][-1] == phase
    # Killed, Blender removed nothing: the copy went with the temporary
    # workspace, and none was left outside it.
    assert not any(directory.exists() for _, directory in run.imported())
    assert run.strays() == []
    assert list(run.parent_temp.iterdir()) == []
    assert run.outputs() == run.earlier


@pytest.mark.parametrize("phase", PHASES)
def test_an_interruption_with_a_work_dir_after_the_import_keeps_any_copy_inside_it(
    tmp_path, monkeypatch, capsys, found, phase
):
    run = Run(tmp_path, monkeypatch, found, "block", at=phase)
    work = tmp_path / "work"
    status, err, pid = interrupted(run, capsys, run.argv("--work-dir", str(work)))
    assert (status, err) == (130, "moskophoros: error: interrupted\n")
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert [mode for mode, _ in run.imported()][-1] == phase
    # The retained workspace may still hold the copy, but nothing else may.
    assert all(
        directory.is_relative_to(work) or not directory.exists()
        for _, directory in run.imported()
    )
    assert run.strays() == []
    assert list(run.parent_temp.iterdir()) == []
    assert run.outputs() == run.earlier
