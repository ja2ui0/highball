"""
Destinations Views (GET handlers)
Handle destination listing, repository browsing, and read-only operations
"""

import html
import logging
from typing import Dict, Any, Callable, List
from fastapi.responses import HTMLResponse, JSONResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from shared.services.config import ConfigReader
from dests.services.config import DestConfigService
from dests.services.rsync import network_discovery_service
from dests.services.restic import restic_api_service
from dests.schema import DESTINATION_TYPE_SCHEMAS

logger = logging.getLogger(__name__)


class DestinationsViews(BaseHandler):
    """Handle destinations GET operations - read-only views"""
    
    def __init__(self):
        self._init_template_service()

        # Services handle all config access - handlers delegate everything
        self.dest_config = DestConfigService()
        self.config_reader = ConfigReader()
        self.network_discovery = network_discovery_service
    
    # =========================================================================
    # DESTINATION VALIDATION RENDERING - presentation logic stays in handlers
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
    
    # =========================================================================
    # GET HANDLERS - read-only operations
    # =========================================================================
    
    @handle_page_errors("Show destinations")
    def show_destinations(self) -> HTMLResponse:
        """Show destinations management page"""
        destinations = self.config_reader.get_destinations()
        # TODO: Remove global_settings dependency or handle differently
        global_settings = {}
        
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

    # REMOVED: _check_and_respond_repository_status_html - cross-domain violation
    # This method accessed jobs domain data and should be moved to jobs handlers

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


# Global handler instance
destinations_views = DestinationsViews()