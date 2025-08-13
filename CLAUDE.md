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

**Job Management**: Full CRUD, validation, cron scheduling, per-job conflict avoidance, custom rsync options
**Scheduling**: Runtime conflict detection, automatic queuing, configurable defaults
**Logging**: Per-job logs, SSH validation caching (30min), refresh-based viewing
**Notifications**: `notifiers` library backend, Telegram/email, per-method toggles, emoji-free
**UI**: Sectioned forms, real-time validation, share discovery, theming, password toggles

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
**Form Parser Architecture**: Dedicated parsers per destination type with consistent interface
**Form UI Architecture**: Sectioned forms (Job Identity & Source, Backup Destination, Schedule & Options, Actions)
**Backup Execution Architecture**: Separated concerns - `BackupExecutor`, `BackupCommandBuilder`, `BackupConflictHandler`, `BackupNotificationDispatcher`
**Rsync Options Architecture**: Per-job custom options override defaults (`-a --info=stats1 --delete --delete-excluded`), unified SSH/rsyncd field

## Commands

**Run**: `./rr` (intelligent rebuild and restart)
**Multi-arch**: `./rr multi` (build multiarch image for distribution)
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

## Roadmap

**Planned**: Borg, rclone direct destinations
**Wishlist**: Kopia destinations

