"""All libraries are generated here; no owner library files are used."""

import copy
import json
import sys

import pytest
import yaml

from moskophoros.gltf import PrimitiveMaterial
from moskophoros.materials import (
    Entry,
    LibraryError,
    Shade,
    capture_overrides,
    override_warnings,
    read_library,
    read_library_bytes,
    validate_library,
)

COLORS = tuple((i, i, i) for i in range(16))


def library(**changes):
    document = {
        "schema": "moskophoros.materials/2",
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


# The same library as `library()`, as the owner might write it.
LIBRARY_TEXT = """\
# Ramps run dark to light, as indices into the palette.
schema: moskophoros.materials/2
ramps:
  metal: [12, 13, 14, 15, 7]
  cloth: [8, 9, 10]
default: cloth  # parts with no entry take this ramp
materials:
  steel: {uses: metal}
  cloth.red:
    ramp: [8, 9, 10]
  face: ordinary
"""


def dump(document):
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def write(tmp_path, text, name="materials.yaml"):
    path = tmp_path / name
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
    return refused(tmp_path, dump(document), colors)


# Valid libraries


def test_a_library_with_every_kind_of_entry(tmp_path):
    parsed = read_library(write(tmp_path, dump(library())), COLORS)
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
    parsed = read_library(write(tmp_path, dump(library())), COLORS)
    with pytest.raises(TypeError):
        parsed.ramps["new"] = (1,)
    with pytest.raises(TypeError):
        parsed.materials["new"] = Entry()


def test_a_library_without_a_default(tmp_path):
    parsed = read_library(write(tmp_path, dump(library(default=None))), COLORS)
    assert parsed.default is None
    assert len(parsed.materials) == 3


def test_empty_ramps_and_materials(tmp_path):
    document = library(ramps={}, default=None, materials={})
    parsed = read_library(write(tmp_path, dump(document)), COLORS)
    assert parsed.ramps == {} and parsed.materials == {} and parsed.default is None


def test_flat_repeated_and_unordered_ramps(tmp_path):
    document = library(
        ramps={"flat": [3], "repeated": [4, 4, 2, 4], "bright first": [15, 0]},
        default=None,
        materials={"lamp": {"ramp": [15, 1, 15]}},
    )
    parsed = read_library(write(tmp_path, dump(document)), COLORS)
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
    parsed = read_library(write(tmp_path, dump(document)), COLORS)
    assert parsed.ramps["long"] == tuple(ramp)
    assert parsed.materials["long"] == Entry(ramp=tuple(ramp))


def test_the_last_palette_index_is_valid(tmp_path):
    document = library(ramps={"edge": [0, 15]}, default=None, materials={})
    assert read_library(write(tmp_path, dump(document)), COLORS).ramps == {
        "edge": (0, 15)
    }


def test_unused_entries_and_ramps_are_valid(tmp_path):
    document = library(
        ramps={"unused": [1], "metal": [2]},
        materials={"never": {"uses": "unused"}, "nor": "ordinary"},
        default=None,
    )
    assert len(read_library(write(tmp_path, dump(document)), COLORS).ramps) == 2


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
    parsed = read_library(write(tmp_path, dump(document)), COLORS)
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
    first = read_library(write(tmp_path, dump(forward)), COLORS)
    second = read_library(write(tmp_path, dump(backward)), COLORS)
    assert first == second
    assert list(first.ramps) == list(second.ramps)
    assert list(first.materials) == list(second.materials)


def test_comments_are_allowed(tmp_path):
    assert read_library(write(tmp_path, LIBRARY_TEXT), COLORS) == validate_library(
        library(), COLORS, source="s"
    )


def test_a_json_library_and_its_yaml_conversion_give_an_equal_library(tmp_path):
    text = json.dumps(library(), indent=2)
    from_json = validate_library(json.loads(text), COLORS, source="materials.json")
    from_yaml = read_library(write(tmp_path, LIBRARY_TEXT), COLORS)
    assert from_json == from_yaml
    assert list(from_json.ramps) == list(from_yaml.ramps)
    assert list(from_json.materials) == list(from_yaml.materials)


def test_aliases_reuse_a_ramp(tmp_path):
    text = (
        "schema: moskophoros.materials/2\n"
        "ramps:\n  metal: &metal [1, 2, 3]\n"
        "materials:\n  steel: {ramp: *metal}\n  iron: {ramp: *metal}\n"
    )
    parsed = read_library(write(tmp_path, text), COLORS)
    assert parsed.materials == {
        "iron": Entry(ramp=(1, 2, 3)),
        "steel": Entry(ramp=(1, 2, 3)),
    }


@pytest.mark.parametrize("name", ["on", "no", "yes", "off", "true1", "1.5.2"])
def test_yaml_words_are_kept_as_names(tmp_path, name):
    text = (
        "schema: moskophoros.materials/2\n"
        f"ramps: {{{name}: [1]}}\n"
        f"default: {name}\n"
        f"materials: {{{name}: {{uses: {name}}}}}\n"
    )
    parsed = read_library(write(tmp_path, text), COLORS)
    assert parsed.ramps == {name: (1,)}
    assert parsed.default == name
    assert parsed.materials == {name: Entry(uses=name)}


@pytest.mark.parametrize(
    ("name", "shown"), [("1", "1"), ("true", "true"), ("null", "null"), ("~", "null")]
)
def test_an_unquoted_name_that_is_not_a_string_is_refused(tmp_path, name, shown):
    base = "schema: moskophoros.materials/2\nramps: {}\n"
    problem = refused(tmp_path, base + f"materials:\n  {name}: ordinary\n")
    assert problem == f"materials: key {shown} is not a string"
    quoted = read_library(
        write(tmp_path, base + f"materials:\n  '{name}': ordinary\n"), COLORS
    )
    assert quoted.materials == {name: Entry()}


def test_file_bytes_and_parsed_give_the_same_library(tmp_path):
    path = write(tmp_path, LIBRARY_TEXT)
    document = library()
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


@pytest.mark.parametrize(
    "name", ["materials.json", "materials.JSON", "materials", "lib.yaml.txt", "yaml"]
)
def test_a_name_without_a_yaml_suffix_is_refused_before_reading(tmp_path, name):
    path = write(tmp_path, LIBRARY_TEXT, name=name)
    for target in (path, tmp_path / f"absent-{name}"):
        with pytest.raises(LibraryError) as raised:
            read_library(target, COLORS)
        assert raised.value.source == target
        assert raised.value.problem == (
            "material libraries are YAML; the file name must end in .yaml or .yml"
        )


@pytest.mark.parametrize("name", ["a.yaml", "a.yml", "a.YAML", "a.Yml", "a.b.yaml"])
def test_yaml_suffixes_in_any_case(tmp_path, name):
    assert read_library(write(tmp_path, LIBRARY_TEXT, name=name), COLORS).default == (
        "cloth"
    )


def test_an_unreadable_file(tmp_path):
    path = tmp_path / "absent.yaml"
    with pytest.raises(LibraryError) as raised:
        read_library(path, COLORS)
    assert raised.value.source == path
    assert raised.value.problem.startswith("cannot be read: ")


def test_a_directory_is_unreadable(tmp_path):
    directory = tmp_path / "library.yaml"
    directory.mkdir()
    with pytest.raises(LibraryError, match="cannot be read"):
        read_library(directory, COLORS)


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        (b'{"schema": "\xff"}', "is not UTF-8: invalid start byte at byte 12"),
        (
            b"\xff\xfe" + LIBRARY_TEXT.encode("utf-16-le"),
            "is not UTF-8: invalid start byte at byte 0",
        ),
    ],
    ids=["invalid-byte", "utf-16le-bom"],
)
def test_only_utf8_is_read(tmp_path, data, problem):
    assert refused(tmp_path, data) == problem


@pytest.mark.parametrize("text", ["", "\n", "# nothing yet\n"])
def test_an_empty_file(tmp_path, text):
    assert refused(tmp_path, text) == "is empty: it holds no YAML document"


def test_two_documents(tmp_path):
    problem = refused(tmp_path, LIBRARY_TEXT + "---\n" + LIBRARY_TEXT)
    assert problem == (
        "holds more than one YAML document; the second starts at line 12, column 1"
    )


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ("{", "line 1, column 2"),
        ("schema: moskophoros.materials/2\nramps: {metal: [1, 2}\n", "line 2"),
        ("schema: moskophoros.materials/2\nramps:\n\tmetal: [1]\n", "line 3"),
        ("schema: x\n ramps: {}\n", "line 2"),
    ],
    ids=["unclosed", "mismatched", "tab", "indentation"],
)
def test_malformed_yaml(tmp_path, text, where):
    assert refused(tmp_path, text).startswith(f"is not valid YAML at {where}")


def test_deep_nesting(tmp_path):
    problem = refused(tmp_path, "[" * 100_000)
    assert problem.startswith("is not valid YAML at line 1, column ")
    assert problem.endswith(": it is nested too deeply")


def test_an_escape_past_unicode_is_refused(tmp_path):
    text = LIBRARY_TEXT.replace("face: ordinary", 'face: "\\U00110000"')
    assert refused(tmp_path, text).startswith(
        "is not valid YAML at line 11, column 12: cannot read a token"
    )


@pytest.mark.parametrize(
    ("text", "key", "line", "column"),
    [
        ("schema: x\nramps: {}\nschema: y\n", "schema", 3, 1),
        ("ramps:\n  metal: [1]\n  metal: [2]\n", "metal", 3, 3),
        ("materials:\n  steel: ordinary\n  steel: ordinary\n", "steel", 3, 3),
        ("materials:\n  steel:\n    uses: a\n    uses: b\n", "uses", 4, 5),
    ],
    ids=["root", "ramps", "materials", "entry"],
)
def test_repeated_keys(tmp_path, text, key, line, column):
    assert refused(tmp_path, text) == (
        f'repeats the key "{key}" at line {line}, column {column}'
    )


@pytest.mark.parametrize(
    ("text", "tag"), [("!!int 0x0F", "!!int"), ("!!float .nan", "!!float")]
)
def test_tags_are_refused(tmp_path, text, tag):
    problem = refused(tmp_path, f"ramps:\n  metal: [1, {text}]\n")
    assert problem == f"uses the tag {tag} at line 2, column 14; tags are not allowed"


def test_a_recursive_alias_is_refused(tmp_path):
    problem = refused(tmp_path, "ramps:\n  metal: &m [1, *m]\n")
    assert problem == "the alias *m is inside its own anchor at line 2, column 17"


@pytest.mark.parametrize("index", ["017", "0x0F", "1:20", ".nan", ".inf", "+1", "1_0"])
def test_yaml_number_spellings_are_not_integers(tmp_path, index):
    text = LIBRARY_TEXT.replace("[12, 13", f"[{index}, 13")
    problem = refused(tmp_path, text)
    assert problem == f'ramps["metal"][0]: "{index}" is not an integer'


# The outer shape


@pytest.mark.parametrize("document", [[], "library", 1, None])
def test_not_a_mapping(tmp_path, document):
    assert refused_document(tmp_path, document) == "expected a mapping"


@pytest.mark.parametrize("field", ["schema", "ramps", "materials"])
def test_a_missing_field(tmp_path, field):
    assert refused_document(tmp_path, library(**{field: None})) == f"{field}: missing"


@pytest.mark.parametrize(
    ("schema", "shown"),
    [
        ("moskophoros.materials/3", '"moskophoros.materials/3"'),
        ("Moskophoros.materials/2", '"Moskophoros.materials/2"'),
        ("moskophoros.materials/2 ", '"moskophoros.materials/2 "'),
        (1, "1"),
        (None, "null"),
        (["moskophoros.materials/2"], '["moskophoros.materials/2"]'),
    ],
)
def test_a_wrong_schema(tmp_path, schema, shown):
    document = library()
    document["schema"] = schema
    problem = refused_document(tmp_path, document)
    assert problem == f'schema: expected "moskophoros.materials/2", got {shown}'


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
def test_maps_must_be_mappings(tmp_path, field, value):
    document = library(default=None)
    document[field] = value
    assert refused_document(tmp_path, document) == f"{field}: expected a mapping"


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
    text = LIBRARY_TEXT.replace("[8, 9, 10]", "[8, 9.0, 10]", 1)
    assert refused(tmp_path, text) == 'ramps["cloth"][1]: 9.0 is not an integer'


def test_an_integer_too_long_to_convert_is_refused(tmp_path):
    digits = "9" * (sys.get_int_max_str_digits() + 1)
    text = LIBRARY_TEXT.replace("[8, 9, 10]", f"[8, {digits}, 10]", 1)
    assert refused(tmp_path, text) == (
        f"has an integer of {len(digits)} digits, too long to read at line 5, column 14"
    )


def test_an_overflowing_number_is_refused(tmp_path):
    text = LIBRARY_TEXT.replace("[8, 9, 10]", "[8, 1e400, 10]", 1)
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


# Per-material shading values (settings design D-9, D-20, D-23, D-29, D-30)

SHADED_TEXT = """\
schema: moskophoros.materials/2
ramps:
  stone: [15, 14, 12, 10, 9]
default: stone
materials:
  Grey:
    shade: {range: [120, 255], convexity_weight: 0.5}
    uses: stone
  Rock:
    ramp: [1, 2, 3]
    shade:
      range: [10, 20]
      occlusion_weight: 0
      ao_distance_m: 1.2
  Plain: {uses: stone}
  Glass: ordinary
"""


def test_entries_may_give_their_own_shading_values(tmp_path):
    parsed = read_library(write(tmp_path, SHADED_TEXT), COLORS)
    assert parsed.materials == {
        "Glass": Entry(),
        "Grey": Entry(
            uses="stone", shade=Shade(convexity_weight=0.5, range=(120, 255))
        ),
        "Plain": Entry(uses="stone"),
        "Rock": Entry(
            ramp=(1, 2, 3),
            shade=Shade(ao_distance_m=1.2, occlusion_weight=0.0, range=(10, 20)),
        ),
    }
    # Given in a fixed order, whatever the file's.
    assert parsed.materials["Rock"].shade.given() == (
        ("ao_distance_m", 1.2),
        ("occlusion_weight", 0.0),
        ("range", (10, 20)),
    )


def test_an_empty_shade_gives_no_values(tmp_path):
    document = library(ramps={"m": [1]}, default=None)
    document["materials"] = {"steel": {"uses": "m", "shade": {}}}
    parsed = read_library(write(tmp_path, dump(document)), COLORS)
    assert parsed.materials["steel"] == Entry(uses="m")


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("ao_distance_m", 1e-9, 1e-9),
        ("ao_distance_m", 5, 5.0),
        ("occlusion_weight", 0, 0.0),
        ("occlusion_weight", 3.5, 3.5),
        ("convexity_weight", 0.0, 0.0),
        ("range", [0, 1], (0, 1)),
        ("range", [254, 255], (254, 255)),
    ],
)
def test_each_override_inside_its_bounds(tmp_path, key, value, expected):
    document = library(ramps={"m": [1]}, default=None)
    document["materials"] = {"steel": {"uses": "m", "shade": {key: value}}}
    parsed = read_library(write(tmp_path, dump(document)), COLORS)
    assert getattr(parsed.materials["steel"].shade, key) == expected


@pytest.mark.parametrize(
    ("key", "value", "problem"),
    [
        ("ao_distance_m", 0, "expected a finite number greater than 0, got 0"),
        ("ao_distance_m", -1.5, "expected a finite number greater than 0, got -1.5"),
        ("ao_distance_m", "0.3", 'expected a finite number greater than 0, got "0.3"'),
        ("ao_distance_m", True, "expected a finite number greater than 0, got true"),
        ("occlusion_weight", -0.01, "expected a finite number 0 or greater, got -0.01"),
        ("convexity_weight", None, "expected a finite number 0 or greater, got null"),
        ("range", [191, 84], "expected [lo, hi], two integers with 0 <= lo < hi"),
        ("range", [84, 256], "expected [lo, hi], two integers with 0 <= lo < hi"),
        ("range", [84.0, 191], "got [84.0, 191]"),
        ("range", [True, 191], "got [true, 191]"),
        ("range", "84,191", 'got "84,191"'),
        ("range", [84], "got [84]"),
    ],
)
def test_each_override_outside_its_bounds_names_the_entry(
    tmp_path, key, value, problem
):
    document = library(ramps={"m": [1]}, default=None)
    document["materials"] = {"steel": {"uses": "m", "shade": {key: value}}}
    message = refused_document(tmp_path, document)
    assert message.startswith(f'materials["steel"].shade.{key}: ')
    assert problem in message


def test_ao_samples_is_global_only(tmp_path):
    document = library(ramps={"m": [1]}, default=None)
    document["materials"] = {"steel": {"uses": "m", "shade": {"ao_samples": 8}}}
    assert refused_document(tmp_path, document) == (
        'materials["steel"].shade.ao_samples: AO samples is a global setting only; '
        "set it with --ao-samples or shade.ao_samples in a settings file"
    )


@pytest.mark.parametrize(
    ("shade", "problem"),
    [
        ({"glossiness": 1}, 'materials["steel"].shade: unknown field "glossiness"'),
        (
            [1, 2],
            'materials["steel"].shade: expected a mapping of shading values, got [1, 2]',
        ),
        (
            0.5,
            'materials["steel"].shade: expected a mapping of shading values, got 0.5',
        ),
    ],
)
def test_a_malformed_shade_is_refused(tmp_path, shade, problem):
    document = library(ramps={"m": [1]}, default=None)
    document["materials"] = {"steel": {"uses": "m", "shade": shade}}
    assert refused_document(tmp_path, document) == problem


def test_a_shade_needs_a_ramp_or_uses(tmp_path):
    document = library(ramps={"m": [1]}, default=None)
    document["materials"] = {"steel": {"shade": {"range": [1, 2]}}}
    assert refused_document(tmp_path, document) == (
        'materials["steel"]: expected exactly one of "ramp" and "uses"'
    )


def test_a_version_1_library_is_refused_with_the_schema_hint(tmp_path):
    text = LIBRARY_TEXT.replace("moskophoros.materials/2", "moskophoros.materials/1")
    assert refused(tmp_path, text) == (
        'schema: "moskophoros.materials/1" libraries no longer load; change the '
        'schema line to "moskophoros.materials/2", the only edit the library needs'
    )


def record(index, name, alpha="OPAQUE", node=0):
    return PrimitiveMaterial(node, 0, index, index, name, alpha)


SHADED = validate_library(yaml.safe_load(SHADED_TEXT), COLORS, source="s")
GLOBALS = {"ao_distance_m": 0.3, "occlusion_weight": 0.25, "convexity_weight": 1.0}


def test_a_materials_own_capture_values_beat_the_globals():
    records = [
        record(0, "Rock"),
        record(1, "Grey"),
        record(2, "Plain"),
        record(3, "Unknown"),
        record(4, "Glass"),
        record(5, None),
        record(6, "Grey"),
        record(None, None),
    ]
    assert capture_overrides(records, SHADED, GLOBALS) == [
        (0, 1.2, 0.0, 1.0),
        (1, 0.3, 0.25, 0.5),
        # Materials sharing a name share their entry.
        (6, 0.3, 0.25, 0.5),
    ]


def test_a_translucent_material_keeps_the_globals():
    records = [record(0, "Rock", "BLEND"), record(1, "Grey", "MASK")]
    assert capture_overrides(records, SHADED, GLOBALS) == [(1, 0.3, 0.25, 0.5)]


def test_a_range_alone_overrides_no_capture_value():
    library_ = validate_library(
        {
            "schema": "moskophoros.materials/2",
            "ramps": {"m": [1]},
            "materials": {"a": {"uses": "m", "shade": {"range": [1, 2]}}},
        },
        COLORS,
        source="s",
    )
    assert capture_overrides([record(0, "a")], library_, GLOBALS) == []


def test_an_override_warns_only_for_an_explicit_global():
    records = [
        record(0, "Rock"),
        record(1, "Grey"),
        record(2, "Grey"),
        record(3, "Plain"),
    ]
    explicit = {"convexity_weight": 0.0, "range": (84, 191), "occlusion_weight": 0.9}
    assert override_warnings(records, SHADED, explicit) == [
        'material "Rock" keeps its own shade.occlusion_weight, 0.0, from the material '
        "library; the global 0.9 applies to materials without their own",
        'material "Rock" keeps its own shade.range, [10, 20], from the material '
        "library; the global [84, 191] applies to materials without their own",
        'material "Grey" keeps its own shade.convexity_weight, 0.5, from the '
        "material library; the global 0.0 applies to materials without their own",
        'material "Grey" keeps its own shade.range, [120, 255], from the material '
        "library; the global [84, 191] applies to materials without their own",
    ]
    assert override_warnings(records, SHADED, {}) == []


def test_unused_and_translucent_overrides_warn_nothing():
    records = [record(0, "Rock", "BLEND"), record(1, "Plain")]
    assert override_warnings(records, SHADED, {"range": (84, 191)}) == []
