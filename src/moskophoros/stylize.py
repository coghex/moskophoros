"""Stylize: the look of each frame, following design §Stylize.

A stage between capture and cleanup. It depends only on the frames it is
given, never on capture internals, and touches no file or process.
"""

from moskophoros import imageops
from moskophoros.sampling import ImageFrame


def plain(frames, factor):
    """Reduce every supersampled frame by `factor`×`factor` blocks.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata.
    """
    return tuple(
        ImageFrame(
            frame.address, imageops.reduce_blocks(frame.pixels, factor), frame.metadata
        )
        for frame in frames
    )


def mode(frames, factor):
    """Reduce every supersampled frame by `factor`×`factor` blocks, keeping
    each block's most common colour.

    Returns new `ImageFrame`s with the same addresses, in the same order, each
    carrying its input frame's metadata.
    """
    return tuple(
        ImageFrame(
            frame.address,
            imageops.reduce_blocks_mode(frame.pixels, factor),
            frame.metadata,
        )
        for frame in frames
    )
