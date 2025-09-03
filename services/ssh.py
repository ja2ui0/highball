"""
SSH Operations and Container Services
SSH orchestration, container operations, and cross-domain services
Extracted from services/shared.py for better organization and maintainability
"""
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import shlex
import subprocess
import base64
import tempfile
import os

# Import execution infrastructure from new location
from services.exec import OperationType, ExecutionResult, CommandObfuscationService


# =============================================================================
# ===                         SSH OPERATIONS                               ===
# =============================================================================

class SSHCommandFactory:
    """Centralized SSH command building to eliminate 15+ instances of duplication"""
    
    def __init__(self, 
                 ssh_key_path: str = '/config/local/secrets/.ssh/id_highball',
                 connect_timeout: Optional[int] = None):
        self.ssh_key_path = ssh_key_path
        # Future: could read from origin/dest config here
        self.connect_timeout = connect_timeout or 5  # Default 5s - reasonable for most networks
        self.base_options = [
            '-o', 'BatchMode=yes', 
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null'
        ]
    
    
    def build_ssh_command(
        self, 
        hostname: str, 
        username: str, 
        remote_command: str,
        use_key: bool = True,
        port: Optional[int] = None,
        connect_timeout: Optional[int] = None,
        password: Optional[str] = None,
        base_cmd: str = 'ssh'
    ) -> List[str]:
        """Build standard SSH command with consistent options"""
        cmd = [base_cmd]
        
        # Password auth: no key, no BatchMode (interactive)
        if password:
            # Don't use key for password auth
            pass
        elif use_key:
            # Key auth: use Highball key + BatchMode
            cmd.extend(['-i', self.ssh_key_path])
        
        if port:
            cmd.extend(['-p', str(port)])
        
        # Build options - exclude BatchMode for password auth
        timeout = connect_timeout or self.connect_timeout
        cmd.extend(['-o', f'ConnectTimeout={timeout}'])
        cmd.extend(['-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null'])
        
        # Only add BatchMode for key authentication
        if not password:
            cmd.extend(['-o', 'BatchMode=yes'])
        
        cmd.append(f'{username}@{hostname}')
        cmd.append(remote_command)
        
        # Wrap with sshpass if password provided
        if password:
            cmd = ['sshpass', '-p', password] + cmd
        
        return cmd
    
    def build_ssh_copy_id_command(
        self,
        hostname: str,
        username: str, 
        key_path: str,
        password: str,
        port: Optional[int] = None
    ) -> List[str]:
        """Build ssh-copy-id command with consistent options"""
        cmd = ['sshpass', '-p', password, 'ssh-copy-id']
        
        # Add key path
        cmd.extend(['-i', key_path])
        
        # Add SSH options that ssh-copy-id understands
        cmd.extend(['-o', f'ConnectTimeout={self.connect_timeout}'])
        cmd.extend(['-o', 'StrictHostKeyChecking=no'])
        cmd.extend(['-o', 'UserKnownHostsFile=/dev/null'])
        
        # Add port if specified
        if port:
            cmd.extend(['-p', str(port)])
        
        # Add target
        cmd.append(f'{username}@{hostname}')
        
        return cmd


class SSHExecutionService:
    """SSH command execution - ONLY handles SSH execution using centralized SSHCommandFactory"""
    
    def __init__(self, ssh_factory: Optional[SSHCommandFactory] = None):
        self.ssh_factory = ssh_factory or SSHCommandFactory()
        self.obfuscation = CommandObfuscationService()
    
    def execute_via_ssh(
        self,
        hostname: str,
        username: str,
        command: List[str],
        ssh_password: Optional[str] = None,
        ssh_port: Optional[int] = None,
        timeout: int = 120
    ) -> ExecutionResult:
        """Execute command on remote host via SSH using centralized factory"""
        
        # Convert command list to shell string for SSH transmission
        container_cmd_str = shlex.join(command)
        # Allow shell evaluation of $(id -u):$(id -g) on remote host (like highball-main)
        container_cmd_str = container_cmd_str.replace("'$(id -u):$(id -g)'", "$(id -u):$(id -g)")
        
        # Build SSH command using centralized factory (eliminates DRY violation)
        ssh_cmd = self.ssh_factory.build_ssh_command(
            hostname=hostname,
            username=username,
            remote_command=container_cmd_str,
            password=ssh_password,
            port=ssh_port,
            connect_timeout=10
        )
        
        # Execute with proper logging obfuscation
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return ExecutionResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                timeout_expired=False
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                returncode=-1,
                stdout="",
                stderr=f"SSH command timed out after {timeout} seconds",
                timeout_expired=True
            )
        except Exception as e:
            return ExecutionResult(
                returncode=-1,
                stdout="",
                stderr=f"SSH execution failed: {str(e)}",
                timeout_expired=False
            )
    
    def execute_container_via_ssh(
        self,
        hostname: str,
        username: str,
        container_command: List[str],
        ssh_password: Optional[str] = None,
        ssh_port: Optional[int] = None,
        timeout: int = 120
    ) -> ExecutionResult:
        """Execute container command via SSH using centralized execution"""
        return self.execute_via_ssh(
            hostname, username, container_command, ssh_password, ssh_port, timeout
        )


class ResticSSHService:
    """Restic-specific SSH operations - context determination and SSH execution"""
    
    def __init__(self):
        self.ssh_executor = SSHExecutionService()
    
    def should_use_ssh(self, dest_config: Dict[str, Any], source_config: Optional[Dict[str, Any]], operation_type: OperationType) -> bool:
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
    
    def execute_restic_via_ssh(
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
        
        # Execute via SSH using consolidated service
        result = self.ssh_executor.execute_via_ssh(hostname, username, container_cmd)
        
        # Convert ExecutionResult back to subprocess.CompletedProcess for compatibility
        return subprocess.CompletedProcess(
            args=container_cmd,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr
        )


class SSHWorkflowService:
    """SSH key management and connection validation workflows"""
    
    def __init__(self):
        self.ssh_factory = SSHCommandFactory()
    
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
            
            # Create progress callback for detailed capability detection
            def log_capability_progress(message):
                progress_messages.append(message)
            
            final_test = self._test_connection_and_capabilities(hostname, username, log_capability_progress)
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
        if use_password:
            cmd = self.ssh_factory.build_ssh_command(
                hostname, username, 
                'echo "INITIAL_SSH_OK"',
                use_key=False, 
                password=password,
                connect_timeout=10
            )
        else:
            cmd = self.ssh_factory.build_ssh_command(
                hostname, username,
                'echo "INITIAL_SSH_OK"',
                connect_timeout=10
            )
        
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
        # Read our public key
        with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
            our_pubkey = f.read().strip()
        
        # Extract the key part (without comment)
        key_parts = our_pubkey.split()
        if len(key_parts) >= 2:
            key_signature = key_parts[1]  # The actual key data
        else:
            return {'key_exists': False, 'validation_message': 'Invalid public key format'}
        
        cmd = self.ssh_factory.build_ssh_command(
            hostname, username,
            f'grep -q "{key_signature}" ~/.ssh/authorized_keys 2>/dev/null && echo "KEY_EXISTS" || echo "KEY_NOT_FOUND"',
            connect_timeout=10
        )
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            if 'KEY_EXISTS' in result.stdout:
                return {'key_exists': True}
            else:
                return {'key_exists': False}
        else:
            return {'key_exists': False, 'validation_message': 'Could not check authorized_keys'}

    def _push_highball_key(self, hostname: str, username: str, password: str) -> dict:
        """Push Highball public key to remote authorized_keys using ssh-copy-id"""
        # Use temporary directory as HOME for ssh-copy-id (avoids read-only /var/www issue)
        with tempfile.TemporaryDirectory() as temp_home:
            # Create .ssh directory in temp location
            ssh_dir = os.path.join(temp_home, '.ssh')
            os.makedirs(ssh_dir, mode=0o700)
            
            # Set up environment with writable HOME
            env = os.environ.copy()
            env['HOME'] = temp_home
            
            cmd = [
                'sshpass', '-p', password,
                'ssh-copy-id',
                '-i', '/config/local/secrets/.ssh/id_highball.pub',
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{username}@{hostname}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        
        if result.returncode == 0:
            return {'success': True}
        else:
            return {
                'success': False,
                'validation_message': f'Key installation failed: {result.stderr.strip()}'
            }

    def _copy_keypair_to_remote(self, hostname: str, username: str) -> dict:
        """Copy Highball keypair to remote host ~/.ssh/ directory"""
        try:
            # Read both keys
            with open('/config/local/secrets/.ssh/id_highball', 'r') as f:
                private_key = f.read()
            with open('/config/local/secrets/.ssh/id_highball.pub', 'r') as f:
                public_key = f.read()
            
            # Copy private key using base64 for safe transfer
            private_b64 = base64.b64encode(private_key.encode()).decode()
            private_cmd = self.ssh_factory.build_ssh_command(
                hostname, username,
                f'echo "{private_b64}" | base64 -d > ~/.ssh/id_highball'
            )
            result = subprocess.run(private_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {
                    'success': False,
                    'validation_message': f'Private key copy failed: {result.stderr.strip()}'
                }
            
            # Copy public key using base64 for safe transfer  
            public_b64 = base64.b64encode(public_key.encode()).decode()
            public_cmd = self.ssh_factory.build_ssh_command(
                hostname, username,
                f'echo "{public_b64}" | base64 -d > ~/.ssh/id_highball.pub'
            )
            result = subprocess.run(public_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {
                    'success': False,
                    'validation_message': f'Public key copy failed: {result.stderr.strip()}'
                }
            
            # Set permissions
            chmod_cmd = self.ssh_factory.build_ssh_command(
                hostname, username,
                'chmod 600 ~/.ssh/id_highball && chmod 644 ~/.ssh/id_highball.pub'
            )
            result = subprocess.run(chmod_cmd, capture_output=True, text=True, timeout=30)
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
        if log_progress:
            log_progress("Testing SSH connection with Highball keypair...")
        
        test_cmd = self.ssh_factory.build_ssh_command(
            hostname, username,
            'echo "SSH_OK" && which rsync >/dev/null 2>&1 && echo "RSYNC_AVAILABLE" || echo "RSYNC_UNAVAILABLE" && which docker >/dev/null 2>&1 && echo "DOCKER_AVAILABLE" || which podman >/dev/null 2>&1 && echo "PODMAN_AVAILABLE" || echo "NO_CONTAINER_RUNTIME"',
            connect_timeout=10
        )
        
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


# =============================================================================
# ===                       CONTAINER OPERATIONS                           ===
# =============================================================================

class MountStrategy(Enum):
    """Different mounting strategies for container operations"""
    BACKUP_SOURCES = "backup_sources"
    RESTORE_TO_HIGHBALL = "restore_to_highball" 
    RESTORE_TO_SOURCE = "restore_to_source"


class ResticContainerFactory:
    """Centralized restic container command building for backup, restore, init, maintenance"""
    
    def __init__(self, container_runtime: str = 'docker'):
        self.container_runtime = container_runtime
        self.restic_image = 'restic/restic:0.18.0'
    
    def build_container_command(
        self,
        command_type: str,
        repository_url: str,
        args: List[str],
        environment_vars: Dict[str, str],
        mount_strategy: MountStrategy,
        source_paths: Optional[List[str]] = None,
        restore_target: Optional[str] = None
    ) -> List[str]:
        """Build complete restic container execution command"""
        
        # Base container command
        container_cmd = [self.container_runtime, 'run', '--rm']
        
        # Add environment variables
        for key, value in environment_vars.items():
            container_cmd.extend(['-e', f'{key}={value}'])
        
        # Add volume mounts based on strategy
        mounts = self._get_volume_mounts(mount_strategy, source_paths, restore_target)
        for mount in mounts:
            container_cmd.extend(['-v', mount])
        
        # Add the container image
        container_cmd.append(self.restic_image)
        
        # Add repository argument (restic/restic:0.18.0 has restic as entrypoint)
        container_cmd.extend(['-r', repository_url])
        
        # Add the specific command and arguments
        container_cmd.extend([command_type] + args)
        
        return container_cmd
    
    def _get_volume_mounts(
        self, 
        strategy: MountStrategy, 
        source_paths: Optional[List[str]] = None,
        restore_target: Optional[str] = None
    ) -> List[str]:
        """Generate volume mount specifications based on strategy"""
        mounts = []
        
        if strategy == MountStrategy.BACKUP_SOURCES:
            # Mount source paths for backup operations preserving original paths
            if source_paths:
                for source_path in source_paths:
                    # Mount each source path to same path in container to preserve repository paths
                    mounts.append(f'{source_path}:{source_path}:ro')
        
        elif strategy == MountStrategy.RESTORE_TO_HIGHBALL:
            # Mount Highball's restore directory
            mounts.append('/restore:/restore:rw')
        
        elif strategy == MountStrategy.RESTORE_TO_SOURCE:
            # Mount original source locations for restore
            if source_paths:
                for source_path in source_paths:
                    mounts.append(f'{source_path}:{source_path}:rw')
        
        # Always mount cache directories for performance
        mounts.extend([
            '/tmp/.cache:/tmp/.cache:rw',
            '/tmp:/tmp:rw'
        ])
        
        return mounts
    
    def build_backup_command(
        self,
        repository_url: str,
        source_paths: List[str],
        environment_vars: Dict[str, str],
        backup_args: Optional[List[str]] = None
    ) -> List[str]:
        """Build backup-specific container command"""
        args = backup_args or []
        
        # Add actual source paths to backup command (paths are preserved in container via volume mounts)
        args.extend(source_paths)
        
        return self.build_container_command(
            command_type='backup',
            repository_url=repository_url,
            args=args,
            environment_vars=environment_vars,
            mount_strategy=MountStrategy.BACKUP_SOURCES,
            source_paths=source_paths
        )
    
    def build_restore_command(
        self,
        repository_url: str,
        snapshot_id: str,
        environment_vars: Dict[str, str],
        restore_to_highball: bool = True,
        restore_args: Optional[List[str]] = None
    ) -> List[str]:
        """Build restore-specific container command"""
        args = ['restore', snapshot_id] + (restore_args or [])
        
        if restore_to_highball:
            args.extend(['--target', '/restore'])
            mount_strategy = MountStrategy.RESTORE_TO_HIGHBALL
        else:
            mount_strategy = MountStrategy.RESTORE_TO_SOURCE
        
        return self.build_container_command(
            command_type='',  # Empty because restore is already in args
            repository_url=repository_url,
            args=args,
            environment_vars=environment_vars,
            mount_strategy=mount_strategy
        )
    
    def wrap_with_ssh(
        self,
        container_command: List[str],
        ssh_hostname: str,
        ssh_username: str,
        ssh_factory: SSHCommandFactory
    ) -> List[str]:
        """Wrap container command for SSH execution"""
        escaped_cmd = shlex.join(container_command)
        return ssh_factory.build_ssh_command(ssh_hostname, ssh_username, escaped_cmd)



# =============================================================================
# ===                    CROSS-DOMAIN SERVICES                             ===
# =============================================================================

class JobConflictManager:
    """Conflict management functionality - ONLY handles resource conflict detection"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        from jobs.services.manage import JobProcessTracker
        self.process_tracker = JobProcessTracker()
    
    def get_job_resources(self, job_config: Dict[str, Any]) -> Dict[str, Set[str]]:
        """Conflict concern: extract resource identifiers from job configuration"""
        sources = set()
        destinations = set()
        
        # Extract source resources
        if job_config.get('source_type') == 'ssh':
            source_config = job_config.get('source_config', {})
            hostname = source_config.get('hostname')
            if hostname:
                sources.add(hostname.lower())
        
        # Extract destination resources  
        dest_type = job_config.get('dest_type')
        dest_config = job_config.get('dest_config', {})
        
        if dest_type == 'ssh':
            hostname = dest_config.get('hostname')
            if hostname:
                destinations.add(hostname.lower())
        elif dest_type == 'rsyncd':
            hostname = dest_config.get('hostname')
            if hostname:
                destinations.add(hostname.lower())
        elif dest_type == 'restic':
            repo_uri = dest_config.get('repo_uri', '')
            if repo_uri:
                destinations.add(repo_uri)
        
        return {'sources': sources, 'destinations': destinations}
    
    def check_for_conflicts(self, job_name: str) -> List[str]:
        """Conflict concern: detect if job conflicts with currently running jobs"""
        # Get this job's config
        jobs = self.backup_config.config.get('backup_jobs', {})
        job_config = jobs.get(job_name)
        if not job_config:
            return []
        
        job_resources = self.get_job_resources(job_config)
        running_jobs = self.process_tracker.get_running_jobs()
        conflicts = []
        
        for running_job in running_jobs:
            if running_job == job_name:
                continue  # Skip self
            
            running_job_config = jobs.get(running_job)
            if not running_job_config:
                continue
            
            running_resources = self.get_job_resources(running_job_config)
            
            # Check for overlapping resources
            if (job_resources['sources'] & running_resources['sources'] or
                job_resources['destinations'] & running_resources['destinations']):
                conflicts.append(running_job)
        
        return conflicts