"""
Restore execution service for handling Restic restore operations
Handles both dry run and background restore execution with proper command selection
"""
import subprocess
import threading
import time
import select
import sys
from typing import Dict, Any, Optional
from services.job_logger import JobLogger
from services.restic_runner import ResticRunner
from services.command_execution_service import CommandExecutionService, ExecutionConfig
from services.command_obfuscation import obfuscate_password_in_command


class RestoreExecutionService:
    """Service for executing restore operations with progress tracking"""
    
    def __init__(self):
        self.job_logger = JobLogger()
        self.restic_runner = ResticRunner()
        self.active_restores = {}  # Track active restore operations
    
    def execute_dry_run(self, job_config: Dict[str, Any], restore_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute dry run restore and return results"""
        try:
            job_name = restore_config['job_name']
            
            # Set dry run flag
            dry_run_config = {**restore_config, 'dry_run': True}
            
            # Build restic restore command using ResticRunner
            plan = self.restic_runner.plan_restore_job(job_config, dry_run_config)
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
        job_name = restore_config['job_name']
        
        try:
            # Build restic restore command using ResticRunner
            plan = self.restic_runner.plan_restore_job(job_config, restore_config)
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
        import json
        
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
        
        # Import error parser for clean error messages
        from services.restore_error_parser import RestoreErrorParser
        parser = RestoreErrorParser()
        clean_message = parser.parse_error_message(error_message)
        
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