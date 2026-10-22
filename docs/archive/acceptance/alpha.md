# Alpha acceptance

This records the owner's acceptance of the alpha arc, following #119 (ALPHA-7) and vision V-12. The arc is epic #113. Its code slices were delivered with:

| Slice | Issue | Pull request |
|---|---|---|
| ALPHA-1, capture colour and buffers in one flat Cycles render | #114 | #121 |
| ALPHA-2, cut out `MASK` materials | #115 | #122 |
| ALPHA-3, 8-bit alpha, the `edges` setting and preview blending (with ALPHA-6) | #116 | #123 |
| ALPHA-4, capture and composite translucent layers | #117 | #124 |
| ALPHA-5, give translucent materials identities and ramps | #118 | #125 |

The design is [`docs/archive/designs/alpha_design.md`](../designs/alpha_design.md).

**Cutouts are judged separately, in [Cutouts](#cutouts).** The chest has no `MASK` material: the owner removed the cutout from the test model while making it (see [Input](#input)). This review judges translucency (`BLEND`, with an alpha gradient), the combined front layer (D-12), the occlusion baseline (D-7) and both `edges` values. A second model, a potted shrub with `MASK` leaf cards, was made for the cutouts.

## Verdict

**Accepted by the owner, confirmed on 2026-10-19 at 03:20 UTC, with one defect found in review and fixed in the model.** The owner gave it in two messages, both typed in the moskophoros manager's terminal and relayed by the manager.

**The owner's answers**, at about 03:05 UTC, to five questions the manager asked about the comparisons (summarised: 1, are `hard` and `soft` both right; 2, should the glow haze past the chest be in the sprite; 3, D-12, does the single combined glow layer read as light; 4, D-7, does the darkening inside the chest and under the lid look natural; 5, the look apart from alpha):

> "1) yes, hard and soft are both working very well, these are both requirements so that's good, we arent choosing between the two. 2) yes the glow looks good. this is just a test sprite, so there are no requirements. 3) yes the library versions are outstanding, especially along the top of the crate and the glow, and the edges where the wood meets the bronze bands, these are particularly strong. 4) it looks natural, i like it. one thing i did notice, take a look at north-west at frame 17 with a dark background. the glow ends at a firm line, it doesnt fade away, it needs to fade out. 5) the wood could honestly have more shading, and perhaps some more texture to it, but we can do that later, the lines of the wood planks are imperceptable on the plain images, but they look great with the library. for any object i want the option i select, but if i were to use this in my game, i would take library-hard, but i could see myself using library-soft for a different project, these are good."

Relay: the manager's file `relay-119-verdict.md` (SHA-256 `77ec63757cbb8992e8e3b53a3a51974808b742b4760540fe45f5f56118548fbc`), delivered by cmux message `a51e81e0-8190-47be-ab85-99ff495d2e59`. The file gives the manager's reading of the answers, which the owner then confirmed:

- **D-7, the occlusion baseline: accepted** ("it looks natural, i like it"). The shade keeps today's approximation, in which the translucent glow occludes as if solid. No investigation of occlusion through translucency follows.
- **D-12, the combined front layer: accepted** (question 3, "yes"). The glow's stacked sheets combine into one front layer, ramped by the front-most material. Translucent layers are not kept separately.
- **Edges:** `hard` and `soft` both work and are both requirements; neither is preferred.
- **One defect:** in north-west, frame 17, over a dark background, the glow ended at a firm line instead of fading out.
- **Not requested now:** more shading and texture for the wood ("we can do that later").

**The owner's confirmation**, at 03:20:13 UTC, after the defect was traced to the model ([below](#the-firm-line)):

> "yes, you dont need my permission to rebuild a blender model, you thats just local compute, then rerun the renders. i confirm your vertict, once the glow is taken care of, then we can move on"

Relay: cmux message `5a50a60e-7ad3-4b1f-99df-0210b7c09a00` from the manager, which also states that the owner's words authorise rerunning the signed-off commands on the rebuilt model, unchanged except for the model and its SHA-256.

The verdict is the owner's alone (V-12). This record quotes it and does not extend it. It is bound to the reruns on model v5 listed under [Output](#output), made from master `18e764a6` (the merge of #125). The firm line is gone from them, checked by reading the files.

### The firm line

The owner's firm line was caused by the model, not by moskophoros. The glow's gradient texture had no wrap mode, so glTF's default `REPEAT` applied. At each glow sheet's tip, the texture's transparent last row was filtered together with its opaque first row: a thin rim of alpha up to about 0.23 (59 of 255) ran along the tip, and the sheet's geometry ended there. A diagnostic copy of the model with the texture clamped (`CLAMP_TO_EDGE`), rendered with the `plain-hard` settings, removed the rim and let the glow fade out. The fix is one line in the model's script (Blender's image `extension` set to `EXTEND`), rebuilt as model v5. Nothing in moskophoros changed, and no issue follows.

In north-west, frame 17, the translucent pixels along the glow's outer edge, next to empty pixels, measure (`edge_check.py`, below):

| Runs | Edge pixels | Highest alpha | Mean alpha | At 32 or more |
|---|---|---|---|---|
| first runs, `*-hard` | 48 | 59 | 29.0 | 16 |
| first runs, `*-soft` | 49 | 44 | 22.0 | 14 |
| v5 runs, `*-hard` | 47 | 7 | 3.5 | 0 |
| v5 runs, `*-soft` | 47 | 7 | 3.4 | 0 |

## Earlier owner decisions

These are quoted and kept apart from the verdict; none of them is the verdict.

- **The review was requested** on 2026-10-18 in the manager's terminal. The manager asked "Should I start #119, the review?", and the owner answered: "yes, do the review".
- **The review commands were signed off before rendering**, on 2026-10-19 at 01:58 UTC, typed directly in the review agent's pane, so there is no relay message. The agent presented the saved proposal `proposal.md` (SHA-256 `89e55a2b61c564023f6c50bb2c215dd4ed3a633e76ce2d2a0c50b62821414222`): the inputs and their hashes, the library's content, and the four commands under [Commands](#commands). The owner answered:
  > "yea, those are fine"
- **Rerunning on the rebuilt model** was authorised by the owner's confirmation above: "yes, you dont need my permission to rebuild a blender model, you thats just local compute, then rerun the renders." Only the model and its SHA-256 changed.

## Input

- **Model:** `chest.glb`, a treasure chest the owner designed and an agent generated with a script in headless Blender, on 2026-10-18 (request moskophoros-20261018-1). The owner chose a simple object: a wooden box with a curved lid, bronze trim and a dark iron lock, whose lid cracks open with warm gold light spilling out. The owner removed a cutout (`MASK`) cobweb and a translucent cloth that the agent had proposed for the review ("no silk no cobweb … they look bad, just the chest"), and accepted the model with "that's perfect, model is ready."
  - **v5, the model the verdict is bound to:** `~/.local/share/moskophoros-acceptance/alpha-model/v5/chest.glb`, SHA-256 `04932ad4c77d1348d6d123fa4fda8924edbfa338e7c25a8de814b7200ed3a72c`, 58,300 bytes. Built by `make_chest.py` (SHA-256 `942f791ef6b70d6145fca252ec18ab0c5d2ea48139ae9422c6bdca5dcfd749d7`) with Blender 5.2.2, headless, under the shared Blender lock. It differs from the first model only in the glow texture's sampler, which records `wrapS` and `wrapT` 33071 (`CLAMP_TO_EDGE`).
  - **The first model:** `~/.local/share/moskophoros-acceptance/alpha-model/chest.glb`, SHA-256 `4e4175a449071ccd8fb26bca944ec5cba458d934f5092c050d9ba69cefb9e335`, 58,272 bytes, built by `make_chest_v4.py` (SHA-256 `f4cb07998607fbc495705bcc3d7d5552ddda0ca0fcabf7963f0bc54f5df8a82e`). The owner's answers were given on the review of this model.
  - **Contents, read from the `.glb`'s JSON:** materials `Wood`, `Bronze` and `Iron`, `OPAQUE` (no `alphaMode`), and `Glow`, `BLEND`, whose texture's alpha falls from 0.9 at the crack to 0 at the tip and to 0 at the sides. Glow is three sheets fanning out of the crack and a static pool inside the chest. One animation, `Open`, 1.5 s, linear: the lid rotates 20° and the glow sheets grow.
  - Neither model is committed.
- **The owner's look**, read from the owner's own files and never changed:
  - user settings `~/.config/moskophoros/config.yaml`, SHA-256 `4f6d474af5526cd298a7628c69d6a51a7268a614d0e55a0737360a7e995828b1`: the palette and the shading;
  - palette `vince-144.gpl`, SHA-256 `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c`.
- **Library:** `review-library.yaml`, proposed with the commands and signed off with them. It is a review input, never a default or a fixture (V-1). SHA-256 `251d2f81537873d4ad88ef8dcf30638c611562719465aa2edf576fb7cbf63d24`, verbatim:

  ```yaml
  # Review library for the alpha test chest, #119 (ALPHA-7). A review input
  # only, never a default or a fixture (V-1). Ramps run darkest first, as
  # indices into the owner's palette, vince-144.gpl.
  schema: moskophoros.materials/3
  ramps:
    wood: {base: "#573924", bands: 4}
    bronze: {base: "#b99346", bands: 4}
    iron: {base: "#333333", bands: 3}
    glow: [4, 5, 119]   # #b65f33 orange, #b99346 gold, #f4d3a5 pale gold
  default: wood
  materials:
    Wood: {uses: wood}
    Bronze: {uses: bronze}
    Iron: {uses: iron}
    Glow: {uses: glow}
  ```

  Resolved on vince-144, as each library sheet's JSON records, darkest first: `wood` [128, 128, 17, 18] (`#0d0d0d #0d0d0d #3b2422 #573924`), `bronze` [17, 19, 12, 5] (`#3b2422 #6a5822 #8c6d5d #b99346`), `iron` [128, 129, 131] (`#0d0d0d #191919 #333333`), `glow` [4, 5, 119] (`#b65f33 #b99346 #f4d3a5`).
- **Clip:** `Open`, played once. View `iso`, 8 directions.

## Commands

All runs were made from `~/.local/share/moskophoros-acceptance/alpha-review/`, one at a time, each under the shared Blender lock, by `run.sh` (first runs, SHA-256 `f22cb0c7f64c8dd5424f764b94cb61ded36b791024a3f971ad294672129de16c`) and `run-v5.sh` (reruns, SHA-256 `89af019693486db77218f50e15ab5da8a5802fef3af56e000b85cf5e2d728f52`). The owner's user settings were in effect. Each run's literal command is kept beside its outputs as `command.txt`, and its output as `run.log`. The v5 commands, literally:

    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-18e764a/.venv/bin/moskophoros --clip Open --once Open --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges hard ../alpha-model/v5/chest.glb v5-plain-hard/chest.png
    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-18e764a/.venv/bin/moskophoros --clip Open --once Open --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges soft ../alpha-model/v5/chest.glb v5-plain-soft/chest.png
    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-18e764a/.venv/bin/moskophoros --clip Open --once Open --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges hard --materials review-library.yaml ../alpha-model/v5/chest.glb v5-library-hard/chest.png
    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-18e764a/.venv/bin/moskophoros --clip Open --once Open --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges soft --materials review-library.yaml ../alpha-model/v5/chest.glb v5-library-soft/chest.png

The first runs are the same four commands with `../alpha-model/chest.glb` and the output directories `plain-hard`, `plain-soft`, `library-hard` and `library-soft`. The light, `-53.333,106.667,80`, is the lighting review's upper-left front light L1 (`-20,40,30` at 48×48) scaled to 128×128.

## Environment

- **moskophoros:** 0.1.0, master `18e764a6fe9fc92281c9638bc231399324ba3d2b`, the head of master at both signoff and rendering. It ran from a clean copy made with `git archive` into `alpha-review/tool-18e764a/`, with a virtual environment from `requirements.lock`.
- **Libraries:** Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0.
- **Blender:** 5.2.2 LTS, headless.
- **Colour:** `cycles-flat-emission`, 1 sample per pixel, seed 0, BOX filter of width 0.01 px, minimum and maximum transparent bounces 64, pass alpha threshold 9.313225746154785e-10.
- **Shade:** `cycles-ambient-occlusion`, 1 sample per pixel, seed 0, BOX filter of width 0.01 px.

## Resolved settings

The settings are the same in every run except `edges` and the library:

| Setting | Value |
|---|---|
| View | orthographic, pitch 30°, 8 directions, start angle 0° |
| Sampling | 12 fps, frames `auto`; `Open` one-shot, 19 frames of 1/12 s, `time_scale` 1 |
| Cell | 128×128, `pixels_per_meter` 104.03085341729185, ground pixel (64, 102); sheet 2432×1024 |
| Capture | supersample 8, model yaw 0°, root motion `error` |
| Maps | `normals: true`, `depth: true`; previews on |
| Light | position `[-53.333, 106.667, 80.0]`, intensity 1.0, ambient 0.3 |
| Shade | `ao_distance_m` 1.2, `ao_samples` 64, `occlusion_weight` 0.5, `convexity_weight` 0.25, `range` [190, 225] |
| Generated ramps | `lightness_step` 0.12, `hue_shift_deg` −12, `chroma_fade` 0.3 |
| Style | `reduce: plain`; palette `vince-144.gpl`; `edges` `hard` or `soft`; library `review-library.yaml` or none |

Every sheet's schema is `moskophoros.sheet/13`.

## Checks before review

These were checked by reading the files with `check.py` (SHA-256 `4a86103fe2fd8d51c1af78aa1dbfd3cc4daeb691ebb356f19af613b886c1dc8e`), for the first runs before the owner was shown anything, and again for the v5 runs. Every check passed for all eight runs; the output is kept as `checks-chest-4e4175.txt` and `checks.txt`.

- **The sheets' JSON** records `settings.style.edges` as signed off, `hard` or `soft`. It records the library `review-library.yaml` with its SHA-256 in the library runs, and no library in the plain runs. It records the model's SHA-256, `depth: true`, and the normal and depth maps under `maps`.
- **Normal maps:** each is the sheet's size, RGBA, and its alpha equals the colour sheet's in every pixel.
- **Depth maps:** each is the sheet's size, 16-bit greyscale, and non-zero exactly where the colour's alpha is above 0. The v5 runs cover 1,175,507 pixels with `hard` and 1,195,886 with `soft`. Depths run from −12.875 to +84.0 sheet pixels, far inside the encodable range.
- **Partial alpha:** every sheet uses all 256 alpha levels. The v5 runs have 54,280 partly transparent pixels with `hard` and 107,388 with `soft`.
- **Previews:** each run wrote `chest.Open.gif` and `chest-lit.Open.gif`, as the design names them.
- **Warnings.** Every run, first and v5, warned that its lit preview had frames with more than 256 colours, reduced to 256 without dithering. The two `library-soft` runs also warned this for their flat preview. These are the documented behaviour. No other warning was printed.

## Review images

All review images are the runs' own pixels, enlarged by whole pixels only (nearest neighbour). Each is labelled with what it shows, and the pages list each run's exact command. The helpers stay outside the repository, in `alpha-review/`.

- **`make_review.py`** (SHA-256 `4fb600aa28a99529e33977ef4a312fc70446693e1479b2ee3746598c35021539`) writes `review/` and a simple page, `review/index.html`. It shows:
  - **the maps, per run:** for the fully open frame and the half-open frame, in all eight directions at 2×: the colour sheet over a checkerboard, the alpha channel alone, the normal map, and the depth map stretched to grey over the run's covered range, nearer brighter. An alignment overlay blends colour and normal 50/50, marking in red any pixel where the normal map's alpha differs from the colour's, and in magenta any pixel where the depth's coverage differs. No pixel was marked.
  - **`hard` against `soft`:** side by side at native size and at 4×, with the pixels whose alpha differs marked in yellow, without and with the library.
  - **glow close-ups:** the fully open lid facing south, south-east, south-west and north, all four runs side by side at 5×. They show where the glow lies over the ramped lid, hasp, rim and inside (D-12), and the shade of the surfaces around and behind it (D-7).
  - **the previews:** flat and lit, at true size and 2×.
- **`viewer/make_viewer.py`**, a tabbed viewer the manager built after the owner found the simple page hard to read (SHA-256 `c9c8b9840f48cc968148793c16a3d3ecffa2b691413e2d2adfdb356be79564b2`; its page `viewer/index.html`, SHA-256 `885918d32bee1514f3b9e3553f3789a0121fc4bd85590cee99707ed6e4a8755f`). Its tabs are:
  - explore one run, by layer (colour, alpha, normal map or depth map), direction and frame, with play;
  - compare all four runs;
  - the animated previews;
  - the glow close-ups;
  - `hard` against `soft`;
  - the map sheets;
  - the commands and checks.

  It copies every image it shows into `viewer/`, so the browser can load them. It writes two made-visible maps per run: the alpha channel as grey, black empty and white opaque, and the depth map's non-zero values stretched to grey 40 to 255 over the range shared by all four runs, nearer brighter, with empty pixels transparent. An early version drew the depth with nearer darker, against its own label; it was corrected before the verdict.
- **`edge_check.py`** (SHA-256 `9f857842cc4fc71cd6dd974ead3b1fa9b64f8f038527000d6bc7c69c53f7b074`) measures the glow's outer edge in north-west, frame 17 (the cell's rows 0–27 and columns 0–57, outside the chest's outline), giving the table under [The firm line](#the-firm-line). `diag/nw-f17-before-after.png` shows that cell for both library runs, first and v5, over dark grey at 5×.

The owner gave the answers on the pages built from the first runs, which are kept as `review-chest-4e4175/` and `viewer-chest-4e4175/`. `review/` and `viewer/` now show the v5 runs.

## Output

All outputs are under `~/.local/share/moskophoros-acceptance/alpha-review/`, and none is committed.

### The v5 runs, which the verdict is bound to

| Run | Fingerprint | Finished (UTC) |
|---|---|---|
| `v5-plain-hard` | `sha256:180fd0b7ae01d8c74dbc9d20a2c82307c80938c81b177b01b230c85f6581535c` | 2026-10-19 03:28 |
| `v5-plain-soft` | `sha256:ced77e3ea4014420e782ec82ae31fd04527abcd1c1417e1af37173a5946e6e63` | 2026-10-19 03:35 |
| `v5-library-hard` | `sha256:7fb6cf137d5b29e2168d23aae8d6bd2cc0769049ede4ec95102f1b86b86eeeef` | 2026-10-19 03:43 |
| `v5-library-soft` | `sha256:b03648590bf1347ce82477bfe575a4e99ba7e58ea60274315163029fc3c8d260` | 2026-10-19 03:51 |

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `v5-plain-hard` | `chest-lit.Open.gif` | 3,329,487 | `fac81c4c097f23b1e254422d23757de22feb480a3f142127884d2a690548a7ad` |
| `v5-plain-hard` | `chest.Open.gif` | 1,278,737 | `d50e5ffce29dda92ec0ca16150a753c99f382f5f4eae31cd9a62fc1c0885936b` |
| `v5-plain-hard` | `chest.depth.png` | 271,410 | `d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26` |
| `v5-plain-hard` | `chest.json` | 32,454 | `7f50090b62727c4dbeef7eaae35fc1a91dc40284c9caacdf9722700506bf5360` |
| `v5-plain-hard` | `chest.normal.png` | 363,340 | `bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36` |
| `v5-plain-hard` | `chest.png` | 140,562 | `8a376e5c5392ca15ab92915f99bc3b550a3f66bf47fa2e64ca19f9bbb3edcccd` |
| `v5-plain-soft` | `chest-lit.Open.gif` | 3,516,209 | `df0361bf092bc00adb4ab9aee864382e05459db0416d67eabb977c77ce1285cf` |
| `v5-plain-soft` | `chest.Open.gif` | 1,533,509 | `fc01722852ae38cb79a0f749aadf51551696057153daac015dad014a7762e24b` |
| `v5-plain-soft` | `chest.depth.png` | 277,688 | `a23f226fa0b90e68f66bcdc11544bac17024f7e2e6a21d634c34e685ce6e8723` |
| `v5-plain-soft` | `chest.json` | 32,454 | `76bcfd00435bbc3b135a2ab0010567a0ab6597b4d7c29c6d8aeda7cc3a795ae3` |
| `v5-plain-soft` | `chest.normal.png` | 389,881 | `ff46a76f8f391f5e23cace7138d3f38a4dae2e387d9fb602d6bf9863bb68caa7` |
| `v5-plain-soft` | `chest.png` | 169,738 | `904a4a082ba5683a13ea1f7a513766d90d009f1b51936e4353ec4e106f87a5e4` |
| `v5-library-hard` | `chest-lit.Open.gif` | 3,402,346 | `796969f0921474ee8991bfc78fbe3d33a9d98631090f4db2fc8ca913a6c020fe` |
| `v5-library-hard` | `chest.Open.gif` | 1,614,574 | `2ea8a4843c8fc29793519c76c0bfa78ca90df731b5a9ceb1dd32388618c5304e` |
| `v5-library-hard` | `chest.depth.png` | 271,410 | `d83a33174dd5061589f74c48f4387c5b0af587057498f239bba2e87d3431dc26` |
| `v5-library-hard` | `chest.json` | 33,579 | `b0ab9c87b7a987080d392c95a8983abb2087e92bde0501cadc2e8cf19ab01ceb` |
| `v5-library-hard` | `chest.normal.png` | 363,340 | `bf150f476babb3fbbddaf3649c6596abc83bb5700526d935adee7dacff4a2f36` |
| `v5-library-hard` | `chest.png` | 157,082 | `524f8b8af07771ab7b09559cedec00a8e93b6bff5b032a4c70676949bb3aca2f` |
| `v5-library-soft` | `chest-lit.Open.gif` | 3,566,099 | `62a3e5bbbb52feef3c4b398841252e81427b203a760885a601d890f52129c274` |
| `v5-library-soft` | `chest.Open.gif` | 1,910,855 | `8a4d6da00a03a708c35c2906f7593dedacde8be16f20a78e9e374f76c3e3d6aa` |
| `v5-library-soft` | `chest.depth.png` | 277,688 | `a23f226fa0b90e68f66bcdc11544bac17024f7e2e6a21d634c34e685ce6e8723` |
| `v5-library-soft` | `chest.json` | 33,579 | `9ef816cf15dbc177aa852f70d81d1eb15483cbfb603728334156b4957808a0f7` |
| `v5-library-soft` | `chest.normal.png` | 389,881 | `ff46a76f8f391f5e23cace7138d3f38a4dae2e387d9fb602d6bf9863bb68caa7` |
| `v5-library-soft` | `chest.png` | 189,693 | `a9aa4dcfe41e27b741990214eca45df5354734b8967f4e52fdc5d626fa9292ae` |

### The first runs, on the first model

The owner gave the answers on these. They are kept unchanged.

| Run | Fingerprint | Finished (UTC) |
|---|---|---|
| `plain-hard` | `sha256:dd0ee883efb68ecf78d83efcbf247b75ac4beddaa17522efcd7db659e9d4fa61` | 2026-10-19 02:06 |
| `plain-soft` | `sha256:5dba43141ac94b21b2e60d49bdf5301eb1e46c6072e4c4f1a8d945a30be3011f` | 2026-10-19 02:13 |
| `library-hard` | `sha256:e4853e5e0d08443a6683544e762c286d49e9e60661d51f8838ebb595ddb8071f` | 2026-10-19 02:20 |
| `library-soft` | `sha256:9512b09acf893f5bc956a01f4c1049aecfdcfb6dc22902ddc64d801456ed1e9a` | 2026-10-19 02:27 |

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `plain-hard` | `chest-lit.Open.gif` | 3,337,171 | `fbde32a547559a3d10123cdc40121f7b557a78709dd7d465b9f901eaf67e93c1` |
| `plain-hard` | `chest.Open.gif` | 1,293,742 | `32d38c23d8abe7fc87d1ddb4c61819caced3ed4bfe3e8aa393e579c951e0a11c` |
| `plain-hard` | `chest.depth.png` | 271,631 | `fbe5b170980bde635c4585cc2ec09cacaadc341d261568c34ac98a9e4b50f3ef` |
| `plain-hard` | `chest.json` | 32,454 | `79c9bc3ed2980f8f7570e1365b6d00f86f137cc98b83f29b9342b14caf9d30ad` |
| `plain-hard` | `chest.normal.png` | 365,010 | `196638cef39db8f76d4bb420599517b90e28ad626434ac77b2db114c55f9733a` |
| `plain-hard` | `chest.png` | 142,567 | `178e346ab0660d79186bd5deae471668f90fef93f9bda80b5cc23e289797c685` |
| `plain-soft` | `chest-lit.Open.gif` | 3,530,297 | `7d3266b32d4c0310226bf962e8b584ecfa5e396a8d76dfd2024fae90f5947508` |
| `plain-soft` | `chest.Open.gif` | 1,547,020 | `d67459d95c5bb670be76c62cdb3399d128c380e83d123824d94af11a493f42f0` |
| `plain-soft` | `chest.depth.png` | 278,463 | `b106cfe0fe36cb902032dd7a8274aed3867bfbe5c2b58314a8a75d5f06e996ef` |
| `plain-soft` | `chest.json` | 32,454 | `ca5c9331bf4e63dd5545044d545a8dc205ea43204f7a370436e388157286b68d` |
| `plain-soft` | `chest.normal.png` | 391,904 | `bedb404c347c4b6e9d5560d01295768d041ab708c04f3832d1258e20e7cbf3e8` |
| `plain-soft` | `chest.png` | 171,346 | `775777f21424c7e428f6647d9fd45385643a02a064ac851b4e0da90c9f80c3a9` |
| `library-hard` | `chest-lit.Open.gif` | 3,401,752 | `9eab09f5621671ba9dcced4154528ad66f6753f439c215263b51bdbc6737b68c` |
| `library-hard` | `chest.Open.gif` | 1,626,622 | `c0f1d1faefb8830c521d1fb777bc0e85521ef7009ecc3978e32745fd90d712b7` |
| `library-hard` | `chest.depth.png` | 271,631 | `fbe5b170980bde635c4585cc2ec09cacaadc341d261568c34ac98a9e4b50f3ef` |
| `library-hard` | `chest.json` | 33,579 | `b516ba35c7ccc2ac635ddd5d7a07e7bc98483a3f1699ad8119c19a4cc8552795` |
| `library-hard` | `chest.normal.png` | 365,010 | `196638cef39db8f76d4bb420599517b90e28ad626434ac77b2db114c55f9733a` |
| `library-hard` | `chest.png` | 159,094 | `dc830dfa831fbaa53213afc65c20768c7500831a0ed27e8ad7f0946d9bb9d837` |
| `library-soft` | `chest-lit.Open.gif` | 3,589,821 | `49275c67c1b742e8d2910099dbad4c45fcb50a4e6f8a2e36476fca0f27f36024` |
| `library-soft` | `chest.Open.gif` | 1,923,154 | `bfecfb5d5643c45c6430ccb5eb578d13fe0f0a68dd713d5ab4db205c0371ea3c` |
| `library-soft` | `chest.depth.png` | 278,463 | `b106cfe0fe36cb902032dd7a8274aed3867bfbe5c2b58314a8a75d5f06e996ef` |
| `library-soft` | `chest.json` | 33,579 | `11c5b3a889ba03d1c8f24e1be46b8ba6344df8f2fc96c0d01a261c38d844016c` |
| `library-soft` | `chest.normal.png` | 391,904 | `bedb404c347c4b6e9d5560d01295768d041ab708c04f3832d1258e20e7cbf3e8` |
| `library-soft` | `chest.png` | 191,815 | `71591c8bf5690e9e54fba61640d1205997759f15583e0908dc5bc75b4ef7b7c3` |

## Follow-up notes

- **The wood's look.** The owner would like the wood to have more shading, and perhaps more texture, "but we can do that later". The plank lines show only with a library. Nothing is filed for it.
- **Cutouts were not reviewed on the chest,** which has no `MASK` material. They were reviewed on the shrub, and accepted: see [Cutouts](#cutouts).
- **No code change** came from this review, and no issue was filed. The one defect found was in the model.

## Cutouts

This addendum records the owner's review of `MASK` cutouts (D-1, D-2, ALPHA-2) on a model made for it, which the chest above could not give. It follows the chest review's shape and settings. The moskophoros manager proposed it and the owner approved it (request moskophoros-20261019-4). No issue was filed for it.

### Cutout verdict

**Accepted by the owner, on 2026-10-19 at 14:39 UTC, typed directly in the review agent's pane after viewing the four runs:**

> "they do look good, but the green mostly went dark, the range of green is very low and ramps up very quickly, the leaves look like a dark ball with little green highlights scattered around. but the cutout behavior is correct, and looks good, especially library-hard lit, it looks so much better than i would have thought."

The agent asked whether to record the verdict as "the cutout behavior is correct, and looks good, especially library-hard lit", with the leaf colour kept apart. The owner confirmed, on 2026-10-19 at 15:55 UTC:

> "yes exactly, i signed off already on your cutoffs, i am simply using your context to fix another, unrelated problem"

- **Cutouts: accepted.** The questions put to the owner were: whether holes show only the background, with no colour or fringe from the cards (D-1); whether the trunk, the back leaves and the pot show through holes where they should (D-1); the cut edges with `hard` and with `soft`; and the leaves while they sway.
- **Not part of the verdict:** with the review library, most leaves took the darkest green. The owner calls this a separate problem, in the library's leaf ramp, and it is being tuned outside this record (see [Leaf colour](#leaf-colour)).

The verdict is the owner's alone (V-12). It is bound to the four runs under [Cutout output](#cutout-output).

### Cutout signoff

The proposal `proposal.md` (SHA-256 `9fab0434513302f1ee0a71a7a4d2f324dcccfe482685c4a93e91f61a2162e9a2`) gave the four commands, the library and every input's hash. The manager relayed the owner's signoff by cmux message `503ab252-6eae-46ad-9059-1d5d1919d3ed`: "The owner signs off your proposal (proposal.md SHA-256 9fab0434…) through me. Render the four runs now." It quotes the owner, typed directly in the manager's terminal at 14:04 UTC: "when i give you, the manager, permission, that needs to propegated down to the workers, you are their boss. so tell the worker to do the renders". Earlier, answering the manager's proposal of this review, the owner had written: "ok yea, bring me the renders". The relay is kept as `signoff.txt` (SHA-256 `7fabbc7ee13df5a424c3ea5211c8b13d31b317fc58ebf0b5b36059efccdf6a81`).

### Cutout input

- **Model:** `~/.local/share/moskophoros-acceptance/cutout-model/v1/shrub.glb`, SHA-256 `7a1a29382888c8c21a0b19c9418fdbcc5417e8ac038c9d626770ca6f4f0b684f`, 143,624 bytes. It is a potted shrub the owner chose ("a potted shrub sounds nice, i very much want something different than a chest this time"), generated by `make_shrub_v1.py` (SHA-256 `8982eb3df892e40ca5fefc0753b9a4e4adc8021ea4459483336e1caa7aa4928a`) with Blender 5.2.2, headless, under the shared Blender lock (request moskophoros-20261019-2). The owner accepted it on 2026-10-19 at 13:53 UTC: "keep it as it is, it looks good". It is not committed.
  - **Contents, read from the `.glb`'s JSON:**
    - **`Leaves`:** `MASK`, `alphaCutoff` 0.4 and double-sided. Its base colour texture is a leaf sprig whose alpha is 0 between the leaves, drawn at 4× and box-filtered, so the alpha has soft edges for the cutoff to cut. The sampler is `LINEAR` with both wraps 33071 (`CLAMP_TO_EDGE`).
    - **`Terracotta`, `Soil` and `Bark`:** `OPAQUE` (no `alphaMode`).
    - **Geometry:** a pot with soil; a trunk and branches; and 52 leaf cards of 0.32 m around a sphere about 0.34 m in radius.
    - **Animation:** one, `Sway`, a 2.0 s loop of rotations only. The canopy sways about 2° about the trunk's base, and each card rustles about 5° about its centre, each motion a whole number of cycles per loop. Nothing translates.
- **The owner's look:** user settings `~/.config/moskophoros/config.yaml`, SHA-256 `4f6d474af5526cd298a7628c69d6a51a7268a614d0e55a0737360a7e995828b1`, and palette `vince-144.gpl`, SHA-256 `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c`, both read and never changed.
- **Library:** `review-library.yaml`, signed off with the commands. It is a review input, never a default or a fixture (V-1). SHA-256 `3a3173b5cd35e7e3a6bb7e247ee83c45f87e1a74da9c1ea5370b0b877dc13da5`, verbatim:

  ```yaml
  # Review library for the cutout test shrub, the cutout review of the alpha
  # arc. A review input only, never a default or a fixture (V-1). Ramps run
  # darkest first, as indices into the owner's palette, vince-144.gpl.
  schema: moskophoros.materials/3
  ramps:
    leaves: [34, 35, 36, 37]     # #3d431c #41631f #358824 #43ad55, greens
    terracotta: [17, 3, 4]       # #3b2422 #9e3535 #b65f33
    soil: [16, 17, 18]           # #1c1517 #3b2422 #573924
    bark: [17, 18, 12]           # #3b2422 #573924 #8c6d5d
  default: leaves
  materials:
    Leaves: {uses: leaves}
    Terracotta: {uses: terracotta}
    Soil: {uses: soil}
    Bark: {uses: bark}
  ```

- **Clip:** `Sway`, a loop. View `iso`, 8 directions.

### Cutout commands

All runs were made from `~/.local/share/moskophoros-acceptance/cutout-review/`, one at a time, each under the shared Blender lock, by `run.sh` (SHA-256 `e7f08fb2e1762d7ee5a878ac712580db7959b8434f3a989400c5af33c521f491`), with the owner's user settings in effect. Each run's literal command is kept beside its outputs as `command.txt`, and its output as `run.log`. Literally:

    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-965f12e/.venv/bin/moskophoros --clip Sway --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges hard ../cutout-model/v1/shrub.glb plain-hard/shrub.png
    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-965f12e/.venv/bin/moskophoros --clip Sway --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges soft ../cutout-model/v1/shrub.glb plain-soft/shrub.png
    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-965f12e/.venv/bin/moskophoros --clip Sway --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges hard --materials review-library.yaml ../cutout-model/v1/shrub.glb library-hard/shrub.png
    /usr/bin/lockf -k /Users/vincentcoghlan/.local/state/project-manager/moskophoros/blender.lock tool-965f12e/.venv/bin/moskophoros --clip Sway --view iso --directions 8 --cell 128x128 --depth --light -53.333,106.667,80 --edges soft --materials review-library.yaml ../cutout-model/v1/shrub.glb library-soft/shrub.png

### Cutout environment and settings

- **moskophoros:** 0.1.0, master `965f12e`, the head of master at signoff and rendering. Its code is the same as `5c59809`'s. It ran from a clean copy made with `git archive` into `cutout-review/tool-965f12e/`, with a virtual environment from `requirements.lock`.
- **Libraries:** Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0. **Blender:** 5.2.2 LTS, headless.
- **Capture:** as for the chest (see [Environment](#environment)).
- **Settings:** as in the chest's [Resolved settings](#resolved-settings), except:
  - **Sampling:** `Sway` loops in 24 frames of 1/12 s.
  - **Cell:** `pixels_per_meter` 104.63348333762265 and ground pixel (64, 119), giving a sheet of 3072×1024.
  - **Library:** `review-library.yaml`, or none.
  - **Sheet schema:** `moskophoros.sheet/13`.

### Cutout checks before review

These were checked by reading the files with `check.py` (SHA-256 `87a5f8a30d8c6ad955aa34f2127609664c91cbf6b4db94f5b33597be105a932b`), the chest's checks adapted to the shrub, before the owner was shown anything. Every check passed for all four runs. The output is kept as `checks.txt` (SHA-256 `a739686f4fe2486092c42b2e7a2810b95e9783d6a8c614f8c21df1520e46b391`).

- **The chest's checks:**
  - the sheets' JSON records the signed-off `edges`, the library and its SHA-256 or no library, the model's SHA-256, `depth: true`, and both maps;
  - each normal map's alpha equals the colour sheet's;
  - each depth map is non-zero exactly where the colour's alpha is above 0;
  - the previews are named `shrub.Sway.gif` and `shrub-lit.Sway.gif`.
- **Holes over the background:** an empty pixel not reached from its cell's border through empty pixels is background seen through a hole in the leaves.
  - Every sheet has such holes, in all 192 cells: 112,752 pixels with `hard` and 104,678 with `soft`.
  - Every empty pixel, holes included, has RGB 0 in the colour sheet and is 0 in the normal and depth maps.
- **Alpha:** with `hard`, every sheet uses only alpha 0 and 255. With `soft`, 466,889 pixels are partly transparent, in 65 levels.
- **Soft edge colour:** `edge_colour.py` (SHA-256 `2207542133f9baf918cc8d2d1df679508fb45167916d31b21478e895c22692e6`; output `edge-colour.txt`, SHA-256 `23902a24fbd78b8a0e2c4108f575355860c719d33388fa79bb72cc15fbc66743`) compared the 268,102 pixels that are partly transparent with `soft` and opaque with `hard`, for both pairs.
  - Every one has exactly the hard run's RGB, so no background is mixed into a soft edge's colour.
  - The measure says nothing about soft pixels below alpha 128, which the hard run leaves empty.
- **Determinism:** the two plain runs' colour sheets are byte-identical to check renders of the same model made at `5c59809` before the review.
- **Warnings:**
  - Every run warned that its lit preview had frames with more than 256 colours, reduced to 256 without dithering.
  - The two `soft` runs also warned this for their flat preview.
  - These are the documented behaviour. No other warning was printed.

### Cutout review images

The viewer is `viewer/make_viewer.py` (SHA-256 `a9224c4e4bf8d03df9fd09fc42575722a2b9d7c39afaecf12fec5e034639f0a9`), the chest's tabbed viewer adapted. Its page is `viewer/index.html` (SHA-256 `4e035c3d272635e85b9fb3fec84adc899829624e9028be3b021f3a7009e90929`). It shows the runs' own pixels, enlarged by whole pixels only, and copies every image into `viewer/`. Its tabs are:

- **explore one run**, by layer (colour, alpha, normal map or depth map), direction and frame, with play;
- **compare all four runs**;
- **holes (D-1):** all eight directions of one frame over a background of the viewer's choice, magenta and blue included;
- **`hard` against `soft`**, with the pixels whose alpha differs marked in yellow;
- **the animated previews;**
- **the commands and checks.**

"Mark holes", in the explore, compare and holes tabs, paints magenta every pixel the hole check counts.

### Cutout output

All outputs are under `~/.local/share/moskophoros-acceptance/cutout-review/`, and none is committed.

| Run | Fingerprint | Finished (UTC) |
|---|---|---|
| `plain-hard` | `sha256:4f5381fa395a802a2a2abb7cfde2d3b3b619dbe1de5f880f7d94512ce4e15b54` | 2026-10-19 14:12 |
| `plain-soft` | `sha256:59e5c4d1e11521698cd28cc394dc0bddbedba8ec8c16e8940cfe4b0cab3b8cbc` | 2026-10-19 14:19 |
| `library-hard` | `sha256:5747914cfcf4a26d468b419c918166a1799d16ddfa9a08aa8a99a65cfea160c1` | 2026-10-19 14:27 |
| `library-soft` | `sha256:c5f9df7f7ad09f7e0748c3878468038a44dfe47f67eb1e0cd9cfe4fee0f4483b` | 2026-10-19 14:34 |

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `plain-hard` | `shrub-lit.Sway.gif` | 4,427,776 | `3fb55aab464727c492c6bb1393bf68cc7370c73bb1731752f11df75d174641e0` |
| `plain-hard` | `shrub.Sway.gif` | 2,177,051 | `4e7fdf513c5166b5548c9bdf471cc96031746c4c1c9ea28134635db063bf0e98` |
| `plain-hard` | `shrub.depth.png` | 1,161,691 | `665e8abf834ddf9a6e16bbf9806e1dbb6c701fe3bf180016383a5c6b396b59eb` |
| `plain-hard` | `shrub.json` | 39,689 | `cc11a00d7290e0708cab3e9c725815ae90ffb2fc75fe3d860683b195349f5474` |
| `plain-hard` | `shrub.normal.png` | 1,819,151 | `4e74a38832e00470e8c8a1016d4130ac79dd97dc059ecb0bb32eb79352cd77cb` |
| `plain-hard` | `shrub.png` | 646,296 | `3ef5826f009d40f4b78d72110574b92cab0d9fd7d8fb42d3492fa2d48cda9d49` |
| `plain-soft` | `shrub-lit.Sway.gif` | 5,903,158 | `250e3f81e8eff176dc9a7f8967509ceddcb8158e877e76b57654b0f38aaf4ab7` |
| `plain-soft` | `shrub.Sway.gif` | 5,086,312 | `2329ae155ed2b200c90489bf896f2f7795030612ff127cac1c98f08cd095510e` |
| `plain-soft` | `shrub.depth.png` | 1,288,830 | `fe0afcbe9e6274c3d39944d51c2edabe549b56f6088e88c21058050cd12e86b9` |
| `plain-soft` | `shrub.json` | 39,689 | `9bf2c6b9403bb2bae0076243599447d0dd0c7c2b55e4517008cd1c9b12244cd5` |
| `plain-soft` | `shrub.normal.png` | 2,606,796 | `a78152403dd0284f11b642c8a66aef959ffd19f3a84e013095e2a9436bd21ca3` |
| `plain-soft` | `shrub.png` | 1,655,253 | `46e24fd892b4f0c802fe33b55de71f665d3defe125bf44e048c68eac2a1f3579` |
| `library-hard` | `shrub-lit.Sway.gif` | 3,951,075 | `0750b92a3398092e1a27bec142dea3f448e97df14c9df33d9e18f0671f13efec` |
| `library-hard` | `shrub.Sway.gif` | 1,512,921 | `587b3005658306f10bf6d99948ba9914571ed7dd036fcf5eef48be53f0fd0253` |
| `library-hard` | `shrub.depth.png` | 1,161,691 | `665e8abf834ddf9a6e16bbf9806e1dbb6c701fe3bf180016383a5c6b396b59eb` |
| `library-hard` | `shrub.json` | 40,509 | `db0146f48bc158b767f97c8c6ce27470d1d014854b2555e1ddccf1427b905379` |
| `library-hard` | `shrub.normal.png` | 1,819,151 | `4e74a38832e00470e8c8a1016d4130ac79dd97dc059ecb0bb32eb79352cd77cb` |
| `library-hard` | `shrub.png` | 361,418 | `453555d045c65524ccd022122d438bbda649e93a077f2c8ab97540431dd0de06` |
| `library-soft` | `shrub-lit.Sway.gif` | 5,781,615 | `0df5cdf655ba2027fb15fd2e8a92dd541a489976655f841a6797c1f446763d28` |
| `library-soft` | `shrub.Sway.gif` | 4,569,376 | `59779af22e44c44e8957e1d8359f802456116804db9d3911a3a704232e751314` |
| `library-soft` | `shrub.depth.png` | 1,288,830 | `fe0afcbe9e6274c3d39944d51c2edabe549b56f6088e88c21058050cd12e86b9` |
| `library-soft` | `shrub.json` | 40,509 | `78a2e2926826c786097527d1d2057334db82b29f14f15f7c888ae8aa3b954084` |
| `library-soft` | `shrub.normal.png` | 2,606,796 | `a78152403dd0284f11b642c8a66aef959ffd19f3a84e013095e2a9436bd21ca3` |
| `library-soft` | `shrub.png` | 1,282,538 | `058b19d1db3f852161102c46bb2531f6e4115022ec4a90bde0ef55038e4e876f` |

### Leaf colour

This is not part of the cutout verdict. With the review library, the leaves fell mostly in the darkest green: 86% of leaf pixels in `library-hard` are `#3d431c`.

A capture of one frame in all eight directions, kept with `--work-dir`, measured the reason:
- **Leaves:** 76% of the leaves' shade values fall below the owner's shade range, `[190, 225]`, mostly between 132 and 150. Values below the range take the darkest band.
- **Bark and soil:** they lie entirely below it.
- **Terracotta:** 77% of the pot falls inside it.

Foliage self-occludes far more than the chest's solid surfaces. Each card also occludes as a solid rectangle, holes included, as D-7's approximation does.

The owner asked for this to be fixed in the library's leaf entry, outside this record. It needs no change to moskophoros or to the owner's settings. Trials of the leaves' own ramp and shade values are kept in `cutout-review/trials/`. A shorter occlusion distance for the leaves (0.3 m and 0.15 m) left 83–87% of them in the darkest band. A shade range of the leaves' own spread them across the bands.

**The owner's choice,** on 2026-10-19 at about 16:02 UTC, typed directly in the review agent's pane: "good work, they all look good so its hard to choose, F looks best i would say". Trial F keeps the review library's greens and gives the leaves their own range:

```yaml
Leaves: {uses: leaves, shade: {range: [110, 190]}}
```

- **Library:** `trials/lib-F.yaml`, SHA-256 `f67099def641676eb9a39924f2f89455ba93b03d88b9df6a8996c4eff528b74c`.
- **Run:** the `library-hard` command with that library; fingerprint `sha256:3628f4f67a191d5aefa55d1f15974965a30c291b877ec823b86bc6f7c1ee4c25`.
- **Result:** leaf pixels per band, darkest first, are 8%, 50%, 13% and 28%, where the review run had 86%, 5%, 6% and 4%.

The bark and soil stay below the global range; giving them ranges of their own was offered, and the owner has not asked for it.
