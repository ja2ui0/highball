"""
Notification sender service
Handles actual sending of notifications via different providers using notifiers library
"""
from dataclasses import dataclass
from typing import Optional, List
from notifiers import get_notifier
from services.notification_provider_factory import NotificationProvider


@dataclass
class NotificationResult:
    """Result of notification attempt"""
    provider: str
    success: bool
    error_message: Optional[str] = None


class NotificationSender:
    """Service for sending notifications via configured providers"""
    
    def __init__(self):
        pass
    
    def send_via_provider(self, provider: NotificationProvider, formatted_content: dict, 
                         notification_type: str) -> tuple[bool, Optional[str]]:
        """Send notification via specific provider using notifiers library"""
        try:
            notifier = get_notifier(provider.provider_name)
            
            # Prepare notification content and send
            result = None
            if provider.provider_name == "telegram":
                # Use the formatted content directly
                telegram_config = provider.config.copy()
                telegram_config.update(formatted_content)
                result = notifier.notify(**telegram_config)
            
            elif provider.provider_name == "email":
                # Email needs subject and body
                email_config = provider.config.copy()
                email_config.update(formatted_content)
                result = notifier.notify(**email_config)
            
            else:
                # Generic provider (for future extensions)
                generic_config = provider.config.copy()
                generic_config.update(formatted_content)
                result = notifier.notify(**generic_config)
            
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
    
    def send_to_multiple_providers(self, providers: List[NotificationProvider], 
                                 formatted_content_map: dict, notification_type: str) -> List[NotificationResult]:
        """Send to multiple providers and return results"""
        results = []
        
        for provider in providers:
            if provider.is_valid():
                formatted_content = formatted_content_map.get(provider.provider_name, {})
                success, error = self.send_via_provider(provider, formatted_content, notification_type)
                results.append(NotificationResult(provider.provider_name, success, error))
        
        return results
    
    def log_notification_results(self, results: List[NotificationResult], context: str = ""):
        """Log results of notification attempts"""
        if not results:
            print(f"INFO: No notification providers configured - notification skipped{' for ' + context if context else ''}")
            return
        
        successful = [r for r in results if r.success]
        context_suffix = f" for {context}" if context else ""
        
        if successful:
            providers = ", ".join(r.provider for r in successful)
            print(f"INFO: Notification sent successfully via {len(successful)}/{len(results)} providers: {providers}{context_suffix}")
        else:
            providers = ", ".join(r.provider for r in results)
            print(f"WARNING: Notification failed via all {len(results)} providers: {providers}{context_suffix}")
            for result in results:
                if result.error_message:
                    print(f"  - {result.provider}: {result.error_message}")
    
    def log_success_notification_results(self, results: List[NotificationResult], job_name: str):
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