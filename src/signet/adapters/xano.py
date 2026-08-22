"""Xano: the system of record.

We own both sides of this contract, so it is defined here rather than discovered.
Five operations, one per method on the RecordStore port, and nothing more.

The division of labour matters and is worth stating where someone will read it.
Xano holds state and workflow: issuers, batches, the submissions ledger, cached
evidence, and the append-only audit log. It does not decide anything. Signing,
Merkle work and the verdict stay in Python, where they are pure functions with a
golden test suite, because a determinism claim you cannot run offline is not a
claim worth making.

Authentication is a shared secret in a header, checked by the function stack.
Xano's own auth issues user tokens, which is the wrong shape here: the caller is
a worker, not a person.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

import httpx

from signet.errors import AdapterError
from signet.ports.store import Issuer

API_KEY_HEADER: Final = "X-Signet-Key"
_TIMEOUT_SECONDS: Final = 20.0


# Xano's routing 404 carries this message. A function stack reporting a genuine
# record miss does not.
_ROUTE_MISSING: Final = "Unable to locate request"


class XanoRecordStore:
    def __init__(self, base_url: str, api_key: str, client: httpx.Client | None = None) -> None:
        if not base_url or not api_key:
            raise ValueError("Xano requires an API group base URL and an API key")
        self._base_url = base_url.rstrip("/")
        self._headers = {API_KEY_HEADER: api_key, "Accept": "application/json"}
        self._client = client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def issuer(self, domain: str) -> Issuer | None:
        body = self._request("GET", f"/issuer/{domain}", allow_missing=True)
        if body is None:
            return None
        return Issuer(
            domain=str(body.get("domain", domain)),
            brand=str(body.get("brand", "")),
            public_key=bytes.fromhex(str(body.get("public_key_hex", ""))),
            enrolled=bool(body.get("enrolled")),
            frozen=bool(body.get("frozen")),
        )

    def record_submission(self, fingerprint: str, submitted_by: str) -> bool:
        """Record a submission. Returns False when this fingerprint was seen before.

        The uniqueness decision belongs to the database, not to a read followed
        by a write. Two workers verifying the same receipt at once must not both
        be told they are the first.
        """
        body = self._request(
            "POST", "/submission", json={"fingerprint": fingerprint, "submitted_by": submitted_by}
        )
        return bool(body.get("first_time", False))

    def cache_get(self, namespace: str, key: str) -> Mapping[str, object] | None:
        body = self._request(
            "GET", "/cache", params={"namespace": namespace, "key": key}, allow_missing=True
        )
        if body is None:
            return None
        value = body.get("value")
        return value if isinstance(value, dict) else None

    def cache_put(self, namespace: str, key: str, value: Mapping[str, object]) -> None:
        self._request(
            "POST", "/cache", json={"namespace": namespace, "key": key, "value": dict(value)}
        )

    def append_audit(self, run_id: str, event: str, detail: Mapping[str, object]) -> None:
        self._request(
            "POST", "/audit", json={"run_id": run_id, "event": event, "detail": dict(detail)}
        )

    def _request(self, method: str, path: str, allow_missing: bool = False, **kwargs: Any) -> Any:
        try:
            response = self._client.request(
                method, f"{self._base_url}{path}", headers=self._headers, **kwargs
            )
        except httpx.HTTPError as exc:
            raise AdapterError(f"Xano {method} {path} failed: {exc}") from exc

        if response.status_code == 404:
            # Xano answers 404 both for a record that does not exist and for a route
            # that was never built, and only the body tells them apart. Swallowing
            # both made an empty workspace look like a working one, so a missing
            # route is an error even where a missing record is not.
            if _ROUTE_MISSING in response.text:
                raise AdapterError(
                    f"Xano has no endpoint at {path}. The API group answered, so the base "
                    "URL and key are right, but the function stack does not exist yet."
                )
            if allow_missing:
                return None
        if response.status_code in (401, 403):
            raise AdapterError(
                f"Xano rejected the request. Check that {API_KEY_HEADER} matches the value "
                "the function stack expects."
            )
        if not response.is_success:
            raise AdapterError(
                f"Xano {method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise AdapterError(f"Xano returned a non-JSON body for {path}") from exc
