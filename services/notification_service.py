"""
Notification service - pure coordinator for backup job alerts and status updates
Thin orchestration layer that delegates to specialized services
"""
from typing import Dict, Any, List, Optional
from services.notification_provider_factory import NotificationProviderFactory, NotificationProvider
from services.notification_message_formatter import NotificationMessageFormatter
from services.notification_sender import NotificationSender, NotificationResult
from services.notification_job_config_manager import NotificationJobConfigManager
from services.notification_queue_coordinator import NotificationQueueCoordinator


class NotificationService:
    """Pure coordinator for notification system - delegates to specialized services"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.global_settings = backup_config.config.get("global_settings", {})
        self.notification_config = self.global_settings.get("notification", {})
        
        # Initialize service components
        self.provider_factory = NotificationProviderFactory()
        self.message_formatter = NotificationMessageFormatter()
        self.sender = NotificationSender()
        
        # Initialize providers using factory
        self.providers = {
            p.provider_name: p 
            for p in self.provider_factory.create_all_providers(self.notification_config)
        }
        
        # Initialize specialized coordinators
        self.job_config_manager = NotificationJobConfigManager(backup_config)
        self.queue_coordinator = NotificationQueueCoordinator(self.notification_config, self.providers)
    
    def send_notification(self, title: str, message: str, notification_type: str = "info", job_name: Optional[str] = None):
        """Send notification via all configured providers with queue support"""
        if not self.is_notifications_enabled():
            return
        
        formatted_message = self.message_formatter.format_message_with_timestamp(message)
        
        # Get job-specific notification settings if job_name provided
        job_notifications = self.job_config_manager.get_job_notification_config(job_name) if job_name else None
        
        # Process each provider individually for queue management
        for provider in self.providers.values():
            if provider.is_valid():
                # Check if this provider should be used for this job and notification type
                if self.job_config_manager.should_send_to_provider(provider, notification_type, job_notifications):
                    # Get job-specific message if available
                    final_message = self.message_formatter.get_job_specific_message(
                        formatted_message, notification_type, provider.provider_name, job_notifications
                    )
                    self.queue_coordinator.send_via_provider_with_queue(
                        provider, title, final_message, notification_type, job_name
                    )
    
    def send_job_delay_notification(self, job_name: str, delay_minutes: float, 
                                  conflicting_jobs: List[str], source: str):
        """Send specific notification for job delays due to conflicts"""
        title, message = self.message_formatter.create_job_delay_message(
            job_name, delay_minutes, conflicting_jobs, source
        )
        self.send_notification(title, message, "warning", job_name)
    
    def send_job_failure_notification(self, job_name: str, error_message: str, dry_run: bool = False):
        """Send notification for job failures"""
        title, default_message = self.message_formatter.create_job_failure_message(
            job_name, error_message, dry_run
        )
        
        # Send notification - per-job logic will handle custom messages and template expansion
        self._send_job_notification(title, default_message, "error", job_name, error_message=error_message)
    
    def send_job_success_notification(self, job_name: str, duration_seconds: float, dry_run: bool = False):
        """Send notification for successful job completion (if enabled per method)"""
        title, default_message = self.message_formatter.create_job_success_message(
            job_name, duration_seconds, dry_run
        )
        
        duration_str = self.message_formatter.format_duration(duration_seconds)
        
        # Send notification - per-job logic will handle custom messages and template expansion
        self._send_job_notification(title, default_message, "success", job_name, duration=duration_str)
    
    def send_maintenance_failure_notification(self, job_name: str, operation: str, error_message: str):
        """Send notification for maintenance operation failures"""
        title, default_message = self.message_formatter.create_maintenance_failure_message(
            job_name, operation, error_message
        )
        
        # Send notification - per-job logic will handle custom messages and template expansion
        self._send_job_notification(title, default_message, "maintenance", job_name, 
                                   operation=operation, error_message=error_message)
    
    def is_notifications_enabled(self) -> bool:
        """Check if any notification provider is enabled"""
        return any(provider.is_valid() for provider in self.providers.values())
    
    def test_notifications(self) -> bool:
        """Test all configured notification providers"""
        test_title = "Highball Test Notification"
        test_message = "This is a test notification to verify your notification settings are working correctly."
        
        print("Testing notification providers...")
        self.send_notification(test_title, test_message, "info")
        return self.is_notifications_enabled()
    
    def test_notification_with_results(self, title: str, message: str, notification_type: str = "info") -> List[NotificationResult]:
        """Test notification and return detailed results for validation"""
        if not self.is_notifications_enabled():
            return []
        
        formatted_message = self.message_formatter.format_message_with_timestamp(message)
        results = self._send_to_all_providers(title, formatted_message, notification_type)
        return results
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names for future frontend expansion"""
        return list(self.providers.keys())
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of currently enabled provider names"""
        return [name for name, provider in self.providers.items() if provider.is_valid()]
    
    def get_queue_status(self, provider: str) -> Dict[str, Any]:
        """Get queue status for a specific provider"""
        return self.queue_coordinator.get_queue_status(provider)
    
    def get_all_queue_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get queue status for all enabled providers"""
        return self.queue_coordinator.get_all_queue_statuses()
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get overall queue statistics across all providers"""
        return self.queue_coordinator.get_queue_statistics()
    
    def get_job_notification_summary(self, job_name: str) -> Dict[str, Any]:
        """Get summary of notification settings for a job"""
        return self.job_config_manager.get_job_notification_summary(job_name)
    
    def validate_job_notifications(self, job_name: str) -> Dict[str, Any]:
        """Validate notification configuration for a job"""
        return self.job_config_manager.validate_job_notification_config(job_name)
    
    def _send_job_notification(self, title: str, default_message: str, notification_type: str, job_name: str, **template_vars):
        """Send job notification with template variable support"""
        if not self.is_notifications_enabled():
            return
        
        # Get job-specific notification settings
        job_notifications = self.job_config_manager.get_job_notification_config(job_name)
        
        # Process each provider individually
        for provider in self.providers.values():
            if provider.is_valid():
                # Check if this provider should be used for this job and notification type
                if self.job_config_manager.should_send_to_provider(provider, notification_type, job_notifications):
                    # Get job-specific message if available, otherwise use default
                    message = self.message_formatter.get_job_specific_message(
                        default_message, notification_type, provider.provider_name, job_notifications
                    )
                    
                    # Expand template variables
                    final_message = self.message_formatter.expand_template_variables(
                        message, job_name=job_name, **template_vars
                    )
                    
                    # Format with timestamp
                    formatted_message = self.message_formatter.format_message_with_timestamp(final_message)
                    
                    # Send via queue system
                    self.queue_coordinator.send_via_provider_with_queue(
                        provider, title, formatted_message, notification_type, job_name
                    )
    
    def _send_to_all_providers(self, title: str, message: str, notification_type: str) -> List[NotificationResult]:
        """Send to all enabled providers"""
        results = []
        
        for provider in self.providers.values():
            if provider.is_valid():
                formatted_content = self.message_formatter.format_message_for_provider(
                    provider.provider_name, title, message, notification_type
                )
                success, error = self.sender.send_via_provider(provider, formatted_content, notification_type)
                results.append(NotificationResult(provider.provider_name, success, error))
        
        return results


class NotificationManager:
    """Factory for creating notification services"""
    
    @staticmethod
    def create_notifier(backup_config):
        """Create a notification service instance"""
        return NotificationService(backup_config)
    
    @staticmethod
    def get_notification_config_template() -> Dict[str, Any]:
        """Get template configuration for notifications"""
        return NotificationProviderFactory.get_notification_config_template()