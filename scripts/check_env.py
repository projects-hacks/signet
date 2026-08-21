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


def probe_live(settings: Settings) -> list[tuple[str, str, str]]:
    """Call the services whose credentials are present. Read-only calls only."""
    from signet.adapters.namecom import NameComClient, NameComRegistrar
    from signet.adapters.nutrient import NutrientClient
    from signet.adapters.rdap import RdapRegistrationData

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

    if settings.nutrient.configured:
        try:
            NutrientClient(settings.nutrient.values[0]).post("/tokens", json={"expirationTime": 60})
            results.append(("Nutrient", OK, "minted a scoped token"))
        except AdapterError as exc:
            results.append(("Nutrient", FAILED, str(exc)[:70]))

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
