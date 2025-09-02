# Highball — Backup Manager

Web backup orchestration with scheduling, monitoring, notification. Providers: **rsync, restic**.

---
## Critical Execution

**OpType**: **Exec Context**
`UI`: Local container (Highball)
`BACKUP`: SSH+container on source host
`BROWSE` / `INSPECT`: SSH if source is SSH
`MAINTENANCE/*`: Auto detection (`_should_use_ssh(...)`)

- Always call `ResticExecutionService.execute_restic_command()` (`services/execution.py`).
- Never `subprocess.run()` directly.
- `same_as_origin` repos always SSH.
- `container_runtime` lives in `source_config`.
- `restic/restic:0.18.0` container (entrypoint = `restic`): run as `-r repo cmd`.

---
## Type Safety

- 100% typed signatures.
- Explicit imports: `Dict`, `List`, `Optional`, `Callable`.
- Precise types only (`Dict[str, Any]`, not `dict`).
- Decorators typed.

---
## Testing Musts

1. Real backups
2. Restore with overwrite protection
3. Notifications (email/Telegram)
4. Restic maintenance ops
5. Rsync patterns

---
## Architecture — MVC Refactor

- **app.py = switchboard only** (pure routes, zero logic).
- **Domains (pillars)**:
    - **Origins**: SSH hosts (keys, capability detection).
    - **Destinations**: targets (restic/rsyncd validation, init).
    - **Jobs**: paths, restores, lifecycle.
    - **Admin**: notifications, global config (in progress).
- **Shared services** (still central): execution, ssh, repos, maintenance.
- **Top-level /handlers, /models, /services** are frozen; no new code.

### Directory Map (target)

```bash
app.py             # Thin FastAPI routes
origins/           # handlers/, services/, schema.py
dests/             # handlers/, services/, schema.py
jobs/              # handlers/, services/, schema.py
admin/             # handlers/, services/, schema.py
handlers/          # Legacy page building - NO NEW CONTENT
models/            # Legacy shared validation/builders - NO NEW CONTENT
services/          # Legacy shared (execution, ssh, repos, maintenance) - NO NEW CONTENT
templates/         # schema-driven, HTMX
static/            # CSS, JavaScript, themes
config/            # local/{jobs,dests,origins,secrets}, local.yaml
config.py          # CRUD for config/
```

---
## Features

- Job CRUD + cron + conflict avoidance
- Notifications (spam-safe queue, templated vars)
- UI: schema-driven HTMX; `/inspect?name=job` hubs
- Restic: connectivity, browsing, auto/user/off maintenance
- Restore: overwrite protection, dual targets, dry run
- Backup browser: restic + FS
- REST API: `GET /api/highball/jobs` (filters)
- Debug: `/dev` scanner/logs, `/jobs` APScheduler internals

---
## Development Discipline

**Code**
- Always `execute_restic_command()`.
- Consider split >1000 lines.
- Enum only (no strings).
- One concern per module.

**HTMX**
- Never target parent of trigger.
- Source path arrays: add→`#list beforeend`; remove→`outerHTML self`.
- Path[0] not removable.

**Responses**
- Centralized in `handlers/api.py:ResponseUtils`.

**Anti-patterns**
- Duplicated try/catch → use decorator.

**Authority**
- Claude: implementation patterns.
- Shane: design/arch/product.
- Ask before big design moves; recommend, don’t just list.

---
## Navigation

- **Execution**: `services/execution.py` (ResticExecutionService)
- **SSH**: `services/ssh.py`
- **Repos**: `services/repositories.py`
- **Maintenance**: `services/maintenance.py`
- **Jobs**: `jobs/services/{backup,restore,notify,schedule}.py`
- **Dests**: `dests/services/{local,restic,rsync}.py`
- **Admin**: `admin/services/*` (notifications/config)
- **Schemas**: each domain `schema.py`; shared legacy `models/*`
- **Config**: `config.py` + `/config/local/*`
- **Logs**: `/var/log/highball/`

---
## Refactor Tracker

-  All routes → domain handlers
-  All orchestration → domain services
-  Restic via `ResticExecutionService` only
-  Module size audit <1000
-  HTMX target audit
-  ResponseUtils used everywhere

---
## TODO

@LOCAL/MVC.md

---
## Conventions

- Don’t say “production ready”
- No arbitrary ETAs
- No emoji in codebase

---
## Legacy (Pre-MVC)

Temporary, safe to delete post-refactor:

- Old top-level `/handlers`, `/services`, `/models` still exist but frozen.
- `app.py` still has some cruft; pure switchboard is target.

---
# Notes
Claude code auto-appends after this line.

---
