"""Named buffers carried per frame from capture into stylize, following design
§Pipeline (Frames into stylize)."""

import weakref
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_command import Setup, run, speckled_argv

from moskophoros import cleanup, imageops, stylize
from moskophoros.sampling import (
    BACKGROUND,
    IDENTITY,
    SHADE,
    FrameAddress,
    Identities,
    ImageFrame,
)

COLORS = ((0, 0, 0), (255, 0, 0), (255, 255, 255))
# Every existing look: each reduction, with and without a palette.
LOOKS = [
    pytest.param(stylize.plain, None, id="plain"),
    pytest.param(stylize.plain, COLORS, id="plain-palette"),
    pytest.param(stylize.mode, None, id="mode"),
    pytest.param(stylize.mode, COLORS, id="mode-palette"),
]
OPTIONS = [
    pytest.param("plain", False, id="plain"),
    pytest.param("plain", True, id="plain-palette"),
    pytest.param("mode", False, id="mode"),
    pytest.param("mode", True, id="mode-palette"),
]
IDENTITIES = Identities(("steel", "cloth"))


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def address(i):
    return FrameAddress("s", "default", "walk", i, float(i))


def buffers(i):
    """A frame's identity, shade and raw extra buffers, all 8×8."""
    rng = np.random.default_rng(i)
    identity = rng.integers(BACKGROUND, len(IDENTITIES), (8, 8), dtype=np.int32)
    shade = rng.integers(0, 256, (8, 8), dtype=np.uint8)
    extra = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    return {IDENTITY: identity, SHADE: shade, "extra": extra}


def colour(i):
    rng = np.random.default_rng(100 + i)
    pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    pixels[:4, :4, 3] = 0
    return pixels


def look_argv(setup, reduce, paletted):
    options = ["--reduce", reduce]
    if paletted:
        path = setup.tmp_path / "test.hex"
        path.write_text("".join(bytes(c).hex() + "\n" for c in COLORS))
        options += ["--palette", str(path)]
    return options


# The frame and the identity list


def test_a_frame_built_from_its_colour_carries_no_buffers():
    pixels = np.zeros((2, 2, 4), dtype=np.uint8)
    frame = ImageFrame(address(0), pixels, {"k": 1})
    assert (frame.pixels, frame.metadata, frame.buffers) == (pixels, {"k": 1}, {})
    assert ImageFrame(address(0), pixels).buffers == {}


def test_a_frame_carries_its_named_buffers_as_given():
    named = buffers(0)
    frame = ImageFrame(address(0), colour(0), buffers=named)
    assert frame.buffers is named


def test_the_identity_list_ends_with_the_no_identity_class():
    assert len(IDENTITIES) == 3
    assert IDENTITIES.no_identity == 2
    assert IDENTITIES.names[:2] == ("steel", "cloth")
    assert BACKGROUND not in range(len(IDENTITIES))
    empty = Identities(())
    assert (len(empty), empty.no_identity) == (1, 0)


# Stylize


@pytest.mark.parametrize(("look", "palette"), LOOKS)
def test_buffers_do_not_change_the_reduced_frames(look, palette):
    bare = [ImageFrame(address(i), colour(i), {"i": i}) for i in range(3)]
    named = [buffers(i) for i in range(3)]
    before = [{name: array.copy() for name, array in b.items()} for b in named]
    carrying = [ImageFrame(address(i), colour(i), {"i": i}, named[i]) for i in range(3)]
    expected = look(bare, 2, palette=palette)
    result = look(carrying, 2, palette=palette, identities=IDENTITIES)
    for reduced, plain_reduced, original in zip(
        result, expected, carrying, strict=True
    ):
        assert reduced.address == original.address
        assert reduced.metadata is original.metadata
        assert reduced.buffers == {}
        np.testing.assert_array_equal(reduced.pixels, plain_reduced.pixels)
    for given, kept in zip(named, before, strict=True):
        assert given.keys() == kept.keys()
        for name in kept:
            np.testing.assert_array_equal(given[name], kept[name])


@pytest.mark.parametrize(("look", "palette"), LOOKS)
def test_a_stage_releases_every_buffer_of_a_frame_before_loading_the_next(
    look, palette
):
    held = []

    def capture():
        for i in range(3):
            assert all(ref() is None for ref in held), "a previous frame is held"
            pixels, named = colour(i), buffers(i)
            held.extend(weakref.ref(a) for a in [pixels, *named.values()])
            yield ImageFrame(address(i), pixels, {"i": i}, named)
            del pixels, named

    result = look(capture(), 2, palette=palette, identities=IDENTITIES)
    assert len(result) == 3
    # The reduced frames keep nothing supersampled, through fields or metadata.
    assert all(ref() is None for ref in held)
    assert all(frame.buffers == {} for frame in result)


# The command


def test_an_extra_capture_buffer_reaches_stylize_intact(setup, capsys, monkeypatch):
    seen = []
    real_plain = stylize.plain

    def recording_plain(frames, factor, **kwargs):
        def watched():
            for frame in frames:
                seen.append(
                    (
                        frame.pixels.copy(),
                        {n: a.copy() for n, a in frame.buffers.items()},
                    )
                )
                yield frame
                del frame

        return real_plain(watched(), factor, **kwargs)

    monkeypatch.setattr(stylize, "plain", recording_plain)
    setup.configure(extra=True)
    work = setup.tmp_path / "work"
    assert run(capsys, setup.argv("--work-dir", str(work))) == (0, "", "")
    assert len(seen) == (4 + 3) * 8
    for i, (pixels, named) in enumerate(seen):
        assert set(named) == {"extra"}
        with Image.open(work / "render" / "extra" / f"{i:06d}.png") as image:
            np.testing.assert_array_equal(named["extra"], np.asarray(image))
        with Image.open(work / "render" / "color" / f"{i:06d}.png") as image:
            np.testing.assert_array_equal(pixels, np.asarray(image))
        assert named["extra"].dtype == np.uint8
        assert not np.array_equal(named["extra"], pixels)


@pytest.mark.parametrize(("reduce", "paletted"), OPTIONS)
def test_an_extra_capture_buffer_changes_no_output(setup, capsys, reduce, paletted):
    argv = speckled_argv(setup, *look_argv(setup, reduce, paletted))
    setup.configure(pixels="noise")
    status = run(capsys, argv)
    assert status[0] == 0
    without = setup.listing()
    setup.configure(pixels="noise", extra=True)
    assert run(capsys, argv) == status
    assert setup.listing() == without
    assert sorted(without) == [
        "hero.attack.gif",
        "hero.json",
        "hero.png",
        "hero.walk.gif",
    ]


@pytest.mark.parametrize(("reduce", "paletted"), OPTIONS)
def test_the_command_loads_frames_lazily_and_releases_each_before_the_next(
    setup, capsys, monkeypatch, reduce, paletted
):
    events, held = [], {}
    real_load = imageops.load_png
    reductions = {"plain": "reduce_blocks", "mode": "reduce_blocks_mode"}
    real_reduce = getattr(imageops, reductions[reduce])

    def load(path):
        path = Path(path)
        frame = int(path.stem)
        for earlier, refs in held.items():
            if earlier != frame:
                assert all(ref() is None for ref in refs), f"frame {earlier} is held"
        events.append(("load", path.parent.name))
        pixels = real_load(path)
        held.setdefault(frame, []).append(weakref.ref(pixels))
        return pixels

    def reduce_blocks(pixels, factor):
        events.append("reduce")
        return real_reduce(pixels, factor)

    def passthrough(frames):
        # The reduced frames are all held here, and keep no supersampled array.
        frames = tuple(frames)
        assert all(ref() is None for refs in held.values() for ref in refs)
        assert all(frame.buffers == {} for frame in frames)
        return real_passthrough(frames)

    real_passthrough = cleanup.passthrough
    monkeypatch.setattr(imageops, "load_png", load)
    monkeypatch.setattr(imageops, reductions[reduce], reduce_blocks)
    monkeypatch.setattr(cleanup, "passthrough", passthrough)
    setup.configure(extra=True)
    argv = speckled_argv(setup, *look_argv(setup, reduce, paletted))
    assert run(capsys, argv) == (0, "", "")
    frames = (4 + 3) * 8
    assert events == [("load", "color"), ("load", "extra"), "reduce"] * frames
    assert len(held) == frames
