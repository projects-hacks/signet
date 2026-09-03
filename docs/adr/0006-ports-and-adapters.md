# 6. The domain never imports a vendor

Accepted, 2026-08-20.

## Context

Signet touches eight external services. Every one of them is a hackathon
sponsor's API, several were released this year, and at least two behave
differently from their published documentation. Verification has to keep working
when one of them is down, slow, or has changed under us.

The failure this guards against is not abstract. Extraction, generation, DNS
reads, DNS writes, live search, signature routing and the record store are all
somebody else's uptime. If the decision logic imports any of them, then testing
the decision logic requires the network, and the product's central claim, that
the same signals always produce the same verdict, becomes untestable.

## Decision

`core`, `ports`, `verify` and `issue` import from `signet.ports` only. A port is
a `Protocol` stated in domain terms. Adapters implement them and are the only
modules that know a vendor exists.

This is enforced mechanically rather than by review, with a ruff `banned-api`
rule on `signet.adapters`, waived only for `adapters/` itself, `wiring.py`,
`cli.py`, `api/`, `tests/` and `scripts/`.

Ports are segregated by capability, not by vendor. name.com provides both DNS
writing and registrar lookups, so it implements two ports, and a check that needs
availability does not thereby depend on DNS writing.

## Consequences

The whole pipeline runs offline against fakes, which is why the suite is fast and
why `SIGNET_FIXTURES=1` is the default.

The rule has already caught real mistakes. Composing a document and its mark was
first written in `issue/`, where it needed the QR adapter; the rule refused the
import, and the code moved to `adapters/page.py` where it belonged.

The cost is one indirection per capability and a composition root that has to
know everything. That root is `wiring.py`. The entry points the rule waives, `cli.py` and `api/`, wire their own narrow paths the same way; nothing else does.
