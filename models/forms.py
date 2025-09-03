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

# TRANSIENT DATA STRUCTURES MOVED TO jobs/handlers/old.py
# Will be deleted after job form rebuild to use dropdown selection

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

# DESTINATION PARSER MOVED TO dests/handlers/pages.py

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
        from origins.schema import SOURCE_TYPE_SCHEMAS
        
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
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        
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

# SSH ORIGIN PARSER MOVED TO origins/handlers/pages.py

# =============================================================================
# EXPORTS - Clean interface
# =============================================================================

# Create instances for easy import
job_parser = JobFormParser()
source_parser = SourceParser()
# destination_parser moved to dests/handlers/pages.py
notification_parser = NotificationParser()
maintenance_parser = MaintenanceParser()
source_paths_parser = SourcePathsParser()
# origin_parser moved to origins/handlers/pages.py