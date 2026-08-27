"""The gate on the one irreversible act.

The interesting tests here are the refusals. A completed envelope proves a
person acted; it does not prove what they acted on, and every case below is
about that gap.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from signet.core.signing import generate_key
from signet.issue.broker import (
    AUTHORISATION_CLASS,
    EnrolmentBroker,
    Pending,
    ReleaseRefused,
    authorisation_hash,
)
from signet.issue.publish import KeyPublisher
from signet.ports.signature_gateway import Envelope
from tests.fakes import FakeDnsPublisher, FakeDnsResolver, FakeRecordStore

DOMAIN = "northpost.dev"
BRAND = "Northpost"
SIGNER = "ops@northpost.dev"


class FakeRenderer:
    """Renders an authorisation that contains everything it was given."""

    def __init__(self, *, drop_reference: bool = False) -> None:
        self.drop_reference = drop_reference
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def render(
        self, document_class: str, record: Mapping[str, object], mark: str, locator: str
    ) -> bytes:
        self.calls.append((document_class, record))
        parts = [str(value) for key, value in record.items() if key != "AuthorisationHash"]
        if not self.drop_reference:
            parts.append(str(record["AuthorisationHash"]))
        return "\n".join(parts).encode("utf-8")


class FakeGateway:
    def __init__(self, envelope: Envelope | None = None) -> None:
        self.sent: list[tuple[bytes, str, str]] = []
        self.envelope = envelope

    def send_for_signature(
        self, document: bytes, signer_email: str, signer_name: str, subject: str
    ) -> str:
        self.sent.append((document, signer_email, subject))
        return "env-1"

    def fetch(self, envelope_id: str) -> Envelope:
        assert self.envelope is not None
        return self.envelope


class FakeReader:
    """Reading a PDF back as text, which here is just the bytes."""

    def text_of_document(self, document: bytes) -> str:
        return document.decode("utf-8", errors="replace")


def broker(
    gateway: FakeGateway,
    store: FakeRecordStore,
    publisher: FakeDnsPublisher,
    renderer: FakeRenderer | None = None,
) -> EnrolmentBroker:
    return EnrolmentBroker(
        renderer=renderer or FakeRenderer(),
        gateway=gateway,
        reader=FakeReader(),
        store=store,
        publisher=KeyPublisher(publisher, FakeDnsResolver({})),
    )


def pending(public_key: bytes) -> Pending:
    return Pending(
        domain=DOMAIN,
        brand=BRAND,
        public_key=public_key,
        envelope_id="env-1",
        authorisation_hash=authorisation_hash(DOMAIN, BRAND, public_key),
    )


def test_requesting_a_release_publishes_nothing() -> None:
    """The whole point of the gate is that asking is not doing."""
    _, public = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    gateway = FakeGateway()

    broker(gateway, store, publisher).request_release(
        DOMAIN, BRAND, public, SIGNER, "Ops Team", "nothing adverse"
    )

    assert publisher.writes == []
    assert store.issuers == {}
    assert gateway.sent


def test_an_unsigned_envelope_releases_nothing() -> None:
    _, public = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    gateway = FakeGateway(Envelope("env-1", completed=False, signer_role=None, document=None))

    with pytest.raises(ReleaseRefused, match="Nobody has signed"):
        broker(gateway, store, publisher).release(pending(public))
    assert publisher.writes == []


def test_a_completed_envelope_with_no_document_releases_nothing() -> None:
    """Missing evidence is not evidence. There is nothing to check against."""
    _, public = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    gateway = FakeGateway(Envelope("env-1", completed=True, signer_role=SIGNER, document=None))

    with pytest.raises(ReleaseRefused, match="could not be downloaded"):
        broker(gateway, store, publisher).release(pending(public))
    assert publisher.writes == []


def test_a_signed_document_that_is_not_ours_releases_nothing() -> None:
    """The case the gate exists for: the envelope completed, a person signed,
    and what came back is a different document."""
    _, public = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    gateway = FakeGateway(
        Envelope("env-1", completed=True, signer_role=SIGNER, document=b"a different agreement")
    )

    with pytest.raises(ReleaseRefused, match="does not carry the authorisation reference"):
        broker(gateway, store, publisher).release(pending(public))
    assert publisher.writes == []
    assert any(event == "release_refused" for _, event, _ in store.audit)


def test_a_signed_authorisation_carrying_its_reference_publishes_the_key() -> None:
    _, public = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    reference = authorisation_hash(DOMAIN, BRAND, public)
    gateway = FakeGateway(
        Envelope(
            "env-1",
            completed=True,
            signer_role=SIGNER,
            document=f"authorisation reference {reference}".encode(),
        )
    )

    released = broker(gateway, store, publisher).release(pending(public))

    assert released.domain == DOMAIN
    assert publisher.writes
    assert store.issuers[DOMAIN].brand == BRAND
    assert any(event == "released" for _, event, _ in store.audit)


def test_an_authorisation_signed_for_one_key_cannot_release_another() -> None:
    """The reference covers the domain, the brand and the key, so a document
    signed for one enrolment is not a licence for a different one."""
    _, public = generate_key()
    _, other = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    gateway = FakeGateway(
        Envelope(
            "env-1",
            completed=True,
            signer_role=SIGNER,
            document=f"reference {authorisation_hash(DOMAIN, BRAND, other)}".encode(),
        )
    )

    with pytest.raises(ReleaseRefused):
        broker(gateway, store, publisher).release(pending(public))
    assert publisher.writes == []


def test_an_authorisation_signed_for_one_domain_cannot_release_another() -> None:
    _, public = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    gateway = FakeGateway(
        Envelope(
            "env-1",
            completed=True,
            signer_role=SIGNER,
            document=f"reference {authorisation_hash('north-post.dev', BRAND, public)}".encode(),
        )
    )

    with pytest.raises(ReleaseRefused):
        broker(gateway, store, publisher).release(pending(public))
    assert publisher.writes == []


def test_a_template_that_dropped_the_reference_is_caught_before_anyone_signs() -> None:
    """Such an authorisation could never be released, and finding that out after
    a person signed wastes their time and an envelope."""
    _, public = generate_key()
    publisher, store = FakeDnsPublisher(), FakeRecordStore()
    gateway = FakeGateway()

    with pytest.raises(ReleaseRefused, match="could never be released"):
        broker(gateway, store, publisher, FakeRenderer(drop_reference=True)).request_release(
            DOMAIN, BRAND, public, SIGNER, "Ops Team", "nothing adverse"
        )
    assert gateway.sent == []


def test_the_authorisation_says_what_it_is_authorising() -> None:
    """A person is being asked to agree to something, so the document has to
    carry the domain, the record and what was checked."""
    _, public = generate_key()
    renderer = FakeRenderer()
    broker(FakeGateway(), FakeRecordStore(), FakeDnsPublisher(), renderer).request_release(
        DOMAIN, BRAND, public, SIGNER, "Ops Team", "no adverse coverage found"
    )

    document_class, record = renderer.calls[0]
    assert document_class == AUTHORISATION_CLASS
    assert record["Domain"] == DOMAIN
    assert record["Brand"] == BRAND
    assert "v=SIGNET1" in str(record["Record"])
    assert record["Diligence"] == "no adverse coverage found"
    assert record["AuthorisationHash"] == authorisation_hash(DOMAIN, BRAND, public)
