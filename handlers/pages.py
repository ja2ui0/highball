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
from typing import Dict, Any, List, Optional
from datetime import datetime

# FastAPI imports
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

# Import models for unified validation and forms
from models.validation import validation_service
from models.forms import job_parser

# Import services
from services.template import TemplateService
from services.data_services import JobFormDataBuilder, DestinationTypeService

logger = logging.getLogger(__name__)

def handle_page_errors(operation_name: str):
    """Decorator to handle common page operation errors consistently"""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
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

class GETHandlers:
    """Handler for all read-only page rendering operations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        from handlers.api import ResponseUtils
        self.response_utils = ResponseUtils(template_service)
    
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
        
        html = self.template_service.render_template('pages/dashboard.html', **template_data)
        return HTMLResponse(content=html)
    
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
        
        html = self.template_service.render_template('pages/job_form.html', **form_data)
        return HTMLResponse(content=html)
    
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
            error_html = self.template_service.render_template('pages/error.html', 
                error_message="Job name is required", page_title="Error")
            return HTMLResponse(content=error_html, status_code=400)
        
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            error_html = self.template_service.render_template('pages/error.html', 
                error_message=f"Job '{job_name}' not found", page_title="Error")
            return HTMLResponse(content=error_html, status_code=404)
        
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
        
        html = self.template_service.render_template('pages/job_form.html', **form_data)
        return HTMLResponse(content=html)
    
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
            
        html = self.template_service.render_template('pages/config_manager.html', **template_data)
        return HTMLResponse(content=html)
    
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
        
        html = self.template_service.render_template('pages/config_editor.html', **template_data)
        return HTMLResponse(content=html)
    
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
    
    def _send_error(self, request_handler, message: str, status_code: int = 500):
        """Send error response using template partial"""
        request_handler.send_response(status_code)
        request_handler.send_header('Content-type', 'text/html')
        request_handler.end_headers()
        
        # Render error template
        html = self.template_service.render_template('pages/error.html', 
                                                   error_message=message,
                                                   page_title='Error')
        request_handler.wfile.write(html.encode())

    @handle_page_errors("Job inspection")
    def show_job_inspect(self, job_name: str = "") -> HTMLResponse:
        """Show job inspection page"""
        if not job_name:
            error_html = self.template_service.render_template('pages/error.html', 
                error_message="Job name is required", page_title="Error")
            return HTMLResponse(content=error_html, status_code=400)
        
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            error_html = self.template_service.render_template('pages/error.html', 
                error_message=f"Job '{job_name}' not found", page_title="Error")
            return HTMLResponse(content=error_html, status_code=404)
        
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
        
        html = self.template_service.render_template('pages/job_inspect.html', **template_data)
        return HTMLResponse(content=html)

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
        
        html = self.template_service.render_template('pages/dev_logs.html', **template_data)
        return HTMLResponse(content=html)
    
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


class POSTHandlers:
    """Handler for all form submissions and mutations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        from handlers.api import ResponseUtils
        self.response_utils = ResponseUtils(template_service)
    
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
    def save_backup_job(self, request_handler, form_data: Dict[str, Any]):
        """Save backup job from form submission"""
        # Parse job form data using unified parser
        job_result = job_parser.parse_job_form(form_data)
        
        if not job_result['valid']:
            self._send_job_form_error(request_handler, form_data, job_result['error'])
            return
        
        # Build and save job configuration
        job_name = job_result['job_name']
        job_config = self._build_job_config_from_result(job_result)
        
        # Save to config
        success = self.backup_config.save_job(job_name, job_config)
        
        if success:
            self.response_utils.send_redirect(request_handler, '/dashboard')
        else:
            self._send_job_form_error(request_handler, form_data, "Failed to save job configuration")

    @handle_page_errors("Delete job")
    def delete_backup_job(self, request_handler, job_name: str):
        """Delete backup job"""
        if not job_name:
            raise ValueError("Job name is required")
        
        success = self.backup_config.delete_backup_job(job_name)
        
        if success:
            self.response_utils.send_redirect(request_handler, '/dashboard')
        else:
            raise Exception(f"Failed to delete job '{job_name}'")

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
    def save_raw_config(self, request_handler, form_data: Dict[str, Any]):
        """Save raw YAML configuration"""
        raw_config = form_data.get('raw_config', [''])[0]
        
        # Validate YAML syntax
        try:
            import yaml
            yaml.safe_load(raw_config)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {str(e)}")
        
        # Save to file
        config_path = self.backup_config.config_file
        with open(config_path, 'w') as f:
            f.write(raw_config)
        
        # Reload configuration
        self.backup_config.reload_config()
        
        self.response_utils.send_redirect(request_handler, '/config')

    @handle_page_errors("Save config")
    def save_structured_config(self, request_handler, form_data: Dict[str, Any]):
        """Save structured configuration from form"""
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
        self.response_utils.send_redirect(request_handler, '/config')

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
    def preview_config_changes(self, request_handler, form_data: Dict[str, Any]):
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
        html = self.template_service.render_template('partials/config_preview.html', 
                                                   preview_yaml=preview_yaml,
                                                   success=True)
        self.response_utils.send_html_response(request_handler, html)


class ValidationHandlers:
    """Handler for all validation endpoints and AJAX operations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        from handlers.api import ResponseUtils
        self.response_utils = ResponseUtils(template_service)
    
    def _send_json_response(self, request_handler, data: Dict[str, Any]):
        """Send JSON response"""
        import json
        request_handler.send_response(200)
        request_handler.send_header('Content-type', 'application/json')
        request_handler.end_headers()
        request_handler.wfile.write(json.dumps(data).encode())
    
    def _send_error(self, request_handler, message: str, status_code: int = 500):
        """Send error response using template partial"""
        request_handler.send_response(status_code)
        request_handler.send_header('Content-type', 'text/html')
        request_handler.end_headers()
        
        # Render error template
        error_html = self.template_service.render_template('error.html', 
            error_message=message,
            status_code=status_code
        )
        request_handler.wfile.write(error_html.encode())
    
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
        from services.validation import ValidationService
        validation_service = ValidationService()
        result = validation_service.validate_ssh_source(ssh_config)
        return JSONResponse(content=result)

    @handle_page_errors("Path validation")
    def validate_source_paths(self, request_handler, form_data: Dict[str, Any]):
        """Validate source paths from form"""
        # Parse source paths from form
        from models.forms import source_paths_parser
        paths_result = source_paths_parser.parse_multi_path_options(form_data)
        
        if not paths_result['valid']:
            self.response_utils.send_json_response(request_handler, paths_result)
            return
        
        # Build SSH configuration and validate paths
        source_type = form_data.get('source_type', ['local'])[0]
        ssh_config = self._build_ssh_config_from_form(form_data) if source_type == 'ssh' else {}
        validation_results = self._validate_individual_paths(source_type, paths_result['source_paths'], ssh_config)
        
        self.response_utils.send_json_response(request_handler, {
            'valid': True,
            'results': validation_results
        })


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

    def _extract_job_name_parameter(self, request_handler, job_name=None) -> str:
        """Extract job name from parameter or query string"""
        if job_name:
            return job_name
            
        from urllib.parse import urlparse, parse_qs
        url_parts = urlparse(request_handler.path)
        params = parse_qs(url_parts.query)
        return params.get('job', [''])[0]

    def _get_validated_job_config(self, request_handler, job_name: str):
        """Get job config and validate it exists, send error if not"""
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            self.response_utils.send_htmx_error(request_handler, f"Job '{job_name}' not found")
            return None
        return jobs[job_name]

    def _check_and_respond_repository_status(self, request_handler, job_name: str, job_config: Dict[str, Any]):
        """Check repository availability and send appropriate HTMX response"""
        dest_type = job_config.get('dest_type')
        
        if dest_type == 'restic':
            self._check_restic_repository(request_handler, job_name, job_config)
        else:
            # Non-restic repositories - assume available for now
            self._send_repository_available_response(request_handler, job_name, dest_type)

    def _check_restic_repository(self, request_handler, job_name: str, job_config: Dict[str, Any]):
        """Check restic repository availability and respond"""
        dest_config = job_config.get('dest_config', {})
        repo_uri = dest_config.get('repo_uri')
        
        if not repo_uri:
            self.response_utils.send_htmx_error(request_handler, 'Repository URI not configured')
            return
            
        from models.backup import backup_service
        check_success, check_message = backup_service.repository_service._quick_repository_check(repo_uri, dest_config)
        
        if check_success:
            self._send_repository_available_response(request_handler, job_name, 'restic')
        else:
            self._send_repository_error_response(request_handler, job_name, check_message)

    def _send_repository_available_response(self, request_handler, job_name: str, job_type: str):
        """Send repository available HTMX partial"""
        self.response_utils.send_htmx_partial(request_handler, 'partials/repository_available.html', {
            'job_name': job_name,
            'job_type': job_type
        })

    def _send_repository_error_response(self, request_handler, job_name: str, error_message: str):
        """Send appropriate repository error HTMX partial based on error type"""
        if error_message and ('locked by' in error_message.lower() or 'repository is already locked' in error_message.lower()):
            # Repository locked - render unlock interface
            self.response_utils.send_htmx_partial(request_handler, 'partials/repository_locked_error.html', {
                'job_name': job_name,
                'error_message': error_message
            })
        else:
            # Other error - render error template
            self.response_utils.send_htmx_partial(request_handler, 'partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'connection_error',
                'error_message': error_message or 'Unknown error'
            })

    def _build_ssh_config_from_form(self, form_data: Dict[str, Any]) -> Dict[str, str]:
        """Build SSH configuration from form data"""
        hostname = form_data.get('hostname', [''])[0]
        username = form_data.get('username', [''])[0]
        return {'hostname': hostname, 'username': username}

    def _validate_individual_paths(self, source_type: str, source_paths: List[Dict[str, Any]], ssh_config: Dict[str, str]) -> List[Dict[str, Any]]:
        """Validate each individual source path"""
        from services.validation import ValidationService
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
    def check_repository_availability_htmx(self, request_handler, job_name=None):
        """HTMX endpoint for repository availability check"""
        job_name = self._extract_job_name_parameter(request_handler, job_name)
        
        if not job_name:
            self.response_utils.send_htmx_error(request_handler, 'Job name is required')
            return
        
        # Get and validate job configuration
        job_config = self._get_validated_job_config(request_handler, job_name)
        if not job_config:
            return
        # Perform repository availability check and send response
        self._check_and_respond_repository_status(request_handler, job_name, job_config)

    @handle_page_errors("Repository unlock")
    def unlock_repository_htmx(self, request_handler, job_name=None):
        """HTMX endpoint for repository unlock"""
        job_name = self._extract_job_name_parameter(request_handler, job_name)
        
        if not job_name:
            self.response_utils.send_htmx_error(request_handler, 'Job name is required')
            return
            
        # Get and validate job configuration
        job_config = self._get_validated_job_config(request_handler, job_name)
        if not job_config:
            return
            
        dest_type = job_config.get('dest_type')
        
        if dest_type != 'restic':
            self.response_utils.send_htmx_error(request_handler, 'Unlock is only supported for restic repositories')
            return

        # Execute restic unlock command
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        from models.backup import backup_service
        result = backup_service.unlock_repository(dest_config, source_config)
        
        if result.get('success'):
            # Unlock successful - automatically retry availability check
            self.check_repository_availability_htmx(request_handler, job_name)
        else:
            # Unlock failed - show error
            self.response_utils.send_htmx_partial(request_handler, 'partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'unlock_failed',
                'error_message': result.get('error', 'Unlock operation failed')
            })


