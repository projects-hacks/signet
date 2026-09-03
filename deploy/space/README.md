---
title: Signet Verifier
emoji: 🔏
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Signet verifier

The API behind [Signet](https://github.com/projects-hacks/signet), which answers
whether a document was really sent by the company it names.

This container verifies and nothing else. It cannot issue a document, enrol an
issuer, or write to DNS. Those are deliberately not reachable from anything
public, so the worst a compromise here achieves is a wrong answer about a
document somebody uploaded, never a forged one.

## Endpoints

| | |
|---|---|
| `GET /api/health` | whether extraction is configured |
| `POST /api/verify` | one document, one verdict, as JSON |
| `POST /api/examine` | the same run, streamed as each check answers |
| `POST /api/adjudicate` | a person answering what the extractor could not read |
| `GET /api/sample/{kind}` | a demo document, signed at the moment it is asked for |

## Configuration

Set these as Space secrets. Three services, because that is all verification
needs.

| Secret | Why |
|---|---|
| `XANO_BASE_URL`, `XANO_API_KEY` | issuers, the submissions ledger, the audit log |
| `NUTRIENT_API_KEY` | reading the page as it arrived |
| `SERPAPI_API_KEY` | what the live web publishes for the brand |
| `SIGNET_ALLOWED_ORIGINS` | the site allowed to call this from a browser |

DNS is read over HTTPS from two public resolvers and needs no credential, which
is the point of anchoring to DNS in the first place.
