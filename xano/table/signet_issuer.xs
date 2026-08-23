// The brand to domain binding. This is the trust registry: what a verifier
// consults to decide whether the domain that signed is the domain that brand
// signs from.
table signet_issuer {
  schema {
    int id
    timestamp created_at?=now
    text domain filters=trim|lower
    text brand filters=trim
    text public_key_hex filters=trim
    bool enrolled
    bool frozen
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "domain", op: "asc"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]
  guid = "7g1Cm_kZERvUvIkOkPPP1v4EuvA"
}
