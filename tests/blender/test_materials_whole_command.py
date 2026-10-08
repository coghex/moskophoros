"""`--materials` in the whole command, in real Blender: the library's look is
repeatable, the old looks are untouched without one, and one library colours a
material the same on subjects built differently (material styling design,
Verification strategy)."""

import json

import pytest
from material_models import GREY, Model, cube, quad_xy
from PIL import Image

from moskophoros import cli, stylize
from moskophoros.capture import backend, blender
from moskophoros.sampling import ImageFrame

pytestmark = pytest.mark.blender

FAST = ["--supersample", "4", "--cell", "24x24", "--fps", "4", "--view", "side"]
COLORS = ((20, 20, 30), (200, 60, 50), (60, 180, 90), (230, 220, 120), (250, 250, 250))
LIBRARY = {
    "schema": "moskophoros.materials/1",
    "ramps": {"metal": [1, 2, 3, 4], "cloth": [2, 3]},
    "default": "cloth",
    "materials": {"steel": {"uses": "metal"}},
}


@pytest.fixture(scope="module")
def found():
    try:
        return blender.locate()
    except backend.BackendError as error:
        pytest.fail(str(error), pytrace=False)


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    directory = tmp_path_factory.mktemp("inputs")
    palette = directory / "palette.hex"
    palette.write_text("".join(bytes(color).hex() + "\n" for color in COLORS))
    library = directory / "materials.json"
    library.write_text(json.dumps(LIBRARY))
    return palette, library


def two_cubes(directory, stem, materials):
    """Two cubes side by side with a pillar between them; `materials(model)`
    returns the materials of the left cube, the right cube and the pillar."""
    model = Model()
    left, right, pillar = materials(model)
    model.primitive(cube((-0.45, 0.35, 0.0), 0.3), left)
    model.primitive(cube((0.45, 0.35, 0.0), 0.3), right)
    model.primitive(quad_xy(-0.1, 0.0, 0.1, 0.8, 0.0), pillar)
    return model.write(directory, stem)


def subject_a(directory):
    """`steel` is one material; the pillar is `cloth`."""

    def materials(model):
        steel = model.material("steel", (0.8, 0.1, 0.1, 1.0))
        return steel, steel, model.material("cloth", GREY)

    return two_cubes(directory, "a", materials)


def subject_b(directory):
    """The same geometry: `steel` is two materials of other colours, at other
    indices, among unused ones; the pillar is `cloth` again."""

    def materials(model):
        model.material("padding", (0.5, 0.5, 0.5, 1.0))
        blue = model.material("steel", (0.1, 0.1, 0.9, 1.0))
        model.material("more padding", (0.4, 0.4, 0.4, 1.0))
        yellow = model.material("steel", (0.9, 0.9, 0.1, 1.0))
        return blue, yellow, model.material("cloth", (0.2, 0.7, 0.2, 1.0))

    return two_cubes(directory, "b", materials)


def run(capsys, found, model, outfile, *options):
    argv = [
        *FAST,
        *options,
        "--blender",
        str(found.path),
        str(model),
        str(outfile),
    ]
    status = cli.run(argv)
    out, err = capsys.readouterr()
    return status, out, err


def listing(directory):
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


def colours(path):
    with Image.open(path) as image:
        return set(image.get_flattened_data())


@pytest.mark.parametrize("look", ["plain", "mode"])
def test_a_library_gives_byte_identical_outputs_on_repeat_and_on_reuse(
    capsys, found, inputs, tmp_path, look
):
    palette, library = inputs
    model = subject_a(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    options = ["--reduce", look, "--palette", str(palette), "--materials", str(library)]
    status, _, _ = run(capsys, found, model, out / "a.png", *options)
    assert status == 0
    first = listing(out)
    assert sorted(first) == ["a.json", "a.png", "a.static.gif"]
    assert run(capsys, found, model, out / "a.png", *options)[0] == 0
    assert listing(out) == first
    description = json.loads(first["a.json"])
    style = description["settings"]["style"]
    assert style["materials"]["source"] == "materials.json"
    assert style["shade_range"] == list(backend.DEFAULT_SHADE_RANGE)

    # Reuse needs neither file.
    palette.rename(palette.with_name("moved.hex"))
    library.rename(library.with_name("moved.json"))
    try:
        reuse = ["--settings-from", str(out / "a.json")]
        assert run(capsys, found, model, out / "a.png", *reuse)[0] == 0
        assert listing(out) == first
    finally:
        palette.with_name("moved.hex").rename(palette)
        library.with_name("moved.json").rename(library)

    # Only ramp entries and the transparent background appear.
    allowed = {(0, 0, 0, 0)} | {(*COLORS[i], 255) for i in (1, 2, 3, 4)}
    assert colours(out / "a.png") <= allowed
    assert len(colours(out / "a.png") - {(0, 0, 0, 0)}) > 1


@pytest.mark.parametrize("look", ["plain", "mode"])
@pytest.mark.parametrize("paletted", [False, True])
def test_without_a_library_the_sheet_and_previews_are_the_colour_only_output(
    capsys, found, inputs, tmp_path, monkeypatch, look, paletted
):
    palette, _ = inputs
    model = subject_a(tmp_path)
    options = ["--reduce", look]
    if paletted:
        options += ["--palette", str(palette)]
    out = tmp_path / "out"
    out.mkdir()
    assert run(capsys, found, model, out / "a.png", *options)[0] == 0
    with_buffers = listing(out)

    # The same run through the reduction given the colour alone, as it was
    # before frames carried buffers: the identity list, library and range
    # are not even passed.
    real = getattr(stylize, look)

    def colour_only(frames, factor, **kwargs):
        assert "library" not in kwargs and "shade_range" not in kwargs
        kwargs.pop("identities", None)
        bare = (ImageFrame(f.address, f.pixels, f.metadata) for f in frames)
        return real(bare, factor, **kwargs)

    monkeypatch.setattr(stylize, look, colour_only)
    other = tmp_path / "colour-only"
    other.mkdir()
    assert run(capsys, found, model, other / "a.png", *options)[0] == 0
    assert listing(other) == with_buffers
    description = json.loads(with_buffers["a.json"])
    assert description["settings"]["style"]["materials"] is None


def test_one_library_colours_a_material_the_same_on_differently_built_subjects(
    capsys, found, inputs, tmp_path
):
    palette, library = inputs
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    a, b = subject_a(first), subject_b(second)
    with_library = ["--palette", str(palette), "--materials", str(library)]
    plain_palette = ["--palette", str(palette)]

    # Without the library their source colours show through.
    for name, model in (("a", a), ("b", b)):
        status, _, _ = run(
            capsys, found, model, tmp_path / f"{name}-plain.png", *plain_palette
        )
        assert status == 0
    assert colours(tmp_path / "a-plain.png") != colours(tmp_path / "b-plain.png")

    # With it, `steel` is the same on both, however it is built.
    for name, model in (("a", a), ("b", b)):
        status, _, err = run(
            capsys, found, model, tmp_path / f"{name}.png", *with_library
        )
        assert status == 0
        assert "steel" not in err
    sheet_a = (tmp_path / "a.png").read_bytes()
    sheet_b = (tmp_path / "b.png").read_bytes()
    assert sheet_a == sheet_b
    used = colours(tmp_path / "a.png") - {(0, 0, 0, 0)}
    assert used <= {(*COLORS[i], 255) for i in (1, 2, 3, 4)}
