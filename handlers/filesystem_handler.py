"""
Filesystem handler for backup browser functionality.
Handles filesystem browsing for rsync-compatible destinations (SSH, local, rsyncd).
"""

from urllib.parse import urlparse, parse_qs
from services.filesystem_service import FilesystemService


class FilesystemHandler:
    """Handles filesystem browsing requests"""
    
    def __init__(self, backup_config):
        """Initialize with backup configuration"""
        self.backup_config = backup_config
        self.filesystem_service = FilesystemService()
    
    def browse_filesystem(self, handler):
        """Handle filesystem browse requests"""
        try:
            # Parse query parameters
            url_parts = urlparse(handler.path)
            params = parse_qs(url_parts.query)
            
            job_name = params.get('job', [''])[0]
            path = params.get('path', ['/'])[0]
            
            if not job_name:
                self._send_error_response(handler, 'Job name is required')
                return
            
            # Get job configuration
            jobs = self.backup_config.config.get('backup_jobs', {})
            if job_name not in jobs:
                self._send_error_response(handler, f'Job not found: {job_name}')
                return
            
            job_config = jobs[job_name]
            dest_type = job_config.get('dest_type', '')
            
            # Validate destination type supports filesystem browsing
            if dest_type not in ['ssh', 'local', 'rsyncd']:
                self._send_error_response(handler, f'Job type {dest_type} does not support filesystem browsing')
                return
            
            # Browse the filesystem
            result = self.filesystem_service.browse_directory(job_config, path)
            
            # Send response
            self._send_json_response(handler, result)
            
        except Exception as e:
            self._send_error_response(handler, f'Filesystem browse error: {str(e)}')
    
    def _send_json_response(self, handler, data):
        """Send JSON response"""
        import json
        
        handler.send_response(200)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        
        response = json.dumps(data, indent=2)
        handler.wfile.write(response.encode('utf-8'))
    
    def _send_error_response(self, handler, error_message):
        """Send error response in standard format"""
        error_data = {
            'success': False,
            'error': error_message
        }
        self._send_json_response(handler, error_data)