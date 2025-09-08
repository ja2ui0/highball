"""
Shared Error Handling Decorators
Standardized error handling for handlers and services across domains
"""

import logging
from functools import wraps
from typing import Callable, Any, Dict
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def handle_page_errors(operation_name: str) -> Callable:
    """Decorator to handle common page operation errors consistently for handlers"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"{operation_name} error: {e}")
                return JSONResponse(content={
                    'success': False,
                    'error': str(e)
                }, status_code=500)
        return wrapper
    return decorator


def handle_service_errors(operation_name: str) -> Callable:
    """Decorator to handle common service operation errors consistently for services"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{operation_name} operation error: {e}")
                return {
                    'success': False,
                    'error': f'{operation_name} operation failed: {str(e)}'
                }
        return wrapper
    return decorator