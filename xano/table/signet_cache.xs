// Third party answers, held so a question is asked once.
//
// This is budget protection rather than speed. Live search has a hard monthly
// quota and re-asking the same question burns it.
//
// key arrives already namespaced by the caller, so uniqueness sits on one
// column. A composite unique index is structurally possible in XanoScript but
// no source demonstrates one, and the correctness of the whole cache rests on
// this index holding.
table signet_cache {
  schema {
    int id
    timestamp created_at?=now
    text namespace filters=trim
    text key filters=trim
    json value
    timestamp expires_at?
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "key", op: "asc"}]}
  ]
}
