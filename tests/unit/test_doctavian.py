"""Doctavian's real flow, against recorded shapes.

A render is three calls, not one: upload the data, generate to a urn, download
the urn. Everything except the download comes back inside a result envelope.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from signet.adapters.doctavian import DoctavianRenderer
from signet.errors import AdapterError

TEMPLATES = {"receipt": ("receipt.docx", "tmpl-urn")}


def envelope(data: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"result": {"data": data, "statusCode": status}})


def renderer(
    handler: Any, templates: dict[str, tuple[str, str]] | None = None
) -> DoctavianRenderer:
    return DoctavianRenderer(
        api_key="documents-key",
        token_provider=lambda: "bearer-token",
        template_urns=TEMPLATES if templates is None else templates,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def happy_path(seen: dict[str, Any]) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.setdefault("paths", []).append(path)
        seen["auth"] = request.headers.get("Authorization")
        seen["key"] = request.headers.get("x-api-key")
        if path.endswith("/data/upload"):
            seen["data_body"] = request.read()
            return envelope({"files": [{"id": "data-urn", "fileName": "receipt.json"}]}, 201)
        if path.endswith("/document/generate"):
            seen["generate_body"] = request.read().decode()
            return envelope({"document": {"urn": "doc-urn", "fileFormat": "pdf"}}, 201)
        if path.endswith("/download"):
            return httpx.Response(200, content=b"%PDF-1.7 real bytes")
        raise AssertionError(f"unexpected path {path}")

    return handler


def test_a_render_uploads_generates_and_downloads() -> None:
    seen: dict[str, Any] = {}
    out = renderer(happy_path(seen)).render(
        "receipt", {"amt": "14.75"}, "S1|mark", "bluebottle.com/R-1"
    )

    assert out == b"%PDF-1.7 real bytes"
    assert seen["paths"] == [
        "/v1/documents/data/upload",
        "/v1/documents/document/generate",
        "/v1/documents/document/doc-urn/download",
    ]


def test_the_mark_and_locator_travel_in_the_uploaded_data() -> None:
    seen: dict[str, Any] = {}
    renderer(happy_path(seen)).render("receipt", {"amt": "14.75"}, "S1|mark", "bluebottle.com/R-1")

    body = seen["data_body"].decode()
    assert "signet_mark" in body
    assert "bluebottle.com/R-1" in body


def test_generation_references_the_uploaded_data_and_template() -> None:
    seen: dict[str, Any] = {}
    renderer(happy_path(seen)).render("receipt", {}, "S1|m", "a.com/1")

    body = seen["generate_body"]
    assert "tmpl-urn" in body
    assert "data-urn" in body
    assert '"fileFormat": "docx"' in body or '"fileFormat":"docx"' in body


def test_both_auth_headers_are_sent() -> None:
    seen: dict[str, Any] = {}
    renderer(happy_path(seen)).render("receipt", {}, "S1|m", "a.com/1")
    assert seen["auth"] == "Bearer bearer-token"
    assert seen["key"] == "documents-key"


def test_an_unconfigured_class_is_refused_before_any_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not have been called")

    with pytest.raises(AdapterError, match="no Doctavian template"):
        renderer(handler, templates={}).render("payslip", {}, "S1|m", "a.com/1")


def test_provisioning_returns_both_guids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/datasource/create"):
            return envelope({"dataSourceGuid": "ds-1"})
        return envelope({"documentSolution": {"documentSolutionGuid": "sol-1", "dataGuid": "ds-1"}})

    provisioning = renderer(handler).provision("Signet")
    assert provisioning.data_source_guid == "ds-1"
    assert provisioning.document_solution_guid == "sol-1"


def test_a_missing_urn_is_an_adapter_error_not_a_key_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/data/upload"):
            return envelope({"files": [{"id": "data-urn"}]}, 201)
        return envelope({"document": {}}, 201)

    with pytest.raises(AdapterError, match="no document urn"):
        renderer(handler).render("receipt", {}, "S1|m", "a.com/1")


def test_an_unwrapped_response_is_an_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(AdapterError, match="unexpected Doctavian response"):
        renderer(handler).provision("Signet")


def test_a_401_explains_which_credential_is_wrong() -> None:
    """Confirmed live: a key of thirty two zeros gives the same ApiKeyInvalid as a
    real one, so the message must not claim the key is merely the wrong area."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "ApiKeyInvalid"})

    with pytest.raises(AdapterError, match="does not recognise the x-api-key"):
        renderer(handler).ping()


def test_a_server_error_carries_the_status_and_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    with pytest.raises(AdapterError, match="503"):
        renderer(handler).ping()


def test_template_upload_returns_the_urn() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return envelope({"files": [{"id": "tmpl-99", "fileName": "receipt.docx"}]}, 201)

    assert renderer(handler).upload_template("receipt.docx", b"docx bytes") == "tmpl-99"
