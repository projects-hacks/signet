# Xano CLI

Sources: `docs.xano.com/xano-cli/*` (get-started, push-pull, profiles, sandbox, static-hosting, command-reference), `docs.xano.com/xano-features/workspace-settings`, and the actual `xano/` directory in this repo, which is the output of a real pull.

---

## 1. Install

`[docs]` The CLI is an npm package named `@xano/cli`:

```bash
npm install -g @xano/cli
xano --version
```

Update in place:

```bash
xano update
xano update --check
```

---

## 2. Authentication

`[docs]` Browser based, interactive:

```bash
xano auth
```

This opens a browser login, then prompts for instance, workspace (optional), branch (optional), and a profile name (defaults to `default`). Credentials are written to `~/.xano/credentials.yaml`.

For a self hosted instance, pass the origin:

```bash
xano auth -o https://my-xano.my-domain.com
xano auth -o https://my-xano.my-domain.com --insecure
```

Non interactive, for scripting. The access token is generated in Xano account settings under **API Access**:

```bash
xano profile create my-profile \
  -t YOUR_ACCESS_TOKEN \
  -i https://your-instance.xano.io \
  -w WORKSPACE_ID \
  -b BRANCH_LABEL \
  --default
```

| Flag | Meaning |
| --- | --- |
| `-t` | access token (required) |
| `-i` | instance origin URL (required) |
| `-a` | account origin URL, for self hosted |
| `-w` | workspace ID |
| `-b` | branch label |
| `-k, --insecure` | skip TLS certificate verification |
| `--default` | set as the default profile |

Verify:

```bash
xano profile me
xano profile list
xano profile set my-profile
xano profile token
```

### Profile selection precedence

`[docs]` A project can pin itself to a profile with a local `profile.yaml`, which references a profile **by name only**; the docs state that an `access_token` key inside `profile.yaml` is rejected and the token always stays in `~/.xano/credentials.yaml`. Precedence, highest first:

1. `-p, --profile` flag
2. `XANO_PROFILE` environment variable
3. project local `profile.yaml`

Two global flags exist on every command: `-p/--profile` (`XANO_PROFILE`) and `-v/--verbose` (`XANO_VERBOSE`).

---

## 3. Pull

`[docs]`:

```bash
xano workspace pull -d ./my-workspace
```

| Flag | Meaning |
| --- | --- |
| `-b` | branch name; overrides the profile, defaults to the live branch |
| `-w` | workspace ID; overrides the profile |
| `--env` | include environment variables |
| `--records` | include database records |
| `--draft` | include draft versions of resources |

`--records` is the documented way to snapshot data locally before a schema change.

---

## 4. Directory layout

### What the docs say

`[docs]` (`xano-cli/push-pull`) a pull produces:

```
my-workspace/
├── workspace/
│   ├── my_workspace.xs
│   └── trigger/
│       └── on_workspace_event.xs
├── table/
│   ├── user.xs
│   ├── product.xs
│   └── trigger/
│       └── on_user_create.xs
├── function/
│   ├── calculate_shipping.xs
│   └── utils/
│       └── validate_email.xs
├── api/
│   ├── user/
│   │   ├── api_group.xs
│   │   ├── get_user_get.xs
│   │   └── create_user_post.xs
│   └── product/
│       ├── api_group.xs
│       └── list_products_get.xs
├── task/
│   └── cleanup_expired_sessions.xs
├── ai/
│   ├── agent/
│   ├── tool/
│   └── mcp_server/
├── realtime/
│   ├── channel/
│   └── trigger/
├── middleware/
│   └── auth_check.xs
└── addon/
    └── fetch_related.xs
```

Documented rules: endpoints group under `api/{group_name}/` with an `api_group.xs` plus endpoint files named `{name}_{verb}.xs`; a function whose name contains `/` splits into subdirectories; triggers go into a `trigger/` subdirectory of their parent type; and "All filenames are converted to `snake_case`".

### What the real pull actually produced

`[workspace]` the complete listing of `xano/` in this repo:

```
xano/addon/user.xs
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

Two differences from the documented layout, both confirmed by inspection:

1. The API group file is named after the group (`authentication.xs`, `event_logs.xs`, `signet.xs`), **not** `api_group.xs`.
2. The verb suffix is **uppercase** (`login_POST.xs`, `me_GET.xs`), not lowercase snake_case.

Other observed conventions, consistent with the docs:

- Endpoint path segments become directories. `query "logs/user/my_events"` lands at `api/event_logs/logs/user/my_events_GET.xs`.
- A hyphen in a route becomes an underscore in the filename. `query "reset/magic-link-login"` lands at `reset/magic_link_login_POST.xs`.
- A function named `"Quick Start/log_event"` lands at `function/quick_start/log_event.xs`.
- Directories with no objects are simply absent. There is no `task/`, `middleware/`, `realtime/`, or `trigger/` directory in this pull.

**File paths do not matter for identity.** `[docs]`: "Existing objects are matched by the `guid` stored in each file, there's no manifest and file paths don't matter." A fresh pull is what guarantees each file carries the right `guid`.

---

## 5. Push

Two different targets, and which one is the default depends on the plan.

### Sandbox push, the default on paid plans

`[docs]` Pushing through a sandbox is the default and is **required** unless direct workspace push has been explicitly enabled. The sandbox is an isolated copy of the workspace.

```bash
xano sandbox push -d ./my-sandbox
xano sandbox push -d ./my-sandbox --dry-run    # preview without applying
xano sandbox push -d ./my-sandbox --sync       # full push, send all files
xano sandbox push -d ./my-sandbox --review     # push, then open review in the browser
xano sandbox review
xano sandbox reset
```

`sandbox push` shares most of `workspace push`'s flags with one documented exception: it does **not** support the `-i/--include` or `-e/--exclude` filters.

`[docs]` Sandbox access is not available on the free plan.

`[docs]` If local files name a different workspace than the one loaded on the sandbox, and the push contains 25 or more changes, the CLI shows a Workspace Mismatch warning and asks for confirmation.

### Direct workspace push

```bash
xano workspace push -d ./my-workspace
```

`[docs]` (`xano-features/workspace-settings`) the gate is a workspace setting called **Allow Direct Workspace Push**: "When enabled, `xano workspace push` applies changes to this workspace immediately, skipping the standard sandbox review flow. **Use with caution.**"

Free plan users can push directly right away.

### Push flags

| Flag | Meaning |
| --- | --- |
| `--dry-run` | show the push preview, then exit without applying anything |
| `--sync` | full push, send all files rather than only changed ones; required for `--delete` |
| `--delete` | delete workspace objects not included in the push; requires `--sync` |
| `--force` | skip the preview and confirmation prompt, and override critical error blocking; required in non interactive environments |
| `-i / --include` | push only matching files |
| `-e / --exclude` | skip matching files |
| `--records` | include table records |
| `--truncate` | delete all existing table records before importing |

`[docs]` The flag is `--dry-run` with **two** dashes. The docs call this out explicitly because `-dry-run` is a common mistake.

### Push modes

`[docs]`:

| Mode | Command | Sends | Remote objects not present locally | Destructive |
| --- | --- | --- | --- | --- |
| Partial (default) | `xano workspace push` | only changed files | left untouched, listed under *Remote Only* | no |
| Mirror | `xano workspace push --sync --delete` | all files | **deleted** so the workspace matches local exactly | yes, permanent |
| Preview only | `xano workspace push --dry-run` | nothing | nothing | no |
| Skip confirmation | `xano workspace push --force` | as combined | as combined | inherits |

---

## 6. Is there a dry run or a diff?

Yes, and it is the main safety mechanism.

`[docs]` Every `xano workspace push` **automatically** runs a preview before changing anything: the CLI performs a dry run against the instance, shows what will happen, and prompts for confirmation. If there is nothing to do it exits with `No changes to push.`

The preview is structured as:

- A per type count of creates, updates, and deletes, color coded green, yellow, red.
- Non destructive operations: `CREATE`, `UPDATE`, `ADD_FIELD`, `UPDATE_FIELD`.
- Destructive operations listed **separately** and highlighted: `DELETE`, `CASCADE_DELETE`, `TRUNCATE`, `DROP_FIELD`, `ALTER_FIELD`. When any are present the confirmation prompt warns explicitly.
- A *Remote Only* section listing objects that exist in Xano but not locally. Shown when `--delete` is not set, so the discrepancy is visible without acting on it.
- Record counts per table when `--records` is used.

`--dry-run` prints exactly what a real push would print, then stops.

`[docs]` The documented pre push routine:

1. Pull first, so local files are current.
2. `xano workspace push -d ./my-workspace --dry-run`, and read the left column: existing objects should show as **UPDATE**, and only genuinely new objects as **CREATE**.
3. If the preview matches intent, run the push and confirm at the prompt.

`[docs]` Pushes containing critical errors, named as XanoScript syntax errors or unresolved placeholders, are **automatically blocked**, with the errors highlighted in the preview. `--force` overrides that blocking.

There is no separate `xano diff` command. The docs recommend `git diff` on the local `.xs` files for that.

---

## 7. Risks of a direct workspace push

Collected from `xano-cli/get-started` and `xano-cli/push-pull`.

- **It is applied immediately.** Direct push skips the sandbox review flow entirely. The workspace setting that enables it is labeled "Use with caution."
- **Schema changes hit a real database.** The docs frame local `.xs` files as production infrastructure code and recommend committing to git before every push so there is a known good snapshot to revert to.
- **`--sync --delete` permanently removes** any object in Xano that is absent from the local push. `--delete` is gated behind `--sync` for this reason.
- **`--truncate` deletes all existing table records** before importing. The docs restrict it to staging and test workspaces and say never to use it against production.
- **`--force` removes both guardrails at once**: it skips the confirmation prompt and overrides critical error blocking, so a file with a syntax error will still be pushed.
- **There is no automatic sync from the other editors.** `[docs]`: if changes were made in the visual builder, the in browser editor, or the extension, local files will not reflect them and there is no automatic sync or diff checking. Always `xano workspace pull` before working locally, otherwise a push can silently revert someone else's work.
- **No branch isolation by default.** The docs recommend developing on a non live branch or a secondary workspace and promoting to live only after testing.
- **Command help text carries severity markers.** `[docs]` destructive commands are tagged `[CRITICAL]` (irreversible or high blast radius: `sandbox reset`, `--force` deletes, `workspace push --truncate`, `--sync --delete`) and impactful but reversible ones `[IMPORTANT]` (base `workspace push` / `sandbox push`, `branch set_live`, release deploys).

A workable local rule: allow `--dry-run` freely, require a human read of the preview for anything else, and never combine `--force` with `--delete` or `--truncate`.

---

## 8. Environment variables through the CLI

`xano workspace pull --env` includes environment variables in a pull.

`[docs]` (`xano-cli/command-reference`) there are dedicated env commands for **sandboxes** and **tenants**:

```bash
xano sandbox env list
xano sandbox env get --name KEY
xano sandbox env set --name KEY --value VAL
xano sandbox env delete --name KEY
xano sandbox env get_all --file ./env.yaml
xano sandbox env set_all --file ./env.yaml --clean
```

No equivalent `xano workspace env set` command appears in the command reference. How an environment variable is set on a live workspace from the CLI is **not documented**; the workspace settings panel is the documented route (see `auth-and-security.md`).

---

## 9. Other command families

`[docs]` present in the command reference but not needed for a first build: `xano branch` (including `branch set_live`), `xano release` (versioned snapshots that give a rollback point independent of git history), `xano tenant`, `xano static_host` (see `tasks-and-hosting.md`), `xano function`, and workflow test commands.
