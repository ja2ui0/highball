"""
SSH validation service for remote backup sources - modernized
Validates SSH connectivity and permissions using modern patterns
"""
import subprocess
import re
import validators
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


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
    path: str
    
    @property
    def connection_string(self) -> str:
        """Get the full SSH connection string"""
        return f"{self.username}@{self.hostname}:{self.path}"
    
    def is_valid(self) -> bool:
        """Validate connection details"""
        return bool(self.username and self.hostname and self.path)


@dataclass
class ValidationResult:
    """Result of SSH validation attempt"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    tested_from: Optional[str] = None
    
    @classmethod
    def success_result(cls, message: str, **kwargs) -> 'ValidationResult':
        """Create a successful validation result"""
        return cls(success=True, message=message, **kwargs)
    
    @classmethod
    def error_result(cls, message: str, **kwargs) -> 'ValidationResult':
        """Create an error validation result"""
        return cls(success=False, message=message, **kwargs)


class SSHValidator:
    """Validates SSH connections and remote paths for backup jobs - modernized"""
    
    def __init__(self, config: Optional[SSHConfig] = None):
        self.config = config or SSHConfig()
    
    @staticmethod
    def parse_ssh_source(source: str) -> Optional[SSHConnectionDetails]:
        """Parse SSH source into structured components"""
        # Match pattern: user@hostname:/path
        match = re.match(r'^([^@]+)@([^:]+):(.+)$', source.strip())
        if not match:
            return None
        
        username, hostname, path = match.groups()
        return SSHConnectionDetails(
            username=username.strip(),
            hostname=hostname.strip(), 
            path=path.strip()
        )
    
    def validate_hostname(self, hostname: str) -> bool:
        """Validate hostname using validators module"""
        hostname = hostname.strip()
        # Check if it's a valid domain, IPv4, or IPv6 address
        return (validators.domain(hostname) or 
                validators.ipv4(hostname) or 
                validators.ipv6(hostname))
    
    def validate_ssh_source(self, source: str) -> ValidationResult:
        """Comprehensive SSH source validation"""
        # Parse the source string
        connection = self.parse_ssh_source(source)
        if not connection:
            return ValidationResult.error_result(
                "Invalid SSH source format. Expected: user@hostname:/path"
            )
        
        if not connection.is_valid():
            return ValidationResult.error_result(
                "SSH source missing required components (username, hostname, or path)"
            )
        
        # Validate hostname format
        if not self.validate_hostname(connection.hostname):
            return ValidationResult.error_result(
                f"Invalid hostname format: {connection.hostname}"
            )
        
        # Test SSH connection
        ssh_result = self._test_ssh_connection(connection)
        if not ssh_result.success:
            return ssh_result
        
        # Test remote path accessibility
        path_result = self._test_remote_path(connection)
        if not path_result.success:
            return path_result
        
        # Test rsync compatibility
        rsync_result = self._test_rsync_compatibility(connection)
        
        # Combine results
        details = {
            'ssh_status': ssh_result.message,
            'path_status': path_result.message,
            'rsync_status': rsync_result.message
        }
        
        if rsync_result.success:
            return ValidationResult.success_result(
                f"SSH source validated successfully: {connection.connection_string}",
                details=details,
                tested_from="Highball container"
            )
        else:
            # SSH and path work, but rsync has issues - still report as success with warning
            details['rsync_status'] += " (WARNING: may affect backup reliability)"
            return ValidationResult.success_result(
                f"SSH source accessible with rsync warnings: {connection.connection_string}",
                details=details,
                tested_from="Highball container"
            )
    
    def _test_ssh_connection(self, connection: SSHConnectionDetails) -> ValidationResult:
        """Test basic SSH connectivity"""
        try:
            cmd = ['ssh'] + self.config.to_ssh_args() + [
                f'{connection.username}@{connection.hostname}',
                'echo "SSH_OK"'
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=self.config.timeout_seconds
            )
            
            if result.returncode == 0 and 'SSH_OK' in result.stdout:
                return ValidationResult.success_result('SSH connection established')
            else:
                error_msg = result.stderr.strip() or 'Connection failed'
                return ValidationResult.error_result(f'SSH connection failed: {error_msg}')
                
        except subprocess.TimeoutExpired:
            return ValidationResult.error_result('SSH connection timed out')
        except Exception as e:
            return ValidationResult.error_result(f'SSH test error: {str(e)}')
    
    def _test_remote_path(self, connection: SSHConnectionDetails) -> ValidationResult:
        """Test if remote path exists and is accessible"""
        try:
            # Test if path exists and get basic info
            cmd = ['ssh'] + self.config.to_ssh_args() + [
                f'{connection.username}@{connection.hostname}',
                f'test -e "{connection.path}" && echo "PATH_EXISTS" || echo "PATH_MISSING"'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if 'PATH_EXISTS' in output:
                    return ValidationResult.success_result('Remote path exists and is accessible')
                elif 'PATH_MISSING' in output:
                    return ValidationResult.error_result(
                        f'Remote path does not exist: {connection.path}'
                    )
                else:
                    return ValidationResult.error_result('Could not determine path status')
            else:
                error_msg = result.stderr.strip() or 'Path test failed'
                return ValidationResult.error_result(f'Remote path test failed: {error_msg}')
                
        except subprocess.TimeoutExpired:
            return ValidationResult.error_result('Remote path test timed out')
        except Exception as e:
            return ValidationResult.error_result(f'Path test error: {str(e)}')
    
    def _test_rsync_compatibility(self, connection: SSHConnectionDetails) -> ValidationResult:
        """Test rsync compatibility with the remote host"""
        try:
            # Test rsync --version on remote host
            cmd = ['ssh'] + self.config.to_ssh_args() + [
                f'{connection.username}@{connection.hostname}',
                'rsync --version 2>/dev/null | head -1 || echo "RSYNC_MISSING"'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if 'rsync version' in output.lower():
                    return ValidationResult.success_result(f'Rsync available: {output}')
                elif 'RSYNC_MISSING' in output:
                    return ValidationResult.error_result(
                        'rsync not found on remote host - backup will fail'
                    )
                else:
                    return ValidationResult.error_result('Could not determine rsync availability')
            else:
                return ValidationResult.error_result('Could not test rsync on remote host')
                
        except subprocess.TimeoutExpired:
            return ValidationResult.error_result('Rsync compatibility test timed out')
        except Exception as e:
            return ValidationResult.error_result(f'Rsync test error: {str(e)}')
    
    @staticmethod
    def get_validation_summary(result: ValidationResult) -> Dict[str, Any]:
        """Convert ValidationResult to API response format"""
        response = {
            'success': result.success,
            'message': result.message
        }
        
        if result.details:
            response['details'] = result.details
        
        if result.tested_from:
            response['tested_from'] = result.tested_from
        
        return response


class SSHValidationCache:
    """Simple in-memory cache for SSH validation results"""
    
    def __init__(self, cache_duration_minutes: int = 30):
        self.cache: Dict[str, Tuple[ValidationResult, datetime]] = {}
        self.cache_duration_minutes = cache_duration_minutes
    
    def get_cached_result(self, source: str) -> Optional[ValidationResult]:
        """Get cached validation result if still valid"""
        if source not in self.cache:
            return None
        
        result, timestamp = self.cache[source]
        age_minutes = (datetime.now() - timestamp).total_seconds() / 60
        
        if age_minutes <= self.cache_duration_minutes:
            return result
        else:
            # Cache expired, remove it
            del self.cache[source]
            return None
    
    def cache_result(self, source: str, result: ValidationResult):
        """Cache a validation result"""
        self.cache[source] = (result, datetime.now())
    
    def clear_cache(self):
        """Clear all cached results"""
        self.cache.clear()


# Global validator instance with caching
_default_validator = SSHValidator()
_validation_cache = SSHValidationCache()


def validate_ssh_source(source: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Public API function for SSH source validation with optional caching
    Maintains backward compatibility while using modern implementation
    """
    if use_cache:
        cached_result = _validation_cache.get_cached_result(source)
        if cached_result:
            return SSHValidator.get_validation_summary(cached_result)
    
    result = _default_validator.validate_ssh_source(source)
    
    if use_cache:
        _validation_cache.cache_result(source, result)
    
    return SSHValidator.get_validation_summary(result)