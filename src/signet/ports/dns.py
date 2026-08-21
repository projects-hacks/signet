"""Reading and writing the trust root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TxtLookup:
    """The result of resolving one name.

    dnssec_validated records whether the answer arrived over a validated chain.
    It is advisory: adoption is partial, so an unsigned zone still verifies, and
    the evidence bundle records which it was.
    """

    name: str
    records: tuple[str, ...]
    dnssec_validated: bool
    resolvers_agreed: bool


class DnsResolver(Protocol):
    def lookup_txt(self, name: str) -> TxtLookup: ...


class DnsPublisher(Protocol):
    def publish_txt(self, domain: str, name: str, value: str, ttl: int) -> None: ...
