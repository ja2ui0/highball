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
from jobs.services.validate import validation_service
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
        # Initialize system logging service
        from services.management import SystemLoggingService
        self.system_logging_service = SystemLoggingService()
        # ResponseUtils removed - all methods now return FastAPI responses directly
    
    
    @handle_page_errors("Dashboard")
    
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
        from admin.schema import PROVIDER_FIELD_SCHEMAS
        
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
        # Delegate to system logging service - this is pure business logic
        return self.system_logging_service.get_system_logs(log_type)


class POSTHandlers(BaseHandler):
    """Handler for all form submissions and mutations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        # Initialize form processing handler
        from handlers.forms import FormProcessingHandler
        self.form_processor = FormProcessingHandler(backup_config)
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
        from admin.schema import PROVIDER_FIELD_SCHEMAS
        
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
        from admin.schema import PROVIDER_FIELD_SCHEMAS
        
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
        
        from jobs.services.validate import ValidationService
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
    
    # =============================================================================
    # DESTINATION MANAGEMENT HANDLERS
    # =============================================================================
    
class ValidationHandlers(BaseHandler):
    """Handler for all validation endpoints and AJAX operations"""
    
    def __init__(self, backup_config, template_service: TemplateService, job_form_builder):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_form_builder = job_form_builder
        # Initialize destination validation handler
        from handlers.forms import DestinationValidationHandler
        self.destination_validator = DestinationValidationHandler()
        # ResponseUtils removed - all methods now return FastAPI responses directly
    
    # CGI utility methods removed - all handlers now return FastAPI responses directly
    
    
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Helper to safely get form values handling both list and string formats"""
        value = form_data.get(field_name, [default])
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)
    

    # Job name extraction now handled by FastAPI Query() parameters

    # Job config validation now handled inline in HTMX methods





