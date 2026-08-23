// Every enrolled issuer. The lookalike check compares a signing domain against
// the domain a claimed brand actually signs from, and probing one candidate
// spelling at a time would be several hundred round trips to answer one
// question.
query "issuers" verb=GET {
  api_group = "Signet"

  input {
  }

  stack {
    function.run "Signet/require_api_key" {
      input = {}
    }
  
    db.query signet_issuer {
      where = $db.signet_issuer.enrolled == true
      return = {type: "list"}
    } as $issuers
  }

  response = {issuers: $issuers}
  guid = "0JNYxFpivEs0XDKncvQBaWAFws4"
}
