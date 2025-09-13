"""
Destinations Forms (POST handlers)  
Handle destination CRUD operations, validation, and repository management
"""

from typing import Dict, Any
from functools import wraps
from urllib.parse import parse_qs
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from shared.services.config import ConfigReader
from dests.services.config import DestConfigService
from dests.services.restic import ResticRepositoryTypeService, ResticRepositoryService, unlock_repository, initialize_repository
from dests.schema import MAINTENANCE_MODE_SCHEMAS, RESTIC_REPOSITORY_TYPE_SCHEMAS, DESTINATION_TYPE_SCHEMAS

# Import views for template rendering (presentation logic)
from dests.handlers.views import destinations_views


class DestinationsForms(BaseHandler):
    """Handle destinations POST operations - CRUD and form processing"""
    
    def __init__(self):
        self._init_template_service()

        # Services handle all config access - handlers delegate everything
        self.dest_config = DestConfigService()
        self.config_reader = ConfigReader()

    # =========================================================================
    # DESTINATION CRUD OPERATIONS
    # =========================================================================

    @handle_page_errors("Add destination")
    async def add_destination_htmx(self, request) -> JSONResponse:
        """Add destination with form parsing - delegates to service"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to service business logic
        result = self.dest_config.add_destination_from_form(form_data)
        
        if result['success']:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content=result, status_code=400)
    
    @handle_page_errors("Save destination")
    async def save_destination_htmx(self, request) -> JSONResponse:
        """Save destination with form parsing - delegates to service"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to service business logic
        result = self.dest_config.save_destination_with_validation(form_data)
        
        if result['success']:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            status_code = 404 if 'not found' in result['error'].lower() else 400
            return JSONResponse(content=result, status_code=status_code)

    @handle_page_errors("Delete destination")
    def delete_destination(self, dest_name: str) -> JSONResponse:
        """Delete destination"""
        
        # Delegate to service
        result = self.dest_config.delete_destination_with_validation(dest_name)
        
        if result['success']:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            status_code = 400 if 'required' in result.get('error', '') else 500
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=status_code)

    # =========================================================================
    # VALIDATION OPERATIONS
    # =========================================================================
    
    @handle_page_errors("Validate destination")
    async def validate_destination_htmx(self, request) -> HTMLResponse:
        """Validate destination with form parsing - delegates to service"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to service business logic  
        template_context = self.dest_config.validate_destination_from_form(form_data)
        return self._render_html('partials/destination_validation_result.html', template_context)

    @handle_page_errors("Validate SSH destination")
    async def validate_ssh_dest_htmx(self, request) -> HTMLResponse:
        """Validate SSH destination configuration for HTMX forms"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.dest_config.validate_ssh_destination_from_form(form_data)
        
        # Handler renders appropriate template based on service result
        html_response = destinations_views.render_ssh_dest_validation_status(result)
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Validate restic")
    async def validate_restic_htmx(self, request) -> HTMLResponse:
        """Validate Restic repository configuration for HTMX forms"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.dest_config.validate_restic_destination_from_form(form_data)
        
        # Handler renders appropriate template based on service result
        html_response = destinations_views.render_restic_validation_status(result)
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Validate origin repo path")
    async def validate_origin_repo_path_htmx(self, request) -> HTMLResponse:
        """Validate same-as-origin repository path with RWX requirements for HTMX forms"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate business logic to service
        result = self.dest_config.validate_origin_repo_path_from_form(form_data)
        
        # Handler renders appropriate template based on service result
        html_response = destinations_views.render_origin_repo_path_validation_status(result)
        return HTMLResponse(content=html_response)

    # =========================================================================
    # FIELD RENDERING OPERATIONS
    # =========================================================================
    
    def destination_type_fields(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Load destination type-specific fields (HTMX partial)"""
        dest_type = self._get_form_value(form_data, 'dest_type', '')
        
        if dest_type == 'rsync':
            template = 'partials/dest_rsync_fields.html'
        elif dest_type == 'rsyncd':
            template = 'partials/dest_rsyncd_fields.html'
        elif dest_type == 'restic':
            template = 'partials/dest_restic_fields.html'
        else:
            return HTMLResponse(content='')
        
        return self._render_html(template, {})
    
    @handle_page_errors("Render destination type fields")
    async def destination_type_fields_htmx(self, request) -> HTMLResponse:
        """Load destination type fields with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic - delegate to non-HTMX method
        return self.destination_type_fields(form_data)

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
        maintenance_mode = self._get_form_value(form_data, 'restic_maintenance', 'auto')
        
        # Extract current field values from form data or use defaults
        field_values = {}
        if maintenance_mode == 'user':
            schema = MAINTENANCE_MODE_SCHEMAS.get('user', {})
            for field in schema.get('fields', []):
                field_values[field['name']] = self._get_form_value(form_data, field['name'], field.get('default', ''))
        
        html_response = self.template_service.render_template('partials/maintenance_mode_dynamic.html',
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
        rsyncd_hostname = self._get_form_value(form_data, 'rsyncd_hostname')
        rsyncd_share = self._get_form_value(form_data, 'rsyncd_share')
        
        html_response = self.template_service.render_template('partials/dest_rsyncd_fields.html',
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
        repo_type = self._get_form_value(form_data, 'restic_repo_type') or self._get_form_value(form_data, 'repo_type')
        
        if not repo_type:
            html_response = ''  # No fields for unselected type
        else:
            html_response = self.template_service.render_template('partials/restic_repo_fields_dynamic.html',
                                                               repo_type=repo_type,
                                                               repo_schemas=RESTIC_REPOSITORY_TYPE_SCHEMAS,
                                                               field_values={})

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

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
            html_response = self.template_service.render_template('partials/info_message.html',
                                                               message='Select a destination type to configure')
            return HTMLResponse(content=html_response)
        
        # Special handling for restic (has complex sub-types)
        if dest_type == 'restic':
            return await self.render_restic_fields_htmx(request)
        
        # Handle other destination types using schema-driven approach
        schema = DESTINATION_TYPE_SCHEMAS.get(dest_type)
        template_name = schema.get('template')
        
        if template_name and schema.get('fields'):
            # Extract values for schema fields
            template_values = {}
            for field_name, field_config in schema['fields'].items():
                # Use the form field name directly (already mapped in schema)
                template_values[field_name] = get_form_value(form_data, field_name)
            
            html_response = self.template_service.render_template(template_name, **template_values)
            return HTMLResponse(content=html_response)
        else:
            # No fields defined in schema
            html_response = self.template_service.render_template('partials/info_message.html',
                                                               message=f'{schema["display_name"]} destination - configuration needed')
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
        
        html_response = self.template_service.render_template('partials/job_form_dest_restic.html',
                                                           restic_password='',
                                                           restic_repo_type='',
                                                           available_repository_types=available_repository_types,
                                                           selected_repo_type='',
                                                           show_wrapper=False)
        return HTMLResponse(content=html_response)

    # =========================================================================
    # REPOSITORY OPERATIONS
    # =========================================================================
    
    @handle_page_errors("Initialize restic repository")
    async def init_restic_repository_htmx(self, request) -> HTMLResponse:
        """Initialize Restic repository - HTMX handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())

        # Delegate business logic to service
        restic_result = self.dest_config.parse_restic_destination_from_form(form_data)
        
        if not restic_result['valid']:
            html_response = destinations_views._render_validation_result("error", restic_result['error'])
        else:
            # Direct repository initialization using service
            repo_service = ResticRepositoryService()
            result = repo_service.initialize_repository(restic_result['config'])
            
            if result['success']:
                html_response = destinations_views._render_validation_result("success", "Repository initialized successfully")
            else:
                html_response = destinations_views._render_validation_result("error", f"Initialization failed: {result.get('error', 'Unknown error')}")

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
        
        # Delegate to service business logic
        # Get destination name from form and initialize repository using destinations domain only
        dest_name = form_data.get('dest_name', [''])[0] if form_data.get('dest_name') else ''
        if not dest_name:
            result = {'success': False, 'error': 'Destination name is required for repository initialization'}
        else:
            dest_config = self.config_reader.get_destination(dest_name)
            if dest_config:
                result = initialize_repository(dest_config)
            else:
                result = {'success': False, 'error': f'Destination "{dest_name}" not found'}
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
        
        # Extract dest_name from form data instead of using job_name
        form_data = dict(await request.form())
        dest_name = form_data.get('dest_name', '')
        return self.unlock_repository_htmx(dest_name)
    
    @handle_page_errors("Repository unlock")
    def unlock_repository_htmx(self, dest_name: str) -> HTMLResponse:
        """HTMX endpoint for repository unlock - destinations domain only"""
        
        # Get destination config and unlock repository
        if not dest_name:
            result = {'success': False, 'error': 'Destination name is required for repository unlock'}
        else:
            dest_config = self.config_reader.get_destination(dest_name)
            if dest_config:
                result = unlock_repository(dest_config)
            else:
                result = {'success': False, 'error': f'Destination "{dest_name}" not found'}
        
        if result.get('success'):
            # Unlock successful
            return self._render_html('partials/repository_unlock_success.html', {'dest_name': dest_name})
        else:
            # Unlock failed - show appropriate error template
            return self._render_html('partials/repository_error.html', {
                'dest_name': dest_name,
                'error_type': 'unlock_failed',
                'error_message': result.get('error', 'Unlock failed')
            })

    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    @handle_page_errors("Generate restic URI preview")
    async def generate_restic_uri_preview_htmx(self, request) -> HTMLResponse:
        """Generate real-time URI preview for repository configuration - HTMX handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())

        # Delegate business logic to service
        result = self.dest_config.generate_uri_preview('restic', form_data)
        
        # Handler renders template with service result
        html_response = self.template_service.render_template('partials/uri_preview.html', uri=result['uri'])
        return HTMLResponse(content=html_response)

    async def initialize_repository_htmx(self, request) -> JSONResponse:
        """Initialize repository - destinations domain only"""
        # Parse form data and initialize repository
        form_data = dict(await request.form())
        dest_name = form_data.get('dest_name', '')
        if not dest_name:
            result = {'success': False, 'error': 'Destination name is required for repository initialization'}
        else:
            dest_config = self.config_reader.get_destination(dest_name)
            if dest_config:
                result = initialize_repository(dest_config)
            else:
                result = {'success': False, 'error': f'Destination "{dest_name}" not found'}
        return JSONResponse(content=result)


# Global handler instance
destinations_forms = DestinationsForms()