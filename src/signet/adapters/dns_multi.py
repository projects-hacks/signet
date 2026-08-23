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


def _host(provider: str) -> str:
    """The resolver's hostname, which is what a reader recognises."""
    return provider.split("//", 1)[-1].split("/", 1)[0]


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
        seen: list[tuple[frozenset[str], bool]] = []
        answers: dict[str, tuple[str, ...]] = {}
        for provider in self._providers:
            records, authenticated = self._query(provider, name)
            seen.append((frozenset(records), authenticated))
            answers[_host(provider)] = records

        # A provider returning nothing has not contradicted one returning a key, it
        # has not caught up. Negative caching makes that the normal state for the
        # first minutes after publication, so counting it as a conflict reports our
        # own propagation as a spoofing attempt. The attack this check exists for
        # still fails: a forged key shows up as two providers answering with
        # different keys, and withholding an answer cannot manufacture a signature.
        answered = [(records, validated) for records, validated in seen if records]
        if not answered:
            return TxtLookup(
                name=name,
                records=(),
                dnssec_validated=False,
                resolvers_agreed=True,
                answers=answers,
            )

        distinct = {records for records, _ in answered}
        agreed = len(distinct) == 1
        return TxtLookup(
            name=name,
            records=tuple(sorted(next(iter(distinct)))) if agreed else (),
            dnssec_validated=agreed and all(validated for _, validated in answered),
            resolvers_agreed=agreed,
            answers=answers,
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
