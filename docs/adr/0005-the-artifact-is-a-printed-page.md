# 5. The canonical artifact is a printed page

Accepted, 2026-08-22.

## Context

The obvious carrier for a signed document is PDF metadata: embed the signature
in the file and verify the bytes. It proves the wrong thing. Documents that
decide payments are printed, photographed, scanned, faxed and pasted into
email threads, and a proof that dies at the first photocopier protects only
the rare document that stays digital.

## Decision

The proof rides on the face of the page, as a QR mark, and the issuing path
rasterises the rendered document deliberately: a PDF carrying a vector mark
would verify perfectly and prove nothing about the path real paper takes.
Whatever survives a phone photograph of a printed page is the product.

The mark is budgeted against that path. It stays within QR version 8, where
decoding off crumpled thermal paper is still reliable, which is why the
Merkle proof is excluded from the mark and fetched by locator instead. Error
correction is level Q, for glare and creases. The text is base32, to stay in
the QR alphanumeric mode. Encoding above the byte cap raises rather than
silently producing an unscannable code.

Reading is a ladder of decoders, kept in measured order. OpenCV was dropped
from the default install: 120 megabytes, more than the rest of the runtime
together, and it failed on the one photographed page that mattered while
zxing read all four.

A verifier accepts the page in whatever container it arrives: an image
directly, or a PDF whose first page is rasterised through the same code the
issuing path uses.

## Consequences

The demo path and the threat path are the same path. What is photographed on
stage is what a supplier's invoice actually goes through.

A damaged mark degrades rather than dying: the printed locator still names
where the key lives, so a person can fall back to checking by hand.

The page must match what was signed, which is why the fidelity check exists
at all: rasterising makes the visible page authoritative, so the visible page
is what gets compared.
