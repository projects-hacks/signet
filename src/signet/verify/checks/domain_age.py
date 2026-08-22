"""How long the issuing domain has existed.

A young domain is context, not a contradiction. Signet exists because detection
tools falsely flag around one authentic document in eight, and failing every
document from a business that registered its domain last month reintroduces
exactly that. A new company is not a fraud.

So this reports UNKNOWN rather than FAIL. It is loud in the report and it never
decides the verdict alone. The case it is really guarding against, a lookalike
registered days ago to run one invoice, already fails the identity check, which
compares the signing domain against the brand's canonical one. Age corroborates
that finding; it does not need to carry it.

Some registries reset the creation date on transfer, so a young date means the
registration is young, not necessarily that the brand is. The detail says so
rather than asserting fraud.
"""

from __future__ import annotations

from datetime import date

from signet.core.verdict import Outcome, Signal
from signet.errors import AdapterError
from signet.ports.registry import RegistrationData
from signet.verify.context import VerificationContext

NAME = "domain_age"
YOUNG_DOMAIN_DAYS = 90


class DomainAgeCheck:
    name = NAME

    def __init__(self, registrations: RegistrationData, today: date) -> None:
        self._registrations = registrations
        self._today = today

    def run(self, context: VerificationContext) -> Signal:
        domain = context.mark.payload.issuer if context.mark else None
        if domain is None:
            return Signal(NAME, Outcome.UNKNOWN, "No issuer domain to check.", "rdap")

        try:
            registration = self._registrations.registration(domain)
        except AdapterError as exc:
            return Signal(NAME, Outcome.UNKNOWN, f"Could not look up {domain}.", str(exc))

        if registration.created is None:
            return Signal(NAME, Outcome.UNKNOWN, f"No registration date for {domain}.", "rdap")

        age = (self._today - registration.created).days
        if age < YOUNG_DOMAIN_DAYS:
            return Signal(
                NAME,
                Outcome.UNKNOWN,
                f"{domain} was registered {age} days ago, which is recent enough to be "
                "worth a second look.",
                "rdap",
            )
        return Signal(NAME, Outcome.PASS, f"{domain} has been registered {age} days.", "rdap")
