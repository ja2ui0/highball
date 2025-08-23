"""
Core Backup Operations Module
Contains core backup orchestration classes and utilities
Schema definitions moved to models/schemas.py
Command builders moved to models/builders.py
Service classes moved to services/restic.py
"""

import subprocess
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import tempfile
from functools import wraps
import shlex
from pydantic import BaseModel, Field
from services.execution import OperationType

# Import extracted modules
from models.schemas import SOURCE_PATH_SCHEMA
from models.builders import ResticArgumentBuilder
from services.restic import ResticRunner, ResticRepositoryService, ResticContentAnalyzer, ResticMaintenanceService

logger = logging.getLogger(__name__)

# =============================================================================
# COMMAND EXECUTION DATA STRUCTURES
# =============================================================================

class CommandInfo(BaseModel):
    """Information about built backup command"""
    exec_argv: List[str]
    log_cmd_str: str
    src_display: str
    dst_display: str

# =============================================================================
# BACKUP CONFIGURATION CLASSES
# =============================================================================

class BackupConfig(BaseModel):
    """Base configuration for backup operations"""
    job_name: str = Field(default="unknown")
    source_config: Dict[str, Any] = Field(default_factory=dict)
    dest_config: Dict[str, Any] = Field(default_factory=dict)
    source_type: str = Field(default="local")
    dest_type: str = Field(default="local")
    
    @classmethod
    def from_job_config(cls, job_config: Dict[str, Any]) -> 'BackupConfig':
        """Create BackupConfig from job configuration dict"""
        return cls(
            job_name=job_config.get('job_name', 'unknown'),
            source_config=job_config.get('source_config', {}),
            dest_config=job_config.get('dest_config', {}),
            source_type=job_config.get('source_type', 'local'),
            dest_type=job_config.get('dest_type', 'local')
        )
    
    @property
    def is_restic_backup(self) -> bool:
        """Check if this is a Restic backup job"""
        return self.dest_type == 'restic'
    
    @property
    def is_ssh_source(self) -> bool:
        """Check if source is SSH"""
        return self.source_type == 'ssh'
    
    @property
    def container_runtime(self) -> Optional[str]:
        """Get container runtime for SSH sources"""
        return self.source_config.get('container_runtime')

# =============================================================================
# UNIFIED BACKUP SERVICE - Main interface
# =============================================================================

class BackupService:
    """Unified backup service - single entry point for all backup operations"""
    
    def __init__(self):
        self.restic_runner = ResticRunner()
        self.repository_service = ResticRepositoryService()
        self.content_analyzer = ResticContentAnalyzer()
        self.maintenance_service = ResticMaintenanceService()
    
    def execute_backup(self, job_config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Execute backup operation using unified ResticExecutionService"""
        config = BackupConfig.from_job_config(job_config)
        
        if config.is_restic_backup:
            # Use ResticRepositoryService which has ResticExecutionService integration
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            # Build backup arguments using the existing argument builder
            backup_args = self.restic_runner.argument_builder.build_backup_args(config, dry_run)
            
            # Use ResticRepositoryService for proper SSH execution
            return self.repository_service.run_backup_unified(dest_config, source_config, backup_args)
        else:
            return {
                'success': False,
                'error': f'Backup type {config.dest_type} not supported by unified service'
            }
    
    def test_repository_connection(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test repository connection using appropriate service"""
        config = BackupConfig.from_job_config(job_config)
        
        if config.is_restic_backup:
            return self.repository_service.test_repository_access(job_config)
        else:
            return {
                'success': False,
                'error': f'Repository test not supported for {config.dest_type}'
            }
    
    def list_snapshots(self, job_config: Dict[str, Any], filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List snapshots using appropriate service"""
        config = BackupConfig.from_job_config(job_config)
        
        if config.is_restic_backup:
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            return self.repository_service.list_snapshots_with_ssh(dest_config, source_config, filters)
        else:
            return {
                'success': False,
                'error': f'Snapshot listing not supported for {config.dest_type}'
            }

# =============================================================================
# MODULE EXPORTS - Backward compatibility
# =============================================================================

# Create a module-level backup service instance for backward compatibility
backup_service = BackupService()