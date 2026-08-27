"""The decision table.

decide is pure and total: the same signals always produce the same verdict. No
model, no clock, no network. The output of this product is evidence, and evidence
that cannot be replayed is not evidence.

Adding a signal means adding a Check, not editing this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Outcome(Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Verdict(Enum):
    CERTIFIED = "certified"
    UNSIGNED = "unsigned"
    FLAGGED = "flagged"


# Ordered by how much a reader needs to hear it first, not alphabetically. A page
# that contradicts what was signed is an alteration, while the same document sent
# twice is often just a chased payment, so alteration is the louder finding.
CRITICAL_CHECKS: tuple[str, ...] = (
    "signature",
    "identity",
    "lookalike",
    "fidelity",
    "duplicate",
)


@dataclass(frozen=True, slots=True)
class Signal:
    """One finding, and the evidence it rests on.

    detail is the sentence a reader acts on. evidence is what the check actually
    saw: the query it made, the answer that came back, the bytes it verified.
    Keeping only the sentence made the product look like it was asserting things
    rather than checking them, and a claim nobody can inspect is not evidence.

    decide never reads evidence. The verdict is a function of outcomes alone, so
    carrying the working cannot change what the working concluded.
    """

    name: str
    outcome: Outcome
    detail: str
    source: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


def _severity(signal: Signal) -> int:
    if signal.name in CRITICAL_CHECKS:
        return CRITICAL_CHECKS.index(signal.name)
    return len(CRITICAL_CHECKS)


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: Verdict
    reason: str
    signals: tuple[Signal, ...]


def _every(signals: Sequence[Signal], name: str) -> bool:
    """Whether every signal under this name passed, and there was at least one.

    Reading one signal per name let a repeated name decide the verdict by
    position. A bundle carrying signature UNKNOWN followed by signature PASS
    certified, which matters because replay re-decides from a deserialised
    archive that an attacker may have authored.
    """
    found = [signal for signal in signals if signal.name == name]
    return bool(found) and all(signal.outcome is Outcome.PASS for signal in found)


def decide(signals: Sequence[Signal]) -> Decision:
    """Reduce signals to one verdict.

    Any failing signal flags the document, reported in CRITICAL_CHECKS order so
    the headline names the most consequential problem. A passing signature with a
    passing identity certifies. Everything else is unsigned, which means no proof
    was available and nothing contradicted the document.
    """
    collected = tuple(signals)

    failures = [signal for signal in collected if signal.outcome is Outcome.FAIL]
    if failures:
        ranked = sorted(failures, key=_severity)
        return Decision(verdict=Verdict.FLAGGED, reason=ranked[0].detail, signals=collected)

    if _every(collected, "signature") and _every(collected, "identity"):
        return Decision(
            verdict=Verdict.CERTIFIED,
            reason=next(s.detail for s in collected if s.name == "signature"),
            signals=collected,
        )

    return Decision(
        verdict=Verdict.UNSIGNED,
        reason="No proof available. Nothing contradicts this document.",
        signals=collected,
    )
