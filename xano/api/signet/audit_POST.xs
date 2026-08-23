// Append one line to the trail. Never read on the verification path.
//
// A verdict that depends on logging is a verdict that goes down when logging
// does, so a caller treats a failure here as noise rather than as a result.
query "audit" verb=POST {
  api_group = "Signet"

  input {
    text run_id filters=trim
    text event filters=trim
    json detail?
  }

  stack {
    function.run "Signet/require_api_key" {
      input = {}
    }
  
    db.add signet_audit {
      data = {
        created_at: "now"
        run_id    : $input.run_id
        event     : $input.event
        detail    : $input.detail
      }
    }
  }

  response = null
}
