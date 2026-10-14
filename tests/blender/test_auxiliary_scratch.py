"""The auxiliary render's TGA and OpenEXR share the command workspace's
lifetime (design §CLI, §Capture): a temporary workspace takes them with it
after success, failure or interruption, and a retained `--work-dir` keeps
them inside it. Faults are injected around the real script's `save_exr`
through a wrapper script, with real headless Blender."""

import os
import signal
import tempfile
import threading

import pytest
from material_models import edges

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

INTERMEDIATES = {"auxiliary.tga", "auxiliary.exr"}

# Runs the real script with its own temporary files under `child_temp`.
# `fault` is "none", "raise" (fail right after the OpenEXR is saved) or
# "block" (report the pid on `ready` once it is saved, then wait forever).
WRAPPER = """\
import os, runpy, sys, tempfile
tempfile.tempdir = {child_temp!r}
scope = runpy.run_path({script!r})["main"].__globals__
original = scope["save_exr"]


def save_exr(scene, path):
    original(scene, path)
    if {fault!r} == "raise":
        raise OSError("injected failure after the OpenEXR was saved")
    if {fault!r} == "block":
        with open({ready!r}, "w") as fifo:
            fifo.write(str(os.getpid()))
        with open({never!r}) as fifo:
            fifo.read()


scope["save_exr"] = save_exr
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

    def __init__(self, tmp_path, monkeypatch, found, fault):
        self.found = found
        self.parent_temp = tmp_path / "parent-temp"
        self.child_temp = tmp_path / "child-temp"
        self.out = tmp_path / "out"
        for directory in (self.parent_temp, self.child_temp, self.out):
            directory.mkdir()
        self.ready, never = tmp_path / "ready", tmp_path / "never"
        if fault == "block":
            os.mkfifo(self.ready)
            os.mkfifo(never)
        wrapper = tmp_path / "fault.py"
        wrapper.write_text(
            WRAPPER.format(
                child_temp=str(self.child_temp),
                script=str(blender.SCRIPT),
                fault=fault,
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

    def stray_intermediates(self):
        """Auxiliary intermediates left anywhere under the script's own
        temporary directory, outside the command's workspace."""
        return sorted(
            str(path.relative_to(self.child_temp))
            for path in self.child_temp.rglob("*")
            if path.name in INTERMEDIATES or "auxiliary" in path.name
        )


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


def test_a_successful_run_leaves_no_intermediates(tmp_path, monkeypatch, capsys, found):
    run = Run(tmp_path, monkeypatch, found, "none")
    work = tmp_path / "work"
    status = cli.run(run.argv("--work-dir", str(work)))
    assert status == 0, capsys.readouterr().err
    assert sorted(p.name for p in (work / "render").iterdir()) == [
        "color",
        "depth",
        "job.json",
        "matid",
        "normal",
        "result.json",
        "shade",
    ]
    assert run.stray_intermediates() == []
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
    assert run.stray_intermediates() == []
    assert run.outputs() == run.earlier


def test_a_failure_with_a_work_dir_keeps_the_intermediates_inside_it(
    tmp_path, monkeypatch, capsys, found
):
    run = Run(tmp_path, monkeypatch, found, "raise")
    work = tmp_path / "work"
    status = cli.run(run.argv("--work-dir", str(work)))
    assert status == 5, capsys.readouterr().err
    scratch = work / "render" / "auxiliary"
    assert {path.name for path in scratch.iterdir()} == INTERMEDIATES
    assert run.stray_intermediates() == []
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
    assert run.stray_intermediates() == []
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
    scratch = work / "render" / "auxiliary"
    assert {path.name for path in scratch.iterdir()} == INTERMEDIATES
    assert run.stray_intermediates() == []
    assert list(run.parent_temp.iterdir()) == []
    assert run.outputs() == run.earlier
