"""Putting the issuer's key where anyone can find it.

Publication is the moment Signet stops being a claim about a document and
becomes a claim anyone can check without us. The key lives on the issuer's own
domain, so the trust root is the domain, not this service.

Writing the record is the easy half. The half that matters is confirming it,
because a write that the registrar accepted but the public internet cannot see
yet is indistinguishable from a working setup right up until the demo. So a
publication is not finished when the API returns; it is finished when an
independent resolver answers with the value we wrote.

Confirmation is a single lookup rather than a loop. Propagation delay is real
and belongs to whoever is watching a progress line, not to a domain object.
"""

from __future__ import annotations

from dataclasses import dataclass

from signet.constants import DNS_LABEL
from signet.core.signing import encode_public_key
from signet.ports.dns import DnsPublisher, DnsResolver

# Short enough that a key change is visible quickly, long enough that a verifier
# under load is not resolving on every document.
DEFAULT_TTL: int = 300


@dataclass(frozen=True, slots=True)
class Publication:
    """What was written, and whether the public internet agrees it exists."""

    domain: str
    record_name: str
    value: str
    visible: bool
    resolvers_agreed: bool
    dnssec_validated: bool

    @property
    def fqdn(self) -> str:
        return f"{self.record_name}.{self.domain}"


class KeyPublisher:
    def __init__(
        self, publisher: DnsPublisher, resolver: DnsResolver, ttl: int = DEFAULT_TTL
    ) -> None:
        self._publisher = publisher
        self._resolver = resolver
        self._ttl = ttl

    def publish(self, domain: str, public_key: bytes) -> str:
        """Write the key record and return the value that should appear in DNS."""
        value = encode_public_key(public_key)
        self._publisher.publish_txt(domain, DNS_LABEL, value, self._ttl)
        return value

    def confirm(self, domain: str, value: str) -> Publication:
        """Ask a resolver whether the record is visible, from outside our own stack."""
        lookup = self._resolver.lookup_txt(f"{DNS_LABEL}.{domain}")
        return Publication(
            domain=domain,
            record_name=DNS_LABEL,
            value=value,
            visible=value in lookup.records,
            resolvers_agreed=lookup.resolvers_agreed,
            dnssec_validated=lookup.dnssec_validated,
        )
