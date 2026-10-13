"""Sample times and frame addresses, following design §Clips and sampling.

A frame's address (`subject`, `variant`, `clip`, `direction`, `time_s`) is
its identity in every stage. `frames` enumerates a request in sheet order:
clips in selection order, then directions in index order, then samples in
time order. Everything here is pure.

After capture, stages pass `ImageFrame`s: an address, its pixels, the
metadata attached to it and any further named buffers. `IDENTITY`, `SHADE`,
`NORMAL`, `DEPTH`, `BACKGROUND` and `Identities` define the identity, shade,
normal and depth buffers stylize receives beside the colour (design
§Pipeline, Frames into stylize).
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from moskophoros import views

# Slice 1 has one variant.
VARIANT = "default"

# The names of a frame's identity, shade, normal and depth buffers.
IDENTITY = "identity"
SHADE = "shade"
NORMAL = "normal"
DEPTH = "depth"

# The identity array's value where no surface was hit; never an index.
BACKGROUND = -1


# A frame count that leaves sampling to the clip's duration.
AUTO = "auto"


@dataclass(frozen=True)
class Sampling:
    """One clip's samples: `times` in seconds, each lasting `frame_duration`,
    and `time_scale`, the retiming factor (settings design D-33): 1 for
    automatic sampling and for one frame."""

    frame_count: int
    times: tuple[float, ...]
    frame_duration: float
    time_scale: float = 1.0


def count(selected, frames=AUTO):
    """The frame count `selected` samples with, or None for automatic
    sampling: its own count or `"auto"`, else the global `frames` (settings
    design D-26, D-31)."""
    own = frames if selected.frames is None else selected.frames
    return None if own == AUTO else own


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

    `buffers` maps names to the frame's further per-frame arrays, of the
    same height and width as `pixels`; only frames going into stylize carry
    any. Under `IDENTITY`, an `int32` array of shape `(height, width)` holds
    each pixel's index into the asset's `Identities`, or `BACKGROUND`; under
    `SHADE`, a `uint8` array of shape `(height, width)` holds its shade.
    Under `NORMAL`, a `float32` array of shape `(height, width, 3)` holds the
    unit normal of the surface each pixel sampled, in the frame's camera
    space (+X screen right, +Y screen up, +Z toward the viewer), or
    `(0, 0, 0)` where no surface was hit; under `DEPTH`, a `float32` array
    of shape `(height, width)` holds that surface's depth in meters, positive
    toward the viewer from the ground point's camera depth, or NaN where no
    surface was hit. The command decodes and validates them; stylize trusts
    them. A buffer under any other name is a capture buffer as loaded, an
    image like `pixels`.
    """

    address: FrameAddress
    pixels: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)
    buffers: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Identities:
    """An asset's identity list, which a frame's `IDENTITY` array indexes.

    `names` are the distinct names of its eligible (`OPAQUE` or `MASK`)
    materials, each placed by its lowest glTF material index. The list is
    `names` followed by the no-identity class, so index `i` names `names[i]`
    for `i < len(names)`, and `no_identity`, which is `len(names)`, is the
    no-identity class.
    """

    names: tuple[str, ...]

    @property
    def no_identity(self):
        return len(self.names)

    def __len__(self):
        return len(self.names) + 1


def sample(selected, fps, frames=AUTO):
    """The samples of `selected`, a `gltf.SelectedClip`, at target `fps`,
    with `frames` the global frame count as given.

    The synthetic `static` clip, which has no animation index, and any clip of
    zero duration have one frame at `t0` lasting `1/fps`, whatever its count
    (settings design D-25). A clip whose count resolves to `"auto"` (`count`)
    samples by duration: with `n = max(1, floor(d · fps + 0.5))`, a looping
    clip has `n` frames and a one-shot clip `n + 1`, at `t0 + k·d/n`, each
    lasting `d/n`. A one-shot clip's last sample is `t1` itself, which
    `t0 + n·d/n` can miss by rounding.

    With a count `N` (settings design D-13, D-33, D-38), every frame lasts
    exactly `1/fps`: a looping clip samples `t0 + k·d/N` and a one-shot clip
    `t0 + k·d/(N − 1)` for k = 0 … N − 1, its last sample `t1` itself, with
    `time_scale` `d·fps/N` or `d·fps/(N − 1)`; `N` = 1 is a still, one frame
    at `t0` with `time_scale` 1.
    """
    if not (math.isfinite(fps) and fps > 0):
        raise ValueError(f"fps must be finite and greater than 0, got {fps!r}")
    clip = selected.clip
    if clip.animation_index is None:
        return Sampling(1, (0.0,), 1 / fps)
    duration = clip.t1 - clip.t0
    if duration == 0:
        return Sampling(1, (clip.t0,), 1 / fps)
    given = count(selected, frames)
    if given is not None:
        if isinstance(given, bool) or not isinstance(given, int) or given < 1:
            raise ValueError(f"a frame count must be 1 or more, got {given!r}")
        if given == 1:
            return Sampling(1, (clip.t0,), 1 / fps)
        steps = given if not selected.one_shot else given - 1
        times = tuple(clip.t0 + k * duration / steps for k in range(steps))
        if selected.one_shot:
            times += (clip.t1,)
        return Sampling(given, times, 1 / fps, duration * fps / steps)
    n = max(1, math.floor(duration * fps + 0.5))
    times = tuple(clip.t0 + k * duration / n for k in range(n))
    if selected.one_shot:
        times += (clip.t1,)
    return Sampling(len(times), times, duration / n)


def frames(subject, selected_clips, view, fps, frame_count=AUTO):
    """Every requested frame of `subject` (its name) in sheet order, with
    `frame_count` the global frame count as given.

    Raises `ValueError` if two frames would share an address, such as two
    selected clips with one name.
    """
    directions = views.directions(view)
    result = []
    for selected in selected_clips:
        times = sample(selected, fps, frame_count).times
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
