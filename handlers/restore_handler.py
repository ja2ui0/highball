"""
Restore handler for processing backup restore requests
Handles Restic restore operations with progress tracking and password validation
"""
import json
import os
import threading
import subprocess
from urllib.parse import parse_qs
from typing import Dict, Any, List
from services.job_logger import JobLogger
from services.restic_runner import ResticRunner


class RestoreHandler:
    """Handles backup restore operations"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_logger = JobLogger()
        self.restic_runner = ResticRunner()
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
            
            # No password validation needed - confirmation handled by frontend for source overwrites
            
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
    
    def check_restore_overwrites(self, handler, form_data):
        """Check if restore would overwrite existing files at source"""
        try:
            # Parse form data
            job_name = self._safe_get_form_value(form_data, 'job_name')
            snapshot_id = self._safe_get_form_value(form_data, 'snapshot_id')
            select_all = self._safe_get_form_value(form_data, 'select_all') == 'on'
            selected_paths = form_data.get('selected_paths', [''])
            
            # Validate required fields
            if not job_name:
                return self._send_json_response(handler, {'hasOverwrites': False, 'error': 'Job name required'})
            
            # Get job configuration
            jobs = self.backup_config.config.get('backup_jobs', {})
            if job_name not in jobs:
                return self._send_json_response(handler, {'hasOverwrites': False, 'error': 'Job not found'})
            
            job_config = jobs[job_name]
            source_config = job_config.get('source_config', {})
            source_type = job_config.get('source_type', '')
            
            # Get restore target
            restore_target = self._safe_get_form_value(form_data, 'restore_target', 'highball')
            
            # Get paths to check based on restore target
            check_paths = []
            if select_all:
                # For select all, check job's source paths
                source_paths = source_config.get('source_paths', [])
                for path_config in source_paths:
                    if isinstance(path_config, dict):
                        check_paths.append(path_config.get('path', ''))
                    else:
                        check_paths.append(str(path_config))
            else:
                # For specific selection, check selected paths
                check_paths = [path for path in selected_paths if path.strip()]
            
            # Check if any files exist at destination that would be overwritten
            has_overwrites = self._check_destination_files_exist(restore_target, source_type, source_config, check_paths)
            
            return self._send_json_response(handler, {'hasOverwrites': has_overwrites})
            
        except Exception as e:
            return self._send_json_response(handler, {'hasOverwrites': False, 'error': str(e)})
    
    def _check_destination_files_exist(self, restore_target: str, source_type: str, source_config: Dict[str, Any], check_paths: List[str]) -> bool:
        """Check if any files exist at destination that would be overwritten"""
        try:
            if restore_target == 'highball':
                # Check Highball container /restore directory
                restore_dir = '/restore'
                
                
                for path in check_paths:
                    if path:
                        # Convert source path to restore destination path
                        # Remove leading slash and join with restore dir
                        dest_path = os.path.join(restore_dir, path.lstrip('/'))
                        
                        if os.path.exists(dest_path):
                            # If it's a directory, check if it has any contents
                            if os.path.isdir(dest_path):
                                try:
                                    if any(os.scandir(dest_path)):
                                        return True
                                except (PermissionError, OSError):
                                    return True
                            else:
                                # File exists
                                return True
                                
            elif restore_target == 'source':
                # Check at original source location
                if source_type == 'local':
                    # Check local filesystem
                    for path in check_paths:
                        if path and os.path.exists(path):
                            # If it's a directory, check if it has any contents
                            if os.path.isdir(path):
                                try:
                                    if any(os.scandir(path)):
                                        return True
                                except (PermissionError, OSError):
                                    return True
                            else:
                                # File exists
                                return True
                                
                elif source_type == 'ssh':
                    # Check remote filesystem via SSH
                    hostname = source_config.get('hostname', '')
                    username = source_config.get('username', '')
                    
                    if not hostname:
                        return False
                        
                    # Use SSH to check if files exist
                    for path in check_paths:
                        if path:
                            # Build SSH command to check if path exists and has contents
                            ssh_cmd = ['ssh']
                            if username:
                                ssh_cmd.append(f'{username}@{hostname}')
                            else:
                                ssh_cmd.append(hostname)
                            
                            # Check if path exists and is non-empty
                            check_cmd = f'[ -e "{path}" ] && ([ -f "{path}" ] || [ "$(ls -A "{path}" 2>/dev/null)" ])'
                            ssh_cmd.append(check_cmd)
                            
                            try:
                                result = subprocess.run(ssh_cmd, capture_output=True, timeout=10)
                                if result.returncode == 0:
                                    return True  # Path exists and has contents
                            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                                # Assume no overwrites if we can't check
                                continue
            
            return False  # No overwrites detected
            
        except Exception as e:
            self.job_logger.log_job_execution('system', f'Error checking destination files: {str(e)}', 'WARNING')
            return False  # Default to no overwrites if check fails
    
    def _execute_dry_run_restore(self, restore_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute dry run restore and return results"""
        try:
            job_name = restore_config['job_name']
            job_config = restore_config['job_config']
            
            # Set dry run flag
            dry_run_config = {**restore_config, 'dry_run': True}
            
            # Build restic restore command using ResticRunner
            plan = self.restic_runner.plan_restore_job(job_config, dry_run_config)
            if not plan.commands:
                return {'success': False, 'error': 'No restore commands generated'}
            
            # Get first command (restore operations have only one command)
            restore_command = plan.commands[0]
            
            # Build execution command based on transport
            if restore_command.transport.value == 'ssh':
                exec_command = restore_command.to_ssh_command()
            else:
                exec_command = restore_command.to_local_command()
            
            # Debug: Log the exact command being executed
            self.job_logger.log_job_execution(job_name, f"DEBUG: Full command: {' '.join(exec_command)}")
            self.job_logger.log_job_execution(job_name, f"DEBUG: Args from ResticRunner: {restore_command.args}")
            
            # Execute command
            result = subprocess.run(
                exec_command,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for dry run
            )
            
            # Log the dry run (obfuscate password)
            safe_command = self._obfuscate_password_in_command(exec_command)
            self.job_logger.log_job_execution(job_name, f"Dry run restore: {' '.join(safe_command)}")
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
                    'command': ' '.join(exec_command)
                }
            else:
                return {
                    'success': False,
                    'error': f'Dry run failed: {result.stderr}',
                    'output': result.stdout,
                    'command': ' '.join(exec_command)
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
            job_config = restore_config['job_config']
            
            # Build restic restore command using ResticRunner
            plan = self.restic_runner.plan_restore_job(job_config, restore_config)
            if not plan.commands:
                self._finish_restore_with_error(job_name, 'No restore commands generated')
                return
            
            # Get first command (restore operations have only one command)
            restore_command = plan.commands[0]
            
            # Build execution command based on transport
            if restore_command.transport.value == 'ssh':
                exec_command = restore_command.to_ssh_command()
            else:
                exec_command = restore_command.to_local_command()
            
            # Log restore start
            safe_command = self._obfuscate_password_in_command(exec_command)
            self.job_logger.log_job_execution(job_name, f"Starting restore: {' '.join(safe_command)}")
            
            # Execute with progress tracking
            process = subprocess.Popen(
                exec_command,
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
    
    def _obfuscate_password_in_command(self, command: List[str]) -> List[str]:
        """Replace password in command with asterisks for logging"""
        safe_command = command.copy()
        for i, arg in enumerate(safe_command):
            if arg == '--password-command' and i + 1 < len(safe_command):
                # Replace the echo command that contains the password
                safe_command[i + 1] = 'echo "***"'
        return safe_command
    
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