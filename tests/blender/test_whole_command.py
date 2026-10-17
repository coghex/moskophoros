"""The whole `moskophoros` command on a generated rigged model, in real
Blender.

The model has a looping clip, `walk`, a one-shot clip, `attack`, and a clip
whose root travels, `slide`. Every failing run starts from a directory of
earlier outputs and must leave them byte-identical.
"""

import json
import shutil

import numpy as np
import pytest
from glb_writer import GlbWriter
from PIL import Image
from shading import DEFAULT_RANGE

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

FAST = ["--supersample", "2", "--cell", "16x16", "--fps", "4"]
OUTPUTS = [
    "hero.attack.gif",
    "hero.json",
    "hero.normal.png",
    "hero.png",
    "hero.walk.gif",
]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def box(x0, y0, z0, x1, y1, z1):
    """Triangles of an axis-aligned box."""
    corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4)]
    faces.append((1, 5, 7, 3))
    triangles = []
    for a, b, c, d in faces:
        triangles += [corners[i] for i in (a, b, c, a, c, d)]
    return triangles


def rigged_model(directory):
    """A body on joint `hips` and a head on its child joint `head`.

    `walk` sways the head and returns, `attack` raises it 0.4 m, `slide`
    moves the hips 1 m across the ground, and `nod` tips the head forward
    over 0.5 s.
    """
    model = GlbWriter()
    head_joint = model.node("head", translation=(0.0, 0.5, 0.0))
    hips = model.node("hips", children=[head_joint])
    skin = model.skin(
        [hips, head_joint],
        [
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
            (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -0.5, 0, 1),
        ],
    )
    body = box(-0.15, 0.0, -0.1, 0.15, 0.5, 0.1)
    head = box(-0.1, 0.5, -0.1, 0.1, 0.7, 0.1)
    red = model.material((0.8, 0.1, 0.1, 1.0))
    mesh = model.mesh(
        body + head,
        joints=[(0, 0, 0, 0)] * len(body) + [(1, 0, 0, 0)] * len(head),
        skin_weights=[(1, 0, 0, 0)] * (len(body) + len(head)),
        material=red,
    )
    model.scene([hips, model.node("body", mesh=mesh, skin=skin)], default=True)
    model.animation(
        "walk",
        [
            (
                head_joint,
                "translation",
                [0.0, 0.5, 1.0],
                [(0.0, 0.5, 0.0), (0.05, 0.5, 0.0), (0.0, 0.5, 0.0)],
            )
        ],
    )
    model.animation(
        "attack",
        [(head_joint, "translation", [0.0, 0.5], [(0.0, 0.5, 0.0), (0.0, 0.9, 0.0)])],
    )
    model.animation(
        "slide",
        [(hips, "translation", [0.0, 1.0], [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])],
    )
    model.animation(
        "nod",
        [(head_joint, "translation", [0.0, 0.5], [(0.0, 0.5, 0.0), (0.0, 0.5, 0.06)])],
    )
    return model.write(directory, "hero")


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    return rigged_model(tmp_path_factory.mktemp("model"))


def run(capsys, found, model, outfile, *options, blender_path=None, base=FAST):
    argv = [
        *base,
        *options,
        "--blender",
        str(found.path if blender_path is None else blender_path),
        str(model),
        str(outfile),
    ]
    status = cli.run(argv)
    out, err = capsys.readouterr()
    return status, out, err


def listing(directory):
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


@pytest.fixture(scope="module")
def earlier(found, model, tmp_path_factory):
    """A successful run's outputs, from `walk` and `attack`."""
    out = tmp_path_factory.mktemp("earlier")
    status = cli.run(
        [
            *FAST,
            "--clip",
            "walk",
            "--clip",
            "attack",
            "--once",
            "attack",
            "--blender",
            str(found.path),
            str(model),
            str(out / "hero.png"),
        ]
    )
    assert status == 0
    return out


@pytest.fixture
def out(earlier, tmp_path):
    """A directory holding a copy of the earlier outputs."""
    directory = tmp_path / "out"
    shutil.copytree(earlier, directory)
    return directory


SHEET = ["--clip", "walk", "--clip", "attack", "--once", "attack"]


def test_the_complete_output_set(earlier):
    assert sorted(path.name for path in earlier.iterdir()) == OUTPUTS
    description = json.loads((earlier / "hero.json").read_text())
    assert description["generator"]["blender"].startswith("5.2.")
    assert description["generator"]["renderer"] == "cycles"
    assert "studio_light" not in description["generator"]
    assert description["generator"]["color"]["technique"] == "cycles-flat-emission"
    assert [(c["name"], c["loop"], c["frame_count"]) for c in description["clips"]] == [
        ("walk", True, 4),
        ("attack", False, 3),
    ]
    assert len(description["directions"]) == 8
    assert len(description["frames"]) == (4 + 3) * 8
    with Image.open(earlier / "hero.png") as image:
        assert image.mode == "RGBA"
        assert image.size == (4 * 16, 2 * 8 * 16)
        assert image.getextrema()[3] == (0, 255)  # drawn, and transparent around
        colour = np.asarray(image)
    # The normal map: the sheet's size and alpha, a unit normal per pixel.
    assert description["maps"] == {"normal": {"file": "hero.normal.png"}, "depth": None}
    with Image.open(earlier / "hero.normal.png") as image:
        assert image.mode == "RGBA"
        normal = np.asarray(image)
    np.testing.assert_array_equal(normal[..., 3], colour[..., 3])
    assert (normal[colour[..., 3] == 0] == 0).all()
    covered = normal[colour[..., 3] == 255][:, :3].astype(np.float64) * 2 / 255 - 1
    lengths = np.linalg.norm(covered, axis=-1)
    assert np.abs(lengths - 1).max() < 0.01
    # Mostly facing the viewer side of the screen.
    assert (covered[:, 2] > 0).mean() > 0.9
    for name in ("walk", "attack"):
        with Image.open(earlier / f"hero.{name}.gif") as image:
            assert image.size == (8 * 16 * 4, 16 * 4)
            assert image.n_frames == {"walk": 4, "attack": 3}[name]


def test_no_preview_omits_the_gifs(capsys, found, model, tmp_path):
    status, _, err = run(
        capsys, found, model, tmp_path / "hero.png", *SHEET, "--no-preview"
    )
    assert (status, err) == (0, "")
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "hero.json",
        "hero.normal.png",
        "hero.png",
    ]


def test_two_runs_give_byte_identical_outputs(capsys, found, model, earlier, out):
    status, _, err = run(capsys, found, model, out / "hero.png", *SHEET)
    assert (status, err) == (0, "")
    assert listing(out) == listing(earlier)


def test_two_mode_runs_give_byte_identical_outputs(capsys, found, model, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    for directory in (first, second):
        directory.mkdir()
        status, _, err = run(
            capsys, found, model, directory / "hero.png", *SHEET, "--reduce", "mode"
        )
        assert (status, err) == (0, "")
    assert listing(first) == listing(second)
    description = json.loads((first / "hero.json").read_text())
    assert description["settings"]["style"] == {
        "reduce": "mode",
        "edges": "hard",
        "palette": None,
        "materials": None,
    }
    assert description["settings"]["shade"]["range"] == list(DEFAULT_RANGE)


def test_settings_reuse_with_an_explicit_override(capsys, found, model, earlier, out):
    status, _, err = run(
        capsys,
        found,
        model,
        out / "reused.png",
        "--settings-from",
        str(earlier / "hero.json"),
        "--fps",
        "2",
        *SHEET,
        base=["--supersample", "2", "--cell", "16x16"],
    )
    assert (status, err) == (0, "")
    before = json.loads((earlier / "hero.json").read_text())["settings"]
    after = json.loads((out / "reused.json").read_text())["settings"]
    assert after == before | {"fps": 2.0}


@pytest.mark.parametrize(
    "previews",
    [
        (),
        ("--no-preview",),
        ("--no-normals",),
        ("--depth",),
        ("--light", "-20,30,40", "--light-ambient", "0.2"),
    ],
    ids=["on", "off", "no normals", "depth", "light"],
)
def test_a_sheet_regenerated_from_itself_is_byte_identical(
    capsys, found, model, tmp_path, previews
):
    """Settings design D-16: loading a sheet, with the same model and no
    other options, gives the same PNG, JSON, normal map and previews, the
    clip selection, its one-shot marks and the previews and normals flags
    included."""
    first, again = tmp_path / "first", tmp_path / "again"
    first.mkdir()
    again.mkdir()
    status, _, err = run(
        capsys,
        found,
        model,
        first / "hero.png",
        *SHEET,
        "--model-yaw",
        "15",
        *previews,
        base=[*FAST, "--no-user-config"],
    )
    assert (status, err) == (0, "")
    status, _, err = run(
        capsys,
        found,
        model,
        again / "hero.png",
        "--settings-from",
        str(first / "hero.json"),
        "--no-user-config",
        base=[],
    )
    assert (status, err) == (0, "")
    assert listing(again) == listing(first)
    expected = {
        (): OUTPUTS,
        ("--no-preview",): ["hero.json", "hero.normal.png", "hero.png"],
        ("--no-normals",): [name for name in OUTPUTS if name != "hero.normal.png"],
        ("--depth",): sorted([*OUTPUTS, "hero.depth.png"]),
        ("--light", "-20,30,40", "--light-ambient", "0.2"): sorted(
            [*OUTPUTS, "hero-lit.attack.gif", "hero-lit.walk.gif"]
        ),
    }[previews]
    assert sorted(listing(again)) == expected


# Frame counts (settings design D-13, D-16, D-31, D-33, D-38)

FRAMES_CONFIG = """\
frames: 4
clips:
  attack: {frames: 3}
  nod: {frames: auto}
  slide: {frames: 1}
"""


def test_counts_retime_the_sheet_and_its_previews(capsys, found, model, tmp_path):
    config = tmp_path / "frames.yaml"
    config.write_text(FRAMES_CONFIG)
    out = tmp_path / "out"
    out.mkdir()
    status, _, err = run(
        capsys,
        found,
        model,
        out / "hero.png",
        *SHEET,
        "--config",
        str(config),
        base=[
            "--supersample",
            "2",
            "--cell",
            "16x16",
            "--fps",
            "12",
            "--no-user-config",
        ],
    )
    assert status == 0, err
    # The file's global names attack, which keeps its own (D-41).
    assert err == (
        "moskophoros: warning: the global frame count 4 does not reach the clips "
        'with their own: "attack" (3)\n'
    )
    description = json.loads((out / "hero.json").read_text())
    clips = {clip["name"]: clip for clip in description["clips"]}
    # walk takes the global 4 over 1 s; attack, a one-shot, its own 3 over
    # 0.5 s. Each frame lasts exactly 1/12 s.
    assert [
        (
            clips[name]["frame_count"],
            clips[name]["frame_duration_s"],
            clips[name]["time_scale"],
        )
        for name in ("walk", "attack")
    ] == [(4, 1 / 12, 3.0), (3, 1 / 12, 3.0)]
    times = {
        name: sorted(
            {
                frame["time_s"]
                for frame in description["frames"]
                if frame["clip"] == name
            }
        )
        for name in ("walk", "attack")
    }
    assert times == {"walk": [0.0, 0.25, 0.5, 0.75], "attack": [0.0, 0.25, 0.5]}
    # The GIFs round 1/12 s to 80 ms; a one-shot holds its last frame 500 ms
    # longer.
    for name, delays in (("walk", [80] * 4), ("attack", [80, 80, 580])):
        with Image.open(out / f"hero.{name}.gif") as image:
            seen = []
            for index in range(image.n_frames):
                image.seek(index)
                seen.append(image.info["duration"])
        assert seen == delays, name


def test_a_counted_sheet_regenerated_from_itself_is_byte_identical(
    capsys, found, model, tmp_path
):
    """Settings design D-16 with counts: a global count (walk), a clip's own
    count (attack), a clip's own auto (nod) and a one-frame clip (slide)."""
    config = tmp_path / "frames.yaml"
    config.write_text(FRAMES_CONFIG)
    first, again = tmp_path / "first", tmp_path / "again"
    first.mkdir()
    again.mkdir()
    selection = [*SHEET, "--clip", "nod", "--clip", "slide", "--root-motion", "keep"]
    status, _, err = run(
        capsys,
        found,
        model,
        first / "hero.png",
        *selection,
        "--config",
        str(config),
        base=[*FAST, "--no-user-config"],
    )
    assert status == 0, err
    assert "does not reach the clips with their own" in err
    recorded = json.loads((first / "hero.json").read_text())
    assert recorded["settings"]["frames"] == 4
    assert [clip["frames"] for clip in recorded["settings"]["clips"]] == [
        None,
        3,
        "auto",
        1,
    ]
    assert [clip["frame_count"] for clip in recorded["clips"]] == [4, 3, 2, 1]
    config.unlink()
    status, _, err = run(
        capsys,
        found,
        model,
        again / "hero.png",
        "--settings-from",
        str(first / "hero.json"),
        "--no-user-config",
        base=[],
    )
    assert (status, err) == (0, "")
    assert listing(again) == listing(first)


# One failing run per exit code, each leaving the earlier outputs as they were


def test_a_nonempty_work_dir_fails_with_2(capsys, found, model, out, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "kept").write_text("kept")
    before = listing(out)
    status, _, err = run(
        capsys, found, model, out / "hero.png", *SHEET, "--work-dir", str(work)
    )
    assert status == 2
    assert "is not empty" in err
    assert listing(out) == before
    assert listing(work) == {"kept": b"kept"}


def test_travelling_root_motion_fails_with_3(capsys, found, model, out):
    before = listing(out)
    status, _, err = run(capsys, found, model, out / "hero.png", "--clip", "slide")
    assert status == 3
    assert "clip 'slide' moves its root node" in err
    assert "('hips')" in err
    assert "export the clip in place" in err
    assert listing(out) == before


def test_a_source_changed_during_capture_fails_with_3(
    capsys, found, model, out, tmp_path
):
    changing = tmp_path / "model" / "hero.glb"
    changing.parent.mkdir()
    shutil.copy(model, changing)
    wrapper = tmp_path / "blender"
    wrapper.write_text(
        "#!/bin/sh\n"
        f'"{found.path}" "$@"\n'
        "status=$?\n"
        'case "$*" in *measure/job.json*) '
        f"printf ' ' >> '{changing}';; esac\n"
        "exit $status\n"
    )
    wrapper.chmod(0o755)
    before = listing(out)
    status, _, err = run(
        capsys, found, changing, out / "hero.png", *SHEET, blender_path=wrapper
    )
    assert status == 3
    assert "changed during capture" in err
    assert listing(out) == before


def test_a_reused_fixed_cell_that_overflows_fails_with_4(
    capsys, found, model, out, tmp_path
):
    # Fitted to walk alone, the cell has no room for attack's raised head.
    walk = tmp_path / "walk"
    walk.mkdir()
    status, _, _ = run(capsys, found, model, walk / "walk.png", "--clip", "walk")
    assert status == 0
    before = listing(out)
    status, _, err = run(
        capsys,
        found,
        model,
        out / "hero.png",
        "--settings-from",
        str(walk / "walk.json"),
        "--clip",
        "attack",
        "--once",
        "attack",
    )
    assert status == 4
    assert "overflows" in err
    assert "clip 'attack'" in err
    assert listing(out) == before


def test_an_unusable_blender_fails_with_5(capsys, found, model, out, tmp_path):
    before = listing(out)
    status, _, err = run(
        capsys,
        found,
        model,
        out / "hero.png",
        *SHEET,
        blender_path=tmp_path / "no-blender",
    )
    assert status == 5
    assert "is not an executable file" in err
    assert listing(out) == before


def test_a_one_shot_clip_whose_endpoint_rounds_past_t1(capsys, tmp_path, found):
    # The clip's range in the JSON is 0 to 0.833333313465118, written to 15
    # digits as RobotExpressive's Punch is. At 12 fps, n = 10, and
    # 0 + 10·d/10 rounds past t1; the last sample must be t1 itself.
    t1 = 0.833333313465118
    model = GlbWriter()
    arm = model.node("arm", mesh=model.mesh(box(-0.1, 0.0, -0.1, 0.1, 0.5, 0.1)))
    model.scene([arm], default=True)
    model.animation(
        "punch", [(arm, "translation", [0.0, t1], [(0, 0, 0), (0, 0.2, 0)])]
    )
    sampler_input = model.document["animations"][0]["samplers"][0]["input"]
    model.document["accessors"][sampler_input]["max"] = [t1]
    path = model.write(tmp_path, "puncher")
    out = tmp_path / "out"
    out.mkdir()
    status, _, err = run(
        capsys,
        found,
        path,
        out / "puncher.png",
        "--once",
        "punch",
        "--fps",
        "12",
        base=["--supersample", "2", "--cell", "16x16"],
    )
    assert (status, err) == (0, "")
    description = json.loads((out / "puncher.json").read_text())
    times = sorted({frame["time_s"] for frame in description["frames"]})
    assert len(times) == 11
    assert times[-1] == t1


@pytest.mark.parametrize("look", ["plain", "mode"])
def test_paletted_looks_are_byte_identical_on_repeat_and_reuse(
    capsys, found, model, tmp_path, look
):
    palette = tmp_path / "test.hex"
    palette.write_text("000000\nff0000\nffffff\n")
    output = tmp_path / "out"
    output.mkdir()
    options = [*SHEET, "--reduce", look, "--palette", str(palette)]
    assert run(capsys, found, model, output / "hero.png", *options) == (0, "", "")
    before = listing(output)
    with Image.open(output / "hero.png") as image:
        colors = set(image.get_flattened_data())
    assert colors <= {
        (0, 0, 0, 0),
        (0, 0, 0, 255),
        (255, 0, 0, 255),
        (255, 255, 255, 255),
    }
    assert any(c[3] for c in colors)
    assert run(capsys, found, model, output / "hero.png", *options) == (0, "", "")
    assert listing(output) == before
    palette.unlink()
    assert run(
        capsys,
        found,
        model,
        output / "hero.png",
        *SHEET,
        "--settings-from",
        str(output / "hero.json"),
    ) == (0, "", "")
    assert listing(output) == before
