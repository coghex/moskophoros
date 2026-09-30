from importlib.metadata import version

import moskophoros


def test_version_matches_the_installed_distribution():
    assert moskophoros.__version__ == version("moskophoros")


def test_version_is_the_only_public_attribute():
    public = {name for name in vars(moskophoros) if not name.startswith("_")}
    assert public == set()
    assert hasattr(moskophoros, "__version__")
