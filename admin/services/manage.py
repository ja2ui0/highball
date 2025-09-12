"""
Admin Management Service
Handles non-config admin operations (notification testing only)
"""

from typing import Dict, Any
from shared.handlers.errors import handle_service_errors
from admin.services.config import AdminConfigService


class AdminOperationsService:
    """Service for non-config admin operations - notification testing only"""
    
    def __init__(self):
        # No more config access - only non-config operations
        self.admin_config = AdminConfigService()

    @handle_service_errors("Test telegram notification")
    def test_telegram_notification(self, test_message: str) -> Dict[str, Any]:
        """Test telegram notification via service"""
        # Get current config from admin config service
        global_settings = self.admin_config.get_global_settings()
        
        from admin.services.notifications import NotificationTestService
        # Create temporary backup_config-like object for notification service compatibility
        class ConfigAdapter:
            def get_global_settings(self):
                return global_settings
        
        test_service = NotificationTestService(ConfigAdapter())
        return test_service.test_telegram_notification(test_message)

    @handle_service_errors("Test email notification")
    def test_email_notification(self, test_message: str) -> Dict[str, Any]:
        """Test email notification via service"""
        # Get current config from admin config service
        global_settings = self.admin_config.get_global_settings()
        
        from admin.services.notifications import NotificationTestService
        # Create temporary backup_config-like object for notification service compatibility
        class ConfigAdapter:
            def get_global_settings(self):
                return global_settings
        
        test_service = NotificationTestService(ConfigAdapter())
        return test_service.test_email_notification(test_message)


# Export service instance for easy import
def create_admin_operations_service():
    """Factory function to create AdminOperationsService instance - no config dependency"""
    return AdminOperationsService()