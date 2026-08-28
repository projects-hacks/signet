"""Live diligence on the party asking to be paid.

The interesting cases are the ones where the cryptography is perfect. A forger
who registers a domain and signs from it produces a document every other check
passes, and only what the open web publishes for that brand contradicts it.
"""

from __future__ import annotations

import json

import httpx
import pytest

from signet.adapters.serpapi import SerpApiResolver, registrable
from signet.core.mark import decode_mark, encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, generate_key
from signet.core.verdict import Outcome
from signet.errors import AdapterError
from signet.ports.intelligence import BrandResolution, Diligence
from signet.ports.store import Issuer
from signet.verify.checks.counterparty import CounterpartyCheck
from signet.verify.context import VerificationContext
from tests.fakes import FakeRecordStore


def context(issuer: str, brand: str | None = "Northpost") -> VerificationContext:
    private, _ = generate_key()
    payload = canonicalize(
        {"iss": issuer, "ts": "2026-09-01T09:00:00Z", "id": "INV-1", "cls": "invoice"}
    )
    mark = decode_mark(encode_mark(payload, Ed25519Signer(private).sign(payload)))
    return VerificationContext(
        run_id="r",
        content=b"x",
        media_type="image/png",
        submitted_by="tester",
        mark=mark,
        claimed_brand=brand,
    )


class StubResolver:
    def __init__(self, canonical: str | None, diligence: Diligence) -> None:
        self._canonical = canonical
        self._diligence = diligence

    def resolve_brand(self, brand: str) -> BrandResolution:
        return BrandResolution(brand=brand, canonical_domain=self._canonical, sources=("s",))

    def diligence(self, domain: str, brand: str) -> Diligence:
        return self._diligence


def clean(domain: str) -> Diligence:
    return Diligence(
        domain=domain, exists=True, published_domain=domain, adverse_mentions=(), sources=("s",)
    )


def test_a_brand_published_elsewhere_contradicts_the_signing_domain() -> None:
    """The forgery no enrolled registry can see, because the victim never enrolled."""
    check = CounterpartyCheck(StubResolver("northpost.dev", clean("x")), FakeRecordStore())
    signal = check.run(context("northpost-invoices.dev"))
    assert signal.outcome is Outcome.FAIL
    assert "northpost.dev" in signal.detail
    assert signal.evidence["publishedDomain"] == "northpost.dev"


def test_enrolment_beats_a_search_result() -> None:
    """A reviewed binding outranks whatever Google shows, or every company whose
    invoices come from a second domain would be flagged."""
    store = FakeRecordStore(
        {
            "billing.northpost.dev": Issuer(
                domain="billing.northpost.dev",
                brand="Northpost",
                public_key=b"k",
                enrolled=True,
                frozen=False,
            )
        }
    )
    check = CounterpartyCheck(StubResolver("northpost.dev", clean("billing.northpost.dev")), store)
    assert check.run(context("billing.northpost.dev")).outcome is Outcome.PASS


def test_adverse_coverage_is_reported_and_never_decides() -> None:
    """Keyword matches are for a person to read. A rule acting on them would fire
    on ordinary commercial reporting and teach readers to ignore the check."""
    diligence = Diligence(
        domain="northpost.dev",
        exists=True,
        published_domain="northpost.dev",
        adverse_mentions=("Northpost named in invoice fraud inquiry",),
        sources=("s",),
    )
    check = CounterpartyCheck(StubResolver("northpost.dev", diligence), FakeRecordStore())
    signal = check.run(context("northpost.dev"))
    assert signal.outcome is Outcome.UNKNOWN
    assert "different companies with similar names" in signal.detail


def test_a_company_the_web_has_never_heard_of_is_thin_evidence_not_proof() -> None:
    absent = Diligence(
        domain="northpost.dev",
        exists=False,
        published_domain=None,
        adverse_mentions=(),
        sources=(),
    )
    check = CounterpartyCheck(StubResolver(None, absent), FakeRecordStore())
    assert check.run(context("northpost.dev")).outcome is Outcome.UNKNOWN


def test_no_brand_means_nothing_to_look_up() -> None:
    check = CounterpartyCheck(StubResolver("northpost.dev", clean("x")), FakeRecordStore())
    assert check.run(context("northpost.dev", brand=None)).outcome is Outcome.UNKNOWN


def resolver(handler: object, store: FakeRecordStore | None = None) -> SerpApiResolver:
    return SerpApiResolver(
        api_key="key",
        store=store or FakeRecordStore(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),  # type: ignore[arg-type]
    )


def test_the_knowledge_graph_is_preferred_over_the_first_blue_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "knowledge_graph": {"title": "Northpost", "website": "https://www.northpost.dev/"},
                "organic_results": [{"link": "https://directory.example/northpost"}],
            },
        )

    assert resolver(handler).resolve_brand("Northpost").canonical_domain == "northpost.dev"


def test_a_result_not_named_after_the_brand_is_a_source_and_not_an_answer() -> None:
    """Position on a page is not ownership. Searching a small freight company
    returned a New York town's .gov site, and taking it as canonical would have
    failed genuine documents."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"organic_results": [{"link": "https://northportny.gov/about"}]}
        )

    found = resolver(handler).resolve_brand("Northpost")
    assert found.canonical_domain is None
    assert found.sources == ("https://northportny.gov/about",)


def test_a_result_named_after_the_brand_answers() -> None:
    """Requiring a knowledge graph answered for almost nobody: Google returns
    none for Maersk. A domain the brand is named after is weaker evidence than
    an entity record and much stronger than ranking."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic_results": [{"link": "https://www.maersk.com/"}]})

    assert resolver(handler).resolve_brand("Maersk").canonical_domain == "maersk.com"


def test_what_a_company_does_is_not_who_it_is() -> None:
    """The tail of a company name describes the industry and half of it shares
    that tail, so containment is not enough."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"organic_results": [{"link": "https://freightservices.net"}]}
        )

    assert resolver(handler).resolve_brand("Northpost Freight Services").canonical_domain is None


def test_a_directory_listing_the_brand_is_not_the_brand() -> None:
    """linkedin.com/company/maersk mentions the brand in its path, and the
    comparison is on the registrable label only."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"organic_results": [{"link": "https://www.linkedin.com/company/maersk"}]}
        )

    assert resolver(handler).resolve_brand("Maersk").canonical_domain is None


def test_a_repeated_question_costs_nothing() -> None:
    """The month allows a few hundred searches, so a second reading of the same
    invoice must not spend one."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"organic_results": [{"link": "https://northpost.dev"}]})

    store = FakeRecordStore()
    resolver(handler, store).resolve_brand("Northpost")
    resolver(handler, store).resolve_brand("Northpost")
    assert len(calls) == 1


def test_an_error_carried_in_a_200_is_still_an_error() -> None:
    """Their failures arrive with a success status and an error key."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "Your account has run out of searches."})

    with pytest.raises(AdapterError, match="run out of searches"):
        resolver(handler).resolve_brand("Northpost")


def test_a_rejected_key_says_so() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorised")

    with pytest.raises(AdapterError, match="rejected the key"):
        resolver(handler).resolve_brand("Northpost")


def test_adverse_terms_are_matched_against_the_result_not_assumed_from_the_query() -> None:
    """The query asks for trouble, so every result mentions it. Only results whose
    own text carries a term count, or the check reports its own question back."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "fraud" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "organic_results": [
                        {"title": "Northpost wins haulage contract", "snippet": "Expansion."},
                        {"title": "Northpost named in fraud inquiry", "snippet": "Reported."},
                    ]
                },
            )
        return httpx.Response(200, json={"organic_results": [{"link": "https://northpost.dev"}]})

    found = resolver(handler).diligence("northpost.dev", "Northpost")
    assert len(found.adverse_mentions) == 1
    assert "fraud inquiry" in found.adverse_mentions[0]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("https://www.northpost.dev/pay", "northpost.dev"),
        ("northpost.dev", "northpost.dev"),
        ("HTTPS://NorthPost.dev", "northpost.dev"),
        ("", None),
        ("   ", None),
    ],
)
def test_an_answer_is_reduced_to_a_host(given: str, expected: str | None) -> None:
    assert registrable(given) == expected


def test_a_non_json_body_is_an_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    with pytest.raises(AdapterError):
        resolver(handler).resolve_brand("Northpost")


def test_the_cache_holds_what_came_back() -> None:
    store = FakeRecordStore()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic_results": [{"link": "https://northpost.dev"}]})

    resolver(handler, store).resolve_brand("Northpost")
    assert json.dumps(next(iter(store.cache.values())))


def test_being_enrolled_for_one_brand_does_not_exempt_claiming_another() -> None:
    """north-post.dev is enrolled as North Post Holdings. An invoice from it
    claiming to be Maersk was skipping this check entirely, because the
    exemption tested that the domain was enrolled rather than that it was
    enrolled for the brand on the paper."""
    store = FakeRecordStore(
        {
            "north-post.dev": Issuer(
                domain="north-post.dev",
                brand="North Post Holdings",
                public_key=b"k",
                enrolled=True,
                frozen=False,
            )
        }
    )
    check = CounterpartyCheck(StubResolver("maersk.com", clean("maersk.com")), store)
    signal = check.run(context("north-post.dev", brand="Maersk"))

    assert signal.outcome is Outcome.FAIL
    assert "maersk.com" in signal.detail
