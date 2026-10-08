"""Stylize: the look of each frame, following design §Stylize.

A stage between capture and cleanup. It depends only on the frames it is
given, never on capture internals, and touches no file or process.

Frames arrive one at a time and may carry named buffers beside their colour;
`identities`, a `sampling.Identities`, is the asset's identity list that a
frame's identity buffer indexes. The reductions here read only the colour.
Each returns ordinary reduced colour frames carrying no buffers, and lets go
of a frame, with all its buffers, before asking for the next.
"""

from moskophoros import imageops
from moskophoros.sampling import ImageFrame


def plain(frames, factor, palette=None, identities=None):
    """Reduce every supersampled frame by `factor`×`factor` blocks.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata. With a palette, map the reduced
    pixels after averaging.
    """
    result = []
    for frame in frames:
        pixels = imageops.reduce_blocks(frame.pixels, factor)
        if palette is not None:
            pixels = imageops.map_palette(pixels, palette)
        result.append(ImageFrame(frame.address, pixels, frame.metadata))
        # Release the capture before asking its iterator for the next array.
        del frame
    return tuple(result)


def mode(frames, factor, palette=None, identities=None):
    """Reduce every supersampled frame by `factor`×`factor` blocks, keeping
    each block's most common colour.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata. With a palette, map the supersampled
    pixels before voting, so shades mapped to one entry pool their votes.
    """
    result = []
    for frame in frames:
        pixels = frame.pixels
        if palette is not None:
            pixels = imageops.map_palette(pixels, palette)
        pixels = imageops.reduce_blocks_mode(pixels, factor)
        result.append(ImageFrame(frame.address, pixels, frame.metadata))
        del frame
    return tuple(result)
