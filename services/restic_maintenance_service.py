"""
Restic repository maintenance service
Pure coordinator delegating to specialized maintenance services
"""
from typing import Optional
from services.maintenance_operation import MaintenanceOperation, MaintenanceResult
from services.maintenance_config_manager import MaintenanceConfigManager
from services.maintenance_scheduler import MaintenanceScheduler
from services.maintenance_executor import MaintenanceExecutor
from services.job_conflict_manager import RuntimeConflictManager


class ResticMaintenanceService:
    """Pure coordinator for Restic repository maintenance operations"""
    
    def __init__(self, backup_config, scheduler_service, notification_service: Optional = None):
        self.backup_config = backup_config
        self.scheduler_service = scheduler_service
        self.notification_service = notification_service
        
        # Initialize specialized services
        self.config_manager = MaintenanceConfigManager(backup_config)
        self.scheduler = MaintenanceScheduler(backup_config, scheduler_service)
        self.executor = MaintenanceExecutor()
        self.conflict_manager = RuntimeConflictManager(backup_config)
        
        print("INFO: ResticMaintenanceService initialized")
    
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
        """Execute a maintenance operation with conflict avoidance"""
        print(f"INFO: Starting {operation.operation_type} maintenance for job '{operation.job_name}'")
        
        # Check for conflicts before starting
        if self._should_wait_for_conflicts(operation.job_name):
            print(f"INFO: Waiting for conflicting jobs before running {operation.operation_type} for '{operation.job_name}'")
            # Reschedule for later (5 minutes)
            self._reschedule_maintenance(operation, delay_minutes=5)
            return MaintenanceResult(
                operation_type=operation.operation_type,
                job_name=operation.job_name,
                success=False,
                error_message="Rescheduled due to conflicts"
            )
        
        # Execute the operation
        try:
            if operation.operation_type == 'discard':
                result = self.executor.execute_discard(operation)
            elif operation.operation_type == 'check':
                result = self.executor.execute_check(operation)
            else:
                raise ValueError(f"Unknown maintenance operation type: {operation.operation_type}")
            
            # Handle result
            if result.success:
                print(f"INFO: Completed {operation.operation_type} maintenance for job '{operation.job_name}'")
            else:
                print(f"ERROR: Failed {operation.operation_type} maintenance for job '{operation.job_name}': {result.error_message}")
                
                # Send notification if configured
                if self.notification_service:
                    self.notification_service.send_maintenance_failure_notification(
                        operation.job_name, operation.operation_type, result.error_message
                    )
            
            return result
            
        except Exception as e:
            error_msg = f"Maintenance {operation.operation_type} failed for job '{operation.job_name}': {str(e)}"
            print(f"ERROR: {error_msg}")
            
            # Send notification if configured
            if self.notification_service:
                self.notification_service.send_maintenance_failure_notification(
                    operation.job_name, operation.operation_type, str(e)
                )
            
            return MaintenanceResult(
                operation_type=operation.operation_type,
                job_name=operation.job_name,
                success=False,
                error_message=str(e)
            )
    
    def get_maintenance_summary(self, job_name: str) -> dict:
        """Get maintenance status summary for a job"""
        return self.config_manager.get_maintenance_summary(job_name)
    
    def is_maintenance_enabled(self, job_name: str) -> bool:
        """Check if auto maintenance is enabled for job"""
        return self.config_manager.is_maintenance_enabled(job_name)
    
    def _should_wait_for_conflicts(self, job_name: str) -> bool:
        """Check if maintenance should wait for conflicting jobs"""
        return self.conflict_manager.check_for_conflicts(job_name)
    
    def _reschedule_maintenance(self, operation: MaintenanceOperation, delay_minutes: int = 5):
        """Reschedule maintenance operation for later"""
        import threading
        import time
        
        def delayed_execution():
            time.sleep(delay_minutes * 60)
            self.execute_maintenance_operation(operation)
        
        thread = threading.Thread(target=delayed_execution, daemon=True)
        thread.start()