# Highball - Backup Manager

Web-based rsync backup orchestration with scheduling and monitoring.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging

**Stack**: Python 3.11, APScheduler, PyYAML, Docker, rsync/SSH

## Key Components

**Core**: `app.py` (routing), `config.py` (YAML config)
**Handlers**: `backup.py` (execution), `job_manager.py` (CRUD), `job_validator.py` (validation), `logs.py` (log viewer)  
**Services**: `job_logger.py` (logging), `ssh_validator.py`, `scheduler_service.py`, `job_conflict_manager.py` (runtime conflicts), `notification_service.py` (alerts)

## Data Storage

**Config** (user-facing): `/config/config.yaml` - jobs, global settings, deleted jobs
**Operational** (file-based logging):
- `/var/log/highball/job_status.yaml` - last-run status per job  
- `/var/log/highball/jobs/{job_name}.log` - detailed execution logs
- `/var/log/highball/job_validation.yaml` - SSH validation timestamps
- `/var/log/highball/running_jobs.txt` - currently running jobs for conflict detection
- `/var/log/highball/deleted_jobs.yaml` - deleted job tracking with timestamps (separate from config)

## Features

**Job Management**: Full CRUD with renaming, validation, cron scheduling, per-job conflict avoidance settings  
**Smart Scheduling**: Configurable default times (hourly/daily/weekly/monthly), runtime conflict detection, automatic job queuing
**Logging**: Per-job execution logs, status tracking, SSH validation state, conflict delay tracking, live log streaming
**Notifications**: Method-specific Telegram/email alerts with individual enabled/disabled flags and per-method success notifications
**UI**: Real-time validation, share discovery, job history with live log viewing, structured config forms + raw YAML editor

## Development

**Conventions**: PEP 8, centralized validation in `job_validator.py`, stdlib preference
**Extensions**: New engines via `services/<engine>_runner.py` + update `job_validator.py`

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

