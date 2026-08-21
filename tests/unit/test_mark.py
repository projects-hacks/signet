import pytest

from signet.core.mark import decode_mark, encode_mark, format_locator, parse_locator
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, Ed25519Verifier, generate_key
from signet.errors import MarkError

FIELDS = {
    "iss": "bluebottle.com",
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-88213104",
    "cls": "receipt",
    "amt": "14.75",
    "cur": "USD",
}


def test_mark_round_trips_and_verifies() -> None:
    private, public = generate_key()
    payload = canonicalize(FIELDS)
    signature = Ed25519Signer(private).sign(payload)

    mark = decode_mark(encode_mark(payload, signature))

    assert mark.payload.fields == FIELDS
    assert Ed25519Verifier().verify(mark.payload_bytes, mark.signature, public)


def test_mark_stays_inside_the_qr_budget() -> None:
    private, _ = generate_key()
    payload = canonicalize(FIELDS)
    text = encode_mark(payload, Ed25519Signer(private).sign(payload))
    assert len(text.encode("utf-8")) <= 300


def test_oversized_payload_is_refused() -> None:
    private, _ = generate_key()
    fields = {**FIELDS, "note": "x" * 400}
    payload = canonicalize(fields)
    with pytest.raises(MarkError, match="over the"):
        encode_mark(payload, Ed25519Signer(private).sign(payload))


def test_tampering_breaks_verification() -> None:
    private, public = generate_key()
    payload = canonicalize(FIELDS)
    signature = Ed25519Signer(private).sign(payload)
    tampered = canonicalize({**FIELDS, "amt": "1475.00"})

    assert not Ed25519Verifier().verify(tampered, signature, public)


def test_unknown_version_is_refused() -> None:
    with pytest.raises(MarkError, match="unrecognised"):
        decode_mark("S9|cls=receipt;id=1;iss=a.com;ts=t|AAAA")


def test_locator_round_trips() -> None:
    assert parse_locator(format_locator("bluebottle.com", "R-1")) == ("bluebottle.com", "R-1")


def test_malformed_locator_is_refused() -> None:
    with pytest.raises(MarkError, match="malformed"):
        parse_locator("bluebottle.com")
