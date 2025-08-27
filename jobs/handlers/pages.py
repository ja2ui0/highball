"""
Jobs Page Handlers
Job management, inspection, and execution monitoring
"""

import logging
from typing import Dict, Any, Callable, List
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from services.template import TemplateService
from config import BackupConfig

logger = logging.getLogger(__name__)

def handle_page_errors(operation_name: str) -> Callable:
    """Decorator to handle common page operation errors consistently"""
    def decorator(func: Callable) -> Callable:
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"{operation_name} error: {e}")
                return JSONResponse(content={
                    'success': False,
                    'error': str(e)
                }, status_code=500)
        return wrapper
    return decorator

class BaseHandler:
    """Base class for handlers with shared rendering helpers"""
    
    def _render_html(self, template: str, context: dict) -> HTMLResponse:
        """Helper to render template and return HTMLResponse"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html)
    
    def _render_error(self, template: str, context: dict, status: int = 400) -> HTMLResponse:
        """Helper to render error template and return HTMLResponse with status"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html, status_code=status)

class JobsHandler(BaseHandler):
    """Handle job management and inspection"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.backup_config = BackupConfig()
    
    @handle_page_errors("Dashboard")
    def show_dashboard(self) -> HTMLResponse:
        """Show main dashboard with job list"""
        jobs = self.backup_config.get_backup_jobs()
        global_settings = self.backup_config.get_global_settings()
        
        # Get job status information
        from services.management import JobManagementService
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
        
        # Process deleted jobs into display format
        deleted_jobs = self.backup_config.config.get('deleted_jobs', {})
        deleted_job_rows = ""
        
        if deleted_jobs:
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
                
                # Render each deleted job row
                row_html = self.template_service.render_template(
                    'partials/deleted_job_row.html',
                    job_name=job_name,
                    source_display=source_display,
                    dest_display=dest_display,
                    deleted_at=deleted_at
                )
                deleted_job_rows += row_html
        
        template_data = {
            'jobs': job_list,
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
        from services.data_services import JobFormDataBuilder, DestinationTypeService
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
        from services.data_services import JobFormDataBuilder, DestinationTypeService, JobFormTemplateBuilder
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
        import json
        form_data['original_job_config'] = json.dumps(job_config, sort_keys=True)
        
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
        from services.data_services import NotificationFormDataBuilder
        builder = NotificationFormDataBuilder(self.backup_config)
        return builder.build_notification_context(existing_notifications)
        
    def _build_schedule_form_data(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build schedule form data structure (delegated to service)"""
        from services.data_services import ScheduleFormDataBuilder
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
        from services.management import JobManagementService
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
        from models.forms import job_parser
        
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
        
        # Save to config
        success = self.backup_config.save_job(job_name, job_config)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': 'Failed to save job configuration'
            }, status_code=500)

    @handle_page_errors("Delete job")
    def delete_backup_job(self, job_name: str) -> JSONResponse:
        """Delete backup job"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.backup_config.delete_backup_job(job_name)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to delete job '{job_name}'"
            }, status_code=500)

    @handle_page_errors("Purge job")
    def purge_backup_job(self, job_name: str) -> JSONResponse:
        """Permanently purge backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.backup_config.purge_job(job_name)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to purge job '{job_name}'"
            }, status_code=500)

    @handle_page_errors("Restore job")
    def restore_backup_job(self, job_name: str) -> JSONResponse:
        """Restore backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.backup_config.restore_deleted_job(job_name)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to restore job '{job_name}'"
            }, status_code=500)

    @handle_page_errors("Path validation")
    def validate_source_paths(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Validate source paths from form"""
        # Parse source paths from form
        from models.forms import source_paths_parser
        paths_result = source_paths_parser.parse_multi_path_options(form_data)
        
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
    
    @handle_page_errors("Repository check")
    def check_repository_availability_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository availability check"""
        
        if not job_name:
            return self._render_html('partials/error_message.html', {
                'error_message': 'Job name is required'
            })
        
        # Get and validate job configuration
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_html('partials/error_message.html', {
                'error_message': f"Job '{job_name}' not found"
            })
        
        job_config = jobs[job_name]
        # Perform repository availability check and return response
        return self._check_and_respond_repository_status_html(job_name, job_config)
    
    @handle_page_errors("Repository unlock")
    def unlock_repository_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository unlock"""
        
        if not job_name:
            return self._render_html('partials/error_message.html', {
                'error_message': 'Job name is required'
            })
            
        # Get and validate job configuration
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_html('partials/error_message.html', {
                'error_message': f"Job '{job_name}' not found"
            })
        
        job_config = jobs[job_name]
        dest_type = job_config.get('dest_type')
        
        if dest_type != 'restic':
            return self._render_html('partials/error_message.html', {
                'error_message': 'Unlock is only supported for restic repositories'
            })
        # Execute restic unlock command
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        from jobs.services.backup import backup_service
        result = backup_service.unlock_repository(dest_config, source_config)
        
        if result.get('success'):
            # Unlock successful - automatically retry availability check
            return self.check_repository_availability_htmx(job_name)
        else:
            # Unlock failed - show error
            return self._render_html('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'unlock_failed',
                'error_message': result.get('error', 'Unlock failed')
            })
    
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

    async def validate_source_path_htmx(self, request) -> HTMLResponse:
        """Validate source path with robust permission checking for HTMX forms"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        form_data = {}
        for key, value in form.items():
            if key in form_data:
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]
        
        def get_form_value(form_data, key, default=''):
            """Extract single value from form data (works with FastAPI form parsing)"""
            value_list = form_data.get(key, [default])
            return value_list[0] if value_list else default
        
        try:
            # Extract path from array format
            path_array = form_data.get('source_path[]', [])
            path_index = int(get_form_value(form_data, 'path_index', '0'))
            path = path_array[path_index] if path_index < len(path_array) else ''
            
            if not path or not path.strip():
                result = {'valid': False, 'error': 'Please enter a path'}
                html_response = self.template_service.render_validation_status('source_path', result)
                return HTMLResponse(content=html_response)
            
            # Extract source configuration
            source_type = get_form_value(form_data, 'source_type')
            hostname = get_form_value(form_data, 'hostname')
            username = get_form_value(form_data, 'username')
            
            # Validate based on source type (robust handling from working version)
            if source_type == 'ssh':
                result = self._check_ssh_path(hostname, username, path)
            elif source_type == 'local':
                result = self._check_local_path(path)
            else:
                result = {'valid': False, 'error': 'Please select a source type (Local Path or SSH Remote)'}
            
            html_response = self.template_service.render_validation_status('source_path', result)
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            result = {'valid': False, 'error': f'Validation error: {str(e)}'}
            html_response = self.template_service.render_validation_status('source_path', result)
            return HTMLResponse(content=html_response)

    def _check_ssh_path(self, hostname: str, username: str, path: str) -> Dict[str, Any]:
        """Check SSH path permissions with robust RX/RWX analysis (from working version)"""
        if not hostname or not username:
            return {'valid': False, 'error': 'SSH hostname and username required for remote path validation'}
        
        try:
            from services.execution import ExecutionService
            executor = ExecutionService()
            
            # Test RX permissions (required for backup) + write test in one command
            test_cmd = f'[ -d "{path}" ] && [ -r "{path}" ] && [ -x "{path}" ] && echo "RX_OK" && ([ -w "{path}" ] && echo "W_OK" || echo "W_FAIL") || echo "RX_FAIL"'
            result = executor.execute_ssh_command(hostname, username, ['bash', '-c', test_cmd])
            
            if result.returncode != 0:
                return {'valid': False, 'error': f'SSH connection failed: {result.stderr}'}
            
            output = result.stdout.strip()
            
            if 'RX_OK' not in output:
                return {'valid': False, 'error': f'Path not accessible (missing read/execute permissions or does not exist)'}
            
            has_write = 'W_OK' in output
            if has_write:
                return {'valid': True, 'message': 'Path is RWX (backup + restore capable)'}
            else:
                return {'valid': True, 'message': 'Path is RO (backup only - no restore to source)'}
            
        except Exception as e:
            return {'valid': False, 'error': f'Permission check failed: {str(e)}'}
    
    def _check_local_path(self, path: str) -> Dict[str, Any]:
        """Check local path permissions with robust RX/RWX analysis (from working version)"""
        try:
            import os
            
            if not os.path.exists(path):
                return {'valid': False, 'error': 'Path does not exist'}
            
            if not os.path.isdir(path):
                return {'valid': False, 'error': 'Path is not a directory'}
            
            # Check RX permissions
            if not (os.access(path, os.R_OK) and os.access(path, os.X_OK)):
                return {'valid': False, 'error': 'Missing read/execute permissions'}
            
            has_write = os.access(path, os.W_OK)
            if has_write:
                return {'valid': True, 'message': 'Path is RWX (backup + restore capable)'}
            else:
                return {'valid': True, 'message': 'Path is RO (backup only - no restore to source)'}
            
        except Exception as e:
            return {'valid': False, 'error': f'Permission check failed: {str(e)}'}

    async def add_source_path_htmx(self, request) -> HTMLResponse:
        """Add a new source path entry for HTMX forms"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        form_data = {}
        for key, value in form.items():
            if key in form_data:
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]
        
        def get_form_value(form_data, key, default=''):
            """Extract single value from form data (works with FastAPI form parsing)"""
            value_list = form_data.get(key, [default])
            return value_list[0] if value_list else default
        
        from origins.schema import SOURCE_PATH_SCHEMA
        
        # Get path count from JavaScript via hx-vals
        path_count = int(get_form_value(form_data, 'path_count', '0'))
        new_path_index = path_count  # Next sequential index
        
        # Create new empty path data
        path_data = {'path': '', 'includes': [], 'excludes': []}
        source_paths = ['', '']  # Always show remove button for new paths
        
        # Return just the new path entry wrapped in its container
        html_response = self.template_service.render_template('partials/source_path_entry_container.html',
                                                           path_index=new_path_index,
                                                           path_data=path_data,
                                                           source_paths=source_paths,
                                                           source_path_schema=SOURCE_PATH_SCHEMA)
        return HTMLResponse(content=html_response)

    async def remove_source_path_htmx(self, request) -> HTMLResponse:
        """Remove a source path entry - returns empty response for HTMX DELETE"""
        # Since we're using hx-delete and hx-swap="outerHTML", 
        # the target element will be removed automatically.
        # We just need to return an empty response.
        return HTMLResponse(content="")

    async def check_restore_overwrites_htmx(self, request) -> HTMLResponse:
        """Check restore overwrites for HTMX forms"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        form_data = {}
        for key, value in form.items():
            if key in form_data:
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]
        
        def get_form_value(form_data, key, default=''):
            """Extract single value from form data (works with FastAPI form parsing)"""
            value_list = form_data.get(key, [default])
            return value_list[0] if value_list else default
        
        # HTTP concern: extract parameters
        job_name = get_form_value(form_data, 'job_name')
        restore_target = get_form_value(form_data, 'restore_target', 'highball')
        select_all = get_form_value(form_data, 'select_all') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: delegate to restore service
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths, select_all
        )
        
        # Template concern: pass data to Jinja2 template for conditional rendering
        target_text = "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        return self._render_html('partials/restore_overwrite_warning.html', {
            'has_overwrites': has_overwrites,
            'target_text': target_text,
            'dry_run': False
        })

    async def render_notification_providers_htmx(self, request) -> HTMLResponse:
        """Render notification providers section for job configuration HTMX forms"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        form_data = {}
        for key, value in form.items():
            if key in form_data:
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]
        
        # Get available providers from global config
        available_providers = self._get_enabled_global_providers()
        existing_notifications = []  # Parse from form if editing
        
        # Build provider configurations
        provider_html = ""
        for i, provider in enumerate(existing_notifications):
            provider_html += self._render_notification_provider(provider, i)
        
        # Build provider selection dropdown
        self.configured_providers = []  # Initialize for rendering
        selection_html = self._render_provider_selection(available_providers)
        
        html_response = self.template_service.render_template('partials/notification_providers_section.html',
                                                            provider_html=provider_html,
                                                            selection_html=selection_html)
        return HTMLResponse(content=html_response)

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

    async def add_notification_provider_htmx(self, request) -> HTMLResponse:
        """Add a new notification provider to job configuration for HTMX forms"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        form_data = {}
        for key, value in form.items():
            if key in form_data:
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]
        
        def get_form_value(form_data, key, default=''):
            """Extract single value from form data (works with FastAPI form parsing)"""
            value_list = form_data.get(key, [default])
            return value_list[0] if value_list else default
        
        provider_name = get_form_value(form_data, 'provider')
        if not provider_name:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               message="Invalid provider selection")
            return HTMLResponse(content=html_response)
        
        # Generate unique ID
        import time
        timestamp = int(time.time() * 1000)
        provider_id = f"notification_{provider_name}_{timestamp}"
        
        new_provider_html = self._render_notification_provider({
            'provider': provider_name,
            'notify_on_success': False,
            'notify_on_failure': True,  # Default to True for failures
            'notify_on_maintenance_failure': False,
            'success_message': '',
            'failure_message': ''
        }, timestamp, provider_id)
        
        # Get currently configured providers from form data
        current_providers = self._get_form_providers(form_data)
        current_providers.append(provider_name)
        
        # Update dropdown with remaining providers
        available_providers = self._get_enabled_global_providers()
        self.configured_providers = current_providers  # Update state
        updated_selection = self._render_provider_selection(available_providers)
        
        html_response = self.template_service.render_template('partials/notification_provider_added_response.html',
                                                            new_provider_html=new_provider_html,
                                                            updated_selection_html=updated_selection)
        return HTMLResponse(content=html_response)

    def _get_form_providers(self, form_data):
        """Get currently configured providers from form data"""
        providers = form_data.get('notification_providers[]', [])
        # Handle both single string and list formats
        if isinstance(providers, str):
            return [providers] if providers else []
        return [p for p in providers if p]  # Filter out empty strings

# Global handler instance
jobs_handler = JobsHandler()