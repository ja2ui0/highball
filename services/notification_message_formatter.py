"""
Notification message formatting and template service
Handles message templates, variable expansion, and formatting
"""
from datetime import datetime
from typing import Dict, Any, Optional, List


class NotificationMessageFormatter:
    """Service for formatting notification messages with template support"""
    
    def __init__(self):
        pass
    
    def format_message_with_timestamp(self, message: str) -> str:
        """Add timestamp to message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] {message}"
    
    def format_duration(self, duration_seconds: float) -> str:
        """Format duration for display"""
        duration_minutes = duration_seconds / 60
        if duration_minutes < 1:
            return f"{duration_seconds:.1f} seconds"
        return f"{duration_minutes:.1f} minutes"
    
    def expand_template_variables(self, message: str, job_name: Optional[str] = None, 
                                 duration: Optional[str] = None, error_message: Optional[str] = None) -> str:
        """Expand template variables in notification messages"""
        if not message:
            return message
            
        # Available template variables
        variables = {
            'job_name': job_name or 'Unknown Job',
            'duration': duration or 'Unknown',
            'error_message': error_message or 'No details available',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Simple template variable expansion
        expanded_message = message
        for var_name, var_value in variables.items():
            expanded_message = expanded_message.replace(f'{{{var_name}}}', str(var_value))
        
        return expanded_message
    
    def get_job_specific_message(self, default_message: str, notification_type: str, 
                                provider_name: str, job_notifications: Optional[List[Dict[str, Any]]]) -> str:
        """Get job-specific message template if available (without timestamp formatting)"""
        if not job_notifications:
            return default_message
        
        # Find configuration for this provider
        for job_notif in job_notifications:
            if job_notif.get('provider') == provider_name:
                # Get custom message based on notification type
                if notification_type == 'success' and 'success_message' in job_notif:
                    return job_notif['success_message']
                elif notification_type in ['error', 'warning', 'info'] and 'failure_message' in job_notif:
                    return job_notif['failure_message']
        
        return default_message
    
    def create_job_delay_message(self, job_name: str, delay_minutes: float, 
                                conflicting_jobs: List[str], source: str) -> tuple[str, str]:
        """Create message for job delay notifications"""
        title = f"Job Delayed: {job_name}"
        conflict_list = ", ".join(conflicting_jobs) if conflicting_jobs else "unknown jobs"
        message = (
            f"Backup job '{job_name}' was delayed {delay_minutes:.1f} minutes due to resource conflicts.\n\n"
            f"Conflicting jobs: {conflict_list}\n"
            f"Triggered by: {source}\n\n"
            f"Consider adjusting schedules to reduce conflicts."
        )
        return title, message
    
    def create_job_failure_message(self, job_name: str, error_message: str, dry_run: bool = False) -> tuple[str, str]:
        """Create message for job failure notifications"""
        mode = "dry run" if dry_run else "backup"
        title = f"Job Failed: {job_name}"
        
        message = (
            f"Backup job '{job_name}' {mode} failed.\n\n"
            f"Error: {error_message}\n\n"
            f"Check logs for detailed information."
        )
        
        return title, message
    
    def create_job_success_message(self, job_name: str, duration_seconds: float, dry_run: bool = False) -> tuple[str, str]:
        """Create message for successful job completion"""
        mode = "dry run" if dry_run else "backup"
        title = f"Job Completed: {job_name}"
        
        duration_str = self.format_duration(duration_seconds)
        message = (
            f"Backup job '{job_name}' {mode} completed successfully.\n\n"
            f"Duration: {duration_str}"
        )
        
        return title, message
    
    def create_maintenance_failure_message(self, job_name: str, operation: str, error_message: str) -> tuple[str, str]:
        """Create message for maintenance operation failures"""
        title = f"Maintenance Failed: {job_name}"
        
        message = (
            f"Repository maintenance operation '{operation}' failed for job '{job_name}'.\n\n"
            f"Error: {error_message}\n\n"
            f"Check logs for detailed information. Repository integrity may be affected."
        )
        
        return title, message
    
    def format_message_for_provider(self, provider_name: str, title: str, message: str, notification_type: str) -> Dict[str, Any]:
        """Format message according to provider-specific requirements"""
        # Format message with type prefix (no emojis)
        prefixes = {
            "info": "[INFO]",
            "success": "[SUCCESS]", 
            "warning": "[WARNING]",
            "error": "[ERROR]",
            "maintenance": "[MAINTENANCE]"
        }
        prefix = prefixes.get(notification_type, "[INFO]")
        
        if provider_name == "telegram":
            # Telegram supports markdown formatting
            return {
                "message": f"{prefix} **{title}**\n\n{message}",
                "parse_mode": "markdown"
            }
        
        elif provider_name == "email":
            # Email needs subject and body
            return {
                "subject": f"Highball: {title}",
                "message": f"Highball Backup Manager\n\n{message}"
            }
        
        else:
            # Generic provider (for future extensions)
            return {
                "message": f"{prefix} {title}\n\n{message}"
            }