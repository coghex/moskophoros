"""The strict reader of `moskophoros.export/1` (export design P-8, part 4;
P-8a): what it refuses, with the file and the field, and what it restores."""

import copy
import json
import subprocess
from pathlib import Path

import pytest
from manifest_fixture import (
    LIGHT,
    PLAIN,
    clip,
    dump,
    export_for,
    seal,
)

from moskophoros import cli, exportsettings, manifest, outputs, views
from moskophoros.usage import UsageError

RING4 = views.View(4, 0.0)
POSE = clip(0, "pose", t1=0.0)
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
CLIPS = (clip(0, "walk"), clip(1, "idle"), clip(2, "jump", t1=2.0, one_shot=True))
_cache = {}


def base():
    """The full export's document, read once; callers copy it."""
    if "x" not in _cache:
        _cache["x"] = export_for(
            FULL,
            clips=CLIPS,
            view=RING4,
            depth=True,
            light=LIGHT,
            destination=outputs.Directory(),
        )
    return _cache["x"]


def document():
    return copy.deepcopy(base().document)


def refused(data, label="the manifest"):
    with pytest.raises(UsageError) as raised:
        manifest.decode(data, label)
    message = str(raised.value)
    assert message.startswith(f"{label}: ")
    assert raised.value.exit_code == 2
    return message


def find(doc, kind, channel, clip_name=None, direction=None, index=None):
    for position, artifact in enumerate(doc["artifacts"]):
        if (
            artifact["kind"] == kind
            and artifact["channel"] == channel
            and artifact.get("clip") == clip_name
            and artifact.get("direction") == direction
            and artifact.get("index") == index
        ):
            return position
    raise LookupError((kind, channel, clip_name, direction, index))


def frame_record(doc, clip_name, direction, index):
    return next(
        f
        for f in doc["frames"]
        if (f["clip"], f["direction"], f["index"]) == (clip_name, direction, index)
    )


def walk_to(value, path):
    for step in path[:-1]:
        value = value[step]
    return value, path[-1]


def edited(*operations, sealed=False):
    """The full document with `operations` applied, as bytes: `("set", path,
    value)`, `("del", path)` or `("add", path, value)`; `sealed` recomputes
    the fingerprint after them."""
    doc = document()
    for operation, path, *value in operations:
        container, last = walk_to(doc, path)
        if operation == "del":
            del container[last]
        else:
            container[last] = value[0]
    return dump(seal(doc) if sealed else doc)


# The file and its schema


def test_a_valid_manifest_reads_back_with_its_document():
    loaded = manifest.decode(base().data)
    assert loaded.document["schema"] == "moskophoros.export/1"
    assert dict(loaded.document) == base().document
    assert loaded.reused.clip == ("walk", "idle", "jump")
    assert loaded.reused.once == ("jump",)


def test_read_names_the_file_in_every_problem(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_bytes(edited(("del", ("frames",))))
    with pytest.raises(UsageError) as raised:
        manifest.read(path)
    assert str(raised.value).startswith(f"manifest {str(path)!r}: ")
    assert "frames: missing" in str(raised.value)
    with pytest.raises(UsageError, match="cannot be read"):
        manifest.read(tmp_path / "absent.json")


def test_read_needs_nothing_beside_the_manifest(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_bytes(base().data)
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: started.append(a))
    written = []
    monkeypatch.setattr(Path, "write_bytes", lambda *a, **k: written.append(a))
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: written.append(a))
    loaded = manifest.read(path)
    assert loaded.label == f"manifest {str(path)!r}"
    assert not started and not written
    assert sorted(p.name for p in tmp_path.iterdir()) == ["manifest.json"]


def test_a_manifest_with_a_palette_and_library_loads_without_their_files(tmp_path):
    from test_manifest_styles import styled

    x = styled()
    path = tmp_path / "manifest.json"
    path.write_bytes(x.data)
    assert x.document["settings"]["style"]["palette"]["source"] == "colors.hex"
    assert manifest.read(path).reused.palette.source == "colors.hex"


def test_the_sheet_15_schema_is_refused_naming_both_schemas():
    data = dump({"schema": "moskophoros.sheet/15", "settings": {}})
    message = refused(data)
    assert "moskophoros.sheet/15" in message and "moskophoros.export/1" in message
    assert "generate it again from the model or project" in message


def test_another_old_sheet_schema_is_refused_the_same_way():
    message = refused(dump({"schema": "moskophoros.sheet/14"}))
    assert "moskophoros.sheet/14" in message and "moskophoros.export/1" in message


@pytest.mark.parametrize(
    "data, problem",
    [
        pytest.param(b"\xff\xfe{}", "is not UTF-8", id="not utf-8"),
        pytest.param(b"{", "is not valid JSON", id="truncated"),
        pytest.param(b"[1]", "not a JSON object", id="array"),
        pytest.param(b"{}", "schema is missing", id="no schema"),
        pytest.param(b'{"schema": 5}', "schema is 5", id="numeric schema"),
        pytest.param(
            b'{"schema": "moskophoros.export/2"}',
            'schema is "moskophoros.export/2"',
            id="future schema",
        ),
        pytest.param(
            b'{"schema": "x", "schema": "y"}', "repeats the key 'schema'", id="repeat"
        ),
        pytest.param(
            b"[" * 200000 + b"]" * 200000, "nested too deeply", id="deeply nested"
        ),
    ],
)
def test_unreadable_json_and_unknown_schemas_are_refused(data, problem):
    assert problem in refused(data)


def test_a_duplicate_key_anywhere_is_refused():
    text = base().data.decode().replace('"x": 2,', '"x": 2, "x": 2,', 1)
    assert text != base().data.decode()
    assert "repeats the key 'x'" in refused(text.encode())


def test_not_a_number_and_infinity_constants_are_refused():
    text = base().data.decode()
    assert "NaN is not a JSON value" in refused(
        text.replace('"time_s": 0.0', '"time_s": NaN', 1).encode()
    )
    assert "Infinity is not a JSON value" in refused(
        text.replace('"duration_s": 1.0', '"duration_s": Infinity', 1).encode()
    )


def test_a_number_too_large_to_be_finite_is_refused_with_its_field():
    text = base().data.decode()
    message = refused(text.replace('"time_s": 0.0', '"time_s": 1e999', 1).encode())
    assert "frames[0].time_s: expected a finite number" in message


# Members and types


TOP = ["schema", "generator", "source", "subject", "variant", "settings"]


@pytest.mark.parametrize(
    "name", ["generator", "source", "settings", "artifacts", "frames"]
)
def test_a_missing_top_level_member_is_named(name):
    assert f"{name}: missing" in refused(edited(("del", (name,))))


def test_an_unknown_top_level_member_is_named():
    assert "image: unknown member" in refused(edited(("set", ("image",), {})))


STRUCTURE = [
    (
        "empty tool",
        [("set", ("generator", "tool"), "")],
        "generator.tool: expected a nonempty string",
    ),
    (
        "missing seed",
        [("del", ("generator", "color", "seed"))],
        "generator.color.seed: missing",
    ),
    (
        "extra color",
        [("set", ("generator", "color", "x"), 1)],
        "generator.color.x: unknown member",
    ),
    (
        "boolean width",
        [("set", ("generator", "shade", "filter_width_px"), True)],
        "generator.shade.filter_width_px: expected a finite number",
    ),
    (
        "zero width",
        [("set", ("generator", "shade", "filter_width_px"), 0)],
        "generator.shade.filter_width_px: expected a finite number greater than 0",
    ),
    (
        "negative seed",
        [("set", ("generator", "color", "seed"), -1)],
        "generator.color.seed: expected a whole number",
    ),
    (
        "bad digest",
        [("set", ("source", "sha256"), "XYZ")],
        "source.sha256: expected 64 lowercase hexadecimal digits",
    ),
    (
        "path file",
        [("set", ("source", "file"), "a/b.glb")],
        "source.file: expected a nonempty base filename",
    ),
    (
        "numeric subject",
        [("set", ("subject",), 5)],
        "subject: expected a nonempty string",
    ),
    ("other variant", [("set", ("variant",), "other")], "variant: expected 'default'"),
    (
        "bad fingerprint",
        [("set", ("fingerprint",), "md5:00")],
        "fingerprint: expected sha256:",
    ),
    (
        "null cell",
        [("set", ("settings", "cell"), None)],
        "settings.cell: must be set, got null",
    ),
    (
        "null scale",
        [("set", ("settings", "pixels_per_meter"), None)],
        "settings.pixels_per_meter: must be set, got null",
    ),
    (
        "null ground pixel",
        [("set", ("settings", "ground_px"), None)],
        "settings.ground_px: must be set, got null",
    ),
    ("no export", [("del", ("settings", "export"))], "settings.export: missing"),
    (
        "unknown setting",
        [("set", ("settings", "extra"), 1)],
        "settings.extra: unknown field",
    ),
    (
        "boolean fps",
        [("set", ("settings", "fps"), True)],
        "settings.fps: expected a number",
    ),
    (
        "string frames",
        [("set", ("settings", "frames"), "8")],
        "settings.frames: expected a whole number 1 or more",
    ),
    (
        "null stored",
        [("set", ("settings", "stored_directions"), None)],
        "settings.stored_directions: must be set, got null",
    ),
    (
        "empty stored",
        [("set", ("settings", "stored_directions"), [])],
        "settings.stored_directions: expected all or a nonempty list",
    ),
    (
        "repeated stored",
        [("set", ("settings", "stored_directions"), [1, 1])],
        "the direction 1 is listed twice",
    ),
    (
        "string stored",
        [("set", ("settings", "stored_directions"), ["1"])],
        "expected a direction index",
    ),
    (
        "boolean stored",
        [("set", ("settings", "stored_directions"), [True])],
        "expected a direction index",
    ),
    (
        "keyed names",
        [("set", ("settings", "direction_names"), {"1": "a"})],
        "settings.direction_names: expected an array of names",
    ),
    (
        "null names",
        [("set", ("settings", "direction_names"), None)],
        "settings.direction_names: must be set, got null",
    ),
    (
        "boolean name index",
        [("set", ("settings", "direction_names"), [{"index": True, "name": "a"}])],
        "[0].index: expected a whole number",
    ),
    (
        "string name index",
        [("set", ("settings", "direction_names"), [{"index": "1", "name": "a"}])],
        "[0].index: expected a whole number",
    ),
    (
        "repeated names",
        [
            (
                "set",
                ("settings", "direction_names"),
                [{"index": 1, "name": "a"}, {"index": 1, "name": "b"}],
            )
        ],
        "[1].index: 1 is listed twice",
    ),
    (
        "unsorted names",
        [
            (
                "set",
                ("settings", "direction_names"),
                [{"index": 2, "name": "a"}, {"index": 1, "name": "b"}],
            )
        ],
        "[1].index: 1 follows 2; the entries must be sorted by index",
    ),
    (
        "extra name key",
        [("set", ("settings", "direction_names"), [{"index": 1, "name": "a", "x": 1}])],
        "[0]: expected exactly index, name",
    ),
    (
        "numeric name",
        [("set", ("settings", "direction_names"), [{"index": 1, "name": 5}])],
        "expected a name",
    ),
    (
        "keyed mirrors",
        [("set", ("settings", "mirrors"), {"3": 1})],
        "settings.mirrors: expected an array of mirrors",
    ),
    (
        "null mirrors",
        [("set", ("settings", "mirrors"), None)],
        "settings.mirrors: must be set, got null",
    ),
    (
        "repeated targets",
        [
            (
                "set",
                ("settings", "mirrors"),
                [{"target": 3, "source": 1}, {"target": 3, "source": 2}],
            )
        ],
        "[1].target: 3 is listed twice",
    ),
    (
        "unsorted targets",
        [
            (
                "set",
                ("settings", "mirrors"),
                [{"target": 3, "source": 1}, {"target": 2, "source": 1}],
            )
        ],
        "[1].target: 2 follows 3",
    ),
    (
        "boolean target",
        [("set", ("settings", "mirrors"), [{"target": True, "source": 1}])],
        "[0].target: expected a whole number",
    ),
    (
        "boolean source",
        [("set", ("settings", "mirrors"), [{"target": 3, "source": True}])],
        "expected a stored source direction index",
    ),
    (
        "formats order",
        [("set", ("settings", "export", "formats"), ["frames", "sheet", "atlases"])],
        "expected the formats in the order sheet, frames, atlases",
    ),
    (
        "repeated format",
        [("set", ("settings", "export", "formats"), ["sheet", "sheet"])],
        "the format sheet is listed twice",
    ),
    (
        "empty formats",
        [("set", ("settings", "export", "formats"), [])],
        "expected a nonempty list of sheet, frames or atlases",
    ),
    (
        "unknown format",
        [("set", ("settings", "export", "formats"), ["png"])],
        "settings.export.formats",
    ),
    (
        "bad template",
        [("set", ("settings", "export", "frame_path"), "{nope}.png")],
        "settings.export.frame_path: the template",
    ),
    (
        "null template",
        [("set", ("settings", "export", "sheet_path"), None)],
        "settings.export.sheet_path: must be set, got null",
    ),
    (
        "big padding",
        [("set", ("settings", "export", "atlas_padding"), 65)],
        "settings.export.atlas_padding: expected a whole number from 0 to 64",
    ),
    (
        "boolean padding",
        [("set", ("settings", "export", "atlas_padding"), True)],
        "settings.export.atlas_padding",
    ),
    (
        "no clips",
        [("set", ("settings", "clips"), [])],
        "settings.clips: expected a nonempty list of clips",
    ),
    (
        "clip missing key",
        [("del", ("settings", "clips", 0, "fps"))],
        "settings.clips: [0]: expected exactly name, loop, frames, fps, stored_directions, mirrors, output_name",
    ),
    (
        "clip repeated",
        [("set", ("settings", "clips", 1, "name"), "walk")],
        '[1].name: the clip "walk" is recorded twice',
    ),
    (
        "clip loop",
        [("set", ("settings", "clips", 0, "loop"), "yes")],
        "[0].loop: expected true or false",
    ),
    (
        "clip zero frames",
        [("set", ("settings", "clips", 0, "frames"), 0)],
        "[0].frames: expected a whole number 1 or more, auto or null",
    ),
    (
        "clip bad fps",
        [("set", ("settings", "clips", 0, "fps"), -1)],
        "[0].fps: expected a finite number greater than 0",
    ),
    (
        "clip boolean fps",
        [("set", ("settings", "clips", 0, "fps"), True)],
        "[0].fps: expected a finite number greater than 0",
    ),
    (
        "clip empty stored",
        [("set", ("settings", "clips", 0, "stored_directions"), [])],
        "[0].stored_directions",
    ),
    (
        "clip mirrors keyed",
        [("set", ("settings", "clips", 0, "mirrors"), {"3": 1})],
        "[0].mirrors: expected an array of mirrors",
    ),
    (
        "clip numeric alias",
        [("set", ("settings", "clips", 0, "output_name"), 5)],
        "[0].output_name: expected a name or null",
    ),
    (
        "view directions",
        [("set", ("settings", "view", "directions"), True)],
        "settings.view.directions",
    ),
    (
        "bad palette",
        [
            (
                "set",
                ("settings", "style", "palette"),
                {"source": "p.hex", "sha256": "0" * 64, "colors": ["#GG0000"]},
            )
        ],
        "settings.style.palette.colors: entry 1",
    ),
    (
        "library without palette",
        [
            (
                "set",
                ("settings", "style", "materials"),
                {
                    "source": "m.yaml",
                    "sha256": "0" * 64,
                    "ramps": {},
                    "default": None,
                    "materials": {},
                },
            )
        ],
        "a library needs a palette, but the palette is null",
    ),
    (
        "unknown kind",
        [("set", ("artifacts", 0, "kind"), "image")],
        "artifacts[0].kind: expected sheet, atlas, frame or preview",
    ),
    (
        "artifact missing",
        [("del", ("artifacts", 0, "width"))],
        "artifacts[0].width: missing",
    ),
    (
        "irrelevant sheet key",
        [("set", ("artifacts", 0, "clip"), "walk")],
        "artifacts[0].clip: unknown member",
    ),
    (
        "null suffix",
        [("set", ("artifacts", 0, "padding"), None)],
        "artifacts[0].padding: expected a whole number",
    ),
    (
        "preview with cell",
        [("set", ("artifacts", 47, "cell"), {"width": 1, "height": 1})],
        "artifacts[47].cell: unknown member",
    ),
    (
        "zero width",
        [("set", ("artifacts", 0, "width"), 0)],
        "artifacts[0].width: expected a whole number 1 or more",
    ),
    (
        "boolean height",
        [("set", ("artifacts", 0, "height"), True)],
        "artifacts[0].height",
    ),
    (
        "png flat",
        [("set", ("artifacts", 0, "channel"), "flat")],
        "artifacts[0].channel: expected one of color, normal, depth",
    ),
    (
        "gif colour",
        [("set", ("artifacts", 47, "channel"), "color")],
        "artifacts[47].channel: expected one of flat, lit",
    ),
    ("empty path", [("set", ("artifacts", 0, "path"), "")], "artifacts[0].path"),
    ("rooted path", [("set", ("artifacts", 0, "path"), "/x.png")], "artifacts[0].path"),
    (
        "dotted path",
        [("set", ("artifacts", 0, "path"), "a/../x.png")],
        "artifacts[0].path",
    ),
    (
        "empty component",
        [("set", ("artifacts", 0, "path"), "a//x.png")],
        "artifacts[0].path",
    ),
    (
        "zero cell",
        [("set", ("artifacts", 0, "cell", "width"), 0)],
        "artifacts[0].cell.width",
    ),
    (
        "null cell record",
        [("set", ("artifacts", 0, "cell"), None)],
        "artifacts[0].cell: expected an object",
    ),
    (
        "direction object",
        [("set", ("directions",), {})],
        "directions: expected a nonempty array",
    ),
    (
        "direction missing",
        [("del", ("directions", 0, "label"))],
        "directions[0].label: missing",
    ),
    (
        "direction boolean",
        [("set", ("directions", 0, "index"), True)],
        "directions[0].index",
    ),
    (
        "direction label",
        [("set", ("directions", 0, "label"), 5)],
        "directions[0].label",
    ),
    (
        "clip null mirrors",
        [("set", ("clips", 0, "mirrors"), None)],
        "clips[0].mirrors: expected an array",
    ),
    (
        "clip zero count",
        [("set", ("clips", 0, "frame_count"), 0)],
        "clips[0].frame_count: expected a whole number 1 or more",
    ),
    (
        "clip empty stored",
        [("set", ("clips", 0, "stored_directions"), [])],
        "clips[0].stored_directions: expected a nonempty array",
    ),
    (
        "clip null stored",
        [("set", ("clips", 0, "stored_directions"), None)],
        "clips[0].stored_directions: expected a nonempty array",
    ),
    (
        "clip boolean index",
        [("set", ("clips", 0, "stored_directions", 0), True)],
        "clips[0].stored_directions[0]",
    ),
    (
        "negative duration",
        [("set", ("clips", 0, "duration_s"), -1.0)],
        "clips[0].duration_s: expected a finite number at least 0",
    ),
    (
        "zero fps",
        [("set", ("clips", 0, "fps"), 0)],
        "clips[0].fps: expected a finite number greater than 0",
    ),
    (
        "mirror transform",
        [("set", ("clips", 2, "mirrors", 0, "transform"), "flip-y")],
        "clips[2].mirrors[0].transform: expected 'flip-x'",
    ),
    (
        "mirror ground",
        [("del", ("clips", 2, "mirrors", 0, "ground_px", "y"))],
        "clips[2].mirrors[0].ground_px.y: missing",
    ),
    ("frames object", [("set", ("frames",), {})], "frames: expected an array"),
    ("frame boolean", [("set", ("frames", 0, "index"), True)], "frames[0].index"),
    ("frame extra", [("set", ("frames", 0, "x"), 1)], "frames[0].x: unknown member"),
    (
        "locations null",
        [("set", ("frames", 0, "locations"), None)],
        "frames[0].locations: expected an array",
    ),
    (
        "location boolean",
        [("set", ("frames", 0, "locations", 0, "artifact"), True)],
        "frames[0].locations[0].artifact",
    ),
    (
        "location zero size",
        [("set", ("frames", 0, "locations", 0, "w"), 0)],
        "frames[0].locations[0].w: expected a whole number 1 or more",
    ),
    (
        "location negative",
        [("set", ("frames", 0, "locations", 0, "x"), -1)],
        "frames[0].locations[0].x",
    ),
    (
        "location extra",
        [("set", ("frames", 0, "locations", 0, "z"), 1)],
        "frames[0].locations[0].z: unknown member",
    ),
]


@pytest.mark.parametrize(
    "operations, problem",
    [pytest.param(ops, problem, id=name) for name, ops, problem in STRUCTURE],
)
def test_a_malformed_member_is_refused_with_its_field(operations, problem):
    assert problem in refused(edited(*operations))


def test_two_artifacts_may_not_share_a_path():
    path = base().document["artifacts"][0]["path"]
    message = refused(edited(("set", ("artifacts", 1, "path"), path)))
    assert f"artifacts[1].path: {path!r} is also the path of artifacts[0]" in message


def test_several_problems_are_listed_together_up_to_a_limit():
    doc = document()
    for position in range(10):
        doc["frames"][position]["index"] = True
    for position in range(4):
        doc["directions"][position]["index"] = True
    message = refused(dump(doc))
    assert message.count(";") >= 9
    assert "and " in message and "more" in message


# Inline styles stay checked wherever an override would replace them


def test_a_malformed_inline_library_is_refused_whatever_could_override_it(tmp_path):
    from test_manifest_styles import styled

    doc = copy.deepcopy(styled().document)
    materials = doc["settings"]["style"]["materials"]
    materials["materials"]["steel"] = {"uses": "no-such-ramp"}
    message = refused(dump(seal(doc)))
    assert "settings.style.materials:" in message
    doc = copy.deepcopy(styled().document)
    doc["settings"]["style"]["materials"]["ramps"]["metal"] = [1, 999]
    assert "settings.style.materials:" in refused(dump(seal(doc)))
    doc = copy.deepcopy(styled().document)
    doc["settings"]["style"]["palette"]["colors"][0] = "#ABCDEF"
    assert "settings.style.palette.colors: entry 1" in refused(dump(seal(doc)))
    doc = copy.deepcopy(styled().document)
    del doc["settings"]["style"]["materials"]["materials"]["steel"]["shade"]["range"]
    # A partial shade is allowed; a shade leaf outside its bounds is not.
    doc["settings"]["style"]["materials"]["materials"]["steel"]["shade"][
        "convexity_weight"
    ] = -1
    assert "settings.style.materials:" in refused(dump(seal(doc)))


# The records the settings imply


def test_the_fingerprint_must_be_the_hash_of_the_recorded_generator_settings_and_digest():
    for operation in (
        ("set", ("settings", "supersample"), 5),
        ("set", ("generator", "blender"), "5.2.3"),
        ("set", ("source", "sha256"), "cd" * 32),
        ("set", ("settings", "export", "atlas_path"), "other/{clip}{map}.png"),
    ):
        message = refused(edited(operation))
        assert "fingerprint: is sha256:" in message, operation
        assert "hash to sha256:" in message


def test_a_different_generator_than_the_running_tool_is_not_an_error():
    doc = document()
    doc["generator"]["version"] = "9.9.9"
    doc["generator"]["blender"] = "6.0.0"
    loaded = manifest.decode(dump(seal(doc)))
    assert loaded.document["generator"]["version"] == "9.9.9"


def test_the_artifact_paths_and_sizes_are_outside_the_fingerprint():
    doc = document()
    doc["artifacts"][0]["path"] = "elsewhere/sheet.png"
    manifest.decode(dump(doc))
    doc["source"]["file"] = "renamed.glb"
    manifest.decode(dump(doc))


DIRECTIONS = [
    (
        "angle",
        [("set", ("directions", 1, "angle_deg"), 91.0)],
        "directions[1].angle_deg: expected 90.0, got 91.0",
    ),
    (
        "label",
        [("set", ("directions", 1, "label"), "west")],
        "directions[1].label: expected 'east', got 'west'",
    ),
    (
        "null label",
        [("set", ("directions", 1, "label"), None)],
        "directions[1].label: expected 'east', got None",
    ),
    (
        "name",
        [("set", ("directions", 1, "output_name"), "east")],
        "directions[1].output_name: expected 'right', got 'east'",
    ),
    (
        "index",
        [("set", ("directions", 1, "index"), 5)],
        "directions[1].index: expected 1, got 5",
    ),
    ("missing", [("del", ("directions", 3))], "directions[3]: expected"),
    (
        "extra",
        [
            (
                "set",
                ("directions", 4),
                {"index": 4, "angle_deg": 0.0, "label": None, "output_name": "x"},
            )
        ],
        "directions[4]: expected None, got",
    ),
]


@pytest.mark.parametrize(
    "operations, problem",
    [pytest.param(ops, problem, id=name) for name, ops, problem in DIRECTIONS],
)
def test_the_directions_must_be_the_recorded_views_ring_with_resolved_names(
    operations, problem
):
    doc = document()
    for operation, path, *value in operations:
        container, last = walk_to(doc, path)
        if operation == "del":
            del container[last]
        elif isinstance(container, list) and last == len(container):
            container.append(value[0])
        else:
            container[last] = value[0]
    assert problem in refused(dump(doc))


CLIPS_RECORDS = [
    (
        "name",
        [("set", ("clips", 0, "name"), "run")],
        "clips[0].name: expected 'walk', got 'run'",
    ),
    (
        "loop",
        [("set", ("clips", 2, "loop"), True)],
        "clips[2].loop: expected False, got True",
    ),
    (
        "count",
        [("set", ("clips", 0, "frame_count"), 3)],
        "clips[0].frame_count: expected 2, got 3",
    ),
    ("duration", [("set", ("clips", 0, "duration_s"), 2.0)], "clips[0]"),
    (
        "frame duration",
        [("set", ("clips", 0, "frame_duration_s"), 0.5)],
        "clips[0].frame_duration_s: expected 0.16666666666666666, got 0.5",
    ),
    (
        "time scale",
        [("set", ("clips", 0, "time_scale"), 2.0)],
        "clips[0].time_scale: expected 3.0, got 2.0",
    ),
    (
        "output name",
        [("set", ("clips", 0, "output_name"), "walk")],
        "clips[0].output_name: expected 'stride', got 'walk'",
    ),
    (
        "fps",
        [("set", ("clips", 1, "fps"), 6.0)],
        "clips[1].fps: expected 12.0, got 6.0",
    ),
    (
        "stored order",
        [("set", ("clips", 0, "stored_directions"), [0, 1])],
        "clips[0].stored_directions[0]: expected 1, got 0",
    ),
    (
        "stored subset",
        [("set", ("clips", 0, "stored_directions"), [1])],
        "clips[0].stored_directions",
    ),
    (
        "mirror anchor",
        [("set", ("clips", 2, "mirrors", 0, "ground_px", "x"), 1)],
        "clips[2].mirrors[0].ground_px.x: expected 2, got 1",
    ),
    (
        "mirror target",
        [("set", ("clips", 2, "mirrors", 0, "target"), 1)],
        "clips[2].mirrors[0].target: expected 3, got 1",
    ),
    (
        "mirror missing",
        [("set", ("clips", 2, "mirrors"), [])],
        "clips[2].mirrors[0]: expected",
    ),
    (
        "fake mirror",
        [
            (
                "set",
                ("clips", 1, "mirrors"),
                [
                    {
                        "target": 3,
                        "source": 2,
                        "transform": "flip-x",
                        "ground_px": {"x": 2, "y": 2},
                    }
                ],
            )
        ],
        "clips[1].mirrors[0]: expected None, got",
    ),
    (
        "inherited mirror dropped",
        [("set", ("clips", 2, "mirrors"), [])],
        "clips[2].mirrors",
    ),
    ("order", None, "clips[0].name: expected"),
    ("count of clips", None, "clips: has 2 clips, but settings.clips selects 3"),
]


def apply(doc, operations):
    for operation, path, *value in operations:
        container, last = walk_to(doc, path)
        if operation == "del":
            del container[last]
        else:
            container[last] = value[0]


@pytest.mark.parametrize(
    "operations, problem",
    [pytest.param(ops, problem, id=name) for name, ops, problem in CLIPS_RECORDS],
)
def test_the_clip_records_must_be_what_the_recorded_settings_resolve_to(
    operations, problem
):
    doc = document()
    if operations is None:
        if "has 2 clips" in problem:
            del doc["clips"][2]
        else:
            doc["clips"][0], doc["clips"][1] = doc["clips"][1], doc["clips"][0]
    else:
        apply(doc, operations)
    message = refused(dump(doc))
    assert problem in message


def test_the_frame_timing_is_rederived_from_the_records_own_duration():
    doc = document()
    # A one-shot clip of 2 s at 12 fps with two samples: the formulas use
    # t1 - t0 only, so a different duration cannot keep these values.
    doc["clips"][2]["duration_s"] = 4.0
    message = refused(dump(doc))
    assert "clips[2]" in message and "time_scale" in message


SETTINGS_EDITS = [
    (
        "stored target",
        [("set", ("settings", "clips", 0, "mirrors"), [{"target": 1, "source": 0}])],
        "mirror 1 <- 0 replaces direction 1, which is stored, not omitted",
    ),
    (
        "unstored source",
        [("set", ("settings", "clips", 0, "mirrors"), [{"target": 3, "source": 2}])],
        "mirror 3 <- 2 takes its picture from direction 2, which is not stored",
    ),
    (
        "self mirror",
        [("set", ("settings", "clips", 0, "mirrors"), [{"target": 1, "source": 1}])],
        "which is stored, not omitted",
    ),
    (
        "chain",
        [
            ("set", ("settings", "clips", 0, "stored_directions"), [0]),
            (
                "set",
                ("settings", "clips", 0, "mirrors"),
                [{"target": 1, "source": 0}, {"target": 2, "source": 1}],
            ),
        ],
        "mirror 2 <- 1 takes its picture from direction 1, which is not stored",
    ),
    (
        "out of ring",
        [("set", ("settings", "clips", 0, "mirrors"), [{"target": 9, "source": 1}])],
        "the direction 9 is not one of the view's 4 directions",
    ),
    (
        "name out of ring",
        [("set", ("settings", "direction_names"), [{"index": 9, "name": "x"}])],
        "direction_names",
    ),
    (
        "stored out of ring",
        [("set", ("settings", "stored_directions"), [2, 9])],
        "the direction 9 is not one of the view's 4 directions",
    ),
    (
        "global mirror unstored",
        [("set", ("settings", "mirrors"), [{"target": 3, "source": 1}])],
        "which is not stored",
    ),
]


@pytest.mark.parametrize(
    "operations, problem",
    [pytest.param(ops, problem, id=name) for name, ops, problem in SETTINGS_EDITS],
)
def test_invalid_mirror_and_direction_references_are_refused(operations, problem):
    message = refused(edited(*operations, sealed=True))
    assert "settings" in message
    assert problem in message


def test_a_frame_count_far_beyond_the_records_is_refused_without_planning_it():
    message = refused(
        edited(("set", ("settings", "clips", 1, "frames"), 10**9), sealed=True)
    )
    assert "clips[1].frame_count: the settings sample about" in message
    auto = export_for("{}\n", clips=(clip(0, "walk"),), view=RING4).document
    auto["clips"][0]["duration_s"] = 1e300
    message = refused(dump(auto))
    assert "clips[0].frame_count: the settings sample about" in message
    # A long clip sampled to a small count is a valid document, though.
    long = document()
    long["clips"][1]["duration_s"] = 1e300
    long["clips"][1]["time_scale"] = 1e300 * 12.0
    assert refused(dump(long))


ARTIFACTS = [
    ("swapped", "swap", "artifacts[0].channel: expected 'color', got 'normal'"),
    ("missing", "drop", "artifacts: has 47 entries, but the recorded formats"),
    ("extra", "add", "artifacts: has 49 entries"),
    ("channel", "channel", "artifacts[1].channel: expected 'normal', got 'color'"),
    ("kind", "kind", "artifacts[0].kind: expected 'sheet', got 'atlas'"),
    ("width", "width", "artifacts[3].width: expected 10, got 11"),
    ("height", "height", "artifacts[0].height: expected 12, got 13"),
    ("padding", "padding", "artifacts[3].padding: expected 1, got 0"),
    ("sheet padding", "sheet padding", "artifacts[0].padding: expected 0, got 1"),
    ("cell", "cell", "artifacts[0].cell.width: expected 3, got 4"),
    ("clip", "clip", "artifacts[3].clip: expected 'walk', got 'idle'"),
    ("direction", "direction", "artifacts[12].direction: expected 1, got 0"),
    ("index", "index", "artifacts[12].index: expected 0, got 1"),
    ("preview dimensions", "preview", "artifacts[42].width: expected"),
    ("lit preview dropped", "lit", "artifacts: has 47 entries"),
]


def mutate_artifacts(doc, how):
    artifacts = doc["artifacts"]
    if how == "swap":
        artifacts[0], artifacts[1] = artifacts[1], artifacts[0]
    elif how == "drop":
        del artifacts[-1]
    elif how == "add":
        artifacts.append(copy.deepcopy(artifacts[-1]) | {"path": "extra.gif"})
    elif how == "channel":
        artifacts[1]["channel"] = "color"
    elif how == "kind":
        artifacts[0] = artifacts[3] | {"path": artifacts[0]["path"]}
    elif how == "width":
        artifacts[3]["width"] += 1
    elif how == "height":
        artifacts[0]["height"] += 1
    elif how == "padding":
        artifacts[3]["padding"] = 0
    elif how == "sheet padding":
        artifacts[0]["padding"] = 1
    elif how == "cell":
        artifacts[0]["cell"]["width"] = 4
    elif how == "clip":
        artifacts[3]["clip"] = "idle"
    elif how == "direction":
        artifacts[12]["direction"] = 0
    elif how == "index":
        artifacts[12]["index"] = 1
    elif how == "preview":
        artifacts[42]["width"] += 4
    elif how == "lit":
        del artifacts[43]


@pytest.mark.parametrize(
    "how, problem",
    [pytest.param(how, problem, id=name) for name, how, problem in ARTIFACTS],
)
def test_the_artifact_list_must_be_what_the_formats_maps_previews_and_clips_imply(
    how, problem
):
    doc = document()
    mutate_artifacts(doc, how)
    assert problem in refused(dump(doc))


def test_lit_previews_exist_only_with_previews_and_a_light_position():
    unlit = export_for("{}\n", clips=(POSE,), view=RING4).document
    assert [a["channel"] for a in unlit["artifacts"] if a["kind"] == "preview"] == [
        "flat"
    ]
    doc = copy.deepcopy(unlit)
    doc["artifacts"].append(
        copy.deepcopy(doc["artifacts"][-1]) | {"channel": "lit", "path": "x.lit.gif"}
    )
    assert "artifacts: has 4 entries, but" in refused(dump(doc))
    off = export_for("{}\n", clips=(POSE,), view=RING4, previews=False, light=LIGHT)
    assert [a["kind"] for a in off.document["artifacts"]] == ["sheet", "sheet"]


FRAMES = [
    (
        "missing",
        "drop",
        "frames: has 9 records, but the clips and stored directions imply 10",
    ),
    ("extra", "add", "frames: has 11 records"),
    (
        "swapped",
        "swap",
        "frames[0]: is clip 'walk', direction 1, sample 1, but the clips and stored directions put clip 'walk', direction 1, sample 0 here",
    ),
    ("duplicate", "duplicate", "frames[1]: is clip 'walk', direction 1, sample 0"),
    ("clip", "clip", "frames[0]: is clip 'idle'"),
    ("direction", "direction", "frames[0]: is clip 'walk', direction 3"),
    (
        "time",
        "time",
        "frames[2].time_s: is 0.25, but sample 0 of clip 'walk' is at 0.0 in another direction",
    ),
]


@pytest.mark.parametrize(
    "how, problem",
    [pytest.param(how, problem, id=name) for name, how, problem in FRAMES],
)
def test_the_frame_records_must_be_every_real_sample_once_in_order(how, problem):
    doc = document()
    frames = doc["frames"]
    if how == "drop":
        del frames[-1]
    elif how == "add":
        frames.append(copy.deepcopy(frames[-1]))
    elif how == "swap":
        frames[0], frames[1] = frames[1], frames[0]
    elif how == "duplicate":
        frames[1] = copy.deepcopy(frames[0])
    elif how == "clip":
        frames[0]["clip"] = "idle"
    elif how == "direction":
        frames[0]["direction"] = 3
    elif how == "time":
        frames[2]["time_s"] = 0.25
    assert problem in refused(dump(doc))


def test_an_alien_direction_with_no_stored_source_has_no_frame_record():
    doc = document()
    fake = copy.deepcopy(doc["frames"][0]) | {"direction": 3}
    doc["frames"].insert(1, fake)
    assert "frames:" in refused(dump(doc))


def location_cases():
    doc = document()
    first = frame_record(doc, "walk", 1, 0)
    sheet = find(doc, "sheet", "color")
    atlas = find(doc, "atlas", "color", "walk")
    mismatched_frame = find(doc, "frame", "color", "walk", 0, 0)
    other_clip_atlas = find(doc, "atlas", "color", "idle")
    preview = find(doc, "preview", "flat", "walk")
    return first, sheet, atlas, mismatched_frame, other_clip_atlas, preview


def test_locations_are_refused_for_every_reference_and_layout_violation():
    first, sheet, atlas, wrong_frame, other_clip, preview = location_cases()
    count = len(base().document["artifacts"])

    def case(change):
        doc = document()
        change(frame_record(doc, "walk", 1, 0)["locations"], doc)
        return refused(dump(doc))

    def at(places, artifact):
        return next(p for p in places if p["artifact"] == artifact)

    assert f"is not one of the {count} artifacts" in case(
        lambda places, doc: places[0].update(artifact=count)
    )
    assert "is a preview, which holds no sample" in case(
        lambda places, doc: places[0].update(artifact=preview)
    )
    assert f"artifacts[{other_clip}] belongs to clip 'idle', not 'walk'" in case(
        lambda places, doc: at(places, atlas).update(artifact=other_clip)
    )
    assert (
        f"artifacts[{wrong_frame}] is direction 0, sample 0, not direction 1, sample 0"
        in case(lambda places, doc: places[-3].update(artifact=wrong_frame))
    )
    assert "is 2x2, but the cell is 3x2" in case(
        lambda places, doc: places[0].update(w=2)
    )
    assert "lies outside artifacts[0]" in case(
        lambda places, doc: places[0].update(x=99)
    )
    assert "points into the padding of atlas" in case(
        lambda places, doc: at(places, atlas).update(x=0)
    )
    assert "points into the padding of atlas" in case(
        lambda places, doc: at(places, atlas).update(y=4)
    )
    assert "layout puts the sample at (0, 0)" in case(
        lambda places, doc: at(places, sheet).update(x=3)
    )
    assert "follows" in case(lambda places, doc: places.reverse())
    assert "is listed twice" in case(
        lambda places, doc: places.insert(1, copy.deepcopy(places[0]))
    )
    assert "does not hold exactly one location" in case(
        lambda places, doc: places.pop(1)
    )
    message = case(lambda places, doc: places.pop())
    assert "missing [" in message


def test_a_location_in_a_representation_the_sample_does_not_have_is_refused():
    doc = document()
    places = frame_record(doc, "walk", 1, 0)["locations"]
    spare = find(doc, "frame", "color", "walk", 1, 1)
    places.append({"artifact": spare, "x": 0, "y": 0, "w": 3, "h": 2})
    message = refused(dump(doc))
    assert "is direction 1, sample 1, not direction 1, sample 0" in message


def test_a_sample_in_the_sheet_is_located_by_its_clip_rows_not_a_guess():
    doc = document()
    place = next(
        p
        for p in frame_record(doc, "idle", 2, 0)["locations"]
        if p["artifact"] == find(doc, "sheet", "color")
    )
    place["y"] -= 2
    assert "layout puts the sample at (0, 4)" in refused(dump(doc))


# Mirrors need no new records and no camera refusal


def test_a_mirror_whose_camera_conditions_fail_still_loads():
    x = export_for(
        "stored_directions: [1]\nmirrors: {7: 1}\n",
        clips=(POSE,),
        view=views.View(8, 10.0),
    )
    loaded = manifest.decode(x.data)
    assert loaded.layer["mirrors"] == {7: 1}
    mirror = loaded.document["clips"][0]["mirrors"][0]
    assert (mirror["target"], mirror["source"]) == (7, 1)


# Reload into the settings layer


def test_the_reload_restores_every_supplied_override_and_the_inheritance_of_each():
    loaded = manifest.decode(base().data)
    layer = loaded.layer
    assert layer["stored_directions"] == (2, 0)
    assert dict(layer["direction_names"]) == {1: "right", 3: "west-side"}
    assert dict(layer["mirrors"]) == {3: 2}
    assert layer["export.formats"] == ("sheet", "frames", "atlases")
    assert layer["export.atlas_path"] == "atlas/{clip}{map}.png"
    assert layer["export.frame_path"].startswith("frames/")
    assert layer["export.atlas_padding"] == 1
    assert layer["fps"] == 12.0 and layer["frames"] == "auto"
    assert layer["clips"]["walk"] == {
        "frames": 2,
        "fps": 6.0,
        "stored_directions": (1, 0),
        "mirrors": {3: 1},
        "output_name": "stride",
    }
    assert layer["clips"]["idle"]["mirrors"] == {}
    assert layer["clips"]["idle"]["fps"] is None
    assert layer["clips"]["jump"] == {
        "frames": 2,
        "fps": None,
        "stored_directions": None,
        "mirrors": None,
        "output_name": None,
    }


def resolved_request(loaded, selected=None, layers=()):
    resolved = exportsettings.resolve([loaded.source(), *layers])
    chosen = exportsettings.request(resolved, "hero", selected or CLIPS, RING4)
    return resolved, chosen


def test_the_reloaded_layer_resolves_to_the_effective_values_it_was_written_from():
    resolved, chosen = resolved_request(manifest.decode(base().data))
    plans = {c.selected.clip.name: c for c in chosen.plan.clips}
    assert [c.fps for c in plans.values()] == [6.0, 12.0, 12.0]
    assert [d.index for d in plans["walk"].directions] == [1, 0]
    assert [d.index for d in plans["idle"].directions] == [2, 0]
    assert [(m.target, m.source) for m in plans["walk"].mirrors] == [(3, 1)]
    assert plans["idle"].mirrors == ()
    assert [(m.target, m.source) for m in plans["jump"].mirrors] == [(3, 2)]
    assert resolved.origins["stored_directions"] == base_label()


def base_label():
    return "the manifest"


def test_a_reselected_clip_keeps_its_loaded_overrides_and_a_new_one_has_none():
    loaded = manifest.decode(base().data)
    option = exportsettings.Source(
        exportsettings.OPTION,
        "option",
        {"clips": {"walk": {"frames": 3}}},
    )
    walk_only = (clip(0, "walk"), clip(3, "run"))
    resolved, chosen = resolved_request(loaded, walk_only, [option])
    walk, run = chosen.plan.clips
    assert walk.fps == 6.0
    assert [d.index for d in walk.directions] == [1, 0]
    assert [(m.target, m.source) for m in walk.mirrors] == [(3, 1)]
    assert resolved.clips["walk"].output_name == "stride"
    assert walk.sampling.frame_count == 3
    assert (run.fps, [d.index for d in run.directions]) == (12.0, [2, 0])
    assert "run" not in resolved.clips


def test_layers_above_the_reused_one_win_and_a_clips_own_fps_beats_a_global_option():
    loaded = manifest.decode(base().data)
    project = exportsettings.Source(
        exportsettings.PROJECT, "project", {"fps": 8.0, "frames": 4}
    )
    option = exportsettings.Source(
        exportsettings.OPTION, "option", {"fps": 24.0, "export.atlas_padding": 3}
    )
    resolved, chosen = resolved_request(loaded, layers=[project, option])
    assert resolved.fps == 24.0 and resolved.atlas_padding == 3
    plans = {c.selected.clip.name: c for c in chosen.plan.clips}
    assert plans["walk"].fps == 6.0
    assert plans["idle"].fps == 24.0
    assert plans["jump"].sampling.frame_count == 2
    assert plans["jump"].fps == 24.0


def test_normalized_vectors_and_fitted_values_come_back_exactly():
    loaded = manifest.decode(base().data)
    reused = loaded.reused
    recorded = base().document["settings"]
    assert list(reused.key_direction) == recorded["shade"]["key"]["direction"]
    assert list(reused.direction) == recorded["camera"]["direction"]
    assert reused.cell == (recorded["cell"]["width"], recorded["cell"]["height"])
    assert reused.ground_px == (recorded["ground_px"]["x"], recorded["ground_px"]["y"])
    assert reused.ppm == recorded["pixels_per_meter"]
    assert reused.clip == ("walk", "idle", "jump") and reused.once == ("jump",)
    assert dict(reused.clip_frames) == {"walk": 2, "idle": 1, "jump": 2}
    assert reused.palette is None and reused.materials is None


def parsed(*argv):
    return cli.parse_args([*argv, "hero.glb", "out.png"])


def test_an_explicit_clip_replaces_the_loaded_selection_and_its_one_shot_marks():
    reused = manifest.decode(base().data).reused
    options = cli.apply_settings(parsed("--clip", "idle"), reused)
    assert options.clip == ("idle",) and options.once == ()
    kept = cli.apply_settings(parsed(), reused)
    assert kept.clip == ("walk", "idle", "jump") and kept.once == ("jump",)


def test_an_explicit_once_replaces_the_marks_and_must_name_loaded_clips():
    reused = manifest.decode(base().data).reused
    options = cli.apply_settings(parsed("--once", "walk"), reused)
    assert options.once == ("walk",) and options.clip == ("walk", "idle", "jump")
    with pytest.raises(cli.UsageError):
        cli.apply_settings(parsed("--once", "swim"), reused)


def test_the_public_command_does_not_accept_an_export_manifest_yet(tmp_path, capsys):
    path = tmp_path / "manifest.json"
    path.write_bytes(base().data)
    with pytest.raises(cli.UsageError):
        cli.read_settings(path)
    assert "is not a moskophoros.sheet/15 document" in capsys.readouterr().err


def test_the_manifest_is_not_a_style_of_its_own():
    assert PLAIN["reduce"] == manifest.decode(base().data).reused.reduce


def test_top_level_mirrors_must_be_sorted_by_target():
    x = export_for(
        "stored_directions: [0]\nmirrors: {1: 0, 3: 0}\n",
        clips=(POSE,),
        view=RING4,
    )
    doc = copy.deepcopy(x.document)
    assert [m["target"] for m in doc["clips"][0]["mirrors"]] == [1, 3]
    doc["clips"][0]["mirrors"].reverse()
    assert "clips[0].mirrors[0].target: expected 1, got 3" in refused(dump(doc))


def test_a_clips_own_mirror_entries_must_be_sorted_by_target():
    x = export_for(
        "stored_directions: [0]\nclips: {pose: {mirrors: {1: 0, 3: 0}}}\n",
        clips=(POSE,),
        view=RING4,
    )
    doc = copy.deepcopy(x.document)
    doc["settings"]["clips"][0]["mirrors"].reverse()
    message = refused(dump(doc))
    assert "[0].mirrors" in message and "must be sorted by target" in message


def test_stored_directions_keep_their_supplied_order():
    x = export_for("stored_directions: [3, 1, 2]\n", clips=(POSE,), view=RING4)
    loaded = manifest.decode(x.data)
    assert loaded.layer["stored_directions"] == (3, 1, 2)
    assert x.document["clips"][0]["stored_directions"] == [3, 1, 2]


@pytest.mark.parametrize("name", ["CON.png", "a\\b.png", "con.png", "NUL.normal.png"])
def test_a_legacy_output_with_a_directory_mode_forbidden_name_still_loads(name):
    x = export_for(
        "{}\n",
        clips=(POSE,),
        view=RING4,
        destination=outputs.Positional(name),
    )
    loaded = manifest.decode(x.data)
    assert loaded.document["artifacts"][0]["path"] == name


def _paths(value, path=()):
    yield path
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _paths(item, (*path, key))
    elif isinstance(value, list):
        for position, item in enumerate(value):
            yield from _paths(item, (*path, position))


def test_an_artifact_kind_that_is_not_a_string_is_a_usage_error():
    for kind in ({}, [], 5, None):
        assert "artifacts[0].kind" in refused(
            edited(("set", ("artifacts", 0, "kind"), kind))
        )


def test_random_corruption_is_always_a_usage_error_or_a_valid_manifest():
    import random

    rng = random.Random(20261024)
    pool = [None, True, 0, -1, 2, 1.5, 1e999, "x", "", [], {}, [0], [1, 1], {"a": 1}]
    pool += [10**30, "all", "auto", 255, [[]], "sheet", "color", "../x"]
    places = [path for path in _paths(base().document) if path]
    for _ in range(400):
        doc = document()
        for _ in range(rng.choice([1, 2, 3])):
            path = rng.choice(places)
            try:
                container, last = walk_to(doc, path)
                if isinstance(container, dict) and rng.random() < 0.15:
                    del container[last]
                elif isinstance(container, list) and rng.random() < 0.15:
                    del container[last]
                else:
                    container[last] = rng.choice(pool)
            except (KeyError, IndexError, TypeError):
                continue
        data = json.dumps(doc).encode()
        try:
            manifest.decode(data)
        except UsageError as error:
            assert error.exit_code == 2


# Counts, names and text the reader must treat as data


def test_a_still_clip_is_one_sample_whatever_count_the_settings_give():
    ring8 = views.View(8, 0.0)
    for text in (
        "frames: 12\n",
        "clips: {pose: {frames: 12}}\n",
        "frames: 12\nclips: {pose: {frames: 50}}\n",
    ):
        x = export_for(text, clips=(POSE,), view=ring8)
        assert [c["frame_count"] for c in x.document["clips"]] == [1]
        assert len(x.document["frames"]) == 8
        manifest.decode(x.data)


def test_a_count_too_large_for_a_float_is_refused_without_an_overflow():
    animated = export_for("{}\n", clips=(clip(0, "walk"),), view=RING4).document
    for path in (("settings", "frames"), ("settings", "clips", 0, "frames")):
        doc = copy.deepcopy(animated)
        container, last = walk_to(doc, path)
        container[last] = 10**309
        message = refused(dump(seal(doc)))
        assert (
            "clips[0].frame_count: the settings sample about " + "1" + "0" * 309
            in message
        )


def test_a_source_basename_with_a_backslash_round_trips():
    from pathlib import PurePosixPath

    from moskophoros.capture.backend import Source

    odd = Source(PurePosixPath("/models/a\\b.glb"), "ab" * 32, 0)
    x = export_for("{}\n", clips=(POSE,), view=RING4, source=odd)
    assert x.document["source"]["file"] == "a\\b.glb"
    assert manifest.decode(x.data).document["source"]["file"] == "a\\b.glb"
    for name in ("", ".", "..", "dir/hero.glb"):
        assert "source.file" in refused(edited(("set", ("source", "file"), name)))


def test_an_unpaired_surrogate_is_a_usage_error_before_any_hashing():
    text = base().data.decode()
    value = text.replace('"tool": "moskophoros"', '"tool": "\\ud800"')
    assert value != text
    assert "generator.tool: holds an unpaired surrogate" in refused(value.encode())
    key = text.replace('"variant": "default"', '"variant": "default", "\\udfff": 1')
    assert "is a key with an unpaired surrogate" in refused(key.encode())
    name = text.replace('"name": "walk"', '"name": "w\\ud800"', 1)
    assert "holds an unpaired surrogate" in refused(name.encode())


def test_a_value_nested_beyond_the_recursion_limit_is_a_usage_error():
    text = base().data.decode()
    assert '"materials": null' in text
    for depth in (1500, 3000, 20000):
        nested = '"materials": ' + "[" * depth + "]" * depth
        message = refused(text.replace('"materials": null', nested, 1).encode())
        assert "nested too deeply" in message or "settings.style" in message
