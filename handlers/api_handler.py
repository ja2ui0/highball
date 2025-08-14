"""
API handler for providing REST endpoints for external dashboard widgets
"""

import json
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Any, Optional
from .job_manager import JobManager


class ApiHandler:
    """Handles REST API requests for external integrations"""
    
    def __init__(self, backup_config):
        """Initialize with backup configuration"""
        self.backup_config = backup_config
        self.job_manager = JobManager(backup_config)
    
    def get_jobs(self, handler):
        """GET /api/highball/jobs - Return job data with optional filtering"""
        try:
            # Future: Add authentication check here
            # if not self._authenticate(handler):
            #     return self._send_error_response(handler, 'Unauthorized', 401)
            
            # Parse query parameters
            url_parts = urlparse(handler.path)
            params = parse_qs(url_parts.query)
            
            # Extract parameters
            state_filter = params.get('state', [None])[0]  # active, inactive, all
            fields_param = params.get('fields', [None])[0]  # comma-separated field list
            format_param = params.get('format', ['json'])[0]  # json (future: csv, etc.)
            
            # Parse fields filter
            requested_fields = None
            if fields_param:
                requested_fields = set(field.strip() for field in fields_param.split(','))
            
            # Get job data
            jobs_data = self._get_jobs_data(state_filter, requested_fields)
            
            # Send JSON response
            self._send_json_response(handler, {
                'success': True,
                'data': jobs_data,
                'count': len(jobs_data),
                'api_version': '1.0'
            })
            
        except Exception as e:
            self._send_error_response(handler, f'API error: {str(e)}')
    
    def _get_jobs_data(self, state_filter: Optional[str], requested_fields: Optional[set]) -> List[Dict[str, Any]]:
        """Get job data with filtering"""
        # Get job configurations
        jobs = self.backup_config.config.get('backup_jobs', {})
        
        # Get job status logs
        logs = self.job_manager.get_job_logs()
        
        result = []
        
        for job_name, job_config in jobs.items():
            # Apply state filter
            if state_filter:
                job_enabled = job_config.get('enabled', True)
                if state_filter == 'active' and not job_enabled:
                    continue
                elif state_filter == 'inactive' and job_enabled:
                    continue
                # 'all' or None includes everything
            
            # Get job status information
            job_log = logs.get(job_name, {})
            
            # Build full job data
            job_data = {
                'id': job_name,
                'name': job_name,
                'enabled': job_config.get('enabled', True),
                'source_type': job_config.get('source_type', ''),
                'dest_type': job_config.get('dest_type', ''),
                'schedule': job_config.get('schedule', ''),
                'last_status': job_log.get('status', 'never_run'),
                'last_run': job_log.get('last_run'),
                'last_run_ended_at': job_log.get('last_run'),  # Same as last_run for now
                'last_failed_at': job_log.get('last_run') if job_log.get('status') in ['error', 'failed'] else None,
                'last_message': job_log.get('message', ''),
                'source_config': job_config.get('source_config', {}),
                'dest_config': job_config.get('dest_config', {}),
                'respect_conflicts': job_config.get('respect_conflicts', True)
            }
            
            # Apply field filtering if requested
            if requested_fields:
                filtered_data = {}
                for field in requested_fields:
                    if field in job_data:
                        filtered_data[field] = job_data[field]
                    else:
                        # Handle unknown fields gracefully
                        filtered_data[field] = None
                job_data = filtered_data
            
            result.append(job_data)
        
        # Sort by job name for consistent output
        result.sort(key=lambda x: x.get('name', x.get('id', '')))
        
        return result
    
    def _authenticate(self, handler) -> bool:
        """Future: Check authentication (bearer token, API key, etc.)"""
        # Example implementation for future use:
        # auth_header = handler.headers.get('Authorization', '')
        # if not auth_header.startswith('Bearer '):
        #     return False
        # token = auth_header[7:]  # Remove 'Bearer ' prefix
        # return self._validate_token(token)
        return True  # No authentication required for now
    
    def _send_json_response(self, handler, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response"""
        handler.send_response(status_code)
        handler.send_header('Content-type', 'application/json')
        handler.send_header('Access-Control-Allow-Origin', '*')  # Allow CORS for dashboard widgets
        handler.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')  # Ready for auth headers
        handler.end_headers()
        
        response = json.dumps(data, indent=2, default=str)  # default=str handles datetime objects
        handler.wfile.write(response.encode('utf-8'))
    
    def _send_error_response(self, handler, error_message: str, status_code: int = 400):
        """Send error response in standard format"""
        error_data = {
            'success': False,
            'error': error_message,
            'api_version': '1.0'
        }
        self._send_json_response(handler, error_data, status_code)
    
    def handle_options(self, handler):
        """Handle CORS preflight requests"""
        handler.send_response(200)
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')  # Ready for auth headers
        handler.end_headers()