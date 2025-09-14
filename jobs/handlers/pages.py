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
from jobs.services.define import JobFormDataBuilder, JobFormTemplateBuilder, JobDisplayBuilder
from jobs.services.notify import NotificationFormDataBuilder
from jobs.services.schedule import ScheduleFormDataBuilder, SchedulingService, JobSchedulerHandler
from jobs.services.validate import ValidationRenderingService, ValidationService
from jobs.services.restore import RestoreOperationsService, RestoreService
from jobs.services.backup import BackupOrchestrationService, backup_service
from shared.services.config import ConfigReader
from dests.services.kinds import DestinationTypeService
from jobs.handlers.old import JobFormParser
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
        self.backup_orchestration = BackupOrchestrationService(self.job_config)

        # Initialize display and form services with template service
        self.validation_renderer = ValidationRenderingService(self.template_service)
        self.display_builder = JobDisplayBuilder(self.template_service)
        self.restore_ops = RestoreOperationsService()
        self.restore_service = RestoreService()
        self.scheduler_service = SchedulingService()
    
    # Validation rendering moved to ValidationRenderingService
    
    # Job row building moved to JobDisplayBuilder service
    
    # =========================================================================
    # PAGE HANDLERS
    # =========================================================================
    
    @handle_page_errors("Dashboard")
    def show_dashboard(self) -> HTMLResponse:
        """Show main dashboard with job list - thin wrapper"""
        dashboard_data = self.display_builder.build_dashboard_display_data()

        template_data = {
            'job_rows': dashboard_data['job_rows'],
            'deleted_job_rows': dashboard_data['deleted_job_rows'],
            'global_settings': dashboard_data['global_settings'],
            'page_title': 'Dashboard'
        }

        return self._render_html('pages/dashboard.html', template_data)


    @handle_page_errors("Add job form")
    def show_add_job_form(self) -> HTMLResponse:
        """Show add job form - thin wrapper"""
        # Delegate to define service for complete form building
        form_data = self.display_builder.build_add_job_form_data()

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
        result = self.display_builder.build_edit_job_form_data(job_name)

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
        result = self.display_builder.build_job_inspect_data(job_name)

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
        """Delete backup job - thin wrapper"""
        result = self.job_config.delete_backup_job_with_response(job_name)

        if result['type'] == 'redirect':
            return RedirectResponse(url=result['url'], status_code=result['status_code'])
        else:
            return JSONResponse(content=result['content'], status_code=result['status_code'])

    @handle_page_errors("Purge job")
    def purge_backup_job(self, job_name: str) -> JSONResponse:
        """Permanently purge backup job from deleted jobs - thin wrapper"""
        result = self.job_config.purge_backup_job_with_response(job_name)

        if result['type'] == 'redirect':
            return RedirectResponse(url=result['url'], status_code=result['status_code'])
        else:
            return JSONResponse(content=result['content'], status_code=result['status_code'])

    @handle_page_errors("Restore job")
    def restore_backup_job(self, job_name: str) -> JSONResponse:
        """Restore backup job from deleted jobs - thin wrapper"""
        result = self.job_config.restore_backup_job_with_response(job_name)

        if result['type'] == 'redirect':
            return RedirectResponse(url=result['url'], status_code=result['status_code'])
        else:
            return JSONResponse(content=result['content'], status_code=result['status_code'])

    @handle_page_errors("Path validation")
    def validate_source_paths(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Validate source paths from form - thin handler, delegates to service"""
        # Delegate business logic to service
        result = self.job_config.validate_source_paths_from_form(form_data)
        return JSONResponse(content=result)

    @handle_page_errors("Process restore")
    def process_restore_request(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Process restore request from form - thin handler, delegates to service"""
        # Delegate business logic to service
        result = self.restore_ops.process_restore_request_from_form(form_data)
        return JSONResponse(content=result)











    # =============================================================================
    # RESTORE OPERATIONS - Extracted from mega-dispatcher
    # =============================================================================




    @handle_page_errors("Browse filesystem")
    def browse_filesystem(self, path: str = '/') -> JSONResponse:
        """Browse local filesystem for path selection - delegate to restore service"""
        result = self.restore_service.browse_filesystem_path(path)
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
        result = self.scheduler_service.schedule_job_from_form(form_data)
        return JSONResponse(content=result)

    @handle_page_errors("List scheduler jobs")
    def list_scheduler_jobs(self) -> JSONResponse:
        """List APScheduler internal jobs - DEBUG/ADMIN endpoint"""
        job_scheduler = JobSchedulerHandler(self.scheduler_service)
        result = job_scheduler.list_jobs()
        return JSONResponse(content=result)

# Global handler instance
jobs_handler = JobsHandler()