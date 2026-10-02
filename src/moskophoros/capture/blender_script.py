"""Run one capture phase inside Blender: `blender ... --python <this> -- <job.json>`.

This is the only module that imports `bpy`, and nothing in the package
imports it. It runs under Blender's bundled Python and uses only `bpy` and
the standard library. It follows design §Capture, §Capture job and result
contract, §Clips and sampling, §Root motion, §Scale and ground point and
§Camera and directions.

Measure mode reports bounds, heights and root travel; render mode renders
each frame with the accepted Workbench settings. Both share the import,
subject selection, identity mapping and clip isolation below.

Identity mapping: the script imports a private copy of the source in which
every node is renamed `moskophoros.node.<index>` and every animation
`moskophoros.animation.<index>`. Every mesh node gets its own copy of its
mesh, named `moskophoros.mesh.<mesh>.node.<node>.data`, whose morph targets
are named `moskophoros.target.<index>`. Skins, cameras, lights and scenes are renamed
into namespaces of their own, so no name from the file reaches Blender and
nothing the importer creates can take a node's name. Blender names objects
and bones after nodes, mesh data after meshes, shape keys after targets and
actions after animations, so original indices map exactly, whatever the
original names, and an index with no imported counterpart fails by name. The
subject is found by mesh data, which names its node, because Blender moves
some meshes, such as a skinned mesh with animated morph weights, into an
object of their own.

Static state: the importer makes the first animation active, and Blender
evaluates it, so its channels would no longer hold the file's static values.
The copy therefore starts with a synthetic animation of one synthetic empty
node, which moves nothing. Every object transform, pose bone transform and
shape key value is recorded right after import and restored before each clip.

A failure prints `moskophoros: error: <message>` to stderr and exits 1,
writing no result.
"""

import hashlib
import json
import math
import os
import re
import struct
import sys
import tempfile
import urllib.parse
from array import array

import bpy

JOB_SCHEMA = "moskophoros.capture-job/1"
RESULT_SCHEMA = "moskophoros.capture-result/1"
NODE_NAME = "moskophoros.node.{}"
ANIMATION_NAME = "moskophoros.animation.{}"
# Not ending in digits: Blender would read those as its own ".001" suffix
# when it duplicates mesh data.
MESH_NAME = "moskophoros.mesh.{}.node.{}.data"
TARGET_NAME = "moskophoros.target.{}"
PLACEHOLDER = "moskophoros.placeholder"
_MESH_DATA = re.compile(r"moskophoros\.mesh\.\d+\.node\.(\d+)\.data(?:\.\d+)?")
_MESH_WEIGHTS = re.compile(r"/meshes/\d+/weights")
_TARGET_PATH = re.compile(r'key_blocks\["moskophoros\.target\.(\d+)"\]\.value')

_SHA256 = re.compile(r"[0-9a-f]{64}")
_GLB_HEADER = struct.Struct("<4sII")
_CHUNK_HEADER = struct.Struct("<II")
_JSON_CHUNK = 0x4E4F534A


class ScriptError(Exception):
    pass


# The job


def load_job(path):
    """Parse `path` strictly: no duplicate keys and only finite numbers."""

    def pairs(items):
        document = {}
        for key, value in items:
            if key in document:
                raise ScriptError(f"the job has a duplicate key {key!r}")
            document[key] = value
        return document

    def constant(name):
        raise ScriptError(f"the job has a non-finite number {name}")

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ScriptError(f"the job has a non-finite number {text}")
        return value

    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(
                handle,
                object_pairs_hook=pairs,
                parse_constant=constant,
                parse_float=number,
            )
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as error:
        raise ScriptError(f"cannot read the job {path}: {error}") from None


def _fields(value, keys, where):
    if not isinstance(value, dict):
        raise ScriptError(f"the job's {where} is not an object")
    missing = [key for key in keys if key not in value]
    unknown = [key for key in value if key not in keys]
    if missing or unknown:
        raise ScriptError(
            f"the job's {where} is missing {missing} or has unknown {unknown}"
        )
    return value


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, float) and math.isfinite(value))


def _require(condition, message):
    if not condition:
        raise ScriptError(f"the job is invalid: {message}")


def check_job(job):
    """Check the job's structure before anything is imported."""
    _fields(
        job,
        [
            "schema",
            "mode",
            "source",
            "subject",
            "variant",
            "settings",
            "clips",
            "frames",
            "output_dir",
        ],
        "top level",
    )
    _require(job["schema"] == JOB_SCHEMA, f"schema {job['schema']!r}")
    _require(job["mode"] in ("measure", "render"), f"mode {job['mode']!r}")
    source = _fields(job["source"], ["path", "sha256", "scene"], "source")
    _require(
        isinstance(source["path"], str) and os.path.isabs(source["path"]),
        "source.path is not absolute",
    )
    _require(
        isinstance(source["sha256"], str) and _SHA256.fullmatch(source["sha256"]),
        "source.sha256 is not a digest",
    )
    _require(_is_int(source["scene"]) and source["scene"] >= 0, "source.scene")
    for key in ("subject", "variant"):
        _require(isinstance(job[key], str) and job[key], f"{key} is not a name")
    _require(
        isinstance(job["output_dir"], str) and os.path.isabs(job["output_dir"]),
        "output_dir is not absolute",
    )

    settings = _fields(
        job["settings"],
        [
            "view",
            "model_yaw_deg",
            "fps",
            "supersample",
            "pixels_per_meter",
            "cell",
            "ground_m",
            "ground_px",
            "root_motion",
            "clips",
        ],
        "settings",
    )
    view = _fields(
        settings["view"],
        ["preset", "projection", "pitch_deg", "directions", "start_angle_deg"],
        "settings.view",
    )
    _require(isinstance(view["preset"], str) and view["preset"], "the view preset")
    _require(view["projection"] == "orthographic", "the projection")
    _require(
        _is_number(view["pitch_deg"]) and 0 <= view["pitch_deg"] <= 90,
        "settings.view.pitch_deg",
    )
    _require(
        _is_int(view["directions"]) and 1 <= view["directions"] <= 64,
        "settings.view.directions",
    )
    _require(_is_number(view["start_angle_deg"]), "settings.view.start_angle_deg")
    _require(_is_number(settings["model_yaw_deg"]), "settings.model_yaw_deg")
    _require(_is_number(settings["fps"]) and settings["fps"] > 0, "settings.fps")
    _require(
        _is_int(settings["supersample"]) and 1 <= settings["supersample"] <= 16,
        "settings.supersample",
    )
    _require(settings["root_motion"] in ("error", "keep"), "settings.root_motion")
    ground = _fields(settings["ground_m"], ["x", "y", "z"], "settings.ground_m")
    _require(all(map(_is_number, ground.values())), "settings.ground_m")
    if job["mode"] == "measure":
        for key in ("pixels_per_meter", "cell", "ground_px"):
            _require(settings[key] is None, f"settings.{key} is set in a measure job")
    else:
        ppm = settings["pixels_per_meter"]
        _require(
            _is_number(ppm) and ppm > 0,
            f"settings.pixels_per_meter {ppm!r} is not resolved for a render job",
        )
        for key, fields, low, high in (
            ("cell", ["width", "height"], 1, 4096),
            ("ground_px", ["x", "y"], 0, None),
        ):
            value = settings[key]
            _require(
                value is not None, f"settings.{key} is not resolved for a render job"
            )
            _fields(value, fields, f"settings.{key}")
            _require(
                all(
                    _is_int(item) and item >= low and (high is None or item <= high)
                    for item in value.values()
                ),
                f"settings.{key} {value!r} is out of range",
            )

    clips = job["clips"]
    _require(isinstance(clips, list) and clips, "clips")
    listed = settings["clips"]
    _require(
        isinstance(listed, list)
        and all(
            isinstance(item, dict)
            and set(item) == {"name", "loop"}
            and isinstance(item["loop"], bool)
            for item in listed
        )
        and [item["name"] for item in listed]
        == [clip.get("name") if isinstance(clip, dict) else None for clip in clips],
        "settings.clips does not list the job's clips",
    )
    names = set()
    for clip in clips:
        _fields(clip, ["animation_index", "name", "t0_s", "t1_s", "roots"], "clip")
        index = clip["animation_index"]
        _require(index is None or (_is_int(index) and index >= 0), "animation_index")
        if index is None:
            _require(
                clip["t0_s"] == 0 and clip["t1_s"] == 0 and clip["roots"] == [],
                f"clip {clip['name']!r} has no animation index, so it must be the "
                "static clip: zero endpoints and no roots",
            )
        _require(isinstance(clip["name"], str) and clip["name"], "a clip name")
        _require(clip["name"] not in names, f"clip {clip['name']!r} repeats")
        names.add(clip["name"])
        _require(
            _is_number(clip["t0_s"])
            and _is_number(clip["t1_s"])
            and clip["t0_s"] <= clip["t1_s"],
            f"clip {clip['name']!r}'s range",
        )
        _require(isinstance(clip["roots"], list), "roots")
        seen_roots = set()
        for root in clip["roots"]:
            _fields(root, ["node_index", "node_name"], "root")
            _require(
                _is_int(root["node_index"]) and root["node_index"] >= 0,
                "a root node_index",
            )
            _require(
                root["node_name"] is None or isinstance(root["node_name"], str),
                "a root node_name",
            )
            _require(
                root["node_index"] not in seen_roots,
                f"clip {clip['name']!r} repeats root node {root['node_index']}",
            )
            seen_roots.add(root["node_index"])

    frames = job["frames"]
    _require(isinstance(frames, list) and frames, "frames")
    ranges = {clip["name"]: (clip["t0_s"], clip["t1_s"]) for clip in clips}
    addresses = set()
    samples = {}
    for frame in frames:
        _fields(frame, ["address", "index", "angle_deg"], "frame")
        address = _fields(
            frame["address"],
            ["subject", "variant", "clip", "direction", "time_s"],
            "frame address",
        )
        _require(
            address["subject"] == job["subject"]
            and address["variant"] == job["variant"],
            "a frame's subject or variant",
        )
        _require(address["clip"] in names, f"a frame's clip {address['clip']!r}")
        _require(
            _is_int(address["direction"])
            and 0 <= address["direction"] < view["directions"],
            "a frame's direction",
        )
        _require(_is_number(address["time_s"]), "a frame's time_s")
        _require(_is_int(frame["index"]) and frame["index"] >= 0, "a frame's index")
        _require(_is_number(frame["angle_deg"]), "a frame's angle_deg")
        t0, t1 = ranges[address["clip"]]
        _require(
            t0 <= address["time_s"] <= t1,
            f"time {address['time_s']!r} is outside clip {address['clip']!r}'s "
            f"range {t0!r} to {t1!r}",
        )
        key = tuple(address[k] for k in ("clip", "direction", "time_s"))
        _require(key not in addresses, f"the frame address {address!r} repeats")
        addresses.add(key)
        expected = direction_angle(
            view["start_angle_deg"], address["direction"], view["directions"]
        )
        _require(
            frame["angle_deg"] == expected,
            f"direction {address['direction']}'s angle is {frame['angle_deg']!r}, "
            f"not {expected!r}",
        )
        samples.setdefault((address["clip"], address["direction"]), []).append(
            (frame["index"], address["time_s"])
        )
    for (clip_name, direction), indexed in samples.items():
        times = [time_s for _, time_s in indexed]
        _require(
            [index for index, _ in indexed] == list(range(len(indexed)))
            and times == sorted(set(times)),
            f"clip {clip_name!r} direction {direction}'s samples are not indexed "
            "0, 1, 2, ... in time order",
        )


def _wrap(degrees):
    turned = degrees % 360
    return 0.0 if turned == 360 else turned


def direction_angle(start, index, count):
    """θᵢ = (start + i · 360 / N) mod 360, computed as moskophoros.views does."""
    return _wrap(_wrap(start) + index * 360 / count)


def canonical_sha256(document):
    text = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(text.encode("ascii")).hexdigest()


# The private copy


def split_glb(data, path):
    if len(data) < _GLB_HEADER.size + _CHUNK_HEADER.size:
        raise ScriptError(f"{path} is not binary glTF")
    magic, version, _ = _GLB_HEADER.unpack_from(data)
    if magic != b"glTF" or version != 2:
        raise ScriptError(f"{path} is not binary glTF 2.0")
    length, kind = _CHUNK_HEADER.unpack_from(data, _GLB_HEADER.size)
    if kind != _JSON_CHUNK:
        raise ScriptError(f"{path} has no JSON chunk")
    start = _GLB_HEADER.size + _CHUNK_HEADER.size
    try:
        document = json.loads(data[start : start + length].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ScriptError(f"{path} has unreadable JSON: {error}") from None
    return document, data[start + length :]


def private_copy(document, rest, source, scene):
    """The GLB bytes Blender imports: nodes, meshes and animations renamed by
    index, a placeholder animation first, the job's scene made the default,
    and external files given absolute paths."""
    document = json.loads(json.dumps(document))
    nodes = document.setdefault("nodes", [])
    for index, node in enumerate(nodes):
        node["name"] = NODE_NAME.format(index)
    meshes = document.get("meshes", [])
    originals = list(meshes)
    for index, node in enumerate(nodes):
        if "mesh" in node:
            mesh = json.loads(json.dumps(originals[node["mesh"]]))
            mesh["name"] = MESH_NAME.format(node["mesh"], index)
            targets = max(
                (len(primitive.get("targets", [])) for primitive in mesh["primitives"]),
                default=0,
            )
            mesh["extras"] = {
                "targetNames": [TARGET_NAME.format(i) for i in range(targets)]
            }
            meshes.append(mesh)
            node["mesh"] = len(meshes) - 1
    # The importer names armatures after skins, objects after cameras and
    # lights, and collections after scenes.
    for key, kind in (("skins", "skin"), ("cameras", "camera"), ("scenes", "scene")):
        for index, item in enumerate(document.get(key, [])):
            item["name"] = f"moskophoros.{kind}.{index}.data"
    lights = document.get("extensions", {}).get("KHR_lights_punctual", {})
    for index, light in enumerate(lights.get("lights", [])):
        light["name"] = f"moskophoros.light.{index}.data"
    animations = document.get("animations") or []
    for index, animation in enumerate(animations):
        animation["name"] = ANIMATION_NAME.format(index)
    if animations:
        # One key at time 0 holding (0, 0, 0). Accessors without a buffer
        # view are zeros.
        accessors = document.setdefault("accessors", [])
        accessors.append(
            {
                "componentType": 5126,
                "count": 1,
                "type": "SCALAR",
                "min": [0],
                "max": [0],
            }
        )
        accessors.append({"componentType": 5126, "count": 1, "type": "VEC3"})
        nodes.append({"name": PLACEHOLDER})
        document["scenes"][scene].setdefault("nodes", []).append(len(nodes) - 1)
        animations.insert(
            0,
            {
                "name": PLACEHOLDER,
                "channels": [
                    {
                        "sampler": 0,
                        "target": {"node": len(nodes) - 1, "path": "translation"},
                    }
                ],
                "samplers": [
                    {
                        "input": len(accessors) - 2,
                        "output": len(accessors) - 1,
                        "interpolation": "LINEAR",
                    }
                ],
            },
        )
    document["scene"] = scene
    directory = os.path.dirname(source)
    for key in ("buffers", "images"):
        for item in document.get(key, []):
            uri = item.get("uri")
            if isinstance(uri, str) and not uri.startswith("data:"):
                absolute = os.path.join(directory, urllib.parse.unquote(uri))
                item["uri"] = urllib.parse.quote(absolute)
    text = json.dumps(document, separators=(",", ":")).encode("utf-8")
    text += b" " * (-len(text) % 4)
    body = _CHUNK_HEADER.pack(len(text), _JSON_CHUNK) + text + rest
    return _GLB_HEADER.pack(b"glTF", 2, _GLB_HEADER.size + len(body)) + body


def _pointer(channel):
    """A channel's KHR_animation_pointer pointer, or None."""
    pointer = (
        channel.get("target", {})
        .get("extensions", {})
        .get("KHR_animation_pointer", {})
        .get("pointer")
    )
    return pointer if isinstance(pointer, str) else None


def refuse_unsupported(document, source):
    """Refuse what the input contract rejects and Blender's importer cannot
    reproduce: CUBICSPLINE samplers and mesh morph-weight pointers. The
    caller rejects these as input errors first; this keeps a job that skips
    that check from being measured wrongly."""
    for index, animation in enumerate(document.get("animations") or []):
        for sampler in animation.get("samplers", []):
            if sampler.get("interpolation") == "CUBICSPLINE":
                raise ScriptError(
                    f"{source}: animation {index} uses CUBICSPLINE interpolation, "
                    "which is not supported"
                )
        for channel in animation.get("channels", []):
            pointer = _pointer(channel)
            if pointer is not None and _MESH_WEIGHTS.fullmatch(pointer):
                raise ScriptError(
                    f"{source}: animation {index} animates {pointer}, which is not "
                    "supported"
                )


def import_glb(data, directory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = os.path.join(directory, "subject.glb")
    with open(path, "wb") as handle:
        handle.write(data)
    # No bone display shapes: they are not part of the subject.
    result = bpy.ops.import_scene.gltf(filepath=path, disable_bone_shape=True)
    if "FINISHED" not in result:
        raise ScriptError(f"Blender could not import the model: {sorted(result)}")


# Static state


_TRANSFORM = (
    "location",
    "rotation_quaternion",
    "rotation_euler",
    "rotation_axis_angle",
    "scale",
)


def _transform(item):
    state = {"rotation_mode": item.rotation_mode}
    state.update((key, tuple(getattr(item, key))) for key in _TRANSFORM)
    return state


def _restore(item, state):
    item.rotation_mode = state["rotation_mode"]
    for key in _TRANSFORM:
        setattr(item, key, state[key])


# Blender's limits for a shape key's value.
WEIGHT_LIMIT = 10.0


def widen_weight_ranges():
    """Let every morph weight reach any value Blender can hold. The importer
    sets each shape key's range from the first key of its animation only,
    and Blender clamps evaluated values to that range."""
    for key in bpy.data.shape_keys:
        for block in key.key_blocks[1:]:
            block.slider_min = -WEIGHT_LIMIT
            block.slider_max = WEIGHT_LIMIT


def check_weights(objects, document, clip, times, fps):
    """Fail if a weight the clip uses is beyond what Blender can hold.

    A weight the clip animates is checked where it is evaluated, at each
    sample; one it leaves alone keeps its node's default from the file.
    """
    nodes = document.get("nodes", [])
    for obj in objects:
        key = obj.data.shape_keys
        if key is None:
            continue
        node = nodes[int(_MESH_DATA.fullmatch(obj.data.name)[1])]
        mesh = document["meshes"][node["mesh"]]
        defaults = node.get("weights") or mesh.get("weights") or []
        curves = {}
        animation = key.animation_data
        if animation is not None and animation.action is not None:
            for layer in animation.action.layers:
                for strip in layer.strips:
                    for channelbag in strip.channelbags:
                        if channelbag.slot != animation.action_slot:
                            continue
                        for curve in channelbag.fcurves:
                            match = _TARGET_PATH.fullmatch(curve.data_path)
                            if match is not None:
                                curves[int(match[1])] = curve
        for block in key.key_blocks[1:]:
            target = int(block.name.rsplit(".", 1)[1])
            if target in curves:
                for time_s in times:
                    weight = curves[target].evaluate(time_s * fps)
                    if abs(weight) > WEIGHT_LIMIT:
                        raise ScriptError(
                            f"clip {clip['name']!r} drives morph target {target} to "
                            f"{weight!r} at {time_s!r} s, beyond Blender's "
                            f"±{WEIGHT_LIMIT:g}"
                        )
            else:
                weight = defaults[target] if target < len(defaults) else 0.0
                if abs(weight) > WEIGHT_LIMIT:
                    raise ScriptError(
                        f"morph target {target}'s default weight is {weight!r}, "
                        f"beyond Blender's ±{WEIGHT_LIMIT:g}"
                    )


def record_statics():
    """Every object's and pose bone's transform and every shape key value,
    as the importer left them."""
    statics = {}
    for obj in bpy.data.objects:
        bones = {}
        if obj.pose is not None:
            bones = {bone.name: _transform(bone) for bone in obj.pose.bones}
        keys = ()
        if obj.type == "MESH" and obj.data.shape_keys is not None:
            keys = tuple(block.value for block in obj.data.shape_keys.key_blocks)
        statics[obj.name] = (_transform(obj), bones, keys)
    return statics


def reset(statics):
    """Stop every animation and return everything to its static state."""
    for data in (*bpy.data.objects, *bpy.data.shape_keys):
        if data.animation_data is not None:
            data.animation_data.action = None
            data.animation_data.use_nla = False
    for obj in bpy.data.objects:
        if obj.name not in statics:
            continue  # the render camera, which this script places itself
        transform, bones, keys = statics[obj.name]
        _restore(obj, transform)
        if obj.pose is not None:
            for bone in obj.pose.bones:
                _restore(bone, bones[bone.name])
        if obj.type == "MESH" and obj.data.shape_keys is not None:
            for block, value in zip(obj.data.shape_keys.key_blocks, keys, strict=True):
                block.value = value


def activate(animation_index):
    """Make the animation's action the only active one, on every ID it
    animates, with that ID's slot."""
    name = ANIMATION_NAME.format(animation_index)
    action = bpy.data.actions.get(name)
    if action is None:
        raise ScriptError(f"animation {animation_index} has no imported action")
    assigned = set()
    for data in (*bpy.data.objects, *bpy.data.shape_keys):
        animation_data = data.animation_data
        if animation_data is None:
            continue
        for track in animation_data.nla_tracks:
            for strip in track.strips:
                if strip.action == action:
                    animation_data.action = action
                    animation_data.action_slot = strip.action_slot
                    assigned.add(strip.action_slot.identifier)
    # Only objects and shape keys shape the subject; slots for cameras,
    # lights or materials, which the design ignores, need no owner here.
    geometric = {
        slot.identifier
        for slot in action.slots
        if slot.target_id_type in ("OBJECT", "KEY")
    }
    unassigned = geometric - assigned
    if unassigned:
        raise ScriptError(
            f"animation {animation_index}'s targets {sorted(unassigned)} have no "
            "imported counterpart"
        )


# Evaluation


# Blender's frame range; a frame outside it would be clamped.
MAX_FRAME = 1048574


def evaluate(scene, fps, time_s):
    frame = time_s * fps
    if not -MAX_FRAME <= frame <= MAX_FRAME:
        raise ScriptError(
            f"time {time_s!r} s is frame {frame!r} at {fps!r} fps, beyond "
            f"Blender's frame range of ±{MAX_FRAME}"
        )
    whole = math.floor(frame)
    scene.frame_set(int(whole), subframe=frame - whole)
    return bpy.context.evaluated_depsgraph_get()


def subject_objects(document, scene_index):
    """The objects holding the selected scene's mesh nodes: one per node, or
    one per instance."""
    nodes = document.get("nodes", [])
    pending = list(document["scenes"][scene_index].get("nodes", []))
    expected = {}
    while pending:
        index = pending.pop()
        node = nodes[index]
        if "mesh" in node:
            expected[index] = instances(document, node)
        pending.extend(node.get("children", []))
    found = {}
    objects = []
    for obj in sorted(bpy.data.objects, key=lambda obj: obj.name):
        if obj.type != "MESH":
            continue
        match = _MESH_DATA.fullmatch(obj.data.name)
        if match is None or int(match[1]) not in expected:
            continue
        node = int(match[1])
        found[node] = found.get(node, 0) + 1
        objects.append(obj)
    for node in sorted(expected):
        if expected[node] != found.get(node, 0):
            raise ScriptError(
                f"mesh node {node} should make {expected[node]} object(s), but "
                f"{found.get(node, 0)} were imported"
            )
    return objects


def instances(document, node):
    """How many objects Blender makes of a mesh node: one, or, with
    EXT_mesh_gpu_instancing, one per entry of its first attribute among
    TRANSLATION, ROTATION and SCALE, as the importer counts them."""
    extension = node.get("extensions", {}).get("EXT_mesh_gpu_instancing")
    if extension is None:
        return 1
    attributes = extension.get("attributes", {})
    for key in ("TRANSLATION", "ROTATION", "SCALE"):
        if key in attributes:
            return document["accessors"][attributes[key]]["count"]
    return 0


def include_every_collection(layer_collection):
    for child in layer_collection.children:
        child.exclude = False
        include_every_collection(child)


def vertices(objects, depsgraph):
    """Every evaluated vertex, in glTF world coordinates."""
    points = []
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            coordinates = array("f", [0.0]) * (3 * len(mesh.vertices))
            mesh.vertices.foreach_get("co", coordinates)
            m = evaluated.matrix_world
            rows = [tuple(m[row]) for row in range(3)]
            for i in range(0, len(coordinates), 3):
                x, y, z = coordinates[i], coordinates[i + 1], coordinates[i + 2]
                wx, wy, wz = (r[0] * x + r[1] * y + r[2] * z + r[3] for r in rows)
                # Blender is Z-up; glTF is Y-up with +Z toward the viewer.
                points.append((wx, wz, -wy))
        finally:
            evaluated.to_mesh_clear()
    return points


def bounds(points, ground, rotation_deg, pitch_deg):
    """L, R, U, D on the screen plane from the projected ground point, with
    the subject turned by `rotation_deg` about the vertical axis through
    `ground`, counter-clockwise seen from above."""
    if not points:
        return {"L": 0.0, "R": 0.0, "U": 0.0, "D": 0.0}
    a = math.radians(rotation_deg)
    p = math.radians(pitch_deg)
    cos_a, sin_a, cos_p, sin_p = math.cos(a), math.sin(a), math.cos(p), math.sin(p)
    gx, gy, gz = ground
    xs = []
    ys = []
    for x, y, z in points:
        dx, dy, dz = x - gx, y - gy, z - gz
        turned_x = dx * cos_a + dz * sin_a
        turned_z = -dx * sin_a + dz * cos_a
        xs.append(turned_x)
        ys.append(cos_p * dy - sin_p * turned_z)
    return {
        "L": max(0.0, -min(xs)),
        "R": max(0.0, *xs),
        "U": max(0.0, *ys),
        "D": max(0.0, -min(ys)),
    }


_SUFFIXED_NODE = re.compile(r"moskophoros\.node\.\d+\.\d+")


def check_node_names():
    """Every node's object must have kept its exact name."""
    for obj in bpy.data.objects:
        if _SUFFIXED_NODE.fullmatch(obj.name):
            raise ScriptError(
                f"Blender renamed a node's object to {obj.name!r}; its identity "
                "is ambiguous"
            )


def node_position(index, depsgraph):
    """A node's evaluated world position in glTF coordinates: its bone's head
    if it is a joint, otherwise its object's origin."""
    name = NODE_NAME.format(index)
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and name in obj.pose.bones:
            evaluated = obj.evaluated_get(depsgraph)
            x, y, z = evaluated.matrix_world @ evaluated.pose.bones[name].head
            return x, z, -y
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ScriptError(f"node {index} has no imported object or bone")
    x, y, z = obj.evaluated_get(depsgraph).matrix_world.translation
    return x, z, -y


def measure(job, document, statics):
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    settings = job["settings"]
    pitch = settings["view"]["pitch_deg"]
    yaw = settings["model_yaw_deg"]
    ground = tuple(settings["ground_m"][axis] for axis in "xyz")
    check_node_names()
    objects = subject_objects(document, job["source"]["scene"])
    # The importer leaves other scenes' collections out of the view layer,
    # so their objects would never be evaluated; a root may be among them.
    # The subject is already chosen, so including them changes no bounds.
    include_every_collection(bpy.context.view_layer.layer_collection)

    measured = {}
    roots = []
    for clip in job["clips"]:
        reset(statics)
        if clip["animation_index"] is not None:
            activate(clip["animation_index"])
        for root in clip["roots"]:
            start = node_position(
                root["node_index"], evaluate(scene, fps, clip["t0_s"])
            )
            end = node_position(root["node_index"], evaluate(scene, fps, clip["t1_s"]))
            roots.append(
                {
                    "clip": clip["name"],
                    "node_index": root["node_index"],
                    "node_name": root["node_name"],
                    "travel_m": math.hypot(end[0] - start[0], end[2] - start[2]),
                }
            )
        angles = {}
        for frame in job["frames"]:
            address = frame["address"]
            if address["clip"] == clip["name"]:
                angles.setdefault(address["time_s"], {})[address["direction"]] = frame[
                    "angle_deg"
                ]
        check_weights(objects, document, clip, sorted(angles), fps)
        for time_s in sorted(angles):
            points = vertices(objects, evaluate(scene, fps, time_s))
            heights = [y for _, y, _ in points]
            height = max(heights) - min(heights) if heights else 0.0
            for direction, angle in angles[time_s].items():
                # Reduce first: a huge yaw would swallow the angle.
                rotation = (angle % 360 + yaw % 360) % 360
                measured[(clip["name"], direction, time_s)] = (
                    bounds(points, ground, rotation, pitch),
                    height,
                )

    frames = []
    for frame in job["frames"]:
        address = frame["address"]
        box, height = measured[
            (address["clip"], address["direction"], address["time_s"])
        ]
        frames.append({"address": address, "bounds_m": box, "height_m": height})
    return frames, roots


# Rendering


RENDERER = "workbench"


def configure_render(scene, settings):
    """Design §Capture's render settings and capture output."""
    render = scene.render
    render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    # Studio lighting fixed in view space, Workbench's default.
    shading.light = "STUDIO"
    shading.use_world_space_lighting = False
    # Texture color, falling back to the material color.
    shading.color_type = "TEXTURE"
    shading.show_shadows = False
    shading.show_cavity = False
    shading.show_object_outline = False
    shading.use_dof = False
    render.film_transparent = True
    view = scene.view_settings
    view.view_transform = "Standard"
    view.look = "None"
    view.exposure = 0.0
    view.gamma = 1.0
    scene.display_settings.display_device = "sRGB"
    image = render.image_settings
    image.file_format = "PNG"
    image.color_mode = "RGBA"
    image.color_depth = "8"
    # No date or render-time metadata, so identical frames are identical files.
    render.use_stamp = False
    for name in dir(render):
        if name.startswith("use_stamp_"):
            setattr(render, name, False)
    width, height, padded_width, padded_height = frame_size(settings)
    render.resolution_x = padded_width
    render.resolution_y = padded_height
    render.resolution_percentage = 100
    render.pixel_aspect_x = 1.0
    render.pixel_aspect_y = 1.0
    # Blender renders at least 4 pixels each way. A smaller image is the
    # top-left corner of a padded frame, cropped by the render border; the
    # fractions are exact, so the crop is exactly the requested size.
    padded = (padded_width, padded_height) != (width, height)
    render.use_border = padded
    render.use_crop_to_border = padded
    render.border_min_x = 0.0
    render.border_max_x = width / padded_width
    render.border_min_y = 1.0 - height / padded_height
    render.border_max_y = 1.0
    render.use_compositing = False
    render.use_sequencer = False


MIN_RESOLUTION = 4
# The camera stands this many meters clear of the subject's bounds, with its
# near plane halfway there, however far the subject reaches.
CLEARANCE = 1.0


def frame_size(settings):
    """The supersampled image size, and the frame Blender renders it from:
    at least MIN_RESOLUTION pixels each way."""
    scale = settings["supersample"]
    width = settings["cell"]["width"] * scale
    height = settings["cell"]["height"] * scale
    return width, height, max(width, MIN_RESOLUTION), max(height, MIN_RESOLUTION)


def _sin_cos(degrees):
    """Sine and cosine, exact at quarter turns so axes stay exact."""
    turned = _wrap(degrees)
    exact = {0: (0.0, 1.0), 90: (1.0, 0.0), 180: (0.0, -1.0), 270: (-1.0, 0.0)}
    if turned in exact:
        return exact[turned]
    radians = math.radians(turned)
    return math.sin(radians), math.cos(radians)


def _turn(vector, sin, cos):
    """`vector` turned about +Y, counter-clockwise seen from above."""
    x, y, z = vector
    return (x * cos + z * sin, y, -x * sin + z * cos)


def _blender(vector):
    """glTF (Y-up, +Z toward the viewer) to Blender (Z-up) coordinates."""
    x, y, z = vector
    return (x, -z, y)


def place_camera(camera, settings, rotation_deg, reach):
    """Put the orthographic camera where the ground point lands on pixel
    corner (gx·s, gy·s), as if the subject were turned by `rotation_deg`.

    Turning the subject by a about the vertical axis through the ground
    point is the same image as turning the camera by −a around it; the
    studio light is fixed to the camera, so the lighting is the same too.
    The camera sits in direction (0, sin p, cos p) from the ground point
    and looks back at it, with screen right +X and screen up
    (0, cos p, −sin p).
    """
    sin_p, cos_p = _sin_cos(settings["view"]["pitch_deg"])
    sin_a, cos_a = _sin_cos(-rotation_deg)
    toward = _turn((0.0, sin_p, cos_p), sin_a, cos_a)
    right = _turn((1.0, 0.0, 0.0), sin_a, cos_a)
    up = _turn((0.0, cos_p, 0.0 - sin_p), sin_a, cos_a)
    scale = settings["supersample"]
    meters = 1.0 / (settings["pixels_per_meter"] * scale)  # per image pixel
    _, _, width, height = frame_size(settings)
    gx = settings["ground_px"]["x"] * scale
    gy = settings["ground_px"]["y"] * scale
    ground = tuple(settings["ground_m"][axis] for axis in "xyz")
    distance = reach + CLEARANCE
    across = (width / 2 - gx) * meters
    down = (gy - height / 2) * meters
    center = tuple(
        ground[i] + right[i] * across + up[i] * down + toward[i] * distance
        for i in range(3)
    )
    # Blender reads a nested sequence assigned to a matrix column by column:
    # the camera's local X, Y and Z axes, then its position.
    camera.matrix_world = [
        (*_blender(right), 0.0),
        (*_blender(up), 0.0),
        (*_blender(toward), 0.0),
        (*_blender(center), 1.0),
    ]
    data = camera.data
    data.type = "ORTHO"
    data.sensor_fit = "HORIZONTAL"
    data.ortho_scale = width * meters
    data.shift_x = 0.0
    data.shift_y = 0.0
    data.clip_start = CLEARANCE / 2
    data.clip_end = distance + reach + CLEARANCE
    data.dof.use_dof = False


def reach(objects, depsgraph, ground):
    """How far the subject's bounding boxes reach from the ground point, in
    meters, so the camera can stand clear of it."""
    gx, gy, gz = _blender(ground)
    farthest = 0.0
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        m = evaluated.matrix_world
        for corner in evaluated.bound_box:
            x, y, z = (
                m[row][0] * corner[0]
                + m[row][1] * corner[1]
                + m[row][2] * corner[2]
                + m[row][3]
                for row in range(3)
            )
            farthest = max(farthest, math.dist((x, y, z), (gx, gy, gz)))
    return farthest


def render_frames(job, document, statics):
    """Render every requested frame to color/NNNNNN.png in request order."""
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    settings = job["settings"]
    yaw = settings["model_yaw_deg"]
    ground = tuple(settings["ground_m"][axis] for axis in "xyz")
    check_node_names()
    objects = subject_objects(document, job["source"]["scene"])
    include_every_collection(bpy.context.view_layer.layer_collection)
    subject = {obj.name for obj in objects}
    for obj in bpy.data.objects:
        # Only the subject's meshes are rendered, hidden or not; nothing
        # the importer added is.
        obj.hide_render = obj.name not in subject
        if obj.name in subject:
            obj.hide_viewport = False
    camera = bpy.data.objects.new("moskophoros.camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    configure_render(scene, settings)
    os.makedirs(os.path.join(job["output_dir"], "color"), exist_ok=False)

    ordinals = {}
    for ordinal, frame in enumerate(job["frames"]):
        ordinals.setdefault(frame["address"]["clip"], []).append((ordinal, frame))
    paths = {}
    for clip in job["clips"]:
        reset(statics)
        if clip["animation_index"] is not None:
            activate(clip["animation_index"])
        requested = ordinals.get(clip["name"], [])
        times = sorted({frame["address"]["time_s"] for _, frame in requested})
        check_weights(objects, document, clip, times, fps)
        for ordinal, frame in requested:
            depsgraph = evaluate(scene, fps, frame["address"]["time_s"])
            rotation = (frame["angle_deg"] % 360 + yaw % 360) % 360
            place_camera(camera, settings, rotation, reach(objects, depsgraph, ground))
            relative = f"color/{ordinal:06d}.png"
            scene.render.filepath = os.path.join(job["output_dir"], relative)
            bpy.ops.render.render(write_still=True)
            paths[ordinal] = relative
    return [
        {"address": frame["address"], "buffers": {"color": paths[ordinal]}}
        for ordinal, frame in enumerate(job["frames"])
    ], {
        "blender": ".".join(map(str, bpy.app.version)),
        "renderer": RENDERER,
        "studio_light": scene.display.shading.studio_light,
    }


def main(argv):
    if "--" not in argv or argv.index("--") + 1 >= len(argv):
        raise ScriptError("usage: blender ... --python blender_script.py -- JOB")
    job = load_job(argv[argv.index("--") + 1])
    check_job(job)

    source = job["source"]["path"]
    try:
        with open(source, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise ScriptError(f"cannot read {source}: {error}") from None
    if hashlib.sha256(data).hexdigest() != job["source"]["sha256"]:
        raise ScriptError(f"{source} does not match the job's sha256")
    document, rest = split_glb(data, source)
    refuse_unsupported(document, source)
    scene_index = job["source"]["scene"]
    if scene_index >= len(document.get("scenes", [])):
        raise ScriptError(f"{source} has no scene {scene_index}")

    with tempfile.TemporaryDirectory(prefix="moskophoros-") as directory:
        import_glb(private_copy(document, rest, source, scene_index), directory)
        widen_weight_ranges()
        if job["mode"] == "measure":
            frames, roots = measure(job, document, record_statics())
            backend = {"blender": ".".join(map(str, bpy.app.version))}
        else:
            frames, backend = render_frames(job, document, record_statics())

    result = {
        "schema": RESULT_SCHEMA,
        "mode": job["mode"],
        "job_sha256": canonical_sha256(job),
        "source_sha256": job["source"]["sha256"],
        "backend": backend,
        "frames": frames,
    }
    if job["mode"] == "measure":
        result["roots"] = roots
    output = os.path.join(job["output_dir"], "result.json")
    temporary = output + ".partial"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, output)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except ScriptError as error:
        print(f"moskophoros: error: {error}", file=sys.stderr)
        sys.exit(1)
