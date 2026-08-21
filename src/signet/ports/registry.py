"""Domain facts and domain lifecycle.

Split from DNS because they answer different questions and come from different
sources: registration data is registry authoritative, availability is registrar
specific.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Registration:
    domain: str
    created: date | None
    expires: date | None
    registrar: str | None
    locked: bool


class RegistrationData(Protocol):
    def registration(self, domain: str) -> Registration: ...


class DomainRegistrar(Protocol):
    def available(self, domains: tuple[str, ...]) -> dict[str, bool]: ...
