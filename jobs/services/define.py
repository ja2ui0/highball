"""
Job Definition Services
Handles job configuration building and form data structures
"""
from typing import Dict, List, Optional, Any
from jobs.handlers.old import JobFormData, SourceConfig, DestConfig, ResticConfig
from origins.schema import SOURCE_PATH_SCHEMA


# =============================================================================
# **JOB FORM DATA BUILDING** - JobFormData creation from various sources
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
    def _build_notification_configs(cls, notifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Building concern: build notification configurations"""
        configs = []
        for notification in notifications:
            config = {
                'provider_type': notification.get('provider', ''),
                'notify_on_success': notification.get('notify_on_success', False),
                'notify_on_failure': notification.get('notify_on_failure', True),
                'success_message': notification.get('success_message', ''),
                'failure_message': notification.get('failure_message', '')
            }
            configs.append(config)
        return configs


# =============================================================================
# **JOB FORM TEMPLATE BUILDING** - Complex job form template data and HTML
# =============================================================================

class JobFormTemplateBuilder:
    """Service for building complex job form template data and HTML"""
    
    def __init__(self, template_service):
        self.template_service = template_service
    
    def build_source_fields_html(self, source_type: str, source_config: Dict[str, Any]) -> str:
        """Build source-specific fields HTML"""
        from origins.schema import SOURCE_TYPE_SCHEMAS
        
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
        from dests.schema import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
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
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        
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
# **JOB DISPLAY BUILDING** - Complex job display data building moved from handlers
# =============================================================================

class JobDisplayBuilder:
    """Service for building complex job display data structures - moved verbatim from handler"""

    def __init__(self, template_service):
        self.template_service = template_service
        from shared.services.config import ConfigReader
        self.config_reader = ConfigReader()

    def build_job_rows(self, jobs):
        """Build job table rows from job data - moved verbatim from handler"""
        if not jobs:
            return self.template_service.load_template('partials/empty_job_rows.html')

        rows = []
        for job in jobs:
            row_html = self.template_service.render_template('partials/job_row.html',
                job_name=job['name'],
                source_display=job['source_display'],
                dest_display=job['dest_display'],
                status_class=job['status_class'],
                status_text=job['status'],
                schedule=job['schedule']
            )
            rows.append(row_html)

        return '\n'.join(rows)

    def build_deleted_job_rows(self, deleted_jobs):
        """Build deleted job table rows from deleted jobs data - moved verbatim from handler"""
        if not deleted_jobs:
            return self.template_service.load_template('partials/empty_deleted_rows.html')

        rows = []
        for job_name, job_config in deleted_jobs.items():
            # Build source and destination displays same way as active jobs
            source_display = self.build_source_display_with_type(job_config)
            dest_display = self.build_dest_display_with_type(job_config)

            # Format deleted_at timestamp (break into date and time)
            deleted_at_raw = job_config.get('deleted_at', 'Unknown')
            if deleted_at_raw != 'Unknown' and ' ' in deleted_at_raw:
                # Split "2025-08-20 14:30:45" into "2025-08-20\n14:30:45"
                date_part, time_part = deleted_at_raw.split(' ', 1)
                deleted_at = f"{date_part}\n{time_part}"
            else:
                deleted_at = deleted_at_raw

            row_html = self.template_service.render_template('partials/deleted_job_row.html',
                job_name=job_name,
                source_display=source_display,
                dest_display=dest_display,
                deleted_at=deleted_at
            )
            rows.append(row_html)

        return '\n'.join(rows)

    def build_source_display_with_type(self, job_config):
        """Build source display string with type prefix - moved verbatim from handler"""
        source_type = job_config.get('source_type', 'local')
        source_config = job_config.get('source_config', {})

        if source_type == 'local':
            # Local source - show paths
            source_paths = source_config.get('source_paths', [])
            if source_paths:
                first_path = source_paths[0]
                if isinstance(first_path, dict):
                    path_display = first_path.get('path', 'Unknown')
                else:
                    path_display = str(first_path)

                if len(source_paths) > 1:
                    path_display += f" (+{len(source_paths)-1})"
            else:
                path_display = "No paths configured"
            return f"local: {path_display}"

        elif source_type == 'ssh':
            # SSH source - show hostname and paths
            hostname = source_config.get('hostname', 'unknown')
            username = source_config.get('username', 'unknown')
            source_paths = source_config.get('source_paths', [])

            if source_paths:
                first_path = source_paths[0]
                if isinstance(first_path, dict):
                    path_display = first_path.get('path', 'Unknown')
                else:
                    path_display = str(first_path)

                if len(source_paths) > 1:
                    path_display += f" (+{len(source_paths)-1})"
            else:
                path_display = "No paths configured"

            return f"ssh: {username}@{hostname}:{path_display}"

        return f"{source_type}: Unknown configuration"

    def build_dest_display_with_type(self, job_config):
        """Build destination display string with type prefix - moved verbatim from handler"""
        dest_type = job_config.get('dest_type', 'local')
        dest_config = job_config.get('dest_config', {})

        if dest_type == 'local':
            path = dest_config.get('path', 'Unknown')
            return f"local: {path}"

        elif dest_type == 'ssh':
            hostname = dest_config.get('hostname', 'unknown')
            path = dest_config.get('path', 'unknown')
            return f"ssh: {hostname}:{path}"

        elif dest_type == 'rsyncd':
            hostname = dest_config.get('hostname', 'unknown')
            share = dest_config.get('share', 'unknown')
            return f"rsyncd: {hostname}::{share}"

        elif dest_type == 'restic':
            repo_type = dest_config.get('repo_type', 'local')
            repo_uri = dest_config.get('repo_uri', 'Unknown')

            # Show just the repo type and a simplified URI
            if repo_type == 'local':
                return f"restic: local:{repo_uri}"
            elif repo_type == 'rest':
                return f"restic: rest-server"
            elif repo_type == 's3':
                return f"restic: s3-bucket"
            elif repo_type == 'sftp':
                return f"restic: sftp"
            elif repo_type == 'rclone':
                return f"restic: rclone"
            elif repo_type == 'same_as_origin':
                return f"restic: same-as-origin"
            else:
                return f"restic: {repo_type}"

        return f"{dest_type}: Unknown configuration"

    def build_dashboard_display_data(self) -> Dict[str, Any]:
        """Build complete dashboard display data - business logic moved from handler"""
        from shared.services.config import ConfigReader
        config_reader = ConfigReader()

        # Get data directly using ConfigReader
        jobs = config_reader.get_backup_jobs()
        deleted_jobs = config_reader.get_deleted_jobs()

        # Build job list for display
        job_list = []
        for job_name, job_config in jobs.items():
            # Use enabled/disabled status like original, not execution status
            enabled = job_config.get('enabled', True)
            status = "enabled" if enabled else "disabled"
            status_class = "status-success" if enabled else "status-error"

            # Build display strings with type prefixes
            source_display = self.build_source_display_with_type(job_config)
            dest_display = self.build_dest_display_with_type(job_config)

            job_display = {
                'name': job_name,
                'source_display': source_display,
                'dest_display': dest_display,
                'status': status.capitalize(),
                'status_class': status_class,
                'schedule': job_config.get('schedule', 'manual')
            }
            job_list.append(job_display)

        # Sort jobs by name
        job_list.sort(key=lambda j: j['name'])

        # Build HTML rows
        job_rows = self.build_job_rows(job_list)
        deleted_job_rows = self.build_deleted_job_rows(deleted_jobs)

        return {
            'job_list': job_list,
            'jobs': jobs,
            'deleted_jobs': deleted_jobs,
            'job_count': len(jobs),
            'deleted_count': len(deleted_jobs),
            'global_settings': config_reader.get_global_settings(),
            'job_rows': job_rows,
            'deleted_job_rows': deleted_job_rows
        }

    def build_edit_job_form_data(self, job_name: str) -> Dict[str, Any]:
        """Build edit job form data with complete business logic - moved from handler"""
        from shared.services.config import ConfigReader
        from jobs.services.define import JobFormDataBuilder
        from jobs.services.manage import JobOperationsService
        from dests.services.kinds import DestinationTypeService

        config_reader = ConfigReader()
        jobs = config_reader.get_backup_jobs()

        if job_name not in jobs:
            return {
                'found': False,
                'error': f"Job '{job_name}' not found"
            }

        job_config = jobs[job_name]
        job_form_builder = JobFormDataBuilder()
        form_data = job_form_builder.build_form_data_from_job(job_name, job_config)

        # Add edit-specific metadata
        form_data['page_title'] = f'Edit Job: {job_name}'
        form_data['form_title'] = f'Edit Backup Job: {job_name}'
        form_data['submit_button_text'] = 'Commit Changes'
        form_data['form_has_changes'] = False

        # Store original config for change detection
        job_operations = JobOperationsService()
        form_data['original_job_config'] = job_operations.serialize_job_config(job_config)

        # Add available destination types
        source_config = job_config.get('source_config', {})
        destination_service = DestinationTypeService()
        form_data['available_destination_types'] = destination_service.get_available_destination_types(source_config)

        # Pre-select source and destination types for edit mode
        source_type = job_config.get('source_type', 'local')
        form_data['selected_source_type'] = source_type
        form_data['source_local_selected'] = (source_type == 'local')
        form_data['source_ssh_selected'] = (source_type == 'ssh')
        form_data['selected_dest_type'] = job_config.get('dest_type', 'local')

        # Build source and destination fields HTML using template builder
        from jobs.services.define import JobFormTemplateBuilder
        template_builder = JobFormTemplateBuilder(self.template_service)
        form_data['source_fields_html'] = template_builder.build_source_fields_html(source_type, source_config)

        dest_type = job_config.get('dest_type', 'local')
        dest_config = job_config.get('dest_config', {})
        form_data['dest_fields_html'] = template_builder.build_destination_fields_html(dest_type, dest_config, form_data)

        # Add notification and schedule form data
        existing_notifications = job_config.get('notifications', [])
        form_data.update(self._build_notification_form_data_helper(existing_notifications))
        form_data.update(self._build_schedule_form_data_helper(job_config))

        return {
            'found': True,
            'form_data': form_data
        }

    def _build_notification_form_data_helper(self, existing_notifications):
        """Helper for notification form data building"""
        from jobs.services.notify import NotificationFormDataBuilder
        builder = NotificationFormDataBuilder()
        return builder.build_notification_context(existing_notifications)

    def _build_schedule_form_data_helper(self, job_config):
        """Helper for schedule form data building"""
        from jobs.services.schedule import ScheduleFormDataBuilder
        builder = ScheduleFormDataBuilder()
        return builder.build_schedule_context(job_config)

    def build_job_inspect_data(self, job_name: str) -> Dict[str, Any]:
        """Build job inspection data with complete business logic - moved from handler"""
        from shared.services.config import ConfigReader
        from jobs.services.manage import JobManagementService

        config_reader = ConfigReader()
        jobs = config_reader.get_backup_jobs()

        if job_name not in jobs:
            return {
                'found': False,
                'error': f"Job '{job_name}' not found"
            }

        job_config = jobs[job_name]

        # Get job status and logs
        job_management = JobManagementService()
        status_info = job_management.get_status(job_name)
        recent_logs = job_management.get_log_entries(job_name, max_lines=100)

        # Format log content as string
        job_log_content = '\n'.join(recent_logs) if recent_logs else f'No log file yet for job "{job_name}". Job has not been executed (test or run) since creation.'

        return {
            'found': True,
            'job_name': job_name,
            'job_type': job_config.get('dest_type', 'unknown'),
            'last_run': status_info.get('last_updated', 'Never'),
            'status': status_info.get('status', 'No runs'),
            'message': status_info.get('details', 'No message'),
            'job_log_content': job_log_content
        }

    def build_add_job_form_data(self) -> Dict[str, Any]:
        """Build add job form data - business logic moved from handler"""
        job_form_builder = JobFormDataBuilder()

        form_data = job_form_builder.build_empty_form_data()
        form_data['page_title'] = 'Add Job'
        form_data['form_title'] = 'Add New Backup Job'
        form_data['submit_button_text'] = 'Create Job'

        # Add available destination types
        from dests.services.kinds import DestinationTypeService
        destination_service = DestinationTypeService()
        form_data['available_destination_types'] = destination_service.get_available_destination_types()

        # Add notification configuration - provide data for template to render
        from jobs.services.define import NotificationFormBuilder
        notification_form_builder = NotificationFormBuilder(self.template_service, self.config_reader)

        # Get available providers list for template
        enabled_providers = notification_form_builder.get_enabled_global_providers()

        # Add notification form data
        form_data.update(self._build_notification_form_data_helper([]))
        form_data['available_options'] = enabled_providers  # For template to render options
        form_data['existing_notification_providers_html'] = ""  # No existing for new job
        form_data['add_provider_class'] = ""  # Show the add provider section

        # Add schedule configuration
        form_data.update(self._build_schedule_form_data_helper({}))

        return form_data


# =============================================================================
# **NOTIFICATION FORM BUILDING** - Notification form HTML and data building moved from handlers
# =============================================================================

class NotificationFormBuilder:
    """Service for building notification form HTML and managing form state - moved verbatim from handler"""

    def __init__(self, template_service, config_reader):
        self.template_service = template_service
        self.config_reader = config_reader
        self.configured_providers = []  # State for rendering

    def get_enabled_global_providers(self):
        """Get list of globally enabled notification providers - moved verbatim from handler"""
        global_settings = self.config_reader.get_global_settings()
        notification_config = global_settings.get('notification', {})

        enabled_providers = []
        for provider, config in notification_config.items():
            if isinstance(config, dict) and config.get('enabled', False):
                enabled_providers.append(provider)

        return enabled_providers

    def render_notification_provider(self, config, index, provider_id=None):
        """Render a single notification provider configuration - moved verbatim from handler"""
        import html
        provider_name = config.get('provider', '')
        display_name = provider_name.capitalize()

        if not provider_id:
            provider_id = f"notification_{provider_name}_{index}"

        notify_on_success = config.get('notify_on_success', False)
        success_message = html.escape(config.get('success_message', ''))

        notify_on_failure = config.get('notify_on_failure', False)
        failure_message = html.escape(config.get('failure_message', ''))

        notify_on_maintenance_failure = config.get('notify_on_maintenance_failure', False)

        return self.template_service.render_template('partials/notification_provider_config.html',
                                                   provider_id=provider_id,
                                                   provider_name=provider_name,
                                                   display_name=display_name,
                                                   notify_on_success=notify_on_success,
                                                   success_message=success_message,
                                                   notify_on_failure=notify_on_failure,
                                                   failure_message=failure_message,
                                                   notify_on_maintenance_failure=notify_on_maintenance_failure)

    def render_provider_selection(self, available_providers):
        """Render provider selection dropdown - moved verbatim from handler"""
        # Filter out configured providers
        available_options = [p for p in available_providers if p not in self.configured_providers]

        return self.template_service.render_template('partials/provider_selection_dropdown.html',
                                                   available_options=available_options)

    def toggle_success_message_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Toggle success message field visibility for job notification configuration - moved verbatim from handler"""
        from models.forms import safe_get_value

        # Check if checkbox is checked
        enabled = 'notify_on_success[]' in form_data
        success_message = safe_get_value(form_data, 'notification_success_messages[]')

        return {
            'enabled': enabled,
            'success_message': success_message
        }

    def toggle_failure_message_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Toggle failure message field visibility for job notification configuration - moved verbatim from handler"""
        from models.forms import safe_get_value

        # Check if checkbox is checked
        enabled = 'notify_on_failure[]' in form_data
        failure_message = safe_get_value(form_data, 'notification_failure_messages[]')

        return {
            'enabled': enabled,
            'failure_message': failure_message
        }

    def add_notification_provider_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new notification provider to job configuration for HTMX forms - moved verbatim from handler"""
        import time
        from models.forms import safe_get_value

        provider_name = safe_get_value(form_data, 'provider')
        if not provider_name:
            return {
                'success': False,
                'error': 'Invalid provider selection'
            }

        # Generate unique ID
        timestamp = int(time.time() * 1000)
        provider_id = f"notification_{provider_name}_{timestamp}"

        new_provider_html = self.render_notification_provider({
            'provider': provider_name,
            'notify_on_success': False,
            'notify_on_failure': True,  # Default to True for failures
            'notify_on_maintenance_failure': False,
            'success_message': '',
            'failure_message': ''
        }, timestamp, provider_id)

        # Get currently configured providers from form data
        current_providers = self._get_form_providers_from_data(form_data)
        current_providers.append(provider_name)

        # Update dropdown with remaining providers
        available_providers = self.get_enabled_global_providers()
        self.configured_providers = current_providers  # Update state
        updated_selection = self.render_provider_selection(available_providers)

        return {
            'success': True,
            'new_provider_html': new_provider_html,
            'updated_selection_html': updated_selection
        }

    def remove_notification_provider_from_form(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove a notification provider from job configuration for HTMX forms - moved verbatim from handler"""
        from models.forms import safe_get_value

        provider_id = safe_get_value(form_data, 'provider_id')

        # Extract provider name from ID (format: notification_{provider}_{timestamp})
        provider_name = None
        if provider_id and '_' in provider_id:
            parts = provider_id.split('_')
            if len(parts) >= 2:
                provider_name = parts[1]

        # Get current providers from form and remove this one
        current_providers = self._get_form_providers_from_data(form_data)
        if provider_name and provider_name in current_providers:
            current_providers.remove(provider_name)

        # Update state and render dropdown
        self.configured_providers = current_providers
        available_providers = self.get_enabled_global_providers()
        updated_selection = self.render_provider_selection(available_providers)

        return {
            'success': True,
            'provider_id': provider_id,
            'updated_selection_html': updated_selection
        }

    def _get_form_providers_from_data(self, form_data):
        """Get currently configured providers from form data - moved verbatim from handler"""
        providers = form_data.get('notification_providers[]', [])
        # Handle both single string and list formats
        if isinstance(providers, str):
            return [providers] if providers else []
        return [p for p in providers if p]  # Filter out empty strings

    def get_job_config_for_repository_check(self, job_name: str) -> Dict[str, Any]:
        """Get job configuration for repository availability check - business logic moved from handler"""
        jobs = self.config_reader.get_backup_jobs()
        if job_name not in jobs:
            return {
                'found': False,
                'error': f"Job '{job_name}' not found"
            }

        return {
            'found': True,
            'job_config': jobs[job_name]
        }

    def build_notification_providers_html(self, existing_notifications: List = None) -> Dict[str, Any]:
        """Build notification providers HTML - business logic moved from handler"""
        if existing_notifications is None:
            existing_notifications = []

        # Get available providers from global config
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.config_reader)
        available_providers = form_builder.get_enabled_global_providers()

        # Build provider configurations HTML
        provider_html = ""
        for i, provider in enumerate(existing_notifications):
            provider_html += form_builder.render_notification_provider(provider, i)

        # Build provider selection dropdown HTML
        form_builder.configured_providers = []  # Initialize for rendering
        selection_html = form_builder.render_provider_selection(available_providers)

        return {
            'provider_html': provider_html,
            'selection_html': selection_html
        }