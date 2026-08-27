"""When the machine will not guess, a person answers.

The tests that matter are the ones establishing what a person cannot do. They
supply one input, what the page says, and the same rule reaches the verdict.
"""

from __future__ import annotations

from typing import Any

import pytest

from signet.core.verdict import Outcome, Signal, Verdict, decide
from signet.verify.adjudication import (
    NotAdjudicable,
    apply_reading,
    uncertain_fields,
)

THRESHOLD = 0.8


def field(name: str, signed: str, printed: str | None, confidence: float) -> dict[str, Any]:
    return {
        "field": name,
        "signed": signed,
        "printed": printed,
        "confidence": confidence,
        "agrees": printed is not None and printed == signed,
    }


def fidelity(*fields: dict[str, Any]) -> Signal:
    return Signal(
        "fidelity",
        Outcome.UNKNOWN,
        "Needs a human.",
        "extraction",
        {"threshold": THRESHOLD, "compared": list(fields)},
    )


def signals(*fields: dict[str, Any]) -> list[Signal]:
    return [
        Signal("signature", Outcome.PASS, "Issued by northpost.dev.", "dns"),
        Signal("identity", Outcome.PASS, "northpost.dev is Northpost.", "registry"),
        fidelity(*fields),
    ]


def test_a_confirmed_reading_that_matches_the_signature_certifies() -> None:
    """The verdict the run would have reached had the extractor read it."""
    amended = apply_reading(
        signals(field("iban", "GB29NWBK60161331926819", "GB29NWBK6O161331926819", 0.4)),
        "iban",
        "GB29NWBK60161331926819",
        "dana",
    )
    assert decide(amended).verdict is Verdict.CERTIFIED


def test_a_person_cannot_adjudicate_a_document_into_being_certified() -> None:
    """One input, and it is what the page says. If that disagrees with the
    signature, it fails, no matter who typed it."""
    amended = apply_reading(
        signals(field("iban", "GB29NWBK60161331926819", "unreadable", 0.3)),
        "iban",
        "GB94BARC10201530093459",
        "dana",
    )
    decision = decide(amended)
    assert decision.verdict is Verdict.FLAGGED
    assert "GB94BARC10201530093459" in decision.reason


def test_the_signed_value_is_not_editable() -> None:
    """It comes from the mark, and a comparison against an editable expectation
    would be a comparison against nothing."""
    original = "GB29NWBK60161331926819"
    amended = apply_reading(
        signals(field("iban", original, "smudged", 0.2)), "iban", "anything", "dana"
    )
    compared = amended[-1].evidence["compared"]
    assert compared[0]["signed"] == original


def test_answering_one_doubtful_field_does_not_resolve_another() -> None:
    """A document with two unreadable fields is not settled by one answer."""
    amended = apply_reading(
        signals(
            field("iban", "GB29", "GB29", 0.9),
            field("amt", "15580.00", "1558O.OO", 0.3),
            field("bic", "NWBKGB2L", "NWBKG82L", 0.2),
        ),
        "amt",
        "15580.00",
        "dana",
    )
    assert amended[-1].outcome is Outcome.UNKNOWN
    assert "bic" in amended[-1].detail
    assert "amt" not in amended[-1].detail


def test_answering_the_last_doubtful_field_settles_the_run() -> None:
    once = apply_reading(
        signals(
            field("amt", "15580.00", "1558O.OO", 0.3),
            field("bic", "NWBKGB2L", "NWBKG82L", 0.2),
        ),
        "amt",
        "15580.00",
        "dana",
    )
    twice = apply_reading(once, "bic", "NWBKGB2L", "dana")
    assert twice[-1].outcome is Outcome.PASS


def test_the_machine_reading_is_kept_beside_the_human_one() -> None:
    """A person overriding a machine is the event an audit trail exists for, and
    the trail is worth nothing without what was overridden."""
    amended = apply_reading(signals(field("iban", "GB29", "G829", 0.3)), "iban", "GB29", "dana")
    entry = amended[-1].evidence["compared"][0]
    assert entry["machineRead"] == "G829"
    assert entry["adjudicatedBy"] == "dana"


def test_a_field_absent_from_the_page_cannot_be_supplied_by_hand() -> None:
    """Reading what is not there is authoring, not adjudicating."""
    with pytest.raises(NotAdjudicable, match="no reading to correct"):
        apply_reading(signals(field("iban", "GB29", None, 0.0)), "iban", "GB29", "dana")


def test_a_field_the_run_never_compared_is_refused() -> None:
    with pytest.raises(NotAdjudicable, match="not one of the fields"):
        apply_reading(signals(field("iban", "GB29", "GB29", 0.9)), "amt", "1", "dana")


def test_a_run_with_no_page_comparison_is_refused() -> None:
    with pytest.raises(NotAdjudicable, match="no page comparison"):
        apply_reading([Signal("signature", Outcome.PASS, "ok", "dns")], "iban", "GB29", "dana")


def test_only_the_doubtful_fields_are_put_to_a_person() -> None:
    """Asking about fields the extractor read confidently trains people to
    click through the ones that matter."""
    asked = uncertain_fields(
        fidelity(
            field("iban", "GB29", "GB29", 0.98),
            field("amt", "15580.00", "1558O.OO", 0.3),
            field("bic", "NWBKGB2L", None, 0.0),
        ),
        THRESHOLD,
    )
    assert [entry["field"] for entry in asked] == ["amt"]
