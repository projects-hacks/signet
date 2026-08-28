"""Does the paper say what the signature says?

This is the check that catches the attack layer one cannot see: take a genuinely
signed document, keep its mark intact, and doctor the visible amount or account
number. The signature still verifies, because the signature covers the mark, not
the render. Only comparing the two catches it.

Comparison is deliberately lenient about presentation and strict about content.
A rendered IBAN carries spaces, a rendered amount carries a thousands separator,
and neither is a discrepancy. A different account number is.

Low confidence is not a failure. A field the extractor was unsure about becomes
unknown, which routes it to a human rather than accusing anyone.

Neither is a mismatch, on a page that could not be read cleanly. Measured
against a photographed copy of a genuine invoice, extraction returned the
account number at 0.40 confidence and, on the same page, a completely invented
bank code at 0.95. Trusting the second score would have flagged an authentic
document, which is the false accusation this whole product exists to avoid.

The score alone does not settle legibility either. The same photograph returned
an amount of "15.s80.00" and scored it 0.95. A letter inside a number is not a
95 percent reading of anything, so the shape of a value is checked as well as
its score, and a value that cannot be what it claims to be counts as doubtful
however confidently it was offered.

So a discrepancy only counts when the page it was read from was read cleanly. If
any field on the page was doubtful, the conditions that made it doubtful make
every reading on that page suspect, and the apparent mismatch is reported as a
question rather than a finding. That is what the adjudication path is for.
"""

from __future__ import annotations

from typing import Final

from signet.core.shape import well_formed
from signet.core.verdict import Outcome, Signal
from signet.errors import AdapterError
from signet.ports.documents import DocumentExtractor
from signet.verify.context import VerificationContext

NAME = "fidelity"

REVIEW_THRESHOLD = 0.80

# The printed, payment critical fields. We name them to the extractor rather than
# accept a vendor's own labels, so both sides of the comparison use one vocabulary.
# iss, ts and cls are envelope metadata and never appear on the page.
COMPARED_FIELDS: Final = ("id", "amt", "cur", "iban", "bic")


def comparable(value: str) -> str:
    """Strip presentation, keep content."""
    return "".join(ch for ch in value if ch.isalnum()).casefold()


class FidelityCheck:
    name = NAME

    def __init__(self, extractor: DocumentExtractor, threshold: float = REVIEW_THRESHOLD) -> None:
        self._extractor = extractor
        self._threshold = threshold

    def run(self, context: VerificationContext) -> Signal:
        if context.mark is None:
            return Signal(NAME, Outcome.UNKNOWN, "No mark to compare the page against.", "signet")

        try:
            extraction = self._extractor.extract(context.content, context.media_type)
        except AdapterError as exc:
            return Signal(NAME, Outcome.UNKNOWN, "Could not read the document.", str(exc))

        signed = context.mark.payload.fields
        printed = extraction.by_name()
        uncertain: list[str] = []
        malformed: list[str] = []
        # Every field compared, kept whether or not it disagreed, because a
        # reader deciding whether to trust the verdict needs to see what was
        # looked at rather than only what was found wanting.
        compared: list[dict[str, object]] = []
        mismatched: list[tuple[str, str, str]] = []

        for field_name in COMPARED_FIELDS:
            expected = signed.get(field_name)
            if expected is None:
                continue
            found = printed.get(field_name)
            # A signed field the page does not carry is not a discrepancy.
            if found is None:
                compared.append({"field": field_name, "signed": expected, "printed": None})
                continue

            compared.append(
                {
                    "field": field_name,
                    "signed": expected,
                    "printed": found.value,
                    "confidence": found.confidence,
                    "page": found.page,
                    "box": None
                    if found.box is None
                    else {
                        "left": found.box.left,
                        "top": found.box.top,
                        "width": found.box.width,
                        "height": found.box.height,
                    },
                    "agrees": comparable(found.value) == comparable(expected),
                }
            )

            if found.confidence < self._threshold:
                uncertain.append(field_name)
                continue
            if not well_formed(field_name, found.value):
                # Confidently offered, and not a value this field can hold.
                uncertain.append(field_name)
                malformed.append(field_name)
                continue
            if comparable(found.value) != comparable(expected):
                mismatched.append((field_name, found.value, expected))

        evidence: dict[str, object] = {"threshold": self._threshold, "compared": compared}
        if malformed:
            evidence["malformed"] = malformed

        # Every field read cleanly, and one of them disagrees. That is a finding.
        if mismatched and not uncertain:
            field_name, printed_value, expected = mismatched[0]
            return Signal(
                NAME,
                Outcome.FAIL,
                f"The page shows {printed_value} where the signature covers {expected}.",
                "extraction",
                evidence,
            )

        if uncertain:
            evidence["uncertain"] = uncertain
            if mismatched:
                # The page is not legible enough to accuse anyone with, so the
                # apparent discrepancy is named and put to a person.
                field_name, printed_value, expected = mismatched[0]
                evidence["apparentMismatch"] = {
                    "field": field_name,
                    "printed": printed_value,
                    "signed": expected,
                }
                return Signal(
                    NAME,
                    Outcome.UNKNOWN,
                    f"Needs a human: {', '.join(uncertain)} could not be read reliably, "
                    f"and {field_name} reads as {printed_value} against a signed "
                    f"{expected}. A page this hard to read cannot settle either.",
                    "extraction",
                    evidence,
                )
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"Needs a human: {', '.join(uncertain)} could not be read reliably.",
                "extraction",
                evidence,
            )
        return Signal(
            NAME, Outcome.PASS, "The page matches what was signed.", "extraction", evidence
        )
