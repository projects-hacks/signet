"""Live web data about the counterparty an invoice asks you to pay.

The signature says who issued a document. It cannot say whether that issuer is
the company the reader thinks it is, because a forger who registers their own
domain and signs from it is cryptographically flawless. Answering that needs
something outside the document, and what is outside the document changes daily.

Two questions are asked here and they are different.

Brand to canonical domain runs once, at enrolment. It is the question the
lookalike check depends on and it is allowed to be slow, because a person reads
the answer before an issuer is bound to a brand.

Diligence runs when a reader is looking at a document from a counterparty nobody
has enrolled. It asks whether the business exists at all, which domain the open
web publishes for it, and whether the recent record carries anything a person
should read before transferring money.

Two things shape this adapter. The plan allows 250 searches a month and 50 an
hour, so results are cached per counterparty and the budget is counted here
rather than by callers. And Google surfaces the answer in different blocks for
different queries, so the knowledge graph is preferred and organic results are
the fallback, never the other way round.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final
from urllib.parse import urlsplit

import httpx

from signet.adapters import http
from signet.errors import AdapterError
from signet.ports.intelligence import BrandResolution, Diligence
from signet.ports.store import RecordStore

BASE_URL: Final = "https://serpapi.com/search"
_TIMEOUT_SECONDS: Final = 20.0

CACHE_NAMESPACE: Final = "serpapi"
# A company's registered domain does not change between two readings of the same
# invoice, and the month's budget is small enough that a repeat lookup is a real
# cost rather than a rounding error.
_RESULT_LIMIT: Final = 10

# Words that make a search result worth a person's attention. Deliberately narrow:
# a list that fires on ordinary commercial language would train readers to ignore
# it, which is worse than not reporting at all.
ADVERSE_TERMS: Final = (
    "fraud",
    "scam",
    "phishing",
    "invoice fraud",
    "impersonation",
    "court",
    "lawsuit",
    "liquidation",
    "insolvency",
)

_HOST_PREFIX: Final = re.compile(r"^www\.")


def registrable(url_or_host: str) -> str | None:
    """The host an answer points at, without the scheme, path or www.

    Comparison is on the host and not the full url, because a company's knowledge
    graph entry may point at a landing page while its documents come from the
    bare domain.
    """
    text = url_or_host.strip()
    if not text:
        return None
    host = urlsplit(text if "//" in text else f"//{text}").hostname
    if not host:
        return None
    return _HOST_PREFIX.sub("", host.lower())


class SerpApiResolver:
    """Implements EntityResolver.

    The store supplies the cache, so a deployment with a shared store shares the
    budget across every process rather than each one spending its own.
    """

    def __init__(
        self,
        api_key: str,
        store: RecordStore,
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._store = store
        self._base_url = base_url
        self._client = client or http.client(_TIMEOUT_SECONDS)

    def resolve_brand(self, brand: str) -> BrandResolution:
        payload = self._search(f"{brand} official website")
        graph = payload.get("knowledge_graph")
        sources: list[str] = []
        domain: str | None = None
        if isinstance(graph, dict):
            website = graph.get("website")
            if isinstance(website, str):
                domain = registrable(website)
                sources.append(website)
        # Organic results are recorded but never answer the question. A first
        # blue link is not an assertion that a brand owns a domain, and treating
        # it as one is not a theoretical problem: searching a small freight
        # company returned a New York town's .gov site, which as a canonical
        # domain would have failed a genuine document and blocked a genuine
        # enrolment. The knowledge graph is an entity claim; a search result is
        # a page that mentioned the words.
        for result in _organic(payload)[:_RESULT_LIMIT]:
            link = result.get("link")
            if isinstance(link, str):
                sources.append(link)
        return BrandResolution(brand=brand, canonical_domain=domain, sources=tuple(sources))

    def diligence(self, domain: str, brand: str) -> Diligence:
        payload = self._search(f'"{brand}" {domain}')
        graph = payload.get("knowledge_graph")
        published: str | None = None
        if isinstance(graph, dict):
            website = graph.get("website")
            if isinstance(website, str):
                published = registrable(website)

        results = _organic(payload)
        sources = tuple(
            result["link"] for result in results if isinstance(result.get("link"), str)
        )[:_RESULT_LIMIT]
        # Existence is read from the open web having anything to say at all. A
        # trading company that no page anywhere mentions is not proof of fraud,
        # but it is the thing a reader would want to know.
        exists = bool(graph) or bool(sources)

        adverse = self._search(f'"{brand}" ({" OR ".join(ADVERSE_TERMS[:4])})') if exists else {}
        mentions = tuple(
            _snippet(result)
            for result in _organic(adverse)
            if _mentions_adverse(result) and _snippet(result)
        )[:_RESULT_LIMIT]

        return Diligence(
            domain=domain,
            exists=exists,
            published_domain=published,
            adverse_mentions=mentions,
            sources=sources,
        )

    def _search(self, query: str) -> Mapping[str, Any]:
        cached = self._store.cache_get(CACHE_NAMESPACE, query)
        if cached is not None:
            return cached

        response = self._client.get(
            self._base_url,
            params={"engine": "google", "q": query, "api_key": self._api_key, "hl": "en"},
        )
        if response.status_code == 401:
            raise AdapterError("SerpApi rejected the key.")
        if not response.is_success:
            raise AdapterError(f"SerpApi returned {response.status_code}: {response.text[:200]}")
        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError("SerpApi returned a non-JSON body.") from exc
        if not isinstance(body, dict):
            raise AdapterError("unexpected SerpApi response shape")
        # Their errors arrive with a 200 and an error key rather than a status.
        error = body.get("error")
        if isinstance(error, str):
            raise AdapterError(f"SerpApi: {error}")
        self._store.cache_put(CACHE_NAMESPACE, query, body)
        return body


def _organic(payload: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    results = payload.get("organic_results")
    if not isinstance(results, list):
        return ()
    return [result for result in results if isinstance(result, dict)]


def _snippet(result: Mapping[str, Any]) -> str:
    title = result.get("title")
    snippet = result.get("snippet")
    parts = [str(part) for part in (title, snippet) if isinstance(part, str) and part.strip()]
    return " ".join(parts)[:300]


def _mentions_adverse(result: Mapping[str, Any]) -> bool:
    text = _snippet(result).lower()
    return any(term in text for term in ADVERSE_TERMS)
