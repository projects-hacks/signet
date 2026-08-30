"""Render the base pages the sample endpoint stamps, once, and their manifest.

The pages are committed rather than rendered on demand because rendering needs
a Doctavian session and the sample endpoint must not: a public button that
depends on a token that expires hourly is a button that stops working during
judging. The signature is the part minted per request; the paper is fixed.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from signet.adapters.page import rasterise
from signet.adapters.renderers import document_renderer
from signet.config import load_env_file, load_settings

OUT = Path("assets/samples")
RECORD = Path("demo/records/inv-0611.json")

GENUINE_DOMAIN = "northpost.dev"
LOOKALIKE_DOMAIN = "north-post.dev"
TRUE_IBAN = "GB29NWBK60161331926819"
SWAPPED_IBAN = "GB94BARC10201530093459"


def signed_fields(record: dict[str, Any], iban: str) -> dict[str, str]:
    return {
        "cls": "invoice",
        "id": record["Number"],
        "amt": f"{sum(item['LineAmount'] for item in record['LineItems']):.2f}",
        "cur": record["Currency"],
        "iban": iban,
        "bic": record["Bic"],
    }


def main() -> int:
    load_env_file()
    renderer = document_renderer(load_settings())
    base = json.loads(RECORD.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    def page(name: str, record: dict[str, Any]) -> None:
        locator = f"{record['PayeeDomain']}/{record['Number']}"
        document = renderer.render("invoice", record, "", locator)
        (OUT / name).write_bytes(rasterise(document))
        print(f"  {OUT / name}")

    # The honest page. Signed over exactly what it prints.
    page("genuine.png", base)

    # The interception. The page shows the fraudster's account; the signature
    # in the manifest covers the account the issuer actually holds, because a
    # forger cannot re-sign after altering the paper.
    doctored = deepcopy(base)
    doctored["Iban"] = SWAPPED_IBAN
    page("doctored.png", doctored)

    # The impersonation. Internally consistent, signed by the wrong domain.
    forged = deepcopy(base)
    forged["PayeeDomain"] = LOOKALIKE_DOMAIN
    forged["Iban"] = SWAPPED_IBAN
    page("lookalike.png", forged)

    manifest = {
        "genuine": {
            "page": "genuine.png",
            "issuer": GENUINE_DOMAIN,
            "fields": signed_fields(base, TRUE_IBAN),
        },
        "doctored": {
            "page": "doctored.png",
            "issuer": GENUINE_DOMAIN,
            "fields": signed_fields(base, TRUE_IBAN),
        },
        "lookalike": {
            "page": "lookalike.png",
            "issuer": LOOKALIKE_DOMAIN,
            "fields": signed_fields(forged, SWAPPED_IBAN),
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"  {OUT / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
