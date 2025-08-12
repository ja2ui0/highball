"""
Backup execution handler
Refactored for modularity and maintainability
"""
import threading
from services.template_service import TemplateService
from .backup_executor import BackupExecutor
from .backup_conflict_handler import BackupConflictHandler
from .backup_notification_dispatcher import BackupNotificationDispatcher


class BackupHandler:
    """Handles backup job execution with modular architecture"""

    def __init__(self, backup_config, scheduler_service=None):
        self.backup_config = backup_config
        self.scheduler_service = scheduler_service
        
        # Initialize modular components
        self.executor = BackupExecutor(backup_config)
        self.conflict_handler = BackupConflictHandler(backup_config)
        self.notification_dispatcher = BackupNotificationDispatcher(backup_config)

    # ---------------------------
    # Public entry points
    # ---------------------------
    def run_backup_job(self, handler, job_name, dry_run=True, source="manual"):
        """
        Kick off a backup job in the background and (if handler is provided) redirect immediately.
        When handler is None (scheduler/CLI), no HTTP responses are sent.
        """
        if job_name not in self.backup_config.config.get("backup_jobs", {}):
            if handler is not None:
                TemplateService.send_error_response(handler, f"Job '{job_name}' not found")
            return

        job_config = self.backup_config.config["backup_jobs"][job_name]

        # Start background worker
        t = threading.Thread(
            target=self._run_job_background,
            args=(job_name, job_config, dry_run, source),
            daemon=True,
        )
        t.start()

        # Log immediate start status
        self.executor.log_job_start(job_name, dry_run, source)

        # Only redirect when serving an HTTP request
        if handler is not None:
            TemplateService.send_redirect(handler, "/")

    def run_backup_job_headless(self, job_name, dry_run=True, source="scheduler"):
        """
        Convenience wrapper for scheduler/CLI use (no HTTP handler).
        """
        self.run_backup_job(handler=None, job_name=job_name, dry_run=dry_run, source=source)
    
    def run_backup_job_with_conflict_check(self, handler, job_name, dry_run=True, source="schedule"):
        """
        Run backup job with runtime conflict detection and avoidance.
        Will wait for conflicting jobs to finish before running.
        """
        if job_name not in self.backup_config.config.get("backup_jobs", {}):
            if handler is not None:
                TemplateService.send_error_response(handler, f"Job '{job_name}' not found")
            return

        job_config = self.backup_config.config["backup_jobs"][job_name]
        
        # Handle conflicts and delays
        delay_info = self.conflict_handler.wait_for_conflicts_to_resolve(job_name, job_config)
        
        # Send delay notification if needed
        if delay_info and delay_info['total_wait_time'] > 0:
            self.notification_dispatcher.send_delay_notification(
                job_name, delay_info['total_wait_time'], delay_info['conflicting_jobs'], source
            )

        # Register this job as running
        self.conflict_handler.register_running_job(job_name)
        
        try:
            # Run the actual backup job
            self.run_backup_job(handler, job_name, dry_run, source)
        finally:
            # Always unregister the job, even if it fails
            self.conflict_handler.unregister_running_job(job_name)

    # ---------------------------
    # Background worker
    # ---------------------------
    def _run_job_background(self, job_name, job_config, dry_run, trigger_source):
        """
        Runs in a daemon thread: executes backup and handles notifications.
        """
        try:
            result = self.executor.execute_backup(job_name, job_config, dry_run, trigger_source)
            
            # Send appropriate notification
            if result["success"]:
                self.notification_dispatcher.send_success_notification(
                    job_name, result["duration"], dry_run
                )
            else:
                error_msg = f'Return code {result["return_code"]}'
                self.notification_dispatcher.send_failure_notification(
                    job_name, error_msg, dry_run
                )
                
        except Exception as e:
            # Log and notify about execution failure
            self.executor.log_job_error(job_name, str(e))
            self.notification_dispatcher.send_failure_notification(job_name, str(e), dry_run)