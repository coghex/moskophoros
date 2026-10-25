"""The configurable export through the whole command, with the fake Blender:
both destination forms, every format combination, per-clip rates, counts and
stored directions, and the exact samples the capture jobs carry (export design
P-7, P-8, P-9; EXP-6b).

Blender is faked, so these tests inspect the jobs it is given and the files
the command writes; what the pixels look like is the real-Blender tests'.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from glb_writer import GlbWriter
from PIL import Image, ImageSequence
from test_command import Setup, run

from moskophoros import cli

BASE = ["--supersample", "1", "--cell", "16x16"]
FORMATS = ["sheet", "frames", "atlases"]
# The seven nonempty format combinations, in the canonical order.
COMBINATIONS = [
    ("sheet",),
    ("frames",),
    ("atlases",),
    ("sheet", "frames"),
    ("sheet", "atlases"),
    ("frames", "atlases"),
    ("sheet", "frames", "atlases"),
]


def clock_model(directory):
    """`hero.glb` with a one-second loop `walk` and a two-second loop
    `idle`, both in place."""
    model = GlbWriter()
    hips = model.node("hips", mesh=True)
    arm = model.node(None, mesh=True, translation=(0.2, 0.5, 0.0))
    model.scene([hips, arm], default=True)
    model.animation(
        "walk", [(hips, "translation", [0.0, 1.0], [(0, 0, 0), (0, 0.01, 0)])]
    )
    model.animation(
        "idle", [(arm, "translation", [0.0, 2.0], [(0.2, 0.5, 0), (0.2, 0.51, 0)])]
    )
    return model.write(directory, "hero")


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


@pytest.fixture
def clocks(tmp_path):
    (tmp_path / "clocks").mkdir()
    return clock_model(tmp_path / "clocks")


def config(tmp_path, text, name="config.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def to_dir(setup, out, *options, model=None):
    """The arguments of a directory run of `model` (default: the setup's)."""
    return [
        *BASE,
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model if model is None else model),
        "--output-dir",
        str(out),
    ]


def to_png(setup, png, *options, model=None):
    return [
        *BASE,
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model if model is None else model),
        str(png),
    ]


def tree(root):
    """Every file under `root` as a path relative to it, with its bytes."""
    root = Path(root)
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def read_manifest(root):
    return json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))


def jobs(work):
    """The measure and render jobs of a retained work directory."""
    return {
        mode: json.loads((Path(work) / mode / "job.json").read_text(encoding="utf-8"))
        for mode in ("measure", "render")
    }


def modes(setup):
    return [call["mode"] for call in setup.calls()]


# The destination


def test_exactly_one_destination_is_required(setup, capsys, tmp_path):
    both = [*BASE, "--blender", str(setup.fake), str(setup.model)]
    status, _, err = run(capsys, [*both, str(setup.png), "--output-dir", "out"])
    assert status == 2
    assert "give either <outfile.png> or --output-dir, not both" in err
    status, _, err = run(capsys, both)
    assert status == 2
    assert "a destination is required: give <outfile.png>, or --output-dir" in err
    assert setup.calls() == []


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("sheet,sheet", "'sheet' is listed twice in 'sheet,sheet'"),
        ("", "'' is not one of them"),
        ("sheet,", "'' is not one of them"),
        ("sheet,pdf", "'pdf' is not one of them"),
        ("Sheet", "'Sheet' is not one of them"),
    ],
)
def test_a_bad_formats_list_is_a_usage_error_before_capture(
    setup, capsys, tmp_path, value, problem
):
    status, _, err = run(capsys, to_dir(setup, tmp_path / "out", "--formats", value))
    assert status == 2
    assert problem in err
    assert setup.calls() == []


def test_formats_are_given_once_and_normalised(setup, capsys, tmp_path):
    status, _, err = run(
        capsys,
        to_dir(setup, tmp_path / "out", "--formats", "sheet", "--formats", "frames"),
    )
    assert status == 2 and "given more than once" in err
    options = cli.parse_args(
        ["--formats", "atlases,sheet,frames", "hero.glb", "--output-dir", "out"]
    )
    assert options.formats == ("sheet", "frames", "atlases")
    assert options.outfile is None and options.output_dir == Path("out")
    assert "formats" in options.explicit


def test_a_destination_may_follow_the_options_in_any_order(tmp_path):
    options = cli.parse_args(["hero.glb", "--fps", "4", "out.png"])
    assert (options.infile, options.outfile) == (Path("hero.glb"), Path("out.png"))
    options = cli.parse_args(["--output-dir", "out", "--fps", "4", "hero.glb"])
    assert (options.infile, options.output_dir) == (Path("hero.glb"), Path("out"))


@pytest.mark.parametrize(
    "how",
    [
        ["--formats", "frames"],
        ["--formats", "atlases,sheet"],
        ["--config", "{config}"],
    ],
)
def test_other_formats_with_a_png_need_the_directory_form(setup, capsys, tmp_path, how):
    how = [
        str(config(tmp_path, "export: {formats: [frames, sheet]}\n"))
        if part == "{config}"
        else part
        for part in how
    ]
    status, _, err = run(capsys, to_png(setup, setup.png, *how))
    assert status == 2
    assert "need an output directory: give --output-dir" in err
    assert setup.calls() == [] and setup.listing() == {}


def test_a_png_with_the_sheet_format_is_the_ordinary_run(setup, capsys):
    status, _, err = run(capsys, to_png(setup, setup.png, "--formats", "sheet"))
    assert (status, err) == (0, "")
    assert modes(setup) == ["measure", "render"]
    assert json.loads(setup.json.read_text())["settings"]["export"]["formats"] == [
        "sheet"
    ]


# Every combination


def expected_kinds(formats, clips):
    kinds = set()
    if "sheet" in formats:
        kinds.add("sheet")
    if "frames" in formats:
        kinds.add("frame")
    if "atlases" in formats:
        kinds.add("atlas")
    return kinds | {"preview"}


@pytest.mark.parametrize("formats", COMBINATIONS)
def test_each_format_combination_writes_its_files_from_one_capture(
    setup, capsys, tmp_path, formats
):
    out = tmp_path / "export"
    status, _, err = run(
        capsys,
        to_dir(setup, out, "--formats", ",".join(formats), "--depth"),
    )
    assert (status, err) == (0, "")
    # One measure pass and one render pass, whatever is written.
    assert modes(setup) == ["measure", "render"]
    document = read_manifest(out)
    assert document["settings"]["export"]["formats"] == list(formats)
    assert {a["kind"] for a in document["artifacts"]} == expected_kinds(formats, 2)
    files = tree(out)
    assert set(files) == {a["path"] for a in document["artifacts"]} | {"manifest.json"}
    # Maps accompany every enabled format.
    for kind in expected_kinds(formats, 2) - {"preview"}:
        channels = {a["channel"] for a in document["artifacts"] if a["kind"] == kind}
        assert channels == {"color", "normal", "depth"}


def test_the_defaults_write_a_sheet_in_the_directory(setup, capsys, tmp_path):
    out = tmp_path / "export"
    assert run(capsys, to_dir(setup, out))[0] == 0
    document = read_manifest(out)
    paths = [a["path"] for a in document["artifacts"]]
    assert paths == [
        "sheet.png",
        "sheet.normal.png",
        "previews/walk.gif",
        "previews/attack.gif",
    ]
    assert document["settings"]["export"]["sheet_path"] == "sheet{map}.png"


def test_a_directory_run_and_a_png_run_describe_the_same_settings(
    setup, capsys, tmp_path
):
    out = tmp_path / "export"
    assert run(capsys, to_dir(setup, out))[0] == 0
    assert run(capsys, to_png(setup, setup.png))[0] == 0
    directory, positional = read_manifest(out), json.loads(setup.json.read_text())
    assert directory["settings"] == positional["settings"]
    assert directory["fingerprint"] == positional["fingerprint"]
    assert tree(out)["sheet.png"] == setup.png.read_bytes()


# Per-clip rates, counts and stored directions

EXAMPLE = """\
stored_directions: [0, 4, 3, 2, 1]
mirrors: {7: 1, 6: 2, 5: 3}
export:
  formats: [frames, atlases]
clips:
  walk: {frames: 6, fps: 8}
  idle: {frames: 4, fps: 6, stored_directions: all, mirrors: {}}
"""


def example_run(setup, capsys, tmp_path, clocks, *extra):
    out, work = tmp_path / "export", tmp_path / "work"
    argv = to_dir(
        setup,
        out,
        *["--config", str(config(tmp_path, EXAMPLE))],
        *["--work-dir", str(work), "--clip", "walk", "--clip", "idle"],
        *extra,
        model=clocks,
    )
    status, _, err = run(capsys, argv)
    assert status == 0, err
    return out, jobs(work)


def addresses(job):
    return [
        (
            f["address"]["clip"],
            f["address"]["direction"],
            f["index"],
            f["address"]["time_s"],
            f["angle_deg"],
        )
        for f in job["frames"]
    ]


def test_unequal_rates_counts_and_subsets_request_exactly_their_samples(
    setup, capsys, tmp_path, clocks
):
    out, both = example_run(setup, capsys, tmp_path, clocks)
    stored = [0, 4, 3, 2, 1]
    expected = [("walk", d, k, k / 6, d * 45.0) for d in stored for k in range(6)] + [
        ("idle", d, k, k / 2, d * 45.0) for d in range(8) for k in range(4)
    ]
    assert len(expected) == 30 + 32
    for mode in ("measure", "render"):
        got = addresses(both[mode])
        assert [g[:3] for g in got] == [e[:3] for e in expected], mode
        for g, e in zip(got, expected, strict=True):
            assert g[3] == pytest.approx(e[3], abs=1e-12), (mode, g)
            assert g[4] == e[4]
    # No mirrored direction was captured.
    walk_directions = {a[1] for a in addresses(both["render"]) if a[0] == "walk"}
    assert walk_directions == set(stored)
    document = read_manifest(out)
    walk, idle = document["clips"]
    assert (walk["fps"], idle["fps"]) == (8.0, 6.0)
    assert (walk["frame_count"], idle["frame_count"]) == (6, 4)
    assert walk["frame_duration_s"] == pytest.approx(1 / 8)
    assert idle["frame_duration_s"] == pytest.approx(1 / 6)
    assert walk["time_scale"] == pytest.approx(8 / 6)
    assert idle["time_scale"] == pytest.approx(3.0)
    assert walk["stored_directions"] == stored
    assert [m["target"] for m in walk["mirrors"]] == [5, 6, 7]
    assert idle["stored_directions"] == list(range(8)) and idle["mirrors"] == []
    times = {
        (f["clip"], f["direction"], f["index"]): f["time_s"] for f in document["frames"]
    }
    assert times[("walk", 4, 3)] == pytest.approx(0.5)
    assert times[("idle", 7, 3)] == pytest.approx(1.5)
    # Samples are the jobs' addresses, in the same order.
    assert [(f["clip"], f["direction"], f["index"]) for f in document["frames"]] == [
        a[:3] for a in addresses(both["render"])
    ]


def test_the_previews_have_only_stored_rows_and_each_clips_cadence(
    setup, capsys, tmp_path, clocks
):
    out, _ = example_run(setup, capsys, tmp_path, clocks)
    document = read_manifest(out)
    cell = document["settings"]["cell"]["width"]
    widths = {
        a["clip"]: a["width"] for a in document["artifacts"] if a["kind"] == "preview"
    }
    assert widths == {"walk": 5 * cell * 4, "idle": 8 * cell * 4}
    for name, delay in (("walk", 130), ("idle", 170)):
        with Image.open(out / "previews" / f"{name}.gif") as gif:
            durations = [f.info["duration"] for f in ImageSequence.Iterator(gif)]
        assert durations == [delay] * (6 if name == "walk" else 4), name


def test_every_representation_holds_the_same_logical_pixels(
    setup, capsys, tmp_path, clocks
):
    out = tmp_path / "export"
    argv = to_dir(
        setup,
        out,
        *["--config", str(config(tmp_path, EXAMPLE))],
        *["--formats", "sheet,frames,atlases", "--depth"],
        *["--clip", "walk", "--clip", "idle"],
        model=clocks,
    )
    assert run(capsys, argv)[0] == 0
    document = read_manifest(out)
    images = {}

    def pixels(index):
        if index not in images:
            path = out / document["artifacts"][index]["path"]
            with Image.open(path) as image:
                images[index] = np.asarray(image)
        return images[index]

    checked = 0
    for sample in document["frames"]:
        crops = []
        for place in sample["locations"]:
            artifact = document["artifacts"][place["artifact"]]
            crop = pixels(place["artifact"])[
                place["y"] : place["y"] + place["h"],
                place["x"] : place["x"] + place["w"],
            ]
            crops.append((artifact["channel"], artifact["kind"], crop))
        by_channel = {}
        for channel, kind, crop in crops:
            by_channel.setdefault(channel, []).append((kind, crop))
        assert set(by_channel) == {"color", "normal", "depth"}
        for channel, found in by_channel.items():
            assert {k for k, _ in found} == {"sheet", "atlas", "frame"}
            first = found[0][1]
            for _, crop in found[1:]:
                assert np.array_equal(first, crop), (sample, channel)
            checked += 1
    assert checked == 3 * (30 + 32)


def test_atlas_padding_repeats_the_nearest_edge_texel_including_corners(
    setup, capsys, tmp_path, clocks
):
    out = tmp_path / "export"
    padded = EXAMPLE.replace(
        "  formats: [frames, atlases]\n",
        "  formats: [frames, atlases]\n  atlas_padding: 2\n",
    )
    argv = to_dir(
        setup,
        out,
        *["--config", str(config(tmp_path, padded))],
        *["--clip", "walk", "--clip", "idle"],
        model=clocks,
    )
    status, _, err = run(capsys, argv)
    assert status == 0, err
    document = read_manifest(out)
    atlas = next(
        a
        for a in document["artifacts"]
        if a["kind"] == "atlas" and a["clip"] == "walk" and a["channel"] == "color"
    )
    assert atlas["padding"] == 2
    cell_w, cell_h = atlas["cell"]["width"], atlas["cell"]["height"]
    assert atlas["width"] == 6 * (cell_w + 4) and atlas["height"] == 5 * (cell_h + 4)
    with Image.open(out / atlas["path"]) as image:
        pixels = np.asarray(image)
    slot_w, slot_h = cell_w + 4, cell_h + 4
    for row in range(5):
        for column in range(6):
            slot = pixels[
                row * slot_h : (row + 1) * slot_h,
                column * slot_w : (column + 1) * slot_w,
            ]
            inner = slot[2 : 2 + cell_h, 2 : 2 + cell_w]
            expected = np.pad(inner, ((2, 2), (2, 2), (0, 0)), mode="edge")
            assert np.array_equal(slot, expected), (row, column)


def test_adding_formats_does_not_change_the_captured_frames(
    setup, capsys, tmp_path, clocks
):
    work_a, work_b = tmp_path / "work-a", tmp_path / "work-b"
    for work, formats in ((work_a, "sheet"), (work_b, "sheet,frames,atlases")):
        argv = to_dir(
            setup,
            tmp_path / f"out-{formats}",
            *["--config", str(config(tmp_path, EXAMPLE, f"{formats}.yaml"))],
            *["--formats", formats, "--work-dir", str(work)],
            *["--clip", "walk", "--clip", "idle"],
            model=clocks,
        )
        assert run(capsys, argv)[0] == 0
    assert jobs(work_a)["render"]["frames"] == jobs(work_b)["render"]["frames"]
    assert modes(setup) == ["measure", "render"] * 2


# The capture stays isolated


def test_the_jobs_keep_their_settings_keys_whatever_the_export_asks(
    setup, capsys, tmp_path, clocks
):
    _, both = example_run(setup, capsys, tmp_path, clocks)
    plain = tmp_path / "plain-work"
    argv = to_png(setup, tmp_path / "plain.png", "--work-dir", str(plain))
    assert run(capsys, argv)[0] == 0
    plain_jobs = jobs(plain)
    for mode in ("measure", "render"):
        assert list(both[mode]["settings"]) == list(plain_jobs[mode]["settings"])
        assert list(both[mode]) == list(plain_jobs[mode])
        text = json.dumps(both[mode]["settings"])
        for word in ("mirror", "stored", "formats", "atlas", "output_name", "path"):
            assert word not in text, word
        # Only the existing per-clip keys travel.
        assert all(
            sorted(clip) == ["frames", "loop", "name"]
            for clip in both[mode]["settings"]["clips"]
        )


def test_the_global_rate_does_not_time_a_clip_with_its_own(
    setup, capsys, tmp_path, clocks
):
    times = {}
    for rate in ("2", "30"):
        work = tmp_path / f"work-{rate}"
        argv = to_dir(
            setup,
            tmp_path / f"out-{rate}",
            *["--config", str(config(tmp_path, EXAMPLE, f"c{rate}.yaml"))],
            *["--fps", rate, "--work-dir", str(work)],
            *["--clip", "walk", "--clip", "idle"],
            model=clocks,
        )
        status, _, err = run(capsys, argv)
        assert status == 0, err
        job = jobs(work)["render"]
        times[rate] = [(a[0], a[2], a[3]) for a in addresses(job)]
        assert job["settings"]["fps"] == float(rate)
    assert times["2"] == times["30"]


def test_the_manifest_records_what_the_files_set(setup, capsys, tmp_path, clocks):
    out, _ = example_run(setup, capsys, tmp_path, clocks)
    settings = read_manifest(out)["settings"]
    assert settings["stored_directions"] == [0, 4, 3, 2, 1]
    assert settings["mirrors"] == [
        {"target": 5, "source": 3},
        {"target": 6, "source": 2},
        {"target": 7, "source": 1},
    ]
    assert settings["export"]["formats"] == ["frames", "atlases"]
    walk, idle = settings["clips"]
    assert (walk["fps"], walk["frames"], walk["stored_directions"]) == (8.0, 6, None)
    assert (idle["fps"], idle["stored_directions"], idle["mirrors"]) == (6.0, "all", [])


# Warnings


def warnings_of(err):
    return [
        line.removeprefix("moskophoros: warning: ")
        for line in err.splitlines()
        if line.startswith("moskophoros: warning: ")
    ]


def fps_warnings_of(err):
    return [w for w in warnings_of(err) if "does not reach the clips" in w]


def mirror_warnings_of(err):
    return [w for w in warnings_of(err) if "is not a reflection" in w]


SHADOWING = "clips:\n  walk: {fps: 8}\n  attack: {fps: 4}\n  gone: {fps: 2}\n"


def test_an_option_fps_is_shadowed_by_a_clips_own_and_one_warning_lists_them(
    setup, capsys, tmp_path
):
    cfg = config(tmp_path, SHADOWING)
    status, _, err = run(
        capsys, to_dir(setup, tmp_path / "o", "--config", str(cfg), "--fps", "4")
    )
    assert status == 0, err
    # An equal value warns too; an entry for a clip the model lacks does not.
    assert fps_warnings_of(err) == [
        'the global fps 4.0 does not reach the clips with their own: "walk" (8.0), '
        '"attack" (4.0)'
    ]


def test_a_project_files_fps_is_shadowed_too(setup, capsys, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "moskophoros" / "projects").mkdir(parents=True)
    (home / "moskophoros" / "projects" / "look.yaml").write_text(
        "fps: 6\nclips:\n  walk: {fps: 6}\n", encoding="utf-8"
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    status, _, err = run(
        capsys, to_dir(setup, tmp_path / "o", "--project", "look", "--no-user-config")
    )
    assert status == 0, err
    assert fps_warnings_of(err) == [
        'the global fps 6.0 does not reach the clips with their own: "walk" (6.0)'
    ]


def test_default_global_file_and_reused_rates_warn_nothing(setup, capsys, tmp_path):
    first = tmp_path / "first"
    # The shipped default, with a clip rate: nothing to shadow.
    cfg = config(tmp_path, "clips:\n  walk: {fps: 8}\n")
    argv = [
        *["--supersample", "1", "--cell", "16x16", "--config", str(cfg)],
        *["--blender", str(setup.fake), str(setup.model), "--output-dir", str(first)],
    ]
    status, _, err = run(capsys, argv)
    assert status == 0, err
    assert fps_warnings_of(err) == []
    # The global file's own fps, over the clip's.
    cfg = config(tmp_path, "fps: 6\nclips:\n  walk: {fps: 8}\n", "global.yaml")
    status, _, err = run(
        capsys, to_dir(setup, tmp_path / "second", "--config", str(cfg))
    )
    assert status == 0 and fps_warnings_of(err) == []
    # A reused fps: the loaded manifest's, whatever a clip says.
    status, _, err = run(
        capsys,
        to_dir(
            setup,
            tmp_path / "third",
            *["--settings-from", str(first / "manifest.json"), "--no-user-config"],
        ),
    )
    assert status == 0 and fps_warnings_of(err) == []


def test_a_still_clip_with_its_own_rate_is_named(setup, capsys, tmp_path):
    (tmp_path / "still").mkdir()
    model = GlbWriter()
    model.scene([model.node("body", mesh=True)], default=True)
    still = model.write(tmp_path / "still", "hero")
    cfg = config(tmp_path, "clips:\n  static: {fps: 3}\n")
    status, _, err = run(
        capsys,
        to_dir(setup, tmp_path / "o", "--config", str(cfg), "--fps", "5", model=still),
    )
    assert status == 0, err
    assert fps_warnings_of(err) == [
        'the global fps 5.0 does not reach the clips with their own: "static" (3.0)'
    ]


def mirror_run(setup, capsys, tmp_path, mirrors, *options):
    cfg = config(
        tmp_path,
        f"stored_directions: [0, 1, 2, 3, 4, 5, 6]\nmirrors: {mirrors}\n",
    )
    out = tmp_path / "out"
    status, _, err = run(
        capsys, to_dir(setup, out, "--config", str(cfg), "--once", "attack", *options)
    )
    assert status == 0, err
    return err, out


@pytest.mark.parametrize("yaw", ["0", "90", "30"])
def test_a_correct_mirror_pair_never_warns_whatever_the_facing_correction(
    setup, capsys, tmp_path, yaw
):
    err, out = mirror_run(setup, capsys, tmp_path, "{7: 1}", "--model-yaw", yaw)
    assert mirror_warnings_of(err) == []
    assert [m["target"] for m in read_manifest(out)["clips"][0]["mirrors"]] == [7]


@pytest.mark.parametrize("yaw", ["0", "90"])
def test_a_wrong_angle_pair_warns_once_per_clip_and_still_exports(
    setup, capsys, tmp_path, yaw
):
    err, out = mirror_run(setup, capsys, tmp_path, "{7: 2}", "--model-yaw", yaw)
    messages = mirror_warnings_of(err)
    # One per selected clip and pair, listing the failed condition.
    assert len(messages) == 2
    assert messages[0].startswith('clip "walk" mirror 7 <- 2 is not a reflection: ')
    assert messages[1].startswith('clip "attack" mirror 7 <- 2 is not a reflection: ')
    assert "do not sum to 0 modulo 360" in messages[0]
    assert [m["source"] for m in read_manifest(out)["clips"][0]["mirrors"]] == [2]


def test_a_rolled_camera_and_a_wrong_pair_share_one_warning(setup, capsys, tmp_path):
    err, _ = mirror_run(setup, capsys, tmp_path, "{7: 2}", "--camera-roll", "0.5")
    (walk, attack) = mirror_warnings_of(err)
    for message in (walk, attack):
        assert "the camera roll 0.5 is not 0, 1 or -1 half turns" in message
        assert "do not sum to 0 modulo 360" in message
        assert message.count("; ") == 1


def test_a_roll_of_one_half_turn_is_no_failure(setup, capsys, tmp_path):
    err, _ = mirror_run(setup, capsys, tmp_path, "{7: 1}", "--camera-roll", "1")
    assert mirror_warnings_of(err) == []


def test_the_perspective_camera_beside_its_heading_plane_warns(setup, capsys, tmp_path):
    err, _ = mirror_run(
        setup,
        capsys,
        tmp_path,
        "{7: 1}",
        *["--projection", "perspective", "--camera-position", "0.5,2,3"],
        *["--camera-direction", "0,-0.6,-0.8"],
    )
    messages = mirror_warnings_of(err)
    assert len(messages) == 2
    assert "m to the side of its heading plane" in messages[0]
    err, _ = mirror_run(
        setup,
        capsys,
        tmp_path,
        "{7: 1}",
        *["--projection", "perspective", "--camera-position", "0,2,3"],
        *["--camera-direction", "0,-0.6,-0.8"],
    )
    assert mirror_warnings_of(err) == []


def test_a_mirror_of_an_unselected_clip_warns_nothing(setup, capsys, tmp_path):
    cfg = config(
        tmp_path,
        "stored_directions: [0, 1, 2, 3, 4, 5, 6]\n"
        "clips:\n  attack: {mirrors: {7: 2}}\n",
    )
    status, _, err = run(
        capsys,
        to_dir(setup, tmp_path / "o", "--config", str(cfg), "--clip", "walk"),
    )
    assert status == 0, err
    assert mirror_warnings_of(err) == []


# Names and paths


def test_directory_names_are_refused_before_capture_and_the_png_form_keeps_its_own(
    setup, capsys, tmp_path
):
    cfg = config(
        tmp_path,
        "clips:\n  walk: {output_name: aux}\n  attack: {output_name: AUX}\n",
    )
    status, _, err = run(capsys, to_dir(setup, tmp_path / "o", "--config", str(cfg)))
    assert status == 2
    assert "aux" in err and setup.calls() == []
    assert not (tmp_path / "o").exists()
    # The positional form checks no directory name, and the manifest carries
    # the informational names, equal as they are.
    status, _, err = run(capsys, to_png(setup, setup.png, "--config", str(cfg)))
    assert status == 0, err
    names = [c["output_name"] for c in json.loads(setup.json.read_text())["clips"]]
    assert names == ["aux", "AUX"]
    assert "hero.walk.gif" in setup.listing()


def test_colliding_names_and_paths_are_usage_errors_before_capture(
    setup, capsys, tmp_path
):
    for text, word in [
        (
            "clips:\n  walk: {output_name: same}\n  attack: {output_name: SAME}\n",
            "same",
        ),
        ("direction_names: {1: a, 2: A}\n", "direction"),
        (
            "export: {formats: [frames], frame_path: 'f/{clip}.png'}\n",
            "would both write",
        ),
        ("export: {atlas_path: 'a/{clip}.png'}\n", "would both write"),
        (
            "export: {sheet_path: 'dir{map}.png', "
            "frame_path: 'dir.png/{clip}-{direction}-{frame}{map}.png'}\n",
            "needs as a directory",
        ),
    ]:
        cfg = config(tmp_path, text)
        status, _, err = run(
            capsys,
            to_dir(
                setup,
                tmp_path / "o",
                *["--config", str(cfg), "--formats", "sheet,frames,atlases"],
            ),
        )
        assert status == 2, text
        assert word in err, (text, err)
    assert setup.calls() == [] and not (tmp_path / "o").exists()


def test_an_unusable_expanded_path_names_its_template_and_address(
    setup, capsys, tmp_path
):
    cfg = config(tmp_path, "export: {sheet_path: 'out/{map}/sheet.png'}\n")
    status, _, err = run(capsys, to_dir(setup, tmp_path / "o", "--config", str(cfg)))
    assert status == 2
    assert "export.sheet_path 'out/{map}/sheet.png' gives" in err
    assert "empty component" in err
    assert setup.calls() == []


def test_templates_are_syntax_checked_even_in_the_png_form(setup, capsys, tmp_path):
    cfg = config(tmp_path, "export: {frame_path: 'f/{nope}.png'}\n")
    status, _, err = run(capsys, to_png(setup, setup.png, "--config", str(cfg)))
    assert status == 2 and setup.calls() == []
    assert "frame_path" in err


def test_a_changed_view_cannot_silently_drop_a_stored_direction(
    setup, capsys, tmp_path
):
    cfg = config(tmp_path, "stored_directions: [0, 4]\n")
    status, _, err = run(
        capsys,
        to_dir(setup, tmp_path / "o", "--config", str(cfg), "--directions", "4"),
    )
    assert status == 2
    assert "the direction 4 is not one of the view's 4 directions" in err
    assert setup.calls() == []


# Ownership, preflight and publication


def first_export(setup, capsys, tmp_path, *options, name="export"):
    out = tmp_path / name
    status, _, err = run(capsys, to_dir(setup, out, *options))
    assert status == 0, err
    return out


def test_a_rerun_of_the_same_subject_replaces_its_files_and_keeps_the_rest(
    setup, capsys, tmp_path, clocks
):
    out = first_export(
        setup, capsys, tmp_path, "--formats", "sheet,frames,atlases", "--depth"
    )
    (out / "notes.txt").write_text("not an output", encoding="utf-8")
    before = tree(out)
    # A different model of the same subject, writing less.
    status, _, err = run(capsys, to_dir(setup, out, "--formats", "sheet", model=clocks))
    assert status == 0, err
    after = tree(out)
    assert after["notes.txt"] == before["notes.txt"]
    # Stale frames and atlases stay; the manifest names only this run's files.
    assert {p for p in before if p.startswith(("frames/", "atlases/"))} <= set(after)
    assert all(after[p] == before[p] for p in before if p.startswith("frames/"))
    paths = {a["path"] for a in read_manifest(out)["artifacts"]}
    assert not any(p.startswith(("frames/", "atlases/")) for p in paths)
    assert (
        read_manifest(out)["source"]["sha256"]
        != json.loads(json.dumps(read_manifest(out)))["fingerprint"]
    )


def test_a_manifest_of_another_subject_is_refused_before_capture(
    setup, capsys, tmp_path
):
    out = first_export(setup, capsys, tmp_path)
    before = tree(out)
    other = tmp_path / "other"
    other.mkdir()
    (other / "stranger.glb").write_bytes(setup.model.read_bytes())
    calls = len(setup.calls())
    status, _, err = run(capsys, to_dir(setup, out, model=other / "stranger.glb"))
    assert status == 2
    assert "subject" in err and "hero" in err
    assert len(setup.calls()) == calls and tree(out) == before


@pytest.mark.parametrize(
    "content",
    [b"{", b"[]", b'{"schema": "moskophoros.export/1"}', b'{"subject": 3}'],
)
def test_a_manifest_that_cannot_establish_the_subject_is_refused(
    setup, capsys, tmp_path, content
):
    out = tmp_path / "export"
    out.mkdir()
    (out / "manifest.json").write_bytes(content)
    status, _, err = run(capsys, to_dir(setup, out))
    assert status == 2
    assert "manifest.json" in err
    assert setup.calls() == [] and tree(out) == {"manifest.json": content}


def test_an_unreadable_manifest_is_an_output_error(setup, capsys, tmp_path):
    out = tmp_path / "export"
    out.mkdir()
    manifest = out / "manifest.json"
    manifest.write_bytes(b"{}")
    manifest.chmod(0)
    try:
        status, _, err = run(capsys, to_dir(setup, out))
    finally:
        manifest.chmod(0o644)
    assert status == 6
    assert setup.calls() == []


def test_a_root_needs_an_existing_parent_and_must_not_be_a_file(
    setup, capsys, tmp_path
):
    status, _, err = run(capsys, to_dir(setup, tmp_path / "missing" / "export"))
    assert status == 2 and not (tmp_path / "missing").exists()
    (tmp_path / "file").write_text("x", encoding="utf-8")
    status, _, err = run(capsys, to_dir(setup, tmp_path / "file"))
    assert status == 2 and (tmp_path / "file").read_text(encoding="utf-8") == "x"
    assert setup.calls() == []


def test_a_new_root_is_created_with_the_directories_the_paths_need(
    setup, capsys, tmp_path
):
    out = tmp_path / "fresh"
    assert not out.exists()
    status, _, err = run(capsys, to_dir(setup, out, "--formats", "frames"))
    assert status == 0, err
    assert (out / "frames" / "walk" / "south" / "frame_000.png").is_file()


def test_a_link_below_the_root_is_never_followed_and_an_ancestor_link_is(
    setup, capsys, tmp_path
):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    out = tmp_path / "export"
    out.mkdir()
    (out / "frames").symlink_to(elsewhere)
    status, _, err = run(capsys, to_dir(setup, out, "--formats", "frames"))
    assert status == 2 and list(elsewhere.iterdir()) == []
    assert setup.calls() == []
    # The root's own ancestors may be links.
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "linked").symlink_to(real)
    status, _, err = run(capsys, to_dir(setup, tmp_path / "linked" / "export"))
    assert status == 0, err
    assert (real / "export" / "manifest.json").is_file()


def test_a_directory_where_a_file_goes_is_refused(setup, capsys, tmp_path):
    out = tmp_path / "export"
    (out / "sheet.png").mkdir(parents=True)
    status, _, err = run(capsys, to_dir(setup, out))
    assert status == 2 and setup.calls() == []


def test_an_input_cannot_be_replaced_by_the_export(setup, capsys, tmp_path):
    out = tmp_path / "export"
    out.mkdir()
    palette = out / "sheet.png"
    Image.new("RGBA", (2, 1), (10, 20, 30, 255)).save(palette)
    before = palette.read_bytes()
    status, _, err = run(capsys, to_dir(setup, out, "--palette", str(palette)))
    assert status == 2
    assert "sheet.png" in err
    assert setup.calls() == [] and palette.read_bytes() == before


def test_the_loaded_manifest_may_be_replaced_in_place_in_both_forms(
    setup, capsys, tmp_path
):
    out = first_export(
        setup, capsys, tmp_path, "--formats", "sheet,frames", "--depth", "--no-preview"
    )
    before = tree(out)
    status, _, err = run(
        capsys,
        to_dir(
            setup,
            out,
            *["--settings-from", str(out / "manifest.json"), "--no-user-config"],
        ),
    )
    assert status == 0, err
    assert tree(out) == before
    # The positional form replaces its own JSON.
    status, _, err = run(capsys, to_png(setup, setup.png))
    assert status == 0, err
    before = setup.listing()
    status, _, err = run(
        capsys,
        to_png(setup, setup.png, *["--settings-from", str(setup.json)]),
    )
    assert status == 0, err
    assert setup.listing() == before


def test_a_failed_publication_is_an_output_error_that_restores_the_files(
    setup, capsys, tmp_path, monkeypatch
):
    import os

    out = first_export(setup, capsys, tmp_path, "--formats", "sheet,frames")
    before = tree(out)
    real = os.replace
    seen = []

    def failing(source, target, *args, **kwargs):
        seen.append(target)
        if len(seen) == 5:
            raise OSError(28, "No space left on device")
        return real(source, target, *args, **kwargs)

    monkeypatch.setattr(os, "replace", failing)
    argv = to_dir(setup, out, "--formats", "sheet,frames", "--model-yaw", "90")
    status, _, err = run(capsys, argv)
    assert status == 6, err
    assert "No space left on device" in err
    monkeypatch.undo()
    assert tree(out) == before


def test_an_interruption_during_publication_is_130_and_restores_the_files(
    setup, capsys, tmp_path, monkeypatch
):
    import os

    out = first_export(setup, capsys, tmp_path, "--formats", "sheet,frames")
    before = tree(out)
    real = os.replace
    seen = []

    def interrupted(source, target, *args, **kwargs):
        seen.append(target)
        if len(seen) == 3:
            raise KeyboardInterrupt
        return real(source, target, *args, **kwargs)

    monkeypatch.setattr(os, "replace", interrupted)
    status, _, err = run(
        capsys, to_dir(setup, out, "--formats", "sheet,frames", "--model-yaw", "90")
    )
    monkeypatch.undo()
    assert status == 130, err
    assert tree(out) == before


# Replay


def test_a_manifest_alone_restores_the_export_in_a_fresh_root(
    setup, capsys, tmp_path, clocks
):
    cfg = config(
        tmp_path,
        EXAMPLE.replace(
            "  formats: [frames, atlases]\n",
            "  formats: [frames, atlases]\n  atlas_padding: 1\n",
        ),
    )
    first = tmp_path / "first"
    argv = to_dir(
        setup,
        first,
        *["--config", str(cfg), "--clip", "walk", "--clip", "idle", "--depth"],
        *["--formats", "sheet,frames,atlases"],
        model=clocks,
    )
    assert run(capsys, argv)[0] == 0
    cfg.unlink()
    second = tmp_path / "second"
    status, _, err = run(
        capsys,
        to_dir(
            setup,
            second,
            *["--settings-from", str(first / "manifest.json"), "--no-user-config"],
            model=clocks,
        ),
    )
    assert status == 0, err
    assert tree(second) == tree(first)
    # And in place.
    before = tree(first)
    status, _, err = run(
        capsys,
        to_dir(
            setup,
            first,
            *["--settings-from", str(first / "manifest.json"), "--no-user-config"],
            model=clocks,
        ),
    )
    assert status == 0, err
    assert tree(first) == before


def test_a_frames_manifest_needs_the_sheet_format_to_become_a_png(
    setup, capsys, tmp_path
):
    out = first_export(setup, capsys, tmp_path, "--formats", "frames")
    path = str(out / "manifest.json")
    status, _, err = run(
        capsys, to_png(setup, setup.png, "--settings-from", path, "--no-user-config")
    )
    assert status == 2 and "need an output directory" in err
    calls = len(setup.calls())
    status, _, err = run(
        capsys,
        to_png(
            setup,
            setup.png,
            *["--settings-from", path, "--no-user-config", "--formats", "sheet"],
        ),
    )
    assert status == 0, err
    assert len(setup.calls()) == calls + 2
    replayed = json.loads(setup.json.read_text())
    assert replayed["settings"]["export"]["formats"] == ["sheet"]
    assert replayed["fingerprint"] != read_manifest(out)["fingerprint"]


def test_the_same_settings_in_another_root_give_the_same_files_and_fingerprint(
    setup, capsys, tmp_path
):
    one = first_export(setup, capsys, tmp_path, "--formats", "atlases", name="one")
    two = first_export(setup, capsys, tmp_path, "--formats", "atlases", name="two")
    assert tree(one) == tree(two)
    assert str(one) not in (one / "manifest.json").read_text(encoding="utf-8")


def test_a_directory_manifest_reloads_as_a_directory_without_the_original_files(
    setup, capsys, tmp_path
):
    cfg = config(
        tmp_path,
        "export: {formats: [frames], frame_path: 'f/{clip}/{direction}-{frame}{map}.png'}\n"
        "direction_names: {0: front}\n"
        "clips:\n  walk: {output_name: stride}\n",
    )
    first = first_export(setup, capsys, tmp_path, "--config", str(cfg), name="a")
    assert (first / "f" / "stride" / "front-0.png").is_file()
    cfg.unlink()
    second = tmp_path / "b"
    status, _, err = run(
        capsys,
        to_dir(
            setup,
            second,
            *["--settings-from", str(first / "manifest.json"), "--no-user-config"],
        ),
    )
    assert status == 0, err
    assert tree(second) == tree(first)
