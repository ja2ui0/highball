"""
Rsync Backup Operations Module
Handles rsync-based backup operations for SSH, local, and rsyncd destinations
Separate from Restic operations for clean provider separation
"""

import subprocess
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import shlex
from pydantic import BaseModel, Field

# =============================================================================
# RESPONSE MODELS
# =============================================================================

class RsyncResult(BaseModel):
    """Rsync operation result structure"""
    success: bool
    message: str = ""
    error: str = ""
    stats: Dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    dry_run: bool = False
    return_code: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for backward compatibility"""
        result = {'success': self.success}
        if self.message:
            result['message'] = self.message
        if self.error:
            result['error'] = self.error
        if self.stats:
            result['stats'] = self.stats
        if self.output:
            result['output'] = self.output
        if self.dry_run:
            result['dry_run'] = self.dry_run
        if self.return_code is not None:
            result['return_code'] = self.return_code
        return result

logger = logging.getLogger(__name__)

# =============================================================================
# RSYNC CONFIGURATION
# =============================================================================

class RsyncConfig(BaseModel):
    """Configuration for rsync backup operations"""
    job_name: str = Field(default="unknown")
    source_config: Dict[str, Any] = Field(default_factory=dict)
    dest_config: Dict[str, Any] = Field(default_factory=dict)
    source_type: str = Field(default="local")
    dest_type: str = Field(default="local")
    
    @classmethod
    def from_job_config(cls, job_config: Dict[str, Any]) -> 'RsyncConfig':
        """Create RsyncConfig from job configuration dict"""
        return cls(
            job_name=job_config.get('job_name', 'unknown'),
            source_config=job_config.get('source_config', {}),
            dest_config=job_config.get('dest_config', {}),
            source_type=job_config.get('source_type', 'local'),
            dest_type=job_config.get('dest_type', 'local')
        )
    
    @property
    def is_ssh_source(self) -> bool:
        """Check if source is SSH"""
        return self.source_type == 'ssh'
    
    @property
    def is_ssh_dest(self) -> bool:
        """Check if destination is SSH"""
        return self.dest_type == 'ssh'
    
    @property
    def is_rsyncd_dest(self) -> bool:
        """Check if destination is rsyncd"""
        return self.dest_type == 'rsyncd'

# =============================================================================
# RSYNC ARGUMENT BUILDER
# =============================================================================

class RsyncArgumentBuilder:
    """Builds rsync command arguments for various scenarios"""
    
    @staticmethod
    def build_backup_args(config: RsyncConfig, dry_run: bool = False) -> List[str]:
        """Build rsync backup command arguments"""
        args = []
        
        # Basic rsync options
        args.extend(['-av', '--progress', '--stats'])
        
        if dry_run:
            args.append('--dry-run')
        
        # Include/exclude patterns
        source_paths = config.source_config.get('source_paths', [])
        for path_config in source_paths:
            for include in path_config.get('includes', []):
                args.extend(['--include', include])
            for exclude in path_config.get('excludes', []):
                args.extend(['--exclude', exclude])
        
        # Source paths
        sources = []
        if config.is_ssh_source:
            hostname = config.source_config['hostname']
            username = config.source_config['username']
            for path_config in source_paths:
                sources.append(f"{username}@{hostname}:{path_config['path']}")
        else:
            for path_config in source_paths:
                sources.append(path_config['path'])
        
        args.extend(sources)
        
        # Destination
        if config.is_ssh_dest:
            hostname = config.dest_config['hostname']
            username = config.dest_config['username']
            path = config.dest_config['path']
            args.append(f"{username}@{hostname}:{path}")
        elif config.is_rsyncd_dest:
            hostname = config.dest_config['hostname']
            share = config.dest_config['share']
            args.append(f"{hostname}::{share}")
        else:  # local
            args.append(config.dest_config['path'])
        
        return args

# =============================================================================
# RSYNC RUNNER
# =============================================================================

class RsyncRunner:
    """Executes rsync backup operations"""
    
    def __init__(self):
        self.argument_builder = RsyncArgumentBuilder()
    
    def run_backup(self, config: RsyncConfig, dry_run: bool = False) -> Dict[str, Any]:
        """Execute rsync backup operation"""
        try:
            # Build command
            args = self.argument_builder.build_backup_args(config, dry_run)
            cmd = ['rsync'] + args
            
            logger.info(f"Executing rsync backup: {' '.join(cmd)}")
            
            # Execute rsync
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                stats = self._parse_rsync_stats(result.stdout)
                return RsyncResult(
                    success=True,
                    message='Rsync backup completed successfully' if not dry_run else 'Rsync dry run completed successfully',
                    stats=stats,
                    output=result.stdout,
                    dry_run=dry_run
                ).to_dict()
            else:
                return RsyncResult(
                    success=False,
                    error=f'Rsync backup failed: {result.stderr}',
                    output=result.stdout,
                    return_code=result.returncode
                ).to_dict()
                
        except subprocess.TimeoutExpired:
            return RsyncResult(
                success=False,
                error='Rsync backup timeout (1 hour limit)'
            ).to_dict()
        except Exception as e:
            logger.error(f"Rsync backup error: {e}")
            return RsyncResult(
                success=False,
                error=f'Rsync backup failed: {str(e)}'
            ).to_dict()
    
    def _parse_rsync_stats(self, output: str) -> Dict[str, Any]:
        """Parse rsync statistics from output"""
        stats = {}
        
        lines = output.split('\n')
        for line in lines:
            line = line.strip()
            
            if 'Number of files:' in line:
                # Extract file counts
                parts = line.split()
                if len(parts) >= 4:
                    stats['total_files'] = int(parts[3].replace(',', ''))
            
            elif 'Number of created files:' in line:
                parts = line.split()
                if len(parts) >= 5:
                    stats['created_files'] = int(parts[4].replace(',', ''))
            
            elif 'Number of deleted files:' in line:
                parts = line.split()
                if len(parts) >= 5:
                    stats['deleted_files'] = int(parts[4].replace(',', ''))
            
            elif 'Number of regular files transferred:' in line:
                parts = line.split()
                if len(parts) >= 6:
                    stats['transferred_files'] = int(parts[5].replace(',', ''))
            
            elif 'Total file size:' in line:
                parts = line.split()
                if len(parts) >= 4:
                    stats['total_size'] = int(parts[3].replace(',', ''))
            
            elif 'Total transferred file size:' in line:
                parts = line.split()
                if len(parts) >= 5:
                    stats['transferred_size'] = int(parts[4].replace(',', ''))
        
        return stats

# =============================================================================
# UNIFIED RSYNC SERVICE
# =============================================================================

class RsyncService:
    """Unified rsync service for all rsync-based backup operations"""
    
    def __init__(self):
        self.runner = RsyncRunner()
    
    def execute_backup(self, job_config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Execute rsync backup operation"""
        config = RsyncConfig.from_job_config(job_config)
        return self.runner.run_backup(config, dry_run)
    
    def test_destination(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test rsync destination connectivity"""
        try:
            config = RsyncConfig.from_job_config(job_config)
            
            # Build a simple test command
            if config.is_ssh_dest:
                hostname = config.dest_config['hostname']
                username = config.dest_config['username']
                path = config.dest_config['path']
                
                # Test SSH connectivity and path writability
                cmd = ['ssh', f"{username}@{hostname}", f"test -w '{path}' && echo 'OK'"]
                
            elif config.is_rsyncd_dest:
                hostname = config.dest_config['hostname']
                share = config.dest_config['share']
                
                # Test rsyncd connectivity
                cmd = ['rsync', '--list-only', f"{hostname}::{share}"]
                
            else:  # local
                path = config.dest_config['path']
                
                # Test local path writability
                cmd = ['test', '-w', path]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return RsyncResult(
                    success=True,
                    message='Destination is accessible and writable'
                ).to_dict()
            else:
                return RsyncResult(
                    success=False,
                    error=f'Destination test failed: {result.stderr}'
                ).to_dict()
                
        except subprocess.TimeoutExpired:
            return RsyncResult(
                success=False,
                error='Destination test timeout'
            ).to_dict()
        except Exception as e:
            logger.error(f"Destination test error: {e}")
            return RsyncResult(
                success=False,
                error=f'Destination test failed: {str(e)}'
            ).to_dict()

# Export the service
rsync_service = RsyncService()