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
            '-i', '/config/local/secrets/.ssh/id_highball',
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
        """Execute restic command via SSH using container"""
        from models.builders import ResticArgumentBuilder
        
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


# =============================================================================
# **SSH WORKFLOW SERVICE** - SSH key management and validation
# =============================================================================

class SSHWorkflowService:
    """Service for SSH key management and connection validation workflows"""
    
    def push_keys_and_validate_workflow(self, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Complete workflow: push keys → validate connection → detect capabilities"""
        progress_messages = []
        
        try:
            # Step 1: Test initial connection
            progress_messages.append("• Testing initial SSH connection...")
            initial_test = self._test_initial_ssh_connection(hostname, username, password, use_password)
            if not initial_test['success']:
                progress_messages.append(f"✗ Initial connection failed: {initial_test.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': '\n'.join(progress_messages)
                }
            progress_messages.append("✓ Initial SSH connection successful")
            
            # Step 2: Check for existing key in authorized_keys
            progress_messages.append("• Checking for existing Highball key in authorized_keys...")
            key_check = self._check_highball_key_in_authorized_keys(hostname, username)
            
            # Step 3: Push key if needed
            if not key_check['key_exists']:
                progress_messages.append("• Highball key not found, installing...")
                if not use_password:
                    progress_messages.append("✗ Password required to install key")
                    return {
                        'success': False,
                        'validation_message': '\n'.join(progress_messages)
                    }
                push_result = self._push_highball_key(hostname, username, password)
                if not push_result['success']:
                    progress_messages.append(f"✗ Key installation failed: {push_result.get('validation_message', 'Unknown error')}")
                    return {
                        'success': False,
                        'validation_message': '\n'.join(progress_messages)
                    }
                progress_messages.append("✓ Highball key installed successfully")
            else:
                progress_messages.append("✓ Highball key already present in authorized_keys")
            
            # Step 4: Copy keypair to remote host
            progress_messages.append("• Copying Highball keypair to remote host...")
            copy_result = self._copy_keypair_to_remote(hostname, username)
            if not copy_result['success']:
                progress_messages.append(f"✗ Keypair copy failed: {copy_result.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': '\n'.join(progress_messages)
                }
            progress_messages.append("✓ Keypair copied successfully")
            
            # Step 5: Test final connection and detect capabilities
            progress_messages.append("• Testing final connection and detecting capabilities...")
            final_test = self._test_connection_and_capabilities(hostname, username)
            if not final_test['success']:
                progress_messages.append(f"✗ Final connection test failed: {final_test.get('validation_message', 'Unknown error')}")
                return {
                    'success': False,
                    'validation_message': '\n'.join(progress_messages)
                }
            
            progress_messages.append("✓ All steps completed successfully!")
            
            return {
                'success': True,
                'validation_message': '\n'.join(progress_messages),
                'rsync_available': final_test.get('rsync_available', False),
                'container_runtime': final_test.get('container_runtime', None)
            }
            
        except Exception as e:
            progress_messages.append(f"✗ Workflow failed: {str(e)}")
            return {
                'success': False,
                'validation_message': '\n'.join(progress_messages)
            }

    def _test_initial_ssh_connection(self, hostname: str, username: str, password: str, use_password: bool) -> dict:
        """Test initial SSH connection using password or existing key"""
        import subprocess
        
        if use_password:
            # Test connection with password using sshpass
            cmd = [
                'sshpass', '-p', password,
                'ssh', '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                'echo "INITIAL_SSH_OK"'
            ]
        else:
            # Test connection with existing key
            cmd = [
                'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
                '-o', 'ConnectTimeout=10',
                '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                'echo "INITIAL_SSH_OK"'
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and 'INITIAL_SSH_OK' in result.stdout:
            return {'success': True}
        else:
            return {
                'success': False,
                'validation_message': f'Initial SSH connection failed: {result.stderr.strip()}'
            }

    def _check_highball_key_in_authorized_keys(self, hostname: str, username: str) -> dict:
        """Check if Highball public key exists in remote authorized_keys"""
        import subprocess
        
        # Read our public key
        with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
            our_pubkey = f.read().strip()
        
        # Extract the key part (without comment)
        key_parts = our_pubkey.split()
        if len(key_parts) >= 2:
            key_signature = key_parts[1]  # The actual key data
        else:
            return {'key_exists': False, 'validation_message': 'Invalid public key format'}
        
        # Check if key exists in remote authorized_keys
        cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            f'grep -q "{key_signature}" ~/.ssh/authorized_keys 2>/dev/null && echo "KEY_EXISTS" || echo "KEY_NOT_FOUND"'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            if 'KEY_EXISTS' in result.stdout:
                return {'key_exists': True}
            else:
                return {'key_exists': False}
        else:
            # Fallback: assume key doesn't exist if we can't check
            return {'key_exists': False, 'validation_message': 'Could not check authorized_keys'}

    def _push_highball_key(self, hostname: str, username: str, password: str) -> dict:
        """Push Highball public key to remote authorized_keys using ssh-copy-id"""
        import subprocess
        
        cmd = [
            'sshpass', '-p', password,
            'ssh-copy-id',
            '-i', '/config/local/secrets/.ssh/id_highball.pub',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return {'success': True}
        else:
            return {
                'success': False,
                'validation_message': f'Key installation failed: {result.stderr.strip()}'
            }

    def _copy_keypair_to_remote(self, hostname: str, username: str) -> dict:
        """Copy Highball keypair to remote host ~/.ssh/ directory"""
        import subprocess
        
        try:
            # Copy private key
            private_copy_cmd = [
                'scp', '-i', '/config/local/secrets/.ssh/id_highball',
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '/config/local/secrets/.ssh/id_highball',
                f'{username}@{hostname}:~/.ssh/'
            ]
            
            result = subprocess.run(private_copy_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {
                    'success': False,
                    'validation_message': f'Private key copy failed: {result.stderr.strip()}'
                }
            
            # Copy public key
            public_copy_cmd = [
                'scp', '-i', '/config/local/secrets/.ssh/id_highball',
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '/config/local/secrets/.ssh/id_highball.pub',
                f'{username}@{hostname}:~/.ssh/'
            ]
            
            result = subprocess.run(public_copy_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {
                    'success': False,
                    'validation_message': f'Public key copy failed: {result.stderr.strip()}'
                }
            
            # Set proper permissions
            chmod_cmd = [
                'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}',
                'chmod 600 ~/.ssh/id_highball && chmod 644 ~/.ssh/id_highball.pub'
            ]
            
            result = subprocess.run(chmod_cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return {
                    'success': False,
                    'validation_message': f'Permission setting failed: {result.stderr.strip()}'
                }
            
            return {'success': True}
            
        except Exception as e:
            return {
                'success': False,
                'validation_message': f'Keypair copy failed: {str(e)}'
            }

    def _test_connection_and_capabilities(self, hostname: str, username: str, log_progress=None) -> dict:
        """Test final connection and detect available capabilities"""
        import subprocess
        
        if log_progress:
            log_progress("Testing SSH connection with Highball keypair...")
        
        # Test SSH connection and detect capabilities
        test_cmd = [
            'ssh', '-i', '/config/local/secrets/.ssh/id_highball',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{username}@{hostname}',
            'echo "SSH_OK" && which rsync >/dev/null 2>&1 && echo "RSYNC_AVAILABLE" || echo "RSYNC_UNAVAILABLE" && which docker >/dev/null 2>&1 && echo "DOCKER_AVAILABLE" || which podman >/dev/null 2>&1 && echo "PODMAN_AVAILABLE" || echo "NO_CONTAINER_RUNTIME"'
        ]
        
        result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and 'SSH_OK' in result.stdout:
            if log_progress:
                log_progress("✓ SSH connection successful")
            
            # Parse capabilities
            output = result.stdout
            rsync_available = 'RSYNC_AVAILABLE' in output
            container_runtime = None
            
            if 'DOCKER_AVAILABLE' in output:
                container_runtime = 'docker'
            elif 'PODMAN_AVAILABLE' in output:
                container_runtime = 'podman'
            
            if log_progress:
                log_progress(f"✓ Capabilities detected: rsync={rsync_available}, runtime={container_runtime}")
            
            return {
                'success': True,
                'rsync_available': rsync_available,
                'container_runtime': container_runtime
            }
        else:
            error_msg = f'SSH connection test failed: {result.stderr.strip()}'
            if log_progress:
                log_progress(f"✗ {error_msg}")
            return {
                'success': False,
                'validation_message': error_msg
            }


# Legacy compatibility functions
def obfuscate_password_in_command(command: List[str], password: str = None) -> List[str]:
    """Legacy compatibility: obfuscate password in command"""
    return CommandObfuscationService.obfuscate_password_in_command(command, password)