"""Xano, against the contract we define for it.

We own both sides here, so these tests are the specification the function stacks
have to satisfy, not a record of something discovered.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from signet.adapters.xano import API_KEY_HEADER, XanoRecordStore
from signet.errors import AdapterError

BASE = "https://x.xano.io/api:signet"


def store(handler: Any) -> XanoRecordStore:
    return XanoRecordStore(
        BASE, "secret", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_the_shared_secret_goes_out_on_every_call() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get(API_KEY_HEADER)
        return httpx.Response(404)

    store(handler).issuer("bluebottle.com")
    assert seen["key"] == "secret"


def test_a_known_issuer_comes_back_whole() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "domain": "bluebottle.com",
                "brand": "Blue Bottle Coffee",
                "public_key_hex": "ab" * 32,
                "enrolled": True,
                "frozen": False,
            },
        )

    issuer = store(handler).issuer("bluebottle.com")
    assert issuer is not None
    assert issuer.brand == "Blue Bottle Coffee"
    assert len(issuer.public_key) == 32
    assert issuer.enrolled and not issuer.frozen


def test_an_unknown_issuer_is_none_rather_than_an_error() -> None:
    """Most documents come from domains we have never enrolled. That is normal."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    assert store(handler).issuer("stranger.com") is None


def test_a_first_submission_is_accepted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/submission")
        return httpx.Response(200, json={"first_time": True})

    assert store(handler).record_submission("abc", "tester")


def test_a_repeat_submission_is_refused_by_the_database() -> None:
    """Uniqueness is the database's decision, not a read followed by a write."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"first_time": False})

    assert not store(handler).record_submission("abc", "tester")


def test_cache_round_trips() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"value": {"canonical_domain": "bluebottle.com"}})
        return httpx.Response(200, json={})

    subject = store(handler)
    subject.cache_put("brand", "Blue Bottle Coffee", {"canonical_domain": "bluebottle.com"})
    assert subject.cache_get("brand", "Blue Bottle Coffee") == {
        "canonical_domain": "bluebottle.com"
    }


def test_a_cache_miss_is_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    assert store(handler).cache_get("brand", "Unknown") is None


def test_audit_events_carry_the_run_id() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={})

    store(handler).append_audit("run-1", "decided", {"verdict": "certified"})
    assert "run-1" in seen["body"]
    assert "certified" in seen["body"]


def test_a_rejected_key_names_the_header_to_check() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    with pytest.raises(AdapterError, match=API_KEY_HEADER):
        store(handler).record_submission("abc", "tester")


def test_missing_configuration_fails_at_construction() -> None:
    with pytest.raises(ValueError, match="base URL and an API key"):
        XanoRecordStore("", "")


def test_a_missing_route_is_an_error_rather_than_a_missing_record() -> None:
    """An empty workspace answered 404 and looked exactly like a working one."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"code": "ERROR_CODE_NOT_FOUND", "message": "Unable to locate request."},
        )

    store = XanoRecordStore(
        "https://x.invalid/api:abc",
        "key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(AdapterError, match="no endpoint"):
        store.issuer("probe.invalid")


def test_a_genuine_record_miss_is_still_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "no such issuer"})

    store = XanoRecordStore(
        "https://x.invalid/api:abc",
        "key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert store.issuer("probe.invalid") is None
