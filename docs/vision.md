# Moskophoros vision and design guardrails

**Status: accepted by the owner on 2026-09-29.** This is the heading that
`$guide` reviews against.

Moskophoros turns animated 3D models into pixel-art sprite sheets that stay
consistent in every direction. Over time it grows into the owner's general
toolkit for game art. It exists because AI image generation cannot keep one
subject coherent as it rotates: proportions, pose and placement drift between
directions.

This document holds the direction: what the project must stay true to, and
where it is heading. Concrete, unambiguous decisions (conventions, formulas,
formats, error behavior) live in [the design](design.md). When the two
disagree, raise it with the owner; do not quietly pick one. Current work and
coverage belong in the tracker and [guide reports](guide/).

New explicit owner decisions can revise this document. Record the decision and
its date beside the change; do not change intent to fit new code or an agent
recommendation. Preserve these principle IDs; retire a principle rather than
renumbering.

## Principles

### V-1. A generic tool that belongs to no game

Moskophoros serves the owner's games (Synarchy, and its rewrite Hetoimasia)
but never integrates with them, reads their files or emits their private
layouts (owner decision 2026-09-29). It speaks only of subjects, clips, views,
directions, frames, sheets and variants; game concepts such as units or tiles
are not part of it. Characters, creatures, buildings, items and flora all go
through one pipeline; a static sprite is a one-frame clip. See
[design §Vocabulary](design.md#vocabulary).

### V-2. A conventional, reproducible command-line tool

`moskophoros [options] <infile.glb> <outfile.png>` writes a sheet and a JSON
description beside it (owner decision 2026-09-29). Options have sensible
defaults, and the tool is scriptable and non-interactive. The same input and
settings produce the same bytes within the same recorded tools (Blender
version, renderer, Python dependencies), and every sheet records those tools
and settings so a result can be reproduced or questioned later (owner decision
2026-09-29, from the second review). See [design §CLI](design.md#cli).

### V-3. Binary glTF is the canonical input

`.glb` is the input (owner decision 2026-09-29; the owner delegated the
choice). It is an open, single-file format that carries mesh, skeleton,
animations and textures, and is readable without Blender, so a future renderer
can consume the same files. Blender-only features are baked into keyframes at
export.

### V-4. Stages with firm boundaries

Work flows through **capture** (3D to high-resolution images), **stylize**
(images to pixel art), **cleanup** (pixel-level fixes) and **export** (sheets
and metadata). Each stage depends only on the previous stage's output, keyed
by frame address, never on its internals. Capture keeps full information and
decides nothing about the look: reducing resolution, hardening transparency
and choosing colors all happen after it, so a style experiment never needs a
re-render (owner decision 2026-09-29). See [design §Pipeline](design.md#pipeline).

### V-5. Blender renders, behind one boundary

Blender is an integral part of the workflow for now (owner decision
2026-09-29). All Blender code lives in one backend that runs in Blender's own
process. Nothing else in the tool imports Blender or depends on a Blender
scene, so replacing it would mean swapping one backend.

### V-6. Views are parameters, not special cases

A view is a projection, a camera pitch, a number of directions and a start
angle (owner decision 2026-09-29). Top-down, side and isometric views, with 1,
2, 4, 8 or any number of directions, all come from those settings. Named
presets are shorthand and get no behavior their settings do not explain. See
[design §Camera and directions](design.md#camera-and-directions).

### V-7. Consistency is the product

Everything that AI generation gets wrong must be structurally impossible here,
and a defect in this principle outranks any visual improvement (owner decision
2026-09-29):

- **Stable scale.** One scale for every clip and direction of a sheet. The
  scale and ground point can be fixed explicitly and reused across separate
  exports, so adding a clip never shrinks existing sprites and different
  subjects keep their relative sizes. A fixed configuration that no longer
  fits is an error, never a silent shrink.
- **A fixed ground point.** It is defined once, in the subject's own
  coordinates, and always lands on the same pixel. It is never recomputed from
  a frame's feet or bounds, so intentional bounce and jumps survive.
- **Clips stay in place.** A clip whose root travels across the ground is
  rejected with a clear error until motion is deliberately allowed.
- **Lighting fixed to the camera**, so shading reads the same in every
  direction.

### V-8. Style comes later, and in the owner's hands

Output is deliberately plain until the owner sets the look, one pass at a time
(owner decision 2026-09-29). Style passes are replaceable and must not require
changes to capture or export. Where the style pipeline is expected to go is
under [Long-term direction](#long-term-direction).

### V-9. Every frame has an identity

A frame is addressed by subject, variant, clip, direction and sample time,
alongside a fingerprint of the settings that produced it (owner decision
2026-09-29). A frame index alone is not an identity, because it changes
meaning when the frame rate changes. This is what lets future touch-ups
survive a re-render, and notice when they no longer match.

### V-10. The toolkit grows from shared operations

Image operations are composable library functions that the pipeline uses and
that later commands can expose directly. Producing reusable sprites comes
first; other commands are added for a concrete need.

### V-11. Inputs are validated, never trusted

The owner makes and rigs models with AI assistance (owner decision
2026-09-29), so input quality varies. The tool states its expectations and
rejects violations with an error naming the file, clip and problem. A
malformed input is a readable failure, never a silently wrong sheet. See
[design §Input contract](design.md#input-contract).

### V-12. Python, and the owner's eye as the final judge

Python with numpy and Pillow (owner decision 2026-09-29), with few, pinned
dependencies. Automated tests cover what is mechanical: geometry, sampling,
layout, metadata, validation and determinism. Whether output is good is judged
by the owner, reviewing it at the size it will be used, both as a sheet and in
motion. A milestone is done when the owner approves, not when it integrates
with a game (owner decision 2026-09-29).

## Long-term direction

These are ideas the owner intends to pursue, not settled designs. They shape
today's choices only by what must not be ruled out. Each becomes concrete in
the design when the owner takes it up.

**The style pipeline.** Stylize becomes a chain of named, swappable passes
that can be saved as a style, so every asset shares one look. Candidates from
the founding conversation:

- supersampled capture shrunk by picking each block's most common color
  rather than averaging
- palettes, either authored or extracted from existing art, with per-material
  color ramps
- stepped (cel) shading from surface directions and a camera-fixed light
- 1-pixel selective outlines where depth, surface direction or material
  changes
- cleanup of stray pixels, doubled lines and jaggies
- stability between frames, so edges do not flicker in motion
- possibly an AI-assisted restyling pass, if it can stay consistent between
  frames

This is why capture keeps auxiliary images such as depth, surface direction
and base color available.

**The editor.** An interactive editor for viewing sheets, playing animations
and making pixel touch-ups, with history. Touch-ups are stored as overrides
keyed by frame identity (V-9), reapplied after a re-render, and flagged when
the settings fingerprint changes underneath them. It is a stretch goal; its
form (desktop or browser) is open.

**Variants.** Props attached to bones (weapons, tools) and palette swaps
(factions, injury, seasons) rendered from one animation, so combinations cost
no extra animation work.

**Beyond Blender.** A custom glTF renderer may replace the Blender backend
once the capture boundary has proven stable. Accepting `.blend` files
directly, by converting them to `.glb` first, is a possible convenience.

**More outputs and tools.** Other sheet formats (for example Aseprite's),
game-specific layouts expressed purely as configuration, and standalone image
commands such as palette extraction and remapping, recoloring, outlining,
trimming, rescaling and contact sheets.

## Continuing after a context reset

Run `$guide` after a meaningful batch of work. It compares merged code and
changed issues with these principles from the cursor in
[`guide/CURSOR.md`](guide/CURSOR.md). Read [the design](design.md) before
implementing. Update this document only for accepted changes in intent. When
no settled next step exists, discuss the next unmet goal or long-term idea
before designing more work.
