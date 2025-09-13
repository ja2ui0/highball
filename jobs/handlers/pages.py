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
        """Render source path validation status (basic validation, no special SSH details)"""
        return self._render_validation_status_template(result, [])
    
    def _render_validation_status_template(self, result: Dict[str, Any], details: List[str]) -> str:
        """Render validation status using template with consistent formatting"""
        # Determine status class and label
        if result.get('valid', False):
            status_class = 'success'
            status_label = '[OK]'
        else:
            status_class = 'error'
            status_label = '[ERROR]'
        
        # Build message from details or error
        if details:
            # Pass details as a list for proper formatting in template
            message = None
        else:
            # Use appropriate message based on validation result
            if result.get('valid', False):
                message = result.get('message', 'Validation successful')
            else:
                message = result.get('error', 'Validation failed')
            details = None
        
        # Use Jinja2 template to render the result
        return self.template_service.render_template('partials/validation_result.html', 
                                   status_class=status_class,
                                   status_label=status_label,
                                   message=message,
                                   details=details)
    
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
        """Show main dashboard with job list"""
        jobs = self.job_config.get_backup_jobs()
        global_settings = self.config_reader.get_global_settings()
        
        # Get job status information
        job_management = JobManagementService()
        
        job_list = []
        for job_name, job_config in jobs.items():
            # Use enabled/disabled status like original, not execution status
            enabled = job_config.get('enabled', True)
            status = "enabled" if enabled else "disabled"
            status_class = "status-success" if enabled else "status-error"
            
            # Build display strings with type prefixes like original
            source_display = self._build_source_display_with_type(job_config)
            dest_display = self._build_dest_display_with_type(job_config)
            
            job_display = {
                'name': job_name,
                'source_display': source_display,
                'dest_display': dest_display,
                'status': status.capitalize(),
                'status_class': status_class,
                'schedule': job_config.get('schedule', 'manual')
            }
            job_list.append(job_display)
        
        # Sort jobs by name
        job_list.sort(key=lambda j: j['name'])
        
        # Build job and deleted job HTML using local methods (moved from template service)
        job_rows = self._build_job_rows(job_list)
        deleted_jobs = self.job_config.get_deleted_jobs()
        deleted_job_rows = self._build_deleted_job_rows(deleted_jobs)
        
        template_data = {
            'job_rows': job_rows,
            'deleted_job_rows': deleted_job_rows,
            'global_settings': global_settings,
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
        """Show add job form"""
        job_form_builder = JobFormDataBuilder()
        
        form_data = job_form_builder.build_empty_form_data()
        form_data['page_title'] = 'Add Job'
        form_data['form_title'] = 'Add New Backup Job'
        form_data['submit_button_text'] = 'Create Job'
        
        # Add available destination types
        destination_service = DestinationTypeService()
        form_data['available_destination_types'] = destination_service.get_available_destination_types()
        
        # Add notification configuration
        form_data.update(self._build_notification_form_data([]))
        
        # Add schedule configuration
        form_data.update(self._build_schedule_form_data({}))
        
        return self._render_html('pages/job_form.html', form_data)

    @handle_page_errors("Edit job form")
    def show_edit_job_form(self, job_name: str) -> HTMLResponse:
        """Show edit job form"""
        job_form_builder = JobFormDataBuilder()
        
        if not job_name:
            return self._render_error('partials/error_page.html', {
                'error_message': "Job name is required", 
                'page_title': "Error"
            }, 400)
        
        jobs = self.job_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_error('partials/error_page.html', {
                'error_message': f"Job '{job_name}' not found", 
                'page_title': "Error"
            }, 404)
        
        job_config = jobs[job_name]
        form_data = job_form_builder.build_form_data_from_job(job_name, job_config)
        form_data['page_title'] = f'Edit Job: {job_name}'
        form_data['form_title'] = f'Edit Backup Job: {job_name}'
        form_data['submit_button_text'] = 'Commit Changes'
        form_data['form_has_changes'] = False  # Initially no changes
        
        # Store original config for change detection (as JSON string)
        form_data['original_job_config'] = self.job_operations.serialize_job_config(job_config)
        
        # Add available destination types (could be context-aware based on source)
        source_config = job_config.get('source_config', {})
        destination_service = DestinationTypeService()
        form_data['available_destination_types'] = destination_service.get_available_destination_types(source_config)
        
        # Pre-select source and destination types for edit mode
        source_type = job_config.get('source_type', 'local')
        form_data['selected_source_type'] = source_type
        form_data['source_local_selected'] = (source_type == 'local')
        form_data['source_ssh_selected'] = (source_type == 'ssh')
        form_data['selected_dest_type'] = job_config.get('dest_type', 'local')
        
        # Build source fields HTML using template builder
        template_builder = JobFormTemplateBuilder(self.template_service)
        form_data['source_fields_html'] = template_builder.build_source_fields_html(source_type, source_config)
        
        # Build destination fields HTML using template builder
        dest_type = job_config.get('dest_type', 'local')
        dest_config = job_config.get('dest_config', {})
        form_data['dest_fields_html'] = template_builder.build_destination_fields_html(dest_type, dest_config, form_data)
        
        # Add notification configuration
        existing_notifications = job_config.get('notifications', [])
        form_data.update(self._build_notification_form_data(existing_notifications))
        
        # Add schedule configuration
        form_data.update(self._build_schedule_form_data(job_config))
        
        return self._render_html('pages/job_form.html', form_data)

    def _build_notification_form_data(self, existing_notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build notification form data structure (delegated to service)"""
        builder = NotificationFormDataBuilder()
        return builder.build_notification_context(existing_notifications)
        
    def _build_schedule_form_data(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build schedule form data structure (delegated to service)"""
        builder = ScheduleFormDataBuilder()
        return builder.build_schedule_context(job_config)

    @handle_page_errors("Job inspect")
    def show_job_inspect(self, job_name: str = "") -> HTMLResponse:
        """Show job inspection page"""
        if not job_name:
            return self._render_error('partials/error_page.html', {
                'error_message': "Job name is required", 
                'page_title': "Error"
            }, 400)
        
        jobs = self.job_config.get_backup_jobs()
        if job_name not in jobs:
            return self._render_error('partials/error_page.html', {
                'error_message': f"Job '{job_name}' not found", 
                'page_title': "Error"
            }, 404)
        
        job_config = jobs[job_name]
        
        # Get job status and logs
        job_management = JobManagementService()
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
        """Check repository availability and return appropriate HTMX HTML response"""
        dest_type = job_config.get('dest_type')
        
        if dest_type == 'restic':
            return self._check_restic_repository_html(job_name, job_config)
        else:
            # Non-restic repositories - assume available for now
            return self._render_html('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': dest_type
            })
    
    def _check_restic_repository_html(self, job_name: str, job_config: Dict[str, Any]) -> HTMLResponse:
        """Check restic repository availability and return HTML response"""
        dest_config = job_config.get('dest_config', {})
        repo_uri = dest_config.get('repo_uri')
        
        if not repo_uri:
            return self._render_html('partials/error_message.html', {
                'error_message': 'Repository URI not configured'
            })
            
        check_success, check_message = backup_service.repository_service._quick_repository_check(repo_uri, dest_config)
        
        if check_success:
            return self._render_html('partials/repository_available.html', {
                'job_name': job_name,
                'job_type': 'restic'
            })
        else:
            return self._send_repository_error_html(job_name, check_message)
    
    def _send_repository_error_html(self, job_name: str, error_message: str) -> HTMLResponse:
        """Send appropriate repository error HTMX partial based on error type"""
        if error_message and ('locked by' in error_message.lower() or 'repository is already locked' in error_message.lower()):
            # Repository locked - render unlock interface
            return self._render_html('partials/repository_locked_error.html', {
                'job_name': job_name,
                'error_message': error_message
            })
        else:
            # Other error - render error template
            return self._render_html('partials/repository_error.html', {
                'job_name': job_name,
                'error_type': 'connection_error',
                'error_message': error_message or 'Unknown error'
            })






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
        """Schedule a job for execution - using functional SchedulingService"""
        
        # Use the functional scheduling service that already exists
        scheduler_service = SchedulingService()
        
        # Bootstrap all schedules (this will include the requested job if it's enabled and scheduled)
        scheduled_count = scheduler_service.bootstrap_schedules()
        
        job_name = form_data.get('job_name', [''])[0] if isinstance(form_data.get('job_name'), list) else form_data.get('job_name', '')
        
        return JSONResponse(content={
            'success': True,
            'message': f'Scheduler refreshed. {scheduled_count} jobs scheduled total.',
            'job_name': job_name,
            'scheduled_count': scheduled_count
        })

    @handle_page_errors("List scheduler jobs")
    def list_scheduler_jobs(self) -> JSONResponse:
        """List APScheduler internal jobs - DEBUG/ADMIN endpoint"""
        scheduler_service = SchedulingService()
        job_scheduler = JobSchedulerHandler(scheduler_service)
        result = job_scheduler.list_jobs()
        return JSONResponse(content=result)

# Global handler instance
jobs_handler = JobsHandler()