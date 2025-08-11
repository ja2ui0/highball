# Highball - Backup Manager

Web-based rsync backup orchestration with scheduling and monitoring.

## Architecture

**Flow**: `app.py` → `handlers/` → `services/` → `templates/`
**Principles**: Thin handlers, centralized validation in `job_validator.py`, file-based logging

**Stack**: Python 3.11, APScheduler, PyYAML, Docker, rsync/SSH

## Key Components

**Core**: `app.py` (routing), `config.py` (YAML config)
**Handlers**: `backup.py` (execution), `job_manager.py` (CRUD), `job_validator.py` (validation)  
**Services**: `job_logger.py` (logging), `ssh_validator.py`, `scheduler_service.py`

## Data Storage

**Config** (user-facing): `/config/config.yaml` - jobs, global settings, deleted jobs
**Operational** (file-based logging):
- `/var/log/highball/job_status.yaml` - last-run status per job  
- `/var/log/highball/jobs/{job_name}.log` - detailed execution logs
- `/var/log/highball/job_validation.yaml` - SSH validation timestamps

## Development

**Conventions**: PEP 8, centralized validation in `job_validator.py`, stdlib preference
**Extensions**: New engines via `services/<engine>_runner.py` + update `job_validator.py`

## Commands

**Run**: `./build.sh && docker-compose up -d`  
**Debug**: `docker logs -f backup-manager`

## Configuration Schema (User-facing Only)

```yaml
global_settings:
  scheduler_timezone: "America/Denver"
  notification:
    telegram_token: ""
    telegram_chat_id: ""

backup_jobs:
  job_name:
    source_type: "ssh|local"
    source_config: {hostname, username, path}
    dest_type: "ssh|local|rsyncd" 
    dest_config: {hostname, share}  # must specify explicit destinations
    schedule: "daily|weekly|hourly|cron"
    enabled: true

deleted_jobs:  # user can manually restore to backup_jobs
  job_name: {...}
```

