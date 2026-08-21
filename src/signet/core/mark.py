"""The mark: what gets printed on the document.

A document is photographed far more often than it is forwarded as a file, and a
photograph destroys every byte of the original. Only what is visually printed
survives, so the mark carries the payload and the signature and nothing else.

The Merkle proof deliberately stays out. Including it pushes the QR past version
8, where decoding off crumpled thermal paper becomes unreliable. It is fetched
online in the rare case a date is disputed.

A short locator prints beneath the code so a damaged mark degrades to a slower
online verification rather than to none.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from signet.constants import MARK_SEPARATOR, MARK_VERSION, MAX_MARK_BYTES
from signet.core.payload import CanonicalPayload, parse
from signet.errors import MarkError


@dataclass(frozen=True, slots=True)
class Mark:
    payload: CanonicalPayload
    payload_bytes: bytes
    signature: bytes


def _b32(raw: bytes) -> str:
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _unb32(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 8)
    return base64.b32decode(padded)


def encode_mark(payload_bytes: bytes, signature: bytes) -> str:
    """Render the string that goes into the QR code.

    Base32 keeps the signature inside the QR alphanumeric mode, which is denser
    than byte mode for the same content.

    Raises MarkError when the result would exceed MAX_MARK_BYTES.
    """
    text = MARK_SEPARATOR.join(
        (MARK_VERSION, payload_bytes.decode("utf-8"), _b32(signature)),
    )
    if len(text.encode("utf-8")) > MAX_MARK_BYTES:
        raise MarkError(
            f"mark is {len(text.encode('utf-8'))} bytes, over the {MAX_MARK_BYTES} byte limit"
        )
    return text


def decode_mark(text: str) -> Mark:
    """Recover a mark from a scanned code.

    The signature is split off the end rather than by field position, because the
    payload itself contains the separator.

    Raises MarkError on a wrong version, a missing signature, or a bad payload.
    """
    version, separator, remainder = text.partition(MARK_SEPARATOR)
    if not separator or version != MARK_VERSION:
        raise MarkError(f"unrecognised mark version: {version!r}")
    payload_text, separator, encoded_signature = remainder.rpartition(MARK_SEPARATOR)
    if not separator or not payload_text:
        raise MarkError("mark has no signature segment")
    try:
        signature = _unb32(encoded_signature)
    except ValueError as exc:
        raise MarkError("signature is not valid base32") from exc
    if len(signature) != 64:
        raise MarkError(f"signature is {len(signature)} bytes, expected 64")
    return Mark(
        payload=parse(payload_text),
        payload_bytes=payload_text.encode("utf-8"),
        signature=signature,
    )


def format_locator(issuer: str, document_id: str) -> str:
    """The human readable fallback printed beneath the code."""
    return f"{issuer}/{document_id}"


def parse_locator(text: str) -> tuple[str, str]:
    """Split a locator into issuer and document id.

    Raises MarkError when the separator is absent or either half is empty.
    """
    issuer, separator, document_id = text.strip().partition("/")
    if not separator or not issuer or not document_id:
        raise MarkError(f"malformed locator: {text!r}")
    return issuer, document_id
