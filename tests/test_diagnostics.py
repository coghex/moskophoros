"""The warnings the export preparation builds: shadowed per-clip rates and
mirrors whose camera conditions fail (export design P-7 and P-8; D-17)."""

import pytest

from moskophoros import diagnostics, exportsettings, settings, views
from moskophoros.diagnostics import MirrorWarning, fps_warnings, mirror_warnings
from moskophoros.exportsettings import GLOBAL, OPTION, PROJECT, REUSED, Source, resolve
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.plan import MirrorPair, plan
from moskophoros.views import View

# The fps warning


def read(text):
    return settings._read_document(
        text.encode(), source="f.yaml", directory="/s", open_gate=True
    )


def sel(name, t1=1.0, animated=True):
    index = 0 if animated else None
    return SelectedClip(Clip(index, name, 0.0, t1, ()), False)


WALK, RUN, POSE, UNUSED = sel("walk"), sel("run"), sel("pose", 0.0), sel("unused")
CLIPS = "clips:\n  walk: {fps: 8}\n  pose: {fps: 6}\n  gone: {fps: 3}\n"


def resolved(kind, global_fps="fps: 6\n", clips=CLIPS, below=()):
    layers = [Source(k, f"{k}-file", read(text)) for k, text in below]
    layers.append(Source(kind, f"{kind}-file", read(global_fps)))
    layers.append(Source(GLOBAL if kind != GLOBAL else PROJECT, "clips", read(clips)))
    return resolve(sorted(layers, key=lambda s: exportsettings.KINDS.index(s.kind)))


def test_an_explicit_option_rate_is_shadowed_by_one_warning_listing_the_clips():
    result = fps_warnings(resolved(OPTION), (WALK, RUN, POSE))
    assert result == (
        'the global fps 6.0 does not reach the clips with their own: "walk" (8.0), '
        '"pose" (6.0)',
    )


def test_a_project_rate_warns_the_same_way():
    result = fps_warnings(resolved(PROJECT), (WALK, POSE))
    assert len(result) == 1 and result[0].startswith("the global fps 6.0 does not")


def test_an_equal_clip_rate_and_a_still_clip_are_included():
    only_equal = resolved(OPTION, "fps: 8\n", "clips:\n  pose: {fps: 8}\n")
    assert fps_warnings(only_equal, (WALK, POSE)) == (
        'the global fps 8.0 does not reach the clips with their own: "pose" (8.0)',
    )
    # Zero duration and the static clip both have a frame duration from fps.
    static = SelectedClip(Clip(None, "static", 0.0, 0.0, ()), False)
    both = resolved(
        OPTION, "fps: 8\n", "clips:\n  static: {fps: 2}\n  pose: {fps: 8}\n"
    )
    assert fps_warnings(both, (static, POSE))[0].endswith(
        '"static" (2.0), "pose" (8.0)'
    )


@pytest.mark.parametrize("kind", [GLOBAL, REUSED])
def test_a_global_file_or_reused_rate_does_not_warn(kind):
    assert fps_warnings(resolved(kind), (WALK, POSE)) == ()


def test_the_default_rate_does_not_warn():
    assert fps_warnings(resolve([Source(GLOBAL, "c", read(CLIPS))]), (WALK, POSE)) == ()


def test_the_highest_layer_that_gives_the_rate_decides_its_kind():
    own = "clips:\n  walk: {fps: 1}\n"

    def warns(*layers):
        return bool(
            fps_warnings(resolve([Source(k, k, read(t)) for k, t in layers]), (WALK,))
        )

    # A global file's rate stays global when the project only sets clips.
    assert not warns((GLOBAL, "fps: 5\n"), (PROJECT, own))
    # A project's rate over a global file's or a reused sheet's is the project's.
    assert warns((GLOBAL, "fps: 9\n"), (PROJECT, "fps: 5\n" + own))
    assert warns((REUSED, "fps: 9\n"), (PROJECT, "fps: 5\n" + own))
    # The reused sheet's rate over a global file's is not explicit.
    assert not warns((GLOBAL, "fps: 9\n"), (REUSED, "fps: 5\n" + own))
    # An option over a project's rate is explicit; a project's over an option
    # layer given lower is the project's, which is explicit as well.
    assert warns((PROJECT, "fps: 9\n" + own), (OPTION, "fps: 5\n"))
    assert warns((OPTION, "fps: 9\n"), (PROJECT, "fps: 5\n" + own))
    # No rate in any layer: the default's, which does not warn.
    assert not warns((PROJECT, own))


def test_unused_and_unselected_clip_entries_do_not_warn():
    only_unused = resolved(
        OPTION, clips="clips:\n  gone: {fps: 3}\n  walk: {frames: 3}\n"
    )
    assert fps_warnings(only_unused, (WALK, RUN)) == ()
    assert fps_warnings(resolved(OPTION), (RUN, UNUSED)) == ()
    assert fps_warnings(resolved(OPTION), ()) == ()


def test_a_null_clip_rate_is_no_override():
    nulled = resolved(OPTION, clips="clips:\n  walk: {fps: null}\n")
    assert fps_warnings(nulled, (WALK,)) == ()


# The mirror warnings


def directions(count, start=0.0, yaw=0.0):
    return View(count, start, yaw)


def mirrored(view, stored, mirrors, clips=("walk",)):
    selected = tuple(
        SelectedClip(Clip(i, n, 0.0, 1.0, ()), False) for i, n in enumerate(clips)
    )
    return plan("hero", selected, view, 4, stored_directions=stored, mirrors=mirrors)


def warnings(view, stored, mirrors, **camera):
    camera = {"direction": views.pitch_direction(45)} | camera
    return mirror_warnings(mirrored(view, stored, mirrors), view, **camera)


@pytest.mark.parametrize("yaw", [0.0, 90.0, 30.0, -45.0, 725.0])
def test_a_correct_pair_never_warns_whatever_the_facing_correction(yaw):
    # 315 + 45 = 360: eight directions, start 0, direction 7 from direction 1.
    assert warnings(directions(8, 0.0, yaw), [0, 1, 2, 3, 4], {7: 1, 6: 2, 5: 3}) == ()


@pytest.mark.parametrize("yaw", [0.0, 90.0, 30.0])
def test_a_wrong_pair_warns_whatever_the_facing_correction(yaw):
    found = warnings(directions(8, 0.0, yaw), [0, 1, 2], {7: 2})
    assert found == (
        MirrorWarning(
            "walk",
            7,
            2,
            ("the direction angles 315.0 and 90.0 do not sum to 0 modulo 360",),
        ),
    )
    assert found[0].message == (
        'clip "walk" mirror 7 <- 2 is not a reflection: the direction angles '
        "315.0 and 90.0 do not sum to 0 modulo 360"
    )


def test_the_start_angle_shifts_which_pairs_are_reflections():
    # theta_i = 22.5 + 45 i, so the sum is 45 + 45 (t + s): zero for t + s = 7.
    assert warnings(directions(8, 22.5), [0, 1], {7: 0, 6: 1}) == ()
    found = warnings(directions(8, 22.5), [0, 1, 2], {6: 2})
    assert [(w.target, w.source) for w in found] == [(6, 2)]


@pytest.mark.parametrize(
    ("count", "stored", "mirrors"),
    [
        (11, [1, 2, 3], {10: 1, 9: 2, 8: 3}),
        (50, [1, 20, 5], {49: 1, 30: 20, 45: 5}),
        (7, [1, 2, 3], {6: 1, 5: 2, 4: 3}),
        (64, [1, 31, 7], {63: 1, 33: 31, 57: 7}),
    ],
)
def test_directions_with_fractional_angles_do_not_warn_for_a_true_pair(
    count, stored, mirrors
):
    # target + source = count, so the angles sum to 360 degrees.
    assert warnings(directions(count), stored, mirrors) == ()


@pytest.mark.parametrize(
    ("count", "pair"), [(13, (0, 12)), (14, (0, 13)), (14, (1, 12))]
)
def test_a_sum_that_rounds_just_off_360_does_not_warn(count, pair):
    # With the start half a step back, target + source = count - 1 is a true
    # pair whose float angles sum to 359.99999999999994 or to 5.7e-14.
    start = 360 / (2 * count)
    ring = views.directions(directions(count, start))
    total = (ring[pair[0]].angle + ring[pair[1]].angle) % 360
    assert total != 0.0
    assert min(total, 360 - total) < 1e-12
    assert warnings(directions(count, start), [pair[1]], {pair[0]: pair[1]}) == ()
    # A start off by a degree is a wrong pair and warns.
    off = directions(count, start + 1.0)
    assert len(warnings(off, [pair[1]], {pair[0]: pair[1]})) == 1


def test_directions_with_inexact_angles_still_warn_for_a_wrong_pair():
    assert [w.target for w in warnings(directions(11), [1], {9: 1})] == [9]
    assert [w.target for w in warnings(directions(50), [1], {48: 1})] == [48]


@pytest.mark.parametrize("roll", [0, 0.0, -0.0, 1, 1.0, -1, -1.0])
def test_the_roll_of_zero_or_a_half_turn_either_way_is_allowed(roll):
    assert warnings(directions(8), [1], {7: 1}, roll=roll) == ()


@pytest.mark.parametrize("roll", [0.5, -0.5, 0.25, 0.999, 1e-9])
def test_any_other_roll_warns_once(roll):
    found = warnings(directions(8), [1], {7: 1}, roll=roll)
    assert [w.failed for w in found] == [
        (f"the camera roll {roll} is not 0, 1 or -1 half turns",)
    ]


DIRECTION = views.normalise((1, -1, 3))


def test_a_perspective_camera_on_its_heading_plane_does_not_warn():
    found = warnings(
        directions(8),
        [1],
        {7: 1},
        projection="perspective",
        direction=DIRECTION,
        position=(-1.0, 1.0, -3.0),
    )
    assert found == ()
    # Still on the plane, far away or very close.
    for scale in (1e-6, 3.0, 1e6):
        position = tuple(c * scale for c in (-1.0, 1.0, -3.0))
        assert (
            warnings(
                directions(8),
                [1],
                {7: 1},
                projection="perspective",
                direction=DIRECTION,
                position=position,
            )
            == ()
        )
    # The heading's own line, straight along the way the camera looks.
    along = tuple(-c for c in DIRECTION)
    assert (
        warnings(
            directions(8),
            [1],
            {7: 1},
            projection="perspective",
            direction=DIRECTION,
            position=along,
        )
        == ()
    )


def test_a_perspective_camera_beside_its_heading_plane_warns():
    found = warnings(
        directions(8),
        [1],
        {7: 1},
        projection="perspective",
        direction=DIRECTION,
        position=(1.0, 1.0, -3.0),
    )
    assert len(found) == 1
    assert found[0].failed[0].startswith("the perspective camera is ")
    assert found[0].failed[0].endswith(" m to the side of its heading plane")


def test_the_orthographic_cameras_position_is_unused():
    assert (
        warnings(
            directions(8),
            [1],
            {7: 1},
            projection="orthographic",
            direction=DIRECTION,
            position=(1.0, 1.0, -3.0),
        )
        == ()
    )


def test_a_perspective_camera_looking_straight_down_has_x_for_its_sideways_axis():
    down = (0.0, -1.0, 0.0)
    ok = warnings(
        directions(8),
        [1],
        {7: 1},
        projection="perspective",
        direction=down,
        position=(0.0, 5.0, 2.0),
    )
    assert ok == ()
    assert (
        len(
            warnings(
                directions(8),
                [1],
                {7: 1},
                projection="perspective",
                direction=down,
                position=(0.5, 5.0, 0.0),
            )
        )
        == 1
    )


def test_a_pair_failing_every_condition_gives_exactly_one_warning():
    found = warnings(
        directions(8),
        [2],
        {7: 2},
        roll=0.5,
        projection="perspective",
        direction=DIRECTION,
        position=(1.0, 0.0, 0.0),
    )
    assert len(found) == 1
    assert len(found[0].failed) == 3
    assert found[0].failed[0].startswith("the direction angles 315.0 and 90.0")
    assert found[0].failed[1] == "the camera roll 0.5 is not 0, 1 or -1 half turns"
    assert found[0].failed[2].startswith("the perspective camera is ")


def test_each_clip_and_pair_warns_once_in_plan_order_and_the_plan_keeps_its_pairs():
    view = directions(8)
    request = mirrored(view, [1, 2], {7: 1, 6: 1}, clips=("walk", "run"))
    found = mirror_warnings(request, view, direction=views.pitch_direction(45))
    assert [(w.clip, w.target, w.source) for w in found] == [
        ("walk", 6, 1),
        ("run", 6, 1),
    ]
    assert all(
        clip.mirrors == (MirrorPair(6, 1), MirrorPair(7, 1)) for clip in request.clips
    )


def test_no_mirrors_means_no_warnings_and_nothing_else_is_produced():
    view = directions(8)
    request = mirrored(view, "all", {})
    assert (
        mirror_warnings(request, view, roll=0.5, direction=views.pitch_direction(30))
        == ()
    )
    assert diagnostics.ANGLE_TOLERANCE_DEG == 1e-9
