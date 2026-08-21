"""Composing checks into a verdict.

The pipeline finds the mark, runs every check, and hands the signals to decide().
It contains no judgement of its own: adding or removing a signal changes the
registry, never this module.

Extraction is deliberately not on the path to a certified verdict. The mark
carries everything layer one needs, so a document that extracts badly still
verifies. Extraction only supplies the mark when the caller did not scan it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from signet.core.mark import Mark, decode_mark
from signet.core.verdict import Decision, decide
from signet.errors import AdapterError, MarkError
from signet.ports.documents import DocumentExtractor
from signet.ports.store import RecordStore
from signet.verify.checks import Check
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
        extractor: DocumentExtractor | None = None,
    ) -> None:
        self._checks = tuple(checks)
        self._store = store
        self._extractor = extractor

    def run(self, request: VerificationRequest) -> Decision:
        mark = self._find_mark(request)
        context = VerificationContext(
            run_id=request.run_id,
            content=request.content,
            media_type=request.media_type,
            submitted_by=request.submitted_by,
            mark=mark,
            claimed_brand=request.claimed_brand,
        )

        self._store.append_audit(request.run_id, "started", {"marked": mark is not None})
        signals = [check.run(context) for check in self._checks]
        decision = decide(signals)
        self._store.append_audit(
            request.run_id,
            "decided",
            {
                "verdict": decision.verdict.value,
                "reason": decision.reason,
                "signals": {signal.name: signal.outcome.value for signal in decision.signals},
            },
        )
        return decision

    def _find_mark(self, request: VerificationRequest) -> Mark | None:
        """Prefer a mark the caller scanned; fall back to extraction.

        A mark that fails to decode is treated as absent rather than fatal, so a
        smudged code degrades to the corroboration path instead of an error page.
        """
        candidates: list[str] = []
        if request.mark_text:
            candidates.append(request.mark_text)
        elif self._extractor is not None:
            try:
                candidates.extend(
                    self._extractor.extract(request.content, request.media_type).marks
                )
            except AdapterError:
                return None

        for candidate in candidates:
            try:
                return decode_mark(candidate)
            except MarkError:
                continue
        return None
