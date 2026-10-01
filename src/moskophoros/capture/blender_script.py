"""Run one capture phase inside Blender: `blender ... --python <this> -- <job.json>`.

This is the only module that imports `bpy`, and nothing in the package
imports it. It runs under Blender's bundled Python and uses only `bpy` and
the standard library. It follows design §Capture, §Capture job and result
contract, §Clips and sampling, §Root motion, §Scale and ground point and
§Camera and directions.

Slice 1 implements measure mode; a render job is refused as unsupported.

Identity mapping: the script imports a private copy of the source in which
every node is renamed `moskophoros.node.<index>` and every animation
`moskophoros.animation.<index>`. Blender names objects and bones after nodes
and actions after animations, so original indices map exactly, whatever the
original names, and an index with no imported counterpart fails by name.

Static state: the importer evaluates animation while importing, so the
values it leaves are not the file's static ones. The script first imports
the copy without animations and records every object's transform and every
shape key's value, then imports it with animations and restores those
values before each clip.

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
    if job["mode"] != "measure":
        raise ScriptError(f"{job['mode']} jobs are not supported yet")
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
    for key in ("pixels_per_meter", "cell", "ground_px"):
        _require(settings[key] is None, f"settings.{key} is set in a measure job")

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

    frames = job["frames"]
    _require(isinstance(frames, list) and frames, "frames")
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


def private_copy(document, rest, source, scene, animations):
    """The GLB bytes Blender imports: nodes and animations renamed by index,
    the job's scene made the default, and external files given absolute
    paths. Without `animations`, it has none."""
    document = json.loads(json.dumps(document))
    for index, node in enumerate(document.get("nodes", [])):
        node["name"] = NODE_NAME.format(index)
    if animations:
        for index, animation in enumerate(document.get("animations", [])):
            animation["name"] = ANIMATION_NAME.format(index)
    else:
        document.pop("animations", None)
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


def import_glb(data, directory, name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = os.path.join(directory, name)
    with open(path, "wb") as handle:
        handle.write(data)
    result = bpy.ops.import_scene.gltf(filepath=path)
    if "FINISHED" not in result:
        raise ScriptError(f"Blender could not import the model: {sorted(result)}")


# Static state


def record_statics():
    """Every object's transform and every mesh's shape key values."""
    statics = {}
    for obj in bpy.data.objects:
        keys = ()
        if obj.type == "MESH" and obj.data.shape_keys is not None:
            keys = tuple(block.value for block in obj.data.shape_keys.key_blocks)
        statics[obj.name] = {
            "rotation_mode": obj.rotation_mode,
            "location": tuple(obj.location),
            "rotation_quaternion": tuple(obj.rotation_quaternion),
            "rotation_euler": tuple(obj.rotation_euler),
            "rotation_axis_angle": tuple(obj.rotation_axis_angle),
            "scale": tuple(obj.scale),
            "shape_keys": keys,
        }
    return statics


def reset(statics):
    """Stop every animation and return everything to its static state."""
    for data in (*bpy.data.objects, *bpy.data.shape_keys):
        if data.animation_data is not None:
            data.animation_data.action = None
            data.animation_data.use_nla = False
    for obj in bpy.data.objects:
        static = statics.get(obj.name)
        if static is None:
            raise ScriptError(f"object {obj.name!r} has no recorded static state")
        obj.rotation_mode = static["rotation_mode"]
        for key in (
            "location",
            "rotation_quaternion",
            "rotation_euler",
            "rotation_axis_angle",
            "scale",
        ):
            setattr(obj, key, static[key])
        if obj.pose is not None:
            for bone in obj.pose.bones:
                bone.location = (0.0, 0.0, 0.0)
                bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                bone.rotation_euler = (0.0, 0.0, 0.0)
                bone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
                bone.scale = (1.0, 1.0, 1.0)
        if obj.type == "MESH" and obj.data.shape_keys is not None:
            blocks = obj.data.shape_keys.key_blocks
            if len(blocks) != len(static["shape_keys"]):
                raise ScriptError(f"object {obj.name!r}'s shape keys changed")
            for block, value in zip(blocks, static["shape_keys"], strict=True):
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
    unassigned = {slot.identifier for slot in action.slots} - assigned
    if unassigned:
        raise ScriptError(
            f"animation {animation_index}'s targets {sorted(unassigned)} have no "
            "imported counterpart"
        )


# Evaluation


def evaluate(scene, fps, time_s):
    frame = time_s * fps
    whole = math.floor(frame)
    scene.frame_set(int(whole), subframe=frame - whole)
    return bpy.context.evaluated_depsgraph_get()


def subject_objects(document, scene_index):
    """The objects created from the selected scene's mesh nodes."""
    nodes = document.get("nodes", [])
    scenes = document.get("scenes", [])
    pending = list(scenes[scene_index].get("nodes", []))
    meshes = []
    while pending:
        index = pending.pop()
        node = nodes[index]
        if "mesh" in node:
            meshes.append(index)
        pending.extend(node.get("children", []))
    view_layer = bpy.context.view_layer
    objects = []
    for index in sorted(meshes):
        obj = bpy.data.objects.get(NODE_NAME.format(index))
        if obj is None or obj.type != "MESH" or obj.name not in view_layer.objects:
            raise ScriptError(f"mesh node {index} has no imported mesh object")
        objects.append(obj)
    return objects


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
    objects = subject_objects(document, job["source"]["scene"])

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
        for time_s in sorted(angles):
            points = vertices(objects, evaluate(scene, fps, time_s))
            heights = [y for _, y, _ in points]
            height = max(heights) - min(heights) if heights else 0.0
            for direction, angle in angles[time_s].items():
                measured[(clip["name"], direction, time_s)] = (
                    bounds(points, ground, angle + yaw, pitch),
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
    scene_index = job["source"]["scene"]
    if scene_index >= len(document.get("scenes", [])):
        raise ScriptError(f"{source} has no scene {scene_index}")

    with tempfile.TemporaryDirectory(prefix="moskophoros-") as directory:
        import_glb(
            private_copy(document, rest, source, scene_index, False),
            directory,
            "static.glb",
        )
        statics = record_statics()
        import_glb(
            private_copy(document, rest, source, scene_index, True),
            directory,
            "animated.glb",
        )
        frames, roots = measure(job, document, statics)

    result = {
        "schema": RESULT_SCHEMA,
        "mode": "measure",
        "job_sha256": canonical_sha256(job),
        "source_sha256": job["source"]["sha256"],
        "backend": {"blender": ".".join(map(str, bpy.app.version))},
        "frames": frames,
        "roots": roots,
    }
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
