"""Foxit, which is two capabilities behind one gateway.

Their developer portal issues one credential pair for every Foxit API, sent as
two plain headers with no token exchange. The published blog documents a
different, legacy eSign product with an OAuth2 flow; that surface rejects a
portal credential outright. Confirmed by call, and written up in
docs/context/sponsors/foxit.md.

Two ports live here for one vendor because they are two capabilities. Documents
can be converted, merged and read as often as we like. Sending one for signature
puts it in front of a person, and the executed result is the only thing that can
release a key. A caller that needs the first must not thereby acquire the second.

Everything here costs credits from a pool of five hundred a year, shared across
every Foxit API. A processing call is one, an envelope is five, and an envelope
is billed when it is created rather than when it is sent, so a draft costs the
same as the real thing. That is why the tool surface below is small and why
nothing in it loops.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any, Final

import httpx

from signet.adapters import http
from signet.errors import AdapterError
from signet.ports.signature_gateway import Envelope

BASE_URL: Final = "https://na1.fusion.foxit.com"
_TIMEOUT_SECONDS: Final = 90.0

_ESIGN: Final = "/esign/api/v1"
_SERVICES: Final = "/pdf-services/api"

# Their gateway answers 404 for a path missing its version segment, which reads
# like a permission problem and is not one. Every path below was taken from
# their own MCP client rather than from the reference, which names some of them
# differently.
_COMPLETED: Final = frozenset({"COMPLETED", "EXECUTED", "SIGNED"})
_POLL_ATTEMPTS: Final = 25


@dataclass(frozen=True, slots=True)
class Task:
    """A PDF Services operation, which finishes asynchronously."""

    task_id: str
    document_id: str | None


class FoxitClient:
    """Shared transport. One credential pair, two headers, no token exchange."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # Per request rather than baked into the transport, so authentication
        # does not depend on who constructed the client.
        self._auth = {"client_id": client_id, "client_secret": client_secret}
        self._client = client or http.client(_TIMEOUT_SECONDS)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._auth, **dict(kwargs.pop("headers", {}) or {})}
        response = self._client.request(
            method, f"{self._base_url}{path}", headers=headers, **kwargs
        )
        if response.status_code == 401:
            raise AdapterError("Foxit rejected the client id or secret.")
        if response.status_code == 429:
            raise AdapterError(
                "Foxit refused the call: either the rate limit or the annual credit "
                f"pool is exhausted. {response.text[:160]}"
            )
        if not response.is_success:
            raise AdapterError(
                f"Foxit {method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        return response

    def json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, path, **kwargs)
        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError(f"Foxit returned a non-JSON body: {response.text[:200]}") from exc
        if not isinstance(body, dict):
            raise AdapterError(f"unexpected Foxit response shape: {str(body)[:200]}")
        return body


class FoxitDocuments:
    """The reversible half. Upload, convert, combine, read back.

    Every one of these can be run again, and running one twice produces another
    document rather than another consequence. That is what makes this the half an
    agent is allowed to drive.
    """

    def __init__(self, client: FoxitClient) -> None:
        self._client = client

    def upload(self, filename: str, content: bytes) -> str:
        body = self._client.json(
            "POST", f"{_SERVICES}/documents/upload", files={"file": (filename, content)}
        )
        document_id = body.get("documentId")
        if not isinstance(document_id, str):
            raise AdapterError("Foxit upload returned no document id")
        return document_id

    def download(self, document_id: str) -> bytes:
        return self._client.request("GET", f"{_SERVICES}/documents/{document_id}/download").content

    def task(self, task_id: str) -> Task:
        body = self._client.json("GET", f"{_SERVICES}/tasks/{task_id}")
        result = body.get("resultDocumentId")
        return Task(task_id=task_id, document_id=result if isinstance(result, str) else None)

    def _start(self, path: str, payload: dict[str, Any]) -> str:
        body = self._client.json("POST", path, json=payload)
        task_id = body.get("taskId")
        if not isinstance(task_id, str):
            raise AdapterError(f"Foxit {path} returned no task id")
        return task_id

    def to_pdf(self, document_id: str) -> str:
        return self._start(
            f"{_SERVICES}/documents/create/pdf-from-word", {"documentId": document_id}
        )

    def combine(self, document_ids: list[str]) -> str:
        # Both field names are sent because their own client sends both, noting
        # that deployments differ on which one they validate.
        documents = [{"documentId": each} for each in document_ids]
        return self._start(
            f"{_SERVICES}/documents/enhance/pdf-combine",
            {"documents": documents, "documentInfos": documents},
        )

    def compress(self, document_id: str) -> str:
        return self._start(
            f"{_SERVICES}/documents/modify/pdf-compress",
            {"documentId": document_id, "compressionLevel": "MEDIUM"},
        )

    def text_of_document(self, document: bytes, poll_seconds: float = 1.5) -> str:
        """Read a document back as text. Implements the broker's TextReader.

        Four calls to answer one question, because their conversion is
        asynchronous: upload, start, poll, download. The broker asks it twice per
        enrolment and nowhere else, so the cost is per person rather than per
        document.
        """
        document_id = self.upload("document.pdf", document)
        task_id = self.text_of(document_id)
        for _ in range(_POLL_ATTEMPTS):
            result = self.task(task_id)
            if result.document_id:
                return self.download(result.document_id).decode("utf-8", errors="replace")
            time.sleep(poll_seconds)
        raise AdapterError("Foxit did not finish converting the document to text in time.")

    def text_of(self, document_id: str) -> str:
        """Read a PDF back as text.

        Their pdf-extract endpoint extracts pages, not words. This is the one
        that answers whether a string we put into a document is still in it.
        """
        return self._start(
            f"{_SERVICES}/documents/convert/pdf-to-text", {"documentId": document_id}
        )


def _named(signer_name: str) -> dict[str, str]:
    """Their party object requires both halves of a name and rejects neither.

    A single word is a legitimate way for someone to be addressed, so the
    surname falls back to a placeholder rather than the request failing over a
    naming convention.
    """
    parts = signer_name.strip().split()
    if not parts:
        return {"firstName": "Authorised", "lastName": "Signatory"}
    return {"firstName": parts[0], "lastName": " ".join(parts[1:]) or "Signatory"}


class FoxitSignatures:
    """The irreversible half, and the reason the two are separate classes.

    Creating an envelope puts a document in front of a named person and spends
    five of the year's five hundred credits whether or not it is ever sent. The
    agent reaches this through one narrow tool; nothing else here is exposed to
    it.
    """

    def __init__(self, client: FoxitClient, send_now: bool = True) -> None:
        self._client = client
        # An envelope costs five credits whether or not it is sent, so drafting
        # buys nothing except not mailing a person. That is worth having while
        # rehearsing, and it is off by default because a gate nobody is asked to
        # pass is not a gate.
        self._send_now = send_now

    def send_for_signature(
        self, document: bytes, signer_email: str, signer_name: str, subject: str
    ) -> str:
        body = self._client.json(
            "POST",
            f"{_ESIGN}/folders/createfolder",
            json={
                "folderName": subject,
                "inputType": "base64",
                "base64FileString": [base64.b64encode(document).decode("ascii")],
                "fileNames": [f"{subject}.pdf"],
                "parties": [
                    {
                        **_named(signer_name),
                        "emailId": signer_email,
                        "permission": "FILL_FIELDS_AND_SIGN",
                        "sequence": 1,
                    }
                ],
                # The document carries its own text tags, so the signature field
                # is placed by whoever wrote the document rather than by
                # coordinates guessed here.
                "processTextTags": True,
                "processAcroFields": False,
                "createEmbeddedSigningSession": False,
                "sendNow": self._send_now,
            },
        )
        # Their create response nests the envelope, while the fetch response is
        # accepted in either shape. Confirmed against a live call.
        nested = body.get("folder")
        envelope_id = nested.get("folderId") if isinstance(nested, dict) else body.get("folderId")
        if envelope_id is None:
            raise AdapterError(f"Foxit created no envelope: {str(body)[:200]}")
        return str(envelope_id)

    def fetch(self, envelope_id: str) -> Envelope:
        body = self._client.json(
            "GET", f"{_ESIGN}/folders/myfolder", params={"folderId": envelope_id}
        )
        nested = body.get("folder")
        folder: dict[str, Any] = nested if isinstance(nested, dict) else body
        status = str(folder.get("folderStatus", "")).upper()
        completed = status in _COMPLETED
        parties = folder.get("parties")
        role = None
        if isinstance(parties, list) and parties and isinstance(parties[0], dict):
            role = parties[0].get("emailId")
        return Envelope(
            envelope_id=envelope_id,
            completed=completed,
            signer_role=str(role) if isinstance(role, str) else None,
            document=self._download(envelope_id) if completed else None,
        )

    def _download(self, envelope_id: str) -> bytes | None:
        """The executed document, which is what a release is actually checked against.

        A status field says a person acted. Only the document says what they
        signed, and the broker needs the second.
        """
        try:
            return self._client.request(
                "GET", f"{_ESIGN}/folders/download", params={"folderId": envelope_id}
            ).content
        except AdapterError:
            return None
