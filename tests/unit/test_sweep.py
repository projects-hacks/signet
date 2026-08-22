"""The enrolment sweep: a registrar's availability answer, read backwards."""

from __future__ import annotations

import pytest

from signet.core.lookalike import permutations
from signet.issue.sweep import LookalikeSweep
from tests.fakes import FakeDomainRegistrar

DOMAIN = "northpost.dev"
SQUAT = "north-post.dev"


class RecordingRegistrar(FakeDomainRegistrar):
    """A registrar that remembers how it was asked."""

    def __init__(self, taken: set[str] | None = None) -> None:
        super().__init__(taken)
        self.batches: list[tuple[str, ...]] = []

    def available(self, domains: tuple[str, ...]) -> dict[str, bool]:
        self.batches.append(domains)
        return super().available(domains)


class SilentRegistrar(FakeDomainRegistrar):
    """A registrar that answers for part of the batch, as they do for odd suffixes."""

    def __init__(self, silent_about: str) -> None:
        super().__init__()
        self.silent_about = silent_about

    def available(self, domains: tuple[str, ...]) -> dict[str, bool]:
        answered = super().available(domains)
        answered.pop(self.silent_about, None)
        return answered


def test_the_sweep_reports_every_permutation() -> None:
    swept = LookalikeSweep(FakeDomainRegistrar()).sweep(DOMAIN)
    assert tuple(neighbour.domain for neighbour in swept) == permutations(DOMAIN)


def test_a_name_nobody_owns_is_not_worth_an_alert() -> None:
    assert LookalikeSweep(FakeDomainRegistrar()).alerts(DOMAIN) == ()


def test_a_registered_permutation_of_your_own_domain_is_the_alert() -> None:
    alerts = LookalikeSweep(FakeDomainRegistrar({SQUAT})).alerts(DOMAIN)
    assert [neighbour.domain for neighbour in alerts] == [SQUAT]


def test_a_taken_name_is_registered_and_a_free_one_is_not() -> None:
    swept = LookalikeSweep(FakeDomainRegistrar({SQUAT})).sweep(DOMAIN)
    held = {neighbour.domain: neighbour.registered for neighbour in swept}
    assert held[SQUAT] is True
    assert held["northpost.com"] is False


def test_a_name_the_registrar_did_not_answer_for_is_unknown_rather_than_free() -> None:
    """Silence is not an all clear."""
    swept = LookalikeSweep(SilentRegistrar(SQUAT)).sweep(DOMAIN)
    unanswered = next(found for found in swept if found.domain == SQUAT)
    assert unanswered.registered is None
    assert not unanswered.alerting


def test_availability_is_asked_in_batches_rather_than_once_per_name() -> None:
    registrar = RecordingRegistrar()
    LookalikeSweep(registrar).sweep(DOMAIN)
    assert len(registrar.batches) < len(permutations(DOMAIN))


def test_every_permutation_reaches_the_registrar_exactly_once() -> None:
    registrar = RecordingRegistrar()
    LookalikeSweep(registrar).sweep(DOMAIN)
    asked = [domain for batch in registrar.batches for domain in batch]
    assert sorted(asked) == sorted(permutations(DOMAIN))


def test_no_batch_exceeds_the_size_it_was_given() -> None:
    registrar = RecordingRegistrar()
    LookalikeSweep(registrar, batch_size=7).sweep(DOMAIN)
    assert all(len(batch) <= 7 for batch in registrar.batches)


def test_alerts_put_the_closest_imitation_first() -> None:
    registrar = FakeDomainRegistrar({SQUAT, "nothpost.dev"})
    alerts = LookalikeSweep(registrar).alerts(DOMAIN)
    assert [neighbour.domain for neighbour in alerts] == [SQUAT, "nothpost.dev"]


def test_a_domain_with_no_label_asks_the_registrar_nothing() -> None:
    registrar = RecordingRegistrar()
    assert LookalikeSweep(registrar).sweep("") == ()
    assert registrar.batches == []


def test_a_batch_size_below_one_is_rejected() -> None:
    with pytest.raises(ValueError):
        LookalikeSweep(FakeDomainRegistrar(), batch_size=0)
