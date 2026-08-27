"""The only module that reads the environment.

Everything else takes what it needs as an argument. That keeps configuration
testable, keeps secrets out of import side effects, and means a missing key
surfaces once at startup rather than deep inside a request.

Every name here appears in .env.example. If you add one, add it there too, or
the next person will not know it exists.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from signet.errors import ConfigError

FIXTURES_ENV: Final = "SIGNET_FIXTURES"

# Providers on separate infrastructure, so a poisoned cache in one does not
# silently become the answer. Agreement between them is the signal.
DEFAULT_RESOLVERS: Final = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
)

_PLACEHOLDER: Final = "replace-me"


@dataclass(frozen=True, slots=True)
class Credentials:
    name: str
    values: tuple[str, ...]

    @property
    def configured(self) -> bool:
        return all(value and value != _PLACEHOLDER for value in self.values)

    def require(self) -> tuple[str, ...]:
        """Return the values, or explain exactly which service is unconfigured."""
        if not self.configured:
            raise ConfigError(
                f"{self.name} is not configured. Set it in .env, or run with "
                f"{FIXTURES_ENV}=1 to use recorded responses."
            )
        return self.values


@dataclass(frozen=True, slots=True)
class Demo:
    """The domains the demo issues and verifies against.

    Both are ours. Never register a permutation of a real company's domain, not
    even to demonstrate one.
    """

    issuer_domain: str
    lookalike_domain: str
    brand: str

    @property
    def configured(self) -> bool:
        """A placeholder is not a domain, and nor is a bare label with no dot."""
        return all(
            value and value != _PLACEHOLDER and "." in value
            for value in (self.issuer_domain, self.lookalike_domain)
        )


@dataclass(frozen=True, slots=True)
class Settings:
    fixtures: bool
    resolvers: tuple[str, ...]
    demo: Demo
    xano: Credentials
    nutrient: Credentials
    foxit: Credentials
    doctavian: Credentials
    doctavian_templates: Mapping[str, Path]
    doctavian_signatures: Credentials
    namecom: Credentials
    serpapi: Credentials
    llm: Credentials

    def unconfigured(self) -> tuple[str, ...]:
        """Names of services still missing credentials, for a startup report."""
        return tuple(
            item.name
            for item in (
                self.xano,
                self.nutrient,
                self.foxit,
                self.doctavian,
                self.doctavian_signatures,
                self.namecom,
                self.serpapi,
                self.llm,
            )
            if not item.configured
        )


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _templates(raw: str) -> Mapping[str, Path]:
    """Parse class=path pairs, so adding a document class is configuration.

    Which template renders which class is deployment specific, and the file is
    the thing that has to exist rather than a reference to it.
    """
    parsed: dict[str, Path] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        document_class, path = entry.split("=", 1)
        parsed[document_class.strip()] = Path(path.strip())
    return parsed


def load_settings() -> Settings:
    """Read settings from the environment.

    Fixtures default to on so a fresh clone runs the suite and the CLI without
    any credentials at all.
    """
    return Settings(
        fixtures=_get(FIXTURES_ENV, "1") not in {"0", "false", "no"},
        resolvers=DEFAULT_RESOLVERS,
        demo=Demo(
            issuer_domain=_get("SIGNET_DEMO_DOMAIN"),
            lookalike_domain=_get("SIGNET_DEMO_LOOKALIKE"),
            brand=_get("SIGNET_DEMO_BRAND"),
        ),
        xano=Credentials("Xano", (_get("XANO_BASE_URL"), _get("XANO_API_KEY"))),
        nutrient=Credentials("Nutrient", (_get("NUTRIENT_API_KEY"),)),
        foxit=Credentials(
            "Foxit",
            (
                _get("FOXIT_API_HOST"),
                _get("FOXIT_CLIENT_ID"),
                _get("FOXIT_CLIENT_SECRET"),
            ),
        ),
        doctavian=Credentials(
            "Doctavian",
            (_get("DOCTAVIAN_API_KEY"), _get("DOCTAVIAN_BASE_URL")),
        ),
        doctavian_templates=_templates(_get("DOCTAVIAN_TEMPLATES")),
        doctavian_signatures=Credentials(
            "Doctavian Signatures",
            # Their portal scopes the key by API version. If it turns out to
            # scope by area too, set the second key; otherwise the one key
            # covers both and this falls back to it.
            (
                _get("DOCTAVIAN_SIGNATURES_KEY") or _get("DOCTAVIAN_API_KEY"),
                _get("DOCTAVIAN_TOKEN"),
            ),
        ),
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
