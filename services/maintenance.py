"""
Unified maintenance service for Restic repository operations
Consolidates all maintenance-related functionality into a single module
"""
import subprocess
from time import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from services.execution import OperationType, ResticExecutionService


# Maintenance defaults
DISCARD_SCHEDULE = "0 3 * * *"
CHECK_SCHEDULE = "0 2 * * 0"
KEEP_LAST = 7
KEEP_HOURLY = 6
KEEP_DAILY = 7
KEEP_WEEKLY = 4
KEEP_MONTHLY = 6
KEEP_YEARLY = 0
CHECK_READ_DATA_SUBSET = "5%"
NICE_LEVEL = 10
IONICE_CLASS = 3
IONICE_LEVEL = 7


class MaintenanceOperation(BaseModel):
    """Represents a maintenance operation to be executed"""
    operation_type: OperationType  # OperationType.DISCARD (forget+prune combined) or OperationType.CHECK
    job_name: str
    repository_url: str
    environment_vars: Dict[str, str]
    ssh_config: Optional[Dict[str, str]] = None
    container_runtime: str = "docker"
    retention_config: Optional[Dict[str, Any]] = None
    check_config: Optional[Dict[str, Any]] = None


class MaintenanceResult(BaseModel):
    """Result of a maintenance operation"""
    operation_type: OperationType
    job_name: str
    success: bool
    duration_seconds: float = 0.0
    output: str = ""
    error_message: Optional[str] = None


class MaintenanceDefaults(BaseModel):
    """Default maintenance parameters following Restic best practices"""
    # Retention policy - keeps reasonable amount while preventing unbounded growth
    KEEP_LAST: int = 7        # always keep last 7 snapshots regardless of age
    KEEP_HOURLY: int = 6      # keep 6 most recent hourly snapshots (6 hours coverage)
    KEEP_DAILY: int = 7       # keep 7 most recent daily snapshots (1 week coverage)
    KEEP_WEEKLY: int = 4      # keep 4 most recent weekly snapshots (1 month coverage)
    KEEP_MONTHLY: int = 6     # keep 6 most recent monthly snapshots (6 months coverage)
    KEEP_YEARLY: int = 0      # disable yearly retention by default
    
    # Scheduling defaults
    DISCARD_SCHEDULE: str = "0 3 * * *"         # daily at 3am - combines forget+prune operations
    CHECK_SCHEDULE: str = "0 2 * * 0"           # weekly Sunday 2am (staggered from backups)
    
    # Check operation defaults
    CHECK_READ_DATA_SUBSET: str = "5%"          # balance integrity vs performance
    
    # Resource priority (lower than backups)
    NICE_LEVEL: int = 10                        # vs backup nice -n 5
    IONICE_CLASS: int = 3                       # idle vs backup ionice -c 2
    IONICE_LEVEL: int = 7                       # vs backup ionice -n 4


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
        return maintenance_settings.get('discard_schedule', DISCARD_SCHEDULE)
    
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
        return maintenance_settings.get('check_schedule', CHECK_SCHEDULE)
    
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
            'keep_last': KEEP_LAST,
            'keep_hourly': KEEP_HOURLY,
            'keep_daily': KEEP_DAILY,
            'keep_weekly': KEEP_WEEKLY,
            'keep_monthly': KEEP_MONTHLY,
            'keep_yearly': KEEP_YEARLY
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
            'read_data_subset': CHECK_READ_DATA_SUBSET
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
        from services.execution import ResticExecutionService
        self.restic_executor = ResticExecutionService()
    
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
    
    def _create_base_operation(self, job_name: str, job_config: Dict[str, Any], operation_type: OperationType) -> MaintenanceOperation:
        """Create base maintenance operation from job config"""
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        # Build repository URL
        repository_url = dest_config.get('repo_uri', dest_config.get('dest_string', ''))
        
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
    


class MaintenanceExecutor:
    """Service for executing maintenance operations"""
    
    def __init__(self):
        from services.management import JobManagementService
        self.job_management = JobManagementService()
        self.restic_executor = ResticExecutionService()
    
    def execute_discard(self, operation: MaintenanceOperation) -> MaintenanceResult:
        """Execute discard operation (combines forget+prune)"""
        print(f"INFO: Executing discard for job '{operation.job_name}'")
        
        start_time = time()
        
        try:
            # Build retention args
            retention_args = self._build_retention_args(operation.retention_config)
            
            # Execute forget command with unified execution service
            command_args = ['forget'] + retention_args + ['--prune']
            dest_config = self._convert_operation_to_dest_config(operation)
            source_config = operation.ssh_config
            
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=command_args,
                source_config=source_config,
                operation_type=OperationType.DISCARD,
                timeout=1800  # 30 minute timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"Discard operation failed: {result.stderr}")
            
            output = result.stdout
            
            duration = time() - start_time
            return MaintenanceResult(
                operation_type=OperationType.DISCARD,
                job_name=operation.job_name,
                success=True,
                duration_seconds=duration,
                output=output
            )
            
        except Exception as e:
            duration = time() - start_time
            return MaintenanceResult(
                operation_type=OperationType.DISCARD,
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
            
            # Execute check command with unified execution service
            command_args = ['check'] + check_args
            dest_config = self._convert_operation_to_dest_config(operation)
            source_config = operation.ssh_config
            
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=command_args,
                source_config=source_config,
                operation_type=OperationType.CHECK,
                timeout=1800  # 30 minute timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"Check operation failed: {result.stderr}")
            
            output = result.stdout
            
            duration = time() - start_time
            return MaintenanceResult(
                operation_type=OperationType.CHECK,
                job_name=operation.job_name,
                success=True,
                duration_seconds=duration,
                output=output
            )
            
        except Exception as e:
            duration = time() - start_time
            return MaintenanceResult(
                operation_type=OperationType.CHECK,
                job_name=operation.job_name,
                success=False,
                duration_seconds=duration,
                error_message=str(e)
            )
    
        except Exception as e:
            self.job_management.log_execution(job_name, f"Maintenance {operation_type} error: {str(e)}", 'ERROR')
            raise
    
    def _add_maintenance_priority(self, command: List[str]) -> List[str]:
        """Add nice/ionice priority for maintenance operations (lower than backups)"""
        return [
            'nice', f'-n', str(NICE_LEVEL),
            'ionice', '-c', str(IONICE_CLASS), '-n', str(IONICE_LEVEL)
        ] + command
    
    def _convert_operation_to_dest_config(self, operation: MaintenanceOperation) -> Dict[str, Any]:
        """Convert maintenance operation to dest_config format for ResticExecutionService"""
        # Extract repository info from repository_url
        repo_uri = operation.repository_url
        
        # Create dest_config with environment variables
        dest_config = {
            'repo_uri': repo_uri,
            'repo_type': 'local',  # Will be determined by ResticExecutionService
        }
        
        # Add environment variables as individual fields
        for env_key, env_value in operation.environment_vars.items():
            if env_key == 'RESTIC_PASSWORD':
                dest_config['password'] = env_value
            elif env_key.startswith('AWS_'):
                # S3 credentials
                if env_key == 'AWS_ACCESS_KEY_ID':
                    dest_config['s3_access_key_id'] = env_value
                elif env_key == 'AWS_SECRET_ACCESS_KEY':
                    dest_config['s3_secret_access_key'] = env_value
            # Add other credential types as needed
        
        return dest_config
    
    def _build_retention_args(self, retention_config: dict) -> List[str]:
        """Build retention arguments for forget command"""
        if not retention_config:
            retention_config = {}
        
        args = ['--prune']  # Always prune after forget
        
        # Use configured values or defaults
        keep_last = retention_config.get('keep_last', KEEP_LAST)
        keep_hourly = retention_config.get('keep_hourly', KEEP_HOURLY)
        keep_daily = retention_config.get('keep_daily', KEEP_DAILY)
        keep_weekly = retention_config.get('keep_weekly', KEEP_WEEKLY)
        keep_monthly = retention_config.get('keep_monthly', KEEP_MONTHLY)
        keep_yearly = retention_config.get('keep_yearly', KEEP_YEARLY)
        
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
        read_data_subset = check_config.get('read_data_subset', '5%')
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
    
    def schedule_job_maintenance(self, job_name: str) -> None:
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
    
    def unschedule_job_maintenance(self, job_name: str) -> None:
        """Remove scheduled maintenance operations for a job"""
        discard_job_id = f"maintenance_discard_{job_name}"
        check_job_id = f"maintenance_check_{job_name}"
        
        self.scheduler_service.remove_job(discard_job_id)
        self.scheduler_service.remove_job(check_job_id)
        
        print(f"INFO: Unscheduled maintenance operations for job '{job_name}'")
    
    def reschedule_job_maintenance(self, job_name: str) -> None:
        """Reschedule maintenance operations for a job (remove + add)"""
        self.unschedule_job_maintenance(job_name)
        self.schedule_job_maintenance(job_name)
    
    def _schedule_discard_operation(self, job_name: str):
        """Schedule discard operation for a job (combines forget+prune)"""
        schedule = self.config_manager.get_discard_schedule(job_name)
        timezone = self.backup_config.config.get('global_settings', {}).get('scheduler_timezone', 'UTC')
        
        job_id = f"maintenance_discard_{job_name}"
        
        # Create operation factory function for scheduler
        def execute_discard() -> None:
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
        def execute_check() -> None:
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
    
    def schedule_job_maintenance(self, job_name: str) -> None:
        """Schedule maintenance operations for a job"""
        self.scheduler.schedule_job_maintenance(job_name)
    
    def unschedule_job_maintenance(self, job_name: str) -> None:
        """Remove scheduled maintenance operations for a job"""
        self.scheduler.unschedule_job_maintenance(job_name)
    
    def reschedule_job_maintenance(self, job_name: str) -> None:
        """Reschedule maintenance operations for a job"""
        self.scheduler.reschedule_job_maintenance(job_name)
    
    def execute_maintenance_operation(self, operation: MaintenanceOperation) -> MaintenanceResult:
        """Execute a maintenance operation"""
        if operation.operation_type == OperationType.DISCARD:
            return self.executor.execute_discard(operation)
        elif operation.operation_type == OperationType.CHECK:
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


def update_job_maintenance_schedule(job_name: str, job_config: Dict[str, Any], backup_config: Any, scheduler_service: Any, notification_service: Optional[Any] = None) -> None:
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


def remove_job_maintenance_schedule(job_name: str, backup_config: Any, scheduler_service: Any) -> None:
    """Remove maintenance schedule for a job (called when job is deleted)"""
    maintenance_service = ResticMaintenanceService(
        backup_config=backup_config,
        scheduler_service=scheduler_service
    )
    
    maintenance_service.unschedule_job_maintenance(job_name)
    print(f"INFO: Removed maintenance schedule for deleted job '{job_name}'")