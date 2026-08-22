"""Which imitations of an issuer's domain already exist.

Enrolment is the moment to ask this, and verification is not. A squat registered
this morning says nothing new about an invoice signed last month, and putting a
registrar round trip inside the verdict path makes every verdict depend on
somebody else's uptime. So this lives in issue, runs when an issuer joins and
again on a schedule, and produces a list a person reads.

The registrar's availability answer is read backwards. It exists to sell the
names that are free; what an issuer needs is the small set that is not, because a
permutation of your own domain that somebody already owns is either a defensive
registration you made or a squat you did not.

Calls are batched. One lookup per permutation is several hundred requests against
a service that allows twenty a second, so the neighbourhood goes up in chunks and
a whole sweep costs a handful of calls.

A registrar that answers for only part of a batch leaves the rest unknown rather
than free, because silence is not an all clear and a monitoring tool that reports
one as the other is worse than no tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from signet.core.lookalike import confusability, permutations
from signet.ports.registry import DomainRegistrar

# Large enough that a full neighbourhood is under a dozen calls, small enough
# that one rejected batch does not cost the whole sweep.
BATCH_SIZE: Final = 50


@dataclass(frozen=True, slots=True)
class Neighbour:
    """One permutation of the swept domain, and who holds it."""

    domain: str
    registered: bool | None
    confusability: float

    @property
    def alerting(self) -> bool:
        """Registered by someone. Unknown is not an alert, and neither is free."""
        return self.registered is True


class LookalikeSweep:
    def __init__(self, registrar: DomainRegistrar, batch_size: int = BATCH_SIZE) -> None:
        if batch_size < 1:
            raise ValueError("batch size must be at least one")
        self._registrar = registrar
        self._batch_size = batch_size

    def sweep(self, domain: str) -> tuple[Neighbour, ...]:
        """Every permutation of domain, each marked with whether it is taken.

        Returned in permutation order rather than by severity, so two sweeps of
        the same domain a month apart diff line by line.
        """
        candidates = permutations(domain)
        availability: dict[str, bool] = {}
        for start in range(0, len(candidates), self._batch_size):
            batch = candidates[start : start + self._batch_size]
            availability.update(self._registrar.available(batch))

        return tuple(
            Neighbour(
                domain=candidate,
                registered=None if candidate not in availability else not availability[candidate],
                confusability=confusability(domain, candidate),
            )
            for candidate in candidates
        )

    def alerts(self, domain: str) -> tuple[Neighbour, ...]:
        """The neighbours somebody already owns, closest imitation first."""
        taken = [neighbour for neighbour in self.sweep(domain) if neighbour.alerting]
        return tuple(sorted(taken, key=lambda found: (-found.confusability, found.domain)))
