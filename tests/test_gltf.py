import json
import math

import pytest
from glb_writer import GlbWriter, float32

from moskophoros.gltf import (
    Clip,
    InputError,
    Root,
    SelectedClip,
    read_glb,
    select_clips,
)

HALF = math.sqrt(0.5)
STILL = (0.0, 0.0, 0.0, 1.0)
TURNED = (0.0, HALF, 0.0, HALF)


def _translation(node, times):
    return (node, "translation", times, [(0.0, 0.0, float(t)) for t in times])


def _rotation(node, times):
    return (
        node,
        "rotation",
        times,
        [STILL if k % 2 == 0 else TURNED for k in range(len(times))],
    )


def _scale(node, times):
    return (node, "scale", times, [(1.0, 1.0, 1.0)] * len(times))


def _three_clips():
    """Three animations whose ranges differ, each over two samplers."""
    model = GlbWriter()
    body = model.node("body", mesh=True)
    arm = model.node("arm", mesh=True)
    model.scene([body, arm])
    times = {
        "walk": ([0.0, 0.5, 1.0], [0.25, 1.5]),
        "jump": ([0.125, 0.75], [0.5, 2.25]),
        "idle": ([3.0, 3.0], [3.0]),
    }
    for name, (first, second) in times.items():
        model.animation(name, [_translation(body, first), _rotation(arm, second)])
    return model, times


def _clip_names(subject):
    return [clip.name for clip in subject.clips]


# Reading valid files


def test_subject_scene_and_clips(tmp_path):
    model, times = _three_clips()
    subject = read_glb(model.write(tmp_path, "hero.walker"))
    assert subject.path == tmp_path / "hero.walker.glb"
    assert subject.name == "hero.walker"
    assert subject.scene_index == 0
    expected = []
    for index, (name, samplers) in enumerate(times.items()):
        stored = [[float32(t) for t in sampler] for sampler in samplers]
        t0 = min(min(sampler) for sampler in stored)
        t1 = max(max(sampler) for sampler in stored)
        expected.append((index, name, t0, t1))
    assert [
        (clip.animation_index, clip.name, clip.t0, clip.t1) for clip in subject.clips
    ] == expected
    assert subject.clips[0].t0 == 0.0 and subject.clips[0].t1 == 1.5
    assert subject.clips[1].t0 == 0.125 and subject.clips[1].t1 == 2.25


def test_ranges_hold_inexact_times_as_stored(tmp_path):
    model = GlbWriter()
    node = model.node(mesh=True)
    model.scene([node])
    model.animation("tick", [_translation(node, [0.1, 0.7])])
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert (clip.t0, clip.t1) == (float32(0.1), float32(0.7))


def test_the_scene_property_chooses_the_subject_scene(tmp_path):
    model = GlbWriter()
    first = model.node(mesh=True)
    second = model.node(mesh=True)
    model.scene([first])
    model.scene([second], default=True)
    assert read_glb(model.write(tmp_path)).scene_index == 1


def test_a_file_without_animations_has_one_static_clip(tmp_path):
    model = GlbWriter()
    model.scene([model.node("box", mesh=True)])
    subject = read_glb(model.write(tmp_path))
    assert subject.clips == (Clip(None, "static", 0.0, 0.0, ()),)


def test_an_empty_animations_array_also_means_static(tmp_path):
    model = GlbWriter()
    model.scene([model.node(mesh=True)])
    model.document["animations"] = []
    assert _clip_names(read_glb(model.write(tmp_path))) == ["static"]


def test_reading_writes_nothing(tmp_path):
    model, _ = _three_clips()
    path = model.write(tmp_path)
    before = path.read_bytes()
    read_glb(path)
    assert [entry.name for entry in tmp_path.iterdir()] == [path.name]
    assert path.read_bytes() == before


# Roots


def _roots(tmp_path, model):
    return [clip.roots for clip in read_glb(model.write(tmp_path)).clips]


def test_an_animated_ancestor_hides_an_animated_descendant(tmp_path):
    model = GlbWriter()
    hand = model.node("hand", mesh=True)
    arm = model.node("arm", children=[hand])
    hips = model.node("hips", children=[arm])
    model.scene([hips])
    model.animation("both", [_translation(hand, [0, 1]), _translation(hips, [0, 1])])
    model.animation("hand", [_translation(hand, [0, 1])])
    assert _roots(tmp_path, model) == [(Root(hips, "hips"),), (Root(hand, "hand"),)]


def test_an_untargeted_parent_leaves_its_translated_child_a_root(tmp_path):
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    model.animation("move", [_translation(child, [0, 1])])
    assert _roots(tmp_path, model) == [(Root(child, "child"),)]


@pytest.mark.parametrize("channel", [_rotation, _scale])
def test_an_ancestor_targeted_by_any_channel_hides_a_descendant(tmp_path, channel):
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    model.animation("move", [_translation(child, [0, 1]), channel(parent, [0, 1])])
    assert _roots(tmp_path, model) == [()]


def test_only_translated_nodes_are_roots(tmp_path):
    model = GlbWriter()
    node = model.node("spin", mesh=True)
    model.scene([node])
    model.animation("spin", [_rotation(node, [0, 1]), _scale(node, [0, 1])])
    assert _roots(tmp_path, model) == [()]


def test_a_channel_without_a_target_node_is_ignored(tmp_path):
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    model.animation(
        "move",
        [
            _translation(child, [0, 1]),
            _rotation(parent, [0, 1]),
            _translation(parent, [0, 1]),
        ],
    )
    channels = model.document["animations"][0]["channels"]
    del channels[1]["target"]["node"]
    del channels[2]["target"]["node"]
    assert _roots(tmp_path, model) == [(Root(child, "child"),)]


def _pointer(model, clip, node, path, *, interpolation="LINEAR"):
    """A `/nodes/<node>/<path>` pointer channel; the reader checks its target,
    never its values."""
    count = 3 if interpolation == "CUBICSPLINE" else 1
    model.pointer_channel(
        clip,
        f"/nodes/{node}/{path}",
        [0, 1],
        [(0.0,)] * (2 * count),
        interpolation=interpolation,
    )


@pytest.mark.parametrize("interpolation", ["STEP", "LINEAR", "CUBICSPLINE"])
def test_a_translation_pointer_makes_a_root_like_a_translation_channel(
    tmp_path, interpolation
):
    count = 3 if interpolation == "CUBICSPLINE" else 1
    ordinary = GlbWriter()
    node = ordinary.node("walker", mesh=True)
    ordinary.scene([node])
    ordinary.animation(
        "walk",
        [(node, "translation", [0, 1], [(0.0, 0.0, 0.0)] * (2 * count))],
        interpolation=interpolation,
    )
    pointed = GlbWriter()
    assert pointed.node("walker", mesh=True) == node
    pointed.scene([node])
    clip = pointed.animation("walk", [])
    _pointer(pointed, clip, node, "translation", interpolation=interpolation)
    expected = [(Root(node, "walker"),)]
    assert _roots(tmp_path, ordinary) == expected
    assert _roots(tmp_path, pointed) == expected


@pytest.mark.parametrize("path", ["rotation", "scale", "weights"])
def test_only_translation_pointers_make_roots(tmp_path, path):
    model = GlbWriter()
    node = model.node("spin", mesh=True)
    model.scene([node])
    _pointer(model, model.animation("spin", []), node, path)
    assert _roots(tmp_path, model) == [()]


def test_a_pointer_translation_leaves_a_distinct_root_per_node(tmp_path):
    model = GlbWriter()
    low = model.node("low", mesh=True)
    high = model.node("high", mesh=True)
    model.scene([low, high])
    clip = model.animation("move", [])
    _pointer(model, clip, high, "translation")
    _pointer(model, clip, low, "translation")
    _pointer(model, clip, high, "translation")
    assert _roots(tmp_path, model) == [(Root(low, "low"), Root(high, "high"))]


@pytest.mark.parametrize("path", ["rotation", "weights"])
def test_a_pointer_ancestor_hides_a_translated_descendant(tmp_path, path):
    # Deliberate: a file this refuses as moving its root is now accepted.
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    clip = model.animation("move", [_translation(child, [0, 1])])
    _pointer(model, clip, parent, path)
    assert _roots(tmp_path, model) == [()]


def test_a_pointer_translated_child_of_an_animated_parent_is_no_root(tmp_path):
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    clip = model.animation("move", [_scale(parent, [0, 1])])
    _pointer(model, clip, child, "translation")
    assert _roots(tmp_path, model) == [()]


def test_a_pointer_translated_child_of_an_untargeted_parent_is_a_root(tmp_path):
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    _pointer(model, model.animation("move", []), child, "translation")
    assert _roots(tmp_path, model) == [(Root(child, "child"),)]


def test_a_pointer_translated_parent_hides_a_pointer_translated_child(tmp_path):
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    clip = model.animation("move", [])
    _pointer(model, clip, child, "translation")
    _pointer(model, clip, parent, "translation")
    assert _roots(tmp_path, model) == [(Root(parent, "parent"),)]


def test_a_pointer_target_in_another_animation_hides_nothing(tmp_path):
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    model.animation("other", [_translation(parent, [0, 1])])
    _pointer(model, model.animation("move", []), child, "translation")
    assert _roots(tmp_path, model) == [
        (Root(parent, "parent"),),
        (Root(child, "child"),),
    ]


@pytest.mark.parametrize(
    "pointer",
    [
        "/meshes/0/weights",
        "/nodes/0/translation/0",
        "/nodes/-1/translation",
        "/nodes/0/extras",
        "/cameras/0/perspective/yfov",
        "/nodes/99/extras",
        "/nodes/99/translation/0",
    ],
)
def test_other_pointers_target_no_node(tmp_path, pointer):
    # Neither a root nor a node reference to check, even one that names no node.
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("pan", [])
    model.pointer_channel(clip, pointer, [0, 1], [(0.0,), (0.5,)])
    assert _roots(tmp_path, model) == [()]


def test_a_pointer_that_is_not_a_string_targets_no_node(tmp_path):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("pan", [])
    model.pointer_channel(clip, "/nodes/0/translation", [0, 1], [(0.0,), (0.5,)])
    channel = model.document["animations"][clip]["channels"][0]
    channel["target"]["extensions"]["KHR_animation_pointer"]["pointer"] = 7
    assert _roots(tmp_path, model) == [()]


def test_a_direct_target_wins_over_a_pointer_on_the_same_channel(tmp_path):
    # A rotation of `first` that also carries a translation pointer to `second`
    # is a rotation of `first` and nothing else.
    model = GlbWriter()
    first = model.node("first", mesh=True)
    second = model.node("second", mesh=True)
    model.scene([first, second])
    clip = model.animation("move", [_rotation(first, [0, 1])])
    channel = model.document["animations"][clip]["channels"][0]
    channel["target"]["extensions"] = {
        "KHR_animation_pointer": {"pointer": f"/nodes/{second}/translation"}
    }
    assert _roots(tmp_path, model) == [()]


def test_a_node_beside_a_pointer_path_leaves_the_pointer_to_decide(tmp_path):
    # `path: "pointer"` is no direct target, so the pointer is the target. The
    # node the channel also names stays targeted, so the child it translates
    # has an animated ancestor.
    model = GlbWriter()
    child = model.node("child", mesh=True)
    parent = model.node("parent", children=[child])
    model.scene([parent])
    clip = model.animation("move", [])
    _pointer(model, clip, child, "translation")
    model.document["animations"][clip]["channels"][0]["target"]["node"] = parent
    assert _roots(tmp_path, model) == [()]


def _pointer_error(tmp_path, pointer):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    model.animation("fine", [_translation(node, [0, 1])])
    clip = model.animation("bad", [])
    model.pointer_channel(clip, pointer, [0, 1], [(0.0,), (0.5,)])
    return _input_error(model.write(tmp_path))


@pytest.mark.parametrize("path", ["translation", "rotation", "scale", "weights"])
def test_a_pointer_to_a_missing_node_is_an_input_error(tmp_path, path):
    error = _pointer_error(tmp_path, f"/nodes/7/{path}")
    assert error.exit_code == 3
    assert error.problem == (
        "animation 1's channel 0 names target node 7, which does not exist"
    )
    assert str(error).startswith(f"{tmp_path / 'subject.glb'}: ")


def test_an_unselected_animation_s_missing_pointer_node_is_still_refused(tmp_path):
    # The check is part of reading the file, whichever clips are selected.
    error = _pointer_error(tmp_path, "/nodes/1/translation")
    assert "animation 1's channel 0 names target node 1" in error.problem


@pytest.mark.parametrize(
    ("extensions", "problem"),
    [
        ("text", "animation 0's channel 0's target extensions is not an object"),
        (
            {"KHR_animation_pointer": [1]},
            "animation 0's channel 0's target KHR_animation_pointer is not an object",
        ),
    ],
)
def test_a_malformed_pointer_extension_is_an_input_error(tmp_path, extensions, problem):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("bad", [])
    model.pointer_channel(clip, "/nodes/0/translation", [0, 1], [(0.0,), (0.5,)])
    channel = model.document["animations"][clip]["channels"][0]
    channel["target"]["extensions"] = extensions
    error = _input_error(model.write(tmp_path))
    assert error.exit_code == 3
    assert error.problem == problem


def test_a_malformed_extension_beside_a_direct_target_is_never_read(tmp_path):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    model.animation("move", [_translation(node, [0, 1])])
    model.document["animations"][0]["channels"][0]["target"]["extensions"] = "text"
    assert _roots(tmp_path, model) == [(Root(node, "box"),)]


def test_roots_are_distinct_by_index_and_in_ascending_order(tmp_path):
    model = GlbWriter()
    nodes = [model.node("twin", mesh=True) for _ in range(3)]
    unnamed = model.node(mesh=True)
    model.scene([*nodes, unnamed])
    model.animation(
        "march",
        [
            _translation(node, [0, 1])
            for node in (unnamed, nodes[2], nodes[0], nodes[1])
        ],
    )
    assert _roots(tmp_path, model) == [
        (Root(0, "twin"), Root(1, "twin"), Root(2, "twin"), Root(3, None)),
    ]


# Selection


def test_without_clip_every_clip_is_selected_in_animation_order(tmp_path):
    model, _ = _three_clips()
    subject = read_glb(model.write(tmp_path))
    selected = select_clips(subject, [], [])
    assert selected == tuple(SelectedClip(clip, False) for clip in subject.clips)
    assert [s.clip.name for s in selected] == ["walk", "jump", "idle"]


def test_clip_selects_in_the_order_given(tmp_path):
    model, _ = _three_clips()
    subject = read_glb(model.write(tmp_path))
    selected = select_clips(subject, ["idle", "walk"], ["walk"])
    assert [(s.clip.name, s.clip.animation_index, s.one_shot) for s in selected] == [
        ("idle", 2, False),
        ("walk", 0, True),
    ]


def test_once_marks_clips_one_shot_without_clip(tmp_path):
    model, _ = _three_clips()
    subject = read_glb(model.write(tmp_path))
    selected = select_clips(subject, [], ["jump", "idle"])
    assert [(s.clip.name, s.one_shot) for s in selected] == [
        ("walk", False),
        ("jump", True),
        ("idle", True),
    ]


def test_the_static_clip_can_be_selected_by_name(tmp_path):
    model = GlbWriter()
    model.scene([model.node(mesh=True)])
    subject = read_glb(model.write(tmp_path))
    (selected,) = select_clips(subject, ["static"], ["static"])
    assert selected == SelectedClip(subject.clips[0], True)


@pytest.mark.parametrize(
    ("clips", "once"),
    [(["walk", "walk"], []), ([], ["jump", "jump"]), (["walk"], ["jump"])],
)
def test_combinations_the_parser_rejects_are_bugs_here(tmp_path, clips, once):
    model, _ = _three_clips()
    subject = read_glb(model.write(tmp_path))
    with pytest.raises(ValueError):
        select_clips(subject, clips, once)


# Input errors (exit classification 3). Each case returns the path to read.


def _valid(tmp_path):
    model, _ = _three_clips()
    return model


def _edited(edit):
    def make(tmp_path):
        model = _valid(tmp_path)
        edit(model.document)
        return model.write(tmp_path)

    return make


def _container(**overrides):
    return lambda tmp_path: _valid(tmp_path).write(tmp_path, **overrides)


def _raw(data):
    def make(tmp_path):
        path = tmp_path / "subject.glb"
        path.write_bytes(data)
        return path

    return make


def _json_text(replace):
    """Encode the valid document, then edit its JSON text."""

    def make(tmp_path):
        model = _valid(tmp_path)
        text = json.dumps(model.document, separators=(",", ":"))
        return model.write(tmp_path, json_bytes=replace(text).encode())

    return make


def _set(*keys_and_value):
    *keys, value = keys_and_value

    def edit(document):
        target = document
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value

    return edit


def _delete(*keys):
    def edit(document):
        target = document
        for key in keys[:-1]:
            target = target[key]
        del target[keys[-1]]

    return edit


def _two_parents(document):
    document["nodes"].append({"children": [0]})
    document["nodes"].append({"children": [0]})


def _cycle(document):
    document["nodes"][0]["children"] = [1]
    document["nodes"][1]["children"] = [0]


def _long_cycle(document):
    count = len(document["nodes"])
    document["nodes"].extend({"children": [count + k + 1]} for k in range(50))
    document["nodes"][-1]["children"] = [count]


def _duplicate_name(document):
    document["animations"][2]["name"] = "walk"


def _sampler_input(value):
    return _set("animations", 1, "samplers", 0, "input", value)


def _input_accessor(document):
    animation = document["animations"][1]
    return document["accessors"][animation["samplers"][1]["input"]]


def _bound(key, value):
    def edit(document):
        _input_accessor(document)[key] = value

    return edit


def _drop_bound(key):
    def edit(document):
        del _input_accessor(document)[key]

    return edit


def _missing(tmp_path):
    return tmp_path / "missing.glb"


def _directory(tmp_path):
    path = tmp_path / "folder.glb"
    path.mkdir()
    return path


ERRORS = {
    # 1. unreadable, or not binary glTF 2.0
    "missing file": (_missing, "cannot be read"),
    "a directory": (_directory, "cannot be read"),
    "empty file": (_raw(b""), "shorter than its header"),
    "wrong magic": (_container(magic=b"gltf"), "wrong magic"),
    "container version 1": (_container(version=1), "container version 1"),
    "container version 3": (_container(version=3), "container version 3"),
    "no chunks": (
        _raw(b"glTF" + (2).to_bytes(4, "little") + (12).to_bytes(4, "little")),
        "no JSON chunk",
    ),
    "no JSON chunk": (_container(omit_json=True), "no JSON chunk"),
    "JSON not UTF-8": (_container(json_bytes=b'{"a":"\xff"}'), "undecodable JSON"),
    "JSON syntax": (_container(json_bytes=b'{"scenes":'), "undecodable JSON"),
    "JSON NaN": (
        _json_text(lambda text: text.replace('"min":[0.0]', '"min":[NaN]', 1)),
        "undecodable JSON",
    ),
    "JSON array": (_container(json_bytes=b"[]"), "not an object"),
    "length too large": (
        lambda tmp_path: _valid(tmp_path).write(tmp_path, length=10**6),
        "inconsistent length",
    ),
    "length too small": (_container(length=20), "inconsistent length"),
    "chunk past the end": (_container(json_chunk_length=10**6), "inconsistent length"),
    "cut-off chunk header": (
        _raw(
            b"glTF" + (2).to_bytes(4, "little") + (16).to_bytes(4, "little") + b"\0" * 4
        ),
        "inconsistent length",
    ),
    # 2. no scenes
    "scenes absent": (_edited(_delete("scenes")), "has no scenes"),
    "scenes empty": (_edited(_set("scenes", [])), "has no scenes"),
    # 3. references to objects that do not exist, and malformed shapes
    "scene property too large": (_edited(_set("scene", 1)), "scene 1"),
    "scene property negative": (_edited(_set("scene", -1)), "scene -1"),
    "scene property a string": (_edited(_set("scene", "0")), "scene '0'"),
    "scene property a bool": (_edited(_set("scene", False)), "scene False"),
    "scene node": (_edited(_set("scenes", 0, "nodes", [0, 2])), "node 2"),
    "scene node negative": (_edited(_set("scenes", 0, "nodes", [-1])), "node -1"),
    "scene node a float": (_edited(_set("scenes", 0, "nodes", [0.0])), "node 0.0"),
    "child": (_edited(_set("nodes", 0, "children", [7])), "child node 7"),
    "channel sampler": (
        _edited(_set("animations", 0, "channels", 1, "sampler", 2)),
        "sampler 2",
    ),
    "channel sampler absent": (
        _edited(_delete("animations", 0, "channels", 1, "sampler")),
        "names no sampler",
    ),
    "channel target node": (
        _edited(_set("animations", 2, "channels", 0, "target", "node", 2)),
        "target node 2",
    ),
    "channel target node a string": (
        _edited(_set("animations", 2, "channels", 0, "target", "node", "body")),
        "target node 'body'",
    ),
    "sampler input": (_edited(_sampler_input(99)), "accessor 99"),
    "sampler input negative": (_edited(_sampler_input(-1)), "accessor -1"),
    "sampler input absent": (
        _edited(_delete("animations", 1, "samplers", 0, "input")),
        "names no accessor",
    ),
    "scenes not an array": (
        _edited(_set("scenes", {"0": {}})),
        "scenes is not an array",
    ),
    "scene not an object": (_edited(_set("scenes", [[0]])), "scene 0 is not an object"),
    "nodes not an array": (_edited(_set("nodes", {})), "nodes is not an array"),
    "node not an object": (_edited(_set("nodes", 1, None)), "node 1 is not an object"),
    "children not an array": (
        _edited(_set("nodes", 0, "children", 1)),
        "children is not an array",
    ),
    "node name not a string": (
        _edited(_set("nodes", 1, "name", 7)),
        "node 1's name is not a string",
    ),
    "accessors not an array": (
        _edited(_set("accessors", {})),
        "accessors is not an array",
    ),
    "accessor not an object": (
        _edited(
            lambda d: d["accessors"].__setitem__(
                d["animations"][1]["samplers"][0]["input"], 3
            )
        ),
        "is not an object",
    ),
    "animations not an array": (
        _edited(_set("animations", {"walk": {}})),
        "animations is not an array",
    ),
    "animation not an object": (
        _edited(_set("animations", 1, "jump")),
        "animation 1 is not an object",
    ),
    "samplers empty": (
        _edited(_set("animations", 1, "samplers", [])),
        "animation 1 has no samplers",
    ),
    "samplers absent": (
        _edited(_delete("animations", 1, "samplers")),
        "animation 1 has no samplers",
    ),
    "sampler not an object": (
        _edited(_set("animations", 1, "samplers", 0, 4)),
        "sampler 0 is not an object",
    ),
    "channels not an array": (
        _edited(_set("animations", 1, "channels", {})),
        "channels is not an array",
    ),
    "channel not an object": (
        _edited(_set("animations", 1, "channels", 0, None)),
        "channel 0 is not an object",
    ),
    "channel target absent": (
        _edited(_delete("animations", 1, "channels", 0, "target")),
        "target is not an object",
    ),
    "channel target path not a string": (
        _edited(_set("animations", 1, "channels", 0, "target", "path", 3)),
        "path is not a string",
    ),
    "scene property null": (_edited(_set("scene", None)), "names no scene"),
    "channel target node null": (
        _edited(_set("animations", 2, "channels", 0, "target", "node", None)),
        "names no target node",
    ),
    "scenes null": (_edited(_set("scenes", None)), "scenes is not an array"),
    "scene nodes null": (
        _edited(_set("scenes", 0, "nodes", None)),
        "scene 0's nodes is not an array",
    ),
    "nodes null": (_edited(_set("nodes", None)), "nodes is not an array"),
    "children null": (
        _edited(_set("nodes", 0, "children", None)),
        "node 0's children is not an array",
    ),
    "node name null": (
        _edited(_set("nodes", 1, "name", None)),
        "node 1's name is not a string",
    ),
    "accessors null": (_edited(_set("accessors", None)), "accessors is not an array"),
    "animations null": (
        _edited(_set("animations", None)),
        "animations is not an array",
    ),
    "samplers null": (
        _edited(_set("animations", 1, "samplers", None)),
        "animation 1's samplers is not an array",
    ),
    "channels null": (
        _edited(_set("animations", 1, "channels", None)),
        "animation 1's channels is not an array",
    ),
    # 4. not a forest
    "two parents": (_edited(_two_parents), "has two parents"),
    "a node listed twice as a child": (
        _edited(_set("nodes", 1, "children", [0, 0])),
        "has two parents",
    ),
    "own child": (_edited(_set("nodes", 0, "children", [0])), "in a cycle"),
    "cycle": (_edited(_cycle), "in a cycle"),
    "long cycle": (_edited(_long_cycle), "in a cycle"),
    # 5. sampler input bounds
    "min absent": (_edited(_drop_bound("min")), "'min'"),
    "max absent": (_edited(_drop_bound("max")), "'max'"),
    "min empty": (_edited(_bound("min", [])), "'min'"),
    "max two elements": (_edited(_bound("max", [1.0, 2.0])), "'max'"),
    "min not an array": (_edited(_bound("min", 0.0)), "'min'"),
    "max a string": (_edited(_bound("max", ["2"])), "'max'"),
    "min a bool": (_edited(_bound("min", [False])), "'min'"),
    "max overflows a float": (_edited(_bound("max", [10**400])), "'max'"),
    "max infinite": (
        _json_text(lambda text: text.replace('"max":[2.25]', '"max":[1e400]', 1)),
        "'max'",
    ),
    "reversed bounds": (_edited(_bound("min", [3.0])), "exceeds its max"),
}

# 6. animation names: each message gives the animation's index.
NAME_ERRORS = {
    "name absent": (_delete("animations", 1, "name"), "animation 1 has no name"),
    "name empty": (_set("animations", 1, "name", ""), "animation 1 has no name"),
    "name null": (_set("animations", 1, "name", None), "animation 1 has no name"),
    "name not a string": (
        _set("animations", 1, "name", 5),
        "animation 1's name is not a string",
    ),
    "names shared": (_duplicate_name, "animation 2 is named 'walk', like animation 0"),
}


def _input_error(path):
    with pytest.raises(InputError) as raised:
        read_glb(path)
    return raised.value


@pytest.mark.parametrize(("make", "problem"), ERRORS.values(), ids=ERRORS.keys())
def test_malformed_files_are_input_errors(tmp_path, make, problem):
    path = make(tmp_path)
    error = _input_error(path)
    assert error.exit_code == 3
    assert error.path == path
    assert str(error).startswith(f"{path}: ")
    assert problem in str(error)


@pytest.mark.parametrize(
    ("edit", "problem"), NAME_ERRORS.values(), ids=NAME_ERRORS.keys()
)
def test_bad_animation_names_are_input_errors(tmp_path, edit, problem):
    path = _edited(edit)(tmp_path)
    error = _input_error(path)
    assert error.exit_code == 3
    assert str(error) == f"{path}: {problem}"


@pytest.mark.parametrize(
    ("clips", "once", "missing"),
    [
        (["walk", "run"], [], "run"),
        ([], ["fall"], "fall"),
        (["walk"], ["Walk"], "Walk"),
    ],
    ids=["clip", "once", "once inside clip"],
)
def test_unknown_clip_names_are_input_errors(tmp_path, clips, once, missing):
    path = _valid(tmp_path).write(tmp_path)
    subject = read_glb(path)
    with pytest.raises(InputError) as raised:
        select_clips(subject, clips, once)
    assert raised.value.exit_code == 3
    assert str(raised.value) == f"{path}: no clip is named {missing!r}"


# Cubic spline animation and mesh weight pointers are read, not rejected


def test_a_cubic_spline_sampler_is_accepted(tmp_path):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    flat = (0.0, 0.0, 0.0)
    model.animation(
        "sway",
        [
            (
                node,
                "translation",
                [0.5, 2.0],
                [flat, flat, flat, flat, (1.0, 0.0, 0.0), flat],
            )
        ],
        interpolation="CUBICSPLINE",
    )
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert (clip.name, clip.t0, clip.t1) == ("sway", 0.5, 2.0)


def test_a_mesh_weight_pointer_is_accepted_and_sets_the_clip_range(tmp_path):
    # The pointer's sampler runs to 2 s, beyond the translation's 1 s.
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("swell", [(node, "translation", [0, 1], [(0, 0, 0)] * 2)])
    model.pointer_channel(clip, "/meshes/0/weights", [0, 2], [(0.0,), (0.5,)])
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert (clip.name, clip.t0, clip.t1) == ("swell", 0.0, 2.0)


def test_a_cubic_mesh_weight_pointer_is_accepted(tmp_path):
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("swell", [])
    model.pointer_channel(
        clip,
        "/meshes/0/weights",
        [0, 1],
        [(0.0,), (0.0,), (1.0,), (-1.0,), (0.0,), (0.0,)],
        interpolation="CUBICSPLINE",
    )
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert (clip.name, clip.t0, clip.t1) == ("swell", 0.0, 1.0)


def test_pointers_to_other_targets_are_accepted(tmp_path):
    # A node's own weights, and a camera, may be animated through pointers.
    model = GlbWriter()
    node = model.node("box", mesh=True)
    model.scene([node])
    clip = model.animation("pan", [(node, "translation", [0, 1], [(0, 0, 0)] * 2)])
    model.pointer_channel(clip, "/nodes/0/weights", [0, 1], [(0.0,), (0.5,)])
    model.pointer_channel(clip, "/cameras/0/perspective/yfov", [0, 1], [(0.8,), (1.0,)])
    (clip,) = read_glb(model.write(tmp_path)).clips
    assert clip.name == "pan"
