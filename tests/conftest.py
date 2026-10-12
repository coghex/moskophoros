"""Shared fixtures for every test, the Blender tests included."""

import pytest


@pytest.fixture(autouse=True)
def no_owner_settings(tmp_path_factory, monkeypatch):
    """Point `$XDG_CONFIG_HOME` and `$HOME` at empty temporary directories, so
    no test reads the owner's user settings file (settings design D-17). A
    test that needs a user file writes it under these."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
