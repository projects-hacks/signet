// The guard every Signet endpoint runs first.
//
// Omitting auth on a Xano endpoint produces a public one, and there is no
// marker that says "public on purpose". A forgotten line is therefore an open
// backend, so the check lives in one function that every endpoint calls rather
// than being repeated and eventually missed.
//
// UNVERIFIED, confirm on the first live call: whether $env.$request_auth_token
// arrives with the "Bearer " prefix intact. Set the signet_api_key environment
// variable to whatever form the header actually carries, prefix included if it
// is there. The composition of $env.$request_auth_token with a precondition is
// documented piece by piece but no source shows it written out.
function "Signet/require_api_key" {
  input {
  }

  stack {
    precondition ($env.$request_auth_token == $env.$signet_api_key) {
      error_type = "unauthorized"
      error = "Signet API key missing or wrong."
    }
  }

  response = null
}
