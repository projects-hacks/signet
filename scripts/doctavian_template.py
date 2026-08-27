"""Upload the invoice template and print the urn to configure against a class.

Storage references are per account and not stable across environments, so the
urn belongs in the environment rather than in code.
"""

from __future__ import annotations

import sys
from pathlib import Path

from signet.adapters.doctavian import DoctavianRenderer
from signet.config import load_settings


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/northpost-invoice.docx")
    settings = load_settings()
    api_key, token, base_url = settings.doctavian.values
    renderer = DoctavianRenderer(
        api_key=api_key,
        token_provider=lambda: token,
        template_urns={},
        base_url=base_url,
    )
    urn = renderer.upload_template(path.name, path.read_bytes())
    print(f"DOCTAVIAN_TEMPLATES=invoice={path.name}:{urn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
