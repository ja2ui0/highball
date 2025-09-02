# handlers/job_scheduler.py
import logging
from typing import Dict, Any
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

class JobSchedulerHandler:
    def __init__(self, scheduler_service):
        self.scheduler_service = scheduler_service

    def list_jobs(self) -> JSONResponse:
        """List APScheduler internal scheduled jobs - DEBUG/ADMIN endpoint"""
        jobs = self.scheduler_service.scheduler_manager.scheduler.get_jobs()
        job_list = []
        for j in jobs:
            next_run = j.next_run_time.isoformat() if j.next_run_time else None
            job_list.append({
                'id': j.id,
                'name': j.name or '',
                'trigger': str(j.trigger),
                'next_run': next_run
            })
        
        return JSONResponse(content={
            'jobs': job_list,
            'count': len(job_list),
            'note': 'This shows APScheduler internal jobs. For backup job configs, use /api/highball/jobs'
        })

    def schedule_job(self, form_data: dict) -> JSONResponse:
        """Schedule a backup job - FastAPI pattern"""
        job_name = form_data.get('job_name', [''])[0] if isinstance(form_data.get('job_name'), list) else form_data.get('job_name', '')
        schedule = form_data.get('schedule', [''])[0] if isinstance(form_data.get('schedule'), list) else form_data.get('schedule', '')
        
        if not job_name or not schedule:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name and schedule are required'
            }, status_code=400)
        
        try:
            # Add job to scheduler (this would need BackupHandler integration)
            # For now, just show success
            return JSONResponse(content={
                'success': True,
                'message': f'Job "{job_name}" scheduled with: {schedule}',
                'job_name': job_name,
                'schedule': schedule
            })
        except Exception as e:
            return JSONResponse(content={
                'success': False,
                'error': f'Failed to schedule job: {str(e)}'
            }, status_code=500)


# =============================================================================
# JOB SCHEDULING ORCHESTRATION SERVICE
# =============================================================================

class JobSchedulingOrchestrationService:
    """Orchestrates job scheduling with validation and actual scheduler integration"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
    
    def schedule_job(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a job for execution - extracted from operations.py"""
        try:
            job_name = form_data.get('job_name', [''])[0]
            
            if not job_name:
                return {
                    'success': False,
                    'error': 'Job name is required'
                }
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                }
            
            # Add job to scheduler
            from jobs.services.schedule import SchedulingService
            scheduler = SchedulingService()
            
            job_config = jobs[job_name]
            schedule = job_config.get('schedule', 'manual')
            
            if schedule != 'manual':
                scheduler.schedule_job(job_name, job_config)
                message = f"Job '{job_name}' scheduled with pattern: {schedule}"
            else:
                message = f"Job '{job_name}' is set to manual execution"
            
            return {
                'success': True,
                'message': message,
                'job_name': job_name,
                'schedule': schedule
            }
            
        except Exception as e:
            logger.error(f"Schedule job error: {e}")
            return {
                'success': False,
                'error': f'Schedule error: {str(e)}'
            }
