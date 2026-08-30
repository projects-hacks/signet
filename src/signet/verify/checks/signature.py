"""Layer one: did this domain emit this document?

No extraction, no model, no heuristics. The mark carries the payload, so this
check verifies exactly the bytes it received against the key published at the
issuer's own domain. Nothing here can be flaky.
"""

from __future__ import annotations

from base64 import b64encode

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
        signed = {
            "algorithm": "ed25519",
            "query": name,
            "signedBytes": context.mark.payload_bytes.decode("utf-8", "replace"),
            "signature": b64encode(context.mark.signature).decode("ascii"),
        }
        try:
            lookup = self._resolver.lookup_txt(name)
        except AdapterError as exc:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"Could not reach DNS for {issuer}.",
                str(exc),
                {**signed, "reached": False},
            )

        seen = {
            **signed,
            "reached": True,
            "answers": {who: list(records) for who, records in lookup.answers.items()},
            "resolversAgreed": lookup.resolvers_agreed,
            "dnssecValidated": lookup.dnssec_validated,
        }

        if not lookup.resolvers_agreed:
            return Signal(
                NAME,
                Outcome.FAIL,
                f"DNS providers disagree about {issuer}, which can mean a spoofed answer.",
                name,
                seen,
            )

        keys = [key for record in lookup.records if (key := decode_public_key(record))]
        if not keys:
            return Signal(NAME, Outcome.UNKNOWN, f"{issuer} publishes no Signet key.", name, seen)

        verified = any(
            self._verifier.verify(context.mark.payload_bytes, context.mark.signature, key)
            for key in keys
        )
        seen = {**seen, "keysPublished": len(keys), "verified": verified}
        if not verified:
            # Stated as what was observed. The same branch fires for a payload
            # altered after issue, a mark fabricated wholesale, and a key the
            # issuer has since rotated out of DNS, and the check cannot tell
            # which happened.
            return Signal(
                NAME,
                Outcome.FAIL,
                f"The signature does not match the key {issuer} publishes.",
                name,
                seen,
            )

        chain = "a validated DNSSEC chain" if lookup.dnssec_validated else "an unsigned zone"
        return Signal(
            NAME,
            Outcome.PASS,
            f"Issued by {issuer} on {context.mark.payload.timestamp}.",
            f"{name} over {chain}",
            seen,
        )
