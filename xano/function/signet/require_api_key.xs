// The guard every Signet endpoint runs first.
//
// Omitting auth on a Xano endpoint produces a public one, and there is no
// marker that says "public on purpose". A forgotten line is therefore an open
// backend, so the check lives in one function that every endpoint calls rather
// than being repeated and eventually missed.
//
// The emptiness check is not defensive padding. A single equality against an
// unset variable compares empty to empty, so an anonymous caller passed while
// an authenticated one was refused, and the backend was open exactly when
// nobody had configured it. An unconfigured instance now refuses everyone.
//
// Confirmed live: the comparison is against whatever the Authorization header
// carries, so signet_api_key must hold that same form.
function "Signet/require_api_key" {
  input {
  }

  stack {
    precondition ($env.$signet_api_key != "") {
      error_type = "unauthorized"
      error = "Signet is not configured on this instance."
    }
    precondition ($env.$request_auth_token == $env.$signet_api_key) {
      error_type = "unauthorized"
      error = "Signet API key missing or wrong."
    }
  }

  response = null
  guid = "GUB0iF9lBJuYuTScDB-JIQHWBao"
}
