"""Wiring the default check set.

Kept apart from the pipeline so composition is one readable list rather than
constructor arguments threaded through a class.
"""

from __future__ import annotations

from datetime import date

from signet.ports.dns import DnsResolver
from signet.ports.documents import DocumentExtractor
from signet.ports.intelligence import EntityResolver
from signet.ports.registry import RegistrationData
from signet.ports.store import RecordStore
from signet.verify.checks import Check
from signet.verify.checks.counterparty import CounterpartyCheck
from signet.verify.checks.domain_age import DomainAgeCheck
from signet.verify.checks.duplicate import DuplicateCheck
from signet.verify.checks.fidelity import FidelityCheck
from signet.verify.checks.identity import IdentityCheck
from signet.verify.checks.lookalike import LookalikeCheck
from signet.verify.checks.signature import SignatureCheck


def default_checks(
    resolver: DnsResolver,
    store: RecordStore,
    registrations: RegistrationData,
    today: date,
    extractor: DocumentExtractor | None = None,
    entities: EntityResolver | None = None,
) -> tuple[Check, ...]:
    checks: list[Check] = [
        SignatureCheck(resolver),
        IdentityCheck(store),
        LookalikeCheck(store),
        DomainAgeCheck(registrations, today),
    ]
    if extractor is not None:
        checks.append(FidelityCheck(extractor))
    if entities is not None:
        checks.append(CounterpartyCheck(entities, store))
    # Last on purpose: it is the one check that writes, and the pipeline holds
    # its write back when a deciding check could not reach its source.
    checks.append(DuplicateCheck(store))
    return tuple(checks)
