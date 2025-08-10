# Highball Architecture

## Purpose
Highball is a small web app that orchestrates backup jobs across multiple hosts. It starts with rsync over SSH or rsync daemons and will grow to include rclone and restic.

## Request flow (happy path)
1. `app.py` wires routes → handler functions.
2. `handlers/*` parse/validate requests, call services, and select templates.
3. `services/*` hold reusable logic (ssh validation, template rendering, future engines).
4. Templates in `templates/*` render the UI. Static assets in `static/*`.
5. Config is read via `config.py` from `config/config.yaml`.

## Key modules
- **app.py**: route table, server bootstrap.
- **handlers/dashboard.py**: home view and summaries.
- **handlers/backup.py**: run and preview job actions.
- **handlers/job_manager.py**: create, update, delete, schedule jobs.
- **handlers/job_validator.py**: job-level validation.
- **handlers/job_form_parser.py**: translate form → normalized job dict.
- **handlers/logs.py**: log listing and tail view.
- **services/ssh_validator.py**: host reachability and auth checks.
- **services/template_service.py**: render helpers and shared context.
- **config.py**: config loader and schema defaults.

## Data model (lightweight)
- **Host**: name, type (ssh|rsyncd), address, user, port, options.
- **Job**: name, type (rsync|rclone|restic), source, target, options, schedule.
- **Run**: job name, started_at, finished_at, exit_code, stdout/stderr.

## Conventions
- Keep handlers thin. Put reusable logic in `services/`.
- Validation lives in `handlers/job_validator.py`. Do not duplicate per handler.
- Templates get simple dicts. Avoid embedding business logic in templates.
- Prefer pure stdlib unless already using a library.

## Extension points
- New engine: add `services/<engine>_runner.py`, wire in `handlers/backup.py`.
- New job option: extend validator and form parser, update templates.

