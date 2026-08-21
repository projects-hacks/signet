from __future__ import annotations

from signet.ports.intelligence import BrandResolution, Diligence


class FakeEntityResolver:
    def __init__(self, canonical: dict[str, str] | None = None) -> None:
        self.canonical = canonical or {}
        self.calls: list[str] = []

    def resolve_brand(self, brand: str) -> BrandResolution:
        self.calls.append(brand)
        return BrandResolution(
            brand=brand,
            canonical_domain=self.canonical.get(brand),
            sources=("fake",),
        )

    def diligence(self, domain: str, brand: str) -> Diligence:
        return Diligence(
            domain=domain,
            exists=True,
            published_domain=self.canonical.get(brand),
            adverse_mentions=(),
            sources=("fake",),
        )
