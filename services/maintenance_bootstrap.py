"""
Maintenance system bootstrap
Integrates maintenance scheduling with app startup and job management
"""
from services.restic_maintenance_service import ResticMaintenanceService


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
        # Only schedule for Restic jobs with auto maintenance enabled
        if (job_config.get('dest_type') == 'restic' and 
            job_config.get('auto_maintenance', True)):
            
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
    
    # Reschedule if it's a Restic job, otherwise unschedule
    if (job_config.get('dest_type') == 'restic' and 
        job_config.get('auto_maintenance', True)):
        maintenance_service.reschedule_job_maintenance(job_name)
        print(f"INFO: Updated maintenance schedule for job '{job_name}'")
    else:
        maintenance_service.unschedule_job_maintenance(job_name)
        print(f"INFO: Unscheduled maintenance for job '{job_name}'")


def remove_job_maintenance_schedule(job_name: str, backup_config, scheduler_service):
    """Remove maintenance schedule for a job (called when job is deleted)"""
    maintenance_service = ResticMaintenanceService(
        backup_config=backup_config,
        scheduler_service=scheduler_service
    )
    
    maintenance_service.unschedule_job_maintenance(job_name)
    print(f"INFO: Removed maintenance schedule for deleted job '{job_name}'")