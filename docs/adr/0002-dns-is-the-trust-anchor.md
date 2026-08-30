# 2. The issuer's own DNS is the trust anchor

Accepted, 2026-08-20.

## Context

Something has to vouch for the binding between a brand and a signing key. The
established answer is a certificate authority: X.509, or in the regulated
e-invoicing world, the eIDAS qualified electronic seal. That path is real, it
is what several mandates endorse, and it was considered.

It was rejected for this product because it reintroduces the enrolment
gatekeeper. A CA model means every issuer buys a relationship with an
authority before their first document can verify, and every verifier trusts
that authority's judgement rather than anything they can check themselves.

## Decision

The key lives in a TXT record at `_signet.<domain>`, published by whoever
controls the domain's DNS and nobody else. The precedent is DKIM: domain
anchored keys in TXT records have carried mail authentication for twenty
years, on exactly this trust model.

Downstream choices follow from the transport. Ed25519, because a 32 byte
public key fits a TXT record with room to spare and RSA at comparable
strength does not. Reads go over DoH to two providers on separate
infrastructure, and agreement between them is the signal, because a single
resolver's answer is a single point of spoofing. DNSSEC is reported when the
chain validates but never required, because requiring it would exclude most
issuers.

## Consequences

Anyone can check any document with dig and openssl and no account anywhere,
which is the product's central claim and docs/verify-by-hand.md proves it.

The sender has to go first. A document from a company that never published a
key can only ever be unsigned, which docs/limits.md states as the first
limit: adoption is the constraint, not cryptography.

Signet must never be mistaken for the mandated eIDAS path. It is a different
mechanism on a different trust model, and the limits doc says so in those
words.
