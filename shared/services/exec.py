"""
Execution Infrastructure
Command execution, process management, obfuscation, and core execution services
Extracted from services/shared.py for better organization and maintainability
"""
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel
import subprocess


# =============================================================================
# ===                      EXECUTION INFRASTRUCTURE                        ===
# =============================================================================

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
                import re
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
        from shared.services.ssh import SSHExecutionService
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
        from shared.services.ssh import SSHExecutionService
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


class ResticArgumentBuilder:
    """Builds Restic command arguments for various operations"""
    
    @staticmethod
    def build_backup_args(config, dry_run: bool = False) -> List[str]:
        """Build backup command arguments"""
        args = ['backup']  # Add backup command
        
        # Source paths
        source_paths = config.source_config.get('source_paths', [])
        for path_config in source_paths:
            args.append(path_config['path'])
        
        # Exclude patterns only (restic doesn't support --include)
        for path_config in source_paths:
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
    
    @staticmethod
    def build_environment(dest_config: Dict[str, Any]) -> Dict[str, str]:
        """Build complete environment for restic operations with all credentials"""
        import os
        env = os.environ.copy()
        
        # Always required
        env['RESTIC_PASSWORD'] = dest_config['password']
        
        # Add S3 credentials if S3 repository
        if dest_config.get('repo_type') == 's3':
            if 's3_access_key' in dest_config:
                env['AWS_ACCESS_KEY_ID'] = dest_config['s3_access_key']
            if 's3_secret_key' in dest_config:
                env['AWS_SECRET_ACCESS_KEY'] = dest_config['s3_secret_key']
        
        # Future: Add other cloud provider credentials here
        # elif dest_config.get('repo_type') == 'azure':
        #     env['AZURE_ACCOUNT_NAME'] = dest_config.get('azure_account_name', '')
        #     env['AZURE_ACCOUNT_KEY'] = dest_config.get('azure_account_key', '')
        
        return env
    
    @staticmethod 
    def build_ssh_environment_flags(dest_config: Dict[str, Any]) -> List[str]:
        """Build environment flags for SSH container commands"""
        flags = []
        
        # Always required
        flags.extend(['-e', f'RESTIC_PASSWORD={dest_config["password"]}'])
        
        # Add S3 credentials if S3 repository
        if dest_config.get('repo_type') == 's3':
            if 's3_access_key' in dest_config:
                flags.extend(['-e', f'AWS_ACCESS_KEY_ID={dest_config["s3_access_key"]}'])
            if 's3_secret_key' in dest_config:
                flags.extend(['-e', f'AWS_SECRET_ACCESS_KEY={dest_config["s3_secret_key"]}'])
        
        # Future: Add other cloud provider credentials here
        # elif dest_config.get('repo_type') == 'azure':
        #     flags.extend(['-e', f'AZURE_ACCOUNT_NAME={dest_config.get("azure_account_name", "")}'])
        #     flags.extend(['-e', f'AZURE_ACCOUNT_KEY={dest_config.get("azure_account_key", "")}'])
        
        return flags


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
        from shared.services.ssh import ResticSSHService
        restic_ssh = ResticSSHService()
        return restic_ssh.should_use_ssh(dest_config, source_config, operation_type)
    
    def _execute_locally(
        self, 
        dest_config: Dict[str, Any], 
        command_args: List[str], 
        timeout: int
    ) -> subprocess.CompletedProcess:
        """Execute restic command locally with proper credentials"""
        
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
        from shared.services.ssh import ResticSSHService
        restic_ssh = ResticSSHService()
        return restic_ssh.execute_restic_via_ssh(dest_config, command_args, source_config, timeout)