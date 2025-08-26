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

# Global handler instance
admin_handler = AdminHandler()