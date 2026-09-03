"""Nutrient DWS Data Extraction API.

Written against their API overview and extract guide, and confirmed against the
live service rather than inferred.

Two products share the api.nutrient.io host and they are not interchangeable.
The Processor API endpoints answer 403 to a Data Extraction key, which is what a
key that is valid but unentitled looks like: an unknown key gets 401, so a 403
is the service saying the credential is real and the account is not entitled.
Everything here is Data Extraction only.

Extraction is schema driven, which inverts the usual arrangement. Rather than
accept whatever pairs a vendor happens to detect and hope its label vocabulary
matches ours, we hand Nutrient the field names the signature covers and it
returns those names with a citation each. The fidelity check then compares like
for like, and nothing in Signet depends on a vendor's idea of what an IBAN is
called.

Every field is requested as a string so the printed form survives. Asking for a
number turns 1240.00 into 1240, and the comparison against the signed 1240.00
then fails on presentation rather than on content.

A field the page does not carry is omitted from data while still appearing under
metadata with nulls throughout, so data is what decides whether we found
something. Confidence is already on 0.0 to 1.0 here, so nothing is rescaled.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from io import BytesIO
from typing import Any, Final

import httpx
import pypdfium2
from PIL import Image

from signet.adapters import http
from signet.errors import AdapterError
from signet.ports.documents import BoundingBox, ExtractedField, Extraction

BASE_URL: Final = "https://api.nutrient.io"
_TIMEOUT_SECONDS: Final = 120.0

# understand runs layout analysis before the schema is applied, which is what
# produces a per field citation rather than a value with no provenance.
_PARSE_MODE: Final = "understand"

# Signet field name to the description Nutrient is given. Only fields that appear
# on the page belong here; iss, ts and cls are envelope metadata and are never
# printed, so there would be nothing to compare them against.
EXTRACTION_SCHEMA: Final[Mapping[str, str]] = {
    "id": "The invoice or document identifier printed on the page, exactly as shown",
    "amt": "The total amount payable, digits exactly as printed, without a currency symbol",
    "cur": "The ISO 4217 currency code",
    "iban": "The IBAN of the account to be paid",
    "bic": "The BIC or SWIFT code of the receiving bank",
}

# Observed: Nutrient renders a PDF at this density before reading it, and
# reports boxes in the resulting pixels.
PDF_RENDER_DPI: Final = 200.0
POINTS_PER_INCH: Final = 72.0


def _page_size(content: bytes, media_type: str) -> tuple[float, float] | None:
    """The first page, in the same units Nutrient reports boxes in.

    Nutrient reports a raster page in pixels and a PDF in points, so each is
    measured with the reader that speaks its units. Only the first page is
    measured, because only the first page is ever shown: pages within one PDF
    may differ in size, and scaling a later page by this one would point
    confidently at the wrong part of the document.
    """
    if media_type.startswith("image/"):
        try:
            with Image.open(BytesIO(content)) as page:
                return float(page.width), float(page.height)
        except (OSError, ValueError):
            return None
    if media_type == "application/pdf":
        try:
            width, height = pypdfium2.PdfDocument(content)[0].get_size()
        except Exception:  # pypdfium2 raises its own hierarchy
            return None
        # A PDF measures in points, but Nutrient rasterises one before reading
        # it and reports boxes in the pixels of that render, so the page has to
        # be given in the same pixels. The scale is observed rather than
        # documented, which is why _box refuses anything landing off the page.
        scale = PDF_RENDER_DPI / POINTS_PER_INCH
        return float(width) * scale, float(height) * scale
    return None


def _box(raw: Any, page: tuple[float, float] | None, index: int) -> BoundingBox | None:
    """A box only for the page the reader is looking at.

    Boxes are drawn over the rendered first page, so a box carrying any other
    page index has nothing to sit on and is dropped rather than misplaced.
    """
    if not isinstance(raw, dict) or page is None or index != 0:
        return None
    width, height = page
    if width <= 0 or height <= 0:
        return None
    try:
        box = BoundingBox(
            left=float(raw["x"]) / width,
            top=float(raw["y"]) / height,
            width=float(raw["width"]) / width,
            height=float(raw["height"]) / height,
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    # A box off the page means the units were not what we measured the page in.
    # Drop it: an absent highlight costs a reviewer a glance, a misplaced one
    # points confidently at the wrong line.
    if box.left < 0 or box.top < 0 or box.left + box.width > 1 or box.top + box.height > 1:
        return None
    return box


def _confidence(raw: Any) -> float:
    """Absent confidence is treated as no confidence, which routes to a human."""
    return float(raw) if isinstance(raw, int | float) else 0.0


class NutrientClient:
    def __init__(
        self, api_key: str, base_url: str = BASE_URL, client: httpx.Client | None = None
    ) -> None:
        if not api_key:
            raise ValueError("Nutrient requires an API key")
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or http.client(_TIMEOUT_SECONDS)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.post(f"{self._base_url}{path}", headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Nutrient POST {path} failed: {exc}") from exc
        if response.status_code == 401:
            raise AdapterError("Nutrient did not recognise the API key.")
        if response.status_code == 403:
            raise AdapterError(
                f"Nutrient accepted the key but not for {path}. A 403 rather than a 401 means "
                "the key is valid and the account is not entitled to the product serving that "
                "path, so check the key came from the Data Extraction dashboard."
            )
        if not response.is_success:
            raise AdapterError(
                f"Nutrient POST {path} returned {response.status_code}: {response.text[:200]}"
            )
        return response


class NutrientExtractor:
    """Implements DocumentExtractor against POST /extraction/extract."""

    def __init__(
        self,
        client: NutrientClient,
        schema: Mapping[str, str] = EXTRACTION_SCHEMA,
        parse_mode: str = _PARSE_MODE,
    ) -> None:
        self._client = client
        self._schema = dict(schema)
        self._parse_mode = parse_mode

    def extract(self, content: bytes, media_type: str) -> Extraction:
        instructions = {
            "schema": {
                "type": "object",
                "properties": {
                    name: {"type": "string", "description": description}
                    for name, description in self._schema.items()
                },
            },
            "parseConfig": {"mode": self._parse_mode},
            "options": {"includeCitations": True},
        }
        response = self._client.post(
            "/extraction/extract",
            files={"file": ("document", content, media_type)},
            data={"instructions": json.dumps(instructions)},
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError("Nutrient returned a non-JSON extraction body") from exc
        output = body.get("output")
        if not isinstance(output, dict):
            raise AdapterError(f"unexpected Nutrient extraction shape: {str(body)[:200]}")
        return Extraction(fields=tuple(self._fields(output, _page_size(content, media_type))))

    def _fields(
        self, output: Mapping[str, Any], page_size: tuple[float, float] | None
    ) -> list[ExtractedField]:
        data = output.get("data")
        if not isinstance(data, dict):
            return []
        raw_metadata = output.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}

        fields: list[ExtractedField] = []
        for name, value in data.items():
            if value is None:
                continue
            citation = metadata.get(name)
            citation = citation if isinstance(citation, dict) else {}
            index = citation.get("pageIndex")
            page = index if isinstance(index, int) else 0
            fields.append(
                ExtractedField(
                    name=str(name),
                    value=str(value),
                    confidence=_confidence(citation.get("confidence")),
                    page=page,
                    box=_box(citation.get("bbox"), page_size, page),
                )
            )
        return fields
