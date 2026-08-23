"""The canonical form that gets signed.

Both sides call canonicalize. An earlier design had issuance and verification
derive the payload independently from extracted text, and four out of five benign
formatting variants of the same document produced different hashes. The payload
now travels inside the mark, so verification signs over exactly the bytes it
received and never re-derives them.

Field keys are short because the canonical form is printed into a QR code.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

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

# Control characters and lone surrogates. Everything else, including combining
# marks and the joiners that legitimate scripts need, is left alone: refusing a
# real issuer's name is the expensive kind of mistake here.
_FORBIDDEN_CATEGORIES: Final = frozenset({"Cc", "Cs"})


def _reject_unrenderable(label: str, text: str) -> None:
    # A payload is read by a person and printed into a mark. A newline inside an
    # issuer lets the line a reader sees end at bluebottle.com while the signed
    # bytes carry somewhere else, and a lone surrogate cannot be encoded at all,
    # so both are refused at the boundary rather than carried into a verdict.
    if any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in text):
        raise PayloadError(f"{label} contains a forbidden character: {text!r}")


def _require_fields(fields: Mapping[str, str]) -> None:
    missing = REQUIRED_FIELDS - fields.keys()
    if missing:
        raise PayloadError(f"payload missing required field(s): {', '.join(sorted(missing))}")
    # An empty required value is a missing field wearing the key. The check above
    # cannot see it, and iss= names no domain to look a key up at.
    empty = sorted(key for key in REQUIRED_FIELDS if not fields[key].strip())
    if empty:
        raise PayloadError(f"payload has empty required field(s): {', '.join(empty)}")


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
    Raises PayloadError when a required field is missing or empty, when a key is
    empty, or when any key or value holds a character a mark cannot carry.
    """
    _require_fields(fields)
    if any(not key for key in fields):
        raise PayloadError("payload contains an empty field key")
    for key, value in fields.items():
        _reject_unrenderable(f"field key {key!r}", key)
        _reject_unrenderable(f"field {key!r}", value)
    # The key is escaped for the same reason the value is. Escaping only the
    # value let a single field keyed "amt=14.75;bal" render the same bytes as two
    # fields amt and bal, so one signature covered two different meanings. That
    # is the forgery this whole format exists to prevent.
    pairs = (f"{_escape(key)}{PAIR_SEPARATOR}{_escape(fields[key])}" for key in sorted(fields))
    return FIELD_SEPARATOR.join(pairs).encode("utf-8")


def parse(raw: str | bytes) -> CanonicalPayload:
    """Recover a payload from its canonical form.

    Raises PayloadError on a malformed pair, a duplicate key, a forbidden
    character, or a missing or empty required field.
    """
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    fields: dict[str, str] = {}
    for chunk in text.split(FIELD_SEPARATOR):
        raw_key, separator, raw_value = chunk.partition(PAIR_SEPARATOR)
        if not separator or not raw_key:
            raise PayloadError(f"malformed field: {chunk!r}")
        key, value = _unescape(raw_key), _unescape(raw_value)
        if key in fields:
            raise PayloadError(f"duplicate field: {key}")
        _reject_unrenderable(f"field key {key!r}", key)
        _reject_unrenderable(f"field {key!r}", value)
        fields[key] = value
    _require_fields(fields)
    return CanonicalPayload(fields=fields)
