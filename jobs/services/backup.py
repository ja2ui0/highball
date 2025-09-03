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
from services.exec import OperationType

# Import extracted modules
from origins.schema import SOURCE_PATH_SCHEMA
from services.exec import ResticArgumentBuilder
from dests.services.restic import ResticRunner, ResticRepositoryService, ResticContentAnalyzer, ResticMaintenanceService

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
# BACKUP ORCHESTRATION SERVICE
# =============================================================================

class BackupOrchestrationService:
    """Orchestrates backup job execution with validation, conflict checking, and threading"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        from jobs.services.manage import JobManagementService
        self.job_management = JobManagementService(backup_config)
    
    def run_backup_job(self, job_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """Execute backup job with full orchestration"""
        try:
            if not job_name:
                return {
                    'success': False,
                    'error': 'Job name is required'
                }
            
            jobs = self.backup_config.get_backup_jobs()
            if job_name not in jobs:
                return {
                    'success': False,
                    'error': f"Job '{job_name}' not found"
                }
            
            job_config = jobs[job_name]
            # Add job name to config for proper tagging
            job_config['job_name'] = job_name
            
            # Check if job is enabled
            if not job_config.get('enabled', True):
                return {
                    'success': False,
                    'error': f"Job '{job_name}' is disabled"
                }
            
            # Check for conflicts if required
            if job_config.get('respect_conflicts', True):
                conflicts = self.job_management.check_conflicts(job_name)
                if conflicts:
                    return {
                        'success': False,
                        'error': f"Job '{job_name}' conflicts with running jobs: {', '.join(conflicts)}"
                    }
            
            # Start backup via JobManagementService in background thread
            import threading
            backup_thread = threading.Thread(
                target=self.job_management.run_backup_job_async,
                args=(job_name, job_config, dry_run)
            )
            backup_thread.daemon = True
            backup_thread.start()
            
            # Send immediate response
            status_message = f"{'Dry run' if dry_run else 'Backup'} started for job '{job_name}'"
            return {
                'success': True,
                'message': status_message,
                'job_name': job_name,
                'dry_run': dry_run
            }
            
        except Exception as e:
            logger.error(f"Backup job error: {e}")
            return {
                'success': False,
                'error': f'Backup error: {str(e)}'
            }

# =============================================================================
# MODULE EXPORTS - Backward compatibility
# =============================================================================

# Create a module-level backup service instance for backward compatibility
backup_service = BackupService()