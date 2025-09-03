"""
TRANSIENT FILE - TO BE DELETED AFTER JOB FORM REBUILD

Legacy form data structures from models/forms.py that will be discarded
after the job form is rebuilt to use dropdown selection of pre-defined
origins and destinations instead of inline definition.

This file exists temporarily to keep define.py working during the transition.
DELETE THIS FILE once the new job form using dropdown selection is complete.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from models.forms import safe_get_value


# =============================================================================
# TRANSIENT FORM DATA STRUCTURES - TO BE DISCARDED
# =============================================================================

class SourceConfig(BaseModel):
    """TRANSIENT: Form concern - source configuration data structure"""
    source_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    
    # Multi-path support
    source_paths: List[Dict[str, Any]] = Field(default_factory=list)


class DestConfig(BaseModel):
    """TRANSIENT: Form concern - standard destination configuration data structure"""
    dest_type: str = ""
    local_path: str = ""
    ssh_hostname: str = ""
    ssh_username: str = ""
    ssh_path: str = ""
    rsyncd_hostname: str = ""
    rsyncd_share: str = ""
    rsync_options: str = ""


class ResticConfig(BaseModel):
    """TRANSIENT: Form concern - Restic repository configuration data structure"""
    repo_type: str = ""
    password: str = ""
    
    # Repository type specific fields
    local_path: str = ""
    
    # REST fields
    rest_hostname: str = ""
    rest_port: str = "8000"
    rest_path: str = ""
    rest_use_root: bool = False
    rest_use_https: bool = True
    rest_username: str = ""
    rest_password: str = ""
    
    # S3 fields
    s3_bucket: str = ""
    s3_region: str = ""
    s3_prefix: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint: str = ""
    
    # SFTP fields
    sftp_hostname: str = ""
    sftp_path: str = ""
    
    # Rclone fields
    rclone_config: str = ""


class JobFormData(BaseModel):
    """TRANSIENT: Form concern - complete job form data structure"""
    job_name: str = ""
    source_config: SourceConfig = Field(default_factory=SourceConfig)
    dest_config: DestConfig = Field(default_factory=DestConfig)
    restic_config: ResticConfig = Field(default_factory=ResticConfig)
    schedule: str = ""
    enabled: bool = True
    respect_conflicts: bool = True
    restic_maintenance: str = "auto"
    notifications: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# TEMPORARY PARSERS - Used during job form revamp transition  
# =============================================================================

class SourceParser:
    """Parse source configurations (SSH, local) - temporary location during revamp"""
    
    @staticmethod
    def parse_ssh_source(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SSH source configuration"""
        hostname = safe_get_value(form_data, 'hostname')
        username = safe_get_value(form_data, 'username')
        
        if not hostname:
            return {'valid': False, 'error': 'SSH hostname is required'}
        if not username:
            return {'valid': False, 'error': 'SSH username is required'}
        
        config = {
            'hostname': hostname.strip(),
            'username': username.strip()
        }
        
        # Include container runtime if detected during validation
        container_runtime = safe_get_value(form_data, 'container_runtime')
        if container_runtime:
            config['container_runtime'] = container_runtime
        
        return {'valid': True, 'config': config}
    
    @staticmethod
    def parse_local_source(form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse local source configuration"""
        # Local sources need minimal configuration
        return {'valid': True, 'config': {}}