"""What the open web says about the party asking to be paid.

Signature and identity are closed questions. They compare a document against
records we hold, and they are silent about a company nobody has enrolled, which
is most companies. A reader looking at an invoice from a haulier they have never
dealt with is not asking whether our records agree with themselves. They are
asking whether this business exists and whether the account on the page belongs
to it.

That answer is not in the document and it is not in our store, so it is fetched
live. Three things come back: whether the open web has anything to say at all,
which domain it publishes for the brand, and whether the recent record carries
anything a person should read before transferring money.

Only one of those can fail a document. The published domain disagreeing with the
signing domain is a contradiction, and it is the case an enrolled registry cannot
see, because impersonating a real company works precisely when that company never
heard of us. Nothing else here fails: a business with no web presence is thin
evidence rather than proof, and adverse coverage is for a person to read, not for
a rule to act on. A check that flagged on a matched keyword would be wrong often
enough that readers would learn to ignore it.

An enrolled issuer is exempt from the contradiction. Enrolment is a reviewed
binding of a brand to a domain, and a company whose invoices come from a
different domain than its marketing site is ordinary. The reviewed record wins
over the search result.
"""

from __future__ import annotations

from signet.core.verdict import Outcome, Signal
from signet.ports.intelligence import EntityResolver
from signet.ports.store import RecordStore
from signet.verify.context import VerificationContext

NAME = "counterparty"


class CounterpartyCheck:
    name = NAME

    def __init__(self, resolver: EntityResolver, store: RecordStore) -> None:
        self._resolver = resolver
        self._store = store

    def run(self, context: VerificationContext) -> Signal:
        if context.mark is None:
            return Signal(NAME, Outcome.UNKNOWN, "This document carries no mark.", "signet")

        domain = context.mark.payload.issuer
        issuer = self._store.issuer(domain)
        brand = context.claimed_brand or (issuer.brand if issuer else None)
        if not brand:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                "This document names no brand, so there is nothing to look up.",
                "serpapi",
            )

        resolution = self._resolver.resolve_brand(brand)
        published = resolution.canonical_domain
        enrolled = issuer is not None and issuer.enrolled

        if published and published != domain and not enrolled:
            return Signal(
                NAME,
                Outcome.FAIL,
                f"The open web publishes {published} for {brand}, and this was signed by {domain}.",
                "serpapi",
                {
                    "brand": brand,
                    "signingDomain": domain,
                    "publishedDomain": published,
                    "sources": list(resolution.sources),
                },
            )

        # A lookup that cannot complete surfaces as UNKNOWN through the pipeline,
        # which is missing corroboration rather than a contradiction.
        diligence = self._resolver.diligence(domain, brand)
        evidence = {
            "brand": brand,
            "signingDomain": domain,
            "publishedDomain": diligence.published_domain,
            "adverseMentions": list(diligence.adverse_mentions),
            "sources": list(diligence.sources),
        }
        if not diligence.exists:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"The open web has nothing to say about {brand} at {domain}.",
                "serpapi",
                evidence,
            )
        if diligence.adverse_mentions:
            count = len(diligence.adverse_mentions)
            noun = "result mentions" if count == 1 else "results mention"
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"{count} recent search {noun} {brand} alongside fraud or insolvency. "
                "Read them before paying.",
                "serpapi",
                evidence,
            )
        return Signal(
            NAME,
            Outcome.PASS,
            f"{brand} trades at {domain} and the recent record is clean.",
            "serpapi",
            evidence,
        )
