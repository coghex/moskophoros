"""All libraries are generated here; no owner library files are used."""

import copy
import json

import pytest

from moskophoros.materials import (
    Entry,
    LibraryError,
    read_library,
    read_library_bytes,
    validate_library,
)

COLORS = tuple((i, i, i) for i in range(16))


def library(**changes):
    document = {
        "schema": "moskophoros.materials/1",
        "ramps": {"metal": [12, 13, 14, 15, 7], "cloth": [8, 9, 10]},
        "default": "cloth",
        "materials": {
            "steel": {"uses": "metal"},
            "cloth.red": {"ramp": [8, 9, 10]},
            "face": "ordinary",
        },
    }
    for key, value in changes.items():
        if value is None:
            del document[key]
        else:
            document[key] = value
    return document


def write(tmp_path, text):
    path = tmp_path / "materials.json"
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


def refused(tmp_path, text, colors=COLORS):
    path = write(tmp_path, text)
    with pytest.raises(LibraryError) as raised:
        read_library(path, colors)
    assert raised.value.source == path
    assert str(raised.value).startswith(f"{path}: ")
    return raised.value.problem


def refused_document(tmp_path, document, colors=COLORS):
    return refused(tmp_path, json.dumps(document), colors)


# Valid libraries


def test_a_library_with_every_kind_of_entry(tmp_path):
    parsed = read_library(write(tmp_path, json.dumps(library())), COLORS)
    assert parsed.ramps == {"cloth": (8, 9, 10), "metal": (12, 13, 14, 15, 7)}
    assert parsed.default == "cloth"
    assert parsed.materials == {
        "cloth.red": Entry(ramp=(8, 9, 10)),
        "face": Entry(),
        "steel": Entry(uses="metal"),
    }
    assert list(parsed.ramps) == ["cloth", "metal"]
    assert list(parsed.materials) == ["cloth.red", "face", "steel"]


def test_the_result_is_read_only(tmp_path):
    parsed = read_library(write(tmp_path, json.dumps(library())), COLORS)
    with pytest.raises(TypeError):
        parsed.ramps["new"] = (1,)
    with pytest.raises(TypeError):
        parsed.materials["new"] = Entry()


def test_a_library_without_a_default(tmp_path):
    parsed = read_library(write(tmp_path, json.dumps(library(default=None))), COLORS)
    assert parsed.default is None
    assert len(parsed.materials) == 3


def test_empty_ramps_and_materials(tmp_path):
    document = library(ramps={}, default=None, materials={})
    parsed = read_library(write(tmp_path, json.dumps(document)), COLORS)
    assert parsed.ramps == {} and parsed.materials == {} and parsed.default is None


def test_flat_repeated_and_unordered_ramps(tmp_path):
    document = library(
        ramps={"flat": [3], "repeated": [4, 4, 2, 4], "bright first": [15, 0]},
        default=None,
        materials={"lamp": {"ramp": [15, 1, 15]}},
    )
    parsed = read_library(write(tmp_path, json.dumps(document)), COLORS)
    assert parsed.ramps == {
        "bright first": (15, 0),
        "flat": (3,),
        "repeated": (4, 4, 2, 4),
    }
    assert parsed.materials == {"lamp": Entry(ramp=(15, 1, 15))}


def test_the_largest_ramp_with_repeated_indices(tmp_path):
    ramp = [i % 16 for i in range(256)]
    document = library(materials={"long": {"ramp": ramp}}, ramps={"long": ramp})
    document["default"] = "long"
    parsed = read_library(write(tmp_path, json.dumps(document)), COLORS)
    assert parsed.ramps["long"] == tuple(ramp)
    assert parsed.materials["long"] == Entry(ramp=tuple(ramp))


def test_the_last_palette_index_is_valid(tmp_path):
    document = library(ramps={"edge": [0, 15]}, default=None, materials={})
    assert read_library(write(tmp_path, json.dumps(document)), COLORS).ramps == {
        "edge": (0, 15)
    }


def test_unused_entries_and_ramps_are_valid(tmp_path):
    document = library(
        ramps={"unused": [1], "metal": [2]},
        materials={"never": {"uses": "unused"}, "nor": "ordinary"},
        default=None,
    )
    assert len(read_library(write(tmp_path, json.dumps(document)), COLORS).ramps) == 2


def test_names_are_kept_exactly(tmp_path):
    document = library(
        ramps={"Metal": [1], "metal": [2], " metal ": [3]},
        default="metal",
        materials={
            "Steel": {"uses": "Metal"},
            "steel": {"uses": "metal"},
            "steel ": {"uses": " metal "},
        },
    )
    parsed = read_library(write(tmp_path, json.dumps(document)), COLORS)
    assert parsed.ramps == {" metal ": (3,), "Metal": (1,), "metal": (2,)}
    assert parsed.default == "metal"
    assert parsed.materials == {
        "Steel": Entry(uses="Metal"),
        "steel": Entry(uses="metal"),
        "steel ": Entry(uses=" metal "),
    }


@pytest.mark.parametrize(
    ("reference", "ramps"),
    [("metal", {"Metal": [1]}), ("metal", {" metal": [1]}), ("Metal", {"metal": [1]})],
)
def test_references_match_exactly(tmp_path, reference, ramps):
    document = library(ramps=ramps, default=None, materials={"x": {"uses": reference}})
    problem = refused_document(tmp_path, document)
    assert problem == f'materials["x"].uses: no ramp is named "{reference}"'


def test_key_order_does_not_matter(tmp_path):
    forward = library()
    backward = {
        key: (dict(reversed(value.items())) if isinstance(value, dict) else value)
        for key, value in reversed(forward.items())
    }
    first = read_library(write(tmp_path, json.dumps(forward)), COLORS)
    second = read_library(write(tmp_path, json.dumps(backward)), COLORS)
    assert first == second
    assert list(first.ramps) == list(second.ramps)
    assert list(first.materials) == list(second.materials)


def test_file_bytes_and_parsed_give_the_same_library(tmp_path):
    text = json.dumps(library())
    path = write(tmp_path, text)
    document = json.loads(text)
    before = copy.deepcopy(document)
    from_file = read_library(path, COLORS)
    from_bytes = read_library_bytes(path.read_bytes(), COLORS, source=path)
    from_parsed = validate_library(document, COLORS, source="settings.json")
    assert from_file == from_bytes == from_parsed
    assert document == before


def test_validating_a_parsed_library_reads_nothing(tmp_path):
    missing = tmp_path / "absent.json"
    validate_library(library(), COLORS, source=missing)
    with pytest.raises(LibraryError) as raised:
        validate_library(library(schema="other"), COLORS, source=missing)
    assert raised.value.source == missing
    assert not missing.exists()


def test_parsed_libraries_may_use_tuples():
    document = library(ramps={"metal": (1, 2)}, default="metal", materials={})
    assert validate_library(document, COLORS, source="s").ramps == {"metal": (1, 2)}


# Reading and parsing failures


def test_an_unreadable_file(tmp_path):
    path = tmp_path / "absent.json"
    with pytest.raises(LibraryError) as raised:
        read_library(path, COLORS)
    assert raised.value.source == path
    assert raised.value.problem.startswith("cannot be read: ")


def test_a_directory_is_unreadable(tmp_path):
    with pytest.raises(LibraryError, match="cannot be read"):
        read_library(tmp_path, COLORS)


def test_invalid_utf8(tmp_path):
    problem = refused(tmp_path, b'{"schema": "\xff"}')
    assert problem.startswith("is not UTF-8: ")
    assert "at byte 12" in problem


@pytest.mark.parametrize(
    "text", ["", "{", '{"schema": }', "[1, 2,]", "{'schema': 1}", "﻿{}"]
)
def test_malformed_json(tmp_path, text):
    assert refused(tmp_path, text).startswith("is not valid JSON: ")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_json_constants(tmp_path, constant):
    text = json.dumps(library(ramps={"metal": [1]})).replace("[1]", f"[{constant}]")
    problem = refused(tmp_path, text)
    assert problem == f"is not valid JSON: {constant} is not a JSON value"


def test_deep_nesting(tmp_path):
    assert refused(tmp_path, "[" * 100_000).startswith("is not valid JSON")


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('{"schema": 1, "schema": 2}', "schema"),
        ('{"ramps": {"metal": [1], "metal": [2]}}', "metal"),
        ('{"materials": {"steel": "ordinary", "steel": "ordinary"}}', "steel"),
        ('{"materials": {"steel": {"uses": "a", "uses": "b"}}}', "uses"),
    ],
    ids=["root", "ramps", "materials", "entry"],
)
def test_repeated_keys(tmp_path, text, key):
    assert refused(tmp_path, text) == f'repeats the key "{key}"'


# The outer shape


@pytest.mark.parametrize("document", [[], "library", 1, None])
def test_not_an_object(tmp_path, document):
    assert refused_document(tmp_path, document) == "expected a JSON object"


@pytest.mark.parametrize("field", ["schema", "ramps", "materials"])
def test_a_missing_field(tmp_path, field):
    assert refused_document(tmp_path, library(**{field: None})) == f"{field}: missing"


@pytest.mark.parametrize(
    ("schema", "shown"),
    [
        ("moskophoros.materials/2", '"moskophoros.materials/2"'),
        ("Moskophoros.materials/1", '"Moskophoros.materials/1"'),
        ("moskophoros.materials/1 ", '"moskophoros.materials/1 "'),
        (1, "1"),
        (None, "null"),
        (["moskophoros.materials/1"], '["moskophoros.materials/1"]'),
    ],
)
def test_a_wrong_schema(tmp_path, schema, shown):
    document = library()
    document["schema"] = schema
    problem = refused_document(tmp_path, document)
    assert problem == f'schema: expected "moskophoros.materials/1", got {shown}'


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"palette": []}, 'unknown field "palette"'),
        (
            {
                "ramps": {"metal": [1]},
                "materials": {"steel": {"ramp": [1], "shine": 1}},
            },
            'materials["steel"]: unknown field "shine"',
        ),
        (
            {"ramps": {"metal": [1]}, "materials": {"steel": {"properties": {}}}},
            'materials["steel"]: unknown field "properties"',
        ),
    ],
    ids=["root", "entry", "entry-only"],
)
def test_unknown_fields(tmp_path, change, problem):
    document = library(default=None, **change)
    assert refused_document(tmp_path, document) == problem


@pytest.mark.parametrize("field", ["ramps", "materials"])
@pytest.mark.parametrize("value", [[], "x", 1, None])
def test_maps_must_be_objects(tmp_path, field, value):
    document = library(default=None)
    document[field] = value
    assert refused_document(tmp_path, document) == f"{field}: expected an object"


# Ramps


@pytest.mark.parametrize("where", ["named", "entry"])
@pytest.mark.parametrize(
    ("ramp", "problem"),
    [
        ([], "has 0 entries; expected 1 to 256"),
        ([1] * 257, "has 257 entries; expected 1 to 256"),
        ({"0": 1}, "expected a list of palette indices"),
        ("1, 2", "expected a list of palette indices"),
        (1, "expected a list of palette indices"),
        (None, "expected a list of palette indices"),
    ],
)
def test_a_ramp_of_the_wrong_shape(tmp_path, where, ramp, problem):
    if where == "named":
        document = library(ramps={"metal": ramp}, default=None, materials={})
        location = 'ramps["metal"]'
    else:
        document = library(ramps={}, default=None, materials={"steel": {"ramp": ramp}})
        location = 'materials["steel"].ramp'
    assert refused_document(tmp_path, document) == f"{location}: {problem}"


@pytest.mark.parametrize("where", ["named", "entry"])
@pytest.mark.parametrize(
    ("index", "problem"),
    [
        (True, "true is not an integer"),
        (False, "false is not an integer"),
        (3.0, "3.0 is not an integer"),
        ("3", '"3" is not an integer'),
        (None, "null is not an integer"),
        ([3], "[3] is not an integer"),
        (16, "16 is not an index into the 16-colour palette (0 to 15)"),
        (99, "99 is not an index into the 16-colour palette (0 to 15)"),
        (-1, "-1 is not an index into the 16-colour palette (0 to 15)"),
    ],
)
def test_a_bad_ramp_index(tmp_path, where, index, problem):
    ramp = [0, 1, index]
    if where == "named":
        document = library(ramps={"metal": ramp}, default=None, materials={})
        location = 'ramps["metal"][2]'
    else:
        document = library(ramps={}, default=None, materials={"steel": {"ramp": ramp}})
        location = 'materials["steel"].ramp[2]'
    assert refused_document(tmp_path, document) == f"{location}: {problem}"


def test_the_float_spelling_of_an_integer_is_refused(tmp_path):
    text = json.dumps(library()).replace("[8, 9, 10]", "[8, 9.0, 10]", 1)
    assert refused(tmp_path, text) == 'ramps["cloth"][1]: 9.0 is not an integer'


def test_an_overflowing_number_is_refused(tmp_path):
    text = json.dumps(library()).replace("[8, 9, 10]", "[8, 1e400, 10]", 1)
    assert refused(tmp_path, text) == 'ramps["cloth"][1]: inf is not an integer'


def test_indices_are_checked_against_the_given_palette(tmp_path):
    problem = refused_document(tmp_path, library(), COLORS[:14])
    assert problem == (
        'ramps["metal"][2]: 14 is not an index into the 14-colour palette (0 to 13)'
    )


# Material entries and references


@pytest.mark.parametrize(
    ("entry", "problem"),
    [
        ({}, 'expected exactly one of "ramp" and "uses"'),
        ({"ramp": [1], "uses": "metal"}, 'expected exactly one of "ramp" and "uses"'),
        (
            "Ordinary",
            'expected {"ramp": [...]}, {"uses": NAME} or "ordinary", got "Ordinary"',
        ),
        (
            "metal",
            'expected {"ramp": [...]}, {"uses": NAME} or "ordinary", got "metal"',
        ),
        ([1, 2], 'expected {"ramp": [...]}, {"uses": NAME} or "ordinary", got [1, 2]'),
        (None, 'expected {"ramp": [...]}, {"uses": NAME} or "ordinary", got null'),
        (3, 'expected {"ramp": [...]}, {"uses": NAME} or "ordinary", got 3'),
    ],
)
def test_a_material_entry_of_the_wrong_form(tmp_path, entry, problem):
    document = library(ramps={"metal": [1]}, default=None, materials={"steel": entry})
    assert refused_document(tmp_path, document) == f'materials["steel"]: {problem}'


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("metl", 'no ramp is named "metl"'),
        ("", "the empty name is not allowed"),
        (None, "expected a ramp name, got null"),
        (1, "expected a ramp name, got 1"),
        (["metal"], 'expected a ramp name, got ["metal"]'),
    ],
)
def test_a_bad_uses(tmp_path, value, problem):
    document = library(materials={"steel": {"uses": value}})
    assert refused_document(tmp_path, document) == f'materials["steel"].uses: {problem}'


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("silk", 'no ramp is named "silk"'),
        ("", "the empty name is not allowed"),
        (None, "expected a ramp name, got null"),
        (False, "expected a ramp name, got false"),
        ({"uses": "cloth"}, 'expected a ramp name, got {"uses": "cloth"}'),
    ],
)
def test_a_bad_default(tmp_path, value, problem):
    document = library()
    document["default"] = value
    assert refused_document(tmp_path, document) == f"default: {problem}"


def test_a_default_without_ramps(tmp_path):
    document = library(ramps={}, default="cloth", materials={})
    assert refused_document(tmp_path, document) == 'default: no ramp is named "cloth"'


@pytest.mark.parametrize("field", ["ramps", "materials"])
def test_the_empty_name(tmp_path, field):
    document = library(default=None)
    document[field] = {"": [1] if field == "ramps" else "ordinary"}
    problem = refused_document(tmp_path, document)
    assert problem == f"{field}: the empty name is not allowed"


@pytest.mark.parametrize("field", [None, "ramps", "materials"])
def test_parsed_libraries_need_string_keys(field):
    document = library(default=None)
    if field is None:
        document[1] = "x"
    else:
        document[field] = {1: [1] if field == "ramps" else "ordinary"}
    with pytest.raises(LibraryError) as raised:
        validate_library(document, COLORS, source="settings.json")
    where = f"{field}: " if field else ""
    assert raised.value.problem == f"{where}key 1 is not a string"
    assert raised.value.source == "settings.json"


def test_the_first_error_does_not_depend_on_key_order(tmp_path):
    bad = {"b": [99], "a": [98]}
    forward = library(ramps=bad, default=None, materials={})
    backward = library(ramps=dict(reversed(bad.items())), default=None, materials={})
    assert refused_document(tmp_path, forward) == refused_document(tmp_path, backward)
