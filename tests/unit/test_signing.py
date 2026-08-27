from signet.core.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    decode_public_key,
    encode_public_key,
    generate_key,
)


def test_sign_and_verify() -> None:
    private, public = generate_key()
    signature = Ed25519Signer(private).sign(b"payload")
    assert Ed25519Verifier().verify(b"payload", signature, public)


def test_wrong_key_does_not_verify() -> None:
    private, _ = generate_key()
    _, other_public = generate_key()
    signature = Ed25519Signer(private).sign(b"payload")
    assert not Ed25519Verifier().verify(b"payload", signature, other_public)


def test_public_key_round_trips_through_a_txt_record() -> None:
    _, public = generate_key()
    assert decode_public_key(encode_public_key(public)) == public


def test_txt_record_fits_a_single_dns_string() -> None:
    _, public = generate_key()
    assert len(encode_public_key(public)) <= 255


def test_unrelated_txt_records_are_ignored() -> None:
    assert decode_public_key("v=spf1 include:example.com ~all") is None
    assert decode_public_key("v=DKIM1; k=rsa; p=MIGf") is None


def test_the_public_key_is_derived_from_the_private_one() -> None:
    """A stored pair can go out of step. A derived one cannot, which is what
    keeps the DNS record and the signing key from ever disagreeing."""
    private, public = generate_key()
    assert Ed25519Signer(private).public_key == public
