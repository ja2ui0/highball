# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync and Restic providers with full connectivity validation.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging, dataclass-driven configuration

**Rule: Job = Source + Destination + Definition**: Each backup job connects a source (host) to a destination (repository) with a definition (paths, schedule, settings). Definitions contain one or more paths with per-path include/exclude rules. This architecture balances user workflow simplicity with granular control and tool efficiency.

**Rule: Pure Orchestration Layer**: Highball orchestrates backup/restore operations by SSH-ing to hosts and running binaries there. Backup: SSH to source host → run restic/rsync → direct to destination. Restore: SSH to target host → run restic restore → files appear on target. Exception: Highball can restore to itself at `/restore` when source hosts no longer exist (designed for bind-mount persistence). This design enables ANY host to ANY destination with Highball providing coordination, not data intermediation.

**Rule: Container Execution Strategy**: Use official `restic/restic:0.18.0` containers on remote hosts to solve version mismatch problems. Remote hosts may have outdated restic versions (e.g., 0.16.4 missing `--dry-run` for restore) while Highball has 0.18.0. Container execution ensures version consistency across all operations. SSH validation auto-detects docker/podman availability and populates `container_runtime` in job config.

**Rule: DRY Principle & Provider Separation**: Don't Repeat Yourself. RestoreHandler orchestrates provider-agnostic operations (overwrite detection, validation, progress tracking). Provider-specific runners (ResticRunner, future BorgRunner/KopiaRunner) handle command building and execution. SSH patterns, authentication, environment management shared across all operations. This separation enables cohesive multi-provider support without code duplication.

**Rule: Just In Time, Progressive Disclosure**: User sees what they need when they need it. Ask only what can't be inferred. Do not overwhelm with choices.

**Stack**: Python 3.11 (dataclasses, pathlib, validators, notifiers), APScheduler, PyYAML, Docker, rsync/SSH

## Key Components

**Core**: `app.py` (routing), `config.py` (YAML config)
**Handlers**: `backup.py` (modular execution orchestration), `backup_executor.py` (core backup execution), `backup_command_builder.py` (rsync command construction with multi-path support), `restic_command_builder.py` (restic command construction), `command_builder_factory.py` (routing commands to providers), `backup_conflict_handler.py` (conflict management), `backup_notification_dispatcher.py` (notification handling), `job_manager.py` (CRUD), `job_validator.py` (validation), `logs.py` (system debug log viewer), `inspect_handler.py` (per-job inspection and restore UI), `restore_handler.py` (complete Restic restore execution with progress tracking), `restic_handler.py` (Restic management), `filesystem_handler.py` (backup-agnostic filesystem browsing), `api_handler.py` (REST API for external integrations), `restic_validator.py` (connectivity validation), `restic_form_parser.py`, `ssh_form_parser.py`, `local_form_parser.py`, `rsyncd_form_parser.py`, `notification_form_parser.py` (modular form parsing), `form_error_handler.py` (inline error display), `job_display.py` (dashboard formatting), `dashboard.py` (modularized coordinator), `config_handler.py` (global configuration management), `notification_test_handler.py` (notification testing), `network.py` (network scanning), `job_scheduler.py` (job scheduling)
**Services**: `job_logger.py` (pathlib-based logging), `ssh_validator.py` (modern validation with caching), `scheduler_service.py`, `job_conflict_manager.py` (runtime conflicts), `notification_service.py` (notifiers library backend), `notification_queue_service.py` (queue management), `form_data_service.py` (modular template generation), `restic_runner.py` (command execution), `restic_content_analyzer.py` (content fingerprinting), `backup_client.py` (generic SSH/local execution), `repository_service.py` (abstract base for providers), `restic_repository_service.py` (Restic implementation), `filesystem_service.py` (rsync filesystem browsing), `binary_checker_service.py` (multi-binary support), `template_service.py` (template rendering), `schedule_loader.py` (schedule management)
**Static Assets**: Modular JavaScript architecture with `job-form-core.js` (utilities), `job-form-ssh.js` (SSH validation), `job-form-rsyncd.js` (rsync discovery), `job-form-restic.js` (Restic management), `job-form-globals.js` (compatibility), `config-manager.js` (settings UI), `config-notifications.js` (notification testing), `network-scan.js` (rsync discovery), `backup-browser.js` (multi-provider backup browsing), `restore-core.js` (generic restore UI and provider orchestration), `restore-restic.js` (Restic-specific restore implementation), `job-inspect.js` (per-job inspection interface), `nav.js` (navigation)

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
**Notifications**: `notifiers` library backend, Telegram/email, spam-prevention queuing with configurable intervals, batch message formatting, test capabilities, emoji-free
**UI**: Sectioned forms, real-time validation, share discovery, theming, password toggles, multi-path management
**Restic Integration**: Repository connectivity testing, binary availability checking, existing repository detection, content fingerprinting, complete repository browser with snapshot statistics and file tree navigation
**Backup Browser**: Multi-provider backup browsing system supporting Restic (repository snapshots), rsync/SSH/local/rsyncd (filesystem directories) with unified interface, provider-specific terminology, and expandable file trees
**Restore System**: Complete Restic restore functionality with intelligent overwrite protection, dual restore targets (safe Highball `/restore` vs. risky source location), pre-flight risk assessment via `/check-restore-overwrites` endpoint, progressive disclosure confirmation system (no modals), dry run capability (default enabled), background execution with progress tracking, and modular JavaScript architecture extensible to future providers (rsync, borg, kopia) - full implementation with smart safety controls
**REST API**: GET `/api/highball/jobs` endpoint for external dashboard widgets with query filtering (`state`, `fields`), CORS support, and authentication-ready architecture
**Debug System**: System debugging interface (`/dev`) with network scanner, 8 unified log sources (system + operational) with organized 2-row layout, separated from per-job inspection

## Development Rules (Critical - Reference First)

**Development Environment**: Claude runs in distrobox container with package installation capabilities. Use `./rr` for rebuild/restart during development iterations.
**Testing Paradigm**: Create unit tests before human testing for dramatic subsystem changes. Test files in `tests/` with mocking patterns to avoid dependency issues. Sequence: unit tests → implementation → human integration testing.
**Decision Authority**: Claude owns technical implementation decisions (patterns, algorithms, code structure). Human is tech director/product manager - owns design decisions, architectural direction, and product requirements. When uncertain about design preferences or high-level architecture, ask before implementing rather than having changes aborted for clarification. **Present options with reasoned recommendations** - not just choices, but grounded opinions based on sound practice and project cohesiveness.
**JavaScript**: Always in `/static/` files, never inline in templates. Use modular 5-file architecture with single responsibility per component
**CSS**: Colors ONLY in `/static/themes/{dark,light}.css`. Structure ONLY in `/static/style.css` 
**Architecture**: Proactively modularize components when they become monolithic. Thin handlers, centralized validation, dataclass-driven config
**Code Standards**: PEP 8, dataclasses, pathlib, type hints, emoji-free, external assets only
**Extensions**: Multi-provider pattern via `services/<engine>_repository_service.py` + `handlers/<engine>_validator.py` + form parsers. Official containers: `restic/restic`, future `kopia/kopia`
**Dependencies**: `dataclasses`, `pathlib`, `validators`, `croniter`, `notifiers`
**Testing**: Write standalone tests that don't import main app modules (avoid dependency/permission errors). Mock external dependencies. Use `test_*_standalone.py` pattern for isolated unit tests.
**Context Management**: Use SESSION.md workflow to maintain context across compression cycles. Session start: create SESSION.md with current priorities. During session: track progress, decisions, blockers. Session end: fold important findings into CLAUDE.md (permanent) and SUBSYSTEMS.md (current focus), preserve SESSION.md for post-compression context restore. Post-compression: feed SESSION.md (~500 tokens) instead of full docs (~20k tokens) to quickly restore working context. Grep CLAUDE.md/SUBSYSTEMS.md for specific details as needed.

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
**Validation**: SSH 30min cache, `validators` module, centralized in `job_validator.py`
**Forms**: Sectioned UI, dedicated parsers per destination (`_safe_get_value`), inline error display (`FormErrorHandler`)
**UI Paradigm**: Per-job inspection hubs (`/inspect?name=<jobname>`) consolidate logs, status, backup browser, and restore controls into unified interfaces (paradigm shift from separate pages)
**Container Execution**: **CRITICAL ASYMMETRY** - Restore operations use container execution (`restic/restic:0.18.0` on remote hosts), but backup execution still uses local restic binary. This creates inconsistent execution strategies that need unification.
**Backup Browser**: Multi-provider PROVIDERS config (repository vs filesystem), unified JS interface
**Backup Execution**: Separated concerns - `BackupExecutor`, `BackupCommandBuilder`, `BackupConflictHandler`, `BackupNotificationDispatcher`
**Restore**: Provider system `restore-core.js` + `restore-restic.js`, `RestoreHandler` backend, extensible architecture
**Notifications**: `notifiers` backend, spam-prevention queuing, template variables, per-job integration
**API**: Query filtering, CORS, field selection, JSON responses, authentication-ready
**Testing**: Unit coverage with mocking patterns
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

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

## Roadmap

**Next Session Priority**: 
1. **Container-Based Backup Execution** - Update ResticRunner and backup execution to use official `restic/restic:0.18.0` container for SSH source backups (never tested before - critical gap)
2. **Restore Command Integration** - Complete ResticRunner restore command building to use container execution for SSH "restore to source" operations
3. **Real Progress Parsing** - Replace simulated progress with actual `restic restore --json` output parsing for accurate progress display
4. **Dashboard Status Integration** - Add restore status polling and display "Restoring... N%" in main dashboard job table

**Recent Completion (2025-08-15)**:
- **Container Execution Strategy** - Implemented official `restic/restic:0.18.0` container execution for SSH operations to solve version mismatch issues, with provider-agnostic architecture for future Kopia support
- **SSH Capability Detection** - Added comprehensive SSH validation that detects rsync, docker, and podman availability on remote hosts with intelligent backend support recommendations
- **Configuration-Driven Container Runtime** - SSH validation now populates `container_runtime` field in job config (preferring podman over docker) for clean separation of concerns
- **Comprehensive Secret Obfuscation** - Enhanced logging to properly obfuscate all password instances in commands (environment variables, container flags, command args) with 100% coverage
- **Container-Based Restore Execution** - Successfully tested restore functionality using container execution for version consistency (dry run verified working)

**Recent Completion (2025-08-14)**:
- **Intelligent Restore System** - Complete implementation with smart overwrite protection, dual restore targets (Highball container vs. source), pre-flight risk assessment, progressive disclosure confirmation (eliminated modals), multipart form data handling, and comprehensive safety controls
- **Multipart Form Data Refactor** - Repo-wide conversion from URL-encoded to multipart with auto-detection, better array handling, enhanced security, and backward compatibility
- **Modal Elimination** - Replaced modal-based UI with progressive disclosure patterns, eliminated race conditions, simplified state management, and improved UX consistency
- **Restore Infrastructure (Phase 1)** - Complete per-job inspection system with `/inspect?name=<jobname>` endpoint, integrated job status/logs/backup browser/restore controls, dashboard "Inspect" buttons, `/dev` system debugging separation, backup command builder multi-path `source_paths` format support, and UI refinements for restore workflow
- **Backup-agnostic browser refactoring** - Converted Restic-only browser to multi-provider system supporting all backup types (Restic snapshots, rsync/SSH/local/rsyncd filesystems) with unified interface, proper terminology distinction, and provider detection
- **Complete notification system** - Full spam-prevention queue system with configurable intervals, batch formatting, event-driven processing, per-job notification integration with template variables, and comprehensive testing
- **Enhanced log inspection** - Added 4 new log sources (Job Status, Running Jobs, SSH Validation Cache, Notification Queues) with organized 2-row button layout
- **Per-job notification completion** - Full integration of job-specific provider selection, custom message templates with variable expansion, and queue system compatibility
- **Conflict detection verification** - Confirmed host-level conflict detection works correctly for multi-path jobs (no changes needed)
- **Restic repository browser** - Complete implementation with progressive loading, expandable tree, multi-level selection, detailed snapshot statistics, theme-adaptive icons, instant loading feedback, and multi-provider architecture (100% complete)

**Future Priorities**: Section-specific save buttons for configuration, notification template preview, enhanced Restic features
**Planned**: Kopia provider (official `kopia/kopia` container), enhanced Restic execution features (progress parsing, retention policies)
**Wishlist**: notification template preview, notification history, expanded variable system for notifications
**anti-goals**: 
