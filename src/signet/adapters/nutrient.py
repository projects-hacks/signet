"""Nutrient DWS Processor API.

Written against their OpenAPI 3.1 spec, version 1.18.0.

One endpoint does the work. POST /build takes a declarative instructions object
and returns either a document or, with a json-content output, the document's
contents. Extraction is not a separate endpoint; asking for keyValuePairs on a
build is the extraction.

Their key-value pairs carry a dataType, and the vocabulary happens to be exactly
ours: IBAN, BIC, Currency, CreditCard, SSN, PostalAddress. A fidelity check can
therefore ask for the IBAN the page actually shows rather than pattern matching
text, and get a confidence score with it.

Confidence arrives as 0 to 100 and is normalised to 0.0 to 1.0 at this boundary,
so no check has to remember which scale it is on.
"""

from __future__ import annotations

import json
from typing import Any, Final

import httpx

from signet.errors import AdapterError
from signet.ports.documents import BoundingBox, ExtractedField, Extraction

BASE_URL: Final = "https://api.nutrient.io"
_TIMEOUT_SECONDS: Final = 120.0
_CONFIDENCE_SCALE: Final = 100.0

# The key text Nutrient uses when a detected value has no label of its own.
_UNLABELLED: Final = "#"


def _box(raw: Any) -> BoundingBox | None:
    if not isinstance(raw, dict):
        return None
    try:
        return BoundingBox(
            left=float(raw["left"]),
            top=float(raw["top"]),
            width=float(raw["width"]),
            height=float(raw["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


class NutrientClient:
    def __init__(
        self, api_key: str, base_url: str = BASE_URL, client: httpx.Client | None = None
    ) -> None:
        if not api_key:
            raise ValueError("Nutrient requires an API key")
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.post(f"{self._base_url}{path}", headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Nutrient POST {path} failed: {exc}") from exc
        if response.status_code == 401:
            raise AdapterError("Nutrient rejected the API key.")
        if not response.is_success:
            raise AdapterError(
                f"Nutrient POST {path} returned {response.status_code}: {response.text[:200]}"
            )
        return response


class NutrientExtractor:
    """Implements DocumentExtractor via a json-content build."""

    def __init__(self, client: NutrientClient, language: str = "english") -> None:
        self._client = client
        self._language = language

    def extract(self, content: bytes, media_type: str) -> Extraction:
        instructions = {
            "parts": [{"file": "document"}],
            "output": {
                "type": "json-content",
                "plainText": False,
                "structuredText": False,
                "keyValuePairs": True,
                "tables": False,
                "language": self._language,
            },
        }
        response = self._client.post(
            "/build",
            files={"document": ("document", content, media_type)},
            data={"instructions": json.dumps(instructions)},
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError(
                "Nutrient returned a non-JSON body for a json-content build"
            ) from exc
        return Extraction(fields=tuple(self._fields(body)))

    def _fields(self, body: dict[str, Any]) -> list[ExtractedField]:
        fields: list[ExtractedField] = []
        for page in body.get("pages", []) or []:
            if not isinstance(page, dict):
                continue
            index = page.get("pageIndex")
            page_number = int(index) if isinstance(index, int) else 0
            for pair in page.get("keyValuePairs", []) or []:
                field = self._field(pair, page_number)
                if field is not None:
                    fields.append(field)
        return fields

    def _field(self, pair: Any, page: int) -> ExtractedField | None:
        if not isinstance(pair, dict):
            return None
        key, value = pair.get("key"), pair.get("value")
        if not isinstance(key, dict) or not isinstance(value, dict):
            return None
        label = str(key.get("content", ""))
        return ExtractedField(
            # An unlabelled value is still worth keeping when it is a typed one:
            # an IBAN with no caption beside it is exactly what we look for.
            name=str(value.get("dataType", "")) if label == _UNLABELLED else label,
            value=str(value.get("content", "")),
            confidence=float(pair.get("confidence", 0.0)) / _CONFIDENCE_SCALE,
            page=page,
            data_type=value.get("dataType") if isinstance(value.get("dataType"), str) else None,
            box=_box(value.get("bbox")),
        )


class NutrientRedactor:
    """Implements DocumentRedactor via AI redaction."""

    def __init__(self, client: NutrientClient) -> None:
        self._client = client

    def redact(self, content: bytes, criteria: str) -> bytes:
        payload = {"documents": [{"file": "document"}], "criteria": criteria}
        response = self._client.post(
            "/ai/redact",
            files={"document": ("document", content, "application/pdf")},
            data={"data": json.dumps(payload)},
        )
        return response.content


def viewer_token(
    client: NutrientClient, operations: tuple[str, ...], expires_in: int, origin: str | None = None
) -> str:
    """Mint a scoped, expiring token for the browser.

    The Viewer runs client side, so it must never see the API key. A token
    restricted to the operations it needs, to one origin, and to a short life is
    revocable in a way the key is not.
    """
    body: dict[str, Any] = {"allowedOperations": list(operations), "expirationTime": expires_in}
    if origin:
        body["allowedOrigins"] = [origin]
    data = client.post("/tokens", json=body).json()
    token = data.get("jwt") or data.get("token") or data.get("accessToken")
    if not isinstance(token, str):
        raise AdapterError(f"Nutrient token response had no token field: {str(data)[:200]}")
    return token
