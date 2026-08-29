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

from typing import Final

# The part of a name that says what kind of company it is rather than which one.
# Present or absent depending on who typed it, and never what anybody searches.
LEGAL_FORMS: Final = frozenset(
    {
        "ltd",
        "limited",
        "llc",
        "llp",
        "lp",
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "company",
        "plc",
        "gmbh",
        "ag",
        "bv",
        "nv",
        "sa",
        "sas",
        "srl",
        "spa",
        "ab",
        "oy",
        "as",
        "pty",
        "pte",
        "kk",
    }
)

# Forms written with a stroke, which splits them into single letters that are
# far too common to strip on their own. Matched as a trailing pair instead.
LEGAL_PAIRS: Final = frozenset({("a", "s"), ("s", "a"), ("a", "g"), ("k", "k")})


def words(name: str) -> tuple[str, ...]:
    """The significant words of a name, lowercased and stripped of punctuation."""
    cleaned = "".join(character if character.isalnum() else " " for character in name.lower())
    return tuple(word for word in cleaned.split() if word)


def trading_name(name: str) -> str:
    """The name with its legal form removed, for asking the world about it.

    Whether somebody writes "Northpost Freight Services" or the same followed by
    "Ltd" is not a fact about the company, and it must not change what diligence
    reports. Measured: the two spellings returned a different domain from live
    search, and the longer one refused an enrolment the shorter one allowed.

    Stripping only ever removes trailing forms, and never the whole name: a
    company actually called "Company" keeps its name.
    """
    parts = list(words(name))
    while len(parts) > 1:
        if parts[-1] in LEGAL_FORMS:
            parts.pop()
            continue
        if len(parts) > 2 and (parts[-2], parts[-1]) in LEGAL_PAIRS:
            del parts[-2:]
            continue
        break
    return " ".join(parts)


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
