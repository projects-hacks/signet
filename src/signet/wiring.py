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
from signet.adapters.foxit import FoxitClient, FoxitSignatures
from signet.adapters.foxit_mcp import FoxitMcp, McpTextReader
from signet.adapters.llm import ChatClient
from signet.adapters.namecom import NameComClient, NameComDns
from signet.adapters.nutrient import NutrientClient, NutrientExtractor
from signet.adapters.qr import ImageMarkReader
from signet.adapters.rdap import RdapRegistrationData
from signet.adapters.records import record_store
from signet.adapters.renderers import document_renderer
from signet.adapters.serpapi import SerpApiResolver
from signet.agent import Agent, Toolbox
from signet.config import Settings
from signet.errors import ConfigError
from signet.issue.broker import EnrolmentBroker
from signet.issue.publish import KeyPublisher
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


def build_broker(settings: Settings, store_path: Path) -> EnrolmentBroker:
    """The only thing in the system that publishes a key."""
    host, client_id, client_secret = settings.foxit.require()
    namecom_user, namecom_token, namecom_url = settings.namecom.require()
    foxit = FoxitClient(client_id, client_secret, host)
    # The reversible document work goes through Foxit's own MCP server, which is
    # what their challenge asks for. Signing does not: it is called directly,
    # from here, because their catalogue deliberately leaves it out and we agree
    # with the shape of that decision.
    return EnrolmentBroker(
        renderer=document_renderer(settings),
        gateway=FoxitSignatures(foxit, send_now=settings.send_envelopes),
        reader=McpTextReader(
            FoxitMcp(host, client_id, client_secret, interpreter=settings.foxit_mcp_python)
        ),
        store=record_store(settings, store_path),
        publisher=KeyPublisher(
            NameComDns(NameComClient(namecom_user, namecom_token, namecom_url)),
            DohResolver(),
        ),
    )


def build_agent(settings: Settings, store_path: Path) -> Agent:
    """The enrolment agent, and everything it is allowed to touch.

    Assembled here rather than by the agent so the tool surface is a property of
    the deployment. The broker takes the publisher; the agent never sees it.
    """
    base_url, api_key, model = settings.llm.require()

    store = record_store(settings, store_path)
    broker = build_broker(settings, store_path)
    resolver = resolver_for(settings, store)
    if resolver is None:
        raise ConfigError(
            "Enrolment needs live search, because an authorisation nobody checked is "
            "a form. Configure SerpApi, or turn fixtures off."
        )
    return Agent(ChatClient(base_url, api_key, model), Toolbox(resolver=resolver, broker=broker))


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
