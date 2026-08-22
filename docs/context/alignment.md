# Where Signet stands against each track

Written 22 August 2026, twelve days out. Kept honest rather than flattering,
because the gap list is the build plan.

## Summary

| Track | Prize | State | The gap |
|---|---|---|---|
| name.com | 2,000 | Strong | Only one endpoint family is load bearing |
| Nutrient | 1,500 | Strong, incomplete | No human anywhere in the human in the loop |
| Xano | 2,500 | Partial | Adapter exists, the product does not use it |
| Doctavian | 1,000 | Weak | No agent, and flat fields are what they mock |
| SerpApi | 3,000 | Not started | Largest single prize in the event |
| Foxit | 1,000 | Not started | Fits the issuance path unusually well |
| Perfect Corp | 2,500 | Out of scope, deliberately | |

## name.com

Live and real. An Ed25519 public key is published at `_signet.northpost.dev`
and resolves from public DNS, and verification fetches it on every run. A
second domain, `north-post.dev`, carries its own valid key so the lookalike
attack can be demonstrated rather than described.

Their criteria explicitly favour combining several endpoints. Right now DNS
management is load bearing and availability appears only in the environment
doctor. Search used adversarially, to sweep permutations of an issuer domain
for lookalikes, and registration, to defensively claim them, are both designed
and neither is built.

## Nutrient

Extraction is real and schema driven. We hand DWS the field names the signature
covers and it returns those names with a per field confidence and a bounding
box, which the fidelity check compares against the signed payload. A doctored
page fails while its signature still verifies. That is a core operation used
meaningfully, not a throwaway call.

Their bonus is explicitly a human in the loop where a guess is not acceptable.
Our fidelity check returns UNKNOWN and says "needs a human", and then there is
no human. No DWS Viewer, no review queue, no adjudication surface. The
confidence scores are computed and then discarded rather than routed. That is
the single highest value gap on this track and it is close to free, because the
signal already exists.

## Xano

The record store adapter is written and the API group answers. The CLI uses the
local file store instead, so nothing the product does depends on Xano today.
Their one requirement is that Xano is the backend in a meaningful way, so this
has to change from an adapter that exists to an adapter that is used.

## Doctavian

The weakest fit, and not only because credentials are blocked.

Their brief asks for an AI agent that takes the messiest real world data and
produces a correct document, with templates that branch, loop and calculate.
Our renderer takes a flat mapping of strings and substitutes it, which is the
mail-merge they explicitly define themselves against. Signet also has no agent.
The verdict engine is a pure total function with no model, which is right for
the verification claim and is a direct mismatch with this brief.

The fix is not to bolt an agent on. It is that Signet's issuance path has a
genuine hole: the fields are typed by hand on the command line. Filling that
hole with an agent that normalises messy input into a verified record, and
having Doctavian generate the document from that record, answers the brief and
closes a real weakness at the same time. Generation from a verified record is
itself the control, because the payee block is never typed by a human.

## SerpApi

Not started, largest prize. The argument is that fraud signals are perishable.
A domain registered nine days ago, a counterparty with no web presence, a
business whose published domain differs from the sender's, none of these exist
in a static database at the moment they matter. Live search is load bearing
rather than decorative. This belongs at enrolment and at issuance, not at
verification, so it composes with the agent above.

## Foxit

Not started. Their boundary, that an agent gets forty reversible tools and
signing is deliberately excluded so a human must sign, is the same argument
Signet makes about payment instructions. Agreeing with a sponsor's thesis and
providing the case where it is provably correct is a strong submission.
