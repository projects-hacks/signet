"""A file backed record store.

Two reasons this exists rather than everything going through Xano.

The demo has to run with the conference network unplugged, and a verdict that
depends on a round trip is a verdict that fails on stage.

And it makes the CLI usable before any backend exists, which is how the whole
pipeline got exercised end to end in the first place.

One JSON file, rewritten atomically. Not concurrent, and it does not pretend to
be: a single operator on one laptop is the whole design brief.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from signet.ports.store import Issuer

DEFAULT_PATH = Path(".signet/store.json")


class LocalRecordStore:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path
        self._data: dict[str, Any] = {
            "issuers": {},
            "submissions": {},
            "cache": {},
            "audit": [],
        }
        if path.is_file():
            self._data.update(json.loads(path.read_text(encoding="utf-8")))

    def issuer(self, domain: str) -> Issuer | None:
        record = self._data["issuers"].get(domain)
        if record is None:
            return None
        return Issuer(
            domain=domain,
            brand=str(record.get("brand", "")),
            public_key=bytes.fromhex(str(record.get("public_key_hex", ""))),
            enrolled=bool(record.get("enrolled", True)),
            frozen=bool(record.get("frozen", False)),
        )

    def enrolled_issuers(self) -> tuple[Issuer, ...]:
        found = (self.issuer(domain) for domain in self._data["issuers"])
        return tuple(issuer for issuer in found if issuer is not None and issuer.enrolled)

    def enrol(self, domain: str, brand: str, public_key: bytes) -> None:
        self._data["issuers"][domain] = {
            "brand": brand,
            "public_key_hex": public_key.hex(),
            "enrolled": True,
            "frozen": False,
        }
        self._flush()

    def record_submission(self, fingerprint: str, submitted_by: str) -> bool:
        if fingerprint in self._data["submissions"]:
            return False
        self._data["submissions"][fingerprint] = submitted_by
        self._flush()
        return True

    def cache_get(self, namespace: str, key: str) -> Mapping[str, object] | None:
        value = self._data["cache"].get(f"{namespace}/{key}")
        return value if isinstance(value, dict) else None

    def cache_put(self, namespace: str, key: str, value: Mapping[str, object]) -> None:
        self._data["cache"][f"{namespace}/{key}"] = dict(value)
        self._flush()

    def append_audit(self, run_id: str, event: str, detail: Mapping[str, object]) -> None:
        self._data["audit"].append({"run_id": run_id, "event": event, "detail": dict(detail)})
        self._flush()

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the target and rename, so an interrupted run cannot leave
        # a half written ledger that silently forgets a submission.
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self._path)
