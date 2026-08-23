"""Lookalike domains: the forgery a valid signature cannot see."""

from __future__ import annotations

import pytest

from signet.core.lookalike import (
    MAX_PERMUTATIONS,
    confusability,
    is_confusable,
    permutations,
)
from signet.core.mark import decode_mark, encode_mark
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer, generate_key
from signet.core.verdict import Outcome, Verdict, decide
from signet.ports.store import Issuer
from signet.verify.checks.lookalike import LookalikeCheck
from signet.verify.context import VerificationContext
from tests.fakes import FakeRecordStore

ENROLLED = "northpost.dev"


def context(issuer: str) -> VerificationContext:
    private, _ = generate_key()
    payload = canonicalize(
        {"iss": issuer, "ts": "2026-09-01T09:00:00Z", "id": "INV-1", "cls": "invoice"}
    )
    mark = decode_mark(encode_mark(payload, Ed25519Signer(private).sign(payload)))
    return VerificationContext(
        run_id="r",
        content=b"x",
        media_type="image/png",
        submitted_by="tester",
        mark=mark,
        claimed_brand="Northpost",
    )


def unmarked() -> VerificationContext:
    return VerificationContext(
        run_id="r",
        content=b"x",
        media_type="image/png",
        submitted_by="tester",
        mark=None,
        claimed_brand="Northpost",
    )


def issuer(domain: str, enrolled: bool = True) -> Issuer:
    return Issuer(
        domain=domain,
        brand="Northpost",
        public_key=b"\x00" * 32,
        enrolled=enrolled,
        frozen=False,
    )


def store(*issuers: Issuer) -> FakeRecordStore:
    return FakeRecordStore({record.domain: record for record in issuers})


def run(signing_domain: str, *issuers: Issuer) -> Outcome:
    return LookalikeCheck(store(*issuers)).run(context(signing_domain)).outcome


def test_a_domain_is_never_offered_as_a_permutation_of_itself() -> None:
    assert ENROLLED not in permutations(ENROLLED)


def test_permutations_carry_no_duplicates() -> None:
    generated = permutations(ENROLLED)
    assert len(generated) == len(set(generated))


def test_permutations_are_deterministic() -> None:
    """Evidence that cannot be replayed is not evidence."""
    assert permutations(ENROLLED) == permutations(ENROLLED)


def test_a_hyphen_is_offered_at_the_word_boundary() -> None:
    assert "north-post.dev" in permutations(ENROLLED)


def test_a_hyphenated_domain_is_offered_without_its_hyphen() -> None:
    assert ENROLLED in permutations("north-post.dev")


def test_a_zero_for_o_homoglyph_is_offered() -> None:
    assert "n0rthpost.dev" in permutations(ENROLLED)


def test_a_dropped_character_is_offered() -> None:
    assert "nothpost.dev" in permutations(ENROLLED)


def test_a_doubled_character_is_offered() -> None:
    assert "norrthpost.dev" in permutations(ENROLLED)


def test_a_neighbouring_key_is_offered_in_place_of_a_character() -> None:
    assert "nprthpost.dev" in permutations(ENROLLED)


def test_a_common_suffix_swap_is_offered() -> None:
    assert "northpost.com" in permutations(ENROLLED)


def test_a_domain_that_dropped_a_character_still_reaches_the_original() -> None:
    """Omission has to be invertible, or a probe of the neighbourhood is one-way."""
    assert ENROLLED in permutations("nothpost.dev")


def test_the_permutation_set_stays_within_its_cap() -> None:
    assert len(permutations("internationalpaymentsgroup.com")) <= MAX_PERMUTATIONS


def test_a_domain_with_no_label_permutes_to_nothing() -> None:
    assert permutations("") == ()


def test_every_permutation_is_confusable_with_the_domain_it_came_from() -> None:
    assert all(is_confusable(ENROLLED, variant) for variant in permutations(ENROLLED))


def test_a_hyphen_variant_is_confusable_with_the_plain_domain() -> None:
    assert is_confusable("north-post.dev", ENROLLED)


def test_a_dropped_character_is_confusable_with_the_plain_domain() -> None:
    assert is_confusable("nothpost.dev", ENROLLED)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (ENROLLED, "north-post.dev"),
        (ENROLLED, "nothpost.dev"),
        ("north-post.dev", "nothpost.dev"),
        ("n0rthp0st.dev", ENROLLED),
    ],
    ids=["hyphen", "omission", "hyphen-and-omission", "homoglyph"],
)
def test_confusability_reads_the_same_in_both_directions(left: str, right: str) -> None:
    assert is_confusable(left, right)
    assert is_confusable(right, left)


def test_an_unrelated_domain_is_not_confusable() -> None:
    assert not is_confusable(ENROLLED, "example.dev")


def test_a_shared_stem_is_not_enough_to_be_confusable() -> None:
    """Two edits is where unrelated brands that share a stem start colliding."""
    assert not is_confusable(ENROLLED, "southpost.dev")


def test_a_three_letter_name_needs_more_than_one_letter_in_common() -> None:
    """One edit is most of a short name, and short names differ by one constantly."""
    assert not is_confusable("abc.com", "abd.com")


def test_a_domain_is_perfectly_confusable_with_itself() -> None:
    assert confusability(ENROLLED, ENROLLED) == 1.0


def test_presentation_alone_still_scores_a_perfect_match() -> None:
    assert confusability("N0rth-Post.dev", ENROLLED) == 1.0


def test_the_same_name_under_another_suffix_scores_below_an_exact_match() -> None:
    assert confusability(ENROLLED, "northpost.com") < confusability(ENROLLED, ENROLLED)


def test_a_closer_imitation_scores_higher_than_a_looser_one() -> None:
    assert confusability(ENROLLED, "north-post.dev") > confusability(ENROLLED, "nothpost.dev")


@pytest.mark.parametrize("other", ["north-post.dev", "nothpost.dev", "example.com", "", "."])
def test_confusability_stays_between_zero_and_one(other: str) -> None:
    assert 0.0 <= confusability(ENROLLED, other) <= 1.0


def test_a_subdomain_is_judged_on_the_name_that_had_to_be_bought() -> None:
    assert is_confusable("billing.north-post.dev", ENROLLED)


def test_the_enrolled_domain_itself_passes() -> None:
    assert run(ENROLLED, issuer(ENROLLED)) is Outcome.PASS


def test_a_hyphenated_imitation_of_an_enrolled_domain_fails() -> None:
    assert run("north-post.dev", issuer(ENROLLED)) is Outcome.FAIL


def test_a_dropped_character_imitation_of_an_enrolled_domain_fails() -> None:
    assert run("nothpost.dev", issuer(ENROLLED)) is Outcome.FAIL


def test_the_same_name_under_another_suffix_fails() -> None:
    assert run("northpost.com", issuer(ENROLLED)) is Outcome.FAIL


def test_the_failure_names_the_imitation_and_the_domain_it_imitates() -> None:
    signal = LookalikeCheck(store(issuer(ENROLLED))).run(context("north-post.dev"))
    assert "north-post.dev" in signal.detail
    assert ENROLLED in signal.detail


def test_an_unrelated_signing_domain_is_not_an_imitation() -> None:
    """This check answers one question: does the signer imitate the named brand.

    A domain that resembles nothing is not imitating anything, so this passes and
    the identity check is the one that refuses the document. Reporting a failure
    here as well would say the same thing twice under a name that does not fit.
    """
    assert run("example.dev", issuer(ENROLLED)) is Outcome.PASS


def test_a_document_with_no_mark_is_unknown() -> None:
    assert LookalikeCheck(store()).run(unmarked()).outcome is Outcome.UNKNOWN


def test_a_store_with_nothing_enrolled_is_unknown() -> None:
    assert run("north-post.dev") is Outcome.UNKNOWN


def test_a_neighbour_that_was_never_enrolled_is_not_something_to_imitate() -> None:
    assert run("north-post.dev", issuer(ENROLLED, enrolled=False)) is Outcome.UNKNOWN


def test_the_closest_of_several_enrolled_neighbours_is_the_one_named() -> None:
    signal = LookalikeCheck(store(issuer(ENROLLED), issuer("nothpost.dev"))).run(
        context("north-post.dev")
    )
    assert ENROLLED in signal.detail


def test_an_imitation_flags_the_document() -> None:
    signal = LookalikeCheck(store(issuer(ENROLLED))).run(context("north-post.dev"))
    assert decide([signal]).verdict is Verdict.FLAGGED
