# Try it

The fastest way is the hosted page: it hands you the documents itself, freshly
signed per visitor, at https://signet-lime.vercel.app/verify. Nothing here is
needed for that.

The kits below are for testing away from the hosted page: one folder per
person, four invoices per folder, every document carrying its own signature
over its own numbers.

**Type the brand in first.** The checker asks who the document claims to be
from. Put `Northpost Freight Services` there and leave it for all four; on the
command line it is `--brand "Northpost Freight Services"`. Without a claimed
brand there is no name for a domain to be compared against, and the lookalike
below correctly certifies, because nothing on it is forged and nothing is being
imitated. The hosted page fills this in for you.

| File | What it is | What the verifier should say |
| --- | --- | --- |
| `1-genuine.png` | An ordinary invoice, signed by the company that issued it | CERTIFIED |
| `2-doctored.png` | The same invoice with the bank account swapped after signing | FLAGGED, the page disagrees with the signature |
| `3-lookalike.png` | Signed with a real key, from a domain that reads like the real one | FLAGGED, the signing domain is not the brand's |
| `4-the-same-invoice-again.png` | Byte for byte the first file | FLAGGED, already submitted |

Check them against the hosted page, where every check runs. A local build
without extraction credentials runs five of the seven checks and cannot catch
the doctored page. It names the two it is not running at the foot of the report
rather than pretending it asked.

Two rules. Take a kit nobody else has taken: the ledger records every document
ever verified anywhere, so a genuine invoice is new to it exactly once, which
is the point of the fourth file. And keep the order: the fourth is only a
duplicate because you checked the first a moment earlier.

`scripts/make_try_kits.py` generates more kits; it needs the demo signing keys.
