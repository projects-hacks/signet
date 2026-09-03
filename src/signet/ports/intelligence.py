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
    """What the open web says a brand publishes, and how firmly it says it.

    The two are not the same claim. An entity record naming a company's website
    is an assertion about that company. A page that ranked for the company's
    name is a page that mentioned the words, and treating the second as the
    first refused a legitimate enrolment: searching a company that does not
    exist returned an unrelated northpost.org, which was then strong enough to
    contradict the domain the signer actually controls.

    So callers that can accuse somebody require `authoritative`. Callers that
    only inform a person may use the domain either way.
    """

    brand: str
    canonical_domain: str | None
    sources: tuple[str, ...]
    authoritative: bool = False


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
