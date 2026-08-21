"""Reading documents and producing them.

Extraction never gates a certified verdict: the mark carries everything the
signature check needs, so a document that extracts badly still verifies. These
feed the fidelity check and the unsigned path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExtractedField:
    """One value with the evidence behind it.

    The box drives the reviewer straight to the disputed region, so a human
    adjudicates one number instead of reading a whole document.
    """

    name: str
    value: str
    confidence: float
    page: int
    box: tuple[float, float, float, float] | None


@dataclass(frozen=True, slots=True)
class Extraction:
    fields: tuple[ExtractedField, ...]
    marks: tuple[str, ...]

    def by_name(self) -> Mapping[str, ExtractedField]:
        return {field.name: field for field in self.fields}


class DocumentExtractor(Protocol):
    def extract(self, content: bytes, media_type: str) -> Extraction: ...


class DocumentRenderer(Protocol):
    def render(
        self, document_class: str, fields: Mapping[str, str], mark: str, locator: str
    ) -> bytes: ...
