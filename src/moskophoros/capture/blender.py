"""Find Blender, check its version and run one capture phase.

Follows design §Capture, §Supported Blender version and §Capture job and
result contract. Blender always runs headless, as its own process, in a phase
directory this module creates. There is no timeout: a phase waits for Blender
to finish or fail, or for the caller to be interrupted.

A script that cannot map an original animation or node index to imported
state reports it by failing, with its message on stderr; like any nonzero
exit, that is a `BackendError` carrying the captured output.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from moskophoros.capture.backend import BackendError, MalformedJob, validate_result
from moskophoros.gltf import InputError

# The supported series. Design §Supported Blender version is its one record;
# a test checks that this agrees with it.
SUPPORTED_SERIES = (5, 2)
MACOS_APP = Path("/Applications/Blender.app/Contents/MacOS/Blender")
SCRIPT = Path(__file__).with_name("blender_script.py")
ENVIRONMENT_VARIABLE = "MOSKOPHOROS_BLENDER"

# The first line of `blender --version`, such as "Blender 5.2.2 LTS".
_VERSION_LINE = re.compile(r"Blender (\d+)\.(\d+)(?:\.(\d+))?(?:\s.*)?")


@dataclass(frozen=True)
class Blender:
    """A usable Blender: its absolute path, how it was found, its version."""

    path: Path
    source: str
    version: str


def find_blender(option=None, environ=None, platform=None, macos_app=MACOS_APP):
    """Find Blender: `--blender`, `$MOSKOPHOROS_BLENDER`, `blender` on PATH,
    then the macOS application.

    Returns the absolute path and the source that named it. The first
    source that is set decides: an unusable `--blender` or environment
    variable is a `BackendError`, and later sources are not tried.
    """
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    configured = [
        ("--blender", None if option is None else str(option)),
        (f"${ENVIRONMENT_VARIABLE}", environ.get(ENVIRONMENT_VARIABLE) or None),
    ]
    for source, path in configured:
        if path is not None:
            if not _is_executable(path):
                raise BackendError(
                    f"{source} names {path!r}, which is not an executable file; "
                    "no other Blender is tried"
                )
            return Path(os.path.abspath(path)), source
    search_path = environ.get("PATH", os.defpath)
    found = shutil.which("blender", path=search_path)
    if found:
        return Path(os.path.abspath(found)), "PATH"
    looked = [
        "--blender (not given)",
        f"${ENVIRONMENT_VARIABLE} (unset or empty)",
        f"blender on PATH ({search_path})",
    ]
    if platform == "darwin":
        if _is_executable(macos_app):
            return Path(os.path.abspath(macos_app)), "the macOS application"
        looked.append(str(macos_app))
    raise BackendError("Blender was not found. Looked at: " + "; ".join(looked))


def _is_executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def parse_version(line):
    """The version in `blender --version`'s first line, or None."""
    match = _VERSION_LINE.fullmatch(line.strip())
    if match is None:
        return None
    return ".".join(part for part in match.groups() if part is not None)


def check_version(path, any_blender=False):
    """Run `path --version` and return its version.

    A failed probe or unparseable output is a `BackendError`, even with
    `any_blender`. A series other than the supported one is a `BackendError`
    unless `any_blender` is given.
    """
    stdout, stderr, status = _run([str(path), "--version"], cwd=None)
    if status is None:
        raise BackendError(f"could not run {path} --version: {stderr}")
    if status != 0:
        raise BackendError(
            f"{path} --version exited with status {status}", stdout, stderr
        )
    first = stdout.splitlines()[0] if stdout.splitlines() else ""
    version = parse_version(first)
    if version is None:
        raise BackendError(
            f"{path} --version did not report a version; its first line is {first!r}",
            stdout,
            stderr,
        )
    series = tuple(int(part) for part in version.split(".")[:2])
    if series != SUPPORTED_SERIES and not any_blender:
        supported = ".".join(map(str, SUPPORTED_SERIES))
        raise BackendError(
            f"{path} is Blender {version}, but {supported} is supported; "
            "give --any-blender to use it anyway"
        )
    return version


def locate(option=None, any_blender=False, environ=None, platform=None):
    """Find Blender and check its version."""
    path, source = find_blender(option, environ, platform)
    return Blender(path, source, check_version(path, any_blender))


def command(blender, job_path):
    """The exact headless command line for one phase."""
    return [
        str(blender.path),
        "-b",
        "--factory-startup",
        "-noaudio",
        "--python-exit-code",
        "1",
        "--python",
        str(SCRIPT),
        "--",
        str(job_path),
    ]


def run_phase(blender, workspace, job):
    """Run `job` in its own phase directory inside `workspace`.

    The phase directory, `workspace/<mode>`, must be the job's `output_dir`;
    it is created empty and given `job.json` before Blender starts. The
    source is checked against the job's digest before and after Blender
    runs: a change is an `InputError`, even when Blender also failed. Any
    capture failure is a `BackendError` with Blender's output; nothing is
    retried. On interruption, only the Blender this started is stopped, and
    the interruption propagates.
    """
    mode = job["mode"]
    phase_dir = Path(workspace) / mode
    if not phase_dir.is_absolute() or str(phase_dir) != job["output_dir"]:
        raise MalformedJob(
            f"the job's output_dir {job['output_dir']!r} is not {str(phase_dir)!r}"
        )
    phase_dir.mkdir()
    job_path = phase_dir / "job.json"
    job_path.write_text(_job_text(job), encoding="utf-8")

    source = Path(job["source"]["path"])
    _check_source(source, job["source"]["sha256"])
    stdout, stderr, status = _run(command(blender, job_path), cwd=phase_dir)
    _check_source(source, job["source"]["sha256"])

    if status is None:
        raise BackendError(f"could not start Blender at {blender.path}: {stderr}")
    if status != 0:
        raise BackendError(
            f"Blender's {mode} phase exited with status {status}", stdout, stderr
        )
    result_path = phase_dir / "result.json"
    if not result_path.exists():
        raise BackendError(
            f"Blender's {mode} phase wrote no result.json", stdout, stderr
        )
    if not result_path.is_file():
        raise BackendError(
            f"Blender's {mode} phase result.json is not a regular file", stdout, stderr
        )
    try:
        data = result_path.read_bytes()
    except OSError as error:
        raise BackendError(
            f"Blender's {mode} phase result.json cannot be read: {error}",
            stdout,
            stderr,
        ) from None
    try:
        return validate_result(job, phase_dir, data)
    except BackendError as error:
        raise BackendError(error.message, stdout, stderr) from None


def _job_text(job):
    return json.dumps(job, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _check_source(path, sha256):
    try:
        data = path.read_bytes()
    except OSError as error:
        raise InputError(path, f"cannot be read: {error.strerror or error}") from None
    if hashlib.sha256(data).hexdigest() != sha256:
        raise InputError(path, "changed during capture; run again on the final file")


def _run(argv, cwd):
    """Run `argv` to completion, returning its decoded stdout, stderr and status.

    A launch failure returns a None status with the error as stderr. On any
    interruption, the process is killed and reaped before it propagates.
    """
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return "", str(error), None
    try:
        stdout, stderr = process.communicate()
    except BaseException:
        process.kill()
        process.wait()
        raise
    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        process.returncode,
    )
