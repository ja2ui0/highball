"""
Consolidated Form Parsing Module
Merges all form parsers into single module with clean class-based organization
Replaces: job_form_parser.py, ssh_form_parser.py, restic_form_parser.py, local_form_parser.py, 
         rsyncd_form_parser.py, notification_form_parser.py, maintenance_form_parser.py
Also includes form data structures moved from services/form_data_service.py
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# UTILITY FUNCTIONS - Common form parsing helpers
# =============================================================================

def safe_get_list(data: Dict[str, Any], key: str) -> List[str]:
    """Safely get list from form data regardless of format"""
    if hasattr(data, 'getlist'):
        return data.getlist(key)
    else:
        value = data.get(key, [])
        return value if isinstance(value, list) else [value]

def safe_get_value(data: Dict[str, Any], key: str, default: str = '') -> str:
    """Safely get single value from form data"""
    values = safe_get_list(data, key)
    return values[0] if values and values[0] else default

def parse_lines(text: str) -> List[str]:
    """Parse textarea input into list of non-empty lines"""
    return [line.strip() for line in text.split('\n') if line.strip()]

# =============================================================================
# SOURCE CONFIGURATION PARSERS
# =============================================================================

# SOURCE PARSER MOVED TO jobs/handlers/old.py

# =============================================================================
# UNIFIED JOB PARSER - Main entry point
# =============================================================================

# JOB FORM PARSER MOVED TO jobs/handlers/old.py


# =============================================================================
# EXPORTS - Clean interface
# =============================================================================

# Create instances for easy import
# job_parser moved to jobs/handlers/old.py
# source_parser moved to jobs/handlers/old.py
