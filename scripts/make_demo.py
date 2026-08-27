"""The three documents the demo examines, produced once and kept.

Two of them are what an adversary would send, so they are built here rather than
exposed as a flag on the issuing path. Nothing in the product should make it
convenient to sign one set of numbers and print another.

The documents are generated ahead of the walkthrough and committed as artifacts
because generation depends on a token that expires, and a demo that calls a
vendor live is a demo that fails on somebody else's outage.
"""

from __future__ import annotations

import json
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

KEYS = Path(".signet/keys")
OUT = Path("demo")
RECORD = Path("demo/records/inv-0611.json")

GENUINE_DOMAIN = "northpost.dev"
LOOKALIKE_DOMAIN = "north-post.dev"
TRUE_IBAN = "GB29NWBK60161331926819"
# The account an invoice redirection fraud substitutes. Same length and shape, so
# the swap survives a glance at the paper.
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
    return encode_mark(payload, Ed25519Signer(key).sign(payload)), format_locator(
        domain, document_id
    )


def main() -> int:
    renderer = document_renderer(load_settings())
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)

    def write(name: str, page_record: dict[str, Any], mark: str, locator: str) -> None:
        document = renderer.render("invoice", page_record, mark, locator)
        path = OUT / name
        path.write_bytes(page_with_mark(document, mark))
        print(f"  {path}")

    # Act one. Signed and printed from the same record.
    mark, locator = signed(GENUINE_DOMAIN, record, record["Number"])
    write("act1-genuine.png", record, mark, locator)

    # Act two. The mark still carries the real account because it was signed
    # before the page was altered, which is what makes the alteration detectable.
    doctored = deepcopy(record)
    doctored["Iban"] = SWAPPED_IBAN
    write("act2-doctored.png", doctored, mark, locator)

    # Act three. Nothing here is forged. A real domain, a real key, a real
    # signature. The name is the whole attack.
    forged = deepcopy(record)
    forged["PayeeDomain"] = LOOKALIKE_DOMAIN
    forged["Iban"] = SWAPPED_IBAN
    # The forger copies the invoice number too, so nothing on the page is out of
    # step with what was signed. Only the domain that signed it is wrong.
    forged_mark, forged_locator = signed(LOOKALIKE_DOMAIN, forged, record["Number"])
    write("act3-lookalike.png", forged, forged_mark, forged_locator)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
