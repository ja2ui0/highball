"""
Notification queue service for spam prevention
Event-driven queue management with file persistence and in-memory timers
"""
import os
import yaml
import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class QueuedMessage:
    """Individual message in the notification queue"""
    timestamp: float
    title: str
    message: str
    notification_type: str
    job_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization"""
        return {
            'timestamp': self.timestamp,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'job_name': self.job_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueuedMessage':
        """Create from dictionary loaded from YAML"""
        return cls(
            timestamp=data['timestamp'],
            title=data['title'],
            message=data['message'],
            notification_type=data['notification_type'],
            job_name=data.get('job_name')
        )


@dataclass 
class QueueState:
    """State of a notification queue for a specific provider"""
    provider: str
    last_sent_timestamp: float
    queue_interval_minutes: int
    pending_messages: List[QueuedMessage] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization"""
        return {
            'provider': self.provider,
            'last_sent_timestamp': self.last_sent_timestamp,
            'queue_interval_minutes': self.queue_interval_minutes,
            'pending_messages': [msg.to_dict() for msg in self.pending_messages]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueState':
        """Create from dictionary loaded from YAML"""
        messages = [QueuedMessage.from_dict(msg_data) for msg_data in data.get('pending_messages', [])]
        return cls(
            provider=data['provider'],
            last_sent_timestamp=data['last_sent_timestamp'],
            queue_interval_minutes=data['queue_interval_minutes'],
            pending_messages=messages
        )


class NotificationQueueManager:
    """Manages notification queues with event-driven processing"""
    
    def __init__(self, queue_dir: str = "/var/log/highball/notification_queues"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory queue states for active queues
        self._active_queues: Dict[str, QueueState] = {}
        
        # Timer management for batch processing
        self._queue_timers: Dict[str, threading.Timer] = {}
        self._timer_lock = threading.Lock()
        
    def should_send_immediately(self, provider: str, queue_enabled: bool, 
                               queue_interval_minutes: int) -> bool:
        """Check if message should be sent immediately or queued"""
        if not queue_enabled:
            return True
            
        # Load or create queue state
        queue_state = self._get_queue_state(provider, queue_interval_minutes)
        
        # Check if enough time has passed since last send
        current_time = time.time()
        interval_seconds = queue_interval_minutes * 60
        
        time_since_last_send = current_time - queue_state.last_sent_timestamp
        return time_since_last_send >= interval_seconds
    
    def queue_message(self, provider: str, title: str, message: str, 
                     notification_type: str, queue_interval_minutes: int,
                     job_name: Optional[str] = None) -> bool:
        """Queue a message for later batch sending"""
        try:
            # Create queued message
            queued_msg = QueuedMessage(
                timestamp=time.time(),
                title=title,
                message=message,
                notification_type=notification_type,
                job_name=job_name
            )
            
            # Get or create queue state
            queue_state = self._get_queue_state(provider, queue_interval_minutes)
            
            # Add message to queue
            queue_state.pending_messages.append(queued_msg)
            
            # Update in-memory state
            self._active_queues[provider] = queue_state
            
            # Persist to file
            self._save_queue_state(queue_state)
            
            # Set up timer for batch processing if not already set
            self._ensure_batch_timer(provider, queue_interval_minutes)
            
            print(f"INFO: Queued {notification_type} notification for {provider} (queue size: {len(queue_state.pending_messages)})")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to queue message for {provider}: {e}")
            return False
    
    def mark_sent_immediately(self, provider: str, queue_interval_minutes: int):
        """Mark that a message was sent immediately (update timestamp)"""
        try:
            queue_state = self._get_queue_state(provider, queue_interval_minutes)
            queue_state.last_sent_timestamp = time.time()
            
            # Update in-memory state
            self._active_queues[provider] = queue_state
            
            # Persist timestamp update
            self._save_queue_state(queue_state)
            
        except Exception as e:
            print(f"ERROR: Failed to mark sent timestamp for {provider}: {e}")
    
    def process_queue_batch(self, provider: str, send_callback) -> bool:
        """Process queued messages for a provider using callback"""
        try:
            with self._timer_lock:
                # Clear the timer for this provider
                if provider in self._queue_timers:
                    del self._queue_timers[provider]
            
            # Get queue state
            if provider not in self._active_queues:
                queue_state = self._load_queue_state(provider)
                if not queue_state or not queue_state.pending_messages:
                    return True  # Nothing to process
            else:
                queue_state = self._active_queues[provider]
            
            if not queue_state.pending_messages:
                return True  # Nothing to process
            
            # Create batch message
            batch_title, batch_message = self._format_batch_message(
                queue_state.pending_messages
            )
            
            # Send via callback
            success = send_callback(batch_title, batch_message, "batch")
            
            if success:
                # Clear the queue and update timestamp
                queue_state.pending_messages.clear()
                queue_state.last_sent_timestamp = time.time()
                
                # Update states
                self._active_queues[provider] = queue_state
                self._save_queue_state(queue_state)
                
                print(f"INFO: Sent batch notification via {provider}")
            else:
                print(f"WARNING: Failed to send batch notification via {provider}")
                # Keep messages in queue for retry
            
            return success
            
        except Exception as e:
            print(f"ERROR: Failed to process queue batch for {provider}: {e}")
            return False
    
    def _get_queue_state(self, provider: str, queue_interval_minutes: int) -> QueueState:
        """Get queue state, loading from file or creating new"""
        if provider in self._active_queues:
            return self._active_queues[provider]
            
        # Try to load from file
        loaded_state = self._load_queue_state(provider)
        if loaded_state:
            # Update interval if it changed in config
            loaded_state.queue_interval_minutes = queue_interval_minutes
            return loaded_state
            
        # Create new queue state
        return QueueState(
            provider=provider,
            last_sent_timestamp=0.0,  # Allow immediate first send
            queue_interval_minutes=queue_interval_minutes
        )
    
    def _load_queue_state(self, provider: str) -> Optional[QueueState]:
        """Load queue state from file"""
        queue_file = self.queue_dir / f"{provider}_state.yaml"
        
        if not queue_file.exists():
            return None
            
        try:
            with open(queue_file, 'r') as f:
                data = yaml.safe_load(f)
                return QueueState.from_dict(data)
                
        except Exception as e:
            print(f"WARNING: Failed to load queue state for {provider}: {e}")
            return None
    
    def _save_queue_state(self, queue_state: QueueState):
        """Save queue state to file"""
        queue_file = self.queue_dir / f"{queue_state.provider}_state.yaml"
        
        try:
            # If queue is empty and no recent activity, remove file (transient approach)
            current_time = time.time()
            if (not queue_state.pending_messages and 
                current_time - queue_state.last_sent_timestamp > 3600):  # 1 hour cleanup
                
                if queue_file.exists():
                    queue_file.unlink()
                    print(f"INFO: Cleaned up empty queue file for {queue_state.provider}")
                return
            
            # Save state to file
            with open(queue_file, 'w') as f:
                yaml.safe_dump(queue_state.to_dict(), f, default_flow_style=False)
                
        except Exception as e:
            print(f"ERROR: Failed to save queue state for {queue_state.provider}: {e}")
    
    def _ensure_batch_timer(self, provider: str, queue_interval_minutes: int):
        """Ensure there's a timer set up for batch processing"""
        with self._timer_lock:
            if provider in self._queue_timers:
                return  # Timer already exists
            
            # Calculate delay until next batch send
            queue_state = self._active_queues.get(provider)
            if not queue_state:
                return
                
            current_time = time.time()
            interval_seconds = queue_interval_minutes * 60
            time_since_last_send = current_time - queue_state.last_sent_timestamp
            
            delay_seconds = max(0, interval_seconds - time_since_last_send)
            
            # Create timer for batch processing
            timer = threading.Timer(delay_seconds, self._timer_callback, [provider])
            timer.daemon = True
            timer.start()
            
            self._queue_timers[provider] = timer
            
            print(f"INFO: Set batch timer for {provider} (delay: {delay_seconds:.1f}s)")
    
    def _timer_callback(self, provider: str):
        """Timer callback to trigger batch processing"""
        print(f"INFO: Batch timer fired for {provider} - processing queue")
        
        # Create a basic send callback that just logs (will be overridden by notification service)
        def default_send_callback(title, message, notification_type):
            print(f"INFO: Would send batch notification via {provider}: {title}")
            return True  # Assume success for timer callback
        
        # Process the queue
        self.process_queue_batch(provider, default_send_callback)
    
    def _format_batch_message(self, messages: List[QueuedMessage]) -> tuple[str, str]:
        """Format multiple messages into a batch notification"""
        if not messages:
            return "Empty Queue", "No messages to send"
            
        if len(messages) == 1:
            msg = messages[0]
            return msg.title, msg.message
        
        # Multiple messages - create summary
        message_counts = {}
        job_names = set()
        
        for msg in messages:
            msg_type = msg.notification_type
            message_counts[msg_type] = message_counts.get(msg_type, 0) + 1
            if msg.job_name:
                job_names.add(msg.job_name)
        
        # Create batch title
        count_parts = []
        for msg_type, count in message_counts.items():
            if count == 1:
                count_parts.append(f"1 {msg_type}")
            else:
                count_parts.append(f"{count} {msg_type}s")
        
        batch_title = f"Batch Notification: {', '.join(count_parts)}"
        
        # Create batch message
        time_range = self._format_time_range(messages[0].timestamp, messages[-1].timestamp)
        batch_message = f"Multiple notifications from {time_range}:\n\n"
        
        for i, msg in enumerate(messages, 1):
            timestamp_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S")
            batch_message += f"{i}. [{timestamp_str}] {msg.title}\n"
            
            # Truncate very long messages in batch
            msg_preview = msg.message[:100] + "..." if len(msg.message) > 100 else msg.message
            batch_message += f"   {msg_preview}\n\n"
        
        if job_names:
            batch_message += f"Jobs involved: {', '.join(sorted(job_names))}"
        
        return batch_title, batch_message
    
    def _format_time_range(self, start_timestamp: float, end_timestamp: float) -> str:
        """Format time range for batch messages"""
        start_time = datetime.fromtimestamp(start_timestamp)
        end_time = datetime.fromtimestamp(end_timestamp)
        
        if start_time.date() == end_time.date():
            return f"{start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}"
        else:
            return f"{start_time.strftime('%m/%d %H:%M')} to {end_time.strftime('%m/%d %H:%M')}"
    
    def get_queue_status(self, provider: str) -> Dict[str, Any]:
        """Get current queue status for monitoring"""
        queue_state = self._active_queues.get(provider)
        if not queue_state:
            queue_state = self._load_queue_state(provider)
            
        if not queue_state:
            return {'provider': provider, 'status': 'inactive'}
            
        return {
            'provider': provider,
            'status': 'active',
            'pending_count': len(queue_state.pending_messages),
            'last_sent': datetime.fromtimestamp(queue_state.last_sent_timestamp).isoformat(),
            'next_batch_in_seconds': self._get_next_batch_delay(queue_state)
        }
    
    def _get_next_batch_delay(self, queue_state: QueueState) -> Optional[float]:
        """Calculate seconds until next batch send"""
        if not queue_state.pending_messages:
            return None
            
        current_time = time.time()
        interval_seconds = queue_state.queue_interval_minutes * 60
        time_since_last_send = current_time - queue_state.last_sent_timestamp
        
        return max(0, interval_seconds - time_since_last_send)