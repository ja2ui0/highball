"""
Origins Page Handlers
SSH host management, origin configuration, and capability validation
"""

import logging
from functools import wraps
from typing import Dict, Any, Callable
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from dataclasses import dataclass
import asyncio

from shared.handlers.templating import TemplateService
from config import BackupConfig
from models.forms import safe_get_value
from origins.services.manage import OriginOperationsService
from origins.services.ssh import OriginSSHService

logger = logging.getLogger(__name__)


# =============================================================================
# ORIGIN FORM PARSER
# =============================================================================

class OriginParser:
    """Parse SSH origin configurations"""
    
    @staticmethod
    def parse_origin_form(form_data: Dict[str, Any], require_password: bool = True) -> Dict[str, Any]:
        """Parse SSH origin form data"""
        origin_name = safe_get_value(form_data, 'origin_name').strip()
        if not origin_name:
            return {'valid': False, 'error': 'Origin name is required'}
        
        # Validate origin name is a valid slug (matches filename requirements)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', origin_name):
            return {'valid': False, 'error': 'Origin name must contain only letters, numbers, underscores, and hyphens'}
        
        friendly_name = safe_get_value(form_data, 'friendly_name').strip()
        if not friendly_name:
            return {'valid': False, 'error': 'Friendly name is required'}
        
        ssh_hostname = safe_get_value(form_data, 'ssh_hostname').strip()
        if not ssh_hostname:
            return {'valid': False, 'error': 'SSH hostname is required'}
        
        ssh_username = safe_get_value(form_data, 'ssh_username').strip()
        if not ssh_username:
            return {'valid': False, 'error': 'SSH username is required'}
        
        # Parse authentication method
        ssh_highball = safe_get_value(form_data, 'ssh_highball') == 'on'
        
        # Parse optional fields with defaults
        ssh_port = safe_get_value(form_data, 'ssh_port', '22')
        ssh_timeout = safe_get_value(form_data, 'ssh_timeout', '5')
        
        try:
            ssh_port = int(ssh_port)
            ssh_timeout = int(ssh_timeout)
        except ValueError:
            return {'valid': False, 'error': 'SSH port and timeout must be numbers'}
        
        # Note: Auth validation removed - no BYOK fields to validate anymore
        
        # Build origin configuration
        # Parse detected capabilities from validation (if present)
        detected_rsync = safe_get_value(form_data, 'detected_rsync_available', 'false')
        detected_runtime = safe_get_value(form_data, 'detected_container_runtime', '')
        
        
        origin_config = {
            'origin_name': origin_name,
            'friendly_name': friendly_name,
            'ssh_hostname': ssh_hostname,
            'ssh_port': ssh_port,
            'ssh_timeout': ssh_timeout,
            'ssh_username': ssh_username,
            'ssh_highball': True,  # Always true - Highball-only system
            'rsync_available': detected_rsync.lower() == 'true',
            'container_runtime': detected_runtime if detected_runtime else None
        }
        
        # Add authentication-specific fields
        if ssh_highball:
            # Highball key mode - password only required for validation, not for save operations
            ssh_password = safe_get_value(form_data, 'ssh_password')
            if require_password and not ssh_password:
                return {'valid': False, 'error': 'SSH password is required for Highball key installation'}
            if ssh_password:
                origin_config['ssh_password'] = ssh_password  # Transient
        # Note: When ssh_highball is False, user has existing keys and no additional input is required
        
        return {'valid': True, 'origin_config': origin_config}


# Create parser instance for easy access
origin_parser = OriginParser()

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
        self.origin_service = OriginOperationsService(self.backup_config)
        self.ssh_service = OriginSSHService()
    
    # =========================================================================
    # SSH SOURCE VALIDATION RENDERING - moved to origins.services.ssh
    # =========================================================================
    
    # =========================================================================
    # PAGE HANDLERS
    # =========================================================================
    
    @handle_page_errors("Show SSH origins")
    def show_ssh_origins(self) -> HTMLResponse:
        """Show SSH origins management page"""
        origins = self.origin_service.get_origins()
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
        origin_config = self.origin_service.get_origin(origin_name)
        
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

    async def add_ssh_origin_htmx(self, request) -> JSONResponse:
        """Add SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.add_ssh_origin(form_data)

    @handle_page_errors("Add SSH origin")
    def add_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new SSH origin"""
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
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
        
        # Delegate business logic to origin service
        result = self.origin_service.save_origin_with_rename_handling(origin_name, origin_config, original_origin_name)
        
        if result['success']:
            return RedirectResponse(url='/origins', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    def _get_form_value(self, form_data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Helper to get form value with default"""
        return form_data.get(key, default)

    @handle_page_errors("SSH source validation")
    def validate_ssh_source(self, source: str) -> JSONResponse:
        """Validate SSH source configuration"""
        result = self.ssh_service.validate_origin_string(source)
        return JSONResponse(content=result)

    @handle_page_errors("SSH origin validation")
    def validate_ssh_origin(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Push keys and validate SSH origin configuration with persistent session tracking"""
        # Parse origin form data (no password required for save operations)
        origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
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
    
    @handle_page_errors("SSH progress polling")
    def get_ssh_progress(self, session_id: str) -> HTMLResponse:
        """Get current SSH validation progress for a session using persistent storage"""
        # Get session progress from service
        session_data = self.ssh_service.read_session_progress(session_id)
        
        if not session_data['exists']:
            return self._render_html('partials/ssh_validation_expired.html', {
                'success': False,
                'validation_message': "Session not found or expired"
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
            # DISABLE session cleanup - known HTMX polling issue
            # Sessions accumulate but validation completes without console spam
            pass
            return self._render_html('partials/ssh_validation_result.html', result)
    
    @handle_page_errors("SSH progress streaming")
    async def stream_ssh_progress(self, session_id: str, request: Request) -> StreamingResponse:
        """Stream SSH validation progress using Server-Sent Events"""
        import time
        
        async def event_generator():
            last_progress_count = 0
            max_wait_time = 60  # Maximum wait time in seconds
            start_time = time.time()
            
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                    
                # Check for timeout
                if time.time() - start_time > max_wait_time:
                    error_result = {
                        'success': False, 
                        'validation_message': 'Validation timeout. Please try again.',
                        'edit_mode': False
                    }
                    inner_error_html = self.template_service.render_template('partials/ssh_validation_result.html', **error_result)
                    final_html = self.template_service.render_template('partials/ssh_validation_final_result.html', 
                                                                     result_html=inner_error_html)
                    # Remove newlines and extra whitespace from HTML for SSE
                    final_html = ' '.join(final_html.split())
                    yield f"event: error\ndata: {final_html}\n\n"
                    break
                
                # Get session progress from service
                session_data = self.ssh_service.read_session_progress(session_id)
                
                # Wait for session to be created (don't immediately error)
                if not session_data['exists']:
                    await asyncio.sleep(0.5)
                    continue
                
                # Send new progress messages  
                current_progress = session_data['progress']
                if len(current_progress) > last_progress_count:
                    progress_content = "<br>".join(current_progress)
                    progress_html = self.template_service.render_template('partials/ssh_validation_progress_update.html', 
                                                                       progress_content=progress_content)
                    progress_html = ' '.join(progress_html.split())
                    yield f"event: progress\ndata: {progress_html}\n\n"
                    last_progress_count = len(current_progress)
                
                # Check if completed
                if session_data['completed']:
                    result = session_data['result']
                    result['edit_mode'] = session_data['edit_mode']
                    
                    # Render the final result template
                    inner_result_html = self.template_service.render_template('partials/ssh_validation_result.html', **result)
                    final_html = self.template_service.render_template('partials/ssh_validation_final_result.html', 
                                                                     result_html=inner_result_html)
                    # Remove newlines and extra whitespace from HTML for SSE
                    final_html = ' '.join(final_html.split())
                    event_type = "success" if result['success'] else "error"
                    yield f"event: {event_type}\ndata: {final_html}\n\n"
                    
                    # Clean up session after successful completion
                    self.ssh_service.cleanup_session(session_id)
                    break
                
                await asyncio.sleep(0.5)  # Poll every 500ms
        
        return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        })
    
    
    
    @handle_page_errors("Toggle SSH auth method")
    def toggle_ssh_auth_method(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Toggle between Highball and user SSH authentication methods"""
        ssh_highball = 'ssh_highball' in form_data
        template_data = self.ssh_service.get_auth_method_template_data(ssh_highball)
        return self._render_html(template_data['template'], template_data['context'])
    

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
            # origin_parser is now local to this module
            
            origin_result = origin_parser.parse_origin_form(form_data, require_password=False)
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
            import traceback
            traceback.print_exc()
            html_response = self.template_service.render_template('partials/ssh_config_preview.html',
                                                               preview_content=f"Error generating preview: {str(e)}\n\nCheck server logs for details.",
                                                               origin_name=get_form_value(form_data, 'origin_name', 'unknown'))
            return HTMLResponse(content=html_response)

# Global handler instance
origins_handler = OriginsHandler()