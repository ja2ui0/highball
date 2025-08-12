# Highball - Backup Manager

Web-based rsync backup orchestration with scheduling and monitoring.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/` → `static/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging, dataclass-driven configuration

**Stack**: Python 3.11 (dataclasses, pathlib, validators, notifiers), APScheduler, PyYAML, Docker, rsync/SSH

## Key Components

**Core**: `app.py` (routing), `config.py` (YAML config)
**Handlers**: `backup.py` (execution), `job_manager.py` (CRUD), `job_validator.py` (validation), `logs.py` (log viewer)  
**Services**: `job_logger.py` (pathlib-based logging), `ssh_validator.py` (modern validation with caching), `scheduler_service.py`, `job_conflict_manager.py` (runtime conflicts), `notification_service.py` (notifiers library backend), `form_data_service.py` (template generation)
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
**Logging**: Per-job execution logs, status tracking, SSH validation state with 30min caching, conflict delay tracking, live log streaming
**Notifications**: Professional notification system using `notifiers` library backend, method-specific Telegram/email alerts with individual enabled/disabled flags and per-method success notifications (emoji-free, extensible to 25+ providers)
**UI**: Real-time validation, share discovery, job history with live log viewing, structured config forms + raw YAML editor, network scanning
**System Inspection**: Network rsync server discovery, live log streaming, comprehensive system monitoring

## Development

**Conventions**: PEP 8, dataclasses for structured data, pathlib for file operations, external static assets (no inline JS/CSS), emoji-free interfaces
**Modern Patterns**: Type hints throughout, consolidated YAML operations, CSS utility classes, cached validation, error handling with fallbacks
**Extensions**: New engines via `services/<engine>_runner.py` + update `job_validator.py`
**Dependencies**: `dataclasses`, `pathlib`, `validators`, `croniter`, `notifiers` for modern Python patterns

## Modern Architecture Notes

**Template Consolidation**: Single `job_form.html` template with dataclass-driven variable generation (eliminates `edit_job.html` duplication)
**JavaScript Modularity**: Consolidated `job-form.js` (replaces `add-job.js`), separate `config-manager.js`, `network-scan.js` for specific functionality
**Type Safety**: Extensive use of dataclasses (`NotificationProvider`, `NotificationResult`, `LogPaths`, `SSHConfig`, `ValidationResult`, `JobFormData`)
**File Operations**: All file paths use `pathlib.Path` objects with proper error handling and atomic operations
**Validation**: SSH validation with 30-minute in-memory cache, proper hostname validation via `validators` module
**CSS Architecture**: Semantic utility classes (`.status-success`, `.status-error`, `.method-settings`) replace inline styles
**Error Handling**: Comprehensive exception handling with graceful degradation and user-friendly error messages
**Notification Architecture**: Professional `notifiers` library backend eliminates ~200 lines of manual SMTP/HTTP code, extensible factory pattern ready for 25+ providers (Slack, Discord, SMS, etc.) with unchanged frontend

## Commands

**Run**: `./build.sh` or `./rr` (rebuild and restart)
**Debug**: `docker logs -f backup-manager`
**Test Notifications**: `./test_notifications.py`

## Configuration Schema (User-facing Only)

```yaml
global_settings:
  scheduler_timezone: "UTC"  # default UTC, configurable
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
    dest_type: "ssh|local|rsyncd" 
    dest_config: {hostname, share}  # must specify explicit destinations
    schedule: "daily|weekly|hourly|monthly|cron_pattern"
    enabled: true
    respect_conflicts: true     # wait for conflicting jobs (default: true)

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

