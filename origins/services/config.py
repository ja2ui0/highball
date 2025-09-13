"""
Origins Config Service
Handle origin CRUD operations - origins use only Highball SSH keys (no secrets)
"""

import os
import glob
import yaml
import tempfile
import shutil
import io
import re
from typing import Dict, Any, Optional

from shared.services.config import ConfigIOService, ConfigReader
from models.forms import safe_get_value


class OriginConfigService:
    """Handle origin configuration CRUD operations"""

    def __init__(self):
        self.shared = ConfigIOService()
        self.config_reader = ConfigReader()
    
    def save_origin(self, origin_name: str, origin_config: Dict[str, Any]) -> bool:
        """Save an SSH origin - origins use only Highball SSH keys (no secrets)"""
        try:
            # Ensure directories exist
            origins_dir = "/config/local/origins"
            os.makedirs(origins_dir, exist_ok=True)
            
            # Clean origin config - no secrets for origins (Highball SSH keys only)
            clean_config = self._extract_clean_origin_config(origin_config)
            
            # Write config file atomically
            self._write_origin_file_atomically(origin_name, clean_config)
            
            return True
            
        except Exception as e:
            print(f"Error saving origin {origin_name}: {str(e)}")
            return False
    
    def delete_origin(self, origin_name: str) -> bool:
        """Delete an SSH origin permanently - no restore (as per CONFIG.md)"""
        try:
            # File path
            config_file = f"/config/local/origins/{origin_name}.yaml"
            
            # Check if origin exists on disk
            if not os.path.exists(config_file):
                return False
            
            # Remove config file permanently
            os.remove(config_file)
            
            return True
            
        except Exception as e:
            print(f"Error deleting origin {origin_name}: {str(e)}")
            return False
    
    def preview_origin_yaml(self, origin_name: str, origin_config: Dict[str, Any]) -> str:
        """Generate preview YAML for origin config"""
        try:
            # Clean origin config same as save operation
            clean_config = self._extract_clean_origin_config(origin_config)
            
            # Generate YAML preview
            return self._generate_yaml_preview(clean_config)
            
        except Exception as e:
            print(f"Error generating preview for origin {origin_name}: {str(e)}")
            return f"# Error generating preview: {str(e)}"
    
    
    def _extract_clean_origin_config(self, origin_config: Dict[str, Any]) -> Dict[str, Any]:
        """Clean origin config - remove transient fields (no secrets for origins)"""
        clean_config = origin_config.copy()
        
        # Remove fields that shouldn't be stored in YAML
        if 'origin_name' in clean_config:
            del clean_config['origin_name']  # Derived from filename, not stored
        if 'ssh_password' in clean_config:
            del clean_config['ssh_password']  # Transient field, not stored
        
        return clean_config
    
    def _write_origin_file_atomically(self, origin_name: str, clean_config: Dict[str, Any]) -> None:
        """Write origin config file atomically"""
        # Ensure friendly_name is quoted if it contains spaces (but not already quoted)
        if 'friendly_name' in clean_config and ' ' in clean_config['friendly_name']:
            friendly_name = clean_config['friendly_name']
            # Only add quotes if not already quoted
            if not (friendly_name.startswith('"') and friendly_name.endswith('"')):
                clean_config['friendly_name'] = f'"{friendly_name}"'
        
        config_file = f"/config/local/origins/{origin_name}.yaml"
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as temp_config:
            yaml.dump(clean_config, temp_config, default_flow_style=False, indent=2)
            temp_config_path = temp_config.name
        
        # Atomically move config file into place
        shutil.move(temp_config_path, config_file)
    
    def _generate_yaml_preview(self, clean_config: Dict[str, Any]) -> str:
        """Generate YAML preview content"""
        yaml_output = io.StringIO()
        yaml.dump(clean_config, yaml_output, default_flow_style=False, indent=2)
        yaml_content = yaml_output.getvalue()
        yaml_output.close()
        return yaml_content
    
    # =========================================================================
    # FORM PARSING AND VALIDATION - moved from manage.py
    # =========================================================================
    
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
        
        return {'valid': True, 'origin_config': origin_config}
    
    def origin_exists(self, origin_name: str) -> bool:
        """Check if origin already exists"""
        existing_origins = self.config_reader.get_ssh_origins()
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