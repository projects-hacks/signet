"""The gate between an agent and an irreversible act.

Publishing a signing key to DNS is the only thing Signet does that cannot be
undone. Once `_signet.<domain>` carries a key, that domain vouches for every
document signed with it, to everyone, for as long as the record stands. Nothing
else here has that shape: a document can be regenerated, an envelope voided, a
record store row corrected.

So the agent does everything up to this line and stops. The broker is the only
caller of the publisher, and it will not call it on a status field.

What the release rests on
-------------------------

A completed envelope proves a person acted. It does not prove what they acted
on. A recipient can be told they are approving one thing and shown another, and
the webhook that reports completion is produced by the same system that showed
it to them.

So the release is checked against content we placed in the document ourselves.
The authorisation carries a hash over the domain, the brand and the public key.
After signing, the executed document is downloaded and read back as text, and
the hash has to be in it. If the document that came back is not the document we
sent, the string is not there and no key is published.

That check is deliberately cheap to state and hard to fool: it does not depend
on the vendor being honest about status, on a payload field, or on a signature
we cannot verify. It depends on the bytes of the thing the person signed.

Failing closed
--------------

Every refusal here leaves the world as it was. A pending enrolment that never
completes publishes nothing, and an authorisation that comes back altered
publishes nothing. The cost of a false refusal is that somebody signs again.
The cost of a false release is a domain vouching for a forger indefinitely.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Protocol

from signet.core.signing import encode_public_key
from signet.errors import SignetError
from signet.issue.publish import KeyPublisher
from signet.ports.documents import DocumentRenderer
from signet.ports.signature_gateway import SignatureGateway
from signet.ports.store import RecordStore

AUTHORISATION_CLASS: Final = "authorisation"
_HASH_LENGTH: Final = 16


class ReleaseRefused(SignetError):
    """The key was not published, and why."""


class TextReader(Protocol):
    """Reads a document back as text.

    Named for what the broker needs rather than for the vendor that provides it,
    because what matters is that the executed document can be read at all.
    """

    def text_of_document(self, document: bytes) -> str: ...


@dataclass(frozen=True, slots=True)
class Pending:
    """An enrolment waiting on a person."""

    domain: str
    brand: str
    public_key: bytes
    envelope_id: str
    authorisation_hash: str


@dataclass(frozen=True, slots=True)
class Released:
    domain: str
    brand: str
    record: str


def authorisation_hash(domain: str, brand: str, public_key: bytes) -> str:
    """A short reference bound to exactly this enrolment.

    Over the three things that make the enrolment what it is. Change the domain,
    the brand or the key and the reference changes, so an authorisation signed
    for one cannot release another.
    """
    material = b"\x00".join((domain.encode("utf-8"), brand.encode("utf-8"), public_key))
    return hashlib.sha256(material).hexdigest()[:_HASH_LENGTH].upper()


def dns_record(public_key: bytes) -> str:
    return encode_public_key(public_key)


class EnrolmentBroker:
    """Requests a human authorisation, and releases against the signed result."""

    def __init__(
        self,
        renderer: DocumentRenderer,
        gateway: SignatureGateway,
        reader: TextReader,
        store: RecordStore,
        publisher: KeyPublisher,
    ) -> None:
        self._renderer = renderer
        self._gateway = gateway
        self._reader = reader
        self._store = store
        self._publisher = publisher

    def request_release(
        self,
        domain: str,
        brand: str,
        public_key: bytes,
        signer_email: str,
        signer_name: str,
        diligence: str,
    ) -> Pending:
        """Put the authorisation in front of a person. Publishes nothing."""
        reference = authorisation_hash(domain, brand, public_key)
        record = dns_record(public_key)
        document = self._renderer.render(
            AUTHORISATION_CLASS,
            {
                "Domain": domain,
                "Brand": brand,
                "Record": record,
                "Fingerprint": _fingerprint(public_key),
                "Diligence": diligence,
                "AuthorisationHash": reference,
            },
            reference,
            f"{domain}/enrolment",
        )

        # Read our own document back before sending it. A template that dropped
        # the reference produces an authorisation that can never be released,
        # and finding that out after a person has signed wastes their time and
        # an envelope.
        if reference not in self._reader.text_of_document(document):
            raise ReleaseRefused(
                "The authorisation was generated without its reference, so it could "
                "never be released. Nothing was sent."
            )

        envelope_id = self._gateway.send_for_signature(
            document, signer_email, signer_name, f"Signet enrolment for {domain}"
        )
        self._store.append_audit(
            reference,
            "authorisation_sent",
            {"domain": domain, "brand": brand, "envelope": envelope_id, "signer": signer_email},
        )
        return Pending(
            domain=domain,
            brand=brand,
            public_key=public_key,
            envelope_id=envelope_id,
            authorisation_hash=reference,
        )

    def release(self, pending: Pending) -> Released:
        """Publish the key, but only against the document that came back."""
        envelope = self._gateway.fetch(pending.envelope_id)

        if not envelope.completed:
            raise ReleaseRefused(f"Nobody has signed the authorisation for {pending.domain} yet.")
        if envelope.document is None:
            raise ReleaseRefused(
                f"The signed authorisation for {pending.domain} could not be downloaded, "
                "so there is nothing to check the release against."
            )

        text = self._reader.text_of_document(envelope.document)
        if pending.authorisation_hash not in text:
            # The envelope completed and the document is not ours. That is the
            # case this whole gate exists for, so it is audited before raising.
            self._store.append_audit(
                pending.authorisation_hash,
                "release_refused",
                {"domain": pending.domain, "envelope": pending.envelope_id, "reason": "reference"},
            )
            raise ReleaseRefused(
                f"The signed document does not carry the authorisation reference for "
                f"{pending.domain}. It is not the document that was sent, so no key "
                "was published."
            )

        record = self._publisher.publish(pending.domain, pending.public_key)
        self._store.enrol(pending.domain, pending.brand, pending.public_key)
        self._store.append_audit(
            pending.authorisation_hash,
            "released",
            {
                "domain": pending.domain,
                "brand": pending.brand,
                "envelope": pending.envelope_id,
                "signer": envelope.signer_role,
            },
        )
        return Released(domain=pending.domain, brand=pending.brand, record=record)


def _fingerprint(public_key: bytes) -> str:
    digest = hashlib.sha256(public_key).hexdigest()[:32].upper()
    return ":".join(digest[index : index + 4] for index in range(0, len(digest), 4))
