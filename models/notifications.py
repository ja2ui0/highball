"""
Consolidated Notifications Module
Merges all notification logic into single module with clean class-based organization
Replaces: notification_service.py, notification_provider_factory.py, notification_message_formatter.py,
         notification_sender.py, notification_job_config_manager.py, notification_queue_coordinator.py,
         notification_queue_service.py
"""

import os
import logging
import json
import yaml
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import threading
import time
from pydantic import BaseModel, Field

# Import notifiers for actual sending
try:
    from notifiers import get_notifier
    NOTIFIERS_AVAILABLE = True
except ImportError:
    NOTIFIERS_AVAILABLE = False
    logger.warning("notifiers library not available - notifications disabled")

logger = logging.getLogger(__name__)

# =============================================================================
# NOTIFICATION DATA CLASSES
# =============================================================================

class NotificationMessage(BaseModel):
    """Represents a notification message"""
    provider: str
    recipient: str
    title: str
    message: str
    job_name: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'provider': self.provider,
            'recipient': self.recipient,
            'title': self.title,
            'message': self.message,
            'job_name': self.job_name,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NotificationMessage':
        """Create from dictionary"""
        return cls(
            provider=data['provider'],
            recipient=data['recipient'],
            title=data['title'],
            message=data['message'],
            job_name=data.get('job_name', ''),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat()))
        )

class NotificationConfig(BaseModel):
    """Notification configuration for a job"""
    provider: str
    notify_on_success: bool = False
    notify_on_failure: bool = True
    notify_on_maintenance_failure: bool = False
    success_message: str = ""
    failure_message: str = ""

# =============================================================================
# NOTIFICATION PROVIDER FIELD SCHEMAS
# =============================================================================

PROVIDER_FIELD_SCHEMAS = {
    'telegram': {
        'display_name': 'Telegram',
        'required_fields': ['token', 'chat_id'],
        'fields': [
            {
                'name': 'enabled',
                'type': 'checkbox',
                'label': 'Enable Telegram notifications',
                'help': 'Globally enable or disable Telegram notifications'
            },
            {
                'name': 'token',
                'type': 'text',
                'label': 'Bot Token',
                'help': 'Get from @BotFather on Telegram',
                'placeholder': '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz',
                'required': True
            },
            {
                'name': 'chat_id', 
                'type': 'text',
                'label': 'Chat ID',
                'help': 'Chat or group ID where notifications will be sent',
                'placeholder': '-1001234567890',
                'required': True
            }
        ],
        'sections': [
            {
                'name': 'queue_settings',
                'title': 'Queue Settings',
                'fields': [
                    {
                        'name': 'queue_enabled',
                        'type': 'checkbox',
                        'label': 'Enable notification queueing',
                        'help': 'Spam prevention - batches messages to avoid frequent notifications'
                    },
                    {
                        'name': 'queue_interval_minutes',
                        'type': 'number',
                        'label': 'Minimum time between messages (minutes)',
                        'help': 'Messages will be batched and sent no more frequently than this interval',
                        'placeholder': '5',
                        'min': 1,
                        'max': 1440
                    }
                ]
            }
        ]
    },
    'email': {
        'display_name': 'Email',
        'required_fields': ['smtp_server', 'smtp_port', 'from_email', 'to_email'],
        'fields': [
            {
                'name': 'enabled',
                'type': 'checkbox',
                'label': 'Enable email notifications',
                'help': 'Globally enable or disable email notifications'
            }
        ],
        'sections': [
            {
                'name': 'smtp_config',
                'title': 'SMTP Configuration', 
                'fields': [
                    {
                        'name': 'smtp_server',
                        'type': 'text',
                        'label': 'SMTP Server',
                        'placeholder': 'smtp.gmail.com',
                        'required': True
                    },
                    {
                        'name': 'smtp_port',
                        'type': 'number',
                        'label': 'SMTP Port',
                        'help': '587 for TLS, 465 for SSL, 25 for plain',
                        'placeholder': '587',
                        'required': True
                    },
                    {
                        'name': 'encryption',
                        'type': 'select',
                        'label': 'Encryption',
                        'help': 'Encryption method for SMTP connection',
                        'default': 'tls',
                        'options': [
                            {'value': 'tls', 'label': 'TLS', 'config_field': 'use_tls'},
                            {'value': 'ssl', 'label': 'SSL', 'config_field': 'use_ssl'}, 
                            {'value': 'none', 'label': 'None'}
                        ]
                    },
                    {
                        'name': 'from_email',
                        'type': 'email',
                        'label': 'From Email',
                        'placeholder': 'backup@yourcompany.com',
                        'required': True
                    },
                    {
                        'name': 'to_email',
                        'type': 'email', 
                        'label': 'To Email',
                        'placeholder': 'admin@yourcompany.com',
                        'required': True
                    },
                    {
                        'name': 'username',
                        'type': 'text',
                        'label': 'SMTP Username',
                        'help': 'Usually your email address',
                        'placeholder': 'your.email@gmail.com'
                    },
                    {
                        'name': 'password',
                        'type': 'password',
                        'label': 'SMTP Password', 
                        'help': 'Use app password for Gmail',
                        'placeholder': 'your-app-password'
                    }
                ]
            },
            {
                'name': 'queue_settings',
                'title': 'Queue Settings',
                'fields': [
                    {
                        'name': 'queue_enabled',
                        'type': 'checkbox',
                        'label': 'Enable notification queueing',
                        'help': 'Spam prevention - batches messages to avoid frequent notifications'
                    },
                    {
                        'name': 'queue_interval_minutes',
                        'type': 'number',
                        'label': 'Minimum time between messages (minutes)',
                        'help': 'Messages will be batched and sent no more frequently than this interval',
                        'placeholder': '15',
                        'min': 1,
                        'max': 1440
                    }
                ]
            }
        ]
    }
}

# =============================================================================
# NOTIFICATION PROVIDER FACTORY
# =============================================================================

class NotificationProviderFactory:
    """Creates and configures notification providers"""
    
    def __init__(self, global_config: Dict[str, Any]):
        self.global_config = global_config
        self._providers = {}
    
    def get_provider(self, provider_name: str) -> Any:
        """Get configured provider instance"""
        if not NOTIFIERS_AVAILABLE:
            raise Exception("notifiers library not available")
        
        if provider_name in self._providers:
            return self._providers[provider_name]
        
        provider_config = self.global_config.get('notification', {}).get(provider_name, {})
        
        if not provider_config.get('enabled', False):
            raise Exception(f"Provider {provider_name} is not enabled")
        
        provider = get_notifier(provider_name)
        
        # Schema-driven provider validation
        if provider_name in PROVIDER_FIELD_SCHEMAS:
            schema = PROVIDER_FIELD_SCHEMAS[provider_name]
            required_fields = schema.get('required_fields', [])
            
            for field in required_fields:
                if not provider_config.get(field):
                    raise Exception(f"{schema['display_name']} provider missing required field: {field}")
        else:
            raise Exception(f"Unknown notification provider: {provider_name}")
        
        self._providers[provider_name] = provider
        return provider
    
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get provider configuration"""
        return self.global_config.get('notification', {}).get(provider_name, {})
    
    def list_enabled_providers(self) -> List[str]:
        """List all enabled providers"""
        notification_config = self.global_config.get('notification', {})
        enabled = []
        
        for provider_name, config in notification_config.items():
            if isinstance(config, dict) and config.get('enabled', False):
                enabled.append(provider_name)
        
        return enabled

# =============================================================================
# MESSAGE FORMATTER
# =============================================================================

class NotificationMessageFormatter:
    """Formats notification messages with template variables"""
    
    @staticmethod
    def format_success_message(job_name: str, duration: str, custom_message: str = "") -> Tuple[str, str]:
        """Format success notification message"""
        if custom_message:
            title = f"Backup Success: {job_name}"
            message = custom_message.format(job_name=job_name, duration=duration)
        else:
            title = f"Backup Success: {job_name}"
            message = f"Job '{job_name}' completed successfully in {duration}"
        
        return title, message
    
    @staticmethod
    def format_failure_message(job_name: str, error_message: str, custom_message: str = "") -> Tuple[str, str]:
        """Format failure notification message"""
        if custom_message:
            title = f"Backup Failed: {job_name}"
            message = custom_message.format(job_name=job_name, error_message=error_message)
        else:
            title = f"Backup Failed: {job_name}"
            message = f"Job '{job_name}' failed: {error_message}"
        
        return title, message
    
    @staticmethod
    def format_maintenance_failure_message(job_name: str, operation: str, error_message: str) -> Tuple[str, str]:
        """Format maintenance failure notification message"""
        title = f"Maintenance Failed: {job_name}"
        message = f"Maintenance operation '{operation}' failed for job '{job_name}': {error_message}"
        
        return title, message
    
    @staticmethod
    def format_delay_message(job_name: str, delay_seconds: int) -> Tuple[str, str]:
        """Format delay notification message"""
        delay_minutes = delay_seconds // 60
        title = f"Job Delayed: {job_name}"
        message = f"Job '{job_name}' has been delayed for {delay_minutes} minutes due to conflicts"
        
        return title, message

# =============================================================================
# NOTIFICATION SENDER
# =============================================================================

class NotificationSender:
    """Sends notifications via configured providers"""
    
    def __init__(self, provider_factory: NotificationProviderFactory):
        self.provider_factory = provider_factory
    
    def send_notification(self, notification: NotificationMessage) -> Dict[str, Any]:
        """Send a single notification"""
        try:
            provider = self.provider_factory.get_provider(notification.provider)
            provider_config = self.provider_factory.get_provider_config(notification.provider)
            
            # Build provider-specific arguments
            if notification.provider == 'telegram':
                result = provider.notify(
                    token=provider_config['token'],
                    chat_id=provider_config['chat_id'],
                    message=f"{notification.title}\n\n{notification.message}"
                )
            
            elif notification.provider == 'email':
                result = provider.notify(
                    to=provider_config['to_email'],
                    from_=provider_config['from_email'],
                    subject=notification.title,
                    message=notification.message,
                    host=provider_config['smtp_server'],
                    port=provider_config.get('smtp_port', 587),
                    username=provider_config.get('username'),
                    password=provider_config.get('password'),
                    tls=provider_config.get('use_tls', True),
                    ssl=provider_config.get('use_ssl', False)
                )
            
            else:
                return {
                    'success': False,
                    'error': f'Unknown provider: {notification.provider}'
                }
            
            if result.status == 'Success':
                return {
                    'success': True,
                    'provider': notification.provider,
                    'message': 'Notification sent successfully'
                }
            else:
                return {
                    'success': False,
                    'provider': notification.provider,
                    'error': f'Provider error: {result.errors}'
                }
                
        except Exception as e:
            logger.error(f"Notification send error for {notification.provider}: {e}")
            return {
                'success': False,
                'provider': notification.provider,
                'error': str(e)
            }
    
    def test_provider(self, provider_name: str, test_message: str = "Test notification from Highball") -> Dict[str, Any]:
        """Test a notification provider"""
        try:
            provider_config = self.provider_factory.get_provider_config(provider_name)
            
            test_notification = NotificationMessage(
                provider=provider_name,
                recipient=provider_config.get('chat_id') or provider_config.get('to_email', 'test'),
                title="Highball Test Notification",
                message=test_message,
                job_name="test"
            )
            
            return self.send_notification(test_notification)
            
        except Exception as e:
            return {
                'success': False,
                'provider': provider_name,
                'error': f'Test failed: {str(e)}'
            }

# =============================================================================
# NOTIFICATION QUEUE SYSTEM
# =============================================================================

class NotificationQueue:
    """Manages notification queuing and batching"""
    
    def __init__(self, queue_dir: str = "/var/log/highball/notification_queues"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self._locks = {}
    
    def enqueue_notification(self, provider: str, notification: NotificationMessage, interval_seconds: int = 300) -> None:
        """Add notification to provider queue"""
        queue_file = self.queue_dir / f"{provider}_state.yaml"
        
        # Thread-safe queue operations
        lock = self._get_lock(provider)
        with lock:
            queue_state = self._load_queue_state(queue_file)
            
            # Check if we should send immediately or queue
            now = datetime.now()
            last_sent = queue_state.get('last_sent')
            
            if last_sent:
                last_sent_dt = datetime.fromisoformat(last_sent)
                time_since_last = (now - last_sent_dt).total_seconds()
                
                if time_since_last < interval_seconds:
                    # Queue the notification
                    queue_state.setdefault('pending_messages', []).append(notification.to_dict())
                    self._save_queue_state(queue_file, queue_state)
                    return {'queued': True, 'next_send_time': last_sent_dt + timedelta(seconds=interval_seconds)}
            
            # Send immediately and clear queue
            all_messages = queue_state.get('pending_messages', []) + [notification.to_dict()]
            queue_state['pending_messages'] = []
            queue_state['last_sent'] = now.isoformat()
            self._save_queue_state(queue_file, queue_state)
            
            return {'queued': False, 'messages_to_send': all_messages}
    
    def get_pending_count(self, provider: str) -> int:
        """Get count of pending messages for provider"""
        queue_file = self.queue_dir / f"{provider}_state.yaml"
        queue_state = self._load_queue_state(queue_file)
        return len(queue_state.get('pending_messages', []))
    
    def _get_lock(self, provider: str) -> threading.Lock:
        """Get thread lock for provider"""
        if provider not in self._locks:
            self._locks[provider] = threading.Lock()
        return self._locks[provider]
    
    def _load_queue_state(self, queue_file: Path) -> Dict[str, Any]:
        """Load queue state from file"""
        try:
            if queue_file.exists():
                with open(queue_file, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading queue state: {e}")
        
        return {}
    
    def _save_queue_state(self, queue_file: Path, state: Dict[str, Any]):
        """Save queue state to file"""
        try:
            with open(queue_file, 'w') as f:
                yaml.safe_dump(state, f)
        except Exception as e:
            logger.error(f"Error saving queue state: {e}")

# =============================================================================
# JOB CONFIG MANAGER
# =============================================================================

class NotificationJobConfigManager:
    """Manages notification configuration for jobs"""
    
    @staticmethod
    def extract_job_notifications(job_config: Dict[str, Any]) -> List[NotificationConfig]:
        """Extract notification configurations from job config"""
        notifications = job_config.get('notifications', [])
        configs = []
        
        for notification in notifications:
            config = NotificationConfig(
                provider=notification.get('provider', ''),
                notify_on_success=notification.get('notify_on_success', False),
                notify_on_failure=notification.get('notify_on_failure', True),
                notify_on_maintenance_failure=notification.get('notify_on_maintenance_failure', False),
                success_message=notification.get('success_message', ''),
                failure_message=notification.get('failure_message', '')
            )
            configs.append(config)
        
        return configs
    
    @staticmethod
    def should_notify_success(job_config: Dict[str, Any], global_config: Dict[str, Any]) -> bool:
        """Check if success notifications should be sent for this job"""
        job_notifications = NotificationJobConfigManager.extract_job_notifications(job_config)
        
        for notification in job_notifications:
            if notification.notify_on_success:
                # Check if provider is globally enabled for success
                provider_config = global_config.get('notification', {}).get(notification.provider, {})
                if provider_config.get('notify_on_success', False):
                    return True
        
        return False
    
    @staticmethod
    def should_notify_failure(job_config: Dict[str, Any]) -> bool:
        """Check if failure notifications should be sent for this job"""
        job_notifications = NotificationJobConfigManager.extract_job_notifications(job_config)
        
        for notification in job_notifications:
            if notification.notify_on_failure:
                return True
        
        return False

# =============================================================================
# UNIFIED NOTIFICATION SERVICE
# =============================================================================

class NotificationService:
    """Unified notification service - single entry point for all notification operations"""
    
    def __init__(self, global_config: Dict[str, Any]):
        self.global_config = global_config
        self.provider_factory = NotificationProviderFactory(global_config)
        self.sender = NotificationSender(self.provider_factory)
        self.formatter = NotificationMessageFormatter()
        self.queue = NotificationQueue()
        self.job_config_manager = NotificationJobConfigManager()
    
    def notify_job_success(self, job_name: str, duration: str, job_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Send success notifications for a job"""
        if not self.job_config_manager.should_notify_success(job_config, self.global_config):
            return []
        
        results = []
        job_notifications = self.job_config_manager.extract_job_notifications(job_config)
        
        for notification_config in job_notifications:
            if notification_config.notify_on_success:
                try:
                    title, message = self.formatter.format_success_message(
                        job_name, duration, notification_config.success_message
                    )
                    
                    notification = NotificationMessage(
                        provider=notification_config.provider,
                        recipient="job_notification",
                        title=title,
                        message=message,
                        job_name=job_name
                    )
                    
                    # Use queuing to prevent spam
                    queue_result = self.queue.enqueue_notification(
                        notification_config.provider, 
                        notification,
                        interval_seconds=self.global_config.get('delay_notification_threshold', 300)
                    )
                    
                    if queue_result.get('queued'):
                        results.append({
                            'success': True,
                            'provider': notification_config.provider,
                            'message': 'Notification queued to prevent spam',
                            'next_send_time': queue_result.get('next_send_time')
                        })
                    else:
                        # Send all queued messages
                        for msg_data in queue_result.get('messages_to_send', []):
                            msg = NotificationMessage.from_dict(msg_data)
                            send_result = self.sender.send_notification(msg)
                            results.append(send_result)
                
                except Exception as e:
                    logger.error(f"Success notification error: {e}")
                    results.append({
                        'success': False,
                        'provider': notification_config.provider,
                        'error': str(e)
                    })
        
        return results
    
    def notify_job_failure(self, job_name: str, error_message: str, job_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Send failure notifications for a job"""
        if not self.job_config_manager.should_notify_failure(job_config):
            return []
        
        results = []
        job_notifications = self.job_config_manager.extract_job_notifications(job_config)
        
        for notification_config in job_notifications:
            if notification_config.notify_on_failure:
                try:
                    title, message = self.formatter.format_failure_message(
                        job_name, error_message, notification_config.failure_message
                    )
                    
                    notification = NotificationMessage(
                        provider=notification_config.provider,
                        recipient="job_notification",
                        title=title,
                        message=message,
                        job_name=job_name
                    )
                    
                    # Send failure notifications immediately (no queuing)
                    send_result = self.sender.send_notification(notification)
                    results.append(send_result)
                
                except Exception as e:
                    logger.error(f"Failure notification error: {e}")
                    results.append({
                        'success': False,
                        'provider': notification_config.provider,
                        'error': str(e)
                    })
        
        return results
    
    def notify_maintenance_failure(self, job_name: str, operation: str, error_message: str, 
                                 job_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Send maintenance failure notifications"""
        results = []
        job_notifications = self.job_config_manager.extract_job_notifications(job_config)
        
        for notification_config in job_notifications:
            if notification_config.notify_on_maintenance_failure:
                try:
                    title, message = self.formatter.format_maintenance_failure_message(
                        job_name, operation, error_message
                    )
                    
                    notification = NotificationMessage(
                        provider=notification_config.provider,
                        recipient="maintenance_notification",
                        title=title,
                        message=message,
                        job_name=job_name
                    )
                    
                    send_result = self.sender.send_notification(notification)
                    results.append(send_result)
                
                except Exception as e:
                    logger.error(f"Maintenance notification error: {e}")
                    results.append({
                        'success': False,
                        'provider': notification_config.provider,
                        'error': str(e)
                    })
        
        return results
    
    def test_provider(self, provider_name: str) -> Dict[str, Any]:
        """Test a notification provider"""
        return self.sender.test_provider(provider_name)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get notification queue status"""
        enabled_providers = self.provider_factory.list_enabled_providers()
        status = {}
        
        for provider in enabled_providers:
            pending_count = self.queue.get_pending_count(provider)
            status[provider] = {
                'pending_messages': pending_count,
                'enabled': True
            }
        
        return status

# =============================================================================
# NOTIFICATION SERVICE FACTORY
# =============================================================================

def create_notification_service(global_config: Dict[str, Any]) -> NotificationService:
    """Factory function to create notification service"""
    return NotificationService(global_config)