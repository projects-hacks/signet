"""Live questions about a counterparty.

Brand to canonical domain runs once per issuer at enrolment, where it can be slow
and a human can overrule it. Diligence runs on the unsigned path and is cached per
counterparty, so call volume tracks distinct merchants rather than traffic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BrandResolution:
    brand: str
    canonical_domain: str | None
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Diligence:
    domain: str
    exists: bool
    published_domain: str | None
    adverse_mentions: tuple[str, ...]
    sources: tuple[str, ...]


class EntityResolver(Protocol):
    def resolve_brand(self, brand: str) -> BrandResolution: ...

    def diligence(self, domain: str, brand: str) -> Diligence: ...
