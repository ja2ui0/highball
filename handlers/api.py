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
from jobs.services.backup import backup_service
from jobs.services.notify import create_notification_service

logger = logging.getLogger(__name__)

class APIHandler:
    """Unified handler for all API endpoints and data services"""
    
    def __init__(self, backup_config, template_service=None):
        self.backup_config = backup_config
        self.template_service = template_service
        self.notification_service = create_notification_service(backup_config.get_global_settings())
    
    # =============================================================================
    # EXTERNAL API ENDPOINTS - FOR DASHBOARD WIDGETS & EXTERNAL CONSUMERS ONLY
    # TODO: Review these methods when app core is complete - may need refactoring
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
    # RESTIC REPOSITORY OPERATIONS - MOVED TO dests/services/restic.py
    # =============================================================================
    
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
    
    # =============================================================================
    # NOTIFICATION TESTING - MOVED TO admin/services/notifications.py
    # =============================================================================
    
    # =============================================================================
    # CORS HANDLING
    # =============================================================================
    
    def handle_options(self) -> JSONResponse:
        """Handle CORS preflight requests for API endpoints"""
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )


# ResponseUtils class removed - all CGI patterns eliminated for Python 3.13 compatibility