"""Output names and the relative output-path plan (export design P-7, parts
2 and 3), without files, Blender or capture."""

from types import SimpleNamespace

import pytest

from moskophoros import outputs
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.outputs import (
    Directory,
    Positional,
    UsageError,
    plan_outputs,
    resolve_names,
)
from moskophoros.plan import plan
from moskophoros.views import View


def selected(*specs):
    """Looping clips `(name, frames)` over one second each."""
    return tuple(
        SelectedClip(Clip(i, name, 0.0, 1.0, ()), False, frames)
        for i, (name, frames) in enumerate(specs)
    )


RING4 = View(4, 0.0)  # south, east, north, west
RING8 = View(8, 0.0)


def settings(**changes):
    values = {
        "formats": ("sheet",),
        "frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
        "atlas_path": "atlases/{clip}{map}.png",
        "sheet_path": "sheet{map}.png",
    }
    return SimpleNamespace(**(values | changes))


def names_for(clips, view=RING4, **options):
    return resolve_names(clips, view, subject=options.pop("subject", "hero"), **options)


def request_for(clips, view=RING4, **options):
    return plan("hero", clips, view, 4, **options)


def paths(output_plan, kind=None, channel=None):
    return [
        o.path
        for o in output_plan.artifacts
        if (kind is None or o.kind == kind)
        and (channel is None or o.channel == channel)
    ]


# Names


def test_a_clip_name_is_its_alias_or_its_cleaned_source_name():
    clips = selected(
        ("Run Fast!", None), ("a/b", None), ("ok-1_2.x", None), ("é", None)
    )
    names = names_for(clips)
    assert dict(names.clips) == {
        "Run Fast!": "Run_Fast_",
        "a/b": "a_b",
        "ok-1_2.x": "ok-1_2.x",
        "é": "_",
    }
    aliased = names_for(clips[:1], clip_aliases={"Run Fast!": "strike", "other": "x"})
    assert dict(aliased.clips) == {"Run Fast!": "strike"}


def test_a_direction_name_is_an_alias_a_compass_label_or_a_numbered_fallback():
    clips = selected(("w", None))
    full = names_for(clips, RING8, direction_aliases={2: "side"})
    assert dict(full.directions) == {
        0: "south",
        1: "south-east",
        2: "side",
        3: "north-east",
        4: "north",
        5: "north-west",
        6: "west",
        7: "south-west",
    }
    # A start angle off the 45 degree grid gives no compass label.
    odd = names_for(clips, View(3, 10.0), direction_aliases={1: "right"})
    assert dict(odd.directions) == {
        0: "direction-000",
        1: "right",
        2: "direction-002",
    }
    # The fallback pads the original index to three digits.
    assert names_for(clips, View(64, 1.0)).directions[63] == "direction-063"


def test_subject_and_variant_are_cleaned_but_not_refused():
    names = names_for(selected(("w", None)), subject="my hero.v2")
    assert (names.subject, names.variant) == ("my_hero.v2", "default")
    # An input called aux.glb gives the subject aux; no directory plan whose
    # templates leave out {subject} fails for it.
    assert names_for(selected(("w", None)), subject="aux").subject == "aux"


@pytest.mark.parametrize(
    ("alias", "problem"),
    [
        ("", "output name is empty"),
        (".", "is not a usable name"),
        ("..", "is not a usable name"),
        ("name.", "ends with a dot"),
        ("a..", "ends with a dot"),
        ("a b", "uses a character outside"),
        ("a/b", "uses a character outside"),
        ("é", "uses a character outside"),
        ("CON", "is a Windows device name"),
        ("con", "is a Windows device name"),
        ("Nul.txt", "is a Windows device name"),
        ("aux.png", "is a Windows device name"),
        ("COM1", "is a Windows device name"),
        ("com9.x.y", "is a Windows device name"),
        ("LPT5", "is a Windows device name"),
        ("prn", "is a Windows device name"),
    ],
)
def test_directory_mode_refuses_unusable_aliases(alias, problem):
    clips = selected(("walk", None))
    with pytest.raises(UsageError, match=problem) as raised:
        names_for(clips, clip_aliases={"walk": alias})
    assert "clip 'walk'" in str(raised.value)
    with pytest.raises(UsageError, match=problem) as raised:
        names_for(clips, direction_aliases={3: alias})
    assert "direction 3" in str(raised.value)


@pytest.mark.parametrize(
    "alias", ["com0", "COM10", "console", "aux1", "a.con", "lpt", "x_"]
)
def test_names_close_to_devices_or_dots_are_fine(alias):
    assert (
        names_for(selected(("w", None)), clip_aliases={"w": alias}).clips["w"] == alias
    )


def test_a_cleaned_source_name_is_checked_like_an_alias_except_its_characters():
    for source, problem in [
        ("aux", "device"),
        ("nul.x", "device"),
        ("a.", "ends with a dot"),
        ("..", "not a usable"),
        ("", "empty"),
    ]:
        with pytest.raises(UsageError, match=problem):
            names_for(selected((source, None)))


def test_clip_names_that_differ_only_by_case_or_cleaning_collide():
    with pytest.raises(UsageError) as raised:
        names_for(selected(("Walk", None), ("walk", None)))
    assert str(raised.value) == (
        "clips 'Walk' and 'walk' both have the output name 'Walk' and 'walk', "
        "equal ignoring case; give one an alias"
    )
    with pytest.raises(UsageError) as raised:
        names_for(selected(("a b", None), ("a_b", None)))
    assert str(raised.value) == (
        "clips 'a b' and 'a_b' both have the output name 'a_b'; give one an alias"
    )
    with pytest.raises(
        UsageError, match="'one' and 'two' both have the output name 'x'"
    ):
        names_for(
            selected(("one", None), ("two", None)),
            clip_aliases={"one": "x", "two": "X"},
        )


def test_no_numeric_suffix_is_added_to_a_colliding_name():
    names = names_for(
        selected(("Walk", None), ("walk", None)), clip_aliases={"walk": "walk-2"}
    )
    assert dict(names.clips) == {"Walk": "Walk", "walk": "walk-2"}


def test_direction_names_collide_over_the_whole_ring_not_only_stored_ones():
    # Directions 5 and 6 are not stored by any clip but the manifest names all.
    with pytest.raises(UsageError) as raised:
        names_for(
            selected(("w", None)), RING8, direction_aliases={5: "Side", 6: "side"}
        )
    assert str(raised.value) == (
        "directions 5 (north-west) and 6 (west) both have the output name "
        "'Side' and 'side', equal ignoring case; give one an alias"
    )
    with pytest.raises(UsageError, match=r"directions 1 \(east\) and 3 \(west\) both"):
        names_for(selected(("w", None)), View(4, 0.0), direction_aliases={3: "east"})
    with pytest.raises(UsageError, match="direction 7's output name 'nul'"):
        names_for(selected(("w", None)), RING8, direction_aliases={7: "nul"})


def test_only_selected_clips_are_named():
    names = names_for(selected(("walk", None)), clip_aliases={"unused": "aux"})
    assert dict(names.clips) == {"walk": "walk"}


def test_positional_names_are_informational_and_nothing_is_refused():
    clips = selected(("aux", None), ("Walk", None), ("walk", None), ("a b", None))
    names = names_for(
        clips,
        clip_aliases={"a b": ".."},
        direction_aliases={0: "con", 1: "con"},
        directory=False,
    )
    assert dict(names.clips) == {
        "aux": "aux",
        "Walk": "Walk",
        "walk": "walk",
        "a b": "..",
    }
    assert names.directions[0] == names.directions[1] == "con"


# The directory plan: exact paths and order


WALK_ATTACK = selected(("walk", 2), ("attack", 1))


def default_request(**options):
    return request_for(WALK_ATTACK, stored_directions=[2, 0], **options)


def plan_for(request, names=None, destination=None, **options):
    destination = Directory() if destination is None else destination
    names = names or names_for(tuple(c.selected for c in request.clips))
    formats = options.pop("formats", ("sheet",))
    templates = {
        k: options.pop(k)
        for k in ("frame_path", "atlas_path", "sheet_path")
        if k in options
    }
    return plan_outputs(
        request,
        names,
        settings(formats=formats, **templates),
        destination=destination,
        **options,
    )


def test_the_default_sheet_plan_lists_the_sheet_maps_previews_and_the_manifest():
    out = plan_for(default_request(), normals=True, depth=True, previews=True, lit=True)
    assert [(o.kind, o.channel, o.path, o.clip) for o in out.artifacts] == [
        ("sheet", "color", "sheet.png", None),
        ("sheet", "normal", "sheet.normal.png", None),
        ("sheet", "depth", "sheet.depth.png", None),
        ("preview", "flat", "previews/walk.gif", "walk"),
        ("preview", "lit", "previews/walk.lit.gif", "walk"),
        ("preview", "flat", "previews/attack.gif", "attack"),
        ("preview", "lit", "previews/attack.lit.gif", "attack"),
    ]
    assert (out.manifest.kind, out.manifest.path) == ("manifest", "manifest.json")


def test_the_atlas_plan_has_one_atlas_per_clip_in_clip_order_each_channel():
    out = plan_for(
        default_request(),
        formats=("atlases",),
        normals=True,
        depth=True,
        previews=False,
    )
    assert paths(out) == [
        "atlases/walk.png",
        "atlases/walk.normal.png",
        "atlases/walk.depth.png",
        "atlases/attack.png",
        "atlases/attack.normal.png",
        "atlases/attack.depth.png",
    ]
    assert [(o.kind, o.clip, o.direction, o.index) for o in out.artifacts[:1]] == [
        ("atlas", "walk", None, None)
    ]


def test_the_frame_plan_lists_only_real_stored_frames_in_clip_direction_sample_order():
    out = plan_for(
        default_request(),
        formats=("frames",),
        normals=True,
        depth=False,
        previews=False,
    )
    # Stored directions are [2, 0]: north then south, in configured order.
    assert paths(out) == [
        "frames/walk/north/frame_000.png",
        "frames/walk/north/frame_000.normal.png",
        "frames/walk/north/frame_001.png",
        "frames/walk/north/frame_001.normal.png",
        "frames/walk/south/frame_000.png",
        "frames/walk/south/frame_000.normal.png",
        "frames/walk/south/frame_001.png",
        "frames/walk/south/frame_001.normal.png",
        "frames/attack/north/frame_000.png",
        "frames/attack/north/frame_000.normal.png",
        "frames/attack/south/frame_000.png",
        "frames/attack/south/frame_000.normal.png",
    ]
    first = out.artifacts[0]
    assert (first.kind, first.channel, first.clip, first.direction, first.index) == (
        "frame",
        "color",
        "walk",
        2,
        0,
    )


def test_no_frame_is_planned_for_a_mirrored_target_direction():
    request = request_for(WALK_ATTACK, stored_directions=[0, 1], mirrors={3: 1})
    out = plan_for(request, formats=("frames",), normals=False, previews=False)
    assert {o.direction for o in out.artifacts} == {0, 1}
    assert len(out.artifacts) == 2 * 2 + 2 * 1
    assert not [p for p in paths(out) if "west" in p]


def test_all_formats_together_keep_the_fixed_artifact_order():
    request = request_for(selected(("walk", 2)), stored_directions=[1])
    out = plan_for(
        request,
        formats=("sheet", "frames", "atlases"),
        normals=True,
        depth=True,
        previews=True,
        lit=True,
    )
    assert paths(out) == [
        "sheet.png",
        "sheet.normal.png",
        "sheet.depth.png",
        "atlases/walk.png",
        "atlases/walk.normal.png",
        "atlases/walk.depth.png",
        "frames/walk/east/frame_000.png",
        "frames/walk/east/frame_000.normal.png",
        "frames/walk/east/frame_000.depth.png",
        "frames/walk/east/frame_001.png",
        "frames/walk/east/frame_001.normal.png",
        "frames/walk/east/frame_001.depth.png",
        "previews/walk.gif",
        "previews/walk.lit.gif",
    ]
    assert out.manifest.path == "manifest.json"
    assert "manifest.json" not in paths(out)


def test_previews_alternate_flat_and_lit_clip_by_clip():
    out = plan_for(default_request(), previews=True, lit=True)
    assert paths(out, "preview") == [
        "previews/walk.gif",
        "previews/walk.lit.gif",
        "previews/attack.gif",
        "previews/attack.lit.gif",
    ]
    assert paths(plan_for(default_request(), previews=True, lit=False), "preview") == [
        "previews/walk.gif",
        "previews/attack.gif",
    ]
    assert (
        paths(plan_for(default_request(), previews=False, lit=False), "preview") == []
    )


@pytest.mark.parametrize(
    "formats",
    [
        ("sheet",),
        ("frames",),
        ("atlases",),
        ("sheet", "frames"),
        ("sheet", "atlases"),
        ("frames", "atlases"),
        ("sheet", "frames", "atlases"),
    ],
)
@pytest.mark.parametrize(
    "maps", [(False, False), (True, False), (False, True), (True, True)]
)
@pytest.mark.parametrize("previews", [False, True])
def test_every_format_map_and_preview_combination_plans_the_files_it_enables(
    formats, maps, previews
):
    normals, depth = maps
    request = request_for(selected(("walk", 3)), stored_directions=[3, 1])
    out = plan_for(
        request, formats=formats, normals=normals, depth=depth, previews=previews
    )
    channels = 1 + normals + depth
    count = {"sheet": channels, "atlases": channels, "frames": channels * 2 * 3}
    expected = sum(count[name] for name in formats) + (1 if previews else 0)
    assert len(out.artifacts) == expected
    assert len({p.lower() for p in paths(out)}) == expected
    # The same formats in another order are one request: settings normalise
    # them, and the plan follows the order of the artifact kinds.
    kinds = [o.kind for o in out.artifacts]
    assert kinds == sorted(kinds, key=["sheet", "atlas", "frame", "preview"].index)


def test_templates_use_the_subject_variant_and_wider_frame_numbers():
    request = request_for(selected(("walk", 1)), stored_directions=[0])
    names = names_for(selected(("walk", 1)), subject="my hero")
    out = plan_for(
        request,
        names,
        formats=("sheet", "atlases", "frames"),
        frame_path="{subject}/{variant}/{clip}-{direction}-{frame:012}{map}.png",
        atlas_path="{subject}_{clip}{map}.png",
        sheet_path="{subject}.{variant}{map}.png",
        previews=False,
        normals=True,
    )
    assert paths(out) == [
        "my_hero.default.png",
        "my_hero.default.normal.png",
        "my_hero_walk.png",
        "my_hero_walk.normal.png",
        "my_hero/default/walk-south-000000000000.png",
        "my_hero/default/walk-south-000000000000.normal.png",
    ]


def test_a_frame_index_wider_than_its_width_is_not_truncated():
    request = request_for(selected(("walk", 1200)), stored_directions=[0])
    out = plan_for(
        request,
        formats=("frames",),
        frame_path="f/{frame:03}.png",
        normals=False,
        previews=False,
    )
    names = paths(out)
    assert len(names) == 1200
    assert names[:2] == ["f/000.png", "f/001.png"]
    assert names[999:1001] == ["f/999.png", "f/1000.png"]
    assert names[-1] == "f/1199.png"


def test_the_plan_follows_aliases_for_clips_and_directions():
    clips = selected(("walk", 1))
    names = names_for(
        clips, clip_aliases={"walk": "stride"}, direction_aliases={0: "front"}
    )
    out = plan_for(
        request_for(clips, stored_directions=[0]),
        names,
        formats=("frames", "atlases"),
        normals=False,
        previews=False,
    )
    assert paths(out) == ["atlases/stride.png", "frames/stride/front/frame_000.png"]
    assert out.artifacts[1].clip == "walk" and out.artifacts[1].direction == 0


# Expanded-path validation and collisions


def failure(request, names=None, **options):
    with pytest.raises(UsageError) as raised:
        plan_for(request, names, **options)
    return str(raised.value)


ONE = request_for(selected(("walk", 2)), stored_directions=[0, 1])


def test_an_empty_colour_map_component_is_refused_after_expansion():
    message = failure(
        ONE,
        formats=("frames",),
        frame_path="out/{map}/{clip}_{frame}.png",
        normals=False,
    )
    assert message == (
        "export.frame_path 'out/{map}/{clip}_{frame}.png' gives 'out//walk_0.png' "
        "for clip 'walk', direction 0, sample 0, color: it has an empty component"
    )
    # With the normal map on, only colour's path is empty; it still fails.
    assert "it has an empty component" in failure(
        ONE, formats=("frames",), frame_path="out/{map}/f_{frame}.png", normals=True
    )


@pytest.mark.parametrize(
    ("template", "problem"),
    [
        ("../{clip}.png", "it has the component '..'"),
        ("a/./{clip}.png", "it has the component '.'"),
        ("a/../{clip}.png", "it has the component '..'"),
        ("/{clip}.png", "it is not a relative path"),
        ("a//{clip}.png", "it has an empty component"),
        ("{clip}.PNG", "it does not end in .png"),
        ("{clip}.Png", "it does not end in .png"),
        ("{clip}.gif", "it does not end in .png"),
        ("{clip}", "it does not end in .png"),
        ("{clip}.png/", "it does not end in .png"),
        ("a./{clip}.png", "ends with a dot or a space"),
        ("con/{clip}.png", "is a Windows device name"),
        ("a/NUL/{clip}.png", "is a Windows device name"),
        ("aux.png", "is a Windows device name"),
        ("COM3.x.png", "is a Windows device name"),
        ("lpt1/{clip}.png", "is a Windows device name"),
    ],
)
def test_an_expanded_path_must_be_a_safe_relative_png_path(template, problem):
    assert problem in failure(
        ONE, formats=("atlases",), atlas_path=template, normals=False, previews=False
    )


@pytest.mark.parametrize(
    ("path", "problem"),
    [
        ("a\\b.png", "backslash"),
        ("a/b\x07.png", "control character"),
        ("a/b\x7f.png", "control character"),
        ('a/"b".png', "Windows-reserved character"),
        ("a/b?.png", "Windows-reserved character"),
        ("a/b*.png", "Windows-reserved character"),
        ("a/b<.png", "Windows-reserved character"),
        ("a/b|.png", "Windows-reserved character"),
        ("C:/x.png", "not a relative path"),
        ("c:x.png", "not a relative path"),
        ("a:b.png", "not a relative path"),
        ("a/b:c.png", "Windows-reserved character"),
        ("a/ .png", None),
        ("a/b .png", None),
        ("a/b /c.png", "ends with a dot or a space"),
        ("a/b.png ", "does not end in .png"),
    ],
)
def test_path_problem_names_what_is_wrong(path, problem):
    found = outputs.path_problem(path)
    if problem is None:
        assert found is None
    else:
        assert found and problem in found


def test_a_hidden_component_is_allowed():
    out = plan_for(
        ONE,
        formats=("atlases",),
        atlas_path=".{clip}/.hidden/{clip}{map}.png",
        normals=False,
        previews=False,
    )
    assert paths(out) == [".walk/.hidden/walk.png"]
    assert outputs.path_problem(".a/.png") is None


def test_a_subject_that_is_a_device_name_fails_only_where_a_template_uses_it():
    names = names_for(selected(("walk", 2)), subject="aux")
    fine = plan_for(ONE, names, formats=("sheet",), normals=False, previews=False)
    assert paths(fine) == ["sheet.png"]
    message = failure(
        ONE,
        names,
        formats=("sheet",),
        sheet_path="{subject}.png",
        normals=False,
        previews=False,
    )
    assert "is a Windows device name" in message


def test_omitting_map_collides_when_a_map_is_enabled():
    message = failure(
        ONE, formats=("sheet",), sheet_path="sheet.png", normals=True, previews=False
    )
    assert message == (
        "export.sheet_path 'sheet.png' for the sheet, color and export.sheet_path "
        "'sheet.png' for the sheet, normal would both write 'sheet.png'"
    )
    # With no map enabled the same template is fine.
    assert paths(
        plan_for(
            ONE,
            formats=("sheet",),
            sheet_path="sheet.png",
            normals=False,
            previews=False,
        )
    ) == ["sheet.png"]


def test_omitting_an_address_token_collides_only_when_paths_repeat():
    request = request_for(selected(("walk", 2), ("run", 1)), stored_directions=[0, 1])
    message = failure(
        request,
        formats=("frames",),
        frame_path="{clip}/{direction}.png",
        normals=False,
        previews=False,
    )
    assert message == (
        "export.frame_path '{clip}/{direction}.png' for clip 'walk', direction 0, "
        "sample 0, color and export.frame_path '{clip}/{direction}.png' for clip "
        "'walk', direction 0, sample 1, color would both write 'walk/south.png'"
    )
    single = request_for(selected(("walk", 1)), stored_directions=[0, 1])
    assert paths(
        plan_for(
            single,
            formats=("frames",),
            frame_path="{clip}/{direction}.png",
            normals=False,
            previews=False,
        )
    ) == ["walk/south.png", "walk/east.png"]


def test_a_repeated_expansion_is_never_deduplicated():
    request = request_for(selected(("walk", 1), ("run", 1)), stored_directions=[0])
    assert failure(
        request,
        formats=("atlases",),
        atlas_path="same.png",
        normals=False,
        previews=False,
    ) == (
        "export.atlas_path 'same.png' for the atlas of clip 'walk', color and "
        "export.atlas_path 'same.png' for the atlas of clip 'run', color would "
        "both write 'same.png'"
    )


def test_formats_collide_across_templates():
    request = request_for(selected(("walk", 1)), stored_directions=[0])
    message = failure(
        request,
        formats=("sheet", "atlases"),
        sheet_path="out.png",
        atlas_path="out.png",
        normals=False,
        previews=False,
    )
    assert message == (
        "export.sheet_path 'out.png' for the sheet, color and export.atlas_path "
        "'out.png' for the atlas of clip 'walk', color would both write 'out.png'"
    )


def test_paths_compare_ignoring_ascii_case_including_the_fixed_ones():
    request = request_for(selected(("walk", 1)), stored_directions=[0])
    # Only .png files come from a template, so a preview collision needs a
    # clip name that makes the fixed path equal an image path: none can, which
    # is why previews meet templates only as directory prefixes (below). Two
    # image paths that differ only in case do collide.
    message = failure(
        request_for(selected(("a", 1), ("b", 1)), stored_directions=[0]),
        SimpleNamespace(
            clips={"a": "Q", "b": "q"},
            directions={0: "south"},
            subject="s",
            variant="v",
        ),
        formats=("atlases",),
        atlas_path="{clip}.png",
        normals=False,
        previews=False,
    )
    assert message == (
        "export.atlas_path '{clip}.png' for the atlas of clip 'a', color and "
        "export.atlas_path '{clip}.png' for the atlas of clip 'b', color would "
        "both write 'q.png' ('Q.png', equal ignoring case)"
    )
    assert paths(
        plan_for(
            request,
            formats=("sheet", "atlases"),
            sheet_path="Same.png",
            atlas_path="same-{clip}.png",
            normals=False,
            previews=False,
        )
    ) == ["Same.png", "same-walk.png"]


def test_a_case_difference_alone_is_a_collision():
    request = request_for(selected(("a", 1)), stored_directions=[0])
    message = failure(
        request,
        formats=("sheet", "atlases"),
        sheet_path="X/Y.png",
        atlas_path="x/y.PNG".replace("PNG", "png"),
        normals=False,
        previews=False,
    )
    assert message == (
        "export.sheet_path 'X/Y.png' for the sheet, color and export.atlas_path "
        "'x/y.png' for the atlas of clip 'a', color would both write 'x/y.png' "
        "('X/Y.png', equal ignoring case)"
    )


def test_a_template_may_not_write_where_a_preview_or_the_manifest_goes():
    request = request_for(selected(("walk", 1)), stored_directions=[0])
    # A file that is also a directory prefix of another output.
    assert failure(
        request,
        formats=("atlases",),
        atlas_path="manifest.json/{clip}.png",
        normals=False,
        previews=False,
    ) == (
        "the manifest for manifest.json writes the file 'manifest.json', which "
        "export.atlas_path 'manifest.json/{clip}.png' for the atlas of clip "
        "'walk', color needs as a directory in 'manifest.json/walk.png'"
    )
    assert "previews/walk.gif" in failure(
        request,
        formats=("atlases",),
        atlas_path="previews/walk.gif/{clip}.png",
        normals=False,
        previews=True,
    )
    # Case-folded: PREVIEWS/Walk.GIF/x.png under previews/walk.gif.
    assert "needs as a directory" in failure(
        request,
        formats=("atlases",),
        atlas_path="PREVIEWS/Walk.GIF/{clip}.png",
        normals=False,
        previews=True,
    )
    assert "needs as a directory" in failure(
        request,
        formats=("atlases",),
        atlas_path="Manifest.JSON/x.png",
        normals=False,
        previews=False,
    )


def test_image_paths_conflict_as_files_and_directories_between_templates():
    request = request_for(selected(("walk", 1)), stored_directions=[0])
    message = failure(
        request,
        formats=("sheet", "atlases"),
        sheet_path="out.png",
        atlas_path="out.png/{clip}.png",
        normals=False,
        previews=False,
    )
    assert message == (
        "export.sheet_path 'out.png' for the sheet, color writes the file "
        "'out.png', which export.atlas_path 'out.png/{clip}.png' for the atlas "
        "of clip 'walk', color needs as a directory in 'out.png/walk.png'"
    )
    # Siblings in one directory are not a conflict, nor a shared prefix name.
    assert paths(
        plan_for(
            request,
            formats=("sheet", "atlases"),
            sheet_path="out.png",
            atlas_path="out.png.d/{clip}.png",
            normals=False,
            previews=False,
        )
    ) == ["out.png", "out.png.d/walk.png"]


def test_a_preview_cannot_share_a_name_with_another_preview_after_naming():
    request = request_for(selected(("Walk", 1), ("walk", 1)), stored_directions=[0])
    # Names are refused first, before any path is planned.
    with pytest.raises(UsageError, match="both have the output name"):
        plan_for(request, names_for(selected(("Walk", 1), ("walk", 1))))


def test_syntax_is_checked_for_every_template_whatever_the_formats():
    request = request_for(selected(("walk", 1)), stored_directions=[0])
    for key, value in [
        ("frame_path", "{bogus}.png"),
        ("atlas_path", "{direction}.png"),
        ("sheet_path", "{clip}.png"),
        ("sheet_path", "a{{b.png"),
    ]:
        message = failure(
            request,
            formats=("frames",) if key != "frame_path" else ("sheet",),
            **{key: value},
        )
        assert message.startswith(f"export.{key} {value!r}: the template ")


def test_the_plan_is_pure_and_its_failure_is_a_usage_error_before_any_effect():
    assert outputs.UsageError.exit_code == 2
    request = request_for(selected(("walk", 1)), stored_directions=[0])
    with pytest.raises(UsageError) as raised:
        plan_for(request, formats=("sheet",), sheet_path="a/../x.png")
    assert raised.value.exit_code == 2


# The positional form


def positional(clips, **options):
    request = request_for(clips, **options.pop("request", {}))
    names = names_for(clips, directory=False)
    return plan_for(request, names, Positional("hero.png"), **options)


def test_the_positional_plan_keeps_the_legacy_names():
    out = positional(
        selected(("walk", 1), ("attack", 1)),
        normals=True,
        depth=True,
        previews=True,
        lit=True,
    )
    assert [(o.kind, o.channel, o.path, o.clip) for o in out.artifacts] == [
        ("sheet", "color", "hero.png", None),
        ("sheet", "normal", "hero.normal.png", None),
        ("sheet", "depth", "hero.depth.png", None),
        ("preview", "flat", "hero.walk.gif", "walk"),
        ("preview", "lit", "hero-lit.walk.gif", "walk"),
        ("preview", "flat", "hero.attack.gif", "attack"),
        ("preview", "lit", "hero-lit.attack.gif", "attack"),
    ]
    assert (out.manifest.kind, out.manifest.path) == ("manifest", "hero.json")


def test_the_positional_plan_omits_what_is_off():
    out = positional(
        selected(("walk", 1)), normals=False, depth=False, previews=False, lit=False
    )
    assert paths(out) == ["hero.png"]
    assert out.manifest.path == "hero.json"


def test_the_positional_plan_keeps_aux_and_case_colliding_clips_with_original_identity():
    clips = selected(("aux", 1), ("Walk", 1), ("walk", 1), ("Walk 2", 1))
    out = positional(clips, normals=False, previews=True)
    assert paths(out, "preview") == [
        "hero.aux.gif",
        "hero.Walk.gif",
        "hero.walk-2.gif",
        "hero.Walk_2.gif",
    ]
    assert [o.clip for o in out.artifacts if o.kind == "preview"] == [
        "aux",
        "Walk",
        "walk",
        "Walk 2",
    ]


def test_the_positional_plan_ignores_directory_templates_even_unusable_ones():
    clips = selected(("walk", 1))
    request = request_for(clips)
    out = plan_outputs(
        request,
        names_for(clips, directory=False),
        settings(
            sheet_path="{subject}.png",
            atlas_path="a/{clip}{map}.png",
            frame_path="x/{frame}.png",
        ),
        destination=Positional("pic.png"),
        normals=True,
        previews=False,
    )
    assert paths(out) == ["pic.png", "pic.normal.png"]


@pytest.mark.parametrize(
    "formats", [("frames",), ("atlases",), ("sheet", "frames"), ("sheet", "atlases")]
)
def test_the_positional_form_needs_the_sheet_format_alone(formats):
    clips = selected(("walk", 1))
    with pytest.raises(UsageError) as raised:
        plan_for(
            request_for(clips),
            names_for(clips, directory=False),
            Positional("hero.png"),
            formats=formats,
        )
    assert "give --output-dir" in str(raised.value)


def test_template_syntax_is_checked_in_the_positional_form_too():
    clips = selected(("walk", 1))
    with pytest.raises(UsageError, match="export.atlas_path 'a/{frame}.png'"):
        plan_for(
            request_for(clips),
            names_for(clips, directory=False),
            Positional("hero.png"),
            atlas_path="a/{frame}.png",
        )


def test_the_destination_is_an_explicit_input():
    clips = selected(("walk", 1))
    with pytest.raises(ValueError, match="not a destination"):
        plan_for(request_for(clips), names_for(clips), destination="somewhere")


# Purity: a failure comes before any effect


def test_planning_touches_no_file_process_or_capture_code(monkeypatch):
    import builtins
    import os
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("the plan reached outside memory")

    for owner, name in [
        (builtins, "open"),
        (os, "stat"),
        (os, "scandir"),
        (os, "listdir"),
        (os, "mkdir"),
        (os, "replace"),
        (subprocess, "Popen"),
    ]:
        monkeypatch.setattr(owner, name, forbidden)
    request = request_for(selected(("walk", 2)), stored_directions=[0, 1])
    names = names_for(selected(("walk", 2)))
    good = plan_outputs(
        request,
        names,
        settings(formats=("sheet", "frames", "atlases")),
        destination=Directory(),
    )
    assert len(good.artifacts) > 3
    with pytest.raises(UsageError) as raised:
        plan_outputs(
            request,
            names,
            settings(sheet_path="../x.png"),
            destination=Directory(),
        )
    assert raised.value.exit_code == 2
    legacy = plan_outputs(
        request, names, settings(), destination=Positional("/any/dir/hero.png")
    )
    assert legacy.manifest.path == "hero.json"


def test_the_preparation_modules_import_no_file_or_process_machinery():
    from moskophoros import diagnostics, exportsettings, templates

    for module in (outputs, exportsettings, diagnostics, templates):
        for name in ("os", "subprocess", "shutil", "tempfile", "bpy", "backend"):
            assert name not in vars(module), (module.__name__, name)
