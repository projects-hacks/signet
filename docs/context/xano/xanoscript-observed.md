# XanoScript as observed in this workspace

Everything below is copied verbatim from the `.xs` files under `xano/` in this repo. Those files were pulled from a live Xano workspace, so they are ground truth for syntax. Nothing here is invented. Where the workspace contains no example of a feature, the heading says "not observed in this workspace".

The whole workspace is 20 `.xs` files. That is the entire evidence base.

## 1. Directory layout and file naming

```
xano/addon/user.xs
xano/ai/agent/xano_example_agent.xs
xano/ai/tool/search_xano_docs.xs
xano/api/authentication/authentication.xs
xano/api/authentication/auth/login_POST.xs
xano/api/authentication/auth/me_GET.xs
xano/api/authentication/auth/signup_POST.xs
xano/api/authentication/message/send_welcome_email_POST.xs
xano/api/authentication/reset/magic_link_login_POST.xs
xano/api/authentication/reset/request_reset_link_GET.xs
xano/api/authentication/reset/update_password_POST.xs
xano/api/event_logs/event_logs.xs
xano/api/event_logs/logs/user/my_events_GET.xs
xano/api/signet/signet.xs
xano/function/quick_start/enforce_role.xs
xano/function/quick_start/generate_magic_link.xs
xano/function/quick_start/log_event.xs
xano/table/event_log.xs
xano/table/user.xs
xano/workspace/rajeev_workspace_1.xs
```

Naming rules visible in that listing:

- One object per file, one file per object. Every file is `.xs`.
- `xano/table/<table_name>.xs` is flat. The filename is the table name.
- `xano/api/<group_slug>/<group_slug>.xs` is the API group declaration itself. The same directory then holds the endpoints, nested by the path segments of the endpoint. `query "logs/user/my_events"` lives at `xano/api/event_logs/logs/user/my_events_GET.xs`, so path segments become directories and the last segment becomes the filename.
- Endpoint filenames carry the verb as an uppercase suffix: `login_POST.xs`, `me_GET.xs`, `request_reset_link_GET.xs`.
- Non identifier characters in a name are normalized to underscores for the filename while the declaration keeps the original. `xano/api/event_logs/event_logs.xs` declares `api_group "Event Logs"`. `xano/api/authentication/reset/magic_link_login_POST.xs` declares `query "reset/magic-link-login"`, so the hyphen in the route became an underscore in the filename.
- `xano/function/<group_slug>/<function_name>.xs` mirrors the function's two part name. `function "Quick Start/log_event"` lives at `xano/function/quick_start/log_event.xs`.
- `xano/ai/` is split into `agent/` and `tool/` subdirectories.
- `xano/addon/<name>.xs` is flat.
- `xano/workspace/<workspace_slug>.xs` is a single file for the workspace itself.
- `xano/authentication/` and `xano/event_logs/` as top level directories: not observed in this workspace. The only authentication and event log material lives under `xano/api/`.

### What the top of each file kind looks like

Every declaration is `<keyword> <name> { ... }`. A name that is a bare identifier is unquoted; a name containing spaces, slashes, or hyphens is double quoted. Leading `//` comments above the declaration are the object's description.

Table, from `xano/table/user.xs`:

```
// Stores user information and allows the user to authenticate  against
table user {
  auth = true
```

API group, from `xano/api/event_logs/event_logs.xs`:

```
// Contains API Endpoints for reports of event logs
api_group "Event Logs" {
  canonical = "U-gPAk4Q"
  tags = ["xano:quick-start"]
  guid = "B6rZTRksJtAi1a4eaH2EQLxyl4s"
}
```

API endpoint, from `xano/api/authentication/auth/login_POST.xs`:

```
// Login and retrieve an authentication token
query "auth/login" verb=POST {
  api_group = "Authentication"
```

Function, from `xano/function/quick_start/log_event.xs`:

```
// Creates a record in the event log table
function "Quick Start/log_event" {
  input {
```

Workspace, the complete file `xano/workspace/rajeev_workspace_1.xs`:

```
workspace "Rajeev Workspace #1" {
  acceptance = {ai_terms: true}
  preferences = {
    internal_docs    : false
    track_performance: true
    sql_names        : false
    sql_columns      : true
  }
}
```

Addon, from `xano/addon/user.xs`:

```
addon user {
  input {
    int user_id? {
      table = "user"
    }
  }
```

Agent, from `xano/ai/agent/xano_example_agent.xs`:

```
agent "Xano Example Agent" {
  canonical = "fcvU0I0j"
  tags = ["xano:quick-start"]
  llm = {
```

Tool, from `xano/ai/tool/search_xano_docs.xs`:

```
tool search_xano_docs {
  instructions = "This allows you to search the Xano Documentation and input a search query. It will return a pages of the Xano Documentation based on the search query. This can be used to answer and analyze questions around Xano and how to use it."
```

## 2. `canonical` and `guid` identifiers

`canonical` appears on exactly two object kinds in this workspace: `api_group` and `agent`. It is a short opaque string, 8 characters in every observed case.

- `xano/api/authentication/authentication.xs`: `canonical = "q5SKyUsy"`
- `xano/api/event_logs/event_logs.xs`: `canonical = "U-gPAk4Q"`
- `xano/api/signet/signet.xs`: `canonical = "P8WKBRmD"`
- `xano/ai/agent/xano_example_agent.xs`: `canonical = "fcvU0I0j"`

No `query`, `function`, `table`, `addon`, `tool`, or `workspace` file in this workspace carries a `canonical`. Endpoints instead reference their group by display name, `api_group = "Authentication"` in `xano/api/authentication/auth/login_POST.xs`, not by canonical.

`guid` is separate and much more widely used. It is a 27 character URL safe base64 style string and it closes the block, always as the last property. Observed values:

- `xano/table/user.xs`: `guid = "bdjdLsrEUIvUNU_GlfnLIi814Og"`
- `xano/table/event_log.xs`: `guid = "GYfh6Umz0wfiMzQrpeLmAcE96NA"`
- `xano/addon/user.xs`: `guid = "XeuPO--9RWSRMdcttH8RHn1H3_Q"`
- `xano/api/authentication/auth/login_POST.xs`: `guid = "xoxkeQtmfHR9nVDoCp3sxJqvu2w"`
- `xano/function/quick_start/log_event.xs`: `guid = "jn_Y3HPwcYAGPg4QY5kl-1xl-Lg"`
- `xano/ai/tool/search_xano_docs.xs`: `guid = "VJX9gnmceM6B6vEP34SdYvE1vxw"`

`xano/workspace/rajeev_workspace_1.xs` is the only file with neither a `canonical` nor a `guid`. `xano/api/signet/signet.xs` is the only file with a `canonical` and `guid` but no `tags` and no description comment, and it is the only API group with no endpoints on disk.

`tags` is a string array and every generated object carries the same one: `tags = ["xano:quick-start"]`.

## 3. Table declaration

The complete file `xano/table/user.xs`:

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

The complete file `xano/table/event_log.xs`:

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

What these two files establish:

- A field line is `<type> <name>` with no separator, inside a `schema { }` block. No commas, no semicolons, one field per line.
- `auth = true` on a table marks it as the authentication source. `event_log` has `auth = false`, so the property is written explicitly either way.
- Field types seen: `int`, `timestamp`, `text`, `email`, `password`, `bool`, `json`, `enum`, `object`.
- A trailing `?` on the field name marks it optional or nullable: `created_at?`, `user_id?`, `action?`, `metadata?`, `role?`, `password_reset?`, `token?`, `used?`.
- A `?` can also appear on the type itself, and both positions can be used at once. From `user`: `email? email filters=trim|lower`, `password? password filters=min:8|minAlpha:1|minDigit:1`, and inside the nested object `timestamp? expiration?`.
- A default is written with `=` directly after the name: `timestamp created_at?=now`. `now` is a bare keyword, not a string, in this position.
- `filters=` attaches a pipe separated validation and coercion chain to a field: `filters=trim`, `filters=trim|lower`, `filters=min:8|minAlpha:1|minDigit:1`. Filter arguments use a colon.
- A foreign key is a typed field with a nested block naming the table: `int user_id? { table = "user" }`. No explicit relation keyword, no cascade rules.
- `enum` takes a nested block with `values = [...]`.
- `object` nests a further `schema { }`, giving a structured column. `password_reset` is that pattern and its subfields are addressed with dots elsewhere, for example `$user.password_reset.token`.
- Comments describing a field go on their own line immediately above it, inside the schema block.

### Indexes and uniqueness

Indexes are not per field. They are a single top level `index = [ ... ]` array of objects, and the array elements are newline separated with no commas between them:

```
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
    {type: "btree|unique", field: [{name: "email", op: "asc"}]}
  ]
```

Uniqueness is expressed by piping into the type string, `type: "btree|unique"`, not by a separate flag. `field` is itself an array, so composite indexes are structurally possible, though every index in this workspace is single column. `op` carries the sort direction, `"asc"` or `"desc"`. `{name: "id"}` shows `op` is optional.

Table level properties observed: `auth`, `schema`, `index`, `tags`, `guid`. No `canonical` on a table.

## 4. API endpoint declaration

### Group

An API group is its own tiny file. Full text of `xano/api/authentication/authentication.xs`:

```
// This group provides endpoints for user login, signup, and reset password, returning authentication tokens and user records.
api_group Authentication {
  canonical = "q5SKyUsy"
  tags = ["xano:quick-start"]
  guid = "J9rdjDgp5B8f45r-duw46ee9G6U"
}
```

Note the name here is a bare unquoted identifier, while `api_group "Event Logs"` is quoted because of the space. The group holds no routing information itself; endpoints point back at it.

### Endpoint

Verb and path live on the declaration line, `verb=` is unquoted. Group membership, auth, inputs, the step stack, and the response are properties of the block. Complete file `xano/api/event_logs/logs/user/my_events_GET.xs`, the smallest full endpoint in the workspace:

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

Verbs observed: `verb=POST` and `verb=GET` only. `PUT`, `PATCH`, `DELETE`: not observed in this workspace.

Paths are quoted and relative to the group, with no leading slash: `"auth/login"`, `"auth/me"`, `"auth/signup"`, `"message/send_welcome_email"`, `"reset/magic-link-login"`, `"reset/request-reset-link"`, `"reset/update_password"`, `"logs/user/my_events"`. Both underscores and hyphens appear in paths. Path parameters such as `{id}`: not observed in this workspace.

### Inputs

`input { }` declares the request shape using the same field grammar as a table schema, including `filters=`:

From `xano/api/authentication/auth/signup_POST.xs`:

```
  input {
    text name?
    email email? filters=trim|lower
    text password?
  }
```

From `xano/api/authentication/reset/update_password_POST.xs`, showing a filter with an argument:

```
  input {
    text password? filters=trim|min:8
    text confirm_password? filters=trim
  }
```

From `xano/api/authentication/message/send_welcome_email_POST.xs`, showing a required input with no `?` and a description comment:

```
  input {
    // The ID of the user to send the welcome email to.
    int user_id
  }
```

An endpoint with no inputs still writes the empty block, as in `me_GET.xs` and `my_events_GET.xs`:

```
  input {
  }
```

Inputs are read as `$input.<name>`, for example `$input.email`, `$input.magic_token`, `$input.user_id`.

The addon at `xano/addon/user.xs` shows an input carrying a table reference, exactly like a table foreign key field:

```
  input {
    int user_id? {
      table = "user"
    }
  }
```

### Authentication

`auth = "user"` on the endpoint block turns on authentication and names the auth table. It sits right under `api_group`. From `xano/api/authentication/auth/me_GET.xs`:

```
query "auth/me" verb=GET {
  api_group = "Authentication"
  auth = "user"
```

Endpoints with `auth = "user"`: `auth/me`, `reset/update_password`, `logs/user/my_events`. All other endpoints simply omit the property, which is how a public endpoint is written. There is no `auth = false` on any `query` in this workspace.

Once authenticated, the token's identity is available as `$auth`. Only `$auth.id` is used, in `me_GET.xs`, `update_password_POST.xs`, and `my_events_GET.xs`:

```
    db.get user {
      field_name = "id"
      field_value = $auth.id
      output = ["id", "created_at", "name", "email", "role"]
    } as $user
```

### Response shape

`response =` sits after the `stack` block and before `tags`. Four distinct forms appear.

A bare variable, from `me_GET.xs`:

```
  response = $user
```

An inline object literal mixing variables, from `login_POST.xs` and `signup_POST.xs`:

```
  response = {authToken: $authToken, user_id: $user.id}
```

A multi line object built with filters, from `request_reset_link_GET.xs`:

```
  response = {
    message: {}|set:"success":true|set:"message":"magic link sent"
  }
```

A multi line object with a quoted key JSON literal, from `update_password_POST.xs`:

```
  response = {
    message: {"success":"true","message":"Password updated"}
  }
```

And `response = null` for a function that returns nothing, from `log_event.xs` and `enforce_role.xs`:

```
  response = null
```

Note the inconsistency preserved from the source: `update_password_POST.xs` returns `"success":"true"` as a string while `request_reset_link_GET.xs` builds `"success":true` as a boolean. Both are valid syntax.

There is no separate response schema or status code declaration anywhere. `response` is a value expression only.

## 5. Function stack

### Step sequencing

`stack { }` holds an ordered list of steps. There are no commas, semicolons, or step numbers. Each step is `<step_type> [target] { <properties> } as $<variable>`, and the `as $name` clause is what binds its result. A `//` comment line above a step is that step's description in the Xano UI. Blank lines between steps in the source files are indented with two trailing spaces, which is an artifact of the exporter, not meaningful syntax.

The step types observed across the workspace:

- `db.get`
- `db.query`
- `db.add`
- `db.edit`
- `var`
- `precondition`
- `conditional` with `if` and `throw`
- `function.run`
- `security.check_password`
- `security.create_auth_token`
- `security.create_uuid`
- `util.send_email`
- `util.template_engine`
- `ai.external.mcp.tool.run`

Not observed in this workspace: `db.delete`, loops of any kind (`for`, `foreach`, `while`), `try`/`catch`, external HTTP request steps, `switch`, `db.bulk_add`, `db.patch`, or any transaction step.

### Function declaration

Functions use a `"Group/name"` two part name, and are called by that same string. Complete file `xano/function/quick_start/log_event.xs`:

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

Calling a function, from `xano/api/authentication/auth/login_POST.xs`:

```
    // Create an event log for login
    function.run "Quick Start/log_event" {
      input = {user_id: $user.id, action: "login", metadata: $user}
    } as $event_log
```

The same call written multi line, from `xano/api/authentication/auth/me_GET.xs`. Note the exporter aligns the colons with padding:

```
    function.run "Quick Start/log_event" {
      input = {
        user_id : $user.id
        action  : "get_auth_user"
        metadata: $user
      }
    } as $event_log
```

Both the single line comma separated object and the multi line newline separated object are valid. Multi line objects use no commas.

### Variables

`var $name { value = ... }` is the only assignment form. From `xano/function/quick_start/enforce_role.xs`:

```
    // Defines a hierarchy of roles with numerical levels.
    var $role_hierarchy {
      value = {admin: 2, member: 1}
    }
```

References are `$name` for step results and variables, `$input.<field>` for inputs, `$auth.<field>` for the auth token, `$env.<name>` for environment values, and `$db.<table>.<field>` inside a `where` expression. Dot access reaches into nested objects: `$user.password_reset.expiration`.

String concatenation uses `~`, seen in `xano/api/authentication/message/send_welcome_email_POST.xs`:

```
    var $email_subject {
      value = "Welcome to Our Service, " ~ $user_record.name ~ "!"
    }
```

A variable can be rebound by a later step. In `update_password_POST.xs`, `$user` is first bound by `db.get` and then rebound by `db.edit`.

### Database operations

`db.get` fetches one record by a single field. `field_name` is a quoted string and `field_value` is the expression. `output` is an optional array of columns. From `login_POST.xs`:

```
    db.get user {
      field_name = "email"
      field_value = $input.email
      output = ["id", "created_at", "name", "email", "password", "role"]
    } as $user
```

`output` can select nested object subfields with dotted paths, and when the array is long it is written one entry per line with no commas. From `magic_link_login_POST.xs`:

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

Omitting `output` returns the whole record, as in `signup_POST.xs` and `send_welcome_email_POST.xs`.

`db.get` returns `null` when nothing matches. That is the basis of the existence checks throughout, for example `precondition ($user == null)` in `signup_POST.xs`.

`db.query` filters with a `where` expression and a `return` shape. List form, from `my_events_GET.xs`:

```
    db.query event_log {
      where = $db.event_log.user_id == $auth.id
      return = {type: "list"}
    } as $user_events
```

Single record form, from `xano/function/quick_start/generate_magic_link.xs`:

```
    db.query user {
      where = $db.user.email == $input.email
      return = {type: "single"}
    } as $user
```

And from `xano/addon/user.xs`:

```
  stack {
    db.query user {
      where = $db.user.id == $input.user_id
      return = {type: "single"}
    }
  }
```

Note the addon's `db.query` has no `as $name` clause. Inside `where`, the left hand side is always the `$db.<table>.<field>` form, which is how a column is distinguished from a variable. Only `==` and only single condition `where` clauses appear. Compound `where` with `and`/`or`, sorting, paging, joins, and aggregates: not observed in this workspace.

`db.add` takes a `data` object. From `signup_POST.xs`:

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

`created_at: "now"` is a quoted string here, unlike the bare `now` used as a table default and as a comparison operand. The result of `db.add` is the created record, since `$user.id` is used immediately after.

`db.edit` combines a `db.get` style selector with a `data` payload. From `update_password_POST.xs`:

```
    db.edit user {
      field_name = "id"
      field_value = $auth.id
      data = {password: $input.password}
    } as $user
```

Writing a whole nested object, from `magic_link_login_POST.xs`. The odd inner indentation is verbatim from the export:

```
    db.edit user {
      field_name = "id"
      field_value = $user.id
      data = {
        password_reset: {
        token     : $user.password_reset.token
        expiration: $user.password_reset.expiration
        used      : true
      }
      }
    } as $user1
```

And with a filter expression as the selector value, from `generate_magic_link.xs`:

```
    db.edit user {
      field_name = "id"
      field_value = $user|get:"id":0
      data = {password_reset: $password_reset}
    } as $updated_password_reset
```

`db.delete`: not observed in this workspace.

### Filters

Filters are pipe expressions applied to a value, `value|filter:arg` or `value|filter:arg1:arg2`. They chain, and when chained across lines each continuation line begins with the pipe. Observed filters and their call sites:

- `|get:$user_role` and `|get:$input.required_role`, in `enforce_role.xs`
- `|get:"id":0`, a get with a default, in `generate_magic_link.xs`
- `|set:"success":true|set:"message":"magic link sent"`, in `request_reset_link_GET.xs`
- `|concat:...`, in `request_reset_link_GET.xs`
- `|add_secs_to_timestamp:`, `|to_int`, in `generate_magic_link.xs`
- `|json_encode()`, in `xano/ai/agent/xano_example_agent.xs`, inside a `{{ }}` template

Filters starting from an empty object literal, and nested parenthesized filter expressions, from `generate_magic_link.xs`:

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

A multi line `|concat:` chain, from `request_reset_link_GET.xs`. The second argument is the separator placed before the concatenated value:

```
    var $magic_link {
      value = $api_base_url
        |concat:"1_start_here_demo_page#/update-password":"/"
        |concat:$token_and_email.token:"?magic_token="
        |concat:$token_and_email.email:""
    }
```

The schema level `filters=` attribute uses the same pipe syntax without a leading value: `filters=trim|lower`, `filters=min:8|minAlpha:1|minDigit:1`.

### Conditions

`precondition (<expr>) { ... }` is the dominant guard. It asserts the expression is truthy and aborts with the given error otherwise. From `login_POST.xs`:

```
    // Check to make sure a user with that email exists
    precondition ($user != null) {
      error_type = "accessdenied"
      error = "Invalid Credentials."
    }
```

`error_type` is optional. When only `error` is given, from `magic_link_login_POST.xs`:

```
    precondition ($input.magic_token != null) {
      error = "magic_token is required but was not provided."
    }
```

`error` is optional too. From `update_password_POST.xs`:

```
    precondition ($user.id == $auth.id) {
      error_type = "accessdenied"
    }
```

`error_type` values observed: `"accessdenied"`, `"notfound"`, `"unauthorized"`, `"inputerror"`.

Operators observed inside conditions: `==`, `!=`, `>`, `<`. A bare variable is a valid condition, as in `precondition ($pass_result)` in `login_POST.xs` and `precondition ($verify_token)` in `magic_link_login_POST.xs`. `now` works as a bare comparison operand, from `magic_link_login_POST.xs`:

```
    precondition ($user.password_reset.expiration > now) {
      error = "Magic token has expired. Please request another one."
    }
```

Branching uses `conditional { if (<expr>) { ... } }`. The only instance in the workspace, from `enforce_role.xs`:

```
    // Check if the user's role level is sufficient for the required role.
    conditional {
      if ($user_role_level < $required_role_level) {
        throw {
          name = "accessdenied"
          value = "User does not have the required role to perform this action. Required: " ~ $input.required_role ~ ", Actual: " ~ $user_role
        }
      }
    }
```

`else` and `else if` branches: not observed in this workspace. Because there is exactly one `conditional` in the workspace, that single example is the entire evidence for branching syntax.

### Raising errors

Two mechanisms, both shown above. `precondition` raises when its expression is falsy, taking `error_type` and `error`. `throw` raises unconditionally inside a `conditional`, and it uses different property names, `name` and `value`, rather than `error_type` and `error`. `name = "accessdenied"` matches the `error_type` vocabulary.

`try`/`catch`, custom error objects, and HTTP status codes on errors: not observed in this workspace.

## 6. Auth, environment variables, secrets

### Auth

Three pieces, all shown earlier and collected here.

The auth source is a table with `auth = true`, in `xano/table/user.xs`. Passwords are stored in a field of type `password` with validation filters:

```
    password? password filters=min:8|minAlpha:1|minDigit:1
```

Tokens are minted by `security.create_auth_token`. From `signup_POST.xs`:

```
    security.create_auth_token {
      table = "user"
      extras = {}
      expiration = 86400
      id = $user.id
    } as $authToken
```

`table` names the auth table, `id` is the record id to bind, `expiration` is seconds. `extras` is `{}` in `login_POST.xs` and `signup_POST.xs` but the empty string `""` in `magic_link_login_POST.xs`, so both appear to be accepted for "no extras".

Passwords are verified with `security.check_password`, which returns a boolean checked by the next `precondition`. From `login_POST.xs`:

```
    security.check_password {
      text_password = $input.password
      hash_password = $user.password
    } as $pass_result
```

Nothing in the stack hashes a password before `db.add`. `signup_POST.xs` writes `password: $input.password` straight into `db.add`, so hashing is implicit in the `password` field type.

`security.create_uuid` is a step with no property block at all, from `generate_magic_link.xs`:

```
    // Creates a unique UUID as token
    security.create_uuid as $token
```

That UUID is then stored through the `password` typed field `password_reset.token`, so it is hashed on write and later verified with `security.check_password` in `magic_link_login_POST.xs`. That is the whole magic link mechanism: a UUID stored hashed, plus an `expiration` timestamp and a `used` boolean, all checked by preconditions.

Role checks are application level, not part of `auth`. `xano/function/quick_start/enforce_role.xs` builds `{admin: 2, member: 1}` and compares levels. It is defined but never called by any endpoint in this workspace.

### Environment variables

One reference exists, in `xano/api/authentication/reset/request_reset_link_GET.xs`:

```
    // Create a variable with the API base URL
    var $api_base_url {
      value = $env.$api_baseurl
    }
```

The syntax is `$env.$<name>`, with a second `$` before the variable name. There is no declaration of environment variables anywhere in the workspace, no defaults, no types, and no list of what is available. There is exactly one usage, so this line is the sole evidence for the form.

### Secrets

No secret store, no secret reference syntax, and no credential values appear. `xano/ai/tool/search_xano_docs.xs` calls an external service and leaves the credential blank rather than referencing a secret:

```
    ai.external.mcp.tool.run {
      url = "https://docs.xano.com/mcp"
      bearer_token = ""
      connection_type = "stream"
      tool = "SearchXanoDocumentation"
      args = {}|set:"query":$input.search
    } as $search_xano_docs
```

Likewise `util.send_email` uses `service_provider = "xano"` and carries no API key. A dedicated secrets mechanism: not observed in this workspace.

## 7. Other step types worth recording

`util.send_email`, from `send_welcome_email_POST.xs`. Note there is no `to` property in any observed call:

```
    util.send_email {
      service_provider = "xano"
      subject = $email_subject
      message = $email_body
    } as $send_email
```

`util.template_engine` with a triple quoted heredoc string and `{{ $var.<name> }}` interpolation, from `request_reset_link_GET.xs`. Inside a template the prefix is `$var.`, not the bare `$`, and the closing `"""` sits on its own line:

```
    util.template_engine {
      value = """
        <!DOCTYPE html>
        <html>
        ...
            <p style="text-align: center; margin: 30px 0;">
              <a href="{{ $var.magic_link }}" style="display: inline-block; padding: 12px 25px; background-color: #007bff; color: #ffffff; text-decoration: none; border-radius: 4px; font-size: 16px;">
                Reset Your Password
              </a>
            </p>
        ...
        </html>
        """
    } as $message
```

The triple quoted string is also how the agent's system prompt is written, in `xano/ai/agent/xano_example_agent.xs`. That file shows an `llm = { ... }` config object with aligned colon keys and a `tools` array referencing tools by name:

```
  tools = [{name: "search_xano_docs"}]
```

and

```
    messages        : "{{ $args.messages|json_encode() }}"
```

which is the only appearance of `$args` in the workspace.

## 8. Summary of the grammar

- `<keyword> <name> [attr=value] { ... }` declares every object. Names are quoted only when they contain spaces, slashes, or hyphens.
- Properties are `key = value` and use `=`. Object literal members are `key: value` and use `:`. The exporter pads keys to align the colons.
- Arrays and objects written across multiple lines have no commas. Written on one line they do.
- Blocks that carry structure and no values, `schema { }`, `input { }`, `stack { }`, take no `=`.
- `$` prefixes everything readable: `$input`, `$auth`, `$env`, `$db`, `$args`, `$var` inside templates, and any `as $name` binding.
- `|` is both the filter pipe and the separator inside `filters=` and inside index `type` strings.
- `~` concatenates strings. `?` marks optional. `//` comments describe the next declaration or step.
- `guid` closes an object block; `tags` sits just before it.
