#!/usr/bin/env python3
"""
Jobs Domain Forms Handler
POST/PUT/DELETE operations for job management
"""
from typing import Dict, Any, List
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler

from jobs.services.config import JobConfigService
from jobs.services.backup import BackupOrchestrationService
from jobs.services.define import JobDisplayBuilder


async def parse_htmx_form(request: Request) -> Dict[str, Any]:
    return await HtmxFormHandler.parse_form_data(request)


def get_form_value(form_data: Dict[str, Any], key: str, default: str = '') -> str:
    """Get form value with default fallback"""
    value = form_data.get(key)
    if isinstance(value, list):
        return value[0] if value else default
    return value or default


class JobFormsHandler(BaseHandler):
    """Handler for job form operations (POST/PUT/DELETE)"""

    def __init__(self):
        super().__init__()
        self.template_service = TemplateService()
        self.job_config = JobConfigService()
        self.backup_orchestration = BackupOrchestrationService(self.job_config)
        self.display_builder = JobDisplayBuilder(self.template_service)

    def _render_html(self, template_path: str, data: Dict[str, Any]) -> HTMLResponse:
        """Render HTML template response"""
        html_response = self.template_service.render_template(template_path, **data)
        return HTMLResponse(content=html_response)

    # =========================================================================
    # JOB CRUD OPERATIONS
    # =========================================================================

    async def save_backup_job(self, request: Request) -> JSONResponse:
        """Save backup job from form submission"""
        form_data = await parse_htmx_form(request)

        # Delegate business logic to service
        result = self.job_config.save_backup_job_from_form(form_data)

        # Handle presentation concern - return appropriate response type
        if result['type'] == 'redirect':
            return RedirectResponse(url=result['url'], status_code=result['status_code'])
        else:
            return JSONResponse(content=result['content'], status_code=result['status_code'])

    @handle_page_errors("Delete job")
    def delete_backup_job(self, job_name: str) -> JSONResponse:
        """Delete backup job configuration"""
        result = self.job_config.delete_backup_job(job_name)
        return JSONResponse(content=result)

    @handle_page_errors("Purge job")
    def purge_backup_job(self, job_name: str) -> JSONResponse:
        """Purge backup job and all associated data"""
        result = self.job_config.purge_backup_job(job_name)
        return JSONResponse(content=result)

    @handle_page_errors("Restore backup job")
    def restore_backup_job(self, job_name: str) -> JSONResponse:
        """Restore backup job configuration"""
        result = self.job_config.restore_backup_job(job_name)
        return JSONResponse(content=result)

    # =========================================================================
    # BACKUP OPERATIONS
    # =========================================================================

    async def run_backup(self, request: Request) -> JSONResponse:
        """Execute backup job - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        job_name = get_form_value(form_data, 'job_name')

        result = self.backup_orchestration.run_backup_job(job_name, False)
        return JSONResponse(content=result)

    async def dry_run_backup(self, request: Request) -> JSONResponse:
        """Execute dry run backup - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        job_name = get_form_value(form_data, 'job_name')

        result = self.backup_orchestration.run_backup_job(job_name, True)
        return JSONResponse(content=result)

    def run_backup_job_direct(self, job_name: str, dry_run: bool = False) -> JSONResponse:
        """Execute backup job with full orchestration"""
        result = self.backup_orchestration.run_backup_job(job_name, dry_run)
        return JSONResponse(content=result)

    # =========================================================================
    # SCHEDULING OPERATIONS
    # =========================================================================

    async def schedule_job(self, request: Request) -> JSONResponse:
        """Schedule backup job - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        result = self.job_config.schedule_job_from_form(form_data)
        return JSONResponse(content=result)

    # =========================================================================
    # VALIDATION OPERATIONS
    # =========================================================================

    async def validate_source_paths(self, request: Request) -> JSONResponse:
        """Validate source paths from form submission"""
        form_data = await parse_htmx_form(request)
        result = self.job_config.validate_source_paths_from_form(form_data)
        return JSONResponse(content=result)

    async def validate_source_path(self, request: Request) -> JSONResponse:
        """Validate individual source path - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        result = self.job_config.validate_source_path_from_form(form_data)
        return JSONResponse(content=result)

    # =========================================================================
    # SOURCE PATH MANAGEMENT
    # =========================================================================

    async def add_source_path(self, request: Request) -> HTMLResponse:
        """Add a new source path entry for HTMX forms - matches original working implementation"""
        form_data = await parse_htmx_form(request)

        # Delegate to service (same as original)
        template_data = self.job_config.add_source_path_entry_data(form_data)

        # Return rendered template (same as original)
        return self._render_html('partials/source_path_entry_container.html', template_data)

    async def remove_source_path(self, request: Request) -> HTMLResponse:
        """Remove source path from job configuration - HTMX endpoint"""
        form_data = await parse_htmx_form(request)

        # Get path to remove and current paths
        path_to_remove = get_form_value(form_data, 'path_to_remove')
        current_paths = form_data.get('source_paths', [])
        if isinstance(current_paths, str):
            current_paths = [current_paths] if current_paths else []

        # Remove the path if it exists
        if path_to_remove in current_paths:
            current_paths.remove(path_to_remove)

        # Render updated path list
        return self._render_html('partials/source_path_list.html', {
            'source_paths': current_paths
        })

    # =========================================================================
    # RESTORE OPERATIONS
    # =========================================================================

    async def process_restore_request(self, request: Request) -> JSONResponse:
        """Process restore request from form submission"""
        form_data = await parse_htmx_form(request)
        result = self.job_config.process_restore_request_from_form(form_data)
        return JSONResponse(content=result)

    async def handle_restore_target_change(self, request: Request) -> HTMLResponse:
        """Handle restore target change - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        restore_target = get_form_value(form_data, 'restore_target')

        return self._render_html('partials/restore_target_options.html', {
            'restore_target': restore_target
        })

    async def handle_restore_dry_run_change(self, request: Request) -> HTMLResponse:
        """Handle restore dry run toggle - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        dry_run = get_form_value(form_data, 'dry_run') == 'on'

        return self._render_html('partials/restore_dry_run_status.html', {
            'dry_run': dry_run
        })

    async def check_restore_overwrites(self, request: Request) -> HTMLResponse:
        """Check for potential restore overwrites - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        result = self.job_config.check_restore_overwrites(form_data)

        return self._render_html('partials/restore_overwrite_warning.html', {
            'overwrites': result.get('overwrites', []),
            'has_overwrites': len(result.get('overwrites', [])) > 0
        })

    # =========================================================================
    # NOTIFICATION OPERATIONS
    # =========================================================================

    async def toggle_success_message(self, request: Request) -> HTMLResponse:
        """Toggle success message notification - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        enabled = get_form_value(form_data, 'success_enabled') == 'on'

        return self._render_html('partials/success_message_toggle.html', {
            'success_enabled': enabled
        })

    async def toggle_failure_message(self, request: Request) -> HTMLResponse:
        """Toggle failure message notification - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        enabled = get_form_value(form_data, 'failure_enabled') == 'on'

        return self._render_html('partials/failure_message_toggle.html', {
            'failure_enabled': enabled
        })

    async def render_notification_providers(self, request: Request) -> HTMLResponse:
        """Render notification providers list - HTMX endpoint"""
        form_data = await parse_htmx_form(request)
        providers = form_data.get('notification_providers', [])

        return self._render_html('partials/notification_providers_list.html', {
            'notification_providers': providers
        })

    async def add_notification_provider(self, request: Request) -> HTMLResponse:
        """Add notification provider - HTMX endpoint"""
        form_data = await parse_htmx_form(request)

        # Get provider details
        provider_type = get_form_value(form_data, 'provider_type')
        provider_config = get_form_value(form_data, 'provider_config')

        # Get current providers
        current_providers = form_data.get('notification_providers', [])
        if isinstance(current_providers, str):
            current_providers = [current_providers] if current_providers else []

        # Add new provider if valid
        if provider_type and provider_config:
            new_provider = f"{provider_type}:{provider_config}"
            if new_provider not in current_providers:
                current_providers.append(new_provider)

        return self._render_html('partials/notification_providers_list.html', {
            'notification_providers': current_providers
        })

    async def remove_notification_provider(self, request: Request) -> HTMLResponse:
        """Remove notification provider - HTMX endpoint"""
        form_data = await parse_htmx_form(request)

        # Get provider to remove
        provider_to_remove = get_form_value(form_data, 'provider_to_remove')

        # Get current providers
        current_providers = form_data.get('notification_providers', [])
        if isinstance(current_providers, str):
            current_providers = [current_providers] if current_providers else []

        # Remove provider if exists
        if provider_to_remove in current_providers:
            current_providers.remove(provider_to_remove)

        return self._render_html('partials/notification_providers_list.html', {
            'notification_providers': current_providers
        })


class HtmxFormHandler:
    """Helper class for HTMX form parsing"""

    @staticmethod
    async def parse_form_data(request: Request) -> Dict[str, Any]:
        """Parse form data from FastAPI request"""
        try:
            form = await request.form()
            parsed_data = {}

            for key, value in form.items():
                if key in parsed_data:
                    # Handle multiple values for same key
                    if isinstance(parsed_data[key], list):
                        parsed_data[key].append(value)
                    else:
                        parsed_data[key] = [parsed_data[key], value]
                else:
                    parsed_data[key] = value

            return parsed_data

        except Exception as e:
            print(f"Error parsing form data: {e}")
            return {}


# Export instance for consistent naming pattern
jobs_forms = JobFormsHandler()