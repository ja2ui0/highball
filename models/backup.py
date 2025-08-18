"""
Consolidated Backup Operations Module
Merges all backup provider logic into single module with clean class-based organization
Replaces: restic_runner.py, restic_repository_service.py, restic_argument_builder.py, 
         restic_content_analyzer.py, restic_maintenance_service.py
"""

import subprocess
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import tempfile
import shlex

logger = logging.getLogger(__name__)

# =============================================================================
# BACKUP CONFIGURATION CLASSES
# =============================================================================

class BackupConfig:
    """Base configuration for backup operations"""
    
    def __init__(self, job_config: Dict[str, Any]):
        self.job_config = job_config
        self.job_name = job_config.get('job_name', 'unknown')
        self.source_config = job_config.get('source_config', {})
        self.dest_config = job_config.get('dest_config', {})
        self.source_type = job_config.get('source_type', 'local')
        self.dest_type = job_config.get('dest_type', 'local')
    
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
# RESTIC ARGUMENT BUILDER - Command construction
# =============================================================================

class ResticArgumentBuilder:
    """Builds Restic command arguments for various operations"""
    
    @staticmethod
    def build_backup_args(config: BackupConfig, dry_run: bool = False) -> List[str]:
        """Build backup command arguments"""
        args = []
        
        # Repository and authentication
        args.extend(['-r', config.dest_config['repo_uri']])
        
        # Source paths
        source_paths = config.source_config.get('source_paths', [])
        for path_config in source_paths:
            args.append(path_config['path'])
        
        # Include/exclude patterns
        for path_config in source_paths:
            for include in path_config.get('includes', []):
                args.extend(['--include', include])
            for exclude in path_config.get('excludes', []):
                args.extend(['--exclude', exclude])
        
        # Additional options
        args.extend(['--verbose', '--json'])
        
        if dry_run:
            args.append('--dry-run')
        
        # Job name tag
        args.extend(['--tag', f'job:{config.job_name}'])
        args.extend(['--tag', f'hostname:{config.source_config.get("hostname", "localhost")}'])
        
        return args
    
    @staticmethod
    def build_list_args(repo_uri: str, filters: Optional[Dict[str, Any]] = None) -> List[str]:
        """Build snapshot list command arguments"""
        args = ['-r', repo_uri, 'snapshots', '--json']
        
        if filters:
            if filters.get('job_name'):
                args.extend(['--tag', f'job:{filters["job_name"]}'])
            if filters.get('hostname'):
                args.extend(['--tag', f'hostname:{filters["hostname"]}'])
            if filters.get('latest'):
                args.append('--latest')
                args.append('1')
        
        return args
    
    @staticmethod
    def build_restore_args(repo_uri: str, snapshot_id: str, target_path: str, 
                          include_patterns: List[str] = None, dry_run: bool = False) -> List[str]:
        """Build restore command arguments"""
        args = ['-r', repo_uri, 'restore', snapshot_id, '--target', target_path]
        
        if include_patterns:
            for pattern in include_patterns:
                args.extend(['--include', pattern])
        
        if dry_run:
            args.append('--dry-run')
        
        args.extend(['--verbose', '--verify'])
        
        return args
    
    @staticmethod
    def build_maintenance_args(repo_uri: str, operation: str, config: Dict[str, Any] = None) -> List[str]:
        """Build maintenance operation arguments"""
        args = ['-r', repo_uri]
        
        if operation == 'forget':
            args.append('forget')
            if config:
                retention = config.get('retention_policy', {})
                if retention.get('keep_last'):
                    args.extend(['--keep-last', str(retention['keep_last'])])
                if retention.get('keep_hourly'):
                    args.extend(['--keep-hourly', str(retention['keep_hourly'])])
                if retention.get('keep_daily'):
                    args.extend(['--keep-daily', str(retention['keep_daily'])])
                if retention.get('keep_weekly'):
                    args.extend(['--keep-weekly', str(retention['keep_weekly'])])
                if retention.get('keep_monthly'):
                    args.extend(['--keep-monthly', str(retention['keep_monthly'])])
                if retention.get('keep_yearly'):
                    args.extend(['--keep-yearly', str(retention['keep_yearly'])])
            args.append('--prune')
            
        elif operation == 'check':
            args.append('check')
            if config and config.get('read_data_subset'):
                args.extend(['--read-data-subset', config['read_data_subset']])
                
        elif operation == 'prune':
            args.append('prune')
            
        return args

# =============================================================================
# RESTIC REPOSITORY SERVICE - Repository operations
# =============================================================================

class ResticRepositoryService:
    """Handles Restic repository operations and management"""
    
    def __init__(self):
        self.command_builder = ResticArgumentBuilder()
    
    def test_repository_access(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test repository access and get status information"""
        try:
            dest_config = job_config.get('dest_config', {})
            repo_uri = dest_config.get('repo_uri')
            password = dest_config.get('password')
            
            if not repo_uri or not password:
                return {
                    'success': False,
                    'error': 'Repository URI and password are required'
                }
            
            # Set environment
            env = os.environ.copy()
            env['RESTIC_PASSWORD'] = password
            
            # Test repository access with snapshots list
            cmd = ['restic', '-r', repo_uri, 'snapshots', '--json']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            if result.returncode == 0:
                # Repository exists and is accessible
                try:
                    snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                    snapshot_count = len(snapshots)
                    
                    latest_backup = None
                    if snapshots:
                        # Get most recent snapshot
                        latest_snapshot = max(snapshots, key=lambda s: s['time'])
                        latest_backup = latest_snapshot['time']
                    
                    return {
                        'success': True,
                        'repository_status': 'existing' if snapshot_count > 0 else 'empty',
                        'snapshot_count': snapshot_count,
                        'latest_backup': latest_backup,
                        'repository_uri': repo_uri
                    }
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'repository_status': 'empty',
                        'snapshot_count': 0,
                        'repository_uri': repo_uri
                    }
            else:
                # Check if repository doesn't exist vs other error
                if 'unable to open config file' in result.stderr or 'repository does not exist' in result.stderr:
                    return {
                        'success': False,
                        'error': 'Repository does not exist - needs initialization',
                        'needs_init': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Repository access failed: {result.stderr}'
                    }
                    
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Repository access timeout - check connection'
            }
        except Exception as e:
            logger.error(f"Repository test error: {e}")
            return {
                'success': False,
                'error': f'Repository test failed: {str(e)}'
            }
    
    def initialize_repository(self, dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize a new Restic repository"""
        try:
            repo_uri = dest_config.get('repo_uri')
            password = dest_config.get('password')
            
            if not repo_uri or not password:
                return {
                    'success': False,
                    'error': 'Repository URI and password are required'
                }
            
            # Set environment
            env = os.environ.copy()
            env['RESTIC_PASSWORD'] = password
            
            # Initialize repository
            cmd = ['restic', '-r', repo_uri, 'init']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env=env
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Repository initialized successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Repository initialization failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Repository initialization timeout'
            }
        except Exception as e:
            logger.error(f"Repository initialization error: {e}")
            return {
                'success': False,
                'error': f'Initialization failed: {str(e)}'
            }
    
    def list_snapshots(self, dest_config: Dict[str, Any], filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List repository snapshots with optional filtering"""
        try:
            repo_uri = dest_config.get('repo_uri')
            password = dest_config.get('password')
            
            if not repo_uri or not password:
                return {
                    'success': False,
                    'error': 'Repository URI and password are required'
                }
            
            # Set environment
            env = os.environ.copy()
            env['RESTIC_PASSWORD'] = password
            
            # Build command
            args = self.command_builder.build_list_args(repo_uri, filters)
            cmd = ['restic'] + args
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            if result.returncode == 0:
                try:
                    snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                    return {
                        'success': True,
                        'snapshots': snapshots,
                        'count': len(snapshots)
                    }
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'snapshots': [],
                        'count': 0
                    }
            else:
                return {
                    'success': False,
                    'error': f'Failed to list snapshots: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Snapshot listing timeout'
            }
        except Exception as e:
            logger.error(f"Snapshot listing error: {e}")
            return {
                'success': False,
                'error': f'Snapshot listing failed: {str(e)}'
            }

# =============================================================================
# RESTIC CONTENT ANALYZER - Repository content analysis
# =============================================================================

class ResticContentAnalyzer:
    """Analyzes Restic repository content and provides insights"""
    
    def __init__(self):
        self.repository_service = ResticRepositoryService()
    
    def analyze_repository_content(self, dest_config: Dict[str, Any], job_name: str = None) -> Dict[str, Any]:
        """Analyze repository content for a specific job"""
        try:
            # Get snapshots for this job
            filters = {'job_name': job_name} if job_name else None
            snapshots_result = self.repository_service.list_snapshots(dest_config, filters)
            
            if not snapshots_result['success']:
                return snapshots_result
            
            snapshots = snapshots_result['snapshots']
            
            if not snapshots:
                return {
                    'success': True,
                    'analysis': {
                        'snapshot_count': 0,
                        'size_stats': None,
                        'frequency_stats': None,
                        'latest_snapshot': None
                    }
                }
            
            # Analyze snapshot metadata
            analysis = {
                'snapshot_count': len(snapshots),
                'size_stats': self._analyze_size_trends(snapshots),
                'frequency_stats': self._analyze_backup_frequency(snapshots),
                'latest_snapshot': self._get_latest_snapshot_info(snapshots)
            }
            
            return {
                'success': True,
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Content analysis error: {e}")
            return {
                'success': False,
                'error': f'Content analysis failed: {str(e)}'
            }
    
    def _analyze_size_trends(self, snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze backup size trends"""
        if not snapshots:
            return None
        
        sizes = []
        for snapshot in snapshots:
            if 'summary' in snapshot and 'total_bytes_processed' in snapshot['summary']:
                sizes.append(snapshot['summary']['total_bytes_processed'])
        
        if not sizes:
            return None
        
        return {
            'average_size': sum(sizes) / len(sizes),
            'min_size': min(sizes),
            'max_size': max(sizes),
            'latest_size': sizes[-1] if sizes else 0
        }
    
    def _analyze_backup_frequency(self, snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze backup frequency patterns"""
        if len(snapshots) < 2:
            return None
        
        # Sort by time
        sorted_snapshots = sorted(snapshots, key=lambda s: s['time'])
        
        intervals = []
        for i in range(1, len(sorted_snapshots)):
            prev_time = datetime.fromisoformat(sorted_snapshots[i-1]['time'].replace('Z', '+00:00'))
            curr_time = datetime.fromisoformat(sorted_snapshots[i]['time'].replace('Z', '+00:00'))
            intervals.append((curr_time - prev_time).total_seconds())
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            return {
                'average_interval_hours': avg_interval / 3600,
                'min_interval_hours': min(intervals) / 3600,
                'max_interval_hours': max(intervals) / 3600
            }
        
        return None
    
    def _get_latest_snapshot_info(self, snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get detailed info about the latest snapshot"""
        if not snapshots:
            return None
        
        latest = max(snapshots, key=lambda s: s['time'])
        
        return {
            'id': latest.get('short_id', latest.get('id', 'unknown')),
            'time': latest['time'],
            'hostname': latest.get('hostname'),
            'paths': latest.get('paths', []),
            'tags': latest.get('tags', [])
        }

# =============================================================================
# RESTIC RUNNER - Backup execution
# =============================================================================

class ResticRunner:
    """Executes Restic backup operations with proper environment and error handling"""
    
    def __init__(self):
        self.argument_builder = ResticArgumentBuilder()
        self.repository_service = ResticRepositoryService()
    
    def run_backup(self, config: BackupConfig, dry_run: bool = False) -> Dict[str, Any]:
        """Execute Restic backup with comprehensive error handling"""
        try:
            # Validate configuration
            if not config.is_restic_backup:
                return {
                    'success': False,
                    'error': 'Not a Restic backup configuration'
                }
            
            # Build backup command
            backup_args = self.argument_builder.build_backup_args(config, dry_run)
            
            # Determine execution context (local vs SSH with container)
            if config.is_ssh_source and config.container_runtime:
                return self._run_container_backup(config, backup_args, dry_run)
            else:
                return self._run_local_backup(config, backup_args, dry_run)
                
        except Exception as e:
            logger.error(f"Backup execution error: {e}")
            return {
                'success': False,
                'error': f'Backup execution failed: {str(e)}'
            }
    
    def _run_local_backup(self, config: BackupConfig, backup_args: List[str], dry_run: bool) -> Dict[str, Any]:
        """Run backup locally"""
        try:
            # Set environment
            env = os.environ.copy()
            env['RESTIC_PASSWORD'] = config.dest_config['password']
            
            # Execute backup
            cmd = ['restic', 'backup'] + backup_args
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
                env=env
            )
            
            return self._process_backup_result(result, dry_run)
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Backup operation timeout (1 hour limit)'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Local backup failed: {str(e)}'
            }
    
    def _run_container_backup(self, config: BackupConfig, backup_args: List[str], dry_run: bool) -> Dict[str, Any]:
        """Run backup using container on remote SSH host"""
        try:
            # Use command execution service for container operations
            from services.execution import ExecutionService
            
            exec_service = ExecutionService()
            
            # Build container command
            container_args = [
                'backup',
                '-r', config.dest_config['repo_uri']
            ] + backup_args[2:]  # Skip the repo_uri we already added
            
            # Execute via container
            result = exec_service.execute_restic_command(
                config.job_config,
                container_args,
                env_vars={'RESTIC_PASSWORD': config.dest_config['password']}
            )
            
            if result['success']:
                return {
                    'success': True,
                    'message': 'Container backup completed successfully',
                    'output': result.get('output', ''),
                    'dry_run': dry_run
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Container backup failed'),
                    'output': result.get('output', '')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Container backup failed: {str(e)}'
            }
    
    def _process_backup_result(self, result: subprocess.CompletedProcess, dry_run: bool) -> Dict[str, Any]:
        """Process backup command result"""
        if result.returncode == 0:
            # Parse JSON output if available
            backup_stats = self._parse_backup_output(result.stdout)
            
            return {
                'success': True,
                'message': 'Backup completed successfully' if not dry_run else 'Dry run completed successfully',
                'stats': backup_stats,
                'output': result.stdout,
                'dry_run': dry_run
            }
        else:
            return {
                'success': False,
                'error': f'Backup failed: {result.stderr}',
                'output': result.stdout,
                'return_code': result.returncode
            }
    
    def _parse_backup_output(self, output: str) -> Dict[str, Any]:
        """Parse JSON output from Restic backup"""
        try:
            lines = output.strip().split('\n')
            for line in reversed(lines):  # Start from the end
                if line.strip().startswith('{'):
                    data = json.loads(line)
                    if data.get('message_type') == 'summary':
                        return {
                            'files_new': data.get('files_new', 0),
                            'files_changed': data.get('files_changed', 0),
                            'files_unmodified': data.get('files_unmodified', 0),
                            'dirs_new': data.get('dirs_new', 0),
                            'dirs_changed': data.get('dirs_changed', 0),
                            'data_added': data.get('data_added', 0),
                            'total_bytes_processed': data.get('total_bytes_processed', 0)
                        }
        except (json.JSONDecodeError, KeyError):
            pass
        
        return {}

# =============================================================================
# RESTIC MAINTENANCE SERVICE - Repository maintenance
# =============================================================================

class ResticMaintenanceService:
    """Handles Restic repository maintenance operations"""
    
    def __init__(self):
        self.argument_builder = ResticArgumentBuilder()
    
    def run_maintenance_operation(self, dest_config: Dict[str, Any], operation: str, 
                                config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run maintenance operation on repository"""
        try:
            repo_uri = dest_config.get('repo_uri')
            password = dest_config.get('password')
            
            if not repo_uri or not password:
                return {
                    'success': False,
                    'error': 'Repository URI and password are required'
                }
            
            # Set environment
            env = os.environ.copy()
            env['RESTIC_PASSWORD'] = password
            
            # Build command
            args = self.argument_builder.build_maintenance_args(repo_uri, operation, config)
            cmd = ['restic'] + args
            
            # Execute maintenance operation
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout
                env=env
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'operation': operation,
                    'message': f'{operation.capitalize()} operation completed successfully',
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'operation': operation,
                    'error': f'{operation.capitalize()} operation failed: {result.stderr}',
                    'output': result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'operation': operation,
                'error': f'{operation.capitalize()} operation timeout (30 minute limit)'
            }
        except Exception as e:
            logger.error(f"Maintenance operation {operation} error: {e}")
            return {
                'success': False,
                'operation': operation,
                'error': f'{operation.capitalize()} operation failed: {str(e)}'
            }

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
        """Execute backup operation"""
        config = BackupConfig(job_config)
        
        if config.is_restic_backup:
            return self.restic_runner.run_backup(config, dry_run)
        else:
            return {
                'success': False,
                'error': f'Backup type {config.dest_type} not supported by unified service'
            }
    
    def test_repository(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test repository access"""
        return self.repository_service.test_repository_access(job_config)
    
    def initialize_repository(self, dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize new repository"""
        return self.repository_service.initialize_repository(dest_config)
    
    def list_snapshots(self, dest_config: Dict[str, Any], filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List repository snapshots"""
        return self.repository_service.list_snapshots(dest_config, filters)
    
    def analyze_content(self, dest_config: Dict[str, Any], job_name: str = None) -> Dict[str, Any]:
        """Analyze repository content"""
        return self.content_analyzer.analyze_repository_content(dest_config, job_name)
    
    def run_maintenance(self, dest_config: Dict[str, Any], operation: str, 
                       config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run maintenance operation"""
        return self.maintenance_service.run_maintenance_operation(dest_config, operation, config)

# Export the unified service as the main interface
backup_service = BackupService()