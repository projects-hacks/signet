"""Which record store the composition roots use.

Xano when it is configured, the local file otherwise. The choice lives here
rather than in the CLI and the API separately, because two copies of it drift
and the demo then runs on a different store from the one a judge inspects.

Fixtures force the local store regardless. A test that reaches the network is
not a test, and the whole suite has to pass with the cable out.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Final

from signet.adapters.local_store import LocalRecordStore
from signet.adapters.xano import XanoRecordStore
from signet.config import Settings
from signet.ports.store import RecordStore

SEED: Final = Path("assets/issuers.json")


def record_store(settings: Settings, local_path: Path) -> RecordStore:
    if settings.xano.configured and not settings.fixtures:
        base_url, api_key = settings.xano.values
        return XanoRecordStore(base_url, api_key)
    store = LocalRecordStore(local_path)
    if not local_path.is_file():
        _seed(store)
    return store


def _seed(store: LocalRecordStore) -> None:
    """Enrol the demo issuers into a store that does not exist yet.

    A fresh clone has no store, and with no enrolled issuers the identity
    check correctly fails every demo document, which reads as the product
    being broken rather than the clone being empty. The seed carries only
    facts that are already public: the brand, the domain, and the public key
    the domain itself publishes in DNS. Never applied to an existing store,
    because overwriting somebody's enrolments on startup is not seeding.
    """
    if not SEED.is_file():
        return
    for domain, entry in json.loads(SEED.read_text(encoding="utf-8")).items():
        if entry.get("enrolled"):
            store.enrol(domain, str(entry["brand"]), base64.b64decode(str(entry["publicKey"])))
