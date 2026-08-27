"""Registration data from the registry.

RDAP is the IANA standard successor to WHOIS: public, keyless, and authoritative
in a way a registrar API is not. name.com exposes no creation date, so domain age
comes from here.

Registries reset the creation date on some transfers, so a young date means the
registration is young, not necessarily that the brand is.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx

from signet.adapters import http
from signet.errors import AdapterError
from signet.ports.registry import Registration

_BOOTSTRAP = "https://rdap.org/domain/"
# Domain age is advisory: it never fails a document on its own, and a verdict
# that already has its answer should not wait ten seconds for a footnote. The
# bootstrap service is also the slowest thing on the verification path when a
# registry is unresponsive, which is exactly when the wait buys nothing.
_TIMEOUT_SECONDS = 3.0


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


class RdapRegistrationData:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or http.client(
            _TIMEOUT_SECONDS, follow_redirects=True, headers={"Accept": "application/json"}
        )

    def registration(self, domain: str) -> Registration:
        try:
            response = self._client.get(f"{_BOOTSTRAP}{domain}")
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AdapterError(f"RDAP lookup for {domain} failed: {exc}") from exc

        events = {
            event.get("eventAction"): event.get("eventDate")
            for event in body.get("events", [])
            if isinstance(event, dict)
        }
        statuses = {str(status).lower() for status in body.get("status", [])}
        return Registration(
            domain=domain,
            created=_parse_date(events.get("registration")),
            expires=_parse_date(events.get("expiration")),
            registrar=_registrar_name(body),
            locked=any("transfer prohibited" in status for status in statuses),
        )


def _registrar_name(body: dict[str, object]) -> str | None:
    entities = body.get("entities")
    if not isinstance(entities, list):
        return None
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        if "registrar" not in [str(role) for role in entity.get("roles", [])]:
            continue
        vcard = entity.get("vcardArray")
        if isinstance(vcard, list) and len(vcard) == 2 and isinstance(vcard[1], list):
            for field in vcard[1]:
                if isinstance(field, list) and len(field) == 4 and field[0] == "fn":
                    return str(field[3])
    return None
