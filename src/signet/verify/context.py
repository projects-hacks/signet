"""What a check is given, and what it is not.

The context carries document data only. Ports arrive through each check's
constructor, so a check declares its own dependencies and none can quietly reach
for a capability it did not ask for.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from signet.core.mark import Mark


@dataclass(frozen=True, slots=True)
class VerificationContext:
    run_id: str
    content: bytes
    media_type: str
    submitted_by: str
    mark: Mark | None
    claimed_brand: str | None


def fingerprint(context: VerificationContext) -> str:
    """Identify a document for duplicate detection.

    A marked document is identified by what was signed, so the same receipt
    photographed twice is one document. An unmarked one falls back to the bytes,
    which is weaker but is all there is.
    """
    if context.mark is not None:
        return hashlib.sha256(context.mark.payload_bytes).hexdigest()
    return hashlib.sha256(context.content).hexdigest()
