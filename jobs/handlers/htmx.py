"""
HTMX Utilities for Jobs Handlers

Standardizes repetitive form parsing patterns used across ~16 HTMX handler methods.
Reduces code duplication and improves maintainability.
"""

from typing import Dict, Any, List, Union
from fastapi import Request


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