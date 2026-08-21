from __future__ import annotations

from signet.ports.dns import TxtLookup


class FakeDnsResolver:
    def __init__(self, records: dict[str, tuple[str, ...]] | None = None) -> None:
        self.records = records or {}
        self.dnssec: set[str] = set()

    def lookup_txt(self, name: str) -> TxtLookup:
        return TxtLookup(
            name=name,
            records=self.records.get(name, ()),
            dnssec_validated=name in self.dnssec,
            resolvers_agreed=True,
        )


class FakeDnsPublisher:
    def __init__(self, resolver: FakeDnsResolver | None = None) -> None:
        self.resolver = resolver or FakeDnsResolver()
        self.writes: list[tuple[str, str, str, int]] = []

    def publish_txt(self, domain: str, name: str, value: str, ttl: int) -> None:
        self.writes.append((domain, name, value, ttl))
        fqdn = f"{name}.{domain}"
        self.resolver.records[fqdn] = (*self.resolver.records.get(fqdn, ()), value)
