"""The decision table.

decide is pure and total: the same signals always produce the same verdict. No
model, no clock, no network. The output of this product is evidence, and evidence
that cannot be replayed is not evidence.

Adding a signal means adding a Check, not editing this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class Outcome(Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Verdict(Enum):
    CERTIFIED = "certified"
    UNSIGNED = "unsigned"
    FLAGGED = "flagged"


# Ordered by how much a reader needs to hear it first, not alphabetically.
CRITICAL_CHECKS: tuple[str, ...] = (
    "signature",
    "identity",
    "duplicate",
    "fidelity",
)


@dataclass(frozen=True, slots=True)
class Signal:
    name: str
    outcome: Outcome
    detail: str
    source: str


def _severity(signal: Signal) -> int:
    if signal.name in CRITICAL_CHECKS:
        return CRITICAL_CHECKS.index(signal.name)
    return len(CRITICAL_CHECKS)


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: Verdict
    reason: str
    signals: tuple[Signal, ...]


def decide(signals: Sequence[Signal]) -> Decision:
    """Reduce signals to one verdict.

    Any failing signal flags the document, reported in CRITICAL_CHECKS order so
    the headline names the most consequential problem. A passing signature with a
    passing identity certifies. Everything else is unsigned, which means no proof
    was available and nothing contradicted the document.
    """
    collected = tuple(signals)
    by_name = {signal.name: signal for signal in collected}

    failures = [signal for signal in collected if signal.outcome is Outcome.FAIL]
    if failures:
        ranked = sorted(failures, key=_severity)
        return Decision(verdict=Verdict.FLAGGED, reason=ranked[0].detail, signals=collected)

    signature = by_name.get("signature")
    identity = by_name.get("identity")
    if (
        signature is not None
        and signature.outcome is Outcome.PASS
        and identity is not None
        and identity.outcome is Outcome.PASS
    ):
        return Decision(
            verdict=Verdict.CERTIFIED,
            reason=signature.detail,
            signals=collected,
        )

    return Decision(
        verdict=Verdict.UNSIGNED,
        reason="No proof available. Nothing contradicts this document.",
        signals=collected,
    )
