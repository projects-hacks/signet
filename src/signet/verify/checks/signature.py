"""Layer one: did this domain emit this document?

No extraction, no model, no heuristics. The mark carries the payload, so this
check verifies exactly the bytes it received against the key published at the
issuer's own domain. Nothing here can be flaky.
"""

from __future__ import annotations

from signet.constants import DNS_LABEL
from signet.core.signing import Ed25519Verifier, decode_public_key
from signet.core.verdict import Outcome, Signal
from signet.errors import AdapterError
from signet.ports.dns import DnsResolver
from signet.verify.context import VerificationContext

NAME = "signature"


class SignatureCheck:
    name = NAME

    def __init__(self, resolver: DnsResolver) -> None:
        self._resolver = resolver
        self._verifier = Ed25519Verifier()

    def run(self, context: VerificationContext) -> Signal:
        if context.mark is None:
            return Signal(NAME, Outcome.UNKNOWN, "This document carries no mark.", "signet")

        issuer = context.mark.payload.issuer
        name = f"{DNS_LABEL}.{issuer}"
        try:
            lookup = self._resolver.lookup_txt(name)
        except AdapterError as exc:
            return Signal(NAME, Outcome.UNKNOWN, f"Could not reach DNS for {issuer}.", str(exc))

        if not lookup.resolvers_agreed:
            return Signal(
                NAME,
                Outcome.FAIL,
                f"DNS providers disagree about {issuer}, which can mean a spoofed answer.",
                name,
            )

        keys = [key for record in lookup.records if (key := decode_public_key(record))]
        if not keys:
            return Signal(NAME, Outcome.UNKNOWN, f"{issuer} publishes no Signet key.", name)

        verified = any(
            self._verifier.verify(context.mark.payload_bytes, context.mark.signature, key)
            for key in keys
        )
        if not verified:
            return Signal(
                NAME,
                Outcome.FAIL,
                "This document was altered after it was issued.",
                name,
            )

        chain = "a validated DNSSEC chain" if lookup.dnssec_validated else "an unsigned zone"
        return Signal(
            NAME,
            Outcome.PASS,
            f"Issued by {issuer} on {context.mark.payload.timestamp}.",
            f"{name} over {chain}",
        )
