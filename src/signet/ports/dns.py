"""Reading and writing the trust root."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TxtLookup:
    """The result of resolving one name.

    dnssec_validated records whether the answer arrived over a validated chain.
    It is advisory: adoption is partial, so an unsigned zone still verifies, and
    the evidence bundle records which it was.

    answers keeps what each provider said separately. Agreement between
    independent resolvers is the thing that makes a spoofed answer expensive, so
    the reader should be able to see both sides of it rather than take the
    agreement on trust.
    """

    name: str
    records: tuple[str, ...]
    dnssec_validated: bool
    resolvers_agreed: bool
    answers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


class DnsResolver(Protocol):
    def lookup_txt(self, name: str) -> TxtLookup: ...


class DnsPublisher(Protocol):
    def publish_txt(self, domain: str, name: str, value: str, ttl: int) -> None: ...
