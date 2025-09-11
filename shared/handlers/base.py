"""
Shared Base Handler
Base class for handlers with common rendering and form parsing utilities
"""

from typing import Dict, Any
from fastapi.responses import HTMLResponse


class BaseHandler:
    """Base class for handlers with shared rendering and form parsing helpers"""
    
    def _render_html(self, template: str, context: dict) -> HTMLResponse:
        """Helper to render template and return HTMLResponse"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html)
    
    def _render_error(self, template: str, context: dict, status: int = 400) -> HTMLResponse:
        """Helper to render error template and return HTMLResponse with status"""
        html = self.template_service.render_template(template, **context)
        return HTMLResponse(content=html, status_code=status)
    
    def _get_form_value(self, form_data: Dict[str, Any], field_name: str, default: str = '') -> str:
        """Helper to get form value with default - handles HTMX list format"""
        value = form_data.get(field_name, default)
        # Handle list format from HTMX form parsing
        if isinstance(value, list) and len(value) > 0:
            return value[0]
        return value if isinstance(value, str) else default