"""
HTMX Handlers for Destinations Domain

Contains all HTMX endpoint handlers following jobs domain pattern.
Handlers parse form data and delegate to destinations_handler for business logic.
"""

from typing import Dict, Any, Callable
from functools import wraps
from urllib.parse import parse_qs
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from shared.handlers.errors import handle_page_errors
from dests.handlers.pages import DestinationsHandler
from dests.schema import MAINTENANCE_MODE_SCHEMAS, RESTIC_REPOSITORY_TYPE_SCHEMAS, DESTINATION_TYPE_SCHEMAS
from dests.services.rsync import rsync_service
from dests.services.restic import restic_service, ResticRepositoryTypeService, ResticRepositoryService, restic_api_service, unlock_repository_for_job

# =============================================================================
# **HTMX HANDLERS CLASS**
# =============================================================================

class HTMXHandlers:
    """HTMX endpoint handlers for destinations domain"""
    
    def __init__(self):
        # Initialize destinations handler for delegation
        self.destinations_handler = DestinationsHandler()
        
        # Direct config access to avoid cross-handler config access
        from config import BackupConfig
        self.backup_config = BackupConfig()
        
        # Initialize destination service for proper config access
        from dests.services.manage import create_destination_operations_service
        self.dest_operations = create_destination_operations_service(self.backup_config)
    
    # =========================================================================
    # **FORM PARSING WRAPPERS**
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
    # **FIELD RENDERING**
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

    # =========================================================================
    # **VALIDATION**
    # =========================================================================
    
    @handle_page_errors("Validate SSH destination")
    async def validate_ssh_dest_htmx(self, request) -> HTMLResponse:
        """Validate SSH destination configuration for HTMX forms"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.dest_operations.validate_ssh_destination_from_form(form_data)
        
        # Handler renders appropriate template based on service result
        html_response = self.destinations_handler.render_ssh_dest_validation_status(result)
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Validate restic")
    async def validate_restic_htmx(self, request) -> HTMLResponse:
        """Validate Restic repository configuration for HTMX forms"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.dest_operations.validate_restic_destination_from_form(form_data)
        
        # Handler renders appropriate template based on service result
        html_response = self.destinations_handler.render_restic_validation_status(result)
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Validate origin repo path")
    async def validate_origin_repo_path_htmx(self, request) -> HTMLResponse:
        """Validate same-as-origin repository path with RWX requirements for HTMX forms"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.dest_operations.validate_origin_repo_path_from_form(form_data)
        
        # Handler renders appropriate template based on service result
        html_response = self.destinations_handler.render_origin_repo_path_validation_status(result)
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Render restic fields")
    async def render_restic_fields_htmx(self, request) -> HTMLResponse:
        """Render Restic repository configuration fields for HTMX forms"""
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
        
        repo_service = ResticRepositoryTypeService()
        available_repository_types = repo_service.get_available_repository_types()
        
        html_response = self.destinations_handler.template_service.render_template('partials/job_form_dest_restic.html',
                                                           restic_password='',
                                                           restic_repo_type='',
                                                           available_repository_types=available_repository_types,
                                                           selected_repo_type='',
                                                           show_wrapper=False)
        return HTMLResponse(content=html_response)

    # =========================================================================
    # **REPOSITORY OPERATIONS**
    # =========================================================================
    
    @handle_page_errors("Initialize restic repository")
    async def init_restic_repository_htmx(self, request) -> HTMLResponse:
        """Initialize Restic repository - HTMX handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())

        # Delegate business logic to service
        restic_result = self.dest_operations.parse_restic_destination_from_form(form_data)
        
        if not restic_result['valid']:
            html_response = self.destinations_handler._render_validation_result("error", restic_result['error'])
        else:
            # Direct repository initialization using service
            repo_service = ResticRepositoryService()
            result = repo_service.initialize_repository(restic_result['config'])
            
            if result['success']:
                html_response = self.destinations_handler._render_validation_result("success", "Repository initialized successfully")
            else:
                html_response = self.destinations_handler._render_validation_result("error", f"Initialization failed: {result.get('error', 'Unknown error')}")

        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Initialize restic repo")
    async def initialize_restic_repo_htmx(self, request) -> JSONResponse:
        """Initialize Restic repository with form parsing - pure switchboard compliance"""
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
        
        # Call existing restic API service (now returns plain data, not JSONResponse)
        result = restic_api_service.initialize_restic_repo(form_data)
        return JSONResponse(content=result)
    
    @handle_page_errors("Repository unlock")
    async def unlock_repository_post_htmx(self, request) -> HTMLResponse:
        """HTMX endpoint for repository unlock (POST) - pure switchboard compliance"""
        # Parse form data (though there might not be any)
        form = await request.form()
        
        # Extract job name from query params for POST
        url_parts = str(request.url).split('?')
        if len(url_parts) > 1:
            params = parse_qs(url_parts[1])
            job_name = params.get('job', [''])[0]
        else:
            job_name = ''
        
        # Call existing business logic
        return self.unlock_repository_htmx(job_name)
    
    @handle_page_errors("Repository unlock")
    def unlock_repository_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository unlock - business logic calls destinations service"""
        
        # Delegate business logic to service
        result = unlock_repository_for_job(job_name, self.backup_config)
        
        if result.get('success'):
            # Unlock successful - automatically retry availability check
            return self.destinations_handler._check_and_respond_repository_status_html(job_name, {})
        else:
            # Unlock failed - show appropriate error template
            return self.destinations_handler._render_html('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'unlock_failed',
                'error_message': result.get('error', 'Unlock failed')
            })

    # =========================================================================
    # **UTILITIES**
    # =========================================================================
    
    @handle_page_errors("Generate restic URI preview")
    async def generate_restic_uri_preview_htmx(self, request) -> HTMLResponse:
        """Generate real-time URI preview for repository configuration - HTMX handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())

        # Delegate business logic to service
        result = self.dest_operations.generate_uri_preview('restic', form_data)
        
        # Handler renders template with service result
        html_response = self.destinations_handler.template_service.render_template('partials/uri_preview.html', uri=result['uri'])
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Repository check")
    def check_repository_availability_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository availability check"""
        
        # Delegate to existing method that now uses services internally
        return self.destinations_handler._check_and_respond_repository_status_html(job_name, {})


# Export handler instance
destinations_htmx = HTMXHandlers()
