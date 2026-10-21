"""The back and front layer normals (shading design D-37; design §Capture job
and result contract, §Frames into stylize): the transported `back_normal`
buffer's validation, its decoding, and the front normal derived from the
front-most normal and the front layer's presence."""

import math

import numpy as np
import pytest
from capture_buffers import normal_samples, write_depth, write_front, write_normal
from test_capture_backend import (
    FRONT_PIXEL,
    _clear,
    encode,
    render_document,
    render_job,
)
from test_command import Setup, run
from test_normal_depth_buffers import (
    COVERED,
    SIZE,
    SURFACE,
    UNIT,
    ZERO,
    _corrupt,
    _drop,
    _eight_bit,
    _filtered,
    _greyscale16,
    _moved,
    _not_png,
    _with_text,
    _wrong_size,
    at_corner,
    both,
    file,
    matid_background_corner,
    quantised,
    rendered,
    samples,
)

from moskophoros import sampling, stylize
from moskophoros.capture import backend
from moskophoros.capture.backend import BackendError
from moskophoros.sampling import BACK_NORMAL, FRONT_NORMAL, FRONT_PRESENT, NORMAL

HALF = quantised(0.0), quantised(0.0), quantised(0.5)


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def front_most_without_the_corner(document, tmp_path):
    """Frame 0's normal and depth buffers with pixel (0, 0) no surface."""
    covered = COVERED.copy()
    covered[0, 0] = False
    write_normal(tmp_path / "normal/000000.png", covered)
    write_depth(tmp_path / "depth/000000.png", covered, 0.5)


# The launcher rejects a bad back normal (exit 5).


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_drop("back_normal"), "frame 0 has no back_normal buffer"),
        (_moved("back_normal"), "back_normal buffer is 'back_normal/other.png', not"),
        (file("back_normal", _eight_bit), "is not 16-bit RGBA \\(bit depth 8"),
        (file("back_normal", _greyscale16), "is not 16-bit RGBA \\(bit depth 16"),
        (file("back_normal", _wrong_size), "is 7x6, not 8x6"),
        (file("back_normal", _filtered), "filters row 1"),
        (file("back_normal", _with_text), "not IHDR, IDAT and IEND only"),
        (file("back_normal", _corrupt), "corrupt"),
        (file("back_normal", _not_png), "is not a PNG"),
    ],
)
def test_a_missing_misplaced_or_misencoded_back_normal_is_a_backend_error(
    tmp_path, change, message
):
    with pytest.raises(BackendError, match=message) as raised:
        rendered(tmp_path, change)
    assert raised.value.exit_code == 5
    assert "frame 0" in str(raised.value)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        # A normal that is not unit length, or none at all, on a surface.
        (samples("back_normal", at_corner((*HALF, SURFACE))), "not a unit normal"),
        (samples("back_normal", at_corner((*ZERO, SURFACE))), "not a unit normal"),
        (samples("back_normal", at_corner((0, 0, 0, SURFACE))), "not a unit normal"),
        # Partial alpha, and background holding a value.
        (samples("back_normal", at_corner((*UNIT, 1000))), "not an encoded value"),
        (samples("back_normal", at_corner((*UNIT, 0))), "not an encoded value"),
        # No surface where the back colour has one ...
        (
            samples("back_normal", at_corner((0, 0, 0, 0))),
            "back_normal pixel \\(0, 0\\) is .*, no surface, but the back layer "
            "shows one",
        ),
        # ... and a surface where it has none, the front-most buffers agreeing
        # with the colour.
        (
            both(matid_background_corner, front_most_without_the_corner),
            "back_normal pixel \\(0, 0\\) is .*, a surface, but the back layer "
            "shows none",
        ),
    ],
)
def test_bad_back_normal_pixels_are_backend_errors(tmp_path, change, message):
    with pytest.raises(BackendError, match=message) as raised:
        rendered(tmp_path, change)
    assert raised.value.exit_code == 5
    assert "frame 0" in str(raised.value)


def test_a_back_normal_facing_away_from_the_viewer_is_accepted(tmp_path):
    normal = np.zeros((*SIZE, 3))
    normal[...] = (0.0, 0.6, 0.8)
    normal[0, 0] = (0.0, math.sqrt(1 - 0.31**2), -0.31)
    normal[0, 1] = (0.0, 0.0, -1.0)

    def change(document, tmp_path):
        write_normal(tmp_path / "back_normal/000000.png", COVERED, normal)

    rendered(tmp_path, change)


def test_a_front_alone_has_no_back_normal(tmp_path):
    # A front layer where its back is cleared: the front-most buffers cover the
    # pixel, so the back normal must not.
    phase_dir = tmp_path / "render"
    job = render_job(str(phase_dir))
    document = render_document(job, phase_dir)
    _clear(phase_dir, 5, (3, 2))
    write_front(phase_dir, 5, (8, 6), FRONT_PIXEL, (10, 20, 30), 0)
    write_normal(phase_dir / "normal/000005.png", COVERED)
    write_depth(phase_dir / "depth/000005.png", COVERED, 0.5)
    backend.validate_result(job, phase_dir, encode(document))
    write_normal(phase_dir / "back_normal/000005.png", COVERED)
    with pytest.raises(
        BackendError, match="frame 5: back_normal pixel \\(3, 2\\)"
    ) as e:
        backend.validate_result(job, phase_dir, encode(document))
    assert e.value.exit_code == 5


def test_the_front_most_normal_checks_still_apply(tmp_path):
    # Either layer's surface still needs the front-most normal.
    with pytest.raises(BackendError, match="normal pixel \\(0, 0\\) is .*, no surface"):
        rendered(tmp_path, samples("normal", at_corner((0, 0, 0, 0))))


# Decoding and deriving


def test_the_back_normal_decodes_like_the_normal_with_its_background(tmp_path):
    covered = COVERED.copy()
    covered[0, 0] = False
    normal = np.zeros((*SIZE, 3))
    normal[...] = (0.6, 0.0, -0.8)

    def change(document, tmp_path):
        matid_background_corner(document, tmp_path)
        front_most_without_the_corner(document, tmp_path)
        write_normal(tmp_path / "back_normal/000000.png", covered, normal)

    result = rendered(tmp_path, change)
    paths = next(iter(result.buffers.values()))
    decoded = backend.decode_back_normal(paths)
    assert decoded.dtype == np.float32 and decoded.shape == (*SIZE, 3)
    np.testing.assert_allclose(decoded[covered], normal[covered], atol=1.6e-5)
    assert (decoded[~covered] == 0).all()
    expected = backend.decode_normal(backend.read_wide_png(paths["back_normal"]))
    np.testing.assert_array_equal(decoded, expected)


def test_a_back_normal_changed_after_validation_is_a_backend_error(tmp_path):
    result = rendered(tmp_path)
    paths = next(iter(result.buffers.values()))
    paths["back_normal"].write_bytes(b"truncated")
    with pytest.raises(BackendError, match="back_normal/000000.png is not a PNG"):
        backend.decode_back_normal(paths)


def test_the_front_normal_is_the_front_most_normal_where_the_front_is_present():
    rng = np.random.default_rng(5)
    normals = rng.normal(size=(3, 4, 3))
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    covered = np.ones((3, 4), dtype=bool)
    covered[0, 0] = False
    normal = backend.decode_normal(normal_samples(normals, covered))
    present = np.zeros((3, 4), dtype=bool)
    present[1, 1] = present[2, 3] = True
    before = normal.copy()
    front = backend.derive_front_normal(
        {"normal": "normal/000007.png"}, normal, present
    )
    assert front.dtype == np.float32 and front.shape == (3, 4, 3)
    np.testing.assert_array_equal(front[present], normal[present])
    assert (front[~present] == 0).all()
    # A new array, and the front-most normal untouched.
    assert not np.shares_memory(front, normal)
    np.testing.assert_array_equal(normal, before)
    front[present] = 0
    np.testing.assert_array_equal(normal, before)


def test_a_present_front_keeps_its_normal_whatever_its_opacity(tmp_path):
    # Presence comes from the front colour, never the quantised alpha q: a
    # front present at q = 0 still has the front-most normal.
    phase_dir = tmp_path / "render"
    job = render_job(str(phase_dir))
    document = render_document(job, phase_dir)
    write_front(phase_dir, 4, (8, 6), FRONT_PIXEL, (10, 20, 30), 0)
    result = backend.validate_result(job, phase_dir, encode(document))
    paths = list(result.buffers.values())[4]
    codes = np.full(backend.NO_MATERIAL_ID + 1, 0, dtype=np.int32)
    lookup = backend.MaterialLookup(sampling.Identities(()), codes)
    _, alpha, present, _, _ = backend.decode_front(paths, lookup)
    assert alpha[2, 3] == 0 and present[2, 3] and present.sum() == 1
    normal, _ = backend.decode_normal_depth(paths)
    front = backend.derive_front_normal(paths, normal, present)
    np.testing.assert_array_equal(front[2, 3], normal[2, 3])
    assert (front[2, 3] != 0).any()
    assert (front[~present] == 0).all()


def test_a_present_front_over_no_normal_is_a_backend_error():
    normal = np.zeros((2, 2, 3), dtype=np.float32)
    normal[..., 2] = 1.0
    normal[1, 0] = 0.0
    present = np.zeros((2, 2), dtype=bool)
    present[1, 0] = True
    paths = {"normal": "normal/000003.png"}
    with pytest.raises(
        BackendError,
        match="normal/000003.png pixel \\(0, 1\\) is .*not a unit normal, but the "
        "front layer is present there",
    ) as raised:
        backend.derive_front_normal(paths, normal, present)
    assert raised.value.exit_code == 5
    # Where the front is absent, no normal is nothing to refuse.
    assert (backend.derive_front_normal(paths, normal, ~present)[1, 0] == 0).all()


def test_a_normal_and_front_of_different_sizes_are_a_backend_error():
    with pytest.raises(BackendError, match="has shape \\(2, 2\\), but the front"):
        backend.derive_front_normal(
            {"normal": "normal/000003.png"},
            np.zeros((2, 2, 3), np.float32),
            np.zeros((2, 3), bool),
        )


# Through the command


@pytest.mark.parametrize(
    "front",
    [None, {"colour": [10, 20, 30], "q": 0}, {"colour": [10, 20, 30], "q": 26214}],
    ids=["no-front", "zero-opacity-front", "translucent-front"],
)
def test_both_layer_normals_reach_stylize_as_addressed_arrays(
    setup, capsys, monkeypatch, front
):
    seen = []
    real_plain = stylize.plain

    def recording_plain(frames, factor, **kwargs):
        def watched():
            for frame in frames:
                buffers = frame.buffers
                # New arrays, not views of the exported-map source.
                for name in (BACK_NORMAL, FRONT_NORMAL):
                    assert not np.shares_memory(buffers[name], buffers[NORMAL])
                seen.append({name: array.copy() for name, array in buffers.items()})
                yield frame

        return real_plain(watched(), factor, **kwargs)

    monkeypatch.setattr(stylize, "plain", recording_plain)
    setup.configure(surfaces="varied", front=front)
    work = setup.tmp_path / "work"
    assert run(capsys, setup.argv("--work-dir", str(work))) == (0, "", "")
    assert len(seen) == (4 + 3) * 8
    for i, named in enumerate(seen):
        render = work / "render"
        back = backend.read_wide_png(render / "back_normal" / f"{i:06d}.png")
        normal = backend.read_wide_png(render / "normal" / f"{i:06d}.png")
        assert named[BACK_NORMAL].dtype == named[FRONT_NORMAL].dtype == np.float32
        assert named[BACK_NORMAL].shape == named[FRONT_NORMAL].shape == (16, 16, 3)
        np.testing.assert_array_equal(named[BACK_NORMAL], backend.decode_normal(back))
        np.testing.assert_array_equal(named[NORMAL], backend.decode_normal(normal))
        present = named[FRONT_PRESENT]
        if front is None:
            assert not present.any()
            assert (named[FRONT_NORMAL] == 0).all()
            continue
        # The fake's front covers every surface, even at q = 0, and its back
        # normals face away from the front-most ones.
        covered = normal[..., 3] == SURFACE
        assert covered.any() and np.array_equal(present, covered)
        np.testing.assert_array_equal(
            named[FRONT_NORMAL][present], named[NORMAL][present]
        )
        assert (named[FRONT_NORMAL][~present] == 0).all()
        np.testing.assert_allclose(
            named[BACK_NORMAL][covered], -named[NORMAL][covered], atol=1e-5
        )
