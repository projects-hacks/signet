# 3. The verdict is a pure function, and no model touches it

Accepted, 2026-08-21.

## Context

The obvious 2026 design is a model: score the document, learn from examples,
return a confidence. Detection tools built that way flag roughly one authentic
document in eight, and the forger has a copy of the same tool. A score also
cannot be replayed: ask twice, get twice, explain never.

## Decision

`decide(signals)` in `core/verdict.py` is pure and total. Same signals in,
same verdict out, always: no model, no clock, no network, no randomness. It is
pinned by a golden test suite rather than measured by accuracy, because its
output is evidence, and evidence that cannot be replayed is not evidence.

Two reversals during the build are part of this decision. Verdicts once
carried only a prose reason; the signals now travel with the decision, because
keeping only the sentence made the product look like it was asserting things
rather than checking them. And `decide` re-checks every signal outcome against
the full list rather than the first match, because a replayed bundle carrying
`signature UNKNOWN` followed by `signature PASS` once certified.

Models still exist in the product, in one place: the enrolment agent drafts
paperwork. ADR 0007 records why even there the tools are the safety, not the
model.

## Consequences

A verdict is explainable line by line: each signal names its question, its
answer, and its evidence, and the reader can disagree with the rule rather
than with a weight.

An archived run re-decides offline to the identical verdict, which is what
makes a dispute six months later settleable.

The cost is that Signet never gets smarter on its own. New fraud shapes need
new checks, written and tested, which is the trade this product wants: a
false accusation shipped by a silent model update is the failure it exists to
avoid.
