"""Generated ramps: the formula, its numerical reference and the owner's
reference vectors, the `/3` library reader, and how ramps, formula values
and shade ranges resolve (material styling design D-28 to D-36). Pure tests;
see test_generated_ramps_command for the command."""

import math

import pytest
import yaml

from moskophoros import materials, ramps, stylize
from moskophoros.gltf import PrimitiveMaterial
from moskophoros.materials import Generated, LibraryError, validate_library

# The Vince 144 palette, 144 colours in file order, as hex (the owner's
# vince-144.gpl, copied as literal data: no file outside the repository
# is read).
VINCE_144_HEX = (
    "1c151c3b2233682c409e3535b65f33b99346bdbd6acadfa0f2fcedc3cbb4a2a28594876b"
    "8c6d5d7c5757553f46332a301c15173b24225739246a5822757d227ba54087ca70a5e7ab"
    "edfcf4bad2bc95ad8d7685605d603f534c39473c34332b2a1c19152d2a1a3d431c41631f"
    "35882443ad5570ca9da3e3d9edfafcb7cfcb8dad9d658b6b4a6844414d35343728272620"
    "1a1c15222d1a22481e21663224875e41a89f7ac3dbc2d9f9edeffcd4dce799b3bc628784"
    "44675937503d2d3b2b232720151c151a2e211e47392063632d7ea76897f3b2b2f6ded0f9"
    "f7edfce2ddecc8c8e094a5c7547180354e4e2b3a35202823151c1a1b2d2f264357405699"
    "6d61f0b081f3e1a1f6f9c7f5fcedf6e9d7e8d3bcdbb6a5cf938fc25c647d364047212829"
    "15191c24293f41357a753dacb93dd2ed61d6f69dcaf9cbd3fcf0edeadadddab9cac08eb8"
    "996da27561884f4b642d2e3617151c33243e602a6595317cd13d7bed717cf0a78ff4d3a5"
    "fcfbeddbcfbed1b7aec5999da26c8375516c503d52322c360d0d0d191919262626333333"
    "4040404f4f4f5d5d5d6d6d6d7c7c7c8c8c8c9c9c9cadadadbebebecfcfcfe0e0e0f2f2f2"
)
# The ten sample materials the owner reviewed (material styling design D-30,
# D-33): base, band count, and the indices settings B and C give on Vince
# 144, copied as literal data from ramp-gen/samples.json.
SAMPLES = [
    ("gold", "#ca9337", 4, [18, 19, 4, 5], [110, 13, 4, 5]),
    ("steel", "#8c939c", 4, [111, 133, 135, 137], [132, 134, 136, 137]),
    ("wood", "#8b5a2b", 4, [128, 17, 18, 19], [0, 1, 14, 19]),
    ("leather", "#6b4226", 4, [128, 16, 17, 29], [128, 0, 17, 29]),
    ("cloth", "#a83232", 4, [128, 1, 2, 3], [112, 113, 2, 3]),
    ("skin", "#e0ac8a", 4, [14, 12, 11, 118], [93, 124, 123, 118]),
    ("leaf", "#4f8a3a", 4, [48, 34, 35, 36], [17, 18, 19, 36]),
    ("stone", "#8a8478", 4, [47, 30, 134, 11], [30, 133, 135, 11]),
    ("grey", "#adadad", 5, [130, 132, 135, 137, 139], [132, 134, 136, 137, 139]),
    ("black", "#404040", 3, [128, 130, 132], [112, 130, 132]),
]
VINCE_144 = [
    tuple(int(VINCE_144_HEX[i + j : i + j + 2], 16) for j in (0, 2, 4))
    for i in range(0, len(VINCE_144_HEX), 6)
]
B = {"lightness_step": 0.12, "hue_shift_deg": -12.0, "chroma_fade": 0.3}
C = {"lightness_step": 0.09, "hue_shift_deg": -35.0, "chroma_fade": 0.6}


def rgb(text):
    return tuple(int(text[i : i + 2], 16) for i in (1, 3, 5))


def lch(shade):
    lightness, a, b = shade
    return lightness, math.hypot(a, b), math.degrees(math.atan2(b, a))


# The formula (D-28, D-33)


def test_the_palette_is_vince_144():
    assert len(VINCE_144) == 144 and len(set(VINCE_144)) == 144


@pytest.mark.parametrize(
    ("key", "base", "bands", "b", "c"), SAMPLES, ids=[s[0] for s in SAMPLES]
)
def test_the_owner_s_reference_vectors(key, base, bands, b, c):
    assert list(ramps.generate(rgb(base), bands, *B.values(), VINCE_144)) == b
    assert list(ramps.generate(rgb(base), bands, *C.values(), VINCE_144)) == c


def test_the_design_s_pinned_cases():
    # The review's counterexample: snapping the unclamped shade gives
    # [0, 0]; a clamped RGB round trip would give [1, 0].
    assert ramps.generate(
        rgb("#000040"), 2, 1.0, -12.0, 0.3, [(0, 0, 3), (1, 0, 0)]
    ) == (0, 0)
    assert ramps.generate(rgb("#ca9337"), 4, *B.values(), VINCE_144) == (18, 19, 4, 5)
    assert ramps.generate(rgb("#8c939c"), 4, *B.values(), VINCE_144) == (
        111,
        133,
        135,
        137,
    )
    assert ramps.generate(rgb("#ca9337"), 4, *C.values(), VINCE_144) == (110, 13, 4, 5)
    assert ramps.generate(rgb("#8c939c"), 4, *C.values(), VINCE_144) == (
        132,
        134,
        136,
        137,
    )


def test_each_band_s_lightness_hue_and_chroma():
    # A muted base whose shades all stay in gamut.
    base = rgb("#8a7a6a")
    shades = ramps.shades(base, 5, 0.05, -10.0, 0.4)
    l0, c0, h0 = lch(ramps.shades(base, 1, 0.05, -10.0, 0.4)[0])
    assert c0 >= ramps.GREY_CHROMA
    for band, shade in enumerate(shades):
        k = 4 - band
        lightness, chroma, hue = lch(shade)
        assert lightness == pytest.approx(l0 - 0.05 * k, abs=1e-12)
        assert chroma == pytest.approx(c0 * (1 - 0.4 * k / 4), abs=1e-12)
        assert (hue - (h0 - 10.0 * k) + 180) % 360 - 180 == pytest.approx(0, abs=1e-9)
        assert ramps.in_gamut(*shade)
    # The last band is the base colour itself (D-28).
    assert shades[-1] == pytest.approx(tuple(ramps.oklab([base])[0]), abs=1e-12)


def test_a_near_grey_keeps_its_hue():
    base = rgb("#8c939c")  # C0 about 0.016
    first = ramps.shades(base, 4, 0.1, -90.0, 0.0)
    hues = [lch(shade)[2] for shade in first]
    assert lch(first[-1])[1] < ramps.GREY_CHROMA
    assert max(hues) - min(hues) == pytest.approx(0, abs=1e-12)


def test_one_band_is_the_base_with_its_chroma():
    base = rgb("#a83232")
    (shade,) = ramps.shades(base, 1, 0.5, -90.0, 1.0)
    assert shade == pytest.approx(tuple(ramps.oklab([base])[0]), abs=1e-12)


def test_lightness_stops_at_0():
    shades = ramps.shades(rgb("#404040"), 4, 0.3, 0.0, 0.0)
    assert [lch(s)[0] for s in shades[:2]] == [0.0, 0.0]
    assert lch(shades[2])[0] > 0


def test_a_shade_out_of_gamut_loses_chroma_only():
    # Pure red turned 60° per shade leaves the gamut; lightness and hue stay.
    base = rgb("#ff0000")
    l0, c0, h0 = lch(ramps.oklab([base])[0])
    shades = ramps.shades(base, 3, 0.05, 60.0, 0.0)
    clipped = 0
    for band, shade in enumerate(shades):
        k = 2 - band
        lightness, chroma, hue = lch(shade)
        assert lightness == pytest.approx(l0 - 0.05 * k, abs=1e-12)
        if chroma > 1e-12:
            assert (hue - (h0 + 60.0 * k) + 180) % 360 - 180 == pytest.approx(
                0, abs=1e-9
            )
        assert ramps.in_gamut(*shade)
        if chroma < c0 - 1e-9:
            clipped += 1
            # The largest chroma in gamut, within the search's last step.
            a, b = (
                (chroma + 2 * c0 / 2**40) * math.cos(math.radians(hue)),
                (chroma + 2 * c0 / 2**40) * math.sin(math.radians(hue)),
            )
            assert not ramps.in_gamut(lightness, a, b)
    assert clipped >= 1


def test_the_gamut_tolerance():
    assert ramps.in_gamut(1.0, 0.0, 0.0) and ramps.in_gamut(0.0, 0.0, 0.0)
    assert not ramps.in_gamut(1.001, 0.0, 0.0)


def test_equal_distances_keep_the_lower_index_and_repeats_are_kept():
    palette = [(255, 255, 255), (10, 10, 10), (10, 10, 10)]
    lab = ramps.oklab(palette)
    assert ramps.snap(tuple(lab[1]), lab) == 1
    # Four bands into a two-colour palette: repeats, never fewer bands.
    result = ramps.generate(
        rgb("#808080"), 4, 0.05, 0.0, 0.0, [(0, 0, 0), (128, 128, 128)]
    )
    assert len(result) == 4 and result[-1] == 1 and len(set(result)) < 4


# The reader (D-34, D-35, D-36)

COLORS = [(i * 30, 255 - i * 30, i * 7) for i in range(8)]


def library(schema=materials.SCHEMA, **changes):
    document = {
        "schema": schema,
        "ramps": {"metal": [1, 2, 3], "gold": {"base": "#CA9337", "bands": 3}},
        "default": "gold",
        "materials": {
            "steel": {"uses": "metal"},
            "cloth": {"ramp": {"base": "#7a3b2e", "bands": 2, "hue_shift_deg": -35}},
        },
    }
    for key, value in changes.items():
        if value is None:
            document.pop(key)
        else:
            document[key] = value
    return document


def refused(document):
    with pytest.raises(LibraryError) as raised:
        validate_library(document, COLORS, source="lib.yaml")
    return raised.value.problem


def test_a_3_library_reads_generated_ramps_as_given():
    parsed = validate_library(library(), COLORS, source="lib.yaml")
    assert parsed.ramps["metal"] == (1, 2, 3)
    assert parsed.ramps["gold"] == Generated("#ca9337", 3)
    assert parsed.materials["cloth"].ramp == Generated(
        "#7a3b2e", 2, hue_shift_deg=-35.0
    )
    assert parsed.shade is None


def test_a_2_library_still_reads_exactly_as_before():
    listed = library(
        materials.LEGACY_SCHEMA,
        ramps={"metal": [1, 2, 3]},
        default="metal",
        materials={"steel": {"uses": "metal", "shade": {"range": [10, 200]}}},
    )
    parsed = validate_library(listed, COLORS, source="lib.yaml")
    current = validate_library(
        listed | {"schema": materials.SCHEMA}, COLORS, source="lib.yaml"
    )
    assert parsed == current


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (
            {"ramps": {"gold": {"base": "#ca9337", "bands": 3}}, "default": None},
            'ramps["gold"]: a generated ramp needs schema "moskophoros.materials/3"',
        ),
        (
            {
                "ramps": {},
                "default": None,
                "materials": {"cloth": {"ramp": {"base": "#7a3b2e", "bands": 2}}},
            },
            'materials["cloth"].ramp: a generated ramp needs schema',
        ),
        (
            {"ramps": {"m": [1]}, "default": None, "shade": {"range": [1, 2]}},
            'shade: a library\'s own shade needs schema "moskophoros.materials/3"',
        ),
    ],
)
def test_a_2_library_using_a_3_feature_is_refused(change, problem):
    document = library(materials.LEGACY_SCHEMA, materials={}) | change
    document = {key: value for key, value in document.items() if value is not None}
    assert refused(document).startswith(problem)


def test_a_1_library_is_still_refused():
    assert "no longer load" in refused(library("moskophoros.materials/1"))


@pytest.mark.parametrize(
    ("ramp", "problem"),
    [
        ({"bands": 3}, 'ramps["x"].base: missing'),
        ({"base": "#ca9337"}, 'ramps["x"].bands: missing'),
        (
            {"base": "ca9337", "bands": 3},
            'ramps["x"].base: expected an sRGB #rrggbb, got "ca9337"',
        ),
        ({"base": "#ca933", "bands": 3}, 'ramps["x"].base: expected an sRGB #rrggbb'),
        ({"base": "#ggg000", "bands": 3}, 'ramps["x"].base: expected an sRGB #rrggbb'),
        ({"base": 1, "bands": 3}, 'ramps["x"].base: expected an sRGB #rrggbb, got 1'),
        (
            {"base": "#ca9337", "bands": 0},
            'ramps["x"].bands: expected a whole number from 1 to 256, got 0',
        ),
        (
            {"base": "#ca9337", "bands": 257},
            'ramps["x"].bands: expected a whole number from 1 to 256',
        ),
        (
            {"base": "#ca9337", "bands": 2.0},
            'ramps["x"].bands: expected a whole number from 1 to 256',
        ),
        (
            {"base": "#ca9337", "bands": True},
            'ramps["x"].bands: expected a whole number from 1 to 256',
        ),
        (
            {"base": "#ca9337", "bands": 3, "lightness_step": 1.5},
            'ramps["x"].lightness_step: expected a finite number from 0 to 1',
        ),
        (
            {"base": "#ca9337", "bands": 3, "lightness_step": -0.1},
            'ramps["x"].lightness_step: expected a finite number from 0 to 1',
        ),
        (
            {"base": "#ca9337", "bands": 3, "hue_shift_deg": 181},
            'ramps["x"].hue_shift_deg: expected a finite number from -180 to 180',
        ),
        (
            {"base": "#ca9337", "bands": 3, "hue_shift_deg": float("nan")},
            'ramps["x"].hue_shift_deg: expected a finite number',
        ),
        (
            {"base": "#ca9337", "bands": 3, "chroma_fade": True},
            'ramps["x"].chroma_fade: expected a finite number from 0 to 1',
        ),
        (
            {"base": "#ca9337", "bands": 3, "chroma_fade": "0.3"},
            'ramps["x"].chroma_fade: expected a finite number',
        ),
        (
            {"base": "#ca9337", "bands": 3, "shine": 1},
            'ramps["x"]: unknown field "shine"',
        ),
        (
            {"base": "#ca9337", "bands": 3, "indices": [1, 2, 3]},
            'ramps["x"]: unknown field "indices"',
        ),
    ],
)
def test_a_malformed_generated_ramp_is_refused_naming_it(ramp, problem):
    assert refused(library(ramps={"x": ramp}, default=None, materials={})).startswith(
        problem
    )


@pytest.mark.parametrize(
    ("shade", "problem"),
    [
        (
            {"ao_distance_m": 1.2},
            "shade.ao_distance_m: a library's own shade gives only range",
        ),
        (
            {"occlusion_weight": 0.5},
            "shade.occlusion_weight: a library's own shade gives only range",
        ),
        (
            {"convexity_weight": 0},
            "shade.convexity_weight: a library's own shade gives only range",
        ),
        ({"ao_samples": 8}, "shade.ao_samples: a library's own shade gives only range"),
        ({"range": [9, 1]}, "shade.range: expected [lo, hi]"),
        ({"shine": 1}, 'shade: unknown field "shine"'),
        ([190, 225], "shade: expected a mapping of shading values"),
    ],
)
def test_a_library_shade_gives_the_range_only(shade, problem):
    assert refused(library(shade=shade)).startswith(problem)


def test_a_library_shade_range_is_read():
    parsed = validate_library(library(shade={"range": [190, 225]}), COLORS, source="l")
    assert parsed.shade == materials.Shade(range=(190, 225))


# Generation and resolution (D-33)


def test_generate_fills_every_generated_ramp_with_the_formula_in_force():
    parsed = validate_library(library(), COLORS, source="lib.yaml")
    made = materials.generate(parsed, COLORS, B)
    gold, cloth = made.ramps["gold"], made.materials["cloth"].ramp
    assert gold.indices == ramps.generate(rgb("#ca9337"), 3, 0.12, -12.0, 0.3, COLORS)
    # cloth's own hue shift beats the global.
    assert cloth.indices == ramps.generate(rgb("#7a3b2e"), 2, 0.12, -35.0, 0.3, COLORS)
    assert made.ramps["metal"] == (1, 2, 3)
    assert stylize.resolve(made, "steel") == (1, 2, 3)
    assert stylize.resolve(made, "cloth") == cloth.indices
    assert stylize.resolve(made, "anything") == gold.indices


def test_a_recorded_ramp_regenerates_only_when_its_formula_changes(monkeypatch):
    recorded = library(
        ramps={
            "gold": {"base": "#ca9337", "bands": 3, "indices": [7, 7, 7]},
            "own": {
                "base": "#ca9337",
                "bands": 2,
                "hue_shift_deg": -35,
                "indices": [6, 6],
            },
        },
        default=None,
        materials={},
    )
    parsed = validate_library(recorded, COLORS, source="record", recorded=True)
    calls = []
    real = ramps.generate

    def counting(*args):
        calls.append(args)
        return real(*args)

    monkeypatch.setattr(ramps, "generate", counting)
    same = materials.generate(parsed, COLORS, B, recorded=B)
    assert (same.ramps["gold"].indices, same.ramps["own"].indices) == (
        (7, 7, 7),
        (6, 6),
    )
    assert calls == []
    # A hue shift the own ramp shadows changes only gold.
    shifted = materials.generate(
        parsed, COLORS, B | {"hue_shift_deg": -20.0}, recorded=B
    )
    assert shifted.ramps["own"].indices == (6, 6)
    assert shifted.ramps["gold"].indices != (7, 7, 7) and len(calls) == 1


def test_recorded_indices_are_checked_without_regenerating():
    def record(indices, bands=3):
        return library(
            ramps={"gold": {"base": "#ca9337", "bands": bands, "indices": indices}},
            default=None,
            materials={},
        )

    for indices, problem in [
        ([1, 2], 'ramps["gold"].indices: has 2 entries; expected 3, its bands'),
        ([1, 2, 99], 'ramps["gold"].indices[2]: 99 is not an index into the 8-colour'),
        ("1,2,3", 'ramps["gold"].indices: expected a list of palette indices'),
        ([1, True, 3], 'ramps["gold"].indices[1]: true is not an integer'),
    ]:
        with pytest.raises(LibraryError) as raised:
            validate_library(record(indices), COLORS, source="r", recorded=True)
        assert raised.value.problem.startswith(problem), raised.value.problem
    with pytest.raises(LibraryError, match="indices: missing"):
        validate_library(
            library(
                ramps={"g": {"base": "#ca9337", "bands": 1}}, default=None, materials={}
            ),
            COLORS,
            source="r",
            recorded=True,
        )


def part(index, name, alpha="OPAQUE"):
    return PrimitiveMaterial(0, 0, index, index, name, alpha)


PARTS = [
    part(0, "steel"),
    part(1, "cloth"),
    part(2, "plain"),
    part(3, "glass", "BLEND"),
]


def test_shade_ranges_resolve_own_then_library_then_global():
    document = library(
        shade={"range": [190, 225]},
        materials={
            "steel": {"uses": "metal", "shade": {"range": [10, 20]}},
            "cloth": {"uses": "metal"},
        },
    )
    parsed = validate_library(document, COLORS, source="l")
    assert stylize._own_range(parsed, "steel") == (10, 20)
    assert stylize._own_range(parsed, "cloth") == (190, 225)
    # A material with no entry takes the default ramp and the library's range.
    assert stylize._own_range(parsed, "plain") == (190, 225)
    without = validate_library(library(), COLORS, source="l")
    assert stylize._own_range(without, "plain") is None


def test_a_ramp_s_own_value_warns_over_an_explicit_global():
    parsed = materials.generate(
        validate_library(library(), COLORS, source="l"), COLORS, B
    )
    assert materials.ramp_warnings(PARTS, parsed, {"hue_shift_deg": -20.0}) == [
        'material "cloth"\'s own ramp keeps its own hue_shift_deg, -35.0, from the '
        "material library; the global -20.0 applies to generated ramps without "
        "their own"
    ]
    # Equal values still warn; nothing is explicit, nothing warns.
    assert len(materials.ramp_warnings(PARTS, parsed, {"hue_shift_deg": -35.0})) == 1
    assert materials.ramp_warnings(PARTS, parsed, {}) == []
    assert materials.ramp_warnings(PARTS, parsed, {"chroma_fade": 0.1}) == []


def test_a_named_ramp_s_own_value_warns_only_when_in_use():
    document = library(
        ramps={"chrome": {"base": "#8c939c", "bands": 2, "chroma_fade": 0.6}},
        default=None,
        materials={"steel": {"uses": "chrome"}},
    )
    parsed = materials.generate(
        validate_library(document, COLORS, source="l"), COLORS, B
    )
    assert materials.ramp_warnings(PARTS, parsed, {"chroma_fade": 0.3}) == [
        'ramp "chrome" keeps its own chroma_fade, 0.6, from the material library; '
        "the global 0.3 applies to generated ramps without their own"
    ]
    assert (
        materials.ramp_warnings([part(2, "plain")], parsed, {"chroma_fade": 0.3}) == []
    )


def test_the_library_range_warns_once_over_an_explicit_global_range():
    parsed = validate_library(library(shade={"range": [190, 225]}), COLORS, source="l")
    assert materials.library_shade_warnings(PARTS, parsed, {"range": (84, 191)}) == [
        "the material library gives shade.range [190, 225] to its materials "
        "without their own; the global [84, 191] does not reach them"
    ]
    assert materials.library_shade_warnings(PARTS, parsed, {}) == []
    # Every material in use giving its own range: nothing to warn about.
    own = library(
        shade={"range": [190, 225]},
        default=None,
        materials={"steel": {"uses": "metal", "shade": {"range": [1, 2]}}},
    )
    parsed = validate_library(own, COLORS, source="l")
    assert materials.library_shade_warnings(PARTS, parsed, {"range": (84, 191)}) == []


def test_a_library_shade_never_reaches_capture():
    with_shade = validate_library(
        library(shade={"range": [190, 225]}), COLORS, source="l"
    )
    without = validate_library(library(), COLORS, source="l")
    values = {"ao_distance_m": 0.3, "occlusion_weight": 0.25, "convexity_weight": 1.0}
    assert materials.capture_overrides(PARTS, with_shade, values) == []
    assert materials.capture_overrides(PARTS, with_shade, values) == (
        materials.capture_overrides(PARTS, without, values)
    )


def test_a_yaml_library_with_generated_ramps_reads_from_text(tmp_path):
    text = """\
schema: moskophoros.materials/3
ramps:
  stone: [1, 2, 3]
  gold: {base: "#ca9337", bands: 4}
  chrome: {base: "#8c939c", bands: 5, hue_shift_deg: -35, chroma_fade: 0.6}
shade: {range: [190, 225]}
materials:
  Main: {uses: gold}
  Cloth: {ramp: {base: "#7a3b2e", bands: 3}}
"""
    path = tmp_path / "lib.yaml"
    path.write_text(text)
    parsed = materials.read_library(path, COLORS)
    assert parsed.ramps["chrome"] == Generated("#8c939c", 5, None, -35.0, 0.6)
    assert parsed.shade.range == (190, 225)
    assert yaml.safe_load(text)["schema"] == materials.SCHEMA
