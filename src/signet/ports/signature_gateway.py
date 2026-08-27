"""The human gate on irreversible acts.

Publishing a signing key lets a domain vouch for its documents indefinitely, so a
person signs for it. The broker binds a release to content we placed in the
document ourselves rather than to an undocumented webhook field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Envelope:
    envelope_id: str
    completed: bool
    signer_role: str | None
    document: bytes | None


class SignatureGateway(Protocol):
    def send_for_signature(
        self, document: bytes, signer_email: str, signer_name: str, subject: str
    ) -> str:
        """Address the document to a person.

        A name rather than only an address, because every gateway shows the
        recipient who is being asked and an envelope addressed to a mailbox
        reads like a machine sent it, which is the opposite of what a human
        gate is for.
        """
        ...

    def fetch(self, envelope_id: str) -> Envelope: ...
