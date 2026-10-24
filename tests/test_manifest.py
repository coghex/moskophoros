"""The writer of `moskophoros.export/1` (export design P-8, P-8a): every
member and its order, the arrays that encode the integer-keyed maps, the
supplied settings beside the effective clip records, the real sample
locations and the mirror records, the fingerprint, and the strict
separation from the capture job's settings."""

import copy
import hashlib
import io
import json

import numpy as np
import pytest
from manifest_fixture import (
    GENERATOR,
    LIGHT,
    PLAIN,
    SHA,
    SOURCE,
    W,
    clip,
    export_for,
)
from manifest_golden import POSITIONAL
from PIL import Image

from moskophoros import export, imageops, manifest, outputs, views
from moskophoros.capture import backend
from moskophoros.capture.backend import Source

POSE = clip(0, "pose", t1=0.0)

# Every object's members in serialized order, from the issue's table.
ORDER = {
    "": [
        "schema",
        "generator",
        "source",
        "subject",
        "variant",
        "settings",
        "fingerprint",
        "artifacts",
        "directions",
        "clips",
        "frames",
    ],
    "generator": [
        "tool",
        "version",
        "python",
        "numpy",
        "pillow",
        "blender",
        "renderer",
        "color",
        "shade",
    ],
    "generator.color": [
        "technique",
        "samples_per_pixel",
        "seed",
        "pixel_filter",
        "filter_width_px",
        "min_transparent_bounces",
        "transparent_max_bounces",
        "pass_alpha_threshold",
    ],
    "generator.shade": [
        "technique",
        "samples_per_pixel",
        "seed",
        "pixel_filter",
        "filter_width_px",
    ],
    "source": ["file", "sha256"],
    "settings": [
        "view",
        "camera",
        "model_yaw_deg",
        "fps",
        "frames",
        "supersample",
        "pixels_per_meter",
        "cell",
        "ground_m",
        "ground_px",
        "root_motion",
        "previews",
        "normals",
        "depth",
        "light",
        "shade",
        "ramp",
        "style",
        "stored_directions",
        "direction_names",
        "mirrors",
        "export",
        "clips",
    ],
    "settings.view": ["preset", "directions", "start_angle_deg"],
    "settings.camera": ["projection", "direction", "roll", "position"],
    "settings.cell": ["width", "height"],
    "settings.ground_m": ["x", "y", "z"],
    "settings.ground_px": ["x", "y"],
    "settings.light": ["position", "intensity", "ambient"],
    "settings.shade": [
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
    ],
    "settings.shade.key": ["direction", "strength"],
    "settings.shade.sky": ["strength"],
    "settings.shade.ground": ["strength"],
    "settings.shade.brightness": ["floor", "ceiling"],
    "settings.shade.dither": ["pattern", "strength"],
    "settings.ramp": ["lightness_step", "hue_shift_deg", "chroma_fade"],
    "settings.style": ["reduce", "edges", "palette", "materials"],
    "settings.export": [
        "formats",
        "frame_path",
        "atlas_path",
        "sheet_path",
        "atlas_padding",
    ],
}
SETTINGS_CLIP = [
    "name",
    "loop",
    "frames",
    "fps",
    "stored_directions",
    "mirrors",
    "output_name",
]
PREFIX = ["kind", "channel", "path", "width", "height"]
SUFFIX = {
    "sheet": ["padding", "cell"],
    "atlas": ["clip", "padding", "cell"],
    "frame": ["clip", "direction", "index", "padding", "cell"],
    "preview": ["clip"],
}
DIRECTION = ["index", "angle_deg", "label", "output_name"]
CLIP = [
    "name",
    "loop",
    "duration_s",
    "frame_count",
    "frame_duration_s",
    "time_scale",
    "output_name",
    "fps",
    "stored_directions",
    "mirrors",
]
MIRROR = ["target", "source", "transform", "ground_px"]
FRAME = ["clip", "direction", "index", "time_s", "locations"]
LOCATION = ["artifact", "x", "y", "w", "h"]

# Every feature at once: unequal rates, counts, subsets, mirrors and names,
# the three formats with padding, every map and both previews. The maps are
# written in the order a hand would, not the canonical one.
FULL = """
stored_directions: [2, 0]
direction_names: {3: west-side, 1: right}
mirrors: {3: 2}
export:
  formats: [atlases, frames, sheet]
  atlas_padding: 1
  atlas_path: "atlas/{clip}{map}.png"
clips:
  walk: {frames: 2, fps: 6, stored_directions: [1, 0], mirrors: {3: 1}, output_name: stride}
  idle: {frames: 1, mirrors: {}}
  jump: {frames: 2}
"""
WALK_IDLE_JUMP = (
    clip(0, "walk"),
    clip(1, "idle"),
    clip(2, "jump", t1=2.0, one_shot=True),
)
RING4 = views.View(4, 0.0)


def full(**changes):
    options = {
        "text": FULL,
        "clips": WALK_IDLE_JUMP,
        "view": RING4,
        "depth": True,
        "light": LIGHT,
        "destination": outputs.Directory(),
    }
    return export_for(**(options | changes))


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def fingerprint_of(document):
    """The fingerprint the design defines, computed here from the parsed
    document without the writer's machinery."""
    mirrored = {
        "generator": document["generator"],
        "settings": document["settings"],
        "source": {"sha256": document["source"]["sha256"]},
    }
    return "sha256:" + hashlib.sha256(canonical(mirrored)).hexdigest()


def members(document, path=""):
    """Every (path, member names) pair of the nested objects in `ORDER`."""
    found = [(path, list(document))]
    for name, value in document.items():
        here = f"{path}.{name}" if path else name
        if isinstance(value, dict) and here in ORDER:
            found += members(value, here)
    return found


def png(artifact):
    return np.array(Image.open(io.BytesIO(artifact.data)))


# The byte-exact manifest


def test_the_smallest_positional_manifest_matches_the_pinned_bytes():
    x = export_for(clips=(POSE,), view=views.View(2, 0.0))
    assert x.data == POSITIONAL


def test_the_pinned_fingerprint_is_the_canonical_hash_of_the_pinned_parts():
    document = json.loads(POSITIONAL)
    assert document["fingerprint"] == fingerprint_of(document)
    assert document["fingerprint"] == (
        "sha256:abb6647b2be4cea863706a6bb15a08c0aefe899825a5f60314da4a35d9c66a6c"
    )


def test_the_text_is_two_space_indented_utf8_with_one_trailing_newline():
    x = export_for(clips=(clip(0, "läuft"),), view=views.View(2, 0.0))
    text = x.data.decode("utf-8")
    assert text.endswith("}\n") and not text.endswith("\n\n")
    assert '"name": "läuft"' in text
    assert text.splitlines()[1].startswith('  "schema"')
    assert b"\\u" not in x.data


def test_two_exports_of_the_same_inputs_are_byte_identical():
    assert full().data == full().data


# Every member and its order


def test_every_object_has_the_members_of_the_table_in_order():
    document = full().document
    seen = dict(members(document))
    assert set(seen) == set(ORDER)
    for path, names in seen.items():
        assert names == ORDER[path], path
    assert [list(c) for c in document["settings"]["clips"]] == [SETTINGS_CLIP] * 3
    assert [list(c) for c in document["clips"]] == [CLIP] * 3
    assert [list(d) for d in document["directions"]] == [DIRECTION] * 4
    assert {tuple(f) for f in document["frames"]} == {tuple(FRAME)}
    places = [p for f in document["frames"] for p in f["locations"]]
    assert {tuple(p) for p in places} == {tuple(LOCATION)}
    for artifact in document["artifacts"]:
        assert list(artifact) == PREFIX + SUFFIX[artifact["kind"]]
    mirrors = [m for c in document["clips"] for m in c["mirrors"]]
    assert mirrors and {tuple(m) for m in mirrors} == {tuple(MIRROR)}
    assert {tuple(m["ground_px"]) for m in mirrors} == {("x", "y")}
    names = document["settings"]["direction_names"]
    assert [list(n) for n in names] == [["index", "name"]] * 2
    pairs = document["settings"]["mirrors"]
    assert [list(p) for p in pairs] == [["target", "source"]]


def test_the_singleton_image_and_maps_members_are_gone():
    document = full().document
    assert "image" not in document and "maps" not in document
    assert document["schema"] == "moskophoros.export/1"


def test_the_document_holds_no_root_project_or_mode():
    text = full().data.decode()
    for word in ("output_dir", "project", "positional", "destination", "root"):
        assert f'"{word}"' not in text


# Arrays, nulls and supplied against effective values


def test_the_name_and_mirror_arrays_are_sorted_whatever_order_they_were_given():
    first = full()
    reordered = FULL.replace("{3: west-side, 1: right}", "{1: right, 3: west-side}")
    assert reordered != FULL
    assert full(text=reordered).data == first.data
    settings = first.document["settings"]
    assert settings["direction_names"] == [
        {"index": 1, "name": "right"},
        {"index": 3, "name": "west-side"},
    ]
    many = "mirrors: {7: 1, 5: 3}\nstored_directions: [3, 1]\n"
    shuffled = "mirrors: {5: 3, 7: 1}\nstored_directions: [3, 1]\n"
    ring8 = views.View(8, 0.0)
    a = export_for(many, clips=(POSE,), view=ring8)
    b = export_for(shuffled, clips=(POSE,), view=ring8)
    assert a.data == b.data
    assert a.document["settings"]["mirrors"] == [
        {"target": 5, "source": 3},
        {"target": 7, "source": 1},
    ]
    assert a.document["clips"][0]["mirrors"][0]["target"] == 5


def test_empty_maps_are_arrays_and_a_null_override_differs_from_an_empty_one():
    x = export_for("{}\n", clips=(POSE,), view=views.View(2, 0.0))
    settings = x.document["settings"]
    assert settings["direction_names"] == [] and settings["mirrors"] == []
    assert settings["stored_directions"] == "all"
    only = settings["clips"][0]
    assert only["mirrors"] is None and only["stored_directions"] is None
    explicit = export_for(
        "mirrors: {1: 0}\nclips: {pose: {mirrors: {}}}\n",
        clips=(POSE,),
        view=views.View(2, 0.0),
        # The global mirror stored-source rule needs direction 0 only.
    )
    assert explicit.document["settings"]["mirrors"] == [{"target": 1, "source": 0}]
    clip_settings = explicit.document["settings"]["clips"][0]
    assert clip_settings["mirrors"] == []
    assert explicit.document["clips"][0]["mirrors"] == []


def test_a_clip_can_override_to_all_and_each_leaf_is_independent():
    x = export_for(
        "stored_directions: [1]\nclips:\n  walk: {stored_directions: all}\n  idle: {fps: 24}\n",
        clips=(clip(0, "walk"), clip(1, "idle")),
        view=RING4,
    )
    walk, idle = x.document["settings"]["clips"]
    assert walk["stored_directions"] == "all" and walk["fps"] is None
    assert idle["fps"] == 24.0 and idle["stored_directions"] is None
    top = x.document["clips"]
    assert top[0]["stored_directions"] == [0, 1, 2, 3]
    assert top[1]["stored_directions"] == [1]
    assert (top[0]["fps"], top[1]["fps"]) == (12.0, 24.0)


def test_the_settings_keep_what_was_supplied_and_the_clips_what_it_resolved_to():
    document = full().document
    walk, idle, jump = document["settings"]["clips"]
    assert walk == {
        "name": "walk",
        "loop": True,
        "frames": 2,
        "fps": 6.0,
        "stored_directions": [1, 0],
        "mirrors": [{"target": 3, "source": 1}],
        "output_name": "stride",
    }
    assert idle["mirrors"] == [] and idle["fps"] is None
    assert jump["mirrors"] is None and jump["stored_directions"] is None
    assert jump["loop"] is False
    top_walk, top_idle, top_jump = document["clips"]
    assert (top_walk["fps"], top_idle["fps"], top_jump["fps"]) == (6.0, 12.0, 12.0)
    assert top_walk["stored_directions"] == [1, 0]
    assert top_idle["stored_directions"] == top_jump["stored_directions"] == [2, 0]
    assert top_idle["mirrors"] == []
    assert [m["source"] for m in top_jump["mirrors"]] == [2]
    assert document["settings"]["stored_directions"] == [2, 0]
    assert top_walk["duration_s"] == 1.0 and top_jump["duration_s"] == 2.0
    assert [c["frame_count"] for c in document["clips"]] == [2, 1, 2]


def test_a_clips_source_name_is_its_identity_and_its_output_name_an_alias():
    document = full().document
    assert [c["name"] for c in document["clips"]] == ["walk", "idle", "jump"]
    assert [c["output_name"] for c in document["clips"]] == ["stride", "idle", "jump"]
    assert {f["clip"] for f in document["frames"]} == {"walk", "idle", "jump"}
    assert {a["clip"] for a in document["artifacts"] if "clip" in a} == {
        "walk",
        "idle",
        "jump",
    }
    atlas = next(
        a for a in document["artifacts"] if a["kind"] == "atlas" and a["clip"] == "walk"
    )
    assert atlas["path"] == "atlas/stride.png"


def test_directions_cover_the_whole_ring_even_when_clips_store_subsets():
    document = full().document
    directions = document["directions"]
    assert [d["index"] for d in directions] == [0, 1, 2, 3]
    assert [d["angle_deg"] for d in directions] == [0.0, 90.0, 180.0, 270.0]
    assert [d["label"] for d in directions] == ["south", "east", "north", "west"]
    assert [d["output_name"] for d in directions] == [
        "south",
        "right",
        "north",
        "west-side",
    ]
    stored = {tuple(c["stored_directions"]) for c in document["clips"]}
    assert stored == {(1, 0), (2, 0)}


def test_a_direction_without_a_compass_label_has_a_null_label_and_a_numbered_name():
    x = export_for("{}\n", clips=(POSE,), view=views.View(3, 0.0))
    third = x.document["directions"][1]
    assert third["label"] is None and third["output_name"] == "direction-001"


# Artifacts


def kinds(document):
    return [(a["kind"], a["channel"], a.get("clip")) for a in document["artifacts"]]


def test_artifacts_follow_the_fixed_order_with_the_channel_innermost():
    document = full().document
    expected = [("sheet", c, None) for c in ("color", "normal", "depth")]
    for name in ("walk", "idle", "jump"):
        expected += [("atlas", c, name) for c in ("color", "normal", "depth")]
    # walk stores 2 directions of 2 samples, idle 2 of 1, jump 2 of 2.
    for name, samples in (("walk", 4), ("idle", 2), ("jump", 4)):
        for _ in range(samples):
            expected += [("frame", c, name) for c in ("color", "normal", "depth")]
    for name in ("walk", "idle", "jump"):
        expected += [("preview", "flat", name), ("preview", "lit", name)]
    assert kinds(document) == expected


def test_frame_artifacts_follow_clip_stored_direction_then_sample_order():
    document = full().document
    frames = [a for a in document["artifacts"] if a["kind"] == "frame"]
    colour = [
        (a["clip"], a["direction"], a["index"])
        for a in frames
        if a["channel"] == "color"
    ]
    assert colour == [
        ("walk", 1, 0),
        ("walk", 1, 1),
        ("walk", 0, 0),
        ("walk", 0, 1),
        ("idle", 2, 0),
        ("idle", 0, 0),
        ("jump", 2, 0),
        ("jump", 2, 1),
        ("jump", 0, 0),
        ("jump", 0, 1),
    ]


def test_previews_are_clip_major_with_flat_then_lit_for_each_clip():
    document = full().document
    previews = [
        (a["clip"], a["channel"])
        for a in document["artifacts"]
        if a["kind"] == "preview"
    ]
    assert previews == [
        ("walk", "flat"),
        ("walk", "lit"),
        ("idle", "flat"),
        ("idle", "lit"),
        ("jump", "flat"),
        ("jump", "lit"),
    ]


def test_omitted_outputs_have_no_entries():
    bare = export_for(
        "export: {formats: [frames]}\n",
        clips=(POSE,),
        view=views.View(2, 0.0),
        normals=False,
        previews=False,
    ).document
    assert kinds(bare) == [("frame", "color", "pose")] * 2
    assert (
        bare["settings"]["normals"] is False and bare["settings"]["previews"] is False
    )
    nolight = export_for("{}\n", clips=(POSE,), view=views.View(2, 0.0)).document
    assert [k[1] for k in kinds(nolight)] == ["color", "normal", "flat"]


def test_png_artifacts_record_padding_and_cell_and_gifs_neither():
    document = full().document
    for artifact in document["artifacts"]:
        if artifact["kind"] == "preview":
            assert "padding" not in artifact and "cell" not in artifact
            continue
        assert artifact["cell"] == {"width": W, "height": 2}
        assert artifact["padding"] == (1 if artifact["kind"] == "atlas" else 0)
        assert artifact["width"] > 0 and artifact["height"] > 0


def test_artifact_dimensions_are_the_encoded_images():
    x = full()
    for recorded, built in zip(
        x.document["artifacts"], x.encoded.artifacts, strict=True
    ):
        if built.kind == "preview":
            with Image.open(io.BytesIO(built.data)) as image:
                assert image.size == (recorded["width"], recorded["height"])
        else:
            assert png(built).shape[:2] == (recorded["height"], recorded["width"])


# Locations


def test_every_enabled_png_representation_of_a_sample_is_located_exactly_once():
    document = full().document
    by_frame = {
        (f["clip"], f["direction"], f["index"]): f["locations"]
        for f in document["frames"]
    }
    assert len(by_frame) == 10
    for key, places in by_frame.items():
        clip_name, direction, index = key
        artifacts = [document["artifacts"][p["artifact"]] for p in places]
        assert [p["artifact"] for p in places] == sorted(
            {p["artifact"] for p in places}
        )
        assert [a["kind"] for a in artifacts] == ["sheet"] * 3 + ["atlas"] * 3 + [
            "frame"
        ] * 3
        assert [a["channel"] for a in artifacts] == ["color", "normal", "depth"] * 3
        assert all(a["kind"] != "preview" for a in artifacts)
        for a in artifacts[6:]:
            assert (a["clip"], a["direction"], a["index"]) == key
        assert {a["clip"] for a in artifacts[3:]} == {clip_name}
        assert all((p["w"], p["h"]) == (W, 2) for p in places)


def test_every_location_holds_the_samples_pixels_in_its_representation():
    x = full()
    pixels = {f.address: f for f in x.frames}
    for frame in x.document["frames"]:
        key = (frame["clip"], frame["direction"], frame["index"])
        address = next(
            f.address
            for f in x.request.frames
            if (f.address.clip, f.address.direction, f.index) == key
        )
        source = pixels[address]
        covered = source.pixels[..., 3] > 0
        for place in frame["locations"]:
            artifact = x.document["artifacts"][place["artifact"]]
            image = png(x.encoded.artifacts[place["artifact"]])
            rect = image[
                place["y"] : place["y"] + place["h"],
                place["x"] : place["x"] + place["w"],
            ]
            if artifact["channel"] == "color":
                assert (rect == source.pixels).all()
            elif artifact["channel"] == "normal":
                want = np.zeros_like(source.pixels)
                want[covered, :3] = imageops.encode_normal(
                    source.buffers["normal_map"][covered]
                )
                want[covered, 3] = source.pixels[covered, 3]
                assert (rect == want).all()
            else:
                want = np.zeros(source.pixels.shape[:2], dtype=np.uint16)
                want[covered] = export.encode_depth(
                    source.buffers["depth_map"][covered]
                )
                assert (rect == want).all()
    assert len({tuple(f["locations"][0].values()) for f in x.document["frames"]}) == 10


def test_atlas_locations_exclude_the_padding():
    x = full()
    atlas = next(
        i
        for i, a in enumerate(x.document["artifacts"])
        if a["kind"] == "atlas" and a["clip"] == "walk" and a["channel"] == "color"
    )
    places = {
        (f["direction"], f["index"]): p
        for f in x.document["frames"]
        if f["clip"] == "walk"
        for p in f["locations"]
        if p["artifact"] == atlas
    }
    # Slots are 5x4 with a one-pixel border; walk stores [1, 0] over 2 samples.
    assert places[1, 0] == {"artifact": atlas, "x": 1, "y": 1, "w": 3, "h": 2}
    assert places[1, 1]["x"] == 6 and places[0, 0]["y"] == 5
    assert x.document["artifacts"][atlas]["width"] == 10
    assert x.document["artifacts"][atlas]["height"] == 8


def test_the_combined_sheet_has_a_row_per_clip_and_stored_direction():
    x = full()
    sheet = x.document["artifacts"][0]
    assert (sheet["width"], sheet["height"]) == (2 * W, 6 * 2)
    rows = {
        (f["clip"], f["direction"]): p["y"]
        for f in x.document["frames"]
        for p in f["locations"]
        if p["artifact"] == 0
    }
    assert rows == {
        ("walk", 1): 0,
        ("walk", 0): 2,
        ("idle", 2): 4,
        ("idle", 0): 6,
        ("jump", 2): 8,
        ("jump", 0): 10,
    }


# Mirrors


@pytest.mark.parametrize(
    "cell, ground, anchor",
    [
        ((5, 2), (2, 1), (3, 1)),
        ((4, 2), (2, 1), (2, 1)),
        ((3, 2), (1, 2), (2, 2)),
        ((6, 3), (0, 0), (6, 0)),
        ((1, 1), (1, 1), (0, 1)),
    ],
)
def test_a_mirror_records_the_flipped_pixel_edge_anchor(cell, ground, anchor):
    x = export_for(
        "stored_directions: [1]\nmirrors: {3: 1}\n",
        clips=(POSE,),
        view=RING4,
        cell=cell,
        ground_px=ground,
    )
    mirror = x.document["clips"][0]["mirrors"][0]
    assert mirror == {
        "target": 3,
        "source": 1,
        "transform": "flip-x",
        "ground_px": {"x": anchor[0], "y": anchor[1]},
    }


def test_mirrors_add_no_frames_locations_or_artifacts():
    plain = export_for("stored_directions: [1]\n", clips=(POSE,), view=RING4).document
    mirrored = export_for(
        "stored_directions: [1]\nmirrors: {3: 1}\n", clips=(POSE,), view=RING4
    ).document
    assert mirrored["frames"] == plain["frames"]
    assert mirrored["artifacts"] == plain["artifacts"]
    assert {f["direction"] for f in mirrored["frames"]} == {1}
    assert mirrored["directions"] == plain["directions"]


def test_a_mirror_inherits_its_clips_real_source_samples_and_times():
    document = full().document
    jump = next(c for c in document["clips"] if c["name"] == "jump")
    assert jump["mirrors"] == [
        {"target": 3, "source": 2, "transform": "flip-x", "ground_px": {"x": 2, "y": 2}}
    ]
    sources = [
        f for f in document["frames"] if f["clip"] == "jump" and f["direction"] == 2
    ]
    assert [f["index"] for f in sources] == [0, 1]
    assert [f["time_s"] for f in sources] == [0.0, 2.0]
    assert not [
        f for f in document["frames"] if f["clip"] == "jump" and f["direction"] == 3
    ]


def flipped(rect):
    return rect[:, ::-1]


def decoded_x(encoded_red):
    """The normal's X scaled by 255: `2 * byte - 255`, an exact integer."""
    return 2 * encoded_red.astype(np.int64) - 255


def test_the_reference_flip_reverses_depth_and_negates_normal_x_exactly():
    x = full()
    document = x.document
    sample = next(
        f
        for f in document["frames"]
        if (f["clip"], f["direction"], f["index"]) == ("walk", 1, 0)
    )
    rects = {}
    for place in sample["locations"]:
        artifact = document["artifacts"][place["artifact"]]
        if artifact["kind"] != "frame":
            continue
        image = png(x.encoded.artifacts[place["artifact"]])
        rects[artifact["channel"]] = image[
            place["y"] : place["y"] + place["h"], place["x"] : place["x"] + place["w"]
        ]
    colour, normal, depth = rects["color"], rects["normal"], rects["depth"]
    alpha = colour[..., 3]
    assert (alpha == 0).any() and (alpha > 0).any()
    covered = flipped(colour)[..., 3] > 0

    mirrored_normal = flipped(normal).copy()
    mirrored_normal[covered, 0] = 255 - mirrored_normal[covered, 0]
    assert (
        decoded_x(mirrored_normal[covered, 0])
        == -decoded_x(flipped(normal)[covered, 0])
    ).all()
    assert (mirrored_normal[..., 1:] == flipped(normal)[..., 1:]).all()
    assert (mirrored_normal[..., 3] == flipped(colour)[..., 3]).all()
    assert (mirrored_normal[~covered] == 0).all()

    mirrored_depth = flipped(depth)
    assert sorted(mirrored_depth.ravel()) == sorted(depth.ravel())
    assert (mirrored_depth[~covered] == export.NO_SURFACE).all()
    assert (mirrored_depth[::, 0] == depth[::, -1]).all()


def test_re_encoding_the_negated_normal_would_not_match_at_zero_so_the_test_is_exact():
    # n_x = 0 encodes as 128, whose complement is 127, not the 128 a
    # re-encode of -0 gives; the decoded negation is what the contract states.
    zero = imageops.encode_normal(np.array([[0.0, 0.0, 1.0]]))
    assert zero[0, 0] == 128
    assert 255 - zero[0, 0] == 127
    assert decoded_x(np.array([255 - 128])) == -decoded_x(np.array([128]))


def test_camera_conditions_that_would_warn_do_not_stop_the_record():
    # An eight-direction ring starting at 10 degrees: 1 and 7 are no
    # reflection of each other, so the pair would warn, but it is recorded.
    x = export_for(
        "stored_directions: [1]\nmirrors: {7: 1}\n",
        clips=(POSE,),
        view=views.View(8, 10.0),
    )
    assert x.document["clips"][0]["mirrors"][0]["source"] == 1
    assert x.document["directions"][1]["angle_deg"] == 55.0


# The fingerprint


def test_the_fingerprint_is_the_canonical_hash_of_generator_settings_and_source():
    document = full().document
    assert document["fingerprint"] == fingerprint_of(document)


CHANGES = {
    "stored_directions": "stored_directions: [0, 1]\n",
    "direction_names": "direction_names: {0: aaa}\n",
    "mirrors": "stored_directions: [0]\nmirrors: {2: 0}\n",
    "formats": "export: {formats: [sheet, frames]}\n",
    "frame_path": "export: {frame_path: 'f/{clip}{frame}{map}.png'}\n",
    "atlas_path": "export: {atlas_path: 'a/{clip}{map}.png'}\n",
    "sheet_path": "export: {sheet_path: 's{map}.png'}\n",
    "padding": "export: {atlas_padding: 2}\n",
    "clip fps": "clips: {pose: {fps: 8}}\n",
    "clip frames": "clips: {pose: {frames: 3}}\n",
    "clip stored": "clips: {pose: {stored_directions: [1]}}\n",
    "clip mirrors": "stored_directions: [0]\nclips: {pose: {mirrors: {1: 0}}}\n",
    "clip name": "clips: {pose: {output_name: aliased}}\n",
    "clip all": "stored_directions: [0]\nclips: {pose: {stored_directions: all}}\n",
}


def fingerprint_with(text, **kwargs):
    return export_for(
        text, clips=(clip(0, "pose", t1=0.5),), view=views.View(4, 0.0), **kwargs
    ).document["fingerprint"]


@pytest.mark.parametrize("name", list(CHANGES))
def test_changing_any_recorded_new_setting_changes_the_fingerprint(name):
    base = fingerprint_with("{}\n")
    text = CHANGES[name]
    directory = outputs.Directory() if "frames" in text or "atlas" in text else None
    assert fingerprint_with(text, destination=directory) != base


def test_inactive_templates_are_hashed_even_when_the_formats_do_not_use_them():
    base = fingerprint_with("{}\n")
    assert fingerprint_with("export: {atlas_path: 'other/{clip}{map}.png'}\n") != base


def test_the_same_recorded_settings_keep_the_fingerprint_whatever_the_destination():
    positional = export_for(
        "{}\n", clips=(POSE,), view=RING4, destination=outputs.Positional("hero.png")
    )
    renamed = export_for(
        "{}\n", clips=(POSE,), view=RING4, destination=outputs.Positional("other.png")
    )
    directory = export_for(
        "{}\n", clips=(POSE,), view=RING4, destination=outputs.Directory()
    )
    moved = Source(SOURCE.path.with_name("elsewhere.glb"), SHA, 3)
    relocated = export_for("{}\n", clips=(POSE,), view=RING4, source=moved)
    fingerprints = {
        x.document["fingerprint"] for x in (positional, renamed, directory, relocated)
    }
    assert len(fingerprints) == 1
    paths = lambda x: [a["path"] for a in x.document["artifacts"]]  # noqa: E731
    assert paths(positional) != paths(renamed) != paths(directory)
    assert relocated.document["source"]["file"] == "elsewhere.glb"
    assert positional.data != renamed.data


def test_switching_frames_and_atlases_to_the_sheet_changes_settings_and_hash():
    directory = full()
    sheet = full(
        text=FULL.replace("formats: [atlases, frames, sheet]", "formats: [sheet]"),
        destination=outputs.Positional("hero.png"),
    )
    assert sheet.document["settings"]["export"]["formats"] == ["sheet"]
    assert sheet.document["fingerprint"] != directory.document["fingerprint"]


def test_a_generator_or_source_digest_change_changes_the_fingerprint():
    base = fingerprint_with("{}\n")
    other = GENERATOR | {"blender": "5.2.3"}
    assert fingerprint_with("{}\n", generator=other) != base
    assert fingerprint_with("{}\n", source=Source(SOURCE.path, "cd" * 32, 0)) != base


def test_artifact_paths_and_sizes_are_outside_the_fingerprint():
    narrow = export_for("{}\n", clips=(POSE,), view=RING4, cell=(3, 2))
    # A cell is a setting; only artifact-only changes may keep the hash.
    same = export_for(
        "{}\n", clips=(POSE,), view=RING4, destination=outputs.Positional("z.png")
    )
    assert narrow.document["fingerprint"] == same.document["fingerprint"]


# Positional output keeps its legacy names beside informational ones


def test_positional_output_names_may_collide_or_name_devices_without_refusal():
    text = (
        "direction_names: {0: CON, 1: con, 2: CON, 3: aux.txt}\n"
        "clips: {walk: {output_name: NUL}, idle: {output_name: nul}}\n"
    )
    x = export_for(
        text,
        clips=(clip(0, "walk"), clip(1, "idle")),
        view=RING4,
        destination=outputs.Positional("hero.png"),
    )
    document = x.document
    assert [d["output_name"] for d in document["directions"]] == [
        "CON",
        "con",
        "CON",
        "aux.txt",
    ]
    assert [c["output_name"] for c in document["clips"]] == ["NUL", "nul"]
    assert [a["path"] for a in document["artifacts"]] == [
        "hero.png",
        "hero.normal.png",
        "hero.walk.gif",
        "hero.idle.gif",
    ]


def test_the_same_names_are_refused_when_a_directory_is_chosen():
    from moskophoros.usage import UsageError

    with pytest.raises(UsageError):
        export_for(
            "direction_names: {0: CON}\nexport: {formats: [frames]}\n",
            clips=(POSE,),
            view=RING4,
            destination=outputs.Directory(),
        )


# The capture job's settings stay as they were


LEGACY_KEYS = {
    "view",
    "camera",
    "model_yaw_deg",
    "fps",
    "frames",
    "supersample",
    "pixels_per_meter",
    "cell",
    "ground_m",
    "ground_px",
    "root_motion",
    "shade",
    "clips",
}


def job_settings(x):
    selected = [c.selected for c in x.request.clips]
    return backend.settings_document(x.settings, selected)


def test_the_capture_settings_do_not_change_with_manifest_only_fields():
    base = export_for(
        "clips: {walk: {frames: 2}}\n", clips=(clip(0, "walk"),), view=RING4
    )
    variants = [
        "clips: {walk: {frames: 2, fps: 6}}\n",
        "clips: {walk: {frames: 2, output_name: x}}\n",
        "clips: {walk: {frames: 2, stored_directions: [1]}}\n",
        "clips: {walk: {frames: 2, stored_directions: [1, 0], mirrors: {3: 1}}}\n",
        "direction_names: {0: a}\nclips: {walk: {frames: 2}}\n",
        "stored_directions: [0]\nmirrors: {1: 0}\nclips: {walk: {frames: 2}}\n",
        "export: {formats: [frames], atlas_padding: 4}\nclips: {walk: {frames: 2}}\n",
        "export: {sheet_path: 'q{map}.png'}\nclips: {walk: {frames: 2}}\n",
    ]
    wanted = json.dumps(job_settings(base))
    for text in variants:
        x = export_for(
            text,
            clips=(clip(0, "walk"),),
            view=RING4,
            destination=outputs.Directory() if "formats" in text else None,
        )
        assert json.dumps(job_settings(x)) == wanted, text
        assert x.data != base.data


def test_no_new_key_reaches_the_capture_job_settings():
    x = full()
    document = job_settings(x)
    assert set(document) == LEGACY_KEYS
    assert all(set(c) == {"name", "loop", "frames"} for c in document["clips"])
    assert document["fps"] == 12.0


def test_the_manifest_settings_are_built_without_the_capture_settings_document(
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("settings_document was called")

    monkeypatch.setattr(backend, "settings_document", forbidden)
    monkeypatch.setattr(export, "settings_document", forbidden)
    x = export_for("{}\n", clips=(POSE,), view=RING4)
    assert x.document["settings"]["fps"] == 12.0


# Internal consistency


def test_the_writer_refuses_settings_that_are_not_fitted():
    x = export_for("{}\n", clips=(POSE,), view=RING4, encode=False)
    from dataclasses import replace

    options = dict(x.options)
    options["settings"] = replace(x.settings, cell=None)
    with pytest.raises(ValueError, match="not fitted"):
        manifest.encode(**options)


def test_the_writer_refuses_to_write_a_manifest_the_reader_would_refuse():
    x = export_for("{}\n", clips=(POSE,), view=RING4, encode=False)
    options = dict(x.options)
    options["generator"] = {**GENERATOR, "tool": ""}
    with pytest.raises(ValueError, match="invalid"):
        manifest.encode(**options)


def test_the_style_record_is_written_as_given():
    style = PLAIN | {"reduce": "mode", "edges": "soft"}
    x = export_for("{}\n", clips=(POSE,), view=RING4, style=style)
    assert x.document["settings"]["style"] == style
    assert copy.deepcopy(x.document["settings"]["style"]) == style
