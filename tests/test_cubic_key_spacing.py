"""Closely spaced CUBICSPLINE keys are an input error (design §Input contract).

Blender keeps keys no closer than 0.01 frame at its 24 frames per second scene
rate, as 32-bit floats; the tool refuses a cubic spline closer than that
before Blender starts. Models are generated here.
"""

import base64
import struct

import pytest
from glb_writer import GlbWriter
from test_command import Setup, run

from moskophoros import keytimes
from moskophoros.gltf import InputError, read_glb

FRAME = 1 / keytimes.BLENDER_FRAME_RATE
FLAT = (0.0, 0.0, 0.0)


def _model(times, path="translation", interpolation="CUBICSPLINE", name="sway"):
    """One node with a `path` channel whose keys are at `times`."""
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    width = {"translation": 3, "scale": 3, "rotation": 4, "weights": 1}[path]
    still = (0.0,) * width
    if interpolation == "CUBICSPLINE":
        values = [still] * (3 * len(times))
    else:
        values = [still] * len(times)
    model.animation(name, [(node, path, times, values)], interpolation=interpolation)
    return model


def _gap(frames):
    """Key times, in seconds, with `frames` Blender frames between the last two."""
    return [0.0, 1.0, 1.0 + frames * FRAME]


def test_the_threshold_is_blenders_resolution_at_its_scene_rate():
    assert keytimes.BLENDER_FRAME_RATE == 24.0
    assert keytimes.MIN_KEY_SPACING_FRAMES == 0.01


@pytest.mark.parametrize("frames", [0.0001, 0.005, 0.0099, 0.01])
def test_keys_no_further_apart_than_blender_resolves_are_refused(tmp_path, frames):
    path = _model(_gap(frames)).write(tmp_path)
    with pytest.raises(InputError) as raised:
        read_glb(path)
    assert raised.value.exit_code == 3
    message = str(raised.value)
    assert message.startswith(
        f"{path}: clip 'sway' (animation 0), channel 0 "
        "(translation of node 0) has a CUBICSPLINE sampler whose keys 1 and 2, at "
        "1.0 s and "
    )
    assert "Blender frame(s) apart as Blender stores them" in message
    assert "0.01 frame (0.4167 ms)" in message


@pytest.mark.parametrize("frames", [0.0101, 0.0102, 0.05, 1.0, 24.0])
def test_keys_just_outside_the_limit_are_accepted(tmp_path, frames):
    (clip,) = read_glb(_model(_gap(frames)).write(tmp_path)).clips
    assert clip.name == "sway"


@pytest.mark.parametrize("path", ["translation", "rotation", "scale", "weights"])
def test_every_evaluated_path_is_checked(tmp_path, path):
    model = _model(_gap(0.005), path)
    with pytest.raises(InputError, match=rf"\({path} of node 0\)"):
        read_glb(model.write(tmp_path))


@pytest.mark.parametrize("interpolation", ["LINEAR", "STEP"])
def test_other_interpolations_behave_as_before(tmp_path, interpolation):
    model = _model([0.0, 1.0, 1.0 + 0.001 * FRAME], interpolation=interpolation)
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert clip.name == "sway"


@pytest.mark.parametrize(
    "pointer",
    ["/meshes/0/weights", "/nodes/0/weights", "/nodes/0/translation"],
)
def test_pointer_channels_that_are_evaluated_are_checked(tmp_path, pointer):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("swell", [])
    times = _gap(0.005)
    width = 3 if pointer.endswith("translation") else 1
    model.pointer_channel(
        clip,
        pointer,
        times,
        [(0.0,) * width] * (3 * len(times)),
        interpolation="CUBICSPLINE",
    )
    with pytest.raises(InputError) as raised:
        read_glb(model.write(tmp_path))
    assert f"channel 0 (pointer {pointer})" in str(raised.value)


@pytest.mark.parametrize(
    "pointer",
    [
        "/cameras/0/perspective/yfov",
        "/extensions/KHR_lights_punctual/lights/0/intensity",
    ],
)
def test_camera_and_light_pointers_have_no_effect_so_are_not_checked(tmp_path, pointer):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("swell", [])
    times = _gap(0.005)
    model.pointer_channel(
        clip, pointer, times, [(0.0,)] * (3 * len(times)), interpolation="CUBICSPLINE"
    )
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert clip.name == "swell"


def test_the_clip_and_channel_of_the_offending_sampler_are_named(tmp_path):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    good = [0.0, 1.0]
    model.animation(
        "fine",
        [(node, "translation", good, [FLAT] * 6)],
        interpolation="CUBICSPLINE",
    )
    other = model.animation(
        "tight",
        [(node, "translation", good, [FLAT] * 6)],
        interpolation="CUBICSPLINE",
    )
    # Channel 1 of the second animation is the offender.
    tight = _gap(0.002)
    model.pointer_channel(
        other, "/nodes/0/weights", tight, [(0.0,)] * 9, interpolation="CUBICSPLINE"
    )
    with pytest.raises(InputError) as raised:
        read_glb(model.write(tmp_path))
    assert "clip 'tight' (animation 1), channel 1 (pointer /nodes/0/weights)" in str(
        raised.value
    )


def test_a_shared_sampler_is_reported_once_for_its_first_channel(tmp_path):
    model = _model(_gap(0.004))
    channels = model.document["animations"][0]["channels"]
    channels.append({"sampler": 0, "target": {"node": 0, "path": "scale"}})
    with pytest.raises(InputError) as raised:
        read_glb(model.write(tmp_path))
    assert "channel 0 (translation of node 0)" in str(raised.value)


@pytest.mark.parametrize("times", [[0.0, 0.5, 0.5], [0.0, 1.0, 0.5], [2.0, 1.0]])
def test_keys_that_do_not_increase_are_refused(tmp_path, times):
    with pytest.raises(InputError, match="do not increase in time"):
        read_glb(_model(times).write(tmp_path))


def test_the_limit_applies_to_times_as_blender_stores_them():
    # 100 s is frame 2400, where 32-bit floats are 2.4e-4 frame apart: keys a
    # microsecond apart are the same float, and 0.006 frame is 25 steps.
    index, text = keytimes.spacing_problem([0.0, 100.0, 100.0 + 1e-6])
    assert index == 1
    assert "0 Blender frame(s) apart as Blender stores them" in text
    index, text = keytimes.spacing_problem([0.0, 100.0, 100.0 + 0.006 * FRAME])
    assert index == 1
    assert "0.00610352 Blender frame(s) apart" in text


def test_a_pair_that_32_bit_rounding_spreads_apart_is_judged_as_stored():
    # 0.0099 frame requested, 0.0100098 stored at frame 2400: outside the limit.
    assert keytimes.spacing_problem([0.0, 100.0, 100.0 + 0.0099 * FRAME]) is None


def test_a_file_whose_equal_32_bit_times_cannot_be_told_apart_is_refused(tmp_path):
    # Times are stored as 32-bit floats: 100 s and 100 s plus a microsecond are one.
    with pytest.raises(InputError, match="do not increase in time"):
        read_glb(_model([0.0, 100.0, 100.0 + 1e-6]).write(tmp_path))


def test_keys_exactly_at_the_limit_are_refused_and_just_beyond_it_are_not():
    # Blender merges keys no further apart than its 32-bit 0.01 frame.
    at = keytimes.float32(0.01) / 24
    assert keytimes.spacing_problem([0.0, at]) is not None
    assert keytimes.spacing_problem([0.0, 0.0100001 / 24]) is None


# Reading the key times


def _document(data, accessor, views=None):
    document = {
        "buffers": [{"byteLength": len(data)}],
        "bufferViews": views or [{"buffer": 0, "byteLength": len(data)}],
        "accessors": [accessor],
    }
    return document, (lambda index: data)


def _floats(*values):
    return struct.pack(f"<{len(values)}f", *values)


def test_times_are_read_with_an_offset_and_a_stride():
    data = _floats(9, 0.5, 9, 9, 1.5, 9, 9, 2.5)
    # The view starts 4 bytes in; rows are 12 bytes apart.
    document, fetch = _document(
        data,
        {
            "bufferView": 0,
            "byteOffset": 4,
            "componentType": 5126,
            "count": 3,
            "type": "SCALAR",
        },
        [{"buffer": 0, "byteOffset": 0, "byteStride": 12, "byteLength": len(data)}],
    )
    assert keytimes.sampler_times(document, fetch, 0) == [0.5, 1.5, 2.5]


def test_sparse_replacements_are_applied():
    data = _floats(0, 1, 2, 3) + struct.pack("<H", 2) + _floats(7.5)
    document, fetch = _document(
        data,
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": 4,
            "type": "SCALAR",
            "sparse": {
                "count": 1,
                "indices": {"bufferView": 1, "componentType": 5123},
                "values": {"bufferView": 2},
            },
        },
        [
            {"buffer": 0, "byteOffset": 0, "byteLength": 16},
            {"buffer": 0, "byteOffset": 16, "byteLength": 2},
            {"buffer": 0, "byteOffset": 18, "byteLength": 4},
        ],
    )
    assert keytimes.sampler_times(document, fetch, 0) == [0.0, 1.0, 7.5, 3.0]


def test_a_sparse_accessor_without_a_buffer_view_starts_at_zero():
    data = struct.pack("<B", 1) + _floats(2.0)
    document, fetch = _document(
        data,
        {
            "componentType": 5126,
            "count": 3,
            "type": "SCALAR",
            "sparse": {
                "count": 1,
                "indices": {"bufferView": 0, "componentType": 5121},
                "values": {"bufferView": 1},
            },
        },
        [
            {"buffer": 0, "byteOffset": 0, "byteLength": 1},
            {"buffer": 0, "byteOffset": 1, "byteLength": 4},
        ],
    )
    assert keytimes.sampler_times(document, fetch, 0) == [0.0, 2.0, 0.0]


@pytest.mark.parametrize(
    "accessor",
    [
        {"bufferView": 0, "componentType": 5126, "count": 9, "type": "SCALAR"},
        {"bufferView": 0, "componentType": 5126, "count": 2, "type": "VEC3"},
        {"bufferView": 0, "componentType": 5123, "count": 2, "type": "SCALAR"},
        {"bufferView": 1, "componentType": 5126, "count": 2, "type": "SCALAR"},
        {"bufferView": 0, "componentType": 5126, "count": True, "type": "SCALAR"},
        {"bufferView": 0, "componentType": 5126, "count": -1, "type": "SCALAR"},
        {"bufferView": 0, "componentType": 5126, "count": 10**9, "type": "SCALAR"},
        {"bufferView": 0, "componentType": 5126, "count": 2},
    ],
    ids=[
        "past the data",
        "not scalar",
        "not float",
        "no such view",
        "bool count",
        "negative count",
        "huge count",
        "no type",
    ],
)
def test_an_unreadable_accessor_gives_none(accessor):
    document, fetch = _document(_floats(0.0, 1.0), accessor)
    assert keytimes.sampler_times(document, fetch, 0) is None


def test_a_sparse_index_past_the_count_gives_none():
    data = struct.pack("<B", 9) + _floats(2.0)
    document, fetch = _document(
        data,
        {
            "componentType": 5126,
            "count": 3,
            "type": "SCALAR",
            "sparse": {
                "count": 1,
                "indices": {"bufferView": 0, "componentType": 5121},
                "values": {"bufferView": 1},
            },
        },
        [
            {"buffer": 0, "byteOffset": 0, "byteLength": 1},
            {"buffer": 0, "byteOffset": 1, "byteLength": 4},
        ],
    )
    assert keytimes.sampler_times(document, fetch, 0) is None


def test_non_finite_times_give_none():
    document, fetch = _document(
        _floats(0.0, float("inf")),
        {"bufferView": 0, "componentType": 5126, "count": 2, "type": "SCALAR"},
    )
    assert keytimes.sampler_times(document, fetch, 0) is None


def test_a_missing_accessor_gives_none():
    document, fetch = _document(b"", {"componentType": 5126})
    assert keytimes.sampler_times(document, fetch, 4) is None


def test_spacing_of_zero_and_one_key():
    assert keytimes.spacing_problem([]) is None
    assert keytimes.spacing_problem([3.0]) is None


# Models whose data is not in the GLB's binary chunk


def _tight_model(tmp_path):
    return _model(_gap(0.004))


def test_a_data_uri_buffer_is_checked(tmp_path):
    model = _tight_model(tmp_path)
    blob = bytes(model._binary)
    model.document["buffers"][0]["uri"] = (
        "data:application/octet-stream;base64," + base64.b64encode(blob).decode()
    )
    with pytest.raises(InputError, match="Blender frame"):
        read_glb(model.write(tmp_path))


def test_an_external_buffer_is_checked(tmp_path):
    model = _tight_model(tmp_path)
    (tmp_path / "data 1.bin").write_bytes(bytes(model._binary))
    model.document["buffers"][0]["uri"] = "data%201.bin"
    with pytest.raises(InputError, match="Blender frame"):
        read_glb(model.write(tmp_path))


def test_an_unreadable_buffer_is_left_to_the_capture(tmp_path):
    model = _tight_model(tmp_path)
    model.document["buffers"][0]["uri"] = "missing.bin"
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert clip.name == "sway"


# The command: the refusal comes before Blender starts


def test_the_command_refuses_before_starting_blender(tmp_path, capsys):
    setup = Setup(tmp_path)
    setup.model.unlink()
    setup.model = _model(_gap(0.005), name="walk").write(setup.model.parent, "hero")
    status, out, err = run(capsys, setup.argv())
    assert status == 3
    assert out == ""
    assert err.startswith(
        f"moskophoros: error: {setup.model}: clip 'walk' (animation 0), channel 0 "
        "(translation of node 0) has a CUBICSPLINE sampler whose keys 1 and 2, at "
    )
    assert setup.calls() == []
    assert setup.listing() == {}
