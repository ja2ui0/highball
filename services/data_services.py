"""
Unified Data Services
Consolidates form data building and snapshot introspection
Replaces: job_form_data_builder.py, snapshot_introspection_service.py
"""
from typing import Dict, List, Optional, Any
from models.forms import JobFormData, SourceConfig, DestConfig, ResticConfig, NotificationConfig
from models.backup import SOURCE_PATH_SCHEMA
from services.execution import ExecutionService


# =============================================================================
# **FORM DATA BUILDING CONCERN** - JobFormData creation and population
# =============================================================================

class JobFormDataBuilder:
    """Form data building - ONLY handles JobFormData creation from various sources"""
    
    def build_empty_form_data(self) -> Dict[str, Any]:
        """Building concern: create empty form data for new job creation"""
        return {
            'job_name': '',
            'source_type': 'local',
            'dest_type': 'local',
            'schedule': 'manual',
            'enabled': True,
            'respect_conflicts': True,
            'restic_maintenance': 'auto',
            'source_config': {},
            'dest_config': {},
            'restic_config': {},
            'notifications': [],
            'source_paths': [{'path': '', 'includes': [], 'excludes': []}],  # Start with one empty path
            'source_path_schema': SOURCE_PATH_SCHEMA,
            'page_title': 'Add Backup Job',
            'form_mode': 'add'
        }
    
    def build_form_data_from_job(self, job_name: str, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Building concern: create form data from existing job for editing"""
        form_data = self.from_job_config(job_name, job_config)
        
        # Extract source_paths from source_config
        source_config = job_config.get('source_config', {})
        source_paths = source_config.get('source_paths', [])
        
        return {
            'job_name': job_name,
            'source_type': job_config.get('source_type', 'local'),
            'dest_type': job_config.get('dest_type', 'local'),
            'schedule': job_config.get('schedule', 'manual'),
            'enabled': job_config.get('enabled', True),
            'respect_conflicts': job_config.get('respect_conflicts', True),
            'restic_maintenance': job_config.get('restic_maintenance', 'auto'),
            'source_config': source_config,
            'dest_config': job_config.get('dest_config', {}),
            'restic_config': self._build_restic_config(job_config.get('dest_type'), job_config.get('dest_config', {})),
            'notifications': job_config.get('notifications', []),
            'source_paths': source_paths,  # Extracted array for template iteration
            'source_path_schema': SOURCE_PATH_SCHEMA,
            'page_title': f'Edit Job: {job_name}',
            'form_mode': 'edit'
        }
    
    def build_form_data_with_error(self, form_data: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Building concern: create form data preserving user input with error message"""
        
        # Reconstruct source_paths array from form data
        source_paths = self._extract_source_paths_from_form(form_data)
        
        return {
            'job_name': form_data.get('job_name', [''])[0],
            'source_type': form_data.get('source_type', ['local'])[0],
            'dest_type': form_data.get('dest_type', ['local'])[0],
            'schedule': form_data.get('schedule', ['manual'])[0],
            'enabled': 'enabled' in form_data,
            'respect_conflicts': form_data.get('respect_conflicts', ['on'])[0] == 'on',
            'restic_maintenance': form_data.get('restic_maintenance', ['auto'])[0],
            'source_config': {},
            'dest_config': {},
            'restic_config': {},
            'notifications': [],
            'source_paths': source_paths,  # Preserve user input
            'source_path_schema': SOURCE_PATH_SCHEMA,
            'error_message': error_message,
            'page_title': 'Job Configuration Error',
            'form_mode': 'error'
        }
    
    def _extract_source_paths_from_form(self, form_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract source_paths array from form submission data"""
        source_paths = []
        
        # Get arrays from form data
        paths = form_data.get('source_path[]', [])
        includes = form_data.get('source_includes[]', [])
        excludes = form_data.get('source_excludes[]', [])
        
        # Build array of path objects
        for i in range(len(paths)):
            if i < len(paths) and paths[i].strip():  # Only include non-empty paths
                path_data = {
                    'path': paths[i],
                    'includes': includes[i].split('\n') if i < len(includes) and includes[i] else [],
                    'excludes': excludes[i].split('\n') if i < len(excludes) and excludes[i] else []
                }
                source_paths.append(path_data)
        
        return source_paths
    
    @classmethod
    def from_job_config(cls, job_name: str, job_config: Dict[str, Any]) -> JobFormData:
        """Building concern: create JobFormData from existing job configuration"""
        source_config = job_config.get('source_config', {})
        dest_config = job_config.get('dest_config', {})
        
        # Parse schedule
        schedule_type, cron_pattern = cls._parse_schedule(job_config.get('schedule', 'manual'))
        
        # Build structured configuration
        source = SourceConfig(
            source_type=job_config.get('source_type', ''),
            local_path=source_config.get('path', ''),
            ssh_hostname=source_config.get('hostname', ''),
            ssh_username=source_config.get('username', ''),
            ssh_path=source_config.get('path', ''),
            source_paths=source_config.get('source_paths', [])  # Multi-path support
        )
        
        dest = DestConfig(
            dest_type=job_config.get('dest_type', ''),
            local_path=dest_config.get('path', ''),
            ssh_hostname=dest_config.get('hostname', ''),
            ssh_username=dest_config.get('username', ''),
            ssh_path=dest_config.get('path', ''),
            rsyncd_hostname=dest_config.get('hostname', ''),
            rsyncd_share=dest_config.get('share', ''),
            rsync_options=dest_config.get('rsync_options', ''),
        )
        
        # Build Restic config only if needed
        restic = cls._build_restic_config(job_config.get('dest_type'), dest_config)
        
        # Build notification configs
        notifications = cls._build_notification_configs(job_config.get('notifications', []))
        
        return JobFormData(
            job_name=job_name,
            source_config=source,
            dest_config=dest,
            restic_config=restic,
            schedule=job_config.get('schedule', 'manual'),
            enabled=job_config.get('enabled', True),
            respect_conflicts=job_config.get('respect_conflicts', True),
            restic_maintenance=job_config.get('restic_maintenance', 'auto'),
            notifications=notifications
        )
    
    @classmethod
    def from_form_data(cls, form_data: Dict[str, Any]) -> JobFormData:
        """Building concern: create JobFormData from form submission"""
        # Parse schedule
        schedule = form_data.get('schedule', 'manual')
        if schedule == 'custom':
            cron_pattern = form_data.get('cron_pattern', '').strip()
            if cron_pattern:
                schedule = cron_pattern
        
        return JobFormData(
            job_name=form_data.get('job_name', ''),
            schedule=schedule,
            enabled=form_data.get('enabled', False),
            respect_conflicts=form_data.get('respect_conflicts', True),
            restic_maintenance=form_data.get('restic_maintenance', 'auto')
        )
    
    @classmethod
    def _parse_schedule(cls, schedule_value: str) -> tuple:
        """Building concern: parse schedule into type and pattern"""
        if not schedule_value or schedule_value in ['manual', 'hourly', 'daily', 'weekly', 'monthly']:
            return schedule_value or 'manual', ''
        else:
            # Custom cron pattern
            return 'custom', schedule_value
    
    @classmethod
    def _build_restic_config(cls, dest_type: str, dest_config: Dict[str, Any]) -> ResticConfig:
        """Building concern: build Restic configuration from destination config"""
        if dest_type != 'restic':
            return ResticConfig()
        
        # Extract Restic-specific configuration
        return ResticConfig(
            repo_type=dest_config.get('repo_type', ''),
            password=dest_config.get('password', ''),
            local_path=dest_config.get('local_path', ''),
            rest_hostname=dest_config.get('rest_hostname', ''),
            rest_port=dest_config.get('rest_port', '8000'),
            rest_path=dest_config.get('rest_path', ''),
            rest_use_https=dest_config.get('rest_use_https', True),
            s3_bucket=dest_config.get('s3_bucket', ''),
            s3_region=dest_config.get('s3_region', ''),
            s3_prefix=dest_config.get('s3_prefix', ''),
            s3_access_key=dest_config.get('s3_access_key', ''),
            s3_secret_key=dest_config.get('s3_secret_key', ''),
            s3_endpoint=dest_config.get('s3_endpoint', ''),
            sftp_hostname=dest_config.get('sftp_hostname', ''),
            sftp_path=dest_config.get('sftp_path', ''),
            rclone_config=dest_config.get('rclone_config', '')
        )
    
    @classmethod
    def _build_notification_configs(cls, notifications: List[Dict[str, Any]]) -> List[NotificationConfig]:
        """Building concern: build notification configurations"""
        configs = []
        for notification in notifications:
            config = NotificationConfig(
                provider_type=notification.get('provider', ''),
                notify_on_success=notification.get('notify_on_success', False),
                notify_on_failure=notification.get('notify_on_failure', True),
                success_message=notification.get('success_message', ''),
                failure_message=notification.get('failure_message', '')
            )
            configs.append(config)
        return configs


class ScheduleFormDataBuilder:
    """Service for building schedule form data structures"""
    
    def build_schedule_context(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build schedule form data structure for job forms
        
        Args:
            job_config: Job configuration dictionary (can be empty for add-job form)
            
        Returns:
            Dict containing schedule form fields: schedule, enabled, respect_conflicts
        """
        schedule = job_config.get('schedule', 'daily')
        enabled = job_config.get('enabled', True)
        respect_conflicts = job_config.get('respect_conflicts', True)
        
        return {
            'schedule': schedule,
            'enabled': enabled,
            'respect_conflicts': respect_conflicts
        }


class NotificationFormDataBuilder:
    """Service for building notification form data structures"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def build_notification_context(self, existing_notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build notification form data structure for job forms
        
        Args:
            existing_notifications: List of existing notification configurations (unused in current implementation)
            
        Returns:
            Dict containing notification form fields for all providers
        """
        from models.notifications import PROVIDER_FIELD_SCHEMAS
        
        # Get global notification settings from config
        global_settings = self.backup_config.get_global_settings()
        global_notification = global_settings.get('notification', {})
        
        # Build form data for each provider
        notification_data = {}
        
        for provider_name, schema in PROVIDER_FIELD_SCHEMAS.items():
            provider_config = global_notification.get(provider_name, {})
            
            # Process top-level fields
            for field_info in schema.get('fields', []):
                field_name = f"{provider_name}_{field_info['name']}"
                field_value = provider_config.get(field_info['name'], field_info.get('default', ''))
                
                if field_info['type'] == 'checkbox':
                    notification_data[field_name] = bool(field_value)
                else:
                    notification_data[field_name] = field_value
            
            # Process section fields
            if 'sections' in schema:
                for section in schema['sections']:
                    for field_info in section['fields']:
                        field_name = f"{provider_name}_{field_info['name']}"
                        field_value = provider_config.get(field_info['name'], field_info.get('default', ''))
                        
                        if field_info['type'] == 'checkbox':
                            notification_data[field_name] = bool(field_value)
                        elif field_info['type'] == 'select' and 'options' in field_info:
                            # Handle select fields with config_field mapping
                            selected_option = None
                            for option in field_info['options']:
                                if 'config_field' in option and provider_config.get(option['config_field']):
                                    selected_option = option['value']
                                    break
                            notification_data[field_name] = selected_option or field_info.get('default', '')
                        else:
                            notification_data[field_name] = field_value
        
        return notification_data


class JobFormTemplateBuilder:
    """Service for building complex job form template data and HTML"""
    
    def __init__(self, template_service):
        self.template_service = template_service
    
    def build_source_fields_html(self, source_type: str, source_config: Dict[str, Any]) -> str:
        """Build source-specific fields HTML"""
        from models.backup import SOURCE_TYPE_SCHEMAS
        
        if source_type not in SOURCE_TYPE_SCHEMAS:
            return ''
        
        schema = SOURCE_TYPE_SCHEMAS[source_type]
        
        # Check if this source type has additional fields requiring a template
        if schema.get('fields'):
            template_name = f'partials/source_{source_type}_fields.html'
            try:
                return self.template_service.render_template(
                    template_name,
                    **source_config
                )
            except Exception:
                # Template doesn't exist, no additional fields to render
                return ''
        else:
            # No additional fields needed (e.g., local)
            return ''
    
    def build_destination_fields_html(self, dest_type: str, dest_config: Dict[str, Any], form_data: Dict[str, Any]) -> str:
        """Build destination-specific fields HTML"""
        if dest_type == 'restic':
            return self._build_restic_destination_html(dest_config, form_data)
        else:
            return self._build_standard_destination_html(dest_type, dest_config)
    
    def _build_restic_destination_html(self, dest_config: Dict[str, Any], form_data: Dict[str, Any]) -> str:
        """Build complex restic destination fields HTML"""
        from models.backup import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
        # Get restic config 
        restic_config = form_data.get('restic_config', {})
        
        # Build repository type options
        available_repository_types = []
        for repo_type, schema in RESTIC_REPOSITORY_TYPE_SCHEMAS.items():
            available_repository_types.append({
                'value': repo_type,
                'display_name': schema['display_name']
            })
        
        # Get selected repository type and password
        selected_repo_type = dest_config.get('repo_type', '')
        restic_password = dest_config.get('password', '')
        
        # Build repository-specific fields for the selected type
        repo_fields_html = ''
        if selected_repo_type:
            repo_fields_html = self.template_service.render_template(
                'partials/restic_repo_fields_dynamic.html',
                repo_type=selected_repo_type,
                repo_schemas=RESTIC_REPOSITORY_TYPE_SCHEMAS,
                field_values=dest_config  # Pass the actual config values for pre-population
            )
        
        # Build the destination fields HTML for the selected type
        return self.template_service.render_template(
            'partials/job_form_dest_restic.html',
            restic_config=restic_config,
            available_repository_types=available_repository_types,
            selected_repo_type=selected_repo_type,
            restic_password=restic_password,
            repo_fields_html=repo_fields_html,  # Pre-rendered fields
            show_wrapper=False
        )
    
    def _build_standard_destination_html(self, dest_type: str, dest_config: Dict[str, Any]) -> str:
        """Build standard destination fields HTML using schemas"""
        from models.backup import DESTINATION_TYPE_SCHEMAS
        
        if dest_type not in DESTINATION_TYPE_SCHEMAS:
            return ''
        
        # Build template name from destination type
        template_name = f'partials/dest_{dest_type}_fields.html'
        
        try:
            # Use schema mapping to translate config field names to template field names
            schema = DESTINATION_TYPE_SCHEMAS[dest_type]
            template_values = {}
            
            if 'fields' in schema:
                for field_name, field_config in schema['fields'].items():
                    config_key = field_config.get('config_key', field_name)
                    template_values[field_name] = dest_config.get(config_key, '')
            
            return self.template_service.render_template(
                template_name,
                **template_values  # Pass mapped values for pre-population
            )
        except Exception:
            # Template doesn't exist, no fields to render
            return ''


# =============================================================================
# **SNAPSHOT INTROSPECTION CONCERN** - Discovery of paths and metadata from snapshots
# =============================================================================

class SnapshotIntrospectionService:
    """Snapshot introspection - ONLY handles discovery of snapshot contents and metadata"""
    
    def __init__(self):
        self.executor = ExecutionService()
        from services.execution import ResticExecutionService
        self.restic_executor = ResticExecutionService()
        self.timeout = 30  # seconds for introspection commands
    
    def get_snapshot_source_paths(
        self,
        snapshot_id: str,
        repository_url: str,
        dest_config: Dict[str, Any],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> List[str]:
        """Introspection concern: get original source paths that were backed up in a snapshot"""
        try:
            # Convert ssh_config to source_config format for ResticExecutionService
            source_config = None
            if ssh_config:
                source_config = {
                    'hostname': ssh_config['hostname'],
                    'username': ssh_config['username'],
                    'container_runtime': container_runtime
                }
            
            # Execute using unified ResticExecutionService
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=['ls', snapshot_id, '--long'],
                source_config=source_config,
                operation_type='ui',
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                return self._parse_snapshot_paths(result.stdout)
            else:
                print(f"WARNING: Failed to introspect snapshot {snapshot_id}: {result.stderr}")
                return []
                
        except Exception as e:
            print(f"ERROR: Snapshot introspection failed for {snapshot_id}: {str(e)}")
            return []
    
    def get_snapshot_metadata(
        self,
        snapshot_id: str,
        repository_url: str,
        dest_config: Dict[str, Any],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> Dict[str, Any]:
        """Introspection concern: get detailed metadata for a snapshot"""
        try:
            # Convert ssh_config to source_config format for ResticExecutionService
            source_config = None
            if ssh_config:
                source_config = {
                    'hostname': ssh_config['hostname'],
                    'username': ssh_config['username'],
                    'container_runtime': container_runtime
                }
            
            # Execute using unified ResticExecutionService
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=['snapshots', '--json', snapshot_id],
                source_config=source_config,
                operation_type='ui',
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                import json
                snapshots = json.loads(result.stdout)
                if snapshots and len(snapshots) > 0:
                    return snapshots[0]
            
            return {}
            
        except Exception as e:
            print(f"ERROR: Snapshot metadata retrieval failed for {snapshot_id}: {str(e)}")
            return {}
    
    
    def _parse_snapshot_paths(self, ls_output: str) -> List[str]:
        """Introspection concern: parse restic ls output to extract original source paths"""
        paths = []
        lines = ls_output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            # Parse restic ls --long output
            # Format: permissions size date time path
            parts = line.split()
            if len(parts) >= 5:
                # The path is the last part
                path = ' '.join(parts[4:])
                
                # Only include top-level directories as source paths
                if path and not path.startswith('.'):
                    # Remove leading slash and extract top-level directory
                    clean_path = path.lstrip('/')
                    if '/' in clean_path:
                        top_level = '/' + clean_path.split('/')[0]
                    else:
                        top_level = '/' + clean_path
                    
                    if top_level not in paths:
                        paths.append(top_level)
        
        return sorted(paths)


# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates form building and introspection
# =============================================================================

class DataService:
    """Unified data service - ONLY coordinates form building and introspection concerns"""
    
    def __init__(self):
        self.form_builder = JobFormDataBuilder()
        self.introspection = SnapshotIntrospectionService()
    
    # **FORM BUILDING DELEGATION** - Pure delegation to building concern
    def build_job_form_data_from_config(self, job_name: str, job_config: Dict[str, Any]) -> JobFormData:
        """Delegation: build form data from job config"""
        return self.form_builder.from_job_config(job_name, job_config)
    
    def build_job_form_data_from_form(self, form_data: Dict[str, Any]) -> JobFormData:
        """Delegation: build form data from form submission"""
        return self.form_builder.from_form_data(form_data)
    
    # **INTROSPECTION DELEGATION** - Pure delegation to introspection concern
    def get_snapshot_source_paths(
        self,
        snapshot_id: str,
        repository_url: str,
        dest_config: Dict[str, Any],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> List[str]:
        """Delegation: get snapshot source paths"""
        return self.introspection.get_snapshot_source_paths(
            snapshot_id, repository_url, dest_config, ssh_config, container_runtime
        )
    
    def get_snapshot_metadata(
        self,
        snapshot_id: str,
        repository_url: str,
        dest_config: Dict[str, Any],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> Dict[str, Any]:
        """Delegation: get snapshot metadata"""
        return self.introspection.get_snapshot_metadata(
            snapshot_id, repository_url, dest_config, ssh_config, container_runtime
        )


# =============================================================================
# DESTINATION TYPE SERVICE - following notification service pattern
# =============================================================================

class DestinationTypeService:
    """Service for managing destination type availability and options"""
    
    def get_available_destination_types(self, source_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get list of available destination types with their metadata"""
        from models.backup import DESTINATION_TYPE_SCHEMAS
        
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
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error checking restic availability: {e}")
            return False

class ResticRepositoryTypeService:
    """Service for managing restic repository type availability and options"""
    
    def get_available_repository_types(self) -> List[Dict[str, Any]]:
        """Get list of available restic repository types with their metadata"""
        from models.backup import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
        available_types = []
        
        for repo_type, schema in RESTIC_REPOSITORY_TYPE_SCHEMAS.items():
            if self._is_repository_type_available(repo_type, schema):
                available_types.append({
                    'value': repo_type,
                    'display_name': schema['display_name'],
                    'description': schema['description']
                })
        
        return available_types
    
    def _is_repository_type_available(self, repo_type: str, schema: Dict[str, Any]) -> bool:
        """Check if a repository type is available"""
        # All repository types are always available - no special requirements
        return schema.get('always_available', True)