from __future__ import annotations

from collections.abc import Mapping

from signet.ports.documents import ExtractedField, Extraction


class FakeDocumentExtractor:
    def __init__(self, extraction: Extraction | None = None) -> None:
        self.extraction = extraction or Extraction(fields=(), marks=())

    def extract(self, content: bytes, media_type: str) -> Extraction:
        return self.extraction

    @staticmethod
    def with_fields(marks: tuple[str, ...], **values: str) -> FakeDocumentExtractor:
        fields = tuple(
            ExtractedField(name=name, value=value, confidence=0.99, page=1, box=(0, 0, 1, 1))
            for name, value in values.items()
        )
        return FakeDocumentExtractor(Extraction(fields=fields, marks=marks))


class FakeDocumentRenderer:
    def __init__(self) -> None:
        self.rendered: list[tuple[str, Mapping[str, str], str, str]] = []

    def render(
        self, document_class: str, fields: Mapping[str, str], mark: str, locator: str
    ) -> bytes:
        self.rendered.append((document_class, dict(fields), mark, locator))
        return f"{document_class}\n{mark}\n{locator}".encode()
