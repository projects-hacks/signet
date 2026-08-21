"""The only module that reads the environment.

Everything else takes what it needs as an argument. That keeps configuration
testable, keeps secrets out of import side effects, and means a missing key
surfaces once at startup rather than deep inside a request.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

from signet.errors import ConfigError

FIXTURES_ENV: Final = "SIGNET_FIXTURES"

# Providers on separate infrastructure, so a poisoned cache in one does not
# silently become the answer. Agreement between them is the signal.
DEFAULT_RESOLVERS: Final = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
)


@dataclass(frozen=True, slots=True)
class Credentials:
    name: str
    values: tuple[str, ...]

    def require(self) -> tuple[str, ...]:
        """Return the values, or explain exactly which service is unconfigured."""
        if not all(self.values):
            raise ConfigError(
                f"{self.name} is not configured. Set it in .env, or run with "
                f"{FIXTURES_ENV}=1 to use recorded responses."
            )
        return self.values


@dataclass(frozen=True, slots=True)
class Settings:
    fixtures: bool
    resolvers: tuple[str, ...]
    xano: Credentials
    nutrient: Credentials
    foxit_services: Credentials
    foxit_esign: Credentials
    doctavian: Credentials
    namecom: Credentials
    serpapi: Credentials
    llm: Credentials


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def load_settings() -> Settings:
    """Read settings from the environment.

    Fixtures default to on so a fresh clone runs the suite and the CLI without
    any credentials at all.
    """
    return Settings(
        fixtures=_get(FIXTURES_ENV, "1") not in {"0", "false", "no"},
        resolvers=DEFAULT_RESOLVERS,
        xano=Credentials("Xano", (_get("XANO_BASE_URL"), _get("XANO_API_KEY"))),
        nutrient=Credentials("Nutrient", (_get("NUTRIENT_API_KEY"),)),
        foxit_services=Credentials(
            "Foxit PDF Services",
            (
                _get("FOXIT_CLOUD_API_HOST"),
                _get("FOXIT_CLOUD_API_CLIENT_ID"),
                _get("FOXIT_CLOUD_API_CLIENT_SECRET"),
            ),
        ),
        foxit_esign=Credentials("Foxit eSign", (_get("FOXIT_ESIGN_API_KEY"),)),
        doctavian=Credentials("Doctavian", (_get("DOCTAVIAN_API_KEY"),)),
        namecom=Credentials(
            "name.com",
            (
                _get("NAMECOM_USERNAME"),
                _get("NAMECOM_TOKEN"),
                _get("NAMECOM_BASE_URL", "https://api.name.com"),
            ),
        ),
        serpapi=Credentials("SerpApi", (_get("SERPAPI_API_KEY"),)),
        llm=Credentials(
            "LLM provider",
            (_get("LLM_BASE_URL"), _get("LLM_API_KEY"), _get("LLM_MODEL")),
        ),
    )
