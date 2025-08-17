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

logger = logging.getLogger(__name__)

# =============================================================================
# RSYNC CONFIGURATION
# =============================================================================

class RsyncConfig:
    """Configuration for rsync backup operations"""
    
    def __init__(self, job_config: Dict[str, Any]):
        self.job_config = job_config
        self.job_name = job_config.get('job_name', 'unknown')
        self.source_config = job_config.get('source_config', {})
        self.dest_config = job_config.get('dest_config', {})
        self.source_type = job_config.get('source_type', 'local')
        self.dest_type = job_config.get('dest_type', 'local')
    
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
                return {
                    'success': True,
                    'message': 'Rsync backup completed successfully' if not dry_run else 'Rsync dry run completed successfully',
                    'stats': stats,
                    'output': result.stdout,
                    'dry_run': dry_run
                }
            else:
                return {
                    'success': False,
                    'error': f'Rsync backup failed: {result.stderr}',
                    'output': result.stdout,
                    'return_code': result.returncode
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Rsync backup timeout (1 hour limit)'
            }
        except Exception as e:
            logger.error(f"Rsync backup error: {e}")
            return {
                'success': False,
                'error': f'Rsync backup failed: {str(e)}'
            }
    
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
        config = RsyncConfig(job_config)
        return self.runner.run_backup(config, dry_run)
    
    def test_destination(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test rsync destination connectivity"""
        try:
            config = RsyncConfig(job_config)
            
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
                return {
                    'success': True,
                    'message': 'Destination is accessible and writable'
                }
            else:
                return {
                    'success': False,
                    'error': f'Destination test failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Destination test timeout'
            }
        except Exception as e:
            logger.error(f"Destination test error: {e}")
            return {
                'success': False,
                'error': f'Destination test failed: {str(e)}'
            }

# Export the service
rsync_service = RsyncService()