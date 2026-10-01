"""The installed Blender is found through the normal search order and passes
the version check."""

import pytest

from moskophoros.capture import blender


@pytest.mark.blender
def test_the_installed_blender_is_found_and_supported():
    found = blender.locate()
    assert found.path.is_absolute()
    series = tuple(int(part) for part in found.version.split(".")[:2])
    assert series == blender.SUPPORTED_SERIES
