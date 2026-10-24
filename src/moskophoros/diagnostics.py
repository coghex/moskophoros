"""Warnings the export preparation builds, as text, for the command to emit
later (export design P-7 part 1 and P-8 part 2; D-17).

`fps_warnings` names the clips whose own `fps` shadows a global one the user
gave. `mirror_warnings` tests each requested mirror against the camera
conditions under which a horizontal flip is a geometric reflection. Both only
build messages: they emit nothing, and the planned work is unchanged.
Everything here is pure.
"""

import json
import math
from dataclasses import dataclass

from moskophoros import exportsettings, views

# How near zero the angle sum and the sideways offset must be to count as
# zero. Direction angles are floats, `views.directions` wrapping
# `start + index * 360 / count`, so a sum that is exactly 360 in theory can
# land a few ulps (about 6e-14 degrees at 360) off; a tolerance this much
# larger than that and far smaller than any real offset keeps rounding from
# creating or hiding a warning. The offset is compared with the horizontal
# distance of the camera, at least 1 meter, so it scales with the position.
ANGLE_TOLERANCE_DEG = 1e-9
OFFSET_TOLERANCE = 1e-9


def fps_warnings(resolved, selected_clips):
    """The warnings for selected clips whose own `fps` shadows the global one.

    Only a global `fps` that the command line or a project file gave warns:
    one warning lists every selected clip with its own `fps`, even an equal
    one, and a still clip too, because its frame duration uses the rate. A
    default, a global file's or a reused sheet's `fps`, and an entry for a
    clip that is not selected, give none.
    """
    if resolved.fps_kind not in (exportsettings.OPTION, exportsettings.PROJECT):
        return ()
    own = []
    for item in selected_clips:
        clip = resolved.clips.get(item.clip.name)
        if clip is not None and clip.fps is not None:
            own.append(f"{json.dumps(item.clip.name, ensure_ascii=False)} ({clip.fps})")
    if not own:
        return ()
    return (
        f"the global fps {resolved.fps} does not reach the clips with their own: "
        f"{', '.join(own)}",
    )


@dataclass(frozen=True)
class MirrorWarning:
    """A requested mirror whose camera conditions fail: `clip` is the source
    clip name, `target` and `source` the original direction indices, and
    `failed` each failed condition in words."""

    clip: str
    target: int
    source: int
    failed: tuple[str, ...]

    @property
    def message(self):
        return (
            f"clip {json.dumps(self.clip, ensure_ascii=False)} mirror "
            f"{self.target} <- {self.source} is not a reflection: "
            + "; ".join(self.failed)
        )


def mirror_warnings(
    request_plan, view, *, roll=0.0, projection="orthographic", direction, position=None
):
    """One `MirrorWarning` for each clip and mirror pair of `request_plan`
    whose horizontal flip is not a geometric reflection, in plan order.

    The conditions are necessary ones, not a claim that the subject or its
    lighting is symmetric. The roll must be 0 or ±1 (half turns). With
    `theta = (start + i * 360 / N) mod 360` the direction angles, `theta`
    of the target plus `theta` of the source must be congruent to 0 modulo
    360, within `ANGLE_TOLERANCE_DEG`; the model's facing correction does
    not enter. A perspective camera's `position` must lie in the vertical
    plane through the ground point along the camera's heading, its sideways
    offset within `OFFSET_TOLERANCE` of the horizontal distance (at least 1
    m); the orthographic camera's position is unused. A pair that fails
    several conditions gives one warning listing them all.
    """
    angle = {d.index: d.angle for d in views.directions(view)}
    failed_camera = []
    if roll not in (0, 1, -1):
        failed_camera.append(f"the camera roll {roll} is not 0, 1 or -1 half turns")
    offset = None
    if projection == "perspective" and position is not None:
        side = views.camera_basis(direction, 0.0).right
        sideways = sum(p * r for p, r in zip(position, side, strict=True))
        scale = max(1.0, math.hypot(position[0], position[2]))
        if abs(sideways) > OFFSET_TOLERANCE * scale:
            offset = sideways
    if offset is not None:
        failed_camera.append(
            f"the perspective camera is {offset:.6g} m to the side of its heading plane"
        )
    warnings = []
    for clip in request_plan.clips:
        for pair in clip.mirrors:
            failed = []
            total = (angle[pair.target] + angle[pair.source]) % 360
            if min(total, 360 - total) > ANGLE_TOLERANCE_DEG:
                failed.append(
                    f"the direction angles {angle[pair.target]} and "
                    f"{angle[pair.source]} do not sum to 0 modulo 360"
                )
            failed += failed_camera
            if failed:
                warnings.append(
                    MirrorWarning(
                        clip.selected.clip.name, pair.target, pair.source, tuple(failed)
                    )
                )
    return tuple(warnings)
