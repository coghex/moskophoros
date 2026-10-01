import types
from importlib.metadata import version

import moskophoros
import moskophoros.cli
import moskophoros.gltf
import moskophoros.sampling
import moskophoros.views


def test_version_matches_the_installed_distribution():
    assert moskophoros.__version__ == version("moskophoros")


def test_the_package_namespace_holds_only_its_submodules():
    """The package exports nothing itself; its modules are its public surface."""
    public = {name for name in vars(moskophoros) if not name.startswith("_")}
    assert {"cli", "gltf", "sampling", "views"} <= public
    for name in public:
        module = getattr(moskophoros, name)
        assert isinstance(module, types.ModuleType), name
        assert module.__name__ == f"moskophoros.{name}"
    assert hasattr(moskophoros, "__version__")
