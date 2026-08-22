"""Domain age: context about the issuer, never an accusation on its own."""

from __future__ import annotations

from datetime import date

import pytest

from signet.core.mark import decode_mark, encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, generate_key
from signet.core.verdict import Outcome, decide
from signet.ports.registry import Registration
from signet.verify.checks.domain_age import DomainAgeCheck
from signet.verify.context import VerificationContext
from tests.fakes import FakeRegistrationData

TODAY = date(2026, 9, 3)


def context(issuer: str = "northpost.dev") -> VerificationContext:
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
        claimed_brand="Northpost",
    )


def registered_on(created: date | None) -> FakeRegistrationData:
    return FakeRegistrationData(
        {
            "northpost.dev": Registration(
                domain="northpost.dev",
                created=created,
                expires=date(2027, 8, 22),
                registrar="Name.com",
                locked=True,
            )
        }
    )


def run(created: date | None) -> Outcome:
    return DomainAgeCheck(registered_on(created), TODAY).run(context()).outcome


def test_an_established_domain_passes() -> None:
    assert run(date(2015, 4, 1)) is Outcome.PASS


def test_a_young_domain_is_uncertain_rather_than_failed() -> None:
    """A business that registered its domain last month is not a fraud."""
    assert run(date(2026, 8, 22)) is Outcome.UNKNOWN


def test_a_domain_registered_today_still_does_not_fail() -> None:
    assert run(TODAY) is Outcome.UNKNOWN


def test_a_missing_registration_date_is_uncertain() -> None:
    assert run(None) is Outcome.UNKNOWN


@pytest.mark.parametrize("created", [date(2026, 8, 22), TODAY, None])
def test_age_alone_never_flags_a_document(created: date | None) -> None:
    """The verdict engine flags on any failure, so this check must not fail alone."""
    signals = [
        DomainAgeCheck(registered_on(created), TODAY).run(context()),
    ]
    assert decide(signals).verdict.name != "FLAGGED"


def test_the_detail_names_the_age_so_a_reader_can_judge() -> None:
    signal = DomainAgeCheck(registered_on(date(2026, 8, 22)), TODAY).run(context())
    assert "12 days ago" in signal.detail
