"""
Notification provider factory service
Handles creation and configuration of notification providers
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


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
            notify_on_success=False,  # Success notifications are now per-job only
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
            notify_on_success=False,  # Success notifications are now per-job only
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
    
    @staticmethod
    def get_notification_config_template() -> Dict[str, Any]:
        """Get template configuration for notifications"""
        return {
            "notification": {
                "telegram": {
                    "enabled": False,  # Enable/disable Telegram globally
                    "token": "",  # Bot token from @BotFather
                    "chat_id": "",  # Chat ID where notifications will be sent
                },
                "email": {
                    "enabled": False,  # Enable/disable Email globally
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
                #     "webhook_url": "",
                #     "channel": ""
                # },
                # "discord": {
                #     "enabled": False,
                #     "webhook_url": ""
                # }
            },
            # Per-job notification configuration example:
            "backup_jobs": {
                "example_job": {
                    "notifications": [
                        {
                            "provider": "telegram",
                            "notify_on_success": True,
                            "notify_on_failure": True,
                            "notify_on_maintenance_failure": False,  # For future maintenance system
                            "success_message": "Job '{job_name}' completed in {duration}",
                            "failure_message": "Job '{job_name}' failed: {error_message}"
                        }
                    ]
                }
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