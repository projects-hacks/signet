from __future__ import annotations

from collections.abc import Mapping

from signet.ports.store import Issuer


class FakeRecordStore:
    def __init__(self, issuers: dict[str, Issuer] | None = None) -> None:
        self.issuers = issuers or {}
        self.submissions: set[str] = set()
        self.cache: dict[tuple[str, str], Mapping[str, object]] = {}
        self.audit: list[tuple[str, str, Mapping[str, object]]] = []

    def issuer(self, domain: str) -> Issuer | None:
        return self.issuers.get(domain)

    def record_submission(self, fingerprint: str, submitted_by: str) -> bool:
        if fingerprint in self.submissions:
            return False
        self.submissions.add(fingerprint)
        return True

    def cache_get(self, namespace: str, key: str) -> Mapping[str, object] | None:
        return self.cache.get((namespace, key))

    def cache_put(self, namespace: str, key: str, value: Mapping[str, object]) -> None:
        self.cache[(namespace, key)] = value

    def append_audit(self, run_id: str, event: str, detail: Mapping[str, object]) -> None:
        self.audit.append((run_id, event, detail))
