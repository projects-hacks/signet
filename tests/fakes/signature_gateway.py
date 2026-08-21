from __future__ import annotations

from signet.ports.signature_gateway import Envelope


class FakeSignatureGateway:
    """Nothing completes until complete() is called, so a test cannot accidentally
    prove that an unsigned authorization released a credential."""

    def __init__(self) -> None:
        self.envelopes: dict[str, Envelope] = {}
        self._next = 0

    def send_for_signature(self, document: bytes, signer_email: str, subject: str) -> str:
        self._next += 1
        envelope_id = f"env-{self._next}"
        self.envelopes[envelope_id] = Envelope(
            envelope_id=envelope_id, completed=False, signer_role=None, document=document
        )
        return envelope_id

    def fetch(self, envelope_id: str) -> Envelope:
        return self.envelopes[envelope_id]

    def complete(self, envelope_id: str, signer_role: str) -> None:
        existing = self.envelopes[envelope_id]
        self.envelopes[envelope_id] = Envelope(
            envelope_id=envelope_id,
            completed=True,
            signer_role=signer_role,
            document=existing.document,
        )
