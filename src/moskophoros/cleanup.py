"""Cleanup, following design §Cleanup (slice 1: none).

A stage between stylize and export. It depends only on the frames it is
given, and touches no file or process.
"""


def passthrough(frames):
    """Return the frames unchanged: the same addresses, order, pixels and
    metadata."""
    return tuple(frames)
