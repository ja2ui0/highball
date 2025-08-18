"""
Consolidated Form Parsing Module
Merges all form parsers into single module with clean class-based organization
Replaces: job_form_parser.py, ssh_form_parser.py, restic_form_parser.py, local_form_parser.py, 
         rsyncd_form_parser.py, notification_form_parser.py, maintenance_form_parser.py
Also includes form data structures moved from services/form_data_service.py
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# **FORM DATA STRUCTURES** - Configuration dataclasses for form handling
# =============================================================================

@dataclass
class SourceConfig:
    """Form concern: source configuration data structure"""
    source_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    
    # Multi-path support
    source_paths: list = field(default_factory=list)


@dataclass  
class DestConfig:
    """Form concern: standard destination configuration data structure"""
    dest_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    rsyncd_hostname: str = ""
    rsyncd_share: str = ""
    rsync_options: str = ""


@dataclass
class ResticConfig:
    """Form concern: Restic repository configuration data structure"""
    repo_type: str = ""
    password: str = ""
    
    # Repository type specific fields
    local_path: str = ""
    
    # REST fields
    rest_hostname: str = ""
    rest_port: str = "8000"
    rest_path: str = ""
    rest_use_https: bool = True
    
    # S3 fields
    s3_bucket: str = ""
    s3_region: str = ""
    s3_prefix: str = ""
    
    # SFTP fields
    sftp_hostname: str = ""
    sftp_path: str = ""
    
    # Rclone fields
    rclone_config: str = ""


@dataclass
class NotificationConfig:
    """Form concern: notification provider configuration data structure"""
    provider_type: str = ""
    notify_on_success: bool = False
    notify_on_failure: bool = True
    success_message: str = ""
    failure_message: str = ""


@dataclass
class JobFormData:
    """Form concern: complete job form data structure"""
    job_name: str = ""
    source_config: SourceConfig = field(default_factory=SourceConfig)
    dest_config: DestConfig = field(default_factory=DestConfig)
    restic_config: ResticConfig = field(default_factory=ResticConfig)
    schedule: str = ""
    enabled: bool = True
    respect_conflicts: bool = True
    auto_maintenance: bool = True
    notifications: List[NotificationConfig] = field(default_factory=list)

# =============================================================================
# UTILITY FUNCTIONS - Common form parsing helpers
# =============================================================================

def safe_get_list(data, key):
    """Safely get list from form data regardless of format"""
    if hasattr(data, 'getlist'):
        return data.getlist(key)
    else:
        value = data.get(key, [])
        return value if isinstance(value, list) else [value]

def safe_get_value(data, key, default=''):
    """Safely get single value from form data"""
    values = safe_get_list(data, key)
    return values[0] if values and values[0] else default

def parse_lines(text):
    """Parse textarea input into list of non-empty lines"""
    return [line.strip() for line in text.split('\n') if line.strip()]

# =============================================================================
# SOURCE CONFIGURATION PARSERS
# =============================================================================

class SourceParser:
    """Parse source configurations (SSH, local)"""
    
    @staticmethod
    def parse_ssh_source(form_data):
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
    def parse_local_source(form_data):
        """Parse local source configuration"""
        # Local sources need minimal configuration
        return {'valid': True, 'config': {}}

# =============================================================================
# DESTINATION CONFIGURATION PARSERS  
# =============================================================================

class DestinationParser:
    """Parse destination configurations (SSH, local, rsyncd, restic)"""
    
    @staticmethod
    def parse_ssh_destination(form_data):
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
    def parse_local_destination(form_data):
        """Parse local destination configuration"""
        path = safe_get_value(form_data, 'dest_path')
        
        if not path:
            return {'valid': False, 'error': 'Local destination path is required'}
        
        config = {'path': path.strip()}
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_rsyncd_destination(form_data):
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
    def parse_restic_destination(form_data):
        """Parse Restic destination configuration with all repository types"""
        repo_type = safe_get_value(form_data, 'repo_type')
        password = safe_get_value(form_data, 'restic_password')
        
        if not repo_type:
            return {'valid': False, 'error': 'Repository type is required'}
        if not password:
            return {'valid': False, 'error': 'Repository password is required'}
        
        # Generate repository URI based on type
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        if not uri_result['valid']:
            return uri_result
        
        config = {
            'repo_type': repo_type,
            'repo_uri': uri_result['uri'],
            'password': password
        }
        
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
            repo_name = safe_get_value(form_data, 'rest_repo_name')
            
            if not hostname:
                return {'valid': False, 'error': 'REST server hostname is required'}
            if not repo_name:
                return {'valid': False, 'error': 'REST repository name is required'}
            
            return {'valid': True, 'uri': f'rest:http://{hostname}:{port}/{repo_name}'}
            
        elif repo_type == 's3':
            bucket = safe_get_value(form_data, 's3_bucket')
            prefix = safe_get_value(form_data, 's3_prefix', '')
            
            if not bucket:
                return {'valid': False, 'error': 'S3 bucket name is required'}
            
            uri = f's3:{bucket}'
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
        
        else:
            return {'valid': False, 'error': f'Unknown repository type: {repo_type}'}

# =============================================================================
# SOURCE PATHS PARSER
# =============================================================================

class SourcePathsParser:
    """Parse multi-path source configurations"""
    
    @staticmethod
    def parse_multi_path_options(form_data):
        """Parse multi-path source options from form data"""
        source_paths = safe_get_list(form_data, 'source_paths[]')
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
    def parse_notification_config(form_data):
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
    def parse_maintenance_config(form_data):
        """Parse maintenance configuration from form data"""
        auto_maintenance = 'auto_maintenance' in form_data
        
        # Default maintenance config if auto-maintenance is enabled
        if auto_maintenance:
            maintenance_config = {
                'auto_maintenance': True,
                # Could add custom schedules here if form provides them
                # 'discard_schedule': safe_get_value(form_data, 'maintenance_discard_schedule'),
                # 'check_schedule': safe_get_value(form_data, 'maintenance_check_schedule'),
            }
        else:
            maintenance_config = {'auto_maintenance': False}
        
        return {'valid': True, 'maintenance_config': maintenance_config}

# =============================================================================
# UNIFIED JOB PARSER - Main entry point
# =============================================================================

class JobFormParser:
    """Unified job form parser - single entry point for all form parsing"""
    
    @staticmethod
    def parse_job_form(form_data):
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
        if schedule == 'cron':
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
    def parse_source_configuration(form_data):
        """Parse complete source configuration including paths"""
        source_type = safe_get_value(form_data, 'source_type')
        if not source_type:
            return {'valid': False, 'error': 'Source type is required'}
        
        # Parse basic source config (connection details)
        if source_type == 'local':
            source_result = SourceParser.parse_local_source(form_data)
        elif source_type == 'ssh':
            source_result = SourceParser.parse_ssh_source(form_data)
        else:
            return {'valid': False, 'error': f'Unknown source type: {source_type}'}
        
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
    def parse_destination_configuration(form_data):
        """Parse destination configuration"""
        dest_type = safe_get_value(form_data, 'dest_type')
        if not dest_type:
            return {'valid': False, 'error': 'Destination type is required'}
        
        if dest_type == 'local':
            dest_result = DestinationParser.parse_local_destination(form_data)
        elif dest_type == 'ssh':
            dest_result = DestinationParser.parse_ssh_destination(form_data)
        elif dest_type == 'rsyncd':
            dest_result = DestinationParser.parse_rsyncd_destination(form_data)
        elif dest_type == 'restic':
            dest_result = DestinationParser.parse_restic_destination(form_data)
        else:
            return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}
        
        if not dest_result['valid']:
            return dest_result
        
        dest_config = dest_result['config']
        dest_config['dest_type'] = dest_type
        
        return {'valid': True, 'config': dest_config}

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