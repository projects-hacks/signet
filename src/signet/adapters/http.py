"""One HTTP client, so every adapter inherits the same failure policy.

Retries are deliberately limited to connection failures. A refused connection
carried no request, so repeating it cannot repeat an effect, and that is the
transient we actually see: a verification died mid demo on a connection refused
that succeeded on the next attempt a second later.

A response is never retried, however tempting a 502 looks. Recording a
submission is not idempotent, and a retry that lands after a write nobody saw
the answer to would tell the second verifier a duplicate document was new. The
whole point of that ledger is that it does not.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

# Three attempts covers a transport blip without turning a genuinely down
# service into a wait long enough that a demo looks broken.
CONNECT_RETRIES = 2


def client(
    timeout: float,
    *,
    headers: Mapping[str, str] | None = None,
    follow_redirects: bool = False,
) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers=dict(headers or {}),
        follow_redirects=follow_redirects,
        transport=httpx.HTTPTransport(retries=CONNECT_RETRIES),
    )
