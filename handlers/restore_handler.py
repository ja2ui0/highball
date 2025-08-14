"""
Restore handler for processing backup restore requests
Handles Restic restore operations with progress tracking and password validation
"""
import json
import threading
import subprocess
from urllib.parse import parse_qs
from typing import Dict, Any, List
from services.job_logger import JobLogger


class RestoreHandler:
    """Handles backup restore operations"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_logger = JobLogger()
        self.active_restores = {}  # Track active restore operations
    
    def process_restore_request(self, handler, form_data):
        """Process restore request from job inspect page"""
        try:
            # Parse form data
            job_name = self._safe_get_form_value(form_data, 'job_name')
            snapshot_id = self._safe_get_form_value(form_data, 'snapshot_id')
            restore_target = self._safe_get_form_value(form_data, 'restore_target', 'highball')
            dry_run = self._safe_get_form_value(form_data, 'dry_run') == 'on'
            select_all = self._safe_get_form_value(form_data, 'select_all') == 'on'
            selected_paths = form_data.get('selected_paths', [''])
            password = self._safe_get_form_value(form_data, 'password', '')
            
            # Validate required fields
            if not job_name:
                return self._send_error_response(handler, 'Job name is required')
            
            if not snapshot_id and not select_all:
                return self._send_error_response(handler, 'Snapshot ID is required')
            
            # Get job configuration
            jobs = self.backup_config.config.get('backup_jobs', {})
            if job_name not in jobs:
                return self._send_error_response(handler, f'Job not found: {job_name}')
            
            job_config = jobs[job_name]
            dest_type = job_config.get('dest_type', '')
            
            # Only support Restic for now
            if dest_type != 'restic':
                return self._send_error_response(handler, f'Restore not supported for job type: {dest_type}')
            
            # Validate password for non-dry-run operations
            if not dry_run and not password:
                return self._send_error_response(handler, 'Password is required for actual restore operations')
            
            # Check if restore is already running for this job
            if job_name in self.active_restores:
                return self._send_error_response(handler, f'Restore already in progress for job: {job_name}')
            
            # Build restore configuration
            restore_config = {
                'job_name': job_name,
                'job_config': job_config,
                'snapshot_id': snapshot_id,
                'restore_target': restore_target,
                'dry_run': dry_run,
                'select_all': select_all,
                'selected_paths': [path for path in selected_paths if path.strip()],
                'password': password
            }
            
            if dry_run:
                # Execute dry run synchronously and return result
                result = self._execute_dry_run_restore(restore_config)
                return self._send_json_response(handler, result)
            else:
                # Start background restore process
                self._start_background_restore(restore_config)
                return self._send_json_response(handler, {
                    'success': True,
                    'message': f'Restore started for job: {job_name}',
                    'job_name': job_name
                })
                
        except Exception as e:
            return self._send_error_response(handler, f'Restore request failed: {str(e)}')
    
    def _execute_dry_run_restore(self, restore_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute dry run restore and return results"""
        try:
            job_name = restore_config['job_name']
            
            # Build restic restore command for dry run
            cmd_result = self._build_restic_restore_command(restore_config, dry_run=True)
            if not cmd_result['success']:
                return cmd_result
            
            # Execute command
            result = subprocess.run(
                cmd_result['command'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for dry run
            )
            
            # Log the dry run
            self.job_logger.log_job_execution(job_name, f"Dry run restore: {' '.join(cmd_result['command'])}")
            self.job_logger.log_job_execution(job_name, f"Dry run result: {result.returncode}")
            if result.stdout:
                self.job_logger.log_job_execution(job_name, f"Dry run stdout: {result.stdout}")
            if result.stderr:
                self.job_logger.log_job_execution(job_name, f"Dry run stderr: {result.stderr}")
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Dry run completed successfully',
                    'output': result.stdout,
                    'command': ' '.join(cmd_result['command'])
                }
            else:
                return {
                    'success': False,
                    'error': f'Dry run failed: {result.stderr}',
                    'output': result.stdout,
                    'command': ' '.join(cmd_result['command'])
                }
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Dry run timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Dry run error: {str(e)}'}
    
    def _start_background_restore(self, restore_config: Dict[str, Any]):
        """Start restore operation in background thread"""
        job_name = restore_config['job_name']
        
        # Mark restore as active
        self.active_restores[job_name] = {
            'status': 'starting',
            'progress': 0,
            'message': 'Initializing restore...'
        }
        
        # Update job status to show restore in progress
        self.job_logger.log_job_status(job_name, 'restoring', 'Restore operation starting...')
        
        # Start background thread
        restore_thread = threading.Thread(
            target=self._execute_background_restore,
            args=(restore_config,)
        )
        restore_thread.daemon = True
        restore_thread.start()
    
    def _execute_background_restore(self, restore_config: Dict[str, Any]):
        """Execute restore operation in background with progress tracking"""
        job_name = restore_config['job_name']
        
        try:
            # Build restic restore command
            cmd_result = self._build_restic_restore_command(restore_config, dry_run=False)
            if not cmd_result['success']:
                self._finish_restore_with_error(job_name, cmd_result['error'])
                return
            
            # Log restore start
            self.job_logger.log_job_execution(job_name, f"Starting restore: {' '.join(cmd_result['command'])}")
            
            # Execute with progress tracking
            process = subprocess.Popen(
                cmd_result['command'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Track progress if using JSON output
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                    
                if output:
                    # Log output
                    self.job_logger.log_job_execution(job_name, f"Restore output: {output.strip()}")
                    
                    # Try to parse JSON progress (if available)
                    if output.strip().startswith('{'):
                        try:
                            progress_data = json.loads(output.strip())
                            self._update_restore_progress(job_name, progress_data)
                        except json.JSONDecodeError:
                            pass  # Not JSON, continue
            
            # Wait for completion
            return_code = process.poll()
            stderr_output = process.stderr.read()
            
            # Log completion
            self.job_logger.log_job_execution(job_name, f"Restore completed with code: {return_code}")
            if stderr_output:
                self.job_logger.log_job_execution(job_name, f"Restore stderr: {stderr_output}")
            
            if return_code == 0:
                self._finish_restore_success(job_name)
            else:
                self._finish_restore_with_error(job_name, f"Restore failed: {stderr_output}")
                
        except Exception as e:
            self._finish_restore_with_error(job_name, f"Restore execution error: {str(e)}")
    
    def _build_restic_restore_command(self, restore_config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Build restic restore command based on configuration"""
        try:
            job_config = restore_config['job_config']
            dest_config = job_config.get('dest_config', {})
            
            # Basic restic command
            cmd = ['restic']
            
            # Add repository
            repo_uri = dest_config.get('repo_uri') or dest_config.get('dest_string')
            if repo_uri:
                cmd.extend(['-r', repo_uri])
            else:
                return {'success': False, 'error': 'No repository URI found in job configuration'}
            
            # Add password
            password = restore_config.get('password', '')
            if password:
                cmd.extend(['--password-command', f'echo "{password}"'])
            
            # Restore command
            cmd.append('restore')
            
            # Add snapshot ID (latest if select_all)
            if restore_config.get('select_all'):
                cmd.append('latest')
            else:
                snapshot_id = restore_config.get('snapshot_id')
                if snapshot_id:
                    cmd.append(snapshot_id)
                else:
                    return {'success': False, 'error': 'No snapshot ID specified'}
            
            # Add target directory
            if restore_config.get('restore_target') == 'highball':
                restore_path = '/restore'
                cmd.extend(['--target', restore_path])
            else:
                return {'success': False, 'error': f'Unsupported restore target: {restore_config.get("restore_target")}'}
            
            # Add selected paths (if not select_all)
            if not restore_config.get('select_all'):
                selected_paths = restore_config.get('selected_paths', [])
                if selected_paths:
                    for path in selected_paths:
                        cmd.extend(['--include', path])
            
            # Add dry run flag
            if dry_run:
                cmd.append('--dry-run')
            
            # Add JSON output for progress tracking (if not dry run)
            if not dry_run:
                cmd.append('--json')
            
            return {
                'success': True,
                'command': cmd,
                'description': f'Restic restore to {restore_config.get("restore_target")}'
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Command building error: {str(e)}'}
    
    def _update_restore_progress(self, job_name: str, progress_data: Dict[str, Any]):
        """Update restore progress from JSON output"""
        try:
            if job_name in self.active_restores:
                # Extract progress information (Restic JSON format)
                files_restored = progress_data.get('files_restored', 0)
                total_files = progress_data.get('total_files', 1)
                bytes_restored = progress_data.get('bytes_restored', 0)
                total_bytes = progress_data.get('total_bytes', 1)
                
                # Calculate percentage
                progress = min(100, int((files_restored / max(total_files, 1)) * 100))
                
                self.active_restores[job_name].update({
                    'status': 'running',
                    'progress': progress,
                    'message': f'Restoring files... {files_restored}/{total_files} files',
                    'files_restored': files_restored,
                    'total_files': total_files,
                    'bytes_restored': bytes_restored,
                    'total_bytes': total_bytes
                })
                
                # Update job status
                self.job_logger.log_job_status(job_name, 'restoring', f'Restoring... {progress}% ({files_restored}/{total_files} files)')
        
        except Exception as e:
            self.job_logger.log_job_execution(job_name, f"Progress update error: {str(e)}")
    
    def _finish_restore_success(self, job_name: str):
        """Mark restore as completed successfully"""
        if job_name in self.active_restores:
            del self.active_restores[job_name]
        
        self.job_logger.log_job_status(job_name, 'restore_completed', 'Restore operation completed successfully')
        self.job_logger.log_job_execution(job_name, "Restore completed successfully")
    
    def _finish_restore_with_error(self, job_name: str, error_message: str):
        """Mark restore as failed with error"""
        if job_name in self.active_restores:
            del self.active_restores[job_name]
        
        self.job_logger.log_job_status(job_name, 'restore_failed', f'Restore failed: {error_message}')
        self.job_logger.log_job_execution(job_name, f"Restore failed: {error_message}", "ERROR")
    
    def get_restore_status(self, job_name: str) -> Dict[str, Any]:
        """Get current restore status for a job"""
        if job_name in self.active_restores:
            return self.active_restores[job_name]
        return {'status': 'none'}
    
    def _safe_get_form_value(self, form_data: Dict[str, List[str]], key: str, default: str = '') -> str:
        """Safely get form value with default"""
        return form_data.get(key, [default])[0] if form_data.get(key) else default
    
    def _send_json_response(self, handler, data: Dict[str, Any]):
        """Send JSON response"""
        handler.send_response(200)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        
        response = json.dumps(data, indent=2)
        handler.wfile.write(response.encode('utf-8'))
    
    def _send_error_response(self, handler, error_message: str):
        """Send error response"""
        error_data = {
            'success': False,
            'error': error_message
        }
        self._send_json_response(handler, error_data)