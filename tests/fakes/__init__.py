"""In-memory ports.

Every adapter has a fake here so the whole pipeline runs with the network
unplugged. If a test ever needs a socket, a vendor has leaked into the domain.
"""

from tests.fakes.dns import FakeDnsPublisher, FakeDnsResolver
from tests.fakes.documents import (
    FakeDocumentExtractor,
    FakeDocumentRenderer,
    FakeMarkReader,
)
from tests.fakes.intelligence import FakeEntityResolver
from tests.fakes.registry import FakeDomainRegistrar, FakeRegistrationData
from tests.fakes.signature_gateway import FakeSignatureGateway
from tests.fakes.store import FakeRecordStore

__all__ = [
    "FakeDnsPublisher",
    "FakeDnsResolver",
    "FakeDocumentExtractor",
    "FakeDocumentRenderer",
    "FakeDomainRegistrar",
    "FakeEntityResolver",
    "FakeMarkReader",
    "FakeRecordStore",
    "FakeRegistrationData",
    "FakeSignatureGateway",
]
