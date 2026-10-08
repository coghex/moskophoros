"""The whole `moskophoros` command, with a controlled fake Blender.

The fake answers `--version`, then for each capture phase reads its job and
writes a valid result, unless `config.json` beside it asks it to fail, wait,
change the source or write a bad result. It logs each phase it runs. Tests
coordinate with it through FIFOs, never by sleeping.
"""

import errno
import hashlib
import json
import os
import shutil
import signal
import sys
import textwrap
import threading
from dataclasses import replace
from importlib.metadata import entry_points
from pathlib import Path

import numpy as np
import pytest
from glb_writer import GlbWriter
from PIL import Image

from moskophoros import cli, export, gltf, imageops, sampling, stylize, views
from moskophoros.capture import backend, blender

FAKE = """\
#!{python}
import hashlib, json, os, pathlib, random, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("Blender 5.2.2 LTS")
    sys.exit(0)
here = pathlib.Path(__file__).parent
config = json.loads((here / "config.json").read_text())
job = json.loads(pathlib.Path(args[-1]).read_text())
mode = job["mode"]
with open(here / "calls.log", "a") as log:
    log.write(json.dumps({{"mode": mode, "cwd": os.getcwd()}}) + "\\n")
step = config.get(mode, {{}})
if "wait" in step:
    import signal
    with open(step["wait"], "w") as fifo:
        fifo.write(str(os.getpid()))
    signal.pause()
if "fail" in step:
    print("rendering, then", file=sys.stdout)
    print(step["fail"], file=sys.stderr)
    sys.exit(1)
if step.get("change_source"):
    with open(job["source"]["path"], "ab") as source:
        source.write(b" ")
canonical = json.dumps(
    job, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
).encode("ascii")
result = {{
    "schema": "moskophoros.capture-result/1",
    "mode": mode,
    "job_sha256": hashlib.sha256(canonical).hexdigest(),
    "source_sha256": job["source"]["sha256"],
}}
if mode == "measure":
    result["backend"] = {{"blender": "5.2.2"}}
    result["frames"] = [
        {{"address": f["address"], "bounds_m": config["bounds"],
          "height_m": config["height"]}}
        for f in job["frames"]
    ]
    result["roots"] = [
        {{"clip": c["name"], "node_index": r["node_index"],
          "node_name": r["node_name"],
          "travel_m": config["travel"].get(c["name"], 0.0)}}
        for c in job["clips"]
        for r in c["roots"]
    ]
else:
    from PIL import Image
    s = job["settings"]["supersample"]
    size = (job["settings"]["cell"]["width"] * s, job["settings"]["cell"]["height"] * s)
    os.mkdir("color")
    for i, f in enumerate(job["frames"]):
        if config["pixels"] == "noise":
            rng = random.Random(i)
            data = bytes(
                value
                for _ in range(size[0] * size[1])
                for value in (rng.randrange(256), rng.randrange(256),
                              rng.randrange(256), 255)
            )
            image = Image.frombytes("RGBA", size, data)
        elif config["pixels"] == "speckled":
            # Three of one colour and one of another in every 2x2 block.
            image = Image.new("RGBA", size, (200, 40, 10, 255))
            for y in range(0, size[1], 2):
                for x in range(0, size[0], 2):
                    image.putpixel((x, y), (10, 40, 200, 255))
        else:
            image = Image.new("RGBA", size, (37 * i % 256, 91 * i % 256, 128, 255))
            image.paste((0, 0, 0, 0), (0, 0, size[0] // 2, size[1] // 2))
        image.save(f"color/{{i:06d}}.png")
    buffers = [{{"color": f"color/{{i:06d}}.png"}} for i in range(len(job["frames"]))]
    if config.get("extra"):
        # A further named buffer, unlike the colour in every channel.
        os.mkdir("extra")
        for i, named in enumerate(buffers):
            rng = random.Random(1000 + i)
            data = bytes(rng.randrange(256) for _ in range(size[0] * size[1] * 4))
            Image.frombytes("RGBA", size, data).save(f"extra/{{i:06d}}.png")
            named["extra"] = f"extra/{{i:06d}}.png"
    result["backend"] = {{"blender": "5.2.2", "renderer": "workbench",
                          "studio_light": "Default"}}
    result["frames"] = [
        {{"address": f["address"], "buffers": named}}
        for f, named in zip(job["frames"], buffers)
    ]
if step.get("bad_result"):
    result["job_sha256"] = "0" * 64
pathlib.Path("result.json").write_text(json.dumps(result))
"""

DEFAULT_CONFIG = {
    "bounds": {"L": 0.25, "R": 0.25, "U": 0.75, "D": 0.0},
    "height": 1.0,
    "travel": {},
    "pixels": "solid",
}
OPTIONS = ["--once", "attack", "--supersample", "1", "--cell", "16x16", "--fps", "4"]
BACKEND = {"blender": "5.2.2", "renderer": "workbench", "studio_light": "Default"}
MODES = ("measure", "render")


class Setup:
    """A model, a fake Blender and an output directory under `tmp_path`."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        (tmp_path / "model").mkdir()
        self.model = _model(tmp_path / "model")
        self.fake = tmp_path / "bin" / "blender"
        self.fake.parent.mkdir()
        self.fake.write_text(FAKE.format(python=sys.executable))
        self.fake.chmod(0o755)
        self.out = tmp_path / "out"
        self.out.mkdir()
        self.png = self.out / "hero.png"
        self.json = self.out / "hero.json"
        self.walk_gif = self.out / "hero.walk.gif"
        self.attack_gif = self.out / "hero.attack.gif"
        self.configure()

    def configure(self, **changes):
        config = DEFAULT_CONFIG | changes
        (self.fake.parent / "config.json").write_text(json.dumps(config))

    def argv(self, *options, outfile=None):
        return [
            *OPTIONS,
            *options,
            "--blender",
            str(self.fake),
            str(self.model),
            str(self.png if outfile is None else outfile),
        ]

    def calls(self):
        log = self.fake.parent / "calls.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def listing(self):
        """Every file in the output directory, with its bytes."""
        return {path.name: path.read_bytes() for path in sorted(self.out.iterdir())}


def _model(directory):
    """`hero.glb`: `walk` moves the named root `hips`; `attack` moves an
    unnamed root."""
    model = GlbWriter()
    hips = model.node("hips", mesh=True)
    arm = model.node(None, mesh=True, translation=(0.2, 0.5, 0.0))
    model.scene([hips, arm], default=True)
    model.animation(
        "walk", [(hips, "translation", [0.0, 1.0], [(0, 0, 0), (0, 0.1, 0)])]
    )
    model.animation(
        "attack",
        [(arm, "translation", [0.0, 0.5], [(0.2, 0.5, 0), (0.2, 0.9, 0)])],
    )
    return model.write(directory, "hero")


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def run(capsys, argv):
    status = cli.run(argv)
    out, err = capsys.readouterr()
    return status, out, err


def earlier_outputs(setup, *names):
    """Write recognizable earlier outputs; return the directory listing."""
    for name in names:
        (setup.out / name).write_bytes(f"earlier {name}".encode())
    (setup.out / "notes.txt").write_text("not an output")
    return setup.listing()


# A successful run


def test_a_run_writes_the_sheet_its_json_and_a_preview_per_clip(setup, capsys):
    status, out, err = run(capsys, setup.argv())
    assert (status, out, err) == (0, "", "")
    assert sorted(setup.listing()) == [
        "hero.attack.gif",
        "hero.json",
        "hero.png",
        "hero.walk.gif",
    ]
    description = json.loads(setup.json.read_text())
    assert description["schema"] == "moskophoros.sheet/2"
    assert description["settings"]["style"] == {"reduce": "plain", "palette": None}
    assert description["image"]["file"] == "hero.png"
    assert [(c["name"], c["loop"]) for c in description["clips"]] == [
        ("walk", True),
        ("attack", False),
    ]
    with Image.open(setup.png) as image:
        assert image.mode == "RGBA"
        assert image.size == (
            description["image"]["width"],
            description["image"]["height"],
        )
    for gif in (setup.walk_gif, setup.attack_gif):
        with Image.open(gif) as image:
            assert image.format == "GIF"
    assert [call["mode"] for call in setup.calls()] == ["measure", "render"]


def test_no_preview_writes_only_the_sheet_and_its_json(setup, capsys):
    assert run(capsys, setup.argv("--no-preview"))[0] == 0
    assert sorted(setup.listing()) == ["hero.json", "hero.png"]


def test_the_main_entry_point_exits_with_the_status(setup, capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(setup.argv())
    assert raised.value.code == 0


def test_the_console_script_is_declared():
    (script,) = entry_points(group="console_scripts", name="moskophoros")
    assert script.value == "moskophoros.cli:main"


def test_help_exits_0(capsys):
    status, out, err = run(capsys, ["--help"])
    assert (status, err) == (0, "")
    assert out.startswith("usage: moskophoros [options] <infile.glb> <outfile.png>")


def test_the_fingerprint_reaches_the_frames_before_stylize(setup, capsys, monkeypatch):
    seen = []
    real_plain = stylize.plain

    def recording_plain(frames, factor):
        frames = tuple(frames)
        seen.extend(frames)
        return real_plain(frames, factor)

    monkeypatch.setattr(stylize, "plain", recording_plain)
    argv = setup.argv("--ppm", "10", "--ground-px", "8,15")
    assert run(capsys, argv)[0] == 0

    # Worked out from the options: the iso view, 4 fps, 16x16 cell, 10 ppm.
    settings = {
        "view": {
            "preset": "iso",
            "projection": "orthographic",
            "pitch_deg": 30.0,
            "directions": 8,
            "start_angle_deg": 0.0,
        },
        "model_yaw_deg": 0.0,
        "fps": 4.0,
        "supersample": 1,
        "pixels_per_meter": 10.0,
        "cell": {"width": 16, "height": 16},
        "ground_m": {"x": 0.0, "y": 0.0, "z": 0.0},
        "ground_px": {"x": 8, "y": 15},
        "root_motion": "error",
        "style": {"reduce": "plain", "palette": None},
        "clips": [{"name": "walk", "loop": True}, {"name": "attack", "loop": False}],
    }
    expected = export.fingerprint(
        export.generator(BACKEND),
        settings,
        hashlib.sha256(setup.model.read_bytes()).hexdigest(),
    )
    # walk: 4 samples, attack: 2 + 1, each in 8 directions.
    assert len(seen) == (4 + 3) * 8
    assert all(frame.metadata == {"fingerprint": expected} for frame in seen)
    description = json.loads(setup.json.read_text())
    assert description["settings"] == settings
    assert description["fingerprint"] == expected


def test_each_captured_frame_is_reduced_before_the_next_is_loaded(
    setup, capsys, monkeypatch
):
    events = []
    real_load, real_reduce = imageops.load_png, imageops.reduce_blocks

    def load(path):
        events.append("load")
        return real_load(path)

    def reduce(pixels, factor):
        events.append("reduce")
        return real_reduce(pixels, factor)

    monkeypatch.setattr(imageops, "load_png", load)
    monkeypatch.setattr(imageops, "reduce_blocks", reduce)
    assert run(capsys, setup.argv())[0] == 0
    assert events == ["load", "reduce"] * ((4 + 3) * 8)


def test_two_runs_give_identical_outputs(setup, capsys, tmp_path):
    assert run(capsys, setup.argv())[0] == 0
    first = setup.listing()
    assert run(capsys, setup.argv())[0] == 0
    assert setup.listing() == first


def test_an_explicit_plain_reduction_changes_no_output(setup, capsys):
    assert run(capsys, setup.argv())[0] == 0
    default = setup.listing()
    assert run(capsys, setup.argv("--reduce", "plain"))[0] == 0
    assert setup.listing() == default


def test_the_style_never_reaches_the_capture_jobs(setup, capsys):
    work = setup.tmp_path / "work"
    jobs = []
    for options in [(), ("--reduce", "plain")]:
        assert run(capsys, setup.argv("--work-dir", str(work), *options))[0] == 0
        jobs.append({mode: (work / mode / "job.json").read_bytes() for mode in MODES})
        shutil.rmtree(work)
    assert jobs[0] == jobs[1]
    for mode in MODES:
        job = json.loads(jobs[0][mode])
        assert "style" not in job["settings"]
        assert job["schema"] == "moskophoros.capture-job/1"


# Measure and render jobs as master built them before the style was recorded,
# for fixed source and output paths: SHA-256 of the job file's text.
JOB_BASELINES = {
    "measure": "ff7fc011058a0270b604a93cb7fcccaa930addf47248857ed31a0d0b88b8348d",
    "render": "445b27ea3c882aabdb2bf0a1fe366462a0029a6ab3ae7ac99ba37436b0ce7017",
}


@pytest.mark.parametrize("options", [(), ("--reduce", "plain")])
def test_the_capture_jobs_are_byte_identical_to_the_baseline(options):
    subject = gltf.Subject(
        Path("/models/hero.glb"),
        "hero",
        0,
        (
            gltf.Clip(0, "walk", 0.0, 0.5, (gltf.Root(0, "hips"),)),
            gltf.Clip(1, "attack", 0.25, 0.5, ()),
        ),
    )
    source = backend.Source(Path("/models/hero.glb"), "cd" * 32, 0)
    parsed = cli.parse_args(
        ["--once", "attack", "--fps", "4", *options, "hero.glb", "hero.png"]
    )
    settings = cli.capture_settings(cli.resolve_settings(parsed))
    selected = gltf.select_clips(subject, parsed.clip or (), parsed.once)
    view = views.View(
        settings.pitch, settings.directions, settings.start_angle, settings.model_yaw
    )
    requested = sampling.frames("hero", selected, view, settings.fps)
    fitted = replace(settings, ppm=24.5, cell=(48, 40), ground_px=(24, 37))
    for mode, resolved in (("measure", settings), ("render", fitted)):
        job = backend.build_job(
            mode, source, "hero", resolved, selected, requested, f"/work/{mode}"
        )
        text = blender._job_text(job)
        assert hashlib.sha256(text.encode()).hexdigest() == JOB_BASELINES[mode]


# The most-common-colour reduction: each 2x2 block of the speckled capture
# holds three of SPECKLE_MOST and one other, which plain blends.
SPECKLED = ["--once", "attack", "--cell", "16x16", "--fps", "4", "--supersample", "2"]
SPECKLE_MOST = (200, 40, 10, 255)
# ((3 · 200 + 10) / 4, 40, (3 · 10 + 200) / 4), rounded half up.
SPECKLE_MEAN = (153, 40, 58, 255)
UNUSED = (0, 0, 0, 0)


def speckled_argv(setup, *options, outfile=None):
    return [
        *SPECKLED,
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(setup.png if outfile is None else outfile),
    ]


def sheet_colours(path):
    with Image.open(path) as image:
        pixels = np.array(image)
    return {tuple(int(v) for v in pixel) for pixel in pixels.reshape(-1, 4)}


def test_reduce_mode_keeps_each_block_s_most_common_colour(setup, capsys):
    setup.configure(pixels="speckled")
    assert run(capsys, speckled_argv(setup, "--reduce", "mode"))[0] == 0
    assert sheet_colours(setup.png) == {SPECKLE_MOST, UNUSED}
    mode = json.loads(setup.json.read_text())
    assert mode["settings"]["style"] == {"reduce": "mode", "palette": None}

    assert run(capsys, speckled_argv(setup))[0] == 0
    assert sheet_colours(setup.png) == {SPECKLE_MEAN, UNUSED}
    plain = json.loads(setup.json.read_text())
    assert plain["settings"]["style"] == {"reduce": "plain", "palette": None}
    assert mode["fingerprint"] != plain["fingerprint"]
    assert {k: v for k, v in mode["settings"].items() if k != "style"} == {
        k: v for k, v in plain["settings"].items() if k != "style"
    }


def test_a_reused_mode_sheet_selects_mode_unless_overridden(setup, capsys):
    setup.configure(pixels="speckled")
    assert run(capsys, speckled_argv(setup, "--reduce", "mode"))[0] == 0
    reused = setup.out / "reused.png"
    argv = [
        "--settings-from",
        str(setup.json),
        "--once",
        "attack",
        "--blender",
        str(setup.fake),
        str(setup.model),
    ]
    assert run(capsys, [*argv, str(reused)])[0] == 0
    assert sheet_colours(reused) == {SPECKLE_MOST, UNUSED}
    assert reused.read_bytes() == setup.png.read_bytes()
    assert (setup.out / "reused.json").read_text().replace(
        "reused.png", "hero.png"
    ) == setup.json.read_text()

    assert run(capsys, ["--reduce", "plain", *argv, str(reused)])[0] == 0
    assert sheet_colours(reused) == {SPECKLE_MEAN, UNUSED}
    style = json.loads((setup.out / "reused.json").read_text())["settings"]["style"]
    assert style == {"reduce": "plain", "palette": None}


def test_mode_reduces_each_captured_frame_before_the_next_is_loaded(
    setup, capsys, monkeypatch
):
    events = []
    real_load, real_reduce = imageops.load_png, imageops.reduce_blocks_mode

    def load(path):
        events.append("load")
        return real_load(path)

    def reduce(pixels, factor):
        events.append("reduce")
        return real_reduce(pixels, factor)

    def plain(pixels, factor):
        raise AssertionError("plain ran under --reduce mode")

    monkeypatch.setattr(imageops, "load_png", load)
    monkeypatch.setattr(imageops, "reduce_blocks_mode", reduce)
    monkeypatch.setattr(imageops, "reduce_blocks", plain)
    setup.configure(pixels="speckled")
    assert run(capsys, speckled_argv(setup, "--reduce", "mode"))[0] == 0
    assert events == ["load", "reduce"] * ((4 + 3) * 8)


def test_settings_reuse_with_an_explicit_override(setup, capsys):
    assert run(capsys, setup.argv("--ppm", "10", "--ground-px", "8,15"))[0] == 0
    earlier = json.loads(setup.json.read_text())["settings"]
    reused = setup.out / "reused.png"
    argv = [
        "--settings-from",
        str(setup.json),
        "--fps",
        "2",
        "--once",
        "attack",
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(reused),
    ]
    assert run(capsys, argv)[0] == 0
    settings = json.loads(reused.with_suffix(".json").read_text())["settings"]
    assert settings == earlier | {"fps": 2.0}


# Root motion


@pytest.mark.parametrize("travel", [0.0199, 0.02, 0.0201])
@pytest.mark.parametrize("mode", ["error", "keep"])
def test_the_root_motion_limit(setup, capsys, travel, mode):
    setup.configure(travel={"walk": travel})
    status, _, err = run(capsys, setup.argv("--root-motion", mode))
    if mode == "keep" or travel <= 0.02:
        assert (status, err) == (0, "")
        return
    assert status == 3
    assert err == (
        f"moskophoros: error: {setup.model}: clip 'walk' moves its root node 0 "
        "('hips') 0.0201 m across the ground, more than 0.02 m; export the clip "
        "in place, or give --root-motion keep\n"
    )
    assert setup.listing() == {}
    assert [call["mode"] for call in setup.calls()] == ["measure"]


def test_every_travelling_root_is_named(setup, capsys):
    setup.configure(travel={"walk": 1.5, "attack": 0.25})
    status, _, err = run(capsys, setup.argv())
    assert status == 3
    assert "clip 'walk' moves its root node 0 ('hips') 1.5 m" in err
    assert "clip 'attack' moves its root node 1 0.25 m" in err


# Workspaces


def test_a_missing_work_dir_is_created_and_kept(setup, capsys):
    work = setup.tmp_path / "new" / "work"
    assert run(capsys, setup.argv("--work-dir", str(work)))[0] == 0
    assert sorted(path.name for path in work.iterdir()) == ["measure", "render"]
    for phase in ("measure", "render"):
        assert (work / phase / "job.json").is_file()
        assert (work / phase / "result.json").is_file()
    assert (work / "render" / "color" / "000000.png").is_file()


def test_an_empty_work_dir_is_used(setup, capsys):
    work = setup.tmp_path / "work"
    work.mkdir()
    assert run(capsys, setup.argv("--work-dir", str(work)))[0] == 0
    assert sorted(path.name for path in work.iterdir()) == ["measure", "render"]


def test_a_nonempty_work_dir_is_a_usage_error(setup, capsys):
    work = setup.tmp_path / "work"
    work.mkdir()
    (work / "kept.txt").write_text("kept")
    earlier = earlier_outputs(setup, "hero.png")
    status, _, err = run(capsys, setup.argv("--work-dir", str(work)))
    assert status == 2
    assert err.splitlines() == [
        "usage: moskophoros [options] <infile.glb> <outfile.png>",
        f"moskophoros: error: --work-dir {str(work)!r} is not empty; give a new "
        "or empty directory",
    ]
    assert [path.name for path in work.iterdir()] == ["kept.txt"]
    assert (work / "kept.txt").read_text() == "kept"
    assert setup.calls() == []
    assert setup.listing() == earlier


def test_a_work_dir_that_is_a_file_is_a_usage_error(setup, capsys):
    work = setup.tmp_path / "work"
    work.write_text("a file")
    status, _, err = run(capsys, setup.argv("--work-dir", str(work)))
    assert status == 2
    assert f"--work-dir {str(work)!r} is not a directory" in err
    assert work.read_text() == "a file"


def test_a_work_dir_keeps_what_capture_left_after_a_failure(setup, capsys):
    setup.configure(render={"fail": "out of memory"})
    work = setup.tmp_path / "work"
    status, _, _ = run(capsys, setup.argv("--work-dir", str(work)))
    assert status == 5
    assert (work / "measure" / "result.json").is_file()
    assert (work / "render" / "job.json").is_file()
    assert not (work / "render" / "result.json").exists()


@pytest.mark.parametrize("fail", [None, "render"])
def test_the_temporary_workspace_is_deleted(setup, capsys, fail):
    if fail:
        setup.configure(render={"fail": "out of memory"})
    status, _, _ = run(capsys, setup.argv())
    assert status == (5 if fail else 0)
    calls = setup.calls()
    assert [call["mode"] for call in calls] == ["measure", "render"]
    workspace = Path(calls[0]["cwd"]).parent
    assert Path(calls[1]["cwd"]).parent == workspace
    assert not workspace.exists()


# Publication


def _failing_replace(monkeypatch, out, fail_at, error):
    """Make the `fail_at`-th rename into or out of `out` raise `error`."""
    real_replace = os.replace
    calls = []

    def replace(source, target):
        if out in (Path(source).parent, Path(target).parent):
            calls.append((source, target))
            if len(calls) - 1 == fail_at:
                raise error
        return real_replace(source, target)

    monkeypatch.setattr(os, "replace", replace)
    return calls


# The earlier PNG, JSON and attack preview exist; the walk preview is new.
# Each existing target takes two renames (aside, then into place), a new one
# one: 2 + 2 + 1 + 2.
RENAMES = 7


# The output each rename moves: aside then into place for an existing
# target, only into place for a new one.
RENAMED = [
    "hero.png",
    "hero.png",
    "hero.json",
    "hero.json",
    "hero.walk.gif",
    "hero.attack.gif",
    "hero.attack.gif",
]


def assert_output_error(setup, status, err, name, reason):
    """Exit 6 with one error line naming the output, and no usage synopsis
    or traceback."""
    assert status == 6
    assert err == (
        f"moskophoros: error: cannot write {str(setup.out / name)!r}: {reason}; "
        "earlier outputs are kept\n"
    )


@pytest.mark.parametrize("fail_at", range(RENAMES))
def test_a_rename_failure_restores_every_earlier_output(
    setup, capsys, monkeypatch, fail_at
):
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    calls = _failing_replace(
        monkeypatch,
        setup.out,
        fail_at,
        OSError(errno.EBUSY, "Device or resource busy"),
    )
    status, _, err = run(capsys, setup.argv())
    assert_output_error(setup, status, err, RENAMED[fail_at], "Device or resource busy")
    assert len(calls) > fail_at
    assert setup.listing() == earlier


class _FullDisk:
    """A file handle whose write stops halfway with ENOSPC."""

    def __init__(self, handle):
        self.handle = handle

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.handle.close()

    def write(self, data):
        self.handle.write(data[: len(data) // 2])
        raise OSError(errno.ENOSPC, "No space left on device", self.handle.name)


def _failing_stage(monkeypatch, name, failure):
    """Make staging the output `name` fail: `full` creates the staged file,
    then its write fails with ENOSPC; `denied` cannot create it."""
    real_open = open

    def staged_open(path, mode="r", *args, **kwargs):
        if "x" in mode and Path(path).name.startswith(f".{name}.moskophoros-new-"):
            if failure == "denied":
                raise PermissionError(errno.EACCES, "Permission denied", str(path))
            return _FullDisk(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(cli, "open", staged_open, raising=False)


@pytest.mark.parametrize("name", ["hero.png", "hero.walk.gif", "hero.attack.gif"])
@pytest.mark.parametrize(
    ("failure", "reason"),
    [("full", "No space left on device"), ("denied", "Permission denied")],
)
def test_a_staging_failure_keeps_every_earlier_output(
    setup, capsys, monkeypatch, name, failure, reason
):
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    _failing_stage(monkeypatch, name, failure)
    status, _, err = run(capsys, setup.argv())
    assert_output_error(setup, status, err, name, reason)
    # Byte for byte, with no staged file left behind.
    assert setup.listing() == earlier


def test_a_clean_publication_takes_the_counted_renames(setup, capsys, monkeypatch):
    earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    calls = _failing_replace(monkeypatch, setup.out, None, None)
    assert run(capsys, setup.argv())[0] == 0
    assert len(calls) == RENAMES


def test_an_interruption_during_publication_restores_every_earlier_output(
    setup, capsys, monkeypatch
):
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    # After the PNG has been replaced and the JSON moved aside.
    _failing_replace(monkeypatch, setup.out, 3, KeyboardInterrupt())
    status, out, err = run(capsys, setup.argv())
    assert (status, out, err) == (130, "", "moskophoros: error: interrupted\n")
    assert setup.listing() == earlier


def _interrupt_after(monkeypatch, module, name, out, after):
    """Deliver a real Ctrl-C right after the `after`-th call of
    `module.name` touching `out` completes, as if it arrived between that
    filesystem change and whatever follows."""
    real = getattr(module, name)
    calls = []

    def wrapper(*args, **kwargs):
        result = real(*args, **kwargs)
        if any(Path(arg).parent == out for arg in args if isinstance(arg, str | Path)):
            calls.append(args)
            if len(calls) - 1 == after:
                signal.raise_signal(signal.SIGINT)
        return result

    monkeypatch.setattr(module, name, wrapper)
    return calls


@pytest.mark.parametrize("after", range(RENAMES))
def test_ctrl_c_right_after_any_rename_restores_every_earlier_output(
    setup, capsys, monkeypatch, after
):
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    calls = _interrupt_after(monkeypatch, os, "replace", setup.out, after)
    status, out, err = run(capsys, setup.argv())
    assert (status, out, err) == (130, "", "moskophoros: error: interrupted\n")
    assert len(calls) > after
    # Byte for byte, with no staged or moved-aside file left behind.
    assert setup.listing() == earlier


def test_ctrl_c_while_staging_restores_every_earlier_output(setup, capsys, monkeypatch):
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    real_open = open

    def staging_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if "x" in mode and Path(path).name.startswith(".hero.json."):
            signal.raise_signal(signal.SIGINT)
        return handle

    monkeypatch.setattr(cli, "open", staging_open, raising=False)
    status, out, err = run(capsys, setup.argv())
    assert (status, out, err) == (130, "", "moskophoros: error: interrupted\n")
    assert setup.listing() == earlier


def test_ctrl_c_after_every_output_is_in_place_lets_the_run_finish(
    setup, capsys, monkeypatch
):
    # Deleting the earlier files is cleanup after the publication is
    # complete: an interruption there neither stops it nor loses a file.
    earlier = earlier_outputs(setup, "hero.png", "hero.json", "hero.attack.gif")
    _interrupt_after(monkeypatch, os, "remove", setup.out, 0)
    status, out, err = run(capsys, setup.argv())
    assert (status, out, err) == (0, "", "")
    after = setup.listing()
    assert sorted(after) == [
        "hero.attack.gif",
        "hero.json",
        "hero.png",
        "hero.walk.gif",
        "notes.txt",
    ]
    for name in ("hero.png", "hero.json", "hero.attack.gif"):
        assert after[name] != earlier[name]
    assert after["notes.txt"] == earlier["notes.txt"]


def test_ctrl_c_outside_publication_still_interrupts(setup, capsys):
    # The deferral is only for publication: the handler is restored after.
    assert run(capsys, setup.argv())[0] == 0
    with pytest.raises(KeyboardInterrupt):
        signal.raise_signal(signal.SIGINT)


def test_earlier_previews_stay_under_no_preview(setup, capsys):
    earlier = earlier_outputs(setup, "hero.walk.gif", "hero.attack.gif")
    assert run(capsys, setup.argv("--no-preview"))[0] == 0
    after = setup.listing()
    for name in ("hero.walk.gif", "hero.attack.gif", "notes.txt"):
        assert after[name] == earlier[name]
    assert sorted(after) == sorted([*earlier, "hero.png", "hero.json"])


def test_a_dropped_clip_keeps_its_earlier_preview(setup, capsys):
    earlier = earlier_outputs(setup, "hero.walk.gif", "hero.attack.gif")
    argv = setup.argv("--clip", "walk")
    argv.remove("--once")
    argv.remove("attack")
    assert run(capsys, argv)[0] == 0
    after = setup.listing()
    assert after["hero.attack.gif"] == earlier["hero.attack.gif"]
    assert after["hero.walk.gif"] != earlier["hero.walk.gif"]


def test_a_missing_output_directory_is_a_usage_error_before_capture(setup, capsys):
    outfile = setup.tmp_path / "missing" / "hero.png"
    status, _, err = run(capsys, setup.argv(outfile=outfile))
    assert status == 2
    assert f"the output directory {str(outfile.parent)!r} does not exist" in err
    assert setup.calls() == []


def test_an_output_that_is_a_directory_is_a_usage_error_before_capture(setup, capsys):
    setup.walk_gif.mkdir()
    status, _, err = run(capsys, setup.argv())
    assert status == 2
    assert f"the output {str(setup.walk_gif)!r} is a directory" in err
    assert setup.calls() == []


# Interruption, errors and warnings


def test_an_interruption_during_capture_publishes_nothing(setup, capsys):
    earlier = earlier_outputs(setup, "hero.png", "hero.json")
    ready = setup.tmp_path / "ready"
    os.mkfifo(ready)
    setup.configure(measure={"wait": str(ready)})
    main = threading.main_thread().ident
    launched = []

    def interrupt_when_ready():
        with open(ready) as fifo:
            launched.append(int(fifo.read()))
        signal.pthread_kill(main, signal.SIGINT)

    helper = threading.Thread(target=interrupt_when_ready)
    helper.start()
    status, out, err = run(capsys, setup.argv())
    helper.join()
    assert (status, out, err) == (130, "", "moskophoros: error: interrupted\n")
    (pid,) = launched
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # stopped and reaped
    assert setup.listing() == earlier
    workspace = Path(setup.calls()[0]["cwd"]).parent
    assert not workspace.exists()


def test_an_internal_error_prints_a_traceback_and_exits_1(setup, capsys, monkeypatch):
    earlier = earlier_outputs(setup, "hero.png")

    def broken(*args, **kwargs):
        raise RuntimeError("a bug in export")

    monkeypatch.setattr(export, "encode", broken)
    status, _, err = run(capsys, setup.argv())
    assert status == 1
    assert err.startswith("Traceback (most recent call last):\n")
    assert "RuntimeError: a bug in export\n" in err
    assert err.endswith("moskophoros: error: internal error; this is a bug\n")
    assert setup.listing() == earlier


def test_the_unit_warning_is_printed_and_the_run_continues(setup, capsys):
    setup.configure(height=500.0)
    status, _, err = run(capsys, setup.argv())
    assert status == 0
    assert err == (
        "moskophoros: warning: the subject is 500.0 m tall, outside 0.01 m to "
        "100 m; check that the model is in meters\n"
    )
    assert setup.png.exists()


def test_the_preview_color_warning_is_printed_and_the_run_continues(setup, capsys):
    setup.configure(pixels="noise")
    status, _, err = run(capsys, setup.argv())
    assert status == 0
    assert err.splitlines() == [
        f"moskophoros: warning: clip {name!r}'s preview has frames with more than "
        "256 colors, reduced to 256 without dithering"
        for name in ("walk", "attack")
    ]
    assert setup.walk_gif.exists()


# Failures by exit code, each leaving earlier outputs as they were

EARLIER = ("hero.png", "hero.json", "hero.walk.gif", "hero.attack.gif")


def test_a_bad_settings_file_is_a_usage_error(setup, capsys):
    earlier = earlier_outputs(setup, *EARLIER)
    bad = setup.tmp_path / "bad.json"
    bad.write_text("{}")
    status, _, err = run(capsys, setup.argv("--settings-from", str(bad)))
    assert status == 2
    assert "is not a moskophoros.sheet/2 or moskophoros.sheet/1 document" in err
    assert setup.listing() == earlier


def test_a_source_changed_during_capture_is_an_input_error(setup, capsys):
    earlier = earlier_outputs(setup, *EARLIER)
    setup.configure(measure={"change_source": True})
    status, _, err = run(capsys, setup.argv())
    assert status == 3
    assert err == (
        f"moskophoros: error: {setup.model}: changed during capture; run again on "
        "the final file\n"
    )
    assert setup.listing() == earlier


def test_a_bad_model_is_an_input_error(setup, capsys):
    earlier = earlier_outputs(setup, *EARLIER)
    setup.model.write_bytes(b"not a model")
    status, _, err = run(capsys, setup.argv())
    assert status == 3
    assert err.startswith(f"moskophoros: error: {setup.model}: ")
    assert setup.listing() == earlier
    assert setup.calls() == []


@pytest.mark.parametrize(
    ("edit", "problem"),
    [
        ("name", "material 0's name is not a string"),
        ("material", "mesh 0's primitive 0's material names no material"),
        ("mesh", "node 0's mesh names mesh True, which does not exist"),
    ],
)
def test_bad_material_input_fails_before_blender_without_a_library(
    setup, capsys, monkeypatch, edit, problem
):
    earlier = earlier_outputs(setup, *EARLIER)
    model = GlbWriter()
    model.scene([model.node(mesh=True)])
    model.document["materials"] = [{"name": "steel"}]
    primitive = model.document["meshes"][0]["primitives"][0]
    primitive["material"] = 0
    if edit == "name":
        model.document["materials"][0]["name"] = None
    elif edit == "material":
        primitive["material"] = None
    else:
        model.document["nodes"][0]["mesh"] = True
    setup.model.write_bytes(model.to_bytes())

    def unexpected_blender(*args, **kwargs):
        pytest.fail("invalid material input reached Blender discovery or capture")

    monkeypatch.setattr(blender, "locate", unexpected_blender)
    monkeypatch.setattr(blender, "run_phase", unexpected_blender)
    status, out, err = run(capsys, setup.argv())
    assert status == 3
    assert out == ""
    assert err == f"moskophoros: error: {setup.model}: {problem}\n"
    assert setup.listing() == earlier
    assert setup.calls() == []


def test_an_overflowing_fixed_configuration_is_exit_4(setup, capsys):
    earlier = earlier_outputs(setup, *EARLIER)
    status, _, err = run(capsys, setup.argv("--ppm", "100"))
    assert status == 4
    assert err.startswith("moskophoros: error: the subject overflows the 16x16 cell")
    assert setup.listing() == earlier
    assert [call["mode"] for call in setup.calls()] == ["measure"]


def test_a_failed_capture_phase_is_a_backend_error_with_its_output(setup, capsys):
    earlier = earlier_outputs(setup, *EARLIER)
    setup.configure(render={"fail": "GPU lost"})
    status, _, err = run(capsys, setup.argv())
    assert status == 5
    assert err == textwrap.dedent(
        """\
        moskophoros: error: Blender's render phase exited with status 1
        Blender stdout:
        rendering, then
        Blender stderr:
        GPU lost
        """
    )
    assert setup.listing() == earlier


@pytest.mark.parametrize("mode", ["measure", "render"])
def test_an_invalid_capture_result_is_a_backend_error(setup, capsys, mode):
    earlier = earlier_outputs(setup, *EARLIER)
    setup.configure(**{mode: {"bad_result": True}})
    status, _, err = run(capsys, setup.argv())
    assert status == 5
    assert err.startswith("moskophoros: error: ")
    assert "job_sha256" in err
    assert setup.listing() == earlier


def test_an_unusable_blender_is_a_backend_error(setup, capsys):
    earlier = earlier_outputs(setup, *EARLIER)
    argv = setup.argv()
    argv[argv.index("--blender") + 1] = str(setup.tmp_path / "no-blender")
    status, _, err = run(capsys, argv)
    assert status == 5
    assert "is not an executable file" in err
    assert setup.listing() == earlier
