"""Publishing output files (export design P-9, parts 2 and 3).

Two forms share one all-or-nothing publisher. `publish` writes the files of
the positional form, each beside its target in a directory that exists.
`check_directory` and `publish_directory` write a planned export into an
output directory: the first checks the filesystem against the plan before
anything is captured, and creates nothing; the second creates the
directories the plan needs, stages every file, and replaces the targets with
the metadata file last. A failure or an interruption restores every earlier
file, removes every new one and every directory this run created that is
still empty, and says honestly what it could not undo.

The publisher takes paths and opaque bytes. It knows nothing of image
encodings, settings or the manifest's contents; the one thing it reads is the
`subject` of an existing `manifest.json`, to keep one subject to a root. It
promises nothing about crashes or concurrent writers.
"""

import errno
import json
import os
import signal
import stat
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import count
from pathlib import Path

from moskophoros.usage import UsageError

PROG = "moskophoros"
OUTPUT_ERROR = 6
MANIFEST_NAME = "manifest.json"


class OutputError(Exception):
    """An output that could not be written, such as on a full disk or without
    permission, or one whose directory changed after the check. The message
    says whether the earlier outputs are kept, or what could not be restored.
    Exit classification 6."""

    exit_code = OUTPUT_ERROR


class Interrupted(KeyboardInterrupt):
    """An interruption during publication whose rollback could not undo
    everything; the message says what is left. Exit classification 130."""


@dataclass(frozen=True)
class DirectoryTarget:
    """A checked output directory. `root` is the output root resolved once,
    `given` the path as it was given, and `paths` the planned files' paths
    relative to the root, apart from the metadata file `manifest`, which is
    published last."""

    given: Path
    root: Path
    paths: tuple[str, ...]
    manifest: str


def check_directory(root, plan, *, subject, inputs=(), reuse=None):
    """Check the filesystem against `plan` for the output directory `root`,
    before anything is captured; return the `DirectoryTarget`. Nothing is
    created.

    `plan` has `artifacts` and `manifest`, as `outputs.OutputPlan` does: each
    an output with a relative `/`-separated `path`. `subject` is the run's
    subject, the input's file stem. `inputs` are the paths of every file the
    run reads, and `reuse` is the settings document it read completely and
    closed, which may be replaced.

    `root` may be an existing directory, or a missing one whose parent is a
    directory, or a link to a directory; its ancestors may be links. Below
    the resolved root no existing link may be an output or on the way to one,
    no target may be a directory or other non-regular file, no output may be
    an input, and an existing `manifest.json` must belong to `subject`. A
    refusal is a `UsageError` naming the path and the reason; a filesystem
    failure while checking is an `OutputError`.
    """
    given = Path(root)
    resolved = _resolve_root(given)
    paths = tuple(output.path for output in plan.artifacts)
    manifest = plan.manifest.path
    targets = {}
    for path in (*paths, manifest):
        targets[path] = resolved.joinpath(*_parts(path))
    for path in targets:
        problem = _component_problem(resolved, _parts(path))
        if problem:
            raise UsageError(
                f"the output {str(targets[path])!r} cannot be written: "
                f"{problem[0]!r} {problem[1]}"
            )
    _check_overlap(targets, inputs, reuse)
    _check_subject(targets[manifest], subject)
    return DirectoryTarget(given, resolved, paths, manifest)


def publish_directory(target, artifacts, manifest):
    """Publish `artifacts`, `(relative path, bytes)` pairs for exactly the
    planned paths of `target` (from `check_directory`), and then `manifest`,
    the bytes of its metadata file.

    The directories the paths need are created first, every file is staged
    beside its target, and then the targets are replaced one by one, the
    metadata file last. Components are checked again before anything changes;
    one that became a link or the wrong kind of file is an `OutputError`.
    On failure everything is undone as `publish` does, and the directories
    this run created are removed if they are empty. Files the plan does not
    list are never touched.
    """
    artifacts = [(path, data) for path, data in artifacts]
    given = sorted(path for path, _ in artifacts)
    if given != sorted(target.paths):
        raise ValueError("the published paths are not the planned paths")
    outputs = [(target.root.joinpath(*_parts(path)), data) for path, data in artifacts]
    outputs.append((target.root.joinpath(*_parts(target.manifest)), manifest))
    _Publication(outputs, target).run()


def publish(outputs):
    """Write each `(path, bytes)` in `outputs`, all or nothing.

    Every output is first written to a temporary file beside its target.
    Then, target by target, an existing file is moved aside and the new one
    renamed into place. If anything fails or is interrupted before every
    output is in place, each output placed is removed, each earlier file is
    moved back, and the error propagates. Once every output is in place the
    publication is complete: the earlier files are deleted, and an
    interruption then no longer stops the run. Nothing else in the output
    directories is touched. A target that is a link is moved aside and
    replaced by a regular file, never followed.

    While publishing, an interruption is deferred to the next step, so no
    rename is ever left out of the record the rollback reads, and the
    rollback itself runs to the end. A failure to write is an `OutputError`
    naming the output and the reason. When a rollback step fails, the
    error names each target left unrestored and the backup that holds its
    earlier file, and does not say the earlier outputs are kept.
    """
    _Publication([(Path(target), data) for target, data in outputs], None).run()


class _Publication:
    """One publication: the record of what has changed, which the rollback
    reads. `directory` is the `DirectoryTarget`, in the directory form."""

    def __init__(self, outputs, directory):
        self.outputs = outputs
        self.directory = directory
        self.interrupted = []
        self.made = []  # directories this run created, in order
        self.staged = []  # (target, temporary file)
        self.moved = []  # (target, where its earlier file was moved)
        self.placed = []  # (target, temporary file renamed to it)
        self.doing = ("write", None)

    def run(self):
        with _deferred_interrupts(self.interrupted):
            try:
                self._place()
            except BaseException as failure:
                problems = self._roll_back()
                error = self._failure(failure, problems)
                if error is failure:
                    raise
                raise error from None
            for target, backup in self.moved:
                try:
                    reason = self._unsafe(backup)
                    if reason:
                        raise OSError(0, reason)
                    os.remove(backup)
                except OSError as error:
                    _warn(
                        f"the earlier {str(target)!r} could not be deleted from "
                        f"{str(backup)!r}: {error.strerror or error}"
                    )

    def _place(self):
        stop = self.interrupted
        if self.directory is not None:
            self._recheck()
            self._make_directories()
        for target, data in self.outputs:
            _stop_if(stop)
            self.doing = ("write", target)
            _stage(
                target,
                data,
                lambda path, target=target: self.staged.append((target, path)),
            )
        if self.directory is not None:
            _stop_if(stop)
            self._recheck()
        for target, temporary in self.staged:
            _stop_if(stop)
            self.doing = ("write", target)
            if _exists(target):
                backup = _unused_name(target, "earlier")
                # Recorded first: the rollback checks which renames happened.
                self.moved.append((target, backup))
                os.replace(target, backup)
            self.placed.append((target, temporary))
            os.replace(temporary, target)
        _stop_if(stop)

    def _recheck(self):
        """Refuse, as an output error, a root or component that is no longer
        what `check_directory` accepted."""
        directory = self.directory
        root = directory.root
        where = str(directory.given)
        if Path(os.path.realpath(directory.given)) != root:
            raise OutputError(
                f"the output directory {where!r} no longer resolves to {str(root)!r}"
            )
        if _exists(root) and (os.path.islink(root) or not root.is_dir()):
            raise OutputError(
                f"the output directory {where!r} is no longer a directory"
            )
        for path in (*directory.paths, directory.manifest):
            problem = _component_problem(root, _parts(path))
            if problem:
                raise OutputError(
                    f"the output {str(root.joinpath(*_parts(path)))!r} changed after "
                    f"it was checked: {problem[0]!r} {problem[1]}"
                )

    def _make_directories(self):
        root = self.directory.root
        wanted = [root]
        for target, _ in self.outputs:
            parts = target.relative_to(root).parts
            wanted += [root.joinpath(*parts[:n]) for n in range(1, len(parts))]
        for path in wanted:
            _stop_if(self.interrupted)
            self.doing = ("create the directory", path)
            if _exists(path):
                continue
            self.made.append(path)
            try:
                os.mkdir(path)
            except OSError:
                # Not created: nothing else raises between the call and here.
                self.made.pop()
                raise

    def _unsafe(self, path):
        """Why `path` must not be touched, or None: in the directory form,
        the root or a directory above `path` is a link, or the lookup that
        would show it failed. Cleanup must not follow a link, or act where
        confinement cannot be established."""
        if self.directory is None:
            return None
        root = self.directory.root
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            return "it is outside the output directory"
        current = root
        for part in ("", *parts[:-1]):
            current = current / part if part else current
            try:
                linked = stat.S_ISLNK(os.lstat(current).st_mode)
            except (FileNotFoundError, NotADirectoryError):
                return None  # nothing there to follow
            except OSError as error:
                return f"its directory could not be checked: {error.strerror or error}"
            if linked:
                return "its directory is now a link"
        return None

    def _roll_back(self):
        """Undo a partial publication: remove each output whose rename into
        place happened, move each earlier file that was moved aside back,
        remove the temporary files, then the directories this run created
        that are empty. A step that fails is recorded, and the rest still
        run. Return the `_Problems`."""
        problems = _Problems()
        unremoved = {}
        for target, temporary in reversed(self.placed):
            try:
                if _exists(temporary):
                    continue  # its rename never happened
            except OSError:
                # Cannot tell. If nothing was placed there is nothing to
                # remove, and the removal below finds none.
                pass
            try:
                reason = self._unsafe(target)
                if reason:
                    raise OSError(0, reason)
                os.remove(target)
            except FileNotFoundError:
                pass
            except OSError as error:
                unremoved[target] = (
                    f"the new {str(target)!r} could not be removed: "
                    f"{error.strerror or error}"
                )
        for target, backup in reversed(self.moved):
            try:
                reason = self._unsafe(target)
                if reason:
                    raise OSError(0, reason)
                os.replace(backup, target)
                unremoved.pop(target, None)
            except OSError as error:
                if isinstance(error, FileNotFoundError) and _gone(backup):
                    continue  # its rename never happened
                problems.restore.append(
                    f"the earlier {str(target)!r} could not be restored and is "
                    f"kept at {str(backup)!r}: {error.strerror or error}"
                )
        problems.restore += unremoved.values()
        for _, temporary in self.staged:
            try:
                reason = self._unsafe(temporary)
                if reason:
                    raise OSError(0, reason)
                os.remove(temporary)
            except FileNotFoundError:
                pass
            except OSError as error:
                problems.cleanup.append(
                    f"the temporary file {str(temporary)!r} could not be "
                    f"removed: {error.strerror or error}"
                )
        for path in reversed(self.made):
            try:
                reason = self._unsafe(path)
                if reason:
                    raise OSError(0, reason)
                os.rmdir(path)
            except OSError as error:
                if error.errno not in (errno.ENOTEMPTY, errno.ENOENT):
                    problems.cleanup.append(
                        f"the new directory {str(path)!r} could not be "
                        f"removed: {error.strerror or error}"
                    )
        return problems

    def _failure(self, failure, problems):
        """The exception to raise for `failure` after the rollback: `failure`
        itself when it is not one this module classifies."""
        tail = problems.tail()
        if isinstance(failure, OSError):
            verb, path = self.doing
            return OutputError(
                f"cannot {verb} {str(path)!r}: {failure.strerror or failure}; {tail}"
            )
        if isinstance(failure, OutputError):
            return OutputError(f"{failure}; {tail}")
        if isinstance(failure, KeyboardInterrupt) and not isinstance(
            failure, Interrupted
        ):
            if problems.restore or problems.cleanup:
                return Interrupted(f"interrupted; {tail}")
        return failure


@dataclass
class _Problems:
    """What a rollback could not undo: `restore` the targets left holding
    new content or without their earlier file, `cleanup` the temporary files
    and directories left behind."""

    restore: list
    cleanup: list

    def __init__(self):
        self.restore = []
        self.cleanup = []

    def tail(self):
        if self.restore:
            return "rolling back failed: " + "; ".join(self.restore + self.cleanup)
        if self.cleanup:
            return "earlier outputs are kept, but " + "; ".join(self.cleanup)
        return "earlier outputs are kept"


def _parts(path):
    """The components of a planned relative `path`, which the plan has
    already validated; anything that could leave the root is a bug."""
    parts = path.split("/")
    if path.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"not a path inside the output directory: {path!r}")
    return parts


def _resolve_root(given):
    shown = str(given)
    resolved = Path(os.path.realpath(given))
    try:
        present = _exists(given)
    except OSError as error:
        raise OutputError(
            f"cannot check the output directory {shown!r}: {error.strerror or error}"
        ) from None
    if present:
        if not resolved.is_dir():
            if os.path.islink(given):
                raise UsageError(
                    f"the output directory {shown!r} is a link to "
                    f"{str(resolved)!r}, which is not a directory"
                )
            raise UsageError(f"the output directory {shown!r} is not a directory")
        return resolved
    if not resolved.parent.is_dir():
        raise UsageError(
            f"the output directory {shown!r} cannot be created: its parent "
            f"{str(resolved.parent)!r} is not a directory"
        )
    return resolved


def _component_problem(root, parts):
    """The first component of `parts` below `root` that cannot be used, as
    `(path, reason)`, or None. A component that does not exist yet is fine,
    and so is everything below it."""
    current = root
    last = len(parts) - 1
    for index, part in enumerate(parts):
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            return None
        except OSError as error:
            raise OutputError(
                f"cannot check {str(current)!r}: {error.strerror or error}"
            ) from None
        if stat.S_ISLNK(mode):
            return str(current), "is a symbolic link"
        if index < last:
            if not stat.S_ISDIR(mode):
                return str(current), "is not a directory"
        elif stat.S_ISDIR(mode):
            return str(current), "is a directory"
        elif not stat.S_ISREG(mode):
            return str(current), "is not a regular file"
    return None


def _identity(path):
    try:
        status = os.stat(path)
    except OSError:
        return None
    return status.st_dev, status.st_ino


def _check_overlap(targets, inputs, reuse):
    """Refuse an output that is a file the run reads, other than the reuse
    document, which was read completely and closed."""
    exempt = None if reuse is None else _identity(reuse)
    existing = {}
    for target in targets.values():
        try:
            status = os.lstat(target)
        except OSError:
            continue
        existing[(status.st_dev, status.st_ino)] = target
    for source in inputs:
        identity = _identity(source)
        if identity is None or identity == exempt:
            continue
        if identity in existing:
            raise UsageError(
                f"the output {str(existing[identity])!r} is also an input "
                f"({str(source)!r}), which the run reads"
            )


def _check_subject(manifest, subject):
    """Refuse an existing `manifest` that does not name `subject`."""
    data = _read_regular(manifest)
    if data is None:
        return
    shown = str(manifest)
    try:
        document = json.loads(data)
    except (ValueError, RecursionError) as error:
        raise UsageError(
            f"{shown!r} is not valid JSON ({error}), so the subject it belongs "
            "to is unknown; give another output directory or remove the file"
        ) from None
    if not isinstance(document, dict) or "subject" not in document:
        raise UsageError(
            f"{shown!r} has no subject, so the subject it belongs to is unknown; "
            "give another output directory or remove the file"
        )
    found = document["subject"]
    if not isinstance(found, str):
        raise UsageError(
            f"{shown!r} has a subject that is not a string, so the subject it "
            "belongs to is unknown; give another output directory or remove the file"
        )
    if found != subject:
        raise UsageError(
            f"{shown!r} belongs to the subject {found!r}, not {subject!r}; an "
            "output directory holds one subject's export, so give another"
        )


def _read_regular(path):
    """The bytes of the regular file `path`, or None if it is absent. A link
    is not followed, and a file that is not regular is not opened to read:
    that would block on a FIFO, or reach outside the root."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise OutputError(
            f"cannot read {str(path)!r}: {error.strerror or error}"
        ) from None
    try:
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise UsageError(f"{str(path)!r} is not a regular file")
            return handle.read()
    except OSError as error:
        raise OutputError(
            f"cannot read {str(path)!r}: {error.strerror or error}"
        ) from None


def _warn(message):
    sys.stderr.write(f"{PROG}: warning: {message}\n")


@contextmanager
def _deferred_interrupts(received):
    """Record Ctrl-C in `received` instead of raising it, in the main thread,
    where Python delivers signals."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.signal(
        signal.SIGINT, lambda signum, frame: received.append(signum)
    )
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _stop_if(interrupted):
    if interrupted:
        raise KeyboardInterrupt


def _stage(target, data, record):
    """Write `data` to a new temporary file beside `target`, calling
    `record(path)` as soon as the file exists, so a failed write leaves it in
    the rollback's record rather than to a cleanup of its own.

    It is created like any new file, so the umask sets its permissions.
    """
    path = _unused_name(target, "new")
    handle = open(path, "xb")
    record(path)
    with handle:
        handle.write(data)


def _exists(path):
    """Whether anything, a dangling link included, is at `path`. Unlike
    `os.path.lexists`, a lookup that fails for another reason raises, instead
    of answering that nothing is there."""
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def _gone(path):
    """Whether `path` is confirmed absent: a failed lookup is not."""
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return True
    except OSError:
        return False
    return False


def _unused_name(target, purpose):
    """A name beside `target`, hidden and unused, for a `purpose` file."""
    for n in count():
        path = target.with_name(f".{target.name}.{PROG}-{purpose}-{os.getpid()}-{n}")
        if not _exists(path):
            return path
