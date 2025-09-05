"""
Destination Management Service
Handles all destination CRUD operations and configuration management
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# =============================================================================
# **DESTINATION OPERATIONS SERVICE** - Full CRUD operations
# =============================================================================

class DestinationOperationsService:
    """Service for destination CRUD operations and lifecycle management"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def get_destinations(self) -> Dict[str, Any]:
        """Get all destination configurations"""
        return self.backup_config.get_destinations()
    
    def get_destination(self, dest_name: str) -> Optional[Dict[str, Any]]:
        """Get specific destination configuration"""
        if not dest_name:
            return None
        return self.backup_config.get_destination(dest_name)
    
    def save_destination(self, dest_name: str, dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """Save destination configuration to persistent storage"""
        if not dest_name:
            return {'success': False, 'error': 'Destination name is required'}
        
        if not dest_config:
            return {'success': False, 'error': 'Destination configuration is required'}
        
        success = self.backup_config.save_destination(dest_name, dest_config)
        
        if success:
            return {'success': True, 'message': f"Destination '{dest_name}' saved successfully"}
        else:
            return {'success': False, 'error': 'Failed to save destination configuration'}
    
    def delete_destination(self, dest_name: str) -> Dict[str, Any]:
        """Delete destination configuration"""
        if not dest_name:
            return {'success': False, 'error': 'Destination name is required'}
        
        success = self.backup_config.delete_destination(dest_name)
        
        if success:
            return {'success': True, 'message': f"Destination '{dest_name}' deleted successfully"}
        else:
            return {'success': False, 'error': 'Failed to delete destination configuration'}
    
    def destination_exists(self, dest_name: str) -> bool:
        """Check if destination exists"""
        existing_destinations = self.get_destinations()
        return dest_name in existing_destinations


# Export service instance for easy import
def create_destination_operations_service(backup_config):
    """Factory function to create DestinationOperationsService instance"""
    return DestinationOperationsService(backup_config)