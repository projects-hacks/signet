// Record that a document was seen, and report whether it had been seen before.
//
// The read then insert below is not itself atomic. Two verifiers can both pass
// the read at the same instant, and the unique index on fingerprint is what
// stops the second insert landing. Xano's behaviour on a constraint violation
// is not documented anywhere, so this deliberately does not try to catch and
// interpret that error. It fails loudly instead, which is the correct direction
// for a duplicate check: refusing to answer beats answering "new" twice.
query "submission" verb=POST {
  api_group = "Signet"

  input {
    text fingerprint filters=trim
    text submitted_by filters=trim
  }

  stack {
    function.run "Signet/require_api_key" {
      input = {}
    }
  
    db.get signet_submission {
      field_name = "fingerprint"
      field_value = $input.fingerprint
      output = ["id", "created_at", "submitted_by"]
    } as $existing
  
    // Only the insert is conditional. XanoScript documents if without else, so
    // the caller derives "first seen" from whether existing came back null.
    conditional {
      if ($existing == null) {
        db.add signet_submission {
          data = {
            created_at  : "now"
            fingerprint : $input.fingerprint
            submitted_by: $input.submitted_by
          }
        }
      }
    }
  }

  response = {existing: $existing}
  guid = "VkrpxSd1ZO2QZ_bl2aASFGXnKg8"
}
