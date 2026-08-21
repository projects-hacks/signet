"""End to end through the pipeline, including the attacks it exists to catch.

Every scenario here is a beat in the demo. If one of these regresses, the demo
regresses with it.
"""

from __future__ import annotations

from datetime import date

import pytest

from signet.constants import DNS_LABEL
from signet.core.mark import encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, encode_public_key, generate_key
from signet.core.verdict import Verdict
from signet.ports.registry import Registration
from signet.ports.store import Issuer
from signet.verify.pipeline import VerificationPipeline, VerificationRequest
from signet.verify.registry import default_checks
from tests.fakes import FakeDnsResolver, FakeRecordStore, FakeRegistrationData

BRAND = "Blue Bottle Coffee"
DOMAIN = "bluebottle.com"
LOOKALIKE = "bluebottle-receipts.com"
TODAY = date(2026, 8, 20)

FIELDS = {
    "iss": DOMAIN,
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-88213104",
    "cls": "receipt",
    "amt": "14.75",
    "cur": "USD",
}


@pytest.fixture
def world() -> tuple[FakeDnsResolver, FakeRecordStore, FakeRegistrationData, bytes]:
    private, public = generate_key()
    resolver = FakeDnsResolver({f"{DNS_LABEL}.{DOMAIN}": (encode_public_key(public),)})
    resolver.dnssec.add(f"{DNS_LABEL}.{DOMAIN}")
    store = FakeRecordStore(
        {DOMAIN: Issuer(domain=DOMAIN, brand=BRAND, public_key=public, enrolled=True, frozen=False)}
    )
    return resolver, store, FakeRegistrationData(), private


def build(
    resolver: FakeDnsResolver, store: FakeRecordStore, registrations: FakeRegistrationData
) -> VerificationPipeline:
    return VerificationPipeline(
        checks=default_checks(resolver, store, registrations, TODAY), store=store
    )


def mark_for(private: bytes, fields: dict[str, str]) -> str:
    payload = canonicalize(fields)
    return encode_mark(payload, Ed25519Signer(private).sign(payload))


def request(mark_text: str | None, brand: str | None = BRAND) -> VerificationRequest:
    return VerificationRequest(
        run_id="run-1",
        content=b"a photograph of a receipt",
        media_type="image/jpeg",
        submitted_by="tester",
        mark_text=mark_text,
        claimed_brand=brand,
    )


def test_a_genuine_receipt_certifies(world) -> None:  # type: ignore[no-untyped-def]
    resolver, store, registrations, private = world
    decision = build(resolver, store, registrations).run(request(mark_for(private, FIELDS)))
    assert decision.verdict is Verdict.CERTIFIED
    assert DOMAIN in decision.reason


def test_an_altered_amount_is_flagged(world) -> None:  # type: ignore[no-untyped-def]
    resolver, store, registrations, private = world
    genuine = mark_for(private, FIELDS)
    tampered = genuine.replace("amt=14.75", "amt=1475.00")

    decision = build(resolver, store, registrations).run(request(tampered))

    assert decision.verdict is Verdict.FLAGGED
    assert "altered" in decision.reason


def test_a_forger_signing_at_their_own_domain_is_flagged(world) -> None:  # type: ignore[no-untyped-def]
    """The signature is genuinely valid. Only the identity check catches this."""
    resolver, store, registrations, _ = world
    forger_private, forger_public = generate_key()
    resolver.records[f"{DNS_LABEL}.{LOOKALIKE}"] = (encode_public_key(forger_public),)
    registrations.registrations[LOOKALIKE] = Registration(
        domain=LOOKALIKE,
        created=date(2026, 8, 9),
        expires=date(2027, 8, 9),
        registrar="Fake Registrar",
        locked=False,
    )
    forged = mark_for(forger_private, {**FIELDS, "iss": LOOKALIKE})

    decision = build(resolver, store, registrations).run(request(forged))

    signals = {signal.name: signal.outcome.value for signal in decision.signals}
    assert signals["signature"] == "pass"
    assert decision.verdict is Verdict.FLAGGED
    assert "brand record" in decision.reason


def test_a_repeated_submission_is_flagged(world) -> None:  # type: ignore[no-untyped-def]
    resolver, store, registrations, private = world
    pipeline = build(resolver, store, registrations)
    text = mark_for(private, FIELDS)

    assert pipeline.run(request(text)).verdict is Verdict.CERTIFIED
    second = pipeline.run(request(text))

    assert second.verdict is Verdict.FLAGGED
    assert "already been submitted" in second.reason


def test_a_frozen_issuer_is_flagged(world) -> None:  # type: ignore[no-untyped-def]
    """A lapsed or transferred domain hands the identity to whoever registers it next."""
    resolver, store, registrations, private = world
    store.issuers[DOMAIN] = Issuer(
        domain=DOMAIN, brand=BRAND, public_key=b"", enrolled=True, frozen=True
    )

    decision = build(resolver, store, registrations).run(request(mark_for(private, FIELDS)))

    assert decision.verdict is Verdict.FLAGGED
    assert "frozen" in decision.reason


def test_an_unmarked_document_is_unsigned_not_flagged(world) -> None:  # type: ignore[no-untyped-def]
    resolver, store, registrations, _ = world
    decision = build(resolver, store, registrations).run(request(None))
    assert decision.verdict is Verdict.UNSIGNED


def test_a_smudged_mark_falls_back_rather_than_erroring(world) -> None:  # type: ignore[no-untyped-def]
    resolver, store, registrations, _ = world
    decision = build(resolver, store, registrations).run(request("S1|not-a-real-mark"))
    assert decision.verdict is Verdict.UNSIGNED


def test_disagreeing_resolvers_are_flagged(world) -> None:  # type: ignore[no-untyped-def]
    """A split answer can mean a spoofed one, so it fails closed."""
    resolver, store, registrations, private = world

    class Disagreeing(FakeDnsResolver):
        def lookup_txt(self, name: str):  # type: ignore[no-untyped-def]
            lookup = super().lookup_txt(name)
            return type(lookup)(
                name=lookup.name, records=(), dnssec_validated=False, resolvers_agreed=False
            )

    split = Disagreeing(resolver.records)
    decision = build(split, store, registrations).run(request(mark_for(private, FIELDS)))

    assert decision.verdict is Verdict.FLAGGED
    assert "disagree" in decision.reason
