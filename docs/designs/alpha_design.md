# Alpha design

Moskophoros's sprite sheets have alpha, but only as coverage: a pixel is
either a surface (alpha 255) or background (alpha 0). Transparency in the
model itself is lost. A glTF `MASK` material's cut-out texels render as
opaque texture colour (#75), and a translucent `BLEND` surface is drawn as if
it were solid. This arc makes the sheet carry the model's transparency, so
foliage, fences, hair cards, glass or ghosts come out as the model intends.
The colour sheet, its normal and depth maps and the lit preview all stay
aligned.

The owner asked for it on 2026-10-15: "outlines are something i want for
sure, but actually outside my use case at the moment, much more critical is
transparency. help me implement alpha". It lifts #75's deferral for design.
It benefits the owner producing game art, and any project using the tool
(V-1).

Design state: `exploring`

Status legend: `[ ]` unprocessed · `[#N]` linked to issue N · `[no-issue]`
reviewed and deliberately not tracked separately · `[deferred]` blocked on a
concrete precondition

## Processing status

Slices are proposed once scope is settled.

- [ ] EPIC. Carry the model's transparency into the sprite sheet

## Epic contract

- **Goal:** a model whose glTF materials are transparent renders a sheet
  whose pixels carry that transparency as the design settles it. Its normal
  and depth maps, material identity and shade agree with the colour pixel for
  pixel, and the owner judges the look (V-12).
- **Done when:** to be settled with the scope (Q-1). It will include
  automated alignment checks on generated fixtures, and byte-identical
  output for models without transparent materials (Q-6). The owner reviews
  sheets and previews and approves them, in a slice of its own.
- **Users and operators:** the owner producing game art; agents maintaining
  the tool.
- **Arc label:** None proposed.

## Current state and evidence

**Fixed by earlier owner decisions (not reopened here):**

- The flat ambient colour sheet, the normal map, the optional depth map and
  the lit preview are accepted (lighting sheet design; owner LIT-6 review,
  2026-10-14). Alpha must keep them aligned: whatever is transparent in the
  colour sheet is transparent in every map.
- Material styling is accepted, generated ramps included (MAT-8, D-28 to
  D-36). Only its D-26 is revisited here.
- V-4: capture keeps full information and decides nothing about the look.
  Any hardening of transparency happens after capture, so a style change
  never needs a re-render.
- Output is deterministic; the tool belongs to no game (V-1); the owner
  judges the look (V-12).

**Verified current behaviour (master `bd52aba`):**

- **Input:** the glTF reader reports each primitive's alpha mode as given,
  defaulting to `OPAQUE` (design §Input contract).
- **Colour capture:** Workbench, "texture color, falling back to material
  color", film transparent, straight alpha (design §Capture, *Render
  settings*). Its alpha is antialiased coverage only.
  - Workbench ignores the alpha the glTF importer builds for a `MASK`
    material, so cut-out texels render opaque. In the material styling
    spike's *edges* fixture, the holes are `(54, 54, 54, 255)`.
  - Setting `blend_method` (`CLIP`, `BLEND`) or `surface_render_method`
    (`BLENDED`) changes nothing (material styling Q-26; #75).
- **Auxiliary capture:** one Cycles render, 1 sample per pixel, transparent
  bounces 8. It gives the material ID, shade, normal and depth from one
  shared camera sample per pixel. Every material's shader is replaced by an
  emission, so no material property, alpha included, reaches it.
  - **D-26** (owner, 2026-10-08): `MASK` materials are captured opaque, with
    no cutouts, so the ID and shade match the colour.
  - The spike noted that its Cycles method can honour the importer's alpha
    (#75).
- **Identity:** a pixel showing a `BLEND` material, or any alpha mode other
  than `OPAQUE` and `MASK`, decodes to no identity and takes the ordinary
  look (design §Pipeline; material styling D-23).
- **Stylize:** a pixel's coverage is the mean alpha of its supersampled
  block, and a pixel below 0.5 is `(0, 0, 0, 0)`. Every kept pixel has alpha
  255, under `plain` (the alpha-weighted mean) and `mode` (an alpha-weighted
  vote) alike (design §Stylize).
- **Maps:** a normal or depth map pixel exists exactly where the reduced
  colour's alpha is 255 (design §Stylize, *Normal and depth maps*).
- **Palettes** have no alpha; a palette maps only the RGB of a kept pixel.
- **Previews** are GIFs, whose transparency is one bit.
- **The owner's models at hand** use no transparency: RobotExpressive, the
  ramp review's `suzannes.glb` and `lightfix.glb` are all `OPAQUE`, with no
  `baseColorFactor` alpha below 1.
- **Tracker:** #75 (open, `enhancement`, `blocked`) records `MASK` cutouts
  as deferred work. No other open epic overlaps this arc.

## Open questions

### Q-1. Scope: what does "alpha" cover?

glTF has two kinds of transparency:

- **`MASK`, cutouts.** Each texel is either drawn or discarded, at the
  material's `alphaCutoff` (0.5 by default). Used for foliage, fences, hair
  cards and chain mail.
- **`BLEND`, translucency.** A surface is partly see-through: glass, water,
  smoke, ghosts, energy effects.

Alpha can come from the base colour texture's alpha, from
`baseColorFactor`'s alpha, or both (glTF multiplies them, and vertex colour
alpha too).

What matters is which effects the owner needs now, and whether a model
needs it today.

### Q-2. Output alpha: binary, or levels of translucency?

A sheet pixel can be binary, fully there or not, which is the pixel-art
convention, or it can carry levels of partial alpha. With levels:

- how many there are;
- how they relate to the palette (which has no alpha), the coverage rule
  and `plain` and `mode`;
- what a translucent pixel shows: the colour blended over what is behind it
  in the model, or the front surface's colour with a partial alpha.

### Q-3. Where does a surface's alpha come from?

Follow glTF: `baseColorFactor` alpha × texture alpha × vertex colour alpha,
with `alphaCutoff` for `MASK`. Or a subset.

### Q-4. Capture technique and cost

How Blender produces cutouts and, if in scope, translucency,
deterministically: Cycles for the colour, a separate alpha pass, or another
method, with its cost per frame. To settle by a spike once scope is known.

### Q-5. The other buffers through a cutout or a translucent surface

The material ID, shade, normal and depth: do they show the front surface,
the first opaque surface, or none? And how do the lit preview and the GIF
previews (one-bit transparency) show it?

### Q-6. Compatibility

- Sheets of models without `MASK` or `BLEND` materials stay byte-identical
  (to confirm).
- Sheets of existing `MASK` models change. The owner decides that change and
  its acceptance. D-26 and design §Capture are revised to match.

### Q-7. Settings

Whether anything is a setting or an option, such as an alpha cutoff
override, the number of levels or an opt-out, under the settings layers and
the schema-bump rule.

### Q-8. What happens to #75?

The new epic either supersedes #75 or absorbs it as a child. This design
recommends one; `process-design-doc` and the manager act on it.

## Verification strategy

To be settled with Q-1 to Q-6. Expected families:

- generated fixtures, such as a cutout plane and a translucent quad over an
  opaque body;
- alignment tests across the colour and every map;
- byte-identical output for models without transparent materials;
- the owner's visual review as its own slice (V-12), as the lighting arc
  did with LIT-6.
