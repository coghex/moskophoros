"""The request plan: each selected clip's effective timing, stored directions
and logical mirrors, with the addressed frames they make.

This is a pure planner, preparatory to the export arc (design §Clips and
sampling). It reads no file, imports no Blender and mutates nothing, and it
reuses `sampling.sample` and `views.directions` rather than restating their
rules. Settings parsing, layer merging and warnings are the caller's: the
planner takes resolved values and raises `ValueError`, naming the clip or the
global setting and the offending index or pair, when they do not fit the view.

With the global values alone (every direction stored, no mirrors, no
overrides) the plan's frames equal `sampling.frames`.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from moskophoros import sampling, views

# The `stored_directions` value selecting the whole original ring.
ALL = "all"


@dataclass(frozen=True)
class ClipOverride:
    """One clip's own resolved values; None inherits the global value.

    `fps` replaces the global FPS. `stored_directions` is `ALL` or an ordered
    list of original direction indices, and replaces the global selection
    wholesale. `mirrors` maps target index to stored source index and replaces
    the global map wholesale: an empty map disables inherited mirrors. A
    clip's own frame count stays on its `gltf.SelectedClip`.
    """

    fps: float | None = None
    stored_directions: object = None
    mirrors: Mapping[int, int] | None = None


@dataclass(frozen=True)
class MirrorPair:
    """A logical mirror: direction `target` is not captured and is to be
    taken from the stored direction `source`. Original indices both."""

    target: int
    source: int


@dataclass(frozen=True)
class ClipPlan:
    """One selected clip's effective values and real frames.

    `directions` are the stored directions in configured order, each as the
    original ring has it. `frames` run over them in that order, then in
    sample order; the mirrors add none.
    """

    selected: object
    fps: float
    sampling: sampling.Sampling
    directions: tuple[views.Direction, ...]
    mirrors: tuple[MirrorPair, ...]
    frames: tuple[sampling.Frame, ...]


@dataclass(frozen=True)
class RequestPlan:
    """The selected clips' plans in selection order, and every real frame."""

    clips: tuple[ClipPlan, ...]
    frames: tuple[sampling.Frame, ...]


def plan(
    subject,
    selected_clips,
    view,
    fps,
    frame_count=sampling.AUTO,
    stored_directions=ALL,
    mirrors=None,
    overrides=None,
):
    """The plan for `selected_clips` of `subject` (its name) in `view`.

    `fps`, `frame_count` (as `sampling.sample` takes it), `stored_directions`
    and `mirrors` are the global values; `overrides` maps a source clip name
    to its `ClipOverride`. An override for a clip that is not selected is
    ignored. The global directions and mirrors are checked against the view
    even when every clip overrides them; whether a mirror's source is stored
    and its target omitted is checked on each clip's effective values.

    Raises `ValueError` for an unusable value, or if two frames would share an
    address.
    """
    ring = views.directions(view)
    _check_fps(fps, "global fps")
    global_stored = _stored(stored_directions, ring, "global stored_directions")
    global_mirrors = _mirror_pairs(mirrors, ring, "global mirrors")
    overrides = {} if overrides is None else overrides

    clips = []
    for selected in selected_clips:
        name = selected.clip.name
        own = overrides.get(name, ClipOverride())
        where = f"clip {name!r}"
        clip_fps = fps
        if own.fps is not None:
            _check_fps(own.fps, f"{where} fps")
            clip_fps = own.fps
        if own.stored_directions is None:
            stored = global_stored
        else:
            stored = _stored(own.stored_directions, ring, f"{where} stored_directions")
        if own.mirrors is None:
            pairs = global_mirrors
        else:
            pairs = _mirror_pairs(own.mirrors, ring, f"{where} mirrors")
        _check_mirrors(pairs, stored, where)
        try:
            timing = sampling.sample(selected, clip_fps, frame_count)
        except ValueError as error:
            raise ValueError(f"{where}: {error}") from None
        clip_frames = tuple(
            sampling.Frame(
                sampling.FrameAddress(
                    subject, sampling.VARIANT, name, direction.index, time_s
                ),
                index,
                direction.angle,
            )
            for direction in stored
            for index, time_s in enumerate(timing.times)
        )
        clips.append(ClipPlan(selected, clip_fps, timing, stored, pairs, clip_frames))

    every = tuple(frame for clip in clips for frame in clip.frames)
    sampling.refuse_shared_addresses(every)
    return RequestPlan(tuple(clips), every)


def _is_index(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_fps(value, where):
    ok = isinstance(value, int | float) and not isinstance(value, bool)
    if not (ok and math.isfinite(value) and value > 0):
        raise ValueError(f"{where} must be finite and greater than 0, got {value!r}")


def _check_index(value, ring, where):
    if not _is_index(value):
        raise ValueError(f"{where}: {value!r} is not a direction index")
    if not 0 <= value < len(ring):
        raise ValueError(
            f"{where}: index {value} is not in the view's {len(ring)} directions"
        )


def _stored(value, ring, where):
    """The directions `value` selects, in its order."""
    if isinstance(value, str):
        if value != ALL:
            raise ValueError(f"{where}: expected {ALL!r} or a list, got {value!r}")
        return ring
    try:
        indices = tuple(value)
    except TypeError:
        raise ValueError(
            f"{where}: expected {ALL!r} or a list, got {value!r}"
        ) from None
    if not indices:
        raise ValueError(f"{where}: the list of directions is empty")
    seen = set()
    for index in indices:
        _check_index(index, ring, where)
        if index in seen:
            raise ValueError(f"{where}: index {index} is listed twice")
        seen.add(index)
    return tuple(ring[index] for index in indices)


def _mirror_pairs(value, ring, where):
    """The pairs of the target-to-source map `value`, by target index."""
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError(f"{where}: expected a map of target to source, got {value!r}")
    for target, source in value.items():
        _check_index(target, ring, f"{where} target")
        _check_index(source, ring, f"{where} source")
    return tuple(MirrorPair(target, value[target]) for target in sorted(value))


def _check_mirrors(pairs, stored, where):
    """Every source is stored and every target omitted, so a chain or a
    self-mirror, which makes one index both, cannot qualify."""
    kept = {direction.index for direction in stored}
    for pair in pairs:
        if pair.source not in kept:
            raise ValueError(
                f"{where} mirrors: source {pair.source} of target {pair.target} "
                "is not a stored direction"
            )
        if pair.target in kept:
            raise ValueError(
                f"{where} mirrors: target {pair.target} (source {pair.source}) "
                "is a stored direction, not omitted"
            )
