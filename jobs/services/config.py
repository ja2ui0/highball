"""
Jobs Config Service
Handle job CRUD operations with deleted/restore logic (compat mode)
"""

import os
import glob
import yaml
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List

from shared.services.config import ConfigIOService, ConfigReader
from models.forms import safe_get_value, safe_get_list, parse_lines


# =============================================================================
# JOB FORM PARSERS - moved from handlers
# =============================================================================

class SourceParser:
    """Parse source configurations (SSH, local) - moved from old.py"""

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


class JobFormParser:
    """Unified job form parser - moved from old.py"""

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
            from dests.handlers.pages import MaintenanceParser
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
        from dests.handlers.pages import DestinationParser
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

class NotificationParser:
    """Parse notification provider configurations - moved verbatim from handler"""

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


class SourcePathsParser:
    """Parse multi-path source configurations - moved verbatim from handler"""

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


class JobConfigService:
    """Handle job configuration CRUD operations"""

    def __init__(self):
        self.shared = ConfigIOService()
        self.config_reader = ConfigReader()

    def get_backup_jobs(self) -> Dict[str, Any]:
        """Get all backup jobs - read directly from disk for real-time updates"""
        return self.config_reader.get_backup_jobs()

    def get_backup_job(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get specific backup job - read directly from disk"""
        return self.config_reader.get_backup_job(job_name)

    def add_backup_job(self, job_name: str, job_config: Dict[str, Any]) -> bool:
        """Add or update a backup job using new file hierarchy"""
        return self.save_job(job_name, job_config)

    def save_job(self, job_name: str, job_config: Dict[str, Any]) -> bool:
        """Save a backup job config file"""
        try:
            # Ensure directory exists
            jobs_dir = "/config/local/jobs"
            os.makedirs(jobs_dir, exist_ok=True)

            # Write config file atomically
            config_file = f"/config/local/jobs/{job_name}.yaml"
            self.shared.save_yaml(config_file, job_config)

            return True

        except Exception as e:
            print(f"Error saving job {job_name}: {str(e)}")
            return False

    def delete_backup_job(self, job_name: str) -> bool:
        """Delete a backup job (move files to deleted/ subdirectories)"""
        try:
            # Check if job exists
            jobs = self._load_backup_jobs()
            if job_name not in jobs:
                return False

            # Ensure deleted directory exists
            deleted_jobs_dir = "/config/local/jobs/deleted"
            os.makedirs(deleted_jobs_dir, exist_ok=True)

            # File paths
            config_file = f"/config/local/jobs/{job_name}.yaml"
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"

            # Add deleted_on timestamp to job config
            if os.path.exists(config_file):
                job_config = self.shared.load_yaml(config_file)
                if job_config:
                    job_config['deleted_on'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

                    # Write updated config to deleted location
                    self.shared.save_yaml(deleted_config_file, job_config)

                    # Remove original config file
                    os.remove(config_file)

            return True

        except Exception as e:
            print(f"Error deleting job {job_name}: {str(e)}")
            return False

    def restore_deleted_job(self, job_name: str) -> bool:
        """Restore a deleted job (move files back from deleted/ subdirectories)"""
        try:
            # Check if deleted job exists
            deleted_jobs = self._load_deleted_jobs()
            if job_name not in deleted_jobs:
                return False

            # Check if job name conflicts with existing active job
            active_jobs = self._load_backup_jobs()
            if job_name in active_jobs:
                print(f"Error: Job name '{job_name}' already exists in active jobs")
                return False

            # File paths
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"
            config_file = f"/config/local/jobs/{job_name}.yaml"

            # Restore config file
            if os.path.exists(deleted_config_file):
                job_config = self.shared.load_yaml(deleted_config_file)
                if job_config:
                    # Remove deleted_on timestamp
                    if 'deleted_on' in job_config:
                        del job_config['deleted_on']

                    # Write restored config to active location
                    self.shared.save_yaml(config_file, job_config)

                    # Remove from deleted location
                    os.remove(deleted_config_file)

            return True

        except Exception as e:
            print(f"Error restoring job {job_name}: {str(e)}")
            return False

    def purge_job(self, job_name: str) -> bool:
        """Permanently delete a job from deleted/ directories (irreversible)"""
        try:
            # Check if deleted job exists
            deleted_jobs = self._load_deleted_jobs()
            if job_name not in deleted_jobs:
                return False

            # File path for deleted job
            deleted_config_file = f"/config/local/jobs/deleted/{job_name}.yaml"

            # Remove config file
            if os.path.exists(deleted_config_file):
                os.remove(deleted_config_file)

            return True

        except Exception as e:
            print(f"Error purging job {job_name}: {str(e)}")
            return False

    def get_deleted_jobs(self) -> Dict[str, Any]:
        """Get all deleted jobs"""
        return self.config_reader.get_deleted_jobs()

    # =========================================================================
    # RESPONSE ORCHESTRATION - business logic moved from handlers
    # =========================================================================

    def delete_backup_job_with_response(self, job_name: str) -> Dict[str, Any]:
        """Delete backup job and return appropriate response data"""
        if not job_name:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': 'Job name is required'
                },
                'status_code': 400
            }

        success = self.delete_backup_job(job_name)
        if success:
            return {
                'type': 'redirect',
                'url': '/dashboard',
                'status_code': 302
            }
        else:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': f"Failed to delete job '{job_name}'"
                },
                'status_code': 500
            }

    def purge_backup_job_with_response(self, job_name: str) -> Dict[str, Any]:
        """Purge backup job and return appropriate response data"""
        if not job_name:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': 'Job name is required'
                },
                'status_code': 400
            }

        success = self.purge_job(job_name)
        if success:
            return {
                'type': 'redirect',
                'url': '/dashboard',
                'status_code': 302
            }
        else:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': f"Failed to purge job '{job_name}'"
                },
                'status_code': 500
            }

    def restore_backup_job_with_response(self, job_name: str) -> Dict[str, Any]:
        """Restore backup job and return appropriate response data"""
        if not job_name:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': 'Job name is required'
                },
                'status_code': 400
            }

        success = self.restore_deleted_job(job_name)
        if success:
            return {
                'type': 'redirect',
                'url': '/dashboard',
                'status_code': 302
            }
        else:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': f"Failed to restore job '{job_name}'"
                },
                'status_code': 500
            }

    # =========================================================================
    # FORM-BASED JOB OPERATIONS - business logic moved from handlers
    # =========================================================================

    def save_backup_job_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save backup job from form submission - business logic moved verbatim from handler"""
        job_parser = JobFormParser()

        # Parse job form data using unified parser
        job_result = job_parser.parse_job_form(form_data)

        if not job_result['valid']:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': job_result['error']
                },
                'status_code': 400
            }

        # Build and save job configuration
        job_name = job_result['job_name']
        job_config = self._build_job_config_from_result(job_result)

        # Save via service
        success = self.save_job(job_name, job_config)
        if success:
            result = {'success': True, 'message': f"Job '{job_name}' saved successfully"}
        else:
            result = {'success': False, 'error': 'Failed to save job configuration'}

        if result['success']:
            return {
                'type': 'redirect',
                'url': '/dashboard',
                'status_code': 302
            }
        else:
            return {
                'type': 'json',
                'content': {
                    'success': False,
                    'error': result['error']
                },
                'status_code': 500
            }

    def _build_job_config_from_result(self, job_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build job configuration from parsed form result - moved verbatim from handler"""
        job_config = {
            'source_type': job_result['source_type'],
            'source_config': job_result['source_config'],
            'dest_type': job_result['dest_type'],
            'dest_config': job_result['dest_config'],
            'schedule': job_result['schedule'],
            'enabled': job_result['enabled'],
            'respect_conflicts': job_result['respect_conflicts'],
            'notifications': job_result['notifications']
        }

        # Add maintenance config if present
        if 'maintenance_config' in job_result:
            job_config['maintenance_config'] = job_result['maintenance_config']

        return job_config

    def validate_source_paths_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate source paths from form - business logic moved verbatim from handler"""
        # Parse source paths from form
        # SourcePathsParser is now local to this module
        paths_result = SourcePathsParser.parse_multi_path_options(form_data)

        if not paths_result['valid']:
            return paths_result

        # Build SSH configuration and validate paths
        source_type = form_data.get('source_type', ['local'])[0]
        ssh_config = self._build_ssh_config_from_form(form_data) if source_type == 'ssh' else {}
        validation_results = self._validate_individual_paths(source_type, paths_result['source_paths'], ssh_config)

        return {
            'valid': True,
            'results': validation_results
        }

    def _build_ssh_config_from_form(self, form_data: Dict[str, Any]) -> Dict[str, str]:
        """Build SSH configuration from form data - moved verbatim from handler"""
        hostname = form_data.get('hostname', [''])[0]
        username = form_data.get('username', [''])[0]
        return {'hostname': hostname, 'username': username}

    def _validate_individual_paths(self, source_type: str, source_paths: List[Dict[str, Any]], ssh_config: Dict[str, str]) -> List[Dict[str, Any]]:
        """Validate each individual source path - moved verbatim from handler"""
        from jobs.services.validate import ValidationService

        validation_service = ValidationService()

        validation_results = []
        for path_config in source_paths:
            if source_type == 'ssh':
                result = validation_service.validate_source_path(ssh_config, path_config['path'])
            else:
                result = validation_service.validate_source_path({}, path_config['path'])

            validation_results.append({
                'path': path_config['path'],
                'valid': result['valid'],
                'error': result.get('error'),
                'permissions': result.get('permissions')
            })

        return validation_results

    def _get_form_providers(self, form_data):
        """Get currently configured providers from form data - moved verbatim from handler"""
        providers = form_data.get('notification_providers[]', [])
        # Handle both single string and list formats
        if isinstance(providers, str):
            return [providers] if providers else []
        return [p for p in providers if p]  # Filter out empty strings


    def validate_source_path_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate source path with robust permission checking for HTMX forms - moved verbatim from handler"""
        from models.forms import safe_get_value, safe_get_list

        # Extract path from array format
        path_array = form_data.get('source_path[]', [])
        path_index = int(safe_get_value(form_data, 'path_index', '0'))
        path = path_array[path_index] if path_index < len(path_array) else ''

        if not path or not path.strip():
            result = {'valid': False, 'error': 'Please enter a path'}
            return result

        # Extract source configuration
        source_type = safe_get_value(form_data, 'source_type')
        hostname = safe_get_value(form_data, 'hostname')
        username = safe_get_value(form_data, 'username')

        # Validate based on source type (robust handling from working version)
        from jobs.services.validate import ValidationService
        validation_service = ValidationService()

        if source_type == 'ssh':
            result = validation_service.validate_source_path_for_backup_ssh(hostname, username, path)
        elif source_type == 'local':
            result = validation_service.validate_source_path_for_backup_local(path)
        else:
            result = {'valid': False, 'error': 'Please select a source type (Local Path or SSH Remote)'}

        return result

    def add_source_path_entry_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new source path entry for HTMX forms - moved verbatim from handler"""
        from models.forms import safe_get_value
        from origins.schema import SOURCE_PATH_SCHEMA

        # Get path count from JavaScript via hx-vals
        path_count = int(safe_get_value(form_data, 'path_count', '0'))
        new_path_index = path_count  # Next sequential index

        # Create new empty path data
        path_data = {'path': '', 'includes': [], 'excludes': []}
        source_paths = ['', '']  # Always show remove button for new paths

        return {
            'path_index': new_path_index,
            'path_data': path_data,
            'source_paths': source_paths,
            'source_path_schema': SOURCE_PATH_SCHEMA
        }


