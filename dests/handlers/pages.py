"""
Destinations Page Handlers
Repository management, destination configuration, and validation
"""

import logging
from typing import Dict, Any, Callable, List
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

    # =============================================================================
    # DESTINATION FIELD RENDERING AND OPERATIONS - Extracted from mega-dispatcher
    # =============================================================================

    def _get_form_value(self, form_data: Dict[str, Any], key: str, default: str = '') -> str:
        """HTTP concern: extract single value from form data"""
        value_list = form_data.get(key, [default])
        return value_list[0] if value_list else default

    def _render_validation_result(self, status: str, message: str) -> str:
        """Render validation result with consistent styling"""
        import html
        
        status_class = {
            'success': 'success',
            'error': 'error', 
            'warning': 'warning'
        }.get(status, 'info')
        
        status_label = {
            'success': '[OK]',
            'error': '[ERROR]',
            'warning': '[WARN]'
        }.get(status, '[INFO]')
        
        return self.template_service.render_template('partials/validation_result.html',
                                                   status_class=status_class,
                                                   status_label=status_label,
                                                   message=html.escape(message))

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
        from models.forms import DestinationParser
        restic_result = DestinationParser.parse_restic_destination(form_data)
        
        if not restic_result['valid']:
            html_response = self._render_validation_result("error", restic_result['error'])
        else:
            # Direct repository initialization
            try:
                from services.restic_repository_service import ResticRepositoryService
                repo_service = ResticRepositoryService()
                result = repo_service.initialize_repository(restic_result['config'])
                
                if result['success']:
                    html_response = self._render_validation_result("success", "Repository initialized successfully")
                else:
                    html_response = self._render_validation_result("error", f"Initialization failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                html_response = self._render_validation_result("error", f"Initialization error: {str(e)}")

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

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
        
        from dests.schema import MAINTENANCE_MODE_SCHEMAS
        
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
            from dests.schema import RESTIC_REPOSITORY_TYPE_SCHEMAS
            
            html_response = self.template_service.render_template('partials/restic_repo_fields_dynamic.html',
                                                               repo_type=repo_type,
                                                               repo_schemas=RESTIC_REPOSITORY_TYPE_SCHEMAS)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

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
        repo_type = self._get_form_value(form_data, 'restic_repo_type') or self._get_form_value(form_data, 'repo_type')
        
        if not repo_type:
            html_response = self.template_service.render_template('partials/uri_preview.html',
                                                               uri='Select repository type to see URI preview')
        else:
            # Use existing URI builder from forms module
            from models.forms import DestinationParser
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
                
                html_response = self.template_service.render_template('partials/uri_preview.html', uri=uri)
            else:
                html_response = self.template_service.render_template('partials/uri_preview.html',
                                                                   uri=uri_result.get('error', 'Invalid configuration'))

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

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

    @handle_page_errors("Validate destination")
    def validate_destination(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Validate destination configuration"""
        dest_type = self._get_form_value(form_data, 'dest_type', '')
        hostname = self._get_form_value(form_data, 'hostname', '')
        
        if not dest_type or not hostname:
            template_context = {
                'success': False,
                'validation_message': 'Destination type and hostname are required for validation'
            }
        else:
            # Test basic connectivity based on destination type - delegate to destination validator
            from handlers.forms import DestinationValidationHandler
            destination_validator = DestinationValidationHandler()
            
            if dest_type == 'rsync':
                template_context = destination_validator.validate_rsync_destination(form_data)
            elif dest_type == 'rsyncd':
                template_context = destination_validator.validate_rsyncd_destination(form_data)
            elif dest_type == 'restic':
                template_context = destination_validator.validate_restic_destination(form_data)
            else:
                template_context = {
                    'success': False,
                    'validation_message': f'Validation not implemented for destination type: {dest_type}'
                }
        
        # Generate URI preview
        if template_context.get('success'):
            from models.forms import DestinationParser
            uri_result = DestinationParser.build_destination_uri(dest_type, form_data)
            if uri_result['valid']:
                template_context['uri_generated'] = uri_result['uri']
        
        return self._render_html('partials/destination_validation_result.html', template_context)

    @handle_page_errors("Destination type fields")
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
    
    @handle_page_errors("Network scan")
    def scan_network_for_rsyncd(self, network_range: str) -> JSONResponse:
        """Scan network for rsyncd services"""
        # TODO: Move core nmap scanning logic to dests/services/rsyncd.py for proper SoC
        import subprocess
        
        try:
            # Use nmap to scan for rsyncd (port 873)
            cmd = ['nmap', '-p', '873', '--open', network_range]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            servers = []
            total_checked = 0
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                current_host = None
                
                for line in lines:
                    line = line.strip()
                    if 'Nmap scan report for' in line:
                        current_host = line.split('for ')[-1]
                        total_checked += 1
                    elif '873/tcp open' in line and current_host:
                        # For each found server, try to get module list
                        modules = self._get_rsync_modules(current_host)
                        servers.append({
                            'ip': current_host,
                            'modules': modules
                        })
            
            return JSONResponse(content={
                'network_range': network_range,
                'total_checked': total_checked,
                'found_servers': len(servers),
                'servers': servers
            })
            
        except subprocess.TimeoutExpired:
            return JSONResponse(content={
                'error': f'Network scan timed out for range: {network_range}'
            }, status_code=408)
        except Exception as e:
            return JSONResponse(content={
                'error': f'Scan failed: {str(e)}'
            }, status_code=500)

    def _get_rsync_modules(self, host: str) -> List[Dict[str, str]]:
        """Get available rsync modules from a host"""
        import subprocess
        try:
            cmd = ['rsync', f'{host}::']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            modules = []
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('@'):
                        # Parse module line: "module_name   Description"
                        parts = line.split(None, 1)
                        if parts:
                            module = {'path': parts[0]}
                            if len(parts) > 1:
                                module['description'] = parts[1]
                            modules.append(module)
            
            return modules
        except:
            # If we can't get modules, just return basic info
            return [{'path': 'rsync', 'description': 'Rsync service available'}]

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
            html_response = self.template_service.render_template('partials/info_message.html',
                                                               message='Select a destination type to configure')
            return HTMLResponse(content=html_response)
        
        # Special handling for restic (has complex sub-types)
        if dest_type == 'restic':
            return await self.render_restic_fields_htmx(request)
        
        schema = DESTINATION_TYPE_SCHEMAS[dest_type]
        
        # Check if this destination type has fields requiring a template
        if schema.get('fields'):
            template_name = f'partials/dest_{dest_type}_fields.html'
            try:
                # Extract field values using schema field definitions
                template_values = {}
                for field_name, field_config in schema['fields'].items():
                    # Use the form field name directly (already mapped in schema)
                    template_values[field_name] = get_form_value(form_data, field_name)
                
                html_response = self.template_service.render_template(template_name, **template_values)
                return HTMLResponse(content=html_response)
            except Exception:
                # Template doesn't exist or failed to render
                html_response = self.template_service.render_template('partials/info_message.html',
                                                                   message=f'{schema["display_name"]} destination configuration')
                return HTMLResponse(content=html_response)
        else:
            # No fields defined in schema
            html_response = self.template_service.render_template('partials/info_message.html',
                                                               message=f'{schema["display_name"]} destination - configuration needed')
            return HTMLResponse(content=html_response)

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
        
        from services.data_services import ResticRepositoryTypeService
        
        repo_service = ResticRepositoryTypeService()
        available_repository_types = repo_service.get_available_repository_types()
        
        html_response = self.template_service.render_template('partials/job_form_dest_restic.html',
                                                           restic_password='',
                                                           restic_repo_type='',
                                                           available_repository_types=available_repository_types,
                                                           selected_repo_type='',
                                                           show_wrapper=False)
        return HTMLResponse(content=html_response)

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
        
        # Business logic: delegate to validation service
        from jobs.services.validate import ValidationService
        validation_service = ValidationService(self.backup_config)
        result = validation_service.ssh.validate_ssh_destination(hostname, username, path)
        
        # View: delegate to template service
        html_response = self.template_service.render_validation_status('ssh_dest', result)
        return HTMLResponse(content=html_response)

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
                html_response = self.template_service.render_validation_status('restic', {
                    'valid': False, 'error': f'{display_name} destination missing {field}'
                })
                return HTMLResponse(content=html_response)
        
        # Build URI from individual repository fields using existing URI builder
        from models.forms import DestinationParser
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        
        if not uri_result.get('valid'):
            html_response = self.template_service.render_validation_status('restic', {
                'valid': False, 'error': uri_result.get('error', 'Invalid repository configuration')
            })
            return HTMLResponse(content=html_response)
        
        repo_uri = uri_result['uri']
        
        # Business logic: delegate to validation service
        from jobs.services.validate import ValidationService
        validation_service = ValidationService(self.backup_config)
        result = validation_service.validate_restic_config(repo_type, repo_uri, password)
        
        # View: delegate to template service
        html_response = self.template_service.render_validation_status('restic', result)
        return HTMLResponse(content=html_response)

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
        
        try:
            # Extract repository path
            repo_path = get_form_value(form_data, 'origin_repo_path')
            if not repo_path or not repo_path.strip():
                result = {'valid': False, 'error': 'Please enter a repository path'}
                html_response = self.template_service.render_validation_status('origin_repo_path', result)
                return HTMLResponse(content=html_response)
            
            # Extract SSH configuration (required for same_as_origin)
            hostname = get_form_value(form_data, 'hostname')
            username = get_form_value(form_data, 'username')
            
            if not hostname or not username:
                result = {'valid': False, 'error': 'SSH configuration required for same-as-origin repositories'}
                html_response = self.template_service.render_validation_status('origin_repo_path', result)
                return HTMLResponse(content=html_response)
            
            # Business logic: delegate to validation service
            from jobs.services.validate import ValidationService
            validation_service = ValidationService(self.backup_config)
            result = validation_service.ssh.validate_ssh_repo_path_with_creation(hostname, username, repo_path)
            
            # View: delegate to template service
            html_response = self.template_service.render_validation_status('origin_repo_path', result)
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            result = {'valid': False, 'error': f'Validation failed: {str(e)}'}
            html_response = self.template_service.render_validation_status('origin_repo_path', result)
            return HTMLResponse(content=html_response)

# Global handler instance
destinations_handler = DestinationsHandler()