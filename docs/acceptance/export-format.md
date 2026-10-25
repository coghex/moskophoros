# Configurable export acceptance — EXP-7

**Status: pending owner visual acceptance.** Technical checks passed on 2026-10-25.
No acceptance verdict has been given for this implemented export. The owner is
reviewing it directly in `mosk-designer-5`'s pane, request
`moskophoros-20261024-1`, issue [#161](https://github.com/coghex/moskophoros/issues/161).
This record must not be used to close #161 or epic #153 until the owner's
explicit verdict on these exact results is recorded below.

## Review and scope

- New round folder: `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01`.
- Review page: `file:///Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/index.html`.
- Three questions sent directly in the pane on 2026-10-25: placement/motion,
  the five-view/mirror tradeoff, and overall export acceptance. All remain pending.
- Base unequipped acolyte only. No model/look changes, equipped acceptance,
  game writes, private frame compilation or integration were performed.
- Potential consumer handoff: `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/production/animations/` only.
  Normal and depth maps are separate trees; generic atlases alone are not
  claimed to be game-ready assets.
- No browser was opened. The page's script syntax, file references and all
  animation assets were checked; no browser layout or interaction test is claimed.

## Implementation gate

Clean detached checkout: `82ddf5c3e5b793400b9e6ba85901caf1d3d8de76` at `/Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review`.
The tool is installed from that checkout at `/Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/moskophoros` in
`/Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv`. Each invocation records the full commit and an empty
`git status --porcelain` before execution in its `*-exit.json`.
The package version does not identify a git revision.

The review checkout includes merged PRs #162–#168. The last implementation
merge is `13467b3bff9434ff16ca083799367d86ad44a174`. Compared with the validated
PR #168 head `83686ff46f79fc17d541399ecdb270c1e73a1e34`, only `MEMORY.md`
differs: source, tests, dependencies and validation code are unchanged.

- [PR #167](https://github.com/coghex/moskophoros/pull/167): 273 Blender tests,
  no failures/skips, at `5a1cf91cfae43534670ac57b85f42cdd06e521e1`;
  6,242 package tests passed. Default image-byte evidence is
  [EXP-6a evidence](../archive/exp-6a-image-evidence.md), landed at `e9f2ce787a`.
  The JSON/schema change there was intentional.
- [PR #168](https://github.com/coghex/moskophoros/pull/168): 279 Blender tests,
  no failures/skips, under the shared lock at the validated head above;
  6,445 package tests, 233 workflow tests and static checks passed.
  Its required `build-test` and opposite-brand review checks passed.
  [EXP-6b evidence](../archive/exp-6b-image-evidence.md), landed at `43f11d9224`,
  records default PNG/GIF/JSON byte identity.
- Rehashed all 13 retained EXP-6b default comparison files independently:
  base/head bytes equal, and each hash agrees with PR #168's table and the
  EXP-6a head hashes. Saved in `implementation-gate.json`.
- No fresh full test suite was needed or claimed: the validated implementation
  is unchanged. Four real-model export runs below all exited 0.

The virtual environment was created with `python3 -m venv .venv`, then
`python -m pip install -r requirements.lock` and
`python -m pip install --no-deps -e .` using its own Python. The initial pip
launcher and dependency imports stalled at macOS dynamic-library loading;
the exporter eventually proceeded without a workaround. Logs and stack
samples remain local. No alternate environment was used for the exports;
see `environment-note.md`. Nothing was installed into Blender.

## Approved inputs and transcription

Approved bundle: `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1`. Dated approval is in
`/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/CHANGES-2026-10-24-rework.md` and `owner-decisions.jsonl`.
The owner said directly in the earlier model designer's pane on 2026-10-24:

> yes, that is better, we can use this for now

That is model/look approval, not acceptance of this implemented export.
All 14 hashes declared by the bundle manifest match. Model, palette,
library, historical settings, baseline and provenance were copied into this
round. The bundle's verification-render PNG/GIF hashes also match its hashed
`reproduction-checks.json`. Source paths and frozen-copy hashes:

| Local input | SHA-256 | Source |
|---|---|---|
| `inputs/CHANGES-2026-10-24-rework.md` | `ad91fc165ed3444406f5bf074c7012e40491c9d3e8a04cea00250fa2c073c4ee` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/CHANGES-2026-10-24-rework.md` |
| `inputs/accepted-idle.json` | `712faf7bd40f5fb9abc5009eff4561da5c2524ac8ef72c2ba2879572e629da2c` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/verification-render/idle/acolyte.json` |
| `inputs/accepted-walk.json` | `61b671ebc4e1df630c48caf4d75b987488aa5ad4bcb00342162f9320b18b1008` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/verification-render/walk/acolyte.json` |
| `inputs/acolyte.glb` | `bfd3e9840fa2920e14d8ebd380f691e88dac62b577efa00e7d69697af6ec8247` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/acolyte.glb` |
| `inputs/baseline-settings.json` | `34b2a13ab7507096845364cd11545d661d11a41c381e721d0e33ec5afa1d7468` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/baseline-settings.json` |
| `inputs/library.yaml` | `e58fdd96fe1b1e0d832fb9673d4c5cd9df75f8151ac8963ba4029515bdc85593` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/library.yaml` |
| `inputs/manifest.json` | `5449c070620afec5fc6af2150b9271f087913145b770a1d72eaa34ba47d4e308` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/manifest.json` |
| `inputs/owner-decisions.jsonl` | `6268585433b304ab2e1b122404e2a9d8132479e03001dd62302ce6d0a6734d32` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/owner-decisions.jsonl` |
| `inputs/render.py` | `e0eb846b6563790b4c7c448ff5e7f8378cabd2df80078f4d0773a5de36ede1b0` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/render.py` |
| `inputs/reproduction-checks.json` | `fd864f1673f221191f06efcbbec5183532876cbe7d96894380a188d687b0deed` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/reproduction-checks.json` |
| `inputs/settings.yaml` | `7ecd1e1188260d718aad4917b95c028aeb7c11e6b3dff8c2805e99e50aeb8a04` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/settings.yaml` |
| `inputs/synarchy.gpl` | `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c` | `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/acolyte-model/accepted-rework-v1/synarchy.gpl` |

The historical command loaded `settings.yaml` below `baseline-settings.json`,
then replaced the material library and supplied timing/placement flags.
The current config transcribes the effective settings from the actual accepted
verification-render JSON, checked against the original accepted review JSON.
No `/15` file was passed to the new reader. This is settings transcription,
not legacy-loader support.

One historical note is inaccurate about the effective baked key direction:
`settings.yaml` says `[-0.35,0.85,0.4]`, but the baseline overrides it. The
accepted renders actually record
`[-0.5183210553488161,0.604707897906952,0.604707897906952]`; this review retains
that vector. The library's robe/belt strength remains 0.95. Every effective
look setting (including the material/palette records) equals the accepted
render's value. All 150 stored colour/normal/depth cells also match the
accepted renders pixel for pixel. See `transcription.md` and
`accepted-pixel-comparison.json`.

The camera is orthographic, direction
`[0,-0.49999999999999994,-0.8660254037844387]` (30° pitch), roll 0,
model yaw 0, eight directions starting at 0, supersample 8. Ground is
`[0,0,0]`, scale 24 pixels/metre, cells 48×48 and ground pixel `(24,44)`.
No overflow occurred; nothing was shrunk, recentered or cropped.

Preview light is `[-53.333,106.667,80]`, intensity `1`, ambient `0.3`.
The historical project comment says “scaled for 128x128 cells”; these actual
approved values are retained for the 48×48 target and displayed to the owner.
The live project configuration was read only, never selected for a run or edited.

Production stores `[0,4,3,2,1]` (south, north, north-east, east, south-east),
with mirrors `{7:1,6:2,5:3}`. Walk has 6 frames at 8 fps; idle has 4 at 6 fps.
The GLB's clips start at `1/48` second, not zero. Walk ends at
`1.0208333333333333`, idle at `2.0208333333333335`; durations are one and
two seconds (walk records `0.9999999999999999` due to floating point).
Samples are `t0 + k*d/N`, preserving this source offset and excluding the
endpoint. Walk time scale is `1.3333333333333333`; idle is `3`.

| Frozen configuration | SHA-256 |
|---|---|
| `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/config.yaml` | `a423394c08e119fa6f04dd64a687f3bf59eb056d48f91cee665620a313f6960a` |
| `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/control-config.yaml` | `e4b822764962159d8d8957eded5a79b4703c5f7a3b9f0a4fc46b34ea4004490f` |

The control config changes only `stored_directions: all` and `mirrors: {}`;
all counts, rates, look and placement remain identical.

## Exact commands

All captures run headless through the unchanged backend
(`-b --factory-startup -noaudio`) under the shared Blender lock. Every run
passes `/opt/homebrew/bin/blender` explicitly. Every output and retained work
root was fresh. The sheet run is positional and therefore uses `acolyte.*`
names, not the inactive `sheet{map}.png` template.

### Production

```sh
/usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/python /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/moskophoros --blender /opt/homebrew/bin/blender --config /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/config.yaml --clip walk --clip idle --work-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/production-work /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/inputs/acolyte.glb --output-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/production
```

Exit status: 0. Command stdout/stderr log: `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/production-run.log` (empty; no CLI warnings).

### Sheet

```sh
/usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/python /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/moskophoros --blender /opt/homebrew/bin/blender --config /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/config.yaml --clip walk --clip idle --work-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/sheet-work --formats sheet /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/inputs/acolyte.glb /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/sheet/acolyte.png
```

Exit status: 0. Command stdout/stderr log: `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/sheet-run.log` (empty; no CLI warnings).

### Replay

```sh
/usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/python /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/replay_guard.py /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/moskophoros --blender /opt/homebrew/bin/blender --no-user-config --settings-from /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/production/manifest.json --work-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/replay-work /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/inputs/acolyte.glb --output-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/replay
```

Exit status: 0. Command stdout/stderr log: `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/replay-run.log` (empty; no CLI warnings).

### Control

```sh
/usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/python /Users/vincentcoghlan/worktrees/coghex/moskophoros/exp7-review/.venv/bin/moskophoros --blender /opt/homebrew/bin/blender --config /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/control-config.yaml --clip walk --clip idle --work-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/control-work /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/inputs/acolyte.glb --output-dir /Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/control
```

Exit status: 0. Command stdout/stderr log: `/Users/vincentcoghlan/.local/share/moskophoros-acceptance/export-review/round-01/control-run.log` (empty; no CLI warnings).

`replay_guard.py` is a local evidence wrapper around the installed CLI,
not product code. CPython's audit hook refuses reads of both the original
bundle and live configuration directory and the frozen config/palette/library
and historical settings files. It records file opens in
`replay-open-audit.json`; no forbidden input was opened. The replay uses only
the `/1` manifest's embedded settings plus the same model and generator.
Successful Blender subprocess output is not exposed by the CLI; an empty
CLI log is not a claim that Blender emitted no internal messages.

## Generator and fingerprints

The serialized `generator` objects are byte-equal in all four JSON files:

```json
{
  "tool": "moskophoros",
  "version": "0.1.0",
  "python": "3.14.8",
  "numpy": "2.5.3",
  "pillow": "12.3.0",
  "blender": "5.2.2",
  "renderer": "cycles",
  "color": {
    "technique": "cycles-flat-emission",
    "samples_per_pixel": 1,
    "seed": 0,
    "pixel_filter": "BOX",
    "filter_width_px": 0.01,
    "min_transparent_bounces": 64,
    "transparent_max_bounces": 64,
    "pass_alpha_threshold": 9.313225746154785e-10
  },
  "shade": {
    "technique": "cycles-ambient-occlusion",
    "samples_per_pixel": 1,
    "seed": 0,
    "pixel_filter": "BOX",
    "filter_width_px": 0.01
  }
}
```

| Run | Fingerprint | Files |
|---|---|---:|
| production | `sha256:df7e0761a8620d0fce4dd93d156dae01b6f5a3e1073d46acc08570b22b374b8a` | 161 |
| sheet | `sha256:bdadef0053709df28da191489225fa57c25cdb503089ab9554187300f8ba9c5c` | 8 |
| replay | `sha256:df7e0761a8620d0fce4dd93d156dae01b6f5a3e1073d46acc08570b22b374b8a` | 161 |
| control | `sha256:1122a1557c584d3bd728382c326b2d776633649890d20cf4142dbe1ea636a5d9` | 251 |

Production and replay hashes agree for every relative path, all 161 files,
including the manifest. Sheet settings/fingerprint differ only because its
formats select `sheet`; compare logical pixels, not fingerprints. The control
has its own fingerprint because direction storage/mirroring differ.

## Mechanical results — all pass

1. Both measure and render request exactly 50 production samples, in clip,
   stored-direction and frame order, preserving original direction indices,
   angles and exact source times. Sheet and replay request the same 50;
   control requests 80. Mirrors have records only, no jobs or frame artifacts.
2. Exactly 50 48×48 PNGs in each channel: 150 total. No maps or extra files
   occur in the colour tree. Scale, ground and cell agree across all runs.
3. Each walk atlas is 300×250 and idle atlas 200×250. Every 50×50 slot is
   exactly its 48×48 frame plus nearest encoded edge/corner texels. Every
   channel's logical rectangles match the frame PNGs. The positional sheet
   is 288×480, in the agreed row/column order, with empty unused idle cells.
4. `/1` references every enabled artifact with correct locations and records
   source identity, resolved settings, fingerprint, intended `1/8` and `1/6`
   frame durations, counts, directions and mirrors. Mirrored anchor is
   `(48-24,44)=(24,44)`. Config file paths/hashes are evidence here, not
   fields expected in the manifest. Comparison relighting negates normal X
   after decoding/normalizing and preserves normal alpha and depth values.
5. Both flat/lit GIFs have five stored panels (960×192 at encoded 4× scale).
   Walk has six 130 ms delays: 0.78 s. Idle has four 170 ms delays: 0.68 s.
   Intended playback is 0.75 s and 2/3 s respectively. No terminal hold occurs
   for these loops. The page uses intended timing, with actual GIFs separately
   labelled. All 100 stored flat/lit page cells equal the exported GIF panels.
6. Fresh-root metadata-only replay reproduces all 161 files byte for byte.
   Generator objects are byte-equal across all four runs. The isolated
   all-direction control differs only in storage/mirroring; its 80 samples
   and 240 frame PNGs are excluded from production counts.

`mechanical-checks.json` contains 633 passing assertions;
`capture-checks.json` covers all eight capture phases, settings identity,
generator bytes and replay access. No mismatch or unexpected CLI warning was
observed. The early preparation assertion expecting a zero source start was
corrected to the documented `t0 + k*d/N` rule; the source was never changed.
This was an evidence-script assumption, not an implementation failure.

## Output hashes

Complete relative-path tables for all four outputs are in
`output-hashes.json`; its SHA-256 is `314afb0747bcba872d4a213d45ff0bf3a349fa663d3389486918354a4f0db5df`.
The production table below also applies to replay byte for byte.

| Production relative path | SHA-256 |
|---|---|
| `animations/idle/east/frame_000.png` | `05ecb6326a04ab50cafbdd9860d97eeba7d098e19cdadd877586788f823a2678` |
| `animations/idle/east/frame_001.png` | `c0e510f172bc71447705c7d98960965259563aeda23312eff8e4f929737fca55` |
| `animations/idle/east/frame_002.png` | `0c38384ec1031b8b5d0947b47a974f29cebdce634752e6b9ac2ca6a57a2b62ec` |
| `animations/idle/east/frame_003.png` | `05201078fb66918ffc28e8b7a3905ada1c1664f33332b9fe09fecbf57c3babb2` |
| `animations/idle/north/frame_000.png` | `8a0ca3b5e725f121a5718eae103029a4d686a58ee7613dfa2b2a963d0c54c779` |
| `animations/idle/north/frame_001.png` | `e8526cd0c131ff0dbe1b20cd59ea71768e485381dbba71b84fb50df87ca8c830` |
| `animations/idle/north/frame_002.png` | `32f96228e9471b79ac0957b0d8a5580fccc6b8d396ff65c3ce779a480fa31b84` |
| `animations/idle/north/frame_003.png` | `62f87e02e30862d56f09bceb3ec2d96266709f6153aab6bce32016f8cd3e2683` |
| `animations/idle/north-east/frame_000.png` | `3174cabe5314524ba94d939b32e1476a8f69c50685c0203e2a9736c658e7c4a7` |
| `animations/idle/north-east/frame_001.png` | `e1ca60bbe8283674efeeafdea87dd282ac6261970143e826527335baf2341409` |
| `animations/idle/north-east/frame_002.png` | `531af67a5d0b872c5778cd4aa5b3bb1032d7fe97ff8dd06bc8cc21b5e6fddc6a` |
| `animations/idle/north-east/frame_003.png` | `f44d7d03a1cf9bfb88945f6750e33ed0c56f667e11b830f125f8b5013d9a1168` |
| `animations/idle/south/frame_000.png` | `3fa69122feb5955c532cfaf0cb0badbdfaa0e245b2bcef1f29d7a43d96f73e91` |
| `animations/idle/south/frame_001.png` | `0c41041aba77d6f4bbcf244d83b08ad59b8e5ff6db68537842b8d2b7a81b9b21` |
| `animations/idle/south/frame_002.png` | `336aaf077652ec35c8a1f72968837fe5e07a5cd6cea28ba45e134850d12572cd` |
| `animations/idle/south/frame_003.png` | `f51865d5395098a744b28d4e44e52da90b98de8d1333c4e6aa6cf3e529e2a443` |
| `animations/idle/south-east/frame_000.png` | `c47842ac1ad756a87a589482308090c49af7782fcf4953e82841353f2cbb0d91` |
| `animations/idle/south-east/frame_001.png` | `bceb2c69dc577e4083c576a57d1a7ed1728638769c15aa8e4a80d378949d38f4` |
| `animations/idle/south-east/frame_002.png` | `71bee0374864591d132c06490a22552347996ecd3d9afc79a01f19df7fbf9c80` |
| `animations/idle/south-east/frame_003.png` | `367b446e9d6d5ab6cd585d0a9e55d352ab54bed43d0012000acc2897b5ba692b` |
| `animations/walk/east/frame_000.png` | `1f3de46562f773067cee1a30af82cd9d72acecf8e21dffe9df68a677c2d4cbcd` |
| `animations/walk/east/frame_001.png` | `5f706a16927a75721bad4238e6265a4ac9e1f6a8cf173f0b7e483a238aa4da27` |
| `animations/walk/east/frame_002.png` | `c9aefdf00f1a3becf8223c9d485b32fea5282be7df392a651c413736dab71ba2` |
| `animations/walk/east/frame_003.png` | `06f851612c63d4ccc0db6b23721726dd475d122f217c2f19dda50fabd1a56b7b` |
| `animations/walk/east/frame_004.png` | `d5e5e4a32de7b7b97b86779a551c49655bd2bb76fb705057be520eb9b3fa8962` |
| `animations/walk/east/frame_005.png` | `80ea1f127bf074ba9d8de74466a17aca2f81ef95ae4cfa68361979d7337532f5` |
| `animations/walk/north/frame_000.png` | `8ce5b10b620c6f8f0a071fd52aab02f198f71675cf75607d4dc67e1b1c5abd1e` |
| `animations/walk/north/frame_001.png` | `8664ba3c1cbe5cdfcf10261b065c5988d24b7194cf8fa2a791ddbc208fe7b9a6` |
| `animations/walk/north/frame_002.png` | `47c8bf8dfbd0c7e59de0bd6053b7656f16d7fa50732524e686300b48243a670c` |
| `animations/walk/north/frame_003.png` | `d865791cca226363b9c0006d0c2cacb5795734d50c5b6914164fae5723d00c1a` |
| `animations/walk/north/frame_004.png` | `43045bd57a1ffee9cb9ce4e0e078a5c32e51b2d1d026b0d1b76ef4cdffe61ce7` |
| `animations/walk/north/frame_005.png` | `00703283939d5dab9b25755f99d968ebd19a8517f91f20c8967521c4d45642ff` |
| `animations/walk/north-east/frame_000.png` | `999706f18ce767baede22265165ffa40ee0f81e47aad8ac4707d9ab2979fb94f` |
| `animations/walk/north-east/frame_001.png` | `fcb78ef5d829813ed6544a0268d9a890e54bdb7a29ee3efffa06d5ff085ffe10` |
| `animations/walk/north-east/frame_002.png` | `f226f72e3610008e9dd4929bfb0c3c62656ca01178ce8b19c9c64e5a1fd6ba3e` |
| `animations/walk/north-east/frame_003.png` | `b56d370d9cab4135fe6db611cfb49fb3e0e536d7e074582bf179ad72a814c495` |
| `animations/walk/north-east/frame_004.png` | `8e15b9db4e4f291b9787a24c6e0cfdd798bb72bc27f5e61f95e0fd00b540c6cd` |
| `animations/walk/north-east/frame_005.png` | `eb49dde665f101314af84e8f1a62beab0f2769a223d7f074d7c8b9a09a4da2aa` |
| `animations/walk/south/frame_000.png` | `270b30b2b2a3dcd496573af3babc77738147a23fb84ca7434e4735e33fd92959` |
| `animations/walk/south/frame_001.png` | `6ddb141b064a1632e7a9b88375d74fbd00d15aabf85f1825bb5ffbcb79c214d1` |
| `animations/walk/south/frame_002.png` | `499e4175423cd1ebc888698b233b5f2e669b36104029012b1c39d7891028830b` |
| `animations/walk/south/frame_003.png` | `2a793d7cbf90817c31930c5a3af23ca2ffbc98fe40eb51ae3fa7edb7adcdb166` |
| `animations/walk/south/frame_004.png` | `9240ee3e275c4aa401edbb577b1a2e3da40c0d7fea2eb99cc3fa20d64b2d959b` |
| `animations/walk/south/frame_005.png` | `9a71d0e07acb64fbabdeeff848e731c2e456bd953f09835d2ef5ff61bd1b3a57` |
| `animations/walk/south-east/frame_000.png` | `8093d0f03d3c3793754f97e68871658d066f5963fddc4e2e6cccc487b16a4987` |
| `animations/walk/south-east/frame_001.png` | `3e556d80d2c7fbdc52bdf48fe4fb65f8e35a441978dd54d9a17b114f2ba3f2c0` |
| `animations/walk/south-east/frame_002.png` | `b6380b8877353a8b99a6de8d1a1823d56276554d6dce53f5a79b4ef014f0f9fb` |
| `animations/walk/south-east/frame_003.png` | `f56692624f91fa5d088a7e8e25b3d147f501fe15d1fd08955c219847917ecbaf` |
| `animations/walk/south-east/frame_004.png` | `9ef4160870d15658b9e68bc2573fd8dd1f9380735987cdb5dac35f6c7e746caa` |
| `animations/walk/south-east/frame_005.png` | `dd7601613e623321fdcdb39ea7cc29a91fad70cac079a931f9aa9906d982cbb6` |
| `animations.depth/idle/east/frame_000.png` | `093bb30f9cc8e0eaf82c3fb20f20e1411a301fe01b3e22a83a870c9e50b7844b` |
| `animations.depth/idle/east/frame_001.png` | `13da979fe6bf8903142ffeef104649c3d702393ec572b1e98f655c057c724ba1` |
| `animations.depth/idle/east/frame_002.png` | `6c08e6ab9633ef60c2caf3b811202bc0d9d9db04e5eb46dee1f888cac11ea62e` |
| `animations.depth/idle/east/frame_003.png` | `71c22c7208317e9e947827bed9b05e1a96d2ed1a66694dc591e7f3e065553deb` |
| `animations.depth/idle/north/frame_000.png` | `202c1c83789569c408029e7b9228b818e5e2be19ec9b8a28f0ee40d4ed496415` |
| `animations.depth/idle/north/frame_001.png` | `c8436a5bf86b4292e8a3443f523414918be3159ba6f58a54e74663af54d526bb` |
| `animations.depth/idle/north/frame_002.png` | `e48545cfc0cd8e561c94d6bdfd2c1e85b2d2c62a67a8037d28aa6d7665cde638` |
| `animations.depth/idle/north/frame_003.png` | `8e5a70c830a9228e06281739a134214635042422826a71bbfef22ea770f5bcde` |
| `animations.depth/idle/north-east/frame_000.png` | `01aff734984674a691056a2900c576ac41e7b87982628f0a726878917edeac90` |
| `animations.depth/idle/north-east/frame_001.png` | `0c64b156a51f18a93c79ecea1f647f87c248ab59959c1b24c4ad07598e4208f3` |
| `animations.depth/idle/north-east/frame_002.png` | `2d4fb10112d9eeb9a9dc06d2a979843b8a2eaa50e6c105f727b67eedc9c990f7` |
| `animations.depth/idle/north-east/frame_003.png` | `28bfb47b1f36f7efbe4bf31177e279b53a59caa98500883121a6e51ce827e117` |
| `animations.depth/idle/south/frame_000.png` | `cb131e8246c77bb0b4188cbf477f42e094420da95e731cb3efb0676d2201a212` |
| `animations.depth/idle/south/frame_001.png` | `c1a29ae62a6fcfccaa09daa2bd033af1fd59dc2ea978fb25ccc2e5ea2ee3a1bc` |
| `animations.depth/idle/south/frame_002.png` | `d70ade7894725d47c61df1d71dd55c68ce2201adee2f6d414df04dda3ba3d3d6` |
| `animations.depth/idle/south/frame_003.png` | `82520789d1daca24cec2bfc8d3bd3d9bd7f9269919d47babb83563fa62974916` |
| `animations.depth/idle/south-east/frame_000.png` | `84ba1c2eda20e717b9667f3d3cf6e728e6b1cbd877624e38ffa506cb9bfad36d` |
| `animations.depth/idle/south-east/frame_001.png` | `1c254baa0ad75efeb948ff87bf3200e43264fb2f42b89de3af20eb6f50940dd1` |
| `animations.depth/idle/south-east/frame_002.png` | `cfba4d1752ea9c6c603a83a5ba7979c235f005110caabd04440e4e2fc20a481b` |
| `animations.depth/idle/south-east/frame_003.png` | `2f4c4174ffe2344ad6f9f300a6d4db2b422bab4697c649e158f909d58b905d64` |
| `animations.depth/walk/east/frame_000.png` | `a02a92447c14b0188ff394c66c8f22d3715be9018e0e97c1a4536c7d79a3da0c` |
| `animations.depth/walk/east/frame_001.png` | `37e57569238a8d6923f9a419a0bf33a04ffabd390d4872e9940a1842cf08dd8b` |
| `animations.depth/walk/east/frame_002.png` | `5870c988682dd47c6287946184a819a8b19378c754df2ccd1b6ffb99640ba5f5` |
| `animations.depth/walk/east/frame_003.png` | `6918bc2a2e79c761981f226772471d9e33c3bf7a93691201c60e462c3a4753b2` |
| `animations.depth/walk/east/frame_004.png` | `7d7d7374818c656291419e5eb67a448d27c16970d3af9715c5ff2148746e0366` |
| `animations.depth/walk/east/frame_005.png` | `2b59f525722c84a9004223be88a9ef04902ee78370a6783d0728dee1c5c0095f` |
| `animations.depth/walk/north/frame_000.png` | `eaad583ecca9cdc3e21337ac078aa5ede76c7003d3c65acd4aadf1fc55822220` |
| `animations.depth/walk/north/frame_001.png` | `98e0e4b7be4b2595f2f44e53794de09e5b6a26d8261e391bcb96870b9ab40412` |
| `animations.depth/walk/north/frame_002.png` | `b2afc8c780a09ac84bf14bfb82c832dc10fc0440dcaf3301f3705ecfc65c82cc` |
| `animations.depth/walk/north/frame_003.png` | `4490b66e7e0da9afe32cd507da1fe4b13656f43f52c0e26c7d9469abc4e9b9c8` |
| `animations.depth/walk/north/frame_004.png` | `bf244c3c2c799b089e60bb7d2bf447d24b5c717bef28bdcdad6956eac74c41ea` |
| `animations.depth/walk/north/frame_005.png` | `7dcb5bf9515f39ee4b1747e3a56813d1f3b8347d404479f3f1d5bbd228595ebf` |
| `animations.depth/walk/north-east/frame_000.png` | `50f3c36327d5834a2389b7d83e058857a0f6216ae8525a9725db76d2c8ba9fc5` |
| `animations.depth/walk/north-east/frame_001.png` | `9672cce6fc84d3fb69f7f81ad302088f200aba8f225eb979e27f918bdd1cbfcf` |
| `animations.depth/walk/north-east/frame_002.png` | `990d6cc82bf0144614deae8be993b705d4e27d475673cb873021e6537a91b6d5` |
| `animations.depth/walk/north-east/frame_003.png` | `73a9def4df344091ebeebfa833acc6d6f6e7fdeca3458c1dfe5e2e1abd6a143c` |
| `animations.depth/walk/north-east/frame_004.png` | `e285580938e59ac735c871d34eaccca8a954c35f266202d2b56d060c563c7583` |
| `animations.depth/walk/north-east/frame_005.png` | `0cc872bd583d3bfd630c26bc186cdcd48416dc24fbe26450c55fcf52d615fd76` |
| `animations.depth/walk/south/frame_000.png` | `4a25a18c3809170b4ea95cd0a8ff703de2cbe754604e23c1978f2936c1a61e1e` |
| `animations.depth/walk/south/frame_001.png` | `00b0c50557b1bce016319f0cc78c32ba9d70e3ea023a2e9dbc321ed77c408275` |
| `animations.depth/walk/south/frame_002.png` | `3d355652d318a761c9dc554b30d4cf4f4558dda667c419247d6143e734b1f785` |
| `animations.depth/walk/south/frame_003.png` | `1e9420ab311972eec7d36fecfbb568a54bf6f319d212632ba4642774b131280a` |
| `animations.depth/walk/south/frame_004.png` | `604b033039b656babb20b26b0adc1b98a14f42ade713726e4778440fcef44676` |
| `animations.depth/walk/south/frame_005.png` | `ccfc30074d6b0c666e77e3db69975f9b87bde75121a89bce491f6f9141036f0c` |
| `animations.depth/walk/south-east/frame_000.png` | `ec964591bf4d1a19313dbb647d576a3f42478ec4df5236adf375237281c7439e` |
| `animations.depth/walk/south-east/frame_001.png` | `eccb0c6b7fb5e48f22c3e5b04e64ecac75944828c4eb10c15fb3edcb7281b480` |
| `animations.depth/walk/south-east/frame_002.png` | `92f41e600546e65a985d0d171be980858566a9fc2d554d3fe93bbfc7a8ab1086` |
| `animations.depth/walk/south-east/frame_003.png` | `46008a2be458e9359ac6240d074edd8a7a785a5b6fa1f033273e4a703f8f98f5` |
| `animations.depth/walk/south-east/frame_004.png` | `bcbd5bff011bc117c17363cf85ff367276bea80ca48571d0eec1f98b77823c11` |
| `animations.depth/walk/south-east/frame_005.png` | `e1e4a9946c93be519974d26f748e52913084a35b7b23566e1d55bcb3d484ec20` |
| `animations.normal/idle/east/frame_000.png` | `25f8d5f97e448ffd53d132923e0543bc3bd39273fe8019bd426d4dbc23ed4c20` |
| `animations.normal/idle/east/frame_001.png` | `5b53b673bfe65790a1aa1770cb6d614c16fa0ef0a7d344921425a5610883dee7` |
| `animations.normal/idle/east/frame_002.png` | `941b07af781275f7668f1eb985ebe0cd087d84101fd5cfa32d7934f0b4075303` |
| `animations.normal/idle/east/frame_003.png` | `440cbb8eb894f7a68fdb3ebf8e3ea52af7192263c725dfaedfaea19a110bba91` |
| `animations.normal/idle/north/frame_000.png` | `ab898b5fb5fae126e22806e42e99ddfac5fb1a2ca940a7714232eb39814512a5` |
| `animations.normal/idle/north/frame_001.png` | `9edec72987b9e5f17b74d082f02f8e77b4908f31ccf09b27d4b4836419b617a5` |
| `animations.normal/idle/north/frame_002.png` | `7a24fc9bcc820c9057f7d45b99f58b3eb67222d68ee19dc026ee1919516c102d` |
| `animations.normal/idle/north/frame_003.png` | `45eed7f159b37ccf34363d0bbc023036bf49d7b75ef45ccd4f983ee3c6c110df` |
| `animations.normal/idle/north-east/frame_000.png` | `6b14293e6aa832e6077c853d5117b54a99e0b05aa9f56fa26fb164338c03ffe8` |
| `animations.normal/idle/north-east/frame_001.png` | `b819ad4b67b75da20f6fa22388dc37a658a39c6d5022b433fa34732a959d714f` |
| `animations.normal/idle/north-east/frame_002.png` | `95beab43d9ecaffb2e49af28ddce28174dfe1bc8c1c94a24a49d9a79609bc885` |
| `animations.normal/idle/north-east/frame_003.png` | `8d3a7541d6c216505714ef6a5a24da8edefbfe3559aef200ea0a0e9656df8ea5` |
| `animations.normal/idle/south/frame_000.png` | `07f2a208a532273d5122fa7bab9323f9bd9bde23ee5e9938cc72f55c05ca0a37` |
| `animations.normal/idle/south/frame_001.png` | `c1eeb97beb0baf8e206f9b5251114873f7e123f788287c13824e45087469721c` |
| `animations.normal/idle/south/frame_002.png` | `9047543cbaeb486f4c5525976a72d56e145167053166793536f51579b7632063` |
| `animations.normal/idle/south/frame_003.png` | `4a2a0536b8b6e2034fd277c456323ec495a314d0d2b41d0bb2fc87bb5e5993d1` |
| `animations.normal/idle/south-east/frame_000.png` | `6b7e4cc109faef81c6eea774b8af5c72c6ff4ea52dd08c7df79654a680efbba6` |
| `animations.normal/idle/south-east/frame_001.png` | `e4dc58bbe8f07ca5f7caa8a0b714fe3b53805278d883d1114bb07214965d67a9` |
| `animations.normal/idle/south-east/frame_002.png` | `8842332f737bea177c668827cea69d06128638b88cd366c1294e2cf716ffd14c` |
| `animations.normal/idle/south-east/frame_003.png` | `7f66cdd7093ee8260728d2b28111b72db760d963376f70251bd8c0771cf5d994` |
| `animations.normal/walk/east/frame_000.png` | `d428862d5ca641a44063fbb628d11c48d7f777bc9614075761c395827577c8dc` |
| `animations.normal/walk/east/frame_001.png` | `e8b3393a9c88a867be3cff4c06c59f912224a069c3fc420e56959b71c7e2ee0f` |
| `animations.normal/walk/east/frame_002.png` | `45105e14a2dbce733d980053db8aa1b8ba267cea125349ec5e2b7d06ddcb45a1` |
| `animations.normal/walk/east/frame_003.png` | `0ed7dfe92db82f56b31419271329da5647a741b9fbfec4354578012526a3474d` |
| `animations.normal/walk/east/frame_004.png` | `95bb160c8897ef14a5acc9d73e69e06e0d0bd7c40e94e181a7c7fadd61e8cfe4` |
| `animations.normal/walk/east/frame_005.png` | `3e1fdcf99ddb1e503c9fe727050fadcb558e5fe69b517e1976adf23eb27ca3e5` |
| `animations.normal/walk/north/frame_000.png` | `cfde4ee3a65c6b995368885ee261f019ec3c3786cfa0dee075a9e43481c7bc5a` |
| `animations.normal/walk/north/frame_001.png` | `30b6c9fb10e11889aac94c0bf2be69ec7722aaef34035f5267b3d242e5bb10d5` |
| `animations.normal/walk/north/frame_002.png` | `55de6d46477a0d526f64bfbb5ef58ba74634ff1c30fe65f17c88eb0af682671b` |
| `animations.normal/walk/north/frame_003.png` | `86d51fe3412da529a50e7ebd6c361dd3eb7e3671486f9e999cf44e8fc1083960` |
| `animations.normal/walk/north/frame_004.png` | `2ba1fb6c8d3368154eefad6f400c3d0eb365ed19f573dfc1389b18081221f514` |
| `animations.normal/walk/north/frame_005.png` | `46dc37a948456ee3d81be755b4e2cf47999f4e81c507cacee1e9ef376a8401a6` |
| `animations.normal/walk/north-east/frame_000.png` | `cc2c13d0cf8721fcc12c471e8dae56e2f68c46d856c8914ce78536702d5ab32a` |
| `animations.normal/walk/north-east/frame_001.png` | `0ec7feefb5263ee54fa1810176ecff6629d669e510f156e1c1b5d3d794f0e473` |
| `animations.normal/walk/north-east/frame_002.png` | `53f136eedff417806c4e86245f4a3227d3541de8ec871d69fc7d6e96c7ca7240` |
| `animations.normal/walk/north-east/frame_003.png` | `06212851c0f3a09f6c17d36d99730d0dc913a3fb611ac4e969e2866cb82ce191` |
| `animations.normal/walk/north-east/frame_004.png` | `edc20209141d20a22722dddc1f085c240bcd0b1357944a6ac8986aad89c0db66` |
| `animations.normal/walk/north-east/frame_005.png` | `39bfe8037e0a1c7d913e7071755a6a5dc23b4daa3d0354d38e40ae74f06895dd` |
| `animations.normal/walk/south/frame_000.png` | `aa3603ea1e5608f96c47873d78dc8fee5ff8393753e17cfa451b7cbf208adeec` |
| `animations.normal/walk/south/frame_001.png` | `dc8053366edf050431473c0d2f2cbbb20a69ab547666c097538e6f754a35213e` |
| `animations.normal/walk/south/frame_002.png` | `9b44af40cad0043e24bfb090c7d2b8769ce37fb834532baa901187b52e1819b7` |
| `animations.normal/walk/south/frame_003.png` | `51b7c69759505c453e0ba480aa2b27d646b8824590a5696b3534c5b97df27fdd` |
| `animations.normal/walk/south/frame_004.png` | `5ed54981bf8a84109c53289403d177281f198f52773d1d78596e3fefd4ee97a3` |
| `animations.normal/walk/south/frame_005.png` | `d54d458baa97bdbd01b902ac4f0d67110889a5881093e7ff2912e1d2d44e5d73` |
| `animations.normal/walk/south-east/frame_000.png` | `7cceb704514bb0056e3c79b3fff82be19998f655fd02496d1265791f6e550eac` |
| `animations.normal/walk/south-east/frame_001.png` | `9ea97df1b464db9812bd9193bb3c36ef9470166475087a91f3bb83c659b40d4a` |
| `animations.normal/walk/south-east/frame_002.png` | `ad57465678558e10bf51ce0735fa6e1f8de93293d9aab5c9c4f3c850953c15d1` |
| `animations.normal/walk/south-east/frame_003.png` | `abacbf91ad3fc9939f789a0520b5aa71171d1c4ef4380ba06b7ea459c4af8278` |
| `animations.normal/walk/south-east/frame_004.png` | `7b83cd84a23cad4b14f15fd14b6e39149291bea8812cf1137956d569f617ff69` |
| `animations.normal/walk/south-east/frame_005.png` | `193fa94e31569890d27b14026f3dec5354e02dc5639238b395848b78ffadca43` |
| `atlases/idle.depth.png` | `9235cf377706b9666c949eca72e062cb239445737ac70f25cc5ee5a786ee94eb` |
| `atlases/idle.normal.png` | `6720dbd8e48ac55733cfaf97fbbe2b9b568e1b59fd173b2dceebaa34e561c013` |
| `atlases/idle.png` | `a3f0e249d86939adcf1f4e1eaf48cf3ad0ece2dee5cff3b77bced2069e10e13a` |
| `atlases/walk.depth.png` | `a3a0a10142835bee7f025460219316fcc0ad8385e3584e089cbd665cd04eb0b0` |
| `atlases/walk.normal.png` | `2aa7a74e5dcb1f713c5509d1dbb24a77f99c63ddb3d63c60a897097c7aca992a` |
| `atlases/walk.png` | `11713fa3b1bd8652b903381b73661de84b20200fb8c875b7b1e723d5405eb82a` |
| `manifest.json` | `97d510dce94445549f4ac2d7b2bcfdf13c5f1802701a662fd5dad93209e85caf` |
| `previews/idle.gif` | `5cc79a6c7f2e435a56736abafa5e11aa7533ab7c2a23cc19340aa45139955088` |
| `previews/idle.lit.gif` | `7eb88d68216cb38310d7288ee41a612121004457a9540e397666a2804e4e68a8` |
| `previews/walk.gif` | `8a94cdd1d2183a4ae0d3b1ca76f1cc02ffb09fb3137f6abad54e1bc3448faa21` |
| `previews/walk.lit.gif` | `17beaffdbe00a1135fb2432b3773b9a7993c8e44db467c56f9154cafa0ed37b2` |

| Positional sheet comparison relative path | SHA-256 |
|---|---|
| `acolyte-lit.idle.gif` | `7eb88d68216cb38310d7288ee41a612121004457a9540e397666a2804e4e68a8` |
| `acolyte-lit.walk.gif` | `17beaffdbe00a1135fb2432b3773b9a7993c8e44db467c56f9154cafa0ed37b2` |
| `acolyte.depth.png` | `41e0ca9d13a517c3ff608759ce2ed8185a0c02e4de28283bdf86c7b622c225bc` |
| `acolyte.idle.gif` | `5cc79a6c7f2e435a56736abafa5e11aa7533ab7c2a23cc19340aa45139955088` |
| `acolyte.json` | `38f549c66fd39b80f378ebf6dce9c6637132a4f63fdf5670dbd1344bc4ac64bb` |
| `acolyte.normal.png` | `373a0773a101910137c531e213d3d7220dea948217de67a460a8a9460fbc9ef2` |
| `acolyte.png` | `8b381581987f1692fc0aedf77ded6fea36d4b2914f3b171ec3697ee45ddda498` |
| `acolyte.walk.gif` | `8a94cdd1d2183a4ae0d3b1ca76f1cc02ffb09fb3137f6abad54e1bc3448faa21` |

## Local evidence and limitations

All rendered images, GLB inputs, scripts, logs, retained work roots and page
assets remain outside git in the round folder above. Old sprite files were
read and copied unchanged into the page folder; `old-source-hashes.json`
identifies each source. They are displayed at their original 48×48 cell size,
without translating pixels to imply anchor agreement. Comparison pages do
not become production exports.

Evidence inventory: `evidence-hashes.json`, SHA-256 `5f5de24d6e14e8f209fe01c22d23e20fc32d8a2719609063bca3985acf2d5387`.
It identifies commands/configs, scripts, page, checks and other key local
records. `capture-checks.json` additionally hashes every retained job.
The four output roots, retained capture buffers and original evidence have
not been overwritten. No model, image or log is committed to git.

The owner alone judges visual quality. Prior model approval, design approval,
pixel identity and successful mechanical checks do not provide that verdict.
The interactive page has been checked structurally and its pixels checked
against outputs, but not opened in a browser by the agent. Only this macOS
execution was used for acceptance evidence.

## Owner verdict

**Pending.** Questions were presented directly in the `mosk-designer-5` pane
on 2026-10-25, with exact `file://` links to this new round. Await explicit
answers on placement/motion, mirroring and this implemented export overall.
Record the owner's words and direct-pane provenance here before marking
accepted. Then report the landed record's commit to the manager for closeout.
