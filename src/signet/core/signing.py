"""Ed25519 signing over the canonical payload.

Ed25519 because the public key is 32 bytes, which fits a DNS TXT record with room
to spare. RSA at a comparable strength does not.
"""

from __future__ import annotations

import base64
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from signet.constants import DNS_KEY_ALGORITHM, DNS_KEY_VERSION


class Signer(Protocol):
    def sign(self, payload: bytes) -> bytes: ...


class SignatureVerifier(Protocol):
    def verify(self, payload: bytes, signature: bytes, public_key: bytes) -> bool: ...


def generate_key() -> tuple[bytes, bytes]:
    """Return a new (private_key, public_key) pair as raw bytes."""
    private = Ed25519PrivateKey.generate()
    return (
        private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        ),
        private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ),
    )


class Ed25519Signer:
    def __init__(self, private_key: bytes) -> None:
        self._key = Ed25519PrivateKey.from_private_bytes(private_key)

    def sign(self, payload: bytes) -> bytes:
        return self._key.sign(payload)


class Ed25519Verifier:
    def verify(self, payload: bytes, signature: bytes, public_key: bytes) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload)
        except (InvalidSignature, ValueError):
            return False
        return True


def encode_public_key(public_key: bytes) -> str:
    """Render a public key as the DNS TXT record value."""
    encoded = base64.b64encode(public_key).decode("ascii")
    return f"v={DNS_KEY_VERSION}; k={DNS_KEY_ALGORITHM}; p={encoded}"


def decode_public_key(record: str) -> bytes | None:
    """Extract the raw public key from a TXT record, or None if it is not ours.

    Returns None rather than raising: a domain may publish many TXT records and
    finding an unrelated one is normal, not an error.
    """
    tags = dict(
        (part.split("=", 1)[0].strip(), part.split("=", 1)[1].strip())
        for part in record.split(";")
        if "=" in part
    )
    if tags.get("v") != DNS_KEY_VERSION or tags.get("k") != DNS_KEY_ALGORITHM:
        return None
    encoded = tags.get("p")
    if not encoded:
        return None
    try:
        key = base64.b64decode(encoded, validate=True)
    except ValueError:
        return None
    return key if len(key) == 32 else None
