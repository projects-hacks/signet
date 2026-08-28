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


def _opened(opener: Any, content: bytes) -> Any:
    """Open an image, or say so in our own vocabulary.

    Anything a reader uploads can turn out not to be an image, and a caller that
    has to catch an imaging library's exception is a caller that has this
    adapter's dependencies in its own code.
    """
    try:
        return opener(io.BytesIO(content))
    except Exception as exc:
        raise AdapterError(f"could not decode the image: {exc}") from exc


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
        results = self._decode(_opened(self._open, content))
        return tuple(item.data.decode("utf-8", errors="replace") for item in results if item.data)


class ZxingDecoder:
    """Reads what OpenCV cannot, and installs from a wheel.

    OpenCV's detector fails on the larger versions this payload needs, which is
    how a mark that is plainly present reads as absent. This one carries its own
    native library, so unlike zbar it needs nothing from the system.
    """

    name = "zxing"

    def __init__(self) -> None:
        import zxingcpp
        from PIL import Image

        self._open = Image.open
        self._read = zxingcpp.read_barcodes

    def decode(self, content: bytes) -> tuple[str, ...]:
        results = self._read(_opened(self._open, content))
        return tuple(item.text for item in results if item.text)


class OpenCvDecoder:
    """A last resort, and optional.

    It was the only decoder here originally and it is the reason marks read as
    absent when they were plainly present: its detector fails on the versions
    this payload needs. Measured across the demo documents it reads the clean
    renders and fails on the photographed one, which is the case that matters,
    while zxing reads all four.

    So it is no longer a dependency. It weighs a hundred and twenty megabytes,
    more than the rest of the runtime put together, and it is kept only as a
    third opinion where somebody already has it installed.
    """

    name = "opencv"

    def __init__(self) -> None:
        import cv2

        self._cv2 = cv2
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
        import numpy as np

        image = self._cv2.imdecode(
            np.frombuffer(content, dtype=np.uint8), self._cv2.IMREAD_GRAYSCALE
        )
        if image is None:
            raise AdapterError("could not decode the image")
        return image


def available_decoders() -> tuple[Decoder, ...]:
    """Every decoder this machine can actually run, best first."""
    decoders: list[Decoder] = []
    with contextlib.suppress(ImportError, OSError):
        decoders.append(ZbarDecoder())
    with contextlib.suppress(ImportError, OSError):
        decoders.append(ZxingDecoder())
    with contextlib.suppress(ImportError, OSError):
        decoders.append(OpenCvDecoder())
    if not decoders:
        raise AdapterError(
            "No QR decoder is installed. Install zxing-cpp, which is the one this "
            "was measured against and ships as a wheel."
        )
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
