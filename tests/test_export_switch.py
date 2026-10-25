"""The positional command writes and reloads the complete `moskophoros.export/1`
manifest (export design P-8, P-8a, P-13; EXP-6a): all of its members, with the
new settings at their inactive defaults; reload of its own output byte for
byte; and a loaded manifest that records any other value of an export setting
refused, before Blender, since the command could not honor it yet."""

import json
import shutil

import pytest
from manifest_fixture import clip as fixture_clip
from manifest_fixture import export_for
from test_command import Setup, run
from test_materials_command import forbid_blender
from test_settings_command import own

from moskophoros import cli, exportsettings
from moskophoros import settings as layered

CLIPS = ("--clip", "walk", "--clip", "attack")
WALK = fixture_clip(0, "walk")
DEFAULT_EXPORT = {
    "stored_directions": "all",
    "direction_names": [],
    "mirrors": [],
    "export": {
        "formats": ["sheet"],
        "frame_path": "frames/{clip}/{direction}/frame_{frame:03}{map}.png",
        "atlas_path": "atlases/{clip}{map}.png",
        "sheet_path": "sheet{map}.png",
        "atlas_padding": 0,
    },
}
LEGACY_KEYS = {
    "view",
    "camera",
    "model_yaw_deg",
    "fps",
    "frames",
    "supersample",
    "pixels_per_meter",
    "cell",
    "ground_m",
    "ground_px",
    "root_motion",
    "shade",
    "clips",
}


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def written(setup, capsys, *options):
    status, _, err = run(capsys, setup.argv(*CLIPS, *options))
    assert status == 0, err
    return json.loads(setup.json.read_text())


# What a run writes


def test_a_run_records_every_inactive_default(setup, capsys):
    settings = written(setup, capsys)["settings"]
    for name, value in DEFAULT_EXPORT.items():
        assert settings[name] == value
    assert [clip for clip in settings["clips"]] == [
        own("walk", True),
        own("attack", False),
    ]


def test_the_defaults_recorded_are_the_schema_authority_s(setup, capsys):
    settings = written(setup, capsys)["settings"]
    assert settings["stored_directions"] == layered.ALL_DEFAULTS["stored_directions"]
    assert settings["direction_names"] == list(layered.ALL_DEFAULTS["direction_names"])
    assert settings["mirrors"] == list(layered.ALL_DEFAULTS["mirrors"])
    for key in ("frame_path", "atlas_path", "sheet_path", "atlas_padding"):
        assert settings["export"][key] == layered.ALL_DEFAULTS[f"export.{key}"]
    assert settings["export"]["formats"] == list(layered.ALL_DEFAULTS["export.formats"])


def test_the_samples_keep_the_full_ring_and_global_timing(setup, capsys):
    document = written(setup, capsys)
    assert [c["stored_directions"] for c in document["clips"]] == [list(range(8))] * 2
    assert [c["mirrors"] for c in document["clips"]] == [[], []]
    assert [c["fps"] for c in document["clips"]] == [4.0, 4.0]
    assert len(document["directions"]) == 8
    # walk: 4 samples, attack: 3, in each of the 8 directions, clip by clip.
    order = [(f["clip"], f["direction"], f["index"]) for f in document["frames"]]
    assert order == [
        (clip, direction, index)
        for clip, count in (("walk", 4), ("attack", 3))
        for direction in range(8)
        for index in range(count)
    ]


def test_each_sample_is_located_in_every_png_it_was_written_to(setup, capsys):
    document = written(setup, capsys)
    png = [i for i, a in enumerate(document["artifacts"]) if a["kind"] == "sheet"]
    assert png == [0, 1]
    for frame in document["frames"]:
        assert [place["artifact"] for place in frame["locations"]] == png
        colour, normal = frame["locations"]
        assert (colour["x"], colour["y"]) == (normal["x"], normal["y"])
        assert (colour["w"], colour["h"]) == (16, 16)


def test_the_early_fingerprint_is_the_manifest_s(setup, capsys):
    work = setup.tmp_path / "work"
    document = written(setup, capsys, "--work-dir", str(work))
    # The frames carry the fingerprint to stylize, and the manifest ends with
    # the same one (see the command test that pins its worked-out value).
    from moskophoros import export

    assert document["fingerprint"] == export.fingerprint(
        document["generator"],
        document["settings"],
        document["source"]["sha256"],
    )


def test_no_manifest_only_field_reaches_the_capture_jobs(setup, capsys):
    work = setup.tmp_path / "work"
    written(setup, capsys, "--work-dir", str(work))
    for mode in ("measure", "render"):
        job = json.loads((work / mode / "job.json").read_text())
        assert set(job["settings"]) == LEGACY_KEYS
        assert all(
            set(c) == {"name", "loop", "frames"} for c in job["settings"]["clips"]
        )


# Reloading its own output


def test_a_manifest_reloads_itself_in_a_fresh_root_without_the_original_files(
    setup, capsys, tmp_path
):
    palette = tmp_path / "palette.hex"
    palette.write_text("102030\n405060\n708090\n")
    written(setup, capsys, "--palette", str(palette), "--depth", "--light", "5,5,30")
    kept = tmp_path / "kept.json"
    shutil.copy(setup.json, kept)
    first = setup.listing()
    palette.unlink()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    argv = [
        "--settings-from",
        str(kept),
        "--no-user-config",
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(elsewhere / "hero.png"),
    ]
    status, _, err = run(capsys, argv)
    assert status == 0, err
    again = {path.name: path.read_bytes() for path in sorted(elsewhere.iterdir())}
    assert again == first
    assert sorted(again) == sorted(first) and "hero.json" in again


def test_a_manifest_reloads_itself_in_place(setup, capsys):
    written(setup, capsys, "--depth")
    first = setup.listing()
    argv = [
        "--settings-from",
        str(setup.json),
        "--no-user-config",
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(setup.png),
    ]
    status, _, err = run(capsys, argv)
    assert status == 0, err
    assert setup.listing() == first


def test_the_loaded_values_keep_their_precedence(setup, capsys):
    written(setup, capsys, "--frames", "3")
    status, _, err = run(
        capsys,
        [
            "--settings-from",
            str(setup.json),
            "--no-user-config",
            "--frames",
            "2",
            "--once",
            "walk",
            "--blender",
            str(setup.fake),
            str(setup.model),
            str(setup.png),
        ],
    )
    assert status == 0, err
    document = json.loads(setup.json.read_text())
    assert document["settings"]["frames"] == 2
    assert [(c["name"], c["loop"]) for c in document["clips"]] == [
        ("walk", False),
        ("attack", True),
    ]


# Export settings that are not available yet


def manifest_with(text, tmp_path, clips=(WALK,)):
    """A complete manifest whose settings include the export settings `text`
    sets, made by the writer: the unavailable values a loaded document may
    hold."""
    made = export_for(text, clips=clips)
    path = tmp_path / "unavailable.json"
    path.write_bytes(made.data)
    return path


# Each text sets export settings away from their inactive defaults, or to an
# equivalent that the null override and the global value would still differ
# from: the keys the command names.
UNAVAILABLE = [
    ("stored_directions: [0, 1, 2, 3, 4, 5, 6, 7]\n", ["settings.stored_directions"]),
    ("stored_directions: [0, 4]\n", ["settings.stored_directions"]),
    ("direction_names: {1: right}\n", ["settings.direction_names"]),
    (
        "stored_directions: [0, 1, 2, 3, 4, 5, 6]\nmirrors: {7: 1}\n",
        ["settings.stored_directions", "settings.mirrors"],
    ),
    ("export: {formats: [frames]}\n", ["settings.export.formats"]),
    ("export: {formats: [atlases, sheet]}\n", ["settings.export.formats"]),
    (
        "export: {frame_path: 'f/{clip}/{frame}{map}.png'}\n",
        ["settings.export.frame_path"],
    ),
    ("export: {atlas_path: 'a/{clip}{map}.png'}\n", ["settings.export.atlas_path"]),
    ("export: {sheet_path: 'sheet-x{map}.png'}\n", ["settings.export.sheet_path"]),
    ("export: {atlas_padding: 2}\n", ["settings.export.atlas_padding"]),
    ("clips: {walk: {fps: 6}}\n", ["settings.clips[0].fps"]),
    # Equal to the global FPS, 12: still not the null that inherits it.
    ("clips: {walk: {fps: 12}}\n", ["settings.clips[0].fps"]),
    (
        "clips: {walk: {stored_directions: [0, 4]}}\n",
        ["settings.clips[0].stored_directions"],
    ),
    # "all" in place of the inheriting null.
    (
        "clips: {walk: {stored_directions: all}}\n",
        ["settings.clips[0].stored_directions"],
    ),
    ("clips: {walk: {mirrors: {}}}\n", ["settings.clips[0].mirrors"]),
    (
        "stored_directions: [0, 1, 2, 3, 4, 5, 6]\nclips: {walk: {mirrors: {7: 1}}}\n",
        ["settings.stored_directions", "settings.clips[0].mirrors"],
    ),
    ("clips: {walk: {output_name: stride}}\n", ["settings.clips[0].output_name"]),
    # An alias equal to the cleaned name it would otherwise take.
    ("clips: {walk: {output_name: walk}}\n", ["settings.clips[0].output_name"]),
]


@pytest.mark.parametrize(("text", "keys"), UNAVAILABLE)
def test_a_manifest_recording_a_non_default_export_setting_is_refused(
    setup, capsys, monkeypatch, tmp_path, text, keys
):
    path = manifest_with(text, tmp_path)
    forbid_blender(monkeypatch)
    status, out, err = run(
        capsys, ["--settings-from", str(path), "--no-user-config", *setup.argv()]
    )
    assert status == 2
    assert out == ""
    problems = [f"{key}: not available yet" for key in keys]
    assert (
        f"--settings-from {str(path)!r}: " + "; ".join(problems) in err.splitlines()[-1]
    )
    assert setup.calls() == []
    assert setup.listing() == {}


@pytest.mark.parametrize(("text", "keys"), UNAVAILABLE)
def test_an_explicit_option_cannot_hide_an_unavailable_setting(
    setup, capsys, monkeypatch, tmp_path, text, keys
):
    path = manifest_with(text, tmp_path)
    forbid_blender(monkeypatch)
    with pytest.raises(cli.UsageError):
        cli.resolve_settings(
            cli.parse_args(
                [
                    "--settings-from",
                    str(path),
                    "--no-user-config",
                    "--fps",
                    "12",
                    "--frames",
                    "2",
                    "--clip",
                    "other",
                    "in.glb",
                    "out.png",
                ]
            )
        )
    assert f"{keys[0]}: not available yet" in capsys.readouterr().err


@pytest.mark.parametrize(
    "text",
    [
        "{}\n",
        "stored_directions: all\ndirection_names: {}\nmirrors: {}\n",
        "export: {formats: [sheet], atlas_padding: 0}\n",
        "clips: {walk: {frames: 2}}\n",
        "fps: 6\nframes: 3\n",
    ],
)
def test_a_manifest_at_the_inactive_defaults_loads(tmp_path, text):
    path = manifest_with(text, tmp_path)
    reused = cli.read_settings(path)
    assert reused.clip == ("walk",)


def test_the_gate_compares_every_inactive_setting_with_the_schema_default():
    unchecked = set(exportsettings.GLOBAL_KEYS) - {"fps", "frames"}
    assert unchecked <= set(layered.ALL_DEFAULTS)
    assert not unchecked & set(layered.DEFAULTS)
