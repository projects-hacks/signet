"""Fidelity: the attack the signature alone cannot see."""

from __future__ import annotations

from signet.core.mark import decode_mark, encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, generate_key
from signet.core.verdict import Outcome
from signet.verify.checks.fidelity import FidelityCheck
from signet.verify.context import VerificationContext
from tests.fakes import FakeDocumentExtractor

FIELDS = {
    "iss": "bluebottle.com",
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-1",
    "cls": "receipt",
    "iban": "GB29NWBK60161331926819",
    "amt": "14.75",
}


def context_with_mark() -> VerificationContext:
    private, _ = generate_key()
    payload = canonicalize(FIELDS)
    mark = decode_mark(encode_mark(payload, Ed25519Signer(private).sign(payload)))
    return VerificationContext(
        run_id="r",
        content=b"image",
        media_type="image/jpeg",
        submitted_by="tester",
        mark=mark,
        claimed_brand="Blue Bottle Coffee",
    )


def test_a_matching_page_passes() -> None:
    extractor = FakeDocumentExtractor.typed(iban=("GB29NWBK60161331926819", "IBAN", 0.99))
    signal = FidelityCheck(extractor).run(context_with_mark())
    assert signal.outcome is Outcome.PASS


def test_presentation_differences_are_not_discrepancies() -> None:
    """A rendered IBAN carries spaces. That is not a doctored document."""
    extractor = FakeDocumentExtractor.typed(iban=("GB29 NWBK 6016 1331 9268 19", "IBAN", 0.99))
    assert FidelityCheck(extractor).run(context_with_mark()).outcome is Outcome.PASS


def test_a_doctored_account_number_fails_despite_a_valid_signature() -> None:
    extractor = FakeDocumentExtractor.typed(iban=("GB94BARC10201530093459", "IBAN", 0.99))
    signal = FidelityCheck(extractor).run(context_with_mark())
    assert signal.outcome is Outcome.FAIL
    assert "GB94BARC" in signal.detail


def test_low_confidence_routes_to_a_human_rather_than_accusing() -> None:
    extractor = FakeDocumentExtractor.typed(iban=("GB94BARC10201530093459", "IBAN", 0.40))
    signal = FidelityCheck(extractor).run(context_with_mark())
    assert signal.outcome is Outcome.UNKNOWN
    assert "Needs a human" in signal.detail


def test_a_field_absent_from_the_page_is_not_a_discrepancy() -> None:
    assert FidelityCheck(FakeDocumentExtractor()).run(context_with_mark()).outcome is Outcome.PASS


def test_an_unmarked_document_has_nothing_to_compare() -> None:
    context = VerificationContext(
        run_id="r",
        content=b"x",
        media_type="image/jpeg",
        submitted_by="t",
        mark=None,
        claimed_brand=None,
    )
    assert FidelityCheck(FakeDocumentExtractor()).run(context).outcome is Outcome.UNKNOWN
