"""Keeping a Doctavian session alive without a person in the loop.

Their gateway wants two credentials. The x-api-key names the environment and is
ordinary configuration. The bearer names the caller, and it is a Microsoft Entra
access token that lives sixty five minutes, which is short enough that a value
pasted into a file is stale before most work finishes.

The authorisation flow already asks for offline_access, so the exchange returns a
refresh token alongside the access token. That refresh token is the thing worth
keeping, and this module is the reason a person signs in once rather than hourly.

Entra rotates the refresh token on every use, so the store is read before each
refresh and rewritten after it. A file rather than an environment variable,
because a value that changes cannot live somewhere only a human edits.

The session file is the only source of truth for this credential. If the refresh
token itself expires or is revoked, no amount of retrying helps and the error
says so rather than reporting a generic authentication failure.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx

from signet.adapters import http
from signet.errors import AdapterError, ConfigError

AUTH_PATH: Final = "/public/v1/auth/microsoft/token"
CLIENT_ID: Final = "11e71170-3499-43f3-b878-7df343f43d37"
SCOPE: Final = "api://40728276-52a7-4932-bf32-76737f1fd01a/.default offline_access"

DEFAULT_SESSION_PATH: Final = Path(".signet/doctavian-session.json")
# Refresh before the token actually expires. A request that starts inside the
# margin and takes a few seconds must not arrive after the token has died.
_MARGIN_SECONDS: Final = 300.0
_TIMEOUT_SECONDS: Final = 30.0


@dataclass(frozen=True, slots=True)
class Session:
    access_token: str
    expires_at: float
    refresh_token: str

    @property
    def usable(self) -> bool:
        return bool(self.access_token) and self.expires_at - _MARGIN_SECONDS > time.time()


def read_session(path: Path) -> Session | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    return Session(
        access_token=str(raw.get("access_token", "")),
        expires_at=float(raw.get("expires_at", 0)),
        refresh_token=str(raw.get("refresh_token", "")),
    )


def write_session(path: Path, session: Session) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "access_token": session.access_token,
                "expires_at": session.expires_at,
                "refresh_token": session.refresh_token,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # The refresh token is a long lived credential. Nothing else on the machine
    # needs to read it.
    path.chmod(0o600)


def session_from(payload: dict[str, object], previous: str = "") -> Session:
    """Build a session from a token response.

    Entra usually rotates the refresh token, but a response that omits it means
    the previous one is still current rather than that the session is over.
    """
    access = str(payload.get("access_token", ""))
    if not access:
        raise AdapterError("Doctavian returned no access token.")
    expires_in = payload.get("expires_in")
    lifetime = float(expires_in) if isinstance(expires_in, int | float | str) else 3600.0
    return Session(
        access_token=access,
        expires_at=time.time() + lifetime,
        refresh_token=str(payload.get("refresh_token", "") or previous),
    )


class RefreshingToken:
    """Implements the renderer's TokenProvider by keeping a session current."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        path: Path = DEFAULT_SESSION_PATH,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/").removesuffix("/v1")
        self._path = path
        self._client = client or http.client(_TIMEOUT_SECONDS)

    def __call__(self) -> str:
        session = read_session(self._path)
        if session is None:
            raise ConfigError("No Doctavian session. Run: uv run python scripts/doctavian_login.py")
        if session.usable:
            return session.access_token
        return self._refresh(session).access_token

    def _refresh(self, session: Session) -> Session:
        if not session.refresh_token:
            raise ConfigError(
                "The Doctavian session has expired and carries no refresh token. "
                "Run: uv run python scripts/doctavian_login.py"
            )
        response = self._client.post(
            f"{self._base_url}{AUTH_PATH}",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": session.refresh_token,
                "scope": SCOPE,
            },
            headers={"x-api-key": self._api_key},
        )
        if not response.is_success:
            raise ConfigError(
                "Doctavian would not renew the session, so a person has to sign in again. "
                f"The provider said {response.status_code}: {response.text[:160]}. "
                "Run: uv run python scripts/doctavian_login.py"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AdapterError("Doctavian returned a non-JSON token response.") from exc
        if not isinstance(payload, dict):
            raise AdapterError("unexpected Doctavian token response shape")
        renewed = session_from(payload, previous=session.refresh_token)
        write_session(self._path, renewed)
        return renewed
