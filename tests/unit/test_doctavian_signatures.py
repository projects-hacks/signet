"""Doctavian as the human gate, against their documented shapes.

The same port Foxit implements. These tests are about the request we build,
because their demo environment does not currently retain an uploaded document
and the live path stops there.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from signet.adapters.doctavian_signatures import (
    DATE_ANCHOR,
    SIGNATURE_ANCHOR,
    DoctavianSignatures,
)
from signet.errors import AdapterError


def gateway(handler: Any) -> DoctavianSignatures:
    return DoctavianSignatures(
        api_key="key",
        token_provider=lambda: "bearer",
        base_url="https://demo.api.doctavian.com/v1",
        sender_email="signet@example.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def envelope(data: dict[str, Any], status: int = 201) -> httpx.Response:
    return httpx.Response(status, json={"result": {"data": data, "statusCode": status}})


def happy(seen: dict[str, Any]) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.setdefault("paths", []).append(path)
        if path.endswith("/document/upload"):
            return envelope({"files": [{"id": "urn-1", "fileName": "a.pdf"}]})
        if path.endswith("/envelope/create"):
            seen["create"] = json.loads(request.read())
            return envelope({"envelope": {"id": "env-1", "status": "Draft"}})
        if path.endswith("/send"):
            return httpx.Response(200, json={"result": {"data": {}, "statusCode": 200}})
        raise AssertionError(f"unexpected path {path}")

    return handler


def test_the_document_is_uploaded_then_wrapped_then_sent() -> None:
    """Three calls, in that order. An envelope that fails validation never
    reaches a person, because sending is separate from creating."""
    seen: dict[str, Any] = {}
    assert (
        gateway(happy(seen)).send_for_signature(b"pdf", "a@b.c", "Dana Okafor", "Sign") == "env-1"
    )
    assert seen["paths"] == [
        "/v1/signatures/document/upload",
        "/v1/signatures/envelope/create",
        "/v1/signatures/envelope/env-1/send",
    ]


def test_fields_are_placed_by_anchor_rather_than_coordinates() -> None:
    """Coordinates would move every time the paragraph above the signature
    block changes length, and a signature box on the wrong line is worse than
    one that is hard to place. Their API rejects both together."""
    seen: dict[str, Any] = {}
    gateway(happy(seen)).send_for_signature(b"pdf", "a@b.c", "Dana", "Sign")

    fields = seen["create"]["fields"]
    anchors = {field["anchorString"] for field in fields}
    assert anchors == {SIGNATURE_ANCHOR, DATE_ANCHOR}
    for field in fields:
        assert "positionX" not in field
        assert "page" not in field


def test_reference_ids_are_integers_and_link_the_field_to_both_sides() -> None:
    """They are locally unique integers within one envelope, not system ids,
    and sending a string is rejected by their deserialiser."""
    seen: dict[str, Any] = {}
    gateway(happy(seen)).send_for_signature(b"pdf", "a@b.c", "Dana", "Sign")

    created = seen["create"]
    document_ref = created["documents"][0]["referenceDocumentId"]
    signer_ref = created["recipients"][0]["referenceSignerId"]
    assert isinstance(document_ref, int)
    assert isinstance(signer_ref, int)
    for field in created["fields"]:
        assert field["referenceDocumentId"] == document_ref
        assert field["referenceSignerId"] == signer_ref


def test_the_signer_is_mandatory_so_a_decline_stops_the_enrolment() -> None:
    """An optional signer would let an enrolment complete without the one
    consent it exists to collect."""
    seen: dict[str, Any] = {}
    gateway(happy(seen)).send_for_signature(b"pdf", "ops@x.dev", "Dana", "Sign")

    recipient = seen["create"]["recipients"][0]
    assert recipient["mandatory"] is True
    assert recipient["role"] == "signer"
    assert recipient["email"] == "ops@x.dev"


def test_an_unfinished_envelope_carries_no_document() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return envelope({"envelope": {"id": "env-1", "status": "Draft"}}, 200)

    found = gateway(handler).fetch("env-1")
    assert not found.completed
    assert found.document is None


def test_a_completed_envelope_brings_back_what_was_signed() -> None:
    """A status says a person acted. Only the document says what they acted on,
    and the broker checks the second."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/download"):
            return httpx.Response(200, content=b"%PDF executed")
        return envelope(
            {
                "envelope": {"id": "env-1", "status": "Completed"},
                "documents": [{"id": "doc-1"}],
                "recipients": [{"email": "ops@x.dev"}],
            },
            200,
        )

    found = gateway(handler).fetch("env-1")
    assert found.completed
    assert found.document == b"%PDF executed"
    assert found.signer_role == "ops@x.dev"


def test_an_upload_that_returns_no_id_is_an_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return envelope({"files": []})

    with pytest.raises(AdapterError, match="no uploaded document id"):
        gateway(handler).send_for_signature(b"pdf", "a@b.c", "Dana", "Sign")


def test_a_rejected_credential_says_so() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorised")

    with pytest.raises(AdapterError, match="rejected the credentials"):
        gateway(handler).send_for_signature(b"pdf", "a@b.c", "Dana", "Sign")
