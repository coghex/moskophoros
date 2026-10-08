"""Palette selection, composition and provenance, with generated inputs only."""

import hashlib
import json
import math
import shutil
import subprocess
import tracemalloc
import weakref
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image
from test_capture_backend import raw_png
from test_command import Setup, run
from test_reuse import edited, write_sheet

from moskophoros import cli, export, imageops, stylize
from moskophoros.sampling import FrameAddress, ImageFrame

COLORS = ((0, 0, 0), (255, 0, 0), (255, 255, 255))
RECORD = {
    "source": "gone.hex",
    "sha256": "ab" * 32,
    "colors": ["#000000", "#ff0000", "#ffffff"],
}


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def palette_file(tmp_path, colors=COLORS):
    path = tmp_path / "test.hex"
    path.write_text("".join(bytes(color).hex() + "\n" for color in colors))
    return path


def scalar_lab(rgb):
    # Independent scalar reference for the published OKLab matrices.
    linear = [
        c / 255 / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4
        for c in rgb
    ]
    r, g, b = linear
    l_root = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_root + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l_root - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l_root + 0.7827717662 * m - 0.8086757660 * s,
    )


def nearest(rgb, colors):
    point = scalar_lab(rgb)
    return min(
        colors,
        key=lambda c: sum(
            (a - b) ** 2 for a, b in zip(point, scalar_lab(c), strict=True)
        ),
    )


def test_mapping_matches_independent_oklab_reference_and_preserves_alpha():
    colors = ((12, 244, 31), (71, 22, 250), (200, 155, 12), (240, 90, 93))
    pixels = np.random.default_rng(19).integers(0, 256, (17, 19, 4), dtype=np.uint8)
    pixels[0, 0] = (19, 20, 21, 0)
    before = pixels.copy()
    result = imageops.map_palette(pixels, colors)
    expected = [
        [[*(nearest(p[:3], colors) if p[3] else (0, 0, 0)), p[3]] for p in row]
        for row in pixels
    ]
    assert result.tolist() == expected
    np.testing.assert_array_equal(pixels, before)
    assert not np.shares_memory(pixels, result)
    assert any(
        nearest(p[:3], colors)
        != min(
            colors,
            key=lambda c: sum((int(a) - b) ** 2 for a, b in zip(p[:3], c, strict=True)),
        )
        for row in pixels
        for p in row
    )


def test_exact_distance_tie_keeps_earlier_entry_without_an_epsilon(monkeypatch):
    # Controlled coordinates exercise an exact floating-point tie between
    # distinct valid RGB entries; reversing the order must reverse the choice.
    def lab(rgb):
        return np.stack(
            (
                rgb[..., 0].astype(float),
                np.zeros(rgb.shape[:-1]),
                np.zeros(rgb.shape[:-1]),
            ),
            axis=-1,
        )

    monkeypatch.setattr(imageops, "_oklab", lab)
    pixels = np.array([[[10, 0, 0, 128], [11, 0, 0, 255]]], dtype=np.uint8)
    colors = ((0, 0, 0), (20, 0, 0))
    assert imageops.map_palette(pixels, colors)[0, :, 0].tolist() == [0, 20]
    assert imageops.map_palette(pixels, colors[::-1])[0, :, 0].tolist() == [20, 20]


def test_mapping_work_memory_does_not_multiply_pixels_by_palette_size():
    pixels = np.full((512, 512, 4), 255, dtype=np.uint8)
    colors = [(i, 0, 0) for i in range(255)]
    tracemalloc.start()
    try:
        mapped = imageops.map_palette(pixels, colors)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert mapped.shape == pixels.shape
    assert peak < 24 * 1024 * 1024  # A pixels × palette distance table exceeds 500 MB.


@pytest.mark.parametrize(
    "pixels", [np.zeros((2, 2, 3), dtype=np.uint8), np.zeros((2, 2, 4), dtype=float)]
)
def test_mapping_rejects_invalid_images(pixels):
    with pytest.raises((ValueError, TypeError)):
        imageops.map_palette(pixels, COLORS)


def test_mode_pools_shades_before_voting_and_plain_maps_after_averaging():
    pixels = np.array(
        [
            [[10, 10, 10, 255], [11, 11, 11, 255], [12, 12, 12, 255]],
            [[10, 10, 10, 255], [11, 11, 11, 255], [12, 12, 12, 255]],
            [[255, 255, 255, 255]] * 3,
        ],
        dtype=np.uint8,
    )
    frame = ImageFrame(FrameAddress("s", "default", "walk", 1, 0), pixels, {"test": 1})
    colors = ((0, 0, 0), (255, 255, 255))
    assert stylize.mode([frame], 3)[0].pixels.tolist() == [[[255, 255, 255, 255]]]
    assert stylize.mode([frame], 3, palette=colors)[0].pixels.tolist() == [
        [[0, 0, 0, 255]]
    ]
    # The mean maps to black; mapping before averaging yields an intermediate,
    # which is outside this palette. Compare the published composition directly.
    expected = imageops.map_palette(imageops.reduce_blocks(pixels, 3), colors)
    np.testing.assert_array_equal(
        stylize.plain([frame], 3, palette=colors)[0].pixels, expected
    )


@pytest.mark.parametrize("look", [stylize.plain, stylize.mode])
def test_paletted_stages_keep_silhouette_addresses_and_metadata_one_frame_at_a_time(
    look, monkeypatch
):
    events = []
    original = imageops.map_palette

    def mapped(pixels, colors):
        events.append("map")
        return original(pixels, colors)

    monkeypatch.setattr(imageops, "map_palette", mapped)
    pixels = np.random.default_rng(24).integers(0, 256, (8, 8, 4), dtype=np.uint8)
    pixels[:2, :2] = (100, 20, 40, 0)
    frames = [
        ImageFrame(
            FrameAddress("s", "default", "walk", i, float(i)), pixels.copy(), {"i": i}
        )
        for i in (2, 0, 1)
    ]

    def capture():
        for frame in frames:
            events.append("load")
            yield frame

    result = look(capture(), 2, palette=COLORS)
    assert events == ["load", "map"] * 3
    for frame, output in zip(frames, result, strict=True):
        assert output.address == frame.address
        assert output.metadata is frame.metadata
        np.testing.assert_array_equal(
            output.pixels[..., 3], imageops.reduce_blocks(frame.pixels, 2)[..., 3]
        )
        assert set(map(tuple, output.pixels[output.pixels[..., 3] != 0, :3])) <= set(
            COLORS
        )
        assert set(np.unique(output.pixels[..., 3])) <= {0, 255}
        np.testing.assert_array_equal(frame.pixels, pixels)


@pytest.mark.parametrize("look", [stylize.plain, stylize.mode])
def test_a_stage_releases_the_previous_capture_before_loading_the_next(look):
    def capture():
        previous = None
        for i in range(3):
            if previous is not None:
                assert previous() is None
            pixels = np.full((8, 8, 4), 255, dtype=np.uint8)
            previous = weakref.ref(pixels)
            yield ImageFrame(FrameAddress("s", "default", "walk", i, float(i)), pixels)
            del pixels

    assert len(look(capture(), 2, palette=COLORS)) == 3


@pytest.mark.parametrize(
    "args",
    [
        ("--palette", "a.hex", "--palette", "b.hex"),
        ("--no-palette", "--no-palette"),
        ("--palette", "a.hex", "--no-palette"),
    ],
)
def test_palette_option_conflicts_and_repeats_are_usage_errors(args, capsys):
    with pytest.raises(cli.UsageError):
        cli.parse_args([*args, "model.glb", "out.png"])
    assert "moskophoros: error:" in capsys.readouterr().err


def test_palette_parsing_does_not_read_files(tmp_path):
    path = tmp_path / "absent.hex"
    options = cli.parse_args(["--palette", str(path), "model.glb", "out.png"])
    assert options.palette_file == path
    assert options.explicit == {"palette"}
    assert options.palette is None
    dropped = cli.parse_args(["--no-palette", "model.glb", "out.png"])
    assert dropped.no_palette and dropped.explicit == {"no_palette"}


@pytest.mark.parametrize(
    "kind",
    [
        "absent",
        "suffix",
        "malformed",
        "duplicate",
        "empty",
        "too-many",
        "png-alpha",
        "png-broken",
        "png-empty-iccp",
    ],
)
def test_palette_errors_precede_every_blender_invocation_including_version(
    setup, capsys, monkeypatch, kind
):
    path = setup.tmp_path / ("bad.png" if kind.startswith("png") else "bad.hex")
    if kind == "suffix":
        path = path.with_suffix(".txt")
    if kind != "absent":
        if kind == "png-alpha":
            Image.new("RGBA", (1, 1), (1, 2, 3, 254)).save(path)
        elif kind == "png-empty-iccp":
            raw_png(path, 8, 6, 8, 6, 4, [(b"iCCP", b"")])
        else:
            content = {
                "malformed": "000000\nbad",
                "duplicate": "000000\n000000",
                "empty": "",
                "too-many": "\n".join(f"{i:06x}" for i in range(256)),
            }.get(kind, "bad")
            path.write_text(content)

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Blender was invoked, including a possible --version probe"
        )

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    status, out, err = run(capsys, setup.argv("--palette", str(path)))
    assert (status, out) == (2, "")
    assert str(path) in err
    assert "Traceback" not in err
    assert "internal error" not in err
    if kind in {"malformed", "duplicate"}:
        assert "line 2" in err
    assert setup.listing() == {}


@pytest.mark.parametrize(
    "change",
    [
        {"source": ""},
        {"source": "a/b.hex"},
        {"source": "a\\b.hex"},
        {"source": ".."},
        {"sha256": "AB" * 32},
        {"sha256": "a" * 63},
        {"colors": []},
        {"colors": ["#ABCDEF"]},
        {"colors": ["ffffff"]},
        {"colors": ["#000000"] * 2},
        {"colors": [f"#{i:06x}" for i in range(256)]},
        {"colors": [1]},
        {"colors": "#000000"},
        {"colors": None},
        {"source": None},
        {"sha256": None},
        {"extra": 0},
    ],
)
@pytest.mark.parametrize(
    "override",
    [(), ("--reduce", "mode"), ("--no-palette",), ("--palette", "replacement.hex")],
)
def test_invalid_reused_palette_is_checked_before_all_overrides(
    tmp_path, capsys, monkeypatch, change, override
):
    path = write_sheet(tmp_path, edited({"style.palette": RECORD | change}))

    def forbidden(*args, **kwargs):
        raise AssertionError("a process ran before rejecting reused palette")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert (
        cli.run(["--settings-from", str(path), *override, "model.glb", "out.png"]) == 2
    )
    err = capsys.readouterr().err
    assert str(path) in err and "settings.style.palette." in err


@pytest.mark.parametrize("member", ["source", "sha256", "colors"])
def test_reused_palette_requires_every_member(tmp_path, capsys, member):
    record = {k: v for k, v in RECORD.items() if k != member}
    path = write_sheet(tmp_path, edited({"style.palette": record}))
    with pytest.raises(cli.UsageError):
        cli.read_settings(path)
    assert f"settings.style.palette.{member}: missing" in capsys.readouterr().err


def test_palette_reuse_and_overrides_do_not_need_original_file(tmp_path):
    path = write_sheet(
        tmp_path, edited({"style.palette": RECORD, "style.reduce": "mode"})
    )

    def resolve(*args):
        return cli.resolve_settings(
            cli.parse_args(
                ["--settings-from", str(path), *args, "model.glb", "out.png"]
            )
        )

    unmaterialed = {"materials": None, "shade_range": [84, 191]}
    assert (
        cli.style_record(resolve())
        == {
            "reduce": "mode",
            "palette": RECORD,
        }
        | unmaterialed
    )
    assert (
        cli.style_record(resolve("--reduce", "plain"))
        == {
            "reduce": "plain",
            "palette": RECORD,
        }
        | unmaterialed
    )
    assert (
        cli.style_record(resolve("--no-palette"))
        == {
            "reduce": "mode",
            "palette": None,
        }
        | unmaterialed
    )
    replacement = palette_file(tmp_path, ((1, 2, 3),))
    record = cli.style_record(resolve("--palette", str(replacement)))["palette"]
    assert record == {
        "source": replacement.name,
        "sha256": hashlib.sha256(replacement.read_bytes()).hexdigest(),
        "colors": ["#010203"],
    }
    assert list(record) == ["source", "sha256", "colors"]


def test_fingerprint_changes_with_palette_colors_and_order_with_same_provenance():
    options = cli.parse_args(["model.glb", "out.png"])
    record = cli.PaletteRecord("same.hex", "ab" * 32, COLORS)
    records = [
        record,
        replace(record, colors=COLORS[::-1]),
        replace(record, colors=((1, 0, 0), *COLORS[1:])),
    ]
    fingerprints = []
    for item in records:
        style = cli.style_record(replace(options, palette=item))
        fingerprints.append(export.fingerprint({}, {"style": style}, "cd" * 32))
    assert len(set(fingerprints)) == 3


@pytest.mark.parametrize("look", ["plain", "mode"])
def test_paletted_command_is_deterministic_reuses_inline_colors_and_leaves_jobs_unchanged(
    setup, capsys, look
):
    path = palette_file(setup.tmp_path)
    work = setup.tmp_path / "work"
    args = setup.argv("--reduce", look, "--work-dir", str(work))
    assert run(capsys, args) == (0, "", "")
    jobs = [(work / phase / "job.json").read_bytes() for phase in ("measure", "render")]
    unpaletted_alpha = np.asarray(Image.open(setup.png))[..., 3].copy()
    shutil.rmtree(work)
    paletted = [*args, "--palette", str(path)]
    assert run(capsys, paletted) == (0, "", "")
    before = setup.listing()
    assert jobs == [
        (work / phase / "job.json").read_bytes() for phase in ("measure", "render")
    ]
    sheet = json.loads(setup.json.read_text())
    record = sheet["settings"]["style"]["palette"]
    assert record["source"] == path.name
    assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    pixels = np.asarray(Image.open(setup.png))
    np.testing.assert_array_equal(pixels[..., 3], unpaletted_alpha)
    assert set(map(tuple, pixels[pixels[..., 3] != 0, :3])) <= set(COLORS)
    path.unlink()
    shutil.rmtree(work)
    assert run(capsys, setup.argv("--settings-from", str(setup.json))) == (0, "", "")
    assert setup.listing() == before


@pytest.mark.parametrize("look", ["plain", "mode"])
def test_full_palette_previews_keep_exact_colors_without_warning(setup, capsys, look):
    colors = tuple((i, 0, 255 - i) for i in range(255))
    path = palette_file(setup.tmp_path, colors)
    setup.configure(pixels="noise")
    assert run(capsys, setup.argv("--reduce", look, "--palette", str(path))) == (
        0,
        "",
        "",
    )
    allowed = set(colors) | {(128, 128, 128)}
    for gif in (setup.walk_gif, setup.attack_gif):
        with Image.open(gif) as image:
            for i in range(image.n_frames):
                image.seek(i)
                actual = set(image.convert("RGB").get_flattened_data())
                assert actual <= allowed


@pytest.mark.parametrize("suffix", [".HEX", ".GPL", ".PNG"])
def test_command_reads_every_palette_format_and_hashes_the_parsed_snapshot(
    setup, capsys, suffix
):
    path = setup.tmp_path / ("colors" + suffix)
    if suffix == ".HEX":
        path.write_text("000000\nff0000\nffffff\n")
    elif suffix == ".GPL":
        path.write_text("GIMP Palette\n0 0 0 black\n255 0 0 red\n255 255 255 white\n")
    else:
        image = Image.new("RGB", (3, 1))
        image.putdata(COLORS)
        image.save(path)
    assert run(capsys, setup.argv("--palette", str(path))) == (0, "", "")
    record = json.loads(setup.json.read_text())["settings"]["style"]["palette"]
    assert record == {
        "source": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "colors": RECORD["colors"],
    }
