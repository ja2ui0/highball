"""
Origins Page Handlers
SSH host management, origin configuration, and capability validation
"""

import logging
from functools import wraps
from typing import Dict, Any, Callable
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from dataclasses import dataclass

from services.template import TemplateService
from config import BackupConfig

logger = logging.getLogger(__name__)

@dataclass
class HtmxFormData:
    """Parsed HTMX form data with common headers"""
    form_data: Dict[str, Any]
    hx_request: bool
    hx_target: str | None
    hx_trigger: str | None
    hx_current_url: str | None

def parse_htmx_form(func: Callable) -> Callable:
    """Decorator that parses HTMX form data and provides clean error responses"""
    @wraps(func)
    async def wrapper(self, request: Request, form_data: Dict[str, Any]) -> HTMLResponse:
        try:
            # Extract HTMX headers
            hx_request = request.headers.get('HX-Request', 'false').lower() == 'true'
            hx_target = request.headers.get('HX-Target')
            hx_trigger = request.headers.get('HX-Trigger')
            hx_current_url = request.headers.get('HX-Current-URL')
            
            # Create parsed form data object
            parsed_form = HtmxFormData(
                form_data=form_data,
                hx_request=hx_request,
                hx_target=hx_target,
                hx_trigger=hx_trigger,
                hx_current_url=hx_current_url
            )
            
            # Call the actual handler with clean parsed data
            html_response = await func(self, parsed_form)
            
            # Return HTMX-compatible HTML response
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            logger.error(f"HTMX form processing failed in {func.__name__}: {e}")
            # Return basic error HTML that works with any HTMX target
            error_html = f'<div class="error">Form processing failed: {str(e)}</div>'
            return HTMLResponse(content=error_html, status_code=500)
    
    return wrapper

def get_form_value(form_data: Dict[str, Any], key: str, default: str = '') -> str:
    """Extract single value from form data (works with FastAPI form parsing)"""
    value_list = form_data.get(key, [default])
    return value_list[0] if value_list else default

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

class OriginsHandler(BaseHandler):
    """Handle SSH origins management and validation"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.backup_config = BackupConfig()
    
    @handle_page_errors("Show SSH origins")
    def show_ssh_origins(self) -> HTMLResponse:
        """Show SSH origins management page"""
        origins = self.backup_config.get_ssh_origins()
        global_settings = self.backup_config.get_global_settings()
        
        # Build origin display list
        origin_list = []
        for origin_name, origin_config in origins.items():
            # Determine authentication method display
            auth_method = "Highball SSH Key" if origin_config.get('ssh_highball', True) else "User SSH Key"
            
            # Connection info display
            connection_info = f"{origin_config.get('ssh_username')}@{origin_config.get('ssh_hostname')}:{origin_config.get('ssh_port', 22)}"
            
            # Capabilities display
            capabilities = []
            if origin_config.get('rsync_available'):
                capabilities.append("rsync")
            if origin_config.get('container_runtime'):
                capabilities.append(origin_config['container_runtime'])
            capabilities_display = ", ".join(capabilities) if capabilities else "Not detected"
            
            origin_display = {
                'name': origin_name,
                'friendly_name': origin_config.get('friendly_name', origin_name),
                'connection_info': connection_info,
                'auth_method': auth_method,
                'capabilities': capabilities_display,
                'config': origin_config
            }
            origin_list.append(origin_display)
        
        # Sort by friendly name for consistent display
        origin_list.sort(key=lambda x: x['friendly_name'].lower())
        
        template_data = {
            'origins': origin_list,
            'global_settings': global_settings,
            'theme_css_path': '',
            'page_title': 'SSH Origins'
        }
        
        return self._render_html('pages/ssh_config.html', template_data)

    @handle_page_errors("Edit SSH origin")
    def edit_ssh_origin(self, origin_name: str) -> HTMLResponse:
        """Load SSH origin for editing"""
        origin_config = self.backup_config.get_ssh_origin(origin_name)
        
        if not origin_config:
            # Return empty form if origin not found
            return self._render_html('partials/ssh_origin_form.html', {})
        
        # Create edit form with populated values including existing capabilities
        form_data = {
            'origin_name': origin_name,
            'friendly_name': origin_config.get('friendly_name', ''),
            'ssh_hostname': origin_config.get('ssh_hostname', ''),
            'ssh_username': origin_config.get('ssh_username', ''),
            'ssh_port': origin_config.get('ssh_port', 22),
            'ssh_timeout': origin_config.get('ssh_timeout', 5),
            'ssh_highball': origin_config.get('ssh_highball', True),
            'rsync_available': origin_config.get('rsync_available', False),
            'container_runtime': origin_config.get('container_runtime', None),
            'edit_mode': True  # Flag to indicate this is edit mode
        }
        
        return self._render_html('partials/ssh_origin_form.html', form_data)

    @handle_page_errors("Delete SSH origin")
    def delete_ssh_origin(self, origin_name: str) -> JSONResponse:
        """Delete SSH origin"""
        
        if not origin_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Origin name is required'
            }, status_code=400)
        
        success = self.backup_config.delete_origin(origin_name)
        
        if success:
            return RedirectResponse(url='/ssh', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to delete origin '{origin_name}'"
            }, status_code=500)

    async def add_ssh_origin_htmx(self, request) -> JSONResponse:
        """Add SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.add_ssh_origin(form_data)

    @handle_page_errors("Add SSH origin")
    def add_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new SSH origin"""
        from models.forms import origin_parser
        
        
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        
        # Check if origin already exists
        existing_origins = self.backup_config.get_ssh_origins()
        if origin_name in existing_origins:
            return JSONResponse(content={
                'success': False,
                'error': f'Origin "{origin_name}" already exists'
            }, status_code=400)
        
        # Save origin with capabilities from form parser (including any detected values)
        success = self.backup_config.save_origin(origin_name, origin_config)
        
        if success:
            return RedirectResponse(url='/ssh', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save origin '{origin_name}'"
            }, status_code=500)

    async def save_ssh_origin_htmx(self, request) -> JSONResponse:
        """Save SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.save_ssh_origin(form_data)

    async def validate_ssh_origin_htmx(self, request) -> JSONResponse:
        """Validate SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.validate_ssh_origin(form_data)

    async def toggle_ssh_auth_method_htmx(self, request) -> HTMLResponse:
        """Toggle SSH auth method with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.toggle_ssh_auth_method(form_data)

    @handle_page_errors("Save SSH origin")
    def save_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save SSH origin changes"""
        from models.forms import origin_parser
        
        
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        original_origin_name = self._get_form_value(form_data, 'original_origin_name', '')
        
        # Handle renaming if the origin name changed
        if original_origin_name and original_origin_name != origin_name:
            # Delete the old file
            self.backup_config.delete_origin(original_origin_name)
        
        # Save origin with detected capabilities (overwrites existing or creates new)
        success = self.backup_config.save_origin(origin_name, origin_config)
        
        if success:
            return RedirectResponse(url='/ssh', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save origin '{origin_name}'"
            }, status_code=500)

    def _get_form_value(self, form_data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Helper to get form value with default"""
        return form_data.get(key, default)

    @handle_page_errors("SSH source validation")
    def validate_ssh_source(self, source: str) -> JSONResponse:
        """Validate SSH source configuration"""
        # Parse source string (format: username@hostname)
        if '@' not in source:
            return JSONResponse(content={
                'valid': False,
                'error': 'Invalid source format. Expected: username@hostname'
            })
        
        username, hostname = source.split('@', 1)
        ssh_config = {'username': username, 'hostname': hostname}
        
        # Use unified validation service
        from jobs.services.validate import ValidationService
        validation_service = ValidationService()
        result = validation_service.validate_ssh_source(ssh_config)
        return JSONResponse(content=result)

    @handle_page_errors("SSH origin validation")
    def validate_ssh_origin(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Push keys and validate SSH origin configuration with persistent session tracking"""
        from models.forms import origin_parser
        import uuid
        import threading
        import json
        import os
        
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content=origin_result)
        
        origin_config = origin_result['origin_config']
        edit_mode = 'original_origin_name' in form_data and form_data['original_origin_name']
        
        # Extract connection details
        hostname = origin_config['ssh_hostname']
        username = origin_config['ssh_username']  
        password = form_data.get('ssh_password', '')
        ssh_highball = form_data.get('ssh_highball') == 'on'
        
        # Require password when Highball checkbox is checked
        if ssh_highball and not password:
            return self._render_html('partials/ssh_validation_result.html', {
                'success': False,
                'edit_mode': edit_mode,
                'validation_message': 'Password is required when "Auto-populate keys using Highball" is checked.'
            })
        
        use_password = ssh_highball and password
        
        # Generate session ID and create persistent session file
        session_id = str(uuid.uuid4())
        session_dir = '/tmp/ssh_validation_sessions'
        os.makedirs(session_dir, exist_ok=True)
        session_file = f"{session_dir}/{session_id}.json"
        
        # Initialize session data
        session_data = {
            'progress': ['• Starting SSH validation workflow...'],
            'completed': False,
            'success': None,
            'result': None,
            'edit_mode': edit_mode
        }
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f)
        
        # Start background workflow
        def run_workflow():
            try:
                result = self._push_keys_and_validate_workflow_with_session(session_id, hostname, username, password, use_password)
                # Update session with completion
                session_data['completed'] = True
                session_data['result'] = result
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
            except Exception as e:
                # Handle workflow errors
                error_result = {
                    'success': False,
                    'validation_message': f'Validation failed: {str(e)}'
                }
                session_data['completed'] = True
                session_data['result'] = error_result
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
        
        threading.Thread(target=run_workflow, daemon=True).start()
        
        # Return initial progress template
        return self._render_html('partials/ssh_validation_progress.html', {
            'session_id': session_id,
            'initial_message': "Starting SSH validation workflow..."
        })
    
    @handle_page_errors("SSH progress polling")
    def get_ssh_progress(self, session_id: str) -> HTMLResponse:
        """Get current SSH validation progress for a session using persistent storage"""
        import json
        import os
        
        session_file = f"/tmp/ssh_validation_sessions/{session_id}.json"
        
        if not os.path.exists(session_file):
            return self._render_html('partials/ssh_validation_expired.html', {
                'success': False,
                'validation_message': "Session not found or expired"
            })
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return self._render_html('partials/ssh_validation_expired.html', {
                'success': False,
                'validation_message': "Session data corrupted"
            })
        
        progress_text = '\n'.join(session_data['progress'])
        
        if not session_data['completed']:
            # Still in progress - return progress template with polling
            return self._render_html('partials/ssh_validation_progress.html', {
                'session_id': session_id,
                'initial_message': progress_text
            })
        else:
            # Completed - return final result and schedule cleanup
            result = session_data['result']
            result['edit_mode'] = session_data['edit_mode']
            # Schedule cleanup after a longer delay to prevent race conditions
            import threading
            def delayed_cleanup():
                import time
                time.sleep(15)  # Wait 15 seconds before cleanup (was 5, too short)
                try:
                    os.remove(session_file)
                except OSError:
                    pass  # Ignore cleanup errors
            threading.Thread(target=delayed_cleanup, daemon=True).start()
            return self._render_html('partials/ssh_validation_result.html', result)
    
    def _push_keys_and_validate_workflow(self, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete workflow: push keys → validate connection → detect capabilities"""
        # Initialize SSH workflow service
        from services.execution import SSHWorkflowService
        ssh_service = SSHWorkflowService()
        # Delegate to SSH service - this is pure business logic
        return ssh_service.push_keys_and_validate_workflow(hostname, username, password, use_password)
    
    def _push_keys_and_validate_workflow_with_session(self, session_id: str, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete workflow with session progress tracking using persistent storage"""
        import json
        import os
        
        session_file = f"/tmp/ssh_validation_sessions/{session_id}.json"
        
        # Get the result from the SSH service
        result = self._push_keys_and_validate_workflow(hostname, username, password, use_password)
        
        # Update session progress with service result
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                # Split the service's validation message into progress steps
                if result.get('validation_message'):
                    progress_lines = result['validation_message'].split('\n')
                    session_data['progress'] = progress_lines
                else:
                    session_data['progress'].append('• SSH validation completed')
                
                # Save updated progress
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
            except (json.JSONDecodeError, IOError):
                pass  # Ignore session update errors
        
        return result
    
    @handle_page_errors("Toggle SSH auth method")
    def toggle_ssh_auth_method(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Toggle between Highball and user SSH authentication methods"""
        ssh_highball = 'ssh_highball' in form_data
        
        if ssh_highball:
            # Checkbox checked: show password field for automatic key installation
            template = 'partials/ssh_auth_highball.html'
            template_context = {}
        else:
            # Checkbox unchecked: show manual key copy instructions
            template = 'partials/ssh_auth_user.html'
            # Read Highball public key for display
            template_context = {
                'highball_public_key': self._get_highball_public_key()
            }
        
        return self._render_html(template, template_context)
    
    def _get_highball_public_key(self) -> str:
        """Read Highball public key content"""
        try:
            with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
                return f.read().strip()
        except Exception as e:
            return f"Error reading public key: {str(e)}"

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
        
        # Extract parameters from form data
        hostname = get_form_value(form_data, 'hostname')
        username = get_form_value(form_data, 'username')
        
        # Build source config
        source_config = {'hostname': hostname, 'username': username}
        
        # Use validation service for business logic
        from jobs.services.validate import ValidationService
        backup_config = BackupConfig()
        validation_service = ValidationService(backup_config)
        result = validation_service.ssh.validate_ssh_source(source_config)
        
        # Render validation status using template service
        html_response = self.template_service.render_validation_status('ssh_source', result)
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
        
        source_type = form_data.get('source_type', [''])[0]
        
        # Schema-driven source field rendering
        from origins.schema import SOURCE_TYPE_SCHEMAS
        
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
        
        try:
            import yaml
            
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
            from models.forms import origin_parser
            
            origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
            if not origin_result['valid']:
                html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                                   preview_content=f"# Error: {origin_result['error']}",
                                                                   origin_name=origin_name)
                return HTMLResponse(content=html_response)
            
            origin_config = origin_result['origin_config']
            origin_name = origin_config['origin_name']
            
            # Generate YAML using the same code path as config.py save operation
            yaml_content = self.backup_config.preview_origin_yaml(origin_name, origin_config)
            
            html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                               preview_content=yaml_content,
                                                               origin_name=origin_name)
            return HTMLResponse(content=html_response)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                               preview_content=f"Error generating preview: {str(e)}\n\nCheck server logs for details.",
                                                               origin_name=get_form_value(form_data, 'origin_name', 'unknown'))
            return HTMLResponse(content=html_response)

# Global handler instance
origins_handler = OriginsHandler()