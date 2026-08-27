"""Author the enrolment authorisation Doctavian renders and a person signs.

This is the document the whole Foxit argument turns on. It states, in words a
non engineer can hold someone to, exactly what publishing a key to a domain
means and how long it lasts. Somebody puts their name to that claim before any
key becomes live.

Two things are load bearing in the markup.

The authorisation hash is printed as ordinary body text. The broker downloads
the executed document, reads it back as text, and looks for that string. A
webhook field says a person acted; the hash says what they acted on, and only
the second is something we put there ourselves.

The signature and date fields are eSign text tags rather than coordinates. A
tag travels with the sentence it belongs to, so a longer diligence section moves
the signature block with it. Coordinates guessed at authoring time do not move,
and a signature box that lands on the wrong paragraph is worse than one that is
hard to place.
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

OUT = Path("assets/signet-authorisation.docx")


def line(
    document: Document,
    text: str,
    *,
    size: int = 10,
    bold: bool = False,
    space_after: int = 4,
    mono: bool = False,
) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_after = Pt(space_after)
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "Courier New" if mono else "Helvetica"


def build() -> None:
    document = Document()
    for section in document.sections:
        section.left_margin = section.right_margin = Pt(54)
        section.top_margin = section.bottom_margin = Pt(54)

    line(document, "SIGNET", size=20, bold=True, space_after=0)
    line(document, "Enrolment authorisation", size=9, space_after=18)

    line(
        document,
        "{!Enrolment.Brand} at {!Enrolment.Domain}",
        size=14,
        bold=True,
        space_after=10,
    )
    line(
        document,
        "This authorises Signet to publish a signing key in the DNS of "
        "{!Enrolment.Domain}. Read the next paragraph before signing.",
        space_after=14,
    )

    line(document, "WHAT YOU ARE AGREEING TO", size=9, bold=True, space_after=4)
    line(
        document,
        "Once this record is live, any document signed with the matching private "
        "key will verify as issued by {!Enrolment.Domain}, to anyone, anywhere, "
        "with no further involvement from you. There is no expiry. Removing the "
        "DNS record is the only way to stop it, and documents already signed "
        "keep verifying until you do.",
        space_after=10,
    )
    line(
        document,
        "Sign this only if you control the DNS for {!Enrolment.Domain} and intend "
        "that domain to vouch for documents issued in its name.",
        space_after=14,
    )

    line(document, "THE RECORD TO BE PUBLISHED", size=9, bold=True, space_after=4)
    line(document, "_signet.{!Enrolment.Domain}   TXT", size=9, mono=True, space_after=2)
    line(document, "{!Enrolment.Record}", size=8, mono=True, space_after=10)
    line(document, "Key fingerprint   {!Enrolment.Fingerprint}", size=9, mono=True, space_after=14)

    line(document, "WHAT WAS CHECKED BEFORE ASKING", size=9, bold=True, space_after=4)
    line(document, "{!Enrolment.Diligence}", size=9, space_after=14)

    # The string the broker looks for in the executed document. Printed rather
    # than encoded, so a person can compare it against what they were sent.
    line(document, "AUTHORISATION REFERENCE", size=9, bold=True, space_after=4)
    line(document, "{!Enrolment.AuthorisationHash}", size=9, mono=True, space_after=2)
    line(
        document,
        "Quote this reference in any query. The key is published only after a "
        "signed copy of this document carrying this exact reference is read back.",
        size=8,
        space_after=20,
    )

    line(document, "SIGNED FOR {!Enrolment.Brand}", size=9, bold=True, space_after=8)
    line(document, "Name       ${textfield:1:y:Signer_Name:________________}", space_after=6)
    line(document, "Role       ${textfield:1:y:Signer_Role:________________}", space_after=6)
    line(document, "Signature  ${signfield:1:y:____________}", space_after=6)
    line(document, "Date       ${datefield:1:y:Date_Signed:__________}", space_after=0)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUT)
    print(f"  wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
    sys.exit(0)
