"""The shading controls through the whole command, with a controlled fake
Blender: what a run records, how a sheet reproduces it without the palette or
library files, `/4` libraries, the capture job of an ordinary entry, and the
warnings for a global value a library or material beats (shading design
contract 1 to 3, D-5 to D-11, D-24 to D-30, D-32 to D-34, D-41).

Pixel arithmetic is the stage tests' business; these tests pin that the
command wires the settings through, records them and reuses them, and that
nothing a shading choice does touches alpha or the geometry maps."""

import copy
import json
import os
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image
from test_command import Setup, run
from test_materials_command import (
    HERO_MATERIALS,
    forbid_blender,
    named_hero,
    palette_file,
    warnings_of,
)
from test_settings_command import project_file

from moskophoros import cli, views

V4 = "moskophoros.materials/4"
DIRECTION = [-0.5183210553488161, 0.604707897906952, 0.604707897906952]
# What `--bake-key-direction 0,0.3,0.4` resolves to.
STEEP = list(views.normalise((0.0, 0.3, 0.4)))


@pytest.fixture
def setup(tmp_path):
    hero = Setup(tmp_path)
    named_hero(hero, HERO_MATERIALS)
    return hero


def library(**changes):
    document = {
        "schema": V4,
        "ramps": {"metal": [1, 2, 3], "cloth": [4, 5]},
        "materials": {
            "steel": {"uses": "metal"},
            "cloth": {"uses": "cloth"},
            "glass": {"ramp": [6]},
        },
    }
    return document | changes


def write_library(tmp_path, document, name="materials.yaml"):
    path = Path(tmp_path) / name
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    return path


def argv(setup, *options, document=None, outfile=None):
    """A run with the eight-colour palette and, if `document`, a library."""
    extra = ["--palette", str(palette_file(setup.tmp_path))]
    if document is not None:
        extra += ["--materials", str(write_library(setup.tmp_path, document))]
    return setup.argv(*extra, *options, outfile=outfile)


def go(setup, capsys, *options, document=None, outfile=None):
    status, _, err = run(
        capsys, argv(setup, *options, document=document, outfile=outfile)
    )
    assert status == 0, err
    return err


def sheet_of(setup):
    return json.loads(setup.json.read_text())


def shade_of(setup):
    return sheet_of(setup)["settings"]["shade"]


def listing(directory):
    return {path.name: path.read_bytes() for path in sorted(Path(directory).iterdir())}


# What a run records


def test_a_default_run_records_the_default_shading_in_order(setup, capsys):
    go(setup, capsys, "--no-preview")
    shade = shade_of(setup)
    assert list(shade) == [
        "ao_distance_m",
        "ao_samples",
        "occlusion_weight",
        "convexity_weight",
        "range",
        "mode",
        "ambient_form",
        "key",
        "sky",
        "ground",
        "sky_ground_frame",
        "brightness",
        "snap",
        "dither",
    ]
    assert shade == {
        "ao_distance_m": 0.3,
        "ao_samples": 64,
        "occlusion_weight": 0.25,
        "convexity_weight": 1.0,
        "range": [84, 191],
        "mode": "ramp",
        "ambient_form": True,
        "key": {"direction": DIRECTION, "strength": 0.0},
        "sky": {"strength": 0.0},
        "ground": {"strength": 0.0},
        "sky_ground_frame": "camera",
        "brightness": {"floor": 0.3, "ceiling": 1.0},
        "snap": "off",
        "dither": {"pattern": "off", "strength": 1.0},
    }
    assert sheet_of(setup)["schema"] == "moskophoros.sheet/15"
    text = setup.json.read_text()
    # Numbers are floats, the integers stay integers, and booleans are JSON.
    assert '"strength": 0.0' in text and '"ao_samples": 64' in text
    assert '"ambient_form": true' in text


ALL_OPTIONS = (
    "--shade-mode",
    "both",
    "--no-ambient-form",
    "--bake-key-direction",
    "0,0.3,0.4",
    "--bake-key-strength",
    "0.4",
    "--bake-sky-strength",
    "0.25",
    "--bake-ground-strength",
    "0.125",
    "--bake-sky-ground-frame",
    "world",
    "--brightness-floor",
    "0.2",
    "--brightness-ceiling",
    "0.9",
    "--shade-snap",
    "ramp",
    "--dither-pattern",
    "clustered4",
    "--dither-strength",
    "0.5",
)


def test_every_option_is_recorded_as_resolved_even_when_inactive(setup, capsys):
    go(setup, capsys, "--no-preview", *ALL_OPTIONS)
    shade = shade_of(setup)
    assert {key: shade[key] for key in list(shade)[5:]} == {
        "mode": "both",
        "ambient_form": False,
        "key": {"direction": STEEP, "strength": 0.4},
        "sky": {"strength": 0.25},
        "ground": {"strength": 0.125},
        "sky_ground_frame": "world",
        "brightness": {"floor": 0.2, "ceiling": 0.9},
        "snap": "ramp",
        "dither": {"pattern": "clustered4", "strength": 0.5},
    }
    # The unit direction is recorded exactly as `views.normalise` gives it.
    assert shade["key"]["direction"] == STEEP


def test_inactive_values_are_recorded_beside_a_mode_that_ignores_them(setup, capsys):
    go(setup, capsys, "--no-preview", "--bake-key-strength", "0.5")
    shade = shade_of(setup)
    assert shade["mode"] == "ramp" and shade["key"]["strength"] == 0.5


@pytest.mark.parametrize(
    "variation",
    [
        ("--shade-mode", "neither"),
        ("--no-ambient-form",),
        ("--bake-key-direction", "1,0,0"),
        ("--bake-key-strength", "0.1"),
        ("--bake-sky-strength", "0.1"),
        ("--bake-ground-strength", "0.1"),
        ("--bake-sky-ground-frame", "world"),
        ("--brightness-floor", "0.2"),
        ("--brightness-ceiling", "0.9"),
        ("--shade-snap", "palette"),
        ("--dither-pattern", "ordered2"),
        ("--dither-strength", "0.5"),
    ],
)
def test_every_shading_value_is_in_the_fingerprint(setup, capsys, variation):
    go(setup, capsys, "--no-preview")
    default = sheet_of(setup)["fingerprint"]
    go(setup, capsys, "--no-preview", *variation)
    assert sheet_of(setup)["fingerprint"] != default


def test_an_inline_override_is_in_the_fingerprint(setup, capsys):
    plain = library()
    go(setup, capsys, "--no-preview", document=plain)
    first = sheet_of(setup)["fingerprint"]
    plain["materials"]["steel"]["shade"] = {"dither": {"strength": 0.5}}
    go(setup, capsys, "--no-preview", document=plain)
    second = sheet_of(setup)["fingerprint"]
    plain["materials"]["steel"]["shade"] = {"dither": {"strength": 0.25}}
    go(setup, capsys, "--no-preview", document=plain)
    assert len({first, second, sheet_of(setup)["fingerprint"]}) == 3


# `/4` records: as supplied, in a fixed order, byte for byte on reuse

SUPPLIED = library(
    shade={
        "range": [100, 200],
        "dither": {"strength": 0.5, "pattern": "ordered2"},
        "mode": "brightness",
        "brightness": {"ceiling": 0.8},
    },
    materials={
        "steel": {
            "uses": "metal",
            "shade": {
                "sky": {"strength": 0.125},
                "range": [10, 250],
                "ambient_form": False,
                "occlusion_weight": 0.5,
                "key": {"strength": 0.25},
            },
        },
        "cloth": "ordinary",
        "paint": {"ordinary": True},
        "glass": {
            "ordinary": True,
            "shade": {
                "mode": "both",
                "ao_distance_m": 0.6,
                "convexity_weight": 0.0,
                "brightness": {"floor": 0.1},
                "dither": {"pattern": "ordered8"},
            },
        },
    },
)


def test_a_v4_library_is_recorded_as_supplied_in_a_fixed_order(setup, capsys):
    go(setup, capsys, "--no-preview", document=SUPPLIED)
    record = sheet_of(setup)["settings"]["style"]["materials"]
    assert list(record) == [
        "source",
        "sha256",
        "ramps",
        "default",
        "shade",
        "materials",
    ]
    # The library-wide shade: the range, then the response in table order,
    # nested mappings holding only the leaves supplied.
    assert list(record["shade"]) == ["range", "mode", "brightness", "dither"]
    assert record["shade"] == {
        "range": [100, 200],
        "mode": "brightness",
        "brightness": {"ceiling": 0.8},
        "dither": {"pattern": "ordered2", "strength": 0.5},
    }
    assert list(record["shade"]["dither"]) == ["pattern", "strength"]
    steel = record["materials"]["steel"]
    assert list(steel) == ["uses", "shade"]
    assert list(steel["shade"]) == [
        "occlusion_weight",
        "range",
        "ambient_form",
        "key",
        "sky",
    ]
    assert steel["shade"] == {
        "occlusion_weight": 0.5,
        "range": [10, 250],
        "ambient_form": False,
        "key": {"strength": 0.25},
        "sky": {"strength": 0.125},
    }
    # A string stays a string; a mapping stays a mapping with only what it
    # supplied; nothing inherited is written into an entry.
    assert record["materials"]["cloth"] == "ordinary"
    assert record["materials"]["paint"] == {"ordinary": True}
    glass = record["materials"]["glass"]
    assert list(glass) == ["ordinary", "shade"]
    assert list(glass["shade"]) == [
        "ao_distance_m",
        "convexity_weight",
        "mode",
        "brightness",
        "dither",
    ]
    assert glass["shade"]["brightness"] == {"floor": 0.1}
    assert glass["shade"]["dither"] == {"pattern": "ordered8"}


def test_a_v4_record_reuses_to_the_same_bytes_without_the_files(
    setup, capsys, tmp_path
):
    go(setup, capsys, "--no-preview", document=SUPPLIED)
    first = setup.json.read_bytes()
    first_png = setup.png.read_bytes()
    (tmp_path / "materials.yaml").unlink()
    (tmp_path / "palette.hex").unlink()
    again = setup.tmp_path / "again" / "hero.png"
    again.parent.mkdir()
    status, _, err = run(
        capsys,
        [
            "--settings-from",
            str(setup.json),
            "--blender",
            str(setup.fake),
            str(setup.model),
            str(again),
        ],
    )
    assert status == 0, err
    assert (again.parent / "hero.json").read_bytes() == first
    assert again.read_bytes() == first_png


def test_the_two_forms_of_an_ordinary_entry_are_never_collapsed(
    setup, capsys, tmp_path
):
    document = library(
        materials={
            "steel": "ordinary",
            "cloth": {"ordinary": True},
            "glass": {"ordinary": True, "shade": {"mode": "neither"}},
        }
    )
    go(setup, capsys, "--no-preview", document=document)
    materials = sheet_of(setup)["settings"]["style"]["materials"]["materials"]
    assert materials == {
        "steel": "ordinary",
        "cloth": {"ordinary": True},
        "glass": {"ordinary": True, "shade": {"mode": "neither"}},
    }


# Reproduction from a sheet alone


def reproduce(setup, capsys, tmp_path, *options, document=None):
    """Run with `options`, remove the palette and library files, and run
    again with `--settings-from` and nothing else; return both listings."""
    go(setup, capsys, *options, document=document)
    first = listing(setup.out)
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    for name in ("palette.hex", "materials.yaml"):
        if (tmp_path / name).exists():
            (tmp_path / name).unlink()
    other = tmp_path / "again"
    other.mkdir()
    status, _, err = run(
        capsys,
        [
            "--settings-from",
            str(sheet),
            "--blender",
            str(setup.fake),
            str(setup.model),
            str(other / "hero.png"),
        ],
    )
    assert status == 0, err
    return first, listing(other)


REPRODUCED = [
    pytest.param(
        ("--shade-mode", "brightness", "--bake-key-strength", "0.5"),
        id="brightness key",
    ),
    pytest.param(
        (
            "--shade-mode",
            "both",
            "--bake-key-direction",
            "-1,0.5,0.2",
            "--bake-key-strength",
            "0.4",
            "--bake-sky-strength",
            "0.3",
            "--bake-sky-ground-frame",
            "world",
            "--camera-roll",
            "0.2",
            "--view",
            "topdown",
            "--dither-pattern",
            "ordered4",
            "--dither-strength",
            "0.5",
            "--shade-snap",
            "palette",
        ),
        id="world frame, roll, dither and snap",
    ),
    pytest.param(
        (
            "--shade-mode",
            "neither",
            "--no-ambient-form",
            "--bake-ground-strength",
            "0.5",
            "--shade-snap",
            "ramp",
            "--no-normals",
            "--no-preview",
            "--depth",
        ),
        id="neither, disabled maps and previews",
    ),
    pytest.param(
        (
            "--projection",
            "perspective",
            "--camera-position",
            "0,1,8",
            "--camera-roll",
            "-0.1",
            "--shade-mode",
            "both",
            "--bake-sky-ground-frame",
            "world",
            "--bake-sky-strength",
            "0.5",
            "--light",
            "20,30,40",
        ),
        id="perspective, roll and a preview light",
    ),
]


@pytest.mark.parametrize("options", REPRODUCED)
def test_a_new_sheet_reproduces_byte_for_byte_from_its_json_alone(
    setup, capsys, tmp_path, options
):
    setup.configure(
        pixels="noise",
        surfaces="varied",
        depths=[0.05],
        code=1,
        **setup_materials(setup),
    )
    first, second = reproduce(setup, capsys, tmp_path, *options)
    assert first.keys() == second.keys()
    assert first == second


def setup_materials(setup):
    return {
        "materials": [{"id": k + 1, "material": k} for k in range(len(HERO_MATERIALS))]
        + [{"id": 65535, "material": None}]
    }


@pytest.mark.parametrize("options", REPRODUCED[:2])
def test_a_sheet_with_a_library_reproduces_without_either_file(
    setup, capsys, tmp_path, options
):
    setup.configure(
        pixels="noise",
        surfaces="varied",
        depths=[0.05],
        code=1,
        **setup_materials(setup),
    )
    first, second = reproduce(setup, capsys, tmp_path, *options, document=SUPPLIED)
    assert first == second
    assert json.loads(first["hero.json"])["settings"]["style"]["materials"]


def test_a_translucent_front_layer_reproduces_too(setup, capsys, tmp_path):
    setup.configure(
        pixels="noise",
        surfaces="varied",
        depths=[0.05],
        front={"colour": [200, 30, 30], "q": 0.5, "code": 1},
        code=1,
        **setup_materials(setup),
    )
    first, second = reproduce(
        setup,
        capsys,
        tmp_path,
        "--shade-mode",
        "both",
        "--bake-key-strength",
        "0.5",
        "--shade-snap",
        "palette",
        "--dither-pattern",
        "diagonal4",
    )
    assert first == second


def test_an_explicit_option_overrides_only_its_own_leaf_on_reuse(
    setup, capsys, tmp_path
):
    go(setup, capsys, "--no-preview", *ALL_OPTIONS[:-6])
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    status, _, err = run(
        capsys,
        setup.argv(
            "--settings-from", str(sheet), "--no-preview", "--bake-key-strength", "0.1"
        ),
    )
    assert status == 0, err
    shade = shade_of(setup)
    assert shade["key"] == {"direction": STEEP, "strength": 0.1}
    assert shade["mode"] == "both" and shade["sky"] == {"strength": 0.25}


def test_a_global_option_does_not_defeat_retained_material_leaves(
    setup, capsys, tmp_path
):
    document = library(
        materials={
            "steel": {"uses": "metal", "shade": {"mode": "both"}},
            "glass": {"ordinary": True, "shade": {"brightness": {"floor": 0.1}}},
        }
    )
    go(setup, capsys, "--no-preview", document=document)
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    status, _, err = run(
        capsys,
        setup.argv(
            "--settings-from",
            str(sheet),
            "--no-preview",
            "--shade-mode",
            "neither",
            "--brightness-floor",
            "0.6",
        ),
    )
    assert status == 0, err
    materials = sheet_of(setup)["settings"]["style"]["materials"]["materials"]
    assert materials["steel"]["shade"] == {"mode": "both"}
    assert materials["glass"]["shade"] == {"brightness": {"floor": 0.1}}
    shade = shade_of(setup)
    assert shade["mode"] == "neither" and shade["brightness"]["floor"] == 0.6


def test_a_sheet_from_the_previous_schema_is_refused_without_conversion(
    setup, capsys, monkeypatch, tmp_path
):
    go(setup, capsys, "--no-preview")
    document = json.loads(setup.json.read_text())
    document["schema"] = "moskophoros.sheet/14"
    for name in list(document["settings"]["shade"])[5:]:
        del document["settings"]["shade"][name]
    old = tmp_path / "old.json"
    old.write_text(json.dumps(document))
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--settings-from", str(old)))
    assert status == 2
    assert err.splitlines()[-1] == (
        f"moskophoros: error: --settings-from {str(old)!r}: is a "
        "moskophoros.sheet/14 sheet; only moskophoros.sheet/15 sheets load, so "
        "generate it again"
    )


def test_a_recorded_non_unit_key_direction_is_invalid_not_normalised(
    setup, capsys, monkeypatch, tmp_path
):
    go(setup, capsys, "--no-preview")
    document = json.loads(setup.json.read_text())
    document["settings"]["shade"]["key"]["direction"] = [0.0, 0.0, 2.0]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(document))
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--settings-from", str(path)))
    assert status == 2
    assert (
        "settings.shade.key.direction: expected a recorded unit direction [x, y, z]"
        in err
    )
    # A unit vector within tolerance is kept as it is, to the last digit.
    document["settings"]["shade"]["key"]["direction"] = [0.0, 0.6, 0.8000000000001]
    path.write_text(json.dumps(document))
    reused = cli.read_settings(path)
    assert reused.key_direction == (0.0, 0.6, 0.8000000000001)


@pytest.mark.parametrize(
    ("edit", "problem"),
    [
        (("mode", "sparkle"), "settings.shade.mode: expected ramp, brightness"),
        (("ambient_form", 1), "settings.shade.ambient_form: expected true or false"),
        (("snap", None), "settings.shade.snap: must be set, got null"),
        (("snap", "all"), "settings.shade.snap: expected off, ramp or palette"),
        (
            ("sky_ground_frame", "up"),
            "settings.shade.sky_ground_frame: expected camera or world",
        ),
        (
            ("key", {"direction": [0, 1, 0]}),
            "settings.shade.key.strength: missing",
        ),
        (
            ("key", {"direction": [0, 1, 0], "strength": True}),
            "settings.shade.key.strength: expected a finite number from 0 to 1",
        ),
        (
            ("sky", {"strength": 1.5}),
            "settings.shade.sky.strength: expected a finite number from 0 to 1",
        ),
        (
            ("brightness", {"floor": 0.1}),
            "settings.shade.brightness.ceiling: missing",
        ),
        (
            ("dither", {"pattern": "off", "strength": 1, "extra": 1}),
            "settings.shade.dither.extra: unknown field",
        ),
        (("ground", None), "settings.shade.ground: must be set, got null"),
    ],
)
def test_a_recorded_shading_field_is_checked_strictly(
    setup, capsys, monkeypatch, tmp_path, edit, problem
):
    go(setup, capsys, "--no-preview")
    document = json.loads(setup.json.read_text())
    document["settings"]["shade"][edit[0]] = edit[1]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(document))
    forbid_blender(monkeypatch)
    status, _, err = run(
        capsys, setup.argv("--settings-from", str(path), "--shade-mode", "both")
    )
    assert status == 2
    assert problem in err


def test_a_missing_recorded_shading_field_is_refused(
    setup, capsys, monkeypatch, tmp_path
):
    go(setup, capsys, "--no-preview")
    document = json.loads(setup.json.read_text())
    del document["settings"]["shade"]["dither"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(document))
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, setup.argv("--settings-from", str(path)))
    assert status == 2
    assert "settings.shade.dither: missing" in err


# An ordinary entry's capture values reach the capture job


def job_materials(work, mode="render"):
    job = json.loads((work / mode / "job.json").read_text())
    return job["settings"]["shade"]["materials"]


def test_an_ordinary_mapping_entrys_capture_values_reach_the_job(setup, capsys):
    document = library(
        materials={
            "steel": {
                "ordinary": True,
                "shade": {"ao_distance_m": 1.5, "occlusion_weight": 0.9},
            },
            "cloth": {"uses": "cloth", "shade": {"convexity_weight": 0.2}},
            "glass": {"ordinary": True, "shade": {"mode": "both"}},
        }
    )
    work = setup.tmp_path / "work"
    go(
        setup,
        capsys,
        "--no-preview",
        "--convexity-weight",
        "0.6",
        "--work-dir",
        str(work),
        document=document,
    )
    for mode in ("measure", "render"):
        # Steel is glTF material 0, cloth 1; glass, with only a response, has
        # nothing to capture differently. Omitted capture leaves take the
        # resolved global values, not the shipped ones.
        assert job_materials(work, mode) == [
            {
                "material": 0,
                "ao_distance_m": 1.5,
                "occlusion_weight": 0.9,
                "convexity_weight": 0.6,
            },
            {
                "material": 1,
                "ao_distance_m": 0.3,
                "occlusion_weight": 0.25,
                "convexity_weight": 0.2,
            },
        ]
    record = sheet_of(setup)["settings"]["style"]["materials"]["materials"]
    assert record["steel"] == {
        "ordinary": True,
        "shade": {"ao_distance_m": 1.5, "occlusion_weight": 0.9},
    }


def colours(path):
    with Image.open(path) as image:
        return np.array(image)


def run_ranges(setup, capsys, name, document, *options):
    out = setup.tmp_path / name
    out.mkdir()
    status, _, err = run(
        capsys,
        argv(
            setup, "--no-preview", *options, document=document, outfile=out / "hero.png"
        ),
    )
    assert status == 0, err
    return colours(out / "hero.png")


def test_an_ordinary_entrys_own_range_sets_its_ambient_signal(setup, capsys):
    setup.configure(code=1, pixels="noise", **setup_materials(setup))
    mode = ("--shade-mode", "brightness")
    plain = library(materials={"steel": {"ordinary": True}})
    entry = copy.deepcopy(plain)
    entry["materials"]["steel"]["shade"] = {"range": [10, 200]}
    wide = copy.deepcopy(plain)
    wide["shade"] = {"range": [10, 200]}
    both = copy.deepcopy(wide)
    both["materials"]["steel"]["shade"] = {"range": [100, 250]}

    default = run_ranges(setup, capsys, "default", plain, *mode)
    global_range = run_ranges(
        setup, capsys, "global", plain, *mode, "--shade-range", "10,200"
    )
    by_entry = run_ranges(setup, capsys, "entry", entry, *mode)
    by_library = run_ranges(setup, capsys, "library", wide, *mode)
    shadowed = run_ranges(setup, capsys, "both", both, *mode)
    narrow = run_ranges(
        setup, capsys, "narrow", plain, *mode, "--shade-range", "100,250"
    )

    assert not np.array_equal(default, global_range)
    # The entry's range, else the library's, else the global one: each gives
    # what the same range as the global setting does.
    assert np.array_equal(by_entry, global_range)
    assert np.array_equal(by_library, global_range)
    assert np.array_equal(shadowed, narrow)
    # Alpha is the shading's invariant.
    assert np.array_equal(default[..., 3], by_entry[..., 3])


# Alpha and the geometry maps are the same whatever the shading

CHOICES = [
    ("--shade-mode", "brightness"),
    ("--shade-mode", "both", "--bake-key-strength", "0.7"),
    ("--shade-mode", "neither", "--bake-sky-strength", "0.5"),
    (
        "--shade-mode",
        "both",
        "--bake-ground-strength",
        "0.4",
        "--bake-sky-ground-frame",
        "world",
        "--shade-snap",
        "palette",
        "--dither-pattern",
        "ordered8",
    ),
    ("--shade-mode", "brightness", "--shade-snap", "ramp", "--no-ambient-form"),
]


@pytest.mark.parametrize("edges", ["hard", "soft"])
@pytest.mark.parametrize("reduce", ["plain", "mode"])
@pytest.mark.parametrize(
    "front",
    [None, {"colour": [200, 30, 30], "q": 0.5, "code": 1}],
    ids=["opaque", "translucent"],
)
def test_alpha_and_both_maps_are_the_same_whatever_the_shading(
    setup, capsys, tmp_path, edges, reduce, front
):
    config = {
        "pixels": "noise",
        "surfaces": "varied",
        "depths": [0.05],
        "code": 1,
    } | setup_materials(setup)
    if front is not None:
        config["front"] = front
    setup.configure(**config)
    common = ("--depth", "--no-preview", "--edges", edges, "--reduce", reduce)
    document = library(
        materials={"steel": {"uses": "metal"}, "glass": {"ordinary": True}}
    )

    def render(name, *options):
        out = tmp_path / name
        out.mkdir()
        go(
            setup,
            capsys,
            *common,
            *options,
            document=document,
            outfile=out / "hero.png",
        )
        return out

    base = render("base")
    base_png = colours(base / "hero.png")
    for index, choice in enumerate(CHOICES):
        out = render(f"choice{index}", *choice)
        png = colours(out / "hero.png")
        assert np.array_equal(png[..., 3], base_png[..., 3]), choice
        for suffix in (".normal.png", ".depth.png"):
            assert (out / f"hero{suffix}").read_bytes() == (
                base / f"hero{suffix}"
            ).read_bytes(), (choice, suffix)


def test_the_default_run_is_the_pre_arc_run_for_image_bytes(setup, capsys, tmp_path):
    # Default settings with and without the shading arguments the command now
    # always passes: the library's ramps are untouched.
    setup.configure(code=1, pixels="noise", **setup_materials(setup))
    document = library()
    first = tmp_path / "first"
    first.mkdir()
    go(setup, capsys, document=document, outfile=first / "hero.png")
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    go(
        setup,
        capsys,
        "--shade-mode",
        "ramp",
        "--bake-key-strength",
        "0",
        "--dither-pattern",
        "off",
        "--shade-snap",
        "off",
        document=document,
        outfile=explicit / "hero.png",
    )
    for name in ("hero.png", "hero.normal.png", "hero.walk.gif", "hero.attack.gif"):
        assert (first / name).read_bytes() == (explicit / name).read_bytes()
    assert (first / "hero.json").read_bytes() == (explicit / "hero.json").read_bytes()


# The preview light stays separate


def test_baking_never_requests_the_additional_preview_light(setup, capsys):
    go(setup, capsys, "--shade-mode", "brightness", "--bake-key-strength", "0.5")
    assert not any(path.name.startswith("hero-lit") for path in setup.out.iterdir())
    go(
        setup,
        capsys,
        "--shade-mode",
        "brightness",
        "--bake-key-strength",
        "0.5",
        "--light",
        "20,30,40",
    )
    lit = sorted(path.name for path in setup.out.iterdir() if "-lit." in path.name)
    assert lit == ["hero-lit.attack.gif", "hero-lit.walk.gif"]
    assert sheet_of(setup)["settings"]["light"]["position"] == [20.0, 30.0, 40.0]


# Warnings: only an option or a project file counts as explicit (D-41)

SHADOWING = library(
    shade={"dither": {"pattern": "ordered4"}},
    ramps={
        "metal": [1, 2, 3],
        "gold": {"base": "#ca9337", "bands": 4, "lightness_step": 0.2},
    },
    materials={
        "steel": {
            "uses": "metal",
            "shade": {"key": {"strength": 0.25}, "occlusion_weight": 0.5},
        },
        "cloth": {"ordinary": True, "shade": {"mode": "both", "ao_distance_m": 0.7}},
        "glass": {"uses": "gold"},
    },
)


def shadow_warnings(setup, capsys, *options):
    err = go(setup, capsys, "--no-preview", *options, document=SHADOWING)
    return [
        text
        for text in warnings_of(err)
        if "keeps its own" in text or "does not reach" in text
    ]


EXPLICIT = [
    ("--bake-key-strength", "0.3"),
    ("--shade-mode", "neither"),
    ("--occlusion-weight", "0.9"),
    ("--ao-distance", "0.45"),
    ("--dither-pattern", "ordered2"),
    ("--ramp-step", "0.15"),
]


@pytest.mark.parametrize("option", EXPLICIT, ids=lambda option: option[0])
def test_an_explicit_option_a_library_value_beats_warns(setup, capsys, option):
    warnings = shadow_warnings(setup, capsys, *option)
    assert len(warnings) == 1, warnings
    assert option[1] in warnings[0] or option[0] in warnings[0]


def test_the_warnings_name_the_value_the_entry_keeps_and_the_global_it_beats(
    setup, capsys
):
    warnings = shadow_warnings(
        setup, capsys, "--bake-key-strength", "0.3", "--shade-mode", "neither"
    )
    assert len(warnings) == 2
    by_key = next(text for text in warnings if "shade.key.strength" in text)
    assert by_key.startswith('material "steel" keeps its own shade.key.strength, 0.25')
    assert "the global 0.3 (--bake-key-strength) applies to materials" in by_key
    ordinary = next(text for text in warnings if "shade.mode" in text)
    assert ordinary.startswith('material "cloth" keeps its own shade.mode, "both"')
    assert "(--shade-mode)" in ordinary


def test_a_library_wide_response_value_a_global_option_cannot_reach_warns(
    setup, capsys
):
    warnings = shadow_warnings(setup, capsys, "--dither-pattern", "ordered2")
    assert len(warnings) == 1
    assert warnings[0].startswith("the material library gives shade.dither.pattern")
    assert "(--dither-pattern) does not reach them" in warnings[0]


def test_a_generated_ramps_own_formula_value_warns_for_an_explicit_global(
    setup, capsys
):
    warnings = shadow_warnings(setup, capsys, "--ramp-step", "0.15")
    assert warnings == [
        'ramp "gold" keeps its own lightness_step, 0.2, from the material '
        "library; the global 0.15 applies to generated ramps without their own"
    ]


def test_a_project_file_value_is_an_explicit_global_that_warns(setup, capsys):
    project_file(
        "shade:\n  key: {strength: 0.3}\n  occlusion_weight: 0.9\nramp: {lightness_step: 0.15}\n"
    )
    warnings = shadow_warnings(setup, capsys, "--project", "look")
    assert len(warnings) == 3
    assert any("shade.key.strength" in text for text in warnings)
    assert any("shade.occlusion_weight" in text for text in warnings)
    assert any("lightness_step" in text for text in warnings)
    text = next(text for text in warnings if "shade.key.strength" in text)
    assert "--project 'look'" in text and "line 2, column" in text


GLOBAL_TEXT = (
    "shade:\n  key: {strength: 0.3}\n  mode: neither\n  occlusion_weight: 0.9\n"
    "  ao_distance_m: 0.45\n  dither: {pattern: ordered2}\n"
    "ramp: {lightness_step: 0.15}\n"
)


def test_the_user_file_never_warns(setup, capsys):
    path = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros", "config.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(GLOBAL_TEXT)
    assert shadow_warnings(setup, capsys) == []
    assert shade_of(setup)["key"]["strength"] == 0.3


def test_a_config_file_replacing_the_user_file_never_warns(setup, capsys, tmp_path):
    path = tmp_path / "global.yaml"
    path.write_text(GLOBAL_TEXT)
    assert shadow_warnings(setup, capsys, "--config", str(path)) == []
    assert shade_of(setup)["mode"] == "neither"


def test_the_shipped_defaults_never_warn(setup, capsys):
    assert shadow_warnings(setup, capsys) == []


def test_a_reused_sheet_never_warns(setup, capsys, tmp_path):
    go(setup, capsys, "--no-preview", "--bake-key-strength", "0.3", document=SHADOWING)
    sheet = tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    err = go_reuse(setup, capsys, sheet)
    assert [text for text in warnings_of(err) if "keeps its own" in text] == []
    # Only a new explicit option after it warns, for that option alone.
    err = go_reuse(setup, capsys, sheet, "--bake-key-strength", "0.2")
    warnings = [text for text in warnings_of(err) if "keeps its own" in text]
    assert len(warnings) == 1 and "shade.key.strength" in warnings[0]


def go_reuse(setup, capsys, sheet, *options):
    status, _, err = run(
        capsys, setup.argv("--settings-from", str(sheet), "--no-preview", *options)
    )
    assert status == 0, err
    return err


def test_inheritance_and_inactive_terms_warn_nothing(setup, capsys):
    # No explicit global at all, and an explicit global no entry gives its own
    # value for, are not events.
    assert shadow_warnings(setup, capsys, "--bake-ground-strength", "0.1") == []
    assert shadow_warnings(setup, capsys, "--brightness-floor", "0.2") == []
    assert shadow_warnings(setup, capsys, "--bake-sky-ground-frame", "world") == []
    assert shadow_warnings(setup, capsys, "--shade-snap", "palette") == []


def test_the_old_libraries_warn_as_they_did(setup, capsys):
    document = {
        "schema": "moskophoros.materials/3",
        "ramps": {"metal": [1, 2, 3]},
        "shade": {"range": [10, 250]},
        "materials": {
            "steel": {"uses": "metal", "shade": {"occlusion_weight": 0.5}},
        },
    }
    err = go(
        setup,
        capsys,
        "--no-preview",
        "--occlusion-weight",
        "0.9",
        "--shade-range",
        "20,200",
        document=document,
    )
    warnings = [
        text
        for text in warnings_of(err)
        if "keeps its own" in text or "does not reach" in text
    ]
    assert warnings == [
        'material "steel" keeps its own shade.occlusion_weight, 0.5, from the '
        "material library; the global 0.9 applies to materials without their own",
        "the material library gives shade.range [10, 250] to its materials "
        "without their own; the global [20, 200] does not reach them",
    ]
