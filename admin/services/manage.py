"""
Admin Management Service
Handles admin configuration operations and settings management
"""

from typing import Dict, Any


class AdminOperationsService:
    """Service for admin configuration operations"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    # =========================================================================
    # CONFIG ACCESS METHODS - handlers should use these instead of direct access
    # =========================================================================
    
    def get_global_settings(self) -> Dict[str, Any]:
        """Get global settings - handlers should call this instead of backup_config.get_global_settings()"""
        return self.backup_config.get_global_settings()
    
    def get_config_file_path(self) -> str:
        """Get config file path - handlers should call this instead of backup_config.config_file"""
        return self.backup_config.config_file
    
    def update_global_settings(self, settings: Dict[str, Any]) -> None:
        """Update global settings - handlers should call this instead of backup_config.update_global_settings()"""
        return self.backup_config.update_global_settings(settings)
    
    def reload_config(self) -> None:
        """Reload config - handlers should call this instead of backup_config.reload_config()"""
        return self.backup_config.reload_config()
    
    def get_or_create_global_settings(self) -> Dict[str, Any]:
        """Get or create global settings dict - handlers should call this instead of backup_config.config.setdefault()"""
        return self.backup_config.config.setdefault('global_settings', {})