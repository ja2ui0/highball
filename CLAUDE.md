# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync and Restic providers with full connectivity validation.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging, dataclass-driven configuration

**Rule: Job = Source + Destination + Definition**: Each backup job connects a source (host) to a destination (repository) with a definition (paths, schedule, settings). Definitions contain one or more paths with per-path include/exclude rules. This architecture balances user workflow simplicity with granular control and tool efficiency.

**Rule: Just In Time, Progressive Disclosure**: User sees what they need when they need it. Ask only what can't be inferred. Do not overwhelm with choices.

**Stack**: Python 3.11 (dataclasses, pathlib, validators, notifiers), APScheduler, PyYAML, Docker, rsync/SSH

## Key Components

**Core**: `app.py` (routing), `config.py` (YAML config)
**Handlers**: `backup.py` (modular execution orchestration), `backup_executor.py` (core backup execution), `backup_command_builder.py` (rsync command construction with multi-path support), `restic_command_builder.py` (restic command construction), `command_builder_factory.py` (routing commands to providers), `backup_conflict_handler.py` (conflict management), `backup_notification_dispatcher.py` (notification handling), `job_manager.py` (CRUD), `job_validator.py` (validation), `logs.py` (system debug log viewer), `inspect_handler.py` (per-job inspection and restore UI), `restore_handler.py` (complete Restic restore execution with progress tracking), `restic_handler.py` (Restic management), `filesystem_handler.py` (backup-agnostic filesystem browsing), `api_handler.py` (REST API for external integrations), `restic_validator.py` (connectivity validation), `restic_form_parser.py`, `ssh_form_parser.py`, `local_form_parser.py`, `rsyncd_form_parser.py` (modular form parsing), `form_error_handler.py` (inline error display), `job_display.py` (dashboard formatting), `dashboard.py` (modularized coordinator)
**Services**: `job_logger.py` (pathlib-based logging), `ssh_validator.py` (modern validation with caching), `scheduler_service.py`, `job_conflict_manager.py` (runtime conflicts), `notification_service.py` (notifiers library backend), `form_data_service.py` (modular template generation), `restic_runner.py` (command execution), `restic_content_analyzer.py` (content fingerprinting), `backup_client.py` (generic SSH/local execution), `repository_service.py` (abstract base for providers), `restic_repository_service.py` (Restic implementation), `filesystem_service.py` (rsync filesystem browsing), `binary_checker_service.py` (multi-binary support)
**Static Assets**: Modular JavaScript architecture with `job-form-core.js` (utilities), `job-form-ssh.js` (SSH validation), `job-form-rsyncd.js` (rsync discovery), `job-form-restic.js` (Restic management), `job-form-globals.js` (compatibility), `config-manager.js` (settings UI), `network-scan.js` (rsync discovery), `backup-browser.js` (multi-provider backup browsing), `restore-core.js` (generic restore UI and provider orchestration), `restore-restic.js` (Restic-specific restore implementation)

## Data Storage

**Config** (user-facing): `/config/config.yaml` - jobs, global settings, deleted jobs
**Operational** (file-based logging):
- `/var/log/highball/job_status.yaml` - last-run status per job  
- `/var/log/highball/jobs/{job_name}.log` - detailed execution logs
- `/var/log/highball/job_validation.yaml` - SSH validation timestamps
- `/var/log/highball/running_jobs.txt` - currently running jobs for conflict detection
- `/var/log/highball/deleted_jobs.yaml` - deleted job tracking with timestamps (separate from config)

## Features

**Job Management**: Full CRUD, validation, cron scheduling, per-job conflict avoidance, custom rsync options, multi-path sources
**Scheduling**: Runtime conflict detection, automatic queuing, configurable defaults
**Logging**: Per-job logs, SSH validation caching (30min), refresh-based viewing
**Notifications**: `notifiers` library backend, Telegram/email, spam-prevention queuing with configurable intervals, batch message formatting, test capabilities, emoji-free
**UI**: Sectioned forms, real-time validation, share discovery, theming, password toggles, multi-path management
**Restic Integration**: Repository connectivity testing, binary availability checking, existing repository detection, content fingerprinting, complete repository browser with snapshot statistics and file tree navigation
**Backup Browser**: Multi-provider backup browsing system supporting Restic (repository snapshots), rsync/SSH/local/rsyncd (filesystem directories) with unified interface, provider-specific terminology, and expandable file trees
**Restore System**: Complete Restic restore functionality with per-job inspection interface (`/inspect?name=<jobname>`), integrated job status/backup browser/restore controls, modal password confirmation, dry run capability (default enabled), "Restore to Highball" target (/restore directory), background execution with progress tracking, and modular JavaScript architecture extensible to future providers (rsync, borg, kopia) - core implementation complete with clean HTML structure and proper container nesting
**REST API**: GET `/api/highball/jobs` endpoint for external dashboard widgets with query filtering (`state`, `fields`), CORS support, and authentication-ready architecture
**Debug System**: System debugging interface (`/dev`) with network scanner, 8 unified log sources (system + operational) with organized 2-row layout, separated from per-job inspection

## Development

**Conventions**: PEP 8, dataclasses, pathlib, external assets, emoji-free
**Patterns**: Type hints, cached validation, error fallbacks
**Extensions**: Repository providers via `services/<engine>_repository_service.py` (inheriting from `repository_service.py`) + `handlers/<engine>_validator.py` + `handlers/<engine>_form_parser.py` + update routing. Filesystem providers use existing `filesystem_service.py` + `filesystem_handler.py`. Multi-provider architecture supports Borg, Kopia with shared `backup_client.py` and `binary_checker_service.py`
**Dependencies**: `dataclasses`, `pathlib`, `validators`, `croniter`, `notifiers`

## Theming System

**Architecture**: Base + Theme separation - `/static/style.css` (structure) + `/static/themes/{theme}.css` (colors only)
**Loading**: Automatic via `TemplateService` - `{{THEME_CSS_PATH}}` variable
**Configuration**: `global_settings.theme` (default: "dark")
**Extension**: New themes = new CSS file with color variables

## Modern Architecture Notes

**Template Modularity**: `{{INCLUDE:filename}}` directives - `job_form.html` orchestrates components
**JavaScript Modularity**: 5-file architecture - single responsibility per component
**Type Safety**: Dataclasses for all structured data (`JobFormData`, `SourceConfig`, `DestConfig`, etc.)
**File Operations**: `pathlib.Path` with atomic operations
**Validation**: SSH 30min cache, `validators` module
**CSS Architecture**: Structural CSS + theme colors, `--bg-input` for input field depth
**Notification Architecture**: `notifiers` library backend, extensible to 25+ providers
**Backup Browser Architecture**: Multi-provider system with PROVIDERS configuration for repository-based (Restic/Borg/Kopia) vs filesystem-based (rsync/SSH/local/rsyncd) access, unified JavaScript interface with provider-specific terminology and endpoints
**REST API Architecture**: External integration endpoint with query parameter filtering, CORS headers, field selection, authentication stub for future token-based access, JSON responses with API versioning
**Restic Implementation**: Complete job management, repository browser, snapshot statistics, multi-provider service architecture ready for Borg/Kopia (see `RESTIC.md`)
**Form Parser Architecture**: Dedicated parsers per destination type with consistent interface (`_safe_get_value` for form data compatibility)
**Form UI Architecture**: Sectioned forms (Job Identity & Source, Backup Destination, Schedule & Options, Actions)
**Error Handling Architecture**: Modular inline error display (`FormErrorHandler`) with user input preservation, no scary error pages
**Dashboard Display Architecture**: Clean multi-path source display with hierarchical formatting and proper line breaks
**Backup Execution Architecture**: Separated concerns - `BackupExecutor`, `BackupCommandBuilder`, `BackupConflictHandler`, `BackupNotificationDispatcher`
**Restore Architecture**: Modular JavaScript provider system with `restore-core.js` (generic UI orchestration) and provider-specific implementations (`restore-restic.js`), `RestoreHandler` backend with command building and background execution, extensible to future providers
**Rsync Options Architecture**: Per-job custom options override defaults (`-a --info=stats1 --delete --delete-excluded`), unified SSH/rsyncd field
**Testing Architecture**: Comprehensive unit test coverage for error handling with mocking patterns

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

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

## Roadmap

**Next Session Priority**: 
1. **Real Progress Parsing** - Replace simulated progress with actual `restic restore --json` output parsing for accurate progress display
2. **Dashboard Status Integration** - Add restore status polling and display "Restoring... N%" in main dashboard job table
3. **Multi-Provider Restore** - Extend restore system to rsync, borg, kopia using established modular architecture

**Recent Completion (2025-08-14)**:
- **Complete Restore System Implementation** - Full Restic restore implementation with `RestoreHandler` backend, modular JavaScript architecture (`restore-core.js` + `restore-restic.js`), modal password confirmation, dry run capability, background execution with progress tracking, comprehensive unit test coverage (35/35 tests passing), and clean codebase after debugging cleanup
- **HTML Structure Resolution** - Fixed corrupted job inspect template HTML structure causing layout issues, proper container nesting for selection controls and job logs, modular JavaScript provider system ready for testing
- **Restore Infrastructure (Phase 1)** - Complete per-job inspection system with `/inspect?name=<jobname>` endpoint, integrated job status/logs/backup browser/restore controls, dashboard "Inspect" buttons, `/dev` system debugging separation, backup command builder multi-path `source_paths` format support, and UI refinements for restore workflow
- **Backup-agnostic browser refactoring** - Converted Restic-only browser to multi-provider system supporting all backup types (Restic snapshots, rsync/SSH/local/rsyncd filesystems) with unified interface, proper terminology distinction, and provider detection
- **Complete notification system** - Full spam-prevention queue system with configurable intervals, batch formatting, event-driven processing, per-job notification integration with template variables, and comprehensive testing
- **Enhanced log inspection** - Added 4 new log sources (Job Status, Running Jobs, SSH Validation Cache, Notification Queues) with organized 2-row button layout
- **Per-job notification completion** - Full integration of job-specific provider selection, custom message templates with variable expansion, and queue system compatibility
- **Conflict detection verification** - Confirmed host-level conflict detection works correctly for multi-path jobs (no changes needed)
- **Restic repository browser** - Complete implementation with progressive loading, expandable tree, multi-level selection, detailed snapshot statistics, theme-adaptive icons, instant loading feedback, and multi-provider architecture (100% complete)

**Future Priorities**: Section-specific save buttons for configuration, notification template preview, enhanced Restic features
**Planned**: Borg, Kopia, enhanced Restic execution features (progress parsing, retention policies)
**Wishlist**: notification template preview, notification history, expanded variable system for notifications
**anti-goals**: 
