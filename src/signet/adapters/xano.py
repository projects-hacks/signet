"""Xano: the system of record.

We own both sides of this contract, so it is defined here rather than discovered.
Five operations, one per method on the RecordStore port, and nothing more.

The division of labour matters and is worth stating where someone will read it.
Xano holds state and workflow: issuers, batches, the submissions ledger, cached
evidence, and the append-only audit log. It does not decide anything. Signing,
Merkle work and the verdict stay in Python, where they are pure functions with a
golden test suite, because a determinism claim you cannot run offline is not a
claim worth making.

Authentication is a shared secret sent as a bearer token, checked by one guard
function every endpoint runs first. Xano's own auth issues user tokens, which is
the wrong shape here because the caller is a worker rather than a person, but
the bearer header is still the right carrier: it is the only documented way a
function stack can read a caller supplied credential, through
$env.$request_auth_token. A custom header would have to be parsed out of
$http_headers, which is documented only as a text array.

Absence is a 200 carrying null, never a 404. Xano answers 404 both for a record
that is missing and for a route that was never built, and letting those wear the
same costume is how an empty workspace passed for a working one.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, Final

import httpx

from signet.errors import AdapterError
from signet.ports.store import Issuer

_TIMEOUT_SECONDS: Final = 20.0


# Xano's routing 404 carries this message. A function stack reporting a genuine
# record miss does not.
_ROUTE_MISSING: Final = "Unable to locate request"


def _cache_key(namespace: str, key: str) -> str:
    """One column carries the namespace, so no composite unique index is needed.

    A composite unique index is structurally expressible in XanoScript but no
    source demonstrates one, and the correctness of the cache rests entirely on
    that index holding.
    """
    return f"{namespace}:{key}"


# A day is long enough to stop a demo re-asking the same question and short
# enough that a domain registered this morning is not reported as absent
# tomorrow.
CACHE_TTL_SECONDS: Final = 86_400


def _now_ms() -> int:
    return int(time.time() * 1000)


class XanoRecordStore:
    def __init__(self, base_url: str, api_key: str, client: httpx.Client | None = None) -> None:
        if not base_url or not api_key:
            raise ValueError("Xano requires an API group base URL and an API key")
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        self._client = client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def issuer(self, domain: str) -> Issuer | None:
        body = self._request("GET", "/issuer", params={"domain": domain})
        # An absent record answers null, which arrives here as an empty body.
        if not isinstance(body, dict) or not body:
            return None
        return self._issuer(body, domain)

    @staticmethod
    def _issuer(row: Mapping[str, Any], domain: str = "") -> Issuer:
        return Issuer(
            domain=str(row.get("domain", domain)),
            brand=str(row.get("brand", "")),
            public_key=bytes.fromhex(str(row.get("public_key_hex", ""))),
            enrolled=bool(row.get("enrolled")),
            frozen=bool(row.get("frozen")),
        )

    def enrol(self, domain: str, brand: str, public_key: bytes) -> None:
        """Bind a brand to a domain, replacing an earlier binding for that domain.

        Upsert rather than insert: keygen is the kind of command someone runs
        twice, and the second run should supersede the key it replaced rather
        than fail on the unique index.
        """
        self._request(
            "POST",
            "/issuer",
            json={"domain": domain, "brand": brand, "public_key_hex": public_key.hex()},
        )

    def enrolled_issuers(self) -> tuple[Issuer, ...]:
        body = self._request("GET", "/issuers")
        rows = body.get("issuers") if isinstance(body, dict) else body
        if not isinstance(rows, list):
            raise AdapterError(f"Xano returned an unexpected issuer list: {str(body)[:200]}")
        return tuple(self._issuer(row) for row in rows if isinstance(row, dict))

    def record_submission(self, fingerprint: str, submitted_by: str) -> bool:
        """Record a submission. Returns False when this fingerprint was seen before.

        The uniqueness decision belongs to the database, not to a read followed
        by a write. Two workers verifying the same receipt at once must not both
        be told they are the first.
        """
        body = self._request(
            "POST", "/submission", json={"fingerprint": fingerprint, "submitted_by": submitted_by}
        )
        existing = body.get("existing") if isinstance(body, dict) else None
        return existing is None

    def cache_get(self, namespace: str, key: str) -> Mapping[str, object] | None:
        """The cached value, or None once it is past its expiry.

        Freshness is enforced here rather than in the query, because the store
        returns whatever row it holds and the port promises that an entry which
        has expired reads as absent. A stale answer is worse than no answer for
        a signal like domain age: the fact it records can change, and serving
        the old one would keep a resolved risk alive indefinitely.
        """
        body = self._request("GET", "/cache", params={"key": _cache_key(namespace, key)})
        if not isinstance(body, dict):
            return None
        expires_at = body.get("expires_at")
        if isinstance(expires_at, int | float) and expires_at and expires_at <= _now_ms():
            return None
        value = body.get("value")
        return value if isinstance(value, dict) else None

    def cache_put(self, namespace: str, key: str, value: Mapping[str, object]) -> None:
        self._request(
            "POST",
            "/cache",
            json={
                "namespace": namespace,
                "key": _cache_key(namespace, key),
                "value": dict(value),
                "expires_at": _now_ms() + CACHE_TTL_SECONDS * 1000,
            },
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
                "Xano rejected the request. Check that the bearer token matches the "
                "signet_api_key environment variable the guard function compares against."
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
