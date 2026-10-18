"""Run one capture phase inside Blender: `blender ... --python <this> -- <job.json>`.

This is the only module that imports `bpy`, and nothing in the package
imports it. It runs under Blender's bundled Python and uses only `bpy` and
the standard library. It follows design §Capture, §Capture job and result
contract, §Clips and sampling, §Root motion, §Scale and ground point and
§Camera and directions.

Measure mode reports bounds, heights and root travel; render mode renders
each frame's colour, material-ID, shade, normal and depth buffers in one
flat, unlit Cycles render. Both share the import, subject selection,
identity mapping and clip isolation below.

Identity mapping: the script imports a private copy of the source in which
every node is renamed `moskophoros.node.<index>` and every animation
`moskophoros.animation.<index>`. Every mesh node gets its own copy of its
mesh, named `moskophoros.mesh.<mesh>.node.<node>.data`, whose morph targets
are named `moskophoros.target.<index>`, and every material
`moskophoros.material.<index>.data`. Skins, cameras, lights and scenes are renamed
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
import zlib
from array import array

import bpy

JOB_SCHEMA = "moskophoros.capture-job/1"
RESULT_SCHEMA = "moskophoros.capture-result/3"
NODE_NAME = "moskophoros.node.{}"
ANIMATION_NAME = "moskophoros.animation.{}"
# Not ending in digits: Blender would read those as its own ".001" suffix
# when it duplicates mesh data.
MESH_NAME = "moskophoros.mesh.{}.node.{}.data"
TARGET_NAME = "moskophoros.target.{}"
MATERIAL_NAME = "moskophoros.material.{}.data"
PLACEHOLDER = "moskophoros.placeholder"
_MESH_DATA = re.compile(r"moskophoros\.mesh\.\d+\.node\.(\d+)\.data(?:\.\d+)?")
_MESH_WEIGHTS = re.compile(r"/meshes/\d+/weights")
# The importer copies a material, adding Blender's ".001" suffix, when one
# glTF material serves primitives with and without vertex colours.
_MATERIAL = re.compile(r"moskophoros\.material\.(\d+)\.data(?:\.\d+)?")
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


def _is_frame_count(value):
    """A frame count as given: "auto" or a whole number of 1 or more. The
    job's frames already hold the times it samples; this only checks it."""
    return value == "auto" or (_is_int(value) and value >= 1)


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
            "frames",
            "supersample",
            "pixels_per_meter",
            "cell",
            "ground_m",
            "ground_px",
            "root_motion",
            "shade",
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
    _require(_is_frame_count(settings["frames"]), "settings.frames")
    _require(
        _is_int(settings["supersample"]) and 1 <= settings["supersample"] <= 16,
        "settings.supersample",
    )
    _require(settings["root_motion"] in ("error", "keep"), "settings.root_motion")
    ground = _fields(settings["ground_m"], ["x", "y", "z"], "settings.ground_m")
    _require(all(map(_is_number, ground.values())), "settings.ground_m")
    shade = _fields(
        settings["shade"],
        [
            "ao_distance_m",
            "ao_samples",
            "occlusion_weight",
            "convexity_weight",
            "materials",
        ],
        "settings.shade",
    )
    _require(
        _is_number(shade["ao_distance_m"]) and shade["ao_distance_m"] > 0,
        "settings.shade.ao_distance_m",
    )
    _require(
        _is_int(shade["ao_samples"]) and 1 <= shade["ao_samples"] <= MAX_AO_SAMPLES,
        f"settings.shade.ao_samples {shade['ao_samples']!r} is not 1 to "
        f"{MAX_AO_SAMPLES}",
    )
    for key in ("occlusion_weight", "convexity_weight"):
        _require(_is_number(shade[key]) and shade[key] >= 0, f"settings.shade.{key}")
    _require(isinstance(shade["materials"], list), "settings.shade.materials")
    indices = []
    for own in shade["materials"]:
        _fields(
            own,
            ["material", "ao_distance_m", "occlusion_weight", "convexity_weight"],
            "settings.shade.materials entry",
        )
        _require(
            _is_int(own["material"]) and 0 <= own["material"] < MAX_MATERIALS,
            f"settings.shade.materials material {own['material']!r}",
        )
        indices.append(own["material"])
        _require(
            _is_number(own["ao_distance_m"]) and own["ao_distance_m"] > 0,
            f"settings.shade.materials[{own['material']}].ao_distance_m",
        )
        for key in ("occlusion_weight", "convexity_weight"):
            _require(
                _is_number(own[key]) and own[key] >= 0,
                f"settings.shade.materials[{own['material']}].{key}",
            )
    _require(
        indices == sorted(set(indices)),
        "settings.shade.materials is not in ascending, distinct material order",
    )
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
            and set(item) == {"name", "loop", "frames"}
            and isinstance(item["loop"], bool)
            and (item["frames"] is None or _is_frame_count(item["frames"]))
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
    for index, material in enumerate(document.get("materials", [])):
        material["name"] = MATERIAL_NAME.format(index)
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
    # No bone display shapes: they are not part of the subject. The TEMPERANCE
    # bone heuristic places a mesh parented to a bone where glTF puts it under
    # a scaled armature. The default, BLENDER, shortens each bone by the
    # armature's scale but moves the bone's child objects back by the full
    # length, misplacing them by length × (scale − 1).
    result = bpy.ops.import_scene.gltf(
        filepath=path, disable_bone_shape=True, bone_heuristic="TEMPERANCE"
    )
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


RENDERER = "cycles"
# The colour's technique and fixed parameters, reported in the result: one
# flat, unlit Cycles render per frame (alpha design, The pipeline with alpha).
COLOR = {
    "technique": "cycles-flat-emission",
    "samples_per_pixel": 1,
    "seed": 0,
    "pixel_filter": "BOX",
    "filter_width_px": 0.01,
    "min_transparent_bounces": 64,
    "transparent_max_bounces": 64,
    # 2^-30, exactly.
    "pass_alpha_threshold": 9.313225746154785e-10,
}
_RENDER_SETTINGS = (
    ("render", "engine", "CYCLES"),
    ("render", "film_transparent", True),
    ("render", "dither_intensity", 0.0),
    ("cycles", "device", "CPU"),
    ("cycles", "samples", COLOR["samples_per_pixel"]),
    ("cycles", "use_adaptive_sampling", False),
    ("cycles", "seed", COLOR["seed"]),
    ("cycles", "use_animated_seed", False),
    ("cycles", "pixel_filter_type", COLOR["pixel_filter"]),
    ("cycles", "filter_width", COLOR["filter_width_px"]),
    ("cycles", "max_bounces", 0),
    ("cycles", "diffuse_bounces", 0),
    ("cycles", "glossy_bounces", 0),
    ("cycles", "transmission_bounces", 0),
    ("cycles", "volume_bounces", 0),
    ("cycles", "min_transparent_bounces", COLOR["min_transparent_bounces"]),
    ("cycles", "transparent_max_bounces", COLOR["transparent_max_bounces"]),
    ("cycles", "sample_clamp_direct", 0.0),
    ("cycles", "sample_clamp_indirect", 0.0),
    ("cycles", "use_denoising", False),
    ("layer", "pass_alpha_threshold", COLOR["pass_alpha_threshold"]),
    ("image", "file_format", "TARGA_RAW"),
    ("image", "color_mode", "RGBA"),
)


def configure_render(scene, settings):
    """Design §Capture's render settings and capture output."""
    render = scene.render
    owners = {
        "render": render,
        "cycles": scene.cycles,
        "layer": bpy.context.view_layer,
        "image": render.image_settings,
    }
    for owner, name, value in _RENDER_SETTINGS:
        setattr(owners[owner], name, value)
        held = getattr(owners[owner], name)
        # Blender stores floats in 32 bits.
        if held != value and not (
            isinstance(value, float) and math.isclose(held, value, rel_tol=1e-6)
        ):
            raise ScriptError(
                f"Blender holds the render setting {owner}.{name} as {held!r}, "
                f"not {value!r}"
            )
    view = scene.view_settings
    view.view_transform = "Standard"
    view.look = "None"
    view.exposure = 0.0
    view.gamma = 1.0
    scene.display_settings.display_device = "sRGB"
    # No date or render-time metadata reaches a buffer: every buffer is
    # written from pixels, and Blender's own stamps are off besides.
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


# The buffers (design §Capture; alpha design, Capture transport and
# provenance): every surface's shader is replaced by a flat emission of its
# material colour, `Mix(Transparent, Emission(colour))`, which writes its
# material-ID code, shade, normal and depth to float AOVs, so every buffer
# comes from one camera sample at the pixel centre of one render.

ID_BACKGROUND = 0
NO_MATERIAL_ID = 0xFFFF
MAX_MATERIALS = NO_MATERIAL_ID - 1
# The fixed shade technique, reported in the result. The capture values,
# the ambient occlusion distance and samples and the two weights, are the
# job's `settings.shade`.
SHADE = {
    "technique": "cycles-ambient-occlusion",
    "samples_per_pixel": 1,
    "seed": 0,
    "pixel_filter": "BOX",
    "filter_width_px": 0.01,
}
# The most samples the Ambient Occlusion node takes; it silently clamps more.
MAX_AO_SAMPLES = 128
NO_MATERIAL = "moskophoros.no-material"
# glTF's default material, which a primitive without one takes: white.
NO_MATERIAL_COLOR = (1.0, 1.0, 1.0, 1.0)
# Every render frame's buffers, each at <name>/NNNNNN.png: the back layer's
# colour, material ID and shade, the front-most surface's normal and depth,
# and the front layer's colour, alpha, material ID and shade (alpha design,
# Capture transport and provenance).
BUFFERS = (
    "color",
    "matid",
    "shade",
    "normal",
    "depth",
    "front_color",
    "front_alpha",
    "front_matid",
    "front_shade",
)
# The render phase's directory for the render's TGA and OpenEXR, removed
# once every frame is done.
SCRATCH = "scratch"
# The view-layer AOVs the renders add: the material-ID code and the linear
# shade, values; the camera-space shading normal, a colour (lighting sheet
# design D-11); the camera depth, a value; the gated hit; and the front
# layer's material-ID code, shade and hit.
AOVS = (
    ("matid", "VALUE"),
    ("shade", "VALUE"),
    ("normal", "COLOR"),
    ("depth", "VALUE"),
    ("hit", "VALUE"),
    ("front_matid", "VALUE"),
    ("front_shade", "VALUE"),
    ("front_hit", "VALUE"),
)
# The surface gate's threshold, the view layer's `pass_alpha_threshold`.
GATE_THRESHOLD = COLOR["pass_alpha_threshold"]
# Cycles drops a closure whose weight is below this (CLOSURE_WEIGHT_CUTOFF).
CLOSURE_CUTOFF = 1e-5
# The shared node group whose two values switch every surface between the
# back, front and count renders.
SWITCH = "moskophoros.switch"
# A camera path may cross this many surfaces that still let light through:
# both transparent bounce limits (alpha design spike 3).
LAYER_LIMIT = COLOR["transparent_max_bounces"]
# Where the render result is saved for its AOVs: a multilayer OpenEXR of
# 32-bit floats, uncompressed, since decompressing in pure Python is slow.
_EXR_SETTINGS = (
    ("media_type", "MULTI_LAYER_IMAGE"),
    ("file_format", "OPEN_EXR_MULTILAYER"),
    ("color_depth", "32"),
    ("exr_codec", "NONE"),
)


def material_codes(document):
    """{glTF material index: ID code}, and the result's table of every code."""
    count = len(document.get("materials", []))
    if count > MAX_MATERIALS:
        raise ScriptError(
            f"the model has {count} materials; the material-ID buffer holds "
            f"{MAX_MATERIALS}"
        )
    codes = {index: index + 1 for index in range(count)}
    table = [{"id": code, "material": index} for index, code in codes.items()]
    table.append({"id": NO_MATERIAL_ID, "material": None})
    return codes, table


def _shown_material(document, index):
    """A glTF material as diagnostics name it: its index, and its name."""
    name = document.get("materials", [])[index].get("name")
    return f"glTF material {index}" + ("" if name is None else f" ({name!r})")


def _from_node(socket):
    return socket.links[0].from_node if socket.is_linked else None


def _is_unlit_core(node):
    """Whether `node` is the glTF importer's `KHR_materials_unlit` core:
    `Mix(Light Path "Is Camera Ray", Transparent, Emission)`."""
    if node is None or node.bl_idname != "ShaderNodeMixShader":
        return False
    fac = node.inputs[0]
    if not (
        fac.is_linked
        and fac.links[0].from_node.bl_idname == "ShaderNodeLightPath"
        and fac.links[0].from_socket.identifier == "Is Camera Ray"
    ):
        return False
    first, second = _from_node(node.inputs[1]), _from_node(node.inputs[2])
    return (
        first is not None
        and first.bl_idname == "ShaderNodeBsdfTransparent"
        and second is not None
        and second.bl_idname == "ShaderNodeEmission"
    )


def surface_sockets(material, where):
    """The sockets of `material`'s node tree whose values are its surface
    colour and alpha, by the extraction rule of alpha design spike 2: a
    Principled BSDF's `Base Color` and `Alpha`; or the Emission colour of the
    `KHR_materials_unlit` core, with alpha 1 alone and the factor of the
    `Mix` wrapping it in an alpha chain otherwise (None for alpha 1). Any
    other shape is refused, naming the material as `where`."""
    tree = material.node_tree
    outputs = [
        node
        for node in (tree.nodes if tree is not None else ())
        if node.bl_idname == "ShaderNodeOutputMaterial" and node.is_active_output
    ]
    if len(outputs) != 1:
        raise ScriptError(
            f"{where} has {len(outputs)} active material outputs; the capture reads one"
        )
    surface = _from_node(outputs[0].inputs["Surface"])
    if surface is not None and surface.bl_idname == "ShaderNodeBsdfPrincipled":
        return surface.inputs["Base Color"], surface.inputs["Alpha"]
    core, alpha = None, None
    if _is_unlit_core(surface):
        core = surface
    elif (
        surface is not None
        and surface.bl_idname == "ShaderNodeMixShader"
        and _from_node(surface.inputs[1]) is not None
        and _from_node(surface.inputs[1]).bl_idname == "ShaderNodeBsdfTransparent"
        and _is_unlit_core(_from_node(surface.inputs[2]))
    ):
        core, alpha = _from_node(surface.inputs[2]), surface.inputs[0]
    if core is None:
        shape = "nothing" if surface is None else surface.bl_idname
        raise ScriptError(
            f"{where}'s surface is {shape}; the capture reads a Principled BSDF "
            "or a KHR_materials_unlit graph as the glTF importer builds them"
        )
    return _from_node(core.inputs[2]).inputs["Color"], alpha


class Surfaces:
    """Replaces every rendered surface's shader with the capture's flat
    emission and AOVs, adds the AOVs and the stand-in for surfaces without a
    material, and restores every one of them exactly."""

    def __init__(self, scene, objects, codes, shade, document):
        self.scene = scene
        self.objects = objects
        self.codes = codes
        self.document = document
        # The job's capture values: settings.shade, and each glTF material's
        # own distance and weights by material index.
        self.shade = shade
        self.own = {own["material"]: own for own in shade["materials"]}
        self.trees = []
        self.slots = []
        self.appended = []
        self.aovs = []
        self.stand_in = None
        self.switch = None
        self.translucent = False

    def make_switch(self):
        """The shared node group whose two values, each 0 or 1, switch every
        surface between the back, front and count renders."""
        self.switch = bpy.data.node_groups.new(SWITCH, "ShaderNodeTree")
        output = self.switch.nodes.new("NodeGroupOutput")
        for index, name in enumerate(("count", "front")):
            self.switch.interface.new_socket(
                name, in_out="OUTPUT", socket_type="NodeSocketFloat"
            )
            value = self.switch.nodes.new("ShaderNodeValue")
            value.name = name
            value.outputs[0].default_value = 0.0
            self.switch.links.new(value.outputs[0], output.inputs[index])

    def mode(self, name):
        """Switch every surface to the `back`, `front` or `count` render's
        shader: two shared values, which Cycles folds into each material."""
        values = {"back": (0.0, 0.0), "front": (0.0, 1.0), "count": (1.0, 0.0)}[name]
        for key, value in zip(("count", "front"), values, strict=True):
            self.switch.nodes[key].outputs[0].default_value = value

    def apply(self):
        rendered = {
            slot.material
            for obj in self.objects
            if obj.type == "MESH"
            for slot in obj.material_slots
            if slot.material is not None
        }
        materials = []
        for material in bpy.data.materials:
            match = _MATERIAL.fullmatch(material.name)
            if material not in rendered:
                continue
            if match is None:
                raise ScriptError(
                    f"a rendered surface uses the material {material.name!r}, "
                    "which is no glTF material of the model"
                )
            index = int(match.group(1))
            where = _shown_material(self.document, index)
            colour, alpha = surface_sockets(material, where)
            # A MASK material's alpha cuts out, and a BLEND material's is
            # translucent (alpha design D-1, D-3); an OPAQUE material is
            # opaque whatever its alpha.
            mode = self.document["materials"][index].get("alphaMode", "OPAQUE")
            translucent = mode == "BLEND"
            self.translucent |= translucent
            materials.append(
                (
                    material,
                    self.codes[index],
                    colour,
                    alpha if mode in ("MASK", "BLEND") else None,
                    translucent,
                )
            )
        layer = bpy.context.view_layer
        for name, kind in AOVS:
            aov = layer.aovs.add()
            aov.name = name
            aov.type = kind
            self.aovs.append(aov)
        self.make_switch()
        self.stand_in = bpy.data.materials.new(NO_MATERIAL)
        self.stand_in.use_nodes = True
        materials.append((self.stand_in, NO_MATERIAL_ID, None, None, False))
        for material, code, colour, alpha, translucent in materials:
            self._inject(material, code, colour, alpha, translucent)
        for obj in self.objects:
            if obj.type != "MESH":
                continue
            if not obj.material_slots:
                obj.data.materials.append(self.stand_in)
                self.appended.append(obj.data)
            for slot in obj.material_slots:
                if slot.material is None:
                    self.slots.append(slot)
                    slot.material = self.stand_in

    def _inject(self, material, code, colour, alpha, translucent):
        tree = material.node_tree
        outputs = [n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
        added = []

        def node(kind):
            created = tree.nodes.new(kind)
            added.append(created)
            return created

        def math(operation, first, second=None, clamp=False):
            """A Math node of `operation` on sockets or constants."""
            made = node("ShaderNodeMath")
            made.operation = operation
            made.use_clamp = clamp
            for index, value in enumerate((first, second)):
                if value is None:
                    continue
                if isinstance(value, float):
                    made.inputs[index].default_value = value
                else:
                    tree.links.new(value, made.inputs[index])
            return made.outputs[0]

        def source(socket, kind):
            """What feeds `socket`: its link's source, or a constant node."""
            if socket.is_linked:
                return socket.links[0].from_socket
            constant = node("ShaderNodeRGB" if kind == "rgb" else "ShaderNodeValue")
            value = socket.default_value
            constant.outputs[0].default_value = (
                tuple(value) if kind == "rgb" else float(value)
            )
            return constant.outputs[0]

        output = next((n for n in outputs if n.is_active_output), None)
        if output is None:
            output = node("ShaderNodeOutputMaterial")
        links = [
            (link.from_socket, link.to_socket)
            for link in tree.links
            if link.to_node == output
        ]
        for link in [link for link in tree.links if link.to_node == output]:
            tree.links.remove(link)
        # The flat colour (alpha design D-8), through the importer's colour
        # chain, or the stand-in's white.
        emission = node("ShaderNodeEmission")
        emission.inputs["Strength"].default_value = 1.0
        if colour is None:
            emission.inputs["Color"].default_value = NO_MATERIAL_COLOR
        else:
            tree.links.new(source(colour, "rgb"), emission.inputs["Color"])
        # The alpha: a MASK material's chain, exactly 0 or 1, or 1.
        if alpha is None:
            one = node("ShaderNodeValue")
            one.outputs[0].default_value = 1.0
            opacity = one.outputs[0]
        else:
            opacity = source(alpha, "value")
        transparent = node("ShaderNodeBsdfTransparent")
        transparent.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        shown = node("ShaderNodeMixShader")
        tree.links.new(opacity, shown.inputs["Fac"])
        tree.links.new(transparent.outputs[0], shown.inputs[1])
        tree.links.new(emission.outputs[0], shown.inputs[2])
        # The two layers (alpha design D-6, D-12): the back render shows the
        # opaque surfaces with every translucent one a hole; the front render
        # shows the translucent surfaces, each opaque one held out, so its
        # alpha is the front layer's and its colour the front's alone.
        if translucent:
            back_surface = transparent.outputs[0]
            front_surface = shown.outputs[0]
        else:
            back_surface = shown.outputs[0]
            holdout = node("ShaderNodeHoldout")
            held = node("ShaderNodeMixShader")
            tree.links.new(opacity, held.inputs["Fac"])
            tree.links.new(transparent.outputs[0], held.inputs[1])
            tree.links.new(holdout.outputs[0], held.inputs[2])
            front_surface = held.outputs[0]
        # The surface gate (alpha design spike 2), in the order Cycles computes
        # the Mix shader's transparency: Cycles stops its passes exactly where
        # the opacity v > 0, which is where g = 1, so the surface it selects
        # writes each gated AOV exactly once and a hole writes none.
        saturated = math("ADD", opacity, 0.0, clamp=True)
        through = math("SUBTRACT", 1.0, saturated)
        opaque = math("SUBTRACT", 1.0, through)
        gate = math("SUBTRACT", 1.0, math("LESS_THAN", opaque, GATE_THRESHOLD))
        # The count render's surface (alpha design spike 3): a shading point
        # that still has a transparent closure, by Cycles' own test, adds 1
        # and lets the path through; any other emits nothing.
        average = math(
            "MULTIPLY", math("ADD", math("ADD", through, through), through), 1 / 3
        )
        closure = math("SUBTRACT", 1.0, math("LESS_THAN", average, CLOSURE_CUTOFF))
        if translucent:
            # The back render crosses every translucent surface, as a hole.
            closure = math("ADD", 1.0, 0.0)
        let_through = node("ShaderNodeBsdfTransparent")
        let_through.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        one_more = node("ShaderNodeEmission")
        one_more.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        one_more.inputs["Strength"].default_value = 1.0
        crossed = node("ShaderNodeAddShader")
        tree.links.new(let_through.outputs[0], crossed.inputs[0])
        tree.links.new(one_more.outputs[0], crossed.inputs[1])
        stopped = node("ShaderNodeEmission")
        stopped.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        stopped.inputs["Strength"].default_value = 0.0
        counted = node("ShaderNodeMixShader")
        tree.links.new(math("SUBTRACT", 1.0, closure), counted.inputs["Fac"])
        tree.links.new(crossed.outputs[0], counted.inputs[1])
        tree.links.new(stopped.outputs[0], counted.inputs[2])
        # One shared switch of two values: back, front or count, the count
        # also zeroing every AOV and the occlusion distance.
        switch = node("ShaderNodeGroup")
        switch.node_tree = self.switch
        layered = node("ShaderNodeMixShader")
        tree.links.new(switch.outputs["front"], layered.inputs["Fac"])
        tree.links.new(back_surface, layered.inputs[1])
        tree.links.new(front_surface, layered.inputs[2])
        chosen = node("ShaderNodeMixShader")
        tree.links.new(switch.outputs["count"], chosen.inputs["Fac"])
        tree.links.new(layered.outputs[0], chosen.inputs[1])
        tree.links.new(counted.outputs[0], chosen.inputs[2])
        tree.links.new(chosen.outputs[0], output.inputs["Surface"])
        rendering = math("SUBTRACT", 1.0, switch.outputs["count"])
        front_on = math("MULTIPLY", switch.outputs["front"], rendering)
        back_on = math("SUBTRACT", rendering, front_on)
        if translucent:
            back_kept = math("MULTIPLY", 0.0, back_on)
            front_kept = math("MULTIPLY", gate, front_on)
        else:
            back_kept = math("MULTIPLY", gate, back_on)
            front_kept = math("MULTIPLY", 0.0, front_on)
        kept = math("ADD", back_kept, front_kept)

        def aov(name, value):
            written = node("ShaderNodeOutputAOV")
            written.aov_name = name
            if name == "normal":
                scaled = node("ShaderNodeVectorMath")
                scaled.operation = "SCALE"
                tree.links.new(value, scaled.inputs[0])
                tree.links.new(kept, scaled.inputs["Scale"])
                tree.links.new(scaled.outputs[0], written.inputs["Color"])
            else:
                tree.links.new(math("MULTIPLY", value, kept), written.inputs["Value"])

        # A glTF material's code is its index plus 1, exact in a float.
        identity = node("ShaderNodeValue")
        identity.outputs[0].default_value = float(code)

        def gated(name, value, by):
            written = node("ShaderNodeOutputAOV")
            written.aov_name = name
            tree.links.new(math("MULTIPLY", value, by), written.inputs["Value"])

        gated("matid", identity.outputs[0], back_kept)
        gated("front_matid", identity.outputs[0], front_kept)
        for name, by in (("hit", back_kept), ("front_hit", front_kept)):
            hit = node("ShaderNodeOutputAOV")
            hit.aov_name = name
            tree.links.new(by, hit.inputs["Value"])
        # The shade (material styling design D-9); the stand-in for surfaces
        # without a material takes the global values. The occlusion distance
        # is gated too, so a hole runs no occlusion (alpha design D-7).
        values = self.own.get(code - 1, self.shade)
        outside = node("ShaderNodeAmbientOcclusion")
        inside = node("ShaderNodeAmbientOcclusion")
        distance = math("MULTIPLY", kept, float(values["ao_distance_m"]))
        distance.node.label = "moskophoros.ao_distance_m"
        for ao, is_inside in ((outside, False), (inside, True)):
            ao.samples = self.shade["ao_samples"]
            ao.inside = is_inside
            ao.only_local = False
            tree.links.new(distance, ao.inputs["Distance"])
        occlusion = node("ShaderNodeMath")
        occlusion.label = "moskophoros.occlusion_weight"
        occlusion.operation = "MULTIPLY"
        occlusion.inputs[1].default_value = values["occlusion_weight"]
        tree.links.new(outside.outputs["AO"], occlusion.inputs[0])
        convexity = node("ShaderNodeMath")
        convexity.label = "moskophoros.convexity"
        convexity.operation = "SUBTRACT"
        convexity.inputs[0].default_value = 1.0
        tree.links.new(inside.outputs["AO"], convexity.inputs[1])
        shade = node("ShaderNodeMath")
        shade.label = "moskophoros.convexity_weight"
        shade.operation = "MULTIPLY_ADD"
        shade.use_clamp = True
        shade.inputs[1].default_value = values["convexity_weight"]
        tree.links.new(convexity.outputs[0], shade.inputs[0])
        tree.links.new(occlusion.outputs[0], shade.inputs[2])
        gated("shade", shade.outputs[0], back_kept)
        gated("front_shade", shade.outputs[0], front_kept)
        # The shading normal, the model's interpolated vertex normal, in the
        # camera's space; no material property reaches it (D-2, D-16).
        geometry = node("ShaderNodeNewGeometry")
        transform = node("ShaderNodeVectorTransform")
        transform.vector_type = "NORMAL"
        transform.convert_from = "WORLD"
        transform.convert_to = "CAMERA"
        tree.links.new(geometry.outputs["Normal"], transform.inputs["Vector"])
        aov("normal", transform.outputs["Vector"])
        # The distance along the camera's viewing axis (D-10).
        camera = node("ShaderNodeCameraData")
        aov("depth", camera.outputs["View Z Depth"])
        self.trees.append((tree, added, links))

    def restore(self):
        for tree, added, links in reversed(self.trees):
            for created in added:
                tree.nodes.remove(created)
            for from_socket, to_socket in links:
                tree.links.new(from_socket, to_socket)
        for slot in self.slots:
            slot.material = None
        for data in self.appended:
            data.materials.pop()
        if self.stand_in is not None:
            bpy.data.materials.remove(self.stand_in)
        if self.switch is not None:
            bpy.data.node_groups.remove(self.switch)
        layer = bpy.context.view_layer
        for aov in reversed(self.aovs):
            layer.aovs.remove(aov)
        self.trees, self.slots, self.appended, self.aovs = [], [], [], []
        self.stand_in = None
        self.switch = None


def save_exr(scene, path):
    """Save the render result, every pass and AOV, as `_EXR_SETTINGS` say,
    and restore the image settings exactly, in the reverse order."""
    image = scene.render.image_settings
    names = [name for name, _ in _EXR_SETTINGS] + ["color_mode"]
    saved = [(name, getattr(image, name)) for name in names]
    try:
        for name, value in _EXR_SETTINGS:
            setattr(image, name, value)
        bpy.data.images["Render Result"].save_render(path, scene=scene)
    finally:
        # The media type first: it decides which formats are allowed.
        for name, value in saved:
            setattr(image, name, value)
    restored = [(name, getattr(image, name)) for name in names]
    if restored != saved:
        raise ScriptError(f"the image settings were not restored: {restored}")


_EXR_MAGIC = b"\x76\x2f\x31\x01"
_EXR_FLOAT = 2


def _exr_header(data, at):
    """One header's {attribute: bytes}, and the offset after it."""
    attributes = {}
    while data[at] != 0:
        end = data.index(b"\0", at)
        name = data[at:end].decode("ascii")
        end_type = data.index(b"\0", end + 1)
        (size,) = struct.unpack_from("<i", data, end_type + 1)
        start = end_type + 5
        attributes[name] = data[start : start + size]
        at = start + size
    return attributes, at + 1


def read_exr(path, width, height, wanted):
    """{channel: array('f') of width·height values, top row first} for each
    name in `wanted`, from an uncompressed scanline OpenEXR of 32-bit float
    channels, single- or multi-part, as `save_exr` writes it."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:4] != _EXR_MAGIC:
        raise ScriptError(f"the render {path} is not an OpenEXR file")
    flags = struct.unpack_from("<I", data, 4)[0]
    if flags & 0x200:
        raise ScriptError(f"the render {path} is tiled")
    multipart = bool(flags & 0x1000)
    at, headers = 8, []
    while True:
        attributes, at = _exr_header(data, at)
        headers.append(attributes)
        if not multipart or data[at] == 0:
            break
    if multipart:
        at += 1
    parts = []
    for attributes in headers:
        if attributes["compression"][0] != 0:
            raise ScriptError(f"the render {path} is compressed")
        xmin, ymin, xmax, ymax = struct.unpack("<iiii", attributes["dataWindow"])
        if (xmax - xmin + 1, ymax - ymin + 1) != (width, height):
            raise ScriptError(
                f"the render is {(xmax - xmin + 1, ymax - ymin + 1)}, "
                f"not {(width, height)}"
            )
        offsets = struct.unpack_from(f"<{height}Q", data, at)
        at += 8 * height
        channels, raw = [], attributes["channels"]
        position = 0
        while raw[position] != 0:
            end = raw.index(b"\0", position)
            (kind,) = struct.unpack_from("<i", raw, end + 1)
            channels.append((raw[position:end].decode("ascii"), kind))
            position = end + 17
        parts.append((ymin, offsets, channels))
    found = {}
    every = [name for _, _, channels in parts for name, _ in channels]
    for ymin, offsets, channels in parts:
        names = [name for name, _ in channels]
        for name, kind in channels:
            if name in wanted and kind != _EXR_FLOAT:
                raise ScriptError(f"the render's {name} is not 32-bit")
        if not any(name in wanted for name in names):
            continue
        # Every channel here is 32-bit or skipped by its size, in name order.
        sizes = [4 if kind in (0, _EXR_FLOAT) else 2 for _, kind in channels]
        rows = {name: [None] * height for name in names if name in wanted}
        skip = 4 if multipart else 0
        for offset in offsets:
            (y,) = struct.unpack_from("<i", data, offset + skip)
            start = offset + skip + 8
            for (name, _), size in zip(channels, sizes, strict=True):
                if name in rows:
                    values = array("f")
                    values.frombytes(data[start : start + 4 * width])
                    rows[name][y - ymin] = values
                start += size * width
        for name, lines in rows.items():
            if any(line is None for line in lines):
                raise ScriptError(f"the render's {name} is truncated")
            merged = array("f")
            for line in lines:
                merged.extend(line)
            found[name] = merged
    missing = [name for name in wanted if name not in found]
    if missing:
        raise ScriptError(f"the render has no channel {missing[0]}; it has {every}")
    if sys.byteorder != "little":
        for values in found.values():
            values.byteswap()
    return found


def read_targa(path, width, height):
    """The rows of an uncompressed 32-bit TGA, top first, as RGBA bytes."""
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) < 18 or data[2] != 2 or data[16] != 32:
        raise ScriptError(f"the render {path} is not a 32-bit TGA")
    size = (data[12] | data[13] << 8, data[14] | data[15] << 8)
    if size != (width, height):
        raise ScriptError(f"the render is {size}, not {(width, height)}")
    start = 18 + data[0]
    pixels = bytearray(data[start : start + width * height * 4])
    if len(pixels) != width * height * 4:
        raise ScriptError(f"the render {path} is truncated")
    pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]
    stride = width * 4
    rows = [pixels[y * stride : (y + 1) * stride] for y in range(height)]
    if not data[17] & 0x20:
        rows.reverse()
    return rows


def write_png(path, width, rows, bits=8, level=9):
    """An RGBA PNG of `rows` at `bits` per sample, every row unfiltered and
    compressed at zlib `level`, with nothing but its pixels."""

    def chunk(kind, body):
        crc = zlib.crc32(kind + body)
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, len(rows), bits, 6, 0, 0, 0)
    raw = b"".join(b"\0" + bytes(row) for row in rows)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", header))
        handle.write(chunk(b"IDAT", zlib.compress(raw, level)))
        handle.write(chunk(b"IEND", b""))


def _srgb(value):
    """The `Standard` transform's sRGB encoding of a linear value in [0, 1]."""
    if value <= 0.0031308:
        return 12.92 * value
    return 1.055 * value ** (1 / 2.4) - 0.055


def shade_byte(value):
    """The 8-bit shade the `Standard` transform gives the linear `value`:
    `floor(255 · sRGB(v) + ½)`, `v` clamped to [0, 1] (0.25 gives 137)."""
    return math.floor(255 * _srgb(min(max(value, 0.0), 1.0)) + 0.5)


def material_code(value, codes):
    """The material-ID code an AOV `value` holds: an integer of `codes`, the
    model's codes and the background's, exactly. Anything else is refused."""
    if not math.isfinite(value) or value != int(value) or int(value) not in codes:
        raise ScriptError(f"the render's material-ID AOV holds {value!r}, no code")
    return int(value)


def coverage(alpha, width, where):
    """Each row of the render's float `alpha` as bytes, 255 where the pixel
    shows a surface and 0 where it shows none. A surface is opaque or a
    `MASK` material's whole texel, so its alpha is exactly 1, and a hole's
    0; any other value is refused."""
    if not set(alpha) <= {0.0, 1.0}:
        index = _first_other(alpha)
        raise ScriptError(
            f"{where}: the render's alpha at pixel "
            f"{(index % width, index // width)} is {alpha[index]!r}, not a whole "
            "opaque surface or none"
        )
    # 0.0 and 1.0 differ in their 32-bit floats' high byte: 0x00 and 0x3F.
    data = array("f", alpha)
    if sys.byteorder != "little":
        data.byteswap()
    covered = data.tobytes()[3::4].translate(_COVERED)
    stride = width
    return [covered[y : y + stride] for y in range(0, len(covered), stride)]


_COVERED = bytes(255 if byte == 0x3F else 0 for byte in range(256))


def _first_other(values):
    """The index of the first value that is neither 0 nor 1, NaN included."""
    return next(i for i, value in enumerate(values) if value not in (0.0, 1.0))


def check_hits(hit, covered, width, where):
    """Refuse a frame whose gated hit AOV is not exactly 0 or 1 at every
    pixel, or whose hits are not exactly the colour's surfaces, `covered`:
    the surface gate selects each surface exactly once (alpha design
    spike 2)."""
    if not set(hit) <= {0.0, 1.0}:
        index = _first_other(hit)
        raise ScriptError(
            f"{where}: the surface gate's hit at pixel "
            f"{(index % width, index // width)} is {hit[index]!r}, not exactly 0 "
            "or 1"
        )
    _check_coverage("surface gate", bytes(map(bool, hit)), covered, width, where)


def check_count(red, width, place):
    """Refuse a frame where the count render's `red`, the surfaces each camera
    path crossed that still let light through, reaches `LAYER_LIMIT` + 1:
    Cycles stopped that path before its end, so the frame would render
    wrong (alpha design spike 3). `place` names the frame."""
    deepest = max(red, default=0.0)
    if deepest >= LAYER_LIMIT + 1:
        index = red.index(deepest)
        raise ScriptError(
            f"{place}: a camera path at pixel {(index % width, index // width)} "
            f"crossed more than {LAYER_LIMIT} surfaces that still let light "
            f"through, which the capture cannot render (the limit is "
            f"{LAYER_LIMIT})"
        )


def _masked(data, mask):
    """`data` with every byte where `mask`, of 0s and 255s, is 0 set to 0."""
    size = len(data)
    kept = int.from_bytes(data, "little") & int.from_bytes(mask, "little")
    return kept.to_bytes(size, "little")


def _per_channel(covered):
    """Per-pixel coverage bytes repeated for each of the 4 channels."""
    mask = bytearray(4 * len(covered))
    for channel in range(4):
        mask[channel::4] = covered
    return bytes(mask)


def _split(data, stride):
    return [bytearray(data[y : y + stride]) for y in range(0, len(data), stride)]


def _first_difference(found, expected):
    return next(
        x for x, (a, b) in enumerate(zip(found, expected, strict=True)) if a != b
    )


def colour_rows(rows, covered, where):
    """The colour buffer's rows: the render's 8-bit straight sRGB `rows`
    where `covered` shows a surface, and `(0, 0, 0, 0)` elsewhere."""
    for y, (row, hit) in enumerate(zip(rows, covered, strict=True)):
        if row[3::4] != hit:
            x = _first_difference(row[3::4], hit)
            raise ScriptError(
                f"{where}: the colour at pixel {(x, y)} has 8-bit alpha "
                f"{row[4 * x + 3]}, but the render's alpha there is "
                f"{1.0 if hit[x] else 0.0}"
            )
    width = len(rows[0]) if rows else 0
    present = b"".join(covered)
    return _split(_masked(b"".join(rows), _per_channel(present)), width)


def id_and_shade_rows(ids, shades, covered, width, codes, where):
    """The material-ID rows (red the code's high byte, green its low byte,
    blue 0, alpha 255) and the shade rows (`R = G = B`, alpha 255) from the
    render's float AOVs `ids` and `shades`, where `covered` shows a surface,
    and `(0, 0, 0, 0)` elsewhere. A surface must hold one of `codes`, and no
    surface the background's code."""
    code = {value: material_code(value, codes | {ID_BACKGROUND}) for value in set(ids)}
    present = b"".join(covered)
    if len(code) <= 256:
        # Few codes: give each a byte, and translate it to each channel.
        values = list(code)
        index = {value: i for i, value in enumerate(values)}
        pixels = bytes(map(index.__getitem__, ids))

        def channel(of):
            table = bytes(of(code[value]) for value in values)
            return pixels.translate(table + bytes(256 - len(table)))

    else:

        def channel(of):
            table = {value: of(found) for value, found in code.items()}
            return bytes(map(table.__getitem__, ids))

    holds = channel(lambda found: 0 if found == ID_BACKGROUND else 255)
    if holds != present:
        index = _first_difference(holds, present)
        x, y = index % width, index // width
        raise ScriptError(
            f"{where}: the material ID at pixel {(x, y)} is "
            f"{code[ids[index]]}, but the colour there shows "
            f"{'a' if present[index] else 'no'} surface"
        )
    identity = bytearray(4 * len(present))
    identity[0::4] = channel(lambda found: found >> 8)
    identity[1::4] = channel(lambda found: found & 0xFF)
    identity[3::4] = present
    byte = {value: shade_byte(value) for value in set(shades)}
    shade = _masked(bytes(map(byte.__getitem__, shades)), present)
    level = bytearray(4 * len(present))
    for index in range(3):
        level[index::4] = shade
    level[3::4] = present
    return _split(identity, 4 * width), _split(level, 4 * width)


# The normal and depth buffers (lighting sheet design D-2, D-10, D-11): each
# a 16-bit RGBA PNG whose alpha is 65535 where the AOV holds a surface and
# whose every sample is 0 where it holds none. Their samples vary too finely
# to compress much, so they take zlib's fastest level.
COVERED = 0xFFFF
WIDE_LEVEL = 1


def _samples(values):
    """`values` as big-endian 16-bit PNG samples."""
    samples = array("H", values)
    if sys.byteorder == "little":
        samples.byteswap()
    return samples.tobytes()


def _rows(pixels, width, height):
    stride = width * 8
    return [pixels[y * stride : (y + 1) * stride] for y in range(height)]


# Coverage bytes 0 and 255 as 0 and 1.
_UNIT = bytes([0] + [1] * 255)


def _check_coverage(name, holds, surface, width, where):
    """Refuse a buffer whose surfaces `holds`, one byte per pixel, 1 for a
    surface and 0 for none, are not exactly the colour's, `surface`, its
    rows of 0 and 255."""
    expected = b"".join(surface).translate(_UNIT)
    if holds != expected:
        index = _first_difference(holds, expected)
        raise ScriptError(
            f"{where}: the {name} at pixel {(index % width, index // width)} "
            f"shows {'a' if holds[index] else 'no'} surface, but the colour "
            f"there shows {'a' if expected[index] else 'no'} surface"
        )


def write_normal(path, width, height, x, y, z, where, surface):
    """The normal buffer from the AOV's camera-space components. Cycles'
    camera looks along −Z, so the design's normal (+Z toward the viewer) is
    `(x, y, −z)`; each component n is stored as floor((n + 1) / 2 · 65535 +
    ½). A pixel the AOV left at (0, 0, 0) holds no surface, and the pixels
    holding one must be exactly the colour's, `surface`."""
    covered = list(map(any, zip(x, y, z, strict=True)))
    _check_coverage("normal", bytes(covered), surface, width, where)
    try:
        channels = [
            _samples(
                [
                    int((1 + sign * value) * 32767.5 + 0.5) if hit else 0
                    for value, hit in zip(values, covered, strict=True)
                ]
            )
            for values, sign in ((x, 1.0), (y, 1.0), (z, -1.0))
        ]
    except (ValueError, OverflowError):
        for index, (a, b, c) in enumerate(zip(x, y, z, strict=True)):
            if not all(math.isfinite(v) and abs(v) <= 1.00001 for v in (a, b, c)):
                raise ScriptError(
                    f"{where}: the normal at pixel {(index % width, index // width)} "
                    f"is {(a, b, -c)}, not a unit vector"
                ) from None
        raise
    alpha = _samples(COVERED if hit else 0 for hit in covered)
    pixels = bytearray(width * height * 8)
    for channel, samples in enumerate((*channels, alpha)):
        pixels[2 * channel :: 8] = samples[0::2]
        pixels[2 * channel + 1 :: 8] = samples[1::2]
    write_png(path, width, _rows(pixels, width, height), bits=16, level=WIDE_LEVEL)


def write_depth(path, width, height, view_z, ground_view_z, where, surface):
    """The depth buffer from the AOV's view depth: each covered pixel's depth
    toward the viewer from the ground point, `ground_view_z − view_z`, in
    meters, stored as the big-endian bits of a 32-bit float in red (high
    half) and green (low half), blue 0. A pixel the AOV left at 0 holds no
    surface, since the camera's near plane is in front of every surface, and
    the pixels holding one must be exactly the colour's, `surface`."""
    _check_coverage("depth", bytes(map(bool, view_z)), surface, width, where)
    depths = array("f", (ground_view_z - value if value else 0.0 for value in view_z))
    if not all(map(math.isfinite, depths)):
        index = next(i for i, value in enumerate(depths) if not math.isfinite(value))
        raise ScriptError(
            f"{where}: the depth at pixel {(index % width, index // width)} "
            f"is {depths[index]}"
        )
    if sys.byteorder == "little":
        depths.byteswap()
    bits = depths.tobytes()
    alpha = _samples(COVERED if value else 0 for value in view_z)
    pixels = bytearray(width * height * 8)
    for byte in range(4):
        pixels[byte::8] = bits[byte::4]
    pixels[6::8] = alpha[0::2]
    pixels[7::8] = alpha[1::2]
    write_png(path, width, _rows(pixels, width, height), bits=16, level=WIDE_LEVEL)


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
    corner (gx·s, gy·s), as if the subject were turned by `rotation_deg`, and
    return the ground point's camera depth.

    Turning the subject by a about the vertical axis through the ground
    point is the same image as turning the camera by −a around it, since
    the colour is flat and unlit.
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
    # The ground point's distance along the viewing axis, the camera depth
    # the depth buffer is relative to (lighting sheet design D-10). It is
    # taken from the transform Blender stores, in single precision, which is
    # the camera Cycles measures View Z Depth from, not from `center`.
    stored = camera.matrix_world
    axis = [stored[row][2] for row in range(3)]
    length = math.sqrt(sum(value * value for value in axis))
    position = [stored[row][3] for row in range(3)]
    return sum(
        (position[i] - target) * axis[i] / length
        for i, target in enumerate(_blender(ground))
    )


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
    """Render every requested frame to color/NNNNNN.png, and its other
    buffers (`BUFFERS`) to their directories, in request order."""
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
    codes, table = material_codes(document)
    surfaces = Surfaces(scene, objects, codes, settings["shade"], document)
    known = {entry["id"] for entry in table}
    width, height, _, _ = frame_size(settings)
    for name in BUFFERS:
        os.makedirs(os.path.join(job["output_dir"], name), exist_ok=False)
    # The render's intermediate files live in the phase directory, so they
    # share the command workspace's lifetime: a temporary workspace is
    # deleted whatever happens to Blender, and a retained one keeps them.
    scratch = os.path.join(job["output_dir"], SCRATCH)
    os.mkdir(scratch)

    ordinals = {}
    for ordinal, frame in enumerate(job["frames"]):
        ordinals.setdefault(frame["address"]["clip"], []).append((ordinal, frame))
    paths = {}
    surfaces.apply()
    try:
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
                ground_view_z = place_camera(
                    camera, settings, rotation, reach(objects, depsgraph, ground)
                )
                relative = {name: f"{name}/{ordinal:06d}.png" for name in BUFFERS}
                address = frame["address"]
                render_frame(
                    scene,
                    surfaces,
                    scratch,
                    (width, height),
                    job,
                    relative,
                    known,
                    ground_view_z,
                    f"frame {ordinal}",
                    f"{job['source']['path']}: clip {address['clip']!r}, "
                    f"direction {address['direction']}, frame {ordinal} "
                    f"(t = {address['time_s']!r} s)",
                )
                paths[ordinal] = relative
    finally:
        surfaces.restore()
    os.rmdir(scratch)
    return (
        [
            {"address": frame["address"], "buffers": paths[ordinal]}
            for ordinal, frame in enumerate(job["frames"])
        ],
        {
            "blender": ".".join(map(str, bpy.app.version)),
            "renderer": RENDERER,
            "color": dict(COLOR),
            "shade": dict(SHADE),
        },
        table,
    )


def render_frame(
    scene, surfaces, scratch, size, job, relative, codes, ground_view_z, where, place
):
    """The frame's back and front buffers: the back render's colour (its
    8-bit TGA through the `Standard` transform), material ID and shade; the
    front render's straight colour (its TGA), 16-bit alpha, material ID and
    shade; and the front-most surface's normal and depth. A count render
    after them refuses a frame too deep to render (`check_count`)."""
    width, height = size
    layer = bpy.context.view_layer.name
    target = os.path.join(scratch, "capture.tga")
    exr = os.path.join(scratch, "capture.exr")
    front_target = os.path.join(scratch, "front.tga")
    front_exr = os.path.join(scratch, "front.exr")
    count = os.path.join(scratch, "count.exr")
    try:
        surfaces.mode("back")
        scene.render.filepath = target
        bpy.ops.render.render(write_still=True)
        save_exr(scene, exr)
        if surfaces.translucent:
            surfaces.mode("front")
            scene.render.filepath = front_target
            # One transparent bounce more than the limit. Cycles shades the
            # surface a path ends at after its last bounce without closures,
            # so a holdout there would hold nothing out; the count render
            # refuses any path crossing more than LAYER_LIMIT surfaces that
            # let light through, so here the path always reaches the opaque
            # surface it ends at, and holds it out.
            limits = (LAYER_LIMIT + 1, LAYER_LIMIT + 1)
            cycles = scene.cycles
            cycles.min_transparent_bounces, cycles.transparent_max_bounces = limits
            try:
                bpy.ops.render.render(write_still=True)
            finally:
                cycles.min_transparent_bounces = COLOR["min_transparent_bounces"]
                cycles.transparent_max_bounces = COLOR["transparent_max_bounces"]
            save_exr(scene, front_exr)
        surfaces.mode("count")
        bpy.ops.render.render(write_still=False)
        save_exr(scene, count)
    finally:
        surfaces.mode("back")
    red = f"{layer}.Combined.R"
    check_count(read_exr(count, width, height, [red])[red], width, place)
    os.remove(count)
    rows = read_targa(target, width, height)
    os.remove(target)
    names = (
        [f"{layer}.Combined.A", f"{layer}.matid.X", f"{layer}.shade.X"]
        + [f"{layer}.normal.{axis}" for axis in "RGB"]
        + [f"{layer}.depth.X", f"{layer}.hit.X"]
    )
    channels = read_exr(exr, width, height, names)
    os.remove(exr)
    alpha, ids, shades, x, y, z, view_z, hit = (channels[name] for name in names)
    del channels
    output = job["output_dir"]
    covered = coverage(alpha, width, where)
    check_hits(hit, covered, width, where)
    write_png(
        os.path.join(output, relative["color"]),
        width,
        colour_rows(rows, covered, where),
    )
    del rows
    id_rows, shade_rows = id_and_shade_rows(ids, shades, covered, width, codes, where)
    write_png(os.path.join(output, relative["matid"]), width, id_rows)
    write_png(os.path.join(output, relative["shade"]), width, shade_rows)
    del id_rows, shade_rows, ids, shades
    if surfaces.translucent:
        front_rows = read_targa(front_target, width, height)
        os.remove(front_target)
        names = (
            [f"{layer}.Combined.A", f"{layer}.front_matid.X", f"{layer}.front_shade.X"]
            + [f"{layer}.normal.{axis}" for axis in "RGB"]
            + [f"{layer}.depth.X", f"{layer}.front_hit.X"]
        )
        channels = read_exr(front_exr, width, height, names)
        os.remove(front_exr)
        f_alpha, f_ids, f_shades, fx, fy, fz, f_view_z, f_hit = (
            channels[name] for name in names
        )
        del channels
        front = front_presence(f_hit, f_alpha, width, where)
        write_png(
            os.path.join(output, relative["front_color"]),
            width,
            front_colour_rows(front_rows, front, width),
        )
        del front_rows
        write_front_alpha(
            os.path.join(output, relative["front_alpha"]), width, height, f_alpha, front
        )
        id_rows, shade_rows = id_and_shade_rows(
            f_ids, f_shades, front, width, codes, where
        )
        write_png(os.path.join(output, relative["front_matid"]), width, id_rows)
        write_png(os.path.join(output, relative["front_shade"]), width, shade_rows)
        del id_rows, shade_rows, f_ids, f_shades
        # The maps describe the front-most surface (alpha design D-11).
        x, y, z, view_z = (
            frontmost(f, b, front)
            for f, b in ((fx, x), (fy, y), (fz, z), (f_view_z, view_z))
        )
        surface = [
            bytes(a | b for a, b in zip(back_row, front_row, strict=True))
            for back_row, front_row in zip(covered, front, strict=True)
        ]
    else:
        nothing = [bytes(4 * width)] * height
        for name in ("front_color", "front_matid", "front_shade"):
            write_png(os.path.join(output, relative[name]), width, nothing)
        write_png(
            os.path.join(output, relative["front_alpha"]),
            width,
            [bytes(8 * width)] * height,
            bits=16,
            level=WIDE_LEVEL,
        )
        surface = covered
    write_normal(
        os.path.join(output, relative["normal"]),
        width,
        height,
        x,
        y,
        z,
        where,
        surface,
    )
    write_depth(
        os.path.join(output, relative["depth"]),
        width,
        height,
        view_z,
        ground_view_z,
        where,
        surface,
    )


def front_presence(hit, alpha, width, where):
    """The front layer's rows of 255 where the gated front hit is 1 and 0
    where it is 0: its presence, from Blender's float data. A hit must be
    exactly 0 or 1, and the front render's alpha must be above 0 exactly
    where it is 1."""
    if not set(hit) <= {0.0, 1.0}:
        index = _first_other(hit)
        raise ScriptError(
            f"{where}: the front gate's hit at pixel "
            f"{(index % width, index // width)} is {hit[index]!r}, not exactly 0 "
            "or 1"
        )
    present = bytes(map(bool, hit))
    shown = bytes(value > 0.0 for value in alpha)
    if present != shown:
        index = _first_difference(present, shown)
        raise ScriptError(
            f"{where}: the front layer at pixel {(index % width, index // width)} "
            f"has alpha {alpha[index]!r} but hit {hit[index]!r}"
        )
    rows = present.translate(_FULL)
    return [rows[y : y + width] for y in range(0, len(rows), width)]


_FULL = bytes([0] + [255] * 255)


def front_colour_rows(rows, front, width):
    """The front colour's rows: the front render's straight 8-bit sRGB where
    the front layer is present, with alpha 255, and `(0, 0, 0, 0)`
    elsewhere."""
    present = b"".join(front)
    pixels = bytearray(_masked(b"".join(rows), _per_channel(present)))
    pixels[3::4] = present
    return _split(pixels, 4 * width)


def write_front_alpha(path, width, height, alpha, front):
    """The front alpha buffer: R the front layer's alpha `f` as
    `q = floor(65535 · f + ½)`, G = B = 0 and alpha 65535 where the front
    layer is present, and 0 everywhere else."""
    present = b"".join(front)
    q = _samples(
        math.floor(65535 * value + 0.5) if shown else 0
        for value, shown in zip(alpha, present, strict=True)
    )
    covered = _samples(COVERED if shown else 0 for shown in present)
    pixels = bytearray(width * height * 8)
    pixels[0::8] = q[0::2]
    pixels[1::8] = q[1::2]
    pixels[6::8] = covered[0::2]
    pixels[7::8] = covered[1::2]
    write_png(path, width, _rows(pixels, width, height), bits=16, level=WIDE_LEVEL)


def frontmost(front_values, back_values, front):
    """The front render's float values where the front layer is present, else
    the back render's."""
    mask = _per_channel(b"".join(front))
    size = len(mask)
    taken = int.from_bytes(front_values.tobytes(), "little") & int.from_bytes(
        mask, "little"
    )
    kept = int.from_bytes(back_values.tobytes(), "little") & ~int.from_bytes(
        mask, "little"
    )
    merged = array("f")
    merged.frombytes((taken | kept).to_bytes(size, "little"))
    return merged


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
            frames, backend, materials = render_frames(job, document, record_statics())

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
    else:
        result["materials"] = materials
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
