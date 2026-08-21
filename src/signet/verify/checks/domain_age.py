"""A domain registered days ago is the highest signal check available.

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
                Outcome.FAIL,
                f"{domain} was registered {age} days ago.",
                "rdap",
            )
        return Signal(NAME, Outcome.PASS, f"{domain} has been registered {age} days.", "rdap")
