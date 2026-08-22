"""An archive that is not byte stable is a story about a run, not a record of one."""

from __future__ import annotations

import json

import pytest

from signet.core.mark import Mark, decode_mark, encode_mark
from signet.core.payload import canonicalize
from signet.core.verdict import Outcome, Signal, Verdict, decide
from signet.verify.context import VerificationContext, fingerprint
from signet.verify.evidence import SCHEMA, Bundle, EvidenceError, read, replay, write

RECORDED_AT = "2026-08-20T09:14:00Z"
CONTENT = b"%PDF-1.7 a receipt"

FIELDS = {
    "iss": "bluebottle.com",
    "ts": "2026-08-20T09:14:00Z",
    "id": "R-88213104",
    "cls": "receipt",
    "amt": "14.75",
    "cur": "USD",
}

OBSERVATIONS = {
    "dns": {"_signet.bluebottle.com": ["SIGNET1;k=abc"], "dnssec": True},
    "rdap": {"registered": "2011-04-02", "age_days": 5589},
    "extraction": [{"name": "amt", "value": "14.75", "confidence": 0.99}],
}


def signal(name: str, outcome: Outcome, detail: str = "", source: str = "test") -> Signal:
    return Signal(name=name, outcome=outcome, detail=detail or name, source=source)


def mark_for(fields: dict[str, str]) -> Mark:
    return decode_mark(encode_mark(canonicalize(fields), b"\x11" * 64))


def context_for(mark: Mark | None) -> VerificationContext:
    return VerificationContext(
        run_id="run-0001",
        content=CONTENT,
        media_type="application/pdf",
        submitted_by="claims@insurer.example",
        mark=mark,
        claimed_brand="Blue Bottle Coffee",
    )


def bundle_for(context: VerificationContext, signals: list[Signal]) -> Bundle:
    return Bundle.from_run(
        context=context,
        decision=decide(signals),
        recorded_at=RECORDED_AT,
        observations=OBSERVATIONS,
    )


def test_a_captured_run_records_everything_needed_to_re_decide_it() -> None:
    context = context_for(mark_for(FIELDS))
    bundle = bundle_for(
        context, [signal("signature", Outcome.PASS), signal("identity", Outcome.PASS)]
    )

    assert bundle.run_id == "run-0001"
    assert bundle.recorded_at == RECORDED_AT
    assert bundle.media_type == "application/pdf"
    assert bundle.submitted_by == "claims@insurer.example"
    assert bundle.claimed_brand == "Blue Bottle Coffee"
    assert bundle.payload_fields == FIELDS
    assert bundle.verdict is Verdict.CERTIFIED
    assert bundle.observations["rdap"] == OBSERVATIONS["rdap"]


def test_the_archived_fingerprint_is_the_one_the_ledger_used() -> None:
    context = context_for(mark_for(FIELDS))
    bundle = bundle_for(context, [signal("duplicate", Outcome.PASS)])
    assert bundle.fingerprint == fingerprint(context)


def test_a_run_without_a_mark_records_no_payload_fields() -> None:
    bundle = bundle_for(context_for(None), [signal("duplicate", Outcome.PASS)])
    assert bundle.payload_fields is None
    assert read(write(bundle)).payload_fields is None


def test_serialising_the_same_bundle_twice_produces_identical_bytes() -> None:
    bundle = bundle_for(context_for(mark_for(FIELDS)), [signal("signature", Outcome.PASS)])
    assert write(bundle).encode("utf-8") == write(bundle).encode("utf-8")


def test_field_order_in_the_recorded_data_does_not_change_the_archive() -> None:
    signals = [signal("signature", Outcome.PASS), signal("identity", Outcome.PASS)]
    forwards = Bundle.from_run(
        context=context_for(mark_for(FIELDS)),
        decision=decide(signals),
        recorded_at=RECORDED_AT,
        observations=dict(OBSERVATIONS),
    )
    backwards = Bundle.from_run(
        context=context_for(mark_for(dict(reversed(list(FIELDS.items()))))),
        decision=decide(signals),
        recorded_at=RECORDED_AT,
        observations=dict(reversed(list(OBSERVATIONS.items()))),
    )
    assert write(forwards) == write(backwards)


def test_nested_observation_keys_are_sorted_too() -> None:
    one = Bundle.from_run(
        context=context_for(None),
        decision=decide([signal("duplicate", Outcome.PASS)]),
        recorded_at=RECORDED_AT,
        observations={"dns": {"a": 1, "b": 2}},
    )
    other = Bundle.from_run(
        context=context_for(None),
        decision=decide([signal("duplicate", Outcome.PASS)]),
        recorded_at=RECORDED_AT,
        observations={"dns": {"b": 2, "a": 1}},
    )
    assert write(one) == write(other)


def test_a_bundle_round_trips_losslessly() -> None:
    bundle = bundle_for(
        context_for(mark_for(FIELDS)),
        [
            signal("signature", Outcome.PASS, "Issued by Blue Bottle Coffee on 20 Aug 2026."),
            signal("identity", Outcome.PASS, "Signed by bluebottle.com.", source="ledger"),
            signal("fidelity", Outcome.UNKNOWN, "Needs a human: amt.", source="extraction"),
        ],
    )
    assert read(write(bundle)) == bundle


def test_reading_an_archive_and_writing_it_again_reproduces_the_archive() -> None:
    bundle = bundle_for(context_for(mark_for(FIELDS)), [signal("signature", Outcome.FAIL)])
    archive = write(bundle)
    assert write(read(archive)) == archive


def test_unicode_and_awkward_characters_survive_a_round_trip() -> None:
    detail = 'Zahlung "über" 14,75 €\tan Bäckerei\\Müller\nzeile 2\u2028☃ 😀 ﷽'
    bundle = Bundle(
        run_id="run-ü-0002",
        recorded_at=RECORDED_AT,
        fingerprint="0" * 64,
        media_type="application/pdf",
        submitted_by="rückfragen@händler.example",
        verdict=Verdict.FLAGGED,
        reason=detail,
        signals=(signal("fidelity", Outcome.FAIL, detail, source="extraction"),),
        claimed_brand="Bäckerei Müller",
        payload_fields={"iss": "händler.example", "amt": "14,75 €"},
        observations={"dns": {"txt": ["v=SIGNET1; k=«quoted»"]}, "note": detail},
    )
    restored = read(write(bundle))
    assert restored == bundle
    assert restored.reason == detail
    assert restored.signals[0].detail == detail


def test_the_archive_carries_only_the_timestamp_it_was_handed() -> None:
    bundle = bundle_for(context_for(None), [signal("duplicate", Outcome.PASS)])
    body = json.loads(write(bundle))
    assert body["recorded_at"] == RECORDED_AT
    assert body["schema"] == SCHEMA


def test_replaying_a_bundle_needs_nothing_but_the_recorded_signals() -> None:
    signals = [signal("signature", Outcome.PASS), signal("identity", Outcome.PASS)]
    bundle = bundle_for(context_for(mark_for(FIELDS)), signals)
    decision = replay(bundle)
    assert decision.verdict is Verdict.CERTIFIED
    assert decision.signals == tuple(signals)


def test_reading_something_that_is_not_json_is_refused() -> None:
    with pytest.raises(EvidenceError):
        read("not an archive")


def test_reading_a_json_array_is_refused() -> None:
    with pytest.raises(EvidenceError):
        read("[]")


def test_reading_an_unknown_schema_is_refused() -> None:
    body = json.loads(write(bundle_for(context_for(None), [signal("duplicate", Outcome.PASS)])))
    body["schema"] = "signet-evidence/99"
    with pytest.raises(EvidenceError):
        read(json.dumps(body))


def test_reading_an_unrecognised_outcome_is_refused() -> None:
    body = json.loads(write(bundle_for(context_for(None), [signal("duplicate", Outcome.PASS)])))
    body["signals"][0]["outcome"] = "maybe"
    with pytest.raises(EvidenceError):
        read(json.dumps(body))


def test_reading_an_unrecognised_verdict_is_refused() -> None:
    body = json.loads(write(bundle_for(context_for(None), [signal("duplicate", Outcome.PASS)])))
    body["verdict"] = "probably fine"
    with pytest.raises(EvidenceError):
        read(json.dumps(body))


def test_reading_an_archive_with_a_missing_field_is_refused() -> None:
    body = json.loads(write(bundle_for(context_for(None), [signal("duplicate", Outcome.PASS)])))
    del body["submitted_by"]
    with pytest.raises(EvidenceError):
        read(json.dumps(body))


def test_reading_an_archive_whose_signals_are_not_a_list_is_refused() -> None:
    body = json.loads(write(bundle_for(context_for(None), [signal("duplicate", Outcome.PASS)])))
    body["signals"] = {"signature": "pass"}
    with pytest.raises(EvidenceError):
        read(json.dumps(body))


def test_reading_an_archive_with_non_string_payload_fields_is_refused() -> None:
    body = json.loads(write(bundle_for(context_for(mark_for(FIELDS)), [signal("x", Outcome.PASS)])))
    body["payload_fields"]["amt"] = 14.75
    with pytest.raises(EvidenceError):
        read(json.dumps(body))
