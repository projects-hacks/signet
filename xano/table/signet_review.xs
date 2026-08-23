// The queue a human works.
//
// Extraction returns a confidence per field. Below the threshold the pipeline
// says the field needs a person, and until this table existed that sentence went
// nowhere. A row here carries the disputed value, what was signed, and the box
// on the page, so a reviewer sees the one region in question rather than reading
// a whole document.
table signet_review {
  schema {
    int id
    timestamp created_at?=now
    text run_id filters=trim
    text field_name filters=trim
    text extracted_value
    text signed_value
    decimal confidence
    json box?
    enum state {
      values = ["pending", "approved", "rejected"]
    }
    text decided_by?
    timestamp decided_at?
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "state", op: "asc"}]}
    {type: "btree", field: [{name: "created_at", op: "asc"}]}
    {type: "btree", field: [{name: "run_id", op: "asc"}]}
  ]
}
