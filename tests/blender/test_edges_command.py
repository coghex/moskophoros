"""The whole command under `--edges hard` and `--edges soft` on a `MASK`
model, in real Blender (alpha design ALPHA-3; D-2, D-4, D-9, D-11, D-13):
hard keeps binary alpha, soft carries the partial alpha its cut-out edges
and outline reduce to, the maps copy it, the previews blend it, and the
capture job is the same under both."""

import json

import numpy as np
import pytest
from PIL import Image
from test_mask_cutouts import mask_over

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

# A front view of the checker 1 m in front of its body, 2 m × 1.6 m at 16
# pixels per meter, supersampled 4 times.
VIEW = ["--pitch", "0", "--directions", "1", "--start-angle", "0"]
SCALE = ["--ppm", "16", "--cell", "40x32", "--ground-px", "20,16", "--supersample", "4"]
LIGHT = ["--light", "-20,30,40", "--light-ambient", "0.3"]


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def command(found, model, out, edges, *options):
    out.mkdir()
    work = out / "work"
    status = cli.run(
        [
            "--no-user-config",
            "--blender",
            str(found.path),
            *VIEW,
            *SCALE,
            "--edges",
            edges,
            "--depth",
            "--work-dir",
            str(work),
            *options,
            str(model),
            str(out / "over.png"),
        ]
    )
    return status, work


def loaded(path):
    with Image.open(path) as image:
        return np.asarray(image)


@pytest.fixture(scope="module")
def runs(found, tmp_path_factory):
    directory = tmp_path_factory.mktemp("edges")
    model = mask_over(directory)
    results = {}
    for edges in ("hard", "soft"):
        # The same output and work paths for both, which the jobs name; each
        # run is then moved aside.
        run = directory / "run"
        status, _ = command(found, model, run, edges, *LIGHT)
        assert status == 0, edges
        out = run.rename(directory / edges)
        results[edges] = (out, out / "work")
    return results


def test_hard_keeps_binary_alpha_and_soft_carries_partial_alpha(runs):
    hard = loaded(runs["hard"][0] / "over.png")[..., 3]
    soft = loaded(runs["soft"][0] / "over.png")[..., 3]
    assert set(np.unique(hard)) == {0, 255}
    partial = (soft > 0) & (soft < 255)
    assert partial.any()
    # Every pixel hard keeps, soft keeps too; soft adds partial pixels where
    # less than half a block shows a surface.
    assert ((hard == 255) <= (soft > 0)).all()
    assert ((hard == 0) & partial).any()
    for edges in ("hard", "soft"):
        style = json.loads((runs[edges][0] / "over.json").read_text())["settings"][
            "style"
        ]
        assert style["edges"] == edges


@pytest.mark.parametrize("edges", ["hard", "soft"])
def test_the_maps_alpha_follows_the_colours(runs, edges):
    out = runs[edges][0]
    alpha = loaded(out / "over.png")[..., 3]
    normal = loaded(out / "over.normal.png")
    depth = loaded(out / "over.depth.png")
    assert np.array_equal(normal[..., 3], alpha)
    assert np.array_equal(depth != 0, alpha > 0)


def test_the_previews_flat_and_lit_are_written_under_soft_edges(runs):
    out = runs["soft"][0]
    for name in ("over.static.gif", "over-lit.static.gif"):
        with Image.open(out / name) as image:
            assert image.format == "GIF"


def test_a_partial_pixel_previews_as_its_blend_over_the_grey(runs):
    out = runs["soft"][0]
    colour = loaded(out / "over.png")
    with Image.open(out / "over.static.gif") as image:
        preview = np.asarray(image.convert("RGB"))[::4, ::4]
    alpha = colour[..., 3:4].astype(np.int64)
    blended = (2 * (colour[..., :3] * alpha + 128 * (255 - alpha)) + 255) // 510
    assert np.array_equal(preview, blended)


def test_the_capture_jobs_are_the_same_under_hard_and_soft(runs):
    for phase in ("measure", "render"):
        hard = (runs["hard"][1] / phase / "job.json").read_bytes()
        soft = (runs["soft"][1] / phase / "job.json").read_bytes()
        assert hard == soft, phase
