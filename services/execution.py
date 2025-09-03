"""
Unified Execution Service
Consolidates command execution and obfuscation functionality
Replaces: command_execution_service.py, command_obfuscation.py
"""
import subprocess
import shlex
import re
import base64
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel


# Import moved infrastructure from shared.py
from services.shared import OperationType, ExecutionConfig, ExecutionResult, CommandObfuscationService


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
        """Execution concern: delegate to centralized SSH execution service"""
        from services.shared import SSHExecutionService
        ssh_service = SSHExecutionService()
        return ssh_service.execute_via_ssh(hostname, username, command)
    
    def execute_container_via_ssh(
        self,
        hostname: str,
        username: str,
        container_command: List[str],
        ssh_options: Optional[List[str]] = None
    ) -> ExecutionResult:
        """Execution concern: delegate to centralized SSH execution service"""
        from services.shared import SSHExecutionService
        ssh_service = SSHExecutionService()
        return ssh_service.execute_container_via_ssh(hostname, username, container_command)
    
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
        """Determine if SSH execution should be used based on context - delegate to shared service"""
        from services.shared import ResticSSHService
        restic_ssh = ResticSSHService()
        return restic_ssh.should_use_ssh(dest_config, source_config, operation_type)
    
    def _execute_locally(
        self, 
        dest_config: Dict[str, Any], 
        command_args: List[str], 
        timeout: int
    ) -> subprocess.CompletedProcess:
        """Execute restic command locally with proper credentials"""
        from models.builders import ResticArgumentBuilder
        
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
        """Execute restic command via SSH using container - delegate to shared service"""
        from services.shared import ResticSSHService
        restic_ssh = ResticSSHService()
        return restic_ssh.execute_restic_via_ssh(dest_config, command_args, source_config, timeout)


# =============================================================================
# **SSH WORKFLOW SERVICE** - SSH key management and validation
# =============================================================================
# MOVED TO shared.py - import from there for compatibility

# Compatibility import - actual implementation is in shared.py
from services.shared import SSHWorkflowService


# Legacy compatibility functions
def obfuscate_password_in_command(command: List[str], password: str = None) -> List[str]:
    """Legacy compatibility: obfuscate password in command"""
    return CommandObfuscationService.obfuscate_password_in_command(command, password)