"""
Backup execution service
Handles the core backup execution, command building, and logging
"""
import subprocess
import time
from datetime import datetime
import shlex
from services.job_logger import JobLogger
from .command_builder_factory import CommandBuilderFactory


class BackupExecutor:
    """Handles backup execution and logging"""

    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.job_logger = JobLogger()
        self.command_factory = CommandBuilderFactory(backup_config)

    def execute_backup(self, job_name, job_config, dry_run, trigger_source):
        """Execute backup and return result with timing information"""
        start_time = time.time()
        
        try:
            result = self._execute_backup(job_name, job_config, dry_run, trigger_source)
            duration = time.time() - start_time
            result["duration"] = duration
            
            # Log completion status
            if dry_run:
                status = "completed-dry-run" if result["success"] else "error-dry-run"
                message = f'Dry run completed with return code {result["return_code"]} (triggered by {trigger_source})'
            else:
                status = "completed" if result["success"] else "error"
                message = f'Backup completed with return code {result["return_code"]}'
            
            self.job_logger.log_job_status(job_name, status, message)
            self.job_logger.log_job_execution(job_name, result["log_content"])
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_job_error(job_name, str(e))
            return {
                "success": False,
                "return_code": -1,
                "duration": duration,
                "log_content": f"ERROR: {str(e)}"
            }

    def log_job_start(self, job_name, dry_run, source):
        """Log job start status"""
        started_msg = (
            "Dry run started" if dry_run else "Backup started"
        ) + f" (triggered by {source})"
        try:
            self.job_logger.log_job_status(job_name, "started", started_msg)
        except Exception:
            pass

    def log_job_error(self, job_name, error_message):
        """Log job error"""
        self.job_logger.log_job_status(job_name, "error", error_message)
        self.job_logger.log_job_execution(job_name, f"ERROR: {error_message}", "ERROR")

    def _execute_backup(self, job_name, job_config, dry_run, trigger_source):
        """Execute rsync command and log output"""
        timestamp = datetime.now().isoformat()
        mode_text = "DRY RUN" if dry_run else "REAL BACKUP"

        # Build command using appropriate builder via factory
        command_info = self.command_factory.build_command(job_config, job_name, dry_run)
        
        # Prepare log content
        log_content = self._build_log_header(
            job_name=job_name,
            timestamp=timestamp,
            mode_text=mode_text,
            trigger_source=trigger_source,
            command_info=command_info,
            job_config=job_config,
        )

        # Execute using appropriate execution strategy
        timeout = self._get_timeout(dry_run)
        
        # Determine execution strategy based on job configuration
        source_type = job_config.get('source_type')
        source_config = job_config.get('source_config', {})
        dest_type = job_config.get('dest_type')
        
        try:
            if source_type == 'ssh' and source_config.get('hostname') and dest_type == 'restic':
                # SSH + Restic: Use container execution via CommandExecutionService
                execution_result = self._execute_via_container_ssh(command_info, source_config, timeout)
            else:
                # Local or non-container execution: Use traditional subprocess
                execution_result = self._execute_via_subprocess(command_info, timeout)
            
            log_content += f"\nSTDOUT:\n{execution_result.stdout}\n"
            log_content += f"\nSTDERR:\n{execution_result.stderr}\n"
            log_content += f"\nRETURN CODE: {execution_result.returncode}\n"
            success = execution_result.success

        except Exception as e:
            log_content += f"\nERROR: {str(e)}\n"
            success = False
            execution_result = type("Result", (), {"returncode": -1})()

        # Log detailed execution
        try:
            self.job_logger.log_job_execution(job_name, log_content)
        except Exception:
            pass

        return {
            "success": success,
            "return_code": execution_result.returncode,
            "log_content": log_content,
        }

    def _get_timeout(self, dry_run):
        """Get timeout configuration for backup execution"""
        global_settings = self.backup_config.config.get("global_settings", {})
        
        # Default: 300s for dry runs, unlimited for real backups
        dry_default = 300
        timeout_cfg = global_settings.get("rsync_timeout_seconds")
        
        if isinstance(timeout_cfg, (int, float)):
            return timeout_cfg
        return dry_default if dry_run else None

    def _build_log_header(self, job_name, timestamp, mode_text, trigger_source, command_info, job_config):
        """Build log header with job details"""
        return f"""
========================================
Backup Job: {job_name} ({mode_text})
Time: {timestamp}
Triggered by: {trigger_source}
========================================
COMMAND EXECUTED:
{command_info.log_cmd_str}
SOURCE: {command_info.src_display}
DESTINATION: {command_info.dst_display}
INCLUDES: {job_config.get('includes', [])}
EXCLUDES: {job_config.get('excludes', [])}
========================================
{mode_text} OUTPUT:
"""
    
    def _execute_via_container_ssh(self, command_info, source_config, timeout):
        """Execute container command via SSH using CommandExecutionService pattern from repository initialization"""
        from services.command_execution_service import CommandExecutionService, ExecutionConfig
        
        # Configure execution with backup timeout
        backup_config = ExecutionConfig(
            timeout=timeout or 3600,  # Default 1 hour if no timeout
            capture_output=True,
            text=True
        )
        
        executor = CommandExecutionService(backup_config)
        
        # Execute container command via SSH - command_info.exec_argv should be the container command
        result = executor.execute_container_via_ssh(
            source_config['hostname'],
            source_config['username'],
            command_info.exec_argv
        )
        
        return result
    
    def _execute_via_subprocess(self, command_info, timeout):
        """Execute command via traditional subprocess for local/non-container operations"""
        try:
            if timeout is None:
                result = subprocess.run(command_info.exec_argv, capture_output=True, text=True)
            else:
                result = subprocess.run(command_info.exec_argv, capture_output=True, text=True, timeout=timeout)
            
            # Convert subprocess result to ExecutionResult-like format
            return type("ExecutionResult", (), {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            })()
            
        except subprocess.TimeoutExpired:
            return type("ExecutionResult", (), {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds"
            })()