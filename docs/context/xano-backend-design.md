# What the Xano backend has to do

Written before any XanoScript, deliberately. This half is derived from our own
code and from the scenarios the product has to survive, so it can be checked
without knowing anything about Xano. The syntax half waits on their
documentation and is not guessed here.

Status: requirements agreed, implementation not started. The `signet` API group
in the workspace is currently an empty stub, and all four endpoints the adapter
calls return 404.

## Why Xano at all

Two reasons, and only one of them is the sponsor track.

Verification needs shared state that a single laptop cannot hold. Duplicate
detection is worthless if each verifier keeps its own list. A brand to domain
binding that lives in one person's file store is not a registry. The moment
there is more than one verifier, the store has to be central.

The sponsor requirement is that Xano is the backend in a meaningful way:
business logic, APIs, workflows, authentication, integrations or data model.
Holding the trust registry and the duplicate ledger is meaningful by any
reading. Using it as a key value bucket would not be.

## The contract already exists

`src/signet/ports/store.py` defines `RecordStore`, and `tests/unit/test_xano.py`
is written as a specification rather than a record of something observed. The
function stacks have to satisfy those tests. That is the acceptance criterion.

Current port surface: `issuer`, `record_submission`, `cache_get`, `cache_put`,
`append_audit`. The CLI also calls `enrol`, which is not on the port and is not
on the Xano adapter. That gap is real and has to be closed either by widening
the port or by giving enrolment its own port.

## Data model

Seven tables. Field types are deliberately not stated here, because that needs
their schema documentation rather than a guess.

| Table | Holds | Uniqueness that matters |
|---|---|---|
| `issuer` | domain, brand, public key, enrolled, frozen, timestamps | unique on domain |
| `submission` | document fingerprint, who submitted, when first seen | unique on fingerprint |
| `document` | issuer domain, document id, canonical payload, mark, batch | unique on issuer plus document id |
| `batch` | issuer domain, day, merkle root, published state | unique on issuer plus day |
| `cache` | namespace, key, value, expiry | unique on namespace plus key |
| `audit` | run id, event, detail, when | append only, no uniqueness |
| `review` | run id, field, extracted value, signed value, confidence, box, state, who decided, when | one row per uncertain field |

`review` is the table that earns the Nutrient track. We already compute a per
field confidence and then throw it away. Persisting the uncertain ones is what
turns "needs a human" from a string into a workflow.

## Scenarios the backend has to survive

Written as scenarios rather than endpoints, because the endpoint list falls out
of these and not the other way round.

### Verification, the hot path

1. A verifier resolves an issuer by domain. Must distinguish three outcomes:
   enrolled, frozen, and absent. Today the adapter collapses frozen and absent
   into an `Issuer` with flags, which is fine, but the endpoint must return
   enough to tell them apart.
2. A verifier records a submission fingerprint and learns whether it is a
   repeat. This is a check and set, not a read then write. Two verifiers
   submitting the same document at the same instant must not both be told it is
   new. A unique index on the fingerprint plus handling the conflict is the
   correct shape; a read followed by an insert is a race and would let a
   duplicated invoice pass twice.
3. Every run appends to the audit trail. Audit must never be able to fail a
   verification. If the append fails the verdict still stands, because a
   verdict that depends on logging is a verdict that goes down when logging
   does.

### Availability, and what happens when Xano is unreachable

This needs an explicit decision rather than a default. Verification currently
works entirely offline apart from DNS. If the record store becomes mandatory,
a Xano outage takes verification down.

Proposed rule: the signature check never depends on the store, because the key
comes from DNS and the payload comes from the mark. Identity and duplicate do
depend on it, and when the store is unreachable they must return UNKNOWN with a
reason naming the outage, never PASS. Failing open on identity would let a
lookalike through during an outage, which is exactly when an attacker would
choose to try.

### Enrolment

4. Register a domain and brand, store the public key, and mark it not yet
   enrolled until domain control is proven.
5. Prove domain control, then flip to enrolled. Until then the issuer exists
   but must not satisfy the identity check.
6. Reject a second enrolment claiming a brand already bound to a different
   domain, or surface it for review. Two domains claiming one brand is either a
   mistake or the attack.

### Issuance

7. Append an issued document and assign it to today's open batch for its
   issuer. Must be idempotent on issuer plus document id, so a retried issue
   call cannot mint two documents with the same id and different payloads.
8. Close a day's batch, compute the Merkle root, and record it as published
   once the DNS write is confirmed. One DNS write per issuer per day regardless
   of volume, which is the whole point of batching.

### Revocation and lifecycle

9. A domain that expires, transfers or lapses freezes its issuer. The trigger
   is a name.com lifecycle webhook, so the backend needs an endpoint that
   accepts it and a way to authenticate that it is genuinely from name.com.
   Anyone who can call that endpoint unauthenticated can freeze a competitor.
10. A frozen issuer fails the identity check with a reason naming the freeze,
    rather than silently disappearing.

### Human review, the Nutrient path

11. When extraction returns a field below the confidence threshold, create a
    review row carrying the extracted value, the signed value, the confidence
    and the bounding box, so a reviewer sees exactly the disputed region.
12. List pending reviews, oldest first, with paging.
13. Adjudicate one: approve or reject, recording who and when. The decision has
    to be auditable, because the point of a human in the loop is that someone
    is accountable for the call.
14. A decided review updates the run's outcome. Deciding twice must not double
    apply.

### Caching and third party budget

15. Cache RDAP and search responses by namespace and key with an expiry. This
    is not an optimisation, it is budget protection: SerpApi has a hard monthly
    quota and re-asking the same question burns it.
16. An expired entry must read as absent rather than stale.

## Authentication

Three classes of caller, and they must not share one key.

| Caller | Needs | Risk if wrong |
|---|---|---|
| Verifier | read issuer, write submission, write audit | Low value, high volume |
| Issuer tooling | enrol, issue, close batch | Can mint documents |
| name.com webhook | freeze an issuer | Can disable a competitor |

A single shared key across all three means a verifier's key can mint documents.
How Xano expresses per endpoint auth is a documentation question, deliberately
left open here.

## Open questions, to be answered from documentation and not assumed

- How a unique index is declared, and what a conflicting insert returns, since
  the duplicate check depends on it.
- Whether scheduled tasks exist and at what granularity, since the nightly
  batch close needs one.
- How a static API key is verified inside a function stack, and where the
  expected value is stored.
- Whether there is a dry run or diff before a workspace push.
- Transaction semantics, if any, across a multi step function stack.
