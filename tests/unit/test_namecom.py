"""name.com, against the shapes its OpenAPI spec declares.

The behaviour worth pinning is idempotent publishing: a daily root goes out
under the same host every day, and creating instead of updating would leave a
zone full of stale roots that all still verify.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from signet.adapters.namecom import (
    MIN_TTL_SECONDS,
    NameComClient,
    NameComDns,
    NameComRegistrar,
)
from signet.errors import AdapterError

KEY_VALUE = "v=SIGNET1; k=ed25519; p=abc"


def client(handler: Any) -> NameComClient:
    return NameComClient(
        username="tester",
        token="token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
    )


def records_page(records: list[dict[str, Any]], next_page: int | None = None) -> dict[str, Any]:
    return {"records": records, "nextPage": next_page, "totalCount": len(records)}


def test_credentials_go_out_as_basic_auth() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=records_page([]))

    list(NameComDns(client(handler)).records("example.com"))
    assert seen["auth"] == "Basic dGVzdGVyOnRva2Vu"


def test_publishing_a_new_record_creates_it() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=records_page([]))
        return httpx.Response(200, json={"id": 1})

    NameComDns(client(handler)).publish_txt("example.com", "_signet", KEY_VALUE, 300)

    assert ("POST", "/core/v1/domains/example.com/records") in calls


def test_republishing_updates_rather_than_duplicating() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(
                200,
                json=records_page(
                    [{"id": 42, "type": "TXT", "host": "_signet", "answer": "v=SIGNET1; old"}]
                ),
            )
        return httpx.Response(200, json={"id": 42})

    NameComDns(client(handler)).publish_txt("example.com", "_signet", KEY_VALUE, 300)

    assert ("PUT", "/core/v1/domains/example.com/records/42") in calls
    assert not any(method == "POST" for method, _ in calls)


def test_a_ttl_below_the_floor_raises_rather_than_being_clamped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not have been called")

    with pytest.raises(AdapterError, match=f"minimum TTL of {MIN_TTL_SECONDS}"):
        NameComDns(client(handler)).publish_txt("example.com", "_signet", KEY_VALUE, 60)


def test_record_listing_follows_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", 1))
        if page == 1:
            return httpx.Response(200, json=records_page([{"id": 1, "type": "TXT"}], next_page=2))
        return httpx.Response(200, json=records_page([{"id": 2, "type": "TXT"}]))

    assert [r["id"] for r in NameComDns(client(handler)).records("example.com")] == [1, 2]


def test_availability_maps_domains_to_purchasability() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"domainName": "bluebottle.com", "purchasable": False},
                    {"domainName": "bluebott1e.com", "purchasable": True},
                ]
            },
        )

    result = NameComRegistrar(client(handler)).available(("bluebottle.com", "bluebott1e.com"))
    assert result == {"bluebottle.com": False, "bluebott1e.com": True}


def test_an_empty_availability_request_skips_the_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not have been called")

    assert NameComRegistrar(client(handler)).available(()) == {}


def test_search_returns_candidate_names() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"bluebottle" in request.read()
        return httpx.Response(200, json={"results": [{"domainName": "bluebottle.net"}]})

    assert NameComRegistrar(client(handler)).search("bluebottle") == ["bluebottle.net"]


def test_bad_credentials_explain_the_two_usual_causes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Permission Denied"})

    with pytest.raises(AdapterError, match="two-step verification"):
        NameComRegistrar(client(handler)).available(("a.com",))


def test_a_rate_limit_surfaces_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "60"}, json={})

    with pytest.raises(AdapterError, match="Retry-After: 60"):
        NameComRegistrar(client(handler)).available(("a.com",))


def test_missing_credentials_fail_at_construction() -> None:
    with pytest.raises(ValueError, match="username and an API token"):
        NameComClient(username="", token="")


def test_requests_are_paced_to_the_documented_ceiling() -> None:
    slept: list[float] = []
    now = [0.0]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=records_page([]))

    paced = NameComClient(
        username="u",
        token="t",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=slept.append,
        monotonic=lambda: now[0],
    )
    dns = NameComDns(paced)
    list(dns.records("a.com"))
    list(dns.records("a.com"))

    assert any(delay > 0 for delay in slept)
