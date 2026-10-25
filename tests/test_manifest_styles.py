"""The inline palette and material library of a manifest (export design P-8,
part 2; P-8a): every form is recorded as it was supplied and comes back
byte-for-byte, with the files that supplied it gone. Everything is generated
here."""

import hashlib
import json
import tempfile
from pathlib import Path

import pytest
from manifest_fixture import export_for

from moskophoros import cli, materials, palette, views
from moskophoros.cli import MaterialsRecord, PaletteRecord

RING4 = views.View(4, 0.0)
COLORS = [
    f"{(17 * i) % 256:02x}{(53 * i + 9) % 256:02x}{(91 * i + 40) % 256:02x}"
    for i in range(16)
]
LIBRARY = """
schema: moskophoros.materials/4
ramps:
  tint: {base: "#7A3B2E", bands: 3, hue_shift_deg: -35, chroma_fade: 0.1}
  metal: [1, 2, 3]
  gold: {base: "#FFD700", bands: 3}
default: gold
shade:
  range: [90, 200]
  dither: {strength: 0.5}
materials:
  trim:
    uses: tint
    shade: {occlusion_weight: 0.9}
  steel:
    uses: metal
    shade:
      key: {strength: 0.25}
      dither: {pattern: ordered4}
      range: [100, 200]
      convexity_weight: 0.5
      ao_distance_m: 1.5
  rim:
    ramp: [4]
    shade:
      sky: {strength: 0.1}
      ambient_form: false
      mode: ramp
      range: [10, 250]
  helm: {ordinary: true, shade: {mode: neither}}
  glass: {ordinary: true}
  face: ordinary
  cloth:
    ramp: {base: "#7a3b2e", bands: 3, lightness_step: 0.05}
"""
FORMULA = {"lightness_step": 0.12, "hue_shift_deg": -12.0, "chroma_fade": 0.3}
_cache = {}


def records():
    """The palette and library records the command would make, read from
    files that are deleted before they return."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        colors_file = root / "colors.hex"
        library_file = root / "materials.yaml"
        colors_file.write_text("\n".join(COLORS) + "\n")
        library_file.write_text(LIBRARY)
        data = colors_file.read_bytes()
        colors = palette.read_palette_bytes(data, source=colors_file)
        record = PaletteRecord("colors.hex", hashlib.sha256(data).hexdigest(), colors)
        text = library_file.read_bytes()
        library = materials.read_library_bytes(text, colors, source=library_file)
        library = materials.generate(library, colors, FORMULA)
        return record, MaterialsRecord(
            "materials.yaml", hashlib.sha256(text).hexdigest(), library
        )


def style(palette_record, library_record, reduce="mode", edges="soft"):
    return cli.style_document(reduce, edges, palette_record, library_record)


def styled(**changes):
    if "x" not in _cache or changes:
        record, library = records()
        result = export_for(
            "{}\n",
            clips=(export_clip(),),
            view=RING4,
            style=style(record, library),
            **changes,
        )
        if changes:
            return result
        _cache["x"] = result
    return _cache["x"]


def export_clip():
    from manifest_fixture import clip

    return clip(0, "pose", t1=0.0)


def entries(document):
    return document["settings"]["style"]["materials"]["materials"]


def test_the_palette_is_recorded_with_its_source_digest_and_ordered_colours():
    recorded = styled().document["settings"]["style"]["palette"]
    assert list(recorded) == ["source", "sha256", "colors"]
    assert recorded["source"] == "colors.hex"
    assert len(recorded["sha256"]) == 64
    assert recorded["colors"] == ["#" + color for color in COLORS]


def test_the_library_record_lists_ramps_default_and_materials_by_name():
    record = styled().document["settings"]["style"]["materials"]
    assert list(record) == [
        "source",
        "sha256",
        "ramps",
        "default",
        "shade",
        "materials",
    ]
    assert list(record["ramps"]) == ["gold", "metal", "tint"]
    assert list(record["materials"]) == [
        "cloth",
        "face",
        "glass",
        "helm",
        "rim",
        "steel",
        "trim",
    ]
    assert record["default"] == "gold"
    assert record["ramps"]["metal"] == [1, 2, 3]


def test_generated_ramps_keep_their_supplied_properties_in_order_with_indices_last():
    ramps = styled().document["settings"]["style"]["materials"]["ramps"]
    assert list(ramps["gold"]) == ["base", "bands", "indices"]
    assert ramps["gold"]["base"] == "#ffd700"
    assert list(ramps["tint"]) == [
        "base",
        "bands",
        "hue_shift_deg",
        "chroma_fade",
        "indices",
    ]
    assert ramps["tint"]["base"] == "#7a3b2e"
    assert len(ramps["tint"]["indices"]) == 3
    cloth = entries(styled().document)["cloth"]["ramp"]
    assert list(cloth) == ["base", "bands", "lightness_step", "indices"]


def test_ordinary_keeps_its_string_or_mapping_form_and_a_shade_follows_it():
    found = entries(styled().document)
    assert found["face"] == "ordinary"
    assert found["glass"] == {"ordinary": True}
    assert found["helm"] == {"ordinary": True, "shade": {"mode": "neither"}}
    assert list(found["helm"]) == ["ordinary", "shade"]


def test_partial_shades_record_only_what_was_supplied_in_the_fixed_order():
    found = entries(styled().document)
    assert list(found["steel"]["shade"]) == [
        "ao_distance_m",
        "convexity_weight",
        "range",
        "key",
        "dither",
    ]
    assert found["steel"]["shade"]["key"] == {"strength": 0.25}
    assert found["steel"]["shade"]["dither"] == {"pattern": "ordered4"}
    assert list(found["trim"]["shade"]) == ["occlusion_weight"]
    assert list(found["steel"]) == ["uses", "shade"]
    assert list(found["rim"]) == ["ramp", "shade"]


def test_the_response_leaves_follow_the_range_in_the_shade_tables_order():
    shade = entries(styled().document)["rim"]["shade"]
    # `ambient_form` is a response leaf, not an ambient/range one: it follows
    # `range` and `mode`, in the shading table's order.
    assert list(shade) == ["range", "mode", "ambient_form", "sky"]
    assert shade["ambient_form"] is False and shade["sky"] == {"strength": 0.1}


def test_a_library_wide_shade_gives_the_range_and_response_leaves_only():
    record = styled().document["settings"]["style"]["materials"]
    assert record["shade"] == {"range": [90, 200], "dither": {"strength": 0.5}}


def test_the_originals_are_gone_yet_the_style_comes_back_byte_for_byte():
    x = styled()
    loaded = cli_loaded(x.data)
    again = style(
        loaded.reused.palette,
        loaded.reused.materials,
        loaded.reused.reduce,
        loaded.reused.edges,
    )
    assert json.dumps(again) == json.dumps(x.document["settings"]["style"])
    assert loaded.reused.materials.source == "materials.yaml"
    assert loaded.reused.palette.colors == tuple(
        tuple(bytes.fromhex(color)) for color in COLORS
    )


def test_a_library_loaded_from_the_manifest_re_encodes_the_same_bytes():
    x = styled()
    loaded = cli_loaded(x.data)
    again = export_for(
        "{}\n",
        clips=(export_clip(),),
        view=RING4,
        style=style(
            loaded.reused.palette,
            loaded.reused.materials,
            loaded.reused.reduce,
            loaded.reused.edges,
        ),
    )
    assert again.data == x.data


def cli_loaded(data):
    from moskophoros import manifest

    return manifest.decode(data)


def test_an_ordinary_string_never_becomes_a_mapping_on_the_way_back():
    loaded = cli_loaded(styled().data)
    library = loaded.reused.materials.library
    assert library.materials["face"].ordinary_mapping is False
    assert library.materials["glass"].ordinary_mapping is True


@pytest.mark.parametrize("reduce, edges", [("plain", "hard"), ("mode", "soft")])
def test_the_reduction_and_edges_are_part_of_the_look_record(reduce, edges):
    x = export_for(
        "{}\n",
        clips=(export_clip(),),
        view=RING4,
        style=style(None, None, reduce, edges),
    )
    assert x.document["settings"]["style"] == {
        "reduce": reduce,
        "edges": edges,
        "palette": None,
        "materials": None,
    }
    assert cli_loaded(x.data).reused.edges == edges
