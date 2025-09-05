"""
HTMX Handlers for Destinations Domain

Contains all HTMX endpoint handlers following jobs domain pattern.
Handlers parse form data and delegate to destinations_handler for business logic.
"""

from typing import Dict, Any, Callable
from functools import wraps
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse


# =============================================================================
# **ERROR HANDLING DECORATOR**
# =============================================================================

def handle_page_errors(operation_name: str) -> Callable:
    """Error handling decorator for HTMX handlers"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"Error in {operation_name}: {str(e)}")
                # Return error HTML for HTMX requests
                error_html = f'<div class="error">Error in {operation_name}: {str(e)}</div>'
                return HTMLResponse(content=error_html, status_code=500)
        return wrapper
    return decorator


# =============================================================================
# **HTMX HANDLERS CLASS**
# =============================================================================

class HTMXHandlers:
    """HTMX endpoint handlers for destinations domain"""
    
    def __init__(self):
        # Import destinations handler for delegation
        from dests.handlers.pages import DestinationsHandler
        self.destinations_handler = DestinationsHandler()
    
    # =========================================================================
    # **FORM PARSING WRAPPERS** - Batch 1
    # =========================================================================
    
    @handle_page_errors("Add destination")
    async def add_destination_htmx(self, request) -> JSONResponse:
        """Add destination with form parsing - delegates to destinations_handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to main handler business logic
        return self.destinations_handler.add_destination(form_data)
    
    @handle_page_errors("Save destination")
    async def save_destination_htmx(self, request) -> JSONResponse:
        """Save destination with form parsing - delegates to destinations_handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to main handler business logic
        return self.destinations_handler.save_destination(form_data)
    
    @handle_page_errors("Validate destination")
    async def validate_destination_htmx(self, request) -> HTMLResponse:
        """Validate destination with form parsing - delegates to destinations_handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to main handler business logic
        return self.destinations_handler.validate_destination(form_data)

    # =========================================================================
    # **FIELD RENDERING** - Batch 2
    # =========================================================================
    
    @handle_page_errors("Render maintenance fields")
    async def render_maintenance_fields_htmx(self, request) -> HTMLResponse:
        """Render maintenance configuration fields based on selected mode - HTMX handler"""
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
        maintenance_mode = self.destinations_handler._get_form_value(form_data, 'restic_maintenance', 'auto')
        
        from dests.schema import MAINTENANCE_MODE_SCHEMAS
        
        # Extract current field values from form data or use defaults
        field_values = {}
        if maintenance_mode == 'user':
            schema = MAINTENANCE_MODE_SCHEMAS.get('user', {})
            for field in schema.get('fields', []):
                field_values[field['name']] = self.destinations_handler._get_form_value(form_data, field['name'], field.get('default', ''))
        
        html_response = self.destinations_handler.template_service.render_template('partials/maintenance_mode_dynamic.html',
                                                           maintenance_mode=maintenance_mode,
                                                           maintenance_schemas=MAINTENANCE_MODE_SCHEMAS,
                                                           field_values=field_values)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Render rsyncd fields")
    async def render_rsyncd_fields_htmx(self, request) -> HTMLResponse:
        """Render rsyncd-specific fields based on current state - HTMX handler"""
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
        rsyncd_hostname = self.destinations_handler._get_form_value(form_data, 'rsyncd_hostname')
        rsyncd_share = self.destinations_handler._get_form_value(form_data, 'rsyncd_share')
        
        html_response = self.destinations_handler.template_service.render_template('partials/dest_rsyncd_fields.html',
                                                           rsyncd_hostname=rsyncd_hostname,
                                                           rsyncd_share=rsyncd_share)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Render restic repo fields")
    async def render_restic_repo_fields_htmx(self, request) -> HTMLResponse:
        """Render Restic repository type fields using schema-driven templates - HTMX handler"""
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
        # Check both job form field name (restic_repo_type) and destination form field name (repo_type)
        repo_type = self.destinations_handler._get_form_value(form_data, 'restic_repo_type') or self.destinations_handler._get_form_value(form_data, 'repo_type')
        
        if not repo_type:
            html_response = ''  # No fields for unselected type
        else:
            from dests.schema import RESTIC_REPOSITORY_TYPE_SCHEMAS
            
            html_response = self.destinations_handler.template_service.render_template('partials/restic_repo_fields_dynamic.html',
                                                               repo_type=repo_type,
                                                               repo_schemas=RESTIC_REPOSITORY_TYPE_SCHEMAS,
                                                               field_values={})

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Render destination type fields")
    async def destination_type_fields_htmx(self, request) -> HTMLResponse:
        """Load destination type fields with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic - delegate to non-HTMX method
        return self.destinations_handler.destination_type_fields(form_data)
    
    @handle_page_errors("Render dest fields")
    async def render_dest_fields_htmx(self, request) -> HTMLResponse:
        """Render destination-specific fields based on destination type for HTMX forms"""
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
        
        dest_type = form_data.get('dest_type', [''])[0]
        
        # Schema-driven destination field rendering
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        
        if dest_type not in DESTINATION_TYPE_SCHEMAS:
            html_response = self.destinations_handler.template_service.render_template('partials/info_message.html',
                                                               message='Select a destination type to configure')
            return HTMLResponse(content=html_response)
        
        # Special handling for restic (has complex sub-types)
        if dest_type == 'restic':
            return await self.destinations_handler.render_restic_fields_htmx(request)
        
        # Handle other destination types using schema-driven approach
        schema = DESTINATION_TYPE_SCHEMAS.get(dest_type)
        template_name = schema.get('template')
        
        if template_name and schema.get('fields'):
            # Extract values for schema fields
            template_values = {}
            for field_name, field_config in schema['fields'].items():
                # Use the form field name directly (already mapped in schema)
                template_values[field_name] = get_form_value(form_data, field_name)
            
            html_response = self.destinations_handler.template_service.render_template(template_name, **template_values)
            return HTMLResponse(content=html_response)
        else:
            # No fields defined in schema
            html_response = self.destinations_handler.template_service.render_template('partials/info_message.html',
                                                               message=f'{schema["display_name"]} destination - configuration needed')
            return HTMLResponse(content=html_response)


# Export handler instance
destinations_htmx = HTMXHandlers()