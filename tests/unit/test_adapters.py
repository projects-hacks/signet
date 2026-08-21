"""Adapter parsing, against recorded responses.

Vendor translation is where bugs hide: a quoted TXT chunk, a vcard buried three
levels down, a provider that answers differently from its neighbour. These run
against a mock transport so they stay offline.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from signet.adapters.dns_multi import DohResolver
from signet.adapters.rdap import RdapRegistrationData
from signet.errors import AdapterError

KEY_RECORD = "v=SIGNET1; k=ed25519; p=2Kk758/5PHlZFO13qZHXbx5mRIuiuX78PLtD/FOMlvQ="


def doh(records: list[str], authenticated: bool = True) -> dict[str, Any]:
    return {
        "AD": authenticated,
        "Answer": [{"type": 16, "data": f'"{record}"'} for record in records],
    }


def resolver_over(responses: list[dict[str, Any]]) -> DohResolver:
    calls = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(calls))

    return DohResolver(
        providers=("https://a.example/dns", "https://b.example/dns"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_agreeing_providers_return_the_record() -> None:
    lookup = resolver_over([doh([KEY_RECORD]), doh([KEY_RECORD])]).lookup_txt("_signet.a.com")
    assert lookup.records == (KEY_RECORD,)
    assert lookup.resolvers_agreed
    assert lookup.dnssec_validated


def test_disagreeing_providers_return_nothing() -> None:
    lookup = resolver_over([doh([KEY_RECORD]), doh(["something else"])]).lookup_txt("_signet.a.com")
    assert lookup.records == ()
    assert not lookup.resolvers_agreed


def test_dnssec_needs_every_provider_to_validate() -> None:
    lookup = resolver_over(
        [doh([KEY_RECORD], authenticated=True), doh([KEY_RECORD], authenticated=False)]
    ).lookup_txt("_signet.a.com")
    assert lookup.resolvers_agreed
    assert not lookup.dnssec_validated


def test_a_split_txt_record_is_rejoined() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"AD": True, "Answer": [{"type": 16, "data": '"abc" "def"'}]}
        )

    resolver = DohResolver(
        providers=("https://a.example/dns",),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert resolver.lookup_txt("a.com").records == ("abcdef",)


def test_non_txt_answers_are_ignored() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"AD": True, "Answer": [{"type": 5, "data": "cname.example."}]}
        )

    resolver = DohResolver(
        providers=("https://a.example/dns",),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert resolver.lookup_txt("a.com").records == ()


def test_a_failing_provider_raises_an_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502)

    resolver = DohResolver(
        providers=("https://a.example/dns",),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(AdapterError, match="DNS lookup"):
        resolver.lookup_txt("a.com")


def test_at_least_one_provider_is_required() -> None:
    with pytest.raises(ValueError, match="at least one"):
        DohResolver(providers=())


RDAP_BODY: dict[str, Any] = {
    "events": [
        {"eventAction": "registration", "eventDate": "1995-09-12T04:00:00Z"},
        {"eventAction": "expiration", "eventDate": "2027-09-11T04:00:00Z"},
    ],
    "status": ["client transfer prohibited", "client delete prohibited"],
    "entities": [
        {
            "roles": ["registrar"],
            "vcardArray": [
                "vcard",
                [["version", {}, "text", "4.0"], ["fn", {}, "text", "SafeNames"]],
            ],
        }
    ],
}


def rdap_over(body: dict[str, Any], status: int = 200) -> RdapRegistrationData:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return RdapRegistrationData(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_registration_dates_and_lock_are_parsed() -> None:
    registration = rdap_over(RDAP_BODY).registration("stripe.com")
    assert registration.created == date(1995, 9, 12)
    assert registration.expires == date(2027, 9, 11)
    assert registration.locked
    assert registration.registrar == "SafeNames"


def test_a_domain_with_no_events_has_no_dates() -> None:
    registration = rdap_over({"status": []}).registration("new.com")
    assert registration.created is None
    assert not registration.locked
    assert registration.registrar is None


def test_a_malformed_date_is_dropped_rather_than_raising() -> None:
    body = {"events": [{"eventAction": "registration", "eventDate": "not a date"}]}
    assert rdap_over(body).registration("a.com").created is None


def test_an_rdap_failure_raises_an_adapter_error() -> None:
    with pytest.raises(AdapterError, match="RDAP lookup"):
        rdap_over({}, status=404).registration("a.com")
