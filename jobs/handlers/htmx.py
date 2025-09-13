"""
HTMX Handlers and Utilities for Jobs Domain

Contains all HTMX endpoint handlers and form parsing utilities.
Handlers are organized by functional area for easy navigation.
"""

from typing import Dict, Any, List, Union, Callable
from functools import wraps
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from jobs.services.config import JobConfigService




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
        from jobs.services.manage import JobOperationsService
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
        """Validate source path with robust permission checking for HTMX forms"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        # Extract path from array format
        path_array = form_data.get('source_path[]', [])
        path_index = int(get_form_value(form_data, 'path_index', '0'))
        path = path_array[path_index] if path_index < len(path_array) else ''
        
        if not path or not path.strip():
            result = {'valid': False, 'error': 'Please enter a path'}
            from jobs.handlers.pages import jobs_handler
            html_response = jobs_handler.render_source_path_validation_status(result)
            return HTMLResponse(content=html_response)
        
        # Extract source configuration
        source_type = get_form_value(form_data, 'source_type')
        hostname = get_form_value(form_data, 'hostname')
        username = get_form_value(form_data, 'username')
        
        # Validate based on source type (robust handling from working version)
        from jobs.handlers.pages import jobs_handler
        if source_type == 'ssh':
            result = jobs_handler.validation_service.validate_source_path_for_backup_ssh(hostname, username, path)
        elif source_type == 'local':
            result = jobs_handler.validation_service.validate_source_path_for_backup_local(path)
        else:
            result = {'valid': False, 'error': 'Please select a source type (Local Path or SSH Remote)'}
        
        html_response = jobs_handler.render_source_path_validation_status(result)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Add source path")
    async def add_source_path_htmx(self, request) -> HTMLResponse:
        """Add a new source path entry for HTMX forms"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        from origins.schema import SOURCE_PATH_SCHEMA
        
        # Get path count from JavaScript via hx-vals
        path_count = int(get_form_value(form_data, 'path_count', '0'))
        new_path_index = path_count  # Next sequential index
        
        # Create new empty path data
        path_data = {'path': '', 'includes': [], 'excludes': []}
        source_paths = ['', '']  # Always show remove button for new paths
        
        # Return just the new path entry wrapped in its container
        html_response = self.template_service.render_template('partials/source_path_entry_container.html',
                                                           path_index=new_path_index,
                                                           path_data=path_data,
                                                           source_paths=source_paths,
                                                           source_path_schema=SOURCE_PATH_SCHEMA)
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
        """Save backup job with form parsing - pure switchboard compliance"""
        from jobs.handlers.htmx import parse_htmx_form
        
        form_data = await parse_htmx_form(request)
        
        # Call existing business logic via pages handler
        from jobs.handlers.pages import jobs_handler
        return jobs_handler.save_backup_job(form_data)

    @handle_page_errors("Validate source paths")
    async def validate_source_paths_htmx(self, request) -> JSONResponse:
        """Validate source paths with form parsing - pure switchboard compliance"""
        from jobs.handlers.htmx import parse_htmx_form
        
        form_data = await parse_htmx_form(request)
        
        # Call existing business logic via pages handler
        from jobs.handlers.pages import jobs_handler
        return jobs_handler.validate_source_paths(form_data)

    @handle_page_errors("Process restore request")
    async def process_restore_request_htmx(self, request) -> JSONResponse:
        """Process restore request with form parsing - pure switchboard compliance"""
        from jobs.handlers.htmx import parse_htmx_form
        
        form_data = await parse_htmx_form(request)
        
        # Call existing business logic via pages handler  
        from jobs.handlers.pages import jobs_handler
        return jobs_handler.process_restore_request(form_data)

    @handle_page_errors("Schedule job")
    async def schedule_job_htmx(self, request) -> JSONResponse:
        """Schedule job with form parsing - pure switchboard compliance"""
        from jobs.handlers.htmx import parse_htmx_form
        
        form_data = await parse_htmx_form(request)
        
        # Call existing business logic via pages handler
        from jobs.handlers.pages import jobs_handler
        return jobs_handler.schedule_job_direct(form_data)
    
    # =========================================================================
    # RESTORE OPERATION HTMX HANDLERS
    # =========================================================================
    
    @handle_page_errors("Handle restore target change")
    async def handle_restore_target_change_htmx(self, request) -> HTMLResponse:
        """Handle restore target change and check overwrites - HTMX handler"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)

        # Business logic (preserve original implementation)
        # HTTP concern: extract parameters
        job_name = get_form_value(form_data, 'job_name')
        restore_target = get_form_value(form_data, 'restore_target', 'highball')
        dry_run = get_form_value(form_data, 'dry_run') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: check for overwrites using restore service
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.job_config.get_backup_jobs()
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths
        )
        
        # Template concern: use template service to render partial
        template_vars = {
            'HAS_OVERWRITES': 'true' if has_overwrites else 'false',
            'RESTORE_TARGET': restore_target,
            'DRY_RUN': 'true' if dry_run else 'false',
            'TARGET_TEXT': "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        }
        
        html_response = self.template_service.render_template('partials/restore_overwrite_warning.html', **template_vars)

        # Return HTMLResponse wrapper
        return HTMLResponse(content=html_response)

    @handle_page_errors("Handle restore dry run change")
    async def handle_restore_dry_run_change_htmx(self, request) -> HTMLResponse:
        """Handle dry run toggle and update warning - HTMX handler"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)

        # Business logic (preserve original implementation)
        # HTTP concern: extract parameters  
        job_name = get_form_value(form_data, 'job_name')
        restore_target = get_form_value(form_data, 'restore_target', 'highball')
        dry_run = get_form_value(form_data, 'dry_run') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: check for overwrites using restore service
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details  
        jobs = self.job_config.get_backup_jobs()
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths
        )
        
        # Template concern: use template service to render partial
        template_vars = {
            'HAS_OVERWRITES': 'true' if has_overwrites else 'false',
            'RESTORE_TARGET': restore_target,
            'DRY_RUN': 'true' if dry_run else 'false',
            'TARGET_TEXT': "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        }
        
        html_response = self.template_service.render_template('partials/restore_overwrite_warning.html', **template_vars)

        # Return HTMLResponse wrapper  
        return HTMLResponse(content=html_response)

    @handle_page_errors("Check restore overwrites")
    async def check_restore_overwrites_htmx(self, request) -> HTMLResponse:
        """Check restore overwrites for HTMX forms"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        # HTTP concern: extract parameters
        job_name = get_form_value(form_data, 'job_name')
        restore_target = get_form_value(form_data, 'restore_target', 'highball')
        select_all = get_form_value(form_data, 'select_all') == 'on'
        selected_paths = form_data.get('selected_paths', [])
        
        # Business logic concern: delegate to restore service
        from jobs.services.restore import RestoreService
        restore_service = RestoreService()
        
        # Get job config for source details
        jobs = self.job_config.get_backup_jobs()
        job_config = jobs.get(job_name, {})
        source_config = job_config.get('source_config', {})
        source_type = job_config.get('source_type', 'local')
        
        has_overwrites = restore_service.check_restore_overwrites(
            restore_target, source_type, source_config, selected_paths, select_all
        )
        
        # Template concern: pass data to Jinja2 template for conditional rendering
        target_text = "Highball's /restore directory" if restore_target == 'highball' else "the original source location"
        html_response = self.template_service.render_template('partials/restore_overwrite_warning.html',
                                                            has_overwrites=has_overwrites,
                                                            target_text=target_text,
                                                            dry_run=False)
        return HTMLResponse(content=html_response)
    
    # =========================================================================
    # JOB EXECUTION HTMX HANDLERS
    # =========================================================================
    
    @handle_page_errors("Run backup")
    async def run_backup_htmx(self, request) -> JSONResponse:
        """Run backup job with form parsing - pure switchboard compliance"""
        from fastapi.responses import JSONResponse
        
        form = await request.form()
        job_name = form.get('job_name', '')
        
        # Call direct business logic (moved from operations handler)
        return self.run_backup_job_direct(job_name, False)

    @handle_page_errors("Dry run backup")
    async def dry_run_backup_htmx(self, request) -> JSONResponse:
        """Dry run backup job with form parsing - pure switchboard compliance"""
        from fastapi.responses import JSONResponse
        
        form = await request.form()
        job_name = form.get('job_name', '')
        
        # Call direct business logic (moved from operations handler)  
        return self.run_backup_job_direct(job_name, True)
    
    def run_backup_job_direct(self, job_name: str, dry_run: bool = False) -> JSONResponse:
        """Execute backup job with full orchestration - moved from operations handler"""
        from fastapi.responses import JSONResponse
        
        # Need to get backup orchestration from pages handler for now
        from jobs.handlers.pages import jobs_handler
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
        from jobs.handlers.pages import jobs_handler
        
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
        """Toggle success message field visibility for job notification configuration"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        # Check if checkbox is checked
        enabled = 'notify_on_success[]' in form_data
        success_message = get_form_value(form_data, 'notification_success_messages[]')
        
        html_response = self.template_service.render_template('partials/notification_success_message.html',
                                                            enabled=enabled,
                                                            success_message=success_message)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Toggle failure message")
    async def toggle_failure_message_htmx(self, request) -> HTMLResponse:
        """Toggle failure message field visibility for job notification configuration"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        # Check if checkbox is checked
        enabled = 'notify_on_failure[]' in form_data
        failure_message = get_form_value(form_data, 'notification_failure_messages[]')
        
        html_response = self.template_service.render_template('partials/notification_failure_message.html',
                                                            enabled=enabled,
                                                            failure_message=failure_message)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Render notification providers")
    async def render_notification_providers_htmx(self, request) -> HTMLResponse:
        """Render notification providers section for job configuration HTMX forms"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        # Delegate to jobs_handler helper methods
        from jobs.handlers.pages import jobs_handler
        
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
        """Add a new notification provider to job configuration for HTMX forms"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        provider_name = get_form_value(form_data, 'provider')
        if not provider_name:
            html_response = self.template_service.render_template('partials/error_message.html',
                                                               message="Invalid provider selection")
            return HTMLResponse(content=html_response)
        
        # Delegate to jobs_handler for complex provider operations
        from jobs.handlers.pages import jobs_handler
        
        # Generate unique ID
        import time
        timestamp = int(time.time() * 1000)
        provider_id = f"notification_{provider_name}_{timestamp}"
        
        new_provider_html = jobs_handler._render_notification_provider({
            'provider': provider_name,
            'notify_on_success': False,
            'notify_on_failure': True,  # Default to True for failures
            'notify_on_maintenance_failure': False,
            'success_message': '',
            'failure_message': ''
        }, timestamp, provider_id)
        
        # Get currently configured providers from form data
        current_providers = jobs_handler._get_form_providers(form_data)
        current_providers.append(provider_name)
        
        # Update dropdown with remaining providers
        available_providers = jobs_handler._get_enabled_global_providers()
        jobs_handler.configured_providers = current_providers  # Update state
        updated_selection = jobs_handler._render_provider_selection(available_providers)
        
        html_response = self.template_service.render_template('partials/notification_provider_added_response.html',
                                                            new_provider_html=new_provider_html,
                                                            updated_selection_html=updated_selection)
        return HTMLResponse(content=html_response)

    @handle_page_errors("Remove notification provider")
    async def remove_notification_provider_htmx(self, request) -> HTMLResponse:
        """Remove a notification provider from job configuration for HTMX forms"""
        from jobs.handlers.htmx import parse_htmx_form, get_form_value
        
        form_data = await parse_htmx_form(request)
        
        provider_id = get_form_value(form_data, 'provider_id')
        
        # Delegate to jobs_handler for provider operations
        from jobs.handlers.pages import jobs_handler
        
        # Extract provider name from ID (format: notification_{provider}_{timestamp})
        provider_name = None
        if provider_id and '_' in provider_id:
            parts = provider_id.split('_')
            if len(parts) >= 2:
                provider_name = parts[1]
        
        # Get current providers from form and remove this one
        current_providers = jobs_handler._get_form_providers(form_data)
        if provider_name and provider_name in current_providers:
            current_providers.remove(provider_name)
        
        # Update state and render dropdown
        jobs_handler.configured_providers = current_providers
        available_providers = jobs_handler._get_enabled_global_providers()
        updated_selection = jobs_handler._render_provider_selection(available_providers)
        
        # Return response that removes provider config and updates dropdown
        html_response = self.template_service.render_template('partials/notification_provider_removed_response.html',
                                                            provider_id=provider_id,
                                                            updated_selection_html=updated_selection)
        return HTMLResponse(content=html_response)


# =============================================================================
# INSTANCE
# =============================================================================

# Singleton instance for use by routers
htmx_handlers = HTMXHandlers()