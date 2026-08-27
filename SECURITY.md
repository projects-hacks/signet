# Security

Signet exists to tell people whether a document can be trusted, so a flaw here
is not an inconvenience. It is the product being wrong about the one thing it
claims.

## Reporting

Open a private security advisory on the repository, or email the maintainer
listed on the GitHub profile. Please do not open a public issue for anything
that would let someone forge a verdict.

Say what you found, how to reproduce it, and what you think it lets an attacker
do. A proof of concept against the demo domains is welcome. Please do not test
against anybody else's domain.

## What we consider a vulnerability

The severe class is anything that produces a CERTIFIED verdict for a document
the named domain did not sign, or that suppresses a FLAGGED verdict for one that
contradicts itself. Concretely:

- A signature that verifies against a key the issuer did not publish
- Two different payloads that canonicalise to the same bytes
- A mark that decodes to different fields than it encodes
- Any path that publishes a key to DNS without a countersigned authorisation
- Any input that makes a check report PASS when it could not reach its evidence

We also want to hear about credential exposure, injection into any of the vendor
calls, and anything that lets one submission read another's evidence.

## What is already known and stated

These are documented limits rather than findings. They are in
[docs/limits.md](docs/limits.md) and are not vulnerabilities:

- Whoever controls a domain can sign as that issuer. A domain takeover produces
  signatures that verify, and detection depends on lifecycle monitoring.
- DNSSEC validation is reported but not required, because requiring it would
  exclude most issuers.
- A certified document can still be an invoice you do not owe.
- Duplicate detection is per deployment, not global.
- Ingestion is at least once, so a redelivered submission can be recorded twice.

## Handling of credentials

No credential is committed. `.env` is ignored, `.env.example` carries
placeholders only, and both a pre-commit hook and a CI job scan for secrets, the
CI job over the full history rather than the working tree.

The Doctavian bearer is a session held in `.signet/`, not configuration, and it
renews itself. Signing keys never leave the machine that generated them, and the
public half is derived from the private half rather than stored beside it, so
the two cannot go out of step.
