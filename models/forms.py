"""
Consolidated Form Parsing Module
Merges all form parsers into single module with clean class-based organization
Replaces: job_form_parser.py, ssh_form_parser.py, restic_form_parser.py, local_form_parser.py, 
         rsyncd_form_parser.py, notification_form_parser.py, maintenance_form_parser.py
Also includes form data structures moved from services/form_data_service.py
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# **FORM DATA STRUCTURES** - Configuration dataclasses for form handling
# =============================================================================

class SourceConfig(BaseModel):
    """Form concern: source configuration data structure"""
    source_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    
    # Multi-path support
    source_paths: List[Dict[str, Any]] = Field(default_factory=list)


class DestConfig(BaseModel):
    """Form concern: standard destination configuration data structure"""
    dest_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    rsyncd_hostname: str = ""
    rsyncd_share: str = ""
    rsync_options: str = ""


class ResticConfig(BaseModel):
    """Form concern: Restic repository configuration data structure"""
    repo_type: str = ""
    password: str = ""
    
    # Repository type specific fields
    local_path: str = ""
    
    # REST fields
    rest_hostname: str = ""
    rest_port: str = "8000"
    rest_path: str = ""
    rest_use_root: bool = False
    rest_use_https: bool = True
    rest_username: str = ""
    rest_password: str = ""
    
    # S3 fields
    s3_bucket: str = ""
    s3_region: str = ""
    s3_prefix: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint: str = ""
    
    # SFTP fields
    sftp_hostname: str = ""
    sftp_path: str = ""
    
    # Rclone fields
    rclone_config: str = ""


class NotificationConfig(BaseModel):
    """Form concern: notification provider configuration data structure"""
    provider_type: str = ""
    notify_on_success: bool = False
    notify_on_failure: bool = True
    success_message: str = ""
    failure_message: str = ""


class JobFormData(BaseModel):
    """Form concern: complete job form data structure"""
    job_name: str = ""
    source_config: SourceConfig = Field(default_factory=SourceConfig)
    dest_config: DestConfig = Field(default_factory=DestConfig)
    restic_config: ResticConfig = Field(default_factory=ResticConfig)
    schedule: str = ""
    enabled: bool = True
    respect_conflicts: bool = True
    restic_maintenance: str = "auto"
    notifications: List[NotificationConfig] = Field(default_factory=list)


class OriginConfig(BaseModel):
    """SSH origin configuration data structure matching origins/{name}.yaml schema"""
    friendly_name: str
    ssh_hostname: str
    ssh_port: int = 22
    ssh_timeout: int = 5
    ssh_username: str
    ssh_highball: bool = True
    ssh_pubkey: str = "${SSH_PUBKEY}"
    ssh_passphrase: str = "${SSH_PASSPHRASE}"
    rsync_available: bool = False
    container_runtime: Optional[str] = None
    
    # Origin name is derived from filename, not stored in YAML


class OriginSecrets(BaseModel):
    """SSH origin secrets data structure matching secrets/origins/{name}.env schema"""
    ssh_pubkey: Optional[str] = None
    ssh_passphrase: Optional[str] = None


class OriginFormData(BaseModel):
    """Form concern: SSH origin form data structure"""
    origin_name: str = ""
    friendly_name: str = ""
    ssh_hostname: str = ""
    ssh_port: int = 22
    ssh_timeout: int = 5
    ssh_username: str = ""
    ssh_highball: bool = True
    ssh_password: str = ""  # Transient - not stored
    ssh_pubkey: str = ""
    requires_passphrase: bool = False
    ssh_passphrase: str = ""


class OriginValidationResult(BaseModel):
    """SSH origin validation result data structure"""
    success: bool
    connection_success: bool = False
    rsync_available: bool = False
    container_runtime: Optional[str] = None
    validation_message: str = ""
    error_message: Optional[str] = None

# =============================================================================
# UTILITY FUNCTIONS - Common form parsing helpers
# =============================================================================

def safe_get_list(data: Dict[str, Any], key: str) -> List[str]:
    """Safely get list from form data regardless of format"""
    if hasattr(data, 'getlist'):
        return data.getlist(key)
    else:
        value = data.get(key, [])
        return value if isinstance(value, list) else [value]

def safe_get_value(data: Dict[str, Any], key: str, default: str = '') -> str:
    """Safely get single value from form data"""
    values = safe_get_list(data, key)
    return values[0] if values and values[0] else default

def parse_lines(text: str) -> List[str]:
    """Parse textarea input into list of non-empty lines"""
    return [line.strip() for line in text.split('\n') if line.strip()]

# =============================================================================
# SOURCE CONFIGURATION PARSERS
# =============================================================================

class SourceParser:
    """Parse source configurations (SSH, local)"""
    
    @staticmethod
    def parse_ssh_source(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SSH source configuration"""
        hostname = safe_get_value(form_data, 'hostname')
        username = safe_get_value(form_data, 'username')
        
        if not hostname:
            return {'valid': False, 'error': 'SSH hostname is required'}
        if not username:
            return {'valid': False, 'error': 'SSH username is required'}
        
        config = {
            'hostname': hostname.strip(),
            'username': username.strip()
        }
        
        # Include container runtime if detected during validation
        container_runtime = safe_get_value(form_data, 'container_runtime')
        if container_runtime:
            config['container_runtime'] = container_runtime
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_local_source(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse local source configuration"""
        # Local sources need minimal configuration
        return {'valid': True, 'config': {}}

# =============================================================================
# DESTINATION CONFIGURATION PARSERS  
# =============================================================================

class DestinationParser:
    """Parse destination configurations (SSH, local, rsyncd, restic)"""
    
    @staticmethod
    def parse_ssh_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    @staticmethod
    def parse_local_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse local destination configuration"""
        path = safe_get_value(form_data, 'dest_path')
        
        if not path:
            return {'valid': False, 'error': 'Local destination path is required'}
        
        config = {'path': path.strip()}
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_rsyncd_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    @staticmethod
    def parse_restic_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Restic destination configuration with all repository types"""
        repo_type = safe_get_value(form_data, 'restic_repo_type')
        password = safe_get_value(form_data, 'restic_password')
        
        # Schema-driven validation for required fields
        from models.schemas import DESTINATION_TYPE_SCHEMAS
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
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        if not uri_result['valid']:
            return uri_result
        
        # Base config with URI and password
        config = {
            'repo_type': repo_type,
            'repo_uri': uri_result['uri'],
            'password': password
        }
        
        # Store discrete fields for form editing round-trip
        DestinationParser._store_discrete_fields(config, repo_type, form_data)
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def _build_restic_uri(repo_type, form_data):
        """Build Restic repository URI based on type"""
        if repo_type == 'local':
            path = safe_get_value(form_data, 'local_path')
            if not path:
                return {'valid': False, 'error': 'Local repository path is required'}
            return {'valid': True, 'uri': path.strip()}
            
        elif repo_type == 'rest':
            hostname = safe_get_value(form_data, 'rest_hostname')
            port = safe_get_value(form_data, 'rest_port', '8000')
            path = safe_get_value(form_data, 'rest_path', '')
            use_root = safe_get_value(form_data, 'rest_use_root') == 'on'
            use_https = safe_get_value(form_data, 'rest_use_https') == 'on'
            username = safe_get_value(form_data, 'rest_username', '')
            password = safe_get_value(form_data, 'rest_password', '')
            
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
            bucket = safe_get_value(form_data, 's3_bucket')
            prefix = safe_get_value(form_data, 's3_prefix', '')
            endpoint = safe_get_value(form_data, 's3_endpoint', '')
            region = safe_get_value(form_data, 's3_region', 'us-east-1')  # Default for compatibility
            access_key = safe_get_value(form_data, 's3_access_key')
            secret_key = safe_get_value(form_data, 's3_secret_key')
            
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
            hostname = safe_get_value(form_data, 'sftp_hostname')
            username = safe_get_value(form_data, 'sftp_username')
            path = safe_get_value(form_data, 'sftp_path')
            
            if not hostname:
                return {'valid': False, 'error': 'SFTP hostname is required'}
            if not username:
                return {'valid': False, 'error': 'SFTP username is required'}
            if not path:
                return {'valid': False, 'error': 'SFTP path is required'}
            
            return {'valid': True, 'uri': f'sftp:{username}@{hostname}:{path}'}
            
        elif repo_type == 'rclone':
            remote = safe_get_value(form_data, 'rclone_remote')
            path = safe_get_value(form_data, 'rclone_path')
            
            if not remote:
                return {'valid': False, 'error': 'rclone remote name is required'}
            if not path:
                return {'valid': False, 'error': 'rclone path is required'}
            
            return {'valid': True, 'uri': f'rclone:{remote}:{path}'}
            
        elif repo_type == 'same_as_origin':
            path = safe_get_value(form_data, 'origin_repo_path')
            if not path:
                return {'valid': False, 'error': 'Origin repository path is required'}
            return {'valid': True, 'uri': path.strip()}
        
        else:
            return {'valid': False, 'error': f'Unknown repository type: {repo_type}'}
    
    @staticmethod
    def _store_discrete_fields(config, repo_type, form_data):
        """Store discrete fields for form editing round-trip data integrity using schema"""
        from models.schemas import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
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

# =============================================================================
# SOURCE PATHS PARSER
# =============================================================================

class SourcePathsParser:
    """Parse multi-path source configurations"""
    
    @staticmethod
    def parse_multi_path_options(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse multi-path source options from form data"""
        source_paths = safe_get_list(form_data, 'source_path[]')
        source_includes = safe_get_list(form_data, 'source_includes[]') 
        source_excludes = safe_get_list(form_data, 'source_excludes[]')
        
        if not source_paths:
            return {'valid': False, 'error': 'At least one source path is required'}
        
        # Build source paths array with per-path includes/excludes
        parsed_paths = []
        for i, path in enumerate(source_paths):
            path = path.strip()
            if not path:
                continue  # Skip empty paths instead of failing
            
            # Get includes/excludes for this path (or empty if not provided)
            includes_text = source_includes[i] if i < len(source_includes) else ''
            excludes_text = source_excludes[i] if i < len(source_excludes) else ''
            
            path_config = {
                'path': path,
                'includes': parse_lines(includes_text),
                'excludes': parse_lines(excludes_text)
            }
            parsed_paths.append(path_config)
        
        # Ensure we have at least one valid path after filtering empty ones
        if not parsed_paths:
            return {'valid': False, 'error': 'At least one source path is required'}
        
        return {'valid': True, 'source_paths': parsed_paths}

# =============================================================================
# NOTIFICATION CONFIGURATION PARSER
# =============================================================================

class NotificationParser:
    """Parse notification provider configurations"""
    
    @staticmethod
    def parse_notification_config(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse notification configuration from form data"""
        # Get notification form arrays
        providers = safe_get_list(form_data, 'notification_providers[]')
        notify_success_flags = safe_get_list(form_data, 'notify_on_success[]')
        success_messages = safe_get_list(form_data, 'notification_success_messages[]')
        notify_failure_flags = safe_get_list(form_data, 'notify_on_failure[]')
        failure_messages = safe_get_list(form_data, 'notification_failure_messages[]')
        notify_maintenance_failure_flags = safe_get_list(form_data, 'notify_on_maintenance_failure[]')
        
        notifications = []
        
        # Process each provider configuration
        for i, provider in enumerate(providers):
            if not provider:  # Skip empty providers
                continue
                
            # Get corresponding values for this provider (with safe indexing)
            notify_success = i < len(notify_success_flags) and notify_success_flags[i] == 'on'
            success_message = success_messages[i] if i < len(success_messages) else ''
            notify_failure = i < len(notify_failure_flags) and notify_failure_flags[i] == 'on'
            failure_message = failure_messages[i] if i < len(failure_messages) else ''
            notify_maintenance_failure = i < len(notify_maintenance_failure_flags) and notify_maintenance_failure_flags[i] == 'on'
            
            # Validate - at least one notification type must be enabled
            if not notify_success and not notify_failure:
                return {
                    'valid': False, 
                    'error': f'Provider {provider}: At least one notification type (success or failure) must be enabled'
                }
            
            # Build notification config
            notification_config = {
                'provider': provider,
                'notify_on_success': notify_success,
                'notify_on_failure': notify_failure,
                'notify_on_maintenance_failure': notify_maintenance_failure
            }
            
            # Add custom messages if provided
            if notify_success and success_message.strip():
                notification_config['success_message'] = success_message.strip()
            if notify_failure and failure_message.strip():
                notification_config['failure_message'] = failure_message.strip()
            
            notifications.append(notification_config)
        
        return {'valid': True, 'notifications': notifications}

# =============================================================================
# MAINTENANCE CONFIGURATION PARSER
# =============================================================================

class MaintenanceParser:
    """Parse maintenance configuration for Restic repositories"""
    
    @staticmethod
    def parse_maintenance_config(form_data: Dict[str, Any]) -> Dict[str, Any]:
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

# =============================================================================
# UNIFIED JOB PARSER - Main entry point
# =============================================================================

class JobFormParser:
    """Unified job form parser - single entry point for all form parsing"""
    
    @staticmethod
    def parse_job_form(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse complete job form data"""
        # Basic job info
        job_name = safe_get_value(form_data, 'job_name').strip()
        if not job_name:
            return {'valid': False, 'error': 'Job name is required'}
        
        # Source parsing
        source_result = JobFormParser.parse_source_configuration(form_data)
        if not source_result['valid']:
            return source_result
        source_config = source_result['config']
        
        # Destination parsing
        dest_result = JobFormParser.parse_destination_configuration(form_data)
        if not dest_result['valid']:
            return dest_result
        dest_config = dest_result['config']
        
        # Handle schedule
        schedule = safe_get_value(form_data, 'schedule', 'manual')
        if schedule == 'custom':
            cron_pattern = safe_get_value(form_data, 'cron_pattern').strip()
            if cron_pattern:
                schedule = cron_pattern
            else:
                return {'valid': False, 'error': 'Cron pattern is required when Custom Cron Pattern is selected'}
        
        enabled = 'enabled' in form_data
        respect_conflicts = 'respect_conflicts' in form_data
        
        # Parse notification configuration
        notification_result = NotificationParser.parse_notification_config(form_data)
        if not notification_result['valid']:
            return notification_result
        notifications = notification_result['notifications']
        
        # Parse maintenance configuration (only for Restic destinations)
        maintenance_config = None
        if dest_config.get('repo_type'):  # Restic destination
            maintenance_result = MaintenanceParser.parse_maintenance_config(form_data)
            if not maintenance_result['valid']:
                return maintenance_result
            maintenance_config = maintenance_result.get('maintenance_config')
        
        job_data = {
            'valid': True,
            'job_name': job_name,
            'source_type': source_config['source_type'],
            'source_config': source_config,
            'dest_type': dest_config['dest_type'],
            'dest_config': dest_config,
            'schedule': schedule,
            'enabled': enabled,
            'respect_conflicts': respect_conflicts,
            'notifications': notifications
        }
        
        # Add maintenance config if present
        if maintenance_config:
            job_data['maintenance_config'] = maintenance_config
            
        return job_data
    
    @staticmethod
    def parse_source_configuration(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse complete source configuration including paths"""
        source_type = safe_get_value(form_data, 'source_type')
        if not source_type:
            return {'valid': False, 'error': 'Source type is required'}
        
        # Schema-driven source parsing
        from models.schemas import SOURCE_TYPE_SCHEMAS
        
        if source_type not in SOURCE_TYPE_SCHEMAS:
            return {'valid': False, 'error': f'Unknown source type: {source_type}'}
        
        # Parse using type-specific parser (following naming convention)
        parser_method_name = f'parse_{source_type}_source'
        if hasattr(SourceParser, parser_method_name):
            parser_method = getattr(SourceParser, parser_method_name)
            source_result = parser_method(form_data)
        else:
            return {'valid': False, 'error': f'No parser available for source type: {source_type}'}
        
        if not source_result['valid']:
            return source_result
        source_config = source_result['config']
        
        # Parse source paths (common to all source types)
        source_paths_data = SourcePathsParser.parse_multi_path_options(form_data)
        if not source_paths_data['valid']:
            return source_paths_data
        
        # Combine config with paths
        source_config['source_type'] = source_type
        source_config['source_paths'] = source_paths_data['source_paths']
        
        return {'valid': True, 'config': source_config}
    
    @staticmethod
    def parse_destination_configuration(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse destination configuration"""
        dest_type = safe_get_value(form_data, 'dest_type')
        if not dest_type:
            return {'valid': False, 'error': 'Destination type is required'}
        
        # Schema-driven destination parsing
        from models.schemas import DESTINATION_TYPE_SCHEMAS
        
        if dest_type not in DESTINATION_TYPE_SCHEMAS:
            return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}
        
        # Parse using type-specific parser (following naming convention)
        parser_method_name = f'parse_{dest_type}_destination'
        if hasattr(DestinationParser, parser_method_name):
            parser_method = getattr(DestinationParser, parser_method_name)
            dest_result = parser_method(form_data)
        else:
            return {'valid': False, 'error': f'No parser available for destination type: {dest_type}'}
        
        if not dest_result['valid']:
            return dest_result
        
        dest_config = dest_result['config']
        dest_config['dest_type'] = dest_type
        
        return {'valid': True, 'config': dest_config}

# =============================================================================
# SSH ORIGIN CONFIGURATION PARSER
# =============================================================================

class OriginParser:
    """Parse SSH origin configurations"""
    
    @staticmethod
    def parse_origin_form(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SSH origin form data"""
        origin_name = safe_get_value(form_data, 'origin_name').strip()
        if not origin_name:
            return {'valid': False, 'error': 'Origin name is required'}
        
        # Validate origin name is a valid slug (matches filename requirements)
        import re
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
        
        # Validate authentication configuration
        auth_validation = OriginParser._validate_auth_config(form_data, ssh_highball)
        if not auth_validation['valid']:
            return auth_validation
        
        # Build origin configuration
        origin_config = {
            'origin_name': origin_name,
            'friendly_name': friendly_name,
            'ssh_hostname': ssh_hostname,
            'ssh_port': ssh_port,
            'ssh_timeout': ssh_timeout,
            'ssh_username': ssh_username,
            'ssh_highball': ssh_highball
        }
        
        # Add authentication-specific fields
        if ssh_highball:
            # Highball key mode - need transient password for setup
            ssh_password = safe_get_value(form_data, 'ssh_password')
            if not ssh_password:
                return {'valid': False, 'error': 'SSH password is required for Highball key installation'}
            origin_config['ssh_password'] = ssh_password  # Transient
        else:
            # User key mode - need public key and optional passphrase
            ssh_pubkey = safe_get_value(form_data, 'ssh_pubkey').strip()
            if not ssh_pubkey:
                return {'valid': False, 'error': 'SSH public key is required when not using Highball keys'}
            
            origin_config['ssh_pubkey'] = ssh_pubkey
            
            requires_passphrase = safe_get_value(form_data, 'requires_passphrase') == 'on'
            if requires_passphrase:
                ssh_passphrase = safe_get_value(form_data, 'ssh_passphrase')
                if not ssh_passphrase:
                    return {'valid': False, 'error': 'SSH key passphrase is required when "Requires passphrase" is checked'}
                origin_config['ssh_passphrase'] = ssh_passphrase
        
        return {'valid': True, 'origin_config': origin_config}
    
    @staticmethod
    def _validate_auth_config(form_data: Dict[str, Any], ssh_highball: bool) -> Dict[str, Any]:
        """Validate authentication configuration consistency"""
        if ssh_highball:
            # Highball mode: should not have user key fields filled
            ssh_pubkey = safe_get_value(form_data, 'ssh_pubkey').strip()
            if ssh_pubkey:
                return {'valid': False, 'error': 'Cannot specify SSH public key when using Highball keys'}
        else:
            # User key mode: should not have password filled
            ssh_password = safe_get_value(form_data, 'ssh_password')
            if ssh_password:
                return {'valid': False, 'error': 'Cannot specify SSH password when using user-managed keys'}
        
        return {'valid': True}

# =============================================================================
# EXPORTS - Clean interface
# =============================================================================

# Create instances for easy import
job_parser = JobFormParser()
source_parser = SourceParser()
destination_parser = DestinationParser()
notification_parser = NotificationParser()
maintenance_parser = MaintenanceParser()
source_paths_parser = SourcePathsParser()
origin_parser = OriginParser()