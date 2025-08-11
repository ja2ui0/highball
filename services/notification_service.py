"""
Notification service for backup job alerts and status updates
Supports Telegram, email, and extensible provider framework
"""
import requests
import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class NotificationService:
    """Handles notifications for backup events"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.global_settings = backup_config.config.get("global_settings", {})
        self.notification_config = self.global_settings.get("notification", {})
    
    def send_notification(self, title, message, notification_type="info"):
        """
        Send notification via all configured providers
        
        Args:
            title: Notification title/subject
            message: Notification message body
            notification_type: Type of notification (info, warning, error, success)
        """
        if not self.is_notifications_enabled():
            return
        
        # Add timestamp and formatting
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Send via all enabled providers
        providers_attempted = []
        providers_successful = []
        
        # Try Telegram
        if self.is_telegram_enabled():
            providers_attempted.append("telegram")
            if self._send_telegram(title, formatted_message, notification_type):
                providers_successful.append("telegram")
        
        # Try Email
        if self.is_email_enabled():
            providers_attempted.append("email")
            if self._send_email(title, formatted_message, notification_type):
                providers_successful.append("email")
        
        if providers_attempted:
            success_ratio = f"{len(providers_successful)}/{len(providers_attempted)}"
            if providers_successful:
                print(f"INFO: Notification sent successfully via {success_ratio} providers: {', '.join(providers_successful)}")
            else:
                print(f"WARNING: Notification failed to send via all {len(providers_attempted)} providers: {', '.join(providers_attempted)}")
        else:
            print("INFO: No notification providers configured - notification skipped")
    
    def send_job_delay_notification(self, job_name, delay_minutes, conflicting_jobs, source):
        """Send specific notification for job delays due to conflicts"""
        title = f"🕐 Job Delayed: {job_name}"
        
        conflict_list = ", ".join(conflicting_jobs) if conflicting_jobs else "unknown jobs"
        message = (
            f"Backup job '{job_name}' was delayed {delay_minutes:.1f} minutes due to resource conflicts.\n\n"
            f"Conflicting jobs: {conflict_list}\n"
            f"Triggered by: {source}\n\n"
            f"Consider adjusting schedules to reduce conflicts."
        )
        
        self.send_notification(title, message, "warning")
    
    def send_job_failure_notification(self, job_name, error_message, dry_run=False):
        """Send notification for job failures"""
        mode = "dry run" if dry_run else "backup"
        title = f"❌ Job Failed: {job_name}"
        
        message = (
            f"Backup job '{job_name}' {mode} failed.\n\n"
            f"Error: {error_message}\n\n"
            f"Check logs for detailed information."
        )
        
        self.send_notification(title, message, "error")
    
    def send_job_success_notification(self, job_name, duration_seconds, dry_run=False):
        """Send notification for successful job completion (if enabled per method)"""
        mode = "dry run" if dry_run else "backup"
        title = f"✅ Job Completed: {job_name}"
        
        duration_minutes = duration_seconds / 60
        if duration_minutes < 1:
            duration_str = f"{duration_seconds:.1f} seconds"
        else:
            duration_str = f"{duration_minutes:.1f} minutes"
        
        message = (
            f"Backup job '{job_name}' {mode} completed successfully.\n\n"
            f"Duration: {duration_str}"
        )
        
        # Send to methods that have success notifications enabled
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        providers_attempted = []
        providers_successful = []
        
        # Check Telegram success notifications
        if self.is_telegram_enabled():
            telegram_config = self.notification_config.get("telegram", {})
            if telegram_config.get("notify_on_success", False):
                providers_attempted.append("telegram")
                if self._send_telegram(title, formatted_message, "success"):
                    providers_successful.append("telegram")
        
        # Check Email success notifications
        if self.is_email_enabled():
            email_config = self.notification_config.get("email", {})
            if email_config.get("notify_on_success", False):
                providers_attempted.append("email")
                if self._send_email(title, formatted_message, "success"):
                    providers_successful.append("email")
        
        if providers_attempted:
            success_ratio = f"{len(providers_successful)}/{len(providers_attempted)}"
            if providers_successful:
                print(f"INFO: Success notification sent via {success_ratio} providers: {', '.join(providers_successful)}")
            else:
                print(f"WARNING: Success notification failed via all {len(providers_attempted)} providers: {', '.join(providers_attempted)}")
        else:
            print(f"INFO: Success notifications disabled for job '{job_name}' - skipped")
    
    def is_notifications_enabled(self):
        """Check if any notification provider is enabled"""
        return self.is_telegram_enabled() or self.is_email_enabled()
    
    def is_telegram_enabled(self):
        """Check if Telegram notifications are configured and enabled"""
        telegram_config = self.notification_config.get("telegram", {})
        return bool(
            telegram_config.get("enabled", False) and
            telegram_config.get("token") and 
            telegram_config.get("chat_id")
        )
    
    def is_email_enabled(self):
        """Check if email notifications are configured and enabled"""
        email_config = self.notification_config.get("email", {})
        return bool(
            email_config.get("enabled", False) and
            email_config.get("smtp_server") and
            email_config.get("smtp_port") and
            email_config.get("from_email") and
            email_config.get("to_email")
        )
    
    def _send_telegram(self, title, message, notification_type):
        """Send notification via Telegram Bot API"""
        try:
            telegram_config = self.notification_config["telegram"]
            token = telegram_config["token"]
            chat_id = telegram_config["chat_id"]
            
            # Format message with emoji based on type
            emoji_map = {
                "info": "ℹ️",
                "success": "✅", 
                "warning": "⚠️",
                "error": "❌"
            }
            emoji = emoji_map.get(notification_type, "ℹ️")
            
            formatted_text = f"{emoji} **{title}**\n\n{message}"
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": formatted_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                print(f"WARNING: Telegram API error {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            print(f"WARNING: Failed to send Telegram notification: {str(e)}")
            return False
    
    def _send_email(self, title, message, notification_type):
        """Send notification via email SMTP"""
        try:
            email_config = self.notification_config["email"]
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = email_config["from_email"]
            msg['To'] = email_config["to_email"]
            msg['Subject'] = f"Highball: {title}"
            
            # Add body with plain text and optional HTML
            body = f"Highball Backup Manager\n\n{message}"
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            smtp_server = email_config["smtp_server"]
            smtp_port = int(email_config["smtp_port"])
            
            # Determine if we need TLS/SSL
            use_tls = email_config.get("use_tls", True)
            use_ssl = email_config.get("use_ssl", False)
            
            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port)
                if use_tls:
                    server.starttls()
            
            # Authenticate if credentials provided
            username = email_config.get("username")
            password = email_config.get("password")
            if username and password:
                server.login(username, password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"WARNING: Failed to send email notification: {str(e)}")
            return False
    
    def test_notifications(self):
        """Test all configured notification providers"""
        test_title = "🧪 Highball Test Notification"
        test_message = "This is a test notification to verify your notification settings are working correctly."
        
        print("Testing notification providers...")
        self.send_notification(test_title, test_message, "info")
        
        return self.is_notifications_enabled()


class NotificationManager:
    """Factory for creating notification services"""
    
    @staticmethod
    def create_notifier(backup_config):
        """Create a notification service instance"""
        return NotificationService(backup_config)
    
    @staticmethod
    def get_notification_config_template():
        """Get template configuration for notifications"""
        return {
            "notification": {
                "telegram": {
                    "token": "",  # Bot token from @BotFather
                    "chat_id": "",  # Chat ID where notifications will be sent
                },
                "email": {
                    "smtp_server": "smtp.gmail.com",  # SMTP server hostname
                    "smtp_port": 587,  # SMTP port (587 for TLS, 465 for SSL, 25 for plain)
                    "use_tls": True,  # Use TLS encryption
                    "use_ssl": False,  # Use SSL encryption (alternative to TLS)
                    "from_email": "your-email@gmail.com",  # Sender email address
                    "to_email": "admin@example.com",  # Recipient email address
                    "username": "your-email@gmail.com",  # SMTP authentication username
                    "password": "your-app-password"  # SMTP authentication password
                },
                "notify_on_success": False,  # Set to true to get success notifications
            }
        }