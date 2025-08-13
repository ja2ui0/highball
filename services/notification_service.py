"""
Notification service for backup job alerts and status updates
Modern implementation using notifiers library with extensible backend
"""
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from notifiers import get_notifier


@dataclass
class NotificationProvider:
    """Base notification provider configuration"""
    provider_name: str
    enabled: bool = False
    notify_on_success: bool = False
    config: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if provider configuration is valid"""
        return self.enabled and bool(self.config)


@dataclass
class NotificationResult:
    """Result of notification attempt"""
    provider: str
    success: bool
    error_message: Optional[str] = None


class NotificationProviderFactory:
    """Factory for creating notification providers from config"""
    
    @staticmethod
    def create_telegram_provider(config: Dict[str, Any]) -> NotificationProvider:
        """Create Telegram provider from configuration"""
        telegram_config = config.get("telegram", {})
        
        # Build notifiers-compatible config
        provider_config = {}
        if telegram_config.get("token") and telegram_config.get("chat_id"):
            provider_config = {
                "token": telegram_config["token"],
                "chat_id": telegram_config["chat_id"],
                "parse_mode": "markdown",
                "disable_web_page_preview": True
            }
        
        return NotificationProvider(
            provider_name="telegram",
            enabled=telegram_config.get("enabled", False),
            notify_on_success=telegram_config.get("notify_on_success", False),
            config=provider_config
        )
    
    @staticmethod
    def create_email_provider(config: Dict[str, Any]) -> NotificationProvider:
        """Create Email provider from configuration"""
        email_config = config.get("email", {})
        
        # Build notifiers-compatible config
        provider_config = {}
        if all(email_config.get(key) for key in ["smtp_server", "from_email", "to_email"]):
            provider_config = {
                "to": email_config["to_email"],
                "from": email_config["from_email"],
                "subject": "Highball: {title}",  # Template for dynamic subject
                "host": email_config["smtp_server"],
                "port": email_config.get("smtp_port", 587),
                "tls": email_config.get("use_tls", True),
                "ssl": email_config.get("use_ssl", False),
                "username": email_config.get("username", ""),
                "password": email_config.get("password", "")
            }
        
        return NotificationProvider(
            provider_name="email",
            enabled=email_config.get("enabled", False),
            notify_on_success=email_config.get("notify_on_success", False),
            config=provider_config
        )
    
    @staticmethod
    def create_all_providers(notification_config: Dict[str, Any]) -> List[NotificationProvider]:
        """Create all providers from notification configuration"""
        providers = []
        
        # Current providers (keeping frontend unchanged)
        providers.append(NotificationProviderFactory.create_telegram_provider(notification_config))
        providers.append(NotificationProviderFactory.create_email_provider(notification_config))
        
        # Future providers can be easily added here:
        # providers.append(NotificationProviderFactory.create_slack_provider(notification_config))
        # providers.append(NotificationProviderFactory.create_discord_provider(notification_config))
        # providers.append(NotificationProviderFactory.create_sms_provider(notification_config))
        
        return providers


class NotificationService:
    """Modern notification service using notifiers library"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.global_settings = backup_config.config.get("global_settings", {})
        self.notification_config = self.global_settings.get("notification", {})
        
        # Initialize providers using factory
        self.providers = {
            p.provider_name: p 
            for p in NotificationProviderFactory.create_all_providers(self.notification_config)
        }
    
    def send_notification(self, title: str, message: str, notification_type: str = "info"):
        """Send notification via all configured providers"""
        if not self.is_notifications_enabled():
            return
        
        formatted_message = self._format_message(message)
        results = self._send_to_all_providers(title, formatted_message, notification_type)
        self._log_notification_results(results)
    
    def send_job_delay_notification(self, job_name: str, delay_minutes: float, 
                                  conflicting_jobs: List[str], source: str):
        """Send specific notification for job delays due to conflicts"""
        title = f"Job Delayed: {job_name}"
        conflict_list = ", ".join(conflicting_jobs) if conflicting_jobs else "unknown jobs"
        message = (
            f"Backup job '{job_name}' was delayed {delay_minutes:.1f} minutes due to resource conflicts.\n\n"
            f"Conflicting jobs: {conflict_list}\n"
            f"Triggered by: {source}\n\n"
            f"Consider adjusting schedules to reduce conflicts."
        )
        self.send_notification(title, message, "warning")
    
    def send_job_failure_notification(self, job_name: str, error_message: str, dry_run: bool = False):
        """Send notification for job failures"""
        mode = "dry run" if dry_run else "backup"
        title = f"Job Failed: {job_name}"
        message = (
            f"Backup job '{job_name}' {mode} failed.\n\n"
            f"Error: {error_message}\n\n"
            f"Check logs for detailed information."
        )
        self.send_notification(title, message, "error")
    
    def send_job_success_notification(self, job_name: str, duration_seconds: float, dry_run: bool = False):
        """Send notification for successful job completion (if enabled per method)"""
        mode = "dry run" if dry_run else "backup"
        title = f"Job Completed: {job_name}"
        
        duration_str = self._format_duration(duration_seconds)
        message = (
            f"Backup job '{job_name}' {mode} completed successfully.\n\n"
            f"Duration: {duration_str}"
        )
        
        formatted_message = self._format_message(message)
        results = self._send_success_notifications(title, formatted_message)
        self._log_success_notification_results(results, job_name)
    
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
        
        formatted_message = self._format_message(message)
        results = self._send_to_all_providers(title, formatted_message, notification_type)
        return results
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names for future frontend expansion"""
        return list(self.providers.keys())
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of currently enabled provider names"""
        return [name for name, provider in self.providers.items() if provider.is_valid()]
    
    def _format_message(self, message: str) -> str:
        """Add timestamp to message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] {message}"
    
    def _format_duration(self, duration_seconds: float) -> str:
        """Format duration for display"""
        duration_minutes = duration_seconds / 60
        if duration_minutes < 1:
            return f"{duration_seconds:.1f} seconds"
        return f"{duration_minutes:.1f} minutes"
    
    def _send_to_all_providers(self, title: str, message: str, notification_type: str) -> List[NotificationResult]:
        """Send to all enabled providers"""
        results = []
        
        for provider in self.providers.values():
            if provider.is_valid():
                success, error = self._send_via_provider(provider, title, message, notification_type)
                results.append(NotificationResult(provider.provider_name, success, error))
        
        return results
    
    def _send_success_notifications(self, title: str, message: str) -> List[NotificationResult]:
        """Send to providers that have success notifications enabled"""
        results = []
        
        for provider in self.providers.values():
            if provider.is_valid() and provider.notify_on_success:
                success, error = self._send_via_provider(provider, title, message, "success")
                results.append(NotificationResult(provider.provider_name, success, error))
        
        return results
    
    def _send_via_provider(self, provider: NotificationProvider, title: str, 
                          message: str, notification_type: str) -> tuple[bool, Optional[str]]:
        """Send notification via specific provider using notifiers library"""
        try:
            notifier = get_notifier(provider.provider_name)
            
            # Format message with type prefix (no emojis)
            prefixes = {
                "info": "[INFO]",
                "success": "[SUCCESS]", 
                "warning": "[WARNING]",
                "error": "[ERROR]"
            }
            prefix = prefixes.get(notification_type, "[INFO]")
            
            # Prepare notification content and send
            result = None
            if provider.provider_name == "telegram":
                # Telegram supports markdown formatting
                formatted_text = f"{prefix} **{title}**\n\n{message}"
                result = notifier.notify(message=formatted_text, **provider.config)
            
            elif provider.provider_name == "email":
                # Email needs subject and body
                email_config = provider.config.copy()
                email_config["subject"] = f"Highball: {title}"
                email_config["message"] = f"Highball Backup Manager\n\n{message}"
                result = notifier.notify(**email_config)
            
            else:
                # Generic provider (for future extensions)
                formatted_text = f"{prefix} {title}\n\n{message}"
                result = notifier.notify(message=formatted_text, **provider.config)
            
            # Check result status
            if result and hasattr(result, 'status'):
                if str(result.status).lower() == 'success':
                    return True, None
                else:
                    # Get error details from result
                    errors = getattr(result, 'errors', ['Unknown error'])
                    return False, f"Notification failed: {', '.join(errors)}"
            else:
                # Fallback for providers that don't return status objects
                return True, None
            
        except Exception as e:
            return False, f"Failed to send {provider.provider_name} notification: {str(e)}"
    
    def _log_notification_results(self, results: List[NotificationResult]):
        """Log results of notification attempts"""
        if not results:
            print("INFO: No notification providers configured - notification skipped")
            return
        
        successful = [r for r in results if r.success]
        if successful:
            providers = ", ".join(r.provider for r in successful)
            print(f"INFO: Notification sent successfully via {len(successful)}/{len(results)} providers: {providers}")
        else:
            providers = ", ".join(r.provider for r in results)
            print(f"WARNING: Notification failed via all {len(results)} providers: {providers}")
            for result in results:
                if result.error_message:
                    print(f"  - {result.provider}: {result.error_message}")
    
    def _log_success_notification_results(self, results: List[NotificationResult], job_name: str):
        """Log results of success notification attempts"""
        if not results:
            print(f"INFO: Success notifications disabled for job '{job_name}' - skipped")
            return
        
        successful = [r for r in results if r.success]
        if successful:
            providers = ", ".join(r.provider for r in successful)
            print(f"INFO: Success notification sent via {len(successful)}/{len(results)} providers: {providers}")
        else:
            providers = ", ".join(r.provider for r in results)
            print(f"WARNING: Success notification failed via all {len(results)} providers: {providers}")


class NotificationManager:
    """Factory for creating notification services"""
    
    @staticmethod
    def create_notifier(backup_config):
        """Create a notification service instance"""
        return NotificationService(backup_config)
    
    @staticmethod
    def get_notification_config_template() -> Dict[str, Any]:
        """Get template configuration for notifications"""
        return {
            "notification": {
                "telegram": {
                    "enabled": False,
                    "notify_on_success": False,
                    "token": "",  # Bot token from @BotFather
                    "chat_id": "",  # Chat ID where notifications will be sent
                },
                "email": {
                    "enabled": False,
                    "notify_on_success": False,
                    "smtp_server": "smtp.gmail.com",  # SMTP server hostname
                    "smtp_port": 587,  # SMTP port (587 for TLS, 465 for SSL, 25 for plain)
                    "use_tls": True,  # Use TLS encryption
                    "use_ssl": False,  # Use SSL encryption (alternative to TLS)
                    "from_email": "",  # Sender email address
                    "to_email": "",  # Recipient email address
                    "username": "",  # SMTP authentication username
                    "password": ""  # SMTP authentication password
                }
                # Future providers can be easily added here:
                # "slack": {
                #     "enabled": False,
                #     "notify_on_success": False,
                #     "webhook_url": "",
                #     "channel": ""
                # },
                # "discord": {
                #     "enabled": False,
                #     "notify_on_success": False,
                #     "webhook_url": ""
                # }
            }
        }


# Utility function for future provider expansion
def get_supported_providers() -> List[str]:
    """Get list of all providers supported by notifiers library"""
    try:
        from notifiers import all_providers
        return [provider.name for provider in all_providers()]
    except ImportError:
        return ["telegram", "email"]  # Fallback if notifiers not available