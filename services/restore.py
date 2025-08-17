"""
Unified restore service for handling Restic restore operations
Consolidates execution, overwrite checking, and error parsing into a single module
"""
import subprocess
import threading
import time
import select
import sys
import os
import json
from typing import Dict, Any, Optional, List
from services.job_logger import JobLogger


class RestoreErrorParser:
    """Service for parsing and cleaning restore error messages"""
    
    def parse_error_message(self, error_message: str) -> str:
        """Parse error message and extract meaningful information for users"""
        try:
            # Check if message contains JSON lines
            if '{' in error_message and '"message_type"' in error_message:
                return self._parse_json_error_message(error_message)
            else:
                # Return original message if no JSON parsing needed
                return error_message
                
        except Exception:
            # If parsing fails, return original message
            return error_message
    
    def _parse_json_error_message(self, error_message: str) -> str:
        """Parse JSON-formatted error messages from Restic"""
        lines = error_message.split('\n')
        parsed_errors = []
        initial_error = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('{') and '"message_type"' in line:
                parsed_error = self._parse_json_line(line)
                if parsed_error:
                    parsed_errors.append(parsed_error)
            elif line and not line.startswith('{'):
                # Capture non-JSON error messages
                if not initial_error:
                    initial_error = line
        
        # Build clean error message
        if parsed_errors:
            return self._aggregate_parsed_errors(parsed_errors)
        elif initial_error:
            return initial_error
        else:
            return error_message
    
    def _parse_json_line(self, line: str) -> str:
        """Parse a single JSON line and extract error information"""
        try:
            error_json = json.loads(line)
            message_type = error_json.get('message_type', '')
            
            if message_type == 'error':
                return self._extract_error_message(error_json)
            elif message_type == 'exit_error':
                return self._extract_exit_error_message(error_json)
            
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _extract_error_message(self, error_json: Dict) -> str:
        """Extract error message from JSON error object"""
        error_info = error_json.get('error', {})
        error_msg = error_info.get('message', '')
        item = error_json.get('item', '')
        
        if error_msg and item:
            return f"{item}: {error_msg}"
        elif error_msg:
            return error_msg
        
        return None
    
    def _extract_exit_error_message(self, error_json: Dict) -> str:
        """Extract exit error message from JSON"""
        exit_msg = error_json.get('message', '')
        if exit_msg:
            return f"Fatal: {exit_msg}"
        
        return None
    
    def _aggregate_parsed_errors(self, parsed_errors: List[str]) -> str:
        """Aggregate and summarize multiple parsed errors"""
        # Group similar errors
        error_counts = {}
        unique_errors = []
        
        for error in parsed_errors:
            # Extract the base error type
            base_error = self._categorize_error(error)
            
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
    
    def _categorize_error(self, error: str) -> str:
        """Categorize error into user-friendly groups"""
        error_lower = error.lower()
        
        # Permission errors
        if 'permission denied' in error_lower:
            if 'mkdir' in error_lower:
                return 'Cannot create directory due to permissions'
            else:
                return 'Permission denied accessing backup destination'
        
        # File not found errors
        elif 'no such file or directory' in error_lower:
            return 'Backup destination path does not exist'
        
        # Ownership/permission setting errors
        elif any(cmd in error_lower for cmd in ['chmod', 'lchown', 'chown']):
            return 'Cannot set file permissions/ownership'
        
        # Network/connectivity errors
        elif any(net_err in error_lower for net_err in ['connection', 'network', 'timeout', 'unreachable']):
            return 'Network connectivity issue'
        
        # Repository errors
        elif any(repo_err in error_lower for repo_err in ['repository', 'snapshot', 'index']):
            return 'Repository or snapshot issue'
        
        # Disk space errors
        elif any(space_err in error_lower for space_err in ['no space', 'disk full', 'quota']):
            return 'Insufficient disk space'
        
        # Authentication errors
        elif any(auth_err in error_lower for auth_err in ['authentication', 'password', 'unauthorized']):
            return 'Authentication failed'
        
        # Default: return original error
        else:
            return error
    
    def get_error_category(self, error_message: str) -> str:
        """Get the primary category of an error for classification"""
        parsed_message = self.parse_error_message(error_message)
        
        # Map categories to types
        if 'permission' in parsed_message.lower():
            return 'permission'
        elif 'network' in parsed_message.lower() or 'connectivity' in parsed_message.lower():
            return 'network'
        elif 'repository' in parsed_message.lower() or 'snapshot' in parsed_message.lower():
            return 'repository'
        elif 'space' in parsed_message.lower() or 'disk' in parsed_message.lower():
            return 'storage'
        elif 'authentication' in parsed_message.lower() or 'password' in parsed_message.lower():
            return 'auth'
        else:
            return 'general'
    
    def suggest_resolution(self, error_message: str) -> str:
        """Suggest resolution steps based on error category"""
        category = self.get_error_category(error_message)
        
        suggestions = {
            'permission': 'Check file permissions and ensure the restore target is writable',
            'network': 'Verify network connectivity and repository accessibility',
            'repository': 'Check repository integrity and snapshot availability',
            'storage': 'Free up disk space at the restore destination',
            'auth': 'Verify repository password and credentials',
            'general': 'Check logs for detailed error information'
        }
        
        return suggestions.get(category, suggestions['general'])


class RestoreOverwriteChecker:
    """Service for checking restore overwrite conflicts"""
    
    def __init__(self):
        self.job_logger = JobLogger()
    
    def check_restore_overwrites(self, restore_target: str, source_type: str, source_config: Dict[str, Any], 
                                check_paths: List[str], select_all: bool = False) -> bool:
        """Check if restore would overwrite existing files at destination"""
        try:
            if restore_target == 'highball':
                return self._check_highball_overwrites(check_paths)
            elif restore_target == 'source':
                return self._check_source_overwrites(source_type, source_config, check_paths, select_all)
            else:
                return False
                
        except Exception as e:
            self.job_logger.log_job_execution('system', f'Error checking destination files: {str(e)}', 'WARNING')
            return False  # Default to no overwrites if check fails
    
    def _check_highball_overwrites(self, check_paths: List[str]) -> bool:
        """Check if files exist in Highball /restore directory that would be overwritten"""
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
        
        return False
    
    def _check_source_overwrites(self, source_type: str, source_config: Dict[str, Any], 
                                check_paths: List[str], select_all: bool) -> bool:
        """Check if files exist at original source location that would be overwritten"""
        # Map backup paths back to actual source paths
        source_paths = source_config.get('source_paths', [])
        if not source_paths:
            return False  # No source paths configured
        
        # Map backup paths to actual source paths
        actual_paths_to_check = self._map_backup_paths_to_source_paths(check_paths, source_paths)
        
        if source_type == 'local':
            return self._check_local_filesystem_overwrites(actual_paths_to_check)
        elif source_type == 'ssh':
            hostname = source_config.get('hostname', '')
            username = source_config.get('username', '')
            return self._check_ssh_filesystem_overwrites(hostname, username, actual_paths_to_check)
        
        return False
    
    def _map_backup_paths_to_source_paths(self, check_paths: List[str], source_paths: List[Dict]) -> List[str]:
        """Map backup paths to actual source paths"""
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
        
        return actual_paths_to_check
    
    def _check_local_filesystem_overwrites(self, paths_to_check: List[str]) -> bool:
        """Check local filesystem for existing files"""
        for path in paths_to_check:
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
        
        return False
    
    def _check_ssh_filesystem_overwrites(self, hostname: str, username: str, paths_to_check: List[str]) -> bool:
        """Check remote filesystem via SSH for existing files"""
        if not hostname:
            return False
        
        # Use SSH to check if files exist
        for path in paths_to_check:
            if path:
                # Build SSH command to check if path exists and has contents
                ssh_cmd = [
                    'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', 
                    '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null'
                ]
                
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
        
        return False
    
    def get_overwrite_paths_for_display(self, restore_target: str, source_type: str, source_config: Dict[str, Any], 
                                       check_paths: List[str]) -> List[str]:
        """Get list of paths that would be overwritten for display to user"""
        overwrite_paths = []
        
        try:
            if restore_target == 'highball':
                restore_dir = '/restore'
                for path in check_paths:
                    if path:
                        dest_path = os.path.join(restore_dir, path.lstrip('/'))
                        if os.path.exists(dest_path):
                            overwrite_paths.append(dest_path)
                            
            elif restore_target == 'source':
                source_paths = source_config.get('source_paths', [])
                actual_paths = self._map_backup_paths_to_source_paths(check_paths, source_paths)
                
                if source_type == 'local':
                    for path in actual_paths:
                        if path and os.path.exists(path):
                            overwrite_paths.append(path)
                elif source_type == 'ssh':
                    # Return summary labels instead of SSH-querying each file for performance.
                    # Core overwrite detection works via SSH - this display method unused by UI.
                    # TODO: If UI needs specific file lists, implement SSH queries here.
                    overwrite_paths = [f"Remote: {path}" for path in actual_paths]
        
        except Exception as e:
            self.job_logger.log_job_execution('system', f'Error getting overwrite paths: {str(e)}', 'WARNING')
        
        return overwrite_paths


class RestoreExecutionService:
    """Service for executing restore operations with progress tracking"""
    
    def __init__(self):
        self.job_logger = JobLogger()
        self.active_restores = {}  # Track active restore operations
        self.error_parser = RestoreErrorParser()
    
    def execute_dry_run(self, job_config: Dict[str, Any], restore_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute dry run restore and return results"""
        try:
            from models.backup import ResticRunner
            from services.command_execution_service import CommandExecutionService, ExecutionConfig
            from services.command_obfuscation import obfuscate_password_in_command
            
            job_name = restore_config['job_name']
            
            # Set dry run flag
            dry_run_config = {**restore_config, 'dry_run': True}
            
            # Build restic restore command using ResticRunner
            restic_runner = ResticRunner()
            plan = restic_runner.plan_restore_job(job_config, dry_run_config)
            if not plan.commands:
                return {'success': False, 'error': 'No restore commands generated'}
            
            # Get first command (restore operations have only one command)
            restore_command = plan.commands[0]
            
            # Execute using container execution for consistency with backup operations
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
            safe_command = obfuscate_password_in_command(exec_cmd_for_logging, job_password)
            self.job_logger.log_job_execution(job_name, f"Dry run restore: {' '.join(safe_command)}")
            self.job_logger.log_job_execution(job_name, f"Dry run result: {result.returncode}")
            if result.stdout:
                self.job_logger.log_job_execution(job_name, f"Dry run stdout: {result.stdout}")
            if result.stderr:
                self.job_logger.log_job_execution(job_name, f"Dry run stderr: {result.stderr}")
            
            # Get safe command for API response
            safe_command_for_api = obfuscate_password_in_command(exec_cmd_for_logging, job_password)
            
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
    
    def start_background_restore(self, job_config: Dict[str, Any], restore_config: Dict[str, Any]):
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
            args=(job_config, restore_config)
        )
        restore_thread.daemon = True
        restore_thread.start()
    
    def _execute_background_restore(self, job_config: Dict[str, Any], restore_config: Dict[str, Any]):
        """Execute restore operation in background with progress tracking"""
        from models.backup import ResticRunner
        from services.command_obfuscation import obfuscate_password_in_command
        
        job_name = restore_config['job_name']
        
        try:
            # Build restic restore command using ResticRunner
            restic_runner = ResticRunner()
            plan = restic_runner.plan_restore_job(job_config, restore_config)
            if not plan.commands:
                self._finish_restore_with_error(job_name, 'No restore commands generated')
                return
            
            # Get first command (restore operations have only one command)
            restore_command = plan.commands[0]
            
            # Get environment variables from restore command
            env_vars = restore_command.environment_vars or {}
            
            # Add cache environment variables to prevent warnings
            env_vars.update({
                'HOME': '/tmp',
                'XDG_CACHE_HOME': '/tmp/.cache'
            })
            
            # Build execution command based on transport type
            if restore_command.transport.value == 'ssh':
                # For SSH, we need to use the SSH command that wraps the container
                container_cmd = restore_command._build_container_command(restore_command.job_config)
                exec_command = restore_command.to_ssh_command()
                exec_cmd_for_logging = container_cmd
            else:
                # For local (Restore to Highball), use direct restic binary
                exec_command = restore_command.to_local_command()
                exec_cmd_for_logging = exec_command
            
            # Log restore start
            job_password = job_config.get('dest_config', {}).get('password', '')
            safe_command = obfuscate_password_in_command(exec_cmd_for_logging, job_password)
            self.job_logger.log_job_execution(job_name, f"Starting restore: {' '.join(safe_command)}")
            
            # Execute with progress tracking
            process = subprocess.Popen(
                exec_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env_vars
            )
            
            # Track progress with health monitoring
            self._monitor_restore_progress(job_name, process)
            
            # Wait for completion
            return_code = process.wait()
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
    
    def _monitor_restore_progress(self, job_name: str, process: subprocess.Popen):
        """Monitor restore progress with health monitoring and JSON parsing"""
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
        
        # Parse error message for clean user display
        clean_message = self.error_parser.parse_error_message(error_message)
        
        self.job_logger.log_job_status(job_name, 'restore_failed', f'Restore failed: {clean_message}')
        self.job_logger.log_job_execution(job_name, f"Restore failed: {error_message}", "ERROR")
    
    def get_restore_status(self, job_name: str) -> Dict[str, Any]:
        """Get current restore status for a job"""
        if job_name in self.active_restores:
            return self.active_restores[job_name]
        return {'status': 'none'}
    
    def is_restore_active(self, job_name: str) -> bool:
        """Check if restore is currently active for a job"""
        return job_name in self.active_restores


class RestoreService:
    """Main restore service that orchestrates all restore operations"""
    
    def __init__(self):
        self.execution_service = RestoreExecutionService()
        self.overwrite_checker = RestoreOverwriteChecker()
        self.error_parser = RestoreErrorParser()
    
    def execute_dry_run(self, job_config: Dict[str, Any], restore_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute dry run restore and return results"""
        return self.execution_service.execute_dry_run(job_config, restore_config)
    
    def start_background_restore(self, job_config: Dict[str, Any], restore_config: Dict[str, Any]):
        """Start restore operation in background thread"""
        self.execution_service.start_background_restore(job_config, restore_config)
    
    def check_restore_overwrites(self, restore_target: str, source_type: str, source_config: Dict[str, Any], 
                                check_paths: List[str], select_all: bool = False) -> bool:
        """Check if restore would overwrite existing files at destination"""
        return self.overwrite_checker.check_restore_overwrites(restore_target, source_type, source_config, check_paths, select_all)
    
    def get_overwrite_paths_for_display(self, restore_target: str, source_type: str, source_config: Dict[str, Any], 
                                       check_paths: List[str]) -> List[str]:
        """Get list of paths that would be overwritten for display to user"""
        return self.overwrite_checker.get_overwrite_paths_for_display(restore_target, source_type, source_config, check_paths)
    
    def get_restore_status(self, job_name: str) -> Dict[str, Any]:
        """Get current restore status for a job"""
        return self.execution_service.get_restore_status(job_name)
    
    def is_restore_active(self, job_name: str) -> bool:
        """Check if restore is currently active for a job"""
        return self.execution_service.is_restore_active(job_name)
    
    def parse_error_message(self, error_message: str) -> str:
        """Parse error message and extract meaningful information for users"""
        return self.error_parser.parse_error_message(error_message)
    
    def suggest_resolution(self, error_message: str) -> str:
        """Suggest resolution steps based on error category"""
        return self.error_parser.suggest_resolution(error_message)