# services/scheduler_service.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import atexit

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("SchedulerService started")
        atexit.register(lambda: self.shutdown())

    def add_cron_job(self, func, job_id, cron_expr, args=None, kwargs=None):
        """Add or replace a job with explicit CronTrigger kwargs (minute, hour, etc.)."""
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

    def add_crontab_job(self, func, job_id, crontab: str, timezone: str | None = None, args=None, kwargs=None):
        """Add or replace a job using a crontab string like '30 3 * * 1,3,5'."""
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

    def add_interval_job(self, func, job_id, seconds, args=None, kwargs=None):
        """Add or replace a job on a fixed interval in seconds."""
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

    def remove_job(self, job_id):
        """Remove a job if it exists."""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}")
        except Exception:
            pass  # No job to remove

    def shutdown(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("SchedulerService stopped")

