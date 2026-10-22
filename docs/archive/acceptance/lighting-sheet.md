# Lighting sheet acceptance

This records the owner's acceptance of the lighting sheet arc, following #101 (LIT-6) and vision V-12. The arc is epic #95. Its code slices were delivered with:

| Slice | Issue | Pull request |
|---|---|---|
| LIT-1 | #96 | #102 |
| LIT-2 | #97 | #103 |
| LIT-3 | #98 | #104 |
| LIT-4 | #99 | #105 |
| LIT-5 | #100 | #106 |

The design is [`docs/archive/designs/lighting_sheet_design.md`](../designs/lighting_sheet_design.md).

## Verdict

**Accepted by the owner on 2026-10-14 at 00:39 UTC.** The owner typed it directly in the moskophoros manager's terminal, after viewing the review page described under [Review images](#review-images):

> "these look good to me, the behind right reads as flat dark, but that is probably correct. i approve this"

"The behind right" is light L5, a low rim light behind the subject on its right. A light behind the subject reaches few surfaces that face the viewer, so most pixels fall to the ambient level. The owner judged that probably correct. The note asks for no change.

The verdict is the owner's alone (V-12). This record quotes it and does not extend it. It is bound to the outputs listed under [Output](#output), made from master `fcb85d14` (the merge of #106).

## Earlier owner decisions

These are quoted and kept apart from the verdict; none of them is the verdict.

- **The review was requested** on 2026-10-14 at 00:30 UTC, in the manager's terminal: "allright, show me the results for visual review".
- **The review commands were signed off before rendering**, the same minute. The manager presented the plan, and the owner chose "Approve as proposed (Recommended)" from:
  > "Approve these review renders? Each light position is one render at 48×48 and one at 32×32, all with your look and --depth."

  The approved option listed these lights at 48×48, with coordinates scaled by 2/3 at 32×32:
  - upper-left front (-20,40,30);
  - upper-right front (20,40,30);
  - overhead (0,80,10);
  - distant upper-left front (-1000,1000,1000), which acts like sunlight;
  - low rim light from behind-right (30,5,-20).

## Input

- **Model:** `RobotExpressive.glb`, SHA-256 `047f5e5fb3bb6d378bd1df16ca6137f2a596c99b3a1b5690b4020c05aaf6f319`. Its source, licence and attribution are in [slice 1's record](slice-1.md#input). It is not committed.
- **The owner's look**, read from the owner's own files and never changed:
  - user settings `~/.config/moskophoros/config.yaml`, SHA-256 `33bdc557146d9bee65b3f285d1b59949cd910c3b37dbf0b9bf23eb18bc4905d1`. They set the palette and the shading chosen on 2026-10-13 (render N3; see [the settings record](settings.md)).
  - palette `vince-144.gpl` (Vince 128 plus a 16-step grey ramp), SHA-256 `073695cba52f4fc6a38f035246e69f5c1f8343885fcdb9f376c8fef7b0c2938c`;
  - material library `~/.config/moskophoros/libraries/robotexpressive.yaml`, SHA-256 `10f325996faf3989fbcfde2ebfdb71ba9d6b659bc8c4e0e73b6a6b47483e8b51`.
- **Clips:** `Walking` (loops) and `Jump` (plays once). View `iso`, 8 directions.

## Commands

All ten ran from `~/.local/share/moskophoros-acceptance/robotexpressive/`, one at a time, each under the shared Blender lock (`/usr/bin/lockf -k ~/.local/state/project-manager/moskophoros/blender.lock`). The owner's user settings were in effect. Only the cell size and the light changed:

    moskophoros --depth --light X,Y,Z \
      --clip Walking --clip Jump --once Jump --cell 48x48 --view iso --directions 8 \
      --materials ~/.config/moskophoros/libraries/robotexpressive.yaml \
      RobotExpressive.glb lighting-review/c48-<light>/RobotExpressive.png

| Light | At 48×48 | At 32×32 |
|---|---|---|
| L1, upper-left front | `-20,40,30` | `-13.333,26.667,20` |
| L2, upper-right front | `20,40,30` | `13.333,26.667,20` |
| L3, overhead | `0,80,10` | `0,53.333,6.667` |
| L4, distant sun | `-1000,1000,1000` | `-666.667,666.667,666.667` |
| L5, rim behind right | `30,5,-20` | `20,3.333,-13.333` |

The literal command for each run is kept beside its outputs as `command.txt`.

## Environment

- **moskophoros:** 0.1.0, built from master `fcb85d14` in a throwaway worktree.
- **Libraries:** Python 3.14.8, NumPy 2.5.3, Pillow 12.3.0.
- **Blender:** 5.2.2.
- **Colour render:** Workbench with the `Default` studio light.
- **Shade technique:** `cycles-ambient-occlusion`, 1 sample per pixel, seed 0, BOX filter of width 0.01 px.

## Resolved settings

The settings are the same in every run except the cell, its scale and the light:

| Setting | Value |
|---|---|
| Normal map | `normals: true` |
| Depth map | `depth: true` |
| Previews | `previews: true` |
| Light | `intensity` 1.0, `ambient` 0.3; `position` as above |
| Shade | `ao_distance_m` 1.2, `ao_samples` 64, `occlusion_weight` 0.5, `convexity_weight` 0.25, `range` [120, 220] |
| Style | `reduce: plain`, palette `vince-144.gpl`, library `robotexpressive.yaml` (ramps `warm` [18, 4, 5], `stone` [133, 135, 137, 138, 139], `shadow` [129, 131, 132]) |
| View | orthographic, pitch 30°, 8 directions, 12 fps, frames `auto`, supersample 8 |
| 48×48 | sheet 528×768, `pixels_per_meter` 7.0176, ground pixel (24, 41) |
| 32×32 | sheet 352×512, `pixels_per_meter` 4.5224, ground pixel (16, 27) |

Every sheet's schema is `moskophoros.sheet/10`, and its `maps` names both the normal map and the depth map.

**Fingerprints:**

| Run | Fingerprint (prefix) |
|---|---|
| c48-L1 | `41f440eb9` |
| c48-L2 | `26714bbfb` |
| c48-L3 | `f121d30a4` |
| c48-L4 | `68df30632` |
| c48-L5 | `11e3b3c29` |
| c32-L1 | `bec64ddd2` |
| c32-L2 | `8d8eb29f6` |
| c32-L3 | `5f0bb48c7` |
| c32-L4 | `3bb4a2b7e` |
| c32-L5 | `58566bc08` |

The full values are in each sheet's JSON.

## Checks before review

These were checked by reading the files, before the owner was shown anything.

- **Size and transparency.** Each normal map and depth map has exactly its sheet's size. Their coverage matches the sheet's transparency exactly:
  - the normal map's alpha equals the sheet's;
  - the depth map has no alpha channel, so a depth code of 0 marks "no surface", and the nonzero codes cover exactly the sheet's opaque pixels.

  No pixel is misaligned.
- **Fallback pixels.** These are covered pixels whose block had no surface sample, so they face the viewer, `(128, 128, 255)`. There were 2 of 65,072 at 48×48 and 3 of 27,061 at 32×32, the same in every run of a size. They are marked in magenta in the alignment overlays.
- **Depth range.** At 48×48 it runs from −7.19 to +30.75 sheet pixels, and at 32×32 from −3.56 to +19.69. Both are far inside the encodable range.
- **Lit previews.** They are named `RobotExpressive-lit.Walking.gif` and `RobotExpressive-lit.Jump.gif` (D-22), beside the unchanged flat previews.
- **Warnings.** Every run except c48-L5, c32-L3 and c32-L5 warned that its lit previews had frames with more than 256 colours, reduced without dithering. This is the documented behaviour, because lit colours leave the palette.

## Review images

The owner viewed one private review page, built from the outputs above and enlarged by whole pixels only. For each cell size it showed:

- **the maps:** colour sheet, normal map, depth map and alignment overlay, for one Walking pose in all eight directions. The depth codes are stretched to grey over the covered range. The overlay blends colour and normal 50/50, marks fallback pixels in magenta and misaligned pixels in red (none);
- **lit poses:** the same Walking pose under each light beside the flat one, and Jump near its top;
- **close-ups:** south, at 10× (48) and 15× (32);
- **motion:** the flat and lit Walking animations at true size (the 4× preview GIFs shown at a quarter), and enlarged.

Lit stills are the matching frames of the written lit GIFs, shrunk back to true size. The page and its helper stay outside the repository.

## Output

All outputs are under `~/.local/share/moskophoros-acceptance/robotexpressive/lighting-review/`, and none are committed.

| Run | File | Bytes | SHA-256 |
|---|---|---|---|
| `c32-L1-upper-left` | `RobotExpressive-lit.Jump.gif` | 101,236 | `f1bb4360c601343b9f7f5762a8757a5427a881921421dcf4f5f02f29071be168` |
| `c32-L1-upper-left` | `RobotExpressive-lit.Walking.gif` | 123,076 | `954df28439be609c79e4bb182078474f7f24a2a3d9137a266c96b12cb6735162` |
| `c32-L1-upper-left` | `RobotExpressive.Jump.gif` | 36,805 | `ce15320677f99ab00835bb8f5aa80ab6ec029af552496502a48089d7365dd37e` |
| `c32-L1-upper-left` | `RobotExpressive.Walking.gif` | 44,147 | `ac099258176a694fe0114bb7a11afccf8636c0eb5efae9baeb053bd7b54660da` |
| `c32-L1-upper-left` | `RobotExpressive.depth.png` | 44,323 | `a51aeb569d441cd4112356e5a03546d235d38cdb33722ee4cca49368bfbbae73` |
| `c32-L1-upper-left` | `RobotExpressive.json` | 34,557 | `1c7a2f1b10053c0195a0fac95f8a783b6d9ecd7dfe17618c0ad35b416d597b48` |
| `c32-L1-upper-left` | `RobotExpressive.normal.png` | 102,361 | `94891478fa8b141ffc27b9ed24fdeaedd5c7a09ba838e5637752cf81f4e5ab04` |
| `c32-L1-upper-left` | `RobotExpressive.png` | 23,336 | `51d7d6cb3201465ed990058c1782a081a296d4b0f74152a44e10c0f9dacfd5ac` |
| `c32-L2-upper-right` | `RobotExpressive-lit.Jump.gif` | 101,399 | `3eab499b72e9d86c8019e03f6081d298a3330a860a5796d3b3a8a18ec25263fc` |
| `c32-L2-upper-right` | `RobotExpressive-lit.Walking.gif` | 122,530 | `9518dfac9fa8b0baa09b6a09411cc0b31065f7060ad763181a66d92cc16a9b84` |
| `c32-L2-upper-right` | `RobotExpressive.Jump.gif` | 36,805 | `ce15320677f99ab00835bb8f5aa80ab6ec029af552496502a48089d7365dd37e` |
| `c32-L2-upper-right` | `RobotExpressive.Walking.gif` | 44,147 | `ac099258176a694fe0114bb7a11afccf8636c0eb5efae9baeb053bd7b54660da` |
| `c32-L2-upper-right` | `RobotExpressive.depth.png` | 44,323 | `a51aeb569d441cd4112356e5a03546d235d38cdb33722ee4cca49368bfbbae73` |
| `c32-L2-upper-right` | `RobotExpressive.json` | 34,556 | `5f201155bf6ba210194d2573de4676663afdad127191b2ac9119a3df8b8dc1ff` |
| `c32-L2-upper-right` | `RobotExpressive.normal.png` | 102,361 | `94891478fa8b141ffc27b9ed24fdeaedd5c7a09ba838e5637752cf81f4e5ab04` |
| `c32-L2-upper-right` | `RobotExpressive.png` | 23,336 | `51d7d6cb3201465ed990058c1782a081a296d4b0f74152a44e10c0f9dacfd5ac` |
| `c32-L3-overhead` | `RobotExpressive-lit.Jump.gif` | 80,404 | `814dc57c1846a02ed537da3425e57184f208eec367083722b4c353613f6629e9` |
| `c32-L3-overhead` | `RobotExpressive-lit.Walking.gif` | 97,590 | `3973de8934132e5787db08cb6d00e688c6b9eba48244fb920eacbcecf38cfb33` |
| `c32-L3-overhead` | `RobotExpressive.Jump.gif` | 36,805 | `ce15320677f99ab00835bb8f5aa80ab6ec029af552496502a48089d7365dd37e` |
| `c32-L3-overhead` | `RobotExpressive.Walking.gif` | 44,147 | `ac099258176a694fe0114bb7a11afccf8636c0eb5efae9baeb053bd7b54660da` |
| `c32-L3-overhead` | `RobotExpressive.depth.png` | 44,323 | `a51aeb569d441cd4112356e5a03546d235d38cdb33722ee4cca49368bfbbae73` |
| `c32-L3-overhead` | `RobotExpressive.json` | 34,554 | `d6c7901fa9f1f60c0c14d42940defb1912d60fcfb102fb3b9f840e3b7f1974b3` |
| `c32-L3-overhead` | `RobotExpressive.normal.png` | 102,361 | `94891478fa8b141ffc27b9ed24fdeaedd5c7a09ba838e5637752cf81f4e5ab04` |
| `c32-L3-overhead` | `RobotExpressive.png` | 23,336 | `51d7d6cb3201465ed990058c1782a081a296d4b0f74152a44e10c0f9dacfd5ac` |
| `c32-L4-sun` | `RobotExpressive-lit.Jump.gif` | 105,533 | `f6fc4ee8ec97a88e88fe33036ced5f56d057539eef69a408d44ff154fd861290` |
| `c32-L4-sun` | `RobotExpressive-lit.Walking.gif` | 128,170 | `f08ea333ecf3be7afd88a483eaa487e5f6437d4cf00c2f43b65f79536ff23f46` |
| `c32-L4-sun` | `RobotExpressive.Jump.gif` | 36,805 | `ce15320677f99ab00835bb8f5aa80ab6ec029af552496502a48089d7365dd37e` |
| `c32-L4-sun` | `RobotExpressive.Walking.gif` | 44,147 | `ac099258176a694fe0114bb7a11afccf8636c0eb5efae9baeb053bd7b54660da` |
| `c32-L4-sun` | `RobotExpressive.depth.png` | 44,323 | `a51aeb569d441cd4112356e5a03546d235d38cdb33722ee4cca49368bfbbae73` |
| `c32-L4-sun` | `RobotExpressive.json` | 34,562 | `574965d3824a008fdc6da20e7ae51f415d097a6dfbf27d59f1b0d1a288179270` |
| `c32-L4-sun` | `RobotExpressive.normal.png` | 102,361 | `94891478fa8b141ffc27b9ed24fdeaedd5c7a09ba838e5637752cf81f4e5ab04` |
| `c32-L4-sun` | `RobotExpressive.png` | 23,336 | `51d7d6cb3201465ed990058c1782a081a296d4b0f74152a44e10c0f9dacfd5ac` |
| `c32-L5-rim` | `RobotExpressive-lit.Jump.gif` | 43,320 | `d1c971e1515b0de01836c4a9b7cf1082789b73d2e442ea81bf8862f00d2f8ec0` |
| `c32-L5-rim` | `RobotExpressive-lit.Walking.gif` | 52,258 | `21d667bc1dfbd1ab3a658e0b018a86272ca45a29cd595c45efbd4cc7c8c44e3b` |
| `c32-L5-rim` | `RobotExpressive.Jump.gif` | 36,805 | `ce15320677f99ab00835bb8f5aa80ab6ec029af552496502a48089d7365dd37e` |
| `c32-L5-rim` | `RobotExpressive.Walking.gif` | 44,147 | `ac099258176a694fe0114bb7a11afccf8636c0eb5efae9baeb053bd7b54660da` |
| `c32-L5-rim` | `RobotExpressive.depth.png` | 44,323 | `a51aeb569d441cd4112356e5a03546d235d38cdb33722ee4cca49368bfbbae73` |
| `c32-L5-rim` | `RobotExpressive.json` | 34,556 | `4eecaec4532da68b2b55d5a77c5658e2c771188c825612c81531b5c3a7a86127` |
| `c32-L5-rim` | `RobotExpressive.normal.png` | 102,361 | `94891478fa8b141ffc27b9ed24fdeaedd5c7a09ba838e5637752cf81f4e5ab04` |
| `c32-L5-rim` | `RobotExpressive.png` | 23,336 | `51d7d6cb3201465ed990058c1782a081a296d4b0f74152a44e10c0f9dacfd5ac` |
| `c48-L1-upper-left` | `RobotExpressive-lit.Jump.gif` | 210,686 | `a50cc2bd45f677732d3ba59962092dfd4d83ca34f4f68d8fa407e276513d1cae` |
| `c48-L1-upper-left` | `RobotExpressive-lit.Walking.gif` | 256,794 | `d6cffea304d9724cfe28c03bbb2efa2ca2a1f8a819144aa4ababbe95f29d2836` |
| `c48-L1-upper-left` | `RobotExpressive.Jump.gif` | 70,472 | `bea5cf02932ae2b14bcbb88a11923fda776243090891b5ba936cb308d17e04fe` |
| `c48-L1-upper-left` | `RobotExpressive.Walking.gif` | 85,367 | `11fff9922b60ff33b408e48f80dfec2b95f9d3c93cde68ddfc47cae6f57d945a` |
| `c48-L1-upper-left` | `RobotExpressive.depth.png` | 96,775 | `8d3ebf46f2ca2c385fedb383e67efda29776f7e159daa8e7dafe2c6dbc9198f5` |
| `c48-L1-upper-left` | `RobotExpressive.json` | 34,580 | `c384c7342a085752a1481f43e95e1daacece144703e8238041e09acd95ee3635` |
| `c48-L1-upper-left` | `RobotExpressive.normal.png` | 216,980 | `345b2cb6a0bbb0d339c7227b185da5313ee3f933bb2bd49fac25b4ea104173a1` |
| `c48-L1-upper-left` | `RobotExpressive.png` | 45,947 | `9608de90c5f3bc3d0c9323752b500949094ffb9ff3e8ee7be46dfe508ecf285d` |
| `c48-L2-upper-right` | `RobotExpressive-lit.Jump.gif` | 211,450 | `be46295e059d4685170ab48f1b43047ca27b049102f72c5352a05c7697d12ca2` |
| `c48-L2-upper-right` | `RobotExpressive-lit.Walking.gif` | 257,148 | `c8c1fe4aefe34026ef702398b93e05c80c43a8426db3401cbd113e4e9212e1c9` |
| `c48-L2-upper-right` | `RobotExpressive.Jump.gif` | 70,472 | `bea5cf02932ae2b14bcbb88a11923fda776243090891b5ba936cb308d17e04fe` |
| `c48-L2-upper-right` | `RobotExpressive.Walking.gif` | 85,367 | `11fff9922b60ff33b408e48f80dfec2b95f9d3c93cde68ddfc47cae6f57d945a` |
| `c48-L2-upper-right` | `RobotExpressive.depth.png` | 96,775 | `8d3ebf46f2ca2c385fedb383e67efda29776f7e159daa8e7dafe2c6dbc9198f5` |
| `c48-L2-upper-right` | `RobotExpressive.json` | 34,579 | `7523ffeb9c4bcea75667855c86c8dba49f1b9e6d4bb5e3666c95fb549ddd1610` |
| `c48-L2-upper-right` | `RobotExpressive.normal.png` | 216,980 | `345b2cb6a0bbb0d339c7227b185da5313ee3f933bb2bd49fac25b4ea104173a1` |
| `c48-L2-upper-right` | `RobotExpressive.png` | 45,947 | `9608de90c5f3bc3d0c9323752b500949094ffb9ff3e8ee7be46dfe508ecf285d` |
| `c48-L3-overhead` | `RobotExpressive-lit.Jump.gif` | 157,605 | `b38d7f1ac775e12c3ccc8d8d0573aec2704c1d2cc8992ab413ed9c9b92023b40` |
| `c48-L3-overhead` | `RobotExpressive-lit.Walking.gif` | 191,031 | `e9beb8fd09f25dfdf1bfe731fcc641d1fa69a06b20255f80b595a0da6607c8ca` |
| `c48-L3-overhead` | `RobotExpressive.Jump.gif` | 70,472 | `bea5cf02932ae2b14bcbb88a11923fda776243090891b5ba936cb308d17e04fe` |
| `c48-L3-overhead` | `RobotExpressive.Walking.gif` | 85,367 | `11fff9922b60ff33b408e48f80dfec2b95f9d3c93cde68ddfc47cae6f57d945a` |
| `c48-L3-overhead` | `RobotExpressive.depth.png` | 96,775 | `8d3ebf46f2ca2c385fedb383e67efda29776f7e159daa8e7dafe2c6dbc9198f5` |
| `c48-L3-overhead` | `RobotExpressive.json` | 34,578 | `81c927dec0e2634ca8a30fc83538e23689ab4f859d185035b14920d6995eb008` |
| `c48-L3-overhead` | `RobotExpressive.normal.png` | 216,980 | `345b2cb6a0bbb0d339c7227b185da5313ee3f933bb2bd49fac25b4ea104173a1` |
| `c48-L3-overhead` | `RobotExpressive.png` | 45,947 | `9608de90c5f3bc3d0c9323752b500949094ffb9ff3e8ee7be46dfe508ecf285d` |
| `c48-L4-sun` | `RobotExpressive-lit.Jump.gif` | 217,700 | `e447a62cbcb4a748600416af68c57a8072d439e9f8533057e4b5ab135a3728c7` |
| `c48-L4-sun` | `RobotExpressive-lit.Walking.gif` | 264,150 | `b9125f713897c271dbeb4ffbb77b7a92c2acd118b2dc54958a381deb85819281` |
| `c48-L4-sun` | `RobotExpressive.Jump.gif` | 70,472 | `bea5cf02932ae2b14bcbb88a11923fda776243090891b5ba936cb308d17e04fe` |
| `c48-L4-sun` | `RobotExpressive.Walking.gif` | 85,367 | `11fff9922b60ff33b408e48f80dfec2b95f9d3c93cde68ddfc47cae6f57d945a` |
| `c48-L4-sun` | `RobotExpressive.depth.png` | 96,775 | `8d3ebf46f2ca2c385fedb383e67efda29776f7e159daa8e7dafe2c6dbc9198f5` |
| `c48-L4-sun` | `RobotExpressive.json` | 34,586 | `1373893b3d18ead4aa0eb84f3748a1a86340e7aba8fc6194ae48aaeea0626fac` |
| `c48-L4-sun` | `RobotExpressive.normal.png` | 216,980 | `345b2cb6a0bbb0d339c7227b185da5313ee3f933bb2bd49fac25b4ea104173a1` |
| `c48-L4-sun` | `RobotExpressive.png` | 45,947 | `9608de90c5f3bc3d0c9323752b500949094ffb9ff3e8ee7be46dfe508ecf285d` |
| `c48-L5-rim` | `RobotExpressive-lit.Jump.gif` | 89,352 | `8a15c4cf4b6e92b2787c1da05a24931ac94d370c945edff17385c2d24faea329` |
| `c48-L5-rim` | `RobotExpressive-lit.Walking.gif` | 108,462 | `8823bbdaccc5b89449316a1ea3c9ddb5b7f28f6e9ae4e81400a4f61642e857d5` |
| `c48-L5-rim` | `RobotExpressive.Jump.gif` | 70,472 | `bea5cf02932ae2b14bcbb88a11923fda776243090891b5ba936cb308d17e04fe` |
| `c48-L5-rim` | `RobotExpressive.Walking.gif` | 85,367 | `11fff9922b60ff33b408e48f80dfec2b95f9d3c93cde68ddfc47cae6f57d945a` |
| `c48-L5-rim` | `RobotExpressive.depth.png` | 96,775 | `8d3ebf46f2ca2c385fedb383e67efda29776f7e159daa8e7dafe2c6dbc9198f5` |
| `c48-L5-rim` | `RobotExpressive.json` | 34,579 | `31169ea640ea5f6ed2ed22a181ddde983bc52330914a63f9b9f09f1f8c2f3a7b` |
| `c48-L5-rim` | `RobotExpressive.normal.png` | 216,980 | `345b2cb6a0bbb0d339c7227b185da5313ee3f933bb2bd49fac25b4ea104173a1` |
| `c48-L5-rim` | `RobotExpressive.png` | 45,947 | `9608de90c5f3bc3d0c9323752b500949094ffb9ff3e8ee7be46dfe508ecf285d` |

## Follow-up notes

- **Rendering cost.** Encoding the normal and depth buffers in pure Python costs about 0.07 s per 384×384 frame. The test suite's whole-command render went from 11.9 s to 21.9 s. This is recorded in PR #102 and the design, and no issue is open for it.
- **What the light can do.** The lit preview never brightens a pixel beyond its flat colour (D-14): a lit pixel ranges from its flat colour down to 30% of it. `--light-intensity` above 1 lets more of a surface reach full colour.
