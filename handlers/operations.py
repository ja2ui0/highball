"""
Consolidated Operations Handler
Merges all backup and restore operation handlers into single module
Replaces: backup.py, backup_executor.py, backup_command_builder.py, backup_conflict_handler.py,
         backup_notification_dispatcher.py, restore_handler.py
"""

import logging
from typing import Dict, Any

# FastAPI imports
from fastapi.responses import JSONResponse

# Import unified models
from jobs.services.backup import backup_service, ResticArgumentBuilder, BackupOrchestrationService
from jobs.services.scheduler import JobSchedulingOrchestrationService
from dests.services.rsync import rsync_service
from jobs.services.notify import create_notification_service

# Import services
from services.management import JobManagementService
from services.execution import OperationType

logger = logging.getLogger(__name__)

class OperationsHandler:
    """Unified handler for all backup and restore operations"""
    
    def __init__(self, backup_config, template_service):
        self.backup_config = backup_config
        self.template_service = template_service
        self.job_management = JobManagementService(backup_config)
        self.notification_service = create_notification_service(backup_config.get_global_settings())
        self.backup_orchestration = BackupOrchestrationService(backup_config)
        self.scheduling_orchestration = JobSchedulingOrchestrationService(backup_config)
    
    # =============================================================================
    # BACKUP OPERATIONS
    # =============================================================================
    
    def run_backup_job(self, job_name: str, dry_run: bool = False) -> JSONResponse:
        """Execute backup job with full orchestration"""
        result = self.backup_orchestration.run_backup_job(job_name, dry_run)
        return JSONResponse(content=result)
    
    
    # =============================================================================
    # JOB SCHEDULING
    # =============================================================================
    
    def schedule_job(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Schedule a job for execution"""
        result = self.scheduling_orchestration.schedule_job(form_data)
        return JSONResponse(content=result)
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    # All operations methods now return JSONResponse directly - no utility methods needed