# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync and Restic providers with full connectivity validation.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging, dataclass-driven configuration

**Prime Directive - Job = Source + Destination + Definition**: Each backup job connects a source (host + multiple related paths) to a destination (repository) with a definition (schedule and settings). Sources contain multiple paths with per-path include/exclude rules. This architecture balances user workflow simplicity with granular control and tool efficiency.

**Stack**: Python 3.11 (dataclasses, pathlib, validators, notifiers), APScheduler, PyYAML, Docker, rsync/SSH

## Key Components

**Core**: `app.py` (routing), `config.py` (YAML config)
**Handlers**: `backup.py` (modular execution orchestration), `backup_executor.py` (core backup execution), `backup_command_builder.py` (rsync command construction), `restic_command_builder.py` (restic command construction), `command_builder_factory.py` (routing commands to providers), `backup_conflict_handler.py` (conflict management), `backup_notification_dispatcher.py` (notification handling), `job_manager.py` (CRUD), `job_validator.py` (validation), `logs.py` (log viewer), `restic_handler.py` (Restic management), `restic_validator.py` (connectivity validation), `restic_form_parser.py`, `ssh_form_parser.py`, `local_form_parser.py`, `rsyncd_form_parser.py` (modular form parsing), `form_error_handler.py` (inline error display), `job_display.py` (dashboard formatting), `dashboard.py` (modularized coordinator)
**Services**: `job_logger.py` (pathlib-based logging), `ssh_validator.py` (modern validation with caching), `scheduler_service.py`, `job_conflict_manager.py` (runtime conflicts), `notification_service.py` (notifiers library backend), `form_data_service.py` (modular template generation), `restic_runner.py` (command execution), `restic_content_analyzer.py` (content fingerprinting)
**Static Assets**: Modular JavaScript architecture with `job-form-core.js` (utilities), `job-form-ssh.js` (SSH validation), `job-form-rsyncd.js` (rsync discovery), `job-form-restic.js` (Restic management), `job-form-globals.js` (compatibility), `config-manager.js` (settings UI), `network-scan.js` (rsync discovery)

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
**Restic Integration**: Repository connectivity testing, binary availability checking, existing repository detection, content fingerprinting, repository browser (scaffolded)
**Inspect System**: Network scanner, Restic repository browser, unified log sources with proper container organization

## Development

**Conventions**: PEP 8, dataclasses, pathlib, external assets, emoji-free
**Patterns**: Type hints, cached validation, error fallbacks
**Extensions**: New engines via `services/<engine>_runner.py` + `handlers/<engine>_validator.py` + `handlers/<engine>_form_parser.py` + update `job_validator.py`
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
**Restic Scaffold**: Command planning abstraction, 202 responses, ready for execution (see `RESTIC_SCAFFOLD.md`)
**Form Parser Architecture**: Dedicated parsers per destination type with consistent interface (`_safe_get_value` for form data compatibility)
**Form UI Architecture**: Sectioned forms (Job Identity & Source, Backup Destination, Schedule & Options, Actions)
**Error Handling Architecture**: Modular inline error display (`FormErrorHandler`) with user input preservation, no scary error pages
**Dashboard Display Architecture**: Clean multi-path source display with hierarchical formatting and proper line breaks
**Backup Execution Architecture**: Separated concerns - `BackupExecutor`, `BackupCommandBuilder`, `BackupConflictHandler`, `BackupNotificationDispatcher`
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
1. **Multi-path conflict detection** - Update conflict detection logic to handle jobs with multiple source paths correctly
2. **Restic repository browser** - Implement actual functionality for the scaffolded browser interface  
3. **Restic restore functionality** - Add restore capabilities for snapshots and file recovery

**Recent Completion (2025-08-13)**:
- **Notification queue system** - Complete spam-prevention implementation with configurable intervals (5min telegram, 15min email), batch message formatting, event-driven timer processing, file-based persistence, and comprehensive testing
- **Global notification configuration redesign** - Removed success notification toggles, changed labels to "Configure <provider>...", added test notification buttons with comprehensive error handling, integrated queue settings UI
- **Modular notification testing** - Created `NotificationTestHandler` with provider-specific error messages, proper result validation, and user-friendly feedback
- **Per-job notification foundation** - Added dynamic provider selection UI, custom success/failure messages with template variables, expandable form sections (scaffolded)

**Future Priorities**: Complete per-job notification implementation, section-specific save buttons for configuration
**Planned**: Borg, rclone direct destinations, enhanced Restic execution features (progress parsing, retention policies)
**Wishlist**: Kopia destinations

