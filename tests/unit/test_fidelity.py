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
    extractor = FakeDocumentExtractor.reading(iban=("GB29NWBK60161331926819", 0.99))
    signal = FidelityCheck(extractor).run(context_with_mark())
    assert signal.outcome is Outcome.PASS


def test_presentation_differences_are_not_discrepancies() -> None:
    """A rendered IBAN carries spaces. That is not a doctored document."""
    extractor = FakeDocumentExtractor.reading(iban=("GB29 NWBK 6016 1331 9268 19", 0.99))
    assert FidelityCheck(extractor).run(context_with_mark()).outcome is Outcome.PASS


def test_a_doctored_account_number_fails_despite_a_valid_signature() -> None:
    extractor = FakeDocumentExtractor.reading(iban=("GB94BARC10201530093459", 0.99))
    signal = FidelityCheck(extractor).run(context_with_mark())
    assert signal.outcome is Outcome.FAIL
    assert "GB94BARC" in signal.detail


def test_low_confidence_routes_to_a_human_rather_than_accusing() -> None:
    extractor = FakeDocumentExtractor.reading(iban=("GB94BARC10201530093459", 0.40))
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


def test_a_mismatch_on_an_illegible_page_is_a_question_not_an_accusation() -> None:
    """Measured against a photographed copy of a genuine invoice: the account
    number came back at 0.40 and, on the same page, an invented bank code at
    0.95. Trusting the second score would have flagged an authentic document."""
    extractor = FakeDocumentExtractor.reading(iban=("", 0.40), amt=("9999.00", 0.95))
    signal = FidelityCheck(extractor).run(context_with_mark())

    assert signal.outcome is Outcome.UNKNOWN
    assert "iban" in signal.detail
    assert signal.evidence["apparentMismatch"]["field"] == "amt"


def test_a_confident_score_on_an_impossible_value_does_not_accuse_anyone() -> None:
    """The same photograph returned an amount of 15.s80.00 and scored it 0.95.
    A letter inside a number is not a 95 percent reading of anything, and the
    document it came from was authentic."""
    extractor = FakeDocumentExtractor.reading(amt=("15.s80.00", 0.95))
    signal = FidelityCheck(extractor).run(context_with_mark())

    assert signal.outcome is Outcome.UNKNOWN
    assert signal.evidence["malformed"] == ["amt"]


def test_presentation_is_not_a_malformed_value() -> None:
    """An extractor returning grouped digits is reading the page correctly, and
    a rule that called that illegible would route every clean page to a human."""
    extractor = FakeDocumentExtractor.reading(
        amt=("14.75", 0.95), iban=("GB29 NWBK 6016 1331 9268 19", 0.95)
    )
    assert FidelityCheck(extractor).run(context_with_mark()).outcome is Outcome.PASS


def test_a_mismatch_on_a_page_read_cleanly_is_still_a_finding() -> None:
    """The rule above must not become a way to launder a doctored page by
    degrading it. Every field here read confidently."""
    extractor = FakeDocumentExtractor.reading(
        iban=("GB94BARC10201530093459", 0.96), amt=("14.75", 0.97)
    )
    assert FidelityCheck(extractor).run(context_with_mark()).outcome is Outcome.FAIL
