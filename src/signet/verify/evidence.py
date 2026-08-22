"""An archived run, and the promise that replaying it changes nothing.

A verdict on its own is an assertion. A verdict together with the observations
that produced it is evidence, and a dispute raised six months later is settled by
re-deciding the archive rather than by asking DNS what it answers today, which is
a different question about a different moment.

Two consequences shape this module. The timestamp is a recorded field rather than
something write() reads, because a serialiser that consults the clock can never be
byte-compared against itself. And replay() reaches for decide() alone, never for a
check or an adapter, so an archive opened on a machine with no network reaches the
verdict the original run reached.

Observations are kept as whatever each source actually returned. Reducing them to
the fields today's checks happen to read would discard the answer to the next
question someone asks of the archive.

There is no hash function here. The fingerprint is the one the duplicate ledger
already uses, so the archive and the ledger cannot disagree about which document
this was.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from signet.core.verdict import Decision, Outcome, Signal, Verdict, decide
from signet.errors import SignetError
from signet.verify.context import VerificationContext, fingerprint

# Stamped into every archive. A reader that cannot name the shape it is holding
# has to guess, and guessing is how an audit trail quietly stops being one.
SCHEMA = "signet-evidence/1"

type JsonValue = str | int | float | bool | Sequence[JsonValue] | Mapping[str, JsonValue] | None


class EvidenceError(SignetError):
    """An evidence bundle could not be read."""


@dataclass(frozen=True, slots=True)
class Bundle:
    """Everything needed to re-decide one run without asking anybody anything."""

    run_id: str
    recorded_at: str
    fingerprint: str
    media_type: str
    submitted_by: str
    verdict: Verdict
    reason: str
    signals: tuple[Signal, ...]
    claimed_brand: str | None = None
    payload_fields: Mapping[str, str] | None = None
    observations: Mapping[str, JsonValue] = field(default_factory=dict)

    @classmethod
    def from_run(
        cls,
        context: VerificationContext,
        decision: Decision,
        recorded_at: str,
        observations: Mapping[str, JsonValue] | None = None,
    ) -> Bundle:
        """Capture a finished run.

        recorded_at is passed in rather than taken here so that the caller owns the
        single clock read in the whole pipeline and a test can pin it.
        """
        mark = context.mark
        return cls(
            run_id=context.run_id,
            recorded_at=recorded_at,
            fingerprint=fingerprint(context),
            media_type=context.media_type,
            submitted_by=context.submitted_by,
            verdict=decision.verdict,
            reason=decision.reason,
            signals=decision.signals,
            claimed_brand=context.claimed_brand,
            payload_fields=dict(mark.payload.fields) if mark is not None else None,
            observations=dict(observations) if observations is not None else {},
        )


def write(bundle: Bundle) -> str:
    """Render a bundle as canonical JSON.

    Keys are sorted at every level and separators are fixed, so the same inputs
    produce the same characters and an archive can be compared by hash. Nothing
    here reads the clock, the filesystem or the network.

    NaN and Infinity are refused rather than emitted, because neither survives a
    conforming JSON reader and an archive that cannot be read back is not one.
    """
    return json.dumps(
        _encode(bundle),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def read(text: str) -> Bundle:
    """Recover a bundle from its canonical JSON.

    The exact inverse of write: every field comes back as the type it left as, so
    write(read(archive)) is the archive.

    Raises EvidenceError on malformed JSON, an unknown schema, a missing field or
    an outcome or verdict this build does not recognise.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"evidence is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise EvidenceError("evidence must be a JSON object")

    schema = raw.get("schema")
    if schema != SCHEMA:
        raise EvidenceError(f"unrecognised evidence schema: {schema!r}")

    return Bundle(
        run_id=_text(raw, "run_id"),
        recorded_at=_text(raw, "recorded_at"),
        fingerprint=_text(raw, "fingerprint"),
        media_type=_text(raw, "media_type"),
        submitted_by=_text(raw, "submitted_by"),
        verdict=_verdict(_text(raw, "verdict")),
        reason=_text(raw, "reason"),
        signals=_signals(raw.get("signals")),
        claimed_brand=_optional_text(raw, "claimed_brand"),
        payload_fields=_optional_fields(raw.get("payload_fields")),
        observations=_observations(raw.get("observations")),
    )


def replay(bundle: Bundle) -> Decision:
    """Re-decide an archived run.

    The recorded signals go back through the same decision table that produced the
    original verdict. Nothing is observed again: re-running the checks would ask
    the world what it looks like now, which is the one question an archive is not
    for.
    """
    return decide(bundle.signals)


def _encode(bundle: Bundle) -> dict[str, JsonValue]:
    return {
        "schema": SCHEMA,
        "run_id": bundle.run_id,
        "recorded_at": bundle.recorded_at,
        "fingerprint": bundle.fingerprint,
        "media_type": bundle.media_type,
        "submitted_by": bundle.submitted_by,
        "verdict": bundle.verdict.value,
        "reason": bundle.reason,
        "signals": [
            {
                "name": signal.name,
                "outcome": signal.outcome.value,
                "detail": signal.detail,
                "source": signal.source,
            }
            for signal in bundle.signals
        ],
        "claimed_brand": bundle.claimed_brand,
        "payload_fields": None if bundle.payload_fields is None else dict(bundle.payload_fields),
        "observations": dict(bundle.observations),
    }


def _text(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise EvidenceError(f"evidence field {key!r} must be a string")
    return value


def _optional_text(raw: Mapping[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise EvidenceError(f"evidence field {key!r} must be a string or null")
    return value


def _outcome(value: str) -> Outcome:
    try:
        return Outcome(value)
    except ValueError as exc:
        raise EvidenceError(f"unrecognised outcome: {value!r}") from exc


def _verdict(value: str) -> Verdict:
    try:
        return Verdict(value)
    except ValueError as exc:
        raise EvidenceError(f"unrecognised verdict: {value!r}") from exc


def _signals(raw: Any) -> tuple[Signal, ...]:
    if not isinstance(raw, list):
        raise EvidenceError("evidence field 'signals' must be a list")
    return tuple(_signal(item) for item in raw)


def _signal(raw: Any) -> Signal:
    if not isinstance(raw, dict):
        raise EvidenceError("every recorded signal must be a JSON object")
    return Signal(
        name=_text(raw, "name"),
        outcome=_outcome(_text(raw, "outcome")),
        detail=_text(raw, "detail"),
        source=_text(raw, "source"),
    )


def _optional_fields(raw: Any) -> Mapping[str, str] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise EvidenceError("evidence field 'payload_fields' must be an object or null")
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise EvidenceError("payload fields must be strings")
    return dict(raw)


def _observations(raw: Any) -> Mapping[str, JsonValue]:
    if not isinstance(raw, dict):
        raise EvidenceError("evidence field 'observations' must be an object")
    return dict(raw)
