# 4. Unknown, never pass

Accepted, 2026-08-21.

## Context

Checks depend on things that go down: DNS, the record store, extraction, live
search. Something has to happen when a check cannot reach its source, and both
obvious defaults are wrong. Passing on outage certifies exactly when an
attacker would choose to strike, because an outage is the moment to send the
lookalike. Failing on outage accuses honest documents by the thousand, which
is the false flag rate this product exists to undo: a new company is not a
fraud, and a photographed page is not a forgery.

## Decision

A check that cannot reach its evidence reports UNKNOWN, a third state distinct
from both pass and fail. Certification requires positive evidence from the
signature and identity checks; any failure flags; a run reduced to unknowns is
UNSIGNED, which says "no proof available" and accuses nobody.

Unknown splits further by the shape of the signal. One that carries findings
reached its source and is putting something to a person, like a page too
doubtful to read by machine. One that carries no evidence, or records that the
lookup never landed, could not look at all. The pipeline uses that distinction:
a run in which a deciding check could not look does not spend the document in
the submissions ledger, because an outage must cost a retry, never the
document.

Failure ordering is part of the decision. A page that contradicts its own
signature outranks a duplicate, because an alteration is the louder finding
and the same document sent twice is often just a chased payment.

## Consequences

The verdict degrades honestly under outage: lower, never higher, and the
outage is named in the signal a reader sees.

Advisory checks get room to exist. Domain age and counterparty coverage can
say "worth a look" without the power to flag, because a name collision with a
fraud story is not evidence against a document.

Nothing in the system converts absence of evidence into evidence, in either
direction.
