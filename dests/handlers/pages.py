"""
Destinations Page Handlers
Repository management, destination configuration, and validation
"""

import logging
from typing import Dict, Any, Callable, List
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from services.template import TemplateService
from config import BackupConfig
from models.forms import safe_get_value, safe_get_list

logger = logging.getLogger(__name__)


# =============================================================================
# DESTINATION FORM PARSER
# =============================================================================

class DestinationParser:
    """Parse destination configurations (SSH, local, rsyncd, restic)"""
    
    @staticmethod
    def parse_ssh_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SSH destination configuration"""
        hostname = safe_get_value(form_data, 'dest_hostname')
        username = safe_get_value(form_data, 'dest_username')
        path = safe_get_value(form_data, 'dest_path')
        
        if not hostname:
            return {'valid': False, 'error': 'SSH destination hostname is required'}
        if not username:
            return {'valid': False, 'error': 'SSH destination username is required'}
        if not path:
            return {'valid': False, 'error': 'SSH destination path is required'}
        
        config = {
            'hostname': hostname.strip(),
            'username': username.strip(),
            'path': path.strip()
        }
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_local_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse local destination configuration"""
        path = safe_get_value(form_data, 'dest_path')
        
        if not path:
            return {'valid': False, 'error': 'Local destination path is required'}
        
        config = {'path': path.strip()}
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_rsyncd_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse rsyncd destination configuration"""
        hostname = safe_get_value(form_data, 'rsyncd_hostname')
        share = safe_get_value(form_data, 'rsyncd_share')
        
        if not hostname:
            return {'valid': False, 'error': 'Rsyncd hostname is required'}
        if not share:
            return {'valid': False, 'error': 'Rsyncd share is required'}
        
        config = {
            'hostname': hostname.strip(),
            'share': share.strip()
        }
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_restic_destination(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Restic destination configuration with all repository types"""
        repo_type = safe_get_value(form_data, 'restic_repo_type')
        password = safe_get_value(form_data, 'restic_password')
        
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
                return {'valid': False, 'error': f'{display_name} destination missing {field}'}
        
        # Generate repository URI based on type
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        if not uri_result['valid']:
            return uri_result
        
        # Base config with URI and password
        config = {
            'repo_type': repo_type,
            'repo_uri': uri_result['uri'],
            'password': password
        }
        
        # Store discrete fields for form editing round-trip
        DestinationParser._store_discrete_fields(config, repo_type, form_data)
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def build_destination_uri(dest_type, form_data):
        """Higher-order URI builder for all destination types"""
        if dest_type == 'rsync':
            hostname = safe_get_value(form_data, 'hostname')
            username = safe_get_value(form_data, 'username')
            path = safe_get_value(form_data, 'path')
            port = safe_get_value(form_data, 'port', '22')
            
            if not all([hostname, username, path]):
                return {'valid': False, 'error': 'Rsync destination requires hostname, username, and path'}
            
            if port != '22':
                uri = f"{username}@{hostname}:{path} (port {port})"
            else:
                uri = f"{username}@{hostname}:{path}"
            
            return {'valid': True, 'uri': uri}
            
        elif dest_type == 'rsyncd':
            hostname = safe_get_value(form_data, 'hostname')
            share = safe_get_value(form_data, 'share')
            port = safe_get_value(form_data, 'port', '873')
            
            if not all([hostname, share]):
                return {'valid': False, 'error': 'Rsyncd destination requires hostname and share'}
            
            if port != '873':
                uri = f"rsync://{hostname}:{port}/{share}"
            else:
                uri = f"rsync://{hostname}/{share}"
            
            return {'valid': True, 'uri': uri}
            
        elif dest_type == 'restic':
            repo_type = safe_get_value(form_data, 'repo_type', '')
            return DestinationParser._build_restic_uri(repo_type, form_data)
            
        else:
            return {'valid': False, 'error': f'Unknown destination type: {dest_type}'}

    @staticmethod
    def _build_restic_uri(repo_type, form_data):
        """Build Restic repository URI based on type"""
        if repo_type == 'local':
            path = safe_get_value(form_data, 'local_path')
            if not path:
                return {'valid': False, 'error': 'Local repository path is required'}
            return {'valid': True, 'uri': path.strip()}
            
        elif repo_type == 'rest':
            hostname = safe_get_value(form_data, 'hostname')
            port = safe_get_value(form_data, 'port', '8000')
            path = safe_get_value(form_data, 'path', '')
            use_root = safe_get_value(form_data, 'use_root') == 'on'
            use_https = safe_get_value(form_data, 'use_https') == 'on'
            username = safe_get_value(form_data, 'username', '')
            password = safe_get_value(form_data, 'password', '')
            
            if not hostname:
                return {'valid': False, 'error': 'REST server hostname is required'}
            
            # Validate path logic: either path OR use_root must be true, but not both, not neither
            has_path = bool(path.strip())
            if has_path and use_root:
                return {'valid': False, 'error': 'Cannot specify both repository path and use repository root - choose one'}
            if not has_path and not use_root:
                return {'valid': False, 'error': 'Must specify either a repository path or check "Use Repository Root"'}
            
            # Build URI components
            scheme = 'https' if use_https else 'http'
            
            # Build authority (user:pass@host:port or just host:port)
            authority = f'{hostname}:{port}'
            if username and password:
                authority = f'{username}:{password}@{authority}'
            elif username:
                authority = f'{username}@{authority}'
            
            # Build path
            if use_root:
                uri_path = ''  # No trailing slash for repository root
            else:
                # Ensure path starts with /
                clean_path = path.strip()
                if not clean_path.startswith('/'):
                    clean_path = '/' + clean_path
                uri_path = clean_path
            
            return {'valid': True, 'uri': f'rest:{scheme}://{authority}{uri_path}'}
            
        elif repo_type == 's3':
            bucket = safe_get_value(form_data, 'bucket')
            prefix = safe_get_value(form_data, 'prefix', '')
            endpoint = safe_get_value(form_data, 'endpoint', '')
            region = safe_get_value(form_data, 'region', 'us-east-1')  # Default for compatibility
            access_key = safe_get_value(form_data, 'access_key')
            secret_key = safe_get_value(form_data, 'secret_key')
            
            if not bucket:
                return {'valid': False, 'error': 'S3 bucket name is required'}
            if not access_key:
                return {'valid': False, 'error': 'S3 access key is required'}
            if not secret_key:
                return {'valid': False, 'error': 'S3 secret key is required'}
            
            # Build URI using restic S3 format
            if endpoint:
                # Custom S3-compatible endpoint (Cloudflare R2, MinIO, etc.)
                # Format: s3:https://endpoint/bucket
                uri = f's3:{endpoint}/{bucket}'
            else:
                # AWS S3 - use region-based endpoint
                # Format: s3:s3.region.amazonaws.com/bucket  
                uri = f's3:s3.{region}.amazonaws.com/{bucket}'
            
            if prefix:
                uri += f'/{prefix}'
            return {'valid': True, 'uri': uri}
            
        elif repo_type == 'sftp':
            hostname = safe_get_value(form_data, 'hostname')
            username = safe_get_value(form_data, 'username')
            path = safe_get_value(form_data, 'path')
            
            if not hostname:
                return {'valid': False, 'error': 'SFTP hostname is required'}
            if not username:
                return {'valid': False, 'error': 'SFTP username is required'}
            if not path:
                return {'valid': False, 'error': 'SFTP path is required'}
            
            return {'valid': True, 'uri': f'sftp:{username}@{hostname}:{path}'}
            
        elif repo_type == 'rclone':
            remote = safe_get_value(form_data, 'remote')
            path = safe_get_value(form_data, 'path')
            
            if not remote:
                return {'valid': False, 'error': 'rclone remote name is required'}
            if not path:
                return {'valid': False, 'error': 'rclone path is required'}
            
            return {'valid': True, 'uri': f'rclone:{remote}:{path}'}
            
        elif repo_type == 'same_as_origin':
            path = safe_get_value(form_data, 'path')
            if not path:
                return {'valid': False, 'error': 'Origin repository path is required'}
            return {'valid': True, 'uri': path.strip()}
        
        else:
            return {'valid': False, 'error': f'Unknown repository type: {repo_type}'}
    
    @staticmethod
    def _store_discrete_fields(config, repo_type, form_data):
        """Store discrete fields for form editing round-trip data integrity using schema"""
        from dests.schema import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
        if repo_type in RESTIC_REPOSITORY_TYPE_SCHEMAS:
            schema = RESTIC_REPOSITORY_TYPE_SCHEMAS[repo_type]
            
            # Iterate through schema fields and extract values
            for field_def in schema.get('fields', []):
                field_name = field_def['name']
                
                # Handle different field types
                if field_def.get('type') == 'checkbox':
                    # Checkbox fields use 'on' for checked
                    config[field_name] = safe_get_value(form_data, field_name) == 'on'
                else:
                    # Text/number fields use placeholder as default or empty string
                    default_value = field_def.get('placeholder', '')
                    config[field_name] = safe_get_value(form_data, field_name, default_value)

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
    
    # =========================================================================
    # DESTINATION VALIDATION RENDERING (moved from services/template.py)
    # =========================================================================
    
    def render_ssh_dest_validation_status(self, result: Dict[str, Any]) -> str:
        """Render SSH destination validation status with path permissions details"""
        details = []
        
        # SSH connection always appears first when present (success or failure)
        if result.get('ssh_status') == 'OK':
            details.append("SSH connection successful")
            
            # Path validation details (destination validation only)
            if result.get('path_permissions'):
                permissions = result['path_permissions']
                if permissions == 'RWX':
                    details.append(f"Path permissions: {permissions} (backup + restore capable)")
                elif permissions == 'RO':
                    details.append(f"Path permissions: {permissions} (backup only - no restore capability)")
                else:
                    details.append(f"Path permissions: {permissions}")
        
        return self._render_validation_status_template(result, details)
    
    def render_restic_validation_status(self, result: Dict[str, Any]) -> str:
        """Render Restic validation status (basic validation, no special details)"""
        return self._render_validation_status_template(result, [])
    
    def render_origin_repo_path_validation_status(self, result: Dict[str, Any]) -> str:
        """Render origin repository path validation status (same as SSH dest)"""
        # Same logic as ssh_dest - checking path on origin host for same-as-origin repos
        return self.render_ssh_dest_validation_status(result)
    
    def _render_validation_status_template(self, result: Dict[str, Any], details: list) -> str:
        """Helper method to render validation status template with consistent logic"""
        # Determine status class and label
        if result.get('valid', False):
            status_class = 'success'
            status_label = '[OK]'
        else:
            status_class = 'error'
            status_label = '[ERROR]'
        
        # Build message from details or error
        if details:
            # Pass details as a list for proper formatting in template
            message = None
        else:
            # Use appropriate message based on validation result
            if result.get('valid', False):
                message = result.get('message', 'Validation successful')
            else:
                message = result.get('error', 'Validation failed')
            details = None
        
        # Use template service to render the result
        return self.template_service.render_template('partials/validation_result.html', 
                                       status_class=status_class,
                                       status_label=status_label,
                                       message=message,
                                       details=details)
    
    # =========================================================================
    # PAGE HANDLERS
    # =========================================================================
    
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
        value = form_data.get(key, default)
        if isinstance(value, list) and len(value) > 0:
            return str(value[0])
        return str(value) if value else default

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
        # DestinationParser is now local to this module
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
                                                               repo_schemas=RESTIC_REPOSITORY_TYPE_SCHEMAS,
                                                               field_values={})

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
            # DestinationParser is now local to this module
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

    async def add_destination_htmx(self, request) -> JSONResponse:
        """Add destination with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.add_destination(form_data)

    def add_destination(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new destination"""
        
        # Extract basic destination info
        dest_name = self._get_form_value(form_data, 'dest_name', '').strip()
        friendly_name = self._get_form_value(form_data, 'friendly_name', '').strip()
        dest_type = self._get_form_value(form_data, 'dest_type', '')
        hostname = self._get_form_value(form_data, 'hostname', '').strip()
        port = self._get_form_value(form_data, 'port', '')
        
        # Validation
        if not dest_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination name is required'
            }, status_code=400)
            
        if not dest_type:
            return JSONResponse(content={
                'success': False,
                'error': 'Destination type is required'
            }, status_code=400)
        
        # Check if destination already exists
        existing_destinations = self.backup_config.get_destinations()
        if dest_name in existing_destinations:
            return JSONResponse(content={
                'success': False,
                'error': f'Destination "{dest_name}" already exists'
            }, status_code=400)
        
        # Build nested destination config following example pattern
        dest_config = {
            'type': dest_type,
            'uri': '',  # Will be generated
            'hostname': hostname,
            'port': int(port) if port else self._get_default_port(dest_type),
            'friendly_name': friendly_name or dest_name
        }
        
        # Add type-specific nested sections
        if dest_type == 'rsync':
            username = self._get_form_value(form_data, 'username', '').strip()
            path = self._get_form_value(form_data, 'path', '').strip()
            
            if not username or not path:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Username and path are required for rsync destinations'
                }, status_code=400)
            
            dest_config['rsync'] = {
                'username': username,
                'path': path
            }
            
        elif dest_type == 'rsyncd':
            share = self._get_form_value(form_data, 'share', '').strip()
            
            if not share:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Share is required for rsyncd destinations'
                }, status_code=400)
            
            rsyncd_config = {'share': share}
            
            # Optional fields
            username = self._get_form_value(form_data, 'username', '').strip()
            password = self._get_form_value(form_data, 'password', '').strip()
            if username:
                rsyncd_config['username'] = username
            if password:
                rsyncd_config['password'] = password
                
            dest_config['rsyncd'] = rsyncd_config
            
        elif dest_type == 'restic':
            repo_type = self._get_form_value(form_data, 'repo_type', '')
            password = self._get_form_value(form_data, 'password', '')
            
            if not repo_type or not password:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Repository type and password are required for restic destinations'
                }, status_code=400)
            
            dest_config['restic'] = {
                'type': repo_type,
                'password': password
            }
            
            # Add repo type-specific nested config
            if repo_type == 'rest':
                rest_config = {}
                # Add REST-specific fields as they're implemented
                dest_config['restic']['rest'] = rest_config
            # Other restic types can be added similarly
        
        # Generate URI using the nested structure
        flat_data = self._flatten_dest_config_for_uri(dest_config)
        dest_config['uri'] = self._build_destination_uri(flat_data)
        
        # Save destination
        success = self.backup_config.save_destination(dest_name, dest_config)
        
        if success:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save destination '{dest_name}'"
            }, status_code=500)

    def _get_default_port(self, dest_type: str) -> int:
        """Get default port for destination type"""
        defaults = {
            'rsync': 22,
            'rsyncd': 873,
            'restic': 443
        }
        return defaults.get(dest_type, 22)

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
        # DestinationParser is now local to this module
        
        dest_type = dest_config.get('type')
        uri_result = DestinationParser.build_destination_uri(dest_type, dest_config)
        
        if uri_result['valid']:
            return uri_result['uri']
        else:
            return f"Error: {uri_result.get('error', 'URI generation failed')}"

    @handle_page_errors("Save destination")
    async def save_destination_htmx(self, request) -> JSONResponse:
        """Save destination with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.save_destination(form_data)

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
    async def validate_destination_htmx(self, request) -> HTMLResponse:
        """Validate destination with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.validate_destination(form_data)

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
            # Test basic connectivity based on destination type using atomic services
            if dest_type == 'rsync':
                # Use superior rsync validation from atomic service (SSH + path writability)
                from dests.services.rsync import rsync_service
                result = rsync_service.validate_rsync_destination(form_data)
                template_context = {
                    'success': result['success'],
                    'validation_message': result.get('message') or result.get('error', 'Unknown error')
                }
            elif dest_type == 'rsyncd':
                # Use superior rsyncd validation from atomic service
                from dests.services.rsync import rsync_service
                result = rsync_service.validate_rsyncd_destination(form_data)
                template_context = {
                    'success': result['success'],
                    'validation_message': result.get('message') or result.get('error', 'Unknown error')
                }
            elif dest_type == 'restic':
                # Use superior restic validation from atomic service (real repository connectivity)
                from dests.services.restic import restic_service
                result = restic_service.validate_restic_destination(form_data)
                template_context = {
                    'success': result['success'],
                    'validation_message': result.get('message', 'Unknown error')
                }
            else:
                template_context = {
                    'success': False,
                    'validation_message': f'Validation not implemented for destination type: {dest_type}'
                }
        
        # Generate URI preview
        if template_context.get('success'):
            # DestinationParser is now local to this module
            uri_result = DestinationParser.build_destination_uri(dest_type, form_data)
            if uri_result['valid']:
                template_context['uri_generated'] = uri_result['uri']
        
        return self._render_html('partials/destination_validation_result.html', template_context)

    @handle_page_errors("Destination type fields")
    async def destination_type_fields_htmx(self, request) -> HTMLResponse:
        """Load destination type fields with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.destination_type_fields(form_data)

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
        
        from dests.services.restic import ResticRepositoryTypeService
        
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
        
        # View: delegate to local validation method (moved from template service)
        html_response = self.render_ssh_dest_validation_status(result)
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
                html_response = self.render_restic_validation_status({
                    'valid': False, 'error': f'{display_name} destination missing {field}'
                })
                return HTMLResponse(content=html_response)
        
        # Build URI from individual repository fields using existing URI builder
        # DestinationParser is now local to this module
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        
        if not uri_result.get('valid'):
            html_response = self.render_restic_validation_status({
                'valid': False, 'error': uri_result.get('error', 'Invalid repository configuration')
            })
            return HTMLResponse(content=html_response)
        
        repo_uri = uri_result['uri']
        
        # Business logic: delegate to validation service
        from jobs.services.validate import ValidationService
        validation_service = ValidationService(self.backup_config)
        result = validation_service.validate_restic_config(repo_type, repo_uri, password)
        
        # View: delegate to local validation method (moved from template service)
        html_response = self.render_restic_validation_status(result)
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
                html_response = self.render_origin_repo_path_validation_status(result)
                return HTMLResponse(content=html_response)
            
            # Extract SSH configuration (required for same_as_origin)
            hostname = get_form_value(form_data, 'hostname')
            username = get_form_value(form_data, 'username')
            
            if not hostname or not username:
                result = {'valid': False, 'error': 'SSH configuration required for same-as-origin repositories'}
                html_response = self.render_origin_repo_path_validation_status(result)
                return HTMLResponse(content=html_response)
            
            # Business logic: delegate to validation service
            from jobs.services.validate import ValidationService
            validation_service = ValidationService(self.backup_config)
            result = validation_service.ssh.validate_ssh_repo_path_with_creation(hostname, username, repo_path)
            
            # View: delegate to local validation method (moved from template service)
            html_response = self.render_origin_repo_path_validation_status(result)
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            result = {'valid': False, 'error': f'Validation failed: {str(e)}'}
            html_response = self.render_origin_repo_path_validation_status(result)
            return HTMLResponse(content=html_response)

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

    def unlock_repository_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository unlock - business logic calls destinations service"""
        
        if not job_name:
            return self._render_html('partials/error_message.html', {
                'error_message': 'Job name is required'
            })
            
        # Get and validate job configuration
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_html('partials/error_message.html', {
                'error_message': f"Job '{job_name}' not found"
            })
        
        job_config = jobs[job_name]
        dest_type = job_config.get('dest_type')
        
        if dest_type != 'restic':
            return self._render_html('partials/error_message.html', {
                'error_message': 'Unlock is only supported for restic repositories'
            })
        
        # Execute restic unlock command via destinations service
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        from dests.services.restic import restic_service
        result = restic_service.unlock_repository(dest_config, source_config)
        
        if result.get('success'):
            # Unlock successful - automatically retry availability check
            return self.check_repository_availability_htmx(job_name)
        else:
            # Unlock failed - show error
            return self._render_html('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'unlock_failed',
                'error_message': result.get('error', 'Unlock failed')
            })

    @handle_page_errors("Repository check")
    def check_repository_availability_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository availability check"""
        
        if not job_name:
            return self._render_html('partials/error_message.html', {
                'error_message': 'Job name is required'
            })
        
        # Get and validate job configuration
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_html('partials/error_message.html', {
                'error_message': f"Job '{job_name}' not found"
            })
        
        job_config = jobs[job_name]
        # Perform repository availability check and return response
        return self._check_and_respond_repository_status_html(job_name, job_config)

    def _check_and_respond_repository_status_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check repository availability and return appropriate HTMX HTML response"""
        dest_type = job_config.get('dest_type')
        
        if dest_type == 'restic':
            return self._check_restic_repository_html(job_name, job_config)
        else:
            # Non-restic repositories - assume available for now
            return self._render_html('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': dest_type
            })

    def _check_restic_repository_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check restic repository availability and return HTML response"""
        dest_config = job_config.get('dest_config', {})
        repo_uri = dest_config.get('repo_uri')
        
        if not repo_uri:
            return self._render_html('partials/error_message.html', {
                'error_message': 'Repository URI not configured'
            })
            
        from dests.services.restic import restic_service
        check_success, check_message = restic_service._quick_repository_check(repo_uri, dest_config)
        
        if check_success:
            return self._render_html('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': 'restic'
            })
        else:
            return self._send_repository_error_html(job_name, check_message)

    def _send_repository_error_html(self, job_name: str, error_message: str) -> HTMLResponse:
        """Send appropriate repository error HTMX partial based on error type"""
        if error_message and ('locked by' in error_message.lower() or 'repository is already locked' in error_message.lower()):
            # Repository locked - render unlock interface
            return self._render_html('partials/repository_locked_error.html', {
                'job_name': job_name,
                'error_message': error_message
            })
        else:
            # Other error - render error template
            return self._render_html('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'connection_error',
                'error_message': error_message or 'Unknown error'
            })

# Global handler instance
destinations_handler = DestinationsHandler()