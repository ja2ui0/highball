"""
Jobs Page Handlers
Job management, inspection, and execution monitoring
"""

import html
import logging
from typing import Dict, Any, Callable, List
from pathlib import Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from jobs.services.config import JobConfigService
from jobs.services.manage import JobOperationsService, JobManagementService
from jobs.services.define import JobFormDataBuilder, JobFormTemplateBuilder
from jobs.services.notify import NotificationFormDataBuilder
from jobs.services.schedule import ScheduleFormDataBuilder
from shared.services.config import ConfigReader
from dests.services.kinds import DestinationTypeService
from jobs.handlers.old import JobFormParser
from jobs.services.validate import ValidationService
from jobs.services.backup import backup_service
from jobs.services.restore import RestoreService
from jobs.services.schedule import SchedulingService, JobSchedulerHandler
from models.forms import safe_get_value, safe_get_list, parse_lines

logger = logging.getLogger(__name__)


# =============================================================================
# JOB FORM PARSERS
# =============================================================================





class JobsHandler(BaseHandler):
    """Handle job management and inspection"""
    
    def __init__(self):
        self.job_config = JobConfigService()
        self.config_reader = ConfigReader()
        self._init_template_service()

        # Initialize service orchestrators (moved from operations handler)
        self.job_operations = JobOperationsService()
    
    # =========================================================================
    # VALIDATION RENDERING (moved from services/template.py)
    # =========================================================================
    
    def render_source_path_validation_status(self, result: Dict[str, Any]) -> str:
        """Render source path validation status - thin wrapper"""
        from jobs.services.validate import ValidationRenderingService
        renderer = ValidationRenderingService(self.template_service)
        return renderer.render_source_path_validation_status(result)
    
    # =========================================================================
    # JOB ROW BUILDING (moved from services/template.py)
    # =========================================================================
    
    def _build_job_rows(self, jobs):
        """Build job table rows from job data - thin wrapper"""
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        return display_builder.build_job_rows(jobs)

    def _build_deleted_job_rows(self, deleted_jobs):
        """Build deleted job table rows from deleted jobs data - thin wrapper"""
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        return display_builder.build_deleted_job_rows(deleted_jobs)
    
    # =========================================================================
    # PAGE HANDLERS
    # =========================================================================
    
    @handle_page_errors("Dashboard")
    def show_dashboard(self) -> HTMLResponse:
        """Show main dashboard with job list - thin wrapper"""
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        dashboard_data = display_builder.build_dashboard_display_data()

        template_data = {
            'job_rows': dashboard_data['job_rows'],
            'deleted_job_rows': dashboard_data['deleted_job_rows'],
            'global_settings': dashboard_data['global_settings'],
            'page_title': 'Dashboard'
        }

        return self._render_html('pages/dashboard.html', template_data)

    def _build_source_display_with_type(self, job_config):
        """Build source display string with type prefix - thin wrapper"""
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        return display_builder.build_source_display_with_type(job_config)

    def _build_dest_display_with_type(self, job_config):
        """Build destination display string with type prefix - thin wrapper"""
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        return display_builder.build_dest_display_with_type(job_config)

    @handle_page_errors("Add job form")
    def show_add_job_form(self) -> HTMLResponse:
        """Show add job form - thin wrapper"""
        # Delegate to define service for complete form building
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        form_data = display_builder.build_add_job_form_data()

        return self._render_html('pages/job_form.html', form_data)

    @handle_page_errors("Edit job form")
    def show_edit_job_form(self, job_name: str) -> HTMLResponse:
        """Show edit job form - thin wrapper"""
        if not job_name:
            return self._render_error('partials/error_page.html', {
                'error_message': "Job name is required",
                'page_title': "Error"
            }, 400)

        # Delegate to define service for complete form building
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        result = display_builder.build_edit_job_form_data(job_name)

        if not result['found']:
            return self._render_error('partials/error_page.html', {
                'error_message': result['error'],
                'page_title': "Error"
            }, 404)

        return self._render_html('pages/job_form.html', result['form_data'])


    @handle_page_errors("Job inspect")
    def show_job_inspect(self, job_name: str = "") -> HTMLResponse:
        """Show job inspection page - thin wrapper"""
        if not job_name:
            return self._render_error('partials/error_page.html', {
                'error_message': "Job name is required",
                'page_title': "Error"
            }, 400)

        # Delegate to define service for complete inspection data building
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        result = display_builder.build_job_inspect_data(job_name)

        if not result['found']:
            return self._render_error('partials/error_page.html', {
                'error_message': result['error'],
                'page_title': "Error"
            }, 404)

        return self._render_html('pages/job_inspect.html', result['template_data'])


    @handle_page_errors("Save job")
    def save_backup_job(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save backup job from form submission - thin handler, delegates to service"""
        # Delegate business logic to service
        result = self.job_config.save_backup_job_from_form(form_data)

        # Handle presentation concern - return appropriate response type
        if result['type'] == 'redirect':
            return RedirectResponse(url=result['url'], status_code=result['status_code'])
        else:
            return JSONResponse(content=result['content'], status_code=result['status_code'])

    @handle_page_errors("Delete job")
    def delete_backup_job(self, job_name: str) -> JSONResponse:
        """Delete backup job"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.job_config.delete_backup_job(job_name)
        if success:
            result = {'success': True, 'message': f"Job '{job_name}' deleted successfully"}
        else:
            result = {'success': False, 'error': f"Failed to delete job '{job_name}'"}
        
        if result['success']:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("Purge job")
    def purge_backup_job(self, job_name: str) -> JSONResponse:
        """Permanently purge backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.job_config.purge_job(job_name)
        if success:
            result = {'success': True, 'message': f"Job '{job_name}' permanently purged"}
        else:
            result = {'success': False, 'error': f"Failed to purge job '{job_name}'"}
        
        if result['success']:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("Restore job")
    def restore_backup_job(self, job_name: str) -> JSONResponse:
        """Restore backup job from deleted jobs"""
        
        if not job_name:
            return JSONResponse(content={
                'success': False,
                'error': 'Job name is required'
            }, status_code=400)
        
        success = self.job_config.restore_deleted_job(job_name)
        if success:
            result = {'success': True, 'message': f"Job '{job_name}' restored successfully"}
        else:
            result = {'success': False, 'error': f"Failed to restore job '{job_name}'"}
        
        if result['success']:
            return RedirectResponse(url='/dashboard', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    @handle_page_errors("Path validation")
    def validate_source_paths(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Validate source paths from form - thin handler, delegates to service"""
        # Delegate business logic to service
        result = self.job_config.validate_source_paths_from_form(form_data)
        return JSONResponse(content=result)

    @handle_page_errors("Process restore")
    def process_restore_request(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Process restore request from form - thin handler, delegates to service"""
        from jobs.services.restore import RestoreOperationsService
        # Delegate business logic to service
        restore_ops = RestoreOperationsService()
        result = restore_ops.process_restore_request_from_form(form_data)
        return JSONResponse(content=result)


    def _check_and_respond_repository_status_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check repository availability and return appropriate HTMX HTML response - thin wrapper"""
        from jobs.services.define import JobDisplayBuilder
        display_builder = JobDisplayBuilder(self.template_service)
        response_data = display_builder.check_repository_status_and_build_response(job_name, job_config)

        return self._render_html(response_data['template'], response_data['data'])






    def _get_enabled_global_providers(self):
        """Get list of globally enabled notification providers - thin wrapper"""
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.config_reader)
        return form_builder.get_enabled_global_providers()

    def _render_notification_provider(self, config, index, provider_id=None):
        """Render a single notification provider configuration - thin wrapper"""
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.config_reader)
        return form_builder.render_notification_provider(config, index, provider_id)

    def _render_provider_selection(self, available_providers):
        """Render provider selection dropdown - thin wrapper"""
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.config_reader)
        if not hasattr(self, 'configured_providers'):
            self.configured_providers = []
        form_builder.configured_providers = self.configured_providers
        return form_builder.render_provider_selection(available_providers)

    def _get_form_providers(self, form_data):
        """Get currently configured providers from form data - thin wrapper"""
        return self.job_config._get_form_providers(form_data)



    # =============================================================================
    # RESTORE OPERATIONS - Extracted from mega-dispatcher
    # =============================================================================




    @handle_page_errors("Browse filesystem")
    def browse_filesystem(self, path: str = '/') -> JSONResponse:
        """Browse local filesystem for path selection - delegate to restore service"""
        restore_service = RestoreService()
        result = restore_service.browse_filesystem_path(path)
        return JSONResponse(content=result)


    # =============================================================================
    # DIRECT ORCHESTRATION METHODS (moved from operations handler)
    # =============================================================================
    
    @handle_page_errors("Run backup direct")
    def run_backup_job_direct(self, job_name: str, dry_run: bool = False) -> JSONResponse:
        """Execute backup job with full orchestration - moved from operations handler"""
        result = self.backup_orchestration.run_backup_job(job_name, dry_run)
        return JSONResponse(content=result)
    
    @handle_page_errors("Schedule job direct")
    def schedule_job_direct(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Schedule a job for execution - thin wrapper"""
        from jobs.services.schedule import SchedulingService
        scheduler_service = SchedulingService()
        result = scheduler_service.schedule_job_from_form(form_data)
        return JSONResponse(content=result)

    @handle_page_errors("List scheduler jobs")
    def list_scheduler_jobs(self) -> JSONResponse:
        """List APScheduler internal jobs - DEBUG/ADMIN endpoint"""
        scheduler_service = SchedulingService()
        job_scheduler = JobSchedulerHandler(scheduler_service)
        result = job_scheduler.list_jobs()
        return JSONResponse(content=result)

# Global handler instance
jobs_handler = JobsHandler()