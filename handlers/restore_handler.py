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
                # Map backup paths back to actual source paths
                source_paths = source_config.get('source_paths', [])
                if not source_paths:
                    return False  # No source paths configured
                
                # Map backup paths to actual source paths
                actual_paths_to_check = []
                for check_path in check_paths:
                    if check_path:
                        # Remove container mount prefix (e.g., /backup-source-0/README.md -> README.md)
                        if check_path.startswith('/backup-source-'):
                            # Find the mount number and remove prefix
                            parts = check_path.split('/', 3)  # ['', 'backup-source-N', 'relative', 'path']
                            if len(parts) >= 3:
                                relative_path = parts[2] if len(parts) == 3 else '/'.join(parts[2:])
                                
                                # Map to actual source paths
                                for source_path_config in source_paths:
                                    source_path = source_path_config.get('path', '') if isinstance(source_path_config, dict) else str(source_path_config)
                                    if source_path:
                                        # Combine source path with relative path from backup
                                        actual_path = os.path.join(source_path, relative_path) if relative_path else source_path
                                        actual_paths_to_check.append(actual_path)
                        else:
                            # Direct path - add to check list
                            actual_paths_to_check.append(check_path)
                
                if source_type == 'local':
                    # Check local filesystem
                    for path in actual_paths_to_check:
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
                    for path in actual_paths_to_check:
                        if path:
                            # Build SSH command to check if path exists and has contents
                            ssh_cmd = ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', 
                                     '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null']
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
            
            # Execute using container execution for consistency with backup operations
            from services.command_execution_service import CommandExecutionService, ExecutionConfig
            
            # Configure execution
            config = ExecutionConfig(timeout=300)  # 5 minutes for dry runs
            executor = CommandExecutionService(config)
            
            # Execute based on transport type
            if restore_command.transport.value == 'ssh':
                # SSH restore - use container execution service
                container_cmd = restore_command._build_container_command(restore_command.job_config)
                result = executor.execute_container_via_ssh(
                    restore_command.ssh_config['hostname'],
                    restore_command.ssh_config['username'],
                    container_cmd
                )
                exec_cmd_for_logging = container_cmd
            else:
                # Local restore (Restore to Highball) - use direct restic binary
                local_cmd = restore_command.to_local_command()
                result = executor.execute_locally(local_cmd, restore_command.environment_vars)
                exec_cmd_for_logging = local_cmd
            
            # Log the dry run (obfuscate password)
            job_password = job_config.get('dest_config', {}).get('password', '')
            safe_command = self._obfuscate_password_in_command(exec_cmd_for_logging, job_password)
            self.job_logger.log_job_execution(job_name, f"Dry run restore: {' '.join(safe_command)}")
            self.job_logger.log_job_execution(job_name, f"Dry run result: {result.returncode}")
            if result.stdout:
                self.job_logger.log_job_execution(job_name, f"Dry run stdout: {result.stdout}")
            if result.stderr:
                self.job_logger.log_job_execution(job_name, f"Dry run stderr: {result.stderr}")
            
            # Get safe command for API response
            job_password = job_config.get('dest_config', {}).get('password', '')
            safe_command_for_api = self._obfuscate_password_in_command(exec_cmd_for_logging, job_password)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Dry run completed successfully',
                    'output': result.stdout,
                    'command': ' '.join(safe_command_for_api)
                }
            else:
                return {
                    'success': False,
                    'error': f'Dry run failed: {result.stderr}',
                    'output': result.stdout,
                    'command': ' '.join(safe_command_for_api)
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
            
            # Use container execution for consistency
            from services.command_execution_service import CommandExecutionService, ExecutionConfig
            
            # Configure execution for background restore (longer timeout)
            config = ExecutionConfig(timeout=3600)  # 1 hour for full restores
            executor = CommandExecutionService(config)
            
            # Get container command
            container_cmd = restore_command._build_container_command(restore_command.job_config)
            
            # Log restore start (show actual command that will be executed)
            job_password = restore_config['job_config'].get('dest_config', {}).get('password', '')
            if restore_command.transport.value == 'ssh':
                log_command = container_cmd
            else:
                log_command = restore_command.to_local_command()
            safe_command = self._obfuscate_password_in_command(log_command, job_password)
            self.job_logger.log_job_execution(job_name, f"Starting restore: {' '.join(safe_command)}")
            
            # Get environment variables from restore command
            env_vars = restore_command.environment_vars or {}
            
            # Add cache environment variables to prevent warnings
            env_vars.update({
                'HOME': '/tmp',
                'XDG_CACHE_HOME': '/tmp/.cache'
            })
            
            # Build execution command for progress tracking
            if restore_command.transport.value == 'ssh':
                # For SSH, we need to use the SSH command that wraps the container
                exec_command = restore_command.to_ssh_command()
            else:
                # For local (Restore to Highball), use direct restic binary instead of container
                exec_command = restore_command.to_local_command()
            
            # Execute with progress tracking
            process = subprocess.Popen(
                exec_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env_vars
            )
            
            # Track progress with health monitoring
            import time
            import select
            import sys
            
            last_output_time = time.time()
            initial_response_timeout = 30  # 30 seconds to start producing output
            ongoing_timeout = 60  # 60 seconds between outputs once started
            has_started = False
            
            while True:
                # Check if process has finished
                if process.poll() is not None:
                    break
                
                # Use select to check for available output (non-blocking)
                if sys.platform != 'win32':
                    ready, _, _ = select.select([process.stdout], [], [], 1.0)  # 1 second timeout
                    if ready:
                        output = process.stdout.readline()
                    else:
                        output = ''
                else:
                    # Windows fallback - blocking read with shorter readline
                    output = process.stdout.readline()
                
                current_time = time.time()
                
                if output:
                    # Got output - update timing and mark as started
                    last_output_time = current_time
                    has_started = True
                    
                    # Log output
                    self.job_logger.log_job_execution(job_name, f"Restore output: {output.strip()}")
                    
                    # Try to parse JSON progress (if available)
                    if output.strip().startswith('{'):
                        try:
                            progress_data = json.loads(output.strip())
                            self._update_restore_progress(job_name, progress_data)
                        except json.JSONDecodeError:
                            pass  # Not JSON, continue
                else:
                    # No output - check if we've exceeded timeout
                    time_since_last_output = current_time - last_output_time
                    
                    if not has_started and time_since_last_output > initial_response_timeout:
                        # Process hasn't started producing output within initial timeout
                        self.job_logger.log_job_execution(job_name, 
                            f"Process appears stuck - no initial output after {initial_response_timeout} seconds", "WARNING")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        raise Exception(f"Process failed to start - no output after {initial_response_timeout} seconds")
                    
                    elif has_started and time_since_last_output > ongoing_timeout:
                        # Process was working but stopped producing output
                        self.job_logger.log_job_execution(job_name, 
                            f"Process appears stuck - no output for {ongoing_timeout} seconds", "WARNING")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        raise Exception(f"Process stopped responding - no output for {ongoing_timeout} seconds")
            
            # Wait for completion
            return_code = process.wait()  # Use wait() instead of poll() to ensure process completion
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
        
        # Parse and clean up error message for user display
        clean_message = self._parse_error_message(error_message)
        
        self.job_logger.log_job_status(job_name, 'restore_failed', f'Restore failed: {clean_message}')
        self.job_logger.log_job_execution(job_name, f"Restore failed: {error_message}", "ERROR")
    
    def get_restore_status(self, job_name: str) -> Dict[str, Any]:
        """Get current restore status for a job"""
        if job_name in self.active_restores:
            return self.active_restores[job_name]
        return {'status': 'none'}
    
    def _parse_error_message(self, error_message: str) -> str:
        """Parse error message and extract meaningful information for users"""
        try:
            # Check if message contains JSON lines
            if '{' in error_message and '"message_type"' in error_message:
                lines = error_message.split('\n')
                parsed_errors = []
                initial_error = ""
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('{') and '"message_type"' in line:
                        try:
                            # Parse JSON error
                            error_json = json.loads(line)
                            if error_json.get('message_type') == 'error':
                                error_info = error_json.get('error', {})
                                error_msg = error_info.get('message', '')
                                item = error_json.get('item', '')
                                
                                if error_msg and item:
                                    parsed_errors.append(f"{item}: {error_msg}")
                                elif error_msg:
                                    parsed_errors.append(error_msg)
                            elif error_json.get('message_type') == 'exit_error':
                                exit_msg = error_json.get('message', '')
                                if exit_msg:
                                    parsed_errors.append(f"Fatal: {exit_msg}")
                        except json.JSONDecodeError:
                            continue
                    elif line and not line.startswith('{'):
                        # Capture non-JSON error messages
                        if not initial_error:
                            initial_error = line
                
                # Build clean error message
                if parsed_errors:
                    # Group similar errors
                    error_counts = {}
                    unique_errors = []
                    
                    for error in parsed_errors:
                        # Extract the base error type
                        if ': permission denied' in error:
                            base_error = 'Permission denied accessing backup destination'
                        elif ': no such file or directory' in error:
                            base_error = 'Backup destination path does not exist'
                        elif 'mkdir' in error and 'permission denied' in error:
                            base_error = 'Cannot create directory due to permissions'
                        elif 'chmod' in error or 'lchown' in error:
                            base_error = 'Cannot set file permissions/ownership'
                        else:
                            base_error = error
                        
                        if base_error in error_counts:
                            error_counts[base_error] += 1
                        else:
                            error_counts[base_error] = 1
                            unique_errors.append(base_error)
                    
                    # Build summary message
                    if len(unique_errors) == 1:
                        return unique_errors[0]
                    else:
                        # Show the most common error and count
                        main_error = max(error_counts.keys(), key=lambda k: error_counts[k])
                        total_errors = sum(error_counts.values())
                        return f"{main_error} ({total_errors} errors total)"
                
                # Fall back to initial error if we have one
                if initial_error:
                    return initial_error
            
            # Return original message if no JSON parsing needed
            return error_message
            
        except Exception:
            # If parsing fails, return original message
            return error_message
    
    def _safe_get_form_value(self, form_data: Dict[str, List[str]], key: str, default: str = '') -> str:
        """Safely get form value with default"""
        return form_data.get(key, [default])[0] if form_data.get(key) else default
    
    def _obfuscate_password_in_command(self, command: List[str], password: str = None) -> List[str]:
        """Replace password in command with asterisks for logging using simple string replacement"""
        safe_command = []
        
        for arg in command:
            safe_arg = arg
            
            # If we have the actual password value, do simple string replacement
            if password and password in arg:
                safe_arg = arg.replace(password, '***')
            
            safe_command.append(safe_arg)
                
        return safe_command
    
    def _obfuscate_password_in_list(self, args: List[str], password: str = None) -> List[str]:
        """Replace password in argument list with asterisks for logging"""
        if not args:
            return []
        return self._obfuscate_password_in_command(args, password)
    
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