"""`MASK` materials cut out (alpha design ALPHA-2, D-1, D-3; design
§Capture): a texel below the material's `alphaCutoff` is a hole in every
buffer, showing the surface behind it or nothing; the surface gate selects
one surface per pixel; and a stack of see-through surfaces deeper than the
capture renders fails loudly, naming the frame, and publishes nothing."""

import numpy as np
import pytest
from material_models import Model, edges, quad_xy
from test_flat_capture import aligned, loaded
from test_render import render

from moskophoros import cli
from moskophoros.capture import backend, blender

pytestmark = pytest.mark.blender

# Two rows of 0.4 m quads, 0.5 m apart, in a front view of 6 m × 2 m at 20
# pixels per meter.
PPM = 20.0
CELL = (120, 40)
GROUND_PX = (60, 20)
QUAD_UV = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
COLOUR = (200, 100, 50)


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


def slot(index, z=0.0):
    """Quad `index`: twelve to a row, the first row above the second."""
    column, line = index % 12, index // 12
    x0 = -3.0 + 0.5 * column + 0.05
    y0 = 0.15 if line == 0 else -0.85
    return quad_xy(x0, y0, x0 + 0.4, y0 + 0.7, z)


def inside(image, index):
    """The pixels well inside quad `index`."""
    column, line = index % 12, index // 12
    x0 = GROUND_PX[0] + (-3.0 + 0.5 * column + 0.1) * PPM
    x1 = GROUND_PX[0] + (-3.0 + 0.5 * column + 0.4) * PPM
    y_top = 0.8 if line == 0 else -0.2
    y0 = GROUND_PX[1] - y_top * PPM
    y1 = GROUND_PX[1] - (y_top - 0.6) * PPM
    return image[int(y0) : int(y1), int(x0) : int(x1)].reshape(-1, image.shape[-1])


def rows(found, path, tmp_path, workspace="work", **options):
    return render(
        found,
        path,
        tmp_path,
        ppm=PPM,
        cell=CELL,
        ground_px=GROUND_PX,
        supersample=1,
        workspace=workspace,
        **options,
    )


def uniform(model, alpha, *, linear=False):
    return model.texture((4, 4), lambda x, y: (*COLOUR, alpha), linear=linear)


def gradient(model):
    """A horizontal sweep of alpha from 0 to 255, for linear filtering."""
    return model.texture((16, 1), lambda x, y: (*COLOUR, 17 * x), linear=True)


def cutoffs(directory, unlit):
    """Quads of `MASK` materials, each kept or cut whole, but for a linear
    sweep across its cutoff; `KEPT` and `CUT` say which."""
    model = Model()
    white = (1.0, 1.0, 1.0, 1.0)

    def mask(name, color=white, *, texture=None, cutoff=None):
        return model.material(
            name, color, alpha_mode="MASK", cutoff=cutoff, texture=texture, unlit=unlit
        )

    cases = [
        # The default cutoff, 0.5: texel alpha 128 is kept, 127 cut.
        mask("128", texture=uniform(model, 128)),
        mask("127", texture=uniform(model, 127)),
        # An explicit cutoff: 0.25 keeps 70/255 and cuts 60/255.
        mask("70 of 0.25", texture=uniform(model, 70), cutoff=0.25),
        mask("60 of 0.25", texture=uniform(model, 60), cutoff=0.25),
        # The factor's alpha alone, without a texture.
        mask("factor 0.4", (1, 1, 1, 0.4)),
        mask("factor 0.6", (1, 1, 1, 0.6)),
        # Equality at the cutoff keeps the texel.
        mask("factor 0.5", (1, 1, 1, 0.5)),
        mask("factor 0.25 of 0.25", (1, 1, 1, 0.25), cutoff=0.25),
        # The factor's alpha times the texture's: 0.5 · 1 is kept, 0.5 · 200/255
        # cut.
        mask("0.5 of 255", (1, 1, 1, 0.5), texture=uniform(model, 255)),
        mask("0.5 of 200", (1, 1, 1, 0.5), texture=uniform(model, 200)),
        # Linear filtering across the cutoff stays binary.
        mask("sweep", texture=gradient(model)),
    ]
    for index, material in enumerate(cases):
        model.primitive(slot(index), material, texcoords=QUAD_UV)
    return model.write(directory, "cutoffs")


KEPT = (0, 2, 5, 6, 7, 8)
CUT = (1, 3, 4, 9)
SWEEP = 10


@pytest.mark.parametrize("unlit", [False, True], ids=["principled", "unlit"])
def test_the_cutoff_keeps_or_cuts_whole_texels(found, tmp_path, unlit):
    result, _ = rows(found, cutoffs(tmp_path, unlit), tmp_path)
    colour = loaded(result, "color")
    for index in KEPT:
        assert (inside(colour, index)[:, 3] == 255).all(), index
    for index in CUT:
        assert (inside(colour, index) == 0).all(), index
    sweep = inside(colour, SWEEP)
    assert set(sweep[:, 3].tolist()) == {0, 255}
    aligned(result)


def mask_over(directory, distance=1.0):
    """A `MASK` checker 2 m wide, `distance` in front of a body that fills
    only its left half: its holes show the body on the left and nothing on
    the right. Beyond the occlusion distance, the checker leaves the body's
    shade alone."""
    model = Model()

    def checker(x, y):
        return (255, 220, 0, 255) if (x + y) % 2 else (0, 0, 0, 0)

    leaf = model.material(
        "leaf",
        (1, 1, 1, 1),
        alpha_mode="MASK",
        texture=model.texture((8, 8), checker),
    )
    body = model.material("body", (0.2, 0.3, 0.9, 1))
    model.primitive(quad_xy(-1.0, -0.8, 1.0, 0.8, distance), leaf, texcoords=QUAD_UV)
    model.primitive(quad_xy(-1.0, -0.8, 0.0, 0.8, 0.0), body)
    return model.write(directory, "over")


def body_alone(directory):
    """`mask_over`'s body alone, with the same material codes."""
    model = Model()
    model.material("leaf", (1, 1, 1, 1), alpha_mode="MASK")
    body = model.material("body", (0.2, 0.3, 0.9, 1))
    model.primitive(quad_xy(-1.0, -0.8, 0.0, 0.8, 0.0), body)
    return model.write(directory, "alone")


def test_holes_show_the_body_behind_in_every_buffer_or_nothing(found, tmp_path):
    over, _ = rows(found, mask_over(tmp_path), tmp_path, workspace="over")
    alone, _ = rows(found, body_alone(tmp_path), tmp_path, workspace="alone")
    ids = loaded(over, "matid")
    code = (ids[..., 0] << 8) | ids[..., 1]
    through = (ids[..., 3] == 255) & (code == 2)
    left = np.zeros(code.shape, dtype=bool)
    left[:, : GROUND_PX[0]] = True
    # The leaf's holes over the body show the body, and over the background
    # nothing at all.
    assert through.any() and (through <= left).all()
    holes_right = (ids[..., 3] == 0) & ~left
    holes_right[:, GROUND_PX[0] + int(PPM) :] = False
    assert holes_right.any()
    for name in ("color", "matid", "shade", "normal", "depth"):
        mine, theirs = loaded(over, name), loaded(alone, name)
        np.testing.assert_array_equal(mine[through], theirs[through], err_msg=name)
        assert (mine[holes_right] == 0).all(), name
    aligned(over)


# The limit: 64 surfaces that let light through, and no more.


def stack(directory, holes, over_body):
    """`holes` cut-out quads, each wholly a hole, stacked in front of a body
    or of nothing. Every surface occludes as if solid (alpha design D-7), so
    the stack starts beyond the occlusion distance, 0.3 m, and leaves the
    body's shade as it is alone."""
    model = Model()
    hole = model.material("hole", (1, 1, 1, 0), alpha_mode="MASK")
    body = model.material("body", (0.9, 0.2, 0.2, 1))
    for layer in range(holes):
        model.primitive(quad_xy(-0.5, -0.5, 0.5, 0.5, 0.5 + 0.01 * layer), hole)
    if over_body:
        model.primitive(quad_xy(-0.5, -0.5, 0.5, 0.5, 0.0), body)
    return model.write(directory, f"stack-{holes}")


SMALL = dict(ppm=10.0, cell=(16, 16), ground_px=(8, 8), supersample=1)


@pytest.mark.parametrize(
    "over_body", [True, False], ids=["over a body", "over nothing"]
)
def test_64_holes_render_correctly(found, tmp_path, over_body):
    result, _ = render(found, stack(tmp_path, 64, over_body), tmp_path, **SMALL)
    reference, _ = render(
        found, stack(tmp_path, 0, over_body), tmp_path, workspace="none", **SMALL
    )
    for name in ("color", "matid", "normal", "depth"):
        np.testing.assert_array_equal(
            loaded(result, name), loaded(reference, name), err_msg=name
        )
    assert loaded(result, "color")[..., 3].any() == over_body
    # The shade covers the same pixels. Each transparent bounce advances
    # Cycles' random sequence, so occlusion's one-sample noise at the quad's
    # convex edges moves; an open flat surface, 137 at the defaults, is
    # exact whatever the noise.
    mine, theirs = loaded(result, "shade"), loaded(reference, "shade")
    np.testing.assert_array_equal(mine[..., 3], theirs[..., 3])
    flat = theirs[..., 0] == 137
    assert flat.any() == over_body
    np.testing.assert_array_equal(mine[flat], theirs[flat])


@pytest.mark.parametrize(
    "over_body", [True, False], ids=["over a body", "over nothing"]
)
def test_65_holes_fail_naming_the_frame_and_publish_nothing(
    found, tmp_path, capsys, over_body
):
    path = stack(tmp_path, 65, over_body)
    out = tmp_path / "out"
    out.mkdir()
    earlier = {"stack-65.png": b"earlier sheet", "stack-65.json": b"earlier json"}
    for name, data in earlier.items():
        (out / name).write_bytes(data)
    status = cli.run(
        [
            "--no-user-config",
            "--blender",
            str(found.path),
            "--cell",
            "16x16",
            "--supersample",
            "1",
            "--directions",
            "1",
            "--no-preview",
            str(path),
            str(out / "stack-65.png"),
        ]
    )
    err = capsys.readouterr().err
    assert status == 5, err
    assert f"{path.resolve()}: clip 'static', direction 0, frame 0 (t = 0.0 s)" in err
    assert "crossed more than 64 surfaces that still let light through" in err
    assert "(the limit is 64)" in err
    assert {p.name: p.read_bytes() for p in out.iterdir()} == earlier


# Determinism and restoration


def test_repeat_renders_of_cutouts_are_byte_identical(found, tmp_path):
    path = edges(tmp_path)
    options = dict(pitch=30.0, ppm=40.0, cell=(64, 64), ground_px=(32, 48))
    first, _ = render(found, path, tmp_path, workspace="one", supersample=2, **options)
    second, _ = render(found, path, tmp_path, workspace="two", supersample=2, **options)
    for name in ("color", "matid", "shade", "normal", "depth"):
        (a,) = [buffers[name] for buffers in first.buffers.values()]
        (b,) = [buffers[name] for buffers in second.buffers.values()]
        assert a.read_bytes() == b.read_bytes(), name


def test_a_cutout_frame_is_the_same_alone_and_after_a_count_render(found, tmp_path):
    path = edges(tmp_path)
    options = dict(pitch=30.0, ppm=40.0, cell=(64, 64), ground_px=(32, 48))
    sequence, _ = render(
        found, path, tmp_path, directions=4, supersample=2, workspace="seq", **options
    )
    alone, _ = render(
        found, path, tmp_path, start=180.0, supersample=2, workspace="one", **options
    )
    within = list(sequence.buffers.values())[2]
    (single,) = alone.buffers.values()
    for name in ("color", "matid", "shade", "normal", "depth"):
        assert within[name].read_bytes() == single[name].read_bytes(), name
