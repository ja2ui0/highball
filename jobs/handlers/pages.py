"""
Jobs Page Handlers
Job management, inspection, and execution monitoring
"""

import logging
from typing import Dict, Any, Callable, List
from pathlib import Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from config import BackupConfig
from models.forms import safe_get_value, safe_get_list, parse_lines

logger = logging.getLogger(__name__)


# =============================================================================
# JOB FORM PARSERS
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



class JobsHandler(BaseHandler):
    """Handle job management and inspection"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.backup_config = BackupConfig()
        
        # Initialize service orchestrators (moved from operations handler)
        from jobs.services.backup import BackupOrchestrationService
        from jobs.services.validate import ValidationService
        from jobs.services.manage import JobOperationsService
        self.backup_orchestration = BackupOrchestrationService(self.backup_config)
        self.validation_service = ValidationService(self.backup_config)
        self.job_operations = JobOperationsService(self.backup_config)
    
    # =========================================================================
    # VALIDATION RENDERING (moved from services/template.py)
    # =========================================================================
    
    def render_source_path_validation_status(self, result: Dict[str, Any]) -> str:
        """Render source path validation status (basic validation, no special SSH details)"""
        return self._render_validation_status_template(result, [])
    
    def _render_validation_status_template(self, result: Dict[str, Any], details: List[str]) -> str:
        """Render validation status using template with consistent formatting"""
        # Determine status class and label
        if result.get('valid', False):
            status_class = 'success'
            status_label = '[OK]'
        else:
            status_class = 'error'
            status_label = '[ERROR]'
        
        # Build message from details or error
        if details:
            # Pass details as a list for proper formatting in template
            message = None
        else:
            # Use appropriate message based on validation result
            if result.get('valid', False):
                message = result.get('message', 'Validation successful')
            else:
                message = result.get('error', 'Validation failed')
            details = None
        
        # Use Jinja2 template to render the result
        return self.template_service.render_template('partials/validation_result.html', 
                                   status_class=status_class,
                                   status_label=status_label,
                                   message=message,
                                   details=details)
    
    # =========================================================================
    # JOB ROW BUILDING (moved from services/template.py)
    # =========================================================================
    
    def _build_job_rows(self, jobs):
        """Build job table rows from job data"""
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
    
    def _build_deleted_job_rows(self, deleted_jobs):
        """Build deleted job table rows from deleted jobs data"""
        if not deleted_jobs:
            return self.template_service.load_template('partials/empty_deleted_rows.html')
        
        rows = []
        for job_name, job_config in deleted_jobs.items():
            # Build source and destination displays same way as active jobs
            source_display = self._build_source_display_with_type(job_config)
            dest_display = self._build_dest_display_with_type(job_config)
            
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
    
    # =========================================================================
    # PAGE HANDLERS
    # =========================================================================
    
    @handle_page_errors("Dashboard")
    def show_dashboard(self) -> HTMLResponse:
        """Show main dashboard with job list"""
        jobs = self.backup_config.get_backup_jobs()
        global_settings = self.backup_config.get_global_settings()
        
        # Get job status information
        from jobs.services.manage import JobManagementService
        job_management = JobManagementService(self.backup_config)
        
        job_list = []
        for job_name, job_config in jobs.items():
            # Use enabled/disabled status like original, not execution status
            enabled = job_config.get('enabled', True)
            status = "enabled" if enabled else "disabled"
            status_class = "status-success" if enabled else "status-error"
            
            # Build display strings with type prefixes like original
            source_display = self._build_source_display_with_type(job_config)
            dest_display = self._build_dest_display_with_type(job_config)
            
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
        
        # Build job and deleted job HTML using local methods (moved from template service)
        job_rows = self._build_job_rows(job_list)
        deleted_jobs = self.backup_config.config.get('deleted_jobs', {})
        deleted_job_rows = self._build_deleted_job_rows(deleted_jobs)
        
        template_data = {
            'job_rows': job_rows,
            'deleted_job_rows': deleted_job_rows,
            'global_settings': global_settings,
            'page_title': 'Dashboard'
        }
        
        return self._render_html('pages/dashboard.html', template_data)

    def _build_source_display_with_type(self, job_config):
        """Build source display string with type prefix"""
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
    
    def _build_dest_display_with_type(self, job_config):
        """Build destination display string with type prefix"""
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

    @handle_page_errors("Add job form")
    def show_add_job_form(self) -> HTMLResponse:
        """Show add job form"""
        from jobs.services.define import JobFormDataBuilder
        from dests.services.kinds import DestinationTypeService
        job_form_builder = JobFormDataBuilder()
        
        form_data = job_form_builder.build_empty_form_data()
        form_data['page_title'] = 'Add Job'
        form_data['form_title'] = 'Add New Backup Job'
        form_data['submit_button_text'] = 'Create Job'
        
        # Add available destination types
        destination_service = DestinationTypeService()
        form_data['available_destination_types'] = destination_service.get_available_destination_types()
        
        # Add notification configuration
        form_data.update(self._build_notification_form_data([]))
        
        # Add schedule configuration
        form_data.update(self._build_schedule_form_data({}))
        
        return self._render_html('pages/job_form.html', form_data)

    @handle_page_errors("Edit job form")
    def show_edit_job_form(self, job_name: str) -> HTMLResponse:
        """Show edit job form"""
        from jobs.services.define import JobFormDataBuilder, JobFormTemplateBuilder
        from dests.services.kinds import DestinationTypeService
        job_form_builder = JobFormDataBuilder()
        
        if not job_name:
            return self._render_error('partials/error_page.html', {
                'error_message': "Job name is required", 
                'page_title': "Error"
            }, 400)
        
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_error('partials/error_page.html', {
                'error_message': f"Job '{job_name}' not found", 
                'page_title': "Error"
            }, 404)
        
        job_config = jobs[job_name]
        form_data = job_form_builder.build_form_data_from_job(job_name, job_config)
        form_data['page_title'] = f'Edit Job: {job_name}'
        form_data['form_title'] = f'Edit Backup Job: {job_name}'
        form_data['submit_button_text'] = 'Commit Changes'
        form_data['form_has_changes'] = False  # Initially no changes
        
        # Store original config for change detection (as JSON string)
        form_data['original_job_config'] = self.job_operations.serialize_job_config(job_config)
        
        # Add available destination types (could be context-aware based on source)
        source_config = job_config.get('source_config', {})
        destination_service = DestinationTypeService()
        form_data['available_destination_types'] = destination_service.get_available_destination_types(source_config)
        
        # Pre-select source and destination types for edit mode
        source_type = job_config.get('source_type', 'local')
        form_data['selected_source_type'] = source_type
        form_data['source_local_selected'] = (source_type == 'local')
        form_data['source_ssh_selected'] = (source_type == 'ssh')
        form_data['selected_dest_type'] = job_config.get('dest_type', 'local')
        
        # Build source fields HTML using template builder
        template_builder = JobFormTemplateBuilder(self.template_service)
        form_data['source_fields_html'] = template_builder.build_source_fields_html(source_type, source_config)
        
        # Build destination fields HTML using template builder
        dest_type = job_config.get('dest_type', 'local')
        dest_config = job_config.get('dest_config', {})
        form_data['dest_fields_html'] = template_builder.build_destination_fields_html(dest_type, dest_config, form_data)
        
        # Add notification configuration
        existing_notifications = job_config.get('notifications', [])
        form_data.update(self._build_notification_form_data(existing_notifications))
        
        # Add schedule configuration
        form_data.update(self._build_schedule_form_data(job_config))
        
        return self._render_html('pages/job_form.html', form_data)

    def _build_notification_form_data(self, existing_notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build notification form data structure (delegated to service)"""
        from jobs.services.notify import NotificationFormDataBuilder
        builder = NotificationFormDataBuilder(self.backup_config)
        return builder.build_notification_context(existing_notifications)
        
    def _build_schedule_form_data(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build schedule form data structure (delegated to service)"""
        from jobs.services.schedule import ScheduleFormDataBuilder
        builder = ScheduleFormDataBuilder()
        return builder.build_schedule_context(job_config)

    @handle_page_errors("Job inspect")
    def show_job_inspect(self, job_name: str = "") -> HTMLResponse:
        """Show job inspection page"""
        if not job_name:
            return self._render_error('partials/error_page.html', {
                'error_message': "Job name is required", 
                'page_title': "Error"
            }, 400)
        
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_error('partials/error_page.html', {
                'error_message': f"Job '{job_name}' not found", 
                'page_title': "Error"
            }, 404)
        
        job_config = jobs[job_name]
        
        # Get job status and logs
        from jobs.services.manage import JobManagementService
        job_management = JobManagementService(self.backup_config)
        status_info = job_management.get_status(job_name)
        recent_logs = job_management.get_log_entries(job_name, max_lines=100)
        
        # Format log content as string
        job_log_content = '\n'.join(recent_logs) if recent_logs else f'No log file yet for job "{job_name}". Job has not been executed (test or run) since creation.'
        
        template_data = {
            'job_name': job_name,
            'job_type': job_config.get('dest_type', 'unknown'),
            'last_run': status_info.get('last_updated', 'Never'), 
            'status': status_info.get('status', 'No runs'),
            'message': status_info.get('details', 'No message'),
            'job_log_content': job_log_content
        }
        
        return self._render_html('pages/job_inspect.html', template_data)

    def _build_job_config_from_result(self, job_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build job configuration from parsed form result"""
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

    @handle_page_errors("Save job")
    def save_backup_job(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save backup job from form submission"""
        from jobs.handlers.old import JobFormParser
        job_parser = JobFormParser()
        
        # Parse job form data using unified parser
        job_result = job_parser.parse_job_form(form_data)
        
        if not job_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': job_result['error']
            }, status_code=400)
        
        # Build and save job configuration
        job_name = job_result['job_name']
        job_config = self._build_job_config_from_result(job_result)
        
        # Save via service
        result = self.job_operations.save_job(job_name, job_config)
        
        if result['success']:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("Delete job")
    def delete_backup_job(self, job_name: str) -> JSONResponse:
        """Delete backup job"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        result = self.job_operations.delete_job(job_name)
        
        if result['success']:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("Purge job")
    def purge_backup_job(self, job_name: str) -> JSONResponse:
        """Permanently purge backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        result = self.job_operations.purge_job(job_name)
        
        if result['success']:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("Restore job")
    def restore_backup_job(self, job_name: str) -> JSONResponse:
        """Restore backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        result = self.job_operations.restore_job(job_name)
        
        if result['success']:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("Path validation")
    def validate_source_paths(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Validate source paths from form"""
        # Parse source paths from form
        # SourcePathsParser is now local to this module  
        paths_result = SourcePathsParser.parse_multi_path_options(form_data)
        
        if not paths_result['valid']:
            return JSONResponse(content=paths_result)
        
        # Build SSH configuration and validate paths
        source_type = form_data.get('source_type', ['local'])[0]
        ssh_config = self._build_ssh_config_from_form(form_data) if source_type == 'ssh' else {}
        validation_results = self._validate_individual_paths(source_type, paths_result['source_paths'], ssh_config)
        
        return JSONResponse(content={
            'valid': True,
            'results': validation_results
        })

    def _build_ssh_config_from_form(self, form_data: Dict[str, Any]) -> Dict[str, str]:
        """Build SSH configuration from form data"""
        hostname = form_data.get('hostname', [''])[0]
        username = form_data.get('username', [''])[0]
        return {'hostname': hostname, 'username': username}

    def _validate_individual_paths(self, source_type: str, source_paths: List[Dict[str, Any]], ssh_config: Dict[str, str]) -> List[Dict[str, Any]]:
        """Validate each individual source path"""
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
    
    
    def _check_and_respond_repository_status_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check repository availability and return appropriate HTMX HTML response"""
        dest_type = job_config.get('dest_type')
        
        if dest_type == 'restic':
            return self._check_restic_repository_html(job_name, job_config)
        else:
            # Non-restic repositories - assume available for now
            return self._render_html('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': dest_type
            })
    
    def _check_restic_repository_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check restic repository availability and return HTML response"""
        dest_config = job_config.get('dest_config', {})
        repo_uri = dest_config.get('repo_uri')
        
        if not repo_uri:
            return self._render_html('partials/error_message.html', {
                'error_message': 'Repository URI not configured'
            })
            
        from jobs.services.backup import backup_service
        check_success, check_message = backup_service.repository_service._quick_repository_check(repo_uri, dest_config)
        
        if check_success:
            return self._render_html('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': 'restic'
            })
        else:
            return self._send_repository_error_html(job_name, check_message)
    
    def _send_repository_error_html(self, job_name: str, error_message: str) -> HTMLResponse:
        """Send appropriate repository error HTMX partial based on error type"""
        if error_message and ('locked by' in error_message.lower() or 'repository is already locked' in error_message.lower()):
            # Repository locked - render unlock interface
            return self._render_html('partials/repository_locked_error.html', {
                'job_name': job_name,
                'error_message': error_message
            })
        else:
            # Other error - render error template
            return self._render_html('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'connection_error',
                'error_message': error_message or 'Unknown error'
            })






    def _get_enabled_global_providers(self):
        """Get list of globally enabled notification providers"""
        global_settings = self.backup_config.get_global_settings()
        notification_config = global_settings.get('notification', {})
        
        enabled_providers = []
        for provider, config in notification_config.items():
            if isinstance(config, dict) and config.get('enabled', False):
                enabled_providers.append(provider)
        
        return enabled_providers

    def _render_notification_provider(self, config, index, provider_id=None):
        """Render a single notification provider configuration"""
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

    def _render_provider_selection(self, available_providers):
        """Render provider selection dropdown"""
        # Filter out configured providers
        if not hasattr(self, 'configured_providers'):
            self.configured_providers = []
        available_options = [p for p in available_providers if p not in self.configured_providers]
        
        return self.template_service.render_template('partials/provider_selection_dropdown.html',
                                                   available_options=available_options)


    def _get_form_providers(self, form_data):
        """Get currently configured providers from form data"""
        providers = form_data.get('notification_providers[]', [])
        # Handle both single string and list formats
        if isinstance(providers, str):
            return [providers] if providers else []
        return [p for p in providers if p]  # Filter out empty strings



    # =============================================================================
    # RESTORE OPERATIONS - Extracted from mega-dispatcher
    # =============================================================================




    @handle_page_errors("Browse filesystem")
    def browse_filesystem(self, path: str = '/') -> JSONResponse:
        """Browse local filesystem for path selection - delegate to restore service"""
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        result = restore_service.browse_filesystem_path(path)
        return JSONResponse(content=result)


    @handle_page_errors("Process restore")
    def process_restore_request(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Process restore request from form - moved from operations handler"""
        job_name = form_data.get('job_name', [''])[0]
        snapshot_id = form_data.get('snapshot_id', [''])[0]
        target_type = form_data.get('target_type', ['safe'])[0]  # safe or source
        dry_run = 'dry_run' in form_data
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            })
        
        if not snapshot_id:
            return JSONResponse(content={
                'success': False,
                'error': 'Snapshot ID is required'
            })
        
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return JSONResponse(content={
                'success': False,
                'error': f"Job '{job_name}' not found"
            })
        
        job_config = jobs[job_name]
        
        # Only support Restic restores for now
        if job_config.get('dest_type') != 'restic':
            return JSONResponse(content={
                'success': False,
                'error': 'Restore only supported for Restic repositories'
            })
        
        # Build restore request
        restore_request = {
            'job_name': job_name,
            'job_config': job_config,
            'snapshot_id': snapshot_id,
            'target_type': target_type,
            'dry_run': dry_run
        }
        
        # Add include patterns if specified
        include_patterns = form_data.get('include_patterns', [''])
        if include_patterns[0]:
            restore_request['include_patterns'] = [p.strip() for p in include_patterns[0].split('\n') if p.strip()]
        
        # Execute restore (using operations handler implementation)
        result = self._execute_restore(restore_request)
        return JSONResponse(content=result)

    def _execute_restore(self, restore_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute restore operation - delegate to RestoreService"""
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        return restore_service.execute_restore_sync(restore_request)


    
    # =============================================================================
    # DIRECT ORCHESTRATION METHODS (moved from operations handler)
    # =============================================================================
    
    @handle_page_errors("Run backup direct")
    def run_backup_job_direct(self, job_name: str, dry_run: bool = False) -> JSONResponse:
        """Execute backup job with full orchestration - moved from operations handler"""
        from fastapi.responses import JSONResponse
        result = self.backup_orchestration.run_backup_job(job_name, dry_run)
        return JSONResponse(content=result)
    
    @handle_page_errors("Schedule job direct")
    def schedule_job_direct(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Schedule a job for execution - using functional SchedulingService"""
        from fastapi.responses import JSONResponse
        from jobs.services.schedule import SchedulingService
        
        # Use the functional scheduling service that already exists
        scheduler_service = SchedulingService()
        
        # Bootstrap all schedules (this will include the requested job if it's enabled and scheduled)
        scheduled_count = scheduler_service.bootstrap_schedules(self.backup_config)
        
        job_name = form_data.get('job_name', [''])[0] if isinstance(form_data.get('job_name'), list) else form_data.get('job_name', '')
        
        return JSONResponse(content={
            'success': True,
            'message': f'Scheduler refreshed. {scheduled_count} jobs scheduled total.',
            'job_name': job_name,
            'scheduled_count': scheduled_count
        })

    @handle_page_errors("List scheduler jobs")
    def list_scheduler_jobs(self) -> JSONResponse:
        """List APScheduler internal jobs - DEBUG/ADMIN endpoint"""
        from jobs.services.schedule import JobSchedulerHandler, SchedulingService
        scheduler_service = SchedulingService()
        job_scheduler = JobSchedulerHandler(scheduler_service)
        result = job_scheduler.list_jobs()
        return JSONResponse(content=result)

# Global handler instance
jobs_handler = JobsHandler()