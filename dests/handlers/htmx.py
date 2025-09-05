"""
HTMX Handlers for Destinations Domain

Contains all HTMX endpoint handlers following jobs domain pattern.
Handlers parse form data and delegate to destinations_handler for business logic.
"""

from typing import Dict, Any, Callable
from functools import wraps
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse


# =============================================================================
# **ERROR HANDLING DECORATOR**
# =============================================================================

def handle_page_errors(operation_name: str) -> Callable:
    """Error handling decorator for HTMX handlers"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"Error in {operation_name}: {str(e)}")
                # Return error HTML for HTMX requests
                error_html = f'<div class="error">Error in {operation_name}: {str(e)}</div>'
                return HTMLResponse(content=error_html, status_code=500)
        return wrapper
    return decorator


# =============================================================================
# **HTMX HANDLERS CLASS**
# =============================================================================

class HTMXHandlers:
    """HTMX endpoint handlers for destinations domain"""
    
    def __init__(self):
        # Import destinations handler for delegation
        from dests.handlers.pages import DestinationsHandler
        self.destinations_handler = DestinationsHandler()
    
    # =========================================================================
    # **FORM PARSING WRAPPERS** - Batch 1
    # =========================================================================
    
    @handle_page_errors("Add destination")
    async def add_destination_htmx(self, request) -> JSONResponse:
        """Add destination with form parsing - delegates to destinations_handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to main handler business logic
        return self.destinations_handler.add_destination(form_data)
    
    @handle_page_errors("Save destination")
    async def save_destination_htmx(self, request) -> JSONResponse:
        """Save destination with form parsing - delegates to destinations_handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to main handler business logic
        return self.destinations_handler.save_destination(form_data)
    
    @handle_page_errors("Validate destination")
    async def validate_destination_htmx(self, request) -> HTMLResponse:
        """Validate destination with form parsing - delegates to destinations_handler"""
        # Parse form data using dict() approach (matches current pattern)
        form_data = dict(await request.form())
        
        # Delegate to main handler business logic
        return self.destinations_handler.validate_destination(form_data)


# Export handler instance
destinations_htmx = HTMXHandlers()