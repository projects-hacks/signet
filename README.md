# Signet

Proof of origin for documents, anchored to the issuer's own domain in DNS.

A convincing fake receipt now takes thirty seconds and costs nothing. Detection is
losing: tools falsely flag around one in eight authentic documents, and the
generator improves every month while the detector does not.

Signet takes the other route. A document carries a signature over its
payment-critical fields, and the verifying key lives in the issuer's own DNS. Any
recipient can check it with `dig` and `openssl`, with no account and no trust in
us. The verdict changes category: not "this looks suspicious", but "this was never
issued".

## How verification works

Three layers, each degrading independently.

| Layer | Question | Basis |
| --- | --- | --- |
| Issuance | Did this domain emit this document? | Ed25519 signature over the canonical payload, checked against the key in DNS |
| Identity | Is that domain really the brand on the paper? | Brand to canonical domain, resolved once at issuer enrolment |
| Corroboration | Anything wrong when there is no signature? | Duplicate submission, domain age, lookalike scan, counterparty diligence |

The verdict engine is a pure function. The same signals always produce the same
verdict: no model, no clock, no network. The output of this product is evidence,
and evidence that cannot be replayed is not evidence.

See `docs/verification-model.md` for the decision table and `docs/limits.md` for
what Signet does not do.

## Quick start

```bash
git clone https://github.com/rajeev-chaurasia/signet
cd signet
cp .env.example .env      # fixtures are on by default, so no keys are needed yet
make setup
make test
```

`make test` runs entirely offline against in-memory fakes. If it ever needs the
network, a vendor has leaked into the domain.

## Verifying a document by hand

The point of anchoring to DNS is that you do not need this repository to check a
Signet document. `docs/verify-by-hand.md` walks through it with `dig` and
`openssl` alone.

```bash
dig +short TXT _signet.<issuer-domain>
```

## Commands

| Command | What it does |
| --- | --- |
| `make setup` | Install dependencies and git hooks |
| `make check` | Lint, strict type check, secret scan, prose hygiene |
| `make test` | Test suite with branch coverage, fully offline |
| `make gate` | Week one gate scripts against live APIs |
| `make demo` | Seed the demo issuer and documents |
| `make verify FILE=path` | Run one document through the pipeline |

## Layout

```
src/signet/core/       pure domain: payload, signing, merkle, mark, verdict
src/signet/ports/      one Protocol per external capability
src/signet/adapters/   one module per vendor, behind those ports
src/signet/verify/     pipeline and checks
src/signet/issue/      enrolment, keys, batching, publication
tests/                 unit, golden verdict suite, offline replay, fakes
```

`core` and `verify` import from `ports` only. A lint rule fails the build if the
domain ever reaches for a vendor.

## Licence

Apache-2.0.
