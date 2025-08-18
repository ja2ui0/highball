"""
Unified Repository Service
Consolidates repository abstraction and filesystem browsing
Replaces: repository_service.py, filesystem_service.py
"""
import os
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from services.execution import ExecutionService


# =============================================================================
# **DATA STRUCTURES** - Repository and response formatting
# =============================================================================

class RepositoryResponse:
    """Standard response format for repository operations"""
    
    @staticmethod
    def error(error_message: str) -> Dict[str, Any]:
        """Standard error response format"""
        return {
            'success': False,
            'error': error_message
        }
    
    @staticmethod
    def success(data: Any) -> Dict[str, Any]:
        """Standard success response format"""
        return {
            'success': True,
            **data
        }


# =============================================================================
# **REPOSITORY ABSTRACTION CONCERN** - Common interface for backup providers
# =============================================================================

class RepositoryService(ABC):
    """Abstract base class for backup repository operations"""
    
    @abstractmethod
    def test_repository_access(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test if repository is accessible and get basic info"""
        pass
    
    @abstractmethod
    def list_snapshots(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """List all snapshots in the repository"""
        pass
    
    @abstractmethod
    def get_snapshot_statistics(self, job_config: Dict[str, Any], snapshot_id: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific snapshot"""
        pass
    
    @abstractmethod
    def browse_directory(self, job_config: Dict[str, Any], snapshot_id: str, path: str) -> Dict[str, Any]:
        """Browse files and directories in a snapshot"""
        pass
    
    def _should_use_ssh(self, source_config: Optional[Dict[str, Any]]) -> bool:
        """Determine if SSH execution should be used"""
        return source_config and source_config.get('hostname') and source_config.get('username')


# =============================================================================
# **FILESYSTEM BROWSING CONCERN** - Directory browsing for rsync destinations
# =============================================================================

class FilesystemBrowser:
    """Filesystem browsing - ONLY handles directory navigation for rsync-compatible destinations"""
    
    def __init__(self):
        self.executor = ExecutionService()
    
    def browse_directory(self, job_config: Dict[str, Any], path: str = '/') -> Dict[str, Any]:
        """Filesystem concern: browse files and directories in filesystem path"""
        try:
            dest_config = job_config.get('dest_config', {})
            dest_type = job_config.get('dest_type', '')
            
            # Determine which destination to browse based on job configuration
            if dest_type == 'ssh':
                return self._browse_destination_via_ssh(dest_config, path)
            elif dest_type == 'local':
                return self._browse_local_destination(dest_config, path)
            elif dest_type == 'rsyncd':
                return self._browse_rsyncd_destination(dest_config, path)
            else:
                return RepositoryResponse.error(f'Unsupported destination type for filesystem browsing: {dest_type}')
                
        except Exception as e:
            return RepositoryResponse.error(f'Filesystem browse failed: {str(e)}')
    
    def _browse_destination_via_ssh(self, dest_config: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Filesystem concern: browse SSH destination directory using execution service"""
        try:
            hostname = dest_config.get('hostname', '')
            username = dest_config.get('username', '')
            dest_path = dest_config.get('path', '/')
            
            if not hostname or not username:
                return RepositoryResponse.error('SSH destination missing hostname or username')
            
            # Combine destination path with requested browse path
            full_path = self._combine_paths(dest_path, path)
            
            # Use ExecutionService for SSH execution
            ls_command = ['sh', '-c', f'ls -la "{full_path}" 2>/dev/null || echo "ERROR: Cannot access {full_path}"']
            result = self.executor.execute_ssh_command(hostname, username, ls_command)
            
            if result.returncode != 0:
                return RepositoryResponse.error(f'SSH ls failed: {result.stderr or "Unknown error"}')
            
            stdout = result.stdout
            if stdout.startswith('ERROR:'):
                return RepositoryResponse.error(stdout)
            
            # Parse ls output
            contents = self._parse_ls_output(stdout, path)
            
            return RepositoryResponse.success({
                'contents': contents,
                'path': path,
                'full_path': full_path
            })
            
        except Exception as e:
            return RepositoryResponse.error(f'SSH browse error: {str(e)}')
    
    def _browse_local_destination(self, dest_config: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Filesystem concern: browse local destination directory"""
        try:
            dest_path = dest_config.get('path', '/')
            
            # Combine destination path with requested browse path
            full_path = self._combine_paths(dest_path, path)
            
            if not os.path.exists(full_path):
                return RepositoryResponse.error(f'Path does not exist: {full_path}')
            
            if not os.path.isdir(full_path):
                return RepositoryResponse.error(f'Path is not a directory: {full_path}')
            
            contents = []
            try:
                for item in sorted(os.listdir(full_path)):
                    item_path = os.path.join(full_path, item)
                    relative_path = self._combine_paths(path, item)
                    
                    if os.path.isdir(item_path):
                        contents.append({
                            'name': item,
                            'type': 'directory',
                            'path': relative_path
                        })
                    else:
                        stat_info = os.stat(item_path)
                        contents.append({
                            'name': item,
                            'type': 'file',
                            'path': relative_path,
                            'size': stat_info.st_size
                        })
            except PermissionError:
                return RepositoryResponse.error(f'Permission denied accessing: {full_path}')
            
            return RepositoryResponse.success({
                'contents': contents,
                'path': path,
                'full_path': full_path
            })
            
        except Exception as e:
            return RepositoryResponse.error(f'Local browse error: {str(e)}')
    
    def _browse_rsyncd_destination(self, dest_config: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Filesystem concern: browse rsyncd destination using rsync listing"""
        try:
            hostname = dest_config.get('hostname', '')
            share = dest_config.get('share', '')
            
            if not hostname or not share:
                return RepositoryResponse.error('Rsyncd destination missing hostname or share')
            
            # Build rsync destination with path
            if path == '/' or path == '':
                rsync_dest = f'{hostname}::{share}/'
            else:
                # Remove leading slash for rsync module paths
                clean_path = path.lstrip('/')
                rsync_dest = f'{hostname}::{share}/{clean_path}/'
            
            # Use rsync to list directory contents
            rsync_cmd = ['rsync', '--list-only', rsync_dest]
            
            result = self.executor.execute_local_command(rsync_cmd)
            
            if result.returncode != 0:
                return RepositoryResponse.error(f'Rsync listing failed: {result.stderr.strip()}')
            
            # Parse rsync output
            contents = self._parse_rsync_output(result.stdout, path)
            
            return RepositoryResponse.success({
                'contents': contents,
                'path': path,
                'share': share
            })
            
        except Exception as e:
            return RepositoryResponse.error(f'Rsyncd browse error: {str(e)}')
    
    def _parse_ls_output(self, ls_output: str, base_path: str) -> List[Dict[str, Any]]:
        """Filesystem concern: parse ls -la output into structured format"""
        contents = []
        lines = ls_output.strip().split('\n')
        
        for line in lines:
            if not line.strip() or line.startswith('total '):
                continue
            
            # Parse ls -la format: permissions links owner group size month day time/year name
            parts = line.split()
            if len(parts) < 9:
                continue
            
            permissions = parts[0]
            name = ' '.join(parts[8:])  # Handle names with spaces
            
            # Skip . and .. entries
            if name in ['.', '..']:
                continue
            
            # Determine type from permissions
            is_directory = permissions.startswith('d')
            item_type = 'directory' if is_directory else 'file'
            
            # Build relative path
            if base_path == '/' or base_path == '':
                relative_path = name
            else:
                relative_path = f"{base_path.rstrip('/')}/{name}"
            
            item = {
                'name': name,
                'type': item_type,
                'path': relative_path
            }
            
            # Add size for files
            if not is_directory and len(parts) >= 5:
                try:
                    item['size'] = int(parts[4])
                except ValueError:
                    pass  # Size not parseable, skip it
            
            contents.append(item)
        
        return contents
    
    def _parse_rsync_output(self, rsync_output: str, base_path: str) -> List[Dict[str, Any]]:
        """Filesystem concern: parse rsync --list-only output into structured format"""
        contents = []
        lines = rsync_output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            # Parse rsync list format: permissions size date time name
            parts = line.split()
            if len(parts) < 5:
                continue
            
            permissions = parts[0]
            name = ' '.join(parts[4:])  # Handle names with spaces
            
            # Skip . entries
            if name == '.':
                continue
            
            # Determine type from permissions
            is_directory = permissions.startswith('d')
            item_type = 'directory' if is_directory else 'file'
            
            # Build relative path
            if base_path == '/' or base_path == '':
                relative_path = name
            else:
                relative_path = f"{base_path.rstrip('/')}/{name}"
            
            item = {
                'name': name,
                'type': item_type,
                'path': relative_path
            }
            
            # Add size for files
            if not is_directory and len(parts) >= 2:
                try:
                    item['size'] = int(parts[1])
                except ValueError:
                    pass  # Size not parseable, skip it
            
            contents.append(item)
        
        return contents
    
    def _combine_paths(self, base_path: str, sub_path: str) -> str:
        """Filesystem concern: safely combine two paths"""
        if not base_path or base_path == '/':
            base_path = ''
        if not sub_path or sub_path == '/':
            sub_path = ''
        
        # Remove leading/trailing slashes and combine
        base_clean = base_path.strip('/')
        sub_clean = sub_path.strip('/')
        
        if not base_clean and not sub_clean:
            return '/'
        elif not base_clean:
            return f'/{sub_clean}'
        elif not sub_clean:
            return f'/{base_clean}'
        else:
            return f'/{base_clean}/{sub_clean}'


# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates repository and filesystem concerns
# =============================================================================

class RepositoryManager:
    """Unified repository manager - ONLY coordinates repository and filesystem concerns"""
    
    def __init__(self):
        self.filesystem_browser = FilesystemBrowser()
    
    # **FILESYSTEM DELEGATION** - Pure delegation to filesystem concern
    def browse_filesystem_directory(self, job_config: Dict[str, Any], path: str = '/') -> Dict[str, Any]:
        """Delegation: browse filesystem directory"""
        return self.filesystem_browser.browse_directory(job_config, path)
    
    # **UTILITY METHODS** - Common repository patterns
    def get_response_formatter(self):
        """Get standard response formatter"""
        return RepositoryResponse


# Legacy compatibility
filesystem_service = RepositoryManager()