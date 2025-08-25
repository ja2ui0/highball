"""
Consolidated Page Handlers
Merges all page rendering handlers into single module
Replaces: dashboard.py, config_handler.py, inspect_handler.py, logs.py, network.py
"""

import json
import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

# FastAPI imports
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# Import models for unified validation and forms
from models.validation import validation_service
from models.forms import job_parser

# Import services
from services.template import TemplateService
from services.data_services import JobFormDataBuilder, DestinationTypeService

logger = logging.getLogger(__name__)

class BaseHandler:
    """Base class for all handlers with shared rendering helpers"""
    
    def _render_html(self, template: str, context: dict) -> HTMLResponse:
        """Helper to render template and return HTMLResponse"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html)
    
    def _render_error(self, template: str, context: dict, status: int = 400) -> HTMLResponse:
        """Helper to render error template and return HTMLResponse with status"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html, status_code=status)


def handle_page_errors(operation_name: str) -> Callable:
    """Decorator to handle common page operation errors consistently"""
    def decorator(func: Callable) -> Callable:
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"{operation_name} error: {e}")
                # Return FastAPI error response
                return HTMLResponse(
                    content=f"<html><body><h1>Error</h1><p>{operation_name} error: {str(e)}</p></body></html>",
                    status_code=500
                )
        return wrapper
    return decorator

class GETHandlers(BaseHandler):
    """Handler for all read-only page rendering operations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        # ResponseUtils removed - all methods now return FastAPI responses directly
    
    
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
    
    @handle_page_errors("SSH origins")
    def show_ssh_origins(self) -> HTMLResponse:
        """Show SSH origins management page"""
        origins = self.backup_config.get_ssh_origins()
        global_settings = self.backup_config.get_global_settings()
        
        # Build origin display list
        origin_list = []
        for origin_name, origin_config in origins.items():
            # Determine authentication method display
            auth_method = "Highball SSH Key" if origin_config.get('ssh_highball', True) else "User SSH Key"
            
            # Connection info display
            connection_info = f"{origin_config.get('ssh_username')}@{origin_config.get('ssh_hostname')}:{origin_config.get('ssh_port', 22)}"
            
            # Capabilities display
            capabilities = []
            if origin_config.get('rsync_available'):
                capabilities.append("rsync")
            if origin_config.get('container_runtime'):
                capabilities.append(origin_config['container_runtime'])
            capabilities_display = ", ".join(capabilities) if capabilities else "Not detected"
            
            origin_display = {
                'name': origin_name,
                'friendly_name': origin_config.get('friendly_name', origin_name),
                'connection_info': connection_info,
                'auth_method': auth_method,
                'capabilities': capabilities_display,
                'config': origin_config
            }
            origin_list.append(origin_display)
        
        # Sort by friendly name for consistent display
        origin_list.sort(key=lambda x: x['friendly_name'].lower())
        
        template_data = {
            'origins': origin_list,
            'global_settings': global_settings,
            'theme_css_path': '',
            'page_title': 'SSH Origins'
        }
        
        return self._render_html('pages/ssh_config.html', template_data)
    
    @handle_page_errors("Edit SSH origin")
    def edit_ssh_origin(self, origin_name: str) -> HTMLResponse:
        """Load SSH origin for editing"""
        origin_config = self.backup_config.get_ssh_origin(origin_name)
        
        if not origin_config:
            # Return empty form if origin not found
            return self._render_html('partials/ssh_origin_form.html', {})
        
        # Create edit form with populated values including existing capabilities
        form_data = {
            'origin_name': origin_name,
            'friendly_name': origin_config.get('friendly_name', ''),
            'ssh_hostname': origin_config.get('ssh_hostname', ''),
            'ssh_username': origin_config.get('ssh_username', ''),
            'ssh_port': origin_config.get('ssh_port', 22),
            'ssh_timeout': origin_config.get('ssh_timeout', 5),
            'ssh_highball': origin_config.get('ssh_highball', True),
            'rsync_available': origin_config.get('rsync_available', False),
            'container_runtime': origin_config.get('container_runtime', None),
            'edit_mode': True  # Flag to indicate this is edit mode
        }
        
        return self._render_html('partials/ssh_origin_form.html', form_data)
    
    @handle_page_errors("Destinations")
    def show_destinations(self) -> HTMLResponse:
        """Show destinations management page"""
        destinations = self.backup_config.get_destinations()
        global_settings = self.backup_config.get_global_settings()
        
        # Build destination display list
        dest_list = []
        for dest_name, dest_config in destinations.items():
            # Determine destination type display
            dest_type = dest_config.get('type', 'Unknown')
            type_display = {
                'rsync': 'Rsync (SSH)',
                'rsyncd': 'Rsync Daemon', 
                'restic': 'Restic Repository'
            }.get(dest_type, dest_type)
            
            # Connection info display from nested structure
            hostname = dest_config.get('hostname', 'unknown')
            port = dest_config.get('port', 'unknown')
            connection_info = f"{hostname}:{port}"
            
            # URI display (truncated for display)
            uri = dest_config.get('uri', 'Not generated')
            uri_display = uri if len(uri) <= 50 else uri[:47] + "..."
            
            dest_display = {
                'name': dest_name,
                'friendly_name': dest_config.get('friendly_name', dest_name),
                'type_display': type_display,
                'connection_info': connection_info,
                'uri_display': uri_display,
                'config': dest_config
            }
            dest_list.append(dest_display)
        
        # Sort by friendly name for consistent display
        dest_list.sort(key=lambda x: x['friendly_name'].lower())
        
        template_data = {
            'destinations': dest_list,
            'global_settings': global_settings,
            'theme_css_path': '',
            'page_title': 'Destinations'
        }
        
        return self._render_html('pages/destinations.html', template_data)
    
    @handle_page_errors("Add job form")
    def show_add_job_form(self) -> HTMLResponse:
        """Show add job form"""
        form_data = self.job_form_builder.build_empty_form_data()
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
    
    @handle_page_errors("Edit job form")
    def show_edit_job_form(self, job_name: str) -> HTMLResponse:
        """Show edit job form"""
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
        form_data = self.job_form_builder.build_form_data_from_job(job_name, job_config)
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
        from services.data_services import JobFormTemplateBuilder
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
    
    @handle_page_errors("Config manager")
    def show_config_manager(self) -> HTMLResponse:
        """Show configuration management page"""
        from models.notifications import PROVIDER_FIELD_SCHEMAS
        
        global_settings = self.backup_config.get_global_settings()
        
        # Extract individual field values for template population
        default_schedule_times = global_settings.get('default_schedule_times', {})
        
        # Get available themes for template to handle
        available_themes = self._get_available_themes()
        current_theme = global_settings.get('theme', 'dark')
        
        template_data = {
            # Keep global_settings for partials that use it
            'global_settings': global_settings,
            'provider_schemas': PROVIDER_FIELD_SCHEMAS,
            'page_title': 'Configuration',
            
            # Individual field values for form population
            'scheduler_timezone': global_settings.get('scheduler_timezone', 'UTC'),
            'available_themes': available_themes,
            'current_theme': current_theme,
            'enable_conflict_avoidance': 'checked' if global_settings.get('enable_conflict_avoidance', True) else '',
            'conflict_check_interval': str(global_settings.get('conflict_check_interval', 300)),
            'delay_notification_threshold': str(global_settings.get('delay_notification_threshold', 300)),
            
            # Default schedule times
            'hourly_default': default_schedule_times.get('hourly', '0 * * * *'),
            'daily_default': default_schedule_times.get('daily', '0 3 * * *'),
            'weekly_default': default_schedule_times.get('weekly', '0 3 * * 0'),
            'monthly_default': default_schedule_times.get('monthly', '0 3 1 * *'),
        }
            
        return self._render_html('pages/config_manager.html', template_data)
    
    @handle_page_errors("Raw editor")
    def show_raw_editor(self) -> HTMLResponse:
        """Show raw YAML configuration editor"""
        config_path = self.backup_config.config_file
        raw_config = ""
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                raw_config = f.read()
        
        template_data = {
            'raw_config': raw_config,
            'config_path': config_path,
            'page_title': 'Raw Configuration Editor'
        }
        
        return self._render_html('pages/config_editor.html', template_data)
    
    def _get_available_themes(self):
        """Get list of available themes by scanning theme directory"""
        import os
        themes = []
        theme_dir = 'static/themes'
        
        if os.path.exists(theme_dir):
            for file in os.listdir(theme_dir):
                if file.endswith('.css'):
                    theme_name = file[:-4]  # Remove .css extension
                    themes.append(theme_name)
        
        # Always ensure 'dark' is available as fallback
        if 'dark' not in themes:
            themes.append('dark')
        
        return sorted(themes)
    
    # CGI error method removed - all page handlers now return FastAPI responses directly

    @handle_page_errors("Job inspection")
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

    @handle_page_errors("Dev logs")
    def show_dev_logs(self, log_type: str = 'app') -> HTMLResponse:
        """Show development/debug logs page"""
        logs_data = self._get_system_logs(log_type)
        
        template_data = {
            'log_type': log_type,
            'logs': logs_data,
            'available_types': ['app', 'system', 'job_status', 'validation', 'running_jobs', 'deleted_jobs'],
            'page_title': f'Debug Logs: {log_type}'
        }
        
        return self._render_html('pages/dev_logs.html', template_data)
    
    def _get_system_logs(self, log_type: str) -> List[str]:
        """Get system logs by type"""
        try:
            if log_type == 'app':
                # Application logs from docker
                import subprocess
                result = subprocess.run(['docker', 'logs', '--tail', '100', 'highball'], 
                                      capture_output=True, text=True, timeout=10)
                return result.stdout.split('\n') if result.returncode == 0 else ['Log retrieval failed']
            
            elif log_type == 'system':
                # System logs
                log_files = ['/var/log/syslog', '/var/log/messages']
                for log_file in log_files:
                    if os.path.exists(log_file):
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                        return lines[-100:]  # Last 100 lines
                return ['No system logs found']
            
            elif log_type in ['job_status', 'validation', 'running_jobs', 'deleted_jobs']:
                # Highball operational logs
                log_file = f'/var/log/highball/{log_type}.yaml'
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    return [content] if content.strip() else ['Empty log file']
                return ['Log file not found']
            
            else:
                return ['Unknown log type']
                
        except Exception as e:
            logger.error(f"Get logs error: {e}")
            return [f'Error retrieving logs: {str(e)}']


class POSTHandlers(BaseHandler):
    """Handler for all form submissions and mutations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        # ResponseUtils removed - all methods now return FastAPI responses directly
    
    def _send_job_form_error(self, request_handler, form_data: Dict[str, Any], error_message: str):
        """Send job form with error message"""
        error_form_data = self.job_form_builder.build_form_data_with_error(
            form_data, error_message
        )
        # Determine if this is add or edit based on job_name
        job_name_from_form = form_data.get('job_name', [''])[0] if isinstance(form_data.get('job_name', []), list) else form_data.get('job_name', '')
        if job_name_from_form:
            error_form_data['page_title'] = f'Edit Job: {job_name_from_form}'
            error_form_data['form_title'] = f'Edit Backup Job: {job_name_from_form}'
        else:
            error_form_data['page_title'] = 'Add Job'
            error_form_data['form_title'] = 'Add New Backup Job'
        html = self.template_service.render_template('pages/job_form.html', **error_form_data)
        self.response_utils.send_html_response(request_handler, html)

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

    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Helper to safely get form values handling both list and string formats"""
        value = form_data.get(field_name, [default])
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)

    def _update_notification_settings(self, global_settings: dict, form_data: Dict[str, Any]):
        """Update notification settings from form data"""
        notification_config = global_settings.setdefault('notification', {})
        
        # Process each provider using the schema-driven approach
        from models.notifications import PROVIDER_FIELD_SCHEMAS
        
        for provider_name, schema in PROVIDER_FIELD_SCHEMAS.items():
            provider_config = notification_config.setdefault(provider_name, {})
            
            # Process top-level fields (including enabled checkbox)
            for field_info in schema.get('fields', []):
                self._process_notification_field(provider_config, provider_name, field_info, form_data)
            
            # Handle all sections (smtp_config, queue_settings, etc.)
            if 'sections' in schema:
                for section in schema['sections']:
                    for field_info in section['fields']:
                        self._process_notification_field(provider_config, provider_name, field_info, form_data)

    def _process_notification_field(self, provider_config: dict, provider_name: str, field_info: dict, form_data: Dict[str, Any]):
        """Process a single notification field based on its type"""
        field_name = f"{provider_name}_{field_info['name']}"
        
        if field_info['type'] == 'checkbox':
            provider_config[field_info['name']] = field_name in form_data
        elif field_info['type'] == 'select' and 'options' in field_info:
            # Handle select with config_field mapping (e.g., encryption)
            select_value = self._get_form_value(form_data, field_name, field_info.get('default', ''))
            # Reset all boolean options first
            for option in field_info['options']:
                if 'config_field' in option:
                    provider_config[option['config_field']] = False
            # Set the selected option to True
            for option in field_info['options']:
                if option['value'] == select_value and 'config_field' in option:
                    provider_config[option['config_field']] = True
        elif field_info['type'] == 'number':
            value = self._get_form_value(form_data, field_name, str(field_info.get('placeholder', '0')))
            try:
                provider_config[field_info['name']] = int(value)
            except ValueError:
                provider_config[field_info['name']] = field_info.get('placeholder', 0)
        else:
            # text, email, password fields
            provider_config[field_info['name']] = self._get_form_value(form_data, field_name, '')

    @handle_page_errors("Save raw config")
    def save_raw_config(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save raw YAML configuration"""
        
        raw_config = form_data.get('raw_config', [''])[0]
        
        # Validate YAML syntax
        try:
            import yaml
            yaml.safe_load(raw_config)
        except yaml.YAMLError as e:
            return JSONResponse(content={
                'success': False,
                'error': f'Invalid YAML: {str(e)}'
            }, status_code=400)
        
        # Save to file
        config_path = self.backup_config.config_file
        with open(config_path, 'w') as f:
            f.write(raw_config)
        
        # Reload configuration
        self.backup_config.reload_config()
        
        return RedirectResponse(url='/config', status_code=302)

    @handle_page_errors("Save config")
    def save_structured_config(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save structured configuration from form"""
        
        try:
            # Update global settings
            global_settings = self.backup_config.config.setdefault('global_settings', {})
            
            # Basic settings
            global_settings['scheduler_timezone'] = self._get_form_value(form_data, 'scheduler_timezone', 'UTC')
            
            # Theme setting (only save if not default 'dark')
            theme = self._get_form_value(form_data, 'theme', 'dark')
            if theme != 'dark':
                global_settings['theme'] = theme
            elif 'theme' in global_settings:
                # Remove theme key if set back to default
                del global_settings['theme']
            
            global_settings['enable_conflict_avoidance'] = 'enable_conflict_avoidance' in form_data
            global_settings['conflict_check_interval'] = int(self._get_form_value(form_data, 'conflict_check_interval', '300'))
            global_settings['delay_notification_threshold'] = int(self._get_form_value(form_data, 'delay_notification_threshold', '300'))
            
            # Default schedule times
            default_schedule_times = global_settings.setdefault('default_schedule_times', {})
            default_schedule_times['hourly'] = self._get_form_value(form_data, 'hourly_default', '0 * * * *')
            default_schedule_times['daily'] = self._get_form_value(form_data, 'daily_default', '0 3 * * *')
            default_schedule_times['weekly'] = self._get_form_value(form_data, 'weekly_default', '0 3 * * 0')
            default_schedule_times['monthly'] = self._get_form_value(form_data, 'monthly_default', '0 3 1 * *')
            
            # Notification settings - delegate to notification form parser
            self._update_notification_settings(global_settings, form_data)
            
            # Save configuration
            self.backup_config.save_config()
            
            # Redirect back to config page
            return RedirectResponse(url='/config', status_code=302)
            
        except Exception as e:
            return JSONResponse(content={
                'success': False,
                'error': f'Configuration save failed: {str(e)}'
            }, status_code=500)

    def _build_notification_preview(self, global_settings: dict, form_data: Dict[str, Any]):
        """Build notification settings for preview (without modifying actual config)"""
        notification_config = global_settings.setdefault('notification', {})
        
        # Process each provider using the schema-driven approach
        from models.notifications import PROVIDER_FIELD_SCHEMAS
        
        for provider_name, schema in PROVIDER_FIELD_SCHEMAS.items():
            provider_config = notification_config.setdefault(provider_name, {})
            
            # Process top-level fields (including enabled checkbox)
            for field_info in schema.get('fields', []):
                self._process_notification_field(provider_config, provider_name, field_info, form_data)
            
            # Handle all sections (smtp_config, queue_settings, etc.)
            if 'sections' in schema:
                for section in schema['sections']:
                    for field_info in section['fields']:
                        self._process_notification_field(provider_config, provider_name, field_info, form_data)

    @handle_page_errors("Preview config")
    def preview_config_changes(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Preview configuration changes without saving"""
        # Build the configuration that would be saved (without actually saving)
        preview_config = {}
        global_settings = preview_config.setdefault('global_settings', {})
        
        # Basic settings
        global_settings['scheduler_timezone'] = self._get_form_value(form_data, 'scheduler_timezone', 'UTC')
        
        # Theme setting
        theme = self._get_form_value(form_data, 'theme', 'dark')
        if theme != 'dark':
            global_settings['theme'] = theme
        
        global_settings['enable_conflict_avoidance'] = 'enable_conflict_avoidance' in form_data
        global_settings['conflict_check_interval'] = int(self._get_form_value(form_data, 'conflict_check_interval', '300'))
        global_settings['delay_notification_threshold'] = int(self._get_form_value(form_data, 'delay_notification_threshold', '300'))
        
        # Default schedule times
        default_schedule_times = global_settings.setdefault('default_schedule_times', {})
        default_schedule_times['hourly'] = self._get_form_value(form_data, 'hourly_default', '0 * * * *')
        default_schedule_times['daily'] = self._get_form_value(form_data, 'daily_default', '0 3 * * *')
        default_schedule_times['weekly'] = self._get_form_value(form_data, 'weekly_default', '0 3 * * 0')
        default_schedule_times['monthly'] = self._get_form_value(form_data, 'monthly_default', '0 3 1 * *')
        
        # Notification settings
        self._build_notification_preview(global_settings, form_data)
        
        # Convert to YAML for display
        import yaml
        preview_yaml = yaml.dump(preview_config, default_flow_style=False, indent=2)
        
        # Render preview partial
        return self._render_html('partials/config_preview.html', {
            'preview_yaml': preview_yaml,
            'success': True
        })
    
    # =============================================================================
    # SSH ORIGIN MANAGEMENT HANDLERS
    # =============================================================================
    
    def _validate_and_update_origin_capabilities(self, origin_config):
        """Run SSH validation and update origin config with detected capabilities"""
        ssh_config = {
            'hostname': origin_config['ssh_hostname'],
            'username': origin_config['ssh_username']
        }
        
        from models.validation import ValidationService
        validation_service = ValidationService()
        validation_result = validation_service.validate_ssh_source(ssh_config)
        
        # Add detected capabilities to origin config
        if validation_result['valid']:
            origin_config['rsync_available'] = 'rsync' in validation_result.get('rsync_status', '').lower() or validation_result.get('rsync_status') == 'Available'
            origin_config['container_runtime'] = validation_result.get('container_runtime')
        else:
            # If validation fails, still save but with unknown capabilities
            origin_config['rsync_available'] = False
            origin_config['container_runtime'] = None
        
        return origin_config
    
    @handle_page_errors("Add SSH origin")
    def add_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new SSH origin"""
        from models.forms import origin_parser
        
        
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        
        # Check if origin already exists
        existing_origins = self.backup_config.get_ssh_origins()
        if origin_name in existing_origins:
            return JSONResponse(content={
                'success': False,
                'error': f'Origin "{origin_name}" already exists'
            }, status_code=400)
        
        # Save origin with capabilities from form parser (including any detected values)
        success = self.backup_config.save_origin(origin_name, origin_config)
        
        if success:
            return RedirectResponse(url='/ssh', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save origin '{origin_name}'"
            }, status_code=500)
    
    def _get_recent_validation_results(self, hostname: str, username: str) -> dict:
        """Get capabilities from recent SSH validation session for this host/user"""
        if not hasattr(self, '_ssh_sessions'):
            return {}
            
        # Look for completed validation sessions for this hostname/username
        for session_id, session_data in self._ssh_sessions.items():
            if (session_data.get('completed') and 
                session_data.get('success') and 
                session_data.get('result')):
                
                result = session_data['result']
                # Check if this result is for our hostname/username (rough match)
                if (result.get('success') and 
                    'rsync_available' in result and 
                    'container_runtime' in result):
                    return {
                        'rsync_available': result.get('rsync_available', False),
                        'container_runtime': result.get('container_runtime', None)
                    }
        
        return {}
    
    @handle_page_errors("Save SSH origin")
    def save_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save SSH origin changes"""
        from models.forms import origin_parser
        
        
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        original_origin_name = self._get_form_value(form_data, 'original_origin_name', '')
        
        # Handle renaming if the origin name changed
        if original_origin_name and original_origin_name != origin_name:
            # Delete the old file
            self.backup_config.delete_origin(original_origin_name)
        
        # Save origin with detected capabilities (overwrites existing or creates new)
        success = self.backup_config.save_origin(origin_name, origin_config)
        
        if success:
            return RedirectResponse(url='/ssh', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save origin '{origin_name}'"
            }, status_code=500)
    
    @handle_page_errors("Delete SSH origin")
    def delete_ssh_origin(self, origin_name: str) -> JSONResponse:
        """Delete SSH origin"""
        
        if not origin_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Origin name is required'
            }, status_code=400)
        
        success = self.backup_config.delete_origin(origin_name)
        
        if success:
            return RedirectResponse(url='/ssh', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to delete origin '{origin_name}'"
            }, status_code=500)
    
    # =============================================================================
    # DESTINATION MANAGEMENT HANDLERS
    # =============================================================================
    
    def _flatten_dest_config_for_uri(self, dest_config):
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

    def _build_destination_uri(self, dest_config):
        """Build destination URI based on type and configuration"""
        from models.forms import DestinationParser
        
        dest_type = dest_config.get('type')
        uri_result = DestinationParser.build_destination_uri(dest_type, dest_config)
        
        if uri_result['valid']:
            return uri_result['uri']
        else:
            return f"Error: {uri_result.get('error', 'URI generation failed')}"

    def _get_default_port(self, dest_type: str) -> int:
        """Get default port for destination type"""
        defaults = {
            'rsync': 22,
            'rsyncd': 873,
            'restic': 8000  # Default for REST, will vary by repo type
        }
        return defaults.get(dest_type, 22)
    
    @handle_page_errors("Add destination")
    def add_destination(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new destination"""
        
        # Extract basic destination info
        dest_name = self._get_form_value(form_data, 'dest_name', '').strip()
        friendly_name = self._get_form_value(form_data, 'friendly_name', '').strip()
        dest_type = self._get_form_value(form_data, 'dest_type', '')
        hostname = self._get_form_value(form_data, 'hostname', '').strip()
        port = self._get_form_value(form_data, 'port', '')
        
        # Validation
        if not dest_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination name is required'
            }, status_code=400)
            
        if not dest_type:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination type is required'
            }, status_code=400)
        
        # Check if destination already exists
        existing_destinations = self.backup_config.get_destinations()
        if dest_name in existing_destinations:
            return JSONResponse(content={
                'success': False,
                'error': f'Destination "{dest_name}" already exists'
            }, status_code=400)
        
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
            username = self._get_form_value(form_data, 'username', '').strip()
            path = self._get_form_value(form_data, 'path', '').strip()
            
            if not username or not path:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Username and path are required for rsync destinations'
                }, status_code=400)
            
            dest_config['rsync'] = {
                'username': username,
                'path': path
            }
            
        elif dest_type == 'rsyncd':
            share = self._get_form_value(form_data, 'share', '').strip()
            
            if not share:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Share is required for rsyncd destinations'
                }, status_code=400)
            
            rsyncd_config = {'share': share}
            
            # Optional fields
            username = self._get_form_value(form_data, 'username', '').strip()
            password = self._get_form_value(form_data, 'password', '').strip()
            if username:
                rsyncd_config['username'] = username
            if password:
                rsyncd_config['password'] = password
                
            dest_config['rsyncd'] = rsyncd_config
            
        elif dest_type == 'restic':
            repo_type = self._get_form_value(form_data, 'repo_type', '')
            password = self._get_form_value(form_data, 'password', '')
            
            if not repo_type or not password:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Repository type and password are required for restic destinations'
                }, status_code=400)
            
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
        success = self.backup_config.save_destination(dest_name, dest_config)
        
        if success:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save destination '{dest_name}'"
            }, status_code=500)
    
    @handle_page_errors("Save destination")
    def save_destination(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save destination changes"""
        
        # Extract destination name from form
        dest_name = self._get_form_value(form_data, 'dest_name', '').strip()
        
        if not dest_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination name is required'
            }, status_code=400)
        
        # Get existing destination config to preserve type-specific settings
        existing_dest = self.backup_config.get_destination(dest_name)
        if not existing_dest:
            return JSONResponse(content={
                'success': False,
                'error': f'Destination "{dest_name}" not found'
            }, status_code=404)
        
        # Update config with form data (similar to add_destination logic)
        updated_config = existing_dest.copy()
        updated_config['friendly_name'] = self._get_form_value(form_data, 'friendly_name', dest_name).strip()
        updated_config['hostname'] = self._get_form_value(form_data, 'hostname', '').strip()
        port = self._get_form_value(form_data, 'port', '')
        if port:
            updated_config['port'] = int(port)
        
        # Regenerate URI with updated config
        flat_data = self._flatten_dest_config_for_uri(updated_config)
        updated_config['uri'] = self._build_destination_uri(flat_data)
        
        # Save updated destination
        success = self.backup_config.save_destination(dest_name, updated_config)
        
        if success:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to update destination '{dest_name}'"
            }, status_code=500)
    
    @handle_page_errors("Delete destination")
    def delete_destination(self, dest_name: str) -> JSONResponse:
        """Delete destination"""
        
        if not dest_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination name is required'
            }, status_code=400)
        
        # Delete destination
        success = self.backup_config.delete_destination(dest_name)
        
        if success:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to delete destination '{dest_name}'"
            }, status_code=500)


class ValidationHandlers(BaseHandler):
    """Handler for all validation endpoints and AJAX operations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        # ResponseUtils removed - all methods now return FastAPI responses directly
    
    # CGI utility methods removed - all handlers now return FastAPI responses directly
    
    @handle_page_errors("SSH validation")
    def validate_ssh_source(self, source: str) -> JSONResponse:
        """Validate SSH source configuration"""
        # Parse source string (format: username@hostname)
        if '@' not in source:
            return JSONResponse(content={
                'valid': False,
                'error': 'Invalid source format. Expected: username@hostname'
            })
        
        username, hostname = source.split('@', 1)
        ssh_config = {'username': username, 'hostname': hostname}
        
        # Use unified validation service
        from models.validation import ValidationService
        validation_service = ValidationService()
        result = validation_service.validate_ssh_source(ssh_config)
        return JSONResponse(content=result)

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
    
    @handle_page_errors("SSH origin validation")
    def validate_ssh_origin(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Push keys and validate SSH origin configuration - main workflow orchestrator"""
        from models.forms import origin_parser
        
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content=origin_result)
        
        origin_config = origin_result['origin_config']
        edit_mode = 'original_origin_name' in form_data and form_data['original_origin_name']
        
        # Extract connection details
        hostname = origin_config['ssh_hostname']
        username = origin_config['ssh_username']  
        password = form_data.get('ssh_password', '')
        ssh_highball = form_data.get('ssh_highball') == 'on'
        
        # Require password when Highball checkbox is checked
        if ssh_highball and not password:
            return self._render_html('partials/ssh_validation_result.html', {
                'success': False,
                'edit_mode': edit_mode,
                'validation_message': 'Password is required when "Auto-populate keys using Highball" is checked.'
            })
        
        use_password = ssh_highball and password
        
        # Return immediate progress template, start workflow in background
        import uuid
        import threading
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Store session data
        if not hasattr(self, '_ssh_sessions'):
            self._ssh_sessions = {}
        
        self._ssh_sessions[session_id] = {
            'progress': ['• Starting SSH validation workflow...'],
            'completed': False,
            'success': None,
            'result': None,
            'edit_mode': edit_mode
        }
        
        # Start background workflow
        def run_workflow():
            result = self._push_keys_and_validate_workflow_with_session(session_id, hostname, username, password, use_password)
            self._ssh_sessions[session_id]['completed'] = True
            self._ssh_sessions[session_id]['result'] = result
        
        threading.Thread(target=run_workflow, daemon=True).start()
        
        # Return initial progress template
        return self._render_html('partials/ssh_validation_progress.html', {
            'session_id': session_id,
            'initial_message': "Starting SSH validation workflow..."
        })
    
    @handle_page_errors("SSH progress polling")
    def get_ssh_progress(self, session_id: str) -> HTMLResponse:
        """Get current SSH validation progress for a session"""
        if not hasattr(self, '_ssh_sessions') or session_id not in self._ssh_sessions:
            return self._render_html('partials/ssh_validation_result.html', {
                'success': False,
                'validation_message': "Session not found or expired"
            })
        
        session = self._ssh_sessions[session_id]
        progress_text = '\n'.join(session['progress'])
        
        if not session['completed']:
            # Still in progress - return progress template with polling
            return self._render_html('partials/ssh_validation_progress.html', {
                'session_id': session_id,
                'initial_message': progress_text
            })
        else:
            # Completed - return final result and clean up session
            result = session['result']
            result['edit_mode'] = session['edit_mode']
            # Clean up session data
            del self._ssh_sessions[session_id]
            return self._render_html('partials/ssh_validation_result.html', result)
    
    def _push_keys_and_validate_workflow(self, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete workflow: push keys → validate connection → detect capabilities"""
        progress_messages = []
        
        try:
            # Step 1: Test initial connection
            progress_messages.append("• Testing initial SSH connection...")
            initial_test = self._test_initial_ssh_connection(hostname, username, password, use_password)
            if not initial_test['success']:
                progress_messages.append(f"✗ Initial connection failed: {initial_test.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': '\n'.join(progress_messages)
                }
            progress_messages.append("✓ Initial SSH connection successful")
            
            # Step 2: Check for existing key in authorized_keys
            progress_messages.append("• Checking for existing Highball key in authorized_keys...")
            key_check = self._check_highball_key_in_authorized_keys(hostname, username)
            
            # Step 3: Push key if needed
            if not key_check['key_exists']:
                progress_messages.append("• Highball key not found, installing...")
                if not use_password:
                    progress_messages.append("✗ Password required to install key")
                    return {
                        'success': False,
                        'validation_message': '\n'.join(progress_messages)
                    }
                push_result = self._push_highball_key(hostname, username, password)
                if not push_result['success']:
                    progress_messages.append(f"✗ Key installation failed: {push_result.get('validation_message', 'Unknown error')}")
                    return {
                        'success': False,
                        'validation_message': '\n'.join(progress_messages)
                    }
                progress_messages.append("✓ Highball key installed successfully")
            else:
                progress_messages.append("✓ Highball key already present in authorized_keys")
            
            # Step 4: Copy keypair to remote host
            progress_messages.append("• Copying Highball keypair to remote host...")
            copy_result = self._copy_keypair_to_remote(hostname, username)
            if not copy_result['success']:
                progress_messages.append(f"✗ Keypair copy failed: {copy_result.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': '\n'.join(progress_messages)
                }
            progress_messages.append("✓ Keypair copied successfully")
            
            # Step 5: Test final connection and detect capabilities
            progress_messages.append("• Testing final connection and detecting capabilities...")
            final_test = self._test_connection_and_capabilities(hostname, username)
            if not final_test['success']:
                progress_messages.append(f"✗ Final connection test failed: {final_test.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': '\n'.join(progress_messages)
                }
            
            progress_messages.append("✓ All steps completed successfully!")
            
            return {
                'success': True,
                'validation_message': '\n'.join(progress_messages),
                'rsync_available': final_test.get('rsync_available', False),
                'container_runtime': final_test.get('container_runtime', None)
            }
            
        except Exception as e:
            progress_messages.append(f"✗ Workflow failed: {str(e)}")
            return {
                'success': False,
                'validation_message': '\n'.join(progress_messages)
            }
    
    @handle_page_errors("SSH workflow with session tracking")
    def _push_keys_and_validate_workflow_with_session(self, session_id: str, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete workflow with session progress tracking"""
        def log_progress(message):
            if hasattr(self, '_ssh_sessions') and session_id in self._ssh_sessions:
                self._ssh_sessions[session_id]['progress'].append(message)
        
        # Step 1: Test initial connection
        log_progress("• Testing initial SSH connection...")
        initial_test = self._test_initial_ssh_connection(hostname, username, password, use_password)
        if not initial_test['success']:
            log_progress(f"✗ Initial connection failed: {initial_test.get('validation_message', 'Unknown error')}")
            return {
                'success': False,
                'validation_message': initial_test.get('validation_message', 'Initial connection failed')
            }
        log_progress("✓ Initial SSH connection successful")
        
        # Step 2: Check for existing key in authorized_keys
        log_progress("• Checking for existing Highball key in authorized_keys...")
        key_check = self._check_highball_key_in_authorized_keys(hostname, username)
        
        # Step 3: Push key if needed
        if not key_check['key_exists']:
            log_progress("• Highball key not found, installing...")
            if not use_password:
                log_progress("✗ Password required to install key")
                return {
                    'success': False,
                    'validation_message': 'Password required to install key'
                }
            push_result = self._push_highball_key(hostname, username, password)
            if not push_result['success']:
                log_progress(f"✗ Key installation failed: {push_result.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': push_result.get('validation_message', 'Key installation failed')
                }
            log_progress("✓ Highball key installed successfully")
        else:
            log_progress("✓ Highball key already present in authorized_keys")
        
        # Step 4: Check for existing keypair files on remote host
        log_progress("• Checking for existing Highball keypair files...")
        keypair_check = self._check_highball_keypair_on_remote(hostname, username)
        
        # Step 5: Copy keypair if needed
        if not keypair_check['keypair_exists']:
            log_progress("• Highball keypair not found or doesn't match, copying...")
            copy_result = self._copy_keypair_to_remote(hostname, username)
            if not copy_result['success']:
                log_progress(f"✗ Keypair copy failed: {copy_result.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': copy_result.get('validation_message', 'Keypair copy failed')
                }
            log_progress("✓ Highball keypair copied successfully")
        else:
            log_progress("✓ Highball keypair already present and matches current keys")
        
        # Step 6: Test final connection and detect capabilities  
        final_test = self._test_connection_and_capabilities(hostname, username, log_progress)
        if not final_test['success']:
            return {
                'success': False,
                'validation_message': final_test.get('validation_message', 'Final connection test failed')
            }
        
        log_progress("✓ All steps completed successfully!")
        
        # Get all progress messages for final display
        all_progress = '\n'.join(self._ssh_sessions[session_id]['progress']) if hasattr(self, '_ssh_sessions') and session_id in self._ssh_sessions else "All steps completed successfully!"
        
        return {
            'success': True,
            'validation_message': all_progress,
            'rsync_available': final_test.get('rsync_available', False),
            'container_runtime': final_test.get('container_runtime', None)
        }
    
    @handle_page_errors("Initial SSH connection test")
    def _test_initial_ssh_connection(self, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Test initial SSH connection using password or existing key"""
        import subprocess
        
        if use_password:
            # Test connection with password using sshpass
            cmd = [
                'sshpass', '-p', password,
                'ssh', '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                'echo "INITIAL_SSH_OK"'
            ]
        else:
            # Test connection with existing key
            cmd = [
                'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
                '-o', 'ConnectTimeout=10',
                '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                'echo "INITIAL_SSH_OK"'
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and 'INITIAL_SSH_OK' in result.stdout:
            return {'success': True}
        else:
            return {
                'success': False,
                'validation_message': f'Initial SSH connection failed: {result.stderr.strip()}'
            }
    
    @handle_page_errors("Highball key existence check")
    def _check_highball_key_in_authorized_keys(self, hostname: str, username: str) -> dict:
        """Check if Highball public key exists in remote authorized_keys"""
        import subprocess
        
        # Read our public key
        with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
            our_pubkey = f.read().strip()
        
        # Extract the key part (without comment)
        key_parts = our_pubkey.split()
        if len(key_parts) >= 2:
            key_signature = key_parts[1]  # The actual key data
        else:
            return {
                'key_exists': False,
                'error': 'Invalid public key format'
            }
        
        # Check if this key exists in remote authorized_keys
        cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            f'grep -q "{key_signature}" ~/.ssh/authorized_keys 2>/dev/null && echo "KEY_EXISTS" || echo "KEY_MISSING"'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            if 'KEY_EXISTS' in result.stdout:
                return {'key_exists': True}
            else:
                return {'key_exists': False}
        else:
            # If command failed, assume key doesn't exist
            return {'key_exists': False}
    
    @handle_page_errors("Check Highball keypair on remote")
    def _check_highball_keypair_on_remote(self, hostname: str, username: str) -> dict:
        """Check if Highball keypair files exist on remote host and match our current keys"""
        import subprocess
        
        # Read our local keys
        with open('/config/local/secrets/.ssh/id_highball', 'r') as f:
            our_private_key = f.read().strip()
        with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
            our_public_key = f.read().strip()
        
        # Check if remote private key exists and matches
        private_check_cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            'test -f ~/.ssh/id_highball && cat ~/.ssh/id_highball'
        ]
        
        private_result = subprocess.run(private_check_cmd, capture_output=True, text=True, timeout=15)
        private_matches = (private_result.returncode == 0 and private_result.stdout.strip() == our_private_key)
        
        # Check if remote public key exists and matches  
        public_check_cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            'test -f ~/.ssh/id_highball.pub && cat ~/.ssh/id_highball.pub'
        ]
        
        public_result = subprocess.run(public_check_cmd, capture_output=True, text=True, timeout=15)
        public_matches = (public_result.returncode == 0 and public_result.stdout.strip() == our_public_key)
        
        return {
            'keypair_exists': private_matches and public_matches
        }
    
    @handle_page_errors("SSH key push")
    def _push_highball_key(self, hostname: str, username: str, password: str) -> dict:
        """Push Highball public key using manual authorized_keys append"""
        import subprocess
        
        # Read our public key
        with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
            public_key = f.read().strip()
        
        # Create .ssh directory and append key to authorized_keys
        cmd = [
            'sshpass', '-p', password,
            'ssh',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            f'mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo "{public_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return {'success': True}
        else:
            return {
                'success': False,
                'validation_message': f'Key installation failed: {result.stderr.strip()}'
            }
    
    @handle_page_errors("Keypair copy to remote")
    def _copy_keypair_to_remote(self, hostname: str, username: str) -> dict:
        """Copy id_highball and id_highball.pub to remote .ssh directory"""
        import subprocess
        
        # Ensure remote .ssh directory exists with correct permissions
        setup_cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            'mkdir -p ~/.ssh && chmod 700 ~/.ssh'
        ]
        
        setup_result = subprocess.run(setup_cmd, capture_output=True, text=True, timeout=15)
        if setup_result.returncode != 0:
            return {
                'success': False,
                'validation_message': f'Failed to setup remote .ssh directory: {setup_result.stderr.strip()}'
            }
        
        # Copy private key
        scp_private_cmd = [
            'scp', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '/config/local/secrets/.ssh/id_highball',
            f'{username}@{hostname}:~/.ssh/id_highball'
        ]
        
        private_result = subprocess.run(scp_private_cmd, capture_output=True, text=True, timeout=30)
        if private_result.returncode != 0:
            return {
                'success': False,
                'validation_message': f'Failed to copy private key: {private_result.stderr.strip()}'
            }
        
        # Copy public key
        scp_public_cmd = [
            'scp', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '/config/local/secrets/.ssh/id_highball.pub',
            f'{username}@{hostname}:~/.ssh/id_highball.pub'
        ]
        
        public_result = subprocess.run(scp_public_cmd, capture_output=True, text=True, timeout=30)
        if public_result.returncode != 0:
            return {
                'success': False,
                'validation_message': f'Failed to copy public key: {public_result.stderr.strip()}'
            }
        
        # Set correct permissions on private key
        chmod_cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            'chmod 600 ~/.ssh/id_highball'
        ]
        
        chmod_result = subprocess.run(chmod_cmd, capture_output=True, text=True, timeout=15)
        if chmod_result.returncode != 0:
            return {
                'success': False,
                'validation_message': f'Failed to set key permissions: {chmod_result.stderr.strip()}'
            }
        
        return {'success': True}
    
    @handle_page_errors("Connection and capability detection")
    def _test_connection_and_capabilities(self, hostname: str, username: str, log_progress=None) -> dict:
        """Test final connection and detect rsync/container capabilities"""
        import subprocess
        
        def log(msg):
            if log_progress:
                log_progress(msg)
        
        # Test basic SSH connectivity with key
        log("• Testing SSH connection with Highball key...")
        ssh_test_cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            'echo "SSH_FINAL_OK"'
        ]
        
        ssh_result = subprocess.run(ssh_test_cmd, capture_output=True, text=True, timeout=15)
        if ssh_result.returncode != 0 or 'SSH_FINAL_OK' not in ssh_result.stdout:
            log(f"✗ SSH connection test failed: {ssh_result.stderr.strip()}")
            return {
                'success': False,
                'validation_message': f'SSH connection test failed: {ssh_result.stderr.strip()}'
            }
        log("✓ SSH connection test successful")
        
        # Test rsync availability
        log("• Testing rsync availability...")
        rsync_cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            'rsync --version 2>/dev/null | head -1 || echo "RSYNC_MISSING"'
        ]
        
        rsync_result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=15)
        rsync_available = (rsync_result.returncode == 0 and 
                         'rsync' in rsync_result.stdout.lower() and 
                         'RSYNC_MISSING' not in rsync_result.stdout)
        log(f"✓ Rsync test complete - {'available' if rsync_available else 'not available'}")
        
        # Test container runtime (try docker first, then podman)
        log("• Testing container runtime availability...")
        container_runtime = None
        for runtime in ['docker', 'podman']:
            log(f"• Testing {runtime}...")
            runtime_cmd = [
                'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
                '-o', 'ConnectTimeout=10',
                '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                f'{runtime} --version 2>/dev/null || echo "{runtime.upper()}_MISSING"'
            ]
            
            runtime_result = subprocess.run(runtime_cmd, capture_output=True, text=True, timeout=15)
            if (runtime_result.returncode == 0 and 
                runtime in runtime_result.stdout.lower() and 
                f'{runtime.upper()}_MISSING' not in runtime_result.stdout):
                container_runtime = runtime
                log(f"✓ {runtime} detected and available")
                break
            else:
                log(f"✓ {runtime} test complete - not available")
        
        if not container_runtime:
            log("✓ Container runtime test complete - none detected")
        
        # Build validation message
        capabilities = []
        if rsync_available:
            capabilities.append('rsync')
        if container_runtime:
            capabilities.append(f'{container_runtime} runtime')
        
        if capabilities:
            message = f'Connection successful - detected: {", ".join(capabilities)}'
        else:
            message = 'Connection successful - no rsync or container runtime detected'
        
        log("✓ Capability detection complete")
        
        return {
            'success': True,
            'validation_message': message,
            'rsync_available': rsync_available,
            'container_runtime': container_runtime
        }
    
    @handle_page_errors("Toggle SSH auth method")
    def toggle_ssh_auth_method(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Toggle between Highball and user SSH authentication methods"""
        ssh_highball = 'ssh_highball' in form_data
        
        if ssh_highball:
            # Checkbox checked: show password field for automatic key installation
            template = 'partials/ssh_auth_highball.html'
            template_context = {}
        else:
            # Checkbox unchecked: show manual key copy instructions
            template = 'partials/ssh_auth_user.html'
            # Read Highball public key for display
            template_context = {
                'highball_public_key': self._get_highball_public_key()
            }
        
        return self._render_html(template, template_context)
    
    def _get_highball_public_key(self) -> str:
        """Read Highball public key content"""
        try:
            with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
                return f.read().strip()
        except Exception as e:
            return f"Error reading public key: {str(e)}"
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Helper to safely get form values handling both list and string formats"""
        value = form_data.get(field_name, [default])
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)
    
    @handle_page_errors("Destination validation")
    def validate_destination(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Validate destination configuration"""
        dest_type = self._get_form_value(form_data, 'dest_type', '')
        hostname = self._get_form_value(form_data, 'hostname', '')
        
        if not dest_type or not hostname:
            template_context = {
                'success': False,
                'validation_message': 'Destination type and hostname are required for validation'
            }
        else:
            # Test basic connectivity based on destination type
            if dest_type == 'rsync':
                template_context = self._validate_rsync_destination(form_data)
            elif dest_type == 'rsyncd':
                template_context = self._validate_rsyncd_destination(form_data)
            elif dest_type == 'restic':
                template_context = self._validate_restic_destination(form_data)
            else:
                template_context = {
                    'success': False,
                    'validation_message': f'Validation not implemented for destination type: {dest_type}'
                }
        
        # Generate URI preview
        if template_context.get('success'):
            from models.forms import DestinationParser
            uri_result = DestinationParser.build_destination_uri(dest_type, form_data)
            if uri_result['valid']:
                template_context['uri_generated'] = uri_result['uri']
        
        return self._render_html('partials/destination_validation_result.html', template_context)
    
    def _validate_rsync_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rsync (SSH) destination"""
        hostname = self._get_form_value(form_data, 'hostname', '')
        username = self._get_form_value(form_data, 'username', '')
        path = self._get_form_value(form_data, 'path', '')
        port = self._get_form_value(form_data, 'port', '22')
        
        if not all([hostname, username, path]):
            return {
                'success': False,
                'validation_message': 'Hostname, username, and path are required for rsync validation'
            }
        
        # Test SSH connectivity (reuse existing SSH validation)
        ssh_config = {
            'hostname': hostname,
            'username': username,
            'port': int(port) if port.isdigit() else 22
        }
        
        from models.validation import ValidationService
        validation_service = ValidationService()
        result = validation_service.validate_ssh_source(ssh_config)
        
        if result['valid']:
            return {
                'success': True,
                'validation_message': f"SSH connection successful to {hostname}. Path writability not tested."
            }
        else:
            return {
                'success': False,
                'validation_message': f"SSH connection failed: {result.get('error', 'Unknown error')}"
            }
    
    def _validate_rsyncd_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rsyncd destination"""
        hostname = self._get_form_value(form_data, 'hostname', '')
        share = self._get_form_value(form_data, 'share', '')
        port = self._get_form_value(form_data, 'port', '873')
        
        if not all([hostname, share]):
            return {
                'success': False,
                'validation_message': 'Hostname and share are required for rsyncd validation'
            }
        
        # Test rsyncd connectivity
        import subprocess
        try:
            port_num = int(port) if port.isdigit() else 873
            cmd = ['rsync', '--list-only', f'rsync://{hostname}:{port_num}/{share}']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'validation_message': f"Rsyncd connection successful to {hostname}:{port_num}/{share}"
                }
            else:
                return {
                    'success': False,
                    'validation_message': f"Rsyncd connection failed: {result.stderr.strip() or 'Connection error'}"
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'validation_message': 'Rsyncd connection timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'validation_message': f'Rsyncd validation error: {str(e)}'
            }
    
    def _validate_restic_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate restic destination"""
        repo_type = self._get_form_value(form_data, 'repo_type', '')
        password = self._get_form_value(form_data, 'restic_password', '')
        
        if not repo_type:
            return {
                'success': False,
                'validation_message': 'Repository type is required for restic validation'
            }
        
        if not password:
            return {
                'success': False,
                'validation_message': 'Repository password is required for restic validation'
            }
        
        # For now, just validate that we can build the URI
        # Full restic validation would require container execution
        from models.forms import DestinationParser
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        
        if uri_result['valid']:
            return {
                'success': True,
                'validation_message': f"Restic repository URI generated successfully. Full connectivity test requires repository initialization."
            }
        else:
            return {
                'success': False,
                'validation_message': f"Restic repository configuration error: {uri_result.get('error', 'Unknown error')}"
            }

    @handle_page_errors("Destination type fields")
    def destination_type_fields(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Load destination type-specific fields (HTMX partial)"""
        dest_type = self._get_form_value(form_data, 'dest_type', '')
        
        if dest_type == 'rsync':
            template = 'partials/dest_rsync_fields.html'
        elif dest_type == 'rsyncd':
            template = 'partials/dest_rsyncd_fields.html'
        elif dest_type == 'restic':
            template = 'partials/dest_restic_fields.html'
        else:
            return HTMLResponse(content='')
        
        html = self.template_service.render_template(template)
        return HTMLResponse(content=html)
    
    @handle_page_errors("Toggle SSH passphrase field")
    def toggle_ssh_passphrase(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Toggle SSH passphrase field visibility"""
        requires_passphrase = 'requires_passphrase' in form_data
        
        if requires_passphrase:
            template = 'partials/ssh_passphrase_field.html'
            html = self.template_service.render_template(template)
        else:
            html = ''
        
        return HTMLResponse(content=html)

    @handle_page_errors("Network scan")
    def scan_network_for_rsyncd(self, network_range: str) -> HTMLResponse:
        """Scan network for rsyncd services"""
        # Basic network scanning functionality
        import subprocess
        
        # Use nmap to scan for rsyncd (port 873)
        cmd = ['nmap', '-p', '873', '--open', network_range]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        scan_results = []
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            current_host = None
            
            for line in lines:
                line = line.strip()
                if 'Nmap scan report for' in line:
                    current_host = line.split('for ')[-1]
                elif '873/tcp open' in line and current_host:
                    scan_results.append({
                        'host': current_host,
                        'port': 873,
                        'service': 'rsyncd'
                    })
        
        template_data = {
            'network_range': network_range,
            'scan_results': scan_results,
            'page_title': 'Network Scan Results'
        }
        
        html = self.template_service.render_template('pages/network_scan.html', **template_data)
        return HTMLResponse(content=html)

    # Job name extraction now handled by FastAPI Query() parameters

    # Job config validation now handled inline in HTMX methods

    def _check_and_respond_repository_status_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check repository availability and return appropriate HTMX HTML response"""
        dest_type = job_config.get('dest_type')
        
        if dest_type == 'restic':
            return self._check_restic_repository_html(job_name, job_config)
        else:
            # Non-restic repositories - assume available for now
            html = self.template_service.render_template('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': dest_type
            })
            return HTMLResponse(content=html)

    def _check_restic_repository_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check restic repository availability and return HTML response"""
        dest_config = job_config.get('dest_config', {})
        repo_uri = dest_config.get('repo_uri')
        
        if not repo_uri:
            html = self.template_service.render_template('partials/error_message.html', 
                                                       error_message='Repository URI not configured')
            return HTMLResponse(content=html)
            
        from models.backup import backup_service
        check_success, check_message = backup_service.repository_service._quick_repository_check(repo_uri, dest_config)
        
        if check_success:
            html = self.template_service.render_template('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': 'restic'
            })
            return HTMLResponse(content=html)
        else:
            return self._send_repository_error_html(job_name, check_message)

    # Repository response methods now return HTMLResponse directly

    def _send_repository_error_html(self, job_name: str, error_message: str) -> HTMLResponse:
        """Send appropriate repository error HTMX partial based on error type"""
        if error_message and ('locked by' in error_message.lower() or 'repository is already locked' in error_message.lower()):
            # Repository locked - render unlock interface
            html = self.template_service.render_template('partials/repository_locked_error.html', {
                'job_name': job_name,
                'error_message': error_message
            })
            return HTMLResponse(content=html)
        else:
            # Other error - render error template
            html = self.template_service.render_template('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'connection_error',
                'error_message': error_message or 'Unknown error'
            })
            return HTMLResponse(content=html)

    def _build_ssh_config_from_form(self, form_data: Dict[str, Any]) -> Dict[str, str]:
        """Build SSH configuration from form data"""
        hostname = form_data.get('hostname', [''])[0]
        username = form_data.get('username', [''])[0]
        return {'hostname': hostname, 'username': username}

    def _validate_individual_paths(self, source_type: str, source_paths: List[Dict[str, Any]], ssh_config: Dict[str, str]) -> List[Dict[str, Any]]:
        """Validate each individual source path"""
        from models.validation import ValidationService
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
            html = self.template_service.render_template('partials/error_message.html', 
                                                       error_message='Job name is required')
            return HTMLResponse(content=html)
        
        # Get and validate job configuration
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            html = self.template_service.render_template('partials/error_message.html', 
                                                       error_message=f"Job '{job_name}' not found")
            return HTMLResponse(content=html)
        
        job_config = jobs[job_name]
        # Perform repository availability check and return response
        return self._check_and_respond_repository_status_html(job_name, job_config)

    @handle_page_errors("Repository unlock")
    def unlock_repository_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository unlock"""
        
        if not job_name:
            html = self.template_service.render_template('partials/error_message.html', 
                                                       error_message='Job name is required')
            return HTMLResponse(content=html)
            
        # Get and validate job configuration
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            html = self.template_service.render_template('partials/error_message.html', 
                                                       error_message=f"Job '{job_name}' not found")
            return HTMLResponse(content=html)
        
        job_config = jobs[job_name]
        dest_type = job_config.get('dest_type')
        
        if dest_type != 'restic':
            html = self.template_service.render_template('partials/error_message.html', 
                                                       error_message='Unlock is only supported for restic repositories')
            return HTMLResponse(content=html)

        # Execute restic unlock command
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        from models.backup import backup_service
        result = backup_service.unlock_repository(dest_config, source_config)
        
        if result.get('success'):
            # Unlock successful - automatically retry availability check
            return self.check_repository_availability_htmx(job_name)
        else:
            # Unlock failed - show error
            html = self.template_service.render_template('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'unlock_failed',
                'error_message': result.get('error', 'Unlock failed')
            })
            return HTMLResponse(content=html)


