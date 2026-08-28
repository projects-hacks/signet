"""Whether a value read off a page is even the right shape for its field.

Confidence from an extractor is not a measure of legibility. Measured against a
photographed invoice, extraction returned an amount of "15.s80.00" and scored it
0.95. A letter inside a number is not a 95 percent reading of anything, and
treating it as one turns an authentic document into an accusation.

So the shape is checked here as well as the score. A field that cannot be what
it claims to be was not read cleanly, whatever the vendor says about it, and a
disagreement resting on that reading is a question for a person rather than a
finding against a document.

Only fields with a shape worth asserting appear here. A document identifier is
whatever the issuer says it is, so there is nothing to check and nothing is
claimed.
"""

from __future__ import annotations

import re
from typing import Final

# Presentation an extractor may legitimately return: an IBAN in groups of four,
# an amount with thousands separators.
_SEPARATORS: Final = re.compile(r"[\s,]")

_SHAPES: Final = {
    "amt": re.compile(r"^\d+(\.\d{1,2})?$"),
    "cur": re.compile(r"^[A-Za-z]{3}$"),
    "iban": re.compile(r"^[A-Za-z]{2}\d{2}[A-Za-z0-9]{10,30}$"),
    "bic": re.compile(r"^[A-Za-z]{4}[A-Za-z]{2}[A-Za-z0-9]{2}([A-Za-z0-9]{3})?$"),
}


def well_formed(field: str, value: str) -> bool:
    """Whether this reading could be a real value for this field."""
    shape = _SHAPES.get(field)
    if shape is None:
        return True
    return bool(shape.fullmatch(_SEPARATORS.sub("", value)))
