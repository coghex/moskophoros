"""The `moskophoros.materials/4` library behind the internal gate of
`validate_library` and `read_library_bytes`: the shading response, ordinary
entries as mappings, version-aware errors and positions (shading design
contract 2, D-33, D-39). Every library is generated here."""

import copy

import pytest
import yaml
from test_materials import COLORS, LIBRARY_TEXT, library, record

from moskophoros import materials
from moskophoros import shading as model
from moskophoros.materials import (
    Entry,
    LibraryError,
    Shade,
    capture_overrides,
    read_library_bytes,
    validate_library,
)

V4 = "moskophoros.materials/4"


def v4(**changes):
    return library(schema=V4) | changes


def parse(document, **kwargs):
    return validate_library(document, COLORS, source="lib", shading=True, **kwargs)


def refused(document, **kwargs):
    with pytest.raises(LibraryError) as raised:
        parse(document, **kwargs)
    assert raised.value.source == "lib"
    return raised.value.problem


def with_entry(entry, name="Painted"):
    return v4(materials={name: entry})


# The gate


def test_a_v4_library_is_refused_without_the_gate_as_before():
    with pytest.raises(LibraryError) as raised:
        validate_library(v4(), COLORS, source="lib")
    assert raised.value.problem == (
        'schema: expected "moskophoros.materials/3" or "moskophoros.materials/2", '
        'got "moskophoros.materials/4"'
    )


@pytest.mark.parametrize(
    ("document", "problem"),
    [
        (
            library(
                schema="moskophoros.materials/3", materials={"a": {"ordinary": True}}
            ),
            'materials["a"]: unknown field "ordinary"',
        ),
        (
            library(
                schema="moskophoros.materials/3",
                materials={"a": {"uses": "metal", "shade": {"mode": "both"}}},
            ),
            'materials["a"].shade: unknown field "mode"',
        ),
        (
            library(schema="moskophoros.materials/3", shade={"key": {"strength": 0.5}}),
            'shade: unknown field "key"',
        ),
        (
            library(
                schema="moskophoros.materials/2",
                materials={
                    "a": {"uses": "metal", "shade": {"dither": {"strength": 1}}}
                },
            ),
            'materials["a"].shade: unknown field "dither"',
        ),
        (
            v4(materials={"a": {"ordinary": True}}),
            'schema: expected "moskophoros.materials/3" or "moskophoros.materials/2", '
            'got "moskophoros.materials/4"',
        ),
    ],
)
def test_without_the_gate_the_new_fields_are_refused_as_before(document, problem):
    with pytest.raises(LibraryError) as raised:
        validate_library(document, COLORS, source="lib")
    assert raised.value.problem == problem


def test_the_gate_is_a_keyword_only_internal_parameter():
    import inspect

    for function in (validate_library, read_library_bytes):
        parameter = inspect.signature(function).parameters["shading"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is False


# Old schemas keep their meaning


@pytest.mark.parametrize(
    "schema", ["moskophoros.materials/2", "moskophoros.materials/3"]
)
def test_old_libraries_read_the_same_through_the_gate(schema):
    document = yaml.safe_load(LIBRARY_TEXT)
    document["schema"] = schema
    assert parse(document) == validate_library(document, COLORS, source="lib")


def test_a_v3_library_with_every_old_feature_reads_the_same_through_the_gate():
    document = {
        "schema": "moskophoros.materials/3",
        "ramps": {
            "metal": [12, 13, 14],
            "gold": {"base": "#FFD700", "bands": 4, "lightness_step": 0.1},
        },
        "default": "gold",
        "shade": {"range": [10, 200]},
        "materials": {
            "steel": {"uses": "metal", "shade": {"occlusion_weight": 0.5}},
            "face": "ordinary",
        },
    }
    assert parse(document) == validate_library(document, COLORS, source="lib")


@pytest.mark.parametrize(
    "schema", ["moskophoros.materials/2", "moskophoros.materials/3"]
)
def test_an_old_library_may_not_give_the_response(schema):
    document = library(
        schema=schema, materials={"a": {"uses": "metal", "shade": {"mode": "both"}}}
    )
    assert refused(document) == (
        'materials["a"].shade.mode: the shading response needs '
        f'{V4}; this library is "{schema}"'
    )
    for shade, name in (
        ({"key": {"strength": 0.5}}, "key"),
        ({"brightness": {"floor": 0}}, "brightness"),
        ({"dither": {}}, "dither"),
        ({"ambient_form": True}, "ambient_form"),
    ):
        document = library(
            schema=schema, materials={"a": {"uses": "metal", "shade": shade}}
        )
        assert f'materials["a"].shade.{name}: the shading response needs {V4}' in (
            refused(document)
        )


def test_an_old_library_may_not_give_a_mapping_ordinary_entry():
    document = library(
        schema="moskophoros.materials/3", materials={"a": {"ordinary": True}}
    )
    assert refused(document) == 'materials["a"]: unknown field "ordinary"'


def test_an_old_library_wide_response_names_the_schema_it_needs():
    document = library(schema="moskophoros.materials/3", shade={"mode": "both"})
    assert refused(document) == (
        f"shade.mode: the shading response needs {V4}; this library is "
        '"moskophoros.materials/3"'
    )


def test_a_v2_library_wide_shade_and_generated_ramps_need_v3_or_later():
    document = library(shade={"range": [1, 2]})
    assert refused(document) == (
        "shade: a library's own shade needs moskophoros.materials/3 or later; "
        'this library is "moskophoros.materials/2"'
    )
    document = library(ramps={"gold": {"base": "#ffd700", "bands": 3}})
    assert refused(document) == (
        'ramps["gold"]: a generated ramp needs moskophoros.materials/3 or later; '
        'this library is "moskophoros.materials/2"'
    )
    # Public readers keep the old wording.
    with pytest.raises(LibraryError) as raised:
        validate_library(library(shade={"range": [1, 2]}), COLORS, source="lib")
    assert raised.value.problem == (
        'shade: a library\'s own shade needs schema "moskophoros.materials/3"; '
        'this library is "moskophoros.materials/2"'
    )


def test_a_v1_library_is_pointed_at_v4_through_the_gate_and_v3_otherwise():
    document = library(schema="moskophoros.materials/1")
    assert refused(document) == (
        'schema: "moskophoros.materials/1" libraries no longer load; change the '
        f'schema line to "{V4}", the only edit the library needs'
    )
    with pytest.raises(LibraryError) as raised:
        validate_library(document, COLORS, source="lib")
    assert 'change the schema line to "moskophoros.materials/3"' in raised.value.problem


def test_the_gate_lists_the_schemas_it_reads():
    assert refused(library(schema="moskophoros.materials/5")) == (
        'schema: expected "moskophoros.materials/4", "moskophoros.materials/3" or '
        '"moskophoros.materials/2", got "moskophoros.materials/5"'
    )
    assert "got 4" in refused(library(schema=4))


# Entries of a v4 library


def test_every_entry_form_reads():
    parsed = parse(
        library(
            schema=V4,
            ramps={"metal": [12, 13], "gold": {"base": "#FFD700", "bands": 3}},
            default=None,
            materials={
                "A": {"ramp": [1, 2]},
                "B": {"uses": "metal"},
                "C": "ordinary",
                "D": {"ordinary": True},
                "E": {"ordinary": True, "shade": {"mode": "neither"}},
                "F": {"uses": "gold", "shade": {"key": {"strength": 0.25}}},
                "G": {"ramp": [3], "shade": {"dither": {"pattern": "ordered4"}}},
            },
        )
    )
    assert parsed.materials["A"] == Entry(ramp=(1, 2))
    assert parsed.materials["B"] == Entry(uses="metal")
    assert parsed.materials["C"] == Entry()
    assert parsed.materials["D"] == Entry()
    assert parsed.materials["E"] == Entry(shade=Shade(mode="neither"))
    assert parsed.materials["F"] == Entry(uses="gold", shade=Shade(key_strength=0.25))
    assert parsed.materials["G"] == Entry(
        ramp=(3,), shade=Shade(dither_pattern="ordered4")
    )


@pytest.mark.parametrize("value", [False, None, "true", "yes", 1, 0, 1.0, [True], {}])
def test_ordinary_in_a_mapping_must_be_the_boolean_true(value):
    problem = refused(with_entry({"ordinary": value}))
    assert problem.startswith(
        'materials["Painted"].ordinary: expected true, which is the ordinary look, got '
    )


@pytest.mark.parametrize(
    "entry",
    [
        {},
        {"shade": {"mode": "both"}},
        {"ordinary": True, "ramp": [1]},
        {"ordinary": True, "uses": "metal"},
        {"ramp": [1], "uses": "metal"},
        {"ordinary": True, "ramp": [1], "uses": "metal"},
    ],
)
def test_an_entry_has_exactly_one_of_ramp_uses_and_ordinary(entry):
    assert refused(with_entry(entry)) == (
        'materials["Painted"]: expected exactly one of "ramp", "uses" and "ordinary"'
    )


def test_an_ordinary_mapping_keeps_its_capture_values_and_response():
    parsed = parse(
        with_entry(
            {
                "ordinary": True,
                "shade": {
                    "ao_distance_m": 0.5,
                    "occlusion_weight": 0,
                    "convexity_weight": 2,
                    "range": [10, 90],
                    "mode": "both",
                    "brightness": {"floor": 0.4},
                },
            }
        )
    )
    assert parsed.materials["Painted"].shade == Shade(
        ao_distance_m=0.5,
        occlusion_weight=0.0,
        convexity_weight=2.0,
        range=(10, 90),
        mode="both",
        brightness_floor=0.4,
    )


def test_a_missing_ramp_reference_still_fails_and_no_ramp_is_invented():
    assert refused(with_entry({"uses": "nope"})) == (
        'materials["Painted"].uses: no ramp is named "nope"'
    )
    assert refused(v4(default="nope")) == 'default: no ramp is named "nope"'


def test_the_legacy_ordinary_string_inherits_and_carries_no_shade():
    entry = parse(with_entry("ordinary")).materials["Painted"]
    assert entry == Entry() and entry.shade is None


# The response leaves


FULL = {
    "ao_distance_m": 0.5,
    "range": [20, 100],
    "mode": "brightness",
    "ambient_form": False,
    "key": {"strength": 0.25},
    "sky": {"strength": 0.5},
    "ground": {"strength": 0.125},
    "brightness": {"floor": 0.2, "ceiling": 0.8},
    "dither": {"pattern": "clustered4", "strength": 0.5},
}


def test_every_response_leaf_reads_as_supplied():
    shade = (
        parse(with_entry({"uses": "metal", "shade": FULL})).materials["Painted"].shade
    )
    assert shade == Shade(
        ao_distance_m=0.5,
        range=(20, 100),
        mode="brightness",
        ambient_form=False,
        key_strength=0.25,
        sky_strength=0.5,
        ground_strength=0.125,
        brightness_floor=0.2,
        brightness_ceiling=0.8,
        dither_pattern="clustered4",
        dither_strength=0.5,
    )
    assert shade.given() == (
        ("ao_distance_m", 0.5),
        ("range", (20, 100)),
        ("mode", "brightness"),
        ("ambient_form", False),
        ("key_strength", 0.25),
        ("sky_strength", 0.5),
        ("ground_strength", 0.125),
        ("brightness_floor", 0.2),
        ("brightness_ceiling", 0.8),
        ("dither_pattern", "clustered4"),
        ("dither_strength", 0.5),
    )


def test_a_shade_hands_back_the_mapping_it_was_supplied_as():
    shade = (
        parse(with_entry({"uses": "metal", "shade": FULL})).materials["Painted"].shade
    )
    document = shade.document()
    assert document == FULL | {"range": [20, 100]}
    assert list(document) == [
        "ao_distance_m",
        "range",
        "mode",
        "ambient_form",
        "key",
        "sky",
        "ground",
        "brightness",
        "dither",
    ]
    # Round trip: the same mapping reads back the same shade.
    again = parse(with_entry({"uses": "metal", "shade": document}))
    assert again.materials["Painted"].shade == shade
    assert Shade().document() == {}
    assert Shade(brightness_floor=0.1).document() == {"brightness": {"floor": 0.1}}


def test_a_leaf_not_supplied_stays_unsupplied_not_inherited():
    shade = (
        parse(with_entry({"uses": "metal", "shade": {"brightness": {"floor": 0.4}}}))
        .materials["Painted"]
        .shade
    )
    assert shade.brightness_floor == 0.4 and shade.brightness_ceiling is None
    assert shade.given() == (("brightness_floor", 0.4),)
    assert (
        parse(with_entry({"uses": "metal", "shade": {"key": {}}}))
        .materials["Painted"]
        .shade
        is None
    )


def test_the_library_wide_shade_gives_the_range_and_the_response():
    parsed = parse(
        v4(shade={"range": [1, 9], "mode": "both", "sky": {"strength": 0.5}})
    )
    assert parsed.shade == Shade(range=(1, 9), mode="both", sky_strength=0.5)


@pytest.mark.parametrize(
    "name", ["ao_distance_m", "occlusion_weight", "convexity_weight"]
)
def test_the_library_wide_shade_may_not_give_capture_values(name):
    assert refused(v4(shade={name: 1})) == (
        f"shade.{name}: a library's own shade gives only range and the shading "
        f"response; give {name} in a material's own shade, or as a global setting"
    )


def test_ao_samples_is_global_only_everywhere():
    assert "gives only range and the shading response" in refused(
        v4(shade={"ao_samples": 8})
    )
    assert "AO samples is a global setting only" in refused(
        with_entry({"uses": "metal", "shade": {"ao_samples": 8}})
    )


@pytest.mark.parametrize(
    ("shade", "where"),
    [
        ({"key": {"direction": [1, 0, 0]}}, "key.direction"),
        ({"sky_ground_frame": "world"}, "sky_ground_frame"),
        ({"snap": "ramp"}, "snap"),
    ],
)
@pytest.mark.parametrize("place", ["entry", "library"])
def test_direction_frame_and_snap_are_global_only(shade, where, place):
    document = (
        with_entry({"uses": "metal", "shade": shade})
        if place == "entry"
        else v4(shade=shade)
    )
    problem = refused(document)
    prefix = 'materials["Painted"].shade' if place == "entry" else "shade"
    assert problem.startswith(
        f"{prefix}.{where}: shade.{where} is a global setting only"
    )


@pytest.mark.parametrize("place", ["entry", "library"])
@pytest.mark.parametrize(
    ("shade", "problem"),
    [
        ({"key": None}, "key: expected a mapping of shading values, got null"),
        ({"sky": []}, "sky: expected a mapping of shading values, got []"),
        ({"ground": 0.5}, "ground: expected a mapping of shading values, got 0.5"),
        (
            {"brightness": "x"},
            'brightness: expected a mapping of shading values, got "x"',
        ),
        ({"dither": True}, "dither: expected a mapping of shading values, got true"),
        ({"key": {"colour": 1}}, 'key: unknown field "colour"'),
        ({"sky": {"direction": 1}}, 'sky: unknown field "direction"'),
        ({"dither": {"patterns": "off"}}, 'dither: unknown field "patterns"'),
        ({"glow": 1}, 'unknown field "glow"'),
        ({"mode": None}, "mode: expected ramp, brightness, both or neither, got null"),
        (
            {"mode": "Both"},
            'mode: expected ramp, brightness, both or neither, got "Both"',
        ),
        ({"ambient_form": 1}, "ambient_form: expected true or false, got 1"),
        ({"ambient_form": None}, "ambient_form: expected true or false, got null"),
        (
            {"key": {"strength": None}},
            "key.strength: expected a finite number from 0 to 1, got null",
        ),
        (
            {"key": {"strength": True}},
            "key.strength: expected a finite number from 0 to 1, got true",
        ),
        (
            {"sky": {"strength": 1.5}},
            "sky.strength: expected a finite number from 0 to 1, got 1.5",
        ),
        (
            {"ground": {"strength": -1}},
            "ground.strength: expected a finite number from 0 to 1, got -1",
        ),
        (
            {"brightness": {"floor": "0.1"}},
            'brightness.floor: expected a finite number from 0 to 1, got "0.1"',
        ),
        (
            {"brightness": {"ceiling": float("inf")}},
            "brightness.ceiling: expected a finite number from 0 to 1, got inf",
        ),
        (
            {"dither": {"strength": float("nan")}},
            "dither.strength: expected a finite number from 0 to 1, got nan",
        ),
        (
            {"dither": {"pattern": "ordered3"}},
            'dither.pattern: expected off, ordered2, ordered4, ordered8, clustered4, diagonal4 or shuffled8, got "ordered3"',
        ),
    ],
)
def test_a_bad_response_value_is_refused_wherever_the_shade_is(place, shade, problem):
    if place == "entry":
        document = with_entry({"uses": "metal", "shade": shade})
        prefix = 'materials["Painted"].shade'
    else:
        document = v4(shade=shade)
        prefix = "shade"
    got = refused(document)
    if problem.startswith("unknown field"):
        assert got == f"{prefix}: {problem}"
    else:
        assert got == f"{prefix}.{problem}"


def test_a_bad_value_in_an_unused_inactive_entry_is_still_refused():
    document = v4(
        materials={
            "Used": {"uses": "metal", "shade": {"mode": "neither"}},
            "Unused": {"ordinary": True, "shade": {"dither": {"strength": 2}}},
        }
    )
    assert refused(document) == (
        'materials["Unused"].shade.dither.strength: expected a finite number '
        "from 0 to 1, got 2"
    )


def test_a_cross_field_violation_is_not_a_parse_error():
    # The sum and the order depend on what a leaf is combined with, so they
    # are checked on the resolved values (`shading_resolve`).
    parsed = parse(
        v4(
            shade={"key": {"strength": 0.9}},
            materials={
                "A": {
                    "ordinary": True,
                    "shade": {
                        "sky": {"strength": 0.9},
                        "brightness": {"floor": 0.9, "ceiling": 0.1},
                    },
                }
            },
        )
    )
    assert parsed.shade.key_strength == 0.9


# Capture values of an ordinary mapping


def test_an_ordinary_mapping_overrides_the_capture_values_like_a_ramped_entry():
    parsed = parse(
        v4(
            materials={
                "Plain": {"ordinary": True, "shade": {"occlusion_weight": 0.5}},
                "Steel": {"uses": "metal", "shade": {"ao_distance_m": 2}},
                "Bare": {"ordinary": True},
                "Word": "ordinary",
                "OnlyResponse": {"ordinary": True, "shade": {"mode": "both"}},
            }
        )
    )
    records = [
        record(0, "Plain"),
        record(1, "Steel"),
        record(2, "Bare"),
        record(3, "Word"),
        record(4, "Plain", "BLEND"),
        record(5, "Missing"),
        record(6, "OnlyResponse"),
    ]
    globals_ = {"ao_distance_m": 0.3, "occlusion_weight": 0.25, "convexity_weight": 1.0}
    assert (
        capture_overrides(records, parsed, globals_)
        == [
            (0, 0.3, 0.5, 1.0),
            (1, 2.0, 0.25, 1.0),
            (4, 0.3, 0.5, 1.0),
        ]
        + [(6, 0.3, 0.25, 1.0)][:0]
    )


def test_the_capture_overrides_of_old_libraries_are_unchanged():
    old = library(
        schema="moskophoros.materials/3",
        materials={
            "Steel": {"uses": "metal", "shade": {"range": [1, 2], "ao_distance_m": 3}},
            "Plain": "ordinary",
            "Cloth": {"ramp": [8, 9]},
        },
    )
    parsed = validate_library(old, COLORS, source="lib")
    records = [record(0, "Steel"), record(1, "Plain"), record(2, "Cloth")]
    globals_ = {"ao_distance_m": 0.3, "occlusion_weight": 0.25, "convexity_weight": 1.0}
    assert capture_overrides(records, parsed, globals_) == [(0, 3.0, 0.25, 1.0)]


# Positions


YAML_TEXT = """\
schema: moskophoros.materials/4
ramps:
  metal: [12, 13, 14]
shade:
  mode: both
  sky: {strength: 0.5}
materials:
  Painted:
    ordinary: true
    shade:
      key:
        strength: 0.8
      range: [10, 90]
  Steel: {uses: metal}
"""


def read(text, **kwargs):
    return read_library_bytes(
        text.encode(), COLORS, source="library.yaml", shading=True
    )


def test_a_library_read_from_bytes_keeps_the_position_of_every_shading_value():
    parsed = read(YAML_TEXT)
    assert dict(parsed.where) == {
        ("shade", "mode"): (5, 3),
        ("shade", "sky", "strength"): (6, 9),
        ("materials", "Painted", "shade", "key", "strength"): (12, 9),
        ("materials", "Painted", "shade", "range"): (13, 7),
    }
    assert (
        parsed.origin(("shade", "sky", "strength")) == "library.yaml line 6, column 9"
    )
    assert parsed.source == "library.yaml"


def test_positions_and_source_take_no_part_in_comparing_libraries():
    positioned = read(YAML_TEXT)
    bare = parse(yaml.safe_load(YAML_TEXT))
    assert positioned == bare
    assert not bare.where


def test_a_document_without_positions_names_the_source_key_path_and_material():
    bare = parse(yaml.safe_load(YAML_TEXT))
    assert bare.origin(("materials", "Painted", "shade", "key", "strength")) == (
        'lib: materials["Painted"].shade.key.strength'
    )
    assert bare.origin(("shade", "mode")) == "lib: shade.mode"
    unsourced = materials.Library(bare.ramps, None, bare.materials)
    assert unsourced.origin(("shade", "mode")) == "the material library: shade.mode"


@pytest.mark.parametrize(
    ("edit", "problem"),
    [
        (
            ("      key:\n        strength: 0.8", "      key:\n        strength: 8"),
            'materials["Painted"].shade.key.strength: expected a finite number from '
            "0 to 1, got 8 at line 12, column 9",
        ),
        (
            ("    ordinary: true", "    ordinary: false"),
            'materials["Painted"].ordinary: expected true, which is the ordinary '
            "look, got false at line 9, column 5",
        ),
        (
            ("  mode: both", "  mode: sometimes"),
            'shade.mode: expected ramp, brightness, both or neither, got "sometimes" '
            "at line 5, column 3",
        ),
        (
            ("  sky: {strength: 0.5}", "  sky: null"),
            "shade.sky: expected a mapping of shading values, got null at line 6, "
            "column 3",
        ),
        (
            ("      range: [10, 90]", "      range: [90, 10]"),
            'materials["Painted"].shade.range: expected [lo, hi]',
        ),
    ],
)
def test_a_gated_error_about_a_shading_value_names_its_line_and_column(edit, problem):
    with pytest.raises(LibraryError) as raised:
        read(YAML_TEXT.replace(*edit))
    assert raised.value.source == "library.yaml"
    assert raised.value.problem.startswith(problem)


def test_the_error_names_the_material_for_every_form_of_entry():
    for entry in ({"ramp": [1]}, {"uses": "metal"}, {"ordinary": True}):
        problem = refused(with_entry(entry | {"shade": {"mode": "x"}}, name="A b"))
        assert problem.startswith('materials["A b"].shade.mode: ')


def test_a_materials_name_is_shown_as_json():
    problem = refused(with_entry({"ordinary": True, "shade": {"sky": 1}}, name='Q"'))
    assert problem.startswith('materials["Q\\""].shade.sky: ')


def test_a_deep_copy_of_the_document_is_never_changed():
    document = with_entry({"ordinary": True, "shade": copy.deepcopy(FULL)})
    before = copy.deepcopy(document)
    parse(document)
    assert document == before


def test_the_response_leaves_are_those_of_the_contract():
    assert [name for name in model.FIELDS.values()] == list(materials.RESPONSE_NAMES)
    assert [field for field in Shade.__dataclass_fields__][4:] == list(
        materials.RESPONSE_NAMES
    )
