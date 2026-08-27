# Doctavian, "Generate It Right. Sign It Tight."

| | |
|---|---|
| Prize | 500 USD plus a 150 USD subscription, second place 200 plus 150 |
| Contact | hello@doctavian.com |
| Judge on panel | Kanwal Roshi, Engineering Manager, Maven Mule |

## What they are selling

A document operations platform for generating and digitally signing documents,
built for structured data with real complexity. Their templates use expressions
and elements that branch, loop and calculate on the fly, so one template handles
whatever data arrives and shapes the result correctly every time.

They are explicit about what they are not: "Most document APIs are glorified
mail-merge, swap a name, swap a number, ship it." Anything that looks like flat
field substitution answers the brief badly by their own framing.

## The challenge

Bring the messiest, most real-world data problem you have, and build an AI agent
that turns it into a document that gets it right, repeatedly. Take it all the
way to signed if the idea calls for it.

## Hard requirement

The agent must actually call Doctavian's generation API to shape a real
document, not just talk about one.

## Credentials

They say to reach out when you register and they will set the team up fast.
This is human in the loop and should have been an email on day one.

## Submit

Project name and one line pitch, public repo with setup instructions, two to
four minute demo video, one line on where Doctavian did the real work and why.

## The signatures API, mapped by hand

Their signatures product is live on the demo environment and the portal shows it
at `demo.portal.doctavian.com/signatures/envelopes`. None of it appears in any
published spec, and there is no OpenAPI document at any standard path, so the
surface below was recovered from their own portal bundle and confirmed by call.

**The existing key works.** No separate signatures credential is needed, which
means `DOCTAVIAN_SIGNATURES_KEY` can stay unset.

Same base as documents, `https://demo.api.doctavian.com/v1`, same two headers,
same result envelope.

| Purpose | Call |
|---|---|
| Upload a document | `POST /signatures/document/upload`, multipart |
| Download one | `GET /signatures/document/{id}/download` |
| Create an envelope | `POST /signatures/envelope/create` |
| Send it | `GET /signatures/envelope/{id}/send` |
| Read it back | `GET /signatures/envelope/{id}/get` |
| Its fields | `GET /signatures/envelope/{id}/fields` |
| The audit trail | `GET /signatures/envelope/{id}/audit/get` and `/audit/download` |
| A signed document | `GET /signatures/envelope/{id}/document/{documentId}/download` |
| Cancel | `GET /signatures/envelope/{id}/cancel` |
| Templates | `/signatures/template/list`, `/template/create`, `/template/{id}/envelope/create` |

Confirmed working:

```
POST /signatures/document/upload   -> 201 {"files":[{"id":"8413aaf1-...","fileName":"seal-probe.pdf"}]}
GET  /signatures/envelope/list     -> 200 {"envelopes":[],"rowCount":0}
GET  /signatures/template/list     -> 200 {"templates":[],"rowCount":0}
```

### What is still unknown

`POST /signatures/envelope/create` validates, so the shape is partly recoverable
from its own error messages:

- `documents[]` takes `urn`, `name` and `referenceDocumentId`, and that last one
  must be an **integer**, not a string. Sending a string returns a .NET
  conversion error naming the field.
- `recipients[]` cannot be empty, and takes `referenceRecipientId`, `email`,
  `name`, `order` and `type`.

With both present the call returns a 500 carrying
`Object reference not set to an instance of an object`, which is a null
dereference on their side rather than a validation message, so it names nothing.
Tried and still failing: `type` as an integer, `type` omitted, an empty `fields`
array, and `firstName`/`lastName` instead of `name`.

At least one more required field exists and their errors will not say which.

### How to settle it

Create one envelope in the portal with the browser network tab open and read the
request body of the `envelope/create` call. That is definitive and takes two
minutes, and it is faster than continuing to guess against a null reference.
