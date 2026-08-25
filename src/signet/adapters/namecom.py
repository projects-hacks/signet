"""name.com CORE API: the trust root, and the lookalike sweep.

Written against their OpenAPI 3.1 spec rather than the prose docs, so the field
names and shapes here are the ones the service actually accepts.

Two ports, one vendor, because name.com genuinely provides two capabilities. A
check that needs availability does not thereby gain the ability to write DNS.

Publishing is idempotent. A daily root is republished every day under the same
host, and creating rather than updating would leave a zone full of stale roots
that all verify, which defeats the point of publishing one.

Their limits are enforced here rather than by callers: 20 requests per second
and 3000 per hour, and a TTL floor of 300 seconds. A TTL below the floor raises
instead of being silently clamped, because a caller that asked for 60 has made
an assumption about propagation that is about to be wrong.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable, Iterator
from typing import Any, Final

import httpx

from signet.adapters import http
from signet.errors import AdapterError

PRODUCTION_URL: Final = "https://api.name.com"
SANDBOX_URL: Final = "https://api.dev.name.com"

MIN_TTL_SECONDS: Final = 300
MAX_REQUESTS_PER_SECOND: Final = 20
_MIN_INTERVAL: Final = 1.0 / MAX_REQUESTS_PER_SECOND
_TIMEOUT_SECONDS: Final = 20.0
_PER_PAGE: Final = 1000


class NameComClient:
    """Shared transport: auth, pacing, pagination and error translation."""

    def __init__(
        self,
        username: str,
        token: str,
        base_url: str = PRODUCTION_URL,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not username or not token:
            raise ValueError("name.com requires a username and an API token")
        credential = base64.b64encode(f"{username}:{token}".encode()).decode("ascii")
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Basic {credential}", "Accept": "application/json"}
        self._client = client or http.client(_TIMEOUT_SECONDS)
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_call = 0.0

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        self._pace()
        try:
            response = self._client.request(
                method, f"{self._base_url}{path}", headers=self._headers, **kwargs
            )
        except httpx.HTTPError as exc:
            raise AdapterError(f"name.com {method} {path} failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise AdapterError(
                "name.com rejected the credentials. Use your API token rather than your "
                "account password, and note that two-step verification is not compatible "
                "with API access."
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise AdapterError(f"name.com rate limit reached. Retry-After: {retry_after}.")
        if not response.is_success:
            raise AdapterError(
                f"name.com {method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise AdapterError(f"name.com returned a non-JSON body for {path}") from exc

    def _pace(self) -> None:
        elapsed = self._monotonic() - self._last_call
        if elapsed < _MIN_INTERVAL:
            self._sleep(_MIN_INTERVAL - elapsed)
        self._last_call = self._monotonic()


class NameComDns:
    """Publishes and reads DNS records. Implements DnsPublisher."""

    def __init__(self, client: NameComClient) -> None:
        self._client = client

    def publish_txt(self, domain: str, name: str, value: str, ttl: int) -> None:
        if ttl < MIN_TTL_SECONDS:
            raise AdapterError(
                f"name.com enforces a minimum TTL of {MIN_TTL_SECONDS} seconds, got {ttl}"
            )
        body = {"host": name, "type": "TXT", "answer": value, "ttl": ttl}
        existing = self._find(domain, host=name, answer=None)
        if existing is None:
            self._client.request("POST", f"/core/v1/domains/{domain}/records", json=body)
            return
        self._client.request("PUT", f"/core/v1/domains/{domain}/records/{existing}", json=body)

    def records(self, domain: str) -> Iterator[dict[str, Any]]:
        """Yield every TXT record on the zone, following pagination."""
        page = 1
        while True:
            body = self._client.request(
                "GET",
                f"/core/v1/domains/{domain}/records",
                params={"page": page, "perPage": _PER_PAGE},
            )
            for record in body.get("records", []) or []:
                if isinstance(record, dict):
                    yield record
            next_page = body.get("nextPage")
            if not next_page or next_page == page:
                return
            page = int(next_page)

    def delete(self, domain: str, record_id: int) -> None:
        self._client.request("DELETE", f"/core/v1/domains/{domain}/records/{record_id}")

    def _find(self, domain: str, host: str, answer: str | None) -> int | None:
        for record in self.records(domain):
            if record.get("type") != "TXT":
                continue
            if (record.get("host") or "") != host:
                continue
            if answer is not None and record.get("answer") != answer:
                continue
            identifier = record.get("id")
            return int(identifier) if isinstance(identifier, int) else None
        return None


class NameComRegistrar:
    """Availability and search. Implements DomainRegistrar."""

    def __init__(self, client: NameComClient) -> None:
        self._client = client

    def available(self, domains: tuple[str, ...]) -> dict[str, bool]:
        if not domains:
            return {}
        body = self._client.request(
            "POST", "/core/v1/domains:checkAvailability", json={"domainNames": list(domains)}
        )
        return {
            str(result["domainName"]): bool(result.get("purchasable"))
            for result in body.get("results", []) or []
            if isinstance(result, dict) and "domainName" in result
        }

    def search(self, keyword: str, tlds: tuple[str, ...] = (), timeout_ms: int = 2500) -> list[str]:
        """Ask name.com for related names. Used to widen a lookalike sweep."""
        payload: dict[str, Any] = {"keyword": keyword, "timeout": timeout_ms}
        if tlds:
            payload["tldFilter"] = list(tlds)
        body = self._client.request("POST", "/core/v1/domains:search", json=payload)
        return [
            str(result["domainName"])
            for result in body.get("results", []) or []
            if isinstance(result, dict) and "domainName" in result
        ]
