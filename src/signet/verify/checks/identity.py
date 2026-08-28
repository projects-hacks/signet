"""Layer two: is that domain really the brand on the paper?

A forger can register a domain, publish their own key and sign their own fake.
The signature is entirely valid. Only this check catches it, which is why a
signature alone never certifies.

The brand to domain question is settled once, at enrolment, where it can be slow,
draw on several sources and escalate to a person. Here it is a registry lookup.
"""

from __future__ import annotations

from signet.core.brand import same_brand
from signet.core.verdict import Outcome, Signal
from signet.ports.store import RecordStore
from signet.verify.context import VerificationContext

NAME = "identity"


class IdentityCheck:
    name = NAME

    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def run(self, context: VerificationContext) -> Signal:
        if context.mark is None:
            return Signal(NAME, Outcome.UNKNOWN, "This document carries no mark.", "signet")

        domain = context.mark.payload.issuer
        issuer = self._store.issuer(domain)
        if issuer is None or not issuer.enrolled:
            return Signal(
                NAME,
                Outcome.FAIL,
                f"Signed by {domain}, which is not a domain we hold a brand record for.",
                "registry",
                {"domain": domain, "claimedBrand": context.claimed_brand, "enrolled": False},
            )
        if issuer.frozen:
            return Signal(
                NAME,
                Outcome.FAIL,
                f"{domain} is frozen. Its registration changed hands or lapsed.",
                "registry",
                {"domain": domain, "enrolledBrand": issuer.brand, "frozen": True},
            )
        if context.claimed_brand and not same_brand(issuer.brand, context.claimed_brand):
            return Signal(
                NAME,
                Outcome.FAIL,
                f"This document names {context.claimed_brand}, but {domain} is {issuer.brand}.",
                "registry",
                {
                    "domain": domain,
                    "claimedBrand": context.claimed_brand,
                    "enrolledBrand": issuer.brand,
                },
            )
        return Signal(
            NAME,
            Outcome.PASS,
            f"{domain} is {issuer.brand}.",
            "registry",
            {
                "domain": domain,
                "claimedBrand": context.claimed_brand,
                "enrolledBrand": issuer.brand,
            },
        )
