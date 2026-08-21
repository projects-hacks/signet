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

from collections.abc import Mapping

from signet.core.verdict import Outcome, Signal
from signet.errors import AdapterError
from signet.ports.documents import DocumentExtractor
from signet.verify.context import VerificationContext

NAME = "fidelity"

REVIEW_THRESHOLD = 0.80

# Payload field to the extractor's own type vocabulary. Nutrient classifies these
# natively, so a money field is found by type rather than by hunting for a label.
TYPED_FIELDS: Mapping[str, str] = {
    "iban": "IBAN",
    "bic": "BIC",
    "amt": "Currency",
}


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
        uncertain: list[str] = []

        for field_name, data_type in TYPED_FIELDS.items():
            expected = signed.get(field_name)
            if expected is None:
                continue
            found = extraction.of_type(data_type)
            if not found:
                continue

            confident = [item for item in found if item.confidence >= self._threshold]
            if not confident:
                uncertain.append(field_name)
                continue
            if not any(_comparable(item.value) == _comparable(expected) for item in confident):
                shown = confident[0].value
                return Signal(
                    NAME,
                    Outcome.FAIL,
                    f"The page shows {shown} where the signature covers {expected}.",
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
