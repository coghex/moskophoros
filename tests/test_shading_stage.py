"""Stylize applies the resolved shading response (SHD-5; shading design
contract 3, D-14, D-18 to D-21, D-23, D-27 to D-30, D-34, D-36, D-37): each
layer shaded by its winning material's response, then snapped, dithered and
composited, from exact addressed fixtures and with no Blender or command."""

import inspect
import math
import weakref
from dataclasses import dataclass

import numpy as np
import pytest
from test_layers import over

from moskophoros import (
    dither,
    imageops,
    lighting,
    materials,
    settings,
    shading_resolve,
    stylize,
    views,
)
from moskophoros.sampling import (
    BACK_NORMAL,
    BACKGROUND,
    DEPTH,
    DEPTH_MAP,
    FRONT_ALPHA,
    FRONT_COLOR,
    FRONT_IDENTITY,
    FRONT_NORMAL,
    FRONT_PRESENT,
    FRONT_SHADE,
    IDENTITY,
    NORMAL,
    NORMAL_MAP,
    SHADE,
    FrameAddress,
    Identities,
    ImageFrame,
)

LOOKS = [pytest.param(stylize.plain, id="plain"), pytest.param(stylize.mode, id="mode")]
MODES = ("ramp", "brightness", "both", "neither")
BRIGHT = ("brightness", "both")
SNAPS = ("off", "ramp", "palette")
EDGES = ("hard", "soft")
PALETTE = (
    (0, 0, 0),
    (255, 255, 255),
    (200, 40, 40),
    (40, 200, 40),
    (40, 40, 200),
    (220, 220, 60),
    (60, 220, 220),
    (128, 128, 128),
)
RAMP_BACK = (2, 3, 4, 5)
RAMP_FRONT = (6, 7, 5, 3)
IDENTITIES = Identities(("back", "front"))
BACK, FRONT, NONE = 0, 1, 2
RANGE = (0, 99)
KEY = (0.0, 0.0, 1.0)
LIGHTS = lighting.Lights(key=KEY, sky=(0.0, 1.0, 0.0), ground=(0.0, -1.0, 0.0))
V4 = materials.SCHEMA_V4
GLOBALS = {**settings.DEFAULTS, **settings.SHADING_DEFAULTS, "shade.range": RANGE}
BACK_SHADE, FRONT_SHADE_VALUE = 50, 80  # signals 0.5 and 0.8 over RANGE
OPAQUE = 65535


def values(**changes):
    return {
        **GLOBALS,
        **{f"shade.{k.replace('__', '.')}": v for k, v in changes.items()},
    }


def library(entries=None, shade=None, ramps=None, default=None, palette=PALETTE):
    document = {
        "schema": V4,
        "ramps": ramps or {"back": list(RAMP_BACK), "front": list(RAMP_FRONT)},
        "materials": entries
        if entries is not None
        else {"back": {"uses": "back"}, "front": {"uses": "front"}},
    }
    if shade is not None:
        document["shade"] = shade
    if default is not None:
        document["default"] = default
    return materials.validate_library(document, palette, source="test", shading=True)


def resolved(lib=None, **changes):
    return shading_resolve.resolve(values(**changes), lib, has_palette=True)


def modes_library(back_mode, front_mode, back=None, front=None):
    """The matrix library: each material its ramp and mode, and any further
    response leaves in `back` and `front`."""
    return library(
        {
            "back": {"uses": "back", "shade": {"mode": back_mode, **(back or {})}},
            "front": {"uses": "front", "shade": {"mode": front_mode, **(front or {})}},
        }
    )


@dataclass
class Layer:
    """One layer of a test frame: a uniform colour, identity, shade and normal
    over `where`, a boolean mask of the supersamples (all, if None)."""

    colour: tuple = (90, 90, 90)
    ident: int = BACK
    shade: int = BACK_SHADE
    normal: tuple = KEY
    where: object = None
    q: int = 0  # the front's alpha, in units of 1/65535


def address(i=0):
    return FrameAddress("s", "default", "walk", i, float(i))


def frame(back=None, front=None, size=(1, 1), factor=2, i=0, normals=True, extra=None):
    """A frame of `size` output pixels in rows and columns, `factor`
    supersamples a side, from a back and a front `Layer` (a frame with no
    front layer if `front` is None)."""
    height, width = size[0] * factor, size[1] * factor
    pixels = np.zeros((height, width, 4), np.uint8)
    buffers = {
        IDENTITY: np.full((height, width), BACKGROUND, np.int32),
        SHADE: np.zeros((height, width), np.uint8),
    }
    if normals:
        buffers[BACK_NORMAL] = np.zeros((height, width, 3), np.float32)

    def mask(layer):
        return np.ones((height, width), bool) if layer.where is None else layer.where

    if back is not None:
        on = mask(back)
        pixels[on] = (*back.colour, 255)
        buffers[IDENTITY][on] = back.ident
        buffers[SHADE][on] = back.shade
        if normals:
            buffers[BACK_NORMAL][on] = back.normal
    if front is not None:
        on = mask(front)
        colour = np.zeros((height, width, 4), np.uint8)
        colour[on] = (*front.colour, 255)
        buffers[FRONT_COLOR] = colour
        buffers[FRONT_ALPHA] = np.where(on, front.q, 0).astype(np.uint16)
        buffers[FRONT_PRESENT] = on.copy()
        buffers[FRONT_IDENTITY] = np.where(on, front.ident, BACKGROUND).astype(np.int32)
        buffers[FRONT_SHADE] = np.where(on, front.shade, 0).astype(np.uint8)
        if normals:
            normal = np.zeros((height, width, 3), np.float32)
            normal[on] = front.normal
            buffers[FRONT_NORMAL] = normal
    buffers.update(extra or {})
    return ImageFrame(address(i), pixels, {"i": i}, buffers)


def run(look, one, shading=None, lights=LIGHTS, factor=2, **options):
    options.setdefault("palette", PALETTE)
    options.setdefault("identities", IDENTITIES)
    options.setdefault("shade_range", RANGE)
    if shading is not None:
        options.update(shading=shading, lights=lights)
    (result,) = look([one], factor, **options)
    return result


def plain_pixel(result):
    return tuple(int(v) for v in result.pixels[0, 0])


# The oracle: the design's arithmetic worked out here, independently.


def decode(byte):
    c = byte / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def encode(linear):
    s = 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055
    return min(255, math.floor(255 * s + 0.5))


def scaled(colour, gain):
    return tuple(encode(decode(c) * gain) for c in colour)


def nearest(colour, colours):
    """`colour` mapped to the nearest of `colours` by OKLab distance."""
    pixel = np.array([[[*colour, 255]]], np.uint8)
    return tuple(int(v) for v in imageops.map_palette(pixel, colours)[0, 0, :3])


def ramp_colours(ramp, palette=PALETTE):
    return [palette[i] for i in ramp]


def layer_colour(
    mode, ramp, shade, floor=0.3, ceiling=1.0, lo=0, hi=99, palette=PALETTE
):
    """A ramped layer's colour for the form signal `e` of its shade, with no
    light: the band, the last entry or the base, scaled as the mode says."""
    e = (min(max(shade, lo), hi) - lo) / (hi - lo + 1)
    colours = ramp_colours(ramp, palette)
    band = min(math.floor(len(ramp) * e), len(ramp) - 1)
    chosen = colours[band] if mode in ("ramp", "both") else colours[-1]
    if mode in BRIGHT:
        chosen = scaled(chosen, floor + (ceiling - floor) * e)
    return chosen


def cells(size):
    rows, columns = np.indices(size)
    return rows.reshape(-1), columns.reshape(-1)


# Every pairing of front and back modes under every snap target


def pair_expected(snap, front_mode, back_mode, q):
    front_c = layer_colour(front_mode, RAMP_FRONT, FRONT_SHADE_VALUE)
    back_c = layer_colour(back_mode, RAMP_BACK, BACK_SHADE)
    front_bright, back_bright = front_mode in BRIGHT, back_mode in BRIGHT
    if snap == "ramp":
        if front_bright:
            front_c = nearest(front_c, ramp_colours(RAMP_FRONT))
        if back_bright:
            back_c = nearest(back_c, ramp_colours(RAMP_BACK))
    composite = over(front_c, 4 * q, back_c, 4 * (OPAQUE - q))
    if front_bright or back_bright:
        # Brightness keeps its colour off the palette, unless the whole
        # palette is the snap target.
        return nearest(composite, PALETTE) if snap == "palette" else composite
    return nearest(composite, PALETTE)


@pytest.mark.parametrize("edges", EDGES)
@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("snap", SNAPS)
@pytest.mark.parametrize("front_mode", MODES)
@pytest.mark.parametrize("back_mode", MODES)
def test_every_front_and_back_mode_under_every_snap(
    look, snap, front_mode, back_mode, edges
):
    q = 26214
    one = frame(
        Layer(ident=BACK, shade=BACK_SHADE),
        Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=q),
    )
    lib = modes_library(back_mode, front_mode)
    got = run(look, one, resolved(lib, snap=snap), library=lib, edges=edges)
    expected = pair_expected(snap, front_mode, back_mode, q)
    assert plain_pixel(got)[:3] == expected
    assert got.pixels[0, 0, 3] == 255
    if (front_mode in BRIGHT or back_mode in BRIGHT) and snap != "palette":
        assert expected not in PALETTE  # off the palette: nothing snapped it


def single_expected(snap, mode, ramp, shade):
    colour = layer_colour(mode, ramp, shade)
    if mode in BRIGHT and snap == "ramp":
        return nearest(colour, ramp_colours(ramp))
    if mode in BRIGHT and snap == "palette":
        return nearest(colour, PALETTE)
    return colour


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("snap", SNAPS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", ["back", "front", "unlayered"])
def test_a_lone_layer_is_shaded_and_snapped_on_its_own(look, snap, mode, kind):
    if kind == "front":
        one = frame(None, Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=OPAQUE))
        # The front's alpha is its q, in this one-layer frame 1.
        ramp, shade = RAMP_FRONT, FRONT_SHADE_VALUE
    else:
        one = frame(Layer(ident=BACK, shade=BACK_SHADE))
        if kind == "back":
            one = frame(
                Layer(ident=BACK, shade=BACK_SHADE),
                Layer(ident=FRONT, q=0, where=np.zeros((2, 2), bool)),
            )
        ramp, shade = RAMP_BACK, BACK_SHADE
    lib = modes_library(mode, mode)
    got = run(look, one, resolved(lib, snap=snap), library=lib)
    assert plain_pixel(got)[:3] == single_expected(snap, mode, ramp, shade)
    assert got.pixels[0, 0, 3] == 255


def test_a_back_only_frame_with_an_absent_front_layer_is_the_lone_back():
    # `FRONT_PRESENT` nowhere: the frame is reduced as one without a front.
    lib = modes_library("brightness", "brightness")
    one = frame(Layer(), Layer(q=0, where=np.zeros((2, 2), bool)))
    got = run(stylize.plain, one, resolved(lib), library=lib)
    assert plain_pixel(got)[:3] == layer_colour("brightness", RAMP_BACK, BACK_SHADE)


# Which signal reaches which layer


def test_each_layer_is_shaded_from_its_own_normal_and_shade_only():
    # The key light at full strength with the form off: a layer's signal is
    # its normal's facing term, so front and back signals are independent.
    lib = library(
        shade={
            "mode": "brightness",
            "ambient_form": False,
            "key": {"strength": 1},
            "brightness": {"floor": 0.0, "ceiling": 1.0},
        }
    )
    shading = resolved(lib)
    toward, away = (0.0, 0.0, 1.0), (0.6, 0.0, 0.8)  # facing 1 and 0.8
    q = 32768

    def pixel(front_normal, back_normal, front_shade=0, back_shade=0):
        one = frame(
            Layer(ident=BACK, shade=back_shade, normal=back_normal),
            Layer(ident=FRONT, shade=front_shade, normal=front_normal, q=q),
        )
        return plain_pixel(run(stylize.plain, one, shading, library=lib))[:3]

    def expected(front_facing, back_facing):
        front = scaled(RAMP_FRONT_LAST, front_facing)
        back = scaled(RAMP_BACK_LAST, back_facing)
        return over(front, 4 * q, back, 4 * (OPAQUE - q))

    assert pixel(toward, away) == expected(1.0, 0.8)
    assert pixel(away, toward) == expected(0.8, 1.0)
    # Shades are not read at all with the ambient form off.
    assert pixel(toward, away, 10, 90) == expected(1.0, 0.8)


RAMP_FRONT_LAST = PALETTE[RAMP_FRONT[-1]]
RAMP_BACK_LAST = PALETTE[RAMP_BACK[-1]]


def test_a_layer_with_no_weight_contributes_nothing_not_even_a_normal():
    lib = library(
        shade={"mode": "brightness", "key": {"strength": 0.5}},
    )
    shading = resolved(lib)
    # The front is present everywhere but its q is 0, and its normal is the
    # zero vector a weightless sample may carry.
    one = frame(Layer(), Layer(ident=FRONT, q=0, normal=(0.0, 0.0, 0.0)))
    alone = frame(Layer())
    assert (
        run(stylize.plain, one, shading, library=lib).pixels
        == run(stylize.plain, alone, shading, library=lib).pixels
    ).all()


def test_a_present_front_with_q_zero_does_not_make_snap_effective():
    # The front would use brightness, but weighs nothing; the back, ramp-only,
    # keeps its band dithering under whole-palette snap.
    lib = modes_library(
        "ramp",
        "brightness",
        back={"dither": {"pattern": "ordered4", "strength": 1}},
    )
    shading = resolved(lib, snap="palette")
    size = (4, 4)
    one = frame(Layer(), Layer(ident=FRONT, q=0), size=size)
    got = run(stylize.plain, one, shading, library=lib).pixels
    rows, columns = cells(size)
    threshold = dither.thresholds("ordered4", rows, columns)
    band = dither.dithered_band(0.5, 4, threshold, 1.0)
    expected = np.array([PALETTE[RAMP_BACK[b]] for b in band]).reshape(4, 4, 3)
    assert (got[..., :3] == expected).all()
    assert len(set(map(tuple, expected.reshape(-1, 3)))) > 1  # really dithered


@pytest.mark.parametrize("other_shade", [0, 99])
def test_the_winning_identity_alone_gives_the_shade_and_ties_go_to_the_lower(
    other_shade,
):
    # Two identities each win two samples of the block, so the lower index
    # wins; only its samples' shades make the signal, whatever the other's.
    mine = np.array([[True, True], [False, False]])
    one = frame(Layer(ident=BACK, shade=BACK_SHADE, where=mine))
    one.pixels[~mine] = (90, 90, 90, 255)
    one.buffers[IDENTITY][~mine] = FRONT
    one.buffers[SHADE][~mine] = other_shade
    lib = modes_library("brightness", "ramp")
    got = run(stylize.plain, one, resolved(lib), library=lib)
    assert plain_pixel(got)[:3] == layer_colour("brightness", RAMP_BACK, BACK_SHADE)


# Missing buffers


def test_a_directional_response_needs_the_layers_normals_by_name():
    lib = library(shade={"mode": "brightness", "key": {"strength": 0.5}})
    shading = resolved(lib)
    both = frame(Layer(), Layer(ident=FRONT, q=OPAQUE // 2), normals=False)
    with pytest.raises(ValueError, match=r"back_normal") as raised:
        run(stylize.plain, both, shading, library=lib)
    assert str(address()) in str(raised.value)
    back_only = frame(Layer(), normals=False)
    with pytest.raises(ValueError, match="back_normal"):
        run(stylize.plain, back_only, shading, library=lib)
    # With only the front's normal missing, it is the front's that is named.
    some = frame(Layer(), Layer(ident=FRONT, q=OPAQUE // 2))
    del some.buffers[FRONT_NORMAL]
    with pytest.raises(ValueError, match="front_normal"):
        run(stylize.plain, some, shading, library=lib)


def test_a_sample_with_weight_needs_a_normal_that_is_not_zero():
    lib = library(shade={"mode": "brightness", "sky": {"strength": 0.5}})
    one = frame(Layer(normal=(0.0, 0.0, 0.0)))
    with pytest.raises(ValueError, match="finite normal") as raised:
        run(stylize.plain, one, resolved(lib), library=lib)
    assert str(address()) in str(raised.value)


@pytest.mark.parametrize("name", [IDENTITY, SHADE])
def test_a_response_needs_the_identity_and_shade_buffers_by_name(name):
    lib = library(shade={"mode": "brightness"})
    one = frame(Layer())
    del one.buffers[name]
    with pytest.raises(ValueError, match=name) as raised:
        run(stylize.plain, one, resolved(lib), library=lib)
    assert str(address()) in str(raised.value)


def test_zero_directional_responses_need_no_normals_and_keep_their_results():
    lib = modes_library("both", "both")
    shading = resolved(lib)
    with_normals = frame(Layer(), Layer(ident=FRONT, q=OPAQUE // 2))
    without = frame(Layer(), Layer(ident=FRONT, q=OPAQUE // 2), normals=False)
    for look in (stylize.plain, stylize.mode):
        np.testing.assert_array_equal(
            run(look, with_normals, shading, library=lib).pixels,
            run(look, without, shading, library=lib).pixels,
        )


def test_a_buffer_of_the_wrong_shape_is_named():
    lib = library(shade={"mode": "brightness", "key": {"strength": 0.5}})
    one = frame(Layer())
    one.buffers[BACK_NORMAL] = np.zeros((3, 3, 3), np.float32)
    with pytest.raises(ValueError, match="back_normal"):
        run(stylize.plain, one, resolved(lib), library=lib)


def test_an_identity_beyond_the_list_is_named():
    lib = library(shade={"mode": "brightness"})
    one = frame(Layer(ident=7))
    with pytest.raises(ValueError, match="identity"):
        run(stylize.plain, one, resolved(lib), library=lib)


# The arguments


def test_shading_and_its_lights_come_together_and_agree_with_the_range():
    lib = library()
    shading = resolved(lib)
    one = frame(Layer())
    with pytest.raises(ValueError, match="together"):
        stylize.plain([one], 2, palette=PALETTE, shading=shading)
    with pytest.raises(ValueError, match="together"):
        stylize.mode([one], 2, palette=PALETTE, lights=LIGHTS)
    with pytest.raises(ValueError, match="shade range"):
        run(stylize.plain, one, shading, library=lib, shade_range=None)
    with pytest.raises(ValueError, match="resolved global range"):
        run(stylize.plain, one, shading, library=lib, shade_range=(1, 99))
    with pytest.raises(TypeError, match="shading_resolve.Resolved"):
        run(stylize.plain, one, "nonsense", library=lib)
    with pytest.raises(TypeError, match="lighting.Lights"):
        run(stylize.plain, one, shading, lights=KEY, library=lib)


def test_a_library_or_a_snap_target_needs_a_palette_and_a_response_the_identities():
    lib = library()
    one = frame(Layer())
    with pytest.raises(ValueError, match="needs a palette"):
        run(stylize.plain, one, resolved(lib), library=lib, palette=None)
    with pytest.raises(ValueError, match="needs a palette"):
        run(stylize.plain, one, resolved(snap="ramp"), palette=None)
    with pytest.raises(ValueError, match="identity list"):
        run(stylize.plain, one, resolved(mode="both"), identities=None)


# No library


def ordinary_base(look, one):
    """The reduction with no shading at all."""
    return run(look, one).pixels


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("palette", [None, PALETTE], ids=["no palette", "palette"])
def test_brightness_needs_no_library_and_no_palette(look, palette):
    one = frame(Layer(colour=(180, 120, 60), shade=BACK_SHADE))
    got = run(look, one, resolved(mode="brightness"), palette=palette)
    # The ordinary base: the model's colour, mapped to a palette if there is one.
    colour = tuple(int(v) for v in run(look, one, palette=palette).pixels[0, 0, :3])
    assert colour == ((180, 120, 60) if palette is None else nearest(colour, PALETTE))
    assert plain_pixel(got)[:3] == scaled(colour, 0.3 + 0.7 * 0.5)


@pytest.mark.parametrize("look", LOOKS)
def test_both_without_a_ramp_falls_back_to_brightness(look):
    one = frame(Layer(colour=(180, 120, 60)))
    brightness = run(look, one, resolved(mode="brightness"), palette=None)
    both = run(look, one, resolved(mode="both"), palette=None)
    np.testing.assert_array_equal(brightness.pixels, both.pixels)
    assert plain_pixel(both)[:3] == scaled((180, 120, 60), 0.65)


@pytest.mark.parametrize("mode", ["ramp", "neither"])
@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("palette", [None, PALETTE], ids=["no palette", "palette"])
def test_ramp_and_neither_keep_the_ordinary_base_without_a_ramp(mode, look, palette):
    one = frame(Layer(colour=(180, 120, 60)), Layer(colour=(10, 200, 90), q=30000))
    shading = resolved(mode=mode)
    assert (
        stylize.shaded(
            2, palette, IDENTITIES, None, RANGE, shading, LIGHTS, by_mode=False
        )
        is None
    )
    np.testing.assert_array_equal(
        run(look, one, shading, palette=palette).pixels,
        run(look, one, palette=palette).pixels,
    )


@pytest.mark.parametrize("look", LOOKS)
def test_the_all_default_case_is_the_historical_one_even_without_the_buffers(look):
    # No identity, shade or normal buffers at all, with and without a palette
    # and under either edge rule: the response step does not exist.
    rng = np.random.default_rng(3)
    pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    pixels[..., 3] = np.where(rng.random((8, 8)) < 0.7, 255, 0)
    bare = ImageFrame(address(), pixels, {"k": 1})
    for palette in (None, PALETTE):
        for edges in EDGES:
            (a,) = look([bare], 2, palette=palette, edges=edges)
            (b,) = look(
                [bare],
                2,
                palette=palette,
                edges=edges,
                shade_range=RANGE,
                shading=resolved(),
                lights=LIGHTS,
            )
            np.testing.assert_array_equal(a.pixels, b.pixels)


@pytest.mark.parametrize("look", LOOKS)
def test_the_global_range_reaches_a_response_without_a_library(look):
    one = frame(Layer(colour=(200, 100, 50), shade=60))
    for lo, hi in ((0, 99), (50, 99), (60, 69)):
        shading = shading_resolve.resolve(
            {**values(mode="brightness"), "shade.range": (lo, hi)},
            None,
            has_palette=False,
        )
        got = run(look, one, shading, palette=None, shade_range=(lo, hi))
        e = (min(max(60, lo), hi) - lo) / (hi - lo + 1)
        assert plain_pixel(got)[:3] == scaled((200, 100, 50), 0.3 + 0.7 * e)


# A /4 library's ordinary entries


@pytest.mark.parametrize("look", LOOKS)
def test_ordinary_entries_and_unlisted_names_inherit_the_library_response(look):
    lib = library(
        entries={
            "back": {"ordinary": True},
            "front": {"ordinary": True, "shade": {"mode": "neither"}},
        },
        shade={"mode": "brightness", "brightness": {"floor": 0.5, "ceiling": 1.0}},
        default=None,
    )
    shading = resolved(lib)
    colour = (180, 120, 60)
    # An ordinary entry takes the library's brightness; its sibling, its own
    # `neither`; a part with no identity the library's response again.
    for ident, gain in ((BACK, 0.5 + 0.5 * 0.5), (FRONT, None), (NONE, 0.75)):
        one = frame(Layer(colour=colour, ident=ident, shade=BACK_SHADE))
        got = plain_pixel(run(look, one, shading, library=lib))[:3]
        base = nearest(colour, PALETTE)
        assert got == (base if gain is None else scaled(base, gain))


@pytest.mark.parametrize("look", LOOKS)
def test_a_global_option_does_not_defeat_a_material_value(look):
    lib = library(
        entries={"back": {"uses": "back", "shade": {"mode": "ramp"}}},
        shade={"mode": "both"},
    )
    shading = resolved(lib, mode="neither")
    got = run(look, frame(Layer()), shading, library=lib)
    assert plain_pixel(got)[:3] == layer_colour("ramp", RAMP_BACK, BACK_SHADE)


# The default response equals the historical path


def random_frame(layered, seed, size=4, factor=3):
    rng = np.random.default_rng(seed)
    h = size * factor
    pixels = rng.integers(0, 256, (h, h, 4), dtype=np.uint8)
    pixels[..., 3] = np.where(rng.random((h, h)) < 0.8, 255, 0)
    buffers = {
        IDENTITY: rng.integers(-1, 3, (h, h)).astype(np.int32),
        SHADE: rng.integers(0, 256, (h, h)).astype(np.uint8),
    }
    if layered:
        present = rng.random((h, h)) < 0.5
        buffers[FRONT_COLOR] = rng.integers(0, 256, (h, h, 4), dtype=np.uint8)
        buffers[FRONT_ALPHA] = np.where(
            present, rng.integers(0, 65536, (h, h)), 0
        ).astype(np.uint16)
        buffers[FRONT_PRESENT] = present
        buffers[FRONT_IDENTITY] = rng.integers(-1, 3, (h, h)).astype(np.int32)
        buffers[FRONT_SHADE] = rng.integers(0, 256, (h, h)).astype(np.uint8)
    return ImageFrame(address(seed), pixels, {}, buffers)


@pytest.mark.parametrize("edges", EDGES)
@pytest.mark.parametrize("layered", [False, True], ids=["opaque", "layered"])
@pytest.mark.parametrize("look", LOOKS)
def test_the_default_response_with_a_library_is_the_historical_reduction(
    look, layered, edges
):
    lib = library(
        entries={"back": {"ramp": [7, 2]}, "front": "ordinary"},
        ramps={"back": [1, 2, 3]},
        default="back",
    )
    frames = [random_frame(layered, seed) for seed in range(4)]
    options = dict(
        palette=PALETTE,
        identities=IDENTITIES,
        library=lib,
        shade_range=(84, 191),
        edges=edges,
    )
    old = look(frames, 3, **options)
    shading = shading_resolve.resolve(
        {**values(), "shade.range": (84, 191)}, lib, has_palette=True
    )
    new = look(frames, 3, shading=shading, lights=LIGHTS, **options)
    for a, b in zip(old, new, strict=True):
        np.testing.assert_array_equal(a.pixels, b.pixels)
    # The ramps took effect: the library path differs from the plain palette one.
    bare = look(frames, 3, palette=PALETTE, edges=edges)
    assert any((a.pixels != b.pixels).any() for a, b in zip(old, bare, strict=True))


# Alpha, maps and the preview light


@pytest.mark.parametrize("edges", EDGES)
@pytest.mark.parametrize("look", LOOKS)
def test_shading_changes_colour_only_never_alpha_or_the_maps(look, edges):
    lib = modes_library("both", "brightness", back={"key": {"strength": 0.5}})
    rng = np.random.default_rng(5)
    base = random_frame(True, 5, size=3, factor=2)
    base.buffers[NORMAL] = rng.normal(size=(6, 6, 3)).astype(np.float32)
    base.buffers[NORMAL] /= np.linalg.norm(base.buffers[NORMAL], axis=-1, keepdims=True)
    base.buffers[DEPTH] = rng.random((6, 6)).astype(np.float32)
    base.buffers[BACK_NORMAL] = base.buffers[NORMAL].copy()
    base.buffers[FRONT_NORMAL] = base.buffers[NORMAL].copy()
    options = dict(
        palette=PALETTE,
        identities=IDENTITIES,
        library=lib,
        shade_range=RANGE,
        edges=edges,
        pixels_per_meter=10.0,
    )
    (plain,) = look([base], 2, **options)
    (lit,) = look(
        [base], 2, shading=resolved(lib, snap="palette"), lights=LIGHTS, **options
    )
    np.testing.assert_array_equal(plain.pixels[..., 3], lit.pixels[..., 3])
    assert (plain.pixels[..., :3] != lit.pixels[..., :3]).any()
    assert set(lit.buffers) == {NORMAL_MAP, DEPTH_MAP}
    for name in (NORMAL_MAP, DEPTH_MAP):
        np.testing.assert_array_equal(plain.buffers[name], lit.buffers[name])
    # A pixel with no alpha stays transparent black.
    clear = lit.pixels[..., 3] == 0
    assert (lit.pixels[clear] == 0).all()


def test_a_point_lit_preview_lights_the_baked_colour_and_stylize_takes_no_light():
    lib = modes_library("brightness", "brightness")
    (baked,) = stylize.plain(
        [frame(Layer(colour=(200, 100, 50)))],
        2,
        palette=PALETTE,
        identities=IDENTITIES,
        library=lib,
        shade_range=RANGE,
        shading=resolved(lib),
        lights=LIGHTS,
    )
    colour = layer_colour("brightness", RAMP_BACK, BACK_SHADE)
    assert plain_pixel(baked)[:3] == colour
    # An existing preview light acts on the baked pixels, as on any sheet.
    normals = np.full((1, 1, 3), (128, 128, 255), np.uint8)
    codes = np.full((1, 1), 32768, np.uint16)
    args = (normals, codes, (0, 0), (0.0, 0.0, 100.0), 1.0, 0.3)
    factor = imageops.light_factors(*args)
    lit = imageops.light_pixels(baked.pixels, *args)
    assert tuple(lit[0, 0, :3]) == scaled(colour, float(factor[0, 0]))
    assert lit[0, 0, 3] == baked.pixels[0, 0, 3]
    # Baking never requests preview lighting: stylize has no such argument.
    for look in (stylize.plain, stylize.mode):
        assert "light" not in inspect.signature(look).parameters


# Band dithering, snap dithering and which of them runs

# Forty-two greys 6 apart, so a snap has little to hide behind; the ramps
# pick every tenth, 60 to 240.
GREY = tuple((v, v, v) for v in range(0, 252, 6))
GREY_BACK = (10, 20, 30, 40)  # ascending, for the back
GREY_FRONT = (40, 30, 20, 10)  # descending, for the front
GRID = (4, 4)
LEFT_OVER = {"ordered2": "diagonal4", "ordered4": "shuffled8"}


def grey_library(back_mode, front_mode, back=None, front=None, snap="off", **top):
    lib = library(
        {
            "back": {"uses": "g", "shade": {"mode": back_mode, **(back or {})}},
            "front": {"uses": "h", "shade": {"mode": front_mode, **(front or {})}},
        },
        ramps={"g": list(GREY_BACK), "h": list(GREY_FRONT)},
        palette=GREY,
    )
    return lib, resolved(lib, snap=snap, **top)


def grey_run(look, one, lib, shading, **options):
    return run(look, one, shading, library=lib, palette=GREY, **options)


def grey_layer(mode, which, shade):
    ramp = GREY_BACK if which == "back" else GREY_FRONT
    return layer_colour(mode, ramp, shade, palette=GREY)


def band_grid(pattern, strength, e=0.5, bands=4, size=GRID):
    rows, columns = cells(size)
    threshold = dither.thresholds(pattern, rows, columns)
    return dither.dithered_band(e, bands, threshold, strength).reshape(size)


def snapped_grid(colours, target, pattern, strength, size=GRID):
    """`colours`, a grid of RGB triples, snapped to `target` with the output
    cells' own coordinates."""
    rows, columns = cells(size)
    flat = np.asarray(colours, np.uint8).reshape(-1, 3)
    return dither.snap(
        flat, target, pattern=pattern, strength=strength, rows=rows, columns=columns
    ).reshape(*size, 3)


def pixels_of(result):
    return result.pixels[..., :3]


# A shade whose band dithered and snap dithered differ in every fixture below.
DITHER_SHADE, DITHER_E = 45, 0.45
DITHERS = [
    ("ordered4", 1.0),
    ("ordered4", 0.5),
    ("clustered4", 1.0),
    ("shuffled8", 0.6),
]


@pytest.mark.parametrize(("pattern", "strength"), DITHERS)
@pytest.mark.parametrize("snap", SNAPS)
@pytest.mark.parametrize("look", LOOKS)
def test_a_ramp_only_layer_keeps_its_band_dithering_under_every_snap_target(
    look, snap, pattern, strength
):
    lib, shading = grey_library(
        "ramp",
        "ramp",
        back={"dither": {"pattern": pattern, "strength": strength}},
        snap=snap,
    )
    got = pixels_of(
        grey_run(look, frame(Layer(shade=DITHER_SHADE), size=GRID), lib, shading)
    )
    band = band_grid(pattern, strength, e=DITHER_E)
    expected = np.array([GREY[GREY_BACK[b]] for b in band.reshape(-1)]).reshape(4, 4, 3)
    np.testing.assert_array_equal(got, expected)
    assert len(set(map(tuple, expected.reshape(-1, 3)))) > 1  # it really dithers


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize(("pattern", "strength"), DITHERS)
def test_a_both_layer_dithers_its_bands_when_nothing_snaps(look, pattern, strength):
    lib, shading = grey_library(
        "both", "both", back={"dither": {"pattern": pattern, "strength": strength}}
    )
    got = pixels_of(
        grey_run(look, frame(Layer(shade=DITHER_SHADE), size=GRID), lib, shading)
    )
    band = band_grid(pattern, strength, e=DITHER_E)
    expected = np.array(
        [scaled(GREY[GREY_BACK[b]], 0.3 + 0.7 * DITHER_E) for b in band.reshape(-1)]
    ).reshape(4, 4, 3)
    np.testing.assert_array_equal(got, expected)
    assert len(set(map(tuple, expected.reshape(-1, 3)))) > 1


@pytest.mark.parametrize("snap", ["ramp", "palette"])
@pytest.mark.parametrize("mode", ["brightness", "both"])
@pytest.mark.parametrize(
    ("pattern", "strength"), DITHERS + [("off", 1.0), ("ordered4", 0.0)]
)
@pytest.mark.parametrize("look", LOOKS)
def test_snap_dithers_the_final_colour_instead_of_the_bands(
    look, snap, mode, pattern, strength
):
    lib, shading = grey_library(
        mode,
        mode,
        back={"dither": {"pattern": pattern, "strength": strength}},
        snap=snap,
    )
    got = pixels_of(
        grey_run(look, frame(Layer(shade=DITHER_SHADE), size=GRID), lib, shading)
    )
    # The band is chosen undithered, brightness applied, then the snap alone
    # is dithered, to the layer's ramp or to the whole palette.
    colour = grey_layer(mode, "back", DITHER_SHADE)
    target = ramp_colours(GREY_BACK, GREY) if snap == "ramp" else list(GREY)
    expected = snapped_grid(np.tile(colour, (16, 1)), target, pattern, strength)
    np.testing.assert_array_equal(got, expected)
    if pattern != "off" and strength > 0 and mode == "both":
        # Not dithered twice: dithering the bands as well would differ.
        band = band_grid(pattern, strength, e=DITHER_E)
        twice = snapped_grid(
            [
                scaled(GREY[GREY_BACK[b]], 0.3 + 0.7 * DITHER_E)
                for b in band.reshape(-1)
            ],
            target,
            pattern,
            strength,
        )
        assert (expected != twice).any()


def test_the_snap_dither_is_visible_in_the_fixture_it_is_pinned_with():
    colour = grey_layer("both", "back", DITHER_SHADE)
    for target in (ramp_colours(GREY_BACK, GREY), list(GREY)):
        grid = snapped_grid(np.tile(colour, (16, 1)), target, "ordered4", 1.0)
        assert len(set(map(tuple, grid.reshape(-1, 3)))) == 2


@pytest.mark.parametrize("snap", SNAPS)
def test_a_neither_layer_gets_no_artificial_noise_under_any_snap(snap):
    lib, shading = grey_library(
        "neither",
        "neither",
        back={"dither": {"pattern": "ordered4", "strength": 1}},
        snap=snap,
    )
    got = pixels_of(
        grey_run(
            stylize.plain, frame(Layer(shade=DITHER_SHADE), size=GRID), lib, shading
        )
    )
    assert (got == GREY[GREY_BACK[-1]]).all()


def partner_expected(snap, front_dominates=True):
    """The pixel colour of a ramp-only front over a brightness back under
    `snap`, cell by cell, each layer with its own pattern."""
    front_pattern, back_pattern = "ordered4", "clustered4"
    q = 50000 if front_dominates else 12000
    bands = band_grid(front_pattern, 1.0, e=0.8)
    fronts = np.array([GREY[GREY_FRONT[b]] for b in bands.reshape(-1)])
    return q, front_pattern, back_pattern, bands, fronts


@pytest.mark.parametrize("snap", SNAPS)
@pytest.mark.parametrize("look", LOOKS)
def test_whole_palette_snap_suppresses_a_ramp_only_partners_band_dithering(look, snap):
    q, front_pattern, back_pattern, _, _ = partner_expected(snap)
    lib, shading = grey_library(
        "brightness",
        "ramp",
        back={"dither": {"pattern": back_pattern, "strength": 1}},
        front={"dither": {"pattern": front_pattern, "strength": 1}},
        snap=snap,
    )
    one = frame(
        Layer(ident=BACK, shade=BACK_SHADE),
        Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=q),
        size=GRID,
    )
    got = pixels_of(grey_run(look, one, lib, shading))
    back_colour = grey_layer("brightness", "back", BACK_SHADE)
    rows, columns = cells(GRID)
    dithered = band_grid(front_pattern, 1.0, e=0.8)
    undithered = band_grid(front_pattern, 0.0, e=0.8)
    # Only the front's bands depend on snap; the back is brightness alone.
    front_band = undithered if snap == "palette" else dithered
    wf, wb = 4 * q, 4 * (OPAQUE - q)
    composite = np.array(
        [over(GREY[GREY_FRONT[b]], wf, back_colour, wb) for b in front_band.reshape(-1)]
    ).reshape(4, 4, 3)
    if snap == "ramp":
        # Own-ramp snap works on the brightness layer apart from the front:
        # the back snaps to its ramp before compositing.
        snapped_back = snapped_grid(
            np.tile(back_colour, (16, 1)),
            ramp_colours(GREY_BACK, GREY),
            back_pattern,
            1.0,
        )
        composite = np.array(
            [
                over(GREY[GREY_FRONT[b]], wf, tuple(snapped_back.reshape(-1, 3)[i]), wb)
                for i, b in enumerate(front_band.reshape(-1))
            ]
        ).reshape(4, 4, 3)
    if snap == "palette":
        # The front dominates, so its pattern controls the final choice.
        composite = snapped_grid(composite, list(GREY), front_pattern, 1.0)
    np.testing.assert_array_equal(got, composite)
    assert (dithered != undithered).any()


@pytest.mark.parametrize("look", LOOKS)
def test_an_ineffective_whole_palette_snap_keeps_ordinary_band_dithering(look):
    # Neither layer uses brightness or both, so the target changes nothing:
    # both bands dither, and the composite maps to the palette as it always did.
    lib, shading = grey_library(
        "ramp",
        "neither",
        back={"dither": {"pattern": "ordered4", "strength": 1}},
        front={"dither": {"pattern": "clustered4", "strength": 1}},
        snap="palette",
    )
    q = 30000
    one = frame(
        Layer(ident=BACK, shade=BACK_SHADE),
        Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=q),
        size=GRID,
    )
    got = pixels_of(grey_run(look, one, lib, shading))
    back_bands = band_grid("ordered4", 1.0, e=0.5).reshape(-1)
    expected = np.array(
        [
            nearest(
                over(GREY[GREY_FRONT[-1]], 4 * q, GREY[GREY_BACK[b]], 4 * (OPAQUE - q)),
                GREY,
            )
            for b in back_bands
        ]
    ).reshape(4, 4, 3)
    np.testing.assert_array_equal(got, expected)


# The composite dither controller

CONTROL = ("ordered2", "diagonal4")  # the front's pattern, the back's


def controller_case(q_or_masks):
    return q_or_masks


def pair_frame(kind):
    """A grid of two-layer pixels whose front visibly dominates, loses or ties."""
    if kind == "tie":
        top = np.zeros((8, 8), bool)
        top[::2, :] = True  # each block's upper row: front opaque, back unseen
        return frame(
            Layer(ident=BACK, shade=BACK_SHADE),
            Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=OPAQUE, where=top),
            size=GRID,
        ), (2 * OPAQUE, 2 * OPAQUE)
    q = {"front": 50000, "back": 6000, "neither": 46000}[kind]
    one = frame(
        Layer(ident=BACK, shade=BACK_SHADE),
        Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=q),
        size=GRID,
    )
    return one, (4 * q, 4 * (OPAQUE - q))


@pytest.mark.parametrize("strength", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("kind", ["front", "back", "tie"])
@pytest.mark.parametrize("look", LOOKS)
def test_the_visibly_dominant_layer_controls_the_composite_snap(look, kind, strength):
    lib, shading = grey_library(
        "brightness",
        "both",
        back={"dither": {"pattern": CONTROL[1], "strength": strength}},
        front={"dither": {"pattern": CONTROL[0], "strength": strength}},
        snap="palette",
    )
    one, (wf, wb) = pair_frame(kind)
    got = pixels_of(grey_run(look, one, lib, shading))
    # Both layers' bands are undithered under the effective snap.
    front = grey_layer("both", "front", FRONT_SHADE_VALUE)
    back = grey_layer("brightness", "back", BACK_SHADE)
    composite = over(front, wf, back, wb)
    # A tie goes to the front.
    pattern = CONTROL[1] if kind == "back" else CONTROL[0]
    other = CONTROL[0] if kind == "back" else CONTROL[1]
    expected = snapped_grid(np.tile(composite, (16, 1)), list(GREY), pattern, strength)
    np.testing.assert_array_equal(got, expected)
    wrong = snapped_grid(np.tile(composite, (16, 1)), list(GREY), other, strength)
    if strength > 0:
        assert (expected != wrong).any()  # the controller really matters


@pytest.mark.parametrize("look", LOOKS)
def test_a_dominant_neither_layer_makes_the_final_snap_undithered_not_cancelled(look):
    lib, shading = grey_library(
        "brightness",
        "neither",
        back={"dither": {"pattern": CONTROL[1], "strength": 1}},
        front={"dither": {"pattern": CONTROL[0], "strength": 1}},
        snap="palette",
    )
    one, (wf, wb) = pair_frame("neither")
    got = pixels_of(grey_run(look, one, lib, shading))
    composite = over(
        grey_layer("neither", "front", FRONT_SHADE_VALUE),
        wf,
        grey_layer("brightness", "back", BACK_SHADE),
        wb,
    )
    # The brightness back makes the snap effective; the neither front controls
    # it and so it does not dither.
    expected = snapped_grid(np.tile(composite, (16, 1)), list(GREY), "off", 1.0)
    np.testing.assert_array_equal(got, expected)
    assert nearest(composite, GREY) == tuple(expected[0, 0])
    dithered = snapped_grid(np.tile(composite, (16, 1)), list(GREY), CONTROL[0], 1.0)
    assert (expected != dithered).any()


@pytest.mark.parametrize("look", LOOKS)
def test_a_single_contributor_uses_its_own_controls_and_a_weightless_partner_none(
    look,
):
    lib, shading = grey_library(
        "brightness",
        "brightness",
        back={"dither": {"pattern": CONTROL[1], "strength": 1}},
        front={"dither": {"pattern": CONTROL[0], "strength": 1}},
        snap="palette",
    )
    colour = grey_layer("brightness", "back", BACK_SHADE)
    expected = snapped_grid(np.tile(colour, (16, 1)), list(GREY), CONTROL[1], 1.0)
    alone = frame(Layer(ident=BACK, shade=BACK_SHADE), size=GRID)
    np.testing.assert_array_equal(
        pixels_of(grey_run(look, alone, lib, shading)), expected
    )
    # A front present with a q of 0 weighs nothing: it controls nothing.
    weightless = frame(
        Layer(ident=BACK, shade=BACK_SHADE),
        Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=0),
        size=GRID,
    )
    np.testing.assert_array_equal(
        pixels_of(grey_run(look, weightless, lib, shading)), expected
    )


@pytest.mark.parametrize("look", LOOKS)
def test_own_ramp_snap_is_per_layer_and_a_missing_ramp_falls_back_to_the_palette(look):
    # The front has no ramp (an ordinary entry); the back has one. Ramp snap
    # puts each brightness layer on its own target before compositing, the
    # front's the whole palette; the composite is then left where it falls.
    lib = library(
        {"back": {"uses": "g"}, "front": {"ordinary": True}},
        ramps={"g": list(GREY_BACK)},
        shade={"mode": "brightness"},
        palette=GREY,
    )
    q = 30000
    one = frame(
        Layer(colour=(90, 90, 90), ident=BACK, shade=BACK_SHADE),
        Layer(colour=(200, 200, 200), ident=FRONT, shade=50, q=q),
    )
    ramp_snap = pixels_of(grey_run(look, one, lib, resolved(lib, snap="ramp")))[0, 0]
    palette_snap = pixels_of(grey_run(look, one, lib, resolved(lib, snap="palette")))[
        0, 0
    ]
    front = scaled(nearest((200, 200, 200), GREY), 0.3 + 0.7 * 0.5)
    back = scaled(GREY[GREY_BACK[-1]], 0.3 + 0.7 * 0.5)
    front_snapped = nearest(front, GREY)
    back_snapped = nearest(back, ramp_colours(GREY_BACK, GREY))
    wf, wb = 4 * q, 4 * (OPAQUE - q)
    assert tuple(ramp_snap) == over(front_snapped, wf, back_snapped, wb)
    assert tuple(palette_snap) == nearest(over(front, wf, back, wb), GREY)
    assert tuple(ramp_snap) != tuple(palette_snap)
    assert tuple(ramp_snap) not in GREY  # the composite stays off the palette


# Order, placement and memory


@pytest.mark.parametrize("look", LOOKS)
def test_a_frames_pattern_does_not_depend_on_order_or_its_neighbours(look):
    lib, shading = grey_library(
        "both",
        "both",
        back={"dither": {"pattern": "shuffled8", "strength": 1}},
        front={"dither": {"pattern": "ordered4", "strength": 0.7}},
        snap="palette",
    )
    frames = [
        frame(
            Layer(ident=BACK, shade=BACK_SHADE + 10 * i),
            Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=20000 + 9000 * i),
            size=GRID,
            i=i,
        )
        for i in range(3)
    ]
    options = dict(
        palette=GREY,
        identities=IDENTITIES,
        library=lib,
        shade_range=RANGE,
        shading=shading,
        lights=LIGHTS,
    )
    forward = look(frames, 2, **options)
    backward = look(frames[::-1], 2, **options)
    for result in forward:
        (alone,) = look([frames[result.address.direction]], 2, **options)
        np.testing.assert_array_equal(result.pixels, alone.pixels)
    for early, late in zip(forward, backward[::-1], strict=True):
        np.testing.assert_array_equal(early.pixels, late.pixels)
    assert len({result.pixels.tobytes() for result in forward}) == 3


def layered_stream(held, count=3):
    """Frames with every array a response reads, each checked to be the only
    one alive when the next is asked for."""

    def stream():
        for i in range(count):
            assert all(ref() is None for ref in held), "a previous frame is held"
            one = frame(
                Layer(ident=BACK, shade=BACK_SHADE + i),
                Layer(ident=FRONT, shade=FRONT_SHADE_VALUE, q=30000),
                size=(3, 3),
                i=i,
            )
            rng = np.random.default_rng(i)
            one.buffers[NORMAL] = rng.normal(size=(6, 6, 3)).astype(np.float32)
            one.buffers[DEPTH] = rng.random((6, 6)).astype(np.float32)
            held.extend(weakref.ref(a) for a in [one.pixels, *one.buffers.values()])
            yield one
            del one

    return stream()


@pytest.mark.parametrize("snap", SNAPS)
@pytest.mark.parametrize("look", LOOKS)
def test_lazy_frames_release_every_array_and_keep_addresses_order_and_metadata(
    look, snap
):
    held = []
    lib, shading = grey_library(
        "both",
        "both",
        back={"key": {"strength": 0.5}, "dither": {"pattern": "ordered4"}},
        front={"sky": {"strength": 0.5}},
        snap=snap,
    )
    result = look(
        layered_stream(held),
        2,
        palette=GREY,
        identities=IDENTITIES,
        library=lib,
        shade_range=RANGE,
        pixels_per_meter=10.0,
        shading=shading,
        lights=LIGHTS,
    )
    assert [r.address for r in result] == [address(i) for i in range(3)]
    assert [r.metadata for r in result] == [{"i": i} for i in range(3)]
    assert all(set(r.buffers) == {NORMAL_MAP, DEPTH_MAP} for r in result)
    assert len(held) > 10 and all(ref() is None for ref in held)


def test_inputs_are_left_unchanged_and_results_hold_no_input_memory():
    lib, shading = grey_library(
        "both",
        "both",
        back={"key": {"strength": 0.5}},
        front={"sky": {"strength": 1}},
        snap="ramp",
    )
    held = []
    (one,) = list(layered_stream(held, 1))
    before = {k: v.copy() for k, v in one.buffers.items()}
    pixels = one.pixels.copy()
    (result,) = stylize.plain(
        [one],
        2,
        palette=GREY,
        identities=IDENTITIES,
        library=lib,
        shade_range=RANGE,
        pixels_per_meter=10.0,
        shading=shading,
        lights=LIGHTS,
    )
    np.testing.assert_array_equal(one.pixels, pixels)
    for name, array in before.items():
        np.testing.assert_array_equal(one.buffers[name], array)
    for array in (result.pixels, *result.buffers.values()):
        assert not any(
            np.shares_memory(array, source)
            for source in (one.pixels, *one.buffers.values())
        )


# #140's behaviours, reached through the stage


LONG = tuple((i * 6, 255 - i * 5, (i * 37) % 256) for i in range(40))


def ranged(lib, rng, **changes):
    return shading_resolve.resolve(
        {**values(**changes), "shade.range": rng}, lib, has_palette=True
    )


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("shade", [0, 189, 190, 191, 207, 224, 225, 226, 255])
def test_a_long_ramp_clamps_raw_shade_before_normalising(look, shade):
    # The continuous path (a key light facing it at full strength): over
    # [190, 225] forty bands are reached from 0 to 38, never 39.
    lib = library(
        {"back": {"uses": "long"}},
        ramps={"long": list(range(40))},
        shade={"key": {"strength": 1}},
        palette=LONG,
    )
    shading = ranged(lib, (190, 225))
    got = run(
        look,
        frame(Layer(shade=shade)),
        shading,
        library=lib,
        palette=LONG,
        shade_range=(190, 225),
    )
    clamped = min(max(shade, 190), 225)
    band = min(math.floor(40 * (clamped - 190) / (225 - 190 + 1)), 39)
    assert plain_pixel(got)[:3] == LONG[band]
    assert band <= 38


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize(
    "shades", [(101, 101, 101, 101), (255, 255, 255, 255), (50, 200, 100, 150)]
)
@pytest.mark.parametrize(("form", "gain"), [(True, 0.65), (False, 1.0)])
def test_the_narrow_range_brightness_cap_holds_in_the_stage(look, shades, form, gain):
    colour = (200, 100, 50)
    one = frame(Layer(colour=colour))
    one.buffers[SHADE][:] = np.array(shades, np.uint8).reshape(2, 2)
    shading = shading_resolve.resolve(
        {**values(mode="brightness", ambient_form=form), "shade.range": (100, 101)},
        None,
        has_palette=False,
    )
    got = run(look, one, shading, palette=None, shade_range=(100, 101))
    # Every case's (mean) shade is at or above 101, the range's top.
    assert plain_pixel(got)[:3] == scaled(colour, gain)


@pytest.mark.parametrize(
    ("direction", "roll"),
    [((0, -0.5, -0.866), 0.0), ((0, -1, -1), 0.25), ((0.3, -0.6, -0.7), -0.1)],
)
@pytest.mark.parametrize("name", ["camera", "world"])
def test_the_supplied_sky_vector_decides_the_colour_not_the_pixels(
    name, direction, roll
):
    # A normal facing straight up in the camera, under a full-strength sky,
    # no ambient form and a brightness range of 0 to 1: the colour is its
    # facing term with the sky vector the caller supplied.
    lights = lighting.light_vectors(KEY, name, direction, roll)
    lib = library(
        shade={
            "mode": "brightness",
            "ambient_form": False,
            "sky": {"strength": 1},
            "brightness": {"floor": 0.0, "ceiling": 1.0},
        }
    )
    one = frame(Layer(normal=(0.0, 1.0, 0.0)))
    got = run(stylize.plain, one, resolved(lib), lights=lights, library=lib)
    facing = float(lighting.facing(np.array([0.0, 1.0, 0.0]), lights.sky))
    # The back's ramp, unlit by anything but the sky: its last entry, scaled.
    assert plain_pixel(got)[:3] == scaled(PALETTE[RAMP_BACK[-1]], facing)


def sky_of(basis):
    return (basis.right[1], basis.up[1], 0.0 - basis.forward[1])


@pytest.mark.parametrize("direction", [(0, -0.5, -0.866), (0.3, -0.6, -0.7)])
@pytest.mark.parametrize("roll", [0.0, 0.25, -0.5])
def test_both_projections_share_the_world_sky_and_roll_turns_it(direction, roll):
    orthographic = views.subject_basis(direction, roll)
    perspective = views.perspective(direction, roll, (0.0, 1.0, 6.0)).basis
    assert sky_of(orthographic) == sky_of(perspective)
    lights = lighting.light_vectors(KEY, "world", direction, roll)
    assert lights.sky == pytest.approx(sky_of(orthographic))
    lib = library(
        shade={
            "mode": "brightness",
            "ambient_form": False,
            "sky": {"strength": 1},
            "brightness": {"floor": 0.0, "ceiling": 1.0},
        }
    )
    one = frame(Layer(normal=(1.0, 0.0, 0.0)))
    got = run(stylize.plain, one, resolved(lib), lights=lights, library=lib)
    facing = float(lighting.facing(np.array([1.0, 0.0, 0.0]), lights.sky))
    assert plain_pixel(got)[:3] == scaled(PALETTE[RAMP_BACK[-1]], facing)


# What the stage hands the kernel


@pytest.mark.parametrize("by_mode", [False, True], ids=["plain", "mode"])
def test_the_kernel_gets_the_front_layers_own_weights_shades_and_normals(by_mode):
    # A front layer alone, its samples of different q, shade, identity and
    # normal: the stage must hand `shade_blocks` exactly those, the winner's
    # samples at their own weights.
    look = stylize.mode if by_mode else stylize.plain
    lib, shading = grey_library(
        "ramp",
        "both",
        front={"key": {"strength": 0.5}, "sky": {"strength": 0.25}},
    )
    qs = np.array([[60000, 20000], [41000, 9000]])
    shades = np.array([[10, 90], [50, 70]])
    idents = np.array([[FRONT, FRONT], [FRONT, BACK]])
    normals = np.array(
        [[[0, 0, 1], [0, 1, 0]], [[0.6, 0, 0.8], [1, 0, 0]]], dtype=np.float32
    )
    one = frame(None, Layer(colour=(70, 70, 70), q=OPAQUE))
    one.buffers[FRONT_ALPHA][:] = qs
    one.buffers[FRONT_SHADE][:] = shades
    one.buffers[FRONT_IDENTITY][:] = idents
    one.buffers[FRONT_NORMAL][:] = normals
    got = grey_run(look, one, lib, shading).pixels[0, 0]
    # The winner is FRONT (more weight); only its three samples take part.
    own = idents == FRONT
    weight = np.where(own, qs, 0).reshape(1, 4)
    expected = lighting.shade_blocks(
        np.array([[70, 70, 70]], np.uint8),
        weight,
        shades.reshape(1, 4),
        normals.reshape(1, 4, 3),
        ramp=GREY_FRONT,
        palette=GREY,
        response=shading.look("front").response,
        shade_range=RANGE,
        lights=LIGHTS,
        by_mode=by_mode,
    )
    assert tuple(got[:3]) == tuple(expected[0])
    # And it is not what the whole block, the loser included, would give.
    every = lighting.shade_blocks(
        np.array([[70, 70, 70]], np.uint8),
        qs.reshape(1, 4),
        shades.reshape(1, 4),
        normals.reshape(1, 4, 3),
        ramp=GREY_FRONT,
        palette=GREY,
        response=shading.look("front").response,
        shade_range=RANGE,
        lights=LIGHTS,
        by_mode=by_mode,
    )
    assert tuple(expected[0]) != tuple(every[0])


@pytest.mark.parametrize("edges", EDGES)
@pytest.mark.parametrize("look", LOOKS)
def test_a_partly_covered_block_is_shaded_under_either_edge_rule(look, edges):
    half = np.array([[True, True], [False, False]])
    one = frame(Layer(colour=(180, 120, 60), where=half))
    shading = resolved(mode="brightness")
    got = run(look, one, shading, palette=None, edges=edges)
    plain = run(look, one, palette=None, edges=edges)
    assert got.pixels[0, 0, 3] == plain.pixels[0, 0, 3]
    assert tuple(got.pixels[0, 0, :3]) == scaled(
        tuple(plain.pixels[0, 0, :3]), 0.3 + 0.7 * 0.5
    )
