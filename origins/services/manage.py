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