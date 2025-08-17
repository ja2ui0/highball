"""
Maintenance scheduler service
Handles scheduling and unscheduling of maintenance operations
"""
from services.maintenance_config_manager import MaintenanceConfigManager
from services.maintenance_operation_factory import MaintenanceOperationFactory


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
            from services.restic_maintenance_service import ResticMaintenanceService
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
            from services.restic_maintenance_service import ResticMaintenanceService
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