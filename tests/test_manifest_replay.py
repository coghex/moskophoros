"""Replaying an export from its manifest alone (export design P-8, part 4):
with the same model and generator, the manifest restores the settings, the
fingerprint, the images and the metadata without the original config,
project, palette or library files. The command does not do this yet, so the
stages are chained here as the command will chain them."""

from dataclasses import replace

import pytest
from manifest_fixture import (
    GENERATOR,
    LIGHT,
    RANGE,
    SOURCE,
    clip,
    export_for,
    frames_for,
    settings_for,
)
from test_manifest_styles import export_clip, styled

from moskophoros import (
    cli,
    export,
    exportimages,
    exportsettings,
    manifest,
    outputs,
    views,
)
from moskophoros.gltf import SelectedClip
from moskophoros.usage import UsageError

RING4 = views.View(4, 0.0)
FULL = """
stored_directions: [2, 0]
direction_names: {3: west-side, 1: right}
mirrors: {3: 2}
export:
  formats: [atlases, frames, sheet]
  atlas_padding: 1
clips:
  walk: {frames: 2, fps: 6, stored_directions: [1, 0], mirrors: {3: 1}, output_name: stride}
  idle: {frames: 1, mirrors: {}}
  jump: {frames: 2}
"""
MODEL = (clip(0, "walk"), clip(1, "idle"), clip(2, "jump", t1=2.0, one_shot=True))


def full(**changes):
    options = {
        "text": FULL,
        "clips": MODEL,
        "view": RING4,
        "depth": True,
        "light": LIGHT,
        "destination": outputs.Directory(),
    }
    return export_for(**(options | changes))


def replay(
    first,
    tmp_path,
    monkeypatch,
    *,
    argv=(),
    layers=(),
    model=MODEL,
    destination=None,
    subject="hero",
    seed=1,
):
    """The export the manifest `first.data` restores, as the command will make
    it: the settings layered under the options, the model's own clips, and
    the same stages as the original."""
    loaded = manifest.decode(first.data)
    (tmp_path / "hero.glb").write_bytes(b"model")
    parsed = cli.parse_args(
        [
            "--settings-from",
            str(tmp_path / "manifest.json"),
            "--no-user-config",
            *argv,
            str(tmp_path / "hero.glb"),
            str(tmp_path / "out.png"),
        ]
    )
    monkeypatch.setattr(cli, "read_settings", lambda path: loaded.reused)
    options = cli.resolve_settings(parsed, environ={"HOME": str(tmp_path)})
    by_name = {c.clip.name: c for c in model}
    selected = tuple(
        SelectedClip(by_name[name].clip, name in options.once) for name in options.clip
    )
    explicit = {
        key: getattr(options, key)
        for key in ("fps", "frames")
        if key in options.explicit
    }
    command_line = exportsettings.Source(exportsettings.OPTION, "option", explicit)
    resolved = exportsettings.resolve([loaded.source(), *layers, command_line])
    chosen = exportsettings.request(
        resolved,
        subject,
        selected,
        views.View(options.directions, options.start_angle, options.model_yaw),
    )
    settings = cli.capture_settings(options)
    light = export.Light(options.light, options.light_intensity, options.light_ambient)
    lit = options.previews and light.position is not None
    destination = destination or (
        outputs.Directory()
        if resolved.formats != ("sheet",)
        else outputs.Positional("hero.png")
    )
    view = views.View(options.directions, options.start_angle, options.model_yaw)
    names = outputs.resolve_names(
        chosen.selected,
        view,
        subject=subject,
        clip_aliases={n: c.output_name for n, c in resolved.clips.items()},
        direction_aliases=dict(resolved.direction_names),
        directory=isinstance(destination, outputs.Directory),
    )
    output_plan = outputs.plan_outputs(
        chosen.plan,
        names,
        resolved,
        destination=destination,
        normals=options.normals,
        depth=options.depth,
        previews=options.previews,
        lit=lit,
    )
    frames = frames_for(chosen.plan, seed, (settings.cell[1], settings.cell[0]))
    encoded = exportimages.encode(
        frames,
        request=chosen.plan,
        output_plan=output_plan,
        settings=settings,
        formats=resolved.formats,
        atlas_padding=resolved.atlas_padding,
        normals=options.normals,
        depth=options.depth,
        previews=options.previews,
        light=light,
    )
    data = manifest.encode(
        generator=GENERATOR,
        source=SOURCE,
        subject=subject,
        settings=settings,
        style=cli.style_record(options),
        resolved=resolved,
        request=chosen.plan,
        names=names,
        encoded=encoded,
        shade_range=options.shade_range,
        previews=options.previews,
        normals=options.normals,
        depth=options.depth,
        light=light,
        ramp=cli._formula(options),
        shading=cli._resolved_shading(options).settings,
    )
    return data, encoded, options


def test_the_manifest_alone_restores_the_directory_export_byte_for_byte(
    tmp_path, monkeypatch
):
    first = full()
    data, encoded, options = replay(first, tmp_path, monkeypatch)
    assert data == first.data
    assert [a.data for a in encoded.artifacts] == [
        a.data for a in first.encoded.artifacts
    ]
    assert options.clip == ("walk", "idle", "jump") and options.once == ("jump",)


def test_a_palette_and_library_come_back_without_their_files(tmp_path, monkeypatch):
    first = styled()
    data, _, options = replay(
        first, tmp_path, monkeypatch, model=(export_clip(),), destination=None
    )
    assert data == first.data
    assert options.palette is not None and options.materials is not None
    assert options.palette_file is None and options.materials_file is None


def test_positional_output_at_another_root_keeps_bytes_and_metadata(
    tmp_path, monkeypatch
):
    first = export_for(
        "{}\n",
        clips=MODEL,
        view=RING4,
        destination=outputs.Positional("/one/place/hero.png"),
    )
    data, encoded, _ = replay(
        first,
        tmp_path,
        monkeypatch,
        destination=outputs.Positional("/two/else/where/hero.png"),
    )
    assert data == first.data
    assert [a.data for a in encoded.artifacts] == [
        a.data for a in first.encoded.artifacts
    ]


def test_another_destination_name_changes_the_files_but_not_the_settings_or_hash(
    tmp_path, monkeypatch
):
    first = export_for(
        "{}\n",
        clips=MODEL,
        view=RING4,
        destination=outputs.Positional("hero.png"),
    )
    data, _, _ = replay(
        first,
        tmp_path,
        monkeypatch,
        destination=outputs.Positional("renamed.png"),
    )
    again = manifest.decode(data).document
    assert data != first.data
    assert again["settings"] == first.document["settings"]
    assert again["fingerprint"] == first.document["fingerprint"]
    assert [a["path"] for a in again["artifacts"]][0] == "renamed.png"


def test_frames_and_atlases_cannot_silently_become_positional_output(
    tmp_path, monkeypatch
):
    first = full()
    with pytest.raises(UsageError, match="need an output directory"):
        replay(
            first,
            tmp_path,
            monkeypatch,
            destination=outputs.Positional("hero.png"),
        )


def test_choosing_the_sheet_changes_the_settings_and_the_fingerprint(
    tmp_path, monkeypatch
):
    first = full()
    sheet = exportsettings.Source(
        exportsettings.OPTION, "option", {"export.formats": ("sheet",)}
    )
    data, _, _ = replay(
        first,
        tmp_path,
        monkeypatch,
        layers=[sheet],
        destination=outputs.Positional("hero.png"),
    )
    again = manifest.decode(data).document
    assert again["settings"]["export"]["formats"] == ["sheet"]
    assert again["fingerprint"] != first.document["fingerprint"]
    assert again["settings"]["clips"] == first.document["settings"]["clips"]


def test_an_explicit_clip_replaces_the_selection_but_keeps_its_overrides(
    tmp_path, monkeypatch
):
    first = full()
    data, _, options = replay(first, tmp_path, monkeypatch, argv=["--clip", "idle"])
    again = manifest.decode(data).document
    assert options.clip == ("idle",) and options.once == ()
    assert again["settings"]["clips"] == [first.document["settings"]["clips"][1]]
    assert [c["name"] for c in again["clips"]] == ["idle"]
    assert again["fingerprint"] != first.document["fingerprint"]


def test_an_explicit_once_changes_the_marks_and_so_the_fingerprint(
    tmp_path, monkeypatch
):
    first = full()
    data, _, options = replay(first, tmp_path, monkeypatch, argv=["--once", "walk"])
    again = manifest.decode(data).document
    assert options.once == ("walk",)
    assert [c["loop"] for c in again["settings"]["clips"]] == [False, True, True]
    assert again["fingerprint"] != first.document["fingerprint"]


def test_an_explicit_option_beats_the_manifest_and_a_clips_own_rate_beats_it(
    tmp_path, monkeypatch
):
    first = full()
    data, _, options = replay(first, tmp_path, monkeypatch, argv=["--fps", "24"])
    again = manifest.decode(data).document
    assert options.fps == 24.0
    assert again["settings"]["fps"] == 24.0
    assert [c["fps"] for c in again["clips"]] == [6.0, 24.0, 24.0]
    assert again["settings"]["clips"][0]["fps"] == 6.0


def test_the_settings_object_is_rebuilt_not_copied(tmp_path, monkeypatch):
    first = full()
    other = replace(first.settings, ppm=8.0)
    changed = manifest.settings_record(
        other,
        first.resolved,
        first.request,
        first.options["style"],
        shade_range=RANGE,
        light=LIGHT,
    )
    assert changed["pixels_per_meter"] == 8.0
    assert changed["pixels_per_meter"] != first.document["settings"]["pixels_per_meter"]
    assert settings_for(first.resolved).ppm == 4.0
