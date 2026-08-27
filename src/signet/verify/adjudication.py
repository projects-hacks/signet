"""When the machine will not guess, a person answers.

Extraction returns a confidence with every field. Below the threshold the
fidelity check reports UNKNOWN and says which fields it could not read, which is
the right answer for a machine and a dead end for a reader: the whole document
then sits at "no proof available" because of a smudged digit.

So the reading becomes a question. A person is shown the field, what the
extractor thought it said, how sure it was, and where on the page it looked, and
types what the page actually says. That answer replaces the machine's reading
and the comparison runs again.

Three things this deliberately does not do.

It does not let a person set the verdict. They supply one input, what the page
says, and `decide` reaches the same conclusion it would have reached if the
extractor had read it correctly. Nobody can adjudicate a document into being
certified: if their reading disagrees with the signature, it fails.

It does not touch what was signed. The signed value comes from the mark and is
not editable by anyone, which is what makes the comparison worth running.

It does not forget. Every adjudication is recorded with who made it and what
they said, because a person overriding a machine is exactly the event an audit
trail exists for.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from signet.core.verdict import Outcome, Signal
from signet.errors import SignetError
from signet.verify.checks.fidelity import NAME as FIDELITY
from signet.verify.checks.fidelity import comparable

HUMAN_CONFIDENCE = 1.0


class NotAdjudicable(SignetError):
    """The reading cannot be applied, and why."""


def uncertain_fields(signal: Signal, threshold: float) -> tuple[Mapping[str, Any], ...]:
    """The fields a person is being asked about, with everything they need."""
    compared = signal.evidence.get("compared")
    if not isinstance(compared, list):
        return ()
    return tuple(
        field
        for field in compared
        if isinstance(field, dict)
        and field.get("printed") is not None
        and float(field.get("confidence", 1.0)) < threshold
    )


def apply_reading(signals: Sequence[Signal], field: str, reading: str, by: str) -> list[Signal]:
    """Replace one machine reading with a person's, and compare again.

    The whole fidelity signal is recomputed rather than patched, so a document
    with two doubtful fields does not become certified after one of them is
    answered.
    """
    fidelity = next((signal for signal in signals if signal.name == FIDELITY), None)
    if fidelity is None:
        raise NotAdjudicable("This run has no page comparison to adjudicate.")

    compared = fidelity.evidence.get("compared")
    if not isinstance(compared, list):
        raise NotAdjudicable("This run recorded no fields to compare.")

    threshold = float(fidelity.evidence.get("threshold", 0.0))
    amended: list[dict[str, Any]] = []
    found = False
    for entry in compared:
        if not isinstance(entry, dict):
            continue
        if entry.get("field") != field:
            amended.append(dict(entry))
            continue
        if entry.get("printed") is None:
            raise NotAdjudicable(
                f"{field} was not found on the page at all, so there is no reading to correct."
            )
        found = True
        amended.append(
            {
                **entry,
                "printed": reading,
                "confidence": HUMAN_CONFIDENCE,
                "agrees": comparable(reading) == comparable(str(entry.get("signed", ""))),
                "adjudicatedBy": by,
                "machineRead": entry.get("printed"),
            }
        )

    if not found:
        raise NotAdjudicable(f"{field} is not one of the fields this run compared.")

    replaced = _fidelity_from(amended, threshold)
    return [replaced if signal.name == FIDELITY else signal for signal in signals]


def _fidelity_from(compared: Sequence[Mapping[str, Any]], threshold: float) -> Signal:
    """The same rule the check itself applies, over the amended readings."""
    evidence: dict[str, Any] = {"threshold": threshold, "compared": list(compared)}

    for entry in compared:
        if entry.get("printed") is None:
            continue
        if float(entry.get("confidence", 1.0)) < threshold:
            continue
        if not entry.get("agrees"):
            return Signal(
                FIDELITY,
                Outcome.FAIL,
                f"The page shows {entry['printed']} where the signature covers {entry['signed']}.",
                "extraction",
                evidence,
            )

    doubtful = [
        str(entry["field"])
        for entry in compared
        if entry.get("printed") is not None and float(entry.get("confidence", 1.0)) < threshold
    ]
    if doubtful:
        return Signal(
            FIDELITY,
            Outcome.UNKNOWN,
            f"Needs a human: {', '.join(doubtful)} could not be read confidently.",
            "extraction",
            evidence,
        )

    read = [entry for entry in compared if entry.get("printed") is not None]
    if not read:
        return Signal(
            FIDELITY,
            Outcome.UNKNOWN,
            "None of the signed fields were found on the page.",
            "extraction",
            evidence,
        )
    return Signal(
        FIDELITY, Outcome.PASS, "The page matches what was signed.", "extraction", evidence
    )
