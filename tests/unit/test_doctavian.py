from __future__ import annotations

import httpx
import pytest

from signet.adapters.doctavian import DoctavianRenderer
from signet.errors import AdapterError


def renderer(handler: object, templates: dict[str, str] | None = None) -> DoctavianRenderer:
    return DoctavianRenderer(
        api_key="documents-key",
        token_provider=lambda: "bearer-token",
        template_ids=templates if templates is not None else {"receipt": "tmpl-1"},
        client=httpx.Client(transport=httpx.MockTransport(handler)),  # type: ignore[arg-type]
    )


def test_generation_sends_both_auth_headers_and_the_mark() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["key"] = request.headers.get("x-api-key")
        seen["body"] = request.read().decode()
        return httpx.Response(200, content=b"%PDF-1.7 fake")

    out = renderer(handler).render("receipt", {"amt": "14.75"}, "S1|mark", "a.com/R-1")

    assert out.startswith(b"%PDF")
    assert seen["auth"] == "Bearer bearer-token"
    assert seen["key"] == "documents-key"
    assert "signet_mark" in str(seen["body"])
    assert "signet_locator" in str(seen["body"])


def test_an_unconfigured_document_class_is_refused_before_the_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not have been called")

    with pytest.raises(AdapterError, match="no Doctavian template"):
        renderer(handler, templates={}).render("payslip", {}, "S1|m", "a.com/1")


def test_a_generation_failure_becomes_an_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(AdapterError, match="Doctavian generation failed"):
        renderer(handler).render("receipt", {}, "S1|m", "a.com/1")


def test_a_401_explains_which_credential_is_wrong() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "ApiKeyInvalid"})

    with pytest.raises(AdapterError, match="Documents key"):
        renderer(handler).ping()


def test_ping_succeeds_against_the_list_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/documents/document/list")
        return httpx.Response(200, json=[])

    assert renderer(handler).ping()
