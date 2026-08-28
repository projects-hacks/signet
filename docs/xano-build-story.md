# Build story

Written for the Xano challenge, which asks what software we replaced and how we
built the replacement.

## The software we replaced

Not a product. A phone call.

When an invoice arrives from a supplier and the bank details differ from last
time, the control in almost every finance team is that somebody rings the
supplier on a number they already had and asks whether the change is real. It
works. It is also slow, it does not scale, it is skipped under deadline
pressure, and it fails completely when the person answering has themselves been
compromised.

Around that sits a second layer we also replace: invoice fraud detection tools
that inspect the document and guess. They look at fonts, compression artefacts
and layout consistency, and they were built when forging a convincing invoice
was hard. It is no longer hard, and the forger has a copy of the same tool.

Both are answering the wrong question. They ask "does this look genuine". We
replace them with software that asks the sender.

The numbers are the reason it is worth replacing. Business email compromise,
where an invoice arrives from a real supplier with the bank details changed,
took **3.05 billion dollars** in 2025 with an average loss per report of
**122,000 dollars**, and **86 percent** of that money moves by wire or ACH, so
by the time anyone notices it has gone. Figures from the FBI Internet Crime
Complaint Center 2025 annual report.

## Why this one

Three reasons, in order of how much they mattered.

It is a control that everyone agrees is inadequate and nobody has replaced,
because the replacement is not a better inspection. It is a different question,
and asking it needs the sender to have published something first.

It is falsifiable. The claim is that a recipient can verify a document with
`dig` and `openssl` and no account, and either that works in front of you or the
whole thing is theatre. Most fraud tooling cannot be checked by the person
relying on it.

And the failure is expensive and quiet. Nobody notices a wrong bank account
until the supplier chases the invoice a month later.

## Where Xano is the backend

Xano holds everything the verdict depends on that is not in the document itself.
Take it away and three of the seven checks stop working and the audit trail
disappears.

| Table | What it carries | Which claim breaks without it |
|---|---|---|
| `signet_issuer` | domain, brand, public key, enrolled, frozen | identity and lookalike checks, and enrolment is the only writer of identity |
| `signet_submission` | the fingerprint ledger | duplicate detection, which is meaningless per process |
| `signet_cache` | evidence with expiry | the live search budget, a few hundred a month shared across every process |
| `signet_audit` | append only | every verdict, and every time a person overrode a machine reading |
| `signet_review` | adjudication state | the human in the loop path |

Eight endpoints under one API group, plus a shared function
`require_api_key` that every one of them calls first. The function stack is
committed in `xano/` so it can be read rather than described.

Three things about that design are worth pointing at.

**The browser never talks to Xano.** Every call goes through our own service.
Calling Xano from the frontend would mean shipping the API key inside the
JavaScript bundle, where anyone could read it out of the page and write to the
issuer table.

**The cache is a budget control, not a speed optimisation.** Live search allows
a few hundred queries a month. Without a shared cache, two processes checking
the same counterparty spend twice, and the month is gone by Thursday. Expiry is
enforced on read, because the store returns whatever row it holds and an expired
entry has to read as absent.

**The audit log is the product's output, not its telemetry.** A verdict a reader
cannot re-derive is not evidence. Every run, every signal and every human
adjudication is written there, including who made it and what the machine had
said before they overrode it.

The site is deployed on Xano static hosting as well as Vercel.

## The security bug Xano taught us

Our first `require_api_key` was one line: compare the request token to the
configured key. With the key unset it compared empty to empty, so **anonymous
callers got 200 and authenticated ones got 401**. Exactly backwards.

Finding it needed a second lesson. Their documentation gives `$env.$<name>` as
the syntax for environment variables, and that returns null for user defined
ones. We proved it with a temporary endpoint reporting both forms side by side:
`doubled_null: true, single_null: false, single_len: 43`. The doubled sigil is
for Xano built-ins only.

The fix is a precondition that the key is configured at all, before the
comparison that uses it. It is three lines and it is the reason the store is not
world writable.

## How it was built

**Approximately eight days.** First commit 20 August, this written on 28 August.
Eighty one commits. The tooling question the submission form asks is answered
there rather than here, where it would not mean anything to a reader of the
code.

Roughly 7,000 lines of source and 4,900 lines of tests, 400 tests, strict type
checking, and continuous integration that runs with no credentials at all so a
fork gets the same result.

## What would have taken far longer

**Eight vendor integrations, and the parts of them that are wrong.** Every one
of these cost hours and would have cost days alone: Doctavian's demo host
appears in no published spec and a key issued elsewhere is refused with a
message that names the wrong cause; their storage consumes an uploaded template
so the second render of the same document fails; Foxit's published eSign
endpoint is a different product from the one a portal account gets, and their
own MCP server has three defects between a client and a working session, from a
console script pointing at a package that does not exist to an entry point
incompatible with the FastMCP version it depends on. Finding those meant
reading their client code, their portal bundle, and their responses, rather than
their documentation.

**The Xano backend itself.** Seven tables, eight endpoints and a shared auth
function, written as XanoScript and pushed from the command line, in an
afternoon. The auth bug above is the kind of thing that would have shipped.

**Measuring instead of assuming.** We chose the model by running four candidates
against our own tool schemas rather than a leaderboard, and found that two
capable models, told to hurry, would enrol a lookalike domain while reporting
the check as passed. That measurement is why every gate in this system is a
precondition in code rather than an instruction in a prompt. It cost an hour and
it changed the architecture.

**The bug our own extraction confidence caught.** On a photographed copy of a
genuine invoice, extraction returned the account number at 0.40 confidence and,
on the same page, an entirely invented bank code at 0.95. We would have flagged
an authentic document, which is the exact failure this product exists to
prevent. A discrepancy now only counts when the page it was read from was read
cleanly.

None of that is the part anyone demos. It is the part that makes the demo true.
