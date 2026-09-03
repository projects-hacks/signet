"""The test suite may not touch the network, and this is what stops it.

The claim that `make test` runs offline was previously prose. A lint rule bans
the domain from importing an adapter, but the tests are waived from that rule by
design, so nothing prevented a test from opening a socket and quietly making the
suite depend on somebody else's uptime.

Blocking the socket itself is the enforcement. A test that reaches for the
network fails with a message naming the rule rather than hanging until a timeout
somewhere in a vendor client.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Any

import pytest


class NetworkUsedInTests(RuntimeError):
    """A test tried to open a socket."""


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise NetworkUsedInTests(
            "The test suite runs offline. Something reached for the network, "
            "which means a fake is missing or an adapter is being exercised "
            "for real. Use the fakes in tests/fakes."
        )

    # Local sockets stay open: pytest plugins and coverage use them, and a
    # loopback connection is not a dependency on anyone else's uptime.
    original = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) and address else ""
        if host in {"127.0.0.1", "::1", "localhost"}:
            return original(self, address)
        return refuse()

    monkeypatch.setattr(socket.socket, "connect", guarded)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield
