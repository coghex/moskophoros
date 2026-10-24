"""The export settings in the schema table and the internal reader (export
design P-7, part 1; P-13, EXP-2).

The settings are defined but inactive: `read_bytes` refuses them, and these
tests read them through the internal reader that opens the gate.
"""

from types import MappingProxyType

import pytest

from moskophoros import settings
from moskophoros.settings import SettingsError, merge, merge_clips, read_bytes


def read(text):
    return settings._read_document(
        text.encode("utf-8"), source="s.yaml", directory="/s", open_gate=True
    )


def refused(text):
    with pytest.raises(SettingsError) as raised:
        read(text)
    return raised.value.problem


# The table: what is defined, what is active


NEW_GLOBAL = [
    "stored_directions",
    "direction_names",
    "mirrors",
    "export.formats",
    "export.frame_path",
    "export.atlas_path",
    "export.sheet_path",
    "export.atlas_padding",
]


def test_the_new_settings_are_defined_after_the_active_ones_and_inactive():
    names = list(settings.SCHEMA)
    assert names[-len(NEW_GLOBAL) :] == NEW_GLOBAL
    assert list(settings.ACTIVE_SCHEMA) == names[: -len(NEW_GLOBAL)]
    assert not any(settings.SCHEMA[name].active for name in NEW_GLOBAL)
    assert all(settings.SCHEMA[name].active for name in settings.ACTIVE_SCHEMA)
    assert list(settings.CLIP_SCHEMA) == [
        "frames",
        "fps",
        "stored_directions",
        "mirrors",
        "output_name",
    ]
    assert list(settings.ACTIVE_CLIP_SCHEMA) == ["frames"]


def test_the_public_groups_and_defaults_leave_the_inactive_rows_out():
    assert settings.GROUPS == {"camera", "shade", "light", "ramp"}
    assert settings.ALL_GROUPS == settings.GROUPS | {"export"}
    assert set(settings.DEFAULTS) == set(settings.ACTIVE_SCHEMA)
    assert not set(NEW_GLOBAL) & set(settings.DEFAULTS)
    shipped = settings.read_defaults()
    assert list(shipped) == list(settings.ACTIVE_SCHEMA)
    assert "clips" not in shipped


def test_every_new_setting_has_its_internal_default():
    assert {name: settings.ALL_DEFAULTS[name] for name in NEW_GLOBAL} == {
        "stored_directions": "all",
        "direction_names": {},
        "mirrors": {},
        "export.formats": ("sheet",),
        "export.frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
        "export.atlas_path": "atlases/{clip}{map}.png",
        "export.sheet_path": "sheet{map}.png",
        "export.atlas_padding": 0,
    }
    assert {
        name: setting.default
        for name, setting in settings.CLIP_SCHEMA.items()
        if name != "frames"
    } == {"fps": None, "stored_directions": None, "mirrors": None, "output_name": None}
    assert set(settings.ALL_DEFAULTS) == set(settings.SCHEMA)


def test_the_shipped_defaults_file_holds_no_inactive_setting():
    text = settings.resources.files("moskophoros").joinpath("defaults.yaml")
    document = text.read_text("utf-8")
    for name in ("stored_directions", "direction_names", "mirrors", "export", "clips:"):
        assert f"\n{name}" not in document


# The public reader keeps the gate shut


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (
            "stored_directions: all\n",
            "stored_directions: not available yet at line 1, column 1",
        ),
        (
            "direction_names: {}\n",
            "direction_names: not available yet at line 1, column 1",
        ),
        ("version: 1\nmirrors: {}\n", "mirrors: not available yet at line 2, column 1"),
        ("export: {}\n", "export: not available yet at line 1, column 1"),
        ("export: 5\n", "export: not available yet at line 1, column 1"),
        (
            "export:\n  formats: [sheet]\n",
            "export: not available yet at line 1, column 1",
        ),
        (
            "clips:\n  Walk:\n    fps: null\n",
            "clips.Walk.fps: not available yet at line 3, column 5",
        ),
        (
            "clips:\n  Walk: {output_name: null}\n",
            "clips.Walk.output_name: not available yet at line 2, column 10",
        ),
    ],
)
def test_the_public_reader_refuses_every_inactive_key_as_not_available_yet(
    text, problem
):
    with pytest.raises(SettingsError) as raised:
        read_bytes(text.encode(), source="s.yaml", directory="/s")
    assert raised.value.problem == problem
    with pytest.raises(SettingsError):
        read_bytes(text.encode(), source="s.yaml", directory="/s", shipped=True)


def test_an_empty_clip_entry_and_a_count_are_still_accepted_publicly():
    layer = read_bytes(
        b"clips:\n  A: {}\n  B: {frames: 3}\n", source="s.yaml", directory="/s"
    )
    assert layer["clips"] == {"B": {"frames": 3}}


# Reading: types, ranges and positions


def test_the_new_global_settings_read_as_typed_values():
    layer = read(
        "stored_directions: [0, 4, 3]\n"
        "direction_names: {4: back, 0: front}\n"
        "mirrors: {7: 1, 6: 2}\n"
        "export:\n"
        "  formats: [atlases, sheet]\n"
        "  frame_path: f/{clip}/{frame}.png\n"
        "  atlas_path: a/{clip}.png\n"
        "  sheet_path: s.png\n"
        "  atlas_padding: 64\n"
    )
    assert dict(layer) == {
        "stored_directions": (0, 4, 3),
        "direction_names": {0: "front", 4: "back"},
        "mirrors": {6: 2, 7: 1},
        "export.formats": ("sheet", "atlases"),
        "export.frame_path": "f/{clip}/{frame}.png",
        "export.atlas_path": "a/{clip}.png",
        "export.sheet_path": "s.png",
        "export.atlas_padding": 64,
    }
    assert isinstance(layer["mirrors"], MappingProxyType)
    assert layer.where["export.formats"] == (5, 3)


def test_stored_directions_accepts_all_and_ordered_distinct_indices():
    assert read("stored_directions: all\n")["stored_directions"] == "all"
    assert read("stored_directions: [63]\n")["stored_directions"] == (63,)
    assert read("stored_directions: [5, 0]\n")["stored_directions"] == (5, 0)


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        (
            "[]",
            "expected all or a nonempty list of distinct direction indices, got an empty list",
        ),
        (
            "none",
            "expected all or a nonempty list of distinct direction indices, got 'none'",
        ),
        (
            "null",
            "expected all or a nonempty list of distinct direction indices, got null",
        ),
        ("3", "expected all or a nonempty list of distinct direction indices, got 3"),
        (
            "true",
            "expected all or a nonempty list of distinct direction indices, got true",
        ),
    ],
)
def test_stored_directions_refuses_other_shapes(value, problem):
    assert refused(f"stored_directions: {value}\n") == (
        f"stored_directions: {problem} at line 1, column 1"
    )


@pytest.mark.parametrize(
    ("value", "at", "problem"),
    [
        ("[0, 0]", "stored_directions.1", "the direction 0 is listed twice"),
        ("[1, 2, 1]", "stored_directions.2", "the direction 1 is listed twice"),
        (
            "[64]",
            "stored_directions.0",
            "expected a direction index, a whole number from 0 to 63, got 64",
        ),
        (
            "[-1]",
            "stored_directions.0",
            "expected a direction index, a whole number from 0 to 63, got -1",
        ),
        (
            "[0, 1.0]",
            "stored_directions.1",
            "expected a direction index, a whole number from 0 to 63, got 1.0",
        ),
        (
            "[true]",
            "stored_directions.0",
            "expected a direction index, a whole number from 0 to 63, got true",
        ),
        (
            "['1']",
            "stored_directions.0",
            "expected a direction index, a whole number from 0 to 63, got '1'",
        ),
    ],
)
def test_stored_directions_names_the_bad_entry(value, at, problem):
    text = f"stored_directions: {value}\n"
    assert refused(text).startswith(f"{at}: {problem} at line 1, column ")


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (
            "direction_names: {'1': right}\n",
            "direction_names.1: expected a direction index key, a whole number from 0 to 63, got '1'",
        ),
        (
            "direction_names: {64: x}\n",
            "direction_names.64: expected a direction index key, a whole number from 0 to 63, got 64",
        ),
        (
            "direction_names: {true: x}\n",
            "direction_names.True: expected a direction index key, a whole number from 0 to 63, got true",
        ),
        ("direction_names: {1: 2}\n", "direction_names.1: expected a name, got 2"),
        (
            "direction_names: {1: null}\n",
            "direction_names.1: expected a name, got null",
        ),
        (
            "direction_names: [a]\n",
            "direction_names: expected a mapping of direction index to name, got a list",
        ),
        (
            "direction_names: null\n",
            "direction_names: expected a mapping of direction index to name, got null",
        ),
        (
            "mirrors: {'7': 1}\n",
            "mirrors.7: expected a target direction index key, a whole number from 0 to 63, got '7'",
        ),
        (
            "mirrors: {7: '1'}\n",
            "mirrors.7: expected a stored source direction index, a whole number from 0 to 63, got '1'",
        ),
        (
            "mirrors: {7: 64}\n",
            "mirrors.7: expected a stored source direction index, a whole number from 0 to 63, got 64",
        ),
        (
            "mirrors: {7: 1.0}\n",
            "mirrors.7: expected a stored source direction index, a whole number from 0 to 63, got 1.0",
        ),
        (
            "mirrors: null\n",
            "mirrors: expected a mapping of target direction index to stored source index, got null",
        ),
    ],
)
def test_the_maps_name_the_bad_entry_and_refuse_string_digits_and_null(text, problem):
    assert refused(text).startswith(problem + " at line ")


def test_a_map_entry_is_located_at_its_own_key():
    assert refused("direction_names:\n  1: right\n  2: 7\n") == (
        "direction_names.2: expected a name, got 7 at line 3, column 3"
    )


def test_an_empty_map_is_valid_and_clears():
    assert read("direction_names: {}\nmirrors: {}\n")["mirrors"] == {}


@pytest.mark.parametrize(
    ("value", "canonical"),
    [
        ("[sheet]", ("sheet",)),
        ("[frames]", ("frames",)),
        ("[atlases]", ("atlases",)),
        ("[atlases, frames, sheet]", ("sheet", "frames", "atlases")),
        ("[frames, sheet]", ("sheet", "frames")),
        ("[sheet, atlases]", ("sheet", "atlases")),
    ],
)
def test_formats_normalise_to_one_canonical_order(value, canonical):
    assert read(f"export: {{formats: {value}}}\n")["export.formats"] == canonical


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("[]", "got an empty list"),
        ("[sheet, sheet]", "the format sheet is listed twice"),
        ("[frames, sheet, frames]", "the format frames is listed twice"),
        ("[png]", "got 'png'"),
        ("[Sheet]", "got 'Sheet'"),
        ("[1]", "got 1"),
        ("sheet", "got 'sheet'"),
        ("null", "got null"),
    ],
)
def test_formats_refuse_empty_duplicate_unknown_and_non_lists(value, problem):
    assert problem in refused(f"export:\n  formats: {value}\n")


@pytest.mark.parametrize("value", [0, 1, 32, 64])
def test_atlas_padding_accepts_its_endpoints_and_between(value):
    assert (
        read(f"export: {{atlas_padding: {value}}}\n")["export.atlas_padding"] == value
    )


@pytest.mark.parametrize("value", ["-1", "65", "1.0", "'1'", "true", "null", "[1]"])
def test_atlas_padding_refuses_everything_else(value):
    problem = refused(f"export: {{atlas_padding: {value}}}\n")
    assert problem.startswith(
        "export.atlas_padding: expected a whole number from 0 to 64"
    )


@pytest.mark.parametrize("name", ["frame_path", "atlas_path", "sheet_path"])
def test_a_template_is_checked_for_syntax_whatever_format_is_selected(name):
    text = f"export:\n  formats: [sheet]\n  {name}: 'x/{{bogus}}.png'\n"
    problem = refused(text)
    assert problem.startswith(
        f"export.{name}: the template has the unknown token '{{bogus}}'"
    )


def test_a_template_refuses_a_token_its_format_cannot_use():
    assert refused("export: {atlas_path: 'a/{direction}.png'}\n").startswith(
        "export.atlas_path: the template uses '{direction}', which an atlas path cannot use"
    )
    assert refused("export: {sheet_path: '{clip}.png'}\n").startswith(
        "export.sheet_path: the template uses '{clip}', which a sheet path cannot use"
    )
    assert read(
        "export: {frame_path: '{subject}/{variant}/{clip}/{direction}/{frame}{map}.png'}\n"
    )


@pytest.mark.parametrize("value", ["null", "3", "[a]"])
def test_a_template_must_be_a_string(value):
    assert "the template is not a string" in refused(
        f"export: {{sheet_path: {value}}}\n"
    )


# Per-clip leaves


def test_clip_leaves_read_by_leaf_with_their_positions():
    layer = read(
        "clips:\n"
        "  Walk:\n"
        "    frames: 6\n"
        "    fps: 6\n"
        "    stored_directions: all\n"
        "    mirrors: {7: 1}\n"
        "    output_name: stride\n"
        "  Idle: {fps: null, stored_directions: null, mirrors: null, output_name: null}\n"
        "  Pose: {}\n"
    )
    assert layer["clips"] == {
        "Walk": {
            "frames": 6,
            "fps": 6.0,
            "stored_directions": "all",
            "mirrors": {7: 1},
            "output_name": "stride",
        },
        "Idle": {
            "fps": None,
            "stored_directions": None,
            "mirrors": None,
            "output_name": None,
        },
    }
    assert layer.where[("clips", "Walk", "fps")] == (4, 5)
    assert layer.where[("clips", "Walk", "output_name")] == (7, 5)
    assert layer.where[("clips", "Idle", "mirrors")] == (8, 46)


def test_a_clip_with_empty_entries_is_not_recorded():
    assert "clips" not in read("clips:\n  Pose: {}\n")


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (
            "fps: 0",
            "clips.A.fps: expected a finite number greater than 0, or null, got 0",
        ),
        (
            "fps: -1",
            "clips.A.fps: expected a finite number greater than 0, or null, got -1",
        ),
        (
            "fps: .nan",
            "clips.A.fps: expected a finite number greater than 0, or null, got '.nan'",
        ),
        (
            "fps: '6'",
            "clips.A.fps: expected a finite number greater than 0, or null, got '6'",
        ),
        (
            "fps: true",
            "clips.A.fps: expected a finite number greater than 0, or null, got true",
        ),
        (
            "stored_directions: []",
            "clips.A.stored_directions: expected all or a nonempty list",
        ),
        (
            "stored_directions: [1, 1]",
            "clips.A.stored_directions.1: the direction 1 is listed twice",
        ),
        (
            "stored_directions: [64]",
            "clips.A.stored_directions.0: expected a direction index",
        ),
        (
            "stored_directions: none",
            "clips.A.stored_directions: expected all or a nonempty list",
        ),
        (
            "mirrors: {'7': 1}",
            "clips.A.mirrors.7: expected a target direction index key",
        ),
        (
            "mirrors: [1]",
            "clips.A.mirrors: expected a mapping of target direction index",
        ),
        ("output_name: 3", "clips.A.output_name: expected a name or null, got 3"),
        (
            "output_name: [a]",
            "clips.A.output_name: expected a name or null, got a list",
        ),
    ],
)
def test_a_bad_clip_leaf_names_its_path(text, problem):
    assert refused(f"clips:\n  A:\n    {text}\n").startswith(problem)


def test_booleans_and_nonfinite_numbers_are_no_fps():
    for value in ("true", "false", ".inf", "-.inf", "'inf'"):
        assert "clips.A.fps" in refused(f"clips:\n  A: {{fps: {value}}}\n")
    assert read("clips:\n  A: {fps: 1e-300}\n")["clips"]["A"]["fps"] == 1e-300


def test_every_clip_entry_is_checked_even_when_unused_or_overwritten():
    assert "clips.Nowhere.fps" in refused(
        "clips:\n  Walk: {frames: 2}\n  Nowhere: {fps: 0}\n"
    )
    assert "clips.Walk.mirrors" in refused("clips:\n  Walk: {mirrors: 3}\n")


# Merging layers


def layers(*texts):
    return [read(text) for text in texts]


def test_global_lists_and_maps_replace_whole_and_empty_maps_clear():
    low, high = layers(
        "stored_directions: [0, 1, 2]\ndirection_names: {1: a, 2: b}\n"
        "mirrors: {5: 1}\nexport: {formats: [frames, sheet]}\n",
        "stored_directions: [3]\ndirection_names: {}\nmirrors: {}\n"
        "export: {formats: [atlases]}\n",
    )
    merged = merge(low, high)
    assert merged["stored_directions"] == (3,)
    assert merged["direction_names"] == {}
    assert merged["mirrors"] == {}
    assert merged["export.formats"] == ("atlases",)
    assert merge(low, read("stored_directions: all\n"))["stored_directions"] == "all"


def test_the_other_export_leaves_merge_independently():
    low, high = layers(
        "export:\n  frame_path: a/{frame}.png\n  atlas_padding: 3\n",
        "export: {sheet_path: s.png, atlas_padding: 5}\n",
    )
    merged = merge(low, high)
    assert merged["export.frame_path"] == "a/{frame}.png"
    assert merged["export.sheet_path"] == "s.png"
    assert merged["export.atlas_padding"] == 5
    assert "export.formats" not in merged


def test_clip_entries_merge_by_clip_and_leaf_and_null_clears():
    low, high = layers(
        "clips:\n  Walk: {frames: 6, fps: 8, mirrors: {7: 1}}\n  Idle: {frames: 2}\n",
        "clips:\n  Walk: {fps: 4, mirrors: null, output_name: stride}\n"
        "  Idle: {frames: null}\n  Run: {fps: 9}\n",
    )
    assert merge(low, high)["clips"] == {
        "Walk": {
            "frames": 6,
            "fps": 4.0,
            "mirrors": None,
            "output_name": "stride",
        },
        "Idle": {"frames": None},
        "Run": {"fps": 9.0},
    }
    assert merge_clips({"A": {"fps": 1.0}}, {"A": {"frames": 2}}) == {
        "A": {"fps": 1.0, "frames": 2}
    }
    merged = merge(low, high)
    assert merged.where[("clips", "Walk", "frames")] == (2, 10)
    assert merged.where[("clips", "Run", "fps")] == (4, 9)


def test_a_clip_layer_is_not_changed_by_a_merge():
    low, high = layers("clips:\n  A: {fps: 1}\n", "clips:\n  A: {fps: 2}\n")
    merge(low, high)
    assert low["clips"] == {"A": {"fps": 1.0}}
    assert high["clips"] == {"A": {"fps": 2.0}}


def test_reading_a_nonmapping_clip_value_stays_an_error():
    assert "clips: expected a mapping of clips by name" in refused("clips: 3\n")
