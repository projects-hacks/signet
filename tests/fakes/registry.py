from __future__ import annotations

from datetime import date

from signet.ports.registry import Registration


class FakeRegistrationData:
    def __init__(self, registrations: dict[str, Registration] | None = None) -> None:
        self.registrations = registrations or {}

    def registration(self, domain: str) -> Registration:
        if domain in self.registrations:
            return self.registrations[domain]
        return Registration(
            domain=domain,
            created=date(2010, 1, 1),
            expires=date(2030, 1, 1),
            registrar="Fake Registrar",
            locked=True,
        )


class FakeDomainRegistrar:
    def __init__(self, taken: set[str] | None = None) -> None:
        self.taken = taken or set()

    def available(self, domains: tuple[str, ...]) -> dict[str, bool]:
        return {domain: domain not in self.taken for domain in domains}
