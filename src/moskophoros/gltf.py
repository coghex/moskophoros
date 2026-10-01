"""Read a `.glb` file's subject scene and clips, without Blender.

Implements design §Input contract, §Clips and sampling and §Root motion for
the structure the tool itself relies on. Every other glTF rule is left to
Blender's importer.
"""

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

INPUT_ERROR = 3
STATIC_CLIP = "static"

_MAGIC = b"glTF"
_HEADER = struct.Struct("<4sII")
_CHUNK_HEADER = struct.Struct("<II")
_JSON_CHUNK = 0x4E4F534A


class InputError(Exception):
    """A problem with the input file: exit classification 3."""

    exit_code = INPUT_ERROR

    def __init__(self, path, problem):
        super().__init__(f"{path}: {problem}")
        self.path = path
        self.problem = problem


@dataclass(frozen=True)
class Root:
    """A clip's candidate root. Names are diagnostics, never identities."""

    node_index: int
    node_name: str | None


@dataclass(frozen=True)
class Clip:
    """One animation, or the synthetic `static` clip (no animation index)."""

    animation_index: int | None
    name: str
    t0: float
    t1: float
    roots: tuple[Root, ...]


@dataclass(frozen=True)
class Subject:
    path: Path
    name: str
    scene_index: int
    clips: tuple[Clip, ...]


@dataclass(frozen=True)
class SelectedClip:
    clip: Clip
    one_shot: bool


def read_glb(path):
    """Read the subject at `path`, raising `InputError` for a bad file."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise InputError(path, f"cannot be read: {error.strerror or error}") from None
    return _Reader(path, _document(path, data)).subject()


def select_clips(subject, clip_names, once_names):
    """Select clips by `--clip` and mark them by `--once`, given as names.

    The option parser rejects a name repeated within either list and, with
    `--clip`, a `--once` outside it (usage errors); here they are bugs.
    """
    clip_names = list(clip_names)
    once_names = list(once_names)
    for option, names in (("--clip", clip_names), ("--once", once_names)):
        if len(set(names)) != len(names):
            raise ValueError(f"{option} repeats a name: {names!r}")
    by_name = {clip.name: clip for clip in subject.clips}
    for name in clip_names + once_names:
        if name not in by_name:
            raise InputError(subject.path, f"no clip is named {name!r}")
    if clip_names:
        unselected = [name for name in once_names if name not in clip_names]
        if unselected:
            raise ValueError(f"--once names unselected clips: {unselected!r}")
        clips = [by_name[name] for name in clip_names]
    else:
        clips = subject.clips
    once = set(once_names)
    return tuple(SelectedClip(clip, clip.name in once) for clip in clips)


def _document(path, data):
    """Check the binary glTF 2.0 container and decode its JSON chunk."""
    if len(data) < _HEADER.size:
        raise InputError(path, "is not binary glTF: shorter than its header")
    magic, version, length = _HEADER.unpack_from(data)
    if magic != _MAGIC:
        raise InputError(path, "is not binary glTF: wrong magic")
    if version != 2:
        raise InputError(path, f"is not binary glTF 2.0: container version {version}")
    if length != len(data):
        raise InputError(
            path,
            f"has an inconsistent length: the header says {length} bytes, "
            f"the file has {len(data)}",
        )
    chunks = []
    offset = _HEADER.size
    while offset < length:
        if length - offset < _CHUNK_HEADER.size:
            raise InputError(
                path,
                f"has an inconsistent length: a chunk header at byte {offset} is cut off",
            )
        chunk_length, chunk_type = _CHUNK_HEADER.unpack_from(data, offset)
        start = offset + _CHUNK_HEADER.size
        if chunk_length > length - start:
            raise InputError(
                path,
                f"has an inconsistent length: the chunk at byte {offset} runs past the end",
            )
        chunks.append((chunk_type, data[start : start + chunk_length]))
        offset = start + chunk_length
    if not chunks or chunks[0][0] != _JSON_CHUNK:
        raise InputError(path, "is not binary glTF: it has no JSON chunk first")
    try:
        document = json.loads(
            chunks[0][1].decode("utf-8"), parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise InputError(path, f"has an undecodable JSON chunk: {error}") from None
    if not isinstance(document, dict):
        raise InputError(path, "has an undecodable JSON chunk: it is not an object")
    return document


def _reject_constant(constant):
    raise ValueError(f"{constant} is not a JSON number")


def _is_index(value):
    return isinstance(value, int) and not isinstance(value, bool)


class _Reader:
    def __init__(self, path, document):
        self.path = path
        self.document = document

    def fail(self, problem):
        raise InputError(self.path, problem)

    def array(self, owner, key, what):
        """`owner[key]` as a list: empty when absent, but never when null."""
        if key not in owner:
            return []
        value = owner[key]
        if not isinstance(value, list):
            self.fail(f"{what} is not an array")
        return value

    def obj(self, value, what):
        if not isinstance(value, dict):
            self.fail(f"{what} is not an object")
        return value

    def objects(self, values, what):
        return [self.obj(value, f"{what} {i}") for i, value in enumerate(values)]

    def index(self, value, count, what, target):
        if value is None:
            self.fail(f"{what} names no {target}")
        if not _is_index(value) or not 0 <= value < count:
            self.fail(f"{what} names {target} {value!r}, which does not exist")
        return value

    def subject(self):
        scenes = self.array(self.document, "scenes", "scenes")
        if not scenes:
            self.fail("has no scenes")
        nodes = self.objects(self.array(self.document, "nodes", "nodes"), "node")
        scene_index = self.document.get("scene", 0)
        self.index(scene_index, len(scenes), "the scene property", "scene")
        for i, scene in enumerate(self.objects(scenes, "scene")):
            for node in self.array(scene, "nodes", f"scene {i}'s nodes"):
                self.index(node, len(nodes), f"scene {i}", "node")
        parents = self.parents(nodes)
        names = []
        for i, node in enumerate(nodes):
            name = node.get("name")
            if "name" in node and not isinstance(name, str):
                self.fail(f"node {i}'s name is not a string")
            names.append(name)
        accessors = self.array(self.document, "accessors", "accessors")
        animations = self.array(self.document, "animations", "animations")
        if animations:
            clips = self.clips(animations, accessors, len(nodes), parents, names)
        else:
            clips = (Clip(None, STATIC_CLIP, 0.0, 0.0, ()),)
        return Subject(self.path, self.path.stem, scene_index, clips)

    def parents(self, nodes):
        """Map each child to its parent, failing unless the nodes form a forest."""
        parent = {}
        for i, node in enumerate(nodes):
            for child in self.array(node, "children", f"node {i}'s children"):
                self.index(child, len(nodes), f"node {i}", "child node")
                if child in parent:
                    self.fail(
                        f"has a node hierarchy that is not a forest: node {child} "
                        f"has two parents, nodes {parent[child]} and {i}"
                    )
                parent[child] = i
        reaches_root = set()
        for start in parent:
            path = set()
            node = start
            while node in parent and node not in reaches_root:
                if node in path:
                    self.fail(
                        "has a node hierarchy that is not a forest: "
                        f"node {node} is in a cycle"
                    )
                path.add(node)
                node = parent[node]
            reaches_root.update(path)
        return parent

    def clips(self, animations, accessors, node_count, parents, node_names):
        clips = []
        first_index = {}
        for i, animation in enumerate(self.objects(animations, "animation")):
            name = animation.get("name")
            if name is None or name == "":
                self.fail(f"animation {i} has no name")
            if not isinstance(name, str):
                self.fail(f"animation {i}'s name is not a string")
            if name in first_index:
                self.fail(
                    f"animation {i} is named {name!r}, "
                    f"like animation {first_index[name]}"
                )
            first_index[name] = i
            samplers = self.array(animation, "samplers", f"animation {i}'s samplers")
            if not samplers:
                self.fail(f"animation {i} has no samplers")
            ranges = [
                self.sampler_range(i, s, sampler, accessors)
                for s, sampler in enumerate(samplers)
            ]
            targeted, translated = self.targets(i, animation, len(samplers), node_count)
            roots = tuple(
                Root(node, node_names[node])
                for node in sorted(translated)
                if not _has_ancestor_in(node, parents, targeted)
            )
            t0 = min(low for low, _ in ranges)
            t1 = max(high for _, high in ranges)
            clips.append(Clip(i, name, t0, t1, roots))
        return tuple(clips)

    def sampler_range(self, animation, s, sampler, accessors):
        what = f"animation {animation}'s sampler {s}"
        sampler = self.obj(sampler, what)
        input_index = self.index(sampler.get("input"), len(accessors), what, "accessor")
        accessor = self.obj(accessors[input_index], f"accessor {input_index}")
        bounds = []
        for key in ("min", "max"):
            value = accessor.get(key)
            number = None
            if isinstance(value, list) and len(value) == 1:
                number = _finite(value[0])
            if number is None:
                self.fail(
                    f"{what} has input accessor {input_index}, which lacks a "
                    f"one-element, finite {key!r}"
                )
            bounds.append(number)
        low, high = bounds
        if low > high:
            self.fail(
                f"{what} has input accessor {input_index}, whose min {low} "
                f"exceeds its max {high}"
            )
        return low, high

    def targets(self, i, animation, sampler_count, node_count):
        """Return the nodes animation `i` targets, and those it translates."""
        targeted = set()
        translated = set()
        channels = self.array(animation, "channels", f"animation {i}'s channels")
        for c, channel in enumerate(self.objects(channels, f"animation {i}'s channel")):
            what = f"animation {i}'s channel {c}"
            self.index(channel.get("sampler"), sampler_count, what, "sampler")
            target = self.obj(channel.get("target"), f"{what}'s target")
            path = target.get("path")
            if not isinstance(path, str):
                self.fail(f"{what}'s target path is not a string")
            if "node" not in target:
                continue
            node = self.index(target["node"], node_count, what, "target node")
            targeted.add(node)
            if path == "translation":
                translated.add(node)
        return targeted, translated


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _has_ancestor_in(node, parents, nodes):
    while node in parents:
        node = parents[node]
        if node in nodes:
            return True
    return False
