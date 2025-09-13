"""
HTMX Handlers and Utilities for Jobs Domain

Contains all HTMX endpoint handlers and form parsing utilities.
Handlers are organized by functional area for easy navigation.
"""

import time
from typing import Dict, Any, List, Union, Callable
from functools import wraps
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from jobs.services.config import JobConfigService
from jobs.services.manage import JobOperationsService
from jobs.handlers.pages import jobs_handler
from origins.schema import SOURCE_PATH_SCHEMA
from jobs.services.restore import RestoreService




class HTMXFormParser:
    """Utility class for parsing HTMX form data from FastAPI requests"""
    
    @staticmethod
    async def parse_form_data(request: Request) -> Dict[str, Any]:
        """
        Parse form data from FastAPI request into standardized format
        
        Returns a dictionary where:
        - Single values are stored as lists with one element
        - Multiple values (like checkboxes) are stored as lists with multiple elements
        
        This matches the expected format used throughout the jobs handlers.
        """
        form = await request.form()
        form_data = {}
        
        for key, value in form.items():
            if key in form_data:
                # Convert to list if not already
                if not isinstance(form_data[key], list):
                    form_data[key] = [form_data[key]]
                form_data[key].append(value)
            else:
                form_data[key] = [value]
        
        return form_data
    
    @staticmethod
    def get_form_value(form_data: Dict[str, Any], key: str, default: str = '') -> str:
        """
        Extract single value from parsed form data
        
        Args:
            form_data: Form data parsed by parse_form_data()
            key: Form field name
            default: Default value if key not found
            
        Returns:
            Single string value from form field
        """
        values = form_data.get(key, [default])
        return values[0] if values else default
    
    @staticmethod
    def get_form_list(form_data: Dict[str, Any], key: str) -> List[str]:
        """
        Extract list of values from parsed form data
        
        Args:
            form_data: Form data parsed by parse_form_data()
            key: Form field name
            
        Returns:
            List of string values from form field
        """
        return form_data.get(key, [])
    
    @staticmethod
    def is_form_checked(form_data: Dict[str, Any], key: str) -> bool:
        """
        Check if a checkbox/toggle field is checked
        
        Args:
            form_data: Form data parsed by parse_form_data()
            key: Form field name
            
        Returns:
            True if field is present and has value 'on' or 'true'
        """
        value = HTMXFormParser.get_form_value(form_data, key)
        return value.lower() in ('on', 'true', '1')


# Convenience functions for backward compatibility
async def parse_htmx_form(request: Request) -> Dict[str, Any]:
    """Parse HTMX form data - convenience function"""
    return await HTMXFormParser.parse_form_data(request)

def get_form_value(form_data: Dict[str, Any], key: str, default: str = '') -> str:
    """Get single form value - convenience function"""
    return HTMXFormParser.get_form_value(form_data, key, default)


# =============================================================================
# HTMX HANDLERS CLASS
# =============================================================================

class HTMXHandlers(BaseHandler):
    """HTMX endpoint handlers for jobs domain"""
    
    def __init__(self):
        self.job_config = JobConfigService()
        self._init_template_service()

        # Initialize services for non-config operations
        self.job_operations = JobOperationsService()
    
    def _render_html(self, template_path: str, data: Dict[str, Any]) -> HTMLResponse:
        """Render HTML template with data"""
        html_content = self.template_service.render_template(template_path, data)
        return HTMLResponse(content=html_content)

    # =========================================================================
    # SOURCE PATH VALIDATION HTMX HANDLERS
    # =========================================================================
    
    @handle_page_errors("Validate source path")
    async def validate_source_path_htmx(self, request) -> HTMLResponse:
        """Validate source path with robust permission checking for HTMX forms - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        result = self.job_config.validate_source_path_from_form(form_data)
        html_response = jobs_handler.render_source_path_validation_status(result)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Add source path")
    async def add_source_path_htmx(self, request) -> HTMLResponse:
        """Add a new source path entry for HTMX forms - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        template_data = self.job_config.add_source_path_entry_data(form_data)

        # Return rendered template
        html_response = self.template_service.render_template('partials/source_path_entry_container.html', **template_data)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Remove source path")
    async def remove_source_path_htmx(self, request) -> HTMLResponse:
        """Remove a source path entry - returns empty response for HTMX DELETE"""
        # Since we're using hx-delete and hx-swap="outerHTML", 
        # the target element will be removed automatically.
        # We just need to return an empty response.
        return HTMLResponse(content="")
    
    # =========================================================================
    # JOB CRUD HTMX HANDLERS  
    # =========================================================================
    
    @handle_page_errors("Save backup job")
    async def save_backup_job_htmx(self, request) -> JSONResponse:
        """Save backup job with form parsing - calls service directly"""
        form_data = await parse_htmx_form(request)

        # Call service directly
        result = self.job_config.save_backup_job_from_form(form_data)
        if result['type'] == 'redirect':
            return RedirectResponse(url=result['url'], status_code=result['status_code'])
        else:
            return JSONResponse(content=result['content'], status_code=result['status_code'])

    @handle_page_errors("Validate source paths")
    async def validate_source_paths_htmx(self, request) -> JSONResponse:
        """Validate source paths with form parsing - calls service directly"""
        form_data = await parse_htmx_form(request)

        # Call service directly
        result = self.job_config.validate_source_paths_from_form(form_data)
        return JSONResponse(content=result)

    @handle_page_errors("Process restore request")
    async def process_restore_request_htmx(self, request) -> JSONResponse:
        """Process restore request with form parsing - calls service directly"""
        form_data = await parse_htmx_form(request)

        # Call service directly
        from jobs.services.restore import RestoreOperationsService
        restore_ops = RestoreOperationsService()
        result = restore_ops.process_restore_request_from_form(form_data)
        return JSONResponse(content=result)

    @handle_page_errors("Schedule job")
    async def schedule_job_htmx(self, request) -> JSONResponse:
        """Schedule job with form parsing - pure switchboard compliance"""
        form_data = await parse_htmx_form(request)
        
        # Call existing business logic via pages handler
        return jobs_handler.schedule_job_direct(form_data)
    
    # =========================================================================
    # RESTORE OPERATION HTMX HANDLERS
    # =========================================================================
    
    @handle_page_errors("Handle restore target change")
    async def handle_restore_target_change_htmx(self, request) -> HTMLResponse:
        """Handle restore target change and check overwrites - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        from jobs.services.restore import RestoreOperationsService
        restore_ops = RestoreOperationsService()
        template_vars = restore_ops.handle_restore_target_change_from_form(form_data)

        # Return rendered template
        html_response = self.template_service.render_template('partials/restore_overwrite_warning.html', **template_vars)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Handle restore dry run change")
    async def handle_restore_dry_run_change_htmx(self, request) -> HTMLResponse:
        """Handle dry run toggle and update warning - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        from jobs.services.restore import RestoreOperationsService
        restore_ops = RestoreOperationsService()
        template_vars = restore_ops.handle_restore_dry_run_change_from_form(form_data)

        # Return rendered template
        html_response = self.template_service.render_template('partials/restore_overwrite_warning.html', **template_vars)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Check restore overwrites")
    async def check_restore_overwrites_htmx(self, request) -> HTMLResponse:
        """Check restore overwrites for HTMX forms - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        from jobs.services.restore import RestoreOperationsService
        restore_ops = RestoreOperationsService()
        template_data = restore_ops.check_restore_overwrites_from_form(form_data)

        # Return rendered template
        html_response = self.template_service.render_template('partials/restore_overwrite_warning.html', **template_data)
        return HTMLResponse(content=html_response)
    
    # =========================================================================
    # JOB EXECUTION HTMX HANDLERS
    # =========================================================================
    
    @handle_page_errors("Run backup")
    async def run_backup_htmx(self, request) -> JSONResponse:
        """Run backup job with form parsing - pure switchboard compliance"""
        form = await request.form()
        job_name = form.get('job_name', '')
        
        # Call direct business logic (moved from operations handler)
        return self.run_backup_job_direct(job_name, False)

    @handle_page_errors("Dry run backup")
    async def dry_run_backup_htmx(self, request) -> JSONResponse:
        """Dry run backup job with form parsing - pure switchboard compliance"""
        
        form = await request.form()
        job_name = form.get('job_name', '')
        
        # Call direct business logic (moved from operations handler)  
        return self.run_backup_job_direct(job_name, True)
    
    def run_backup_job_direct(self, job_name: str, dry_run: bool = False) -> JSONResponse:
        """Execute backup job with full orchestration - moved from operations handler"""
        
        # Need to get backup orchestration from pages handler for now
        result = jobs_handler.backup_orchestration.run_backup_job(job_name, dry_run)
        return JSONResponse(content=result)
    
    @handle_page_errors("Check repository availability")
    def check_repository_availability_htmx(self, job_name: str) -> HTMLResponse:
        """HTMX endpoint for repository availability check"""
        
        if not job_name:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               error_message='Job name is required')
            return HTMLResponse(content=html_response)
        
        # Delegate to jobs_handler for repository operations
        
        # Get and validate job configuration
        jobs = self.job_config.get_backup_jobs()
        if job_name not in jobs:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               error_message=f"Job '{job_name}' not found")
            return HTMLResponse(content=html_response)
        
        job_config = jobs[job_name]
        # Perform repository availability check and return response
        return jobs_handler._check_and_respond_repository_status_html(job_name, job_config)
    
    # =========================================================================
    # NOTIFICATION HTMX HANDLERS
    # =========================================================================
    
    @handle_page_errors("Toggle success message")
    async def toggle_success_message_htmx(self, request) -> HTMLResponse:
        """Toggle success message field visibility for job notification configuration - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.job_config.config_reader)
        template_data = form_builder.toggle_success_message_from_form(form_data)

        # Return rendered template
        html_response = self.template_service.render_template('partials/notification_success_message.html', **template_data)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Toggle failure message")
    async def toggle_failure_message_htmx(self, request) -> HTMLResponse:
        """Toggle failure message field visibility for job notification configuration - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.job_config.config_reader)
        template_data = form_builder.toggle_failure_message_from_form(form_data)

        # Return rendered template
        html_response = self.template_service.render_template('partials/notification_failure_message.html', **template_data)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Render notification providers")
    async def render_notification_providers_htmx(self, request) -> HTMLResponse:
        """Render notification providers section for job configuration HTMX forms"""
        form_data = await parse_htmx_form(request)
        
        # Delegate to jobs_handler helper methods
        
        # Get available providers from global config
        available_providers = jobs_handler._get_enabled_global_providers()
        existing_notifications = []  # Parse from form if editing
        
        # Build provider configurations
        provider_html = ""
        for i, provider in enumerate(existing_notifications):
            provider_html += jobs_handler._render_notification_provider(provider, i)
        
        # Build provider selection dropdown
        jobs_handler.configured_providers = []  # Initialize for rendering
        selection_html = jobs_handler._render_provider_selection(available_providers)
        
        html_response = self.template_service.render_template('partials/notification_providers_section.html',
                                                            provider_html=provider_html,
                                                            selection_html=selection_html)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Add notification provider")
    async def add_notification_provider_htmx(self, request) -> HTMLResponse:
        """Add a new notification provider to job configuration for HTMX forms - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.job_config.config_reader)
        result = form_builder.add_notification_provider_from_form(form_data)

        if not result['success']:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               message=result['error'])
            return HTMLResponse(content=html_response)

        # Return rendered template
        html_response = self.template_service.render_template('partials/notification_provider_added_response.html',
                                                            new_provider_html=result['new_provider_html'],
                                                            updated_selection_html=result['updated_selection_html'])
        return HTMLResponse(content=html_response)

    @handle_page_errors("Remove notification provider")
    async def remove_notification_provider_htmx(self, request) -> HTMLResponse:
        """Remove a notification provider from job configuration for HTMX forms - thin wrapper"""
        form_data = await parse_htmx_form(request)

        # Delegate to service
        from jobs.services.define import NotificationFormBuilder
        form_builder = NotificationFormBuilder(self.template_service, self.job_config.config_reader)
        result = form_builder.remove_notification_provider_from_form(form_data)

        # Return rendered template
        html_response = self.template_service.render_template('partials/notification_provider_removed_response.html',
                                                            provider_id=result['provider_id'],
                                                            updated_selection_html=result['updated_selection_html'])
        return HTMLResponse(content=html_response)


# =============================================================================
# INSTANCE
# =============================================================================

# Singleton instance for use by routers
htmx_handlers = HTMXHandlers()