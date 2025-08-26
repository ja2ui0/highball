"""
Destinations Page Handlers
Repository management, destination configuration, and validation
"""

import logging
from typing import Dict, Any, Callable
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

class DestinationsHandler(BaseHandler):
    """Handle destinations management and validation"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.backup_config = BackupConfig()
    
    @handle_page_errors("Show destinations")
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

    def add_destination(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new destination - delegate to form processor"""
        from handlers.forms import FormProcessingHandler
        form_processor = FormProcessingHandler(self.backup_config)
        return form_processor.add_destination(form_data)

    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Helper to get form value with default"""
        return form_data.get(field_name, default)

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

# Global handler instance
destinations_handler = DestinationsHandler()