"""What a verdict does when the record store cannot be reached.

The interesting direction is not that the run survives, it is that it refuses
to certify. An outage is exactly when someone would send a lookalike, and a
check that passes because it could not look is worse than no check at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from signet.constants import DNS_LABEL
from signet.core.mark import encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, encode_public_key, generate_key
from signet.core.verdict import Decision, Outcome, Verdict
from signet.errors import AdapterError
from signet.ports.store import Issuer
from signet.verify.pipeline import VerificationPipeline, VerificationRequest
from signet.verify.registry import default_checks
from tests.fakes import FakeDnsResolver, FakeRecordStore, FakeRegistrationData

BRAND = "Blue Bottle Coffee"
DOMAIN = "bluebottle.com"
TODAY = date(2026, 8, 20)
FIELDS = {
    "iss": DOMAIN,
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-88213104",
    "cls": "receipt",
    "amt": "14.75",
    "cur": "USD",
}


class UnreachableStore(FakeRecordStore):
    """Down in every direction a check might touch it."""

    def issuer(self, domain: str) -> Issuer | None:
        raise AdapterError("Xano is unreachable.")

    def enrolled_issuers(self) -> tuple[Issuer, ...]:
        raise AdapterError("Xano is unreachable.")

    def record_submission(self, fingerprint: str, submitted_by: str) -> bool:
        raise AdapterError("Xano is unreachable.")

    def append_audit(self, run_id: str, event: str, detail: Mapping[str, object]) -> None:
        raise AdapterError("Xano is unreachable.")


@pytest.fixture
def outage() -> Decision:
    private, public = generate_key()
    resolver = FakeDnsResolver({f"{DNS_LABEL}.{DOMAIN}": (encode_public_key(public),)})
    payload = canonicalize(FIELDS)
    mark_text = encode_mark(payload, Ed25519Signer(private).sign(payload))

    store = UnreachableStore(
        {DOMAIN: Issuer(domain=DOMAIN, brand=BRAND, public_key=public, enrolled=True, frozen=False)}
    )
    pipeline = VerificationPipeline(
        checks=default_checks(resolver, store, FakeRegistrationData(), TODAY), store=store
    )
    return pipeline.run(
        VerificationRequest(
            run_id="outage",
            content=b"a photograph of a receipt",
            media_type="image/png",
            submitted_by="tester",
            mark_text=mark_text,
            claimed_brand=BRAND,
        )
    )


def outcome_of(decision: Decision, name: str) -> Outcome:
    return next(signal.outcome for signal in decision.signals if signal.name == name)


def test_an_unreachable_store_never_certifies(outage: Decision) -> None:
    assert outage.verdict is not Verdict.CERTIFIED


def test_identity_is_unknown_rather_than_passing(outage: Decision) -> None:
    """Passing identity because the registry was unreachable admits a lookalike."""
    assert outcome_of(outage, "identity") is Outcome.UNKNOWN


def test_duplicate_is_unknown_rather_than_not_seen_before(outage: Decision) -> None:
    assert outcome_of(outage, "duplicate") is Outcome.UNKNOWN


def test_the_signature_still_verifies_without_the_store(outage: Decision) -> None:
    """The key comes from DNS and the payload from the mark, so neither needs the store."""
    assert outcome_of(outage, "signature") is Outcome.PASS


def test_an_unwritable_audit_trail_does_not_fail_the_run(outage: Decision) -> None:
    """A verdict that depends on logging is one that vanishes when logging does."""
    assert outage.signals


class ExtractorDown:
    def extract(self, content: bytes, media_type: str) -> object:
        raise AdapterError("Nutrient is unreachable.")


def run_with(store: FakeRecordStore, extractor: object | None) -> Decision:
    private, public = generate_key()
    resolver = FakeDnsResolver({f"{DNS_LABEL}.{DOMAIN}": (encode_public_key(public),)})
    store.issuers = {
        DOMAIN: Issuer(domain=DOMAIN, brand=BRAND, public_key=public, enrolled=True, frozen=False)
    }
    payload = canonicalize(FIELDS)
    mark_text = encode_mark(payload, Ed25519Signer(private).sign(payload))
    pipeline = VerificationPipeline(
        checks=default_checks(resolver, store, FakeRegistrationData(), TODAY, extractor=extractor),
        store=store,
    )
    return pipeline.run(
        VerificationRequest(
            run_id="spend",
            content=b"a photograph of a receipt",
            media_type="image/png",
            submitted_by="tester",
            mark_text=mark_text,
            claimed_brand=BRAND,
        )
    )


def test_an_outage_does_not_spend_the_document() -> None:
    """The ledger write is permanent and this run never reached a verdict a
    person could act on. Spending the document here turns the retry into a
    false accusation: the document comes back and is told it was already
    submitted. An outage must cost a retry, never the document."""
    store = FakeRecordStore({})
    first = run_with(store, extractor=ExtractorDown())
    assert outcome_of(first, "fidelity") is Outcome.UNKNOWN
    assert outcome_of(first, "duplicate") is Outcome.UNKNOWN
    assert store.submissions == set()

    healed = run_with(store, extractor=None)
    assert outcome_of(healed, "duplicate") is Outcome.PASS
    assert healed.verdict is Verdict.CERTIFIED


def test_a_healthy_run_still_spends_exactly_once() -> None:
    store = FakeRecordStore({})
    assert outcome_of(run_with(store, extractor=None), "duplicate") is Outcome.PASS
    assert outcome_of(run_with(store, extractor=None), "duplicate") is Outcome.FAIL
