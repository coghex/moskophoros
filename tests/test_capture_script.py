"""The capture script's pure encoders, loaded without Blender: the shade
byte the `Standard` transform gives, and the material-ID AOV's codes and
coverage (alpha design, Capture transport and provenance). A refusal here
is the script's error, which fails the command with exit 5."""

import importlib.util
import math
import sys
import types
from array import array

import pytest

from moskophoros.capture import blender


@pytest.fixture(scope="module")
def script():
    """blender_script.py, with a stand-in for `bpy`, which only Blender has."""
    saved = sys.modules.get("bpy")
    sys.modules["bpy"] = types.ModuleType("bpy")
    try:
        spec = importlib.util.spec_from_file_location("capture_script", blender.SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if saved is None:
            del sys.modules["bpy"]
        else:
            sys.modules["bpy"] = saved
    return module


def srgb(value):
    if value <= 0.0031308:
        return 12.92 * value
    return 1.055 * value ** (1 / 2.4) - 0.055


def test_a_quarter_shade_is_137(script):
    assert script.shade_byte(0.25) == 137


@pytest.mark.parametrize(
    ("value", "byte"),
    [(0.0, 0), (1.0, 255), (-0.5, 0), (2.0, 255), (0.5, 188), (0.001, 3)],
)
def test_the_shade_byte_is_the_standard_transform_s(script, value, byte):
    assert script.shade_byte(value) == byte


def test_every_shade_byte_rounds_the_srgb_value_half_up(script):
    for step in range(1001):
        value = step / 1000
        assert script.shade_byte(value) == math.floor(255 * srgb(value) + 0.5)


CODES = {1, 2, 255, 256, 65535}


@pytest.mark.parametrize("value", [1.0, 256.0, 65535.0, 0.0])
def test_an_exact_code_is_read(script, value):
    assert script.material_code(value, CODES | {0}) == int(value)


@pytest.mark.parametrize(
    "value",
    [1.5, 0.9999999, 3.0, 65536.0, -1.0, math.nan, math.inf],
    ids=["half", "almost one", "unknown", "too large", "negative", "nan", "inf"],
)
def test_a_value_that_is_no_exact_code_is_refused(script, value):
    with pytest.raises(script.ScriptError, match="material-ID AOV holds"):
        script.material_code(value, CODES | {0})


def frame(ids, shades, alpha, width=2):
    covered = [
        bytes(255 if a else 0 for a in alpha[y : y + width])
        for y in range(0, len(alpha), width)
    ]
    return array("f", ids), array("f", shades), covered


def test_the_material_id_and_shade_rows(script):
    ids, shades, covered = frame(
        [0.0, 255.0, 256.0, 65535.0], [0.0, 0.25, 1.0, 0.5], [0, 1, 1, 1]
    )
    id_rows, shade_rows = script.id_and_shade_rows(
        ids, shades, covered, 2, CODES, "frame 0"
    )
    assert [bytes(row) for row in id_rows] == [
        bytes([0, 0, 0, 0, 0, 255, 0, 255]),
        bytes([1, 0, 0, 255, 255, 255, 0, 255]),
    ]
    assert [bytes(row) for row in shade_rows] == [
        bytes([0, 0, 0, 0, 137, 137, 137, 255]),
        bytes([255, 255, 255, 255, 188, 188, 188, 255]),
    ]


@pytest.mark.parametrize(
    ("ids", "alpha", "message"),
    [
        (
            [0.0, 1.0],
            [1, 1],
            r"material ID at pixel \(0, 0\) is 0, but the colour there shows a surface",
        ),
        (
            [1.0, 2.0],
            [1, 0],
            r"material ID at pixel \(1, 0\) is 2, but the colour there shows no surface",
        ),
        ([1.0, 2.5], [1, 1], "material-ID AOV holds 2.5"),
        ([1.0, 7.0], [1, 1], "material-ID AOV holds 7.0"),
    ],
)
def test_a_material_id_that_disagrees_or_is_no_code_is_refused(
    script, ids, alpha, message
):
    ids, shades, covered = frame(ids, [0.0, 0.0], alpha)
    with pytest.raises(script.ScriptError, match=message):
        script.id_and_shade_rows(ids, shades, covered, 2, CODES, "frame 0")


def test_coverage_accepts_only_whole_surfaces(script):
    assert script.coverage(array("f", [0.0, 1.0, 1.0, 0.0]), 2, "frame 0") == [
        bytes([0, 255]),
        bytes([255, 0]),
    ]
    with pytest.raises(script.ScriptError, match=r"alpha at pixel \(1, 1\) is 0.5"):
        script.coverage(array("f", [0.0, 1.0, 1.0, 0.5]), 2, "frame 0")


def test_the_colour_rows_mask_empty_pixels_and_follow_the_alpha(script):
    rows = [bytearray([9, 9, 9, 0, 200, 100, 50, 255])]
    assert script.colour_rows(rows, [bytes([0, 255])], "frame 0") == [
        bytearray([0, 0, 0, 0, 200, 100, 50, 255])
    ]
    with pytest.raises(
        script.ScriptError, match=r"colour at pixel \(1, 0\) has 8-bit alpha 255"
    ):
        script.colour_rows(
            [bytearray([9, 9, 9, 0, 1, 2, 3, 255])], [bytes([0, 0])], "frame 0"
        )


def test_a_frame_of_more_than_256_codes(script):
    # More distinct codes than a byte can index takes the slower path.
    codes = set(range(1, 301))
    ids = array("f", [float(code) for code in range(1, 301)] + [0.0] * 4)
    shades = array("f", [0.25] * 300 + [0.0] * 4)
    covered = [bytes([255] * 300 + [0] * 4)]
    (identity,), (level,) = script.id_and_shade_rows(
        ids, shades, covered, 304, codes, "f"
    )
    assert [(identity[4 * i], identity[4 * i + 1]) for i in (0, 255, 299)] == [
        (0, 1),
        (1, 0),
        (1, 44),
    ]
    assert identity[4 * 300 :] == bytes(16)
    assert level[0:4] == bytes([137, 137, 137, 255]) and level[4 * 300 :] == bytes(16)


# The surface gate and the count render (alpha design ALPHA-2)


def test_whole_hits_on_the_colour_s_surfaces_pass(script):
    script.check_hits(
        array("f", [0.0, 1.0, 1.0, 0.0]), [bytes([0, 255]), bytes([255, 0])], 2, "f"
    )


@pytest.mark.parametrize("value", [0.5, 2.0, 1e-30, -1.0, math.nan])
def test_a_hit_other_than_0_or_1_is_refused(script, value):
    hits = array("f", [0.0, 1.0, value, 1.0])
    with pytest.raises(
        script.ScriptError, match=r"surface gate's hit at pixel \(0, 1\) is"
    ):
        script.check_hits(hits, [bytes([0, 255]), bytes([255, 255])], 2, "frame 3")


def test_a_refusal_names_the_first_pixel_s_own_value(script):
    values = array("f", [1.0, 0.25, 0.0, 0.75])
    with pytest.raises(script.ScriptError) as hit:
        script.check_hits(values, [bytes([255, 255]), bytes([0, 255])], 2, "frame 3")
    assert str(hit.value) == (
        "frame 3: the surface gate's hit at pixel (1, 0) is 0.25, not exactly 0 or 1"
    )
    with pytest.raises(script.ScriptError) as alpha:
        script.coverage(values, 2, "frame 3")
    assert str(alpha.value) == (
        "frame 3: the render's alpha at pixel (1, 0) is 0.25, not a whole opaque "
        "surface or none"
    )


def test_hits_off_the_colour_s_surfaces_are_refused(script):
    with pytest.raises(
        script.ScriptError,
        match=r"frame 3: the surface gate at pixel \(1, 0\) shows no surface, but "
        r"the colour there shows a surface",
    ):
        script.check_hits(array("f", [1.0, 0.0]), [bytes([255, 255])], 2, "frame 3")


PLACE = "/models/fence.glb: clip 'walk', direction 3, frame 17 (t = 0.25 s)"


def test_a_count_of_64_passes(script):
    script.check_count(array("f", [0.0, 64.0, 12.0, 64.0]), 2, PLACE)


@pytest.mark.parametrize("deepest", [65.0, 100.0])
def test_a_count_of_65_or_more_names_the_frame_and_the_limit(script, deepest):
    with pytest.raises(script.ScriptError) as raised:
        script.check_count(array("f", [0.0, 3.0, deepest, 64.0]), 2, PLACE)
    assert str(raised.value) == (
        f"{PLACE}: a camera path at pixel (0, 1) crossed more than 64 surfaces "
        "that still let light through, which the capture cannot render (the "
        "limit is 64)"
    )
    assert script.LAYER_LIMIT == 64


def test_a_nan_alpha_is_refused(script):
    with pytest.raises(script.ScriptError, match=r"alpha at pixel \(1, 0\) is nan"):
        script.coverage(array("f", [0.0, math.nan]), 2, "frame 0")
