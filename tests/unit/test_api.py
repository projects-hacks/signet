"""The HTTP surface, which must not be able to reach a verdict the library cannot."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from signet.api.app import MAX_UPLOAD_BYTES, create_app
from signet.config import Credentials, Demo, Settings


def settings() -> Settings:
    unset = Credentials("unset", ("",))
    return Settings(
        fixtures=True,
        resolvers=(),
        demo=Demo(issuer_domain="", lookalike_domain="", brand=""),
        xano=unset,
        nutrient=unset,
        foxit=unset,
        doctavian=unset,
        doctavian_templates={},
        allowed_origins=(),
        send_envelopes=False,
        foxit_mcp_python=None,
        signature_gateway="foxit",
        sender_email="",
        doctavian_signatures=unset,
        namecom=unset,
        serpapi=unset,
        llm=unset,
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(settings(), store_path=tmp_path / "store.json"))


def test_health_reports_whether_extraction_is_live(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["extraction"] is False


def test_an_unmarked_document_is_unsigned_rather_than_refused(client: TestClient) -> None:
    """Nothing to prove is not the same as proof of a problem."""
    response = client.post("/api/verify", files={"file": ("scan.png", b"not a real image")})
    assert response.status_code == 200
    assert response.json()["verdict"] == "unsigned"


def test_every_signal_reaches_the_caller_with_its_working(client: TestClient) -> None:
    """A conclusion without the material behind it is an assertion, not evidence."""
    body = client.post("/api/verify", files={"file": ("scan.png", b"x")}).json()
    assert body["signals"]
    for signal in body["signals"]:
        assert set(signal) == {"name", "outcome", "detail", "source", "evidence"}
        assert isinstance(signal["evidence"], dict)


def test_a_run_is_identified_so_a_verdict_can_be_traced(client: TestClient) -> None:
    body = client.post("/api/verify", files={"file": ("scan.png", b"x")}).json()
    assert body["runId"]


def test_a_request_with_no_file_is_refused(client: TestClient) -> None:
    assert client.post("/api/verify", data={"brand": "Northpost"}).status_code == 400


def test_an_empty_file_is_refused(client: TestClient) -> None:
    response = client.post("/api/verify", files={"file": ("empty.png", b"")})
    assert response.status_code == 400


def test_an_oversized_upload_is_refused_rather_than_read(client: TestClient) -> None:
    """A scan nobody photographed is how a demo machine falls over on stage."""
    payload = b"\x00" * (MAX_UPLOAD_BYTES + 1)
    assert client.post("/api/verify", files={"file": ("huge.png", payload)}).status_code == 413


def test_a_blank_brand_is_treated_as_no_brand(client: TestClient) -> None:
    response = client.post("/api/verify", files={"file": ("scan.png", b"x")}, data={"brand": "   "})
    assert response.status_code == 200


def test_no_allowlist_means_no_cross_origin_access(client: TestClient) -> None:
    """One process serving both the page and the API needs no exception, and an
    exception nobody needs is an exception somebody can use."""
    response = client.post(
        "/api/verify",
        files={"file": ("scan.png", b"bytes")},
        headers={"Origin": "https://elsewhere.example"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_a_named_origin_is_allowed_and_others_are_not(tmp_path: Path) -> None:
    """Static hosting runs no server side code, so the page there is a different
    origin from the verifier and has to be named."""
    allowed = "https://signet-dev.example"
    configured = replace(settings(), allowed_origins=(allowed,))
    app = TestClient(create_app(configured, store_path=tmp_path / "store.json"))

    permitted = app.post(
        "/api/verify", files={"file": ("scan.png", b"bytes")}, headers={"Origin": allowed}
    )
    assert permitted.headers.get("access-control-allow-origin") == allowed

    refused = app.post(
        "/api/verify",
        files={"file": ("scan.png", b"bytes")},
        headers={"Origin": "https://elsewhere.example"},
    )
    assert "access-control-allow-origin" not in refused.headers


def test_the_stream_names_every_check_before_asking_any(client: TestClient) -> None:
    """A reader waiting on a verdict is owed the shape of the answer, and the
    shape is knowable at the start."""
    with client.stream(
        "POST", "/api/examine", files={"file": ("scan.png", b"not a real image")}
    ) as response:
        first = json.loads(next(response.iter_lines()))
    assert first["event"] == "started"
    assert first["checks"]
    assert "signature" in first["checks"]


def test_every_signal_arrives_before_the_verdict(client: TestClient) -> None:
    with client.stream(
        "POST", "/api/examine", files={"file": ("scan.png", b"not a real image")}
    ) as response:
        events = [json.loads(line) for line in response.iter_lines() if line]

    kinds = [event["event"] for event in events]
    assert kinds[0] == "started"
    assert kinds[-1] == "decided"
    assert set(kinds[1:-1]) == {"signal"}

    named = [event["name"] for event in events if event["event"] == "signal"]
    assert named == list(events[0]["checks"])
    assert events[-1]["verdict"] in {"certified", "flagged", "unsigned"}


def test_the_streamed_verdict_matches_the_single_shot_one(client: TestClient) -> None:
    """Two endpoints, one pipeline. If they can disagree, one of them is lying.

    Distinct content on purpose. The same bytes twice is genuinely a different
    question the second time, which the next test is about.
    """
    once = client.post("/api/verify", files={"file": ("a.png", b"one document")}).json()
    with client.stream("POST", "/api/examine", files={"file": ("b.png", b"another")}) as response:
        streamed = [json.loads(line) for line in response.iter_lines() if line][-1]

    assert streamed["verdict"] == once["verdict"]
    assert [signal["name"] for signal in streamed["signals"]] == [
        signal["name"] for signal in once["signals"]
    ]


def test_the_submissions_ledger_is_shared_across_both_endpoints(client: TestClient) -> None:
    """Sending the same document again is a different question, and asking it
    through the other endpoint must not reset the answer."""
    client.post("/api/verify", files={"file": ("scan.png", b"the same bytes")})
    with client.stream(
        "POST", "/api/examine", files={"file": ("scan.png", b"the same bytes")}
    ) as response:
        events = [json.loads(line) for line in response.iter_lines() if line]

    duplicate = next(
        event for event in events if event.get("event") == "signal" and event["name"] == "duplicate"
    )
    assert duplicate["outcome"] == "fail"
    assert events[-1]["verdict"] == "flagged"


def test_a_stream_refuses_an_empty_file_before_it_starts(client: TestClient) -> None:
    """A failure known before any work is a status code, not a final line."""
    response = client.post("/api/examine", files={"file": ("scan.png", b"")})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")


def test_an_unknown_run_cannot_be_adjudicated(client: TestClient) -> None:
    """The run is loaded from the store, not from the request, so a caller
    cannot post their own signals and have them re-decided."""
    response = client.post(
        "/api/adjudicate",
        json={"runId": "never-existed", "field": "iban", "reading": "GB29"},
    )
    assert response.status_code == 404


def test_adjudicating_needs_a_field_and_a_reading(client: TestClient) -> None:
    response = client.post("/api/adjudicate", json={"runId": "abc"})
    assert response.status_code == 400


def test_a_reading_for_a_field_the_run_never_compared_is_refused(client: TestClient) -> None:
    """A conflict rather than a not found: the run exists and the ask does not
    apply to it."""
    with client.stream(
        "POST", "/api/examine", files={"file": ("scan.png", b"not a real image")}
    ) as response:
        decided = [json.loads(line) for line in response.iter_lines() if line][-1]

    refused = client.post(
        "/api/adjudicate",
        json={"runId": decided["runId"], "field": "iban", "reading": "GB29"},
    )
    assert refused.status_code == 409


def test_a_check_that_could_not_run_carries_no_evidence(client: TestClient) -> None:
    """The frontend separates a check that found something advisory from one
    that could not reach anything, and it does that on the presence of
    evidence rather than on a fourth outcome. This pins that discriminator."""
    with client.stream(
        "POST", "/api/examine", files={"file": ("scan.png", b"not a real image")}
    ) as response:
        events = [json.loads(line) for line in response.iter_lines() if line]

    unknown = [
        event
        for event in events
        if event.get("event") == "signal" and event["outcome"] == "unknown"
    ]
    assert unknown, "this document should leave several checks unable to answer"
    for signal in unknown:
        if signal["detail"].startswith("Could not complete"):
            assert signal["evidence"] == {}
            assert signal["source"], "the reason it failed belongs in the source"
