"""Root motion driven through a `KHR_animation_pointer` node pointer, measured
and refused through the whole command, in real Blender.

A triangle node `walker` walks 1 m along x in one second, on a cubic spline
with zero tangents, so its position is the smoothstep 3s² − 2s³ of the time
s: the form of ordinary `translation` channel and the form of a
`/nodes/0/translation` pointer must agree on the root, on the 1 m travel
between the clip's endpoints and on the default refusal. Every expected value
is worked out here from glTF's cubic formula and the fixture's geometry,
independently of the script.
"""

import re
import shutil

import pytest
from glb_writer import GlbWriter
from test_measure import TIMES, assert_close, boxes, by_clip, measure

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

ZERO = (0.0, 0.0, 0.0)
# An in-tangent, a value and an out-tangent for each of the keys at 0 s and
# 1 s, all tangents zero.
KEYS = [ZERO, ZERO, ZERO, ZERO, (1.0, 0.0, 0.0), ZERO]
FORMS = ["ordinary", "pointer"]
FAST = ["--supersample", "2", "--cell", "16x16", "--fps", "4", "--directions", "1"]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def walker(directory, form, *, stem="walker", keys=KEYS, interpolation="CUBICSPLINE"):
    """`walker.glb`: node 0, `walker`, walks `keys` as a `translation`
    channel (`ordinary`) or a `/nodes/0/translation` pointer (`pointer`)."""
    model = GlbWriter()
    node = model.node("walker", mesh=True, translation=ZERO)
    model.scene([node], default=True)
    if form == "ordinary":
        model.animation(
            "walk",
            [(node, "translation", [0, 1], keys)],
            interpolation=interpolation,
        )
    else:
        clip = model.animation("walk", [])
        model.pointer_channel(
            clip,
            f"/nodes/{node}/translation",
            [0, 1],
            keys,
            interpolation=interpolation,
            kind="VEC3",
        )
    return model.write(directory, stem)


def smoothstep(t):
    """glTF's cubic spline from 0 to 1 with zero tangents, at time `t` of 1 s."""
    return -2 * t**3 + 3 * t**2


def run(capsys, found, model, out, *options):
    status = cli.run(
        [*FAST, *options, "--blender", str(found.path), str(model), str(out)]
    )
    _, err = capsys.readouterr()
    return status, err


def listing(directory):
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


@pytest.mark.parametrize("form", FORMS)
def test_the_endpoint_travel_is_measured_whatever_the_stored_frames(
    found, tmp_path, form
):
    # The loop at 4 fps stores 0, 0.25, 0.5 and 0.75 s: never its endpoint,
    # at which the root stands 1 m from where it started.
    path = walker(tmp_path, form)
    result, job = measure(found, path, tmp_path)
    assert [(r["node_index"], r["node_name"]) for r in job["clips"][0]["roots"]] == [
        (0, "walker")
    ]
    assert [t for _, t, _, _ in by_clip(result)["walk"]] == TIMES
    assert_close(
        boxes(result)["walk"], [(0.0, 1.0 + smoothstep(t), 1.0, 0.0) for t in TIMES]
    )
    assert max(smoothstep(t) for t in TIMES) < 0.9
    assert [(r.clip, r.node_index, r.node_name) for r in result.roots] == [
        ("walk", 0, "walker")
    ]
    assert result.roots[0].travel_m == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize("form", FORMS)
def test_a_one_shot_clip_travels_the_same_metre(found, tmp_path, form):
    result, _ = measure(
        found, walker(tmp_path, form), tmp_path, clip_names=["walk"], once=["walk"]
    )
    assert result.roots[0].travel_m == pytest.approx(1.0, abs=1e-5)
    assert_close(
        boxes(result)["walk"][-1:], [(0.0, 2.0, 1.0, 0.0)]
    )  # at t = 1 s, 1 m on


def test_a_linear_pointer_translation_is_a_root_too(found, tmp_path):
    # Not cubic: LINEAR keys of a VEC3 output, through the same pointer.
    keys = [ZERO, (1.0, 0.0, 0.0)]
    result, job = measure(
        found, walker(tmp_path, "pointer", keys=keys, interpolation="LINEAR"), tmp_path
    )
    assert [r["node_index"] for r in job["clips"][0]["roots"]] == [0]
    assert result.roots[0].travel_m == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize("form", FORMS)
def test_vertical_pointer_travel_is_allowed(found, tmp_path, form):
    keys = [ZERO, ZERO, ZERO, ZERO, (0.0, 1.0, 0.0), ZERO]
    result, _ = measure(found, walker(tmp_path, form, keys=keys), tmp_path)
    assert result.roots[0].travel_m == pytest.approx(0.0, abs=1e-5)
    cli.check_root_motion(tmp_path / "walker.glb", result.roots)


@pytest.mark.parametrize("form", FORMS)
def test_the_command_refuses_by_default_and_keeps_earlier_outputs(
    capsys, found, tmp_path, form
):
    model = walker(tmp_path, form)
    out = tmp_path / "out"
    out.mkdir()
    status, err = run(capsys, found, model, out / "walker.png", "--root-motion", "keep")
    assert status == 0, err
    earlier = listing(out)
    assert earlier

    status, err = run(capsys, found, model, out / "walker.png")
    assert status == 3
    message = re.search(
        r"clip 'walk' moves its root node 0 \('walker'\) ([0-9.e+-]+) m", err
    )
    assert message
    assert float(message[1]) == pytest.approx(1.0, abs=1e-5)
    assert err.startswith(f"moskophoros: error: {model}: ")
    assert "m across the ground, more than 0.02 m" in err
    assert "export the clip in place, or give --root-motion keep" in err
    assert listing(out) == earlier

    shutil.rmtree(out)
    out.mkdir()
    status, err = run(capsys, found, model, out / "walker.png")
    assert status == 3
    assert list(out.iterdir()) == []
