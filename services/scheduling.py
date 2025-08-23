"""
Unified Scheduling Service
Consolidates scheduler management and schedule loading
Replaces: scheduler_service.py, schedule_loader.py
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import atexit
from typing import Optional, Any, Callable, List, Dict

logger = logging.getLogger(__name__)


# =============================================================================
# **SCHEDULER MANAGEMENT CONCERN** - APScheduler operation and job management
# =============================================================================

class SchedulerManager:
    """Scheduler management - ONLY handles APScheduler operations"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("SchedulerManager started")
        atexit.register(lambda: self.shutdown())

    def add_cron_job(self, func: Callable, job_id: str, cron_expr: Dict[str, Any], args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Scheduler concern: add or replace job with explicit CronTrigger kwargs"""
        self.remove_job(job_id)
        self.scheduler.add_job(
            func,
            CronTrigger(**cron_expr),
            id=job_id,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True
        )
        logger.info(f"Added cron job {job_id} with schedule {cron_expr}")

    def add_crontab_job(self, func: Callable, job_id: str, crontab: str, timezone: Optional[str] = None, args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Scheduler concern: add or replace job using crontab string like '30 3 * * 1,3,5'"""
        self.remove_job(job_id)
        trigger = CronTrigger.from_crontab(crontab, timezone=timezone)
        self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True
        )
        logger.info(f"Added crontab job {job_id}: '{crontab}' tz={timezone or 'scheduler default'}")

    def add_interval_job(self, func: Callable, job_id: str, seconds: int, args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Scheduler concern: add or replace job on fixed interval in seconds"""
        self.remove_job(job_id)
        self.scheduler.add_job(
            func,
            'interval',
            seconds=seconds,
            id=job_id,
            args=args or [],
            kwargs=kwargs or {},
            replace_existing=True
        )
        logger.info(f"Added interval job {job_id} every {seconds} seconds")

    def remove_job(self, job_id: str) -> None:
        """Scheduler concern: remove job if it exists"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}")
        except Exception:
            pass  # No job to remove

    def shutdown(self) -> None:
        """Scheduler concern: stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("SchedulerManager stopped")


# =============================================================================
# **SCHEDULE LOADING CONCERN** - Configuration parsing and job registration
# =============================================================================

class ScheduleLoader:
    """Schedule loading - ONLY handles config parsing and job bootstrap"""
    
    def __init__(self, scheduler_manager: SchedulerManager):
        self.scheduler_manager = scheduler_manager
    
    def resolve_cron_string(self, schedule: str, backup_config) -> str | None:
        """Loading concern: resolve schedule string to cron expression using configurable times"""
        schedule = (schedule or "").strip().lower()
        if not schedule or schedule == "manual":
            return None
        
        # Get configurable schedule times from global settings
        global_settings = backup_config.config.get("global_settings", {})
        default_times = global_settings.get("default_schedule_times", {
            "hourly": "0 * * * *",
            "daily": "0 3 * * *", 
            "weekly": "0 3 * * 0",
            "monthly": "0 3 1 * *"
        })
        
        if schedule in default_times:
            return default_times[schedule]
        
        # Crude check: treat anything with spaces like a crontab expr
        if " " in schedule:
            return schedule
        return None

    def bootstrap_schedules(self, backup_config) -> int:
        """Loading concern: register all enabled jobs that have non-manual schedule"""
        from handlers.operations import OperationsHandler
        
        jobs = backup_config.config.get("backup_jobs", {}) or {}
        global_settings = backup_config.config.get("global_settings", {}) or {}
        timezone = global_settings.get("scheduler_timezone", "UTC")
        default_dry = bool(global_settings.get("default_dry_run_on_schedule", True))

        operations_handler = OperationsHandler(backup_config, None)

        scheduled = 0
        for name, conf in jobs.items():
            if not conf.get("enabled", False):
                continue

            cron_str = self.resolve_cron_string(conf.get("schedule", "manual"), backup_config)
            if not cron_str:
                continue

            # Per-job override; default to global default
            dry = bool(conf.get("dry_run_on_schedule", default_dry))

            # Register: run via the same path as UI, but headless (no HTTP handler)
            # Use a stable job id so we could update/replace later if needed
            job_id = f"backup:{name}"

            def _run(job_name=name, dry_run=dry):
                # Source label tells your logs this was a scheduler trigger
                operations_handler.run_backup_job_async(None, job_name, dry_run)

            # Use crontab string directly
            self.scheduler_manager.add_crontab_job(
                func=_run,
                job_id=job_id,
                crontab=cron_str,
                timezone=timezone,
            )
            scheduled += 1

        return scheduled


# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates scheduler management and loading
# =============================================================================

class SchedulingService:
    """Unified scheduling service - ONLY coordinates scheduler and loading concerns"""
    
    def __init__(self):
        self.scheduler_manager = SchedulerManager()
        self.schedule_loader = ScheduleLoader(self.scheduler_manager)
    
    # **SCHEDULER DELEGATION** - Pure delegation to scheduler concern
    def add_cron_job(self, func: Callable, job_id: str, cron_expr: Dict[str, Any], args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Delegation: add cron job"""
        return self.scheduler_manager.add_cron_job(func, job_id, cron_expr, args, kwargs)
    
    def add_crontab_job(self, func: Callable, job_id: str, crontab: str, timezone: Optional[str] = None, args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Delegation: add crontab job"""
        return self.scheduler_manager.add_crontab_job(func, job_id, crontab, timezone, args, kwargs)
    
    def add_interval_job(self, func: Callable, job_id: str, seconds: int, args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Delegation: add interval job"""
        return self.scheduler_manager.add_interval_job(func, job_id, seconds, args, kwargs)
    
    def remove_job(self, job_id: str) -> None:
        """Delegation: remove job"""
        return self.scheduler_manager.remove_job(job_id)
    
    def shutdown(self) -> None:
        """Delegation: shutdown scheduler"""
        return self.scheduler_manager.shutdown()
    
    # **LOADING DELEGATION** - Pure delegation to loading concern
    def bootstrap_schedules(self, backup_config) -> int:
        """Delegation: bootstrap schedules from config"""
        return self.schedule_loader.bootstrap_schedules(backup_config)
    
    def resolve_cron_string(self, schedule: str, backup_config) -> str | None:
        """Delegation: resolve schedule string"""
        return self.schedule_loader.resolve_cron_string(schedule, backup_config)


# Legacy compatibility instances
scheduler_service = SchedulingService()