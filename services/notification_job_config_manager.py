"""
Notification job configuration manager
Handles job-specific notification settings and provider selection logic
"""
from typing import Dict, Any, List, Optional
from services.notification_provider_factory import NotificationProvider


class NotificationJobConfigManager:
    """Service for managing job-specific notification configurations"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def get_job_notification_config(self, job_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get notification configuration for a specific job"""
        if not job_name:
            return None
            
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        return job_config.get('notifications', [])
    
    def should_send_to_provider(self, provider: NotificationProvider, notification_type: str, 
                               job_notifications: Optional[List[Dict[str, Any]]]) -> bool:
        """Check if notification should be sent to this provider based on job config"""
        # Success notifications are ONLY per-job now - no global fallback
        if notification_type == 'success':
            if not job_notifications:
                return False  # No job config = no success notifications
            
            # Find configuration for this provider in job settings
            for job_notif in job_notifications:
                if job_notif.get('provider') == provider.provider_name:
                    return job_notif.get('notify_on_success', False)
            
            return False  # Provider not configured for this job
        
        # Maintenance notifications are per-job only
        if notification_type == 'maintenance':
            if not job_notifications:
                return False  # No job config = no maintenance notifications
            
            # Find configuration for this provider in job settings
            for job_notif in job_notifications:
                if job_notif.get('provider') == provider.provider_name:
                    return job_notif.get('notify_on_maintenance_failure', False)
            
            return False  # Provider not configured for this job
        
        # Non-success notifications (error, warning, info) use job config if available, otherwise send
        if not job_notifications:
            return True  # Send error/warning/info notifications if no job-specific config
        
        # Find configuration for this provider in job settings
        for job_notif in job_notifications:
            if job_notif.get('provider') == provider.provider_name:
                return job_notif.get('notify_on_failure', True)
        
        # Provider not configured for this job, default to sending for failures
        return True
    
    def get_providers_for_job(self, job_name: str, notification_type: str, 
                             all_providers: Dict[str, NotificationProvider]) -> List[NotificationProvider]:
        """Get list of providers that should receive notifications for this job and type"""
        job_notifications = self.get_job_notification_config(job_name)
        valid_providers = []
        
        for provider in all_providers.values():
            if provider.is_valid():
                if self.should_send_to_provider(provider, notification_type, job_notifications):
                    valid_providers.append(provider)
        
        return valid_providers
    
    def get_job_notification_summary(self, job_name: str) -> Dict[str, Any]:
        """Get summary of notification settings for a job"""
        job_notifications = self.get_job_notification_config(job_name)
        
        if not job_notifications:
            return {
                'configured': False,
                'providers': [],
                'success_enabled': False,
                'failure_enabled': True,  # Default behavior
                'maintenance_enabled': False
            }
        
        providers = []
        success_enabled = False
        failure_enabled = False
        maintenance_enabled = False
        
        for job_notif in job_notifications:
            provider_name = job_notif.get('provider', 'unknown')
            providers.append({
                'provider': provider_name,
                'notify_on_success': job_notif.get('notify_on_success', False),
                'notify_on_failure': job_notif.get('notify_on_failure', True),
                'notify_on_maintenance_failure': job_notif.get('notify_on_maintenance_failure', False),
                'has_custom_success_message': bool(job_notif.get('success_message')),
                'has_custom_failure_message': bool(job_notif.get('failure_message'))
            })
            
            # Track if any provider has these enabled
            if job_notif.get('notify_on_success', False):
                success_enabled = True
            if job_notif.get('notify_on_failure', True):
                failure_enabled = True
            if job_notif.get('notify_on_maintenance_failure', False):
                maintenance_enabled = True
        
        return {
            'configured': True,
            'providers': providers,
            'success_enabled': success_enabled,
            'failure_enabled': failure_enabled,
            'maintenance_enabled': maintenance_enabled
        }
    
    def validate_job_notification_config(self, job_name: str) -> Dict[str, Any]:
        """Validate notification configuration for a job"""
        job_notifications = self.get_job_notification_config(job_name)
        
        if not job_notifications:
            return {
                'valid': True,
                'warnings': ['No notification configuration - using defaults'],
                'errors': []
            }
        
        warnings = []
        errors = []
        
        for i, job_notif in enumerate(job_notifications):
            provider = job_notif.get('provider')
            if not provider:
                errors.append(f"Configuration {i+1}: Missing provider name")
                continue
            
            # Check if at least one notification type is enabled
            notify_success = job_notif.get('notify_on_success', False)
            notify_failure = job_notif.get('notify_on_failure', False)
            notify_maintenance = job_notif.get('notify_on_maintenance_failure', False)
            
            if not any([notify_success, notify_failure, notify_maintenance]):
                warnings.append(f"Provider '{provider}': No notification types enabled")
            
            # Check for custom messages without corresponding enabled types
            if job_notif.get('success_message') and not notify_success:
                warnings.append(f"Provider '{provider}': Custom success message defined but success notifications disabled")
            
            if job_notif.get('failure_message') and not notify_failure:
                warnings.append(f"Provider '{provider}': Custom failure message defined but failure notifications disabled")
        
        return {
            'valid': len(errors) == 0,
            'warnings': warnings,
            'errors': errors
        }