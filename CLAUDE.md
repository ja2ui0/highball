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

---
# Notes
Claude code auto-appends after this line.

## Form Parsing Consistency Issue (2025-09-02)

During the MVC switchboard refactor, we moved form parsing from app.py to individual `*_htmx` handler methods. Each handler now has its own `_get_form_value()` helper method, but they have different implementations:

- **admin/handlers/pages.py**: Uses `isinstance(value, list)` check to handle list format
- **jobs/handlers/pages.py**: Uses `value_list[0]` assuming list format  
- **dests/handlers/pages.py**: Uses `isinstance(value, list)` check with `str()` casting
- **origins/handlers/pages.py**: Simple `form_data.get()` (old format, but apparently still works)

This inconsistency could lead to future bugs when form parsing patterns change or new `*_htmx` methods are added. We should investigate creating a standardized form parsing helper that all handlers can inherit or import, ensuring consistent behavior across the entire application.

The immediate fix for the config preview button (admin handler) worked, but this underlying inconsistency remains a technical debt item.

## 🚨 TECHNICAL DEBT: GET/POST Route Duplication

**Issue:** Multiple endpoints have redundant GET/POST routes doing the same operation, creating DRY violations and maintenance overhead.

**Example:** `/unlock-repository` has both GET and POST routes that essentially do the same thing - unlock a repository given a job parameter.

**Current Pattern:**
```python
@app.get("/unlock-repository") 
async def unlock_repository_get(job: str = Query("")):
    return handler.unlock_repository_htmx(job)

@app.post("/unlock-repository")
async def unlock_repository_post(request: Request):
    # Parse URL params to extract job
    return handler.unlock_repository_post_htmx(request)
    # Which then calls the same unlock_repository_htmx(job) method
```

**Suggested Solution:**
1. **Single endpoint approach:** Use FastAPI's flexible parameter handling to accept both GET query params and POST form data in one route
2. **Method consolidation:** One handler method that can extract parameters from either source
3. **Low risk implementation:**
   - Create new unified route alongside existing ones
   - Test thoroughly 
   - Remove old routes once confirmed working
   - Update all HTMX templates to use new unified endpoint

**Fast/Easy Implementation:**
```python
@app.api_route("/unlock-repository", methods=["GET", "POST"])
async def unlock_repository_unified(request: Request, job: str = Query(None)):
    return await handler.unlock_repository_unified_htmx(request, job)
```

**Priority:** Medium - addresses technical debt but doesn't block core functionality.

## 🚨 TECHNICAL DEBT: Duplicate Restore Service Implementations

**Issue:** Two separate restore implementations exist with overlapping functionality, creating maintenance overhead and potential inconsistencies.

**Current State:**
1. **`jobs/services/restore.py`**: Full-featured async restore service (733 lines)
   - Background execution with threading
   - Progress tracking and JSON parsing
   - Health monitoring with timeouts
   - Advanced error parsing and categorization
   - Overwrite checking with risk analysis
   - Status tracking for active restores

2. **`jobs/handlers/pages.py`**: Simpler sync restore implementation (moved from operations.py)
   - Direct synchronous execution
   - Basic form data processing  
   - Simple target path logic
   - Manual restic command building
   - Immediate response (no backgrounding)

**Problem:** Both implementations serve restore functionality but with different approaches:
- The async version (restore.py) is more sophisticated but may not be used by current UI forms
- The sync version (handlers/pages.py) is actively used by restore forms but less feature-rich
- Duplication violates DRY principle and creates maintenance burden

**Recommended Consolidation:**
1. **Research which implementation is actively used** by current restore forms/routes
2. **Merge functionality** - combine the best of both:
   - Use async background execution for UI responsiveness (from restore.py)
   - Keep form processing and validation logic (from handlers/pages.py)
   - Preserve progress tracking and error parsing (from restore.py)
3. **Single restore service** that handles both simple and complex restore scenarios
4. **Update all restore endpoints** to use the unified implementation

**Priority:** Medium-High - Multiple restore paths create confusion and maintenance issues.

**Similar Issue:** The backup services may also have duplication between `jobs/services/backup.py` implementations that should be reviewed.

## SSH Timeout Configuration (2025-09-02)

The SSHCommandFactory in `services/shared.py` supports configurable SSH connection timeouts with a sensible default of 5 seconds. Currently uses code-level configuration, but is scaffolded for future per-host timeout configuration:

**Current Implementation:**
- Default: 5 seconds (reasonable for most networks)
- Code override: `ssh_factory.build_ssh_command(..., connect_timeout=3)`
- Instance override: `SSHCommandFactory(connect_timeout=10)`

**Future Enhancement Options:**
- Per-origin/destination timeout configuration in setup forms
- Global timeout defaults in `config/local.yaml`
- Network-type-based defaults (local vs internet)

**Rationale:** 5 seconds is sufficient for TCP connection establishment on most networks, down from the previous 10-second default that made users wait unnecessarily when hosts were unreachable.

**Note:** SSH and SCP use different port flags (`-p` vs `-P`) due to OpenSSH tool conventions.

## SSH Command Consolidation (2025-09-03)

Centralized SSH command building in `services/shared.py` with `SSHCommandFactory` to eliminate 15+ instances of duplicated SSH option patterns across the codebase. Factory handles key auth, password auth (with sshpass), port configuration, and consistent timeout/security options.

**Remaining:** Complete conversion in `services/execution.py` and `dests/services/rsync.py` (see LOCAL/SSH.md).

---
