"""Foxit, split by what a call does rather than by which product sells it.

Uploading and converting can be repeated. Creating an envelope puts a document
in front of a person and spends five of the year's five hundred credits whether
or not it is ever sent. The tests below hold that line.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest

from signet.adapters.foxit import FoxitClient, FoxitDocuments, FoxitSignatures
from signet.errors import AdapterError


def client(handler: Any) -> FoxitClient:
    return FoxitClient(
        client_id="cid",
        client_secret="secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_the_credential_pair_travels_as_two_plain_headers() -> None:
    """No token exchange, which is what separates the portal from the legacy
    product their own blog documents."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["id"] = request.headers.get("client_id")
        seen["secret"] = request.headers.get("client_secret")
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"documentId": "d1"})

    FoxitDocuments(client(handler)).upload("a.pdf", b"bytes")
    assert seen == {"id": "cid", "secret": "secret", "auth": None}


def test_every_path_carries_its_version_segment() -> None:
    """A path missing it answers 404, which reads like a permission problem."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"folder": {"folderId": 5510}})

    FoxitSignatures(client(handler)).send_for_signature(
        b"pdf", "ops@example.com", "Dana Okafor", "Authorisation"
    )
    assert seen == ["/esign/api/v1/folders/createfolder"]


def test_a_document_is_sent_as_base64_not_a_url() -> None:
    """A url input would need the authorisation to be publicly reachable before
    anyone had signed it."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.read()))
        return httpx.Response(200, json={"folder": {"folderId": 5510}})

    FoxitSignatures(client(handler)).send_for_signature(
        b"pdf bytes", "ops@x.com", "Dana Okafor", "Authorisation"
    )
    assert seen["inputType"] == "base64"
    assert base64.b64decode(seen["base64FileString"][0]) == b"pdf bytes"
    assert seen["parties"][0]["emailId"] == "ops@x.com"
    assert seen["parties"][0]["firstName"] == "Dana"
    assert seen["parties"][0]["lastName"] == "Okafor"


def test_a_numeric_envelope_id_is_returned_as_text() -> None:
    """Their folderId is a number and every caller treats it as an identifier."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"folder": {"folderId": 5510}})

    assert FoxitSignatures(client(handler)).send_for_signature(b"p", "a@b.c", "Dana", "s") == "5510"


def test_the_envelope_id_is_found_whether_or_not_it_is_nested() -> None:
    """Their create response nests it and their docs show it flat."""

    def flat(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"folderId": 77})

    assert FoxitSignatures(client(flat)).send_for_signature(b"p", "a@b.c", "Dana", "s") == "77"


def test_an_unfinished_envelope_carries_no_document() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"folder": {"folderStatus": "SHARED"}})

    envelope = FoxitSignatures(client(handler)).fetch("5510")
    assert not envelope.completed
    assert envelope.document is None


def test_a_completed_envelope_brings_back_what_was_actually_signed() -> None:
    """A status field says a person acted. Only the document says what they
    signed, and a release is checked against the second."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/download"):
            return httpx.Response(200, content=b"%PDF executed")
        return httpx.Response(
            200,
            json={"folder": {"folderStatus": "COMPLETED", "parties": [{"emailId": "a@b.c"}]}},
        )

    envelope = FoxitSignatures(client(handler)).fetch("5510")
    assert envelope.completed
    assert envelope.document == b"%PDF executed"
    assert envelope.signer_role == "a@b.c"


def test_a_download_that_fails_leaves_the_envelope_complete_but_empty() -> None:
    """Missing evidence is not the same as evidence of a refusal, and the broker
    treats an absent document as a release it cannot grant."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/download"):
            return httpx.Response(500, text="storage error")
        return httpx.Response(200, json={"folder": {"folderStatus": "COMPLETED"}})

    envelope = FoxitSignatures(client(handler)).fetch("5510")
    assert envelope.completed
    assert envelope.document is None


def test_combine_sends_both_field_names() -> None:
    """Their own client sends both, noting deployments validate different ones."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.read()))
        return httpx.Response(200, json={"taskId": "t1"})

    FoxitDocuments(client(handler)).combine(["a", "b"])
    assert seen["documents"] == seen["documentInfos"]
    assert [each["documentId"] for each in seen["documents"]] == ["a", "b"]


def test_reading_a_pdf_back_uses_the_text_conversion_not_page_extraction() -> None:
    """pdf-extract pulls out pages. Only pdf-to-text answers whether a string we
    put in a document is still in it."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"taskId": "t1"})

    FoxitDocuments(client(handler)).text_of("d1")
    assert seen == ["/pdf-services/api/documents/convert/pdf-to-text"]


def test_an_unfinished_task_reports_no_document_rather_than_failing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"taskId": "t1", "status": "PROCESSING"})

    assert FoxitDocuments(client(handler)).task("t1").document_id is None


def test_an_exhausted_credit_pool_is_named_rather_than_reported_as_a_rate_limit() -> None:
    """Both arrive as 429 and one of them is fixed by waiting."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": "QUOTA_EXCEEDED", "message": "Credit quota"})

    with pytest.raises(AdapterError, match="credit pool"):
        FoxitDocuments(client(handler)).upload("a.pdf", b"x")


def test_a_rejected_credential_says_which_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorised")

    with pytest.raises(AdapterError, match="client id or secret"):
        FoxitDocuments(client(handler)).upload("a.pdf", b"x")


def test_a_missing_document_id_is_an_adapter_error_not_a_key_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with pytest.raises(AdapterError, match="no document id"):
        FoxitDocuments(client(handler)).upload("a.pdf", b"x")


def test_a_one_word_name_still_produces_a_valid_party() -> None:
    """Their party object requires both halves, and a single word is a
    legitimate way for somebody to be addressed."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.read()))
        return httpx.Response(200, json={"folder": {"folderId": 1}})

    FoxitSignatures(client(handler)).send_for_signature(b"p", "a@b.c", "Prince", "s")
    assert seen["parties"][0]["firstName"] == "Prince"
    assert seen["parties"][0]["lastName"] == "Signatory"
