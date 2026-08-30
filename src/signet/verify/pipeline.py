"""Composing checks into a verdict.

The pipeline finds the mark, runs every check, and hands the signals to decide().
It contains no judgement of its own: adding or removing a signal changes the
registry, never this module.

Mark reading is deliberately not extraction. Nutrient's json-content build has
no barcode option, so the code is decoded locally. That also keeps a certified
verdict off the extraction path entirely: a document that extracts badly still
verifies, because the mark carries everything layer one needs.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from signet.core.mark import Mark, decode_mark
from signet.core.verdict import Decision, Outcome, Signal, decide
from signet.errors import AdapterError, MarkError, SignetError
from signet.ports.documents import MarkReader
from signet.ports.store import RecordStore
from signet.verify.checks import Check
from signet.verify.checks.duplicate import NAME as DUPLICATE
from signet.verify.context import VerificationContext


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    run_id: str
    content: bytes
    media_type: str
    submitted_by: str
    mark_text: str | None = None
    claimed_brand: str | None = None


class VerificationPipeline:
    def __init__(
        self,
        checks: Sequence[Check],
        store: RecordStore,
        mark_reader: MarkReader | None = None,
    ) -> None:
        self._checks = tuple(checks)
        self._store = store
        self._mark_reader = mark_reader

    @property
    def check_names(self) -> tuple[str, ...]:
        """What this run will ask, before it has asked any of it.

        A reader waiting on a verdict is owed the shape of the answer rather than
        a spinner, and the shape is knowable at the start.
        """
        return tuple(check.name for check in self._checks)

    def run(self, request: VerificationRequest) -> Decision:
        decision: Decision | None = None
        for step in self.stream(request):
            if isinstance(step, Decision):
                decision = step
        if decision is None:  # pragma: no cover, stream always ends in a decision
            raise SignetError("the pipeline produced no decision")
        return decision

    def stream(self, request: VerificationRequest) -> Iterator[Signal | Decision]:
        """Every signal as it lands, then the verdict.

        Checks take unequal time. The signature is a DNS read and answers in
        milliseconds; reading the page is an upload to an extraction service and
        takes seconds. Yielding each one as it completes lets a reader watch the
        cheap answers arrive rather than wait on the slowest, and it costs
        nothing, because the checks already run in sequence.
        """
        mark = self._find_mark(request)
        context = VerificationContext(
            run_id=request.run_id,
            content=request.content,
            media_type=request.media_type,
            submitted_by=request.submitted_by,
            mark=mark,
            claimed_brand=request.claimed_brand,
        )

        self._audit(request.run_id, "started", {"marked": mark is not None})
        signals: list[Signal] = []
        for check in self._checks:
            if check.name == DUPLICATE and not _spendable(signals, marked=mark is not None):
                # Recording a submission is the one write in the pipeline, and
                # it is permanent. A run in which a deciding check could not
                # reach its source ends unsigned, and spending the document on
                # that run turns the retry into a false accusation: the
                # document comes back and is told it was already submitted.
                # An outage must cost a retry, never the document.
                signal = Signal(
                    DUPLICATE,
                    Outcome.UNKNOWN,
                    "Not recorded: a deciding check could not reach its source, "
                    "so this run does not use up the document.",
                    "ledger",
                )
            else:
                signal = self._signal_from(check, context)
            signals.append(signal)
            yield signal

        decision = decide(signals)
        self._audit(
            request.run_id,
            "decided",
            {
                "verdict": decision.verdict.value,
                "reason": decision.reason,
                "signals": {signal.name: signal.outcome.value for signal in decision.signals},
            },
        )
        yield decision

    @staticmethod
    def _signal_from(check: Check, context: VerificationContext) -> Signal:
        """A check that cannot reach its evidence reports UNKNOWN, never PASS.

        Certification requires signature and identity to pass, so an unreachable
        store drops the verdict to unsigned rather than certifying anything. That
        is the only safe direction: an outage is exactly when an attacker would
        choose to send a lookalike, and a check that passes because it could not
        look is worse than no check.
        """
        try:
            return check.run(context)
        except AdapterError as exc:
            return Signal(
                check.name,
                Outcome.UNKNOWN,
                f"Could not complete the {check.name} check.",
                str(exc),
            )

    def _audit(self, run_id: str, event: str, detail: Mapping[str, object]) -> None:
        """Logging must never be able to fail a verification.

        A verdict that depends on the audit trail being writable is a verdict
        that disappears when the trail does, and the signature was still valid
        either way.
        """
        try:
            self._store.append_audit(run_id, event, detail)
        except AdapterError:
            return

    def _find_mark(self, request: VerificationRequest) -> Mark | None:
        """Prefer a mark the caller scanned; fall back to reading the document.

        A mark that fails to decode is treated as absent rather than fatal, so a
        smudged code degrades to the corroboration path instead of an error page.
        """
        candidates: list[str] = []
        if request.mark_text:
            candidates.append(request.mark_text)
        elif self._mark_reader is not None:
            try:
                candidates.extend(self._mark_reader.read_marks(request.content, request.media_type))
            except AdapterError:
                return None

        for candidate in candidates:
            try:
                return decode_mark(candidate)
            except MarkError:
                continue
        return None


# The checks whose failure or absence decides a verdict. An advisory check
# being unreachable does not hold the ledger back.
_DECIDING: Final = ("signature", "identity", "fidelity")


def _unreachable(signal: Signal) -> bool:
    """Whether a check reported that it could not reach its source.

    Two shapes mean unreachable: no evidence at all, which is how the pipeline
    wraps a raised adapter error and how extraction reports being down, and
    evidence explicitly recording that the lookup never landed. An unknown that
    carries findings, like a page put to a person, reached its source fine.
    """
    if signal.outcome is not Outcome.UNKNOWN:
        return False
    return not signal.evidence or signal.evidence.get("reached") is False


def _spendable(signals: Sequence[Signal], marked: bool) -> bool:
    """Whether this run may permanently record the submission.

    An unmarked document depends on no vendor, so it always records. A marked
    one holds back when a deciding check could not reach its source, because
    that run ends unsigned and spending the document on it turns the retry
    into a false accusation.
    """
    if not marked:
        return True
    return not any(signal.name in _DECIDING and _unreachable(signal) for signal in signals)
