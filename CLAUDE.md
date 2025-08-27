# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync and Restic providers with full connectivity validation.

## 🚨 CRITICAL EXECUTION PATTERNS (READ FIRST)

**CRITICAL**: The unified execution service and modular architecture are fundamental to all operations.

### Unified Execution Service (MANDATORY)

**Pattern**: ALL Restic operations MUST use `ResticExecutionService.execute_restic_command()`:
- **UI Operations**: `OperationType.UI` - Execute locally from Highball container  
- **Source Operations**: `OperationType.BACKUP` - Execute via SSH+container on source host
- **Repository Operations**: `OperationType.BROWSE/INSPECT` - Execute via SSH when source is SSH
- **Maintenance Operations**: `OperationType.MAINTENANCE/DISCARD/CHECK` - Automatic context detection

**SSH vs Container Execution Intelligence**:
- **Pattern**: `_should_use_ssh(source_config, operation_type)` determines execution context
- **Same-as-Origin Exception**: same_as_origin repositories always use SSH execution regardless of operation type
- **Container Runtime Location**: `container_runtime` field MUST be in `source_config` (not global)

**Execution Service Rules (CRITICAL)**:
- **ALWAYS use** `ResticExecutionService.execute_restic_command()` from `services/execution.py`
- **NEVER use direct** `subprocess.run()` calls for restic commands
- **ALWAYS use** `OperationType` enum - never strings for operation types
- Service provides automatic SSH/local context detection and credential handling

### Modular Architecture Discipline (MANDATORY)

**Module Separation Rules**:
- **services/**: Business logic and orchestration only  
- **models/schemas.py**: Data structure definitions only
- **models/builders.py**: Command construction logic only
- **models/forms.py**: Form parsing and validation only
- **No God Objects**: Maximum 800 lines per module, split when exceeded

### Type Safety Requirements (MANDATORY)

**Type Hint Rules**:
- **ALL function signatures** MUST have complete type hints: `def func(param: Type) -> ReturnType:`
- **Import required types**: `from typing import Dict, Any, List, Optional, Callable`
- **Use precise types**: `Dict[str, Any]` not `dict`, `Optional[str]` not `str | None`
- **Decorator typing**: Include full decorator chain types with `Callable[[...], ...]`

## Primary Critical Testing Requirements

1. **Real backup execution** (not just dry-run) - verify actual data transfer
2. **Restore operations with overwrite protection** - critical safety feature
3. **Notification system** (email/telegram success/failure notifications)
4. **Restic maintenance operations** (discard/prune/check scheduling and execution)
5. **Rsync patterns** - multi-provider support verification

## Core Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Stack**: Python 3.13, FastAPI, Pydantic, APScheduler, PyYAML, Jinja2, Docker/Podman (rootless), HTMX

### Key Principles
- **Job = Source + Destination + Definition**: Each backup job connects a source (host) to a destination (repository) with a definition (paths, schedule, settings). Definitions contain one or more paths with per-path include/exclude rules.
- **Pure Orchestration Layer**: Highball orchestrates by SSH-ing to hosts and running binaries there
- **Container Execution Strategy**: Use official `restic/restic:0.18.0` containers on remote hosts for version consistency. **CRITICAL**: `restic/restic:0.18.0` has `restic` as entrypoint - container commands use `-r repository command` NOT `restic -r repository command`.
- **Schema-Driven Everything**: Secret management, validation, and form rendering all use schema definitions
- **Rootless Container Architecture**: LinuxServer.io-style user management with runtime PUID/PGID support

## Features

**Job Management**: Full CRUD, validation, cron scheduling, per-job conflict avoidance, multi-path sources
**Scheduling**: Runtime conflict detection, automatic queuing, configurable defaults
**Notifications**: Telegram/email with spam-prevention queuing, per-job integration, template variables
**UI**: Schema-driven HTMX forms, real-time validation, per-job inspection hubs (`/inspect?name=<jobname>`)
**Restic Integration**: Repository connectivity testing, complete repository browser, three-mode maintenance system (auto/user/off)
**Backup Browser**: Multi-provider system supporting Restic snapshots and filesystem directories
**Restore System**: Complete functionality with intelligent overwrite protection, dual restore targets, dry run capability
**REST API**: GET `/api/highball/jobs` endpoint for external dashboard widgets with query filtering
**Debug System**: System debugging interface (`/dev`) with network scanner and unified log sources
**Scheduler Debug**: GET `/jobs` endpoint shows APScheduler internal jobs (debug/admin only - distinct from `/api/highball/jobs` which shows backup job configs)

## Architecture Status

**✅ COMPLETED IMPLEMENTATIONS**:
- **Unified Execution Service** - All Restic operations use consistent execution patterns
- **Modular Architecture** - God Object eliminated, focused single-responsibility modules  
- **Complete Type Safety** - 100% type hint coverage across all function signatures
- **Enum-based Operations** - Type-safe operation types throughout execution layer
- **FastAPI/Pydantic** - 100% modernization with zero legacy remnants, Python 3.13 ready
- **Rootless Containers** - PUID/PGID support (Docker + Podman compatible)
- **Distributed Config Hierarchy** - Job-scoped secret isolation (`/config/local/` structure)
- **Schema-Driven Validation** - Zero hardcoded field requirements, unified validation paths
- **SSH Origin Management** - Complete HTMX-based SSH key and host management system
- **Same-as-Origin Repository** - Support for local rollbacks on source host filesystem
- **Anti-Pattern Elimination** - Response Service and Extract Method patterns established

**Technical Foundation**: Python 3.13, FastAPI, Pydantic, comprehensive typing, modular services

## Development Discipline (MANDATORY)

**Code Quality Standards** - These patterns are REQUIRED for all changes:

1. **Execution Consolidation**: Use `ResticExecutionService.execute_restic_command()` for ALL restic operations
2. **Module Size Limits**: Split any module exceeding 800 lines into focused components
3. **Complete Type Hints**: Every function signature must have parameter and return type annotations
4. **Enum Usage**: Use `OperationType` enum constants, never operation type strings
5. **Single Responsibility**: Each module handles one architectural concern only

### Critical HTMX Patterns (DOM-Safe Targeting)

**NEVER target parent containers that contain the triggering button** - causes DOM corruption and HTMX re-scanning failures:

**Multi-Path Source Management**:
- **Add Operation**: Button targets child list (`#source_paths_list`) with `hx-swap="beforeend"` to append new entries
- **Remove Operation**: Button targets own container (`#path_entry_{{ index }}`) with `hx-swap="outerHTML"` for clean removal
- **Form Array Safety**: HTML forms auto-reindex `name="field[]"` arrays, eliminating index gaps from removals
- **Protection**: Path 0 never shows remove button (`{% if path_index > 0 %}`), ensuring at least one path remains

### Response Handling Architecture

**ResponseUtils Class**: Centralized HTTP response handling in `handlers/api.py` eliminates duplication across all handler classes:
- **Unified Interface**: `send_html_response()`, `send_json_response()`, `send_redirect()`, `send_htmx_partial()`, `send_error()`, `send_htmx_error()`
- **Separation of Concerns**: HTTP response logic stays in handlers layer, template rendering stays in services layer

### Anti-Pattern Detection

**Future Claude Detection**: If you see multiple methods with identical try/catch/return error blocks, immediately flag this as an anti-pattern and refactor to decorator + exception pattern.

**When making changes**:
- Check module line counts after edits - split if >800 lines
- Add type hints to any new functions immediately  
- Use existing service patterns - don't create new execution paths
- Test functionality after architectural changes (`./rr` then verify API)
- Follow established import patterns (`from typing import...`)

### Development Environment & Authority

**Development Environment**: Claude runs in distrobox container with package installation capabilities.

**Decision Authority**: 
- **Claude**: Owns technical implementation decisions (patterns, algorithms, code structure)
- **Shane**: Tech director/product manager - owns design decisions, architectural direction, product requirements
- **When uncertain** about design preferences or high-level architecture, ask before implementing rather than having changes aborted for clarification
- **Present options with reasoned recommendations** - not just choices, but grounded opinions based on sound practice and project cohesiveness

**Context Management**: Two-file documentation workflow:
- **CLAUDE.md** (permanent): architecture, patterns, rules, technical debt
- **CHANGES.md** (temporal): current session focus, progress, technical notes, next priorities  
- **Session end**: fold architectural insights into CLAUDE.md, update CHANGES.md for next session
- **Post-compression**: feed both files to restore complete context efficiently

**Live Testing Environment**: Against `yeti.home.arpa` with actual restic repository at `rest:http://yeti.home.arpa:8000/yeti`

## How to Find Things (Navigation Guide)

### Core Business Logic
- **Backup Execution**: `services/execution.py` - `ResticExecutionService.execute_restic_command()`
- **Job Scheduling**: `services/scheduling.py` - APScheduler integration and conflict detection  
- **Restore Operations**: `services/restore.py` - Provider-agnostic restore orchestration
- **Repository Management**: `services/repositories.py` - Repository abstraction and browsing
- **Maintenance Operations**: `services/maintenance.py` - Automated cleanup and health checks

### HTTP & UI Layer
- **FastAPI Routes**: `app.py` - All HTTP endpoints and route definitions
- **Page Handlers**: `handlers/pages.py` - HTML page rendering logic
- **API Handlers**: `handlers/api.py` - JSON endpoints and ResponseUtils class
- **Form Processing**: `handlers/forms.py` - HTMX form submission handling
- **Templates**: `templates/` - Jinja2 templates with schema-driven rendering

### Data Models & Validation  
- **Pydantic Models**: `models/forms.py`, `models/backup.py` - Type-safe data structures
- **Validation Logic**: `models/validation.py` - Schema-driven validation methods
- **Schema Definitions**: `models/schemas.py` - Field definitions and requirements

### Configuration & Secrets
- **Global Settings**: `/config/local/local.yaml` - App-wide configuration
- **Job Configs**: `/config/local/jobs/{job_name}.yaml` - Individual job definitions  
- **Job Secrets**: `/config/local/secrets/jobs/{job_name}.env` - Environment variables
- **SSH Origins**: `/config/local/origins/{origin_name}.yaml` - SSH host configurations
- **Config Loading**: `config.py` - YAML parsing and secret merging

### Key Files by Function
- **Container Execution**: `services/execution.py` - Restic container orchestration
- **SSH Operations**: `services/ssh.py` - SSH connection and key management
- **HTMX Patterns**: `templates/partials/` - Dynamic form components
- **Scheduling**: `services/scheduling.py` - Cron job management
- **Logging**: `/var/log/highball/` - Operational logs and status files

**NEVER USE THE TERM PRODUCTION READY OR GIVE ARBITRARY TIME ESTIMATES TO SHANE**
**NEVER USE EMOJI IN THE CODEBASE**

**TODO**: Refactor `check_repository_availability_htmx()` and `unlock_repository_htmx()` in jobs/handlers/pages.py - these are 90% restic destination operations with job coordination wrapper, violates SoC by mixing job orchestration with destination-specific repository logic
**TODO**: Refactor `scan_network_for_rsyncd()` in dests/handlers/pages.py - move core nmap scanning logic to dests/services/rsyncd.py for proper SoC (network discovery vs HTTP handling)


- note: validate_origin_repo_path_htmx() (dests handler) should just make the user pick an origin from a dropdown.