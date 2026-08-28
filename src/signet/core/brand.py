"""When two names are the same company.

A reader is asked who a document claims to be from and types what is on the
paper, which is the trading name. The enrolment holds whatever the issuer
registered, which is usually the legal entity. "Northpost" and "Northpost
Freight Services" are the same company, and exact comparison flags every real
invoice where the header and the registration disagree by a suffix.

Comparison is on whole words, and one name matches the other only when it is a
leading run of the other's words. That distinction is the entire point:

    Northpost            vs Northpost Freight Services   same
    Northpost            vs North Post Holdings          different

Compacting to characters instead would make the second pair match, because
"northpostholdings" starts with "northpost". A lookalike that survives the
check by removing a space is exactly the forgery this product exists to catch,
so the comparison is deliberately blind to that trick.

Trailing words are descriptors. Leading words are identity.

The weak edge is that "Maersk" also matches "Maersk Rival Shipping", because
nothing in the words separates a descriptor a company chose from one a forger
inherited. That is accepted deliberately: refusing it would flag every invoice
whose header carries the trading name while the registration carries the legal
entity. What catches the forger is not here. Enrolment is reviewed by a person,
and the counterparty check asks the open web which domain the claimed brand
actually publishes.
"""

from __future__ import annotations


def words(name: str) -> tuple[str, ...]:
    """The significant words of a name, lowercased and stripped of punctuation."""
    cleaned = "".join(character if character.isalnum() else " " for character in name.lower())
    return tuple(word for word in cleaned.split() if word)


def same_brand(left: str, right: str) -> bool:
    """Whether these two names refer to the same company.

    True when one name's words are a leading run of the other's, so a trading
    name matches its legal entity while a rearrangement of the same letters
    does not.
    """
    first, second = words(left), words(right)
    if not first or not second:
        return False
    shorter, longer = sorted((first, second), key=len)
    return longer[: len(shorter)] == shorter
