"""The HTTP surface, which must not be able to reach a verdict the library cannot."""

from __future__ import annotations

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
        foxit_services=unset,
        foxit_esign=unset,
        doctavian=unset,
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


def test_every_signal_reaches_the_caller(client: TestClient) -> None:
    body = client.post("/api/verify", files={"file": ("scan.png", b"x")}).json()
    assert body["signals"]
    for signal in body["signals"]:
        assert set(signal) == {"name", "outcome", "detail", "source"}


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
