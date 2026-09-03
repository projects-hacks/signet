"""Sample documents a stranger can verify without preparing anything.

The submissions ledger is global on purpose, and it makes a static sample file
a one-shot: the first person to check it spends it, and everyone after is told,
truthfully and uselessly, that it is a duplicate. A product page that only
works for the first visitor does not demonstrate anything.

So the genuine sample is not a file. It is minted per request: the same page,
signed afresh, with a timestamp that makes each signature a new document to the
ledger. The printed fields never change, so the page still matches what was
signed, and the fields that do change are the ones no page prints. Every
visitor gets a document the system has never seen.

The dishonest samples are minted the same way, because their dishonesty is in
the relationship between the page and the signature, not in the signature. The
doctored page is signed over the account the issuer actually holds, so the page
disagrees with its own proof. The lookalike is signed consistently by the wrong
domain, so nothing disagrees and only the question of who signed it fails.

Keys arrive from the environment, or from the local key store when developing.
They are demo keys for demo domains, which is why letting a public endpoint
sign with them is acceptable; a real issuer's key never leaves the issuer.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from signet.adapters.page import stamp_mark
from signet.core.mark import encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer
from signet.errors import SignetError

MANIFEST: Final = "manifest.json"
DEFAULT_ROOT: Final = Path("assets/samples")
LOCAL_KEYS: Final = Path(".signet/keys")


class SampleError(SignetError):
    """A sample that cannot be produced, and why."""


@dataclass(frozen=True, slots=True)
class Sample:
    filename: str
    content: bytes


@dataclass(frozen=True, slots=True)
class _Kind:
    page: Path
    issuer: str
    fields: dict[str, str]


class SampleMinter:
    """Signs a known page afresh for whoever asks."""

    def __init__(self, root: Path = DEFAULT_ROOT, keys_env: str = "") -> None:
        self._root = root
        self._keys = _parse_keys(keys_env)
        self._kinds = _load_manifest(root) if (root / MANIFEST).is_file() else {}

    @property
    def available(self) -> bool:
        """Whether every declared kind can actually be minted."""
        return bool(self._kinds) and all(
            self._key_for(kind.issuer) is not None for kind in self._kinds.values()
        )

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(self._kinds)

    def mint(self, kind_name: str) -> Sample:
        kind = self._kinds.get(kind_name)
        if kind is None:
            raise SampleError(f"There is no sample called {kind_name!r}.")
        key = self._key_for(kind.issuer)
        if key is None:
            raise SampleError(f"No signing key is configured for {kind.issuer}.")

        # The timestamp is the whole trick. It is signed, it is never printed,
        # and it makes each minting a document the ledger has not seen.
        fields = {
            **kind.fields,
            "iss": kind.issuer,
            "ts": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }
        payload = canonicalize(fields)
        mark = encode_mark(payload, Ed25519Signer(key).sign(payload))
        return Sample(
            filename=f"sample-{kind_name}.png",
            content=stamp_mark(kind.page.read_bytes(), mark),
        )

    def _key_for(self, domain: str) -> bytes | None:
        configured = self._keys.get(domain)
        if configured is not None:
            return configured
        local = LOCAL_KEYS / f"{domain}.key"
        return local.read_bytes() if local.is_file() else None


def _parse_keys(keys_env: str) -> dict[str, bytes]:
    """domain=base64 pairs, comma separated, whitespace forgiven.

    The variable's own name is stripped if it is present. Setting this means
    pasting a value into somebody's dashboard, and pasting the whole
    NAME=value line is the obvious mistake to make. Failing on it would mean a
    deployment that starts, reports no samples, and never says why.
    """
    parsed: dict[str, bytes] = {}
    for entry in keys_env.removeprefix("SIGNET_SAMPLE_KEYS=").split(","):
        entry = entry.strip()
        if not entry:
            continue
        domain, separator, encoded = entry.partition("=")
        if not separator:
            raise SampleError("SIGNET_SAMPLE_KEYS entries are domain=base64key, comma separated.")
        try:
            parsed[domain.strip()] = base64.b64decode(encoded.strip(), validate=True)
        except ValueError as exc:
            raise SampleError(f"The sample key for {domain.strip()} is not base64.") from exc
    return parsed


def _load_manifest(root: Path) -> dict[str, _Kind]:
    raw = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    kinds: dict[str, _Kind] = {}
    for name, entry in raw.items():
        kinds[name] = _Kind(
            page=root / str(entry["page"]),
            issuer=str(entry["issuer"]),
            fields={key: str(value) for key, value in entry["fields"].items()},
        )
    return kinds
