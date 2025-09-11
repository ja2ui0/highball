"""
Origins Form Handlers (POST operations)
SSH origins CRUD operations, validation, and form processing
"""

import logging
import traceback
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from config import BackupConfig
from models.forms import safe_get_value
from origins.services.manage import OriginOperationsService
from origins.services.ssh import OriginSSHService
from origins.schema import SOURCE_TYPE_SCHEMAS

logger = logging.getLogger(__name__)


class OriginsFormHandler(BaseHandler):
    """Handle SSH origins form operations and validation"""
    
    def __init__(self):
        self.backup_config = BackupConfig()
        self._init_template_service()
        self.origin_service = OriginOperationsService(self.backup_config)
        self.ssh_service = OriginSSHService()
    
    @handle_page_errors("Delete SSH origin")
    def delete_ssh_origin(self, origin_name: str) -> JSONResponse:
        """Delete SSH origin"""
        # Delegate business logic to origin service
        result = self.origin_service.delete_origin_with_validation(origin_name)
        
        if result['success']:
            return RedirectResponse(url='/origins', status_code=302)
        else:
            status_code = 400 if result['error'] == 'Origin name is required' else 500
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=status_code)

    @handle_page_errors("Add SSH origin")
    def add_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new SSH origin"""
        # Parse origin form data (no password required for save operations)
        origin_result = self.origin_service.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        
        # Delegate business logic to origin service
        result = self.origin_service.add_new_origin(origin_name, origin_config)
        
        if result['success']:
            return RedirectResponse(url='/origins', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=400)

    @handle_page_errors("Save SSH origin")
    def save_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save SSH origin changes"""
        # Parse origin form data (no password required for save operations)
        origin_result = self.origin_service.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        original_origin_name = self._get_form_value(form_data, 'original_origin_name', '')
        
        # Delegate business logic to origin service
        result = self.origin_service.save_origin_with_rename_handling(origin_name, origin_config, original_origin_name)
        
        if result['success']:
            return RedirectResponse(url='/origins', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("SSH source validation")
    def validate_ssh_source(self, source: str) -> JSONResponse:
        """Validate SSH source configuration"""
        result = self.ssh_service.validate_origin_string(source)
        return JSONResponse(content=result)

    @handle_page_errors("SSH origin validation")
    def validate_ssh_origin(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Push keys and validate SSH origin configuration with persistent session tracking"""
        # Parse origin form data (no password required for save operations)
        origin_result = self.origin_service.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content=origin_result)
        
        origin_config = origin_result['origin_config']
        edit_mode = 'original_origin_name' in form_data and form_data['original_origin_name']
        
        # Extract connection details (HTTP form parsing - presentation concern)
        hostname = origin_config['ssh_hostname']
        username = origin_config['ssh_username']  
        password = form_data.get('ssh_password', '')
        ssh_highball = form_data.get('ssh_highball') == 'on'
        
        try:
            # Delegate business logic to service
            session_id = self.ssh_service.create_validation_session(hostname, username, password, ssh_highball, edit_mode)
            
            # Return initial progress template
            return self._render_html('partials/ssh_validation_progress.html', {
                'session_id': session_id,
                'initial_message': "Starting SSH validation workflow..."
            })
        except ValueError as e:
            # Handle business validation errors
            return self._render_html('partials/ssh_validation_result.html', {
                'success': False,
                'edit_mode': edit_mode,
                'validation_message': str(e)
            })
    
    @handle_page_errors("Toggle SSH auth method")
    def toggle_ssh_auth_method(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Toggle between Highball and user SSH authentication methods"""
        ssh_highball = 'ssh_highball' in form_data
        template_data = self.ssh_service.get_auth_method_template_data(ssh_highball)
        return self._render_html(template_data['template'], template_data['context'])
    
    # =========================================================================
    # HTMX FORM HANDLERS - Direct business logic (no delegation)
    # =========================================================================

    async def add_ssh_origin_htmx(self, request) -> JSONResponse:
        """Add SSH origin with form parsing - direct business logic"""
        form_data = dict(await request.form())
        return self.add_ssh_origin(form_data)

    async def save_ssh_origin_htmx(self, request) -> JSONResponse:
        """Save SSH origin with form parsing - direct business logic"""
        form_data = dict(await request.form())
        return self.save_ssh_origin(form_data)

    async def validate_ssh_origin_htmx(self, request) -> JSONResponse:
        """Validate SSH origin with form parsing - direct business logic"""
        form_data = dict(await request.form())
        return self.validate_ssh_origin(form_data)

    async def toggle_ssh_auth_method_htmx(self, request) -> HTMLResponse:
        """Toggle SSH auth method with form parsing - direct business logic"""
        form_data = dict(await request.form())
        return self.toggle_ssh_auth_method(form_data)

    async def validate_ssh_source_htmx(self, request) -> HTMLResponse:
        """Validate SSH source configuration for HTMX forms - direct business logic"""
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
        
        # Extract parameters from form data
        hostname = get_form_value(form_data, 'hostname')
        username = get_form_value(form_data, 'username')
        
        # Build source config
        source_config = {'hostname': hostname, 'username': username}
        
        # Use origins SSH service for validation
        result = self.ssh_service.validate_ssh_source(source_config)
        
        # Render validation status using SSH service
        html_response = self.ssh_service.render_validation_status(result)
        return HTMLResponse(content=html_response)

    async def render_source_fields_htmx(self, request) -> HTMLResponse:
        """Render source-specific fields based on source type for HTMX forms"""
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
        
        source_type = form_data.get('source_type', [''])[0]
        
        # Schema-driven source field rendering
        if source_type not in SOURCE_TYPE_SCHEMAS:
            html_response = self.template_service.render_template('partials/info_message.html',
                                                               message='Select a source type to configure')
            return HTMLResponse(content=html_response)
        
        schema = SOURCE_TYPE_SCHEMAS[source_type]
        
        # Check if this source type has additional fields requiring a template
        if schema.get('fields'):
            template_name = f'partials/source_{source_type}_fields.html'
            try:
                # Extract field values using schema field definitions
                template_values = {}
                for field_name, field_config in schema['fields'].items():
                    config_key = field_config.get('config_key', field_name)
                    template_values[config_key] = get_form_value(form_data, config_key)
                
                html_response = self.template_service.render_template(template_name, **template_values)
                return HTMLResponse(content=html_response)
            except Exception:
                # Template doesn't exist or failed to render
                html_response = self.template_service.render_template('partials/info_message.html',
                                                                   message=f'{schema["display_name"]} source configuration')
                return HTMLResponse(content=html_response)
        else:
            # No additional fields needed (e.g., local)
            html_response = self.template_service.render_template('partials/info_message.html',
                                                               message=f'{schema["display_name"]} source - no additional configuration needed')
            return HTMLResponse(content=html_response)

    async def preview_ssh_config_htmx(self, request) -> HTMLResponse:
        """Generate and display SSH origin config preview for HTMX forms"""
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
            if not form_data:
                html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                                   preview_content="Error: No form data received",
                                                                   origin_name="unknown")
                return HTMLResponse(content=html_response)
            
            # Extract form values
            origin_name = get_form_value(form_data, 'origin_name', '').strip()
            friendly_name = get_form_value(form_data, 'friendly_name', '').strip()
            ssh_hostname = get_form_value(form_data, 'ssh_hostname', '').strip()
            ssh_username = get_form_value(form_data, 'ssh_username', '').strip()
            ssh_port = get_form_value(form_data, 'ssh_port', '22')
            ssh_timeout = get_form_value(form_data, 'ssh_timeout', '5')
            
            if not all([origin_name, friendly_name, ssh_hostname, ssh_username]):
                html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                                   preview_content="Error: Required fields missing (origin name, friendly name, hostname, username)",
                                                                   origin_name=origin_name or "unknown")
                return HTMLResponse(content=html_response)
            
            # Parse form data using the same parser as save operations
            origin_result = self.origin_service.parse_origin_form(form_data, require_password=False)
            if not origin_result['valid']:
                html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                                   preview_content=f"# Error: {origin_result['error']}",
                                                                   origin_name=origin_name)
                return HTMLResponse(content=html_response)
            
            origin_config = origin_result['origin_config']
            origin_name = origin_config['origin_name']
            
            # Generate YAML using the same code path as config.py save operation
            yaml_content = self.origin_service.preview_origin_yaml(origin_name, origin_config)
            
            html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                               preview_content=yaml_content,
                                                               origin_name=origin_name)
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            traceback.print_exc()
            html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                               preview_content=f"Error generating preview: {str(e)}\n\nCheck server logs for details.",
                                                               origin_name=get_form_value(form_data, 'origin_name', 'unknown'))
            return HTMLResponse(content=html_response)


# Global handler instance
origins_form_handler = OriginsFormHandler()