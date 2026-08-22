"""The central claim, tested rather than asserted.

A run is archived, the archive is closed, and the archive alone is re-decided.
If the replayed verdict ever drifts from the recorded one, the product stops
being evidence and becomes an opinion with a timestamp.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from signet.constants import DNS_LABEL
from signet.core.mark import Mark, decode_mark, encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, encode_public_key, generate_key
from signet.core.verdict import Decision, Verdict
from signet.ports.store import Issuer
from signet.verify.context import VerificationContext
from signet.verify.evidence import Bundle, JsonValue, read, replay, write
from signet.verify.pipeline import VerificationPipeline, VerificationRequest
from signet.verify.registry import default_checks
from tests.fakes import FakeDnsResolver, FakeRecordStore, FakeRegistrationData

BRAND = "Blue Bottle Coffee"
DOMAIN = "bluebottle.com"
TODAY = date(2026, 8, 20)
RECORDED_AT = "2026-08-20T09:14:00Z"
CONTENT = b"a photograph of a receipt"

FIELDS = {
    "iss": DOMAIN,
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-88213104",
    "cls": "receipt",
    "amt": "14.75",
    "cur": "USD",
}

World = tuple[FakeDnsResolver, FakeRecordStore, FakeRegistrationData, bytes]


@pytest.fixture
def world() -> World:
    private, public = generate_key()
    resolver = FakeDnsResolver({f"{DNS_LABEL}.{DOMAIN}": (encode_public_key(public),)})
    resolver.dnssec.add(f"{DNS_LABEL}.{DOMAIN}")
    store = FakeRecordStore(
        {DOMAIN: Issuer(domain=DOMAIN, brand=BRAND, public_key=public, enrolled=True, frozen=False)}
    )
    return resolver, store, FakeRegistrationData(), private


def mark_for(private: bytes, fields: dict[str, str]) -> str:
    payload = canonicalize(fields)
    return encode_mark(payload, Ed25519Signer(private).sign(payload))


def observed(
    resolver: FakeDnsResolver, registrations: FakeRegistrationData
) -> dict[str, JsonValue]:
    """The third party answers this run depended on, kept as they came back."""
    lookup = resolver.lookup_txt(f"{DNS_LABEL}.{DOMAIN}")
    registration = registrations.registration(DOMAIN)
    return {
        "dns": {
            "name": lookup.name,
            "records": list(lookup.records),
            "dnssec_validated": lookup.dnssec_validated,
            "resolvers_agreed": lookup.resolvers_agreed,
        },
        "rdap": {
            "domain": registration.domain,
            "created": registration.created.isoformat(),
            "expires": registration.expires.isoformat(),
            "registrar": registration.registrar,
            "locked": registration.locked,
        },
    }


def decoded(mark_text: str | None) -> Mark | None:
    return decode_mark(mark_text) if mark_text is not None else None


def run_and_capture(world: World, mark_text: str | None) -> tuple[Decision, Bundle]:
    resolver, store, registrations, _ = world
    request = VerificationRequest(
        run_id="run-1",
        content=CONTENT,
        media_type="image/jpeg",
        submitted_by="claims@insurer.example",
        mark_text=mark_text,
        claimed_brand=BRAND,
    )
    pipeline = VerificationPipeline(
        checks=default_checks(resolver, store, registrations, TODAY), store=store
    )
    decision = pipeline.run(request)
    context = VerificationContext(
        run_id=request.run_id,
        content=request.content,
        media_type=request.media_type,
        submitted_by=request.submitted_by,
        mark=decoded(mark_text),
        claimed_brand=request.claimed_brand,
    )
    bundle = Bundle.from_run(
        context=context,
        decision=decision,
        recorded_at=RECORDED_AT,
        observations=observed(resolver, registrations),
    )
    return decision, bundle


def test_a_certified_run_replays_to_the_same_verdict_and_reason(world: World) -> None:
    _, _, _, private = world
    decision, bundle = run_and_capture(world, mark_for(private, FIELDS))
    assert decision.verdict is Verdict.CERTIFIED

    replayed = replay(read(write(bundle)))

    assert replayed.verdict is decision.verdict
    assert replayed.reason == decision.reason
    assert replayed.signals == decision.signals


def test_a_flagged_run_replays_to_the_same_verdict_and_reason(world: World) -> None:
    _, _, _, private = world
    tampered = mark_for(private, FIELDS).replace("amt=14.75", "amt=1475.00")
    decision, bundle = run_and_capture(world, tampered)
    assert decision.verdict is Verdict.FLAGGED

    replayed = replay(read(write(bundle)))

    assert replayed.verdict is decision.verdict
    assert replayed.reason == decision.reason
    assert replayed.signals == decision.signals


def test_an_unsigned_run_replays_to_the_same_verdict_and_reason(world: World) -> None:
    decision, bundle = run_and_capture(world, None)
    assert decision.verdict is Verdict.UNSIGNED

    replayed = replay(read(write(bundle)))

    assert replayed.verdict is decision.verdict
    assert replayed.reason == decision.reason


def test_an_archive_read_from_disk_replays_without_the_run_that_made_it(
    world: World, tmp_path: Path
) -> None:
    _, store, _, private = world
    decision, bundle = run_and_capture(world, mark_for(private, FIELDS))
    archive = tmp_path / "run-1.evidence.json"
    archive.write_text(write(bundle), encoding="utf-8")

    audited = len(store.audit)
    replayed = replay(read(archive.read_text(encoding="utf-8")))

    assert replayed.verdict is decision.verdict
    assert replayed.reason == decision.reason
    # Nothing was consulted a second time, so nothing new was recorded.
    assert len(store.audit) == audited


def test_two_archives_of_one_run_are_byte_identical(world: World) -> None:
    _, _, _, private = world
    _, bundle = run_and_capture(world, mark_for(private, FIELDS))
    assert write(bundle).encode("utf-8") == write(read(write(bundle))).encode("utf-8")


def test_replaying_twice_returns_the_same_decision(world: World) -> None:
    _, _, _, private = world
    _, bundle = run_and_capture(world, mark_for(private, FIELDS))
    archived = read(write(bundle))
    assert replay(archived) == replay(archived)


def test_an_archived_verdict_matches_the_verdict_it_recorded(world: World) -> None:
    """A bundle whose stored verdict disagreed with its signals would be worthless."""
    _, _, _, private = world
    for mark_text in (mark_for(private, FIELDS), None):
        _, bundle = run_and_capture(world, mark_text)
        replayed = replay(read(write(bundle)))
        assert replayed.verdict is bundle.verdict
        assert replayed.reason == bundle.reason
