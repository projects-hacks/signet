"""The composition root.

Which adapter serves which port is a deployment question, and answering it in
both the command line and the HTTP surface meant two places to forget a check.
Every entry point builds its pipeline here.

An unconfigured vendor removes a check rather than breaking the run. Verification
degrades in depth, never in correctness, because a check that cannot run reports
UNKNOWN and certification already requires positive evidence.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from signet.adapters.dns_multi import DohResolver
from signet.adapters.nutrient import NutrientClient, NutrientExtractor
from signet.adapters.qr import ImageMarkReader
from signet.adapters.rdap import RdapRegistrationData
from signet.adapters.records import record_store
from signet.adapters.serpapi import SerpApiResolver
from signet.config import Settings
from signet.ports.documents import DocumentExtractor
from signet.ports.intelligence import EntityResolver
from signet.ports.store import RecordStore
from signet.verify.pipeline import VerificationPipeline
from signet.verify.registry import default_checks


def extractor_for(settings: Settings) -> DocumentExtractor | None:
    if not settings.nutrient.configured or settings.fixtures:
        return None
    return NutrientExtractor(NutrientClient(settings.nutrient.values[0]))


def resolver_for(settings: Settings, store: RecordStore) -> EntityResolver | None:
    if not settings.serpapi.configured or settings.fixtures:
        return None
    return SerpApiResolver(settings.serpapi.values[0], store)


def build_pipeline(settings: Settings, store_path: Path) -> VerificationPipeline:
    store = record_store(settings, store_path)
    return VerificationPipeline(
        checks=default_checks(
            resolver=DohResolver(),
            store=store,
            registrations=RdapRegistrationData(),
            today=date.today(),
            extractor=extractor_for(settings),
            entities=resolver_for(settings, store),
        ),
        store=store,
        mark_reader=ImageMarkReader(),
    )
