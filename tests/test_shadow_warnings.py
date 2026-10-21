"""The warnings for a global given explicitly that a library or material
value takes precedence over, with the new response leaves and ordinary
entries (shading design contract 2, D-33, D-41, D-39). Libraries are generated
here."""

import pytest
import yaml
from test_materials import COLORS, record

from moskophoros import materials
from moskophoros.materials import (
    library_shade_warnings,
    override_warnings,
    ramp_warnings,
    shadow_warnings,
    validate_library,
)

V4 = "moskophoros.materials/4"


def gated(text, source="library.yaml"):
    return materials.read_library_bytes(
        text.encode(), COLORS, source=source, shading=True
    )


def old(text):
    return validate_library(yaml.safe_load(text), COLORS, source="lib")


# What the old builders say, which the new one repeats for old libraries

OLD_LIBRARY = """\
schema: moskophoros.materials/3
ramps:
  stone: [15, 14, 12, 10, 9]
  gold: {base: "#FFD700", bands: 4, lightness_step: 0.2, chroma_fade: 0.5}
default: stone
shade: {range: [50, 150]}
materials:
  Grey:
    uses: stone
    shade: {range: [120, 255], convexity_weight: 0.5}
  Rock:
    ramp: [1, 2, 3]
    shade: {range: [10, 20], occlusion_weight: 0, ao_distance_m: 1.2}
  Coin: {uses: gold, shade: {occlusion_weight: 0.7}}
  Ring: {ramp: {base: "#aabbcc", bands: 3, hue_shift_deg: 30}}
  Plain: {uses: stone}
  Glass: ordinary
"""
RECORDS = [
    record(0, "Rock"),
    record(1, "Grey"),
    record(2, "Coin"),
    record(3, "Ring", "BLEND"),
    record(4, "Plain"),
    record(5, "Glass"),
    record(6, "Missing"),
    record(7, None),
    record(8, "Grey"),
]
FORMULA = {"lightness_step": 0.12, "hue_shift_deg": -12.0, "chroma_fade": 0.3}


def generated(text):
    return materials.generate(text, COLORS, FORMULA)


@pytest.mark.parametrize(
    "schema", ["moskophoros.materials/3", "moskophoros.materials/2"]
)
@pytest.mark.parametrize(
    "explicit",
    [
        {},
        {"range": (84, 191)},
        {"convexity_weight": 0.0, "range": (84, 191), "occlusion_weight": 0.9},
        {"ao_distance_m": 0.3, "occlusion_weight": 0.25, "convexity_weight": 1.0},
    ],
)
def test_an_old_library_warns_exactly_as_the_old_builders_did(schema, explicit):
    document = yaml.safe_load(OLD_LIBRARY)
    document["schema"] = schema
    if schema.endswith("/2"):
        # A `/2` library has neither generated ramps nor a library shade.
        document.pop("shade")
        document["ramps"].pop("gold")
        document["materials"].pop("Coin")
        document["materials"]["Ring"] = {"ramp": [3, 4]}
    library = generated(validate_library(document, COLORS, source="lib"))
    formula = {"lightness_step": 0.5, "chroma_fade": 0.1, "hue_shift_deg": 5.0}
    expected = [
        *override_warnings(RECORDS, library, explicit),
        *library_shade_warnings(RECORDS, library, explicit),
        *ramp_warnings(RECORDS, library, formula),
    ]
    assert shadow_warnings(RECORDS, library, explicit, formula) == expected
    # Origins add nothing to a message about an old library's old values.
    labelled = {name: f"--{name}" for name in explicit} | {
        name: f"--{name}" for name in formula
    }
    assert shadow_warnings(RECORDS, library, explicit, formula, labelled) == expected


def test_the_equivalence_covers_messages_that_exist():
    library = generated(old(OLD_LIBRARY))
    explicit = {"convexity_weight": 0.0, "range": (84, 191), "occlusion_weight": 0.9}
    formula = {"lightness_step": 0.5, "hue_shift_deg": 5.0}
    messages = shadow_warnings(RECORDS, library, explicit, formula)
    assert any("keeps its own shade.range" in message for message in messages)
    assert any(
        "the material library gives shade.range" in message for message in messages
    )
    assert any("keeps its own lightness_step" in message for message in messages)


# The new response leaves and ordinary entries

NEW_LIBRARY = f"""\
schema: {V4}
ramps:
  metal: [12, 13, 14]
shade:
  range: [30, 60]
  mode: brightness
  sky: {{strength: 0.25}}
  dither: {{pattern: ordered4}}
materials:
  Painted:
    ordinary: true
    shade:
      ao_distance_m: 2
      key: {{strength: 0.5}}
      mode: both
  Steel:
    uses: metal
    shade:
      brightness: {{floor: 0.4}}
      range: [1, 2]
  Cloth: {{uses: metal}}
  Glow: ordinary
"""
NEW_RECORDS = [
    record(0, "Painted"),
    record(1, "Steel"),
    record(2, "Cloth"),
    record(3, "Glow"),
    record(4, "Unlisted"),
]


def test_a_response_override_on_an_explicit_global_warns_with_both_sources():
    library = gated(NEW_LIBRARY)
    explicit = {"mode": "ramp", "key.strength": 0.8, "brightness.floor": 0.1}
    origins = {
        "mode": "--shade-mode",
        "key.strength": "--bake-key-strength",
        "brightness.floor": "--project 'look'",
    }
    assert shadow_warnings(NEW_RECORDS, library, explicit, {}, origins) == [
        'material "Painted" keeps its own shade.mode, "both" (library.yaml line '
        '15, column 7), from the material library; the global "ramp" '
        "(--shade-mode) applies to materials without their own",
        'material "Painted" keeps its own shade.key.strength, 0.5 (library.yaml '
        "line 14, column 13), from the material library; the global 0.8 "
        "(--bake-key-strength) applies to materials without their own",
        'material "Steel" keeps its own shade.brightness.floor, 0.4 (library.yaml '
        "line 19, column 20), from the material library; the global 0.1 "
        "(--project 'look') applies to materials without their own",
        'the material library gives shade.mode "brightness" (library.yaml line 6, '
        'column 3) to its materials without their own; the global "ramp" '
        "(--shade-mode) does not reach them",
    ]


def test_ordinary_entry_overrides_of_the_old_values_warn_too():
    library = gated(NEW_LIBRARY)
    assert shadow_warnings(
        NEW_RECORDS,
        library,
        {"ao_distance_m": 0.3, "range": (84, 191)},
        {},
        {"ao_distance_m": "--ao-distance"},
    ) == [
        'material "Painted" keeps its own shade.ao_distance_m, 2.0 (library.yaml '
        "line 13, column 7), from the material library; the global 0.3 "
        "(--ao-distance) applies to materials without their own",
        'material "Steel" keeps its own shade.range, [1, 2], from the material '
        "library; the global [84, 191] applies to materials without their own",
        "the material library gives shade.range [30, 60] to its materials without "
        "their own; the global [84, 191] does not reach them",
    ]


def test_an_ordinary_entry_warns_without_an_origin_for_the_global():
    library = gated(NEW_LIBRARY)
    assert shadow_warnings(NEW_RECORDS, library, {"key.strength": 0.8}, {}) == [
        'material "Painted" keeps its own shade.key.strength, 0.5 (library.yaml '
        "line 14, column 13), from the material library; the global 0.8 applies to "
        "materials without their own"
    ]


def test_a_unit_less_origin_is_the_library_key_path_without_positions():
    document = yaml.safe_load(NEW_LIBRARY)
    library = validate_library(document, COLORS, source="inline", shading=True)
    assert shadow_warnings(NEW_RECORDS, library, {"key.strength": 0.8}, {}) == [
        'material "Painted" keeps its own shade.key.strength, 0.5 (inline: '
        'materials["Painted"].shade.key.strength), from the material library; the '
        "global 0.8 applies to materials without their own"
    ]


def test_only_what_was_given_explicitly_warns():
    library = gated(NEW_LIBRARY)
    # Defaults, the global file, a reused sheet and inheritance are the caller's
    # to leave out of `explicit`; a leaf it does not name never warns.
    assert shadow_warnings(NEW_RECORDS, library, {}, {}) == []
    assert shadow_warnings(NEW_RECORDS, library, {"snap": "ramp"}, {}) == []
    assert shadow_warnings(NEW_RECORDS, library, {"ground.strength": 0.3}, {}) == []
    # Cloth inherits the library's mode and Glow inherits everything: neither
    # warns, and a term merely being off is no event.
    assert shadow_warnings(
        [record(2, "Cloth"), record(3, "Glow")], library, {"mode": "both"}, {}
    ) == [
        'the material library gives shade.mode "brightness" (library.yaml line 6, '
        'column 3) to its materials without their own; the global "both" does not '
        "reach them"
    ]


def test_a_library_value_every_part_overrides_warns_nothing():
    library = gated(
        f"""\
schema: {V4}
ramps: {{metal: [1, 2]}}
shade: {{mode: neither}}
materials:
  A: {{ordinary: true, shade: {{mode: both}}}}
  B: {{uses: metal, shade: {{mode: brightness}}}}
"""
    )
    records = [record(0, "A"), record(1, "B"), record(2, "A")]
    assert shadow_warnings(records, library, {"mode": "ramp"}, {}) == [
        'material "A" keeps its own shade.mode, "both" (library.yaml line 5, column '
        '31), from the material library; the global "ramp" applies to materials '
        "without their own",
        'material "B" keeps its own shade.mode, "brightness" (library.yaml line 6, '
        'column 28), from the material library; the global "ramp" applies to '
        "materials without their own",
    ]
    # An unnamed part, or one with no entry, takes the library's own value.
    assert (
        len(
            shadow_warnings(
                [*records, record(None, None)], library, {"mode": "ramp"}, {}
            )
        )
        == 3
    )
    assert (
        len(
            shadow_warnings(
                [*records, record(3, "Other")], library, {"mode": "ramp"}, {}
            )
        )
        == 3
    )


def test_materials_taking_the_ordinary_look_by_alpha_mode_ignore_their_entry():
    library = gated(NEW_LIBRARY)
    odd = [record(0, "Painted", "SPECULAR")]
    assert shadow_warnings(odd, library, {"key.strength": 0.8}, {}) == []


def test_the_order_is_entries_then_the_library_then_the_ramps():
    library = materials.generate(
        gated(
            f"""\
schema: {V4}
ramps:
  gold: {{base: "#FFD700", bands: 4, chroma_fade: 0.5}}
shade: {{sky: {{strength: 0.25}}, range: [30, 60]}}
materials:
  A: {{uses: gold, shade: {{dither: {{strength: 0.5}}}}}}
  B: {{ordinary: true, shade: {{convexity_weight: 0.5}}}}
"""
        ),
        COLORS,
        FORMULA,
    )
    records = [record(0, "B"), record(1, "A"), record(2, "Other")]
    messages = shadow_warnings(
        records,
        library,
        {
            "convexity_weight": 1.0,
            "range": (84, 191),
            "sky.strength": 0.5,
            "dither.strength": 1.0,
        },
        {"chroma_fade": 0.3},
    )
    assert len(messages) == 5
    assert "shade.convexity_weight" in messages[0]
    assert "shade.dither.strength" in messages[1]
    assert "shade.range" in messages[2]
    assert "shade.sky.strength" in messages[3]
    assert messages[4].startswith('ramp "gold" keeps its own chroma_fade')


def test_a_resolved_global_the_library_only_shares_is_not_a_warning_event():
    library = gated(
        f"schema: {V4}\nramps: {{}}\nshade: {{mode: both}}\nmaterials: {{}}\n"
    )
    # Every part takes the library's value, but nothing was set explicitly.
    assert shadow_warnings([record(0, "A")], library, {}, {}) == []
