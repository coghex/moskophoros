"""`--materials` and `--no-materials`: choosing, recording and reusing a
material library (design §CLI, §Option validation, §Export and §Scale and
ground point, Reuse), with a controlled fake Blender."""

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from glb_writer import GlbWriter
from PIL import Image
from test_command import PLAIN_STYLE, Setup, run
from test_reuse import edited, write_legacy_sheet, write_previous_sheet, write_sheet

from moskophoros import cli, materials, stylize
from moskophoros.capture import backend
from moskophoros.gltf import PrimitiveMaterial

# Eight colours, so every ramp index below is valid.
COLORS = tuple((index * 30, 255 - index * 30, index * 7) for index in range(8))
HEX = "".join(bytes(color).hex() + "\n" for color in COLORS)
LIBRARY = {
    "schema": materials.SCHEMA,
    "ramps": {"metal": [1, 2, 3], "cloth": [4, 5]},
    "materials": {
        "steel": {"uses": "metal"},
        "glass": {"ramp": [6]},
        "ghost": {"ramp": [7, 0]},
    },
}
DEFAULT_RANGE = list(backend.DEFAULT_SHADE_RANGE)


@pytest.fixture
def setup(tmp_path):
    return Setup(tmp_path)


def palette_file(directory, colors=COLORS, name="palette.hex"):
    path = Path(directory) / name
    path.write_text("".join(bytes(color).hex() + "\n" for color in colors))
    return path


def library_file(directory, document=None, name="materials.json"):
    path = Path(directory) / name
    path.write_text(json.dumps(LIBRARY if document is None else document))
    return path


def named_hero(setup, definitions):
    """Replace the setup's model with `hero.glb` whose two nodes share one mesh
    holding a primitive for each of `definitions` (glTF material dictionaries)
    and one with no material; `walk` and `attack` as in the default model."""
    setup.model.unlink()
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
    model.document["materials"] = copy.deepcopy(definitions)
    mesh = model.document["meshes"][0]
    primitive = mesh["primitives"][0]
    mesh["primitives"] = [
        {**primitive, "material": index} for index in range(len(definitions))
    ] + [primitive]
    setup.model = model.write(setup.model.parent, "hero")
    # The fake renders material k as the ID code k + 1.
    setup.configure(
        materials=[{"id": k + 1, "material": k} for k in range(len(definitions))]
        + [{"id": 65535, "material": None}],
        code=1,
    )


HERO_MATERIALS = [
    {"name": "steel"},
    {"name": "cloth"},
    {"name": "glass", "alphaMode": "BLEND"},
    {"name": ""},
]


def sheet_colours(path):
    with Image.open(path) as image:
        pixels = np.array(image)
    return {tuple(int(v) for v in pixel) for pixel in pixels.reshape(-1, 4)}


def opaque(index):
    return (*COLORS[index], 255)


CLEAR = (0, 0, 0, 0)


def materialed(setup, *options, library=None):
    """The argv of a run with the eight-colour palette and a library file."""
    return setup.argv(
        "--palette",
        str(palette_file(setup.tmp_path)),
        "--materials",
        str(library_file(setup.tmp_path, library)),
        *options,
    )


def forbid_blender(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("a process ran before a usage error")

    monkeypatch.setattr(subprocess, "Popen", forbidden)


# The options


@pytest.mark.parametrize(
    "args",
    [
        ("--materials", "a.json", "--materials", "b.json"),
        ("--no-materials", "--no-materials"),
        ("--materials", "a.json", "--no-materials"),
        ("--no-materials", "--materials", "a.json"),
    ],
)
def test_materials_option_conflicts_and_repeats_are_usage_errors(args, capsys):
    with pytest.raises(cli.UsageError):
        cli.parse_args([*args, "model.glb", "out.png"])
    assert "moskophoros: error:" in capsys.readouterr().err


def test_materials_parsing_reads_no_files(tmp_path):
    path = tmp_path / "absent.json"
    options = cli.parse_args(["--materials", str(path), "model.glb", "out.png"])
    assert options.materials_file == path
    assert options.explicit == {"materials"}
    assert options.materials is None
    dropped = cli.parse_args(["--no-materials", "model.glb", "out.png"])
    assert dropped.no_materials and dropped.explicit == {"no_materials"}
    assert dropped.shade_range == backend.DEFAULT_SHADE_RANGE


def test_help_lists_the_options(capsys):
    status, out, _ = run(capsys, ["--help"])
    assert status == 0
    assert "--materials FILE" in out and "--no-materials" in out


# Errors, before any Blender invocation


def library_with(**changes):
    return json.loads(json.dumps(LIBRARY)) | changes


@pytest.mark.parametrize(
    ("kind", "mention"),
    [
        ("absent", "absent.json"),
        ("not-json", "materials.json"),
        ("bad-schema", "schema"),
        ("outside-palette", 'materials["glass"].ramp[0]'),
        ("unknown-ramp", 'materials["steel"].uses'),
        ("unknown-field", "unknown field"),
        ("empty-ramp", 'ramps["metal"]'),
        ("repeated-key", "repeats the key"),
        ("bad-default", "default"),
    ],
)
def test_every_library_error_is_exit_2_before_blender_and_names_file_and_entry(
    setup, capsys, monkeypatch, kind, mention
):
    path = setup.tmp_path / "materials.json"
    document = library_with()
    if kind == "absent":
        path = setup.tmp_path / "absent.json"
    elif kind == "not-json":
        path.write_text("{")
    elif kind == "repeated-key":
        path.write_text('{"schema": "x", "schema": "x"}')
    else:
        if kind == "bad-schema":
            document["schema"] = "moskophoros.materials/0"
        elif kind == "outside-palette":
            document["materials"]["glass"] = {"ramp": [8]}
        elif kind == "unknown-ramp":
            document["materials"]["steel"] = {"uses": "nope"}
        elif kind == "unknown-field":
            document["extra"] = 1
        elif kind == "empty-ramp":
            document["ramps"]["metal"] = []
        elif kind == "bad-default":
            document["default"] = "nope"
        path.write_text(json.dumps(document))
    forbid_blender(monkeypatch)
    argv = setup.argv(
        "--palette", str(palette_file(setup.tmp_path)), "--materials", str(path)
    )
    status, _, err = run(capsys, argv)
    assert status == 2
    assert f"--materials {path}" in err or str(path) in err
    assert mention in err
    assert setup.calls() == []
    assert not setup.png.exists()


def test_a_library_without_a_palette_is_exit_2_before_blender(
    setup, capsys, monkeypatch
):
    path = library_file(setup.tmp_path)
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--materials", str(path)))
    assert status == 2
    assert str(path) in err and "needs a palette" in err
    assert setup.calls() == []


def test_a_library_with_no_palette_after_reuse_is_exit_2(setup, capsys, tmp_path):
    sheet = write_sheet(tmp_path, edited({"style.palette": None}))
    path = library_file(setup.tmp_path)
    status, _, err = run(
        capsys, setup.argv("--settings-from", str(sheet), "--materials", str(path))
    )
    assert status == 2 and "needs a palette" in err
    assert setup.calls() == []


def test_the_library_is_read_once_and_parsed_and_hashed_as_the_same_bytes(
    setup, capsys, monkeypatch
):
    path = library_file(setup.tmp_path)
    reads = []
    real = Path.read_bytes

    def read_bytes(self):
        if self == path:
            reads.append(self)
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    options = cli.resolve_settings(
        cli.parse_args(
            [
                "--palette",
                str(palette_file(setup.tmp_path)),
                "--materials",
                str(path),
                "model.glb",
                "out.png",
            ]
        )
    )
    assert reads == [path]
    assert options.materials.sha256 == hashlib.sha256(real(path)).hexdigest()
    assert options.materials.source == "materials.json"


# Recording


def run_with_library(setup, capsys, *options, library=None):
    status, _, err = run(capsys, materialed(setup, *options, library=library))
    assert status == 0, err
    return err


def test_a_run_records_the_library_inline_and_the_shade_range(setup, capsys):
    setup.configure(code=1, pixels="solid")
    named_hero(setup, HERO_MATERIALS)
    run_with_library(setup, capsys, "--no-preview")
    description = json.loads(setup.json.read_text())
    assert description["schema"] == "moskophoros.sheet/3"
    style = description["settings"]["style"]
    assert list(style) == ["reduce", "palette", "materials", "shade_range"]
    assert style["shade_range"] == DEFAULT_RANGE
    record = style["materials"]
    assert list(record) == ["source", "sha256", "ramps", "default", "materials"]
    assert record["source"] == "materials.json"
    assert record["ramps"] == LIBRARY["ramps"]
    assert record["default"] is None
    assert record["materials"] == LIBRARY["materials"]
    assert list(record["materials"]) == ["ghost", "glass", "steel"]
    assert list(description["settings"])[-2:] == ["style", "clips"]


def test_ordinary_entries_and_the_default_are_recorded(setup, capsys):
    document = library_with(default="cloth")
    document["materials"]["face"] = "ordinary"
    run_with_library(setup, capsys, "--no-preview", library=document)
    record = json.loads(setup.json.read_text())["settings"]["style"]["materials"]
    assert record["default"] == "cloth"
    assert record["materials"]["face"] == "ordinary"


def test_the_shade_range_is_recorded_without_a_library(setup, capsys):
    assert run(capsys, setup.argv("--no-preview"))[0] == 0
    style = json.loads(setup.json.read_text())["settings"]["style"]
    assert style == PLAIN_STYLE and style["materials"] is None


def test_a_run_with_a_library_maps_each_frame_through_the_ramps(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    run_with_library(setup, capsys, "--no-preview")
    # Steel is metal [1, 2, 3]; the fake shades every pixel 137 over (84, 191),
    # which is band (137 − 84)·3 // 108 = 1.
    assert sheet_colours(setup.png) == {CLEAR, opaque(2)}


@pytest.mark.parametrize("look", ["plain", "mode"])
def test_both_reductions_use_the_ramps(setup, capsys, look):
    named_hero(setup, HERO_MATERIALS)
    run_with_library(setup, capsys, "--no-preview", "--reduce", look)
    assert sheet_colours(setup.png) == {CLEAR, opaque(2)}


def palette_only_sheet(setup, capsys):
    """The sheet bytes of the same run with the palette and no library."""
    outfile = setup.out / "palette-only.png"
    argv = setup.argv(
        "--palette",
        str(palette_file(setup.tmp_path)),
        "--no-preview",
        outfile=outfile,
    )
    assert run(capsys, argv)[0] == 0
    return outfile.read_bytes()


def configure_code(setup, code):
    config = json.loads((setup.fake.parent / "config.json").read_text())
    setup.configure(**(config | {"code": code}))


def test_an_unmapped_material_takes_the_default_ramp_else_the_ordinary_look(
    setup, capsys
):
    named_hero(setup, HERO_MATERIALS)
    configure_code(setup, 2)
    # Cloth has no entry: with the default ramp [4, 5] it takes band
    # (137 − 84)·2 // 108 = 0.
    run_with_library(
        setup, capsys, "--no-preview", library=library_with(default="cloth")
    )
    assert sheet_colours(setup.png) == {CLEAR, opaque(4)}
    # Without a default it takes the ordinary look: exactly the sheet of a run
    # with the palette and no library.
    run_with_library(setup, capsys, "--no-preview")
    assert setup.png.read_bytes() == palette_only_sheet(setup, capsys)


def test_a_blend_material_takes_the_ordinary_look_even_with_an_entry_and_a_default(
    setup, capsys
):
    named_hero(setup, HERO_MATERIALS)
    configure_code(setup, 3)
    document = library_with(default="cloth")
    run_with_library(setup, capsys, "--no-preview", library=document)
    assert setup.png.read_bytes() == palette_only_sheet(setup, capsys)
    assert sheet_colours(setup.png) != {CLEAR, opaque(6)}


def test_an_ordinary_entry_and_missing_and_unnamed_materials_take_the_ordinary_look(
    setup, capsys
):
    named_hero(setup, HERO_MATERIALS)
    document = library_with(default="cloth")
    document["materials"]["cloth"] = "ordinary"
    # The unnamed material, then the primitive without a material.
    for code in (2, 4, 65535):
        configure_code(setup, code)
        run_with_library(setup, capsys, "--no-preview", library=document)
        assert setup.png.read_bytes() == palette_only_sheet(setup, capsys)


# Warnings


def warnings_of(err):
    return [
        line.removeprefix("moskophoros: warning: ")
        for line in err.splitlines()
        if line.startswith("moskophoros: warning: ")
    ]


def test_unmapped_unnamed_and_blend_only_materials_are_named(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    err = run_with_library(setup, capsys, "--no-preview")
    # Two nodes share the mesh, so two parts each have no name (an empty name)
    # and two have no material.
    assert warnings_of(err) == [
        'material "cloth" has no entry in the material library and takes the '
        "ordinary look",
        "4 parts have no material name (an unnamed or missing material) and "
        "take the ordinary look",
        'the library entry "glass" names only translucent (BLEND) materials, '
        "which take the ordinary look",
    ]


def test_the_default_ramp_is_named_in_the_fallback_warning(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    err = run_with_library(
        setup, capsys, "--no-preview", library=library_with(default="metal")
    )
    assert warnings_of(err)[0] == (
        'material "cloth" has no entry in the material library and takes the '
        'default ramp "metal"'
    )


def test_a_blend_only_name_without_an_entry_takes_the_ordinary_look_whatever_the_default(
    setup, capsys
):
    named_hero(setup, HERO_MATERIALS)
    document = library_with(default="metal")
    del document["materials"]["glass"]
    err = run_with_library(setup, capsys, "--no-preview", library=document)
    assert (
        'material "glass" has no entry in the material library; it is translucent '
        "(BLEND) and takes the ordinary look"
    ) in warnings_of(err)


def test_a_library_entry_used_only_by_blend_materials_is_named(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    err = run_with_library(setup, capsys, "--no-preview")
    assert (
        warnings_of(err).count(
            'the library entry "glass" names only translucent (BLEND) materials, '
            "which take the ordinary look"
        )
        == 1
    )


def test_unused_entries_and_ramps_are_silent_and_every_name_warns_once(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    err = run_with_library(setup, capsys, "--no-preview")
    shown = "\n".join(warnings_of(err))
    assert "ghost" not in shown and "cloth" in shown
    assert all("metal" not in warning for warning in warnings_of(err))
    assert len([w for w in warnings_of(err) if '"cloth"' in w]) == 1


def test_there_are_no_material_warnings_without_a_library(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    status, _, err = run(capsys, setup.argv("--no-preview"))
    assert (status, err) == (0, "")


def test_a_name_shared_by_opaque_and_blend_materials_is_reported_once():
    records = [
        PrimitiveMaterial(0, 0, 0, 0, "wood", "OPAQUE"),
        PrimitiveMaterial(0, 0, 1, 1, "wood", "BLEND"),
        PrimitiveMaterial(1, 0, 0, 0, "wood", "OPAQUE"),
        PrimitiveMaterial(1, 0, 1, 1, "wood", "BLEND"),
    ]
    library = materials.validate_library(
        {"schema": materials.SCHEMA, "ramps": {"r": [0]}, "materials": {}},
        COLORS,
        source="t",
    )
    assert materials.warnings(records, library) == [
        'material "wood" has no entry in the material library and takes the '
        "ordinary look; its translucent (BLEND) parts take the ordinary look"
    ]


def test_one_unnamed_part_is_counted_in_the_singular():
    library = materials.validate_library(
        {"schema": materials.SCHEMA, "ramps": {}, "materials": {}}, COLORS, source="t"
    )
    records = [PrimitiveMaterial(0, 0, 0, None, None, "OPAQUE")]
    assert materials.warnings(records, library) == [
        "1 part has no material name (an unnamed or missing material) and takes "
        "the ordinary look"
    ]
    assert materials.warnings([], library) == []


# Fingerprint


def fingerprint(setup):
    return json.loads(setup.json.read_text())["fingerprint"]


def test_the_fingerprint_changes_with_the_library_and_the_shade_range(
    setup, capsys, tmp_path
):
    named_hero(setup, HERO_MATERIALS)
    assert run(capsys, setup.argv("--palette", str(palette_file(tmp_path))))[0] == 0
    without = fingerprint(setup)
    run_with_library(setup, capsys)
    with_library = fingerprint(setup)
    other = library_with()
    other["ramps"]["metal"] = [1, 2, 4]
    run_with_library(setup, capsys, library=other)
    changed = fingerprint(setup)
    assert len({without, with_library, changed}) == 3

    # The same library and a different recorded shade range.
    sheet = tmp_path / "range.json"
    document = json.loads(setup.json.read_text())
    run_with_library(setup, capsys)
    document = json.loads(setup.json.read_text())
    document["settings"]["style"]["shade_range"] = [90, 180]
    sheet.write_text(json.dumps(document))
    assert run(capsys, setup.argv("--settings-from", str(sheet)))[0] == 0
    assert fingerprint(setup) not in {without, with_library, changed}


def test_two_runs_give_byte_identical_outputs(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    run_with_library(setup, capsys)
    first = setup.listing()
    run_with_library(setup, capsys)
    assert setup.listing() == first


# Reuse


def recorded(setup, capsys, *options, library=None):
    """Run with a library, and return the written sheet JSON's path copy."""
    run_with_library(setup, capsys, "--no-preview", *options, library=library)
    sheet = setup.tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    return sheet


def test_a_reused_sheet_reproduces_the_look_without_the_files(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    sheet = recorded(setup, capsys, library=library_with(default="cloth"))
    original = setup.png.read_bytes()
    (setup.tmp_path / "materials.json").unlink()
    (setup.tmp_path / "palette.hex").unlink()
    again = setup.out / "again.png"
    argv = setup.argv("--settings-from", str(sheet), "--no-preview", outfile=again)
    assert run(capsys, argv)[0] == 0
    assert again.read_bytes() == original
    reused = json.loads((setup.out / "again.json").read_text())
    first = json.loads(sheet.read_text())
    assert reused["settings"] == first["settings"]
    assert reused["fingerprint"] == first["fingerprint"]


def test_a_reused_library_warns_about_the_model_it_is_used_on(setup, capsys):
    named_hero(setup, HERO_MATERIALS)
    sheet = recorded(setup, capsys)
    (setup.tmp_path / "materials.json").unlink()
    status, _, err = run(
        capsys,
        setup.argv("--settings-from", str(sheet), "--no-preview"),
    )
    assert status == 0
    assert any('"cloth"' in warning for warning in warnings_of(err))


def test_a_reused_shade_range_decides_the_bands(setup, capsys, tmp_path):
    named_hero(setup, HERO_MATERIALS)
    sheet = recorded(setup, capsys)
    document = json.loads(sheet.read_text())
    document["settings"]["style"]["shade_range"] = [140, 200]
    sheet.write_text(json.dumps(document))
    assert (
        run(capsys, setup.argv("--settings-from", str(sheet), "--no-preview"))[0] == 0
    )
    # Shade 137 is below 140 and clamps to band 0 of metal: entry 1.
    assert sheet_colours(setup.png) == {CLEAR, opaque(1)}


def test_a_reused_shade_range_is_kept_when_an_explicit_library_replaces_the_library(
    setup, capsys
):
    named_hero(setup, HERO_MATERIALS)
    sheet = recorded(setup, capsys)
    document = json.loads(sheet.read_text())
    document["settings"]["style"]["shade_range"] = [140, 200]
    sheet.write_text(json.dumps(document))
    replacement = library_file(setup.tmp_path, library_with(), name="other.json")
    assert (
        run(
            capsys,
            setup.argv(
                "--settings-from",
                str(sheet),
                "--materials",
                str(replacement),
                "--no-preview",
            ),
        )[0]
        == 0
    )
    style = json.loads(setup.json.read_text())["settings"]["style"]
    assert style["shade_range"] == [140, 200]
    assert style["materials"]["source"] == "other.json"
    assert sheet_colours(setup.png) == {CLEAR, opaque(1)}


def test_a_version_2_sheet_reuses_with_no_library_and_the_default_range(tmp_path):
    path = write_previous_sheet(tmp_path)
    options = cli.resolve_settings(
        cli.parse_args(["--settings-from", str(path), "model.glb", "out.png"])
    )
    assert options.materials is None
    assert options.shade_range == backend.DEFAULT_SHADE_RANGE
    assert cli.style_record(options) == PLAIN_STYLE


def test_a_legacy_sheet_reuses_with_no_library_and_the_default_range(tmp_path):
    options = cli.resolve_settings(
        cli.parse_args(
            ["--settings-from", str(write_legacy_sheet(tmp_path)), "m.glb", "o.png"]
        )
    )
    assert cli.style_record(options) == PLAIN_STYLE


def test_an_older_sheet_has_no_library_or_range_fields(tmp_path, capsys):
    path = write_previous_sheet(
        tmp_path,
        edited({"style.materials": None, "style.shade_range": [84, 191]}),
    )
    with pytest.raises(cli.UsageError):
        cli.read_settings(path)
    err = capsys.readouterr().err
    assert "settings.style.materials: unknown field" in err
    assert "settings.style.shade_range: unknown field" in err


# Malformed `/3` style fields


GOOD_RECORD = {
    "source": "materials.json",
    "sha256": "ab" * 32,
    "ramps": {"metal": [1, 2, 3]},
    "default": None,
    "materials": {"steel": {"uses": "metal"}, "face": "ordinary"},
}
PALETTE_RECORD = {
    "source": "palette.hex",
    "sha256": "cd" * 32,
    "colors": ["#" + bytes(color).hex() for color in COLORS],
}


def style_sheet(tmp_path, **changes):
    style = {
        "reduce": "plain",
        "palette": PALETTE_RECORD,
        "materials": GOOD_RECORD,
        "shade_range": [84, 191],
    } | changes
    return write_sheet(tmp_path, edited({"style": style}))


def test_a_well_formed_library_record_reads(tmp_path):
    reused = cli.read_settings(style_sheet(tmp_path))
    assert reused.materials.source == "materials.json"
    assert reused.materials.library.ramps["metal"] == (1, 2, 3)
    assert reused.shade_range == (84, 191)


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"materials": "x"}, "settings.style.materials: expected an object"),
        ({"materials": []}, "settings.style.materials: expected an object"),
        (
            {"materials": {k: v for k, v in GOOD_RECORD.items() if k != "ramps"}},
            "settings.style.materials.ramps: missing",
        ),
        (
            {"materials": {k: v for k, v in GOOD_RECORD.items() if k != "default"}},
            "settings.style.materials.default: missing",
        ),
        (
            {"materials": GOOD_RECORD | {"extra": 1}},
            "settings.style.materials.extra: unknown field",
        ),
        (
            {"materials": GOOD_RECORD | {"source": "a/b.json"}},
            "settings.style.materials.source: expected a nonempty base filename",
        ),
        (
            {"materials": GOOD_RECORD | {"sha256": "AB" * 32}},
            "settings.style.materials.sha256: expected 64 lowercase hexadecimal",
        ),
        (
            {"materials": GOOD_RECORD | {"ramps": []}},
            "settings.style.materials: ramps: expected an object",
        ),
        (
            {"materials": GOOD_RECORD | {"ramps": {"metal": [1, 8]}}},
            'settings.style.materials: ramps["metal"][1]: 8 is not an index',
        ),
        (
            {"materials": GOOD_RECORD | {"ramps": {"metal": [True]}}},
            'settings.style.materials: ramps["metal"][0]: true is not an integer',
        ),
        (
            {"materials": GOOD_RECORD | {"ramps": {"metal": []}}},
            'settings.style.materials: ramps["metal"]: has 0 entries',
        ),
        (
            {"materials": GOOD_RECORD | {"default": 1}},
            "settings.style.materials.default: expected a nonempty ramp name or null",
        ),
        (
            {"materials": GOOD_RECORD | {"default": ""}},
            "settings.style.materials.default: expected a nonempty ramp name or null",
        ),
        (
            {"materials": GOOD_RECORD | {"default": "nope"}},
            "settings.style.materials: default: no ramp is named",
        ),
        (
            {"materials": GOOD_RECORD | {"materials": {"steel": {"uses": "nope"}}}},
            'settings.style.materials: materials["steel"].uses: no ramp is named',
        ),
        (
            {"materials": GOOD_RECORD | {"materials": {"steel": "metal"}}},
            'settings.style.materials: materials["steel"]: expected',
        ),
        (
            {"materials": GOOD_RECORD | {"materials": {"": "ordinary"}}},
            "settings.style.materials: materials: the empty name is not allowed",
        ),
        (
            {"materials": GOOD_RECORD | {"materials": None}},
            "settings.style.materials.materials: must be set, got null",
        ),
        ({"palette": None}, "settings.style.materials: a library needs a palette"),
        ({"shade_range": None}, "settings.style.shade_range: must be set"),
        (
            {"shade_range": "84,191"},
            "settings.style.shade_range: expected two integers",
        ),
        ({"shade_range": [84]}, "settings.style.shade_range: expected two integers"),
        (
            {"shade_range": [84, 191, 200]},
            "settings.style.shade_range: expected two integers",
        ),
        ({"shade_range": [84.0, 191]}, "settings.style.shade_range: expected two"),
        ({"shade_range": [84, 191.5]}, "settings.style.shade_range: expected two"),
        ({"shade_range": [True, 191]}, "settings.style.shade_range: expected two"),
        ({"shade_range": ["84", "191"]}, "settings.style.shade_range: expected two"),
        ({"shade_range": [191, 84]}, "settings.style.shade_range: expected 0 <= lo"),
        ({"shade_range": [100, 100]}, "settings.style.shade_range: expected 0 <= lo"),
        ({"shade_range": [-1, 5]}, "settings.style.shade_range: expected 0 <= lo"),
        ({"shade_range": [0, 256]}, "settings.style.shade_range: expected 0 <= lo"),
    ],
)
def test_each_malformed_style_field_is_a_usage_error_naming_it(
    tmp_path, capsys, changes, problem
):
    path = style_sheet(tmp_path, **changes)
    with pytest.raises(cli.UsageError):
        cli.read_settings(path)
    err = capsys.readouterr().err
    assert f"--settings-from {str(path)!r}: " in err
    assert problem in err


def test_a_bad_shade_range_is_an_error_even_when_the_library_is_null(tmp_path, capsys):
    path = style_sheet(tmp_path, materials=None, shade_range=[200, 100])
    with pytest.raises(cli.UsageError):
        cli.read_settings(path)
    assert "settings.style.shade_range: expected 0 <= lo" in capsys.readouterr().err


def test_a_style_member_missing_from_a_version_3_sheet_is_an_error(tmp_path, capsys):
    for member in ("materials", "shade_range"):
        style = {
            "reduce": "plain",
            "palette": None,
            "materials": None,
            "shade_range": [84, 191],
        }
        del style[member]
        path = write_sheet(tmp_path, edited({"style": style}))
        with pytest.raises(cli.UsageError):
            cli.read_settings(path)
        assert f"settings.style.{member}: missing" in capsys.readouterr().err


# D-24: explicit options beside a reused library


def resolved(tmp_path, *args, sheet=None):
    path = style_sheet(tmp_path) if sheet is None else sheet
    return cli.resolve_settings(
        cli.parse_args(["--settings-from", str(path), *args, "model.glb", "out.png"])
    )


def failing(tmp_path, capsys, *args, sheet=None):
    with pytest.raises(cli.UsageError):
        resolved(tmp_path, *args, sheet=sheet)
    err = capsys.readouterr().err
    assert err.splitlines()[0].startswith("usage:")
    return err


def test_a_reused_library_with_a_reused_palette_is_allowed(tmp_path):
    options = resolved(tmp_path)
    assert options.materials.source == "materials.json"
    assert options.palette.source == "palette.hex"
    assert cli.style_record(options)["materials"] == GOOD_RECORD | {
        "materials": {"face": "ordinary", "steel": {"uses": "metal"}}
    }


def test_the_reused_record_is_written_back_unchanged(tmp_path):
    record = GOOD_RECORD | {
        "materials": {"face": "ordinary", "steel": {"uses": "metal"}}
    }
    options = resolved(tmp_path, sheet=style_sheet(tmp_path, materials=record))
    assert cli.style_record(options)["materials"] == record


@pytest.mark.parametrize(
    "colors",
    [
        COLORS[::-1],
        COLORS[1:] + COLORS[:1],
        COLORS[:-1],
        (*COLORS, (9, 9, 9)),
        ((1, 2, 3), *COLORS[1:]),
    ],
    ids=["reversed", "rotated", "dropped", "added", "changed"],
)
def test_a_reused_library_with_a_different_palette_is_refused(tmp_path, capsys, colors):
    other = palette_file(tmp_path, colors, name="other.hex")
    err = failing(tmp_path, capsys, "--palette", str(other))
    assert str(other) in err and "reused material library" in err
    assert "--materials" in err and "--no-materials" in err


def test_the_same_colours_from_another_file_and_format_are_the_same_palette(
    tmp_path,
):
    gpl = tmp_path / "other.gpl"
    gpl.write_text(
        "GIMP Palette\nName: x\n#\n" + "".join(f"{r} {g} {b} c\n" for r, g, b in COLORS)
    )
    options = resolved(tmp_path, "--palette", str(gpl))
    assert options.palette.source == "other.gpl"
    assert options.palette.sha256 != PALETTE_RECORD["sha256"]
    assert options.materials.source == "materials.json"


def test_a_reused_library_with_no_palette_is_refused(tmp_path, capsys):
    err = failing(tmp_path, capsys, "--no-palette")
    assert "--no-palette" in err and "--no-materials" in err


def test_no_materials_drops_the_reused_library(tmp_path):
    options = resolved(tmp_path, "--no-materials")
    assert options.materials is None
    assert options.palette.source == "palette.hex"
    assert cli.style_record(options)["materials"] is None
    assert cli.style_record(options)["shade_range"] == [84, 191]


def test_a_valid_library_may_be_dropped_with_the_palette_or_beside_a_new_one(
    tmp_path,
):
    dropped = resolved(tmp_path, "--no-materials", "--no-palette")
    assert (dropped.materials, dropped.palette) == (None, None)
    other = palette_file(tmp_path, ((1, 2, 3),), name="tiny.hex")
    replaced = resolved(tmp_path, "--no-materials", "--palette", str(other))
    assert replaced.materials is None and replaced.palette.source == "tiny.hex"


def test_an_explicit_library_replaces_the_reused_one_with_any_palette_in_force(
    tmp_path,
):
    document = library_with()
    document["materials"] = {"cloth": {"ramp": [0, 1]}}
    path = library_file(tmp_path, document, name="mine.json")
    options = resolved(tmp_path, "--materials", str(path))
    assert options.materials.source == "mine.json"
    assert "cloth" in options.materials.library.materials
    tiny = palette_file(tmp_path, COLORS[:2], name="tiny.hex")
    small = tmp_path / "small.json"
    small.write_text(
        json.dumps(
            {
                "schema": materials.SCHEMA,
                "ramps": {"r": [0, 1]},
                "materials": {"a": {"uses": "r"}},
            }
        )
    )
    options = resolved(tmp_path, "--palette", str(tiny), "--materials", str(small))
    assert options.palette.source == "tiny.hex"
    assert options.materials.source == "small.json"


def test_an_explicit_library_is_validated_against_the_palette_in_force(
    tmp_path, capsys
):
    # Index 7 is valid in the reused eight-colour palette and not in two.
    tiny = palette_file(tmp_path, COLORS[:2], name="tiny.hex")
    err = failing(
        tmp_path,
        capsys,
        "--palette",
        str(tiny),
        "--materials",
        str(library_file(tmp_path)),
    )
    assert (
        "materials.json" in err and "is not an index into the 2-colour palette" in err
    )


def test_an_invalid_reused_library_is_an_error_whatever_overrides_it(tmp_path, capsys):
    bad = GOOD_RECORD | {"ramps": {"metal": [1, 2, 9]}}
    sheet = style_sheet(tmp_path, materials=bad)
    mine = library_file(tmp_path, library_with(), name="mine.json")
    other = palette_file(tmp_path, COLORS[:3], name="other.hex")
    for args in (
        (),
        ("--no-materials",),
        ("--no-materials", "--no-palette"),
        ("--materials", str(mine)),
        ("--palette", str(other), "--materials", str(mine)),
    ):
        err = failing(tmp_path, capsys, *args, sheet=sheet)
        assert 'settings.style.materials: ramps["metal"][2]: 9 is not an index' in err


def test_the_final_combination_is_checked_before_any_blender_invocation(
    setup, capsys, monkeypatch, tmp_path
):
    forbid_blender(monkeypatch)
    sheet = style_sheet(tmp_path)
    other = palette_file(tmp_path, COLORS[::-1], name="other.hex")
    status, _, err = run(
        capsys,
        setup.argv("--settings-from", str(sheet), "--palette", str(other)),
    )
    assert status == 2 and "reused material library" in err
    assert setup.calls() == []
    status, _, err = run(
        capsys, setup.argv("--settings-from", str(sheet), "--no-palette")
    )
    assert status == 2 and setup.calls() == []


# Without a library the existing looks are unchanged


@pytest.mark.parametrize("look", ["plain", "mode"])
@pytest.mark.parametrize("paletted", [False, True])
def test_the_buffers_change_no_sheet_or_preview_without_a_library(
    setup, capsys, monkeypatch, look, paletted
):
    setup.configure(pixels="noise")
    options = ["--reduce", look]
    if paletted:
        options += ["--palette", str(palette_file(setup.tmp_path))]
    assert run(capsys, setup.argv(*options))[0] == 0
    with_buffers = setup.listing()

    # The same run through the reduction as it was before the buffers: the
    # colour alone, nothing else asked.
    real = getattr(stylize, look)

    def colour_only(frames, factor, **kwargs):
        from moskophoros.sampling import ImageFrame

        bare = (ImageFrame(f.address, f.pixels, f.metadata) for f in frames)
        kwargs.pop("identities", None)
        assert "library" not in kwargs and "shade_range" not in kwargs
        return real(bare, factor, **kwargs)

    monkeypatch.setattr(stylize, look, colour_only)
    assert run(capsys, setup.argv(*options))[0] == 0
    assert setup.listing() == with_buffers
    assert sorted(with_buffers) == [
        "hero.attack.gif",
        "hero.json",
        "hero.png",
        "hero.walk.gif",
    ]
