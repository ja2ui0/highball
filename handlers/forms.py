"""
Remaining Forms Classes - Destination validation and processing
TODO: Extract to appropriate domain services
"""

import html
import logging
from typing import Dict, Any
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)

# =============================================================================
# **DESTINATION VALIDATION HANDLER** - Moved from pages.py ValidationHandlers
# =============================================================================

class DestinationValidationHandler:
    """Handler for destination validation - form parsing and connectivity testing"""
    
    def __init__(self):
        # No dependencies needed - methods are self-contained
        pass
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Get form field value with default"""
        value = form_data.get(field_name, default)
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)
    
    


# =============================================================================
# **FORM PROCESSING HANDLER** - Moved from pages.py POSTHandlers  
# =============================================================================

class FormProcessingHandler:
    """Handler for form data processing - parsing, building configs, saving"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Get form field value with default"""
        value = form_data.get(field_name, default)
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)
    
    def _get_default_port(self, dest_type: str) -> int:
        """Get default port for destination type"""
        defaults = {
            'rsync': 22,
            'rsyncd': 873,
            'restic': 443
        }
        return defaults.get(dest_type, 22)
    
    def _flatten_dest_config_for_uri(self, dest_config):
        """Flatten nested destination config for URI generation"""
        flat_data = {
            'hostname': dest_config.get('hostname'),
            'port': str(dest_config.get('port', '')),
        }
        
        dest_type = dest_config.get('type')
        if dest_type == 'rsync' and 'rsync' in dest_config:
            flat_data.update({
                'username': dest_config['rsync'].get('username'),
                'path': dest_config['rsync'].get('path')
            })
        elif dest_type == 'rsyncd' and 'rsyncd' in dest_config:
            flat_data.update({
                'share': dest_config['rsyncd'].get('share'),
                'username': dest_config['rsyncd'].get('username', ''),
                'password': dest_config['rsyncd'].get('password', '')
            })
        elif dest_type == 'restic' and 'restic' in dest_config:
            flat_data.update({
                'repo_type': dest_config['restic'].get('type'),
                'password': dest_config['restic'].get('password')
            })
        
        return flat_data
    
    def _build_destination_uri(self, dest_config):
        """Build destination URI from config"""
        dest_type = dest_config.get('type', self._get_form_value(dest_config, 'dest_type', ''))
        hostname = dest_config.get('hostname', '')
        port = dest_config.get('port', '')
        
        if dest_type == 'rsync':
            username = dest_config.get('username', '')
            path = dest_config.get('path', '')
            port_str = f":{port}" if port and port != "22" else ""
            return f"rsync://{username}@{hostname}{port_str}{path}"
        elif dest_type == 'rsyncd':
            share = dest_config.get('share', '')
            port_str = f":{port}" if port and port != "873" else ""
            return f"rsync://{hostname}{port_str}/{share}"
        elif dest_type == 'restic':
            repo_type = dest_config.get('repo_type', '')
            if repo_type == 'rest':
                port_str = f":{port}" if port and port != "80" and port != "443" else ""
                return f"rest:http://{hostname}{port_str}/"
        
        return f"{dest_type}://{hostname}"
    
    def add_destination(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new destination"""
        
        # Extract basic destination info
        dest_name = self._get_form_value(form_data, 'dest_name', '').strip()
        friendly_name = self._get_form_value(form_data, 'friendly_name', '').strip()
        dest_type = self._get_form_value(form_data, 'dest_type', '')
        hostname = self._get_form_value(form_data, 'hostname', '').strip()
        port = self._get_form_value(form_data, 'port', '')
        
        # Validation
        if not dest_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination name is required'
            }, status_code=400)
            
        if not dest_type:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination type is required'
            }, status_code=400)
        
        # Check if destination already exists
        existing_destinations = self.backup_config.get_destinations()
        if dest_name in existing_destinations:
            return JSONResponse(content={
                'success': False,
                'error': f'Destination "{dest_name}" already exists'
            }, status_code=400)
        
        # Build nested destination config following example pattern
        dest_config = {
            'type': dest_type,
            'uri': '',  # Will be generated
            'hostname': hostname,
            'port': int(port) if port else self._get_default_port(dest_type),
            'friendly_name': friendly_name or dest_name
        }
        
        # Add type-specific nested sections
        if dest_type == 'rsync':
            username = self._get_form_value(form_data, 'username', '').strip()
            path = self._get_form_value(form_data, 'path', '').strip()
            
            if not username or not path:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Username and path are required for rsync destinations'
                }, status_code=400)
            
            dest_config['rsync'] = {
                'username': username,
                'path': path
            }
            
        elif dest_type == 'rsyncd':
            share = self._get_form_value(form_data, 'share', '').strip()
            
            if not share:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Share is required for rsyncd destinations'
                }, status_code=400)
            
            rsyncd_config = {'share': share}
            
            # Optional fields
            username = self._get_form_value(form_data, 'username', '').strip()
            password = self._get_form_value(form_data, 'password', '').strip()
            if username:
                rsyncd_config['username'] = username
            if password:
                rsyncd_config['password'] = password
                
            dest_config['rsyncd'] = rsyncd_config
            
        elif dest_type == 'restic':
            repo_type = self._get_form_value(form_data, 'repo_type', '')
            password = self._get_form_value(form_data, 'password', '')
            
            if not repo_type or not password:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Repository type and password are required for restic destinations'
                }, status_code=400)
            
            dest_config['restic'] = {
                'type': repo_type,
                'password': password
            }
            
            # Add repo type-specific nested config
            if repo_type == 'rest':
                rest_config = {}
                # Add REST-specific fields as they're implemented
                dest_config['restic']['rest'] = rest_config
            # Other restic types can be added similarly
        
        # Generate URI using the nested structure
        flat_data = self._flatten_dest_config_for_uri(dest_config)
        dest_config['uri'] = self._build_destination_uri(flat_data)
        
        # Save destination
        success = self.backup_config.save_destination(dest_name, dest_config)
        
        if success:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save destination '{dest_name}'"
            }, status_code=500)