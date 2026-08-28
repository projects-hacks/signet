"""What the agent claims it read, and where it says it read it.

Enrolment starts from whatever somebody actually has: a forwarded thread, a
chat log, a scanned onboarding form. Nothing in that is labelled. A domain
appears three times meaning three different things, the brand is spelled two
ways, and the person who can sign is on a cc line under a legal disclaimer.

A model reading that will produce a domain and an email address either way, and
a wrong one looks exactly like a right one. So every field it extracts has to be
attributed: the value, and the line it came from. The line is then checked
against the source here rather than believed, which turns an assertion into
something falsifiable.

The check is deliberately literal. A quote that is not in the text is not a
quote, and a field nobody can point at does not reach a document somebody is
asked to sign.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

FIELDS: Final = ("domain", "brand", "signer_email", "signer_name")

# Fields that are strings a machine will act on rather than names a person
# writes differently. These have to appear in the source verbatim; a brand may
# reasonably be tidied from "NORTHPOST FREIGHT SERVICES LTD." on the way past.
VERBATIM: Final = ("domain", "signer_email")

_QUOTE_MARKERS: Final = re.compile(r"^[>|\s]+", re.MULTILINE)
_WHITESPACE: Final = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Interpretation:
    """One field, the value read for it, and the evidence for that reading."""

    field: str
    value: str
    quote: str
    alternative: str = ""

    @property
    def uncertain(self) -> bool:
        return bool(self.alternative.strip())

    @property
    def note(self) -> str:
        """A sentence for the person signing, never empty.

        An empty cell in a document reads as a rendering fault. A row that says
        nothing else fit is a row somebody can move past.
        """
        if self.uncertain:
            return f"also read as {self.alternative}, which was not chosen"
        return "nothing else in the text fit this field"


def flatten(text: str) -> str:
    """One line, no quoting furniture, comparable to another flattened line."""
    return _WHITESPACE.sub(" ", _QUOTE_MARKERS.sub(" ", text)).strip().casefold()


def quoted_from(quote: str, source: str) -> bool:
    """Whether this line is genuinely in what we were given."""
    flat = flatten(quote)
    return bool(flat) and flat in flatten(source)


def present_in(value: str, source: str) -> bool:
    """Whether the value itself survives anywhere in the source."""
    return bool(value.strip()) and value.strip().casefold() in flatten(source)
