"""
Consolidated Validation Module
Merges all validation logic into single module with clean class-based organization
Replaces: ssh_validator.py, restic_validator.py, source_path_validator.py, job_validator.py
"""

import subprocess
import re
import os
import validators
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# DATA CLASSES - Shared validation structures
# =============================================================================

@dataclass
class SSHConfig:
    """SSH connection configuration with sensible defaults"""
    connect_timeout: int = 5
    batch_mode: bool = True
    strict_host_checking: bool = False
    known_hosts_file: str = "/dev/null"
    timeout_seconds: int = 10
    
    def to_ssh_args(self) -> List[str]:
        """Convert configuration to SSH command arguments"""
        return [
            '-o', f'ConnectTimeout={self.connect_timeout}',
            '-o', f'BatchMode={"yes" if self.batch_mode else "no"}',
            '-o', f'StrictHostKeyChecking={"yes" if self.strict_host_checking else "no"}',
            '-o', f'UserKnownHostsFile={self.known_hosts_file}'
        ]

@dataclass
class SSHConnectionDetails:
    """Parsed SSH connection information"""
    username: str
    hostname: str
    path: str = ""
    
    @property
    def connection_string(self) -> str:
        """Get the full SSH connection string"""
        return f"{self.username}@{self.hostname}:{self.path}"
    
    def is_valid(self) -> bool:
        """Validate connection details"""
        return bool(self.username and self.hostname)
    
    def is_valid_with_path(self) -> bool:
        """Validate connection details including path"""
        return bool(self.username and self.hostname and self.path)

@dataclass
class ValidationResult:
    """Standard validation result structure"""
    valid: bool
    error: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        result = {'valid': self.valid}
        if self.error:
            result['error'] = self.error
        if self.details:
            result.update(self.details)
        return result

# =============================================================================
# SSH VALIDATION - Complete SSH connectivity and permissions
# =============================================================================

class SSHValidator:
    """Validates SSH connectivity, permissions, and container runtime detection"""
    
    def __init__(self):
        self.config = SSHConfig()
        self._validation_cache = {}
        self.cache_duration = 1800  # 30 minutes in seconds
    
    def validate_ssh_source(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SSH source with enhanced status details"""
        hostname = source_config.get('hostname', '')
        username = source_config.get('username', '')
        
        if not hostname or not username:
            return {'valid': False, 'error': 'Hostname and username are required'}
        
        # Check cache first
        cache_key = f"ssh:{username}@{hostname}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Test basic SSH connectivity
            ssh_test = self._test_ssh_connection(hostname, username)
            if not ssh_test['success']:
                result = {'valid': False, 'error': ssh_test['error']}
                self._cache_result(cache_key, result)
                return result
            
            # Test rsync availability
            rsync_test = self._test_rsync_availability(hostname, username)
            
            # Detect container runtime
            container_runtime = self._detect_container_runtime(hostname, username)
            
            # Test path permissions (basic home directory test)
            path_permissions = self._test_path_permissions(hostname, username, "~")
            
            result = {
                'valid': True,
                'ssh_status': 'OK',
                'rsync_status': 'OK' if rsync_test['success'] else 'MISSING',
                'container_runtime': container_runtime,
                'path_permissions': path_permissions,
                'tested_at': datetime.now().isoformat()
            }
            
            self._cache_result(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"SSH validation error for {hostname}: {e}")
            result = {'valid': False, 'error': f'SSH validation failed: {str(e)}'}
            self._cache_result(cache_key, result)
            return result
    
    def _test_ssh_connection(self, hostname: str, username: str) -> Dict[str, Any]:
        """Test basic SSH connectivity"""
        try:
            cmd = ['ssh'] + self.config.to_ssh_args() + [f'{username}@{hostname}', 'echo "SSH_OK"']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.timeout_seconds)
            
            if result.returncode == 0 and 'SSH_OK' in result.stdout:
                return {'success': True}
            else:
                return {'success': False, 'error': f'SSH connection failed: {result.stderr}'}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'SSH connection timeout'}
        except Exception as e:
            return {'success': False, 'error': f'SSH test failed: {str(e)}'}
    
    def _test_rsync_availability(self, hostname: str, username: str) -> Dict[str, Any]:
        """Test if rsync is available on remote host"""
        try:
            cmd = ['ssh'] + self.config.to_ssh_args() + [f'{username}@{hostname}', 'which rsync']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.timeout_seconds)
            
            return {'success': result.returncode == 0}
        except Exception:
            return {'success': False}
    
    def _detect_container_runtime(self, hostname: str, username: str) -> Optional[str]:
        """Detect available container runtime (docker/podman)"""
        runtimes = ['podman', 'docker']  # Prefer podman over docker
        
        for runtime in runtimes:
            try:
                cmd = ['ssh'] + self.config.to_ssh_args() + [f'{username}@{hostname}', f'which {runtime}']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.timeout_seconds)
                
                if result.returncode == 0:
                    return runtime
            except Exception:
                continue
        
        return None
    
    def _test_path_permissions(self, hostname: str, username: str, path: str) -> str:
        """Test path permissions (RO vs RWX)"""
        try:
            # Test read access
            cmd = ['ssh'] + self.config.to_ssh_args() + [f'{username}@{hostname}', f'test -r "{path}"']
            read_result = subprocess.run(cmd, capture_output=True, timeout=self.config.timeout_seconds)
            
            if read_result.returncode != 0:
                return 'NO_ACCESS'
            
            # Test write access  
            cmd = ['ssh'] + self.config.to_ssh_args() + [f'{username}@{hostname}', f'test -w "{path}"']
            write_result = subprocess.run(cmd, capture_output=True, timeout=self.config.timeout_seconds)
            
            return 'RWX' if write_result.returncode == 0 else 'RO'
            
        except Exception:
            return 'UNKNOWN'
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached validation result if still valid"""
        if cache_key in self._validation_cache:
            cached_at, result = self._validation_cache[cache_key]
            if (datetime.now() - cached_at).total_seconds() < self.cache_duration:
                return result
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache validation result"""
        self._validation_cache[cache_key] = (datetime.now(), result)

# =============================================================================
# RESTIC VALIDATION - Repository access and status
# =============================================================================

class ResticValidator:
    """Validates Restic repository configurations and access"""
    
    def validate_restic_repository_access(self, restic_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Restic repository access with detailed status"""
        try:
            # Basic config validation
            if not restic_config.get('repo_uri'):
                return {'valid': False, 'error': 'Repository URI is required'}
            
            if not restic_config.get('password'):
                return {'valid': False, 'error': 'Repository password is required'}
            
            # Test repository access via service
            from services.restic_repository_service import ResticRepositoryService
            repo_service = ResticRepositoryService()
            repo_test = repo_service.test_repository_access({'dest_config': restic_config})
            
            if not repo_test.get('success', False):
                return {
                    'valid': False,
                    'error': repo_test.get('error', 'Repository access failed')
                }
            
            # Enhanced repository status
            result = {
                'valid': True,
                'status': repo_test.get('repository_status', 'accessible'),
                'snapshot_count': repo_test.get('snapshot_count', 0),
                'latest_backup': repo_test.get('latest_backup'),
                'repository_uri': restic_config['repo_uri'],
                'tested_at': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Restic validation error: {e}")
            return {'valid': False, 'error': f'Repository validation failed: {str(e)}'}
    
    def validate_restic_destination(self, parsed_job: Dict[str, Any]) -> Dict[str, Any]:
        """Validate complete Restic destination configuration"""
        dest_config = parsed_job.get('dest_config', {})
        
        # Check required fields
        repo_type = dest_config.get('repo_type')
        if not repo_type:
            return {
                'success': False,
                'message': 'Repository type is required for Restic destinations'
            }
        
        repo_uri = dest_config.get('repo_uri')
        if not repo_uri:
            return {
                'success': False,
                'message': 'Repository URI is required for Restic destinations'
            }
        
        password = dest_config.get('password')
        if not password:
            return {
                'success': False,
                'message': 'Repository password is required for Restic destinations'
            }
        
        # Test repository access
        access_result = self.validate_restic_repository_access(dest_config)
        if not access_result['valid']:
            return {
                'success': False,
                'message': access_result['error']
            }
        
        return {
            'success': True,
            'message': 'Restic repository configuration is valid',
            'repository_status': access_result.get('status'),
            'snapshot_count': access_result.get('snapshot_count', 0)
        }

# =============================================================================
# SOURCE PATH VALIDATION - Path existence and permissions
# =============================================================================

class SourcePathValidator:
    """Validates source paths for backup operations"""
    
    def validate_local_path(self, path: str) -> Dict[str, Any]:
        """Validate local filesystem path"""
        try:
            path_obj = Path(path).expanduser().resolve()
            
            if not path_obj.exists():
                return {'valid': False, 'error': f'Path does not exist: {path}'}
            
            if not path_obj.is_dir():
                return {'valid': False, 'error': f'Path is not a directory: {path}'}
            
            # Test read permissions
            if not os.access(path_obj, os.R_OK):
                return {'valid': False, 'error': f'No read permission for path: {path}'}
            
            return {
                'valid': True,
                'permissions': 'RO',  # Local paths are read-only for backup
                'resolved_path': str(path_obj)
            }
            
        except Exception as e:
            return {'valid': False, 'error': f'Path validation failed: {str(e)}'}
    
    def validate_ssh_path(self, ssh_config: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Validate path on remote SSH host"""
        hostname = ssh_config.get('hostname')
        username = ssh_config.get('username')
        
        if not hostname or not username:
            return {'valid': False, 'error': 'SSH configuration required for remote path validation'}
        
        try:
            # Use SSH validator for the actual SSH operations
            ssh_validator = SSHValidator()
            
            # Test path existence
            cmd = ['ssh'] + ssh_validator.config.to_ssh_args() + [
                f'{username}@{hostname}', f'test -d "{path}"'
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            
            if result.returncode != 0:
                return {'valid': False, 'error': f'Remote path does not exist or is not a directory: {path}'}
            
            # Test permissions
            permissions = ssh_validator._test_path_permissions(hostname, username, path)
            
            return {
                'valid': True,
                'permissions': permissions,
                'remote_path': path
            }
            
        except Exception as e:
            return {'valid': False, 'error': f'Remote path validation failed: {str(e)}'}

# =============================================================================
# JOB VALIDATION - Complete job configuration validation
# =============================================================================

class JobValidator:
    """Validates complete backup job configurations"""
    
    def __init__(self):
        self.ssh_validator = SSHValidator()
        self.restic_validator = ResticValidator()
        self.source_path_validator = SourcePathValidator()
    
    def validate_backup_job(self, job_config: Dict[str, Any]) -> ValidationResult:
        """Validate complete backup job configuration"""
        try:
            # Basic job structure validation
            required_fields = ['job_name', 'source_type', 'source_config', 'dest_type', 'dest_config']
            for field in required_fields:
                if not job_config.get(field):
                    return ValidationResult(valid=False, error=f'Missing required field: {field}')
            
            # Validate source configuration
            source_result = self._validate_source_config(job_config)
            if not source_result.valid:
                return source_result
            
            # Validate destination configuration  
            dest_result = self._validate_dest_config(job_config)
            if not dest_result.valid:
                return dest_result
            
            # Validate source paths
            paths_result = self._validate_source_paths(job_config)
            if not paths_result.valid:
                return paths_result
            
            # Validate schedule if provided
            if job_config.get('schedule'):
                schedule_result = self._validate_schedule(job_config['schedule'])
                if not schedule_result.valid:
                    return schedule_result
            
            return ValidationResult(
                valid=True,
                details={
                    'message': 'Job configuration is valid',
                    'source_type': job_config['source_type'],
                    'dest_type': job_config['dest_type'],
                    'path_count': len(job_config.get('source_config', {}).get('source_paths', []))
                }
            )
            
        except Exception as e:
            logger.error(f"Job validation error: {e}")
            return ValidationResult(valid=False, error=f'Job validation failed: {str(e)}')
    
    def _validate_source_config(self, job_config: Dict[str, Any]) -> ValidationResult:
        """Validate source configuration"""
        source_type = job_config['source_type']
        source_config = job_config['source_config']
        
        if source_type == 'ssh':
            ssh_result = self.ssh_validator.validate_ssh_source(source_config)
            if not ssh_result['valid']:
                return ValidationResult(valid=False, error=f"SSH source validation failed: {ssh_result['error']}")
        elif source_type == 'local':
            # Local sources need minimal validation
            pass
        else:
            return ValidationResult(valid=False, error=f'Unknown source type: {source_type}')
        
        return ValidationResult(valid=True)
    
    def _validate_dest_config(self, job_config: Dict[str, Any]) -> ValidationResult:
        """Validate destination configuration"""
        dest_type = job_config['dest_type']
        dest_config = job_config['dest_config']
        
        if dest_type == 'restic':
            restic_result = self.restic_validator.validate_restic_destination(job_config)
            if not restic_result['success']:
                return ValidationResult(valid=False, error=restic_result['message'])
        elif dest_type in ['ssh', 'local', 'rsyncd']:
            # Basic validation for other destination types
            if dest_type == 'ssh':
                required = ['hostname', 'username', 'path']
                for field in required:
                    if not dest_config.get(field):
                        return ValidationResult(valid=False, error=f'SSH destination missing {field}')
            elif dest_type == 'local':
                if not dest_config.get('path'):
                    return ValidationResult(valid=False, error='Local destination missing path')
            elif dest_type == 'rsyncd':
                required = ['hostname', 'share']
                for field in required:
                    if not dest_config.get(field):
                        return ValidationResult(valid=False, error=f'Rsyncd destination missing {field}')
        else:
            return ValidationResult(valid=False, error=f'Unknown destination type: {dest_type}')
        
        return ValidationResult(valid=True)
    
    def _validate_source_paths(self, job_config: Dict[str, Any]) -> ValidationResult:
        """Validate all source paths in the job"""
        source_config = job_config['source_config']
        source_paths = source_config.get('source_paths', [])
        
        if not source_paths:
            return ValidationResult(valid=False, error='At least one source path is required')
        
        for i, path_config in enumerate(source_paths):
            path = path_config.get('path')
            if not path:
                return ValidationResult(valid=False, error=f'Source path {i+1} is empty')
            
            # Validate path based on source type
            if job_config['source_type'] == 'ssh':
                path_result = self.source_path_validator.validate_ssh_path(source_config, path)
            else:  # local
                path_result = self.source_path_validator.validate_local_path(path)
            
            if not path_result['valid']:
                return ValidationResult(valid=False, error=f"Source path {i+1} validation failed: {path_result['error']}")
        
        return ValidationResult(valid=True)
    
    def _validate_schedule(self, schedule: str) -> ValidationResult:
        """Validate cron schedule format"""
        if schedule in ['manual', 'hourly', 'daily', 'weekly', 'monthly']:
            return ValidationResult(valid=True)
        
        # Validate cron expression
        try:
            from croniter import croniter
            croniter(schedule)
            return ValidationResult(valid=True)
        except Exception as e:
            return ValidationResult(valid=False, error=f'Invalid cron expression: {str(e)}')

# =============================================================================
# UNIFIED VALIDATION FACADE - Single entry point
# =============================================================================

class ValidationService:
    """Unified validation service - single entry point for all validation"""
    
    def __init__(self, backup_config=None):
        self.backup_config = backup_config
        self.ssh = SSHValidator()
        self.restic = ResticValidator()
        self.source_path = SourcePathValidator()
        self.job = JobValidator()
    
    def validate_ssh_connection(self, hostname: str, username: str) -> Dict[str, Any]:
        """Validation concern: validate SSH connection parameters and connectivity"""
        if not hostname or not username:
            return {'valid': False, 'error': 'Hostname and username are required'}
        
        source_config = {'hostname': hostname, 'username': username}
        return self.ssh.validate_ssh_source(source_config)
    
    def validate_ssh_source(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SSH source configuration"""
        return self.ssh.validate_ssh_source(source_config)
    
    def validate_restic_config(self, repo_type: str, repo_uri: str, password: str) -> Dict[str, Any]:
        """Validation concern: validate Restic configuration parameters"""
        if not repo_type or not repo_uri or not password:
            return {'valid': False, 'error': 'Repository type, URI, and password are required'}
        
        restic_config = {
            'repo_type': repo_type,
            'repo_uri': repo_uri, 
            'password': password
        }
        return self.restic.validate_restic_repository_access(restic_config)
    
    def validate_restic_repository(self, restic_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Restic repository access"""
        return self.restic.validate_restic_repository_access(restic_config)
    
    def validate_source_path_with_ssh(self, hostname: str, username: str, path: str) -> Dict[str, Any]:
        """Validation concern: validate source path with optional SSH details"""
        if not path:
            return {'valid': False, 'error': 'Path is required'}
        
        if hostname and username:
            # SSH path validation
            source_config = {'hostname': hostname, 'username': username}
            return self.source_path.validate_ssh_path(source_config, path)
        else:
            # Local path validation
            return self.source_path.validate_local_path(path)
    
    def validate_source_path(self, source_config: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Validate individual source path"""
        if source_config.get('hostname'):  # SSH source
            return self.source_path.validate_ssh_path(source_config, path)
        else:  # Local source
            return self.source_path.validate_local_path(path)
    
    def validate_backup_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate complete backup job configuration"""
        result = self.job.validate_backup_job(job_config)
        return result.to_dict()

# Export the unified service as the main interface
validation_service = ValidationService()