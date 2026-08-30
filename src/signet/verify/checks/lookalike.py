"""Is the signing domain wearing an enrolled domain's name?

Identity answers whether the signing domain is one we hold a brand record for.
It cannot answer the case where the forger never claimed to be the brand's domain
at all, only to look like it. north-post.dev registers cleanly, publishes its own
key and signs its own invoice, and every cryptographic step passes because
nothing about it is forged. The name is the forgery, and this is the only check
that reads the name as a name.

The comparison is local on purpose. The store already holds the enrolled set, so
this looks up the domain enrolled for the claimed brand and asks one question:
does the signing domain read as that domain without being it? A check that needs
a registrar to be reachable is a check that goes missing exactly when a backed up
queue is being cleared, and whether a squat was registered this morning does not
change what an invoice from last month is.

An enrolled domain resembles itself perfectly, so being the enrolled domain is
the pass rather than the failure.
"""

from __future__ import annotations

from signet.core.brand import same_brand
from signet.core.lookalike import is_confusable
from signet.core.verdict import Outcome, Signal
from signet.ports.store import RecordStore
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
        if context.claimed_brand is None:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                "This document names no brand, so there is nothing for it to imitate.",
                "registry",
            )

        # Confusability alone cannot say which of a pair is the imitation, and a
        # legitimately enrolled domain is confusable with anyone imitating it. The
        # brand on the paper breaks the symmetry: the domain worth comparing
        # against is the one the claimed brand actually signs from.
        claimed = self._brand_domain(context.claimed_brand)
        if claimed is None:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"No enrolled domain to compare against for {context.claimed_brand}.",
                "registry",
            )
        if claimed == domain:
            return Signal(
                NAME,
                Outcome.PASS,
                f"{domain} is the domain {context.claimed_brand} signs from.",
                "registry",
            )
        if is_confusable(domain, claimed):
            return Signal(
                NAME,
                Outcome.FAIL,
                f"{domain} reads as {claimed}, which is where {context.claimed_brand} "
                f"actually signs from, but it is not {claimed}.",
                "registry",
            )
        return Signal(
            NAME,
            Outcome.PASS,
            f"{domain} does not resemble {claimed}.",
            "registry",
        )

    def _brand_domain(self, brand: str) -> str | None:
        for issuer in self._store.enrolled_issuers():
            if same_brand(issuer.brand, brand):
                return issuer.domain
        return None
