"""The canonical form that gets signed.

Both sides call canonicalize. An earlier design had issuance and verification
derive the payload independently from extracted text, and four out of five benign
formatting variants of the same document produced different hashes. The payload
now travels inside the mark, so verification signs over exactly the bytes it
received and never re-derives them.

Field keys are short because the canonical form is printed into a QR code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from signet.constants import (
    FIELD_CLASS,
    FIELD_DOCUMENT_ID,
    FIELD_ISSUER,
    FIELD_SEPARATOR,
    FIELD_TIMESTAMP,
    PAIR_SEPARATOR,
    REQUIRED_FIELDS,
)
from signet.errors import PayloadError


def _escape(value: str) -> str:
    for raw, encoded in (("%", "%25"), (FIELD_SEPARATOR, "%3B"), (PAIR_SEPARATOR, "%3D")):
        value = value.replace(raw, encoded)
    return value


def _unescape(value: str) -> str:
    for raw, encoded in ((FIELD_SEPARATOR, "%3B"), (PAIR_SEPARATOR, "%3D"), ("%", "%25")):
        value = value.replace(encoded, raw)
    return value


@dataclass(frozen=True, slots=True)
class CanonicalPayload:
    """An immutable, order-independent set of signed facts about one document."""

    fields: Mapping[str, str]

    @property
    def issuer(self) -> str:
        return self.fields[FIELD_ISSUER]

    @property
    def document_id(self) -> str:
        return self.fields[FIELD_DOCUMENT_ID]

    @property
    def document_class(self) -> str:
        return self.fields[FIELD_CLASS]

    @property
    def timestamp(self) -> str:
        return self.fields[FIELD_TIMESTAMP]

    def to_bytes(self) -> bytes:
        return canonicalize(self.fields)


def canonicalize(fields: Mapping[str, str]) -> bytes:
    """Render fields as the canonical byte string that gets signed.

    Sorted by key so callers cannot change the result by changing insertion order.
    Raises PayloadError when a required field is missing or a key is empty.
    """
    missing = REQUIRED_FIELDS - fields.keys()
    if missing:
        raise PayloadError(f"payload missing required field(s): {', '.join(sorted(missing))}")
    if any(not key for key in fields):
        raise PayloadError("payload contains an empty field key")
    # The key is escaped for the same reason the value is. Escaping only the
    # value let a single field keyed "amt=14.75;bal" render the same bytes as two
    # fields amt and bal, so one signature covered two different meanings. That
    # is the forgery this whole format exists to prevent.
    pairs = (f"{_escape(key)}{PAIR_SEPARATOR}{_escape(fields[key])}" for key in sorted(fields))
    return FIELD_SEPARATOR.join(pairs).encode("utf-8")


def parse(raw: str | bytes) -> CanonicalPayload:
    """Recover a payload from its canonical form.

    Raises PayloadError on a malformed pair, a duplicate key, or a missing
    required field.
    """
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    fields: dict[str, str] = {}
    for chunk in text.split(FIELD_SEPARATOR):
        key, separator, value = chunk.partition(PAIR_SEPARATOR)
        if not separator or not key:
            raise PayloadError(f"malformed field: {chunk!r}")
        if _unescape(key) in fields:
            raise PayloadError(f"duplicate field: {_unescape(key)}")
        fields[_unescape(key)] = _unescape(value)
    missing = REQUIRED_FIELDS - fields.keys()
    if missing:
        raise PayloadError(f"payload missing required field(s): {', '.join(sorted(missing))}")
    return CanonicalPayload(fields=fields)
