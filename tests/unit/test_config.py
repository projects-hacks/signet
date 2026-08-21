from __future__ import annotations

import pytest

from signet.config import Credentials, load_settings
from signet.errors import ConfigError


def test_fixtures_are_on_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNET_FIXTURES", raising=False)
    assert load_settings().fixtures


def test_fixtures_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNET_FIXTURES", "0")
    assert not load_settings().fixtures


def test_an_unconfigured_service_names_itself() -> None:
    with pytest.raises(ConfigError, match="SerpApi is not configured"):
        Credentials("SerpApi", ("",)).require()


def test_a_configured_service_returns_its_values() -> None:
    assert Credentials("SerpApi", ("key",)).require() == ("key",)


def test_settings_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "  abc  ")
    assert load_settings().serpapi.require() == ("abc",)
