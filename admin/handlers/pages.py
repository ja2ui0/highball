"""
Admin Page Handlers
System configuration, settings management, and debugging
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

# Import services
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

class AdminHandler(BaseHandler):
    """Handle system administration and configuration"""
    
    def __init__(self):
        self.backup_config = BackupConfig()
        self.template_service = TemplateService(self.backup_config)
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Helper to get form value with default"""
        return form_data.get(field_name, default)

    def _get_available_themes(self):
        """Get list of available theme files from static/themes directory"""
        themes_dir = Path('static/themes')
        if not themes_dir.exists():
            return ['dark', 'light']  # Fallback themes
        
        themes = []
        for theme_file in themes_dir.glob('*.css'):
            theme_name = theme_file.stem
            themes.append(theme_name)
        
        return sorted(themes)

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

    @handle_page_errors("Dev logs")
    def show_dev_logs(self, log_type: str = 'app') -> HTMLResponse:
        """Show development logs and debugging interface"""
        log_data = self._get_system_logs(log_type)
        template_data = {
            'log_data': log_data,
            'log_type': log_type,
            'page_title': f'{log_type.title()} Logs'
        }
        return self._render_html('pages/dev_logs.html', template_data)
    
    def _get_system_logs(self, log_type: str) -> List[str]:
        """Get system log entries based on type"""
        # Simplified implementation for now - would be expanded with actual log reading logic
        return [f"Sample {log_type} log entry 1", f"Sample {log_type} log entry 2"]

    def _update_notification_settings(self, global_settings: dict, form_data: Dict[str, Any]):
        """Update notification settings in global_settings from form data"""
        from admin.schema import PROVIDER_FIELD_SCHEMAS
        
        notification_config = global_settings.setdefault('notification', {})
        
        # Process each provider's configuration
        for provider_name, provider_schema in PROVIDER_FIELD_SCHEMAS.items():
            # Only process if provider fields are present in form
            if any(f"{provider_name}_{field['name']}" in form_data for field in provider_schema):
                provider_config = notification_config.setdefault(provider_name, {})
                
                # Process individual fields
                for field_info in provider_schema:
                    self._process_notification_field(provider_config, provider_name, field_info, form_data)
                
                # Handle all sections (smtp_config, queue_settings, etc.)
                for section_name in ['smtp_config', 'queue_settings', 'retry_settings']:
                    if section_name in provider_config:
                        for field_info in provider_config[section_name]:
                            self._process_notification_field(provider_config, provider_name, field_info, form_data)

    def _process_notification_field(self, provider_config: dict, provider_name: str, field_info: dict, form_data: Dict[str, Any]):
        """Process a single notification field from form data"""
        field_name = f"{provider_name}_{field_info['name']}"
        
        if field_info['type'] == 'checkbox':
            provider_config[field_info['name']] = field_name in form_data
        elif field_info['type'] == 'select':
            # Handle select with config_field mapping (e.g., encryption)
            select_value = self._get_form_value(form_data, field_name, '')
            
            if 'options' in field_info:
                # Reset all config_field booleans first
                for option in field_info['options']:
                    if 'config_field' in option:
                        provider_config[option['config_field']] = False
                
                # Set the selected option's config_field to True
                for option in field_info['options']:
                    if option['value'] == select_value and 'config_field' in option:
                        provider_config[option['config_field']] = True
        elif field_info['type'] == 'number':
            value = self._get_form_value(form_data, field_name, '0')
            try:
                provider_config[field_info['name']] = int(value)
            except ValueError:
                provider_config[field_info['name']] = field_info.get('placeholder', 0)
        else:
            # text, password, email, etc.
            provider_config[field_info['name']] = self._get_form_value(form_data, field_name, '')

    @handle_page_errors("Save raw config")
    def save_raw_config(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save raw YAML configuration"""
        try:
            raw_config = form_data.get('raw_config', [''])[0]
            
            # Validate YAML syntax
            try:
                yaml.safe_load(raw_config)
            except yaml.YAMLError as e:
                return JSONResponse(content={
                    'success': False,
                    'error': f'Invalid YAML syntax: {str(e)}'
                }, status_code=400)
            
            # Save to file
            config_path = self.backup_config.config_file
            with open(config_path, 'w') as f:
                f.write(raw_config)
            
            # Reload configuration
            self.backup_config.reload_config()
            
            return RedirectResponse(url='/config', status_code=302)
        except Exception as e:
            return JSONResponse(content={
                'success': False,
                'error': f'Configuration save failed: {str(e)}'
            }, status_code=500)

    @handle_page_errors("Save config")
    def save_structured_config(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save structured configuration from form"""
        try:
            # Get current configuration and update global settings
            global_settings = self.backup_config.config.setdefault('global_settings', {})
            
            # Update basic settings
            global_settings['scheduler_timezone'] = self._get_form_value(form_data, 'scheduler_timezone', 'UTC')
            
            # Update theme if provided
            theme = self._get_form_value(form_data, 'theme', '')
            if theme:
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
        
        # Process each provider's configuration
        from admin.schema import PROVIDER_FIELD_SCHEMAS
        for provider_name, provider_schema in PROVIDER_FIELD_SCHEMAS.items():
            # Only process if provider fields are present in form
            if any(f"{provider_name}_{field['name']}" in form_data for field in provider_schema):
                provider_config = notification_config.setdefault(provider_name, {})
                
                # Process individual fields
                for field_info in provider_schema:
                    self._process_notification_field(provider_config, provider_name, field_info, form_data)
                
                # Handle all sections (smtp_config, queue_settings, etc.)
                for section_name in ['smtp_config', 'queue_settings', 'retry_settings']:
                    if section_name in provider_config:
                        for field_info in provider_config[section_name]:
                            self._process_notification_field(provider_config, provider_name, field_info, form_data)

    @handle_page_errors("Preview config")
    def preview_config_changes(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Preview configuration changes without saving"""
        # Build the configuration that would be saved (without actually saving)
        preview_config = {}
        global_settings = preview_config.setdefault('global_settings', {})
        
        # Update basic settings
        global_settings['scheduler_timezone'] = self._get_form_value(form_data, 'scheduler_timezone', 'UTC')
        
        # Update theme if provided
        theme = self._get_form_value(form_data, 'theme', '')
        if theme:
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
        preview_yaml = yaml.dump(preview_config, default_flow_style=False, indent=2)
        
        # Render preview partial
        return self._render_html('partials/config_preview.html', {
            'preview_yaml': preview_yaml,
            'success': True
        })

    # =============================================================================
    # NOTIFICATION PROVIDER MANAGEMENT - Admin pillar methods
    # =============================================================================

    def _render_error(self, message):
        """Render error message"""
        import html
        return self.template_service.render_template('partials/error_message.html',
                                                   message=html.escape(message))

    async def add_global_notification_provider_htmx(self, request) -> HTMLResponse:
        """Add a new global notification provider to config manager - HTMX handler"""
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

        # Business logic (preserve original implementation)
        provider = self._get_form_value(form_data, 'add_provider')
        if not provider or provider not in ['telegram', 'email']:
            html_response = self._render_error("Invalid provider selection")
        else:
            # TODO: Add provider to global config and render updated notification section
            html_response = self.template_service.render_template('partials/notification_provider_added.html',
                                                                provider=provider)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    async def remove_global_notification_provider_htmx(self, request) -> HTMLResponse:
        """Remove a global notification provider from config manager - HTMX handler"""
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

        # Business logic (preserve original implementation)
        provider = self._get_form_value(form_data, 'provider')
        if not provider or provider not in ['telegram', 'email']:
            html_response = self._render_error("Invalid provider")
        else:
            # TODO: Remove provider from global config and render updated notification section
            html_response = self.template_service.render_template('partials/notification_provider_removed.html',
                                                                provider=provider)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    # =============================================================================
    # LOG MANAGEMENT - Admin pillar methods
    # =============================================================================

    async def clear_logs_htmx(self, request) -> HTMLResponse:
        """Clear logs using existing pages handler functionality - HTMX handler"""
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

        # Business logic (preserve original implementation)
        # Connect to existing _get_system_logs in pages.py for log clearing
        html_response = self.template_service.render_template('partials/log_cleared.html')

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    async def refresh_logs_htmx(self, request) -> HTMLResponse:
        """Refresh logs using existing pages handler log system - HTMX handler"""
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

        # Business logic (preserve original implementation)
        job_name = self._get_form_value(form_data, 'job_name')
        html_response = self.template_service.render_template('partials/logs_refreshed.html', 
                                                           job_name=job_name)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    # =============================================================================
    # QUEUE SETTINGS - Admin pillar methods
    # =============================================================================

    async def handle_queue_settings_htmx(self, request) -> HTMLResponse:
        """Handle notification queue settings using existing queue system - HTMX handler"""
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

        # Business logic (preserve original implementation)
        provider = self._get_form_value(form_data, 'provider')
        enabled = self._get_form_value(form_data, 'enabled') == 'true'
        
        # Connect to existing notification queue system
        html_response = self.template_service.render_template('partials/queue_settings.html',
                                                           provider=provider,
                                                           enabled=enabled)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    # =============================================================================
    # FIELD RENDERING - Admin pillar methods
    # =============================================================================

    async def render_cron_field_htmx(self, request) -> HTMLResponse:
        """Render cron field using existing template logic - HTMX handler"""
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

        # Business logic (preserve original implementation)
        schedule = self._get_form_value(form_data, 'schedule')
        cron_pattern = self._get_form_value(form_data, 'cron_pattern')
        
        html_response = self.template_service.render_template('partials/cron_field.html',
                                                           schedule=schedule,
                                                           cron_pattern=cron_pattern,
                                                           show_field=(schedule == 'custom'))

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    async def toggle_password_visibility_htmx(self, request) -> HTMLResponse:
        """Toggle password field visibility state - HTMX handler"""
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

        # Business logic (preserve original implementation)
        field_id = self._get_form_value(form_data, 'field_id')
        current_hidden = self._get_form_value(form_data, 'hidden') == 'true'
        new_hidden = not current_hidden
        
        html_response = self.template_service.render_template('partials/password_field.html',
                                                           field_id=field_id,
                                                           field_name=field_id,  # Assume same as ID
                                                           field_value='',  # Don't echo passwords for security
                                                           hidden=new_hidden)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    # =============================================================================
    # CONFIG PREVIEW AND FORM PROCESSING - Admin pillar methods
    # =============================================================================

    async def preview_config_htmx(self, request) -> HTMLResponse:
        """Generate and display job config preview - HTMX handler"""
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

        # Business logic (preserve original implementation)
        try:
            if not form_data:
                html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                       preview_content="Error: No form data received")
                return HTMLResponse(content=html_response)
            
            # Parse the form data using the existing parser
            from models.forms import JobFormParser
            parser = JobFormParser()
            
            result = parser.parse_job_form(form_data)
            
            if not result.get('valid', False):
                error_msg = result.get('error', 'Unknown parsing error')
                # Add some debug info to the error
                from models.forms import safe_get_value
                restic_repo_type = safe_get_value(form_data, 'restic_repo_type')
                dest_type = safe_get_value(form_data, 'dest_type')
                
                debug_error = f"Form Validation Error: {error_msg}\n\n"
                debug_error += f"Debug Info:\n"
                debug_error += f"- restic_repo_type extracted: '{restic_repo_type}'\n"
                debug_error += f"- dest_type extracted: '{dest_type}'\n"
                debug_error += f"- Form data keys: {list(form_data.keys())}\n"
                
                html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                       preview_content=debug_error)
                return HTMLResponse(content=html_response)
            
            # Parse the form data using the existing parser  
            from models.forms import JobFormParser
            parser = JobFormParser()
            
            result = parser.parse_job_form(form_data)
            
            if not result.get('valid', False):
                error_msg = result.get('error', 'Unknown parsing error')
                html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                       preview_content=f"Form Validation Error: {error_msg}")
                return HTMLResponse(content=html_response)
            
            # Build the job config as it would appear in config.yaml
            job_data = result.copy()
            if 'valid' in job_data:
                del job_data['valid']  # Remove the validation flag
            
            # Format as YAML for display
            import yaml
            yaml_content = yaml.dump({job_data.get('job_name', 'unnamed_job'): job_data}, 
                                   default_flow_style=False, sort_keys=False)
            
            html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                       preview_content=yaml_content)
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            html_response = self.template_service.render_template('partials/job_config_preview.html',
                                                       preview_content=f"Error generating preview: {str(e)}\n\nCheck server logs for details.")

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    async def check_form_changes_htmx(self, request) -> HTMLResponse:
        """Check if form has changes compared to original config - HTMX handler"""
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

        # Business logic (preserve original implementation)
        try:
            import json
            from models.forms import job_parser
            
            # Get original config from hidden field
            original_config_str = self._get_form_value(form_data, 'original_job_config')
            if not original_config_str:
                # No original config means this is add mode, always enable
                html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Create Job',
                                                       enabled=True)
                return HTMLResponse(content=html_response)
            
            # Parse current form data
            current_result = job_parser.parse_job_form(form_data)
            if not current_result['valid']:
                # Form is invalid, disable button
                html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Commit Changes',
                                                       enabled=False)
                return HTMLResponse(content=html_response)
            
            # Compare configs (normalize for comparison)
            original_config = json.loads(original_config_str)
            current_config = current_result.copy()
            if 'valid' in current_config:
                del current_config['valid']
            
            # Compare as JSON strings for deep equality
            original_json = json.dumps(original_config, sort_keys=True)
            current_json = json.dumps(current_config, sort_keys=True)
            
            has_changes = original_json != current_json
            html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Commit Changes',
                                                       enabled=has_changes)
            
        except Exception as e:
            # On error, default to enabled
            html_response = self.template_service.render_template('partials/submit_button.html',
                                                       button_text='Commit Changes',
                                                       enabled=True)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

# Global handler instance
admin_handler = AdminHandler()