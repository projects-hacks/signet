"""Is the signing domain wearing an enrolled domain's name?

Identity answers whether the signing domain is one we hold a brand record for.
It cannot answer the case where the forger never claimed to be the brand's domain
at all, only to look like it. north-post.dev registers cleanly, publishes its own
key and signs its own invoice, and every cryptographic step passes because
nothing about it is forged. The name is the forgery, and this is the only check
that reads the name as a name.

The comparison is local on purpose. The store already holds the enrolled set, so
this asks the store about names in the neighbourhood of the signing domain rather
than asking a registrar what exists. A check that needs a vendor to be reachable
is a check that goes missing exactly when a backed up queue is being cleared, and
whether a squat was registered this morning does not change what an invoice from
last month is.

The store answers one name at a time, so the neighbourhood is enumerated and
probed rather than listed. That is bounded by the permutation cap, and it means
this check needs nothing from the store that verification does not already use.

An enrolled domain resembles itself perfectly, so being the enrolled domain is
the pass rather than the failure.
"""

from __future__ import annotations

from signet.core.lookalike import confusability, is_confusable, permutations
from signet.core.verdict import Outcome, Signal
from signet.ports.store import Issuer, RecordStore
from signet.verify.context import VerificationContext

NAME = "lookalike"


class LookalikeCheck:
    name = NAME

    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def run(self, context: VerificationContext) -> Signal:
        if context.mark is None:
            return Signal(NAME, Outcome.UNKNOWN, "This document carries no mark.", "signet")

        domain = context.mark.payload.issuer
        if self._enrolled(domain) is not None:
            return Signal(
                NAME,
                Outcome.PASS,
                f"{domain} is the enrolled domain itself, not an imitation of one.",
                "registry",
            )

        imitated = self._nearest_enrolled(domain)
        if imitated is None:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"No enrolled domain resembles {domain} closely enough to compare it against.",
                "registry",
            )
        return Signal(
            NAME,
            Outcome.FAIL,
            f"{domain} reads as {imitated}, an enrolled domain, but it is not {imitated}.",
            "registry",
        )

    def _enrolled(self, domain: str) -> Issuer | None:
        issuer = self._store.issuer(domain)
        return issuer if issuer is not None and issuer.enrolled else None

    def _nearest_enrolled(self, domain: str) -> str | None:
        """The enrolled domain this one imitates most closely, if any.

        Ties break on the permutation order, which is fixed, so the same document
        always names the same domain in its evidence.
        """
        best: str | None = None
        best_score = 0.0
        for candidate in permutations(domain):
            if self._enrolled(candidate) is None:
                continue
            if not is_confusable(domain, candidate):
                continue
            score = confusability(domain, candidate)
            if score > best_score:
                best, best_score = candidate, score
        return best
