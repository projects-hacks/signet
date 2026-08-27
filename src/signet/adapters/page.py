"""Turn a rendered document into the page a reader actually holds.

The renderer produces a PDF and the mark is a QR code, so something has to put
one on the other. That join lives in an adapter because both halves are vendor
work: a PDF rasteriser and an image library. Doctavian does not know what a
Signet mark is, and the QR encoder does not know what an invoice is.

The page is rasterised deliberately. A PDF carrying a vector mark would verify
perfectly and prove nothing, because the path a real document takes is a
photograph of a printed page, and that is the path this has to survive.
"""

from __future__ import annotations

from io import BytesIO
from typing import Final

import pypdfium2
from PIL import Image
from PIL.Image import Resampling

from signet.adapters.qr import render_mark
from signet.errors import AdapterError

# Enough that a phone camera resolves the mark from a printed page.
RENDER_SCALE: Final = 2.0

# The mark sits in the lower right, clear of the text, sized against the page so
# it stays scannable whatever dimensions the template produces.
MARK_WIDTH: Final = 0.18
MARGIN: Final = 0.05
# Below about three, a phone camera cannot separate one module from the next.
MIN_PIXELS_PER_MODULE: Final = 3


def page_with_mark(document: bytes, mark: str) -> bytes:
    """Rasterise the first page and print the mark on it, as PNG bytes."""
    try:
        pdf = pypdfium2.PdfDocument(document)
        page = pdf[0].render(scale=RENDER_SCALE).to_pil().convert("RGB")
    except Exception as exc:  # pypdfium2 raises its own hierarchy
        raise AdapterError(f"could not rasterise the rendered document: {exc}") from exc

    # The mark arrives at one pixel per module and is enlarged by a whole
    # number of pixels. Anything else lands module edges between pixels, and a
    # code that is visibly there stops decoding.
    # One pixel per module, so the enlargement below is the only scaling.
    code = Image.open(BytesIO(render_mark(mark, box_pixels=1))).convert("RGB")
    factor = max(MIN_PIXELS_PER_MODULE, round(page.width * MARK_WIDTH / code.width))
    side = code.width * factor
    code = code.resize((side, side), Resampling.NEAREST)

    margin = int(page.width * MARGIN)
    page.paste(code, (page.width - side - margin, page.height - side - margin))

    out = BytesIO()
    page.save(out, format="PNG")
    return out.getvalue()
