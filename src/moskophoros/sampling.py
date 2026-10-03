"""Sample times and frame addresses, following design §Clips and sampling.

A frame's address (`subject`, `variant`, `clip`, `direction`, `time_s`) is
its identity in every stage. `frames` enumerates a request in sheet order:
clips in selection order, then directions in index order, then samples in
time order. Everything here is pure.

After capture, stages pass `ImageFrame`s: an address, its pixels and the
metadata attached to it.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from moskophoros import views

# Slice 1 has one variant.
VARIANT = "default"


@dataclass(frozen=True)
class Sampling:
    """One clip's samples: `times` in seconds, each lasting `frame_duration`."""

    frame_count: int
    times: tuple[float, ...]
    frame_duration: float


@dataclass(frozen=True)
class FrameAddress:
    subject: str
    variant: str
    clip: str
    direction: int
    time_s: float


@dataclass(frozen=True)
class Frame:
    """A requested frame. `index` (the sample's position in its clip) and
    `angle` (the direction's angle in degrees) are lookup data for layout and
    capture; `address` alone identifies the frame."""

    address: FrameAddress
    index: int
    angle: float


@dataclass(frozen=True, eq=False)
class ImageFrame:
    """A frame's image as it passes between the stages after capture.

    `pixels` is an image as `imageops` defines it: a `uint8` array of shape
    `(height, width, 4)`, straight-alpha RGBA. `metadata` is whatever the
    caller attaches, such as the sheet fingerprint; every stage passes it on
    unchanged. A stage never changes a frame's pixels in place.
    """

    address: FrameAddress
    pixels: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)


def sample(selected, fps):
    """The samples of `selected`, a `gltf.SelectedClip`, at target `fps`.

    The synthetic `static` clip, which has no animation index, and any clip of
    zero duration have one frame at `t0` lasting `1/fps`. Otherwise, with
    `n = max(1, floor(d · fps + 0.5))`, a looping clip has `n` frames and a
    one-shot clip `n + 1`, at `t0 + k·d/n`, each lasting `d/n`. A one-shot
    clip's last sample is `t1` itself, which `t0 + n·d/n` can miss by rounding.
    """
    if not (math.isfinite(fps) and fps > 0):
        raise ValueError(f"fps must be finite and greater than 0, got {fps!r}")
    clip = selected.clip
    if clip.animation_index is None:
        return Sampling(1, (0.0,), 1 / fps)
    duration = clip.t1 - clip.t0
    if duration == 0:
        return Sampling(1, (clip.t0,), 1 / fps)
    n = max(1, math.floor(duration * fps + 0.5))
    times = tuple(clip.t0 + k * duration / n for k in range(n))
    if selected.one_shot:
        times += (clip.t1,)
    return Sampling(len(times), times, duration / n)


def frames(subject, selected_clips, view, fps):
    """Every requested frame of `subject` (its name) in sheet order.

    Raises `ValueError` if two frames would share an address, such as two
    selected clips with one name.
    """
    directions = views.directions(view)
    result = []
    for selected in selected_clips:
        times = sample(selected, fps).times
        for direction in directions:
            for index, time_s in enumerate(times):
                address = FrameAddress(
                    subject, VARIANT, selected.clip.name, direction.index, time_s
                )
                result.append(Frame(address, index, direction.angle))
    seen = set()
    for frame in result:
        if frame.address in seen:
            raise ValueError(f"two requested frames share the address {frame.address}")
        seen.add(frame.address)
    return tuple(result)
