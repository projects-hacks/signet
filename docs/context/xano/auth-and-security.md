# Authentication, endpoint security, and secrets

Sources: the `.xs` files under `xano/` marked `[workspace]`, and `docs.xano.com` pages marked `[docs]`.

---

## 1. How an endpoint is secured

There is exactly one declarative mechanism: an `auth` property on the endpoint block naming the authentication table.

`[workspace]` from `xano/api/authentication/auth/me_GET.xs`:

```
query "auth/me" verb=GET {
  api_group = "Authentication"
  auth = "user"
```

`[docs]` (`xanoscript/api`) lists `auth` as an optional string setting: "Specifies the authentication level required for this endpoint."

Rules established by the workspace:

- Three endpoints set `auth = "user"`: `auth/me`, `reset/update_password`, and `logs/user/my_events`.
- Every other endpoint simply **omits** the property. That is how a public endpoint is written. No `query` in the workspace writes `auth = false`.
- Omission is the default, so forgetting `auth` produces a public endpoint. There is no opt out marker to make that intent explicit and reviewable.

When `auth` is set, the token identity is available as `$auth`. Only `$auth.id` is used anywhere in the workspace:

```
    db.get user {
      field_name = "id"
      field_value = $auth.id
      output = ["id", "created_at", "name", "email", "role"]
    } as $user
```

The complete set of fields on `$auth` is **not documented**. `extras` passed at token creation presumably lands there, but no source shows it being read.

---

## 2. The authentication table

`[workspace]` a table becomes an auth source with `auth = true`, in `xano/table/user.xs`:

```
table user {
  auth = true
```

Passwords live in a field of type `password`, with validation attached as schema filters:

```
    password? password filters=min:8|minAlpha:1|minDigit:1
```

Hashing is implicit in the `password` field type. Nothing in the workspace hashes before writing. `[workspace]` `signup_POST.xs` writes the plaintext input straight into `db.add`:

```
    db.add user {
      data = {
        created_at: "now"
        name      : $input.name
        email     : $input.email
        password  : $input.password
        role      : "member"
      }
    } as $user
```

---

## 3. Issuing and checking a token

### Issue

`[workspace]` from `signup_POST.xs`:

```
    security.create_auth_token {
      table = "user"
      extras = {}
      expiration = 86400
      id = $user.id
    } as $authToken
```

`table` names the auth table, `id` is the record to bind, `expiration` is in seconds. `[docs]` (`xanoscript/function-reference/security`) documents `extras` as "A JSON object that contains any extra information you want to include in the token" and shows it populated:

```
    security.create_auth_token {
      table = "users"
      extras = { "role": "admin" }
      expiration = 86400
      id = 1
    } as $authToken
```

Note the workspace is inconsistent about the empty value: `extras = {}` in `login_POST.xs` and `signup_POST.xs`, but `extras = ""` in `magic_link_login_POST.xs`. Both round tripped, so both parse.

### Verify a password

`[workspace]` from `login_POST.xs`. It returns a boolean, checked by the following precondition:

```
    security.check_password {
      text_password = $input.password
      hash_password = $user.password
    } as $pass_result

    precondition ($pass_result) {
      error_type = "accessdenied"
      error = "Invalid Credentials."
    }
```

### Full login flow

`[workspace]` the whole stack of `xano/api/authentication/auth/login_POST.xs`, which is the canonical shape:

```
  stack {
    // Get the user record via email
    db.get user {
      field_name = "email"
      field_value = $input.email
      output = ["id", "created_at", "name", "email", "password", "role"]
    } as $user

    // Check to make sure a user with that email exists
    precondition ($user != null) {
      error_type = "accessdenied"
      error = "Invalid Credentials."
    }

    // Check that the password matches the hashed password
    security.check_password {
      text_password = $input.password
      hash_password = $user.password
    } as $pass_result

    // Verify that the password check passed
    precondition ($pass_result) {
      error_type = "accessdenied"
      error = "Invalid Credentials."
    }

    // Create an authentication token
    security.create_auth_token {
      table = "user"
      extras = {}
      expiration = 86400
      id = $user.id
    } as $authToken
  }

  response = {authToken: $authToken, user_id: $user.id}
```

Both failure branches return the same message, which is correct practice and worth preserving.

---

## 4. How a static API key or bearer token is checked inside a function stack

Nothing in the workspace does this. The mechanism is assembled from documented parts.

### The raw material

`[docs]` (`building/logic/working-with-data/environment-variables`) Xano maintains request scoped values exposed through `$env`:

| Variable | Contents |
| --- | --- |
| `$remote_ip` | IP address of the caller |
| `$http_headers` | a text array of the headers sent to the endpoint |
| `$api_baseurl` | base URL of the active endpoint |
| `$request_uri` | the URI being accessed |
| `$request_method` | the HTTP method of the incoming request |
| `$request_querystring` | the query string |
| `$request_auth_token` | **the authorization token of the API request** |
| `$datasource` | which datasource is in use |
| `$branch` | which branch is in use |

`$request_auth_token` is the documented hook for reading a bearer token on an endpoint that does not use `auth =`. `$http_headers` is the fallback for a custom header such as `X-API-Key`, but it is documented only as "a text array of headers", so parsing a single named header out of it would need a filter chain that neither source demonstrates.

### The reference syntax

`[workspace]` the one and only environment variable read in the workspace, in `request_reset_link_GET.xs`. Note the doubled `$`:

```
    // Create a variable with the API base URL
    var $api_base_url {
      value = $env.$api_baseurl
    }
```

The form is `$env.$<name>`. There is exactly one instance, so that line is the entire evidence for the syntax.

### The comparison

`[workspace]` `precondition` is the guard idiom, and it takes an arbitrary expression. A shared secret check would be a `precondition` comparing `$env.$<secret_name>` against `$env.$request_auth_token`. **No source shows this written out**, so treat the composition as unverified even though every piece is individually documented.

Two things are **not documented** and matter here:

1. Whether string comparison in a `precondition` is constant time. Assume it is not.
2. Whether `$env.$request_auth_token` includes the `Bearer ` prefix or strips it.

### Middleware, the better place for a shared guard

`[docs]` (`xanoscript/middleware`) middleware can be applied to APIs, custom functions, background tasks, and tools, and runs pre or post. Its stack works like any other and can halt execution with a `precondition`:

```
middleware <middleware_name> {
  input {
    json vars
    enum type {
      values = ["pre", "post"]
    }
  }

  stack {
    db.get user {
      field_name = "id"
      field_value = $auth.id
    } as $user1

    precondition ($user1.banned == false) {
      error_type = "unauthorized"
      error = "Your account has been suspended."
    }
  }

  response = {user1: $user1}
}
```

`vars` carries the calling context (for APIs, "Contains `$input`, `$auth`, and other API-specific variables"). Settings:

| Setting | Values | Default |
| --- | --- | --- |
| `response_strategy` | `"merge"`, `"replace"` | `"merge"` |
| `exception_policy` | `"critical"`, `"silent"`, `"rethrow"` | `"silent"` |

`exception_policy` defaulting to `"silent"` is a trap for a security guard: a middleware that throws would be swallowed unless the policy is set to `"critical"` or `"rethrow"`. **How a middleware is attached to a specific endpoint is not documented** in the pages reviewed; the middleware file declares itself but nothing observed declares the binding.

---

## 5. Authorization beyond authentication

Role checks are application level, not part of `auth`.

`[workspace]` the complete stack of `xano/function/quick_start/enforce_role.xs`, which builds a numeric hierarchy and throws:

```
  stack {
    // Defines a hierarchy of roles with numerical levels.
    var $role_hierarchy {
      value = {admin: 2, member: 1}
    }

    // Retrieve the user's role from the database.
    db.get user {
      field_name = "id"
      field_value = $input.user_id
      output = ["role"]
    } as $user

    // Ensure the user exists
    precondition ($user != null) {
      error_type = "inputerror"
      error = "User not found with the provided ID."
    }

    var $user_role {
      value = $user.role
    }

    var $user_role_level {
      value = $role_hierarchy|get:$user_role
    }

    var $required_role_level {
      value = $role_hierarchy|get:$input.required_role
    }

    precondition ($required_role_level > 0) {
      error_type = "inputerror"
      error = "Invalid required role specified: " ~ $input.required_role
    }

    conditional {
      if ($user_role_level < $required_role_level) {
        throw {
          name = "accessdenied"
          value = "User does not have the required role to perform this action. Required: " ~ $input.required_role ~ ", Actual: " ~ $user_role
        }
      }
    }
  }
```

Worth noting: this function is **defined but never called** by any endpoint in the workspace. It is a template, not a wired up control.

The role itself is a plain enum column on the auth table, `xano/table/user.xs`:

```
    enum role? {
      values = ["admin", "member"]
    }
```

Ownership checks are written by hand as preconditions. `[workspace]` from `update_password_POST.xs`:

```
    precondition ($user.id == $auth.id) {
      error_type = "accessdenied"
    }
```

And row scoping is done in the `where` clause. `[workspace]` from `my_events_GET.xs`:

```
    db.query event_log {
      where = $db.event_log.user_id == $auth.id
      return = {type: "list"}
    } as $user_events
```

There is no row level security, no policy layer, and no automatic tenant scoping in either source. Every query is responsible for its own filtering.

---

## 6. Error types

`error_type` values observed across both sources: `"accessdenied"`, `"notfound"`, `"unauthorized"`, `"inputerror"`. The complete enumeration is **not documented**, and neither source maps an `error_type` to an HTTP status code. `throw` uses the same vocabulary under different property names (`name` and `value` instead of `error_type` and `error`).

---

## 7. Secrets and environment variables

### Where they live

`[docs]` (`building/logic/working-with-data/environment-variables`): environment variables are persistent, workspace wide values intended for "external API keys or other sensitive information that you need to use across multiple function stacks, without storing it in a database table."

Key constraint, quoted in substance: they can be **read** in any logic or workflow, but they **cannot be modified from anywhere except the settings panel**. The documented guidance is to use them only for values that do not change often.

They are managed in the Xano UI under the gear icon, then Settings, then Manage. Read syntax is `$env.$<name>` as shown above.

### What is not there

- There is no separate secret store distinct from environment variables in either source.
- There is no secret reference syntax in XanoScript beyond `$env.$name`.
- No workspace file declares an environment variable, so there is no local declaration, default, or type for one. The name `$api_baseurl` used in `request_reset_link_GET.xs` happens to be a Xano provided variable, not a user defined one.
- The workspace leaves outbound credentials **blank** rather than referencing a secret. From `xano/ai/tool/search_xano_docs.xs`, `bearer_token = ""`. `util.send_email` similarly uses `service_provider = "xano"` and carries no key. So the workspace demonstrates no pattern at all for injecting a secret into an outbound call.

### CLI handling

`xano workspace pull --env` includes environment variables in a pull, which means **secrets can land in the local tree and therefore in git**. There are `xano sandbox env set` and `xano tenant env set` commands but no documented `xano workspace env set`. See `cli.md` section 8.

---

## 8. Cryptographic building blocks available in a stack

`[docs]` (`xanoscript/function-reference/security`), all `[docs]` only except the two marked:

| Step | Notes |
| --- | --- |
| `security.create_uuid` | `[workspace]` used, takes no property block: `security.create_uuid as $token` |
| `security.create_auth_token` | `[workspace]` used |
| `security.check_password` | `[workspace]` used |
| `security.generate_password` | |
| `security.random_number` | takes `min` and `max` |
| `security.random_bytes` | takes `length` |
| `security.create_secret_key` | |
| `security.create_rsa_key` | |
| `security.create_elliptic_curve_key` | |
| `security.encrypt` | takes `data`, `algorithm`, `key`, `iv` |
| `security.decrypt` | |
| JWS encode and decode | |
| JWE encode and decode | |

`[docs]` the encrypt form:

```
    security.encrypt {
      data = $sensitive_data
      algorithm = "aes-256-cbc"
      key = "encryption_key"
      iv = "init_vector"
    } as $encrypted_data
```

---

## 9. The magic link pattern, as actually implemented

Worth recording because it is the only non trivial security flow in the workspace and it composes primitives in a way that is not obvious.

1. `security.create_uuid` mints a token.
2. The token is stored into `password_reset.token`, which is declared as type `password`, so it is **hashed on write** by the field type.
3. An expiry timestamp and a `used` boolean are stored alongside it. `[workspace]` from `generate_magic_link.xs`:

```
    var $password_reset {
      value = {}
        |set:"token":$token
        |set:"expiration":(now
          |add_secs_to_timestamp:(3600|to_int)
        )
        |set:"used":false
    }
```

4. On redemption, the presented token is checked against the stored hash with `security.check_password`, then expiry and single use are enforced by preconditions. `[workspace]` from `magic_link_login_POST.xs`:

```
    security.check_password {
      text_password = $input.magic_token
      hash_password = $user.password_reset.token
    } as $verify_token

    precondition ($verify_token) {
      error_type = "unauthorized"
      error = "The token did not match"
    }

    precondition ($user.password_reset.expiration > now) {
      error = "Magic token has expired. Please request another one."
    }

    precondition ($user.password_reset.used == false) {
      error = "This magic link has already been used. Please request another one."
    }
```

5. Only then is an auth token minted and the record marked `used: true`.

The reusable idea: **the `password` field type is the hashed-secret-at-rest primitive**, not just a password column. Any single use token can be stored that way.

The gap: marking `used` happens in a separate `db.edit` after the check, with no transaction around it. Two simultaneous redemptions of the same link could both pass the `used == false` precondition. The same race applies to any check then set. See `gaps.md`, items 1 and 5.
