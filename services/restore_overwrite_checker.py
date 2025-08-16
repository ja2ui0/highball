"""
Restore overwrite checker service for detecting file conflicts
Handles checking if restore would overwrite existing files at destination
"""
import os
import subprocess
from typing import Dict, Any, List
from services.job_logger import JobLogger


class RestoreOverwriteChecker:
    """Service for checking restore overwrite conflicts"""
    
    def __init__(self):
        self.job_logger = JobLogger()
    
    def check_restore_overwrites(self, restore_target: str, source_type: str, source_config: Dict[str, Any], 
                                check_paths: List[str], select_all: bool = False) -> bool:
        """Check if restore would overwrite existing files at destination"""
        try:
            if restore_target == 'highball':
                return self._check_highball_overwrites(check_paths)
            elif restore_target == 'source':
                return self._check_source_overwrites(source_type, source_config, check_paths, select_all)
            else:
                return False
                
        except Exception as e:
            self.job_logger.log_job_execution('system', f'Error checking destination files: {str(e)}', 'WARNING')
            return False  # Default to no overwrites if check fails
    
    def _check_highball_overwrites(self, check_paths: List[str]) -> bool:
        """Check if files exist in Highball /restore directory that would be overwritten"""
        restore_dir = '/restore'
        
        for path in check_paths:
            if path:
                # Convert source path to restore destination path
                # Remove leading slash and join with restore dir
                dest_path = os.path.join(restore_dir, path.lstrip('/'))
                
                if os.path.exists(dest_path):
                    # If it's a directory, check if it has any contents
                    if os.path.isdir(dest_path):
                        try:
                            if any(os.scandir(dest_path)):
                                return True
                        except (PermissionError, OSError):
                            return True
                    else:
                        # File exists
                        return True
        
        return False
    
    def _check_source_overwrites(self, source_type: str, source_config: Dict[str, Any], 
                                check_paths: List[str], select_all: bool) -> bool:
        """Check if files exist at original source location that would be overwritten"""
        # Map backup paths back to actual source paths
        source_paths = source_config.get('source_paths', [])
        if not source_paths:
            return False  # No source paths configured
        
        # Map backup paths to actual source paths
        actual_paths_to_check = self._map_backup_paths_to_source_paths(check_paths, source_paths)
        
        if source_type == 'local':
            return self._check_local_filesystem_overwrites(actual_paths_to_check)
        elif source_type == 'ssh':
            hostname = source_config.get('hostname', '')
            username = source_config.get('username', '')
            return self._check_ssh_filesystem_overwrites(hostname, username, actual_paths_to_check)
        
        return False
    
    def _map_backup_paths_to_source_paths(self, check_paths: List[str], source_paths: List[Dict]) -> List[str]:
        """Map backup paths to actual source paths"""
        actual_paths_to_check = []
        
        for check_path in check_paths:
            if check_path:
                # Remove container mount prefix (e.g., /backup-source-0/README.md -> README.md)
                if check_path.startswith('/backup-source-'):
                    # Find the mount number and remove prefix
                    parts = check_path.split('/', 3)  # ['', 'backup-source-N', 'relative', 'path']
                    if len(parts) >= 3:
                        relative_path = parts[2] if len(parts) == 3 else '/'.join(parts[2:])
                        
                        # Map to actual source paths
                        for source_path_config in source_paths:
                            source_path = source_path_config.get('path', '') if isinstance(source_path_config, dict) else str(source_path_config)
                            if source_path:
                                # Combine source path with relative path from backup
                                actual_path = os.path.join(source_path, relative_path) if relative_path else source_path
                                actual_paths_to_check.append(actual_path)
                else:
                    # Direct path - add to check list
                    actual_paths_to_check.append(check_path)
        
        return actual_paths_to_check
    
    def _check_local_filesystem_overwrites(self, paths_to_check: List[str]) -> bool:
        """Check local filesystem for existing files"""
        for path in paths_to_check:
            if path and os.path.exists(path):
                # If it's a directory, check if it has any contents
                if os.path.isdir(path):
                    try:
                        if any(os.scandir(path)):
                            return True
                    except (PermissionError, OSError):
                        return True
                else:
                    # File exists
                    return True
        
        return False
    
    def _check_ssh_filesystem_overwrites(self, hostname: str, username: str, paths_to_check: List[str]) -> bool:
        """Check remote filesystem via SSH for existing files"""
        if not hostname:
            return False
        
        # Use SSH to check if files exist
        for path in paths_to_check:
            if path:
                # Build SSH command to check if path exists and has contents
                ssh_cmd = [
                    'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes', 
                    '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null'
                ]
                
                if username:
                    ssh_cmd.append(f'{username}@{hostname}')
                else:
                    ssh_cmd.append(hostname)
                
                # Check if path exists and is non-empty
                check_cmd = f'[ -e "{path}" ] && ([ -f "{path}" ] || [ "$(ls -A "{path}" 2>/dev/null)" ])'
                ssh_cmd.append(check_cmd)
                
                try:
                    result = subprocess.run(ssh_cmd, capture_output=True, timeout=10)
                    if result.returncode == 0:
                        return True  # Path exists and has contents
                except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                    # Assume no overwrites if we can't check
                    continue
        
        return False
    
    def get_overwrite_paths_for_display(self, restore_target: str, source_type: str, source_config: Dict[str, Any], 
                                       check_paths: List[str]) -> List[str]:
        """Get list of paths that would be overwritten for display to user"""
        overwrite_paths = []
        
        try:
            if restore_target == 'highball':
                restore_dir = '/restore'
                for path in check_paths:
                    if path:
                        dest_path = os.path.join(restore_dir, path.lstrip('/'))
                        if os.path.exists(dest_path):
                            overwrite_paths.append(dest_path)
                            
            elif restore_target == 'source':
                source_paths = source_config.get('source_paths', [])
                actual_paths = self._map_backup_paths_to_source_paths(check_paths, source_paths)
                
                if source_type == 'local':
                    for path in actual_paths:
                        if path and os.path.exists(path):
                            overwrite_paths.append(path)
                elif source_type == 'ssh':
                    # For SSH, we'd need to query remotely - simplified for now
                    overwrite_paths = [f"Remote: {path}" for path in actual_paths]
        
        except Exception as e:
            self.job_logger.log_job_execution('system', f'Error getting overwrite paths: {str(e)}', 'WARNING')
        
        return overwrite_paths