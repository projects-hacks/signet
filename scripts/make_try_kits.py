"""Numbered sets of documents a stranger can verify without tripping over us.

The submissions ledger is global on purpose: replaying a genuine document is
visible to every verifier, not only to the one that saw it first. That is
correct, and it means one shared sample file works exactly once. The second
person to try it is told it is a duplicate, which is true and useless as a first
impression.

So each tester gets their own kit. Within a kit every document carries its own
signature over its own numbers, so each verdict isolates one behaviour:

  1  genuine        certified, because nothing is wrong with it
  2  doctored       flagged on the page disagreeing with the signature, and
                    nothing else, because its signature was never submitted
  3  lookalike      flagged on identity, with a real key and a real signature
  4  the same again  flagged as a duplicate, which is the point of it

Two of them are what an adversary would send, so they are built here rather than
exposed as a flag on the issuing path. Nothing in the product should make it
convenient to sign one set of numbers and print another.
"""

from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from signet.adapters.page import page_with_mark
from signet.adapters.renderers import document_renderer
from signet.config import load_settings
from signet.core.mark import encode_mark, format_locator
from signet.core.payload import canonicalize
from signet.core.signing import Ed25519Signer
from signet.ports.documents import DocumentRenderer

KEYS = Path(".signet/keys")
RECORD = Path("demo/records/inv-0611.json")

GENUINE_DOMAIN = "northpost.dev"
LOOKALIKE_DOMAIN = "north-post.dev"
SWAPPED_IBAN = "GB94BARC10201530093459"


def signed(domain: str, record: dict[str, Any], document_id: str) -> tuple[str, str]:
    fields = {
        "iss": domain,
        "cls": "invoice",
        "id": document_id,
        "amt": f"{sum(item['LineAmount'] for item in record['LineItems']):.2f}",
        "cur": record["Currency"],
        "iban": record["Iban"],
        "bic": record["Bic"],
        "ts": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    payload = canonicalize(fields)
    key = (KEYS / f"{domain}.key").read_bytes()
    signer = Ed25519Signer(key)
    return encode_mark(payload, signer.sign(payload)), format_locator(domain, document_id)


def write(
    renderer: DocumentRenderer, path: Path, record: dict[str, Any], mark: str, url: str
) -> None:
    path.write_bytes(page_with_mark(renderer.render("invoice", record, mark, url), mark))
    print(f"  {path}")


def kit(renderer: DocumentRenderer, base: dict[str, Any], out: Path, number: int) -> None:
    out.mkdir(parents=True, exist_ok=True)

    # Every document in the kit gets its own invoice number, so no two kits and
    # no two documents within a kit share a fingerprint in the ledger.
    genuine = deepcopy(base)
    genuine["Number"] = f"{base['Number']}-{number:02d}A"
    mark, url = signed(GENUINE_DOMAIN, genuine, genuine["Number"])
    write(renderer, out / "1-genuine.png", genuine, mark, url)

    # Signed from its own clean record, then the page is altered. The mark still
    # carries the real account, which is what makes the alteration detectable,
    # and this signature has never been submitted so the only complaint is the
    # one the document deserves.
    clean = deepcopy(base)
    clean["Number"] = f"{base['Number']}-{number:02d}B"
    doctored_mark, doctored_url = signed(GENUINE_DOMAIN, clean, clean["Number"])
    doctored = deepcopy(clean)
    doctored["Iban"] = SWAPPED_IBAN
    write(renderer, out / "2-doctored.png", doctored, doctored_mark, doctored_url)

    # Nothing here is forged. A real domain, a real key, a real signature. The
    # forger copies the invoice number too, so only the signing domain is wrong.
    forged = deepcopy(base)
    forged["Number"] = f"{base['Number']}-{number:02d}C"
    forged["PayeeDomain"] = LOOKALIKE_DOMAIN
    forged["Iban"] = SWAPPED_IBAN
    forged_mark, forged_url = signed(LOOKALIKE_DOMAIN, forged, forged["Number"])
    write(renderer, out / "3-lookalike.png", forged, forged_mark, forged_url)

    # Byte for byte the first document. Verified after it, it is a duplicate.
    shutil.copyfile(out / "1-genuine.png", out / "4-the-same-invoice-again.png")
    print(f"  {out / '4-the-same-invoice-again.png'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kits", type=int, default=5)
    parser.add_argument("--out", default="assets/try")
    parser.add_argument("--first", type=int, default=1, help="number the first kit from here")
    args = parser.parse_args()

    renderer = document_renderer(load_settings())
    base = json.loads(RECORD.read_text(encoding="utf-8"))
    root = Path(args.out)
    for number in range(args.first, args.first + args.kits):
        print(f"kit {number}")
        kit(renderer, base, root / f"kit-{number:02d}", number)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
