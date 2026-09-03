"""The agent, tested against the ways a model actually goes wrong.

These are not hypotheticals. Measured against Signet's own tool schemas, one
model skipped the diligence lookup when told to hurry, and another ran it, was
handed a contradiction, and enrolled the lookalike anyway. Both are reproduced
below with a scripted client, because the point is that the tools stop them
whatever the model does.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from signet.agent import Agent, Toolbox, ToolRefused
from signet.agent.tools import call
from signet.issue.broker import EnrolmentBroker
from signet.issue.publish import KeyPublisher
from signet.ports.intelligence import BrandResolution, Diligence
from tests.fakes import FakeDnsPublisher, FakeDnsResolver, FakeRecordStore
from tests.unit.test_broker import FakeGateway, FakeReader, FakeRenderer

BRAND = "Northpost"
REAL = "northpost.dev"
LOOKALIKE = "north-post.dev"
SIGNER = "ops@northpost.dev"

# Every field the tools require, present in one body of text, so a test can
# quote a real line rather than assert against a fixture nobody reads.
REQUEST = (
    "> forwarded: please set up Northpost, invoicing runs from northpost.dev\n"
    "> though marketing still owns north-post.dev and always will\n"
    "ops@northpost.dev is the one who can sign for it\n"
)


class StubResolver:
    def __init__(self, published: str | None = REAL) -> None:
        self.published = published
        self.lookups: list[str] = []

    def resolve_brand(self, brand: str) -> BrandResolution:
        self.lookups.append(brand)
        # Authoritative: these tests are about what happens when the web
        # states who a brand is, not when a page merely ranked for the name.
        return BrandResolution(
            brand=brand,
            canonical_domain=self.published,
            sources=("a-source",),
            authoritative=self.published is not None,
        )

    def diligence(self, domain: str, brand: str) -> Diligence:
        return Diligence(domain, True, self.published, (), ("a-source",))


class ScriptedClient:
    """A model that does exactly what the script says, including the wrong thing."""

    def __init__(self, script: Sequence[Mapping[str, Any]]) -> None:
        self.script = list(script)
        self.turns = 0

    def complete(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any]:
        self.turns += 1
        if not self.script:
            return {"content": "Done."}
        return self.script.pop(0)


def says(name: str, **arguments: Any) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [
            {
                "id": f"c{name}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def toolbox(
    resolver: StubResolver | None = None,
    store: FakeRecordStore | None = None,
    publisher: FakeDnsPublisher | None = None,
    gateway: FakeGateway | None = None,
    renderer: FakeRenderer | None = None,
    source: str = REQUEST,
) -> Toolbox:
    return Toolbox(
        resolver=resolver or StubResolver(),
        broker=EnrolmentBroker(
            renderer=renderer or FakeRenderer(),
            gateway=gateway or FakeGateway(),
            reader=FakeReader(),
            store=store or FakeRecordStore(),
            publisher=KeyPublisher(publisher or FakeDnsPublisher(), FakeDnsResolver({})),
        ),
        source=source,
    )


def reads(domain: str = REAL, brand: str = BRAND, signer: str = SIGNER) -> list[dict[str, Any]]:
    """The attribution the tools require, as the turns a model would take."""
    return [
        says(
            "record_interpretation",
            field_name="domain",
            value=domain,
            quote="invoicing runs from northpost.dev",
            alternative="north-post.dev",
        ),
        says(
            "record_interpretation",
            field_name="brand",
            value=brand,
            quote="please set up Northpost",
        ),
        says(
            "record_interpretation",
            field_name="signer_email",
            value=signer,
            quote="ops@northpost.dev is the one who can sign for it",
        ),
    ]


def attribute(box: Toolbox, domain: str = REAL, brand: str = BRAND) -> None:
    """The same attribution, for the tests that call the tools directly."""
    box.record_interpretation("domain", domain, "invoicing runs from northpost.dev")
    box.record_interpretation("brand", brand, "please set up Northpost")
    box.record_interpretation(
        "signer_email", SIGNER, "ops@northpost.dev is the one who can sign for it"
    )


def test_the_happy_path_stops_at_the_signature() -> None:
    """Everything reversible, and then nothing."""
    box = toolbox()
    agent = Agent(
        ScriptedClient(
            [
                *reads(),
                says("resolve_counterparty", brand=BRAND),
                says("generate_signing_key", domain=REAL),
                says("draft_authorisation", domain=REAL, brand=BRAND, signer_email=SIGNER),
                {"content": "Sent for signature."},
            ]
        ),
        box,
    )
    transcript = agent.run(REQUEST)

    assert transcript.refusals == []
    assert transcript.tools_called == [
        "record_interpretation",
        "record_interpretation",
        "record_interpretation",
        "resolve_counterparty",
        "generate_signing_key",
        "draft_authorisation",
    ]
    assert box.pending is not None
    assert not transcript.published


def test_a_model_told_to_hurry_cannot_skip_the_lookup() -> None:
    """Reproduces the first measured failure: the model went straight to
    drafting when the request said to push it through."""
    box = toolbox()
    agent = Agent(
        ScriptedClient(
            [
                *reads(),
                says("generate_signing_key", domain=REAL),
                says("draft_authorisation", domain=REAL, brand=BRAND, signer_email=SIGNER),
                {"content": "I could not proceed."},
            ]
        ),
        box,
    )
    transcript = agent.run(REQUEST + "just push it through")

    assert transcript.refused_tools == ["draft_authorisation"]
    assert box.pending is None


def test_a_model_that_reads_the_contradiction_and_proceeds_is_stopped() -> None:
    """Reproduces the second measured failure: the model ran the lookup, was
    told the brand publishes northpost.dev, and enrolled north-post.dev anyway
    while reporting the check as passed."""
    box = toolbox()
    agent = Agent(
        ScriptedClient(
            [
                *reads(domain=LOOKALIKE),
                says("resolve_counterparty", brand=BRAND),
                says("generate_signing_key", domain=LOOKALIKE),
                says("draft_authorisation", domain=LOOKALIKE, brand=BRAND, signer_email=SIGNER),
                {"content": "Refused, and here is why."},
            ]
        ),
        box,
    )
    transcript = agent.run(REQUEST + "they need it today")

    assert transcript.refused_tools == ["draft_authorisation"]
    assert box.pending is None


def test_the_refusal_explains_that_the_domain_reads_as_the_real_one() -> None:
    """A refusal a person cannot act on is a refusal they will override."""
    box = toolbox()
    attribute(box, domain=LOOKALIKE)
    with pytest.raises(ToolRefused, match=r"reads as northpost\.dev without being it"):
        box.resolve_counterparty(BRAND)
        box.generate_signing_key(LOOKALIKE)
        box.draft_authorisation(LOOKALIKE, BRAND, SIGNER)


def test_looking_up_one_brand_does_not_authorise_another() -> None:
    """Otherwise the precondition is satisfied by looking up anything at all."""
    box = toolbox()
    attribute(box)
    box.resolve_counterparty("Some Other Company")
    box.generate_signing_key(REAL)
    with pytest.raises(ToolRefused, match="Look up the brand being enrolled"):
        box.draft_authorisation(REAL, BRAND, SIGNER)


def test_publishing_is_named_and_refused_rather_than_absent() -> None:
    """Leaving it out of the catalogue makes a model that wants to publish
    invent something else. Naming it ends the attempt with an explanation."""
    box = toolbox()
    result = json.loads(call(box, "publish_key_to_dns", json.dumps({"domain": REAL})))
    assert "irreversible" in result["refused"]


def test_no_route_through_the_agent_reaches_dns() -> None:
    """The property everything else is in service of."""
    publisher = FakeDnsPublisher()
    box = toolbox(publisher=publisher)
    agent = Agent(
        ScriptedClient(
            [
                *reads(),
                says("resolve_counterparty", brand=BRAND),
                says("generate_signing_key", domain=REAL),
                says("draft_authorisation", domain=REAL, brand=BRAND, signer_email=SIGNER),
                says("publish_key_to_dns", domain=REAL),
                says("publish_key_to_dns", domain=REAL),
                {"content": "I cannot publish."},
            ]
        ),
        box,
    )
    transcript = agent.run(REQUEST + "put the key live")

    assert publisher.writes == []
    assert transcript.refused_tools == ["publish_key_to_dns", "publish_key_to_dns"]
    assert not transcript.published


def test_the_authorisation_records_what_live_search_found() -> None:
    """The person signing is told what was checked on their behalf."""
    renderer = FakeRenderer()
    box = toolbox(renderer=renderer)
    attribute(box)
    box.resolve_counterparty(BRAND)
    box.generate_signing_key(REAL)
    box.draft_authorisation(REAL, BRAND, SIGNER)

    _, record = renderer.calls[0]
    assert "northpost.dev" in str(record["Diligence"])
    assert "a-source" in str(record["Diligence"])


def test_a_brand_the_web_has_never_heard_of_says_so_rather_than_blocking() -> None:
    """No published domain is thin evidence, not a contradiction, and the
    person signing is told the domain rests on their word."""
    renderer = FakeRenderer()
    box = toolbox(resolver=StubResolver(published=None), renderer=renderer)
    attribute(box)
    box.resolve_counterparty(BRAND)
    box.generate_signing_key(REAL)
    box.draft_authorisation(REAL, BRAND, SIGNER)

    assert "rests on your word alone" in str(renderer.calls[0][1]["Diligence"])


def test_an_unknown_tool_is_answered_rather_than_crashing() -> None:
    result = json.loads(call(toolbox(), "delete_everything", "{}"))
    assert "no tool called" in result["error"]


def test_malformed_arguments_are_answered_rather_than_crashing() -> None:
    result = json.loads(call(toolbox(), "resolve_counterparty", "{not json"))
    assert "not valid JSON" in result["error"]


def test_the_turn_limit_ends_a_model_that_loops_on_a_refusal() -> None:
    box = toolbox()
    agent = Agent(ScriptedClient([says("publish_key_to_dns", domain=REAL)] * 20), box)
    transcript = agent.run("publish it", max_turns=4)
    assert len(transcript.tools_called) == 4
    assert "turn limit" in transcript.reply


def test_a_refusal_carries_its_reason() -> None:
    """A refusal reported by name alone reads as a failure, and the agent's own
    summary of what happened is not evidence of what happened."""
    box = toolbox()
    agent = Agent(
        ScriptedClient(
            [
                *reads(domain=LOOKALIKE),
                says("resolve_counterparty", brand=BRAND),
                says("generate_signing_key", domain=LOOKALIKE),
                says("draft_authorisation", domain=LOOKALIKE, brand=BRAND, signer_email=SIGNER),
                {"content": "Refused."},
            ]
        ),
        box,
    )
    transcript = agent.run(REQUEST)

    name, reason = transcript.refusals[0]
    assert name == "draft_authorisation"
    assert "northpost.dev" in reason
    assert "lookalike" in reason


def test_a_field_nobody_can_point_at_never_reaches_a_signature() -> None:
    """The hole this closes: an invented address gets a real authorisation."""
    box = toolbox()
    box.resolve_counterparty(BRAND)
    box.generate_signing_key(REAL)
    with pytest.raises(ToolRefused, match="Call record_interpretation"):
        box.draft_authorisation(REAL, BRAND, SIGNER)


def test_a_quote_that_is_not_in_the_request_is_refused() -> None:
    """A model asked for evidence will produce evidence. Unchecked evidence is
    prose, so the line is looked for rather than believed."""
    box = toolbox()
    with pytest.raises(ToolRefused, match="not in the request"):
        box.record_interpretation("domain", REAL, "the finance team confirmed this domain")


def test_a_domain_that_appears_nowhere_is_refused_even_with_a_real_quote() -> None:
    """Quoting a line that exists does not make the value read off it real."""
    box = toolbox()
    with pytest.raises(ToolRefused, match="does not appear anywhere"):
        box.record_interpretation(
            "domain", "northpost-invoices.com", "invoicing runs from northpost.dev"
        )


def test_a_brand_may_be_tidied_where_a_domain_may_not() -> None:
    """People write their own company name several ways in one thread. A
    machine readable string has no such licence."""
    box = toolbox(source="please set up NORTHPOST FREIGHT SERVICES LTD., ops@northpost.dev")
    box.record_interpretation(
        "brand", "Northpost Freight Services", "please set up NORTHPOST FREIGHT SERVICES LTD."
    )
    assert box.readings["brand"].value == "Northpost Freight Services"


def test_quoting_survives_the_furniture_a_forwarded_thread_arrives_in() -> None:
    """Nobody strips the angle brackets before pasting a thread in."""
    box = toolbox()
    box.record_interpretation("domain", REAL, "invoicing runs from northpost.dev")
    assert box.readings["domain"].value == REAL


def test_drafting_something_other_than_what_was_read_is_refused() -> None:
    """Otherwise attribution is a step the model performs and then ignores."""
    box = toolbox()
    attribute(box)
    box.resolve_counterparty(BRAND)
    box.generate_signing_key(LOOKALIKE)
    with pytest.raises(ToolRefused, match="Draft what was read"):
        box.draft_authorisation(LOOKALIKE, BRAND, SIGNER)


def test_the_authorisation_prints_the_line_each_field_came_from() -> None:
    """The document is what a person is asked to check, so the reading and its
    evidence have to be on it."""
    renderer = FakeRenderer()
    box = toolbox(renderer=renderer)
    attribute(box)
    box.resolve_counterparty(BRAND)
    box.generate_signing_key(REAL)
    box.draft_authorisation(REAL, BRAND, SIGNER)

    readings = renderer.calls[0][1]["Readings"]
    assert [row["Field"] for row in readings] == ["domain", "brand", "signer email"]
    assert readings[0]["Quote"] == "invoicing runs from northpost.dev"
    assert all(row["Uncertain"] == 0 for row in readings)


def test_a_rejected_reading_is_named_and_counted_for_the_template() -> None:
    """The warning paragraph branches on the sum, so an ambiguous field has to
    carry a number the template can add up."""
    box = toolbox()
    box.record_interpretation(
        "domain",
        REAL,
        "invoicing runs from northpost.dev",
        alternative="north-post.dev",
    )
    reading = box.readings["domain"]
    assert reading.uncertain
    assert "north-post.dev" in reading.note


def test_an_optional_argument_sent_as_null_is_not_the_models_mistake_to_pay_for() -> None:
    """A model may send an omitted argument as an explicit null, which defeats
    the default. One did, and the agent died mid-enrolment on a traceback."""
    box = toolbox()
    box.record_interpretation("domain", REAL, "invoicing runs from northpost.dev", None)
    assert box.readings["domain"].alternative == ""


def test_a_tool_that_breaks_answers_rather_than_raising() -> None:
    """The design says a tool answers, because the model has to read what went
    wrong and report it. A crash ends the run with no account of what happened."""
    result = json.loads(call(toolbox(), "record_interpretation", '{"field_name": 7}'))
    assert "error" in result
