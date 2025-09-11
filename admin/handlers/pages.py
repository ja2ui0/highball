"""
Admin Page Handlers
System configuration, settings management, and debugging
"""

import html
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
from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from admin.services.init import HighballServices
from admin.services.notifications import NotificationTestService
from admin.schema import PROVIDER_FIELD_SCHEMAS
from config import BackupConfig

logger = logging.getLogger(__name__)



class AdminHandler(BaseHandler):
    """Handle system administration and configuration"""
    
    def __init__(self):
        self.backup_config = BackupConfig()
        self._init_template_service(self.backup_config)
        self.admin_services = HighballServices()
        
        # Initialize admin operations service for config access
        from admin.services.manage import AdminOperationsService
        self.admin_operations = AdminOperationsService(self.backup_config)
    

    def _get_available_themes(self):
        """Get list of available theme files - delegate to admin service"""
        return self.admin_services.get_available_themes()

    @handle_page_errors("Config manager")
    def show_config_manager(self) -> HTMLResponse:
        """Show configuration management page"""
        
        global_settings = self.admin_operations.get_global_settings()
        
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
        config_path = self.admin_operations.get_config_file_path()
        raw_config = self.admin_services.read_raw_config(config_path)
        
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


    @handle_page_errors("Save raw config")
    def save_raw_config(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save raw YAML configuration - delegate to admin service"""
        raw_config = form_data.get('raw_config', [''])[0]
        config_path = self.admin_operations.get_config_file_path()
        
        # Delegate validation and saving to service
        result = self.admin_services.save_raw_config(raw_config, config_path)
        
        if not result['success']:
            return JSONResponse(content=result, status_code=400)
        
        # Reload configuration after successful save
        self.admin_operations.reload_config()
        
        return RedirectResponse(url='/config', status_code=302)

    @handle_page_errors("Save config")
    def save_structured_config(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save structured configuration from form - thin handler delegates to service"""
        result = self.admin_operations.save_structured_config_from_form(form_data)
        
        if result['success']:
            return RedirectResponse(url='/config', status_code=302)
        else:
            return JSONResponse(content=result, status_code=500)


    @handle_page_errors("Preview config")
    def preview_config_changes(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Preview configuration changes without saving - thin handler delegates to service"""
        result = self.admin_operations.preview_config_changes_from_form(form_data)
        
        # Handler decides which template to render
        return self._render_html('partials/config_preview.html', {
            'preview_yaml': result['yaml_content'],
            'success': result['success']
        })

    # =============================================================================
    # NOTIFICATION PROVIDER MANAGEMENT - Admin pillar methods
    # =============================================================================

    def _render_error(self, message):
        """Render error message"""
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

    async def preview_config_changes_htmx(self, request) -> HTMLResponse:
        """Preview configuration changes with form parsing - pure switchboard compliance"""
        
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
        
        # Call admin service for config preview
        result = self.admin_services.preview_config_changes(form_data, self.backup_config)
        
        if result['success']:
            html_response = self.template_service.render_template('partials/config_preview.html',
                                                               success=True,
                                                               preview_yaml=result['preview_content'])
        else:
            html_response = self.template_service.render_template('partials/config_preview.html',
                                                               success=False,
                                                               error_message=result.get('error', 'Unknown error'))
        
        return HTMLResponse(content=html_response)

    async def save_structured_config_htmx(self, request) -> JSONResponse:
        """Save structured configuration with form parsing - pure switchboard compliance"""
        
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
        
        # Call existing business logic
        return self.save_structured_config(form_data)

    async def save_raw_config_htmx(self, request) -> JSONResponse:
        """Save raw YAML configuration with form parsing - pure switchboard compliance"""
        
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
        
        # Call existing business logic
        return self.save_raw_config(form_data)

    async def test_telegram_notification_htmx(self, request) -> JSONResponse:
        """Test Telegram notification with form parsing - pure switchboard compliance"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        test_message = form.get('test_message', 'Test notification from Highball')
        
        # Call existing business logic (notification test service)
        notification_service = NotificationTestService(BackupConfig())
        result = notification_service.test_telegram_notification(test_message)
        return JSONResponse(content=result)

    async def test_email_notification_htmx(self, request) -> JSONResponse:
        """Test email notification with form parsing - pure switchboard compliance"""
        # Parse form data using FastAPI (moved FROM app.py TO handler)
        form = await request.form()
        test_message = form.get('test_message', 'Test notification from Highball')
        
        # Call existing business logic (notification test service)
        notification_service = NotificationTestService(BackupConfig())
        result = notification_service.test_email_notification(test_message)
        return JSONResponse(content=result)

    @handle_page_errors("Handle CORS options")
    def handle_options(self) -> JSONResponse:
        """Handle CORS preflight requests for API endpoints"""
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )

# Global handler instance
admin_handler = AdminHandler()