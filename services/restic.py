"""
Restic Service Module
Contains all Restic-specific service classes for repository operations, content analysis, and maintenance
Extracted from models/backup.py
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

# Import dependencies
from services.execution import OperationType, ResticExecutionService
from models.builders import ResticArgumentBuilder
from models.schemas import RESTIC_REPOSITORY_TYPE_SCHEMAS

logger = logging.getLogger(__name__)

# Import the error handling decorator
def handle_restic_service_errors(operation_name: str):
    """Decorator to handle common restic service operation errors consistently"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Restic {operation_name} error: {e}")
                return {
                    'success': False,
                    'error': f'{operation_name} failed: {str(e)}'
                }
        return wrapper
    return decorator


# =============================================================================
# RESTIC REPOSITORY SERVICE - Repository operations
# =============================================================================

class ResticRepositoryService:
    """Handles Restic repository operations and management"""
    
    def __init__(self):
        self.command_builder = ResticArgumentBuilder()
        from services.execution import ResticExecutionService
        self.restic_executor = ResticExecutionService()
    
    def _validate_required_fields(self, dest_config: Dict[str, Any]) -> None:
        """Validate required fields exist or raise exception with actionable message"""
        from models.schemas import DESTINATION_TYPE_SCHEMAS
        
        schema = DESTINATION_TYPE_SCHEMAS.get('restic', {})
        required_fields = schema.get('required_fields', [])
        
        for field in required_fields:
            if not dest_config.get(field):
                raise ValueError(f'{schema.get("display_name", "Restic")} repository missing {field}')
        
        # If we reach here, all validation passed
    
    @handle_restic_service_errors("repository access test")
    def test_repository_access(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test repository access and get status information"""
        dest_config = job_config.get('dest_config', {})
        source_config = job_config.get('source_config', {})
        
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Execute using unified ResticExecutionService
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=['snapshots', '--json'],
            source_config=source_config,
            operation_type=OperationType.UI,
            timeout=30
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
    
    @handle_restic_service_errors("repository initialization")
    def initialize_repository(self, dest_config: Dict[str, Any], source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Initialize a new Restic repository"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Execute using unified ResticExecutionService
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=['init'],
            source_config=source_config,
            operation_type=OperationType.INIT,
            timeout=60
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

    def run_backup_unified(self, dest_config: Dict[str, Any], source_config: Dict[str, Any], backup_args: List[str]) -> Dict[str, Any]:
        """Run backup using unified ResticExecutionService (supports same_as_origin)"""
        try:
            # Execute using unified ResticExecutionService
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=backup_args,
                source_config=source_config,
                operation_type=OperationType.BACKUP
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Backup completed successfully',
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': f'Backup failed: {result.stderr}',
                    'output': result.stdout
                }
                
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return {
                'success': False,
                'error': f'Backup execution failed: {str(e)}'
            }
    
    @handle_restic_service_errors("snapshot listing")
    def list_snapshots(self, dest_config: Dict[str, Any], filters: Dict[str, Any] = None, source_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List repository snapshots with optional filtering"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Build command args
        args = self.command_builder.build_list_args(repo_uri, filters)
        # Remove 'restic' and repo args since ResticExecutionService handles them
        command_args = []
        skip_next = False
        for i, arg in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if arg == '-r':
                skip_next = True  # skip the repo URI
                continue
            command_args.append(arg)
        
        # Execute using unified ResticExecutionService  
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=command_args,
            source_config=source_config,
            operation_type=OperationType.UI,
            timeout=30
        )
        
        if result.returncode == 0:
            try:
                raw_snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                # Format snapshots for backup browser expectations
                formatted_snapshots = []
                for snapshot in raw_snapshots:
                    formatted_snapshot = {
                        'full_id': snapshot.get('id', ''),
                        'id': snapshot.get('short_id', snapshot.get('id', '')[:8] if snapshot.get('id') else ''),
                        'time': snapshot.get('time', ''),
                        'username': snapshot.get('username', ''),
                        'hostname': snapshot.get('hostname', ''),
                        'paths': snapshot.get('paths', []),
                        'summary': snapshot.get('summary', {}),
                        'tree': snapshot.get('tree', ''),
                        'program_version': snapshot.get('program_version', '')
                    }
                    formatted_snapshots.append(formatted_snapshot)
                
                return {
                    'success': True,
                    'snapshots': formatted_snapshots,
                    'count': len(formatted_snapshots)
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
    
    @handle_restic_service_errors("SSH snapshot listing")
    def list_snapshots_with_ssh(self, dest_config: Dict[str, Any], source_config: Dict[str, Any], filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List snapshots with SSH execution support (like working code)"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Check if we should use SSH execution
        # For same_as_origin repositories, always use SSH (repository is on origin host)
        if (dest_config.get('repo_type') == 'same_as_origin' or 
            (source_config and source_config.get('hostname') and source_config.get('username'))):
            return self._list_snapshots_via_ssh(repo_uri, password, source_config, dest_config)
        else:
            # Fall back to local execution
            return self.list_snapshots(dest_config, filters)
    
    def _execute_template_variables(self, variables: Dict[str, str], context: Dict[str, Any]) -> Dict[str, str]:
        """Execute template variable transformations"""
        resolved = {}
        for var_name, template in variables.items():
            if template.startswith('remove_prefix '):
                # Format: "remove_prefix rest: {repo_uri}"
                parts = template.split(' ', 2)
                prefix = parts[1]
                source_var = parts[2].strip('{}')
                source_value = context.get(source_var, '')
                resolved[var_name] = source_value[len(prefix):] if source_value.startswith(prefix) else source_value
            elif template.startswith('dirname '):
                # Format: "dirname {local_path}"
                source_var = template.split(' ', 1)[1].strip('{}')
                source_value = context.get(source_var, '')
                from pathlib import Path
                resolved[var_name] = str(Path(source_value).parent)
            else:
                # Direct template substitution
                resolved[var_name] = template.format(**context)
        return resolved

    def _quick_repository_check(self, repo_uri: str, dest_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Schema-driven quick check for repository accessibility"""
        repo_type = dest_config.get('repo_type')
        
        if not repo_type or repo_type not in RESTIC_REPOSITORY_TYPE_SCHEMAS:
            return True, "Unknown repository type, skipping check"
        
        schema = RESTIC_REPOSITORY_TYPE_SCHEMAS[repo_type]
        quick_check = schema.get('quick_check')
        
        if not quick_check:
            return True, "No quick check defined for this repository type"
        
        try:
            # Prepare context with repo_uri and all dest_config fields
            context = dict(dest_config)
            context['repo_uri'] = repo_uri
            
            # Check if we should skip due to empty required fields
            skip_if_empty = quick_check.get('skip_if_empty', [])
            for field in skip_if_empty:
                if not context.get(field):
                    return True, f"Skipping check: {field} not specified"
            
            # Execute template variables if defined
            variables = quick_check.get('variables', {})
            if variables:
                resolved_vars = self._execute_template_variables(variables, context)
                context.update(resolved_vars)
            
            # Build command with template substitution
            command_template = quick_check['command']
            command = [arg.format(**context) for arg in command_template]
            
            # Prepare environment variables
            env = os.environ.copy()
            env_template = quick_check.get('env', {})
            for env_key, env_value in env_template.items():
                env[env_key] = env_value.format(**context)
            
            # Execute command
            timeout = quick_check.get('timeout', 10)
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
            
            # Check expected results
            if 'expected_returncode' in quick_check:
                expected_code = quick_check['expected_returncode']
                success = result.returncode == expected_code
                if success:
                    return success, f"Command returned {result.returncode} (expected: {expected_code})"
                else:
                    error_details = f"Command returned {result.returncode} (expected: {expected_code})"
                    if result.stderr:
                        error_details += f" - stderr: {result.stderr.strip()}"
                    if result.stdout:
                        error_details += f" - stdout: {result.stdout.strip()}"
                    return success, error_details
            
            elif 'expected_stdout' in quick_check:
                expected_out = quick_check['expected_stdout']
                actual_out = result.stdout.strip()
                success = actual_out == expected_out
                return success, f"Output: '{actual_out}' (expected: '{expected_out}')"
            
            else:
                # Default: success if returncode is 0
                success = result.returncode == 0
                return success, f"Command {'succeeded' if success else 'failed'} (code: {result.returncode})"
                
        except subprocess.TimeoutExpired:
            return False, f"Quick check timed out after {quick_check.get('timeout', 10)}s"
        except Exception as e:
            return False, f"Quick check failed: {str(e)}"

    def _list_snapshots_via_ssh(self, repo_uri: str, password: str, source_config: Dict[str, Any], dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """List snapshots via SSH execution using unified ResticExecutionService"""
        import json
        
        # Quick pre-check using schema-driven approach
        check_success, check_message = self._quick_repository_check(repo_uri, dest_config)
        if not check_success:
            return {
                'success': False,
                'error': f'Repository endpoint check failed: {check_message}'
            }
        
        # Use ResticExecutionService for unified SSH execution (supports same_as_origin volume mounting)
        try:
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=['snapshots', '--json'],
                source_config=source_config,
                operation_type=OperationType.UI,  # UI operation but uses SSH for same_as_origin
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    raw_snapshots = json.loads(result.stdout) if result.stdout.strip() else []
                    # Format snapshots for backup browser expectations
                    formatted_snapshots = []
                    for snapshot in raw_snapshots:
                        formatted_snapshot = {
                            'full_id': snapshot.get('id', ''),
                            'id': snapshot.get('short_id', snapshot.get('id', '')[:8] if snapshot.get('id') else ''),
                            'time': snapshot.get('time', ''),
                            'username': snapshot.get('username', ''),
                            'hostname': snapshot.get('hostname', ''),
                            'paths': snapshot.get('paths', []),
                            'summary': snapshot.get('summary', {}),
                            'tree': snapshot.get('tree', ''),
                            'program_version': snapshot.get('program_version', '')
                        }
                        formatted_snapshots.append(formatted_snapshot)
                    
                    return {
                        'success': True,
                        'snapshots': formatted_snapshots,
                        'count': len(formatted_snapshots)
                    }
                except json.JSONDecodeError:
                    return {
                        'success': False,
                        'error': 'Invalid JSON response from restic'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Restic command failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Snapshot listing timed out'
            }
        except Exception as e:
            logger.error(f"SSH execution error: {e}")
            return {
                'success': False,
                'error': f'SSH execution failed: {str(e)}'
            }
    
    @handle_restic_service_errors("snapshot statistics")
    def get_snapshot_statistics(self, dest_config: Dict[str, Any], snapshot_id: str, source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get detailed statistics for a specific snapshot"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Get snapshot statistics using unified execution service
        command_args = ['stats', snapshot_id, '--json']
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=command_args,
            source_config=source_config,
            operation_type=OperationType.UI,
            timeout=30
        )
        
        if result.returncode == 0:
            try:
                stats = json.loads(result.stdout) if result.stdout.strip() else {}
                return {
                    'success': True,
                    'stats': stats,  # backup browser expects 'stats' not 'statistics'
                    'snapshot_id': snapshot_id
                }
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': 'Invalid JSON response from restic stats'
                }
        else:
            return {
                'success': False,
                'error': f'Stats command failed: {result.stderr}'
            }
    
    @handle_restic_service_errors("repository unlock")
    def unlock_repository(self, dest_config: Dict[str, Any], source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Unlock a restic repository"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Check if we should use SSH execution (same pattern as other operations)
        if source_config and source_config.get('hostname') and source_config.get('username'):
            return self._unlock_repository_via_ssh(dest_config, source_config)
        else:
            # Fall back to local execution
            return self._unlock_repository_local(dest_config)
    
    def _unlock_repository_local(self, dest_config: Dict[str, Any]) -> Dict[str, Any]:
        """Unlock repository using local restic execution"""
        try:
            repo_uri = dest_config.get('repo_uri')
            
            # Use unified execution service for unlock command
            command_args = ['unlock']
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=command_args,
                operation_type=OperationType.MAINTENANCE,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Repository unlocked successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Unlock failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Repository unlock timed out'
            }
        except Exception as e:
            logger.error(f"Local unlock error: {e}")
            return {
                'success': False,
                'error': f'Local unlock failed: {str(e)}'
            }
    
    def _unlock_repository_via_ssh(self, dest_config: Dict[str, Any], source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Unlock repository via SSH execution (for consistency with other operations)"""
        try:
            repo_uri = dest_config.get('repo_uri')
            hostname = source_config.get('hostname')
            username = source_config.get('username')
            container_runtime = source_config.get('container_runtime', 'docker')
            
            # Use unified execution service for unlock command via SSH
            command_args = ['unlock']
            result = self.restic_executor.execute_restic_command(
                dest_config=dest_config,
                command_args=command_args,
                source_config=source_config,
                operation_type=OperationType.MAINTENANCE,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Repository unlocked successfully via SSH'
                }
            else:
                return {
                    'success': False,
                    'error': f'SSH unlock failed: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'SSH unlock timed out'
            }
        except Exception as e:
            logger.error(f"SSH unlock error: {e}")
            return {
                'success': False,
                'error': f'SSH unlock failed: {str(e)}'
            }
    
    @handle_restic_service_errors("snapshot directory browsing")
    def browse_snapshot_directory(self, dest_config: Dict[str, Any], snapshot_id: str, path: str, source_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Browse directory contents in a specific snapshot"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Clean path for restic ls command
        clean_path = path.strip('/') if path and path != '/' else ''
        
        # List directory contents using unified execution service
        command_args = ['ls', snapshot_id, '--json', path]
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=command_args,
            source_config=source_config,
            operation_type=OperationType.BROWSE,
            timeout=30
        )
        
        if result.returncode == 0:
            # Parse using EXACT working method
            return self._parse_directory_listing(result.stdout, path)
        else:
            return {
                'success': False,
                'error': f'Directory listing failed: {result.stderr}'
            }
    
    def _parse_directory_listing(self, json_output: str, current_path: str) -> Dict[str, Any]:
        """Parse restic ls JSON output into directory listing (EXACT copy from working version)"""
        try:
            lines = json_output.strip().split('\n')
            items = []
            
            # Add parent directory entry if not at root
            if current_path and current_path != '/':
                parent_path = os.path.dirname(current_path) if current_path != '/' else '/'
                items.append({
                    'name': '..',
                    'type': 'parent',
                    'path': parent_path,
                    'size': None
                })
            
            # Parse each JSON line 
            for line in lines:
                if not line.strip():
                    continue
                    
                try:
                    item = json.loads(line)
                    name = item.get('name', '')
                    item_type = item.get('type', 'file')
                    size = item.get('size')
                    full_path = item.get('path', os.path.join(current_path, name))
                    
                    # Skip the current directory entry, empty names, and self-references
                    if (name == '.' or name == current_path or name == '' or 
                        full_path == current_path or 
                        (current_path != '/' and name == os.path.basename(current_path))):
                        continue
                    
                    items.append({
                        'name': name,
                        'type': 'directory' if item_type == 'dir' else 'file',
                        'path': full_path,
                        'size': size
                    })
                    
                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue
            
            return {
                'success': True,
                'contents': items,
                'current_path': current_path,
                'total_items': len(items)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to parse directory listing: {str(e)}'
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
        self.restic_executor = ResticExecutionService()
    
    def run_backup(self, config, dry_run: bool = False) -> Dict[str, Any]:
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
    
    def _run_local_backup(self, config, backup_args: List[str], dry_run: bool) -> Dict[str, Any]:
        """Run backup locally"""
        try:
            # Execute backup using unified execution service
            command_args = ['backup'] + backup_args
            result = self.restic_executor.execute_restic_command(
                dest_config=config.dest_config,
                command_args=command_args,
                source_config=getattr(config, 'source_config', None),
                operation_type=OperationType.BACKUP,
                timeout=3600
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
    
    def _run_container_backup(self, config, backup_args: List[str], dry_run: bool) -> Dict[str, Any]:
        """Run backup using container on remote SSH host"""
        try:
            # Use existing container service for backup operations  
            from services.binaries import ContainerService
            from services.execution import ExecutionService
            
            container_service = ContainerService()
            exec_service = ExecutionService()
            
            # Extract configuration
            repository_url = config.dest_config['repo_uri']
            source_paths = [path['path'] for path in config.source_config.get('source_paths', [])]
            environment_vars = ResticArgumentBuilder.build_environment(config.dest_config)
            
            # Add dry-run to backup args if needed
            if dry_run and '--dry-run' not in backup_args:
                backup_args = backup_args + ['--dry-run']
            
            # Build container command using existing service
            container_command = container_service.build_backup_container_command(
                repository_url=repository_url,
                source_paths=source_paths,
                environment_vars=environment_vars,
                backup_args=backup_args
            )
            
            # Execute via SSH using existing execution service
            source_config = config.source_config
            result = exec_service.execute_ssh_command(
                hostname=source_config['hostname'],
                username=source_config['username'],
                command=container_command
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Container backup completed successfully',
                    'output': result.stdout,
                    'dry_run': dry_run
                }
            else:
                return {
                    'success': False,
                    'error': f'Container backup failed: {result.stderr}',
                    'output': result.stdout
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
        self.restic_executor = ResticExecutionService()
    
    def _validate_required_fields(self, dest_config: Dict[str, Any]) -> None:
        """Validate required fields exist or raise exception with actionable message"""
        from models.schemas import DESTINATION_TYPE_SCHEMAS
        
        schema = DESTINATION_TYPE_SCHEMAS.get('restic', {})
        required_fields = schema.get('required_fields', [])
        
        for field in required_fields:
            if not dest_config.get(field):
                raise ValueError(f'{schema.get("display_name", "Restic")} repository missing {field}')
    
    @handle_restic_service_errors("maintenance operation")
    def run_maintenance_operation(self, dest_config: Dict[str, Any], operation: str, 
                                config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run maintenance operation on repository"""
        self._validate_required_fields(dest_config)
        repo_uri = dest_config['repo_uri']
        password = dest_config['password']
        
        # Build command arguments
        args = self.argument_builder.build_maintenance_args(repo_uri, operation, config)
        
        # Execute maintenance operation using unified execution service
        result = self.restic_executor.execute_restic_command(
            dest_config=dest_config,
            command_args=args,
            operation_type=OperationType.MAINTENANCE,
            timeout=1800  # 30 minute timeout
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