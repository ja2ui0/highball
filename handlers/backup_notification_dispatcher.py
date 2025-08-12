"""
Backup notification dispatcher
Centralized notification handling for backup events
"""


class BackupNotificationDispatcher:
    """Handles all backup-related notifications"""

    def __init__(self, backup_config):
        self.backup_config = backup_config

    def send_success_notification(self, job_name, duration_seconds, dry_run):
        """Send notification for successful job completion"""
        try:
            from services.notification_service import NotificationService
            notifier = NotificationService(self.backup_config)
            notifier.send_job_success_notification(job_name, duration_seconds, dry_run)
        except Exception as notify_error:
            print(f"WARNING: Failed to send job completion notification: {str(notify_error)}")

    def send_failure_notification(self, job_name, error_message, dry_run):
        """Send notification for job failure"""
        try:
            from services.notification_service import NotificationService
            notifier = NotificationService(self.backup_config)
            notifier.send_job_failure_notification(job_name, error_message, dry_run)
        except Exception as notify_error:
            print(f"WARNING: Failed to send job failure notification: {str(notify_error)}")

    def send_delay_notification(self, job_name, delay_seconds, conflicting_jobs, source):
        """Send notification about job delay due to conflicts"""
        # Check if delay is significant enough to notify
        if delay_seconds < self._get_delay_notification_threshold():
            return
            
        try:
            from services.notification_service import NotificationService
            notifier = NotificationService(self.backup_config)
            
            delay_minutes = delay_seconds / 60
            notifier.send_job_delay_notification(job_name, delay_minutes, conflicting_jobs, source)
            print(f"INFO: Sent delay notification for job '{job_name}' (delayed {delay_minutes:.1f} minutes)")
        except Exception as e:
            print(f"WARNING: Failed to send delay notification for job '{job_name}': {str(e)}")

    def _get_delay_notification_threshold(self):
        """Get minimum delay time before sending notification (in seconds)"""
        global_settings = self.backup_config.config.get("global_settings", {})
        return global_settings.get("delay_notification_threshold", 300)  # Default 5 minutes