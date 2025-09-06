# Highball — Backup Manager

Web backup orchestration with scheduling, monitoring, notification. Providers: **rsync, restic**.

---
## Application Setup

- `Dockerfile`: single-stage GitHub action, not used locally
- `Dockerfile.base` + `Dockerfile.app` + `rr`: local (re)build chain

---

## Critical Execution

**OpType → Exec Context**

- `UI`: Local container (Highball)
- `BACKUP`: SSH+container on source host
- `BROWSE` / `INSPECT`: SSH if source is SSH
- `MAINTENANCE/*`: Auto detection (`_should_use_ssh(...)`)

Rules:

- Always call **`ResticExecutionService.execute_restic_command()`** (`services/exec.py`).
- **Never** `subprocess.run()` directly from handlers.
- `same_as_origin` repos always SSH.
- `container_runtime` lives in `source_config`.
- Image: `restic/restic:0.18.0` (entrypoint=`restic`): run as `-r repo cmd`.

---

## Architecture

- **`app.py` = switchboard only** (pure routes, zero logic).
- **Domains**: `origins/`, `dests/`, `jobs/`, `admin/`, each with `handlers/` and `services/`.
- **Shared domain**: `shared/handlers/` (web-facing utilities like templating), `shared/services/` (pure helpers, no web).
- **Top-level `/handlers`, `/services`, `/models` are frozen**; no new code.

### Directory Map (target)

```bash
app.py
origins/           # handlers/, services/, schema.py
dests/             # handlers/, services/, schema.py
jobs/              # handlers/, services/, schema.py
admin/             # handlers/, services/, schema.py
shared/            # handlers/ (templating, response helpers)
                   # services/ (exec, ssh, common)
templates/         # schema-driven, HTMX
static/            # CSS, JavaScript, themes
config/            # local/{jobs,dests,origins,secrets}, local.yaml
config.py          # CRUD for config/
```

---
## Lintable Rules (enforced by guardrails)

These are automatically checked by `.refactor/` scripts (and Ruff/Mypy). Thresholds are tunable.

**Layering**

- **Services & shared/services must not import web stack**: `fastapi`, `jinja2`.
- **Handlers must not perform heavy ops**: forbid `subprocess`, `os`, `pathlib`, `shutil`, `requests`, `json`, `yaml`, long loops/branches doing business logic.

**Handler shape & size**

- Handler files under a size cap (default **≤1000 LoC**).
- Handler functions under a complexity cap (default **≤40 lines** detected as a smell).

**Types & quality**

- **100% typed function signatures** (Mypy: `disallow_untyped_defs=True`).    
- Prefer precise types (`Dict[str, Something]`, not bare `dict`).
- Ruff: basic errors + import order (`E,F,I,B,B9`).

**Execution invariants**

- No direct `subprocess.run()` inside handlers (grep-enforced).
- Restic commands go through `ResticExecutionService` (spot-check via grep; services may spawn processes via execution layer only).

> Run: `.refactor/refactor.sh` (summary) — or `--claude-one` for a single, actionable fix.

---

## Style & Process Rules (human-reviewed)

**Handlers (web layer)**

- Parse request → call a service → render a template (**only**).
- Use `shared/handlers/templating.render()` (Jinja/HTMLResponse live here).
- No business rules, no file or network I/O, no long control-flow.

**Services (domain logic)**

- Pure business operations; **no FastAPI/Jinja**.
- Return **plain data** (dicts/records); let handlers render.
- One concern per module; avoid “god” services.

**Shared**

- `shared/services/`: common helpers (exec, SSH), framework-agnostic.
- `shared/handlers/`: web-only cross-domain helpers (templating, response utils).

**HTMX**

- Never target parent of trigger.
- Path arrays: add → `#list beforeend`; remove → `outerHTML self`.
- `Path[0]` not removable.
- SSE extension available for real-time updates.

**Coding habits**

- Prefer `Enum` values over magic strings.
- Duplicate try/except → replace with decorator.
- Keep modules focused; consider splitting >1000 LoC legacy modules.

**Team/process**

- Claude drives implementation patterns; Shane owns design/arch/product.  
- Ask before big design moves; recommend solutions, don’t list options only.
- Conventions: no “production ready” claims, no arbitrary ETAs, no emoji in codebase.

---

## Testing Scenarios (must validate)

1. Real backups    
2. Restore with overwrite protection
3. Notifications (email/Telegram)
4. Restic maintenance ops
5. Rsync patterns

---

## Navigation

- **Execution**: `services/exec.py` (→ will live in `shared/services/exec.py`)
- **SSH**: `services/ssh.py` (→ `shared/services/ssh.py`)
- **Jobs**: `jobs/services/{backup,restore,notify,schedule}.py`
- **Dests**: `dests/services/{local,restic,rsync}.py`
- **Admin**: `admin/services/*` (notifications/config)
- **Templates**: `shared/handlers/templating.py` (was `services/template.py`)
- **Schemas**: each domain `schema.py`; legacy shared `models/*`
- **Config**: `config.py` + `/config/local/*`
- **Logs**: `/var/log/highball/`

---

## Refactor Tracker

- All routes → domain handlers    
- All orchestration → domain services
- Restic via `ResticExecutionService` only
- Module size audit <1000
- HTMX target audit
- ResponseUtils used everywhere

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

## Legacy (Pre-MVC)

Temporary; safe to delete post-refactor:

- Old top-level `/handlers`, `/services`, `/models` still exist but **frozen**.

---

# Notes

Claude code auto-appends after this line.

## TECHNICAL DEBT PUNCHLIST

### Consolidate Shared Infra

- move models/forms.py into services/templates.py and give it a better name
- move services/ to shared/ so it has relaxed requirements

### Form Parsing Standardization

- **Issue**: 4 different `_get_form_value()` implementations across domain handlers    
- **Action**: Create standardized form parsing helper in `BaseHandler` class
- **Files**: admin/handlers/pages.py, jobs/handlers/pages.py, dests/handlers/pages.py, origins/handlers/pages.py

### GET/POST Route Deduplication

- **Issue**: Duplicate GET/POST routes for same operations (e.g. `/unlock-repository`)
- **Action**: Use `@app.api_route("/path", methods=["GET", "POST"])` pattern
- **Priority**: Medium

### Restore Service Consolidation

- **Issue**: Two restore implementations - async (`jobs/services/restore.py`) vs sync (`jobs/handlers/pages.py`)
- **Action**: Research which is actively used, merge functionality into single service
- **Priority**: Medium-High

### Remaining SSH Consolidation

- **Issue**: `dests/services/rsync.py` still uses manual SSH commands instead of `SSHCommandFactory`
- **Action**: Convert rsync SSH calls to use `SSHCommandFactory` from `services/ssh.py`

### Jobs Domain CRUD Pattern Retrofit (Post-Destinations)

- **Issue**: `jobs/handlers/pages.py` still does direct config read operations, violating "handlers are for data in motion" principle
- **Action**: After destinations domain SOC refactor is complete, retrofit jobs domain to move ALL CRUD operations (read AND write) to services
- **Pattern**: Jobs handlers should become pure HTTP orchestration like destinations handlers    
- **Services**: Enhance `JobOperationsService` to handle all config reads, not just writes

---

- move @handle_page_errors to shared/    
- migrate READ operations for config from handler to services (jobs domain) - write ops already there.  
    **Something smells funny here**
    

1. initialize_restic_repo_htmx - Working (returns Internal Server Error as expected for invalid job)
2. init_restic_repository_htmx - Working (returns proper validation error for missing repo_type)
3. unlock_repository_post_htmx - Working (returns empty error message as expected for non-existent job)
4. unlock_repository_htmx (GET) - Working (returns empty error message as expected for non-existent job)  
    ...why are there duplicate init/unlock methods and why is Internal Server Error ok?