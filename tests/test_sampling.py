import pytest

from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import Frame, FrameAddress, Sampling, frames, sample
from moskophoros.views import View


def animation(name, t0, t1, index=0):
    return Clip(index, name, t0, t1, ())


def looping(clip):
    return SelectedClip(clip, one_shot=False)


def one_shot(clip):
    return SelectedClip(clip, one_shot=True)


STATIC = Clip(None, "static", 0.0, 0.0, ())


# Sample times


def test_a_looping_clip_leaves_out_its_endpoint():
    # d = 1.0 s at 12 fps: n = floor(12.5) = 12.
    result = sample(looping(animation("walk", 0.5, 1.5)), 12)
    assert result == Sampling(12, tuple(0.5 + k * 1.0 / 12 for k in range(12)), 1 / 12)
    assert result.times[0] == 0.5


def test_a_one_shot_clip_keeps_its_final_pose():
    result = sample(one_shot(animation("attack", 0.5, 1.5)), 12)
    assert result == Sampling(13, tuple(0.5 + k * 1.0 / 12 for k in range(13)), 1 / 12)
    assert result.times[-1] == 1.5


@pytest.mark.parametrize(
    ("duration", "fps", "n"),
    [
        (0.125, 12, 2),  # d·fps = 1.5 rounds up
        (0.375, 12, 5),  # 4.5
        (0.25, 10, 3),  # 2.5
        (0.0625, 8, 1),  # 0.5
        (0.5, 3, 2),  # 1.5
        (0.2, 12, 2),  # 2.4 rounds down
    ],
)
def test_frame_count_rounds_half_up(duration, fps, n):
    t0 = 2.0
    t1 = t0 + duration
    d = t1 - t0  # the design's d, which can differ from `duration` in its last bit
    loop = sample(looping(animation("a", t0, t1)), fps)
    once = sample(one_shot(animation("a", t0, t1)), fps)
    assert loop == Sampling(n, tuple(t0 + k * d / n for k in range(n)), d / n)
    assert once == Sampling(n + 1, tuple(t0 + k * d / n for k in range(n + 1)), d / n)


def test_a_short_clip_still_has_one_frame():
    # d·fps = 0.24 rounds to 0, clamped to n = 1: one frame lasting d when
    # looping, and the start and end poses when one-shot.
    clip = animation("blink", 3.0, 3.02)
    duration = 3.02 - 3.0
    assert sample(looping(clip), 12) == Sampling(1, (3.0,), duration)
    assert sample(one_shot(clip), 12) == Sampling(2, (3.0, 3.0 + duration), duration)


@pytest.mark.parametrize("select", [looping, one_shot])
def test_a_zero_length_clip_has_one_frame_at_t0(select):
    assert sample(select(animation("pose", 4.25, 4.25)), 8) == Sampling(
        1, (4.25,), 1 / 8
    )


@pytest.mark.parametrize("select", [looping, one_shot])
def test_the_static_clip_has_one_frame_at_0(select):
    assert sample(select(STATIC), 12) == Sampling(1, (0.0,), 1 / 12)


def test_an_animation_named_static_is_sampled_as_an_animation():
    clip = animation("static", 1.0, 2.0, index=3)
    assert sample(looping(clip), 4) == Sampling(4, (1.0, 1.25, 1.5, 1.75), 0.25)


@pytest.mark.parametrize("fps", [0, -12, float("nan"), float("inf")])
def test_fps_must_be_finite_and_positive(fps):
    with pytest.raises(ValueError, match="fps"):
        sample(looping(animation("walk", 0.0, 1.0)), fps)


# Frame addresses and enumeration


def test_addresses_compare_by_value_and_are_keys():
    a = FrameAddress("hero", "default", "walk", 2, 0.25)
    b = FrameAddress("hero", "default", "walk", 2, 0.25)
    assert a == b
    assert {a: 1}[b] == 1
    assert a != FrameAddress("hero", "default", "walk", 2, 0.5)


def test_frames_are_in_sheet_order():
    # walk: d = 0.5 s at 4 fps, n = 2, looping: 0.25, 0.5.
    # attack: d = 0.5 s at 4 fps, n = 2, one-shot: 1.0, 1.25, 1.5.
    walk = looping(animation("walk", 0.25, 0.75, index=1))
    attack = one_shot(animation("attack", 1.0, 1.5, index=0))
    view = View(30.0, 3, 10.0)

    result = frames("hero", [walk, attack], view, 4)

    expected = []
    for clip, times in (("walk", [0.25, 0.5]), ("attack", [1.0, 1.25, 1.5])):
        for direction, angle in enumerate([10.0, 130.0, 250.0]):
            for index, time_s in enumerate(times):
                address = FrameAddress("hero", "default", clip, direction, time_s)
                expected.append(Frame(address, index, angle))
    assert list(result) == expected
    assert len({frame.address for frame in result}) == len(result) == 15


def test_addresses_start_at_a_nonzero_t0():
    result = frames(
        "hero", [looping(animation("idle", 7.5, 8.5))], View(30.0, 1, 0.0), 2
    )
    assert [frame.address.time_s for frame in result] == [7.5, 8.0]


def test_the_static_clip_has_one_frame_per_direction():
    result = frames("crate", [looping(STATIC)], View(90.0, 8, 0.0), 12)
    assert [
        (f.address.clip, f.address.direction, f.address.time_s) for f in result
    ] == [("static", d, 0.0) for d in range(8)]
    assert {frame.index for frame in result} == {0}


def test_two_frames_with_one_address_are_rejected():
    clip = looping(animation("walk", 0.0, 1.0))
    with pytest.raises(ValueError, match="share the address"):
        frames("hero", [clip, clip], View(30.0, 2, 0.0), 4)


def test_frames_are_deterministic():
    clips = [looping(animation("walk", 0.0, 1.0)), one_shot(animation("hit", 0.0, 0.3))]
    view = View(30.0, 8, 0.0, model_yaw=45.0)
    assert frames("hero", clips, view, 12) == frames("hero", clips, view, 12)
