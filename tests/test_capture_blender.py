"""The Blender launcher, with controlled fake Blender executables.

A fake is a small Python script run through its shebang. It answers
`--version` with a chosen line and, for a capture phase, logs what it saw
and then does what the test asks. Tests coordinate with fakes through files
and FIFOs, never by sleeping.
"""

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest
from PIL import Image

from moskophoros import sampling, views
from moskophoros.capture import blender
from moskophoros.capture.backend import (
    BackendError,
    MalformedJob,
    Settings,
    Source,
    build_job,
    job_sha256,
)
from moskophoros.gltf import Clip, InputError, SelectedClip

DESIGN = Path(__file__).resolve().parents[1] / "docs" / "design.md"


def executable(path, text="#!/bin/sh\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


def fake_blender(path, capture="", version="Blender 5.2.2 LTS", version_status=0):
    """A fake Blender at `path`. `capture` is Python run for a capture phase,
    after it logs its argv, working directory, listing and job to `log`."""
    script = f"""\
        #!{sys.executable}
        import json, os, pathlib, sys
        args = sys.argv[1:]
        if args == ["--version"]:
            print({version!r})
            sys.exit({version_status})
        log = pathlib.Path(__file__).with_name("log.json")
        log.write_text(json.dumps({{
            "argv": args,
            "cwd": os.getcwd(),
            "listing": sorted(os.listdir()),
            "job": pathlib.Path(args[-1]).read_text(),
        }}))
    """
    return executable(path, textwrap.dedent(script) + textwrap.dedent(capture))


def read_log(fake):
    return json.loads(fake.with_name("log.json").read_text())


# Finding Blender


@pytest.fixture
def sources(tmp_path):
    """One executable for each source, and an environment naming them."""
    return {
        "option": executable(tmp_path / "option" / "blender"),
        "environment": executable(tmp_path / "environment" / "blender"),
        "path": executable(tmp_path / "path" / "blender"),
        "app": executable(tmp_path / "app" / "Blender"),
    }


def find(sources, option=True, environment=True, path=True, platform="darwin"):
    environ = {
        "PATH": str(sources["path"].parent) if path else "/nonexistent",
    }
    if environment:
        environ["MOSKOPHOROS_BLENDER"] = str(sources["environment"])
    return blender.find_blender(
        sources["option"] if option else None,
        environ=environ,
        platform=platform,
        macos_app=sources["app"],
    )


def test_discovery_order(sources):
    assert find(sources) == (sources["option"], "--blender")
    assert find(sources, option=False) == (
        sources["environment"],
        "$MOSKOPHOROS_BLENDER",
    )
    assert find(sources, option=False, environment=False) == (sources["path"], "PATH")
    assert find(sources, option=False, environment=False, path=False) == (
        sources["app"],
        "the macOS application",
    )


def test_the_macos_application_is_only_used_on_macos(sources):
    with pytest.raises(BackendError, match="not found") as raised:
        find(sources, option=False, environment=False, path=False, platform="linux")
    assert raised.value.exit_code == 5
    assert str(sources["app"]) not in str(raised.value)


def test_no_blender_found(sources, tmp_path):
    sources["app"] = tmp_path / "missing" / "Blender"
    with pytest.raises(BackendError, match="Blender was not found") as raised:
        find(sources, option=False, environment=False, path=False)
    assert raised.value.exit_code == 5
    assert str(sources["app"]) in str(raised.value)


@pytest.mark.parametrize("problem", ["missing", "not executable", "a directory"])
@pytest.mark.parametrize("source", ["option", "environment"])
def test_an_unusable_configured_source_does_not_fall_through(
    sources, tmp_path, source, problem
):
    # Every later source is usable, but none is tried.
    bad = tmp_path / "bad"
    if problem == "not executable":
        bad.write_text("#!/bin/sh\n")
        bad.chmod(0o644)
    elif problem == "a directory":
        bad.mkdir()
    sources[source] = bad
    name = "--blender" if source == "option" else "$MOSKOPHOROS_BLENDER"
    with pytest.raises(BackendError) as raised:
        find(sources, option=source == "option")
    assert raised.value.exit_code == 5
    message = str(raised.value)
    assert message.startswith(f"{name} names {str(bad)!r}")
    assert "no other Blender is tried" in message


def test_an_empty_environment_variable_is_unset(sources):
    environ = {"MOSKOPHOROS_BLENDER": "", "PATH": str(sources["path"].parent)}
    assert blender.find_blender(None, environ, "linux") == (sources["path"], "PATH")


def test_relative_paths_become_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    executable(tmp_path / "bin" / "blender")
    expected = tmp_path / "bin" / "blender"
    assert blender.find_blender(Path("bin/blender"), {}, "linux")[0] == expected
    assert blender.find_blender(None, {"PATH": "bin"}, "linux")[0] == expected


# The version check


@pytest.mark.parametrize(
    ("line", "version"),
    [
        ("Blender 5.2.2 LTS", "5.2.2"),
        ("Blender 5.2.2", "5.2.2"),
        ("Blender 5.2.10 Alpha", "5.2.10"),
        ("Blender 5.2", "5.2"),
    ],
)
def test_supported_version_lines(tmp_path, line, version):
    fake = fake_blender(tmp_path / "blender", version=line)
    assert blender.check_version(fake) == version


def test_another_series_needs_any_blender(tmp_path):
    fake = fake_blender(tmp_path / "blender", version="Blender 4.5.3 LTS")
    with pytest.raises(BackendError, match="4.5.3, but 5.2 is supported") as raised:
        blender.check_version(fake)
    assert raised.value.exit_code == 5
    assert "--any-blender" in str(raised.value)
    assert blender.check_version(fake, any_blender=True) == "4.5.3"


@pytest.mark.parametrize(
    "line", ["Blender", "Blender five", "blender 5.2.2", "", "5.2.2"]
)
def test_an_unparseable_version_fails_even_with_any_blender(tmp_path, line):
    fake = fake_blender(tmp_path / "blender", version=line)
    with pytest.raises(BackendError, match="did not report a version") as raised:
        blender.check_version(fake, any_blender=True)
    assert repr(line) in str(raised.value)


def test_a_failed_version_probe_is_a_backend_error(tmp_path):
    # The output parses, but the probe failed.
    fake = fake_blender(tmp_path / "blender", version_status=1)
    with pytest.raises(BackendError, match="exited with status 1") as raised:
        blender.check_version(fake, any_blender=True)
    assert "Blender 5.2.2 LTS" in raised.value.stdout


def test_a_version_probe_that_cannot_start(tmp_path):
    fake = executable(tmp_path / "blender", "#!/nonexistent/interpreter\n")
    with pytest.raises(BackendError, match="could not run") as raised:
        blender.check_version(fake, any_blender=True)
    assert raised.value.exit_code == 5


def test_locate_records_the_actual_version(tmp_path):
    fake = fake_blender(tmp_path / "blender", version="Blender 4.2.0")
    found = blender.locate(fake, any_blender=True, environ={}, platform="linux")
    assert found == blender.Blender(fake, "--blender", "4.2.0")


def test_the_supported_series_is_the_design_s():
    section = DESIGN.read_text().split("### Supported Blender version", 1)[1]
    match = re.search(r"\*\*Blender (\d+)\.(\d+) LTS\*\*", section)
    assert (int(match[1]), int(match[2])) == blender.SUPPORTED_SERIES


# Running a phase


def make_job(tmp_path, mode="measure"):
    """A real source file and a one-frame job for it in `tmp_path/work`."""
    source = tmp_path / "hero.glb"
    source.write_bytes(b"glTF model bytes")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    clips = (SelectedClip(Clip(0, "idle", 0.0, 0.0, ()), one_shot=False),)
    settings = Settings(
        "topdown",
        90.0,
        1,
        0.0,
        0.0,
        12.0,
        2,
        10.0,
        (4, 3),
        (0.0, 0.0, 0.0),
        (2, 2),
        "error",
    )
    frames = sampling.frames("hero", clips, views.View(90.0, 1, 0.0), 12.0)
    workspace = tmp_path / "work"
    workspace.mkdir()
    job = build_job(
        mode,
        Source(source, sha, 0),
        "hero",
        settings,
        clips,
        frames,
        str(workspace / mode),
    )
    return workspace, job


def measure_result(job):
    return json.dumps(
        {
            "schema": "moskophoros.capture-result/1",
            "mode": "measure",
            "job_sha256": job_sha256(job),
            "source_sha256": job["source"]["sha256"],
            "backend": {"blender": "5.2.2"},
            "frames": [
                {
                    "address": frame["address"],
                    "bounds_m": {"L": 0.5, "R": 0.5, "U": 1.0, "D": 0.0},
                    "height_m": 1.0,
                }
                for frame in job["frames"]
            ],
            "roots": [],
        }
    )


def write_result(text):
    return f"pathlib.Path('result.json').write_text({text!r})\n"


def fake_found(path):
    return blender.Blender(path, "--blender", "5.2.2")


def test_a_measure_phase(tmp_path):
    workspace, job = make_job(tmp_path)
    fake = fake_blender(tmp_path / "bin" / "blender", write_result(measure_result(job)))

    result = blender.run_phase(fake_found(fake), workspace, job)

    log = read_log(fake)
    phase = workspace / "measure"
    assert log["argv"] == [
        "-b",
        "--factory-startup",
        "-noaudio",
        "--python-exit-code",
        "1",
        "--python",
        str(blender.SCRIPT),
        "--",
        str(phase / "job.json"),
    ]
    assert Path(log["cwd"]).resolve() == phase.resolve()
    assert log["listing"] == ["job.json"]
    assert json.loads(log["job"]) == job
    assert (
        blender.SCRIPT == (Path(blender.__file__).parent / "blender_script.py")
        and blender.SCRIPT.is_absolute()
    )
    assert result.mode == "measure"
    assert len(result.measurements) == 1


SHADE = {
    "technique": "cycles-ambient-occlusion",
    "samples_per_pixel": 1,
    "seed": 0,
    "pixel_filter": "BOX",
    "filter_width_px": 0.01,
    "ao_distance_m": 0.3,
    "ao_samples": 64,
    "occlusion_weight": 0.25,
    "convexity_weight": 1.0,
}
RENDER_BUFFERS = {name: f"{name}/000000.png" for name in ("color", "matid", "shade")}


def copy_buffers(tmp_path, color):
    """Fake-capture code writing the one frame's buffers: `color`, and a
    material-ID and shade buffer showing "no material" shaded 137."""
    sources = {"color": color}
    for name, pixel in (("matid", (255, 255, 0, 255)), ("shade", (137,) * 3 + (255,))):
        sources[name] = tmp_path / f"{name}.png"
        Image.new("RGBA", (8, 6), pixel).save(sources[name])
    return "import shutil\n" + "".join(
        f"pathlib.Path({name!r}).mkdir()\n"
        f"shutil.copy({str(sources[name])!r}, {RENDER_BUFFERS[name]!r})\n"
        for name in RENDER_BUFFERS
    )


def test_a_render_phase(tmp_path):
    workspace, job = make_job(tmp_path, "render")
    color = tmp_path / "color.png"
    Image.new("RGBA", (8, 6)).save(color)
    result_text = json.dumps(
        {
            "schema": "moskophoros.capture-result/1",
            "mode": "render",
            "job_sha256": job_sha256(job),
            "source_sha256": job["source"]["sha256"],
            "backend": {
                "blender": "5.2.2",
                "renderer": "workbench",
                "studio_light": "Default",
                "shade": SHADE,
            },
            "frames": [
                {"address": frame["address"], "buffers": RENDER_BUFFERS}
                for frame in job["frames"]
            ],
            "materials": [{"id": 65535, "material": None}],
        }
    )
    capture = copy_buffers(tmp_path, color) + write_result(result_text)
    fake = fake_blender(tmp_path / "bin" / "blender", capture)
    result = blender.run_phase(fake_found(fake), workspace, job)
    (buffers,) = result.buffers.values()
    assert buffers == {
        name: (workspace / "render" / path).resolve()
        for name, path in RENDER_BUFFERS.items()
    }


def test_a_relative_blender_runs_from_the_phase_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workspace, job = make_job(tmp_path)
    fake_blender(tmp_path / "bin" / "blender", write_result(measure_result(job)))
    found = blender.locate(Path("bin/blender"), environ={}, platform="linux")
    assert blender.run_phase(found, workspace, job).mode == "measure"


def test_the_phase_directory_must_be_the_job_s(tmp_path):
    workspace, job = make_job(tmp_path)
    fake = fake_blender(tmp_path / "bin" / "blender")
    with pytest.raises(MalformedJob, match="output_dir") as raised:
        blender.run_phase(fake_found(fake), tmp_path / "elsewhere", job)
    assert raised.value.exit_code == 1


@pytest.mark.parametrize(
    ("capture", "message", "stdout", "stderr"),
    [
        (
            "print('loading'); print('boom', file=sys.stderr); sys.exit(2)\n",
            "exited with status 2",
            "loading",
            "boom",
        ),
        (
            "print('no result written')\n",
            "wrote no result.json",
            "no result written",
            "",
        ),
        (
            "print('wrote junk', file=sys.stderr)\n" + write_result("{"),
            "the measure result is invalid: not JSON",
            "",
            "wrote junk",
        ),
        (
            "print('node 4 has no imported object', file=sys.stderr); sys.exit(1)\n",
            "exited with status 1",
            "",
            "node 4 has no imported object",
        ),
    ],
    ids=["nonzero exit", "missing result", "malformed result", "unmappable identity"],
)
def test_capture_failures_are_backend_errors_with_diagnostics(
    tmp_path, capture, message, stdout, stderr
):
    workspace, job = make_job(tmp_path)
    fake = fake_blender(tmp_path / "bin" / "blender", capture)
    with pytest.raises(BackendError, match=message) as raised:
        blender.run_phase(fake_found(fake), workspace, job)
    assert raised.value.exit_code == 5
    assert raised.value.stdout.strip() == stdout
    assert raised.value.stderr.strip() == stderr
    for text in (stdout, stderr):
        assert text in str(raised.value)


def test_a_launch_failure_is_a_backend_error(tmp_path):
    workspace, job = make_job(tmp_path)
    fake = executable(tmp_path / "bin" / "blender", "#!/nonexistent/interpreter\n")
    with pytest.raises(BackendError, match="could not start Blender") as raised:
        blender.run_phase(fake_found(fake), workspace, job)
    assert raised.value.exit_code == 5


def change_source(job):
    return f"pathlib.Path({job['source']['path']!r}).write_bytes(b'edited')\n"


@pytest.mark.parametrize("then", ["", "sys.exit(3)\n"], ids=["success", "failure"])
def test_a_source_changed_during_the_phase_is_an_input_error(tmp_path, then):
    workspace, job = make_job(tmp_path)
    capture = change_source(job) + write_result(measure_result(job)) + then
    fake = fake_blender(tmp_path / "bin" / "blender", capture)
    with pytest.raises(InputError, match="changed during capture") as raised:
        blender.run_phase(fake_found(fake), workspace, job)
    assert raised.value.exit_code == 3
    assert raised.value.path == Path(job["source"]["path"])


def test_a_source_changed_before_the_phase_never_starts_blender(tmp_path):
    workspace, job = make_job(tmp_path)
    Path(job["source"]["path"]).write_bytes(b"edited")
    fake = fake_blender(tmp_path / "bin" / "blender")
    with pytest.raises(InputError, match="changed during capture"):
        blender.run_phase(fake_found(fake), workspace, job)
    assert not fake.with_name("log.json").exists()


def test_an_interruption_stops_only_the_launched_process(tmp_path):
    workspace, job = make_job(tmp_path)
    ready = tmp_path / "ready"
    os.mkfifo(ready)
    capture = f"""\
import signal
with open({str(ready)!r}, "w") as fifo:
    fifo.write(str(os.getpid()))
signal.pause()
"""
    fake = fake_blender(tmp_path / "bin" / "blender", capture)
    bystander = subprocess.Popen(
        [sys.executable, "-c", "import signal; signal.pause()"]
    )
    main = threading.main_thread().ident
    launched = []

    def interrupt_when_ready():
        with open(ready) as fifo:
            launched.append(int(fifo.read()))
        signal.pthread_kill(main, signal.SIGINT)

    helper = threading.Thread(target=interrupt_when_ready)
    helper.start()
    try:
        with pytest.raises(KeyboardInterrupt):
            blender.run_phase(fake_found(fake), workspace, job)
        helper.join()
        (pid,) = launched
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)  # stopped and reaped
        assert bystander.poll() is None
        assert not (workspace / "measure" / "result.json").exists()
    finally:
        bystander.kill()
        bystander.wait()


@pytest.mark.parametrize(
    "capture",
    [
        "pathlib.Path('result.json').mkdir()\n",
        "os.mkfifo('result.json')\n",
    ],
    ids=["a directory", "a FIFO"],
)
def test_a_result_that_is_not_a_regular_file(tmp_path, capture):
    workspace, job = make_job(tmp_path)
    fake = fake_blender(
        tmp_path / "bin" / "blender", "print('made result')\n" + capture
    )
    with pytest.raises(BackendError, match="is not a regular file") as raised:
        blender.run_phase(fake_found(fake), workspace, job)
    assert raised.value.exit_code == 5
    assert raised.value.stdout.strip() == "made result"


def test_an_unreadable_result(tmp_path, monkeypatch):
    # Permissions cannot make a file unreadable to root, so the read fails
    # by substitution instead.
    workspace, job = make_job(tmp_path)
    fake = fake_blender(
        tmp_path / "bin" / "blender",
        "print('done', file=sys.stderr)\n" + write_result(measure_result(job)),
    )
    unreadable = workspace / "measure" / "result.json"
    real_read = Path.read_bytes

    def guarded_read(self):
        if self == unreadable:
            raise PermissionError(13, "Permission denied", str(self))
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(BackendError, match="cannot be read") as raised:
        blender.run_phase(fake_found(fake), workspace, job)
    assert raised.value.exit_code == 5
    assert raised.value.stderr.strip() == "done"


def test_a_result_with_a_huge_integer_bound_is_accepted(tmp_path):
    workspace, job = make_job(tmp_path)
    result = json.loads(measure_result(job))
    result["frames"][0]["bounds_m"]["L"] = 10**400
    fake = fake_blender(tmp_path / "bin" / "blender", write_result(json.dumps(result)))
    found = blender.run_phase(fake_found(fake), workspace, job)
    (measurement,) = found.measurements.values()
    assert measurement.bounds.left == 10**400


def test_an_undecodable_buffer_is_a_backend_error_with_diagnostics(tmp_path):
    # An 8-bit RGBA PNG of the right size whose trailing iCCP chunk is empty:
    # Pillow's decoder raises IndexError on it.
    from test_capture_backend import raw_png

    workspace, job = make_job(tmp_path, "render")
    color = tmp_path / "color.png"
    raw_png(color, 8, 6, 8, 6, 4, [(b"iCCP", b"")])
    result_text = json.dumps(
        {
            "schema": "moskophoros.capture-result/1",
            "mode": "render",
            "job_sha256": job_sha256(job),
            "source_sha256": job["source"]["sha256"],
            "backend": {
                "blender": "5.2.2",
                "renderer": "workbench",
                "studio_light": "Default",
                "shade": SHADE,
            },
            "frames": [
                {"address": frame["address"], "buffers": RENDER_BUFFERS}
                for frame in job["frames"]
            ],
            "materials": [{"id": 65535, "material": None}],
        }
    )
    capture = (
        "print('rendered 1 frame')\n"
        + copy_buffers(tmp_path, color)
        + write_result(result_text)
    )
    fake = fake_blender(tmp_path / "bin" / "blender", capture)
    with pytest.raises(BackendError, match="does not decode") as raised:
        blender.run_phase(fake_found(fake), workspace, job)
    assert raised.value.exit_code == 5
    assert raised.value.stdout.strip() == "rendered 1 frame"
