"""Shared fixtures for every test, the Blender tests included."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def no_owner_settings_for_the_session(tmp_path_factory):
    """Point `$XDG_CONFIG_HOME` and `$HOME` at empty temporary directories
    before any fixture of any scope runs, so no test or shared fixture reads
    the owner's user settings file (settings design D-17)."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
        patch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
        yield


@pytest.fixture(autouse=True)
def no_owner_settings(tmp_path_factory, monkeypatch):
    """Give each test its own empty `$XDG_CONFIG_HOME` and `$HOME`, so a user
    file one test writes never reaches another. A test that needs a user
    file writes it under these."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
