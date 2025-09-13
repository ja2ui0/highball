"""
Admin Views (GET handlers)
Handle configuration pages, log viewing, and read-only admin operations
"""

import logging
from typing import Dict, Any, List
from fastapi.responses import HTMLResponse, JSONResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from shared.services.config import ConfigReader
from admin.services.init import HighballServices
from admin.services.config import AdminConfigService
from admin.schema import PROVIDER_FIELD_SCHEMAS

logger = logging.getLogger(__name__)


class AdminViews(BaseHandler):
    """Handle admin GET operations - read-only views"""
    
    def __init__(self):
        # Initialize services - handlers delegate all operations
        self.admin_services = HighballServices()
        self.admin_config = AdminConfigService()
        self.config_reader = ConfigReader()

        # Initialize template service with minimal config adapter
        class ConfigAdapter:
            def __init__(self, config_reader):
                self.config_reader = config_reader
            def get_global_settings(self):
                return self.config_reader.get_global_settings()
        
        config_adapter = ConfigAdapter(self.config_reader)
        self._init_template_service(config_adapter)

    def _get_available_themes(self):
        """Get list of available theme files - delegate to admin service"""
        return self.admin_services.get_available_themes()

    def _get_system_logs(self, log_type: str, lines: int = 100) -> List[str]:
        """Get system log entries based on type - presentation logic"""
        # Simplified implementation for now - would be expanded with actual log reading logic
        return [f"Sample {log_type} log entry {i}" for i in range(1, min(lines + 1, 11))]

    # =========================================================================
    # GET HANDLERS - read-only operations
    # =========================================================================

    @handle_page_errors("Config manager")
    def show_config_manager(self) -> HTMLResponse:
        """Show configuration management interface"""
        
        # Get global settings from service (raw data)
        global_settings = self.config_reader.get_global_settings()
        
        # Presentation logic: Extract individual field values for template population
        default_schedule_times = global_settings.get('default_schedule_times', {})
        
        # Get available themes for display
        available_themes = self._get_available_themes()
        current_theme = global_settings.get('theme', 'dark')

        # Presentation logic: Build template data for display
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


    @handle_page_errors("Development logs")
    def show_dev_logs(self, log_type: str = 'app') -> HTMLResponse:
        """Show development logs interface"""
        
        # Get logs from service (raw data)
        log_entries = self._get_system_logs(log_type, lines=100)
        
        # Presentation logic: Build template data for display
        template_data = {
            'log_entries': log_entries,
            'log_type': log_type,
            'page_title': 'Development Logs'
        }
        
        return self._render_html('pages/dev_logs.html', template_data)

    def handle_options(self) -> JSONResponse:
        """Handle CORS OPTIONS requests"""
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            }
        )


# Global handler instance
admin_views = AdminViews()