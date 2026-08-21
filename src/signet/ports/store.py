"""The system of record.

Issuers, daily batches, issued documents, the submissions ledger, cached evidence
and the append only audit log. Remove this and there is no evidence, which is the
product's entire output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Issuer:
    domain: str
    brand: str
    public_key: bytes
    enrolled: bool
    frozen: bool


class RecordStore(Protocol):
    def issuer(self, domain: str) -> Issuer | None: ...

    def record_submission(self, fingerprint: str, submitted_by: str) -> bool:
        """Record a submission. Returns False when this fingerprint was seen before."""
        ...

    def cache_get(self, namespace: str, key: str) -> Mapping[str, object] | None: ...

    def cache_put(self, namespace: str, key: str, value: Mapping[str, object]) -> None: ...

    def append_audit(self, run_id: str, event: str, detail: Mapping[str, object]) -> None: ...
