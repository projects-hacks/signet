"""Nutrient, against the shapes its OpenAPI 3.1 spec declares (version 1.18.0)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from signet.adapters.nutrient import (
    NutrientClient,
    NutrientExtractor,
    NutrientRedactor,
    viewer_token,
)
from signet.errors import AdapterError


def kvp(key: str, value: str, data_type: str, confidence: float) -> dict[str, Any]:
    box = {"left": 1.0, "top": 2.0, "width": 3.0, "height": 4.0}
    return {
        "confidence": confidence,
        "key": {"content": key, "bbox": box},
        "value": {"content": value, "dataType": data_type, "bbox": box},
    }


def client(handler: Any) -> NutrientClient:
    return NutrientClient("key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_extraction_normalises_confidence_to_a_fraction() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pages": [
                    {"pageIndex": 0, "keyValuePairs": [kvp("IBAN", "GB29 NWBK", "IBAN", 95.4)]}
                ]
            },
        )

    field = client(handler) and NutrientExtractor(client(handler)).extract(
        b"pdf", "application/pdf"
    )
    assert field.fields[0].confidence == pytest.approx(0.954)
    assert field.fields[0].data_type == "IBAN"


def test_the_build_asks_for_key_value_pairs() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode(errors="ignore")
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"pages": []})

    NutrientExtractor(client(handler)).extract(b"pdf", "application/pdf")

    assert "json-content" in seen["body"]
    assert '"keyValuePairs": true' in seen["body"]
    assert seen["auth"] == "Bearer key"


def test_an_unlabelled_value_is_named_by_its_type() -> None:
    """An IBAN with no caption beside it is exactly what we look for."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pages": [{"pageIndex": 0, "keyValuePairs": [kvp("#", "GB29NWBK", "IBAN", 90.0)]}]
            },
        )

    extraction = NutrientExtractor(client(handler)).extract(b"pdf", "application/pdf")
    assert extraction.fields[0].name == "IBAN"
    assert extraction.of_type("IBAN")[0].value == "GB29NWBK"


def test_bounding_boxes_survive_so_a_reviewer_can_be_pointed_at_the_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pages": [
                    {"pageIndex": 2, "keyValuePairs": [kvp("Total", "14.75", "Currency", 99.0)]}
                ]
            },
        )

    field = NutrientExtractor(client(handler)).extract(b"pdf", "application/pdf").fields[0]
    assert field.page == 2
    assert field.box is not None
    assert (field.box.left, field.box.height) == (1.0, 4.0)


def test_malformed_pairs_are_skipped_rather_than_crashing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"pages": [{"pageIndex": 0, "keyValuePairs": ["nonsense", {"key": "wrong"}]}]},
        )

    assert NutrientExtractor(client(handler)).extract(b"pdf", "application/pdf").fields == ()


def test_a_rejected_key_says_so() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"details": "Unauthorized"}})

    with pytest.raises(AdapterError, match="rejected the API key"):
        NutrientExtractor(client(handler)).extract(b"pdf", "application/pdf")


def test_redaction_returns_the_cleaned_document() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ai/redact"
        return httpx.Response(200, content=b"%PDF redacted")

    assert NutrientRedactor(client(handler)).redact(b"pdf", "Redact all PII") == b"%PDF redacted"


def test_a_viewer_token_is_scoped_and_expiring() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"jwt": "scoped-token"})

    token = viewer_token(
        client(handler), operations=("data_extraction_api",), expires_in=600, origin="app.example"
    )

    assert token == "scoped-token"
    assert "data_extraction_api" in seen["body"]
    assert "app.example" in seen["body"]


def test_a_missing_key_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="requires an API key"):
        NutrientClient("")
