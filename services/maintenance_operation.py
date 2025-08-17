"""
Maintenance operation data structures
Defines the contract for maintenance operations
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass 
class MaintenanceOperation:
    """Represents a maintenance operation to be executed"""
    operation_type: str  # 'discard' (forget+prune combined) or 'check'
    job_name: str
    repository_url: str
    environment_vars: Dict[str, str]
    ssh_config: Optional[Dict[str, str]] = None
    container_runtime: str = "docker"
    retention_config: Optional[Dict[str, Any]] = None
    check_config: Optional[Dict[str, Any]] = None


@dataclass
class MaintenanceResult:
    """Result of a maintenance operation"""
    operation_type: str
    job_name: str
    success: bool
    duration_seconds: float = 0.0
    output: str = ""
    error_message: Optional[str] = None