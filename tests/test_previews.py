import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from moskophoros import export, sampling, views
from moskophoros.capture.backend import Settings
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import ImageFrame

GREY = (128, 128, 128)


def _settings(directions, cell, fps=2.0):
    return Settings(
        view="custom",
        pitch=30.0,
        directions=directions,
        start_angle=0.0,
        model_yaw=0.0,
        fps=fps,
        supersample=8,
        ppm=10.0,
        cell=cell,
        ground=(0.0, 0.0, 0.0),
        ground_px=(0, 0),
        root_motion="keep",
    )


def _clip(name, t0=0.0, t1=1.0, one_shot=False, index=0):
    return SelectedClip(Clip(index, name, t0, t1, ()), one_shot=one_shot)


def _previews(settings, clips, pixels):
    """Previews of `clips`, each frame's pixels from `pixels(clip, d, k)`."""
    view = views.View(settings.pitch, settings.directions, settings.start_angle)
    requested = sampling.frames("hero", clips, view, settings.fps)
    frames = [
        ImageFrame(f.address, pixels(f.address.clip, f.address.direction, f.index))
        for f in requested
    ]
    return export.previews(
        frames, subject="hero", settings=settings, selected_clips=clips
    )


def _decode(gif):
    """Each GIF frame as an RGB array, with its delay, and the loop count."""
    image = Image.open(io.BytesIO(gif))
    frames = []
    for k in range(image.n_frames):
        image.seek(k)
        frames.append((np.array(image.convert("RGB")), image.info["duration"]))
    return frames, image.info.get("loop")


def _solid(color, cell):
    width, height = cell
    pixels = np.zeros((height, width, 4), dtype=np.uint8)
    pixels[...] = color
    return pixels


# Layout


def test_directions_sit_side_by_side_enlarged_on_grey():
    cell = (3, 2)
    settings = _settings(3, cell)

    def pixels(clip, d, k):
        image = np.zeros((2, 3, 4), dtype=np.uint8)
        image[0, 0] = (10 * (d + 1), 20 * (k + 1), 7, 255)  # top-left pixel only
        image[1, 2] = (250, 0, 250, 255)  # bottom-right pixel
        return image

    (preview,) = _previews(settings, (_clip("walk"),), pixels)
    frames, loop = _decode(preview.gif)
    assert loop == 0
    assert len(frames) == 2  # a one-second loop at 2 fps
    for k, (rgb, _) in enumerate(frames):
        # N·W·4 by H·4: 3 directions of 3 pixels, 2 pixels high, 4 times.
        assert rgb.shape == (8, 36, 3)
        expected = np.empty((2, 9, 3), dtype=np.uint8)
        expected[...] = GREY
        for d in range(3):
            expected[0, 3 * d] = (10 * (d + 1), 20 * (k + 1), 7)
            expected[1, 3 * d + 2] = (250, 0, 250)
        assert np.array_equal(rgb, expected.repeat(4, axis=0).repeat(4, axis=1))


def test_a_single_frame_clip_gives_a_one_frame_looping_gif():
    static = SelectedClip(Clip(None, "static", 0.0, 0.0, ()), one_shot=False)
    (preview,) = _previews(
        _settings(1, (1, 1), fps=12.0),
        (static,),
        lambda *_: _solid((1, 2, 3, 255), (1, 1)),
    )
    frames, loop = _decode(preview.gif)
    assert loop == 0
    assert [(rgb.tolist(), delay) for rgb, delay in frames] == [
        ([[[1, 2, 3]] * 4] * 4, 80)  # 1/12 s is 8.33 cs, rounded to 80 ms
    ]


def test_identical_consecutive_samples_stay_separate_frames():
    # A one-shot of 1 s at 4 fps: 5 samples, all the same image.
    clip = _clip("hold", one_shot=True)
    (preview,) = _previews(
        _settings(2, (2, 2), fps=4.0),
        (clip,),
        lambda *_: _solid((9, 9, 9, 255), (2, 2)),
    )
    frames, _ = _decode(preview.gif)
    assert [delay for _, delay in frames] == [250, 250, 250, 250, 750]
    assert all((rgb == 9).all() for rgb, _ in frames)


def test_each_clip_gets_its_own_preview_in_sheet_order():
    clips = (_clip("b", index=1), _clip("a", index=0, one_shot=True))
    result = _previews(
        _settings(1, (1, 1)), clips, lambda *_: _solid((0, 0, 0, 255), (1, 1))
    )
    assert [p.clip for p in result] == ["b", "a"]
    assert [len(_decode(p.gif)[0]) for p in result] == [2, 3]


def test_repeated_generation_is_byte_identical():
    def pixels(clip, d, k):
        return _solid((d * 40, k * 30, 5, 255 if (d + k) % 2 else 0), (4, 3))

    first = _previews(_settings(4, (4, 3)), (_clip("walk"),), pixels)
    second = _previews(_settings(4, (4, 3)), (_clip("walk"),), pixels)
    assert first == second


# Width limit


def test_the_widest_representable_preview_is_encoded():
    # 43 directions of 381 pixels, enlarged 4 times: 65,532 pixels.
    (preview,) = _previews(
        _settings(43, (381, 1)),
        (SelectedClip(Clip(None, "static", 0.0, 0.0, ()), one_shot=False),),
        lambda *_: _solid((0, 0, 0, 255), (381, 1)),
    )
    assert Image.open(io.BytesIO(preview.gif)).size == (65_532, 4)


def test_a_preview_wider_than_gif_allows_is_a_usage_error():
    # 16 directions of 1024 pixels, enlarged 4 times: 65,536 pixels.
    with pytest.raises(export.UsageError) as raised:
        _previews(
            _settings(16, (1024, 1)),
            (_clip("walk"),),
            lambda *_: _solid((0, 0, 0, 255), (1024, 1)),
        )
    assert raised.value.exit_code == 2
    message = str(raised.value)
    assert "'walk'" in message
    assert "65536 pixels" in message
    assert "65535 pixels" in message


# Colors


def _palette_frame(colors, transparent, cell):
    """A frame holding `colors` once each, then `transparent` clear pixels,
    then the last color repeated to fill the cell."""
    width, height = cell
    pixels = np.zeros((width * height, 4), dtype=np.uint8)
    for i, color in enumerate(colors):
        pixels[i] = (*color, 255)
    pixels[len(colors) : len(colors) + transparent] = (99, 99, 99, 0)
    pixels[len(colors) + transparent :] = (*colors[-1], 255)
    return pixels.reshape(height, width, 4)


def _distinct(count, offset=0):
    """`count` distinct colors, none of them grey #808080."""
    return [((i + offset) % 256, (i + offset) // 256, 1) for i in range(count)]


def test_256_colors_including_the_background_are_kept_exactly():
    # 255 colors, an opaque #808080 and transparent pixels: 256 colors, since
    # the opaque grey and the background count once.
    colors = [*_distinct(255), GREY]
    frame = _palette_frame(colors, 2, (17, 16))
    (preview,) = _previews(_settings(1, (17, 16)), (_clip("walk"),), lambda *_: frame)
    assert preview.warnings == ()
    for rgb, _ in _decode(preview.gif)[0]:
        expected = frame[..., :3].copy()
        expected[frame[..., 3] == 0] = GREY
        assert np.array_equal(rgb[::4, ::4], expected)


def test_257_colors_are_reduced_without_dithering_and_warned_about():
    # 256 opaque colors, none grey, each in a 2×2 block, and transparent
    # pixels: 257 colors.
    colors = _distinct(256)
    cell = (34, 32)
    frame = np.zeros((32, 34, 4), dtype=np.uint8)
    for i, color in enumerate(colors):
        y, x = 2 * (i // 16), 2 * (i % 16)
        frame[y : y + 2, x : x + 2] = (*color, 255)
    # Columns 32 and 33 stay transparent.
    (preview,) = _previews(_settings(1, cell), (_clip("walk"),), lambda *_: frame)
    assert len(preview.warnings) == 1
    assert "'walk'" in preview.warnings[0]
    for decoded, _ in _decode(preview.gif)[0]:
        rgb = decoded[::4, ::4]
        assert len(np.unique(rgb.reshape(-1, 3), axis=0)) <= 256
        # Transparent source pixels are exact background.
        assert (rgb[:, 32:] == GREY).all()
        # Without dithering, each source color maps to one output color.
        for i in range(256):
            y, x = 2 * (i // 16), 2 * (i % 16)
            block = rgb[y : y + 2, x : x + 2].reshape(-1, 3)
            assert (block == block[0]).all()


def test_frames_keep_their_own_exact_colors_when_together_they_exceed_256():
    # Two samples with 200 colors each, 400 between them.
    first = _palette_frame(_distinct(200), 0, (16, 16))
    second = _palette_frame(_distinct(200, offset=300), 0, (16, 16))
    (preview,) = _previews(
        _settings(1, (16, 16)),
        (_clip("walk"),),
        lambda clip, d, k: first if k == 0 else second,
    )
    assert preview.warnings == ()
    (rgb0, _), (rgb1, _) = _decode(preview.gif)[0]
    assert np.array_equal(rgb0[::4, ::4], first[..., :3])
    assert np.array_equal(rgb1[::4, ::4], second[..., :3])


# Timing


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (0.125, 130),  # exactly 12.5 cs: half rounds up
        (0.375, 380),  # exactly 37.5 cs
        (0.5, 500),
        (1 / 12, 80),
        (0.124, 120),
        (0.019, 20),  # the 20 ms minimum
        (0.001, 20),
        (0.014, 20),
    ],
)
def test_frame_delays_round_half_up_to_10_ms_with_a_20_ms_minimum(duration, expected):
    assert export.preview_delays_ms(duration, 3, False) == [expected] * 3


def test_a_one_shot_holds_only_its_last_frame_500_ms_longer():
    assert export.preview_delays_ms(0.125, 3, True) == [130, 130, 630]
    assert export.preview_delays_ms(0.001, 1, True) == [520]


def test_decoded_delays_follow_the_frame_duration():
    # A 1 s loop at 8 fps: 8 frames of 0.125 s each.
    (preview,) = _previews(
        _settings(1, (1, 1), fps=8.0),
        (_clip("walk"),),
        lambda *_: _solid((0, 0, 0, 255), (1, 1)),
    )
    assert [delay for _, delay in _decode(preview.gif)[0]] == [130] * 8


def _long_frame(seconds, one_shot):
    """A zero-length clip at 1/seconds fps: one frame lasting `seconds`."""
    return _previews(
        _settings(1, (1, 1), fps=1 / seconds),
        (_clip("pose", 0.5, 0.5, one_shot=one_shot),),
        lambda *_: _solid((0, 0, 0, 255), (1, 1)),
    )


@pytest.mark.parametrize(
    ("seconds", "one_shot"), [(655.35, False), (654.85, True)], ids=["loop", "one-shot"]
)
def test_the_longest_representable_delay_is_encoded(seconds, one_shot):
    (preview,) = _long_frame(seconds, one_shot)
    assert [delay for _, delay in _decode(preview.gif)[0]] == [655_350]


@pytest.mark.parametrize(
    ("seconds", "one_shot"), [(655.36, False), (654.86, True)], ids=["loop", "one-shot"]
)
def test_a_delay_longer_than_gif_allows_is_a_usage_error(seconds, one_shot):
    with pytest.raises(export.UsageError) as raised:
        _long_frame(seconds, one_shot)
    assert raised.value.exit_code == 2
    message = str(raised.value)
    assert "'pose'" in message
    assert "655360 ms" in message
    assert "655350 ms" in message


def test_a_frame_too_long_for_a_float_is_a_usage_error():
    # At the accepted fps 1e-309, a static frame's 1/fps overflows to infinity.
    with pytest.raises(export.UsageError) as raised:
        _previews(
            _settings(1, (1, 1), fps=1e-309),
            (SelectedClip(Clip(None, "static", 0.0, 0.0, ()), one_shot=True),),
            lambda *_: _solid((0, 0, 0, 255), (1, 1)),
        )
    assert raised.value.exit_code == 2
    message = str(raised.value)
    assert "'static'" in message
    assert "inf ms" in message
    assert "655350 ms" in message
    assert export.preview_delays_ms(float("inf"), 2, True) == [float("inf")] * 2


# Wrong frames


def test_a_missing_frame_is_rejected():
    settings = _settings(2, (1, 1))
    clips = (_clip("walk"),)
    view = views.View(30.0, 2, 0.0)
    requested = sampling.frames("hero", clips, view, 2.0)[1:]
    frames = [ImageFrame(f.address, _solid((0, 0, 0, 255), (1, 1))) for f in requested]
    with pytest.raises(ValueError, match="missing"):
        export.previews(frames, subject="hero", settings=settings, selected_clips=clips)


def test_partial_alpha_is_rejected():
    with pytest.raises(ValueError, match="alpha other than 0 or 255"):
        _previews(
            _settings(1, (1, 1)),
            (_clip("walk"),),
            lambda *_: _solid((0, 0, 0, 128), (1, 1)),
        )


# Filenames


def _names(png, *clip_names):
    clips = tuple(_clip(name, index=i) for i, name in enumerate(clip_names))
    return [str(path) for path in export.preview_paths(png, clips)]


def test_preview_paths_sit_beside_the_png_with_safe_names():
    assert _names(
        Path("/out/dir/hero.png"), "walk", "run fast", "a/b", "läuft", "攻撃"
    ) == [
        "/out/dir/hero.walk.gif",
        "/out/dir/hero.run_fast.gif",
        "/out/dir/hero.a_b.gif",
        "/out/dir/hero.l_uft.gif",
        "/out/dir/hero.__.gif",
    ]


def test_names_that_clean_alike_take_the_next_free_suffix():
    assert _names("hero.png", "a b", "a/b", "a:b") == [
        "hero.a_b.gif",
        "hero.a_b-2.gif",
        "hero.a_b-3.gif",
    ]


def test_a_suffix_never_takes_another_clips_own_name():
    assert _names("hero.png", "a b", "a/b", "a b-2") == [
        "hero.a_b.gif",
        "hero.a_b-3.gif",
        "hero.a_b-2.gif",
    ]


def test_names_differing_only_in_ascii_case_collide():
    assert _names("hero.png", "Walk", "walk") == ["hero.Walk.gif", "hero.walk-2.gif"]
    assert _names("hero.png", "walk", "WALK-2", "Walk") == [
        "hero.walk.gif",
        "hero.WALK-2.gif",
        "hero.Walk-3.gif",
    ]


def test_write_previews_writes_each_to_its_path(tmp_path):
    result = _previews(
        _settings(1, (1, 1)),
        (_clip("a", index=0), _clip("b", index=1)),
        lambda *_: _solid((0, 0, 0, 255), (1, 1)),
    )
    paths = export.preview_paths(tmp_path / "hero.png", (_clip("a"), _clip("b")))
    export.write_previews(result, paths)
    assert [path.read_bytes() for path in paths] == [p.gif for p in result]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hero.a.gif", "hero.b.gif"]
    with pytest.raises(ValueError, match="2 previews but 1 paths"):
        export.write_previews(result, paths[:1])
