#!/usr/bin/env python3
"""
Jobs Domain Views Handler
GET operations for job management
"""
from typing import Dict, Any
from fastapi.responses import JSONResponse, HTMLResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler

from jobs.services.config import JobConfigService
from jobs.services.define import JobDisplayBuilder
from jobs.services.schedule import SchedulingService, JobSchedulerHandler
from jobs.services.restore import RestoreService


class JobViewsHandler(BaseHandler):
    """Handler for job view operations (GET)"""

    def __init__(self):
        super().__init__()
        self.template_service = TemplateService()
        self.job_config = JobConfigService()
        self.display_builder = JobDisplayBuilder(self.template_service)
        self.scheduler_service = SchedulingService()
        self.restore_service = RestoreService()

    # =========================================================================
    # DASHBOARD AND NAVIGATION
    # =========================================================================

    @handle_page_errors("Show dashboard")
    def show_dashboard(self) -> HTMLResponse:
        """Display main jobs dashboard"""
        # Get dashboard data from service
        dashboard_data = self.display_builder.build_dashboard_display_data()

        # Render dashboard template
        html_response = self.template_service.render_template('pages/dashboard.html', **dashboard_data)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Show add job form")
    def show_add_job_form(self) -> HTMLResponse:
        """Display add job form"""
        # Get form data from service
        form_data = self.display_builder.build_add_job_form_data()

        # Render add job form template
        html_response = self.template_service.render_template('pages/job_form.html', **form_data)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Show edit job form")
    def show_edit_job_form(self, job_name: str) -> HTMLResponse:
        """Display edit job form for specified job"""
        if not job_name:
            # No job name provided - return error
            return JSONResponse(
                content={"success": False, "error": "Job name is required"},
                status_code=400
            )

        # Get job configuration and form data
        form_data = self.display_builder.build_edit_job_form_data(job_name)

        if not form_data.get('found', True):
            # Job not found - return error for API/direct access
            return JSONResponse(
                content={"success": False, "error": form_data.get('error', f"Job '{job_name}' not found")},
                status_code=404
            )

        # Render edit job form template
        html_response = self.template_service.render_template('pages/job_form.html', **form_data['form_data'])
        return HTMLResponse(content=html_response)

    @handle_page_errors("Show job inspect")
    def show_job_inspect(self, job_name: str = "") -> HTMLResponse:
        """Display job inspection interface"""
        # Get inspection data from service
        inspect_data = self.display_builder.build_job_inspect_data(job_name)

        # Render job inspect template
        html_response = self.template_service.render_template('pages/job_inspect.html', **inspect_data)
        return HTMLResponse(content=html_response)

    # =========================================================================
    # BROWSE AND EXPLORE OPERATIONS
    # =========================================================================

    @handle_page_errors("Browse filesystem")
    def browse_filesystem(self, path: str = '/') -> JSONResponse:
        """Browse filesystem for source path selection"""
        # Delegate to service for filesystem browsing
        result = self.restore_service.browse_filesystem_path(path)
        return JSONResponse(content=result)

    # =========================================================================
    # SCHEDULER OPERATIONS
    # =========================================================================

    @handle_page_errors("List scheduler jobs")
    def list_scheduler_jobs(self) -> JSONResponse:
        """List all scheduled jobs from APScheduler"""
        # Get scheduler job list from service
        job_scheduler = JobSchedulerHandler(self.scheduler_service)
        result = job_scheduler.list_jobs()
        return JSONResponse(content=result)

    # =========================================================================
    # REPOSITORY OPERATIONS
    # =========================================================================

    @handle_page_errors("Check repository availability")
    def check_repository_availability(self, job_name: str) -> HTMLResponse:
        """Check repository availability for job - simplified"""
        if not job_name:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               error_message='Job name is required')
            return HTMLResponse(content=html_response)

        # Get job config to find destination
        result = self.display_builder.get_job_config_for_repository_check(job_name)
        if not result['found']:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               error_message=result['error'])
            return HTMLResponse(content=html_response)

        # Use ConfigReader to check if destination exists
        from shared.services.config import ConfigReader
        config_reader = ConfigReader()
        destinations = config_reader.get_destinations()

        job_config = result['job_config']
        dest_name = job_config.get('destination')

        if dest_name and dest_name in destinations:
            dest_config = destinations[dest_name]
            if dest_config.get('repo_type'):  # Restic destination
                status_message = f"Repository '{dest_name}' is available"
                html_response = self.template_service.render_template('partials/success_message.html',
                                                                   success_message=status_message)
            else:
                html_response = self.template_service.render_template('partials/error_message.html',
                                                                   error_message='Destination is not a restic repository')
        else:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               error_message=f'Destination "{dest_name}" not found')

        return HTMLResponse(content=html_response)


# Export instance for consistent naming pattern
jobs_views = JobViewsHandler()