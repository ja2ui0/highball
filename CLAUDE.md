# Highball - Backup Manager

Web-based backup orchestration with scheduling and monitoring. Supports rsync, with Restic provider scaffolded (not yet functional).

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging, dataclass-driven configuration

**Prime Directive - One Job = One Source Path + One Destination**: Each backup job targets a single source path to a single destination repository. This deliberate design decision ensures simpler mental model, clearer conflict detection, better granular control, easier troubleshooting, and reduced complexity. Multiple source paths would require significant architecture changes and make the system more complex for users.

**Stack**: Python 3.11 (dataclasses, pathlib, validators, notifiers), APScheduler, PyYAML, Docker, rsync/SSH

## Key Components

**Core**: `app.py` (routing), `config.py` (YAML config)
**Handlers**: `backup.py` (modular execution orchestration), `backup_executor.py` (core backup execution), `backup_command_builder.py` (rsync command construction), `backup_conflict_handler.py` (conflict management), `backup_notification_dispatcher.py` (notification handling), `job_manager.py` (CRUD), `job_validator.py` (validation), `logs.py` (log viewer), `restic_handler.py` (Restic planning - scaffold), `restic_validator.py`, `restic_form_parser.py`, `ssh_form_parser.py`, `local_form_parser.py`, `rsyncd_form_parser.py` (modular form parsing)
**Services**: `job_logger.py` (pathlib-based logging), `ssh_validator.py` (modern validation with caching), `scheduler_service.py`, `job_conflict_manager.py` (runtime conflicts), `notification_service.py` (notifiers library backend), `form_data_service.py` (modular template generation), `restic_runner.py` (command planning - scaffold)
**Static Assets**: `job-form.js` (consolidated form handling), `config-manager.js` (settings UI), `network-scan.js` (rsync discovery)

## Data Storage

**Config** (user-facing): `/config/config.yaml` - jobs, global settings, deleted jobs
**Operational** (file-based logging):
- `/var/log/highball/job_status.yaml` - last-run status per job  
- `/var/log/highball/jobs/{job_name}.log` - detailed execution logs
- `/var/log/highball/job_validation.yaml` - SSH validation timestamps
- `/var/log/highball/running_jobs.txt` - currently running jobs for conflict detection
- `/var/log/highball/deleted_jobs.yaml` - deleted job tracking with timestamps (separate from config)

## Features

**Job Management**: Full CRUD with renaming, validation, cron scheduling, per-job conflict avoidance settings, consolidated templates
**Smart Scheduling**: Configurable default times (hourly/daily/weekly/monthly), runtime conflict detection, automatic job queuing
**Logging**: Per-job execution logs, status tracking, SSH validation state with 30min caching, conflict delay tracking, simplified refresh-based log viewing
**Notifications**: Professional notification system using `notifiers` library backend, method-specific Telegram/email alerts with individual enabled/disabled flags and per-method success notifications (emoji-free, extensible to 25+ providers)
**UI**: Real-time validation, share discovery, job history with refresh-based log viewing, structured config forms + raw YAML editor, network scanning, theming system
**System Inspection**: Network rsync server discovery, simplified log viewing, comprehensive system monitoring

## Development

**Conventions**: PEP 8, dataclasses for structured data, pathlib for file operations, external static assets (no inline JS/CSS), emoji-free interfaces
**Modern Patterns**: Type hints throughout, consolidated YAML operations, CSS utility classes, cached validation, error handling with fallbacks
**Extensions**: New engines via `services/<engine>_runner.py` + `handlers/<engine>_validator.py` + `handlers/<engine>_form_parser.py` + update `job_validator.py` (see Restic scaffold example)
**Modular Parsing**: All destination types use dedicated form parsers with consistent interface - `JobFormParser` delegates to specialized parsers
**Dependencies**: `dataclasses`, `pathlib`, `validators`, `croniter`, `notifiers` for modern Python patterns

## Theming System

**Architecture**: Base + Theme approach with complete color separation
**Base CSS**: `/static/style.css` - structural styles, spacing, layout (no colors)  
**Theme Files**: `/static/themes/{theme}.css` - color variables only (`:root` definitions)
**Loading**: Automatic via `TemplateService` - all templates get `{{THEME_CSS_PATH}}` variable
**Configuration**: `global_settings.theme` in YAML config (default: "dark")
**Discovery**: Dynamic theme detection from filesystem - scans `/static/themes/` for `.css` files
**UI Selection**: Theme dropdown in Config Manager with auto-generated options
**Extension**: Add new themes by creating CSS files with color variables - no template changes needed

## Modern Architecture Notes

**Template Consolidation**: Single `job_form.html` template with dataclass-driven variable generation (eliminates `edit_job.html` duplication)
**JavaScript Modularity**: Consolidated `job-form.js` (replaces `add-job.js`), separate `config-manager.js`, `network-scan.js` for specific functionality
**Type Safety**: Extensive use of dataclasses (`NotificationProvider`, `NotificationResult`, `LogPaths`, `SSHConfig`, `ValidationResult`, `JobFormData`, `SourceConfig`, `DestConfig`, `ResticConfig`, `CommandInfo`, `ExecutionContext`)
**File Operations**: All file paths use `pathlib.Path` objects with proper error handling and atomic operations
**Validation**: SSH validation with 30-minute in-memory cache, proper hostname validation via `validators` module
**CSS Architecture**: Modular theming system with structural CSS (`style.css`) and theme colors (`/static/themes/{theme}.css`), consolidated utility classes, no duplication or inline styles, rounded table corners, semantic color variables
**Error Handling**: Comprehensive exception handling with graceful degradation and user-friendly error messages
**Notification Architecture**: Professional `notifiers` library backend eliminates ~200 lines of manual SMTP/HTTP code, extensible factory pattern ready for 25+ providers (Slack, Discord, SMS, etc.) with unchanged frontend
**Restic Scaffold**: Complete modular architecture for Restic backup provider with command planning abstraction, implicit enablement, and 202 planning responses - ready for template/execution implementation (see `RESTIC_SCAFFOLD.md`)
**Form Parser Architecture**: Fully modular form parsing with dedicated parsers for each destination type (`LocalFormParser`, `SSHFormParser`, `RsyncdFormParser`, `ResticFormParser`) - eliminates code duplication and establishes clean extension pattern
**Backup Execution Architecture**: Modular backup execution with separation of concerns (`BackupExecutor` for core execution, `BackupCommandBuilder` for rsync command construction, `BackupConflictHandler` for conflict management, `BackupNotificationDispatcher` for notification handling) - replaces monolithic 477-line backup handler with focused, testable components

## Commands

**Run**: `./build.sh` or `./rr` (rebuild and restart)
**Debug**: `docker logs -f highball`
**Test Notifications**: `./test_notifications.py`

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
    source_config: {hostname, username, path}
    dest_type: "ssh|local|rsyncd|restic"  # restic scaffolded but not functional
    dest_config: {hostname, share} | {repo_type, repo_location, password}  # explicit destinations
    schedule: "daily|weekly|hourly|monthly|cron_pattern"
    enabled: true
    respect_conflicts: true     # wait for conflicting jobs (default: true)

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

