"""A cubic spline animation whose accessor does not fit its buffer view,
through the launcher and the whole command on generated models, in real
Blender.

The expected values are worked out here from glTF's own rules (the cubic
spline formula and the data-alignment rule that an accessor fits its buffer
view), independently of the script.
"""

import pytest
from glb_writer import GlbWriter
from test_measure import TIMES, assert_close, boxes, measure

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

ONCE_TIMES = [*TIMES, 1.0]
ZERO = (0.0, 0.0, 0.0)
FAST = ["--supersample", "2", "--cell", "16x16", "--fps", "4"]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def walk_model(*, shrink_output_to=None):
    """A triangle whose translation goes from (0, 0, 0) to (1, 0, 0) over 0 to
    1 s on a cubic spline with zero tangents, so x(t) = 3t² − 2t³. The
    output is six VEC3 rows, 72 bytes. Another accessor follows it in the
    buffer, so its bytes are present beyond a shrunken view."""
    model = GlbWriter()
    shape = model.node("shape", mesh=True)
    model.scene([shape], default=True)
    keys = [ZERO, ZERO, ZERO, ZERO, (1.0, 0.0, 0.0), ZERO]
    model.animation(
        "walk", [(shape, "translation", [0.0, 1.0], keys)], interpolation="CUBICSPLINE"
    )
    model._accessor("VEC3", [ZERO] * 8, False)
    if shrink_output_to is not None:
        sampler = model.document["animations"][0]["samplers"][0]
        output = model.document["accessors"][sampler["output"]]
        model.document["bufferViews"][output["bufferView"]]["byteLength"] = (
            shrink_output_to
        )
    return model


def expected_boxes():
    return [(0.0, 1.0 + 3 * t * t - 2 * t**3, 1.0, 0.0) for t in ONCE_TIMES]


def test_a_cubic_output_in_a_view_that_ends_at_its_last_row_follows_its_spline(
    found, tmp_path
):
    result, _ = measure(
        found,
        walk_model(shrink_output_to=72).write(tmp_path, "walk"),
        tmp_path,
        clip_names=["walk"],
        once=["walk"],
    )
    assert_close(boxes(result)["walk"], expected_boxes())


def test_a_cubic_output_in_a_twelve_byte_view_fails_with_exit_5(found, tmp_path):
    path = walk_model(shrink_output_to=12).write(tmp_path, "walk")
    with pytest.raises(backend.BackendError) as raised:
        measure(found, path, tmp_path, clip_names=["walk"], once=["walk"])
    assert raised.value.exit_code == 5
    message = str(raised.value)
    assert str(path) in message
    assert "animation 0's sampler 0" in message
    assert "accessor" in message
    assert "buffer view" in message


def test_the_whole_command_publishes_nothing_for_an_unreadable_cubic_view(
    capsys, found, tmp_path
):
    model = walk_model(shrink_output_to=12).write(tmp_path, "walk")
    out = tmp_path / "out"
    out.mkdir()
    (out / "walk.png").write_bytes(b"an earlier sheet")
    status = cli.run(
        [*FAST, "--blender", str(found.path), str(model), str(out / "walk.png")]
    )
    err = capsys.readouterr().err
    assert status == 5
    assert str(model) in err
    assert "animation 0's sampler 0" in err
    assert sorted(path.name for path in out.iterdir()) == ["walk.png"]
    assert (out / "walk.png").read_bytes() == b"an earlier sheet"
