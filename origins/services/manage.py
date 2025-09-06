"""
Origin Management Service
Handles all origin CRUD operations and configuration management
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# =============================================================================
# **ORIGIN OPERATIONS SERVICE** - Full CRUD operations
# =============================================================================

class OriginOperationsService:
    """Service for origin CRUD operations and lifecycle management"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def get_origins(self) -> Dict[str, Any]:
        """Get all origin configurations"""
        return self.backup_config.get_ssh_origins()
    
    def get_origin(self, origin_name: str) -> Optional[Dict[str, Any]]:
        """Get specific origin configuration"""
        if not origin_name:
            return None
        return self.backup_config.get_ssh_origin(origin_name)
    
    def save_origin(self, origin_name: str, origin_config: Dict[str, Any]) -> bool:
        """Save origin configuration"""
        if not origin_name or not origin_config:
            return False
        return self.backup_config.save_origin(origin_name, origin_config)
    
    def delete_origin(self, origin_name: str) -> bool:
        """Delete origin configuration"""
        if not origin_name:
            return False
        return self.backup_config.delete_origin(origin_name)
    
    def preview_origin_yaml(self, origin_name: str, origin_config: Dict[str, Any]) -> str:
        """Preview origin YAML configuration"""
        return self.backup_config.preview_origin_yaml(origin_name, origin_config)
    
    def origin_exists(self, origin_name: str) -> bool:
        """Check if origin already exists"""
        existing_origins = self.get_origins()
        return origin_name in existing_origins
    
    def save_origin_with_rename_handling(self, origin_name: str, origin_config: Dict[str, Any], original_origin_name: str = '') -> Dict[str, Any]:
        """Save origin with rename logic - handles old file deletion if name changed"""
        
        # Handle renaming if the origin name changed
        if original_origin_name and original_origin_name != origin_name:
            # Delete the old file
            self.delete_origin(original_origin_name)
        
        # Save origin with detected capabilities (overwrites existing or creates new)
        success = self.save_origin(origin_name, origin_config)
        
        if success:
            return {
                'success': True,
                'origin_name': origin_name
            }
        else:
            return {
                'success': False,
                'error': f"Failed to save origin '{origin_name}'"
            }
    
    def add_new_origin(self, origin_name: str, origin_config: Dict[str, Any]) -> Dict[str, Any]:
        """Add new origin with duplicate name validation"""
        
        # Check if origin already exists
        if self.origin_exists(origin_name):
            return {
                'success': False,
                'error': f'Origin "{origin_name}" already exists'
            }
        
        # Save origin with capabilities from form parser (including any detected values)
        success = self.save_origin(origin_name, origin_config)
        
        if success:
            return {
                'success': True,
                'origin_name': origin_name
            }
        else:
            return {
                'success': False,
                'error': f"Failed to save origin '{origin_name}'"
            }