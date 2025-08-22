"""
Consolidated API Handler
Merges all API and data service handlers into single module
Replaces: api_handler.py, restic_handler.py, filesystem_handler.py, notification_test_handler.py
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# FastAPI imports
from fastapi.responses import JSONResponse

# Import unified models
from models.backup import backup_service
from models.notifications import create_notification_service

logger = logging.getLogger(__name__)

class APIHandler:
    """Unified handler for all API endpoints and data services"""
    
    def __init__(self, backup_config, template_service=None):
        self.backup_config = backup_config
        self.template_service = template_service
        self.notification_service = create_notification_service(backup_config.get_global_settings())
    
    # =============================================================================
    # REST API ENDPOINTS
    # =============================================================================
    
    def get_jobs(self, state_filter: Optional[str] = None, fields_filter: Optional[str] = None) -> JSONResponse:
        """GET /api/highball/jobs - List jobs with optional filtering"""
        try:
            jobs = self.backup_config.get_backup_jobs()
            
            # Get job status information
            from services.management import JobManagementService
            job_management = JobManagementService(self.backup_config)
            
            job_list = []
            for job_name, job_config in jobs.items():
                status_info = job_management.get_status(job_name)
                
                job_data = {
                    'name': job_name,
                    'enabled': job_config.get('enabled', True),
                    'schedule': job_config.get('schedule', 'manual'),
                    'source_type': job_config.get('source_type'),
                    'dest_type': job_config.get('dest_type'),
                    'status': status_info.get('status', 'unknown'),
                    'last_run': status_info.get('last_run'),
                    'last_duration': status_info.get('duration')
                }
                
                # Apply state filter
                if state_filter and job_data['status'] != state_filter:
                    continue
                
                # Apply fields filter
                if fields_filter:
                    requested_fields = [f.strip() for f in fields_filter.split(',')]
                    filtered_job = {}
                    for field in requested_fields:
                        if field in job_data:
                            filtered_job[field] = job_data[field]
                    job_data = filtered_job
                
                job_list.append(job_data)
            
            # Sort by name
            job_list.sort(key=lambda j: j.get('name', ''))
            
            response_data = {
                'jobs': job_list,
                'total': len(job_list),
                'timestamp': datetime.now().isoformat()
            }
            
            return JSONResponse(
                content=response_data,
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                }
            )
            
        except Exception as e:
            logger.error(f"API jobs error: {e}")
            return JSONResponse(
                content={'error': f"API error: {str(e)}", 'timestamp': datetime.now().isoformat()},
                status_code=500
            )
    
    # =============================================================================
    # RESTIC REPOSITORY OPERATIONS
    # =============================================================================
    
    def validate_restic_job(self, job_name: str) -> JSONResponse:
        """Validate Restic repository for a job"""
        try:
            if not job_name:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name is required'
                })
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
            
            job_config = jobs[job_name]
            
            if job_config.get('dest_type') != 'restic':
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job is not configured for Restic'
                })
            
            # Test repository access using unified backup service
            result = backup_service.test_repository(job_config)
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Restic validation error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Validation failed: {str(e)}'
            })
    
    def validate_restic_form(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Validate Restic configuration from form data"""
        try:
            # Parse Restic destination from form
            from models.forms import destination_parser
            restic_result = destination_parser.parse_restic_destination(form_data)
            
            if not restic_result['valid']:
                return JSONResponse(content={
                    'success': False,
                    'error': restic_result['error']
                })
            
            # Test repository access
            result = backup_service.test_repository({'dest_config': restic_result['config']})
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Restic form validation error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Form validation failed: {str(e)}'
            })
    
    def get_repository_info(self, job_name: str) -> JSONResponse:
        """Get Restic repository information"""
        try:
            if not job_name:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name is required'
                })
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
            
            job_config = jobs[job_name]
            
            # Get repository analysis
            dest_config = job_config.get('dest_config', {})
            analysis_result = backup_service.analyze_content(dest_config, job_name)
            
            return JSONResponse(content=analysis_result)
            
        except Exception as e:
            logger.error(f"Repository info error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Repository info failed: {str(e)}'
            })
    
    def check_repository_availability(self, job_name: str) -> JSONResponse:
        """Check if repository is available for browsing (pre-flight check for HTMX)"""
        try:
            if not job_name:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name is required'
                })

            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })

            job_config = jobs[job_name]
            dest_type = job_config.get('dest_type')
            
            if dest_type == 'restic':
                # Use the quick check for restic repositories
                dest_config = job_config.get('dest_config', {})
                repo_uri = dest_config.get('repo_uri')
                
                if repo_uri:
                    check_success, check_message = backup_service.repository_service._quick_repository_check(repo_uri, dest_config)
                    
                    if check_success:
                        return JSONResponse(content={
                            'success': True,
                            'available': True,
                            'job_type': dest_type
                        })
                    else:
                        # Parse for specific error types to enable targeted UI responses
                        error_type = 'unknown'
                        if 'Command returned 11' in check_message and 'locked' in check_message:
                            error_type = 'repository_locked'
                        elif 'Command returned 12' in check_message:
                            error_type = 'wrong_password'
                        elif 'Command returned 10' in check_message:
                            error_type = 'repository_not_found'
                        
                        return JSONResponse(content={
                            'success': True,
                            'available': False,
                            'error_type': error_type,
                            'error_message': check_message,
                            'job_type': dest_type
                        })
                else:
                    return JSONResponse(content={
                        'success': False,
                        'error': 'Repository URI not configured'
                    })
            else:
                # For non-restic jobs (rsync, etc), assume available for now
                # Could add filesystem checks here later
                return JSONResponse(content={
                    'success': True,
                    'available': True,
                    'job_type': dest_type
                })

        except Exception as e:
            logger.error(f"Repository availability check error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Availability check failed: {str(e)}'
            })

    def unlock_repository(self, job_name: str) -> JSONResponse:
        """Unlock a locked restic repository (HTMX endpoint)"""
        try:
            if not job_name:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name is required'
                })

            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })

            job_config = jobs[job_name]
            dest_type = job_config.get('dest_type')
            
            if dest_type != 'restic':
                return JSONResponse(content={
                    'success': False,
                    'error': 'Unlock is only supported for restic repositories'
                })

            # Execute restic unlock command using the same patterns as other operations
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            result = backup_service.unlock_repository(dest_config, source_config)
            
            return JSONResponse(content=result)

        except Exception as e:
            logger.error(f"Repository unlock error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Repository unlock failed: {str(e)}'
            })
    
    def list_snapshots(self, job_name: str) -> JSONResponse:
        """List snapshots for a job"""
        try:
            if not job_name:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name is required'
                })
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            # Pass source_config to backup_service so it can handle SSH execution
            filters = {'job_name': job_name}
            result = backup_service.list_snapshots(dest_config, filters, source_config)
            
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"List snapshots error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Snapshot listing failed: {str(e)}'
            })
    
    def get_snapshot_stats(self, job_name: str, snapshot_id: str) -> JSONResponse:
        """Get statistics for a specific snapshot"""
        try:
            if not job_name or not snapshot_id:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name and snapshot ID are required'
                })
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            # Use unified backup service for snapshot statistics
            result = backup_service.get_snapshot_statistics(dest_config, snapshot_id, source_config)
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Snapshot stats error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Stats retrieval failed: {str(e)}'
            })
    
    def browse_directory(self, job_name: str, snapshot_id: str, path: str = '/') -> JSONResponse:
        """Browse directory contents in a snapshot"""
        try:
            if not job_name or not snapshot_id:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name and snapshot ID are required'
                })
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            # Use unified backup service for directory browsing
            result = backup_service.browse_snapshot_directory(dest_config, snapshot_id, path, source_config)
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Directory browse error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Browse failed: {str(e)}'
            })
    
    def init_repository(self, job_name: str) -> JSONResponse:
        """Initialize Restic repository for a job"""
        try:
            if not job_name:
                return JSONResponse(content={
                    'success': False,
                    'error': 'Job name is required'
                })
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return JSONResponse(content={
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            # Initialize repository using backup service (pass source_config for SSH detection)
            result = backup_service.initialize_repository(dest_config, source_config)
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Repository init error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Repository initialization failed: {str(e)}'
            })
    
    def initialize_restic_repo(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Initialize Restic repository from form data"""
        try:
            # Parse Restic destination from form
            from models.forms import destination_parser
            restic_result = destination_parser.parse_restic_destination(form_data)
            
            if not restic_result['valid']:
                return JSONResponse(content={
                    'success': False,
                    'error': restic_result['error']
                })
            
            # Initialize repository
            result = backup_service.initialize_repository(restic_result['config'])
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Form repository init error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Repository initialization failed: {str(e)}'
            })
    
    # =============================================================================
    # FILESYSTEM OPERATIONS
    # =============================================================================
    
    def browse_filesystem(self, path: str = '/') -> JSONResponse:
        """Browse local filesystem for path selection"""
        try:
            try:
                path_obj = Path(path)
                if not path_obj.exists():
                    return JSONResponse(content={
                        'success': False,
                        'error': f'Path does not exist: {path}'
                    })
                
                if not path_obj.is_dir():
                    return JSONResponse(content={
                        'success': False,
                        'error': f'Path is not a directory: {path}'
                    })
                
                # List directory contents
                entries = []
                try:
                    for item in path_obj.iterdir():
                        if item.is_dir():
                            entries.append({
                                'name': item.name,
                                'path': str(item),
                                'type': 'directory'
                            })
                        elif item.is_file():
                            entries.append({
                                'name': item.name,
                                'path': str(item),
                                'type': 'file',
                                'size': item.stat().st_size
                            })
                    
                    # Sort: directories first, then files
                    entries.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))
                    
                except PermissionError:
                    return JSONResponse(content={
                        'success': False,
                        'error': f'Permission denied: {path}'
                    })
                
                return JSONResponse(content={
                    'success': True,
                    'path': str(path_obj),
                    'parent': str(path_obj.parent) if path_obj.parent != path_obj else None,
                    'entries': entries
                })
                
            except Exception as e:
                return JSONResponse(content={
                    'success': False,
                    'error': f'Filesystem error: {str(e)}'
                })
            
        except Exception as e:
            logger.error(f"Filesystem browse error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Browse failed: {str(e)}'
            })
    
    # =============================================================================
    # NOTIFICATION TESTING
    # =============================================================================
    
    def test_telegram_notification(self, test_message: str = 'Test notification from Highball') -> JSONResponse:
        """Test Telegram notification"""
        try:
            result = self.notification_service.test_provider('telegram')
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Telegram test error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Telegram test failed: {str(e)}'
            })
    
    def test_email_notification(self, test_message: str = 'Test notification from Highball') -> JSONResponse:
        """Test email notification"""
        try:
            result = self.notification_service.test_provider('email')
            return JSONResponse(content=result)
            
        except Exception as e:
            logger.error(f"Email test error: {e}")
            return JSONResponse(content={
                'success': False,
                'error': f'Email test failed: {str(e)}'
            })
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    # All API methods now return JSONResponse directly - no utility methods needed


class ResponseUtils:
    """Shared HTTP response utilities for all handlers"""
    
    def __init__(self, template_service):
        self.template_service = template_service
    
    def send_html_response(self, request_handler, html: str):
        """Send HTML response"""
        request_handler.send_response(200)
        request_handler.send_header('Content-type', 'text/html')
        request_handler.end_headers()
        request_handler.wfile.write(html.encode())
    
    def send_json_response(self, request_handler, data: Dict[str, Any], cors: bool = False):
        """Send JSON response"""
        request_handler.send_response(200)
        request_handler.send_header('Content-type', 'application/json')
        if cors:
            request_handler.send_header('Access-Control-Allow-Origin', '*')
            request_handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            request_handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        request_handler.end_headers()
        request_handler.wfile.write(json.dumps(data).encode())
    
    def send_redirect(self, request_handler, location: str):
        """Send redirect response"""
        request_handler.send_response(302)
        request_handler.send_header('Location', location)
        request_handler.end_headers()
    
    def send_htmx_partial(self, request_handler, template_path: str, data: Dict[str, Any]):
        """Send HTMX partial template response"""
        html = self.template_service.render_template(template_path, **data)
        self.send_html_response(request_handler, html)
    
    def send_error(self, request_handler, message: str, status_code: int = 500):
        """Send error response using template partial"""
        request_handler.send_response(status_code)
        request_handler.send_header('Content-type', 'text/html')
        request_handler.end_headers()
        
        error_html = self.template_service.render_template('partials/error_message.html', {
            'error_message': message
        })
        request_handler.wfile.write(error_html.encode())
    
    def send_htmx_error(self, request_handler, message: str):
        """Send HTMX error response"""
        error_html = self.template_service.render_template('partials/error_message.html', 
            error_message=message
        )
        request_handler.send_response(400)
        request_handler.send_header('Content-type', 'text/html')
        request_handler.end_headers()
        request_handler.wfile.write(error_html.encode())