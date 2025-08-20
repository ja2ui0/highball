"""
Consolidated Operations Handler
Merges all backup and restore operation handlers into single module
Replaces: backup.py, backup_executor.py, backup_command_builder.py, backup_conflict_handler.py,
         backup_notification_dispatcher.py, restore_handler.py
"""

import json
import logging
import subprocess
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import unified models
from models.backup import backup_service, ResticArgumentBuilder
from models.rsync import rsync_service
from models.notifications import create_notification_service

# Import services
from services.management import JobManagementService

logger = logging.getLogger(__name__)

class OperationsHandler:
    """Unified handler for all backup and restore operations"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_management = JobManagementService(backup_config)
        self.notification_service = create_notification_service(backup_config.get_global_settings())
    
    # =============================================================================
    # BACKUP OPERATIONS
    # =============================================================================
    
    def run_backup_job(self, request_handler, job_name: str, dry_run: bool = False):
        """Execute backup job with full orchestration"""
        try:
            if not job_name:
                self._send_error(request_handler, "Job name is required")
                return
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                self._send_error(request_handler, f"Job '{job_name}' not found")
                return
            
            job_config = jobs[job_name]
            # Add job name to config for proper tagging
            job_config['job_name'] = job_name
            
            # Check if job is enabled
            if not job_config.get('enabled', True):
                self._send_error(request_handler, f"Job '{job_name}' is disabled")
                return
            
            # Check for conflicts if required
            if job_config.get('respect_conflicts', True):
                conflicts = self.job_management.check_conflicts(job_name)
                if conflicts:
                    self._send_error(request_handler, 
                                   f"Job '{job_name}' conflicts with running jobs: {', '.join(conflicts)}")
                    return
            
            # Start backup in background thread
            backup_thread = threading.Thread(
                target=self._execute_backup_async,
                args=(job_name, job_config, dry_run)
            )
            backup_thread.daemon = True
            backup_thread.start()
            
            # Send immediate response
            status_message = f"{'Dry run' if dry_run else 'Backup'} started for job '{job_name}'"
            self._send_json_response(request_handler, {
                'success': True,
                'message': status_message,
                'job_name': job_name,
                'dry_run': dry_run
            })
            
        except Exception as e:
            logger.error(f"Backup job error: {e}")
            self._send_error(request_handler, f"Backup error: {str(e)}")
    
    def _execute_backup_async(self, job_name: str, job_config: Dict[str, Any], dry_run: bool):
        """Execute backup operation asynchronously"""
        start_time = datetime.now()
        
        try:
            # Register running job
            self.job_management.register_running_job(job_name)
            
            # Log job start
            self.job_management.log_execution(job_name, f"Starting backup job (dry_run={dry_run})")
            
            # Execute backup based on destination type
            dest_type = job_config.get('dest_type')
            
            if dest_type == 'restic':
                result = backup_service.execute_backup(job_config, dry_run)
            elif dest_type in ['ssh', 'local', 'rsyncd']:
                result = rsync_service.execute_backup(job_config, dry_run)
            else:
                result = {
                    'success': False,
                    'error': f'Unsupported destination type: {dest_type}'
                }
            
            # Calculate duration
            end_time = datetime.now()
            duration_seconds = (end_time - start_time).total_seconds()
            
            # Log result
            if result['success']:
                self.job_management.log_status(job_name, 'completed', f"Backup completed in {duration_seconds:.2f}s")
                
                # Send success notifications if not dry run
                if not dry_run:
                    self.notification_service.notify_job_success(job_name, duration_seconds, job_config)
            else:
                self.job_management.log_status(job_name, 'failed', result['error'])
                
                # Send failure notifications
                self.notification_service.notify_job_failure(job_name, result['error'], job_config)
            
        except Exception as e:
            logger.error(f"Async backup error for {job_name}: {e}")
            self.job_management.log_status(job_name, 'failed', str(e))
            self.notification_service.notify_job_failure(job_name, str(e), job_config)
        
        finally:
            # Unregister running job
            self.job_management.unregister_running_job(job_name)
    
    # =============================================================================
    # RESTORE OPERATIONS
    # =============================================================================
    
    def process_restore_request(self, request_handler, form_data: Dict[str, Any]):
        """Process restore request from form"""
        try:
            job_name = form_data.get('job_name', [''])[0]
            snapshot_id = form_data.get('snapshot_id', [''])[0]
            target_type = form_data.get('target_type', ['safe'])[0]  # safe or source
            dry_run = 'dry_run' in form_data
            
            if not job_name:
                self._send_error(request_handler, "Job name is required")
                return
            
            if not snapshot_id:
                self._send_error(request_handler, "Snapshot ID is required")
                return
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                self._send_error(request_handler, f"Job '{job_name}' not found")
                return
            
            job_config = jobs[job_name]
            
            # Only support Restic restores for now
            if job_config.get('dest_type') != 'restic':
                self._send_error(request_handler, "Restore only supported for Restic repositories")
                return
            
            # Build restore request
            restore_request = {
                'job_name': job_name,
                'job_config': job_config,
                'snapshot_id': snapshot_id,
                'target_type': target_type,
                'dry_run': dry_run
            }
            
            # Add include patterns if specified
            include_patterns = form_data.get('include_patterns', [''])
            if include_patterns[0]:
                restore_request['include_patterns'] = [p.strip() for p in include_patterns[0].split('\n') if p.strip()]
            
            # Execute restore
            result = self._execute_restore(restore_request)
            
            if result['success']:
                self._send_json_response(request_handler, result)
            else:
                self._send_error(request_handler, result['error'])
                
        except Exception as e:
            logger.error(f"Restore request error: {e}")
            self._send_error(request_handler, f"Restore error: {str(e)}")
    
    def _execute_restore(self, restore_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute restore operation"""
        try:
            job_config = restore_request['job_config']
            dest_config = job_config['dest_config']
            
            # Determine target path
            if restore_request['target_type'] == 'safe':
                # Restore to safe location (/restore)
                target_path = f"/restore/{restore_request['job_name']}"
                Path(target_path).mkdir(parents=True, exist_ok=True)
            else:
                # Restore to original source location (risky)
                source_paths = job_config['source_config'].get('source_paths', [])
                if not source_paths:
                    return {'success': False, 'error': 'No source paths defined for restore'}
                target_path = source_paths[0]['path']  # Use first source path
            
            # Use backup service for restore
            from services.restic_repository_service import ResticRepositoryService
            repo_service = ResticRepositoryService()
            
            # Build restore arguments
            restore_args = [
                '-r', dest_config['repo_uri'],
                'restore', restore_request['snapshot_id'],
                '--target', target_path
            ]
            
            # Add include patterns if specified
            if 'include_patterns' in restore_request:
                for pattern in restore_request['include_patterns']:
                    restore_args.extend(['--include', pattern])
            
            if restore_request['dry_run']:
                restore_args.append('--dry-run')
            
            restore_args.extend(['--verbose'])
            
            # Execute restore command
            env = ResticArgumentBuilder.build_environment(dest_config)
            
            cmd = ['restic'] + restore_args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout
                env=env
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f"Restore completed successfully to {target_path}",
                    'target_path': target_path,
                    'output': result.stdout,
                    'dry_run': restore_request['dry_run']
                }
            else:
                return {
                    'success': False,
                    'error': f"Restore failed: {result.stderr}",
                    'output': result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Restore operation timeout (30 minute limit)'
            }
        except Exception as e:
            logger.error(f"Restore execution error: {e}")
            return {
                'success': False,
                'error': f'Restore failed: {str(e)}'
            }
    
    def check_restore_overwrites(self, request_handler, form_data: Dict[str, Any]):
        """Check for potential restore overwrites"""
        try:
            job_name = form_data.get('job_name', [''])[0]
            snapshot_id = form_data.get('snapshot_id', [''])[0]
            target_type = form_data.get('target_type', ['safe'])[0]
            
            if not job_name or not snapshot_id:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': 'Job name and snapshot ID are required'
                })
                return
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                self._send_json_response(request_handler, {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                })
                return
            
            job_config = jobs[job_name]
            
            # Analyze potential overwrites
            overwrite_analysis = self._analyze_restore_overwrites(job_config, snapshot_id, target_type)
            
            self._send_json_response(request_handler, {
                'success': True,
                'analysis': overwrite_analysis
            })
            
        except Exception as e:
            logger.error(f"Overwrite check error: {e}")
            self._send_json_response(request_handler, {
                'success': False,
                'error': f'Overwrite check failed: {str(e)}'
            })
    
    def _analyze_restore_overwrites(self, job_config: Dict[str, Any], snapshot_id: str, target_type: str) -> Dict[str, Any]:
        """Analyze potential file overwrites for restore"""
        try:
            if target_type == 'safe':
                # Safe restore to /restore - minimal risk
                return {
                    'risk_level': 'low',
                    'target_path': f"/restore/{job_config.get('job_name', 'unknown')}",
                    'potential_overwrites': [],
                    'warnings': ['Files will be restored to safe location'],
                    'recommendations': ['Review restored files before moving to final location']
                }
            else:
                # Restore to original location - high risk
                source_paths = job_config['source_config'].get('source_paths', [])
                if not source_paths:
                    return {
                        'risk_level': 'unknown',
                        'error': 'No source paths defined'
                    }
                
                target_path = source_paths[0]['path']
                
                # Check if target path exists and has files
                existing_files = []
                if Path(target_path).exists():
                    try:
                        for file_path in Path(target_path).rglob('*'):
                            if file_path.is_file():
                                existing_files.append(str(file_path))
                                if len(existing_files) >= 10:  # Limit for performance
                                    break
                    except PermissionError:
                        pass
                
                return {
                    'risk_level': 'high' if existing_files else 'medium',
                    'target_path': target_path,
                    'potential_overwrites': existing_files[:10],  # Show first 10
                    'total_existing_files': len(existing_files),
                    'warnings': [
                        'Restoring to original location may overwrite existing files',
                        'Consider using safe restore option instead'
                    ],
                    'recommendations': [
                        'Backup existing files before restore',
                        'Use dry run to preview changes',
                        'Consider restoring to safe location first'
                    ]
                }
                
        except Exception as e:
            logger.error(f"Overwrite analysis error: {e}")
            return {
                'risk_level': 'unknown',
                'error': f'Analysis failed: {str(e)}'
            }
    
    # =============================================================================
    # JOB SCHEDULING
    # =============================================================================
    
    def schedule_job(self, request_handler, form_data: Dict[str, Any]):
        """Schedule a job for execution"""
        try:
            job_name = form_data.get('job_name', [''])[0]
            
            if not job_name:
                self._send_error(request_handler, "Job name is required")
                return
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                self._send_error(request_handler, f"Job '{job_name}' not found")
                return
            
            # Add job to scheduler
            from services.scheduling import SchedulingService
            scheduler = SchedulingService()
            
            job_config = jobs[job_name]
            schedule = job_config.get('schedule', 'manual')
            
            if schedule != 'manual':
                scheduler.schedule_job(job_name, job_config)
                message = f"Job '{job_name}' scheduled with pattern: {schedule}"
            else:
                message = f"Job '{job_name}' is set to manual execution"
            
            self._send_json_response(request_handler, {
                'success': True,
                'message': message,
                'job_name': job_name,
                'schedule': schedule
            })
            
        except Exception as e:
            logger.error(f"Schedule job error: {e}")
            self._send_error(request_handler, f"Schedule error: {str(e)}")
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def _send_json_response(self, request_handler, data: Dict[str, Any]):
        """Send JSON response"""
        request_handler.send_response(200)
        request_handler.send_header('Content-type', 'application/json')
        request_handler.end_headers()
        request_handler.wfile.write(json.dumps(data).encode())
    
    def _send_error(self, request_handler, message: str, status_code: int = 500):
        """Send error response"""
        request_handler.send_response(status_code)
        request_handler.send_header('Content-type', 'application/json')
        request_handler.end_headers()
        
        error_response = {
            'success': False,
            'error': message
        }
        request_handler.wfile.write(json.dumps(error_response).encode())