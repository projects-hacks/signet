# Background tasks, triggers, and static hosting

Sources: `docs.xano.com/xanoscript/tasks`, `docs.xano.com/building/logic/background-tasks`, `docs.xano.com/xanoscript/triggers`, `docs.xano.com/xano-features/static-hosting`, `docs.xano.com/xano-cli/static-hosting`.

Nothing in this file is `[workspace]`. The pull in `xano/` contains **no** `task/`, `trigger/`, or static hosting artifacts, so every example here is `[docs]` only and unverified against a live push.

---

## 1. Do scheduled tasks exist?

Yes. They are a first class primitive called a **background task**, declared with the `task` keyword, and the docs describe them as "background tasks (also called scheduled tasks or cron jobs)".

`[docs]` (`building/logic/background-tasks`) the defining constraint: "Unlike APIs, background tasks **do not** have inputs or responses. They only contain logic and a schedule block."

That matters for design. A task cannot be parameterized and cannot return anything. Anything a task needs must be read from the database or from an environment variable, and anything it produces must be written to the database.

---

## 2. Declaring a task

`[docs]` (`xanoscript/tasks`) a complete example:

```
// Looks at the user table for users that haven't logged in for the last 30 days or more, and sends them an email trying to reengage them with the platform.
task reengage_users {
  active = false
  datasource = "test"

  stack {
    db.query user {
      search = $db.user.last_login <= ("now"|timestamp_subtract_months:1)
    } as $user1

    foreach ($user1) {
      each as $item {
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
      }
    }
  }

  schedule = [{
    starts_on: 2025-10-01 06:00:00+0000
    freq     : 604800
    ends_on  : 2025-10-26 19:51:05+0000
  }]

  tags = ["user actions", "retention"]
}
```

Declaration properties:

| Element | Required | Meaning |
| --- | --- | --- |
| `task` | yes | declares the primitive |
| `task_name` | yes | unique name |
| `description` | no | may also be a `//` comment above the block |
| `active` | no | whether the task is enabled |
| `datasource` | no | which datasource the task runs against |

`[docs]` (`building/logic/background-tasks`) on `datasource`: if no data source is chosen, scheduled runs always use the live data source. The example above sets `datasource = "test"`, which is the safe default while developing.

`[docs]` a task must be **enabled** and then **published** before it runs. The XanoScript equivalent is `active`.

Optional settings, at the root level after the stack and schedule: `description`, `tags`, and `history` (an object, where `{inherit: true}` inherits history settings from the workspace).

---

## 3. Schedule granularity

`[docs]` (`xanoscript/tasks`) the schedule is an array of entries. Each entry has:

- `starts_on`, a date and time in `YYYY-MM-DD HH:MM:SS+TZ` format, written **unquoted**
- `freq`, "a `freq` in seconds which defines the interval between runs"
- `ends_on`, optional, same format. "If `ends_on` is not provided, the task will run indefinitely."

Single line form, `[docs]` from `building/logic/background-tasks`:

```
      schedule = [{starts_on: 2025-10-20 13:47:35+0000, freq: 86400}]
```

Multi line form, `[docs]` from `xanoscript/tasks`:

```
  schedule = [{
    starts_on: 2025-10-01 06:00:00+0000
    freq     : 604800
    ends_on  : 2025-10-26 19:51:05+0000
  }]
```

### What this means for a nightly batch

**Granularity is an interval in seconds anchored to a start timestamp.** It is not cron syntax. A nightly job is `freq: 86400` with `starts_on` set to the desired wall clock time of the first run, expressed with an explicit UTC offset. The example comment in the docs confirms this reading: a task commented "runs every day at 11 PM UTC" is expressed as `starts_on: 2025-10-20 13:47:35+0000, freq: 86400`.

Consequences that follow from an interval model and that the docs do **not** address:

- **Daylight saving is not handled.** A fixed 86400 second interval anchored to a UTC instant will drift relative to local wall clock time across a DST boundary. There is no timezone field on a schedule entry, only the offset baked into `starts_on`.
- **Whether the array can hold multiple entries** is implied by it being an array and by the phrase "one or more objects to represent a schedule entry", but no multi entry example exists.
- **Missed run behavior** is not documented. If the instance is unavailable at the scheduled instant, whether the run is skipped or backfilled is unknown.
- **Overlap behavior** is not documented. If a run takes longer than `freq`, whether the next run is skipped, queued, or started concurrently is unknown. For a batch close this matters.
- **Minimum `freq`** is not documented.
- **Execution timeout** for a task is not documented.

The docs note that the visual builder offers "every hour, day, week, etc." as choices, which is consistent with the interval model.

### Observability

`[docs]` the API reference lists "Search task request history" and "Retrieve task request history" endpoints, so task runs are logged and queryable. The retention and the shape of those records were not examined.

---

## 4. Tasks can loop, which is what makes a batch possible

The task example above is the clearest documented use of a loop: query a set, then `foreach` over it. See `xanoscript.md` section 8.3 for the full loop syntax including `for`, `while`, `break`, and `continue`.

Note the task page writes `search =` where the database operations reference writes `where =`. That conflict is unresolved. See `xanoscript.md` section 11, item 3.

---

## 5. Triggers, the event driven alternative

`[docs]` (`xanoscript/triggers`) four trigger kinds exist. A database trigger is the relevant one for reacting to writes rather than polling on a schedule:

```
// Sends an email when a user signs up for the service.
table_trigger send_email_on_signup {
  table = "user"
  input {
    json new
    json old
    enum action {
      values = ["insert", "update", "delete", "truncate"]
    }
    text datasource
  }

  stack {
    util.send_email {
      api_key = ""
      service_provider = "xano"
      subject = "Welcome"
      message = "Thanks for signing up, "|concat:($input.new.name|split:" "|first):""
      bcc = []
      cc = []
      from = ""
      reply_to = ""
      scheduled_at = ""
    } as $email_sent
  }

  tags = ["user actions"]
  actions = {insert: true}
}
```

The `actions` object at the bottom selects which events fire the trigger. Documented `actions` shapes per kind:

| Kind | `actions` keys |
| --- | --- |
| `table_trigger` | `insert`, `update`, `delete`, `truncate` |
| `workspace_trigger` | `branch_live`, `branch_merge`, `branch_new` |
| `realtime_trigger` | `message`, `join` |
| `mcp_server_trigger` | `connection` |

A table trigger receives `new`, `old`, `action`, and `datasource` as inputs. Whether it runs synchronously inside the writing transaction or asynchronously afterward is **not documented**, which determines whether a trigger can be used to enforce an invariant or only to react to one.

---

## 6. Static hosting for a frontend

### What it is

`[docs]` (`xano-features/static-hosting`) Static Hosting serves pre built frontend assets, HTML, CSS, and JavaScript, from the Xano instance alongside the backend. **It is available on any paid plan**, which is a hard gate to check before designing around it.

Each workspace already has a site created, labeled `default`.

### Build behavior

`[docs]` when a `package.json` is present, Xano automatically runs the `build` script (for example `npm run build`) and hosts the generated output. Node.js runs during the build; it does **not** run as a persistent server at runtime.

Documented as working: React (Create React App, Vite), Next.js with `output: 'export'`, Vue, Svelte and SvelteKit with the static adapter, Astro, Angular, plain HTML/CSS/JS with no build step, and any framework that outputs static files.

Documented as **not** working:

- No server side rendering at request time. Use static export or static site generation.
- No backend application servers (Express, Django, Flask, Rails).
- No server side languages at runtime (Python, PHP, Ruby).

Summarized by the docs as: if the project can produce a static `build`, `dist`, or `out` folder, Xano can host it.

### Environments

`[docs]` each site has two environments, `prod` and `dev`, each with its own Xano issued domain, so a build can be tested without touching production. Custom domains can be attached to either, with Xano providing the DNS records. The Xano domain remains available even when a custom domain is set.

An upload is called a **build**, described as a snapshot of the site at that time. Uploading and deploying are separate steps: a build is uploaded, then explicitly deployed to `prod` or `dev`. Deployment logs are available per build.

Uploads can come from a ZIP file or by pulling from a git repository. For a git repo, HTTPS URLs work only for public repositories; private repositories require the SSH URL. `[docs]` git pulls are **not** automatic: "You'll need to create a new build to pull changes later; they are not synced automatically."

### CLI commands

`[docs]` (`xano-cli/static-hosting`):

```bash
xano static_host list
xano static_host create marketing --description "Marketing site"
xano static_host get marketing
xano static_host edit marketing --name marketing-v2

xano static_host build list marketing
xano static_host build get marketing --build_id 52
xano static_host build push marketing -d ./dist -n "v1.0.0"
xano static_host build push marketing -f ./build.zip -n "v1.0.0"
xano static_host build pull marketing --latest -d ./output
xano static_host build delete marketing --build_id 52

xano static_host deploy marketing --build_id 52 --env dev
xano static_host deploy marketing --build_id 52 --env prod
```

`build push -d <dir>` uploads a directory, `-f <file>` uploads a zip. `[docs]` `xano static_host build create` is deprecated; its zip upload capability moved into `build push -f`.

Deploy is a separate command from push, so promoting to production is an explicit, scriptable step.

There is also `xano static_host migrate` for moving to v2 hosting, which supports `--dry-run`.

### Not documented

- Whether static hosting sets any cache or CORS headers, and whether they are configurable.
- Whether SPA fallback routing (rewriting unknown paths to `index.html`) is handled automatically. This matters for any client side router.
- Build environment variables, Node version pinning, and build timeouts.
- Whether the frontend origin and the API origin are the same, which determines whether cross origin requests are involved at all.
