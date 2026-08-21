"""Doctavian document generation.

Templates carry the branching, so one template handles every shape of a document
class and the payload we sign is produced from a verified record rather than
typed by anyone. That is why generation sits on the issuing path at all.

Two things about their auth are unusual enough to be worth stating. The bearer
token is a standard OAuth 2.0 token from Microsoft or Google rather than a
Doctavian credential, so token acquisition is injected rather than performed
here. And x-api-key is scoped per API area, so the Documents key will not open
the Signatures endpoints.

Tokens are rejected within roughly two minutes of expiry, so a provider that
caches must refresh ahead of that boundary rather than on failure.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

import httpx

from signet.errors import AdapterError

BASE_URL: Final = "https://api.doctavian.com/v1"
_TIMEOUT_SECONDS: Final = 30.0

TokenProvider = Callable[[], str]


class DoctavianRenderer:
    """Renders a document class from structured fields.

    The mark and locator are passed as ordinary template fields, so the template
    decides where they print. Nothing about the signature is Doctavian specific.
    """

    def __init__(
        self,
        api_key: str,
        token_provider: TokenProvider,
        template_ids: Mapping[str, str],
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._token = token_provider
        self._templates = template_ids
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def render(
        self, document_class: str, fields: Mapping[str, str], mark: str, locator: str
    ) -> bytes:
        template_id = self._templates.get(document_class)
        if template_id is None:
            raise AdapterError(
                f"no Doctavian template configured for document class {document_class!r}"
            )

        payload = {
            "templateId": template_id,
            "format": "pdf",
            "data": {**dict(fields), "signet_mark": mark, "signet_locator": locator},
        }
        try:
            response = self._client.post(
                f"{self._base_url}/documents/document/generate",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AdapterError(f"Doctavian generation failed for {document_class}: {exc}") from exc
        return response.content

    def ping(self) -> bool:
        """Connectivity check against the endpoint their quickstart uses."""
        try:
            response = self._client.get(
                f"{self._base_url}/documents/document/list", headers=self._headers()
            )
        except httpx.HTTPError as exc:
            raise AdapterError(f"Doctavian is unreachable: {exc}") from exc
        if response.status_code == 401:
            raise AdapterError(
                "Doctavian rejected the credentials. A 401 naming ApiKeyInvalid means the "
                "x-api-key is not the Documents key; any other 401 means the bearer token "
                "is missing or expired."
            )
        return response.is_success

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}", "x-api-key": self._api_key}
