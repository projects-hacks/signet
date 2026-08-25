"""Which record store the composition roots use.

Xano when it is configured, the local file otherwise. The choice lives here
rather than in the CLI and the API separately, because two copies of it drift
and the demo then runs on a different store from the one a judge inspects.

Fixtures force the local store regardless. A test that reaches the network is
not a test, and the whole suite has to pass with the cable out.
"""

from __future__ import annotations

from pathlib import Path

from signet.adapters.local_store import LocalRecordStore
from signet.adapters.xano import XanoRecordStore
from signet.config import Settings
from signet.ports.store import RecordStore


def record_store(settings: Settings, local_path: Path) -> RecordStore:
    if settings.xano.configured and not settings.fixtures:
        base_url, api_key = settings.xano.values
        return XanoRecordStore(base_url, api_key)
    return LocalRecordStore(local_path)
