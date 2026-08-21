"""Reading and drawing the mark.

Local rather than a service call. Nutrient's json-content build has no barcode
option, and a round trip to any API would put the demo's most visible moment on
the network. A photographed receipt decodes offline in milliseconds.

Two decoders, tried in order, because OpenCV's is not good enough on its own.
Measured on our own payloads: it decoded a 195 character mark at every size
tried and failed on a 197 character one of nearly identical content, returning
a successful detection with empty text. zbar decoded every case, including 400
characters. So zbar leads and OpenCV is the fallback for machines without the
system library.

Rendering lives here too, so the encode and decode halves cannot drift apart.
"""

from __future__ import annotations

import contextlib
import io
from typing import Any, Final, Protocol

import cv2
import numpy as np
import qrcode
from qrcode.constants import ERROR_CORRECT_Q
from qrcode.image.pil import PilImage

from signet.errors import AdapterError

# Q recovers from about a quarter of the code being unreadable. Thermal paper
# fades, receipts crease down the middle and phone photos add glare, so the
# extra modules buy more than they cost.
ERROR_CORRECTION: Final = ERROR_CORRECT_Q
_QUIET_ZONE: Final = 4
_BOX_PIXELS: Final = 8

IMAGE_TYPES: Final = ("image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp")


def render_mark(text: str, box_pixels: int = _BOX_PIXELS) -> bytes:
    """Draw a mark as a PNG, ready to place on a document."""
    code = qrcode.QRCode(error_correction=ERROR_CORRECTION, box_size=box_pixels, border=_QUIET_ZONE)
    code.add_data(text)
    code.make(fit=True)
    buffer = io.BytesIO()
    # Name the factory rather than letting qrcode pick one. The pure-Python
    # fallback writes a different format, and a mark that renders differently
    # depending on what is installed is a bug waiting for the wrong machine.
    code.make_image(image_factory=PilImage, fill_color="black", back_color="white").save(
        buffer, format="PNG"
    )
    return buffer.getvalue()


class Decoder(Protocol):
    name: str

    def decode(self, content: bytes) -> tuple[str, ...]: ...


class ZbarDecoder:
    """The reliable one. Needs libzbar.

    Install with `brew install zbar` or `apt install libzbar0`. On macOS the
    loader reads DYLD_LIBRARY_PATH when the process starts, so Homebrew's lib
    directory has to be on it before Python runs. The Makefile sets it; setting
    it from inside the process is too late and does nothing, which is why no
    attempt is made here.
    """

    name = "zbar"

    def __init__(self) -> None:
        from PIL import Image
        from pyzbar.pyzbar import decode  # type: ignore[import-untyped]

        self._open = Image.open
        self._decode = decode

    def decode(self, content: bytes) -> tuple[str, ...]:
        results = self._decode(self._open(io.BytesIO(content)))
        return tuple(item.data.decode("utf-8", errors="replace") for item in results if item.data)


class OpenCvDecoder:
    """Always available, but see the module docstring before relying on it."""

    name = "opencv"

    def __init__(self) -> None:
        self._detector = cv2.QRCodeDetector()

    def decode(self, content: bytes) -> tuple[str, ...]:
        image = self._image(content)
        ok, decoded, _, _ = self._detector.detectAndDecodeMulti(image)
        # A successful detection with empty text is the failure mode described
        # above, so emptiness is filtered rather than trusted.
        found = tuple(text for text in decoded if text) if ok else ()
        if found:
            return found
        single, _, _ = self._detector.detectAndDecode(image)
        return (single,) if single else ()

    def _image(self, content: bytes) -> Any:
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise AdapterError("could not decode the image")
        return image


def available_decoders() -> tuple[Decoder, ...]:
    """Every decoder this machine can actually run, best first."""
    decoders: list[Decoder] = []
    with contextlib.suppress(ImportError, OSError):
        decoders.append(ZbarDecoder())
    decoders.append(OpenCvDecoder())
    return tuple(decoders)


class ImageMarkReader:
    """Implements MarkReader. Tries each decoder until one reads something."""

    def __init__(self, decoders: tuple[Decoder, ...] | None = None) -> None:
        self._decoders = decoders if decoders is not None else available_decoders()

    @property
    def decoder_names(self) -> tuple[str, ...]:
        return tuple(decoder.name for decoder in self._decoders)

    def read_marks(self, content: bytes, media_type: str) -> tuple[str, ...]:
        if media_type not in IMAGE_TYPES:
            # PDFs and Office files arrive as documents whose pages we have not
            # rasterised. Nothing to read, and that is not an error: the caller
            # falls through to the corroboration path.
            return ()
        for decoder in self._decoders:
            found = decoder.decode(content)
            if found:
                return found
        return ()
