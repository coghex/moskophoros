"""The images of an export: frame files, clip atlases and the combined sheet,
with their maps and stored-view previews, encoded from addressed frames and
the plans (export design P-7, parts 4 and 5; P-8, part 3; P-8a). Every frame
is generated in memory, with values that make a transposed row, a wrong
sample or an interpolated border visible."""

import io
import itertools
import random
from dataclasses import replace
from types import SimpleNamespace

import legacy_encoder
import numpy as np
import pytest
from PIL import Image, ImageSequence
from shading import DEFAULT_SHADE

from moskophoros import export, exportimages, imageops, outputs, plan, views
from moskophoros.capture.backend import Settings
from moskophoros.gltf import Clip, SelectedClip
from moskophoros.sampling import DEPTH_MAP, NORMAL_MAP, ImageFrame

W, H = 3, 2
RING8 = views.View(8, 0.0)
FITTED = SimpleNamespace(ppm=4.0, cell=(W, H), ground_px=(1, 2))
LIGHT = export.Light(position=(5.0, 7.0, 20.0), intensity=0.9, ambient=0.2)
TEMPLATES = {
    "frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
    "atlas_path": "atlases/{clip}{map}.png",
    "sheet_path": "sheet{map}.png",
}
SUBSETS = [
    subset
    for size in (1, 2, 3)
    for subset in itertools.combinations(("sheet", "frames", "atlases"), size)
]


def clip(index, name, t1=1.0, one_shot=False, count=None):
    return SelectedClip(Clip(index, name, 0.0, t1, ()), one_shot, count)


# The issue's example: walk has 2 samples over directions [4, 1], idle one
# sample over [0].
WALK = clip(0, "walk", count=2)
IDLE = clip(1, "idle", count=1)
TWO = (WALK, IDLE)
STORED = {"walk": [4, 1], "idle": [0]}


def make_request(clips=TWO, stored=STORED, fps=4, view=RING8, walk_mirrors=None):
    overrides = {
        name: plan.ClipOverride(stored_directions=value)
        for name, value in stored.items()
    }
    if walk_mirrors:
        overrides["walk"] = plan.ClipOverride(
            stored_directions=stored["walk"], mirrors=walk_mirrors
        )
    return plan.plan("hero", clips, view, fps, overrides=overrides)


def make_plan(
    request,
    formats,
    *,
    normals=True,
    depth=False,
    previews=True,
    lit=False,
    destination=None,
    view=RING8,
):
    names = outputs.resolve_names(
        [c.selected for c in request.clips], view, subject="hero"
    )
    return outputs.plan_outputs(
        request,
        names,
        SimpleNamespace(formats=tuple(formats), **TEMPLATES),
        destination=destination or outputs.Directory(),
        normals=normals,
        depth=depth,
        previews=previews,
        lit=lit,
    )


def make_frames(request, seed=1, shape=(H, W), depth_bound=100):
    """Distinct random cells: alpha 0, 1, 77 and 255 mixed, unit normals,
    depths in sixteenths, and a depth no map could hold under transparency."""
    rng = np.random.default_rng(seed)
    frames = []
    for frame in request.frames:
        pixels = rng.integers(0, 256, shape + (4,), dtype=np.uint8)
        pixels[..., 3] = rng.choice([0, 0, 1, 77, 255], size=shape)
        normals = rng.normal(size=shape + (3,))
        normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
        depths = np.round(rng.uniform(-depth_bound, depth_bound, shape) * 16) / 16
        depths[pixels[..., 3] == 0] = 5000.0
        frames.append(
            ImageFrame(
                frame.address, pixels, buffers={NORMAL_MAP: normals, DEPTH_MAP: depths}
            )
        )
    return frames


def run(
    request,
    frames,
    formats=("sheet",),
    *,
    padding=0,
    normals=True,
    depth=False,
    previews=True,
    light=export.NO_LIGHT,
    settings=FITTED,
    output_plan=None,
):
    lit = previews and light.position is not None
    output_plan = output_plan or make_plan(
        request, formats, normals=normals, depth=depth, previews=previews, lit=lit
    )
    return exportimages.encode(
        frames,
        request=request,
        output_plan=output_plan,
        settings=settings,
        formats=formats,
        atlas_padding=padding,
        normals=normals,
        depth=depth,
        previews=previews,
        light=light,
    )


def decode(artifact):
    image = Image.open(io.BytesIO(artifact.data))
    image.load()
    return image


def by_address(frames):
    return {f.address: f for f in frames}


# What each cell must hold, worked out here and not by the module.


def expected_color(frame):
    return frame.pixels


def expected_normal(frame):
    maps = frame.buffers[NORMAL_MAP]
    cell = np.zeros(frame.pixels.shape, dtype=np.uint8)
    for y, x in itertools.product(range(frame.pixels.shape[0]), range(W)):
        alpha = int(frame.pixels[y, x, 3])
        if alpha:
            cell[y, x, :3] = [
                int(np.floor(255 * (float(n) + 1) / 2 + 0.5)) for n in maps[y, x]
            ]
            cell[y, x, 3] = alpha
    return cell


def expected_depth(frame):
    depths = frame.buffers[DEPTH_MAP]
    cell = np.zeros(depths.shape, dtype=np.uint16)
    for y, x in itertools.product(range(depths.shape[0]), range(depths.shape[1])):
        if frame.pixels[y, x, 3]:
            cell[y, x] = 32768 + int(np.floor(16 * float(depths[y, x]) + 0.5))
    return cell


EXPECTED = {
    outputs.COLOR: expected_color,
    outputs.NORMAL: expected_normal,
    outputs.DEPTH: expected_depth,
}


def padded(cell, p):
    """`cell` with a border of `p` texels each repeating the nearest edge."""
    rows = np.clip(np.arange(-p, cell.shape[0] + p), 0, cell.shape[0] - 1)
    cols = np.clip(np.arange(-p, cell.shape[1] + p), 0, cell.shape[1] - 1)
    return cell[rows][:, cols]


def planned_keys(request, formats, channels, previews=True, lit=False):
    """The artifact order of P-8 part 3, listed independently."""
    keys = []
    if "sheet" in formats:
        keys += [("sheet", c, None, None, None) for c in channels]
    if "atlases" in formats:
        for item in request.clips:
            keys += [
                ("atlas", c, item.selected.clip.name, None, None) for c in channels
            ]
    if "frames" in formats:
        for item in request.clips:
            for frame in item.frames:
                for c in channels:
                    keys.append(
                        (
                            "frame",
                            c,
                            item.selected.clip.name,
                            frame.address.direction,
                            frame.index,
                        )
                    )
    for item in request.clips:
        name = item.selected.clip.name
        if previews:
            keys.append(("preview", "flat", name, None, None))
        if lit:
            keys.append(("preview", "lit", name, None, None))
    return keys


def key_of(artifact):
    return (
        artifact.kind,
        artifact.channel,
        artifact.clip,
        artifact.direction,
        artifact.index,
    )


# Artifacts, their order and the sample locations


@pytest.mark.parametrize("formats", SUBSETS)
@pytest.mark.parametrize(
    ("normals", "depth"), [(False, False), (True, False), (False, True), (True, True)]
)
@pytest.mark.parametrize("light", [export.NO_LIGHT, LIGHT])
def test_every_format_and_map_combination_has_its_artifacts_in_order(
    formats, normals, depth, light
):
    request = make_request()
    frames = make_frames(request)
    padding = 2
    result = run(
        request, frames, formats, padding=padding, normals=normals, depth=depth,
        light=light,
    )  # fmt: skip
    channels = ["color"] + ["normal"] * normals + ["depth"] * depth
    lit = light.position is not None
    assert [key_of(a) for a in result.artifacts] == planned_keys(
        request, formats, channels, lit=lit
    )
    output_plan = make_plan(request, formats, normals=normals, depth=depth, lit=lit)
    assert [a.path for a in result.artifacts] == [o.path for o in output_plan.artifacts]

    wanted = len(channels) * len(formats)
    by = by_address(frames)
    frame_of = {
        (f.address.clip, f.address.direction, f.index): f for f in request.frames
    }
    assert [(s.clip, s.direction, s.index) for s in result.samples] == [
        (f.address.clip, f.address.direction, f.index) for f in request.frames
    ]
    for sample in result.samples:
        address = frame_of[sample.clip, sample.direction, sample.index].address
        assert sample.time_s == address.time_s
        assert len(sample.locations) == wanted
        assert [loc.artifact for loc in sample.locations] == sorted(
            loc.artifact for loc in sample.locations
        )
        for location in sample.locations:
            artifact = result.artifacts[location.artifact]
            assert artifact.kind != "preview"
            assert (artifact.clip in (None, sample.clip)) and artifact.padding == (
                padding if artifact.kind == "atlas" else 0
            )
            if artifact.kind == "frame":
                assert (artifact.direction, artifact.index) == (
                    sample.direction,
                    sample.index,
                )
            assert (location.w, location.h) == (W, H) == artifact.cell
            image = np.array(decode(artifact))
            assert 0 <= location.x and location.x + location.w <= artifact.width
            assert 0 <= location.y and location.y + location.h <= artifact.height
            region = image[location.y : location.y + H, location.x : location.x + W]
            expected = EXPECTED[artifact.channel](by[address])
            assert np.array_equal(region, expected)


@pytest.mark.parametrize("formats", SUBSETS)
def test_shuffled_frames_give_identical_artifacts_and_samples(formats):
    request = make_request()
    frames = make_frames(request)
    first = run(request, frames, formats, depth=True, light=LIGHT, padding=1)
    shuffled = list(frames)
    random.Random(7).shuffle(shuffled)
    assert shuffled != frames
    assert run(request, shuffled, formats, depth=True, light=LIGHT, padding=1) == first


def test_mirror_declarations_add_no_image_sample_or_panel():
    plain = make_request()
    mirrored = make_request(walk_mirrors={7: 1, 6: 4})
    assert [c.mirrors for c in mirrored.clips][0] != ()
    frames = make_frames(plain)
    kwargs = {"normals": True, "depth": True, "light": LIGHT, "padding": 1}
    formats = ("sheet", "frames", "atlases")
    assert run(mirrored, frames, formats, **kwargs) == run(
        plain, frames, formats, **kwargs
    )


# Layouts


def test_the_issue_example_has_the_stated_sheet_atlas_and_frame_sizes():
    request = make_request()
    frames = make_frames(request)
    result = run(
        request, frames, ("sheet", "frames", "atlases"), padding=1, previews=False
    )
    sheet = next(a for a in result.artifacts if a.kind == "sheet")
    assert (sheet.width, sheet.height, sheet.padding) == (6, 6, 0)
    atlases = {a.clip: a for a in result.artifacts if a.kind == "atlas"}
    assert (atlases["walk"].width, atlases["walk"].height) == (10, 8)
    assert (atlases["idle"].width, atlases["idle"].height) == (5, 4)
    assert {a.padding for a in atlases.values()} == {1}
    for frame in (a for a in result.artifacts if a.kind == "frame"):
        assert (frame.width, frame.height, frame.padding) == (3, 2, 0)
        assert decode(frame).size == (3, 2)

    def places(clip_name, kind):
        return {
            (s.direction, s.index): (loc.x, loc.y)
            for s in result.samples
            if s.clip == clip_name
            for loc in s.locations
            if result.artifacts[loc.artifact].kind == kind
            and result.artifacts[loc.artifact].channel == "color"
            and (kind != "atlas" or result.artifacts[loc.artifact].clip == clip_name)
        }

    # Atlas x origins 1 and 6, y origins 1 and 5; rows follow [4, 1].
    assert places("walk", "atlas") == {
        (4, 0): (1, 1),
        (4, 1): (6, 1),
        (1, 0): (1, 5),
        (1, 1): (6, 5),
    }
    # Sheet rows follow clip order then stored order, never the direction index.
    assert places("walk", "sheet") == {
        (4, 0): (0, 0),
        (4, 1): (3, 0),
        (1, 0): (0, 2),
        (1, 1): (3, 2),
    }
    assert places("idle", "sheet") == {(0, 0): (0, 4)}


def test_the_sheet_holds_stored_rows_and_leaves_unused_cells_empty():
    request = make_request()
    frames = make_frames(request)
    by = by_address(frames)
    result = run(request, frames, ("sheet",), depth=True, previews=False)
    colour, normal, depth = (np.array(decode(a)) for a in result.artifacts)
    assert depth.dtype == np.uint16 and decode(result.artifacts[2]).mode == "I;16"
    # Last row (idle, direction 0): its one cell, then an empty second cell.
    address = request.clips[1].frames[0].address
    assert np.array_equal(colour[4:6, 0:3], by[address].pixels)
    for image in (colour, normal, depth):
        assert not image[4:6, 3:6].any()
    # Unequal stored subsets: walk direction 1 is the second row, not row 1*H.
    address = next(
        f.address for f in request.frames if (f.address.direction, f.index) == (1, 1)
    )
    assert np.array_equal(colour[2:4, 3:6], by[address].pixels)


@pytest.mark.parametrize("padding", [0, 1, 3, 64])
def test_atlas_padding_repeats_the_nearest_encoded_edge_texel(padding):
    request = make_request()
    frames = make_frames(request, seed=padding + 2)
    by = by_address(frames)
    result = run(
        request, frames, ("atlases",), padding=padding, depth=True, previews=False
    )
    slot_w, slot_h = W + 2 * padding, H + 2 * padding
    atlases = [a for a in result.artifacts if a.kind == "atlas"]
    assert len(atlases) == 6
    for atlas in atlases:
        item = next(c for c in request.clips if c.selected.clip.name == atlas.clip)
        image = np.array(decode(atlas))
        assert image.shape[:2] == (
            len(item.directions) * slot_h,
            item.sampling.frame_count * slot_w,
        )
        rows = {d.index: r for r, d in enumerate(item.directions)}
        for frame in item.frames:
            x = frame.index * slot_w
            y = rows[frame.address.direction] * slot_h
            cell = EXPECTED[atlas.channel](by[frame.address])
            assert np.array_equal(
                image[y : y + slot_h, x : x + slot_w], padded(cell, padding)
            )


def test_padding_never_blends_neighbouring_cells():
    request = make_request()
    frames = make_frames(request)
    result = run(request, frames, ("atlases",), padding=2, previews=False)
    colour = np.array(decode(result.artifacts[0]))
    # Two adjacent slots of the walk atlas share no texel values at their seam
    # beyond what each cell's own edge holds.
    left = colour[:, 0:7]
    right = colour[:, 7:14]
    assert np.array_equal(left[:, 6], left[:, 5])
    assert np.array_equal(right[:, 0], right[:, 1])


@pytest.mark.parametrize("padding", [0, 7])
def test_frames_and_the_sheet_ignore_atlas_padding(padding):
    request = make_request()
    frames = make_frames(request)
    formats = ("sheet", "frames")
    assert run(request, frames, formats, padding=padding, depth=True) == run(
        request, frames, formats, padding=0, depth=True
    )


# Encodings


def one_cell_run(pixels, normals, depths, **options):
    """A one-clip, one-direction, one-sample export of a single cell."""
    single = clip(0, "idle", count=1)
    request = plan.plan("hero", [single], views.View(1, 0.0), 4)
    address = request.frames[0].address
    height, width = pixels.shape[:2]
    frame = ImageFrame(
        address, pixels, buffers={NORMAL_MAP: normals, DEPTH_MAP: depths}
    )
    names = outputs.resolve_names([single], views.View(1, 0.0), subject="hero")
    output_plan = outputs.plan_outputs(
        request,
        names,
        SimpleNamespace(formats=("sheet",), **TEMPLATES),
        destination=outputs.Directory(),
        normals=options.get("normals", True),
        depth=options.get("depth", True),
        previews=options.get("previews", False),
        lit=options.get("previews", False)
        and options.get("light", export.NO_LIGHT).position is not None,
    )
    settings = SimpleNamespace(ppm=4.0, cell=(width, height), ground_px=(0, 1))
    return exportimages.encode(
        [frame],
        request=request,
        output_plan=output_plan,
        settings=settings,
        formats=("sheet",),
        **{"normals": True, "depth": True, "previews": False} | options,
    )


def test_normals_and_depths_follow_the_reference_encodings():
    pixels = np.array(
        [[[10, 20, 30, 255], [40, 50, 60, 128], [70, 80, 90, 0], [1, 2, 3, 255]]],
        dtype=np.uint8,
    )
    normals = np.array(
        [[[0, 0, 1], [1, 0, 0], [0, 1, 0], [-1, 0, 0]]], dtype=np.float64
    )
    depths = np.array([[0.0, 1.0, 5000.0, -2047.9375]])
    result = one_cell_run(pixels, normals, depths)
    colour, normal, depth = (np.array(decode(a)) for a in result.artifacts)
    assert np.array_equal(colour, pixels)
    assert normal.tolist() == [
        [[128, 128, 255, 255], [255, 128, 128, 128], [0, 0, 0, 0], [0, 128, 128, 255]]
    ]
    assert depth.tolist() == [[32768, 32784, 0, 1]]
    high = depths.copy()
    high[0, 3] = 2047.9375
    assert one_cell_run(pixels, normals, high).artifacts[2].data
    assert (
        np.array(decode(one_cell_run(pixels, normals, high).artifacts[2]))[0, 3]
        == 65535
    )


def test_covered_overflow_is_never_clamped_and_transparent_depth_is_ignored():
    pixels = np.array([[[10, 20, 30, 1], [10, 20, 30, 0]]], dtype=np.uint8)
    normals = np.zeros((1, 2, 3))
    normals[..., 2] = 1
    # Transparent: any depth is fine.
    ok = one_cell_run(pixels, normals, np.array([[0.0, 1e9]]))
    assert np.array(decode(ok.artifacts[2])).tolist() == [[32768, 0]]
    with pytest.raises(export.DepthOverflow) as raised:
        one_cell_run(pixels, normals, np.array([[2048.0, 0.0]]))
    assert raised.value.exit_code == 4
    ((address, (low, high)),) = raised.value.frames
    assert (address.clip, address.direction) == ("idle", 0)
    assert (low, high) == (2048.0, 2048.0)
    assert "'idle'" in str(raised.value) and "2048.0" in str(raised.value)


def test_overflow_lists_samples_in_plan_order_whatever_the_input_order():
    request = make_request()
    frames = make_frames(request)
    for frame in frames:
        frame.buffers[DEPTH_MAP][frame.pixels[..., 3] > 0] = 3000.0
    shuffled = list(reversed(frames))
    for given in (frames, shuffled):
        with pytest.raises(export.DepthOverflow) as raised:
            run(request, given, ("sheet",), depth=True)
        assert [a for a, _ in raised.value.frames] == [
            f.address for f in request.frames
        ]


def test_a_lit_preview_still_checks_depth_when_no_depth_file_is_written():
    request = make_request()
    frames = make_frames(request)
    frames[0].buffers[DEPTH_MAP][frames[0].pixels[..., 3] > 0] = 3000.0
    with pytest.raises(export.DepthOverflow):
        run(request, frames, ("sheet",), depth=False, light=LIGHT)
    # Without a light the same depth is never encoded.
    assert run(request, frames, ("sheet",), depth=False)


def test_disabled_outputs_need_no_maps():
    request = make_request()
    bare = [ImageFrame(f.address, f.pixels) for f in make_frames(request)]
    result = run(request, bare, ("sheet", "frames", "atlases"), normals=False)
    assert {a.channel for a in result.artifacts} == {"color", "flat"}
    with pytest.raises(ValueError, match="normal"):
        run(request, bare, ("sheet",), normals=True)
    with pytest.raises(ValueError, match="depth"):
        run(request, bare, ("sheet",), normals=False, depth=True)
    with pytest.raises(ValueError, match="normal"):
        run(request, bare, ("sheet",), normals=False, light=LIGHT)


def test_pngs_are_deterministic_without_text_or_time_chunks():
    request = make_request()
    frames = make_frames(request)
    result = run(request, frames, ("sheet", "frames", "atlases"), depth=True)
    for artifact in result.artifacts:
        if artifact.kind == "preview":
            continue
        data, chunks, offset = artifact.data, [], 8
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        while offset < len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            chunks.append(data[offset + 4 : offset + 8])
            offset += 12 + length
        assert set(chunks) <= {b"IHDR", b"IDAT", b"IEND"}
    assert result == run(request, frames, ("sheet", "frames", "atlases"), depth=True)


# Refusals


def test_wrong_frames_are_refused_with_their_address():
    request = make_request()
    frames = make_frames(request)
    address = frames[3].address
    with pytest.raises(ValueError, match="missing"):
        run(request, frames[:3] + frames[4:])
    with pytest.raises(ValueError, match="two frames have the address"):
        run(request, frames + [frames[3]])
    extra = ImageFrame(replace(address, direction=5), frames[3].pixels)
    with pytest.raises(ValueError, match="unrequested address") as raised:
        run(request, frames + [extra])
    assert "direction=5" in str(raised.value)
    for pixels in (
        np.zeros((H + 1, W, 4), dtype=np.uint8),
        np.zeros((H, W, 4), dtype=np.int16),
        np.zeros((H, W, 3), dtype=np.uint8),
    ):
        wrong = [replace(frames[0], pixels=pixels)] + frames[1:]
        with pytest.raises(ValueError, match="not uint8") as raised:
            run(request, wrong)
        assert str(frames[0].address) in str(raised.value)


def test_missing_or_wrong_shaped_maps_are_refused_with_their_address():
    request = make_request()
    frames = make_frames(request)
    for name, shape in ((NORMAL_MAP, (H, W)), (DEPTH_MAP, (H, W + 1))):
        broken = dict(frames[2].buffers)
        broken[name] = np.zeros(shape)
        wrong = [*frames[:2], replace(frames[2], buffers=broken), *frames[3:]]
        with pytest.raises(ValueError, match="map") as raised:
            run(request, wrong, depth=True)
        assert str(frames[2].address) in str(raised.value)


def test_unfitted_settings_and_odd_options_are_refused():
    request = make_request()
    frames = make_frames(request)
    for field in ("ppm", "cell", "ground_px"):
        unfitted = SimpleNamespace(**(vars(FITTED) | {field: None}))
        with pytest.raises(ValueError, match="not fitted"):
            run(request, frames, settings=unfitted)
    for padding in (-1, 65, 1.0, True, None):
        with pytest.raises(ValueError, match="padding"):
            run(request, frames, padding=padding)
    for formats in ((), ("sheet", "sheet"), ("sheet", "pdf")):
        with pytest.raises(ValueError, match="formats"):
            exportimages.encode(
                frames,
                request=request,
                output_plan=make_plan(request, ("sheet",)),
                settings=FITTED,
                formats=formats,
            )


def test_a_plan_that_is_not_the_options_plan_is_refused():
    request = make_request()
    frames = make_frames(request)
    with pytest.raises(ValueError, match="output plan"):
        run(
            request,
            frames,
            ("sheet", "frames"),
            output_plan=make_plan(request, ("sheet",)),
        )
    with pytest.raises(ValueError, match="output plan"):
        run(
            request,
            frames,
            ("sheet",),
            depth=True,
            output_plan=make_plan(request, ("sheet",)),
        )
    with pytest.raises(ValueError, match="output plan"):
        run(
            request,
            frames,
            ("sheet",),
            previews=False,
            output_plan=make_plan(request, ("sheet",)),
        )


# Previews


def blend(pixels):
    alpha = pixels[..., 3:4].astype(int)
    colour = pixels[..., :3].astype(int)
    return np.floor((colour * alpha + 128 * (255 - alpha)) / 255 + 0.5).astype(np.uint8)


def read_gif(artifact):
    image = decode(artifact)
    frames = []
    for page in ImageSequence.Iterator(image):
        frames.append((page.info["duration"], np.array(page.convert("RGB"))))
    assert image.info["loop"] == 0
    return frames


def panel(cells):
    return np.concatenate(
        [blend(c).repeat(4, axis=0).repeat(4, axis=1) for c in cells], axis=1
    )


def test_flat_and_lit_previews_show_each_clips_stored_views_in_order():
    request = make_request()
    frames = make_frames(request, seed=9)
    by = by_address(frames)
    result = run(request, frames, ("sheet",), light=LIGHT, depth=True)
    previews = [a for a in result.artifacts if a.kind == "preview"]
    assert [(a.clip, a.channel) for a in previews] == [
        ("walk", "flat"), ("walk", "lit"), ("idle", "flat"), ("idle", "lit"),
    ]  # fmt: skip
    for artifact in previews:
        item = next(c for c in request.clips if c.selected.clip.name == artifact.clip)
        assert (artifact.width, artifact.height) == (
            len(item.directions) * W * 4,
            H * 4,
        )
        assert artifact.padding is None and artifact.cell is None
        pages = read_gif(artifact)
        assert len(pages) == item.sampling.frame_count
        for k, (_, rgb) in enumerate(pages):
            cells = []
            for direction in item.directions:
                source = by[
                    next(
                        f.address
                        for f in item.frames
                        if f.address.direction == direction.index and f.index == k
                    )
                ]
                if artifact.channel == "lit":
                    normal = expected_normal(source)[..., :3]
                    codes = expected_depth(source)
                    cells.append(
                        imageops.light_pixels(
                            source.pixels, normal, codes, FITTED.ground_px,
                            LIGHT.position, LIGHT.intensity, LIGHT.ambient,
                        )
                    )  # fmt: skip
                else:
                    cells.append(source.pixels)
            assert np.array_equal(rgb, panel(cells))


def test_explicit_counts_keep_each_clips_own_rate_in_the_delays():
    walk = clip(0, "walk", count=6)
    run_clip = clip(1, "run", t1=2.0, count=4)
    request = plan.plan(
        "hero",
        [walk, run_clip],
        views.View(1, 0.0),
        12,
        overrides={
            "walk": plan.ClipOverride(fps=8),
            "run": plan.ClipOverride(fps=6),
        },
    )
    frames = make_frames(request)
    names = outputs.resolve_names([walk, run_clip], views.View(1, 0.0), subject="hero")
    output_plan = outputs.plan_outputs(
        request,
        names,
        SimpleNamespace(formats=("sheet",), **TEMPLATES),
        destination=outputs.Directory(),
        normals=False,
    )
    result = exportimages.encode(
        frames,
        request=request,
        output_plan=output_plan,
        settings=FITTED,
        formats=("sheet",),
        normals=False,
    )
    delays = {
        a.clip: [d for d, _ in read_gif(a)]
        for a in result.artifacts
        if a.kind == "preview"
    }
    assert delays == {"walk": [130] * 6, "run": [170] * 4}


def test_automatic_sampling_uses_its_resolved_duration_and_a_one_shot_holds():
    # d = 0.82 at 4 fps: n = floor(3.28 + 0.5) = 3, each frame 0.2733 s, so
    # 27 cs, not the 25 cs of 1/fps; the one-shot has 4 samples, the last
    # 500 ms longer.
    loop = clip(0, "loop", t1=0.82)
    once = clip(1, "once", t1=0.82, one_shot=True)
    still = clip(2, "still", t1=0.0, one_shot=True)
    request = plan.plan("hero", [loop, once, still], views.View(1, 0.0), 4)
    frames = make_frames(request)
    names = outputs.resolve_names(
        [loop, once, still], views.View(1, 0.0), subject="hero"
    )
    output_plan = outputs.plan_outputs(
        request,
        names,
        SimpleNamespace(formats=("sheet",), **TEMPLATES),
        destination=outputs.Directory(),
        normals=False,
    )
    result = exportimages.encode(
        frames,
        request=request,
        output_plan=output_plan,
        settings=FITTED,
        formats=("sheet",),
        normals=False,
    )
    delays = {
        a.clip: [d for d, _ in read_gif(a)]
        for a in result.artifacts
        if a.kind == "preview"
    }
    assert delays == {
        "loop": [270] * 3,
        "once": [270, 270, 270, 770],
        "still": [750],
    }


def test_identical_consecutive_samples_stay_separate_gif_frames():
    request = make_request()
    frames = make_frames(request)
    same = {}
    for frame in frames:
        key = (frame.address.clip, frame.address.direction)
        same.setdefault(key, frame.pixels)
    frames = [
        replace(f, pixels=same[f.address.clip, f.address.direction]) for f in frames
    ]
    result = run(request, frames, ("sheet",), normals=False)
    walk = next(a for a in result.artifacts if a.clip == "walk")
    pages = read_gif(walk)
    assert len(pages) == 2 and np.array_equal(pages[0][1], pages[1][1])


def test_preview_bytes_do_not_depend_on_padding_or_the_selected_png_formats():
    request = make_request()
    frames = make_frames(request)

    def previews(formats, padding):
        result = run(request, frames, formats, padding=padding, light=LIGHT, depth=True)
        return [a for a in result.artifacts if a.kind == "preview"]

    base = previews(("sheet",), 0)
    assert base == previews(("frames", "atlases"), 5) == previews(("atlases",), 64)
    assert len(base) == 4


def test_previews_off_and_no_light_encode_no_gifs():
    request = make_request()
    frames = make_frames(request)
    off = run(request, frames, ("sheet",), previews=False, light=LIGHT)
    assert [a.kind for a in off.artifacts] == ["sheet", "sheet"]
    unlit = run(request, frames, ("sheet",))
    assert [a.channel for a in unlit.artifacts if a.kind == "preview"] == ["flat"] * 2


def test_a_preview_over_256_colours_warns_by_clip_and_kind():
    side = 20
    single = clip(0, "big", count=1)
    request = plan.plan("hero", [single], views.View(1, 0.0), 4)
    rng = np.random.default_rng(3)
    pixels = rng.integers(0, 256, (side, side, 4), dtype=np.uint8)
    pixels[..., 3] = 255
    normals = np.zeros((side, side, 3))
    normals[..., 2] = 1
    frame = ImageFrame(
        request.frames[0].address,
        pixels,
        buffers={NORMAL_MAP: normals, DEPTH_MAP: np.zeros((side, side))},
    )
    names = outputs.resolve_names([single], views.View(1, 0.0), subject="hero")
    output_plan = outputs.plan_outputs(
        request,
        names,
        SimpleNamespace(formats=("sheet",), **TEMPLATES),
        destination=outputs.Directory(),
        normals=False,
        lit=True,
    )
    result = exportimages.encode(
        [frame],
        request=request,
        output_plan=output_plan,
        settings=SimpleNamespace(ppm=4.0, cell=(side, side), ground_px=(0, 0)),
        formats=("sheet",),
        normals=False,
        light=LIGHT,
    )
    flat, lit = (a for a in result.artifacts if a.kind == "preview")
    assert flat.warnings == (
        "clip 'big''s preview has frames with more than 256 colors, reduced to "
        "256 without dithering",
    )
    assert lit.warnings == (
        "clip 'big''s lit preview has frames with more than 256 colors, reduced to "
        "256 without dithering",
    )
    assert all(not a.warnings for a in result.artifacts if a.kind != "preview")


def preview_only_run(cell_width, fps, count=1):
    single = clip(0, "wide", count=count)
    request = plan.plan("hero", [single], views.View(1, 0.0), fps)
    names = outputs.resolve_names([single], views.View(1, 0.0), subject="hero")
    output_plan = outputs.plan_outputs(
        request,
        names,
        SimpleNamespace(formats=("sheet",), **TEMPLATES),
        destination=outputs.Directory(),
        normals=False,
    )
    frames = [
        ImageFrame(f.address, np.zeros((1, cell_width, 4), dtype=np.uint8))
        for f in request.frames
    ]
    return exportimages.encode(
        frames,
        request=request,
        output_plan=output_plan,
        settings=SimpleNamespace(ppm=4.0, cell=(cell_width, 1), ground_px=(0, 0)),
        formats=("sheet",),
        normals=False,
    )


def test_gif_limits_are_usage_errors_naming_the_clip():
    assert preview_only_run(16_383, 4)
    with pytest.raises(export.UsageError, match="'wide'.*65536 pixels wide") as raised:
        preview_only_run(16_384, 4)
    assert raised.value.exit_code == 2
    with pytest.raises(export.UsageError, match="'wide'.*ms, over GIF's limit"):
        preview_only_run(1, 1e-4)


# The default bytes, as the sheet encoder wrote them before the schema switch
#
# `legacy_encoder` is a frozen copy of the encoder that this encoder replaced
# (commit 4a22102519). Both sides compress with the same library, so the
# comparison holds on every platform, unlike a digest of a PNG, which depends
# on the zlib build. It pins design D-3: the default sheet, maps and previews
# never change a byte.


LEGACY = Settings(
    view="side",
    direction=views.pitch_direction(0.0),
    directions=2,
    start_angle=90.0,
    model_yaw=0.0,
    fps=3.0,
    supersample=4,
    ppm=24.5,
    cell=(W, H),
    ground=(0.0, 0.0, 0.0),
    ground_px=(1, 2),
    root_motion="error",
    shade=DEFAULT_SHADE,
)


@pytest.mark.parametrize("light", [export.NO_LIGHT, LIGHT])
@pytest.mark.parametrize(
    ("normals", "depth"), [(False, False), (True, False), (True, True)]
)
def test_default_bytes_equal_the_legacy_encoder_on_identical_inputs(
    light, normals, depth
):
    selected = [
        clip(0, "läuft"),
        clip(1, "攻撃", t1=1.0, one_shot=True),
        clip(2, "pose", t1=0.0),
    ]
    view = views.View(LEGACY.directions, LEGACY.start_angle, LEGACY.model_yaw)
    request = plan.plan("héros", selected, view, LEGACY.fps)
    frames = make_frames(request, seed=11)
    legacy = legacy_encoder.sheet(
        frames,
        subject="héros",
        settings=LEGACY,
        selected_clips=selected,
        normals=normals,
        depth=depth,
    )
    lit = light.position is not None
    names = outputs.resolve_names(selected, view, subject="héros", directory=False)
    output_plan = outputs.plan_outputs(
        request,
        names,
        SimpleNamespace(formats=("sheet",), **TEMPLATES),
        destination=outputs.Positional("out/héros.png"),
        normals=normals,
        depth=depth,
        lit=lit,
    )
    result = exportimages.encode(
        frames,
        request=request,
        output_plan=output_plan,
        settings=LEGACY,
        formats=("sheet",),
        normals=normals,
        depth=depth,
        light=light,
    )
    sheets = [a for a in result.artifacts if a.kind == "sheet"]
    assert sheets[0].data == legacy.png
    if normals:
        assert sheets[1].data == legacy.normal
    if depth:
        assert sheets[-1].data == legacy.depth
    flat = legacy_encoder.previews(
        frames, subject="héros", settings=LEGACY, selected_clips=selected
    )
    expected = [(p.clip, "flat", p.gif, p.warnings) for p in flat]
    if lit:
        lit_set = legacy_encoder.lit_previews(
            frames,
            subject="héros",
            settings=LEGACY,
            selected_clips=selected,
            light=light,
        )
        expected = [
            entry
            for pair in zip(
                expected,
                [(p.clip, "lit", p.gif, p.warnings) for p in lit_set],
                strict=True,
            )
            for entry in pair
        ]
    assert [
        (a.clip, a.channel, a.data, a.warnings)
        for a in result.artifacts
        if a.kind == "preview"
    ] == expected
