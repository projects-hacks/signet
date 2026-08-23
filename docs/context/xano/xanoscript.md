# XanoScript language reference

## How to read this file

Two sources are used, and every example says which one it came from.

- **`[workspace]`** means the syntax was copied verbatim out of a `.xs` file under `xano/` in this repo. Those files were pulled from a live Xano workspace, so they are proof the syntax parses and round trips.
- **`[docs]`** means the syntax was copied from the official documentation at `docs.xano.com`, page named inline. It is real published syntax but nothing in this repo exercises it.
- **"not documented"** means neither source says. It is not an invitation to guess.

The workspace evidence base is exactly 20 `.xs` files. That is small. Most of the language is `[docs]` only.

Where the two sources disagree, section 11 lists the conflicts. Read that section before writing a table.

---

## 1. Grammar basics

Established by every file under `xano/`.

- Every object is declared `<keyword> <name> [attr=value] { ... }`.
- Names are quoted only when they contain a space, slash, or hyphen. `api_group Authentication` in `xano/api/authentication/authentication.xs` is bare; `api_group "Event Logs"` in `xano/api/event_logs/event_logs.xs` is quoted.
- Block properties are `key = value`. Object literal members are `key: value`.
- Multi line arrays and objects use **no commas**. Single line ones do. Both appear in the same file.
- Structural blocks that hold no value take no `=`: `schema { }`, `input { }`, `stack { }`.
- `$` prefixes everything readable: `$input`, `$auth`, `$env`, `$db`, `$this`, and any `as $name` binding.
- `|` is the filter pipe. It is reused as a separator inside `filters=` and inside index `type` strings.
- `~` concatenates strings.
- `?` marks optional or nullable.
- `//` on the line above a declaration or a step is that object's description.
- `guid` closes an object block, `tags` sits just before it.

A leading `//` comment block is the object description. From `xano/table/user.xs`:

```
// Stores user information and allows the user to authenticate  against
table user {
```

---

## 2. Object kinds and where their files live

`[workspace]` file layout, confirmed against the CLI docs in `cli.md`:

| Keyword | File location | Seen in workspace |
| --- | --- | --- |
| `table` | `table/<name>.xs` | yes |
| `api_group` | `api/<group>/<group>.xs` | yes |
| `query` (an endpoint) | `api/<group>/<path>/<name>_<VERB>.xs` | yes |
| `function` | `function/<group>/<name>.xs` | yes |
| `addon` | `addon/<name>.xs` | yes |
| `workspace` | `workspace/<slug>.xs` | yes |
| `task` | `task/<name>.xs` | no, `[docs]` only |
| `middleware` | `middleware/<name>.xs` | no, `[docs]` only |
| `table_trigger` | `table/trigger/<name>.xs` | no, `[docs]` only |
| `workspace_trigger` | `workspace/trigger/<name>.xs` | no, `[docs]` only |

---

## 3. Table declaration

### 3.1 Complete real table

`[workspace]` the entire file `xano/table/user.xs`:

```
// Stores user information and allows the user to authenticate  against
table user {
  auth = true

  schema {
    int id
    timestamp created_at?=now
    text name filters=trim
    email? email filters=trim|lower
    password? password filters=min:8|minAlpha:1|minDigit:1

    // The role of the user within their company (e.g., 'admin', 'member').
    enum role? {
      values = ["admin", "member"]
    }

    object password_reset? {
      schema {
        password token?
        timestamp? expiration?
        bool used?
      }
    }
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
    {type: "btree|unique", field: [{name: "email", op: "asc"}]}
  ]

  tags = ["xano:quick-start"]
  guid = "bdjdLsrEUIvUNU_GlfnLIi814Og"
}
```

`[workspace]` the entire file `xano/table/event_log.xs`, showing a foreign key and a `json` column:

```
// Stores logs of user activities and events within the application.
table event_log {
  auth = false

  schema {
    int id
    timestamp created_at?=now

    // Reference to the user who performed the action.
    int user_id? {
      table = "user"
    }

    // A description of the action performed by the user (e.g., 'login', 'created_invoice', 'updated_profile').
    text action? filters=trim

    // Additional data related to the event, such as resource IDs, old/new values, or other contextual information.
    json metadata?
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]

  tags = ["xano:quick-start"]
  guid = "GYfh6Umz0wfiMzQrpeLmAcE96NA"
}
```

### 3.2 Schema rules

- One field per line, `<type> <name>`, no separator, inside `schema { }`.
- `auth = true` marks the table as an authentication source. `event_log` writes `auth = false` explicitly, so the property is not inferred.
- `[docs]` (`xanoscript/db`) the schema **must** begin with an id field, either `int id` or `uuid id`, and "Changing your primary key type after table creation is not supported."

### 3.3 Field modifiers

`[docs]` (`xanoscript/db`), the full modifier matrix:

| Form | Meaning |
| --- | --- |
| `text name` | required, not nullable |
| `text name?` | optional, not nullable |
| `text ?name?` | required, nullable |
| `text ?name` | required and nullable |
| `text name?=defaultValue` | optional with a default |

`[workspace]` all four positions are used in `xano/table/user.xs`: `created_at?=now` is a default written as a bare keyword rather than a string, `email? email` puts the `?` on the type, and `timestamp? expiration?` inside `password_reset` uses both positions at once.

### 3.4 Field types

`[docs]` (`xanoscript/field-type-reference`) the full list: `int`, `text`, `bool`, `timestamp`, `decimal`, `enum`, `uuid`, `object`, `json`, `vector`, `date`, `email`, `password`, `image`, `video`, `audio`, `attachment`, `geo_point`, `geo_point_collection`, `geo_path`, `geo_path_collection`, `geo_polygon`, `geo_polygon_collection`.

`[workspace]` only these appear: `int`, `timestamp`, `text`, `email`, `password`, `bool`, `json`, `enum`, `object`.

Array types are written with `[]` on the type. `[docs]` (`xanoscript/db`):

```
int[] users_photos? {
  table = "photo"
}
```

`enum` takes a nested block. `[workspace]` from `xano/table/user.xs`:

```
    enum role? {
      values = ["admin", "member"]
    }
```

A structured column nests another `schema` block. `[workspace]` from `xano/table/user.xs`:

```
    object password_reset? {
      schema {
        password token?
        timestamp? expiration?
        bool used?
      }
    }
```

Its subfields are then addressed with dots elsewhere, for example `$user.password_reset.token`.

### 3.5 Foreign keys

`[workspace]` from `xano/table/event_log.xs`. A typed field with a nested block naming the table. There is no relation keyword and no cascade rule:

```
    int user_id? {
      table = "user"
    }
```

See section 11: the field type reference page uses `dbtable` for this, not `table`. The workspace uses `table`.

### 3.6 Indexes and uniqueness

Indexes are **not** per field. They are one top level `index = [ ... ]` array. Elements are newline separated with no commas.

`[workspace]` from `xano/table/user.xs`, and character for character the same block appears in `[docs]` (`xanoscript/db`):

```
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
    {type: "btree|unique", field: [{name: "email", op: "asc"}]}
  ]
```

`[docs]` index types: `primary`, `btree`, `gin`, and `unique`. Uniqueness is expressed by piping it onto the base type, `"btree|unique"`, not as a separate flag.

`op` is the sort direction, `"asc"` or `"desc"`. `{name: "id"}` shows `op` is optional.

Composite indexes are supported. `[docs]` (`xanoscript/db`):

```
{
  type : "btree"
  field: [{name: "name", op: "asc"}, {name: "email", op: "asc"}]
}
```

Every index in the workspace is single column, so composite index syntax is `[docs]` only.

**What a conflicting insert returns is not documented.** See `gaps.md`, item 1.

### 3.7 Views

`[docs]` (`xanoscript/db`) only, no example in the workspace:

```
views = {
  sanitized_user_info: {
    alias: "sql_userinfo"
    hide : ["password", "id"]
    sort : {id: "asc"}
    id   : "1dca1ee2-9997-4fed-9d03-276bd6d68593"
  }
}
```

---

## 4. API endpoint declaration

### 4.1 API group

`[workspace]` the entire file `xano/api/authentication/authentication.xs`. The group carries no routing information; endpoints point back at it by display name:

```
// This group provides endpoints for user login, signup, and reset password, returning authentication tokens and user records.
api_group Authentication {
  canonical = "q5SKyUsy"
  tags = ["xano:quick-start"]
  guid = "J9rdjDgp5B8f45r-duw46ee9G6U"
}
```

`canonical` is an 8 character opaque string. It appears only on `api_group` in this workspace. `guid` is a 27 character URL safe string and appears on nearly every object; it is what the CLI uses to match a local file to a remote object (see `cli.md`).

### 4.2 Endpoint

`[workspace]` the entire file `xano/api/event_logs/logs/user/my_events_GET.xs`, the smallest complete endpoint in the workspace:

```
// Pull all event logs for the authenticated user
query "logs/user/my_events" verb=GET {
  api_group = "Event Logs"
  auth = "user"

  input {
  }

  stack {
    // Retrieve event logs for the authenticated user
    db.query event_log {
      where = $db.event_log.user_id == $auth.id
      return = {type: "list"}
    } as $user_events
  }

  response = $user_events
  tags = ["xano:quick-start"]
  guid = "j8x8brYsq1xNu6zp44DEPlntFlI"
}
```

Structure: declaration line carries the path and `verb=`. Then `api_group`, optional `auth`, `input { }`, `stack { }`, `response =`, then settings.

`[workspace]` verbs seen: `POST` and `GET` only. `[docs]` (`xanoscript/api`) lists "`GET`, `POST`, `PUT`, etc." Paths are relative to the group with no leading slash: `"auth/login"`, `"reset/magic-link-login"`, `"logs/user/my_events"`. Path parameters such as `{id}` do not appear in the workspace; `[docs]` (`troubleshooting-and-support/error-reference`) references an endpoint named `/auth/{user_id}`, so the `{name}` form exists, but no full declaration example was found.

### 4.3 Inputs

`input { }` uses the same field grammar as a table schema, `filters=` included.

`[workspace]` from `xano/api/authentication/auth/signup_POST.xs`:

```
  input {
    text name?
    email email? filters=trim|lower
    text password?
  }
```

`[workspace]` a filter with an argument, from `xano/api/authentication/reset/update_password_POST.xs`:

```
  input {
    text password? filters=trim|min:8
    text confirm_password? filters=trim
  }
```

`[workspace]` a required input with a description, from `xano/api/authentication/message/send_welcome_email_POST.xs`:

```
  input {
    // The ID of the user to send the welcome email to.
    int user_id
  }
```

An endpoint with no inputs still writes the empty block. `[workspace]` from `me_GET.xs` and `my_events_GET.xs`:

```
  input {
  }
```

Inputs are read as `$input.<name>`.

### 4.4 Auth on an endpoint

`[workspace]` from `xano/api/authentication/auth/me_GET.xs`. `auth = "user"` names the auth table and sits directly under `api_group`:

```
query "auth/me" verb=GET {
  api_group = "Authentication"
  auth = "user"
```

Endpoints that omit the property are public. No `query` in the workspace writes `auth = false`. Full treatment in `auth-and-security.md`.

### 4.5 Response

`response =` sits after `stack` and before `tags`. It is a value expression only. There is no response schema and no status code declaration anywhere in either source.

`[workspace]` four forms appear.

A bare variable, from `me_GET.xs`:

```
  response = $user
```

An inline object, from `login_POST.xs`:

```
  response = {authToken: $authToken, user_id: $user.id}
```

An object built with filters, from `request_reset_link_GET.xs`:

```
  response = {
    message: {}|set:"success":true|set:"message":"magic link sent"
  }
```

`null`, from `log_event.xs` and `enforce_role.xs`:

```
  response = null
```

### 4.6 Endpoint settings

`[docs]` (`xanoscript/api`) root level settings after the response block: `description`, `auth`, `tags`, `history`, and `cache`. The `cache` object takes `ttl` (seconds, `0` disables), `input`, `auth`, `datasource`, `ip`, `headers`, and `env`. No workspace file sets `cache` or `history`.

---

## 5. Custom functions

`[workspace]` the entire file `xano/function/quick_start/log_event.xs`. Functions use a two part `"Group/name"` and are called by that same string:

```
// Creates a record in the event log table
function "Quick Start/log_event" {
  input {
    // Unique identifier for the user who performed the action.
    int user_id

    // A description of the action performed by the user (e.g., 'login', 'created_invoice').
    text action

    // Additional data related to the event, such as resource IDs or old/new values.
    json metadata?
  }

  stack {
    // Add a new user event log entry
    db.add event_log {
      data = {
        created_at: "now"
        user_id   : $input.user_id
        action    : $input.action
        metadata  : $input.metadata
      }
    } as $new_log_entry
  }

  response = null
  tags = ["xano:quick-start"]
  guid = "jn_Y3HPwcYAGPg4QY5kl-1xl-Lg"
}
```

Calling it, `[workspace]` from `xano/api/authentication/auth/login_POST.xs`:

```
    function.run "Quick Start/log_event" {
      input = {user_id: $user.id, action: "login", metadata: $user}
    } as $event_log
```

The same call multi line, `[workspace]` from `me_GET.xs`. Note the exporter pads keys to align the colons, and multi line objects carry no commas:

```
    function.run "Quick Start/log_event" {
      input = {
        user_id : $user.id
        action  : "get_auth_user"
        metadata: $user
      }
    } as $event_log
```

`[docs]` (`xanoscript/function-reference/custom-functions`): if the function uses `precondition` or input filters, invalid inputs throw an error, and those errors can be handled with `try_catch`.

---

## 6. Function stacks

### 6.1 Step sequencing

`stack { }` holds an ordered list of steps. No commas, no semicolons, no step numbers. Each step is:

```
<step_type> [target] { <properties> } as $<binding>
```

The `as $name` clause binds the result. It can be omitted when the result is unused. `[workspace]` `xano/addon/user.xs` shows a `db.query` with no binding:

```
  stack {
    db.query user {
      where = $db.user.id == $input.user_id
      return = {type: "single"}
    }
  }
```

Some steps take no property block at all. `[workspace]` from `generate_magic_link.xs`:

```
    security.create_uuid as $token
```

A variable can be rebound by a later step. `[workspace]` in `update_password_POST.xs`, `$user` is bound by `db.get` then rebound by `db.edit`.

### 6.2 Step types seen in the workspace

`db.get`, `db.query`, `db.add`, `db.edit`, `var`, `precondition`, `conditional` with `if` and `throw`, `function.run`, `security.check_password`, `security.create_auth_token`, `security.create_uuid`, `util.send_email`, `util.template_engine`.

Everything else in this file is `[docs]` only.

### 6.3 Variables

`var $name { value = ... }` is the only assignment form. `[workspace]` from `xano/function/quick_start/enforce_role.xs`:

```
    var $role_hierarchy {
      value = {admin: 2, member: 1}
    }
```

`[docs]` (`xanoscript/tasks`) a `var` step can also carry a `description`:

```
        var $transaction_count {
          value = $daily_sales|count
          description = "Count number of transactions"
        }
```

String concatenation with `~`. `[workspace]` from `send_welcome_email_POST.xs`:

```
    var $email_subject {
      value = "Welcome to Our Service, " ~ $user_record.name ~ "!"
    }
```

Dot notation reaches into objects and arrays. `[docs]` (`xanoscript/key-concepts`): `$x1.a` for an object key, `$x1.1` for the second array element.

### 6.4 Magic variables

`[docs]` (`xanoscript/key-concepts`) reserved names, which must not be shadowed:

| Reserved | Holds |
| --- | --- |
| `$input` | API or function input parameters |
| `$auth` | authenticated user context |
| `$env` | environment variables |
| `$db` | database field references, inside `where` clauses |
| `$this` | current item in loops and maps |
| `$var` | the stack variable namespace |
| `$response` | the API or function response |
| `$output` | function output |
| `$error` | error context, inside `try_catch` |

`[workspace]` confirms `$input`, `$auth`, `$env`, `$db`, and `$var` (the latter only inside a template string).

---

## 7. Database operations

### 7.1 `db.get`, fetch one record by one field

`[workspace]` from `login_POST.xs`:

```
    db.get user {
      field_name = "email"
      field_value = $input.email
      output = ["id", "created_at", "name", "email", "password", "role"]
    } as $user
```

`output` is optional; omitting it returns the whole record. `output` can select nested subfields with dotted paths, and a long list is written one entry per line with no commas. `[workspace]` from `magic_link_login_POST.xs`:

```
      output = [
        "id"
        "created_at"
        "name"
        "email"
        "role"
        "password_reset.token"
        "password_reset.expiration"
        "password_reset.used"
      ]
```

`db.get` returns `null` when nothing matches. That is the basis of every existence check in the workspace, for example `precondition ($user == null)` in `signup_POST.xs`.

### 7.2 `db.query`, filter with a `where` expression

`[workspace]` list form, from `my_events_GET.xs`:

```
    db.query event_log {
      where = $db.event_log.user_id == $auth.id
      return = {type: "list"}
    } as $user_events
```

`[workspace]` single form, from `generate_magic_link.xs`:

```
    db.query user {
      where = $db.user.email == $input.email
      return = {type: "single"}
    } as $user
```

Inside `where`, the left hand side is always `$db.<table>.<field>`. That prefix is how a column is distinguished from a variable.

**Compound conditions.** `[docs]` (`xanoscript/function-reference/database-operations`) uses `&&`, `||`, and parentheses:

```
  where = $db.user.name == $input.name && $db.user.created_at > 1 || $db.user.id == 1 && ($db.user.role == "member" && true) || ($db.user.role == "admin" && true)
```

A simpler documented one:

```
  db.query user {
    where = $db.user.id == $input.userId && $db.user.userRole == "admin"
    return = {type: "exists"}
  } as user1
```

Operator precedence between `&&` and `||` is **not documented**. Parenthesize.

**Sorting.** `[docs]`:

```
    db.query user {
      where = $db.user.id == 1
      sort = {user.name: "asc"}
    } as $user1
```

**Return types.** `[docs]` five values for `return.type`: `exists` (boolean), `count` (number), `single` (first record), `list` (array), `stream` (records for efficient iteration).

**Paging.** `[docs]`, configured inside the return object:

```
return = {
  type: "list",
  paging: {
    page: 1,
    per_page: 25,
    totals: true,
    offset: 0,
    metadata: true
  }
}
```

When paging is on, the result is an envelope rather than a bare array. `[docs]` shows these `output` paths: `itemsReceived`, `curPage`, `nextPage`, `prevPage`, `offset`, `itemsTotal`, `pageTotal`, and the records under `items.*`.

**Joins.** `[docs]`:

```
    db.query user {
      where = $db.user.id == 1
      join = {
        event_log: {
          table: "event_log"
          where: $db.user.id == $db.event_log.user_id
        }
      }
    } as $user1
```

**Computed fields.** `[docs]`, `eval`:

```
    db.query user {
      where = $db.user.id == 1
      eval = {user_action: $db.event_log.action}
    } as $user1
```

### 7.3 `db.add`

`[workspace]` from `signup_POST.xs`. The result is the created record, since `$user.id` is read immediately after:

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

Note `created_at: "now"` is a quoted string in a `data` payload, while the same `now` is a bare keyword as a table default and as a comparison operand.

### 7.4 `db.edit`, full record write

`[workspace]` from `update_password_POST.xs`:

```
    db.edit user {
      field_name = "id"
      field_value = $auth.id
      data = {password: $input.password}
    } as $user
```

`[workspace]` with a filter expression as the selector, from `generate_magic_link.xs`:

```
    db.edit user {
      field_name = "id"
      field_value = $user|get:"id":0
      data = {password_reset: $password_reset}
    } as $updated_password_reset
```

### 7.5 `db.patch`, partial write

`[docs]` only:

```
db.patch user {
    field_name = "id"
    field_value = $input.id
    data = {}|set:"name":$input.name
} as $patchRecord
```

### 7.6 `db.add_or_edit`, upsert by one field

`[docs]` only. This is the documented alternative to a check then insert:

```
db.add_or_edit user {
    field_name = "id"
    field_value = $input.id
    data = {name: $input.name}
} as $recordAddOrEdit
```

Whether it is atomic against a concurrent insert is **not documented**.

### 7.7 `db.del`

`[docs]` only. Note the name is `db.del`, not `db.delete`:

```
db.del user {
    field_name = "id"
    field_value = $input.id
}
```

### 7.8 `db.transaction`

`[docs]` only. It wraps a nested `stack`:

```
  db.transaction {
    stack {
      db.add user {
        data = {
          created_at: "now"
          name      : ""
          email     : null
          password  : null
        }
       } as $user1
    }
  }
```

Rollback semantics, isolation level, and what happens on a partial failure are **not documented**. See `gaps.md`, item 5.

### 7.9 `db.direct_query`, raw SQL

`[docs]` only. Two parameterization modes:

```
db.direct_query {
  sql = "SELECT * FROM x52_245;"
  parser = "template_engine"
  response_type = "list"
} as $x1
```

Template engine mode, with an escaping filter:

```
  db.direct_query {
    sql = "SELECT * FROM x52_245 WHERE id = {{ $auth.id|sql_esc }};"
    parser = "template_engine"
    response_type = "single"
  } as $x2
```

Prepared statement mode, omitting `parser`:

```
  db.direct_query {
    sql = "SELECT * FROM x52_245 WHERE id = ?;"
    response_type = "list"
    arg = $auth.id
  } as $x1
```

Note the physical table name is mangled (`x52_245`), so raw SQL is coupled to internal naming.

### 7.10 `db.truncate`

`[docs]` only:

```
db.truncate table_name {
  reset = false
}
```

---

## 8. Control flow

### 8.1 `precondition`, the dominant guard

Asserts the expression is truthy and aborts otherwise.

`[workspace]` from `login_POST.xs`:

```
    precondition ($user != null) {
      error_type = "accessdenied"
      error = "Invalid Credentials."
    }
```

Both properties are individually optional. `[workspace]` `error` only, from `magic_link_login_POST.xs`:

```
    precondition ($input.magic_token != null) {
      error = "magic_token is required but was not provided."
    }
```

`[workspace]` `error_type` only, from `update_password_POST.xs`:

```
    precondition ($user.id == $auth.id) {
      error_type = "accessdenied"
    }
```

`error_type` values observed across both sources: `"accessdenied"`, `"notfound"`, `"unauthorized"`, `"inputerror"`. The complete enumeration is **not documented**, and neither source maps an `error_type` to an HTTP status code.

Operators seen in conditions: `==`, `!=`, `>`, `<`. A bare variable is a valid condition, as in `precondition ($pass_result)` in `login_POST.xs`. `now` works as a bare operand. `[workspace]` from `magic_link_login_POST.xs`:

```
    precondition ($user.password_reset.expiration > now) {
      error = "Magic token has expired. Please request another one."
    }
```

### 8.2 `conditional`

`[workspace]` the only instance in the workspace, from `enforce_role.xs`:

```
    conditional {
      if ($user_role_level < $required_role_level) {
        throw {
          name = "accessdenied"
          value = "User does not have the required role to perform this action. Required: " ~ $input.required_role ~ ", Actual: " ~ $user_role
        }
      }
    }
```

`else` and `else if` are **not documented** in either source. That single block is the entire evidence for branching.

`[docs]` (`xanoscript/function-reference/data-manipulation/loops`) writes conditions inside backticks, `if (\`$index == 5\`)`. The workspace does not. See section 11.

### 8.3 Loops

`[docs]` only. `foreach` over a list:

```
foreach ($list) {
  each as alias {
    // XanoScript statements go here
  }
}
```

A real documented use, `[docs]` from `xanoscript/tasks`, iterating query results:

```
    foreach ($user1) {
      each as $item {
        util.send_email {
          service_provider = "resend"
          to = $item.email
        } as $x1
      }
    }
```

Fixed count `for`:

```
for (`$loops`) {
  each as index {
    // XanoScript statements go here
  }
}
```

`while`:

```
while (`conditions`) {
  each {
    // XanoScript statements go here
  }
}
```

`break` and `continue` are bare statements and `[docs]` states they work in all three loop types:

```
  for (`10`) {
    each as index {
      conditional {
        if (`$index == 5`) {
          break
        }
      }
    }
  }
```

Loops nest. `[docs]`:

```
foreach ($matrix) {
  each as row {
    foreach (row) {
      each as value {
        debug.log {
          value = value
        }
      }
    }
  }
}
```

Note the `[docs]` examples are inconsistent about whether the alias carries a `$`: `each as $item` in the tasks page, `each as item` and a bare `row` reference in the loops page. Which is correct is **not documented**.

### 8.4 `try_catch`

`[docs]` only (`xanoscript/function-reference/utility-functions`):

```
try_catch {
  try {
    // statements that may throw
    function.run risky_function { input = { foo: "bar" } } as $result
  }
  catch {
    debug.log { value = $error }
  }
  finally {
    debug.log { value = "Cleanup actions" }
  }
}
```

`finally` is optional. The error is read from `$error`. The shape of `$error` is **not documented**, so you cannot rely on matching a specific database error inside `catch`.

### 8.5 `throw`

`[docs]`, standalone:

```
throw {
  name = "inputerror"
  value = "A custom error message"
}
```

`throw` uses `name` and `value`, whereas `precondition` uses `error_type` and `error`. The vocabularies match (`accessdenied`, `inputerror`) but the property names differ. Both forms are confirmed by the workspace and the docs.

---

## 9. Outbound requests and other steps

### 9.1 `api.request`, outbound HTTP

`[docs]` only (`xanoscript/function-reference/apis-and-lambdas`):

```
api.request {
  url = "https://www.myapi.com/myApiEndpoint"
  method = "GET"
  params = {}|set:"a":1
  headers = []|array_push:"Authorization: Bearer abc123"
} as api1
```

`method` accepts `"GET"`, `"POST"`, `"PUT"`, `"DELETE"`. `params` carries query parameters or body data. `headers` is an array of raw header strings built with `array_push`. A documented POST:

```
  api.request {
    url = "https://api.example.com/users"
    method = "POST"
    params = {}|set:"name":"John"|set:"age":30
    headers = []|array_push:"Content-Type: application/json"
  } as createUser
```

The response shape of `api.request` (status code, headers, body, and how a non 2xx is surfaced) is **not documented**. See `gaps.md`, item 4.

`[docs]` also documents `stream.from_request` for streaming responses, with `timeout`, `follow_location`, `verify_host`, `verify_peer`, and client certificate parameters.

### 9.2 `api.lambda`, inline JavaScript

`[docs]` only:

```
api.lambda {
  code = "return true;"
  timeout = 10
} as x2
```

### 9.3 `util.send_email`

`[workspace]` from `send_welcome_email_POST.xs`. Note there is no `to` property in either workspace call:

```
    util.send_email {
      service_provider = "xano"
      subject = $email_subject
      message = $email_body
    } as $send_email
```

`[docs]` (`xanoscript/tasks`) the full parameter set:

```
        util.send_email {
          api_key = "abc123"
          service_provider = "resend"
          subject = "Hey, where'd you go?"
          message = "We noticed you haven't logged in for a while. Come back and give us another shot?"
          to = $item.email
          bcc = []
          cc = []
          from = "admin@myapp.com"
          reply_to = ""
          scheduled_at = ""
        } as $x1
```

### 9.4 `util.template_engine`

`[workspace]` from `request_reset_link_GET.xs`, abridged. Triple quoted heredoc, `{{ }}` interpolation, and inside a template the prefix is `$var.` rather than a bare `$`:

```
    util.template_engine {
      value = """
        <!DOCTYPE html>
        <html>
        <body>
            <p style="text-align: center; margin: 30px 0;">
              <a href="{{ $var.magic_link }}">
                Reset Your Password
              </a>
            </p>
        </body>
        </html>
        """
    } as $message
```

### 9.5 `debug.log`

`[docs]` only:

```
        debug.log {
          value = "Daily sales report generated"
          description = "Log report generation"
        }
```

### 9.6 `post_process`

`[docs]` only, runs after the response is sent:

```
post_process {
  stack {
    debug.log { value = "Post-processing after response" }
  }
}
```

---

## 10. Filters

Filters are pipe expressions, `value|filter:arg` or `value|filter:arg1:arg2`. They chain, and when chained across lines each continuation line begins with the pipe.

`[workspace]` filters starting from an empty object literal, with a nested parenthesized filter expression, from `generate_magic_link.xs`:

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

`[workspace]` a multi line `concat` chain from `request_reset_link_GET.xs`. The second argument is the separator placed **before** the concatenated value:

```
    var $magic_link {
      value = $api_base_url
        |concat:"1_start_here_demo_page#/update-password":"/"
        |concat:$token_and_email.token:"?magic_token="
        |concat:$token_and_email.email:""
    }
```

`[workspace]` `get` with a default, from `generate_magic_link.xs`:

```
      field_value = $user|get:"id":0
```

Filters seen in the workspace: `get`, `set`, `concat`, `add_secs_to_timestamp`, `to_int`, `json_encode`, plus the schema level `trim`, `lower`, `min`, `minAlpha`, `minDigit`.

Filters seen only in `[docs]`: `count`, `sum`, `array_push`, `add`, `split`, `first`, `timestamp_subtract_months`, `transform_timestamp`, `sql_esc`, `json_decode`.

`[docs]` (`xanoscript/db`) the schema level `filters=` vocabulary is a distinct, smaller set:

- Validation: `min:n`, `max:n`, `minAlpha:n`, `minDigit:n`, `pattern:regex`
- Transformation: `trim`, `lower`, `upper`
- Character whitelists: `alphaOk`, `digitOk`, `ok:chars`
- Restriction: `startsWith:prefix`, `prevent:blacklist`

The full runtime filter catalogue lives on seven separate `docs.xano.com/xanoscript/filter-reference/*` pages (manipulation, math, timestamp, text, array, transform, comparison, security) which were not exhaustively transcribed here.

---

## 11. Where the two sources disagree

These are real conflicts. When in doubt, trust the workspace, because those files were produced by Xano itself and round trip through the CLI.

**1. Foreign key property name.** The workspace writes `table`, `xano/table/event_log.xs`:

```
    int user_id? {
      table = "user"
    }
```

The field type reference page writes `dbtable`: "For Table References: `int field_name? { dbtable = "table_name" }`". A different docs page (`xanoscript/db`) agrees with the workspace and lists `table` as the field property. Two of three say `table`.

**2. Nested object schema.** The workspace nests a real `schema` block with typed field lines, `xano/table/user.xs`:

```
    object password_reset? {
      schema {
        password token?
        timestamp? expiration?
        bool used?
      }
    }
```

The field type reference page instead shows `schema` as an assigned object of quoted type names:

```
  object settings {
    schema = {
      theme: "string",
      notifications: "boolean"
    }
  }
```

These are structurally incompatible. The workspace form is the one known to round trip.

**3. Query filter keyword.** `xanoscript/function-reference/database-operations` and the workspace both use `where`. The background task pages (`xanoscript/tasks` and `building/logic/background-tasks`) use `search` in their `db.query` examples:

```
        db.query user {
          search = $db.user.last_login <= ("now"|timestamp_subtract_months:1)
        } as $user1
```

Whether `search` is a synonym, a legacy spelling, or a different feature is not stated.

**4. Backticked conditions.** The loops page writes conditions inside backticks, `if (\`$index == 5\`)` and `while (\`true == true\`)`. The workspace writes them bare, `if ($user_role_level < $required_role_level)`. The conditionals reference page uses the bare form.

**5. Quoted endpoint path.** The workspace always quotes: `query "auth/signup" verb=POST`. `xanoscript/api` shows it unquoted in its detailed example: `query auth/signup verb=POST`.

**6. Endpoint filename casing.** The CLI docs say endpoint files are named `{name}_{verb}.xs` and that "All filenames are converted to snake_case", and that the group file is `api_group.xs`. The actual pull produced `login_POST.xs` with an uppercase verb, and named the group file after the group (`authentication.xs`), not `api_group.xs`. See `cli.md`.

**7. Loop alias sigil.** `each as $item` on the tasks page, `each as item` on the loops page.
