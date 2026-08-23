# What we still do not know

Two kinds of entry below. **Answered** items have a documented answer and a citation. **Open** items are things neither the official documentation nor the live workspace states, listed with the cheapest experiment that would settle each one.

---

## Part 1: the five questions the design depends on

### Q1. How is a unique index declared, and what does a conflicting insert return?

**Declaration: answered.** Uniqueness is piped onto the index type inside the table level `index` array. `[workspace]` `xano/table/user.xs`, and the identical block appears in `[docs]` `xanoscript/db`:

```
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
    {type: "btree|unique", field: [{name: "email", op: "asc"}]}
  ]
```

Composite unique indexes are structurally supported, since `field` is an array and `[docs]` shows a multi field index, but no source shows `"btree|unique"` combined with multiple fields.

**Conflict behavior: NOT DOCUMENTED.** This is the single most important gap in this whole document.

What was checked and came back empty:

- `xanoscript/function-reference/database-operations` documents `db.add` with a `data` parameter only. It says nothing about constraint violations.
- `troubleshooting-and-support/error-reference` contains no entry for a duplicate key, unique constraint, or conflict.
- No `error_type` in either source corresponds to a conflict. The four observed values are `accessdenied`, `notfound`, `unauthorized`, `inputerror`.
- No source states an HTTP status code for any error type, so a 409 cannot be assumed.
- `try_catch` exists and exposes `$error`, but **the shape of `$error` is not documented**, so there is no documented way to match specifically on a uniqueness failure inside a `catch`.

Consequence for a check and set duplicate detection: the pattern used throughout the workspace is a read, then a `precondition`, then a write. `[workspace]` `signup_POST.xs`:

```
    db.get user {
      field_name = "email"
      field_value = $input.email
    } as $user

    precondition ($user == null) {
      error_type = "accessdenied"
      error = "An account with this email already exists."
    }

    db.add user {
      data = { ... }
    } as $user
```

That is a read then write race, not an atomic check and set. Xano's own generated code ships this pattern, so it is idiomatic, but it is not safe under concurrency, and there is no documented way to recover from the unique index catching what the precondition missed.

The documented alternative is `db.add_or_edit`, which matches on one field and edits if found or adds if not:

```
db.add_or_edit user {
    field_name = "id"
    field_value = $input.id
    data = {name: $input.name}
} as $recordAddOrEdit
```

Whether `db.add_or_edit` is itself atomic is **not documented**, and it matches on a single field only, so it cannot express a composite key.

**Test to settle it.** On a scratch table with `{type: "btree|unique", field: [{name: "k", op: "asc"}]}`, build one endpoint that calls `db.add` with a colliding value. Record the exact HTTP status and body. Then wrap the same `db.add` in `try_catch` and return `$error` verbatim from the response, to learn whether `$error` carries a code that can be matched on. Then repeat both with `db.add_or_edit`. Finally, fire two concurrent requests with the same key and count the rows created, to learn whether the unique index actually rejects the second one or whether both land.

---

### Q2. Do scheduled or background tasks exist, and at what granularity?

**Answered: yes.** They are a first class `task` primitive. Full detail in `tasks-and-hosting.md`.

`[docs]` (`xanoscript/tasks`) the schedule block:

```
  schedule = [{
    starts_on: 2025-10-01 06:00:00+0000
    freq     : 604800
    ends_on  : 2025-10-26 19:51:05+0000
  }]
```

**Granularity is an interval in seconds anchored to a start timestamp, not cron syntax.** `starts_on` is a `YYYY-MM-DD HH:MM:SS+TZ` value written unquoted, `freq` is the gap between runs in seconds, `ends_on` is optional and the task runs indefinitely without it. A nightly batch close is `freq: 86400` with `starts_on` at the desired first run time.

Hard constraint worth restating: `[docs]` "Unlike APIs, background tasks **do not** have inputs or responses." A task reads from the database and writes to the database. It cannot be called with arguments.

A task also carries `active` (enable flag) and `datasource`. `[docs]` if no datasource is set, scheduled runs always use the **live** datasource.

**Still open, and all of it matters for a nightly close:**

- Minimum allowed `freq`, not documented.
- Whether a run that overruns `freq` causes the next run to be skipped, queued, or run concurrently. Not documented. For an idempotent nightly close this decides whether guard state is needed.
- Whether a missed run (instance unavailable at the scheduled instant) is skipped or backfilled. Not documented.
- Task execution timeout. Not documented.
- DST behavior. A fixed second interval anchored to a UTC instant will drift against local wall clock across a DST boundary, and there is no timezone field on a schedule entry. Not addressed anywhere.
- Whether a task can be triggered manually or from an endpoint, which would be needed to replay a failed night. Not documented.

**Test to settle it.** Create a task with `freq: 60` whose stack writes a row containing `now` and then sleeps past 60 seconds. Read the resulting rows to learn overlap behavior and actual timing accuracy in one experiment. Separately try `freq: 1` to find the floor.

---

### Q3. Can a function stack loop over a list? Can a query use AND/OR? Can results be sorted and paginated?

**All three: answered yes.** All `[docs]`; none of it is exercised in the workspace.

**Loops.** Three forms, plus `break` and `continue` which the docs say work in all three:

```
foreach ($list) {
  each as alias {
    // XanoScript statements go here
  }
}
```

```
for (`$loops`) {
  each as index {
    // XanoScript statements go here
  }
}
```

```
while (`conditions`) {
  each {
    // XanoScript statements go here
  }
}
```

Loops nest, and the documented task example loops directly over query results with `foreach ($user1) { each as $item { ... } }`.

**AND/OR.** `&&`, `||`, and parentheses inside `where`. `[docs]` the fullest documented example:

```
  where = $db.user.name == $input.name && $db.user.created_at > 1 || $db.user.id == 1 && ($db.user.role == "member" && true) || ($db.user.role == "admin" && true)
```

Every `where` in the workspace is a single `==` condition, so compound `where` is unverified locally.

**Sorting.**

```
    db.query user {
      where = $db.user.id == 1
      sort = {user.name: "asc"}
    } as $user1
```

**Pagination.** Configured inside the `return` object:

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

With paging on, the result is an envelope, not a bare array. `[docs]` shows these output paths: `itemsReceived`, `curPage`, `nextPage`, `prevPage`, `offset`, `itemsTotal`, `pageTotal`, and records under `items.*`.

**Still open:**

- Operator precedence between `&&` and `||`. Not documented. Parenthesize everything.
- Whether `sort` accepts multiple keys. Only single key examples exist.
- The `sort` key format is `{user.name: "asc"}`, table qualified but **without** the `$db.` prefix used in `where`. Only one example exists, so this is thin evidence.
- Interaction of `page` and `offset`, both present in the same documented paging object with no explanation.
- Whether the loop alias takes a `$`. The tasks page writes `each as $item`, the loops page writes `each as item` and then references it bare. Not resolved.
- Whether there is an iteration cap or a stack execution timeout that bounds how large a `foreach` can be. Not documented, and it decides whether a nightly batch must self chunk.
- `where` versus `search`. The database operations reference and the workspace use `where`; both background task pages use `search`. Unexplained.

**Test to settle it.** One endpoint containing a compound unparenthesized `where`, a two key `sort`, and paging with both `page` and `offset` set, returning the raw envelope, answers most of these at once. A separate task that loops 100k times and logs the last index reached settles the iteration cap.

---

### Q4. Can a function stack make an outbound HTTP request?

**Answered: yes.** `api.request`, `[docs]` (`xanoscript/function-reference/apis-and-lambdas`):

```
api.request {
  url = "https://www.myapi.com/myApiEndpoint"
  method = "GET"
  params = {}|set:"a":1
  headers = []|array_push:"Authorization: Bearer abc123"
} as api1
```

`method` accepts `"GET"`, `"POST"`, `"PUT"`, `"DELETE"`. `params` holds query parameters or body data. `headers` is an array of raw header strings built with `array_push`. There is also `stream.from_request` for streaming responses, which additionally exposes `timeout`, `follow_location`, `verify_host`, `verify_peer`, and client certificate parameters.

Not present in the workspace. The only outbound call in `xano/` goes through a different, purpose specific step.

**Still open:**

- **The response shape of `api.request` is not documented.** Whether the bound variable holds the body directly or an envelope with status and headers is unknown. This blocks any error handling on an outbound call.
- Whether a non 2xx response throws or returns normally. Not documented. If it returns normally, every call site needs an explicit status check, and the field to check is unknown.
- No `timeout` parameter is documented on `api.request`, though `stream.from_request` has one. The default timeout is not stated.
- How `params` distinguishes a query string from a JSON body on a POST. The single documented POST example sets `params` and a `Content-Type: application/json` header, and the prose says "Includes query parameters or body data" without disambiguating.
- No retry, backoff, or idempotency support is documented.

**Test to settle it.** Point `api.request` at an echo service and return the bound variable verbatim as the endpoint response. That reveals the envelope in one call. Repeat against a URL that returns 500 and against one that hangs, to learn throw behavior and default timeout.

---

### Q5. Is there any transaction or rollback across a multi step function stack?

**Partially answered.** A `db.transaction` step exists. `[docs]` (`xanoscript/function-reference/database-operations`), and this single example is the **entire** documentation for it:

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

It wraps a nested `stack`. That is all the docs say. There is no accompanying prose, no parameter table, and no second example.

**What is not documented, which is nearly everything that matters:**

- **Whether a failure inside the block actually rolls back.** The word "rollback" does not appear anywhere in the reviewed XanoScript documentation.
- Isolation level.
- Whether a `precondition` failure or a `throw` inside the block triggers a rollback, or whether only a database level error does.
- Whether `try_catch` inside a transaction suppresses the rollback.
- Whether variables bound inside the block (`$user1` above) are visible after it.
- Whether nesting is allowed.
- Whether non database steps inside the block (`api.request`, `util.send_email`) are affected, and obviously they cannot be rolled back.
- Whether a transaction can span a `function.run` call to another function.

Outside `db.transaction` there is **no** implicit transaction. A stack is a sequence of independent statements. `try_catch` with `finally` exists for cleanup, but compensation must be written by hand:

```
try_catch {
  try {
    // statements that may throw
  }
  catch {
    debug.log { value = $error }
  }
  finally {
    debug.log { value = "Cleanup actions" }
  }
}
```

The workspace demonstrates the risk concretely. `magic_link_login_POST.xs` checks `used == false`, mints an auth token, then marks `used: true` in a separate `db.edit`, with no transaction around any of it.

**Test to settle it.** Inside one `db.transaction` stack, do two `db.add` calls into different tables with a `throw` between them, then query both tables. If the first insert is gone, rollback is real. Repeat with a failing `precondition` instead of a `throw`, and again with the `throw` wrapped in `try_catch`, to map which failure modes actually trigger the rollback.

---

## Part 2: everything else we do not know

### Language and syntax

1. **`else` and `else if` do not appear in either source.** The workspace contains exactly one `conditional` block, an `if` with no else. The conditionals reference page does not show an else branch either. How to write a two way branch is unverified.
2. **Backticks around conditions.** The loops page writes `if (\`$index == 5\`)` and `while (\`true == true\`)`. The workspace writes conditions bare. Whether backticks are required in loop contexts, optional everywhere, or a documentation artifact is unresolved.
3. **Foreign key property name.** The workspace uses `table`, the field type reference page uses `dbtable`, the db page uses `table`. Two of three agree with the workspace.
4. **Nested object schema syntax.** The workspace nests a `schema { }` block of typed field lines; the field type reference shows `schema = { key: "string" }`. These are structurally incompatible and both are labeled as the same thing.
5. **`where` versus `search`** as the `db.query` filter keyword, as above.
6. **Path parameters in a route.** The error reference page mentions an endpoint named `/auth/{user_id}`, so the `{name}` form exists, but no full endpoint declaration using one was found, and how such a parameter is read (whether it appears on `$input`) is not documented.
7. **The full `error_type` enumeration** and its mapping to HTTP status codes. Four values are observed; the complete list is unstated, and no source gives a status code for any of them.
8. **Response status codes.** `response =` is a value expression only. There is no documented way to set a status code, add response headers, or return a 201 versus a 200.
9. **The filter catalogue was not exhaustively transcribed.** Seven `filter-reference` pages exist (manipulation, math, timestamp, text, array, transform, comparison, security). Only the filters actually used in the workspace and in the examples quoted here were captured.
10. **`$auth` fields beyond `id`.** Only `$auth.id` is ever read. Whether `extras` passed to `security.create_auth_token` is readable from `$auth`, and under what path, is not documented.
11. **Whether `$env.$request_auth_token` includes the `Bearer ` prefix.**
12. **Whether string comparison in a `precondition` is constant time.** Relevant to any shared secret check. Assume not.
13. **How middleware is attached to a specific endpoint.** The `middleware` primitive declares itself, but nothing observed declares the binding between a middleware and the API it guards.

### Operations

14. **Directory layout conflict.** The CLI docs say endpoint files are `{name}_{verb}.xs` in snake_case with a group file named `api_group.xs`. The real pull produced uppercase verbs (`login_POST.xs`) and named the group file after the group (`authentication.xs`). Since push matches by `guid` and "file paths don't matter", this is probably cosmetic, but a hand authored new file has no `guid` and its path and name may then matter. **Untested.**
15. **How a brand new object gets its `guid`.** Every existing file has one. Whether a hand written file must omit `guid` entirely to be treated as a create, or whether the CLI generates one, is not documented. This is the practical question for authoring new tables locally rather than pulling them.
16. **Setting an environment variable on a live workspace from the CLI.** `xano sandbox env set` and `xano tenant env set` exist; no `xano workspace env set` appears in the command reference. The documented route is the settings panel UI.
17. **Secrets in git.** `xano workspace pull --env` writes environment variables into the local tree. Whether they land in plaintext, and in which file, was not verified.
18. **Whether the sandbox is available on this account's plan.** `[docs]` sandbox access is not available on the free plan, and static hosting requires a paid plan. Both gate real design choices and neither was checked against the actual account.
19. **Rate limiting.** No rate limit primitive or setting was found in any reviewed page.
20. **Static hosting details:** SPA fallback routing to `index.html`, cache and CORS headers, build environment variables, Node version pinning, and build timeouts are all unaddressed. Whether the hosted frontend shares an origin with the API, which decides whether CORS is involved at all, is also unstated.
21. **Trigger timing.** Whether a `table_trigger` fires synchronously inside the writing transaction or asynchronously afterward. This decides whether a trigger can enforce an invariant or only react to one.

---

## The single most significant gap

**What a conflicting insert against a unique index returns.**

Everything else on this list is either answered, cosmetic, or has an obvious conservative workaround. This one does not. Three separate facts compound:

1. The unique index declaration is well documented and certainly works at the database level.
2. Nothing anywhere describes what surfaces when it fires: no error type, no status code, no error body shape.
3. `$error` inside `try_catch` has no documented shape, so even the catch-and-inspect escape hatch cannot be written against a specification.

Which means the only documented way to detect a duplicate is the read-then-precondition pattern that Xano's own generated code uses, and that pattern is a race. A design that relies on check and set for duplicate detection is currently resting on an assumption, and it is a cheap one to test: one scratch table, one endpoint, two concurrent requests.

## Addendum: the cache was not researched, and it answers the duplicate question

The original brief for this reference did not ask about caching, so the earlier
sections treat the unique index as the only route to a check and set. That was
an incomplete search rather than a correct conclusion.

Xano's data caching is Redis backed. The documented functions are Set, Get, Has,
Delete, Increment, Decrement, several list operations, Get Cache Keys, and Rate
Limit. Set takes a TTL in seconds where zero means never expire.

**Increment Cache Value returns the incremented value.** That is the missing
atomic primitive. Redis increment on a missing key sets it to one and returns
one, in a single command, so exactly one concurrent caller can receive one.
Duplicate detection can be serialised on that rather than on unique index
conflict semantics nobody has documented.

**Set if absent is not available.** There is an open community feature request
asking for Redis SET NX support on Set Cache Value, so increment is currently
the only atomic claim primitive.

Still not documented, and worth settling by test rather than assumption:

- Whether Xano's Increment preserves Redis atomicity under concurrent calls.
  It is one Redis command, so this is likely, but likely is not measured.
- Whether the cache is shared across instance workers or is per worker. If it
  were per worker the increment would serialise only within one worker, which
  would silently weaken the guarantee.
- What Increment does to a key holding a non numeric value.
- Eviction policy and whether a key with no TTL can still be evicted under
  memory pressure.

The second of those matters most. A per worker cache would make the whole design
unsound, and nothing in the documentation states which it is.
