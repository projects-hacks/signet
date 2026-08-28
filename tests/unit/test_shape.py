"""Whether a reading is the right shape for its field.

The cases here are the ones an extractor actually produced, not invented ones.
"""

from __future__ import annotations

import pytest

from signet.core.shape import well_formed


@pytest.mark.parametrize(
    "field,value",
    [
        ("amt", "15580.00"),
        ("amt", "15,580.00"),
        ("amt", "15 580.00"),
        # An amount is written differently everywhere, and asserting one
        # convention would send every invoice using another one to a person.
        ("amt", "$15,580.00"),
        ("amt", "USD 15580.00"),
        ("amt", "15,580.00 USD"),
        ("amt", "1.234,56"),
        ("amt", "15580"),
        ("amt", "1,234,567.89"),
        ("cur", "USD"),
        ("iban", "GB29NWBK60161331926819"),
        ("iban", "GB29 NWBK 6016 1331 9268 19"),
        ("bic", "NWBKGB2L"),
        ("bic", "NWBKGB2LXXX"),
        # Nothing is claimed about an identifier, so nothing rejects one.
        ("id", "INV- 2026-0611"),
        ("id", "anything at all"),
    ],
)
def test_values_a_page_can_legitimately_carry(field: str, value: str) -> None:
    assert well_formed(field, value)


@pytest.mark.parametrize(
    "field,value",
    [
        # Returned at 0.95 from a photograph of a genuine invoice.
        ("amt", "15.s80.00"),
        ("iban", "GB2 SNWBK60161331926819"),
        # Invented on the same page, also at 0.95.
        ("bic", "CORALDETTE33"),
        ("cur", "US"),
        ("amt", ""),
        # A letter where a digit belongs, which is the whole point of this.
        ("amt", "O15580.00"),
        ("amt", "l5580.00"),
        ("amt", "15,5B0.00"),
        ("amt", "--"),
        # Every character an amount may contain, and no amount anybody writes.
        # Returned by extraction from a photograph of a genuine invoice.
        ("amt", "15.80.00"),
        ("amt", "15.5800.00"),
    ],
)
def test_values_no_page_can_carry(field: str, value: str) -> None:
    assert not well_formed(field, value)
