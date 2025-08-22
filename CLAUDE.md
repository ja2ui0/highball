# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync and Restic providers with full connectivity validation.

See also: @LOCAL/MODERNIZATION.md, @LOCAL/ARCHITECTURE.md, @LOCAL/DEVELOPMENT.md, @LOCAL/CONFIG-SCHEMA.md

## 🚨 CRITICAL EXECUTION PATTERNS (READ FIRST)

**CRITICAL**: The command builder factory pattern and SSH execution intelligence are fundamental to backup functionality.

### SSH vs Container Execution Intelligence

**Pattern**: `_should_use_ssh(source_config, operation_type)` determines execution context:
- **UI Operations**: Execute locally from Highball container  
- **Source Operations**: Execute via SSH+container on source host
- **Repository Operations**: Execute via SSH when source is SSH
- **Same-as-Origin Exception**: Always use SSH execution regardless of operation type

**Execution Service Usage (CRITICAL)**:
- **ALWAYS use** `ResticExecutionService.execute_restic_command()` from `services/execution.py`
- **NEVER manually call** `ResticArgumentBuilder.build_environment()` or build SSH commands directly
- Service provides automatic SSH/local context detection via `operation_type` parameter

## Primary Critical Testing Requirements

**BEFORE ANY FRAMEWORK MIGRATION**, these core systems must be tested:

1. **Real backup execution** (not just dry-run) - verify actual data transfer
2. **Restore operations with overwrite protection** - critical safety feature
3. **Notification system** (email/telegram success/failure notifications)
4. **Restic maintenance operations** (discard/prune/check scheduling and execution)
5. **Rsync patterns** - multi-provider support verification

**UI functionality** - forms, validation, basic workflows are now FULLY FUNCTIONAL.

## Core Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Stack**: Python 3.11, dataclasses, APScheduler, PyYAML, Jinja2, Docker/Podman (rootless), HTMX

### Key Principles
- **Job = Source + Destination + Definition**: Each backup job connects a source (host) to a destination (repository) with a definition (paths, schedule, settings)
- **Pure Orchestration Layer**: Highball orchestrates by SSH-ing to hosts and running binaries there
- **Container Execution Strategy**: Use official `restic/restic:0.18.0` containers on remote hosts for version consistency
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

## Known Issues & Technical Debt

- **Source Path Validation Styling**: Functional but needs UX polish
- **Dashboard Restore Status**: No polling/progress display in main job table yet

## Recent Development Context (Last 2 Days)

**2025-08-22**: Python 3.13 migration planning - identified `cgi.FieldStorage` deprecation, planned `python-multipart` replacement
**2025-08-21**: **ALL anti-patterns eliminated** - Response Service, Long Methods, and Validation Scattered completely resolved through surgical refactoring with zero breakage. ResponseUtils class eliminated 37 duplicate response method calls. Extract Method pattern reduced three 70+ line methods to 12-19 lines (54-84% complexity reduction). All core workflows now follow Single Responsibility Principle.

## Architecture Status

**Architecture Status**: Rootless containers + distributed config + schema-driven validation = **PRODUCTION READY FOUNDATION**. All major architectural migrations complete. Framework changes (FastAPI/Pydantic) are now **optional optimizations**, not requirements.

**Legacy Code Reference**: `/home/ja2ui0/src/ja2ui0/highball-main/` contains fully functional version of all features. Use as reference when implementing missing functionality - adapt patterns to current consolidated architecture rather than copying files directly.

See CHANGES.md for current session focus and detailed implementation status.

## Next Session Priority

**CRITICAL**: These core systems must be tested before any framework migration:

1. **Real Backup Execution** - Test actual backup execution (not dry-run) with data transfer verification
2. **Restore Operations** - Test complete restore workflow with overwrite protection 
3. **Notification System** - Test email/telegram notifications for job success/failure, queue functionality, template variables
4. **Restic Maintenance Operations** - Test discard/prune/check operations, scheduling, retention policies  
5. **Rsync Patterns** - Test multi-provider support and rsync execution patterns

**Future Priorities**: Kopia provider support, enhanced Restic features (progress parsing, retention policies), notification template preview
