// The duplicate ledger. One row per document ever verified, keyed by
// fingerprint, so replaying a genuine document is visible to every verifier
// rather than only to the one that saw it first.
//
// The unique index is the real guard. Two verifiers can pass the read check at
// the same instant, and the second insert has to be the thing that fails.
table signet_submission {
  schema {
    int id
    timestamp created_at?=now
    text fingerprint filters=trim
    text submitted_by filters=trim
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "fingerprint", op: "asc"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]
}
