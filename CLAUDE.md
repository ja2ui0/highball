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

## Features

**Job Management**: Full CRUD with renaming, validation, cron scheduling  
**Smart Scheduling**: Configurable default times, runtime conflict detection, automatic job queuing
**Logging**: Per-job execution logs, status tracking, SSH validation state, conflict delay tracking
**Notifications**: Telegram/email alerts for delays, failures, and successes (configurable)
**UI**: Real-time validation, share discovery, job history with log viewing

## Development

**Conventions**: PEP 8, centralized validation in `job_validator.py`, stdlib preference
**Extensions**: New engines via `services/<engine>_runner.py` + update `job_validator.py`

## Commands

**Run**: `./build.sh && docker-compose up -d`  
**Debug**: `docker logs -f backup-manager`
**Test Notifications**: `./test_notifications.py`

## Configuration Schema (User-facing Only)

```yaml
global_settings:
  scheduler_timezone: "America/Denver"
  default_schedule_times:
    hourly: "0 * * * *"     # configurable default times
    daily: "0 3 * * *" 
    weekly: "0 3 * * 0"
  enable_conflict_avoidance: true  # wait for conflicting jobs before running
  conflict_check_interval: 300     # seconds between conflict checks
  delay_notification_threshold: 300  # send notification after this many seconds delay
  notification:
    telegram_token: ""              # from @BotFather
    telegram_chat_id: ""            # chat ID for notifications
    notify_on_success: false        # send notifications for successful jobs
    email:
      smtp_server: "smtp.gmail.com" # SMTP server hostname
      smtp_port: 587                # 587 for TLS, 465 for SSL
      use_tls: true                 # use TLS encryption
      from_email: ""                # sender email address
      to_email: ""                  # recipient email address
      username: ""                  # SMTP authentication username
      password: ""                  # SMTP authentication password

backup_jobs:
  job_name:
    source_type: "ssh|local"
    source_config: {hostname, username, path}
    dest_type: "ssh|local|rsyncd" 
    dest_config: {hostname, share}  # must specify explicit destinations
    schedule: "daily|weekly|hourly|cron_pattern"
    enabled: true

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

