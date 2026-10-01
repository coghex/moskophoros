"""The fixture writer's skins, morph targets and arbitrary meshes."""

import json
import struct

from glb_writer import FLOAT, UNSIGNED_SHORT, GlbWriter

from moskophoros.gltf import Root, read_glb


def chunks(path):
    data = path.read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    document = json.loads(data[20 : 20 + length])
    return document, data[20 + length + 8 :]


def values(document, binary, index):
    accessor = document["accessors"][index]
    view = document["bufferViews"][accessor["bufferView"]]
    width = {"SCALAR": 1, "VEC3": 3, "VEC4": 4, "MAT4": 16}[accessor["type"]]
    code = {FLOAT: "f", UNSIGNED_SHORT: "H"}[accessor["componentType"]]
    flat = struct.unpack_from(
        f"<{accessor['count'] * width}{code}", binary, view["byteOffset"]
    )
    return [flat[i : i + width] for i in range(0, len(flat), width)]


def test_a_mesh_with_morph_targets_and_skinning(tmp_path):
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 0.0)]],
        weights=[0.25],
        joints=[(0, 0, 0, 0), (0, 0, 0, 0), (1, 0, 0, 0)],
        skin_weights=[(1.0, 0.0, 0.0, 0.0)] * 3,
    )
    joint = model.node("joint")
    skin = model.skin([joint], [(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -1, 0, 1)])
    node = model.node(
        "body",
        mesh=mesh,
        skin=skin,
        rotation=(0.0, 0.0, 0.0, 1.0),
        scale=(2.0, 2.0, 2.0),
        weights=[0.75],
    )
    model.scene([joint, node])
    document, binary = chunks(model.write(tmp_path))

    (primitive,) = document["meshes"][mesh]["primitives"]
    attributes = primitive["attributes"]
    assert values(document, binary, attributes["POSITION"])[2] == (0.0, 2.0, 0.0)
    assert document["accessors"][attributes["POSITION"]]["max"] == [1.0, 2.0, 0.0]
    joints = document["accessors"][attributes["JOINTS_0"]]
    assert joints["componentType"] == UNSIGNED_SHORT
    assert values(document, binary, attributes["JOINTS_0"])[2] == (1, 0, 0, 0)
    (target,) = primitive["targets"]
    assert values(document, binary, target["POSITION"])[1] == (0.0, 0.5, 0.0)
    assert document["meshes"][mesh]["weights"] == [0.25]
    assert document["nodes"][node] == {
        "name": "body",
        "mesh": mesh,
        "rotation": [0.0, 0.0, 0.0, 1.0],
        "scale": [2.0, 2.0, 2.0],
        "weights": [0.75],
        "skin": skin,
    }
    (inverse,) = values(
        document, binary, document["skins"][skin]["inverseBindMatrices"]
    )
    assert inverse[13] == -1.0


def test_a_weights_channel_stores_one_weight_per_target_per_time(tmp_path):
    model = GlbWriter()
    mesh = model.mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        targets=[[(0.0, 0.0, 0.0)] * 3, [(0.0, 0.0, 0.0)] * 3],
    )
    face = model.node("face", mesh=mesh)
    model.scene([face])
    model.animation("smile", [(face, "weights", [0, 1], [(0.0, 1.0), (0.5, 0.25)])])
    path = model.write(tmp_path)
    document, binary = chunks(path)
    (sampler,) = document["animations"][0]["samplers"]
    assert values(document, binary, sampler["output"]) == [
        (0.0,),
        (1.0,),
        (0.5,),
        (0.25,),
    ]
    (clip,) = read_glb(path).clips
    assert (clip.name, clip.t0, clip.t1, clip.roots) == ("smile", 0.0, 1.0, ())


def test_the_shared_triangle_and_other_meshes_coexist(tmp_path):
    model = GlbWriter()
    first = model.mesh([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)])
    triangle = model.node("triangle", mesh=True)
    shape = model.node("shape", mesh=first)
    model.scene([triangle, shape])
    document, _ = chunks(model.write(tmp_path))
    assert len(document["meshes"]) == 2
    assert document["nodes"][triangle]["mesh"] != document["nodes"][shape]["mesh"]


def test_the_reader_reads_skinned_joint_roots(tmp_path):
    model = GlbWriter()
    child = model.node("joint", translation=(0.0, 0.5, 0.0))
    root = model.node("joint", children=[child])
    model.skin([root, child], [(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)] * 2)
    model.scene([root])
    model.animation(
        "stride",
        [
            (root, "translation", [0, 1], [(0, 0, 0), (0, 0, 1)]),
            (child, "translation", [0, 1], [(0, 0.5, 0), (1, 0.5, 0)]),
        ],
    )
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert clip.roots == (Root(root, "joint"),)
