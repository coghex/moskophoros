"""Each material's own shading values in the command (settings design D-9,
D-20, D-22, D-23, D-29, D-36 and D-37), with a controlled fake Blender."""

import json
import os
from pathlib import Path

import pytest
import yaml
from test_command import Setup, run
from test_materials_command import (
    COLORS,
    HERO_MATERIALS,
    forbid_blender,
    library_file,
    library_with,
    materialed,
    named_hero,
    palette_file,
    recorded,
    warnings_of,
)
from test_reuse import edited, write_sheet

from moskophoros import cli

# Steel overrides two capture values and the range; cloth only the range.
OVERRIDES = {
    "schema": "moskophoros.materials/2",
    "ramps": {"metal": [1, 2, 3], "cloth": [4, 5]},
    "materials": {
        "steel": {
            "uses": "metal",
            "shade": {
                "range": [100, 200],
                "convexity_weight": 0.5,
                "ao_distance_m": 1.5,
            },
        },
        "cloth": {"uses": "cloth", "shade": {"range": [10, 250]}},
        "glass": {"ramp": [6], "shade": {"occlusion_weight": 0.9}},
    },
}


@pytest.fixture
def setup(tmp_path):
    hero = Setup(tmp_path)
    named_hero(hero, HERO_MATERIALS)
    return hero


def job_shade(work, mode="render"):
    return json.loads((work / mode / "job.json").read_text())["settings"]["shade"]


def run_in(setup, capsys, work, *options, library=OVERRIDES):
    argv = materialed(
        setup, "--no-preview", "--work-dir", str(work), *options, library=library
    )
    status, _, err = run(capsys, argv)
    assert status == 0, err
    return err


# Capture: each material's own values in the job (D-9, D-36)


def test_the_job_carries_each_overriding_materials_capture_values(setup, capsys):
    work = setup.tmp_path / "work"
    run_in(setup, capsys, work)
    for mode in ("measure", "render"):
        shade = job_shade(work, mode)
        # Steel is glTF material 0. Cloth overrides only the range, which acts
        # in stylize; glass is translucent and takes the ordinary look.
        assert shade["materials"] == [
            {
                "material": 0,
                "ao_distance_m": 1.5,
                "occlusion_weight": 0.25,
                "convexity_weight": 0.5,
            }
        ]
        assert shade["ao_distance_m"] == 0.3 and shade["convexity_weight"] == 1.0


@pytest.mark.parametrize(
    "layer", ["option", "config", "user", "sheet"], ids=lambda layer: layer
)
def test_a_materials_own_value_beats_a_global_from_every_layer(setup, capsys, layer):
    work = setup.tmp_path / "work"
    options = []
    if layer == "option":
        options = ["--convexity-weight", "0", "--occlusion-weight", "0.7"]
    elif layer == "config":
        path = setup.tmp_path / "look.yaml"
        path.write_text("shade: {convexity_weight: 0, occlusion_weight: 0.7}\n")
        options = ["--config", str(path)]
    elif layer == "user":
        path = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros", "config.yaml")
        path.parent.mkdir(parents=True)
        path.write_text("shade: {convexity_weight: 0, occlusion_weight: 0.7}\n")
    if layer == "sheet":
        sheet = recorded(
            setup,
            capsys,
            "--convexity-weight",
            "0",
            "--occlusion-weight",
            "0.7",
            library=OVERRIDES,
        )
        argv = setup.argv(
            "--settings-from", str(sheet), "--no-preview", "--work-dir", str(work)
        )
        assert run(capsys, argv)[0] == 0
    else:
        run_in(setup, capsys, work, *options)
    shade = job_shade(work)
    assert (shade["convexity_weight"], shade["occlusion_weight"]) == (0.0, 0.7)
    # Steel keeps its convexity weight and takes the global occlusion weight.
    assert shade["materials"] == [
        {
            "material": 0,
            "ao_distance_m": 1.5,
            "occlusion_weight": 0.7,
            "convexity_weight": 0.5,
        }
    ]


@pytest.mark.parametrize(
    "change",
    [
        lambda document: document["ramps"].update(metal=[3, 2, 1]),
        lambda document: document.update(default="cloth"),
        lambda document: document["materials"]["cloth"]["shade"].update(range=[0, 5]),
        lambda document: document["materials"]["steel"]["shade"].update(range=[5, 9]),
        lambda document: document["materials"].update(other={"ramp": [7]}),
    ],
    ids=["ramps", "default", "a range", "an overriding material's range", "an entry"],
)
def test_the_job_ignores_the_rest_of_the_style(setup, capsys, change):
    """The job holds each material's capture values and nothing else from the
    style (D-36): not the ramps, the palette, the reduction, the shade range
    or the default."""

    def jobs(name, *options, library=OVERRIDES):
        work = setup.tmp_path / name
        run_in(setup, capsys, work, *options, library=library)
        return {
            mode: (work / mode / "job.json").read_text().replace(str(work), "W")
            for mode in ("measure", "render")
        }

    base = jobs("base")
    changed = json.loads(json.dumps(OVERRIDES))
    change(changed)
    assert jobs("library", library=changed) == base
    assert jobs("reduce", "--reduce", "mode") == base
    assert jobs("range", "--shade-range", "50,60") == base
    other = palette_file(setup.tmp_path, COLORS[::-1], name="other.hex")
    work = setup.tmp_path / "palette"
    argv = setup.argv(
        "--palette",
        str(other),
        "--materials",
        str(library_file(setup.tmp_path, OVERRIDES)),
        "--no-preview",
        "--work-dir",
        str(work),
    )
    assert run(capsys, argv)[0] == 0
    assert {
        mode: (work / mode / "job.json").read_text().replace(str(work), "W")
        for mode in ("measure", "render")
    } == base


def test_a_library_without_overrides_leaves_the_job_as_without_one(setup, capsys):
    plain = setup.tmp_path / "plain"
    assert run(capsys, setup.argv("--no-preview", "--work-dir", str(plain)))[0] == 0
    work = setup.tmp_path / "work"
    run_in(setup, capsys, work, library=library_with())
    assert job_shade(work) == job_shade(plain)
    assert job_shade(work)["materials"] == []


# The warning (D-23)


def overriding_warnings(err):
    return [line for line in warnings_of(err) if "keeps its own" in line]


@pytest.mark.parametrize("how", ["option", "config"])
def test_an_explicit_global_a_material_overrides_warns(setup, capsys, how):
    if how == "option":
        options = ["--convexity-weight", "0", "--shade-range", "84,191"]
    else:
        path = setup.tmp_path / "look.yaml"
        path.write_text("shade: {convexity_weight: 0, range: [84, 191]}\n")
        options = ["--config", str(path)]
    err = run_in(setup, capsys, setup.tmp_path / "work", *options)
    assert overriding_warnings(err) == [
        'material "steel" keeps its own shade.convexity_weight, 0.5, from the '
        "material library; the global 0.0 applies to materials without their own",
        'material "steel" keeps its own shade.range, [100, 200], from the material '
        "library; the global [84, 191] applies to materials without their own",
        'material "cloth" keeps its own shade.range, [10, 250], from the material '
        "library; the global [84, 191] applies to materials without their own",
    ]


@pytest.mark.parametrize("layer", ["defaults", "user", "sheet"])
def test_a_global_from_the_defaults_the_user_file_or_a_sheet_warns_nothing(
    setup, capsys, layer
):
    work = setup.tmp_path / "work"
    if layer == "defaults":
        err = run_in(setup, capsys, work)
    elif layer == "user":
        path = Path(os.environ["XDG_CONFIG_HOME"], "moskophoros", "config.yaml")
        path.parent.mkdir(parents=True)
        path.write_text("shade: {convexity_weight: 0, range: [84, 191]}\n")
        err = run_in(setup, capsys, work)
    else:
        sheet = recorded(setup, capsys, "--convexity-weight", "0", library=OVERRIDES)
        status, _, err = run(
            capsys,
            setup.argv(
                "--settings-from", str(sheet), "--no-preview", "--work-dir", str(work)
            ),
        )
        assert status == 0
    assert overriding_warnings(err) == []


def test_the_output_does_not_change_with_the_warning(setup, capsys):
    run_in(setup, capsys, setup.tmp_path / "a", "--convexity-weight", "1.0")
    warned = setup.png.read_bytes(), json.loads(setup.json.read_text())["fingerprint"]
    run_in(setup, capsys, setup.tmp_path / "b")
    quiet = setup.png.read_bytes(), json.loads(setup.json.read_text())["fingerprint"]
    assert warned == quiet


# The inline record (D-37) and reloading


def test_the_inline_record_keeps_each_entrys_values_in_a_fixed_order(setup, capsys):
    run_in(setup, capsys, setup.tmp_path / "work")
    entries = json.loads(setup.json.read_text())["settings"]["style"]["materials"][
        "materials"
    ]
    assert entries == {
        "cloth": {"uses": "cloth", "shade": {"range": [10, 250]}},
        "glass": {"ramp": [6], "shade": {"occlusion_weight": 0.9}},
        "steel": {
            "uses": "metal",
            "shade": {
                "ao_distance_m": 1.5,
                "convexity_weight": 0.5,
                "range": [100, 200],
            },
        },
    }
    assert [list(entry) for entry in entries.values()] == [
        ["uses", "shade"],
        ["ramp", "shade"],
        ["uses", "shade"],
    ]
    assert list(entries["steel"]["shade"]) == [
        "ao_distance_m",
        "convexity_weight",
        "range",
    ]


def test_the_record_does_not_depend_on_the_files_key_order(setup, capsys):
    run_in(setup, capsys, setup.tmp_path / "a")
    first = setup.json.read_text()
    shuffled = json.loads(json.dumps(OVERRIDES))
    steel = shuffled["materials"]["steel"]
    shuffled["materials"]["steel"] = {
        "shade": dict(reversed(steel["shade"].items())),
        "uses": steel["uses"],
    }
    run_in(setup, capsys, setup.tmp_path / "b", library=shuffled)
    assert (
        json.loads(setup.json.read_text())["settings"] == json.loads(first)["settings"]
    )


def test_an_entry_without_overrides_records_no_shade(setup, capsys):
    run_in(setup, capsys, setup.tmp_path / "work", library=library_with())
    entries = json.loads(setup.json.read_text())["settings"]["style"]["materials"][
        "materials"
    ]
    assert all("shade" not in entry for entry in entries.values())


def test_a_reused_sheet_restores_the_overrides_without_the_files(setup, capsys):
    sheet = recorded(setup, capsys, library=OVERRIDES)
    original = setup.png.read_bytes()
    (setup.tmp_path / "materials.yaml").unlink()
    (setup.tmp_path / "palette.hex").unlink()
    work = setup.tmp_path / "again-work"
    again = setup.out / "again.png"
    argv = setup.argv(
        "--settings-from",
        str(sheet),
        "--no-preview",
        "--work-dir",
        str(work),
        outfile=again,
    )
    assert run(capsys, argv)[0] == 0
    assert again.read_bytes() == original
    assert job_shade(work)["materials"][0]["convexity_weight"] == 0.5
    reused = json.loads((setup.out / "again.json").read_text())
    assert reused["settings"] == json.loads(sheet.read_text())["settings"]


GOOD_RECORD = {
    "source": "materials.yaml",
    "sha256": "ab" * 32,
    "ramps": {"metal": [1, 2, 3]},
    "default": None,
    "materials": {"steel": {"uses": "metal", "shade": {"range": [10, 20]}}},
}
PALETTE_RECORD = {
    "source": "palette.hex",
    "sha256": "cd" * 32,
    "colors": ["#" + bytes(color).hex() for color in COLORS],
}


@pytest.mark.parametrize(
    ("shade", "problem"),
    [
        ({"range": [20, 10]}, 'materials["steel"].shade.range: expected [lo, hi]'),
        ({"range": [True, 10]}, 'materials["steel"].shade.range: expected [lo, hi]'),
        ({"ao_distance_m": 0}, 'materials["steel"].shade.ao_distance_m: expected a'),
        ({"occlusion_weight": "1"}, 'materials["steel"].shade.occlusion_weight'),
        ({"convexity_weight": False}, 'materials["steel"].shade.convexity_weight'),
        ({"ao_samples": 8}, "AO samples is a global setting only"),
        ({"gloss": 1}, 'materials["steel"].shade: unknown field "gloss"'),
        ([1], 'materials["steel"].shade: expected a mapping'),
    ],
)
@pytest.mark.parametrize(
    "options", [(), ("--no-materials",), ("--materials", "REPLACEMENT")]
)
def test_a_malformed_inline_override_is_an_error_whatever_overrides_the_library(
    tmp_path, capsys, shade, problem, options
):
    record = json.loads(json.dumps(GOOD_RECORD))
    record["materials"]["steel"]["shade"] = shade
    style = {"reduce": "plain", "palette": PALETTE_RECORD, "materials": record}
    sheet = write_sheet(tmp_path, edited({"style": style}))
    options = [
        str(library_file(tmp_path, library_with()))
        if option == "REPLACEMENT"
        else option
        for option in options
    ]
    with pytest.raises(cli.UsageError):
        cli.resolve_settings(
            cli.parse_args(
                [
                    "--settings-from",
                    str(sheet),
                    "--no-user-config",
                    *options,
                    "m.glb",
                    "o.png",
                ]
            )
        )
    err = capsys.readouterr().err
    assert "settings.style.materials: " in err and problem in err


# Refusals before Blender


@pytest.mark.parametrize(
    ("library", "problem"),
    [
        (
            library_with(schema="moskophoros.materials/1"),
            'schema: "moskophoros.materials/1" libraries no longer load; change the '
            'schema line to "moskophoros.materials/2"',
        ),
        (
            library_with(
                materials={"steel": {"uses": "metal", "shade": {"ao_samples": 8}}}
            ),
            "AO samples is a global setting only",
        ),
        (
            library_with(
                materials={"steel": {"uses": "metal", "shade": {"range": [9, 1]}}}
            ),
            'materials["steel"].shade.range: expected [lo, hi]',
        ),
        (
            library_with(
                materials={"steel": {"uses": "metal", "shade": {"ao_distance_m": -1}}}
            ),
            'materials["steel"].shade.ao_distance_m',
        ),
        (
            library_with(materials={"steel": {"uses": "metal", "shade": {"shine": 1}}}),
            'materials["steel"].shade: unknown field "shine"',
        ),
    ],
    ids=["version 1", "ao samples", "range", "distance", "unknown key"],
)
def test_every_override_error_is_exit_2_before_any_blender_invocation(
    setup, capsys, monkeypatch, library, problem
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, materialed(setup, library=library))
    assert status == 2
    assert "materials.yaml" in err and problem in err
    assert setup.calls() == []


def test_a_library_yaml_with_overrides_round_trips_through_the_reader(tmp_path):
    path = tmp_path / "lib.yaml"
    path.write_text(yaml.safe_dump(OVERRIDES))
    options = cli.resolve_settings(
        cli.parse_args(
            [
                "--no-user-config",
                "--palette",
                str(palette_file(tmp_path)),
                "--materials",
                str(path),
                "m.glb",
                "o.png",
            ]
        )
    )
    steel = options.materials.library.materials["steel"]
    assert steel.shade.given() == (
        ("ao_distance_m", 1.5),
        ("convexity_weight", 0.5),
        ("range", (100, 200)),
    )
