"""
Destinations Page Handlers
Repository management, destination configuration, and validation
"""

import html
import logging
from typing import Dict, Any, Callable, List
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from config import BackupConfig
from models.forms import safe_get_value, safe_get_list
from dests.services.manage import create_destination_operations_service
from dests.services.rsync import network_discovery_service, rsync_service
from dests.services.restic import restic_service, ResticRepositoryTypeService, ResticRepositoryService, restic_api_service
from dests.schema import DESTINATION_TYPE_SCHEMAS

logger = logging.getLogger(__name__)


# =============================================================================
# DESTINATION FORM PARSER
# =============================================================================

class DestinationsHandler(BaseHandler):
    """Handle destinations management and validation"""
    
    def __init__(self):
        self.backup_config = BackupConfig()
        self._init_template_service()
        
        # Create destination operations service
        self.dest_operations = create_destination_operations_service(self.backup_config)
        
        # Initialize network discovery service
        self.network_discovery = network_discovery_service
    
    # =========================================================================
    # DESTINATION VALIDATION RENDERING
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
        if result.get('success', False):
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
            if result.get('success', False):
                message = result.get('message', 'Validation successful')
            else:
                message = result.get('error', result.get('message', 'Validation failed'))
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
        destinations = self.dest_operations.get_destinations()
        global_settings = self.dest_operations.get_global_settings()
        
        # Build destination display list
        dest_list = []
        for dest_name, dest_config in destinations.items():
            # Determine destination type display from schema
            dest_type = dest_config.get('type', 'Unknown')
            type_display = DESTINATION_TYPE_SCHEMAS.get(dest_type, {}).get('display_name', dest_type)
            
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
    # DESTINATION FIELD RENDERING AND OPERATIONS
    # =============================================================================


    def _render_validation_result(self, status: str, message: str) -> str:
        """Render validation result with consistent styling"""
        
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

    @handle_page_errors("Delete destination")
    def delete_destination(self, dest_name: str) -> JSONResponse:
        """Delete destination"""
        
        # Delegate to service
        result = self.dest_operations.delete_destination(dest_name)
        
        if result['success']:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            status_code = 400 if 'required' in result.get('error', '') else 500
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=status_code)


    def add_destination(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new destination - thin handler delegates to service"""
        result = self.dest_operations.add_destination_from_form(form_data)
        
        if result['success']:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            return JSONResponse(content=result, status_code=400)


    def save_destination(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save destination changes - thin handler delegates to service"""
        dest_name = self._get_form_value(form_data, 'dest_name', '').strip()
        result = self.dest_operations.update_destination_from_form(dest_name, form_data)
        
        if result['success']:
            return RedirectResponse(url='/dests', status_code=302)
        else:
            status_code = 404 if 'not found' in result['error'].lower() else 400
            return JSONResponse(content=result, status_code=status_code)


    def validate_destination(self, form_data: Dict[str, Any]) -> HTMLResponse:
        """Validate destination configuration - thin handler delegates to service"""
        template_context = self.dest_operations.validate_destination_from_form(form_data)
        return self._render_html('partials/destination_validation_result.html', template_context)

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
        
        # Delegate to service
        result = self.network_discovery.scan_network_for_rsyncd(network_range)
        
        if result['success']:
            return JSONResponse(content={
                'network_range': result['network_range'],
                'total_checked': result['total_checked'],
                'found_servers': result['found_servers'],
                'servers': result['servers']
            })
        else:
            status_code = 408 if 'timed out' in result.get('error', '') else 500
            return JSONResponse(content={
                'error': result['error']
            }, status_code=status_code)

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

    @handle_page_errors("Get repository info")
    def get_repository_info(self, job_name: str) -> JSONResponse:
        """Get repository information with proper response formatting"""
        
        # Call service (returns plain data with success/error structure)
        result = restic_api_service.get_repository_info(job_name)
        
        # Service already returns the correct structure, just wrap in JSONResponse
        return JSONResponse(content=result)

    @handle_page_errors("List snapshots")
    def list_snapshots(self, job_name: str) -> JSONResponse:
        result = restic_api_service.list_snapshots(job_name)
        return JSONResponse(content=result)

    @handle_page_errors("Get snapshot stats")
    def get_snapshot_stats(self, job_name: str, snapshot_id: str) -> JSONResponse:
        result = restic_api_service.get_snapshot_stats(job_name, snapshot_id)
        return JSONResponse(content=result)

    @handle_page_errors("Browse directory")
    def browse_directory(self, job_name: str, snapshot_id: str, path: str = '/') -> JSONResponse:
        result = restic_api_service.browse_directory(job_name, snapshot_id, path)
        return JSONResponse(content=result)

    @handle_page_errors("Initialize repository")
    def init_repository(self, job_name: str) -> JSONResponse:
        result = restic_api_service.init_repository(job_name)
        return JSONResponse(content=result)

# Global handler instance
destinations_handler = DestinationsHandler()
