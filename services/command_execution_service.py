"""
Unified command execution service for SSH, local, and container operations
Consolidates execution patterns with consistent error handling and logging
"""
import subprocess
import shlex
import json
import os
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass


@dataclass
class ExecutionConfig:
    """Configuration for command execution"""
    timeout: int = 30
    capture_output: bool = True
    text: bool = True
    connect_timeout: int = 10
    batch_mode: bool = True
    strict_host_checking: bool = False
    known_hosts_file: str = "/dev/null"


@dataclass 
class ExecutionResult:
    """Standardized result for all execution types"""
    success: bool
    returncode: int
    stdout: str
    stderr: str
    error_message: Optional[str] = None
    execution_type: str = "unknown"
    
    @classmethod
    def from_subprocess_result(cls, result: subprocess.CompletedProcess, execution_type: str) -> 'ExecutionResult':
        """Create ExecutionResult from subprocess.CompletedProcess"""
        return cls(
            success=result.returncode == 0,
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            execution_type=execution_type
        )
    
    @classmethod
    def timeout_result(cls, execution_type: str) -> 'ExecutionResult':
        """Create timeout error result"""
        return cls(
            success=False,
            returncode=-1,
            stdout="",
            stderr="Command timed out",
            error_message="Command timed out",
            execution_type=execution_type
        )
    
    @classmethod
    def exception_result(cls, exception: Exception, execution_type: str) -> 'ExecutionResult':
        """Create exception error result"""
        return cls(
            success=False,
            returncode=-1,
            stdout="",
            stderr=str(exception),
            error_message=str(exception),
            execution_type=execution_type
        )


class CommandExecutionService:
    """Unified service for executing commands via SSH, locally, or in containers"""
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig()
    
    def execute_via_ssh(
        self, 
        hostname: str, 
        username: str, 
        command: Union[str, List[str]], 
        env_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute command via SSH with environment variables"""
        try:
            # Build SSH command
            ssh_cmd = self._build_ssh_command(hostname, username, command, env_vars)
            
            # Execute with timeout
            result = subprocess.run(
                ssh_cmd, 
                capture_output=self.config.capture_output,
                text=self.config.text,
                timeout=self.config.timeout
            )
            
            return ExecutionResult.from_subprocess_result(result, "ssh")
            
        except subprocess.TimeoutExpired:
            return ExecutionResult.timeout_result("ssh")
        except Exception as e:
            return ExecutionResult.exception_result(e, "ssh")
    
    def execute_locally(
        self, 
        command: List[str], 
        env_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute command locally with environment variables"""
        try:
            # Build environment
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)
            
            # Execute with timeout
            result = subprocess.run(
                command,
                capture_output=self.config.capture_output,
                text=self.config.text,
                timeout=self.config.timeout,
                env=env
            )
            
            return ExecutionResult.from_subprocess_result(result, "local")
            
        except subprocess.TimeoutExpired:
            return ExecutionResult.timeout_result("local")
        except Exception as e:
            return ExecutionResult.exception_result(e, "local")
    
    def execute_container_via_ssh(
        self,
        hostname: str,
        username: str,
        container_command: List[str]
    ) -> ExecutionResult:
        """Execute container command via SSH"""
        try:
            # Convert container command to string with proper escaping
            container_cmd_str = shlex.join(container_command)
            # Allow shell evaluation of $(id -u):$(id -g) on remote host
            container_cmd_str = container_cmd_str.replace("'$(id -u):$(id -g)'", "$(id -u):$(id -g)")
            
            # Build SSH command
            ssh_cmd = [
                'ssh', 
                '-o', f'ConnectTimeout={self.config.connect_timeout}',
                '-o', f'BatchMode={"yes" if self.config.batch_mode else "no"}',
                '-o', f'StrictHostKeyChecking={"yes" if self.config.strict_host_checking else "no"}',
                '-o', f'UserKnownHostsFile={self.config.known_hosts_file}',
                '-o', 'LogLevel=ERROR',
                f'{username}@{hostname}',
                container_cmd_str
            ]
            
            # Execute with timeout
            result = subprocess.run(
                ssh_cmd,
                capture_output=self.config.capture_output,
                text=self.config.text,
                timeout=self.config.timeout
            )
            
            return ExecutionResult.from_subprocess_result(result, "container_ssh")
            
        except subprocess.TimeoutExpired:
            return ExecutionResult.timeout_result("container_ssh")
        except Exception as e:
            return ExecutionResult.exception_result(e, "container_ssh")
    
    def _build_ssh_command(
        self, 
        hostname: str, 
        username: str, 
        command: Union[str, List[str]], 
        env_vars: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """Build SSH command with proper environment handling"""
        # Convert command to string if it's a list
        if isinstance(command, list):
            command_str = shlex.join(command)
        else:
            command_str = command
        
        # Build environment exports
        env_exports = []
        if env_vars:
            for key, value in env_vars.items():
                # Use proper shell escaping for values
                escaped_value = value.replace("'", "'\"'\"'")  # Escape single quotes
                env_exports.append(f"export {key}='{escaped_value}'")
        
        # Combine environment and command
        remote_command = '; '.join(env_exports + [command_str])
        
        # Build SSH command
        ssh_cmd = [
            'ssh',
            '-o', f'ConnectTimeout={self.config.connect_timeout}',
            '-o', f'BatchMode={"yes" if self.config.batch_mode else "no"}',
            '-o', f'StrictHostKeyChecking={"yes" if self.config.strict_host_checking else "no"}',
            '-o', f'UserKnownHostsFile={self.config.known_hosts_file}',
            f'{username}@{hostname}',
            remote_command
        ]
        
        return ssh_cmd
    
    def test_ssh_connectivity(self, hostname: str, username: str) -> ExecutionResult:
        """Test basic SSH connectivity"""
        return self.execute_via_ssh(hostname, username, 'echo "SSH_OK"')
    
    def test_remote_path(self, hostname: str, username: str, path: str) -> ExecutionResult:
        """Test if remote path exists and is accessible"""
        command = f'test -e "{path}" && echo "PATH_EXISTS" || echo "PATH_MISSING"'
        return self.execute_via_ssh(hostname, username, command)
    
    def test_remote_command(self, hostname: str, username: str, command: str) -> ExecutionResult:
        """Test if a command exists on remote host"""
        test_command = f'{command} --version 2>/dev/null || echo "COMMAND_MISSING"'
        return self.execute_via_ssh(hostname, username, test_command)
    
    def get_safe_result_for_logging(self, result: ExecutionResult, env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get sanitized execution result for logging"""
        safe_result = {
            'success': result.success,
            'returncode': result.returncode,
            'execution_type': result.execution_type
        }
        
        # Sanitize output if environment variables might be exposed
        if env_vars:
            safe_stdout = result.stdout
            safe_stderr = result.stderr
            
            for key, value in env_vars.items():
                if self._is_sensitive_key(key) and value:
                    safe_stdout = safe_stdout.replace(value, '***')
                    safe_stderr = safe_stderr.replace(value, '***')
            
            safe_result['stdout'] = safe_stdout
            safe_result['stderr'] = safe_stderr
        else:
            safe_result['stdout'] = result.stdout
            safe_result['stderr'] = result.stderr
        
        if result.error_message:
            safe_result['error_message'] = result.error_message
        
        return safe_result
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if an environment variable key contains sensitive data"""
        sensitive_keys = {
            'RESTIC_PASSWORD', 'AWS_SECRET_ACCESS_KEY', 'password', 'secret', 'token',
            'rest_password', 'aws_secret_key', 'sftp_password'
        }
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in sensitive_keys)
    
    def parse_json_output(self, stdout: str) -> Dict[str, Any]:
        """Parse JSON output with error handling"""
        try:
            return {
                'success': True,
                'data': json.loads(stdout) if stdout.strip() else None
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Failed to parse JSON: {str(e)}',
                'raw_output': stdout
            }