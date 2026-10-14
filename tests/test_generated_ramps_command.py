"""Generated ramps through the command, with a fake Blender: the sheet's
records, refusals before Blender, warnings, the unchanged capture job,
generated ramps rendering as listed ones, and reuse without regeneration
(material styling design D-28 to D-36; design §Stylize, §Export, Reuse)."""

import json
import os
from pathlib import Path

import pytest
from test_command import Setup, run
from test_materials_command import (
    COLORS,
    HERO_MATERIALS,
    forbid_blender,
    library_file,
    named_hero,
    palette_file,
)

from moskophoros import materials, ramps

GOLD = {"base": "#CA9337", "bands": 4}
B_FORMULA = (0.12, -12.0, 0.3)


def rgb(text):
    return tuple(int(text[i : i + 2], 16) for i in (1, 3, 5))


def generated(base, bands, step=0.12, hue=-12.0, fade=0.3):
    return list(ramps.generate(rgb(base), bands, step, hue, fade, COLORS))


@pytest.fixture
def setup(tmp_path):
    hero = Setup(tmp_path)
    named_hero(hero, HERO_MATERIALS)
    hero.configure(
        materials=[{"id": k + 1, "material": k} for k in range(4)]
        + [{"id": 65535, "material": None}],
        code=1,
        pixels="solid",
    )
    return hero


def document(**changes):
    library = {
        "schema": materials.SCHEMA,
        "ramps": {"metal": [1, 2, 3], "gold": dict(GOLD)},
        "default": "gold",
        "materials": {
            "steel": {"uses": "gold"},
            "cloth": {"ramp": {"base": "#7a3b2e", "bands": 3, "hue_shift_deg": -35}},
        },
    }
    for key, value in changes.items():
        if value is None:
            library.pop(key)
        else:
            library[key] = value
    return library


def argv(setup, *options, library=None, name="materials.yaml"):
    return setup.argv(
        "--palette",
        str(palette_file(setup.tmp_path)),
        "--materials",
        str(
            library_file(
                setup.tmp_path, document() if library is None else library, name
            )
        ),
        *options,
    )


def ok(capsys, arguments):
    status, _, err = run(capsys, arguments)
    assert status == 0, err
    return err


def recorded(setup):
    return json.loads(setup.json.read_text())


# The sheet's records (D-33, D-34, D-35)


def test_the_sheet_records_generated_ramps_and_the_library_shade(setup, capsys):
    library = document(shade={"range": [190, 225]})
    ok(capsys, argv(setup, "--no-preview", library=library))
    sheet = recorded(setup)
    keys = list(sheet["settings"])
    assert keys[keys.index("shade") + 1 : keys.index("shade") + 3] == ["ramp", "style"]
    assert sheet["settings"]["ramp"] == {
        "lightness_step": 0.12,
        "hue_shift_deg": -12.0,
        "chroma_fade": 0.3,
    }
    record = sheet["settings"]["style"]["materials"]
    assert list(record) == [
        "source",
        "sha256",
        "ramps",
        "default",
        "shade",
        "materials",
    ]
    assert record["shade"] == {"range": [190, 225]}
    assert record["ramps"]["metal"] == [1, 2, 3]
    gold = record["ramps"]["gold"]
    assert list(gold) == ["base", "bands", "indices"]
    assert gold == {"base": "#ca9337", "bands": 4, "indices": generated("#ca9337", 4)}
    cloth = record["materials"]["cloth"]["ramp"]
    assert list(cloth) == ["base", "bands", "hue_shift_deg", "indices"]
    assert cloth["indices"] == generated("#7a3b2e", 3, hue=-35.0)


def test_own_formula_values_are_recorded_in_their_fixed_order(setup, capsys):
    ramp = {"chroma_fade": 0.6, "hue_shift_deg": -35, "lightness_step": 0.09}
    library = document(ramps={"gold": GOLD | ramp}, materials={})
    ok(capsys, argv(setup, "--no-preview", library=library))
    gold = recorded(setup)["settings"]["style"]["materials"]["ramps"]["gold"]
    assert list(gold) == [
        "base",
        "bands",
        "lightness_step",
        "hue_shift_deg",
        "chroma_fade",
        "indices",
    ]
    assert gold["indices"] == generated("#ca9337", 4, 0.09, -35.0, 0.6)


def test_a_library_without_a_shade_records_none(setup, capsys):
    ok(capsys, argv(setup, "--no-preview"))
    assert "shade" not in recorded(setup)["settings"]["style"]["materials"]


# Refusals before Blender (D-34, D-36)


@pytest.mark.parametrize(
    ("library", "problem"),
    [
        (
            document(schema=materials.LEGACY_SCHEMA),
            'ramps["gold"]: a generated ramp needs schema',
        ),
        (
            document(ramps={"gold": {"base": "red", "bands": 4}}),
            'ramps["gold"].base: expected an sRGB #rrggbb, got "red"',
        ),
        (
            document(ramps={"gold": GOLD | {"hue_shift_deg": 200}}),
            'ramps["gold"].hue_shift_deg: expected a finite number from -180 to 180',
        ),
        (
            document(shade={"occlusion_weight": 0.5}),
            "shade.occlusion_weight: a library's own shade gives only range",
        ),
        (
            document(
                schema=materials.LEGACY_SCHEMA,
                ramps={"m": [1]},
                default=None,
                materials={},
                shade={"range": [1, 2]},
            ),
            "shade: a library's own shade needs schema",
        ),
    ],
)
def test_library_errors_are_exit_2_before_blender_naming_file_and_ramp(
    setup, capsys, monkeypatch, library, problem
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, argv(setup, library=library))
    assert status == 2
    assert "materials.yaml" in err and problem in err


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--ramp-step", "1.5", "must be from 0 to 1"),
        ("--ramp-step", "nan", "expected a finite number"),
        ("--ramp-hue-shift", "-181", "must be from -180 to 180"),
        ("--ramp-fade", "-0.1", "must be from 0 to 1"),
    ],
)
def test_ramp_options_are_checked_before_blender(
    setup, capsys, monkeypatch, option, value, message
):
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, argv(setup, option, value))
    assert status == 2 and f"argument {option}: {message}" in err


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            "ramp: {lightness_step: 2}",
            "ramp.lightness_step: expected a finite number from 0 to 1",
        ),
        ("ramp: {hue_shift_deg: true}", "ramp.hue_shift_deg: expected a number"),
        (
            "ramp: {chroma_fade: -1}",
            "ramp.chroma_fade: expected a finite number from 0 to 1",
        ),
        ("ramp: {bands: 4}", "ramp.bands: unknown key"),
    ],
)
def test_ramp_settings_errors_name_the_file_key_and_line(
    setup, capsys, monkeypatch, tmp_path, text, message
):
    path = tmp_path / "bad.yaml"
    path.write_text("version: 1\n" + text + "\n")
    forbid_blender(monkeypatch)
    status, _, err = run(capsys, argv(setup, "--config", str(path)))
    assert status == 2
    assert f"--config {str(path)!r}: {message}" in err and "line 2" in err


# Warnings (D-33, D-35; settings design D-23)


def test_an_explicit_global_losing_to_a_ramp_s_own_value_warns(setup, capsys):
    setup.configure(
        materials=[{"id": k + 1, "material": k} for k in range(4)]
        + [{"id": 65535, "material": None}],
        code=2,
        pixels="solid",
    )
    err = ok(capsys, argv(setup, "--no-preview", "--ramp-hue-shift", "-20"))
    assert (
        'moskophoros: warning: material "cloth"\'s own ramp keeps its own '
        "hue_shift_deg, -35.0, from the material library; the global -20.0 "
        "applies to generated ramps without their own"
    ) in err


def test_ramp_globals_from_the_user_file_or_defaults_warn_nothing(
    setup, capsys, tmp_path
):
    home = Path(os.environ["XDG_CONFIG_HOME"]) / "moskophoros"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text("ramp: {hue_shift_deg: -20}\n")
    err = ok(capsys, argv(setup, "--no-preview"))
    assert "keeps its own" not in err


def test_an_explicit_range_losing_to_the_library_s_warns_once(setup, capsys):
    library = document(shade={"range": [190, 225]})
    err = ok(
        capsys, argv(setup, "--no-preview", "--shade-range", "84,191", library=library)
    )
    assert err.count("the material library gives shade.range [190, 225]") == 1
    assert "keeps its own" not in err
    assert "the material library gives" not in ok(
        capsys, argv(setup, "--no-preview", library=library)
    )


# The capture job is unchanged (D-36)


def job(setup, capsys, library, name):
    work = setup.tmp_path / f"work-{name}"
    ok(
        capsys,
        argv(
            setup,
            "--no-preview",
            "--work-dir",
            str(work),
            library=library,
            name=f"{name}.yaml",
        ),
    )
    return (work / "render" / "job.json").read_text().replace(str(work), "W")


def test_the_capture_job_is_the_same_whatever_the_library_shade_and_default(
    setup, capsys
):
    base = job(setup, capsys, document(), "plain")
    assert job(setup, capsys, document(shade={"range": [190, 225]}), "shaded") == base
    assert job(setup, capsys, document(default=None), "nodefault") == base
    listed = document(ramps={"metal": [1, 2, 3], "gold": [4, 5, 6, 7]})
    assert job(setup, capsys, listed, "listed") == base


# Generated renders as listed (D-12, D-33)


@pytest.mark.parametrize("reduce", ["plain", "mode"])
def test_a_generated_ramp_renders_exactly_as_a_listed_ramp_of_its_indices(
    setup, capsys, reduce
):
    # Six bands over the eight-colour palette: some indices repeat, which
    # mode pools.
    ramp = {"base": "#a0c040", "bands": 6, "lightness_step": 0.05, "chroma_fade": 0.0}
    indices = generated("#a0c040", 6, 0.05, -12.0, 0.0)
    assert len(set(indices)) < len(indices)
    outputs = []
    for name, value in (("generated", ramp), ("listed", indices)):
        library = document(ramps={"gold": value}, materials={"steel": {"uses": "gold"}})
        ok(
            capsys,
            argv(setup, "--reduce", reduce, library=library, name=f"{name}.yaml"),
        )
        listing = setup.listing()
        outputs.append(
            {key: data for key, data in listing.items() if key != "hero.json"}
        )
    assert outputs[0] == outputs[1]


# Old output preserved (requirement 10)


LISTED_2 = {
    "schema": materials.LEGACY_SCHEMA,
    "ramps": {"metal": [1, 2, 3], "cloth": [4, 5]},
    "default": "cloth",
    "materials": {"steel": {"uses": "metal", "shade": {"occlusion_weight": 0.5}}},
}


@pytest.mark.parametrize("reduce", ["plain", "mode"])
def test_the_ramp_settings_change_nothing_for_a_listed_library(setup, capsys, reduce):
    work_b, work_c = setup.tmp_path / "work-b", setup.tmp_path / "work-c"
    ok(
        capsys,
        argv(setup, "--reduce", reduce, "--work-dir", str(work_b), library=LISTED_2),
    )
    before = setup.listing()
    ok(
        capsys,
        argv(
            setup,
            "--reduce",
            reduce,
            "--work-dir",
            str(work_c),
            *["--ramp-step", "0.09", "--ramp-hue-shift", "-35", "--ramp-fade", "0.6"],
            library=LISTED_2,
        ),
    )
    after = setup.listing()
    for name in before:
        if name != "hero.json":
            assert after[name] == before[name], name
    a, b = json.loads(before["hero.json"]), json.loads(after["hero.json"])
    assert {k for k in a if a[k] != b[k]} == {"settings", "fingerprint"}
    assert {k for k in a["settings"] if a["settings"][k] != b["settings"][k]} == {
        "ramp"
    }
    jobs = [
        (work / "render" / "job.json").read_text().replace(str(work), "W")
        for work in (work_b, work_c)
    ]
    assert jobs[0] == jobs[1]


@pytest.mark.parametrize("reduce", ["plain", "mode"])
def test_a_listed_3_library_without_a_shade_renders_as_its_2(setup, capsys, reduce):
    ok(capsys, argv(setup, "--reduce", reduce, library=LISTED_2, name="two.yaml"))
    two = setup.listing()
    current = LISTED_2 | {"schema": materials.SCHEMA}
    ok(capsys, argv(setup, "--reduce", reduce, library=current, name="two.yaml"))
    three = setup.listing()
    for name in two:
        if name != "hero.json":
            assert three[name] == two[name], name
    a, b = json.loads(two["hero.json"]), json.loads(three["hero.json"])
    # The library's bytes changed with its schema line, so its digest did.
    assert {k for k in a if a[k] != b[k]} == {"settings", "fingerprint"}
    style_a, style_b = (
        a["settings"]["style"]["materials"],
        b["settings"]["style"]["materials"],
    )
    assert {k for k in style_a if style_a[k] != style_b[k]} == {"sha256"}


# Reuse without regeneration (D-33, requirement 9)


def reload(setup, sheet, *options):
    return [
        "--settings-from",
        str(sheet),
        "--no-user-config",
        *options,
        "--blender",
        str(setup.fake),
        str(setup.model),
        str(setup.png),
    ]


def sheet_from_a_run(setup, capsys, library=None):
    ok(capsys, argv(setup, library=library))
    sheet = setup.tmp_path / "recorded.json"
    sheet.write_bytes(setup.json.read_bytes())
    return sheet


@pytest.fixture
def counted(monkeypatch):
    """Every generation, as the base colours generated."""
    calls = []
    real = ramps.generate

    def counting(base, bands, *rest):
        calls.append("#" + bytes(base).hex())
        return real(base, bands, *rest)

    monkeypatch.setattr(ramps, "generate", counting)
    return calls


def test_reloading_reproduces_the_sheet_without_regenerating(setup, capsys, counted):
    sheet = sheet_from_a_run(setup, capsys)
    first = setup.listing()
    counted.clear()
    for name in list(first):
        (setup.out / name).unlink()
    ok(capsys, reload(setup, sheet))
    assert setup.listing() == first
    assert counted == []


@pytest.mark.parametrize("how", ["option", "config"])
def test_an_explicit_change_regenerates_only_the_ramps_it_reaches(
    setup, capsys, counted, tmp_path, how
):
    sheet = sheet_from_a_run(setup, capsys)
    counted.clear()
    if how == "option":
        extra = ["--ramp-hue-shift", "-20"]
    else:
        path = tmp_path / "hue.yaml"
        path.write_text("ramp: {hue_shift_deg: -20}\n")
        extra = ["--config", str(path)]
    ok(capsys, reload(setup, sheet, *extra))
    # gold takes the global; cloth's own -35 shadows it, so it is kept.
    assert counted == ["#ca9337"]
    record = recorded(setup)["settings"]["style"]["materials"]
    assert record["ramps"]["gold"]["indices"] == generated("#ca9337", 4, hue=-20.0)
    before = json.loads(sheet.read_text())["settings"]["style"]["materials"]
    assert record["materials"]["cloth"] == before["materials"]["cloth"]
    assert recorded(setup)["settings"]["ramp"]["hue_shift_deg"] == -20.0


def test_an_explicit_value_equal_to_the_recorded_one_regenerates_nothing(
    setup, capsys, counted
):
    sheet = sheet_from_a_run(setup, capsys)
    counted.clear()
    ok(capsys, reload(setup, sheet, "--ramp-hue-shift", "-12", "--ramp-step", "0.12"))
    assert counted == []


def test_a_material_s_own_ramp_regenerates_when_its_inputs_change(
    setup, capsys, counted
):
    sheet = sheet_from_a_run(setup, capsys)
    counted.clear()
    ok(capsys, reload(setup, sheet, "--ramp-fade", "0.5"))
    assert sorted(counted) == ["#7a3b2e", "#ca9337"]


def test_the_user_file_never_regenerates_a_loaded_sheet_s_ramps(setup, capsys, counted):
    sheet = sheet_from_a_run(setup, capsys)
    counted.clear()
    home = Path(os.environ["XDG_CONFIG_HOME"]) / "moskophoros"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text("ramp: {hue_shift_deg: -20, chroma_fade: 0.6}\n")
    arguments = reload(setup, sheet)
    arguments.remove("--no-user-config")
    ok(capsys, arguments)
    assert counted == []
    assert recorded(setup)["settings"]["ramp"]["hue_shift_deg"] == -12.0


def test_malformed_recorded_indices_are_refused_without_regenerating(
    setup, capsys, monkeypatch, counted
):
    sheet = sheet_from_a_run(setup, capsys)
    document_ = json.loads(sheet.read_text())
    document_["settings"]["style"]["materials"]["ramps"]["gold"]["indices"] = [1, 2]
    sheet.write_text(json.dumps(document_))
    counted.clear()
    forbid_blender(monkeypatch)
    for extra in ((), ("--no-materials",)):
        status, _, err = run(capsys, reload(setup, sheet, *extra))
        assert status == 2
        assert 'settings.style.materials: ramps["gold"].indices: has 2 entries' in err
    assert counted == []
