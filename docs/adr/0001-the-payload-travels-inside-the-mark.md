# 1. The payload travels inside the mark

Accepted, 2026-08-20.

## Context

A signature is only as good as the certainty about which bytes it covers. The
first design signed a hash of fields derived from the document at issue time,
and re-derived those fields from extracted text at verification time. Measured
against benign variation, it failed: four out of five formatting variants of
the same document, a thousands separator here, a reordered field there,
produced different hashes. Every one was a false accusation waiting to happen.

## Decision

The signed payload travels inside the mark, verbatim. Verification checks the
signature over exactly the bytes it received and never re-derives them.
`canonicalize` in `core/payload.py` is the single function that forms payload
bytes, called once on the issuing side, and `parse` is its inverse; nothing
else concatenates fields.

Three sub-decisions harden the encoding, each after a measured failure:

- Keys are escaped as well as values, because `amt=14.75;bal` as a single key
  rendered identically to two fields and verified as either.
- The signature is re-encoded through canonical base32 before comparison,
  because eight distinct strings decode to the same 64 bytes, and anything
  that dedupes or audits by mark text can be walked past by re-spelling it.
- A TXT record carrying duplicate tags is rejected outright, because
  appending a second `p=` to a record replaced the domain's key with the
  appender's.

## Consequences

Extraction can disagree with the page and say so, but it can never break the
signature: the fidelity check compares what the page shows against what was
signed, and the signature check needs no extraction at all.

The payload rides in the QR, so its size is budgeted. That constraint shapes
ADR 0005.

A forger who alters the page cannot re-derive a matching payload, because the
payload is not derived from the page at all. They would have to re-sign, and
the key never left the issuer.
