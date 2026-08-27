# Foxit, "Your Agent Shouldn't Sign That"

| | |
|---|---|
| Prize | 700 USD, second place 300 |
| Contact | theodore_castro@foxitsoftware.come (trailing e is in the source; try .com) |

## The challenge

Build an agent that starts from a plain prompt and ends with a signed document.

Their open source MCP server wraps the Foxit PDF Services API and gives an agent
forty tools for the reversible work: generation, conversion, merging,
compression, OCR, extraction. Signing is left out of the catalogue on purpose.
To send anything for signature the agent must call the Foxit eSign API directly,
with its own credentials, and a person has to sign it.

They say that handoff is the interesting part and they want to see how it is
designed. They also invite disagreement: if signing belongs in the agent's
toolset, or the boundary sits elsewhere, build it that way and defend it.

## What we are building

Signet has exactly one irreversible act, and it is not printing an invoice. It is
publishing a signing key to DNS. Once `_signet.<domain>` carries a key, that
domain vouches for every document signed with it, indefinitely, to everyone.

So the agent does the whole enrolment up to that point and stops. It resolves the
brand against live search, generates the keypair, has the authorisation document
generated, assembles and checks it through the MCP tools, and sends it for
signature. It cannot publish. The broker publishes, and only after it has read
the executed document and found the authorisation hash it embedded itself.

Where we disagree with the brief: signing a PDF is reversible, since an envelope
can be voided. A DNS write is not. The tool that belongs outside the catalogue is
the one whose effects outlive the agent.

## Verified against the live account, not the blog

Their developer blog documents a legacy eSign surface at
`na1.foxitesign.foxit.com` with an OAuth2 token exchange. That is not what a
developer portal account gets, and using it returns
`invalid_client / invalid consumer credentials`. The portal is a different
product. Confirmed by call:

- **One gateway for every Foxit API**: `https://na1.fusion.foxit.com`
- **One credential pair** covers eSign, PDF Services, Document Generation and
  Embed. Sent as two plain headers, `client_id` and `client_secret`. No token
  exchange, no bearer.
- eSign paths carry a version segment: `/esign/api/v1/...`. Without the `v1` the
  gateway answers 404, which reads like a permission problem and is not one.
- The storage region picked at activation does not change the endpoint.

Working calls, both returning 200 on the hackathon account:

```
POST /pdf-services/api/documents/upload   -> {"documentId": "..."}
GET  /esign/api/v1/webhook/channellist    -> {"result": "success", ...}
```

Account 2917678, US region.

## Budget, which shapes the design

The free developer plan is **500 credits a year**, shared across every Foxit API,
not per product.

| Operation | Credits |
|---|---|
| Any PDF Services processing call | 1 |
| An eSign envelope, created by API or in their UI | 5 |
| Upload, download, task polling, other eSign calls | 0 |

Envelopes are billed on creation, so a draft costs the same five credits as one
that is sent. Rehearsals create envelopes. Every run of the enrolment flow costs
five credits plus one per MCP tool call, so the flow is exercised against
recorded responses and spent live only when the result is kept.

Rate limits are per application: 15 requests a minute in sandbox, 100 in
production.

## Endpoints the broker depends on

| Purpose | Call |
|---|---|
| Create envelope | `POST /esign/api/v1/folders/createfolder` |
| Envelope status | `GET /esign/api/v1/folders/myfolder` |
| Download executed files | `GET /esign/api/v1/folders/download` |
| Activity history | `GET /esign/api/v1/folders/viewActivityHistory` |
| Webhook channels | `POST /esign/api/v1/webhook/createwebhookchannel` |

`sendNow: false` creates a draft without emailing anyone, which is how the flow
is rehearsed without mailing a recipient. It still costs the five credits.

Webhooks post `event_name`, `event_date` and a `data` object, and sign the body
with HMAC-SHA-256 under a `webhookSecret`, base64 encoded into a `signature`
query parameter. Useful for promptness. The release still does not rest on it:
the broker downloads the executed document and looks for the authorisation hash
it put there, because a payload field is something the sender controls and the
hash is something we control.
