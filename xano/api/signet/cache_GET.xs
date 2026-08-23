// Read one cached third party answer.
//
// Expiry is returned rather than enforced here. Comparing a stored timestamp
// against now inside a function stack is expressible but no source demonstrates
// it, and a cache that silently serves stale data is worse than one whose
// freshness the caller can see and decide on.
query "cache" verb=GET {
  api_group = "Signet"

  input {
    text key filters=trim
  }

  stack {
    function.run "Signet/require_api_key" {
      input = {}
    }
  
    db.get signet_cache {
      field_name = "key"
      field_value = $input.key
      output = ["namespace", "key", "value", "expires_at"]
    } as $entry
  }

  response = $entry
}
