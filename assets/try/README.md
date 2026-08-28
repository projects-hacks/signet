# Try it

One kit per person. Each kit is a set of four invoices that exist only to be
verified, and every document in a kit carries its own signature over its own
numbers.

Take a kit nobody else has taken and work through it in order:

| File | What it is | What the verifier should say |
| --- | --- | --- |
| `1-genuine.png` | An ordinary invoice, signed by the company that issued it | CERTIFIED |
| `2-doctored.png` | The same invoice with the bank account swapped after signing | FLAGGED, the page disagrees with the signature |
| `3-lookalike.png` | Signed with a real key, from a domain that reads like the real one | FLAGGED, the signing domain is not the brand's |
| `4-the-same-invoice-again.png` | Byte for byte the first file | FLAGGED, already submitted |

Order matters for the last one. It is a duplicate because you verified the first
file a moment earlier, which is the whole point of it.

Documents 1 and 4 work once per kit. The ledger records every document ever
verified, so a genuine invoice can only be new to it once, and that is deliberate
rather than a limitation of the sample. Run `scripts/make_try_kits.py` for more.
