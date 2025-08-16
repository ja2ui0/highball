"""
Restic-specific implementation of repository service.
Handles Restic repositories, snapshots, and browsing operations.
"""

import os
import json
from typing import Dict, List, Optional, Any
from services.repository_service import RepositoryService
from services.command_execution_service import CommandExecutionService


class ResticRepositoryService(RepositoryService):
    """Restic implementation of repository operations"""
    
    def __init__(self):
        """Initialize with Restic runner for URL and environment building"""
        from services.restic_runner import ResticRunner
        self.runner = ResticRunner()
    
    def test_repository_access(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Restic repository access and get basic info"""
        try:
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            repo_url = self.runner._build_repository_url(dest_config)
            env_vars = self.runner._build_environment(dest_config)
            
            if self._should_use_ssh(source_config):
                return self._test_repository_via_ssh(repo_url, env_vars, source_config)
            else:
                return self._test_repository_locally(repo_url, env_vars)
                
        except Exception as e:
            return self._format_error_response(f'Repository test failed: {str(e)}')
    
    def list_snapshots(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """List all snapshots in Restic repository"""
        try:
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            repo_url = self.runner._build_repository_url(dest_config)
            env_vars = self.runner._build_environment(dest_config)
            
            if self._should_use_ssh(source_config):
                return self._list_snapshots_via_ssh(repo_url, env_vars, source_config)
            else:
                return self._list_snapshots_locally(repo_url, env_vars)
                
        except Exception as e:
            return self._format_error_response(f'Snapshot listing failed: {str(e)}')
    
    def get_snapshot_statistics(self, job_config: Dict[str, Any], snapshot_id: str) -> Dict[str, Any]:
        """Get detailed statistics for a Restic snapshot"""
        try:
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            repo_url = self.runner._build_repository_url(dest_config)
            env_vars = self.runner._build_environment(dest_config)
            
            if self._should_use_ssh(source_config):
                return self._get_snapshot_stats_via_ssh(repo_url, env_vars, source_config, snapshot_id)
            else:
                return self._get_snapshot_stats_locally(repo_url, env_vars, snapshot_id)
                
        except Exception as e:
            return self._format_error_response(f'Snapshot statistics failed: {str(e)}')
    
    def browse_directory(self, job_config: Dict[str, Any], snapshot_id: str, path: str) -> Dict[str, Any]:
        """Browse directory contents in Restic snapshot"""
        try:
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            repo_url = self.runner._build_repository_url(dest_config)
            env_vars = self.runner._build_environment(dest_config)
            
            if self._should_use_ssh(source_config):
                return self._browse_directory_via_ssh(repo_url, env_vars, source_config, snapshot_id, path)
            else:
                return self._browse_directory_locally(repo_url, env_vars, snapshot_id, path)
                
        except Exception as e:
            return self._format_error_response(f'Directory browsing failed: {str(e)}')
    
    def init_repository(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize a new Restic repository"""
        try:
            dest_config = job_config.get('dest_config', {})
            source_config = job_config.get('source_config', {})
            
            repo_url = self.runner._build_repository_url(dest_config)
            env_vars = self.runner._build_environment(dest_config)
            
            if self._should_use_ssh(source_config, 'init'):
                return self._init_repository_via_ssh(repo_url, env_vars, source_config)
            else:
                return self._init_repository_locally(repo_url, env_vars)
                
        except Exception as e:
            return self._format_error_response(f'Repository initialization failed: {str(e)}')
    
    def _test_repository_via_ssh(self, repo_url: str, env_vars: Dict[str, str], source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test repository access via SSH"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        command = f"restic -r '{repo_url}' snapshots --json"
        executor = CommandExecutionService()
        result = executor.execute_via_ssh(hostname, username, command, env_vars)
        
        if result.success:
            json_result = executor.parse_json_output(result.stdout)
            if json_result['success']:
                snapshots = json_result['data'] or []
                snapshot_count = len(snapshots)
                
                if snapshot_count > 0:
                    latest_snap = max(snapshots, key=lambda x: x.get('time', ''))
                    return self._format_success_response({
                        'message': f'EXISTING REPO FOUND! Repository contains {snapshot_count} snapshots',
                        'repository_status': 'existing',
                        'snapshot_count': snapshot_count,
                        'latest_backup': latest_snap.get('time', 'unknown'),
                        'tested_from': f'{username}@{hostname}'
                    })
                else:
                    return self._format_success_response({
                        'message': 'Repository exists but contains no snapshots (empty repository)',
                        'repository_status': 'empty',
                        'snapshot_count': 0,
                        'tested_from': f'{username}@{hostname}'
                    })
            else:
                return self._format_error_response(f'Failed to parse snapshots: {json_result["error"]}')
        else:
            # Check if this is a "repository does not exist" error (should trigger init button)
            if ('repository does not exist' in result.stderr.lower() or 
                'does not exist' in result.stderr.lower() or
                'config file' in result.stderr.lower()):
                return self._format_success_response({
                    'message': 'No repository found at this location (ready for initialization)',
                    'repository_status': 'empty',
                    'snapshot_count': 0,
                    'tested_from': f'{username}@{hostname}'
                })
            else:
                return self._format_error_response(f'Repository test failed: {result.stderr}')
    
    def _test_repository_locally(self, repo_url: str, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Test repository access locally"""
        command = ['restic', '-r', repo_url, 'snapshots', '--json']
        executor = CommandExecutionService()
        result = executor.execute_locally(command, env_vars)
        
        if result.success:
            json_result = executor.parse_json_output(result.stdout)
            if json_result['success']:
                snapshots = json_result['data'] or []
                snapshot_count = len(snapshots)
                
                if snapshot_count > 0:
                    latest_snap = max(snapshots, key=lambda x: x.get('time', ''))
                    return self._format_success_response({
                        'message': f'EXISTING REPO FOUND! Repository contains {snapshot_count} snapshots',
                        'repository_status': 'existing',
                        'snapshot_count': snapshot_count,
                        'latest_backup': latest_snap.get('time', 'unknown'),
                        'tested_from': 'container'
                    })
                else:
                    return self._format_success_response({
                        'message': 'Repository exists but contains no snapshots (empty repository)',
                        'repository_status': 'empty',
                        'snapshot_count': 0,
                        'tested_from': 'container'
                    })
            else:
                return self._format_error_response(f'Failed to parse snapshots: {json_result["error"]}')
        else:
            # Check if this is a "repository does not exist" error (should trigger init button)
            if ('repository does not exist' in result.stderr.lower() or 
                'does not exist' in result.stderr.lower() or
                'config file' in result.stderr.lower()):
                return self._format_success_response({
                    'message': 'No repository found at this location (ready for initialization)',
                    'repository_status': 'empty',
                    'snapshot_count': 0,
                    'tested_from': 'container'
                })
            else:
                return self._format_error_response(f'Repository test failed: {result.stderr}')
    
    def _list_snapshots_via_ssh(self, repo_url: str, env_vars: Dict[str, str], source_config: Dict[str, Any]) -> Dict[str, Any]:
        """List snapshots via SSH"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        command = f"restic -r '{repo_url}' snapshots --json"
        executor = CommandExecutionService()
        result = executor.execute_via_ssh(hostname, username, command, env_vars)
        
        if result.success:
            json_result = executor.parse_json_output(result.stdout)
            if json_result['success']:
                snapshots = json_result['data'] or []
                formatted_snapshots = self._format_snapshots(snapshots)
                
                return self._format_success_response({
                    'snapshots': formatted_snapshots,
                    'count': len(formatted_snapshots)
                })
            else:
                return self._format_error_response(f'Failed to parse snapshots: {json_result["error"]}')
        else:
            return self._format_error_response(f'Snapshot listing failed: {result.stderr}')
    
    def _list_snapshots_locally(self, repo_url: str, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """List snapshots locally"""
        command = ['restic', '-r', repo_url, 'snapshots', '--json']
        executor = CommandExecutionService()
        result = executor.execute_locally(command, env_vars)
        
        if result.success:
            json_result = executor.parse_json_output(result.stdout)
            if json_result['success']:
                snapshots = json_result['data'] or []
                formatted_snapshots = self._format_snapshots(snapshots)
                
                return self._format_success_response({
                    'snapshots': formatted_snapshots,
                    'count': len(formatted_snapshots)
                })
            else:
                return self._format_error_response(f'Failed to parse snapshots: {json_result["error"]}')
        else:
            return self._format_error_response(f'Snapshot listing failed: {result.stderr}')
    
    def _format_snapshots(self, snapshots: List[Dict]) -> List[Dict]:
        """Format snapshot data for consistent output"""
        formatted = []
        for snap in snapshots:
            formatted.append({
                'id': snap.get('short_id', snap.get('id', 'unknown'))[:8],
                'full_id': snap.get('id', 'unknown'),
                'time': snap.get('time', 'unknown'),
                'hostname': snap.get('hostname', 'unknown'),
                'username': snap.get('username', 'unknown'),
                'paths': snap.get('paths', []),
                'tags': snap.get('tags', [])
            })
        return formatted
    
    def _get_snapshot_stats_via_ssh(self, repo_url: str, env_vars: Dict[str, str], source_config: Dict[str, Any], snapshot_id: str) -> Dict[str, Any]:
        """Get snapshot statistics via SSH"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        command = f"restic -r '{repo_url}' stats {snapshot_id} --mode restore-size --json"
        executor = CommandExecutionService()
        result = executor.execute_via_ssh(hostname, username, command, env_vars)
        
        if result.success:
            json_result = executor.parse_json_output(result.stdout)
            if json_result['success']:
                stats = json_result['data']
                return self._format_success_response({
                    'stats': {
                        'total_size': stats.get('total_size', 0),
                        'total_file_count': stats.get('total_file_count', 0),
                        'snapshot_id': snapshot_id[:8],
                        'full_snapshot_id': snapshot_id
                    }
                })
            else:
                return self._format_error_response(f'Failed to parse statistics: {json_result["error"]}')
        else:
            return self._format_error_response(f'Statistics failed: {result.stderr}')
    
    def _get_snapshot_stats_locally(self, repo_url: str, env_vars: Dict[str, str], snapshot_id: str) -> Dict[str, Any]:
        """Get snapshot statistics locally"""
        command = ['restic', '-r', repo_url, 'stats', snapshot_id, '--mode', 'restore-size', '--json']
        executor = CommandExecutionService()
        result = executor.execute_locally(command, env_vars)
        
        if result.success:
            json_result = executor.parse_json_output(result.stdout)
            if json_result['success']:
                stats = json_result['data']
                return self._format_success_response({
                    'stats': {
                        'total_size': stats.get('total_size', 0),
                        'total_file_count': stats.get('total_file_count', 0),
                        'snapshot_id': snapshot_id[:8],
                        'full_snapshot_id': snapshot_id
                    }
                })
            else:
                return self._format_error_response(f'Failed to parse statistics: {json_result["error"]}')
        else:
            return self._format_error_response(f'Statistics failed: {result.stderr}')
    
    def _browse_directory_via_ssh(self, repo_url: str, env_vars: Dict[str, str], source_config: Dict[str, Any], snapshot_id: str, path: str) -> Dict[str, Any]:
        """Browse directory via SSH"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        command = f"restic -r '{repo_url}' ls {snapshot_id} --json '{path}'"
        executor = CommandExecutionService()
        result = executor.execute_via_ssh(hostname, username, command, env_vars)
        
        if result.success:
            return self._parse_directory_listing(result.stdout, path)
        else:
            return self._format_error_response(f'Directory browse failed: {result.stderr}')
    
    def _browse_directory_locally(self, repo_url: str, env_vars: Dict[str, str], snapshot_id: str, path: str) -> Dict[str, Any]:
        """Browse directory locally"""
        command = ['restic', '-r', repo_url, 'ls', snapshot_id, '--json', path]
        executor = CommandExecutionService()
        result = executor.execute_locally(command, env_vars)
        
        if result.success:
            return self._parse_directory_listing(result.stdout, path)
        else:
            return self._format_error_response(f'Directory browse failed: {result.stderr}')
    
    def _parse_directory_listing(self, json_output: str, current_path: str) -> Dict[str, Any]:
        """Parse restic ls JSON output into directory listing"""
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
            
            return self._format_success_response({
                'contents': items,
                'current_path': current_path,
                'total_items': len(items)
            })
            
        except Exception as e:
            return self._format_error_response(f'Failed to parse directory listing: {str(e)}')
    
    def _init_repository_via_ssh(self, repo_url: str, env_vars: Dict[str, str], source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize repository via SSH"""
        hostname = source_config.get('hostname')
        username = source_config.get('username')
        
        command = f"restic -r '{repo_url}' init"
        executor = CommandExecutionService()
        result = executor.execute_via_ssh(hostname, username, command, env_vars)
        
        if result.success:
            return self._format_success_response({
                'message': f'Repository initialized successfully at {repo_url}',
                'repository_status': 'initialized',
                'initialized_from': f'{username}@{hostname}'
            })
        else:
            # Check if it's already initialized
            if 'already initialized' in result.stderr.lower():
                return self._format_success_response({
                    'message': f'Repository already initialized at {repo_url}',
                    'repository_status': 'existing',
                    'initialized_from': f'{username}@{hostname}'
                })
            else:
                return self._format_error_response(f'Repository initialization failed: {result.stderr}')
    
    def _init_repository_locally(self, repo_url: str, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Initialize repository locally"""
        command = ['restic', '-r', repo_url, 'init']
        executor = CommandExecutionService()
        result = executor.execute_locally(command, env_vars)
        
        if result.success:
            return self._format_success_response({
                'message': f'Repository initialized successfully at {repo_url}',
                'repository_status': 'initialized',
                'initialized_from': 'container'
            })
        else:
            # Check if it's already initialized
            if 'already initialized' in result.stderr.lower():
                return self._format_success_response({
                    'message': f'Repository already initialized at {repo_url}',
                    'repository_status': 'existing',
                    'initialized_from': 'container'
                })
            else:
                return self._format_error_response(f'Repository initialization failed: {result.stderr}')
    
    def _should_use_ssh(self, source_config: Dict[str, Any], operation_type: str = 'ui') -> bool:
        """
        Determine if SSH should be used for repository operations.
        
        For UI operations: always use local execution from Highball container.
        For init operations: use SSH when source is SSH to validate container execution pipeline.
        """
        if operation_type == 'init':
            # Use SSH for init to sanity check that host can execute restic containers
            source_type = source_config.get('source_type') if source_config else None
            return source_type == 'ssh'
        
        # UI operations always use local execution
        return False
    
    def _format_success_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format success response"""
        return {
            'success': True,
            **data
        }
    
    def _format_error_response(self, error_message: str) -> Dict[str, Any]:
        """Format error response"""
        return {
            'success': False,
            'error': error_message
        }