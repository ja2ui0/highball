# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync and Restic providers with full connectivity validation.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging, dataclass-driven configuration

**Rule: Job = Source + Destination + Definition**: Each backup job connects a source (host) to a destination (repository) with a definition (paths, schedule, settings). Definitions contain one or more paths with per-path include/exclude rules. This architecture balances user workflow simplicity with granular control and tool efficiency.

**Rule: Pure Orchestration Layer**: Highball orchestrates backup/restore operations by SSH-ing to hosts and running binaries there. Backup: SSH to source host → run restic/rsync → direct to destination. Restore: SSH to target host → run restic restore → files appear on target. Exception: Highball can restore to itself at `/restore` when source hosts no longer exist (designed for bind-mount persistence). This design enables ANY host to ANY destination with Highball providing coordination, not data intermediation.

**Rule: Container Execution Strategy**: Use official `restic/restic:0.18.0` containers on remote hosts to solve version mismatch problems. Remote hosts may have outdated restic versions (e.g., 0.16.4 missing `--dry-run` for restore) while Highball has 0.18.0. Container execution ensures version consistency across all operations. SSH validation auto-detects docker/podman availability and populates `container_runtime` in job config. **CRITICAL**: `restic/restic:0.18.0` has `restic` as entrypoint - container commands use `-r repository command` NOT `restic -r repository command`.

**Rule: DRY Principle & Provider Separation**: Don't Repeat Yourself. RestoreHandler orchestrates provider-agnostic operations (overwrite detection, validation, progress tracking). Provider-specific runners (ResticRunner, future BorgRunner/KopiaRunner) handle command building and execution. SSH patterns, authentication, environment management shared across all operations. This separation enables cohesive multi-provider support without code duplication.

**Rule: Just In Time, Progressive Disclosure**: User sees what they need when they need it. Ask only what can't be inferred. Do not overwhelm with choices.

**Stack**: Python 3.11 (dataclasses, pathlib, validators, notifiers), APScheduler, PyYAML, Docker, rsync/SSH

## Architecture Overview

### Core System
- `app.py` (routing), `config.py` (YAML config)

### HTTP Layer (handlers/)
- **Job Management**: `job_manager.py`, `dashboard.py`, `inspect_handler.py`
- **Backup/Restore**: `backup.py`, `backup_executor.py`, `restore_handler.py`
- **Provider Handlers**: `restic_handler.py`, `filesystem_handler.py` 
- **Form Parsing**: `*_form_parser.py` (SSH, Restic, local, rsyncd, notification)
- **Utilities**: `logs.py`, `config_handler.py`, `api_handler.py`, `network.py`

### Business Logic (services/)
- **Validation**: `job_validator.py`, `restic_validator.py`, `source_path_validator.py`, `ssh_validator.py`
- **Execution**: `restic_runner.py`, `backup_client.py`, `*_repository_service.py`
- **Infrastructure**: `notification_service.py` (coordinator), `scheduler_service.py`, `job_logger.py`
- **Notification System**: `notification_provider_factory.py`, `notification_message_formatter.py`, `notification_sender.py`, `notification_job_config_manager.py`, `notification_queue_coordinator.py`
- **Restore System**: `RestoreExecutionService`, `RestoreOverwriteChecker`, `RestoreErrorParser`
- **Maintenance**: `restic_maintenance_service.py` + 7 specialized services for repository maintenance (discard/check operations)
- **HTMX Form System**: `htmx_field_renderer.py`, `htmx_validation_coordinator.py`, `htmx_restic_renderer.py`, `htmx_source_path_manager.py`, `htmx_log_manager.py`, `htmx_config_manager.py`, `htmx_maintenance_manager.py`, `htmx_rsyncd_manager.py`, `htmx_notifications_manager.py`
- **Support**: `template_service.py`, `job_form_data_builder.py`, `binary_checker_service.py`

### Frontend (static/)
- **Core Features**: `backup-browser.js` (697 lines - file tree navigation), `restore-core.js` + `restore-restic.js` (progress tracking, restore system), `job-inspect.js` (inspection hub, reduced from 265→215 lines)
- **Utilities**: `nav.js`, `network-scan.js`
- **HTMX Migration Complete**: 51% JavaScript reduction (2,898→1,406 lines) - all form operations now server-side HTMX

## Data Storage

**Config** (user-facing): `/config/config.yaml` - jobs, global settings, deleted jobs
**Operational** (file-based logging):
- `/var/log/highball/job_status.yaml` - last-run status per job  
- `/var/log/highball/jobs/{job_name}.log` - detailed execution logs
- `/var/log/highball/job_validation.yaml` - SSH validation timestamps
- `/var/log/highball/running_jobs.txt` - currently running jobs for conflict detection
- `/var/log/highball/deleted_jobs.yaml` - deleted job tracking with timestamps (separate from config)
- `/var/log/highball/notification_queues/{provider}_state.yaml` - notification queue state and pending messages

## Features

**Job Management**: Full CRUD, validation, cron scheduling, per-job conflict avoidance, custom rsync options, multi-path sources
**Scheduling**: Runtime conflict detection, automatic queuing, configurable defaults
**Logging**: Per-job logs, SSH validation caching (30min), refresh-based viewing
**Notifications**: `notifiers` library backend, Telegram/email, spam-prevention queuing with configurable intervals, batch message formatting, per-job integration with template variables, test capabilities, emoji-free. Modular 6-service architecture with `notify_on_success` configured per-job (not global)
**UI**: HTMX server-side forms, real-time validation, share discovery, theming, password toggles, multi-path management, per-job inspection hubs (`/inspect?name=<jobname>`), source path validation buttons with [OK]/[WARN]/[ERROR] feedback
**Restic Integration**: Repository connectivity testing, binary availability checking, existing repository detection, content fingerprinting, complete repository browser with snapshot statistics and file tree navigation
**Backup Browser**: Multi-provider backup browsing system supporting Restic (repository snapshots), rsync/SSH/local/rsyncd (filesystem directories) with unified interface, provider-specific terminology, and expandable file trees
**Restore System**: Complete Restic restore functionality with intelligent overwrite protection, dual restore targets (safe Highball `/restore` vs. risky source location), pre-flight risk assessment via `/check-restore-overwrites` endpoint, progressive disclosure confirmation system (no modals), dry run capability (default enabled), background execution with progress tracking, and modular JavaScript architecture extensible to future providers (rsync, borg, kopia) - full implementation with smart safety controls
**REST API**: GET `/api/highball/jobs` endpoint for external dashboard widgets with query filtering (`state`, `fields`), CORS support, and authentication-ready architecture
**Debug System**: System debugging interface (`/dev`) with network scanner, 8 unified log sources (system + operational) with organized 2-row layout, separated from per-job inspection

## Common Patterns

### Container Execution Strategy
- Use official `restic/restic:0.18.0` containers on remote hosts for version consistency
- SSH validation auto-detects docker/podman availability, populates `container_runtime` in job config
- **Unified container execution** for all SSH Restic operations: init, backup, and restore via `CommandExecutionService`
- Local operations use direct subprocess execution as designed for container-centric workflows

### Form Processing Architecture
- **HTMX Server-Side Rendering**: All form operations use server-side HTMX with 13 modular services
- **Modular Services**: Single responsibility - field rendering, validation coordination, provider-specific operations
- **Thin Coordinators**: Handlers reduced to coordination only (e.g., 284→35 lines in HTMX form handler)
- Multipart form data throughout (not URL-encoded)
- Dedicated parsers per destination type (`*_form_parser.py`)
- Source paths as array format: `[{'path': '/path', 'includes': [], 'excludes': []}]`
- **Parser Resilience Pattern**: Skip empty paths instead of failing (prevents UI errors from default empty form fields)
- **Error Data Preservation Pattern**: Use parsed config from payload over raw form data when available (validation errors retain all user input)
- **Template Variables Pattern**: Server data via HTML data attributes to JavaScript (eliminates inline server variables)

### Validation Patterns
- Real-time validation with dedicated endpoints (`/validate-*`)
- 30-minute SSH validation caching to avoid repeated connection tests
- Permission checking: RX (backup capable), RWX (restore-to-source capable)
- Validators in `services/` (business logic), handlers only coordinate HTTP

### Frontend Architecture
- **HTMX-First**: All form operations use server-side HTMX rendering (51% JavaScript reduction: 2,898→1,406 lines)
- **Remaining JavaScript**: Stable, functional features - `backup-browser.js` (file tree), `restore-core.js` (progress tracking), utilities
- No inline scripts in templates - external modules only
- **Data Flow Pattern**: Server data flows through HTML data attributes to JavaScript (e.g., `data-source-paths='{{SOURCE_PATHS_JSON}}'` → `container.dataset.sourcePaths`)
- Provider-agnostic patterns for multi-backup-type support

### UI Patterns
- Progressive disclosure (show complexity when needed)
- Per-job inspection hubs (`/inspect?name=<jobname>`) replace separate pages
- Conditional UI elements (e.g., init button appears only for empty repositories)
- No modals - inline confirmation flows instead

## Known Issues & Technical Debt

- **Source Path Validation Styling**: Functional but needs UX polish
- **Dashboard Restore Status**: No polling/progress display in main job table yet

## Development Rules (Critical - Reference First)

### Environment & Workflow

**Development Environment**: Claude runs in distrobox container with package installation capabilities. Use `./rr` for rebuild/restart during development iterations.
**Testing Paradigm**: Create unit tests before human testing for dramatic subsystem changes. Test files in `tests/` with mocking patterns to avoid dependency issues. Sequence: unit tests → implementation → human integration testing. Use `test_*_standalone.py` for comprehensive pipeline testing with proper component isolation.
**Decision Authority**: Claude owns technical implementation decisions (patterns, algorithms, code structure). Shane is tech director/product manager - owns design decisions, architectural direction, and product requirements. When uncertain about design preferences or high-level architecture, ask before implementing rather than having changes aborted for clarification. **Present options with reasoned recommendations** - not just choices, but grounded opinions based on sound practice and project cohesiveness.
**Context Management**: Two-file documentation workflow. **CLAUDE.md** (permanent): architecture, patterns, rules, technical debt. **CHANGES.md** (temporal): current session focus, progress, technical notes, next priorities. Session end: fold architectural insights into CLAUDE.md, update CHANGES.md for next session. Post-compression: feed both files to restore complete context efficiently.

### Code Architecture
**Separation of Concerns**: Thin handlers (HTTP coordination), fat services (business logic), validators in `services/` not `handlers/`
**Modularization**: Proactively break up monolithic components. Single responsibility principle. Extract when files exceed ~500 lines. HTMX form system exemplifies this with 13 specialized services replacing JavaScript form complexity.
**Data Structures**: Dataclasses everywhere, `pathlib.Path` operations, type hints
**Multi-provider Pattern**: `services/<engine>_repository_service.py` + `services/<engine>_validator.py` + form parsers

### Frontend Standards
**HTMX**: Server-side form rendering preferred. JavaScript only for complex interactive features (file trees, progress tracking)
**JavaScript**: Always in `/static/` files, never inline in templates. Modular single-responsibility architecture.
**CSS**: Colors ONLY in `/static/themes/{theme}.css`. Structure ONLY in `/static/style.css`
**Assets**: External only - no emoji, no inline styles/scripts
**Forms**: HTMX server-side rendering, multipart form data, dedicated parsers, real-time validation

### Code Quality
**Standards**: PEP 8, emoji-free, external assets only
**Dependencies**: `dataclasses`, `pathlib`, `validators`, `croniter`, `notifiers`
**Testing**: Standalone tests in `tests/` with mocking patterns. HTMX form tests (`test_htmx_form_system.py`) replace deprecated JavaScript form tests. Use `test_*_standalone.py` for isolated unit tests.
**Containers**: Official containers only (`restic/restic`, future `kopia/kopia`)

## Theming System

**Architecture**: Base + Theme separation - `/static/style.css` (structure) + `/static/themes/{theme}.css` (colors only)
**Loading**: Automatic via `TemplateService` - `{{THEME_CSS_PATH}}` variable
**Configuration**: `global_settings.theme` (default: "dark")
**Core Themes**: `dark.css` and `light.css` (maintained in development)
**Community Themes**: gruvbox, solarized, tokyo-night variants (not tracked in development)
**Extension**: New themes = new CSS file with color variables

## Architecture Reference (Quick Lookup)

**Templates**: `{{INCLUDE:filename}}` directives, `job_form.html` orchestrates
**Data**: Dataclasses for all structures (`JobFormData`, `SourceConfig`, `DestConfig`), `pathlib.Path` operations
**Validation**: SSH 30min cache, `validators` module, centralized in `services/job_validator.py`, `services/restic_validator.py`, `services/source_path_validator.py`
**Forms**: HTMX server-side rendering, sectioned UI, dedicated parsers per destination (`_safe_get_value`), inline error display (`FormErrorHandler`)
**UI Paradigm**: Per-job inspection hubs (`/inspect?name=<jobname>`) consolidate logs, status, backup browser, and restore controls into unified interfaces (paradigm shift from separate pages)
**Container Execution**: Unified container execution for all SSH Restic operations (init, backup, restore) using `CommandExecutionService` with official `restic/restic:0.18.0` containers.
**Backup Browser**: Multi-provider PROVIDERS config (repository vs filesystem), unified JS interface
**Backup Execution**: Separated concerns - `BackupExecutor`, `BackupCommandBuilder`, `BackupConflictHandler`, `BackupNotificationDispatcher`
**Restore**: Modular architecture - thin `RestoreHandler` coordinator (140 lines) + specialized services (`RestoreExecutionService`, `RestoreOverwriteChecker`, `RestoreErrorParser`)
**Notifications**: Modular 6-service architecture - coordinator + specialized services for provider factory, message formatting, sending, job config, queue coordination
**API**: Query filtering, CORS, field selection, JSON responses, authentication-ready
**Maintenance System**: Modular 8-service architecture for Restic repository maintenance (discard/check operations), auto-enabled with safe defaults, progressive disclosure UI ready
**Testing**: Unit coverage with mocking patterns, 22 maintenance tests with 100% pass rate
**Development Environment**: Live testing against `yeti.home.arpa` with actual restic repository at `rest:http://yeti.home.arpa:8000/yeti` (not example data)

## Commands

**Run**: `./rr` (intelligent rebuild and restart)
**Multi-arch**: `./rr multi` (build multiarch image for distribution)
**Debug**: `docker logs -f highball`
**Test Notifications**: `./test_notifications.py`
**Test Units**: `python3 -m unittest tests.test_form_error_handler -v`

## Configuration Schema (User-facing Only)

```yaml
global_settings:
  scheduler_timezone: "UTC"  # default UTC, configurable
  theme: "dark"  # UI theme (dark, light, gruvbox, etc.)
  default_schedule_times:
    hourly: "0 * * * *"     # top of every hour
    daily: "0 3 * * *"      # 3am daily
    weekly: "0 3 * * 0"     # 3am Sundays
    monthly: "0 3 1 * *"    # 3am first of month
  enable_conflict_avoidance: true  # wait for conflicting jobs before running
  conflict_check_interval: 300     # seconds between conflict checks
  delay_notification_threshold: 300  # send notification after this many seconds delay
  notification:
    telegram:
      enabled: false              # enable/disable telegram notifications
      notify_on_success: false    # send telegram notifications for successful jobs
      token: ""                   # bot token from @BotFather
      chat_id: ""                 # chat ID for notifications
    email:
      enabled: false              # enable/disable email notifications
      notify_on_success: false    # send email notifications for successful jobs
      smtp_server: ""             # SMTP server hostname
      smtp_port: 587              # 587 for TLS, 465 for SSL
      use_tls: true               # use TLS encryption (mutually exclusive with SSL)
      use_ssl: false              # use SSL encryption
      from_email: ""              # sender email address
      to_email: ""                # recipient email address
      username: ""                # SMTP authentication username
      password: ""                # SMTP authentication password
  maintenance:
    discard_schedule: "0 3 * * *"         # daily at 3am - combines forget+prune operations
    check_schedule: "0 2 * * 0"           # weekly Sunday 2am (staggered from backups)
    retention_policy:
      keep_last: 7                        # always keep last 7 snapshots regardless of age
      keep_hourly: 6                      # keep 6 most recent hourly snapshots
      keep_daily: 7                       # keep 7 most recent daily snapshots  
      keep_weekly: 4                      # keep 4 most recent weekly snapshots
      keep_monthly: 6                     # keep 6 most recent monthly snapshots
      keep_yearly: 0                      # disable yearly retention by default
    check_config:
      read_data_subset: "5%"              # balance integrity vs performance

backup_jobs:
  job_name:
    source_type: "ssh|local"
    source_config: 
      hostname: "hostname" 
      username: "username"
      source_paths:  # multi-path support
        - path: "/path/one"
          includes: ["*.txt"]
          excludes: ["temp/"]
        - path: "/path/two"
          includes: []
          excludes: ["*.log"]
    dest_type: "ssh|local|rsyncd|restic"  # restic fully functional
    dest_config: {hostname, share} | {repo_type, repo_uri, password}  # explicit destinations
    schedule: "daily|weekly|hourly|monthly|cron_pattern"
    enabled: true
    respect_conflicts: true     # wait for conflicting jobs (default: true)
    container_runtime: "docker|podman"  # detected during SSH validation, used for restic container execution
    auto_maintenance: true              # automatic repository maintenance (default: true, Restic only)
    # Optional per-job maintenance overrides:
    # maintenance_discard_schedule: "0 4 * * *"     # custom discard schedule
    # retention_policy: {keep_last: 10, ...}        # custom retention policy
    # maintenance_check_schedule: "0 1 * * 0"       # custom check schedule

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

## Roadmap

**Completed 2025-08-17**: 
1. ✅ **HTMX Form System Migration** - 51% JavaScript reduction (2,898→1,406 lines), complete form consistency with 13 modular services
2. ✅ **Critical Bug Fixes** - Template rendering artifacts resolved, form data preservation fixed
3. ✅ **Test Infrastructure Modernization** - HTMX-focused tests, deprecated JavaScript form tests retired

**Completed 2025-08-16**: 
1. ✅ **Container-Based Backup Execution** - Unified container execution for all SSH Restic operations via `CommandExecutionService`
2. ✅ **Comprehensive Unit Testing** - Full pipeline test coverage with proper mocking and component isolation
3. ✅ **Critical Container Command Fix** - Removed duplicate `restic` command from container execution; `restic/restic:0.18.0` has `restic` as entrypoint
4. ✅ **JavaScript Standards Compliance** - Extracted all embedded JavaScript from templates to external `/static/` files with modular architecture
5. ✅ **Backup Logging Enhancement** - Fixed logging to show actual container commands executed instead of simplified restic commands for debugging
6. ✅ **Command Obfuscation Utility** - Created centralized `services/command_obfuscation.py` for DRY password masking across handlers
7. ✅ **Notification System Modularization** - Complete refactor from 552-line monolith to 6 specialized services with 63% coordinator reduction
8. ✅ **RestoreHandler Modularization** - 660-line monolith → thin coordinator (140 lines) + specialized services
9. ✅ **Restic Repository Maintenance System** - Production-ready maintenance architecture with 8 modular services, safe defaults, and comprehensive test coverage

**Current Priorities**:
1. **Dashboard Status Integration** - Add restore status polling and display "Restoring... N%" in main dashboard job table  
2. **UX Polish** - Source path validation styling improvements

## Recent Development Context

**2025-08-17**: HTMX form system migration achieved 51% JavaScript reduction with 13 modular services, critical template rendering bugs fixed, test infrastructure modernized
**2025-08-16**: Container execution unified, notification system modularized (6 services), RestoreHandler refactored, maintenance system completed
**2025-08-15**: Repository initialization and validator architecture refactored, container execution strategy foundations implemented

See CHANGES.md for current session focus and detailed implementation status.

## Next Session Priority

1. **Dashboard Status Integration** - Add restore status polling and display "Restoring... N%" in main dashboard job table  
2. **UX Polish** - Source path validation styling improvements

**Future Priorities**: Kopia provider support, enhanced Restic features (progress parsing, retention policies), notification template preview 
