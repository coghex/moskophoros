"""Material identities and every-run input checks, using generated GLBs."""

import copy

import pytest
from glb_writer import GlbWriter

from moskophoros.gltf import (
    InputError,
    PrimitiveMaterial,
    read_glb,
    read_material_identities,
)


def model_with_materials(materials):
    model = GlbWriter()
    node = model.node(mesh=True)
    model.scene([node])
    model.document["materials"] = materials
    primitive = model.document["meshes"][0]["primitives"][0]
    model.document["meshes"][0]["primitives"] = [
        {**primitive, "material": i} for i in range(len(materials))
    ] + [primitive]
    return model


def test_names_indices_and_missing_materials(tmp_path):
    model = model_with_materials(
        [{"name": "Steel"}, {}, {"name": ""}, {"name": "Steel"}, {"name": "steel"}]
    )
    path = model.write(tmp_path)
    expected = tuple(
        PrimitiveMaterial(0, 0, p, index, name, "OPAQUE")
        for p, (index, name) in enumerate(
            [
                (0, "Steel"),
                (1, None),
                (2, None),
                (3, "Steel"),
                (4, "steel"),
                (None, None),
            ]
        )
    )
    assert read_glb(path).primitive_materials == expected
    assert read_glb(path).primitive_materials == expected
    before = copy.deepcopy(model.document)
    assert read_material_identities(model.document) == expected
    assert model.document == before


@pytest.mark.parametrize(
    "alpha_mode", ["OPAQUE", "MASK", "BLEND", "other", None, 1, False, [], {}]
)
def test_alpha_mode_is_reported_without_new_validation(tmp_path, alpha_mode):
    model = model_with_materials([{"name": "cloth", "alphaMode": alpha_mode}])
    records = read_glb(model.write(tmp_path)).primitive_materials
    assert records[0] == PrimitiveMaterial(0, 0, 0, 0, "cloth", alpha_mode)
    assert records[1] == PrimitiveMaterial(0, 0, 1, None, None, "OPAQUE")


@pytest.mark.parametrize("explicit_scene", [False, True])
def test_scene_descendants_order_and_shared_mesh_instances(tmp_path, explicit_scene):
    model = model_with_materials([{"name": "shared"}, {"name": "other"}])
    # Mesh 0 has three primitives and is instanced at nodes 0 and 2. Node 1
    # uses mesh 1 in the other scene; mesh 2 is unreachable from either scene.
    model.document["meshes"].extend(
        [
            {"primitives": [{"material": 1}]},
            {"primitives": [{"material": 1}]},
        ]
    )
    model.document["nodes"] = [
        {"mesh": 0},
        {"mesh": 1},
        {"mesh": 0},
        {"children": [2, 0]},
        {"mesh": 2},
    ]
    selected, other = {"nodes": [3]}, {"nodes": [1]}
    model.document["scenes"] = (
        [other, selected] if explicit_scene else [selected, other]
    )
    if explicit_scene:
        model.document["scene"] = 1
    else:
        model.document.pop("scene", None)
    subject = read_glb(model.write(tmp_path))
    assert subject.scene_index == int(explicit_scene)
    assert subject.primitive_materials == tuple(
        PrimitiveMaterial(n, 0, p, index, name, "OPAQUE")
        for n in (0, 2)
        for p, (index, name) in enumerate([(0, "shared"), (1, "other"), (None, None)])
    )
    assert read_material_identities(model.document) == subject.primitive_materials


def test_overlapping_scene_roots_do_not_repeat_a_node(tmp_path):
    model = model_with_materials([{"name": "steel"}])
    parent = model.node(children=[0])
    model.document["scenes"][0]["nodes"] = [parent, 0]
    assert len(read_glb(model.write(tmp_path)).primitive_materials) == 2


@pytest.mark.parametrize("array", ["meshes", "materials", "both"])
def test_optional_arrays_may_be_absent_without_references(tmp_path, array):
    model = GlbWriter()
    node = model.node(mesh=array == "materials")
    model.scene([node])
    if array == "meshes":
        model.document["materials"] = [{"name": "unused"}]
    assert read_glb(model.write(tmp_path)).primitive_materials == (
        (PrimitiveMaterial(0, 0, 0, None, None, "OPAQUE"),)
        if array == "materials"
        else ()
    )


def assert_input_error(model, tmp_path, problem):
    path = model.write(tmp_path)
    with pytest.raises(InputError) as raised:
        read_glb(path)
    assert raised.value.exit_code == 3
    assert raised.value.path == path
    assert str(raised.value) == f"{path}: {problem}"
    with pytest.raises(InputError, match=problem):
        read_material_identities(model.document, path=path)


@pytest.mark.parametrize("value", [True, False, 0.0, "0", None, -1, 1])
@pytest.mark.parametrize("kind", ["mesh", "material"])
@pytest.mark.parametrize("selected", [False, True])
def test_invalid_references_are_checked_document_wide(tmp_path, value, kind, selected):
    model = model_with_materials([{"name": "steel"}])
    if not selected:
        model.document["scenes"][0]["nodes"] = []
        model.scene([0])
    if kind == "mesh":
        model.document["nodes"][0]["mesh"] = value
        what = "node 0's mesh"
    else:
        model.document["meshes"][0]["primitives"][0]["material"] = value
        what = "mesh 0's primitive 0's material"
    suffix = (
        f"names no {kind}"
        if value is None
        else f"names {kind} {value!r}, which does not exist"
    )
    assert_input_error(model, tmp_path, f"{what} {suffix}")


@pytest.mark.parametrize("value", [None, 1, False, [], {}])
def test_invalid_names_in_unused_materials(tmp_path, value):
    model = model_with_materials([{"name": "steel"}])
    model.document["materials"].append({"name": value})
    assert_input_error(model, tmp_path, "material 1's name is not a string")


@pytest.mark.parametrize("value", [None, {}, "wrong", 1, False])
@pytest.mark.parametrize("kind", ["meshes", "materials", "primitives"])
def test_non_array_containers(tmp_path, kind, value):
    model = model_with_materials([{"name": "steel"}])
    if kind == "primitives":
        model.document["meshes"][0][kind] = value
        what = "mesh 0's primitives"
    else:
        model.document[kind] = value
        what = kind
    assert_input_error(model, tmp_path, f"{what} is not an array")


@pytest.mark.parametrize("value", [None, [], "wrong", 1, False])
@pytest.mark.parametrize("kind", ["mesh", "material", "primitive"])
def test_non_object_unused_entries(tmp_path, kind, value):
    model = model_with_materials([{"name": "steel"}])
    if kind == "primitive":
        model.document["meshes"].append({"primitives": [value]})
        what = "mesh 1's primitive 0"
    else:
        model.document["meshes" if kind == "mesh" else "materials"].append(value)
        what = f"{kind} 1"
    assert_input_error(model, tmp_path, f"{what} is not an object")


@pytest.mark.parametrize("kind", ["mesh", "material"])
def test_referencing_an_absent_array_is_an_input_error(tmp_path, kind):
    model = model_with_materials([{"name": "steel"}])
    del model.document["meshes" if kind == "mesh" else "materials"]
    what = "node 0's mesh" if kind == "mesh" else "mesh 0's primitive 0's material"
    assert_input_error(model, tmp_path, f"{what} names {kind} 0, which does not exist")
