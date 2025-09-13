"""
Admin Forms (POST handlers)
Handle configuration updates, notification management, and write operations
"""

import html
import logging
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from shared.services.config import ConfigReader
from admin.services.init import HighballServices
from admin.services.notifications import NotificationTestService
from admin.services.config import AdminConfigService
from admin.schema import PROVIDER_FIELD_SCHEMAS
from admin.handlers.views import AdminViews

logger = logging.getLogger(__name__)


class AdminForms(BaseHandler):
    """Handle admin POST operations - configuration updates and write operations"""
    
    def __init__(self):
        # Services handle all config access - handlers delegate everything
        self.admin_services = HighballServices()
        self.admin_config = AdminConfigService()
        self.config_reader = ConfigReader()

        # Defer notification service initialization to avoid early dependencies
        self._notification_test = None

        # Initialize template service with config adapter
        class ConfigAdapter:
            def __init__(self, config_reader):
                self.config_reader = config_reader
            def get_global_settings(self):
                return self.config_reader.get_global_settings()

        self.config_adapter = ConfigAdapter(self.config_reader)
        self._init_template_service(self.config_adapter)
    
    @property
    def notification_test(self):
        """Lazy initialization of notification test service"""
        if self._notification_test is None:
            self._notification_test = NotificationTestService(self.config_adapter)
        return self._notification_test

    # =========================================================================
    # CONFIGURATION OPERATIONS
    # =========================================================================


    def save_structured_config(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save structured configuration - delegates to service"""
        result = self.admin_config.save_structured_config_from_form(form_data)
        
        if result['success']:
            return JSONResponse(content={'message': 'Configuration saved successfully'})
        else:
            return JSONResponse(
                content={'error': result['error']}, 
                status_code=400
            )

    def preview_config_changes(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Preview configuration changes - delegates to service"""
        result = self.admin_config.preview_config_changes_from_form(form_data)
        
        template_data = {
            'preview_yaml': result['yaml_content'],
            'success': result['success']
        }
        
        return self._render_html('partials/config_preview.html', template_data)

    # =========================================================================
    # HTMX FORM OPERATIONS
    # =========================================================================


    @handle_page_errors("Preview config changes")
    async def preview_config_changes_htmx(self, request) -> HTMLResponse:
        """Preview configuration changes with form parsing"""
        form_data = dict(await request.form())
        return self.preview_config_changes(form_data)

    # =========================================================================
    # NOTIFICATION PROVIDER OPERATIONS
    # =========================================================================

    @handle_page_errors("Add notification provider")
    async def add_global_notification_provider_htmx(self, request) -> HTMLResponse:
        """Add global notification provider with form parsing"""
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.admin_config.add_notification_provider_from_form(form_data)
        
        if result['success']:
            # Return updated notification section showing new provider form
            global_settings = self.config_reader.get_global_settings()
            template_data = {
                'global_settings': global_settings,
                'provider_schemas': PROVIDER_FIELD_SCHEMAS
            }
            return self._render_html('partials/notification_section.html', template_data)
        else:
            # Return error message
            return self._render_html('partials/error_message.html', {
                'error_message': result['error']
            })

    @handle_page_errors("Remove notification provider")
    async def remove_global_notification_provider_htmx(self, request) -> HTMLResponse:
        """Remove global notification provider with form parsing"""
        form_data = dict(await request.form())
        
        # Delegate business logic to service  
        result = self.admin_config.remove_notification_provider_from_form(form_data)
        
        if result['success']:
            # Return updated notification section 
            global_settings = self.config_reader.get_global_settings()
            template_data = {
                'global_settings': global_settings,
                'provider_schemas': PROVIDER_FIELD_SCHEMAS
            }
            return self._render_html('partials/notification_section.html', template_data)
        else:
            # Return error message
            return self._render_html('partials/error_message.html', {
                'error_message': result['error']
            })

    # =========================================================================
    # NOTIFICATION TESTING
    # =========================================================================

    @handle_page_errors("Test Telegram notification")
    async def test_telegram_notification_htmx(self, request) -> JSONResponse:
        """Test Telegram notification with form parsing"""
        form_data = dict(await request.form())
        
        # Delegate to notification test service
        test_message = form_data.get('test_message', 'Test notification from Highball')
        result = self.notification_test.test_telegram_notification(test_message)
        
        return JSONResponse(content=result)

    @handle_page_errors("Test email notification")  
    async def test_email_notification_htmx(self, request) -> JSONResponse:
        """Test email notification with form parsing"""
        form_data = dict(await request.form())
        
        # Delegate to notification test service
        test_message = form_data.get('test_message', 'Test notification from Highball')
        result = self.notification_test.test_email_notification(test_message)
        
        return JSONResponse(content=result)

    @handle_page_errors("Save structured config")
    async def save_structured_config_htmx(self, request) -> HTMLResponse:
        """Save structured configuration with form parsing - returns full page HTML"""
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.admin_config.save_structured_config_from_form(form_data)
        
        if result['success']:
            template_data = {
                'message': 'Configuration saved successfully',
                'success': True
            }
            return self._render_html('partials/config_save_result.html', template_data)
        else:
            # Return error message as HTML  
            template_data = {
                'message': result.get('error', 'Configuration save failed'),
                'success': False
            }
            return self._render_html('partials/config_save_result.html', template_data)

    @handle_page_errors("Hide preview")
    async def hide_preview_htmx(self, request) -> HTMLResponse:
        """Hide config preview by returning empty content"""
        return HTMLResponse(content="")

    # =========================================================================
    # LOG MANAGEMENT OPERATIONS
    # =========================================================================

    @handle_page_errors("Clear logs")
    async def clear_logs_htmx(self, request) -> HTMLResponse:
        """Clear system logs with form parsing"""
        form_data = dict(await request.form())
        
        # Delegate to admin services
        log_type = form_data.get('log_type', 'app')
        result = self.admin_services.clear_logs(log_type)
        
        if result['success']:
            # Return empty log display
            template_data = {
                'log_entries': [],
                'log_type': log_type
            }
            return self._render_html('partials/log_entries.html', template_data)
        else:
            return self._render_html('partials/error_message.html', {
                'error_message': result['error']
            })

    @handle_page_errors("Refresh logs")
    async def refresh_logs_htmx(self, request) -> HTMLResponse:
        """Refresh system logs with form parsing"""
        form_data = dict(await request.form())
        
        # Get fresh logs from service
        log_type = form_data.get('log_type', 'app')
        log_entries = self.admin_services.get_system_logs(log_type, lines=100)
        
        template_data = {
            'log_entries': log_entries,
            'log_type': log_type
        }
        
        return self._render_html('partials/log_entries.html', template_data)

    # =========================================================================
    # UI UTILITIES
    # =========================================================================

    @handle_page_errors("Handle queue settings")
    async def handle_queue_settings_htmx(self, request) -> HTMLResponse:
        """Handle queue settings form with form parsing"""
        form_data = dict(await request.form())
        
        # RESEARCH FINDINGS: Queue settings are per-provider, not global
        # - Schema defines queue_enabled/queue_interval_minutes in sections.queue_settings for each provider 
        # - UI renders these via notification_provider_dynamic.html processing sections array
        # - But AdminConfigService._update_notification_settings() only processes top-level fields, not sections
        # - This orphaned method should be removed - queue settings should be enhanced in existing provider processing
        # TODO: Remove this handler and enhance _update_notification_settings() to process sections array
        
        return self._render_html('partials/error_message.html', {
            'error_message': 'Queue settings are handled per-provider, not globally. This handler is deprecated.'
        })

    @handle_page_errors("Render cron field")
    async def render_cron_field_htmx(self, request) -> HTMLResponse:
        """Render cron field dynamically with form parsing"""
        form_data = dict(await request.form())
        
        # Extract field information
        field_name = form_data.get('field_name', '')
        current_value = form_data.get('current_value', '')
        
        template_data = {
            'field_name': field_name,
            'current_value': current_value
        }
        
        return self._render_html('partials/cron_field.html', template_data)

    @handle_page_errors("Toggle password visibility")
    async def toggle_password_visibility_htmx(self, request) -> HTMLResponse:
        """Toggle password field visibility with form parsing"""
        form_data = dict(await request.form())
        
        # Extract field information
        field_name = form_data.get('field_name', '')
        current_value = form_data.get('current_value', '')
        show_password = form_data.get('show_password', 'false') == 'true'
        
        template_data = {
            'field_name': field_name,
            'current_value': current_value,
            'show_password': not show_password  # Toggle the state
        }
        
        return self._render_html('partials/password_field.html', template_data)

    @handle_page_errors("Change theme")
    async def change_theme_htmx(self, request) -> HTMLResponse:
        """Change theme immediately without saving to config"""
        form_data = dict(await request.form())
        theme = form_data.get('theme', 'dark')
        
        template_data = {'theme': theme}
        return self._render_html('partials/head_content.html', template_data)


# Global handler instance
admin_forms = AdminForms()