"""
Destination Management Service
Handles all destination CRUD operations and configuration management
"""

import logging
from typing import Dict, Any, Optional, List

from models.forms import safe_get_value

logger = logging.getLogger(__name__)

# =============================================================================
# **DESTINATION OPERATIONS SERVICE** - Full CRUD operations
# =============================================================================

class DestinationOperationsService:
    """Service for destination CRUD operations and lifecycle management"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    # =========================================================================
    # DESTINATION PARSING METHODS
    # =========================================================================
    
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

    def _build_restic_uri(self, repo_type, form_data):
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