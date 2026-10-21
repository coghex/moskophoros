"""Resolving the shading response from the global settings and a library:
precedence, palette rules and the cross-field checks on resolved values
(shading design contract 1 and 2, D-10, D-25, D-26, D-33, D-39)."""

import pytest
from test_materials import COLORS

from moskophoros import materials, settings
from moskophoros import shading as model
from moskophoros.settings import merge, read_bytes
from moskophoros.shading_resolve import Look, resolve

V4 = "moskophoros.materials/4"
BASE = {**settings.DEFAULTS, **settings.SHADING_DEFAULTS}


def values(**changes):
    return {
        **BASE,
        **{f"shade.{name.replace('__', '.')}": v for name, v in changes.items()},
    }


def library(text):
    return materials.read_library_bytes(
        text.encode(), COLORS, source="library.yaml", shading=True
    )


def bare(document):
    return materials.validate_library(document, COLORS, source="lib", shading=True)


def problems(*args, **kwargs):
    with pytest.raises(model.ShadingError) as raised:
        resolve(*args, **kwargs)
    return list(raised.value.problems)


DEFAULT_RESPONSE = model.settings_of({}).response
DEFAULT_LOOK = Look(DEFAULT_RESPONSE, (84, 191), 0.3, 0.25, 1.0)


# Without a library


def test_the_defaults_resolve_for_every_identity_without_a_library():
    resolved = resolve(values(), has_palette=False)
    assert resolved.settings == model.settings_of({})
    assert resolved.base == DEFAULT_LOOK
    assert resolved.fallback == DEFAULT_LOOK
    assert resolved.materials == {}
    assert resolved.look(None) == resolved.look("anything") == DEFAULT_LOOK


def test_the_global_response_and_range_apply_to_every_identity():
    resolved = resolve(
        values(mode="both", brightness__floor=0.1, shade__range=None)
        | {"shade.range": (10, 20), "shade.ao_distance_m": 1.5},
        has_palette=False,
    )
    assert resolved.fallback.response.mode == "both"
    assert resolved.fallback.response.brightness_floor == 0.1
    assert resolved.fallback.shade_range == (10, 20)
    assert resolved.fallback.ao_distance_m == 1.5
    assert resolved.base == resolved.fallback


def test_a_palette_is_optional_unless_snap_is_not_off():
    resolve(values(), has_palette=False)
    resolve(values(mode="neither"), has_palette=False)
    resolve(values(snap="ramp"), has_palette=True)
    resolve(values(snap="off"), has_palette=True)
    for snap in ("ramp", "palette"):
        assert problems(values(snap=snap), has_palette=False) == [
            f'shade.snap "{snap}" (shipped default) needs a palette, even when the '
            "mode leaves snap unused"
        ]


def test_snap_names_where_it_was_set_even_when_the_mode_ignores_it():
    assert problems(
        values(snap="palette", mode="neither"),
        has_palette=False,
        origins={"shade.snap": "--shade-snap"},
    ) == [
        'shade.snap "palette" (--shade-snap) needs a palette, even when the mode '
        "leaves snap unused"
    ]


# A library


LIBRARY = f"""\
schema: {V4}
ramps:
  metal: [12, 13, 14]
shade:
  range: [30, 60]
  mode: brightness
  brightness: {{floor: 0.4}}
materials:
  Painted:
    uses: metal
    shade:
      mode: both
      key: {{strength: 0.5}}
  Glow:
    ordinary: true
    shade:
      ao_distance_m: 2
      range: [1, 2]
      mode: neither
  Plain: ordinary
  Steel: {{uses: metal}}
"""


def test_a_library_needs_a_palette():
    assert problems(values(), bare(materials_doc()), has_palette=False) == [
        "the material library needs a palette"
    ]


def materials_doc(**changes):
    return {
        "schema": V4,
        "ramps": {"metal": [1, 2, 3]},
        "materials": {"Steel": {"uses": "metal"}},
    } | changes


def test_material_beats_library_beats_global_for_every_response_leaf():
    resolved = resolve(
        values(
            mode="ramp",
            ambient_form=True,
            key__strength=0.1,
            sky__strength=0.1,
            ground__strength=0.1,
            brightness__floor=0.1,
            brightness__ceiling=0.9,
            dither__pattern="ordered2",
            dither__strength=0.1,
        ),
        bare(
            materials_doc(
                shade={
                    "mode": "both",
                    "ambient_form": False,
                    "key": {"strength": 0.2},
                    "sky": {"strength": 0.2},
                    "brightness": {"floor": 0.2},
                    "dither": {"pattern": "ordered4"},
                },
                materials={
                    "Own": {
                        "uses": "metal",
                        "shade": {
                            "mode": "neither",
                            "key": {"strength": 0.3},
                            "brightness": {"ceiling": 0.8},
                            "dither": {"strength": 0.3},
                        },
                    },
                    "Bare": {"uses": "metal"},
                },
            )
        ),
        has_palette=True,
    )
    assert resolved.fallback.response == model.Response(
        mode="both",
        ambient_form=False,
        key_strength=0.2,
        sky_strength=0.2,
        ground_strength=0.1,
        brightness_floor=0.2,
        brightness_ceiling=0.9,
        dither_pattern="ordered4",
        dither_strength=0.1,
    )
    assert resolved.materials["Bare"].response == resolved.fallback.response
    assert resolved.materials["Own"].response == model.Response(
        mode="neither",
        ambient_form=False,
        key_strength=0.3,
        sky_strength=0.2,
        ground_strength=0.1,
        brightness_floor=0.2,
        brightness_ceiling=0.8,
        dither_pattern="ordered4",
        dither_strength=0.3,
    )
    # The global values were the explicit ones and none beats a library's.
    assert resolved.settings.response.mode == "ramp"
    assert resolved.base.response.key_strength == 0.1


def test_a_library_leaf_equal_to_the_global_one_still_comes_from_the_library():
    resolved = resolve(
        values(mode="ramp"),
        bare(materials_doc(shade={"mode": "ramp"})),
        has_palette=True,
    )
    assert resolved.fallback.response.mode == "ramp"


def test_leaves_inherit_independently_down_the_chain():
    resolved = resolve(
        values(brightness__ceiling=0.9),
        bare(
            materials_doc(
                shade={"brightness": {"floor": 0.2}},
                materials={
                    "A": {"uses": "metal", "shade": {"brightness": {"floor": 0.15}}},
                    "B": {"uses": "metal", "shade": {"brightness": {"ceiling": 0.5}}},
                },
            )
        ),
        has_palette=True,
    )
    a, b = resolved.materials["A"].response, resolved.materials["B"].response
    assert (a.brightness_floor, a.brightness_ceiling) == (0.15, 0.9)
    assert (b.brightness_floor, b.brightness_ceiling) == (0.2, 0.5)


def test_the_range_and_capture_values_resolve_entry_then_library_then_global():
    resolved = resolve(
        values() | {"shade.range": (1, 100), "shade.occlusion_weight": 0.5},
        library(LIBRARY),
        has_palette=True,
    )
    # A material with no own range takes the library's, else the global one.
    assert resolved.fallback.shade_range == (30, 60)
    assert resolved.look("Steel").shade_range == (30, 60)
    assert resolved.look("Unlisted").shade_range == (30, 60)
    assert resolved.look(None).shade_range == (30, 60)
    # The ordinary mapping's own capture values and range win; it falls back
    # to the global capture values for the ones it leaves out.
    glow = resolved.look("Glow")
    assert glow.shade_range == (1, 2)
    assert (glow.ao_distance_m, glow.occlusion_weight, glow.convexity_weight) == (
        2.0,
        0.5,
        1.0,
    )
    assert resolved.look("Steel").ao_distance_m == 0.3
    assert resolved.look("Steel").occlusion_weight == 0.5


def test_without_a_library_range_the_global_range_applies():
    resolved = resolve(
        values() | {"shade.range": (1, 100)},
        bare(materials_doc(shade={"mode": "both"})),
        has_palette=True,
    )
    assert resolved.fallback.shade_range == (1, 100)
    assert resolved.look("Steel").shade_range == (1, 100)


def test_an_ordinary_entry_inherits_the_response_it_does_not_force_neither():
    resolved = resolve(
        values(mode="both"),
        bare(
            materials_doc(
                materials={
                    "Word": "ordinary",
                    "Map": {"ordinary": True},
                    "Tuned": {
                        "ordinary": True,
                        "shade": {"brightness": {"floor": 0.2}},
                    },
                }
            )
        ),
        has_palette=True,
    )
    for name in ("Word", "Map"):
        assert resolved.look(name).response.mode == "both"
        assert resolved.look(name) == resolved.fallback
    assert resolved.look("Tuned").response.mode == "both"
    assert resolved.look("Tuned").response.brightness_floor == 0.2


def test_every_entry_is_resolved_in_name_order_unused_ones_included():
    resolved = resolve(values(), library(LIBRARY), has_palette=True)
    assert list(resolved.materials) == ["Glow", "Painted", "Plain", "Steel"]
    assert resolved.look("Glow").response.mode == "neither"
    assert resolved.look("Painted").response.mode == "both"
    assert resolved.look("Plain").response.mode == "brightness"
    assert resolved.look("Painted").response.key_strength == 0.5
    assert resolved.look("Painted").response.brightness_floor == 0.4


def test_the_library_response_never_changes_the_global_settings():
    resolved = resolve(values(mode="neither"), library(LIBRARY), has_palette=True)
    assert resolved.settings == model.settings_of({"shade.mode": "neither"})
    assert resolved.base.response.mode == "neither"


# Cross-field rules on resolved values


def test_a_floor_above_the_ceiling_names_both_values_and_where_they_came_from():
    first = read_bytes(
        b"shade:\n  brightness: {floor: 0.8}\n",
        source="config.yaml",
        directory=".",
        shading=True,
    )
    flags = {"shade.brightness.ceiling": 0.5}
    origins = settings.origins([("config.yaml", first)]) | {
        "shade.brightness.ceiling": "--brightness-ceiling"
    }
    assert problems(
        values() | dict(first) | flags, has_palette=False, origins=origins
    ) == [
        "shade.brightness.floor 0.8 (config.yaml line 2, column 16) exceeds "
        "shade.brightness.ceiling 0.5 (--brightness-ceiling)"
    ]


def test_a_partial_layer_a_later_layer_corrects_is_valid():
    early = read_bytes(
        b"shade:\n  brightness: {ceiling: 0.2}\n",
        source="a.yaml",
        directory=".",
        shading=True,
    )
    late = read_bytes(
        b"shade:\n  brightness: {floor: 0.1}\n",
        source="b.yaml",
        directory=".",
        shading=True,
    )
    both = values() | dict(merge(early, late))
    resolved = resolve(both, has_palette=False)
    assert resolved.base.response.brightness_floor == 0.1
    assert resolved.base.response.brightness_ceiling == 0.2


def test_the_earlier_layer_alone_names_the_default_it_conflicts_with():
    early = read_bytes(
        b"shade:\n  brightness: {ceiling: 0.2}\n",
        source="a.yaml",
        directory=".",
        shading=True,
    )
    origins = settings.origins([("a.yaml", early)])
    assert problems(values() | dict(early), has_palette=False, origins=origins) == [
        "shade.brightness.floor 0.3 (shipped default) exceeds "
        "shade.brightness.ceiling 0.2 (a.yaml line 2, column 16)"
    ]


def test_a_library_ceiling_is_checked_against_the_global_floor_it_meets():
    # Global floor 0.8 against the default ceiling 1 is fine; a library ceiling
    # of 0.9 keeps it fine, while 0.7 conflicts and names the library's line.
    ok = resolve(
        values(brightness__floor=0.8),
        library(
            f"schema: {V4}\nramps: {{}}\nshade:\n  brightness: {{ceiling: 0.9}}\nmaterials: {{}}\n"
        ),
        has_palette=True,
    )
    assert ok.fallback.response.brightness_ceiling == 0.9
    assert problems(
        values(brightness__floor=0.8),
        library(
            f"schema: {V4}\nramps: {{}}\nshade:\n  brightness: {{ceiling: 0.7}}\nmaterials: {{}}\n"
        ),
        has_palette=True,
        origins={"shade.brightness.floor": "config.yaml line 12, column 3"},
    ) == [
        "the material library's shade: shade.brightness.floor 0.8 (config.yaml line "
        "12, column 3) exceeds shade.brightness.ceiling 0.7 (library.yaml line 4, "
        "column 16)"
    ]


def test_a_strength_sum_over_one_across_sources_names_all_three_and_the_material():
    painted = library(
        f"""\
schema: {V4}
ramps: {{}}
materials:
  Painted:
    ordinary: true
    shade:
      sky:
        strength: 0.5
"""
    )
    assert problems(
        values(key__strength=0.8),
        painted,
        has_palette=True,
        origins={"shade.key.strength": "--bake-key-strength"},
    ) == [
        'material "Painted": shade.key.strength 0.8 (--bake-key-strength) + '
        "shade.sky.strength 0.5 (library.yaml line 8, column 9) + "
        "shade.ground.strength 0.0 (shipped default) = 1.3, exceeds 1"
    ]


def test_a_document_without_positions_names_the_source_path_and_material():
    document = materials_doc(
        materials={"Painted": {"ordinary": True, "shade": {"sky": {"strength": 0.5}}}}
    )
    assert problems(values(key__strength=0.8), bare(document), has_palette=True) == [
        'material "Painted": shade.key.strength 0.8 (shipped default) + '
        'shade.sky.strength 0.5 (lib: materials["Painted"].shade.sky.strength) + '
        "shade.ground.strength 0.0 (shipped default) = 1.3, exceeds 1"
    ]


def test_an_unused_entry_is_checked_too():
    document = materials_doc(
        materials={
            "Used": {"uses": "metal"},
            "Unused": {"uses": "metal", "shade": {"brightness": {"floor": 0.99}}},
        }
    )
    errors = problems(values(brightness__ceiling=0.9), bare(document), has_palette=True)
    assert errors == [
        'material "Unused": shade.brightness.floor 0.99 '
        '(lib: materials["Unused"].shade.brightness.floor) exceeds '
        "shade.brightness.ceiling 0.9 (shipped default)"
    ]


def test_the_library_wide_response_is_checked_once_for_everything_that_inherits_it():
    document = materials_doc(
        shade={"key": {"strength": 0.7}, "sky": {"strength": 0.7}},
        materials={
            "A": {"uses": "metal"},
            "B": {"ordinary": True, "shade": {"mode": "both"}},
            "C": {"uses": "metal", "shade": {"ground": {"strength": 0.1}}},
        },
    )
    errors = problems(values(), bare(document), has_palette=True)
    # One for the library-wide response, and one for the entry that changed a
    # contributing value; A and B repeat nothing.
    assert len(errors) == 2
    assert errors[0].startswith(
        "the material library's shade: shade.key.strength 0.7 ("
    )
    assert errors[1].startswith('material "C": shade.key.strength 0.7 (')
    assert "shade.ground.strength 0.1 (" in errors[1]
    assert errors[1].endswith("= 1.5, exceeds 1")


def test_failures_come_in_the_stated_order():
    document = materials_doc(
        shade={"brightness": {"floor": 0.95}},
        materials={
            "Zed": {"uses": "metal", "shade": {"key": {"strength": 1}}},
            "Alpha": {"ordinary": True, "shade": {"key": {"strength": 1}}},
        },
    )
    errors = problems(
        values(sky__strength=0.5, brightness__ceiling=0.9),
        bare(document),
        has_palette=False,
        origins={"shade.sky.strength": "--bake-sky-strength"},
    )
    assert [error.split(":")[0] for error in errors] == [
        "the material library needs a palette",
        # The global response: the sky strength alone is within budget, the
        # shipped floor 0.3 within the option's ceiling 0.9.
        "the material library's shade",
        'material "Alpha"',
        'material "Zed"',
    ]
    assert errors[1].startswith(
        "the material library's shade: shade.brightness.floor 0.95"
    )
    assert "= 1.5, exceeds 1" in errors[2] and "= 1.5, exceeds 1" in errors[3]


def test_the_global_response_is_reported_before_the_library_s():
    errors = problems(
        values(key__strength=0.8, sky__strength=0.8),
        bare(materials_doc(shade={"mode": "both"})),
        has_palette=True,
    )
    assert len(errors) == 1
    assert errors[0].startswith("shade.key.strength 0.8 (shipped default) + ")


def test_the_budget_and_the_order_are_exact_at_their_boundaries():
    resolve(
        values(key__strength=0.1, sky__strength=0.2, ground__strength=0.7),
        has_palette=False,
    )
    resolve(
        values(ground__strength=0.7, sky__strength=0.2, key__strength=0.1),
        has_palette=False,
    )
    resolve(values(key__strength=1.0), has_palette=False)
    resolve(values(brightness__floor=0.5, brightness__ceiling=0.5), has_palette=False)
    resolve(values(brightness__floor=0.0, brightness__ceiling=0.0), has_palette=False)
    assert problems(values(key__strength=0.8, sky__strength=0.5), has_palette=False)
    assert problems(
        values(brightness__floor=0.5, brightness__ceiling=0.4999999), has_palette=False
    )


def test_a_resolved_error_reports_the_budget_and_the_order_together():
    errors = problems(
        values(
            key__strength=1.0,
            sky__strength=1.0,
            brightness__floor=1.0,
            brightness__ceiling=0.0,
        ),
        has_palette=False,
    )
    assert errors == [
        "shade.key.strength 1.0 (shipped default) + shade.sky.strength 1.0 "
        "(shipped default) + shade.ground.strength 0.0 (shipped default) = 2.0, "
        "exceeds 1",
        "shade.brightness.floor 1.0 (shipped default) exceeds "
        "shade.brightness.ceiling 0.0 (shipped default)",
    ]
