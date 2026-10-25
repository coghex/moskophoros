"""Frame counts in the command (settings design D-13, D-17, D-22, D-25, D-26,
D-31 to D-34 and D-38 to D-41), with a controlled fake Blender.

The model has `walk` (0 to 1 s, a loop), `attack` (0 to 0.5 s, a one-shot
under the setup's options) and `pose`, one keyframe at 0.25 s, so zero
duration. The setup's options run at 4 fps."""

import json
import os
from pathlib import Path

import pytest
from glb_writer import GlbWriter
from test_command import Setup, run
from test_materials_command import forbid_blender
from test_settings_command import project_file

from moskophoros import cli


@pytest.fixture
def setup(tmp_path):
    hero = Setup(tmp_path)
    hero.model.unlink()
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
    model.animation("pose", [(arm, "translation", [0.25], [(0.2, 0.5, 0)])])
    hero.model = model.write(hero.model.parent, "hero")
    return hero


def config(setup, text, name="frames.yaml"):
    path = setup.tmp_path / name
    path.write_text(text)
    return path


def user_file(text):
    path = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros", "config.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def sheet(setup):
    return json.loads(setup.json.read_text())


def counts(setup):
    """Each clip's resolved frame count and time scale, from the sheet."""
    return {
        clip["name"]: (clip["frame_count"], clip["time_scale"])
        for clip in sheet(setup)["clips"]
    }


def ok(capsys, argv):
    status, _, err = run(capsys, argv)
    assert status == 0, err
    return err


def own(name, loop, frames):
    """A selected clip as the manifest's settings record it: no export
    override of its own."""
    return {
        "name": name,
        "loop": loop,
        "frames": frames,
        "fps": None,
        "stored_directions": None,
        "mirrors": None,
        "output_name": None,
    }


def frame_warnings(err):
    return [
        line.removeprefix("moskophoros: warning: ")
        for line in err.splitlines()
        if line.startswith("moskophoros: warning: ") and "frame" in line
    ]


# The sheet record (D-24, D-31, D-40)


def test_counts_are_recorded_as_given_in_their_places(setup, capsys):
    path = config(setup, "clips:\n  attack: {frames: 2}\n  pose: {frames: auto}\n")
    ok(capsys, setup.argv("--frames", "3", "--config", str(path), "--no-preview"))
    document = sheet(setup)
    assert document["schema"] == "moskophoros.export/1"
    settings = document["settings"]
    keys = list(settings)
    assert keys[keys.index("fps") + 1] == "frames"
    assert settings["frames"] == 3
    assert settings["clips"] == [
        own("walk", True, None),
        own("attack", False, 2),
        own("pose", True, "auto"),
    ]
    clips = document["clips"]
    assert list(clips[0]) == [
        "name",
        "loop",
        "duration_s",
        "frame_count",
        "frame_duration_s",
        "time_scale",
        "output_name",
        "fps",
        "stored_directions",
        "mirrors",
    ]
    # walk: 3 frames of 1 s at 4 fps; attack: a one-shot of 2 over 0.5 s;
    # pose: zero duration, one frame.
    assert [
        (c["frame_count"], c["frame_duration_s"], c["time_scale"]) for c in clips
    ] == [
        (3, 0.25, 4 / 3),
        (2, 0.25, 2.0),
        (1, 0.25, 1.0),
    ]
    times = sorted({(f["clip"], f["index"], f["time_s"]) for f in document["frames"]})
    assert times == [
        ("attack", 0, 0.0),
        ("attack", 1, 0.5),
        ("pose", 0, 0.25),
        ("walk", 0, 0.0),
        ("walk", 1, 1 / 3),
        ("walk", 2, 2 / 3),
    ]


def test_without_a_count_the_sheet_records_auto_and_null(setup, capsys):
    ok(capsys, setup.argv("--no-preview"))
    document = sheet(setup)
    assert document["settings"]["frames"] == "auto"
    assert all(clip["frames"] is None for clip in document["settings"]["clips"])
    assert all(clip["time_scale"] == 1.0 for clip in document["clips"])


# Precedence (D-26, D-31, D-39)


@pytest.mark.parametrize("layer", ["option", "project", "config", "user"])
def test_a_clips_own_count_and_auto_beat_the_global_from_each_layer(
    setup, capsys, layer
):
    clips = "clips:\n  walk: {frames: 2}\n  attack: {frames: auto}\n"
    if layer == "option":
        user_file(clips)
        args = ["--frames", "5"]
    elif layer == "project":
        project_file("frames: 5\n" + clips)
        args = ["--project", "look"]
    elif layer == "config":
        args = ["--config", str(config(setup, "frames: 5\n" + clips))]
    else:
        user_file("frames: 5\n" + clips)
        args = []
    ok(capsys, setup.argv(*args, "--no-preview"))
    # attack, auto, samples by duration: a one-shot of 0.5 s at 4 fps.
    assert counts(setup) == {"walk": (2, 2.0), "attack": (3, 1.0), "pose": (1, 1.0)}


def test_null_takes_the_global_and_clears_a_lower_count(setup, capsys):
    user_file("clips:\n  walk: {frames: 2}\n")
    project_file("clips:\n  walk: {frames: null}\n")
    ok(capsys, setup.argv("--frames", "6", "--project", "look", "--no-preview"))
    assert counts(setup)["walk"] == (6, 4 / 6)


@pytest.mark.parametrize("global_", ["user", "config"])
def test_per_clip_entries_merge_by_name_across_layers(setup, capsys, global_):
    text = "clips:\n  walk: {frames: 2}\n  attack: {frames: 4}\n"
    args = []
    if global_ == "user":
        user_file(text)
    else:
        args = ["--config", str(config(setup, text))]
    project_file("clips:\n  attack: {frames: 3}\n")
    ok(capsys, setup.argv(*args, "--project", "look", "--no-preview"))
    assert counts(setup)["walk"][0] == 2
    assert counts(setup)["attack"][0] == 3


def test_frames_auto_returns_to_sampling_by_duration(setup, capsys):
    user_file("frames: 9\n")
    ok(capsys, setup.argv("--frames", "auto", "--no-preview"))
    assert counts(setup) == {"walk": (4, 1.0), "attack": (3, 1.0), "pose": (1, 1.0)}


def test_an_entry_for_a_clip_not_selected_or_missing_is_unused(setup, capsys):
    path = config(setup, "clips:\n  pose: {frames: 3}\n  leap: {frames: 9}\n")
    err = ok(
        capsys,
        setup.argv(
            "--clip", "walk", "--clip", "attack", "--config", str(path), "--no-preview"
        ),
    )
    assert frame_warnings(err) == []
    assert [c["name"] for c in sheet(setup)["settings"]["clips"]] == ["walk", "attack"]


# Warnings (D-25, D-26, D-41)


@pytest.mark.parametrize("how", ["option", "project"])
@pytest.mark.parametrize("global_", ["4", "auto"])
def test_an_explicit_global_names_the_clips_with_their_own(setup, capsys, how, global_):
    clips = (
        "clips:\n  walk: {frames: 4}\n  attack: {frames: auto}\n  pose: {frames: 1}\n"
    )
    if how == "option":
        args = ["--frames", global_, "--config", str(config(setup, clips))]
    else:
        project_file(f"frames: {global_}\n" + clips)
        args = ["--project", "look"]
    err = ok(capsys, setup.argv(*args, "--no-preview"))
    # Equal values still warn; the zero-duration pose is left out.
    assert frame_warnings(err) == [
        f"the global frame count {global_} does not reach the clips with their own: "
        '"walk" (4), "attack" (auto)'
    ]


@pytest.mark.parametrize("layer", ["defaults", "user", "config", "sheet"])
def test_a_global_from_the_defaults_the_global_file_or_a_sheet_warns_nothing(
    setup, capsys, layer
):
    clips = "clips:\n  walk: {frames: 4}\n"
    if layer == "user":
        user_file("frames: 3\n" + clips)
        err = ok(capsys, setup.argv("--no-preview"))
    elif layer == "config":
        path = config(setup, "frames: 3\n" + clips)
        err = ok(capsys, setup.argv("--config", str(path), "--no-preview"))
    elif layer == "defaults":
        user_file(clips)
        err = ok(capsys, setup.argv("--no-preview"))
    else:
        path = config(setup, "frames: 3\n" + clips)
        ok(capsys, setup.argv("--config", str(path), "--no-preview"))
        recorded = setup.tmp_path / "recorded.json"
        recorded.write_bytes(setup.json.read_bytes())
        err = ok(capsys, reload(setup, recorded))
    assert frame_warnings(err) == []


def test_a_zero_duration_clip_with_a_count_above_one_keeps_one_frame(setup, capsys):
    path = config(setup, "clips:\n  pose: {frames: 3}\n")
    err = ok(capsys, setup.argv("--config", str(path), "--no-preview"))
    assert frame_warnings(err) == [
        'clip "pose" has no duration and keeps one frame; its own frame count 3 '
        "does not apply"
    ]
    assert counts(setup)["pose"] == (1, 1.0)


def test_a_zero_duration_clip_with_a_count_of_one_warns_nothing(setup, capsys):
    path = config(setup, "clips:\n  pose: {frames: 1}\n")
    assert (
        frame_warnings(ok(capsys, setup.argv("--config", str(path), "--no-preview")))
        == []
    )


def test_the_output_does_not_change_with_the_warnings(setup, capsys):
    # The same counts, once with both warnings and once with neither: the
    # global from --frames against the user file, pose's 3 against 1.
    path = config(setup, "clips:\n  walk: {frames: 4}\n  pose: {frames: 3}\n")
    err = ok(capsys, setup.argv("--frames", "4", "--config", str(path), "--no-preview"))
    assert len(frame_warnings(err)) == 2
    warned = setup.png.read_bytes()
    user_file("frames: 4\nclips:\n  walk: {frames: 4}\n  pose: {frames: 1}\n")
    assert frame_warnings(ok(capsys, setup.argv("--no-preview"))) == []
    assert setup.png.read_bytes() == warned


# Refusals before Blender (D-34)


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ("frames: 0\n", "frames:"),
        ("frames: -2\n", "frames:"),
        ("frames: 8.0\n", "frames:"),
        ("frames: '8'\n", "frames:"),
        ("frames: true\n", "frames:"),
        ("clips:\n  walk: {frames: 0}\n", "clips.walk.frames:"),
        ("clips:\n  walk: {frames: 2.0}\n", "clips.walk.frames:"),
        ("clips:\n  walk: {frames: '2'}\n", "clips.walk.frames:"),
        ("clips:\n  walk: {frames: false}\n", "clips.walk.frames:"),
        ("clips:\n  walk: {frames: 2, speed: 1}\n", "clips.walk.speed: unknown key"),
        # Entries for clips not selected or missing are still checked.
        ("clips:\n  leap: {frames: 0}\n", "clips.leap.frames:"),
    ],
)
def test_a_bad_count_in_a_file_is_exit_2_before_blender(
    setup, capsys, monkeypatch, text, where
):
    path = config(setup, text)
    forbid_blender(monkeypatch)
    status, _, err = run(
        capsys,
        setup.argv("--clip", "walk", "--clip", "attack", "--config", str(path)),
    )
    assert status == 2
    assert f"--config {str(path)!r}: {where}" in err and " at line " in err
    assert setup.calls() == []


@pytest.mark.parametrize("value", ["0", "-1", "2.5", "8.0", "eight", "+3", "Auto"])
def test_a_bad_frames_option_is_exit_2_before_blender(
    setup, capsys, monkeypatch, value
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--frames", value))
    assert status == 2 and "argument --frames: " in err
    assert setup.calls() == []


# Reloading (D-16, D-24, D-39)


def reload(setup, recorded, *options):
    return [
        "--settings-from",
        str(recorded),
        "--no-user-config",
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(setup.png),
    ]


def recorded_sheet(setup, capsys):
    path = config(
        setup, "frames: 3\nclips:\n  walk: {frames: 2}\n  attack: {frames: auto}\n"
    )
    ok(capsys, setup.argv("--config", str(path), "--no-preview"))
    recorded = setup.tmp_path / "recorded.json"
    recorded.write_bytes(setup.json.read_bytes())
    return recorded


def test_reloading_restores_each_count_auto_and_null_exactly(setup, capsys):
    recorded = recorded_sheet(setup, capsys)
    before = json.loads(recorded.read_text())
    ok(capsys, reload(setup, recorded))
    after = sheet(setup)
    assert after["settings"] == before["settings"]
    assert after["clips"] == before["clips"]
    assert after["settings"]["clips"] == [
        own("walk", True, 2),
        own("attack", False, "auto"),
        own("pose", True, None),
    ]


def test_clip_over_a_loaded_sheet_keeps_a_reselected_clips_count(setup, capsys):
    recorded = recorded_sheet(setup, capsys)
    ok(capsys, reload(setup, recorded, "--clip", "walk", "--clip", "pose"))
    assert sheet(setup)["settings"]["clips"] == [
        own("walk", True, 2),
        own("pose", True, None),
    ]
    assert counts(setup)["walk"][0] == 2


def test_frames_over_a_loaded_sheet_reaches_only_the_null_clips(setup, capsys):
    recorded = recorded_sheet(setup, capsys)
    ok(
        capsys,
        reload(setup, recorded, "--clip", "walk", "--clip", "attack", "--frames", "5"),
    )
    # walk keeps 2 and attack its own auto; neither is null. --clip dropped
    # attack's one-shot mark, so it loops: 2 frames over 0.5 s at 4 fps.
    assert counts(setup) == {"walk": (2, 2.0), "attack": (2, 1.0)}
    project_file("clips:\n  walk: {frames: null}\n", "clear")
    ok(
        capsys,
        reload(
            setup, recorded, "--clip", "walk", "--project", "clear", "--frames", "5"
        ),
    )
    assert counts(setup) == {"walk": (5, 4 / 5)}


def test_per_clip_entries_merge_global_then_sheet_then_project(setup, capsys):
    recorded = recorded_sheet(setup, capsys)
    # The sheet records walk 2, attack auto and pose null. The global file's
    # walk and pose sit below it; the project's attack sits above it.
    user_file("clips:\n  walk: {frames: 9}\n  pose: {frames: 1}\n")
    project_file("clips:\n  attack: {frames: 1}\n")
    arguments = reload(setup, recorded, "--project", "look")
    arguments.remove("--no-user-config")
    ok(capsys, arguments)
    recorded_clips = sheet(setup)["settings"]["clips"]
    assert [clip["frames"] for clip in recorded_clips] == [2, 1, None]
    assert counts(setup)["walk"][0] == 2


# The capture job


def test_the_jobs_carry_the_counts_as_given(setup, capsys):
    work = setup.tmp_path / "work"
    path = config(setup, "clips:\n  attack: {frames: 2}\n")
    ok(
        capsys,
        setup.argv(
            "--frames",
            "3",
            "--config",
            str(path),
            "--no-preview",
            "--work-dir",
            str(work),
        ),
    )
    for mode in ("measure", "render"):
        job = json.loads((work / mode / "job.json").read_text())
        assert job["settings"]["frames"] == 3
        assert [clip["frames"] for clip in job["settings"]["clips"]] == [None, 2, None]
        assert "time_scale" not in json.dumps(job)
        times = sorted(
            frame["address"]["time_s"]
            for frame in job["frames"]
            if frame["address"]["clip"] == "walk" and frame["address"]["direction"] == 0
        )
        assert times == [0.0, 1 / 3, 2 / 3]


def test_a_changed_count_changes_the_job(setup, capsys):
    texts = []
    for frames in ("3", "4"):
        work = setup.tmp_path / f"work-{frames}"
        ok(
            capsys,
            setup.argv("--frames", frames, "--no-preview", "--work-dir", str(work)),
        )
        texts.append((work / "render" / "job.json").read_text().replace(str(work), "W"))
    assert texts[0] != texts[1]


def test_frames_need_a_whole_count_through_parse_args():
    options = cli.parse_args(["--frames", "8", "in.glb", "out.png"])
    assert (options.frames, "frames" in options.explicit) == (8, True)
