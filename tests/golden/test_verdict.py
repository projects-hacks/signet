"""Determinism is the product's central claim, so it is a test rather than a hope."""

from signet.core.verdict import Decision, Outcome, Signal, Verdict, decide


def signal(name: str, outcome: Outcome, detail: str = "") -> Signal:
    return Signal(name=name, outcome=outcome, detail=detail or name, source="test")


def test_valid_signature_and_matching_identity_certifies() -> None:
    decision = decide(
        [
            signal("signature", Outcome.PASS, "Issued by Blue Bottle Coffee on 20 Aug 2026."),
            signal("identity", Outcome.PASS),
            signal("duplicate", Outcome.PASS),
        ]
    )
    assert decision.verdict is Verdict.CERTIFIED
    assert decision.reason.startswith("Issued by")


def test_broken_signature_flags() -> None:
    decision = decide(
        [
            signal("signature", Outcome.FAIL, "The amount does not match what was signed."),
            signal("identity", Outcome.PASS),
        ]
    )
    assert decision.verdict is Verdict.FLAGGED
    assert decision.reason == "The amount does not match what was signed."


def test_valid_signature_at_the_wrong_domain_flags() -> None:
    decision = decide(
        [
            signal("signature", Outcome.PASS),
            signal("identity", Outcome.FAIL, "Signed by a domain that is not Blue Bottle's."),
        ]
    )
    assert decision.verdict is Verdict.FLAGGED
    assert "not Blue Bottle" in decision.reason


def test_duplicate_submission_flags_even_when_certified() -> None:
    decision = decide(
        [
            signal("signature", Outcome.PASS),
            signal("identity", Outcome.PASS),
            signal("duplicate", Outcome.FAIL, "Already submitted on 2 August."),
        ]
    )
    assert decision.verdict is Verdict.FLAGGED


def test_no_mark_is_unsigned_not_flagged() -> None:
    decision = decide(
        [
            signal("domain_age", Outcome.PASS),
            signal("lookalike", Outcome.PASS),
            signal("duplicate", Outcome.PASS),
        ]
    )
    assert decision.verdict is Verdict.UNSIGNED


def test_headline_names_the_most_consequential_failure() -> None:
    decision = decide(
        [
            signal("lookalike", Outcome.FAIL, "lookalike detail"),
            signal("signature", Outcome.FAIL, "signature detail"),
        ]
    )
    assert decision.reason == "signature detail"


def test_same_signals_always_produce_the_same_decision() -> None:
    signals = [signal("signature", Outcome.PASS), signal("identity", Outcome.PASS)]
    first = decide(signals)
    second = decide(list(reversed(signals)))
    assert isinstance(first, Decision)
    assert first.verdict is second.verdict
