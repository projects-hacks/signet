from __future__ import annotations

import os
from pathlib import Path

import pytest

from signet.config import Credentials, load_env_file, load_settings
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


def test_the_env_file_fills_in_what_the_environment_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sourcing the file before every command is a step people forget, and the
    error it produces blames the configuration rather than the missing step."""
    (tmp_path / ".env").write_text(
        "# a comment\n\nexport SERPAPI_API_KEY=from-the-file\nNUTRIENT_API_KEY='quoted'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("NUTRIENT_API_KEY", raising=False)

    assert load_env_file(tmp_path) == tmp_path / ".env"
    assert os.environ["SERPAPI_API_KEY"] == "from-the-file"
    assert os.environ["NUTRIENT_API_KEY"] == "quoted"


def test_the_real_environment_wins_over_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise a file left in a checkout would override a deployment."""
    (tmp_path / ".env").write_text("SERPAPI_API_KEY=from-the-file\n", encoding="utf-8")
    monkeypatch.setenv("SERPAPI_API_KEY", "from-the-environment")

    load_env_file(tmp_path)
    assert os.environ["SERPAPI_API_KEY"] == "from-the-environment"


def test_no_env_file_is_not_an_error(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "nothing-here") is None
