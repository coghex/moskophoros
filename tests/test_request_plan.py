import pytest

from moskophoros.gltf import Clip, SelectedClip
from moskophoros.plan import ALL, ClipOverride, MirrorPair, plan
from moskophoros.sampling import Frame, FrameAddress, Sampling, frames
from moskophoros.views import View


def animation(name, t0, t1, index=0):
    return Clip(index, name, t0, t1, ())


def looping(clip, count=None):
    return SelectedClip(clip, one_shot=False, frames=count)


def one_shot(clip, count=None):
    return SelectedClip(clip, one_shot=True, frames=count)


STATIC = Clip(None, "static", 0.0, 0.0, ())
RING8 = View(8, 0.0)


def addresses(result, clip=None):
    return [
        (f.address.clip, f.address.direction, f.address.time_s)
        for f in result.frames
        if clip is None or f.address.clip == clip
    ]


# Per-clip timing (requirements 1-3)


def test_two_clips_keep_their_own_rate_and_count():
    walk = looping(animation("walk", 0.0, 1.0, index=0), count=6)
    run = looping(animation("run", 0.0, 2.0, index=1), count=4)
    result = plan(
        "hero",
        [walk, run],
        View(1, 0.0),
        12,
        overrides={"walk": ClipOverride(fps=8), "run": ClipOverride(fps=6)},
    )
    first, second = result.clips
    assert first.fps == 8
    assert first.sampling == Sampling(6, tuple(k / 6 for k in range(6)), 1 / 8, 8 / 6)
    assert second.fps == 6
    assert second.sampling == Sampling(4, tuple(k / 2 for k in range(4)), 1 / 6, 3.0)
    assert addresses(result) == [("walk", 0, k / 6) for k in range(6)] + [
        ("run", 0, k / 2) for k in range(4)
    ]


def test_a_null_fps_and_a_null_count_inherit_independently():
    clip = looping(animation("walk", 0.0, 1.0))
    # Global 4 frames at 12 fps; the clip changes only its fps, then only
    # (through its own count) its count.
    own_fps = plan(
        "a", [clip], View(1, 0.0), 12, 4, overrides={"walk": ClipOverride(fps=8)}
    )
    assert own_fps.clips[0].sampling == Sampling(4, (0.0, 0.25, 0.5, 0.75), 1 / 8, 2.0)
    own_count = plan(
        "a", [looping(animation("walk", 0.0, 1.0), count=2)], View(1, 0.0), 12, 4
    )
    assert own_count.clips[0].sampling == Sampling(2, (0.0, 0.5), 1 / 12, 6.0)
    inherits = plan(
        "a", [clip], View(1, 0.0), 12, 4, overrides={"walk": ClipOverride()}
    )
    assert inherits.clips[0].fps == 12
    assert inherits.clips[0].sampling == Sampling(
        4, (0.0, 0.25, 0.5, 0.75), 1 / 12, 3.0
    )


def test_a_clip_s_auto_count_beats_a_global_integer():
    clip = looping(animation("walk", 0.0, 1.0), count="auto")
    result = plan("a", [clip], View(1, 0.0), 4, 9)
    assert result.clips[0].sampling == Sampling(4, (0.0, 0.25, 0.5, 0.75), 0.25)


@pytest.mark.parametrize(
    ("t0", "t1", "fps", "n"),
    [
        (2.0, 2.125, 12, 2),  # d·fps = 1.5 rounds up
        (2.0, 2.375, 12, 5),  # 4.5
        (2.0, 2.0625, 8, 1),  # 0.5
        (2.0, 2.25, 10, 3),  # 2.5
        (2.0, 2.2, 12, 2),  # 2.4 rounds down
    ],
)
def test_automatic_counts_round_half_up_at_the_effective_rate(t0, t1, fps, n):
    d = t1 - t0
    clip = animation("a", t0, t1)
    loop = plan(
        "s", [looping(clip)], View(1, 0.0), 1, overrides={"a": ClipOverride(fps=fps)}
    )
    once = plan(
        "s", [one_shot(clip)], View(1, 0.0), 1, overrides={"a": ClipOverride(fps=fps)}
    )
    expected = tuple(t0 + k * d / n for k in range(n))
    assert loop.clips[0].sampling == Sampling(n, expected, d / n)
    assert once.clips[0].sampling == Sampling(n + 1, (*expected, t1), d / n)


def test_a_one_shot_ends_at_t1_exactly_and_a_loop_omits_it():
    t0, t1 = 0.1, 0.9333333134651179
    result = plan("s", [one_shot(animation("punch", t0, t1))], View(1, 0.0), 12)
    assert result.clips[0].sampling.times[-1] == t1
    assert result.frames[-1].address.time_s == t1
    loop = plan("s", [looping(animation("punch", t0, t1))], View(1, 0.0), 12)
    assert t1 not in loop.clips[0].sampling.times


@pytest.mark.parametrize("once", [False, True])
def test_explicit_counts_retime_to_the_effective_rate(once):
    clip = animation("jump", 0.25, 1.75)
    selected = SelectedClip(clip, one_shot=once, frames=6)
    result = plan(
        "s", [selected], View(1, 0.0), 12, overrides={"jump": ClipOverride(fps=10)}
    )
    steps = 5 if once else 6
    times = tuple(0.25 + k * 1.5 / steps for k in range(steps))
    if once:
        times += (1.75,)
    assert result.clips[0].sampling == Sampling(6, times, 1 / 10, 1.5 * 10 / steps)


def test_an_explicit_count_of_one_is_a_still_lasting_one_over_the_clip_fps():
    selected = looping(animation("walk", 0.5, 1.5), count=1)
    result = plan(
        "s", [selected], View(1, 0.0), 12, overrides={"walk": ClipOverride(fps=5)}
    )
    assert result.clips[0].sampling == Sampling(1, (0.5,), 1 / 5, 1.0)


@pytest.mark.parametrize("count", [None, 3, "auto"])
def test_zero_duration_and_static_clips_ignore_the_count_but_use_the_clip_fps(count):
    pose = looping(animation("pose", 4.25, 4.25, index=1), count)
    static = SelectedClip(STATIC, one_shot=True, frames=count)
    result = plan(
        "s",
        [pose, static],
        View(2, 0.0),
        12,
        overrides={"pose": ClipOverride(fps=4), "static": ClipOverride(fps=2)},
    )
    assert result.clips[0].sampling == Sampling(1, (4.25,), 1 / 4)
    assert result.clips[1].sampling == Sampling(1, (0.0,), 1 / 2)
    assert len(result.frames) == 4


def test_an_animation_named_static_is_an_ordinary_clip():
    clip = animation("static", 1.0, 2.0, index=3)
    result = plan("s", [looping(clip)], View(1, 0.0), 4)
    assert result.clips[0].sampling == Sampling(4, (1.0, 1.25, 1.5, 1.75), 0.25)


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True, "12"])
def test_fps_must_be_finite_and_positive(bad):
    clip = looping(animation("walk", 0.0, 1.0))
    with pytest.raises(ValueError, match="global fps"):
        plan("s", [clip], RING8, bad)
    with pytest.raises(ValueError, match="clip 'walk' fps"):
        plan("s", [clip], RING8, 12, overrides={"walk": ClipOverride(fps=bad)})


def test_a_bad_explicit_count_names_its_clip():
    with pytest.raises(ValueError, match="clip 'walk'.*frame count"):
        plan("s", [looping(animation("walk", 0.0, 1.0), count=0)], RING8, 12)


# Stored directions (requirement 4, 6)


def test_a_restricted_global_list_a_reordered_override_and_a_per_clip_all():
    walk = looping(animation("walk", 0.0, 0.5, index=0))
    attack = one_shot(animation("attack", 0.0, 0.25, index=1))
    idle = looping(animation("idle", 0.0, 0.25, index=2))
    result = plan(
        "hero",
        [walk, attack, idle],
        View(8, 10.0),
        4,
        stored_directions=[0, 2, 4],
        overrides={
            "attack": ClipOverride(stored_directions=[6, 1]),
            "idle": ClipOverride(stored_directions=ALL),
        },
    )
    walk_plan, attack_plan, idle_plan = result.clips
    angle = lambda i: (10.0 + i * 45) % 360  # noqa: E731
    assert [d.index for d in walk_plan.directions] == [0, 2, 4]
    assert [d.index for d in attack_plan.directions] == [6, 1]
    assert [d.index for d in idle_plan.directions] == list(range(8))
    for clip_plan in result.clips:
        for d in clip_plan.directions:
            assert d.angle == angle(d.index)
    # Selection order, then configured direction order, then sample order.
    assert addresses(result, "walk") == [
        ("walk", d, t) for d in (0, 2, 4) for t in (0.0, 0.25)
    ]
    assert addresses(result, "attack") == [
        ("attack", d, t) for d in (6, 1) for t in (0.0, 0.25)
    ]
    assert [c for c, _, _ in addresses(result)] == (
        ["walk"] * 6 + ["attack"] * 4 + ["idle"] * 8
    )
    assert [f.angle for f in result.clips[1].frames] == [
        angle(6),
        angle(6),
        angle(1),
        angle(1),
    ]
    assert [f.index for f in result.clips[1].frames] == [0, 1, 0, 1]
    assert len({f.address for f in result.frames}) == len(result.frames) == 18


def test_an_override_replaces_the_global_list_wholesale():
    clip = looping(animation("walk", 0.0, 0.25))
    result = plan(
        "s",
        [clip],
        RING8,
        4,
        stored_directions=[0, 1, 2],
        overrides={"walk": ClipOverride(stored_directions=[5])},
    )
    assert [d.index for d in result.clips[0].directions] == [5]


def test_a_null_override_inherits_the_global_order():
    clip = looping(animation("walk", 0.0, 0.25))
    result = plan(
        "s",
        [clip],
        RING8,
        4,
        stored_directions=(7, 3),
        overrides={"walk": ClipOverride()},
    )
    assert [d.index for d in result.clips[0].directions] == [7, 3]


def test_overrides_for_unselected_or_unknown_clips_are_ignored():
    clip = looping(animation("walk", 0.0, 0.25))
    ignored = ClipOverride(fps=-1, stored_directions=[99], mirrors={99: 98})
    result = plan(
        "s",
        [clip],
        RING8,
        4,
        overrides={"run": ignored, "walk": ClipOverride()},
    )
    assert result == plan("s", [clip], RING8, 4)


@pytest.mark.parametrize(
    ("stored", "message"),
    [
        ([], "empty"),
        ((), "empty"),
        ([1, 2, 1], "index 1 is listed twice"),
        ([0, 8], "index 8 is not in the view's 8 directions"),
        ([-1], "index -1 is not in the view"),
        ([True], "not a direction index"),
        (["1"], "not a direction index"),
        ([1.0], "not a direction index"),
        ("some", "expected 'all' or a list"),
        (3, "expected 'all' or a list"),
    ],
)
def test_bad_stored_lists_are_rejected_and_name_their_setting(stored, message):
    clip = looping(animation("walk", 0.0, 0.25))
    with pytest.raises(ValueError, match=f"global stored_directions.*{message}"):
        plan("s", [clip], RING8, 4, stored_directions=stored)
    with pytest.raises(ValueError, match=f"clip 'walk' stored_directions.*{message}"):
        plan(
            "s",
            [clip],
            RING8,
            4,
            overrides={"walk": ClipOverride(stored_directions=stored)},
        )


def test_the_global_list_is_checked_even_when_every_clip_overrides_it():
    clip = looping(animation("walk", 0.0, 0.25))
    with pytest.raises(ValueError, match="global stored_directions.*index 9"):
        plan(
            "s",
            [clip],
            RING8,
            4,
            stored_directions=[9],
            overrides={"walk": ClipOverride(stored_directions=[0])},
        )
    with pytest.raises(ValueError, match="global mirrors.*index 9"):
        plan(
            "s",
            [clip],
            RING8,
            4,
            mirrors={9: 0},
            overrides={"walk": ClipOverride(mirrors={})},
        )


def test_a_view_with_fewer_directions_rejects_indices_it_lacks():
    clip = looping(animation("walk", 0.0, 0.25))
    with pytest.raises(ValueError, match="index 5 is not in the view's 4"):
        plan("s", [clip], View(4, 0.0), 4, stored_directions=[0, 5])


def test_custom_start_and_yaw_do_not_move_indices_or_angles():
    clip = looping(animation("walk", 0.0, 0.25))
    view = View(4, 30.0, model_yaw=45.0)
    result = plan("s", [clip], view, 4, stored_directions=[3, 0])
    assert [(f.address.direction, f.angle) for f in result.frames] == [
        (3, 300.0),
        (0, 30.0),
    ]


# Mirrors (requirement 5)


def test_inherited_mirrors_name_pairs_without_adding_frames():
    clip = looping(animation("walk", 0.0, 0.5))
    plain = plan("s", [clip], RING8, 4, stored_directions=[0, 1, 2, 3, 4])
    result = plan(
        "s",
        [clip],
        RING8,
        4,
        stored_directions=[0, 1, 2, 3, 4],
        mirrors={7: 1, 5: 3, 6: 2},
    )
    assert result.clips[0].mirrors == (
        MirrorPair(5, 3),
        MirrorPair(6, 2),
        MirrorPair(7, 1),
    )
    assert result.frames == plain.frames
    assert {f.address.direction for f in result.frames} == {0, 1, 2, 3, 4}


def test_mirror_insertion_order_does_not_change_the_plan():
    clip = looping(animation("walk", 0.0, 0.5))
    first = plan(
        "s", [clip], RING8, 4, stored_directions=[0, 1, 2], mirrors={7: 1, 6: 2}
    )
    second = plan(
        "s", [clip], RING8, 4, stored_directions=[0, 1, 2], mirrors={6: 2, 7: 1}
    )
    assert first == second


def test_a_per_clip_map_replaces_the_global_one_and_an_empty_map_disables_it():
    walk = looping(animation("walk", 0.0, 0.5, index=0))
    run = looping(animation("run", 0.0, 0.5, index=1))
    idle = looping(animation("idle", 0.0, 0.5, index=2))
    result = plan(
        "s",
        [walk, run, idle],
        RING8,
        4,
        stored_directions=[0, 1, 2],
        mirrors={7: 1},
        overrides={
            "run": ClipOverride(mirrors={6: 2}),
            "idle": ClipOverride(mirrors={}),
        },
    )
    assert result.clips[0].mirrors == (MirrorPair(7, 1),)
    assert result.clips[1].mirrors == (MirrorPair(6, 2),)
    assert result.clips[2].mirrors == ()


@pytest.mark.parametrize(
    ("mirrors", "message"),
    [
        ({7: 3}, "source 3 of target 7 is not a stored direction"),
        ({1: 0}, "target 1 .source 0. is a stored direction"),
        ({0: 0}, "target 0 .source 0. is a stored direction"),
        ({5: 4, 4: 1}, "target 4 .source 1. is a stored direction"),
        ({8: 0}, "index 8 is not in the view"),
        ({7: 8}, "index 8 is not in the view"),
        ({"7": 1}, "not a direction index"),
        ({7: True}, "not a direction index"),
    ],
)
def test_invalid_mirrors_cannot_produce_a_plan(mirrors, message):
    clip = looping(animation("walk", 0.0, 0.5))
    with pytest.raises(ValueError, match=message):
        plan("s", [clip], RING8, 4, stored_directions=[0, 1, 4], mirrors=mirrors)


def test_a_chain_cannot_qualify():
    # 6 mirrors 5 and 5 mirrors 1: 5 is both an omitted target and a source.
    clip = looping(animation("walk", 0.0, 0.5))
    with pytest.raises(ValueError, match="source 5 of target 6"):
        plan("s", [clip], RING8, 4, stored_directions=[0, 1], mirrors={6: 5, 5: 1})


def test_inherited_mirrors_that_meet_a_stored_target_are_rejected_not_dropped():
    # A per-clip `all` under a restricted global list with global mirrors.
    walk = looping(animation("walk", 0.0, 0.5))
    with pytest.raises(ValueError, match="clip 'walk' mirrors.*target 7"):
        plan(
            "s",
            [walk],
            RING8,
            4,
            stored_directions=[0, 1],
            mirrors={7: 1},
            overrides={"walk": ClipOverride(stored_directions=ALL)},
        )
    # The clip can disable the inherited map instead.
    ok = plan(
        "s",
        [walk],
        RING8,
        4,
        stored_directions=[0, 1],
        mirrors={7: 1},
        overrides={"walk": ClipOverride(stored_directions=ALL, mirrors={})},
    )
    assert ok.clips[0].mirrors == ()
    assert len(ok.frames) == 8 * 2


def test_a_mirror_error_names_the_clip_when_the_clip_s_own_map_is_bad():
    walk = looping(animation("walk", 0.0, 0.5))
    with pytest.raises(ValueError, match="clip 'walk' mirrors.*source 5"):
        plan(
            "s",
            [walk],
            RING8,
            4,
            stored_directions=[0, 1],
            overrides={"walk": ClipOverride(mirrors={7: 5})},
        )


# Addresses (requirement 6)


def test_two_frames_with_one_address_are_rejected():
    clip = looping(animation("walk", 0.0, 1.0))
    with pytest.raises(ValueError, match="share the address"):
        plan("s", [clip, clip], View(2, 0.0), 4)


def test_reordering_stored_views_does_not_renumber_addresses():
    clip = looping(animation("walk", 0.0, 0.5))
    forward = plan("s", [clip], RING8, 4, stored_directions=[1, 3])
    backward = plan("s", [clip], RING8, 4, stored_directions=[3, 1])
    assert {f.address for f in forward.frames} == {f.address for f in backward.frames}
    assert forward.frames[0].address == FrameAddress("s", "default", "walk", 1, 0.0)
    assert backward.frames[0].address == FrameAddress("s", "default", "walk", 3, 0.0)
    assert forward.frames != backward.frames


# Compatibility (requirement 7)


@pytest.mark.parametrize(
    "view", [View(8, 0.0), View(3, 10.0), View(5, 200.0, model_yaw=45.0), View(1, 0.0)]
)
@pytest.mark.parametrize("count", ["auto", 1, 5])
def test_the_default_plan_equals_the_existing_enumeration(view, count):
    selected = [
        looping(animation("walk", 0.5, 1.5, index=1)),
        one_shot(animation("attack", 1.0, 1.4, index=0)),
        looping(animation("pose", 3.0, 3.0, index=2)),
        looping(STATIC),
        SelectedClip(animation("run", 0.0, 2.0, index=3), False, 4),
    ]
    result = plan("hero", selected, view, 12, count)
    assert result.frames == frames("hero", selected, view, 12, count)
    assert all(clip.mirrors == () for clip in result.clips)
    assert all(len(clip.directions) == view.directions for clip in result.clips)


def test_a_plan_is_deterministic():
    clips = [looping(animation("walk", 0.0, 1.0)), one_shot(animation("hit", 0.0, 0.3))]
    overrides = {"hit": ClipOverride(fps=6, stored_directions=[2, 0], mirrors={})}
    one = plan("hero", clips, RING8, 12, overrides=overrides)
    two = plan("hero", clips, RING8, 12, overrides=overrides)
    assert one == two
    assert all(isinstance(f, Frame) for f in one.frames)
