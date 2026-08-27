"""Doctavian's signatures product, as a second human gate.

The broker asks a SignatureGateway to put a document in front of a person and
tells it nothing about who provides that. Foxit implements the port and so does
this, which is the point: the gate is a boundary in the design rather than a
vendor we happen to have chosen, and swapping the implementation moves none of
the safety properties. The broker still publishes only against the executed
document carrying the reference it embedded itself.

Their envelope is assembled rather than posted in one go. A document is uploaded
to their storage, an envelope is created around it in Draft, and sending is a
separate call, which is a useful shape here: an envelope that fails validation
never reaches a person.

Field placement is by anchor string. The authorisation carries a distinctive
marker and Doctavian finds it and lays the signature field over its bounding
box, leaving the text in the document. Coordinates would have to be recomputed
whenever the diligence paragraph above them changes length, and a signature box
that lands on the wrong paragraph is worse than one that is hard to place.
"""

from __future__ import annotations

from typing import Any, Final

import httpx

from signet.adapters import http
from signet.errors import AdapterError
from signet.ports.signature_gateway import Envelope

_TIMEOUT_SECONDS: Final = 60.0

# The marker the template prints in the signature block. Distinctive on purpose:
# an anchor that also occurs in ordinary prose binds the field to the wrong line.
SIGNATURE_ANCHOR: Final = "_SIG_ISSUER_"
DATE_ANCHOR: Final = "_DATE_ISSUER_"

# Their reference ids are integers, locally unique within one envelope, and link
# fields to their document and recipient. They are not system ids.
_DOCUMENT_REF: Final = 1
_SIGNER_REF: Final = 1

_COMPLETED: Final = frozenset({"completed", "signed", "executed", "finished"})


class DoctavianSignatures:
    """Implements SignatureGateway."""

    def __init__(
        self,
        api_key: str,
        token_provider: Any,
        base_url: str,
        sender_name: str = "Signet",
        sender_email: str = "",
        expire_in_days: int = 7,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._token = token_provider
        self._base_url = base_url.rstrip("/")
        self._sender_name = sender_name
        self._sender_email = sender_email
        self._expire_in_days = expire_in_days
        self._client = client or http.client(_TIMEOUT_SECONDS)

    def send_for_signature(
        self, document: bytes, signer_email: str, signer_name: str, subject: str
    ) -> str:
        urn = self._upload(document, f"{subject}.pdf")
        envelope_id = self._create(urn, signer_email, signer_name, subject)
        # Created envelopes sit in Draft. Sending is what notifies a person, and
        # keeping it separate means a malformed envelope never reaches one.
        self._request("GET", f"/signatures/envelope/{envelope_id}/send")
        return envelope_id

    def fetch(self, envelope_id: str) -> Envelope:
        data = self._json("GET", f"/signatures/envelope/{envelope_id}/get")
        nested = data.get("envelope")
        envelope: dict[str, Any] = nested if isinstance(nested, dict) else data
        status = str(envelope.get("status", "")).strip().lower()
        completed = status in _COMPLETED

        signer = None
        recipients = data.get("recipients")
        if isinstance(recipients, list) and recipients and isinstance(recipients[0], dict):
            signer = recipients[0].get("email")

        return Envelope(
            envelope_id=envelope_id,
            completed=completed,
            signer_role=str(signer) if isinstance(signer, str) else None,
            document=self._executed(envelope_id, data) if completed else None,
        )

    def _upload(self, document: bytes, filename: str) -> str:
        data = self._json(
            "POST",
            "/signatures/document/upload",
            files={"file": (filename, document, "application/pdf")},
        )
        files = data.get("files")
        if isinstance(files, list) and files and isinstance(files[0], dict):
            urn = files[0].get("id")
            if isinstance(urn, str) and urn:
                return urn
        raise AdapterError(f"Doctavian returned no uploaded document id: {str(data)[:200]}")

    def _create(self, urn: str, signer_email: str, signer_name: str, subject: str) -> str:
        data = self._json(
            "POST",
            "/signatures/envelope/create",
            json={
                "documents": [
                    {
                        "referenceDocumentId": _DOCUMENT_REF,
                        "name": subject,
                        "loadMethod": "Storage",
                        "urn": urn,
                    }
                ],
                "recipients": [
                    {
                        "referenceSignerId": _SIGNER_REF,
                        "name": signer_name,
                        "email": signer_email,
                        "role": "signer",
                        "mandatory": True,
                    }
                ],
                "fields": [
                    {
                        "type": "signature",
                        "isRequired": True,
                        "referenceSignerId": _SIGNER_REF,
                        "referenceDocumentId": _DOCUMENT_REF,
                        "anchorString": SIGNATURE_ANCHOR,
                        "name": "signature_issuer",
                    },
                    {
                        "type": "date",
                        "isRequired": True,
                        "referenceSignerId": _SIGNER_REF,
                        "referenceDocumentId": _DOCUMENT_REF,
                        "anchorString": DATE_ANCHOR,
                        "name": "date_issuer",
                    },
                ],
                "envelope": {
                    "subject": subject,
                    "message": (
                        "This authorises a signing key to be published in your domain's "
                        "DNS. Read what it says before signing."
                    ),
                    "senderName": self._sender_name,
                    "senderEmail": self._sender_email,
                    "isSignOrder": False,
                    "expireInDays": self._expire_in_days,
                    "notifyWhenOpened": True,
                    "notifyWhenSigned": True,
                },
            },
        )
        envelope = data.get("envelope")
        envelope_id = envelope.get("id") if isinstance(envelope, dict) else None
        if not isinstance(envelope_id, str) or not envelope_id:
            raise AdapterError(f"Doctavian created no envelope: {str(data)[:200]}")
        return envelope_id

    def _executed(self, envelope_id: str, data: dict[str, Any]) -> bytes | None:
        """The signed document, which is what a release is actually checked against.

        A status field says a person acted. Only the document says what they
        signed, and the broker needs the second.
        """
        documents = data.get("documents")
        if not isinstance(documents, list) or not documents:
            return None
        first = documents[0]
        document_id = first.get("id") if isinstance(first, dict) else None
        if not isinstance(document_id, str):
            return None
        try:
            return self._request(
                "GET", f"/signatures/envelope/{envelope_id}/document/{document_id}/download"
            ).content
        except AdapterError:
            return None

    def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request(method, path, **kwargs)
        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError(
                f"Doctavian returned a non-JSON body: {response.text[:200]}"
            ) from exc
        result = body.get("result") if isinstance(body, dict) else None
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict):
            raise AdapterError(f"unexpected Doctavian response shape: {str(body)[:200]}")
        return data

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(
            method,
            f"{self._base_url}{path}",
            headers={
                "x-api-key": self._api_key,
                "Authorization": f"Bearer {self._token()}",
            },
            **kwargs,
        )
        if response.status_code == 401:
            raise AdapterError("Doctavian rejected the credentials for signatures.")
        if not response.is_success:
            raise AdapterError(
                f"Doctavian {method} {path} returned {response.status_code}: {response.text[:300]}"
            )
        return response
