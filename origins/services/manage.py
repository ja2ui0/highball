"""
Origin Management Service
Handles all origin CRUD operations and configuration management
"""

import logging
import re
from typing import Dict, Any, Optional, List

from models.forms import safe_get_value

logger = logging.getLogger(__name__)

# =============================================================================
# **ORIGIN OPERATIONS SERVICE** - Full CRUD operations
# =============================================================================

class OriginOperationsService:
    """Service for origin CRUD operations and lifecycle management"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    # =========================================================================
    # CONFIG ACCESS METHODS - handlers should use these instead of direct access
    # =========================================================================
    
    def get_global_settings(self) -> Dict[str, Any]:
        """Get global settings - handlers should call this instead of backup_config.get_global_settings()"""
        return self.backup_config.get_global_settings()
    
    def parse_origin_form(self, form_data: Dict[str, Any], require_password: bool = True) -> Dict[str, Any]:
        """Parse and validate SSH origin form data"""
        origin_name = safe_get_value(form_data, 'origin_name').strip()
        if not origin_name:
            return {'valid': False, 'error': 'Origin name is required'}
        
        # Validate origin name is a valid slug (matches filename requirements)
        if not re.match(r'^[a-zA-Z0-9_-]+$', origin_name):
            return {'valid': False, 'error': 'Origin name must contain only letters, numbers, underscores, and hyphens'}
        
        friendly_name = safe_get_value(form_data, 'friendly_name').strip()
        if not friendly_name:
            return {'valid': False, 'error': 'Friendly name is required'}
        
        ssh_hostname = safe_get_value(form_data, 'ssh_hostname').strip()
        if not ssh_hostname:
            return {'valid': False, 'error': 'SSH hostname is required'}
        
        ssh_username = safe_get_value(form_data, 'ssh_username').strip()
        if not ssh_username:
            return {'valid': False, 'error': 'SSH username is required'}
        
        # Parse authentication method
        ssh_highball = safe_get_value(form_data, 'ssh_highball') == 'on'
        
        # Parse optional fields with defaults
        ssh_port = safe_get_value(form_data, 'ssh_port', '22')
        ssh_timeout = safe_get_value(form_data, 'ssh_timeout', '5')
        
        try:
            ssh_port = int(ssh_port)
            ssh_timeout = int(ssh_timeout)
        except ValueError:
            return {'valid': False, 'error': 'SSH port and timeout must be numbers'}
        
        # Note: Auth validation removed - no BYOK fields to validate anymore
        
        # Build origin configuration
        # Parse detected capabilities from validation (if present)
        detected_rsync = safe_get_value(form_data, 'detected_rsync_available', 'false')
        detected_runtime = safe_get_value(form_data, 'detected_container_runtime', '')
        
        
        origin_config = {
            'origin_name': origin_name,
            'friendly_name': friendly_name,
            'ssh_hostname': ssh_hostname,
            'ssh_port': ssh_port,
            'ssh_timeout': ssh_timeout,
            'ssh_username': ssh_username,
            'ssh_highball': True,  # Always true - Highball-only system
            'rsync_available': detected_rsync.lower() == 'true',
            'container_runtime': detected_runtime if detected_runtime else None
        }
        
        # Add authentication-specific fields
        if ssh_highball:
            # Highball key mode - password only required for validation, not for save operations
            ssh_password = safe_get_value(form_data, 'ssh_password')
            if require_password and not ssh_password:
                return {'valid': False, 'error': 'SSH password is required for Highball key installation'}
            if ssh_password:
                origin_config['ssh_password'] = ssh_password  # Transient
        # Note: When ssh_highball is False, user has existing keys and no additional input is required
        
        return {'valid': True, 'origin_config': origin_config}
    
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
    
    def delete_origin_with_validation(self, origin_name: str) -> Dict[str, Any]:
        """Delete origin with input validation and error handling"""
        
        if not origin_name:
            return {
                'success': False,
                'error': 'Origin name is required'
            }
        
        success = self.delete_origin(origin_name)
        
        if success:
            return {
                'success': True,
                'origin_name': origin_name
            }
        else:
            return {
                'success': False,
                'error': f"Failed to delete origin '{origin_name}'"
            }