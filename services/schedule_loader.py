# services/schedule_loader.py
"""
Reads job schedules from config/config.yaml and registers them with SchedulerService.
Supports: manual | hourly | daily | weekly | full crontab strings ("m h dom mon dow").
"""

from handlers.backup import BackupHandler

SHORTHANDS = {
    "hourly": "0 * * * *",
    "daily": "0 3 * * *",     # sane default (3am)
    "weekly": "0 3 * * 0",    # 3am Sundays
}

def _resolve_cron_string(s: str) -> str | None:
    s = (s or "").strip().lower()
    if not s or s == "manual":
        return None
    if s in SHORTHANDS:
        return SHORTHANDS[s]
    # crude check: treat anything with spaces like a crontab expr
    if " " in s:
        return s
    return None

def bootstrap_schedules(backup_config, scheduler_service) -> int:
    """
    Registers all enabled jobs that have a non-manual schedule.
    Returns the number of jobs scheduled.
    """
    jobs = backup_config.config.get("backup_jobs", {}) or {}
    g = backup_config.config.get("global_settings", {}) or {}
    tz = g.get("scheduler_timezone", "UTC")
    default_dry = bool(g.get("default_dry_run_on_schedule", True))

    backup_handler = BackupHandler(backup_config)

    scheduled = 0
    for name, conf in jobs.items():
        if not conf.get("enabled", False):
            continue

        cron_str = _resolve_cron_string(conf.get("schedule", "manual"))
        if not cron_str:
            continue

        # per-job override; default to global default
        dry = bool(conf.get("dry_run_on_schedule", default_dry))

        # Register: run via the same path as UI, but headless (no HTTP handler)
        # Use a stable job id so we could update/replace later if needed
        job_id = f"backup:{name}"

        def _run(job_name=name, dry_run=dry):
            # source label tells your logs this was a scheduler trigger
            backup_handler.run_backup_job(handler=None, job_name=job_name, dry_run=dry_run, source="schedule")

        # Use crontab string directly
        scheduler_service.add_crontab_job(
            func=_run,
            job_id=job_id,
            crontab=cron_str,
            timezone=tz,
        )
        scheduled += 1

    return scheduled

