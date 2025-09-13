"""
Destinations Config Service
Handle destination CRUD operations with secrets support (REST, S3, rsyncd)
"""

import os
import glob
import yaml
import tempfile
import shutil
import copy
from typing import Dict, Any, Optional
from dotenv import dotenv_values

from shared.services.config import ConfigIOService
from models.forms import safe_get_value


class DestConfigService:
    """Handle destination configuration CRUD operations with secrets support"""
    
    def __init__(self):
        self.shared = ConfigIOService()
    
    def get_destinations(self) -> Dict[str, Any]:
        """Get all destinations - read directly from disk for real-time updates"""
        return self._load_destinations()
    
    def get_destination(self, dest_name: str) -> Optional[Dict[str, Any]]:
        """Get specific destination - read directly from disk"""
        destinations = self._load_destinations()
        return destinations.get(dest_name)
    
    def save_destination(self, dest_name: str, dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """Save destination configuration to persistent storage"""
        if not dest_name:
            return {'success': False, 'error': 'Destination name is required'}
        
        if not dest_config:
            return {'success': False, 'error': 'Destination configuration is required'}
        
        try:
            # Ensure directories exist
            dests_dir = "/config/local/dests"
            secrets_dir = "/config/local/secrets/dests"
            os.makedirs(dests_dir, exist_ok=True)
            os.makedirs(secrets_dir, exist_ok=True)
            
            # Extract secrets from destination config
            clean_config, secrets = self._extract_secrets_from_dest_config(dest_config)
            
            # Write files atomically (only creates .env if secrets dict has content)
            self._write_dest_files_atomically(dest_name, clean_config, secrets)
            
            return {'success': True, 'message': f"Destination '{dest_name}' saved successfully"}
            
        except Exception as e:
            logger.error(f"Failed to save destination {dest_name}: {e}")
            return {'success': False, 'error': 'Failed to save destination configuration'}
    
    def delete_destination(self, dest_name: str) -> bool:
        """Delete a destination permanently - no restore (as per CONFIG.md)"""
        try:
            # File paths
            config_file = f"/config/local/dests/{dest_name}.yaml"
            secrets_file = f"/config/local/secrets/dests/{dest_name}.env"
            
            # Check if destination exists on disk
            if not os.path.exists(config_file):
                return False
            
            # Remove config file
            if os.path.exists(config_file):
                os.remove(config_file)
            
            # Remove secrets file if it exists
            if os.path.exists(secrets_file):
                os.remove(secrets_file)
            
            return True
            
        except Exception as e:
            print(f"Error deleting destination {dest_name}: {str(e)}")
            return False
    
    def _load_destinations(self) -> Dict[str, Any]:
        """Load destinations from /config/local/dests/*.yaml with destination-scoped secrets"""
        destinations = {}
        dests_dir = "/config/local/dests"
        
        if not os.path.exists(dests_dir):
            return destinations
            
        # Find all .yaml files in destinations directory
        dest_files = glob.glob(os.path.join(dests_dir, "*.yaml"))
        
        for dest_file in dest_files:
            dest_name = os.path.splitext(os.path.basename(dest_file))[0]
            
            try:
                # Load destination config using shared service
                dest_config = self.shared.load_yaml(dest_file)
                
                if dest_config is None:
                    print(f"Warning: Empty destination config for {dest_name}")
                    continue
                
                # Load destination-specific secrets if they exist (scoped per destination)
                secrets_file = f"/config/local/secrets/dests/{dest_name}.env"
                if os.path.exists(secrets_file):
                    secrets = dotenv_values(secrets_file)
                    dest_config = self._merge_secrets(dest_config, secrets)
                
                destinations[dest_name] = dest_config
                
            except Exception as e:
                print(f"Warning: Error loading destination {dest_name}: {str(e)}")
                continue
        
        return destinations
    
    def _extract_secrets_from_dest_config(self, dest_config: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Extract secrets from nested destination config - keep secrets support for REST, S3, rsyncd"""
        clean_config = copy.deepcopy(dest_config)
        secrets = {}
        
        dest_type = dest_config.get('type')
        
        # Handle restic-specific secrets from nested structure
        if dest_type == 'restic' and 'restic' in dest_config:
            restic_section = dest_config['restic']
            
            # Extract RESTIC_PASSWORD
            password = restic_section.get('password', '')
            if password and password != '${RESTIC_PASSWORD}':
                secrets['RESTIC_PASSWORD'] = password
                clean_config['restic']['password'] = '${RESTIC_PASSWORD}'
            
            # Handle restic type-specific secrets (REST username/password, S3 keys, etc.)
            repo_type = restic_section.get('type')
            if repo_type == 'rest' and 'rest' in restic_section:
                rest_section = restic_section['rest']
                
                # Extract REST username
                rest_username = rest_section.get('username', '')
                if rest_username and rest_username != '${REST_USER}':
                    secrets['REST_USER'] = rest_username
                    clean_config['restic']['rest']['username'] = '${REST_USER}'
                    
                # Extract REST password  
                rest_password = rest_section.get('password', '')
                if rest_password and rest_password != '${REST_PASS}':
                    secrets['REST_PASS'] = rest_password
                    clean_config['restic']['rest']['password'] = '${REST_PASS}'
        
        # Handle rsyncd password from nested structure
        elif dest_type == 'rsyncd' and 'rsyncd' in dest_config:
            rsyncd_section = dest_config['rsyncd']
            password = rsyncd_section.get('password', '')
            if password and password != '${RSYNCD_PASSWORD}':
                secrets['RSYNCD_PASSWORD'] = password
                clean_config['rsyncd']['password'] = '${RSYNCD_PASSWORD}'
        
        # Remove fields that shouldn't be stored in YAML
        if 'dest_name' in clean_config:
            del clean_config['dest_name']  # Derived from filename, not stored
        
        return clean_config, secrets
    
    def _write_dest_files_atomically(self, dest_name: str, clean_config: Dict[str, Any], secrets: Dict[str, Any]) -> None:
        """Write destination config and secrets files atomically"""
        # Write config file
        config_file = f"/config/local/dests/{dest_name}.yaml"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as temp_config:
            yaml.dump(clean_config, temp_config, default_flow_style=False, indent=2)
            temp_config_path = temp_config.name
        
        # Atomically move config file into place
        shutil.move(temp_config_path, config_file)
        
        # Write secrets file only if there are secrets to write
        secrets_file = f"/config/local/secrets/dests/{dest_name}.env"
        if secrets:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as temp_secrets:
                for key, value in secrets.items():
                    temp_secrets.write(f'{key}="{value}"\n')
                temp_secrets_path = temp_secrets.name
            
            # Atomically move secrets file into place
            shutil.move(temp_secrets_path, secrets_file)
        else:
            # Remove secrets file if no secrets
            if os.path.exists(secrets_file):
                os.remove(secrets_file)
    
    def _merge_secrets(self, config: Dict[str, Any], secrets: Dict[str, str]) -> Dict[str, Any]:
        """Merge secrets into config by replacing ${VAR} placeholders - delegated to shared service"""
        return self.shared.merge_secrets(config, secrets)
    
    # =========================================================================
    # BUSINESS LOGIC AND FORM PARSING - moved from manage.py
    # =========================================================================
    
    def destination_exists(self, dest_name: str) -> bool:
        """Check if destination exists"""
        existing_destinations = self.get_destinations()
        return dest_name in existing_destinations
    
    def save_destination_with_validation(self, dest_name: str, dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """Save destination configuration with validation and error handling"""
        if not dest_name:
            return {'success': False, 'error': 'Destination name is required'}
        
        if not dest_config:
            return {'success': False, 'error': 'Destination configuration is required'}
        
        success = self.save_destination(dest_name, dest_config)
        
        if success:
            return {'success': True, 'message': f"Destination '{dest_name}' saved successfully"}
        else:
            return {'success': False, 'error': 'Failed to save destination configuration'}
    
    def delete_destination_with_validation(self, dest_name: str) -> Dict[str, Any]:
        """Delete destination configuration with validation and error handling"""
        if not dest_name:
            return {'success': False, 'error': 'Destination name is required'}
        
        success = self.delete_destination(dest_name)
        
        if success:
            return {'success': True, 'message': f"Destination '{dest_name}' deleted successfully"}
        else:
            return {'success': False, 'error': 'Failed to delete destination configuration'}
    
    def parse_ssh_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SSH destination configuration"""
        hostname = safe_get_value(form_data, 'dest_hostname')
        username = safe_get_value(form_data, 'dest_username')
        path = safe_get_value(form_data, 'dest_path')
        
        if not hostname:
            return {'valid': False, 'error': 'SSH destination hostname is required'}
        if not username:
            return {'valid': False, 'error': 'SSH destination username is required'}
        if not path:
            return {'valid': False, 'error': 'SSH destination path is required'}
        
        config = {
            'hostname': hostname.strip(),
            'username': username.strip(),
            'path': path.strip()
        }
        
        return {'valid': True, 'config': config}
    
    def parse_local_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse local destination configuration"""
        path = safe_get_value(form_data, 'dest_path')
        
        if not path:
            return {'valid': False, 'error': 'Local destination path is required'}
        
        config = {'path': path.strip()}
        return {'valid': True, 'config': config}
    
    def parse_rsyncd_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse rsyncd destination configuration"""
        hostname = safe_get_value(form_data, 'rsyncd_hostname')
        share = safe_get_value(form_data, 'rsyncd_share')
        
        if not hostname:
            return {'valid': False, 'error': 'Rsyncd hostname is required'}
        if not share:
            return {'valid': False, 'error': 'Rsyncd share is required'}
        
        config = {
            'hostname': hostname.strip(),
            'share': share.strip()
        }
        
        return {'valid': True, 'config': config}
    
    def parse_restic_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Restic destination configuration with all repository types"""
        repo_type = safe_get_value(form_data, 'restic_repo_type')
        password = safe_get_value(form_data, 'restic_password')
        
        # Schema-driven validation for required fields
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        schema = DESTINATION_TYPE_SCHEMAS.get('restic', {})
        required_fields = schema.get('required_fields', [])
        
        # Map form fields to config keys
        field_values = {
            'repo_type': repo_type,
            'password': password
        }
        
        for field in required_fields:
            if field in field_values and not field_values[field]:
                display_name = schema.get('display_name', 'Restic')
                return {'valid': False, 'error': f'{display_name} destination missing {field}'}
        
        # Generate repository URI based on type
        uri_result = self._build_restic_uri(repo_type, form_data)
        if not uri_result['valid']:
            return uri_result
        
        # Base config with URI and password
        config = {
            'repo_type': repo_type,
            'repo_uri': uri_result['uri'],
            'password': password
        }
        
        # Store discrete fields for form editing round-trip
        self._store_discrete_fields(config, repo_type, form_data)
        
        return {'valid': True, 'config': config}
    
    def parse_maintenance_config(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse maintenance configuration from form data"""
        maintenance_mode = safe_get_value(form_data, 'restic_maintenance', 'auto')
        
        maintenance_config = {'restic_maintenance': maintenance_mode}
        
        # If user mode, include custom schedules and retention if provided
        if maintenance_mode == 'user':
            # Custom schedules
            discard_schedule = safe_get_value(form_data, 'maintenance_discard_schedule')
            if discard_schedule:
                maintenance_config['maintenance_discard_schedule'] = discard_schedule
                
            check_schedule = safe_get_value(form_data, 'maintenance_check_schedule') 
            if check_schedule:
                maintenance_config['maintenance_check_schedule'] = check_schedule
            
            # Custom retention policy
            retention_fields = ['keep_last', 'keep_hourly', 'keep_daily', 'keep_weekly', 'keep_monthly', 'keep_yearly']
            retention_policy = {}
            for field in retention_fields:
                value = safe_get_value(form_data, field)
                if value:
                    try:
                        retention_policy[field] = int(value)
                    except ValueError:
                        pass  # Skip invalid values
            
            if retention_policy:
                maintenance_config['retention_policy'] = retention_policy
        
        return {'valid': True, 'maintenance_config': maintenance_config}
    
    def build_destination_uri(self, dest_type, form_data):
        """Higher-order URI builder for all destination types"""
        if dest_type == 'rsync':
            hostname = safe_get_value(form_data, 'hostname')
            username = safe_get_value(form_data, 'username')
            path = safe_get_value(form_data, 'path')
            port = safe_get_value(form_data, 'port', '22')
            
            if not all([hostname, username, path]):
                return {'valid': False, 'error': 'Rsync destination requires hostname, username, and path'}
            
            if port != '22':
                uri = f"{username}@{hostname}:{path} (port {port})"
            else:
                uri = f"{username}@{hostname}:{path}"
            
            return {'valid': True, 'uri': uri}
            
        elif dest_type == 'rsyncd':
            hostname = safe_get_value(form_data, 'hostname')
            share = safe_get_value(form_data, 'share')
            port = safe_get_value(form_data, 'port', '873')
            
            if not all([hostname, share]):
                return {'valid': False, 'error': 'Rsyncd destination requires hostname and share'}
            
            if port != '873':
                uri = f"rsync://{hostname}:{port}/{share}"
            else:
                uri = f"rsync://{hostname}/{share}"
            
            return {'valid': True, 'uri': uri}
            
        elif dest_type == 'restic':
            repo_type = safe_get_value(form_data, 'repo_type', '')
            return self._build_restic_uri(repo_type, form_data)
            
        else:
            return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}
    
    def _flatten_dest_config_for_uri(self, dest_config: Dict[str, Any]) -> Dict[str, Any]:
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
            flat_data.update(dest_config['rsyncd'])
        elif dest_type == 'restic' and 'restic' in dest_config:
            flat_data.update({
                'repo_type': dest_config['restic'].get('type'),
                'password': dest_config['restic'].get('password')
            })
        
        return flat_data
    
    def _build_destination_uri(self, dest_config: Dict[str, Any]) -> str:
        """Build destination URI based on type and configuration"""
        dest_type = dest_config.get('type')
        uri_result = self.build_destination_uri(dest_type, dest_config)
        
        if uri_result['valid']:
            return uri_result['uri']
        else:
            return f"Error: {uri_result.get('error', 'URI generation failed')}"
    
    def _store_discrete_fields(self, config, repo_type, form_data):
        """Store discrete fields for form editing round-trip data integrity using schema"""
        from dests.schema import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
        if repo_type in RESTIC_REPOSITORY_TYPE_SCHEMAS:
            schema = RESTIC_REPOSITORY_TYPE_SCHEMAS[repo_type]
            
            # Iterate through schema fields and extract values
            for field_def in schema.get('fields', []):
                field_name = field_def['name']
                
                # Handle different field types
                if field_def.get('type') == 'checkbox':
                    # Checkbox fields use 'on' for checked
                    config[field_name] = safe_get_value(form_data, field_name) == 'on'
                else:
                    # Text/number fields use placeholder as default or empty string
                    default_value = field_def.get('placeholder', '')
                    config[field_name] = safe_get_value(form_data, field_name, default_value)
    
    # =========================================================================
    # FORM HANDLING AND VALIDATION METHODS - moved from manage.py
    # =========================================================================
    
    def add_destination_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add new destination from form data - contains all business logic"""
        # Extract basic destination info using safe_get_value
        dest_name = safe_get_value(form_data, 'dest_name', '').strip()
        friendly_name = safe_get_value(form_data, 'friendly_name', '').strip()
        dest_type = safe_get_value(form_data, 'dest_type', '')
        hostname = safe_get_value(form_data, 'hostname', '').strip()
        port = safe_get_value(form_data, 'port', '')
        
        # Validation
        if not dest_name:
            return {'success': False, 'error': 'Destination name is required'}
            
        if not dest_type:
            return {'success': False, 'error': 'Destination type is required'}
        
        # Check if destination already exists
        if self.destination_exists(dest_name):
            return {'success': False, 'error': f'Destination "{dest_name}" already exists'}
        
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
            username = safe_get_value(form_data, 'username', '').strip()
            path = safe_get_value(form_data, 'path', '').strip()
            
            if not username or not path:
                return {'success': False, 'error': 'Username and path are required for rsync destinations'}
            
            dest_config['rsync'] = {
                'username': username,
                'path': path
            }
            
        elif dest_type == 'rsyncd':
            share = safe_get_value(form_data, 'share', '').strip()
            
            if not share:
                return {'success': False, 'error': 'Share is required for rsyncd destinations'}
            
            rsyncd_config = {'share': share}
            
            # Optional fields
            username = safe_get_value(form_data, 'username', '').strip()
            password = safe_get_value(form_data, 'password', '').strip()
            if username:
                rsyncd_config['username'] = username
            if password:
                rsyncd_config['password'] = password
                
            dest_config['rsyncd'] = rsyncd_config
            
        elif dest_type == 'restic':
            repo_type = safe_get_value(form_data, 'restic_repo_type') or safe_get_value(form_data, 'repo_type', '')
            password = safe_get_value(form_data, 'restic_password') or safe_get_value(form_data, 'password', '')
            
            if not repo_type or not password:
                return {'success': False, 'error': 'Repository type and password are required for restic destinations'}
            
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
        return self.save_destination(dest_name, dest_config)
    
    def update_destination_from_form(self, dest_name: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing destination from form data - contains all business logic"""
        if not dest_name:
            return {'success': False, 'error': 'Destination name is required'}
        
        # Get existing destination config to preserve type-specific settings
        existing_dest = self.get_destination(dest_name)
        if not existing_dest:
            return {'success': False, 'error': f'Destination "{dest_name}" not found'}
        
        # Update config with form data (similar to add_destination logic)
        updated_config = existing_dest.copy()
        updated_config['friendly_name'] = safe_get_value(form_data, 'friendly_name', dest_name).strip()
        updated_config['hostname'] = safe_get_value(form_data, 'hostname', '').strip()
        port = safe_get_value(form_data, 'port', '')
        if port:
            updated_config['port'] = int(port)
        
        # Regenerate URI with updated config
        flat_data = self._flatten_dest_config_for_uri(updated_config)
        updated_config['uri'] = self._build_destination_uri(flat_data)
        
        # Save updated destination
        return self.save_destination(dest_name, updated_config)
    
    def validate_destination_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate destination configuration from form data - contains all business logic"""
        dest_type = safe_get_value(form_data, 'dest_type', '')
        hostname = safe_get_value(form_data, 'hostname', '')
        
        if not dest_type or not hostname:
            return {
                'success': False,
                'validation_message': 'Destination type and hostname are required for validation'
            }
        
        # Import services locally to avoid circular imports
        from dests.services.rsync import rsync_service
        from dests.services.restic import restic_service
        
        # Test basic connectivity based on destination type using atomic services
        if dest_type == 'rsync':
            # Use superior rsync validation from atomic service (SSH + path writability)
            result = rsync_service.validate_rsync_destination(form_data)
            template_context = {
                'success': result['success'],
                'validation_message': result.get('message') or result.get('error', 'Unknown error')
            }
        elif dest_type == 'rsyncd':
            # Use superior rsyncd validation from atomic service
            result = rsync_service.validate_rsyncd_destination(form_data)
            template_context = {
                'success': result['success'],
                'validation_message': result.get('message') or result.get('error', 'Unknown error')
            }
        elif dest_type == 'restic':
            # Use superior restic validation from atomic service (real repository connectivity)
            result = restic_service.validate_restic_destination(form_data)
            template_context = {
                'success': result['success'],
                'validation_message': result.get('message', 'Unknown error')
            }
        else:
            template_context = {
                'success': False,
                'validation_message': f'Validation not implemented for destination type: {dest_type}'
            }
        
        # Generate URI preview
        if template_context.get('success'):
            uri_result = self.build_destination_uri(dest_type, form_data)
            if uri_result['valid']:
                template_context['uri_generated'] = uri_result['uri']
        
        return template_context
    
    def validate_ssh_destination_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SSH destination configuration - business logic moved from htmx handlers"""
        hostname = safe_get_value(form_data, 'dest_hostname')
        username = safe_get_value(form_data, 'dest_username')
        path = safe_get_value(form_data, 'dest_path')
        
        # Business logic: delegate to proper destination validation service
        validation_data = {'hostname': hostname, 'username': username, 'path': path}
        
        # Import service locally to avoid circular imports
        from dests.services.rsync import rsync_service
        result = rsync_service.validate_rsync_destination(validation_data)
        
        # Return structured data for handler to render
        return result
    
    def validate_restic_destination_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Restic destination configuration - business logic moved from htmx handlers"""
        # Extract parameters using correct field names
        repo_type = safe_get_value(form_data, 'restic_repo_type') or safe_get_value(form_data, 'repo_type')
        password = safe_get_value(form_data, 'restic_password')
        
        # Schema-driven validation for required fields
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        schema = DESTINATION_TYPE_SCHEMAS.get('restic', {})
        required_fields = schema.get('required_fields', [])
        
        # Map form fields to config keys
        field_values = {
            'repo_type': repo_type,
            'password': password
        }
        
        for field in required_fields:
            if field in field_values and not field_values[field]:
                display_name = schema.get('display_name', 'Restic')
                return {
                    'success': False, 
                    'error': f'{display_name} destination missing {field}'
                }
        
        # Build URI from individual repository fields using existing URI builder
        uri_result = self._build_restic_uri(repo_type, form_data)
        
        if not uri_result.get('valid'):
            return {
                'success': False, 
                'error': uri_result.get('error', 'Invalid repository configuration')
            }
        
        repo_uri = uri_result['uri']
        
        # Business logic: delegate to proper destination validation service
        validation_data = {'repo_type': repo_type, 'repo_uri': repo_uri, 'restic_password': password}
        
        # Import service locally to avoid circular imports
        from dests.services.restic import restic_service
        result = restic_service.validate_restic_destination(validation_data)
        
        # Return structured data for handler to render
        return result
    
    def validate_origin_repo_path_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate same-as-origin repository path - business logic moved from htmx handlers"""
        # Extract repository path
        repo_path = safe_get_value(form_data, 'origin_repo_path')
        if not repo_path or not repo_path.strip():
            return {'success': False, 'error': 'Please enter a repository path'}
        
        # Extract SSH configuration (required for same_as_origin)
        hostname = safe_get_value(form_data, 'hostname')
        username = safe_get_value(form_data, 'username')
        
        if not hostname or not username:
            return {'success': False, 'error': 'SSH configuration required for same-as-origin repositories'}
        
        # Business logic: delegate to proper destination validation service
        validation_data = {'hostname': hostname, 'username': username, 'path': repo_path}
        
        # Import service locally to avoid circular imports
        from dests.services.rsync import rsync_service
        result = rsync_service.validate_rsync_destination(validation_data)
        
        # Return structured data for handler to render
        return result
    
    def parse_restic_destination_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse restic destination from form data - delegates to existing parser"""
        return self.parse_restic_destination(form_data)
    
    def generate_uri_preview(self, dest_type: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate URI preview for destination configuration - business logic moved from htmx handlers"""
        if dest_type == 'restic':
            # Check both job form field name (restic_repo_type) and destination form field name (repo_type)
            repo_type = safe_get_value(form_data, 'restic_repo_type') or safe_get_value(form_data, 'repo_type')
            
            if not repo_type:
                return {'uri': 'Select repository type to see URI preview'}
            else:
                # Use existing URI builder from service
                uri_result = self._build_restic_uri(repo_type, form_data)
                
                if uri_result.get('valid'):
                    # Mask password in display
                    uri = uri_result['uri']
                    if ':' in uri and '@' in uri:
                        # Replace password with *** for display
                        parts = uri.split('@')
                        if len(parts) == 2:
                            auth_part = parts[0]
                            if ':' in auth_part:
                                scheme_and_user = auth_part.rsplit(':', 1)[0]
                                uri = f"{scheme_and_user}:***@{parts[1]}"
                    
                    return {'uri': uri}
                else:
                    return {'uri': uri_result.get('error', 'Invalid configuration')}
        else:
            # Use general URI builder for other destination types
            uri_result = self.build_destination_uri(dest_type, form_data)
            if uri_result['valid']:
                return {'uri': uri_result['uri']}
            else:
                return {'uri': uri_result.get('error', 'Invalid configuration')}
    
    # =========================================================================
    # HELPER METHODS - moved from manage.py
    # =========================================================================
    
    def _get_default_port(self, dest_type: str) -> int:
        """Get default port for destination type"""
        defaults = {
            'rsync': 22,
            'rsyncd': 873,
            'restic': 443  # Common for REST
        }
        return defaults.get(dest_type, 22)
    
    def _generate_uri_for_config(self, dest_config: Dict[str, Any]) -> str:
        """Generate URI for destination config"""
        dest_type = dest_config.get('type', '')
        hostname = dest_config.get('hostname', '')
        port = dest_config.get('port', 22)
        
        if dest_type == 'rsync':
            rsync_config = dest_config.get('rsync', {})
            username = rsync_config.get('username', '')
            path = rsync_config.get('path', '')
            return f"rsync://{username}@{hostname}:{port}{path}"
            
        elif dest_type == 'rsyncd':
            rsyncd_config = dest_config.get('rsyncd', {})
            share = rsyncd_config.get('share', '')
            return f"rsync://{hostname}:{port}/{share}"
            
        elif dest_type == 'restic':
            restic_config = dest_config.get('restic', {})
            repo_type = restic_config.get('type', '')
            
            if repo_type == 'rest':
                rest_config = restic_config.get('rest', {})
                url = rest_config.get('url', '')
                return url
            elif repo_type == 'same-as-origin':
                path = restic_config.get('path', '')
                return f"same-as-origin:{path}"
        
        return f"{dest_type}://{hostname}:{port}"
    
    def _build_restic_uri(self, repo_type: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Restic repository URI based on type"""
        if repo_type == 'local':
            path = safe_get_value(form_data, 'local_path')
            if not path:
                return {'valid': False, 'error': 'Local repository path is required'}
            return {'valid': True, 'uri': path.strip()}
            
        elif repo_type == 'rest':
            hostname = safe_get_value(form_data, 'hostname')
            port = safe_get_value(form_data, 'port', '8000')
            path = safe_get_value(form_data, 'path', '')
            use_root = safe_get_value(form_data, 'use_root') == 'on'
            use_https = safe_get_value(form_data, 'use_https') == 'on'
            username = safe_get_value(form_data, 'username', '')
            password = safe_get_value(form_data, 'password', '')
            
            if not hostname:
                return {'valid': False, 'error': 'REST server hostname is required'}
            
            # Validate path logic: either path OR use_root must be true, but not both, not neither
            has_path = bool(path.strip())
            if has_path and use_root:
                return {'valid': False, 'error': 'Cannot specify both repository path and use repository root - choose one'}
            if not has_path and not use_root:
                return {'valid': False, 'error': 'Must specify either a repository path or check "Use Repository Root"'}
            
            # Build URI components
            scheme = 'https' if use_https else 'http'
            
            # Build authority (user:pass@host:port or just host:port)
            authority = f'{hostname}:{port}'
            if username and password:
                authority = f'{username}:{password}@{authority}'
            elif username:
                authority = f'{username}@{authority}'
            
            # Build path
            if use_root:
                uri_path = ''  # No trailing slash for repository root
            else:
                # Ensure path starts with /
                clean_path = path.strip()
                if not clean_path.startswith('/'):
                    clean_path = '/' + clean_path
                uri_path = clean_path
            
            return {'valid': True, 'uri': f'rest:{scheme}://{authority}{uri_path}'}
            
        elif repo_type == 's3':
            bucket = safe_get_value(form_data, 'bucket')
            prefix = safe_get_value(form_data, 'prefix', '')
            endpoint = safe_get_value(form_data, 'endpoint', '')
            region = safe_get_value(form_data, 'region', 'us-east-1')  # Default for compatibility
            access_key = safe_get_value(form_data, 'access_key')
            secret_key = safe_get_value(form_data, 'secret_key')
            
            if not bucket:
                return {'valid': False, 'error': 'S3 bucket name is required'}
            if not access_key:
                return {'valid': False, 'error': 'S3 access key is required'}
            if not secret_key:
                return {'valid': False, 'error': 'S3 secret key is required'}
            
            # Build URI using restic S3 format
            if endpoint:
                # Custom S3-compatible endpoint (Cloudflare R2, MinIO, etc.)
                # Format: s3:https://endpoint/bucket
                uri = f's3:{endpoint}/{bucket}'
            else:
                # AWS S3 - use region-based endpoint
                # Format: s3:s3.region.amazonaws.com/bucket  
                uri = f's3:s3.{region}.amazonaws.com/{bucket}'
            
            if prefix:
                uri += f'/{prefix}'
            return {'valid': True, 'uri': uri}
            
        elif repo_type == 'sftp':
            hostname = safe_get_value(form_data, 'hostname')
            username = safe_get_value(form_data, 'username')
            path = safe_get_value(form_data, 'path')
            
            if not hostname:
                return {'valid': False, 'error': 'SFTP hostname is required'}
            if not username:
                return {'valid': False, 'error': 'SFTP username is required'}
            if not path:
                return {'valid': False, 'error': 'SFTP path is required'}
            
            return {'valid': True, 'uri': f'sftp:{username}@{hostname}:{path}'}
            
        elif repo_type == 'rclone':
            remote = safe_get_value(form_data, 'remote')
            path = safe_get_value(form_data, 'path')
            
            if not remote:
                return {'valid': False, 'error': 'rclone remote name is required'}
            if not path:
                return {'valid': False, 'error': 'rclone path is required'}
            
            return {'valid': True, 'uri': f'rclone:{remote}:{path}'}
            
        elif repo_type == 'same_as_origin':
            path = safe_get_value(form_data, 'path')
            if not path:
                return {'valid': False, 'error': 'Origin repository path is required'}
            return {'valid': True, 'uri': path.strip()}
        
        else:
            return {'valid': False, 'error': f'Unknown repository type: {repo_type}'}