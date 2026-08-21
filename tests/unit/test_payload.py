import pytest

from signet.core.payload import CanonicalPayload, canonicalize, parse
from signet.errors import PayloadError

FIELDS = {
    "iss": "bluebottle.com",
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-88213104",
    "cls": "receipt",
    "amt": "14.75",
    "cur": "USD",
}


def test_canonical_form_is_order_independent() -> None:
    reordered = dict(reversed(list(FIELDS.items())))
    assert canonicalize(FIELDS) == canonicalize(reordered)


def test_round_trip_preserves_fields() -> None:
    assert parse(canonicalize(FIELDS)).fields == FIELDS


def test_separators_in_values_survive_round_trip() -> None:
    awkward = {**FIELDS, "note": "a=b;c=d 100%"}
    assert parse(canonicalize(awkward)).fields["note"] == "a=b;c=d 100%"


def test_missing_required_field_is_rejected() -> None:
    with pytest.raises(PayloadError, match="missing required"):
        canonicalize({"iss": "bluebottle.com"})


def test_duplicate_key_is_rejected() -> None:
    with pytest.raises(PayloadError, match="duplicate"):
        parse("cls=receipt;id=1;iss=a.com;iss=b.com;ts=2026-01-01T00:00:00Z")


def test_accessors_expose_required_fields() -> None:
    payload = CanonicalPayload(fields=FIELDS)
    assert payload.issuer == "bluebottle.com"
    assert payload.document_id == "R-88213104"
    assert payload.document_class == "receipt"
    assert payload.timestamp == "2026-08-20T09:14:00Z"
