"""Reading documents and producing them.

Extraction never gates a certified verdict. The mark carries everything the
signature check needs, so a document that extracts badly still verifies.
Extraction feeds the fidelity check, which asks whether the paper says what the
signature says, and the unsigned path, where confidence decides who reviews it.

Mark reading is a separate port because it is a separate problem. Nutrient's
extraction has no barcode option, so the code has to be decoded locally.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Where on the page a value was read, as a fraction of the page, 0 to 1.

    Fractions rather than the extractor's own units, which are page pixels for
    an image and points for a PDF and documented as neither. A reviewer's screen
    is a third size again, so anything absolute has to be converted by whoever
    draws it, and a caller that guesses the unit draws a box across the whole
    window. The conversion belongs once, in the adapter that knows the document.
    """

    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class ExtractedField:
    """One value with the evidence behind it.

    name is ours, not the extractor's. We hand the extractor the field names the
    signature covers and it answers in those names, so both sides of a fidelity
    comparison speak one vocabulary and no vendor's labelling can drift from it.

    confidence is normalised to 0.0 to 1.0 here. Nutrient reports 0 to 100, and
    a check comparing against 0.8 should not have to know that.

    box drives the reviewer straight to the disputed region, so a human
    adjudicates one number instead of reading a whole document.
    """

    name: str
    value: str
    confidence: float
    page: int
    box: BoundingBox | None = None


@dataclass(frozen=True, slots=True)
class Extraction:
    fields: tuple[ExtractedField, ...]

    def by_name(self) -> Mapping[str, ExtractedField]:
        return {field.name: field for field in self.fields}


class DocumentExtractor(Protocol):
    def extract(self, content: bytes, media_type: str) -> Extraction: ...


class MarkReader(Protocol):
    def read_marks(self, content: bytes, media_type: str) -> tuple[str, ...]: ...


class DocumentRenderer(Protocol):
    def render(
        self, document_class: str, record: Mapping[str, object], mark: str, locator: str
    ) -> bytes: ...

    """Produce the document a reader will hold, carrying the mark.

    record is arbitrary structured data, not flat strings, because a real
    document has line items and a template that can loop over them is the
    difference between a document system and a mail merge. The signature still
    covers only the payment critical fields; the rest is what makes the page
    worth reading.
    """
