"""DNS resolution over HTTPS, across independent providers.

The verifying key lives in DNS, so a spoofed answer substitutes an attacker's key
and every signature check then passes against it. Two cheap mechanisms close that
without depending on the issuer's DNS provider: query providers on separate
infrastructure and require them to agree, and record whether the answer arrived
over a validated DNSSEC chain.

DNS over HTTPS rather than UDP port 53. The query is encrypted to the resolver
rather than readable and rewritable by anything on the path, and it survives
networks that block or intercept plain DNS, which describes a great many
corporate networks our verifiers sit inside.

DNSSEC stays advisory. Adoption is partial, so an unsigned zone still verifies
and the evidence bundle records which it was.
"""

from __future__ import annotations

from typing import Final

import httpx

from signet.errors import AdapterError
from signet.ports.dns import TxtLookup

TXT_RECORD_TYPE: Final = 16
_TIMEOUT_SECONDS: Final = 8.0

DEFAULT_PROVIDERS: Final = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
)


def _unquote(value: str) -> str:
    # Providers return TXT data quoted, and split long records into adjacent
    # quoted chunks. The value is the concatenation, not the first chunk.
    parts = [part for part in value.split('" "')]
    return "".join(part.strip('"') for part in parts)


class DohResolver:
    """Resolves through several providers and reports whether they agreed."""

    def __init__(
        self,
        providers: tuple[str, ...] = DEFAULT_PROVIDERS,
        client: httpx.Client | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self._providers = providers
        self._client = client or httpx.Client(
            timeout=_TIMEOUT_SECONDS, headers={"Accept": "application/dns-json"}
        )

    def lookup_txt(self, name: str) -> TxtLookup:
        answers: list[frozenset[str]] = []
        validated = True
        for provider in self._providers:
            records, authenticated = self._query(provider, name)
            answers.append(frozenset(records))
            validated = validated and authenticated

        agreed = len(set(answers)) == 1
        return TxtLookup(
            name=name,
            records=tuple(sorted(answers[0])) if agreed else (),
            dnssec_validated=validated and agreed,
            resolvers_agreed=agreed,
        )

    def _query(self, provider: str, name: str) -> tuple[tuple[str, ...], bool]:
        try:
            response = self._client.get(provider, params={"name": name, "type": "TXT"})
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AdapterError(f"DNS lookup for {name} via {provider} failed: {exc}") from exc

        records = tuple(
            _unquote(str(answer.get("data", "")))
            for answer in body.get("Answer", [])
            if isinstance(answer, dict) and answer.get("type") == TXT_RECORD_TYPE
        )
        return records, bool(body.get("AD"))
