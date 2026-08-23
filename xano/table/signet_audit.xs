// Append only. Every verification run leaves a trail here.
//
// Nothing reads this on the verification path. It exists so a verdict can be
// reconstructed months later by someone who was not there.
table signet_audit {
  schema {
    int id
    timestamp created_at?=now
    text run_id filters=trim
    text event filters=trim
    json detail
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "run_id", op: "asc"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]
}
