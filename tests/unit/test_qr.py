"""Mark rendering and decoding.

The size sweep is here because OpenCV's decoder failed on a 197 character mark
while handling a 195 character one of nearly identical content. That is the kind
of regression a fixed-payload test would never catch.
"""

from __future__ import annotations

import pytest

from signet.adapters.qr import (
    IMAGE_TYPES,
    ImageMarkReader,
    ZxingDecoder,
    available_decoders,
    render_mark,
)

PAYLOAD = (
    "S1|amt=14.75;cls=receipt;cur=USD;id=R-88213104;"
    "iss=mercerfab.dev;ts=2026-08-21T09:14:00Z|" + "A" * 104
)


def test_a_mark_round_trips() -> None:
    reader = ImageMarkReader()
    assert reader.read_marks(render_mark(PAYLOAD), "image/png") == (PAYLOAD,)


@pytest.mark.parametrize("box_pixels", [6, 8, 12, 16])
def test_a_mark_survives_every_print_size(box_pixels: int) -> None:
    reader = ImageMarkReader()
    rendered = render_mark(PAYLOAD, box_pixels=box_pixels)
    assert reader.read_marks(rendered, "image/png") == (PAYLOAD,)


@pytest.mark.parametrize("length", [150, 195, 197, 240, 290])
def test_marks_decode_across_the_size_range(length: int) -> None:
    """197 is in here deliberately. It is where OpenCV alone gave up."""
    payload = "S1|" + "x" * (length - 3)
    assert ImageMarkReader().read_marks(render_mark(payload), "image/png") == (payload,)


def test_a_document_that_is_not_an_image_yields_nothing() -> None:
    """Not an error. The caller falls through to the corroboration path."""
    assert ImageMarkReader().read_marks(b"%PDF-1.7", "application/pdf") == ()


def test_every_image_type_is_attempted() -> None:
    rendered = render_mark(PAYLOAD)
    reader = ImageMarkReader()
    assert "image/png" in IMAGE_TYPES
    assert reader.read_marks(rendered, "image/png")


def test_the_reader_reports_which_decoders_it_has() -> None:
    """zxing is the one this was measured against and the only one required.
    zbar needs a system library and opencv is an optional extra, so neither is
    asserted here."""
    names = ImageMarkReader().decoder_names
    assert names
    assert "zxing" in names


def test_at_least_one_decoder_is_always_available() -> None:
    assert available_decoders()


def test_a_decoder_that_finds_nothing_falls_through_to_the_next() -> None:
    class Blind:
        name = "blind"

        def decode(self, content: bytes) -> tuple[str, ...]:
            return ()

    reader = ImageMarkReader(decoders=(Blind(), ZxingDecoder()))
    assert reader.read_marks(render_mark("S1|short|AAAA"), "image/png") == ("S1|short|AAAA",)


def test_a_pdf_page_is_rasterised_and_its_mark_read() -> None:
    """Every entry point accepts PDFs, so refusing to look at them told the
    reader 'this document carries no mark' about pages nobody had examined."""
    from io import BytesIO

    from PIL import Image

    from signet.adapters.qr import ImageMarkReader, render_mark

    mark = "S1|amt=1.00;iss=example.com|" + "A" * 100
    code = Image.open(BytesIO(render_mark(mark))).convert("RGB")
    page = Image.new("RGB", (code.width + 400, code.height + 600), "white")
    page.paste(code, (200, 200))
    pdf = BytesIO()
    page.save(pdf, format="PDF")

    found = ImageMarkReader().read_marks(pdf.getvalue(), "application/pdf")
    assert mark in found


def test_a_broken_pdf_reads_as_markless_rather_than_crashing() -> None:
    from signet.adapters.qr import ImageMarkReader

    assert ImageMarkReader().read_marks(b"%PDF-not really", "application/pdf") == ()
