// Enrol an issuer, or re-enrol one whose key changed.
//
// Upsert rather than insert, because a domain is unique in this table and
// keygen is the kind of command someone runs twice. The second run should
// replace the key it just superseded, not fail on the index.
query "issuer" verb=POST {
  api_group = "Signet"

  input {
    text domain filters=trim|lower
    text brand filters=trim
    text public_key_hex filters=trim
  }

  stack {
    function.run "Signet/require_api_key" {
      input = {}
    }
  
    db.get signet_issuer {
      field_name = "domain"
      field_value = $input.domain
      output = ["id"]
    } as $existing
  
    conditional {
      if ($existing == null) {
        db.add signet_issuer {
          data = {
            created_at    : "now"
            domain        : $input.domain
            brand         : $input.brand
            public_key_hex: $input.public_key_hex
            enrolled      : true
            frozen        : false
          }
        }
      }
    }
  
    conditional {
      if ($existing != null) {
        db.edit signet_issuer {
          field_name = "domain"
          field_value = $input.domain
          data = {
            brand         : $input.brand
            public_key_hex: $input.public_key_hex
            enrolled      : true
          }
        }
      }
    }
  }

  response = null
  guid = "DXjsSw6R8PKFUrgyqO6oLr7yRb0"
}
