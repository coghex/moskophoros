"""The normal and depth buffers: result validation, decoding into the Frames
into stylize interface, and the command's use of them (design §Capture job
and result contract, §Frames into stylize; lighting sheet design D-2, D-10,
D-11, D-12 and D-21)."""

import math
import struct

import numpy as np
import pytest
from capture_buffers import (
    SURFACE,
    depth_samples,
    normal_samples,
    png16,
    write_depth,
    write_normal,
)
from PIL import Image
from test_buffers import COLORS, IDENTITIES, OPTIONS, address, colour, look_argv
from test_capture_backend import encode, png, render_document, render_job
from test_command import Setup, run, speckled_argv
from test_materials_command import HERO_MATERIALS, materialed, named_hero

from moskophoros import stylize
from moskophoros.capture import backend
from moskophoros.capture.backend import BackendError, validate_result
from moskophoros.sampling import (
    DEPTH,
    DEPTH_MAP,
    IDENTITY,
    NORMAL,
    NORMAL_MAP,
    SHADE,
    ImageFrame,
)

SIZE = (6, 8)  # (height, width) of render_document's buffers
COVERED = np.ones(SIZE, dtype=bool)


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def rendered(tmp_path, change=None):
    """Validate a render result after `change(document, tmp_path)`."""
    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    if change is not None:
        change(document, tmp_path)
    return validate_result(job, tmp_path, encode(document))


def samples(name, edit):
    """A change writing frame 0's `name` buffer from its valid samples after
    `edit(samples)`."""

    def change(document, tmp_path):
        path = tmp_path / f"{name}/000000.png"
        values = backend.read_wide_png(path).copy()
        edit(values)
        png16(path, values)

    return change


def at_corner(value):
    def edit(values):
        values[0, 0] = value

    return edit


def file(name, write):
    """A change replacing frame 0's `name` buffer with `write(path)`."""

    def change(document, tmp_path):
        path = tmp_path / f"{name}/000000.png"
        path.unlink()
        write(path)

    return change


def matid_background_corner(document, tmp_path):
    path = tmp_path / "matid/000000.png"
    pixels = np.asarray(Image.open(path)).copy()
    pixels[0, 0] = (0, 0, 0, 0)
    Image.fromarray(pixels, "RGBA").save(path)
    path = tmp_path / "shade/000000.png"
    pixels = np.asarray(Image.open(path)).copy()
    pixels[0, 0] = (0, 0, 0, 0)
    Image.fromarray(pixels, "RGBA").save(path)


def both(*changes):
    def change(document, tmp_path):
        for each in changes:
            each(document, tmp_path)

    return change


def float_bits(value):
    (bits,) = struct.unpack(">I", struct.pack(">f", value))
    return bits >> 16, bits & 0xFFFF


def quantised(n):
    return math.floor((n + 1) / 2 * 65535 + 0.5)


# Requirement 6: the launcher rejects bad normal and depth buffers (exit 5).


def _drop(name):
    def change(document, tmp_path):
        del document["frames"][0]["buffers"][name]

    return change


def _moved(name):
    def change(document, tmp_path):
        (tmp_path / f"{name}/000000.png").rename(tmp_path / f"{name}/other.png")
        document["frames"][0]["buffers"][name] = f"{name}/other.png"

    return change


def _eight_bit(path):
    png(path)


def _greyscale16(path):
    Image.new("I;16", (8, 6)).save(path)


def _wrong_size(path):
    png16(path, normal_samples(np.zeros((6, 7, 3)), np.ones((6, 7), dtype=bool)))


def _filtered(path):
    # Filter type 2 (Up) on row 1: a valid PNG, but not the recorded encoding.
    valid = normal_samples(np.broadcast_to((0, 0, 1.0), (*SIZE, 3)), COVERED)
    png16(path, valid, filters=[0, 2, 0, 0, 0, 0])


def _with_text(path):
    valid = normal_samples(np.broadcast_to((0, 0, 1.0), (*SIZE, 3)), COVERED)
    png16(path, valid, extra_chunks=[(b"tEXt", b"Render time\x0001:02")])


def _corrupt(path):
    write_normal(path, COVERED)
    data = bytearray(path.read_bytes())
    data[-20] ^= 0xFF
    path.write_bytes(bytes(data))


def _not_png(path):
    path.write_bytes(b"not an image")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_drop("normal"), "frame 0 has no normal buffer"),
        (_drop("depth"), "frame 0 has no depth buffer"),
        (_moved("normal"), "normal buffer is 'normal/other.png', not"),
        (_moved("depth"), "depth buffer is 'depth/other.png', not"),
        (file("normal", _eight_bit), "is not 16-bit RGBA \\(bit depth 8"),
        (file("depth", _eight_bit), "is not 16-bit RGBA \\(bit depth 8"),
        (file("normal", _greyscale16), "is not 16-bit RGBA \\(bit depth 16, color"),
        (file("depth", _wrong_size), "is 7x6, not 8x6"),
        (file("normal", _filtered), "filters row 1"),
        (file("depth", _with_text), "not IHDR, IDAT and IEND only"),
        (file("normal", _corrupt), "corrupt"),
        (file("depth", _not_png), "is not a PNG"),
    ],
)
def test_a_missing_misplaced_or_misencoded_buffer_is_a_backend_error(
    tmp_path, change, message
):
    with pytest.raises(BackendError, match=message) as raised:
        rendered(tmp_path, change)
    assert raised.value.exit_code == 5


UNIT = quantised(0.0), quantised(0.0), quantised(1.0)
HALF = quantised(0.0), quantised(0.0), quantised(0.5)
ZERO = (quantised(0.0),) * 3


@pytest.mark.parametrize(
    ("change", "message"),
    [
        # A normal that is not unit length, or none at all, on a surface.
        (samples("normal", at_corner((*HALF, SURFACE))), "not a unit normal"),
        (samples("normal", at_corner((*ZERO, SURFACE))), "not a unit normal"),
        (samples("normal", at_corner((0, 0, 0, SURFACE))), "not a unit normal"),
        # A depth that is no finite number, or not encoded as one.
        (
            samples("depth", at_corner((*float_bits(math.nan), 0, SURFACE))),
            "not a finite depth",
        ),
        (
            samples("depth", at_corner((*float_bits(math.inf), 0, SURFACE))),
            "not a finite depth",
        ),
        (
            samples("depth", at_corner((*float_bits(-math.inf), 0, SURFACE))),
            "not a finite depth",
        ),
        (samples("depth", at_corner((0, 0, 1, SURFACE))), "not a finite depth"),
        # Partial alpha, and background holding a value.
        (samples("normal", at_corner((*UNIT, 1000))), "not an encoded value"),
        (samples("depth", at_corner((0, 0, 0, 1))), "not an encoded value"),
        (samples("normal", at_corner((*UNIT, 0))), "not an encoded value"),
        (samples("depth", at_corner((0, 1, 0, 0))), "not an encoded value"),
        # Coverage that differs from the material ID's: no surface where it
        # has one ...
        (samples("normal", at_corner((0, 0, 0, 0))), "no surface, but the material-ID"),
        (samples("depth", at_corner((0, 0, 0, 0))), "no surface, but the material-ID"),
        # ... and a surface where it has none.
        (matid_background_corner, "normal pixel \\(0, 0\\) is .*, a surface, but"),
        (
            both(
                matid_background_corner,
                samples("normal", at_corner((0, 0, 0, 0))),
            ),
            "depth pixel \\(0, 0\\) is .*, a surface, but",
        ),
    ],
)
def test_bad_normal_and_depth_pixels_are_backend_errors(tmp_path, change, message):
    with pytest.raises(BackendError, match=message) as raised:
        rendered(tmp_path, change)
    assert raised.value.exit_code == 5
    assert "frame 0" in str(raised.value)


def test_a_normal_facing_away_from_the_viewer_is_accepted(tmp_path):
    # Silhouettes give interpolated normals with z below 0.
    normal = np.zeros((*SIZE, 3))
    normal[...] = (0.0, 0.6, 0.8)
    normal[0, 0] = (0.0, math.sqrt(1 - 0.31**2), -0.31)
    normal[0, 1] = (0.0, 0.0, -1.0)

    def change(document, tmp_path):
        write_normal(tmp_path / "normal/000000.png", COVERED, normal)

    rendered(tmp_path, change)


def test_the_unit_length_tolerance():
    tolerance = backend.NORMAL_TOLERANCE
    assert tolerance == 1e-3
    assert backend.unit_normals(
        [
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 1 + tolerance * 0.99),
            (0.0, 0.0, 1 - tolerance * 0.99),
            (0.6, 0.0, -0.8),
        ]
    ).all()
    assert not backend.unit_normals(
        [
            (0.0, 0.0, 1 + tolerance * 1.01),
            (0.0, 0.0, 1 - tolerance * 1.01),
            (0.0, 0.0, 0.0),
            (math.nan, 0.0, 1.0),
            (math.inf, 0.0, 0.0),
            (0.0, -math.inf, 0.0),
        ]
    ).any()


def test_the_encoding_s_worst_case_is_well_within_the_tolerance():
    # Every component off by half a step in the same direction.
    rng = np.random.default_rng(7)
    normals = rng.normal(size=(64, 64, 3))
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    decoded = backend.decode_normal(normal_samples(normals, np.ones((64, 64), bool)))
    assert np.abs(decoded - normals).max() <= 1 / 65535 + 1e-7
    lengths = np.linalg.norm(decoded.astype(np.float64), axis=-1)
    assert np.abs(lengths - 1).max() < 2.7e-5


def test_a_valid_result_with_background_pixels(tmp_path):
    def change(document, tmp_path):
        matid_background_corner(document, tmp_path)
        covered = COVERED.copy()
        covered[0, 0] = False
        write_normal(tmp_path / "normal/000000.png", covered)
        write_depth(tmp_path / "depth/000000.png", covered, 0.0)

    rendered(tmp_path, change)


# Decoding (requirement 7)


def test_decoding_gives_the_normal_and_depth_arrays_with_their_background():
    covered = np.array([[True, True, False], [True, False, True]])
    normals = np.array(
        [
            [(0.0, 0.0, 1.0), (0.6, -0.8, 0.0), (0.3, 0.3, 0.3)],
            [(-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.28, -0.96)],
        ]
    )
    depths = np.array([[0.0, -0.75, 9.0], [1e6, 3.0, -1e-30]])
    normal = backend.decode_normal(normal_samples(normals, covered))
    depth = backend.decode_depth(depth_samples(depths, covered))
    assert normal.dtype == np.float32 and normal.shape == (2, 3, 3)
    assert depth.dtype == np.float32 and depth.shape == (2, 3)
    np.testing.assert_allclose(normal[covered], normals[covered], atol=1.6e-5)
    assert (normal[~covered] == 0).all()
    # Exactly the 32-bit floats, a covered 0 included, and NaN off a surface.
    assert depth[0, 0] == 0.0 and not math.isnan(depth[0, 0])
    assert depth[0, 1] == np.float32(-0.75)
    assert depth[1, 0] == np.float32(1e6)
    assert depth[1, 2] == np.float32(-1e-30)
    assert np.isnan(depth[~covered]).all()


@pytest.mark.parametrize("meters", [1e4, -1e4, 3.0e7, -2.5e30])
def test_a_depth_far_beyond_the_depth_map_s_range_is_carried_intact(tmp_path, meters):
    # ±2047.9375 sheet pixels is at most 2047.9375 / 0.001 m at the smallest
    # scale; these are beyond it at any, and never clamped or rescaled.
    def change(document, tmp_path):
        write_depth(tmp_path / "depth/000000.png", COVERED, meters)

    result = rendered(tmp_path, change)
    paths = next(iter(result.buffers.values()))
    _, depth = backend.decode_normal_depth(paths)
    assert (depth == np.float32(meters)).all()


def test_a_covered_depth_of_zero_is_not_background(tmp_path):
    def change(document, tmp_path):
        matid_background_corner(document, tmp_path)
        covered = COVERED.copy()
        covered[0, 0] = False
        write_normal(tmp_path / "normal/000000.png", covered)
        write_depth(tmp_path / "depth/000000.png", covered, 0.0)

    result = rendered(tmp_path, change)
    paths = next(iter(result.buffers.values()))
    _, depth = backend.decode_normal_depth(paths)
    assert np.isnan(depth[0, 0])
    assert (depth[COVERED & (np.arange(8) > 0)[np.newaxis]] == 0.0).all()
    raw = backend.read_wide_png(paths["depth"])
    assert tuple(raw[0, 0]) == (0, 0, 0, 0)
    assert tuple(raw[0, 1]) == (0, 0, 0, SURFACE)


def test_a_buffer_changed_after_validation_is_a_backend_error(tmp_path):
    result = rendered(tmp_path)
    paths = next(iter(result.buffers.values()))
    paths["depth"].write_bytes(b"truncated")
    with pytest.raises(BackendError, match="depth/000000.png is not a PNG"):
        backend.decode_normal_depth(paths)


# Into stylize (requirement 7)


def surfaces(i):
    rng = np.random.default_rng(300 + i)
    normal = rng.normal(size=(8, 8, 3)).astype(np.float32)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    depth = rng.uniform(-1e4, 1e4, (8, 8)).astype(np.float32)
    depth[:2, :2] = np.nan
    return normal, depth


@pytest.mark.parametrize(
    ("reduce", "palette"),
    [
        (stylize.plain, None),
        (stylize.plain, COLORS),
        (stylize.mode, None),
        (stylize.mode, COLORS),
    ],
    ids=["plain", "plain-palette", "mode", "mode-palette"],
)
def test_the_normal_and_depth_never_change_the_reduced_colour(reduce, palette):
    def frames(with_surfaces):
        for i in range(3):
            rng = np.random.default_rng(i)
            named = {
                IDENTITY: rng.integers(-1, 2, (8, 8), dtype=np.int32),
                SHADE: rng.integers(0, 256, (8, 8), dtype=np.uint8),
            }
            if with_surfaces:
                named[NORMAL], named[DEPTH] = surfaces(i)
            yield ImageFrame(address(i), colour(i), buffers=named)

    options = {"identities": IDENTITIES, "pixels_per_meter": 40.0}
    if palette is not None:
        options["palette"] = palette
    plain = list(reduce(frames(False), 2, **options))
    lit = list(reduce(frames(True), 2, **options))
    # Without normal and depth, a reduced frame carries no maps; with them,
    # only its maps (see test_normal_depth_maps).
    assert all(frame.buffers == {} for frame in plain)
    assert all(set(frame.buffers) == {NORMAL_MAP, DEPTH_MAP} for frame in lit)
    for a, b in zip(plain, lit, strict=True):
        np.testing.assert_array_equal(a.pixels, b.pixels)


def test_the_command_decodes_each_frame_s_normal_and_depth_for_stylize(
    setup, capsys, monkeypatch
):
    seen = []
    real_plain = stylize.plain

    def recording_plain(frames, factor, **kwargs):
        def watched():
            for frame in frames:
                seen.append({n: frame.buffers[n].copy() for n in (NORMAL, DEPTH)})
                yield frame
                del frame

        return real_plain(watched(), factor, **kwargs)

    monkeypatch.setattr(stylize, "plain", recording_plain)
    setup.configure(surfaces="varied")
    work = setup.tmp_path / "work"
    assert run(capsys, setup.argv("--work-dir", str(work))) == (0, "", "")
    assert len(seen) == (4 + 3) * 8
    for i, named in enumerate(seen):
        normal, depth = named[NORMAL], named[DEPTH]
        assert normal.dtype == np.float32 and normal.shape == (16, 16, 3)
        assert depth.dtype == np.float32 and depth.shape == (16, 16)
        # What the fake wrote: its own generator, frame by frame.
        rng = np.random.default_rng(2000 + i)
        expected = rng.normal(size=(16, 16, 3))
        expected /= np.linalg.norm(expected, axis=-1, keepdims=True)
        expected_depth = rng.uniform(-5000.0, 5000.0, size=(16, 16))
        np.testing.assert_allclose(normal, expected, atol=1.6e-5)
        np.testing.assert_array_equal(depth, expected_depth.astype(np.float32))


# Requirement 8: whole-command outputs do not depend on the normal and depth.


def outputs(setup, capsys, argv, surfaces):
    setup.configure(pixels="noise", surfaces=surfaces)
    status, _, err = run(capsys, argv)
    assert status == 0, err
    return setup.listing()


@pytest.mark.parametrize(("reduce", "paletted"), OPTIONS)
def test_the_normal_and_depth_change_no_output(setup, capsys, reduce, paletted):
    # Only the normal map, which they make, depends on them.
    argv = speckled_argv(setup, *look_argv(setup, reduce, paletted))
    flat = outputs(setup, capsys, argv, "flat")
    varied = outputs(setup, capsys, argv, "varied")
    assert flat.pop("hero.normal.png") != varied.pop("hero.normal.png")
    assert varied == flat
    assert sorted(flat) == ["hero.attack.gif", "hero.json", "hero.png", "hero.walk.gif"]


@pytest.mark.parametrize("reduce", ["plain", "mode"])
def test_the_normal_and_depth_change_no_output_with_a_library(setup, capsys, reduce):
    named_hero(setup, HERO_MATERIALS)
    argv = materialed(setup, "--reduce", reduce)

    def run_with(surfaces):
        setup.configure(
            materials=[{"id": k + 1, "material": k} for k in range(4)]
            + [{"id": 65535, "material": None}],
            code=1,
            pixels="solid",
            surfaces=surfaces,
        )
        status, _, err = run(capsys, argv)
        assert status == 0, err
        return setup.listing()

    flat, varied = run_with("flat"), run_with("varied")
    assert flat.pop("hero.normal.png") != varied.pop("hero.normal.png")
    assert varied == flat
