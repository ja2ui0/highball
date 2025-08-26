"""
Jobs Page Handlers
Job management, inspection, and execution monitoring
"""

import logging
from typing import Dict, Any, Callable, List
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from services.template import TemplateService
from config import BackupConfig

logger = logging.getLogger(__name__)

def handle_page_errors(operation_name: str) -> Callable:
    """Decorator to handle common page operation errors consistently"""
    def decorator(func: Callable) -> Callable:
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"{operation_name} error: {e}")
                return JSONResponse(content={
                    'success': False,
                    'error': str(e)
                }, status_code=500)
        return wrapper
    return decorator

class BaseHandler:
    """Base class for handlers with shared rendering helpers"""
    
    def _render_html(self, template: str, context: dict) -> HTMLResponse:
        """Helper to render template and return HTMLResponse"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html)
    
    def _render_error(self, template: str, context: dict, status: int = 400) -> HTMLResponse:
        """Helper to render error template and return HTMLResponse with status"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html, status_code=status)

class JobsHandler(BaseHandler):
    """Handle job management and inspection"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.backup_config = BackupConfig()
    
    @handle_page_errors("Job inspect")
    def show_job_inspect(self, job_name: str = "") -> HTMLResponse:
        """Show job inspection page"""
        if not job_name:
            return self._render_error('partials/error_page.html', {
                'error_message': "Job name is required", 
                'page_title': "Error"
            }, 400)
        
        jobs = self.backup_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_error('partials/error_page.html', {
                'error_message': f"Job '{job_name}' not found", 
                'page_title': "Error"
            }, 404)
        
        job_config = jobs[job_name]
        
        # Get job status and logs
        from services.management import JobManagementService
        job_management = JobManagementService(self.backup_config)
        status_info = job_management.get_status(job_name)
        recent_logs = job_management.get_log_entries(job_name, max_lines=100)
        
        # Format log content as string
        job_log_content = '\n'.join(recent_logs) if recent_logs else f'No log file yet for job "{job_name}". Job has not been executed (test or run) since creation.'
        
        template_data = {
            'job_name': job_name,
            'job_type': job_config.get('dest_type', 'unknown'),
            'last_run': status_info.get('last_updated', 'Never'), 
            'status': status_info.get('status', 'No runs'),
            'message': status_info.get('details', 'No message'),
            'job_log_content': job_log_content
        }
        
        return self._render_html('pages/job_inspect.html', template_data)

    def _build_job_config_from_result(self, job_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build job configuration from parsed form result"""
        job_config = {
            'source_type': job_result['source_type'],
            'source_config': job_result['source_config'],
            'dest_type': job_result['dest_type'],
            'dest_config': job_result['dest_config'],
            'schedule': job_result['schedule'],
            'enabled': job_result['enabled'],
            'respect_conflicts': job_result['respect_conflicts'],
            'notifications': job_result['notifications']
        }
        
        # Add maintenance config if present
        if 'maintenance_config' in job_result:
            job_config['maintenance_config'] = job_result['maintenance_config']
            
        return job_config

    @handle_page_errors("Save job")
    def save_backup_job(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save backup job from form submission"""
        from models.forms import job_parser
        
        # Parse job form data using unified parser
        job_result = job_parser.parse_job_form(form_data)
        
        if not job_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': job_result['error']
            }, status_code=400)
        
        # Build and save job configuration
        job_name = job_result['job_name']
        job_config = self._build_job_config_from_result(job_result)
        
        # Save to config
        success = self.backup_config.save_job(job_name, job_config)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': 'Failed to save job configuration'
            }, status_code=500)

    @handle_page_errors("Delete job")
    def delete_backup_job(self, job_name: str) -> JSONResponse:
        """Delete backup job"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.backup_config.delete_backup_job(job_name)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to delete job '{job_name}'"
            }, status_code=500)

    @handle_page_errors("Purge job")
    def purge_backup_job(self, job_name: str) -> JSONResponse:
        """Permanently purge backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.backup_config.purge_job(job_name)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to purge job '{job_name}'"
            }, status_code=500)

    @handle_page_errors("Restore job")
    def restore_backup_job(self, job_name: str) -> JSONResponse:
        """Restore backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.backup_config.restore_deleted_job(job_name)
        
        if success:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': f"Failed to restore job '{job_name}'"
            }, status_code=500)

    @handle_page_errors("Path validation")
    def validate_source_paths(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Validate source paths from form"""
        # Parse source paths from form
        from models.forms import source_paths_parser
        paths_result = source_paths_parser.parse_multi_path_options(form_data)
        
        if not paths_result['valid']:
            return JSONResponse(content=paths_result)
        
        # Build SSH configuration and validate paths
        source_type = form_data.get('source_type', ['local'])[0]
        ssh_config = self._build_ssh_config_from_form(form_data) if source_type == 'ssh' else {}
        validation_results = self._validate_individual_paths(source_type, paths_result['source_paths'], ssh_config)
        
        return JSONResponse(content={
            'valid': True,
            'results': validation_results
        })

    def _build_ssh_config_from_form(self, form_data: Dict[str, Any]) -> Dict[str, str]:
        """Build SSH configuration from form data"""
        hostname = form_data.get('hostname', [''])[0]
        username = form_data.get('username', [''])[0]
        return {'hostname': hostname, 'username': username}

    def _validate_individual_paths(self, source_type: str, source_paths: List[Dict[str, Any]], ssh_config: Dict[str, str]) -> List[Dict[str, Any]]:
        """Validate each individual source path"""
        from jobs.services.validate import ValidationService
        validation_service = ValidationService()
        
        validation_results = []
        for path_config in source_paths:
            if source_type == 'ssh':
                result = validation_service.validate_source_path(ssh_config, path_config['path'])
            else:
                result = validation_service.validate_source_path({}, path_config['path'])
            
            validation_results.append({
                'path': path_config['path'],
                'valid': result['valid'],
                'error': result.get('error'),
                'permissions': result.get('permissions')
            })
        
        return validation_results

# Global handler instance
jobs_handler = JobsHandler()