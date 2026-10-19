"""Coverage and alpha, decided once per output pixel under `edges` (alpha
design, *Stylize: numerical reference*, steps 1 and 5; D-2, D-4, D-9,
D-11): the pinned cases that need no front layer, under `plain` and `mode`,
with and without a palette or a material library, and the maps' alpha."""

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from shading import DEFAULT_SHADE

from moskophoros import export, imageops, materials, sampling, stylize, views
from moskophoros.capture.backend import Settings, Source
from moskophoros.gltf import Clip, SelectedClip, Subject
from moskophoros.sampling import (
    BACKGROUND,
    DEPTH,
    DEPTH_MAP,
    IDENTITY,
    NORMAL,
    NORMAL_MAP,
    SHADE,
    FrameAddress,
    Identities,
    ImageFrame,
)

# A palette whose entry 3 is the surface colour, so mapping keeps it, and a
# library whose ramp takes entry 5.
COLORS = tuple((index * 30, index * 30, index * 30) for index in range(8))
SURFACE = COLORS[3]
RAMPED = COLORS[5]
IDENTITIES = Identities(("steel",))
PPM = 10.0
DEPTH_M = 0.25


def library():
    document = {
        "schema": materials.SCHEMA,
        "ramps": {"steel": [5]},
        "materials": {"steel": {"uses": "steel"}},
    }
    return materials.validate_library(document, COLORS, source="test")


LOOKS = [
    pytest.param(stylize.plain, id="plain"),
    pytest.param(stylize.mode, id="mode"),
]
VARIANTS = [
    pytest.param({}, SURFACE, id="no palette"),
    pytest.param({"palette": COLORS}, SURFACE, id="palette"),
    pytest.param(
        {"palette": COLORS, "library": library(), "shade_range": (0, 255)},
        RAMPED,
        id="library",
    ),
]


def address(i=0):
    return FrameAddress("hero", sampling.VARIANT, "walk", 0, float(i))


def block(size, surfaces, depth_m=DEPTH_M):
    """One `size`×`size` block whose first `surfaces` samples, in raster
    order, show the surface; the rest show nothing."""
    count = size * size
    shown = (np.arange(count) < surfaces).reshape(size, size)
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    pixels[shown] = (*SURFACE, 255)
    identity = np.where(shown, 0, BACKGROUND).astype(np.int32)
    shade = np.where(shown, 100, 0).astype(np.uint8)
    normal = np.zeros((size, size, 3), dtype=np.float32)
    normal[shown] = (0.0, 0.0, 1.0)
    depth = np.where(shown, depth_m, np.nan).astype(np.float32)
    return pixels, identity, shade, normal, depth


def frame(*blocks):
    """A frame of blocks side by side."""
    parts = list(zip(*blocks, strict=True))
    pixels, identity, shade, normal, depth = (
        np.concatenate(part, axis=1) for part in parts
    )
    buffers = {IDENTITY: identity, SHADE: shade, NORMAL: normal, DEPTH: depth}
    return ImageFrame(address(), pixels, {}, buffers)


def reduced(look, variant, edges, *blocks):
    size = blocks[0][0].shape[0]
    (result,) = look(
        [frame(*blocks)],
        size,
        identities=IDENTITIES,
        pixels_per_meter=PPM,
        edges=edges,
        **variant,
    )
    return result


# The pinned cases (2×2 blocks unless said)

CASES = [
    # samples shown of four, hard's alpha, soft's alpha
    pytest.param(0, 0, 0, id="empty"),
    pytest.param(4, 255, 255, id="opaque"),
    pytest.param(1, 0, 64, id="one surface sample of four"),
    pytest.param(2, 255, 128, id="two surface samples of four"),
    pytest.param(3, 255, 191, id="three surface samples of four"),
]


@pytest.mark.parametrize(("surfaces", "hard", "soft"), CASES)
@pytest.mark.parametrize(("variant", "colour"), VARIANTS)
@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("edges", ["hard", "soft"])
def test_the_pinned_cases(look, variant, colour, edges, surfaces, hard, soft):
    result = reduced(look, variant, edges, block(2, surfaces))
    alpha = hard if edges == "hard" else soft
    expected = (*colour, alpha) if alpha else (0, 0, 0, 0)
    assert tuple(int(v) for v in result.pixels[0, 0]) == expected
    normal, depth = result.buffers[NORMAL_MAP][0, 0], result.buffers[DEPTH_MAP][0, 0]
    if alpha:
        assert tuple(normal) == (0.0, 0.0, 1.0)
        assert depth == DEPTH_M * PPM
    else:
        # No map pixel.
        assert tuple(normal) == (0.0, 0.0, 0.0) and depth == 0.0


@pytest.mark.parametrize(("variant", "colour"), VARIANTS)
@pytest.mark.parametrize("look", LOOKS)
def test_supersample_sixteen_reaches_soft_alpha_1_and_255(look, variant, colour):
    one = reduced(look, variant, "soft", block(16, 1))
    full = reduced(look, variant, "soft", block(16, 256))
    assert tuple(int(v) for v in one.pixels[0, 0]) == (*colour, 1)
    assert tuple(int(v) for v in full.pixels[0, 0]) == (*colour, 255)
    hard = reduced(look, variant, "hard", block(16, 1))
    assert tuple(int(v) for v in hard.pixels[0, 0]) == (0, 0, 0, 0)


@pytest.mark.parametrize(("variant", "colour"), VARIANTS)
@pytest.mark.parametrize("look", LOOKS)
def test_hard_keeps_todays_outlines_and_soft_gives_the_block_mean(
    look, variant, colour
):
    # Every count of surfaces from 0 to 9 in a 3×3 block.
    blocks = [block(3, k) for k in range(10)]
    hard = reduced(look, variant, "hard", *blocks).pixels[0]
    soft = reduced(look, variant, "soft", *blocks).pixels[0]
    for k in range(10):
        # Today's rule for opaque surfaces: kept at alpha 255 when at least
        # half the block shows one, 2k ≥ 9.
        today = (*colour, 255) if 2 * k >= 9 else (0, 0, 0, 0)
        assert tuple(int(v) for v in hard[k]) == today, k
        mean = (510 * 65535 * k + 65535 * 9) // (2 * 65535 * 9)
        assert tuple(int(v) for v in soft[k]) == ((*colour, mean) if mean else (0,) * 4)


# The maps' alpha (numerical reference step 5, D-11)

CELL = (4, 1)
SUBJECT = Subject(Path("/models/hero.glb"), "hero", 0, (Clip(0, "walk", 0.0, 0.5, ()),))
SELECTED = (SelectedClip(SUBJECT.clips[0], one_shot=False),)
GENERATOR = {"tool": "moskophoros", "version": "0.1.0"}
SOURCE = Source(Path("/models/hero.glb"), "ab" * 32, 0)


def _settings(supersample=2):
    return Settings(
        view="custom",
        direction=views.pitch_direction(0.0),
        directions=1,
        start_angle=0.0,
        model_yaw=0.0,
        fps=2.0,
        supersample=supersample,
        ppm=PPM,
        cell=CELL,
        ground=(0.0, 0.0, 0.0),
        ground_px=(2, 1),
        root_motion="error",
        shade=DEFAULT_SHADE,
    )


def _sheet(look, edges, depth_m=DEPTH_M):
    settings = _settings()
    view = views.View(settings.directions, settings.start_angle)
    (requested,) = sampling.frames("hero", SELECTED, view, settings.fps)
    one = frame(*(block(2, k, depth_m) for k in (1, 2, 3, 4)))
    captured = ImageFrame(requested.address, one.pixels, {}, one.buffers)
    frames = look([captured], 2, pixels_per_meter=PPM, edges=edges)
    sheet = export.encode(
        frames,
        generator=GENERATOR,
        source=SOURCE,
        subject="hero",
        settings=settings,
        style={"reduce": "plain", "edges": edges, "palette": None, "materials": None},
        selected_clips=SELECTED,
        image_path=Path("hero.png"),
        shade_range=(84, 191),
        depth=True,
    )
    return frames, sheet


def _decoded(data):
    with Image.open(io.BytesIO(data)) as image:
        return np.asarray(image)


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("edges", ["hard", "soft"])
def test_the_maps_alpha_follows_the_colours(look, edges):
    _, sheet = _sheet(look, edges)
    colour = _decoded(sheet.png)
    normal = _decoded(sheet.normal)
    depth = _decoded(sheet.depth)
    alpha = colour[..., 3]
    expected = [0, 255, 255, 255] if edges == "hard" else [64, 128, 191, 255]
    assert alpha[0].tolist() == expected
    # The normal map's alpha is the colour's, its direction unblended.
    assert np.array_equal(normal[..., 3], alpha)
    assert (normal[alpha > 0, :3] == imageops.encode_normal((0.0, 0.0, 1.0))).all()
    assert (normal[alpha == 0] == 0).all()
    # The depth map is non-zero exactly where alpha is above 0.
    assert np.array_equal(depth != 0, alpha > 0)
    assert (depth[alpha > 0] == export.DEPTH_ZERO + 16 * DEPTH_M * PPM).all()


@pytest.mark.parametrize("look", LOOKS)
def test_depth_overflow_applies_to_partial_pixels(look):
    # 300 m at 10 pixels per meter is beyond the depth map's 2047.9375 px,
    # on every block; under hard the one-in-four block shows no pixel, but
    # the others still overflow, and under soft it overflows too.
    for edges in ("hard", "soft"):
        with pytest.raises(export.DepthOverflow):
            _sheet(look, edges, depth_m=300.0)
    settings = _settings()
    view = views.View(settings.directions, settings.start_angle)
    (requested,) = sampling.frames("hero", SELECTED, view, settings.fps)
    # Only the partial block is deep: soft overflows, hard does not.
    deep = frame(block(2, 1, 300.0), block(2, 4), block(2, 4), block(2, 4))
    captured = ImageFrame(requested.address, deep.pixels, {}, deep.buffers)
    outcomes = {}
    for edges in ("hard", "soft"):
        frames = look([captured], 2, pixels_per_meter=PPM, edges=edges)
        try:
            export.encode(
                frames,
                generator=GENERATOR,
                source=SOURCE,
                subject="hero",
                settings=settings,
                style={},
                selected_clips=SELECTED,
                image_path=Path("hero.png"),
                shade_range=(84, 191),
                depth=True,
            )
        except export.DepthOverflow:
            outcomes[edges] = "overflow"
        else:
            outcomes[edges] = "written"
    assert outcomes == {"hard": "written", "soft": "overflow"}


def test_lighting_lights_a_partial_pixel_and_keeps_its_alpha():
    pixels = np.array([[(200, 40, 10, 64), (200, 40, 10, 255), (9, 9, 9, 0)]], np.uint8)
    normals = np.zeros((1, 3, 3), dtype=np.uint8)
    normals[:] = imageops.encode_normal((0.0, 0.0, 1.0))
    codes = np.full((1, 3), export.DEPTH_ZERO, dtype=np.uint16)
    # Intensity 0 lights by the ambient alone: every factor is 0.5.
    lit = imageops.light_pixels(pixels, normals, codes, (0, 1), (0, 0, 40), 0.0, 0.5)
    assert lit[0, 0, 3] == 64 and lit[0, 1, 3] == 255
    assert lit[0, 0, :3].tolist() == lit[0, 1, :3].tolist()
    assert lit[0, 0, :3].tolist() != [200, 40, 10]
    assert lit[0, 2].tolist() == [0, 0, 0, 0]
