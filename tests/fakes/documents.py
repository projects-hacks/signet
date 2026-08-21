from __future__ import annotations

from collections.abc import Mapping

from signet.ports.documents import BoundingBox, ExtractedField, Extraction


class FakeDocumentExtractor:
    def __init__(self, extraction: Extraction | None = None) -> None:
        self.extraction = extraction or Extraction(fields=())

    def extract(self, content: bytes, media_type: str) -> Extraction:
        return self.extraction

    @staticmethod
    def typed(**values: tuple[str, str, float]) -> FakeDocumentExtractor:
        """Build an extraction from name -> (value, data_type, confidence)."""
        fields = tuple(
            ExtractedField(
                name=name,
                value=value,
                confidence=confidence,
                page=0,
                data_type=data_type,
                box=BoundingBox(0.0, 0.0, 1.0, 1.0),
            )
            for name, (value, data_type, confidence) in values.items()
        )
        return FakeDocumentExtractor(Extraction(fields=fields))


class FakeMarkReader:
    def __init__(self, marks: tuple[str, ...] = ()) -> None:
        self.marks = marks

    def read_marks(self, content: bytes, media_type: str) -> tuple[str, ...]:
        return self.marks


class FakeDocumentRenderer:
    def __init__(self) -> None:
        self.rendered: list[tuple[str, Mapping[str, str], str, str]] = []

    def render(
        self, document_class: str, fields: Mapping[str, str], mark: str, locator: str
    ) -> bytes:
        self.rendered.append((document_class, dict(fields), mark, locator))
        return f"{document_class}\n{mark}\n{locator}".encode()
