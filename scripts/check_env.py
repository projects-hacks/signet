"""Report which services are configured, and whether the live ones answer.

Run after pasting keys into .env. Configuration and connectivity are different
failures, so they are reported separately: a key can be present and still wrong.

Nothing here prints a secret.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from signet.config import Settings, load_settings
from signet.errors import AdapterError

OK = "  ok    "
MISSING = "  unset "
FAILED = "  failed"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _probe_page() -> bytes:
    """The smallest real PDF that carries a readable identifier."""
    text = b"BT /F1 14 Tf 60 720 Td (Signet probe) Tj 0 -28 Td (Invoice PROBE-1) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(text) + text + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + obj + b"\nendobj\n"
    start = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        start,
    )
    return bytes(out)


_PROBE_PDF = _probe_page()


def probe_live(settings: Settings) -> list[tuple[str, str, str]]:
    """Call the services whose credentials are present. Read-only calls only."""
    from signet.adapters.doctavian import DoctavianRenderer
    from signet.adapters.namecom import NameComClient, NameComRegistrar
    from signet.adapters.nutrient import NutrientClient, NutrientExtractor
    from signet.adapters.rdap import RdapRegistrationData
    from signet.adapters.xano import XanoRecordStore

    results: list[tuple[str, str, str]] = []

    try:
        registration = RdapRegistrationData().registration("stripe.com")
        results.append(("RDAP", OK, f"stripe.com registered {registration.created}"))
    except AdapterError as exc:
        results.append(("RDAP", FAILED, str(exc)[:70]))

    if settings.namecom.configured:
        username, token, base_url = settings.namecom.values
        try:
            registrar = NameComRegistrar(NameComClient(username, token, base_url))
            available = registrar.available((settings.demo.issuer_domain or "example.com",))
            results.append(
                ("name.com", OK, f"availability answered for {len(available)} domain(s)")
            )
        except (AdapterError, ValueError) as exc:
            results.append(("name.com", FAILED, str(exc)[:70]))

    if settings.doctavian.configured:
        api_key, token = settings.doctavian.values
        try:
            renderer = DoctavianRenderer(
                api_key=api_key, token_provider=lambda: token, template_urns={}
            )
            renderer.ping()
            results.append(("Doctavian", OK, "both the token and the key were accepted"))
        except AdapterError as exc:
            results.append(("Doctavian", FAILED, str(exc)[:70]))

    if settings.nutrient.configured:
        try:
            # A real extraction, because the failure worth catching is an entitlement
            # one and only the endpoint we depend on can report that honestly.
            extractor = NutrientExtractor(NutrientClient(settings.nutrient.values[0]))
            found = extractor.extract(_PROBE_PDF, "application/pdf").by_name()
            read = found["id"].value if "id" in found else "nothing"
            results.append(("Nutrient", OK, f"extracted {read} from a probe page"))
        except AdapterError as exc:
            results.append(("Nutrient", FAILED, str(exc)[:70]))

    if settings.xano.configured:
        base_url, api_key = settings.xano.values
        try:
            XanoRecordStore(base_url, api_key).issuer("connectivity-probe.invalid")
            results.append(("Xano", OK, "the API group answered and the key was accepted"))
        except (AdapterError, ValueError) as exc:
            results.append(("Xano", FAILED, str(exc)[:70]))

    return results


def main() -> int:
    load_dotenv(Path(".env"))
    settings = load_settings()

    print(f"fixtures: {'on, no live calls will be made' if settings.fixtures else 'off'}\n")
    print("configuration")
    services = (
        settings.xano,
        settings.nutrient,
        settings.foxit_services,
        settings.foxit_esign,
        settings.doctavian,
        settings.doctavian_signatures,
        settings.namecom,
        settings.serpapi,
        settings.llm,
    )
    for service in services:
        print(f"{OK if service.configured else MISSING}  {service.name}")

    demo = settings.demo
    print(f"\ndemo domains: {demo.issuer_domain or 'unset'} / {demo.lookalike_domain or 'unset'}")

    if settings.fixtures:
        print("\nSet SIGNET_FIXTURES=0 to probe the live services.")
        return 0

    print("\nconnectivity")
    for name, status, detail in probe_live(settings):
        print(f"{status}  {name:12} {detail}")

    missing = settings.unconfigured()
    if missing:
        print(f"\nStill unconfigured: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
