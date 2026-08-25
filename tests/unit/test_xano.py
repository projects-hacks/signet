"""Xano, against the contract we define for it.

We own both sides here, so these tests are the specification the function stacks
have to satisfy, not a record of something discovered.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from signet.adapters.xano import XanoRecordStore
from signet.errors import AdapterError

BASE = "https://x.xano.io/api:signet"


def store(handler: Any) -> XanoRecordStore:
    return XanoRecordStore(
        BASE, "secret", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_the_shared_secret_goes_out_as_a_bearer_token() -> None:
    """The only documented way a function stack can read a caller's credential."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("Authorization")
        return httpx.Response(200, json=None)

    store(handler).issuer("bluebottle.com")
    assert seen["key"] == "Bearer secret"


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
        return httpx.Response(200, json=None)

    assert store(handler).issuer("stranger.com") is None


def test_a_first_submission_is_accepted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/submission")
        return httpx.Response(200, json={"existing": None})

    assert store(handler).record_submission("abc", "tester")


def test_a_repeat_submission_is_refused_by_the_database() -> None:
    """Uniqueness is the database's decision, not a read followed by a write."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"existing": {"id": 7, "submitted_by": "someone"}})

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
        return httpx.Response(200, json=None)

    assert store(handler).cache_get("brand", "Unknown") is None


def test_audit_events_carry_the_run_id() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={})

    store(handler).append_audit("run-1", "decided", {"verdict": "certified"})
    assert "run-1" in seen["body"]
    assert "certified" in seen["body"]


def test_a_rejected_key_names_what_to_compare_it_against() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    with pytest.raises(AdapterError, match="signet_api_key"):
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


def test_any_404_is_a_missing_route_now_that_absence_is_a_200() -> None:
    """Absence carries null with a 200, so a 404 can only mean the route is gone."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"code": "ERROR_CODE_NOT_FOUND", "message": "Unable to locate request."},
        )

    with pytest.raises(AdapterError, match="no endpoint"):
        store(handler).issuer("probe.invalid")


def test_an_expired_entry_reads_as_absent() -> None:
    """A stale fraud signal is worse than none: the fact it records can change."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"value": {"registered": "1999-01-01"}, "expires_at": 1_000}
        )

    store = XanoRecordStore(
        "https://x.invalid/api:abc",
        "key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert store.cache_get("rdap", "stripe.com") is None


def test_an_unexpired_entry_is_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        far_future = 99_999_999_999_999
        return httpx.Response(200, json={"value": {"registered": "1995"}, "expires_at": far_future})

    store = XanoRecordStore(
        "https://x.invalid/api:abc",
        "key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert store.cache_get("rdap", "stripe.com") == {"registered": "1995"}


def test_writing_a_cache_entry_sends_an_expiry() -> None:
    """Without one the row lands with expires_at zero and never goes stale."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=None)

    store = XanoRecordStore(
        "https://x.invalid/api:abc",
        "key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    store.cache_put("rdap", "stripe.com", {"registered": "1995"})
    assert seen["expires_at"] > 0
