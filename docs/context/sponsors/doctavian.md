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

## The schema, from their developer documentation

Their guides at `developers.doctavian.com/en/how-to/signatures/` carry the full
shape. Recorded here because the earlier section was written from probing and
was incomplete on exactly the parts that matter.

`POST /signatures/envelope/create` takes four top level arrays and objects:

- `documents[]` with `referenceDocumentId` (integer), `name`,
  `loadMethod: "Storage"` and `urn` from the upload
- `recipients[]` with `referenceSignerId` (integer), `name`, `email`,
  `role` and `mandatory`
- `fields[]` with `type`, `isRequired`, `referenceSignerId`,
  `referenceDocumentId`, `name`, and either coordinates
  (`page`, `positionX`, `positionY`, `width`, `height`) **or** an
  `anchorString`, never both
- `envelope{}` with `subject`, `message`, `senderName`, `senderEmail`,
  `isSignOrder`, `expireInDays`, `notifyWhenOpened`, `notifyWhenSigned`

`anchorString` is the useful part. A distinctive marker printed in the document
is found at send time and the field is laid over its bounding box, leaving the
text in place. Coordinates would have to be recomputed every time the paragraph
above the signature block changes length.

The reference ids are locally unique integers within one envelope and link
fields to their document and recipient. They are not system ids.

Envelopes are created in `Draft`. `GET /signatures/envelope/{id}/send` is what
notifies anyone, so a malformed envelope never reaches a person.

## Where it stopped, and what it was

Resolved 28 August. Their engineering manager confirmed two things, and only one
of them was a fault.

**The envelopes were never missing.** A misconfiguration on their side against
the second user on our account made them unreadable, and both ids below now
return 200. Envelopes are not automatically deleted.

**Storage consumption on generation is by design.** Templates and data are
transactional and consumed on each generation, so re-uploading before every
render is the correct way to use the API rather than a workaround for a defect.
That is worth knowing, because the error it produces, `FILE_MISSING_FROM_STORAGE`,
reads like a fault.

One real gap of our own surfaced once their side was fixed:
`envelope.senderEmail` must be a valid address and we were sending an empty
string, which returns `SENDER_INVALID_EMAIL_ADDRESS` naming the field. With it
set, generation, upload, envelope creation and send all succeed.

The account is on `demo.api.doctavian.com` and the existing api key covers
signatures, so `DOCTAVIAN_SIGNATURES_KEY` stays unset.

## What we saw before it was fixed

With that exact payload, create returns **201 Created** and a full set of system
ids:

```
{"result":{"statusCode":201,"message":"Created","data":{
  "envelope":{"id":"b2f0b747-...","status":"Draft"},
  "documents":[{"id":"f75a5845-..."}],
  "recipients":[{"id":"c3720664-..."}],
  "fields":[{"id":"c15747e5-..."}]}}}
```

Two seconds later that envelope does not exist:

```
GET /signatures/envelope/b2f0b747-.../get
-> 400 ENVELOPE_ID_INVALID "Envelope with ID b2f0b747-... does not exist"
```

`GET /signatures/envelope/{id}/send` fails with a null reference for the same
reason, and the portal inbox stays empty.

The template route fails earlier and names the cause plainly:

```
POST /signatures/template/create
-> 500 FILE_NOT_EXISTS_IN_STORAGE
   "File with identifier 8413aaf1-... not found in storage."
```

That is the same behaviour already recorded for document generation, where an
uploaded template is consumed and the next generation fails with
`FILE_MISSING_FROM_STORAGE`. **Uploads do not persist on the demo
environment**, and everything above is downstream of that.

The anchors are genuinely in the generated PDF, confirmed by extracting its
text, so field placement is not the problem.

Nothing on our side can work around a document that is not there. The adapter is
written and wired, and the day storage retains an upload it works unchanged.
