// Write one cached answer, replacing any earlier one for the same key.
//
// Two conditionals rather than an if and an else, because XanoScript documents
// if on its own and nothing in either source shows else. The key arrives
// already namespaced by the caller, so the unique index sits on one column and
// no composite index is relied on.
query "cache" verb=POST {
  api_group = "Signet"

  input {
    text namespace filters=trim
    text key filters=trim
    json value
    timestamp expires_at?
  }

  stack {
    function.run "Signet/require_api_key" {
      input = {}
    }
  
    db.get signet_cache {
      field_name = "key"
      field_value = $input.key
      output = ["id"]
    } as $existing
  
    conditional {
      if ($existing == null) {
        db.add signet_cache {
          data = {
            created_at: "now"
            namespace : $input.namespace
            key       : $input.key
            value     : $input.value
            expires_at: $input.expires_at
          }
        }
      }
    }
  
    conditional {
      if ($existing != null) {
        db.edit signet_cache {
          field_name = "key"
          field_value = $input.key
          data = {
            value     : $input.value
            expires_at: $input.expires_at
          }
        }
      }
    }
  }

  response = null
  guid = "X2TGHdiPftz5sy4GVqhcC49bIpc"
}
