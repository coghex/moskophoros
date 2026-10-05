"""The whole `moskophoros` command on a generated rigged model, in real
Blender.

The model has a looping clip, `walk`, a one-shot clip, `attack`, and a clip
whose root travels, `slide`. Every failing run starts from a directory of
earlier outputs and must leave them byte-identical.
"""

import json
import shutil

import pytest
from glb_writer import GlbWriter
from PIL import Image

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

FAST = ["--supersample", "2", "--cell", "16x16", "--fps", "4"]
OUTPUTS = ["hero.attack.gif", "hero.json", "hero.png", "hero.walk.gif"]


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

    `walk` sways the head and returns, `attack` raises it 0.4 m, and `slide`
    moves the hips 1 m across the ground.
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
    assert description["generator"]["renderer"] == "workbench"
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
    assert description["settings"]["style"] == {"reduce": "mode", "palette": None}


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
