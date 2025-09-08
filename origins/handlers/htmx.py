"""
HTMX Handlers for Origins Domain

Contains all HTMX endpoint handlers following jobs/dests domain pattern.
Handlers contain their complete business logic and will be refactored to delegate to services in Phase 2.
"""

import logging
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from config import BackupConfig
from models.forms import safe_get_value

logger = logging.getLogger(__name__)


# =============================================================================
# HTMX HANDLERS CLASS
# =============================================================================

class HTMXHandlers(BaseHandler):
    """HTMX endpoint handlers for origins domain"""
    
    def __init__(self):
        self.template_service = TemplateService()
        self.backup_config = BackupConfig()
        
        # Import services
        from origins.services.manage import OriginOperationsService
        from origins.services.ssh import OriginSSHService
        self.origin_service = OriginOperationsService(self.backup_config)
        self.ssh_service = OriginSSHService()
        
        # Import parser from pages module
        from origins.handlers.pages import origin_parser
        self.origin_parser = origin_parser

    # =========================================================================
    # FORM SUBMISSION HANDLERS
    # =========================================================================

    async def add_ssh_origin_htmx(self, request) -> JSONResponse:
        """Add SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.add_ssh_origin(form_data)

    @handle_page_errors("Add SSH origin")
    def add_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Add new SSH origin"""
        # Parse origin form data (no password required for save operations)
        origin_result = self.origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        
        # Delegate business logic to origin service
        result = self.origin_service.add_new_origin(origin_name, origin_config)
        
        if result['success']:
            return RedirectResponse(url='/origins', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=400)

    async def save_ssh_origin_htmx(self, request) -> JSONResponse:
        """Save SSH origin with form parsing - pure switchboard compliance"""
        # Parse form data using dict() approach (matches current app.py pattern)
        form_data = dict(await request.form())
        
        # Call existing business logic
        return self.save_ssh_origin(form_data)

    @handle_page_errors("Save SSH origin")
    def save_ssh_origin(self, form_data: Dict[str, Any]) -> JSONResponse:
        """Save SSH origin changes"""
        # Parse origin form data (no password required for save operations)
        origin_result = self.origin_parser.parse_origin_form(form_data, require_password=False)
        if not origin_result['valid']:
            return JSONResponse(content={
                'success': False,
                'error': origin_result['error']
            }, status_code=400)
        
        origin_config = origin_result['origin_config']
        origin_name = origin_config['origin_name']
        original_origin_name = self._get_form_value(form_data, 'original_origin_name', '')
        
        # Delegate business logic to origin service
        result = self.origin_service.save_origin_with_rename_handling(origin_name, origin_config, original_origin_name)
        
        if result['success']:
            return RedirectResponse(url='/origins', status_code=302)
        else:
            return JSONResponse(content={
                'success': False,
                'error': result['error']
            }, status_code=500)

    def _get_form_value(self, form_data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Helper to get form value with default"""
        return form_data.get(key, default)


# Export handler instance
origins_htmx = HTMXHandlers()