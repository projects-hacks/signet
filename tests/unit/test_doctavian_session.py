"""The Doctavian session, which has to survive without a person watching it.

Their access token lives sixty five minutes. Everything here exists so that
number stops being an operational problem.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest

from signet.adapters.doctavian_auth import (
    RefreshingToken,
    Session,
    read_session,
    session_from,
    write_session,
)
from signet.errors import ConfigError


def session_file(tmp_path: Path, **overrides: object) -> Path:
    path = tmp_path / "session.json"
    write_session(
        path,
        Session(
            access_token=str(overrides.get("access_token", "live-token")),
            expires_at=float(overrides.get("expires_at", time.time() + 3600)),
            refresh_token=str(overrides.get("refresh_token", "refresh-1")),
        ),
    )
    return path


def token(path: Path, handler: object) -> RefreshingToken:
    return RefreshingToken(
        api_key="key",
        base_url="https://demo.api.doctavian.com/v1",
        path=path,
        client=httpx.Client(transport=httpx.MockTransport(handler)),  # type: ignore[arg-type]
    )


def refused(request: httpx.Request) -> httpx.Response:
    raise AssertionError("the network was reached when the cached token was still good")


def test_a_live_token_is_reused_rather_than_renewed(tmp_path: Path) -> None:
    assert token(session_file(tmp_path), refused)() == "live-token"


def test_a_token_inside_its_last_five_minutes_is_renewed_early(tmp_path: Path) -> None:
    """A request that starts inside the margin and takes a few seconds must not
    arrive after the token has died."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3900})

    path = session_file(tmp_path, expires_at=time.time() + 120)
    assert token(path, handler)() == "fresh"


def test_a_rotated_refresh_token_replaces_the_one_that_was_used(tmp_path: Path) -> None:
    """Entra hands back a new refresh token on every use, and losing it costs a
    human sign-in."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": "fresh", "expires_in": 3900, "refresh_token": "refresh-2"},
        )

    path = session_file(tmp_path, expires_at=0)
    token(path, handler)()
    stored = read_session(path)
    assert stored is not None
    assert stored.refresh_token == "refresh-2"


def test_a_response_without_a_new_refresh_token_keeps_the_old_one(tmp_path: Path) -> None:
    """Omitting it means the current one still stands, not that the session ended."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3900})

    path = session_file(tmp_path, expires_at=0)
    token(path, handler)()
    stored = read_session(path)
    assert stored is not None
    assert stored.refresh_token == "refresh-1"


def test_the_refresh_goes_to_the_auth_host_not_the_versioned_api_path(tmp_path: Path) -> None:
    """The configured base URL carries the API version, and the auth endpoint
    sits above it."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3900})

    token(session_file(tmp_path, expires_at=0), handler)()
    assert seen == ["https://demo.api.doctavian.com/public/v1/auth/microsoft/token"]


def test_a_refused_renewal_names_the_command_that_fixes_it(tmp_path: Path) -> None:
    """A revoked or lapsed refresh token cannot be retried around, so the error
    has to be an instruction rather than a status code."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(ConfigError, match=r"doctavian_login\.py"):
        token(session_file(tmp_path, expires_at=0), handler)()


def test_no_session_at_all_says_how_to_start_one(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"doctavian_login\.py"):
        token(tmp_path / "absent.json", refused)()


def test_a_session_with_no_refresh_token_cannot_renew_itself(tmp_path: Path) -> None:
    path = session_file(tmp_path, expires_at=0, refresh_token="")
    with pytest.raises(ConfigError, match="no refresh token"):
        token(path, refused)()


def test_the_session_file_is_readable_only_by_its_owner(tmp_path: Path) -> None:
    """It holds a long lived credential and nothing else on the machine needs it."""
    path = session_file(tmp_path)
    assert path.stat().st_mode & 0o077 == 0


def test_a_corrupt_session_file_reads_as_absent(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("{ this is not json", encoding="utf-8")
    assert read_session(path) is None


def test_a_token_response_without_an_expiry_still_produces_a_session() -> None:
    """Their proxy is not obliged to send expires_in, and an hour is the
    provider's own default."""
    built = session_from({"access_token": "t"})
    assert 3500 < built.expires_at - time.time() <= 3600


def test_the_written_file_holds_what_was_written(tmp_path: Path) -> None:
    path = session_file(tmp_path, access_token="a", refresh_token="r")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["access_token"] == "a"
    assert raw["refresh_token"] == "r"
