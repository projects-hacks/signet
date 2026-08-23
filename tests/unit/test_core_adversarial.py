from __future__ import annotations

import base64

import pytest

from signet.core.mark import decode_mark, encode_mark, format_locator, parse_locator
from signet.core.merkle import InclusionProof, build_tree, leaf_hash, verify_inclusion
from signet.core.payload import canonicalize, parse
from signet.core.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    decode_public_key,
    encode_public_key,
    generate_key,
)
from signet.core.verdict import Outcome, Signal, Verdict, decide
from signet.errors import MarkError, PayloadError

FIELDS = {
    "iss": "bluebottle.com",
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-88213104",
    "cls": "receipt",
}

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _signal(name: str, outcome: Outcome) -> Signal:
    return Signal(name, outcome, f"{name} is {outcome.value}", "test")


def _leaves(count: int) -> list[bytes]:
    return [f"document-{i}".encode() for i in range(count)]


# Canonicalisation


def test_two_different_field_maps_cannot_canonicalise_to_the_same_bytes() -> None:
    one_field = {**FIELDS, "amt=14.75;bal": "0.00"}
    two_fields = {**FIELDS, "amt": "14.75", "bal": "0.00"}

    assert one_field != two_fields
    assert canonicalize(one_field) != canonicalize(two_fields)


def test_a_key_containing_the_pair_separator_survives_the_round_trip() -> None:
    fields = {**FIELDS, "a=b": "c"}

    assert parse(canonicalize(fields)).fields == fields


def test_a_key_containing_the_field_separator_survives_the_round_trip() -> None:
    """Escaping the key is what closes the collision, so refusing it buys nothing.

    A key holding the field separator used to render bytes that parsed back as two
    fields, which is why keys are now escaped exactly as values are. Once the
    separator cannot leak out of a key, the key is ordinary data.
    """
    fields = {**FIELDS, "a;b": "c"}

    assert parse(canonicalize(fields)).fields == fields


def test_a_key_containing_the_escape_character_survives_the_round_trip() -> None:
    fields = {**FIELDS, "a%b": "c"}

    assert parse(canonicalize(fields)).fields == fields


def test_an_empty_required_field_value_is_refused() -> None:
    with pytest.raises(PayloadError):
        parse("cls=receipt;id=R-1;iss=;ts=2026-01-01T00:00:00Z")


def test_an_issuer_carrying_a_newline_is_refused() -> None:
    with pytest.raises(PayloadError):
        parse("cls=receipt;id=R-1;iss=a.com\nevil.com;ts=2026-01-01T00:00:00Z")


def test_text_that_cannot_be_encoded_raises_a_payload_error() -> None:
    with pytest.raises(PayloadError):
        canonicalize({**FIELDS, "note": "\ud800"})


def test_values_holding_every_separator_survive_the_round_trip() -> None:
    fields = {**FIELDS, "note": "a=b;c=d 100%"}

    assert parse(canonicalize(fields)).fields == fields


def test_values_that_already_look_escaped_survive_the_round_trip() -> None:
    fields = {**FIELDS, "note": "%3B%3D%25 %2525 %%3B"}

    assert parse(canonicalize(fields)).fields == fields


def test_keys_differing_only_by_case_stay_distinct() -> None:
    fields = {**FIELDS, "note": "lower", "NOTE": "upper"}

    assert parse(canonicalize(fields)).fields == fields


def test_a_very_long_value_survives_the_round_trip() -> None:
    fields = {**FIELDS, "note": "x=%;" * 5000}

    assert parse(canonicalize(fields)).fields == fields


def test_unicode_that_normalises_alike_stays_distinct() -> None:
    composed = {**FIELDS, "note": "caf\u00e9"}
    decomposed = {**FIELDS, "note": "cafe\u0301"}

    assert composed != decomposed
    assert canonicalize(composed) != canonicalize(decomposed)


def test_insertion_order_never_changes_the_signed_bytes() -> None:
    reordered = dict(reversed(list(FIELDS.items())))

    assert canonicalize(FIELDS) == canonicalize(reordered)


def test_a_repeated_key_in_a_scanned_payload_is_refused() -> None:
    with pytest.raises(PayloadError, match="duplicate"):
        parse("cls=receipt;id=R-1;iss=a.com;iss=b.com;ts=2026-01-01T00:00:00Z")


def test_an_empty_chunk_in_a_scanned_payload_is_refused() -> None:
    with pytest.raises(PayloadError):
        parse("cls=receipt;;id=R-1;iss=a.com;ts=2026-01-01T00:00:00Z")


def test_an_empty_payload_is_refused() -> None:
    with pytest.raises(PayloadError):
        parse("")


# Mark encoding


def test_a_payload_holding_the_mark_separator_round_trips_unchanged() -> None:
    payload = canonicalize({**FIELDS, "note": "a|b"})
    signature = bytes(range(64))

    mark = decode_mark(encode_mark(payload, signature))

    assert mark.payload_bytes == payload
    assert mark.signature == signature


def test_a_payload_ending_in_something_shaped_like_a_signature_round_trips() -> None:
    decoy = base64.b32encode(bytes(64)).decode("ascii").rstrip("=")
    payload = canonicalize({**FIELDS, "note": f"|{decoy}"})
    signature = bytes(range(64))

    mark = decode_mark(encode_mark(payload, signature))

    assert mark.payload_bytes == payload
    assert mark.signature == signature


def test_a_signature_has_exactly_one_valid_base32_encoding() -> None:
    payload = canonicalize(FIELDS)
    signature = bytes(range(64))
    encoded = base64.b32encode(signature).decode("ascii").rstrip("=")
    padded_out = BASE32_ALPHABET[BASE32_ALPHABET.index(encoded[-1]) | 0b111]

    with pytest.raises(MarkError):
        decode_mark(f"S1|{payload.decode()}|{encoded[:-1]}{padded_out}")


def test_a_lowercase_signature_segment_is_refused() -> None:
    payload = canonicalize(FIELDS)
    encoded = base64.b32encode(bytes(range(64))).decode("ascii").rstrip("=")

    with pytest.raises(MarkError):
        decode_mark(f"S1|{payload.decode()}|{encoded.lower()}")


def test_a_signature_of_the_wrong_length_is_refused() -> None:
    payload = canonicalize(FIELDS)
    encoded = base64.b32encode(bytes(32)).decode("ascii").rstrip("=")

    with pytest.raises(MarkError, match="expected 64"):
        decode_mark(f"S1|{payload.decode()}|{encoded}")


def test_a_mark_with_no_signature_segment_is_refused() -> None:
    payload = canonicalize(FIELDS)

    with pytest.raises(MarkError, match="no signature"):
        decode_mark(f"S1|{payload.decode()}")


def test_an_unknown_mark_version_is_refused() -> None:
    payload = canonicalize(FIELDS)
    encoded = base64.b32encode(bytes(range(64))).decode("ascii").rstrip("=")

    with pytest.raises(MarkError, match="unrecognised"):
        decode_mark(f"S2|{payload.decode()}|{encoded}")


# Locators


def test_an_issuer_holding_the_locator_separator_is_refused() -> None:
    """An issuer is a domain, so it is the half that gives up the separator.

    A locator has to split somewhere, and only one half can hold the separator.
    Document ids do, routinely, and are kept whole; a domain never does, so an
    issuer carrying one is refused rather than encoded into an ambiguous string.
    """
    with pytest.raises(MarkError, match="malformed"):
        format_locator("bluebottle.com/x", "R-1")


def test_two_different_pairs_cannot_share_a_locator() -> None:
    assert parse_locator("bluebottle.com/x/R-1") == ("bluebottle.com", "x/R-1")
    with pytest.raises(MarkError):
        format_locator("bluebottle.com/x", "R-1")


def test_a_document_id_holding_a_slash_round_trips() -> None:
    assert parse_locator(format_locator("bluebottle.com", "x/R-1")) == ("bluebottle.com", "x/R-1")


def test_a_locator_with_an_empty_half_is_refused() -> None:
    with pytest.raises(MarkError, match="malformed"):
        parse_locator("bluebottle.com/")


# Signing


def test_the_verifier_never_raises_on_a_hostile_signature() -> None:
    """A signature is bytes, and anything else is a wiring fault that must surface.

    Every byte string a scanner can hand over, of any length or content, returns
    False rather than raising. A non-bytes signature is not a hostile document but
    a caller passing the wrong type, and swallowing that would report the bug as
    "this document was altered after it was issued", accusing an honest issuer.
    """
    _, public = generate_key()
    verifier = Ed25519Verifier()
    hostile = [b"", b"short", bytes(63), bytes(64), bytes(65), b"\xff" * 64, bytes(range(64))]

    assert not any(verifier.verify(b"payload", signature, public) for signature in hostile)
    with pytest.raises(TypeError):
        verifier.verify(b"payload", "not-bytes", public)  # type: ignore[arg-type]


def test_the_verifier_returns_false_for_a_public_key_of_the_wrong_length() -> None:
    assert Ed25519Verifier().verify(b"payload", bytes(64), b"short") is False


def test_a_public_key_has_exactly_one_valid_record_encoding() -> None:
    _, public = generate_key()
    encoded = base64.b64encode(public).decode("ascii")
    padded_out = BASE64_ALPHABET[BASE64_ALPHABET.index(encoded[-2]) | 0b11]
    mutated = f"{encoded[:-2]}{padded_out}{encoded[-1]}"

    assert decode_public_key(f"v=SIGNET1; k=ed25519; p={mutated}") is None


def test_a_record_carrying_two_key_tags_is_refused() -> None:
    _, public = generate_key()
    intruder = base64.b64encode(bytes(32)).decode("ascii")

    assert decode_public_key(f"{encode_public_key(public)}; p={intruder}") is None


def test_a_genuine_record_round_trips() -> None:
    _, public = generate_key()

    assert decode_public_key(encode_public_key(public)) == public


def test_a_foreign_txt_record_is_ignored() -> None:
    assert decode_public_key("v=spf1 include:example.com ~all") is None
    assert decode_public_key("v=SIGNET1; k=rsa; p=AAAA") is None


def test_a_signature_over_one_payload_does_not_verify_another() -> None:
    private, public = generate_key()
    payload = canonicalize(FIELDS)
    signature = Ed25519Signer(private).sign(payload)

    assert not Ed25519Verifier().verify(canonicalize({**FIELDS, "id": "R-2"}), signature, public)


# Merkle


def test_a_leaf_hash_cannot_collide_with_an_internal_node_hash() -> None:
    left, right = _leaves(2)

    assert leaf_hash(left + right) != build_tree([left, right]).root


def test_an_internal_node_cannot_be_passed_off_as_a_leaf() -> None:
    leaves = _leaves(4)
    left_subtree = build_tree(leaves[:2]).root
    right_subtree = build_tree(leaves[2:]).root
    forged_proof = InclusionProof(steps=((True, right_subtree),))

    assert not verify_inclusion(left_subtree, forged_proof, build_tree(leaves).root)


def test_trees_of_different_shapes_do_not_share_a_root() -> None:
    first, second, third = _leaves(3)
    promoted = build_tree([build_tree([first, second]).root, third])

    assert build_tree([first, second, third]).root != promoted.root


def test_a_proof_from_one_tree_does_not_validate_against_another_root() -> None:
    mine = build_tree(_leaves(8))
    theirs = build_tree([f"other-{i}".encode() for i in range(8)])

    assert not verify_inclusion(_leaves(8)[0], theirs.proof(0), mine.root)


@pytest.mark.parametrize("count", [1, 2, 3, 5, 7, 9, 33])
def test_every_leaf_of_an_odd_batch_proves_inclusion(count: int) -> None:
    leaves = _leaves(count)
    tree = build_tree(leaves)

    assert all(verify_inclusion(leaf, tree.proof(i), tree.root) for i, leaf in enumerate(leaves))


def test_a_repeated_leaf_still_proves_inclusion_at_both_positions() -> None:
    first, second = _leaves(2)
    tree = build_tree([first, first, second, second])

    assert verify_inclusion(first, tree.proof(0), tree.root)
    assert verify_inclusion(first, tree.proof(1), tree.root)


def test_a_leaf_index_outside_the_tree_is_refused() -> None:
    tree = build_tree(_leaves(4))

    with pytest.raises(IndexError):
        tree.proof(4)
    with pytest.raises(IndexError):
        tree.proof(-1)


def test_an_empty_batch_has_no_root() -> None:
    with pytest.raises(ValueError, match="zero leaves"):
        build_tree([])


def test_a_single_document_batch_roots_at_its_leaf_hash() -> None:
    only = _leaves(1)[0]
    tree = build_tree([only])

    assert tree.root == leaf_hash(only)
    assert tree.proof(0).size == 0


# Verdict


def test_a_repeated_signal_name_cannot_upgrade_a_verdict() -> None:
    signals = [
        _signal("signature", Outcome.UNKNOWN),
        _signal("signature", Outcome.PASS),
        _signal("identity", Outcome.PASS),
    ]

    assert decide(signals).verdict is not Verdict.CERTIFIED


def test_deciding_on_no_signals_is_total() -> None:
    decision = decide([])

    assert decision.verdict is Verdict.UNSIGNED
    assert decision.signals == ()


@pytest.mark.parametrize("signature_outcome", list(Outcome))
@pytest.mark.parametrize("identity_outcome", list(Outcome))
def test_every_outcome_pair_produces_a_verdict(
    signature_outcome: Outcome, identity_outcome: Outcome
) -> None:
    decision = decide(
        [_signal("signature", signature_outcome), _signal("identity", identity_outcome)]
    )

    assert isinstance(decision.verdict, Verdict)
    assert decision.reason


def test_only_a_passing_signature_and_identity_certify() -> None:
    for signature_outcome in Outcome:
        for identity_outcome in Outcome:
            decision = decide(
                [_signal("signature", signature_outcome), _signal("identity", identity_outcome)]
            )
            certified = decision.verdict is Verdict.CERTIFIED
            assert certified == (
                signature_outcome is Outcome.PASS and identity_outcome is Outcome.PASS
            )


def test_the_headline_names_the_most_consequential_failure() -> None:
    signals = [
        _signal("fidelity", Outcome.FAIL),
        _signal("duplicate", Outcome.FAIL),
        _signal("signature", Outcome.FAIL),
    ]

    assert decide(signals).reason == "signature is fail"


def test_an_unrecognised_signal_name_ranks_below_every_critical_check() -> None:
    signals = [_signal("weather", Outcome.FAIL), _signal("fidelity", Outcome.FAIL)]

    assert decide(signals).reason == "fidelity is fail"


def test_an_unrecognised_signal_can_still_flag_on_its_own() -> None:
    decision = decide([_signal("weather", Outcome.FAIL)])

    assert decision.verdict is Verdict.FLAGGED
    assert decision.reason == "weather is fail"


def test_every_signal_is_carried_into_the_decision() -> None:
    signals = [_signal("signature", Outcome.PASS), _signal("identity", Outcome.PASS)]

    assert decide(signals).signals == tuple(signals)
