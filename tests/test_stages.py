import builtins
import os
import subprocess

import numpy as np
import pytest

from moskophoros import cleanup, stylize
from moskophoros.sampling import FrameAddress, ImageFrame

FINGERPRINT = {"fingerprint": "sha256:" + "ab" * 32}


def _frames():
    """Three 4×4 frames in a deliberately unsorted address order."""
    addresses = [
        FrameAddress("hero", "default", "walk", 1, 0.5),
        FrameAddress("hero", "default", "walk", 0, 0.0),
        FrameAddress("hero", "default", "idle", 0, 0.0),
    ]
    frames = []
    for k, address in enumerate(addresses):
        pixels = np.zeros((4, 4, 4), dtype=np.uint8)
        pixels[:2, :2] = (10 * (k + 1), 20, 30, 255)  # top-left block opaque
        frames.append(ImageFrame(address, pixels, {**FINGERPRINT, "k": k}))
    return frames


def test_plain_reduces_every_frame_keeping_addresses_order_and_metadata():
    frames = _frames()
    before = [frame.pixels.copy() for frame in frames]
    result = stylize.plain(frames, 2)
    assert [frame.address for frame in result] == [frame.address for frame in frames]
    for k, (original, reduced) in enumerate(zip(frames, result, strict=True)):
        assert reduced.metadata is original.metadata
        assert reduced.pixels.tolist() == [
            [[10 * (k + 1), 20, 30, 255], [0, 0, 0, 0]],
            [[0, 0, 0, 0], [0, 0, 0, 0]],
        ]
        assert np.array_equal(original.pixels, before[k])


def test_plain_accepts_any_iterable_and_returns_a_tuple():
    result = stylize.plain(iter(_frames()), 4)
    assert isinstance(result, tuple)
    assert [frame.pixels.shape for frame in result] == [(1, 1, 4)] * 3


def test_plain_rejects_a_frame_the_factor_does_not_divide():
    with pytest.raises(ValueError, match="does not divide"):
        stylize.plain(_frames(), 3)


def test_passthrough_returns_the_frames_unchanged():
    frames = _frames()
    result = cleanup.passthrough(frames)
    assert isinstance(result, tuple)
    assert len(result) == len(frames)
    for original, passed in zip(frames, result, strict=True):
        assert passed is original
        assert passed.address == original.address
        assert passed.pixels is original.pixels
        assert passed.metadata is original.metadata


def test_an_image_frame_defaults_to_no_metadata():
    frame = ImageFrame(
        FrameAddress("s", "default", "static", 0, 0.0), np.zeros((1, 1, 4))
    )
    assert frame.metadata == {}


def test_the_stages_touch_no_file_or_process(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("a stage touched a file or process")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    cleanup.passthrough(stylize.plain(_frames(), 2))
