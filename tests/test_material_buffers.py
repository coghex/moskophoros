"""The material-ID and shade buffers: result validation, the material table,
decoding into the Frames into stylize interface, and the command's use of
them (design §Capture job and result contract, §Frames into stylize)."""

import json

import numpy as np
import pytest
from glb_writer import GlbWriter
from PIL import Image
from test_capture_backend import encode, render_document, render_job
from test_command import EARLIER, Setup, earlier_outputs, run, speckled_argv

from moskophoros import gltf, stylize
from moskophoros.capture import backend
from moskophoros.capture.backend import BackendError, validate_result
from moskophoros.gltf import PrimitiveMaterial
from moskophoros.sampling import BACKGROUND, IDENTITY, SHADE, Identities


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


def paint(name, pixels):
    """A change writing frame 0's `name` buffer from an (6, 8, 4) array, or a
    callable editing the valid one."""

    def change(document, tmp_path):
        path = tmp_path / f"{name}/000000.png"
        current = np.asarray(Image.open(path)).copy()
        values = pixels(current) if callable(pixels) else pixels
        Image.fromarray(np.asarray(values, dtype=np.uint8), "RGBA").save(path)

    return change


def corner(value):
    """Set pixel (0, 0) to `value`, keeping the rest."""

    def edit(pixels):
        pixels[0, 0] = value
        return pixels

    return edit


def both(*changes):
    def change(document, tmp_path):
        for each in changes:
            each(document, tmp_path)

    return change


# Requirement 8: the launcher rejects bad buffers and tables (exit 5).


@pytest.mark.parametrize(
    ("change", "message"),
    [
        # An ID pixel that is not exactly an encoded value.
        (paint("matid", corner((0, 1, 0, 128))), "not an encoded value"),
        (paint("matid", corner((0, 1, 0, 0))), "not an encoded value"),
        (paint("matid", corner((0, 1, 7, 255))), "not an encoded value"),
        (paint("matid", corner((0, 0, 0, 255))), "not an encoded value"),
        # A non-background ID missing from the table.
        (paint("matid", corner((0, 2, 0, 255))), "code 2 is not in the table"),
        # Shade pixels whose channels differ, or whose alpha is partial.
        (paint("shade", corner((137, 136, 137, 255))), "red, green and blue differ"),
        (paint("shade", corner((137, 137, 138, 255))), "red, green and blue differ"),
        (paint("shade", corner((137, 137, 137, 254))), "neither 0 nor 255"),
        # The two disagree: a surface with no shade sample ...
        (paint("shade", corner((0, 0, 0, 0))), "but the material-ID pixel"),
        # ... or background with a shade.
        (
            both(
                paint("matid", corner((0, 0, 0, 0))),
                paint("shade", corner((137, 137, 137, 255))),
            ),
            "but the material-ID pixel",
        ),
        (
            both(
                paint("matid", corner((0, 0, 0, 0))),
                paint("shade", corner((0, 0, 0, 255))),
            ),
            "but the material-ID pixel",
        ),
    ],
)
def test_bad_material_id_and_shade_pixels_are_backend_errors(tmp_path, change, message):
    with pytest.raises(BackendError, match=message) as raised:
        rendered(tmp_path, change)
    assert raised.value.exit_code == 5
    assert "frame 0" in str(raised.value)


def test_background_with_no_shade_is_valid(tmp_path):
    result = rendered(
        tmp_path,
        both(
            paint("matid", corner((0, 0, 0, 0))),
            paint("shade", corner((0, 0, 0, 0))),
        ),
    )
    assert result.materials == {1: 0, 65535: None}


def _table(entries):
    def change(document, tmp_path):
        document["materials"] = entries

    return change


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ([{"id": 0, "material": 0}], "maps the background code 0"),
        ([{"id": 1, "material": 0}, {"id": 1, "material": 1}], "repeats code 1"),
        ([{"id": 65536, "material": 0}], "not a material-ID code"),
        ([{"id": -1, "material": 0}], "not a material-ID code"),
        ([{"id": True, "material": 0}], "not a material-ID code"),
        ([{"id": 1, "material": -1}], "not a material index"),
        ([{"id": 1, "material": "0"}], "not a material index"),
        ([{"id": 1}], "missing material"),
        ([{"id": 1, "material": 0, "name": "steel"}], "unknown name"),
        ({"1": 0}, "materials is not a list"),
    ],
)
def test_a_malformed_material_table_is_a_backend_error(tmp_path, entries, message):
    with pytest.raises(BackendError, match=message):
        rendered(tmp_path, _table(entries))


def _drop(*path):
    def change(document, tmp_path):
        target = document
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_drop("materials"), "missing materials"),
        (_drop("frames", 0, "buffers", "matid"), "frame 0 has no matid buffer"),
        (_drop("frames", 2, "buffers", "shade"), "frame 2 has no shade buffer"),
        (_drop("backend", "shade"), "backend is missing shade"),
        (_drop("backend", "shade", "seed"), "backend.shade is missing seed"),
    ],
)
def test_render_results_need_the_buffers_table_and_shade_provenance(
    tmp_path, change, message
):
    with pytest.raises(BackendError, match=message):
        rendered(tmp_path, change)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("technique", ""),
        ("technique", 3),
        ("samples_per_pixel", 0),
        ("seed", -1),
        ("seed", 1.5),
        ("filter_width_px", 0),
        ("ao_distance_m", float("inf")),
        ("ao_samples", True),
        ("occlusion_weight", "0.25"),
    ],
)
def test_malformed_shade_provenance_is_a_backend_error(tmp_path, key, value):
    def change(document, tmp_path):
        document["backend"]["shade"][key] = value

    job = render_job(str(tmp_path))
    document = render_document(job, tmp_path)
    change(document, tmp_path)
    text = json.dumps(document, allow_nan=True).encode()
    with pytest.raises(BackendError, match="backend.shade|non-finite"):
        validate_result(job, tmp_path, text)


def test_a_misnamed_auxiliary_buffer_is_a_backend_error(tmp_path):
    def change(document, tmp_path):
        (tmp_path / "matid/000000.png").rename(tmp_path / "matid/other.png")
        document["frames"][0]["buffers"]["matid"] = "matid/other.png"

    with pytest.raises(BackendError, match="matid buffer is 'matid/other.png'"):
        rendered(tmp_path, change)


def test_a_measure_result_keeps_its_contract(tmp_path):
    from test_capture_backend import measure_document, measure_job

    job = measure_job(str(tmp_path))
    result = validate_result(job, tmp_path, encode(measure_document(job)))
    assert result.materials is None and "shade" not in result.backend


# The identity list, the table join and decoding.


def record(material, name, alpha="OPAQUE", primitive=0):
    return PrimitiveMaterial(0, 0, primitive, material, name, alpha)


def test_the_identity_list_follows_lowest_material_index_and_eligibility():
    records = (
        record(4, "cloth"),
        record(1, "steel"),
        record(None, None),  # a primitive without a material
        record(3, "steel"),  # a duplicate name pools into one identity
        record(5, "glass", "BLEND"),
        record(6, None),  # an unnamed material
        record(2, "leaf", "MASK"),
        record(7, "steel", "BLEND"),  # BLEND, though its name is eligible
        record(8, "odd", "SOMETHING"),
        record(1, "steel", primitive=1),
    )
    listed, indices = backend.identities(records)
    assert listed == Identities(("steel", "leaf", "cloth"))
    assert indices == {1: 0, 2: 1, 3: 0, 4: 2, 5: 3, 6: 3, 7: 3, 8: 3}
    assert listed.no_identity == 3


def subject(records, count):
    return gltf.Subject(None, "s", 0, (), tuple(records), count)


def result_with(materials):
    return backend.CaptureResult("render", {}, None, None, {}, materials)


def test_the_table_joins_codes_to_identities():
    records = (record(0, "steel"), record(1, "cloth"), record(2, "steel"))
    records += (record(3, "glass", "BLEND"), record(None, None))
    table = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 65535: None}
    lookup = backend.material_lookup(result_with(table), subject(records, 5))
    assert lookup.identities == Identities(("steel", "cloth"))
    codes = lookup.codes
    assert codes.dtype == np.int32 and codes.shape == (65536,)
    assert codes[0] == BACKGROUND
    # Material 4 is in the model but no primitive of the subject uses it.
    assert [int(codes[c]) for c in (1, 2, 3, 4, 5, 65535)] == [0, 1, 0, 2, 2, 2]
    assert codes[6] == backend.UNKNOWN_CODE


def test_a_table_entry_that_is_not_a_material_of_the_model_is_a_backend_error():
    with pytest.raises(BackendError, match="maps material 3, but the model has 3"):
        backend.material_lookup(result_with({4: 3}), subject((), 3))


def write(path, pixels):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(pixels, dtype=np.uint8), "RGBA").save(path)
    return path


def test_decoding_gives_int32_identities_and_uint8_shade(tmp_path):
    records = (record(0, "steel"), record(299, "cloth"), record(None, None))
    table = {1: 0, 300: 299, 65535: None}
    lookup = backend.material_lookup(result_with(table), subject(records, 300))
    ids = np.zeros((2, 3, 4), dtype=np.uint8)
    ids[0, 0] = (0, 1, 0, 255)
    ids[0, 1] = (1, 44, 0, 255)  # 300: a carry into the high byte
    ids[0, 2] = (255, 255, 0, 255)  # the largest code, "no material"
    shade = np.zeros((2, 3, 4), dtype=np.uint8)
    shade[0] = (90, 90, 90, 255)
    paths = {
        "matid": write(tmp_path / "m.png", ids),
        "shade": write(tmp_path / "s.png", shade),
    }
    identity, shading = backend.decode_frame(paths, lookup)
    assert identity.dtype == np.int32 and shading.dtype == np.uint8
    assert identity.tolist() == [[0, 1, 2], [BACKGROUND] * 3]
    assert shading.tolist() == [[90, 90, 90], [0, 0, 0]]


def test_decoding_refuses_a_code_outside_the_table(tmp_path):
    lookup = backend.material_lookup(result_with({1: 0}), subject((record(0, "a"),), 1))
    ids = np.zeros((1, 1, 4), dtype=np.uint8)
    ids[0, 0] = (0, 9, 0, 255)
    paths = {
        "matid": write(tmp_path / "m.png", ids),
        "shade": write(tmp_path / "s.png", np.full((1, 1, 4), 255, dtype=np.uint8)),
    }
    with pytest.raises(BackendError, match="not in the material table"):
        backend.decode_frame(paths, lookup)


# The command


def many_materials(directory, count):
    model = GlbWriter()
    node = model.node(mesh=True)
    model.scene([node], default=True)
    model.document["materials"] = [{} for _ in range(count)]
    return model.write(directory, "many")


@pytest.mark.parametrize(
    ("count", "status"), [(backend.MAX_MATERIALS, 5), (backend.MAX_MATERIALS + 1, 3)]
)
def test_too_many_materials_is_an_input_error_before_blender(
    setup, capsys, count, status
):
    # 65534 materials take codes 1–65534, beside "no material" (65535) and
    # background (0); one more cannot be encoded. Below the limit the run
    # reaches Blender, here missing, which is a backend error instead.
    model = many_materials(setup.tmp_path / "model", count)
    blender = setup.tmp_path / "no-blender"
    argv = ["--blender", str(blender), str(model), str(setup.out / "many.png")]
    assert backend.MAX_MATERIALS == 65534
    code, _, err = run(capsys, argv)
    assert code == status
    if status == 3:
        assert f"has {count} materials; the material-ID buffer holds at most" in err
        assert str(model) in err
    else:
        assert "no-blender" in err
    assert setup.calls() == []


def test_the_capacity_check_precedes_the_version_probe(setup, capsys):
    model = many_materials(setup.tmp_path / "model", backend.MAX_MATERIALS + 1)
    probe = setup.tmp_path / "probed"
    fake = setup.tmp_path / "probe-blender"
    fake.write_text(f"#!/bin/sh\ntouch {probe}\necho 'Blender 5.2.2 LTS'\n")
    fake.chmod(0o755)
    argv = ["--blender", str(fake), str(model), str(setup.out / "many.png")]
    assert run(capsys, argv)[0] == 3
    assert not probe.exists()


def test_stylize_receives_decoded_identity_and_shade_arrays(setup, capsys, monkeypatch):
    seen = []
    real_plain = stylize.plain

    def recording_plain(frames, factor, **kwargs):
        def watched():
            for frame in frames:
                seen.append(
                    {name: frame.buffers[name].copy() for name in (IDENTITY, SHADE)}
                )
                yield frame

        seen.append(kwargs["identities"])
        return real_plain(watched(), factor, **kwargs)

    monkeypatch.setattr(stylize, "plain", recording_plain)
    assert run(capsys, setup.argv()) == (0, "", "")
    identities, first = seen[0], seen[1]
    # The model's primitives have no material: every code is "no material".
    assert identities == Identities(())
    assert first[IDENTITY].dtype == np.int32 and first[SHADE].dtype == np.uint8
    assert first[IDENTITY].shape == first[SHADE].shape == (16, 16)
    assert (first[IDENTITY] == identities.no_identity).all()
    assert (first[SHADE] == 137).all()
    assert len(seen) == 1 + (4 + 3) * 8


@pytest.mark.parametrize(
    "config",
    [
        {"bad_aux": 3},
        {"code": 1, "materials": [{"id": 1, "material": 0}]},
        {"materials": [{"id": 0, "material": None}]},
    ],
    ids=["shade-disagrees", "not-a-material-of-the-model", "maps-background"],
)
def test_invalid_auxiliary_data_leaves_earlier_outputs_untouched(setup, capsys, config):
    earlier = earlier_outputs(setup, *EARLIER)
    setup.configure(**config)
    status, _, err = run(capsys, setup.argv())
    assert status == 5
    assert err.startswith("moskophoros: error: the render result is invalid")
    assert setup.listing() == earlier


@pytest.mark.parametrize("reduce", ["plain", "mode"])
@pytest.mark.parametrize("paletted", [False, True])
def test_without_a_library_the_auxiliary_buffers_change_no_output(
    setup, capsys, reduce, paletted
):
    options = ["--reduce", reduce]
    if paletted:
        path = setup.tmp_path / "test.hex"
        path.write_text("000000\nff0000\nffffff\n")
        options += ["--palette", str(path)]
    argv = speckled_argv(setup, *options)
    setup.configure(pixels="noise")
    status = run(capsys, argv)
    assert status[0] == 0
    before = setup.listing()
    # Another material everywhere: without a library nothing maps it.
    setup.configure(pixels="noise", code=1, materials=[{"id": 1, "material": None}])
    assert run(capsys, argv) == status
    assert setup.listing() == before


def test_the_script_and_the_launcher_agree_on_the_encoding_and_shade_fields():
    # blender_script.py runs inside Blender and cannot import the launcher, so
    # the constants they share are read from its source here.
    import ast
    from pathlib import Path

    from moskophoros.capture import blender as launcher

    tree = ast.parse(Path(launcher.SCRIPT).read_text())
    script = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                script[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    assert script["ID_BACKGROUND"] == backend.ID_BACKGROUND
    assert script["NO_MATERIAL_ID"] == backend.NO_MATERIAL_ID
    assert list(script["SHADE"]) == list(backend.SHADE_FIELDS)
