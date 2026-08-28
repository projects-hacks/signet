# What Signet does not tell you

A verification tool that overstates its answer is worse than none, because a
reader stops looking at the point the tool stops. This page is the list of things
a CERTIFIED verdict does not mean.

## The sender has to go first

This is the limit that matters most, and no amount of engineering removes it.

Signet says nothing about an invoice from a company that has not published a
key. Not that it is suspicious, not that it is fine: `UNSIGNED`, no proof
available. A supplier who prints an invoice, signs it by hand and photographs it
gets exactly that, and correctly so.

So the value is bounded by adoption, and adoption starts with the party who is
not the one being defrauded. The buyer carries the loss; the supplier has to
act. That asymmetry is the whole problem.

The two paths that have worked for comparable mechanisms are a large buyer
requiring it of its suppliers, which is how structured e-invoicing formats
actually spread, and an intermediary publishing on the supplier's behalf, which
is how most companies ended up with DKIM without ever configuring it.

A photograph of a document that *was* issued through Signet is fine. The mark
survives being photographed, scanned, faxed, forwarded and printed again, which
is what the QR is for and what it was tested against.

## Where this sits against regulation

The problem is regulated. The mechanism is not ours.

France requires large enterprises to issue structured e-invoices from September
2026, and requires every business of any size to be able to receive them from
the same date. Italy has been mandatory since 2019. The direction is settled.

What those regimes endorse is the **eIDAS qualified electronic seal**, issued by
a Qualified Trust Service Provider. Article 35 gives it a legal presumption of
integrity and origin: in a dispute the burden falls on whoever challenges the
document. It is recognised across all twenty seven member states.

Signet has none of that. It is a certificate authority model and ours is not,
and we should not be mistaken for the mandated path.

Where this is useful instead: outside the EU, where no mandate and no trust
service infrastructure exists; for small suppliers who will not buy a qualified
certificate to send four invoices a month; and alongside a seal rather than
instead of one. A qualified seal proves a document in court. This proves it to
the person about to pay, in the time it takes to read a DNS record, with no
public key infrastructure on either side.

The mechanism itself is not speculative. Every legitimate email you receive is
verified against a key published in the sender's own DNS, and has been for
twenty years. What is new here is applying it to documents, where no standard
exists yet.

## Issuance is not entitlement

CERTIFIED means the named domain signed these fields and they have not changed.
It does not mean the goods arrived, the work was done, the amount is right, or
that the invoice is owed at all. A real company can certify a real invoice for
something you never ordered. Signet moves the argument from "is this document
genuine" to "is this charge correct", which is the argument you can actually have
with a counterparty.

## The domain is the identity

Trust rests on the issuer controlling their DNS. Whoever controls the domain can
publish a key and sign as that issuer. A registrar account compromise, a lapsed
renewal picked up by somebody else, or a hijacked nameserver all produce
signatures that verify. Domain lifecycle changes are watched for this reason, but
the window between a takeover and its detection is real.

## DNSSEC is advisory here

The key is read over DNS-over-HTTPS from more than one provider and the answers
must agree, which raises the cost of a poisoned response. Where the zone is
signed, the validation state is reported. Where it is not, the answer still
counts. Requiring DNSSEC would exclude most issuers, so it strengthens a verdict
rather than gating it.

## Identity is only as good as enrolment

The binding of a brand to a domain is reviewed by a person once, at enrolment.
Everything the identity check later says rests on that review being right. The
counterparty check exists because most companies are not enrolled with anyone,
and it reads what the open web publishes rather than anything we hold.

## Live search is evidence, not adjudication

Adverse coverage found by search is reported for a person to read. It never
decides a verdict. Keyword matching on news text produces false positives often
enough that a rule acting on it would train readers to dismiss the check.

## Extraction can misread a page

Field extraction reads a photograph. Confidence is reported per field and low
confidence values are put to a person rather than compared silently. A field the
extractor could not read is reported as unread, never as matching.

## Duplicate detection is per store

The same document submitted twice to the same deployment is caught. Two separate
deployments do not see each other's ledgers.

## A verdict is about a document, not a payment

Signet says nothing about whether the account on a certified invoice is one your
bank will accept, whether the counterparty is solvent tomorrow, or whether a
person inside your own organisation changed the payment instruction after the
document was checked.
