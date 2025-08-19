"""
Unified maintenance service for Restic repository operations
Consolidates all maintenance-related functionality into a single module
"""
import subprocess
from time import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass 
class MaintenanceOperation:
    """Represents a maintenance operation to be executed"""
    operation_type: str  # 'discard' (forget+prune combined) or 'check'
    job_name: str
    repository_url: str
    environment_vars: Dict[str, str]
    ssh_config: Optional[Dict[str, str]] = None
    container_runtime: str = "docker"
    retention_config: Optional[Dict[str, Any]] = None
    check_config: Optional[Dict[str, Any]] = None


@dataclass
class MaintenanceResult:
    """Result of a maintenance operation"""
    operation_type: str
    job_name: str
    success: bool
    duration_seconds: float = 0.0
    output: str = ""
    error_message: Optional[str] = None


@dataclass
class MaintenanceDefaults:
    """Default maintenance parameters following Restic best practices"""
    # Retention policy - keeps reasonable amount while preventing unbounded growth
    KEEP_LAST = 7        # always keep last 7 snapshots regardless of age
    KEEP_HOURLY = 6      # keep 6 most recent hourly snapshots (6 hours coverage)
    KEEP_DAILY = 7       # keep 7 most recent daily snapshots (1 week coverage)
    KEEP_WEEKLY = 4      # keep 4 most recent weekly snapshots (1 month coverage)
    KEEP_MONTHLY = 6     # keep 6 most recent monthly snapshots (6 months coverage)
    KEEP_YEARLY = 0      # disable yearly retention by default
    
    # Scheduling defaults
    DISCARD_SCHEDULE = "0 3 * * *"         # daily at 3am - combines forget+prune operations
    CHECK_SCHEDULE = "0 2 * * 0"           # weekly Sunday 2am (staggered from backups)
    
    # Check operation defaults
    CHECK_READ_DATA_SUBSET = "5%"          # balance integrity vs performance
    
    # Resource priority (lower than backups)
    NICE_LEVEL = 10                        # vs backup nice -n 5
    IONICE_CLASS = 3                       # idle vs backup ionice -c 2
    IONICE_LEVEL = 7                       # vs backup ionice -n 4


class MaintenanceConfigManager:
    """Service for managing maintenance configuration and defaults"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def is_maintenance_enabled(self, job_name: str) -> bool:
        """Check if maintenance is enabled for job (auto or user)"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Only applicable to Restic jobs
        if job_config.get('dest_type') != 'restic':
            return False
        
        maintenance_mode = self.get_maintenance_mode(job_name)
        return maintenance_mode in ['auto', 'user']
    
    def get_maintenance_mode(self, job_name: str) -> str:
        """Get maintenance mode: 'auto', 'user', or 'off'"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        return job_config.get('restic_maintenance', 'auto')
    
    def get_discard_schedule(self, job_name: str) -> str:
        """Get discard schedule for job (combines forget+prune operations)"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'maintenance_discard_schedule' in job_config:
            return job_config['maintenance_discard_schedule']
        
        # Global default
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        return maintenance_settings.get('discard_schedule', MaintenanceDefaults.DISCARD_SCHEDULE)
    
    def get_check_schedule(self, job_name: str) -> str:
        """Get check schedule for job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'maintenance_check_schedule' in job_config:
            return job_config['maintenance_check_schedule']
        
        # Global default
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        return maintenance_settings.get('check_schedule', MaintenanceDefaults.CHECK_SCHEDULE)
    
    def get_retention_policy(self, job_name: str) -> Dict[str, Any]:
        """Get retention policy for job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'retention_policy' in job_config:
            return job_config['retention_policy']
        
        # Global default policy
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        global_retention = maintenance_settings.get('retention_policy', {})
        
        # Merge with defaults
        default_retention = {
            'keep_last': MaintenanceDefaults.KEEP_LAST,
            'keep_hourly': MaintenanceDefaults.KEEP_HOURLY,
            'keep_daily': MaintenanceDefaults.KEEP_DAILY,
            'keep_weekly': MaintenanceDefaults.KEEP_WEEKLY,
            'keep_monthly': MaintenanceDefaults.KEEP_MONTHLY,
            'keep_yearly': MaintenanceDefaults.KEEP_YEARLY
        }
        
        # Override defaults with global settings
        default_retention.update(global_retention)
        
        return default_retention
    
    def get_check_config(self, job_name: str) -> Dict[str, Any]:
        """Get check configuration for job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        # Per-job override
        if 'maintenance_check_config' in job_config:
            return job_config['maintenance_check_config']
        
        # Global default
        global_settings = self.backup_config.config.get('global_settings', {})
        maintenance_settings = global_settings.get('maintenance', {})
        global_check = maintenance_settings.get('check_config', {})
        
        # Merge with defaults
        default_check = {
            'read_data_subset': MaintenanceDefaults.CHECK_READ_DATA_SUBSET
        }
        
        default_check.update(global_check)
        return default_check
    
    def get_maintenance_summary(self, job_name: str) -> Dict[str, Any]:
        """Get maintenance status summary for a job"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name, {})
        
        if job_config.get('dest_type') != 'restic':
            return {'applicable': False, 'reason': 'Not a Restic job'}
        
        maintenance_mode = job_config.get('restic_maintenance', 'auto')
        maintenance_enabled = maintenance_mode in ['auto', 'user']
        
        return {
            'applicable': True,
            'maintenance_enabled': maintenance_enabled,
            'maintenance_mode': maintenance_mode,
            'discard_schedule': self.get_discard_schedule(job_name),
            'check_schedule': self.get_check_schedule(job_name),
            'retention_policy': self.get_retention_policy(job_name)
        }


class MaintenanceOperationFactory:
    """Factory for creating maintenance operations from job configurations"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.config_manager = MaintenanceConfigManager(backup_config)
    
    def create_discard_operation(self, job_name: str) -> MaintenanceOperation:
        """Create discard operation for job (combines forget+prune)"""
        job_config = self._get_job_config(job_name)
        base_operation = self._create_base_operation(job_name, job_config, 'discard')
        
        # Add retention configuration
        base_operation.retention_config = self.config_manager.get_retention_policy(job_name)
        
        return base_operation
    
    def create_check_operation(self, job_name: str) -> MaintenanceOperation:
        """Create check operation for job"""
        job_config = self._get_job_config(job_name)
        base_operation = self._create_base_operation(job_name, job_config, 'check')
        
        # Add check configuration
        base_operation.check_config = self.config_manager.get_check_config(job_name)
        
        return base_operation
    
    def _create_base_operation(self, job_name: str, job_config: Dict[str, Any], operation_type: str) -> MaintenanceOperation:
        """Create base maintenance operation from job config"""
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        # Build repository URL and environment
        repository_url = dest_config.get('repo_uri', dest_config.get('dest_string', ''))
        environment_vars = self._build_environment_vars(dest_config)
        
        # SSH config for remote operations
        ssh_config = None
        if source_config.get('hostname'):
            ssh_config = {
                'hostname': source_config['hostname'],
                'username': source_config.get('username', 'root')
            }
        
        return MaintenanceOperation(
            operation_type=operation_type,
            job_name=job_name,
            repository_url=repository_url,
            environment_vars=environment_vars,
            ssh_config=ssh_config,
            container_runtime=job_config.get('container_runtime', 'docker')
        )
    
    def _get_job_config(self, job_name: str) -> Dict[str, Any]:
        """Get job configuration from backup config"""
        jobs = self.backup_config.config.get('backup_jobs', {})
        return jobs.get(job_name, {})
    
    def _build_environment_vars(self, dest_config: Dict[str, Any]) -> Dict[str, str]:
        """Build environment variables for Restic execution"""
        env_vars = {}
        
        # Repository password
        password = dest_config.get('password', '')
        if password:
            env_vars['RESTIC_PASSWORD'] = password
        
        # Repository-specific environment variables
        repo_type = dest_config.get('repo_type', 'local')
        if repo_type == 'rest':
            # REST server specific variables could go here
            pass
        elif repo_type == 's3':
            # S3 specific variables
            if dest_config.get('aws_access_key_id'):
                env_vars['AWS_ACCESS_KEY_ID'] = dest_config['aws_access_key_id']
            if dest_config.get('aws_secret_access_key'):
                env_vars['AWS_SECRET_ACCESS_KEY'] = dest_config['aws_secret_access_key']
        
        return env_vars


class MaintenanceExecutor:
    """Service for executing maintenance operations"""
    
    def __init__(self):
        from services.management import JobManagementService
        self.job_management = JobManagementService()
    
    def execute_discard(self, operation: MaintenanceOperation) -> MaintenanceResult:
        """Execute discard operation (combines forget+prune)"""
        print(f"INFO: Executing discard for job '{operation.job_name}'")
        
        start_time = time()
        
        try:
            # Build retention args
            retention_args = self._build_retention_args(operation.retention_config)
            
            # Create forget command (includes --prune)
            command = self._create_restic_command(operation, 'forget', retention_args)
            
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
            command = self._create_restic_command(operation, 'check', check_args)
            
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
    
    def _create_restic_command(self, operation: MaintenanceOperation, command_type: str, args: List[str]) -> List[str]:
        """Create command array for maintenance operation"""
        from models.backup import ResticCommand, CommandType, TransportType
        
        transport = TransportType.SSH if operation.ssh_config else TransportType.LOCAL
        command_type_enum = CommandType.FORGET if command_type == 'forget' else CommandType.CHECK
        
        restic_command = ResticCommand(
            command_type=command_type_enum,
            transport=transport,
            ssh_config=operation.ssh_config,
            repository_url=operation.repository_url,
            args=args,
            environment_vars=operation.environment_vars,
            job_config={'container_runtime': operation.container_runtime}
        )
        
        # Convert to execution format
        if transport == TransportType.SSH:
            return restic_command.to_ssh_command()
        else:
            return restic_command.to_local_command()
    
    def _execute_command(self, command: List[str], job_name: str, operation_type: str) -> str:
        """Execute maintenance command with proper logging and priority"""
        # Add maintenance-specific nice/ionice priority
        cmd_array = self._add_maintenance_priority(command)
        
        # Log the command (with password obfuscation)
        from services.command_obfuscation import CommandObfuscationService
        obfuscated_command = CommandObfuscationService.obfuscate_command_array(cmd_array)
        self.job_management.log_execution(job_name, f"Executing {operation_type}: {' '.join(obfuscated_command)}", 'INFO')
        
        # Execute via subprocess
        try:
            result = subprocess.run(cmd_array, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                self.job_management.log_execution(job_name, f"Maintenance {operation_type} completed successfully", 'INFO')
                if result.stdout.strip():
                    self.job_management.log_execution(job_name, f"Output: {result.stdout.strip()}", 'INFO')
                return result.stdout.strip()
            else:
                error_msg = f"Maintenance {operation_type} failed with exit code {result.returncode}"
                if result.stderr.strip():
                    error_msg += f": {result.stderr.strip()}"
                raise Exception(error_msg)
                
        except subprocess.TimeoutExpired:
            raise Exception(f"Maintenance {operation_type} timed out after 1 hour")
        except Exception as e:
            self.job_management.log_execution(job_name, f"Maintenance {operation_type} error: {str(e)}", 'ERROR')
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


class MaintenanceScheduler:
    """Service for scheduling maintenance operations"""
    
    def __init__(self, backup_config, scheduler_service):
        self.backup_config = backup_config
        self.scheduler_service = scheduler_service
        self.config_manager = MaintenanceConfigManager(backup_config)
        self.operation_factory = MaintenanceOperationFactory(backup_config)
    
    def schedule_job_maintenance(self, job_name: str):
        """Schedule maintenance operations for a job"""
        # Check if maintenance is enabled
        if not self.config_manager.is_maintenance_enabled(job_name):
            print(f"INFO: Auto maintenance disabled for job '{job_name}' - skipping scheduling")
            return
        
        # Schedule discard operation (forget+prune combined)
        self._schedule_discard_operation(job_name)
        
        # Schedule check operation  
        self._schedule_check_operation(job_name)
        
        print(f"INFO: Scheduled maintenance operations for job '{job_name}'")
    
    def unschedule_job_maintenance(self, job_name: str):
        """Remove scheduled maintenance operations for a job"""
        discard_job_id = f"maintenance_discard_{job_name}"
        check_job_id = f"maintenance_check_{job_name}"
        
        self.scheduler_service.remove_job(discard_job_id)
        self.scheduler_service.remove_job(check_job_id)
        
        print(f"INFO: Unscheduled maintenance operations for job '{job_name}'")
    
    def reschedule_job_maintenance(self, job_name: str):
        """Reschedule maintenance operations for a job (remove + add)"""
        self.unschedule_job_maintenance(job_name)
        self.schedule_job_maintenance(job_name)
    
    def _schedule_discard_operation(self, job_name: str):
        """Schedule discard operation for a job (combines forget+prune)"""
        schedule = self.config_manager.get_discard_schedule(job_name)
        timezone = self.backup_config.config.get('global_settings', {}).get('scheduler_timezone', 'UTC')
        
        job_id = f"maintenance_discard_{job_name}"
        
        # Create operation factory function for scheduler
        def execute_discard():
            maintenance_service = ResticMaintenanceService(
                backup_config=self.backup_config,
                scheduler_service=self.scheduler_service
            )
            operation = self.operation_factory.create_discard_operation(job_name)
            maintenance_service.execute_maintenance_operation(operation)
        
        self.scheduler_service.add_crontab_job(
            func=execute_discard,
            job_id=job_id,
            crontab=schedule,
            timezone=timezone
        )
    
    def _schedule_check_operation(self, job_name: str):
        """Schedule check operation for a job"""
        schedule = self.config_manager.get_check_schedule(job_name)
        timezone = self.backup_config.config.get('global_settings', {}).get('scheduler_timezone', 'UTC')
        
        job_id = f"maintenance_check_{job_name}"
        
        # Create operation factory function for scheduler
        def execute_check():
            maintenance_service = ResticMaintenanceService(
                backup_config=self.backup_config,
                scheduler_service=self.scheduler_service
            )
            operation = self.operation_factory.create_check_operation(job_name)
            maintenance_service.execute_maintenance_operation(operation)
        
        self.scheduler_service.add_crontab_job(
            func=execute_check,
            job_id=job_id,
            crontab=schedule,
            timezone=timezone
        )


class ResticMaintenanceService:
    """Main maintenance service that orchestrates all maintenance operations"""
    
    def __init__(self, backup_config, scheduler_service, notification_service=None):
        self.backup_config = backup_config
        self.scheduler_service = scheduler_service
        self.notification_service = notification_service
        self.config_manager = MaintenanceConfigManager(backup_config)
        self.operation_factory = MaintenanceOperationFactory(backup_config)
        self.executor = MaintenanceExecutor()
        self.scheduler = MaintenanceScheduler(backup_config, scheduler_service)
    
    def schedule_job_maintenance(self, job_name: str):
        """Schedule maintenance operations for a job"""
        self.scheduler.schedule_job_maintenance(job_name)
    
    def unschedule_job_maintenance(self, job_name: str):
        """Remove scheduled maintenance operations for a job"""
        self.scheduler.unschedule_job_maintenance(job_name)
    
    def reschedule_job_maintenance(self, job_name: str):
        """Reschedule maintenance operations for a job"""
        self.scheduler.reschedule_job_maintenance(job_name)
    
    def execute_maintenance_operation(self, operation: MaintenanceOperation) -> MaintenanceResult:
        """Execute a maintenance operation"""
        if operation.operation_type == 'discard':
            return self.executor.execute_discard(operation)
        elif operation.operation_type == 'check':
            return self.executor.execute_check(operation)
        else:
            raise ValueError(f"Unknown maintenance operation type: {operation.operation_type}")
    
    def get_maintenance_summary(self, job_name: str) -> Dict[str, Any]:
        """Get maintenance status summary for a job"""
        return self.config_manager.get_maintenance_summary(job_name)


# Bootstrap functions for integration
def bootstrap_maintenance_schedules(backup_config, scheduler_service, notification_service=None) -> int:
    """Bootstrap maintenance schedules for all Restic jobs"""
    maintenance_service = ResticMaintenanceService(
        backup_config=backup_config,
        scheduler_service=scheduler_service,
        notification_service=notification_service
    )
    
    # Schedule maintenance for all eligible jobs
    jobs = backup_config.config.get('backup_jobs', {})
    scheduled_count = 0
    
    for job_name, job_config in jobs.items():
        # Only schedule for Restic jobs with maintenance enabled (auto or user mode)
        maintenance_mode = job_config.get('restic_maintenance', 'auto')
        if (job_config.get('dest_type') == 'restic' and 
            maintenance_mode in ['auto', 'user']):
            
            maintenance_service.schedule_job_maintenance(job_name)
            scheduled_count += 1
    
    print(f"INFO: Maintenance system bootstrap complete - {scheduled_count} jobs scheduled")
    return scheduled_count


def update_job_maintenance_schedule(job_name: str, job_config: dict, backup_config, scheduler_service, notification_service=None):
    """Update maintenance schedule for a single job (called when job is added/modified)"""
    maintenance_service = ResticMaintenanceService(
        backup_config=backup_config,
        scheduler_service=scheduler_service,
        notification_service=notification_service
    )
    
    # Reschedule if it's a Restic job with maintenance enabled, otherwise unschedule
    maintenance_mode = job_config.get('restic_maintenance', 'auto')
    if (job_config.get('dest_type') == 'restic' and 
        maintenance_mode in ['auto', 'user']):
        maintenance_service.reschedule_job_maintenance(job_name)
        print(f"INFO: Updated maintenance schedule for job '{job_name}' (mode: {maintenance_mode})")
    else:
        maintenance_service.unschedule_job_maintenance(job_name)
        print(f"INFO: Unscheduled maintenance for job '{job_name}' (mode: {maintenance_mode})")


def remove_job_maintenance_schedule(job_name: str, backup_config, scheduler_service):
    """Remove maintenance schedule for a job (called when job is deleted)"""
    maintenance_service = ResticMaintenanceService(
        backup_config=backup_config,
        scheduler_service=scheduler_service
    )
    
    maintenance_service.unschedule_job_maintenance(job_name)
    print(f"INFO: Removed maintenance schedule for deleted job '{job_name}'")