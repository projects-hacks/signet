"""Every fake must satisfy its port.

isinstance against a runtime protocol would need decorating every port, so the
check is a static assignment: mypy fails the build if a fake drifts from the
Protocol it stands in for.
"""

from signet.ports.dns import DnsPublisher, DnsResolver
from signet.ports.documents import DocumentExtractor, DocumentRenderer
from signet.ports.intelligence import EntityResolver
from signet.ports.registry import DomainRegistrar, RegistrationData
from signet.ports.signature_gateway import SignatureGateway
from signet.ports.store import RecordStore
from tests.fakes import (
    FakeDnsPublisher,
    FakeDnsResolver,
    FakeDocumentExtractor,
    FakeDocumentRenderer,
    FakeDomainRegistrar,
    FakeEntityResolver,
    FakeRecordStore,
    FakeRegistrationData,
    FakeSignatureGateway,
)


def test_fakes_satisfy_their_ports() -> None:
    resolver: DnsResolver = FakeDnsResolver()
    publisher: DnsPublisher = FakeDnsPublisher()
    extractor: DocumentExtractor = FakeDocumentExtractor()
    renderer: DocumentRenderer = FakeDocumentRenderer()
    registrar: DomainRegistrar = FakeDomainRegistrar()
    registration: RegistrationData = FakeRegistrationData()
    entities: EntityResolver = FakeEntityResolver()
    gateway: SignatureGateway = FakeSignatureGateway()
    store: RecordStore = FakeRecordStore()

    assert resolver.lookup_txt("_signet.example.com").records == ()
    assert publisher is not None
    assert extractor.extract(b"", "application/pdf").fields == ()
    assert renderer.render("receipt", {}, "S1|x", "example.com/1")
    assert registrar.available(("example.com",)) == {"example.com": True}
    assert registration.registration("example.com").locked
    assert entities.resolve_brand("Blue Bottle Coffee").canonical_domain is None
    assert gateway is not None
    assert store.record_submission("abc", "tester")


def test_a_repeated_submission_is_refused() -> None:
    store = FakeRecordStore()
    assert store.record_submission("abc", "tester")
    assert not store.record_submission("abc", "tester")


def test_publishing_makes_a_record_resolvable() -> None:
    resolver = FakeDnsResolver()
    publisher = FakeDnsPublisher(resolver)
    publisher.publish_txt("example.com", "_signet", "v=SIGNET1; k=ed25519; p=AAAA", 300)
    assert resolver.lookup_txt("_signet.example.com").records == ("v=SIGNET1; k=ed25519; p=AAAA",)


def test_an_envelope_is_not_complete_until_signed() -> None:
    gateway = FakeSignatureGateway()
    envelope_id = gateway.send_for_signature(b"doc", "officer@example.com", "Publish key")
    assert not gateway.fetch(envelope_id).completed
    gateway.complete(envelope_id, signer_role="authorized_officer")
    assert gateway.fetch(envelope_id).completed
