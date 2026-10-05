# Style pass 1 design

**Approved by the owner on 2026-10-04 and ready for issue processing.** The
owner decided every design question ([Decisions](#decisions), D-1 to D-16)
and authorized readiness. This document owns the arc's delivery; the product
contracts stay in [the design](../design.md) and [the vision](../vision.md),
and each slice amends the design sections it implements, as its decisions
require. Approving the design is not a visual verdict: the owner still judges
every rendered look (V-12).

Slice 1 delivered the deliberately plain pipeline, and the owner accepted its
output on 2026-10-03 ([acceptance](../acceptance/slice-1.md)). This arc is the
first step the vision names under "Long-term direction: the style pipeline":
reducing the supersampled capture by each block's most common colour, and
palettes, either authored or extracted from existing art. It benefits the
owner, whose sprites gain a chosen look, and keeps that look reproducible
and swappable for every later asset.

The owner asked for a draft on 2026-10-04 (request `moskophoros-20261004-2`),
approved its defaults that evening, and approved the remaining details,
the acceptance palette and readiness the same night (request
`moskophoros-20261005-1`), each relayed by laz through the moskophoros
manager. See [Decisions](#decisions) for the record.

Design state: `ready for issue processing`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

- [x] EPIC. Deliver the first owner-selected style passes: most-common-colour reduction and palettes — [#50]
- [x] SP1-1. Record the chosen style in the sheet and reuse it — [#51]
- [x] SP1-2. Reduce supersampled frames by each block's most common colour — [#52]
- [x] SP1-3. Read and validate palettes — [#53]
- [x] SP1-4. Map frames onto a palette, alone and with the most-common-colour reduction — [#54]
- [x] SP1-5. Render the offered styles for the owner's visual review — [#55]

## Epic contract

- **Goal:** the owner can render a sheet with the plain look, with the
  most-common-colour reduction, or with either of those mapped onto a chosen
  palette, by choosing options, without any change to capture. The style used
  is recorded in the sheet's JSON and covered by its fingerprint, so a look
  can be reproduced and reused across assets.
- **Done when:** the automated checks pass; the plain look's pixels are
  unchanged from slice 1 for the same input and settings; the owner reviews
  sheets and previews of RobotExpressive rendered in the four looks with the
  [Vince128 acceptance palette](#acceptance-input-vince128) and approves them
  (V-12, D-16). Visual quality has no acceptance criterion other than the
  owner's judgement.
- **Users and operators:** the owner producing game art; agents maintaining
  the tool.
- **Arc label:** None proposed.

## Current state and evidence

Checked on 2026-10-04 at `master` `f00b5ba`, by reading only, and rechecked
unchanged at `649b1e5` on 2026-10-05. No test, build, render or Blender
process ran for this design.

- **Plain stylize.** `stylize.plain` (`src/moskophoros/stylize.py`) reduces
  each frame through `imageops.reduce_blocks`
  (`src/moskophoros/imageops.py:51`), implementing design §Stylize (slice 1:
  plain): coverage is the block's mean alpha, a pixel is transparent below
  0.5, and otherwise takes the alpha-weighted mean RGB, rounded half up, in
  exact integer arithmetic. Output alpha is always 0 or 255.
- **Cleanup** is a pass-through (`src/moskophoros/cleanup.py`).
- **Frames are reduced one at a time.** The command loads each supersampled
  capture and reduces it before loading the next, so only one supersampled
  frame is held at once (`src/moskophoros/cli.py:433`). A pass that works on
  one frame at a time keeps that property; a pass that needs every frame
  first does not.
- **Capture is unchanged by style.** Capture writes one antialiased RGBA color
  buffer per frame (design §Capture). Workbench's studio light `Default`
  shades surfaces smoothly, so a supersampled block usually holds many
  slightly different colours rather than a few flat ones.
- **The sheet `settings` object is shared with the capture job.**
  `capture.backend.settings_document` (`src/moskophoros/capture/backend.py:185`)
  builds the sheet's `settings`, and the same function builds the capture
  job's `settings` (`backend.py:173`; design §job format: "the accepted sheet
  settings"). `blender_script.py` rejects unknown keys in it
  (`blender_script.py:112`). Adding a style field to that object as it stands
  would therefore change the capture job and the Blender script: a capture
  change, which V-8 forbids for a style pass. [D-11](#d-11-record-the-style-in-settingsstyle-outside-the-capture-job-under-schema-2)
  keeps style out of the capture job.
- **Fingerprint and reuse.** The fingerprint hashes `generator`, `settings`
  and `source.sha256` (design §Export). `--settings-from` validates reused
  `settings` strictly: a missing field or an unknown field is a usage error
  (design §Scale and ground point, Reuse). The schema is
  `moskophoros.sheet/1`. `generator.version` is part of the fingerprint, so
  any release that bumps the version already changes every sheet's
  fingerprint, plain or not.
- **Previews.** A GIF frame keeps exact colours when it has at most 256,
  counting the `#808080` background; otherwise it is reduced to 256 by median
  cut without dithering, with a warning (design §Export; `export.py:382`).
  Slice 1's acceptance run printed this warning for both clips.
- **Deferred items.** Design §Deferred defers auxiliary capture buffers until
  "the first style pass that needs them", and style passes and their
  configuration until "the owner starts style work". This arc is that start.
- **Guide.** The slice 1 guide review
  ([report](../guide/2026-10-04T175222Z-c93605c.md)) found no defect, read
  every vision principle as aligned, and recommends carrying the accepted
  plain baseline into the next arc.
- **Tracker.** No open pull request; open issues are #43 (deferred by the
  owner) and epics #3 and #24, whose children are all closed. No overlapping
  style epic exists (rechecked 2026-10-05 at readiness).
- **Acceptance observations** (from the slice 1 acceptance working notes kept
  on the owner's Mac under `~/.local/share/moskophoros-acceptance/robotexpressive/`):
  - the command passed `--directions 8` explicitly, so the JSON records the
    preset as `custom` although the values equal `iso`'s (design §Presets);
  - both previews were reduced to 256 colours, with the warning;
  - RobotExpressive's tallest measured height is 4.24 m, about four times
    human scale, inside the 0.01–100 m band that triggers the unit warning,
    so no warning was printed.

### Acceptance input: Vince128

The owner adopted Vince128 as the palette for this arc's acceptance render
(D-16). It is an input choice, not a visual verdict. Verified on 2026-10-05
from the owner's copy in the takeover task's inputs directory
(`~/Documents/Codex/2026-10-04/task-3/inputs/`):

- **Package:** `vince-128-palette.zip`, 101,032 bytes, SHA-256
  `36cbc94b3f7a5949b884d5adaa57ba8ff4994e0c0b57c4ae4420f0a1a6a21ac8`. Every
  entry of its `SHA256SUMS.txt` matches, and the extracted files below are
  byte-identical to their ZIP entries.
- **Machine palette:** `vince-128.gpl`, a GIMP palette (`Name: Vince 128`,
  16 columns), SHA-256
  `d7fc8fefc702d2492b72f3c34fe34f59b5b8af109bbde853114ed56cce2ca586`.
  128 unique opaque 8-bit sRGB colours; no transparency, pure black or pure
  white.
- **The same colours, in the same row-major order:** `vince-128.hex` (one
  six-digit `RRGGBB` per line, no prefix; SHA-256
  `128cc25786b5711c7685ed1188928109c7d5a2910cd646a9e5e7af58cc71e5e1`),
  `vince-128-grid.png` (16×8 RGB; SHA-256
  `0876d7ca8af05f9104647318b18ddfd29eb636005990a927334f7cc8beeb9c77`) and
  `vince-128-strip.png` (128×1 RGB; SHA-256
  `9210ce6c6cf7e8a1698e3021508a0a815bf73754008b07bc6c022bc5ed873093`). Under
  D-4, all four sources therefore read as the same palette.
- **Not an input:** `vince-128-preview.png`, a labelled presentation sheet
  whose background and text add colours.
- **Provenance, as the package README states it:** an original 128-colour
  palette created for Vince on 4 October 2026, from original selected and
  tuned HSB values. The ramp construction method is credited to Raymond
  Schlitter / SLYNYRD, *Pixelblog 1: Color Palettes*. The author's Mondo
  colours were not sampled or reproduced. The package states no licence, and
  none is inferred here; it is not a third-party palette.
- **Not tracked in git**, like the acceptance model (AGENTS.md §Files). Tests
  generate their own palette fixtures. The acceptance record cites the files
  by name and hash.

## Desired experience

The owner keeps today's command and adds style options. Without them, output
is exactly slice 1's plain look. With them, the owner picks a reduction and,
optionally, a palette file; the sheet's JSON records the style, including the
palette's colours, so `--settings-from` applies the same look to the next
asset without needing the palette file again. Style errors, such as an
unreadable or malformed palette, fail before Blender starts, naming the file
and the problem.

The owner judges the result by viewing the sheet and the animated previews at
the size they will be used. No test claims that a style looks good.

## Scope

### In scope

- A most-common-colour block reduction, as a library image operation and a
  stylize pass (D-1 to D-3).
- Palettes from an authored file, and from existing art by taking its exact
  colours (D-4, D-5).
- Mapping frames onto a palette by nearest colour, without dithering (D-6),
  alone or combined with the most-common-colour reduction (D-7).
- Choosing the style on the command line (D-9, D-10), recording it in the
  sheet and fingerprint, and reusing it with `--settings-from` (D-11, D-12).
- The design amendments, tests and documentation each slice needs; the
  owner's visual review with Vince128 (D-16).

### Out of scope

- Per-material colour ramps: they need a material-ID buffer from capture
  (D-8).
- Palette swaps and other variants (design §Deferred, "Variants").
- Extracting a palette from the subject's own render: it needs every frame
  before any can be reduced, unlike the current one-frame-at-a-time pipeline.
- Quantizing many-colour art down to a palette (median cut, k-means and the
  like); deferred to a later standalone palette-extraction command (V-10,
  D-4).
- Dithering of any kind in the sheet.
- Stepped (cel) shading, outlines, cleanup passes, frame-to-frame stability,
  AI restyling: later style candidates.
- Auxiliary capture buffers. Neither pass in scope needs depth, normals,
  base colour or material IDs, so they stay deferred.
- Saved named style files (D-9).
- Any change to capture, the capture job's bytes or the Blender script. The
  capture job contract changes only to state that style is excluded (D-11).
- The acceptance-hardening items: preset overrides still record `custom`,
  previews keep their current colour reduction and warnings, and model scale
  is unchanged (D-13 to D-15).

## Design

This section describes the approved behaviour; the decision behind each part
is cited. Exact wording of the product contract lands in design.md with the
slice that implements it.

### Stage placement

Both new operations choose colours, so both belong to stylize (V-4: choosing
colours happens after capture). Each is a pure function on one RGBA array in
`imageops`, usable outside the pipeline (V-10); stylize composes them per
frame, so frames stay addressed, keep their metadata and are still reduced one
at a time. Cleanup stays a pass-through. Capture and its job are untouched.
Export lays out and previews whatever frames it receives, as now; its only
change is recording the style, the one-time foundational change D-12
approves.

Output alpha stays 0 or 255 in every style, which export's previews already
require.

### P-1. The most-common-colour reduction

For each `s×s` block of the supersampled frame:

1. **Coverage** is decided exactly as in plain: transparent when the mean
   alpha is below 0.5 (D-2). Silhouettes are therefore identical in both
   reductions.
2. **Votes.** Each pixel votes for its exact RGB, weighted by its alpha, so a
   partly covered edge pixel counts for less, consistent with plain's
   alpha-weighted mean (D-2). A pixel with alpha 0 casts no vote.
3. **Winner.** The colour with the largest vote total. On a tie, the tied
   colour nearest the block's alpha-weighted mean wins, and any remaining tie
   goes to the smallest packed `0xRRGGBB` value, so the result is fully
   determined (D-3). "Nearest" is squared Euclidean distance in 8-bit sRGB
   values, compared exactly against the mean as a fraction, so no floating
   point enters.

Arithmetic is integer, like plain. The result picks a colour that is actually
present in the capture rather than a blend of neighbours, which is the point
of the technique: hard colour boundaries stay hard.

**The known risk.** Under Workbench's smooth shading, a block may hold nearly
as many distinct colours as pixels, so on raw RGB "most common" can collapse
into the tie-break. Voting on palette entries instead of raw colours avoids
that ([P-3](#p-3-combining-the-two)). The owner judges the result at the
review in SP1-5; experiment [E-1](#optional-experiments) can measure it
beforehand if the owner asks.

### P-2. Palettes and mapping

- **Sources** (D-4):
  - `.hex`: one six-digit `RRGGBB` per line, the form palette sites and
    Vince128's `vince-128.hex` use, with no prefix; a leading `#` is also
    accepted, as the draft wrote it;
  - `.gpl`: the GIMP palette format that pixel-art editors read and write
    (`GIMP Palette` header, optional `Name:` and `Columns:` lines, `#`
    comments, then `R G B` with an optional colour name per line);
  - existing art as a PNG: its exact set of distinct colours, in
    first-appearance order (row-major). Every pixel must be opaque, so art
    with transparency is refused rather than guessed at.
- **Limits** (D-5): 1 to 255 opaque RGB colours. An authored file that lists
  a colour twice is refused; a PNG's repeated pixels are simply one colour.
  255 rather than 256 leaves room for the previews' `#808080` background, so
  a paletted preview keeps exact colours.
- **Matching** (D-6): each opaque colour maps to the nearest palette entry by
  Euclidean distance in OKLab, a perceptual colour space, with ties going to
  the earlier palette entry. No dithering. Conversion uses a fixed 256-entry
  sRGB-to-linear table and numpy arithmetic, so results are reproducible
  under the recorded numpy version (design §Reproducibility).
- **Errors** (D-10): an unreadable palette, a malformed line, too few or too
  many colours, a duplicate entry or a non-opaque art pixel is a usage error
  (exit 2), reported before Blender starts, naming the file and, where there
  is one, the line, like an unreadable `--settings-from` file.

### P-3. Combining the two

Four looks, each a fixed composition of the two operations (D-7):

| Look | Steps |
|---|---|
| plain | coverage and alpha-weighted mean (slice 1, unchanged) |
| mode | coverage and most common raw colour (P-1) |
| plain + palette | plain, then map each output pixel to the palette |
| mode + palette | map every supersampled pixel to the palette, then vote on palette entries per block |

In "mode + palette", the vote happens after mapping, so near-identical shades
that map to one entry pool their votes. That is the combination most likely
to give the hard-edged, few-colour look; mapping after a raw-RGB vote would
inherit P-1's tie risk. Coverage, alpha-weighted votes and the tie-break are
P-1's, applied to the palette entries' colours; entries are unique, so the
packed-value step always decides.

### P-4. Choosing and recording the style

- **Command line** (D-9): `--reduce plain|mode` (default `plain`),
  `--palette FILE` (default none) and `--no-palette`. The names map
  one-to-one onto a later saved style file, which this arc does not add.
  Each follows design §Option validation: given twice, it is a usage error.
- **Recording** (D-11): the sheet's `settings` gains a `style` object, for
  example

  ```json
  "style": {
    "reduce": "mode",
    "palette": { "source": "vince-128.gpl", "sha256": "d7fc8fef…",
                 "colors": ["#rrggbb", "…"] }
  }
  ```

  with `"palette": null` when there is none. The colours themselves are
  recorded, in palette order, so the fingerprint covers the exact palette and
  `--settings-from` reuses it without the file. `source` is the palette
  file's base name, never a path (design §Export), and `sha256` is the
  file's. The capture job's `settings` leave `style` out, so the capture
  job's bytes and `blender_script.py` stay unchanged; design §job format only
  gains a sentence saying that style is excluded.
- **Schema** (D-11): the sheet schema becomes `moskophoros.sheet/2`.
  `--settings-from` still accepts a `/1` sheet, reading it as
  `"reduce": "plain"` with no palette; an older tool rejects a `/2` sheet, as
  it should. A reused `/2` `style` is validated as strictly as the rest of
  `settings`, including D-5's limits on its colours.
- **Reuse precedence** (D-10), with `--settings-from`:
  - an explicit `--reduce` changes only the reduction and keeps a reused
    palette;
  - an explicit `--palette FILE` replaces the reused palette;
  - `--no-palette` drops it;
  - `--palette` together with `--no-palette` is a usage error.

The plain look's PNG stays byte-identical to slice 1 for the same input and
settings. Its JSON changes (schema and the new `style` field), and its
fingerprint changes with it; the fingerprint would change anyway at the next
version bump.

### Optional experiments

Not required by any slice and not authorized now: each needs the owner's
request and free machine time (no Blender while other projects' timing-sensitive
tests run). None has run.

- **E-1. How decisive is the vote?** Render RobotExpressive once with the
  acceptance command and a retained `--work-dir`, then, in plain numpy over
  the retained captures, measure per block: the number of distinct colours,
  the winner's share of the vote, and how often the tie-break decides, for raw
  RGB and for Vince128-entry voting.
- **E-2. An early look for the owner.** From the same retained captures,
  produce the four looks of [P-3](#p-3-combining-the-two) with Vince128 as
  throwaway sheets and previews from a prototype script outside the
  repository, so the owner can steer before the slices are built.
- **E-3. Supersample interaction.** Repeat E-1 at `--supersample` 4, 8 and 16:
  more votes per block may make the mode steadier, at more capture cost.

## Decisions

The owner made these decisions on 2026-10-04, in two steps, each relayed by
laz (the owner's verified assistant) through the moskophoros manager:

- **19:17 UTC**, the defaults (the owner's reply; relayed in chat
  `#moskophoros` at 20:35 UTC, laz message `q5g45yjyzh7z4wz49x5raz6evi`,
  request `mosk-style-defaults-approved-20261004-task15`):
  rendering unchanged unless colour reduction is enabled; HEX, GPL and PNG
  palettes; OKLab matching with no dithering initially; style metadata kept
  separate from Blender capture settings, with backward-compatible sheets;
  material ramps and style files deferred; RobotExpressive for the visual
  comparison.
- **22:56 UTC**, the remaining details, Vince128 and readiness (laz messages
  `khjsa2j29ph33jrgrd34w7yuwa` and `rfxu3ehevg8e8cx8b5htz5csz6`, request
  `mosk-vince128-design-issues-20261005-task3`, posted 2026-10-05 00:02 UTC).
  The owner replied "do 2 and 3" to "adopt Vince128 for the RobotExpressive
  acceptance test, settle the remaining style defaults, then process the
  design into issues"; laz's request enumerates the approved details recorded
  below, and states that the approval covers recording the decisions, design
  readiness and issue processing, not implementation or merges.

Each decision names the question it resolves. Inherited and unchanged: the
accepted vision and design, including the plain reduction (design §Stylize
(slice 1: plain)), the deferral of auxiliary buffers, and the owner's slice 1
acceptance.

### D-1. The most-common-colour reduction sits alongside plain, which stays the default

Resolves Q-1 (option A). Decided 2026-10-04 19:17 UTC (rendering unchanged
unless colour reduction is enabled) and 22:56 UTC (preserve the plain default
and the accepted pixels). `mode` is chosen explicitly; without style options,
output is slice 1's plain look, pixel for pixel. Changing the default later is
a separate owner decision. Affects SP1-2.

### D-2. Plain's coverage rule, with alpha-weighted votes

Resolves Q-2 (options A and C). Decided 2026-10-04 22:56 UTC. A pixel is
transparent when its block's mean alpha is below 0.5, exactly as in plain, so
silhouettes never move between reductions; each pixel's vote is its alpha.
Affects SP1-2 and SP1-4.

### D-3. Ties go to the colour nearest the block's mean, then the smallest packed value

Resolves Q-3 (option A). Decided 2026-10-04 22:56 UTC. Deterministic;
experiment E-1 is not a precondition. Affects SP1-2 and SP1-4.

### D-4. Palettes come from `.hex` and `.gpl` files and the exact colours of a PNG

Resolves Q-4 (options A and B). Decided 2026-10-04 19:17 UTC (HEX, GPL and
PNG palettes) and 22:56 UTC (exact PNG colours; quantized extraction deferred
as drafted). Quantized extraction from many-colour art is deferred to a
later standalone command; extracting from the subject's own render is out.
Affects SP1-3.

### D-5. At most 255 opaque colours, and no duplicate entries

Resolves the limits in Q-4 and the palette part of Q-12. Decided 2026-10-04
22:56 UTC. A palette has 1 to 255 opaque RGB colours, so paletted previews
keep exact colours beside the `#808080` background; an authored file that
repeats a colour is refused. Affects SP1-3.

### D-6. Nearest colour in OKLab, earlier entry on a tie, no dithering

Resolves Q-5 (option B, no dithering). Decided 2026-10-04 19:17 UTC (OKLab,
no dithering initially) and 22:56 UTC (deterministic earlier-entry ties).
Affects SP1-4.

### D-7. Four looks, with mode + palette mapping before it votes

Resolves Q-6 (option A). Decided 2026-10-04 22:56 UTC. The looks are plain,
mode, plain + palette and mode + palette. A free chain of passes waits for
saved style files. Affects SP1-2 and SP1-4.

### D-8. Per-material ramps and palette swaps stay out of this arc

Resolves Q-7 (option A). Decided 2026-10-04 19:17 UTC (material ramps
deferred) and 22:56 UTC (deferred as drafted). Ramps will be the trigger for
the first auxiliary capture buffer in a later style arc; palette swaps remain
a variant (design §Deferred). Affects scope only.

### D-9. Options now, saved style files later

Resolves Q-8 (option C). Decided 2026-10-04 19:17 UTC (style files deferred)
and 22:56 UTC (the options). The options are `--reduce plain|mode`,
`--palette FILE` and `--no-palette`. Affects SP1-1, SP1-2 and SP1-4.

### D-10. Reuse precedence for style, and palette errors exit 2 before Blender

Resolves Q-8's sub-choices. Decided 2026-10-04 22:56 UTC. An explicit
`--reduce` changes the reduction and keeps a reused palette; `--palette FILE`
replaces it; `--no-palette` resets it; `--palette` with `--no-palette` is a
usage error. Every palette error is a usage error (exit 2), reported before
Blender starts. Affects SP1-3 and SP1-4.

### D-11. Record the style in `settings.style`, outside the capture job, under schema /2

Resolves Q-9 (options A and D). Decided 2026-10-04 19:17 UTC (style metadata
separate from capture settings; backward-compatible sheets) and 22:56 UTC
(the details). `settings.style` records the reduction and, when there is one,
the palette's exact colours inline, its source base name and its SHA-256. It
is isolated from capture data: the capture job's bytes and contract stay as
they are, apart from documenting the exclusion. The schema becomes
`moskophoros.sheet/2`, and a `/1` sheet reuses as plain with no palette.
Affects SP1-1 and SP1-4.

### D-12. One foundational change to the settings record is accepted under V-8

Resolves Q-10 (option A). Decided 2026-10-04 22:56 UTC. SP1-1 makes the
single change to how the sheet's settings are built and validated that lets
the style be recorded; after it, adding or swapping a pass needs no change to
export or capture. This reads V-8; the vision text is unchanged. Affects
SP1-1.

### D-13. A preset override still records `custom`

Resolves Q-11 (option A). Decided 2026-10-04 22:56 UTC. Design §Presets is
unchanged; outside this arc.

### D-14. Previews keep their current colour handling and warnings

Resolves Q-12 (option A). Decided 2026-10-04 22:56 UTC. Design §Export's
preview rules are unchanged; outside this arc. D-5's 255-colour limit keeps
paletted previews exact.

### D-15. Model scale behaviour is unchanged

Resolves Q-13 (option A). Decided 2026-10-04 22:56 UTC. No scale option and
no change to the unit warning; outside this arc, revisited when the owner's
own models arrive.

### D-16. The acceptance render is RobotExpressive with Vince128

Resolves Q-14 (option A). Decided 2026-10-04 19:17 UTC (RobotExpressive for
the visual comparison) and 22:56 UTC (Vince128). The acceptance render is
RobotExpressive with slice 1's settings, 256×256 cells, the `iso` view,
8 directions, `Walking` looping and `Jump` one-shot, in each of the four
looks, with `vince-128.gpl` as the palette
([evidence](#acceptance-input-vince128)). Choosing the palette is an input
choice, not a visual verdict: the owner still reviews the rendered sheets and
previews (V-12). Affects SP1-5.

## Open questions

None remain open. Every question below was resolved by the owner on
2026-10-04, each by the decision it names, and is kept with its options and
the draft's recommendation as the record of the alternatives that lost.

### Q-1. Does the most-common-colour reduction sit alongside plain, or replace it?

**Resolved by D-1** (option A).

- **A. Alongside, opt-in.** `plain` stays the default; `mode` is chosen
  explicitly. Existing commands keep producing the accepted look.
- **B. Alongside, as the new default.** Every command without style options
  changes look.
- **C. Replace plain.** One reduction only; the accepted baseline disappears.

**Recommendation: A.** It keeps the accepted baseline reproducible and makes
passes swappable (V-8). The default can change later by a separate owner
decision. Affects SP1-2.

### Q-2. Which pixels vote, and how is transparency decided?

**Resolved by D-2** (options A and C).

Transparency:

- **A. Plain's rule:** transparent when mean alpha is below 0.5; only the
  colour choice changes.
- **B. Transparency votes too:** a pixel is transparent when transparent
  pixels win the vote.

Votes:

- **C. Alpha-weighted:** each pixel's vote is its alpha.
- **D. One vote per pixel with any alpha.**
- **E. Only fully opaque pixels vote**, with the alpha-weighted mean as a
  fallback when none is fully opaque.

**Recommendation: A with C.** Silhouettes then match plain exactly, so
switching reductions never moves an outline, and edge pixels weigh in as they
do in plain. Affects SP1-2.

### Q-3. How are ties broken when no colour clearly wins?

**Resolved by D-3** (option A; E-1 is not a precondition).

- **A. Nearest the block's alpha-weighted mean**, then smallest packed value.
- **B. Fall back to the plain mean** whenever the winner has no strict
  plurality. The output may then contain blended colours.
- **C. Smallest packed value only.** Simple, but biased toward dark and red-poor
  colours.

**Recommendation: A**, reviewed after experiment E-1. If raw-RGB voting is
mostly tie-breaks on real captures, the owner may prefer to offer `mode` only
with a palette (see Q-6). Affects SP1-2.

### Q-4. Which palette sources and file formats are in this arc?

**Resolved by D-4** (A and B now, C later, D out) **and D-5** (the limit and
duplicates).

- **A. Authored text files:** `.hex` (one `RRGGBB` per line) and GIMP `.gpl`.
- **B. Exact colours of existing art (PNG)**, refused above the colour limit.
- **C. Quantized extraction from many-colour art** (median cut or similar),
  with a recorded algorithm.
- **D. Extraction from the subject's own render**, which needs every frame
  first.

**Recommendation: A and B now; C later as a standalone palette-extraction
command (V-10); D out.** A and B are exact and need no algorithm whose output
could drift. Also to decide: the colour limit (proposed 255, see Q-12) and
whether duplicates are an error (proposed). Affects SP1-3.

### Q-5. How is a colour matched to a palette entry?

**Resolved by D-6** (option B, no dithering).

- **A. Euclidean distance in sRGB.** Simplest and exact in integers, but it
  matches darks and saturated colours poorly.
- **B. Euclidean distance in OKLab**, a perceptual space; floating point under
  the recorded numpy version.
- **C. CIELAB with a ΔE formula.** Perceptual too, heavier, and not clearly
  better than B for this.

Dithering: **none**, **ordered (Bayer)** or **error diffusion**.

**Recommendation: B, with no dithering.** Error diffusion and ordered
patterns shimmer between frames as the subject moves, against V-7's spirit;
an ordered option can be a later pass. Affects SP1-4.

### Q-6. Which combinations are offered, and in what order?

**Resolved by D-7** (option A).

- **A. All four looks of P-3**, with "mode + palette" voting after mapping.
- **B. All four, with "mode + palette" mapping after a raw-RGB vote.**
- **C. Only plain, plain + palette and mode + palette**: no raw-RGB mode.
- **D. A free chain** of named passes in any order.

**Recommendation: A.** It covers the owner's two named ideas separately and
together, with the combination least exposed to tie-breaks. D belongs with
saved style files later. If E-1 shows raw-RGB voting is mostly tie-breaks,
C is the fallback. Affects SP1-2 and SP1-4.

### Q-7. Are per-material ramps and palette swaps out of this arc?

**Resolved by D-8** (option A).

Per-material ramps assign each material its own run of palette shades. They
need a material-ID buffer from capture, which is an addition to capture
(design §Deferred: auxiliary buffers). Palette swaps are variants.

- **A. Both out**; record ramps as the trigger for the first auxiliary buffer
  in a later style arc.
- **B. Ramps in**, adding a material-ID buffer to capture in this arc.

**Recommendation: A.** It keeps this arc free of capture changes (V-8) and
small. Affects scope only.

### Q-8. How does the owner choose a style on the command line?

**Resolved by D-9** (option C) **and D-10** (the sub-choices, as proposed).

- **A. Options:** `--reduce plain|mode` and `--palette FILE`.
- **B. A style file** (JSON) naming passes and their settings, given with
  `--style FILE`.
- **C. A, with B later**, the option names chosen to map onto a style file.

Sub-choices, proposed: palette-file errors are usage errors (exit 2); an
explicit `--reduce` overrides only the reduction, keeping a reused palette,
and a palette is dropped by a new option such as `--no-palette`.

**Recommendation: C.** Options fit the existing conventional CLI (V-2), and
`--settings-from` already lets one sheet's look carry to the next, which
covers "every asset shares one look" for now. Affects SP1-1, SP1-2 and SP1-4.

### Q-9. Where is the style recorded, and how does an older sheet reuse?

**Resolved by D-11** (options A and D).

Placement:

- **A. `settings.style`, left out of the capture job's `settings`.** One
  settings object for the fingerprint and reuse; capture never sees style.
  Needs the capture job contract's wording ("the accepted sheet settings") to
  say style is excluded.
- **B. A top-level `style` object** beside `settings`. The fingerprint
  definition and `--settings-from` both have to name it separately.
- **C. `settings.style`, also sent to capture.** Changes the capture job and
  `blender_script.py`: a capture change.

Compatibility:

- **D. Bump to `moskophoros.sheet/2`**; reuse accepts `/1` as plain.
- **E. Stay at `/1`** with `style` optional, absent meaning plain. This
  relaxes strict reuse ("every reused field must be present").

**Recommendation: A with D.** Capture stays untouched, reuse stays strict,
and the version tells readers the format changed. Record the palette's
colours inline, plus its source base name and SHA-256. Affects SP1-1.

### Q-10. Is a one-time change to the shared settings record acceptable under V-8?

**Resolved by D-12** (option A).

V-8 says style passes must not require changes to capture or export.
Recording any style at all needs one change to how the sheet's settings are
built and validated, which today is shared by export and the capture job.

- **A. Accept one foundational change in SP1-1** that adds a general `style`
  record, after which adding or swapping a pass needs no export or capture
  change.
- **B. Record nothing about style** in the sheet. Export is untouched, but
  sheets are no longer reproducible from their JSON (against V-2) and the
  fingerprint misses the look (against V-9).

**Recommendation: A.** This is a reading of the vision, so the owner decides
it; the vision text itself is not changed. Affects SP1-1.

### Q-11. Should an explicit option equal to the preset's value still record `custom`?

**Resolved by D-13** (option A, outside this arc).

Slice 1's acceptance run passed `--directions 8` with `--view iso`, and the
JSON recorded `custom`, as design §Presets specifies.

- **A. Keep as designed.** The record says the user overrode the preset.
- **B. Record the preset** when every resolved value equals it. Pixels are
  unchanged; the JSON and fingerprint change for such commands.

**Recommendation: A, and outside this arc** either way: it is not style.
If the owner prefers B, it is a small separate issue.

### Q-12. Should previews keep exact colours for many-colour frames?

**Resolved by D-14** (option A, outside this arc) **and D-5** (the 255-colour
limit).

Plain and raw-RGB mode frames usually exceed 256 colours, so their previews
are reduced, with a warning.

- **A. Keep the current behaviour.** Paletted looks, with at most 255
  colours plus the background, always preview exactly.
- **B. One palette per clip** instead of per frame: steadier colours, still
  reduced.
- **C. A lossless animated format** (animated PNG or WebP) for previews,
  changing what previews are.

**Recommendation: A, outside this arc**, keeping the palette limit at 255 so
paletted previews are exact. Affects SP1-3's colour limit.

### Q-13. Should a model far from human scale be flagged or corrected?

**Resolved by D-15** (option A, outside this arc).

RobotExpressive measured 4.24 m tall, inside the 0.01–100 m unit-warning band.
Auto-fit hides scale entirely; it matters when one fixed `--ppm` is shared
across subjects, as V-7 intends for relative sizes.

- **A. No change.** The model's size is the input's (V-11 states
  expectations; the model is a stand-in, not the owner's art).
- **B. A `--model-scale` option**, recorded in settings, to correct a model.
- **C. Always report the measured height**, or narrow the warning band.

**Recommendation: A for now, outside this arc**, revisited when the owner's
own models arrive. B or C would be a separate geometry issue, not style.

### Q-14. Which model, palette and settings does the owner want to review?

**Resolved by D-16** (option A, with Vince128 as the palette).

SP1-5 and experiment E-2 need a model, a palette and a command.

- **A. RobotExpressive with the acceptance command** (256×256, iso, 8
  directions, `Walking` and `Jump`), plus a palette the owner supplies or
  picks.
- **B. One of the owner's own models** when available.

**Recommendation: A**, so the plain baseline is the direct comparison, with
B added when a model exists. The owner must name the palette; the tool ships
none. Affects SP1-5.

## Verification strategy

- **Plain is untouched.** For the same constructed frames, `plain` output is
  byte-identical to slice 1's `reduce_blocks`; existing plain tests keep
  passing unchanged.
- **Constructed arrays** test the reduction: alpha weighting, alpha-0 pixels
  casting no vote, the coverage threshold matching plain's silhouettes, each
  tie-break step with exact distances to the mean, a factor of 1, and inputs
  left unmodified.
- **Palettes**, from files the tests generate (no palette is tracked): every
  accepted format parses to the expected colours in order, `.hex` with and
  without `#`, and a PNG's colours in first-appearance order; each error
  (unreadable, malformed line, no colours, a duplicate entry, over 255
  colours, a non-opaque art pixel) gives exit 2 naming the file and line,
  before Blender starts.
- **Mapping:** independently computed nearest entries for chosen colours,
  ties going to the earlier entry, and mode-after-mapping pooling votes.
- **Recording:** the style appears in `settings`, changes the fingerprint
  when it changes, round-trips through `--settings-from` with each D-10
  precedence case, `--palette` with `--no-palette` is refused, and a `/1`
  sheet reuses as plain with no palette. A test asserts the capture job's
  bytes are the same with and without style options.
- **Determinism:** two runs with each style give byte-identical PNG and JSON
  (the Blender test group, run locally per [validation](../validation.md)).
- **Visual quality** is the owner's judgement only (V-12), from the sheets and
  previews in SP1-5. No test or metric stands in for it; E-1's statistics,
  if the owner asks for them, inform choices, not acceptance.

Every slice amends the design sections its decisions change, landing that
documentation with `docs-push` and linking it from the pull request (AGENTS.md
§Delivery): §CLI and §Option validation for the options, §Stylize for the
passes, §Export and §Scale and ground point (Reuse) for the record, schema and
reuse, §job format for the exclusion, and §Deferred for what this arc
settles.

## Delivery plan

Five slices, in dependency order. SP1-1 and SP1-3 can start in parallel;
SP1-2 needs SP1-1; SP1-4 needs SP1-2 and SP1-3; SP1-5 closes the arc with the
owner's review.

### SP1-1. Record the chosen style in the sheet and reuse it

- **Outcome:** sheets record `settings.style` (plain only) under schema `/2`,
  covered by the fingerprint and reused by `--settings-from`; the capture job
  is unchanged.
- **Scope:** the `settings.style` record (`reduce` and a null `palette`) and
  its strict validation on reuse, the schema bump, `/1` reuse as plain,
  keeping style out of the capture job, the `--reduce` option accepting only
  `plain` for now, and the design amendments for these.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** critical path; can land first.
- **Relevant decisions:** D-1, D-9, D-11, D-12.
- **Acceptance signals:** plain PNG bytes unchanged; JSON carries the style
  under `moskophoros.sheet/2`; `/1` and `/2` reuse and override tests;
  capture-job bytes unchanged.
- **Out of scope:** any new look; palette options and recording (SP1-4).
- **Open questions:** None.

### SP1-2. Reduce supersampled frames by each block's most common colour

- **Outcome:** `--reduce mode` produces the most-common-colour look.
- **Scope:** the `imageops` operation (P-1), the stylize pass, the `mode`
  option value and its recording, and the design §Stylize amendment.
- **Phase:** 2.
- **Depends on:** SP1-1.
- **Ordering:** critical path.
- **Relevant decisions:** D-1, D-2, D-3, D-7, D-9.
- **Acceptance signals:** constructed-array tests for votes, coverage and
  ties; plain still byte-identical; determinism of `--reduce mode` runs.
- **Out of scope:** palettes; changing the default.
- **Open questions:** None.

### SP1-3. Read and validate palettes

- **Outcome:** a pure palette reader for the accepted sources, with its errors.
- **Scope:** `.hex`, `.gpl` and exact-colour PNG reading as P-2 describes,
  the 1–255 opaque-colour limit, duplicate refusal, and error messages naming
  the file and line; a pure module with no pipeline wiring.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** independent; can land first, alongside SP1-1.
- **Relevant decisions:** D-4, D-5, D-10.
- **Acceptance signals:** parse and error tests on generated files.
- **Out of scope:** mapping; command-line options; quantized extraction.
- **Open questions:** None.

### SP1-4. Map frames onto a palette, alone and with the most-common-colour reduction

- **Outcome:** `--palette FILE` produces the plain + palette and mode +
  palette looks, recorded and reusable.
- **Scope:** the OKLab mapping operation, its composition with both
  reductions (P-3), `--palette FILE` and `--no-palette` with D-10's reuse
  precedence, palette errors before Blender starts, and recording the
  palette's colours, base name and SHA-256 in `settings.style`.
- **Phase:** 3.
- **Depends on:** SP1-2, SP1-3.
- **Ordering:** critical path.
- **Relevant decisions:** D-6, D-7, D-9, D-10, D-11.
- **Acceptance signals:** mapping tests; recorded colours reuse without the
  file; every precedence case; paletted previews keep exact colours.
- **Out of scope:** dithering; per-material ramps; palette swaps.
- **Open questions:** None.

### SP1-5. Render the offered styles for the owner's visual review

- **Outcome:** the owner reviews RobotExpressive's sheets and previews in
  each of the four looks with Vince128 and approves or redirects (V-12).
- **Scope:** render D-16's input (256×256, `iso`, 8 directions, `Walking`
  looping and `Jump` one-shot) once per look, with `vince-128.gpl` for the
  paletted looks, checking that each sheet's JSON records the palette's
  SHA-256 `d7fc8fef…ca586`; an acceptance record like
  `docs/acceptance/slice-1.md`, with the exact reproducing commands, output
  hashes and the [Vince128 provenance](#acceptance-input-vince128); design
  §Deferred updated for what the arc settled.
- **Phase:** 4.
- **Depends on:** SP1-4.
- **Ordering:** critical path; needs free machine time for Blender.
- **Relevant decisions:** D-14, D-16.
- **Acceptance signals:** the owner's recorded verdict on the rendered
  output. The palette choice alone is not that verdict.
- **Out of scope:** choosing a default look unless the owner asks; tracking
  the palette files or renders in git.
- **Open questions:** None.

## Readiness

**Ready for issue processing**, on the owner's authorization of 2026-10-04
22:56 UTC, which covers recording these decisions, readiness and issue
processing (see [Decisions](#decisions)).

- The epic goal and done condition are observable: options select four looks,
  plain stays byte-identical, and the owner's verdict on the Vince128 render
  closes the arc.
- Scope and non-goals are explicit, including the deferred ramps, style
  files, quantized extraction and the three hardening items kept outside.
- All fourteen questions are resolved by D-1 to D-16; none is deliberately
  left open.
- Five one-PR slices, dependency-ordered, mirrored in the processing ledger.
- Compatibility (schema `/2`, `/1` reuse), persistence (style recorded
  inline), determinism (integer reduction, fixed tie-breaks, recorded numpy
  for OKLab), documentation (design amendments by `docs-push`) and tests
  (generated fixtures; the Blender group for determinism) are recorded.
- No overlapping epic exists: open issues are #3, #24 and #43, with no open
  pull request (checked 2026-10-05).

Readiness does not authorize implementation. `/process-design-doc` processes
the epic first, then exactly one child per invocation, with separate approval
for every tracker artifact.
