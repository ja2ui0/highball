"""
HTMX Validation Renderer Service
Handles rendering of validation status HTML fragments for HTMX responses
"""

import logging

logger = logging.getLogger(__name__)

class HTMXValidationRenderer:
    """Renders validation status HTML fragments for HTMX responses"""
    
    def render_success(self, message, details=None):
        """Render success validation status with enhanced details"""
        details_html = ""
        if details:
            detail_items = []
            
            # Handle specific detail types for better formatting
            if 'ssh_status' in details:
                detail_items.append(f"SSH: {details['ssh_status']}")
            if 'rsync_status' in details:
                detail_items.append(f"Rsync: {details['rsync_status']}")
            if 'container_runtime' in details:
                detail_items.append(f"Container: {details['container_runtime']}")
            if 'path_status' in details:
                detail_items.append(f"Path: {details['path_status']}")
            if 'repository_status' in details:
                detail_items.append(f"Repository: {details['repository_status']}")
            if 'snapshot_count' in details:
                detail_items.append(f"Snapshots: {details['snapshot_count']}")
            if 'latest_backup' in details:
                detail_items.append(f"Latest: {details['latest_backup']}")
            if 'tested_from' in details:
                detail_items.append(f"Tested from: {details['tested_from']}")
            if 'repo_uri' in details:
                detail_items.append(f"URI: {details['repo_uri']}")
            
            # Handle generic details for unknown keys
            for key, value in details.items():
                if key not in ['ssh_status', 'rsync_status', 'container_runtime', 'path_status', 
                              'repository_status', 'snapshot_count', 'latest_backup', 'tested_from', 'repo_uri'] and value:
                    detail_items.append(f"{key}: {value}")
            
            if detail_items:
                details_html = f'<div class="validation-details">{"<br>".join(detail_items)}</div>'
        
        return f'''
        <div class="validation-success">
            <span class="validation-status">[OK] {message}</span>
            {details_html}
        </div>
        '''
    
    def render_error(self, error_message, details=None):
        """Render error validation status with enhanced details"""
        details_html = ""
        if details:
            detail_items = []
            for key, value in details.items():
                if value:
                    detail_items.append(f"{key}: {value}")
            if detail_items:
                details_html = f'<div class="validation-details">{"<br>".join(detail_items)}</div>'
        
        return f'''
        <div class="validation-error">
            <span class="validation-status">[ERROR] {error_message}</span>
            {details_html}
        </div>
        '''
    
    def render_warning(self, warning_message, details=None):
        """Render warning validation status with enhanced details"""
        details_html = ""
        if details:
            detail_items = []
            for key, value in details.items():
                if value:
                    detail_items.append(f"{key}: {value}")
            if detail_items:
                details_html = f'<div class="validation-details">{"<br>".join(detail_items)}</div>'
        
        return f'''
        <div class="validation-warning">
            <span class="validation-status">[WARN] {warning_message}</span>
            {details_html}
        </div>
        '''
    
    def render_progress(self, message):
        """Render progress/loading validation status"""
        return f'''
        <span class="status-progress">{message}</span>
        '''