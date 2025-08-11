# Highball Backup Manager - Development Context

## Project Overview

Highball is a web-based backup management application that orchestrates rsync-based backup jobs across multiple hosts, with planned expansion to rclone and restic engines. It provides centralized scheduling, monitoring, and management of distributed backup operations.

## Architecture & Request Flow

### Request Flow
1. **`app.py`** - Routes requests to handlers
2. **`handlers/*`** - Parse/validate requests, call services, select templates  
3. **`services/*`** - Execute business logic (SSH validation, scheduling, etc.)
4. **`templates/*`** - Render UI with data from handlers
5. **`config.py`** - Manages YAML configuration loading

### Key Design Principles
- **Thin handlers**: HTTP handlers focus on request/response, delegate logic to services
- **Centralized validation**: All validation logic in `handlers/job_validator.py`
- **Simple templates**: Templates receive dictionaries, no business logic in views
- **Extension-ready**: Architecture supports new backup engines and job options

## Technology Stack

**Backend**: Python 3.11, built-in HTTP server, APScheduler, PyYAML, Supervisor
**Frontend**: HTML5/CSS3 dark mode, vanilla JavaScript, Server-Sent Events
**Infrastructure**: Docker, Nginx reverse proxy, Docker Compose
**External Tools**: rsync, SSH, network scanning for rsync daemons

## Key Modules

### Core Application
- **`app.py`** - Route table and HTTP request routing
- **`config.py`** - Configuration loader and YAML management

### Request Handlers (Thin Controllers)
- **`dashboard.py`** - Main dashboard and job management coordination
- **`backup.py`** - Job execution, dry-run previews, monitoring
- **`job_manager.py`** - Job CRUD operations
- **`job_scheduler.py`** - Job scheduling interface
- **`job_validator.py`** - **Centralized validation logic** (avoid duplication)
- **`job_form_parser.py`** - Transform forms into normalized job dictionaries
- **`job_display.py`** - HTML generation for job UI elements
- **`logs.py`** - Log viewing and real-time streaming
- **`config_handler.py`** - Configuration editing
- **`network.py`** - Network scanning for rsync daemons

### Business Logic Services
- **`ssh_validator.py`** - SSH connectivity and path validation
- **`template_service.py`** - HTML template rendering helpers
- **`scheduler_service.py`** - APScheduler wrapper
- **`schedule_loader.py`** - Bootstrap job schedules from config

## Data Model (Current)

### Job Configuration
Jobs embed all source/destination config directly (no separate Host entity):
```python
{
    'source_type': 'ssh|local',
    'source_config': {'hostname': 'server', 'username': 'user', 'path': '/path'},
    'dest_type': 'ssh|local|rsyncd',
    'dest_config': {'hostname': 'backup-server', 'share': 'backup-share'},
    'includes': [], 'excludes': [],
    'schedule': 'daily|weekly|hourly|cron_expression',
    'enabled': True
}
```

### Backup Logs
Simple last-run tracking per job:
```python
{
    'job_name': {
        'last_run': '2025-08-10T07:43:12.660474',
        'status': 'completed-dry-run|completed|error',
        'message': 'Backup completed with return code 0'
    }
}
```

## Extension Points

### Adding New Backup Engines
1. Create engine service: `services/<engine>_runner.py` with standardized interface
2. Extend `handlers/job_validator.py` with engine-specific validation
3. Update `handlers/job_form_parser.py` for engine-specific form fields
4. Wire execution in `handlers/backup.py`
5. Update templates with engine options

### Adding Job Options
1. Add validation rules in `handlers/job_validator.py`
2. Handle new fields in `handlers/job_form_parser.py`
3. Add form fields to `templates/add_job.html` and `templates/edit_job.html`
4. Update `handlers/job_display.py` for new options

## Development Conventions

- **Python**: PEP 8, 4-space indentation
- **Validation centralization**: All validation in `job_validator.py` to avoid duplication
- **Pure stdlib preference**: Minimize external dependencies
- **File naming**: Python `snake_case.py`, HTML `snake_case.html`, JS/CSS `kebab-case`

## Essential Commands

```bash
# Build and run
./build.sh
docker-compose up -d

# Development with live mounting
docker-compose --profile dev up -d

# Debug
docker logs -f backup-manager
docker exec backup-manager python3 /app/app.py

# Test configuration
docker exec backup-manager python3 -c "from config import BackupConfig; BackupConfig('/config/config.yaml')"
```

## Configuration Schema Reference

```yaml
global_settings:
  dest_host: "192.168.1.252"
  scheduler_timezone: "America/Denver"
  rsync_timeout_seconds: 300

backup_jobs:
  job_name:
    source_type: "ssh|local"
    source_config: {hostname, username, path}
    dest_type: "ssh|local|rsyncd" 
    dest_config: {hostname, share}
    schedule: "daily|weekly|hourly|cron"
    enabled: true
```

---

*This document serves as architectural context for Claude-assisted development. It reflects current implementation while noting extension points for future development.*
