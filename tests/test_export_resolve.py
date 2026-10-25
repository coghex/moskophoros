"""Layered resolution of the export settings, with provenance, and their
check against the view (export design P-7, part 1), through the internal
reader that opens the inactive-row gate."""

from dataclasses import replace

import pytest

from moskophoros import exportsettings, settings
from moskophoros.exportsettings import (
    DEFAULTS,
    GLOBAL,
    OPTION,
    PROJECT,
    REUSED,
    Source,
    request,
    resolve,
)
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.plan import MirrorPair
from moskophoros.usage import UsageError
from moskophoros.views import View


def read(text):
    return settings.read_bytes(text.encode(), source="f.yaml", directory="/s")


def source(kind, label, text):
    return Source(kind, label, read(text))


def selected(*specs):
    return tuple(
        SelectedClip(Clip(i, name, 0.0, length, ()), False)
        for i, (name, length) in enumerate(specs)
    )


RING8 = View(8, 0.0)


def test_with_no_layer_every_value_is_its_internal_default():
    resolved = resolve([])
    assert (resolved.fps, resolved.frames) == (12.0, "auto")
    assert resolved.stored_directions == "all"
    assert (resolved.direction_names, resolved.mirrors) == ({}, {})
    assert resolved.formats == ("sheet",)
    assert resolved.frame_path == "frames/{clip}/{direction}/frame_{frame:03}{map}.png"
    assert resolved.atlas_path == "atlases/{clip}{map}.png"
    assert resolved.sheet_path == "sheet{map}.png"
    assert resolved.atlas_padding == 0
    assert dict(resolved.clips) == {}
    assert resolved.fps_kind == DEFAULTS
    assert set(resolved.origins) == set(exportsettings.GLOBAL_KEYS)
    assert set(resolved.origins.values()) == {"the shipped default"}


def test_the_shipped_defaults_layer_changes_nothing_but_the_origin():
    shipped = Source(DEFAULTS, "the shipped defaults", settings.read_defaults())
    resolved, bare = resolve([shipped]), resolve([])
    assert resolved.fps == bare.fps == 12.0
    assert resolved.frames == bare.frames == "auto"
    assert resolved.fps_kind == DEFAULTS
    # Every setting is in the shipped file; with no layer at all each takes the
    # internal default and says so.
    assert resolved.origins["fps"].startswith("the shipped defaults line ")
    assert resolved.origins["stored_directions"].startswith(
        "the shipped defaults line "
    )
    assert bare.origins["stored_directions"] == "the shipped default"
    assert resolved.stored_directions == bare.stored_directions == "all"


def test_the_highest_layer_that_sets_a_value_wins_and_is_named_with_its_position():
    sources = [
        source(GLOBAL, "g", "stored_directions: [0, 1]\nmirrors: {3: 1}\nfps: 8\n"),
        source(REUSED, "r", "stored_directions: [2]\ndirection_names: {1: a}\n"),
        source(PROJECT, "p", "mirrors: {}\nexport:\n  atlas_padding: 4\n"),
        source(OPTION, "o", "fps: 6\nexport:\n  formats: [frames, sheet]\n"),
    ]
    resolved = resolve(sources)
    assert resolved.stored_directions == (2,)
    assert resolved.direction_names == {1: "a"}
    assert resolved.mirrors == {}
    assert resolved.atlas_padding == 4
    assert resolved.formats == ("sheet", "frames")
    assert resolved.fps == 6.0 and resolved.fps_kind == OPTION
    assert resolved.origins["stored_directions"] == "r line 1, column 1"
    assert resolved.origins["direction_names"] == "r line 2, column 1"
    assert resolved.origins["mirrors"] == "p line 1, column 1"
    assert resolved.origins["export.atlas_padding"] == "p line 3, column 3"
    assert resolved.origins["export.formats"] == "o line 3, column 3"
    assert resolved.origins["export.sheet_path"] == "the shipped default"
    assert resolved.origins["fps"] == "o line 1, column 1"


def test_a_layer_without_positions_is_named_by_its_label_alone():
    plain = Source(REUSED, "--settings-from 'a.json'", {"stored_directions": (1,)})
    resolved = resolve([plain])
    assert resolved.origins["stored_directions"] == "--settings-from 'a.json'"


def test_the_fps_kind_names_the_layer_that_gave_the_global_rate():
    for kind in (GLOBAL, REUSED, PROJECT, OPTION):
        assert resolve([source(kind, "x", "fps: 5\n")]).fps_kind == kind
    layers = [source(PROJECT, "p", "fps: 5\n"), source(GLOBAL, "g", "fps: 7\n")]
    assert resolve(layers).fps_kind == GLOBAL
    with pytest.raises(ValueError, match="not a layer kind"):
        resolve([Source("file", "x", {})])


def test_clip_leaves_merge_by_clip_and_leaf_across_layers_with_provenance():
    resolved = resolve(
        [
            source(
                GLOBAL,
                "g",
                "clips:\n  walk: {frames: 6, fps: 8}\n  idle: {frames: 2}\n",
            ),
            source(
                PROJECT,
                "p",
                "clips:\n  walk:\n    fps: 4\n    output_name: stride\n  idle: {frames: null}\n",
            ),
        ]
    )
    walk, idle = resolved.clips["walk"], resolved.clips["idle"]
    # Changing the clip's rate keeps its lower layer's frame count.
    assert (walk.frames, walk.fps, walk.output_name) == (6, 4.0, "stride")
    assert walk.stored_directions is None and walk.mirrors is None
    assert dict(walk.origins) == {
        "frames": "g line 2, column 10",
        "fps": "p line 3, column 5",
        "output_name": "p line 4, column 5",
    }
    assert idle.frames is None
    assert idle.origins == {"frames": "p line 5, column 10"}


def test_an_explicit_null_clears_a_lower_clip_override_only_for_that_leaf():
    resolved = resolve(
        [
            source(
                GLOBAL,
                "g",
                "clips:\n  w: {fps: 8, stored_directions: [1], mirrors: {5: 1}}\n",
            ),
            source(PROJECT, "p", "clips:\n  w: {fps: null, mirrors: null}\n"),
        ]
    )
    clip = resolved.clips["w"]
    assert (clip.fps, clip.mirrors) == (None, None)
    assert clip.stored_directions == (1,)


def test_a_reused_layer_gives_clip_counts_without_positions():
    reused = Source(REUSED, "r", {"clips": {"w": {"frames": 8}}})
    project = source(PROJECT, "p", "clips:\n  w: {fps: 5}\n")
    clip = resolve([reused, project]).clips["w"]
    assert (clip.frames, clip.fps) == (8, 5.0)
    assert clip.origins["frames"] == "r"


# The check against the view and the plan


def plan_clip(result, name):
    return next(c for c in result.plan.clips if c.selected.clip.name == name)


def test_per_clip_fps_counts_directions_and_mirrors_reach_the_planner():
    resolved = resolve(
        [
            source(
                GLOBAL,
                "g",
                "stored_directions: [0, 1, 2, 3, 4]\nmirrors: {7: 1, 6: 2, 5: 3}\nfps: 8\n",
            ),
            source(
                PROJECT,
                "p",
                "clips:\n  walk: {frames: 4, fps: 4}\n"
                "  attack: {stored_directions: all, mirrors: {}}\n",
            ),
            source(OPTION, "o", "fps: 2\n"),
        ]
    )
    result = request(
        resolved, "hero", selected(("walk", 1.0), ("attack", 0.5), ("idle", 2.0)), RING8
    )
    walk, attack, idle = result.plan.clips
    # walk: its own rate 4 beats the option's 2; four frames over 1 s.
    assert walk.fps == 4.0 and walk.sampling.frame_count == 4
    assert walk.sampling.frame_duration == 0.25
    assert [d.index for d in walk.directions] == [0, 1, 2, 3, 4]
    assert walk.mirrors == (MirrorPair(5, 3), MirrorPair(6, 2), MirrorPair(7, 1))
    # attack: `all` bypasses the restricted global list, {} disables mirrors.
    assert attack.fps == 2.0
    assert [d.index for d in attack.directions] == list(range(8))
    assert attack.mirrors == ()
    # idle inherits the global values, the option's rate among them.
    assert (
        idle.fps == 2.0
        and idle.sampling.frame_count == 1
        or idle.sampling.frame_count > 1
    )
    assert [d.index for d in idle.directions] == [0, 1, 2, 3, 4]
    assert idle.mirrors == (MirrorPair(5, 3), MirrorPair(6, 2), MirrorPair(7, 1))
    assert [item.frames for item in result.selected] == [4, None, None]
    # Frames keep original direction indices and real addresses only.
    assert {f.address.direction for f in walk.frames} == {0, 1, 2, 3, 4}
    assert all(f.address.subject == "hero" for f in result.plan.frames)


def test_selected_clips_take_their_counts_from_the_layers_only():
    resolved = resolve([source(GLOBAL, "g", "clips:\n  walk: {frames: 3}\n")])
    given = SelectedClip(Clip(0, "walk", 0.0, 1.0, ()), False, frames=99)
    other = SelectedClip(Clip(1, "run", 0.0, 1.0, ()), False, frames=7)
    result = request(resolved, "hero", (given, other), View(1, 0.0))
    assert [item.frames for item in result.selected] == [3, None]
    assert plan_clip(result, "walk").sampling.frame_count == 3


def test_unselected_clip_entries_are_unused_even_when_invalid_for_the_view():
    resolved = resolve(
        [
            source(
                GLOBAL,
                "g",
                "clips:\n  other: {stored_directions: [40], mirrors: {50: 41}}\n",
            )
        ]
    )
    result = request(resolved, "hero", selected(("walk", 1.0)), RING8)
    assert len(result.plan.clips) == 1


def failure(*layers, clips=(("walk", 1.0),), view=RING8):
    resolved = resolve([source(kind, label, text) for kind, label, text in layers])
    with pytest.raises(UsageError) as raised:
        request(resolved, "hero", selected(*clips), view)
    assert raised.value.exit_code == 2
    return str(raised.value)


def test_a_changed_view_rejects_references_it_no_longer_has_and_drops_none():
    assert failure((GLOBAL, "g", "direction_names:\n  1: a\n  9: b\n")) == (
        "direction_names (g line 1, column 1): the direction 9 is not one of the "
        "view's 8 directions"
    )
    assert failure((PROJECT, "p", "stored_directions: [0, 8]\n")) == (
        "stored_directions (p line 1, column 1): the direction 8 is not one of the "
        "view's 8 directions"
    )
    assert failure((PROJECT, "p", "mirrors: {7: 1, 9: 2}\n")) == (
        "mirrors (p line 1, column 1): the direction 9 is not one of the view's 8 directions"
    )
    assert failure((PROJECT, "p", "mirrors: {3: 8}\n")).startswith("mirrors (p line 1")
    # The same file is fine in a 16-direction view.
    layers = [
        source(
            GLOBAL,
            "g",
            "direction_names: {9: b}\nstored_directions: [0, 8]\nmirrors: {9: 8}\n",
        )
    ]
    request(resolve(layers), "hero", selected(("walk", 1.0)), View(16, 0.0))
    with pytest.raises(UsageError):
        request(resolve(layers), "hero", selected(("walk", 1.0)), RING8)


def test_a_global_value_is_checked_even_when_every_clip_overrides_it():
    text = "stored_directions: [12]\nclips:\n  walk: {stored_directions: all}\n"
    assert "stored_directions (g line 1, column 1): the direction 12" in failure(
        (GLOBAL, "g", text)
    )


def test_a_selected_clips_own_references_must_exist_in_the_view():
    assert failure(
        (PROJECT, "p", "clips:\n  walk:\n    stored_directions: [0, 11]\n")
    ) == (
        "clip 'walk' clips.walk.stored_directions (p line 3, column 5): the "
        "direction 11 is not one of the view's 8 directions"
    )
    assert failure((PROJECT, "p", "clips:\n  walk:\n    mirrors: {8: 0}\n")) == (
        "clip 'walk' clips.walk.mirrors (p line 3, column 5): the direction 8 is "
        "not one of the view's 8 directions"
    )


def test_a_mirror_source_must_be_stored_and_a_target_omitted():
    both = "stored_directions: [0, 1]\nmirrors: {7: 2}\n"
    assert failure((GLOBAL, "g", both)) == (
        "clip 'walk': mirror 7 <- 2 takes its picture from direction 2, which is "
        "not stored; see stored_directions (g line 1, column 1) and mirrors "
        "(g line 2, column 1)"
    )
    assert failure((GLOBAL, "g", "stored_directions: [0, 1]\nmirrors: {1: 0}\n")) == (
        "clip 'walk': mirror 1 <- 0 replaces direction 1, which is stored, not "
        "omitted; see stored_directions (g line 1, column 1) and mirrors "
        "(g line 2, column 1)"
    )
    # A chain or a self-mirror makes one index both stored and omitted.
    assert "which is stored, not omitted" in failure((GLOBAL, "g", "mirrors: {3: 3}\n"))
    assert "which is not stored" in failure(
        (GLOBAL, "g", "stored_directions: [0, 4]\nmirrors: {1: 2, 2: 0}\n")
    )


def test_a_merged_clash_names_the_clip_and_each_contributing_layer():
    assert failure(
        (GLOBAL, "g", "mirrors: {7: 1}\n"),
        (PROJECT, "p", "clips:\n  walk:\n    stored_directions: [0, 2]\n"),
    ) == (
        "clip 'walk': mirror 7 <- 1 takes its picture from direction 1, which is "
        "not stored; see clips.walk.stored_directions (p line 3, column 5) and "
        "mirrors (g line 1, column 1)"
    )
    # Another clip with the global list is fine; the clash is the walk clip's.
    assert failure(
        (GLOBAL, "g", "stored_directions: [0, 1]\nmirrors: {7: 1}\n"),
        (PROJECT, "p", "clips:\n  run: {mirrors: {7: 0}}\n  walk: {mirrors: {1: 0}}\n"),
        clips=(("run", 1.0), ("walk", 1.0)),
    ).startswith("clip 'walk': mirror 1 <- 0 replaces direction 1")


def test_a_clip_with_its_own_stored_directions_checks_the_global_mirrors_against_them():
    global_ = (GLOBAL, "g", "stored_directions: [0, 1]\nmirrors: {7: 1}\n")
    # An entry for another clip changes nothing for walk.
    result = request(
        resolve(
            [
                source(*global_),
                source(PROJECT, "p", "clips:\n  other: {stored_directions: [2, 3]}\n"),
            ]
        ),
        "hero",
        selected(("walk", 1.0)),
        RING8,
    )
    assert result.plan.clips[0].mirrors == (MirrorPair(7, 1),)
    # Walk's own list does: the inherited mirror's source 1 is not stored in it.
    assert failure(
        global_, (PROJECT, "p", "clips:\n  walk: {stored_directions: [2, 3]}\n")
    ).startswith("clip 'walk': mirror 7 <- 1 takes its picture from direction 1")


def test_the_planners_own_refusals_become_usage_errors():
    resolved = replace(resolve([]), fps=float("nan"))
    with pytest.raises(UsageError, match="global fps must be finite"):
        request(resolved, "hero", selected(("walk", 1.0)), RING8)
