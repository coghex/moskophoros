from importlib.metadata import version
from types import ModuleType

import moskophoros


def test_version_matches_the_installed_distribution():
    assert moskophoros.__version__ == version("moskophoros")


def test_version_is_the_only_public_attribute_besides_submodules():
    public = {
        name
        for name, value in vars(moskophoros).items()
        if not name.startswith("_")
        and not (
            isinstance(value, ModuleType) and value.__name__ == f"moskophoros.{name}"
        )
    }
    assert public == set()
    assert hasattr(moskophoros, "__version__")
