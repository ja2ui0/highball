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

    # =========================================================================
    # **VALIDATION** - Batch 3
    # =========================================================================
    
    @handle_page_errors("Validate SSH destination")
    async def validate_ssh_dest_htmx(self, request) -> HTMLResponse:
        """Validate SSH destination configuration for HTMX forms"""
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
        
        # Extract parameters from request
        hostname = get_form_value(form_data, 'dest_hostname')
        username = get_form_value(form_data, 'dest_username')
        path = get_form_value(form_data, 'dest_path')
        
        # Business logic: delegate to proper destination validation service
        from dests.services.rsync import rsync_service
        form_data = {'hostname': hostname, 'username': username, 'path': path}
        result = rsync_service.validate_rsync_destination(form_data)
        
        # View: delegate to local validation method (moved from template service)
        html_response = self.destinations_handler.render_ssh_dest_validation_status(result)
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Validate restic")
    async def validate_restic_htmx(self, request) -> HTMLResponse:
        """Validate Restic repository configuration for HTMX forms"""
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
        
        # Extract parameters from request using correct field names
        repo_type = get_form_value(form_data, 'restic_repo_type') or get_form_value(form_data, 'repo_type')
        password = get_form_value(form_data, 'restic_password')
        
        # Schema-driven validation for required fields
        from dests.schema import DESTINATION_TYPE_SCHEMAS
        schema = DESTINATION_TYPE_SCHEMAS.get('restic', {})
        required_fields = schema.get('required_fields', [])
        
        # Map form fields to config keys
        field_values = {
            'repo_type': repo_type,
            'password': password
        }
        
        for field in required_fields:
            if field in field_values and not field_values[field]:
                display_name = schema.get('display_name', 'Restic')
                html_response = self.destinations_handler.render_restic_validation_status({
                    'success': False, 'error': f'{display_name} destination missing {field}'
                })
                return HTMLResponse(content=html_response)
        
        # Build URI from individual repository fields using existing URI builder
        # DestinationParser is now local to this module
        from dests.handlers.pages import DestinationParser
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        
        if not uri_result.get('valid'):
            html_response = self.destinations_handler.render_restic_validation_status({
                'success': False, 'error': uri_result.get('error', 'Invalid repository configuration')
            })
            return HTMLResponse(content=html_response)
        
        repo_uri = uri_result['uri']
        
        # Business logic: delegate to proper destination validation service
        from dests.services.restic import restic_service
        form_data = {'repo_type': repo_type, 'repo_uri': repo_uri, 'restic_password': password}
        result = restic_service.validate_restic_destination(form_data)
        
        # View: delegate to local validation method (moved from template service)
        html_response = self.destinations_handler.render_restic_validation_status(result)
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Validate origin repo path")
    async def validate_origin_repo_path_htmx(self, request) -> HTMLResponse:
        """Validate same-as-origin repository path with RWX requirements for HTMX forms"""
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
        
        # Extract repository path
        repo_path = get_form_value(form_data, 'origin_repo_path')
        if not repo_path or not repo_path.strip():
            result = {'success': False, 'error': 'Please enter a repository path'}
            html_response = self.destinations_handler.render_origin_repo_path_validation_status(result)
            return HTMLResponse(content=html_response)
        
        # Extract SSH configuration (required for same_as_origin)
        hostname = get_form_value(form_data, 'hostname')
        username = get_form_value(form_data, 'username')
        
        if not hostname or not username:
            result = {'success': False, 'error': 'SSH configuration required for same-as-origin repositories'}
            html_response = self.destinations_handler.render_origin_repo_path_validation_status(result)
            return HTMLResponse(content=html_response)
        
        # Business logic: delegate to proper destination validation service
        from dests.services.rsync import rsync_service
        form_data = {'hostname': hostname, 'username': username, 'path': repo_path}
        result = rsync_service.validate_rsync_destination(form_data)
        
        # View: delegate to local validation method (moved from template service)
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
        
        from dests.services.restic import ResticRepositoryTypeService
        
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
    # **REPOSITORY OPERATIONS** - Batch 4
    # =========================================================================
    
    @handle_page_errors("Initialize restic repository")
    async def init_restic_repository_htmx(self, request) -> HTMLResponse:
        """Initialize Restic repository - HTMX handler"""
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
        # Parse Restic config from unified parser
        # DestinationParser is now local to this module
        from dests.handlers.pages import DestinationParser
        restic_result = DestinationParser.parse_restic_destination(form_data)
        
        if not restic_result['valid']:
            html_response = self.destinations_handler._render_validation_result("error", restic_result['error'])
        else:
            # Direct repository initialization
            from dests.services.restic import ResticRepositoryService
            repo_service = ResticRepositoryService()
            result = repo_service.initialize_repository(restic_result['config'])
            
            if result['success']:
                html_response = self.destinations_handler._render_validation_result("success", "Repository initialized successfully")
            else:
                html_response = self.destinations_handler._render_validation_result("error", f"Initialization failed: {result.get('error', 'Unknown error')}")

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Initialize restic repo")
    async def initialize_restic_repo_htmx(self, request) -> JSONResponse:
        """Initialize Restic repository with form parsing - pure switchboard compliance"""
        from fastapi.responses import JSONResponse
        
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
        
        # Call existing restic API service
        from admin.services.init import services
        return services.restic_api.initialize_restic_repo(form_data)
    
    @handle_page_errors("Repository unlock")
    async def unlock_repository_post_htmx(self, request) -> HTMLResponse:
        """HTMX endpoint for repository unlock (POST) - pure switchboard compliance"""
        # Parse form data (though there might not be any)
        form = await request.form()
        
        # Extract job name from query params for POST
        url_parts = str(request.url).split('?')
        if len(url_parts) > 1:
            from urllib.parse import parse_qs
            params = parse_qs(url_parts[1])
            job_name = params.get('job', [''])[0]
        else:
            job_name = ''
        
        # Call existing business logic
        return self.unlock_repository_htmx(job_name)
    
    @handle_page_errors("Repository unlock")
    def unlock_repository_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository unlock - business logic calls destinations service"""
        
        if not job_name:
            return self.destinations_handler._render_html('partials/error_message.html', {
                'error_message': 'Job name is required'
            })
            
        # Get and validate job configuration
        jobs = self.destinations_handler.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self.destinations_handler._render_html('partials/error_message.html', {
                'error_message': f"Job '{job_name}' not found"
            })
        
        job_config = jobs[job_name]
        dest_type = job_config.get('dest_type')
        
        if dest_type != 'restic':
            return self.destinations_handler._render_html('partials/error_message.html', {
                'error_message': 'Unlock is only supported for restic repositories'
            })
        
        # Execute restic unlock command via destinations service
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        from dests.services.restic import restic_service
        result = restic_service.unlock_repository(dest_config, source_config)
        
        if result.get('success'):
            # Unlock successful - automatically retry availability check
            return self.destinations_handler.check_repository_availability_htmx(job_name)
        else:
            # Unlock failed - show error
            return self.destinations_handler._render_html('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'unlock_failed',
                'error_message': result.get('error', 'Unlock failed')
            })

    # =========================================================================
    # **UTILITIES** - Batch 5
    # =========================================================================
    
    @handle_page_errors("Generate restic URI preview")
    async def generate_restic_uri_preview_htmx(self, request) -> HTMLResponse:
        """Generate real-time URI preview for repository configuration - HTMX handler"""
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
            html_response = self.destinations_handler.template_service.render_template('partials/uri_preview.html',
                                                               uri='Select repository type to see URI preview')
        else:
            # Use existing URI builder from forms module
            # DestinationParser is now local to this module
            from dests.handlers.pages import DestinationParser
            uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
            
            if uri_result.get('valid'):
                # Mask password in display
                uri = uri_result['uri']
                if ':' in uri and '@' in uri:
                    # Replace password with *** for display
                    parts = uri.split('@')
                    if len(parts) == 2:
                        auth_part = parts[0]
                        if ':' in auth_part:
                            scheme_and_user = auth_part.rsplit(':', 1)[0]
                            uri = f"{scheme_and_user}:***@{parts[1]}"
                
                html_response = self.destinations_handler.template_service.render_template('partials/uri_preview.html', uri=uri)
            else:
                html_response = self.destinations_handler.template_service.render_template('partials/uri_preview.html',
                                                                   uri=uri_result.get('error', 'Invalid configuration'))

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)
    
    @handle_page_errors("Repository check")
    def check_repository_availability_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository availability check"""
        
        if not job_name:
            return self.destinations_handler._render_html('partials/error_message.html', {
                'error_message': 'Job name is required'
            })
        
        # Get and validate job configuration
        jobs = self.destinations_handler.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self.destinations_handler._render_html('partials/error_message.html', {
                'error_message': f"Job '{job_name}' not found"
            })
        
        job_config = jobs[job_name]
        # Perform repository availability check and return response
        return self.destinations_handler._check_and_respond_repository_status_html(job_name, job_config)


# Export handler instance
destinations_htmx = HTMXHandlers()