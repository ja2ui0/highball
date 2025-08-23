"""
Unified Execution Service
Consolidates command execution and obfuscation functionality
Replaces: command_execution_service.py, command_obfuscation.py
"""
import subprocess
import shlex
import re
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class OperationType(Enum):
    """Operation type enumeration for execution context determination"""
    # UI operations (execute locally from Highball container)
    UI = "ui"
    BROWSE = "browse"
    INSPECT = "inspect"
    
    # Source operations (execute via SSH when source is SSH)
    BACKUP = "backup"
    RESTORE = "restore"
    MAINTENANCE = "maintenance"
    INIT = "init"
    
    # Maintenance subtypes
    DISCARD = "discard"  # forget+prune combined
    CHECK = "check"      # repository check
    
    # Default
    GENERAL = "general"


# =============================================================================
# **DATA STRUCTURES** - Execution configuration and results
# =============================================================================

class ExecutionConfig(BaseModel):
    """Execution configuration parameters"""
    timeout: int = 120
    capture_output: bool = True
    text: bool = True
    shell: bool = False


class ExecutionResult(BaseModel):
    """Execution result data structure"""
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timeout_expired: bool = False


# =============================================================================
# **COMMAND OBFUSCATION CONCERN** - Security and logging safety
# =============================================================================

class CommandObfuscationService:
    """Command obfuscation - ONLY handles password masking for logging"""
    
    # Password patterns for different services
    PASSWORD_PATTERNS = [
        r'RESTIC_PASSWORD=([^\s]+)',
        r'--password[=\s]+([^\s]+)',
        r'-p\s+([^\s]+)',
        r'password[=:\s]+([^\s\'\"]+)',
        r'AWS_SECRET_ACCESS_KEY=([^\s]+)',
        r'secret[=:\s]+([^\s\'\"]+)'
    ]
    
    @classmethod
    def obfuscate_password_in_command(cls, command: List[str], password: str = None) -> List[str]:
        """Obfuscation concern: mask passwords in command arrays for safe logging"""
        if not command:
            return command
        
        obfuscated = []
        for part in command:
            obfuscated_part = part
            
            # If specific password provided, mask it
            if password and password in part:
                obfuscated_part = part.replace(password, '***')
            
            # Apply generic password patterns
            for pattern in cls.PASSWORD_PATTERNS:
                obfuscated_part = re.sub(pattern, r'\1***', obfuscated_part, flags=re.IGNORECASE)
            
            obfuscated.append(obfuscated_part)
        
        return obfuscated
    
    @classmethod
    def obfuscate_command_array(cls, command_array: List[str]) -> List[str]:
        """Obfuscation concern: mask sensitive data in command arrays"""
        return cls.obfuscate_password_in_command(command_array)
    
    @classmethod
    def obfuscate_environment_vars(cls, env_vars: Dict[str, str]) -> Dict[str, str]:
        """Obfuscation concern: mask sensitive environment variables"""
        obfuscated = {}
        sensitive_keys = {'RESTIC_PASSWORD', 'AWS_SECRET_ACCESS_KEY', 'PASSWORD', 'SECRET'}
        
        for key, value in env_vars.items():
            if any(sensitive in key.upper() for sensitive in sensitive_keys):
                obfuscated[key] = '***'
            else:
                obfuscated[key] = value
        
        return obfuscated


# =============================================================================
# **COMMAND EXECUTION CONCERN** - Process execution and management
# =============================================================================

class CommandExecutionService:
    """Command execution - ONLY handles process execution and result management"""
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig()
    
    def execute_locally(
        self, 
        command: List[str], 
        environment_vars: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ) -> ExecutionResult:
        """Execution concern: run command locally with proper error handling"""
        try:
            # Prepare environment
            env = None
            if environment_vars:
                import os
                env = os.environ.copy()
                env.update(environment_vars)
            
            # Execute command
            result = subprocess.run(
                command,
                timeout=self.config.timeout,
                capture_output=self.config.capture_output,
                text=self.config.text,
                shell=self.config.shell,
                env=env,
                cwd=working_directory
            )
            
            return ExecutionResult(
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or ""
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                returncode=-1,
                stderr="Command timed out",
                timeout_expired=True
            )
        except Exception as e:
            return ExecutionResult(
                returncode=-1,
                stderr=f"Execution error: {str(e)}"
            )
    
    def execute_via_ssh(
        self,
        hostname: str,
        username: str,
        command: List[str],
        ssh_options: Optional[List[str]] = None
    ) -> ExecutionResult:
        """Execution concern: run command on remote host via SSH"""
        # Build SSH command
        ssh_cmd = ['ssh']
        
        # Add SSH options
        default_options = [
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null'
        ]
        ssh_cmd.extend(ssh_options or default_options)
        
        # Add target and command
        ssh_cmd.append(f'{username}@{hostname}')
        
        # Convert command to shell string with proper quote handling
        container_cmd_str = shlex.join(command)
        # Allow shell evaluation of $(id -u):$(id -g) on remote host (like highball-main)
        container_cmd_str = container_cmd_str.replace("'$(id -u):$(id -g)'", "$(id -u):$(id -g)")
        
        ssh_cmd.append(container_cmd_str)
        
        return self.execute_locally(ssh_cmd)
    
    def execute_container_via_ssh(
        self,
        hostname: str,
        username: str,
        container_command: List[str],
        ssh_options: Optional[List[str]] = None
    ) -> ExecutionResult:
        """Execution concern: run container command on remote host via SSH"""
        return self.execute_via_ssh(hostname, username, container_command, ssh_options)
    
    def execute_with_progress_monitoring(
        self,
        command: List[str],
        progress_callback: Optional[callable] = None,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execution concern: run command with real-time progress monitoring"""
        try:
            # Prepare environment
            env = None
            if environment_vars:
                import os
                env = os.environ.copy()
                env.update(environment_vars)
            
            # Start process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            stdout_lines = []
            stderr_lines = []
            
            # Monitor output
            while True:
                output = process.stdout.readline()
                error = process.stderr.readline()
                
                if output:
                    stdout_lines.append(output.strip())
                    if progress_callback:
                        progress_callback(output.strip())
                
                if error:
                    stderr_lines.append(error.strip())
                
                # Check if process finished
                if process.poll() is not None:
                    break
            
            # Get final returncode
            returncode = process.wait()
            
            return ExecutionResult(
                returncode=returncode,
                stdout='\n'.join(stdout_lines),
                stderr='\n'.join(stderr_lines)
            )
            
        except Exception as e:
            return ExecutionResult(
                returncode=-1,
                stderr=f"Progress monitoring error: {str(e)}"
            )


# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates execution and obfuscation
# =============================================================================

class ExecutionService:
    """Unified execution service - ONLY coordinates execution and obfuscation concerns"""
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.executor = CommandExecutionService(config)
        self.obfuscator = CommandObfuscationService()
    
    # **EXECUTION DELEGATION** - Pure delegation to execution concern
    def execute_local_command(
        self,
        command: List[str],
        environment_vars: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None
    ) -> ExecutionResult:
        """Delegation: execute command locally"""
        return self.executor.execute_locally(command, environment_vars, working_directory)
    
    def execute_ssh_command(
        self,
        hostname: str,
        username: str,
        command: List[str],
        ssh_options: Optional[List[str]] = None
    ) -> ExecutionResult:
        """Delegation: execute command via SSH"""
        return self.executor.execute_via_ssh(hostname, username, command, ssh_options)
    
    def execute_container_command(
        self,
        hostname: str,
        username: str,
        container_command: List[str]
    ) -> ExecutionResult:
        """Delegation: execute container command via SSH"""
        return self.executor.execute_container_via_ssh(hostname, username, container_command)
    
    def execute_with_progress(
        self,
        command: List[str],
        progress_callback: Optional[callable] = None,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Delegation: execute with progress monitoring"""
        return self.executor.execute_with_progress_monitoring(command, progress_callback, environment_vars)
    
    # **OBFUSCATION DELEGATION** - Pure delegation to obfuscation concern
    def obfuscate_command_for_logging(self, command: List[str], password: str = None) -> List[str]:
        """Delegation: obfuscate command for safe logging"""
        return self.obfuscator.obfuscate_password_in_command(command, password)
    
    def obfuscate_environment_for_logging(self, env_vars: Dict[str, str]) -> Dict[str, str]:
        """Delegation: obfuscate environment variables for safe logging"""
        return self.obfuscator.obfuscate_environment_vars(env_vars)


# =============================================================================
# **RESTIC EXECUTION SERVICE** - Unified Restic execution with automatic context detection
# =============================================================================

class ResticExecutionService:
    """Unified Restic execution with automatic credential and SSH handling"""
    
    def __init__(self):
        self.executor = ExecutionService()
    
    def execute_restic_command(
        self, 
        dest_config: Dict[str, Any],
        command_args: List[str],
        source_config: Optional[Dict[str, Any]] = None,
        operation_type: OperationType = OperationType.GENERAL,
        timeout: int = 120
    ) -> subprocess.CompletedProcess:
        """Execute restic command with automatic execution context detection
        
        Args:
            dest_config: Destination configuration with credentials
            command_args: Restic command arguments (e.g., ['snapshots', '--json'])
            source_config: Source configuration for SSH detection
            operation_type: Type of operation for execution context determination
            timeout: Command timeout in seconds
            
        Returns:
            subprocess.CompletedProcess result
        """
        
        if self._should_use_ssh(dest_config, source_config, operation_type):
            return self._execute_via_ssh(dest_config, command_args, source_config, timeout)
        else:
            return self._execute_locally(dest_config, command_args, timeout)
    
    def _should_use_ssh(self, dest_config: Dict[str, Any], source_config: Optional[Dict[str, Any]], operation_type: OperationType) -> bool:
        """Determine if SSH execution should be used based on context"""
        if not source_config:
            return False
        
        # For same_as_origin repositories, always use SSH (repository is on origin host filesystem)
        if dest_config.get('repo_type') == 'same_as_origin':
            return True
        
        # UI operations execute locally from Highball container (for networked repos)
        if operation_type in [OperationType.UI, OperationType.BROWSE, OperationType.INSPECT]:
            return False
            
        # Source operations use SSH when source is SSH
        has_ssh_config = bool(source_config.get('hostname') and source_config.get('username'))
        
        if operation_type in [OperationType.BACKUP, OperationType.RESTORE, OperationType.MAINTENANCE, OperationType.INIT]:
            return has_ssh_config
            
        # General operations use SSH when available
        return has_ssh_config
    
    def _execute_locally(
        self, 
        dest_config: Dict[str, Any], 
        command_args: List[str], 
        timeout: int
    ) -> subprocess.CompletedProcess:
        """Execute restic command locally with proper credentials"""
        from models.backup import ResticArgumentBuilder
        
        # Build environment with all credentials (S3, etc.)
        env = ResticArgumentBuilder.build_environment(dest_config)
        
        # Build restic command
        repo_uri = dest_config.get('repo_uri', '')
        cmd = ['restic', '-r', repo_uri] + command_args
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
    
    def _execute_via_ssh(
        self, 
        dest_config: Dict[str, Any], 
        command_args: List[str], 
        source_config: Dict[str, Any], 
        timeout: int
    ) -> subprocess.CompletedProcess:
        """Execute restic command via SSH using container"""
        from models.backup import ResticArgumentBuilder
        
        # Extract SSH configuration
        hostname = source_config['hostname']
        username = source_config['username']
        container_runtime = source_config.get('container_runtime', 'docker')
        
        # Build environment flags for container
        env_flags = ResticArgumentBuilder.build_ssh_environment_flags(dest_config)
        
        # Build container command
        repo_uri = dest_config.get('repo_uri', '')
        container_cmd = [
            container_runtime, 'run', '--rm', '--user', '$(id -u):$(id -g)'
        ] + env_flags
        
        # Add volume mount for same_as_origin repositories (directory should exist from validation)  
        if dest_config.get('repo_type') == 'same_as_origin':
            # Mount the repository directory into container
            container_cmd.extend(['-v', f'{repo_uri}:{repo_uri}'])
        
        # For ALL SSH operations, mount source paths (not just same_as_origin)
        if source_config:
            # For backup operations, mount source paths as read-only
            if 'backup' in command_args:
                source_paths = source_config.get('source_paths', [])
                for path_config in source_paths:
                    source_path = path_config['path']
                    container_cmd.extend(['-v', f'{source_path}:{source_path}:ro'])
            
            # For restore operations, mount source paths as read-write
            if 'restore' in command_args:
                source_paths = source_config.get('source_paths', [])
                for path_config in source_paths:
                    source_path = path_config['path']
                    container_cmd.extend(['-v', f'{source_path}:{source_path}'])
        
        container_cmd.extend([
            'restic/restic:0.18.0',
            '-r', repo_uri
        ] + command_args)
        
        # DEBUG: Log the container command for same_as_origin
        # Execute via SSH
        return self.executor.execute_ssh_command(hostname, username, container_cmd)


# Legacy compatibility functions
def obfuscate_password_in_command(command: List[str], password: str = None) -> List[str]:
    """Legacy compatibility: obfuscate password in command"""
    return CommandObfuscationService.obfuscate_password_in_command(command, password)