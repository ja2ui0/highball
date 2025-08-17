"""
Notification queue coordination service
Handles queue management and batch processing integration
"""
from typing import Dict, Any, Optional
from services.notification_provider_factory import NotificationProvider
from services.notification_message_formatter import NotificationMessageFormatter
from services.notification_sender import NotificationSender
from services.notification_queue_service import NotificationQueueManager


class NotificationQueueCoordinator:
    """Service for coordinating notification queue operations"""
    
    def __init__(self, notification_config: Dict[str, Any], providers: Dict[str, NotificationProvider]):
        self.notification_config = notification_config
        self.providers = providers
        self.queue_manager = NotificationQueueManager()
        self.message_formatter = NotificationMessageFormatter()
        self.sender = NotificationSender()
        
        # Set up queue processing callbacks
        self._setup_queue_callbacks()
    
    def send_via_provider_with_queue(self, provider: NotificationProvider, title: str, 
                                   message: str, notification_type: str, job_name: Optional[str] = None):
        """Send notification via provider with queue management"""
        provider_config = self.notification_config.get(provider.provider_name, {})
        queue_enabled = provider_config.get('queue_enabled', True)
        queue_interval_minutes = provider_config.get('queue_interval_minutes', 
                                                    5 if provider.provider_name == 'telegram' else 15)
        
        # Check if we should send immediately or queue
        if self.queue_manager.should_send_immediately(provider.provider_name, queue_enabled, queue_interval_minutes):
            # Send immediately
            formatted_content = self.message_formatter.format_message_for_provider(
                provider.provider_name, title, message, notification_type
            )
            success, error = self.sender.send_via_provider(provider, formatted_content, notification_type)
            
            if success:
                # Mark as sent to update timestamp
                self.queue_manager.mark_sent_immediately(provider.provider_name, queue_interval_minutes)
                print(f"INFO: Sent {notification_type} notification via {provider.provider_name}")
            else:
                print(f"WARNING: Failed to send {notification_type} notification via {provider.provider_name}: {error}")
        else:
            # Queue the message
            success = self.queue_manager.queue_message(
                provider.provider_name, title, message, notification_type, 
                queue_interval_minutes, job_name
            )
            
            if not success:
                print(f"WARNING: Failed to queue notification for {provider.provider_name}")
    
    def get_queue_status(self, provider: str) -> Dict[str, Any]:
        """Get queue status for a specific provider"""
        return self.queue_manager.get_queue_status(provider)
    
    def get_all_queue_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get queue status for all enabled providers"""
        statuses = {}
        for provider_name, provider in self.providers.items():
            if provider.is_valid():
                statuses[provider_name] = self.get_queue_status(provider_name)
        return statuses
    
    def process_queued_notifications(self, provider_name: str) -> int:
        """Manually process queued notifications for a provider"""
        provider_obj = self.providers.get(provider_name)
        if not provider_obj or not provider_obj.is_valid():
            return 0
        
        def send_callback(title, message, notification_type):
            formatted_content = self.message_formatter.format_message_for_provider(
                provider_name, title, message, notification_type
            )
            success, error = self.sender.send_via_provider(provider_obj, formatted_content, notification_type)
            if error:
                print(f"WARNING: Manual batch send error for {provider_name}: {error}")
            return success
        
        return self.queue_manager.process_queue_batch(provider_name, send_callback)
    
    def clear_queue(self, provider_name: str) -> bool:
        """Clear all queued messages for a provider"""
        try:
            queue_status = self.get_queue_status(provider_name)
            if queue_status.get('has_pending_messages', False):
                # This would need to be implemented in NotificationQueueManager
                # For now, we'll just log the action
                print(f"INFO: Queue clear requested for {provider_name}")
                return True
            return True
        except Exception as e:
            print(f"WARNING: Failed to clear queue for {provider_name}: {e}")
            return False
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get overall queue statistics across all providers"""
        stats = {
            'total_providers': len(self.providers),
            'enabled_providers': 0,
            'providers_with_queues': 0,
            'total_pending_messages': 0,
            'provider_details': {}
        }
        
        for provider_name, provider in self.providers.items():
            if provider.is_valid():
                stats['enabled_providers'] += 1
                
                queue_status = self.get_queue_status(provider_name)
                has_pending = queue_status.get('has_pending_messages', False)
                pending_count = queue_status.get('pending_message_count', 0)
                
                if has_pending:
                    stats['providers_with_queues'] += 1
                    stats['total_pending_messages'] += pending_count
                
                stats['provider_details'][provider_name] = {
                    'enabled': True,
                    'has_pending_messages': has_pending,
                    'pending_count': pending_count,
                    'last_sent': queue_status.get('last_sent_timestamp'),
                    'next_batch': queue_status.get('next_batch_time')
                }
            else:
                stats['provider_details'][provider_name] = {
                    'enabled': False,
                    'has_pending_messages': False,
                    'pending_count': 0
                }
        
        return stats
    
    def _setup_queue_callbacks(self):
        """Set up callbacks for queue processing"""
        # Override the timer callback in queue manager to use our notification sending
        original_timer_callback = self.queue_manager._timer_callback
        
        def enhanced_timer_callback(provider: str):
            print(f"INFO: Batch timer fired for {provider} - processing queue")
            
            # Create send callback that uses our notification system
            def send_callback(title, message, notification_type):
                provider_obj = self.providers.get(provider)
                if provider_obj and provider_obj.is_valid():
                    formatted_content = self.message_formatter.format_message_for_provider(
                        provider, title, message, notification_type
                    )
                    success, error = self.sender.send_via_provider(provider_obj, formatted_content, notification_type)
                    if error:
                        print(f"WARNING: Batch send error for {provider}: {error}")
                    return success
                return False
            
            # Process the queue with our callback
            return self.queue_manager.process_queue_batch(provider, send_callback)
        
        # Replace the timer callback
        self.queue_manager._timer_callback = enhanced_timer_callback