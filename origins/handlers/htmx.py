"""
HTMX Handlers for Origins Domain

Contains all HTMX endpoint handlers following jobs/dests domain pattern.
Handlers contain their complete business logic and will be refactored to delegate to services in Phase 2.
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
from origins.handlers.pages import origins_handler
from origins.schema import SOURCE_TYPE_SCHEMAS

logger = logging.getLogger(__name__)


# =============================================================================
# HTMX HANDLERS CLASS
# =============================================================================

class HTMXHandlers(BaseHandler):
    """HTMX endpoint handlers for origins domain"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.backup_config = BackupConfig()
        
        # Initialize services
        self.origin_service = OriginOperationsService(self.backup_config)
        self.ssh_service = OriginSSHService()
        

    # =========================================================================
    # FORM SUBMISSION HANDLERS
    # =========================================================================

    async def add_ssh_origin_htmx(self, request) -> JSONResponse:
        """Add SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to pages handler
        return origins_handler.add_ssh_origin(form_data)

    async def save_ssh_origin_htmx(self, request) -> JSONResponse:
        """Save SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to pages handler
        return origins_handler.save_ssh_origin(form_data)


    # =========================================================================
    # VALIDATION HANDLERS
    # =========================================================================

    async def validate_ssh_origin_htmx(self, request) -> JSONResponse:
        """Validate SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to pages handler
        return origins_handler.validate_ssh_origin(form_data)

    async def toggle_ssh_auth_method_htmx(self, request) -> HTMLResponse:
        """Toggle SSH auth method with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to pages handler
        return origins_handler.toggle_ssh_auth_method(form_data)

    # =========================================================================
    # FIELD RENDERING HANDLERS
    # =========================================================================

    async def validate_ssh_source_htmx(self, request) -> HTMLResponse:
        """Validate SSH source configuration for HTMX forms"""
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
            # origin_parser is now local to this module
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


# Export handler instance
origins_htmx = HTMXHandlers()