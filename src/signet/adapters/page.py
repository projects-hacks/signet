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

from signet.errors import AdapterError

# Enough that a phone camera resolves the mark from a printed page.
RENDER_SCALE: Final = 2.0

# The mark sits in the lower right, clear of the text, sized against the page so
# it stays scannable whatever dimensions the template produces.
MARK_WIDTH: Final = 0.18
MARGIN: Final = 0.05


def page_with_mark(document: bytes, mark_image: bytes) -> bytes:
    """Rasterise the first page and print the mark on it, as PNG bytes."""
    try:
        pdf = pypdfium2.PdfDocument(document)
        page = pdf[0].render(scale=RENDER_SCALE).to_pil().convert("RGB")
    except Exception as exc:  # pypdfium2 raises its own hierarchy
        raise AdapterError(f"could not rasterise the rendered document: {exc}") from exc

    code = Image.open(BytesIO(mark_image)).convert("RGB")
    side = int(page.width * MARK_WIDTH)
    code = code.resize((side, side), Resampling.LANCZOS)

    margin = int(page.width * MARGIN)
    page.paste(code, (page.width - side - margin, page.height - side - margin))

    out = BytesIO()
    page.save(out, format="PNG")
    return out.getvalue()
