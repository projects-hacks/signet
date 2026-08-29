"""When two names are the same company.

The reader types the trading name off the paper. The enrolment holds the legal
entity. Getting this wrong in either direction is expensive: too strict flags
every real invoice, too loose lets a lookalike through.
"""

from __future__ import annotations

import pytest

from signet.core.brand import same_brand, trading_name, words


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Northpost", "Northpost Freight Services"),
        ("Northpost Freight Services", "Northpost"),
        ("Maersk", "Maersk Line"),
        ("Stripe", "Stripe, Inc."),
        ("northpost", "NORTHPOST"),
        ("Kuehne + Nagel", "Kuehne Nagel"),
    ],
)
def test_a_trading_name_matches_its_legal_entity(left: str, right: str) -> None:
    assert same_brand(left, right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        # The one that matters. Compacting to characters would match these,
        # because "northpostholdings" starts with "northpost", and a lookalike
        # that survives by removing a space is the forgery this exists to catch.
        ("Northpost", "North Post Holdings"),
        ("Northpost Freight Services", "North Post Holdings"),
        ("Stripe", "Stripes"),
        ("Northpost", ""),
        ("", "Northpost"),
    ],
)
def test_a_rearrangement_is_a_different_company(left: str, right: str) -> None:
    assert not same_brand(left, right)


def test_a_leading_name_matches_whatever_follows_it() -> None:
    """A deliberate trade, and the weak edge of this rule.

    "Maersk" matches "Maersk Rival Shipping", because nothing in the words
    themselves separates a descriptor a company chose for itself from one a
    forger chose to inherit a name. Refusing it would mean flagging every
    invoice whose header carries the trading name and whose registration
    carries the legal entity, which is most of them.

    What backstops it is not this function. Enrolment binds a brand to a domain
    only after a person reviews it, and the counterparty check separately asks
    the open web which domain the claimed brand actually publishes. A forger
    enrolling as "Maersk Rival Shipping" still fails that one.
    """
    assert same_brand("Maersk", "Maersk Rival Shipping")


def test_a_trailing_descriptor_never_becomes_identity() -> None:
    """Leading words are who a company is. Trailing words are what it does,
    and half an industry shares them."""
    assert not same_brand("Freight Services", "Northpost Freight Services")


def test_punctuation_and_spacing_are_not_the_name() -> None:
    assert words("Kuehne + Nagel, Ltd.") == ("kuehne", "nagel", "ltd")


def test_the_legal_form_is_not_part_of_what_the_world_is_asked() -> None:
    """Measured: the two spellings returned a different domain from live search,
    and the longer one refused an enrolment the shorter one allowed."""
    assert trading_name("Northpost Freight Services Ltd") == "northpost freight services"
    assert trading_name("Northpost Freight Services") == "northpost freight services"


@pytest.mark.parametrize(
    "written",
    [
        "Maersk A/S",
        "Maersk",
        "MAERSK  Inc.",
        "Maersk Corporation",
        "maersk, LLC",
    ],
)
def test_one_company_asks_one_question(written: str) -> None:
    assert trading_name(written) == "maersk"


def test_a_name_is_never_stripped_to_nothing() -> None:
    """A company actually called Company keeps its name."""
    assert trading_name("Company") == "company"
    assert trading_name("Ltd") == "ltd"
