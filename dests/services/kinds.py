"""
Destination Types Service Module
Contains destination type availability and option management services
Extracted from services/data_services.py
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# =============================================================================
# DESTINATION TYPE SERVICE - General destination type availability
# =============================================================================

class DestinationTypeService:
    """Service for managing destination type availability and options"""
    
    def get_available_destination_types(self, source_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get list of available destination types with their metadata"""
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        
        available_types = []
        
        for dest_type, schema in DESTINATION_TYPE_SCHEMAS.items():
            if self._is_destination_available(dest_type, schema, source_config):
                available_types.append({
                    'value': dest_type,
                    'display_name': schema['display_name'],
                    'description': schema['description']
                })
        
        return available_types
    
    def _is_destination_available(self, dest_type: str, schema: Dict[str, Any], source_config: Optional[Dict[str, Any]] = None) -> bool:
        """Check if a destination type is available"""
        
        # Always available types
        if schema.get('always_available', False):
            return True
        
        # Check specific availability function if defined
        if 'availability_check' in schema:
            check_method = getattr(self, schema['availability_check'], None)
            if check_method:
                return check_method(source_config)
        
        # Default: assume available if no specific check
        return True
    
    def check_restic_availability(self, source_config: Optional[Dict[str, Any]] = None) -> bool:
        """Check if Restic is available as a destination type"""
        try:
            # For SSH sources, check container runtime availability on source
            if source_config and source_config.get('hostname'):
                container_runtime = source_config.get('container_runtime')
                return container_runtime in ['docker', 'podman']
            
            # For local sources, always available (Highball container has restic)
            return True
            
        except Exception as e:
            logger.warning(f"Error checking restic availability: {e}")
            return False


# Export the service
destination_type_service = DestinationTypeService()