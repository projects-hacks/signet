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
"""

from __future__ import annotations

from typing import Final

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


def _comparable(value: str) -> str:
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

        for field_name in COMPARED_FIELDS:
            expected = signed.get(field_name)
            if expected is None:
                continue
            found = printed.get(field_name)
            # A signed field the page does not carry is not a discrepancy.
            if found is None:
                continue

            if found.confidence < self._threshold:
                uncertain.append(field_name)
                continue
            if _comparable(found.value) != _comparable(expected):
                return Signal(
                    NAME,
                    Outcome.FAIL,
                    f"The page shows {found.value} where the signature covers {expected}.",
                    "extraction",
                )

        if uncertain:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"Needs a human: {', '.join(uncertain)} could not be read confidently.",
                "extraction",
            )
        return Signal(NAME, Outcome.PASS, "The page matches what was signed.", "extraction")
