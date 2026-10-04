# Style pass 1 design

**DRAFT for the owner's review. Not approved.** Nothing here is decided, and
it changes no accepted contract. Every choice below is a proposal with a
recommendation, listed under [Open questions](#open-questions) for the owner
to decide (vision V-8). The accepted contracts stay in
[the design](../design.md) and [the vision](../vision.md) until the owner
approves a change to them.

Slice 1 delivered the deliberately plain pipeline, and the owner accepted its
output on 2026-10-03 ([acceptance](../acceptance/slice-1.md)). This arc is the
first step the vision names under "Long-term direction: the style pipeline":
reducing the supersampled capture by each block's most common colour, and
palettes, either authored or extracted from existing art. It benefits the
owner, whose sprites gain a chosen look, and keeps that look reproducible
and swappable for every later asset.

The owner asked for this draft on 2026-10-04, through laz and the moskophoros
manager (request `moskophoros-20261004-2`).

Design state: `exploring` — **DRAFT, not approved**

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

DRAFT: the slices below are a sketch for discussion. None is approved, and no
issue may be filed from this document until the owner decides the open
questions and declares it ready.

- [ ] EPIC. Deliver the first owner-selected style passes: most-common-colour reduction and palettes
- [ ] SP1-1. Record the chosen style in the sheet and reuse it
- [ ] SP1-2. Reduce supersampled frames by each block's most common colour
- [ ] SP1-3. Read and validate palettes
- [ ] SP1-4. Map frames onto a palette, alone and with the most-common-colour reduction
- [ ] SP1-5. Render the offered styles for the owner's visual review

## Epic contract

- **Goal:** the owner can render a sheet with the plain look, with the
  most-common-colour reduction, or with either of those mapped onto a chosen
  palette, by choosing options, without any change to capture. The style used
  is recorded in the sheet's JSON and covered by its fingerprint, so a look
  can be reproduced and reused across assets.
- **Done when:** the automated checks pass; the plain look's pixels are
  unchanged from slice 1 for the same input and settings; the owner reviews
  sheets and previews rendered with the offered styles and approves them
  (V-12). Visual quality has no acceptance criterion other than the owner's
  judgement.
- **Users and operators:** the owner producing game art; agents maintaining
  the tool.
- **Arc label:** None proposed.

## Current state and evidence

Checked on 2026-10-04 at `master` `f00b5ba`, by reading only. No test, build,
render or Blender process ran for this draft.

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
  change, which V-8 forbids for a style pass. See [Q-9](#q-9-where-is-the-style-recorded-and-how-does-an-older-sheet-reuse).
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
  style epic exists.
- **Acceptance observations** (from the slice 1 acceptance working notes kept
  on the owner's Mac under `~/.local/share/moskophoros-acceptance/robotexpressive/`):
  - the command passed `--directions 8` explicitly, so the JSON records the
    preset as `custom` although the values equal `iso`'s (design §Presets);
  - both previews were reduced to 256 colours, with the warning;
  - RobotExpressive's tallest measured height is 4.24 m, about four times
    human scale, inside the 0.01–100 m band that triggers the unit warning,
    so no warning was printed.

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

### In scope (proposed)

- A most-common-colour block reduction, as a library image operation and a
  stylize pass ([Q-1](#q-1-does-the-most-common-colour-reduction-sit-alongside-plain-or-replace-it)
  to [Q-3](#q-3-how-are-ties-broken-when-no-colour-clearly-wins)).
- Palettes from an authored file, and from existing art by taking its exact
  colours ([Q-4](#q-4-which-palette-sources-and-file-formats-are-in-this-arc)).
- Mapping frames onto a palette by nearest colour, without dithering
  ([Q-5](#q-5-how-is-a-colour-matched-to-a-palette-entry)), alone or combined
  with the most-common-colour reduction
  ([Q-6](#q-6-which-combinations-are-offered-and-in-what-order)).
- Choosing the style on the command line
  ([Q-8](#q-8-how-does-the-owner-choose-a-style-on-the-command-line)),
  recording it in the sheet and fingerprint, and reusing it with
  `--settings-from` ([Q-9](#q-9-where-is-the-style-recorded-and-how-does-an-older-sheet-reuse)).
- The design, tests and documentation each slice needs; owner visual review.

### Out of scope (proposed)

- Per-material colour ramps: they need a material-ID buffer from capture
  ([Q-7](#q-7-are-per-material-ramps-and-palette-swaps-out-of-this-arc)).
- Palette swaps and other variants (design §Deferred, "Variants").
- Extracting a palette from the subject's own render: it needs every frame
  before any can be reduced, unlike the current one-frame-at-a-time pipeline.
- Quantizing many-colour art down to a palette (median cut, k-means and the
  like); proposed for a later standalone palette-extraction command (V-10).
- Dithering of any kind in the sheet.
- Stepped (cel) shading, outlines, cleanup passes, frame-to-frame stability,
  AI restyling: later style candidates.
- Auxiliary capture buffers. Neither pass in scope needs depth, normals,
  base colour or material IDs, so they stay deferred.
- Saved named style files ([Q-8](#q-8-how-does-the-owner-choose-a-style-on-the-command-line)).
- Any change to capture, the capture job or the Blender script.
- The acceptance-hardening items, unless the owner pulls them in
  ([Q-11](#q-11-should-an-explicit-option-equal-to-the-presets-value-still-record-custom)
  to [Q-13](#q-13-should-a-model-far-from-human-scale-be-flagged-or-corrected)).

## Design

Everything in this section is a **proposal** awaiting the owner's decisions.

### Stage placement

Both new operations choose colours, so both belong to stylize (V-4: choosing
colours happens after capture). Each is a pure function on one RGBA array in
`imageops`, usable outside the pipeline (V-10); stylize composes them per
frame, so frames stay addressed, keep their metadata and are still reduced one
at a time. Cleanup stays a pass-through. Capture and its job are untouched.
Export lays out and previews whatever frames it receives, as now; its only
change is recording the style ([Q-10](#q-10-is-a-one-time-change-to-the-shared-settings-record-acceptable-under-v-8)).

Output alpha stays 0 or 255 in every style, which export's previews already
require.

### P-1. The most-common-colour reduction

For each `s×s` block of the supersampled frame:

1. **Coverage** is decided exactly as in plain: transparent when the mean
   alpha is below 0.5 ([Q-2](#q-2-which-pixels-vote-and-how-is-transparency-decided)).
2. **Votes.** Each pixel votes for its exact RGB, weighted by its alpha, so a
   partly covered edge pixel counts for less, consistent with plain's
   alpha-weighted mean ([Q-2](#q-2-which-pixels-vote-and-how-is-transparency-decided)).
3. **Winner.** The colour with the largest vote total. On a tie, the tied
   colour nearest the block's alpha-weighted mean wins, and any remaining tie
   goes to the smallest packed `0xRRGGBB` value, so the result is fully
   determined ([Q-3](#q-3-how-are-ties-broken-when-no-colour-clearly-wins)).

Arithmetic is integer, like plain. The result picks a colour that is actually
present in the capture rather than a blend of neighbours, which is the point
of the technique: hard colour boundaries stay hard.

**The risk.** Under Workbench's smooth shading, a block may hold nearly as
many distinct colours as pixels, so on raw RGB "most common" can collapse
into the tie-break. Voting on palette entries instead of raw colours avoids
that ([P-3](#p-3-combining-the-two)). How often it happens on a real model is
the first proposed experiment, [E-1](#proposed-experiments).

### P-2. Palettes and mapping

- **Sources** ([Q-4](#q-4-which-palette-sources-and-file-formats-are-in-this-arc)):
  - an authored text palette: one `#RRGGBB` per line (the `.hex` form
    common on palette sites) and the GIMP `.gpl` format that pixel-art
    editors read and write;
  - existing art as a PNG: its exact set of distinct opaque colours, in
    first-appearance order (row-major), refused when there are more than the
    limit.
- **Limits.** 1 to 255 colours, opaque RGB only; duplicates rejected. 255
  rather than 256 leaves room for the previews' `#808080` background, so a
  paletted preview always keeps exact colours (see [Q-12](#q-12-should-previews-keep-exact-colours-for-many-colour-frames)).
- **Matching** ([Q-5](#q-5-how-is-a-colour-matched-to-a-palette-entry)):
  each opaque colour maps to the nearest palette entry by Euclidean distance
  in OKLab, a perceptual colour space, with ties going to the earlier palette
  entry. No dithering. Conversion uses a fixed 256-entry sRGB-to-linear table
  and numpy arithmetic, so results are reproducible under the recorded numpy
  version (design §Reproducibility).
- **Errors.** An unreadable palette, a malformed line, too many colours, a
  duplicate or a non-opaque art pixel is a usage error (exit 2) naming the
  file and, where there is one, the line, like an unreadable
  `--settings-from` file ([Q-8](#q-8-how-does-the-owner-choose-a-style-on-the-command-line)).

### P-3. Combining the two

Four looks, each a fixed composition of the two operations
([Q-6](#q-6-which-combinations-are-offered-and-in-what-order)):

| Look | Steps |
|---|---|
| plain | coverage and alpha-weighted mean (slice 1, unchanged) |
| mode | coverage and most common raw colour (P-1) |
| plain + palette | plain, then map each output pixel to the palette |
| mode + palette | map every supersampled pixel to the palette, then vote on palette entries per block |

In "mode + palette", the vote happens after mapping, so near-identical shades
that map to one entry pool their votes. That is the combination most likely
to give the hard-edged, few-colour look; mapping after a raw-RGB vote would
inherit P-1's tie risk.

### P-4. Choosing and recording the style

- **Command line** ([Q-8](#q-8-how-does-the-owner-choose-a-style-on-the-command-line)):
  `--reduce plain|mode` (default `plain`) and `--palette FILE` (default none).
  The names map one-to-one onto a later saved style file, which this arc does
  not add.
- **Recording** ([Q-9](#q-9-where-is-the-style-recorded-and-how-does-an-older-sheet-reuse)):
  the sheet's `settings` gains a `style` object, for example

  ```json
  "style": {
    "reduce": "mode",
    "palette": { "source": "dusk.gpl", "sha256": "…",
                 "colors": ["#1a1c2c", "#5d275d", "…"] }
  }
  ```

  with `"palette": null` when there is none. The colours themselves are
  recorded, so the fingerprint covers the exact palette and `--settings-from`
  reuses it without the file; `source` is a base name, never a path (design
  §Export). The capture job's `settings` leave `style` out, so the capture job
  and `blender_script.py` stay unchanged.
- **Schema.** The sheet schema becomes `moskophoros.sheet/2`.
  `--settings-from` still accepts a `/1` sheet, reading it as
  `"reduce": "plain"` with no palette; an older tool rejects a `/2` sheet, as
  it should.
- **Reuse precedence.** As for every reused setting: explicit `--reduce` or
  `--palette` overrides the reused value. Whether an explicit `--reduce plain`
  also drops a reused palette is part of [Q-8](#q-8-how-does-the-owner-choose-a-style-on-the-command-line).

The plain look's PNG stays byte-identical to slice 1 for the same input and
settings. Its JSON changes (schema and the new `style` field), and its
fingerprint changes with it; the fingerprint would change anyway at the next
version bump.

### Proposed experiments

For later machine time, after the Synarchy timing-sensitive tests are clear.
None ran for this draft.

- **E-1. How decisive is the vote?** Render RobotExpressive once with the
  acceptance command and a retained `--work-dir`, then, in plain numpy over
  the retained captures, measure per block: the number of distinct colours,
  the winner's share of the vote, and how often the tie-break decides, for raw
  RGB and for palette-entry voting. Informs [Q-3](#q-3-how-are-ties-broken-when-no-colour-clearly-wins)
  and [Q-6](#q-6-which-combinations-are-offered-and-in-what-order).
- **E-2. An early look for the owner.** From the same retained captures,
  produce the four looks of [P-3](#p-3-combining-the-two) as throwaway sheets
  and previews with a prototype script outside the repository, so the owner
  can steer before the slices are built. Needs a palette from the owner
  ([Q-14](#q-14-which-model-palette-and-settings-does-the-owner-want-to-review)).
- **E-3. Supersample interaction.** Repeat E-1 at `--supersample` 4, 8 and 16:
  more votes per block may make the mode steadier, at more capture cost.

## Decisions

None yet. Every `Q-N` below is an owner decision; this draft records no
choice as made.

Inherited and unchanged: the accepted vision and design, including the plain
reduction (design §Stylize (slice 1: plain)), the deferral of auxiliary
buffers, and the owner's slice 1 acceptance.

## Open questions

Each question lists options and a recommendation. The recommendation is the
draft author's, not a decision.

### Q-1. Does the most-common-colour reduction sit alongside plain, or replace it?

- **A. Alongside, opt-in.** `plain` stays the default; `mode` is chosen
  explicitly. Existing commands keep producing the accepted look.
- **B. Alongside, as the new default.** Every command without style options
  changes look.
- **C. Replace plain.** One reduction only; the accepted baseline disappears.

**Recommendation: A.** It keeps the accepted baseline reproducible and makes
passes swappable (V-8). The default can change later by a separate owner
decision. Affects SP1-2.

### Q-2. Which pixels vote, and how is transparency decided?

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

- **A. Nearest the block's alpha-weighted mean**, then smallest packed value.
- **B. Fall back to the plain mean** whenever the winner has no strict
  plurality. The output may then contain blended colours.
- **C. Smallest packed value only.** Simple, but biased toward dark and red-poor
  colours.

**Recommendation: A**, reviewed after experiment E-1. If raw-RGB voting is
mostly tie-breaks on real captures, the owner may prefer to offer `mode` only
with a palette (see Q-6). Affects SP1-2.

### Q-4. Which palette sources and file formats are in this arc?

- **A. Authored text files:** `.hex` (one `#RRGGBB` per line) and GIMP `.gpl`.
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

- **A. All four looks of P-3**, with "mode + palette" voting after mapping.
- **B. All four, with "mode + palette" mapping after a raw-RGB vote.**
- **C. Only plain, plain + palette and mode + palette**: no raw-RGB mode.
- **D. A free chain** of named passes in any order.

**Recommendation: A.** It covers the owner's two named ideas separately and
together, with the combination least exposed to tie-breaks. D belongs with
saved style files later. If E-1 shows raw-RGB voting is mostly tie-breaks,
C is the fallback. Affects SP1-2 and SP1-4.

### Q-7. Are per-material ramps and palette swaps out of this arc?

Per-material ramps assign each material its own run of palette shades. They
need a material-ID buffer from capture, which is an addition to capture
(design §Deferred: auxiliary buffers). Palette swaps are variants.

- **A. Both out**; record ramps as the trigger for the first auxiliary buffer
  in a later style arc.
- **B. Ramps in**, adding a material-ID buffer to capture in this arc.

**Recommendation: A.** It keeps this arc free of capture changes (V-8) and
small. Affects scope only.

### Q-8. How does the owner choose a style on the command line?

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

Slice 1's acceptance run passed `--directions 8` with `--view iso`, and the
JSON recorded `custom`, as design §Presets specifies.

- **A. Keep as designed.** The record says the user overrode the preset.
- **B. Record the preset** when every resolved value equals it. Pixels are
  unchanged; the JSON and fingerprint change for such commands.

**Recommendation: A, and outside this arc** either way: it is not style.
If the owner prefers B, it is a small separate issue.

### Q-12. Should previews keep exact colours for many-colour frames?

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
- **Constructed arrays** test the reduction: alpha weighting, the coverage
  threshold matching plain's silhouettes, each tie-break step, a single-pixel
  factor, and inputs left unmodified.
- **Palettes:** every accepted format parses to the expected colours; each
  error (unreadable, malformed line, duplicate, over the limit, non-opaque
  art pixel) gives exit 2 naming the file and line.
- **Mapping:** independently computed nearest entries for chosen colours,
  ties going to the earlier entry, and mode-after-mapping pooling votes.
- **Recording:** the style appears in `settings`, changes the fingerprint
  when it changes, round-trips through `--settings-from` with overrides, and a
  `/1` sheet reuses as plain. A test asserts the capture job is unchanged by
  any style option.
- **Determinism:** two runs with each style give byte-identical PNG and JSON
  (the Blender test group, run locally per [validation](../validation.md)).
- **Visual quality** is the owner's judgement only (V-12), from the sheets and
  previews in SP1-5. No test or metric stands in for it; E-1's statistics
  inform design choices, not acceptance.

## Delivery plan

DRAFT sketch for discussion; boundaries follow the recommendations above and
change with the owner's answers.

### SP1-1. Record the chosen style in the sheet and reuse it

- **Outcome:** sheets record `settings.style` (plain only) under schema `/2`,
  covered by the fingerprint and reused by `--settings-from`; the capture job
  is unchanged.
- **Scope:** the style record and its validation, schema bump, `/1` reuse,
  capture-job exclusion, the `--reduce` option accepting only `plain`, and the
  design text for these.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** critical path; can land first.
- **Relevant decisions:** none yet (Q-8, Q-9, Q-10).
- **Acceptance signals:** plain PNG bytes unchanged; JSON carries the style;
  reuse and override tests; capture-job bytes unchanged.
- **Out of scope:** any new look.
- **Open questions:** Q-8, Q-9, Q-10.

### SP1-2. Reduce supersampled frames by each block's most common colour

- **Outcome:** `--reduce mode` produces the most-common-colour look.
- **Scope:** the `imageops` operation, the stylize pass, the option value,
  design §Stylize text.
- **Phase:** 2.
- **Depends on:** SP1-1.
- **Ordering:** critical path.
- **Relevant decisions:** none yet (Q-1, Q-2, Q-3, Q-6).
- **Acceptance signals:** constructed-array tests for votes, coverage and
  ties; determinism.
- **Out of scope:** palettes.
- **Open questions:** Q-1, Q-2, Q-3, Q-6.

### SP1-3. Read and validate palettes

- **Outcome:** a pure palette reader for the accepted sources, with its errors.
- **Scope:** `.hex`, `.gpl` and exact-colour PNG reading, limits, error
  messages; no pipeline wiring.
- **Phase:** 1.
- **Depends on:** none.
- **Ordering:** independent; can land first, alongside SP1-1.
- **Relevant decisions:** none yet (Q-4, Q-12).
- **Acceptance signals:** parse and error tests on generated files.
- **Out of scope:** mapping; quantized extraction.
- **Open questions:** Q-4, Q-12.

### SP1-4. Map frames onto a palette, alone and with the most-common-colour reduction

- **Outcome:** `--palette FILE` produces the plain + palette and mode +
  palette looks, recorded and reusable.
- **Scope:** the mapping operation, its composition with both reductions,
  the option and its reuse precedence, palette recording.
- **Phase:** 3.
- **Depends on:** SP1-2, SP1-3.
- **Ordering:** critical path.
- **Relevant decisions:** none yet (Q-5, Q-6, Q-8, Q-9).
- **Acceptance signals:** mapping tests; recorded colours reuse without the
  file; paletted previews keep exact colours.
- **Out of scope:** dithering; per-material ramps.
- **Open questions:** Q-5, Q-6, Q-8.

### SP1-5. Render the offered styles for the owner's visual review

- **Outcome:** the owner reviews sheets and previews in each offered look and
  approves or redirects (V-12).
- **Scope:** exact reproducing commands, an acceptance record like
  `docs/acceptance/slice-1.md`, design §Deferred updated.
- **Phase:** 4.
- **Depends on:** SP1-4.
- **Ordering:** critical path; needs machine time for Blender.
- **Relevant decisions:** none yet (Q-14).
- **Acceptance signals:** the owner's recorded verdict.
- **Out of scope:** choosing a default look unless the owner asks.
- **Open questions:** Q-14.

## Readiness

Not ready: this is a draft. All fourteen questions are open, and the owner
has not reviewed the scope or the slices. Before readiness: the owner answers
Q-1 to Q-10 and Q-14 (Q-11 to Q-13 may be answered "outside this arc"), the
answers are recorded as decisions, the slices are re-cut to match, and the
owner explicitly declares the design ready. Accepted answers that change a
product contract (design §CLI, §Stylize, §Export, §job format, §Deferred) are
written into the design only on the owner's approval.
