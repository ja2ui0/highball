"""
Maintenance operation executor
Handles execution of forget-prune and check operations using ResticRunner
"""
import subprocess
from time import time
from typing import List
from services.maintenance_operation import MaintenanceOperation, MaintenanceResult
from services.maintenance_defaults import MaintenanceDefaults
from services.restic_runner import ResticCommand, CommandType, TransportType
from services.job_logger import JobLogger


class MaintenanceExecutor:
    """Service for executing maintenance operations"""
    
    def __init__(self):
        self.job_logger = JobLogger()
    
    def execute_discard(self, operation: MaintenanceOperation) -> MaintenanceResult:
        """Execute discard operation (combines forget+prune)"""
        print(f"INFO: Executing discard for job '{operation.job_name}'")
        
        start_time = time()
        
        try:
            # Build retention args
            retention_args = self._build_retention_args(operation.retention_config)
            
            # Create forget command (includes --prune)
            command = self._create_restic_command(operation, CommandType.FORGET, retention_args)
            
            # Execute with maintenance priority
            output = self._execute_command(command, operation.job_name, 'discard')
            
            duration = time() - start_time
            return MaintenanceResult(
                operation_type='discard',
                job_name=operation.job_name,
                success=True,
                duration_seconds=duration,
                output=output
            )
            
        except Exception as e:
            duration = time() - start_time
            return MaintenanceResult(
                operation_type='discard',
                job_name=operation.job_name,
                success=False,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def execute_check(self, operation: MaintenanceOperation) -> MaintenanceResult:
        """Execute check operation"""
        print(f"INFO: Executing check for job '{operation.job_name}'")
        
        start_time = time()
        
        try:
            # Build check args
            check_args = self._build_check_args(operation.check_config)
            
            # Create check command
            command = self._create_restic_command(operation, CommandType.CHECK, check_args)
            
            # Execute with maintenance priority
            output = self._execute_command(command, operation.job_name, 'check')
            
            duration = time() - start_time
            return MaintenanceResult(
                operation_type='check',
                job_name=operation.job_name,
                success=True,
                duration_seconds=duration,
                output=output
            )
            
        except Exception as e:
            duration = time() - start_time
            return MaintenanceResult(
                operation_type='check',
                job_name=operation.job_name,
                success=False,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def _create_restic_command(self, operation: MaintenanceOperation, command_type: CommandType, args: List[str]) -> ResticCommand:
        """Create ResticCommand for maintenance operation"""
        transport = TransportType.SSH if operation.ssh_config else TransportType.LOCAL
        
        return ResticCommand(
            command_type=command_type,
            transport=transport,
            ssh_config=operation.ssh_config,
            repository_url=operation.repository_url,
            args=args,
            environment_vars=operation.environment_vars,
            job_config={'container_runtime': operation.container_runtime}
        )
    
    def _execute_command(self, command: ResticCommand, job_name: str, operation_type: str) -> str:
        """Execute maintenance command with proper logging and priority"""
        # Convert to execution format with maintenance priority
        if command.transport == TransportType.SSH:
            cmd_array = command.to_ssh_command()
        else:
            cmd_array = command.to_local_command()
        
        # Add maintenance-specific nice/ionice priority
        cmd_array = self._add_maintenance_priority(cmd_array)
        
        # Log the command (with password obfuscation)
        from services.command_obfuscation import CommandObfuscationService
        obfuscated_command = CommandObfuscationService.obfuscate_command_array(cmd_array)
        self.job_logger.log_job_execution(job_name, f"Executing {operation_type}: {' '.join(obfuscated_command)}", 'INFO')
        
        # Execute via subprocess
        try:
            result = subprocess.run(cmd_array, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                self.job_logger.log_job_execution(job_name, f"Maintenance {operation_type} completed successfully", 'INFO')
                if result.stdout.strip():
                    self.job_logger.log_job_execution(job_name, f"Output: {result.stdout.strip()}", 'INFO')
                return result.stdout.strip()
            else:
                error_msg = f"Maintenance {operation_type} failed with exit code {result.returncode}"
                if result.stderr.strip():
                    error_msg += f": {result.stderr.strip()}"
                raise Exception(error_msg)
                
        except subprocess.TimeoutExpired:
            raise Exception(f"Maintenance {operation_type} timed out after 1 hour")
        except Exception as e:
            self.job_logger.log_job_execution(job_name, f"Maintenance {operation_type} error: {str(e)}", 'ERROR')
            raise
    
    def _add_maintenance_priority(self, command: List[str]) -> List[str]:
        """Add nice/ionice priority for maintenance operations (lower than backups)"""
        return [
            'nice', f'-n', str(MaintenanceDefaults.NICE_LEVEL),
            'ionice', '-c', str(MaintenanceDefaults.IONICE_CLASS), '-n', str(MaintenanceDefaults.IONICE_LEVEL)
        ] + command
    
    def _build_retention_args(self, retention_config: dict) -> List[str]:
        """Build retention arguments for forget command"""
        if not retention_config:
            retention_config = {}
        
        args = ['--prune']  # Always prune after forget
        
        # Use configured values or defaults
        keep_last = retention_config.get('keep_last', MaintenanceDefaults.KEEP_LAST)
        keep_hourly = retention_config.get('keep_hourly', MaintenanceDefaults.KEEP_HOURLY)
        keep_daily = retention_config.get('keep_daily', MaintenanceDefaults.KEEP_DAILY)
        keep_weekly = retention_config.get('keep_weekly', MaintenanceDefaults.KEEP_WEEKLY)
        keep_monthly = retention_config.get('keep_monthly', MaintenanceDefaults.KEEP_MONTHLY)
        keep_yearly = retention_config.get('keep_yearly', MaintenanceDefaults.KEEP_YEARLY)
        
        args.extend(['--keep-last', str(keep_last)])
        args.extend(['--keep-hourly', str(keep_hourly)])
        args.extend(['--keep-daily', str(keep_daily)])
        args.extend(['--keep-weekly', str(keep_weekly)])
        args.extend(['--keep-monthly', str(keep_monthly)])
        
        if keep_yearly > 0:
            args.extend(['--keep-yearly', str(keep_yearly)])
        
        return args
    
    def _build_check_args(self, check_config: dict) -> List[str]:
        """Build arguments for check command"""
        if not check_config:
            check_config = {}
        
        args = []
        
        # Read data subset for performance balance
        read_data_subset = check_config.get('read_data_subset', MaintenanceDefaults.CHECK_READ_DATA_SUBSET)
        if read_data_subset:
            args.extend(['--read-data-subset', read_data_subset])
        
        return args