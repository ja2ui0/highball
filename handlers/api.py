"""
Consolidated API Handler
Merges all API and data service handlers into single module
Replaces: api_handler.py, restic_handler.py, filesystem_handler.py, notification_test_handler.py
"""

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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
    
    def get_jobs(self, request_handler):
        """GET /api/highball/jobs - List jobs with optional filtering"""
        try:
            # Parse query parameters
            url_parts = urlparse(request_handler.path)
            params = parse_qs(url_parts.query)
            
            # Get filter parameters
            state_filter = params.get('state', [None])[0]
            fields_filter = params.get('fields', [None])[0]
            
            jobs = self.backup_config.get_jobs()
            
            # Get job status information
            from services.job_logger import JobLogger
            job_logger = JobLogger()
            
            job_list = []
            for job_name, job_config in jobs.items():
                status_info = job_logger.get_job_status(job_name)
                
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
            
            self._send_json_response(request_handler, response_data, cors=True)
            
        except Exception as e:
            logger.error(f"API jobs error: {e}")
            self._send_api_error(request_handler, f"API error: {str(e)}")
    
    # =============================================================================
    # RESTIC REPOSITORY OPERATIONS
    # =============================================================================
    
    def validate_restic_job(self, request_handler, job_name: str):
        """Validate Restic repository for a job"""
        try:
            if not job_name:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job name is required'
                })
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
                return
            
            job_config = jobs[job_name]
            
            if job_config.get('dest_type') != 'restic':
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job is not configured for Restic'
                })
                return
            
            # Test repository access using unified backup service
            result = backup_service.test_repository(job_config)
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"Restic validation error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Validation failed: {str(e)}'
            })
    
    def validate_restic_form(self, request_handler, form_data: Dict[str, Any]):
        """Validate Restic configuration from form data"""
        try:
            # Parse Restic destination from form
            from models.forms import destination_parser
            restic_result = destination_parser.parse_restic_destination(form_data)
            
            if not restic_result['valid']:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': restic_result['error']
                })
                return
            
            # Test repository access
            result = backup_service.test_repository({'dest_config': restic_result['config']})
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"Restic form validation error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Form validation failed: {str(e)}'
            })
    
    def get_repository_info(self, request_handler, job_name: str):
        """Get Restic repository information"""
        try:
            if not job_name:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job name is required'
                })
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
                return
            
            job_config = jobs[job_name]
            
            # Get repository analysis
            dest_config = job_config.get('dest_config', {})
            analysis_result = backup_service.analyze_content(dest_config, job_name)
            
            self._send_json_response(request_handler, analysis_result)
            
        except Exception as e:
            logger.error(f"Repository info error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Repository info failed: {str(e)}'
            })
    
    def list_snapshots(self, request_handler, job_name: str):
        """List snapshots for a job"""
        try:
            if not job_name:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job name is required'
                })
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
                return
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            
            # List snapshots with job filter
            filters = {'job_name': job_name}
            result = backup_service.list_snapshots(dest_config, filters)
            
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"List snapshots error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Snapshot listing failed: {str(e)}'
            })
    
    def get_snapshot_stats(self, request_handler, job_name: str, snapshot_id: str):
        """Get statistics for a specific snapshot"""
        try:
            if not job_name or not snapshot_id:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job name and snapshot ID are required'
                })
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
                return
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            
            # Get snapshot details via restic stats command
            try:
                import os
                env = os.environ.copy()
                env['RESTIC_PASSWORD'] = dest_config['password']
                
                cmd = ['restic', '-r', dest_config['repo_uri'], 'stats', snapshot_id, '--json']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
                
                if result.returncode == 0:
                    stats_data = json.loads(result.stdout)
                    self._send_json_response(request_handler, {
                        'success': True,
                        'stats': stats_data
                    })
                else:
                    self._send_json_response(request_handler, {
                        'success': False,
                        'error': f'Stats command failed: {result.stderr}'
                    })
                    
            except subprocess.TimeoutExpired:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Stats command timeout'
                })
            except json.JSONDecodeError:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Invalid stats data returned'
                })
            
        except Exception as e:
            logger.error(f"Snapshot stats error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Stats retrieval failed: {str(e)}'
            })
    
    def browse_directory(self, request_handler, job_name: str, snapshot_id: str, path: str = '/'):
        """Browse directory contents in a snapshot"""
        try:
            if not job_name or not snapshot_id:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job name and snapshot ID are required'
                })
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
                return
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            
            # Browse snapshot contents
            try:
                import os
                env = os.environ.copy()
                env['RESTIC_PASSWORD'] = dest_config['password']
                
                cmd = ['restic', '-r', dest_config['repo_uri'], 'ls', snapshot_id, path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
                
                if result.returncode == 0:
                    # Parse directory listing
                    entries = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            entries.append({
                                'name': os.path.basename(line),
                                'path': line,
                                'type': 'directory' if line.endswith('/') else 'file'
                            })
                    
                    self._send_json_response(request_handler, {
                        'success': True,
                        'path': path,
                        'entries': entries
                    })
                else:
                    self._send_json_response(request_handler, {
                        'success': False,
                        'error': f'Browse command failed: {result.stderr}'
                    })
                    
            except subprocess.TimeoutExpired:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Browse command timeout'
                })
            
        except Exception as e:
            logger.error(f"Directory browse error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Browse failed: {str(e)}'
            })
    
    def init_repository(self, request_handler, job_name: str):
        """Initialize Restic repository for a job"""
        try:
            if not job_name:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job name is required'
                })
                return
            
            jobs = self.backup_config.get_jobs()
            if job_name not in jobs:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
                return
            
            job_config = jobs[job_name]
            dest_config = job_config.get('dest_config', {})
            
            # Initialize repository using backup service
            result = backup_service.initialize_repository(dest_config)
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"Repository init error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Repository initialization failed: {str(e)}'
            })
    
    def initialize_restic_repo(self, request_handler, form_data: Dict[str, Any]):
        """Initialize Restic repository from form data"""
        try:
            # Parse Restic destination from form
            from models.forms import destination_parser
            restic_result = destination_parser.parse_restic_destination(form_data)
            
            if not restic_result['valid']:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': restic_result['error']
                })
                return
            
            # Initialize repository
            result = backup_service.initialize_repository(restic_result['config'])
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"Form repository init error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Repository initialization failed: {str(e)}'
            })
    
    # =============================================================================
    # FILESYSTEM OPERATIONS
    # =============================================================================
    
    def browse_filesystem(self, request_handler):
        """Browse local filesystem for path selection"""
        try:
            # Parse query parameters for path
            url_parts = urlparse(request_handler.path)
            params = parse_qs(url_parts.query)
            path = params.get('path', ['/'])[0]
            
            try:
                path_obj = Path(path)
                if not path_obj.exists():
                    self._send_json_response(request_handler, {
                        'success': False,
                        'error': f'Path does not exist: {path}'
                    })
                    return
                
                if not path_obj.is_dir():
                    self._send_json_response(request_handler, {
                        'success': False,
                        'error': f'Path is not a directory: {path}'
                    })
                    return
                
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
                    self._send_json_response(request_handler, {
                        'success': False,
                        'error': f'Permission denied: {path}'
                    })
                    return
                
                self._send_json_response(request_handler, {
                    'success': True,
                    'path': str(path_obj),
                    'parent': str(path_obj.parent) if path_obj.parent != path_obj else None,
                    'entries': entries
                })
                
            except Exception as e:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f'Filesystem error: {str(e)}'
                })
            
        except Exception as e:
            logger.error(f"Filesystem browse error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Browse failed: {str(e)}'
            })
    
    # =============================================================================
    # NOTIFICATION TESTING
    # =============================================================================
    
    def test_telegram_notification(self, request_handler, form_data: Dict[str, Any]):
        """Test Telegram notification"""
        try:
            test_message = form_data.get('test_message', ['Test notification from Highball'])[0]
            result = self.notification_service.test_provider('telegram')
            
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"Telegram test error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Telegram test failed: {str(e)}'
            })
    
    def test_email_notification(self, request_handler, form_data: Dict[str, Any]):
        """Test email notification"""
        try:
            test_message = form_data.get('test_message', ['Test notification from Highball'])[0]
            result = self.notification_service.test_provider('email')
            
            self._send_json_response(request_handler, result)
            
        except Exception as e:
            logger.error(f"Email test error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Email test failed: {str(e)}'
            })
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def _send_json_response(self, request_handler, data: Dict[str, Any], cors: bool = False):
        """Send JSON response with optional CORS headers"""
        request_handler.send_response(200)
        request_handler.send_header('Content-type', 'application/json')
        
        if cors:
            request_handler.send_header('Access-Control-Allow-Origin', '*')
            request_handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            request_handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        
        request_handler.end_headers()
        request_handler.wfile.write(json.dumps(data).encode())
    
    def _send_api_error(self, request_handler, message: str, status_code: int = 500):
        """Send API error response"""
        request_handler.send_response(status_code)
        request_handler.send_header('Content-type', 'application/json')
        request_handler.end_headers()
        
        error_response = {
            'error': message,
            'timestamp': datetime.now().isoformat()
        }
        request_handler.wfile.write(json.dumps(error_response).encode())