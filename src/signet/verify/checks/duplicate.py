"""A signature proves issuance, not entitlement.

A genuine document can be submitted twice, or borrowed from someone else. No
amount of cryptography addresses that; a ledger does.
"""

from __future__ import annotations

from signet.core.verdict import Outcome, Signal
from signet.ports.store import RecordStore
from signet.verify.context import VerificationContext, fingerprint

NAME = "duplicate"


class DuplicateCheck:
    name = NAME

    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def run(self, context: VerificationContext) -> Signal:
        first_time = self._store.record_submission(fingerprint(context), context.submitted_by)
        if not first_time:
            return Signal(
                NAME,
                Outcome.FAIL,
                "This exact document has already been submitted.",
                "ledger",
            )
        return Signal(NAME, Outcome.PASS, "Not seen before.", "ledger")
