"""
Forms Handler - Pure HTTP coordination for HTMX operations
Delegates all business logic to appropriate services
"""

import html
import logging
import time
from typing import Dict, Any, Optional
from urllib.parse import parse_qs
from fastapi.responses import JSONResponse, RedirectResponse
from jobs.services.validate import ValidationService
from models.forms import JobFormParser, DestinationParser
from services.template import TemplateService

logger = logging.getLogger(__name__)

class FormsHandler:
    """Pure HTTP coordination for HTMX form operations"""
    
    def __init__(self, backup_config, template_service):
        # HTTP coordination only - no business logic state
        self.backup_config = backup_config
        self.validation_service = ValidationService(backup_config)
        self.form_parser = JobFormParser()
        self.template_service = template_service
        self.configured_providers = []  # Track configured notification providers
    
    def handle_htmx_request(self, request: Any, action: str, form_data: Dict[str, Any]) -> str:
        """Single HTMX entry point with action dispatch"""
        # Form data is now always pre-parsed by FastAPI route
        
        # Action dispatch table
        actions = {
            # Validation actions
            
            # Field rendering actions
            
            # Source path management
            
            # Notification management
            
            # Repository management
            
            # Restore actions
            'restore-target-change': self._handle_restore_target_change,
            'restore-dry-run-change': self._handle_restore_dry_run_change,
            
            # Form field rendering (connect to existing implementations)
            'maintenance-toggle': self._render_maintenance_fields,
            'restic-repo-fields': self._render_restic_repo_fields,
            
            # URI preview
            'restic-uri-preview': self._generate_restic_uri_preview,
        }
        
        handler_func = actions.get(action)
        if not handler_func:
            return self._send_error(f"Unknown action: {action}")
        
        try:
            html_response = handler_func(form_data)
            return self._send_htmx_response(html_response)
        except Exception as e:
            logger.error(f"HTMX action {action} failed: {e}")
            return self._send_error(f"Action failed: {str(e)}")
    
    # =============================================================================
    # VALIDATION ACTIONS - Direct validator calls, no coordinators
    # =============================================================================
    
    def _handle_restore_target_change(self, form_data):
        """HTTP coordination: handle restore target change and check overwrites"""
        # HTTP concern: extract parameters
        job_name = self._get_form_value(form_data, 'job_name')
        restore_target = self._get_form_value(form_data, 'restore_target', 'highball')
        dry_run = self._get_form_value(form_data, 'dry_run') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: check for overwrites using restore service
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.validation_service.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths
        )
        
        # Template concern: use template service to render partial
        template_vars = {
            'HAS_OVERWRITES': 'true' if has_overwrites else 'false',
            'RESTORE_TARGET': restore_target,
            'DRY_RUN': 'true' if dry_run else 'false',
            'TARGET_TEXT': "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        }
        
        return self.template_service.render_template('partials/restore_overwrite_warning.html', **template_vars)
    
    def _handle_restore_dry_run_change(self, form_data):
        """HTTP coordination: handle dry run toggle and update warning"""
        # HTTP concern: extract parameters  
        job_name = self._get_form_value(form_data, 'job_name')
        restore_target = self._get_form_value(form_data, 'restore_target', 'highball')
        dry_run = self._get_form_value(form_data, 'dry_run') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: check for overwrites using restore service
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.validation_service.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths
        )
        
        # Template concern: pass data to Jinja2 template for conditional rendering
        target_text = "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        return self.template_service.render_template('partials/restore_overwrite_warning.html', 
                                                    has_overwrites=has_overwrites,
                                                    target_text=target_text,
                                                    dry_run=dry_run)
    
    
    # =============================================================================
    # FIELD RENDERING ACTIONS - Inline HTML, no renderer services
    # =============================================================================
    
    # =============================================================================
    # SOURCE PATH MANAGEMENT - Direct array manipulation
    # =============================================================================
    
    # =============================================================================
    # NOTIFICATION MANAGEMENT - Simplified provider handling
    # =============================================================================
    
    # =============================================================================
    # REPOSITORY MANAGEMENT - Direct operations
    # =============================================================================
    
    
    # =============================================================================
    # UTILITY METHODS - Inline rendering helpers
    # =============================================================================
    
    def _render_validation_result(self, status, message):
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
    
    def _render_notification_provider(self, config, index, provider_id=None):
        """Render a single notification provider configuration"""
        import html
        provider_name = config.get('provider', '')
        display_name = provider_name.capitalize()
        
        if not provider_id:
            provider_id = f"notification_{provider_name}_{index}"
        
        notify_on_success = config.get('notify_on_success', False)
        success_message = html.escape(config.get('success_message', ''))
        
        notify_on_failure = config.get('notify_on_failure', False)
        failure_message = html.escape(config.get('failure_message', ''))
        
        notify_on_maintenance_failure = config.get('notify_on_maintenance_failure', False)
        
        return self.template_service.render_template('partials/notification_provider_config.html',
                                                   provider_id=provider_id,
                                                   provider_name=provider_name,
                                                   display_name=display_name,
                                                   notify_on_success=notify_on_success,
                                                   success_message=success_message,
                                                   notify_on_failure=notify_on_failure,
                                                   failure_message=failure_message,
                                                   notify_on_maintenance_failure=notify_on_maintenance_failure)
    
    def _get_enabled_global_providers(self):
        """Get list of globally enabled notification providers"""
        global_settings = self.backup_config.get_global_settings()
        notification_config = global_settings.get('notification', {})
        
        enabled_providers = []
        for provider, config in notification_config.items():
            if isinstance(config, dict) and config.get('enabled', False):
                enabled_providers.append(provider)
        
        return enabled_providers
    
    def _get_form_providers(self, form_data):
        """Get currently configured providers from form data"""
        providers = form_data.get('notification_providers[]', [])
        # Handle both single string and list formats
        if isinstance(providers, str):
            return [providers] if providers else []
        return [p for p in providers if p]  # Filter out empty strings
    
    def _render_provider_selection(self, available_providers):
        """Render provider selection dropdown"""
        # Filter out configured providers
        available_options = [p for p in available_providers if p not in self.configured_providers]
        
        return self.template_service.render_template('partials/provider_selection_dropdown.html',
                                                   available_options=available_options)
    
    # _parse_form_data method removed - FastAPI now handles form parsing
    
    def _get_form_value(self, form_data, key, default=''):
        """HTTP concern: extract single value from form data"""
        value_list = form_data.get(key, [default])
        return value_list[0] if value_list else default
    
    def _send_htmx_response(self, html):
        """Send HTMX HTML response"""
        return html
    
    def _send_error(self, message):
        """Send error response"""
        import html
        return self.template_service.render_template('partials/error_message.html',
                                                   message=html.escape(message))
    
    def _render_error(self, message):
        """Render error message"""
        import html
        return self.template_service.render_template('partials/error_message.html',
                                                   message=html.escape(message))
    
    # =============================================================================
    # MISSING ENDPOINT IMPLEMENTATIONS - Connect to existing functionality
    # =============================================================================
    
    
    def _render_restic_repo_fields(self, form_data):
        """Render Restic repository type fields using schema-driven templates"""
        # Check both job form field name (restic_repo_type) and destination form field name (repo_type)
        repo_type = self._get_form_value(form_data, 'restic_repo_type') or self._get_form_value(form_data, 'repo_type')
        
        if not repo_type:
            return ''  # No fields for unselected type
            
        from dests.schema import RESTIC_REPOSITORY_TYPE_SCHEMAS
        
        return self.template_service.render_template('partials/restic_repo_fields_dynamic.html',
                                                   repo_type=repo_type,
                                                   repo_schemas=RESTIC_REPOSITORY_TYPE_SCHEMAS)
    
    
    
    def _generate_restic_uri_preview(self, form_data):
        """Generate real-time URI preview for repository configuration"""
        # Check both job form field name (restic_repo_type) and destination form field name (repo_type)
        repo_type = self._get_form_value(form_data, 'restic_repo_type') or self._get_form_value(form_data, 'repo_type')
        
        if not repo_type:
            return self.template_service.render_template('partials/uri_preview.html',
                                                       uri='Select repository type to see URI preview')
        
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
            
            return self.template_service.render_template('partials/uri_preview.html', uri=uri)
        else:
            return self.template_service.render_template('partials/uri_preview.html',
                                                       uri=uri_result.get('error', 'Invalid configuration'))
    


# =============================================================================
# **DESTINATION VALIDATION HANDLER** - Moved from pages.py ValidationHandlers
# =============================================================================

class DestinationValidationHandler:
    """Handler for destination validation - form parsing and connectivity testing"""
    
    def __init__(self):
        # No dependencies needed - methods are self-contained
        pass
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Get form field value with default"""
        value = form_data.get(field_name, default)
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)
    
    def validate_rsync_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rsync (SSH) destination"""
        hostname = self._get_form_value(form_data, 'hostname', '')
        username = self._get_form_value(form_data, 'username', '')
        path = self._get_form_value(form_data, 'path', '')
        port = self._get_form_value(form_data, 'port', '22')
        
        if not all([hostname, username, path]):
            return {
                'success': False,
                'validation_message': 'Hostname, username, and path are required for rsync validation'
            }
        
        # Test SSH connectivity (reuse existing SSH validation)
        ssh_config = {
            'hostname': hostname,
            'username': username,
            'port': int(port) if port.isdigit() else 22
        }
        
        from jobs.services.validate import ValidationService
        validation_service = ValidationService()
        result = validation_service.validate_ssh_source(ssh_config)
        
        if result['valid']:
            return {
                'success': True,
                'validation_message': f"SSH connection successful to {hostname}. Path writability not tested."
            }
        else:
            return {
                'success': False,
                'validation_message': f"SSH connection failed: {result.get('error', 'Unknown error')}"
            }
    
    def validate_rsyncd_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rsyncd destination"""
        hostname = self._get_form_value(form_data, 'hostname', '')
        share = self._get_form_value(form_data, 'share', '')
        port = self._get_form_value(form_data, 'port', '873')
        
        if not all([hostname, share]):
            return {
                'success': False,
                'validation_message': 'Hostname and share are required for rsyncd validation'
            }
        
        # Test rsyncd connectivity
        import subprocess
        try:
            port_num = int(port) if port.isdigit() else 873
            cmd = ['rsync', '--list-only', f'rsync://{hostname}:{port_num}/{share}']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'validation_message': f"Rsyncd connection successful to {hostname}:{port_num}/{share}"
                }
            else:
                return {
                    'success': False,
                    'validation_message': f"Rsyncd connection failed: {result.stderr.strip() or 'Connection error'}"
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'validation_message': 'Rsyncd connection timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'validation_message': f'Rsyncd validation error: {str(e)}'
            }
    
    def validate_restic_destination(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate restic destination"""
        repo_type = self._get_form_value(form_data, 'repo_type', '')
        password = self._get_form_value(form_data, 'restic_password', '')
        
        if not repo_type:
            return {
                'success': False,
                'validation_message': 'Repository type is required for restic validation'
            }
        
        if not password:
            return {
                'success': False,
                'validation_message': 'Repository password is required for restic validation'
            }
        
        # For now, just validate that we can build the URI
        # Full restic validation would require container execution
        from models.forms import DestinationParser
        uri_result = DestinationParser._build_restic_uri(repo_type, form_data)
        
        if uri_result['valid']:
            return {
                'success': True,
                'validation_message': f"Restic repository URI generated successfully. Full connectivity test requires repository initialization."
            }
        else:
            return {
                'success': False,
                'validation_message': f"Restic repository configuration error: {uri_result.get('error', 'Unknown error')}"
            }


# =============================================================================
# **FORM PROCESSING HANDLER** - Moved from pages.py POSTHandlers  
# =============================================================================

class FormProcessingHandler:
    """Handler for form data processing - parsing, building configs, saving"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Get form field value with default"""
        value = form_data.get(field_name, default)
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)
    
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
            flat_data.update({
                'share': dest_config['rsyncd'].get('share'),
                'username': dest_config['rsyncd'].get('username', ''),
                'password': dest_config['rsyncd'].get('password', '')
            })
        elif dest_type == 'restic' and 'restic' in dest_config:
            flat_data.update({
                'repo_type': dest_config['restic'].get('type'),
                'password': dest_config['restic'].get('password')
            })
        
        return flat_data
    
    def _build_destination_uri(self, dest_config):
        """Build destination URI from config"""
        dest_type = dest_config.get('type', self._get_form_value(dest_config, 'dest_type', ''))
        hostname = dest_config.get('hostname', '')
        port = dest_config.get('port', '')
        
        if dest_type == 'rsync':
            username = dest_config.get('username', '')
            path = dest_config.get('path', '')
            port_str = f":{port}" if port and port != "22" else ""
            return f"rsync://{username}@{hostname}{port_str}{path}"
        elif dest_type == 'rsyncd':
            share = dest_config.get('share', '')
            port_str = f":{port}" if port and port != "873" else ""
            return f"rsync://{hostname}{port_str}/{share}"
        elif dest_type == 'restic':
            repo_type = dest_config.get('repo_type', '')
            if repo_type == 'rest':
                port_str = f":{port}" if port and port != "80" and port != "443" else ""
                return f"rest:http://{hostname}{port_str}/"
        
        return f"{dest_type}://{hostname}"
    
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
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to save destination '{dest_name}'"
            }, status_code=500)