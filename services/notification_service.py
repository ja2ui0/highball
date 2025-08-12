"""
Notification service for backup job alerts and status updates
Refactored with dataclasses and modern patterns, emoji-free
"""
import requests
import smtplib
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


@dataclass
class NotificationConfig:
    """Base configuration for notification providers"""
    enabled: bool = False
    notify_on_success: bool = False


@dataclass
class TelegramConfig(NotificationConfig):
    """Telegram notification configuration"""
    token: str = ""
    chat_id: str = ""
    
    def is_valid(self) -> bool:
        return self.enabled and bool(self.token and self.chat_id)


@dataclass
class EmailConfig(NotificationConfig):
    """Email notification configuration"""
    smtp_server: str = ""
    smtp_port: int = 587
    use_tls: bool = True
    use_ssl: bool = False
    from_email: str = ""
    to_email: str = ""
    username: str = ""
    password: str = ""
    
    def is_valid(self) -> bool:
        return (self.enabled and 
                bool(self.smtp_server and self.smtp_port and 
                     self.from_email and self.to_email))


@dataclass
class NotificationResult:
    """Result of notification attempt"""
    provider: str
    success: bool
    error_message: Optional[str] = None


class NotificationService:
    """Handles notifications for backup events - modernized and emoji-free"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.global_settings = backup_config.config.get("global_settings", {})
        self.notification_config = self.global_settings.get("notification", {})
        
        # Initialize typed configs
        self.telegram = self._build_telegram_config()
        self.email = self._build_email_config()
    
    def _build_telegram_config(self) -> TelegramConfig:
        """Build typed Telegram configuration"""
        config = self.notification_config.get("telegram", {})
        return TelegramConfig(
            enabled=config.get("enabled", False),
            notify_on_success=config.get("notify_on_success", False),
            token=config.get("token", ""),
            chat_id=config.get("chat_id", "")
        )
    
    def _build_email_config(self) -> EmailConfig:
        """Build typed Email configuration"""
        config = self.notification_config.get("email", {})
        return EmailConfig(
            enabled=config.get("enabled", False),
            notify_on_success=config.get("notify_on_success", False),
            smtp_server=config.get("smtp_server", ""),
            smtp_port=config.get("smtp_port", 587),
            use_tls=config.get("use_tls", True),
            use_ssl=config.get("use_ssl", False),
            from_email=config.get("from_email", ""),
            to_email=config.get("to_email", ""),
            username=config.get("username", ""),
            password=config.get("password", "")
        )
    
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
        return self.telegram.is_valid() or self.email.is_valid()
    
    def test_notifications(self) -> bool:
        """Test all configured notification providers"""
        test_title = "Highball Test Notification"
        test_message = "This is a test notification to verify your notification settings are working correctly."
        
        print("Testing notification providers...")
        self.send_notification(test_title, test_message, "info")
        return self.is_notifications_enabled()
    
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
        
        if self.telegram.is_valid():
            success, error = self._send_telegram(title, message, notification_type)
            results.append(NotificationResult("telegram", success, error))
        
        if self.email.is_valid():
            success, error = self._send_email(title, message, notification_type)
            results.append(NotificationResult("email", success, error))
        
        return results
    
    def _send_success_notifications(self, title: str, message: str) -> List[NotificationResult]:
        """Send to providers that have success notifications enabled"""
        results = []
        
        if self.telegram.is_valid() and self.telegram.notify_on_success:
            success, error = self._send_telegram(title, message, "success")
            results.append(NotificationResult("telegram", success, error))
        
        if self.email.is_valid() and self.email.notify_on_success:
            success, error = self._send_email(title, message, "success")
            results.append(NotificationResult("email", success, error))
        
        return results
    
    def _send_telegram(self, title: str, message: str, notification_type: str) -> tuple[bool, Optional[str]]:
        """Send notification via Telegram Bot API"""
        try:
            # Format message without emojis
            prefixes = {
                "info": "[INFO]",
                "success": "[SUCCESS]", 
                "warning": "[WARNING]",
                "error": "[ERROR]"
            }
            prefix = prefixes.get(notification_type, "[INFO]")
            formatted_text = f"{prefix} **{title}**\n\n{message}"
            
            url = f"https://api.telegram.org/bot{self.telegram.token}/sendMessage"
            data = {
                "chat_id": self.telegram.chat_id,
                "text": formatted_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                return True, None
            else:
                return False, f"Telegram API error {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, f"Failed to send Telegram notification: {str(e)}"
    
    def _send_email(self, title: str, message: str, notification_type: str) -> tuple[bool, Optional[str]]:
        """Send notification via email SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email.from_email
            msg['To'] = self.email.to_email
            msg['Subject'] = f"Highball: {title}"
            
            # Add body with plain text
            body = f"Highball Backup Manager\n\n{message}"
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            if self.email.use_ssl:
                server = smtplib.SMTP_SSL(self.email.smtp_server, self.email.smtp_port)
            else:
                server = smtplib.SMTP(self.email.smtp_server, self.email.smtp_port)
                if self.email.use_tls:
                    server.starttls()
            
            # Authenticate if credentials provided
            if self.email.username and self.email.password:
                server.login(self.email.username, self.email.password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            return True, None
            
        except Exception as e:
            return False, f"Failed to send email notification: {str(e)}"
    
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
            }
        }