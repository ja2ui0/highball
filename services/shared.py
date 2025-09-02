"""
Global Command Factories
Centralized SSH and Container/Restic command building to eliminate duplication
"""
from typing import Dict, List, Optional
from enum import Enum
import shlex


# =============================================================================
# **SSH COMMAND FACTORY** - Centralized SSH command building
# =============================================================================

class SSHCommandFactory:
    """Centralized SSH command building to eliminate 15+ instances of duplication"""
    
    def __init__(self, ssh_key_path: str = '/config/local/secrets/.ssh/id_highball'):
        self.ssh_key_path = ssh_key_path
        self.standard_options = [
            '-o', 'ConnectTimeout=10',
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
        port: Optional[int] = None
    ) -> List[str]:
        """Build standard SSH command with consistent options"""
        cmd = ['ssh']
        
        if use_key:
            cmd.extend(['-i', self.ssh_key_path])
        
        if port:
            cmd.extend(['-p', str(port)])
            
        cmd.extend(self.standard_options)
        cmd.append(f'{username}@{hostname}')
        cmd.append(remote_command)
        
        return cmd
    
    def build_scp_command(
        self,
        source: str,
        destination: str, 
        hostname: str,
        username: str,
        use_key: bool = True,
        port: Optional[int] = None,
        recursive: bool = False
    ) -> List[str]:
        """Build SCP command with consistent options"""
        cmd = ['scp']
        
        if use_key:
            cmd.extend(['-i', self.ssh_key_path])
            
        if port:
            cmd.extend(['-P', str(port)])  # Note: scp uses -P not -p
            
        if recursive:
            cmd.append('-r')
            
        cmd.extend(self.standard_options)
        cmd.extend([source, f'{username}@{hostname}:{destination}'])
        
        return cmd
    
    def wrap_with_sshpass(self, ssh_command: List[str], password: str) -> List[str]:
        """Wrap SSH command with sshpass for password authentication"""
        return ['sshpass', '-p', password] + ssh_command


# =============================================================================
# **CONTAINER/RESTIC COMMAND FACTORY** - Centralized container command building  
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