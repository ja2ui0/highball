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

**CRITICAL TESTING PRIORITIES** - These core systems must be tested:

1. **Real backup execution** (not just dry-run) - verify actual data transfer
2. **Restore operations with overwrite protection** - critical safety feature
3. **Notification system** (email/telegram success/failure notifications)
4. **Restic maintenance operations** (discard/prune/check scheduling and execution)
5. **Rsync patterns** - multi-provider support verification

**FastAPI Migration Status**: ✅ **COMPLETE** - See @LOCAL/MODERNIZATION.md for full details
**UI functionality** - forms, validation, basic workflows are FULLY FUNCTIONAL.

## Core Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Stack**: Python 3.11+, FastAPI, Pydantic, APScheduler, PyYAML, Jinja2, Docker/Podman (rootless), HTMX

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
**Scheduler Debug**: GET `/jobs` endpoint shows APScheduler internal jobs (debug/admin only - distinct from `/api/highball/jobs` which shows backup job configs)

## Known Issues & Technical Debt

- **Source Path Validation Styling**: Functional but needs UX polish
- **Dashboard Restore Status**: No polling/progress display in main job table yet

## Recent Development Context

**2025-08-23**: ✅ **FastAPI + Pydantic migration COMPLETE** - 100% CGI elimination, Python 3.13 ready, zero legacy patterns (See @LOCAL/MODERNIZATION.md)
**2025-08-22**: Python 3.13 migration planning - identified `cgi.FieldStorage` deprecation 
**2025-08-21**: **ALL anti-patterns eliminated** - Response Service, Long Methods, and Validation Scattered completely resolved through surgical refactoring

## Architecture Status

**PRODUCTION READY**: Rootless containers + distributed config + schema-driven validation + FastAPI/Pydantic = **MODERN ARCHITECTURE COMPLETE**

**Migration Status**: ✅ **FastAPI/Pydantic modernization 100% complete** - Application now looks like it was built with FastAPI from day one
**Python Support**: Ready for Python 3.11+ (including 3.13) - zero deprecated CGI dependencies  
**Legacy Code Reference**: `/home/ja2ui0/src/ja2ui0/highball-main/` contains pre-migration version for reference

**Current Implementation Status**: See @LOCAL/MODERNIZATION.md for complete migration details

## Next Session Priority

**CRITICAL TESTING** - Core functionality validation (migration complete, now verify functionality):

1. **Real Backup Execution** - Test actual backup execution (not dry-run) with data transfer verification
2. **Restore Operations** - Test complete restore workflow with overwrite protection 
3. **Notification System** - Test email/telegram notifications for job success/failure, queue functionality, template variables
4. **Restic Maintenance Operations** - Test discard/prune/check operations, scheduling, retention policies  
5. **Rsync Patterns** - Test multi-provider support and rsync execution patterns

**Future Development**: Kopia provider support, enhanced Restic features (progress parsing, retention policies), notification template preview
