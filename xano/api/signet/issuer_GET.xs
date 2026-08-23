// Resolve one issuer by domain. The hot path of every verification.
query "issuer" verb=GET {
  api_group = "Signet"

  input {
    text domain filters=trim|lower
  }

  stack {
    function.run "Signet/require_api_key" {
      input = {}
    }
  
    // Absent returns null with a 200 rather than a 404. Xano answers 404 both
    // for a record that does not exist and for a route that was never built,
    // and an empty workspace reading as a working one is how this backend went
    // unnoticed once already.
    db.get signet_issuer {
      field_name = "domain"
      field_value = $input.domain
      output = ["domain", "brand", "public_key_hex", "enrolled", "frozen"]
    } as $issuer
  }

  response = $issuer
  guid = "vbMFknhfUo-R1dXyQSunS57Dt4Y"
}
