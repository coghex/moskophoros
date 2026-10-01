"""Blender's glTF importer accepts every kind of file `GlbWriter` builds.

`bpy` is imported only inside the Blender process, never by pytest.
"""

import json
import math
import subprocess

import pytest
from glb_writer import GlbWriter
from test_smoke import TIMEOUT_SECONDS, BlenderNotFound, _diagnostics, find_blender

PREFIX = "moskophoros-glb-import: "
EXPRESSION = f"""\
import json, sys
import bpy
for path in sys.argv[sys.argv.index("--") + 1:]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=path)
    print({PREFIX!r} + json.dumps({{
        "path": path,
        "result": sorted(result),
        "objects": len(bpy.data.objects),
        "actions": sorted(action.name for action in bpy.data.actions),
    }}))
"""
HALF = math.sqrt(0.5)


def _static():
    model = GlbWriter()
    model.scene([model.node("box", mesh=True)])
    return model, []


def _animated():
    model = GlbWriter()
    hand = model.node("hand", mesh=True)
    arm = model.node(children=[hand])
    hips = model.node("hips", mesh=True, translation=(0, 1, 0), children=[arm])
    model.scene([hips])
    model.animation(
        "walk",
        [
            (hips, "translation", [0, 0.5, 1], [(0, 1, 0), (0, 1.1, 0), (0, 1, 0)]),
            (arm, "rotation", [0, 1], [(0, 0, 0, 1), (0, HALF, 0, HALF)]),
        ],
    )
    model.animation(None, [(hand, "translation", [0.25, 2], [(0, 0, 0), (1, 0, 0)])])
    return model, ["walk"]


def _two_scenes():
    model = GlbWriter()
    first = model.node("first", mesh=True)
    second = model.node("second", mesh=True)
    model.scene([first])
    model.scene([second], default=True)
    model.animation("spin", [(second, "rotation", [0, 1], [(0, 0, 0, 1)] * 2)])
    return model, ["spin"]


MODELS = {"static": _static, "animated": _animated, "two scenes": _two_scenes}


@pytest.mark.blender
def test_blender_imports_every_fixture_kind(tmp_path):
    try:
        blender = find_blender()
    except BlenderNotFound as error:
        pytest.fail(str(error), pytrace=False)
    expected = {}
    for stem, build in MODELS.items():
        model, named = build()
        path = model.write(tmp_path, stem.replace(" ", "-"))
        expected[str(path)] = (model.document, named)
    command = [
        blender,
        "-b",
        "--factory-startup",
        "-noaudio",
        "--python-exit-code",
        "1",
        "--python-expr",
        EXPRESSION,
        "--",
        *expected,
    ]
    result = subprocess.run(
        command,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    diagnostics = _diagnostics(result.stdout, result.stderr)
    assert result.returncode == 0, diagnostics
    reports = [
        json.loads(line.removeprefix(PREFIX))
        for line in result.stdout.splitlines()
        if line.startswith(PREFIX)
    ]
    assert [report["path"] for report in reports] == list(expected), diagnostics
    for report in reports:
        document, named = expected[report["path"]]
        assert report["result"] == ["FINISHED"], diagnostics
        assert report["objects"] == len(document["nodes"]), report
        assert len(report["actions"]) == len(document.get("animations", [])), report
        assert set(named) <= set(report["actions"]), report
